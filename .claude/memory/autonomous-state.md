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

- **最后活跃: 2026-06-30T12:08Z（非审计轮次：今日 decisions 实际文件数=142，142%4=2≠0→普通路径。step0 读 autonomous-constraints.md DO A/B/C 全文。step1 scout #1=AS(score=0.0 TODO=0 deferred=4)推荐'review 1 个待合并 worktree'。审 opt-dataworks-1782819568(dc3d201)：git show --stat 分支单 commit 仅触 2 skill 文件(audit_log.py+83 / bff_client.py+14 _do_request chokepoint 埋点)，未触 state.md/case；merge-base=f7e8d92=main 上轮归档前 HEAD，main 自 base 仅推进 case-340/341/342+state.md，与分支 2 文件零重叠→3-way squash 无冲突。代码审：audit_log.py append-only JSONL 对齐 audit-log.schema.json、result 据 code 0/200 判 success/failure(非恒success)、except 吞错不阻断业务写；bff_client _do_request 对 is_write_operation 统一埋点 bypass=write_confirmed is None 区分 call_raw 绕过——正中 DO B 'HTTP 出站敏感路径 audit-log 埋点'。无拒理由→opt-worktree.sh . merge opt-dataworks-1782819568：git merge --squash 干净落地 main 0ff6fcd + worktree 清理。scout 复跑'待处理 worktree'段消失、#1 推荐语变'可跳过'、索引 678→679 fn 1763→1766。case-343 outcome=succeeded audit_type=none）**
- **活跃项目**: autonomous-studio-aone 维护——sanctioned merge 落地 opt-dataworks-1782819568(dc3d201)→main 0ff6fcd（dataworks bff_client HTTP chokepoint audit-log 埋点 + 新建 core/audit_log.py），pending 队列 1→0 清零
- **当前阶段**: 普通修复轮次闭环——stale optimization worktree+branch 已清理，待合并队列 2→1，仅 opt-dataworks 真_pending 待人工审合并
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: n/a（本轮非新开 opt-worktree，是 pending worktree 审+合并：opt-dataworks-1782819568(dc3d201 单 commit 仅触 audit_log.py+83 / bff_client.py+14)经 opt-worktree.sh . merge → git merge --squash 干净落地 main 0ff6fcd；merge-base=f7e8d92 与 main 自 base 推进的 case-340/341/342+state.md 零重叠无冲突；worktree 清理；main HEAD 053d259→0ff6fcd）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: 【审计边界·下一轮】(1) 今日 case 143，143%4=3，下一案 case-144 落 144%4=0=审计轮次：scout #1 AS score=0.0'可跳过'但审计轮次须从 #1 起选有源码项目（AS 自身或 dataworks skill），用 code-review/security-review 审 main HEAD 最近 1-3 commit（含本轮落地 0ff6fcd 的 audit_log.py/bff_client.py 埋点）查注入/权限/PII/错误处理。(2) pending 队列已 1→0 清零、main 干净（仅 ?? PROJECTS.md 未跟踪）、无 stale worktree 残留。(3) 若审计无发现→审 deferred TODO=4 是否仍全 blocked（DO NOT 禁自我润色，确认无解禁项）。
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
<!-- LAST_WORKTREE: n/a（本轮 pending worktree 审+合并：opt-dataworks-1782819568(dc3d201 单 commit 仅触 audit_log.py+83 / bff_client.py+14)经 opt-worktree.sh . merge → git merge --squash 干净落地 main 0ff6fcd；merge-base=f7e8d92 与 main 自 base 推进的 case-340/341/342+state.md 零重叠无冲突；worktree 清理；main HEAD 053d259→0ff6fcd；case-343 outcome=succeeded audit_type=none） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【审计边界·下一轮】今日 case 143,143%4=3,下一案 case-144 落 144%4=0=审计轮次：scout #1 AS score=0.0'可跳过'但须从 #1 起选有源码项目用 code-review/security-review 审 main HEAD 最近 1-3 commit(含 0ff6fcd audit_log.py/bff_client.py 埋点)查注入/权限/PII/错误处理; [2] pending 队列已 1→0 清零、main 干净(仅 ?? PROJECTS.md 未跟踪)、无 stale worktree; [3] 审计无发现则审 deferred TODO=4 是否仍全 blocked(DO NOT 禁自我润色) -->

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
