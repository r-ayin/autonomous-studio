---
name: pm-spec
description: |
  Product spec / PRD as a single page — problem, success metrics, scope,
  user stories, design notes, rollout plan, open questions. Use when the
  brief mentions "PRD", "spec", "product spec", "feature brief", or "需求文档".
triggers:
  - "prd"
  - "spec"
  - "product spec"
  - "feature brief"
  - "feature doc"
  - "需求文档"
od:
  mode: prototype
  platform: desktop
  scenario: product
  preview:
    type: html
    entry: index.html
  design_system:
    requires: true
    sections: [color, typography, layout, components]
  example_prompt: "Write me a PRD for adding two-factor auth to our SaaS app — problem, scope, milestones, open questions."
repository: https://code.alibaba-inc.com/qunbu/autonomous-studio
version: 1.0.0
---

# Product Spec Skill

Produce a one-page product spec / PRD.

## Workflow

1. Read the active DESIGN.md.
2. **Read `~/.claude/skills/pm-spec/example.html`** — this is the canonical template. Copy its complete CSS (`:root` variables like `--ink`/`--accent`/`--border`, layout classes `.wrap`/`.header`/`.problem`/`.goals`/`.node`/`.node-title`/`.scope-bar`/`.q-box`), and the entire annotation system (`#anno-bar` + `#anno-sb` DOM + the `A` JS module) verbatim. Do not invent new styles. Replace the placeholder content (`{{TITLE}}`, "节点 1 名称", etc.) with real PRD content.
3. Identify the feature + audience from the brief.
3. Layout:
   - Header strip: title, status pill (Draft / Review / Approved), date, owner.
   - Three-line summary at the top — what, who, why now.
   - "Problem" panel with one paragraph and a quote from a customer or
     internal partner.
   - "Goals & non-goals" two-column block.
   - "Success metrics" table with metric / target / measurement.
   - "功能需求" section organized by **workflow node** (not by feature category).
   - "Scope" milestone tracker (3–4 phases).
   - "Open questions" with assignee chips — business questions only, not technical implementation.
4. One inline `<style>`, semantic HTML, accent used twice max.
5. **发布预览前必须归档**：生成新版本 PRD HTML 后，执行「批注归档 + 同步预览文件」动作（见下「批注归档规则」），否则用户打开预览看到的仍是旧版本，旧批注也会错位高亮在新版页面上。

## Output contract

```
<artifact identifier="spec-name" type="text/html" title="Spec Title">
<!doctype html>...</artifact>
```

## 预览与批注

PRD 生成后自动启动预览服务器，用户可在浏览器中阅读并添加批注：

```bash
node ~/.claude/skills/pm-spec/prd-preview-server.js [项目目录]
```

批注存储在 `planning/annotations.json`，格式：
```json
[{"id":"ann-...","selectedText":"被选中的文字","comment":"批注内容","contextBefore":"前30字符","contextAfter":"后30字符","createdAt":"ISO时间"}]
```

读取批注用于修改 PRD：直接读 `planning/annotations.json` 即可获取所有批注反馈。

## 批注归档规则

`annotations.json` 是**项目级共享的批注池**，所有版本 PRD 共用同一个文件。新版本 PRD 上线预览时，若旧批注还留在里面，会以高亮形式显示在新版本页面上——这些批注针对的是已不存在的旧内容，用户会困惑"我没看过怎么就有批注了"。

### 何时归档

**每次生成新版本 PRD（含细节迭代 v5→v5.1）并准备预览时，都必须先归档再清空 `annotations.json`。**

判断标准不是"批注锚点能否命中"，而是"PRD 正文是否因批注而改过"。只要本轮是根据上一轮的批注修改了正文生成了新版本，就必须归档——因为新版本正文已经是修改后的内容，旧批注如果留在新版本页面上，用户无法区分"这条批注我提过、改没改"。归档让旧批注进历史，新版本正文呈现修改结果，用户通过对比归档版本确认改动。

只有纯微调（修错别字、调样式，未改任何批注涉及的正文）才不归档。

