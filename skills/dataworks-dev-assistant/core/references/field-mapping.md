# 跨 API 字段映射与参考手册

## 前置 ID 获取

大部分 API 需要先获取以下 ID：

```python
from bff_client import BFFClient
client = BFFClient()

# 获取当前用户信息
user_info = client.load("currentUser")  # → {"baseId": "12345", "nickName": "张三", ...}
base_id = user_info["baseId"]

# 或使用便捷方法（结果会缓存）
base_id = client.get_my_base_id()  # → "12345"

# 获取项目列表
projects = client.load("ListProjects")
for p in projects:
    print(f"{p['projectId']} - {p['projectName']}")
```

| ID | 获取方式 | 用于 |
|----|---------|------|
| baseId | `client.get_my_base_id()` 或 `client.load("currentUser")["baseId"]` | 匹配 ListProjectMembers 的 userId |
| projectId | ListProjects 返回的 `projectId`，或 getDetail 返回的 `projectId` | 大部分 API |
| tableId | getDetail 返回的 `metaEntityId`（冒号格式），或 searchTables 的 qualifiedName 转 id（type.a.b → type:::a::b） | 查分区（ListPartitions）、查血缘（ListLineages）、查表详情（GetTable，参数名为 id） |
| nodeId | searchBatchEntities 返回的 entityId | 查节点代码（getContentByNodeId） |
| taskId / taskInstanceId | listTaskInstances 返回的 taskId | 查日志（get_task_instance_log 用 taskInstanceId）、重跑、终止 |
| dataSourceId | ListDataSources 返回的 `id` | SQL 执行（createExecutorJob4Ida / execute_sql.py） |

---

## 跨 API 字段映射表

> 不同 API 之间的 ID 字段名不同，下表列出关键映射关系，避免猜错字段名。

| 源 API | 源字段 | 目标 API | 目标参数 | 说明 |
|--------|--------|----------|---------|------|
| `currentUser` | `baseId` | `ListProjectMembers` | `userId`（匹配） | baseId == userId，用于判断当前用户在项目中的角色 |
| `ListProjects` | `projectId` | `ListProjectMembers` | `projectId` | 获取某工作空间的成员列表 |
| `searchTables` | `entityGuid` | `getDetail` | `entityGuid` | 搜表后查完整详情（含 projectId） |
| `getDetail` | `entityGuid` | `getTableUpstreamTasks` | `entityGuid` | 直接从表反查产出任务/节点 |
| `getDetail` | `metaEntityId` | `ListPartitions` | `tableId` | 查分区（metaEntityId 已是冒号格式） |
| `getDetail` | `metaEntityId` | `ListLineages` | `entityId` | 查血缘（metaEntityId 已是冒号格式） |
| `getDetail` | `projectId` | 需要 projectId 的 API | `projectId` | 数字型工作空间ID |
| `getDetail` | `metaEntityId` | `GetTable` | `id` | 直接传给 GetTable 的 id 参数 |
| `searchBatchEntities` | `entityId` | `getContentByNodeId` | `nodeId` | 搜索节点后查代码。nodeId 是数字 ID，不是 DMA 实体 ID |
| `searchBatchEntities` | `entityId` | `GetNode` | `uuid` | 节点 uuid 可传给 GetNode 取 taskId |
| `GetNode` | `taskId` | `getNodeCode` | `nodeId` | 查运行态代码时优先用 taskId；已下线节点通常需要这条链路 |
| `listExtensionEventSnapshot` | `extensionBizId` | `getBizStatus` | `extensionBizId` | 发布检查器 BLOCKED 后，用 extensionBizId 查具体失败检查器 |
| `GetNode` | `uuid` + `spec` | `code_parse` | `currentNodeUuid` + `content` + `scheduleConnection` | 检查器 RCA：取当前节点和代码，再解析代码依赖；解析结果字段以实际返回为准 |
| `GetNode` | `spec` | RCA 对比逻辑 | 调度依赖集合 | 从 spec 中提取节点当前声明的调度上游，用于与 code_parse 结果做差集 |
| `searchBatchEntities` | `entityId` | `deploy_node.py` | `--uuid` | 节点 uuid 传给 deploy_node.py |
| `listTaskInstances` | `taskId` | `get_task_instance_log` | `taskInstanceId` | 查实例后查日志（注意参数名不同！） |
| `ListProjects` | `projectId` | `listSupportedEngine` | `projectId` | SQL 执行链路起点：先选工作空间 |
| `listSupportedEngine` | `code` | `listConnection` | `engineType` | 引擎代码（MAX_COMPUTE、HOLOGRES 等） |
| `listConnection` | `id` | `daCreateDataSource` | `contentMap.connectionId` | 连接ID，用于创建 DA 数据源 |
| `daCreateDataSource` | 返回值（字符串） | `createQueryJob` / `execute_sql.py` | `dataSourceCode` / `--datasource-code` | dataSourceCode（ds...格式） |
| `createExecutorJob4Ida` | `jobCode` | `getExecutorJobLog4Ida` | `jobCode` | 提交 SQL 后查执行日志 |
| `createQueryJob` | `jobCode` | `getExecutorJobLog4Ida` | `jobCode` | 同上（两种提交方式共用轮询/结果 API） |
| `createExecutorJob4Ida` | `jobCode` | `getExecutorJobResult4Ida` | `jobCode` | 提交 SQL 后取执行结果 |

