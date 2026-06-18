#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据集成数据源解析工具

根据数据源类型，查找工作空间中可用的数据源。
  · 唯一候选 → 自动选择
  · 多候选 → 列出所有，环境推荐标 ★
  · 输出下一步 probe_table / build_di_spec 命令

用法：
    # 按类型解析（最常用）
    python resolve_sync_datasource.py --project-name cdo_datax --src-type mysql --dst-type odps

    # 已知数据源名称，只查类型
    python resolve_sync_datasource.py --project-id 22153 --src-datasource my_mysql --dst-datasource odps_first
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

from spec_builder.common.datasource_registry import DatasourceRegistry
from telemetry import telemetry_start, telemetry_end, telemetry_fail

_TAG = "[resolve]"

_DI_DATASOURCE_PAGE_SIZE = 10000
_DI_DATASOURCE_DISPLAY_LIMIT = 30
_DI_RESOURCE_GROUP_TYPES = ["PUBLIC_DATA_INTEGRATION", "COMMON_V2", "EXCLUSIVE_DATA_INTEGRATION"]
_DI_MODULES = ["DATA_INTEGRATION"]

_TYPE_EQUIV = {
    "odps": {"odps", "maxcompute"}, "maxcompute": {"odps", "maxcompute"},
    "holo": {"holo", "hologres"}, "hologres": {"holo", "hologres"},
    "sqlserver": {"sqlserver", "sql server"}, "sql server": {"sqlserver", "sql server"},
}

_TYPE_QUERY_NAME = {
    "maxcompute": "odps",
    "holo": "hologres",
    "sql server": "sqlserver",
}

_TYPE_DISPLAY_NAME = {
    "mysql": "MySQL",
    "odps": "MaxCompute(ODPS)",
    "maxcompute": "MaxCompute(ODPS)",
    "hologres": "Hologres",
    "holo": "Hologres",
    "postgresql": "PostgreSQL",
    "oracle": "Oracle",
    "sqlserver": "SQL Server",
    "sql server": "SQL Server",
    "clickhouse": "ClickHouse",
    "tddl": "TDDL",
}


# ─── 工具函数 ─────────────────────────────────────────────────


def _normalize_type(ds_type: str) -> str:
    raw = (ds_type or "").strip().lower()
    return _TYPE_QUERY_NAME.get(raw, raw)


def _display_type(ds_type: str) -> str:
    raw = (ds_type or "").strip().lower()
    return _TYPE_DISPLAY_NAME.get(raw, ds_type)




# ─── 资源组 ───────────────────────────────────────────────────


def _pick_resource_group(client: BFFClient, project_id: int) -> Optional[str]:
    groups = client.load(
        "listDataIntegrationResourceGroups", projectId=project_id,
        resourceGroupTypes=_DI_RESOURCE_GROUP_TYPES, modules=_DI_MODULES,
    )
    if not groups:
        return None
    default = next((g for g in groups if g.get("isDefault")), None)
    chosen = default or next((g for g in groups if g.get("available")), groups[0])
    return chosen.get("resourceGroupIdentifier")


# ─── 数据源查询 ───────────────────────────────────────────────


_ds_cache: Dict = {}


def _load_datasources(client: BFFClient, project_id: int,
                      ds_type: str, keyword: str = "") -> List[Dict[str, Any]]:
    cache_key = (project_id, _normalize_type(ds_type), keyword)
    if cache_key not in _ds_cache:
        _ds_cache[cache_key] = client.load(
            "getDataSourceList",
            projectId=project_id,
            searchType=_normalize_type(ds_type),
            keyword=keyword,
            pageNum=1,
            pageSize=_DI_DATASOURCE_PAGE_SIZE,
            envType="0,1",
            searchResultView="group",
        ) or []
    return _ds_cache[cache_key]


