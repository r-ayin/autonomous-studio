#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点代码获取工具 —— 根据节点 ID 获取开发态或运行态代码

用法:
    python find_node_code.py --project-id <id> --entity-id <entityId>            # 开发态代码
    python find_node_code.py --project-id <id> --task-id <taskId> --runtime      # 运行态代码（默认 prod）
    python find_node_code.py --project-id <id> --task-id <taskId> --runtime --env dev

ID 说明:
    --entity-id: 开发态 UUID，用于 /ide/ 系列 API（getContentByNodeId）
    --task-id:   运行态任务 ID，用于 /workbench/ 系列 API（getNodeCode）
    search_nodes.py 输出的 taskId 直接传给 --task-id

功能:
    根据 projectId + ID 获取节点代码:
    - 开发态（默认）: getContentByNodeId(nodeId=entityId) — IDE 中正在编辑的版本
    - 运行态（--runtime）: getNodeCode(nodeId=taskId) — 已发布到调度系统的版本

输出:
    直接输出代码内容到 stdout
"""

import sys
import os
import argparse

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail


def get_node_code(client, project_id, node, runtime=False, env="prod"):
    """获取单个节点的代码。

    runtime=False: 使用 getContentByNodeId(nodeId=entityId)
    runtime=True:  使用 getNodeCode(nodeId=taskId)

    Args:
        client: BFFClient 实例
        project_id: 项目 ID
        node: dict，可包含 entityId 和/或 taskId
        runtime: 是否获取运行态代码
        env: 运行态环境（prod/dev）

    Returns:
        (code_str, error_str): code_str 非空表示成功，error_str 非空表示失败
    """
    try:
        if runtime:
            return _get_runtime_code(client, project_id, node, env)
        else:
            return _get_dev_code(client, project_id, node)
    except Exception as e:
        return None, str(e)


def _resolve_ids(client, project_id, node):
    """通过 node_profile.resolve 补全 entityId ↔ taskId 双向映射"""
    from node_profile import resolve
    try:
        profile = resolve(int(project_id), client,
                          task_id=int(node["taskId"]) if node.get("taskId") else None,
                          entity_id=node.get("entityId"))
        if profile:
            if profile.get("entity_id") and not node.get("entityId"):
                node["entityId"] = str(profile["entity_id"])
            if profile.get("task_id") and not node.get("taskId"):
                node["taskId"] = str(profile["task_id"])
    except Exception:
        pass


def _get_dev_code(client, project_id, node):
    """开发态代码：getContentByNodeId(nodeId=entityId)

    如果只有 taskId 没有 entityId，通过 resolve 自动反查。
    """
    entity_id = node.get("entityId")

    if not entity_id and node.get("taskId"):
        _resolve_ids(client, project_id, node)
        entity_id = node.get("entityId")

    if not entity_id:
        return None, "缺少 entityId，无法获取开发态代码；请改用 --runtime --task-id <taskId>"

    try:
        result = client.load("getContentByNodeId", projectId=str(project_id),
                            nodeId=entity_id)
        if isinstance(result, dict):
            return result.get("content", str(result)), None
        return result, None
    except Exception as e:
        return None, str(e)


def _get_runtime_code(client, project_id, node, env):
    """运行态代码：getNodeCode(nodeId=taskId)

    workbench API 的 nodeId 就是 taskId。
    如果只有 entityId，通过 resolve 自动补全 taskId。
    """
    task_id = node.get("taskId")

    if not task_id and node.get("entityId"):
        _resolve_ids(client, project_id, node)
        task_id = node.get("taskId")

    if not task_id:
        return None, "缺少 taskId 和 entityId，无法获取运行态代码"

    try:
        result = client.load("getNodeCode", projectId=int(project_id),
                            env=env, nodeId=str(task_id))
        if isinstance(result, dict):
            return result.get("code", str(result)), None
        return result, None
    except Exception as e:
        # 权限错误直接返回
        err_msg = str(e)
        if any(kw in err_msg for kw in ("没有权限", "403", "Forbidden")):
            return None, err_msg
        return None, err_msg


def main():
    parser = argparse.ArgumentParser(
        description="节点代码获取工具 — 根据节点 ID 获取开发态或运行态代码",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project-id", required=True, help="项目 ID（projectId）")
    parser.add_argument("--entity-id", help="开发态节点 UUID（entityId），用于 getContentByNodeId")
    parser.add_argument("--task-id", help="运行态任务 ID（taskId），用于 getNodeCode")
    # 兼容旧参数 --node-id：运行态当 taskId，开发态当 entityId
    parser.add_argument("--node-id", help=argparse.SUPPRESS)
    parser.add_argument("--runtime", action="store_true",
                        help="获取运行态代码（已发布到调度系统的版本），默认获取开发态代码")
    parser.add_argument("--env", default="prod", choices=["prod", "dev"],
                        help="运行态环境（默认 prod），仅 --runtime 时生效")
    args = parser.parse_args()

    # 参数解析：明确 entityId 和 taskId
    entity_id = args.entity_id
    task_id = args.task_id

    # 兼容旧的 --node-id：根据模式推断
    if args.node_id:
        if args.runtime and not task_id:
            task_id = args.node_id
        elif not args.runtime and not entity_id:
            entity_id = args.node_id

    if not entity_id and not task_id:
        parser.error("需要至少指定 --entity-id 或 --task-id（或旧参数 --node-id）")

    node = {"projectId": args.project_id}
    if entity_id:
        node["entityId"] = entity_id
    if task_id:
        node["taskId"] = task_id

    id_label = f"taskId={task_id}" if task_id else f"entityId={entity_id}"
    telemetry_start("find_node_code.py", module="node-management",
                    project_id=args.project_id, node_id=task_id or entity_id)

    client = BFFClient(quiet=True)

    code_mode = f"运行态-{args.env}" if args.runtime else "开发态"
    print(f"获取节点代码（{code_mode}）: projectId={args.project_id}, {id_label}")

    code, err = get_node_code(client, int(args.project_id), node,
                              runtime=args.runtime, env=args.env)
    if err:
        print(f"[获取失败] {err}", file=sys.stderr)
        if any(kw in err for kw in ("没有权限", "403", "Forbidden")):
            print(f"当前用户无此项目的访问权限，无法获取节点代码")
        print(f"→ 可尝试通过血缘查看上下游关系: query_lineage.py --project-id {args.project_id}")
        telemetry_fail("find_node_code.py", module="node-management", exit_code=1, error=err)
        sys.exit(1)
    elif code:
        print(code)
        telemetry_end(result={"code_mode": code_mode, "code_length": len(code)})
        save_tool_result("find_node_code", {
            "project_id": args.project_id,
            "entity_id": entity_id,
            "task_id": task_id,
            "code_mode": code_mode,
            "code": code,
        })
    else:
        print("(无代码)")
        telemetry_end(result={"code_mode": code_mode, "code_length": 0})


if __name__ == "__main__":
    main()
