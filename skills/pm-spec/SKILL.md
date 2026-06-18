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
repository: https://code.alibaba-inc.com/qunbu/pm-spec
---

# Product Spec Skill

Produce a one-page product spec / PRD.

## Workflow

1. Read the active DESIGN.md.
2. Identify the feature + audience from the brief.
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

## Output contract

```
<artifact identifier="spec-name" type="text/html" title="Spec Title">
<!doctype html>...</artifact>
```

---

## 什么让 PRD 失去价值——自检清单

写完每个功能节点后，用这 4 个问题自检。**只要有一个答案是"不知道"，就说明写得不够细，必须补。**

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
