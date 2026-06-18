#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DI 节点创建工具

读取 build_di_spec.py 保存的 pending 配置，创建 DI 节点。

用法：
    # 用户确认后创建节点
    python create_di_node.py --project-id 22153 --task-name users_20260402
"""

import json
import os
import sys
from typing import Optional

from bff_client import BFFClient, save_tool_result
from runtime import print_confirmed_params, remember
from telemetry import telemetry_start, telemetry_end, telemetry_fail

_PENDING_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "pending_di_sync_job.json")
_TAG = "[create_di_node]"


def create(project_id: Optional[int] = None,
           task_name: Optional[str] = None) -> None:
    print_confirmed_params()
    path = _PENDING_FILE
    if not os.path.exists(path):
        print(f"{_TAG} 没有待创建的配置。请先运行 build_di_spec.py 生成配置。")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        pending = json.load(f)

    project_id = project_id or pending["project_id"]
    task_name = task_name or pending["task_name"]
    content = json.dumps(pending["config"], ensure_ascii=False)

    print(f"{_TAG} 正在创建节点: {task_name}")
    print(f"{_TAG}   projectId: {project_id}")

    client = BFFClient(quiet=True)
    client.write("createNodeSimple", _caller_confirmed=True,
                 projectId=project_id, scene="DATAWORKS_PROJECT",
                 command="DI", name=task_name, content=content)
    result = client.confirm_write()

    node_id = None
    if isinstance(result, dict):
        node_id = result.get("uuid") or result.get("nodeId") or result.get("id")
    elif isinstance(result, (int, str)):
        node_id = result

    # 确认成功后再删除 pending 文件
    os.remove(path)

    print(f"{_TAG} ✅ 节点创建成功")
    if node_id:
        print(f"{_TAG}   nodeId(uuid): {node_id}")
    print(f"{_TAG}   任务名称: {task_name}")
    print(f"\n下一步: 如需发布，使用 deploy_node.py --project-id {project_id} --uuid {node_id}")

    telemetry_end(result={"status": "success", "node_id": node_id})
    save_tool_result("create_di_node", {
        "summary": f"节点已创建: {task_name}", "status": "success",
        "project_id": project_id, "task_name": task_name, "node_id": node_id,
    })
    # 累积参数（agent 注意力辅助层）。末步成功后参数仍保留，
    # 供后续相关查询/操作复用，session 切换时自动清理
    if node_id:
        remember(node_uuid=node_id)


def _check_resolve_guard():
    """入口守卫：检查是否已执行 resolve_sync_datasource"""
    import os
    result_path = os.path.join(os.path.expanduser("~"), ".dataworks", "resolve_sync_datasource_result.json")
    if not os.path.exists(result_path):
        print("[create_di_node] 请先执行 resolve_sync_datasource.py 解析数据源。")
        print("  → resolve_sync_datasource.py --project-name <工作空间> --src-type <源类型> --dst-type <目标类型> --src-table <表名>")
        print("  五步流程不可跳步：① resolve → ② probe_table → ③ build_di_spec → ④ ensure_target_table → ⑤ create_di_node")
        import sys
        sys.exit(1)


def main():
    _check_resolve_guard()
    import argparse
    parser = argparse.ArgumentParser(description="DI 节点创建")
    parser.add_argument("--project-id", type=int, help="工作空间 ID（默认从 pending 文件读取）")
    parser.add_argument("--task-name", "--name", dest="task_name", help="任务名称（默认从 pending 文件读取）")
    args = parser.parse_args()

    telemetry_start("create_di_node.py", module="data-integration", project_id=args.project_id)

    create(args.project_id, args.task_name)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("create_di_node.py", "data-integration", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("create_di_node.py", "data-integration", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
