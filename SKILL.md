---
name: autonomous-studio
description: >-
  自主决策引擎 v3.1（autonomous_studio）— Studio × Autonomous-Engine 全量融合。
  双轨架构：L2 执行轨（7min）+ L3 研判轨（60min），检查点保护执行。
  7 阶段 Studio 流水线 + 路线健康度诊断 + 路线修正协议。
  + CodeGraph 融合层 v1.0（代码语义视角·8触点8规则）。
  触发词：自主模式、别等我、自动继续、keep working、autonomous mode、auto-develop、
  决策引擎、继续开发、不用等我、你自己做、auto-continue、studio auto on、继续、
  接下来做什么、下一步、studio、全链路、开发流程、从需求到上线、项目状态、
  帮我聊需求、这个想法能不能做、写PRD、需求文档、技术方案、plan feature、
  开始开发、按计划执行、验证一下、跑一下看看、e2e测试、review、代码评审、部署、上线。
model: sonnet
repository: https://code.alibaba-inc.com/qunbu/autonomous-studio
sync:
  # 任何对话中更新此 Skill 后，执行以下命令同步到仓库：
  # cd /tmp/autonomous-studio && git pull origin main && vim SKILL.md && git add SKILL.md && git commit -m "feat(autonomous-studio): 更新 SKILL.md" && git push origin main
  target_repo: "https://xhq02486164:B06ESflq0Gg_cI_eYrrj@code.alibaba-inc.com/qunbu/autonomous-studio.git"
  target_path: "SKILL.md"
---

# Autonomous Studio — 调度器模式 v3.0

> **autonomous_studio = Studio 7 阶段流水线 × Autonomous-Engine 双轨架构 × CodeGraph 代码语义视角**

## 架构演进

```
v1.x (旧·内联模式):
  CronCreate 触发 → 当前会话加载 SKILL.md → 在项目对话上下文中运行
  问题: 项目对话历史污染决策 ⚠️

v2.0 (隔离模式):
  CronCreate 触发 → 当前会话 spawn Agent 子代理 →
  子代理加载 decision-agent-prompt.md（干净上下文）→ 只读结构化数据文件 →
  返回结构化决策 → 主会话输出摘要
  优势: 零上下文污染 ✅

v3.0 (autonomous_studio·全量融合):
  v2.0 全部能力 +
  🏗️ Studio 7 阶段研发流水线（requirements→prd→tech-plan→development→verification→review→deployment）
  🛤️ 双轨架构：L2 执行轨（7min·推进流程）+ L3 研判轨（60min·路线健康度）
  📊 路线健康度诊断（4 维度 §②E）+ 路线修正协议（§1.6 RC-1→RC-4）
  🔍 检查点保护执行（save-checkpoint.py + git backup branch + auto rollback）
  🔗 CodeGraph 融合层 v1.0（代码语义视角·8触点8规则·自动更新感知）
  优势: Studio 自动驾驶 + 引擎自主决策 + 代码级语义理解 ✅
```

## 你的角色

你是**调度器**，不是决策者。

当引擎被激活时（心跳/手动/内联），你的唯一职责是：
1. 读取 `decision-agent-prompt.md`（子代理的独立系统提示词）
2. 使用 **Agent 工具** spawn 一个独立子代理
3. 将当前激活上下文传递给子代理
4. 子代理完成后，输出简短摘要

**不要自己执行七阶段循环！你的工作是调度。**

---

## 执行流程

### Step 1: 确认激活模式

```
激活来源检测:
  - 如果 prompt 包含 "AUTONOMOUS_HEARTBEAT L2" → 模式 = "heartbeat_l2"
  - 如果 prompt 包含 "AUTONOMOUS_HEARTBEAT L3" → 模式 = "heartbeat_l3"
  - 如果用户主动说触发词 → 模式 = "manual"
  - 如果是回复末尾内联检查 → 模式 = "inline"
```

