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

- **最后活跃: 2026-07-01T03:27Z（case-396=今日第32例,396%4=0=0 DO A 强制审计轮。承接 case-395 NEXT 审 .claude/hooks/ 未审 hook。scout-scan #1=AS score=0.0 无紧迫单位,审计轮挑有源码。已审 hook={autonomous-commit-gate(376/377/378)·codegraph-sync(384)·notify-phone(388)·pipeline-gate(392)},从未审集挑 auto-commit.py(377L,subprocess git commit+push 敏感面)。security-review 发现 1 medium:L313 git add -A 绕过 EXCLUDED_PREFIXES 过滤——过滤仅作用于 commit 消息,实际暂存 git add -A 把 .claude/ 内部文件+非 gitignore 的 .env/凭证一并暂存并 push origin,违背 L6『跳过 .claude/ 等内部文件』。起 opt-worktree engine:security @e0b9b8b 修 1file +56/-2:①git add -A→git add -- <filtered changes+PROGRESS.md> 显式列路径暂存(fail-safe 路径异常则 return False 不退回 -A 泄漏)②补 DO B _audit_log_commit 埋点(action=file_write/resource=repository/result=success|failure 落 <WORKSPACE_ROOT>/.audit JSONL,写引擎仓免子仓反馈环)。残留 1 low:.env* 未纳入 EXCLUDED_PREFIXES 依赖 .gitignore(加 .env 前缀误伤 .env.example 且不解 .env.local,需 pathspec 方案,留 triage)。回归:py_compile OK+staging mock 验证 .claude 不再暂存/src 正常暂存+audit helper schema 合规。LIVE 副本 ~/.claude/hooks/auto-commit.py 旧版未在 settings 注册→休眠无需同步。case-396 outcome=succeeded audit_type=security-review audit_findings=[medium 已修待 sanctioned-merge + low 留 triage]。pending=1(opt-worktree @e0b9b8b 待 sanctioned-merge)。下轮 case-397=397%4=3≠0 非审计轮承接 sanctioned-merge;case-400=400%4=0 下次审计轮审剩余未审 discovery-gate.py/decision-observer.py）**
- **活跃项目**: autonomous-studio-aone 维护——case-396 审计轮 security-review auto-commit.py 发现 git add -A 绕过 EXCLUDED_PREFIXES(medium)+修复+DO B audit 埋点,opt-worktree @e0b9b8b pending sanctioned-merge。case-395 非审计轮 skip。case-393 sanctioned-merge opt-security-1782846352→main 2353e2e(pipeline-gate.py 去 shell=True)。case-392 审 pipeline-gate.py 1 low+修复。case-389 sanctioned-merge notify-phone.py 修复→main 47128f1。case-388 security-review notify-phone.py 1 low+修复。case-385 sanctioned-merge codegraph-sync.py L291 timestamp 修复→main fedf2a0。case-384 security-review codegraph-sync.py。已审 hook 4 个,剩 discovery-gate.py/decision-observer.py(auto-commit.py 本轮已审)。
- **当前阶段**: case-396 审计+修复完成(pending=1 opt-worktree @e0b9b8b 待 sanctioned-merge,main HEAD=1807d11,worktree list=main+optimization);下轮 case-397=397%4=3≠0 非审计轮承接 sanctioned-merge
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01
- **LAST_WORKTREE**: optimization @ e0b9b8b（方向 engine:security,1file .claude/hooks/auto-commit.py +56/-2,闭合 git add -A 绕过 EXCLUDED_PREFIXES + 补 DO B _audit_log_commit 埋点,pending sanctioned-merge;git worktree list=main @1807d11 + optimization,main 干净）
- **LAST_OUTCOME**: in_progress
- **NEXT_SUGGESTION**: [1]【case-397=397%4=3≠0 非审计轮】承接 case-396 审计 pending→sanctioned-merge opt-worktree engine:security @e0b9b8b(auto-commit.py git add -A→显式路径暂存 + audit 埋点)。预审 diff 仅 .claude/hooks/auto-commit.py 1file 与归档环无源码重叠→clean。merge 后回归:py_compile + grep git add -A 无实际调用 + grep _audit_log_commit 命中 + worktree list 仅 main + 无 auto/。[2]【case-400=400%4=0 下次审计轮】审剩余未审 hook:discovery-gate.py(387L,外部输入/路径校验面)/decision-observer.py(688L,文件写/JSON 解析,最大未审 hook)。勿做日常自我润色(DO NOT 禁)。
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
<!-- LAST_WORKTREE: optimization @ e0b9b8b（case-396 审计轮 security-review auto-commit.py:闭合 git add -A 绕过 EXCLUDED_PREFIXES + DO B _audit_log_commit 埋点,1file +56/-2,pending sanctioned-merge;git worktree list=main @1807d11 + optimization,case-396 outcome=succeeded audit_type=security-review audit_findings=[medium 已修待 sanctioned-merge + low 留 triage]） -->
<!-- LAST_OUTCOME: in_progress -->
<!-- NEXT_SUGGESTION: [1]【case-397=397%4=3≠0 非审计轮】承接 case-396 审计 pending→sanctioned-merge opt-worktree engine:security @e0b9b8b(auto-commit.py git add -A→显式路径暂存 + audit 埋点);预审 diff 仅 1file 与归档环无重叠→clean;merge 后回归 py_compile+grep git add -A 无实际调用+grep _audit_log_commit 命中+worktree list 仅 main+无 auto/。[2]【case-400=400%4=0 下次审计轮】审剩余未审 hook:discovery-gate.py(387L)/decision-observer.py(688L)。勿做日常自我润色(DO NOT 禁)。 -->

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
