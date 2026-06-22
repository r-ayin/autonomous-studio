# Studio 阶段速查

> 阶段路由（哪个阶段读哪个文件）已在项目 CLAUDE.md 注入块里。本文件仅作速查，通常不用读。
> 详细规范在 `phases/` 下三个文件，按需 Read。

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
