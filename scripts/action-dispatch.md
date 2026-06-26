# Studio 行动分发规则

> 主会话控制器在 Tier 1 扫描返回 `needsAction=true` 后，按 `actionType` 分发。

## 分发表

| actionType | 走哪条路径 | agent 模型 | 做什么 |
|---|---|---|---|
| `develop` | 路径 B（执行型） | opus（协调）+ sonnet（写代码） | 调 serial-agent-handoff 写代码 |
| `validate` | 路径 B（执行型） | opus | 单任务三维度 Validator |
| `prd-review` | 路径 B（执行型） | opus | ③-R 全量 PRD 对照评审 |
| `verify` | 路径 B（执行型） | opus | 按 test-cases 跑 E2E 验证 |
| `suggest` | 路径 A（建议型） | opus | 分析状态，输出建议，不动文件 |
| `advance_stage` | 主会话直接执行 | 无需 agent | 更新 status.json |
| `archive` | 路径 B（执行型） | opus | 归档 + 生成 retrospective.md |

## 路径 A：建议型（agent 只想不做）

```
spawn Agent:
  model: "opus"
  description: "Studio 建议"
  prompt: |
    读 {项目目录}/planning/status.json 和 prd.json。
    分析当前状态，输出建议的下一步行动。
    不执行任何修改，不改任何文件。
    输出格式：
    - 当前状态：...
    - 建议行动：...
    - 原因：...
```

主会话收到后 → 写 `.claude/memory/autonomous-suggestions.md` → 输出一行摘要。

## 路径 B：执行型（agent 想+做）

### actionType = develop

```
spawn Agent:
  model: "opus"  # 协调者，内部调 serial-agent-handoff（写代码用 sonnet）
  description: "Studio 开发执行"
  prompt: |
    你是开发执行 agent：可以读写项目代码文件并提交，但只能改当前 task 范围内的文件，不能越界改其他模块、不能动 prd.json 之外的 planning 文件、不能 git push 到主干。

    上下文：
    - 完整 prd.json：{项目目录}/planning/prd.json
    - PRD 决策记录：{项目目录}/planning/prd-decisions.md
    - 项目约定：{项目目录}/CLAUDE.md

    任务：
    找到下一个 status=pending 且 priority=P0 的任务。
    调用 serial-agent-handoff Skill 执行开发。
    写代码时使用 sonnet 模型（serial-agent-handoff 内部配置）。
    完成后更新 prd.json 中该任务的 status=done + completedAt。

    代码风格纪律（强制）：只改必须改的代码，保持文件现有命名/缩进/引号风格，不重构无关代码、不抽只用一次的公共函数、不重命名已有符号。diff 超 task 预期 2 倍就停下删多余改动。

    返回：完成的 task id + 标题。
```

### actionType = validate

```
spawn Agent:
  model: "opus"
  description: "Studio 单任务 Validator"
  prompt: |
    你是只读验证者（Validator）：可以读取项目所有文件并输出审查报告，但不能修改源代码（只有 prd.json 的 status/notes/retryCount 字段可改），不能 git commit/push。

    上下文（全量，不裁剪）：
    - 完整 prd.json：{项目目录}/planning/prd.json
    - PRD 决策记录：{项目目录}/planning/prd-decisions.md
    - 当前 task id：{task_id}
    - git diff：{diff内容}

    读 ~/.claude/skills/autonomous-studio/phases/phase-dev.md 的 ③-V 部分。
    按三维度（正确性 + 代码风格 + PRD 一致性）审查。
    输出标准格式的 Validator 报告。
    有 ❌ 时：更新 prd.json 该任务 status=pending + notes 写失败原因 + retryCount +1。
    仅 ⚠️ 时：不阻塞，记录建议。
    全 ✅ 时：维持 done 状态。
```

### actionType = prd-review

```
spawn Agent:
  model: "opus"
  description: "Studio ③-R 全量 PRD 对照评审"
  prompt: |
    上下文（全量）：
    - 完整 prd.json：{项目目录}/planning/prd.json
    - PRD 决策记录：{项目目录}/planning/prd-decisions.md
    - 测试用例：{项目目录}/planning/test-cases.md
    - git log（本次功能）：{git_log}

    读 ~/.claude/skills/autonomous-studio/phases/phase-dev.md 的 ③-R 部分。
    检查三件事：完整性 + 集成点 + PRD 决策落地。
    输出标准格式的全量对照报告。
    有 ❌ → 返回 needs_fix，列出具体遗漏。
    只有 ⚠️ → 返回 needs_confirm，输出给用户决定。
    全 ✅ → 返回 passed。
```

### actionType = verify

```
spawn Agent:
  model: "opus"
  description: "Studio E2E 验证"
  prompt: |
    你是 E2E 验证 agent：可以运行测试和只读命令验证功能，但不能改源代码（发现缺陷只报告，修复交给 develop 路径）。

    上下文：
    - 完整 prd.json：{项目目录}/planning/prd.json
    - 测试用例：{项目目录}/planning/test-cases.md

    读 ~/.claude/skills/autonomous-studio/phases/phase-ship.md 的 ④ 验证部分。
    按规范执行 E2E 验证。
    返回：通过/失败 + 详情。
```

### actionType = archive

```
spawn Agent:
  model: "opus"
  description: "Studio 归档"
  prompt: |
    上下文：
    - 完整 prd.json：{项目目录}/planning/prd.json
    - PRD 决策记录：{项目目录}/planning/prd-decisions.md
    - status.json：{项目目录}/planning/status.json

    读 ~/.claude/skills/autonomous-studio/phases/phase-ship.md 的 ⑦ 归档部分。
    执行归档流程：创建 archive/ 目录、复制 planning/、生成 retrospective.md。
    扫描 {项目根目录}/archive/*/retrospective.md，提取历史教训标签到 known-pitfalls.md（为下个项目准备）。
    返回：归档路径 + 教训条数。
```

### actionType = advance_stage

不 spawn agent，主会话直接执行：
1. 读 status.json 当前 currentStage
2. 按阶段推进表更新 currentStage
3. completedStages 加入已完成阶段
4. lastUpdated 更新为当前时间

## 主会话控制器：行动 agent 返回后

无论走哪条路径，行动 agent 返回后主会话统一执行：

1. **有代码变更** → 自主模式下用 `bash scripts/opt-worktree.sh commit <area:subdirection> "<说明>"`（进 optimization worktree 等人工审，不直接碰 main——autonomous-commit-gate 会拦）；非自主模式（用户指挥）才直接 `git add + commit`
2. **阶段推进** → 更新 `status.json`
3. **输出摘要** → `Studio {阶段} @ {时间} | {摘要}`
4. **建议类** → 追加到 `.claude/memory/autonomous-suggestions.md`
5. **③-R 返回 needs_fix** → 回到 develop 路径补充实现
6. **③-R 返回 passed** → advance_stage 到 verification

主会话是唯一有权执行 git 操作和更新 status.json 的角色。
