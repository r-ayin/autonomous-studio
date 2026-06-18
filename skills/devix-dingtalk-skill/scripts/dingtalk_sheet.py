"""钉钉电子表格（Sheet）MCP 封装。

通过钉钉电子表格 MCP（mcpId=9704）操作在线表格的 工作表 / 范围 / 行列 /
合并 / 筛选 / 下拉 / 浮动图片 等。

入口（spreadsheet）说明：
- 大部分函数都以 nodeId 为入口，可通过钉钉文档 MCP 的 search_docs / list_nodes 找到电子表格
- nodeId 既支持纯 32 位 dentryUuid，也支持
  https://alidocs.dingtalk.com/i/nodes/<dentryUuid>
  https://alidocs.dingtalk.com/spreadsheetv2/<dentryKey>/...  形式的链接，服务端自动识别
- sheetId 同样支持「工作表 ID」或「工作表名称」
- range 使用 A1 表示法，例如 "A1:D10"、"Sheet1!A1:D10"
"""

from ._mcp_client import (  # noqa: F401  (re-export)
    DingMCPError,
    setup,
    list_servers,
    remove_server,
    list_mcp_tools,
    try_servers,
)

_TYPE = "sheet"


# ============================================================
# 通用直通入口
# ============================================================


def raw_call(tool_name, arguments=None, timeout=60):
    """直通调用任意 Sheet MCP 工具。

    用法:
        raw_call("create_float_image", {"nodeId": "...", "sheetId": "...",
                                         "src": "https://...", "range": "A1",
                                         "width": 200, "height": 100})
    """
    return try_servers(_TYPE, tool_name, arguments or {}, timeout=timeout)


# ============================================================
# 在线表格文件（Spreadsheet 级）
# ============================================================


def create_spreadsheet(name, folder_id=None, workspace_id=None):
    """创建一个新的在线表格。

    三种放置位置：
    - 传 folder_id：放到指定文件夹
    - 只传 workspace_id：放到知识库根目录
    - 都不传：放到"我的文档"
    """
    args = {"name": name}
    if folder_id:
        args["folderId"] = folder_id
    if workspace_id:
        args["workspaceId"] = workspace_id
    return try_servers(_TYPE, "create_workspace_sheet", args)


def export_xlsx(node_id):
    """提交 xlsx 导出任务。返回 jobId，需要 query_export_job 轮询。"""
    return try_servers(
        _TYPE, "submit_export_job", {"nodeId": node_id, "exportFormat": "xlsx"}
    )


def query_export_job(job_id):
    """查询导出任务状态，完成时返回 xlsx 下载链接。"""
    return try_servers(_TYPE, "query_export_job", {"jobId": job_id})


# ============================================================
# 工作表（Worksheet 级）
# ============================================================


def get_all_sheets(node_id):
    """列出电子表格中的所有工作表（sheetId + name）。"""
    return try_servers(_TYPE, "get_all_sheets", {"nodeId": node_id})


def get_sheet(node_id, sheet_id):
    """获取指定工作表的详情（行列数、最后非空位置等）。sheet_id 也可传 sheet 名。"""
    return try_servers(_TYPE, "get_sheet", {"nodeId": node_id, "sheetId": sheet_id})


def create_sheet(node_id, name):
    """新增工作表（重名会自动续号）。"""
    return try_servers(_TYPE, "create_sheet", {"nodeId": node_id, "name": name})


def update_sheet(
    node_id,
    sheet_id,
    title=None,
    index=None,
    hidden=None,
    frozen_row_count=None,
    frozen_column_count=None,
):
    """更新工作表属性：重命名 / 移位 / 隐藏 / 冻结行列。"""
    args = {"nodeId": node_id, "sheetId": sheet_id}
    if title is not None:
        args["title"] = title
    if index is not None:
        args["index"] = index
    if hidden is not None:
        args["hidden"] = hidden
    if frozen_row_count is not None:
        args["frozenRowCount"] = frozen_row_count
    if frozen_column_count is not None:
        args["frozenColumnCount"] = frozen_column_count
    return try_servers(_TYPE, "update_sheet", args)


