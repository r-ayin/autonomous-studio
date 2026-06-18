#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运维概览 —— 一站式输出工作空间运行全貌

聚合周期实例、数据集成、手动任务三个维度的核心指标。

用法:
    python ops_overview.py --project-name autotest
    python ops_overview.py --project-id 14255 --date yesterday
    python ops_overview.py --project-id 14255 --mine
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

from bff_client import BFFClient, save_tool_result, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail
from workspace_memory import get_baseline, update_baseline, save_next_check


# ─── 常量 ──────────────────────────────────────────────────────

_TAG = "[ops]"
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
    if date_str == "yesterday" or not date_str:
        return today - timedelta(days=1)
    elif date_str == "today":
        return today
    else:
        return datetime.strptime(date_str, "%Y-%m-%d").date()


def _fmt(n):
    if n is None:
        return "-"
    return str(int(n)) if isinstance(n, (int, float)) else str(n)


# ─── 1. 周期实例概况 ─────────────────────────────────────────

def _section_cycle_instances(client, project_id, biz_date, is_mine):
    """周期实例运行概况，返回 {total, success, fail, running, waiting, success_rate}"""
    data = _safe_call(client, "getTaskRunInfo",
                      projectId=project_id, env="prod", tenantId=1,
                      beginBizDate=f"{biz_date} 00:00:00",
                      endBizDate=f"{biz_date} 23:59:59",
                      isMine=str(is_mine).lower())
    metrics = {}
    if not data or not isinstance(data, dict):
        return metrics

    success = data.get("successCount", data.get("success"))
    fail = data.get("failCount", data.get("fail"))
    running = data.get("runningCount", data.get("running"))
    waiting = data.get("waitCount", data.get("waiting"))
    total = data.get("totalCount", data.get("total"))
    print(f"  总计: {_fmt(total)}  成功: {_fmt(success)}  失败: {_fmt(fail)}  运行中: {_fmt(running)}  等待: {_fmt(waiting)}")

    metrics = {"total": total, "success": success, "fail": fail,
               "running": running, "waiting": waiting}

    if total and isinstance(total, (int, float)) and total > 0:
        s = (success or 0) if isinstance(success, (int, float)) else 0
        rate = s / total
        print(f"  完成率: {rate * 100:.1f}%")
        metrics["success_rate"] = rate

    return metrics


def _section_error_rank(client, project_id):
    """连续失败排行，返回列表 [{name, count, owner}, ...]"""
    data = _safe_call(client, "getTaskSeriesErrorRank",
                      projectId=project_id, env="prod", tenantId=1)
    if not data or not isinstance(data, list) or not data:
        print(f"  (无连续失败任务)")
        return []
    items = []
    for i, item in enumerate(data[:5], 1):
        name = item.get("nodeName", item.get("name", ""))[:30]
        count = item.get("errorCount", item.get("count", ""))
        owner = item.get("ownerName", item.get("owner", ""))
        print(f"  {i}. {name:<30} 连续 {count} 天  {owner}")
        items.append({"name": name, "count": int(count) if count else 0, "owner": owner})
    return items


def _section_slow_rank(client, project_id):
    """耗时排行，返回 True 如果有数据"""
    data = _safe_call(client, "getTaskRunConsumeTimeRank",
                      projectId=project_id, env="prod", tenantId=1)
    if not data or not isinstance(data, list) or not data:
        print(f"  (无数据)")
        return False
    for i, item in enumerate(data[:5], 1):
        name = item.get("nodeName", item.get("name", ""))[:30]
        cost = item.get("consumeTime", item.get("costTime", item.get("duration", 0)))
        if isinstance(cost, (int, float)):
            if cost > 100000:
                cost_str = f"{cost / 1000 / 60:.1f} 分钟"
            elif cost > 1000:
                cost_str = f"{cost / 60:.1f} 分钟"
            else:
                cost_str = f"{cost} 秒"
        else:
            cost_str = str(cost)
        print(f"  {i}. {name:<30} {cost_str}")
    return True


