# 自治引擎约束与指令 (autonomous-constraints.md)

引擎每轮 step 0 必读本文件。分两节：**DO NOT（排除项）** 与 **DO（审计指令）**。

---

## DO NOT（排除项，严格遵守）

- 不做 `moni` 前端重构（用户 2026-06-XX 定，历史包袱大、不在范围内）
- 不动 `.codebase-index/` 大 JSON（只读不写）
- 不直接 `git commit` 到 main（autonomous-commit-gate.py 会拦；产出全进 opt-worktree）
- 不 push 到 main/master 远端（reference-transaction hook 拦截；只走 opt-worktree.sh merge 走 sanctioned squash）；**但 auto/opt-* 分支自动 push 到 origin**（用户 2026-07-01 改：worktree 分支均经 opt-worktree.sh cmd_commit 内置 push 步骤自动同步远端，无需人工 push）
- 不碰其他项目的 `.env` / 凭证 / 密钥文件
- 不做"日常自我润色"型无意义提交（autonomous-studio 自身仅当真有结构性问题才修）

---

## DO（审计指令 — 用户 2026-06-30 加，2026-07-01 重构为事件驱动 + 深度解绑）

### A. 全量审计与瞭望节奏（事件驱动，不再固定每 4 轮）

**全量审计轮**（deep audit）—— 事件驱动，由 `.claude/audit-cycle-state.json` 决定是否触发：

1. 触发条件：`audit-cycle-state.status == idle` 或 `cycle-complete`（即上一次全量审计派生的 fix 全部 merge/reject 落定）。引擎每轮 step 0 读这个文件决定本轮类型。
2. 全量审计轮**解绑深度限制**：
   - 可读 5-15 个相关文件（不限于"不超过 2 个源文件"的普通轮约束）
   - 可追跨模块数据流（input → sink → 副作用）
   - 可用 sub-agent 跑深度读（**必须 `model: "sonnet"`** 防 402，见 [[subagent-model-preference]]）
   - 不强制产出 opt-worktree commit；产出独立的 deep audit report
3. 全量审计范围：
   - 优先挑"未深度审过"的项目（看 `.claude/audits/` 已有报告，避免重复审同一项目）
   - 跳过纯文档/配置项目（skills、x-tool）
   - 一个项目深度审完一次就标 `audited`，本轮不重审
4. 全量审计**深度不限、但单轮 context 仍受 model 限制**——若项目太大审不完，分段：本轮审 module A，下一轮审计轮（如果其他项目都审过了）续审 module B，audit-cycle-state 记录进度。

**瞭望/研究轮**（light scout）—— 每轮都做（除全量审计轮外）：

1. 跑 `scout-scan.py --workspace <ws>`（轻量文本报告）拿项目健康快照
2. 看跨项目趋势：pending worktree 数、最近 24h case 类型分布、积压项目
3. 检查 `audit-cycle-state.json` 的 pending_count，若 > 0 看派生 fix 是否 blocked（一直没 merge）→ 在 NEXT_SUGGESTION 里提醒用户
4. 不深读源码；产出只在 case 里写"瞭望快照" + 下轮建议
5. 若 scout 推荐的项目 #1 是真·小修复（非结构性、1-3 文件能搞定）→ 走普通修复路径，提交 opt-worktree

**派生 fix 派发**（全量审计挖出问题后）：

1. 全量审计 report 里每一条 finding 写：`{finding_id, file, line, severity, kind: route-fix|direction-shift|structural, remediation_sketch}`
2. `kind=route-fix` 的 → 派生为普通修复 case（最小单位，1-3 文件，走 opt-worktree 复用规则）
3. `kind=direction-shift` 的 → 派生为方向更新 case（开新 worktree，commit message 标 `direction-shift`）
4. `kind=structural` 的（拆不成最小单位，需要重构）→ 写入 `.claude/structural-debt.md`（见 D 节），不直接派 fix
5. 派生 fix case 在 JSON 里加字段 `audit_id`（反向追溯到审计 report）
6. audit-cycle-state 的 `derived_fixes` 数组登记每个派生 fix 的 `{fix_case_id, audit_id, finding_id, status: pending|merged|rejected}`，全部 `merged|rejected` 后 `status=cycle-complete` → 触发下一轮全量审计

### B. 审计日志埋点（修改敏感路径时强制，不变）

当本轮工作单位触及以下**敏感路径**时，必须同步补 audit-log 埋点代码（按 `.claude/decisions/audit-log.schema.json` 格式）：

- 认证/鉴权（auth、login、session、token、permission、role）
- 用户数据读写（PII、邮箱、工号、手机号、用户输入存取）
- 凭证/密钥（secret、key、password、credential 文件或 env 读取）
- 外部调用（HTTP 出站、subprocess、shell exec、文件系统写非 worktree）
- 部署/变更单（deploy、release、CR、流水线触发）
- 删除/批量操作（drop、delete-many、truncate、批量重跑）

埋点要求：
- 落到项目内已有的日志通道（若有 audit logger 复用；若无，新增最小 `audit_log.py`/`audit.ts` 单文件，append-only 写 JSONL，文件路径 `<project>/.audit/audit-YYYY-MM-DD.jsonl`）
- 字段对齐 schema：`id`(audit-YYYYMMDD-HHmmss-rand6)/`timestamp`(ISO8601)/`userId`/`userRole`(engine)/`action`/`resource`/`result`(success|failure|denied)/`ip`（无网络上下文写 `local`）
- 不新建数据库表、不接外部系统；纯本地 JSONL，最小改动
- 若敏感路径的代码本就在审计 logger 调用点附近，确保 result 字段如实反映成功/失败（不要恒 success）

### C. 审计 case 上报

无论 A 或 B 触发，case JSON 增加字段：
- `audit_type`: `code-review` | `security-review` | `audit-log-instrumentation` | `deep-audit` | `none`
- `audit_findings`: 数组，每条 `{file, line, severity, finding, remediation, kind}`；无发现写 `[]`
- `audit_id`: 当 case 是审计轮或派生 fix 时写（格式 `audit-YYYY-MM-DD-NNN`，对应 `.claude/audits/audit-YYYY-MM-DD-NNN.md` 的 id），非审计 case 写 `null`
- `audit_depth`: `shallow` | `deep`（瞭望轮 = shallow，全量审计轮 = deep），让人能区分"0 findings 是没审深还是真没问题"

### D. 结构性债务队列（structural-debt.md）

A 节 `kind=structural` 的 finding（拆不成最小单位的重构/抽象变更）写入 `.claude/structural-debt.md`：
- 每条 `{debt_id, audit_id, project, description, affected_files, severity, status: open|scheduled|resolved}`
- 引擎不主动修 structural-debt（需要更大单位授权）；只累积 + 在 NEXT_SUGGESTION 提醒用户
- 用户确认修某条 → 转派生 fix case（可能 direction-shift），从 structural-debt 移除或标 scheduled

---

关联 [[autonomous-engine-operations]]、[[smart-training-agent-skill-system-state]]。
