#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作空间质量概览 — 运维 + 基线 + 治理 + 数据质量

一页看清工作空间的整体质量状况，聚合四个维度的摘要数据。

用法:
    python workspace_quality.py --project-name autotest
    python workspace_quality.py --project-id 14255
    python workspace_quality.py --project-id 14255 --biz-date 2026-04-06

涉及 API: getTaskRunInfo, listBaseline, getBaselineStatusLists,
          getAllScore, getScoreFactorDetail, getRunStatus
"""

import argparse
from datetime import datetime, timedelta

from bff_client import BFFClient, resolve_project_id

_TAG = "workspace_quality"


def main():
    parser = argparse.ArgumentParser(description="工作空间质量概览")
    parser.add_argument("--project-id", type=int, help="项目 ID（与 --project-name 二选一）")
    parser.add_argument("--project-name", help="工作空间名称（与 --project-id 二选一）")
    parser.add_argument("--biz-date", help="业务日期（YYYY-MM-DD，默认昨天）")
    args = parser.parse_args()

    if not args.project_id and not args.project_name:
        parser.error("需要 --project-id 或 --project-name")

    client = BFFClient()
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
    biz_date = args.biz_date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    biz_date_range = f"{biz_date} 00:00:00"
    biz_date_range_end = f"{biz_date} 23:59:59"
    owner_id = client.get_my_base_id()

    project_label = args.project_name or str(project_id)
    print(f"\n{'━' * 50}")
    print(f"  工作空间质量概览: {project_label}（{biz_date}）")
    print(f"{'━' * 50}")

    issues = []

    # ── 1. 运维（任务运行）──
    task_info = client.load("getTaskRunInfo",
                            env="prod",
                            projectId=str(project_id),
                            isMine="false",
                            beginBizDate=biz_date_range,
                            endBizDate=biz_date_range_end)
    print(f"\n【运维】")
    if isinstance(task_info, dict):
        total = task_info.get("totalCount", 0) or 0
        success = task_info.get("successCount", 0) or 0
        failure = task_info.get("failureCount", 0) or 0
        running = task_info.get("runningCount", 0) or 0
        waiting = (task_info.get("waitTimeCount", 0) or 0) + (task_info.get("waitResCount", 0) or 0)
        rate = f"{success * 100 / total:.1f}%" if total > 0 else "—"
        print(f"  任务总数: {total}  成功: {success}  失败: {failure}  运行中: {running}  等待: {waiting}")
        print(f"  完成率: {rate}")
        if total > 0 and success / total < 0.95:
            issues.append(f"任务完成率偏低({rate})")
        if failure > 0:
            print(f"  ⚠️ {failure} 个任务失败")
    else:
        print(f"  {task_info}")

    # ── 2. 基线 ──
    # 基线配置列表
    baselines = client.load("listBaseline",
                            projectId="0", env="prod", tenantId="1",
                            projectIds=str(project_id),
                            isHour="0,1",
                            priority="1,3,5,7,8",
                            pageNum="1", pageSize="50")
    # 基线运行状态
    status_list = client.load("getBaselineStatusLists",
                              projectId="0", env="prod", tenantId="1",
                              bizDate=biz_date,
                              baseLineType="0,1",
                              finishStatus="0,1,2",
                              priority="1,3,5,7,8",
                              pageNum="1", pageSize="200")

    print(f"\n【基线】")
    baseline_count = len(baselines) if isinstance(baselines, list) else 0
    print(f"  基线配置: {baseline_count} 条")

    if isinstance(status_list, list) and status_list:
        finished = sum(1 for s in status_list if s.get("finishstatus") == 1)
        unfinished = sum(1 for s in status_list if s.get("finishstatus") == 0)
        broken = sum(1 for s in status_list if s.get("finishstatus") == 2)
        print(f"  运行状态: 已完成 {finished} | 未完成 {unfinished} | 破线 {broken}")
        if broken > 0:
            issues.append(f"基线破线({broken} 条)")
            for s in status_list:
                if s.get("finishstatus") == 2:
                    name = s.get("slaname", s.get("baselinename", "?"))
                    print(f"    ❌ {name}")
    else:
        print(f"  运行状态: 当日无基线实例")

    # 列出高优先级基线（P7/P8）
    if isinstance(baselines, list):
        high_pri = [b for b in baselines if b.get("priority") in (7, 8)]
        if high_pri:
            print(f"  高优先级基线（{len(high_pri)} 条）:")
            for b in high_pri[:5]:
                name = b.get("slaname", b.get("baselinename", "?"))
                bid = b.get("baselineid", "?")
                exp_h = b.get("exphour", "?")
                exp_m = b.get("expminu", 0)
                exp = f"{exp_h}:{exp_m:02d}" if isinstance(exp_m, int) else "?"
                print(f"    [{bid}] {name}  承诺={exp}")

    # ── 3. 治理评分（DGC）──
    score = client.load("getAllScore", viewType="2", ownerId=owner_id)
    print(f"\n【治理评分】")
    if isinstance(score, dict):
        total_score = score.get("score", "?")
        level = score.get("scoreLevelEnum", "?")
        print(f"  总分: {total_score}  等级: {level}")

        dims = [("computeScore", "计算"), ("storageScore", "存储"),
                ("qualityScore", "质量"), ("securityScore", "安全"),
                ("developScore", "开发规范")]
        parts = []
        for key, label in dims:
            sub = score.get(key)
            if isinstance(sub, dict):
                parts.append(f"{label}={sub.get('score', '?')}")
        if parts:
            print(f"  {' | '.join(parts)}")
        if isinstance(total_score, (int, float)) and total_score < 80:
            issues.append(f"治理评分偏低({total_score})")
    else:
        print(f"  {score}")

    # 扣分项 TOP3
    factors = client.load("getScoreFactorDetail", viewType="2", ownerId=owner_id, field="5")
    if isinstance(factors, list) and factors:
        factors.sort(key=lambda f: f.get("deduction", 0))
        top3 = factors[:3]
        print(f"  扣分 TOP3:")
        for f in top3:
            print(f"    {f.get('deduction', 0):+.1f}  {f.get('name', '?')} ({f.get('count', 0)} 个)")

    # ── 4. 数据质量（DQC）──
    run_status = client.load("getRunStatus",
                             projectId=str(project_id),
                             datasourceTypes="odps",
                             envTypes="",
                             minDataDate=biz_date,
                             maxDataDate=biz_date)
    print(f"\n【数据质量】")
    if isinstance(run_status, dict):
        strong_failed = (run_status.get("strongFailedCount", 0) or 0) + (run_status.get("strongRedCount", 0) or 0)
        strong_passed = run_status.get("strongPassedCount", 0) or 0
        weak_failed = run_status.get("weakFailedCount", 0) or 0
        weak_passed = run_status.get("weakPassedCount", 0) or 0

        strong_total = strong_failed + strong_passed
        weak_total = weak_failed + weak_passed

        print(f"  强规则: {strong_passed} 通过 / {strong_failed} 异常（共 {strong_total}）")
        print(f"  弱规则: {weak_passed} 通过 / {weak_failed} 异常（共 {weak_total}）")
        if strong_failed > 0:
            issues.append(f"强规则异常({strong_failed} 条)")
    else:
        print(f"  {run_status}")

    # ── 5. 当前告警事件（与产品 workbench 首页对齐）──
    try:
        alerts = client.load("listCriticalAlerts",
                             projectId=str(project_id), env="prod", tenantId=1)
        alert_count = len(alerts) if isinstance(alerts, list) else 0
    except Exception:
        alert_count = None

    print(f"\n【当前告警】")
    if alert_count is None:
        print(f"  (告警查询失败，可手动: client.load('listCriticalAlerts', projectId={project_id}, env='prod', tenantId=1))")
    elif alert_count == 0:
        print(f"  ✅ 无未处理告警事件")
    else:
        print(f"  ⚠️ {alert_count} 条未处理告警事件")
        issues.append(f"未处理告警({alert_count} 条)")

    # ── 汇总 ──
    print(f"\n{'─' * 50}")
    if issues:
        print(f"  ⚠️ 需关注: {' | '.join(issues)}")
    else:
        print(f"  ✅ 整体质量正常")

    # chain hints
    print(f"\n  💡 详细查看:")
    print(f"    运维详情: python ops_overview.py --project-id {project_id} --date {biz_date}")
    print(f"    基线详情: python baseline_overview.py --project-id {project_id} --biz-date {biz_date}")
    print(f"    治理详情: python dgc_overview.py --owner-id {owner_id}")
    print(f"    质量规则: python dqc_overview.py --project-id {project_id}")


if __name__ == "__main__":
    main()
