# 阶段三：开发 + Validator + 全量对照（开发期）

> 执行代码开发、单任务审查、全量 PRD 对照时加载本文件。

## ③ 代码开发

- Skill: `serial-agent-handoff`
- 输入: 自动读取 `planning/prd.json`
- 完成后自动 `git add` + `git commit` + `git push`

### GLM 代码风格纪律（使用非前沿模型时强制生效）

GLM-5.2 / Qwen / DeepSeek 等中等模型最常见的质量问题不是"写不出"而是"改太多"。以下规则强制：

1. **最小改动**：只改完成 task 必须改的代码。不"顺手"重构、不"优化"无关文件、不抽取只用一次的公共函数。
2. **不必要抽象禁止**：一段逻辑只用一次就直接内联，不要"为了复用"提取 util/helper。
3. **保持现有风格**：改文件前先读已有 30 行，确认命名规范（camelCase/snake_case）、缩进（tab/space）、引号（单/双），然后严格一致。
4. **禁止创造性重命名**：不要把已有变量/函数/文件改名为"更好的"名字。保持原名。
5. **diff 自检**：每次修改后检查 diff 行数，超过 task 预期改动量 2 倍立即停下审查、删多余改动。

违反任一条 → Validator 标 ❌ 并要求回滚不必要的改动。

### Task 粒度与验收标准（auto-coding-v2.1 对齐）

> 这两条决定 prd.json 能不能被子 agent 干净执行：粒度太大→子 agent 上下文用完产生半截坏代码；验收不可验证→Validator 没法二元判定，沦为"看起来还行"。

**1. Task 粒度第一规则：每个 task 必须能在一次子 agent 上下文（一个 context window）内完成。**
- 经验法则：用 2-3 句话描述不清的改动 = 太大，必须拆。
- 拆分示例："添加用户通知系统" 不是 1 个 task，要拆成：① 建表/migration ② 发通知 service ③ 铃铛图标组件 ④ 下拉面板 ⑤ 已读功能 ⑥ 偏好设置页 —— 每个独立可完成可验证。
- 依赖排序：schema/DB 变更 → 后端逻辑 → 用后端的 UI → 聚合看板。后置 task 可依赖前置，不能反过来。
- 大功能默认按"文件边界 + 数据流阶段"拆，宁多勿大。

**2. 验收标准必须可验证，且每条 task 必含两项硬性 acceptance：**
- 所有 acceptance 必须是可 grep/可跑/可断言的——禁止"工作正常""良好的 UX""处理边缘情况"这种模糊词（Validator 没法判）。
- **每个 task 末尾必加**：`"Typecheck passes（webpack --mode production 无 error / tsc --noEmit 无 error）"`
- **UI 类 task 额外必加**：`"browser verify（点开页面走该功能，截图或描述实测行为）"` —— 前端 task 在浏览器实跑前不算 done，子 agent 用 Playwright 带登录态或人工实跑。
- 配套：`planning/task-evidence.json` 给每个 task 配"代码特征"（file×pattern grep 证据），`studio-status-sync.sh` 据此自动判定 done/partial/manual，不靠自觉。

**3. 执行模型：并行的串行（不是写完一起审）。**
- 多个不重叠文件可并行分支，但**每个分支内部是完整闭环**：写（sonnet）→ Validator（opus）→ 修必修 → 过。不是"3 个一起写完 → 1 个中央 Validator"。
- 单文件多 task → 纯串行，一个 task 一个闭环。
- 全部 done 后控制器做 **③-R 全量对照 PRD**（见下）+ 整体构建 + 实跑关键路径，才能标阶段完成。

### UI 视觉设计参考（react-bits）

