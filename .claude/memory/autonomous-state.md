---
<!-- ENGINE_VERSION: 6.0 -->
<!-- STUDIO_BRIDGE: enabled -->
<!-- ISOLATION_MODE: agent_subprocess -->
<!-- SCOUT_MODE: active -->
<!-- CHECKPOINT_PROTECTION: enabled -->
<!-- AUTONOMOUS_LOOP: continuous (replaces cron dual-track) -->
<!-- CODEGRAPH_FUSION: enabled (v1.0 · 8触点8规则 · codegraph-sync.py) -->
name: autonomous-state
description: 自主决策引擎运行状态 v6.0 — 持续自治管线 + 蒸馏闭环 + opt-worktree + 确定性扫描索引
metadata:
  type: project
---

# 引擎状态 v3.0

- **最后活跃: 2026-07-01T19:47Z（case-400=今日第36例,400%4=0 审计轮·DO A 强制。承接 case-399 NEXT:case-400 审计轮。scout-scan #1=AS score=0.0 无明确单位,审计轮不 skip 走 DO A。手动 security-review .claude/hooks/decision-observer.py(原 688L,第 6 个已审 hook,最大未审)。发现 1 medium+1 low:①medium L451 prompt_preview(300c)/L500 message_preview(500c)原样落盘 .claude/decision-log.jsonl,用户调试粘贴 sk-/Bearer/password=/JWT/AKIA 即凭证明文 at-rest,属 DO B 敏感路径『用户输入存取』;②low L399 get_session_file session_id 未清洗直接拼路径(可信来源但缺防御性 sanitize)。修复 1file +92/-4:新增 _redact_secrets(7 类秘钥正则→[REDACTED])+_audit_log_input_write(DO B 埋点,仅擦到秘钥时写 .audit/audit-YYYY-MM-DD.jsonl action=file_write result 如实 success/failure 不恒 success,对齐 auto-commit.py 模式)+prompt_preview/message_preview 过脱敏+session_id 防御性清洗。验证:py_compile OK+importlib 单测 sk-/password=/Bearer 各 1 redaction normal 0+evil session_id→______etc_evil.json 无 traversal+e2e UserPromptSubmit 喂 sk- prompt→decision-log preview=[REDACTED] & .audit/ 写 1 条 file_write success(id=audit-20260630-194646-zrxgs2 符合 schema)。改动落 opt-worktree engine:security @3a5fa80(auto/optimization) pending=1 待下轮 sanctioned-merge(同 case-396→397)。case-400 outcome=succeeded audit_type=security-review audit_findings=[medium L451 凭证 at-rest/low L399 path traversal]。pending=1。下轮 case-401=401%4=1≠0 非审计轮 sanctioned-merge opt-worktree @3a5fa80）**
- **活跃项目**: autonomous-studio-aone 维护——case-400 审计轮 security-review decision-observer.py 1medium+1low 修复落 opt-worktree @3a5fa80 pending=1。case-399/398 非审计轮 skip。case-397 sanctioned-merge engine:security @e0b9b8b→main 2fca11f。case-396 审计轮 security-review auto-commit.py git add -A medium+修复+DO B。case-393 sanctioned-merge opt-security→main 2353e2e(pipeline-gate 去 shell=True)。case-392 审 pipeline-gate 1low+修复。case-389 sanctioned-merge notify-phone→main 47128f1。case-388 security-review notify-phone 1low+修复。case-385 sanctioned-merge codegraph-sync L291→main fedf2a0。case-384 security-review codegraph-sync。已审 hook 6 个,剩 discovery-gate.py(387L)。
- **当前阶段**: case-400 审计轮完成(pending=1 opt-worktree @3a5fa80,main HEAD=4a146e0,worktree list=main+optimization);下轮 case-401=401%4=1≠0 非审计轮 sanctioned-merge
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01
- **LAST_WORKTREE**: auto/optimization @ 3a5fa80（case-400 审计轮 security-review decision-observer.py:1medium 凭证 at-rest+1low path traversal 修复+_redact_secrets 7类正则+_audit_log_input_write DO B 埋点+session_id 清洗,1file +92/-4,pending=1 待 sanctioned-merge;main HEAD=4a146e0 clean）
- **LAST_OUTCOME**: in_progress
- **NEXT_SUGGESTION**: [1]【case-401=401%4=1≠0 非审计轮】pending=1 opt-worktree engine:security @3a5fa80,预审 diff 仅 .claude/hooks/decision-observer.py 1file +92/-4 与归档环无源码重叠→clean。人工审 diff 确认三点:①_redact_secrets 7类秘钥正则(sk-/sk-ant-/gh[pousr]_/AKIA/Bearer/JWT/password|token|api_key=value)→[REDACTED];②_audit_log_input_write DO B 埋点(.audit/audit-YYYY-MM-DD.jsonl action=file_write result 如实 success/failure);③get_session_id 防御性清洗。opt-worktree.sh . merge optimization→squash 落 main+worktree 清理+auto/optimization 强删(同 case-397 模式)。回归:py_compile+grep _redact_secrets/_audit_log_input_write 命中。[2]【case-404=404%4=0 下次审计轮】DO A 审剩余最后未审 hook discovery-gate.py(387L,外部输入/路径校验面)——审完即 .claude/hooks/ 全量审计闭环。
- **自主循环**: 🟢 活跃
  - L1 Inline: 每次回复末尾内联检查 (+ git status)
  - L2 Heartbeat: CronCreate 每7分钟（执行轨——推进 Studio 阶段或主动扫描）
  - L3 Deep: CronCreate 每60分钟（研判轨——路线健康度 + 修正协议，Studio 项目强制不降频）
