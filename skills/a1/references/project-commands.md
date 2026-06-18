# project / staff 命令完整参考

## a1 project — 项目空间管理

### 全局标志
- `-f, --format string` — 输出格式
- `-q, --quiet` — 仅输出 ID

---

## 项目基础操作

### project list
列出项目。
- `-k, --keyword string` — 搜索关键词
- `--project-set` — 列出项目集

### project get <project-id>
查看项目详情（含创建人 Creator 字段）。

### project link [keyword-or-id]
绑定当前目录到项目空间。

### project unlink [id]
移除项目绑定。
- `--all` — 移除所有绑定

---

## 工作项管理（project workitem）

> **字段发现原则**：本节所有过滤字段、可写字段 flag 及字段别名均**由代码字段注册表驱动**。文档仅描述语法契约和典型用法；**具体字段清单以查询为准**：
> - 项目下所有字段及 CLI 别名：`a1 project workitem field list --project <id> --scope project`
> - 特定类型字段详情：`a1 project workitem field list --project <id> --type <type>`
> - 字段候选值：`a1 project workitem field options <field> --project <id> --type <type>`
> - 命令完整 flag 列表：`a1 project workitem <list|create|update> --help`

### project workitem list
列出工作项。未指定 `--project` 且未关联项目时，查询个人空间（跨项目）。所有系统字段 flag 均支持名称解析。

- `--project string` — 项目 ID（不指定则查个人空间）
- `--view string` — 应用已保存视图的过滤/列/排序设置查询；显式 `--filter`/`--columns`/`--sort` 优先于视图默认值
- `--category string` — 类别（逗号分隔）：`req`（需求）/ `bug`（缺陷）/ `task`（任务）/ `risk`（风险）/ `nodeflownode`（节点）/ `plugintask`；中文别名 `需求/缺陷/任务/风险/节点` 亦可；省略列出默认集合。**默认排除 PluginTask**；如需包含请显式 `--category plugintask`（替代已移除的 `--all`）
- `--filter string` — 过滤表达式，支持布尔组合（AND/OR/NOT）和比较操作符（`=`, `!=`, `~`, `!~`, `>`, `>=`, `<`, `<=`, `=[a,b]` 范围）
- `--cfs strings` — 自定义字段过滤 key=value（显示名或数字 ID），可重复
- `--scope string` — 查询范围：`personal`/`project`/`team`/`all`/`collect`/`associate`/`child`（**注意**：与 `project workitem field list --scope` 语义不同，后者枚举值仅为 `project`/`personal`）
- `--sort string` — 排序，格式 field:dir（如 gmtCreate:desc,priority:asc）
- `--columns strings` — 显示列，默认自动选择。列名支持三种写法：英文标识符（`id`,`title`,`status`,`priority`）、CLI 别名（`assignee`,`created`,`modified`）、中文显示名（`标题`,`状态`,`指派给`,`优先级`）。自定义字段可直接传入数字 ID（如 `100604`），表头自动渲染为字段中文名
- `--page int` — 页码（默认 1）
- `--page-size int` — 每页数量（默认 25）

**输出行为（空结果）：**
- 默认：向 stderr 输出 `No workitems found`
- `--format json`：向 stdout 输出 `[]`（便于脚本/Agent 解析）
- `--quiet`：完全静默，无任何输出

**过滤字段 flag 按字段注册表自动生成**，通过 `a1 project workitem list --help` 查看完整列表。按类型分组的行为约定：
- **列表类字段**（status, type, sprint, module, version, tag, priority, severity 及 user 类字段等）接受逗号分隔多值，语义为 OR（如 `--priority urgent,high`、`--module 前端,后端`）
- **文本/日期类字段**（title, description, created, modified 等）保持原始值不拆分
- **user 类字段**（assignee, creator, tracker, participant, verifier, operator, commentator, closer 等）接受**花名、账号、工号、邮箱**
- 字段与 CLI 别名对应关系见 `field list --scope project` 输出的 **ALIASES** 列

