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

- **最后活跃: 2026-07-01T11:33:13Z（瞭望/light 轮 case-492。audit-cycle-state status=fix-in-progress pending_count=2(两 high 待人工 merge)未触发全量审计轮→light 轮。scout #1=AS score=0.0『review 待合并 worktree(人工动作)+无紧迫小工作单位』不顺延→取可派生最小 route-fix。audit-2026-07-01-001 共 19 findings,7 medium route-fix 中落入 pending worktree 文件(H-003/004/006/007/008)的会冲突→跳过,选 clean-file H-005 codegraph-sync.py L355 capability-registry.json 非原子写。复用 case-488 H-002 已验证 _atomic_write_json 模式(tempfile.mkstemp+os.replace+异常 unlink 不静默吞错)逐字移植+docstring 改述冷启动预分析语境,加 import tempfile,替换 main() L355 写入点。1 文件 +22/-3。py_compile OK+merge-tree --write-tree rc=0 clean。DO B 判定:capability-registry 写入非敏感路径不埋点(同 case-488/489/491)。未动 audit-cycle-state(H-005 非 derived_route_fixes 门控计数,medium 派生独立 case 不破 cycle 数学,pending_count 维持 2)。case-492 outcome=succeeded audit_type=audit-log-instrumentation audit_depth=shallow audit_id=audit-2026-07-01-001）**
- **活跃项目**: autonomous-studio-aone 维护——auto/opt-security-1782873915@09fe68c(ahead=4 累计 7b4189b H-002 原子写+bf46478 resume-checkpoint TOCTOU+ddc0f58 H-001 shell 注入+09fe68c H-005 codegraph 原子写,4 commit 分属 3 不同文件无冲突,merge-tree --write-tree 干演 rc=0 clean,待人工 squash merge)。**另 2 待合并分支:auto/opt-security-1782866336@f7dda51(ahead=4)+auto/opt-security-1782872471@05a6c62(ahead=1)亦 merge-tree 已审 clean**。**已审源码 27 处:.claude/hooks/ 14 hook(含 codegraph-sync.py case-456 无真问题+case-492 H-005 原子写修复已起 opt-security-1782873915@09fe68c 待审)+其余 13 hook 见 case-491 state 详述**。
- **当前阶段**: case-492 瞭望/light 轮·派生 medium route-fix——audit-2026-07-01-001 H-005(codegraph-sync.py 非原子写)已修复@09fe68c;audit-cycle-state 两 high derived_fix(H-001+H-002)仍 status=pending 待人工 merge→pending_count=2 未变(全量审计轮未触发)
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次事件驱动 audit-cycle-state + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01(case-492)
- **LAST_WORKTREE**: auto/opt-security-1782873915@09fe68c(ahead=4:7b4189b H-002 原子写+bf46478 resume-checkpoint TOCTOU+ddc0f58 H-001 shell 注入+09fe68c H-005 codegraph 原子写,4 commit 分属 3 不同文件无冲突,merge-tree 干演 rc=0 clean)。累计待人工 merge 3 分支:auto/opt-security-1782866336@f7dda51(ahead=4)+auto/opt-security-1782872471@05a6c62(ahead=1)+auto/opt-security-1782873915@09fe68c(ahead=4)
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【人工 merge·高优】git merge --squash auto/opt-security-1782873915(现 4 commit:7b4189b+bf46478+ddc0f58+09fe68c)→main;merge-tree 干演 rc=0 clean。merge 后置 audit-cycle-state 两 high derived_fix status=merged→pending_count=0→cycle-complete→触发下轮全量审计(审未深度审过的项目,看 .claude/audits/ 避免重审 hooks)。[2]【人工 merge 待办】另 2 分支:auto/opt-security-1782866336@f7dda51(ahead=4)+auto/opt-security-1782872471@05a6c62(ahead=1)亦待 squash merge。[3]【后续 medium route-fix 派生】H-005 已修(本轮)。剩余 clean-file medium:H-009 notify-phone.py L160 ntfy header 注入(下轮可做)。落入 pending worktree 文件的 medium(H-003/004/006/007/008)待对应 worktree merge 后再评估(main HEAD 可能已修)。[4]【structural debt】H-011~H-018 audit-gap 类尚未写入 structural-debt.md,后续审计轮补登。
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
<!-- LAST_WORKTREE: auto/opt-security-1782873915@09fe68c(ahead=4:7b4189b H-002 原子写+bf46478 resume-checkpoint TOCTOU+ddc0f58 H-001 shell 注入+09fe68c H-005 codegraph 原子写,4 commit 分属 3 不同文件 merge-tree 干演 rc=0 clean)。累计待人工 merge 3 分支 9 commit:auto/opt-security-1782866336(ahead=4)+auto/opt-security-1782872471(ahead=1)+auto/opt-security-1782873915(ahead=4) -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]人工 git merge --squash auto/opt-security-1782873915(4 commit)→main;merge 后置 audit-cycle-state 两 high derived_fix status=merged→pending_count=0→cycle-complete→触发下轮全量审计。[2]另 2 分支亦待 squash merge。[3]下轮 clean-file medium route-fix:H-009 notify-phone.py L160 ntfy header 注入。落入 pending worktree 文件的 medium(H-003/004/006/007/008)待 merge 后再评估。[4]case-493=493%4=1≠0 非审计轮·瞭望(实际仍由 audit-cycle-state 事件驱动判定:status=fix-in-progress 则 light)。 -->

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
