"""钉钉 AI 表格 MCP 封装。

通过钉钉 AI 表格 MCP（mcpId=9555）操作 Base / Table / Field / Record / View /
Dashboard / Chart / AI 字段 等资源。

入口（Base）说明：
- 大部分函数都以 baseId 为入口，可通过 list_bases / search_bases 获取
- baseId 既支持纯 32 位 ID，也支持完整的 AI 表格链接（服务端会自动解析）

设计原则：
- 高频工具提供独立函数（强类型参数）
- 47 个 MCP 工具不全部包装，复杂工具（dashboard config 等）通过 raw_call 直通
"""

from ._mcp_client import (  # noqa: F401  (re-export)
    DingMCPError,
    setup,
    list_servers,
    remove_server,
    list_mcp_tools,
    try_servers,
    extract_id,
)

_TYPE = "ai_table"


def _id(x):
    """AI 表格 MCP 严格要求 baseId/tableId 等只含字母数字；URL 必须先抽 ID。"""
    return extract_id(x)


# ============================================================
# 通用直通入口（覆盖未单独包装的 27/47 个工具）
# ============================================================


def raw_call(tool_name, arguments=None, timeout=60):
    """直通调用任意 AI 表格 MCP 工具。

    用法:
        raw_call("get_dashboard_config_example", {})
        raw_call("create_dashboard", {"baseId": "...", "config": {...}})
    """
    return try_servers(_TYPE, tool_name, arguments or {}, timeout=timeout)


# ============================================================
# Base（AI 表格）
# ============================================================


def list_bases(limit=None, cursor=None):
    """列出当前用户可访问的 AI 表格 Base（默认按最近访问，每页最大 10）。"""
    args = {}
    if limit is not None:
        args["limit"] = limit
    if cursor:
        args["cursor"] = cursor
    return try_servers(_TYPE, "list_bases", args)


def search_bases(query, cursor=None):
    """按名称关键词搜索 AI 表格 Base。"""
    args = {"query": query}
    if cursor:
        args["cursor"] = cursor
    return try_servers(_TYPE, "search_bases", args)


def get_base(base_id):
    """获取 Base 的资源目录信息（tables / dashboards summary，不含字段与记录详情）。"""
    return try_servers(_TYPE, "get_base", {"baseId": _id(base_id)})


def create_base(base_name, folder_id=None, template_id=None):
    """创建新的 AI 表格 Base。"""
    args = {"baseName": base_name}
    if folder_id:
        args["folderId"] = _id(folder_id)
    if template_id:
        args["templateId"] = template_id
    return try_servers(_TYPE, "create_base", args)


def update_base(base_id, new_base_name, description=None):
    """重命名 Base，可选追加备注。"""
    args = {"baseId": _id(base_id), "newBaseName": new_base_name}
    if description:
        args["description"] = description
    return try_servers(_TYPE, "update_base", args)


def delete_base(base_id, reason=None):
    """删除 Base（高风险、不可逆）。"""
    args = {"baseId": _id(base_id)}
    if reason:
        args["reason"] = reason
    return try_servers(_TYPE, "delete_base", args)


def copy_base(base_id, target_folder_id, only_copy_meta=False):
    """复制 Base 到指定文件夹。only_copy_meta=True 时只复制结构不复制数据。"""
    return try_servers(
        _TYPE,
        "copy_base",
        {
            "baseId": _id(base_id),
            "targetFolderId": _id(target_folder_id),
            "onlyCopyMeta": only_copy_meta,
        },
    )


def search_templates(query, limit=None, cursor=None):
    """按关键词搜索 AI 表格模板。templateId 可用于 create_base。"""
    args = {"query": query}
    if limit is not None:
        args["limit"] = limit
    if cursor:
        args["cursor"] = cursor
    return try_servers(_TYPE, "search_templates", args)


# ============================================================
# Table（数据表）
# ============================================================