**--filter 表达式语法：**
- 比较操作符：`=`（等于）、`!=`（不等于）、`~`（包含）、`!~`（不包含）、`>`、`>=`、`<`、`<=`、`=[a,b]`（范围）
- 引号支持：值可用双引号或单引号包围（如 `subject~"登录"` → 按"登录"查询，引号被自动去除），适用于包含特殊字符的场景
- 空值判断：`field=""` 或 `field=null`（为空）、`field!=""` 或 `field!=null`（不为空）
- 多值：`status=Open,Reopen,Fixed`
- 布尔组合：`AND`、`OR`、`NOT`、`()`（优先级：NOT > AND > OR）
- 字段别名（反直觉或带命名空间的常见别名；**完整别名列表见 `field list --scope project` 输出的 ALIASES 列**）：
  - `assignee → assignedTo`、`type → workitemType`、`severity → seriousLevel`、`title → subject`、`id → identifier`
  - `created → gmtCreate`、`modified → gmtModified`、`archived → logicalStatus`
  - `tracker → workitem.tracker`、`participant → ak.issue.member`、`verifier → workitem.verifier`
  - `related-space → relatedSpace`、`closer → closedBy`、`space → spaceIdentifier`
- 自定义字段：支持显示名称（如 `计划开始日期>=2026-01-01`），自动解析为数字 ID
- 示例：`--filter 'status=Open AND priority=urgent'`、`--filter 'operator=八鹤'`、`--filter 'NOT status=Closed'`、`--filter 'created>=2026-01-01'`、`--filter 'archived=正常'`、`--filter 'subject~"登录"'`

> **`--filter` vs `--cfs`**：`--cfs` 仅支持 `=` 操作符，`--filter` 支持全部操作符和布尔组合。建议优先使用 `--filter`。

### project workitem get <id>
查看工作项详情。

### project workitem create
创建工作项。

> **可写字段 flag 由代码自动生成**：从字段注册表自动注册，与 update 命令一致。使用 `--help` 查看完整列表。

- `--project string` — 项目 ID（覆盖已绑定项目）
- `--category string` — 类别：**仅 `req` / `bug` / `task`**；其他类型（risk/nodeflownode/plugintask 等）请使用 `--type`。提供 `--type` 时 `--category` 可省略
- `--type string` — 工作项类型标识符或名称（如 '故事(STO)'），设置后可省略 --category
- `--body string` — 描述内容（Markdown 格式，本地图片自动上传图床）
- `--body-file string` — 从文件读取描述内容（Markdown 格式，本地图片自动上传图床）
- `--relation stringArray` — 创建时添加关联（格式: `<type>:<target>`，可重复）。类型: parent, sub, relate, blocks, blocked-by, duplicate, change, cr, tc, doc（doc 的 target 为 URL）
- `--cfs stringArray` — 自定义字段 key=value（可重复）。key 为字段标识符或显示名称，value 格式取决于字段类型
- `--attachment stringArray` — 本地文件路径（可重复，创建前自动上传）

**可写字段 flag 由字段注册表自动生成**，通过 `a1 project workitem create --help` 查看完整列表。常用字段（及其 CLI 别名）：
- `--title`（必填）、`--assignee`（alias `--owner`）、`--status`、`--priority`、`--severity`
- `--sprint`（aliases `--iteration`/`--milestone`）、`--module`（alias `--component`）、`--version`、`--tag`（alias `--label`）
- `--tracker`（aliases `--watcher`/`--follower`）、`--participant`（aliases `--member`/`--collaborator`）、`--verifier`（alias `--reviewer`）、`--related-space`（alias `--related-project`）
- 人员类字段输入：**花名、账号、工号、邮箱**（自动解析为 staffID）
- 枚举类字段（priority/severity 等）接受**英文标识符、中文别名或数字 ID**；具体候选值用 `field options <field> --type <type>` 查询

**--cfs 使用说明：**
- key 可以是字段的数字标识符（如 79）或显示名称（如 "计划开始日期"）
- value 格式取决于字段类型：
  - date 字段：`79=2024-01-01`
  - list/option 字段：`priority=medium` 或 `priority=中`（显示名或标识符均可）
  - multiList 字段：`100604=高,中`（逗号分隔多个值）
  - bool 字段：`160=是` 或 `160=否`
  - dynamic 字段：`141538=81369177`（按前缀搜索匹配）
  - input/string 字段：`123=文本内容`
  - int 字段：`101426=5`
  - float 字段：`100338=75.5`
- 使用 `a1 project workitem field list --type <type>` 查看可用字段及其类型
- 使用 `a1 project workitem field options <field> --type <type>` 查看字段可选值

