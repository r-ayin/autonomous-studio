# Studio 阶段详细规范

> 本文件是各阶段的详细执行规范，仅在执行具体阶段时按需 Read。
> 行为规则和阶段速查表在项目 CLAUDE.md 中（由 SKILL.md 激活时注入）。

---

## ① 需求探索
- Skill: `demand-discovery`（含 grill-me 压力追问）
- 产出: `planning/requirements.md`

## ② 写 PRD（含技术方案）
- Skill: `pm-spec`
- 输入: 自动读取 `planning/requirements.md` + 已有代码库
- **格式规范**：按工作流节点组织（不按功能分类）：配置项 → 页面交互 → 功能联动 → 异常与边界

**分两步产出**：

**Step 2a — 生成 PRD + 测试用例（等待用户确认）**
- 产出: `planning/prd.md` + `planning/prd.html` + `planning/test-cases.md`
- prd.md 的 description 中已包含技术实现细节（调哪个接口、读写哪张表、用什么样式）
- **prd.html 必须用 pm-spec Skill 生成**，含内置批注系统（支持选中文字批注 + 截图上传 + 编辑批注）
- 生成后用 `prd-preview-server.js` 启动预览服务器 + `port-mapping` 获取公网链接给用户
- **等待用户在 HTML 上批注确认**，不自动推进；用户完成批注后读取 `planning/annotations.json`

**Step 2b — 用户确认后，生成 prd.json（结构化任务串）**
- 从已确认的 prd.md 拆分生成 `planning/prd.json`
- prd.json 是开发阶段的驱动文件，每个 task 的 description 写到"AI 读完直接写代码"的详细度
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
          "completedAt": null
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
- 所有 P0 tasks done → status.json 自动推进到 verification

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
| qwen3.7-max | 写代码（按 prd.json 逐条执行） | `claude --model qwen3.7-max` |
| opus 4.6 | 审查验证、Bug修复、规划讨论 | Claude Code Agent `model: "opus"` |

**prd.json 驱动开发流程**（全自动，不中断用户）：
1. 读取 `planning/prd.json` → 按节点顺序遍历
2. 只处理 `status: "pending"` 且 `priority: "P0"` 且 `blocked: false` 的任务
3. 开始 → `status: "in_progress"`
4. 完成 → `status: "done"` + `completedAt` + 清空 `notes`
5. git commit：`feat: [N1-01] 任务标题`
6. 立即触发 Validator（见下方）
7. Validator 通过 → 继续下一个
8. Validator 失败 → notes 写入原因，status 改回 pending → 下轮自动修复
9. 同一 task 连续失败 3 次 → `blocked: true`，跳过
10. 每完成一批 → 输出进度摘要
11. 所有 P0 done → 推进到验证阶段

**Hook 自动检查**：开发过程中，PostToolUse Hook 会自动：
1. 每次修改 prd.json → 验证格式（不合法会报错打回）
2. 每次修改 prd.json → 检查 P0 进度，全部完成自动推进到验证阶段
3. 源代码改动超过 3 个文件未提交 → 提醒 commit

**不中断原则**：整个开发循环不停下来问用户。只在技术阻塞或全部完成时暂停。

---

## ③-V 单任务 Validator

> Validator 是独立审查角色，只验证不修复。模型: opus 4.6

**触发时机**：开发 Agent 每完成 1 个 task 并 git commit 后立即 spawn。

**职责**：
1. 读 prd.json → 找到刚完成的 task
2. 逐条验证 acceptance[]：
   - UI → 截图验证
   - 数据库 → 检查 API 调用
   - 交互 → 模拟操作
3. 全部通过 → 保持 done，清空 notes
4. 任一失败 → status 改回 pending，notes 写失败原因，retryCount +1
5. retryCount >= 3 → `blocked: true`

**约束**：只验证不修复，只操作当前 task。

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

## ⑥ 上线部署
- Skill: `prod-deploy`

---

## 回退规则

| 场景 | 回退到 |
|---|---|
| 验证发现功能不对 | → ③ 开发 |
| 评审发现设计问题 | → ② PRD |
| 上线后发现 bug | → ③→④→⑥ 快速发布 |

---

## 辅助 Skill（按需调用）

| Skill | 什么时候用 |
|---|---|
| `excalidraw-diagram-skill` | PRD 阶段需要画流程图时 |
| `devix-dingtalk-skill` | PRD 写入钉钉文档时 |
| `agents-map` | 进入新项目需要理解全貌时 |
| `zujianfuyon` | 开发阶段需要复用组件时 |
