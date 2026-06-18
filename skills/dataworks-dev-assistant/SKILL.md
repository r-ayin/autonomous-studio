---
name: dataworks-dev-assistant
version: 0.19.0
description: DataWorks 助手 —— 操作 DataWorks 平台的 agent skill。搜表、查血缘、看代码、任务运维、数据集成、治理、质量检查。当用户提到以下任何内容时必须使用本 skill：表、搜表、血缘、分区、上下游、数据来源、任务、我的任务、任务列表、任务有哪些、失败实例、运行情况、运维、巡检、重跑、终止、强制终止、杀实例、冻结任务、解冻任务、批量重跑失败、工作流重跑、告警、告警诊断、报错、调度失败、节点、节点代码、代码、源码、查代码、工作空间、项目列表、同步任务、DI、数据集成、数据源、SQL执行、补数据、冒烟测试、基线、甘特图、治理、治理评分、扫描器、资源治理、质量、DQC、规则、专辑、数据资产。即使用户只说了”任务”或”我的任务有哪些”也应触发本 skill。当工作目录存在 bff_client.py 或 .dataworks/session_state.json 时也应优先加载本 skill。所有写操作必须先请求用户确认，收到”确认”后才能执行。
x-source: aone-open
repository: https://code.alibaba-inc.com/qunbu/dataworks-dev-assistant
---


# DataWorks 助手

> version: 0.2.15

> **零复制**：所有脚本直接从 skill 目录运行，无需复制文件。`<skill-path>` 指本 skill 安装目录。
> **首次使用**：`pip install -r <skill-path>/requirements.txt`（Python >= 3.8）
>
> **用户需手动配置** `~/.dataworks/.env` 文件（agent 不要创建或修改此文件）：
```
# 方式1：直接指定 endpoint（优先级更高）
BFF_ENDPOINT=你的BFF地址

# 方式2：通过环境名指定（从字典查找）
BFF_ENV=cn-beijing

BFF_TOKEN=your_token_here
```
⚠️ **endpoint 必须明确配置**。若用户未提供，请询问用户正确的 endpoint 或环境名。

**可用环境名**（BFF_ENV）：cn-hangzhou、cn-shanghai、cn-beijing、cn-shenzhen、cn-guangzhou、cn-chengdu、cn-hongkong、ap-southeast-1（新加坡）、ap-northeast-1（东京）等。完整列表见 `<skill-path>/core/references/endpoints.json`。支持中文别名：北京、上海、杭州、新加坡等。

Token 获取：用户访问 https://dw.alibaba-inc.com/dmc/skill-auth 获取 token，写入 `~/.dataworks/.env`：
```
BFF_TOKEN=<token>
BFF_ENDPOINT=http://bff.dw.alibaba-inc.com
```

> **会话 ID**：所有脚本通过 `telemetry.py` 自动生成并持久化到 `.dataworks/current_session`（30 分钟空闲后切新会话），**不要手动 export DW_BFF_SESSION_CODE**。
>
> **异步任务检查**：若 `.dataworks/backlogs.json` 存在，先运行 `PYTHONPATH=<skill-path>/core python <skill-path>/core/check_backlogs.py --list` 告知用户有哪些异步任务待查看，再处理当前问题。

## 开发习惯管理

### 启动时读取

每次 skill 激活后**第一次处理用户问题时**，用 Read 工具读取 `~/.dataworks/dev_habits.md`（若文件存在）。文件不存在则静默跳过，**不要创建空文件**。读取到的习惯规则在后续所有操作中优先遵循（优先级高于 SKILL.md 默认行为）。

### 会话中观察习惯信号

以下信号出现时，在内部标记「本次会话发现潜在习惯」，不要打断当前操作：

| 信号类型 | 示例 |
|---------|------|
| 用户纠正操作方式 | "不要用 --days"、"应该用 --start/--end" |
| 用户表达偏好/规范 | "以后"、"下次"、"统一用"、"规范是" |
| 非显而易见的方案被验证 | 第二次在同类场景主动应用并成功 |
| 用户接受某写法未纠正 | 含蓄认可，但该写法不是 SKILL.md 默认 |

### 里程碑后评估

以下任意事件完成后，在**本次回复末尾**评估是否有值得记录的习惯：

- 节点发布到生产成功（deploy_node.py --confirm-prod 完成）
- 补数据提交成功（backfill_node.py --confirm 完成）
- UDF 部署成功（deploy_udf.py 全流程完成）
- 数据集成任务创建成功
- DQC 规则批量创建成功
- 告警诊断完成并给出结论

**评估三问**（内部判断，全否则不提）：
1. 本次有用户纠正或偏好表达？
2. 遇到了 SKILL.md 未记录的非显然陷阱/技巧？
3. 规律可泛化（不只适用于本次特定节点/表）？

若 ≥1 项为是，在回复末尾追加：

```
---
💡 **发现可记录的开发习惯**
- [规则1，≤2 行]
- [规则2，≤2 行]

是否写入 `~/.dataworks/dev_habits.md`？回复「记录」即可。
```

### 写入与格式

用户回复「记录」后：
1. 若文件不存在，先创建（Write 工具）：
```markdown
# DataWorks 开发习惯

> 由 dataworks-dev-assistant skill 自动管理。可手动编辑。
```
2. 在文件末尾追加（Edit 工具）：
```markdown

### YYYY-MM-DD
- [规则1]
- [规则2]
```
3. 追加后用 Read 工具确认内容正确，告知用户写入成功。

**什么该写、什么不该写：**
- ✅ 操作规范（补数据必须 --start/--end、SCD 表必须加时间范围）
- ✅ 平台陷阱（哪个 API 有什么坑）
- ✅ SQL 约定（别名规则、日期函数偏好）
- ❌ 个人工作空间名称、项目名、表名（不可泛化）
- ❌ 一次性配置值（nodeId、taskId 等）
- ❌ 已在 SKILL.md 中明确记录的规则（不重复）

## 意图路由

> 收到用户问题后，在此表中匹配意图，直接执行对应方式。
> **兜底规则**：用户只给了一个关键字（如"查下 X"、"X 是什么"）且无法确定是表、节点还是其他类型时，直接用 `identify.py` 作为统一入口——它会自动判断类型并返回完整档案。

