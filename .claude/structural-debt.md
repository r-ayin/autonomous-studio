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


## SD-006 — personal-assistant web/api.js clearTimeout 放置错误：body-read 阶段无超时保护

- **debt_id**: SD-006
- **audit_id**: audit-2026-07-07-027
- **project**: personal-assistant
- **description**: `web/api.js:55-58` 的 `clearTimeout(tid)` 放在 fetch resolve 之后、`r.json()` 之前。fetch 本身有 8s AbortController 超时（d6f650b 已修），但 body read（`.json()/.text()`）是独立 Promise，不受该 timeout 覆盖。若服务端返回 header 后挂起 body stream，客户端将无限等待。修复需把 AbortController signal 贯穿到 body consumption，或用 Promise.race 包整个 response pipeline。跨 web/api.js + 可能 android/index.html 同名函数，属架构级超时策略统一问题。
- **affected_files**: web/api.js, android/index.html (api() 函数)
- **severity**: medium
- **status**: open
- **source_finding**: M-001

## SD-007 — wanxia-edit copy-generator 硬编码城市地标 + 色彩文案

- **debt_id**: SD-007
- **audit_id**: audit-2026-07-06-023
- **project**: wanxia-edit
- **description**: `copy-generator.js:19-54, 85-120+` 中 SPOTS/COLOR_VARIANTS 大量硬编码中文文案。新增城市需改源码；文案调整需重新部署。适合抽 spots.json + color-variants.json，运行时 load。
- **affected_files**: copy-generator.js
- **severity**: info
- **status**: open
- **source_finding**: L-002

## SD-008 — personal-assistant Android api() 函数完全无超时/AbortController

- **debt_id**: SD-008
- **audit_id**: audit-2026-07-07-027
- **project**: personal-assistant
- **description**: `android/index.html:581-588` 的 `api()` 函数直接 `await fetch(url, opts)` 无任何超时机制。与 web/api.js（已有 8s AbortController）不同步。在网络抖动/服务端挂起时，Android app UI 会永久阻塞在 loading 状态。修复应与 SD-006/SD-007 联动：设计统一的 client-side timeout strategy（web + android 共用），而非逐文件打补丁。
- **affected_files**: android/index.html, web/api.js (参考实现)
- **severity**: medium
- **status**: open
- **source_finding**: M-003

## SD-009 — moni-master Rust engine settle_buy_fill drift-clamp 会计恒等式破坏

- **debt_id**: SD-009
- **audit_id**: audit-2026-07-07-028
- **project**: moni-master
- **description**: `moni-rs/crates/moni-engine/src/account.rs:87-111` — `frozen_cash` drift 负超容差时 clamp 到 0.0，但 `refund` 在 clamp 前计算为 `(prev - cost - new).max(0.0)` = 0.0（drift 场景下）。Available cash 比应有值高 drift 量。恒等式 `available + frozen + market_value = total_assets` 被破坏。Sub-penny 影响但破坏会计一致性。修复需 clamp 后补扣 shortfall 或改用整数分算术。
- **affected_files**: moni-rs/crates/moni-engine/src/account.rs
- **severity**: medium
- **status**: open
- **source_finding**: M-003 (audit-028)

## SD-010 — moni-master CogAlpha LLM 调用无速率限制/并发上限

- **debt_id**: SD-010
- **audit_id**: audit-2026-07-07-028
- **project**: moni-master
- **description**: `moni-rs/crates/moni-cogalpha/src/agents.rs:114-138` — `run_all_agents` 同时 spawn 21 个 tokio task，零 semaphore/rate-limiter/token-budget。每个请求 max_tokens=1500，全跑可发 63+ 并发请求。误配置循环可导致成本失控。修复需加 `tokio::sync::Semaphore`(permit=5) + token counter + leaky-bucket rate limiter。
- **affected_files**: moni-rs/crates/moni-cogalpha/src/agents.rs
- **severity**: medium
- **status**: open
- **source_finding**: M-004 (audit-028, COGALPHA-02)

## SD-011 — moni-master Rust API 全无鉴权（与 Python API SD-014 对称）

- **debt_id**: SD-011
- **audit_id**: audit-2026-07-07-028
- **project**: moni-master
- **description**: `moni-rs/crates/moni-api/src/routes.rs:25-76, main.rs:80-99` — 所有 endpoint（含 POST /order、DELETE /order/:id、POST /quotes、POST /cogalpha/run 等状态变更接口）无任何 auth middleware。Server 经 axum::serve 绑定，无 TLS/bearer/API key，零 .layer(...) auth 调用。若暴露到非 localhost，任意 peer 可下单、覆盖行情、触发昂贵计算。若仅 localhost 使用需文档化 + 默认绑 127.0.0.1；否则加 auth middleware + 读写路由分离。
- **affected_files**: moni-rs/crates/moni-api/src/routes.rs, moni-rs/crates/moni-api/src/main.rs
- **severity**: high
- **status**: open
- **source_finding**: M-008 (audit-028, MONI-API-003)

## SD-012 — moni-master core 六个 env-var 路径函数无任何校验

