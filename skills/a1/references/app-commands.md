# app 命令完整参考

## a1 app — 应用管理

查询应用信息、管理变更单（CR）、发布流水线和部署单。

---

## 应用基础操作

### app list
列出应用。
- `-k, --keyword string` — 搜索关键词

### app view <app-name-or-id>
查看应用详情。

### app create [beta]
创建新应用。
- `--name string` — 应用名称
- `--description string` — 描述
- `--product-line string` — 产品线
- `--git-group string` — Git 组
- `--language string` — 开发语言（默认 java）
- `--trunk string` — 主干分支（默认 master）
- `--from-json string` — 从 JSON 文件创建

### app link [name-or-id]
绑定当前目录到应用。支持交互式选择。

### app unlink [id]
移除应用绑定。
- `--all` — 移除所有绑定

---

## 变更单管理（app cr）

### app cr list
列出变更单。
- `--app string` — 应用名称（默认从绑定获取）
- `--status strings` — 状态筛选（可多次使用），如 DEVELOPING、INTEGRATED
- `--all` — 显示所有状态
- `-f, --format string`, `-q, --quiet`

### app cr get-by-branch
通过应用分支查询关联的变更单。适用于已知 feature/release 分支，需要反查 CR ID、再查需求/文档/评审上下文的场景。
- `--app string` — 应用名称或 ID（默认从绑定获取）
- `--branch string` — 分支名或完整 branch URL；纯分支名会用应用代码配置中的 repoUrl 自动拼成 `<repo-url> <branch-name>`
- `-f, --format string`, `-q, --quiet`

```bash
a1 app cr get-by-branch --app taodetail --branch feature/demo --quiet
a1 app cr get-by-branch --app taodetail --branch "git@gitlab.alibaba-inc.com:demo/taodetail.git feature/demo"
```

### app cr create <description> (--branch <name> | --existing-branch <name>)
创建变更单。**必须显式指定 `--branch` 或 `--existing-branch` 其一**（互斥，其中之一必填）——`description` 只作为 CR 描述，不再隐式作为分支名。

`description` 会被 a1 按 Aone 字段限制截断到 2000 display-width 以内（中文等宽字符按 2 计）。Agent 自动生成 CR 时不要把 PRD / tech-design 的大段正文直接塞入该字段；先压缩成 3-5 行核心变更摘要，并追加 `详情见 <PRD/tech-design 链接>`。

- `--app string` — 应用名称（默认从 link context 读取）
- `--branch string` — 新建分支名后缀（无 `--existing-branch` 时必填）
- `--existing-branch string` — 复用的已有远程分支名（无 `--branch` 时必填）
- `--workitem-ids string` — 关联的 Aone 工作项 ID，多个用逗号分隔
- `--tester strings` — 测试人花名或工号，多个用逗号分隔或重复使用
- `--plan-release-date string` — 计划发布时间，支持 `2026-06-10 14:00`、`+2d`、`3h` 等

未传两个分支 flag 时命令会报错 `either --branch or --existing-branch is required`。

### app cr submit <cr-id>
提交变更单到待发布，或提交到指定发布流水线并触发执行。
- `--app string` — 应用名称或 ID；默认从当前 link 上下文推断
- `--pipeline-id int` — 发布流水线 ID；指定后将 CR 提交到该流水线的发布流实例并触发执行
- `-f, --format string` — 输出格式，支持 plain、json
- `-q, --quiet` — 仅输出关键 ID

示例：

```bash
# 提交到待发布状态
a1 app cr submit 12345

# 提交到指定发布流水线并触发执行
a1 app cr submit 12345 --pipeline-id 66

# 提交后等待流水线结束
a1 app pipeline status --pipeline-id 66 --wait-until-settled
```

`a1 app pipeline reenter --pipeline-id <id>` 是对最新发布实例执行 REENTER/再次触发的操作；首次把 CR 提交到发布流水线时，直接使用 `app cr submit --pipeline-id`。`app pipeline run` / `app pipeline retry` 已废弃，仅作为兼容别名保留。

