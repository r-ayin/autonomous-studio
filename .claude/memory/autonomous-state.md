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

- **最后活跃: 2026-06-30T12:22Z（DO §A 审计轮次：今日 decisions 实际文件数=143，距上次审计 case-341(security-review)隔 342/343 两轮、距 case-340(code-review)隔 3 轮，符合「至少每 4 轮一次」→判定审计轮次。step0 读 autonomous-constraints.md DO A/B/C 全文。step1 scout #1=AS(score=0.0 TODO=0 active/deferred=4 全已triage)推荐'可跳过'，但 §A.1 审计轮次须从 #1 起选有源码项目。按上轮 NEXT_SUGGESTION 审 main HEAD 最近 3 commit(git log -3 --stat)：0ff6fcd 触 audit_log.py+83/bff_client.py+14(_do_request HTTP 出站埋点)正中 §B 敏感路径。code-review/security-review skill target pending-branch diff 而该代码已 merge 入 main、工作树干净→按 §A.2 fallback「也可审 main HEAD 最近 1-3 commit」手动 code-review(同方法论)。Read 2 源文件：bff_client 埋点(537-545)无发现(bypass 语义正确/失败 code=-1 仍审计/params_summary keys-only PII 脱敏)；audit_log.py 发现 F1——L22 strftime('%Y%m%d-%H%m%S') %m=月份(非 %M=分钟)致 ID 分钟位恒为月份数、与 schema id.description「HHmmss」不符、regex \\d{6} 静默匹配故长期未暴露。python3 复现：修前'20260630-200640'(06=月)/修后'20260630-202156'(21=真分钟)。F1 真正确性 bug→opt-worktree 修：'%H%m%S'→'%H%M%S' 1 行。验证 _audit_id()=audit-20260630-202156-f297ca re.match pattern=True、record() e2e success/failure 均落 JSONL 不抛。opt-worktree.sh . commit dataworks:audit-log→方向分歧(engine→dataworks)开新 worktree opt-dataworks-1782822148 commit 733a51b、main 干净。F2(L81 bare except pass 静默吞审计写失败)低危记 finding 不改避免 scope 蔓延。case-344 outcome=succeeded audit_type=code-review findings=2）**
- **活跃项目**: dataworks-dev-assistant 审计修复——opt-dataworks-1782822148(commit 733a51b, direction=dataworks:audit-log)修复 audit_log._audit_id strftime 分钟位 bug，待人工审合并
- **当前阶段**: 审计轮次闭环——发现并修复 audit_log.py:22 真正确性 bug(ID 分钟位恒为月份数)，pending 队列 0→1(opt-dataworks-1782822148 待 sanctioned merge)
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: opt-dataworks-1782822148(commit 733a51b, direction=dataworks:audit-log, base=main 75629c7)——DO §A 审计轮次 code-review 发现 audit_log.py:22 _audit_id strftime '%H%m%S'(月份)→'%H%M%S'(分钟)真正确性 bug，1 文件 1 行修复；待人工 sanctioned merge opt-worktree.sh . merge opt-dataworks-1782822148；main 干净(仅 ?? PROJECTS.md 未跟踪)
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【审计已闭环·下轮普通路径】今日 case 144,144%4=0=本轮审计;下案 case-345 落 145%4=1≠0=普通路径:scout #1 AS score=0.0'可跳过'、deferred TODO=4 全 blocked(apply_resource_access.py:85/90 Hologres/Lindorm 需真实表实测、bff_client.py:207 dist 兼容分支待人工裁决、scaffold-skill.sh:136 真实回放),DO NOT 禁自我润色→若仍无真工作单位记 skip case 不强造提交; [2] opt-dataworks-1782822148(本审计修复)待人工审合并:merge-base=main 75629c7 单文件单行 3-way 无冲突可 sanctioned squash-merge; [3] 下一审计轮次≈case-348(148%4=0):审 main HEAD 最近 commit(含本轮 merge 后 audit_log.py)+F2(audit_log L81 bare except 加最小 stderr 信号)
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
<!-- LAST_WORKTREE: opt-dataworks-1782822148(commit 733a51b, direction=dataworks:audit-log, base=main 75629c7)——DO §A 审计轮次 code-review 发现 audit_log.py:22 _audit_id strftime '%H%m%S'(月份)→'%H%M%S'(分钟)真正确性 bug,1 文件 1 行修复;待人工 sanctioned merge;main 干净(仅 ?? PROJECTS.md 未跟踪);case-344 outcome=succeeded audit_type=code-review findings=2 -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【审计已闭环·下轮普通路径】今日 case 144,144%4=0=本轮审计;下案 case-345 落 145%4=1≠0=普通路径:scout #1 AS score=0.0'可跳过'、deferred TODO=4 全 blocked,DO NOT 禁自我润色→若仍无真工作单位记 skip case; [2] opt-dataworks-1782822148(本审计修复)待人工审合并:单文件单行 3-way 无冲突可 sanctioned squash-merge; [3] 下一审计轮次≈case-348(148%4=0):审 main HEAD 最近 commit+F2(audit_log L81 bare except 加最小 stderr 信号) -->

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