def _lookup_type(client: BFFClient, project_id: int, name: str) -> str:
    """根据数据源名称查找其类型（单次 keyword 搜索）"""
    rows = client.load(
        "getDataSourceList", projectId=project_id,
        keyword=name, searchType="", pageNum=1, pageSize=100,
        envType="0,1", searchResultView="group",
    ) or []
    for ds in rows:
        if ds.get("name") == name:
            return (ds.get("type") or "").lower()
    print(f"{_TAG} 未找到数据源: {name}")
    sys.exit(1)


def _get_global_project_id(client: BFFClient) -> Optional[int]:
    """从 profile 读取全局数据源所在的 projectId（如 alibaba 环境的 _TDDL/_ODPS）"""
    defaults = getattr(client, "_profile", {}).get("defaults", {})
    pid = defaults.get("global_datasource_project_id")
    return int(pid) if pid else None


def _collect_candidates(client: BFFClient, project_id: int, ds_type: str,
                        registry: DatasourceRegistry) -> List[Dict[str, Any]]:
    """收集该类型 + 关联类型的所有候选数据源"""
    match_set = _TYPE_EQUIV.get(ds_type.lower(), {ds_type.lower()})
    candidates = []
    seen_names = set()
    global_pid = _get_global_project_id(client)

    # 查询的 projectId 列表：当前工作空间 + 全局工作空间
    query_pids = [project_id]
    if global_pid and global_pid != project_id:
        query_pids.append(global_pid)

    # 主类型
    for t in match_set:
        for qpid in query_pids:
            for ds in _load_datasources(client, qpid, t):
                name = ds.get("name")
                if name and name not in seen_names:
                    seen_names.add(name)
                    candidates.append(ds)

    # 关联类型（从 profile 读取，如 mysql → [tddl]）
    defaults = getattr(client, "_profile", {}).get("defaults", {})
    assoc_types = defaults.get("associated_source_types", {})
    for assoc_type in assoc_types.get(ds_type.lower(), []):
        for qpid in query_pids:
            for ds in _load_datasources(client, qpid, assoc_type):
                name = ds.get("name")
                if name and name not in seen_names:
                    seen_names.add(name)
                    ds = dict(ds)  # copy，加标记
                    ds["_assoc_type"] = assoc_type
                    candidates.append(ds)

    return candidates


def _get_preferred_name(client: BFFClient, role_key: str, ds_type: str) -> Optional[str]:
    """从 profile 读取推荐数据源名（仅做展示标记用）"""
    defaults = getattr(client, "_profile", {}).get("defaults", {})
    return defaults.get("preferred_datasources", {}).get(role_key, {}).get(ds_type.lower())


# ─── 候选列表展示 ─────────────────────────────────────────────


def _get_extra_probe_params(ds: Dict[str, Any], registry: DatasourceRegistry) -> List[str]:
    """返回关联类型数据源需要的额外 probe 参数名列表（如 TDDL 的 appName）"""
    assoc_type = ds.get("_assoc_type")
    if not assoc_type:
        return []
    info = registry.resolve(assoc_type)
    if info and info.reader_extra_probe_params:
        return list(info.reader_extra_probe_params)
    return []


def _actual_type(ds: Dict[str, Any]) -> str:
    """候选数据源的实际类型（关联类型优先）"""
    return (ds.get("_assoc_type") or ds.get("type") or "").lower()


def _format_option(index: int, ds: Dict[str, Any], registry: DatasourceRegistry,
                   preferred_name: Optional[str] = None) -> str:
    """格式化候选数据源行。

    name 必须放在首位且加引号，避免 agent 拿到 displayName 当 name 调用。
    格式: `  1. "_ODPS" (type=odps) ★推荐  -- ODPS元数据中心（默认数据源）`
    """
    name = ds.get("name") or ""
    display_name = ds.get("displayName") or ""
    ds_type = ds.get("type") or ds.get("_assoc_type") or ""
    extra_params = _get_extra_probe_params(ds, registry)
    extra_hint = f", 需传 {', '.join(f'--{p.lower()}' for p in extra_params)}" if extra_params else ""
    tag = " ★推荐" if name == preferred_name else ""
    suffix = f"  -- {display_name}" if display_name and display_name != name else ""
    return f'  {index}. "{name}" (type={ds_type}{extra_hint}){tag}{suffix}'


