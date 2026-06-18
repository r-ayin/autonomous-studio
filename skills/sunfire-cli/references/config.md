# config — 业务监控、Dashboard、升级与工具

## monitor — 自定义监控（业务监控）

监控项格式：三元组 `<tenantId> <pluginType> <pluginId>`（空格分隔），对应 URL `https://x.alibaba-inc.com/custom/<tenantId>/product/preview/<pluginType>/<pluginId>`

### monitor source/list — 从日志源发现监控项

```bash
sf monitor source list --app <APP> [--type log|sls]
sf monitor list --app <APP> --log-path <PATH> [--cursor <CURSOR>]
sf monitor list --project <PROJECT> --log-store <LOG_STORE> [--app <APP>]
```

先用 `source list` 找本地日志路径或 SLS Project/LogStore，再用 `monitor list` 获取关联监控项三元组，最后用 `monitor get/fields` 深入查看。

```bash
sf monitor source list --app sunfire-web-api
sf monitor source list --app sunfire-web-api --type sls
sf monitor list --app sunfire-web-api --log-path /home/admin/logs/app.log
sf monitor list --project my-sls-project --log-store app-log --cursor 104_SM_200
```

### monitor get — 监控项详情

```bash
sf monitor get <tenantId> <pluginType> <pluginId>
```

返回监控项的配置信息，包括：类别（本地日志/SLS）、关联应用、日志路径、SLS Project/LogStore、解析规则等。

```bash
sf monitor get 104 spm 1
```

### monitor fields — 可用字段

```bash
sf monitor fields <tenantId> <pluginType> <pluginId>
```

查看可用的指标字段和维度，用于构建查询条件。**查询时序数据前必须先调用此命令**了解有哪些字段可用。

```bash
sf monitor fields 104 spm 1
```

### 业务监控时序查询 — 使用 metric query

```bash
sf metric query '<metric_name>{<labels>}' --tenant <TENANT> [-s <START>] [-e <END>]
```

`sf monitor query` 已删除。查询业务监控时序数据时，先用 `sf monitor fields` 获取指标名和维度，再用 `sf metric query` 查询。

```bash
sf monitor fields 104 spm 1
sf metric query '104_SPM_1$成功率' --tenant sunfire_biz_juicer -s '1h ago'
```

---

## dashboard — 监控大盘

### dashboard get — 查询 Dashboard 详情

```bash
sf dashboard get <ID> [--tenant <TENANT>] [--promql]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `<ID>` | Dashboard ID（从 Sunfire 页面 URL 获取） | 必填 |
| `--tenant` | 租户 | `default` |
| `--promql` | 提取所有面板的 PromQL 查询 | false |

Dashboard ID 从 Sunfire 页面 URL 中获取：`https://sunfire.alibaba-inc.com/#!/dashboard/<ID>`

```bash
sf dashboard get 12345                         # 查看 Dashboard 配置
sf dashboard get 12345 --tenant sunfire_self   # 指定租户
sf dashboard get 12345 --promql                # 提取所有 PromQL 查询
```

---

## alarm rule — 报警规则

报警规则完整用法见 [alert.md](alert.md)。

```bash
sf alarm rule get <rule_id>                         # 获取规则 PromQL
sf alarm rule list --app <APP>                      # 查应用的规则列表
sf alarm rule status <rule_id> -s '24h ago'         # 查规则运行状态
sf alarm rule detect <rule_id> --at '5m ago'        # 单点检测
sf alarm rule detect <rule_id> -s '1h ago' -e now   # 时间范围回测
sf alarm rule create --from-file rule.yaml          # 创建规则（JSON/YAML 均支持）
sf alarm rule update <rule_id> --from-file rule.yaml # 更新规则
sf alarm rule delete <rule_id> -y                   # 删除规则（跳过二次确认）
```

---

## upgrade / doctor / version

```bash
sf upgrade    # 检查并升级到最新版本
sf doctor     # 环境诊断（检查配置、AuthX AIT/APT、OAuth、Token、连通性）
sf version    # 查看当前版本信息
```

---

## completions — Shell 自动补全

```bash
sf completions bash >> ~/.bashrc
sf completions zsh  >> ~/.zshrc
```

---

## feedback — 提交需求或 Bug

通过命令行直接创建 Aone 工作项（底层走 a1 CLI）。

```bash
sf feedback req --title "建议增加某功能" --desc "具体描述"
sf feedback bug --title "某命令崩溃" --desc "复现步骤"
sf feedback req --title "..." --from-file desc.md
```
