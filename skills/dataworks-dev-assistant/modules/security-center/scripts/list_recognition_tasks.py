#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出敏感数据识别任务（安全中心 > 分类分级 > 识别任务）

用法:
    python list_recognition_tasks.py                            # 列全部
    python list_recognition_tasks.py --task-name test_skyfire   # 按任务名模糊搜
    python list_recognition_tasks.py --status Running           # 按状态过滤（客户端）
    python list_recognition_tasks.py --limit 200                # 扩大返回上限

仅公有云（弹内无此产品）。
"""

import argparse
import sys
from datetime import datetime

from bff_client import BFFClient


def _fmt_ts(ms):
    if not ms:
        return ""
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(ms)


def main():
    parser = argparse.ArgumentParser(description="敏感数据识别任务列表 / 单任务执行状态")
    parser.add_argument("--task-name", help="任务名关键字（走 fuzzySearchItem 服务端过滤）")
    parser.add_argument("--task-id", help="任务 uuid（精确单任务，客户端过滤）")
    parser.add_argument("--status", help="任务状态 Waiting/Running/Done/Failed（客户端过滤）")
    parser.add_argument("--limit", type=int, default=50, help="最多返回多少条（默认 50）")
    args = parser.parse_args()

    client = BFFClient(quiet=True)

    # 服务端真实分页；fuzzySearchItem 按 taskName 模糊
    tasks = client.load(
        "listRecognitionTasks",
        pageNumber=1,
        pageSize=min(args.limit, 200),
        fuzzySearchItem=args.task_name or "",
    ) or []

    # 客户端 status 过滤
    if args.status:
        tasks = [t for t in tasks if (t.get("taskStatus") or "").lower() == args.status.lower()]
    # 客户端 task-id 过滤（精确单任务）
    if args.task_id:
        tasks = [t for t in tasks if (t.get("taskId") or "") == args.task_id]

    if not tasks:
        kw = f" name~'{args.task_name}'" if args.task_name else ""
        st = f" status={args.status}" if args.status else ""
        print(f"无识别任务{kw}{st}")
        print("→ 扩大搜索: 不加任何过滤参数再跑一次")
        print("→ 新建识别任务: create_recognition_task.py --task-name xx --engine ODPS.ODPS")
        return

    print(f"共 {len(tasks)} 个识别任务")
    print()
    print(f"  {'序号':<4} {'任务名':<35} {'引擎':<14} {'状态':<10} {'类型':<10} {'执行次数':>6} {'最近执行':<17}")
    print(f"  {'-'*4} {'-'*35} {'-'*14} {'-'*10} {'-'*10} {'-'*6} {'-'*17}")
    for i, t in enumerate(tasks, 1):
        name = (t.get("taskName") or "")[:34]
        engine = (t.get("engineType") or "")[:13]
        status = (t.get("taskStatus") or "")
        ttype = (t.get("taskType") or "")
        exec_times = t.get("executionTimes", 0)
        last_run = _fmt_ts(t.get("lastExecutionTime"))
        print(f"  {i:<4} {name:<35} {engine:<14} {status:<10} {ttype:<10} {exec_times:>6} {last_run:<17}")

    print()
    # 状态分布
    from collections import Counter
    status_dist = Counter(t.get("taskStatus") or "?" for t in tasks)
    engine_dist = Counter(t.get("engineType") or "?" for t in tasks)
    print(f"  状态分布: " + " / ".join(f"{s}={c}" for s, c in status_dist.most_common()))
    print(f"  引擎分布: " + " / ".join(f"{s}={c}" for s, c in engine_dist.most_common()))

    # 下一步引导
    print()
    running = [t for t in tasks if (t.get("taskStatus") or "") == "Running"]
    if running:
        tid = running[0].get("taskId", "")
        print(f"→ 有 {len(running)} 个任务运行中 (示例 taskId={tid[:36]})")
    print(f"→ 模糊搜任务: list_recognition_tasks.py --task-name <关键字>")
    print(f"→ 按状态过滤: list_recognition_tasks.py --status Running|Done|Failed")


if __name__ == "__main__":
    main()
