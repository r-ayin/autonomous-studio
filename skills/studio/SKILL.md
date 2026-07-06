---
name: studio
description: |
  研发 Studio — 状态感知的研发流程路由器。自动检测项目当前走到哪一步，告诉你下一步该做什么。
repository: https://code.alibaba-inc.com/qunbu/autonomous-studio
triggers:
  - "接下来做什么"
  - "下一步"
  - "studio"
  - "全链路"
  - "开发流程"
  - "从需求到上线"
  - "项目状态"
sync:
  # 任何对话中更新此 Skill 后，执行以下命令同步到仓库：
  # cd /tmp/autonomous-studio && git pull origin main && vim skills/studio/SKILL.md && git add skills/studio/SKILL.md && git commit -m "feat(studio): 更新 SKILL.md" && git push origin main
  target_repo: "https://xhq02486164:B06ESflq0Gg_cI_eYrrj@code.alibaba-inc.com/qunbu/autonomous-studio.git"
  target_path: "skills/studio/SKILL.md"
version: 1.0.0
---

# 研发 Studio — 流程路由器

被触发时，先检测项目当前状态，再建议下一步。不是菜单，是导航。

---

## 第一步：检测当前阶段

读取项目目录下的 `.planning/` 文件夹，根据已有产出物判断走到了哪一步：

```
检测顺序（从后往前查，找到最新的产出物即为当前阶段）：

1. 线上已部署？        → 检查最近的 git tag 或部署记录
2. 有代码评审记录？    → 检查最近的 git log 是否有 review/CR 相关提交
3. 有新代码变更？      → 检查 git diff 是否有未提交或最近提交的业务代码
4. 有技术方案？        → 检查 .planning/tech-plan.md 是否存在
5. 有 PRD？           → 检查 .planning/prd.md 是否存在
6. 有需求描述？        → 检查 .planning/requirements.md 是否存在
7. 都没有             → 从需求探索开始
```

## 第二步：报告状态 + 建议下一步

检测完成后，输出：

```
当前状态：[阶段名]
已完成：[列出已有的产出物]
下一步建议：[具体建议，含触发词]
可跳过的步骤：[如果是小改动，哪些步骤可以跳]
```

---

## 研发流程（7 阶段）

```
需求 → PRD → 技术方案 → 开发 → 验证 → 评审 → 部署
        ↑                              ↓
        └──── 验证不通过时回退 ─────────┘
```

### ① 需求探索

| 项目 | 说明 |
|------|------|
| **Skill** | `demand-discovery`（含 grill-me 压力追问） |
| **触发** | "帮我聊需求"、"这个想法能不能做" |
| **输入** | 一句话想法 |
| **产出** | `.planning/requirements.md` |
| **下一步** | 自动建议"要不要写 PRD？" |

### ② 写 PRD

| 项目 | 说明 |
|------|------|
| **Skill** | `pm-spec` |
| **触发** | "写 PRD"、"需求文档" |
| **输入** | 自动读取 `.planning/requirements.md` + 已有代码库 |
| **产出** | `.planning/prd.md` + `.planning/test-cases.md` + 写入钉钉文档（如需评审） |
| **格式** | 按工作流节点组织：配置项 → 页面交互 → 功能联动 → 异常与边界 |
| **可选** | 画流程图/泳道图（触发 `excalidraw-diagram-skill`） |
| **下一步** | 自动建议"要不要生成技术方案？" |

**PRD 完成后必须同时生成 `.planning/test-cases.md`**，格式：

```markdown
# 测试用例

## 正常流程
- [ ] 场景：用户填写推荐理由 ≥10 字 → 期望：提交成功，跳转我的推荐列表
- [ ] 场景：选择职位后显示职位信息卡 → 期望：展示级别、面试官、笔试标注

## 异常与边界（来自 PRD 异常场景表）
- [ ] 场景：推荐理由不足 10 字点提交 → 期望：按钮置灰 + 红字"至少 10 个字"
- [ ] 场景：上传非 PDF 文件 → 期望：提示"仅支持 PDF"
- [ ] 场景：两人同时锁定同一时间槽 → 期望：第二人看到提示"该时间已被占用"
```

