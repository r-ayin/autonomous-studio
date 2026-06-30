# 自治引擎约束与指令 (autonomous-constraints.md)

引擎每轮 step 0 必读本文件。分两节：**DO NOT（排除项）** 与 **DO（审计指令）**。

---

## DO NOT（排除项，严格遵守）

- 不做 `moni` 前端重构（用户 2026-06-XX 定，历史包袱大、不在范围内）
- 不动 `.codebase-index/` 大 JSON（只读不写）
- 不直接 `git commit` 到 main（autonomous-commit-gate.py 会拦；产出全进 opt-worktree）
- 不 push 到远端、不改 git config、不 force push
- 不碰其他项目的 `.env` / 凭证 / 密钥文件
- 不做"日常自我润色"型无意义提交（autonomous-studio 自身仅当真有结构性问题才修）

---

## DO（审计指令 — 用户 2026-06-30 加）

### A. 代码审计任务（约每 4 轮一次）

为避免引擎只做"修 TODO/补桩"类小修，每 **4 轮** 至少做一次**代码审计**工作单位，替代普通修复轮次：

1. 仍跑 `scout-scan.py` 拿项目排序，但从 #1 起选一个**有源代码**的项目（跳过纯文档/配置项目）
2. 用 `code-review` skill 或 `security-review` skill 审计该项目的当前 diff 或最近一次 opt-worktree 改动：
   - 优先关注：注入风险（SQL/命令/XSS）、权限校验缺失、PII/凭证泄漏、错误处理空洞、并发/资源泄漏
   - 也可审 main HEAD 最近 1-3 个 commit（`git log -3 --stat`）
3. 产出：
   - 若发现真问题 → 起一个 opt-worktree 修复（同小工作单位纪律，1-3 文件）
   - 若无真问题 → 写一条 case 存档（outcome=succeeded，outcome_evidence 引用审计的具体文件/行号 + skill 输出摘要，不接受散文）
4. case 的 `work_unit` 字段写 `code-audit:<project>`，`direction` 写 `audit`

### B. 审计日志埋点（修改敏感路径时强制）

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
- `audit_type`: `code-review` | `security-review` | `audit-log-instrumentation` | `none`
- `audit_findings`: 数组，每条 `{file, line, severity, finding, remediation}`；无发现写 `[]`

---

关联 [[autonomous-engine-operations]]、[[smart-training-agent-skill-system-state]]。