### Step 2: 快速预检（调度器层面，3 秒内完成）

```
0. ★ Studio 感知预检（新增，Studio 融合核心）:
   读 planning/status.json（如果存在）:
   
   a. autoAdvance == false？
      是 → 静默 EXIT（用户已暂停自动驾驶）
   
   b. correctionPending == true？
      读 consecutiveHeartbeatsBlocked:
        < 3 → 继续阻断，输出路线修正提醒（不 spawn 子代理做新决策）
        ≥ 3 → 自动降级：写 autonomous-suggestions.md 持续提醒，
               correctionPending=false，恢复正常流程
   
   c. locked == true && autoAdvance == true？
      → 进入 Studio 驱动模式（见下方"Studio 驱动行为"）
      → 此时 consecutiveAutoActions 计数豁免 serial-agent-handoff（整个会话计1次）
   
   d. currentStage == "deployment" && DEVOUT_SERVER_URL 未设置？
      → SUGGEST 用户配置环境变量，EXIT（不执行部署相关操作）

   e. L3 激活 && locked == true？
      → 强制将 calibration.json 的 consecutive_no_delta 写为 0（阻止 L3 降频）

1. 读 calibration.json → cooldown.current_consecutive >= 3？
   是 → 静默 EXIT（不 spawn 子代理）

2. 读 autonomous-state.md → GOAL_STATUS == "paused"？
   是 → 静默 EXIT
   GOAL_STATUS == "achieved" 或无目标 → 继续（引擎主动扫描）

3. 检查 decision-agent-prompt.md 是否存在？
   否 → 静默 EXIT（引擎故障）
```

### Step 2.5: Studio 驱动行为（仅当 locked=true && autoAdvance=true 时）

```
读 planning/status.json.currentStage，按阶段决定 L2 的行为：

"requirements" 或 (requirements.md 不存在):
  → L2 直接执行「主动需求研判协议」（见 studio-engine-bridge.md §①）
  → 不走通常的「spawn 子代理」路径
  → 扫描上下文 → 判断成熟度 → 提一个精准问题

"prd":
  → 检查 draftPending.confirmed:
    confirmed=false 且 artifact 存在 → 静默等待（不重复生成）
    artifact 不存在 → 生成 prd.md + test-cases.md（Step 2a，等待用户确认）
    confirmed=true 且 prd.json 不存在 → 从 prd.md 生成 prd.json（Step 2b）
    confirmed=true 且 prd.json 存在 → 推进 currentStage="development"

"tech-plan":
  → 同上，生成 planning/tech-plan.md（调用 plan-feature，后处理 copy）

"development":
  → 读 tech-plan.md → 执行 serial-agent-handoff
  → 整个会话计为 1 次自主行动（不计入 cooldown 连续计数）

"verification" / "review":
  → 自动执行验证/评审（无需用户触发）

"deployment":
  → 执行 prod-deploy Phase 1-5（全自动）
  → Phase 6-7 需 ACT_NOTIFY 每批次确认

"done":
  → 退出 Studio 驱动模式，回到原有主动扫描协议（§1.5）
```

### Step 2.7: CodeGraph 融合层同步检查（v3.0 新增·可选增强）

```
仅在 codegraph 命令可用时执行（< 2 秒，不阻塞）：

1. 检查 codegraph/capability-registry.json 中的版本
2. 运行 codegraph --version 获取当前安装版本
3. 版本不一致 → 自动运行 python hooks/codegraph-sync.py
   → 重新扫描能力 → 更新注册表 → 检查自动匹配
4. 版本一致 → 跳过
5. codegraph 不可用 → 静默跳过
```

### Step 3: Spawn 子代理