def get_tables(base_id, table_ids=None):
    """批量获取数据表信息（含字段目录与视图目录，字段仅含 id/name/type/desc）。

    table_ids 不传 → 返回 Base 下全部表；建议显式传入以控制返回体大小。
    """
    args = {"baseId": _id(base_id)}
    if table_ids:
        args["tableIds"] = table_ids
    return try_servers(_TYPE, "get_tables", args)


def create_table(base_id, table_name, fields):
    """在指定 Base 中新建表格（单次最多 15 个字段）。

    fields 每项: {"fieldName": "...", "type": "text/number/singleSelect/...",
                  "config": {...}, "description": "...", "aiConfig": {...}}
    若不需更多字段，可传 []，服务会自动补一个 primaryDoc 首列。
    """
    return try_servers(
        _TYPE,
        "create_table",
        {"baseId": _id(base_id), "tableName": table_name, "fields": fields},
    )


def update_table(base_id, table_id, new_table_name):
    """重命名指定 Table。"""
    return try_servers(
        _TYPE,
        "update_table",
        {"baseId": _id(base_id), "tableId": table_id, "newTableName": new_table_name},
    )


def delete_table(base_id, table_id, reason=None):
    """删除指定 Table（不可逆）。"""
    args = {"baseId": _id(base_id), "tableId": table_id}
    if reason:
        args["reason"] = reason
    return try_servers(_TYPE, "delete_table", args)


# ============================================================
# Field（字段）
# ============================================================


def get_fields(base_id, table_id, field_ids=None):
    """批量获取字段的完整配置（含 options / aiConfig 等）。单次最多 10 个字段。"""
    args = {"baseId": _id(base_id), "tableId": table_id}
    if field_ids:
        args["fieldIds"] = field_ids
    return try_servers(_TYPE, "get_fields", args)


def create_fields(base_id, table_id, fields):
    """在已有表格中批量新增字段（单次最多 15 个）。

    每个 field: {"fieldName": "...", "type": "...", "config": {...}, "aiConfig": {...}}
    支持的类型: text/number/singleSelect/multipleSelect/date/currency/user/department/
              group/progress/rating/checkbox/attachment/url/richText/telephone/email/
              idCard/barcode/geolocation/address/primaryDoc/formula/filterUp/lookup/
              unidirectionalLink/bidirectionalLink/creator/lastModifier/createdTime/
              lastModifiedTime
    """
    return try_servers(
        _TYPE,
        "create_fields",
        {"baseId": _id(base_id), "tableId": table_id, "fields": fields},
    )


def update_field(base_id, table_id, field_id, new_field_name=None, config=None, ai_config=None):
    """更新字段名称或配置（不可变更 type）。三者至少传一个。"""
    args = {"baseId": _id(base_id), "tableId": table_id, "fieldId": field_id}
    if new_field_name is not None:
        args["newFieldName"] = new_field_name
    if config is not None:
        args["config"] = config
    if ai_config is not None:
        args["aiConfig"] = ai_config
    return try_servers(_TYPE, "update_field", args)


def delete_field(base_id, table_id, field_id):
    """删除指定字段（不可逆；不能删主字段和最后一个字段）。"""
    return try_servers(
        _TYPE,
        "delete_field",
        {"baseId": _id(base_id), "tableId": table_id, "fieldId": field_id},
    )


# ============================================================
# Record（记录）
# ============================================================


def query_records(
    base_id,
    table_id,
    record_ids=None,
    field_ids=None,
    filters=None,
    sort=None,
    limit=None,
    cursor=None,
):
    """查询记录，两种模式：
    - 按 ID 取：传 record_ids（单次最多 100 个）
    - 条件查：用 filters / sort / cursor 分页遍历

    field_ids: 限制返回字段（最多 100），可节省 token；计算/查找引用字段必须显式列出
    filters 结构示例：
        {"operator": "and",
         "operands": [
            {"fieldId": "fld_xxx", "operator": "eq", "value": "进行中"},
            {"fieldId": "fld_yyy", "operator": "gt", "value": 100}
         ]}
    sort 示例：[{"fieldId": "fld_xxx", "direction": "asc"}, ...]
    """
    args = {"baseId": _id(base_id), "tableId": table_id}
    if record_ids:
        args["recordIds"] = record_ids
    if field_ids:
        args["fieldIds"] = field_ids
    if filters:
        args["filters"] = filters
    if sort:
        args["sort"] = sort
    if limit is not None:
        args["limit"] = limit
    if cursor:
        args["cursor"] = cursor
    return try_servers(_TYPE, "query_records", args)


