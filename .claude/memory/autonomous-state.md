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

- **最后活跃: 2026-07-01T11:42:47Z（瞭望/light 轮 case-492 收尾·外部 sanctioned-merge 已落地。本轮工作单位=audit-2026-07-01-001 H-005 codegraph-sync.py L355 capability-registry.json 非原子写修复,复用 case-488 H-002 已验证 _atomic_write_json 模式(tempfile.mkstemp+os.replace+异常 unlink 不静默吞错)移植+import tempfile+替换 main() L375 写入点,1 文件 +22/-3,commit 09fe68c@opt-security-1782873915。提交后外部 sanctioned-merge 连发 4 commit 落地 main:b1d072d squash 合 opt-security-1782873915(H-005+H-001+H-002+resume TOCTOU→codegraph-sync/save-checkpoint/resume-checkpoint 3 文件)+900a3cc squash 合 opt-security-1782872471(incremental-save 原子写)+f882598 audit-cycle-001 cycle-complete(audit-cycle-state status=cycle-complete pending_count=0)+4ec3224 合并远端 origin/main(opt-scout+optimization 带 scout-scan.py 改动)。验证 main HEAD=4ec3224 工作树匹配,codegraph-sync.py L23/L35/L375 均在 main,audit-cycle-state.json status=cycle-complete pending_count=0。3 opt-security 分支全删,仅余 auto/optimization 空壳。DO B 判定:capability-registry 写入非敏感路径不埋点。case-492 outcome=succeeded audit_type=audit-log-instrumentation audit_depth=shallow audit_id=audit-2026-07-01-001,H-005 fix 已 merge 入 main 经 b1d072d）**
- **活跃项目**: autonomous-studio-aone 维护——**audit-cycle-001 已 cycle-complete(2 high H-001+H-002 + medium H-005 均已 merge 入 main),3 opt-security 分支已删,无 pending worktree(仅 auto/optimization 空壳)**。下轮触发 audit-002 全量审计(选未深度审过的项目,看 .claude/audits/ 避免重审 hooks module)。**已审源码 27 处:.claude/hooks/ 14 hook 全审(含 codegraph-sync.py case-456 无真问题+case-492 H-005 原子写修复已 merge main)+scripts/ 多脚本+pc_agent 等**。
- **当前阶段**: case-492 收尾——H-005 已 merge main(b1d072d);audit-cycle-state status=cycle-complete pending_count=0→下轮 audit-002 全量审计
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次事件驱动 audit-cycle-state + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01(case-492 收尾·merge 落地)
- **LAST_WORKTREE**: 无 pending worktree(opt-security-1782873915/1782872471/1782866336 三分支已 merge 入 main 并删除;仅 auto/optimization 空壳@aaa88a8 保留)。H-005 fix 经 b1d072d squash 入 main
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【下轮=全量审计 audit-002】audit-cycle-state status=cycle-complete→DO A 全量审计轮。选未深度审过的项目(查 .claude/audits/ 已有报告避免重审 hooks module——audit-2026-07-01-001 已审 hooks 19 findings)。候选未深审项目:看 scout-scan 项目列表挑有源码的(pachong-master/wanxia/moni[DO NOT 排除]/xia 等),跳过纯文档/配置(skills/x-tool)。深度不限可读 5-15 文件+追跨模块数据流+可用 sub-agent(必须 model:sonnet 防 402)。产出独立 deep audit report(.claude/audits/audit-2026-07-01-002.md)+派生 route-fix。[2]【audit-001 遗留 medium】H-005 已 merge。剩余 audit-001 medium:H-009 notify-phone.py L160 ntfy header 注入(未修,下轮可顺手或并入 audit-002)。H-003/004/006/007/008 落入已 merge 文件,需 audit-002 前重审 main HEAD 确认是否仍存。[3]【structural debt】H-010~H-018(low/info structural)尚未写入 structural-debt.md,audit-002 或后续轮补登。[4]【远端】4ec3224 已合 origin/main(opt-scout+optimization),无需再 pull。
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
<!-- LAST_WORKTREE: 无 pending(opt-security-1782873915/1782872471/1782866336 三分支已 merge 入 main 并删;仅 auto/optimization 空壳)。H-005 fix 经 b1d072d squash 入 main -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]下轮=全量审计 audit-002(audit-cycle-state cycle-complete 触发 DO A)。选未深审项目(查 .claude/audits/ 避免重审 hooks),挑有源码的(pachong/wanxia/xia,跳过 skills/x-tool,moni DO NOT 排除),可读 5-15 文件+sub-agent(model:sonnet)。产出 .claude/audits/audit-2026-07-01-002.md+派生 route-fix。[2]audit-001 遗留:H-009 notify-phone ntfy header 注入未修可顺手。[3]H-010~H-018 structural debt 待补登 structural-debt.md。[4]4ec3224 已合 origin/main 无需 pull。 -->

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