```
使用 Agent 工具，参数如下：

subagent_type: "general-purpose"
description: "自主决策引擎子代理 - {模式}"
prompt: |
  你是 autodev-engine v3.0 (autonomous_studio) 的独立决策子代理。

  你的系统提示词来自文件:
  {CLAUDE_PROJECT_DIR}/skill/decision-agent-prompt.md

  ★ 在开始任何分析之前，你必须先读取上述文件作为你的完整操作手册。
  ★ 你的上下文是干净的——你没有主会话的对话历史。
  ★ 你只通过读取结构化数据文件来了解当前状态。

  本次激活信息:
  - 激活模式: {模式}
  - 激活时间: {当前ISO时间}
  - 工作区路径: {CLAUDE_PROJECT_DIR}

  执行步骤:
  1. 首先 Read decision-agent-prompt.md（完整读取）
  2. 按照其中的 §0 冷启动协议判断当前状态
  3. 如果是热运行 → 执行 §1 七阶段研判框架
  4. 如果是冷启动 → 执行 §0.2 冷启动流程
  5. 输出 MUST 包含 <decision>JSON</decision> 标签
  6. 在 <decision> 之外只输出最多 3 行自然语言摘要

  记住：你是独立子代理，你的"记忆"是文件系统，不是对话历史。
```

### Step 4: 处理子代理返回（v3.0 Studio 融合更新）

```
子代理返回后:
  1. 检查返回中是否包含 <decision> 标签
  2. 提取 action_level、decision_summary、route_health_score（如有）
  
  3. ★ Studio 融合处理（当 status.json 存在且 locked=true）：
     
     a. route_health_score 处理:
        < 5 → 设置 correctionPending=true，写 autonomous-suggestions.md
               调用 notify-phone.py（高优先级路线修正通知）
               更新 consecutiveHeartbeatsBlocked=0
        5-6 → 写 SUGGEST 级警告到 autonomous-suggestions.md（不阻断）
        ≥ 7 → 正常推进
     
     b. DRAFT 生成后:
        设置 status.json.engine.draftPending = {stage, artifact, confirmed:false}
        设置 blockedReasons += ["草稿待用户审阅"]
        输出明确提示（不静默）
     
     c. 阶段推进检测:
        draftPending.confirmed=true（由 decision-observer 写入）→ 更新 currentStage
        serial-agent-handoff 完成 → 更新 currentStage="verification"
        verification 通过 → currentStage="review"
        review 通过 → currentStage="deployment"
     
     d. handoffFile 路径:
        serial-agent-handoff 开始时 → 将 handoff 文件路径写入
        status.json.engine.stageArtifacts.handoffFile
     
     e. L3 降频处理（Studio 项目激活时豁免）:
        locked=true → 强制 consecutive_no_delta=0（不降频）
        locked=false → 原有降频逻辑
  
  4. 根据 action_level 决定主会话行为:
     - OBSERVE → 写 case JSON + 更新 autonomous-state.md
     - SUGGEST → 追加到 autonomous-suggestions.md
     - ACT_NOTIFY/ACT_SILENT → 检查点保护执行:
       a. python hooks/save-checkpoint.py
       b. 执行 actions_planned
       c. 失败 → git reset --hard 回滚
  
  5. 输出简洁摘要给用户（Studio 模式格式）:
     "🤖 Studio {阶段} @ {时间} | {行动摘要} | 信心 {分数}"
```

---

## 三种激活方式的具体行为

### 方式 A：心跳 L2（每 7 分钟）

```
收到 "AUTONOMOUS_HEARTBEAT L2" prompt →
  Step 2 预检 →
    冷却检查 → 通过
    GOAL_STATUS == "paused" → "<!-- HB SKIP: paused -->"，EXIT
    GOAL_STATUS == "achieved" 或无目标 → 继续（引擎应主动扫描）
  Step 3 Spawn 子代理（description: "L2 哨兵扫描"）→
    子代理在无目标模式下执行 §1.5 主动扫描协议
  Step 4 如果子代理建议 ACT_NOTIFY 且 confidence >= 71 →
     执行建议的行动 →
     输出: "🤖 L2 @ {时间} | {行动摘要} | 信心 {分数}"
  如果子代理输出 SUGGEST（有发现但不自动执行）→
     追加到 autonomous-suggestions.md →
     输出: "🔍 L2 @ {时间} | {发现数量} 条建议"
  否则:
     静默（不输出任何内容）
```

