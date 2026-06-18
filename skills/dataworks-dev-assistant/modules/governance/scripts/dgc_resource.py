#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资源治理概况 — 计算/存储/调度资源用量 + 趋势 + 异常

查看项目的资源使用情况：MC 计算资源、存储资源、调度资源概览，以及资源用量 TOP 表/任务。

用法:
    python dgc_resource.py --project-id 14255
    python dgc_resource.py --project-id 14255 --date 2026-04-05
    python dgc_resource.py --project-id 14255 --detail calc   # 计算资源 TOP 明细
    python dgc_resource.py --project-id 14255 --detail store  # 存储资源 TOP 明细

涉及 API: querySummaryResourceUsageView, queryCalcDetail, queryCalcDiff,
          queryStoreDetail, queryStoreDiff, queryScheduleDetail, mcResourceTrends
"""

import argparse
from datetime import datetime, timedelta

from bff_client import BFFClient, resolve_project_id

_TAG = "dgc_resource"


def fmt_size(bytes_val):
    """字节 → 人类可读"""
    if not isinstance(bytes_val, (int, float)) or bytes_val == 0:
        return str(bytes_val)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(bytes_val) < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def main():
    parser = argparse.ArgumentParser(description="资源治理概况")
    parser.add_argument("--project-id", type=int, help="项目 ID（与 --project-name 二选一）")
    parser.add_argument("--project-name", help="工作空间名称")
    parser.add_argument("--date", help="日期（YYYY-MM-DD 或 YYYYMMDD，默认昨天）")
    parser.add_argument("--detail", choices=["calc", "store", "schedule"], help="查看明细：calc=计算, store=存储, schedule=调度")
    args = parser.parse_args()

    if not args.project_id and not args.project_name:
        parser.error("需要 --project-id 或 --project-name")

    client = BFFClient()
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)

    if args.date:
        ds = args.date.replace("-", "")
    else:
        ds = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    # 1. 资源用量概览
    summary = client.load("querySummaryResourceUsageView",
                          projectId=str(project_id), ds=ds, dataSourceType="MC")
    print(f"\n━━ 资源概览（项目 {project_id}，{ds}）━━")
    if isinstance(summary, dict):
        for key, label in [("mcCalcResourcePre", "MC计算(预付费)"), ("mcCalcResourcePost", "MC计算(后付费)"),
                           ("store", "存储"), ("task", "任务数"),
                           ("schedule", "调度"), ("offlineSync", "离线同步"),
                           ("cpu", "CPU"), ("mem", "内存")]:
            val = summary.get(key)
            if not isinstance(val, dict):
                continue
            count = val.get("count", 0)
            if count == 0 and key not in ("store", "task"):
                continue  # 跳过无数据的
            day_ratio = val.get("preDayRatio")
            if key == "store" and isinstance(count, (int, float)):
                display = fmt_size(count)
            elif isinstance(count, float) and count == int(count):
                display = str(int(count))
            else:
                display = f"{count}"
            ratio_str = ""
            if isinstance(day_ratio, (int, float)):
                ratio_str = f"  日环比: {day_ratio:+.1%}"
            print(f"  {label}: {display}{ratio_str}")
    else:
        print(f"  {summary}")

    # 2. 明细查询
    if args.detail == "calc":
        detail = client.load("queryCalcDetail",
                             projectId=str(project_id), ds=ds,
                             pageNum="1", pageSize="20", dataSourceType="MC",
                             granularity="NODE")
        print(f"\n━━ 计算资源 TOP 20（MC）━━")
        if isinstance(detail, list):
            for i, d in enumerate(detail[:20]):
                name = d.get("nodeName", d.get("taskName", "?"))
                cpu = d.get("cpuCost", "?")
                mem = d.get("memCost", "?")
                owner = d.get("owner", "?")
                print(f"  {i+1}. {name}  cpu={cpu}  mem={mem}  负责人={owner}")
        else:
            print(f"  {detail}")

    elif args.detail == "store":
        detail = client.load("queryStoreDetail",
                             projectId=str(project_id), ds=ds,
                             pageNum="1", pageSize="20", dataSourceType="MC")
        print(f"\n━━ 存储资源 TOP 20（MC）━━")
        if isinstance(detail, list):
            for i, d in enumerate(detail[:20]):
                table = d.get("tableName", d.get("databaseName", "?"))
                size = d.get("dataSize", 0)
                lifecycle = d.get("lifeCycle", "?")
                owner = d.get("owner", "?")
                print(f"  {i+1}. {table}  大小={fmt_size(size)}  生命周期={lifecycle}  负责人={owner}")
        else:
            print(f"  {detail}")

    elif args.detail == "schedule":
        detail = client.load("queryScheduleDetail",
                             projectId=str(project_id), ds=ds,
                             pageNum="1", pageSize="20")
        print(f"\n━━ 调度耗时 TOP 20 ━━")
        if isinstance(detail, list):
            for i, d in enumerate(detail[:20]):
                name = d.get("nodeName", d.get("nodeId", "?"))
                avg = d.get("costTimeAvg", "?")
                baseline = d.get("baseLineName", "")
                owner = d.get("ownerName", d.get("owner", "?"))
                bl = f"  基线={baseline}" if baseline else ""
                print(f"  {i+1}. {name}  平均耗时={avg}  负责人={owner}{bl}")
        else:
            print(f"  {detail}")

    else:
        # 无 --detail 时显示资源趋势
        print(f"\n  💡 查看明细:")
        print(f"    计算 TOP: python dgc_resource.py --project-id {project_id} --detail calc")
        print(f"    存储 TOP: python dgc_resource.py --project-id {project_id} --detail store")
        print(f"    调度 TOP: python dgc_resource.py --project-id {project_id} --detail schedule")


if __name__ == "__main__":
    main()
