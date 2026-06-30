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

- **最后活跃: 2026-07-01T17:43Z（普通轮 case-377=377%4=1≠0 非审计。承接 case-376 NEXT_SUGGESTION[1] 闭合部署态隐患 [f4 medium]:LIVE gate 旧版未同步+state.md 豁免缺口。1 file(.claude/hooks/autonomous-commit-gate.py)+46/-4 经 opt-worktree→sanctioned-merge→main @ac78f92→cp 同步 LIVE。改动:(1) +STATE_FILE_RE 纳入 .claude/memory/autonomous-state.md;(2) is_case_metadata_only 用 CASE_FILE_RE or STATE_FILE_RE(broaden 豁免集,免 gate 激活后拦 state.md 归档环 commit→断裂);(3) +_audit_log_exempt 埋点(DO B 鉴权/permission 敏感路径变更,对称 _audit_log_block——拦 denied/放 success 两端可观测,action=compliance_check 落 .audit/audit-YYYY-MM-DD.jsonl fail-safe);(4) 豁免分支调 _audit_log_exempt(seg,staged)。回归:importlib 14 例(eval/sh -c/嵌套链/checkout/non-git)ALL PASS+is_case_metadata_only 6 例+端到端 born-main repo(marker 存在)exempt→allow+success audit / block→exit2+denied audit / case.json 路径不破+py_compile OK。LIVE diff main==LIVE IDENTICAL+LIVE 14 例 PASS+LIVE state.md exempt PASS。marker .autonomous_active 仍从不创建→gate 休眠,归档环自由(且激活后亦豁免)。audit deploy 条目 audit-20260630-174216-x1i8kv action=deploy identifier=live-commit-gate newValue=ac78f92 result=success 落 .audit/audit-2026-06-30.jsonl。case-372/373/375/376/377 全部硬化现已上线 LIVE。case-377 outcome=succeeded audit_type=audit-log-instrumentation audit_findings=2(state.md 豁免缺口 medium 已修+豁免路径静默 low 已修)。pending=0）**
- **活跃项目**: autonomous-studio-aone 维护——case-377 闭合 case-376 部署态隐患:LIVE gate 同步(main @ac78f92→/home/admin/.claude/hooks/)+state.md 豁免 broaden+_audit_log_exempt 埋点。case-372/373/375/376/377 全部硬化上线 LIVE。
- **当前阶段**: 修复+合并+LIVE 同步完成;pending=0（无待合并 worktree）;下轮 case-378=378%4=2≠0 非审计普通轮——LIVE gate 已同步,可挑 case-376 NEXT_SUGGESTION[3] gate 残留低危项(需真 shell parser,评估是否值得)或预备 case-380 审计轮换审非 gate 目标
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01
- **LAST_WORKTREE**: optimization @e4fdfd0（已 sanctioned-merge squash 入 main @ac78f92,worktree 清理,auto/optimization 残留分支删除;方向 engine:gate-state-exempt;1 file +46/-4;case-377 outcome=succeeded audit_type=audit-log-instrumentation audit_findings=2;LIVE gate 已 cp 同步 diff IDENTICAL;main HEAD=ac78f92 干净 pending=0）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【普通轮·case-378】378%4=2≠0 非审计。pending=0。LIVE gate 已同步,case-372/373/375/376/377 全部硬化上线。可挑:(a) scout-scan #1 AS score=0.0 无紧迫单位——可跳过或做文档润色(纪律:不做无意义自我润色);(b) 闭合 case-376 NEXT_SUGGESTION[3] gate 残留低危项之一(3 级嵌套混合引号 `A && eval \"B && sh -c 'git push'\"` _SHELL_OPS_RE 非 quote-aware / $(git...) 反引号 / source/. 脚本内容 / --norc 长 -c 形态)——需真 shell parser,评估是否值得引入;(c) 预备 case-380 审计轮换审非 gate 目标(scout-scan.py subprocess 面 / opt-worktree.sh 路径 logic / codegraph-sync.py 外部文件读写)。[2]【下次审计轮 case-380=380%4=0=DO A 强制审计轮】须换审非 gate 目标(已连续 case-372/376 两轮审 gate+case-377 又改 gate)。候选:(a) scripts/scout-scan.py code-review(.codebase-index 大 JSON 只读面/subprocess/标记正则虚高历史);(b) scripts/opt-worktree.sh detect_main_branch/ensure_main_wt/cp-guard/_assert_no_collateral_revert 路径 logic;(c) codegraph-sync.py/route-health-scorer.py 外部文件读写。优先挑有源代码项目。[3]【gate 残留(低危,刻意构造)】3 级嵌套混合引号仍漏(_SHELL_OPS_RE 非 quote-aware,需真 shell parser);$(git...)/反引号;source/. 脚本内容;--norc 长 -c 形态。
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
<!-- LAST_WORKTREE: optimization @e4fdfd0（已 sanctioned-merge squash 入 main @ac78f92,worktree 清理,auto/optimization 残留分支删除;方向 engine:gate-state-exempt;1 file +46/-4;case-377 outcome=succeeded audit_type=audit-log-instrumentation audit_findings=2;LIVE gate 已 cp 同步 diff IDENTICAL;main HEAD=ac78f92 干净 pending=0） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【普通轮·case-378】378%4=2≠0 非审计。pending=0。LIVE gate 已同步,case-372/373/375/376/377 全部硬化上线。可挑:(a) scout-scan #1 AS score=0.0 无紧迫单位——可跳过或做文档润色(纪律:不做无意义自我润色);(b) 闭合 case-376 NEXT_SUGGESTION[3] gate 残留低危项之一(3 级嵌套混合引号 `A && eval \"B && sh -c 'git push'\"` _SHELL_OPS_RE 非 quote-aware / $(git...) 反引号 / source/. 脚本内容 / --norc 长 -c 形态)——需真 shell parser,评估是否值得引入;(c) 预备 case-380 审计轮换审非 gate 目标(scout-scan.py subprocess 面 / opt-worktree.sh 路径 logic / codegraph-sync.py 外部文件读写)。[2]【下次审计轮 case-380=380%4=0=DO A 强制审计轮】须换审非 gate 目标(已连续 case-372/376 两轮审 gate+case-377 又改 gate)。候选:(a) scripts/scout-scan.py code-review(.codebase-index 大 JSON 只读面/subprocess/标记正则虚高历史);(b) scripts/opt-worktree.sh detect_main_branch/ensure_main_wt/cp-guard/_assert_no_collateral_revert 路径 logic;(c) codegraph-sync.py/route-health-scorer.py 外部文件读写。优先挑有源代码项目。[3]【gate 残留(低危,刻意构造)】3 级嵌套混合引号仍漏(_SHELL_OPS_RE 非 quote-aware,需真 shell parser);$(git...)/反引号;source/. 脚本内容;--norc 长 -c 形态。 -->

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
