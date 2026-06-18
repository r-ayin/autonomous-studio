---
name: normandy-cli
version: 0.20.0
description: 将自然语言的 Normandy 平台运维问题翻译成正确的 `normandy` CLI 命令，并给出简短、可直接复制的命令模板。只要用户在问 auth 登录、登录状态、OAuth fallback、app 应用查询、app-group 应用分组、host 主机查询与登录与容器文件浏览与 Pod 暂停/恢复、host diagnose 机器诊断/GPU诊断/pod诊断、app-env 环境、order 工单、quota 额度/配额/额度账号/额度统计/组织管理员、log 日志查询/SLS日志/Pod日志、resource 资源搜索、trait 应用特性/限流/熔断/降级/灰度等治理能力查询、cert 证书查询/证书过期/证书托管/TLS探测/顶级域/域名报备、VIP/域名/专线等网络资源、阿里云账号管理（aliyun-account/sub-account/role/user-group）、CLI 升级，或任意 `aliyun-*` 云资源查询应该用什么 Normandy 命令，即使用户没有显式提到 "CLI" 或 "normandy"，也应使用这个 skill。当用户提到"查应用"、"查机器"、"查工单"、"查 ECS/RDS/Redis/NLB"、"登录主机"、"暂停Pod"、"恢复Pod"、"pod暂停"、"pod恢复"、"查 VIP"、"怎么升级 normandy-cli"、"机器异常"、"诊断事件"、"GPU诊断"、"pod诊断"、"查日志"、"SLS日志"、"Pod日志"、"容器日志"、"看文件"、"看目录"、"查特性"、"trait"、"限流规则"、"熔断规则"、"降级规则"、"应用导入了哪些特性"、"查证书"、"证书过期"、"证书托管"、"TLS探测"、"顶级域"、"域名报备"、"DNS TXT"等运维操作时，也应触发。默认把业务命令视为可直接执行，不要把 `normandy auth login` 当成所有业务命令的前置步骤；只有在明确需要 OAuth 修复、用户主动要求登录、或真实执行后收到认证失败信号时，才引导到 `auth status` / `auth login`。
x-source: aone-open
repository: https://code.alibaba-inc.com/qunbu/normandy-cli
---

# Normandy CLI 命令路由 Skill

把自然语言运维需求转换成正确的 `normandy` 命令模板。如果用户只是想了解泛化的云计算概念，而不是映射到 CLI，就不要触发它。

## 前置条件

- 首次使用或缺少normandy(-cli)执行命令时，先读 `references/execution-guard.md` 完成安装
- 只要是在“推荐命令模板”，默认直接给业务命令，不要先要求用户执行 `normandy auth login`。
- 只有在“用户明确要求执行命令”或“需要本机真实查询结果”时，才读 `references/execution-guard.md` 做安装、执行和失败恢复检查。
- 认证默认认知要和当前 CLI 一致：业务命令优先走 AIT/APT；`normandy auth login` 是 OAuth fallback / 手工修复入口，不是所有业务命令的统一前置步骤。

## 命令速查表

优先用这张表直接回答。只有表中信息不够（歧义、缺参、参数名不确定）时，才读对应的领域参考文档。

