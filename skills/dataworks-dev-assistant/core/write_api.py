#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用写操作工具 —— 所有简单写 API 的两阶段确认入口

Phase 1（准备）：输出确认摘要，等待用户确认
Phase 2（执行）：用户确认后执行写操作

用法:
    # Phase 1：准备写操作
    python write_api.py createNodeSimple projectId=23304 scene=DATAWORKS_PROJECT command=ODPS_SQL name=test content="select 1;"

    # Phase 2：用户确认后执行
    python write_api.py --confirm

    # 复杂参数（JSON 值）用引号包裹
    python write_api.py UpdateNode projectId=23304 uuid=xxx spec='{"name":"new_name"}'

注意:
    deploy / SQL 执行有专用脚本，不走此通用入口：
    - 发布部署 → deploy_node.py
    - SQL 执行 → execute_sql.py
"""

import json
import os
import sys

from bff_client import BFFClient, save_tool_result, add_backlog


_TAG = "[write_api]"

# 有专用脚本的写 API，禁止通过本脚本调用
_DEDICATED_APIS = {
    "createDeployment": "deploy_node.py",
    "createQueryJob": "execute_sql.py",
    "createQueryJobRead": "execute_sql.py",
    "createExecutorJob4Ida": "execute_sql.py",
    "createExecutorJob4IdaRead": "execute_sql.py",
    "supplementAsync": "backfill_node.py",
}


_RAW_STRING_PARAMS = {
    # createNodeSimple 的 content 应作为原始字符串透传。
    # 若这里把 JSON 提前反序列化成 dict/list，后续 HTTP 层会再 str()，
    # 最终写入成 Python repr（单引号/True/False），破坏合法 JSON。
    "createNodeSimple": {"content"},
    # UpdateNode / 工作流等接口的 spec 是 JSON 字符串参数。
    # 若这里提前 json.loads()，HTTP 层会把 dict 再 str() 成 Python repr，
    # 导致服务端报 "Spec JSON parse failed"。
    "UpdateNode": {"spec"},
    "CreateWorkflowDefinition": {"spec"},
    "UpdateWorkflowDefinition": {"spec"},
    "ImportWorkflowDefinition": {"spec"},
}


def _parse_value(v):
    """智能解析参数值：JSON / 数字 / 字符串"""
    # JSON 对象或数组
    if (v.startswith("{") and v.endswith("}")) or (v.startswith("[") and v.endswith("]")):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            pass
    # 整数
    try:
        return int(v)
    except ValueError:
        pass
    # 布尔
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    return v


def _parse_args(api_name, raw_args):
    """解析 key=value 参数列表"""
    params = {}
    raw_string_keys = _RAW_STRING_PARAMS.get(api_name, set())
    for arg in raw_args:
        if "=" not in arg:
            print(f"{_TAG} 参数格式错误: {arg}（应为 key=value）")
            sys.exit(1)
        key, value = arg.split("=", 1)
        if key in raw_string_keys:
            params[key] = value
        else:
            params[key] = _parse_value(value)
    return params


def prepare(api_name, params):
    """Phase 1: 准备写操作"""
    # 检查是否有专用脚本
    if api_name in _DEDICATED_APIS:
        script = _DEDICATED_APIS[api_name]
        print(f"{_TAG} {api_name} 请使用专用脚本: python {script}")
        sys.exit(1)

    client = BFFClient(quiet=True)

    # 验证 API 存在且是写操作
    api_meta = client.api_index.get(api_name)
    if not api_meta:
        print(f"{_TAG} 未找到 API: {api_name}")
        sys.exit(1)
    if not api_meta.get("is_write_operation"):
        print(f"{_TAG} {api_name} 不是写操作，请用 client.load() 调用")
        sys.exit(1)

    client.write(api_name, **params)
    print(f"  → 用户确认后执行: python write_api.py --confirm")


def _resolve_follow_up_params(param_mapping, write_params, write_result):
    """解析 follow_up 的 param_mapping 为具体参数值"""
    resolved = {}
    for target_key, source_expr in param_mapping.items():
        if source_expr == "$result":
            if write_result is not None:
                resolved[target_key] = write_result
        elif isinstance(source_expr, str) and source_expr.startswith("$result."):
            if isinstance(write_result, dict):
                value = write_result
                for key in source_expr[len("$result."):].split("."):
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        value = None
                        break
                if value is not None:
                    resolved[target_key] = value
        elif isinstance(source_expr, str) and source_expr.startswith("="):
            literal = source_expr[1:]
            if literal == "null":
                resolved[target_key] = None
            elif literal == "true":
                resolved[target_key] = True
            elif literal == "false":
                resolved[target_key] = False
            else:
                try:
                    resolved[target_key] = int(literal)
                except ValueError:
                    resolved[target_key] = literal
        elif "[0]" in source_expr:
            field = source_expr.replace("[0]", "")
            val = write_params.get(field)
            if isinstance(val, list) and val:
                val = val[0]
            if val is not None:
                resolved[target_key] = val
        else:
            val = write_params.get(source_expr)
            if val is not None:
                resolved[target_key] = val
    return resolved


def confirm():
    """Phase 2: 执行已确认的写操作"""
    pending_path = os.path.join(os.path.expanduser("~"), ".dataworks", "pending_write.json")
    if not os.path.exists(pending_path):
        print(f"{_TAG} 没有待确认的写操作。请先运行: python write_api.py <API名> key=value ...")
        sys.exit(1)

    # 先读 pending 文件获取 api_name 和 params（confirm_write 内部会删除它）
    with open(pending_path, "r", encoding="utf-8") as f:
        pending = json.load(f)
    api_name = pending["api_name"]
    write_params = pending["params"]

    client = BFFClient(quiet=True)
    result = client.confirm_write()

    # 输出返回值（agent 需要这些值进行链式操作）
    if result is not None:
        if isinstance(result, dict):
            for k, v in result.items():
                print(f"  {k}: {v}")
        elif isinstance(result, str) and len(result) < 200:
            print(f"  返回值: {result}")

    # 若 API 有 follow_up 定义，自动加入待办
    api_meta = client.api_index.get(api_name, {})
    follow_up = api_meta.get("follow_up")
    if follow_up and follow_up.get("mode", "async") == "async":
        resolved_params = _resolve_follow_up_params(
            follow_up.get("param_mapping", {}), write_params, result
        )
        add_backlog(
            type_name="write_api",
            label=f"{api_name} 异步结果跟踪",
            check={
                "api": follow_up["api"],
                "params": resolved_params,
                "status_field": follow_up.get("status_field", "status"),
                "terminal": follow_up.get("terminal", {}),
                "pending": follow_up.get("pending", {}),
            },
            context={"api_name": api_name, "params": write_params},
        )
        print(f"{_TAG} → 已加入异步任务列表，稍后运行 check_backlogs.py 查看异步结果")

    save_tool_result("write_api", {
        "summary": f"写操作执行完成: {api_name}",
        "result": result if not isinstance(result, (list, dict)) or len(str(result)) < 500 else str(result)[:500],
    })


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="通用写操作工具（两阶段确认）",
        epilog="发布用 deploy_node.py，SQL 执行用 execute_sql.py",
        usage="%(prog)s <API名> key=value ... | %(prog)s --confirm",
    )
    parser.add_argument("--confirm", action="store_true",
                        help="执行已确认的写操作（Phase 2）")
    parser.add_argument("api_name", nargs="?",
                        help="API 名称（如 createNodeSimple、rerun_task_instances）")
    parser.add_argument("params", nargs="*",
                        help="API 参数，格式: key=value")

    args = parser.parse_args()

    if args.confirm:
        confirm()
    elif args.api_name:
        params = _parse_args(args.api_name, args.params)
        prepare(args.api_name, params)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
