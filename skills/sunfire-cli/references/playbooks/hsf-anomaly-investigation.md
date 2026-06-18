# Playbook: HSF 服务异常排查

**场景：** 应用收到 HSF 相关报警，或怀疑某应用的 HSF 调用存在异常（QPS 下跌、RT 飙升、错误率升高）。

---

## 第一步：了解应用 HSF 可用指标

```bash
# 查看应用概览（确认 HSF 是否存在、当前健康状态）
sf app get --app <APP_NAME>

# 查看 HSF 指标元数据（指标名、维度、example_promql）
sf metric list --app <APP_NAME> --category hsf
```

**关注字段：**
- `name`：指标名，如 `middleware_hsf_provider_qps`、`middleware_hsf_provider_rt`、`middleware_hsf_provider_service_method_error_qps`
- `dimensions`：可用标签，如 `service`、`method`、`site`
- `example_promql`：可直接使用的查询示例

---

## 第二步：查询 HSF 核心指标

```bash
# QPS — 按服务名分组，看哪个接口流量异常
sf metric query 'avg by(service)(middleware_hsf_provider_qps{app_name="<APP_NAME>"})' \
  -s '1h ago' -f table

# RT — p99 响应时间
sf metric query 'quantile by(service)(0.99, middleware_hsf_provider_rt{app_name="<APP_NAME>"})' \
  -s '1h ago' -f table

# 异常次数 — 哪个接口报错最多
sf metric query 'sum by(service)(middleware_hsf_provider_service_method_error_qps{app_name="<APP_NAME>"})' \
  -s '1h ago' -f table

# ASCII 趋势图（直观看时间走势）
sf metric query 'avg(middleware_hsf_provider_qps{app_name="<APP_NAME>"})' -s '1h ago' -f ascii
```

**判断异常：**
- QPS 骤降 → 可能流量切走或服务不可用
- RT p99 > 正常值 3x → 存在慢调用
- error_qps 突增 → 报错服务或调用方异常

---

## 第三步：异常检测（可选）

```bash
# 自动检测趋势异常（陡升/陡降）
sf metric anomaly trend \
  'avg by(service)(middleware_hsf_provider_rt{app_name="<APP_NAME>"})' \
  -s '3h ago'

# 离群点检测（某台机器异常）
sf metric anomaly outlier \
  'avg by(serverIp)(middleware_hsf_provider_service_method_error_qps{app_name="<APP_NAME>"})' \
  -s '1h ago'
```

---

## 第四步：定位异常接口，查关联 Trace

```bash
# 找出异常最多的接口（假设为 SERVICE_NAME）
# 查该接口的失败调用链
sf trace list \
  --filter '{} | serverName="<APP_NAME>" and rpcId="<SERVICE_NAME>" and resultType!=1' \
  -s '1h ago' \
  -n 10

# 或查该接口所有调用，人工从返回结果中按耗时排序/筛选
sf trace list \
  --filter '{} | serverName="<APP_NAME>" and rpcId="<SERVICE_NAME>"' \
  -s '1h ago' \
  -n 10

# 按 RPC 类型过滤（只看 HSF 服务端失败调用）
sf trace list \
  --filter '{} | serverName="<APP_NAME>" and rpcType=2 and resultType!=1' \
  -s '1h ago' \
  -n 10
```

记录返回结果中的 `trace_id` 字段。

---

## 第五步：查 Trace 详情

```bash
# 查某条 trace 的完整 Span 树
sf trace get <TRACE_ID>

# 如返回数据量很大，可只取关键字段
sf trace get <TRACE_ID> --fields spanId,name,rt,resultType,rpcId
```

**关注字段：**
- `rt_ms`：每个 Span 的耗时（毫秒）
- `result`：调用结果（如 `OK`、`BIZ_ERROR`、`RPC_ERROR`、`TIMEOUT`）
- `result_code`：具体错误码
- `service`：接口名
- 最深的 Span = 根因所在层

---

## 第六步：基于 TraceId 查日志

```bash
# 查该 trace 的关联异常日志
sf log error list --app <APP_NAME> --trace-id <TRACE_ID> -s '1h ago'

# 查 Java 异常日志（看是否有 Exception 堆栈）
sf log error list --app <APP_NAME> -s '1h ago' -n 10

# 用堆栈详情查（数据量大，确认有异常后再用）
sf log error list --app <APP_NAME> -s '1h ago' --stack -n 5

# 搜索特定异常关键词（需先获取 LogStore uni-key）
# sf log sls store list --app <APP_NAME>  → 拿到 uni-key
sf log sls query \
  --uni-key '<UNI_KEY>' \
  --query 'HSFTimeOutException OR RpcException' \
  -s '1h ago' -n 20
```

---

## 第七步：检查变更事件（排查是否由发布引起）

```bash
# 查最近 3 天的业务变更
sf event change list --app <APP_NAME> -s '3d ago'

# 含基础设施变更（机器变更、配置推送等）
sf event change list --app <APP_NAME> -s '3d ago' --infra
```

对比异常开始时间与变更时间，判断是否由发布/配置变更引起。

---

## 完整排查命令速查

```bash
APP="<your-app-name>"

# 1. 看应用概览 + HSF 指标元数据
sf app get --app $APP
sf metric list --app $APP --category hsf

# 2. QPS / RT / 异常趋势
sf metric query "avg by(service)(middleware_hsf_provider_qps{app_name=\"$APP\"})" -s '1h ago' -f table
sf metric query "quantile by(service)(0.99, middleware_hsf_provider_rt{app_name=\"$APP\"})" -s '1h ago' -f table
sf metric query "sum by(service)(middleware_hsf_provider_service_method_error_qps{app_name=\"$APP\"})" -s '1h ago' -f table

# 3. 查失败 Trace
sf trace list --filter "{} | serverName=\"$APP\" and resultType!=1" -s '1h ago' -n 10

# 4. Trace 详情（替换 TRACE_ID）
sf trace get <TRACE_ID>

# 5. 关联日志
sf log error list --app $APP --trace-id <TRACE_ID> -s '1h ago'
sf log error list --app $APP -s '1h ago' -n 10

# 6. 变更记录
sf event change list --app $APP -s '3d ago'
```
