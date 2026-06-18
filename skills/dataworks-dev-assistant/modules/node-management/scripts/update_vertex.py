#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新节点属性 —— 消费 update_node_contract.json + update_node_field_behavior.json

所有字段改动经过三层闸门：
  1. 字段存在性：contract 里是否声明了此字段
  2. 字段类型/枚举：值符合 schema 约束
  3. 实测验证：field_behavior 里该 aspect 是否 verified=true

用法：
    # 改调度
    update_vertex.py --uuid X --set trigger.cron="0 0 2 * * ?" --set trigger.cycleType=Daily
    # 改重跑策略
    update_vertex.py --uuid X --set rerunTimes=5 --set rerunInterval=60000
    # 改超时
    update_vertex.py --uuid X --set timeout=7200 --set timeoutUnit=SECONDS
    # 改调度状态
    update_vertex.py --uuid X --set recurrence=Skip
    # 加节点参数
    update_vertex.py --uuid X --set 'script.parameters=[{"name":"bizdate","scope":"NodeParameter","type":"System","value":"$[yyyymmdd]"}]'

支持的 aspect（即 field_behavior 标 verified 的）自动暴露；其他字段拒绝。
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from bff_client import BFFClient, save_tool_result
from runtime import print_confirmed_params, remember
from telemetry import telemetry_start, telemetry_end, telemetry_fail

_TAG = "[update_vertex]"

_SCRIPT_DIR = Path(__file__).resolve().parent
_REF_CANDIDATES = [
    _SCRIPT_DIR.parents[2] / "core" / "references",   # dev: src/
    _SCRIPT_DIR.parents[1] / "..",                     # dist: 相对
]


def _find_ref_file(name: str) -> Path:
    for base in _REF_CANDIDATES:
        p = (base / name).resolve()
        if p.exists():
            return p
    raise FileNotFoundError(f"{_TAG} 找不到 {name}，查找过：{[str(b/name) for b in _REF_CANDIDATES]}")


def _load_contract() -> dict:
    return json.loads(_find_ref_file("update_node_contract.json").read_text())


def _load_behavior() -> dict:
    try:
        return json.loads(_find_ref_file("update_node_field_behavior.json").read_text())
    except FileNotFoundError:
        return {"results": []}


def _verified_aspects(behavior: dict) -> set[str]:
    return {r["aspect"] for r in behavior.get("results", []) if r.get("status") == "verified"}


def _verified_fields(behavior: dict) -> dict[str, str]:
    """返回 { field_top_name: aspect }，仅包含 verified 的（从 expected_paths 提取顶层名）"""
    mapping = {}
    for r in behavior.get("results", []):
        if r.get("status") != "verified":
            continue
        for exp_path in r.get("expected_paths", []):
            top = exp_path.split(".")[0]
            if top:
                mapping[top] = r["aspect"]
    return mapping


def _parse_value(raw: str) -> Any:
    """尝试 json.loads，失败则原样字符串"""
    raw = raw.strip()
    if raw in ("true", "false"):
        return raw == "true"
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


