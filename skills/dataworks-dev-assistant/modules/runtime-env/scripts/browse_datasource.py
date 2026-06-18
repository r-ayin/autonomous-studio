#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作空间数据源档案 — 唯一的「查数据源」入口

合并 4 路 API，按 name 去重，输出每条数据源的能力白名单 + 即拷命令：
  - listDataSourceV2    （工作空间超集，元信息）
  - getDataSourceList    （DI 侧：运行时状态、id、operator、status、connection 连接信息）
  - listDataSourcesProject（DQC 支持类型白名单）
  - listSupportedEngine  （SQL 执行引擎白名单）

用法：
    browse_datasource.py --project-name autotest           # 列全部（按 name 排序）
    browse_datasource.py --project-id 14255
    browse_datasource.py --project-name autotest <关键字>    # 按 name 模糊过滤
    browse_datasource.py --project-name autotest --type odps  # 按类型过滤
    browse_datasource.py --project-name autotest --for sql    # 只列能跑 SQL 的
    browse_datasource.py --project-name autotest --for di_src
    browse_datasource.py --project-name autotest --for di_dst
    browse_datasource.py --project-name autotest --for dqc
    browse_datasource.py --project-name autotest --detail <name>  # 单条详情
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from bff_client import BFFClient, save_tool_result
from runtime import resolve_project_id
from telemetry import telemetry_end, telemetry_fail


ENV_TYPE_LABEL = {1: "DEV", 2: "PROD"}
CONN_KEYS = ("endpoint", "project", "domain", "tag", "region",
             "dsVersion", "authType")


def _parse_conn(raw):
    """从 JSON 字符串或 dict 提取关键连接字段，脱敏 ak/sk。"""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {}
    if not isinstance(raw, dict):
        return {}
    return {k: raw.get(k) for k in CONN_KEYS if raw.get(k)}


DI_SOURCE_ONLY_TYPES = {
    # 实时/流式数据源仅能做同步源端，做不了目标
    "kafka", "datahub", "datahubtt", "loghub", "mysqlbinlog", "oraclecdc",
}

# 数据源 type → listSupportedEngine.code 映射
# （前者为用户视角的 type，后者为 SQL 执行引擎的 code）
SQL_ENGINE_ALIAS = {
    "odps": "max_compute",
    "holo": "hologres",
    "starrocks": "star_rocks",
    "mysql": "mysql",
    "ots": "ots",
    "emr": "emr_spark_sql",
}


def fetch_v2(client, pid):
    """listDataSourceV2 单页拉取（pageSize 上限 500；超出则在输出里标注）"""
    r = client.load("listDataSourceV2", projectId=pid,
                    pageNumber=1, pageSize=500)
    rows = r.get("dataSources", []) if isinstance(r, dict) else []
    total = r.get("totalCount", len(rows)) if isinstance(r, dict) else len(rows)
    return rows, total


def fetch_di(client, pid):
    """getDataSourceList 单页拉取（pageSize 上限 500）"""
    r = client.load("getDataSourceList", projectId=pid,
                    pageNumber=1, pageSize=500)
    rows = r if isinstance(r, list) else []
    return rows


def fetch_dqc_types(client, pid):
    """listDataSourcesProject → DQC 支持的类型白名单 (innerName 小写集)"""
    try:
        r = client.load("listDataSourcesProject", projectId=pid)
        rows = r.get("data") if isinstance(r, dict) else r
        if isinstance(rows, list):
            return {str(x.get("innerName", "")).lower() for x in rows}
    except Exception:
        pass
    return set()


def fetch_sql_engines(client, pid):
    """listSupportedEngine → SQL 可执行引擎 code 集 (小写)"""
    try:
        r = client.load("listSupportedEngine", projectId=str(pid))
        rows = r.get("data") if isinstance(r, dict) else r
        if isinstance(rows, list):
            return {str(x.get("code", "")).lower() for x in rows if x.get("code")}
    except Exception:
        pass
    return set()


def fetch_compute(client, pid):
    """listComputeResources → 计算资源（集群实例）。返回 {name: {type, crId, instanceId, ...}}

    对于 StarRocks/EMR/Hologres/MC 这类自建数仓，它们既是数据源又是计算资源；
    此函数将它们作为第 5 路数据源来源，与 V2/DI 合并后在输出里标 in_compute=True。
    """
    try:
        rows = client.load("listComputeResources", projectId=pid,
                           pageNumber=1, pageSize=200) or []
    except Exception:
        return {}
    # listComputeResources 外层按 type 分组，内层 computeResource[]
    result = {}
    for group in rows:
        gtype = (group.get("type") or "").lower()
        for cr in (group.get("computeResource") or []):
            name = cr.get("name")
            if not name:
                continue
            conn = cr.get("connectionProperties") or {}
            result[name] = {
                "name": name,
                "type": gtype or (cr.get("type") or "").lower(),
                "crId": cr.get("computeResourceId"),
                "instanceId": conn.get("instanceId"),
                "instanceName": conn.get("instanceName"),
                "envType": conn.get("envType"),
                "regionId": conn.get("regionId"),
                "default": cr.get("whetherDefault", False),
            }
    return result


