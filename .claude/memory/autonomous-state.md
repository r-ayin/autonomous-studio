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

- **最后活跃: 2026-06-30T15:30Z（普通路径轮次：362%4=2≠0=非审计（DO A 不触发）。承接 case-361 NEXT_SUGGESTION[2] scout-scan shebang 缺口。step0 读 constraints DO NOT+DO 全文（DO NOT 禁日常自我润色——此为每轮复现真实操作性缺陷非润色，不排除）。step1 python3 scout-scan.py #1=AS score=0.0 无明确工作单位（仅推荐文档润色被 DO NOT 排除），无 #2 可顺延（workspace 仅 1 项目）→取 NEXT_SUGGESTION[2] 代码修复分支。设计 sh/python3 polyglot：保 #!/usr/bin/env python3 shebang（直执原生 python3 不损性能）+ 插入 `''''exec python3 -- "$0" "$@" # '''` 行（bash 调用 re-exec 到 python3，python3 直执为 no-op 字符串字面量）+ 1 行 # 注释说明防误删。/tmp poly-test 四式（bash/sh/python3/direct-exec）全 PYOK 验证后落地。核 scout-scan.py 不用 __doc__（grep 无命中）→polyglot 行覆盖 __doc__ 的代价为零。Edit scripts/scout-scan.py +4 行。验证实脚本：bash scout-scan.py 产出完整报告（此前同命令报 syntax error 失败）+python3 无回归+ast.parse OK+--json 有效 JSON projects=1。提交 opt-worktree.sh . commit scout-scan:polyglot（首次漏 project 参数致 line29 cd 报错→interface [project] commit 补 . 重跑通过）→方向分歧 engine→scout-scan 开新 worktree opt-scout-scan-1782833675 commit 5695a05 +4 行 1 文件。gate 熄火（.autonomous_active marker 不存在同 case-361）故 archival 直提 main。case-362 outcome=succeeded audit_type=none findings=[]。main HEAD=7d41e33 干净 pending=opt-scout-scan-1782833675 @5695a05 待 case-363 sanctioned-merge）**
- **活跃项目**: autonomous-studio-aone 维护——case-362 scout-scan polyglot 修复（bash 调用 re-exec python3）入 opt-scout-scan-1782833675 @5695a05 pending merge，main HEAD=7d41e33 干净
- **当前阶段**: 普通 polyglot 修复轮次完成，改动隔离于 worktree pending；下轮 case-363=363%4=3≠0 非审计普通路径 sanctioned-merge opt-scout-scan-1782833675（main 自 f9b36aa 未动 scout-scan.py 预期 squash 干净无冲突）
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: opt-scout-scan-1782833675 @5695a05（方向 scout-scan:polyglot，+4 行 1 文件 scripts/scout-scan.py，pending sanctioned-merge；main HEAD=7d41e33 干净；case-362 outcome=succeeded audit_type=none findings=[]）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【sanctioned-merge·case-363】承接 pending worktree opt-scout-scan-1782833675 @5695a05（scout-scan:polyglot +4 行 1 文件）。main 自 f9b36aa 起未动 scout-scan.py→预期 squash 干净无冲突（纯新增头无重叠，比 case-357/359 superset 更干净）。运行 opt-worktree.sh . merge opt-scout-scan-1782833675 合并入 main。合并后从 case-363 起循环 step1 'bash scripts/scout-scan.py' 原生跑通，消除每轮 syntax-error 重试；[2]【审计盲区轮换·case-364】364%4=0=DO A 强制审计换审 scripts/opt-worktree.sh cmd_merge（case-361 暴露真缺口：squash 无 MERGE_HEAD 致 line520 git merge --abort no-op，已 resolve+stage 的 merge 无法落地需手工复刻 commit；可审+补 resume 分支：检测 index 已 staged 且无 MERGE_HEAD→跳过 re-merge 直接 commit）或审 scout-scan.py 索引 FS 写敏感性；[3]【gate 残留·低危延后】$(git)/反引号未纳入 _SHELL_OPS_RE 拆分（case-360 已记，不闭环）
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
<!-- LAST_WORKTREE: opt-scout-scan-1782833675 @5695a05（方向 scout-scan:polyglot，+4 行 1 文件 scripts/scout-scan.py，pending sanctioned-merge；case-362 outcome=succeeded audit_type=none findings=[]；main HEAD=7d41e33 干净） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【sanctioned-merge·case-363】承接 pending opt-scout-scan-1782833675 @5695a05（scout-scan:polyglot +4 行 1 文件，main 自 f9b36aa 未动 scout-scan.py 预期 squash 干净无冲突）→ opt-worktree.sh . merge 合并入 main，合并后循环 step1 bash scout-scan.py 原生跑通消除每轮 syntax-error 重试； [2]【审计盲区轮换·case-364】364%4=0=DO A 强制审计换审 opt-worktree.sh cmd_merge（squash 无 MERGE_HEAD 致 merge --abort no-op 真缺口，可审+补 resume 分支）或 scout-scan.py 索引 FS 写敏感性； [3]【gate 残留·低危延后】$(git)/反引号未纳入 _SHELL_OPS_RE（case-360 已记，不闭环） -->

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
