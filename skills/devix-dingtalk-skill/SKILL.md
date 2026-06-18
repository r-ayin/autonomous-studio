---
name: devix-dingtalk-skill
version: 0.2.0
description: 钉钉文档/电子表格/AI表格 三合一读写技能（优先级最高）。当用户消息中包含钉钉文档/表格链接（alidocs.dingtalk.com、docs.dingtalk.com）时，必须优先使用此技能读取内容，禁止使用浏览器打开链接。当用户需要创建、更新、追加或搜索钉钉文档/电子表格/AI 表格时，也使用此技能。
metadata:
  author: Devix
  dependencies:
    - requests
x-source: aone-open
repository: https://code.alibaba-inc.com/qunbu/devix-dingtalk-skill
---

# devix-dingtalk-skill

Devix 用于读写钉钉**文档（Doc）**、**表格（Sheet）**、**AI 表格（AI Table）** 的三合一技能。基于钉钉 MCP（Model Context Protocol）网关实现，支持多组织、多 MCP 类型混合配置、自动切换。

## 当前覆盖范围

| 类型 | 子模块 | MCP 入口 | 状态 |
| --- | --- | --- | --- |
| 钉钉文档 Doc | `scripts.dingtalk_doc` | mcpId=9629 | ✅ 已支持 |
| 钉钉电子表格 Sheet | `scripts.dingtalk_sheet` | mcpId=9704 | ✅ 已支持 |
| 钉钉 AI 表格 | `scripts.dingtalk_ai_table` | mcpId=9555 | ✅ 已支持 |

> ⚠️ 三种 MCP 是**三个独立服务**，授权地址各自不同，都在 `mcp.dingtalk.com`，仅 `mcpId` 不同。

## Priority Rules

**当用户消息中包含 `alidocs.dingtalk.com` 或 `docs.dingtalk.com` 链接时，必须遵循以下规则：**

1. **必须使用本技能** 读取内容
2. **禁止使用浏览器打开钉钉链接** —— 浏览器需要登录且无法正确提取内容
3. 只有当本技能明确报错后，才考虑其他方案

判别链接归属（先看 URL 形态，再看用户描述的关键词）：

| 形态 / 关键词 | 归属 | 入口函数 |
| --- | --- | --- |
| `alidocs.dingtalk.com/i/nodes/<id>` + "文档/段落/标题/Markdown" | **文档** | `read_doc(url)` |
| `alidocs.dingtalk.com/i/nodes/<id>` 或 `spreadsheetv2/...` + "单元格/工作表/A1/行列/筛选" | **电子表格** | `get_all_sheets(url)` → `get_range(url, ...)` |
| `docs.dingtalk.com/i/nodes/<id>` 或 "AI 表格/Base/字段/记录" | **AI 表格** | `get_base(url)` → `query_records(...)` |

> 同样是 `alidocs.dingtalk.com/i/nodes/<id>`，文档和电子表格用同一种 URL 形态。优先按用户描述的关键词判断；不确定时可先调 `dingtalk_doc.get_doc_info(url)` 或 `dingtalk_sheet.get_all_sheets(url)`，看哪个能返回成功结果。

## When to Use

- **（最高优先级）用户消息中出现 `alidocs.dingtalk.com` / `docs.dingtalk.com` 链接**
- 用户要求创建 / 更新 / 追加钉钉文档、AI 表格
- 用户要求搜索钉钉文档 / AI 表格
- 用户要求查看知识库 / 文件夹下的列表
- 用户要求"建表"、"查记录"、"加字段"、"按条件筛选 AI 表格"、"刷新 AI 字段"等
- 用户提供了授权地址（MCP URL）并要求配置

## First-Time Setup

**当配置不存在（脚本报错提示未配置）或用户首次使用时，按以下流程引导用户：**

### 第一步：引导用户获取授权地址

向用户发送以下提示（直接发送，不要改写）：

