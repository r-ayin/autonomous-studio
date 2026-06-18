# app-env / order / quota / resource 领域说明

这些命令都偏查询，但关注点不同。

## `app-env`

适用于：

- 按应用或应用分组查环境
- 已知 `stack-id` 查环境详情

需要最新参数时，运行 `normandy app-env --help` 或对应子命令 `--help`。

## `order`

适用于：

- 查工单详情：`order get`
- 查工单列表：`order list`

当用户说“工单状态、提单结果、历史工单、某个 order id”，优先落到这里。

需要最新参数时，运行 `normandy order --help` 或对应子命令 `--help`。

## `quota`

适用于：

- 查询扩容前可用 quota
- 想知道某个应用分组还有多少可用资源

需要最新参数时，运行 `normandy quota --help` 或对应子命令 `--help`。

## `resource`

适用于：

- 类型不明、只有关键词时的探索性搜索：`resource search --query <keyword>`
- 已知资源 SN，查看资源详情：`resource get --sn <sn>`

### `resource search` 搜索范围

`search` 同时调用三个后端 API，结果分三个区块展示：

| 区块 | 搜索范围 |
|------|----------|
| 主结果 | Normandy 平台全局（应用、主机、分组、VIP、域名等） |
| `--- Resources ---` | 云资源实例（ECS、RDS、Redis 等），按名称/标识模糊匹配 |
| `--- Accounts ---` | 阿里云账号体系，`searchType=ALL` 时同时搜索以下四类，结果按 `searchResultType` 分组展示：<br>• `MASTER`：主账号（云厂商账号）→ 深入查询用 `aliyun-account get --scene-type CLOUD_ACCOUNT`<br>• `RAM_USER`：子账号，支持按 AccessKey ID 反查 → 深入查询用 `aliyun-sub-account get --id <cloud-id>`<br>• `RAM_ROLE`：阿里云角色 → 深入查询用 `aliyun-role get`<br>• `ACCOUNT`：内部应用账号 → 深入查询用 `aliyun-account get --scene-type APPLICATION_ACCOUNT`<br>注：`RAM_GROUP`（用户组）不在 ALL 搜索范围内 |

**关键参数：**

- `--query`：必填，搜索关键词（支持名称、IP、AK ID 等）
- `--output json`：返回三个 API 的完整原始数据，适合脚本处理
- `--verbose`：在 stderr 输出诊断信息

**注意：** 主结果区块 0 条不代表整体无结果，账号区块可能仍有匹配（如按 AK 反查到持有该 AK 的子账号）。

当用户还没明确资源类型，或者只是想先搜一把，优先用 `resource search`。类型已明确（如 ECS、RDS）则直接用对应 `aliyun-*` 命令。

需要最新参数时，运行 `normandy resource --help` 或对应子命令 `--help`。

## 常见分流

- “查工单”不是 `resource`
- “查资源 quota”不是 `resource`
- “已知是 ECS/RDS/Redis/OSS 等阿里云资源”优先转去 `references/aliyun-resource-domain.md`