### 怎么归档

归档按**大版本文件夹**组织，同一大版本下的细节迭代（如 v5.1、v5.2）归到该版本文件夹下，用小编号子目录区分。结构：

```
planning/archive/
  V5/                         # 大版本（取 PRD 文件名里的大版本号整数部分）
    V5.0/                      # 首版
      prd.html                 # 该版本 HTML 快照
      annotations.json        # 该版本收到的批注（原样保留）
    V5.1/                      # 细节迭代（根据 V5.0 批注修订后生成）
      prd.html
      annotations.json        # V5.1 收到的新批注
  V4/
    V4.0/
      prd.html
      annotations.json
```

1. **归档当前版本到版本文件夹**：在生成新版本 HTML 前，把当前 `prd.html` + `annotations.json` 复制到 `planning/archive/V{大版本}/V{大版本}.{迭代号}/`。大版本号取自被归档 PRD 的 title/文件名版本整数部分（`prd-v5.1.html` → `V5`）。迭代号 = 该大版本文件夹下已有子目录数（首版 V5.0，依次递增 V5.1、V5.2）。
2. **同步新 HTML 到预览文件**：把生成的新版本 PRD（如 `prd-v5.1.html`）复制为 `planning/prd.html`——预览服务器固定读 `prd.html`。版本化文件（`prd-vN.M.html`）保留作为历史留档。
3. **清空当前批注**：归档后把 `planning/annotations.json` 置为 `[]`，让新版本预览干净。
4. **告知用户**：回复里说明"已归档到 planning/archive/V5/V5.0/（含原 PRD 和你的批注），新版本 v5.1 正文已按批注修改，预览已就绪。可在 archive 目录查看历史批注"。

### 为什么这样设计

- **每次迭代都归档而非只在大版本归档**：细节迭代（v5→v5.1）同样是根据批注改了正文。若不归档，旧批注留在新版本页面上，用户无法确认"我提的疑问改了没"——这正是核心痛点。归档让旧批注进历史，新版本正文呈现修改结果，用户通过对比归档版本确认改动。
- **新版本正文必须是修改后的**：归档不是目的，改正文才是。生成 v5.1 时必须逐条处理上一轮批注，把疑问改进正文，而非原样保留旧文本。
- **归档里保留原批注**：用户想回看"我当时提了什么"时，打开 `archive/V5/V5.0/annotations.json`（或对应的归档 HTML）即可，原批注一字不动。
- **归档后清空而非保留**：批注锚点在新版本里位置已变，保留只会错位高亮，不如清空让用户在新版本上重新批注下一轮。

---

## 什么让 PRD 失去价值——自检清单

写完每个功能节点后，用以下问题自检。**只要有一个答案是"不知道"，就说明写得不够细，必须补。**

### 自检问题 1：研发看完知道"点什么"吗？

不是"支持查看详情"，而是"点击详情按钮 → 弹出侧边栏，展示 XXX 字段，默认展开 YYY 面板"。

如果你的功能描述删掉所有动词（点击/输入/选择/触发），剩下的只是名词列表，说明交互没写。

### 自检问题 2：研发看完知道"有什么限制"吗？

不是"支持配置人数"，而是"3≤M≤10，任务创建后不可修改"。

每个可配置项都应该有：取值范围、默认值、创建后能否修改、取消时怎么处理。

### 自检问题 3：研发看完知道"改了 A，B 怎么变"吗？

不是"两个功能有关联"，而是"当 [配置A=X] 时，[模块B] 的行为变为……"。

跨节点/跨模块的触发-响应关系，必须显式写出来，不能靠研发猜。

### 自检问题 4：开放问题是"业务问题"还是"技术问题"？

PRD 的开放问题应该是：这个功能边界该怎么划？这个优先级该怎么定？用户看到什么文案？

**不应该有**：用什么框架？用哪个 LLM？数据库表结构怎么设计？这些属于技术方案，不属于 PRD。

### 自检问题 6（流程重构类必查）：每个阶段"谁做什么决策、需要什么信息"写清了吗？

