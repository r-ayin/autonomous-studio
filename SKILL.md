---
name: autonomous-studio
description: >-
  Studio 研发流水线 v5.3。三层心跳架构：Hook(零成本) + 扫描agent(sonnet) + 行动agent(opus)。
  激活后注入行为规则到项目 CLAUDE.md，保证全程遵循。
  触发词：studio、自主模式、别等我、自动继续、keep working、autonomous mode、
  继续开发、不用等我、你自己做、继续、接下来做什么、下一步、全链路、开发流程、
  从需求到上线、项目状态、帮我聊需求、这个想法能不能做、写PRD、需求文档、
  开始开发、按计划执行、验证一下、e2e测试、review、代码评审、部署、上线。
model: sonnet
repository: https://code.alibaba-inc.com/qunbu/autonomous-studio
---

# Autonomous Studio v5.3

> 三层心跳架构：Tier 0 Hook（零成本）→ Tier 1 扫描 sonnet（低成本）→ Tier 2 行动 opus（按需）。
> SKILL.md 负责激活 + 行为规则注入。详细阶段规范在 `studio-pipeline.md`，按需 Read。

---

## Step 1: 激活时做什么

1. 读 `planning/status.json`（不存在则用阶段检测算法推断，并创建）
1.5. **安装 Studio Hook**（幂等）：`bash ~/.claude/skills/autonomous-studio/hooks/install-studio-hooks.sh`
2. **★ 将行为规则注入项目 CLAUDE.md**（用 `<!-- STUDIO:BEGIN/END -->` 标记包裹，已存在则替换）
3. 向用户报告：当前阶段 → 已有产出 → 下一步建议 → 可跳过的步骤
4. 用户说"自动模式/别等我"时 → 额外设置心跳（见 Step 3）

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

```json
{
  "currentStage": "requirements",
  "completedStages": [],
  "lastUpdated": "ISO时间",
  "taskType": "new-feature",
  "notes": "项目描述",
  "locked": true,
  "autoAdvance": true
}
```

---

## Step 2: ★ 注入项目 CLAUDE.md（按需加载，避免重复）

**注入内容存放在独立文件 `studio-inject.md` 中，不内联在 SKILL.md 里。**

### 判断逻辑（先检查再决定是否加载）

1. 读项目 CLAUDE.md，检查是否包含 `<!-- STUDIO:BEGIN v5.3 -->`
2. **版本匹配**（含 `v5.3` 标记）→ **跳过注入**，不读 `studio-inject.md`，节省上下文
3. **版本不匹配**（含旧版本标记如 `v5.0`）→ Read `~/.claude/skills/autonomous-studio/studio-inject.md`，替换旧内容
4. **不存在标记** → Read `~/.claude/skills/autonomous-studio/studio-inject.md`，追加到文件末尾
5. **CLAUDE.md 不存在** → 创建文件，Read 并写入注入内容

> 为什么这样设计：注入内容约 70 行，写在 SKILL.md 里会让每次激活都加载这些内容到上下文。
> 一旦注入到项目 CLAUDE.md，后续每轮对话自动加载，SKILL.md 里再放一份就是双倍浪费。
> 分离后，首次激活多读一个文件，后续激活零额外开销。

---

## Step 3: 三层心跳架构（用户说"自动模式"时设置）

### 架构概览

| 层级 | 模型 | 触发 | 职责 |
|---|---|---|---|
| Tier 0 Hook | 无（shell） | 每次 Write/Edit | 格式验证、进度统计、提交提醒 |
| Tier 1 扫描 | sonnet | 每 7/60 分钟 | 快速诊断：要不要行动？ |
| Tier 2 行动 | opus | 按需 | 写代码/跑验证/出建议 |
| 主会话控制器 | — | 行动完成后 | git commit + status.json + 通知 |

原则：不需要 AI → Hook。需要判断 → sonnet 扫描。需要行动 → opus 执行。权限操作 → 主会话。

### CronCreate 流程（L2 每 7 分钟 / L3 每 60 分钟）

```
1. 预检: bash scripts/studio-precheck.sh {项目目录}
   → skip → 静默退出

2. Tier 1 扫描: spawn Agent (model: sonnet)
   → Read scripts/scanner-prompt.md 作为 prompt
   → 返回 JSON: {needsAction, actionType, reason}
   → needsAction=false → 静默退出

3. Tier 2 行动: spawn Agent (model: opus)
   → Read scripts/action-dispatch.md 按 actionType 分发
   → 返回执行结果

4. 主会话控制器: git commit + status.json + 输出摘要
```

### 渐进式加载的文件

| 文件 | 谁加载 | 何时加载 |
|---|---|---|
| `scripts/studio-precheck.sh` | Cron prompt | 每次心跳第一步 |
| `scripts/scanner-prompt.md` | Tier 1 扫描 agent | 预检通过后 |
| `scripts/action-dispatch.md` | 主会话控制器 | 扫描返回 needsAction=true 后 |
| `studio-inject.md` | 主会话 Step 2 | 项目 CLAUDE.md 无标记或版本不匹配时 |
| `studio-pipeline.md` | Tier 2 行动 agent | 执行具体阶段时 |
| `decision-agent-prompt.md` | Tier 2 行动 agent | L3 深度分析时 |

---

## 补充说明

### 详细规范文件
各阶段的详细规范（PRD 格式、prd.json 格式、Validator 规则、E2E 测试方法、双模型分工等）：
→ `~/.claude/skills/autonomous-studio/studio-pipeline.md`
→ 仅在执行具体阶段时 Read，不常驻上下文

### 子代理决策手册
→ `~/.claude/skills/autonomous-studio/decision-agent-prompt.md`
→ 由 Tier 2 行动 agent 按需加载，主会话不读取

---

## Step 0（激活前）：Skill 自动更新检查

**每次 Studio 被激活时，先检查本地 skill 是否是最新版本。**

1. 检查本地版本标记：`cat ~/.claude/skills/autonomous-studio/.version 2>/dev/null`
2. 获取远程最新 commit：`git ls-remote https://xhq02486164:B06ESflq0Gg_cI_eYrrj@code.alibaba-inc.com/qunbu/autonomous-studio.git HEAD | cut -f1`
3. 比对：本地 hash ≠ 远程 hash → 需要更新
4. 更新方式：
   ```bash
   cd /tmp && rm -rf _studio_update
   git clone https://xhq02486164:B06ESflq0Gg_cI_eYrrj@code.alibaba-inc.com/qunbu/autonomous-studio.git _studio_update
   cp _studio_update/SKILL.md _studio_update/studio-pipeline.md _studio_update/decision-agent-prompt.md _studio_update/studio-inject.md ~/.claude/skills/autonomous-studio/
   cp _studio_update/scripts/* ~/.claude/skills/autonomous-studio/scripts/
   cp _studio_update/hooks/* ~/.claude/skills/autonomous-studio/hooks/
   cp -r _studio_update/evals ~/.claude/skills/autonomous-studio/
   git -C /tmp/_studio_update rev-parse HEAD > ~/.claude/skills/autonomous-studio/.version
   rm -rf /tmp/_studio_update
   ```
5. 更新后告知用户："Studio skill 已从 v{旧} 更新到 v{新}"
6. 本地 hash = 远程 hash → 跳过，直接进入 Step 1

**此规则适用于所有 `qunbu/` 命名空间下的 skill。** 任何 skill 的 SKILL.md 中有 `repository:` 字段指向 `code.alibaba-inc.com/qunbu/*` 的，激活时都应执行同样的版本检查。
