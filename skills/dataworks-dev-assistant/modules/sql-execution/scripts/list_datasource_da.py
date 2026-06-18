#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据源发现工具 —— 列出工作空间可用的数据源连接并生成 dataSourceCode

用法:
    python list_datasource.py                          # 列出所有工作空间的数据源
    python list_datasource_da.py --project-id 23304       # 指定工作空间
    python list_datasource_da.py --project-id 23304 --engine HOLOGRES  # 只看 Hologres

输出:
    每个可用连接的 dataSourceCode（可直接用于 execute_sql.py --datasource-code）
    结果同时灌入 DuckDB 供 SQL 分析。
"""

import argparse
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from bff_client import BFFClient, save_tool_result
from telemetry import telemetry_start, telemetry_end, telemetry_fail


def discover_datasources(client, project_id, engine_filter=None):
    """发现指定工作空间的所有可用数据源

    链路: listSupportedEngine → listConnection → daCreateDataSource

    Args:
        client: BFFClient 实例
        project_id: 工作空间 ID
        engine_filter: 可选，只查指定引擎（如 "HOLOGRES"）

    Returns:
        list[dict]: [{engine, connection_id, connection_name, env, datasource_code}, ...]
    """
    # Step 1: 获取支持的引擎
    engines = client.load("listSupportedEngine", projectId=str(project_id))
    available_engines = [e for e in engines if e.get("available")]

    if engine_filter:
        engine_filter_upper = engine_filter.upper()
        available_engines = [e for e in available_engines if e["code"] == engine_filter_upper]
        if not available_engines:
            print(f"[list_datasource] 引擎 {engine_filter} 在工作空间 {project_id} 中不可用")
            print(f"[list_datasource] 可用引擎: {', '.join(e['code'] for e in engines if e.get('available'))}")
            return []

    # Step 2: 并行获取每个引擎的连接列表
    all_connections = []

    def _fetch_connections(engine):
        try:
            conns = client.load("listConnection",
                                projectId=str(project_id),
                                engineType=engine["code"],
                                pageNum="1", pageSize="100")
            return [(engine, c) for c in conns]
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=len(available_engines)) as pool:
        futures = {pool.submit(_fetch_connections, e): e for e in available_engines}
        for f in as_completed(futures):
            all_connections.extend(f.result())

    if not all_connections:
        print(f"[list_datasource] 工作空间 {project_id} 无可用连接")
        return []

    # Step 3: 并行为每个连接创建 dataSourceCode（幂等操作）
    results = []

    def _create_datasource(engine, conn):
        try:
            code = client.load("daCreateDataSource",
                               contentMap={"projectId": str(project_id),
                                           "connectionId": str(conn["id"])},
                               engineType=engine["code"],
                               type="DATA_WORKS_CONNECTION")
            return {
                "project_id": str(project_id),
                "engine": engine["code"],
                "connection_id": conn["id"],
                "connection_name": conn.get("name", ""),
                "env": conn.get("envType", ""),
                "datasource_code": code if isinstance(code, str) else str(code),
            }
        except Exception as e:
            print(f"[list_datasource] 创建数据源失败 ({conn.get('name', '')}): {e}", file=sys.stderr)
            return None

    with ThreadPoolExecutor(max_workers=min(10, len(all_connections))) as pool:
        futures = [pool.submit(_create_datasource, eng, conn)
                   for eng, conn in all_connections]
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    # 标记推荐数据源：MaxCompute DEV 环境优先（安全，不影响生产数据）
    for r in results:
        r["recommend"] = (r["engine"] == "MAX_COMPUTE" and r["env"] == "DEV")

    # 排序：推荐项在前，其余按引擎 + 连接名
    results.sort(key=lambda r: (not r["recommend"], r["engine"], r["connection_name"]))
    return results


def main():
    parser = argparse.ArgumentParser(
        description="列出工作空间可用的数据源连接及 dataSourceCode",
    )
    parser.add_argument("--project-id", dest="project_id",
                        help="DataWorks 工作空间 ID（缺失时列出所有工作空间供选择）")
    parser.add_argument("--engine", dest="engine",
                        help="只查指定引擎（如 HOLOGRES、MAX_COMPUTE、MYSQL）")

    args = parser.parse_args()

    telemetry_start("list_datasource_da.py", module="sql-execution", project_id=args.project_id)

    client = BFFClient(quiet=True)

    # 如果未指定 projectId，先列出工作空间
    if not args.project_id:
        projects = client.load("ListProjects", pageSize="100", pageNumber="1")
        if not projects:
            print("[list_datasource] 无可访问的工作空间")
            sys.exit(1)
        print(f"[list_datasource] 共 {len(projects)} 个工作空间:")
        for p in projects:
            print(f"  {p['projectId']:>8}  {p.get('projectName', '')}")
        print(f"\n[list_datasource] → 指定工作空间: python list_datasource_da.py --project-id <ID>")
        sys.exit(0)

    project_id = args.project_id

    # 发现数据源
    results = discover_datasources(client, project_id, engine_filter=args.engine)

    if not results:
        sys.exit(1)

    # 格式化输出
    # 列宽计算
    w_eng = max(len("引擎"), max(len(r["engine"]) for r in results))
    w_name = max(len("连接名"), max(len(r["connection_name"]) for r in results))
    w_code = max(len("dataSourceCode"), max(len(str(r["datasource_code"])) for r in results))

    header = f"{'projectId':<12}  {'引擎':<{w_eng}}  {'连接名':<{w_name}}  {'dataSourceCode':<{w_code}}  环境"
    print(f"\n[list_datasource] 工作空间 {project_id} 的可用数据源:\n")
    print(header)
    print("-" * len(header))
    for r in results:
        tag = " (推荐)" if r.get("recommend") else ""
        print(f"{r['project_id']:<12}  {r['engine']:<{w_eng}}  {r['connection_name']:<{w_name}}  {r['datasource_code']:<{w_code}}  {r['env']}{tag}")

    print(f"\n[list_datasource] 共 {len(results)} 个数据源")
    print(f"[list_datasource] → 执行 SQL: python execute_sql.py \"SQL\" --datasource-code <code>")

    # MaxCompute 分区查询提示
    has_mc = any(r["engine"] == "MAX_COMPUTE" for r in results)
    if has_mc:
        print(f"\n💡 MaxCompute 查询必须加分区条件，避免全表扫描:")
        print(f"   单分区(ds): WHERE ds = MAX_PT('project.table')")
        print(f"   双分区(pt,region): WHERE pt = MAX_PT('project.table') AND region = (SELECT MAX(region) FROM table WHERE pt = MAX_PT('project.table'))")
        print(f"   指定分区: WHERE ds = '20260325'")

    # 灌入 DuckDB（去掉 recommend 标记字段）
    if results and client.loader:
        try:
            db_rows = [{k: v for k, v in r.items() if k != "recommend"} for r in results]
            table_name = client.loader.load("list_datasource", db_rows)
            col_names = ", ".join(results[0].keys())
            print(f"[{table_name}] {len(results)} 条 | {col_names}")
        except Exception:
            pass

    telemetry_end(result={"datasource_count": len(results)})
    # 保存结构化结果
    save_tool_result("list_datasource", {
        "summary": f"工作空间 {project_id} 共 {len(results)} 个数据源",
        "project_id": project_id,
        "datasource_count": len(results),
        "datasources": results,
    })


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("list_datasource_da.py", "sql-execution", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("list_datasource_da.py", "sql-execution", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