用户说“提交流水线发布”“提交到发布流水线”“发到流水线”时，使用：

```bash
a1 app cr submit <cr-id> --pipeline-id <pipeline-id>
```

不要使用 `a1 app cr submit-integration` 处理发布流水线提交；`submit-integration` 只用于项目环境/集成阶段。

### app cr submit-integration <cr-id>
提交应用 CR 到集成阶段/项目环境。若 CR 仍处于 DEV/TEST，命令会先自动推进到 PREINTG，再完成集成阶段提交。
- `--project-env-id int` — 项目环境 ID（必需）
- `--project-env-mode string` — 项目环境模式：`existing`（默认）或 `new`
- `--app string` — 应用名称或 ID；默认从当前 link 上下文推断
- `-f, --format string` — 输出格式，支持 plain、json
- `-q, --quiet` — 仅输出关键 ID

仅当用户明确说“项目环境”“联调环境”“集成阶段”并且目标 CR 处于 DEV/TEST/PREINTG 时使用。

示例：

```bash
a1 app cr submit-integration 12345 --project-env-id 678
a1 app cr submit-integration 12345 --project-env-id 678 --project-env-mode new
a1 app cr submit-integration 12345 --project-env-id 678 --app 229256
```

不要把它用于“提交流水线发布”。CR 已进入 `INTG` 或用户要走发布流水线时，应使用 `a1 app cr submit <cr-id> --pipeline-id <pipeline-id>` 及 `a1 app pipeline status` 等发布流水线命令；需要再次触发最新发布实例时使用 `a1 app pipeline reenter --pipeline-id <id>`。

### app cr unsubmit <cr-id>
撤回变更单，回到开发状态。

### app cr delete <cr-id>
关闭变更单（不可逆）。
- `-y, --yes` — 跳过确认

### app cr quit <cr-id>
从发布流水线中退出。
- `--pipeline-id int` — 流水线 ID（必需）

### app cr item list <cr-id>
列出 CR 下的变更项。该命令本身是通用 CR item 查询能力;
- `-f, --format string` — 输出格式：table、json
- `-q, --quiet` — 仅输出 CR item ID

### app cr config-item schema list <cr-id>
列出指定 CR item 下可操作的配置项分组。
- `--item string` — CR item ID；当 CR 下存在多个可操作 item 时必传
- `-f, --format string` — 输出格式：table、json
- `-q, --quiet` — 仅输出 schema

### app cr config-item get <cr-id>
查询 CR 配置项内容。
- `--item string` — CR item ID；当 CR 下存在多个可操作 item 时必传
- `--schema string` — 配置项分组；除 `--all-schema` 外必传
- `--all-schema` — 查询全部配置项分组；与 `--schema` 互斥
- `--query string` — 按配置项 key 过滤
- `--include-unchanged` — 包含未变更的存量配置项
- `--show-secrets` — 显示 secret 配置项明文；默认脱敏
- `-f, --format string` — 输出格式：table、json
- `-q, --quiet` — 仅输出配置项 key

### app cr config-item set <cr-id>
新增或修改 CR 配置项。
- `--item string` — CR item ID；当 CR 下存在多个可操作 item 时必传
- `--schema string` — 配置项分组（必需）
- `--key string` — 配置项 key
- `--value string` — 配置项 value
- `--value-file string` — 从文件读取配置项 value
- `--from-json string` — 从 JSON 文件批量读取配置项变更
- `--secret` — 标记该配置项为 secret
- `--show-secrets` — 显示 secret 配置项明文；默认脱敏
- `-f, --format string` — 输出格式：table、json
- `-q, --quiet` — 仅输出配置项 key

`--key` 需要与 `--value` 或 `--value-file` 配合使用；批量修改使用 `--from-json`。保存成功后只返回本次提交的配置项摘要，不会回查全量配置项。