def _v2_inner(v2):
    """V2 row 的嵌套 dataSource[0]（含 description、connectionProperties）。"""
    ds = v2.get("dataSource") if v2 else None
    if isinstance(ds, list) and ds and isinstance(ds[0], dict):
        return ds[0]
    return {}


def merge(v2_rows, di_rows):
    """按 name 合并。V2 是超集元信息，DI 是运行时状态投影。"""
    di_by_name = {r.get("name"): r for r in di_rows if r.get("name")}
    v2_by_name = {r.get("name"): r for r in v2_rows if r.get("name")}

    all_names = set(v2_by_name) | set(di_by_name)
    merged = []
    for name in sorted(all_names):
        v2 = v2_by_name.get(name, {})
        di = di_by_name.get(name, {})
        v2_inner = _v2_inner(v2)

        # 连接信息：优先 DI.connection，退回 V2.connectionProperties
        conn = _parse_conn(di.get("connection")) \
            or _parse_conn(v2_inner.get("connectionProperties"))

        merged.append({
            "name": name,
            "type": (v2.get("type") or di.get("type") or "").lower(),
            "subType": di.get("subType") or v2_inner.get("subType"),
            "displayName": di.get("displayName") or v2_inner.get("name"),
            "description": di.get("description") or v2_inner.get("description"),
            "projectId": v2.get("projectId") or di.get("projectId"),
            "id": di.get("id") or v2_inner.get("dataSourceId"),
            "operator": di.get("operator") or v2_inner.get("createUser"),
            "status": di.get("status"),
            "envType": di.get("envType"),
            "bindingCalcEngineId": di.get("bindingCalcEngineId")
                or v2_inner.get("bindEngineId"),
            "connection": conn,
            "in_v2": bool(v2),
            "in_di": bool(di),
        })
    return merged


def _sql_engine_code(t):
    """type → engine code；命中 alias 映射才算可跑 SQL"""
    if not t:
        return None
    return SQL_ENGINE_ALIAS.get(t.lower())


def classify(ds, sql_engines, dqc_types):
    """返回 {sql, di_src, di_dst, dqc, probe} 能力标记字典"""
    t = (ds.get("type") or "").lower()
    engine_code = _sql_engine_code(t)
    caps = {
        "sql": bool(engine_code and engine_code in sql_engines),
        "di_src": ds.get("in_di") or t in DI_SOURCE_ONLY_TYPES,
        "di_dst": ds.get("in_di") and t not in DI_SOURCE_ONLY_TYPES,
        "dqc": t in dqc_types,
        "probe": ds.get("in_di") or t in DI_SOURCE_ONLY_TYPES,
    }
    return caps


def format_reason(cap_key, ds, sql_engines, dqc_types):
    """能力为假时给出原因（help agent 不乱猜）"""
    t = (ds.get("type") or "").lower()
    if cap_key == "sql":
        engine_code = _sql_engine_code(t)
        if not engine_code:
            return f"{t} 无 SQL 引擎映射"
        if engine_code not in sql_engines:
            return f"{engine_code} 引擎未在当前工作空间启用"
    if cap_key == "di_dst" and t in DI_SOURCE_ONLY_TYPES:
        return f"{t} 是流式类型，只能做同步源端"
    if cap_key == "di_dst" and not ds.get("in_di"):
        return "该数据源未在 DI 注册（V2 独有）"
    if cap_key == "dqc" and t not in dqc_types:
        return f"{t} 不在 DQC 支持类型"
    return ""


def render_line(ds, caps, pid):
    """单条数据源的多行档案输出"""
    name = ds["name"]
    t = ds.get("type") or "-"
    sub = ds.get("subType") or "-"
    dsid = ds.get("id") or "-"
    op = ds.get("operator") or "-"
    status = ds.get("status")
    status_s = "-" if status is None else str(status)
    env = ds.get("envType")
    env_s = ENV_TYPE_LABEL.get(env, "-" if env is None else str(env))
    display = ds.get("displayName")
    desc = ds.get("description")

    flag_v2 = "V2" if ds.get("in_v2") else "--"
    flag_di = "DI" if ds.get("in_di") else "--"
    flag_comp = "CR" if ds.get("in_compute") else "--"  # CR=ComputeResource

    lines = []
    lines.append(f"── {name}  [type={t} subType={sub}]  [{flag_v2}/{flag_di}/{flag_comp}]")
    if ds.get("in_compute") and ds.get("computeResourceId"):
        lines.append(f"   计算资源 ID: {ds['computeResourceId']}（可同时作为扫描主体/引擎实例）")
    if display and display != name:
        lines.append(f"   displayName={display}")
    if desc:
        lines.append(f"   描述: {desc}")
    lines.append(f"   id={dsid}  operator={op}  status={status_s}  env={env_s}")
    conn = ds.get("connection") or {}
    if conn:
        parts = [f"{k}={v}" for k, v in conn.items()]
        lines.append("   连接: " + "  ".join(parts))
    return lines


