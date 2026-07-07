# Structural Debt Queue

引擎不主动修 structural-debt（需更大单位授权）；只累积 + 在 NEXT_SUGGESTION 提醒用户。
用户确认修某条 → 转派生 fix case（可能 direction-shift），从本文件移除或标 scheduled。

Schema: `{debt_id, audit_id, project, description, affected_files, severity, status}`
Status enum: `open | scheduled | resolved`

---

## SD-001 — pytest 未安装，tests/ 从未被执行（假安全网）

- **debt_id**: SD-001
- **audit_id**: audit-2026-07-01-004
- **project**: autonomous-studio-aone
- **description**: 环境无 pytest (`No module named pytest`)，tests/test_scout_scan.py 从未被执行过。tests/ 是"看起来有测试保护但实际零运行"的假安全网。opt-worktree.sh commit gate 也不跑 pytest。需要决定测试策略：装 pytest + 加 CI/hook gate？还是删 tests/ 承认无测试？
- **affected_files**: tests/test_scout_scan.py, scripts/opt-worktree.sh (gate), .claude/settings.json (hook)
- **severity**: medium
- **status**: open
- **source_finding**: M-002

## SD-002 — tests/ 缺失 5 类关键边界用例（scout-scan 历史修复点无回归守护）

- **debt_id**: SD-002
- **audit_id**: audit-2026-07-01-004
- **project**: autonomous-studio-aone
- **description**: scout-scan.py 注释明确记录多个历史修复点（case-049/327/219/373、marker 自指虚高 7 类剥离），但测试套件无任何回归守护：(1) marker 密度封顶 `min(density*10,5)`；(2) pending_triage 精确抵消 (line 547-549, case-049)；(3) case_only worktree 降级推荐 (line 582-588, case-373)；(4) superseded worktree content-equivalence 检测 (line 416-434, case-327/219)；(5) deferred marker 不计入 triage 推荐 (line 538-541)。补全需设计合成 fixture（tmpdir + git init + 造 worktree），工作量超单轮最小 fix。
- **affected_files**: tests/test_scout_scan.py, scripts/scout-scan.py
- **severity**: low
- **status**: open
- **source_finding**: L-002

## SD-003 — 审计埋点模板代码 6 hook 文件重复实现（DRY 违反）

- **debt_id**: SD-003
- **audit_id**: audit-2026-07-02-001
- **project**: autonomous-studio-aone
- **description**: 6 个 hook 文件各自实现几乎相同的 `_audit_log_*` 审计埋点模板（id/timestamp/userId/resource/result/ip/sensitive/details 构造 + .audit/ makedirs + JSONL append）。差异仅在 action/resource.identifier/details.reason 等业务字段。schema 变更需改 6 处，易漂移。应抽成 `.claude/hooks/_audit_log_helper.py` 暴露 `emit_audit(action, resource_type, resource_id, result, detail="", sensitive_level="medium")` 单函数。属公共接口变更（新增 hooks 模块级共享文件），需 direction-shift worktree。
- **affected_files**: autonomous-commit-gate.py, discovery-gate.py, pipeline-gate.py, auto-commit.py, notify-phone.py, codegraph-sync.py (及 incremental-save.py 间接)
- **severity**: low
- **status**: open
- **source_finding**: I-001

## SD-PD-001 — findBatchEvent 客户端 O(N) 过滤（prod-deploy）

- **debt_id**: SD-PD-001
- **audit_id**: audit-2026-07-03-013
- **project**: autonomous-studio
- **description**: event-client.js findBatchEvent 全量拉取所有 deploy_batch 事件再 client-side filter by batch_index。服务端 query API 不支持 batch_index 参数。10 批次部署尚可，100+ 批次会成为网络/延迟瓶颈。需推动 aone-agent-server 支持 batch_index 查询过滤，或增加客户端 LRU 缓存。
- **affected_files**: skills/prod-deploy/scripts/lib/event-client.js
- **severity**: low
- **status**: open
- **source_finding**: PD-L004

## SD-PD-002 — SKILL.md 文档与实际行为不一致（prod-deploy）

- **debt_id**: SD-PD-002
- **audit_id**: audit-2026-07-03-013
- **project**: autonomous-studio
- **description**: SKILL.md 标 SUNFIRE_ACCESS_ID/SECRET_KEY 为"否"（可选），但观察期 gate 实际依赖它；phases/07-batch-deploy.md L44 说"读取第 1 批事件中的 resolved_strategy.observe_minutes"，实际代码读 deploy_plan 事件。文档与实现漂移，operator 易被误导。需建立文档同步机制（如 SKILL.md 变更时自动 diff phases/）。
- **affected_files**: skills/prod-deploy/SKILL.md, skills/prod-deploy/phases/07-batch-deploy.md
- **severity**: info
- **status**: open
- **source_finding**: PD-I001, PD-I003

