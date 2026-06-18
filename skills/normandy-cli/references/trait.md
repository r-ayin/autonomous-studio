# trait 领域说明

当用户明确在问"应用导入了哪些特性 / 治理规则"时，进入这个领域。Normandy 中的 trait（特性）= 应用层面的资源对象治理规则，例如限流（sentinel.flow.rule）、熔断、降级、灰度等。

## 选命令规则

- 查某个应用已导入的全部特性：`trait list --app-name <app>`
- 按平台过滤特性：追加 `--platform <name>`（如 `aone`）
- 切换生效阶段：`--trait-effective-stage-filter AFTER_VERSIONOUT`（默认，出版本后生效）或 `DURING_VERSIONOUT`（出版本时生效）
- 排除老特性：`--no-including-legacy`（默认包含）
- 包含系统特性：`--including-system`（默认不含）
- 脚本/AI 场景：追加 `--output json`，保留 API 原字段名（id、traitKey、formData、matchScope 等），可被 `jq` 直接处理

## 什么时候优先 `trait`

- 用户在问"应用 X 启用了哪些限流/熔断/降级/灰度规则"
- 用户在问"sentinel rule / hystrix rule / 治理规则 / 规则元数据"
- 用户提到"特性导入清单"、"trait list"、"trait import"、"应用层规则"
- 用户在排查 "为什么这个应用有这条 rule"，想看 creator/modifier/版本/时间戳
- 用户想用脚本批量获取应用的特性配置（用 `--output json`）

## 什么时候不要优先 `trait`

- 用户问的是"应用本身的资源汇总（机器/VIP/quota）" → 用 `app summary`，不是 `trait list`
- 用户问的是"应用基本信息（owner/git/部署单元）" → 用 `app get`
- 用户问的是"日志里命中的限流记录" → 用 `log list`，trait 只查规则本身的元数据，不查运行时事件
- 用户问的是"机器异常/诊断事件" → 用 `host diagnose`
- 用户问的是"VIP/域名/接入配置" → 走 `vip` / `domain` / `uni-connect`
- 用户想"新增/修改/删除特性" → 目前 CLI 不支持，引导用户去 Normandy Web 控制台

## 默认过滤行为提醒

- 默认 `--trait-effective-stage-filter` 是 `AFTER_VERSIONOUT`（只看出版本后生效的）。如果用户怀疑"为什么少了某条 rule"，先确认是否需要切到 `DURING_VERSIONOUT`。
- 默认 `--including-legacy=true`、`--including-system=false`。系统特性需显式 `--including-system` 才会出现。
- `--app-name` 必填，空字符串会被立即拒绝（不发请求）。

## 输出结构提示

- human 模式：表头展示查询元信息（应用名/平台/阶段/总数），每条特性占一行表格，行下追加两行 `Match Scope` 与 `Form Data`；`isDeleted=Y` 的特性会在 `特性Key` 列尾追加 `[DELETED]` 标注。
- 空列表（API 返回 `[]` 或 `null`）显示 `No traits imported.`，退出码 0，非错误。
- JSON 模式：直接输出 API `data` 数组，字段名保留 API 原命名（驼峰），完整保留 `formData` / `matchScope` 嵌套结构。

## 进一步确认

- 需要最新参数或别名时，运行 `normandy trait --help` 或 `normandy trait list --help`
