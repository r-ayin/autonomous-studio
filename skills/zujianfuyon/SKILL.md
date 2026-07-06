---
name: zujianfuyon
version: 1.0.1
description: 组件复用库 — 公共可复用组件仓库（gitlab.alibaba-inc.com/xiqxhq/zujianfuyon）。触发词："用组件仓库的 xxx"、"从组件仓库拉取"、"有没有现成组件"、"写入组件仓库"、"抽离到复用仓库"。支持拉取组件到当前项目、或将代码抽离收录到仓库（推送前需用户确认）。
metadata:
  author: xiqxhq
  triggers:
    - 复用这个组件
    - 组件仓库
    - 写入复用仓库
    - 从仓库拉取
    - 抽离组件
    - 有没有现成的
    - 拉取组件
repository: https://code.alibaba-inc.com/qunbu/zujianfuyon
---

# 组件复用库（zujianfuyon）

通用可复用组件仓库，支持从仓库拉取组件到项目、或将业务代码抽离收录到仓库。

## 仓库信息

- **地址**：`https://gitlab.alibaba-inc.com/xiqxhq/zujianfuyon.git`
- **本地克隆路径**：`/tmp/zujianfuyon`（如不存在则自动克隆）
- **分支**：`master`
- **读取**：完全公开，无需鉴权
- **写入**：需要用户自己的 GitLab 凭据，且推送前必须经用户确认

---

## When to Use

### 浏览组件

用户问"有没有现成的 xxx 组件"、"组件仓库里有什么"、"看看组件库"。

### 拉取组件

用户说"从组件仓库拉取 xxx"、"用组件仓库的 xxx"、"把那个 xxx 组件拿过来"。

### 写入 / 更新组件

用户说"写入组件仓库"、"抽离到复用仓库"、"更新组件仓库的 xxx"。

---

## 快速浏览（无需克隆）

当用户**仅想浏览**组件列表时，直接读取 `references/component-index.md`（仓库 README.md 的快照），无需执行任何 git 操作。

```
读取路径（技能目录下的相对路径）：references/component-index.md
```

> 注意：实际拉取或写入操作时，以克隆仓库中的最新内容为准。

---

## 共用步骤 — 克隆 / 更新仓库

所有涉及实际文件操作的流程（拉取、写入、更新），都先执行此步骤：

```bash
# 使用技能内置脚本（路径需替换为 SKILL.md 所在目录的绝对路径）
bash <SKILL_DIR>/scripts/ensure-repo
```

其中 `<SKILL_DIR>` 是本 SKILL.md 文件所在目录的绝对路径（如 `~/.claude/skills/zujianfuyon`）。

如果克隆失败（网络不可达等），对于读取操作回退到 `references/component-index.md`；对于写入操作则报错终止。

---

## 读取流程 — 从仓库拉取组件

### Step 1: 克隆/更新仓库

执行上述"共用步骤"。

### Step 2: 查看可用组件

```bash
cat /tmp/zujianfuyon/README.md
```

根据用户需求匹配合适的组件。如果不确定用户需要哪个，展示组件列表让用户选择。

### Step 3: 查看组件详情

```bash
cat /tmp/zujianfuyon/<component-name>/README.md
```

向用户展示组件的用途、依赖、使用示例，确认是否符合需求。

### Step 4: 复制组件到当前项目

```bash
cp -r /tmp/zujianfuyon/<component-name>/ <用户指定的目标路径>/
```

如果用户没指定路径，根据项目结构智能推荐（如 `src/components/`、`src/lib/` 等）。

### Step 5: 适配业务

- 根据当前项目的路径别名（如 `@/`、`~/`）调整 import 路径
- 注入业务配置（URL、Key 等）到调用代码中
- 提醒用户：**如需定制，请在业务层 wrap 一层，不要直接修改组件源码**

### 错误处理

- 没有匹配的组件 → 展示完整组件列表，询问用户是否需要其中某个
- 组件依赖缺失 → 根据组件 README.md 中的依赖声明，提示用户安装

---

## 写入流程 — 抽离组件到仓库（含确认门）

> **重要：写入流程的推送步骤必须经过用户明确确认，AI 不得自动执行 git push。**

### Step 1: 克隆/更新仓库

执行"共用步骤"。

如果仓库有未提交的脏状态，先执行 `git -C /tmp/zujianfuyon status` 展示给用户，询问是否清理（`git checkout .`）后继续。

### Step 2: 读取编码规范

```bash
cat /tmp/zujianfuyon/CLAUDE.md
```

**必须内化其中的编码原则和检查清单后才能开始生成代码。**

### Step 3: 确认组件名

- 询问用户组件名称（如未提供）
- 名称必须是 **kebab-case**（如 `date-range-picker`、`dingtalk-robot`）
- 检查 `/tmp/zujianfuyon/<name>/` 是否已存在：
  - 已存在 → 提示用户"该组件已存在，是要更新它还是换个名字？"
  - 不存在 → 继续

### Step 4: 生成组件文件

在 `/tmp/zujianfuyon/<component-name>/` 下创建：

1. **实现文件**（`.ts` / `.tsx`）— 从业务代码中提取，按检查清单剥离业务逻辑
2. **`index.ts`** — 统一导出所有公开 API 和类型
3. **`README.md`** — 包含：
   - 用途说明
   - 依赖声明
   - 快速使用示例
   - 完整 API / Props 说明

