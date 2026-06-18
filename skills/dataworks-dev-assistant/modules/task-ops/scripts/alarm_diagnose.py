#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DataWorks 告警自动诊断

输入告警文本，自动解析告警类型、查实例、查操作记录（必经步骤）、查日志、输出诊断报告。

支持的告警类型：
- 自定义规则告警   含「业务日期」「任务NNN(...)」「创建人」
- 基线告警         含「DataWorks基线告警」或「余量」
- 基线事件告警     含「出错」/「变慢」+「事件余量」+「影响了N级基线」

用法:
    # 从命令行传入
    python alarm_diagnose.py --text "告警全文" --project-id 14255

    # 从文件读入
    python alarm_diagnose.py --file /tmp/alarm.txt --project-id 14255

    # 直接给 alarmId（自定义规则告警的 view_instances URL 中提取）
    python alarm_diagnose.py --alarm-id 12345 --project-id 14255

    # 直接给 nodeId + bizdate（任意场景）
    python alarm_diagnose.py --node-id 267860324 --bizdate 2026-04-12 --project-id 14255
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

from bff_client import BFFClient, save_tool_result, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail


_TAG = "[alarm-diagnose]"
_STATUS_NAMES = {
    "1": "未运行", "2": "等待时间", "3": "等待资源", "4": "运行中",
    "5": "失败", "6": "成功", "7": "校验中",
}


# ─── 告警解析 ───────────────────────────────────────────────

def parse_alarm(text):
    """解析告警文本，返回 dict: {type, node_id, task_id, bizdate, baseline_name,
    alarm_id, ingroup_id, raw}"""
    t = text or ""
    info = {"raw": t, "type": None, "node_id": None, "task_id": None,
            "bizdate": None, "baseline_name": None, "alarm_id": None,
            "ingroup_id": "1"}

    # 告警类型识别（顺序：先具体后泛化）
    if "业务日期" in t and "创建人" in t:
        info["type"] = "custom_rule"
    elif "事件余量" in t and "影响了" in t and "级基线" in t:
        info["type"] = "baseline_event_slow" if "变慢" in t else "baseline_event_error"
    elif "DataWorks基线告警" in t or re.search(r"余量[:：]\s*-\d+", t):
        info["type"] = "baseline"

    # alarmId（view_instances URL）
    m = re.search(r"alarmId[=:]\s*(\d+)", t, re.IGNORECASE)
    if m:
        info["alarm_id"] = m.group(1)

    # 业务日期 YYYYMMDD 或 YYYY-MM-DD
    m = re.search(r"业务日期[:：]?\s*(\d{4}-?\d{2}-?\d{2})", t)
    if m:
        d = m.group(1).replace("-", "")
        if len(d) == 8:
            info["bizdate"] = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

    # nodeId 提取（自定义规则：「任务NNN(...)」可无空格）
    if info["type"] == "custom_rule":
        m = re.search(r"任务\s*(\d{6,})\s*\(", t)
        if m:
            info["node_id"] = m.group(1)

    # 基线事件告警 nodeId 提取（格式 YYYYMMDD-NNN(name)）
    if info["type"] in ("baseline_event_error", "baseline_event_slow"):
        m = re.search(r"\d{8}-(\d{6,})\s*\(", t)
        if m:
            info["node_id"] = m.group(1)

    # 基线名称（排除 type 关键字噪音）
    m = re.search(r"基线[:：]\s*([^\s,，;；()（）]+)", t)
    if m and info["type"] in ("baseline", "baseline_event_error", "baseline_event_slow"):
        cand = m.group(1).strip()
        if cand not in ("告警", "事件", "出错", "变慢"):
            info["baseline_name"] = cand

    # 周期（小时基线 ingroupId）
    m = re.search(r"周期[:：]?\s*(\d+)", t)
    if m:
        info["ingroup_id"] = m.group(1)

    return info


# ─── BFF 调用辅助 ─────────────────────────────────────────────

