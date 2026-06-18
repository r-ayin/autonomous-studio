# 动态 aliyun-* 资源命令说明

当用户已经明确资源类型，或者语义上明显对应某类阿里云资源时，进入这个领域。

## 资源类型到顶层命令的映射

- ECS 实例：`aliyun-ecs`
- ECS 磁盘：`aliyun-ecs-disk`
- RDS：`aliyun-rds`
- Redis：`aliyun-redis`
- OSS：`aliyun-oss`
- Kafka：`aliyun-kafka`
- PolarDB：`aliyun-polardb`
- Elasticsearch：`aliyun-elasticsearch`
- ClickHouse：`aliyun-clickhouse`
- HBase：`aliyun-hbase`
- Lindorm：`aliyun-lindorm`
- DTS：`aliyun-dts`
- MSE：`aliyun-mse`
- OTS：`aliyun-ots`
- GDB：`aliyun-gdb`
- CDN：`aliyun-cdn`
- NAS 文件系统：`aliyun-nas-filesystem`
- NLB：`aliyun-nlb`
- NLB Listener：`aliyun-nlb-listener`
- ONS Group：`aliyun-ons-group`
- ONS Topic：`aliyun-ons-topic`
- ADB：`aliyun-adb`
- ADB Lake：`aliyun-adb-lake`
- ADBPG：`aliyun-adbpg`
- SLS Project：`aliyun-sls-project`
- SLS Logstore：`aliyun-sls-logstore`

## 选择规则

- 用户明确说出资源类型时，直接选对应 `aliyun-*`
- 用户只给了资源 ID 但没说类型，先看是否能从上下文确定类型；不能确定就退回 `resource`
- 用户问题是账号、角色、子账号、用户组，不要留在资源域，转去 `aliyun-account-domain.md`
- 大多数动态资源命令至少有 `get` / `list`；很多命令还支持 `login`
- `aliyun-sls-project` 和 `aliyun-sls-logstore` 还支持 `sts-token`

## 进一步确认

需要查看具体子命令或参数时，直接运行对应命令的 `--help`，例如：

- `normandy aliyun-ecs --help`
- `normandy aliyun-rds get --help`
- `normandy aliyun-redis list --help`
- `normandy aliyun-oss get --help`
- `normandy aliyun-kafka --help`
- `normandy aliyun-nlb-listener --help`
- `normandy aliyun-sls-logstore sts-token --help`