### 方式 B：心跳 L3（每 60 分钟·v2.2 自适应降频）

```
收到 "AUTONOMOUS_HEARTBEAT L3" prompt →
  Step 2 预检（L3 始终执行——基础设施守卫不受目标状态影响）→
  Step 3 Spawn 子代理（description: "L3 深度检查"）→
  子代理会执行完整研判 + 网络研究 + 模式提取 + 项目瞭望 →
  Step 4 处理返回:
    ① 常规处理（action_level 分发）
    ② ★ v2.2 L3 降频自适应检查:
       a. 读取 calibration.json → l3_auto_degrade
       b. 如果子代理判定 OBSERVE + 无增量:
          consecutive_no_delta += 1（写入 calibration.json）
       c. 如果子代理有增量发现:
          consecutive_no_delta = 0（重置计数器）
          如果 current_effective_interval != base_interval_min:
            恢复 L3 CronCreate 为基础间隔（60min）
       d. 检查降频阈值:
          consecutive_no_delta >= 4 → CronCreate L3 调整为 240min
          consecutive_no_delta >= 2 → CronCreate L3 调整为 120min
       e. 用户交互恢复时 → 自动重置为基础间隔 60min
  输出: "🤖 L3 @ {时间} | {发现摘要} | 降频: {当前间隔}min"
```

### 方式 C：用户手动激活

```
用户说触发词 →
  Step 2 预检（跳过冷却检查——用户主动要求）→
  Step 3 Spawn 子代理 →
  Step 4 向用户展示:
    - 当前引擎状态
    - 子代理的研判结果
    - 建议的下一步行动
```

### 方式 D：内联检查（回复末尾）

```
内联检查**不需要 spawn 子代理**（太重了）：
  0. ★ 冷却重置：如果本次回复是对用户消息的直接响应 →
     重置 calibration.json cooldown.current_consecutive = 0
     （主会话负责冷却管理——子 Agent 在隔离上下文中无法感知用户交互）
  1. 读 decision-log.jsonl 最后 5 行
  2. 快速 git status --porcelain（有未提更改？）
  3. 判断是否有明显未完跟进
  4. 有 → 低风险跟进直接在当前回复末尾执行
  5. 无 → 不额外输出
  6. 更新 autonomous-state.md 时间戳

内联检查阈值:
  - 刚修完 bug → 自动运行测试（信心 85，ACT_SILENT）
  - 刚改完文件 → 更新 PROGRESS.md（信心 90，ACT_SILENT）
  - 有未提交更改 > 3 个文件 → 追加 SUGGEST 到建议队列
  - 其他 → 静默
```

---

## 子代理 vs 主会话的职责边界

| 职责 | 子代理（决策者） | 主会话（执行者） |
|------|-----------------|-----------------|
| 读取结构化数据 | ✅ | ✅（仅预检） |
| 分析决策模式 | ✅ | ❌ |
| 网络研究 | ✅ | ❌ |
| 计算信心分 | ✅ | ❌ |
| 输出决策 JSON | ✅ | ❌ |
| 写引擎文件 (.claude/) | ✅ | ❌ |
| 修改项目文件 | ❌ | ✅ |
| 运行测试 | ❌ | ✅ |
| Git 操作 | ❌ | ✅ |
| 发送通知 | ❌ | ✅ |
| 输出用户摘要 | ❌ | ✅ |

**原则：子代理用脑子，主会话用手。引擎文件 (.claude/) 是子代理的「笔记本」——可以自由写入。**

---

## Studio 7 阶段流水线规范（手动触发或 L2 驱动时执行）

> 以下规范是子代理在 `development` / `verification` 等阶段的行为标准，也是手动触发时的导航依据。