def _format_probe_cmd(ds: Dict[str, Any], project_id: int, table: str,
                      resource_group: str, registry: DatasourceRegistry,
                      fallback_type: str = "") -> str:
    """为单个候选数据源生成完整的 probe_table 命令

    table 为空时输出 --list-tables 模式（先列出可用表，避免占位符）
    table 非空时输出 --table 模式
    """
    name = ds.get("name") or ""
    ds_type = _actual_type(ds) or _normalize_type(fallback_type)
    extra_params = _get_extra_probe_params(ds, registry)
    extra_args = " ".join(f"--{p.lower()} <{p}>" for p in extra_params)
    base = f"probe_table.py --project-id {project_id} --datasource {name} --type {ds_type} --resource-group {resource_group}"
    if not table:
        cmd = f"{base} --list-tables"
    else:
        cmd = f"{base} --table {table}"
    if extra_args:
        cmd += f" {extra_args}"
    return cmd


def _print_candidate_list(candidates: List[Dict[str, Any]], ds_type: str,
                          registry: DatasourceRegistry,
                          preferred_name: Optional[str] = None,
                          project_id: int = 0, table: str = "",
                          resource_group: str = "") -> None:
    """按类型分组展示候选数据源，每个候选附带完整 probe 命令"""
    # 按实际类型分组：主类型 vs 关联类型
    main_type_candidates = [ds for ds in candidates if not ds.get("_assoc_type")]
    assoc_groups: Dict[str, List[Dict[str, Any]]] = {}
    for ds in candidates:
        assoc = ds.get("_assoc_type")
        if assoc:
            assoc_groups.setdefault(assoc, []).append(ds)

    show_cmd = bool(project_id and table and resource_group)
    idx = 1

    # 先展示关联类型（通常是推荐的，如 TDDL）
    for assoc_type, group in assoc_groups.items():
        preferred = [ds for ds in group if ds.get("name") == preferred_name]
        others = [ds for ds in group if ds.get("name") != preferred_name]
        sorted_group = preferred + others
        assoc_label = _display_type(assoc_type)
        main_label = _display_type(ds_type)
        print(f"{assoc_label} 数据源（可读写 {main_label} 表，共 {len(sorted_group)} 个）：")
        for cand in sorted_group[:_DI_DATASOURCE_DISPLAY_LIMIT]:
            print(_format_option(idx, cand, registry, preferred_name))
            if show_cmd:
                print(f"     → {_format_probe_cmd(cand, project_id, table, resource_group, registry, fallback_type=assoc_type)}")
            idx += 1
        if len(sorted_group) > _DI_DATASOURCE_DISPLAY_LIMIT:
            print(f"  ...（还有 {len(sorted_group) - _DI_DATASOURCE_DISPLAY_LIMIT} 个未展示）")

    # 再展示主类型
    if main_type_candidates:
        preferred = [ds for ds in main_type_candidates if ds.get("name") == preferred_name]
        others = [ds for ds in main_type_candidates if ds.get("name") != preferred_name]
        sorted_main = preferred + others
        label = _display_type(ds_type)
        print(f"{label} 数据源（共 {len(sorted_main)} 个）：")
        for cand in sorted_main[:_DI_DATASOURCE_DISPLAY_LIMIT]:
            print(_format_option(idx, cand, registry, preferred_name))
            if show_cmd:
                print(f"     → {_format_probe_cmd(cand, project_id, table, resource_group, registry, fallback_type=ds_type)}")
            idx += 1
        if len(sorted_main) > _DI_DATASOURCE_DISPLAY_LIMIT:
            print(f"  ...（还有 {len(sorted_main) - _DI_DATASOURCE_DISPLAY_LIMIT} 个未展示）")


# ─── 单侧解析 ────────────────────────────────────────────────


