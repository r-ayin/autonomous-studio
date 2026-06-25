<!-- STUDIO:BEGIN v5.4 -->
## Studio 研发流程（激活中）

planning/status.json 存在时，所有任务遵循以下规则。

### 铁律

1. **状态优先**：任何任务开始前先确认当前阶段。阶段决定行为边界——开发阶段不做部署，PRD 阶段不写代码。status.json 是唯一可信源。
2. **代码是现状唯一可信源**：报告进度、列待办、判断功能是否完成时，必须先搜代码确认实际状态，不能只看 prd.json 或任务文件就下结论。prd.json 是"计划做什么"，代码才是"实际做了什么"。
   > 为什么：只看 prd.json 的 status 字段会误报——任务标记 pending 但代码里已经实现了，或者标记 done 但实现有缺陷。每次新会话都"重新发现"已完成的功能，浪费用户时间。
3. **规划与执行分离**：协调者不直接改项目文件，代码编写委托给执行 agent（serial-agent-handoff）。自主模式下串行开发时执行 agent 可直接 commit；并行开发时只有控制器可以 commit。
4. **自主模式预授权提交**：进入 Studio 自主模式后，改完代码自动 git add + commit + push，不等用户说。仅自主模式生效，覆盖全局"不主动提交"约定。**不包含 PRD 确认**——PRD 阶段始终需要用户确认（见第 6 条）。
5. **阶段推进可追溯**：阶段完成后立即更新 status.json（含推进原因和时间戳）。只能前进或合理回退，不能跳跃。
6. **主线保护**：临时问题不改 status.json。切换功能主线需用户明确确认。新会话进入若有进行中任务，先报告状态再行动。locked=true 表示有专属任务，其他会话只读不改。
7. 🚫 **PRD 确认硬关卡（HARD-GATE）**：prd.json 只能在用户明确说"确认/approved/可以了/没问题"后生成。"看起来还行""差不多""感觉可以"不算确认。用户还在讨论或修改中不能推进。自主模式也不能绕过此关卡。
   > 为什么：PRD 是后续所有阶段的基石，模糊确认一旦驱动开发返工成本极高，宁可多等一轮。
   > PRD 阶段还有**覆盖检查**强制步骤（详见 phase-build.md），生成 prd.md 前必须输出覆盖对照表确认无遗漏。
8. **业务语言汇报**：所有汇报用产品/运营视角表达，禁技术黑话。待确认项说清选项和后果。

### 阶段路由（按需 Read，不要全读）
做完一个阶段、验证通过后，把 status.json 的 currentStage 推进到下一阶段：需求→prd→development→prd-review→verification→review→deployment→archiving→archived。
| 你要做什么 | 读哪个 phase 文件 |
|---|---|
| 聊需求 / 写 PRD / 生成 prd.json | `phases/phase-build.md`（含覆盖检查强制步骤） |
| 写代码 / 单任务审查 / 全量 PRD 对照 | `phases/phase-dev.md` |
| E2E 验证 / 评审 / 部署 / 归档 / 回退 | `phases/phase-ship.md` |
路径前缀：`~/.claude/skills/autonomous-studio/`

### 新会话恢复规则
- 若 status.json 存在：先读 → 判断 currentStage → 报告当前状态
- currentStage=prd：先读 `planning/prd-decisions.md`，汇总已确认/待讨论要点
- currentStage=development：读 prd.json + **搜代码核实**每条任务实际状态（铁律 2），用业务语言报告。
- locked=true：告知有任务进行中，询问是否接力
<!-- STUDIO:END -->