# ─── 2. 数据集成概况 ─────────────────────────────────────────

def _section_di_status(client, project_id, target_date):
    """DI 离线实例状态"""
    start = int(datetime(target_date.year, target_date.month, target_date.day).timestamp() * 1000)
    end = start + 86400 * 1000 - 1
    data = _safe_call(client, "di_getInstanceStatusSummary",
                      tenantId=1, projectId=project_id,
                      startTime=start, endTime=end, updatedTime="",
                      **_DI_COMMON)
    if not data:
        return
    if isinstance(data, dict):
        parts = []
        for key, val in data.items():
            if isinstance(val, (int, float)) and val > 0:
                parts.append(f"{key}: {_fmt(val)}")
        if parts:
            print(f"  {', '.join(parts)}")


def _section_di_datasource(client, project_id, target_date, ds_type):
    """DI 按数据源统计"""
    start = int(datetime(target_date.year, target_date.month, target_date.day).timestamp() * 1000)
    end = start + 86400 * 1000 - 1
    data = _safe_call(client, "di_getDataSummaryByDatasource",
                      tenantId=1, projectId=project_id,
                      startTime=start, endTime=end, updatedTime="",
                      type=ds_type, **_DI_COMMON)
    if not data:
        return
    items = data if isinstance(data, list) else data.get("list", data.get("data", []))
    if not isinstance(items, list) or not items:
        return
    label = "读取" if ds_type == "reader" else "写入"
    print(f"  {'数据源':<15} {'方向':<5} {'数据量':<15} {'任务数':<8}")
    print(f"  {'─' * 15} {'─' * 5} {'─' * 15} {'─' * 8}")
    for item in items[:10]:
        name = item.get("name", "")
        bytes_str = item.get("totalBytes", "")
        detail = item.get("detail", [])
        task_count = len(detail) if isinstance(detail, list) else ""
        print(f"  {name:<15} {label:<5} {bytes_str or '-':<15} {_fmt(task_count) if task_count else '-'}")


def _section_di_realtime(client, project_id):
    """DI 实时任务概况"""
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
        if parts:
            print(f"  {', '.join(parts)}")
        else:
            print(f"  (无实时任务)")


# ─── 3. 手动任务概况 ─────────────────────────────────────────

def _section_manual_biz(client, project_id, target_date):
    """手动任务状态分布"""
    date_str = target_date.strftime("%Y-%m-%d")
    data = _safe_call(client, "getManualBizStatusDist",
                      projectId=project_id, env="prod", tenantId=1,
                      startCreateTime=f"{date_str} 00:00:00",
                      endCreateTime=f"{date_str} 23:59:59",
                      owner="false")
    if not data:
        print(f"  (无数据)")
        return
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, (int, float)) and val > 0:
                print(f"  {key}: {_fmt(val)}")
    elif isinstance(data, list):
        for item in data:
            name = item.get("statusName", item.get("name", item.get("status", "")))
            count = item.get("count", item.get("num", ""))
            if count:
                print(f"  {name}: {_fmt(count)}")


# ─── 状态判断 ────────────────────────────────────────────────

