#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据集成表探测工具

探测数据源中表的字段、splitPk、存在性，或列出所有表。

用法：
    # 探测表字段（最常用）
    python probe_table.py --project-id 22153 --datasource my_mysql --type mysql \
      --table users --resource-group group_22153

    # 检查表是否存在
    python probe_table.py --project-id 22153 --datasource odps_first --type odps \
      --table users --resource-group group_22153 --check-exists

    # 列出数据源下所有表
    python probe_table.py --project-id 22153 --datasource my_mysql --type mysql \
      --resource-group group_22153 --list-tables
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from bff_client import BFFClient, save_tool_result, resolve_project_id
from runtime import print_confirmed_params, remember

_SCRIPT_DIR = Path(__file__).parent
_MODULE_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_MODULE_DIR))

from telemetry import telemetry_start, telemetry_end, telemetry_fail
from table_metadata import (
    is_tddl_type,
    load_table_metadata,
    load_table_names,
    table_exists,
)

_TAG = "[probe_table]"


# ─── 探测功能 ─────────────────────────────────────────────────


def probe_columns(client: BFFClient, project_id: int, datasource: str,
                  ds_type: str, resource_group: str, table: str,
                  appname: Optional[str] = None) -> None:
    """探测表字段、splitPk 等元数据"""
    print(f"{_TAG} 探测: {datasource}.{table}")

    # 捕获远程 API 的异常（如表不存在），转为定向回退引导
    try:
        meta = load_table_metadata(
            client, project_id, 1, datasource, ds_type,
            resource_group, table, 1, appname,
        )
    except Exception as e:
        err_msg = str(e)
        # 表不存在类错误：输出明确的"列出可用表"恢复命令
        if "doesn't exist" in err_msg or "not exist" in err_msg or "不存在" in err_msg:
            print(f"{_TAG} ❌ 表 {datasource}.{table} 不存在")
            print(f"{_TAG} → 列出 {datasource} 下所有表（确认正确表名后重试）:")
            print(f"  probe_table.py --project-id {project_id} --datasource {datasource} --type {ds_type} --resource-group {resource_group} --list-tables")
        else:
            print(f"{_TAG} ❌ 探测失败: {err_msg[:200]}")
            _suggest_on_failure(client, project_id, datasource, ds_type, resource_group, table, appname)
        sys.exit(1)

    if not meta or not meta.get("column_names"):
        print(f"{_TAG} 无法获取 {datasource}.{table} 的字段信息")
        _suggest_on_failure(client, project_id, datasource, ds_type, resource_group, table, appname)
        sys.exit(1)

    columns = meta["column_names"]
    column_types = meta.get("column_types") or {}
    column_comments = meta.get("column_comments") or {}
    split_pk = meta.get("split_pk")
    is_part = meta.get("is_partitioned", False)
    part_cols = meta.get("partition_columns") or []
    reader_extra = meta.get("reader_extra") or {}

    print(f"{_TAG} 获取到 {len(columns)} 列: {', '.join(columns[:10])}{'...' if len(columns) > 10 else ''}")
    if column_types:
        print(f"{_TAG} 列名与类型（ODPS 映射后）:")
        for col in columns[:30]:
            t = column_types.get(col, "STRING")
            comment = column_comments.get(col, "")
            comment_str = f"  -- {comment}" if comment else ""
            print(f"    {col} {t}{comment_str}")
        if len(columns) > 30:
            print(f"    ...（还有 {len(columns) - 30} 列）")
    if split_pk:
        print(f"{_TAG} splitPk: {split_pk} (自动推荐)")
    if is_part:
        part_names = []
        for p in part_cols:
            part_names.append(p.get("name") if isinstance(p, dict) else str(p))
        print(f"{_TAG} 分区列: {', '.join(part_names)}")
    if reader_extra:
        for k, v in reader_extra.items():
            print(f"{_TAG} {k}: {v}")

    # 输出 build_di_spec 可直接使用的参数
    column_types_str = ",".join(f"{c}:{column_types.get(c, 'STRING')}" for c in columns)
    print(f"\n可用于 build_di_spec.py 的参数:")
    print(f"  --columns {','.join(columns)}")
    if column_types_str:
        print(f"  --column-types {column_types_str}")
    if split_pk:
        print(f"  --split-pk {split_pk}")
    for k, v in reader_extra.items():
        print(f"  --reader-{k} {v}")

    telemetry_end(result={"status": "ok", "column_count": len(columns)})
    save_tool_result("probe_table", {
        "status": "ok",
        "datasource": datasource, "type": ds_type, "table": table,
        "columns": columns, "column_types": column_types,
        "split_pk": split_pk,
        "is_partitioned": is_part, "partition_columns": part_cols,
        "reader_extra": reader_extra,
    })
    # 累积参数到 confirmed_params（agent 注意力辅助层）
    remember_kwargs = {
        "src_table": table,
        "src_columns": ",".join(columns),
        "src_columns_count": len(columns),
        "src_column_types": column_types_str,
    }
    if split_pk:
        remember_kwargs["split_pk"] = split_pk
    remember(**remember_kwargs)


