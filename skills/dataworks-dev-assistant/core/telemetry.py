#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行时遥测 —— 记录脚本调用，驱动数据优化

每次脚本运行写一行 JSONL 到 .dataworks/telemetry.jsonl（用户工作目录）。

API:
    from telemetry import telemetry_start, telemetry_end

    telemetry_start("ops_overview.py", module="task-ops", project_id=14255)
    # ... 脚本逻辑 ...
    telemetry_end(result={"severity": "ok", "count": 5})

CLI:
    python telemetry.py                    # 打印摘要
    python telemetry.py --chains           # 检测常见调用链
    python telemetry.py --failures         # 高失败率脚本
    python telemetry.py --since 2026-04-01 # 按日期过滤
"""

import json
import os
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime

# ─── 配置 ──────────────────────────────────────────────────────

_TELEMETRY_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "telemetry.jsonl")

# ─── 模块状态（每个脚本一个进程，用全局变量即可） ──────────────

_start_time = None
_context = {}


# ─── 敏感参数脱敏（AUDITT-01，audit-2026-07-06-005） ──────────────
# telemetry 落本地 JSONL 且经 telemetry_upload.py 上传远端，
# sql/password/token 等 kwarg 全程零脱敏会外泄表名/列名/WHERE 值（PII/业务数据）。
_SENSITIVE_KWARGS = {
    "password", "passwd", "token", "access_token", "refresh_token",
    "secret", "api_key", "apikey", "credential", "credentials",
    "session_code", "cookie", "authorization",
}


def _sanitize_sql(sql_text, max_len=50):
    """对 SQL 文本保留类型 + 前 max_len 字符，丢弃其余。

    例：'SELECT phone FROM users WHERE id=13800000000'
        → 'SELECT phone FROM users WHERE id=1380000000…'(截断)
    """
    if not isinstance(sql_text, str):
        sql_text = str(sql_text)
    head = sql_text.strip()
    # 提取首个 SQL 关键字作为类型标记
    first_tok = head.split(None, 1)[0].upper() if head else ""
    if len(head) <= max_len:
        body = head
    else:
        body = head[:max_len] + "…"
    return f"{first_tok}:{body}" if first_tok else body


def _sanitize_extra(extra):
    """对 args dict 中敏感 key 脱敏：sql 截断，凭证类丢弃值。"""
    if not extra:
        return extra
    sanitized = {}
    for k, v in extra.items():
        kl = k.lower()
        if kl == "sql":
            sanitized[k] = _sanitize_sql(v)
        elif kl in _SENSITIVE_KWARGS:
            sanitized[k] = "<redacted>"
        else:
            sanitized[k] = v
    return sanitized


# ─── 公开 API ──────────────────────────────────────────────────

# Session ID 管理已迁移到 runtime.py（Phase 0b）
# telemetry.py 保留 _ensure_session_id() 作为向后兼容 wrapper
from runtime import get_session_id as _ensure_session_id  # noqa: F401


def telemetry_start(script_name, module=None, intent=None, **kwargs):
    """脚本入口调用。记录启动时间和上下文参数。

    Args:
        script_name: 脚本文件名
        module: 所属模块名
        intent: agent 匹配到的 routing intent 描述（可选）
        **kwargs: project_id, date, node_id 等上下文参数
    """
    global _start_time, _context
    try:
        _start_time = time.monotonic()
        _context = {
            "script": script_name,
            "module": module,
            "session_id": _ensure_session_id(),
        }
        if intent:
            _context["intent"] = intent
        # 常用上下文字段直接保存
        for key in ("project_id", "date", "node_id", "keyword", "status"):
            if key in kwargs and kwargs[key] is not None:
                _context[key] = kwargs[key]
        # 其余参数放 args（敏感 kwarg 脱敏，避免 SQL/凭证外泄——AUDITT-01）
        extra = {k: v for k, v in kwargs.items()
                 if k not in ("project_id", "date", "node_id", "keyword", "status")
                 and v is not None}
        if extra:
            _context["args"] = _sanitize_extra(extra)
    except Exception:
        pass  # 遥测不影响主流程


def _summarize_api_calls():
    """从 BFF call log 中汇总本次脚本运行期间的 API 调用。

    返回 {"api_count": N, "total_api_ms": M, "apis": ["path1", ...]} 或 None。
    """
    try:
        log_path = os.path.join(os.path.expanduser("~"), ".dataworks", "logs", "dw_bff_calls.log")
        if not os.path.isfile(log_path) or _start_time is None:
            return None

        start_wall = datetime.now().timestamp() - (time.monotonic() - _start_time)
        calls = []
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    ts_str = entry.get("timestamp", "")
                    ts = datetime.fromisoformat(ts_str).timestamp()
                    if ts >= start_wall:
                        path = entry.get("request", {}).get("path", "?")
                        cost = entry.get("cost_ms", 0)
                        calls.append({"path": path, "cost_ms": round(cost)})
                except (json.JSONDecodeError, ValueError):
                    continue

        if not calls:
            return None
        return {
            "api_count": len(calls),
            "total_api_ms": sum(c["cost_ms"] for c in calls),
            "apis": [c["path"] for c in calls],
        }
    except Exception:
        return None


def telemetry_end(result=None, exit_code=0, error=None):
    """脚本结束调用。写一行 JSONL 记录。

    Args:
        result: 脚本输出的结构化摘要
        exit_code: 退出码
        error: 错误描述（exit_code!=0 时的原因）
    """
    try:
        global _start_time, _context
        duration_ms = int((time.monotonic() - _start_time) * 1000) if _start_time else 0

        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "session_id": _context.get("session_id"),
            "script": _context.get("script", "unknown"),
            "module": _context.get("module"),
            "duration_ms": duration_ms,
            "exit_code": exit_code,
        }

        # 错误原因
        if error:
            record["error"] = str(error)[:200]

        # intent（agent 匹配到的 routing 描述）
        intent = _context.get("intent")
        if intent:
            record["intent"] = intent

        # 合入上下文字段
        for key in ("project_id", "date", "node_id", "keyword", "status", "args"):
            val = _context.get(key)
            if val is not None:
                record[key] = val

        if result:
            record["result"] = result

        # API 调用汇总
        api_summary = _summarize_api_calls()
        if api_summary:
            record["api_calls"] = api_summary

        # 写文件
        filepath = _TELEMETRY_FILE
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

        # 重置状态
        _start_time = None
        _context = {}
    except Exception:
        pass  # 遥测不影响主流程


def telemetry_fail(script_name, module, exit_code, error=None):
    """telemetry_start 之前就失败时的快捷记录。

    解决 argparse 报错等场景：telemetry_start 还没调用，
    except 块里 _context 为空导致 script=unknown。

    用法:
        except SystemExit as e:
            telemetry_fail("ops_overview.py", "task-ops", e.code, error="argparse")
            raise
    """
    try:
        global _start_time, _context
        # 如果 telemetry_start 已调用过，直接用 telemetry_end
        if _context.get("script") and _context["script"] != "unknown":
            telemetry_end(exit_code=exit_code, error=error)
            return
        # 否则构造最小记录
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "session_id": os.environ.get("DW_BFF_SESSION_CODE"),
            "script": script_name,
            "module": module,
            "duration_ms": 0,
            "exit_code": exit_code,
        }
        if error:
            record["error"] = str(error)[:200]

        filepath = _TELEMETRY_FILE
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


# ─── 分析与报告 ────────────────────────────────────────────────

def _load_records(since=None):
    """加载 JSONL 记录，可选日期过滤。"""
    filepath = _TELEMETRY_FILE
    if not os.path.exists(filepath):
        return []
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                if since and r.get("ts", "") < since:
                    continue
                records.append(r)
            except json.JSONDecodeError:
                continue
    return records


def report_summary(records):
    """脚本调用次数 + 平均耗时"""
    by_script = defaultdict(lambda: {"count": 0, "total_ms": 0, "fail": 0})
    for r in records:
        name = r.get("script", "?")
        s = by_script[name]
        s["count"] += 1
        s["total_ms"] += r.get("duration_ms", 0)
        if r.get("exit_code", 0) != 0:
            s["fail"] += 1

    if not by_script:
        print("(无遥测数据)")
        return

    print(f"\n{'脚本':<30} {'调用':<6} {'平均耗时':<10} {'失败':<6}")
    print(f"{'─' * 30} {'─' * 6} {'─' * 10} {'─' * 6}")
    for name, s in sorted(by_script.items(), key=lambda x: -x[1]["count"]):
        avg = s["total_ms"] // s["count"] if s["count"] else 0
        avg_str = f"{avg}ms" if avg < 1000 else f"{avg / 1000:.1f}s"
        fail_str = str(s["fail"]) if s["fail"] else "-"
        print(f"  {name:<28} {s['count']:<6} {avg_str:<10} {fail_str:<6}")
    print(f"\n总计: {len(records)} 次调用")


def report_chains(records, window_sec=120):
    """检测频繁出现的连续调用链。

    优先按 session_id 分组（精确），无 session_id 时回退到 project_id + 时间窗口。
    输出如 "ops_overview -> query_instances (23 次)" 表示 agent 经常在
    ops_overview 后接着调 query_instances，可考虑合并或优化引导。
    """
    # 优先按 session_id 分组，无 session_id 的按 project_id 分组
    by_session = defaultdict(list)
    by_project = defaultdict(list)
    for r in records:
        sid = r.get("session_id")
        if sid:
            by_session[sid].append(r)
        else:
            pid = r.get("project_id", "none")
            by_project[pid].append(r)

    pair_count = defaultdict(int)
    triple_count = defaultdict(int)

    def _count_chains_from_group(group):
        """从已排序的记录组中提取调用链"""
        for i in range(len(group) - 1):
            a = group[i].get("script", "?")
            b = group[i + 1].get("script", "?")
            pair_count[f"{a} -> {b}"] += 1
            if i + 2 < len(group):
                c = group[i + 2].get("script", "?")
                triple_count[f"{a} -> {b} -> {c}"] += 1

    # session 内的记录天然有序，不需要时间窗口
    for sid, group in by_session.items():
        group.sort(key=lambda x: x.get("ts", ""))
        _count_chains_from_group(group)

    # 无 session_id 的记录用时间窗口回退
    for pid, group in by_project.items():
        group.sort(key=lambda x: x.get("ts", ""))
        # 按时间窗口切分为子组
        sub_group = [group[0]] if group else []
        for i in range(1, len(group)):
            ts_prev = group[i - 1].get("ts", "")
            ts_curr = group[i].get("ts", "")
            try:
                t_prev = datetime.fromisoformat(ts_prev)
                t_curr = datetime.fromisoformat(ts_curr)
                if (t_curr - t_prev).total_seconds() > window_sec:
                    _count_chains_from_group(sub_group)
                    sub_group = []
            except (ValueError, TypeError):
                pass
            sub_group.append(group[i])
        _count_chains_from_group(sub_group)

    if not pair_count:
        print("\n(无链式调用数据)")
        return

    print(f"\n两步调用链 (间隔 < {window_sec}s):")
    for chain, cnt in sorted(pair_count.items(), key=lambda x: -x[1])[:15]:
        print(f"  {chain}  ({cnt} 次)")

    if triple_count:
        print(f"\n三步调用链:")
        for chain, cnt in sorted(triple_count.items(), key=lambda x: -x[1])[:10]:
            if cnt >= 2:
                print(f"  {chain}  ({cnt} 次)")


def report_session(records, session_id=None):
    """回放指定 session 的完整调用流，或列出所有 session 摘要。

    指定 session_id 时输出该 session 的每步调用详情；
    不指定时输出所有 session 的摘要（调用数、成功率、时间跨度）。
    """
    # 按 session_id 分组
    by_session = defaultdict(list)
    for r in records:
        sid = r.get("session_id")
        if sid:
            by_session[sid].append(r)

    no_session = [r for r in records if not r.get("session_id")]

    if not by_session:
        print("\n(无 session 数据，旧记录缺少 session_id)")
        if no_session:
            print(f"  {len(no_session)} 条记录无 session_id")
        return

    if session_id:
        # 回放单个 session
        group = by_session.get(session_id)
        if not group:
            print(f"\nsession {session_id} 不存在")
            # 模糊匹配
            matches = [s for s in by_session if s.startswith(session_id)]
            if matches:
                print(f"  你是否要找: {', '.join(matches[:5])}")
            return

        group.sort(key=lambda x: x.get("ts", ""))
        pid = next((r.get("project_id") for r in group if r.get("project_id")), "?")
        ts_first = group[0].get("ts", "?")[:19]
        print(f"\nsession {session_id} ({ts_first}, projectId={pid}):")
        for i, r in enumerate(group, 1):
            script = r.get("script", "?")
            dur = r.get("duration_ms", 0)
            dur_str = f"{dur}ms" if dur < 1000 else f"{dur / 1000:.1f}s"
            code = r.get("exit_code", 0)
            mark = "✓" if code == 0 else f"✗(exit={code})"
            intent = r.get("intent", "")
            intent_str = f"  intent={intent}" if intent else ""
            # 附加关键上下文
            ctx_parts = []
            for key in ("node_id", "keyword", "date"):
                val = r.get(key)
                if val:
                    ctx_parts.append(f"{key}={val}")
            ctx_str = f"  {' '.join(ctx_parts)}" if ctx_parts else ""
            print(f"  {i}. {script:<25} {dur_str:<8} {mark}{intent_str}{ctx_str}")
    else:
        # 列出所有 session 摘要
        print(f"\n共 {len(by_session)} 个 session:")
        summaries = []
        for sid, group in by_session.items():
            group.sort(key=lambda x: x.get("ts", ""))
            total = len(group)
            fail = sum(1 for r in group if r.get("exit_code", 0) != 0)
            ts_first = group[0].get("ts", "?")[:16]
            pid = next((r.get("project_id") for r in group if r.get("project_id")), "?")
            summaries.append((ts_first, sid, pid, total, fail))

        summaries.sort(key=lambda x: x[0], reverse=True)
        for ts, sid, pid, total, fail in summaries[:20]:
            fail_str = f" fail={fail}" if fail else ""
            print(f"  {ts}  {sid}  pid={pid}  {total}步{fail_str}")

        if no_session:
            print(f"\n  + {len(no_session)} 条旧记录无 session_id")


def report_failures(records):
    """高失败率脚本"""
    by_script = defaultdict(lambda: {"total": 0, "fail": 0, "errors": []})
    for r in records:
        name = r.get("script", "?")
        s = by_script[name]
        s["total"] += 1
        if r.get("exit_code", 0) != 0:
            s["fail"] += 1

    failures = [(name, s) for name, s in by_script.items() if s["fail"] > 0]
    if not failures:
        print("\n(无失败记录)")
        return

    failures.sort(key=lambda x: -x[1]["fail"])
    print(f"\n{'脚本':<30} {'失败/总计':<12} {'失败率':<8}")
    print(f"{'─' * 30} {'─' * 12} {'─' * 8}")
    for name, s in failures:
        rate = s["fail"] / s["total"] * 100 if s["total"] else 0
        print(f"  {name:<28} {s['fail']}/{s['total']:<10} {rate:.0f}%")


# ─── Phase 2: 数据驱动分析 ────────────────────────────────────

def report_routing_coverage(records, skill_md_path=None):
    """分析 routing 命中率：哪些 intent 高频/低频/从未命中，哪些调用没有 intent。

    读取 SKILL.md 的意图路由表，与 telemetry 中的 intent 字段做 diff。
    """
    # 统计 intent 命中
    intent_counts = defaultdict(lambda: {"total": 0, "fail": 0})
    no_intent_count = 0
    for r in records:
        intent = r.get("intent")
        if intent:
            s = intent_counts[intent]
            s["total"] += 1
            if r.get("exit_code", 0) != 0:
                s["fail"] += 1
        else:
            no_intent_count += 1

    # 尝试读取 SKILL.md 路由表
    skill_intents = set()
    if skill_md_path and os.path.isfile(skill_md_path):
        with open(skill_md_path, "r", encoding="utf-8") as f:
            for line in f:
                # 匹配路由表行: | 用户说... | 执行方式... |
                if line.startswith("|") and "python" in line.lower():
                    parts = line.split("|")
                    if len(parts) >= 3:
                        trigger = parts[1].strip()
                        if trigger and trigger != "用户说":
                            skill_intents.add(trigger)

    print(f"\n{'intent':<40} {'调用':<6} {'失败':<6} {'失败率':<8}")
    print(f"{'─' * 40} {'─' * 6} {'─' * 6} {'─' * 8}")

    # 有 intent 的调用
    for intent, s in sorted(intent_counts.items(), key=lambda x: -x[1]["total"]):
        rate = s["fail"] / s["total"] * 100 if s["total"] else 0
        fail_str = f"{rate:.0f}%" if s["fail"] else "-"
        print(f"  {intent:<38} {s['total']:<6} {s['fail']:<6} {fail_str:<8}")

    if no_intent_count:
        print(f"\n  无 intent 的调用: {no_intent_count} 次（agent 自行拼命令，未走路由）")

    # 与 SKILL.md 路由表做 diff
    if skill_intents:
        matched_intents = set(intent_counts.keys())
        never_hit = skill_intents - matched_intents
        if never_hit:
            print(f"\n  从未命中的路由 ({len(never_hit)}):")
            for intent in sorted(never_hit):
                print(f"    ✗ {intent}")

    total_with_intent = sum(s["total"] for s in intent_counts.values())
    total = total_with_intent + no_intent_count
    if total:
        coverage = total_with_intent / total * 100
        print(f"\n  routing 覆盖率: {coverage:.0f}% ({total_with_intent}/{total})")


def report_scenario_gaps(records, skill_md_path=None):
    """对比高频 chain 与 SKILL.md scenarios，发现 gap。

    高频出现但 scenario 没有覆盖 → 需要补 scenario。
    scenario 定义了但从未出现 → 死 scenario。
    """
    # 按 session 提取完整调用链
    by_session = defaultdict(list)
    for r in records:
        sid = r.get("session_id")
        if sid:
            by_session[sid].append(r)

    # 统计 session 级别的脚本序列
    chain_count = defaultdict(int)
    for sid, group in by_session.items():
        group.sort(key=lambda x: x.get("ts", ""))
        scripts = [r.get("script", "?") for r in group]
        chain_key = " → ".join(scripts)
        chain_count[chain_key] += 1

    # 读取 SKILL.md scenarios
    scenario_chains = {}
    if skill_md_path and os.path.isfile(skill_md_path):
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 粗略提取 scenario 名和涉及的脚本
        import re
        scenario_blocks = re.findall(
            r"###\s+(?:场景\s*\d*[:：]?\s*)?(.+?)(?=\n###|\n##|\Z)",
            content, re.DOTALL
        )
        for block in scenario_blocks:
            title = block.split("\n")[0].strip()
            scripts_in_scenario = re.findall(r"(\w+\.py)", block)
            if scripts_in_scenario:
                scenario_chains[title] = scripts_in_scenario

    if not chain_count:
        print("\n(无 session 级调用链数据)")
        return

    print(f"\n实际调用链 (共 {len(by_session)} 个 session):")
    for chain, cnt in sorted(chain_count.items(), key=lambda x: -x[1])[:15]:
        print(f"  {chain}  ({cnt} 次)")

    if scenario_chains:
        print(f"\n与 SKILL.md scenarios 对比 ({len(scenario_chains)} 个场景):")
        for title, scripts in scenario_chains.items():
            # 检查是否有 session 包含了这些脚本的子序列
            matched = 0
            for sid, group in by_session.items():
                session_scripts = [r.get("script", "?") for r in group]
                if _is_subsequence(scripts, session_scripts):
                    matched += 1
            status = f"✓ {matched} 次" if matched else "✗ 未出现"
            print(f"  {title}: {status}")


def _is_subsequence(pattern, sequence):
    """检查 pattern 是否是 sequence 的子序列"""
    it = iter(sequence)
    return all(item in it for item in pattern)


# ─── Batch 导出（客户端 → 服务端上报） ────────────────────────

def export_batch(records, skill_name="dataworks", skill_version="unknown", env="public"):
    """将本地 JSONL 记录打包为符合 BATCH_SCHEMA 的上报批次。

    返回 batch dict，可直接 json.dumps 后 POST 到服务端。
    """
    from telemetry_schema import SCHEMA_VERSION, validate_batch

    batch = {
        "schema_version": SCHEMA_VERSION,
        "skill_name": skill_name,
        "skill_version": skill_version,
        "env": env,
        "uploaded_at": datetime.now().isoformat(timespec="seconds"),
        "events": records,
    }

    ok, errors = validate_batch(batch)
    if not ok:
        import sys
        print(f"batch 校验失败（{len(errors)} 个问题），仍然导出但标记 _validation_errors:",
              file=sys.stderr)
        for e in errors[:10]:
            print(f"  ✗ {e}", file=sys.stderr)
        batch["_validation_errors"] = errors[:20]

    return batch


# ─── CLI ──────────────────���───────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="遥测分析工具")
    parser.add_argument("--chains", action="store_true", help="检测频繁调用链")
    parser.add_argument("--failures", action="store_true", help="高失败率脚本")
    parser.add_argument("--session", nargs="?", const="__list__",
                        help="会话回放（无参数列出所有 session，指定 ID 回放单个）")
    parser.add_argument("--routing", action="store_true",
                        help="routing 命中率分析（哪些 intent 高频/从未命中）")
    parser.add_argument("--scenarios", action="store_true",
                        help="调用链与 scenarios 对比（发现 gap）")
    parser.add_argument("--skill-md", metavar="PATH",
                        help="SKILL.md 路径（--routing/--scenarios 用）")
    parser.add_argument("--export", metavar="FILE",
                        help="导出 batch JSON 文件（符合 telemetry_schema 契约）")
    parser.add_argument("--env", default="public", help="环境标识（导出用）")
    parser.add_argument("--since", help="过滤起始日期 (YYYY-MM-DD)")
    args = parser.parse_args()

    since = args.since
    records = _load_records(since=since)

    if not records:
        filepath = _TELEMETRY_FILE
        print(f"无遥测数据 ({filepath})")
        return

    date_range = ""
    if records:
        first = records[0].get("ts", "?")[:10]
        last = records[-1].get("ts", "?")[:10]
        date_range = f" ({first} ~ {last})"

    if args.export:
        batch = export_batch(records, env=args.env)
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
        print(f"已导出 {len(records)} ���记录 → {args.export} (schema v{batch['schema_version']})")
        return

    print(f"遥测数据: {len(records)} 条记录{date_range}")

    if args.session is not None:
        sid = None if args.session == "__list__" else args.session
        report_session(records, session_id=sid)
    elif args.routing:
        report_routing_coverage(records, skill_md_path=args.skill_md)
    elif args.scenarios:
        report_scenario_gaps(records, skill_md_path=args.skill_md)
    elif args.chains:
        report_chains(records)
    elif args.failures:
        report_failures(records)
    else:
        report_summary(records)
        # 默认也输出 top chains
        report_chains(records)


if __name__ == "__main__":
    main()
