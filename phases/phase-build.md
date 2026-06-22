# 阶段一：需求 + PRD（制造期）

> 执行需求探索或写 PRD 时加载本文件。

## ① 需求探索
- Skill: `demand-discovery`（含 grill-me 压力追问）
- 产出: `planning/requirements.md`

## ② 写 PRD（含技术方案）
- Skill: `pm-spec`
- 输入: 自动读取 `planning/requirements.md` + 已有代码库
- **格式规范**：按工作流节点组织（不按功能分类）：配置项 → 页面交互 → 功能联动 → 异常与边界

### 核心原则：渐进式共识沉淀

> prd-decisions.md 是 PRD 的唯一输入源。prd.md 是从决策记录汇总的成品，不是独立创作。
> 没记在 prd-decisions.md 里的讨论结论，不能出现在 prd.md 中——没法追溯。
> 反过来，prd-decisions.md 每条 `[x]` 记录，必须在 prd.md 中有对应体现——否则就是遗漏。

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

### 阶段一：讨论 → prd-decisions.md

每达成一个共识**立即追加**到 `planning/prd-decisions.md`，不等全部讨论完再记录。

格式：
```markdown
## PRD 讨论记录
- [x] 推荐理由必填且≥10字 | 结论：前端校验+后端兜底 | 2026-06-22
- [x] 移动端不展示详情按钮 | 结论：用 CSS media query 隐藏 | 2026-06-22
- [ ] 超时未提交是否自动保存草稿 | 待讨论
```

三条规则：
1. **先读后说**：讨论新要点前先读 prd-decisions.md，确认之前结论还在。
2. **即时落盘**：共识达成后立即追加，格式 `- [x] 要点 | 结论 | 日期`。
3. **待定也要记**：未达共识的用 `- [ ] 要点 | 待讨论` 标记，不遗漏。

### 阶段二：覆盖检查（生成 prd.md 前的强制验证）

生成 prd.md 之前，必须先输出覆盖对照表给用户看：

```markdown
## 覆盖检查报告
### 已确认决策 → PRD 对应位置
| # | prd-decisions.md 条目 | PRD 对应章节 | 状态 |
|---|---|---|---|
| 1 | 推荐理由必填且≥10字 | 2.3 表单校验规则 | ✅ 已覆盖 |
| 2 | 移动端不展示详情按钮 | 3.1 响应式适配 | ✅ 已覆盖 |
| 3 | 超时自动保存草稿 | — | ❌ 未覆盖 |
### 待讨论项
| # | 条目 | 建议 |
|---|---|---|
| 4 | 并发编辑冲突处理 | 建议本期不做，标注"后续迭代" |
### 判定
- ❌ 存在未覆盖项 → 不允许生成 prd.md，先补充或标注"不做"
- 全 ✅ → 可以生成
```

规则：
1. **全量扫描**：读所有 `[x]` 条目，逐条检查是否在 prd.md 中有对应内容
2. **缺一不可**：任何一条 `[x]` 找不到对应 → 不允许继续
3. **待讨论项处理**：所有 `[ ]` 必须列出并给建议，用户确认后标记 `[x]` 或删除

### 阶段三：生成 PRD 文档

**Step 2a — 从 prd-decisions.md 汇总生成 PRD（等待用户确认）**
- 输入：`planning/prd-decisions.md` + `planning/requirements.md` + 已有代码库
- 产出: `planning/prd.md` + `planning/prd.html` + `planning/test-cases.md`
- prd.md 的 description 已含技术实现细节（调哪个接口、读写哪张表、用什么样式）
- prd.html 必须用 pm-spec Skill 生成，含批注系统（选中文字批注 + 截图上传）
- 生成后用 `prd-preview-server.js` 启动预览 + `port-mapping` 取公网链接给用户
- 等待用户在 HTML 上批注确认；完成后读 `planning/annotations.json`

<!-- HARD-GATE: PRD 确认 -->
**★ 硬关卡：** 用户必须明确说"确认/approved/可以了/没问题"才能进入 Step 2b。
以下**不算确认**：
- "看起来还行" / "差不多" / "感觉可以" / "你觉得呢"
- 用户只是提了修改意见（改完再等下一次确认）
- 用户没有回复

**常见越权行为（禁止）：**
| 越权行为 | 正确做法 |
|---------|---------|
| 跳过覆盖检查直接生成 prd.md | 先输出覆盖对照表，确认无遗漏再生成 |
| 用户还在讨论时就生成 prd.json | 等明确确认后再生成 |
| 把"沉默"当做确认 | 主动提示用户确认 |
| prd.html 和 prd.json 同时生成 | 必须先 2a 后 2b，中间等确认 |
| prd.md 出现 prd-decisions.md 里没有的新决策 | 先追加到 prd-decisions.md，再写入 prd.md |

**Step 2b — 用户确认后，生成 prd.json（结构化任务串）**
- 从已确认 prd.md 拆分生成 `planning/prd.json`
- 每个 task 的 description 写到"AI 读完直接写代码"的详细度
- 生成前**再次运行覆盖检查**：prd-decisions.md 每条 `[x]` → prd.json 有对应 task 覆盖
- 生成后自动推进 `currentStage = "development"`

### test-cases.md 格式
```markdown
## 正常流程
- [ ] 场景：用户填写推荐理由 ≥10 字 → 期望：提交成功，跳转列表
## 异常与边界（来自 PRD 异常场景表）
- [ ] 场景：推荐理由不足 10 字点提交 → 期望：按钮置灰 + "至少 10 个字"
```
PRD「异常与边界」每一条，必须转为 test-cases.md 里对应的测试用例。

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

规则：
- 每个节点/模块拆成独立 tasks，每个 task 有唯一 id（格式：N{节点号}-{序号}）
- acceptance 数组是验收条件，对应 test-cases.md 里的场景
- status 流转：`pending → in_progress → done`
- 所有 P0 tasks done → 触发 ③-R 全量对照评审

**详细度要求（面向初级开发者）：**
- description 必须含：数据从哪张表读、筛选/排序条件、写入哪张表、UI 展示哪些字段
- acceptance 必须可验证：不写"工作正常"，而写"请假人员灰色显示且标注'请假至X月X日'"
- 涉及数据库：必须写明表名、关键字段、读写方向
- 涉及联动：必须写明"改A → B自动变化"的因果关系
- 涉及弹窗/交互：必须写明触发条件、弹窗内容、确认/取消效果
- 原则：开发者读完 description + acceptance 就能直接写代码
