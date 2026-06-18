#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据集成概览 —— 离线 + 实时 DI 运行情况

用法:
    python di_overview.py --project-name autotest
    python di_overview.py --project-id 14255 --date yesterday
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

from bff_client import BFFClient, save_tool_result, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail


# ─── 常量 ──────────────────────────────────────────────────────

_TAG = "[di]"
_DI_COMMON = {"env": "prod", "projectCode": "di"}


# ─── 内部 API 调用 ────────────────────────────────────────────

def _api_call(client, api_name, **kwargs):
    api_meta = client.api_index.get(api_name)
    if not api_meta:
        raise ValueError(f"未找到 API: {api_name}")
    result = client._do_request(api_name, api_meta, **kwargs)
    code = result.get("code")
    if code not in (None, 0, "0", 200, "200"):
        msg = result.get("message", "")
        raise RuntimeError(f"{api_name} 失败: code={code}, message={msg}")
    return_structure = api_meta.get("return_structure", "")
    return client._parse_return_structure(result, return_structure)


def _safe_call(client, api_name, **kwargs):
    try:
        return _api_call(client, api_name, **kwargs)
    except Exception:
        return None


# ─── 参数解析 ────────────────────────────────────────────────



def _resolve_date(date_str):
    today = datetime.now().date()
    if date_str == "today" or not date_str:
        return today
    elif date_str == "yesterday":
        return today - timedelta(days=1)
    else:
        return datetime.strptime(date_str, "%Y-%m-%d").date()


def _fmt(n):
    if n is None:
        return "-"
    return str(int(n)) if isinstance(n, (int, float)) else str(n)


def _time_range_ms(target_date):
    start = int(datetime(target_date.year, target_date.month, target_date.day).timestamp() * 1000)
    end = start + 86400 * 1000 - 1
    return start, end


# ─── 离线板块 ────────────────────────────────────────────────

def _section_offline_status(client, project_id, start, end):
    """离线实例状态，返回 {total, success, fail, running, ...}"""
    data = _safe_call(client, "di_getInstanceStatusSummary",
                      tenantId=1, projectId=project_id,
                      startTime=start, endTime=end, updatedTime="",
                      **_DI_COMMON)
    if not data or not isinstance(data, dict):
        print(f"  (无数据)")
        return {}
    parts = []
    for key, val in data.items():
        if isinstance(val, (int, float)):
            parts.append(f"{key}: {_fmt(val)}")
    print(f"  {', '.join(parts)}" if parts else "  (无数据)")
    return data


def _section_offline_data_summary(client, project_id, start, end):
    """离线数据量汇总，返回原始数据"""
    data = _safe_call(client, "di_getInstanceDataSummary",
                      tenantId=1, projectId=project_id,
                      startTime=start, endTime=end, updatedTime="",
                      **_DI_COMMON)
    if not data or not isinstance(data, dict):
        return {}
    for key, val in data.items():
        if isinstance(val, (int, float)):
            print(f"  {key}: {_fmt(val)}")
        elif isinstance(val, str) and val:
            print(f"  {key}: {val}")
    return data


def _section_by_datasource(client, project_id, start, end, ds_type):
    """按数据源类型统计"""
    data = _safe_call(client, "di_getDataSummaryByDatasource",
                      tenantId=1, projectId=project_id,
                      startTime=start, endTime=end, updatedTime="",
                      type=ds_type, **_DI_COMMON)
    if not data:
        print(f"  (无数据)")
        return
    items = data if isinstance(data, list) else data.get("list", data.get("data", []))
    if not isinstance(items, list) or not items:
        print(f"  (无数据)")
        return
    label = "读取" if ds_type == "reader" else "写入"
    print(f"  {'数据源':<15} {'方向':<5} {'数据量':<15} {'任务数':<8}")
    print(f"  {'─' * 15} {'─' * 5} {'─' * 15} {'─' * 8}")
    for item in items[:15]:
        name = item.get("name", "")
        bytes_str = item.get("totalBytes", "")
        detail = item.get("detail", [])
        task_count = len(detail) if isinstance(detail, list) else ""
        print(f"  {name:<15} {label:<5} {bytes_str or '-':<15} {_fmt(task_count) if task_count else '-'}")


