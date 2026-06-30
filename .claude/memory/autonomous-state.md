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

- **最后活跃: 2026-06-30T11:18Z（常规工作单位轮次：今日 case 138%4=2 未命中审计边界 140；非审计轮次。step0 .claude/autonomous-constraints.md 此前三轮确认缺失——本轮正是合并落地该文件！step1 scout-scan #1=AS(score=0.0 TODO=0)推荐语=「review 1 个待合并 worktree」即 #1 工作单位=合并 pending worktree。pending 队列余 1 项 auto/optimization(a271bf7, engine:audit-directives)。核真实 merge diff(merge-base 1b498ce..worktree)=仅 2 文件：autonomous-constraints.md(新建+58, 正 protocol step0 所缺)+autonomous-loop.sh(+6/-3, PROMPT step0/5 引用 DO 审计指令+audit_type/audit_findings, 与当前运行 PROMPT 一致)。git diff main..worktree 显 7 文件系两 tip diff 假象(case-337/338/state/audit-log/scout-scan 乃 main 后增非 worktree 贡献)。merge-tree dry-run 零冲突；main 无 constraints 文件(纯新增零冲突)、main loop.sh 仍旧 step0。无源码/敏感路径(纯文档+PROMPT 文本)→audit_type=none。走 sanctioned opt-worktree.sh . merge optimization：squash 合并→剔 .opt-direction 桩→autonomous-studio 身份 commit 036a523→worktree --force 清理。验:constraints.md 落 main(YES, 三轮缺失债清零)、loop.sh grep audit_type=2、worktree list 仅 main(pending 1→0)、scout TODO=0 score=0.0 #1 推荐语变'无明确小工作单位——可跳过或文档润色'。constraints 文件已落地待下轮 step0 真正 Read 全文验证）**
- **活跃项目**: 持续自治管线巡检——sanctioned merge 落地 auto/optimization(a271bf7) 审计指令 worktree，.claude/autonomous-constraints.md 三轮缺失债清零、pending 队列 1→0
- **当前阶段**: merge 落地闭环——autonomous-constraints.md + loop.sh PROMPT 审计指令已入 main(036a523)，pending 队列清空
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: optimization (auto/optimization, a271bf7 → squash merge 入 main 036a523 'merge: 人工批准合并 optimization worktree optimization' — engine:audit-directives 方向；cmd_merge squash 合并 auto/optimization 入 main，带 .claude/autonomous-constraints.md(新建, DO NOT 6条排除+DO A代码审计每4轮/B敏感路径audit-log埋点/C audit_type+audit_findings case字段 三节, 正 protocol step0 所缺文件)+scripts/autonomous-loop.sh(PROMPT step0/5 引用 DO 审计指令+audit_type/audit_findings 字段, 与当前运行 PROMPT 一致)；worktree 已 --force 清理；验 constraints.md 落 main、loop.sh grep audit_type=2、pending 1→0、scout TODO=0 score=0.0)
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: 【可自动·低阻力】(1) pending merge 队列已清空(1→0)，scout #1 AS 推荐语变'无明确小工作单位——可跳过或做文档润色'——下轮 AS 若仍排#1 应跳过自我润色，转 scout #2 或审计轮次，不再霸榜。(2) 审计节奏：今日 case 138→139，下个审计边界=140（140%4=0），届时强制 code-review/security-review skill 走审计路径，优先挑有源代码的项目（跳过纯文档/配置）。(3) constraints 文件已落地，下轮 step0 可真正 Read 全文（不再凭 prompt 内联摘要执行），验证 DO/DO NOT 两节与运行行为一致。(4) AS main TODO=0 score=0.0 持续健康；deferred TODO=4(合法 triage 延期债) 不计入推荐。
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
<!-- LAST_UPDATED: 2026-06-30 -->
<!-- LAST_WORKTREE: autonomous-studio-aone/opt-scout-1782817213 (已 merge 落 main 1aa9b23: scout:backtick-strip — cmd_merge squash 合并 auto/opt-scout-1782817213 入 main，带 scripts/scout-scan.py(_STRIP_BACKTICKS 反引号段剥离治第6类自指虚高致 AS TODO=2 幽灵霸榜#1)+.claude/decisions/audit-log.jsonl(audit-20260630-105936-0dv11c config_change/medium)；worktree 已 --force 清理；验 main TODO=0 score=0.0、case-337 未误删、pending 2→1；上轮 case-337 首例 code-review 已审) -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【可自动·低阻力】pending merge 队列余 optimization worktree(auto/optimization a271bf7 方向 engine:general 4 files +69/-48)——下轮同法核 merge-base..worktree 真实 diff 后 sanctioned merge 或先 review; [2] constraints 文件 .claude/autonomous-constraints.md 持续缺失(三轮确认)——step0 强依赖却不存在，可从 prompt 内联 DO/DO NOT 摘要+历史案例引用重建为独立小工作单位; [3] 审计节奏: 今日 case 138，下个审计边界=140(140%4=0)届时强制 code-review/security-review; [4] AS main 现 TODO=0 score=0.0 永久健康，下轮若 AS 仍排#1 应挑 pending optimization worktree review 或跳过，不再自我润色霸榜 -->

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