def _print_assessment(cycle_metrics, error_rank, project_id, target_date,
                      baseline=None, has_slow_rank=True):
    """基于收集的指标输出状态判断 + 关键发现 + 建议动作"""
    findings = []
    actions = []

    # ── 判断维度 1：完成率 ──
    rate = cycle_metrics.get("success_rate") if cycle_metrics else None
    fail_count = cycle_metrics.get("fail") if cycle_metrics else None
    if isinstance(fail_count, (int, float)):
        fail_count = int(fail_count)

    # ── 判断维度 2：连续失败 ──
    severe_errors = [e for e in error_rank if e["count"] >= 3]
    max_error_days = max((e["count"] for e in error_rank), default=0)

    # ── 综合严重度 ──
    if (rate is not None and rate < 0.85) or max_error_days >= 5:
        severity_emoji = "🔴 严重"
    elif (rate is not None and rate < 0.95) or max_error_days >= 3:
        severity_emoji = "🟡 注意"
    else:
        severity_emoji = "🟢 正常"

    # ── 汇总结论 ──
    parts = []
    if rate is not None:
        parts.append(f"完成率 {rate * 100:.1f}%")
    if fail_count:
        parts.append(f"{fail_count} 个失败")
    if severe_errors:
        parts.append(f"{len(severe_errors)} 个任务连续失败≥3天")
    summary = "，".join(parts) if parts else "无异常"

    print(f"\n{'=' * 60}")
    print(f"【状态判断】{severity_emoji}：{summary}")

    # ── 关键发现 ──
    if rate is not None and rate < 0.95:
        findings.append(f"完成率 {rate * 100:.1f}%，低于 95% 基线")
    # ── 与历史基线对比 ──
    if baseline and rate is not None:
        hist_rate = baseline.get("avg_success_rate")
        if hist_rate is not None and isinstance(hist_rate, (int, float)):
            delta = rate - hist_rate
            if delta < -0.05:
                findings.append(f"完成率较历史基线（{hist_rate * 100:.1f}%）下降 {abs(delta) * 100:.1f} 个百分点")
            elif delta > 0.05:
                findings.append(f"完成率较历史基线（{hist_rate * 100:.1f}%）提升 {delta * 100:.1f} 个百分点")
    if baseline and fail_count is not None:
        hist_fail = baseline.get("typical_failure_count")
        if hist_fail is not None and isinstance(hist_fail, (int, float)) and hist_fail > 0:
            if fail_count > hist_fail * 1.5:
                findings.append(f"失败数 {fail_count} 超出历史均值（{int(hist_fail)}）的 1.5 倍")
    if severe_errors:
        top = severe_errors[0]
        findings.append(f"最严重：{top['name']} 连续失败 {top['count']} 天（{top['owner']}）")
    if fail_count and fail_count > 0 and not severe_errors:
        findings.append(f"有 {fail_count} 个失败实例，但无连续失败任务")

    if findings:
        print("【关键发现】")
        for f in findings:
            print(f"  - {f}")

    # ── 建议动作 ──
    if fail_count and fail_count > 0:
        actions.append(("查看失败实例，定位原因并重跑",
                        f"query_instances.py --project-id {project_id} --status failed --date {target_date}"))
    if severe_errors:
        top = severe_errors[0]
        actions.append((f"优先处理连续失败最久的任务: {top['name']}",
                        f"query_instances.py --project-id {project_id} --status failed --search {top['name']}"))
    if not has_slow_rank:
        actions.append(("查看成功实例耗时排序（耗时排行 API 无数据时的替代方案）",
                        f"query_instances.py --project-id {project_id} --status success --date {target_date}"))
    if not actions:
        actions.append(("查看数据集成详情",
                        f"di_overview.py --project-id {project_id} --date {target_date}"))

    print("【建议动作】")
    for i, (desc, cmd) in enumerate(actions, 1):
        print(f"  {i}. {desc}")
        print(f"     → {cmd}")


# ─── 主流程 ──────────────────────────────────────────────────

