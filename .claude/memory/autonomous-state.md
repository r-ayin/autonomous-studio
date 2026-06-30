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

- **最后活跃: 2026-06-30T15:25Z（普通路径轮次：361%4=1≠0=非审计（DO A 不触发）。承接 case-360 NEXT_SUGGESTION[1] sanctioned-merge pending optimization @b87ecc0。step0 读 constraints DO NOT+DO 全文。step1 python3 scout-scan.py（constraints 写 bash 但该脚本 python3 shebang→bash 报 syntax error，改 python3 跑通）#1=AS score=0.0 推荐 review 1 待合并 wt。差异审：merge-base=d0e6776，optimization 落后 main 的 case-355..360 归档（archival-commit-mechanism 直提 main）；相对 main 真改动仅 autonomous-commit-gate.py(修复)+.gitignore(+.audit/)。运行 opt-worktree.sh . merge optimization：git Auto-merging .gitignore→CONFLICT（base 与两边均异→.audit/ 插入点上下文漂移；squash 无 MERGE_HEAD→cmd_merge line520 git merge --abort no-op→abort-exit，无 manual-resolve resume 路径）。reset 清 main 重试仍同处冲突（确定性）。核 gate：.autonomous_active marker 不存在→gate 熄火（同 case-357/359 merge commit 条件）。忠实复刻 cmd_merge line509-516 落地：resolve .gitignore 保留 .audit/ 块→git add→校验无 .opt-direction 泄漏→git commit -m 'merge: 人工批准合并...'→13c324e→worktree remove+branch -D auto/optimization。另清 case-360 测试遗留孤儿分支 auto/opt-test-audit。验证：git log -4 13c324e on e2b93eb 连续无回退+status 空+worktree list 仅 main+auto/* 分支空+grep _git_segments/_audit_log_block/_push_refs_main=7+check-ignore .audit/=IGNORED+ast.parse OK+无 .opt-direction 泄漏。case-361 outcome=succeeded audit_type=none findings=[]。main HEAD=13c324e 干净 pending=0）**
- **活跃项目**: autonomous-studio-aone 维护——case-361 sanctioned-merge optimization(b87ecc0)入 main 为 13c324e，commit-gate 修复+audit 埋点已落 main，pending=0
- **当前阶段**: 普通 sanctioned-merge 轮次完成，main HEAD=13c324e 干净 pending=0；下轮 case-362=362%4=2≠0 非审计普通路径回 scout 驱动（或承接 NEXT_SUGGESTION 小修）
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: optimization @b87ecc0（已 sanctioned-merge 入 main 为 13c324e；wt+branch 已清；含 _git_segments+_push_refs_main+_audit_log_block 修复+.gitignore .audit/；case-361 outcome=succeeded audit_type=none findings=[]；main HEAD=13c324e 干净 pending=0）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【审计盲区轮换·case-364】364%4=0=DO A 强制审计。换审 scripts/scout-scan.py（step1 每轮跑，确定性扫描+索引，2766 文件索引/IGNORE_DIRS/写 PROJECTS.md&.codebase-index 大 JSON FS 写敏感）或 scripts/opt-worktree.sh cmd_merge（本轮暴露真缺口：line499 git merge --squash 冲突即 abort-exit，无 manual-resolve 后 resume 路径——squash 无 MERGE_HEAD 致 line520 git merge --abort no-op，已 resolve+stage 的 merge 无法落地需手工复刻 commit；可审+补 resume 分支：检测 index 已 staged 且无 MERGE_HEAD→跳过 re-merge 直接 commit）；[2]【scout-scan shebang·低危小修】constraints step1 写 'bash scripts/scout-scan.py' 但该文件 python3 shebang→bash 报 syntax error，本轮改 python3 跑通。可选修 constraints 文档 step1 措辞改 'python3 scripts/scout-scan.py'（小工作单位，case-362/363 非审计轮可做）；[3]【gate 残留·低危延后】$(git)/反引号命令替换未纳入 _SHELL_OPS_RE 拆分（case-360 已记，需 LLM 刻意构造，不闭环）
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
<!-- LAST_WORKTREE: optimization @b87ecc0（已 sanctioned-merge 入 main 为 13c324e；wt+branch 已清；case-361 outcome=succeeded audit_type=none findings=[]；main HEAD=13c324e 干净 pending=0） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【审计盲区轮换·case-364】364%4=0=DO A 强制审计换审 scripts/scout-scan.py 或 scripts/opt-worktree.sh cmd_merge（本轮暴露 cmd_merge 无 manual-resolve resume 路径真缺口，可审+补）； [2]【scout-scan shebang·低危小修】constraints step1 写 bash 但脚本 python3 shebang→修文档措辞改 python3（case-362/363 非审计轮可做）； [3]【gate 残留·低危延后】$(git)/反引号未纳入 _SHELL_OPS_RE（case-360 已记，不闭环） -->

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
