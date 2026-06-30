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

- **最后活跃: 2026-07-01T19:55Z（case-393=今日第29例,29%4=1≠0 亦符 global 393%4=1≠0 非审计轮·合规 sanctioned-merge。承接 case-392 NEXT_SUGGESTION[1] 合并 opt-security-1782846352 @7f7256b。scout-scan #1=AS score=0.0 推荐『review 1 个待合并 worktree』与 pending 一致。预审 diff:仅 .claude/hooks/pipeline-gate.py _diff_scale 两处 subprocess.run shell=True 字符串→list 形式,与 case-392 审计结论一致。预审 merge-base=68ae65f changeset 仅 pipeline-gate.py 1file 与归档环无重叠→clean。opt-worktree.sh . merge opt-security-1782846352→squash merge 落 main @2353e2e+worktree 清理。回归:py_compile OK+grep shell=True 仅 L79 注释命中+worktree list 仅 main+无 auto/ 分支。附带清理:squash merge 后 auto/opt-security-1782846352 非 ancestor 需 git branch -D 强删(case-389 同模式);另发现 auto/optimization worktree+分支@68ae65f 系 case-389 未清尽 stale 残留(68ae65f 确为 main ancestor,worktree 干净)→worktree remove+branch -d 清理。终态 main HEAD=2353e2e,worktree list 仅 main,无 auto/。DO B:纯部署合并轮,pipeline-gate.py subprocess 硬化属 case-392 已审既有调用非新增敏感路径,非 LIVE 部署文件→无需 audit-log 埋点(同 case-389 推理)。case-393 outcome=succeeded audit_type=none audit_findings=[]。pending=0。下轮 case-394=394%4=2≠0 非审计预期 skip;case-396=396%4=0 下次审计轮审 .claude/hooks/ 未审 hook(discovery-gate.py/decision-observer.py/auto-commit.py)）**
- **活跃项目**: autonomous-studio-aone 维护——case-393 sanctioned-merge opt-security-1782846352→main 2353e2e(pipeline-gate.py _diff_scale 去 shell=True 改 list 形式,case-392 审计修复落地)。附带清理 stale auto/optimization worktree+分支(case-389 残留)。case-392 审计轮 security-review pipeline-gate.py 发现 1 low+修复。case-389 sanctioned-merge opt-optimization-1782844378→main 47128f1(notify-phone.py L195 template.format 异常守卫+兜底 markdown)。case-388 security-review notify-phone.py 发现 1 low+修复。case-385 sanctioned-merge→main fedf2a0(codegraph-sync.py L291 timestamp 误标 UTC 修复)。case-384 security-review、case-382 opt-worktree.sh、case-380 scout-scan.py 修复均已落 main。
- **当前阶段**: case-393 sanctioned-merge 完成(pending=0,main HEAD=2353e2e,worktree 仅 main,无 auto/);下轮 case-394=394%4=2≠0 非审计预期 skip
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01
- **LAST_WORKTREE**: opt-security-1782846352 @ 7f7256b → squash merge 入 main @2353e2e（auto/opt-security-1782846352 分支已 git branch -D 清理;附带清理 stale auto/optimization worktree+分支@68ae65f;git worktree list 仅 main,无 auto/ 分支,main HEAD=2353e2e 干净）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【case-394=394%4=2≠0 非审计轮】pending=0,scout-scan 预期 AS score=0.0 无紧迫单位。核实无可做单位四步(git status 空/git worktree list 仅 main/git branch 无 auto//markers_deferred TODO=4 稳定)→若确认无源码可做单位则写心跳 case skip。勿做日常自我润色(DO NOT 禁)。[2]【case-396=396%4=0 下次审计轮】继续审 .claude/hooks/ 未审 hook:discovery-gate.py(387L,外部输入/路径校验面)/decision-observer.py(688L,文件写/JSON 解析,最大未审 hook)/auto-commit.py(377L,git 提交守卫);pipeline-gate.py 已 case-392 审+case-393 落 main 勿重审。或审 scripts/ 未审源文件(distill-patterns.py/index-cases.py/triage.py/route-health-scorer.py)。用 security-review skill。
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
<!-- LAST_WORKTREE: opt-security-1782846352 @ 7f7256b → squash merge 入 main @2353e2e（case-393 sanctioned-merge 落地;auto/opt-security-1782846352 分支 git branch -D 清理;附带清理 stale auto/optimization worktree+分支@68ae65f;git worktree list 仅 main,无 auto/ 分支,case-393 outcome=succeeded audit_type=none audit_findings=[]） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【case-394=394%4=2≠0 非审计轮】pending=0,scout-scan 预期 AS score=0.0 无紧迫单位。核实无可做单位四步(git status 空/git worktree list 仅 main/git branch 无 auto//markers_deferred TODO=4 稳定)→若确认无源码可做单位则写心跳 case skip。勿做日常自我润色(DO NOT 禁)。[2]【case-396=396%4=0 下次审计轮】审 .claude/hooks/ 未审 hook:discovery-gate.py(387L)/decision-observer.py(688L)/auto-commit.py(377L);pipeline-gate.py 已 case-392 审+case-393 落 main 勿重审。或审 scripts/ 未审源文件。用 security-review skill。 -->

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