> 三合一技能需要分别获取 **三个 MCP 授权**（文档 / 表格 / AI 表格是三个独立 MCP 服务）。请依次打开下面的链接并复制各自的 MCP 地址：
>
> 1. **钉钉文档 MCP**：https://mcp.dingtalk.com/#/detail?mcpId=9629&detailType=marketMcpDetail
> 2. **钉钉表格 MCP**：https://mcp.dingtalk.com/#/detail?mcpId=9704&detailType=marketMcpDetail
> 3. **钉钉 AI 表格 MCP**：https://mcp.dingtalk.com/#/detail?mcpId=9555&detailType=marketMcpDetail
>
> 每个页面右侧点击「获取 MCP Server 配置」，复制出来的地址（格式类似
> `https://mcp-gw.dingtalk.com/server/xxx?key=xxx`）发给我，我会自动识别类型并完成配置。
>
> 如果你在多个钉钉组织中都有内容，每个组织 × 每种 MCP 都需要分别获取一个地址。

### 第二步：保存用户授权

收到用户提供的地址后，执行（**任一子模块的 `setup` 都通用**，会自动探测 server 类型）：

```python
from scripts.dingtalk_doc import setup, list_servers

result = setup("用户提供的完整地址")
print(result["message"])
# → "已添加 MCP 服务器 [doc-1] (type=doc)..." 或 "[ai_table-1] (type=ai_table)..."

# 多个组织 / 多个 MCP 类型，多次调用即可
setup("第二个地址", name="org-b-doc")
setup("第三个地址", name="org-b-ai")

list_servers()  # 查看（凭证自动脱敏）
```

`setup()` 通过 `tools/list` 自动识别该 MCP 的类型（`doc` / `ai_table`），并保存到技能目录下
`config/servers.json`，无需手动编辑。

## How to Import

```python
import sys
from pathlib import Path

# 【重要】以下路径仅为示例，需要根据实际使用的工具调整：
# - Claude Code: ~/.claude/skills/devix-dingtalk-skill
# - Cursor: ~/.cursor/skills/devix-dingtalk-skill
# - Qoderwork: ~/.qoderwork/skills/devix-dingtalk-skill
SKILL_DIR = Path.home() / ".claude" / "skills" / "devix-dingtalk-skill"
sys.path.insert(0, str(SKILL_DIR))

# 配置管理（任一模块都有，统一入口）
from scripts.dingtalk_doc import setup, list_servers, remove_server

# 钉钉文档
from scripts.dingtalk_doc import (
    read_doc, read_doc_blocks, get_doc_info,
    create_doc, update_doc,
    insert_block, update_block, delete_block,
    search_docs, list_nodes, create_folder,
)

# 钉钉电子表格
from scripts.dingtalk_sheet import (
    create_spreadsheet, export_xlsx, query_export_job,
    get_all_sheets, get_sheet, create_sheet, update_sheet, copy_sheet,
    get_range, update_range, append_rows,
    find_cells, replace_all,
    merge_cells, unmerge_range,
    add_dimension, insert_dimension, delete_dimension, move_dimension, update_dimension,
    get_filter, create_filter, update_filter, delete_filter,
    set_filter_criteria, clear_filter_criteria, sort_filter,
    set_dropdown_lists, get_dropdown_lists, delete_dropdown_lists,
    raw_call as sheet_raw_call,  # 浮动图片/个人筛选视图等低频
)

# 钉钉 AI 表格
from scripts.dingtalk_ai_table import (
    list_bases, search_bases, get_base, create_base, update_base, delete_base,
    copy_base, search_templates,
    get_tables, create_table, update_table, delete_table,
    get_fields, create_fields, update_field, delete_field,
    query_records, create_records, update_records, delete_records,
    get_base_primary_doc_id,
    get_views, create_view, update_view, delete_view,
    run_ai_field,
    prepare_attachment_upload, prepare_import_upload, import_data, export_data,
    create_guide_document, update_guide_document, delete_guide_document,
    raw_call,  # 任意未单独包装的 MCP 工具直通
)
```

## Steps — 钉钉文档（Doc）

### 读取文档

```python
result = read_doc(url="https://alidocs.dingtalk.com/i/nodes/<nodeId>")
markdown_content = result["markdown"]
```

### 读取文档块元素

```python
result = read_doc_blocks(url="https://alidocs.dingtalk.com/i/nodes/<nodeId>")
for block in result["blocks"]:
    print(block["index"], block["blockType"], block["element"].get("id"))
```

### 创建 / 更新文档