def _section_offline_fail(client, project_id, start, end):
    """离线失败实例，返回失败实例列表"""
    data = _safe_call(client, "di_getLatestInstanceSummary",
                      tenantId=1, projectId=project_id,
                      startTime=start, endTime=end, updatedTime="",
                      state="fail", **_DI_COMMON)
    if not data:
        print(f"  (无失败实例)")
        return []
    items = data if isinstance(data, list) else data.get("list", data.get("data", []))
    if not isinstance(items, list) or not items:
        print(f"  (无失败实例)")
        return []
    for item in items[:10]:
        name = item.get("nodeName", item.get("name", ""))[:35]
        status = item.get("statusName", item.get("status", ""))
        print(f"  {name:<35} {status}")
    return items


# ─── 实时板块 ────────────────────────────────────────────────

def _section_realtime_metrics(client, project_id):
    """实时任务指标"""
    data = _safe_call(client, "di_getProjectMetrics",
                      tenantId=1, projectId=project_id,
                      updatedTime="", **_DI_COMMON)
    if not data:
        print(f"  (无实时任务)")
        return
    if isinstance(data, dict):
        parts = []
        for key, val in data.items():
            if isinstance(val, (int, float)):
                parts.append(f"{key}: {_fmt(val)}")
        print(f"  {', '.join(parts)}" if parts else "  (无实时任务)")


def _section_realtime_tasks(client, project_id):
    """运行中实时任务（按延迟排序），返回任务列表"""
    data = _safe_call(client, "di_listTransformCode",
                      tenantId=1, projectId=project_id,
                      orderBy="delay", state="RUN", desc="true",
                      pageNum=1, pageSize=10, updatedTime="",
                      **_DI_COMMON)
    if not data:
        print(f"  (无运行中的实时任务)")
        return []
    items = data if isinstance(data, list) else data.get("list", data.get("data", []))
    if not isinstance(items, list) or not items:
        print(f"  (无运行中的实时任务)")
        return []
    for item in items[:10]:
        name = item.get("name", item.get("nodeName", ""))[:30]
        delay = item.get("delay", item.get("delayTime", ""))
        status = item.get("state", item.get("status", ""))
        delay_str = f"延迟 {delay}s" if isinstance(delay, (int, float)) and delay > 0 else ""
        print(f"  {name:<30} {status:<8} {delay_str}")
    return items


def _section_realtime_alarms(client, project_id):
    """告警事件，返回告警列表"""
    data = _safe_call(client, "di_findAlarmEvent",
                      tenantId=1, projectId=project_id,
                      pageNum=1, pageSize=10, updatedTime="",
                      **_DI_COMMON)
    if not data:
        print(f"  (无告警)")
        return []
    items = data if isinstance(data, list) else data.get("list", data.get("data", []))
    if not isinstance(items, list) or not items:
        print(f"  (无告警)")
        return []
    for item in items[:10]:
        name = item.get("taskName", item.get("name", ""))[:30]
        msg = item.get("message", item.get("alarmMessage", item.get("content", "")))[:50]
        print(f"  {name:<30} {msg}")
    return items


# ─── 状态判断 ────────────────────────────────────────────────

