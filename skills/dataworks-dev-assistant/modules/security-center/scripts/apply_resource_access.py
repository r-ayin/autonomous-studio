#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""申请资源访问权限（RAP 新版，两阶段写操作）

⚠️ 两阶段写操作：Phase 1 输出确认摘要，Phase 2（--confirm）才真正提交。
   不要自动调 confirm_write()，必须等用户明确确认后才执行 Phase 2。

Phase 1（preview）:
    apply_resource_access.py \\
        --resource-type MaxComputeTable \\
        --project cwy_test_bj_0422 \\
        --table sql_test_pt_01 \\
        --grantee-id 123456789 \\
        --reason "需要访问该表进行数据分析"

    # --workspace-id 可选，不传时脚本自动从 searchTables 反查
    # 列级权限（同时授表级 + 两个列的 Download）：
    apply_resource_access.py \\
        --resource-type MaxComputeTable \\
        --project cwy_test_bj_0422 \\
        --table sql_test_pt_01 \\
        --columns id,name \\
        --grantee-id 123456789 \\
        --reason "需要访问 id 和 name 列"

Phase 2（confirm）:
    apply_resource_access.py --confirm

分步探测模式（遇到歧义时分步 resolve）:
    apply_resource_access.py --probe target  --project X --table Y
    apply_resource_access.py --probe grantee --grantee-id Z
    apply_resource_access.py --probe columns --workspace-id W --dma-entity-id D --columns a,b
    apply_resource_access.py --probe all     --project X --table Y --grantee-id Z [--columns a,b]

applyContent 构造规则：
    - 表级权限一条（accessTypes=--access 指定，默认 Select,Describe）
    - 每一列额外加一条独立 entry（accessTypes=["Download"]）
    - 共 1 + len(columns) 条 applyContent
