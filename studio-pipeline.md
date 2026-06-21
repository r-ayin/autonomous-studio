# Studio 阶段详细规范

> 本文件是各阶段的详细执行规范，仅在执行具体阶段时按需 Read。
> 行为规则和阶段速查表在项目 CLAUDE.md 中（由 SKILL.md 激活时注入）。

---

## ① 需求探索
- Skill: `demand-discovery`（含 grill-me 压力追问）
- 产出: `planning/requirements.md`

---

## ② 写 PRD（含技术方案）
- Skill: `pm-spec`
- 输入: 自动读取 `planning/requirements.md` + 已有代码库
- **格式规范**：按工作流节点组织（不按功能分类）：配置项 → 页面交互 → 功能联动 → 异常与边界

### 核心原则：渐进式共识沉淀

> prd-decisions.md 是 PRD 的唯一输入源。prd.md 是从决策记录中汇总生成的成品，不是独立创作。
> 没有记录在 prd-decisions.md 里的讨论结论，不能出现在 prd.md 中——因为没法追溯。
> 反过来，prd-decisions.md 里每条 `[x]` 记录，必须在 prd.md 中有对应体现——否则就是遗漏。

### 三阶段流程

```
讨论阶段（可跨多轮、多会话）
  ↓ 每达成一个共识 → 立即写入 prd-decisions.md
  ↓ 所有要点讨论完毕
覆盖检查（生成前的强制验证）
  ↓ 输出覆盖对照表 → 用户确认无遗漏
  ↓
生成阶段（Step 2a → 硬关卡 → Step 2b）
```

---

### 阶段一：讨论 → prd-decisions.md

PRD 讨论过程中，**每达成一个共识立即追加**到 `planning/prd-decisions.md`，不等全部讨论完再记录。

**prd-decisions.md 格式：**
```markdown
## PRD 讨论记录

- [x] 推荐理由必填且≥10字 | 结论：前端校验+后端兜底 | 2026-06-22
- [x] 移动端不展示详情按钮 | 结论：用 CSS media query 隐藏 | 2026-06-22
- [ ] 超时未提交是否自动保存草稿 | 待讨论
```

**讨论阶段的三条规则：**

1. **先读后说**：讨论新要点前，先读一遍 `prd-decisions.md`，确认之前的结论还在。
   > 为什么：AI 的对话记忆有限，文件是唯一不会被挤掉的记录。不读就可能重复讨论或推翻已有结论。

2. **即时落盘**：每条共识达成后立即追加，格式 `- [x] 要点 | 结论 | 日期`。不等讨论完再统一记录。
   > 为什么：事后回忆总会漏。你确认了"推荐理由≥10字"，3 轮对话后再记录，可能只记住了结论忘了上下文。

3. **待定也要记**：暂未达成共识的要点用 `- [ ] 要点 | 待讨论` 标记，不能遗漏。
   > 为什么：待讨论的也是信号——防止 AI 擅自替你做决定，或以为你默认同意了。

---

### 阶段二：覆盖检查（生成 prd.md 之前的强制验证）

> 这一步是防止 prd-decisions.md 和 prd.md 脱节的拦截机制。

**在生成 prd.md 之前，必须先输出覆盖对照表给用户看：**

```markdown
## 覆盖检查报告

### 已确认决策 → PRD 对应位置
| # | prd-decisions.md 条目 | PRD 对应章节 | 状态 |
|---|---|---|---|
| 1 | 推荐理由必填且≥10字 | 2.3 表单校验规则 | ✅ 已覆盖 |
| 2 | 移动端不展示详情按钮 | 3.1 响应式适配 | ✅ 已覆盖 |
| 3 | 超时自动保存草稿 | — | ❌ 未覆盖 |

### 待讨论项（不阻塞，但需确认处理方式）
| # | 条目 | 建议 |
|---|---|---|
| 4 | 并发编辑冲突处理 | 建议本期不做，标注为"后续迭代" |

### 判定
- ❌ 存在未覆盖项 → **不允许生成 prd.md**，先补充或标注为"不做"
- 全 ✅ → 可以生成
```

**覆盖检查的三条规则：**

1. **全量扫描**：读 prd-decisions.md 所有 `[x]` 条目，逐条检查是否在将要生成的 prd.md 中有对应内容
2. **缺一不可**：任何一条 `[x]` 条目找不到对应 → 不允许继续，必须补上或跟用户确认"本期不做"
3. **待讨论项处理**：所有 `[ ]` 条目必须在表中列出并给出建议（做/不做/后续迭代），用户确认后标记为 `[x]` 或删除

