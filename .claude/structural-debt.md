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

## SD-004 — FinanceTracker SQLCipher 端到端接线 + 既有明文库迁移（安全宣传空心支柱 #1）
- **debt_id**: SD-004
- **audit_id**: audit-2026-07-06-019
- **project**: FinanceTracker
- **description**: `DatabaseEncryption.getPassphrase()` 是死代码——全仓 grep 仅自身类 + DI 容器引用；`DatabaseModule.provideDatabase` 建 Room 时无 `openHelper`/`SupportFactory`，实际数据库为明文 SQLite。README/UI 宣称"SQLCipher 数据库加密"完全不成立，所有财务 PII 裸存磁盘。修复非"接上线"那么简单：(1) core/data/DatabaseModule 注入 DatabaseEncryption + `openHelperFactory(SupportFactory(passphrase))`；(2) 当前用户已有明文库在磁盘，直接切加密会让旧库读不出——需迁移：明文 key 打开旧库 → `ATTACH ... KEY '...'` → 逐表导出到加密库 → 替换；(3) 口令源同步改 Keystore（与 H-002/fix-010 联动）；(4) 迁移路径需测试网（与 M-004/I-002 联动）。跨 core/data + core/security + 迁移脚本 + 测试，超最小单位，需用户授权。
- **affected_files**: core/data/.../di/DatabaseModule.kt, core/security/.../crypto/DatabaseEncryption.kt, core/data/.../db/FinanceDatabase.kt, app/build.gradle.kts
- **severity**: high
- **status**: open
- **source_finding**: H-001

## SD-005 — FinanceTracker 启动鉴权门端到端落地（安全宣传空心支柱 #2）
- **debt_id**: SD-005
- **audit_id**: audit-2026-07-06-019
- **project**: FinanceTracker
- **description**: 生物识别层三层全断：(1) `SettingsViewModel.toggleBiometric` 只查 `canAuthenticate()`（能力查询）就写布尔，开启动作本身不验证身份；(2) `BiometricAuthenticator.authenticate()` 全仓除自身定义处外**零调用**；(3) `MainActivity.onCreate` 直接进 `AppNavigation`，无启动鉴权屏，`biometricEnabled` 偏好无任何消费方拦截入口。README/UI"使用指纹或面部识别保护应用"为虚假宣传。修复需：(a) 新建 `feature/auth` 模块——Compose `AuthScreen` + `AuthViewModel`，启动调 `BiometricAuthenticator.authenticate`（M-001/fix-012 落地后的 DEVICE_CREDENTIAL 兜底版）；(b) `AppNavigation` 根路由加 `biometricEnabled` 守卫，开关开则启动必过鉴权才进主界面；(c) `toggleBiometric(true)` 改为先强制过一次 `authenticate()` 验证再落布尔。跨 feature/auth(新) + app/navigation + feature/settings，超最小单位，需用户授权。
- **affected_files**: app/.../MainActivity.kt, app/.../navigation/AppNavigation.kt, feature/settings/.../SettingsViewModel.kt, feature/auth/(新建), feature/settings/src/main/AndroidManifest.xml
- **severity**: high
- **status**: open
- **source_finding**: H-005