| 用户说 | 执行方式 |
|-------|---------|
| 表分区、历史产出、有没有数据、产出情况、今天有数据吗、数据到了吗、最新数据是哪天的、产出到几号了、数据更新到哪天了、数据不对、表数据质量有问题、数据异常、字段值不对、数据分区、最新分区、查分区、看分区、分区产出 | `python <skill-path>/modules/discovery/scripts/query_partitions.py "表名关键字"` → 两种模式： - 默认（不传 --latest-only）：全量分区概况 — 总数、时间范围、各维度值数、最近 14 天每日产出、停产检测。适合排查「数据质量问题 / 产出停了 / 断档」。内部会拉全量分区走 DuckDB 分析，大表（2w+ 分区）开销较大。 - --latest-only：快路径 — 单次 GET /dma/listPartitions_2 取最新分区（不拉全量，不进 DuckDB）。用户只问「最新分区是哪个 / 最新数据是几号 / 产出到几号了」时走这个。输出包含最新日期和各维度枚举。 |
| 血缘、上下游、数据从哪来的、数据流向哪、谁在用这个表 | `python <skill-path>/modules/discovery/scripts/query_lineage.py "表名关键字"` → 输出上下游血缘 |
| 查表、搜表、找表、表在哪、表详情、这个表是什么、查节点、搜节点、找节点、节点详情、节点档案、这个节点是什么、查任务、查任务ID、这个任务是什么、查代码、看代码、查工作空间、工作空间详情、entityId是什么、taskId是什么、nodeId是什么、实例是哪个节点、发布历史、版本历史、变更历史、版本diff、谁改过、这张表、分析表结构、分析这个表、帮我查下这张表、查下表、查看表 | `python <skill-path>/modules/discovery/scripts/identify.py "表名、节点名、nodeId、instanceId 或 entityId"` → 统一查询入口，给任意线索自动识别类型并返回完整档案 + 下一步命令。不需要 --project-id，脚本自动定位。 `--deep` 展开健康/时效/质量/变更历史（用户问发布/版本/变更历史时自动加）。 `--show-code` 输出代码（默认运行态，配 `--dev` 查开发态）。 |
| 我的表、我owner的表、我拥有的表、我负责的表、找出所有我owner的表、我的所有表、列出我的表、谁拥有这张表、某人的表、owner是谁、高频访问表、热表、热门表、最常访问的表、访问最多的表、读最多的表、TOP表、哪些表用得最多、空间下有哪些表、项目下有哪些表、工作空间下的表、列出空间的表、最大的表、最近修改的表、我有权限的表、我有哪些有权限的表、我有管理权限的表、有权限的表、我能访问的表、我的odps表 | `python <skill-path>/modules/discovery/scripts/search_table.py` → 按 owner / workspace / 时间维度搜表。与 my_data_assets.py 区别：本脚本走 searchTables API（owner 字段精确过滤），my_data_assets 走专辑维度。"我的表" 类用 `--owner self`。 核心 flag：`--owner {self|baseId}` / `--workspace <名>` / `--since 7d|24h|YYYY-MM-DD` / `--sort {accessTimes,gmtModified,dataSize}` / `--group-by {owner,workspace,type}`。 ⚠️ searchTables 服务端 offset 硬上限 200，分布统计基于前 200 条样本；真全量或剔除 tmp_* 请改用 `listTablesByDB`（见 api-index.json）。 ⚠️ `--sort` 不接受 readCount（热表用 accessTimes）。 |
| 谁产出的、产出节点、计算节点、哪里产出的、最后谁改的、谁在维护这个表、最近变更节点、最近变更的节点、最近修改的节点、最近变更诊断、变更review、我最近改了什么、谁最近改了什么、最近新建节点、最近新增节点、最近创建的节点、本周新增节点、本周创建了多少节点、新建了多少节点、创建人分布、按创建人统计、节点创建人、哪个任务产出、哪个odps任务、产出这张表的任务、源表的任务、同步到哪个任务、找同步任务、产出xxx的任务 | `python <skill-path>/modules/discovery/scripts/search_nodes.py` → 从表名/节点名定位节点，或 `--recent` 扫工作空间最近变更。表名未命中 fallback 到节点名直搜。 `--scope {runtime,dev}`：runtime（默认）只扫已发布调度；**dev 含未发布草稿**，用户问"新建/修改了多少"要的是开发活动时用 dev。 `--by {modify,create}` / `--hours` / `--my-changes` / `--my-owned`。 ⚠️ 用户问「多少 / 谁做的 / 分布」务必加 `--group-by owner`——跳过 entityId 反查（避免 100+ 节点串行卡死），直接返回总数+按人分布（工号去重）。 stdout 给出 dgc_check_nodes.py / find_node_code.py 的下一步命令。 |
| 我的数据资产、我的专辑、数据专辑、推荐专辑 | `python <skill-path>/modules/discovery/scripts/my_data_assets.py` |
| 使用说明、表说明、wiki、查wiki、表介绍、表文档、添加使用说明、编辑使用说明、更新wiki、写使用说明、AI说明、表的使用说明、查看使用说明 | `python <skill-path>/modules/discovery/scripts/table_wiki.py show "表名关键字"` → 查看表的使用说明（人工 wiki + AI 生成说明）。`--ai-only` 只看 AI 说明；`--human-only` 只看人工编写说明。`--entity-id odps.项目名.表名` 直接指定 entityId 跳过搜索（跨工作空间表必须用此参数）。写入/更新使用说明：`table_wiki.py edit "表名" --content "说明文本"` 或 `--file 文件路径`（两阶段确认：edit → 用户确认 → edit --confirm）。⚠️ **addNewWiki 是全量替换，不是追加**。追加内容时必须先 `show` 读取现有内容，将新内容拼接到已有内容后面，再整体写入。 |
| 前几行、前10行、前N行、前N条、看下数据、抽样数据、抽样、采样、取样、sample、样本、数据样本 | `python <skill-path>/modules/sql-execution/scripts/sample_table.py "表名关键字（支持 '项目.表名' 格式）"` → 一键采样（默认前 10 行），自动：找表→查字段→拼 SQL（含 MAX_PT 分区）→ 选 DEV 数据源 → 执行。 `-n` 行数 / `--columns` 规避敏感字段 / `--where` 覆盖自动分区。 跨工作空间取样在 stdout 显式 early-exit（不再盲调底层 API），给申请权限或换工作空间的命令。 权限/敏感字段拒绝时 stdout 自动给出申请链路（公有云 apply_resource_access.py，弹内控制台申请）。 |
| 字段画像、列画像、字段分布、列分布、统计字段、distinct、统计这个字段、NULL率、字段值分布、这个字段有多少个、字段最大最小、统计用户数、统计数量、多少个用户、多少个角色、有多少不同、多少种、用户数、角色数、去重、去重计数、值的数量、分布情况 | `python <skill-path>/modules/sql-execution/scripts/profile_column.py "表名关键字"` → 字段画像：COUNT / DISTINCT / NULL 率 / TOP N 值分布（数值字段额外给 MIN/MAX/AVG）。自动加 MAX_PT 分区 + 自动选数据源。 **用户问"统计 X 数 / 多少个 X / 分布 / 去重 / 不同值"优先用本脚本，不要用 execute_sql 手写 COUNT(DISTINCT)**。 单字段 `--column`，多字段 `--columns col1,col2`（一次跑完）。 |
| 执行SQL、跑SQL、运行查询、SELECT、INSERT、CREATE、DELETE、UPDATE、DROP、ALTER、SHOW、DESCRIBE、DESC、EXPLAIN、WITH | `python <skill-path>/modules/sql-execution/scripts/execute_sql.py "要执行的 SQL 语句" --datasource-code <用户选择的数据源 code>` → ⚠️ **优先用 sample_table.py / profile_column.py**——这两个覆盖 80% 场景且自动选数据源。本脚本仅用于自定义 SQL。 三步（不可跳步）：① `list_datasource_da.py --project-id <id>` 列数据源 → ② **用户选 datasource-code**（禁止自行选择！）→ ③ `execute_sql.py "SQL" --datasource-code <code>`（写 SQL 走 `--confirm` 两阶段）。 **不要手动调用** listSupportedEngine / listConnection / createQueryJob 等底层 API。 |
| 加工SQL、SQL写的什么、代码逻辑 | `python <skill-path>/modules/node-management/scripts/find_node_code.py --project-id <工作空间 ID>` → 先用 identify.py 定位节点拿到 entityId 或 taskId，再用此脚本获取开发态代码。只有 taskId 时自动反查 entityId |
| 线上跑的SQL、线上代码、线上源码、生产环境代码、生产代码、排查线上数据问题、数据缺失、数据为空、字段为空、为什么没有数据、线上实际跑的是什么、生产代码是什么 | `python <skill-path>/modules/node-management/scripts/find_node_code.py --project-id <工作空间 ID> --task-id <运行态任务 ID（taskId）>` → 先用 identify.py 定位节点拿到 taskId，再用此脚本加 --runtime 获取运行态代码（默认 prod，--env dev 查开发环境） |
| 更新节点代码、修改节点SQL、把文件内容写入节点、节点代码替换、更新节点内容、设置调度参数、添加调度参数、改节点调度变量、bizdate、设置bizdate | `python <skill-path>/modules/node-management/scripts/update_node_code.py --project-id <工作空间 ID> --entity-id <entityId> --file <本地代码文件路径>` → 将本地文件内容替换节点 script.content。支持 `--param "bizdate=$[yyyymmdd-1]"` 设置调度参数（可多次，与 --file 互相独立）。⚠️ **调度参数必须走本脚本**，不要用 update_vertex.py（updateVertex 对 script.parameters 有服务端 bug）。支持 --task-id 自动反查 entityId。更新后用 deploy_node.py 发布。 |
| 查看节点依赖、节点依赖关系、节点有哪些上游、上游依赖是什么、添加依赖、加依赖、添加上游依赖、移除依赖、删除依赖、去掉上游、解除依赖、移除上游节点 | `python <skill-path>/modules/node-management/scripts/manage_node_deps.py --project-id <工作空间 ID> --uuid <节点 UUID（entityId）>` → 查看 / 添加 / 移除开发态节点的上游依赖。 不带 --add / --remove 只列出当前依赖。 `--add <upstreamUuid>` 添加上游（可多次）；`--remove <upstreamUuid>` 移除上游（可多次）；`--type` 依赖类型，默认 Normal。 ⚠️ uuid 来自 identify.py 输出的 entityId（纯数字会被误判，用节点名搜索）。操作后自动展示更新后的依赖列表。 |
| 创建节点、新建节点、建一个SQL节点、建个shell任务、加个Flink流节点、新增任务、建任务 | ⚠️ `python <skill-path>/modules/node-management/scripts/create_node.py --project-id <工作空间 ID> --command <节点类型，如 ODPS_SQL / DIDE_SHELL / PYTHON / FLINK_SQL_STREAM / HOLOGRES_SQL / DI> --name <节点名称，支持 dir/subdir/name 多级路径>` → 按 ide_node_types.json 创建开发态节点。仅支持 verified=true 的 command（约 63 种，涵盖 ODPS_SQL / DIDE_SHELL / FLINK_SQL_STREAM / PYODPS3 / HOLOGRES_SQL / DI 等主流）。 未验证的 command 会被拒绝并给出补充 ground truth 的指引（不会硬撑猜参数）。 ⚠️ **ODPS_SCRIPT 节点禁用 create_node.py**（--command ODPS_SCRIPT 会被拒绝，verified=false）。必须改用：`python <skill-path>/core/write_api.py createNodeSimple scene=DATAWORKS_PROJECT command=ODPS_SCRIPT name=<name>`。 |
| 改节点调度、修改 cron、改调度时间、改重试次数、改超时时间、节点调度配置、设置节点优先级、暂停节点调度、恢复节点调度、改为 T+1、改 instance mode | ⚠️ `python <skill-path>/modules/node-management/scripts/update_vertex.py --project-id <工作空间 ID> --uuid <节点 UUID>` → 更新节点属性。8 个 runtime-verified aspect：schedule(trigger.cron/cycleType) / rerun(rerunTimes+rerunInterval) / recurrence / instanceMode / rerunMode / timeout / priority / autoParse。 未 verified 字段会被拒绝。查全部支持字段用 --list-verified。⚠️ **调度参数（bizdate 等）不走本脚本**，用 `update_node_code.py --param "bizdate=$[yyyymmdd-1]"`（updateVertex 对 script.parameters 返回系统错误，2026-05-25 实测）。 |
| 发布UDF、上线UDF、新建UDF、创建Python函数、部署Python UDF、把UDF发布到DataWorks、把UDF上线、更新UDF代码、修改UDF实现 | ⚠️ `PYTHONPATH=<skill-path>/core python <skill-path>/modules/deployment/scripts/deploy_udf.py --project-id <工作空间 ID> --file <本地.py文件路径> --resource-path <资源存放路径> --func-path <函数存放路径>` → **新建 UDF**（资源+函数+DEV+PROD 全流程，约 38s）。更新已有 UDF 代码只需加 `--update`（自动查找已有资源，约 15-20s，不重建函数）。`--skip-prod` 只发到开发环境。⚠️ `--resource-path` 和 `--func-path` 写到末级目录名（如 `旧版工作流/资源` 和 `旧版工作流/函数`）。发布后用 execute_sql.py 验证，结果用 duckdb_query.py 查看。 ⚠️ **Python 版本陷阱**：ODPS 默认用 Python 2 执行 UDF，f-string 等 Python 3 语法会报 `SyntaxError`。调用 UDF 的 SQL 必须先加 `SET odps.sql.python.version = cp37;`。若报错 `failed to get Udf info from xxx.py ... SyntaxError at line N`，是调用方漏加 SET，不是 UDF 代码错误。 |
| 查看UDF代码、看UDF源码、UDF实现是什么、UDF代码内容、查UDF、查Python函数代码、UDF写的是什么 | `PYTHONPATH=<skill-path>/core python <skill-path>/modules/deployment/scripts/view_udf.py --project-id <工作空间 ID> --name <UDF名称>` → 三步：listResources 找 resource_uuid → getResource 解析 file_uuid → GET getOrcFileResourceContent 拉取源码并打印。`--name` 传 UDF 名称（有无 .py 后缀均可）。 |
| 提交发布、上线节点、节点下线、发到线上、上线 | ⚠️ `python <skill-path>/modules/deployment/scripts/deploy_node.py --project-id <工作空间 ID> --uuid <节点 UUID（支持多个）>` → 三步流程：① deploy_node.py --project-id <id> --uuid <uuid> → ② 确认 → deploy_node.py --confirm（发布到开发环境）→ 用户验证 → ③ deploy_node.py --confirm-prod（发布到生产环境）。支持多节点：--uuid uuid1 uuid2。下线用 --type Offline。检查器阻塞时 stdout 会输出 analyze_checker_rca.py 命令。发布前如需检查代码，先用 find_node_code.py 查看。 ⚠️ **两阶段 --confirm 跨进程失效**：Phase 1 和 Phase 2 必须在同一 shell 进程链，用 `&&` 串联：`deploy_node.py ... && deploy_node.py ... --confirm`。否则进程退出后状态丢失，--confirm 找不到待确认项。 ⚠️ **发布前检查清单**：① 依赖已添加；② 依赖周期一致性（天任务只依赖天节点）；③ 天任务设置 `bizdate=$[yyyymmdd-1]`。 |
| 运维概况、工作空间情况、任务运行概况、整体运行情况、今日运行情况、有没有问题、出什么事了、跑完了吗、正常吗、今天怎么样、我的任务有哪些、我有哪些任务、任务列表 | `python <skill-path>/modules/task-ops/scripts/ops_overview.py` → 一站式运维概览：聚合周期实例（成功/失败/运行中、连续失败排行、耗时排行）+ 数据集成（离线状态、按数据源统计、实时指标）+ 手动任务状态。 --mine 只看我的。--date 默认 yesterday。 示例：用户说"autotest 整体运行情况" → ops_overview.py --project-name autotest |
| 每日巡检、运维巡检、今日巡检、每日检查、例行检查、帮我检查一下 | `python <skill-path>/modules/task-ops/scripts/daily_check.py` → 一键运维巡检：自动运行概况 + 查询失败实例 + 按负责人分组 + 输出批量重跑命令。 相比 ops_overview，自动追查失败实例，不需要 agent 再调一次 query_instances。 --mine 只看我的。--date 默认 yesterday。 |
| 数据集成运行情况、DI运行概况、同步任务情况、数据集成概览、离线同步情况、实时同步情况、同步任务情况怎么样、数据搬运正常吗 | `python <skill-path>/modules/task-ops/scripts/di_overview.py` → 数据集成概览（离线+实时）：离线实例状态、数据量汇总、按 source/sink 数据源统计（数据量+任务数）、失败实例；实时任务指标、运行中任务（按延迟排序）、告警事件。 --date 默认 today。 示例：用户说"昨天 autotest 的数据集成运行情况" → di_overview.py --project-name autotest --date yesterday |
| 补数据情况、手动任务情况、手动运行概况、手动实例列表、手动实例、补数据实例、有哪些手工任务、手工任务、手动任务列表、手动任务节点、我的手动任务、我有哪些手动任务、我有哪些手工任务 | `python <skill-path>/modules/task-ops/scripts/manual_biz_overview.py` → 手动任务一站式概览，含任务定义（nodeType=1）+ 运行实例（dagType=5）两层：状态分布、执行趋势、失败排行、节点分组、负责人聚合、实例列表（失败自动给 rerunDag 命令）。 用户问"我的手动任务"加 `--mine`。`--date` 默认 today。 |
| 失败任务、失败实例、未完成任务、任务运行状态、查实例、运维查询、哪些任务挂了、有什么报错、跑失败了、批量重跑、批量处理失败、失败任务处理、批量置成功、失败的节点、运行失败的节点、哪些节点失败、节点负责人、按负责人查失败、某人的失败任务、某人的失败实例、业务日期失败 | `python <skill-path>/modules/task-ops/scripts/query_instances.py` → 封装 getInstanceList 支持**多维组合过滤**：`--project-id` / `--date 业务日期` / `--status {failed,success,running,unfinished}` / `--type ODPS_SQL` / `--owner <工号或 me>` / `--mine` / `--search 节点名关键字`。 **用户 prompt 含"X 空间 Y 日期 Z 负责人 运行失败的节点"类复合过滤**直接组合上述 flag，不要自写 Python。 `--mine` == `--owner me`（和 ops_overview 参数一致）。 ⚠️ 连续失败多天的任务先走 task_detail.py 排查根因，不要直接重跑。 |
| 运行态任务详情、任务调度配置、任务上下游依赖、任务操作日志、这个任务怎么了、任务什么情况 | `python <skill-path>/modules/task-ops/scripts/task_detail.py --node-id <运行态任务 ID（nodeId）>` → 运行态任务详情：调度配置、最近实例、上下游依赖树、操作日志。 --node-id 是运行态任务 ID（getInstanceList 返回的 nodeId，不是开发态 uuid）。 示例：用户说"查看任务 308437862 的详情" → task_detail.py --project-id 14255 --node-id 308437862 |
| 基线概览、基线列表、基线运行状态、基线情况 | `python <skill-path>/modules/task-ops/scripts/baseline_overview.py` → 支持 --project-name 或 --project-id。--biz-date 默认昨天。 示例：用户说"autotest 基线情况" → baseline_overview.py --project-name autotest |
| 冒烟测试、测试运行、试跑、验证节点、跑一下试试、能不能跑通 | `python <skill-path>/modules/task-ops/scripts/smoke_test.py --project-id <工作空间 ID> --task-id <任务 ID（GetNode 的 taskId 字段）>` → 直接提交并轮询结果（成功/失败/超时）。失败时自动拉取运行日志。taskId 来自 GetNode 的 taskId 字段 |
| 补数据、补实例、回刷历史、重新跑历史数据、把数据补上 | ⚠️ `python <skill-path>/modules/task-ops/scripts/backfill_node.py --project-id <工作空间 ID> --task-id <任务 ID（GetNode 的 taskId 字段）>` → taskId 来自 GetNode 的 taskId 字段。支持 --start YYYY-MM-DD --end YYYY-MM-DD 自定义范围。开发环境补数据加 --env dev。 ⚠️ **补数据规范**（必须遵守）：① 禁止用 --days N 作默认值，必须显式传 --start/--end；② 默认只补昨天一天，多天必须用户明确指定；③ **两步必须分开**：preview → 等用户明确回复"确认" → --confirm，禁止在同一条回复里调 --confirm；④ --confirm 跨进程失效，每次补数据都必须重新跑 preview。 |
| 值班表、查值班、值班人员、排班、排班记录、今天谁值班、本周值班、值班安排、谁负责值班 | `python <skill-path>/modules/task-ops/scripts/duty_query.py` → 值班表查询：不带 --calname 列工作空间的值班表；带 --calname 查指定值班表的排班 + 人员名单。 默认日期范围：今天 → 7 天后（用 --begin/--end 自定义）。 内部已处理 listShiftPersonnel 的 calId 陷阱（实际传 calname 字符串）。 |
| 告警诊断、诊断告警、告警分析、这个告警是什么、告警怎么回事、帮我看下这个告警、粘贴告警、DW报错、调度失败诊断、基线告警、基线事件告警、实例失败诊断、失败原因分析 | `python <skill-path>/modules/task-ops/scripts/alarm_diagnose.py` → 告警诊断闭环：解析 → 拉实例 → **必查 listOpLogs**（先成功后失败必看是否代码变更）→ 拉日志 → Markdown 报告 + 处置建议。 输入：`--text "告警全文"` / `--file alarm.txt` / `--alarm-id <id>`（自定义规则）/ `--node-id <id> --bizdate` ⚠️（基线事件告警数字是 nodeId 不是 taskId）。需 `--project-id`。 ⚠️ 即使没发现代码变更也会显式标注「已检查未发现」——是诊断必经步骤。 |
| 批量重跑失败实例、重跑昨天的失败实例、把失败的重跑一下、重跑所有失败、批量补失败实例、按日期批量重跑失败 | ⚠️ `python <skill-path>/modules/task-ops/scripts/rerun_failed_instances.py` → rerun_task_instances API 不支持通过 instanceId 批量重跑，改用 supplementAsync 按 nodeId 补指定业务日期。 Phase 1: python rerun_failed_instances.py --project-id <id> # 输出摘要并写待办（默认昨天） Phase 2: python rerun_failed_instances.py --confirm # 用户确认后逐个提交 可选过滤: --date YYYY-MM-DD / --owner me / --task-type ODPS_SQL 进度查看: python check_backlogs.py |
| 创建离线同步任务、同步任务、DI任务、离线同步、数据搬运、帮我建个同步、把数据搬过来 | `python <skill-path>/modules/data-integration/scripts/resolve_sync_datasource.py` → **必须从 ① 开始，不要跳步、不要反问用户、不要自行拼接 API**。即使用户只说"同步 mysql 到 odps"也直接启动 ①，脚本会引导收集缺失参数。 五步：① resolve_sync_datasource → ② probe_table → ③ build_di_spec → ④ ensure_target_table → ⑤ create_di_node。**后续命令跟着 stdout 输出执行**。 ⚠️ 不知道源表名不要反问用户，**用 stdout 输出的 `probe_table.py ... --list-tables` 列出可用表**。 ⚠️ 用户从候选数据源选了名称后，**重新调 resolve_sync_datasource.py 带 --src-datasource <名>**，让脚本重新输出后续完整命令——不要自己跳到下一步拼参数。 |
| 治理总览、治理评分、数据资产概况、数据治理评分、扣分项 | `python <skill-path>/modules/governance/scripts/dgc_overview.py` → 默认个人视角。管理员查看他人：--owner-id 012345。工作空间视角：--workspace。 示例：dgc_overview.py --owner-id 006130 |
| 热门访问表未配置质量规则、热门问题表、按热度看治理问题、未配置质量规则的热门表、热门表治理、治理问题资产、治理不良资产、按访问热度列问题表、治理项资产列表、问题表按访问排序、问题表按规模排序 | `python <skill-path>/modules/governance/scripts/dgc_issues_asset.py` → ⚡ **当用户 prompt 含"找出...热门访问表未配置质量规则...推荐/配置质量规则"这类完整治理意图时，itemCode 直接用 18，并自动加 --recommend-dqc**，一行拉完问题表 + 输出每张表的 DQC 规则建议 + spec_builder/create_rule 命令链。 ⚡ 其他 item-code（其他治理项扫描结果）不要默认加 --recommend-dqc（推荐算法是按 DQC 模板特化的）。 典型闭环（itemCode=18 为例）： 1. dgc_overview.py 拿扣分项清单（含 itemCode=18） 2. dgc_issues_asset.py --item-code 18 --recommend-dqc 拉 TOP 问题表 + 自动推荐 DQC 规则命令 3. （按 stdout 提示）dqc_spec_builder.py ... -o gap.yaml 生成 spec 4. dqc_create_rule.py ... --spec-file gap.yaml 批量配置（两阶段确认） 和 dgc_rule_findings.py 的区别：findings 走 OpenAPI 版，返字段精简；本脚本走 BFF 版，字段丰富+服务端排序。 |
| 离线作业治理、离线作业下线、治理计划、下线阶段 | `python <skill-path>/modules/governance/scripts/dgc_offline_jobs.py` |
| 扫描器、治理扫描、扫描器概况、治理规则扫描 | `python <skill-path>/modules/governance/scripts/dgc_scanner.py` |
| 资源治理、资源用量、计算资源用量、存储资源、资源概况 | `python <skill-path>/modules/governance/scripts/dgc_resource.py` → 支持 --project-name 或 --project-id。--detail calc/store/schedule 查看 TOP 明细。 示例：dgc_resource.py --project-name autotest --detail calc |
| 资源组、资源组列表、调度资源组、查资源组、工作空间有哪些资源组 | `client.load("listResourceGroups", projectId=...)` → 查工作空间级资源组列表。默认 modules=['SCHEDULER'] 查调度资源组；返回 resourceGroupId / resourceGroupIdentifier / resourceGroupName，可用作 getInstanceList 的 resgroupId 参数 |
| 数据源列表、查数据源、工作空间数据源、有哪些数据源、数据源详情、数据源信息、查某个数据源、按名称查数据源、按类型查数据源、找数据源、数据源名称、数据源类型、支持哪些数据源、可用数据源类型、DI数据源、同步数据源、DQC数据源 | `python <skill-path>/modules/runtime-env/scripts/browse_datasource.py` → **唯一的数据源入口**。合并 5 路底层 API（listDataSourceV2 / getDataSourceList / listDataSourcesProject / listSupportedEngine / listComputeResources）并标注 sql/di_src/di_dst/dqc 能力白名单。 **不要自己调用底层 API**，所有数据源查询走本脚本。 核心 flag：位置参数模糊查名称 / `--type odps` / `--for {sql,di_src,di_dst,dqc}` / `--detail <name>` / `--json`。 StarRocks/EMR/Hologres/MC 等自建数仓的 CR 来源列有标记 → 可作敏感识别任务扫描源。 |
| 计算资源、计算资源列表、集群实例、查计算资源、计算引擎实例、工作空间计算资源、odps 实例、starrocks 集群、hologres 实例、emr 集群 | `python <skill-path>/modules/runtime-env/scripts/list_compute_resources.py` → 计算资源 ≠ 数据源： - MySQL/Oracle 等外部数据源**不在**此列表（只在 browse_datasource） - StarRocks/EMR/Hologres/MC 这类自建数仓同时在两处（browse_datasource 会标 CR 位置） **服务端过滤**（比客户端 filter 快且准）： - --type starrocks,emr（逗号分隔多值） - --keyword xxx（按 name 模糊） - --env dev|prod - --default-only（只看默认资源 ★） 查单条: --detail <name>（客户端过滤） |
| 我是谁、whoami、当前用户、我的信息、我的身份、我在 dataworks 下是谁、我有哪些工作空间、我的角色、确认身份、身份和工作空间、身份和常用工作空间、身份和常用空间、常用工作空间、我的常用工作空间、我的工作空间、看一下我的工作空间、我所在的空间、现在工作空间是什么 | `python <skill-path>/modules/workspace/scripts/whoami.py` → 查询当前用户基本信息 + 所属工作空间列表。 默认 ≤3 个空间时自动带每空间角色；>3 时只列空间，引导用 --with-roles 或 --project。 用户问"我是谁 / 当前用户 / 我的角色 / 我在哪些空间"时优先用此脚本，不要用 bff_client 猜 API 名。 |
| 工作空间概览、项目列表、有哪些工作空间 | `python <skill-path>/modules/workspace/scripts/workspace_overview.py` |
| 数据管道、同步全景 | `python <skill-path>/modules/workspace/scripts/pipeline_overview.py "工作空间 ID"` |
| 报bug、反馈问题、提交建议、上报问题、出bug了、有问题要反馈 | `python <skill-path>/modules/workspace/scripts/report_bug.py "问题描述"` → 自动收集上下文（session_state、最近工具结果、API调用日志）并上报。 用户说"xx脚本报错了"时，agent 应把错误描述作为第一个参数传入。 示例：report_bug.py "probe_table 报错 datasourceType should not be null" --script probe_table.py |
| 质量概览、质量怎么样、质量情况、质量如何、质量巡检、数据质量概览、整体质量 | `python <skill-path>/modules/workspace/scripts/workspace_quality.py` → 支持 --project-name 或 --project-id。--biz-date 默认昨天。 示例：用户说"autotest 质量如何" → workspace_quality.py --project-name autotest |
| DQC概览、DQC质量、规则运行情况、规则有没有问题、告警情况、今天规则怎么样、规则巡检、DQC大盘 | `python <skill-path>/modules/dqc/scripts/dqc_overview.py` → DQC 规则执行全景：通过/告警/阻塞、风险表排行、按表/按人分布、执行趋势。 支持 --project-name 或 --project-id。--date 默认 today，无数据自动降级到最近有数据的日期。 示例：dqc_overview.py --project-name autotest |
| 表有哪些规则、规则列表、规则配置、配了哪些规则、挂了哪些规则、质量规则列表 | `python <skill-path>/modules/dqc/scripts/dqc_list_rules.py` → 查看表的完整规则配置列表（不只是已执行/失败的）。 展示每条规则的名称、强弱类型、阈值配置、ruleId。默认只显示启用的，--all 包含禁用的。 和 dqc_rule_checks.py 的区别：list_rules 看"配了什么"，rule_checks 看"检查结果"。 示例：用户说"test表配了哪些规则" → dqc_list_rules.py --project-id 14255 --table test |
| 创建规则、添加规则、新建规则、加个规则、给表加质量检查、添加质量监控、字段波动、字段波动率、监控字段均值、监控字段总和、监控唯一值、动态阈值规则 | `python <skill-path>/modules/dqc/scripts/dqc_create_rule.py` → 为表创建数据质量规则。两阶段确认：预览 → --confirm 提交。 模板分 6 类（共 30+ 条），--list-templates 查分类清单： 1. 表行数：fixed / flux（1/7/30天/月初/均值/周期）/ delta / dynamic_threshold 2. 表大小：fixed / flux / delta / dynamic_threshold 3. 字段-空值：null_count_0 / null_count_fixed / null_percent 4. 字段-重复值：duplicate_count_0 / duplicate_count_fixed / duplicate_percent / duplicates_multi_0（联合主键，用 --fields） 5. 字段-唯一值：col_distinct_fixed / flux / dynamic / percent 6. 字段-聚合（min/max/avg/sum）：col_*_flux / col_*_dynamic **字段级波动**：col_distinct_flux / col_min_flux / col_avg_flux / col_sum_flux **字段级动态阈值**：col_distinct_dynamic / col_min_dynamic / col_max_dynamic / col_avg_dynamic / col_sum_dynamic **逃生舱**：--template 可直接传完整 templateCode（如 SYSTEM:field:avg:flux:1_7_1m_bizdate） **格式校验 / 枚举值**（需 valid.regex/format/values）请走 Spec 路径： dqc_spec_builder.py --template col_regex --field phone --regex '^\d{11}$' -o rules.yaml dqc_create_rule.py --project-id <id> --table <名> --spec-file rules.yaml 字段级规则需 --field；多字段模板需 --fields。 示例：dqc_create_rule.py --project-id 14255 --table test --template col_avg_flux --field price |
| 识别任务列表、查识别任务、敏感识别任务、识别任务、所有识别任务、任务执行状态、识别任务状态 | `python <skill-path>/modules/security-center/scripts/list_recognition_tasks.py` → 首次用户无任何过滤可直接 list_recognition_tasks.py 看全量前 50 个。 查单任务执行状态：--task-name <关键字> 或 --task-id <uuid>（看 taskStatus + lastExecutionTime 即可）。 ⚠️ 仅公有云（/dp/listRecognitionTasks），弹内/私有无此产品。 |
| 创建识别任务、新建识别任务、建识别任务 | `python <skill-path>/modules/security-center/scripts/create_recognition_task.py --task-name <任务名（服务端不做唯一校验，建议前缀 test_/dev_ 便于清理）> --engine <引擎类型：ODPS.ODPS / STARROCKS / DLF.LEGACY / HOLOGRES 等（从页面下拉同步）>` → 两阶段提交（preview → confirm）。简单任务：--task-name 名 --task-type Once --engine ODPS.ODPS。 复杂配置（识别范围 rangeList、任务配置 taskConfig、EMR 配置 emrConfigs）需要 --config-json <file> 传完整 body。 ⚠️ 仅公有云。 |
| 识别结果、识别出的敏感字段、敏感字段列表、敏感数据清单、查识别结果、识别出了哪些字段、敏感数据识别结果 | `python <skill-path>/modules/security-center/scripts/view_recognition_result.py` → 全量视角不按 taskId 过滤（API 设计如此），用 --db / --table / --engine 收窄。 --since 支持 7d/24h/YYYY-MM-DD 简写。 --group-by 可按 sensitiveTypeName/sensitiveLevelName/engineType/dbName 分布。 |
| 有哪些敏感类型、敏感类型列表、敏感类型清单、列出敏感类型、租户启用的敏感类型、分类分级模板、查敏感类型 | `python <skill-path>/modules/security-center/scripts/list_sensitive_types.py` → 树结构：分类（branch）→ 具体类型（leaf）。leaf 才是实际扫描/过滤目标。 --leaf-only 单行输出方便直接作为 --sensitive-type 入参。 |
| 我的申请、我提交的申请、权限申请单、申请记录、我的权限申请、申请审批列表、application-approval、数据访问权限申请 | `python <skill-path>/modules/security-center/scripts/list_my_applications.py` → --apply-type 自动转 engineType+objectType 组合，无需手算枚举值。 --status 接受中文 审批中/通过/拒绝 或数字 0/1/2。 orderType 默认 1（按时间排序）。 |
| 审批策略、审批策略列表、查审批策略、申请审批、审批策略详情、审批流 | `python <skill-path>/modules/security-center/scripts/list_approval_policies.py` → 列表模式：--policy-type <type>，默认 MaxComputeTable。 详情模式：--id <workflowId> 查完整配置（含 ruleConditions/approvalNodes/notificationServices）。 部分租户必须传 --region（如 cn-beijing）。 |
| 申请权限、申请表权限、申请访问权限、授权申请、提交权限申请 | `python <skill-path>/modules/security-center/scripts/apply_resource_access.py --resource-type <资源类型。**当前仅 MaxComputeTable 可用**；其他值（HologresTable/DLFTable/DLFNextTable/StarRocksTable/EmrTable/LindormTable）尚未实现，传入会退出。> --project <项目名，如 cwy_test_bj_0422> --table <表名> --grantee-id <被授权人 baseId（纯数字）> --reason <申请理由>` → 两阶段提交：Phase 1 preview → 用户确认 → Phase 2 --confirm。 operator/tenantId 服务端自动填，脚本不传。 expirationTime 为毫秒时间戳字符串，脚本自动计算（--expiration-days）。 列级权限：--columns id,name → 额外 2 条 Download entry，共 3 条 applyContent。 ⚠️ 不要先查 workspace_id —— 脚本内部 searchTables→getDetail 自动反查。直接传 --project + --table 就够。 ⚠️ 当前 --resource-type 只支持 MaxComputeTable；其他值会 stderr 报错退出，需补流量样本后独立实现。 **agent 可选：分步探测模式** --probe target → 只 resolve 资源（返回 workspace_id + dma_entity_id） --probe grantee → 只验证被授权人 --probe columns → 只验证列（需 --workspace-id + --dma-entity-id + --columns） --probe all → 跑全部 resolve 但不进入 write 每个 probe 完成后 stdout 自动给出下一步完整命令，agent 直接执行。 典型场景：遇到匹配歧义（多张同名表）时，先 probe target 确认； 用户只给了姓名时，先 probe grantee 找 baseId。 |
| 待审批、待我审批、待办审批、审批待办 | `python <skill-path>/modules/security-center/scripts/list_pending_approvals.py` → 这是「我需要审批的」，不是「我申请的」。 如需看我自己提交的申请 → list_my_applications.py。 如需看我已审批过的 → list_my_approvals.py。 |
| 我审批过的、我的审批记录、审批历史 | `python <skill-path>/modules/security-center/scripts/list_my_approvals.py` → 只读历史，不含「待审批」。 待审批 → list_pending_approvals.py。 |
| 撤销申请、取消申请、撤回申请、撤销权限申请、取消权限申请、撤回我的申请、撤销审批、撤回提交 | ⚠️ `python <skill-path>/modules/security-center/scripts/cancel_application.py` → 两阶段写操作：Phase 1 `cancel_application.py --order-id <orderId>` 只输出"将要撤销的申请摘要"，不真的撤销；用户明确确认后，Phase 2 `cancel_application.py --confirm` 才执行。 已处于终态（通过/拒绝/已取消）的申请会自动跳过，不再发请求。 |
| 安全策略列表、查安全策略、策略列表、有哪些安全策略、DataStudio 策略、安全管控策略、下载策略、查询策略列表 | `python <skill-path>/modules/security-center/scripts/list_security_policies.py` → DataStudio 安全策略控制工作空间下的 IDE 行为：单次查询/复制/下载行数上限、是否允许 Excel 导出、是否允许 ServerIDE 扩展/终端、是否允许下载挂载目录文件。 SYSTEM_ 前缀的系统策略服务端硬编码保护：rule/name 不可改。 |
| 删除安全策略、删除策略、移除安全策略、下线策略、清理安全策略 | ⚠️ `python <skill-path>/modules/security-center/scripts/delete_security_policy.py` → ⚠️ 服务端特殊保留行为，脚本 Phase 1 会预警： - 系统策略（SYSTEM_ 前缀或 isDefaultPolicy）：接口返回成功但实际不删 - DISABLE_DOWNLOAD_FROM_SETTING_CENTER：强制 DISABLE 而非真删（防止管理中心同步反复加载） |
| 生效策略、当前生效的策略、他的策略是什么、为什么不能下载、为什么不能导出、为什么 ServerIDE 终端用不了、为什么无法使用终端、排查下载权限、查策略匹配、策略诊断 | `python <skill-path>/modules/security-center/scripts/match_security_policy.py` |
| 创建安全策略、新建安全策略、添加安全策略、创建下载策略、禁用下载、修改安全策略、更新安全策略、调整策略、改策略 | ⚠️ `python <skill-path>/modules/security-center/scripts/create_security_policy.py` → ⚠️ **upsert 语义**：传 --policy-uuid 是更新已有策略；不传是创建新策略。 ⚠️ 策略内容超 cap 会被服务端**静默裁剪**（不报错）；脚本 Phase 1 会主动调 getLimit 做 pre-check 并对超 cap 字段发 warning。 ⚠️ SYSTEM_ 前缀的系统策略：rule/workspaceIds 服务端硬编码保留。 policyContent 7 字段（布尔 / Long）：maxLimitOfSingleQuery（cap 10000）/ maxLimitOfSingleCopy（cap 10000）/ maxLimitOfSingleDownload（版本 cap）/ allowExportExcel / allowExtensionInServerIDE / allowTerminalInServerIDE / allowDownloadMountedWorkspaceFile。 用 `--set key=value` 可重复传多字段；或直接用 `--content-json '{...}'` 传完整对象。 |

