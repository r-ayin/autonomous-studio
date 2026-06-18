#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询识别任务的执行记录列表（同一个周期任务多次执行的历史）

每条执行记录含 executionId / taskId / startTime / endTime。

用法:
    python list_task_records.py --task-id <uuid>
    python list_task_records.py --task-id <uuid> --limit 20

仅公有云。
"""

import argparse
import sys
from datetime import datetime

from bff_client import BFFClient


def _fmt(ms):
    if not ms:
        return "-"
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return str(ms)


def main():
    p = argparse.ArgumentParser(description="识别任务的历次执行记录")
    p.add_argument("--task-id", required=True, help="任务 uuid")
    p.add_argument("--limit", type=int, default=10, help="返回上限（默认 10）")
    args = p.parse_args()

    client = BFFClient(quiet=True)
    records = client.load(
        "listRecognitionTaskRecord",
        taskId=args.task_id,
        pageNumber=1,
        pageSize=min(args.limit, 100),
    ) or []

    if not records:
        print(f"任务 {args.task_id} 无执行记录")
        print("→ 查任务本身: list_recognition_tasks.py --task-id " + args.task_id)
        return

    print(f"任务 {args.task_id} 共 {len(records)} 条执行记录\n")
    print(f"  {'序号':<4} {'executionId':<40} {'开始':<20} {'结束':<20} {'耗时':<8}")
    print(f"  {'-'*4} {'-'*40} {'-'*20} {'-'*20} {'-'*8}")
    for i, r in enumerate(records, 1):
        eid = (r.get("executionId") or "")[:40]
        start = _fmt(r.get("startTime"))
        end = _fmt(r.get("endTime"))
        dur = "-"
        if r.get("startTime") and r.get("endTime"):
            sec = (int(r["endTime"]) - int(r["startTime"])) // 1000
            dur = f"{sec}s" if sec < 3600 else f"{sec//60}m"
        print(f"  {i:<4} {eid:<40} {start:<20} {end:<20} {dur:<8}")

    print()
    print("→ 看本次执行发现的敏感字段: view_recognition_result.py（目前按 db/table 查询，暂无 executionId 过滤）")


if __name__ == "__main__":
    main()
