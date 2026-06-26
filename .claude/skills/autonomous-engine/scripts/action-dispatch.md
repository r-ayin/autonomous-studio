# Studio 行动分发规则

> 主会话控制器在 Tier 1 扫描返回 `needsAction=true` 后，按 `actionType` 分发。

## 分发表

| actionType | 走哪条路径 | agent 模型 | 做什么 |
|---|---|---|---|
| `develop` | 路径 B（执行型） | opus | 调 serial-agent-handoff 写代码 |
| `verify` | 路径 B（执行型） | opus | 按 test-cases 跑验证 |
| `suggest` | 路径 A（建议型） | opus | 分析状态，输出建议，不动文件 |
| `advance_stage` | 主会话直接执行 | 无需 agent | 更新 status.json |

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
  model: "opus"
  description: "Studio 开发执行"
  prompt: |
    读取 {项目目录}/planning/prd.json。
    找到下一个 status=pending 且 priority=P0 的任务。
    调用 serial-agent-handoff Skill 执行开发。
    完成后更新 prd.json 中该任务的 status=done + completedAt。
    返回：完成的 task id + 标题。
```

### actionType = verify

```
spawn Agent:
  model: "opus"
  description: "Studio 验证执行"
  prompt: |
    读取 {项目目录}/planning/prd.json 和 test-cases.md。
    读 ~/.claude/skills/autonomous-studio/studio-pipeline.md 的验证部分（④ 验证）。
    按规范执行验证。
    返回：通过/失败 + 详情。
```

### actionType = advance_stage

不 spawn agent，主会话直接执行：
1. 读 status.json 当前 currentStage
2. 按阶段推进表更新 currentStage
3. completedStages 加入已完成阶段
4. lastUpdated 更新为当前时间

## 主会话控制器：行动 agent 返回后

无论走哪条路径，行动 agent 返回后主会话统一执行：

1. **有代码变更** → `git add + commit + push`
2. **阶段推进** → 更新 `status.json`
3. **输出摘要** → `Studio {阶段} @ {时间} | {摘要}`
4. **建议类** → 追加到 `.claude/memory/autonomous-suggestions.md`

主会话是唯一有权执行 git 操作和更新 status.json 的角色。
