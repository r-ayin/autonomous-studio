# event — 变更事件 & 应急事件

> 变更事件用 `sf event`，应急事件（TR 故障/风险单）用 `sf incident`。

---

## event — 变更事件

### 子命令

| 子命令 | 说明 |
|--------|------|
| `event query` | 查询/统计变更事件（PromQL 风格语法，支持列表和聚合两种模式） |
| `event change list` | 查询应用业务变更（GOC，含基础设施变更） |

### event query — 事件查询与统计

```bash
sf event query [-s <START>] [-e <END>] [--query <QUERY>] [-n <LIMIT>] [-p <PAGE>]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-s, --start` | 开始时间 | `24h ago` |
| `-e, --end` | 结束时间 | `now` |
| `-Q, --query` | PromQL 风格查询语句（可选，不传则返回所有事件） | - |
| `-n, --limit` | 最多返回多少条事件（聚合查询忽略此参数，别名：`-L`） | `20` |
| `-p, --page` | 分页 | `1` |

**查询语法：** `{} | field = "value" [and|or] field != "value2"`

**可用字段：** `appName`、`source`、`type`、`eventLevel`、`instanceId`、`data.*`

**列表查询示例：**

```bash
# 查最近 24h 所有事件
sf event query -s '24h ago'

# 按应用过滤
sf event query --query '{} | appName = "buy2"' -s '24h ago'

# 按来源系统过滤
sf event query --query '{} | appName = "buy2" and source = "changefree"' -s '24h ago'

# OR 组合
sf event query --query '{} | appName = "buy2" or source = "normandy"' -s '24h ago'
```

**聚合统计示例：**

```bash
# 按时间窗口统计（替代旧的 event stat）
sf event query --query 'count_downsample({} | appName = "buy2"[1h])' -s '7d ago'

# 按来源分组统计
sf event query --query 'sum by(source) count_downsample({} | appName = "buy2"[1h])' -s '7d ago'
```

### event change list — GOC 变更

```bash
sf event change list --app <APP> -s <START> [--infra]
```

```bash
# 查业务变更
sf event change list --app sunfire-web-api -s '3d ago'

# 含基础设施变更（机器变更/配置变更等）
sf event change list --app sunfire-web-api -s '3d ago' --infra
```

---

## incident — 应急事件（TR 技术风险平台）

### 子命令

| 子命令 | 说明 |
|--------|------|
| `incident list` | 列表查询应急单 |
| `incident get` | 查询事件详情 |
| `incident members` | 查询应急人员 |
| `incident groups` | 查询关联钉群 |
| `incident feedback` | 查询结单反馈 |
| `incident impacts` | 查询影响面 |

### incident list

```bash
sf incident list [options]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-t, --type` | 事件类型：`RISK`（风险）/ `FAULT`（故障） | `RISK` |
| `--handler` | 处理人工号 | - |
| `-s, --start` | 开始时间 | - |
| `-e, --end` | 结束时间 | - |
| `--source` | 来源系统（如 `app_monitor`，可多次指定） | - |
| `--app` | 按应用名筛选（逗号分隔多个） | - |
| `-n, --limit` | 最多返回多少条应急单（别名：`-L`） | `20` |
| `-p, --page` | 分页编号 | `1` |

```bash
sf incident list --type RISK -s '24h ago'
sf incident list --type FAULT -s '7d ago' --handler 291194
sf incident list --type RISK --source app_monitor -s '24h ago'
sf incident list --app sunfire-web-api,logflux -s '24h ago'
```

### incident get / members / groups / feedback / impacts

```bash
sf incident get <MISSION_NUMBER>
sf incident members <MISSION_NUMBER>
sf incident groups <MISSION_NUMBER>
sf incident feedback <MISSION_NUMBER>
sf incident impacts <MISSION_NUMBER>
```

**典型工作流：**

```bash
# 1. 查近期风险事件
sf incident list --type RISK -s '24h ago'

# 2. 查事件详情（MISSION_NUMBER 从 list 结果取）
sf incident get 202503100000001290001

# 3. 查应急人员
sf incident members 202503100000001290001

# 4. 查关联钉群
sf incident groups 202503100000001290001

# 5. 查结单反馈
sf incident feedback 202503100000001290001
```