**规则**：PRD 里「异常与边界」章节的每一条，都必须转成 test-cases.md 里对应的测试用例。

### ③ 技术方案

| 项目 | 说明 |
|------|------|
| **Skill** | `plan-feature`（Claude 命令） |
| **触发** | "技术方案"、"plan feature" |
| **输入** | 自动读取 `.planning/prd.md` + 代码库 |
| **产出** | `.planning/tech-plan.md`（代码库分析 → 模式识别 → 分步任务 → 验证命令） |
| **下一步** | 自动建议"要不要开始开发？" |

### ④ 代码开发

| 项目 | 说明 |
|------|------|
| **Skill** | `serial-agent-handoff` |
| **触发** | "开始开发"、"按计划执行" |
| **输入** | 自动读取 `.planning/tech-plan.md` |
| **产出** | 可运行的代码 |
| **完成后自动执行** | `git add` 相关文件 + `git commit` + `git push`，不需要确认 |
| **下一步** | 提交后自动建议"要不要验证一下？" |

### ⑤ 验证

| 项目 | 说明 |
|------|------|
| **Skill** | `verify`（内置）+ Playwright E2E |
| **触发** | "验证一下"、"跑一下看看"、"e2e 测试" |
| **输入** | 自动读取 `.planning/test-cases.md` |
| **产出** | 验证截图 + E2E 测试结果（按 test-cases.md 逐条执行） |
| **失败回退** | 验证不通过 → 建议"回到开发阶段修复" |
| **下一步** | 通过后建议"要不要做代码评审？" |

**E2E 测试标准流程：**

先判断当前任务类型（从 `.planning/status.json` 的 `taskType` 读取），选对应模式：

**模式 A — 全量验证**（新功能、功能优化）
1. 读取 `.planning/test-cases.md`，按「正常流程」→「异常与边界」顺序执行全部用例
2. 测试结果回写：通过改 `[x]`，失败标注失败原因

**模式 B — 定点验证**（Bug 修复、文案/样式）
1. 只跑与改动相关的用例——看 git diff 涉及哪些文件/功能，在 test-cases.md 里找对应用例
2. 额外跑冒烟测试：核心主流程能走通即可（不验证每个边界）
3. 不用全量，省时间

```bash
# 全量验证
playwright test e2e/

# 定点验证（只跑某个功能的测试文件）
playwright test e2e/resume-review.spec.ts

# 冒烟测试（只跑标记了 @smoke 的用例）
playwright test --grep @smoke
```

测试脚本位置：`e2e/<功能名>.spec.ts`，冒烟用例加 `@smoke` 标记，失败截图存 `e2e/screenshots/`，提交到 git。

**已安装路径**：`/home/admin/.local/bin/playwright`

### ⑥ 代码评审

| 项目 | 说明 |
|------|------|
| **Skill** | `code-review` + `simplify`（内置） |
| **触发** | "review"、"代码评审" |
| **产出** | 问题列表 + 自动修复（`--fix`） |
| **下一步** | 评审通过后建议"要不要部署上线？" |

### ⑦ 上线部署

| 项目 | 说明 |
|------|------|
| **Skill** | `prod-deploy` |
| **触发** | "部署"、"上线" |
| **产出** | 线上版本 |
| **完成后** | 建议"要不要线上验证一下？"（复用 verify） |

---

## 跳过规则

不是所有任务都要走完整流程。根据任务大小选择路径：

| 任务类型 | 走哪些阶段 | E2E 模式 | 示例 |
|----------|-----------|---------|------|
| 新功能 | ① → ② → ③ → ④ → ⑤ → ⑥ → ⑦ | 全量验证 | "加一个新的审批流程" |
| 功能优化 | ② → ④ → ⑤ → ⑥ → ⑦ | 全量验证 | "简历审批页加个筛选功能" |
| Bug 修复 | ④ → ⑤ → ⑥ → ⑦ | 定点验证 + 冒烟 | "时间槽锁定后没有释放" |
| 文案/样式 | ④ → ⑤ → ⑦ | 冒烟测试 | "改个按钮颜色" |
| 紧急修复 | ④ → ⑤ → ⑦ | 冒烟测试 | "线上报错了" |

