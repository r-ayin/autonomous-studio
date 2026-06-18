# 阿里云账号域说明

当用户问题落在账号体系，而不是具体某类云资源实例时，进入这个领域。

## 命令分流

### `aliyun-account`

适用于主账号或应用账号层面：

- 查账号列表：`aliyun-account list`
- 查账号详情：`aliyun-account get`

需要最新参数时，运行 `normandy aliyun-account --help` 或对应子命令 `--help`。

### `aliyun-sub-account`

适用于 RAM 子账号：

- 查询子账号列表：`aliyun-sub-account list`
- 查询子账号详情：`aliyun-sub-account get --id <cloud-id>`
- 通过 SSO 登录子账号：`aliyun-sub-account login`
- 查询子账号已绑定的权限策略：`aliyun-sub-account permission list`

#### `permission list` 参数说明

| 参数 | 说明 |
|------|------|
| `--id` | RAM 用户的 UID（长数字串，如 `200123456789012345`）。**注意**：必须使用 RAM 用户的 UID，而非 Normandy 内部映射 ID，否则会报错 `Sub-account not found`。 |
| `--trace-type` | 权限来源过滤：`all`（默认，全部）/ `self`（直接绑定）/ `user-group`（通过用户组继承） |
| `--verbose` | 展示完整的 Policy Document JSON |

**如果只知道 AK，先通过 `resource search` 反查 UID：**

```bash
# 第一步：通过 AK 找到 RAM 用户的 UID（在返回的 accounts.data[].uid 字段）
normandy resource search --query <AK> --output json

# 第二步：用 UID 查权限
normandy aliyun-sub-account permission list --id <uid> --trace-type all
```

**典型用法：**

```bash
# 查看子账号所有权限
normandy aliyun-sub-account permission list --id 200123456789012345

# 只看直接绑定的权限
normandy aliyun-sub-account permission list --id 200123456789012345 --trace-type self

# 只看通过用户组继承的权限，并展示 Policy JSON
normandy aliyun-sub-account permission list --id 200123456789012345 --trace-type user-group --verbose
```

需要最新参数时，运行 `normandy aliyun-sub-account --help` 或对应子命令 `--help`。

### `aliyun-role`

适用于 RAM 角色：

- 查询角色：`aliyun-role list` / `aliyun-role get`

需要最新参数时，运行 `normandy aliyun-role --help` 或对应子命令 `--help`。

### `aliyun-user-group`

适用于 RAM 用户组及成员：

- 查询用户组：`aliyun-user-group list` / `aliyun-user-group get`

需要最新参数时，运行 `normandy aliyun-user-group --help` 或对应子命令 `--help`。

## 什么时候不要走这里

- 用户明确问的是 ECS、RDS、Redis、OSS、Kafka 等资源实例，不要停在账号域，转去 `references/aliyun-resource-domain.md`
