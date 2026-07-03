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
