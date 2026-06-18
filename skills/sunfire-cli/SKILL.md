---
name: sunfire-cli
version: 0.4.0
description: Sunfire 可观测平台 CLI（sf 命令）使用助手。覆盖指标查询（PromQL）、报警管理、调用链分析、日志查询、变更事件、应急事件、应用拓扑、业务监控、Dashboard、AuthX 鉴权状态检查与安装升级等全链路可观测能力。当用户提到以下场景时触发：查指标/PromQL查询/查报警/查告警/查Trace/查调用链/查日志/查变更/查故障单/查应急事件/查应用资源/排查HSF异常/分析性能/查监控大盘/sf命令/sf鉴权/sf auth status/sf登录/sf安装。即使用户没有明确提到"sf"命令，只要涉及 Sunfire 可观测平台的查询与分析操作，均应使用此技能。
x-source: aone-open
repository: https://code.alibaba-inc.com/qunbu/sunfire-cli
---

# sf — Sunfire 可观测平台 CLI

面向 AI Agent 和开发者的可观测数据统一查询入口。默认输出 JSON，适合管道处理和 Agent 消费。

> ⚠️ **仅限阿里集团内网使用**（VPN / 办公网 / 开发机）

> 📌 **版本基线**：本 skill 基于 `sunfire-cli v0.2.3` 编写。用户本机 CLI 可能滞后或更新更快；执行前先用 `sf --version` 确认版本，遇到命令/参数不确定时以 `sf <command> --help` 的实际输出为准，不要凭历史文档猜测。

---

## 环境准备（每次使用前必须执行）

**第一步：检测 CLI 是否已安装**

```bash
which sf && sf --version
```

若命令不存在 → 读取 [`references/setup.md`](references/setup.md) 完成安装，再执行第二步。

**第二步：检测认证状态（必须执行）**

```bash
sf auth status
```

- 输出认证可用 / AuthX 可用 / Token 可用 → 继续执行任务
- 阿里郎 / Aone sandbox 环境通常会通过 AuthX / NCS 自动获取身份，不要默认要求用户先登录
- 输出 AuthX/NCS 不可用且没有 fallback Token/OAuth → 执行 `sf auth login` 配置 BUC OAuth fallback，或按用户提供的 Token 方式处理

> ⚠️ 跳过认证检查可能导致后续命令返回 401。v0.2.3 起优先使用 `sf auth status` 检查状态，只有自动身份不可用时才引导 `sf auth login`。

---

## 命令总览

### 核心查询

| 命令 | 说明 | 详细文档 |
|------|------|----------|
| `sf metric query` | PromQL 时序数据查询 | [metric.md](references/metric.md) |
| `sf metric categories` | 查看应用可用指标分类 | [metric.md](references/metric.md) |
| `sf metric list` | 列出/搜索应用可用指标 | [metric.md](references/metric.md) |
| `sf metric summary` | 应用核心指标一览（CPU/内存/QPS/RT） | [metric.md](references/metric.md) |
| `sf metric anomaly trend/outlier` | 趋势异常/离群点检测 | [metric.md](references/metric.md) |
| `sf semconv describe/resolve/search/list` | 指标语义定义、物理名反查、全文搜索 | [metric.md](references/metric.md) |

### 报警管理

| 命令 | 说明 | 详细文档 |
|------|------|----------|
| `sf alarm list/get/stat` | 报警列表、详情、统计 | [alert.md](references/alert.md) |
| `sf alarm claim/resolve` | 接手/完结报警 | [alert.md](references/alert.md) |
| `sf alarm rule get/list/create/update/delete` | 报警规则查询与 CRUD | [alert.md](references/alert.md) |
| `sf alarm rule detect/status` | 规则检测、历史状态、区间回测 | [alert.md](references/alert.md) |

### 调用链

| 命令 | 说明 | 详细文档 |
|------|------|----------|
| `sf trace list` | 使用 TraceQL 过滤条件查询 Trace | [trace.md](references/trace.md) |
| `sf trace get` | 根据 TraceId 查完整调用链，支持 --fields 裁剪字段 | [trace.md](references/trace.md) |
| `sf trace stat` | TraceQL 多维度统计聚合 | [trace.md](references/trace.md) |

### 日志

| 命令 | 说明 | 详细文档 |
|------|------|----------|
| `sf log sls store list` | 查看应用的 SLS LogStore 列表 | [log.md](references/log.md) |
| `sf log sls query` | SLS 日志查询（通常只需 uni-key） | [log.md](references/log.md) |
| `sf log error list` | Java 异常日志（支持 --trace-id 关联） | [log.md](references/log.md) |
| `sf log sql` | SQL/SPL 宿主机日志直查 | [log.md](references/log.md) |

### 事件与应急

| 命令 | 说明 | 详细文档 |
|------|------|----------|
| `sf event query` | 变更事件查询/统计（PromQL 风格语法） | [event.md](references/event.md) |
| `sf event change list` | GOC 变更记录查询 | [event.md](references/event.md) |
| `sf incident list/get/members/...` | TR 应急事件全链路 | [event.md](references/event.md) |

### 应用与配置