### project workitem update <id>
更新工作项。支持更新系统字段、自定义字段、状态和描述。

**手动注册 flags：**
- `--body string` — 更新描述内容（Markdown 格式，本地图片自动上传图床）
- `--body-file string` — 从文件读取描述内容（Markdown 格式，本地图片自动上传图床）
- `--cfs stringArray` — 自定义字段 key=value（可重复，格式同 create 的 --cfs）

**可写字段 flag 由字段注册表自动生成**（与 create 命令同源），通过 `a1 project workitem update --help` 查看完整列表。常用字段与别名与 create 一致：`--title`、`--assignee`、`--status`、`--priority`、`--severity`、`--sprint`、`--module`、`--version`、`--tag`、`--tracker`、`--participant`、`--verifier`、`--related-space` 等。输入格式（人员字段支持花名/账号/工号/邮箱，枚举字段支持标识符/中文别名/数字 ID）也与 create 一致。

**输出：**
- `--format json` — JSON 格式输出变更摘要
- `--quiet` — 安静模式

### project workitem status <id>
变更工作项状态。
- `--to string` — 目标状态名称

> 注意：也可以使用 `a1 project workitem update <id> --status "目标状态"` 来更新状态。

### project workitem type list
列出项目可用的工作项类型。
- `--project string` — 项目 ID（覆盖已绑定项目）
- `--category string` — 按类别筛选：req / bug / task

### project workitem field list
列出工作项类型的所有字段定义（系统字段和自定义字段）。
- `--project string` — 项目 ID（覆盖已绑定项目）
- `--type string` — 工作项类型：接受数字标识符、类型名（如 `STO`）或显示名（如 `故事(STO)`）；不带 `--scope` 时必填
- `--scope string` — 列出所有字段（跨类型）：`project`（项目下全部字段）或 `personal`（个人空间字段）。**注意**：此处的 `--scope` 语义与 `project workitem list --scope` 不同（后者枚举值更广：personal/project/team/all/collect/associate/child），不要混淆

使用 `--scope project` 时自动列出项目下所有类型的全部字段，输出包含 **ALIASES** 列，显示每个字段对应的 CLI flag 名称。不带 `--scope` 时需指定 `--type`，输出包含格式、类名、类型、是否必填等详细信息。

### project workitem field options <field>
查看特定字段的可选值。根据字段类型自动路由到正确的 API：
- sprint/module/version/tag → 资源搜索 API
- user 字段 → 用户搜索 API
- space 字段 → 空间搜索 API
- product/business → 专用 fieldOption API
- dynamic 字段 → dynamicOptions API
- 其他 → getOptions API
- `--project string` — 项目 ID（覆盖已绑定项目）
- `--type string` — 工作项类型：接受数字标识符、类型名或显示名（自定义字段必填）
- `--query string` — 搜索过滤（用于搜索类字段如 sprint、module、user 等）

### project workitem comment create <id>
添加工作项评论，支持 @mention 自动解析、内联图片上传和回复已有评论。
- `-m, --message string` — 评论内容
  - `@花名` 自动解析为 `@花名(工号)` 格式，后端识别后触发钉钉通知
  - `![alt](本地图片路径)` 自动上传到图床并替换为托管 URL
- `--reply-to int` — 要回复的父评论 ID（从 comment list 输出中获取）

```bash
a1 project workitem comment create 80500194 -m "评论内容"
a1 project workitem comment create 80500194 -m "@八鹤 请看一下这个问题"
a1 project workitem comment create 80500194 -m "截图 ![bug](./screenshot.png)"
a1 project workitem comment create 80500194 -m "回复内容" --reply-to 119474898
```

### project workitem comment list <id>
列出工作项评论（按时间正序，最老在上）。输出格式：`id #序号 评论人 时间`，回复评论会显示 `↪ Reply to #序号`。

```bash
a1 project workitem comment list 80500194
a1 project workitem comment list 80500194 --format json
```

### project workitem activity <id>

查看工作项的变更动态（活动日志/时间线）。展示谁在什么时候把什么字段从什么值改成了什么值。

- `--sort string` — 排序方式：`desc`（默认，最新在前）或 `asc`（最旧在前）
- `--limit int` — 最多显示条数（默认 50，设为 0 显示全部）
- `-f, --format json` — JSON 格式输出