- **debt_id**: SD-012
- **audit_id**: audit-2026-07-07-028
- **project**: moni-master
- **description**: `moni-rs/crates/moni-core/src/paths.rs:8-43` — `resolve_db_path`, `resolve_qlib_provider_uri`, `resolve_baostock_source_dir`, `resolve_output_dir`, `resolve_factor_library`, `resolve_intraday_features_pt` 直接返回 env var PathBuf，无 canonicalize、无 base-dir check、无 traversal guard。作为 public API re-export。设 `MONI_STOCK_DB=/etc/cron.d/pwned` 即静默写任意路径。MR-M13 fix 仅覆盖 resolve_storage_path。修复需 deprecate（如仅测试用）或加 base_dir 参数 + canonicalize+starts_with 校验。
- **affected_files**: moni-rs/crates/moni-core/src/paths.rs
- **severity**: medium
- **status**: open
- **source_finding**: M-010 (audit-028, MC-002)

## SD-013 — moni-master release_cash 静默 cap 隐藏 double-release bug

- **debt_id**: SD-013
- **audit_id**: audit-2026-07-07-028
- **project**: moni-master
- **description**: `moni-rs/crates/moni-engine/src/account.rs:70-78` — `amount.min(self.state.frozen_cash)` 防 frozen_cash 负但隐藏 double-release bug：第二次调用以 amount=0 成功返回 Ok(())。修复需当 `amount > frozen_cash` 时 log warn 或返回 error/bool 指示 partial release。
- **affected_files**: moni-rs/crates/moni-engine/src/account.rs
- **severity**: low
- **status**: open
- **source_finding**: L-002 (audit-028, M-006)

## SD-014 — moni-master Python API 全无鉴权（与 Rust API SD-011 对称）

- **debt_id**: SD-014
- **audit_id**: audit-2026-07-07-029
- **project**: moni-master
- **description**: `local_simulator/api.py:920-2003` — 50+ endpoint（含状态变更类）全无 auth。默认配置绑 127.0.0.1:8000 限制网络暴露，但任何本地进程可完全控制交易引擎。与 audit-028 MONI-API-003 等价。
- **affected_files**: local_simulator/api.py
- **severity**: medium
- **status**: open
- **source_finding**: MONI-PY-006

## SD-015 — moni-master WebSocket /ws 无鉴权

- **debt_id**: SD-015
- **audit_id**: audit-2026-07-07-029
- **project**: moni-master
- **description**: `local_simulator/api.py:1990-2003` — 接受任意 WebSocket 连接无 auth，推送实时交易事件。属 MONI-API-003 umbrella 下单独标注。
- **affected_files**: local_simulator/api.py
- **severity**: low
- **status**: open
- **source_finding**: MONI-PY-007

## SD-016 — moni-master frontend 全无鉴权层（镜像后端 SD-014）

- **debt_id**: SD-016
- **audit_id**: audit-2026-07-07-030
- **project**: moni-master
- **description**: 前端没有任何登录/session/token 概念。所有 API 调用裸发。与后端 SD-014（Python API 无 auth）对称。一旦部署到非 localhost 环境，任何人打开浏览器就能下单/改配置/读持仓。需后端先落地 auth（SD-014），前端再加 login page + token refresh + WS auth handshake。单独前端修无意义。
- **affected_files**: frontend/src/lib/api.ts, frontend/src/lib/ws.ts, frontend/src/router.tsx, frontend/src/stores/aiStore.ts
- **severity**: high
- **status**: open
- **source_finding**: FE-SD-016 (audit-030)

## SD-017 — moni-master AI trust boundary 需架构级重设计

- **debt_id**: SD-017
- **audit_id**: audit-2026-07-07-030
- **project**: moni-master
- **description**: 当前 AI 子系统把 LLM 当可信 agent，所有"安全"靠 riskLevel 表 + 自然语言 systemPrompt + 用户确认 modal。这三层都可被 prompt injection 绕过。需要架构级改造：tool call whitelist per session、per-tool argument schema validation、sandboxed execution、audit trail、异常模式检测。
- **affected_files**: frontend/src/components/ai/chatLoop.ts, frontend/src/components/ai/toolDispatcher.ts, frontend/src/stores/aiStore.ts
- **severity**: medium
- **status**: open
- **source_finding**: FE-SD-017 (audit-030)

## SD-018 — dataworks session_state.json 多写入方无锁竞争（confirmed_params 设计债务）

- **debt_id**: SD-018
- **audit_id**: audit-2026-07-08-038
- **project**: skills/dataworks-dev-assistant
- **description**: runtime.py 中 save_tool_result / _write_session_state / bootstrap_context / remember / forget 共 5 个写入方共享同一 session_state.json，无任何文件锁或乐观并发控制。dispatching-parallel-agents 场景下并行调用多个 skill 脚本时 last-writer-wins 丢失更新。修复需引入 fcntl.flock 或拆分为 per-key state 文件，超最小单位。
- **affected_files**: core/runtime.py (lines 180-183, 361-365, 461-464, 504, 532)
- **severity**: low
- **status**: open
- **source_finding**: DW-CORE-L-001

## SD-019 — personal-assistant bootstrap Promise.race 5s timeout 不取消 in-flight fetches

- **debt_id**: SD-019
- **audit_id**: audit-2026-07-07-027
- **project**: personal-assistant
- **description**: `web/index.html:187-191` bootstrap 用 `Promise.race([initApp(), timeout(5000)])` 做启动超时兜底，但 timeout 胜出后 initApp 内的 fetch 仍在后台运行，其 `.then()` 回调会继续 mutate MockData/state，导致"已渲染 UI 被迟到数据覆盖"的 race condition。修复需让 timeout 分支触发 AbortController.cancel()，或给 initApp 注入 cancellation token。与 SD-006 同属"超时语义不完整"家族，应一并设计统一 abort propagation 方案。
- **affected_files**: web/index.html, web/api.js, android/index.html
- **severity**: medium
- **status**: open
- **source_finding**: M-002
