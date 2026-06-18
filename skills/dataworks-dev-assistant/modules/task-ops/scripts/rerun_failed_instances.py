#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量重跑失败实例（通过补数据方式）

用途：rerun_task_instances API 不支持直接通过 instanceId 批量重跑；
改用 supplementAsync 按 nodeId 补指定业务日期的数据。

两阶段流程：
    # Phase 1：查询失败实例 + 准备（输出确认摘要）
    python rerun_failed_instances.py --project-id 14255                  # 默认昨天
    python rerun_failed_instances.py --project-name autotest --date 2026-04-12
    python rerun_failed_instances.py --project-id 14255 --owner me
    python rerun_failed_instances.py --project-id 14255 --task-type ODPS_SQL

    # Phase 2：用户确认后提交（N 个补数据，逐个提交到异步列表）
    python rerun_failed_instances.py --confirm

    # 查看进度
    python check_backlogs.py
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

from bff_client import BFFClient, save_tool_result, add_backlog, resolve_project_id
from telemetry import telemetry_start, telemetry_end, telemetry_fail


_PENDING_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "pending_rerun_failed.json")
_TAG = "[rerun-failed]"


def _api_call(client, api_name, **kwargs):
    api_meta = client.api_index.get(api_name)
    if not api_meta:
        raise ValueError(f"未找到 API: {api_name}")
    result = client._do_request(api_name, api_meta, **kwargs)
    code = result.get("code")
    if code not in (None, 0, "0", 200, "200"):
        raise RuntimeError(f"{api_name} 失败: code={code}, message={result.get('message','')}")
    return client._parse_return_structure(result, api_meta.get("return_structure", ""))


def _calc_date_params(date_str):
    today = datetime.now().date()
    if not date_str or date_str == "yesterday":
        biz_date = today - timedelta(days=1)
    elif date_str == "today":
        biz_date = today
    else:
        biz_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    run_date = biz_date + timedelta(days=1)
    return biz_date, {
        "bizdate": f"{biz_date.strftime('%Y-%m-%d')} 00:00:00",
        "bizBeginHour": f"{run_date.strftime('%Y-%m-%d')} 00:00:00",
        "bizEndHour": f"{run_date.strftime('%Y-%m-%d')} 23:59:59",
    }


def _resolve_owner(client, owner_str):
    if not owner_str:
        return ""
    if owner_str.strip().lower() == "me":
        return str(client.get_my_base_id())
    return owner_str


def _resolve_task_type(client, project_id, type_name):
    if not type_name:
        return ""
    if type_name.strip().isdigit():
        return type_name.strip()
    types = _api_call(client, "listNodeTypes_v2",
                      projectId=project_id, env="prod", tenantId=1)
    if not isinstance(types, list):
        types = [types] if types else []
    normalized = type_name.strip().upper().replace(" ", "_").replace("-", "_")
    for t in types:
        if (t.get("name") or "").upper() == normalized:
            return str(t.get("id", ""))
    print(f"{_TAG} 未知任务类型: {type_name}")
    sys.exit(1)


