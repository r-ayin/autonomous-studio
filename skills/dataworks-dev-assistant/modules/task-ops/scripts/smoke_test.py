#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
冒烟测试工具 —— 在开发环境运行节点，验证代码逻辑正确性

用法:
    python smoke_test.py --project-id 23304 --task-id 307889927
    python smoke_test.py --project-id 23304 --task-id 307889927 --bizdate 2026-03-26
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

from bff_client import BFFClient, save_tool_result, add_backlog
from telemetry import telemetry_start, telemetry_end, telemetry_fail


# ─── 常量 ──────────────────────────────────────────────────────

_TAG = "[smoke]"
_POLL_INTERVAL = 10   # 轮询间隔（秒）
_POLL_TIMEOUT = 100   # 轮询超时（秒）— 必须 < harness 120s 限制，留余量给 backlog 写入
_POLL_INITIAL_WAIT = 5  # 提交后等待实例创建（秒）

# getInstanceList 实例状态分类（权威源）
_FAIL_STATUSES = frozenset({"5"})
_SUCCESS_STATUSES = frozenset({"6"})
_RUNNING_STATUSES = frozenset({"0", "1", "2", "3", "4"})


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


# ─── 轮询逻辑 ─────────────────────────────────────────────────

def _get_instance_task_ids(client, project_id, dag_id, tenant_id):
    """从 getInstanceList 获取 DAG 内所有实例的 taskId"""
    try:
        items = _api_call(client, "getInstanceList",
                          projectId=project_id, env="dev", tenantId=tenant_id,
                          dagType=2, dagId=dag_id, pageNum=1, pageSize=100)
    except Exception as e:
        print(f"{_TAG} getInstanceList 失败: {e}", file=sys.stderr)
        return []

    # return_structure=data.data[] → 直接返回实例列表
    if not isinstance(items, list):
        items = [items] if items else []

    instances = []
    for item in items:
        if isinstance(item, dict) and item.get("taskId"):
            instances.append((str(item["taskId"]), item.get("nodeName", "")))
    return instances


def _get_failure_log(client, project_id, inst_task_id, tenant_id):
    """获取失败实例的运行日志内容"""
    try:
        log = _api_call(client, "getInstanceRunLog",
                        projectId=project_id, env="dev", tenantId=tenant_id,
                        taskId=inst_task_id, historyId=0)
        if isinstance(log, dict):
            return log.get("data") or log.get("content") or str(log)
        return str(log) if log else ""
    except Exception as e:
        return f"获取日志失败: {e}"


def _poll_instance_list(client, project_id, dag_id, tenant_id):
    """通过 getInstanceList 查询所有实例的最新状态。

    Returns:
        list[dict]: 实例列表，每个含 taskId/status/statusName/nodeName
        None: 查询失败
    """
    try:
        items = _api_call(client, "getInstanceList",
                          projectId=project_id, env="dev", tenantId=tenant_id,
                          dagType=2, dagId=dag_id, pageNum=1, pageSize=100)
    except Exception as e:
        print(f"{_TAG} getInstanceList 查询失败: {e}", file=sys.stderr)
        return None

    if not isinstance(items, list):
        items = [items] if items else []
    return items


def _poll_smoke_result(client, project_id, dag_id, task_id, tenant_id):
    """轮询冒烟测试结果（通过 getInstanceList 轮询实例状态）。

    Returns:
        ("success", None)                        — 全部成功
        ("failed", (inst_task_id, node_name, log)) — 有实例失败
        ("timeout", None)                        — 超时
    """
    time.sleep(_POLL_INITIAL_WAIT)

    # 首次查询确认实例已创建
    items = _poll_instance_list(client, project_id, dag_id, tenant_id)
    if not items:
        print(f"{_TAG} ⚠️ 未获取到实例列表，跳过轮询")
        return "timeout", None

    print(f"{_TAG} 发现 {len(items)} 个实例，开始轮询（超时 {_POLL_TIMEOUT}s）...")

    start_time = time.time()
    poll_count = 0

    while time.time() - start_time < _POLL_TIMEOUT:
        poll_count += 1

        # 每轮重新查询 getInstanceList 获取最新状态
        items = _poll_instance_list(client, project_id, dag_id, tenant_id)
        if items is None:
            # 查询失败，跳过本轮继续
            elapsed = int(time.time() - start_time)
            print(f"{_TAG} 轮询 #{poll_count} | 已等待 {elapsed}s（查询失败，重试）...")
            time.sleep(_POLL_INTERVAL)
            continue

        all_success = True
        status_summary = []

        for item in items:
            inst_task_id = str(item.get("taskId", ""))
            node_name = item.get("nodeName", "")
            status = str(item.get("status", ""))
            status_name = item.get("statusName", status)

            if status in _FAIL_STATUSES:
                print(f"{_TAG} ❌ 实例 {node_name}(taskId={inst_task_id}) {status_name}")
                log = _get_failure_log(client, project_id, inst_task_id, tenant_id)
                return "failed", (inst_task_id, node_name, log)
            elif status in _SUCCESS_STATUSES:
                status_summary.append(f"{node_name}=成功")
            else:
                all_success = False
                status_summary.append(f"{node_name}={status_name}")

        if all_success:
            return "success", None

        elapsed = int(time.time() - start_time)
        summary = ", ".join(status_summary) if len(items) <= 3 else f"{len(items)} 个实例"
        print(f"{_TAG} 轮询 #{poll_count} | 已等待 {elapsed}s | {summary}")
        time.sleep(_POLL_INTERVAL)

    return "timeout", None


# ─── 执行冒烟测试 ─────────────────────────────────────────────

