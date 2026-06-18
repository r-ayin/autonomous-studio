# cert — 证书管理（Freestream）

对接 Freestream 证书管理平台，提供证书组查询、托管实例、TLS 探测、顶级域管理等**只读**能力。

---

## 子命令总览

| 子命令 | 用途 |
|--------|------|
| `cert search` | 按域名/CN/应用名搜索证书组 |
| `cert get` | 查看证书组详情（含 SAN、托管实例） |
| `cert list` | 列出我名下的证书组 |
| `cert expiry` | 证书过期预警报告 |
| `cert hosting` | 查看证书托管实例列表 |
| `cert probe` | 对域名做 TLS 建链探测，返回线上实际证书信息并关联 FS |
| `cert top-domain list` | 列出顶级域（支持 `--name`/`--all` 搜索） |
| `cert top-domain expiry` | 顶级域过期预警 |
| `cert top-domain dns-record` | 输出报备用的 DNS TXT 记录 |

---

## cert search

按域名、应用名或 CN 搜索证书组，支持组合查询。至少需提供 `--domain`、`--app-name`、`--cn` 之一。

```bash
normandy cert search --domain example.com
normandy cert search --app-name freestream
normandy cert search --cn "*.alibaba-inc.com"
normandy cert search --app-name my-app --cn example --output json
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--domain` | string | 否 | 按域名搜索（精确/通配符匹配） |
| `--app-name` | string | 否 | 按应用名过滤 |
| `--cn` | string | 否 | 按 CN 模糊搜索 |
| `--output` | string | 否 | `human`（默认）或 `json` |

---

## cert get

按证书组 ID 查看完整信息，含 SAN 域名列表和托管实例。

```bash
normandy cert get --id 14065
normandy cert get --id 14065 --output json
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--id` | int | 是 | 证书组 ID |
| `--output` | string | 否 | `human`（默认）或 `json` |

---

## cert list

列出我名下的证书组，支持多维过滤。

```bash
normandy cert list
normandy cert list --status VALID
normandy cert list --validity LESS_30
normandy cert list --app-name my-app
normandy cert list --page 2 --size 20
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--status` | string | 否 | 证书状态：`VALID`、`EXPIRED`、`REVOKED`、`INITIAL` |
| `--validity` | string | 否 | 有效期：`EXPIRED`、`LESS_30`、`BETWEEN_30_90`、`MORE_90` |
| `--app-name` | string | 否 | 按应用名过滤 |
| `--cn` | string | 否 | 按 CN 模糊搜索 |
| `--page` | int | 否 | 页码，默认 1 |
| `--size` | int | 否 | 每页条数，默认 20 |
| `--output` | string | 否 | `human`（默认）或 `json` |

---

## cert expiry

证书过期预警报告，默认展示 30 天内到期及已过期的证书。

```bash
normandy cert expiry
normandy cert expiry --days 60
normandy cert expiry --app-name my-app
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--days` | int | 否 | 预警天数，默认 30 |
| `--app-name` | string | 否 | 只看指定应用的证书 |
| `--output` | string | 否 | `human`（默认）或 `json` |

---

## cert hosting

查看某个证书组下的所有托管部署实例。

```bash
normandy cert hosting --id 14065
normandy cert hosting --id 14065 --name "selection"
normandy cert hosting --id 14065 --output json
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--id` | int | 是 | 证书组 ID |
| `--name` | string | 否 | 按资源名模糊过滤 |
| `--output` | string | 否 | `human`（默认）或 `json` |

---

## cert probe

对目标域名发起真实 TLS 握手，提取线上实际部署的证书信息，并自动用 SHA-256 指纹关联 FS 中的证书组。用于排查"线上到底用了哪张证书"以及"这张证书是否在 FS 管理"。

```bash
normandy cert probe --domain example.com
normandy cert probe --domain example.com --port 8443
normandy cert probe --domain cdn.example.com --sni origin.example.com
normandy cert probe --domain example.com --output json
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--domain` | string | 是 | 要探测的域名 |
| `--port` | int | 否 | 目标端口，默认 443 |
| `--sni` | string | 否 | TLS SNI 值，默认与 `--domain` 相同 |
| `--output` | string | 否 | `human`（默认）或 `json` |

---

## cert top-domain list

列出顶级域，支持按域名搜索、状态过滤，默认只查自己名下的。

```bash
normandy cert top-domain list
normandy cert top-domain list --name alibaba-inc.com
normandy cert top-domain list --all
normandy cert top-domain list --status ACTIVE
normandy cert top-domain list --output json
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--name` | string | 否 | 按域名搜索 |
| `--status` | string | 否 | 状态过滤：`ACTIVE`、`PENDING`、`EXPIRED`、`REVOKED` |
| `--auto-renewal` | bool | 否 | 按自动续期状态过滤 |
| `--all` | flag | 否 | 查所有人的顶级域（默认只查自己） |
| `--page` | int | 否 | 页码，默认 1 |
| `--size` | int | 否 | 每页条数，默认 20 |
| `--output` | string | 否 | `human`（默认）或 `json` |

---

## cert top-domain expiry

按过期时间排序，展示即将过期的顶级域。

```bash
normandy cert top-domain expiry
normandy cert top-domain expiry --days 60
normandy cert top-domain expiry --output json
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--days` | int | 否 | 预警天数，默认 30 |
| `--output` | string | 否 | `human`（默认）或 `json` |

---

## cert top-domain dns-record

输出指定顶级域的 DNS 验证记录。同一域名可能存在多条不同 Root 类型的记录，全部展示。

```bash
normandy cert top-domain dns-record --name alibaba-inc.com
normandy cert top-domain dns-record --name alibaba-inc.com --all
normandy cert top-domain dns-record --name alibaba-inc.com --output json
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--name` | string | 是 | 顶级域名 |
| `--all` | flag | 否 | 查所有人的（默认只查自己） |
| `--output` | string | 否 | `human`（默认）或 `json` |

---

## 路由决策指引

| 用户意图 | 推荐命令 |
|----------|----------|
| 查某域名对应哪张证书（FS 记录） | `cert search --domain` |
| 查线上实际部署了什么证书 | `cert probe --domain` |
| 查我有哪些快到期的证书 | `cert expiry` |
| 查证书部署在哪些地方 | `cert hosting --id` |
| 域名报备/DNS TXT 记录 | `cert top-domain dns-record --name` |
| 查顶级域状态和过期情况 | `cert top-domain list` / `cert top-domain expiry` |

---

## 注意事项

- `cert` 命令族**只提供读能力**，不做任何写/变更操作
- FS 平台链接格式：`https://fs.alibaba-inc.com/#/certGroupDetail/{certGroupId}`
- `cert probe` 使用 `CERT_NONE` 模式（允许探测过期/自签证书），这是有意为之——诊断场景需要能连上各种异常状态的证书
- `cert search` 至少需要 `--domain`、`--app-name`、`--cn` 之一，不能不带任何搜索条件
