#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日运维巡检 — 一键完成：概况 → 失败实例 → 建议动作

将 ops_overview + query_instances(failed) 合并为一次调用，
省去 agent 多轮交互。

用法:
    python daily_check.py --project-name autotest
    python daily_check.py --project-id 14255 --date yesterday --mine
"""

import argparse
import json
import sys


from bff_client import BFFClient, save_tool_result, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail
from workspace_memory import get_baseline, update_baseline, get_known_issues, record_known_issue

# 从同目录脚本复用函数
from ops_overview import (
    _resolve_date,
    _fmt,
    _section_cycle_instances,
    _section_error_rank,
    _section_slow_rank,
    _section_di_status,
    _section_di_datasource,
    _section_di_realtime,
    _section_manual_biz,
)
from query_instances import (
    _api_call as _qi_api_call,
    _calc_date_params,
    _print_table,
    _print_fail_groups,
    _STATUS_NAMES,
)


# ─── 常量 ──────────────────────────────────────────────────────

_TAG = "[daily-check]"


# ─── 合并评估 ──────────────────────────────────────────────────

def _combined_assessment(cycle_metrics, error_rank, failed_items, all_items,
                         project_id, target_date, baseline, has_slow_rank):
    """合并 ops_overview + query_instances 的评估，输出单个判断块"""
    findings = []
    actions = []

    # ── 维度 1: 完成率 ──
    rate = cycle_metrics.get("success_rate") if cycle_metrics else None
    fail_count = cycle_metrics.get("fail") if cycle_metrics else None
    if isinstance(fail_count, (int, float)):
        fail_count = int(fail_count)

    # ── 维度 2: 连续失败 ──
    severe_errors = [e for e in error_rank if e["count"] >= 3]
    max_error_days = max((e["count"] for e in error_rank), default=0)

    # ── 维度 3: 实例级失败 ──
    owner_fail = {}
    for i in failed_items:
        o = i.get("ownerName") or i.get("owner") or "未知"
        owner_fail[o] = owner_fail.get(o, 0) + 1

    # ── 综合严重度 ──
    if (rate is not None and rate < 0.85) or max_error_days >= 5 or len(failed_items) >= 10:
        severity = "🔴 严重"
    elif (rate is not None and rate < 0.95) or max_error_days >= 3 or len(failed_items) >= 3:
        severity = "🟡 注意"
    else:
        severity = "🟢 正常"

    # ── 汇总结论 ──
    parts = []
    if rate is not None:
        parts.append(f"完成率 {rate * 100:.1f}%")
    if fail_count:
        parts.append(f"{fail_count} 个失败")
    if severe_errors:
        parts.append(f"{len(severe_errors)} 个任务连续失败>=3天")
    summary = "，".join(parts) if parts else "无异常"

    print(f"\n{'=' * 60}")
    print(f"【状态判断】{severity}：{summary}")

    # ── 关键发现 ──
    if rate is not None and rate < 0.95:
        findings.append(f"完成率 {rate * 100:.1f}%，低于 95% 基线")
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
    if len(owner_fail) > 1 and failed_items:
        top_owner = max(owner_fail, key=owner_fail.get)
        findings.append(
            f"失败分布在 {len(owner_fail)} 个负责人，"
            f"{top_owner} 最多（{owner_fail[top_owner]} 个）"
        )
    elif len(owner_fail) == 1 and failed_items:
        top_owner = list(owner_fail.keys())[0]
        if owner_fail[top_owner] >= 2:
            findings.append(f"全部 {owner_fail[top_owner]} 个失败都属于 {top_owner}")
    if len(failed_items) >= 10:
        findings.append(f"失败数量较多（{len(failed_items)}），可能存在批量性问题（资源组/上游依赖）")

    if findings:
        print("【关键发现】")
        for f in findings:
            print(f"  - {f}")

    # ── 建议动作 ──
    if failed_items:
        first = failed_items[0]
        tid = first.get("taskId", "")
        name = first.get("nodeName", "")
        actions.append((f"查看失败日志 ({name})",
                        f"get_task_instance_log --taskInstanceId {tid}"))
        if len(failed_items) > 1:
            task_ids = [str(i.get("taskId")) for i in failed_items]
            actions.append((f"批量重跑全部 {len(failed_items)} 个失败实例",
                            f"rerun_task_instances --env prod --projectId {project_id} --taskIds '{json.dumps(task_ids)}'"))
    if severe_errors:
        top = severe_errors[0]
        actions.append((f"优先处理连续失败最久的任务: {top['name']}",
                        f"query_instances.py --project-id {project_id} --status failed --search {top['name']}"))
    if not actions:
        actions.append(("查看数据集成详情",
                        f"di_overview.py --project-id {project_id} --date {target_date}"))

    print("【建议动作】")
    for i, (desc, cmd) in enumerate(actions, 1):
        print(f"  {i}. {desc}")
        print(f"     → {cmd}")


# ─── 主流程 ──────────────────────────────────────────────────

def daily_check(args):
    client = BFFClient(quiet=True)
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag="[daily]")
    target_date = _resolve_date(args.date)
    is_mine = args.mine
    scope = "我的" if is_mine else "全部"
    telemetry_start("daily_check.py", module="task-ops",
                    project_id=project_id, date=str(target_date))

    print(f"{_TAG} 工作空间: {project_id} | 业务日期: {target_date} | 范围: {scope}")
    print(f"{'=' * 60}")

    # ── Phase 1: 概况（复用 ops_overview 各 section） ──

    print(f"\n📊 周期实例运行概况")
    cycle_metrics = _section_cycle_instances(client, project_id, target_date, is_mine)

    print(f"\n🔴 连续失败排行 TOP 5")
    error_rank = _section_error_rank(client, project_id)

    print(f"\n🐢 耗时排行 TOP 5")
    has_slow_rank = _section_slow_rank(client, project_id)

    print(f"\n📦 数据集成（离线）")
    _section_di_status(client, project_id, target_date)
    print(f"\n  读取端:")
    _section_di_datasource(client, project_id, target_date, "reader")
    print(f"\n  写入端:")
    _section_di_datasource(client, project_id, target_date, "writer")

    print(f"\n🔄 数据集成（实时）")
    _section_di_realtime(client, project_id)

    print(f"\n🔧 手动任务")
    _section_manual_biz(client, project_id, target_date)

    # ── Phase 2: 自动追查失败实例 ──

    fail_count = cycle_metrics.get("fail") if cycle_metrics else None
    failed_items = []

    if fail_count and isinstance(fail_count, (int, float)) and int(fail_count) > 0:
        print(f"\n{'─' * 60}")
        print(f"📋 失败实例列表（自动追查）")

        date_params = _calc_date_params(args.date)
        try:
            items = _qi_api_call(client, "getInstanceList",
                                 projectId=project_id,
                                 env="prod", tenantId=1,
                                 dagType=0, taskTypes=0,
                                 includeRelation="false",
                                 withAlarm="false", slowly="false",
                                 withRerun="false",
                                 taskStatuses="5",  # failed
                                 prgTypes="",
                                 searchText="",
                                 owner="",
                                 resgroupId="",
                                 sortOrder="", sortField="",
                                 alarmTime="", solId="", nodeTag="",
                                 bizId="", connectionRegionId="",
                                 connectionType="", connections="",
                                 baseLineId="", priorityList="",
                                 scheIntervalList="",
                                 diResGroupIdentifier="",
                                 diSrcType="", diSrcDatasource="",
                                 diDstType="", diDstDatasource="",
                                 flowId="", alarmId="", advanceSort="",
                                 pageNum=1, pageSize=40,
                                 **date_params)
            if not isinstance(items, list):
                items = [items] if items else []
            failed_items = items
            if failed_items:
                _print_table(failed_items)
                _print_fail_groups(failed_items, project_id)
        except Exception as e:
            print(f"{_TAG} 查询失败实例出错: {e}")
    else:
        print(f"\n{_TAG} 无失败实例，跳过失败追查")

    # ── Phase 3: 合并评估 ──

    baseline = get_baseline(project_id)
    _combined_assessment(cycle_metrics, error_rank, failed_items, [],
                         project_id, target_date, baseline, has_slow_rank)

    # ── 更新基线 ──
    rate = cycle_metrics.get("success_rate") if cycle_metrics else None
    if rate is not None and fail_count is not None:
        try:
            update_baseline(project_id, rate, int(fail_count))
        except Exception:
            pass

    # ── 记录失败节点为已知问题 ──
    for item in failed_items:
        node_id = str(item.get("nodeId", item.get("taskId", "")))
        node_name = item.get("nodeName", "")
        if node_id and node_name:
            try:
                record_known_issue(project_id, node_id, node_name,
                                   pattern="实例失败")
            except Exception:
                pass

    # ── telemetry + save ──
    severity = "ok"
    if cycle_metrics:
        r = cycle_metrics.get("success_rate")
        if r is not None and r < 0.85:
            severity = "critical"
        elif r is not None and r < 0.95:
            severity = "warning"
    telemetry_end(result={"severity": severity,
                          "error_rank_count": len(error_rank),
                          "failed_instance_count": len(failed_items)})

    save_tool_result("daily_check", {
        "status": "ok",
        "project_id": project_id,
        "date": str(target_date),
        "cycle_metrics": cycle_metrics,
        "error_rank_count": len(error_rank),
        "failed_instance_count": len(failed_items),
    })


# ─── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="每日运维巡检（一键）")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--project-name", help="工作空间名称")
    parser.add_argument("--date", default="yesterday",
                        help="业务日期: yesterday(默认)/today/YYYY-MM-DD")
    parser.add_argument("--mine", action="store_true", help="只看我的任务")
    args = parser.parse_args()

    if not args.project_id and not args.project_name:
        telemetry_start("daily_check.py", module="task-ops")
        from bff_client import list_workspaces_for_selection
        list_workspaces_for_selection("daily_check.py")
        telemetry_end(exit_code=0, result={"action": "list_workspaces"})
        return

    daily_check(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("daily_check.py", "task-ops", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("daily_check.py", "task-ops", 1, error=str(e)[:100])
        print(f"\n[error] {e}")
        print(f"  如需上报此问题: report_bug.py \"{e}\" --script daily_check.py")
        sys.exit(1)