def _call(client, api_name, **kwargs):
    api_meta = client.api_index.get(api_name)
    if not api_meta:
        raise ValueError(f"未找到 API: {api_name}")
    result = client._do_request(api_name, api_meta, **kwargs)
    code = result.get("code")
    if code not in (None, 0, "0", 200, "200"):
        raise RuntimeError(f"{api_name} 失败: code={code}, message={result.get('message','')}")
    return client._parse_return_structure(result, api_meta.get("return_structure", ""))


def fetch_instances(client, info, project_id):
    """根据告警字段拉实例列表"""
    if info.get("alarm_id"):
        # alarmId 路径：直接拉关联实例
        items = _call(client, "getInstanceList",
                      projectId=project_id, env="prod",
                      alarmId=info["alarm_id"],
                      pageNum=1, pageSize=100)
    elif info.get("node_id") and info.get("bizdate"):
        # nodeId+bizdate 路径：用 searchText 查
        bizstr = f"{info['bizdate']} 00:00:00"
        items = _call(client, "getInstanceList",
                      projectId=project_id, env="prod",
                      searchText=info["node_id"], bizdate=bizstr,
                      pageNum=1, pageSize=100)
    else:
        return []
    return items if isinstance(items, list) else ([items] if items else [])


def fetch_op_logs(client, info):
    """⚠️ 告警诊断必经：查节点操作记录"""
    target_id = info.get("node_id") or info.get("task_id")
    if not target_id:
        return []
    kwargs = {"projectId": "0", "projectEnv": "prod",
              "pageSize": "50", "pageNumber": "1"}
    if info.get("node_id"):
        kwargs["nodeId"] = info["node_id"]
    else:
        kwargs["taskId"] = info["task_id"]
    try:
        result = _call(client, "listOpLogs", **kwargs)
    except Exception as e:
        print(f"{_TAG} ⚠️ 操作记录查询失败: {e}")
        return []
    return result if isinstance(result, list) else ([result] if result else [])


def fetch_log(client, task_id, project_id):
    try:
        return _call(client, "getInstanceRunLog",
                     taskId=task_id, historyId="0",
                     projectId=project_id, env="prod")
    except Exception as e:
        return f"[日志拉取失败: {e}]"


# ─── 失败模式分析 ───────────────────────────────────────────

def classify_failure_pattern(items):
    """先成功后失败 / 全部失败 / 间歇性失败"""
    if not items:
        return "no_data", []
    by_time = sorted(items, key=lambda x: x.get("bizdate", 0) or x.get("createTime", 0))
    statuses = [str(i.get("status")) for i in by_time]
    failed_idx = [i for i, s in enumerate(statuses) if s == "5"]
    success_idx = [i for i, s in enumerate(statuses) if s == "6"]

    if not failed_idx:
        return "no_failure", by_time
    if all(s == "5" for s in statuses):
        return "all_fail", by_time
    if success_idx and failed_idx and max(success_idx) < min(failed_idx):
        return "first_success_then_fail", by_time
    return "intermittent", by_time


def analyze_op_timeline(op_logs, items):
    """对比操作时间和实例运行时间"""
    code_changes = []
    for log in op_logs:
        content = log.get("content", "") or ""
        if "Update:" in content or "更新" in content or "代码" in content:
            op_time = log.get("opTime") or ""
            user = log.get("userName") or log.get("userId") or "未知"
            code_changes.append({"op_time": op_time, "user": user, "content": content})
    return code_changes


# ─── 报告输出 ───────────────────────────────────────────────

