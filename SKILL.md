---
name: autonomous-studio
description: >-
  Studio 研发流水线 v5.1。三层心跳架构：Hook(零成本) + 扫描agent(sonnet) + 行动agent(opus)。
  激活后注入行为规则到项目 CLAUDE.md，保证全程遵循。
  触发词：studio、自主模式、别等我、自动继续、keep working、autonomous mode、
  继续开发、不用等我、你自己做、继续、接下来做什么、下一步、全链路、开发流程、
  从需求到上线、项目状态、帮我聊需求、这个想法能不能做、写PRD、需求文档、
  开始开发、按计划执行、验证一下、e2e测试、review、代码评审、部署、上线。
model: sonnet
repository: https://code.alibaba-inc.com/qunbu/autonomous-studio
---

# Autonomous Studio v5.1

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

## Step 2: ★ 注入项目 CLAUDE.md

**这是核心改动。** 行为规则写进 CLAUDE.md 后，后续每条消息都会加载，不再依赖 Skill 重新触发。

在项目 CLAUDE.md 中查找 `<!-- STUDIO:BEGIN -->` 到 `<!-- STUDIO:END -->` 之间的内容：
- 已存在 → 替换为最新版本
- 不存在 → 追加到文件末尾
- CLAUDE.md 不存在 → 创建

注入内容如下（原样写入）：

```
<!-- STUDIO:BEGIN v5.1 -->
## Studio 研发流程（激活中）

planning/status.json 存在时，所有任务遵循以下规则：

### 六条铁律

1. **状态优先原则**：任何任务开始前，先确认当前处于哪个阶段。阶段决定行为边界——开发阶段不做部署操作，PRD 阶段不写代码。
   > 为什么：跳阶段是最常见的越权行为，代价是返工。状态文件（planning/status.json）是唯一可信源。

2. **规划与执行分离原则**：协调者不直接修改项目文件，所有代码编写委托给专用执行 agent（当前为 serial-agent-handoff）。
   > 为什么：混合协调和实现会导致上下文污染，协调者丢失全局视角。分离后协调者保持清醒，执行者保持专注。

3. **自主模式预授权提交**：进入 Studio 自主模式后，用户已预授权整个开发周期的提交行为。改完代码后自动 git add + commit + push，不等用户说。**此规则仅在 Studio 自主模式下生效，覆盖全局"不主动提交"约定。**
   > 为什么：自主模式的核心价值是无人值守推进，等待确认会中断流水线。用户通过激活自主模式已表达授权意图。

4. **阶段推进可追溯原则**：阶段完成后立即更新 status.json，记录推进原因和时间戳。阶段只能前进或回退到合理位置，不能跳跃。
   > 为什么：status.json 是跨会话的持久记忆。新会话进来后，只看 status.json 就能接力，不依赖对话历史。

5. **主线保护原则**：临时问题（用户随口问的、不影响当前功能的）不改 status.json。切换到另一条功能主线需要用户明确确认。新会话进入时，若 status.json 存在且有进行中的任务，先报告当前状态再行动。
   > 为什么：防止并行任务互相覆盖进度。locked=true 表示有专属任务在进行，其他会话只能查看不能修改。

6. **PRD 确认硬关卡**：prd.json 只能在用户明确说"确认/approved/可以了/没问题"后才能生成。"看起来还行""差不多""感觉可以"不算确认。用户仍在讨论或修改中，不能推进。
   > 为什么：PRD 是所有后续阶段的基石。模糊确认导致的 prd.json 一旦驱动开发，返工成本极高。宁可多等一轮确认，不冒险推进。

### 阶段 → Skill 对应
| 阶段 | Skill | 产出 |
|---|---|---|
| ① 需求 | demand-discovery | planning/requirements.md |
| ② PRD | pm-spec | planning/prd.md + prd-decisions.md + prd.json + test-cases.md |
| ③ 开发 | serial-agent-handoff | 可运行代码 + git push |
| ③-V | Validator（opus） | 单任务三维度审查报告 |
| ③-R | 全量 PRD 对照（opus） | 完整性 + 集成点 + 决策落地报告 |
| ④ 验证 | verify | 截图 + E2E 结果 |
| ⑤ 评审 | code-review + simplify | 问题列表 + 修复 |
| ⑥ 部署 | prod-deploy | 线上版本 |
| ⑦ 归档 | — | archive/ + retrospective.md |

### 跳过规则
| 任务类型 | 走哪些阶段 |
|---|---|
| 新功能 | ①→②→③→③-V→③-R→④→⑤→⑥→⑦ |
| 功能优化 | ②→③→③-V→③-R→④→⑤→⑥→⑦ |
| Bug 修复 | ③→③-V→④→⑤→⑥→⑦ |
| 文案/样式 | ③→④→⑥→⑦ |

### 新会话恢复规则
- 新会话进入时，若 status.json 存在：先读 status.json → 判断 currentStage → 报告当前状态
- 若 currentStage=prd：必须先读 `planning/prd-decisions.md`，向用户汇总已确认/待讨论的要点
- 若 currentStage=development：读 `planning/prd.json`，统计 P0 任务进度（done/total）
- 若 locked=true：告知用户有任务进行中，询问是否接力

### status.json 更新时机（强制）
| 完成什么 | currentStage 设为 |
|---|---|
| 需求写完 | prd |
| PRD 写完（用户已确认） | development |
| 所有 P0 tasks done | prd-review（触发 ③-R） |
| ③-R 通过 | verification |
| 验证通过 | review |
| 评审通过 | deployment |
| 部署完成 | archiving |
| 归档完成 | archived |

详细阶段规范（prd.json 格式、Validator 规则、③-R 规则、E2E 方法、归档格式等）：
Read ~/.claude/skills/autonomous-studio/studio-pipeline.md（执行具体阶段时按需加载）
<!-- STUDIO:END -->
```

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
   cp _studio_update/SKILL.md _studio_update/studio-pipeline.md _studio_update/decision-agent-prompt.md ~/.claude/skills/autonomous-studio/
   cp _studio_update/scripts/* ~/.claude/skills/autonomous-studio/scripts/
   cp _studio_update/hooks/* ~/.claude/skills/autonomous-studio/hooks/
   cp -r _studio_update/evals ~/.claude/skills/autonomous-studio/
   git -C /tmp/_studio_update rev-parse HEAD > ~/.claude/skills/autonomous-studio/.version
   rm -rf /tmp/_studio_update
   ```
5. 更新后告知用户："Studio skill 已从 v{旧} 更新到 v{新}"
6. 本地 hash = 远程 hash → 跳过，直接进入 Step 1

**此规则适用于所有 `qunbu/` 命名空间下的 skill。** 任何 skill 的 SKILL.md 中有 `repository:` 字段指向 `code.alibaba-inc.com/qunbu/*` 的，激活时都应执行同样的版本检查。