> 为什么要这一步：这是整个防遗忘机制的"验收环节"。前面的即时落盘保证了记录完整，这一步保证了记录和成品之间没有偏差。没有这一步，就像做了笔记但交作业时没翻笔记——记了也白记。

---

### 阶段三：生成 PRD 文档

**Step 2a — 从 prd-decisions.md 汇总生成 PRD（等待用户确认）**
- **输入源**：`planning/prd-decisions.md`（已确认的决策条目）+ `planning/requirements.md`（需求背景）+ 已有代码库
- 产出: `planning/prd.md` + `planning/prd.html` + `planning/test-cases.md`
- prd.md 的 description 中已包含技术实现细节（调哪个接口、读写哪张表、用什么样式）
- **prd.html 必须用 pm-spec Skill 生成**，含内置批注系统（支持选中文字批注 + 截图上传 + 编辑批注）
- 生成后用 `prd-preview-server.js` 启动预览服务器 + `port-mapping` 获取公网链接给用户
- **等待用户在 HTML 上批注确认**，不自动推进；用户完成批注后读取 `planning/annotations.json`

<!-- HARD-GATE: PRD 确认 -->
**★ 硬关卡：** 用户必须明确说"确认/approved/可以了/没问题"才能进入 Step 2b。
以下表述**不算确认**，不能推进：
- "看起来还行" / "差不多" / "感觉可以" / "你觉得呢"
- 用户只是提了修改意见（需改完再等下一次确认）
- 用户没有回复

**常见越权行为（禁止）：**
| 越权行为 | 正确做法 |
|---------|---------|
| 跳过覆盖检查直接生成 prd.md | 先输出覆盖对照表，确认无遗漏再生成 |
| 用户还在讨论时就生成 prd.json | 等明确确认后再生成 |
| 把"沉默"当做确认 | 主动提示用户确认 |
| 把 prd.html 和 prd.json 同时生成 | 必须先 2a 后 2b，中间等确认 |
| prd.md 中出现 prd-decisions.md 里没有的新决策 | 先追加到 prd-decisions.md，再写入 prd.md |

**Step 2b — 用户确认后，生成 prd.json（结构化任务串）**
- 从已确认的 prd.md 拆分生成 `planning/prd.json`
- prd.json 是开发阶段的驱动文件，每个 task 的 description 写到"AI 读完直接写代码"的详细度
- 生成前**再次运行覆盖检查**：prd-decisions.md 每条 `[x]` → prd.json 中有对应 task 覆盖
- 生成后自动推进 `currentStage = "development"`

### test-cases.md 格式
```markdown
## 正常流程
- [ ] 场景：用户填写推荐理由 ≥10 字 → 期望：提交成功，跳转列表

## 异常与边界（来自 PRD 异常场景表）
- [ ] 场景：推荐理由不足 10 字点提交 → 期望：按钮置灰 + "至少 10 个字"
```

PRD 里「异常与边界」每一条，必须转为 test-cases.md 里对应的测试用例。

### prd.json 格式

```json
{
  "version": "1.0",
  "source": "planning/prd.md",
  "nodes": [
    {
      "id": "node-1",
      "name": "节点名称",
      "tasks": [
        {
          "id": "N1-01",
          "title": "任务标题",
          "description": "详细说明",
          "acceptance": ["验收条件1", "验收条件2"],
          "priority": "P0",
          "status": "pending",
          "completedAt": null,
          "blocked": false,
          "retryCount": 0,
          "notes": ""
        }
      ]
    }
  ],
  "metadata": {
    "stateMachine": { "状态": { "next": ["下一状态"], "trigger": "触发条件" } }
  }
}
```

**prd.json 规则**：
- 每个 PRD 节点/模块拆成独立 tasks，每个 task 有唯一 id（格式：N{节点号}-{序号}）
- acceptance 数组是验收条件，对应 test-cases.md 里的场景
- status 流转：`pending → in_progress → done`
- 所有 P0 tasks done → 触发 ③-R 全量对照评审

**prd.json 详细度要求（面向初级开发者）**：
- **description 必须包含**：数据从哪张表读取、筛选/排序条件、写入哪张表、UI 展示哪些字段
- **acceptance 必须可验证**：不写"工作正常"，而写"请假人员灰色显示且标注'请假至X月X日'"
- **涉及数据库的 task**：必须写明表名、关键字段、读写方向
- **涉及联动的 task**：必须写明"改A → B自动变化"的因果关系
- **涉及弹窗/交互的 task**：必须写明触发条件、弹窗内容、确认/取消效果
- **原则**：开发者读完 description + acceptance 就能直接写代码