def prepare_rerun(args):
    client = BFFClient(quiet=True)
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
    biz_date, date_params = _calc_date_params(args.date)
    owner = _resolve_owner(client, args.owner)
    prg_types = _resolve_task_type(client, project_id, args.task_type)

    print(f"{_TAG} 查询 bizdate={biz_date} status=失败 的实例...")

    items = _api_call(
        client, "getInstanceList",
        projectId=project_id, env="prod", tenantId=1,
        dagType=0, taskTypes=0, includeRelation="false",
        withAlarm="false", slowly="false", withRerun="false",
        taskStatuses="5",
        prgTypes=prg_types, owner=owner,
        searchText="", resgroupId="", sortOrder="", sortField="",
        alarmTime="", solId="", nodeTag="", bizId="",
        connectionRegionId="", connectionType="", connections="",
        baseLineId="", priorityList="", scheIntervalList="",
        diResGroupIdentifier="", diSrcType="", diSrcDatasource="",
        diDstType="", diDstDatasource="", flowId="", alarmId="",
        advanceSort="", pageNum=1, pageSize=500,
        **date_params,
    )
    if not isinstance(items, list):
        items = [items] if items else []

    if not items:
        print(f"{_TAG} ✅ {biz_date} 没有失败实例，无需重跑")
        save_tool_result("rerun_failed_instances", {
            "status": "empty", "project_id": project_id, "bizdate": str(biz_date),
        })
        return

    # 按 nodeId 去重（一个 node 可能有多个失败实例，补数据补一次即可）
    by_node = {}
    for item in items:
        nid = str(item.get("nodeId") or "")
        if not nid:
            continue
        if nid not in by_node:
            by_node[nid] = {
                "nodeId": nid,
                "nodeName": item.get("nodeName") or "",
                "owner": item.get("ownerName") or item.get("owner") or "",
                "count": 1,
            }
        else:
            by_node[nid]["count"] += 1

    nodes = sorted(by_node.values(), key=lambda x: (x["owner"], x["nodeName"]))

    print(f"{_TAG} ⚠️ 待确认：批量补数据重跑 {len(nodes)} 个节点（bizdate={biz_date}）")
    print(f"  projectId: {project_id}")
    print(f"  方式: supplementAsync（每个 nodeId 单独提交一次）")
    print()
    print(f"  {'nodeId':<14} {'节点名':<32} {'负责人':<12} {'失败实例数':<8}")
    print(f"  {'─'*14} {'─'*32} {'─'*12} {'─'*8}")
    for n in nodes:
        print(f"  {n['nodeId']:<14} {n['nodeName'][:32]:<32} {n['owner'][:12]:<12} {n['count']:<8}")

    pending = {
        "project_id": project_id,
        "bizdate": biz_date.strftime("%Y-%m-%d"),
        "nodes": nodes,
        "created_at": datetime.now().isoformat(),
    }
    pending_path = _PENDING_FILE
    os.makedirs(os.path.dirname(pending_path), exist_ok=True)
    with open(pending_path, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

    print()
    print(f"  → 用户确认后执行: python rerun_failed_instances.py --confirm")


def confirm_and_rerun():
    pending_path = _PENDING_FILE
    if not os.path.exists(pending_path):
        print(f"{_TAG} 没有待确认的重跑操作。请先运行: python rerun_failed_instances.py --project-id <id>")
        sys.exit(1)

    with open(pending_path, "r", encoding="utf-8") as f:
        pending = json.load(f)

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

    client = BFFClient(quiet=True)
    project_id = pending["project_id"]
    bizdate = pending["bizdate"]  # YYYY-MM-DD
    nodes = pending["nodes"]

    submitted, failed = [], []
    for n in nodes:
        task_id = n["nodeId"]
        now = datetime.now()
        name = f"P_rerun_{task_id}_{now.strftime('%Y%m%d%H%M%S')}"
        body = {
            "env": "prod",
            "excludeNodeIds": [],
            "includeNodeIds": [task_id],
            "isParallel": False,
            "multipleTimePeriods": json.dumps([{"bizBeginTime": bizdate, "bizEndTime": bizdate}]),
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
        try:
            result = _api_call(client, "supplementAsync", **body)
        except Exception as e:
            failed.append({"nodeId": task_id, "nodeName": n.get("nodeName",""), "error": str(e)[:120]})
            print(f"{_TAG} ❌ {task_id} {n.get('nodeName','')}: {e}")
            continue

        if isinstance(result, dict):
            request_ids = result.get("requestIds") or result.get("requestId") or result.get("data")
        elif isinstance(result, str):
            request_ids = result
        else:
            request_ids = str(result) if result else None

        if not request_ids:
            failed.append({"nodeId": task_id, "nodeName": n.get("nodeName",""), "error": "未获取到 requestIds"})
            print(f"{_TAG} ❌ {task_id} {n.get('nodeName','')}: 未获取到 requestIds")
            continue

        add_backlog(
            type_name="backfill",
            label=f"批量重跑 task={task_id} {n.get('nodeName','')} bizdate={bizdate}",
            check={
                "api": "getSupplementAsyncResult",
                "params": {"env": "prod", "projectId": project_id, "requestIds": request_ids},
                "result_is_list": True,
                "status_field": "status",
                "terminal": {"6": "成功", "5": "失败"},
                "pending": {"1": "未运行", "4": "运行中"},
            },
            context={"project_id": project_id, "task_id": task_id, "source": "rerun_failed_instances"},
            on_success="补数据重跑完成",
        )
        submitted.append({"nodeId": task_id, "requestIds": request_ids})
        print(f"{_TAG} ✅ {task_id} {n.get('nodeName','')} | requestIds={request_ids}")

    print()
    print(f"{_TAG} 汇总: 提交成功 {len(submitted)} / 失败 {len(failed)} / 共 {len(nodes)}")
    if submitted:
        print(f"{_TAG} → 已加入异步任务列表，查看进度: python check_backlogs.py")

    save_tool_result("rerun_failed_instances", {
        "status": "submitted" if submitted else "fail",
        "project_id": project_id,
        "bizdate": bizdate,
        "submitted_count": len(submitted),
        "failed_count": len(failed),
        "submitted": submitted,
        "failed": failed,
    })


def main():
    parser = argparse.ArgumentParser(
        description="批量重跑失败实例（补数据方式）",
        usage="%(prog)s --project-id <id> [--date YYYY-MM-DD] [--owner me] [--task-type ODPS_SQL] | %(prog)s --confirm",
    )
    parser.add_argument("--confirm", action="store_true", help="执行已确认的重跑操作（Phase 2）")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--project-name", help="工作空间名（二选一）")
    parser.add_argument("--date", help="业务日期 YYYY-MM-DD，默认昨天")
    parser.add_argument("--owner", help="负责人（me 或 baseId）")
    parser.add_argument("--task-type", help="任务类型过滤，如 ODPS_SQL")

    args = parser.parse_args()

    telemetry_start("rerun_failed_instances.py", module="task-ops",
                    project_id=args.project_id)

    if args.confirm:
        confirm_and_rerun()
        telemetry_end(result={"action": "confirm"})
    elif args.project_id or args.project_name:
        prepare_rerun(args)
        telemetry_end(result={"action": "prepare"})
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("rerun_failed_instances.py", "task-ops",
                       e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("rerun_failed_instances.py", "task-ops", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