```bash
a1 project workitem activity 81887072
a1 project workitem activity 81887072 --sort asc
a1 project workitem activity 81887072 --limit 10
a1 project workitem activity 81887072 --format json
```

---

## 工作项创建/更新标准流程

### 创建工作项标准流程

创建工作项时，尤其是涉及自定义字段时，**必须**按以下步骤确保字段值合法，否则 API 可能因必填字段缺失或值不合法而拒绝请求：

```bash
# 步骤 1: 确认工作项类型
a1 project workitem type list --project <id> --category req
# → 选择合适的 type identifier（如 "9"、"故事(STO)"）

# 步骤 2: 获取字段定义，识别必填字段
a1 project workitem field list --project <id> --type <type>
# → 查看 REQUIRED 列为 true 的字段——这些必须提供值
# → 查看 FORMAT 列了解字段类型（date/list/multiList/bool/dynamic 等）

# 步骤 3: 查询候选值（对 list/multiList/bool/dynamic/sprint/module/user 等选项类字段）
a1 project workitem field options <field> --project <id> --type <type>
a1 project workitem field options <field> --project <id> --type <type> --query "关键词"
# → 从返回结果中选择正确的 identifier 作为 --cfs 的值

# 步骤 4: 构造创建命令，确保所有必填字段都有合法值
a1 project workitem create --project <id> --type <type> --title "标题" \
  --cfs <fieldId>=<value> --cfs <fieldId>=<value>
```

> **注意**：标题（subject）和项目 ID 总是必填。如果自定义必填字段未提供值，创建请求会被 API 拒绝。

### 更新工作项标准流程

更新工作项的自定义字段时，同样建议先查字段定义和候选值，以确保传入的值合法：

```bash
# 步骤 1: 查看字段定义（可省略如果已经知道字段标识符和类型）
a1 project workitem field list --project <id> --type <type>

# 步骤 2: 如需确认可选值
a1 project workitem field options <field> --project <id> --type <type>

# 步骤 3: 执行更新
a1 project workitem update <id> --cfs <fieldId>=<value> --title "新标题"
```

> 更新时只需提供要修改的字段，不需要提供所有字段。未提供的字段保持不变。

### project workitem delete <id>
删除工作项（不可恢复）。
- `-y, --yes` — 跳过确认提示
- `--quiet` — 静默模式，仅输出 ID
- `--format json` — JSON 格式输出

```bash
a1 project workitem delete 80928250          # 交互式确认
a1 project workitem delete 80928250 --yes    # 跳过确认
a1 project workitem delete 80928250 --format json
```

### project workitem relation add <id> <type>:<target>
给工作项添加关联。关联格式为 `<type>:<target>`，type 支持以下值：

| 类型 | 说明 | target 格式 |
|------|------|-------------|
| parent | 父工作项 | 工作项 ID |
| sub | 子工作项 | 工作项 ID |
| relate | 关联 | 工作项 ID |
| blocks | 前置阻塞 | 工作项 ID |
| blocked-by | 被阻塞 | 工作项 ID |
| duplicate | 重复 | 工作项 ID |
| change | 变更 | 变更 ID（仅支持 Aone Change） |
| cr | 代码评审 | CR ID |
| tc | 测试用例 | 用例 ID |
| doc | 文档/链接 | URL |

```bash
a1 project workitem relation add 80994397 parent:80994398
a1 project workitem relation add 80994397 relate:80994399
a1 project workitem relation add 80994397 change:CR12345
a1 project workitem relation add 80994397 doc:https://yuque.alibaba-inc.com/xxx/doc
```

### project workitem relation remove <id> <type>:<target>
移除工作项的关联。type 和 target 格式同 add。

```bash
a1 project workitem relation remove 80994397 relate:80994399
a1 project workitem relation remove 80994397 doc:https://yuque.alibaba-inc.com/xxx/doc
```

### project workitem relation list <id> [--category workitem|dev|doc]
列出工作项的所有关联，按类别分组展示。

**类别**：
- `workitem`：关联工作项（父项、子项、关联、阻塞、被阻塞、重复）
- `dev`：关联研发事项（Code Review、测试用例、变更）
- `doc`：关联文档（语雀、钉钉、其他链接、Done）

不指定 `--category` 时展示所有类别。

```bash
a1 project workitem relation list 81240965
a1 project workitem relation list 81240965 --category workitem
a1 project workitem relation list 81240965 --category dev
a1 project workitem relation list 81240965 --category doc
a1 project workitem relation list 81240965 --format json
```