`--from-json` 文件示例：
```json
[
  {"key": "feature.enabled", "value": "true", "secret": false},
  {"key": "token", "value": "xxx", "secret": true}
]
```

### app cr config-item unset <cr-id>
删除 CR 配置项。
- `--item string` — CR item ID；当 CR 下存在多个可操作 item 时必传
- `--schema string` — 配置项分组（必需）
- `--key string` — 配置项 key（必需）
- `--show-secrets` — 显示 secret 配置项明文；默认脱敏
- `-f, --format string` — 输出格式：table、json
- `-q, --quiet` — 仅输出配置项 key

### CR 配置项操作建议
- 如果 CR 下只有一个可操作 item，可以只传 `crId`；如果存在多个可操作 item，先执行 `a1 app cr item list <cr-id>`，再用 `--item <cr-item-id>` 指定目标。
- 查询存量配置项使用 `get --include-unchanged`；查询所有分组使用 `get --all-schema`。
- secret 配置项默认脱敏，只有在用户明确需要明文时才加 `--show-secrets`。
- 配置项修改不要连续高频提交；多次 `set`/`unset` 之间要求间隔 1-2 秒，避免上游配置变更短暂不可见导致失败。
- 同一 schema 下批量修改多个 key 时，优先使用 `set --from-json <file>` 一次性提交，不要循环逐个 `set`。
- 保存或删除配置项可能受 CR 权限控制；无权限保存通常返回 `cr_config_item_permission_denied`。

---

## 发布流水线（app pipeline）

### app pipeline list
列出应用的发布流水线。
- `--app string` — 应用名称或数字 app ID（默认从 link context 读取）

### app pipeline status
查看发布状态（自动解析到最新实例）。
- `--pipeline-id int` — 流水线 ID

### app pipeline branch
按流水线实例 ID 查询 release 分支和分支合并变更。
- `--instance-id int` — 流水线实例 ID
- `--app string` — 应用名称或数字 app ID（默认从 link context 读取）
- `--format json` — JSON 输出，包含 `changeRequests[]`
- `--quiet` — 仅输出 release 分支

### app pipeline reenter
对最新发布实例执行 REENTER/再次触发。
- `--pipeline-id int` — 流水线 ID
- `--wait-until-settled` — REENTER 后持续等待新实例进入稳定状态

需要部署指定 CR 分支时不要使用 `reenter`，直接使用：

```bash
a1 app cr submit <cr-id> --pipeline-id <pipeline-id>
```

### app pipeline run / retry
已废弃，仅作为兼容别名保留。需要再次触发最新发布实例时使用 `a1 app pipeline reenter --pipeline-id <id>`；需要部署指定 CR 分支时使用 `a1 app cr submit <cr-id> --pipeline-id <id>`。

### app pipeline instance list
列出流水线实例。
- `--pipeline-id int` — 流水线 ID

### app pipeline stage list
列出发布阶段（自动解析到最新实例）。
- `--pipeline-id int` — 流水线 ID

### app pipeline stage status
查看阶段状态。
- `--stage-id int` — 阶段 ID

### 深层嵌套命令

发布流水线支持多层嵌套查询：

```
app pipeline stage job list --stage-id <id>        # 阶段内 job 列表
app pipeline stage job status --job-id <id>        # job 状态
app pipeline stage job task list --job-inst-id <id>  # job 内任务列表
app pipeline stage job task status --task-inst-id <id>  # 任务状态
```

还支持动态组件语法（COMPONENT_SIGN 即组件标识，如 BUILD、CR_PUBLISH_RELEASE 等）：
```
app pipeline stage job task <COMPONENT_SIGN> status  # 按组件名查状态
app pipeline stage job task <COMPONENT_SIGN> log     # 按组件名查日志
```

### app pipeline stage job task list
列出 job 内的任务。
- `--job-inst-id int` — Job 实例 ID（**必填**）；别名 `--job-id`
- `--instance-id int` — 流水线实例 ID（可选，跳过应用绑定解析）

