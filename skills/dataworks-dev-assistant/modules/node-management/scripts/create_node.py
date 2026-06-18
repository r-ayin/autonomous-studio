#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点创建工具 —— 按 command 创建开发态节点

用法：
    python create_node.py --project-id 14255 --command ODPS_SQL --name test_demo --content "select 1;"
    python create_node.py --project-id 14255 --command DIDE_SHELL --name my/shell/node --content "echo hi"
    python create_node.py --project-id 14255 --command ODPS_SQL --name demo --content "select 1;" --upstream autotest.test_skyfire_0420

支持范围：
    仅支持 ide_node_types.json 中 verified=true 的 command（约 63 种，覆盖 project 14255 主流节点）。
    未验证的 command 会被拒绝并提示补 canonical baseline 或 traffic 样本。

输出：
    成功后输出新节点 uuid，可作为后续 updateNode / addNodeDependencies / deploy_node 的入参。
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from bff_client import BFFClient, save_tool_result
from runtime import print_confirmed_params, remember
from telemetry import telemetry_start, telemetry_end, telemetry_fail

_TAG = "[create_node]"

# 元数据位置：skill 内 src/core/references/（运行态）
_SCRIPT_DIR = Path(__file__).resolve().parent
# 向上三级（scripts → node-management → modules → src/core/references）
_META_CANDIDATES = [
    _SCRIPT_DIR.parents[2] / "core" / "references" / "ide_node_types.json",    # dev: src/
    _SCRIPT_DIR.parents[0] / "ide_node_types.json",                             # dist: 同目录
    _SCRIPT_DIR.parents[1] / "ide_node_types.json",                             # dist: 模块目录
]


def _load_metadata() -> dict:
    for p in _META_CANDIDATES:
        if p.exists():
            return json.loads(p.read_text())
    raise FileNotFoundError(
        f"{_TAG} 找不到 ide_node_types.json，查找过：\n" +
        "\n".join(f"  - {p}" for p in _META_CANDIDATES)
    )


def _check_command(meta: dict, command: str) -> dict:
    """验证 command 是否在 verified 列表；返回该 command 的元数据"""
    commands = meta.get("commands", {})
    if command not in commands:
        print(f"{_TAG} ❌ command {command!r} 不在 ide_node_types.json（共 {meta['total_commands']} 种已知类型）", file=sys.stderr)
        # 列几个相似的
        similar = [c for c in commands if command.upper()[:4] in c][:5]
        if similar:
            print(f"  相近 command: {', '.join(similar)}", file=sys.stderr)
        sys.exit(1)

    info = commands[command]
    if not info.get("verified"):
        print(f"{_TAG} ❌ command {command!r} 未验证（verified=false）", file=sys.stderr)
        print(f"   sources: {info.get('sources', [])}", file=sys.stderr)
        print(f"   family:  {info.get('family') or '未知'}", file=sys.stderr)
        print(f"   说明:    该节点类型在 project 14255 无 canonical 样本，亦无真实 createPackage 流量佐证", file=sys.stderr)
        print(f"   解决:    1) 换一个有此类节点的 project 重新采样", file=sys.stderr)
        print(f"            2) 在 DataStudio UI 建一个该类型节点 → 录制流量 → 补 ground truth", file=sys.stderr)
        sys.exit(1)
    return info


def create(project_id: int, command: str, name: str, content: Optional[str] = None,
           upstream: Optional[list[str]] = None, scene: str = "DATAWORKS_PROJECT") -> None:
    print_confirmed_params()

    meta = _load_metadata()
    info = _check_command(meta, command)

    # 构造 createNodeSimple 入参（flat 结构）
    call_kwargs = {
        "projectId": project_id,
        "scene": scene,
        "command": command,
        "name": name,
    }
    if content is not None:
        call_kwargs["content"] = content
    if upstream:
        call_kwargs["upstreamNodeIds"] = ",".join(upstream) if isinstance(upstream, list) else upstream

    # 打印 family / notes 辅助理解（agent 信号通道）
    print(f"{_TAG} 将创建 {command} 节点（family={info.get('family')}）")
    print(f"{_TAG}   name={name}  projectId={project_id}  scene={scene}")
    if content:
        preview = content.replace("\n", " ")[:80]
        print(f"{_TAG}   content 预览: {preview}{'...' if len(content) > 80 else ''}")
    if upstream:
        print(f"{_TAG}   上游依赖: {upstream}")
    if info.get("post_create_hooks"):
        print(f"{_TAG}   ⚠ 服务端副作用: {info['post_create_hooks']}")

    client = BFFClient(quiet=True)
    client.write("createNodeSimple", _caller_confirmed=True, **call_kwargs)
    result = client.confirm_write()

    # 提取 uuid（createNodeSimple 返回值 data=uuid 字符串或含 uuid 的 dict）
    node_id = None
    if isinstance(result, dict):
        node_id = result.get("uuid") or result.get("nodeId") or result.get("id")
    elif isinstance(result, (int, str)):
        node_id = str(result)

    print(f"{_TAG} ✅ 节点创建成功")
    if node_id:
        print(f"{_TAG}   uuid: {node_id}")
    print(f"\n下一步可选：")
    if node_id:
        print(f"  · 发布上线: python deploy_node.py --project-id {project_id} --uuid {node_id}")
        print(f"  · 补改内容: 直接调用 UpdateNode（uuid={node_id}）")
    if not upstream:
        print(f"  · 加依赖:   通过 addNodeDependencies API（若本次没指定 --upstream）")

    telemetry_end(result={"status": "success", "node_id": node_id, "command": command})
    save_tool_result("create_node", {
        "summary": f"已创建 {command} 节点: {name}",
        "status": "success",
        "project_id": project_id,
        "command": command,
        "name": name,
        "node_id": node_id,
    })
    if node_id:
        remember(node_uuid=node_id, project_id=project_id)


def main():
    parser = argparse.ArgumentParser(description="按 command 创建开发态节点（使用 createNodeSimple）")
    parser.add_argument("--project-id", type=int, required=True, help="工作空间 ID")
    parser.add_argument("--command", required=True,
                        help="节点类型，如 ODPS_SQL / DIDE_SHELL / PYTHON / FLINK_SQL_STREAM")
    parser.add_argument("--name", required=True, help="节点名称，支持 dir/subdir/name 多级路径")
    parser.add_argument("--content", help="节点代码内容（SQL / shell / JSON 配置等）")
    parser.add_argument("--upstream", action="append", default=[],
                        help="上游依赖的 output 名，可多次。如 autotest.test_skyfire_0420")
    parser.add_argument("--scene", default="DATAWORKS_PROJECT",
                        choices=["DATAWORKS_PROJECT", "DATAWORKS_MANUAL_TASK", "DATAWORKS_MANUAL_WORKFLOW"],
                        help="创建场景（默认 DATAWORKS_PROJECT 项目目录）")
    args = parser.parse_args()

    telemetry_start("create_node.py", module="node-management",
                    project_id=args.project_id, command=args.command, name=args.name)

    create(
        project_id=args.project_id,
        command=args.command,
        name=args.name,
        content=args.content,
        upstream=args.upstream or None,
        scene=args.scene,
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("create_node.py", "node-management",
                       e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("create_node.py", "node-management", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