| 命令族 | 子命令与关键参数                                                                                                                                                                                                                                                                                                                                                                                                                                      | 示例 |
|--------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| `auth` | `login` / `logout` / `status`。`status` 用于看 AIT 与 OAuth 双通道状态；`login` 主要用于 OAuth fallback、非交互环境预热、或手工修复登录态                                                                                                                                                                                                                                                                                                                                                 | `normandy auth status --output json`<br>`normandy auth login` |
| `app` | `get --name` 查基本信息；`summary --name` 查资源汇总                                                                                                                                                                                                                                                                                                                                                                                                     | `normandy app get --name normandy-ai`<br>`normandy app summary --name normandy-ai` |
| `app-group` | `get --name` 查详情；`list --app-name` 查列表                                                                                                                                                                                                                                                                                                                                                                                                        | `normandy app-group get --name normandy-ai.default`<br>`normandy app-group list --app-name normandy-ai` |
| `host` | `get --host` 查主机详情；`get --host --yaml` 查该主机对应 Pod 的原始 YAML；`list --app-name\|--app-group` 查列表；`login --host` 登录；`path --server --path` 浏览容器内文件目录（默认 /home/admin，`--container` 默认 main）；`pause --server [--timeout-minutes 30] [--container main]` 暂停 Pod；`resume --server [--container main]` 恢复 Pod；`--host`/`--server` 可传 SN/hostname/IP，暂停/恢复优先使用 SN 或 hostname。pause 前会检查目标容器在 Pod YAML `status.containerStatuses` 中的 `ready` 状态，只有目标容器非 ready 才允许暂停。注意 `--yaml` 不能和 `--output json` 同时使用                                                                                                                                                                                                                                                            | `normandy host get --host sn-12345`<br>`normandy host get --host sn-12345 --yaml`<br>`normandy host list --app-group normandy-ai.default`<br>`normandy host login --host sn-12345`<br>`normandy host path --server 11.1.1.1 --path /home/admin/logs`<br>`normandy host pause --server sn-12345`<br>`normandy host pause --server sn-12345 --container sidecar --timeout-minutes 15`<br>`normandy host resume --server sn-12345` |
| `host diagnose` | `list --host [--scope HOST\|GPU] [--type host\|pod]` 查诊断事件；`list --scope GPU --pod-name <name>` GPU Pod 诊断；`get --diagnose-id --type HOST\|GPU [--dimension top-kernel,critical-path]` 查诊断详情。`--diagnose-id` 需要先通过 `list` 获取：list 返回结果中的 taskId（HOST）或 profileId（GPU）即为 diagnose-id。用户没有 diagnose-id 时应先引导用 `list` 查询。用户提到"诊断 taskId"、"profileId"、"诊断详情"时应路由到 `host diagnose get`，不是 `order get`                                              | `normandy host diagnose list --host hippo-033118182196.ea120`<br>`normandy host diagnose list --scope GPU --pod-name mlflow-inference-master-0`<br>`normandy host diagnose get --diagnose-id 1233823432430332928 --type HOST`<br>`normandy host diagnose get --diagnose-id 20260317_92c372 --type GPU --dimension top-kernel,critical-path` |
| `app-env` | `get --stack-id` 查详情；`list --app-name\|--app-group` 查列表                                                                                                                                                                                                                                                                                                                                                                                       | `normandy app-env get --stack-id 12345`<br>`normandy app-env list --app-name normandy-ai` |
| `order` | `get --id` 查详情；`list --app-name\|--app-group` 查列表                                                                                                                                                                                                                                                                                                                                                                                             | `normandy order get --id 8700421000158`<br>`normandy order list --app-name normandy-ai` |
| `quota` | `list --app-name --app-group` 查扩容额度；`list-account [--name]` 查我的额度账号；`get-account (--id \| --app-name)` 查账号详情含管理员，两参数互斥；`get-stats --account-id --commodity-type [--scope] [--label] [--page] [--limit]` 按账号查额度统计；`list-org-admins --org-id` 查组织管理员。commodity-type 支持 pouch/pouch_lgt/pouch_spot/pouch_ondemand                                                                                                                                | `normandy quota list --app-name normandy-ai --app-group normandy-ai.default`<br>`normandy quota list-account`<br>`normandy quota list-account --name normandy`<br>`normandy quota get-account --id ACC-001`<br>`normandy quota get-account --app-name normandy-ai`<br>`normandy quota get-stats --account-id ACC-001 --commodity-type pouch`<br>`normandy quota get-stats --account-id ACC-001 --commodity-type pouch --scope CM10,EA120`<br>`normandy quota list-org-admins --org-id ORG-001` |
| `log` | `list --source sls\|pod`。**SLS 模式**（默认）：`--project --logstore` 单源查询，或 `--scene <name>` 按场景多源查询；`--from/--to` 时间范围（默认最近 15 分钟）；`--query` 过滤；`--size` 条数（默认 10）；`--offset` 起始行号（默认 0）；`--reverse` 倒序排列；`--power-sql` 独立 SQL 模式；`--topic` 日志主题。**Pod 模式**：`--source pod --server --path` 读容器日志文件；`--lines` 尾部行数（默认 10）；`--container` 容器名（默认 main）。**通用参数**：`--scene` 需配合 `--source` 指定读哪种源；`--output text\|json` 输出格式；`--verbose` 详细诊断信息；`--config PATH` 自定义配置文件路径。场景配置在 `~/.normandy/log.yaml`，支持 SLS 和 Pod 混合配置。凭证自动获取（STS），无需手工配置 AK/SK | `normandy log list --project my-proj --logstore access-log`<br>`normandy log list --project my-proj --logstore access-log --query "status:500" --size 20 --reverse`<br>`normandy log list --scene baas-center --output json`<br>`normandy log list --source pod --server 33.4.190.155 --path /home/admin/app/logs/app.log --lines 50`<br>`normandy log list --source pod --scene director-pods` |
| `resource` | `search --query` 全局模糊搜（同时搜平台资源、云资源实例、账号三类，结果分区块展示）；`get --sn` 按 SN 查；`--output json` 获取完整原始数据                                                                                                                                                                                                                                                                                                                                                 | `normandy resource search --query payment-gateway`<br>`normandy resource search --query LTAI5txxxxxxxxxxxxxxxx --output json`<br>`normandy resource get --sn sn-12345` |
| `trait` | `list --app-name` 查应用已导入的资源对象特性（限流/熔断/降级/灰度等治理规则）。可选 `--platform` 按平台过滤；`--trait-effective-stage-filter AFTER_VERSIONOUT\|DURING_VERSIONOUT`（默认 `AFTER_VERSIONOUT`，即出版本后生效）；`--including-legacy/--no-including-legacy`（默认包含老特性）；`--including-system/--no-including-system`（默认不含系统特性）。human 输出表格含特性ID/Key/状态/版本/创建人/最后修改人/创建时间/最后修改时间，每行下追加 Match Scope 与 Form Data；JSON 输出保留 API 原字段名 | `normandy trait list --app-name normandy-ai`<br>`normandy trait list --app-name normandy-ai --platform aone --no-including-legacy`<br>`normandy trait list --app-name normandy-ai --including-system --output json` |
| `cert` | `search --domain\|--app-name\|--cn`；`get --id`；`list [--status] [--validity] [--app-name] [--cn]`；`expiry [--days] [--app-name]`；`hosting --id [--name]`；`probe --domain [--port] [--sni]`。对接 Freestream 证书管理平台，只读查询 | `normandy cert search --domain example.com`<br>`normandy cert get --id 14065`<br>`normandy cert list --validity LESS_30`<br>`normandy cert expiry --days 60`<br>`normandy cert hosting --id 14065`<br>`normandy cert probe --domain example.com` |
| `cert top-domain` | `list [--name] [--status] [--all]`；`expiry [--days]`；`dns-record --name [--all]`。顶级域管理与报备辅助 | `normandy cert top-domain list`<br>`normandy cert top-domain list --name alibaba-inc.com`<br>`normandy cert top-domain expiry`<br>`normandy cert top-domain dns-record --name alibaba-inc.com` |
| `upgrade` | 无子命令，升级 CLI 本身                                                                                                                                                                                                                                                                                                                                                                                                                                | `normandy upgrade` |
| `vip` | `list --app-name`；`get --ip --port --protocol`                                                                                                                                                                                                                                                                                                                                                                                                | `normandy vip list --app-name normandy-ai`<br>`normandy vip get --ip 33.88.4.179 --port 80 --protocol TCP` |
| `vip-rs` | `list --ip --port --protocol` 查后端成员                                                                                                                                                                                                                                                                                                                                                                                                           | `normandy vip-rs list --ip 33.88.4.179 --port 80 --protocol TCP` |
| `domain` | `get --name`                                                                                                                                                                                                                                                                                                                                                                                                                                  | `normandy domain get --name n.alibaba-inc.com` |
| `cloud-link` | `list --app-name`；`get --id`                                                                                                                                                                                                                                                                                                                                                                                                                  | `normandy cloud-link list --app-name normandy-ai`<br>`normandy cloud-link get --id 2469719008000120` |
| `uni-connect` | `list --app-name\|--domain`；`get --domain --path --cluster-id`                                                                                                                                                                                                                                                                                                                                                                                | `normandy uni-connect list --domain n.alibaba-inc.com`<br>`normandy uni-connect get --domain n.alibaba-inc.com --path / --cluster-id alibaba-work` |
| `aliyun-account` | `get/list [--scene-type]`                                                                                                                                                                                                                                                                                                                                                                                                                     | `normandy aliyun-account list --scene-type CLOUD_ACCOUNT` |
| `aliyun-sub-account` | `get/list/login`；`permission list --id <cloud-id> [--trace-type all\|self\|user-group] [--verbose]` 查已绑定权限策略                                                                                                                                                                                                                                                                                                                                  | `normandy aliyun-sub-account login --account-id xxx --sub-account-name yyy`<br>`normandy aliyun-sub-account permission list --id ram-user-cloud-id`<br>`normandy aliyun-sub-account permission list --id ram-user-cloud-id --trace-type self`<br>`normandy aliyun-sub-account permission list --id ram-user-cloud-id --trace-type user-group --verbose` |
| `aliyun-role` | `get/list [--scope mine]`                                                                                                                                                                                                                                                                                                                                                                                                                     | `normandy aliyun-role list --scope mine` |
| `aliyun-user-group` | `get/list [--scope mine]`                                                                                                                                                                                                                                                                                                                                                                                                                     | `normandy aliyun-user-group list --scope mine` |
| `aliyun-*` 资源 | **26 种动态资源命令，每种都是独立的顶层命令族**，都至少支持 `get`/`list`，大部分还支持 `login`（打开对应控制台页面）。用户提到任何一种云资源名称时都应路由到对应的 `aliyun-*` 命令，不要说"不支持"。完整列表：`ecs`、`ecs-disk`（云盘）、`rds`、`redis`、`oss`、`kafka`、`nlb`、`nlb-listener`、`polardb`、`elasticsearch`、`clickhouse`、`hbase`、`lindorm`、`dts`、`mse`（微服务引擎）、`ots`、`gdb`、`cdn`、`nas-filesystem`、`ons-group`、`ons-topic`、`adb`、`adb-lake`、`adbpg`、`sls-project`、`sls-logstore`。`sls-project` 和 `sls-logstore` 还支持 `sts-token` | `normandy aliyun-ecs get --id xxx`<br>`normandy aliyun-mse login --id xxx`<br>`normandy aliyun-ecs-disk get --id xxx`<br>`normandy aliyun-sls-project sts-token --id xxx` |