"""

import argparse
import os
import sys
import time

from bff_client import BFFClient


# --resource-type → defSchema（RAP domain schema 标识）
_RESOURCE_TYPE_TO_SCHEMA = {
    "MaxComputeTable": "MaxCompute",
    "HologresTable":   "Hologres",
    "DLFTable":        "DLF",
    "DLFNextTable":    "DLFNext",
    "StarRocksTable":  "StarRocks",
    "EmrTable":        "Emr",
    "LindormTable":    "Lindorm",
}

_DEF_VERSION = "v1.0.0"
_TABLE_ACCESSES = ["Select", "Update", "Describe", "Alter", "Drop"]

# skill 脚本目录路径（用于错误提示中的排查命令）
_SKILL_PATH = "src/core/bff_client.py"

# 动态计算脚本自身路径（用于"下一步"命令拼接）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_CORE_DIR = os.path.join(_PROJECT_ROOT, "core")
_SCRIPT_PATH = os.path.abspath(__file__)


def _build_expiration_ms(days: int) -> str:
    """将天数转为毫秒级 Unix 时间戳字符串"""
    return str(int((time.time() + days * 86400) * 1000))


# ── Resolve 探测层 ──────────────────────────────────────────────────────────


def _resource_type_to_entity_type(resource_type: str) -> str:
    """将 --resource-type 映射为 getDetail 所需的 entityType 参数。"""
    _MAP = {
        "MaxComputeTable": "odps-table",
        "HologresTable":   "holo-table",    # TODO(deferred): 未实测——对真实 Hologres 表调 client.getDetail(entityType="holo-table") 确认 200，否则按 searchTables 返回的 entityType 校正
        "DLFTable":        "dlf-table",
        "DLFNextTable":    "dlfnext-table",
        "StarRocksTable":  "starrocks-table",
        "EmrTable":        "emr-table",
        "LindormTable":    "lindorm-table",  # TODO(deferred): 未实测——同上，对真实 Lindorm 表调 getDetail(entityType="lindorm-table") 验证
    }
    return _MAP.get(resource_type, "odps-table")


def resolve_target_resource(client: BFFClient, project: str, table: str,
                            workspace_id_explicit, resource_type: str = "MaxComputeTable") -> dict:
    """searchTables → getDetail 两步反查 workspace_id，将 MC project + table 解析为权威规范值。

    输入：
        project: MaxCompute project 名（如 cwy_test_bj_0422）
        table: 表名（如 sql_test_pt_01）
        workspace_id_explicit: 用户显式传入的 --workspace-id（int or None）
        resource_type: --resource-type 参数值，用于推导 entityType

    返回：
        {
            "workspace_id": int,
            "mc_project": str,
            "table": str,
            "dma_entity_id": str,   # metaEntityId（冒号格式）或从 qualifiedName 构造
            "qualified_name": str,  # 点分隔限定名
            "source": "searchTables+getDetail" | "explicit_workspace_id",
        }

    失败时向 stderr 输出错误+排查命令，sys.exit(1)。
    """
    entity_type = _resource_type_to_entity_type(resource_type)

    if workspace_id_explicit is not None:
        print(f"  workspace_id 用户显式指定（{workspace_id_explicit}），跳过 resolve")
        # 无法得到 dma_entity_id，构造推断值（格式：type:::project::table）
        qualified_name = f"{entity_type}.{project}.{table}"
        dma_entity_id = f"{entity_type}:::{project}::{table}"
        return {
            "workspace_id": workspace_id_explicit,
            "mc_project": project,
            "table": table,
            "dma_entity_id": dma_entity_id,
            "qualified_name": qualified_name,
            "source": "explicit_workspace_id",
        }

    # ── Step 1: searchTables ────────────────────────────────────────────────
    # searchTables 不返回 projectId，只用于定位 entityGuid
    results = client.load(
        "searchTables",
        keyword=table,
        entityType=entity_type,
        pageSize=50,
        pageNum=1,
    )

    # results 是 list（bff_client.load 返回 data.data[] 展开后的列表）
    if not isinstance(results, list):
        results = []

    # 过滤：databaseName == project（MC project 名）且 name 精确匹配表名
    # searchTables keyword 是模糊匹配，必须精确过滤
    matched = [
        r for r in results
        if r.get("databaseName") == project and r.get("name") == table
    ]

    if len(matched) == 0:
        # 诊断：同名表存在但 project 不对？
        same_name = [r for r in results if r.get("name") == table]
        hint = ""
        if same_name:
            projects = [r.get("databaseName", "?") for r in same_name]
            hint = f"\n  同名表存在于其他 project：{projects}"
        print(
            f"❌ 未找到表：{project}.{table}（entityType={entity_type}）{hint}\n"
            f"排查：\n"
            f"  搜所有同名表：\n"
            f"    python src/modules/discovery/scripts/search_table.py {table}",
            file=sys.stderr,
        )
        sys.exit(1)

    if len(matched) > 1:
        lines = []
        for r in matched:
            guid = r.get("entityGuid", "?")
            qn = r.get("qualifiedName", "?")
            lines.append(f"  entityGuid={guid}  qualifiedName={qn}")
        candidates = "\n".join(lines)
        print(
            f"❌ 匹配到多张表（{len(matched)} 条），请加 --workspace-id 明确：\n{candidates}\n"
            f"排查：\n"
            f"  python src/modules/discovery/scripts/search_table.py {table} --project {project}",
            file=sys.stderr,
        )
        sys.exit(1)

    row = matched[0]
    entity_guid = row.get("entityGuid")
    qualified_name = row.get("qualifiedName", f"{entity_type}.{project}.{table}")

    if not entity_guid:
        print(
            f"❌ searchTables 返回结果中缺少 entityGuid，无法继续查 getDetail。\n"
            f"排查：\n"
            f"  python src/modules/discovery/scripts/search_table.py {table} --project {project}",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Step 2: getDetail ───────────────────────────────────────────────────
    # getDetail 返回 dict（return_structure=data{}），包含 projectId 和 metaEntityId
    try:
        detail = client.load("getDetail", entityType=entity_type, entityGuid=entity_guid)
    except Exception as e:
        print(
            f"❌ getDetail 调用失败（{e}）\n"
            f"排查：\n"
            f"  python -c \"from bff_client import BFFClient; c=BFFClient(); "
            f"print(c.load('getDetail', entityType='{entity_type}', entityGuid='{entity_guid}'))\"",
            file=sys.stderr,
        )
        sys.exit(1)

    if not isinstance(detail, dict):
        print(
            f"❌ getDetail 返回格式异常（期望 dict，实际 {type(detail).__name__}）\n"
            f"排查：\n"
            f"  python -c \"from bff_client import BFFClient; c=BFFClient(); "
            f"print(c.load('getDetail', entityType='{entity_type}', entityGuid='{entity_guid}'))\"",
            file=sys.stderr,
        )
        sys.exit(1)

    raw_pid = detail.get("projectId")
    if raw_pid is None:
        print(
            f"❌ getDetail 返回结果中缺少 projectId 字段，无法确定 workspace_id。\n"
            f"返回字段：{list(detail.keys())}\n"
            f"排查：\n"
            f"  python -c \"from bff_client import BFFClient; c=BFFClient(); "
            f"print(c.load('getDetail', entityType='{entity_type}', entityGuid='{entity_guid}'))\"",
            file=sys.stderr,
        )
        sys.exit(1)

    # 优先使用 metaEntityId（冒号格式，可直接用于 listColumns）
    # 降级：从 qualifiedName 构造（点→冒号）
    meta_entity_id = detail.get("metaEntityId")
    if meta_entity_id:
        dma_entity_id = meta_entity_id
    else:
        parts = qualified_name.split(".")
        if len(parts) == 3:
            dma_entity_id = f"{parts[0]}:::{parts[1]}::{parts[2]}"
        else:
            dma_entity_id = f"{entity_type}:::{project}::{table}"

    # 用 getDetail 返回的 qualifiedName 更新（更权威）
    qualified_name = detail.get("qualifiedName") or qualified_name

    return {
        "workspace_id": int(raw_pid),
        "mc_project": project,
        "table": table,
        "dma_entity_id": dma_entity_id,
        "qualified_name": qualified_name,
        "source": "searchTables+getDetail",
    }


def resolve_grantee(client: BFFClient, grantee_id: str, grantee_type: str) -> dict:
    """验证被授权人 baseId 的真实存在性。

    输入：
        grantee_id: 纯数字 baseId 字符串
        grantee_type: "RAM_USER" | "RAM_ROLE"

    返回：
        {
            "base_id": str,
            "principal_type": str,
            "display_name": str or None,
            "verified": bool,
        }

    验证失败不 exit，仅打印警告，继续执行。
    RAM_ROLE 类型跳过用户检索。
    """
    if grantee_type == "RAM_ROLE":
        print("  grantee-type=RAM_ROLE，跳过用户检索")
        return {
            "base_id": grantee_id,
            "principal_type": grantee_type,
            "display_name": None,
            "verified": False,
        }

    try:
        result = client.load("GetUsersByIdsOrKeyword", userIds=grantee_id)
        # result 可能是 dict 或 list
        users = result if isinstance(result, list) else ([result] if isinstance(result, dict) else [])
        matched = None
        for u in users:
            if str(u.get("baseId", "")) == str(grantee_id) or str(u.get("id", "")) == str(grantee_id):
                matched = u
                break
        if matched:
            display_name = matched.get("displayName") or matched.get("loginName") or matched.get("name")
            return {
                "base_id": grantee_id,
                "principal_type": grantee_type,
                "display_name": display_name,
                "verified": True,
            }
        else:
            print(
                f"  ⚠️ grantee-id {grantee_id} 未在 GetUsersByIdsOrKeyword 中匹配到。"
                f"可能是 RAM_ROLE / 新用户 / 或跨租户。\n"
                f"  继续，但请自行确认 ID 正确。"
            )
    except Exception as e:
        print(f"  ⚠️ GetUsersByIdsOrKeyword 调用失败（{e}），跳过用户验证。")

    return {
        "base_id": grantee_id,
        "principal_type": grantee_type,
        "display_name": None,
        "verified": False,
    }


def resolve_columns(client: BFFClient, resolved_target: dict, requested_columns: list) -> list:
    """验证列名在目标表中存在。

    输入：
        resolved_target: resolve_target_resource 的返回值
        requested_columns: 用户请求的列名列表（空列表时直接返回 []）

    返回：
        [{"name": str, "exists": bool}, ...]

    若有列不存在，向 stderr 输出错误+排查命令，sys.exit(1)。
    """
    if not requested_columns:
        return []

    dma_entity_id = resolved_target["dma_entity_id"]
    mc_project = resolved_target["mc_project"]
    table = resolved_target["table"]

    try:
        result = client.load("listColumns", tableId=dma_entity_id)
        actual_cols = result if isinstance(result, list) else []
    except Exception as e:
        print(
            f"❌ listColumns 调用失败（{e}），无法验证列。\n"
            f"排查：\n"
            f"  python {_SKILL_PATH} listColumns --tableId {dma_entity_id}",
            file=sys.stderr,
        )
        sys.exit(1)

    actual_names = {c.get("name", "") for c in actual_cols if c.get("name")}
    missing = [col for col in requested_columns if col not in actual_names]

    if missing:
        sample = sorted(actual_names)[:20]
        print(
            f"❌ 以下列在 {mc_project}.{table} 中不存在：{missing}\n"
            f"实际存在的列（前 20）：{', '.join(sample)}\n"
            f"排查：\n"
            f"  python {_SKILL_PATH} listColumns --tableId {dma_entity_id}",
            file=sys.stderr,
        )
        sys.exit(1)

    return [{"name": col, "exists": True} for col in requested_columns]


# ── Probe 模式 ──────────────────────────────────────────────────────────────


def _check_probe_args(args, required: list):
    """检查 probe 模式下必需参数是否齐全，缺失时 stderr + exit(2)。
    required 列表中的字段名可用下划线或连字符，统一转换后检查和展示。
    """
    missing = []
    for field in required:
        attr = field.replace("-", "_")
        flag = f"--{field.replace('_', '-')}"
        val = getattr(args, attr, None)
        if val is None or val == "":
            missing.append(flag)
    if missing:
        print(
            f"❌ --probe {args.probe} 缺少必填参数：{', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(2)


def _print_target_probe_result(resolved: dict, args):
    """打印 --probe target 的结构化输出 + 下一步命令。"""
    workspace_id = resolved["workspace_id"]
    dma_entity_id = resolved["dma_entity_id"]
    mc_project = resolved["mc_project"]
    table = resolved["table"]
    qualified_name = resolved["qualified_name"]
    source_note = (
        "← 从 searchTables+getDetail 反查"
        if resolved["source"] == "searchTables+getDetail"
        else "← 用户显式指定"
    )

    print()
    print("═══════════════════════════════════════════════════")
    print("  Probe: target    ✓ 成功")
    print("═══════════════════════════════════════════════════")
    print(f"  MC project       : {mc_project}")
    print(f"  Table            : {table}")
    print(f"  Workspace ID     : {workspace_id}  {source_note}")
    print(f"  DMA entity ID    : {dma_entity_id}")
    print(f"  qualified_name   : {qualified_name}")
    print()
    print("下一步（按场景挑一条执行）:")
    print()
    print("  ▸ 验证被授权人:")
    print(f"    PYTHONPATH={_CORE_DIR} python {_SCRIPT_PATH} \\")
    print(f"      --probe grantee --grantee-id <填入被授权人 baseId>")
    print()
    print("  ▸ 验证列权限（如需）:")
    print(f"    PYTHONPATH={_CORE_DIR} python {_SCRIPT_PATH} \\")
    print(f"      --probe columns \\")
    print(f"      --workspace-id {workspace_id} \\")
    print(f"      --dma-entity-id {dma_entity_id} \\")
    print(f"      --columns <列1,列2>")
    print()
    print("  ▸ 一键提交申请（Phase 1 preview + 等确认）:")
    print(f"    PYTHONPATH={_CORE_DIR} python {_SCRIPT_PATH} \\")
    print(f"      --resource-type MaxComputeTable \\")
    print(f"      --project {mc_project} \\")
    print(f"      --table {table} \\")
    print(f"      --workspace-id {workspace_id} \\")
    print(f"      --grantee-id <baseId> \\")
    print(f"      --grantee-type RAM_USER \\")
    print(f"      [--columns <列>] \\")
    print(f"      --reason \"<申请理由>\"")
    print()


def _print_grantee_probe_result(resolved: dict, args):
    """打印 --probe grantee 的结构化输出 + 下一步命令。"""
    base_id = resolved["base_id"]
    principal_type = resolved["principal_type"]
    display_name = resolved["display_name"]
    verified = resolved["verified"]

    if display_name and verified:
        name_str = f"{display_name}  (GetUsersByIdsOrKeyword 验证通过)"
    elif principal_type == "RAM_ROLE":
        name_str = "（RAM_ROLE，跳过用户检索）"
    else:
        name_str = "（未在 GetUsersByIdsOrKeyword 中匹配，可能是新用户/RAM 角色/跨租户）"

    print()
    print("═══════════════════════════════════════════════════")
    print(f"  Probe: grantee   {'✓ 成功' if verified else '⚠ 未验证（流程不阻塞）'}")
    print("═══════════════════════════════════════════════════")
    print(f"  BaseId           : {base_id}")
    print(f"  Type             : {principal_type}")
    print(f"  Display Name     : {name_str}")
    print()
    print("下一步（按场景挑一条执行）:")
    print()
    print("  ▸ 解析资源（如未完成）:")
    print(f"    PYTHONPATH={_CORE_DIR} python {_SCRIPT_PATH} \\")
    print(f"      --probe target --project <project名> --table <表名>")
    print()
    print("  ▸ 一键提交申请（Phase 1 preview + 等确认）:")
    print(f"    PYTHONPATH={_CORE_DIR} python {_SCRIPT_PATH} \\")
    print(f"      --resource-type MaxComputeTable \\")
    print(f"      --project <project名> \\")
    print(f"      --table <表名> \\")
    print(f"      --grantee-id {base_id} \\")
    print(f"      --grantee-type {principal_type} \\")
    print(f"      [--columns <列>] \\")
    print(f"      --reason \"<申请理由>\"")
    print()


def _print_columns_probe_result(resolved_cols: list, args, requested_columns: list):
    """打印 --probe columns 的结构化输出 + 下一步命令。"""
    col_display = ", ".join(f"{c['name']} ✓" for c in resolved_cols)
    print()
    print("═══════════════════════════════════════════════════")
    print("  Probe: columns   ✓ 成功")
    print("═══════════════════════════════════════════════════")
    print(f"  workspace_id     : {args.workspace_id}")
    print(f"  dma_entity_id    : {args.dma_entity_id}")
    print(f"  请求列 ({len(requested_columns)})       : {col_display}  (全部存在)")
    print()
    cols_str = ",".join(requested_columns)
    print("下一步:")
    print()
    print("  ▸ 一键提交（带列级权限）:")
    print(f"    PYTHONPATH={_CORE_DIR} python {_SCRIPT_PATH} \\")
    print(f"      --resource-type MaxComputeTable \\")
    print(f"      --project <project名> \\")
    print(f"      --table <表名> \\")
    print(f"      --workspace-id {args.workspace_id} \\")
    print(f"      --grantee-id <baseId> \\")
    print(f"      --grantee-type RAM_USER \\")
    print(f"      --columns {cols_str} \\")
    print(f"      --reason \"<申请理由>\"")
    print()


def _print_all_probe_result(target: dict, grantee: dict, cols_resolved: list, args):
    """打印 --probe all 的全部 resolve 结果 + 最终一键提交命令。"""
    workspace_id = target["workspace_id"]
    dma_entity_id = target["dma_entity_id"]
    mc_project = target["mc_project"]
    table = target["table"]
    qualified_name = target["qualified_name"]
    source_note = (
        "← 从 searchTables+getDetail 反查"
        if target["source"] == "searchTables+getDetail"
        else "← 用户显式指定"
    )

    base_id = grantee["base_id"]
    principal_type = grantee["principal_type"]
    display_name = grantee["display_name"]
    verified = grantee["verified"]

    if display_name and verified:
        name_str = f"{display_name}  (GetUsersByIdsOrKeyword 验证通过)"
    elif principal_type == "RAM_ROLE":
        name_str = "（RAM_ROLE，跳过用户检索）"
    else:
        name_str = "（未在 GetUsersByIdsOrKeyword 中匹配，可能是新用户/RAM 角色/跨租户）"

    print()
    print("═══════════════════════════════════════════════════")
    print("  Probe: all — target")
    print("═══════════════════════════════════════════════════")
    print(f"  MC project       : {mc_project}")
    print(f"  Table            : {table}")
    print(f"  Workspace ID     : {workspace_id}  {source_note}")
    print(f"  DMA entity ID    : {dma_entity_id}")
    print(f"  qualified_name   : {qualified_name}")

    print()
    print("═══════════════════════════════════════════════════")
    print(f"  Probe: all — grantee   {'✓ 成功' if verified else '⚠ 未验证（流程不阻塞）'}")
    print("═══════════════════════════════════════════════════")
    print(f"  BaseId           : {base_id}")
    print(f"  Type             : {principal_type}")
    print(f"  Display Name     : {name_str}")

    if cols_resolved:
        col_display = ", ".join(f"{c['name']} ✓" for c in cols_resolved)
        requested_columns = [c["name"] for c in cols_resolved]
        print()
        print("═══════════════════════════════════════════════════")
        print("  Probe: all — columns   ✓ 成功")
        print("═══════════════════════════════════════════════════")
        print(f"  请求列 ({len(requested_columns)})       : {col_display}  (全部存在)")

    # 构造最终一键提交命令（所有已知参数填齐）
    print()
    print("下一步（所有 resolve 完成，可直接提交）:")
    print()
    print("  ▸ Phase 1 preview:")
    cmd_lines = [
        f"    PYTHONPATH={_CORE_DIR} python {_SCRIPT_PATH} \\",
        f"      --resource-type MaxComputeTable \\",
        f"      --project {mc_project} \\",
        f"      --table {table} \\",
        f"      --workspace-id {workspace_id} \\",
        f"      --grantee-id {base_id} \\",
        f"      --grantee-type {principal_type} \\",
    ]
    if cols_resolved:
        cols_str = ",".join(c["name"] for c in cols_resolved)
        cmd_lines.append(f"      --columns {cols_str} \\")
    cmd_lines.append(f"      --reason \"<申请理由>\"")
    print("\n".join(cmd_lines))
    print()
    print("  ▸ Phase 2 confirm（用户确认后）:")
    print(f"    PYTHONPATH={_CORE_DIR} python {_SCRIPT_PATH} --confirm")
    print()


def run_probe(client: BFFClient, args):
    """--probe 模式分发入口。"""

    if args.probe == "target":
        _check_probe_args(args, required=["project", "table"])
        resource_type = args.resource_type or "MaxComputeTable"
        resolved = resolve_target_resource(
            client,
            project=args.project,
            table=args.table,
            workspace_id_explicit=args.workspace_id,
            resource_type=resource_type,
        )
        _print_target_probe_result(resolved, args)
        return

    if args.probe == "grantee":
        _check_probe_args(args, required=["grantee_id"])
        grantee_type = args.grantee_type or "RAM_USER"
        resolved = resolve_grantee(client, args.grantee_id, grantee_type)
        _print_grantee_probe_result(resolved, args)
        return

    if args.probe == "columns":
        _check_probe_args(args, required=["workspace_id", "dma_entity_id", "columns"])
        cols = [c.strip() for c in args.columns.split(",") if c.strip()]
        # 直接用 agent 给的 dma_entity_id，构造 fake_target 跳过 resolve_target
        fake_target = {
            "dma_entity_id": args.dma_entity_id,
            "mc_project": "?",
            "table": "?",
        }
        resolved_cols = resolve_columns(client, fake_target, cols)
        _print_columns_probe_result(resolved_cols, args, cols)
        return

    if args.probe == "all":
        _check_probe_args(args, required=["project", "table", "grantee_id"])
        resource_type = args.resource_type or "MaxComputeTable"
        target = resolve_target_resource(
            client,
            project=args.project,
            table=args.table,
            workspace_id_explicit=args.workspace_id,
            resource_type=resource_type,
        )
        grantee_type = args.grantee_type or "RAM_USER"
        grantee = resolve_grantee(client, args.grantee_id, grantee_type)

        cols_resolved = []
        if args.columns:
            cols = [c.strip() for c in args.columns.split(",") if c.strip()]
            cols_resolved = resolve_columns(client, target, cols)

        _print_all_probe_result(target, grantee, cols_resolved, args)
        return


# ── 主函数 ──────────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(description="申请资源访问权限（RAP 新版）")
    p.add_argument("--resource-type", required=False,
                   choices=list(_RESOURCE_TYPE_TO_SCHEMA.keys()),
                   help="资源类型（Phase 1 必填）：MaxComputeTable / HologresTable / DLFTable 等")
    p.add_argument("--project",
                   help="MaxCompute project（ODPS catalog），不是 DataWorks workspace 名。例：cwy_test_bj_0422")
    p.add_argument("--table", help="表名（Phase 1 必填）")
    p.add_argument("--columns", help="列名列表，逗号分隔（列级权限 Download），如 id,name")
    p.add_argument("--access", default="Select,Describe",
                   help="表级权限类型，逗号分隔（默认 Select,Describe）；支持 Select/Update/Describe/Alter/Drop")
    p.add_argument("--grantee-id",
                   help="被授权人 baseId（纯数字）。脚本会用 GetUsersByIdsOrKeyword 验证存在性。")
    p.add_argument("--grantee-type", default="RAM_USER",
                   choices=["RAM_USER", "RAM_ROLE"],
                   help="被授权人类型（默认 RAM_USER）")
    p.add_argument("--workspace-id", type=int,
                   help="[可选] DataWorks workspace ID（int）。不传时脚本自动从 searchTables 反查。")
    p.add_argument("--expiration-days", type=int, default=30,
                   help="权限有效期天数（默认 30 天）")
    p.add_argument("--reason", help="申请理由（Phase 1 必填）")
    p.add_argument("--confirm", action="store_true", help="Phase 2: 执行提交")
    p.add_argument("--probe", choices=["target", "grantee", "columns", "all"], default=None,
                   help="分步探测模式：target=仅 resolve 目标资源；grantee=仅验证被授权人；"
                        "columns=仅验证列；all=跑全部 resolve 但不进入 Phase 1 write preview。"
                        "不传时默认走完整流程。")
    p.add_argument("--dma-entity-id",
                   help="[仅 --probe columns 模式] DMA 实体 ID（形如 maxcompute-table:::project::table）。"
                        "避免重复跑 resolve_target。")
    args = p.parse_args()

    client = BFFClient()

    # --confirm 优先（保持原有逻辑）
    if args.confirm:
        client.confirm_write()
        return

    # --probe 分支
    if args.probe:
        run_probe(client, args)
        return

    # ── 默认流程（完整 Phase 1 preview）──────────────────────────────────────

    # Phase 1 参数校验
    missing = []
    if not args.resource_type:
        missing.append("--resource-type")
    if not args.project:
        missing.append("--project")
    if not args.table:
        missing.append("--table")
    if not args.grantee_id:
        missing.append("--grantee-id")
    if not args.reason:
        missing.append("--reason")
    if missing:
        p.error(f"Phase 1 必填参数缺失: {', '.join(missing)}")

    # 主路径只支持 MaxComputeTable；其他 schema 有 entity 入口但 metaData 结构完全不同
    # （Hologres 要 instance+database+schema+table、DLF 要 catalog+database+table 等）
    # 需补充真实流量样例后再按 schema 独立实现
    if args.resource_type != "MaxComputeTable":
        print(
            f"❌ 暂不支持 --resource-type={args.resource_type}\n"
            f"   目前仅 MaxComputeTable 主路径已 E2E 验证。\n"
            f"   其他 schema（HOLOGRES / DLF_V1 / DLF_NEXT / STARROCKS / EMR / LINDORM）\n"
            f"   的 metaData 结构与 MaxCompute 不同，需补流量样本后独立实现。\n"
            f"   排查：\n"
            f"     1. 先录制该 schema 的申请页面流量（ingest_traffic）\n"
            f"     2. 对照服务端 ResourceSchemaInitializer 的字段定义构造 metaData",
            file=sys.stderr,
        )
        sys.exit(1)

    # 校验表级权限类型
    access_types = [a.strip() for a in args.access.split(",") if a.strip()]
    invalid = [a for a in access_types if a not in _TABLE_ACCESSES]
    if invalid:
        print(f"❌ --access 含无效值: {invalid}；支持: {_TABLE_ACCESSES}", file=sys.stderr)
        sys.exit(1)

    # ── Phase 0：Resolve 探测层 ──────────────────────────────────────────────
    print("正在解析输入参数…")

    resolved_target = resolve_target_resource(
        client,
        project=args.project,
        table=args.table,
        workspace_id_explicit=args.workspace_id,
        resource_type=args.resource_type,
    )

    resolved_grantee = resolve_grantee(client, args.grantee_id, args.grantee_type)

    columns = []
    resolved_cols = []
    if args.columns:
        columns = [c.strip() for c in args.columns.split(",") if c.strip()]
        resolved_cols = resolve_columns(client, resolved_target, columns)

    expiration_ms = _build_expiration_ms(args.expiration_days)

    # ── Resolve 结果展示 ─────────────────────────────────────────────────────
    workspace_source = (
        "← 从 searchTables+getDetail 反查"
        if resolved_target["source"] == "searchTables+getDetail"
        else "← 用户显式指定"
    )
    grantee_verified = " ✓" if resolved_grantee["verified"] else ""
    grantee_name_str = (
        f" ({resolved_grantee['display_name']}){grantee_verified}"
        if resolved_grantee["display_name"]
        else grantee_verified
    )

    print()
    print("═══════════════════════════════════════════════════")
    print("  Resolve 结果")
    print("═══════════════════════════════════════════════════")
    print(f"  目标资源:")
    print(f"    MC project      : {resolved_target['mc_project']} ✓")
    print(f"    Table           : {resolved_target['table']} ✓"
          f"（DMA id={resolved_target['dma_entity_id']}）")
    print(f"    Workspace ID    : {resolved_target['workspace_id']}  {workspace_source}")
    print(f"  授权对象:")
    print(f"    BaseId          : {resolved_grantee['base_id']}{grantee_name_str}")
    print(f"    Type            : {resolved_grantee['principal_type']}")
    if resolved_cols:
        col_str = ", ".join(f"{c['name']} (Download) ✓" for c in resolved_cols)
        print(f"  权限范围:")
        print(f"    表级            : {', '.join(access_types)}")
        print(f"    列级            : {col_str}")
    else:
        print(f"  权限范围:")
        print(f"    表级            : {', '.join(access_types)}")
    print(f"  有效期:")
    print(f"    {args.expiration_days} 天（过期时间戳 {expiration_ms}）")
    print()

    # ── Phase 1 Preview（构造请求体）────────────────────────────────────────
    workspace_id = resolved_target["workspace_id"]
    def_schema = _RESOURCE_TYPE_TO_SCHEMA[args.resource_type]
    grantee = {
        "principalId": resolved_grantee["base_id"],
        "principalType": resolved_grantee["principal_type"],
    }

    def _make_resource(column=None):
        meta = {
            "project": resolved_target["mc_project"],
            "table": resolved_target["table"],
            "workspace": str(workspace_id),
            "threeTierModel": False,
        }
        if column:
            meta["column"] = column
        return {
            "defSchema": def_schema,
            "defVersion": _DEF_VERSION,
            "metaData": meta,
        }

    apply_content = []

    # 表级权限 entry
    apply_content.append({
        "resource": _make_resource(),
        "grantee": grantee,
        "accessTypes": access_types,
        "expirationTime": expiration_ms,
    })

    # 列级权限 entry（每列独立一条）
    for col in columns:
        apply_content.append({
            "resource": _make_resource(column=col),
            "grantee": grantee,
            "accessTypes": ["Download"],
            "expirationTime": expiration_ms,
        })

    body = {
        "reason": args.reason,
        "applyContent": apply_content,
    }

    # 输出预览摘要
    print(f"权限申请预览")
    print(f"  资源类型  : {args.resource_type} ({def_schema})")
    print(f"  项目.表   : {resolved_target['mc_project']}.{resolved_target['table']}")
    if columns:
        print(f"  列        : {', '.join(columns)}（列级 Download）")
    print(f"  表级权限  : {', '.join(access_types)}")
    print(f"  被授权人  : {resolved_grantee['base_id']} ({resolved_grantee['principal_type']})")
    print(f"  有效期    : {args.expiration_days} 天（过期时间戳: {expiration_ms}）")
    print(f"  申请理由  : {args.reason}")
    print(f"  applyContent 条数: {len(apply_content)}（1 表 + {len(columns)} 列）")

    client.write("applyResourceAccessPermission", **body)
    print(f"\n→ 用户确认后执行: apply_resource_access.py --confirm")


if __name__ == "__main__":
    main()