def create_records(base_id, table_id, records):
    """批量新增记录。

    records 每项: {"cells": {"<fieldId>": <值>, ...}}

    写入格式参考（详见 MCP 文档）：
        text                → "文本"
        number/currency     → 123 / 123.45（也接受 "123"）
        progress            → 0~1（0.5 表示 50%）
        rating              → 数字（min~max 范围内）
        singleSelect        → "选项名"
        multipleSelect      → ["选项1", "选项2"]
        date                → "2026-03-15" / "2026-03-15 09:00" / RFC3339 / 毫秒时间戳
        checkbox            → true | false
        user                → [{"userId": "...", "corpId": "..."}]
        department          → [{"deptId": "..."}]
        group               → [{"cid": "..."}]
        attachment          → 外链 [{"url": "https://..."}] 或 上传后 [{"fileToken": "..."}]
        url                 → "https://..."
        telephone/email/...  → 字符串
    """
    return try_servers(
        _TYPE,
        "create_records",
        {"baseId": _id(base_id), "tableId": table_id, "records": records},
    )


def update_records(base_id, table_id, records):
    """批量更新记录字段值。只需传需修改的字段，未传字段保持原值。

    records 每项: {"recordId": "...", "cells": {"<fieldId>": <新值>, ...}}
    """
    return try_servers(
        _TYPE,
        "update_records",
        {"baseId": _id(base_id), "tableId": table_id, "records": records},
    )


def delete_records(base_id, table_id, record_ids):
    """批量删除记录（单次最多 100 条，不可逆）。"""
    return try_servers(
        _TYPE,
        "delete_records",
        {"baseId": _id(base_id), "tableId": table_id, "recordIds": record_ids},
    )


def get_base_primary_doc_id(base_id, table_id, record_id):
    """获取记录主键文档对应的 dentryUuid，可拿去钉钉文档 MCP 做读写。"""
    return try_servers(
        _TYPE,
        "get_base_primary_doc_id",
        {"baseId": _id(base_id), "tableId": table_id, "recordId": record_id},
    )


# ============================================================
# View（视图）
# ============================================================


def get_views(base_id, table_id, view_ids=None):
    """获取视图完整信息（列顺序 / 筛选 / 排序 / 分组 / 条件格式）。单次最多 10 个视图。"""
    args = {"baseId": _id(base_id), "tableId": table_id}
    if view_ids:
        args["viewIds"] = view_ids
    return try_servers(_TYPE, "get_views", args)


def create_view(base_id, table_id, view_type, view_name=None, config=None):
    """创建视图。view_type ∈ Grid / FormDesigner / Gantt / Calendar / Kanban / Gallery。

    config 可含: visibleFieldIds / filter / sort / group
    """
    args = {"baseId": _id(base_id), "tableId": table_id, "viewType": view_type}
    if view_name:
        args["viewName"] = view_name
    if config:
        args["config"] = config
    return try_servers(_TYPE, "create_view", args)


def update_view(
    base_id,
    table_id,
    view_id,
    new_view_name=None,
    view_description=None,
    config=None,
):
    """更新视图名称 / 描述 / 配置（visibleFieldIds / filter / sort / group / fieldWidths）。"""
    args = {"baseId": _id(base_id), "tableId": table_id, "viewId": view_id}
    if new_view_name is not None:
        args["newViewName"] = new_view_name
    if view_description is not None:
        args["viewDescription"] = view_description
    if config is not None:
        args["config"] = config
    return try_servers(_TYPE, "update_view", args)