def render_commands(ds, caps, pid, reasons):
    """即拷命令块"""
    name = ds["name"]
    t = ds.get("type") or ""
    out = []

    def mark(cap):
        return "✓" if caps.get(cap) else "✗"

    def reason(cap):
        return f"  -- {reasons.get(cap)}" if not caps.get(cap) and reasons.get(cap) else ""

    if caps["sql"]:
        out.append(f"   [SQL]      ✓  execute_sql.py \"<SQL>\" --datasource-code {name}")
    else:
        out.append(f"   [SQL]      ✗{reason('sql')}")

    if caps["di_src"]:
        out.append(f"   [DI 源]    ✓  resolve_sync_datasource.py --project-id {pid} --src-datasource {name} --src-type {t}")
    else:
        out.append(f"   [DI 源]    ✗")

    if caps["di_dst"]:
        out.append(f"   [DI 目标]  ✓  resolve_sync_datasource.py --project-id {pid} --dst-datasource {name} --dst-type {t}")
    else:
        out.append(f"   [DI 目标]  ✗{reason('di_dst')}")

    if caps["probe"]:
        out.append(f"   [探测表]   ✓  probe_table.py --project-id {pid} --src-datasource {name} --src-type {t} --src-table <表名>")

    out.append(f"   [查表列表] client.load(\"getTableListPost\", projectId={pid}, name=\"{name}\")")

    if caps["dqc"]:
        out.append(f"   [DQC]      ✓")
    else:
        out.append(f"   [DQC]      ✗{reason('dqc')}")

    return out


