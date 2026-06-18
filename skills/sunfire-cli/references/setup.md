# Setup — sf CLI 安装与鉴权

## 安装

```bash
# 最新正式版
curl -sSL https://sealeaf.oss-cn-hangzhou-zmf.aliyuncs.com/sunfire-cli/install.sh | sh

# 指定版本安装
curl -sSL https://sealeaf.oss-cn-hangzhou-zmf.aliyuncs.com/sunfire-cli/install.sh | sh -s -- --version 0.2.3

# 安装测试版
curl -sSL https://sealeaf.oss-cn-hangzhou-zmf.aliyuncs.com/sunfire-cli/install.sh | sh -s -- --channel test
```

### 验证安装

```bash
sf --version
```

---

## 鉴权

v0.2.3 默认优先使用 AuthX / NCS 自动获取身份。阿里郎和 Aone sandbox 环境通常无需先执行登录，先检查认证状态即可。

v0.2.3 prefers AuthX / NCS for automatic identity. In Alilang and Aone sandbox environments, check status first instead of asking the user to log in immediately.

```bash
sf auth status   # 检查当前认证状态（AuthX / Token / OAuth fallback）
sf auth login    # 仅在 AuthX/NCS 不可用且无 fallback 时配置 BUC OAuth fallback
sf auth token set <TOKEN>    # 保存自定义 Token（长期运行服务或 CI/CD 场景）
sf auth token status         # 查看自定义 Token 配置状态（不显示 Token 值）
sf auth token clear          # 清除 profile 自定义 Token
sf auth switch <PROFILE>     # 切换当前 profile
sf auth list                 # 列出所有 profile
sf auth logout   # 登出
```

判断规则：

- `sf auth status` 显示 AuthX / NCS 或 Token 可用 → 直接执行查询命令。
- `sf auth status` 显示 AuthX/NCS 不可用且没有可用 Token/OAuth → 再运行 `sf auth login`。
- 如果用户提供 `--token` 或 `SUNFIRE_OMNI_TOKEN`，它们优先于自动身份。

---

## 全局选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `-f, --format` | 输出格式：`json` / `table` / `csv` / `yaml` / `value` / `ascii` | `json` |
| `--profile` | 认证 profile | `default` |
| `--token` | 直接传入自定义 Token（sf\_/sfp\_ 前缀的 Admin/PAT Token），优先级: --token > SUNFIRE_OMNI_TOKEN 环境变量 > OAuth credentials | - |
| `--timezone` | 时区（用于时间解析） | `Asia/Shanghai` |
| `-v, --verbose` | 详细输出（`-v` 请求行/脱敏认证头/状态码，`-vv` 完整请求/响应头/body） | - |
| `-q, --quiet` | 静默模式，仅输出数据 | - |
| `--timeout` | HTTP 超时（秒） | `30` |

## 智能时间解析

所有 `-s` / `-e` 参数支持：

```
"1h ago"  "30m ago"  "3d ago"  "now"  "2026-03-26 10:00:00"  Unix时间戳（秒）
```

---

## 应用信息

### app get — 应用概览

```bash
sf app get --app <APP>
```

返回监控项类别 + 云资源汇总 + 近 1h 报警数 + 健康状态。

```bash
sf app get --app sunfire-web-api
```

### app resources — 云资源与中间件实例

```bash
sf app resources --app <APP> [-t <TYPE>]
```

```bash
sf app resources --app sunfire-web-api          # 查看所有云资源
sf app resources --app sunfire-web-api -t SLS   # 仅查看 SLS 资源
```

### app host get — 机器信息

```bash
sf app host get <IP>                            # 单 IP 查询
sf app host get 33.61.169.216,11.22.33.44       # 多 IP 逗号分隔
```

### app group / host list — 分组与主机列表

```bash
sf app group list --app <APP>                   # 查询应用的所有分组
sf app host list --app <APP>                    # 查询应用下的主机列表
sf app host list --app <APP> --group <GROUP> --limit 50
sf app host list --app <APP> --group <GROUP> --group-by site
```
