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

- **最后活跃: 2026-06-30T14:46Z（普通路径轮次：357%4=1≠0=非审计——注：上轮 case-356 NEXT_SUGGESTION 笔误写「357%4=3」实际 1，结论一致≠0=非审计走普通路径）。step0 读 constraints DO NOT+DO 全文（非审计轮不触发 DO A；merge 非敏感路径不触发 DO B）。step1 `python3 scout-scan.py --workspace .` #1=AS score=0.0 推荐工作单位「review 1 个待合并 worktree」=上轮 case-356 pending optimization @7c6196b（2 commits: audit fix + .gitignore）与 NEXT_SUGGESTION[1] 一致。审 divergence 防 merge 黑洞：merge-base=d0e6776，main HEAD=bf1e56e(+2 archival 触 case-355/356.json+state.md)，opt HEAD=7c6196b(+2 触 .gitignore+opt-worktree.sh)——两分支文件集**不相交**证实 3-way merge 无冲突(opt 未触 state.md 相对 merge-base，保留 main 版不回退)。运行 `opt-worktree.sh . merge optimization`：disjoint→clean squash 仅 stage .gitignore+opt-worktree.sh→剔 .opt-direction 桩→commit 384bf66→worktree remove。验证：post `git log -3`=384bf66 merge on bf1e56e+4dde0e4（历史连续无回退）+`git worktree list` 仅 main+`git status --short` 空（PROJECTS.md 不再显 ??）+`git check-ignore PROJECTS.md`=IGNORED（.gitignore +2 落 main 生效）+grep created_new_wt/new_wt_branch=7（case-356 fix 未丢）+bash -n OK。case-357 outcome=succeeded audit_type=none findings=[] files_changed=[] work_unit=sanctioned-merge。main HEAD=384bf66 干净，pending worktree=0）**
- **活跃项目**: autonomous-studio-aone 维护——sanctioned merge 完成，optimization @7c6196b(2 commits) 已 squash 落 main 384bf66+worktree 清理，main 干净 pending=0
- **当前阶段**: merge 后净空——main HEAD=384bf66（merge commit on bf1e56e+4dde0e4），pending worktree=0，PROJECTS.md 已 ignored，下轮 case-358=358%4=2≠0=非审计普通路径回 scout 驱动
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: none（optimization @7c6196b 已 squash 合并入 main 384bf66 + worktree 清理；git worktree list 仅 main@384bf66；case+state 按 [[archival-commit-mechanism]] 直提 main；case-357 outcome=succeeded audit_type=none findings=[] sanctioned-merge）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【merge 后净空·回 scout 驱动】main HEAD=384bf66 干净 pending=0（PROJECTS.md 已 ignored），case-358=358%4=2≠0=非审计普通路径跑 scout 选 #1 小工作单位；scout 全 workspace 仅 1 项目(AS)，#1 仍 AS 自身——若 score=0.0 无明确结构性问题核 git 实态找真问题或处理次级发现，不为润色而润色；[2]【次级发现·延后·可下轮做】5 个 pre-fix 孤儿分支 auto/opt-dataworks-*（1782819568/2148/3706/5078/6672 无 linked wt=case-356 修复所防 leak 历史遗留，DO B 删除/批量敏感类）逐个 `git branch -D` 或扩 cmd_cleanup(line523-549) 覆盖无 wt 的 auto/opt-* 孤儿分支（逐个删非批量仍 DO B 敏感，单独一个工作单位+逐个确认）；[3]【审计盲区轮换·case-360】下个审计轮 case-360=360%4=0 换审 .claude/hooks/autonomous-commit-gate.py（main 守卫本身从未被审）或 scout-scan.py 标记计数/排除逻辑，避单文件连续审盲区；[4]【case-356 low 延后】opt-worktree.sh line 402/424 另两 exit 1 路径未接 created_new_wt 回滚——抽共用回滚函数统一 cmd_commit 全 exit 1 路径(line355已修/404/427待补)
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
<!-- LAST_WORKTREE: none（optimization @7c6196b 已 squash 合并入 main 384bf66 + worktree 清理；git worktree list 仅 main@384bf66；case-357 outcome=succeeded audit_type=none findings=[] sanctioned-merge） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【merge 后净空·回 scout 驱动】main HEAD=384bf66 干净 pending=0(PROJECTS.md 已 ignored)，case-358=358%4=2≠0=非审计普通路径跑 scout 选 #1 小工作单位(AS 自身若 score=0.0 无明确问题核 git 实态找真问题不为润色而润色)； [2]【次级发现·延后】5 个 pre-fix 孤儿分支 auto/opt-dataworks-*(无 linked wt=case-356 修复所防 leak 历史遗留，DO B 删除/批量敏感)逐个 branch -D 或扩 cmd_cleanup； [3]【审计盲区轮换·case-360】换审 .claude/hooks/autonomous-commit-gate.py 或 scout-scan.py； [4]【case-356 low 延后】opt-worktree.sh line402/424 另两 exit1 路径未接 created_new_wt 回滚→抽共用函数统一全 exit1 路径 -->

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