重启、置换、扩容等变更操作目前不通过 CLI 开放，不要推荐。

## 工作流

1. **命中速查表 → 直接回答**：需求明确落到某个命令族，用速查表里的信息给出命令模板，不读额外文档。
2. **歧义/缺参 → 读一个领域参考文档**：命令族不确定或参数不明确时，先读 `references/top-level-routing.md` 定位命令族，再按需读一个领域文档（见下方"参考文档索引"）。
3. **非 normandy 能力 → 直接说明**：不属于 CLI 能力范围的，直接告知用户，不强行路由。
4. **执行型请求 → 读 `references/execution-guard.md`**：用户明确要执行命令时，读取该文档做安装校验、真实执行和错误恢复。不要把“先 `auth login`”当默认步骤；先执行业务命令，只有明确认证失败时再修复。

## 回答规则

- 默认只推荐模板（1-3 条），不直接执行；用户给了完整命令或明确要求执行时才执行
- 不编造业务参数（app 名、SN、ID 等），缺什么直接说
- AI/程序场景优先加 `--output json`；登录类命令不加
- 不要在业务命令前机械补一句“先执行 `normandy auth login`”；除非用户问的是登录本身、非交互环境预热、或你已经拿到明确认证失败信号
- 认证相关建议的默认顺序是：先给业务命令；需要排查认证时优先 `normandy auth status --output json`；只有 AIT 不可用且 OAuth 也缺失，或用户明确要求登录时，再给 `normandy auth login`
- `aliyun-*` 参数名不确定时，建议跑 `normandy aliyun-xxx ... --help`
- 需求跨多个命令族时，按顺序给 2-3 条命令，每条附一句用途
- 解释要短，不写长教程

