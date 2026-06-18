# alert — 报警管理

## 子命令速查

| 子命令 | 说明 |
|--------|------|
| `alarm list` | 查询报警事件列表（最近 30 天内有效） |
| `alarm get` | 查询单条报警详情 |
| `alarm stat` | 按时间段统计报警数量 |
| `alarm claim` | 接手报警事件（标记由指定人员处理） |
| `alarm resolve` | 完结报警事件（标记报警已处理完毕） |
| `alarm rule get` | 查询报警规则配置与 PromQL |
| `alarm rule list` | 按应用查询报警规则列表 |
| `alarm rule create` | 通过 JSON/YAML 创建报警规则 |
| `alarm rule update` | 通过 JSON/YAML 更新报警规则 |
| `alarm rule delete` | 删除报警规则 |
| `alarm rule detect` | 规则检测（单点检测或时间范围回测） |
| `alarm rule status` | 查看规则运行状态历史（ALERT/OK/NO_DATA） |

---

## alarm list — 报警列表

```bash
sf alarm list [options]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--app` | 应用名过滤 | - |
| `--rule-id` | 报警规则 ID 过滤 | - |
| `--level` | 报警级别：`warning` / `critical` / `urgent` | - |
| `--emp-id` | 按接收人工号过滤 | - |
| `--ip` | 按 IP 过滤（逗号分隔多个），CLI 本地遍历 alarmTags 匹配 | - |
| `--group` | 按应用分组过滤（逗号分隔多个），CLI 本地遍历 alarmTags 匹配 | - |
| `--tag-value` | 按 alarmTags tagValue 过滤（精确匹配，逗号分隔多个） | - |
| `-s, --start` | 开始时间 | `24h ago` |
| `-e, --end` | 结束时间 | `now` |
| `-n, --limit` | 最多返回多少条报警事件（别名：`-L`） | `20` |
| `-p, --page` | 分页编号（从 1 开始） | `1` |

返回字段含 `total`（总数）和 `has_next`（是否有下一页），可自动翻页。

**示例：**

```bash
# 查最近 24h 全局报警
sf alarm list -s '24h ago' -n 10

# 按应用过滤
sf alarm list --app sunfire-web-api -s '24h ago'

# 只看 critical 级别
sf alarm list --app sunfire-web-api --level critical -s '24h ago'

# 查某人收到的报警（按工号）
sf alarm list --emp-id 291194 -s '24h ago'

# 按报警规则 ID 过滤
sf alarm list --rule-id 213667367 -s '24h ago'

# 按 IP 过滤（如查某台机器的报警）
sf alarm list --app sunfire-web-api --ip 33.8.139.111 -s '24h ago'

# 按分组过滤
sf alarm list --app sunfire-web-api --group share1 -s '24h ago'

# 表格格式人类可读
sf alarm list --app sunfire-web-api -s '24h ago' -f table

# 分页
sf alarm list --app sunfire-web-api -s '7d ago' -n 20 --page 2

# 脚本：判断是否有报警
COUNT=$(sf alarm list --app sunfire-web-api -s '1h ago' -f value)
[ "$COUNT" = "0" ] && echo "无报警" || echo "有 $COUNT 条报警"
```

---

## alarm get — 报警详情

```bash
sf alarm get <alarm_id> [-s <START>] [-e <END>]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `<alarm_id>` | 报警 ID（散列值格式） | 必填 |
| `-s, --start` | 查询窗口起始时间 | 最近 30 天 |
| `-e, --end` | 查询窗口结束时间 | `now` |

`alarm_id` 从 `alarm list` 结果中的 `alarm_id` 字段获取。返回完整报警内容，含 `alarm_rule_id` 字段（可用于 `alarm rule get`）。

```bash
sf alarm get 5b2bc9a1ab824f6f83d381afd49458e8
sf alarm get 5b2bc9a1ab824f6f83d381afd49458e8 -s '60d ago'  # 扩大查询窗口
```

---

## alarm stat — 统计

```bash
sf alarm stat [--app <APP>] [--level <LEVEL>] [--emp-id <EMP_ID>] [-s <START>] [-e <END>] [--group-by <DIM>]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--group-by` | 分组维度：`app` / `level` / `rule`（仅支持单个） | - |

```bash
# 最近 7 天报警统计
sf alarm stat --app sunfire-web-api -s '7d ago'

