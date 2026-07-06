---
name: autonomous-studio
description: >-
  从需求到上线的全链路研发流水线。管理阶段推进（需求→PRD→开发→验证→评审→部署→归档），
  注入行为规则到项目 CLAUDE.md，驱动子 Agent 按 PRD 自动开发。
  支持自主模式（由 autonomous-engine 接管持续自治循环）。
  使用场景：启动新功能开发、聊需求写 PRD、查看项目状态和进度、
  执行代码评审和验证、部署上线、
  或任何涉及研发流程阶段管理的操作。
model: sonnet
repository: https://code.alibaba-inc.com/qunbu/autonomous-studio
---

# Autonomous Studio v6.1

> **六阶段流水线**：需求→PRD→开发→验证→评审→部署，按需加载 phase 文件，不全读。
> **确定性 > LLM 自评**：hook 强制 + 确定性脚本兜底，提示词不是护栏。
> **worktree 隔离**：自主模式的改动进独立分支，main 永远安全，人审 diff 才合并。
> **自主模式 E2E 串行**：每批任务完成后必须功能 E2E 通过才进下一批（不攒到最后）。功能 E2E 跑不了（无浏览器/无平台登录态）→ 停自主循环，告诉用户"需你实跑 E2E"，不假装通过继续推阶段。E2E 方法见 `phases/phase-ship.md` ④。
>
> SKILL.md 负责激活 + 行为规则注入 + 阶段路由。
> 自主模式（持续自治循环）由 `autonomous-engine` skill 独立管理。
> 详细阶段规范在 `phases/` 下分文件，按需 Read 对应阶段文件，不要全读。

---

## Step 0（激活前）：Skill 自动更新检查

**每次 Studio 被激活时，先检查本地 skill 是否是最新版本。**

1. 检查本地版本标记：`cat ~/.claude/skills/autonomous-studio/.version 2>/dev/null`
2. 获取远程最新 commit：`git ls-remote https://xhq02486164:B06ESflq0Gg_cI_eYrrj@code.alibaba-inc.com/qunbu/autonomous-studio.git HEAD | cut -f1`
3. 比对：本地 hash ≠ 远程 hash → 需要更新
4. 更新方式：克隆仓库到 /tmp/_studio_update → 复制核心文件（SKILL.md、studio-inject.md、phases/、scripts/、hooks/、evals/）到 ~/.claude/skills/autonomous-studio/ → 写 .version → 清理
5. 更新后告知用户版本变化
6. 本地 hash = 远程 hash → 跳过，直接进入 Step 1

**此规则适用于所有 `qunbu/` 命名空间下的 skill。** 任何 skill 的 SKILL.md 中有 `repository:` 字段指向 `code.alibaba-inc.com/qunbu/*` 的，激活时都应执行同样的版本检查。

---

## Step 1: 激活时做什么

1. 读 `planning/status.json`（不存在则用阶段检测算法推断，并创建）
1.5. **安装 Studio Hook**（幂等）：`bash ~/.claude/skills/autonomous-studio/hooks/install-studio-hooks.sh`
2. **★ 将行为规则注入项目 CLAUDE.md**（用 `<!-- STUDIO:BEGIN/END -->` 标记包裹，已存在则替换）— 见 Step 2
3. 向用户报告：当前阶段 → 已有产出 → 下一步建议 → 可跳过的步骤
4. 用户说"自动模式/别等我"时 → 提示使用 `/autonomous-engine` 启动持续自治循环

### 阶段检测（status.json 不存在时）

按逆序检测，命中即停：
1. 有部署记录 → `done`
2. 有 review 提交 → `review`
3. 有业务代码变更 → `verification`
4. 有 `planning/prd.json` → `development`
5. 有 `planning/prd.md` → `development`（待生成 prd.json）
6. 有 `planning/requirements.md` → `prd`
7. 都没有 → `requirements`

### status.json 初始格式

关键字段：`currentStage`（当前阶段）、`completedStages`、`lastUpdated`、`taskType`（new-feature/bug-fix 等）、`locked`、`autoAdvance`。不存在时由阶段检测自动创建。

---

## Step 2: ★ 注入项目 CLAUDE.md（按需加载，避免重复）

**注入内容存放在独立文件 `studio-inject.md` 中，不内联在 SKILL.md 里。**