def copy_sheet(node_id, sheet_id, title=None, index=None):
    """复制工作表，在同一表格中生成副本。"""
    args = {"nodeId": node_id, "sheetId": sheet_id}
    if title is not None:
        args["title"] = title
    if index is not None:
        args["index"] = index
    return try_servers(_TYPE, "copy_sheet", args)


# ============================================================
# 单元格 / 范围（读写主力）
# ============================================================


def get_range(node_id, sheet_id=None, range=None):
    """读取单元格范围。

    - sheet_id 不传：读第一个工作表
    - range 不传：自动读该工作表全部非空数据
    - range 可写 "A1:D10" 或带前缀 "<sheetId>!A1:D10"

    返回中：
        values        → 公式计算后的值
        formulas      → 原始公式
        displayValues → 界面显示值
    均为二维数组（行 × 列）。
    """
    args = {"nodeId": node_id}
    if sheet_id is not None:
        args["sheetId"] = sheet_id
    if range is not None:
        args["range"] = range
    return try_servers(_TYPE, "get_range", args)


def update_range(
    node_id,
    sheet_id,
    range_address,
    values=None,
    hyperlinks=None,
    font_sizes=None,
    font_colors=None,
    font_weights=None,
    background_colors=None,
    horizontal_alignments=None,
    vertical_alignments=None,
    word_wrap=None,
    number_format=None,
):
    """更新指定区域的单元格（值 / 超链接 / 字体 / 颜色 / 对齐 / 数字格式 / 换行）。

    所有二维数组类参数的行列维度必须与 range_address 一致。
    values 支持：字符串、数字、公式（如 "=SUM(B2:B4)"）、null（清除）。
    """
    args = {"nodeId": node_id, "sheetId": sheet_id, "rangeAddress": range_address}
    if values is not None:
        args["values"] = values
    if hyperlinks is not None:
        args["hyperlinks"] = hyperlinks
    if font_sizes is not None:
        args["fontSizes"] = font_sizes
    if font_colors is not None:
        args["fontColors"] = font_colors
    if font_weights is not None:
        args["fontWeights"] = font_weights
    if background_colors is not None:
        args["backgroundColors"] = background_colors
    if horizontal_alignments is not None:
        args["horizontalAlignments"] = horizontal_alignments
    if vertical_alignments is not None:
        args["verticalAlignments"] = vertical_alignments
    if word_wrap is not None:
        args["wordWrap"] = word_wrap
    if number_format is not None:
        args["numberFormat"] = number_format
    return try_servers(_TYPE, "update_range", args)


def append_rows(node_id, sheet_id, values):
    """在工作表末尾追加若干行（自动定位到最后非空行下方）。

    values 为二维数组：[[行1各列], [行2各列], ...]
    返回追加数据所在的 A1 范围。
    """
    return try_servers(
        _TYPE,
        "append_rows",
        {"nodeId": node_id, "sheetId": sheet_id, "values": values},
    )


def find_cells(
    node_id,
    sheet_id,
    text,
    range=None,
    match_case=None,
    match_entire_cell=None,
    use_regexp=None,
    match_formula_text=None,
    include_hidden=None,
):
    """查找匹配的单元格，返回地址列表。

    - match_case          默认 True
    - match_entire_cell   默认 False（子串匹配）
    - use_regexp          默认 False（text 作为正则）
    - match_formula_text  默认 False（在显示值中查找；True 时在公式文本中查找）
    """
    args = {"nodeId": node_id, "sheetId": sheet_id, "text": text}
    if range is not None:
        args["range"] = range
    if match_case is not None:
        args["matchCase"] = match_case
    if match_entire_cell is not None:
        args["matchEntireCell"] = match_entire_cell
    if use_regexp is not None:
        args["useRegExp"] = use_regexp
    if match_formula_text is not None:
        args["matchFormulaText"] = match_formula_text
    if include_hidden is not None:
        args["includeHidden"] = include_hidden
    return try_servers(_TYPE, "find_cells", args)