```
需求 → PRD（含技术方案+任务串） → 开发 → 验证 → 评审 → 部署
                                    ↑                ↓
                                    └── 验证不通过时回退 ┘
```

### 阶段检测算法（status.json 缺失或过时时使用）

当 `planning/status.json` 不存在或不可信时，按以下逆序检测当前阶段：

```
1. 线上已部署？        → 检查最近的 git tag 或部署记录
2. 有代码评审记录？    → 检查最近的 git log 是否有 review/CR 相关提交
3. 有新代码变更？      → 检查 git diff 是否有未提交或最近提交的业务代码
4. 有技术方案？        → 检查 planning/tech-plan.md 是否存在
5. 有 PRD？           → 检查 planning/prd.md 是否存在
6. 有需求描述？        → 检查 planning/requirements.md 是否存在
7. 都没有             → 从需求探索开始
```

### 状态报告模板（手动触发时输出）

用户手动触发 studio 时，检测完成后输出：

```
当前状态：[阶段名]
已完成：[列出已有的产出物]
下一步建议：[具体建议，含触发词]
可跳过的步骤：[如果是小改动，哪些步骤可以跳]
```

### 各阶段触发词与输入输出

| 阶段 | 触发词 | Skill | 输入 | 产出 | 下一步建议 |
|---|---|---|---|---|---|
| ① 需求探索 | "帮我聊需求"、"这个想法能不能做" | `demand-discovery` | 一句话想法 | `planning/requirements.md` | "要不要写 PRD？" |
| ② 写 PRD | "写 PRD"、"需求文档" | `pm-spec` | requirements.md + 代码库 | prd.md + test-cases.md | "要不要开始开发？" |
| ③ 代码开发 | "开始开发"、"按计划执行" | `serial-agent-handoff` | prd.json | 可运行代码 + git push | "要不要验证一下？" |
| ④ 验证 | "验证一下"、"跑一下看看"、"e2e 测试" | `verify` + Playwright | test-cases.md + prd.json | 截图 + E2E 结果 | "要不要做代码评审？" |
| ⑤ 代码评审 | "review"、"代码评审" | `code-review` + `simplify` | git diff | 问题列表 + 自动修复 | "要不要部署上线？" |
| ⑥ 上线部署 | "部署"、"上线" | `prod-deploy` | 主分支代码 | 线上版本 | "要不要线上验证？" |

### status.json 更新时机表（强制，不可跳过）

| 完成什么 | currentStage 设为 | completedStages 加入 |
|---|---|---|
| 需求探索写完 requirements.md | `"prd"` | `"requirements"` |
| PRD 写完 prd.md + test-cases.md | `"development"` | `"prd"` |
| 代码开发完成（所有 P0 done） | `"verification"` | `"development"` |
| 验证通过 | `"review"` | `"verification"` |
| 评审通过 | `"deployment"` | `"review"` |
| 部署完成 | `"done"` | `"deployment"` |

### ① 需求探索
- Skill: `demand-discovery`（含 grill-me 压力追问）
- 产出: `planning/requirements.md`

### ② 写 PRD（含技术方案）
- Skill: `pm-spec`
- 输入: 自动读取 `planning/requirements.md` + 已有代码库
- **格式规范**：按工作流节点组织（不按功能分类）：配置项 → 页面交互 → 功能联动 → 异常与边界

**分两步产出**：

**Step 2a — 生成 PRD + 测试用例（等待用户确认）**
- 产出: `planning/prd.md` + `planning/test-cases.md` + 写入钉钉文档（如需评审）
- prd.md 的 description 中已包含技术实现细节（调哪个接口、读写哪张表、用什么样式）
- 产出后设置 `status.json.engine.draftPending = {stage: "prd", confirmed: false}`
- **等待用户确认**，不自动推进

