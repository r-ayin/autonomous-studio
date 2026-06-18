# API 调用示例

## 目录

- [BFFClient 常见场景](#bffclient-常见场景)（8 个）
- [多步骤工作流](#多步骤工作流)（7 个）
- [底层 API 调用参考](#底层-api-调用参考)（不使用 BFFClient 的原始调用方式）

---

## BFFClient 常见场景

### 1. 搜索表并查看分区

```python
from bff_client import BFFClient
client = BFFClient()

tables = client.load("searchTables", keyword="表名关键字", entityType="maxcompute-table")  # → 表列表
# qualifiedName 转 id：type.a.b → type:::a::b
qn = tables[0]["qualifiedName"]
table_id = qn.split('.')[0] + ':::' + '::'.join(qn.split('.')[1:])

partitions = client.load("ListPartitions", tableId=table_id)  # → 分区列表
for p in partitions:
    print(p["name"])
```

### 2. 查表血缘

```python
from bff_client import BFFClient
client = BFFClient()

tables = client.load("searchTables", keyword="表名", entityType="maxcompute-table")
qn = tables[0]["qualifiedName"]
table_id = qn.split('.')[0] + ':::' + '::'.join(qn.split('.')[1:])

# direction: "UP"=上游, "DOWN"=下游
# ListLineages 的 return_structure 是 data.list[].entity，自动提取每个 entity
entities = client.load("ListLineages", entityId=table_id, direction="UP")  # → [entity, entity, ...]
for entity in entities:
    print(f"{entity['name']} ({entity['entityType']})")
```

### 3. 查看表的加工SQL（从表名出发）

> 典型场景：用户问「表的加工逻辑」「表的SQL」「表怎么产出的」
> 路径：searchTables → searchBatchEntities → 过滤 deployStatus=2 → getContentByNodeId

```python
from bff_client import BFFClient
client = BFFClient()

# 步骤1：搜索表，获取 projectId（通过 getDetail）
tables = client.load("searchTables", keyword="m_task_sql", entityType="maxcompute-table")
table = tables[0]
detail = client.load("getDetail", entityType="odps-table", entityGuid=table["entityGuid"])
project_id = detail["projectId"]
print(f"表: {table['name']}，项目ID: {project_id}")

# 步骤2：在该项目中搜索相关节点
nodes = client.load("searchBatchEntities", keyword=table["name"],
                    projectId=int(project_id), pageSize=50, pageNum=1,
                    scene="DATAWORKS_PROJECT")

# 步骤3：过滤已发布的节点（deployStatus=2 表示在线）
online_nodes = [n for n in nodes if str(n.get("deployStatus")) == "2"]
print(f"在线节点 {len(online_nodes)} 个:")
for n in online_nodes:
    print(f"  {n['name']} (entityId={n['entityId']})")

# 步骤4：获取每个在线节点的代码
for n in online_nodes:
    result = client.load("getContentByNodeId", projectId=str(project_id),
                        nodeId=n["entityId"])
    # 返回值可能是字符串或 {"content": "...", "path": "..."}
    code = result.get("content", result) if isinstance(result, dict) else result
    print(f"\n--- {n['name']} ---")
    print(code[:500] if code else "无代码")
```

### 4. 查任务实例和日志

```python
from bff_client import BFFClient
client = BFFClient()

# 获取 baseId
base_id = client.get_my_base_id()  # → "12345"

# 查实例列表
instances = client.load("listTaskInstances", projectId="23304", owner=base_id,
                        pageSize="50", pageStart="0")  # → 实例列表
for inst in instances:
    print(f"{inst['taskId']} - {inst['status']}")

# 查日志（taskInstanceId 来自 listTaskInstances 返回的 taskId）
log = client.load("get_task_instance_log", taskInstanceId=str(instances[0]["taskId"]))  # → 日志字符串
print(log)
```

### 5. 获取项目列表

```python
from bff_client import BFFClient
client = BFFClient()

projects = client.load("ListProjects", pageSize="100", pageNumber="1")  # → 项目列表
for p in projects:
    print(f"{p['projectId']} - {p['projectName']}")
```

### 6. 查询数据后做维度统计（DuckDB 分析）

> 每次 `load()` 的返回数据自动灌入 DuckDB，可随时用 SQL 分析。
> 表名从 stdout 获取（如 `searchTables_r1_c1`）。列表 API 会自动输出一行汇总和停产告警。
> auto_summary 只输出汇总，需要查看具体维度分布或明细数据时，用 `client.query()` 查询 DuckDB。

```python
from bff_client import BFFClient

client = BFFClient()

# load() 自动全量翻页 + DuckDB 存储 + 统计摘要
# stdout 输出表名如 [searchTables_r1_c1]、[listTaskInstances_r1_c3]
tables = client.load("searchTables", keyword="m_task_sql", entityType="maxcompute-table")
qn = tables[0]["qualifiedName"]
table_id = qn.split('.')[0] + ':::' + '::'.join(qn.split('.')[1:])
partitions = client.load("ListPartitions", tableId=table_id)
instances = client.load("listTaskInstances", projectId="23304")

# 脚本内用 SQL 分析（返回 list[dict]）
rows = client.query("SELECT name, qualifiedName FROM searchTables_r1_c1 LIMIT 5")
stats = client.query("SELECT status, COUNT(*) as cnt FROM listTaskInstances_r1_c3 GROUP BY status")
```

### 7. 查询数据集成数据源下的表列表

> 典型场景：用户在配置离线同步任务时，需要查看某个数据源下有哪些可选表。
> 这类查询必须统一使用 `getTableListPost`，不要改用 `SHOW TABLES`、`ListTables` 或其他元数据接口。

```bash
python <skill-path>/scripts/list_di_tables.py \
  --project-id 22153 \
  --datasource-name yunshi_mysql_pre_di_ide
```

```python
from bff_client import BFFClient
client = BFFClient()

groups = client.load(
    "listDataIntegrationResourceGroups",
    projectId=22153,
    # 必填：限定只查询数据集成模块可用资源组；当前固定传该值
    modules=["DATA_INTEGRATION"],
    # 必填：限定资源组类型范围，可选值仅支持以下三种
    resourceGroupTypes=[
        "PUBLIC_DATA_INTEGRATION",   # 弹内公共资源组
        "COMMON_V2",                 # 弹外通用型资源组
        "EXCLUSIVE_DATA_INTEGRATION",# 独享数据集成资源组
    ],
)
default_group = next((g for g in groups if g.get("isDefault")), groups[0])

datasources = client.load("ListDataSources", projectId=22153)
ds = next(x for x in datasources if x["name"] == "yunshi_mysql_pre_di_ide")
step_type = ds["type"]

tables = client.load(
    "getTableListPost",
    projectId=22153,
    datasourceName="yunshi_mysql_pre_di_ide",
    resourceGroup=default_group["resourceGroupIdentifier"],
    envType=1,
    pageNum=1,
    pageSize=1000,
    table=None,
    tenantId=1,
    stepType=step_type,
    datasourceType=step_type,
    subType="public",
    schemaName="",
)

for t in tables:
    print(t["tableName"])
```

### 8. 在数据源上执行 SQL 查询

> 典型场景：用户说「在 Holo 上跑个 SQL」「查一下这个表的数据」「执行这个查询」
> SELECT/SHOW/DESCRIBE/EXPLAIN/WITH 等只读语句直接执行；写语句需两阶段确认。

```bash
# 只读 SQL（SELECT/SHOW/DESCRIBE/EXPLAIN/WITH）→ 直接执行，返回结果
python <skill-path>/scripts/execute_sql.py "SELECT * FROM public.users LIMIT 10" \
  --datasource-code ds0dd0a20c06e20a7355ca4bf0a0c5f5f2

# 写 SQL（INSERT/UPDATE/DELETE/DROP/CREATE/ALTER）→ 两阶段确认
python <skill-path>/scripts/execute_sql.py "INSERT INTO t VALUES (1)" \
  --datasource-code ds0dd0a20c06e20a7355ca4bf0a0c5f5f2
# → 输出确认摘要，用户确认后：
python <skill-path>/scripts/execute_sql.py --confirm
```

> 不知道 datasource-code？先运行 `python <skill-path>/scripts/list_datasource.py --project-id <id>` 发现可用数据源。
> ⚠️ createExecutorJob4Ida / createQueryJob 已标记为写操作，不能通过 client.load() 直接调用。必须走 execute_sql.py。

---

## 多步骤工作流

### 示例1：查用户在各工作空间的角色

> 典型场景：currentUser → ListProjects → ListProjectMembers
> 关键映射：currentUser.baseId == ListProjectMembers[].userId

```python
from bff_client import BFFClient
client = BFFClient()

# 步骤1：获取当前用户 baseId
base_id = client.get_my_base_id()  # → "12345"

# 步骤2：获取所有工作空间
projects = client.load("ListProjects", pageSize="100", pageNumber="1")

# 步骤3：遍历每个工作空间，查找当前用户的角色
for project in projects:
    pid = project["projectId"]
    pname = project["projectName"]

    members = client.load("ListProjectMembers", projectId=str(pid), pageSize="200", pageNumber="1")

    # 关键：用 baseId 匹配 members 中的 userId
    my_roles = [m for m in members if str(m.get("userId")) == str(base_id)]
    if my_roles:
        roles = my_roles[0].get("roles", [])
        role_names = [r["name"] for r in roles]
        print(f"工作空间 {pname}({pid}): {', '.join(role_names)}")
    else:
        print(f"工作空间 {pname}({pid}): 非成员")
```

### 示例2：搜表查血缘再查上游节点代码

> 典型场景：searchTables → ListLineages → searchBatchEntities → getContentByNodeId
> 关键映射：searchTables → getDetail[].metaEntityId → ListLineages.entityId，searchBatchEntities[].entityId → getContentByNodeId.nodeId

```python
from bff_client import BFFClient
client = BFFClient()

# 步骤1：搜索目标表，获取完整信息
tables = client.load("searchTables", keyword="dwd_order_di", entityType="maxcompute-table")
table = tables[0]
detail = client.load("getDetail", entityType="odps-table", entityGuid=table["entityGuid"])
table_id = detail["metaEntityId"]  # 冒号格式，可直接用于下游 API
print(f"表: {table['name']}（ID: {table_id}）")

# 步骤2：查上游血缘（entityId = metaEntityId）
entities = client.load("ListLineages", entityId=table_id, direction="UP")
print(f"上游实体数: {len(entities)}")

# 步骤3：查上游节点代码
project_id = detail["projectId"]
for entity in entities:
    if entity.get("entityType") == "maxcompute-table":
        continue  # 跳过表实体，只看节点

    # 搜索节点详情
    nodes = client.load("searchBatchEntities", keyword=entity["name"],
                        projectId=int(project_id), pageSize=10, pageNum=1,
                        scene="DATAWORKS_PROJECT")
    if nodes:
        node_id = nodes[0]["entityId"]
        # 获取代码（nodeId = searchBatchEntities 返回的 entityId）
        result = client.load("getContentByNodeId", projectId=str(project_id),
                            nodeId=node_id)
        code = result.get("content", result) if isinstance(result, dict) else result
        print(f"\n--- 节点 {entity['name']} 的代码 ---")
        print(code[:500] if code else "无代码")
```

### 示例3：创建节点

> 典型场景：用户说「创建一个SQL节点」「创建测试节点」
> API：createNodeSimple（⚠️写操作，需确认）
> 必需参数：projectId、scene、command、name
> 可选参数：content（节点代码）

```bash
# 创建 ODPS SQL 节点（最常见）
python <skill-path>/scripts/write_api.py createNodeSimple projectId=14255 scene=DATAWORKS_PROJECT command=ODPS_SQL name=test_node_example content="select 1;"
# → 用户确认后: python <skill-path>/scripts/write_api.py --confirm

# 创建 Shell 节点
python <skill-path>/scripts/write_api.py createNodeSimple projectId=14255 scene=DATAWORKS_PROJECT command=DIDE_SHELL name=test_shell_node content="echo 'hello world'"

# 创建 Python 节点
python <skill-path>/scripts/write_api.py createNodeSimple projectId=14255 scene=DATAWORKS_PROJECT command=PYTHON name=test_python_node content="print('hello')"

# command 常用值：
# ODPS_SQL     - MaxCompute SQL
# DIDE_SHELL   - Shell 脚本
# PYTHON       - Python 2
# PYODPS3      - PyODPS 3
# HOLOGRES_SQL - Hologres SQL
# DI           - 数据集成节点
```

### 示例4：更新节点（修改代码、调度等）

> 典型场景：用户说「修改节点代码」「改调度时间」「更新节点」
> API：UpdateNode（⚠️写操作，需确认）
> 必需参数：projectId + uuid + spec（JSON 字符串，只填要改的字段）
> 前置：需要先通过 GetNode 或 searchBatchEntities 获取节点 uuid

```bash
# 前置：获取节点 uuid（通过搜索或 GetNode）
# nodes = client.load("searchBatchEntities", keyword="test_node", projectId=14255, ...)
# node_uuid = nodes[0]["entityId"]

# 示例1：修改节点代码
python <skill-path>/scripts/write_api.py UpdateNode projectId=14255 uuid=<node_uuid> spec='{"version":"1.1.0","kind":"Node","spec":{"nodes":[{"id":"<node_uuid>","script":{"content":"select 2;","runtime":{"command":"ODPS_SQL"}}}]}}'
# → 用户确认后: python <skill-path>/scripts/write_api.py --confirm

# 示例2：修改调度时间（每天 8:00 执行）
python <skill-path>/scripts/write_api.py UpdateNode projectId=14255 uuid=<node_uuid> spec='{"version":"1.1.0","kind":"Node","spec":{"nodes":[{"id":"<node_uuid>","trigger":{"type":"Scheduler","cron":"00 08 00 * * ?"}}]}}'

# 示例3：修改重跑策略
python <skill-path>/scripts/write_api.py UpdateNode projectId=14255 uuid=<node_uuid> spec='{"version":"1.1.0","kind":"Node","spec":{"nodes":[{"id":"<node_uuid>","rerunMode":"Allowed","rerunTimes":3,"rerunInterval":180000}]}}'
```

### 示例5：冒烟测试（验证节点代码）

> 典型场景：用户说「冒烟测试」「试跑」「验证节点」
> 工具：smoke_test.py（⚠️写操作，需确认）
> 前置：需要通过 GetNode 获取节点的 taskId（运行时 ID）
> 流程：提交 → 异步等待 → check_backlogs 查询结果 → 失败时查日志

```bash
# 前置：获取节点 taskId
# node = client.load("GetNode", uuid=<entityId>)
# task_id = node["taskId"]  # 运行时 ID，不是 entityId

# Step 1：准备冒烟测试
python <skill-path>/scripts/smoke_test.py --project-id 23304 --task-id 307889927
# → 输出确认摘要

# Step 2：用户确认后执行
python <skill-path>/scripts/smoke_test.py --confirm
# → 提交冒烟测试，返回 dagId，自动加入异步任务列表

# Step 3：查看运行结果
python <skill-path>/scripts/check_backlogs.py
# → 失败时输出: taskId=xxx → 查看失败日志命令
# → 成功时输出: 冒烟测试通过，可继续发布到生产环境
```

```python
# 失败后查日志（check_backlogs 输出的命令）
from bff_client import BFFClient
client = BFFClient(quiet=True)
log = client.load('getInstanceRunLog', projectId=23304, env='dev', tenantId=1,
                  taskId=92906625912, historyId=0)
# 日志末尾包含错误信息，如:
# FAILED: ODPS-0130071: Invalid partition value: '20260326'
```

### 示例6：提交发布节点

> 典型场景：用户说「发布节点」「上线节点」「提交发布」
> 工具：deploy_node.py（⚠️写操作，需确认）
> 前置：需要先通过 searchBatchEntities 获取节点 uuid
> 流程：先发布到开发环境，用户确认后再发布到生产环境

```bash
# Step 1：准备发布（输出确认摘要）
python <skill-path>/scripts/deploy_node.py --project-id 14255 --uuid <节点uuid>

# Step 2：用户确认 → 发布到开发环境（BUILD_PACKAGE → DEV_CHECK → DEV）
python <skill-path>/scripts/deploy_node.py --confirm

# Step 3：开发环境验证通过 → 发布到生产环境（PROD_CHECK → PROD）
python <skill-path>/scripts/deploy_node.py --confirm-prod

# 批量发布多个节点
python <skill-path>/scripts/deploy_node.py --project-id 14255 --uuid uuid1 uuid2 uuid3

# 下线节点
python <skill-path>/scripts/deploy_node.py --project-id 14255 --uuid <节点uuid> --type Offline

# 查询已有发布流程状态
python <skill-path>/scripts/deploy_node.py --project-id 14255 --pipeline-uuid <发布流程uuid>
```
---

## 底层 API 调用参考

> 以下是不使用 BFFClient 的原始调用方式，仅供理解底层协议。正常使用请用 BFFClient。

### 通用函数

```python
import requests
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.dataworks/.env"))
BFF_TOKEN = os.getenv("BFF_TOKEN")
BFF_ENDPOINT = os.getenv("BFF_ENDPOINT", "https://dw.alibaba-inc.com")

# Referer 规则：DW_BFF_SESSION_CODE 统一作为会话 ID（未设置时 skill 运行时自动生成 uuid）
SESSION_CODE = os.getenv("DW_BFF_SESSION_CODE") or "default"
REFERER = f"http://{SESSION_CODE}.qwen.cli"

# 日志配置
LOG_DIR = os.path.join(os.getcwd(), "logs")
LOG_FILE = os.path.join(LOG_DIR, "dw_bff_calls.log")

def log_api_call(path, method, params, data, json_body, response, cost_ms):
    """记录 API 调用日志到 logs/dw_bff_calls.log"""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "cost_ms": round(cost_ms, 2),
        "request": {
            "path": path,
            "method": method,
            "params": params,
            "data": data,
            "json_body": json_body
        },
        "response": {
            "code": response.get("code"),
            "data": response.get("data"),
            "message": response.get("message"),
            "requestId": response.get("requestId")
        }
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

def call_bff_api(path, method="GET", params=None, data=None, json_body=None, content_type=None):
    url = f"{BFF_ENDPOINT}{path}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {BFF_TOKEN}",
        "Referer": REFERER  # 必须添加
    }
    if content_type:
        headers["Content-Type"] = content_type

    start_time = time.time()
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, headers=headers, timeout=30)
        elif method.upper() == "POST":
            if json_body:
                response = requests.post(url, json=json_body, headers=headers, timeout=30)
            elif data:
                response = requests.post(url, data=data, headers=headers, timeout=30)
            else:
                response = requests.post(url, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
    except Exception as e:
        result = {"code": -1, "message": str(e), "data": None, "requestId": None}

    cost_ms = (time.time() - start_time) * 1000
    log_api_call(path, method, params, data, json_body, result, cost_ms)
    return result
```

**成功码判断**：
- `code` 为 `0` 或 `200` 都表示成功（不同 API 不统一）
- 判断失败：`if result.get("code") not in [0, 200]:`

### 搜索表

```python
result = call_bff_api(
    "/dma/searchTables",
    method="GET",
    params={"keyword": "表名", "entityType": "maxcompute-table"}
)
# 返回：result["data"]["data"][0]["qualifiedName"] = "maxcompute-table.项目.表"
# qualifiedName 转 id：type.a.b → type:::a::b
```

### 查分区列表

```python
result = call_bff_api(
    "/dataworks_public_v2024-05-18/listPartitions",
    method="POST",
    data={
        "tableId": "maxcompute-table:::项目::表",
        "pageSize": "100",
        "sortBy": "CreateTime",
        "order": "Desc"
    },
    content_type="application/x-www-form-urlencoded"
)
# 返回：result["data"]["list"]
```

### 查血缘关系

```python
# 上游来源
result = call_bff_api(
    "/dma/openapi_listLineages_for_mcp",
    method="POST",
    data={"entityId": table_id, "direction": "UP"},
    content_type="application/x-www-form-urlencoded"
)
# 下游去向：direction="DOWN"
# 返回：result["data"]["list"][i]["entity"]["name"]
```

### 搜索节点

```python
result = call_bff_api(
    "/ide/searchBatchEntities",
    method="POST",
    json_body={
        "keyword": "节点名",
        "pageSize": 50,
        "pageNum": 1,
        "projectId": 23304,
        "scene": "DATAWORKS_PROJECT"
    }
)
# 返回：result["data"]["data"]
# deployStatus: 0=未发布, 2=已发布
```

### 查任务实例列表

```python
result = call_bff_api(
    "/dgc/listTaskInstances",
    method="GET",
    params={
        "projectId": "23304",
        "owner": "用户baseId",
        "taskTypes": "0",    # 0=周期实例, 1=手动实例
        "dagType": "0",      # 0=周期实例
        "pageSize": "50",
        "pageStart": "0"
    }
)
# 返回：result["data"]["data"] (双层嵌套)
# status: 5=失败, 6=成功
```

### 查实例日志

```python
result = call_bff_api(
    "/dgc/getTaskInstanceLog",
    params={"taskInstanceId": "92555747359"}  # 参数名是 taskInstanceId（不是 taskId）
)

# ⚠️ 注意：data 直接是字符串，不是对象！
log_content = result["data"]  # 字符串，不是 result["data"]["logContent"]
lines = log_content.split("\n")
```

### 查工作空间列表

```python
result = call_bff_api(
    "/dataworks_public_v2024-05-18/listProjects",
    method="POST",
    data={"pageSize": "100", "pageNumber": "1"},
    content_type="application/x-www-form-urlencoded"
)
# 返回：result["data"]["data"] (注意是 data.data)
```

### 查当前用户

```python
result = call_bff_api("/v1/currentUser")
# 返回：result["data"]["baseId"], result["data"]["displayName"]
```

### 重跑实例

```python
result = call_bff_api(
    "/workbench/rerunInstance",
    method="POST",
    json_body={
        "env": "prod",           # prod=生产, dev=开发
        "projectId": 23304,
        "taskIds": [92550586011], # 数组格式！
        "refreshProps": False
    }
)
# 返回：result["data"] = True 表示成功
```

### 终止实例

```python
result = call_bff_api(
    "/workbench/stopInstance",
    method="POST",
    json_body={
        "env": "prod",
        "projectId": 23304,
        "taskIds": [92550586011]
    }
)
```