def overview(args):
    client = BFFClient(quiet=True)
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
    target_date = _resolve_date(args.date)
    is_mine = args.mine
    scope = "我的" if is_mine else "全部"
    telemetry_start("ops_overview.py", module="task-ops",
                    project_id=project_id, date=str(target_date))

    print(f"{_TAG} 工作空间: {project_id} | 业务日期: {target_date} | 范围: {scope}")
    print(f"{'=' * 60}")

    # 1. 周期实例
    print(f"\n📊 周期实例运行概况")
    cycle_metrics = _section_cycle_instances(client, project_id, target_date, is_mine)

    print(f"\n🔴 连续失败排行 TOP 5")
    error_rank = _section_error_rank(client, project_id)

    print(f"\n🐢 耗时排行 TOP 5")
    has_slow_rank = _section_slow_rank(client, project_id)

    # 2. 数据集成
    print(f"\n📦 数据集成（离线）")
    _section_di_status(client, project_id, target_date)

    print(f"\n  读取端:")
    _section_di_datasource(client, project_id, target_date, "reader")

    print(f"\n  写入端:")
    _section_di_datasource(client, project_id, target_date, "writer")

    print(f"\n🔄 数据集成（实时）")
    _section_di_realtime(client, project_id)

    # 3. 手动任务
    print(f"\n🔧 手动任务")
    _section_manual_biz(client, project_id, target_date)

    # 加载历史基线（跨会话记忆）
    baseline = get_baseline(project_id)

    # 状态判断 + 建议动作
    _print_assessment(cycle_metrics, error_rank, project_id, target_date,
                      baseline=baseline, has_slow_rank=has_slow_rank)

    # 更新基线（滑动平均）
    rate = cycle_metrics.get("success_rate") if cycle_metrics else None
    fail_count = cycle_metrics.get("fail") if cycle_metrics else None
    if rate is not None and fail_count is not None:
        try:
            update_baseline(project_id, rate, int(fail_count))
        except Exception:
            pass  # 记忆写入失败不影响主流程

    severity = "ok"
    fail_count_val = cycle_metrics.get("fail") if cycle_metrics else None
    if cycle_metrics:
        rate = cycle_metrics.get("success_rate")
        if rate is not None and rate < 0.85:
            severity = "critical"
        elif rate is not None and rate < 0.95:
            severity = "warning"

    # 严重/警告时保存待跟进事项，供下次会话开始检查
    if severity in ("critical", "warning") and fail_count_val is not None:
        try:
            save_next_check(
                project_id,
                f"上次巡检发现 {int(fail_count_val)} 个失败任务（{severity}），需确认是否恢复",
                f"query_instances.py --project-id {project_id} --status failed")
        except Exception:
            pass

    telemetry_end(result={"severity": severity, "error_rank_count": len(error_rank)})

    save_tool_result("ops_overview", {
        "status": "ok",
        "project_id": project_id,
        "date": str(target_date),
        "cycle_metrics": cycle_metrics,
        "error_rank_count": len(error_rank),
    })


# ─── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="运维概览")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--project-name", help="工作空间名称")
    parser.add_argument("--project", help="canonical：工作空间（纯数字=id，否则=name）")
    parser.add_argument("--date", default=None,
                        help="业务日期: yesterday(默认)/today/YYYY-MM-DD")
    parser.add_argument("--business-date", dest="business_date",
                        help="canonical：等价于 --date")
    parser.add_argument("--mine", action="store_true", help="只看我的任务")
    parser.add_argument("--owner", help="canonical：负责人（'me'=当前用户，等价 --mine）")
    args = parser.parse_args()

    # ── canonical 参数归一 ──
    # 统一参数词表：--project --owner --business-date（与 query_instances 对齐）
    if args.project and not args.project_id and not args.project_name:
        if args.project.isdigit():
            args.project_id = int(args.project)
        else:
            args.project_name = args.project
    if args.business_date and args.date is None:
        args.date = args.business_date
    if args.date is None:
        args.date = "yesterday"
    if args.owner and not args.mine:
        if args.owner.lower() == "me":
            args.mine = True
        # 非 'me' 的 owner 值暂忽略（ops_overview 聚合视图不支持任意 owner 过滤）

    if not args.project_id and not args.project_name:
        telemetry_start("ops_overview.py", module="task-ops")
        from bff_client import list_workspaces_for_selection
        list_workspaces_for_selection("ops_overview.py")
        telemetry_end(exit_code=0, result={"action": "list_workspaces"})
        return

    overview(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("ops_overview.py", "task-ops", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("ops_overview.py", "task-ops", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