写 UI 代码时，视觉特效可参考 [react-bits](https://github.com/DavidHDev/react-bits)（130+ 动画组件库）的效果思路（**只是参考素材，不是照搬**——你作为世界上最厉害的设计师，从中融合、举一反三，写出比原组件更好、更贴合需求主题的 UI），完整目录见 `~/.claude/skills/kanban-automation/recipes/design-reference-react-bits.md`：
- 数字 **CountUp** 滚动、标题 **GradientText** 渐变、入场 **ScrollReveal**、卡片悬停 **GlareHover**、背景 **DotGrid**
- **用纯 CSS 实现**，不要 npm install react-bits 全包（它依赖 three.js/gsap/framer-motion 重量级库，OneDay 平台走 CDN 会白屏）
- 信息密集页（看板/后台）效果要克制，避免 3D 背景/闪电/故障文字抢焦点 + 白屏风险

> react-bits 是**视觉特效层**，不替代 `zujianfuyon`（**业务集成层**：钉钉拉取/Supabase 客户端/钉钉机器人）。看板两层都要——数据推送用 zujianfuyon，视觉激发用 react-bits。

**双模型分工**：
| 模型 | 做什么 | 调用方式 |
|---|---|---|
| sonnet | 写代码（按 prd.json 逐条执行） | Claude Code Agent `model: "sonnet"` |
| opus | 审查验证、Bug修复、规划讨论、③-R 全量对照 | Claude Code Agent `model: "opus"` |

**子 agent 上下文策略**：
| 子 agent | 给什么上下文 |
|---------|------------|
| 写代码（sonnet） | 完整 prd.json + prd-decisions.md + codebase-patterns.md + 当前 task + 项目 CLAUDE.md |
| Validator（opus） | 完整 prd.json + prd-decisions.md + codebase-patterns.md + 当前 task + git diff |
| ③-R 全量对照（opus） | 完整 prd.json + prd-decisions.md + codebase-patterns.md + git log + test-cases.md |

> 给完整 prd.json 的原因：跨 task 的数据关系（字段名、状态流转）只有看全局才能发现集成问题。

**prdRef 回溯引导**：每个 task 有 `prdRef` 字段（如 `"planning/prd.md#3.2-报告阶段"`），指向原始 PRD 对应章节。子 agent prompt 中必须包含以下指令：
> 如果当前 task 的 description 不够理解需求（如缺少业务规则、边界条件、交互细节），用 Read 工具读取 task.prdRef 指向的 PRD 章节获取完整上下文，不要猜测。

### Codebase Patterns（跨 task 经验积累）

文件：`planning/codebase-patterns.md`，开发阶段首个 task 开始前自动创建（不存在则创建空模板）。

**作用**：前面 task 踩过的坑、发现的项目惯例、容易漏的关联改动，积累下来给后面的 task 复用。避免同一个项目里，第 1 个 agent 踩过的坑第 5 个 agent 又踩一遍。

**写入时机**：每个 task 完成（status=done）后，子 agent 必须检查本次开发是否有值得记录的经验，有则追加到文件末尾。Validator 发现的典型问题修复后也追加。

**写入规则**：
- 只记**通用可复用**的 pattern，不记 task 专属细节（"N1-03 改了 XX"不记，"改 store 函数时必须同步更新 types.ts 的导出"要记）
- 每条一行，带发现来源标记
- 文件只追加不删改，不超过 50 条（超出时主控删最早的）

**格式**：
```markdown
## Codebase Patterns
<!-- 子 agent 开发前先读此文件，避免重复踩坑 -->

- [N1-02] store 里新增函数后必须在 adminActions.ts 的 STORE 对象里挂载，否则 View 层调不到
- [N1-03] insertTaskChangeLog 的 old_status/new_status 必须是 statusConstants 里的值，不能写字符串字面量
- [N1-05] 改 notifications 表结构后要同步改 groupNotify.ts 的查询字段，否则推群静默失败
```

**子 agent prompt 中必须包含以下指令**：
> 开始写代码前先读 `planning/codebase-patterns.md`（如果存在），了解前面 task 积累的项目经验和踩坑记录。完成本 task 后，如果发现了通用可复用的经验（如"改 X 时必须同步改 Y"、"这个项目用 Z 方式处理某类问题"），追加一条到该文件。

**prd.json 驱动开发流程**（全自动，不中断用户）：
1. 读取 `planning/prd.json` → 按节点顺序遍历
2. 只处理 `status: "pending"` 且 `priority: "P0"` 且 `blocked: false` 的任务
3. 开始 → `status: "in_progress"`
4. 完成 → `status: "done"` + `completedAt` + 清空 `notes`
5. git commit：`feat: [N1-01] 任务标题`
6. 立即触发 Validator（见 ③-V）
7. Validator 通过 → 继续下一个
8. Validator 失败 → 执行 **Reflexion 修复协议**（最多 2 轮，用外部信号反馈，不是自我反思）：
   - **轮次 1**：读 Validator 报告的 ❌ 条目（这是外部信号，不是自己重新审查代码）→ 对每个 ❌ 提取"预期行为+实际行为+涉及文件"→ 只改必要代码（不重构不优化）→ 重新触发 Validator → 通过则继续下一个 task。
   - **轮次 2**（轮次 1 仍有 ❌ 时）：先对比轮次 1 的修复与新 ❌，判断是否引入新问题；新问题 → `git checkout` 回滚到轮次 1 之前重新分析；同一问题未修好 → 换一种实现思路再试 → 重新触发 Validator。
   - **关键**：Reflexion 的输入必须是 Validator 报告（外部二元信号），不是让模型自己重新审查代码——中等模型纯自我反思可能零提升甚至越改越坏。
9. 同一 task Reflexion 2 轮仍失败 → `blocked: true`，notes 写入两轮尝试的失败原因摘要，跳过并记录（第 3 轮及以后中等模型修复成功率接近 0 但 token 线性增长，不值得继续）。
10. 每完成一批 → 输出进度摘要
11. 所有 P0 done → 自动触发 ③-R 全量对照评审

**Hook 自动检查**：开发过程中 PostToolUse Hook 自动：
1. 每次修改 prd.json → 验证格式（不合法报错打回）
2. 每次修改 prd.json → 检查 P0 进度，全部完成自动触发 ③-R
3. 源代码改动超 3 个文件未提交 → 提醒 commit

**不中断原则**：整个开发循环不停下来问用户。只在技术阻塞或全部完成时暂停。

### ③ 并行开发子模式（多任务可并行时启用）

当 prd.json 有多个独立任务（无 blockedBy 依赖、改动文件不重叠）时，控制器可派多个子 agent 并行开发提速。但并行≠省验证，必须守以下纪律：

**拆分原则**：
1. **按功能边界拆，文件不重叠**：一个子 agent 负责一组任务，同一文件只能给一个 agent。若两个任务都要改 `engine.ts`，合并给同一个 agent 串行做，不能拆给两个（否则并发改同一文件会冲突丢改）。
2. **子 agent 只改不提交**：子 agent 完成后只回报改了什么，**不 git commit**。控制器统一做构建验证 + 提交。理由：子 agent 各自提交会产生碎片提交、且无法做整体集成检查。
3. **每个子 agent 的 prompt 必须含**：要改的文件清单（限定范围，禁止越界改其他文件）、对应 prd.json task 的验收标准、依赖的上下文字段说明。

**闭环（不可跳过）**：
4. 所有子 agent 完成 → 控制器先做**整体构建验证**（webpack/tsc 能编译）。
5. 构建 OK → **必须跑 Validator 审查 agent**（opus，读完整 diff + prd.json，输出 review-findings.md，标必修/建议/可后续）。
6. 控制器**读 review-findings.md，修完所有必修阻塞项**，不能只修一部分就汇报。
7. 修完 → **实跑关键路径**（不只编译，要点开页面走功能：权限、推荐方案、改判、质检等核心流程点一遍）。
8. 全部通过 → 才能标记 task done + 更新 status.json + 向用户汇报。

**禁止行为**：
- ❌ 派完子 agent、只看构建通过就汇报”完成/好了”——审查未做、必修项未修就是谎报。
- ❌ 子 agent 自己 git commit——必须控制器统一提交。
- ❌ 同一文件拆给多个子 agent——会冲突。
- ❌ 跳过实跑验证直接汇报——编译过≠功能对。

> 为什么有这套纪律：并行子 agent 各改各的，能编译但功能可能坏（如缺字段导致方法匹配不到、前端标签没同步去掉）。只有”开发→审查→修复→实跑”四步全走，才能把”能编译”变成”真做好”。控制器是主管，对最终质量负责，不是把活派出去就完事。

## ③-V 单任务 Validator

> 独立审查角色，只验证不修复。模型: opus

**触发时机**：开发 Agent 每完成 1 个 task 并 git commit 后立即 spawn。
**上下文**：完整 prd.json + prd-decisions.md + 当前 task + git diff

**三维度审查**：
| 维度 | 检查什么 |
|------|---------|
| 正确性 | acceptance 条件逐条验证，有无 Bug |
| 代码风格 | 命名规范、文件组织、是否符合项目现有模式 |
| PRD 一致性 | 实现是否完整覆盖 prd.json 的 description，有无遗漏字段/交互/边界处理 |

**输出格式**：
```
## Validator 报告 [N1-01]
### 正确性：✅ 通过 / ❌ 不通过
- [x] 验收条件1：提交成功跳转列表 ✓
- [ ] 验收条件2：推荐理由<10字时按钮置灰 ✗（未实现置灰，只有 toast）
### 代码风格：✅ 通过 / ⚠️ 建议
- 命名：符合项目 camelCase 规范
- ⚠️ 建议：fetchData 函数可提取为共用 hook
### PRD 一致性：✅ 通过 / ❌ 不通过
- [x] 数据从 applications 表读取 ✓
- [ ] PRD 要求"请假状态灰色显示"，代码中未找到对应样式处理
```

**判定规则**：任一维度 ❌ → task 回退为 pending，notes 写入失败原因，retryCount +1。仅 ⚠️ 不阻塞。retryCount >= 3 → `blocked: true`。

## ③-R 全量 PRD 对照评审

> 所有 P0 tasks done 后、进入 E2E 之前自动触发。模型: opus

**触发时机**：Hook 检测到 prd.json 所有 P0 tasks 均为 `done`，自动 spawn。
**上下文**：完整 prd.json + prd-decisions.md + git log（本次功能所有提交）+ test-cases.md

**检查三件事**：
| 检查项 | 具体问题 |
|--------|---------|
| 完整性 | prd.json 每条 acceptance 都有对应实现？有没有 task 无人覆盖？ |
| 集成点 | 跨 task 的数据流转是否一致？字段名/状态值跨模块是否对齐？ |
| PRD 决策落地 | prd-decisions.md 每条 `[x]` 确认的要点，在实现中都有体现吗？ |

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

## ④ 并发构建模式（worktree 隔离 + 主控合并）

> 当 prd.json 有多个独立任务（`blockedBy` 无依赖、`files` 不重叠）时启用。
> 这是 ③ 并行子模式的**强隔离版**：每个 agent 独立 worktree + 独立分支，互不影响，最后主控合并。
> 与 ③ 并行子模式（同目录 spawn、中央提交）二选一——任务各需独立构建环境/真隔离走 ④；小改同栈走 ③。

### 核心流程

**Wave 0 — 主 agent 产出并发契约 `planning/parallel-plan.json`**：
主 agent（opus）读 prd.json，**不写业务代码**，只产出契约：
1. **DAG 分层**：按 `blockedBy` 做拓扑排序，分成 Wave 1..k，同 wave 内任务互不依赖。
2. **文件所有权校验**：同 wave 内所有 task 的 `files` 两两交集为空；有重叠 → 合并到同一 task 或下移一个 wave。
3. **接口契约**：跨 task 的共享接口（类型定义、API schema、状态字段名）写进 parallel-plan.json 的 `contracts` 段——每个 agent 都按此契约编码，不各自发明。
4. **环境脚本**：`env_setup` 段写清每个 worktree 的 install/端口/.env 差异。
5. 依赖环检测：`blockedBy` 成环 → 中止并发，回退 ③ 串行。

**Wave 1..k — 分层限流并发**（`scripts/parallel-dispatch.sh`）：
- 每个 task 一个 `git worktree`（独立工作目录 + 独立分支 `parallel/{task-id}`），共享 .git。
- 每 wave 内 spawn agent（sonnet 写码），**并发上限 4**（`min(DAG 层宽, 4, 端点 QPS)`），超出排队，不是全开。
- 每个 agent 的 prompt **只含**：parallel-plan.json 路径 + 本 task id + "只改你 `files` 清单内的文件、按 contracts 段编码、过 acceptance、commit 到本分支"。
- 每个 agent 内部走 ③ 的 GLM 代码风格纪律 + 测试驱动 Reflexion；Stop 完成门控逐 agent 生效。
- 每 agent 设预算+轮次上限，超限 → `blocked: true`，**不阻塞同 wave 其他 agent**。

**Wave merge — 增量合并**（`scripts/parallel-merge.sh`）：
- **不全部最后并**——按依赖顺序逐个 merge `parallel/{task-id}` → 主分支，每并一个跑集成测试。
- 语义冲突在只牵涉 2 分支时暴露，不是 k 个缠一起时。
- 合并冲突 / 集成测试失败 → 该分支隔离（`parallel-blocked/`），不阻塞已成功的合并。
- Blocked 分支进第二波重试或回主控人工处理。

**Wave final — 主合并 agent**（opus）：
- 修剩余集成 bug → 实跑关键路径（不只编译）→ 跑 ③-R 全量 PRD 对照 → 全过才标记 done + 更新 status.json。
- 合并 agent 是真实工作，用测试通过作停止条件（接 Stop 完成门控）。

### parallel-plan.json 契约格式

```json
{
  "version": "1.0",
  "source": "planning/prd.json",
  "maxConcurrency": 4,
  "waves": [
    { "wave": 1, "tasks": ["N1-01", "N1-02", "N2-01"] },
    { "wave": 2, "tasks": ["N1-03"] }
  ],
  "contracts": {
    "sharedTypes": "src/types/api.ts — 所有 task 按此类型编码，不得各自定义",
    "apiSchema": "POST /api/apply → {userId, reason(>=10字)} → {code, id}",
    "statusFields": "applications.status 枚举: pending|approved|rejected"
  },
  "ownership": { "N1-01": ["src/form.ts"], "N1-02": ["src/list.ts"] },
  "envSetup": "每 worktree: ln -s $MAIN/node_modules .; 端口 3001..300N 写各 .env"
}
```

### 适用边界（路由规则）

| 场景 | 走哪 |
|---|---|
| 任务独立 + 文件不重叠 + 各需独立环境/构建 | ④ 并发构建 |
| 任务独立但同栈小改、不需独立环境 | ③ 并行子模式（同目录中央提交） |
| 任务有依赖 / 改同一文件 / 架构核心耦合 | ③ 串行（先做核心骨架，再放并行翅膀） |
| 机械迁移（per-file，独立） | ④ 并发构建（最理想） |

### 禁止行为
- ❌ 用"分支"而非"worktree"隔离——同一工作目录多分支会互相覆盖文件。必须 `git worktree add`。
- ❌ 全部最后才合并——集成地狱。必须按依赖序增量合并 + 每并一个跑集成测试。
- ❌ 全开并发不限流——GLM 端点 QPS 会限流。必须上限 4。
- ❌ 主 agent 产出完整架构实现而非契约——中等模型在"写完整应用"上易失败；只产接口契约 + 文件所有权，把"写完整应用"降解成 N 个"写过测试的函数"。
- ❌ 跳过 Wave final 的实跑验证直接汇报——编译过≠功能对。