def run_smoke(project_id, task_id, bizdate, tenant_id=1):
    """提交冒烟测试 + 轮询结果"""
    now = datetime.now()
    name = f"P_smoke_{task_id}_{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}"

    client = BFFClient(quiet=True)

    # 构造请求体
    body = {
        "projectId": project_id,
        "env": "dev",
        "tenantId": tenant_id,
        "nodeId": task_id,
        "name": name,
        "bizdate": bizdate,
        "isDryRun": True,
    }

    # 调用 smoke API
    print(f"{_TAG} 提交冒烟测试 | taskId={task_id} | bizdate={bizdate}")
    try:
        result = _api_call(client, "smoke", **body)
    except Exception as e:
        print(f"{_TAG} ❌ 冒烟测试请求失败: {e}")
        save_tool_result("smoke", {
            "summary": f"冒烟测试失败: {e}",
            "status": "fail",
        })
        sys.exit(1)

    # 提取 dagId（smoke API 返回 data=dagId）
    if isinstance(result, dict):
        dag_id = result.get("dagId") or result.get("data")
    elif isinstance(result, (int, float)):
        dag_id = int(result)
    else:
        dag_id = result

    print(f"{_TAG} ✅ 已提交 | dagId={dag_id}")

    # 轮询等待结果
    result_status, result_data = _poll_smoke_result(client, project_id, dag_id, task_id, tenant_id)

    if result_status == "success":
        print(f"{_TAG} ✅ 冒烟测试通过，节点代码逻辑正确。可继续发布到生产环境")
        save_tool_result("smoke", {
            "summary": "冒烟测试通过",
            "status": "success",
            "project_id": project_id,
            "task_id": task_id,
            "dag_id": dag_id,
            "bizdate": bizdate,
        })
        return

    if result_status == "failed":
        inst_task_id, node_name, log = result_data
        print(f"{_TAG} ❌ 冒烟测试失败 | 实例 {node_name}(taskId={inst_task_id})")
        if log:
            print(f"--- 失败日志 ({node_name}) ---")
            print(log)
            print(f"--- 日志结束 ---")
        # 日志可能不完整（如只有环境变量没有实际错误），给出诊断命令
        core_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "core"))
        print(f"{_TAG} 若日志不完整，获取完整运行日志:")
        print(f"  PYTHONPATH={core_dir} python -c \"from bff_client import BFFClient; c = BFFClient(); c.load('getInstanceRunLog', projectId={project_id}, env='dev', tenantId={tenant_id}, taskId={inst_task_id}, historyId=0)\"")
        save_tool_result("smoke", {
            "summary": f"冒烟测试失败: {node_name}",
            "status": "failed",
            "project_id": project_id,
            "task_id": task_id,
            "dag_id": dag_id,
            "bizdate": bizdate,
            "failed_task_id": inst_task_id,
            "failed_node_name": node_name,
        })
        sys.exit(1)

    # timeout → 加入异步任务列表
    print(f"{_TAG} ⏳ 轮询超时（{_POLL_TIMEOUT}s），加入异步任务列表")
    add_backlog(
        type_name="smoke",
        label=f"冒烟测试 taskId={task_id} bizdate={bizdate}",
        check={
            "api": "getInstanceList",
            "params": {
                "projectId": project_id,
                "env": "dev",
                "tenantId": tenant_id,
                "dagType": 2,
                "dagId": dag_id,
                "pageNum": 1,
                "pageSize": 100,
            },
            "result_is_list": True,
            "fail_fast": True,
            "status_field": "status",
            "terminal": {"6": "成功", "5": "失败"},
            "pending": {"0": "未运行", "1": "未运行", "2": "等待时间", "3": "等待资源", "4": "运行中"},
        },
        context={"project_id": project_id, "task_id": task_id, "dag_id": dag_id},
        on_success="冒烟测试通过，节点代码逻辑正确。可继续发布到生产环境",
        on_fail="冒烟测试失败，根据上方日志命令查看具体错误原因",
    )
    print(f"{_TAG} → 已加入异步任务列表，查看进度: python check_backlogs.py")

    save_tool_result("smoke", {
        "summary": f"冒烟测试轮询超时，已加入异步任务列表 | taskId={task_id} | dagId={dag_id}",
        "status": "submitted",
        "project_id": project_id,
        "task_id": task_id,
        "dag_id": dag_id,
        "bizdate": bizdate,
    })


# ─── CLI 入口 ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="冒烟测试工具 — 在开发环境运行节点验证代码逻辑",
        usage="%(prog)s --project-id <id> --task-id <taskId> [--bizdate YYYY-MM-DD]",
    )
    parser.add_argument("--project-id", type=int, required=True,
                        help="工作空间 ID")
    parser.add_argument("--task-id", type=int, required=True,
                        help="节点 ID")
    parser.add_argument("--bizdate",
                        help="业务日期（YYYY-MM-DD，默认昨天）")
    parser.add_argument("--tenant-id", type=int, default=1,
                        help="租户 ID（默认 1）")

    args = parser.parse_args()

    telemetry_start("smoke_test.py", module="task-ops", project_id=args.project_id)

    # 默认业务日期：昨天
    if args.bizdate:
        if len(args.bizdate) == 10:
            now = datetime.now()
            bizdate = f"{args.bizdate} {now.strftime('%H:%M:%S')} 00:00:00"
        else:
            bizdate = args.bizdate
    else:
        now = datetime.now()
        yesterday = (now.date() - timedelta(days=1))
        bizdate = f"{yesterday.strftime('%Y-%m-%d')} {now.strftime('%H:%M:%S')} 00:00:00"

    run_smoke(args.project_id, args.task_id, bizdate, args.tenant_id)
    telemetry_end(result={"task_id": args.task_id})


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("smoke_test.py", "task-ops", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("smoke_test.py", "task-ops", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