```python
create_doc(doc_name="文档标题", content="Markdown 内容")
create_doc(doc_name="标题", content="内容", workspace_id="xxx")
create_doc(doc_name="标题", content="内容", folder_id="xxx")

update_doc(url="https://alidocs.dingtalk.com/i/nodes/<nodeId>", content="新 Markdown 内容")
```

### 块级操作

```python
insert_block(url, {"blockType": "paragraph", "paragraph": {"text": "新段落"}})
insert_block(url, {"blockType": "heading", "heading": {"level": 2, "text": "二级标题"}})
update_block(url, block_id="xxx", element={"blockType": "paragraph", "paragraph": {"text": "更新内容"}})
delete_block(url, block_id="xxx")
```

### 搜索 / 浏览

```python
search_docs(keyword="关键词", count=10)
list_nodes(workspace_id="知识库ID")
list_nodes(folder_id="文件夹ID")
get_doc_info(url="https://alidocs.dingtalk.com/i/nodes/<nodeId>")
create_folder(name="新文件夹", workspace_id="xxx")
```

## Steps — 钉钉 AI 表格（AI Table）

> AI 表格是"Base → Table → Field/Record/View"的结构。
> 几乎所有写操作都需要 `baseId` + `tableId`。先用 `list_bases` / `search_bases` 找 Base，
> 再用 `get_base` 取 Table 列表，再用 `get_tables` 看字段目录，最后做读写。

### 找 Base

```python
list_bases(limit=10)                                # 最近访问的 Base
search_bases(query="销售日报")                       # 按名称搜
get_base(base_id="AR4xxx...")                       # 进入某个 Base
# 返回里有 tables 列表：tableId / tableName / summary
# AI 表格访问 URL：https://docs.dingtalk.com/i/nodes/<baseId>
```

### 建表 / 加字段

```python
# 一次建一张表，并附带初始字段（单次最多 15 个字段）
create_table(
    base_id="<baseId>",
    table_name="销售台账",
    fields=[
        {"fieldName": "客户", "type": "text"},
        {"fieldName": "金额", "type": "currency", "config": {"currencyType": "CNY"}},
        {"fieldName": "阶段", "type": "singleSelect",
         "config": {"options": [{"name": "线索"}, {"name": "成交"}, {"name": "流失"}]}},
        {"fieldName": "负责人", "type": "user", "config": {"multiple": False}},
        {"fieldName": "成交日期", "type": "date"},
    ],
)

# 给已有表加字段
create_fields(base_id, table_id, fields=[
    {"fieldName": "备注", "type": "richText"},
    {"fieldName": "进度", "type": "progress"},
])

# 看字段目录
tables = get_tables(base_id, table_ids=["<tableId>"])
fields = get_fields(base_id, table_id, field_ids=["<fieldId>"])  # 含完整 options 等

update_field(base_id, table_id, field_id, new_field_name="新名字")
delete_field(base_id, table_id, field_id)
```

### 增 / 删 / 查 / 改记录

```python
# 新增
create_records(base_id, table_id, records=[
    {"cells": {
        "fld_客户ID":  "阿里巴巴",
        "fld_金额ID":  120000,
        "fld_阶段ID":  "成交",
        "fld_日期ID":  "2026-05-18",
    }},
    {"cells": {"fld_客户ID": "蚂蚁", "fld_金额ID": 80000, "fld_阶段ID": "线索"}},
])

# 查询：按 ID
query_records(base_id, table_id, record_ids=["rec_xxx", "rec_yyy"])

# 查询：按条件 + 排序 + 分页
result = query_records(
    base_id, table_id,
    field_ids=["fld_客户ID", "fld_金额ID"],          # 限定返回字段，节省 token
    filters={
        "operator": "and",
        "operands": [
            {"fieldId": "fld_阶段ID", "operator": "eq", "value": "成交"},
            {"fieldId": "fld_金额ID", "operator": "gt", "value": 100000},
        ],
    },
    sort=[{"fieldId": "fld_日期ID", "direction": "desc"}],
    limit=100,
)
# 翻页：把 result["cursor"] 传到下一次的 cursor

# 更新（只传需要改的 cells）
update_records(base_id, table_id, records=[
    {"recordId": "rec_xxx", "cells": {"fld_阶段ID": "流失"}},
])

# 删除（最多 100 条）
delete_records(base_id, table_id, record_ids=["rec_xxx"])
```