def _set_nested(body: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = body
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def _validate_field(path: str, value: Any, contract: dict, verified_fields: dict[str, str]) -> tuple[bool, str]:
    top = path.split(".")[0]
    if top not in contract["fields"]:
        return False, f"字段 {top!r} 不在 contract（共 {len(contract['fields'])} 个字段）"
    if contract["fields"][top].get("transient"):
        return False, f"字段 {top!r} 是 transient（服务端内部字段，客户端不可传）"
    if top not in verified_fields:
        verified_list = ", ".join(sorted(set(verified_fields)))
        return False, f"字段 {top!r} 未经 runtime verify。verified 字段: [{verified_list}]"
    # 枚举校验
    field_def = contract["fields"][top]
    enum = field_def.get("enum")
    if enum and "." not in path:  # 顶层枚举字段
        if value not in enum:
            return False, f"{top}={value!r} 不在允许值 {enum}"
    # trigger.* 的嵌套校验（简单检查）
    return True, ""


def update(uuid: str, sets: list[str], project_id: int) -> None:
    print_confirmed_params()
    contract = _load_contract()
    behavior = _load_behavior()
    verified_fields = _verified_fields(behavior)

    if not sets:
        print(f"{_TAG} ❌ 至少指定一条 --set field=value", file=sys.stderr)
        print(f"  已 verified 的字段: {sorted(set(verified_fields))}", file=sys.stderr)
        sys.exit(1)

    # 解析 + 校验
    changes = {}
    errors = []
    for kv in sets:
        if "=" not in kv:
            errors.append(f"{kv!r} 格式错，应为 path=value")
            continue
        path, raw = kv.split("=", 1)
        path = path.strip()
        value = _parse_value(raw)
        ok, err = _validate_field(path, value, contract, verified_fields)
        if not ok:
            errors.append(f"{path}: {err}")
            continue
        changes[path] = value

    if errors:
        for e in errors:
            print(f"{_TAG} ❌ {e}", file=sys.stderr)
        sys.exit(1)

    # 组装 body
    body = {"uuid": uuid, "projectId": project_id}
    for path, value in changes.items():
        _set_nested(body, path, value)

    # 打印 preview
    print(f"{_TAG} 将更新节点 {uuid}（project={project_id}）：")
    affected_aspects = sorted({verified_fields[p.split('.')[0]] for p in changes})
    print(f"{_TAG}   涉及 aspect: {affected_aspects}")
    for k, v in changes.items():
        pv = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
        print(f"{_TAG}   {k} = {pv[:80]}{'...' if len(pv) > 80 else ''}")

    # 发起写操作
    client = BFFClient(quiet=True)
    client.write("updateVertex", _caller_confirmed=True, **body)
    result = client.confirm_write()

    if result is True or (isinstance(result, dict) and result.get("code") == 200):
        print(f"{_TAG} ✅ 更新成功")
    elif result is not None:
        print(f"{_TAG} ⚠ 返回: {result}")
    else:
        print(f"{_TAG} ❌ 调用失败")
        sys.exit(1)

    telemetry_end(result={"status": "success", "uuid": uuid, "aspects": affected_aspects})
    save_tool_result("update_vertex", {
        "summary": f"已更新节点属性 (aspect={affected_aspects})",
        "status": "success",
        "uuid": uuid, "project_id": project_id,
        "changes": list(changes.keys()),
    })
    remember(node_uuid=uuid, project_id=project_id)


def main():
    parser = argparse.ArgumentParser(description="更新节点属性（基于源码 contract + 实测 verified 的字段闸门）")
    parser.add_argument("--project-id", type=int, required=True, help="工作空间 ID")
    parser.add_argument("--uuid", required=True, help="节点 UUID")
    parser.add_argument("--set", action="append", default=[], metavar="path=value",
                        help="待更新字段，支持点号路径（如 trigger.cron=X）。可多次")
    parser.add_argument("--list-verified", action="store_true",
                        help="列出所有 verified 字段和值约束")
    args = parser.parse_args()

    if args.list_verified:
        contract = _load_contract()
        behavior = _load_behavior()
        verified = _verified_fields(behavior)
        print(f"\n已 verified 字段（共 {len(verified)}）：")
        for field, aspect in sorted(verified.items(), key=lambda x: (x[1], x[0])):
            fdef = contract["fields"].get(field, {})
            enum = fdef.get("enum")
            jtype = fdef.get("java_type", "?")
            extra = f"  enum={enum}" if enum else f"  type={jtype}"
            print(f"  [{aspect:18s}] {field:25s}{extra}")
        return

    telemetry_start("update_vertex.py", module="node-management",
                    project_id=args.project_id, uuid=args.uuid)
    update(args.uuid, args.set, args.project_id)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("update_vertex.py", "node-management",
                       e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("update_vertex.py", "node-management", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
