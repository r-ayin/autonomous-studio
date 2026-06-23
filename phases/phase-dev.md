# 阶段三：开发 + Validator + 全量对照（开发期）

> 执行代码开发、单任务审查、全量 PRD 对照时加载本文件。

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
