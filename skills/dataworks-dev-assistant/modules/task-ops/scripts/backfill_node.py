#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补数据工具 —— 对已发布节点创建补数据实例

两阶段流程：
    # Phase 1：准备（输出确认摘要）
    python backfill_node.py --project-id 23304 --task-id 309116864 --days 7
    python backfill_node.py --project-id 23304 --task-id 309116864 --start 2026-03-20 --end 2026-03-26
    python backfill_node.py --project-id 23304 --task-id 309116864 --days 1 --env dev  # 开发环境补数据

    # Phase 2：用户确认后提交（写入待办，不轮询）
    python backfill_node.py --confirm

    # 查看补数据进度
    python check_backlogs.py
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

from bff_client import BFFClient, save_tool_result, add_backlog
from telemetry import telemetry_start, telemetry_end, telemetry_fail


# ─── 常量 ──────────────────────────────────────────────────────

_PENDING_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "pending_backfill.json")
_TAG = "[backfill]"


# ─── 内部 API 调用 ────────────────────────────────────────────

def _api_call(client, api_name, **kwargs):
    """直接调用 API（绕过写操作检查，用于已确认的内部步骤）"""
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


# ─── Phase 1：准备 ─────────────────────────────────────────────

def prepare_backfill(project_id, task_id, start_date, end_date, env="prod"):
    """Phase 1: 展示确认摘要，不调任何 API"""
    now = datetime.now()
    name = f"P_{task_id}_{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}"
    env_label = "生产环境" if env == "prod" else "开发环境"

    print(f"{_TAG} ⚠️ 待确认补数据操作:")
    print(f"  projectId: {project_id}")
    print(f"  taskId: {task_id}")
    print(f"  环境: {env_label} ({env})")
    print(f"  日期范围: {start_date} ~ {end_date}")
    print(f"  补数据名称: {name}")

    pending = {
        "project_id": project_id,
        "task_id": task_id,
        "start_date": start_date,
        "end_date": end_date,
        "name": name,
        "env": env,
        "created_at": now.isoformat(),
    }
    pending_path = _PENDING_FILE
    with open(pending_path, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

    print(f"  → 用户确认后执行: python backfill_node.py --confirm")


# ─── Phase 2：确认执行 + 轮询 ─────────────────────────────────

def confirm_and_backfill():
    """Phase 2: 提交补数据 + 写入待办"""
    pending_path = _PENDING_FILE
    if not os.path.exists(pending_path):
        print(f"{_TAG} 没有待确认的补数据操作。请先运行: python backfill_node.py --project-id <id> --task-id <taskId> --days 7")
        sys.exit(1)

    with open(pending_path, "r", encoding="utf-8") as f:
        pending = json.load(f)

    # 时间守卫
    created_at = pending.get("created_at")
    if created_at:
        elapsed = (datetime.now() - datetime.fromisoformat(created_at)).total_seconds()
        if elapsed < 10:
            print(
                f"⚠️ 操作被拦截：必须先让用户确认。\n"
                f"现在立即停止，将上一步的操作摘要展示给用户，等用户明确回复「确认」后，再调用 confirm。\n"
                f"不要重试，不要等待，不要 sleep —— 先回复用户。"
            )
            sys.exit(1)

    os.remove(pending_path)

    project_id = pending["project_id"]
    task_id = pending["task_id"]
    start_date = pending["start_date"]
    end_date = pending["end_date"]
    name = pending["name"]
    env = pending.get("env", "prod")

    client = BFFClient(quiet=True)

    # 构造请求体
    body = {
        "env": env,
        "excludeNodeIds": [],
        "includeNodeIds": [task_id],
        "isParallel": False,
        "multipleTimePeriods": json.dumps([{
            "bizBeginTime": start_date,
            "bizEndTime": end_date,
        }]),
        "name": name,
        "newAsync": True,
        "order": "asc",
        "parallelGroup": 1,
        "projectId": project_id,
        "resGroupId": "",
        "rootNodeId": task_id,
        "rootNodeProjectId": project_id,
        "tenantId": "",
        "useMultipleTimePeriods": True,
        "needAlert": True,
        "alertNoticeType": "sms,mail",
        "alertType": "5",
    }

    # 调用 supplementAsync
    print(f"{_TAG} 创建补数据任务...")
    try:
        result = _api_call(client, "supplementAsync", **body)
    except Exception as e:
        print(f"{_TAG} ❌ 补数据请求失败: {e}")
        save_tool_result("backfill", {
            "summary": f"补数据失败: {e}",
            "status": "fail",
        })
        sys.exit(1)

    # 提取 requestIds
    if isinstance(result, dict):
        request_ids = result.get("requestIds") or result.get("requestId") or result.get("data")
    elif isinstance(result, str):
        request_ids = result
    else:
        request_ids = str(result) if result else None

    if not request_ids:
        print(f"{_TAG} ❌ 未获取到 requestIds，返回值: {result}")
        save_tool_result("backfill", {
            "summary": "补数据失败: 未获取到 requestIds",
            "status": "fail",
        })
        sys.exit(1)

    # 提交成功，直接写入待办（不轮询，补数据耗时长）
    env_label = "生产环境" if env == "prod" else "开发环境"
    print(f"{_TAG} ✅ 补数据任务已提交 | env={env_label} | requestIds={request_ids}")
    # 成功后的下一步指引
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.abspath(os.path.join(_script_dir, "..", "..", ".."))
    _core_dir = os.path.join(_project_root, "core")
    if env == "dev":
        success_hint = (f"补数据实例已运行完成，数据已产出到开发环境。"
                        f"发布到生产环境: PYTHONPATH={_core_dir} python {_project_root}/modules/deployment/scripts/deploy_node.py --confirm-prod")
    else:
        success_hint = "补数据实例已运行完成，数据已产出"

    add_backlog(
        type_name="backfill",
        label=f"补数据({env_label}) task={task_id} {start_date}~{end_date}",
        check={
            "api": "getSupplementAsyncResult",
            "params": {"env": env, "projectId": project_id, "requestIds": request_ids},
            "result_is_list": True,
            "status_field": "status",
            "terminal": {"6": "成功", "5": "失败"},
            "pending": {"1": "未运行", "4": "运行中"},
        },
        context={"project_id": project_id, "task_id": task_id},
        on_success=success_hint,
    )
    print(f"{_TAG} → 已加入异步任务列表，查看进度: python check_backlogs.py")

    save_tool_result("backfill", {
        "summary": f"补数据已提交，已加入异步任务列表 | {start_date}~{end_date}",
        "status": "submitted",
        "project_id": project_id,
        "task_id": task_id,
        "request_ids": request_ids,
        "date_range": f"{start_date} ~ {end_date}",
    })


# ─── CLI 入口 ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="补数据工具（两阶段确认）",
        usage="%(prog)s --project-id <id> --task-id <taskId> --days 7 | %(prog)s --confirm",
    )
    parser.add_argument("--confirm", action="store_true",
                        help="执行已确认的补数据操作（Phase 2）")
    parser.add_argument("--project-id", type=int,
                        help="工作空间 ID")
    parser.add_argument("--task-id", type=int,
                        help="调度任务 ID（GetNode 返回的 taskId）")
    parser.add_argument("--days", type=int,
                        help="补最近 N 天的数据")
    parser.add_argument("--start",
                        help="起始日期（YYYY-MM-DD）")
    parser.add_argument("--end",
                        help="结束日期（YYYY-MM-DD）")
    parser.add_argument("--env", choices=["prod", "dev"], default="prod",
                        help="环境（prod=生产, dev=开发，默认 prod）")

    args = parser.parse_args()

    telemetry_start("backfill_node.py", module="task-ops", project_id=args.project_id)

    if args.confirm:
        confirm_and_backfill()
        telemetry_end(result={"action": "confirm"})
    elif args.project_id and args.task_id:
        # 计算日期范围
        if args.days:
            today = datetime.now().date()
            end_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            start_date = (today - timedelta(days=args.days)).strftime("%Y-%m-%d")
        elif args.start and args.end:
            start_date = args.start
            end_date = args.end
        else:
            print(f"{_TAG} 请指定日期范围: --days N 或 --start YYYY-MM-DD --end YYYY-MM-DD")
            sys.exit(1)

        prepare_backfill(args.project_id, args.task_id, start_date, end_date, env=args.env)
        telemetry_end(result={"action": "prepare"})
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("backfill_node.py", "task-ops", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("backfill_node.py", "task-ops", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
