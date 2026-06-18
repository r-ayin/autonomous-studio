# 调用模式

## 取数（两步：load → SQL）

> 所有 python 命令通过 `PYTHONPATH=<skill-path>/core` 引入依赖，直接 import 即可。
> **⚠️ 不要 `print(client.load(...))`** — 返回值是完整 list/dict，直接打印会导致输出截断。

**Step 1**：`load()` 取数入库，stdout 输出表名和列名。

```bash
PYTHONPATH=<skill-path>/core python -c "
from bff_client import BFFClient
client = BFFClient()
client.load('searchTables', keyword='m_task_sql', entityType='maxcompute-table')
"
# stdout: [searchTables_r1_c1] 30 条 | keyword=m_task_sql | qualifiedName, name, databaseName, ...
```

**Step 2**：根据 stdout 列名写 SQL 查询。

```bash
PYTHONPATH=<skill-path>/core python <skill-path>/core/duckdb_query.py "SELECT qualifiedName, name, databaseName FROM searchTables_r1_c1 WHERE name = 'm_task_sql'"
```

## 写操作（两阶段确认）

写操作统一通过 `write_api.py` 两阶段执行：

```bash
# Phase 1：准备 → stdout 输出确认摘要
PYTHONPATH=<skill-path>/core python <skill-path>/core/write_api.py rerun_task_instances env=prod projectId=23304 taskIds='[123]'
# stdout: ⚠️ 待确认写操作: rerun_task_instances
#   参数: env='prod', projectId=23304, taskIds=[123]
#   → 用户确认后执行: python write_api.py --confirm
```

```bash
# Phase 2：用户确认后执行
PYTHONPATH=<skill-path>/core python <skill-path>/core/write_api.py --confirm
# 异步写操作（重跑、终止、启停同步等）stdout 会输出下一步指令：
# ✅ 执行写操作: rerun_task_instances
# ⏳ 异步操作已提交，执行下一步确认结果: client.load('get_task_instance', taskInstanceId=123)
#   终态: 6=成功, 5=失败 | 中间态: 4=运行中, 0=未运行
# 按 stdout 指令执行查询，返回值自动翻译状态码并提示是否需要继续轮询。
```

## 链式调用：直接用 load() 返回值

`load()` 返回值就是业务数据（list 或 dict），在同一脚本内直接使用，不需要绕道 DuckDB。

```python
# load() 返回值驱动循环 — 这是链式调用的标准模式
my_id = client.get_my_base_id()                  # → baseId，等同于 ListProjectMembers 的 userId
projects = client.load("ListProjects")            # → list[dict]
for p in projects:
    members = client.load("ListProjectMembers", projectId=p["projectId"])  # → list[dict]
    my_roles = [m for m in members if m["userId"] == my_id]
    # stdout 会输出列名含嵌套结构提示（如 roles[].{code, name}），按提示访问字段
```

## DuckDB 查询：用于聚合分析

`load()` 同时将数据写入 DuckDB，适合 SQL 聚合、JOIN、过滤等分析场景。表名和列名从 stdout 获取。

```bash
# 交互式分析（输出到 stdout）
PYTHONPATH=<skill-path>/core python <skill-path>/core/duckdb_query.py "SELECT type, COUNT(*) FROM ListDataSources_r1_c1 GROUP BY type"

# 查看所有表和视图
PYTHONPATH=<skill-path>/core python <skill-path>/core/duckdb_query.py --tables

# 同一 API 多次 load() 后，stdout 会提示合并命令，按提示执行即可
# python duckdb_query.py --merge "ListProjectMembers_r*" --as all_members
```

```python
# 脚本内 SQL 查询（返回 list[dict]）
rows = client.query("SELECT type, COUNT(*) as cnt FROM ListDataSources_r1_c1 GROUP BY type")
```

> **数据已在 DuckDB 中**：load() 的数据自动入库，修正逻辑后优先用 `duckdb_query.py` SQL 查询已有表，不要重新 load 同一批数据。
> **SQL 字符串用单引号**：DuckDB SQL 中字符串值用单引号 `'Available'`，双引号是标识符引用（列名/表名）。在 `python -c` 中用转义单引号 `\'Available\'` 或三引号包裹。
> **分区展开视图**：`ds=20240101/region=cn-hangzhou` 格式的分区会自动创建 `_{表名}_name_expanded` 视图，含 `ds`、`region` 等展开列。
> **跨脚本共享**：所有脚本的 load() 写同一个 .duckdb 文件，表名全局唯一不冲突。
> 限频自动重试。写操作误用 `load()` 自动抛 `TypeError`。
> 跨 API 字段映射：链式调用前查 `<skill-path>/core/references/field-mapping.md`。
