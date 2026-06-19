---
name: autonomous-studio
description: >-
  Studio 研发流水线 v5.0。三层心跳架构：Hook(零成本) + 扫描agent(sonnet) + 行动agent(opus)。
  激活后注入行为规则到项目 CLAUDE.md，保证全程遵循。
  触发词：studio、自主模式、别等我、自动继续、keep working、autonomous mode、
  继续开发、不用等我、你自己做、继续、接下来做什么、下一步、全链路、开发流程、
  从需求到上线、项目状态、帮我聊需求、这个想法能不能做、写PRD、需求文档、
  开始开发、按计划执行、验证一下、e2e测试、review、代码评审、部署、上线。
model: sonnet
repository: https://code.alibaba-inc.com/qunbu/autonomous-studio
---

# Autonomous Studio v5.0

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
<!-- STUDIO:BEGIN -->
## Studio 研发流程（激活中）

planning/status.json 存在时，所有任务遵循以下规则：

### 五条铁律
1. **阶段感知**：收到任何开发任务，先读 planning/status.json 判断当前阶段
2. **开发用 Agent**：写代码必须调用 serial-agent-handoff Skill（通过 Skill 工具），不直接编辑项目文件
3. **自动提交**：改完代码后自动 git add + commit + push，不等用户说
4. **更新状态**：阶段完成后立即更新 status.json（currentStage → 下一阶段，completedStages 加入已完成阶段）
5. **主线保护**：临时问题不改 status.json；切换主线需用户确认；新对话进入时若 locked=true，主动报告当前状态

### 阶段 → Skill 对应
| 阶段 | Skill | 产出 |
|---|---|---|
| ① 需求 | demand-discovery | planning/requirements.md |
| ② PRD | pm-spec | planning/prd.md + prd.json + test-cases.md |
| ③ 开发 | serial-agent-handoff | 可运行代码 + git push |
| ④ 验证 | verify | 截图 + E2E 结果 |
| ⑤ 评审 | code-review + simplify | 问题列表 + 修复 |
| ⑥ 部署 | prod-deploy | 线上版本 |

### 跳过规则
| 任务类型 | 走哪些阶段 |
|---|---|
| 新功能 | ①→②→③→④→⑤→⑥ |
| 功能优化 | ②→③→④→⑤→⑥ |
| Bug 修复 | ③→④→⑤→⑥ |
| 文案/样式 | ③→④→⑥ |

### status.json 更新时机（强制）
| 完成什么 | currentStage 设为 |
|---|---|
| 需求写完 | prd |
| PRD 写完 | development |
| 开发完成 | verification |
| 验证通过 | review |
| 评审通过 | deployment |
| 部署完成 | done |

详细阶段规范（prd.json 格式、Validator 规则、E2E 方法等）：
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
   → ★ 输出校验：如果返回不是合法 JSON 或不含 needsAction 字段 → 丢弃，视为 needsAction=false

3. Tier 2 行动: spawn Agent (model: opus)
   → Read scripts/action-dispatch.md 按 actionType 分发
   → 返回执行结果
   → ★ 输出校验：如果返回不含 <decision> 标签且超过 500 字符 → 截断为摘要，记录异常

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
