from typing import Any, Dict, List, Optional

_DEFAULT_ENV_TYPE = 1
_DEFAULT_SUBTYPE = "public"
_TDDL_SUBTYPE = "inner"
_TDDL_MASTER_SLAVE = "only_slave"
_IDB_SUBTYPE = "inner"
_IDB_NAME_PREFIX = "_IDB."
_IDB_STEP_TYPE = "mysql"


def normalize_datasource_type(value: str) -> str:
    return (value or "").strip().lower()


def mysql_to_odps_type(mysql_type: str) -> str:
    """Map MySQL column type to ODPS/MaxCompute type for CREATE TABLE DDL."""
    t = (mysql_type or "").upper().split("(")[0].strip()
    mapping = {
        "BIGINT": "BIGINT", "INT": "BIGINT", "INTEGER": "BIGINT",
        "TINYINT": "BIGINT", "SMALLINT": "BIGINT", "MEDIUMINT": "BIGINT",
        "UNSIGNED": "BIGINT",
        "VARCHAR": "STRING", "TEXT": "STRING", "MEDIUMTEXT": "STRING",
        "LONGTEXT": "STRING", "TINYTEXT": "STRING", "CHAR": "STRING",
        "BLOB": "STRING", "MEDIUMBLOB": "STRING", "LONGBLOB": "STRING",
        "JSON": "STRING",
        "DATETIME": "DATETIME", "TIMESTAMP": "DATETIME",
        "DATE": "STRING",
        "DOUBLE": "DOUBLE", "FLOAT": "DOUBLE", "DECIMAL": "DOUBLE",
        "BOOLEAN": "BIGINT", "BOOL": "BIGINT",
        "BIT": "BIGINT",
    }
    return mapping.get(t, "STRING")


def is_tddl_type(datasource_type: str) -> bool:
    return normalize_datasource_type(datasource_type) == "tddl"


def is_idb_datasource(datasource_name: str) -> bool:
    """IDB sources start with '_IDB.' (e.g. '_IDB.TAOBAO')."""
    return (datasource_name or "").upper().startswith(_IDB_NAME_PREFIX.upper())


def resolve_idb_table_info(
    client: Any,
    project_id: int,
    tenant_id: int,
    datasource_name: str,
    resource_group: str,
    table_name: str,
    env_type: int = _DEFAULT_ENV_TYPE,
) -> Optional[Dict[str, Any]]:
    """Resolve IDB table record (including guid) via getTableListPost.

    IDB table_name must be in 'schema.table' format (e.g. 'aone_km_x.page_content_version').
    The response record contains 'guid' in the format 'IDB_<dsId>.<schema>.<table>'.
    """
    rows = client.load(
        "getTableListPost",
        projectId=project_id,
        tenantId=tenant_id,
        table=table_name,
        envType=env_type,
        datasourceName=datasource_name,
        resourceGroup=resource_group,
        subType=_IDB_SUBTYPE,
        stepType=_IDB_STEP_TYPE,
        datasourceType=_IDB_STEP_TYPE,
        pageNum=1,
        pageSize=10,
    )
    for row in rows or []:
        if row.get("guid"):
            return row
    if rows:
        return rows[0]
    return None


