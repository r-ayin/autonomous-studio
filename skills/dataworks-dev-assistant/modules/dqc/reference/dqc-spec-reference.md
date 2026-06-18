# DQC Spec 速查（agent 生成规则时查阅）

## Spec 格式

Spec 是 YAML rules 片段，通过 `dqc_create_rule.py --spec-file` 提交。

```yaml
- assertion: row_count > 0
  name: 表行数大于0
  severity: High
  enabled: true
```

## assertion 语法

### 固定值比较

```
assertion: 指标(字段) 比较符 阈值
```

| 示例 | 说明 |
|------|------|
| `row_count > 0` | 表行数大于0 |
| `row_count > 100` | 表行数大于100 |
| `max(size) <= 500` | 最大值不超过500 |
| `avg(amount) between 100 and 300` | 均值在100-300之间 |
| `missing_count(birthday) = 0` | birthday字段无空值 |
| `missing_percent(gender) < 5%` | gender空值率<5% |
| `duplicate_count(phone) = 0` | phone无重复值 |
| `duplicate_percent(id) < 1%` | id重复率<1% |
| `distinct_count(status) between 3 and 10` | status唯一值3-10个 |
| `sum(amount) > 0` | amount求和大于0 |

### 波动检测

```
assertion: change [聚合方式] [时间窗口] [percent] for 指标(字段) 比较符 阈值
```

| 示例 | 说明 |
|------|------|
| `change 1 day ago for row_count < 10000` | 与昨天相比行数变化<10000 |
| `change 7 days ago percent for row_count < 50%` | 与7天前相比行数波动<50% |
| `change average last 7 days for row_count < 10000` | 与7天平均值相比 |

波动规则需要 warn + fail 阈值：
```yaml
- assertion: change 1 day ago and 7 days ago and 1 month ago percent for row_count
  warn:
  - when not between -10% and 10%
  fail:
  - when not between -20% and 20%
  name: 行数1/7/30天波动率
```

### 动态阈值

```yaml
- assertion: anomaly detection for row_count
  name: 行数动态阈值
```

需要至少21次历史检查记录才能生效。

### 自定义 SQL

```yaml
- assertion: "my_metric > 0"
  my_metric:
    query: "SELECT COUNT(*) FROM ${table} WHERE status IS NULL"
  name: 空状态检查
```

## 可用指标

| 指标 | 级别 | 说明 |
|------|------|------|
| `row_count` | 表 | 数据行数 |
| `table_size` | 表 | 存储大小(字节) |
| `avg(field)` | 字段 | 均值 |
| `sum(field)` | 字段 | 求和 |
| `min(field)` | 字段 | 最小值 |
| `max(field)` | 字段 | 最大值 |
| `missing_count(field)` | 字段 | 空值行数 |
| `missing_percent(field)` | 字段 | 空值占比 |
| `duplicate_count(field)` | 字段 | 重复值行数 |
| `duplicate_percent(field)` | 字段 | 重复值占比 |
| `distinct_count(field)` | 字段 | 唯一值个数 |
| `distinct_percent(field)` | 字段 | 唯一值占比 |

## 比较符

`>`, `>=`, `<`, `<=`, `=`, `!=`, `between X and Y`

## severity

- `Normal` = 弱规则（告警不阻塞）
- `High` = 强规则（阻塞产出）

## 可选字段

| 字段 | 说明 |
|------|------|
| `name` | 规则名称 |
| `severity` | Normal / High |
| `enabled` | true / false |
| `fields` | 字段列表（字段级指标需要） |
| `filter` | 数据过滤（如 `dt='$[yyyymmdd-1]'`） |
| `collectFailedRows` | true = 保留问题数据 |
| `templateId` | 使用系统模板时指定 |

## 空值自定义（把特定值也当空值）

```yaml
- assertion: missing_count(name) = 0
  missing:
    values:
      - n/a
      - NA
      - none
```

或正则：
```yaml
  missing:
    regex: "(?:N/A|null|NULL)"
```

## 限制

- 一个 Spec 只能配一张表
- MaxCompute 分区表必须指定 filter
- 波动阈值：上升告警 fail > warn > 0；下降告警 fail < warn < 0；双向用 not between
- 动态阈值需要 21 次历史记录

## 常见自然语言 → Spec 示例

| 用户说 | Spec |
|--------|------|
| 表不能为空 | `assertion: row_count > 0` + `severity: High` |
| 行数要大于100 | `assertion: row_count > 100` |
| birthday 不能有空值 | `assertion: missing_count(birthday) = 0` + `fields: [birthday]` |
| 手机号不能重复 | `assertion: duplicate_count(phone) = 0` + `fields: [phone]` |
| 金额不能为负 | `assertion: min(amount) >= 0` + `fields: [amount]` |
| 行数波动不超过10% | 用波动 assertion + `warn: when not between -0.1 and 0.1` |
| 状态值只能是 1,2,3 | `assertion: count_not_in(status) = 0` + `valid: {values: [1,2,3]}` |