## 陷阱与规范速查

> 以下规则在对话中禁止重复踩坑，每次执行对应操作前必须检查。

### identify.py 纯数字 ID 陷阱

`identify.py 8473429950060237683` 会把纯数字 ID 误判为 instanceId。**Fix**：用节点名搜索：`identify.py "节点名称关键字"`。

---


### UpdateNode 两大陷阱 ⚠️

1. **spec 全量覆盖**：UpdateNode 的 spec 参数是全量替换，不是 patch merge。只传 `script.content` 会把 `parameters`（调度变量）清空 → 运行时报 `Invalid partition value`。**Fix**：先 `getNode` 拿完整 spec → 内存里只改目标字段 → 再 updateNode。

2. **confirm_write() 404 / 403031**：内网 BFF 的 `/ide/api/v1/openapi/nodes/` 后端未部署。**Fix**：直接 `requests.post` 到 `/dataworks_public_v2024-05-18/updateNode`，headers 带 `Authorization: Bearer <token>`、`Referer: http://<session_code>.qwen.cli`、`X-User-Confirmed: <sha256前16位>`；uuid 必须作为独立顶层 form param。

---

### BFFClient 没有 `_post` 方法

需要拿原始 response body（如 `spec` 字符串）时，用 `requests.post` 直接打 endpoint，不要尝试调 `BFFClient._post`（会报 AttributeError）。

