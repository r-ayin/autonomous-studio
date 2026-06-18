#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基线运行概览 — 基线列表 + 运行状态 + 告警 + 事件

查看项目下的基线配置列表、当日运行状态（完成/未完成/破线）、紧急告警和事件。

用法:
    python baseline_overview.py --project-name autotest
    python baseline_overview.py --project-id 14255
    python baseline_overview.py --project-id 14255 --biz-date 2026-04-06

涉及 API: listBaseline, getBaselineStatusLists, listCriticalAlerts, listTopics
"""

import argparse
from datetime import datetime, timedelta

from bff_client import BFFClient, resolve_project_id

_TAG = "baseline_overview"
_PRIORITY_LABEL = {"1": "P1", "3": "P3", "5": "P5", "7": "P7", "8": "P8",
                   1: "P1", 3: "P3", 5: "P5", 7: "P7", 8: "P8"}


def main():
    parser = argparse.ArgumentParser(description="基线运行概览")
    parser.add_argument("--project-id", type=int, help="项目 ID（与 --project-name 二选一）")
    parser.add_argument("--project-name", help="工作空间名称（与 --project-id 二选一）")
    parser.add_argument("--biz-date", help="业务日期（YYYY-MM-DD，默认昨天）")
    args = parser.parse_args()

    if not args.project_id and not args.project_name:
        parser.error("需要 --project-id 或 --project-name")

    client = BFFClient()

    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
    biz_date = args.biz_date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    common = dict(projectId="0", env="prod", tenantId="1")

    # 1. 基线列表
    baselines = client.load("listBaseline",
                            **common,
                            projectIds=str(project_id),
                            isHour="0,1",
                            priority="1,3,5,7,8",
                            pageNum="1", pageSize="50")

    # 2. 基线运行状态（全优先级，用于和列表关联）
    status_list = client.load("getBaselineStatusLists",
                              **common,
                              bizDate=biz_date,
                              baseLineType="0,1",
                              finishStatus="0,1,2",
                              priority="1,3,5,7,8",
                              pageNum="1", pageSize="200")

    # 构建 baselineid → 运行状态的索引
    status_map = {}
    if isinstance(status_list, list):
        for s in status_list:
            bid = s.get("baselineid")
            if bid:
                status_map[bid] = s

    # 输出基线列表（合并运行状态）
    print(f"\n━━ 基线列表（项目 {project_id}，{biz_date}）━━")
    if isinstance(baselines, list):
        print(f"  共 {len(baselines)} 条基线\n")

        # 表头
        print(f"  {'ID':>12s}  {'名称':<28s} {'承诺':>5s}  {'优先级':>4s} {'负责人':<8s} {'运行状态'}")
        print(f"  {'─'*12}  {'─'*28} {'─'*5}  {'─'*4} {'─'*8} {'─'*10}")

        for b in baselines:
            bid = b.get("baselineid", "?")
            name = b.get("slaname", b.get("baselinename", b.get("appname", "?")))
            if len(name) > 26:
                name = name[:24] + ".."
            exp_h = b.get("exphour", "?")
            exp_m = b.get("expminu", 0)
            exp = f"{exp_h}:{exp_m:02d}" if isinstance(exp_m, int) else "?"
            priority = _PRIORITY_LABEL.get(b.get("priority"), str(b.get("priority", "?")))
            admin = b.get("adminname", "?")
            if len(admin) > 6:
                admin = admin[:5] + ".."

            # 关联运行状态
            st = status_map.get(bid)
            if st:
                fs = st.get("finishstatus")
                if fs == 1:
                    run_status = "✅ 已完成"
                elif fs == 2:
                    run_status = "❌ 破线"
                else:
                    run_status = "⏳ 未完成"
            else:
                run_status = "—"

            print(f"  {bid:>12}  {name:<28s} {exp:>5s}  {priority:>4s} {admin:<8s} {run_status}")
    else:
        print(f"  {baselines}")

    # 3. 运行状态汇总
    if isinstance(status_list, list) and status_list:
        finished = sum(1 for s in status_list if s.get("finishstatus") == 1)
        unfinished = sum(1 for s in status_list if s.get("finishstatus") == 0)
        broken = sum(1 for s in status_list if s.get("finishstatus") == 2)
        print(f"\n  汇总: 已完成 {finished} | 未完成 {unfinished} | 破线 {broken}")

        # 列出破线和未完成的
        problems = [s for s in status_list if s.get("finishstatus") in (0, 2)]
        if problems:
            print()
            for s in problems[:10]:
                name = s.get("slaname", s.get("baselinename", "?"))
                bid = s.get("baselineid", "?")
                fs = "破线" if s.get("finishstatus") == 2 else "未完成"
                print(f"  ⚠️  [{bid}] {name}  {fs}")

    # 4. 紧急告警
    alerts = client.load("listCriticalAlerts",
                         projectId=str(project_id), env="prod", tenantId="1")
    print(f"\n━━ 紧急告警 ━━")
    if isinstance(alerts, list):
        if not alerts:
            print("  无紧急告警")
        for a in alerts[:10]:
            print(f"  {a}")
    else:
        print(f"  {alerts}")

    # 5. 事件列表
    topics = client.load("listTopics",
                         env="prod", tenantId="1",
                         userid=client.get_my_base_id(),
                         topicstatus="10,11",
                         topictypes="0,1",
                         tLevels="1,3,5,7,8",
                         beginDate=biz_date,
                         endDate=biz_date,
                         pageNum="1", pageSize="20")
    print(f"\n━━ 事件（{biz_date}）━━")
    if isinstance(topics, list):
        if not topics:
            print("  无事件")
        for t in topics[:10]:
            subject = t.get("subject", "?")
            status = t.get("topicstatus", "?")
            owner = t.get("rspuserNickname", t.get("rspuser", "?"))
            print(f"  [{status}] {subject}  负责人={owner}")
    else:
        print(f"  {topics}")

    # chain hint
    if isinstance(baselines, list) and baselines:
        bid = baselines[0].get("baselineid", "?")
        print(f"\n  💡 查看基线甘特图: python baseline_gantt.py --project-id {project_id} --baseline-id {bid} --biz-date {biz_date}")


if __name__ == "__main__":
    main()