## SD-004 — engine-skills-extracted SKILL.md model field 未校准任务复杂度

- **debt_id**: SD-004
- **audit_id**: audit-2026-07-03-006
- **project**: engine-skills-extracted
- **description**: 18 个 skill 的 SKILL.md model field 全部为 sonnet/haiku，无 opus；部分纯 bash 编排 skill（自主循环、隔离优化）用 sonnet 浪费，而复杂意图分类 skill（决策观察，688 行）可能需 opus。Model 分配看似随意而非基于 LLM 推理需求校准。低优先级（model field 仅影响部署建议）。
- **affected_files**: engine-skills-extracted/*/SKILL.md (18 files)
- **severity**: low
- **status**: open
- **source_finding**: ESE-L02

## SD-MM-002 — moni-master RuleEngine::evaluate() P1 占位符

- **debt_id**: SD-MM-002
- **audit_id**: audit-2026-07-04-002
- **project**: moni-master
- **description**: RuleEngine::evaluate() 是 P1 占位符，始终返回空 Vec。通过 add() 添加的 STOP_LOSS/TAKE_PROFIT 规则被存储但从不评估，可能误导用户认为规则已生效。需要在 API 响应或规则状态中标注评估未实现，并在添加规则时 log warning。完整实现需要跨 engine/market-data/risk 模块集成，超出单轮最小 fix 范围。
- **affected_files**: moni-rs/crates/moni-engine/src/rules.rs (L53-57), moni-rs/crates/moni-api/src/routes.rs (rule endpoints)
- **severity**: low
- **status**: open
- **source_finding**: MM-I001

## SD-ESE-003 — engine-skills-extracted manifest checksum verification broken

- **debt_id**: SD-ESE-003
- **audit_id**: audit-2026-07-04-012
- **project**: engine-skills-extracted
- **description**: `_manifest.json` 中 `自主循环/autonomous-loop.sh` 条目声称 `"live_md5_match": true`，但实际文件已 diverge 30+ 行。根因：manifest 生成于 extraction_timestamp，而 fix 引用 audit 完成晚 13 分钟——fix applied post-manifest-generation without regenerating checksums。需要建立"post-fix manifest regeneration"流程或 CI gate 防止再次 drift。
- **affected_files**: engine-skills-extracted/_manifest.json, engine-skills-extracted/自主循环/autonomous-loop.sh
- **severity**: medium
- **status**: open
- **source_finding**: ESE-RT-M02
## SD-PA-001 — storage.py hash()-based ID generation non-deterministic + collision-prone

- **debt_id**: SD-PA-001
- **audit_id**: audit-2026-07-07-020
- **project**: personal-assistant
- **description**: Memory/event/reminder/intervention ID generation uses `abs(hash())%10**12` which is non-deterministic across Python runs (PYTHONHASHSEED randomization) and has collision risk. Same pattern in add_event (L219), add_reminder (L254), add_intervention (L184). Fix requires replacing all ID generation with uuid4() or hashlib.sha256(), plus migration logic for existing records. Cross-cutting change touches storage.py core + any code that depends on deterministic IDs.
- **affected_files**: personal_assistant/storage.py (L88, L184, L219, L254)
- **severity**: medium
- **status**: open
- **source_finding**: M-007

## SD-PA-002 — storage.py connect() re-executes full SCHEMA DDL on every call

- **debt_id**: SD-PA-002
- **audit_id**: audit-2026-07-07-020
- **project**: personal-assistant
- **description**: Every `connect()` call re-runs 11 CREATE TABLE IF NOT EXISTS + CREATE INDEX statements via executescript(). While IF NOT EXISTS prevents errors, this adds unnecessary overhead to every DB operation. Fix requires connection pooling or schema-version tracking (e.g., PRAGMA user_version) with conditional DDL execution. Structural because it changes the DB initialization architecture.
- **affected_files**: personal_assistant/storage.py (L52)
- **severity**: low
- **status**: open
- **source_finding**: L-003

## SD-PA-003 — config.py module-level global CONFIG loaded at import time

- **debt_id**: SD-PA-003
- **audit_id**: audit-2026-07-07-020
- **project**: personal-assistant
- **description**: CONFIG is a module-level global loaded at import time (`CONFIG = load_config()`). Runtime overrides via set_override() partially address this, but .env changes after startup are never picked up. Full fix requires lazy config loading or a config reload mechanism with cache invalidation. Low urgency — acceptable for single-process app but limits testability and multi-instance deployment.
- **affected_files**: personal_assistant/config.py (L74)
- **severity**: low
- **status**: open
- **source_finding**: M-008