---

## ③ 代码开发

- Skill: `serial-agent-handoff`
- 输入: 自动读取 `planning/prd.json`
- 完成后自动 `git add` + `git commit` + `git push`

**双模型分工**：
| 模型 | 做什么 | 调用方式 |
|---|---|---|
| sonnet | 写代码（按 prd.json 逐条执行） | Claude Code Agent `model: "sonnet"` |
| opus | 审查验证、Bug修复、规划讨论、③-R 全量对照 | Claude Code Agent `model: "opus"` |

**子 agent 上下文策略**：
| 子 agent | 给什么上下文 |
|---------|------------|
| 写代码（sonnet） | 完整 prd.json + prd-decisions.md + 当前 task + 项目 CLAUDE.md |
| Validator（opus） | 完整 prd.json + prd-decisions.md + 当前 task + git diff |
| ③-R 全量对照（opus） | 完整 prd.json + prd-decisions.md + git log + test-cases.md |

> 给完整 prd.json 的原因：跨 task 的数据关系（字段名、状态流转）只有看全局才能发现集成问题。

**prd.json 驱动开发流程**（全自动，不中断用户）：
1. 读取 `planning/prd.json` → 按节点顺序遍历
2. 只处理 `status: "pending"` 且 `priority: "P0"` 且 `blocked: false` 的任务
3. 开始 → `status: "in_progress"`
4. 完成 → `status: "done"` + `completedAt` + 清空 `notes`
5. git commit：`feat: [N1-01] 任务标题`
6. 立即触发 Validator（见 ③-V）
7. Validator 通过 → 继续下一个
8. Validator 失败 → notes 写入原因，status 改回 pending → 下轮自动修复
9. 同一 task 连续失败 3 次 → `blocked: true`，跳过并记录
10. 每完成一批 → 输出进度摘要
11. 所有 P0 done → 自动触发 ③-R 全量对照评审

**Hook 自动检查**：开发过程中，PostToolUse Hook 会自动：
1. 每次修改 prd.json → 验证格式（不合法会报错打回）
2. 每次修改 prd.json → 检查 P0 进度，全部完成自动触发 ③-R
3. 源代码改动超过 3 个文件未提交 → 提醒 commit

**不中断原则**：整个开发循环不停下来问用户。只在技术阻塞或全部完成时暂停。

---

## ③-V 单任务 Validator

> Validator 是独立审查角色，只验证不修复。模型: opus

**触发时机**：开发 Agent 每完成 1 个 task 并 git commit 后立即 spawn。

**上下文**：完整 prd.json + prd-decisions.md + 当前 task + git diff

**三维度审查**：

| 维度 | 检查什么 |
|------|---------|
| **正确性** | acceptance 条件逐条验证，有无 Bug |
| **代码风格** | 命名规范、文件组织、是否符合项目现有模式 |
| **PRD 一致性** | 实现是否完整覆盖 prd.json 的 description，有无遗漏字段/交互/边界处理 |

**输出格式**：
```
## Validator 报告 [N1-01]

### 正确性：✅ 通过 / ❌ 不通过
- [x] 验收条件1：提交成功跳转列表 ✓
- [ ] 验收条件2：推荐理由<10字时按钮置灰 ✗（未实现置灰，只有 toast 提示）

### 代码风格：✅ 通过 / ⚠️ 建议
- 命名：符合项目 camelCase 规范
- ⚠️ 建议：fetchData 函数可提取为共用 hook

### PRD 一致性：✅ 通过 / ❌ 不通过
- [x] 数据从 applications 表读取 ✓
- [ ] PRD 要求"请假状态灰色显示"，代码中未找到对应样式处理
```

**判定规则**：任一维度标记 ❌ → task 回退为 pending，notes 写入具体失败原因，retryCount +1。仅 ⚠️ 不阻塞。retryCount >= 3 → `blocked: true`。

---

## ③-R 全量 PRD 对照评审

> 所有 P0 tasks done 后、进入 E2E 之前自动触发。模型: opus

**触发时机**：Hook 检测到 prd.json 所有 P0 tasks 均为 `done`，自动 spawn。

**上下文**：完整 prd.json + prd-decisions.md + git log（本次功能所有提交）+ test-cases.md

**检查三件事**：

| 检查项 | 具体问题 |
|--------|---------|
| **完整性** | prd.json 每条 acceptance 都有对应实现？有没有 task 无人覆盖？ |
| **集成点** | 跨 task 的数据流转是否一致？字段名/状态值跨模块是否对齐？ |
| **PRD 决策落地** | prd-decisions.md 每条 `[x]` 确认的要点，在实现中都有体现吗？ |