**Step 2b — 用户确认后，生成 prd.json（结构化任务串）**
- 触发：用户确认 PRD 内容没问题（draftPending.confirmed = true）
- 从已确认的 prd.md 拆分生成 `planning/prd.json`
- prd.json 是开发阶段的驱动文件，每个 task 的 description 写到"AI 读完直接写代码"的详细度
- 生成后自动推进 `currentStage = "development"`

#### `planning/test-cases.md`（测试用例清单）
```markdown
## 正常流程
- [ ] 场景：用户填写推荐理由 ≥10 字 → 期望：提交成功，跳转列表
- [ ] 场景：选择职位后显示职位信息卡 → 期望：展示级别/面试官

## 异常与边界（来自 PRD 异常场景表）
- [ ] 场景：推荐理由不足 10 字点提交 → 期望：按钮置灰 + "至少 10 个字"
- [ ] 场景：上传非 PDF 文件 → 期望：提示"仅支持 PDF"
- [ ] 场景：两人同时锁定同一时间槽 → 期望：第二人看到"该时间已被占用"
```

PRD 里「异常与边界」每一条，必须转为 test-cases.md 里对应的测试用例。

#### `planning/prd.json`（结构化任务串）

从 PRD 按工作流节点拆分为机器可读的开发任务列表。开发阶段逐条读取执行，完成后标记状态。

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
- 开发完成一个 task → 更新 status + completedAt → 重算 progress
- 所有 P0 tasks done → status.json 自动推进到 verification
- metadata.stateMachine 定义业务状态流转，前端可直接读取构建状态机

**prd.json 详细度要求（面向初级开发者）**：
- **description 必须包含**：数据从哪张表读取、筛选/排序条件、写入哪张表、UI 展示哪些字段
- **acceptance 必须可验证**：不写"工作正常"，而写"请假人员灰色显示且标注'请假至X月X日'"
- **涉及数据库的 task**：必须写明表名、关键字段、读写方向（读取/写入/更新）
- **涉及联动的 task**：必须写明"改A → B自动变化"的因果关系
- **涉及弹窗/交互的 task**：必须写明触发条件、弹窗内容、确认/取消效果
- **原则**：开发者读完 description + acceptance 就能直接写代码，不需要再翻 prd.md

### ③ 代码开发（原③技术方案+④开发 合并）

> 技术方案不再单独成阶段。prd.json 的每个 task 的 description 已包含技术实现细节
> （调哪个接口、读写哪张表、用什么样式），开发 Agent 直接读 prd.json 执行即可。

- Skill: `serial-agent-handoff`
- 输入: 自动读取 `planning/prd.json`
- 完成后自动 `git add` + `git commit` + `git push`

**双模型分工**：
| 模型 | 做什么 | 调用方式 |
|---|---|---|
| qwen3.7-max | 写代码（按 prd.json 逐条执行） | `claude --model qwen3.7-max` |
| opus 4.6 | 审查验证、Bug修复、规划讨论 | Claude Code Agent `model: "opus"` |

**规则**：写代码 → qwen。其他所有 → opus。

**prd.json 驱动开发流程**（全自动，不中断用户）：
1. 读取 `planning/prd.json` → 按节点顺序遍历 `nodes[].tasks[]`
2. 只处理 `status: "pending"` 且 `priority: "P0"` 且 `blocked: false` 的任务
3. 开始一个 task → 更新 `status: "in_progress"`
4. 完成一个 task → 更新 `status: "done"` + `completedAt: ISO时间` + 清空 `notes`
5. git commit：`feat: [N1-01] 新建任务表单`
6. **立即触发 ③-V Validator（见下方）**
7. Validator 通过 → **不中断，直接继续下一个 task**
8. Validator 失败 → `notes` 写入失败原因，`status` 改回 `"pending"` → **不中断，开发者下轮自动读 notes 修复**
9. 同一 task 连续失败 3 次 → `blocked: true`，**不中断，跳过继续下一个**
10. 每完成一批（5个 task 或一个节点完成）→ 输出一行进度摘要（不等用户回复）：
    `📊 进度：N1 任务录入 6/6 完成 | 总进度 6/38 (15.8%) | 下一个：N2-01`