### app pipeline stage job task status [ACTION] [PARAM=VALUE ...]
查看任务状态，或执行任务支持的动作。
- `--task-id int` — 任务实例 ID（**必填**）；别名 `--task-inst-id`

不带 ACTION 时显示任务当前状态、组件数据和支持的动作列表（`supportedActions`）。
带 ACTION 时执行该动作；额外参数以 `KEY=VALUE` 形式跟在 ACTION 后面。

#### 部署任务常见动作（supportedActions）

动作列表由服务端动态返回，以下为部署组件（CR_PUBLISH_RELEASE 等）常见的内置动作：

| 动作代码 | 说明 | 示例 |
|---------|------|------|
| `deploy-order-list` | 查看当前部署任务关联的发布单列表 | `task status --task-id <ID> deploy-order-list` |
| `view-diagnosis` | 查看自动失败的启动诊断详情（lastStartupActionDiagnosisErrors） | `task status --task-id <ID> view-diagnosis` |
| `finish` | 批量关闭当前部署任务关联的所有发布单 | `task status --task-id <ID> finish` |
| `resume` | 批量恢复当前部署任务关联的所有发布单 | `task status --task-id <ID> resume` |
| `log` | 查看构建日志（CI 组件，cli 类型，显示可执行的日志命令） | `task status --task-id <ID> log` |
| `skip` | 跳过部署 | `task status --task-id <ID> skip` |

参数自动填充规则：`deployIdList`、`flowComponentInstId`、`flowInstId` 等参数会从组件数据中自动提取，通常无需手动传。
如需指定某个发布单 ID，可显式传 `deploy-id-list=<ID>`（kebab-case 自动转 camelCase）。

#### 发布单操作典型工作流

```bash
# 1. 查看流水线状态，找到阶段 / job / task ID
a1 app pipeline status --pipeline-id 66

# 2. 查看阶段列表
a1 app pipeline stage list --pipeline-id 66

# 3. 查看阶段内的 job 列表
a1 app pipeline stage job list --stage-id <stage-id>

# 4. 查看 job 内的 task 列表
a1 app pipeline stage job task list --job-inst-id <job-inst-id>

# 5. 查看 task 状态和支持的动作
a1 app pipeline stage job task status --task-id <task-id>

# 6. 查看该 task 关联的发布单列表
a1 app pipeline stage job task status --task-id <task-id> deploy-order-list

# 7. 查看部署失败诊断
a1 app pipeline stage job task status --task-id <task-id> view-diagnosis

# 8. 批量恢复发布单（发布暂停后继续）
a1 app pipeline stage job task status --task-id <task-id> resume

# 9. 批量关闭发布单
a1 app pipeline stage job task status --task-id <task-id> finish
```

也可以用组件名快捷访问（无需知道 task-id）：
```bash
a1 app pipeline stage job task CR_PUBLISH_RELEASE status    # 查看发布组件状态
a1 app pipeline stage job task CR_PUBLISH_RELEASE deploy-order-list  # 查看发布单
a1 app pipeline stage job task BUILD log                     # 查看构建日志
```

---

## 部署单（app deploy-order）

### app deploy-order list
列出部署单。
- `--pipeline-id int` — 发布流水线 ID
- `--app string` — 应用名称或数字 app ID（默认从 link context 读取）

### app deploy-order get <deploy-order-id>
查看部署单详情。
- `--app string` — 应用名称或数字 app ID（默认从 link context 读取）

### app deploy-order cr <deploy-order-id>
查看部署单关联的变更单。
- `--app string` — 应用名称或数字 app ID（默认从 link context 读取）

### app deploy-order batch list <deploy-order-id>
列出部署批次。
- `--app string` — 应用名称或数字 app ID（默认从 link context 读取）

### app deploy-order batch hosts <deploy-order-id>
查看部署批次主机详情。
- `--app string` — 应用名称或数字 app ID（默认从 link context 读取）
- `--batch-num int` — 批次号
