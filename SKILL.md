---
name: autonomous-studio
description: >-
  自主决策引擎 v3.1（autonomous_studio）— Studio × Autonomous-Engine 全量融合。
  双轨架构：L2 执行轨（7min）+ L3 研判轨（60min），检查点保护执行。
  7 阶段 Studio 流水线 + 路线健康度诊断 + 路线修正协议。
  + CodeGraph 融合层 v1.0（代码语义视角·8触点8规则）。
  触发词：自主模式、别等我、自动继续、keep working、autonomous mode、auto-develop、
  决策引擎、继续开发、不用等我、你自己做、auto-continue、studio auto on、继续、
  接下来做什么、下一步、studio、全链路、开发流程、从需求到上线、项目状态。
model: sonnet
repository: https://code.alibaba-inc.com/qunbu/autonomous-studio
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
    artifact 不存在 → 生成 prd.md + test-cases.md（调用 demand-discovery SPEC 模板）
    confirmed=true → 推进 currentStage="tech-plan"，下次 L2 生成 tech-plan

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
需求 → PRD → 技术方案 → 开发 → 验证 → 评审 → 部署
        ↑                              ↓
        └──── 验证不通过时回退 ─────────┘
```

### ① 需求探索
- Skill: `demand-discovery`（含 grill-me 压力追问）
- 产出: `planning/requirements.md`

### ② 写 PRD
- Skill: `pm-spec`
- 输入: 自动读取 `planning/requirements.md` + 已有代码库
- 产出: `planning/prd.md` + `planning/test-cases.md` + 写入钉钉文档（如需评审）
- **格式规范**：按工作流节点组织（不按功能分类）：配置项 → 页面交互 → 功能联动 → 异常与边界

**PRD 完成后必须同时生成 `planning/test-cases.md`**：

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

### ③ 技术方案
- Skill: `plan-feature`
- 产出: `planning/tech-plan.md`（代码库分析 → 模式识别 → 分步任务 → 验证命令）

### ④ 代码开发
- Skill: `serial-agent-handoff`
- 输入: 自动读取 `planning/tech-plan.md`
- 完成后自动 `git add` + `git commit` + `git push`

### ⑤ 验证（E2E）

先判断任务类型（从 `planning/status.json` 的 `taskType` 读取）：

**模式 A — 全量验证**（新功能、功能优化）
1. 读取 `planning/test-cases.md`，按「正常流程」→「异常与边界」顺序执行全部用例
2. 通过改 `[x]`，失败标注失败原因

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

### ⑥ 代码评审
- Skill: `code-review` + `simplify`

### ⑦ 上线部署
- Skill: `prod-deploy`

---

## 跳过规则

| 任务类型 | 走哪些阶段 | E2E 模式 |
|---|---|---|
| 新功能 | ①→②→③→④→⑤→⑥→⑦ | 全量验证 |
| 功能优化 | ②→④→⑤→⑥→⑦ | 全量验证 |
| Bug 修复 | ④→⑤→⑥→⑦ | 定点验证 + 冒烟 |
| 文案/样式 | ④→⑤→⑦ | 冒烟测试 |
| 紧急修复 | ④→⑤→⑦ | 冒烟测试 |

## 回退规则

| 场景 | 回退到 |
|---|---|
| 验证发现功能不对 | → ④ 开发（改代码）|
| 评审发现设计问题 | → ② PRD（改需求）|
| 上线后发现 bug | → ④→⑤→⑦ 快速发布 |

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