各字段类型的写入格式（摘要）：

| 类型 | 写入示例 |
| --- | --- |
| `text` / `url` / `email` / `telephone` | `"字符串"` |
| `number` / `currency` | `123` 或 `123.45` |
| `progress` | `0~1`（0.5 = 50%） |
| `rating` | 数字（在 `min~max` 范围内） |
| `checkbox` | `true` / `false` |
| `singleSelect` | `"选项名"` 或 `{"id": "opt_xxx"}` |
| `multipleSelect` | `["选项1", "选项2"]` |
| `date` | `"2026-03-15"` / `"2026-03-15 09:00"` / RFC3339 / 毫秒时间戳 |
| `user` | `[{"userId": "...", "corpId": "..."}]` |
| `department` | `[{"deptId": "..."}]` |
| `group` | `[{"cid": "..."}]`（不是 chatId） |
| `attachment` | 外链 `[{"url": "https://..."}]` 或上传后 `[{"fileToken": "..."}]` |

### 视图（View）

```python
get_views(base_id, table_id)                        # 全部视图
create_view(base_id, table_id, view_type="Kanban",
            view_name="按阶段看板",
            config={"visibleFieldIds": ["fld_主ID", "fld_金额ID", "fld_阶段ID"]})
update_view(base_id, table_id, view_id, config={"sort": [...]})
delete_view(base_id, table_id, view_id)
```

支持的视图类型：`Grid` / `FormDesigner` / `Gantt` / `Calendar` / `Kanban` / `Gallery`。

### AI 字段

```python
# 整列刷新 AI 字段
run_ai_field(base_id, table_id, field_ids=["fld_AI_xxx"])

# 指定记录刷新（最多 500 条）
run_ai_field(base_id, table_id,
             field_ids=["fld_AI_xxx"], record_ids=["rec_a", "rec_b"])
# 异步任务：只返回提交结果，进度需要到文档里看
```

### 模板 / 建 Base

```python
search_templates(query="项目管理")                   # 找模板
create_base(base_name="我的新 Base", template_id="235")
create_base(base_name="空 Base", folder_id="<dentryUuid>")  # 放进知识库指定文件夹
update_base(base_id, new_base_name="改个名")
delete_base(base_id, reason="测试垃圾")
copy_base(base_id, target_folder_id="<dentryUuid>", only_copy_meta=False)
```

### 导入 / 导出 / 附件

```python
# 外链文件写 attachment 字段（不要先下载）
update_records(base_id, table_id, records=[
    {"recordId": "rec_xxx",
     "cells": {"fld_附件ID": [{"url": "https://example.com/report.pdf"}]}},
])

# 本地文件 → 申请上传地址 → PUT 上传 → 写 fileToken
prep = prepare_attachment_upload(base_id, file_name="report.pdf",
                                  size=12345, mime_type="application/pdf")
# 客户端用 requests.put(prep["uploadUrl"], data=..., headers={"Content-Type": "application/pdf"})
update_records(base_id, table_id, records=[
    {"recordId": "rec_xxx",
     "cells": {"fld_附件ID": [{"fileToken": prep["fileToken"]}]}},
])

# 导入 Excel → 自动新建数据表
imp = prepare_import_upload(base_id, file_name="data.xlsx", file_size=98765)
# PUT 上传到 imp["uploadUrl"]
result = import_data(import_id=imp["importId"])      # 等不到再调一次

# 导出整个 Base 为 Excel
export_data(base_id, scope="all", format="excel")
# 单表导出： scope="table", table_id="..."
# 视图导出： scope="view", table_id="...", view_id="..."
```

### 直通入口（未单独包装的工具）

```python
# 仪表盘 / 图表 / 分享 等复杂工具走直通
raw_call("get_dashboard_config_example", {})
raw_call("create_dashboard", {"baseId": "...", "config": {...}})
raw_call("update_dashboard_share", {"baseId": "...", "dashboardId": "...",
                                     "enabled": True, "shareType": "ORG"})
```

完整工具列表见 `_mcp_client.list_mcp_tools(server_index=...)`。

## Steps — 钉钉电子表格（Sheet）

> Spreadsheet 是一个文档（`nodeId` / dentryUuid / URL 三者通用），里面有多个 Worksheet。
> 所有写操作都需 `node_id` + `sheet_id`。`sheet_id` 也可直接传工作表名。