def _resolve_one(client: BFFClient, project_id: int, ds_type: Optional[str],
                 ds_name: Optional[str], role: str, role_key: str,
                 registry: DatasourceRegistry) -> tuple:
    """解析一侧（源端或目标端）的数据源。

    Returns:
        (result, candidates)
        result: {"datasource": name, "type": type} 或 None（需要选择）
        candidates: 候选列表（result 为 None 时供调用方展示）
    """
    # 已知名称 → 查类型
    if ds_name:
        # IDB 虚拟数据源（如 _IDB.TAOBAO）不在 getDataSourceList，直接映射为 mysql
        if ds_name.upper().startswith("_IDB."):
            print(f"{_TAG} {role}: {ds_name} (type=mysql, IDB内部数据源)")
            return {"datasource": ds_name, "type": "mysql"}, []
        actual_type = _lookup_type(client, project_id, ds_name)
        print(f"{_TAG} {role}: {ds_name} (type={actual_type})")
        return {"datasource": ds_name, "type": actual_type}, []

    if not ds_type:
        return None, []

    # 收集所有候选（主类型 + 关联类型）
    candidates = _collect_candidates(client, project_id, ds_type, registry)

    if not candidates:
        print(f"{_TAG} 未找到 {_display_type(ds_type)} 类型的数据源")
        return None, []

    # 唯一候选 → 自动选择
    if len(candidates) == 1:
        ds = candidates[0]
        name = ds.get("name")
        actual_type = (ds.get("type") or ds_type).lower()
        print(f"{_TAG} {role}: {name} (type={actual_type}, 该类型仅此一个)")
        return {"datasource": name, "type": actual_type}, candidates

    # 多个候选 → 需要用户选择
    return None, candidates


# ─── 主流程 ───────────────────────────────────────────────────


def resolve(args: argparse.Namespace) -> None:
    client = BFFClient(quiet=True)
    registry = DatasourceRegistry()

    project_id = resolve_project_id(client, args.project_id, args.project_name, tag=_TAG)
    if args.project_id:
        print(f"{_TAG} 工作空间: {project_id}")

    src, src_candidates = _resolve_one(client, project_id, args.src_type, args.src_datasource,
                                       "源端", "reader", registry)
    dst, dst_candidates = _resolve_one(client, project_id, args.dst_type, args.dst_datasource,
                                       "目标端", "writer", registry)

    # 资源组
    resource_group = _pick_resource_group(client, project_id)
    if resource_group:
        print(f"{_TAG} 资源组: {resource_group}")
    else:
        print(f"{_TAG} ⚠️ 未查询到可用的数据集成资源组")

    # 两侧都解析成功
    if src and dst:
        _print_next_steps(project_id, src, dst, resource_group, args)
        telemetry_end(result={"status": "resolved", "project_id": project_id})
        save_tool_result("resolve_sync_datasource", {
            "status": "resolved",
            "project_id": project_id,
            "src_datasource": src["datasource"], "src_type": src["type"],
            "dst_datasource": dst["datasource"], "dst_type": dst["type"],
            "resource_group": resource_group,
        })
        # 累积参数到 confirmed_params（agent 注意力辅助层）
        # 只 remember 非空值，避免脏数据（如 dst_type='' 的占位）
        remember_kwargs = {"project_id": project_id}
        for key, value in [
            ("src_datasource", src.get("datasource")),
            ("src_type", src.get("type")),
            ("dst_datasource", dst.get("datasource")),
            ("dst_type", dst.get("type")),
            ("resource_group", resource_group),
            ("src_table", args.src_table),
        ]:
            if value:  # 过滤 None / 空字符串
                remember_kwargs[key] = value
        remember(**remember_kwargs)
        return

    # 有一侧或两侧需要选择
    needs_src = src is None and args.src_type
    needs_dst = dst is None and args.dst_type

    if needs_src or needs_dst:
        # table 不传占位符，让 _format_probe_cmd 决定输出 --list-tables 还是 --table
        table = args.src_table or ""
        rg = resource_group or "<资源组>"
        print(f"\n{_TAG} 该工作空间中可用的数据源如下，请从以下所有分组中选择：")
        if needs_src:
            print()
            src_preferred = _get_preferred_name(client, "reader", args.src_type)
            _print_candidate_list(src_candidates, args.src_type, registry, src_preferred,
                                  project_id=project_id, table=table, resource_group=rg)
        if needs_dst:
            print()
            dst_preferred = _get_preferred_name(client, "writer", args.dst_type)
            _print_candidate_list(dst_candidates, args.dst_type, registry, dst_preferred)
        print()
        if not args.src_table:
            print(f"{_TAG} 用户没有指定源表名。先选定源数据源，然后执行对应的 → 命令（--list-tables 模式）列出该数据源下的表。")
        else:
            print(f"{_TAG} 请让用户从以上所有分组中选择数据源，选择后执行对应的 → 命令。")
        sys.exit(1)


