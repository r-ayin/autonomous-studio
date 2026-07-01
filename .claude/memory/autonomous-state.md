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

- **最后活跃: 2026-07-01T01:04:00Z（case-469=今日第105例,469%4=1≠0 非审计轮·sanctioned-merge-review。承接 case-468 NEXT。scout-scan #1=AS score=0.0『review 1 个待合并 worktree』。opt-security-1782866336@cf17a35 ahead=2 含 ba52e9c(case-464 audit-log 埋点)+cf17a35(case-468 redaction 修补),但此前从未作为整体做过合并就绪审查——case-465 只审 ba52e9c 单 commit,case-468 是制造 cf17a35 的审计轮。本轮补缺口:做完整 2-commit worktree 合并就绪审查。关键纠偏:git diff main..worktree 误显 5 case JSON+state.md『删除』,实为 main HEAD vs worktree HEAD 直接对比伪影(worktree 在 5ed9a52 分叉,此后 case-464..468 经 archival-commit-mechanism 直提 main)。改看真 3-way diff:git diff 5ed9a52..worktree --stat=仅 2 源文件(auto-commit.py push 块 3 处 _audit_log_commit + decision-observer.py 字符类扩展),无 case JSON/state.md。main 侧自 merge-base 起仅改 case JSON+state.md(6 文件)与 worktree 改动集完全不相交→无语义冲突。git merge-tree --write-tree main auto/opt-security-1782866336 干演 exit=0 产 tree 3b4a509 无冲突文件=clean merge 可行。两 fix 语义连贯(分属不同函数/文件,均 security-hardening,无重叠)。py_compile OK。四验干净:porcelain=空、worktree list=main@e6d6eb7+opt-security@cf17a35+optimization@57d16a9、rev-list main..opt-security=2。结论:worktree 合并就绪,引擎无权 merge 留人工 squash merge。无新源码改动(审查轮)。case-469.json+state.md 直提 main(archival-commit-mechanism)。case-469 outcome=succeeded audit_type=none audit_findings=[]。下轮 case-470=470%4=2≠0 非审计轮·worktree-cleanup(optimization 死桩残留)或 skip）**
- **活跃项目**: autonomous-studio-aone 维护——case-468 security-review 审 decision-observer.py 起 opt-security-1782866336@cf17a35(ahead=2 累计 case-464 audit-log+case-468 redaction 修复,待人工 squash merge)。**已审源码 23 处:.claude/hooks/ 11 hook(含 decision-observer.py case-468 1 medium 已起 opt-security 修复待审)+codegraph-sync.py case-456+notify-phone/autonomous-commit-gate/pipeline-gate/post-edit-lint.py case-448+scaffold-skill.sh+opt-worktree.sh+scout-scan.py(case-380/049)+triage.py+bff_client.py(case-420 F3+case-436 F1 已合并 main@125a15e)+audit_log.py(case-424)+autonomous-commit-gate.py(case-428/440 已合并 main@051bb4b)+apply_resource_access.py(case-432 info deferred)+pipeline-gate.py(case-432/433 已合并 main)+notify-phone.py(case-444 已合并 main@9a8748e)+post-edit-lint.py(case-448)+scripts/route-health-scorer.py(case-452 无真问题)+codegraph-sync.py(case-456 无真问题)+discovery-gate.py(case-460 无真问题)+auto-commit.py(case-464 1 medium 已起 opt-security-1782866336@ba52e9c 修复,case-465 审查确认可 merge 待人工)+decision-observer.py(case-468 1 medium redaction 缺口已起 opt-security@cf17a35 修复待审)**。
- **当前阶段**: case-469 非审计轮合并就绪审查完成(opt-security-1782866336 整体 2-commit 经 3-way diff+merge-tree 干演确认无冲突合并就绪,留人工 squash merge);下轮 case-470=470%4=2≠0 非审计轮·worktree-cleanup(optimization 死桩残留)或 skip
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01(case-469)
- **LAST_WORKTREE**: opt-security-1782866336@cf17a35(ahead=2: ba52e9c case-464 audit-log + cf17a35 case-468 redaction;整体合并就绪审查通过 case-469,待人工 squash merge)
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【case-470=470%4=2≠0 非审计轮·worktree-cleanup】auto/optimization@57d16a9 死桩(0 ahead main,3-way diff 空)残留未清(case-466 曾称已删但实际仍在 worktree list)→跑 opt-worktree.sh . cleanup 删 optimization worktree+branch。[2]【人工 merge 待办,累计 2 commit】用户手动 `git merge --squash auto/opt-security-1782866336 && git commit` 落 main(case-469 已确认合并就绪:3-way diff 仅 2 源文件+merge-tree exit=0 无冲突+两 fix 语义连贯),随后 cleanup 清 opt-security worktree+branch。[3]【下个审计轮 case-472=472%4=0】续审剩余未审源码(scripts/distill-patterns.py / confidence-calibrator.js 等)。
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
<!-- LAST_WORKTREE: opt-security-1782866336@cf17a35（ahead=2: ba52e9c case-464 audit-log + cf17a35 case-468 redaction;整体合并就绪审查通过 case-469,待人工 squash merge） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]case-470=470%4=2 非审计轮·worktree-cleanup:删 auto/optimization@57d16a9 死桩(0 ahead,case-466 称删实存)。[2]人工 `git merge --squash auto/opt-security-1782866336 && git commit`(case-469 已确认合并就绪)+cleanup opt-security。[3]下个审计轮 case-472 续审 scripts/distill-patterns.py 等 -->

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