- **v2.1 升级**: 2026-06-15T23:20Z — 冷启动自动判定 + 瞭望模式 + 主动扫描
- **v2.2 升级**: 2026-06-16T03:15Z — 检查点保护执行 + L3 降频自适应 + 三轨策略
- **🚀 v3.0 升级**: 2026-06-17T15:50Z — autonomous_studio 全量融合
  - 🏗️ Studio 7 阶段研发流水线深度融合（执行轨 + 研判轨双轨架构）
  - 🔍 L3 路线健康度诊断（§②E: 4 维度评分——产出物质量/跨阶段一致性/外部环境/累计偏差）
  - 🛤️ 路线修正协议（§1.6: RC-1→RC-4，健康度 <5 自动阻断 + 超时降级机制）
  - 📝 DRAFT 确认机制（PRD/技术方案草稿 → 用户确认 → 自动推进阶段）
  - 🔗 9 个修正冲突全部解决（Studio vs Engine 边界清晰）
  - 📊 统一状态文件 planning/status.json（跨会话记忆 + 阶段追踪）
  - 🧩 18 个 Studio 流水线 Skills 就位（demand-discovery / pm-spec / plan-feature / serial-agent-handoff / prod-deploy / e2e-generator ...）
  - 🛡️ 分层自动化: 可逆全自动 / 不可逆需确认 / 方向决策永远 SUGGEST
  - 🔔 L3 降频豁免: Studio locked=true → consecutive_no_delta 强制归零
  - 👥 多 Worker 豁免: serial-agent-handoff 整个会话计为 1 次自主行动
  - 📡 路线修正手机通知（高优先级 → notify-phone.py）
  - 🗂️ 新增: confidence-calibrator.js / model-profiles.json / notification-policy.json / role-permissions.json
  - 📋 新增: audit-log.schema.json / team-decision-log.schema.json / planning/status.schema.json
  - 🧠 决策模式库扩展: +5 个 Studio 融合模式（studio_prd_confirmation / studio_route_correction / studio_multi_worker_execution / studio_verification_mode_select / studio_l3_strategic_review）
  - 🔒 安全硬限制不变: 不自动 push / 不可逆强制 ACT_NOTIFY / 路线修正永远 SUGGEST
- **🧠 v3.0 + CodeGraph 融合层 v1.0 升级**: 2026-06-18T01:30Z
  - 📊 3 个注册表: capability-registry / engine-touchpoints / integration-rules
  - 🔧 2 个脚本: codegraph-sync.py（自动更新感知）/ route-health-scorer.py（客观评分）
  - 🎯 8 引擎触点: 冲击面门禁 / E1质量 / E2一致性 / 跨项目依赖 / 冷启动预分析 / 测试定位 / 模型选择 / 索引健康
  - 📐 8 集成规则: 引擎阶段驱动 + 能力标签匹配 + 自动降级fallback
  - 🔌 4 Agent 接入: Claude Code / Cursor / Codex CLI / opencode
  - 📂 4 项目索引: pachong-master(908节点) / wanxia(500) / moni(6232) / xia(499)
  - 🛡️ 完全可选: 无CodeGraph时引擎降级运行，不阻断