### Step 5: 更新根目录索引

编辑 `/tmp/zujianfuyon/README.md`，在"组件目录（可复用代码）"表格中添加一行：

```markdown
| [组件名](./component-name/) | `component-name/` | 用途描述 | 依赖说明 |
```

### Step 6: Stage 并展示变更（确认门）

```bash
cd /tmp/zujianfuyon
git add <component-name>/ README.md
git diff --cached --stat
git diff --cached
```

**AI 必须在此处展示以下格式的摘要，然后停下等待用户回复：**

```
===== 待提交内容 =====
操作类型：新增组件
组件名称：<component-name>

文件清单：
  <component-name>/index.ts
  <component-name>/<impl>.ts
  <component-name>/README.md
  README.md（索引更新）

Diff 摘要：
  <git diff --cached --stat 的输出>

Commit 消息将为：
  feat: <component-name>（<一句话说明>）

推送目标：origin master
======================

回复 YES 确认推送，回复 NO 取消并保留本地文件。
```

**⚠️ AI 在此处必须停下！不得自动执行 git commit 或 git push。等待用户明确回复。**

### Step 7: 根据用户回复执行

**如果用户回复 YES / 确认 / 推送 / y：**

先检测推送凭据：

```bash
git -C /tmp/zujianfuyon push --dry-run origin master 2>&1
```

- **dry-run 成功** → 执行提交和推送：
  ```bash
  cd /tmp/zujianfuyon
  git commit -m "feat: <component-name>（<一句话说明>）"
  git push origin master
  ```
  报告 commit hash，确认推送成功。

- **dry-run 失败** → 跳转到下方"首次写入设置"章节，引导用户配置凭据后重试。

**如果用户回复 NO / 取消 / n：**

```bash
git -C /tmp/zujianfuyon reset HEAD
```

提示："已取消。本地文件保留在 `/tmp/zujianfuyon/<component-name>/`，可以继续修改后重新确认。"

---

## 更新流程 — 修改已有组件

与写入流程相同，但有以下区别：

- **跳过** Step 3 的冲突检查（组件已存在是预期行为）
- **Step 4** 改为修改已有文件，而非创建新文件夹
- **Step 5** 仅在新增了导出项时才更新索引
- **Step 6** 的 Commit 消息格式改为：
  - 修复：`fix: <component-name> <修复内容>`
  - 新增能力：`feat: <component-name> <新增能力>`
- 同样有**确认门**，不得自动推送

---

## 首次写入设置（GitLab 凭据）

当 `git push --dry-run` 失败时，引导用户配置：

### 说明

写入组件仓库需要 GitLab 凭据，这是一次性配置。

### 配置步骤

1. **获取 Personal Access Token**

   访问 `https://gitlab.alibaba-inc.com/-/profile/personal_access_tokens`，创建一个 Token：
   - 名称：随意（如 `zujianfuyon-push`）
   - 权限范围：勾选 `write_repository`
   - 复制生成的 Token

2. **配置 Git 凭据**

   ```bash
   git config --global credential.helper store
   ```

   然后让用户提供工号和 Token，执行：

   ```bash
   git -C /tmp/zujianfuyon credential approve <<EOF
   protocol=https
   host=gitlab.alibaba-inc.com
   username=<工号>
   password=<PAT>
   EOF
   ```

3. **验证**

   ```bash
   git -C /tmp/zujianfuyon push --dry-run origin master 2>&1
   ```

   如果成功，返回继续之前的推送流程。

---

## 剥离检查清单（AI 自检用）

将代码抽离到组件仓库前，AI 必须逐项确认：

- [ ] 移除所有来自业务项目的 import 路径（`@/store`、`../services/xxx` 等）
- [ ] 移除所有写死的 URL、Token、用户名
- [ ] 移除对全局状态的依赖（localStorage key 改为参数传入）
- [ ] 移除业务专属 type（改为泛型或组件内部定义）
- [ ] 确认组件在空项目中 import 无报错
- [ ] README 中的示例代码可独立运行

---

## 组件命名与结构规范

| 规则 | 说明 |
|------|------|
| 命名格式 | kebab-case（如 `dingtalk-mcp-client`、`echarts-bar`） |
| 必需文件 | 每个组件必须有 `index.ts` 和 `README.md` |
| 配置方式 | 允许提供 DEFAULT 常量，但必须支持参数覆盖 |
| 依赖原则 | 优先浏览器原生 API，最小化外部依赖 |
| 类型导出 | 所有公开 API 和类型必须通过 `index.ts` 统一导出 |

---

## Notes

### 脏状态处理

如果 `/tmp/zujianfuyon` 存在未提交的修改（上次操作残留），先执行 `git status` 展示给用户，询问处理方式后再继续。

### shadcn-ui 和 antd-components

仓库中的 `shadcn-ui/`（55 个组件）和 `antd-components/`（74 个组件）是**预置的参考组件集**，属于只读浏览区。用户可以从中复制单个文件到项目使用，但不通过此 skill 对它们进行增删改。

### 同名冲突

如果用户要写入的组件名已存在于仓库中，读取现有组件的 README.md，展示对比信息，让用户选择"更新"还是"重命名"。

### pages 目录

`pages/` 目录是组件库的在线浏览索引页面，仅供浏览器中查看，不参与组件拉取流程。