---

### check_backlogs.py 使用规范

- `check_backlogs.py --list` **只读本地文件**，不调 API，不能用于轮询状态
- 轮询补数据状态必须用无参数版本：`PYTHONPATH=<skill-path>/core python <skill-path>/core/check_backlogs.py`
- `getSupplementAsyncResult` status=6 表示 DAG 创建成功，**不代表实例跑完**；`check_backlogs.py`（无参数）已实现两层查询，自动用 dagId 查实例真实状态

---

### MaxCompute ALTER TABLE CHANGE COLUMN

每次只能改一列，必须拆成多条独立语句逐条执行（不支持逗号分隔多列）。

---

## 调用规则

> **交互原则**：能自动获取的自动获取，要用户决策的列出选项让选，跳过已知项。

**所有 `python` 命令前缀**：`PYTHONPATH=<skill-path>/core`（路由表和本节命令都省略此前缀；有 intent 需要额外 pythonpath 时会显式写全）。

### 读操作（load → DuckDB 查询）

```bash
python -c "from bff_client import BFFClient; BFFClient().load('searchTables', keyword='xxx', entityType='maxcompute-table')"
# stdout: [searchTables_r1_c1] 30 条 | keyword=xxx | qualifiedName, name, databaseName, ...

python <skill-path>/core/duckdb_query.py "SELECT qualifiedName, name FROM searchTables_r1_c1 WHERE name='xxx'"
```

