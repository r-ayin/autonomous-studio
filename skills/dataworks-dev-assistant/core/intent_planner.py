#!/usr/bin/env python3
"""意图规划器（intent_planner）

借鉴 GOAP（Goal-Oriented Action Planning）的确定性意图路由：
  Action     ← module.yaml 的 intent（script/api + params）
  World      ← NL 抽出的 entities（project / date / keyword / status / owner / ...）
  Pre-cond   ← params.required + alias 映射成 semantic variable
  Effect     ← ACTION_EFFECTS 硬编码表（第一版，未来迁入 module.yaml）
  Planner    ← trigger 正向匹配 goal + 反向拼链（max depth = 2）

用法：
    python intent_planner.py "用户原话"
    python intent_planner.py "用户原话" --top-k 3 --json
    python intent_planner.py "用户原话" --module discovery --module task-ops
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import yaml

# ─── 路径 ─────────────────────────────────────────────
_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_CORE_DIR)
_SKILL_ROOT = os.path.dirname(_SRC_DIR)
MODULES_DIR = os.path.join(_SRC_DIR, "modules")

# ─── Alias：param 名 → semantic variable ─────────────
# 同一个 var 多个 param 表示"二选一"（project-id / project-name）
PARAM_ALIASES = {
    "project-id": "project", "project-name": "project", "projectId": "project",
    "owner": "owner", "mine": "owner",
    "node-id": "node_id", "nodeId": "node_id",
    "task-id": "task_id", "taskId": "task_id",
    "task-instance-id": "instance_id", "taskInstanceId": "instance_id",
    "keyword": "keyword",
    "date": "bizdate", "biz-date": "bizdate", "bizdate": "bizdate",
    "status": "status",
    "baseline-id": "baseline_id", "baselineId": "baseline_id",
    "alarm-id": "alarm_id",
    "workspace": "project",
}

# ─── Effects：硬编码（第一版） ─────────────────────────
# 跑完这个 action 后 agent 能获得哪些 semantic var
ACTION_EFFECTS = {
    "discovery.identify": ["project", "node_id", "task_id", "table_guid"],
    "discovery.search-tables-by-owner": ["project", "table_guid"],
    "discovery.search-nodes": ["project", "node_id", "task_id"],
    "discovery.partitions": ["table_guid"],
    "discovery.lineage": ["upstream", "downstream"],
    "discovery.columns": ["columns"],
    "discovery.my-data-assets": ["album_id"],
    "discovery.trace-upstream": ["root_cause"],
    "task-ops.ops-overview": ["instance_list", "task_id"],
    "task-ops.daily-check": ["instance_list", "task_id"],
    "task-ops.query-instances": ["instance_list", "task_id", "instance_id"],
    "task-ops.task-detail": ["deps", "task_id"],
    "task-ops.baseline-overview": ["baseline_id"],
    "task-ops.baseline-gantt": ["gantt"],
    "task-ops.log-analyzer": ["error_blocks"],
    "task-ops.di-overview": ["di_summary"],
    "task-ops.manual-biz-overview": ["dag_id"],
    "task-ops.alarm-diagnose": ["diagnosis"],
    "task-ops.smoke-test": ["smoke_result"],
    "task-ops.duty-query": ["duty"],
}


# ─── 数据类 ──────────────────────────────────────────
@dataclass
class Entity:
    var: str
    value: str
    source: str = "nl"
    confidence: float = 1.0


@dataclass
class Action:
    id: str
    module: str
    script: Optional[str]
    api: Optional[str]
    triggers: List[str]
    params: List[Dict]
    note: str
    write: bool = False

    @property
    def script_rel(self) -> Optional[str]:
        if not self.script:
            return None
        return f"src/modules/{self.module}/scripts/{self.script}"

    def required_vars(self) -> List[str]:
        """返回必需的 semantic var 列表（param.required 聚合后）"""
        vars_ = set()
        for p in self.params:
            if p.get("required"):
                svar = PARAM_ALIASES.get(p["name"], p["name"])
                vars_.add(svar)
        return sorted(vars_)

    def param_name_for_var(self, var: str, value: Optional[str] = None) -> Optional[str]:
        """找一个 bind 到该 var 的 param 名。
        传入 value 时按类型偏好：纯数字 → *-id 类；字符串 → *-name 类。"""
        cands = [p["name"] for p in self.params
                 if PARAM_ALIASES.get(p["name"], p["name"]) == var]
        if not cands:
            return None
        if value is not None:
            is_digit = str(value).isdigit()
            prefer = "id" if is_digit else "name"
            hit = next((c for c in cands if prefer in c.lower()), None)
            if hit:
                return hit
        return cands[0]

    def positional_param(self) -> Optional[Dict]:
        return next((p for p in self.params if p.get("positional")), None)

    def effects(self) -> List[str]:
        return ACTION_EFFECTS.get(self.id, [])


@dataclass
class PlanStep:
    action_id: str
    target: str          # 脚本相对路径 or <api:name>
    args: Dict[str, str]
    positional: str = ""


@dataclass
class Plan:
    intent_id: str
    confidence: float
    cost: int
    steps: List[PlanStep]
    missing: List[str] = field(default_factory=list)
    reason: str = ""
    write: bool = False

    def command(self) -> str:
        lines = []
        for s in self.steps:
            if s.target.startswith("<api:"):
                lines.append(s.target)
                continue
            arg_str = " ".join(f"--{k} {v}" for k, v in s.args.items())
            parts = [f"python {s.target}"]
            if s.positional:
                parts.append(s.positional)
            if arg_str:
                parts.append(arg_str)
            lines.append(" ".join(parts))
        return " && ".join(lines)


# ─── 加载 Actions ────────────────────────────────────
def load_actions(modules: Optional[List[str]] = None) -> List[Action]:
    if modules:
        targets = modules
    else:
        targets = [d for d in os.listdir(MODULES_DIR)
                   if os.path.isdir(os.path.join(MODULES_DIR, d))]
    actions = []
    for mod in targets:
        yaml_path = os.path.join(MODULES_DIR, mod, "module.yaml")
        if not os.path.isfile(yaml_path):
            continue
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for intent in data.get("intents", []):
            actions.append(Action(
                id=intent["id"],
                module=data["name"],
                script=intent.get("script"),
                api=intent.get("api"),
                triggers=intent.get("triggers", []),
                params=intent.get("params") or [],
                note=intent.get("note", ""),
                write=bool(intent.get("write", False)),
            ))
    return actions


# ─── 实体抽取 ────────────────────────────────────────
_PROJECT_RE = [
    re.compile(r"(?:工作空间|项目|空间|workspace)\s*[：:]?\s*['\"]?([A-Za-z_][A-Za-z0-9_-]*)['\"]?"),
    re.compile(r"([A-Za-z_][A-Za-z0-9_-]{2,})\s*(?:工作空间|项目|空间)"),
]
_TABLE_RE = [
    re.compile(r"表\s*[：:]?\s*([A-Za-z_][A-Za-z0-9_.]{2,})"),
    re.compile(r"\b((?:dim|fact|ods|dwd|dws|ads|tmp|stg|ads|dim|ka)_[A-Za-z0-9_]+)"),
]


def extract_entities(text: str) -> Dict[str, Entity]:
    ents: Dict[str, Entity] = {}

    # project
    for r in _PROJECT_RE:
        m = r.search(text)
        if m:
            ents["project"] = Entity("project", m.group(1), "nl", 0.8)
            break

    # date
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if m:
        ents["bizdate"] = Entity("bizdate", m.group(1))
    elif "昨天" in text:
        ents["bizdate"] = Entity("bizdate", "yesterday")
    elif "今天" in text:
        ents["bizdate"] = Entity("bizdate", "today")

    # status
    if "失败" in text:
        ents["status"] = Entity("status", "failed")
    elif "成功" in text:
        ents["status"] = Entity("status", "success")
    elif "运行中" in text:
        ents["status"] = Entity("status", "running")

    # owner
    if re.search(r"我的|我负责|我owner|我拥有", text):
        ents["owner"] = Entity("owner", "me")
    else:
        m = re.search(r"\b(\d{5,8})\b", text)
        if m:
            ents["owner"] = Entity("owner", m.group(1), "nl", 0.5)

    # node_id / instance_id
    m = re.search(r"节点\s*(?:id)?\s*[：:]?\s*(\d{6,})", text, re.I)
    if m:
        ents["node_id"] = Entity("node_id", m.group(1))
    m = re.search(r"实例\s*(?:id)?\s*[：:]?\s*(\d{8,})", text, re.I)
    if m:
        ents["instance_id"] = Entity("instance_id", m.group(1))

    # keyword / table
    for r in _TABLE_RE:
        m = r.search(text)
        if m:
            ents["keyword"] = Entity("keyword", m.group(1), "nl", 0.7)
            break

    return ents


# ─── Goal 匹配 ───────────────────────────────────────
_NORMALIZE_DROP = re.compile(r"[的了吗呢啊呀啦\s]")


def _normalize(s: str) -> str:
    return _NORMALIZE_DROP.sub("", s)


def trigger_score(text: str, triggers: List[str]) -> Tuple[float, str]:
    """归一化后按最长命中 trigger 打分。
    - 短 trigger（<3 字符）需严格包含，不给分
    - 长 trigger（≥4 字符）按长度线性打分
    """
    norm_text = _normalize(text)
    best = (0.0, "")
    for t in triggers:
        if not t:
            continue
        nt = _normalize(t)
        if len(nt) < 3 or nt not in norm_text:
            continue
        score = min(1.0, len(nt) / 6.0)
        if score > best[0]:
            best = (score, t)
    return best


# ─── 单步规划 ────────────────────────────────────────
def plan_for_action(
    action: Action,
    entities: Dict[str, Entity],
    all_actions: List[Action],
    depth: int = 0,
    max_depth: int = 2,
) -> Plan:
    required = action.required_vars()
    chain: List[PlanStep] = []
    bound: Dict[str, str] = {}
    missing: List[str] = []

    for svar in required:
        if svar in entities:
            bound[svar] = entities[svar].value
            continue
        # 尝试从其他 action 的 effects 拼链
        if depth < max_depth:
            provider = next(
                (a for a in all_actions
                 if svar in a.effects() and a.id != action.id and not a.write),
                None,
            )
            if provider:
                sub = plan_for_action(provider, entities, all_actions, depth + 1, max_depth)
                if not sub.missing:
                    chain.extend(sub.steps)
                    bound[svar] = f"<from:{provider.id}.{svar}>"
                    continue
        missing.append(svar)

    if missing:
        return Plan(
            intent_id=action.id,
            confidence=0.0,
            cost=99,
            steps=[],
            missing=missing,
            reason=f"缺参数：{missing}",
            write=action.write,
        )

    # 组装本 action 最后一步
    args: Dict[str, str] = {}
    positional_val = ""
    pos_param = action.positional_param()
    pos_name = pos_param["name"] if pos_param else None

    # 先填 required
    for svar, val in bound.items():
        pname = action.param_name_for_var(svar, val)
        if pname == pos_name:
            positional_val = val
        elif pname:
            args[pname] = val

    # 再填可选（entities 里有、action 也接收的）
    for svar, ent in entities.items():
        if svar in bound:
            continue
        pname = action.param_name_for_var(svar, ent.value)
        if not pname:
            continue  # 本 action 不接收这个 var
        if pname == pos_name and not positional_val:
            positional_val = ent.value
        elif pname != pos_name:
            args[pname] = ent.value

    target = action.script_rel or f"<api:{action.api}>"
    step = PlanStep(action.id, target, args, positional_val)

    total_cost = len(chain) + 1
    base_conf = 1.0 if not chain else 0.6

    return Plan(
        intent_id=action.id,
        confidence=base_conf,
        cost=total_cost,
        steps=chain + [step],
        write=action.write,
    )


# ─── 主流程 ──────────────────────────────────────────
def plan(text: str, top_k: int = 3, modules: Optional[List[str]] = None) -> Dict:
    actions = load_actions(modules)
    entities = extract_entities(text)

    scored: List[Tuple[Action, float, str]] = []
    for a in actions:
        s, t = trigger_score(text, a.triggers)
        if s > 0:
            scored.append((a, s, t))
    scored.sort(key=lambda x: x[1], reverse=True)

    plans: List[Plan] = []
    for a, s, matched in scored[: top_k * 3]:
        p = plan_for_action(a, entities, actions)
        p.confidence = round(p.confidence * s, 2)
        p.reason = f'trigger "{matched}" (score={s:.2f})'
        plans.append(p)

    # 排序：有参数的 > 缺参数的；高 confidence > 低；cost 低 > 高
    plans.sort(
        key=lambda p: (not p.missing, p.confidence, -p.cost),
        reverse=True,
    )
    plans = plans[:top_k]

    return {
        "input": text,
        "entities": {k: asdict(v) for k, v in entities.items()},
        "plans": [
            {
                "intent_id": p.intent_id,
                "confidence": p.confidence,
                "cost": p.cost,
                "write": p.write,
                "missing": p.missing,
                "reason": p.reason,
                "command": p.command() if not p.missing else "",
                "steps": [
                    {
                        "action_id": s.action_id,
                        "target": s.target,
                        "args": s.args,
                        "positional": s.positional,
                    }
                    for s in p.steps
                ],
            }
            for p in plans
        ],
    }


def format_human(r: Dict) -> str:
    out = [f"输入：{r['input']}"]
    if r["entities"]:
        out.append("抽取实体：")
        for k, v in r["entities"].items():
            out.append(f"  {k} = {v['value']}  ({v['source']}, conf={v['confidence']})")
    out.append("")
    out.append(f"━━━ 候选规划（top {len(r['plans'])}）━━━")
    for i, p in enumerate(r["plans"], 1):
        out.append("")
        tag = " [WRITE]" if p["write"] else ""
        out.append(f"[{i}] {p['intent_id']}{tag}  confidence={p['confidence']} cost={p['cost']}")
        out.append(f"    {p['reason']}")
        if p["missing"]:
            out.append(f"    ⚠️ 缺参数：{p['missing']}")
        elif p["command"]:
            out.append(f"    ▸ {p['command']}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", help="用户原话")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--module", action="append", help="限定模块（可多次）")
    args = ap.parse_args()

    r = plan(args.text, top_k=args.top_k, modules=args.module)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(format_human(r))


if __name__ == "__main__":
    main()