当一个 PRD 把流程从「一步」改成「多阶段」（如「主管全包」→「主管定方向→组长选人→主管确认」三段式），最容易踩的坑是**只写了状态流转和按钮，没写每阶段的业务意图**。研发按 PRD 实现了状态枚举和按钮，但「页面在这个阶段该给角色看什么信息」——这恰恰是重构的核心价值——因为 PRD 没写而没做，上线后用户发现「多了一道流程，体验却没变」。

**判据**：对流程里的每一个阶段，PRD 必须能回答三件事：
1. 这个阶段由**哪个角色**做主？
2. 他要做的是**哪个决策**（不是"审核"，而是"接不接？派给谁带？"这种具体决策）？
3. 做这个决策**需要什么信息**，以及——同样重要的——**哪些信息此时还没产生、不该露出**？

**信息露出原则**：页面可见信息必须服务于"当前阶段 + 当前角色"要做的那个决策。后续阶段才产生、或与当前决策无关的信息，在当前阶段不展示。这条要写成 PRD 的不变量，**不要写成封闭的「隐藏 Tab A/B/C」清单**——因为后续一定新增面板，封闭清单挡不住，研发加新面板时不知道该不该在各阶段显示，又会回到「全显示」。给研发一个判据（「这条信息服务于当前阶段决策吗？」），让他理解业务后自己判断，新增面板也能放对位置。

**反面案例（真实事故）**：V9.3 三段式重构写了 9 个任务全是状态枚举/按钮/流转，没有一个任务写「主管在定方向阶段只需看到决策必需信息」。结果主管打开待审核任务，仍能看到执行名单/话术/拉群/监控/沉淀全套，跟改之前一样——三段式「让主管集中高价值决策」的价值没兑现。根因不在代码漏改，在 PRD 漏写了每阶段的决策与信息需要。

**为什么单列一题**：前 5 题查的是"功能节点写得够不够细"，这题查的是"流程重构的业务意图有没有传达给研发"。前者漏了研发会问，后者漏了研发会按字面实现状态机然后交付一个"流程加了但价值没兑现"的产物——这种事故最隐蔽，因为状态和按钮都在，验收容易过，但用户体验没改善。

---

## 页面交互的固定格式

每个功能节点的页面交互部分，**必须按以下顺序用无序列表写**，不能合并、不能跳过：

```
#### 页面交互

- **页面入口**：用户从哪里进入这个功能（菜单路径 / 按钮位置）
- **展示内容**：页面上显示什么信息（列表字段、卡片内容、状态标签等）
- **操作项及点击效果**：每个可操作元素点击后发生什么，格式："点击「X」→ 发生Y"
- **特殊状态提示文案**：空状态、报错、警告、确认弹窗的文案，精确到原文，不写"提示用户"
```

**为什么要按这个顺序**：用户进页面的第一件事是找入口，找到后看内容，然后操作，操作时遇到异常看文案。这个顺序就是用户的实际体验路径，研发按这个顺序读 PRD 不需要来回翻。

---

## 功能联动与异常场景的固定格式

每个功能节点写完页面交互后，**必须追加以下两个小节**：

```
#### 功能联动

当本节点的状态/配置变化时，哪些**其他节点**会受影响？格式：
- 当 [本节点事件] → [其他节点] 的行为变为……

必须覆盖：
1. 本节点的创建/修改/删除/停用 对下游节点的影响
2. 上游节点变化 对本节点的影响
3. 跨角色操作的连锁反应（A 角色的操作导致 B 角色看到什么变化）

#### 异常与边界

本节点可能出现的异常场景，格式：
| 场景 | 预期处理 |
|------|----------|

必须覆盖：
1. 并发操作（两个人同时操作同一数据）
2. 前置条件失效（操作到一半，前置状态被别人改了）
3. 资源耗尽（名额满、时间槽用完、列表为空）
4. 数据级联（删除/停用时，关联数据怎么处理）
5. 权限变更（操作过程中权限被收回）
```

