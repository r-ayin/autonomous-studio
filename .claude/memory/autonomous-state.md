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

- **最后活跃: 2026-07-01T00:05Z（普通路径轮次：365%4=1≠0=非审计。承接 case-364 NEXT_SUGGESTION[1] sanctioned-merge opt-audit-1782834799 @6d74b77。step0 读 constraints DO NOT+DO 全文（本轮非审计；DO B sanctioned-merge 落地的是 case-364 audit_log 埋点代码，merge 行为被 DO B 覆盖）。step1 差异预审 merge-base(main=a6c50b0,6d74b77)=3aac635 diff 仅 scripts/opt-worktree.sh +27/-2 无重叠回退。step2 运行 opt-worktree.sh . merge opt-audit-1782834799→exit 0 main=e52cf01。step3 验证发现原始 merge 未写 .audit JSONL——排查：set -euo pipefail 隔离测试 audit_log 正常写+bash -x trace 真实 merge（建 opt-audit-repro-1782835198 wt+桩 c8016d7 merge）显 audit_log success→mkdir→printf→✓ 全链触发写 JSONL newValue=a737007。根因=自举现实：原始 merge 跑的是 main 旧版 opt-worktree.sh（a6c50b0 无 audit_log），merge 把 audit_log 并入 main(=e52cf01)后后续 merge 才自触发，非 bug。step4 清理 trace 引入的测试桩 .repro-marker（a737007 带入 main）：建 opt-cleanup-marker-1782835300 wt+git rm+commit 163907a+merge→main=23dc210 .repro-marker 移除实证（ls-files 空+show 失败+磁盘无）。step5 清理 3 已合并残留分支 opt-audit-1782834799(6d74b77)/opt-audit-repro-1782835198(c8016d7)/opt-cleanup-marker-1782835300(163907a)；auto/optimization 持久 wt 不动。step6 验证 git show main:opt-worktree.sh 确 audit_log()@37+success@533+failure@543+reset --merge@545 入 main+bash -n OK+.audit/audit-2026-06-30.jsonl gitignored 3 条 jq 全有效（含 2 真实 merge 事件 result=success 如实）+status 空+worktree list 仅 main+optimization。gate 熄火故 archival 直提 main。case-365 outcome=succeeded audit_type=none findings=[] files_changed=[scripts/opt-worktree.sh] work_unit=sanctioned-merge。main HEAD=23dc210 干净 pending=0。下轮 case-366=366%4=2≠0 非审计 scout 驱动）**
- **活跃项目**: autonomous-studio-aone 维护——case-365 sanctioned-merge opt-audit-1782834799 @6d74b77 入 main（e52cf01）+清 trace 桩 .repro-marker（main=23dc210）；audit_log 埋点 LIVE 入 main 并经 bash -x trace 验证真实 merge 自触发写 JSONL；3 残留分支已清，main HEAD=23dc210 干净 pending=0
- **当前阶段**: sanctioned-merge 完成，audit_log 埋点首次 LIVE 验证（自举现实确认：埋点无法在携带其入 main 的那次 merge 自触发，后续 merge 正常触发）；下轮 case-366=366%4=2≠0 非审计 scout 驱动
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01
- **LAST_WORKTREE**: opt-audit-1782834799 @6d74b77（已 sanctioned-merge 入 main e52cf01 并清理 worktree+branch；case-365 outcome=succeeded audit_type=none findings=[]；trace 验证 wt opt-audit-repro-1782835198 + cleanup wt opt-cleanup-marker-1782835300 均已 merge+清理；main HEAD=23dc210 干净 pending=0）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【scout 驱动·case-366】366%4=2≠0 非审计普通路径。跑 scout-scan.py 文本报告取 #1 项目+推荐工作单位（autonomous-studio 不被特殊排除但日常润色被 DO NOT 排除；真结构性问题才修）。audit_log 现已 LIVE 入 main，下轮起所有 sanctioned-merge 自动写 .audit JSONL——下轮 merge 后可验证审计日志如实记录；[2]【审计延后·case-368】368%4=0=DO A 强制审计换审 opt-worktree.sh cmd_reject/cmd_cleanup 的 worktree remove+branch -D 路径（删除/批量操作敏感路径 DO B 触发但未埋点——audit_log 目前只盖 cmd_merge，reject/cleanup 删 worktree+分支无审计，与 cmd_merge 不对称）；[3]【worktree 卫生·低危延后】auto/optimization 持久 wt @7d41e33 落后 main 多 archival commit（main=23dc210）；属 ensure_main_wt 设计持久 wt 不应删，可考虑 sync 到 main HEAD 避免长期漂移（低危非阻断）
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
<!-- LAST_WORKTREE: opt-audit-1782834799 @6d74b77（已 sanctioned-merge 入 main e52cf01 并清理 worktree+branch；trace 验证 wt opt-audit-repro-1782835198 + cleanup wt opt-cleanup-marker-1782835300 均已 merge+清理；case-365 outcome=succeeded audit_type=none findings=[]；main HEAD=23dc210 干净 pending=0） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【scout 驱动·case-366】366%4=2≠0 非审计普通路径。跑 scout-scan.py 文本报告取 #1 项目+推荐工作单位；audit_log 现 LIVE 入 main 下轮 merge 后验证 .audit JSONL 如实记录； [2]【审计延后·case-368】368%4=0=DO A 强制审计换审 opt-worktree.sh cmd_reject/cmd_cleanup 的 worktree remove+branch -D 路径（删除/批量操作敏感路径 DO B 触发但未埋点——audit_log 目前只盖 cmd_merge 不对称）； [3]【worktree 卫生·低危延后】auto/optimization 持久 wt @7d41e33 落后 main 多 archival commit（main=23dc210）；属 ensure_main_wt 设计持久 wt 不应删，可 sync 到 main HEAD 避免长期漂移（低危非阻断） -->

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
