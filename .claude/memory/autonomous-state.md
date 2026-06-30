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

- **最后活跃: 2026-07-01T00:43Z（普通路径轮次：371%4=3≠0=非审计 sanctioned-merge。承接 case-370 NEXT_SUGGESTION[1]：merge optimization @3e3302f→main。step0 读 constraints，371%4=3≠0 非审计 sanctioned-merge 路径。step1 scout #1=AS score=0.0『review 1 个待合并 worktree』与 NEXT_SUGGESTION 一致。step2 差异预审 merge-base(main,auto/optimization)=3a73708；main 自 base 仅 archival（case-370.json+state.md），optimization 自 base 仅 scripts/opt-worktree.sh +9/-0，无文件重叠→clean merge。step3 人工审 diff：audit_log 签名与现有 delete 路径（reject 585/587、cleanup 621/644）一致 result name "" reason delete artifact；result 分支正确（! -d $target→success / else→failure）；reason 含 $new_wt_branch（auto/opt-... 含 /，json_escape 不转义 / 合法 JSON）；|| true 不阻断。step4 opt-worktree.sh . merge optimization→squash→commit @2fb1c5f worktree 清理。step5 删 cmd_merge 残留 auto/optimization 分支（was 3e3302f，squash 后内容全入 main，按 case-369 step5 模式 branch -D）。step6 验证：bash -n OK；grep audit_log 四删除路径全 LIVE 入 main commit-rollback(416/418)+merge(567/577)+reject(594/596)+cleanup(630/653)；.audit 新条目 audit-20260630-164223-2ccc58 action=deploy resource.type=deployment identifier=optimization newValue=2fb1c5f result=success jq -c 有效（非自举首跑 merge audit_log 真实触发）；git status 空；git branch 仅 main。case-371 outcome=succeeded audit_type=none findings=[]。main HEAD=2fb1c5f 干净 pending=0。下轮 case-372=372%4=0=DO A 强制审计轮换审非 audit_log 目标）**
- **活跃项目**: autonomous-studio-aone 维护——case-371 sanctioned-merge optimization @3e3302f→main @2fb1c5f；四删除路径（merge/reject/cleanup/commit-rollback）audit_log 全 LIVE 入 main 对称；pending=0
- **当前阶段**: sanctioned-merge 完成；pending=0；下轮 case-372=372%4=0=DO A 强制审计轮换审非 audit_log 目标（hooks/pre-commit + autonomous-commit-gate.py 门禁 security-review / scout-scan.py code-review / opt-worktree.sh worktree 建路径 logic review）
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01
- **LAST_WORKTREE**: optimization @3e3302f（已 merged→main @2fb1c5f，分支已删；方向 engine:audit-log-rollback；case-371 outcome=succeeded audit_type=none findings=[]；main HEAD=2fb1c5f 干净 pending=0）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【DO A 强制审计·case-372】372%4=0=强制审计轮次。audit_log 四删除路径全 LIVE 入 main 后换审非 audit_log 目标。候选（scout 届时重排选有源码项目，跳过纯文档/配置）：(a) hooks/pre-commit + .claude/hooks/autonomous-commit-gate.py 门禁 security-review（外部输入/命令注入面，pre-commit 接收用户路径/参数）；(b) scripts/scout-scan.py 自身 code-review（.codebase-index 大 JSON 只读面 / subprocess 调用面）；(c) scripts/opt-worktree.sh detect_main_branch/ensure_main_wt worktree 建路径 logic review。审计轮次优先挑有源代码的项目；[2]【剩余低危延后】audit_log instrumentation 主体已闭合（四删除路径全 LIVE）。后续新增 cmd_* 删除/批量子命令须同步埋点（opt-worktree.sh audit_log() 注释已标 DO B 约束）；[3]【可选】case-372 审计若发现真问题→起 opt-worktree 修复（1-3 文件）；若无真问题→写 case 存档 outcome=succeeded outcome_evidence 引审计具体文件/行号+skill 输出摘要
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
<!-- LAST_WORKTREE: optimization @3e3302f（已 merged→main @2fb1c5f，分支已删；方向 engine:audit-log-rollback；case-371 outcome=succeeded audit_type=none findings=[]；main HEAD=2fb1c5f 干净 pending=0） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【DO A 强制审计·case-372】372%4=0=强制审计轮次。audit_log 四删除路径全 LIVE 入 main 后换审非 audit_log 目标。候选（scout 届时重排选有源码项目，跳过纯文档/配置）：(a) hooks/pre-commit + .claude/hooks/autonomous-commit-gate.py 门禁 security-review（外部输入/命令注入面）；(b) scripts/scout-scan.py 自身 code-review（.codebase-index 大 JSON 只读面 / subprocess 调用面）；(c) scripts/opt-worktree.sh detect_main_branch/ensure_main_wt worktree 建路径 logic review；[2]【剩余低危延后】audit_log instrumentation 主体已闭合（四删除路径全 LIVE）。后续新增 cmd_* 删除/批量子命令须同步埋点（opt-worktree.sh audit_log() 注释已标 DO B 约束）；[3]【可选】case-372 审计若发现真问题→起 opt-worktree 修复（1-3 文件）；若无真问题→写 case 存档 outcome=succeeded outcome_evidence 引审计具体文件/行号+skill 输出摘要 -->

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
