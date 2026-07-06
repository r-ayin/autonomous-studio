#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点依赖管理工具 —— 查看 / 添加 / 移除开发态节点的上游依赖

用法：
    # 查看当前依赖
    python manage_node_deps.py --project-id 22398 --uuid <nodeUuid>

    # 添加普通依赖（同工作空间节点，传 UUID）
    python manage_node_deps.py --project-id 22398 --uuid <nodeUuid> --add <upstreamUuid>

    # 添加跨周期依赖（传 output 字符串，如跨项目的 output 名）
    python manage_node_deps.py --project-id 22398 --uuid <nodeUuid> \
        --add alimonitor_report.dws_sunfire_ai_trace_hf \
        --type CrossCycleDependsOnOtherNode

    # 移除依赖
    python manage_node_deps.py --project-id 22398 --uuid <nodeUuid> --remove <upstreamUuid>

说明：
    --uuid      当前节点的 UUID（开发态 entityId，来自 identify.py 输出）
    --add       上游节点的 UUID 或 output 字符串，可多次。
                · 纯数字 UUID → 自动解析为节点的默认 output 名（仅限同工作空间）
                · 其他字符串 → 直接作为 output 名传给 API
                  跨工作空间格式：project_name.node_name（如 alimonitor_report.dws_sunfire_ai_trace_hf）
    --remove    上游节点的 UUID 或 output 字符串，可多次（同 --add 格式）
    --type      依赖类型，默认 Normal（跨周期用 CrossCycleDependsOnOtherNode）

注意：
    - UUID 方式仅适用于同工作空间节点；跨工作空间请用 output 字符串（project.node_name）
    - 不影响代码和调度参数，仅操作依赖关系
    - 依赖增删是节点拓扑变更（DAG 边），属敏感写操作，走两阶段确认：
      不带 --confirm 时仅预览计划改动后退出（Phase 1）；
      带 --confirm 才执行写操作并落审计记录（Phase 2）。
