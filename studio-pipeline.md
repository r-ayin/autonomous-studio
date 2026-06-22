# Studio 阶段规范索引

> 本文件只是索引。执行具体阶段时，按需 Read 对应 phase 文件，不要全读。
> 行为规则和阶段速查表在项目 CLAUDE.md（由 SKILL.md 激活时注入）。

## 按时期加载

| 你要做什么 | 读哪个文件 |
|---|---|
| 聊需求 / 写 PRD / 生成 prd.json | `phases/phase-build.md` |
| 写代码 / 单任务审查 / 全量 PRD 对照 | `phases/phase-dev.md` |
| E2E 验证 / 评审 / 部署 / 归档 / 回退 | `phases/phase-ship.md` |

## 阶段速查

- ① 需求 → `demand-discovery` → requirements.md
- ② PRD → `pm-spec` → prd.md + prd-decisions.md + prd.json + test-cases.md
- ③ 开发 → `serial-agent-handoff` → 代码 + git push
- ③-V Validator（opus）→ 单任务三维度审查
- ③-R 全量对照（opus）→ 完整性 + 集成点 + 决策落地
- ④ 验证 → `verify` → 截图 + E2E
- ⑤ 评审 → `code-review` + `simplify`
- ⑥ 部署 → `prod-deploy`
- ⑦ 归档 → archive/ + retrospective.md

## 任务类型走哪些阶段

- 新功能：①→②→③→③-V→③-R→④→⑤→⑥→⑦
- 功能优化：②→③→③-V→③-R→④→⑤→⑥→⑦
- Bug 修复：③→③-V→④→⑤→⑥→⑦
- 文案/样式：③→④→⑥→⑦

## 状态推进

做完一个阶段、验证通过后，把 status.json 的 currentStage 推进到下一阶段：
需求→prd→development→prd-review→verification→review→deployment→archiving→archived
