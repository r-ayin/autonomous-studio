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

- **最后活跃: 2026-07-01T04:15:00Z（派生 fix 轮 case-496·audit-002 M-002 route-fix。opt-worktree.sh:431,515 cmd_commit 文件列表 _cp_guard/rm 对 f=../../etc/cron.d/evil 可写/删 worktree 外文件。新增 _validate_commit_file_path helper(拒空/绝对路径/..段),两处 files 循环入口调用;非法路径跳过+报错不 abort。1 文件 +33。触及 scripts/opt-worktree.sh(public-interfaces.txt)→direction-shift 开新 worktree opt-security-shift-1782879314(commit 238afb1)。bash -n OK+单元测试 7/7(reject ['', '/etc/passwd', '../foo', 'a/../b', './../c']; pass ['scripts/foo.sh', '.claude/hooks/bar.py', 'a/b/c.txt'])。主仓 status clean(direction-shift 已还原主树)。落 opt-security-shift-1782879314 待人工 sanctioned-merge。audit-cycle-state M-002 填 fix_case_id=case-496 status 仍 pending pending_count=9 不变(3 已派生待 merge,6 未派生)）**
- **活跃项目**: autonomous-studio-aone 维护——**audit-002 scripts module 9 findings,H-001/H-005/M-002 已派生(case-494/495/496)待 merge,余 6 待派生(M-001→M-003→M-004→L-001/002/003)**。audit-001 hooks module 已 cycle-complete(2H merged via 900a3cc/b1d072d)。**已审源码:hooks/ 14 hook 全审+scripts/opt-worktree.sh+autonomous-loop.sh 深审**。
- **当前阶段**: case-496 收尾——M-002 fix 落 opt-security-shift-1782879314(commit 238afb1)待人工 sanctioned-merge;下轮派 M-001(slug glob 元字符过滤,opt-worktree.sh:339)
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次事件驱动 audit-cycle-state + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01(case-496 M-002 派生 fix)
- **LAST_WORKTREE**: opt-security-shift-1782879314(commit 238afb1,M-002 fix 待 sanctioned-merge)。另 opt-security-shift-1782878468(H-001 commit 0d26e39)+opt-security-shift-1782878926(H-005 commit f5d21f0)亦待 merge;auto/optimization 空壳保留
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【下轮=派生 M-001 fix】scripts/opt-worktree.sh:339 slug() 未过滤 glob 元字符致 ls -d "$WT_BASE"/opt-$(slug "$new_area")-* 若 area 含 * 或 ? 则 glob 展开匹配非目标 worktree→slug() 增加 glob 元字符剥离或报错。route-fix(opt-worktree.sh 公共接口→direction-shift 新 worktree)。[2]【后续优先级队列】M-001→M-003(cmd_merge symbolic-ref 查分支名,:628)→M-004(--bg 实现或删文档,autonomous-loop.sh:19)→L-001(trap 清理孤儿 claude,:20)→L-002(files 转绝对路径,:364)→L-003(grep 模式收窄,:76)。[3]【merge 待办】H-001(opt-security-shift-1782878468/0d26e39)+H-005(opt-security-shift-1782878926/f5d21f0)+M-002(opt-security-shift-1782879314/238afb1)三 fix 待人工 sanctioned-merge 入 main;merge 后回写 audit-cycle-state derived_fixes 对应 status=merged+pending_count 递减。[4]9 个全 merge/reject 后 audit-cycle-state→cycle-complete 触发 audit-003(审 scout-scan.py 或 sibling 项目 agent-dashboard/1BfrYn9G/huiyis)。[5]【structural debt】audit-002 无 structural finding;audit-001 遗留 H-010~H-018 未补登 structural-debt.md,可在派生 fix 间隙顺手补。
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
<!-- LAST_UPDATED: 2026-07-01(case-496 M-002 派生 fix) -->
<!-- LAST_WORKTREE: opt-security-shift-1782879314(commit 238afb1,M-002 fix 待 sanctioned-merge)。另 opt-security-shift-1782878468(H-001 0d26e39)+opt-security-shift-1782878926(H-005 f5d21f0)亦待 merge;auto/optimization 空壳保留 -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]下轮=派生 M-001 fix: scripts/opt-worktree.sh:339 slug() 未过滤 glob 元字符致 ls -d 误匹配→slug() 增 glob 元字符剥离或报错。route-fix(opt-worktree.sh 公共接口→direction-shift)。[2]后续 M-001→M-003(cmd_merge symbolic-ref,:628)→M-004(--bg 实现或删文档,autonomous-loop.sh:19)→L-001(trap 清理孤儿 claude,:20)→L-002(files 转绝对路径,:364)→L-003(grep 模式收窄,:76)。[3]H-001(1782878468/0d26e39)+H-005(1782878926/f5d21f0)+M-002(1782879314/238afb1)三 fix 待人工 sanctioned-merge 入 main;merge 后回写 audit-cycle-state derived_fixes status=merged+pending_count--。[4]9 个全 merge/reject 后 audit-cycle-state→cycle-complete 触发 audit-003(审 scout-scan.py 或 sibling 项目)。[5]audit-001 遗留 H-010~H-018 structural debt 待补登 structural-debt.md。 -->

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