11. 所有 P0 tasks done → 运行 `python3 scripts/validate_prd_json.py` → 自动推进到 ④ 验证

**不中断原则**：整个开发循环从第一个 task 到最后一个 task，中间不停下来问用户"要继续吗"。用户通过 git log 和进度摘要了解状态。只有以下情况才暂停：
- 遇到无法解决的技术阻塞（如 Supabase 连不上、必要文件缺失）
- 全部 P0 完成，等待用户确认进入验证阶段

**写回格式**（每完成一个 task 就更新 prd.json）：
```json
{ "id": "N1-01", "status": "done", "completedAt": "2026-06-18T16:00:00" }
```

### ③-V 单任务 Validator（每个 task 完成后立即执行）

> 参考 auto-coding-v2.1/ralph 的 VALIDATOR.md 模式。
> Validator 是独立审查角色，只验证不修复。
> **模型**: opus 4.6（审查需要判断力）

**触发时机**：开发 Agent 每完成 1 个 task 并 git commit 后，立即 spawn 一个 Validator 子代理。

**Validator 的职责**：
1. 读取 `planning/prd.json` → 找到当前刚完成的 task（status: "done" 且 completedAt 最新的）
2. 逐条验证该 task 的 `acceptance[]`：
   - 涉及 UI 的条目：启动 dev server → 浏览器打开 → 截图验证（截图存 `e2e/screenshots/validator-{task-id}-{pass|fail}.png`）
   - 涉及数据库的条目：检查 Supabase API 调用是否存在且参数正确
   - 涉及交互的条目：模拟点击/输入 → 检查结果
   - 涉及样式的条目：截图对比颜色/布局
3. 所有 acceptance 通过 → 不修改 prd.json（保持 done），清空 notes
4. 任一 acceptance 未通过 → 写入结果：

```
prd.json 更新：
  status: "pending"（改回待做）
  notes: "[验证失败-第N次] 2026-06-18 16:30\n- 失败项：点击提交后未跳转任务详情页\n- 建议修复：检查 setNav 调用是否在 POST 成功回调中"
  retryCount: +1（需在 prd.json task 中新增此字段，从0开始）
```

5. retryCount >= 3 → `blocked: true`，notes 追加 `[BLOCKED: 已达最大重试次数]`

**Validator 的约束**：
- 只验证，不修复代码
- 只操作当前这一个 task，不越界验证其他 task
- 不修改 prd.json 除 status/notes/blocked/retryCount 以外的字段
- 验证完成后正常退出

### ④ 验证（E2E）

先判断任务类型（从 `planning/status.json` 的 `taskType` 读取）：

**模式 A — 全量验证**（新功能、功能优化）
1. 读取 `planning/prd.json` → 遍历所有 `status: "done"` 的 task → 逐条验证 `acceptance[]`
2. 同时读取 `planning/test-cases.md`，按「正常流程」→「异常与边界」顺序执行全部用例
3. 通过改 `[x]`，失败标注失败原因
4. prd.json 中验证不通过的 task → `status` 改回 `"pending"` → 回退到 ④ 开发

**模式 B — 定点验证**（Bug 修复、文案/样式）
1. 只跑与改动相关的用例（看 git diff 涉及的文件）
2. 额外跑冒烟测试：核心主流程能走通即可

```bash
# 全量验证
/home/admin/.local/bin/playwright test e2e/

# 定点验证（只跑某功能）
/home/admin/.local/bin/playwright test e2e/<功能名>.spec.ts

# 冒烟测试（只跑 @smoke 标记的用例）
/home/admin/.local/bin/playwright test --grep @smoke
```

测试脚本位置：`e2e/<功能名>.spec.ts`，冒烟用例加 `@smoke` 标记，失败截图存 `e2e/screenshots/`，提交到 git。

