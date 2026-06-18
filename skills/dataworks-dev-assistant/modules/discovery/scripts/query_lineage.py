#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""表血缘查询工具 — 一条命令完成搜表→getDetail→查血缘

用法:
    python query_lineage.py "表名"
    python query_lineage.py "表名" --direction UP      # 只查上游
    python query_lineage.py "表名" --direction DOWN    # 只查下游
    python query_lineage.py "表名" --depth 5           # 查 5 层（默认 3）
    python query_lineage.py "项目.表名"                 # 自动拆分

输出示例:
    表: m_task_sql (项目: dataworks_analyze, projectId: 23304)

    上游血缘 (2 个):
      maxcompute-table | dataworks_analyze.ods_task_sql | 原始任务SQL
      maxcompute-table | dataworks_analyze.dim_project  | 项目维表

    下游血缘 (10 个):
      maxcompute-table | dataworks_analyze.ads_task_report | 任务报表
      ...
"""

import sys
import argparse

from bff_client import BFFClient, save_tool_result

from search_table import find_table
from telemetry import telemetry_start, telemetry_end, telemetry_fail


def query_lineage(client, entity_id, direction, depth):
    """查询血缘，返回结果列表"""
    try:
        return client.load("ListLineages", entityId=entity_id,
                           direction=direction, depth=depth)
    except Exception as e:
        print(f"查询{direction}血缘失败: {e}", file=sys.stderr)
        return []


def format_lineage(items, direction_label):
    """格式化血缘输出"""
    if not items:
        print(f"\n{direction_label} (0 个)")
        return

    print(f"\n{direction_label} ({len(items)} 个):")
    for item in items:
        et = item.get("entityType", "?")
        name = item.get("name", "?")
        # 尝试从 attributes 提取 qualifiedName
        attrs = item.get("attributes") or {}
        qn = attrs.get("qualifiedName", "") if isinstance(attrs, dict) else ""
        display_name = qn if qn else name
        print(f"  {et:<18} | {display_name}")


def _node_id(name):
    """将表名转为合法的 Mermaid 节点 ID（替换特殊字符）"""
    return name.replace(".", "_").replace("-", "_").replace(" ", "_")


def _display_name(item):
    """提取展示名"""
    attrs = item.get("attributes") or {}
    qn = attrs.get("qualifiedName", "") if isinstance(attrs, dict) else ""
    return qn if qn else item.get("name", "?")


def format_mermaid(center_table, up_items, down_items):
    """输出 Mermaid 流程图"""
    if not up_items and not down_items:
        return

    lines = ["", "Mermaid:", "```mermaid", "graph LR"]
    center_id = _node_id(center_table)
    lines.append(f"  {center_id}[{center_table}]")

    for item in up_items:
        name = _display_name(item)
        nid = _node_id(name)
        lines.append(f"  {nid}[{name}] --> {center_id}")

    for item in down_items:
        name = _display_name(item)
        nid = _node_id(name)
        lines.append(f"  {center_id} --> {nid}[{name}]")

    lines.append("```")
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(
        description="表血缘查询工具 — 一条命令完成搜表→查血缘",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", help="表名关键字（支持 '项目.表名' 格式自动拆分）")
    parser.add_argument("--project", help="按项目名过滤（对应 databaseName）")
    parser.add_argument("--project-id", type=int,
                        help="按 DataWorks workspace ID 过滤（多同名表时启发式选 prod 数据库）")
    parser.add_argument("--direction", choices=["UP", "DOWN", "BOTH"],
                        default="BOTH", help="血缘方向（默认 BOTH）")
    parser.add_argument("--depth", type=int, default=3, help="查询深度（默认 3）")
    args = parser.parse_args()

    telemetry_start("query_lineage.py", module="discovery", keyword=args.keyword)

    keyword = args.keyword
    project = args.project
    # 自动拆分 "项目.表名" 格式
    if not project and "." in keyword:
        parts = keyword.split(".", 1)
        project = parts[0]
        keyword = parts[1]

    client = BFFClient(quiet=True)

    # 1. 搜索表（走上层启发式，支持 workspace 级消歧）
    from bff_client import resolve_table_with_workspace
    print(f"搜索表: {keyword} ...")
    try:
        table = resolve_table_with_workspace(
            client, keyword, project=project, project_id=args.project_id,
            tag="[lineage]")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    table_name = table.get("name", keyword)
    database = table.get("databaseName", "?")
    project_id = table.get("projectId") or 0
    meta_entity_id = table.get("metaEntityId")

    print(f"表: {table_name} (项目: {database}, projectId: {project_id})")

    if not meta_entity_id:
        print("无法获取 metaEntityId，血缘查询需要此字段。", file=sys.stderr)
        print("可能原因: DLF 表不支持血缘查询", file=sys.stderr)
        sys.exit(1)

    # 2. 查询血缘
    up_items = []
    down_items = []

    if args.direction in ("UP", "BOTH"):
        up_items = query_lineage(client, meta_entity_id, "UP", args.depth)
        format_lineage(up_items, "上游血缘")

    if args.direction in ("DOWN", "BOTH"):
        down_items = query_lineage(client, meta_entity_id, "DOWN", args.depth)
        format_lineage(down_items, "下游血缘")

    # Mermaid 图
    format_mermaid(f"{database}.{table_name}", up_items, down_items)

    # 3. 结构化结果
    def _extract(item):
        return {
            "name": item.get("name"),
            "entityType": item.get("entityType"),
            "guid": item.get("guid"),
        }

    telemetry_end(result={"upstream_count": len(up_items), "downstream_count": len(down_items)})
    save_tool_result("query_lineage", {
        "keyword": keyword,
        "table": f"{database}.{table_name}",
        "projectId": project_id,
        "metaEntityId": meta_entity_id,
        "upstream": [_extract(i) for i in up_items],
        "downstream": [_extract(i) for i in down_items],
    })


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("query_lineage.py", "discovery", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("query_lineage.py", "discovery", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
