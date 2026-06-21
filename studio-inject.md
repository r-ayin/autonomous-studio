<!-- STUDIO:BEGIN v5.1 -->
## Studio 研发流程（激活中）

planning/status.json 存在时，所有任务遵循以下规则：

### 六条铁律

1. **状态优先原则**：任何任务开始前，先确认当前处于哪个阶段。阶段决定行为边界——开发阶段不做部署操作，PRD 阶段不写代码。
   > 为什么：跳阶段是最常见的越权行为，代价是返工。状态文件（planning/status.json）是唯一可信源。

2. **规划与执行分离原则**：协调者不直接修改项目文件，所有代码编写委托给专用执行 agent（当前为 serial-agent-handoff）。
   > 为什么：混合协调和实现会导致上下文污染，协调者丢失全局视角。分离后协调者保持清醒，执行者保持专注。

3. **自主模式预授权提交**：进入 Studio 自主模式后，用户已预授权整个开发周期的提交行为。改完代码后自动 git add + commit + push，不等用户说。**此规则仅在 Studio 自主模式下生效，覆盖全局"不主动提交"约定。**
   > 为什么：自主模式的核心价值是无人值守推进，等待确认会中断流水线。用户通过激活自主模式已表达授权意图。

4. **阶段推进可追溯原则**：阶段完成后立即更新 status.json，记录推进原因和时间戳。阶段只能前进或回退到合理位置，不能跳跃。
   > 为什么：status.json 是跨会话的持久记忆。新会话进来后，只看 status.json 就能接力，不依赖对话历史。

5. **主线保护原则**：临时问题（用户随口问的、不影响当前功能的）不改 status.json。切换到另一条功能主线需要用户明确确认。新会话进入时，若 status.json 存在且有进行中的任务，先报告当前状态再行动。
   > 为什么：防止并行任务互相覆盖进度。locked=true 表示有专属任务在进行，其他会话只能查看不能修改。

6. **PRD 确认硬关卡**：prd.json 只能在用户明确说"确认/approved/可以了/没问题"后才能生成。"看起来还行""差不多""感觉可以"不算确认。用户仍在讨论或修改中，不能推进。
   > 为什么：PRD 是所有后续阶段的基石。模糊确认导致的 prd.json 一旦驱动开发，返工成本极高。宁可多等一轮确认，不冒险推进。

### 阶段 → Skill 对应
| 阶段 | Skill | 产出 |
|---|---|---|
| ① 需求 | demand-discovery | planning/requirements.md |
| ② PRD | pm-spec | planning/prd.md + prd-decisions.md + prd.json + test-cases.md |
| ③ 开发 | serial-agent-handoff | 可运行代码 + git push |
| ③-V | Validator（opus） | 单任务三维度审查报告 |
| ③-R | 全量 PRD 对照（opus） | 完整性 + 集成点 + 决策落地报告 |
| ④ 验证 | verify | 截图 + E2E 结果 |
| ⑤ 评审 | code-review + simplify | 问题列表 + 修复 |
| ⑥ 部署 | prod-deploy | 线上版本 |
| ⑦ 归档 | — | archive/ + retrospective.md |

### 跳过规则
| 任务类型 | 走哪些阶段 |
|---|---|
| 新功能 | ①→②→③→③-V→③-R→④→⑤→⑥→⑦ |
| 功能优化 | ②→③→③-V→③-R→④→⑤→⑥→⑦ |
| Bug 修复 | ③→③-V→④→⑤→⑥→⑦ |
| 文案/样式 | ③→④→⑥→⑦ |

### 新会话恢复规则
- 新会话进入时，若 status.json 存在：先读 status.json → 判断 currentStage → 报告当前状态
- 若 currentStage=prd：必须先读 `planning/prd-decisions.md`，向用户汇总已确认/待讨论的要点
- 若 currentStage=development：读 `planning/prd.json`，统计 P0 任务进度（done/total）
- 若 locked=true：告知用户有任务进行中，询问是否接力

### status.json 更新时机（强制）
| 完成什么 | currentStage 设为 |
|---|---|
| 需求写完 | prd |
| PRD 写完（用户已确认） | development |
| 所有 P0 tasks done | prd-review（触发 ③-R） |
| ③-R 通过 | verification |
| 验证通过 | review |
| 评审通过 | deployment |
| 部署完成 | archiving |
| 归档完成 | archived |

详细阶段规范（prd.json 格式、Validator 规则、③-R 规则、E2E 方法、归档格式等）：
Read ~/.claude/skills/autonomous-studio/studio-pipeline.md（执行具体阶段时按需加载）
<!-- STUDIO:END -->
