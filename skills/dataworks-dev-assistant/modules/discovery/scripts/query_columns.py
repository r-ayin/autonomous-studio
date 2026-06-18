#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""表结构查询 — 列出表的所有字段信息

用法:
    python query_columns.py "表名"
    python query_columns.py "项目.表名"
    python query_columns.py "表名" --project 项目名
    python query_columns.py "表名" --project-id 23304

功能:
    搜索表 → 调用 listColumns → 输出字段列表（名字 / 类型 / 注释 / 分区键）

字段含义:
    name:         字段名
    type:         类型（string / bigint / datetime 等）
    comment:      字段注释
    partitionKey: 是否分区键
    position:     字段顺序（物理顺序）
"""

import argparse
import sys

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail

from search_table import find_table


def _table_id_from_qualified_name(qn):
    """qualifiedName 转 tableId 格式：type.a.b → type:::a::b"""
    if not qn:
        return None
    parts = qn.split(".")
    if len(parts) < 2:
        return None
    return parts[0] + ":::" + "::".join(parts[1:])


def _resolve_table_id(table):
    """优先用 metaEntityId（已是冒号格式），fallback 用 qualifiedName 转换"""
    tid = table.get("metaEntityId")
    if tid:
        return tid
    qn = table.get("qualifiedName")
    return _table_id_from_qualified_name(qn)


def print_columns(table_name, database, columns):
    """格式化输出字段列表"""
    if not columns:
        print("\n(无字段数据)")
        return

    # 按 position 排序，去重（listColumns 可能返回重复行）
    seen = set()
    ordered = []
    for c in sorted(columns, key=lambda x: x.get("position") or 999):
        name = c.get("name")
        if name and name not in seen:
            seen.add(name)
            ordered.append(c)

    # 分区键 & 普通字段拆开
    partition_cols = [c for c in ordered if c.get("partitionKey")]
    data_cols = [c for c in ordered if not c.get("partitionKey")]

    print(f"\n字段列表（共 {len(ordered)} 个，含 {len(partition_cols)} 个分区键）")
    print(f"{'─' * 90}")
    print(f"  {'#':<4}{'字段名':<28}{'类型':<18}{'注释'}")
    print(f"{'─' * 90}")

    for i, c in enumerate(data_cols, 1):
        name = (c.get("name") or "")[:26]
        typ = (c.get("type") or "")[:16]
        comment = (c.get("comment") or "")[:50]
        print(f"  {i:<4}{name:<28}{typ:<18}{comment}")

    if partition_cols:
        print(f"\n分区键:")
        for c in partition_cols:
            name = c.get("name") or ""
            typ = c.get("type") or ""
            comment = c.get("comment") or ""
            print(f"  [part] {name} ({typ})  {comment}")


def _print_next_steps(table_name, database, total_cols):
    print(f"\n{'─' * 60}")
    print(f"下一步")
    print(f"{'─' * 60}")
    print(f"  1. 查分区：query_partitions.py \"{database}.{table_name}\"")
    print(f"  2. 查血缘：query_lineage.py \"{database}.{table_name}\"")
    print(f"  3. 产出节点：identify.py \"{table_name}\" --deep")


def main():
    parser = argparse.ArgumentParser(
        description="表结构查询 — 列出字段 / 类型 / 注释 / 分区键",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", help="表名关键字（支持 '项目.表名' 格式自动拆分）")
    parser.add_argument("--project", help="按项目名过滤（对应 databaseName）")
    parser.add_argument("--project-id", type=int, help="按项目数字 ID 过滤（多同名表时精准定位）")
    args = parser.parse_args()

    keyword = args.keyword
    project = args.project
    if not project and "." in keyword:
        parts = keyword.split(".", 1)
        project = parts[0]
        keyword = parts[1]

    client = BFFClient(quiet=True)
    telemetry_start("query_columns.py", module="discovery", keyword=keyword)

    # 1. 搜索表（workspace 级消歧交给 resolve_table_with_workspace）
    from bff_client import resolve_table_with_workspace
    print(f"搜索表: {keyword} ...")
    try:
        table = resolve_table_with_workspace(
            client, keyword, project=project, project_id=args.project_id,
            tag="[columns]")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        telemetry_fail("query_columns.py", "discovery", 1, error=str(e)[:100])
        sys.exit(1)

    table_name = table.get("name", keyword)
    database = table.get("databaseName", "?")
    table_id = _resolve_table_id(table)

    if not table_id:
        print("无法解析 tableId（缺 metaEntityId 和 qualifiedName）", file=sys.stderr)
        telemetry_fail("query_columns.py", "discovery", 1, error="no_table_id")
        sys.exit(1)

    print(f"表: {table_name} (项目: {database})  tableId={table_id}")

    # 2. 调 listColumns
    try:
        columns = client.load("listColumns", tableId=table_id)
    except Exception as e:
        print(f"listColumns 失败: {e}", file=sys.stderr)
        telemetry_fail("query_columns.py", "discovery", 1, error=str(e)[:100])
        sys.exit(1)

    # 3. 输出
    print_columns(table_name, database, columns or [])
    _print_next_steps(table_name, database, len(columns) if columns else 0)

    # 4. 结构化结果
    save_tool_result("query_columns", {
        "table_name": table_name,
        "database": database,
        "table_id": table_id,
        "column_count": len(columns) if columns else 0,
        "columns": [
            {
                "name": c.get("name"),
                "type": c.get("type"),
                "comment": c.get("comment"),
                "partitionKey": c.get("partitionKey"),
                "position": c.get("position"),
            }
            for c in (columns or [])
        ],
    })

    telemetry_end(result={"column_count": len(columns) if columns else 0})


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        telemetry_fail("query_columns.py", "discovery", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