def _print_assessment(offline_status, fail_items, rt_tasks, alarm_items, project_id, target_date):
    """基于收集的指标输出状态判断 + 关键发现 + 建议动作"""
    findings = []
    actions = []

    # ── 判断维度 1：离线实例失败率 ──
    total = 0
    fail_count = 0
    if offline_status and isinstance(offline_status, dict):
        for key, val in offline_status.items():
            if isinstance(val, (int, float)):
                total += int(val)
        fail_count = int(offline_status.get("fail", offline_status.get("failCount", 0)) or 0)
    fail_rate = fail_count / total if total > 0 else 0

    # ── 判断维度 2：实时任务延迟/告警 ──
    high_delay_tasks = []
    for t in (rt_tasks or []):
        delay = t.get("delay", t.get("delayTime", 0))
        if isinstance(delay, (int, float)) and delay > 300:
            high_delay_tasks.append(t)
    alarm_count = len(alarm_items) if alarm_items else 0

    # ── 综合严重度 ──
    if fail_rate > 0.2 or fail_count >= 10 or alarm_count >= 5:
        severity_emoji = "🔴 严重"
    elif fail_count > 0 or high_delay_tasks or alarm_count > 0:
        severity_emoji = "🟡 注意"
    else:
        severity_emoji = "🟢 正常"

    # ── 汇总 ──
    parts = []
    if total > 0:
        parts.append(f"离线 {total} 实例")
        if fail_count:
            parts.append(f"{fail_count} 个失败（{fail_rate * 100:.0f}%）")
    if high_delay_tasks:
        parts.append(f"{len(high_delay_tasks)} 个实时任务延迟>5min")
    if alarm_count:
        parts.append(f"{alarm_count} 条告警")
    summary = "，".join(parts) if parts else "无异常"

    print(f"\n{'=' * 60}")
    print(f"【状态判断】{severity_emoji}：{summary}")

    # ── 关键发现 ──
    if fail_count > 0:
        findings.append(f"离线同步失败 {fail_count} 个（失败率 {fail_rate * 100:.1f}%）")
    if fail_items:
        top = fail_items[0]
        name = top.get("nodeName", top.get("name", ""))
        if name:
            findings.append(f"首个失败任务: {name}")
    if high_delay_tasks:
        top = high_delay_tasks[0]
        name = top.get("name", top.get("nodeName", ""))
        delay = top.get("delay", top.get("delayTime", 0))
        findings.append(f"实时任务 {name} 延迟 {delay}s")
    if alarm_count:
        findings.append(f"有 {alarm_count} 条活跃告警")

    if findings:
        print("【关键发现】")
        for f in findings:
            print(f"  - {f}")

    # ── 建议动作 ──
    if fail_count > 0:
        actions.append(("查看失败的 DI 实例",
                        f"query_instances.py --project-id {project_id} --status failed --type DATAX --date {target_date}"))
    if alarm_count:
        actions.append(("查看运维全局概览（含告警详情）",
                        f"ops_overview.py --project-id {project_id} --date {target_date}"))
    if not actions:
        actions.append(("查看运维全局概览",
                        f"ops_overview.py --project-id {project_id} --date {target_date}"))

    print("【建议动作】")
    for i, (desc, cmd) in enumerate(actions, 1):
        print(f"  {i}. {desc}")
        print(f"     → {cmd}")


# ─── 主流程 ──────────────────────────────────────────────────

def overview(args):
    client = BFFClient(quiet=True)
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
    target_date = _resolve_date(args.date)
    start, end = _time_range_ms(target_date)
    telemetry_start("di_overview.py", module="task-ops",
                    project_id=project_id, date=str(target_date))

    print(f"{_TAG} 工作空间: {project_id} | 日期: {target_date}")
    print(f"{'=' * 60}")

    # ── 离线 ──
    print(f"\n📊 离线同步 - 实例状态")
    offline_status = _section_offline_status(client, project_id, start, end)

    print(f"\n📦 离线同步 - 数据量汇总")
    _section_offline_data_summary(client, project_id, start, end)

    print(f"\n📖 离线同步 - 按数据源统计（读取端）")
    _section_by_datasource(client, project_id, start, end, "reader")

    print(f"\n📝 离线同步 - 按数据源统计（写入端）")
    _section_by_datasource(client, project_id, start, end, "writer")

    print(f"\n🔴 离线同步 - 失败实例")
    fail_items = _section_offline_fail(client, project_id, start, end)

    # ── 实时 ──
    print(f"\n🔄 实时同步 - 项目指标")
    _section_realtime_metrics(client, project_id)

    print(f"\n⏱️  实时同步 - 运行中任务（按延迟排序）")
    rt_tasks = _section_realtime_tasks(client, project_id)

    print(f"\n🔔 实时同步 - 告警事件")
    alarm_items = _section_realtime_alarms(client, project_id)

    # 状态判断 + 建议动作
    _print_assessment(offline_status, fail_items, rt_tasks, alarm_items,
                      project_id, str(target_date))

    fail_count = len(fail_items) if fail_items else 0
    telemetry_end(result={"offline_fail_count": fail_count,
                          "realtime_alarm_count": len(alarm_items) if alarm_items else 0})

    save_tool_result("di_overview", {
        "status": "ok",
        "project_id": project_id,
        "date": str(target_date),
        "offline_fail_count": fail_count,
        "realtime_alarm_count": len(alarm_items) if alarm_items else 0,
    })


# ─── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="数据集成概览（离线+实时）")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--project-name", help="工作空间名称")
    parser.add_argument("--date", default="today",
                        help="日期: today(默认)/yesterday/YYYY-MM-DD")
    args = parser.parse_args()

    if not args.project_id and not args.project_name:
        telemetry_start("di_overview.py", module="task-ops")
        from bff_client import list_workspaces_for_selection
        list_workspaces_for_selection("di_overview.py")
        telemetry_end(exit_code=0, result={"action": "list_workspaces"})
        return

    overview(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("di_overview.py", "task-ops", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("di_overview.py", "task-ops", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
