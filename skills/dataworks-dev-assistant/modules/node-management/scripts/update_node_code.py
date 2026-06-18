#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点代码更新工具 —— 将本地文件内容更新到 DataWorks 开发态节点

用法：
    python update_node_code.py --project-id 21375 --entity-id <entityId> --file path/to/code.sql
    python update_node_code.py --project-id 21375 --task-id <taskId> --file path/to/code.sql
    # 只设置调度参数（不改代码）
    python update_node_code.py --project-id 21375 --entity-id <entityId> --param "bizdate=$[yyyymmdd-1]"
    # 同时改代码和调度参数
    python update_node_code.py --project-id 21375 --entity-id <entityId> --file code.sql --param "bizdate=$[yyyymmdd-1]"

说明：
    --entity-id: 开发态 UUID（getNode 的 uuid / identify.py 输出的 entityId）
    --task-id:   运行态任务 ID（自动通过 node_profile 反查 entityId）
    --file:      本地代码文件路径，内容将完整替换节点 script.content（与 --param 互相独立，可单独用）
    --param:     设置调度参数，格式 key=value（如 bizdate=$[yyyymmdd-1]），可多次。
                 走 updateNode API 的 script.parameters 字段，已验证有效。
                 ⚠️ 不要用 update_vertex.py 设置参数（updateVertex 对 script.parameters 有服务端 bug）

注意：
    - 更新后需配合 deploy_node.py 发布到开发/生产环境
    - 不改动依赖等其他配置（全量 spec 读取后只改指定字段）
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail

_TAG = "[update_node_code]"


def _resolve_entity_id(client, project_id: int, task_id: str) -> str:
    """通过 task_id 反查 entity_id"""
    from node_profile import resolve
    profile = resolve(project_id, client, task_id=int(task_id))
    if profile and profile.get("entity_id"):
        return str(profile["entity_id"])
    raise ValueError(f"无法通过 taskId={task_id} 反查 entityId，请直接传 --entity-id")


def _get_full_spec(endpoint: str, token: str, session_code: str, project_id: int, entity_id: str) -> dict:
    """读取节点完整 spec（JSON 字符串），返回解析后的 dict"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": f"http://{session_code}.qwen.cli",
    }
    resp = requests.post(
        f"{endpoint}/dataworks_public_v2024-05-18/getNode",
        headers=headers,
        data={"projectId": project_id, "uuid": entity_id},
    )
    body = resp.json()
    if body.get("code") != 200:
        raise RuntimeError(f"getNode 失败: {body}")
    spec_str = body.get("data", {}).get("spec")
    if not spec_str:
        raise RuntimeError(f"getNode 返回的 spec 为空: {body}")
    return json.loads(spec_str)


def _update_node_spec(endpoint: str, token: str, session_code: str, project_id: int,
                      entity_id: str, spec: dict) -> None:
    """将修改后的完整 spec 写回节点"""
    spec_str = json.dumps(spec, ensure_ascii=False)
    params = {"projectId": project_id, "uuid": entity_id, "spec": spec_str}
    confirmed = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": f"http://{session_code}.qwen.cli",
        "X-User-Confirmed": confirmed,
    }
    resp = requests.post(
        f"{endpoint}/dataworks_public_v2024-05-18/updateNode",
        headers=headers,
        data=params,
    )
    body = resp.json()
    if body.get("code") != 200 or body.get("data") is not True:
        raise RuntimeError(f"updateNode 失败: {body}")


def update(project_id: int, entity_id: str, file_path: str | None,
           params: list[str] | None = None) -> None:
    client = BFFClient(quiet=True)
    endpoint = client.endpoint
    token = client.token
    session_code = client.session_code

    print(f"{_TAG} 读取节点 spec: projectId={project_id}, entityId={entity_id}")
    spec = _get_full_spec(endpoint, token, session_code, project_id, entity_id)

    nodes = spec.get("spec", {}).get("nodes", [])
    if not nodes:
        raise RuntimeError("spec.nodes 为空，无法定位节点")

    changed = []
    if file_path:
        new_code = Path(file_path).read_text(encoding="utf-8")
        nodes[0]["script"]["content"] = new_code
        changed.append(f"content ({len(new_code)} 字节)")

    if params:
        # 构建 DataWorks spec 的 parameters 对象数组格式（必须是 array，不能是字符串）
        param_list = []
        for kv in params:
            if "=" not in kv:
                raise ValueError(f"--param 格式错误，应为 key=value，got: {kv!r}")
            k, v = kv.split("=", 1)
            param_list.append({
                "artifactType": "Variable",
                "name": k.strip(),
                "scope": "NodeParameter",
                "type": "System",
                "value": v.strip(),
            })
        nodes[0]["script"]["parameters"] = param_list
        names = [p["name"] for p in param_list]
        changed.append(f"parameters ({', '.join(names)})")

    if not changed:
        print(f"{_TAG} ❌ 至少指定 --file 或 --param", file=sys.stderr)
        sys.exit(1)

    print(f"{_TAG} 更新字段: {', '.join(changed)}")
    _update_node_spec(endpoint, token, session_code, project_id, entity_id, spec)

    print(f"{_TAG} ✅ 节点更新成功")
    print(f"\n下一步：")
    print(f"  · 发布上线: python deploy_node.py --project-id {project_id} --uuid {entity_id}")

    telemetry_end(result={"status": "success", "entity_id": entity_id, "changed": changed})
    save_tool_result("update_node_code", {
        "summary": f"已更新节点: entityId={entity_id}, 改动={changed}",
        "status": "success",
        "project_id": project_id,
        "entity_id": entity_id,
        "file": file_path,
        "params": params,
    })


def main():
    parser = argparse.ArgumentParser(description="将本地文件内容更新到 DataWorks 开发态节点代码")
    parser.add_argument("--project-id", type=int, required=True, help="工作空间 ID")
    parser.add_argument("--entity-id", help="开发态节点 UUID（entityId）")
    parser.add_argument("--task-id", help="运行态任务 ID，自动反查 entityId")
    parser.add_argument("--file", help="本地代码文件路径（替换 script.content）")
    parser.add_argument("--param", action="append", default=[], metavar="key=value",
                        help="设置调度参数，如 'bizdate=$[yyyymmdd-1]'，可多次。"
                             "走 updateNode script.parameters，已验证有效")
    args = parser.parse_args()

    if not args.entity_id and not args.task_id:
        parser.error("需要至少指定 --entity-id 或 --task-id")
    if not args.file and not args.param:
        parser.error("需要至少指定 --file 或 --param")

    telemetry_start("update_node_code.py", module="node-management",
                    project_id=args.project_id,
                    entity_id=args.entity_id, task_id=args.task_id,
                    file=args.file, params=args.param)

    entity_id = args.entity_id
    if not entity_id:
        client = BFFClient(quiet=True)
        print(f"{_TAG} 通过 taskId={args.task_id} 反查 entityId ...")
        entity_id = _resolve_entity_id(client, args.project_id, args.task_id)
        print(f"{_TAG} entityId={entity_id}")

    update(
        project_id=args.project_id,
        entity_id=entity_id,
        file_path=args.file,
        params=args.param or None,
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("update_node_code.py", "node-management",
                       e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("update_node_code.py", "node-management", 1, error=str(e)[:100])
        print(f"\n{_TAG} [error] {e}", file=sys.stderr)
        sys.exit(1)