---

## 🎯 历史目标

<!-- GOAL: achieved -->
<!-- GOAL_ID: G-2026-06-15-001 -->
<!-- GOAL_STATUS: goal_achieved -->

| 字段 | 内容 |
|------|------|
| **目标** | 搭建自主决策引擎，验证三阶段（Hook/Skill/CronCreate）正常工作 |
| **完成条件** | ①Hook ②Skill ③CronCreate ④用户确认 |
| **进度** | ①✅ ②✅ ③✅ ④✅ 已完成 (2026-06-15T06:40Z) |

## 🎯 当前行为模式（v3.0 Studio 融合·瞭望哨兵模式）

<!-- GOAL: scout -->
<!-- GOAL_ID: G-2026-06-15-002 -->
<!-- GOAL_STATUS: active -->
<!-- ACTIVE_GOAL: ralph-wiggum-autonomous-loop (每轮一个小工作单位，scout-scan 排序选任务) -->
<!-- LAST_UPDATED: 2026-07-01 -->
<!-- LAST_WORKTREE: auto/optimization @ 3a5fa80（case-400 审计轮 security-review decision-observer.py:1medium 凭证 at-rest(prompt_preview/message_preview 原样落盘)+1low path traversal(session_id 未清洗),修复 _redact_secrets 7类正则→[REDACTED]+_audit_log_input_write DO B 埋点(.audit/audit-YYYY-MM-DD.jsonl action=file_write result 如实 success/failure)+session_id 防御性清洗,1file +92/-4,pending=1 待 sanctioned-merge;main HEAD=4a146e0 clean） -->
<!-- LAST_OUTCOME: in_progress -->
<!-- NEXT_SUGGESTION: [1]【case-401=401%4=1≠0 非审计轮】pending=1 opt-worktree engine:security @3a5fa80,预审 diff 仅 decision-observer.py 1file +92/-4 clean,人工审三点(_redact_secrets 7类/_audit_log_input_write DO B/session_id 清洗)后 opt-worktree.sh . merge optimization→squash 落 main+清理+auto/optimization 强删(同 case-397)。[2]【case-404 下次审计轮】DO A 审最后未审 hook discovery-gate.py(387L)→.claude/hooks/ 全量审计闭环。勿做日常自我润色(DO NOT 禁)。 -->

| 字段 | 内容 |
|------|------|
| **模式** | 瞭望哨兵 + Studio 阶段感知 + 检查点保护执行 |
| **行为规则** | ① L2 心跳: 先读 planning/status.json（如果 locked=true → Studio 驱动模式，按阶段推进）② 无 Studio 项目 → 执行主动扫描协议 ③ L3 研判: 独立评估路线健康度（0-10），<5 触发修正协议 ④ 可逆操作（文件修改/测试/git commit）→ 检查点保护下可达 ACT_SILENT ⑤ 不可逆操作（push/deploy/destroy）→ 强制 ACT_NOTIFY + 用户确认 ⑥ 执行前自动创建 git 检查点，失败自动回滚 |
| **扫描范围** | git status、planning/status.json 阶段状态、各项目 PROGRESS.md、GATES.md 门禁、依赖过期、路线健康度 |
| **双轨架构** | 执行轨 L2（7min）推进流程 / 研判轨 L3（60min）评估路线——独立运行、互不干扰 |
| **停止条件** | 用户设定新目标 → 引擎从瞭望模式切回目标驱动模式；说「studio auto off」暂停自动驾驶 |

> 引擎在 DECIDE 阶段检查：**无活跃目标？** → 执行主动扫描协议 + 机会排序 → 信心≥60 的可逆操作在检查点保护下直接执行。
> 存在 planning/status.json 且 locked=true → Studio 驱动模式 → 按 7 阶段自动推进（草稿需确认）。
> 用户可随时说「设定目标：XXX」退出瞭望模式。