def render_report(info, project_id, items, op_logs, code_changes, pattern, log_excerpt):
    out = []
    out.append("# DataWorks 告警诊断报告\n")
    out.append(f"**告警类型**: {info.get('type') or '未识别'}")
    if info.get("baseline_name"): out.append(f"**基线**: {info['baseline_name']}")
    if info.get("node_id"):       out.append(f"**节点 ID**: {info['node_id']}")
    if info.get("task_id"):       out.append(f"**实例 ID**: {info['task_id']}")
    if info.get("bizdate"):       out.append(f"**业务日期**: {info['bizdate']}")
    if info.get("alarm_id"):      out.append(f"**告警 ID**: {info['alarm_id']}")
    out.append(f"**工作空间 ID**: {project_id}")
    out.append("")

    # 实例分布
    out.append("## 1. 实例状态分布")
    if not items:
        out.append("⚠️ 未查到实例。可能 projectId 不对，或 alarmId/nodeId 失效。\n")
    else:
        out.append(f"共 {len(items)} 个实例：")
        out.append("")
        out.append("| 节点名 | nodeId | 实例 ID (taskId) | 状态 | 责任人 | bizdate |")
        out.append("|-------|-------|------------------|------|-------|---------|")
        for i in items[:30]:
            status = _STATUS_NAMES.get(str(i.get("status")), str(i.get("status")))
            tid = i.get("taskId", "")
            nid = i.get("nodeId", "")
            nname = (i.get("nodeName") or "")[:30]
            owner = i.get("ownerName") or i.get("owner") or ""
            bd = i.get("bizdate") or ""
            if isinstance(bd, (int, float)):
                bd = datetime.fromtimestamp(bd / 1000).strftime("%Y-%m-%d")
            out.append(f"| {nname} | {nid} | {tid} | {status} | {owner} | {bd} |")
        out.append("")
        out.append(f"**失败模式**: `{pattern}`")
        out.append("")

    # 操作记录（必有此段，即使空）
    out.append("## 2. 操作记录分析（必经步骤）")
    if not op_logs:
        out.append("✅ 已检查操作记录，**未发现代码变更**。\n")
    else:
        if code_changes:
            out.append(f"⚠️ 发现 **{len(code_changes)} 条代码变更**：")
            out.append("")
            out.append("| 操作时间 | 操作人 | 操作内容 |")
            out.append("|---------|-------|---------|")
            for c in code_changes[:10]:
                out.append(f"| {c['op_time']} | {c['user']} | {c['content']} |")
            out.append("")
            if pattern == "first_success_then_fail":
                out.append("👉 **诊断**：失败模式是「先成功后失败」，且检测到代码变更——**高度怀疑是变更引入问题**。")
                out.append("对比变更时间与各实例运行时间：变更后跑的实例使用新代码。")
                out.append("")
        else:
            out.append(f"已检查 {len(op_logs)} 条操作记录，无代码变更（仅刷新/重跑等）。")
            out.append("")

    # 失败实例日志（取第一条失败）
    failed = [i for i in items if str(i.get("status")) == "5"]
    if failed and log_excerpt:
        out.append("## 3. 失败实例日志摘录")
        first_failed = failed[0]
        out.append(f"实例 `{first_failed.get('taskId')}` ({first_failed.get('nodeName','')})")
        out.append("")
        out.append("```")
        # 取末尾 60 行
        lines = log_excerpt.splitlines() if isinstance(log_excerpt, str) else []
        out.extend(lines[-60:])
        out.append("```")
        out.append("")

    # 处置建议
    out.append("## 4. 处置建议")
    suggestions = []
    if pattern == "first_success_then_fail" and code_changes:
        suggestions.append("- 联系变更人核实修改是否正确；如错误改回前回滚版本")
        suggestions.append(f"- 修复后重跑失败实例：`rerun_failed_instances.py --project-id {project_id}`")
    elif pattern == "all_fail":
        suggestions.append("- 全部失败可能是上游/资源/权限问题，先看日志根因再决定")
        suggestions.append("- 若是权限错误（Authorization exception / Access denied）→ 申请 Guard 权限")
    elif pattern == "intermittent":
        suggestions.append("- 间歇性失败排查：上游数据质量、资源竞争、超时配置")
    if failed:
        first_id = failed[0].get("taskId")
        suggestions.append(f"- 详细日志: `log_analyzer.py --task-instance-id {first_id}`")
        suggestions.append(f"- 任务详情: `task_detail.py --project-id {project_id} --node-id {failed[0].get('nodeId')}`")
    if not suggestions:
        suggestions.append("- 无失败实例或无明确诊断结论，建议人工核查")
    out.extend(suggestions)
    out.append("")
    return "\n".join(out)


