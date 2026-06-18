#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据集成目标表保障工具

场景：
1. 检测目标端表是否存在
2. 若不存在，自动调用 addTable 生成目标端建表 DDL
3. 展示表名和分区策略，等待用户确认
4. 用户确认后调用 createTableByDDL 一键建表
5. 自动回查目标表结构

用法：
    python ensure_target_table.py \
      --project-id 22153 \
      --src-datasource yunshi_mysql_pre_di_ide \
      --src-type MYSQL \
      --src-table t_parameter \
      --dst-datasource cx_old_inner_odps2 \
      --dst-type ODPS \
      --dst-table t_parameter_v03312010

    # IDB 数据源无法自动拉列信息时，用 --columns-file 绕过 accessId 限制：
    # columns.json 格式：[{"name":"id","type":"bigint(20) unsigned","comment":"...","nullable":"false","primaryKey":"true"}, ...]
    python ensure_target_table.py \
      --project-id 22153 \
      --columns-file columns.json \
      --src-type mysql \
      --src-table page_content_version \
      --dst-datasource _ODPS \
      --dst-type ODPS \
      --dst-table s_ms_aone_km_x_page_content_version_fd

    python ensure_target_table.py --confirm
"""

import argparse
import json
import os
import re
import shlex
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from bff_client import BFFClient, save_tool_result
from runtime import print_confirmed_params, remember
from table_metadata import build_table_column_params, is_idb_datasource, load_table_metadata, table_exists
from telemetry import telemetry_start, telemetry_end, telemetry_fail


_TAG = "[ensure_target_table]"
_PENDING_FILE = os.path.join(os.path.expanduser("~"), ".dataworks", "pending_di_create_table.json")

_DEFAULT_ENV_TYPE = 1
_DEFAULT_SUBTYPE = "public"
_CONFIRM_GUARD_SECONDS = 10
_SCRIPT_PATH = os.path.abspath(__file__)
_CORE_PATH = os.path.abspath(os.path.join(os.path.dirname(_SCRIPT_PATH), "..", "..", "..", "core"))
_DI_RESOURCE_GROUP_TYPES = [
    "PUBLIC_DATA_INTEGRATION",
    "COMMON_V2",
    "EXCLUSIVE_DATA_INTEGRATION",
]
_DI_MODULES = ["DATA_INTEGRATION"]
_TDDL_SUBTYPE = "inner"


def _normalize_type(value: str) -> str:
    return value.strip().lower()


def _reader_step_type(value: str) -> str:
    return value.strip().lower()


def _load_pending() -> Dict[str, Any]:
    path = _PENDING_FILE
    if not os.path.exists(path):
        print(f"{_TAG} 没有待确认的建表操作。请先运行 prepare。")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_pending(payload: Dict[str, Any]) -> None:
    path = _PENDING_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _remove_pending() -> None:
    path = _PENDING_FILE
    if os.path.exists(path):
        os.remove(path)


def _validate_confirm_window(created_at: Optional[str]) -> None:
    if not created_at:
        return
    elapsed = (datetime.now() - datetime.fromisoformat(created_at)).total_seconds()
    if elapsed < _CONFIRM_GUARD_SECONDS:
        print(
            f"{_TAG} ⚠️ 操作被拦截：必须先让用户确认。\n"
            f"{_TAG} 现在先把上一步生成的 DDL 和确认摘要展示给用户，等用户明确回复「确认」后，再执行 --confirm。"
        )
        sys.exit(1)


def _confirm_command() -> str:
    work_dir = shlex.quote(os.getcwd())
    core_path = shlex.quote(_CORE_PATH)
    script_path = shlex.quote(_SCRIPT_PATH)
    return f"cd {work_dir} && PYTHONPATH={core_path} python {script_path} --confirm"


def _pick_di_resource_group(client: BFFClient, project_id: int) -> str:
    groups = client.load(
        "listDataIntegrationResourceGroups",
        projectId=project_id,
        resourceGroupTypes=_DI_RESOURCE_GROUP_TYPES,
        modules=_DI_MODULES,
    )
    if not groups:
        raise RuntimeError("未查询到可用的数据集成资源组")
    default = next((g for g in groups if g.get("isDefault")), None)
    chosen = default or next((g for g in groups if g.get("available")), groups[0])
    identifier = chosen.get("resourceGroupIdentifier")
    if not identifier:
        raise RuntimeError(f"资源组缺少 identifier: {chosen}")
    return identifier


def _is_tddl_type(datasource_type: str) -> bool:
    return _reader_step_type(datasource_type) == "tddl"


def _resolve_tddl_table_info(
        client: BFFClient,
        project_id: int,
        tenant_id: int,
        datasource_name: str,
        resource_group: str,
        table_name: str,
        env_type: int,
) -> Optional[Dict[str, Any]]:
    metadata = load_table_metadata(
        client,
        project_id,
        tenant_id,
        datasource_name,
        "tddl",
        resource_group,
        table_name,
        env_type,
    )
    return metadata.get("table_info") if metadata else None


def _table_exists(
        client: BFFClient,
        project_id: int,
        tenant_id: int,
        datasource_name: str,
        resource_group: str,
        table_name: str,
        env_type: int,
        datasource_type: str = "",
) -> bool:
    return table_exists(
        client,
        project_id,
        tenant_id,
        datasource_name,
        resource_group,
        table_name,
        datasource_type,
        env_type,
    )


def _load_source_columns(
        client: BFFClient,
        project_id: int,
        tenant_id: int,
        datasource_name: str,
        datasource_type: str,
        resource_group: str,
        table_name: str,
        env_type: int,
        guid: Optional[str] = None,
) -> Dict[str, Any]:
    metadata = load_table_metadata(
        client,
        project_id,
        tenant_id,
        datasource_name,
        datasource_type,
        resource_group,
        table_name,
        env_type,
        guid=guid,
    )
    if not metadata:
        raise RuntimeError(f"未找到表结构信息: {datasource_name}.{table_name}")
    raw = dict(metadata.get("raw") or {})
    raw.setdefault("columns", metadata.get("columns") or [])
    raw.setdefault("partitionColumns", metadata.get("partition_columns") or [])
    raw.setdefault("tableComment", metadata.get("table_comment") or "")
    return raw


def _build_verify_params(
        client: BFFClient,
        project_id: int,
        tenant_id: int,
        datasource_name: str,
        datasource_type: str,
        resource_group: str,
        table_name: str,
        env_type: int,
) -> Dict[str, Any]:
    params = build_table_column_params(
        client,
        project_id,
        tenant_id,
        datasource_name,
        datasource_type,
        resource_group,
        table_name,
        env_type,
    )
    if not params:
        raise RuntimeError(f"未找到目标端表信息: {datasource_name}.{table_name}")
    return params


def _extract_partition_clause(ddl: str) -> str:
    match = re.search(r"PARTITIONED BY\s*\((.*?)\)", ddl, re.IGNORECASE | re.DOTALL)
    if not match:
        return "无分区"
    return " ".join(match.group(1).split())


def _build_add_table_params(
        project_id: int,
        tenant_id: int,
        src_datasource: str,
        src_type: str,
        src_table: str,
        dst_datasource: str,
        dst_type: str,
        dst_table: str,
        resource_group: str,
        source_meta: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "projectId": project_id,
        "tenantId": tenant_id,
        "tableComment": source_meta.get("tableComment") or "",
        "readerTableName": src_table,
        "srcDataSourceType": _normalize_type(src_type),
        "tableColumn": source_meta["columns"],
        "srcTableName": src_table,
        "partitionColumns": source_meta.get("partitionColumns") or [],
        "dstDataSourceType": _normalize_type(dst_type),
        "dstDataSourceName": dst_datasource,
        "dstDataSourceEnvType": _DEFAULT_ENV_TYPE,
        "partitionColumn": source_meta.get("partitionColumns") or [],
    }


def _rewrite_ddl_table_name(ddl: str, target_table: str, generated_name: Optional[str]) -> str:
    if generated_name and generated_name != target_table:
        return ddl.replace(generated_name, target_table)
    if "your_table_name" in ddl:
        return ddl.replace("your_table_name", target_table)
    return ddl


def _normalize_ddl(ddl: str, dst_table: str) -> str:
    # partition field: pt → ds
    ddl = re.sub(r"\bpt\b(?=\s+STRING)", "ds", ddl, flags=re.IGNORECASE)
    ddl = re.sub(r"PARTITIONED BY\s*\(\s*`?pt`?\s+", "PARTITIONED BY (ds ", ddl, flags=re.IGNORECASE)
    # lifecycle: any value → 7
    ddl = re.sub(r"LIFECYCLE\s+\d+", "LIFECYCLE 7", ddl, flags=re.IGNORECASE)
    return ddl


def _load_columns_file(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"--columns-file 必须是列数组（JSON array），实际类型: {type(data).__name__}")
    return data


def prepare(args: argparse.Namespace) -> None:
    print_confirmed_params()
    client = BFFClient(quiet=True)
    project_id = args.project_id
    tenant_id = args.tenant_id
    resource_group = args.resource_group or _pick_di_resource_group(client, project_id)

    if _table_exists(
            client,
            project_id,
            tenant_id,
            args.dst_datasource,
            resource_group,
            args.dst_table,
            _DEFAULT_ENV_TYPE,
            args.dst_type,
    ):
        print(f"{_TAG} 目标表已存在，无需创建: {args.dst_datasource}.{args.dst_table}")
        save_tool_result("ensure_target_table", {
            "summary": f"目标表已存在: {args.dst_table}",
            "status": "exists",
            "project_id": project_id,
            "table": args.dst_table,
            "resource_group": resource_group,
        })
        # 累积参数（agent 注意力辅助层）
        remember(target_table_status="exists")
        return

    if args.columns_file:
        print(f"{_TAG} 使用 --columns-file 跳过源端列信息拉取: {args.columns_file}")
        columns = _load_columns_file(args.columns_file)
        source_meta: Dict[str, Any] = {
            "columns": columns,
            "partitionColumns": [],
            "tableComment": "",
        }
    else:
        src_guid = getattr(args, "src_guid", None)
        if is_idb_datasource(args.src_datasource or "") and not src_guid:
            print(
                f"{_TAG} ⚠️  IDB 数据源 ({args.src_datasource}) 需要 --src-guid 才能获取字段注释。\n"
                f"{_TAG}    格式: IDB_<dsId>.<schema>.<table>（从参考节点 GetNode spec 的 reader.guid 复制）。\n"
                f"{_TAG}    示例: --src-guid IDB_1848949466.aone_km_x.page_content_version"
            )
        source_meta = _load_source_columns(
            client,
            project_id,
            tenant_id,
            args.src_datasource,
            args.src_type,
            resource_group,
            args.src_table,
            _DEFAULT_ENV_TYPE,
            guid=src_guid,
        )
    add_params = _build_add_table_params(
        project_id,
        tenant_id,
        args.src_datasource or "",
        args.src_type,
        args.src_table or "",
        args.dst_datasource,
        args.dst_type,
        args.dst_table,
        resource_group,
        source_meta,
    )
    add_result = client.load("addTable", **add_params)
    ddl = _rewrite_ddl_table_name(
        add_result.get("ddlString") or "",
        args.dst_table,
        add_result.get("tableName"),
        )
    ddl = _normalize_ddl(ddl, args.dst_table)
    partition_clause = _extract_partition_clause(ddl)

    print(f"{_TAG} 检测到目标表不存在: {args.dst_datasource}.{args.dst_table}")
    print(f"{_TAG} 自动生成建表 DDL 完成，待用户确认")
    print(f"{_TAG}   目标表名: {args.dst_table}")
    print(f"{_TAG}   分区策略: {partition_clause}")
    print(f"{_TAG}   数据集成资源组: {resource_group}")
    print(f"{_TAG} DDL:")
    print(ddl)

    pending = {
        "api_name": "createTableByDDL",
        "created_at": datetime.now().isoformat(),
        "project_id": project_id,
        "tenant_id": tenant_id,
        "dst_datasource": args.dst_datasource,
        "dst_table": args.dst_table,
        "resource_group": resource_group,
        "ddl": ddl,
        "write_params": {
            "projectId": project_id,
            "tenantId": tenant_id,
            "ddlString": ddl,
            "datasourceName": args.dst_datasource,
            "resgroupIdentifier": resource_group,
        },
        "dst_type": args.dst_type,
    }
    _save_pending(pending)

    print(f"⚠️ 待确认写操作: createTableByDDL")
    print(
        "  参数: "
        f"projectId={project_id!r}, tenantId={tenant_id!r}, ddlString={ddl!r}, "
        f"datasourceName={args.dst_datasource!r}, resgroupIdentifier={resource_group!r}"
    )
    print(f"  → 用户确认后执行: {_confirm_command()}")

    telemetry_end(result={"status": "pending_confirm", "table": args.dst_table})
    save_tool_result("ensure_target_table", {
        "summary": f"已生成目标表 DDL，待确认建表: {args.dst_table}",
        "status": "pending_confirm",
        "project_id": project_id,
        "table": args.dst_table,
        "resource_group": resource_group,
        "partition_strategy": partition_clause,
    })
    # 累积参数（agent 注意力辅助层）
    remember(target_table_status="pending_create")


def confirm() -> None:
    pending = _load_pending()
    _validate_confirm_window(pending.get("created_at"))
    client = BFFClient(quiet=True)
    print(f"✅ 执行写操作: {pending['api_name']}")
    result = client._call(pending["api_name"], confirmed=True, **pending["write_params"])
    verify_params = _build_verify_params(
        client,
        pending["project_id"],
        pending["tenant_id"],
        pending["dst_datasource"],
        pending.get("dst_type") or "",
        pending["resource_group"],
        pending["dst_table"],
        _DEFAULT_ENV_TYPE,
    )
    verify = client.load("getTableColumnPost", **verify_params)
    _remove_pending()

    columns: List[Dict[str, Any]] = verify.get("columns") or []
    partition_columns = verify.get("partitionColumns") or []

    print(f"{_TAG} ✅ 目标表创建成功: {pending['dst_datasource']}.{pending['dst_table']}")
    print(f"{_TAG}   字段数: {len(columns)}")
    print(f"{_TAG}   分区字段: {partition_columns if partition_columns else '无'}")
    if columns:
        preview = ", ".join(c.get("name", "") for c in columns[:10])
        print(f"{_TAG}   字段预览: {preview}")

    telemetry_end(result={"status": "success", "table": pending["dst_table"]})
    save_tool_result("ensure_target_table", {
        "summary": f"目标表已创建并验证成功: {pending['dst_table']}",
        "status": "success",
        "project_id": pending["project_id"],
        "table": pending["dst_table"],
        "resource_group": pending["resource_group"],
        "create_result": result,
        "partition_columns": partition_columns,
        "column_count": len(columns),
    })


def main() -> None:
    parser = argparse.ArgumentParser(
        description="数据集成目标表保障工具（检测不存在 → 生成DDL → 用户确认 → 建表 → 回查）",
        usage="%(prog)s --project-id <id> --src-datasource <name> --src-type MYSQL --src-table <table> "
              "--dst-datasource <name> --dst-type ODPS --dst-table <table> [--resource-group <rg>] | %(prog)s --confirm",
    )
    parser.add_argument("--confirm", action="store_true", help="执行已确认的建表操作")
    parser.add_argument("--project-id", type=int, help="工作空间 ID")
    parser.add_argument("--tenant-id", type=int, default=1, help="租户 ID，默认 1")
    parser.add_argument("--src-datasource", help="源端数据源名称")
    parser.add_argument("--src-type", default="MYSQL", help="源端数据源类型，默认 MYSQL")
    parser.add_argument("--src-table", help="源表名")
    parser.add_argument("--dst-datasource", help="目标端数据源名称")
    parser.add_argument("--dst-type", default="ODPS", help="目标端数据源类型，默认 ODPS")
    parser.add_argument("--dst-table", help="目标表名")
    parser.add_argument("--resource-group", help="数据集成资源组标识；不传则自动选择默认资源组")
    parser.add_argument(
        "--columns-file",
        help=(
            "源表列信息 JSON 文件路径（绕过 IDB accessId 限制）。"
            "格式：[{\"name\":\"id\",\"type\":\"bigint(20)\",\"comment\":\"\",\"nullable\":\"false\",\"primaryKey\":\"true\"}, ...]。"
            "传此参数时 --src-datasource 可省略。"
        ),
    )
    parser.add_argument(
        "--src-guid",
        help=(
            "IDB 源表的 guid（用于获取字段注释）。"
            "格式：IDB_<dsId>.<schema>.<table>，从参考节点 GetNode spec 的 reader.guid 字段复制。"
            "示例：IDB_1848949466.aone_km_x.page_content_version"
        ),
    )

    args = parser.parse_args()

    telemetry_start("ensure_target_table.py", module="data-integration", project_id=args.project_id)
    if args.confirm:
        confirm()
        return

    # src_datasource 仅在未提供 --columns-file 时必填
    required = [
        ("project_id", args.project_id),
        ("src_table", args.src_table),
        ("dst_datasource", args.dst_datasource),
        ("dst_table", args.dst_table),
    ]
    if not args.columns_file:
        required.append(("src_datasource", args.src_datasource))
    missing = [name for name, value in required if not value]
    if missing:
        parser.error(f"缺少必填参数: {', '.join(missing)}")

    prepare(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        telemetry_fail("ensure_target_table.py", "data-integration", e.code if e.code else 1, error="SystemExit")
        raise
    except Exception as e:
        telemetry_fail("ensure_target_table.py", "data-integration", 1, error=str(e)[:100])
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(1)