### 判断逻辑（先检查再决定是否加载）

1. 读项目 CLAUDE.md，检查是否包含 `<!-- STUDIO:BEGIN v6.1 -->`
2. **版本匹配**（含 `v6.1` 标记）→ **跳过注入**，不读 `studio-inject.md`，节省上下文
3. **版本不匹配**（含旧版本标记如 `v5.4`）→ Read `~/.claude/skills/autonomous-studio/studio-inject.md`，替换旧内容
4. **不存在标记** → Read `~/.claude/skills/autonomous-studio/studio-inject.md`，追加到文件末尾
5. **CLAUDE.md 不存在** → 创建文件，Read 并写入注入内容

---

## Hook 栈（确定性 backstop）

| Hook | 触发 | 作用 |
|---|---|---|
| `autonomous-commit-gate.py` | PreToolUse/Bash | 自治标记在时拦死对 main 的 commit/push/merge/reset/branch -D/update-ref |
| `stop-completion-gate.py` | Stop | 测试/任务/语法二元门控，未完成 exit 2 强制继续 |
| `post-edit-lint.py` | PostToolUse/Edit\|Write | 编辑后自动 py_compile/tsc/关联测试 |
| `patterns-write-gate.py` | PreToolUse/Edit\|Write | 阻断直接改 patterns.md（强制走 distill） |
| `discovery-gate.py` | PreToolUse+UserPromptSubmit | 项目初始化门禁，强制苏格拉底发现协议 |
| `pipeline-gate.py` | PreToolUse+Stop | 管线强制：改动前须 triage；complex 须 stage∈{development,verify} 才提交 |
| `decision-observer.py` | Stop+UserPromptSubmit | 决策日志 + 从 case 回读 outcome |
| `auto-commit.py` | Stop+SessionEnd | 项目变更自动 commit（自治标记在时跳过） |
| `resume-checkpoint.py` | SessionStart | 检查点恢复 + 引擎固件注入 |

**原则**：提示词不是护栏——LLM 可能绕过文本指令，bash exit 2 不可协商。

---

## 六阶段 Studio 流水线

需求 → PRD → 技术方案 → 开发 → 验证 → 评审 → 部署。`phases/phase-{build,dev,ship}.md` 按需 Read，不全加载。

### 阶段速查

- ① 需求 → `demand-discovery` → requirements.md
- ② PRD → `pm-spec` → prd.md + prd-decisions.md + prd.json + test-cases.md
- ③ 开发 → `serial-agent-handoff` → 代码 + git push
- ③-V Validator（opus）→ 单任务三维度审查
- ③-R 全量对照（opus）→ 完整性 + 集成点 + 决策落地
- ④ 验证 → `verify` → 截图 + E2E
- ⑤ 评审 → `code-review` + `simplify`
- ⑥ 部署 → `prod-deploy`
- ⑦ 归档 → archive/ + retrospective.md

### 任务类型走哪些阶段

- 新功能：①→②→③→③-V→③-R→④→⑤→⑥→⑦
- 功能优化：②→③→③-V→③-R→④→⑤→⑥→⑦
- Bug 修复：③→③-V→④→⑤→⑥→⑦
- 文案/样式：③→④→⑥→⑦

### phase-dev ④ 并发构建

PRD 产出依赖 DAG（`blockedBy`）+ 文件所有权（`files`）→ `parallel-dispatch.sh` 每 task 一个 worktree（并发上限 4）→ `parallel-merge.sh` 按依赖序增量合并 + 集成测试 + blocked 隔离。

---

## 补充说明

### 与 /autonomous-engine 的关系

`/autonomous-studio` 和 `/autonomous-engine` 是**同一个 skill 的两个入口**，共享同一套代码库（`qunbu/autonomous-studio`）。

- **`/autonomous-studio`**（本命令）= 流水线入口（阶段推进、规则注入、phase 路由）
- **`/autonomous-engine`** = 自主模式入口（持续自治循环、worktree 隔离、确定性扫描、蒸馏闭环）
- 用户说"自动模式/别等我"→ 提示使用 `/autonomous-engine`

### 子代理决策手册
→ `~/.claude/skills/autonomous-studio/decision-agent-prompt.md`
→ 由自治循环按需加载，主会话不读取