### 找工作表

```python
# 列出某个在线表格的所有工作表
get_all_sheets(node_id="https://alidocs.dingtalk.com/i/nodes/<dentryUuid>")
# 或直接传 32 位 dentryUuid

# 取某个 sheet 的详情（含行列数、最后非空位置）
get_sheet(node_id, sheet_id="Sheet1")           # 名字
get_sheet(node_id, sheet_id="sht_xxx")          # ID
```

### 读单元格 / 范围

```python
# 默认：读第一个工作表的全部非空数据
get_range(node_id)

# 读指定区域
get_range(node_id, sheet_id="Sheet1", range="A1:D10")

# 也可写带前缀的形式，会忽略 sheet_id
get_range(node_id, range="Sheet1!A1:D10")
# 返回三套数据：
#   values        → 公式计算后的值
#   formulas      → 原始公式
#   displayValues → 界面显示值
# 均为二维数组 [行][列]
```

### 写单元格 / 范围

```python
# 只写值（最常用）
update_range(
    node_id, sheet_id="Sheet1", range_address="A1:B2",
    values=[["客户", "金额"], ["阿里", 120000]],
)

# 公式
update_range(node_id, "Sheet1", "C2", values=[["=A2&'-'&B2"]])
update_range(node_id, "Sheet1", "B5", values=[["=SUM(B2:B4)"]])

# 清空（实测：必须用空字符串 ""，不能用 None / null —— MCP 把 null 视作"保留原值"）
update_range(node_id, "Sheet1", "A1:B2", values=[["", ""], ["", ""]])
# 大批量清空可直接 delete_dimension(node_id, sheet_id, "ROWS", position="1", length=N)

# 同时写值 + 格式
update_range(
    node_id, "Sheet1", "A1:B1",
    values=[["客户", "金额"]],
    font_weights=[["bold", "bold"]],
    background_colors=[["#FFF2CC", "#FFF2CC"]],
    horizontal_alignments=[["center", "center"]],
)

# 超链接
update_range(
    node_id, "Sheet1", "A2",
    hyperlinks=[[{"type": "path", "link": "https://example.com", "text": "示例"}]],
)

# 数字格式
update_range(node_id, "Sheet1", "B2:B100",
             number_format="¥#,##0")   # 人民币；其它常用："0%"、"yyyy/m/d"

# 自动换行
update_range(node_id, "Sheet1", "A1:Z1", word_wrap="autoWrap")
```

### 追加行（最常用的写入模式）

```python
# 自动定位到最后非空行下方
append_rows(node_id, sheet_id="Sheet1", values=[
    ["阿里",  120000, "2026-05-18"],
    ["蚂蚁",   80000, "2026-05-19"],
])
# 返回追加范围（A1 表示法）
```

### 查找 / 替换

```python
find_cells(node_id, "Sheet1", text="阿里")
find_cells(node_id, "Sheet1", text="^A.*$", use_regexp=True, range="A1:A100")
find_cells(node_id, "Sheet1", text="ALI", match_case=False, match_entire_cell=True)

replace_all(node_id, "Sheet1", text="阿里", replace_text="阿里巴巴")
replace_all(node_id, "Sheet1", text="\\s+", replace_text="", use_regexp=True)
```

### 行 / 列管理

```python
# 末尾追加 5 行 / 3 列
add_dimension(node_id, "Sheet1", dimension="ROWS",    length=5)
add_dimension(node_id, "Sheet1", dimension="COLUMNS", length=3)

# 在第 3 行之前插入 2 行；在 B 列之前插入 1 列
insert_dimension(node_id, "Sheet1", "ROWS",    position="3", length=2)
insert_dimension(node_id, "Sheet1", "COLUMNS", position="B", length=1)

# 从第 3 行起删 2 行
delete_dimension(node_id, "Sheet1", "ROWS", position="3", length=2)

# 移动行（0-based）：把第 1-2 行（index 0~1）移到第 4 行（index 3）后面
move_dimension(node_id, "Sheet1", "ROWS",
               start_index=0, end_index=1, destination_index=4)

# 隐藏 / 设行高 / 设列宽
update_dimension(node_id, "Sheet1", "ROWS",    start_index="3", length=2, hidden=True)
update_dimension(node_id, "Sheet1", "ROWS",    start_index="1", length=1, pixel_size=40)
update_dimension(node_id, "Sheet1", "COLUMNS", start_index="A", length=3, pixel_size=120)
```

