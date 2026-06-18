# metric — 指标查询

## 子命令速查

| 子命令 | 说明 |
|--------|------|
| `metric query` | PromQL 时序查询 |
| `metric categories` | 查看应用可用指标分类 |
| `metric list` | 列出/搜索应用可用指标 |
| `metric summary` | 应用核心指标一览（CPU/内存/QPS/RT） |
| `metric anomaly trend` | 趋势异常检测（陡升/陡降） |
| `metric anomaly outlier` | 离群点检测 |
| `semconv describe/resolve/search/list` | 指标语义化查询与物理名反查 |

---

## metric query — PromQL 查询

```bash
sf metric query '<promql>' [options]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `<promql>` | PromQL 语句（位置参数） | - |
| `-F, --file <FILE>` | 从文件读取 PromQL | - |
| `-s, --start` | 开始时间 | `1h ago` |
| `-e, --end` | 结束时间 | `now` |
| `--tenant` | 指定 tenant（如 `sunfire_snapshot`） | 自动 |
| `--step` | 采样间隔（`10s` / `1m` / `1h`，长时间查询建议加大） | 自动 |
| `-f` | 输出格式：`json` / `table` / `ascii` / `value` | `json` |

**示例：**

```bash
# 基础查询
sf metric query 'avg(pod_cpu_request_util{app_name="sunfire-web-api"})' -s '1h ago'

# 按站点分组
sf metric query 'avg by(site)(pod_cpu_request_util{app_name="sunfire-web-api"})' -s '30m ago'

# ASCII 趋势图
sf metric query 'avg(pod_cpu_request_util{app_name="sunfire-web-api"})' -s '1h ago' -f ascii

# 提取单值（用于脚本条件判断）
CPU=$(sf metric query 'avg(pod_cpu_request_util{app_name="sunfire-web-api"})' -s '10m ago' -f value)

# 长时间查询降低精度
sf metric query 'avg(pod_cpu_request_util{app_name="sunfire-web-api"})' -s '7d ago' --step 1h

# 从文件读取复杂 PromQL（解决 shell 引号转义问题）
sf metric query --file query.promql -s '1h ago'

# stdin 管道
echo 'avg(pod_cpu_limit_usage{app_name="sunfire-web-api"})' | sf metric query -s '1h ago'
```

---

## metric categories / list — 发现可用指标

```bash
# 列出应用所有监控项类别
sf metric categories --app <APP>

# 查看某类别下的指标（含指标名、维度、example_promql 等）
sf metric list --app <APP> --category <CODE>

# 按关键词搜索指标
sf metric list --app <APP> --query <KEYWORD> [--category <CODE>] [-n <LIMIT>]

# 常见 category code：
#   system  — 基础监控（CPU/内存/网络/磁盘）
#   hsf     — HSF RPC 中间件
#   jvm     — JVM（GC/堆/线程）
#   web     — Web/HTTP
#   tddl    — TDDL 数据库
#   metaq   — MetaQ 消息队列
```

**示例：**

```bash
sf metric categories --app sunfire-web-api                 # 先查有哪些类别
sf metric list --app sunfire-web-api --category hsf        # 查 HSF 指标详情（含 example_promql）
sf metric list --app sunfire-web-api --category system
```

---

## metric list — 模糊搜索

```bash
sf metric list --app <APP> [--query <KEYWORD>] [--category <CODE>] [-n <LIMIT>]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--app` | 应用名称 | 必填 |
| `-Q, --query` | 搜索关键词 | - |
| `--category` | 指标分类过滤（如 `system` / `hsf` / `jvm`，别名：`--item`） | - |
| `-n, --limit` | 最多返回多少条指标（别名：`-L`） | `20` |

```bash
sf metric list --app sunfire-web-api                              # 列出应用可见指标
sf metric list --app sunfire-web-api --query cpu                  # 搜索 CPU 相关
sf metric list --app sunfire-web-api --query qps --category hsf   # 在 HSF 类别中搜 qps
```

---

## metric summary — 核心指标一览

```bash
sf metric summary --app <APP> [-s <START>]
```

自动查询 system/web/hsf/jvm 类别的核心指标，返回 avg/max/min/last 汇总值。

```bash
sf metric summary --app sunfire-web-api
sf metric summary --app sunfire-web-api -s '3h ago'
```

---

## metric anomaly — 异常检测

```bash
# 趋势异常（陡升/陡降，建议 3h+ 时间窗口）
sf metric anomaly trend '<promql>' -s '3h ago'
# 离群点检测
sf metric anomaly outlier '<promql>' -s '1h ago'
```

---

## PromQL 技巧

```bash
# HSF 服务端 QPS（按服务名分组）
avg by(service)(middleware_hsf_provider_qps{app_name="sunfire-web-api"})

# HSF 服务端 RT（p99）
quantile by(service)(0.99, middleware_hsf_provider_rt{app_name="sunfire-web-api"})

# HSF 服务端错误率（按接口）
sum by(service)(middleware_hsf_provider_service_method_error_qps{app_name="sunfire-web-api"})
  / sum by(service)(middleware_hsf_provider_service_method_qps{app_name="sunfire-web-api"})

# JVM 堆内存使用率
avg(jvm_heap_used{app_name="sunfire-web-api"}) / avg(jvm_heap_max{app_name="sunfire-web-api"})
```

---

## semconv — 指标语义化查询

`semconv` 用于在“语义指标名”和“后端物理指标名”之间互查，适合不知道具体 PromQL 指标名时先检索定义。

```bash
# 查看语义指标定义（含 storage.metric / unit / category）
sf semconv describe system.cpu.util

# 物理名 → 语义名反查
sf semconv resolve pod_cpu_limit_usage

# 全文搜索指标（匹配指标名、描述、物理名）
sf semconv search "cpu util"
sf semconv search qps --category hsf

# 列出指标，默认 20 条；-n 0 表示不限制
sf semconv list --category system
sf semconv list -n 0 -f csv > all_metrics.csv
```

典型流程：先 `sf semconv search cpu` 找到语义指标，再 `sf semconv describe <name> -b` 获取物理指标名，最后用 `sf metric query '<physical_metric>{app_name="<APP>"}'` 查询时序数据。
