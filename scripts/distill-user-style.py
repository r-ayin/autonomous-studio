#!/usr/bin/env python3
"""distill-user-style.py — 用户决策风格蒸馏器（从会话 transcript 提炼用户自己的决策风格）

修复"蒸馏产物只写不读"断裂：从用户亲口说的会话 transcript 的 type=user 行提炼
决策风格契约，落 .claude/memory/user-decision-style.md，被 loop PROMPT Step0 消费。

与 distill-patterns.py 的区别（两条独立蒸馏线）:
  - distill-patterns.py: 蒸馏 engine 自己跑的 case → decision-patterns.md（engine 自蒸馏）
  - distill-user-style.py: 蒸馏用户亲口说的指示 → user-decision-style.md（蒸馏用户自己）

三步:
  Step 1 (确定性, 零 token): 读 jsonl → 提取 type=user 行 → 按 cwd 聚类 →
          TF-IDF+cosine 去重 → 筛指示性输入（决策信号词）→ 副产物 planning/intent-sources/<project>.txt
  Step 2 (可选 LLM, --llm): 对指示性输入调 claude -p 蒸馏成 4 维度规则
  Step 3 (--apply): 跑 verify-user-style.sh 门禁，通过则 Python open() 直写 user-decision-style.md

设计原则:
  - 蒸馏用户不是蒸馏 engine：原料只取 type=user 且 userType=external 且非 sidechain
  - 孤证不取：规则须≥2条独立输入支撑
  - evidence 必须引用用户原话，非 LLM 臆测
  - 确定性 > 提示词：Step1/3 零 LLM，bash gate 不可协商

用法:
  python3 scripts/distill-user-style.py --project .            # 干跑（只报告）
  python3 scripts/distill-user-style.py --project . --apply    # 落盘（仅 Step1 骨架）
  python3 scripts/distill-user-style.py --project . --llm --apply  # 含 LLM 蒸馏 + 落盘
"""
import os, sys, json, glob, argparse, subprocess, re, math
from collections import Counter
from datetime import datetime, timezone

DIMENSIONS = [
    "沟通粒度与汇报偏好",
    "确认门槛与自动化边界",
    "风险偏好与节奏",
    "技术选型与实现倾向",
]

# 决策信号词：筛选"指示性"用户输入（非闲聊/非纯问答/非复述）
SIGNAL_RE = re.compile(
    r"不要|必须|先.{0,12}后|用.{0,15}不用|别|禁止|按我|以后|默认|改为|撤回|优先|"
    r"先修|再修|不要碰|保留|删掉|增加|去掉|换|改回|切到|启用|禁用|重写|重构|"
    r"不要散文|可观察|证据|确认|notify|suggest|silent|opt-worktree|push|"
    r"彻底|综合|排查|落地|验证|回滚|兜底|节流|限流|配额",
    re.I,
)