# 按级别聚合
sf alarm stat -s '7d ago' --group-by level

# 按应用聚合
sf alarm stat -s '7d ago' --group-by app
```

---

## alarm claim — 接手报警事件

```bash
sf alarm claim <alarm_id> --emp-id <EMP_ID>
```

标记某个报警事件由指定人员接手处理。

```bash
sf alarm claim 5b2bc9a1ab824f6f83d381afd49458e8 --emp-id 111413
```

---

## alarm resolve — 完结报警事件

```bash
sf alarm resolve <alarm_id> [--reason <REASON>] [--emp-id <EMP_ID>]
```

标记报警事件已处理完毕。

```bash
sf alarm resolve 5b2bc9a1ab824f6f83d381afd49458e8                                      # 无附加说明
sf alarm resolve 5b2bc9a1ab824f6f83d381afd49458e8 --reason '已定位并修复' --emp-id 111413  # 带原因完结
```

---

## alarm rule — 报警规则分析

### alarm rule get — 查规则完整配置

```bash
sf alarm rule get <rule_id>
```

`rule_id` 从 `alarm list` 返回的 `alarm_rule_id` 字段或 `alarm rule list` 返回的 `id` 字段获取。

### alarm rule list — 查应用规则列表

```bash
sf alarm rule list --app <APP> [-p <PAGE>] [-n <PAGE_SIZE>]
```

```bash
sf alarm rule list --app sunfire-web-api
```

### alarm rule create/update/delete — 规则 CRUD

```bash
sf alarm rule create --from-json '<JSON>'
sf alarm rule create --from-file alert_rule.json
sf alarm rule create --from-file alert_rule.yaml
sf alarm rule create --from-yaml "$(cat alert_rule.yaml)"

# 更新规则：alertDTO 必须包含 id 字段，operator 由服务端从 OAuth token 提取
sf alarm rule update <rule_id> --from-file alert_rule.yaml
sf alarm rule update <rule_id> --from-json '<JSON>'

# 删除规则：只能删除自己创建且有权限的规则；-y 跳过二次确认
sf alarm rule delete <rule_id> -y
```

`create` / `update` 支持 `--from-json`、`--from-yaml`、`--from-file`，文件扩展名 `.yaml` / `.yml` 自动按 YAML 解析，其他默认 JSON。

### alarm rule detect — 单点检测 / 区间回测

```bash
sf alarm rule detect <rule_id>                   # 单点检测，默认当前时间往前 2 分钟
sf alarm rule detect <rule_id> --at '5m ago'     # 在指定时间点检测
sf alarm rule detect <rule_id> -s '1h ago' -e '2m ago'  # 区间回测
sf alarm rule detect --from-file rule.yaml -s '2h ago' -e '30m ago'
```

单点模式使用 `--at`；区间模式使用 `--start/-s`、`--end/-e`，两种模式互斥。`rule_id`、`--from-json`、`--from-yaml`、`--from-file` 四选一。

### alarm rule status — 运行状态历史

```bash
sf alarm rule status <rule_id> [-s <START>] [-e <END>]
```

查询规则在指定时间段内的每分钟运行状态（ALERT/OK/NO_DATA）。

```bash
sf alarm rule status 395 -s '24h ago'
sf alarm rule status 395 -s '7d ago'
```

## 典型工作流：报警 → 规则分析

```bash
# 1. 查报警列表，拿到 alarm_rule_id
sf alarm list --app myapp -s '24h ago' -n 5

# 2. 查报警详情（可选，查看完整报警内容）
sf alarm get <alarm_id>

# 3. 查规则完整配置（了解 PromQL、触发条件）
sf alarm rule get <alarm_rule_id>

# 4. 查规则运行状态历史（评估误报率）
sf alarm rule status <alarm_rule_id> -s '7d ago'

# 5. 回测验证
sf alarm rule detect <alarm_rule_id> -s '1h ago' -e '2m ago'

# 6. 接手并处理报警事件
sf alarm claim <alarm_id> --emp-id <your_emp_id>

# 7. 处理完毕后完结
sf alarm resolve <alarm_id> --reason '已修复根因'
```