def main():
    parser = argparse.ArgumentParser(
        description="工作空间数据源档案（唯一入口）")
    parser.add_argument("keyword", nargs="?",
                        help="按 name 模糊过滤（可选）")
    parser.add_argument("--project-id", type=int)
    parser.add_argument("--project-name")
    parser.add_argument("--type", help="按数据源类型过滤，如 odps/mysql")
    parser.add_argument("--for", dest="use_for",
                        choices=["sql", "di_src", "di_dst", "dqc"],
                        help="按场景过滤：只列具备该能力的数据源")
    parser.add_argument("--detail",
                        help="指定 name，输出单条完整档案（含命令块）")
    parser.add_argument("--limit", type=int, default=50,
                        help="列表模式最多输出多少条（默认 50）")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 结构（给脚本消费）")
    args = parser.parse_args()

    client = BFFClient()
    pid = resolve_project_id(client, args.project_id, args.project_name,
                             tag="[browse_datasource]")

    # 并行拉五个源
    with ThreadPoolExecutor(max_workers=5) as ex:
        f_v2 = ex.submit(fetch_v2, client, pid)
        f_di = ex.submit(fetch_di, client, pid)
        f_dqc = ex.submit(fetch_dqc_types, client, pid)
        f_eng = ex.submit(fetch_sql_engines, client, pid)
        f_compute = ex.submit(fetch_compute, client, pid)
        v2_rows, v2_total = f_v2.result()
        di_rows = f_di.result()
        dqc_types = f_dqc.result()
        sql_engines = f_eng.result()
        compute_map = f_compute.result()

    v2_truncated = v2_total > len(v2_rows)
    di_truncated = len(di_rows) >= 500

    merged = merge(v2_rows, di_rows)

    # 把 listComputeResources 标记进已合并条目（按 name 对齐），
    # 对只在 compute 中出现（MC/StarRocks 未登记为数据源）的额外追加
    merged_by_name = {d["name"]: d for d in merged}
    for name, cr in compute_map.items():
        if name in merged_by_name:
            d = merged_by_name[name]
            d["in_compute"] = True
            d["computeResourceId"] = cr.get("crId")
            # 补引擎实例信息
            if cr.get("instanceId") and not d.get("connection", {}).get("instanceId"):
                d.setdefault("connection", {})["instanceId"] = cr["instanceId"]
        else:
            merged.append({
                "name": name,
                "type": cr.get("type") or "",
                "subType": None,
                "displayName": name,
                "description": f"（仅在 listComputeResources，未登记为数据源）",
                "projectId": pid,
                "id": None,
                "operator": None,
                "status": None,
                "envType": cr.get("envType"),
                "bindingCalcEngineId": None,
                "connection": {k: v for k, v in cr.items()
                               if k in ("instanceId", "regionId", "envType") and v},
                "in_v2": False, "in_di": False,
                "in_compute": True,
                "computeResourceId": cr.get("crId"),
            })

    # 过滤
    if args.keyword:
        kw = args.keyword.lower()
        merged = [d for d in merged if kw in d["name"].lower()]
    if args.type:
        merged = [d for d in merged if d.get("type") == args.type.lower()]

    # 分类并附上原因
    for ds in merged:
        ds["_caps"] = classify(ds, sql_engines, dqc_types)
        ds["_reasons"] = {
            k: format_reason(k, ds, sql_engines, dqc_types)
            for k in ds["_caps"]
        }

    if args.use_for:
        merged = [d for d in merged if d["_caps"].get(args.use_for)]

    # 详情模式
    if args.detail:
        target = next((d for d in merged if d["name"] == args.detail), None)
        if not target:
            print(f"[browse_datasource] 未找到: {args.detail}")
            telemetry_fail(f"not_found: {args.detail}")
            sys.exit(1)
        for line in render_line(target, target["_caps"], pid):
            print(line)
        for line in render_commands(target, target["_caps"], pid,
                                    target["_reasons"]):
            print(line)
        save_tool_result("browse_datasource",
                         {"mode": "detail", "datasource": target})
        telemetry_end(result={"mode": "detail", "name": args.detail})
        return

    # JSON 模式
    if args.json:
        import json as _json
        for ds in merged:
            ds["caps"] = ds.pop("_caps")
            ds["reasons"] = {k: v for k, v in ds.pop("_reasons").items() if v}
        print(_json.dumps({"projectId": pid, "count": len(merged),
                           "datasources": merged},
                          ensure_ascii=False, indent=2))
        telemetry_end(result={"mode": "json", "count": len(merged)})
        return

    # 列表模式
    total = len(merged)
    shown = merged[: args.limit]

    trunc_hint = ""
    if v2_truncated:
        trunc_hint = f"（V2 有 {v2_total} 条，只取前 500；用关键字或 --type 过滤缩小）"
    print(f"[browse_datasource] 工作空间 {pid} 数据源: 共 {total} 条"
          + (f"，按 --limit 截取 {len(shown)}" if total > args.limit else "")
          + trunc_hint)
    print(f"[白名单] SQL 引擎={sorted(sql_engines) or '-'}")
    print(f"[白名单] DQC 类型={sorted(dqc_types) or '-'}")
    print(f"[标记] V2=listDataSourceV2 有 | DI=getDataSourceList 有 | CR=listComputeResources 有（该类型既是数据源又是计算资源，可作扫描主体/执行引擎）")
    print()

    # 紧凑表格：一行一条，能力白名单做 5 列标记；来源列 V2/DI/CR (CR=ComputeResource)
    header = f"{'name':<40} {'type':<14} {'sub':<14} {'V2/DI/CR':<10} {'env':<4} {'sql':<4} {'di_src':<7} {'di_dst':<7} {'dqc':<4} description"
    print(header)
    print("-" * len(header))
    for ds in shown:
        caps = ds["_caps"]
        mark = lambda k: "✓" if caps[k] else "✗"
        env = ds.get("envType")
        env_s = ENV_TYPE_LABEL.get(env, "-" if env is None else str(env))
        desc = (ds.get("description") or "").replace("\n", " ")
        src_flag = ('V2' if ds.get('in_v2') else '--') + '/' + \
                   ('DI' if ds.get('in_di') else '--') + '/' + \
                   ('CR' if ds.get('in_compute') else '--')
        print(
            f"{ds['name'][:40]:<40} "
            f"{(ds.get('type') or '-')[:14]:<14} "
            f"{(ds.get('subType') or '-')[:14]:<14} "
            f"{src_flag:<10} "
            f"{env_s:<4} "
            f"{mark('sql'):<4} "
            f"{mark('di_src'):<7} "
            f"{mark('di_dst'):<7} "
            f"{mark('dqc'):<4} "
            f"{desc[:50]}"
        )

    print()
    print("→ 看单条详情（含即拷命令）: browse_datasource.py --project-id "
          f"{pid} --detail <name>")
    if not args.use_for:
        print(f"→ 只看某场景可用: browse_datasource.py --project-id {pid} "
              "--for sql|di_src|di_dst|dqc")

    save_tool_result("browse_datasource", {
        "mode": "list", "projectId": pid, "total": total,
        "sql_engines": sorted(sql_engines),
        "dqc_types": sorted(dqc_types),
        "datasources": [{k: v for k, v in ds.items()
                         if not k.startswith("_")} for ds in shown],
    })
    telemetry_end(result={"mode": "list", "count": total})


if __name__ == "__main__":
    main()