**输出格式**：
```
## ③-R 全量 PRD 对照报告

### 完整性：✅ 全部覆盖 / ❌ 有遗漏
- ✅ N1-01 ~ N1-05 全部 done
- ❌ PRD 异常场景"超时未提交自动保存草稿"无对应 task

### 集成点：✅ 通顺 / ⚠️ 有断点
- ⚠️ N1-02 写入 status="pending"，N1-04 过滤用 status="waiting"，字段不一致

### PRD 决策落地：✅ 全部落地 / ❌ 有遗漏
- ✅ 推荐理由≥10字校验 → 前端+后端均已实现
- ❌ 移动端不展示详情按钮 → 未找到对应样式逻辑
```

**判定规则**：
- 有 ❌ → 回到 ③ 开发补充，不进入 E2E
- 只有 ⚠️ → 输出给用户决定是否修复
- 全 ✅ → 自动推进 `currentStage = "verification"`

---

## ④ 验证（E2E）

按任务类型选模式：

**模式 A — 全量验证**（新功能、功能优化）
1. 遍历 prd.json 所有 done 的 task → 逐条验证 acceptance
2. 读 test-cases.md → 按顺序执行全部用例
3. 不通过 → 回退到开发阶段

**模式 B — 定点验证**（Bug 修复、文案/样式）
1. 只跑 git diff 涉及的用例
2. 额外跑冒烟测试

```bash
/home/admin/.local/bin/playwright test e2e/              # 全量
/home/admin/.local/bin/playwright test e2e/<功能>.spec.ts  # 定点
/home/admin/.local/bin/playwright test --grep @smoke       # 冒烟
```

测试脚本：`e2e/<功能名>.spec.ts`，失败截图存 `e2e/screenshots/`。

---

## ⑤ 代码评审

- Skill: `code-review` + `simplify`
- **上下文**：git diff + prd-decisions.md + 项目代码风格规范
- 评审对照 PRD 决策，不是凭感觉，确保评审有依据

---

## ⑥ 上线部署

- Skill: `prod-deploy`

---

## ⑦ 归档（Episodic LTM）

**触发时机**：部署完成后自动执行。

**执行步骤**：
1. 从 status.json 提取功能名称和时间范围
2. 创建 `archive/YYYY-MM-DD-{功能名}/` 目录
3. 复制 `planning/` 全部文件到归档目录
4. 从 prd.json 提取 blocked tasks 列表
5. 生成 `archive/YYYY-MM-DD-{功能名}/retrospective.md`
6. 更新 status.json：`currentStage = "archived"`

**retrospective.md 格式**（带结构化教训标签，供未来项目复用）：
```markdown
# 回顾：{功能名}
**时间**：{开始} → {结束}
**任务总数**：{total} 个，其中 P0 {p0_count} 个
**阻塞任务**：{blocked_count} 个

## 阻塞原因
- N1-03：权限校验时序问题，需先建角色再绑定权限

## 教训（供未来项目参考）
- [坑/权限] 权限 task 必须先建后用，不能和业务 task 并行
- [坑/数据库] Supabase RLS 开启后需要 service role 才能写入
- [坑/PRD] 弹窗关闭按钮经常被遗漏，PRD 要明确写触发条件和关闭效果

## 做得好的地方
- prd-decisions.md 的讨论记录完整，定稿时无遗漏
```

**跨项目学习闭环**：
- 新项目 Studio 激活时，扫描 `archive/*/retrospective.md`
- 提取同类型项目（根据 taskType 匹配）的教训标签 `[坑/*]`
- 写入本次项目 `planning/known-pitfalls.md`
- Validator 验证时额外检查 known-pitfalls.md 中的历史坑点

---

## 回退规则

| 场景 | 回退到 |
|---|---|
| ③-V Validator 失败 | → ③ 开发（自动修复） |
| ③-R 全量对照发现遗漏 | → ③ 开发（补充实现） |
| ④ 验证发现功能不对 | → ③ 开发 |
| ⑤ 评审发现设计问题 | → ② PRD |
| 上线后发现 bug | → ③→④→⑥ 快速发布 |

---

## 辅助 Skill（按需调用）

| Skill | 什么时候用 |
|---|---|
| `excalidraw-diagram-skill` | PRD 阶段需要画流程图时 |
| `devix-dingtalk-skill` | PRD 写入钉钉文档时 |
| `agents-map` | 进入新项目需要理解全貌时 |
| `zujianfuyon` | 开发阶段需要复用组件时 |
