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

- **最后活跃: 2026-07-01T04:01:00Z（派生 fix 轮 case-494·audit-002 H-001 route-fix。opt-worktree.sh:327(direction-shift)+:348(route-fix 新 area)两处 worktree add 失败吞错+空目录残留+写桩造成功假象,仿 ensure_main_wt 守护:失败→rmdir --ignore-fail-on-non-empty $target+exit 1 不写桩。1 文件 +15/-2。bash -n OK+隔离功能测试(预建同名分支强制 worktree add 失败)验证 GUARD_EXIT=1/空目录已清/无桩/无孤儿 wt。落 opt-security-shift-1782878468(commit 0d26e39)待 sanctioned-merge。audit-cycle-state H-001 填 fix_case_id=case-494 status 仍 pending(未 merge) pending_count=9 不变）**
- **活跃项目**: autonomous-studio-aone 维护——**audit-002 scripts module 9 findings,H-001 已派生 case-494 待 merge,余 8 待派生(H-005→M-002→M-001→M-003→M-004→L-001/002/003)**。audit-001 hooks module 已 cycle-complete(2H merged via 900a3cc/b1d072d)。**已审源码:hooks/ 14 hook 全审+scripts/opt-worktree.sh+autonomous-loop.sh 深审**。
- **当前阶段**: case-494 收尾——H-001 fix 落 opt-security-shift-1782878468 待人工 sanctioned-merge;下轮派 H-005(autonomous-loop.sh:73 claude 输出改 mktemp 临时文件)
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次事件驱动 audit-cycle-state + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01(case-493 audit-002 完成)
- **LAST_WORKTREE**: 无(纯审计轮不产 worktree)。opt-security-* 三分支已 merge 入 main 并删;仅 auto/optimization 空壳保留
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【下轮=派生 H-001 fix】opt-worktree.sh line 327/348 worktree add 失败后 rmdir $target + 明确 exit 1(仿 ensure_main_wt 模式),1 文件 route-fix,走 opt-worktree commit。[2]【再下轮=派生 H-005 fix】autonomous-loop.sh line 73 claude 输出改 mktemp 临时文件,tail/grep 读文件避免变量膨胀+敏感信息暴露。[3]【后续】M-002 路径遍历校验→M-001 glob 元字符→M-003 symbolic-ref 查分支→M-004 --bg 实现或删除文档→L-* 三个 low。9 个全部 merge/reject 后 audit-cycle-state 回 cycle-complete→触发 audit-003 审 scout-scan.py 或 sibling 项目(agent-dashboard/1BfrYn9G/huiyis)。[4]【structural debt】audit-002 无 structural finding,H-010~H-018(audit-001 low/info)仍未补登 structural-debt.md,可在派生 fix 间隙顺手补。
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
<!-- LAST_UPDATED: 2026-07-01(case-494 H-001 派生 fix) -->
<!-- LAST_WORKTREE: opt-security-shift-1782878468(commit 0d26e39,H-001 fix 待 sanctioned-merge)。audit-002 余 8 finding 待派生 -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]下轮=派生 H-005 fix: autonomous-loop.sh:73 `out=$(claude -p ... 2>&1)` 改 mktemp 临时文件,tail/grep 读文件避免 MB 级变量膨胀+敏感信息驻留,结束 shred/rm。1 文件 route-fix 走 opt-worktree commit。[2]后续 M-002(opt-worktree.sh:431/515 cmd_commit 文件列表 .. 遍历校验)→M-001(slug glob 元字符)→M-003(symbolic-ref 查分支)→M-004(--bg 实现或删文档)→L-001(trap 清理)/L-002(文件转绝对路径)/L-003(grep 模式收窄)。9 个全 merge/reject 后 audit-cycle-state→cycle-complete 触发 audit-003。[3]H-001 fix 待人工 sanctioned-merge opt-security-shift-1782878468 入 main;merge 后回写 audit-cycle-state derived_fixes[H-001].status=merged+pending_count--。[4]audit-001 遗留 H-009 notify-phone ntfy header 注入未修可顺手;H-010~H-018 structural debt 待补登 structural-debt.md。 -->

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
