#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DI 同步配置构造器

给定已确定的数据源、列名、资源组，构造并校验 DI JSON 配置。
校验失败时输出错误详情，agent 可回退到 probe_table.py 调整参数后重试。

用法：
    python build_di_spec.py --project-id 22153 \
      --src-datasource _TDDL --src-type tddl --src-table users \
      --dst-datasource _ODPS --dst-type odps \
      --columns id,name,age --resource-group group_22153
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from bff_client import BFFClient, save_tool_result
from runtime import print_confirmed_params, remember, project_id_to_project_name

_SCRIPT_DIR = Path(__file__).parent
_MODULE_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_MODULE_DIR))

from spec_builder.common.datasource_registry import DatasourceRegistry
from spec_builder.offline_node.builder import build_di_config
from spec_builder.validation.schema_validator import DIConfigValidator
from telemetry import telemetry_start, telemetry_end, telemetry_fail

# ─── 常量 ──────────────────────────────────────────────────────

_SCHEMA_DIR = _MODULE_DIR / "reference" / "schemas"
_PENDING_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "pending_di_sync_job.json")
_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "di_config.json")

_TAG = "[build_di_spec]"

# builder + validator 验证通过的数据源（capability matrix 测试保证）
_VERIFIED_READERS = {
    "clickhouse", "drds", "hive", "holo", "kafka", "lindorm",
    "mysql", "odps", "oracle", "postgresql", "sqlserver", "starrocks", "tddl",
}
_VERIFIED_WRITERS = {
    "ads", "datahub", "doris", "drds", "holo", "lindorm",
    "mysql", "odps", "oracle", "postgresql", "saphana",
    "selectdb", "sqlserver", "starrocks",
}


# ─── 错误恢复建议 ─────────────────────────────────────────────

_COLUMN_KEYWORDS = {"column", "minItems", "is not of type"}
_REQUIRED_KEYWORD = "is a required property"


def _suggest_recovery(errors: list, args: argparse.Namespace) -> None:
    """根据校验错误类型，输出具体的恢复建议"""
    column_errors = []
    missing_fields = []
    other_errors = []

    for e in errors:
        e_lower = e.lower()
        if any(kw in e_lower for kw in _COLUMN_KEYWORDS):
            column_errors.append(e)
        elif _REQUIRED_KEYWORD in e:
            # 提取缺失的字段名: ... | 'fieldName' is a required property
            field = e.split("'")[1] if "'" in e else ""
            role = "reader" if "/reader]" in e else "writer"
            missing_fields.append((field, role))
        else:
            other_errors.append(e)

    print(f"\n{_TAG} 修复建议:")

    if column_errors:
        print(f"  列信息有误，重新探测源端表结构:")
        print(f"    probe_table.py --project-id {args.project_id} --datasource {args.src_datasource} --type {args.src_type} --table {args.src_table} --resource-group {args.resource_group}")

    if missing_fields:
        for field, role in missing_fields:
            if field in ("column", "table", "datasource"):
                continue  # 这些是 builder 负责填的，不应该缺
            print(f"  缺少 {role} 参数 {field}，添加: --{role}-{field} <值>")

    if not column_errors and not missing_fields:
        print(f"  请检查参数后重试")


# ─── 主流程 ───────────────────────────────────────────────────


def _fetch_base_id() -> str:
    """从 BFF 获取当前用户的 baseId（工号）。失败时静默返回空字符串。"""
    try:
        client = BFFClient(quiet=True)
        user = client.load("currentUser")
        if isinstance(user, list) and user:
            user = user[0]
        return str((user or {}).get("baseId") or (user or {}).get("id") or "")
    except Exception:
        return ""


def _fetch_project_name(project_id: int) -> str:
    """从 BFF 获取工作空间名称。失败时静默返回空字符串。"""
    try:
        client = BFFClient(quiet=True)
        return project_id_to_project_name(client, project_id) or ""
    except Exception:
        return ""