### 合并单元格

```python
merge_cells(node_id, "Sheet1", "A1:D1")                       # 合并所有
merge_cells(node_id, "Sheet1", "A1:D3", merge_type="mergeRows")
unmerge_range(node_id, "Sheet1", "A1:D3")
```

### 全局筛选（每个工作表至多一个）

```python
create_filter(node_id, "Sheet1", range="A1:E100")

# 列 0 只显示 ["阿里","蚂蚁"]
set_filter_criteria(node_id, "Sheet1", column=0,
    filter_criteria={"filterType": "values", "visibleValues": ["阿里", "蚂蚁"]})

# 列 2 金额 > 100000
set_filter_criteria(node_id, "Sheet1", column=2,
    filter_criteria={"filterType": "condition",
                     "condition": {"operator": "greaterThan", "value": 100000}})

sort_filter(node_id, "Sheet1", field={"column": 0, "ascending": True})

clear_filter_criteria(node_id, "Sheet1", column=2)
delete_filter(node_id, "Sheet1")
```

### 下拉列表

```python
set_dropdown_lists(node_id, "Sheet1", range="C2:C100", options=[
    {"value": "线索"},
    {"value": "成交", "color": "#22C55E"},
    {"value": "流失", "color": "#EF4444"},
])
get_dropdown_lists(node_id, "Sheet1", range="C2")
delete_dropdown_lists(node_id, "Sheet1", range="C2:C100")
```

### 工作表管理

```python
create_spreadsheet(name="新表格", folder_id="<dentryUuid>")   # 新建文件
create_sheet(node_id, name="Q2 数据")                          # 表内新增 worksheet
update_sheet(node_id, "Sheet1", title="销售台账", frozen_row_count=1)
copy_sheet(node_id, "Sheet1", title="Sheet1 副本")
```

### 导出 xlsx

```python
job = export_xlsx(node_id)
result = query_export_job(job["jobId"])   # 完成时返回下载链接；未完则继续轮询
```

### 直通入口

浮动图片、个人筛选视图（filter_views）、内嵌单元格图片（write_image）等低频工具走 `sheet_raw_call`：

```python
sheet_raw_call("create_float_image", {
    "nodeId": node_id, "sheetId": "Sheet1",
    "src": "https://...", "range": "A1", "width": 200, "height": 100,
})
sheet_raw_call("list_float_images", {"nodeId": node_id, "sheetId": "Sheet1"})
sheet_raw_call("create_filter_view", {"nodeId": node_id, "sheetId": "Sheet1",
                                       "name": "我的视图", "range": "A1:E100"})
```

## 配置管理

```python
list_servers()                # 已配置的授权（脱敏，含 type/server_id/key）
remove_server("org-name")     # 按名称删除
remove_server(0)              # 按索引删除
```

## Error Handling

- **跨组织限制**：自动尝试下一个同类型授权，无需用户干预
- **同类型授权全失败**：抛出 `DingMCPError`，向用户展示错误信息
- **类型不匹配**：未配置该类型 MCP 时，错误信息会告知"已配置的类型有 [...]，请添加 X 类型"
- **未配置**：按 First-Time Setup 引导用户获取授权地址
- **授权地址格式错误**：`setup()` 返回失败并说明正确格式
- **AI 表格 ID 不存在 / 无权限**：返回业务错误，自动跳到下一个授权

## Notes

- **权限**：需要文档 / AI 表格"可查看 / 下载"或更高权限；写操作需"可编辑"
- 配置文件：`<skill_dir>/config/servers.json`，自动创建，已在 `.gitignore` 中
- 凭证：含每个用户独立的 key，**绝不提交到代码仓库**
- 外部依赖：Python `requests`
- AI 表格的 `baseId` 既支持 32 位纯 ID，也支持 `https://docs.dingtalk.com/i/nodes/<baseId>` 完整链接
- 老版本 `dingtalk-doc-rw` 的配置不会自动迁移；用户需在本技能中重新 `setup()` 一次
