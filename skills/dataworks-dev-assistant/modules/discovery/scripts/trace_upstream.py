#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上游血缘递归追溯工具 —— 自动构建依赖链并定位根因

用法:
    python trace_upstream.py "表名关键字"
    python trace_upstream.py "表名关键字" --max-depth 5

功能:
    1. 搜索目标表，加载全量分区到 DuckDB 分析维度状态
    2. 递归追溯上游血缘，构建完整依赖树
    3. 检查各上游表的分区维度对齐情况
    4. 搜索相关节点，检查 deployStatus
    5. 输出依赖树 + 根因分析 + 排查建议

输出示例:
    m_task_sql  (最新分区: ds=20250803)
    ├── sync_cn_odps_m_task  (mc_table, 最新分区: ds=20250803) ⚠️ 疑似根因
    └── dim_project_info_d  (mc_table, 最新分区: ds=20250318) ✅

    【根因】节点 m_task_sql_group (deployStatus=0 已下线)
    【停产维度】region=group 停在 ds=20250803（其他维度正常到 20260317）
    【链路】sync_cn_odps_m_task → m_task_sql_group → m_task_sql
"""

import sys
import re
import argparse

from bff_client import BFFClient, save_tool_result
from duckdb_loader import DuckDBLoader
from telemetry import telemetry_start, telemetry_end, telemetry_fail


def search_table(client, keyword, project=None):
    """搜索表，返回精确匹配或第一个结果"""
    from search_table import find_table
    try:
        return find_table(client, keyword, project=project)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def analyze_partitions(client, entity_id, table_name, loader):
    """
    加载全量分区到 DuckDB，分析维度状态。

    Args:
        client: BFFClient 实例
        entity_id: 表的 DMA 实体 ID
        table_name: 表名（用于 DuckDB 表名）
        loader: DuckDBLoader 实例

    Returns:
        dict: {
            "latest_partition": str,
            "latest_date": str,            # YYYYMMDD
            "stalled_dims": [{"dimension", "value", "latest", "max_latest"}],
            "partition_count": int,
        }
    """
    result = {
        "latest_partition": None,
        "latest_date": None,
        "stalled_dims": [],
        "partition_count": 0,
    }

    try:
        # 只拉最近的分区（按时间倒序，前 5 页足够判断停产）
        # 避免全量翻页导致限频超时（大表可能有 8000+ 分区）
        partitions = client.load("ListPartitions", tableId=entity_id,
                                   order="Desc", max_pages=5)
    except Exception:
        return result

    if not partitions:
        return result

    result["partition_count"] = len(partitions)
    result["latest_partition"] = partitions[0].get("name", "")
    result["latest_date"] = parse_partition_date(result["latest_partition"])

    # 检测 key=value 多维分区模式
    sample_name = partitions[0].get("name", "")
    if not re.match(r'^[a-zA-Z_]+=.+/.+', sample_name):
        return result

    parts = sample_name.split("/")
    dims = []
    for part in parts:
        if "=" in part:
            key = part.split("=", 1)[0].strip()
            if key:
                dims.append(key)

    if len(dims) < 2:
        return result

    time_dims = [d for d in dims if d in ("ds", "dt", "pt", "bizdate")]
    value_dims = [d for d in dims if d not in time_dims]
    ref_time = time_dims[0] if time_dims else None

    if not ref_time or not value_dims:
        return result

    try:
        tbl = loader.load(f"_trace_{table_name}", partitions)
        if not tbl:
            return result

        view = f"{tbl}_expanded"
        select_parts = [f'"{tbl}".*']
        for dim in dims:
            select_parts.append(
                f"regexp_extract(\"name\", '{re.escape(dim)}=([^/]*)', 1) AS \"{dim}\""
            )
        loader.db.execute(f'DROP VIEW IF EXISTS "{view}"')
        loader.db.execute(
            f'CREATE VIEW "{view}" AS SELECT {", ".join(select_parts)} FROM "{tbl}"'
        )

        for dim in value_dims:
            rows = loader.fetch(f'''
                SELECT "{dim}", MAX("{ref_time}") as latest
                FROM "{view}"
                WHERE "{dim}" IS NOT NULL AND "{dim}" != ''
                GROUP BY "{dim}"
                ORDER BY latest DESC
            ''')
            if rows:
                valid_dates = [r["latest"] for r in rows if r.get("latest")]
                if not valid_dates:
                    continue
                max_latest = max(valid_dates)
                for r in rows:
                    if r["latest"] != max_latest:
                        result["stalled_dims"].append({
                            "dimension": dim,
                            "value": r[dim],
                            "latest": r["latest"],
                            "max_latest": max_latest,
                        })

    except Exception as e:
        print(f"[trace] 分区维度分析出错: {e}", file=sys.stderr)

    return result


def parse_partition_date(partition_str):
    """从分区名提取日期 YYYYMMDD"""
    if not partition_str:
        return None
    m = re.search(r"(\d{8})", partition_str)
    if m:
        return m.group(1)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", partition_str)
    if m:
        return m.group(1) + m.group(2) + m.group(3)
    return None


def search_related_nodes(client, table_name, project_id):
    """搜索与表相关的节点，检查 deployStatus"""
    try:
        nodes = client.load("searchBatchEntities", keyword=table_name,
                            projectId=int(project_id), pageSize=50, pageNum=1,
                            scene="DATAWORKS_PROJECT")
        if not nodes:
            return []
        return [{
            "name": n.get("name", ""),
            "entityId": n.get("entityId", ""),
            "deployStatus": n.get("deployStatus", ""),
            "owner": n.get("ownerName", n.get("owner", "")),
        } for n in nodes]
    except Exception:
        return []


def trace_upstream(client, entity_id, entity_name, entity_type, max_depth=3, depth=0, visited=None):
    """递归追溯上游血缘，构建依赖树"""
    if visited is None:
        visited = set()

    node = {
        "name": entity_name,
        "type": entity_type or "",
        "id": entity_id,
        "partition": None,
        "partition_date": None,
        "children": [],
        "error": None,
    }

    if entity_id in visited:
        node["error"] = "循环引用"
        return node
    if depth > max_depth:
        node["error"] = f"超过最大深度 {max_depth}"
        return node
    visited.add(entity_id)

    # 查表的最新分区
    if "table" in node["type"].lower():
        try:
            partitions = client.load("ListPartitions", tableId=entity_id,
                                               order="Desc", pageSize="1", max_pages=1)
            if partitions:
                node["partition"] = partitions[0].get("name", "unknown")
                node["partition_date"] = parse_partition_date(node["partition"])
            else:
                node["partition"] = "无分区"
        except Exception:
            pass

    # 递归查上游（按 id 去重，避免同名实体重复展开）
    try:
        upstreams = client.load("ListLineages", entityId=entity_id, direction="UP")
        if upstreams:
            seen_ids = set()
            skipped = 0
            for up in upstreams:
                up_id = up.get("id", "")
                if up_id in seen_ids:
                    skipped += 1
                    continue
                seen_ids.add(up_id)
                child = trace_upstream(
                    client,
                    up_id,
                    up.get("name", "unknown"),
                    up.get("entityType", ""),
                    max_depth=max_depth,
                    depth=depth + 1,
                    visited=visited,
                )
                node["children"].append(child)
            if skipped > 0:
                node["children"].append({
                    "name": f"（另有 {skipped} 个重复上游已省略）",
                    "type": "", "id": "", "partition": None,
                    "partition_date": None, "children": [], "error": None,
                })
    except Exception as e:
        node["error"] = str(e)

    return node


def collect_all_nodes(tree, result=None):
    """扁平化收集树中所有节点"""
    if result is None:
        result = []
    result.append(tree)
    for child in tree.get("children", []):
        collect_all_nodes(child, result)
    return result


def find_root_cause(tree, target_date):
    """在依赖树中找根因：分区日期 <= 目标表分区日期的最上游节点"""
    all_nodes = collect_all_nodes(tree)
    table_nodes = [n for n in all_nodes if n["partition_date"]]

    if not table_nodes or not target_date:
        return None

    upstream_nodes = [n for n in table_nodes if n["id"] != tree["id"]]
    if not upstream_nodes:
        return None

    upstream_nodes.sort(key=lambda n: n["partition_date"] or "99999999")
    oldest = upstream_nodes[0]
    if oldest["partition_date"] and oldest["partition_date"] <= target_date:
        return oldest
    return None


def print_tree(node, target_date=None, root_cause_id=None, prefix="", is_last=True, is_root=True):
    """打印依赖树"""
    if is_root:
        connector = ""
        child_prefix = ""
    else:
        connector = "└── " if is_last else "├── "
        child_prefix = prefix + ("    " if is_last else "│   ")

    line = f"{prefix}{connector}{node['name']}"

    annotations = []
    if node["type"] and not is_root:
        short_type = node["type"].replace("maxcompute-", "mc_")
        annotations.append(short_type)
    if node["partition"]:
        annotations.append(f"最新分区: {node['partition']}")
    if node.get("error"):
        annotations.append(node["error"])

    if annotations:
        line += f"  ({', '.join(annotations)})"

    if node["id"] == root_cause_id:
        line += "  ⚠️ 疑似根因"
    elif node["partition_date"] and target_date and node["partition_date"] > target_date and not is_root:
        line += "  ✅"

    print(line)

    children = node.get("children", [])
    for i, child in enumerate(children):
        print_tree(
            child,
            target_date=target_date,
            root_cause_id=root_cause_id,
            prefix=child_prefix,
            is_last=(i == len(children) - 1),
            is_root=False,
        )


def trace_path_to_root_cause(tree, root_cause_id, path=None):
    """从根因节点回溯到目标表的路径"""
    if path is None:
        path = []
    path.append(tree["name"])
    if tree["id"] == root_cause_id:
        return list(reversed(path))
    for child in tree.get("children", []):
        result = trace_path_to_root_cause(child, root_cause_id, path[:])
        if result:
            return result
    return None


def _build_summary(stalled, offline_nodes, root_cause):
    """构建一行摘要文本"""
    parts = []
    if stalled:
        s = stalled[0]
        parts.append(f"{s['dimension']}={s['value']} 停在 {s['latest']}")
    if offline_nodes:
        parts.append(f"根因: {offline_nodes[0]['name']} (已下线)")
    elif root_cause:
        parts.append(f"根因: {root_cause['name']} 停在 {root_cause.get('partition', '?')}")
    return "; ".join(parts) if parts else "未发现异常"


def main():
    parser = argparse.ArgumentParser(
        description="上游血缘递归追溯工具 — 一条命令完成分区停产排查",
        epilog="输出: 停产维度 + 依赖树 + 节点状态(deployStatus) + 根因分析 + 建议措施",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", help="表名关键字（支持 '项目.表名' 格式自动拆分）")
    parser.add_argument("--project", help="按项目名过滤（对应 databaseName）")
    parser.add_argument("--max-depth", type=int, default=3, help="最大追溯深度（默认 3）")
    args = parser.parse_args()

    telemetry_start("trace_upstream.py", module="discovery", keyword=args.keyword)

    keyword = args.keyword
    project = args.project
    if not project and "." in keyword:
        parts = keyword.split(".", 1)
        project = parts[0]
        keyword = parts[1]

    client = BFFClient(quiet=True)
    loader = client.loader or DuckDBLoader()

    # 1. 搜索目标表
    print(f"搜索表: {keyword} ...")
    table = search_table(client, keyword, project=project)
    table_id = table.get("metaEntityId")
    if not table_id:
        # fallback: 从 qualifiedName 转换
        qn = table.get("qualifiedName", "")
        if qn:
            parts = qn.split(".")
            table_id = parts[0] + ":::" + "::".join(parts[1:])
        else:
            print(f"搜索结果缺少 metaEntityId/qualifiedName 字段: {table}", file=sys.stderr)
            sys.exit(1)
    table_name = table.get("name", keyword)
    project_id = table.get("projectId") or 0
    print(f"找到: {table_name} (ID: {table_id})")

    # 2. 分析目标表的分区维度（用独立的 DuckDB loader）
    print(f"\n分析分区维度...")
    partition_info = analyze_partitions(client, table_id, table_name, loader)

    if partition_info["partition_count"] > 0:
        print(f"分区数: {partition_info['partition_count']}, 最新: {partition_info['latest_partition']}")
    else:
        print("无分区数据")

    # 3. 输出停产维度
    stalled = partition_info["stalled_dims"]
    if stalled:
        print(f"\n⚠️ 发现停产维度:")
        for s in stalled:
            print(f"  {s['dimension']}={s['value']}: 停在 {s['latest']}（正常应到 {s['max_latest']}）")

    # 4. 递归追溯上游血缘
    print(f"\n递归追溯上游血缘（最大深度: {args.max_depth}）...\n")
    tree = trace_upstream(
        client,
        entity_id=table_id,
        entity_name=table_name,
        entity_type=table.get("entityType", "maxcompute-table"),
        max_depth=args.max_depth,
    )

    # 5. 分析表级根因
    target_date = tree["partition_date"]
    root_cause = find_root_cause(tree, target_date)
    root_cause_id = root_cause["id"] if root_cause else None

    # 6. 输出依赖树
    print("=" * 60)
    print("依赖树")
    print("=" * 60)
    print_tree(tree, target_date=target_date, root_cause_id=root_cause_id)

    # 7. 搜索相关节点，检查 deployStatus
    print()
    print("=" * 60)
    print("节点状态")
    print("=" * 60)
    nodes = search_related_nodes(client, table_name, project_id)
    offline_nodes = []
    if nodes:
        for n in nodes:
            status = "已下线" if str(n["deployStatus"]) == "0" else "已发布"
            marker = " ⚠️" if str(n["deployStatus"]) == "0" else ""
            print(f"  {n['name']}: deployStatus={n['deployStatus']}（{status}）, 负责人={n['owner']}{marker}")
            if str(n["deployStatus"]) == "0":
                offline_nodes.append(n)
    else:
        print("  未找到相关节点")

    # 8. 综合根因分析
    print()
    print("=" * 60)
    print("根因分析")
    print("=" * 60)

    if stalled and offline_nodes:
        # 最佳情况：同时发现停产维度和下线节点
        for s in stalled:
            # 尝试匹配节点名和停产维度值（优先短名称，更精确）
            matched_node = None
            candidates = [n for n in offline_nodes if s["value"] in n["name"]]
            if candidates:
                # 名称越短越精确（m_task_sql_group 优于 dws_dw_m_task_sql_embedding_group）
                candidates.sort(key=lambda n: len(n["name"]))
                matched_node = candidates[0]
            if not matched_node:
                matched_node = offline_nodes[0]

            print(f"【停产维度】{s['dimension']}={s['value']} 停在 {s['latest']}（正常应到 {s['max_latest']}）")
            print(f"【根因节点】{matched_node['name']} (deployStatus=0 已下线)")
            print(f"【负责人】{matched_node['owner']}")

        if root_cause:
            path = trace_path_to_root_cause(tree, root_cause_id)
            if path:
                print(f"【上游链路】{' → '.join(path)}")

        print(f"\n【建议措施】")
        print(f"  1. 联系负责人确认下线原因")
        print(f"  2. 如需恢复：重新发布节点并补数据")
        print(f"  3. 如已废弃：通知下游使用方数据已停止维护")

    elif stalled:
        # 有停产维度但没找到下线节点
        for s in stalled:
            print(f"【停产维度】{s['dimension']}={s['value']} 停在 {s['latest']}（正常应到 {s['max_latest']}）")
        print(f"【建议】未发现下线节点，可能是调度暂停或资源不足。检查任务实例状态。")

    elif root_cause:
        # 表级根因
        path = trace_path_to_root_cause(tree, root_cause_id)
        path_str = " → ".join(path) if path else root_cause["name"]
        print(f"【根因】{root_cause['name']} 最新分区停在 {root_cause['partition']}，导致下游链路断裂")
        print(f"【链路】{path_str}")

    else:
        all_nodes = collect_all_nodes(tree)
        table_nodes = [n for n in all_nodes if n["partition_date"] and n["id"] != tree["id"]]
        if not table_nodes:
            print("未找到上游表的分区信息，无法自动定位根因。")
            print("建议手动检查上游节点的任务实例状态。")
        elif offline_nodes:
            print(f"上游表分区均正常，但发现 {len(offline_nodes)} 个下线节点:")
            for n in offline_nodes:
                print(f"  ⚠️ {n['name']} (deployStatus=0), 负责人={n['owner']}")
        else:
            print("所有上游表分区正常，所有相关节点均在线。")
            print("表当前处于正常产出状态。")

    telemetry_end(result={"stalled_count": len(stalled), "offline_count": len(offline_nodes)})
    # 结构化结果输出（供 agent 读取）
    save_tool_result("trace", {
        "table_name": table_name,
        "table_id": table_id,
        "partition_info": partition_info,
        "stalled_dims": stalled,
        "offline_nodes": offline_nodes,
        "root_cause": {
            "name": root_cause["name"],
            "partition": root_cause.get("partition"),
            "id": root_cause["id"],
        } if root_cause else None,
        "summary": _build_summary(stalled, offline_nodes, root_cause),
    })


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("trace_upstream.py", "discovery", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("trace_upstream.py", "discovery", 1, error=str(e)[:100])
        print(f"\n[error] {e}")
        print(f"  如需上报此问题: report_bug.py \"{e}\" --script trace_upstream.py")
        sys.exit(1)