def resolve_tddl_table_info(
    client: Any,
    project_id: int,
    tenant_id: int,
    datasource_name: str,
    resource_group: str,
    table_name: str,
    env_type: int = _DEFAULT_ENV_TYPE,
    app_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    params = {
        "projectId": project_id,
        "tenantId": tenant_id,
        "table": table_name,
        "envType": env_type,
        "datasourceName": datasource_name,
        "resourceGroup": resource_group,
        "subType": _TDDL_SUBTYPE,
        "stepType": "tddl",
        "datasourceType": "tddl",
        "pageNum": 1,
        "pageSize": 200,
    }
    if app_name:
        params["appName"] = app_name
    rows = client.load("getTableListPost", **params)
    for row in rows or []:
        candidate = row.get("tableName") or row.get("table") or ""
        if candidate == table_name and row.get("guid") and row.get("appName"):
            return row
    if rows:
        return rows[0]
    return None


def build_table_column_params(
    client: Any,
    project_id: int,
    tenant_id: int,
    datasource_name: str,
    datasource_type: str,
    resource_group: str,
    table_name: str,
    env_type: int = _DEFAULT_ENV_TYPE,
    app_name: Optional[str] = None,
    guid: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    normalized_type = normalize_datasource_type(datasource_type)
    params: Dict[str, Any] = {
        "projectId": project_id,
        "tenantId": tenant_id,
        "envType": env_type,
        "datasourceName": datasource_name,
        "resourceGroup": resource_group,
        "stepType": normalized_type,
        "datasourceType": normalized_type,
        "table": table_name,
    }
    if is_tddl_type(normalized_type):
        table_info = resolve_tddl_table_info(
            client,
            project_id,
            tenant_id,
            datasource_name,
            resource_group,
            table_name,
            env_type,
            app_name,
        )
        if not table_info:
            return None
        params.update({
            "appName": table_info.get("appName"),
            "subType": _TDDL_SUBTYPE,
            "guid": table_info.get("guid"),
            "stepType": "tddl",
            "datasourceType": "tddl",
        })
        return params
    if is_idb_datasource(datasource_name):
        # IDB sources require subType='inner' + guid ('IDB_<dsId>.<schema>.<table>').
        # Auto-resolve guid from getTableListPost if not supplied by caller.
        resolved_guid = guid
        if not resolved_guid:
            table_info = resolve_idb_table_info(
                client, project_id, tenant_id, datasource_name,
                resource_group, table_name, env_type,
            )
            resolved_guid = (table_info or {}).get("guid")
        params.update({
            "subType": _IDB_SUBTYPE,
            "stepType": _IDB_STEP_TYPE,
            "datasourceType": _IDB_STEP_TYPE,
            "guid": resolved_guid,
        })
        return params
    params.update({"subType": _DEFAULT_SUBTYPE, "guid": None})
    return params


def _is_partitioned(raw_meta: Dict[str, Any], table_info: Optional[Dict[str, Any]] = None) -> bool:
    if raw_meta.get("partitionColumns"):
        return True
    if raw_meta.get("partitionColumnMeta"):
        return True
    if raw_meta.get("partitionKey"):
        return True
    if raw_meta.get("partitionList"):
        return True
    if table_info and table_info.get("partitionTableFlag") is True:
        return True
    return False


def _extract_primary_key_columns(columns: List[Dict[str, Any]]) -> List[str]:
    result = []
    for column in columns or []:
        if str(column.get("primaryKey", "")).lower() == "true" and column.get("name"):
            result.append(column["name"])
    return result


def load_table_metadata(
    client: Any,
    project_id: int,
    tenant_id: int,
    datasource_name: str,
    datasource_type: str,
    resource_group: str,
    table_name: str,
    env_type: int = _DEFAULT_ENV_TYPE,
    app_name: Optional[str] = None,
    guid: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    normalized_type = normalize_datasource_type(datasource_type)
    table_info = None
    if is_tddl_type(normalized_type):
        table_info = resolve_tddl_table_info(
            client,
            project_id,
            tenant_id,
            datasource_name,
            resource_group,
            table_name,
            env_type,
            app_name,
        )
        if not table_info:
            return None
    params = build_table_column_params(
        client,
        project_id,
        tenant_id,
        datasource_name,
        normalized_type,
        resource_group,
        table_name,
        env_type,
        app_name,
        guid=guid,
    )
    if not params:
        return None
    raw_meta = client.load("getTableColumnPost", **params)
    if not isinstance(raw_meta, dict):
        return None

    columns = raw_meta.get("columns") or []
    split_pk_candidates = raw_meta.get("splitPk") or []
    partition_columns = raw_meta.get("partitionColumns") or []
    partition_column_meta = raw_meta.get("partitionColumnMeta") or []
    metadata = {
        "columns": columns,
        "column_names": [c.get("name") for c in columns if c.get("name")],
        "column_types": {
            c.get("name"): mysql_to_odps_type(c.get("type") or c.get("dataType") or "")
            for c in columns if c.get("name")
        },
        "column_comments": {
            c.get("name"): (c.get("comment") or c.get("columnComment") or "")
            for c in columns if c.get("name")
        },
        "primary_key_columns": _extract_primary_key_columns(columns),
        "indexes": raw_meta.get("indexes") or [],
        "split_pk_candidates": split_pk_candidates,
        "split_pk": split_pk_candidates[0] if split_pk_candidates else None,
        "partition_columns": partition_columns,
        "partition_column_meta": partition_column_meta,
        "partition_key": raw_meta.get("partitionKey"),
        "partition_list": raw_meta.get("partitionList"),
        "table_comment": raw_meta.get("tableComment") or "",
        "is_partitioned": _is_partitioned(raw_meta, table_info),
        "table_info": table_info or {},
        "raw": raw_meta,
        "column_params": params,
        "reader_extra": {},
    }
    if is_tddl_type(normalized_type):
        metadata["reader_extra"] = {
            "appName": params.get("appName"),
            "guid": params.get("guid"),
            "masterSlave": _TDDL_MASTER_SLAVE,
        }
    elif is_idb_datasource(datasource_name):
        metadata["reader_extra"] = {
            "guid": params.get("guid"),
            "masterSlave": "slave",
            "slaveDelayLimit": 300,
            "socketTimeout": 3600000,
        }
    return metadata


def load_table_names(
    client: Any,
    project_id: int,
    tenant_id: int,
    datasource_name: str,
    resource_group: str,
    datasource_type: str = "",
    env_type: int = _DEFAULT_ENV_TYPE,
) -> Optional[List[str]]:
    params: Dict[str, Any] = {
        "projectId": project_id,
        "tenantId": tenant_id,
        "datasourceName": datasource_name,
        "resourceGroup": resource_group,
        "envType": env_type,
        "table": None,
        "pageNum": 1,
        "pageSize": 200,
    }
    if is_tddl_type(datasource_type):
        params.update({
            "subType": _TDDL_SUBTYPE,
            "stepType": "tddl",
            "datasourceType": "tddl",
        })
    elif is_idb_datasource(datasource_name):
        params.update({
            "subType": _IDB_SUBTYPE,
            "stepType": _IDB_STEP_TYPE,
            "datasourceType": _IDB_STEP_TYPE,
        })
    else:
        params["datasourceType"] = normalize_datasource_type(datasource_type)
        params["schemaName"] = ""
    rows = client.load("getTableListPost", **params)
    return [r.get("tableName") or r.get("table") or "" for r in rows or [] if r]


def table_exists(
    client: Any,
    project_id: int,
    tenant_id: int,
    datasource_name: str,
    resource_group: str,
    table_name: str,
    datasource_type: str = "",
    env_type: int = _DEFAULT_ENV_TYPE,
    app_name: Optional[str] = None,
) -> bool:
    if is_tddl_type(datasource_type):
        table_info = resolve_tddl_table_info(
            client,
            project_id,
            tenant_id,
            datasource_name,
            resource_group,
            table_name,
            env_type,
            app_name,
        )
        return bool(table_info and ((table_info.get("tableName") or table_info.get("table")) == table_name))
    if is_idb_datasource(datasource_name):
        table_info = resolve_idb_table_info(
            client, project_id, tenant_id, datasource_name,
            resource_group, table_name, env_type,
        )
        return bool(table_info)
    normalized_type = normalize_datasource_type(datasource_type)
    rows = client.load(
        "getTableListPost",
        projectId=project_id,
        tenantId=tenant_id,
        table=table_name,
        envType=env_type,
        datasourceName=datasource_name,
        datasourceType=normalized_type,
        resourceGroup=resource_group,
        schemaName="",
        pageNum=1,
        pageSize=20,
    )
    exact = [r for r in rows or [] if (r.get("tableName") or r.get("table")) == table_name]
    return bool(exact)


def build_odps_partition_value(target_metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    if not target_metadata or not target_metadata.get("is_partitioned"):
        return None
    partition_columns = target_metadata.get("partition_columns") or []
    names = []
    for item in partition_columns:
        if isinstance(item, dict):
            name = item.get("name") or item.get("columnName") or item.get("partitionColumnName")
        else:
            name = item
        if name:
            names.append(str(name))
    if not names:
        return None
    return ",".join(f"{name}=${{bizdate}}" for name in names)
