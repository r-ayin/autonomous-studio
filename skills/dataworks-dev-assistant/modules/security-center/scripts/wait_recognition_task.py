#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轮询等待敏感数据识别任务执行完成

用法:
    python wait_recognition_task.py --task-name test_skyfire_01        # 按名字模糊定位
    python wait_recognition_task.py --task-id <uuid>                    # 按 taskId 精确定位
    python wait_recognition_task.py --task-name xx --timeout 300        # 自定义超时（秒）

终态：taskStatus ∈ {Done, Failed}（其他都算中间态继续等）。
超时 → 写 .dataworks/backlogs.json 供下一次会话自动提醒。

⚠️ 本脚本只等"任务执行状态"。敏感字段明细清单用 view_recognition_result.py 查。
"""

import argparse
import sys
import time

from bff_client import BFFClient, add_backlog


_TERMINAL = {"Done", "Failed"}
_PENDING = {"Waiting", "Running", "Queuing", "Scheduled"}


def _fetch(client, task_name=None, task_id=None):
    """拉 listRecognitionTasks，按 task_name/task_id 过滤到单任务。
    只有 task_id 时把 pageSize 调大兜底（服务端没按 taskId 直接过滤的参数）。
    """
    page_size = 50 if task_name else 200
    tasks = client.load(
        "listRecognitionTasks",
        pageNumber=1,
        pageSize=page_size,
        fuzzySearchItem=task_name or "",
    ) or []
    if task_id:
        tasks = [t for t in tasks if (t.get("taskId") or "") == task_id]
    elif task_name:
        exact = [t for t in tasks if (t.get("taskName") or "") == task_name]
        tasks = exact or tasks
    return tasks


def main():
    parser = argparse.ArgumentParser(description="轮询等待识别任务执行完成")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--task-name", help="任务名（fuzzy 后 exact 匹配）")
    g.add_argument("--task-id", help="任务 uuid（精确）")
    parser.add_argument("--timeout", type=int, default=120,
                        help="轮询最长秒数（默认 120）")
    parser.add_argument("--interval", type=int, default=5,
                        help="轮询间隔秒数（默认 5）")
    args = parser.parse_args()

    client = BFFClient()

    # 先定位任务
    tasks = _fetch(client, task_name=args.task_name, task_id=args.task_id)
    if not tasks:
        who = f"name~'{args.task_name}'" if args.task_name else f"id={args.task_id}"
        print(f"未找到识别任务 ({who})", file=sys.stderr)
        print("→ 列所有任务: list_recognition_tasks.py", file=sys.stderr)
        sys.exit(1)
    if len(tasks) > 1:
        print(f"⚠️ 匹配到 {len(tasks)} 个任务，请用 --task-id 精确指定：")
        for t in tasks[:10]:
            print(f"  {t.get('taskId')}  {t.get('taskName')}  [{t.get('taskStatus')}]")
        sys.exit(1)

    task = tasks[0]
    tid = task.get("taskId")
    tname = task.get("taskName")

    # 轮询
    start = time.time()
    last_status = None
    while True:
        status = task.get("taskStatus") or "?"
        if status != last_status:
            last_status = status
            elapsed = int(time.time() - start)
            print(f"[{elapsed:>3}s] {tname} status={status}  executionTimes={task.get('executionTimes', 0)}")

        if status in _TERMINAL:
            break

        elapsed = time.time() - start
        if elapsed >= args.timeout:
            # 超时：进 backlog，下次会话自动提醒
            add_backlog(
                type_name="recognition_task",
                label=f"识别任务 {tname} 等执行完成（当前 status={status}，已等 {int(elapsed)}s）",
                check={
                    "api": "listRecognitionTasks",
                    "params": {"fuzzySearchItem": tname or "", "pageNumber": 1, "pageSize": 20},
                    "status_field": None,   # list 结构，无单字段；backlog 看到后手动检查
                    "terminal": {"Done": "执行完成", "Failed": "执行失败"},
                    "pending": {"Waiting": "等待中", "Running": "运行中", "Queuing": "队列中"},
                },
                context={"taskId": tid, "taskName": tname, "lastSeenStatus": status},
                on_success=f"python wait_recognition_task.py --task-id {tid}",
            )
            print(f"\n⚠️ 轮询超时 {args.timeout}s，已加入异步任务。下次会话开始会自动提醒查看。")
            print(f"→ 手动查: list_recognition_tasks.py --task-id {tid}")
            sys.exit(2)  # 非零退出表示未完成

        time.sleep(args.interval)
        tasks = _fetch(client, task_name=tname, task_id=tid)
        task = tasks[0] if tasks else task

    # 终态
    print()
    print(f"━━ 任务执行结束 ━━")
    print(f"  taskName:          {tname}")
    print(f"  taskId:            {tid}")
    print(f"  taskStatus:        {task.get('taskStatus')}")
    print(f"  executionTimes:    {task.get('executionTimes')}")
    last = task.get("lastExecutionTime")
    if last:
        from datetime import datetime
        ts = datetime.fromtimestamp(int(last) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  lastExecutionTime: {ts}")

    print()
    eng = task.get("engineType")
    eng_arg = f" --engine {eng}" if eng else ""
    if task.get("taskStatus") == "Failed":
        print(f"→ 看失败详情: view_recognition_result.py{eng_arg}（有结果就说明部分表扫完了）")
    else:
        print(f"→ 看识别结果（敏感字段清单）: view_recognition_result.py{eng_arg}")
        print(f"→ 按敏感类型分布: view_recognition_result.py{eng_arg} --group-by sensitiveTypeName")
    print(f"→ 重跑: 暂无 runRecognitionTask API；可用 create_recognition_task.py 再建个 Once 任务")


if __name__ == "__main__":
    main()