- **⚠️ 不要 `print(client.load(...))`** — list/dict 完整返回会被截断
- `load()` 自动全量翻页（20,000 条上限），日志自动写 `logs/dw_bff_calls.log`
- stdout 中 `col.{sub1, sub2}` 是 STRUCT 列 → DuckDB 用 `col.sub1` 访问（不能单用 `sub1`）

### 写操作（两阶段确认）

```bash
python <skill-path>/core/write_api.py <apiName> key=value   # Phase 1 预览
python <skill-path>/core/write_api.py --confirm             # Phase 2 执行
```

### API 元数据（未匹配路由 或 查参数/返回/是否写操作）

```bash
python <skill-path>/core/api_info.py <apiName>              # 精确
python <skill-path>/core/api_info.py <关键字> --search      # 模糊搜（名字/路径/描述/字段）
```

用户问"XXX 接口怎么调 / 入参什么 / 是写操作吗"**一律走 `api_info.py`**，不要 grep 源码或读 api-index.json 整体。精确未命中自动给候选。

> 更多模式（链式 / 聚合 / 高级用法）见 `<skill-path>/core/references/calling-patterns.md`。

---

## 参考文档

| 文档 | 何时读取 |
|-----|---------|
| `<skill-path>/core/references/api-index.json` | 路由表未匹配时查阅（完整 API 列表，含 description 和参数定义） |
| `<skill-path>/core/references/calling-patterns.md` | 链式调用、DuckDB 查询的完整模式和示例 |
| `<skill-path>/core/references/api-examples.md` | 需要多 API 链式调用代码参考时 |
| `<skill-path>/core/references/field-mapping.md` | 跨 API 字段映射、写操作完整清单、常见错误 |
