# log — 日志查询

## 子命令速查

| 子命令 | 说明 |
|--------|------|
| `log sls store list` | 查看应用的 LogStore 列表（SLS 日志源） |
| `log sls query` | SLS 日志查询（需先从 `log sls store list` 获取 uniKey） |
| `log error list` | 查询 Java 异常错误日志明细（支持按 TraceId 过滤） |
| `log sql` | SQL/SPL 宿主机日志查询（绕过采集链路，直接读目标机器） |

---

## log sls store list — LogStore 列表

```bash
sf log sls store list --app <APP> [--log-path <PATH>] [--app-group <GROUP>]
```

查看应用接入的 SLS 日志源，获取 `uniKey` 用于后续 `log sls query`；默认输出按 `uniKey` 分组聚合，`--fields all` 可查看完整 relations。

```bash
sf log sls store list --app sunfire-web-api
sf log sls store list --app sunfire-web-api --log-path /home/admin/logs
sf log sls store list --app sunfire-web-api --fields all
```

---

## log sls query — SLS 日志查询

```bash
sf log sls query --uni-key <UNI_KEY> [--query <SPL>] [options]
```

> `--uni-key` 必填，通常可从其中自动解析 project/logstore。仅需要显式覆盖时，`--project` 和 `--log-store` 必须成对传入。

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--uni-key` | 资源唯一 ID（从 `log sls store list` 的 `config.uniKey` 获取） | 必填 |
| `--project` | SLS Project 名称；显式覆盖时需和 `--log-store` 一起提供 | 从 `--uni-key` 解析 |
| `--log-store` | SLS LogStore 名称；显式覆盖时需和 `--project` 一起提供 | 从 `--uni-key` 解析 |
| `--query` | SPL 查询语句 | - |
| `-s, --start` | 开始时间 | `1h ago` |
| `-e, --end` | 结束时间 | `now` |
| `-n, --limit` | 最多返回多少条日志（最大 1000，别名：`-L`） | `20` |
| `--offset` | 拉取日志起始位点 | `0` |

**示例：**

```bash
# 先获取 LogStore uniKey
sf log sls store list --app sunfire-web-api
# 输出包含: uniKey/project/logstore

# 全文搜索 ERROR
sf log sls query \
  --uni-key 'ACS#1069916544051798#ACS::SLS::LogStore#cn-wulanchabu#sunfire-web:prod-api-log' \
  --query 'ERROR' -s '1h ago' -n 20

# SPL 聚合查询
sf log sls query \
  --uni-key 'ACS#...' \
  --query '* | select count(1)' -s '1h ago'

# 需要覆盖解析结果时，project/log-store 必须成对提供
sf log sls query \
  --uni-key 'ACS#...' \
  --project cn-hangzhou-prod \
  --log-store myapp-access-log \
  --query 'ERROR' -s '1h ago'
```

---

## log error list — Java 异常日志

```bash
sf log error list --app <APP> [options]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--app` | 应用名称 | 必填 |
| `-s, --start` | 开始时间 | `1h ago` |
| `-e, --end` | 结束时间 | `now` |
| `-n, --limit` | 最多返回多少条错误日志（别名：`-L`） | `20` |
| `-p, --page` | 分页编号 | `1` |
| `--stack` | 包含堆栈信息（⚠️ 数据量大） | false |
| `--pattern` | 按异常类型过滤（如 `java.lang.RuntimeException`） | - |
| `--frame-pattern-id` | 按堆栈 md5 精确过滤 | - |
| `--trace-id` | 按 TraceId 过滤异常日志（替代已移除的 `log by-trace`） | - |

```bash
sf log error list --app sunfire-web-api -s '1h ago' -n 5
sf log error list --app sunfire-web-api -s '30m ago' --stack -n 3
sf log error list --app sunfire-web-api --pattern 'java.lang.NullPointerException' -s '1h ago'

# 按 TraceId 查关联异常日志（Trace → Log 关联分析）
sf log error list --app sunfire-web-api --trace-id 0a1b2c3d4e5f6789 -s '1h ago'
```

返回字段含 `trace_id` 和 `next_step`（建议的下一步 trace 查询命令，可直接按 `sf trace get <trace_id>` 继续排查）。

---

## log sql — 宿主机日志查询

通过 SPL Worker 集群直接读取目标宿主机的日志文件，绕过 Sunfire Agent 采集链路，适合即时排查指定机器上的日志。

```bash
sf log sql --ip <IP> --log-path <LOG_PATH> --query <QUERY> [options]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--ip` | 目标机器 IP | 必填 |
| `--log-path` | 宿主机上的日志文件路径 | 必填 |
| `--query` | SQL 或 SPL 查询语句 | 必填 |
| `-s, --start` | 开始时间 | `1h ago` |
| `-e, --end` | 结束时间 | `now` |

```bash
# SQL 语法查询
sf log sql --ip 10.0.0.1 --log-path /home/admin/logs/app.log \
  --query "SELECT * FROM log_table WHERE content LIKE '%ERROR%' LIMIT 100" \
  -s '1h ago'

# SPL 语法查询
sf log sql --ip 10.0.0.1 --log-path /home/admin/logs/app.log \
  --query '* | project content as c | where c like "%ERROR%" | limit 10' \
  -s '30m ago'
```

---

## 典型工作流

```bash
# 1. 先查 LogStore 列表了解有哪些日志源（获取 uni-key）
sf log sls store list --app sunfire-web-api

# 2. 查异常日志
sf log error list --app sunfire-web-api -s '1h ago' -n 10

# 3. 拿到 trace_id 后查关联异常日志
sf log error list --app sunfire-web-api --trace-id <TRACE_ID> -s '1h ago'

# 4. 按关键词搜索 SLS 原始日志（uni-key 从步骤 1 获取）
sf log sls query \
  --uni-key '<UNI_KEY>' \
  --query 'NullPointerException' -s '30m ago' -n 20

# 5. 直接查宿主机日志（需要知道 IP 和日志路径）
sf log sql --ip 33.8.160.171 \
  --log-path /home/admin/logs/app.log \
  --query '* | where content like "%ERROR%" | limit 20' \
  -s '1h ago'
```
