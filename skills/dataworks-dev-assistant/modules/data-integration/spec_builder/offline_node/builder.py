"""单表离线同步 DI JSON 配置构造器

纯函数，不依赖 BFF API / 网络 / 文件系统。
输入结构化参数 → 输出 DI JSON dict。
"""

from typing import Any, Dict, List, Optional

from spec_builder.common.datasource_registry import DatasourceInfo


def build_reader_step(
    ds_info: DatasourceInfo,
    datasource: str,
    table: str,
    columns: List[str],
    split_pk: Optional[str] = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构造 Reader step dict"""
    table_field = ds_info.reader_table_field

    # For mysql/IDB: table may be "schema.table" (e.g. "aone_km_x.page_content_version"),
    # but DI reader config requires bare table name only.
    effective_table = table.split(".")[-1] if ds_info.step_type == "mysql" and "." in table else table

    parameter: Dict[str, Any] = {"column": columns}

    # 根据 param_mode 决定 datasource/table 放在哪
    if ds_info.reader_prefer == "toplevel" or ds_info.reader_param_mode == "toplevel":
        parameter["datasource"] = datasource
        if table_field and effective_table:
            parameter[table_field] = effective_table
    else:
        # connection 模式
        conn_entry: Dict[str, Any] = {"datasource": datasource}
        if table_field and effective_table:
            conn_entry[table_field] = [effective_table]
        parameter["connection"] = [conn_entry]

    # 元数据默认值
    for k, v in ds_info.reader_defaults.items():
        if k not in parameter:
            parameter[k] = v

    # splitPk
    if split_pk and "splitPk" not in parameter:
        parameter["splitPk"] = split_pk

    # 额外参数（--reader-xxx）
    if extra_params:
        for k, v in extra_params.items():
            if k not in parameter:
                parameter[k] = _coerce(v)

    return {
        "stepType": ds_info.step_type,
        "parameter": parameter,
        "name": "Reader",
        "category": "reader",
    }


def build_writer_step(
    ds_info: DatasourceInfo,
    datasource: str,
    table: str,
    columns: List[str],
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构造 Writer step dict"""
    table_field = ds_info.writer_table_field

    parameter: Dict[str, Any] = {"column": columns}

    if ds_info.writer_param_mode == "toplevel":
        parameter["datasource"] = datasource
        if table_field and table:
            parameter[table_field] = table

    # 额外参数优先（用户显式传入，不可被默认值覆盖）
    if extra_params:
        for k, v in extra_params.items():
            parameter[k] = _coerce(v)

    # 元数据默认值（不覆盖已有值）
    for k, v in ds_info.writer_defaults.items():
        if k not in parameter:
            parameter[k] = v

    # schema required 中非公共字段的兜底默认
    _FALLBACK_DEFAULTS = {"truncate": True, "writeMode": "append"}
    for field in ds_info.writer_required:
        if field in ("datasource", "table", "column"):
            continue
        if field not in parameter:
            if field in _FALLBACK_DEFAULTS:
                parameter[field] = _FALLBACK_DEFAULTS[field]

    return {
        "stepType": ds_info.step_type,
        "parameter": parameter,
        "name": "Writer",
        "category": "writer",
    }


def build_di_config(
    src_info: DatasourceInfo,
    dst_info: DatasourceInfo,
    src_datasource: str,
    dst_datasource: str,
    src_table: str,
    dst_table: str,
    columns: List[str],
    resource_group: str,
    split_pk: Optional[str] = None,
    concurrent: int = 3,
    extra_reader_params: Optional[Dict[str, Any]] = None,
    extra_writer_params: Optional[Dict[str, Any]] = None,
    source_metadata: Optional[Dict[str, Any]] = None,
    target_metadata: Optional[Dict[str, Any]] = None,
    base_id: Optional[str] = None,
    task_name: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Dict[str, Any]:
    """构造完整 DI JSON 配置

    Returns:
        dict: 可直接 json.dumps 的 DI 配置
    """
    effective_columns = columns or []
    if not effective_columns and source_metadata and source_metadata.get("column_names"):
        effective_columns = source_metadata["column_names"]
    effective_split_pk = split_pk or (source_metadata.get("split_pk") if source_metadata else None)

    merged_reader_params = dict(source_metadata.get("reader_extra") or {}) if source_metadata else {}
    if extra_reader_params:
        merged_reader_params.update(extra_reader_params)

    merged_writer_params = dict(extra_writer_params or {})
    if dst_info.step_type == "odps":
        # Always add default partition for ODPS writer; override via extra_writer_params if needed.
        if "partition" not in merged_writer_params:
            if (
                target_metadata
                and target_metadata.get("is_partitioned")
                and target_metadata.get("partition_columns")
            ):
                partition_columns = target_metadata.get("partition_columns") or []
                partition_names = []
                for item in partition_columns:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("columnName") or item.get("partitionColumnName")
                    else:
                        name = item
                    if name:
                        partition_names.append(str(name))
                if partition_names:
                    merged_writer_params["partition"] = ",".join(f"{name}=${{bizdate}}" for name in partition_names)
                else:
                    merged_writer_params["partition"] = "ds=${bizdate}"
            else:
                merged_writer_params["partition"] = "ds=${bizdate}"
        # Auto-generate ODPS guid: "odps.<project_name>.<dst_table>"
        if project_name and "guid" not in merged_writer_params:
            merged_writer_params["guid"] = f"odps.{project_name}.{dst_table}"

    reader = build_reader_step(
        src_info, src_datasource, src_table, effective_columns,
        split_pk=effective_split_pk, extra_params=merged_reader_params,
    )
    writer = build_writer_step(
        dst_info, dst_datasource, dst_table, effective_columns,
        extra_params=merged_writer_params,
    )

    return {
        "type": "job",
        "version": "2.0",
        "steps": [reader, writer],
        "order": {"hops": [{"from": "Reader", "to": "Writer"}]},
        "setting": {
            "errorLimit": {"record": "0"},
            "locale": "zh_CN",
            "speed": {"throttle": False, "concurrent": concurrent},
        },
        "extend": {
            "resourceGroup": resource_group,
            "mode": "wizard",
            "__new__": "true",
            "formatType": "datax",
            **({"baseId": str(base_id)} if base_id is not None else {}),
            **({"taskName": task_name} if task_name is not None else {}),
        },
    }


def _coerce(value: Any) -> Any:
    """字符串 → 合适的 JSON 类型"""
    if not isinstance(value, str):
        return value
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    return value
