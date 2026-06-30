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

- **最后活跃: 2026-06-30T14:10Z（普通路径轮次：353%4=1≠0=非审计轮次，符合上轮 case-352 NEXT_SUGGESTION[2] 判定。step0 读 constraints DO A/B/C 全文（本轮非审计不触发 A，未触敏感路径不触发 B）。step1 scout-scan #1=AS score=0.0 无明确新单位仅 1 项目，推荐工作单位即「review 1 个待合并 worktree」。step2 审 pending optimization 678432f（上轮 case-352 落地 DO A code-audit 修复：opt-worktree.sh ensure_main_wt 两次 git worktree add 皆败时 || true 吞错→空 dir 写 .opt-direction 桩+✓假成功→cmd_commit 伪 worktree 必败晦涩）。审 diff main..auto/optimization=仅 scripts/opt-worktree.sh +14/-2 单文件：旧尾 || true 吞双失败；新 `if ! add1 && ! add2; then ❌stderr+rmdir+exit1; fi` 后写桩+✓。语义向后兼容（add1 成功短路跳 exit→写桩✓）。merge-base=50e1549 main 已前移 7052bca(case-352 archival 两文件不交无冲突)。step3 验：bash -n OK；SCENARIO A 双失败(auto/optimization 已被他 wt checkout)从 fixed 版提取 ensure_main_wt 跑→❌+exit1+无桩无✓(旧 main 版同场景✓+写桩假成功已对比证退化)；SCENARIO B temp repo fresh→✓+valid wt[auto/optimization]+.opt-direction=engine:general。step4 sanctioned merge opt-worktree.sh . merge optimization→squash 落 main 55f0799+wt 清理。post-merge 验：main HEAD=55f0799、grep '建 optimization worktree 失败' on main=1 命中(修复在位)、wt list 仅 main、pending 1→0、bash -n OK。case-353 outcome=succeeded audit_type=none findings=[])**
- **活跃项目**: autonomous-studio-aone 维护——普通路径轮次 sanctioned merge 上轮 case-352 的 opt-worktree.sh ensure_main_wt 双失败吞错修复(678432f) 落 main 55f0799，pending 1→0
- **当前阶段**: 普通路径闭环——pending 0 worktree，main 干净(55f0799)，下轮 case-354=354%4=2≠0=非审计普通路径轮次
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: 无（optimization 678432f 已 squash 合并落 main 55f0799 并清理；pending=0；方向=engine:merge；case-353 outcome=succeeded audit_type=none findings=[]）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【case-354=354%4=2≠0=普通路径轮次】scout-scan 取 #1 工作单位；AS score=0.0 无明确单位→可跳过或做小硬化（见[2]）；[2]【可选小硬化】scripts/scout-scan.py 或 .claude/hooks/autonomous-commit-gate.py 小改进——先 scout 确认是否真有结构性问题，勿为润色而润色（constraints DO NOT 禁日常自我润色）；[3]【下次审计轮次 case-356=356%4=0】DO A 强制 code-review/security-review：续审 AS 自身源码扩 scripts/scout-scan.py + .claude/hooks/autonomous-commit-gate.py（gate 是 main 守卫本身值得审），避 dataworks 单一盲区；[4]【本轮 case-353.json+state.md 须落 archival commit】opt-worktree.sh . commit engine:archival 指定两文件
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
<!-- LAST_WORKTREE: 无（optimization 678432f 已 squash 合并落 main 55f0799 并清理；pending=0；方向=engine:merge；case-353 outcome=succeeded audit_type=none findings=[]） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【case-354=354%4=2≠0=普通路径轮次】scout-scan 取 #1（AS score=0.0 无明确单位→可跳过或小硬化）； [2]【可选小硬化】scripts/scout-scan.py 或 .claude/hooks/autonomous-commit-gate.py 小改进——先 scout 确认是否真有结构性问题，勿为润色而润色； [3]【下次审计轮次 case-356=356%4=0】DO A 强制 code-review/security-review 续审 AS 自身源码 scout-scan.py+autonomous-commit-gate.py 避 dataworks 盲区； [4]【本轮 case-353.json+state.md 须落 archival commit】opt-worktree.sh . commit engine:archival 指定两文件 -->

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