"""

import argparse
import os
import sys
import uuid

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)

from audit_log import record as _audit_record
from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail

_TAG = "[manage_node_deps]"


def _headers(c: BFFClient) -> dict:
    return {
        "Authorization": f"Bearer {c.token}",
        "accept": "application/json",
        "content-type": "application/json",
        "Referer": f"http://{c.session_code}.qwen.cli",
    }


def _audit_write(c: BFFClient, api_name: str, params_summary: str, result_code, correlation_id: str) -> None:
    """落审计记录（与 bff_client._do_request 同源的 audit_log.record，使写操作不再 silent）。

    addNodeDependencies/removeNodeDependencies 的请求形是 query-params+json-body / query-params+DELETE，
    bff_client._do_request 的单 params_type 模型无法表达该混合形，故保留原 requests 直发，
    但在此补审计埋点（DO B：外部调用/写操作须可追溯）。--confirm 两阶段门禁保证 sanctioned，
    故 bypass=False。审计写失败永不阻断业务（audit_log.record 内部 except 吞掉）。
    """
    uid = getattr(c, "_cached_base_id", None) or os.getenv("DW_USER_BASE_ID") or "unknown"
    _audit_record(c._work_dir, api_name, params_summary, result_code,
                  user_id=uid, bypass=False, correlation_id=correlation_id, attempt=0)


def list_deps(c: BFFClient, project_id: int, uuid: str) -> list[dict]:
    resp = requests.get(
        f"{c.endpoint}/ide/getNodeDependencies",
        params={"uuid": uuid, "projectId": project_id},
        headers=_headers(c),
    )
    body = resp.json()
    if body.get("code") != 200:
        raise RuntimeError(f"getNodeDependencies 失败: {body}")
    return body.get("data") or []


def _get_node_default_output(c: BFFClient, project_id: int, uuid: str) -> str | None:
    """查询节点的默认 output 名（addNodeDependencies 需要 output 而非 uuid）。
    仅支持同工作空间节点，跨工作空间节点 getNode 无权限，返回 None。"""
    import json as _json
    try:
        headers = {**_headers(c), "Content-Type": "application/x-www-form-urlencoded"}
        resp = requests.post(
            f"{c.endpoint}/dataworks_public_v2024-05-18/getNode",
            headers=headers,
            data={"projectId": project_id, "uuid": uuid},
        )
        body = resp.json()
        if body.get("code") != 200:
            return None
        spec = _json.loads(body.get("data", {}).get("spec") or "{}")
        node_outputs = spec.get("spec", {}).get("nodes", [{}])[0].get("outputs", {}).get("nodeOutputs", [])
        return next((o["data"] for o in node_outputs if o.get("isDefault")), None)
    except Exception:
        return None


def add_dep(c: BFFClient, project_id: int, source_uuid: str, target: str, dep_type: str) -> None:
    # 纯数字视为 UUID，解析出默认 output 名；否则直接用（跨项目 output 字符串）
    if target.isdigit():
        output_name = _get_node_default_output(c, project_id, target)
        if output_name is None:
            raise RuntimeError(
                f"无法解析 uuid={target} 的默认 output 名。\n"
                f"可能原因：节点在其他工作空间（跨工作空间不支持 UUID，需用 output 字符串）或节点无默认 output。\n"
                f"请改用 output 字符串传入，例如：\n"
                f"  同工作空间：--add <project_name>.<node_name>\n"
                f"  跨工作空间：--add <other_project>.<node_name>"
            )
    else:
        output_name = target
    print(f"  上游 output={output_name}")
    corr = str(uuid.uuid4())
    resp = requests.put(
        f"{c.endpoint}/ide/addNodeDependencies",
        params={"uuid": source_uuid, "projectId": project_id},
        headers=_headers(c),
        json={"dependencies": [{"output": output_name, "type": dep_type}]},
    )
    body = resp.json()
    _audit_write(c, "addNodeDependencies",
                 f"uuid={source_uuid},projectId={project_id},output={output_name},type={dep_type}",
                 body.get("code") if isinstance(body, dict) else None, corr)
    if body.get("code") != 200 or not body.get("data"):
        raise RuntimeError(f"addNodeDependencies 失败: {body}")


def remove_dep(c: BFFClient, project_id: int, source_uuid: str, target: str, dep_type: str) -> None:
    # 纯数字视为 UUID 直接传 targetUuid
    # output 字符串先从 getNodeDependencies 查出上游 uuid，再传 targetUuid
    # （直接传 output 参数对 addNodeDependencies 添加的依赖静默失败）
    if target.isdigit():
        target_uuid = target
    else:
        deps = list_deps(c, project_id, source_uuid)
        matched = next((d for d in deps if d.get("output") == target), None)
        if matched is None:
            raise RuntimeError(f"未找到 output={target} 的依赖，当前依赖: {[d.get('output') for d in deps]}")
        target_uuid = matched["uuid"]
        print(f"  output={target} → uuid={target_uuid}")
    params = {"sourceUuid": source_uuid, "projectId": project_id, "targetUuid": target_uuid, "type": dep_type}
    corr = str(uuid.uuid4())
    resp = requests.delete(
        f"{c.endpoint}/ide/removeNodeDependencies",
        params=params,
        headers=_headers(c),
    )
    body = resp.json()
    _audit_write(c, "removeNodeDependencies",
                 f"sourceUuid={source_uuid},projectId={project_id},targetUuid={target_uuid},type={dep_type}",
                 body.get("code") if isinstance(body, dict) else None, corr)
    if body.get("code") != 200 or not body.get("data"):
        raise RuntimeError(f"removeNodeDependencies 失败: {body}")


def print_deps(deps: list[dict], title: str = "当前依赖") -> None:
    print(f"\n{title}（共 {len(deps)} 个）：")
    if not deps:
        print("  （无依赖）")
    for d in deps:
        name = d.get("name") or d.get("uuid", "?")
        uuid = d.get("uuid", "?")
        print(f"  · {name}  uuid={uuid}")


def main():
    parser = argparse.ArgumentParser(description="查看 / 添加 / 移除节点上游依赖")
    parser.add_argument("--project-id", type=int, required=True, help="工作空间 ID")
    parser.add_argument("--uuid", required=True, help="当前节点的开发态 UUID（entityId）")
    parser.add_argument("--add", action="append", default=[], metavar="UUID_OR_OUTPUT",
                        help="上游节点 UUID 或 output 字符串，可多次；纯数字自动解析为 output 名，其他直接透传")
    parser.add_argument("--remove", action="append", default=[], metavar="UUID_OR_OUTPUT",
                        help="上游节点 UUID 或 output 字符串，可多次；格式同 --add")
    parser.add_argument("--type", default="Normal", dest="dep_type",
                        help="依赖类型，默认 Normal")
    parser.add_argument("--confirm", action="store_true",
                        help="两阶段确认 Phase 2：执行写操作。不带 --confirm 时仅预览计划改动后退出（Phase 1）。")
    args = parser.parse_args()

    telemetry_start("manage_node_deps.py", module="node-management",
                    project_id=args.project_id, uuid=args.uuid,
                    add=args.add, remove=args.remove)

    c = BFFClient(quiet=True)

    # 始终先展示当前依赖
    current = list_deps(c, args.project_id, args.uuid)
    print_deps(current, "当前依赖")

    if not args.add and not args.remove:
        telemetry_end(result={"status": "list_only"})
        return

    # 两阶段确认 Phase 1：不带 --confirm 时仅预览计划改动后退出，不执行任何写操作。
    # 依赖增删是节点拓扑变更（DAG 边），属敏感写操作，须经用户显式确认。
    if not args.confirm:
        print(f"\n⚠️ 待确认写操作（节点拓扑变更）:")
        if args.remove:
            print(f"  移除: {', '.join(args.remove)}")
        if args.add:
            print(f"  添加: {', '.join(args.add)}")
        print(f"  当前节点 uuid={args.uuid}, project_id={args.project_id}, dep_type={args.dep_type}")
        print(f"  这是 Phase 1 预览，未执行任何写操作。")
        print(f"  确认无误后请重跑并加 --confirm 执行（Phase 2）。")
        telemetry_end(result={"status": "awaiting_confirm",
                              "add": args.add, "remove": args.remove})
        return

    # 执行移除
    for target in args.remove:
        name = next((d.get("name", target) for d in current if d.get("uuid") == target), target)
        print(f"\n{_TAG} 移除依赖: {name} ({target})")
        remove_dep(c, args.project_id, args.uuid, target, args.dep_type)
        print(f"{_TAG} ✅ 已移除")

    # 执行添加
    for target in args.add:
        print(f"\n{_TAG} 添加依赖: {target}")
        add_dep(c, args.project_id, args.uuid, target, args.dep_type)
        print(f"{_TAG} ✅ 已添加")

    # 显示操作后的依赖
    updated = list_deps(c, args.project_id, args.uuid)
    print_deps(updated, "操作后依赖")
    print(f"\n{_TAG} 依赖数变化: {len(current)} → {len(updated)}")

    result = {
        "status": "success",
        "confirmed": True,
        "project_id": args.project_id,
        "uuid": args.uuid,
        "added": args.add,
        "removed": args.remove,
        "deps_after": [{"name": d.get("name"), "uuid": d.get("uuid")} for d in updated],
    }
    telemetry_end(result=result)
    save_tool_result("manage_node_deps", result)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("manage_node_deps.py", "node-management",
                       e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("manage_node_deps.py", "node-management", 1, error=str(e)[:100])
        print(f"\n{_TAG} [error] {e}", file=sys.stderr)
        sys.exit(1)