def now_ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json_robust(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def extract_text(msg):
    """从 message.content 提取纯文本（兼容 str / list 两种形态）"""
    if not msg or not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return ""


def project_name_from_cwd(cwd, base="/home/admin/workspace"):
    """归一化项目名：取相对 base 的首段；base 自身→workspace-root"""
    if not cwd:
        return "unknown"
    if cwd == base:
        return "workspace-root"
    try:
        rel = os.path.relpath(cwd, base)
    except ValueError:
        return "unknown"
    if rel in (".", "..", ""):
        return "workspace-root"
    parts = rel.split("/")
    return parts[0] if parts and parts[0] not in (".", "..", "") else "workspace-root"


# ---- TF-IDF 去重（复用 index-cases.py 的零依赖实现）----

def tokenize(text):
    if not text:
        return []
    text = text.lower()
    toks = re.findall(r"[a-z0-9_]+|[一-鿿]", text)
    cn = [t for t in toks if re.match(r"[一-鿿]", t)]
    bigrams = [cn[i] + cn[i + 1] for i in range(len(cn) - 1)]
    return toks + bigrams


def build_tfidf(docs):
    """docs=[{text,...}]，给每个 doc 加 vec/norm，返回 idf"""
    N = len(docs) or 1
    df = Counter()
    for d in docs:
        d["tokens"] = tokenize(d["text"])
        for t in set(d["tokens"]):
            df[t] += 1
    idf = {t: math.log((N + 1) / (df[t] + 1)) + 1 for t in df}
    for d in docs:
        tf = Counter(d["tokens"])
        d["vec"] = {t: (cnt / max(1, len(d["tokens"]))) * idf.get(t, 1) for t, cnt in tf.items()}
        d["norm"] = math.sqrt(sum(v * v for v in d["vec"].values())) or 1e-9
    return idf


def cosine(qvec, qnorm, doc):
    dot = sum(v * doc["vec"].get(t, 0) for t, v in qvec.items())
    return dot / (qnorm * doc["norm"])


def dedup_by_similarity(items, threshold=0.85):
    """items=[{text,cwd,ts}]，按 TF-IDF cosine 去重，相似≥threshold 视为同义保留首条+计数"""
    if not items:
        return []
    docs = [{"text": it["text"]} for it in items]
    build_tfidf(docs)
    kept = []
    for i, it in enumerate(items):
        d = docs[i]
        is_dup = False
        for k in kept:
            sim = cosine(d["vec"], d["norm"], k["_doc"])
            if sim >= threshold:
                k["count"] += 1
                if len(k["dup_texts"]) < 3:
                    k["dup_texts"].append(it["text"][:60])
                is_dup = True
                break
        if not is_dup:
            kept.append({"item": it, "count": 1, "dup_texts": [], "_doc": d})
    for k in kept:
        k.pop("_doc", None)
    return kept


# ---- Step 1: 确定性原料提取 ----

def step1_extract(transcript_dir, project_dir):
    """读 jsonl → 提取 user 行 → 按 cwd 聚类 → 去重 → 筛指示性输入"""
    files = sorted(glob.glob(os.path.join(transcript_dir, "*.jsonl")))
    print(f"  扫描 {len(files)} 个 transcript 文件")
    all_user = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if rec.get("type") != "user":
                        continue
                    if rec.get("isSidechain"):
                        continue
                    if rec.get("userType") and rec["userType"] != "external":
                        continue
                    text = extract_text(rec.get("message", {})).strip()
                    if not text or len(text) < 4:
                        continue
                    # 排除系统注入（command 标签、Caveat、local-command 前缀）
                    if text.startswith("<") or text.startswith("Caveat") or text.startswith("local-command"):
                        continue
                    all_user.append({
                        "text": text,
                        "cwd": rec.get("cwd", ""),
                        "ts": rec.get("timestamp", ""),
                        "session": os.path.basename(fp).replace(".jsonl", ""),
                    })
        except Exception:
            continue
    print(f"  提取 {len(all_user)} 条外部 user 输入")

    by_project = {}
    for u in all_user:
        pn = project_name_from_cwd(u["cwd"])
        by_project.setdefault(pn, []).append(u)
    print(f"  聚类到 {len(by_project)} 个项目 cwd")

    # 每个项目去重 + 写 intent-sources 副产物（填补 §C-4 设计占位）
    intent_dir = os.path.join(project_dir, "planning", "intent-sources")
    os.makedirs(intent_dir, exist_ok=True)
    all_dedup = []
    for pn, items in by_project.items():
        dedup = dedup_by_similarity(items)
        all_dedup.extend(dedup)
        with open(os.path.join(intent_dir, f"{pn}.txt"), "w", encoding="utf-8") as f:
            f.write(f"# {pn} — 用户口输入（去重后，{len(dedup)} 条 / 原始 {len(items)} 条）\n")
            f.write(f"# 由 distill-user-style.py Step1 生成，供 BUSINESS-INTENT 提炼 + 引擎阶段①CONTEXTUALIZE 读\n\n")
            for d in dedup:
                f.write(f"[{d['item']['ts'][:10]}] {d['item']['text']}\n")
    print(f"  去重后 {len(all_dedup)} 条独立输入，副产物落 planning/intent-sources/{len(by_project)} 文件")

    indicative = [d for d in all_dedup if SIGNAL_RE.search(d["item"]["text"])]
    print(f"  筛出 {len(indicative)} 条指示性输入（含决策信号词，将喂 Step2 LLM）")
    return all_dedup, indicative, by_project


# ---- Step 2: LLM 蒸馏 ----

STEP2_PROMPT = """你的全部输出必须且只能是一个 JSON 数组——第一个字符是 [，最后一个字符是 ]。禁止任何散文、解释、前言、后缀、markdown 代码块标记。

任务：从以下用户指示性输入（共 {n} 条，已去重，按时间序）提取用户决策风格规则，分四个维度：
1. 沟通粒度与汇报偏好（结论先行 vs 详细展开、汇报粒度、证据要求）
2. 确认门槛与自动化边界（哪些操作可自动、哪些必须确认、不可逆动作门槛）
3. 风险偏好与节奏（快速 MVP vs 保守稳健、修复深度、worktree 策略）
4. 技术选型与实现倾向（偏好库/框架/模式、代码风格、命名注释密度）

硬约束：
- 只提取有≥2条独立输入支撑的规则，孤证不取
- evidence_inputs 必须引用用户原话片段（≤3条），不可改写不可臆测
- signature_prefix 用 `<维度缩写>:<动词短语>` 格式（维度缩写：comm/gate/risk/tech）
- confidence = 支撑输入数 / 该维度总指示输入数（0-1）

输出格式（每个元素）：
{{"dimension":"维度名","signature_prefix":"comm:xxx","rule_text":"规则描述","evidence_inputs":["原话1","原话2"],"confidence":0.7}}

再次强调：直接输出 JSON 数组，第一个字符必须是 [。

用户输入：
{inputs}"""


def step2_llm_distill(indicative, project_dir):
    """调 claude -p 蒸馏成 4 维度规则，分批避免 prompt 过大"""
    items_sorted = sorted(indicative, key=lambda d: d["item"]["ts"])
    BATCH = 80
    all_rules = []
    proposals = []
    for batch_idx in range(0, len(items_sorted), BATCH):
        batch = items_sorted[batch_idx:batch_idx + BATCH]
        bt = "\n".join(
            f"[{batch_idx + j + 1}] ({d['item']['ts'][:10]}) {d['item']['text'][:200]}"
            for j, d in enumerate(batch)
        )
        prompt = STEP2_PROMPT.format(n=len(batch), inputs=bt)
        op = None
        status = "skipped"
        if subprocess.run(["which", "claude"], capture_output=True).returncode == 0:
            try:
                # bypassPermissions：非交互不弹权限；plan 模式会让 LLM 倾向"展示计划"
                # 而非直接吐 JSON（distill-patterns.py 的 LLM 蒸馏长期无效即此因），故改 bypass
                r = subprocess.run(
                    ["claude", "-p", prompt, "--permission-mode", "bypassPermissions"],
                    cwd=project_dir, capture_output=True, text=True, timeout=180)
                op = r.stdout.strip()
                if op:
                    status = "ok"
                else:
                    status = "empty_response" + (f":stderr={r.stderr.strip()[:120]}" if r.stderr.strip() else "")
            except subprocess.TimeoutExpired:
                status = "timeout"
            except Exception as e:
                status = f"exception:{type(e).__name__}:{str(e)[:80]}"
        proposals.append({"batch": batch_idx, "n": len(batch), "llm_status": status, "llm_output": op[:3000] if op else None})
        if op:
            # 鲁棒提取 JSON 数组：第一个 [ 到最后一个 ]，剥离前后散文/markdown 标记
            op_clean = re.sub(r"```(?:json)?", "", op)
            start = op_clean.find("[")
            end = op_clean.rfind("]")
            if start != -1 and end != -1 and end > start:
                candidate = op_clean[start:end + 1]
                try:
                    rules = json.loads(candidate)
                    if isinstance(rules, list):
                        all_rules.extend(rules)
                except Exception as e:
                    print(f"    批 {batch_idx//BATCH+1}: JSON 解析失败 {e}, candidate 前 200: {candidate[:200]}")
            else:
                print(f"    批 {batch_idx//BATCH+1}: 未找到 JSON 数组边界, output 前 200: {op[:200]}")
        print(f"  批 {batch_idx // BATCH + 1}/{(len(items_sorted) + BATCH - 1) // BATCH}: status={status}, 累计规则 {len(all_rules)}")

    # 按签名去重（同签名保留首条）
    seen = {}
    dedup_rules = []
    for r in all_rules:
        sig = r.get("signature_prefix", "")
        if sig and sig in seen:
            continue
        if sig:
            seen[sig] = True
        dedup_rules.append(r)

    prop_path = os.path.join(project_dir, ".claude", "decisions", "user-style-proposals.json")
    os.makedirs(os.path.dirname(prop_path), exist_ok=True)
    with open(prop_path, "w", encoding="utf-8") as f:
        json.dump({"proposals": proposals, "rules_extracted": len(all_rules), "rules_dedup": len(dedup_rules)},
                  f, ensure_ascii=False, indent=2)
    print(f"  Step2: {len(proposals)} 批 → {len(all_rules)} 条规则候选 → 去重后 {len(dedup_rules)} 条，提案落 {prop_path}")
    return dedup_rules


# ---- Step 3: 渲染 + 门禁 + 落盘 ----

def build_md(rules, source_counts):
    """把规则渲染成 user-decision-style.md"""
    by_dim = {d: [] for d in DIMENSIONS}
    for r in rules:
        dim = r.get("dimension", "")
        if dim in by_dim:
            by_dim[dim].append(r)
    lines = [
        "---",
        "name: user-decision-style",
        "description: 从用户会话 transcript 蒸馏的决策风格契约 — 由 distill-user-style.py 自动同步",
        "metadata:",
        "  type: project",
        "---",
        "",
        "# 用户决策风格契约",
        "",
        "> 引擎 Step0 必读，与 autonomous-constraints.md 同权重遵守。",
        f"> 原料：~/.claude/projects/-home-admin-workspace/*.jsonl 的 type=user 行（{source_counts['files']} 会话/{source_counts['user_total']} 条去重输入）。",
        "> 规则须有≥2条独立用户输入支撑（孤证不取）。evidence 引用用户原话片段，非 LLM 臆测。",
        f"> 最后蒸馏：{now_ts()}",
        "",
    ]
    for dim in DIMENSIONS:
        lines.append(f"## {dim}")
        rules_d = by_dim.get(dim, [])
        if not rules_d:
            lines.append("_(该维度暂无≥2条输入支撑的规则，待积累)_")
            lines.append("")
            continue
        for r in rules_d:
            sig = r.get("signature_prefix", "")
            rule = r.get("rule_text", "")
            evid = r.get("evidence_inputs", []) or []
            conf = r.get("confidence", 0)
            evid_str = " / ".join(f"「{e}」" for e in evid[:3]) if evid else "_(无)_"
            lines.append(f"### Style: {sig.split(':')[-1] if ':' in sig else sig}")
            lines.append(f"- **签名前缀**: `{sig}`")
            lines.append(f"- **规则**: {rule}")
            lines.append(f"- **evidence**: {evid_str}")
            lines.append(f"- **confidence**: {conf}")
            lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--apply", action="store_true", help="落盘（否则干跑只报告）")
    ap.add_argument("--llm", action="store_true", help="启用 Step2 LLM 蒸馏")
    ap.add_argument("--transcript-dir",
                    default=os.path.expanduser("~/.claude/projects/-home-admin-workspace"))
    args = ap.parse_args()

    P = os.path.abspath(args.project)
    md_path = os.path.join(P, ".claude", "memory", "user-decision-style.md")

    print("=== Step 1: 确定性原料提取（零 token）===")
    all_dedup, indicative, by_project = step1_extract(args.transcript_dir, P)
    source_counts = {
        "files": len(glob.glob(os.path.join(args.transcript_dir, "*.jsonl"))),
        "user_total": len(all_dedup),
    }

    rules = []
    if args.llm:
        print("=== Step 2: LLM 蒸馏（可选）===")
        if not indicative:
            print("  无指示性输入，跳过")
        else:
            rules = step2_llm_distill(indicative, P)
    else:
        print("=== Step 2: 跳过（未传 --llm）===")

    print("=== Step 3: 渲染 + 门禁 + 落盘 ===")
    md_content = build_md(rules, source_counts)

    if not args.apply:
        print("\n[干跑] 未落盘。加 --apply 落盘。")
        print(f"  将写入 {md_path}")
        print(f"  规则数: {len(rules)} (4 维度)")
        for d in DIMENSIONS:
            n = sum(1 for r in rules if r.get("dimension") == d)
            print(f"    {d}: {n} 条")
        for r in rules[:5]:
            print(f"    [{r.get('signature_prefix')}] {r.get('rule_text', '')[:60]}")
        return

    # 先写 md（门禁要检查内容），门禁失败则回滚删除
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    gate = os.path.join(P, "scripts", "verify-user-style.sh")
    if os.path.exists(gate):
        print("  跑 verify-user-style.sh 门禁...")
        r = subprocess.run(["bash", gate, P], capture_output=True, text=True)
        print(r.stdout)
        if r.returncode != 0:
            print(f"  ❌ 门禁失败，回滚删除 {md_path}:\n{r.stderr}")
            os.remove(md_path)
            return
        print(f"✓ 门禁通过，已落盘 {md_path}")
    else:
        print(f"✓ 已落盘 {md_path}（无门禁脚本，未校验）")


if __name__ == "__main__":
    main()