## 回退规则

| 场景 | 回退到 |
|------|--------|
| 验证发现功能不对 | → ④ 开发（改代码） |
| 评审发现设计问题 | → ② PRD（改需求） |
| 上线后发现 bug | → ④ 开发（修 bug）→ ⑤ → ⑦ 快速发布 |

---

## 产出物约定

所有阶段的产出物存放在项目根目录的 `.planning/` 下：

```
.planning/
├── requirements.md     ← 阶段① 需求探索产出
├── prd.md              ← 阶段② PRD 产出
├── test-cases.md       ← 阶段② PRD 同步产出（验收标准 → 测试用例）
├── tech-plan.md        ← 阶段③ 技术方案产出
└── status.json         ← 当前状态（每个阶段完成后必须更新）
```

### status.json 状态持久化（跨对话记忆）

**每个阶段完成时，必须更新 `.planning/status.json` 并提交到 git。** 这是跨对话的唯一记忆——新对话进来时读这个文件就知道上次走到哪了。

格式：

```json
{
  "currentStage": "development",
  "completedStages": ["requirements", "prd", "tech-plan"],
  "lastUpdated": "2026-06-17T15:00:00",
  "taskType": "new-feature",
  "notes": "招聘系统 Phase 2 数据持久化",
  "locked": true
}
```

### 主任务锁（防止临时问题打断主线）

`"locked": true` 表示当前有主线任务进行中。AI 必须遵守以下规则：

**判断规则：用户说的话是在推进主任务，还是临时插入的小事？**

| 信号 | 判断 | 怎么做 |
|------|------|--------|
| 和 status.json 里的 notes/taskType 相关 | 主线 | 正常推进，阶段结束时更新 status.json |
| 问了一个完全无关的问题（如"帮我查个 CLI 命令"） | 临时插入 | 回答完就回来，不动 status.json |
| 说"先做另一件事"或切换到其他项目的话题 | 可能切换主线 | 先问"要暂停当前任务吗？"再决定 |
| 说"回到主线"/"继续之前的" | 恢复主线 | 读 status.json 报告当前状态 |

**铁律**：
- **临时问题不改 status.json**——问完即忘，主线不受影响
- **切换主线需要明确确认**——不能因为用户聊了几句别的，就把 currentStage 改了
- **新对话进入时**：先读 status.json，如果 locked=true，主动报告"上次走到 XX 阶段，主任务是 YY，要继续吗？"

**更新时机（强制，不可跳过）：**

| 完成什么 | currentStage 设为 | completedStages 加入 |
|----------|-------------------|---------------------|
| 需求探索写完 requirements.md | `"prd"` | `"requirements"` |
| PRD 写完 prd.md | `"tech-plan"` | `"prd"` |
| 技术方案写完 tech-plan.md | `"development"` | `"tech-plan"` |
| 代码开发完成 | `"verification"` | `"development"` |
| 验证通过 | `"review"` | `"verification"` |
| 评审通过 | `"deployment"` | `"review"` |
| 部署完成 | `"done"` | `"deployment"` |

**回退时**：把 currentStage 改回目标阶段，completedStages 不删（保留历史）。

**新对话进入时**：先读 `.planning/status.json`，如果存在就直接报告当前状态和下一步建议。
```

---

## 辅助 Skill（按需调用，不占阶段）

| Skill | 什么时候用 |
|-------|-----------|
| `excalidraw-diagram-skill` | PRD 阶段需要画流程图时 |
| `devix-dingtalk-skill` | PRD 写入钉钉文档时 |
| `agents-map` | 进入新项目需要理解全貌时 |
| `zujianfuyon` | 开发阶段需要复用组件时 |
| `memory` | 任何时候需要记住决策时 |