**为什么要写这两节**：研发最常踩的坑不是"正常流程不知道怎么做"，而是"A 模块改了一个配置，不知道 B 模块要不要跟着变"。功能联动和异常场景写不清楚，上线后就是 bug。

**自检问题 5（新增）：研发看完知道"改了节点 A，节点 B/C/D 怎么变"吗？**

不是"关闭职位后顾问不能推荐"，而是"关闭职位 → 顾问提交页下拉列表不显示该职位 + 该职位下进行中的候选人状态不受影响 + 已锁定的面试时间槽保留 + 钉钉群不再推送新消息"。

每个联动关系都要写清楚**触发条件**、**影响范围**和**不影响什么**（显式排除比隐式遗漏安全）。

---

## 功能节点的写法（举一反三）

### ❌ 错误写法（格子填完了，但研发看完还是不知道怎么做）

```
| 功能 | 说明 |
|---|---|
| 多人投票 | 支持配置多人进行标注，系统取超过半数的答案作为最终结果 |
| 质检范围 | 支持配置质检范围，包括全部/一致/不一致数据 |
```

**问题**：投票人数范围是多少？创建后能改吗？"超过半数"是严格大于还是大于等于？质检范围改了会影响什么？全不知道。

### ✅ 正确写法（研发看完能直接开工）

**多人投票节点**

| 配置项 | 功能说明 | 约束 |
|---|---|---|
| 投票人数 M | 配置参与投票的标注员数量 | 3≤M≤10；任务创建后不可修改 |
| 结果拟合时机 | M 份结果全部提交后产生最终结果 | 不支持部分提交就出结果 |
| 结果拟合规则 | 票数严格大于 M/2 则采纳；无项目超过则置空 | by 组件类型有差异（见下表） |

处理规则（按组件类型）：

| 组件 | 规则 | 举例（M=4）|
|---|---|---|
| 单选 | 统计每个选项票数，>M/2 采纳 | 甲A乙A丙B丁B → 置空（2票=2票） |
| 多选 | 拆成选项粒度分别投票 | 甲ABC乙AB丙AB丁A → 最终：A、B |

页面交互：
- 点击「取消质检节点」→ 弹窗："多轮标注不一致数据将无质检最终结果，系统将取超过半数的答案作为最终结果，当无答案超过半数时，该题结果置空" → 点确认 → 质检节点从流程图中移除

功能联动：
- 当投票模式开启时 → 质检节点默认自动选中；取消质检时需二次确认
- 当 M≥5 时 → 系统在配置页面显示性能警告："投票人数≥5 可能影响系统性能"

---

## 不要写的内容

**PRD 里不该有技术选型**：前端框架、数据库选型、LLM 选择、部署平台 → 这些属于技术方案文档，不属于 PRD。写了只会分散注意力，让评审者以为 PRD 说的是"怎么实现"而不是"要做什么"。

**不要用 as-a/I-want/so-that 用户故事替代功能需求**：用户故事描述"用户动机"，不描述"系统行为"。研发需要的是系统行为，不是用户动机。用户故事可以放在背景部分解释为什么要做，不能替代功能规格。

---

## 触发保障规则

**必须通过本 Skill 生成 PRD HTML**，不要手动拼写 HTML。原因：

1. 手动拼 HTML 会绕过自检清单（4 个自检问题）、页面交互固定格式、功能联动与异常场景模板
2. 手动拼 HTML 不会自动带批注系统（annotation JS + API），用户无法在线批注
3. `prd-preview-server.js` 是标准预览方式，包含批注持久化和公网预览

**触发链路：**
- 用户"聊需求/讨论需求" → 先走 `demand-discovery` Skill 梳理清楚
- 需求确认后 → 调用本 Skill (`pm-spec`) 生成正式 PRD
- 生成后 → 用 `prd-preview-server.js` 启动预览 + `port-mapping` 获取公网链接
- 即使当前处于开发阶段，用户明确要聊需求也要响应，走 demand-discovery → pm-spec 链路