def replace_all(
    node_id,
    sheet_id,
    text,
    replace_text,
    range=None,
    match_case=None,
    match_entire_cell=None,
    use_regexp=None,
    include_hidden=None,
):
    """全局查找替换，返回被替换的单元格数量。replace_text 可为空字符串（删除匹配）。"""
    args = {
        "nodeId": node_id,
        "sheetId": sheet_id,
        "text": text,
        "replaceText": replace_text,
    }
    if range is not None:
        args["range"] = range
    if match_case is not None:
        args["matchCase"] = match_case
    if match_entire_cell is not None:
        args["matchEntireCell"] = match_entire_cell
    if use_regexp is not None:
        args["useRegExp"] = use_regexp
    if include_hidden is not None:
        args["includeHidden"] = include_hidden
    return try_servers(_TYPE, "replace_all", args)


def merge_cells(node_id, sheet_id, range_address, merge_type="mergeAll"):
    """合并单元格。merge_type ∈ mergeAll / mergeRows / mergeColumns。"""
    return try_servers(
        _TYPE,
        "merge_cells",
        {
            "nodeId": node_id,
            "sheetId": sheet_id,
            "rangeAddress": range_address,
            "mergeType": merge_type,
        },
    )


def unmerge_range(node_id, sheet_id, range_address):
    """取消指定范围内的所有合并。"""
    return try_servers(
        _TYPE,
        "unmerge_range",
        {"nodeId": node_id, "sheetId": sheet_id, "rangeAddress": range_address},
    )


# ============================================================
# 行 / 列（维度）操作
# ============================================================


def add_dimension(node_id, sheet_id, dimension, length):
    """在工作表末尾追加若干空行 / 空列。dimension ∈ "ROWS" / "COLUMNS"。"""
    return try_servers(
        _TYPE,
        "add_dimension",
        {
            "nodeId": node_id,
            "sheetId": sheet_id,
            "dimension": dimension,
            "length": length,
        },
    )


def insert_dimension(node_id, sheet_id, dimension, position, length):
    """在指定位置之前插入若干行 / 列。

    position 用 A1 表示法：
        dimension="ROWS"    → "3" 表示第 3 行之前
        dimension="COLUMNS" → "A" / "AB" 表示该列之前
    """
    return try_servers(
        _TYPE,
        "insert_dimension",
        {
            "nodeId": node_id,
            "sheetId": sheet_id,
            "dimension": dimension,
            "position": position,
            "length": length,
        },
    )


def delete_dimension(node_id, sheet_id, dimension, position, length):
    """从指定位置起删除若干连续的行 / 列。position 规则同 insert_dimension。"""
    return try_servers(
        _TYPE,
        "delete_dimension",
        {
            "nodeId": node_id,
            "sheetId": sheet_id,
            "dimension": dimension,
            "position": position,
            "length": length,
        },
    )


def move_dimension(node_id, sheet_id, dimension, start_index, end_index, destination_index):
    """移动一段行 / 列到目标位置。三个 index 均为 0-based。

    destination_index 不能落在 [start_index, end_index]。
    向下/向右移动：destination_index > end_index
    向上/向左移动：destination_index < start_index
    """
    return try_servers(
        _TYPE,
        "move_dimension",
        {
            "nodeId": node_id,
            "sheetId": sheet_id,
            "dimension": dimension,
            "startIndex": start_index,
            "endIndex": end_index,
            "destinationIndex": destination_index,
        },
    )


def update_dimension(
    node_id, sheet_id, dimension, start_index, length, hidden=None, pixel_size=None
):
    """更新连续行 / 列的属性：行高/列宽 (pixel_size) 与 显隐 (hidden)。

    start_index 同 insert_dimension 的 position（A1 表示法字符串）。
    hidden / pixel_size 至少传一个；length 最大 5000。
    """
    args = {
        "nodeId": node_id,
        "sheetId": sheet_id,
        "dimension": dimension,
        "startIndex": start_index,
        "length": length,
    }
    if hidden is not None:
        args["hidden"] = hidden
    if pixel_size is not None:
        args["pixelSize"] = pixel_size
    return try_servers(_TYPE, "update_dimension", args)


