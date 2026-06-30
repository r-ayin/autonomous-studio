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

- **最后活跃: 2026-07-01T20:40Z（case-408=今日第44例,408%4=0 审计轮 DO A 强制。承接 case-407 NEXT[1]:.claude/hooks/ 全量闭环→转审其他源码路径。scout-scan #1=AS score=0.0 无明确小工作单位(延期已triage TODO=4 不计),审计轮不 skip。选 skills/luban/tools/scaffold-skill.sh(170L 鲁班骨架生成器,路径拼接+JSON 注入面)手动 security-review。发现 1medium+1low 均真实复现:①medium L114 marketplace.json heredoc 直拼 ${TAGLINE} 到 JSON 字符串值,tagline 含 " → python3 json.load 拒 JSONDecodeError line8 col27,违反'出生即合规'前提;②low L7 SKILL_NAME 未校验直拼路径,含 ../ 会在 cwd 外建文件。修复 1file:slug 白名单 ^[A-Za-z0-9_-]+$(一关封死路径穿越+JSON 注入两面)+json_escape()(对齐 opt-worktree.sh)+marketplace.json description 用 ${TAGLINE_ESC}。验证 bash -n OK+TEST1/2 tagline 含 "/\ → VALID JSON ✓+TEST3/4 ../evil·foo/bar 被拒+TEST5 正常 run ✓。改动落 opt-worktree engine:security @c4744bc(auto-optimization) pending=1 待下轮 sanctioned-merge。DO B 不适用(输入校验/转义非敏感路径)。case-408.json+state.md 直提 main(archival-commit-mechanism)。case-408 outcome=succeeded audit_type=security-review audit_findings=[medium L114 JSON 注入/low L7 路径穿越]。pending=1 clean。）**
- **活跃项目**: autonomous-studio-aone 维护——case-408 审计轮 security-review scaffold-skill.sh 1medium+1low 修复(slug 白名单+JSON 转义)@c4744bc pending。case-407 skip 心跳。case-405 sanctioned-merge engine:security @f2b767b→main 998136b(discovery-gate.py 原子锁+审计埋点)。case-404 审计轮 security-review discovery-gate.py 1medium+1info 修复+DO B 埋点。case-400 审计轮 security-review decision-observer.py 1medium+1low 修复。case-396 审计轮 security-review auto-commit.py git add -A medium+修复+DO B。case-393 sanctioned-merge opt-security→main 2353e2e(pipeline-gate 去 shell=True)。case-392 审 pipeline-gate 1low+修复。case-389 sanctioned-merge notify-phone→main 47128f1。case-388 security-review notify-phone 1low+修复。**已审源码 8 处:.claude/hooks/ 7 hook 全审(commit-gate/codegraph-sync/notify-phone/pipeline-gate/auto-commit/decision-observer/discovery-gate)+scaffold-skill.sh**。
- **当前阶段**: case-408 审计轮 security-review scaffold-skill.sh 修复落 @c4744bc pending=1(git status clean,worktree list=optimization 1提交,git branch=main+auto-optimization);下轮 case-409=409%4=1≠0 非审计轮·sanctioned-merge @c4744bc→main
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01
- **LAST_WORKTREE**: auto-optimization @c4744bc（case-408 审计修复 scaffold-skill.sh slug 白名单+JSON 转义,pending=1 待 sanctioned-merge;engine:security 方向复用 optimization worktree）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【case-409=409%4=1≠0 非审计轮·sanctioned-merge】合并 opt-worktree auto-optimization @c4744bc(scaffold-skill.sh SKILL_NAME slug 白名单+TAGLINE JSON 转义)到 main。[2]【case-412=412%4=0 下次审计轮】继续审未审源码:scripts/scout-scan.py(677L 每轮扫描器,subprocess+文件读面)/scripts/opt-worktree.sh(718L git exec+cp 守卫,已部分自审 json_escape)/scripts/triage.py(136L)。
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
<!-- LAST_WORKTREE: auto-optimization @c4744bc（case-408 审计修复 pending=1 待 sanctioned-merge） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]case-409=409%4=1非审计轮 sanctioned-merge @c4744bc→main;[2]case-412 审计轮 续审 scout-scan.py/opt-worktree.sh/triage.py -->

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