def build(args: argparse.Namespace, extra_params: Dict) -> None:
    registry = DatasourceRegistry()

    # 1. 验证类型
    src_info = registry.resolve(args.src_type)
    dst_info = registry.resolve(args.dst_type)
    if not src_info or not src_info.can_read or src_info.step_type not in _VERIFIED_READERS:
        print(f"{_TAG} 不支持的源端类型: {args.src_type}")
        print(f"{_TAG} 支持的 Reader: {', '.join(sorted(_VERIFIED_READERS))}")
        sys.exit(1)
    if not dst_info or not dst_info.can_write or dst_info.step_type not in _VERIFIED_WRITERS:
        print(f"{_TAG} 不支持的目标端类型: {args.dst_type}")
        print(f"{_TAG} 支持的 Writer: {', '.join(sorted(_VERIFIED_WRITERS))}")
        sys.exit(1)

    print(f"{_TAG} 工作空间: {args.project_id}")
    print(f"{_TAG} 源端: {args.src_datasource} ({args.src_type})")
    print(f"{_TAG} 目标端: {args.dst_datasource} ({args.dst_type})")
    print(f"{_TAG} 资源组: {args.resource_group}")

    # 2. 列信息
    columns = [c.strip() for c in args.columns.split(",") if c.strip()]
    if not columns:
        print(f"{_TAG} ❌ 列名为空，请通过 probe_table.py 探测源端表结构获取列名")
        sys.exit(1)
    dst_table = args.dst_table or args.src_table
    split_pk = args.split_pk or extra_params.get("reader_splitPk")
    task_name = args.task_name or f"{dst_table}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    print(f"{_TAG} {len(columns)} 列: {', '.join(columns[:10])}{'...' if len(columns) > 10 else ''}")
    if split_pk:
        print(f"{_TAG} splitPk: {split_pk}")

    # 3. 获取当前用户 baseId（工号），写入 extend.baseId；同时解析工作空间名（用于 ODPS guid）
    base_id = _fetch_base_id()
    if base_id:
        print(f"{_TAG} baseId: {base_id}")
    project_name = _fetch_project_name(args.project_id)
    if project_name:
        print(f"{_TAG} 工作空间名: {project_name}")

    # 4. 构造配置
    reader_extra = {k[len("reader_"):]: v for k, v in extra_params.items() if k.startswith("reader_")}
    writer_extra = {k[len("writer_"):]: v for k, v in extra_params.items() if k.startswith("writer_")}

    config = build_di_config(
        src_info=src_info, dst_info=dst_info,
        src_datasource=args.src_datasource, dst_datasource=args.dst_datasource,
        src_table=args.src_table, dst_table=dst_table,
        columns=columns, resource_group=args.resource_group,
        split_pk=split_pk, concurrent=args.concurrent or 3,
        extra_reader_params=reader_extra, extra_writer_params=writer_extra,
        base_id=base_id or None, task_name=task_name,
        project_name=project_name or None,
    )

    # 5. 校验
    validator = DIConfigValidator(schema_dir=str(_SCHEMA_DIR))
    is_valid, errors, warnings = validator.validate(config)
    config_json = json.dumps(config, ensure_ascii=False, indent=2)

    if not is_valid:
        print(f"\n{_TAG} ❌ 配置校验失败:")
        for e in errors:
            print(f"  ✗ {e}")
        for w in warnings:
            print(f"  ⚠ {w}")
        print(f"\n{config_json}")
        _suggest_recovery(errors, args)
        save_tool_result("build_di_spec", {
            "summary": "配置校验失败", "status": "validation_failed",
            "errors": errors, "warnings": warnings,
        })
        sys.exit(1)

    # 6. 保存
    config_file = getattr(args, "output", None) or _CONFIG_FILE
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        f.write(config_json)

    pending = {
        "created_at": datetime.now().isoformat(),
        "project_id": args.project_id, "task_name": task_name,
        "config_file": os.path.abspath(config_file), "config": config,
        "src_type": args.src_type, "dst_type": args.dst_type,
        "src_table": args.src_table, "dst_table": dst_table,
    }
    os.makedirs(os.path.dirname(_PENDING_FILE), exist_ok=True)
    with open(_PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

    print(f"\n{_TAG} ✅ 配置校验通过")
    for w in warnings:
        print(f"  ⚠ {w}")
    print(f"{_TAG} 任务名称: {task_name}")
    print(f"{_TAG} 配置已保存: {config_file}")
    print()
    print(config_json)
    print()
    print(f"下一步:")
    is_idb_src = (args.src_datasource or "").upper().startswith("_IDB.")
    if is_idb_src:
        # 解析 --column-types（由 probe_table.py 输出的 col:TYPE 对）
        col_type_map: Dict[str, str] = {}
        if getattr(args, "column_types", None):
            for pair in args.column_types.split(","):
                pair = pair.strip()
                if ":" in pair:
                    col_name, col_type = pair.split(":", 1)
                    col_type_map[col_name.strip()] = col_type.strip().upper()

        print(f"  ⚠️  IDB 数据源不支持 ensure_target_table.py（_ODPS 数据源的 getTableColumnPost 需要 accessId，必然报错）")
        print(f"  ① 手动建目标表（分区固定为 ds STRING）:")
        if col_type_map:
            col_defs = ", ".join(
                f"{c} {col_type_map.get(c, 'STRING')}"
                for c in columns
            )
        else:
            col_defs = ", ".join(f"{c} <类型>" for c in columns)
            print(f"    ⚠️  未传 --column-types，类型为占位符，请先运行 probe_table.py 获取列类型")
        print(f"    execute_sql.py \"CREATE TABLE IF NOT EXISTS <project>.{dst_table} ({col_defs}) PARTITIONED BY (ds STRING) LIFECYCLE 7\" \\")
        print(f"      --datasource-code <odps_datasource_code>")
        print(f"    # 验证建表成功:")
        print(f"    execute_sql.py \"DESC <project>.{dst_table}\" --datasource-code <odps_datasource_code>")
    else:
        print(f"  ① 确保目标表存在（如已存在会自动跳过）:")
        print(f"    ensure_target_table.py --project-id {args.project_id} --src-datasource {args.src_datasource} --src-type {args.src_type} --src-table {args.src_table} --dst-datasource {args.dst_datasource} --dst-type {args.dst_type} --dst-table {dst_table}")
    print(f"  ② 用户确认后创建节点:")
    print(f"    create_di_node.py --project-id {args.project_id} --task-name {task_name}")

    telemetry_end(result={"status": "pending_confirm", "task_name": task_name})
    save_tool_result("build_di_spec", {
        "summary": f"配置已生成: {task_name} ({args.src_type}→{args.dst_type})",
        "status": "pending_confirm", "project_id": args.project_id,
        "task_name": task_name, "config_file": os.path.abspath(_CONFIG_FILE),
        "src": f"{args.src_type}({args.src_datasource}.{args.src_table})",
        "dst": f"{args.dst_type}({args.dst_datasource}.{dst_table})",
    })
    # 累积参数到 confirmed_params（agent 注意力辅助层）
    remember(
        task_name=task_name,
        dst_table=dst_table,
    )


# ─── CLI ──────────────────────────────────────────────────────


def _check_resolve_guard():
    """入口守卫：检查是否已执行 resolve_sync_datasource"""
    result_path = os.path.join(os.path.expanduser("~"), ".dataworks", "resolve_sync_datasource_result.json")
    if not os.path.exists(result_path):
        print("[build_di_spec] 请先执行 resolve_sync_datasource.py 解析数据源。")
        print("  → resolve_sync_datasource.py --project-name <工作空间> --src-type <源类型> --dst-type <目标类型> --src-table <表名>")
        print("  五步流程不可跳步：① resolve → ② probe_table → ③ build_di_spec → ④ ensure_target_table → ⑤ create_di_node")
        sys.exit(1)


def main():
    _check_resolve_guard()
    parser = argparse.ArgumentParser(description="DI 同步配置构造器")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--src-datasource", help="源端数据源名称")
    parser.add_argument("--src-type", help="源端数据源类型")
    parser.add_argument("--src-table", help="源表名")
    parser.add_argument("--dst-datasource", help="目标数据源名称")
    parser.add_argument("--dst-type", help="目标端数据源类型")
    parser.add_argument("--dst-table", help="目标表名（默认 = 源表名）")
    parser.add_argument("--columns", help="同步列名，逗号分隔")
    parser.add_argument("--resource-group", help="资源组标识")
    parser.add_argument("--split-pk", help="分片键")
    parser.add_argument("--concurrent", type=int, help="并发数（默认 3）")
    parser.add_argument("--task-name", help="任务名称（默认: 源表名_时间戳）")
    parser.add_argument("--column-types", help="列名与ODPS类型，逗号分隔，如 id:BIGINT,name:STRING（由 probe_table.py 输出）")
    parser.add_argument("--output", "-o", help=f"配置输出路径（默认: {_CONFIG_FILE}）")

    args, unknown = parser.parse_known_args()

    telemetry_start("build_di_spec.py", module="data-integration", project_id=args.project_id)
    print_confirmed_params()

    extra_params: Dict[str, Any] = {}
    i = 0
    while i < len(unknown):
        arg = unknown[i]
        if arg.startswith("--reader-") or arg.startswith("--writer-"):
            key = arg[2:].replace("-", "_")
            if i + 1 < len(unknown) and not unknown[i + 1].startswith("--"):
                extra_params[key] = unknown[i + 1]
                i += 2
            else:
                extra_params[key] = True
                i += 1
        else:
            print(f"{_TAG} 未知参数: {arg}", file=sys.stderr)
            sys.exit(1)

    missing = []
    if not args.project_id:
        missing.append("--project-id")
    if not args.src_datasource:
        missing.append("--src-datasource")
    if not args.src_type:
        missing.append("--src-type")
    if not args.src_table:
        missing.append("--src-table")
    if not args.dst_datasource:
        missing.append("--dst-datasource")
    if not args.dst_type:
        missing.append("--dst-type")
    if not args.columns:
        missing.append("--columns")
    if not args.resource_group:
        missing.append("--resource-group")
    if missing:
        print(f"{_TAG} 缺少必填参数: {', '.join(missing)}")
        print(f"{_TAG} 请先用 resolve_sync_datasource.py 解析数据源，再用 probe_table.py 探测表结构")
        sys.exit(1)

    build(args, extra_params)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("build_di_spec.py", "data-integration", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("build_di_spec.py", "data-integration", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
