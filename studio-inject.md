<!-- STUDIO:BEGIN v5.4 -->
## Studio 研发流程（激活中）

planning/status.json 存在时，所有任务遵循以下规则。

### 七条铁律

1. **状态优先**：任何任务开始前先确认当前阶段。阶段决定行为边界——开发阶段不做部署，PRD 阶段不写代码。status.json 是唯一可信源。
2. **规划与执行分离**：协调者不直接改项目文件，代码编写委托给执行 agent（serial-agent-handoff）。
3. **自主模式预授权提交**：进入 Studio 自主模式后，改完代码自动 git add + commit + push，不等用户说。仅自主模式生效，覆盖全局"不主动提交"约定。
4. **阶段推进可追溯**：阶段完成后立即更新 status.json（含推进原因和时间戳）。只能前进或合理回退，不能跳跃。
5. **主线保护**：临时问题不改 status.json。切换功能主线需用户明确确认。新会话进入若有进行中任务，先报告状态再行动。locked=true 表示有专属任务，其他会话只读不改。
6. **PRD 确认硬关卡**：prd.json 只能在用户明确说"确认/approved/可以了/没问题"后生成。"看起来还行""差不多""感觉可以"不算确认。用户还在讨论或修改中不能推进。
   > 为什么：PRD 是后续所有阶段的基石，模糊确认一旦驱动开发返工成本极高，宁可多等一轮。
7. **业务语言汇报**：汇报进度/待办/待确认/bug 时，每条都用业务语言说明"这是什么、用户会遇到什么现象"，禁止只给代号或技术名词。涉及待确认时说清"确认什么、不同选项会导致什么"。
   > 为什么：用户是业务方，代号没信息量无法决策，只给代号等于没汇报。

### 阶段路由（按需 Read，不要全读）
做完一个阶段、验证通过后，把 status.json 的 currentStage 推进到下一阶段：需求→prd→development→prd-review→verification→review→deployment→archiving→archived。
| 你要做什么 | 读哪个 phase 文件 |
|---|---|
| 聊需求 / 写 PRD / 生成 prd.json | `phases/phase-build.md` |
| 写代码 / 单任务审查 / 全量 PRD 对照 | `phases/phase-dev.md` |
| E2E 验证 / 评审 / 部署 / 归档 / 回退 | `phases/phase-ship.md` |
路径前缀：`~/.claude/skills/autonomous-studio/`

### 新会话恢复规则
- 若 status.json 存在：先读 → 判断 currentStage → 报告当前状态
- currentStage=prd：先读 `planning/prd-decisions.md`，汇总已确认/待讨论要点
- currentStage=development：读 `planning/prd.json`，统计 P0 进度（done/total），用业务语言说明每个待办是什么、用户会看到什么
- locked=true：告知有任务进行中，询问是否接力

### 列待办前先核验代码
列"待开发"清单或报告功能未完成前，必须先在代码里搜对应实现确认确实不存在——能从代码确认的不要问用户。已实现的归档到 `archive/` 不删；部分实现的只列未完成部分；无法靠代码判断的（如视觉问题）标注"需实跑页面确认"。真待开发的才问用户是否要做。
> 为什么：只看任务文件存在与否会误报已完成功能。代码是现状唯一可信源，意图文件不算。
<!-- STUDIO:END -->