### ⑤ 代码评审
- Skill: `code-review` + `simplify`

### ⑥ 上线部署
- Skill: `prod-deploy`

---

## 跳过规则

| 任务类型 | 走哪些阶段 | E2E 模式 |
|---|---|---|
| 新功能 | ①→②→③→④→⑤→⑥ | 全量验证 |
| 功能优化 | ②→③→④→⑤→⑥ | 全量验证 |
| Bug 修复 | ③→④→⑤→⑥ | 定点验证 + 冒烟 |
| 文案/样式 | ③→④→⑥ | 冒烟测试 |
| 紧急修复 | ③→④→⑥ | 冒烟测试 |

## 回退规则

| 场景 | 回退到 |
|---|---|
| 验证发现功能不对 | → ③ 开发（改代码）|
| 评审发现设计问题 | → ② PRD（改需求）|
| 上线后发现 bug | → ③→④→⑥ 快速发布 |

---

## planning/status.json 格式（含自动驾驶扩展字段）

```json
{
  "currentStage": "development",
  "completedStages": ["requirements", "prd", "tech-plan"],
  "lastUpdated": "2026-06-18T10:00:00",
  "taskType": "new-feature",
  "notes": "项目描述",
  "locked": true,
  "autoAdvance": true,
  "correctionPending": false,
  "consecutiveHeartbeatsBlocked": 0,
  "engine": {
    "draftPending": null,
    "stageArtifacts": {}
  }
}
```

**`autoAdvance: false`** = 用户暂停自动驾驶，L2 心跳静默退出。  
**`locked: true && autoAdvance: true`** = 进入 Studio 驱动模式，L2 按 currentStage 自动推进。  
**回退时**：把 currentStage 改回目标阶段，completedStages 不删（保留历史）。

### 主任务锁行为规则（locked=true 时）

用户发的每条消息，先判断是"推进主任务"还是"临时插入"：

| 信号 | 判断 | 怎么做 |
|---|---|---|
| 和 status.json 的 notes/taskType 相关 | 主线 | 正常推进，阶段结束时更新 status.json |
| 完全无关的问题（如"帮我查个命令"）| 临时插入 | 回答完就回来，不动 status.json |
| 说"先做另一件事"或切换项目话题 | 可能切换主线 | 先问"要暂停当前任务吗？"再决定 |
| 说"回到主线"/"继续之前的" | 恢复主线 | 读 status.json 报告当前状态 |

**铁律：**
- 临时问题不改 status.json——问完即忘，主线不受影响
- 切换主线需要明确确认——不能因为聊了几句别的就把 currentStage 改了
- 新对话进入时：先读 status.json，如果 locked=true，主动报告"上次走到 XX 阶段，主任务是 YY，要继续吗？"

---

## 辅助 Skill（按需调用）

| Skill | 什么时候用 |
|---|---|
| `excalidraw-diagram-skill` | PRD 阶段需要画流程图时 |
| `devix-dingtalk-skill` | PRD 写入钉钉文档时 |
| `agents-map` | 进入新项目需要理解全貌时 |
| `zujianfuyon` | 开发阶段需要复用组件时 |
| `memory` | 任何时候需要记住决策时 |

---

## CodeGraph 融合层

```
CODEGRAPH_FUSION: v1.0
FILES: codegraph/{capability-registry,engine-touchpoints,integration-rules}.json
SYNC_HOOK: hooks/codegraph-sync.py
HEALTH_SCORER: scripts/route-health-scorer.py
TOUCHPOINTS: 8 | RULES: 8
```

## 上下文污染防护清单

每次调度器激活时确认：
- [ ] 子代理通过 Agent 工具 spawn（不是 Skill 工具）
- [ ] 子代理 prompt 中不包含对话历史
- [ ] 子代理只读 structured data files，不读 audit/transcript
- [ ] 子代理返回的是 JSON，不是长文
- [ ] 主会话只输出摘要，不展开讨论