### 工作项描述中的本地图片（自动上传）

`create --body` / `update --body` / `--body-file` 支持在描述中使用 Markdown 图片语法引用本地图片文件，CLI 会自动上传到图床并替换为托管 URL。

**格式**：标准的 Markdown 图片语法 `![alt](path)`，path 为本地文件路径。

**支持格式**：png, jpg, jpeg, gif, bmp, webp

**路径解析**：
- 绝对路径：`/Users/me/screenshot.png`
- 相对路径：基于 `--body-file` 文件所在目录解析（`--body` 直接传入时基于当前工作目录）

**示例**：
```bash
# 在描述中嵌入单张本地图片
a1 project workitem create --title "UI bug" --body '## 复现截图\n\n![screenshot](/tmp/bug.png)' --category bug --project 123

# 使用 --body-file，文件中可引用相对路径图片
a1 project workitem update 81460160 --body-file ./description.md
# description.md 内容示例：
# ## 问题说明
# ...
# ![复现步骤](./images/step1.png)
# ![结果](./images/result.png)
```

> **Agent 使用提示**：当用户提供截图或本地图片文件、且意图是创建/更新工作项描述时，应将图片路径以 `![描述](/path/to/image.png)` 写入 `--body`，而不是分析图片内容。CLI 负责处理上传和 URL 替换。

### project workitem attachment — 附件管理

管理工作项的附件，支持列表、上传、下载和删除。

### attachment list
列出工作项的附件。
```bash
a1 project workitem attachment list <id>
```

### attachment upload
上传文件作为工作项附件。
```bash
a1 project workitem attachment upload <id> <file-path> [--project <id>]
```

### attachment download
下载工作项附件。
```bash
a1 project workitem attachment download <id> <attachment-id> [-o <output-path>]
```
- `-o, --output string` — 输出文件路径（默认输出到 stdout）

### attachment delete
删除工作项附件（不可逆）。
```bash
a1 project workitem attachment delete <id> <attachment-id>
```

---

## 视图管理（project view）

管理工作项视图（保存的过滤/列/排序/分组配置）。完整 flag 用 `a1 project view <子命令> --help` 查看。

- `a1 project view list` — 列出视图
- `a1 project view get <view-id>` — 查看视图详情
- `a1 project view create --name "..."` — 创建视图
- `a1 project view update <view-id>` — 更新视图（读-改-写，未指定字段保持不变）
- `a1 project view delete <view-id>` — 删除视图

视图作用域：指定 `--project` 或已关联项目 → 项目空间；均未指定 → 个人空间；可用 `--scope personal/project` 强制切换。

---


## 用户组管理（project usergroup）

管理用户组（团队）。成员和管理员用逗号分隔的工号（staffId）指定。

- `a1 project usergroup list` — 列出我管理的用户组（含成员/管理员花名）
- `a1 project usergroup get <group-id>` — 查看用户组成员列表
- `a1 project usergroup create --name "..." --members <staffIds> --admins <staffIds>` — 创建用户组
- `a1 project usergroup update <group-id> [--name "..."] [--members <staffIds>] [--admins <staffIds>]` — 编辑用户组（只更新指定字段）
- `a1 project usergroup delete <group-id> [--yes]` — 删除用户组
- `a1 project usergroup search <query>` — 按名称搜索用户组

---
### staff list
按关键词搜索员工。
- `--query string` — 搜索关键词（姓名、工号等）

### staff get <employee-id>
查看员工详情。

---

## a1 telemetry — 遥测管理

### telemetry status
查看遥测状态。

### telemetry enable
启用遥测。

### telemetry disable
禁用遥测。

---

## a1 auth — 认证管理

### auth login
登录。
- `--buc` — 使用 BUC SSO 登录
- `--platform string` — 指定平台
- `--with-token` — 使用 token 登录

### auth logout
登出。
- `--platform string` — 指定平台

### auth whoami
查看当前登录用户。

---

## a1 link — 资源绑定

### link
交互式绑定当前目录到 Aone 资源（需要终端）。

### link status
查看当前绑定状态。

---

## a1 其他命令

### version
显示版本信息。

### update
更新到最新版本。

### completion <shell>
生成自动补全脚本（bash/zsh/fish/powershell）。