def delete_view(base_id, table_id, view_id):
    """删除视图（最后一个视图和锁定视图不可删）。"""
    return try_servers(
        _TYPE,
        "delete_view",
        {"baseId": _id(base_id), "tableId": table_id, "viewId": view_id},
    )


# ============================================================
# AI 字段
# ============================================================


def run_ai_field(base_id, table_id, field_ids, record_ids=None):
    """触发 AI 字段运行。最多 10 个字段；record_ids 不传则整列刷新（最多 500 条）。

    异步：仅提交任务即返回；运行进度需到文档查看。
    """
    args = {"baseId": _id(base_id), "tableId": table_id, "fieldIds": field_ids}
    if record_ids:
        args["recordIds"] = record_ids
    return try_servers(_TYPE, "run_ai_field", args)


# ============================================================
# 导入 / 导出 / 附件
# ============================================================


def prepare_attachment_upload(base_id, file_name, size, mime_type=None):
    """为 attachment 字段申请 OSS 直传 URL。返回 uploadUrl + fileToken。

    如果已有可下载的外链 URL，**不要**先下载再传；直接在写入时用 [{"url": "..."}]。
    """
    args = {"baseId": _id(base_id), "fileName": file_name, "size": size}
    if mime_type:
        args["mimeType"] = mime_type
    return try_servers(_TYPE, "prepare_attachment_upload", args)


def prepare_import_upload(base_id, file_name, file_size):
    """为导入任务申请 OSS 直传地址。返回 uploadUrl + importId。"""
    return try_servers(
        _TYPE,
        "prepare_import_upload",
        {"baseId": _id(base_id), "fileName": file_name, "fileSize": file_size},
    )


def import_data(import_id, timeout=None):
    """将已上传的文件导入 AI 表格。每个 Sheet 会新建为独立的数据表。

    内部会等待 timeout 秒（默认/最大 30）；未完成时再次以相同 importId 调用即可继续等待。
    """
    args = {"importId": import_id}
    if timeout is not None:
        args["timeout"] = timeout
    return try_servers(_TYPE, "import_data", args)


def export_data(
    base_id,
    scope=None,
    format=None,
    table_id=None,
    view_id=None,
    task_id=None,
    timeout_ms=None,
):
    """导出 AI 表格数据。
    - 创建新任务：传 scope (all/table/view) + format (excel/attachment/...)
    - 继续等待：仅传 task_id
    超时未完成会返回 taskId，下次再传入继续等待。
    """
    args = {"baseId": _id(base_id)}
    if scope:
        args["scope"] = scope
    if format:
        args["format"] = format
    if table_id:
        args["tableId"] = table_id
    if view_id:
        args["viewId"] = view_id
    if task_id:
        args["taskId"] = task_id
    if timeout_ms is not None:
        args["timeoutMs"] = timeout_ms
    return try_servers(_TYPE, "export_data", args)


# ============================================================
# 说明文档（Guide Document，Base 内导航栏文档）
# ============================================================


def create_guide_document(base_id, name=None):
    """在 Base 中创建说明文档（每个 Base 最多 5 个；需管理员权限）。

    返回 documentId 可作为钉钉文档 MCP 的 nodeId 使用。
    """
    args = {"baseId": _id(base_id)}
    if name:
        args["name"] = name
    return try_servers(_TYPE, "create_guide_document", args)


def update_guide_document(base_id, document_id, new_document_name):
    """重命名说明文档。"""
    return try_servers(
        _TYPE,
        "update_guide_document",
        {"baseId": _id(base_id), "documentId": document_id, "newDocumentName": new_document_name},
    )


def delete_guide_document(base_id, document_id, reason=None):
    """删除说明文档（不可逆）。"""
    args = {"baseId": _id(base_id), "documentId": document_id}
    if reason:
        args["reason"] = reason
    return try_servers(_TYPE, "delete_guide_document", args)