def _print_next_steps(project_id: int, src: Dict, dst: Dict,
                      resource_group: Optional[str],
                      args: argparse.Namespace) -> None:
    rg = resource_group or "<资源组>"
    if not args.src_table:
        # 无源表名：先列出可用表，等用户/agent 选择后再继续
        print(f"\n下一步：用户没有指定源表名，先列出 {src['datasource']} 下所有表（由用户或 agent 选择后再继续）:")
        print(f"  probe_table.py --project-id {project_id} --datasource {src['datasource']} --type {src['type']} --resource-group {rg} --list-tables")
        print(f"\n  ↓ 选定表名后，依次执行:")
        print(f"  probe_table.py --project-id {project_id} --datasource {src['datasource']} --type {src['type']} --table <选定的表名> --resource-group {rg}")
        print(f"  build_di_spec.py --project-id {project_id} --src-datasource {src['datasource']} --src-type {src['type']} --src-table <选定的表名> --dst-datasource {dst['datasource']} --dst-type {dst['type']} --resource-group {rg} --columns <列名>")
        return
    print(f"\n下一步:")
    print(f"  ① 探测源端表:")
    print(f"    probe_table.py --project-id {project_id} --datasource {src['datasource']} --type {src['type']} --table {args.src_table} --resource-group {rg}")
    print(f"  ② 创建任务（将 probe 输出的 --columns/--split-pk 填入）:")
    print(f"    build_di_spec.py --project-id {project_id} --src-datasource {src['datasource']} --src-type {src['type']} --src-table {args.src_table} --dst-datasource {dst['datasource']} --dst-type {dst['type']} --resource-group {rg} --columns <列名>")


# ─── CLI ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="数据集成数据源解析")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--project-name", help="工作空间名称")
    parser.add_argument("--src-type", help="源端数据源类型如 mysql")
    parser.add_argument("--src-datasource", help="源端数据源名称（已知时直接查类型）")
    parser.add_argument("--dst-type", help="目标端数据源类型如 odps/holo")
    parser.add_argument("--dst-datasource", help="目标端数据源名称（已知时直接查类型）")
    parser.add_argument("--src-table", help="源表名（传入后会嵌入建议命令）")
    args = parser.parse_args()

    telemetry_start("resolve_sync_datasource.py", module="data-integration", project_id=args.project_id, project_name=args.project_name)
    print_confirmed_params()

    if not args.src_type and not args.src_datasource:
        parser.error("需要 --src-type 或 --src-datasource")
    if not args.dst_type and not args.dst_datasource:
        parser.error("需要 --dst-type 或 --dst-datasource")

    resolve(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("resolve_sync_datasource.py", "data-integration", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("resolve_sync_datasource.py", "data-integration", 1, error=str(e)[:100])
        print(f"\n[error] {e}")
        print(f"  如需上报此问题: report_bug.py \"{e}\" --script resolve_sync_datasource.py")
        import sys; sys.exit(1)