| 命令 | 说明 | 详细文档 |
|------|------|----------|
| `sf app get` | 应用概览（监控项 + 云资源 + 健康状态） | [setup.md](references/setup.md) |
| `sf app resources` | 应用关联的云资源/中间件实例 | [setup.md](references/setup.md) |
| `sf app host get` | 按 IP 查机器元信息 | [setup.md](references/setup.md) |
| `sf monitor source/list/get/fields` | 自定义监控（业务监控）日志源、监控项、配置与字段发现；时序查询用 `sf metric query` | [config.md](references/config.md) |
| `sf dashboard get` | Dashboard 大盘配置与 PromQL 提取 | [config.md](references/config.md) |

### 工具

| 命令 | 说明 | 详细文档 |
|------|------|----------|
| `sf auth status/login/token/switch/list/logout` | 认证管理；默认 AuthX / NCS，OAuth 与 Token 作为 fallback | [setup.md](references/setup.md) |
| `sf upgrade` | 升级到最新版本 | [config.md](references/config.md) |
| `sf doctor` | 环境诊断（配置、AuthX/NCS、OAuth、Token、连通性） | [config.md](references/config.md) |
| `sf feedback req/bug` | 提交需求或 Bug 到 Aone | [config.md](references/config.md) |

**输出格式：** `-f json`（默认）/ `-f table` / `-f value`（单值，脚本用）/ `-f ascii`（趋势图）/ `-f csv` / `-f yaml`

**时间参数：** 所有 `-s` / `-e` 支持 `"1h ago"` `"30m ago"` `"3d ago"` `"now"` `"2026-03-26 10:00:00"`

---

## 故障排查标准路径

每步标注了输出的关键字段和下一步所需的输入，确保数据衔接不断。

```
① sf alarm list --app <APP> -s '24h ago'
   → 输出字段: alarm_id, alarm_rule_id
   → 下一步用: alarm_rule_id

② sf alarm rule get <alarm_rule_id>
   → 输出字段: queries[].query (PromQL), name, eval (触发条件)
   → 用途: 理解报警触发条件和阈值

③ sf metric list --app <APP> --category <CODE>
   → 输出字段: name (指标名), example_promql, dimensions
   → 下一步用: 指标名或 example_promql

④ sf metric query '<promql>' -s '1h ago'
   → 输出: 时序数据点
   → 用途: 定位异常时段，确认指标波动

⑤ sf trace list --filter '{} | serverName="<APP>" and resultType!=1' -s '1h ago'
   → 输出字段: trace_id, server, rt_ms, result
   → 下一步用: trace_id

⑥ sf trace get <trace_id>
   → 输出字段: spans[].server, rt_ms, result, result_code, service
   → 用途: 查看 Span 调用树，找最深异常 Span = 根因层

⑦ sf log error list --app <APP> --trace-id <trace_id> -s '1h ago'
   → 输出字段: exception, message, trace_id, next_step
   → 用途: 按 TraceId 关联查异常日志上下文

⑧ sf log error list --app <APP> -s '1h ago'
   → 输出字段: exception, message, trace_id（批量查看异常堆栈）

⑨ sf event change list --app <APP> -s '3d ago'
   → 输出: 变更记录列表
   → 用途: 对比异常时间与变更时间，判断是否由发布引起
```

---

## 当前能力边界与避免误用

不要把历史文档里的旧命令当作当前 CLI 能力。遇到不确定的命令或参数时，优先执行 `sf <command> --help` 或读取本 skill 对应 reference；不要凭旧记忆补全不存在的 flag。

### 诊断命令边界

| 命令 | 说明 | 备注 |
|------|------|------|
| `sf doctor` | 环境诊断（配置、认证、AuthX/NCS、连通性） | v0.2.3 对外可用 |

### 容易混淆的当前入口

| 场景 | 当前入口 |
|------|----------|
| Trace 过滤 | `sf trace list --filter '<TraceQL>'` |
| 裁剪 Trace 字段 | `sf trace get <trace_id> --fields spanId,name,rt,resultType` |
| SLS 日志源与查询 | `sf log sls store list` / `sf log sls query` |
| 业务监控时序查询 | 先 `sf monitor fields` 发现指标，再 `sf metric query` 查询 |
| 报警规则检测/回测 | `sf alarm rule detect` |
| 认证状态检查 | `sf auth status`，不要默认先要求 `sf auth login` |

---

## Playbooks

- **[HSF 服务异常排查](references/playbooks/hsf-anomaly-investigation.md)** — HSF 指标异常 → 定位接口 → Trace → 日志根因

---

## 参考文档

按排查流程排序，按需加载，不要一次全读：

- [`references/alert.md`](references/alert.md) — 报警管理 + 规则分析（排查起点）
- [`references/metric.md`](references/metric.md) — 指标查询完整参数
- [`references/trace.md`](references/trace.md) — 调用链查询完整参数
- [`references/log.md`](references/log.md) — 日志查询完整参数
- [`references/event.md`](references/event.md) — 变更事件 + 应急事件
- [`references/setup.md`](references/setup.md) — 安装、鉴权、全局选项、应用信息
- [`references/config.md`](references/config.md) — 业务监控、Dashboard、升级、反馈