# ─── 主流程 ───────────────────────────────────────────────

def diagnose(args):
    text = ""
    if args.text:
        text = args.text
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()

    info = parse_alarm(text) if text else {"type": None, "node_id": args.node_id,
                                            "task_id": args.task_id,
                                            "bizdate": args.bizdate,
                                            "alarm_id": args.alarm_id,
                                            "raw": ""}
    # CLI 参数覆盖解析结果（信任用户）
    if args.node_id: info["node_id"] = args.node_id
    if args.task_id: info["task_id"] = args.task_id
    if args.bizdate: info["bizdate"] = args.bizdate
    if args.alarm_id: info["alarm_id"] = args.alarm_id

    if not (info.get("alarm_id") or info.get("node_id") or info.get("task_id")):
        print(f"{_TAG} ❌ 无法从告警中提取 alarmId / nodeId / taskId。请用 --node-id / --task-id / --alarm-id 显式指定")
        sys.exit(1)

    client = BFFClient(quiet=True)
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)

    print(f"{_TAG} 解析结果: type={info.get('type')} nodeId={info.get('node_id')} bizdate={info.get('bizdate')} alarmId={info.get('alarm_id')}")
    print(f"{_TAG} 拉取实例列表...")
    items = fetch_instances(client, info, project_id)

    print(f"{_TAG} 查询操作记录（必经步骤）...")
    op_logs = fetch_op_logs(client, info)
    code_changes = analyze_op_timeline(op_logs, items)

    pattern, ordered = classify_failure_pattern(items)
    print(f"{_TAG} 失败模式: {pattern}")

    log_excerpt = ""
    failed = [i for i in items if str(i.get("status")) == "5"]
    if failed:
        first_failed_id = failed[0].get("taskId")
        if first_failed_id:
            print(f"{_TAG} 拉取失败实例 {first_failed_id} 日志...")
            log_excerpt = fetch_log(client, first_failed_id, project_id)

    report = render_report(info, project_id, items, op_logs, code_changes, pattern, log_excerpt)
    print()
    print(report)

    save_tool_result("alarm_diagnose", {
        "status": "ok",
        "alarm_type": info.get("type"),
        "project_id": project_id,
        "node_id": info.get("node_id"),
        "instance_count": len(items),
        "failed_count": len(failed),
        "pattern": pattern,
        "code_changes": len(code_changes),
    })


def main():
    parser = argparse.ArgumentParser(
        description="DataWorks 告警自动诊断（解析→实例→操作记录→日志→报告）",
        usage="%(prog)s --project-id <id> [--text <告警文本> | --file <文件> | --node-id <id> --bizdate <YYYY-MM-DD>]",
    )
    parser.add_argument("--text", help="告警文本（直接传入）")
    parser.add_argument("--file", help="告警文本文件路径")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--project-name", help="工作空间名称")
    parser.add_argument("--node-id", help="节点 ID（覆盖解析结果）")
    parser.add_argument("--task-id", help="实例 ID（覆盖解析结果）")
    parser.add_argument("--bizdate", help="业务日期 YYYY-MM-DD")
    parser.add_argument("--alarm-id", help="告警 ID（来自 view_instances URL）")
    args = parser.parse_args()

    telemetry_start("alarm_diagnose.py", module="task-ops",
                    project_id=args.project_id)
    try:
        diagnose(args)
        telemetry_end(result={"action": "diagnose"})
    except Exception:
        raise


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("alarm_diagnose.py", "task-ops",
                       e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("alarm_diagnose.py", "task-ops", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