def check_exists(client: BFFClient, project_id: int, datasource: str,
                 ds_type: str, resource_group: str, table: str,
                 appname: Optional[str] = None) -> None:
    """检查表是否存在，存在时探测分区信息"""
    exists = table_exists(
        client, project_id, 1, datasource, resource_group,
        table, ds_type, 1, appname,
    )
    partition_expr = None
    if exists:
        print(f"{_TAG} {table} 在 {datasource} 中已存在")
        # 探测分区信息（用于 ODPS 等分区表的 --writer-partition）
        try:
            meta = load_table_metadata(
                client, project_id, 1, datasource, ds_type,
                resource_group, table, 1, appname,
            )
            if meta and meta.get("is_partitioned"):
                part_cols = meta.get("partition_columns") or []
                part_names = []
                for p in part_cols:
                    part_names.append(p.get("name") if isinstance(p, dict) else str(p))
                if part_names:
                    partition_expr = ",".join(f"{n}=${{bizdate}}" for n in part_names)
                    print(f"{_TAG} 分区表，分区列: {', '.join(part_names)}")
                    print(f"{_TAG} 建议添加: --writer-partition \"{partition_expr}\"")
        except Exception as e:
            print(f"{_TAG} 探测分区信息失败: {e}", file=sys.stderr)
    else:
        print(f"{_TAG} {table} 在 {datasource} 中不存在")

    save_tool_result("probe_table", {
        "status": "ok", "mode": "check_exists",
        "datasource": datasource, "table": table, "exists": exists,
        "partition_expr": partition_expr,
    })


def list_tables(client: BFFClient, project_id: int, datasource: str,
                ds_type: str, resource_group: str) -> None:
    """列出数据源下所有表"""
    names = load_table_names(
        client, project_id, 1, datasource, resource_group, ds_type, 1,
    )
    if not names:
        print(f"{_TAG} {datasource} 下没有表")
        sys.exit(1)

    print(f"{_TAG} {datasource} 下共 {len(names)} 个表:")
    for n in names[:50]:
        print(f"  - {n}")
    if len(names) > 50:
        print(f"  ...（还有 {len(names) - 50} 个）")

    save_tool_result("probe_table", {
        "status": "ok", "mode": "list_tables",
        "datasource": datasource, "table_count": len(names), "tables": names[:50],
    })


def _suggest_on_failure(client: BFFClient, project_id: int, datasource: str,
                        ds_type: str, resource_group: str, table: str,
                        appname: Optional[str]) -> None:
    """探测失败时输出可执行的恢复命令（不只是描述）"""
    if is_tddl_type(ds_type) and not appname:
        print(f"{_TAG} TDDL 数据源需要 --appname 参数。重试:")
        print(f"  probe_table.py --project-id {project_id} --datasource {datasource} --type {ds_type} --table {table} --resource-group {resource_group} --appname <appName>")
        return

    # 尝试列出可用表
    try:
        names = load_table_names(
            client, project_id, 1, datasource, resource_group, ds_type, 1,
        )
    except Exception:
        names = None

    if names:
        print(f"{_TAG} {datasource} 下可用表（共 {len(names)} 个）:")
        for n in names[:20]:
            print(f"  - {n}")
        if len(names) > 20:
            print(f"  ...（还有 {len(names) - 20} 个）")
        print(f"{_TAG} → 用正确的表名重试 probe_table:")
        print(f"  probe_table.py --project-id {project_id} --datasource {datasource} --type {ds_type} --table <正确表名> --resource-group {resource_group}")
    else:
        print(f"{_TAG} → 列出 {datasource} 下所有表:")
        print(f"  probe_table.py --project-id {project_id} --datasource {datasource} --type {ds_type} --resource-group {resource_group} --list-tables")


# ─── CLI ──────────────────────────────────────────────────────


def _check_resolve_guard():
    """入口守卫：检查是否已执行 resolve_sync_datasource

    --list-tables 模式是探索阶段，不需要 resolve 上下文，跳过守卫
    """
    result_path = os.path.join(os.path.expanduser("~"), ".dataworks", "resolve_sync_datasource_result.json")
    if not os.path.exists(result_path):
        print("[probe_table] 请先执行 resolve_sync_datasource.py 解析数据源。")
        print("  → resolve_sync_datasource.py --project-name <工作空间> --src-type <源类型> --dst-type <目标类型>")
        print("  resolve 的 stdout 会输出本脚本的完整命令，直接复制执行即可。")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="数据集成表探测工具")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--project-name", help="工作空间名称")
    parser.add_argument("--datasource", required=True, help="数据源名称")
    parser.add_argument("--type", required=True, dest="ds_type", help="数据源类型")
    parser.add_argument("--table", help="表名")
    parser.add_argument("--resource-group", required=True, help="资源组标识")
    parser.add_argument("--appname", help="TDDL appName")
    parser.add_argument("--check-exists", action="store_true", help="仅检查表是否存在")
    parser.add_argument("--list-tables", action="store_true", help="列出数据源下所有表")
    args = parser.parse_args()

    # 守卫：探索 (--list-tables / --check-exists) 模式不需要 resolve 上下文
    if not args.list_tables and not args.check_exists:
        _check_resolve_guard()

    telemetry_start("probe_table.py", module="data-integration", project_id=args.project_id, project_name=args.project_name)
    print_confirmed_params()

    if not args.list_tables and not args.table:
        parser.error("需要 --table（或使用 --list-tables）")

    client = BFFClient(quiet=True)
    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)

    if args.list_tables:
        list_tables(client, project_id, args.datasource, args.ds_type, args.resource_group)
    elif args.check_exists:
        check_exists(client, project_id, args.datasource, args.ds_type,
                     args.resource_group, args.table, args.appname)
    else:
        probe_columns(client, project_id, args.datasource, args.ds_type,
                      args.resource_group, args.table, args.appname)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("probe_table.py", "data-integration", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("probe_table.py", "data-integration", 1, error=str(e)[:100])
        print(f"\n[error] {e}")
        print(f"  如需上报此问题: report_bug.py \"{e}\" --script probe_table.py")
        sys.exit(1)