## 边界与易混淆分流

- 分组下机器 → `host list`，不是 `app-group get`
- 应用资源概况 → `app summary`，不是 `app get`
- 域名基础信息 → `domain get`；域名接入规则 → `uni-connect`
- 机器异常/诊断事件 → `host diagnose list`；诊断详情 → `host diagnose get`，不是 `host get`
- 查 Pod 原始 YAML → `host get --host <sn|ip|hostname> --yaml`，不是 `host path`/`log list --source pod`
- 暂停/恢复 Pod → `host pause` / `host resume`，必须传 `--server`，优先用 SN 或 hostname；`pause` 的 `--timeout-minutes` 默认 30；`--container` 默认 main，如指定其他容器则 pause 前检查该目标容器的 ready 状态；`--pod-name` 只是可选目标覆盖
- VIP 本身 → `vip`；VIP 后端 → `vip-rs`；四层跨云 → `cloud-link`；七层接入 → `uni-connect`
- 诊断 taskId/profileId → `host diagnose get`，不是 `order get`
- 云盘/磁盘 → `aliyun-ecs-disk`，不是 `aliyun-ecs`；MSE 控制台 → `aliyun-mse login`
- 额度账号列表 → `quota list-account`；账号详情/管理员 → `quota get-account`；额度统计/用量 → `quota get-stats`；扩容额度 → `quota list`；组织管理员 → `quota list-org-admins`
- 查日志内容（SLS 或 Pod） → `log list`，不是 `aliyun-sls-project`/`aliyun-sls-logstore`（后者查 SLS 资源元信息）
- 看容器内文件/目录列表 → `host path`；读容器日志文件内容 → `log list --source pod`；看 Pod 原始 YAML → `host get --yaml`
- 类型明确 → 对应 `aliyun-*`；类型不明/只有 SN/关键字 → `resource`
- 应用治理特性（限流/熔断/降级/灰度/sentinel/hystrix 规则） → `trait list --app-name`，不是 `app get`/`app summary`；`app summary` 是资源汇总（机器/VIP/quota），`trait list` 是治理特性（rule 元数据）。出版本时（DURING_VERSIONOUT）生效的特性需显式传 `--trait-effective-stage-filter DURING_VERSIONOUT`
- **查 AK 权限**：先通过 `normandy resource search --query <AK> --output json` 获取 RAM 用户的 `uid`（返回 `accounts.data[].uid` 字段），再用 `normandy aliyun-sub-account permission list --id <uid> --trace-type all` 查权限。**注意**：`--id` 必须使用 RAM 用户的 UID（长数字串），而非 Normandy 内部 ID，否则会报错 `Sub-account not found`。
- 证书/SSL/TLS/HTTPS 证书相关 → `cert`；域名基础信息/解析 → `domain get`；域名接入规则 → `uni-connect`
- 查 FS 中证书记录 → `cert search`；查线上实际部署的证书 → `cert probe`。两者互补：probe 看真实状态，search 看 FS 管理状态
- 域名报备/验证/DNS TXT 记录 → `cert top-domain`，不是 `domain get`
- 证书部署到哪些集群/CDN → `cert hosting`（只读查看），不是 `uni-connect`
- 证书过期预警 → `cert expiry`；顶级域过期预警 → `cert top-domain expiry`
- "某个域名用的什么证书"：想查 FS 记录用 `cert search --domain`；想查线上实际部署用 `cert probe --domain`
- 不推荐未开放命令（scale、change、create 等）；Pod 暂停/恢复已开放，用 `host pause` / `host resume`

## 参考文档索引

只在速查表信息不够时按需读取，每次最多读一个：

- 顶层命令选型：`references/top-level-routing.md`
- 认证：`references/auth.md`
- 应用和分组：`references/app-and-app-group.md`
- 主机和诊断：`references/host.md`
- 日志查询（SLS/Pod/场景）：`references/log.md`
- 环境/工单/quota/资源：`references/env-order-quota-resource.md`
- 应用特性（trait/治理规则）：`references/trait.md`
- 证书（cert/证书搜索/托管/探测/顶级域）：`references/cert.md`
- 升级：`references/upgrade.md`
- VIP/VIP-RS：`references/vip.md`
- 跨云通道：`references/cloud-link.md`
- 统一接入：`references/uni-connect.md`
- 阿里云账号域：`references/aliyun-account-domain.md`
- 阿里云资源：`references/aliyun-resource-domain.md`
- 输出格式：`references/output-rules.md`
- 执行校验与错误恢复：`references/execution-guard.md`
