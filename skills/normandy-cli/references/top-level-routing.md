# 顶层命令路由

先判断用户的目标，再映射到一个最合适的顶层命令。

## 路由总原则

- 用户在问“登录、退出、状态”时，优先看 `auth`
- 用户在问“应用本身”时，优先看 `app`
- 用户在问“应用分组”时，优先看 `app-group`
- 用户在问“主机/机器/节点”时，优先看 `host`
- 用户在问“环境 stack / app-env”时，优先看 `app-env`
- 用户在问“工单/变更单/order”时，优先看 `order`
- 用户在问“扩容前 quota/可用资源”时，优先看 `quota`
- 用户在问”查日志内容（SLS 或 Pod）”时，优先看 `log`
- 用户在问”通用资源检索或按 SN 查资源实例”时，优先看 `resource`
- 用户在问"应用导入了哪些治理特性 / 限流 / 熔断 / 降级 / 灰度规则 / sentinel rule"时，优先看 `trait`
- 用户在问“怎么升级 CLI / 升级 normandy-cli”时，优先看 `upgrade`
- 用户在问”证书/SSL/TLS/HTTPS 证书/证书过期/证书续期/证书托管/TLS 探测/线上证书”时，优先看 `cert`
- 用户在问”顶级域/域名报备/域名验证/DNS TXT 记录”时，优先看 `cert top-domain`
- 用户在问”VIP / VIP RS / 域名 / 跨云通道 / 专线”时，分别落到 `vip`、`vip-rs`、`domain`、`cloud-link`、`uni-connect`
- 用户在问“阿里云账号体系”时，优先在 `aliyun-account`、`aliyun-sub-account`、`aliyun-role`、`aliyun-user-group` 中选一个
- 用户在问“具体某类阿里云资源”时，落到对应的 `aliyun-*` 顶层命令

## 容易混淆的分流

### `app` vs `app-group` vs `host`

- 查应用概况、应用资源汇总，用 `app`
- 查某个应用分组详情或列表，用 `app-group`
- 查具体主机、按主机条件过滤、登录主机，用 `host`

### `resource` vs `aliyun-*`

- 用户只知道关键字或只想“先搜一下 Normandy 资源”，用 `resource search`
- 用户已经明确资源类型，例如 ECS、RDS、Redis、OSS、Kafka，优先用对应的 `aliyun-*`
- 用户手里只有资源 SN，且不确定类型，可先用 `resource get`

### `upgrade` vs 业务命令

- 用户要升级 Normandy CLI 本身，用 `upgrade`
- 用户要查业务资源或发起业务查询，不要误路由到 `upgrade`

### `order` vs 变更命令

- 用户要"查工单状态/详情/列表"，用 `order`
- 用户要"暂停/恢复 Pod"，用 `host pause` / `host resume`；pause 默认 30 分钟，默认检查 `main` 容器，若用户指定 `--container` 则检查该目标容器的 ready 状态
- 用户要"发起重启/置换等动作"，目前不通过 CLI 支持，建议引导用户使用 Normandy 平台 Web 界面

### `log` vs `aliyun-sls-*` vs `host path` vs `host get --yaml`

- 用户要查日志内容（SLS logstore 里的日志条目或 Pod 文件内容），用 `log list`
- 用户要查 SLS 资源元信息（project/logstore 的配置、详情），用 `aliyun-sls-project` 或 `aliyun-sls-logstore`
- 用户要浏览容器内目录结构（看有哪些文件），用 `host path`
- 用户要查某台机器对应 Pod 的原始 YAML，用 `host get --host <sn|ip|hostname> --yaml`
- 典型组合：先 `host path` 找文件 → 再 `log list --source pod` 读内容

### `trait` vs `app summary` vs `log`

- 用户要查"应用导入的治理规则元数据（特性/降级/灰度规则本身、谁建的、什么版本）"，用 `trait list --app-name`
- 用户要查"应用资源汇总（机器/VIP/quota 总量）"，用 `app summary`，不是 `trait list`
- 用户要查"运行时被限流/降级的具体记录"，用 `log list`，trait 不查运行时事件
- trait 默认只看 `AFTER_VERSIONOUT` 阶段，如果用户想看出版本时生效的，需追加 `--trait-effective-stage-filter DURING_VERSIONOUT`

### `auth` vs 其他命令

- 用户问题是“怎么登录、怎么看当前是否已登录、怎么退出”，用 `auth`
- 用户只是要执行某个业务命令，不要自动把答案切到 `auth`，除非确实需要提醒前置认证

### `cert` vs `domain` vs `uni-connect`

- 用户要查"某域名对应的证书、证书是否在 FS 管理"，用 `cert search` 或 `cert probe`
- 用户要查"域名基础信息/解析"，用 `domain get`
- 用户要查"域名接入规则/路由配置"，用 `uni-connect`
- 用户要查"域名报备/验证/DNS TXT"，用 `cert top-domain dns-record`

## 网络类命令

- `vip`：VIP 资源本身
- `vip-rs`：VIP 绑定的 Real Server
- `domain`：域名资源
- `cloud-link`：跨云链路
- `uni-connect`：统一接入/专线类资源
- `cert`：证书管理（Freestream 平台）

领域路由和分流规则请先读取：

- VIP / VIP-RS：`references/vip.md`
- 跨云通道：`references/cloud-link.md`
- 统一接入：`references/uni-connect.md`
- 证书：`references/cert.md`

详细命令语法请直接运行对应命令的 `--help`。

## 领域参考文档入口

当确定了顶层命令后，进一步读取对应的领域参考文档：

- 认证：`references/auth.md`
- 应用和应用分组：`references/app-and-app-group.md`
- 主机：`references/host.md`
- 环境、工单、quota、通用资源：`references/env-order-quota-resource.md`
- 应用特性（trait/治理规则）：`references/trait.md`
- CLI 升级：`references/upgrade.md`
- 证书（cert/证书/托管/探测/顶级域）：`references/cert.md`
- 网络类（VIP、域名、专线等）：`references/vip.md`、`references/cloud-link.md`、`references/uni-connect.md`
- 阿里云账号域：`references/aliyun-account-domain.md`
- 阿里云资源：`references/aliyun-resource-domain.md`

## 详细命令语法入口

- 认证：`normandy auth --help`
- 应用：`normandy app --help`
- 应用分组：`normandy app-group --help`
- 应用环境：`normandy app-env --help`
- 主机：`normandy host --help`
- 工单：`normandy order --help`
- Quota：`normandy quota --help`
- 通用资源：`normandy resource --help`
- 日志：`normandy log --help`
- 应用特性：`normandy trait --help` / `normandy trait list --help`
- 升级：`normandy upgrade --help`
- VIP：`normandy vip --help`
- VIP RS：`normandy vip-rs --help`
- 域名：`normandy domain --help`
- 跨云链路：`normandy cloud-link --help`
- 统一接入：`normandy uni-connect --help`
- 证书：`normandy cert --help`
- 顶级域：`normandy cert top-domain --help`