---

## 写操作 API 完整清单

> 所有 `is_write_operation: true` 的 API 都必须经过用户确认才能执行。

**任务实例操作**：
- `rerun_task_instances` - 重跑实例
- `stop_task_instances` - 终止实例
- `set_task_instance_success` - 置成功

**数据源操作**：
- `CreateDataSource` / `UpdateDataSource` / `DeleteDataSource` / `CloneDataSource`

**告警规则操作**：
- `CreateAlertRule` / `UpdateAlertRule` / `DeleteAlertRule`

**节点操作**：
- `createNodeSimple` - 创建节点（参数：projectId + scene + command + name + content）
- `UpdateNode` - 更新节点（参数：projectId + uuid + spec JSON，spec 只填要更新的属性）

**任务操作**：
- `UpdateTask` / `DeleteTask` / `BatchUpdateTasks` / `update_task_resource_group`

**工作流操作**：
- `createWorkflowDefinition` / `UpdateWorkflow` / `ImportWorkflowDefinition`
- `StopWorkflowInstances` / `StartWorkflowInstances` / `ExecuteAdhocWorkflowInstance`

**治理操作**：
- `CreateGovernanceAction` / `CreateGovernanceProgram`
- `DgcBatchSaveAgentOptResult` / `saveAgentOptResult` / `UpdateRuleFindingStatus`

**发布操作**（⚠️ 必须通过 deploy_node.py，自动推进流水线）：
- `createDeployment` - deploy_node.py 内部调用，不要直接使用

**补数据操作**（⚠️ 必须通过 backfill_node.py，自动轮询异步结果）：
- `supplementAsync` - backfill_node.py 内部调用，不要直接使用

**SQL 执行操作**（⚠️ 必须通过 execute_sql.py，SELECT 直接执行，写 SQL 两阶段确认）：
- `createQueryJob` - 通过 dataSourceCode 提交 SQL（execute_sql.py 内部调用）
- `createExecutorJob4Ida` - 通过 dataSourceId 提交 SQL（execute_sql.py 内部调用）

**其他操作**：
- `CreateQualityTask` / `createMcProject`

---

## 常见错误

| 错误码 | 原因 | 解决方案 |
|-------|------|---------|
| 401 | Token 过期 | 检查 ~/.dataworks/.env 中的 BFF_TOKEN |
| 403 | 无权限 | 检查用户是否有该项目访问权限 |
| 404 | 资源不存在 | 检查 ID 是否正确 |
| 空列表 | 无数据或参数错误 | 检查参数类型（字符串 vs 数字） |

---

## 常量参考

### deployStatus

| 值 | 含义 |
|---|------|
| 0 | 未发布/已下线 |
| 2 | 已发布（正常） |

### direction（血缘查询）

| 值 | 含义 |
|---|------|
| UP | 上游血缘 |
| DOWN | 下游血缘 |

### env

| 值 | 含义 |
|---|------|
| prod | 生产环境 |
