#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基线甘特图 — 基线详情 + 关键路径 + 甘特图 + 历史曲线

查看指定基线的运行详情、关键路径节点、甘特图时间线、历史完成时间曲线。

用法:
    python baseline_gantt.py --project-name autotest --baseline-id 341401088
    python baseline_gantt.py --project-id 14255 --baseline-id 341401088 --biz-date 2026-04-06

涉及 API: getBaseLineInfo, getBaseLineKeyPath, getGantt,
          getBaseLineHistoryCurve, getBaseLineIngroupIds, getBaseLineRelatedTopic
"""

import argparse
from datetime import datetime, timedelta

from bff_client import BFFClient, resolve_project_id


def fmt_time(ts):
    """时间戳 → HH:MM（自动判断秒/毫秒）"""
    if not ts or not isinstance(ts, (int, float)):
        return "?"
    try:
        # 13 位是毫秒，10 位是秒
        if ts > 1e12:
            ts = ts / 1000
        return datetime.fromtimestamp(ts).strftime("%H:%M")
    except Exception:
        return str(ts)


def main():
    parser = argparse.ArgumentParser(description="基线甘特图")
    parser.add_argument("--project-id", type=int, help="项目 ID（与 --project-name 二选一）")
    parser.add_argument("--project-name", help="工作空间名称（与 --project-id 二选一）")
    parser.add_argument("--baseline-id", type=int, required=True, help="基线 ID")
    parser.add_argument("--biz-date", help="业务日期（YYYY-MM-DD，默认昨天）")
    parser.add_argument("--ingroup-id", type=int, default=1, help="实例分组 ID（默认 1）")
    args = parser.parse_args()

    if not args.project_id and not args.project_name:
        parser.error("需要 --project-id 或 --project-name")

    client = BFFClient()
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag="baseline_gantt")

    biz_date = args.biz_date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    biz_date_compact = biz_date.replace("-", "")
    common = dict(projectId="0", env="prod", tenantId="1",
                  baselineId=str(args.baseline_id), bizDate=biz_date,
                  ingroupId=str(args.ingroup_id))

    # 1. 基线详情
    info = client.load("getBaseLineInfo", **common)
    print(f"\n━━ 基线详情 ━━")
    if isinstance(info, dict):
        name = info.get("appName", info.get("baselinename", "?"))
        exp_time = fmt_time(info.get("exptime"))
        first_ok = fmt_time(info.get("firstok"))
        buffer_val = info.get("buffer", "?")
        owner = info.get("baselineOwnerNickname", "?")
        bid = info.get("baselineid", args.baseline_id)
        print(f"  基线: [{bid}] {name}")
        print(f"  承诺时间: {exp_time}")
        print(f"  首次完成: {first_ok}")
        print(f"  余量: {buffer_val} 分钟")
        print(f"  负责人: {owner}")
    else:
        print(f"  {info}")

    # 2. 基线配置的末端节点
    detail = client.load("baselineDetail",
                         projectId="0", env="prod", tenantId="1",
                         baseLineIds=str(args.baseline_id))
    baseline_nodes = []
    if isinstance(detail, list) and detail:
        baseline_nodes = detail[0].get("nodes", [])
    print(f"\n━━ 基线节点（{len(baseline_nodes)} 个）━━")
    for i, n in enumerate(baseline_nodes):
        nid = n.get("nodeId", "?")
        nname = n.get("nodeName", "?")
        nowner = n.get("ownerName", "?")
        project = n.get("odpsProjectName", "?")
        print(f"  {i+1}. [{nid}] {nname}  负责人={nowner}  项目={project}")

    # 3. 关键路径
    key_path = client.load("getBaseLineKeyPath", **common)
    print(f"\n━━ 关键路径 ━━")
    if isinstance(key_path, list):
        if not key_path:
            print("  无关键路径数据")
        for i, node in enumerate(key_path[:15]):
            name = node.get("nodeName", "?")
            owner = node.get("ownerName", "?")
            buffer_val = node.get("buffer", "?")
            end = node.get("endcast", "?")
            print(f"  {i+1}. {name}  负责人={owner}  余量={buffer_val}min  预计完成={end}")
        if len(key_path) > 15:
            print(f"  ... 还有 {len(key_path) - 15} 个节点")
    else:
        print(f"  {key_path}")

    # 4. 甘特图
    # 获取甘特图需要一个 nodeid：优先关键路径，其次基线节点
    node_id = None
    if isinstance(key_path, list) and key_path:
        node_id = key_path[0].get("taskid")
    elif baseline_nodes:
        node_id = baseline_nodes[0].get("nodeId")

    if node_id:
        gantt = client.load("getGantt",
                            bizdate=biz_date,
                            defaultProjectId=str(project_id),
                            env="prod",
                            ingroupid=str(args.ingroup_id),
                            nodeid=str(node_id),
                            projectId=str(project_id))
        print(f"\n━━ 甘特图（节点 {node_id} 附近）━━")
        if isinstance(gantt, list):
            for g in gantt[:10]:
                name = g.get("viewname", g.get("appname", "?"))
                nid = g.get("nodeid", "?")
                owner = g.get("ownerName", "?")
                # 运行时间在 runs 数组里
                runs = g.get("runs", [])
                if runs and isinstance(runs[0], dict):
                    run = runs[0]
                    start = fmt_time(run.get("begtime"))
                    end = fmt_time(run.get("endtime"))
                    state = run.get("state", "?")
                    state_label = {4: "成功", 5: "失败", 3: "运行中", 0: "未运行"}.get(state, f"state={state}")
                    print(f"  {name} (node={nid})  {start}→{end}  [{state_label}]  负责人={owner}")
                else:
                    print(f"  {name} (node={nid})  负责人={owner}")
            if len(gantt) > 10:
                print(f"  ... 还有 {len(gantt) - 10} 个节点")
        else:
            print(f"  {gantt}")

    # 5. 历史完成时间曲线
    curve = client.load("getBaseLineHistoryCurve",
                        projectId="0", env="prod", tenantId="1",
                        baselineId=str(args.baseline_id),
                        bizDate=biz_date_compact,
                        ingroupId=str(args.ingroup_id))
    print(f"\n━━ 历史完成时间 ━━")
    if isinstance(curve, dict):
        exp = curve.get("expTime", "?")
        sla = curve.get("slaTime", "?")
        avg = curve.get("historyAvgTime", "?")
        history = curve.get("historyFinishTimes", [])
        print(f"  承诺: {exp}  SLA: {sla}  历史平均: {avg}")
        if isinstance(history, list) and history:
            recent = history[-5:]
            for h in recent:
                print(f"  {h.get('date', '?')}: {h.get('time', '?')}")
    else:
        print(f"  {curve}")

    # 6. 关联事件
    topics = client.load("getBaseLineRelatedTopic", **common)
    print(f"\n━━ 关联事件 ━━")
    if isinstance(topics, list):
        if not topics:
            print("  无关联事件")
        for t in topics[:5]:
            subject = t.get("subject", "?")
            owner = t.get("rspuserNickname", t.get("rspuser", "?"))
            print(f"  {subject}  负责人={owner}")
    else:
        print(f"  {topics}")


if __name__ == "__main__":
    main()