# ============================================================
# 全局筛选（每个工作表至多一个）
# ============================================================


def get_filter(node_id, sheet_id):
    """获取当前工作表的筛选范围和各列筛选条件。"""
    return try_servers(_TYPE, "get_filter", {"nodeId": node_id, "sheetId": sheet_id})


def create_filter(node_id, sheet_id, range, criteria=None):
    """在工作表上创建筛选（已存在筛选会报错）。

    criteria 可选，结构示例：
        [{"column": 0, "filterType": "values", "visibleValues": ["A", "B"]},
         {"column": 2, "filterType": "condition",
          "condition": {"operator": "greaterThan", "value": 100}}]
    """
    args = {"nodeId": node_id, "sheetId": sheet_id, "range": range}
    if criteria is not None:
        args["criteria"] = criteria
    return try_servers(_TYPE, "create_filter", args)


def update_filter(node_id, sheet_id, criteria):
    """批量替换多列的筛选条件。未指定的列保持不变。"""
    return try_servers(
        _TYPE,
        "update_filter",
        {"nodeId": node_id, "sheetId": sheet_id, "criteria": criteria},
    )


def delete_filter(node_id, sheet_id):
    """删除整个筛选，所有被隐藏的行会重新显示。"""
    return try_servers(_TYPE, "delete_filter", {"nodeId": node_id, "sheetId": sheet_id})


def set_filter_criteria(node_id, sheet_id, column, filter_criteria):
    """设置单列的筛选条件。column 是相对筛选范围起始列的 0-based 偏移。

    filter_criteria 示例：
        {"filterType": "values", "visibleValues": ["A", "B"]}
        {"filterType": "condition", "condition": {"operator": "greaterThan", "value": 100}}
    """
    return try_servers(
        _TYPE,
        "set_filter_criteria",
        {
            "nodeId": node_id,
            "sheetId": sheet_id,
            "column": column,
            "filterCriteria": filter_criteria,
        },
    )


def clear_filter_criteria(node_id, sheet_id, column):
    """清除单列的筛选条件（保留整个筛选）。"""
    return try_servers(
        _TYPE,
        "clear_filter_criteria",
        {"nodeId": node_id, "sheetId": sheet_id, "column": column},
    )


def sort_filter(node_id, sheet_id, field):
    """按指定列对筛选范围内的数据排序（物理改变行顺序）。

    field 示例：{"column": 0, "ascending": True}
    """
    return try_servers(
        _TYPE,
        "sort_filter",
        {"nodeId": node_id, "sheetId": sheet_id, "field": field},
    )


# ============================================================
# 下拉列表
# ============================================================


def set_dropdown_lists(node_id, sheet_id, range, options, enable_multi_select=False):
    """在范围内设置下拉列表。

    options 每项: {"value": "选项名", "color": "#RRGGBB"}  # color 可选
    options 至少 1 项；value 不能含英文逗号。
    """
    return try_servers(
        _TYPE,
        "set_dropdown_lists",
        {
            "nodeId": node_id,
            "sheetId": sheet_id,
            "range": range,
            "options": options,
            "enableMultiSelect": enable_multi_select,
        },
    )


def get_dropdown_lists(node_id, sheet_id, range):
    """查询范围内的下拉列表配置。"""
    return try_servers(
        _TYPE,
        "get_dropdown_lists",
        {"nodeId": node_id, "sheetId": sheet_id, "range": range},
    )


def delete_dropdown_lists(node_id, sheet_id, range):
    """删除范围内的下拉列表配置。"""
    return try_servers(
        _TYPE,
        "delete_dropdown_lists",
        {"nodeId": node_id, "sheetId": sheet_id, "range": range},
    )
