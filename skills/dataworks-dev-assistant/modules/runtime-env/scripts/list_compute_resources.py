#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列工作空间计算资源（MC/StarRocks/EMR/Hologres 集群实例）

listComputeResources 返回的"计算资源"是**扫描主体/执行引擎实例**，与 listDataSourceV2 的"数据源"概念有重叠：
  - StarRocks/EMR/Hologres/MC 这类自建数仓 → 既是数据源又是计算资源
  - MySQL/Oracle 等纯外部数据源 → 只在 listDataSourceV2
场景用途：创建识别任务 / 看可用于 SQL 执行的引擎实例 / 审计集群分布

用法:
    python list_compute_resources.py --project-name autotest             # 列全部
    python list_compute_resources.py --project-id 14255
    python list_compute_resources.py --project-name autotest --type starrocks   # 按类型
    python list_compute_resources.py --project-name autotest --detail <name>    # 单条详情
"""

import argparse
import json
import sys

from bff_client import BFFClient, save_tool_result
from runtime import resolve_project_id
from telemetry import telemetry_end, telemetry_fail


_ENV_LABEL = {"PROD": "生产", "DEV": "开发"}

# 常见 type 别名 → 服务端认识的内部值（基于 CalcEngineType enum：ODPS/EMR/HOLO/...）
_TYPE_ALIAS = {
    "hologres": "holo", "max_compute": "odps", "maxcompute": "odps",
    "starrocks_serverless": "starrocks", "adb_pg": "hybriddb_for_postgresql",
    "hadoop_cdh_3": "hadoop_cdh", "hadoop_cdh_5": "hadoop_cdh",
}


def _normalize_type(t):
    return _TYPE_ALIAS.get((t or "").lower(), t)


def _flatten(rows):
    """listComputeResources 外层按 type 分组，内层 computeResource[]。打平为 [{type, name, crId, connProps, ...}]"""
    out = []
    for group in rows or []:
        gtype = group.get("type") or ""
        for cr in (group.get("computeResource") or []):
            item = {
                "type": gtype or (cr.get("type") or ""),
                "crId": cr.get("computeResourceId"),
                "name": cr.get("name", ""),
                "description": cr.get("description", ""),
                "default": cr.get("whetherDefault", False),
                "projectId": cr.get("projectId"),
                "createTime": cr.get("createTime"),
                "connectionProperties": cr.get("connectionProperties") or {},
            }
            out.append(item)
    return out


def _fmt_conn(conn):
    """从 connectionProperties 提取关键信息（脱敏 ak/sk/password）"""
    if not isinstance(conn, dict):
        return ""
    keys = ("instanceId", "instanceName", "endpoint", "regionId",
            "envType", "cu", "feHosts", "domain", "project", "instanceType")
    parts = [f"{k}={conn[k]}" for k in keys if conn.get(k)]
    return " | ".join(parts)


def list_compute(client, project_id, types=None, keyword=None, env=None,
                 default_only=False):
    """服务端过滤 + 真分页。pageSize=500 是服务端硬上限（超过会被重置为 10，慎传）"""
    params = {"projectId": project_id, "pageNumber": 1, "pageSize": 500}
    if types:
        # 多值：Spring @ModelAttribute List<String> 绑定用 repeated query param（types=a&types=b）
        params["types"] = list(types) if len(types) > 1 else types[0]
    if keyword:
        params["keyword"] = keyword
    if env:
        params["envType"] = env
    if default_only:
        params["whetherDefault"] = "true"
    rows = client.load("listComputeResources", **params) or []
    return _flatten(rows)


def print_summary(items, pid):
    if not items:
        print(f"工作空间 {pid} 无计算资源")
        return

    # 按 type 分组
    from collections import defaultdict
    by_type = defaultdict(list)
    for it in items:
        by_type[it["type"] or "unknown"].append(it)

    print(f"工作空间 {pid} 计算资源: {len(items)} 个（{len(by_type)} 种类型）")
    print()
    width = max((len(i["name"]) for i in items), default=10)
    print(f"  {'类型':<12} {'名称'.ljust(width)}  {'crId':<9} {'默认':<4} {'环境':<6} 关键连接信息")
    for t in sorted(by_type):
        for i in by_type[t]:
            conn = i["connectionProperties"]
            env = conn.get("envType", "")
            conn_str = _fmt_conn(conn)[:80]
            flag = "★" if i.get("default") else ""
            print(f"  {t:<12} {i['name'].ljust(width)}  {str(i.get('crId') or '-'):<9} {flag:<4} {env:<6} {conn_str}")

    print()
    print("━━ 概念提醒 ━━")
    print("  计算资源 = 执行引擎的实例（跑 SQL / 被扫描的主体）")
    print("  部分类型（starrocks/emr/hologres/odps）同时会出现在数据源列表")
    print()
    print(f"→ 看完整数据源视图（含外部 MySQL/Oracle 等）: browse_datasource.py --project-id {pid}")
    print(f"→ 看某个计算资源详情:  list_compute_resources.py --project-id {pid} --detail <name>")


def print_detail(items, name):
    target = next((i for i in items if i["name"] == name), None)
    if not target:
        print(f"未找到计算资源 name={name}")
        print(f"可选: {[i['name'] for i in items]}")
        sys.exit(1)
    conn = target.pop("connectionProperties", {})
    # 脱敏
    if isinstance(conn, dict):
        for k in ("password", "accessKey", "secretKey", "ak", "sk", "token"):
            if k in conn:
                conn[k] = "***"
    print(f"━━ {target['name']} ━━")
    for k, v in target.items():
        print(f"  {k}: {v}")
    print(f"  connectionProperties: {json.dumps(conn, ensure_ascii=False, indent=2)}")


def main():
    parser = argparse.ArgumentParser(description="列工作空间计算资源（集群/引擎实例）")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--project-name", help="工作空间名")
    parser.add_argument("--type", help="按类型过滤（服务端）：starrocks/emr/odps/hologres/maxgraph/... 逗号分隔多值")
    parser.add_argument("--keyword", help="按 name 模糊搜（服务端）")
    parser.add_argument("--env", choices=["dev", "prod"], help="按环境过滤（服务端）")
    parser.add_argument("--default-only", action="store_true", help="只看默认计算资源")
    parser.add_argument("--detail", help="看某个计算资源的详情 (--detail <name>)")
    args = parser.parse_args()

    client = BFFClient(quiet=True)
    pid = resolve_project_id(client, args.project_id, args.project_name, tag="[list_compute]")
    if not pid:
        sys.exit(1)

    types = [_normalize_type(t.strip()) for t in args.type.split(",")] if args.type else None
    items = list_compute(client, pid,
                         types=types, keyword=args.keyword,
                         env=args.env, default_only=args.default_only)

    if args.detail:
        print_detail(items, args.detail)
    else:
        print_summary(items, pid)

    save_tool_result("list_compute_resources", {
        "project_id": pid,
        "count": len(items),
        "types": sorted(set(i["type"] for i in items)),
    })
    telemetry_end(result={"count": len(items)})


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        telemetry_fail("list_compute_resources.py", "runtime-env", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
