#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字段画像 —— 一条命令看某字段的 distinct / null 率 / 值分布

用法:
    python profile_column.py "表名" --column status
    python profile_column.py "项目.表名" --column amount      # 数值字段自动加 MIN/MAX/AVG
    python profile_column.py "表名" --columns col1,col2       # 多字段（分别跑）
    python profile_column.py "表名" --column k --top 20       # TOP 20 值分布
    python profile_column.py "表名" --column k --where "ds=20260101"

输出:
    对每个字段跑两条 SQL：
      1. 总体: COUNT(1), COUNT(col), COUNT(DISTINCT col), NULL 率 [+MIN/MAX/AVG 对数值字段]
      2. TOP N 值分布（非 NULL）

自动:
    - 分区表自动加 WHERE ds=MAX_PT('proj.table')
    - 数值类型（bigint/double/decimal/...）额外统计 MIN/MAX/AVG
    - 自动选 DEV MaxCompute 数据源
    - 权限/分区错误给出申请链路 / 手动分区建议
"""

import argparse
import sys
import os

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DISCOVERY_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", "discovery", "scripts"))
if _DISCOVERY_DIR not in sys.path:
    sys.path.insert(0, _DISCOVERY_DIR)
# 复用 sample_table 的权限错误识别 + apply 引导
from sample_table import _print_failure_next_steps


# 数值类型前缀（用于判断是否额外算 MIN/MAX/AVG）
_NUMERIC_PREFIXES = ("int", "bigint", "smallint", "tinyint", "double", "float",
                     "decimal", "numeric")


def _is_numeric(col_type):
    if not col_type:
        return False
    t = col_type.lower().strip()
    return any(t.startswith(p) for p in _NUMERIC_PREFIXES)


def _build_partition_where(database, table_name, partition_cols, user_where):
    """返回 WHERE 子句（含 WHERE 关键字），没有则返回空串"""
    if user_where:
        return f"WHERE {user_where}"
    if not partition_cols:
        return ""
    full_name = f"{database}.{table_name}"
    parts = []
    if len(partition_cols) >= 1:
        parts.append(f"{partition_cols[0]} = MAX_PT('{full_name}')")
    if len(partition_cols) == 2:
        p1, p2 = partition_cols
        parts.append(
            f"{p2} = (SELECT MAX({p2}) FROM {full_name} "
            f"WHERE {p1} = MAX_PT('{full_name}'))"
        )
    return f"WHERE {' AND '.join(parts)}" if parts else ""


def _build_stats_sql(database, table_name, col, col_type, where_clause):
    """总体画像 SQL"""
    full_name = f"{database}.{table_name}"
    fields = [
        "COUNT(1) AS total_rows",
        f"COUNT({col}) AS non_null_count",
        f"COUNT(DISTINCT {col}) AS distinct_count",
    ]
    if _is_numeric(col_type):
        fields += [
            f"MIN({col}) AS min_val",
            f"MAX({col}) AS max_val",
            f"AVG({col}) AS avg_val",
        ]
    return f"SELECT {', '.join(fields)} FROM {full_name} {where_clause}".strip()


def _build_topn_sql(database, table_name, col, where_clause, top_n):
    """TOP N 值分布 SQL"""
    full_name = f"{database}.{table_name}"
    extra = f"{col} IS NOT NULL"
    if where_clause:
        merged = where_clause + f" AND {extra}"
    else:
        merged = f"WHERE {extra}"
    return (f"SELECT {col}, COUNT(*) AS cnt FROM {full_name} {merged} "
            f"GROUP BY {col} ORDER BY cnt DESC LIMIT {top_n}")


def _print_stats(col, col_type, rows):
    """打印总体统计"""
    if not rows:
        print(f"  (无数据)")
        return
    r = rows[0]
    total = int(r.get("total_rows") or 0)
    non_null = int(r.get("non_null_count") or 0)
    distinct = int(r.get("distinct_count") or 0)
    null_count = total - non_null
    null_rate = (null_count / total * 100) if total else 0
    dup_ratio = (non_null / distinct) if distinct else 0

    print(f"  总行数:     {total:,}")
    print(f"  非空:       {non_null:,}  (NULL {null_count:,} 条，占 {null_rate:.1f}%)")
    print(f"  distinct:   {distinct:,}" + (f"  (平均 {dup_ratio:.1f} 行/值)" if dup_ratio > 1 else ""))

    if _is_numeric(col_type):
        min_v = r.get("min_val")
        max_v = r.get("max_val")
        avg_v = r.get("avg_val")
        print(f"  数值范围:   min={min_v}  max={max_v}  avg={avg_v}")


def _print_topn(col, rows, total_rows):
    """打印 TOP N 值分布"""
    if not rows:
        print(f"  (无分布)")
        return
    max_cnt = max((int(r.get("cnt") or 0)) for r in rows) if rows else 1
    for r in rows:
        val = r.get(col)
        cnt = int(r.get("cnt") or 0)
        pct = (cnt / total_rows * 100) if total_rows else 0
        bar_len = int(cnt / max_cnt * 30)
        bar = "█" * bar_len
        val_str = str(val) if val is not None else "(NULL)"
        if len(val_str) > 36:
            val_str = val_str[:33] + "..."
        print(f"  {val_str:<38} {cnt:>10,}  {pct:>5.1f}%  {bar}")


def _resolve_datasource(client, project_id, prefer_env=None):
    """默认 DEV（安全路径）；权限不足走 apply_resource_access，不通过切 PROD 绕"""
    from list_datasource_da import discover_datasources
    try:
        datasources = discover_datasources(client, project_id, engine_filter="MAX_COMPUTE")
    except Exception as e:
        print(f"[profile] 数据源发现失败: {e}", file=sys.stderr)
        return None, None
    if not datasources:
        return None, None

    target_env = prefer_env if prefer_env in ("DEV", "PROD") else "DEV"

    primary = [d for d in datasources if d.get("env") == target_env]
    if primary:
        return primary[0]["datasource_code"], target_env

    fallback = [d for d in datasources if d.get("env") != target_env]
    if fallback:
        chosen = fallback[0]
        print(f"[profile] 未找到 {target_env} 环境，回退 {chosen.get('env')}")
        return chosen["datasource_code"], chosen.get("env", "")
    return None, None


def main():
    parser = argparse.ArgumentParser(
        description="字段画像 — distinct / null 率 / 值分布 / 数值范围",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", help="表名关键字（支持 '项目.表名' 格式自动拆分）")
    parser.add_argument("--project", help="按项目名过滤")
    parser.add_argument("--project-id", type=int, help="按项目数字 ID 过滤")
    parser.add_argument("--column", help="字段名（单字段画像）")
    parser.add_argument("--columns", help="字段名列表（逗号分隔，多字段画像）")
    parser.add_argument("--top", type=int, default=10, help="TOP N 值分布（默认 10）")
    parser.add_argument("--where", help="自定义过滤条件（覆盖自动分区）")
    parser.add_argument("--datasource-code", dest="datasource_code",
                        help="直接指定数据源 code；不传则自动选 DEV MaxCompute（安全默认）")
    parser.add_argument("--env", choices=["DEV", "PROD"], default=None,
                        help="强制指定数据源环境（默认 DEV；权限不足时申请权限而非切 PROD）")
    args = parser.parse_args()

    if not args.column and not args.columns:
        print("[profile] 必须指定 --column 或 --columns", file=sys.stderr)
        sys.exit(2)

    keyword = args.keyword
    project = args.project
    if not project and "." in keyword:
        parts = keyword.split(".", 1)
        project = parts[0]
        keyword = parts[1]

    target_cols = []
    if args.column:
        target_cols.append(args.column.strip())
    if args.columns:
        target_cols.extend([c.strip() for c in args.columns.split(",") if c.strip()])

    telemetry_start("profile_column.py", module="sql-execution",
                    keyword=keyword, columns=",".join(target_cols))

    client = BFFClient(quiet=True)

    # 1. 搜索表（workspace 级消歧交给 resolve_table_with_workspace）
    from bff_client import resolve_table_with_workspace
    print(f"[profile] 搜索表: {keyword} ...")
    try:
        table = resolve_table_with_workspace(
            client, keyword, project=project, project_id=args.project_id,
            tag="[profile]")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        telemetry_fail("profile_column.py", "sql-execution", 1, error=str(e)[:100])
        sys.exit(1)

    table_name = table.get("name", keyword)
    database = table.get("databaseName", "?")

    # 2. 字段 + 分区键 + 类型
    table_id = table.get("metaEntityId")
    if not table_id:
        qn = table.get("qualifiedName", "")
        if qn:
            parts = qn.split(".")
            table_id = parts[0] + ":::" + "::".join(parts[1:])

    columns_info = {}
    partition_cols = []
    if table_id:
        try:
            cols = client.load("listColumns", tableId=table_id) or []
            for c in cols:
                n = c.get("name")
                if n and n not in columns_info:
                    columns_info[n] = c
                    if c.get("partitionKey"):
                        partition_cols.append(n)
        except Exception as e:
            print(f"[profile] listColumns 失败: {e}", file=sys.stderr)

    # 3. 校验目标字段
    invalid = [c for c in target_cols if c not in columns_info]
    if invalid and columns_info:
        avail = ", ".join(list(columns_info.keys())[:15])
        print(f"[profile] ❌ 字段不存在: {', '.join(invalid)}", file=sys.stderr)
        print(f"[profile] 可用字段: {avail}", file=sys.stderr)
        telemetry_fail("profile_column.py", "sql-execution", 1, error="invalid_column")
        sys.exit(1)

    print(f"[profile] 表: {database}.{table_name} | 分区: {partition_cols or '无'} | 目标字段: {target_cols}")

    # 4. 数据源
    datasource_code = args.datasource_code
    if not datasource_code:
        target_pid = args.project_id or table.get("projectId")
        if not target_pid:
            try:
                projects = client.load("ListProjects", pageSize=100) or []
                for p in projects:
                    if (p.get("projectName") or "").lower() == database.lower():
                        target_pid = p.get("projectId")
                        break
            except Exception:
                pass
        if not target_pid:
            print(f"[profile] 无法确定工作空间 ID，请显式 --project-id 或 --datasource-code", file=sys.stderr)
            sys.exit(1)
        datasource_code, env = _resolve_datasource(
            client, target_pid, prefer_env=args.env)
        if not datasource_code:
            print(f"[profile] 未找到 MaxCompute 数据源 → list_datasource_da.py --project-id {target_pid}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"[profile] 数据源: {datasource_code} ({env})")

    # 5. 逐字段画像
    from execute_sql import execute_readonly
    where_clause = _build_partition_where(database, table_name, partition_cols, args.where)

    results = []
    failed_cols = []  # 记录失败字段，统一输出权限申请引导
    for col in target_cols:
        col_type = columns_info.get(col, {}).get("type", "")
        print(f"\n{'=' * 60}")
        print(f"📊 字段: {col}  (类型: {col_type})")
        print(f"{'=' * 60}")

        # 5a. 总体
        stats_sql = _build_stats_sql(database, table_name, col, col_type, where_clause)
        print(f"  stats SQL: {stats_sql}")
        try:
            stats_rows = execute_readonly(stats_sql, datasource_code=datasource_code, timeout=120)
        except SystemExit:
            print(f"[profile] 字段 {col} stats 失败，跳过")
            failed_cols.append(col)
            continue

        print()
        _print_stats(col, col_type, stats_rows)
        total_rows = int(stats_rows[0].get("total_rows") or 0) if stats_rows else 0

        # 5b. TOP N
        topn_sql = _build_topn_sql(database, table_name, col, where_clause, args.top)
        try:
            topn_rows = execute_readonly(topn_sql, datasource_code=datasource_code, timeout=120)
        except SystemExit:
            topn_rows = []
            print(f"[profile] 字段 {col} TOP N 失败，跳过")

        print(f"\n  TOP {args.top} 值分布:")
        _print_topn(col, topn_rows, total_rows)

        results.append({
            "column": col,
            "type": col_type,
            "stats": stats_rows[0] if stats_rows else {},
            "top_n": topn_rows,
        })

    # 全部失败时检查是否权限问题，输出 apply 引导
    if not results and failed_cols:
        _print_failure_next_steps(database, table_name,
                                  target_pid=args.project_id or table.get("projectId"))

    # 下一步
    print(f"\n{'─' * 60}")
    print(f"下一步")
    print(f"{'─' * 60}")
    print(f"  采样数据: sample_table.py \"{database}.{table_name}\"")
    print(f"  自定义 SQL: execute_sql.py \"<SQL>\" --datasource-code {datasource_code}")

    save_tool_result("profile_column", {
        "database": database,
        "table_name": table_name,
        "columns": target_cols,
        "where": where_clause,
        "datasource_code": datasource_code,
        "results": results,
    })

    telemetry_end(result={"column_count": len(target_cols), "succeeded": len(results)})


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        telemetry_fail("profile_column.py", "sql-execution", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
