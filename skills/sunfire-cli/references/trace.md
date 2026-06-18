# trace — 调用链查询

## 子命令速查

| 子命令 | 说明 |
|--------|------|
| `trace list` | 使用 TraceQL 过滤条件查询 Trace 列表 |
| `trace get` | 根据 TraceId 查完整调用链明细（Span 树） |
| `trace stat` | TraceQL 多维度统计聚合 |

---

## trace list — 列表查询

```bash
sf trace list [options]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-s, --start` | 开始时间 | `1h ago` |
| `-e, --end` | 结束时间 | `now` |
| `--filter` | TraceQL 过滤条件，如 `'{} | serverName="myapp"'` | 必填 |
| `-n, --limit` | 最多返回多少条 Trace 结果（别名：`-L`） | `20` |

常用 TraceQL 字段：`serverName`（服务端应用）、`clientName`（客户端应用）、`rpcType`（调用类型）、`resultType`（调用结果）。常见 `resultType`：`1` 成功，`2` 业务错误，`3` RPC 错误，`4` 超时，`5` 软错误，`6` 限流。

常见 `rpcType`：`0` HTTP 入口，`1` HSF 客户端，`2` HSF 服务端，`4` TDDL，`5` Tair，`13` MetaQ 发送，`252` MetaQ 消费，`25` HTTP 客户端，`251` HTTP 服务端，`40` 本地调用。

**示例：**

```bash
# 查最近 1h 调用链
sf trace list --filter '{} | serverName="sunfire-web-api"' -s '1h ago' -n 5

# 只看失败调用
sf trace list --filter '{} | serverName="sunfire-web-api" and resultType!=1' -s '1h ago'

# 按服务端 IP 过滤
sf trace list --filter '{} | serverIp="10.0.0.1"' -s '1h ago'

# 按服务名过滤（HSF 接口）
sf trace list --filter '{} | serverName="sunfire-web-api" and rpcId="com.alibaba.sunfire.api.AlarmService:queryAlarms"' -s '1h ago'

# 按 RPC 类型过滤（只看 HSF 服务端）
sf trace list --filter '{} | serverName="logflux" and rpcType=2' -s '1h ago'

# HSF 指定接口
sf trace list --filter '{} | serverName="logflux" and rpcType=2 and rpcId="com.alibaba.logflux.FooService:bar"' -s '1h ago'
```

---

## trace get — 调用链详情

```bash
sf trace get <TRACE_ID> [--fields <FIELD>,...]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `<TRACE_ID>` | TraceId（调用链唯一标识） | 必填 |
| `--fields` | 指定返回字段（逗号分隔），用于减少大 Trace 返回数据量 | - |

```bash
# 查完整调用链详情
sf trace get 0a1b2c3d4e5f6789

# 大 Trace 只返回关键字段
sf trace get 0a1b2c3d4e5f6789 --fields spanId,name,rt,resultType
```

返回 Span 列表，每个 Span 含 `server`、`client`、`rt_ms`（耗时毫秒）、`result`（调用结果）、`result_code`、`time`、`service`（接口名）、`server_ip`、`rpc_type` 等字段。

---

## trace stat — 维度统计

```bash
sf trace stat '<TraceQL>' [-s <START>] [-e <END>]
```

```bash
# 按服务端 IP 统计调用量
sf trace stat 'sum by(serverIp)(count_over_time({serverName="sunfire-web-api"}))' -s '10m ago'

# 按 RPC 接口统计错误数
sf trace stat 'sum by(rpcId)(count_over_time({serverName="sunfire-web-api",status="error"}))' -s '10m ago'

# 按调用状态统计
sf trace stat 'sum by(resultType)(count_over_time({serverName="sunfire-web-api"}))' -s '1h ago'
```

---

## 关联工作流

**Trace → Log：** 拿到 `trace_id` 后，用 `sf log error list --trace-id` 查关联异常日志：

```bash
# 先查 trace 列表拿 trace_id
TRACE_ID=$(sf trace list --filter '{} | serverName="myapp" and resultType!=1' -s '1h ago' -n 1 -f json | jq -r '.traces[0].trace_id')

# 再查该 trace 的异常日志
sf log error list --app myapp --trace-id "$TRACE_ID" -s '1h ago'

# 查完整 Span 树
sf trace get "$TRACE_ID"
```
