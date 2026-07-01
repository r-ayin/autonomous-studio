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

- **最后活跃: 2026-07-01T03:05:00Z（全量审计轮 case-489=今日第125例,audit-cycle-state status=idle 触发 DO A。承接 case-488 NEXT[3]。选未审 resume-checkpoint.py(214行,SessionStart hook 恢复读取端)做 security-review。发现 read_latest_checkpoint L31 TOCTOU 竞态读(os.path.exists→_read_json 非原子,save-checkpoint 写入瞬间可能读到半写文件+except 静默吞错用户无感丢失恢复指令)+memory_files L82 注入未转义(low deferred)+studio_context L144 except pass(info deferred)。修复:新增 _read_json_strict(raises),read_latest_checkpoint 直接 try read+区分 FileNotFoundError vs JSONDecodeError/OSError;损坏时 stderr 警告并降级扫描历史 checkpoint。py_compile OK+smoke test 通过。DO B 判定:.claude/checkpoints/ 非敏感路径不埋点。起 opt-security-1782873915 worktree(复用同 area)提交 1 commit bf46478(ahead=2 累计 save-checkpoint+resume-checkpoint 双修复)。merge-tree 干演 rc=0 clean。四验干净。case-489.json+state.md 直提 main(archival-commit-mechanism)。case-489 outcome=succeeded audit_type=security-review audit_findings=[1 medium 已修复并提交 opt-security-1782873915@bf46478, 1 low+1 info deferred]。下轮 case-490=490%4=2≠0 非审计轮·skip 心跳）**
- **活跃项目**: autonomous-studio-aone 维护——opt-security-1782866336@f7dda51(ahead=4 累计 case-464 audit-log+case-468 redaction+case-472 stop-gate-dash-arg+case-480 patterns-write-gate-normpath,4 commit 分属 4 不同文件无冲突,merge-tree --write-tree 干演 rc=0 clean merge 可行,待人工 squash merge)。**已审源码 26 处:.claude/hooks/ 14 hook(含 decision-observer.py case-468+stop-completion-gate.py case-472 1 low+patterns-write-gate.py case-480 1 medium+resume-checkpoint.py case-489 1 medium 已修复,均起 opt-security 待审)+codegraph-sync.py case-456+notify-phone/autonomous-commit-gate/pipeline-gate/post-edit-lint.py case-448+scaffold-skill.sh+opt-worktree.sh+scout-scan.py(case-380/049)+triage.py+bff_client.py(case-420 F3+case-436 F1 已合并 main@125a15e)+audit_log.py(case-424)+autonomous-commit-gate.py(case-428/440 已合并 main@051bb4b)+apply_resource_access.py(case-432 info deferred)+pipeline-gate.py(case-432/433 已合并 main)+notify-phone.py(case-444 已合并 main@9a8748e)+post-edit-lint.py(case-448)+scripts/route-health-scorer.py(case-452 无真问题)+codegraph-sync.py(case-456 无真问题)+discovery-gate.py(case-460 无真问题)+auto-commit.py(case-464 1 medium 已起 opt-security@ba52e9c 修复,case-465 审查确认可 merge 待人工)+decision-observer.py(case-468 1 medium redaction 缺口已起 opt-security@cf17a35 修复待审)+stop-completion-gate.py(case-472 1 low py_compile 缺 -- 分隔符已起 opt-security@5b5d956 修复待审)+patterns-write-gate.py(case-480 1 medium 路径归一化绕过已起 opt-security@f7dda51 修复待审)+resume-checkpoint.py(case-489 1 medium TOCTOU 竞态读已起 opt-security-1782873915@bf46478 修复待审)**。
- **当前阶段**: case-489 全量审计轮 security-review resume-checkpoint.py TOCTOU 竞态读修复完成(起 opt-security-1782873915@bf46478 ahead=2);下轮 case-490=490%4=2≠0 非审计轮·skip 心跳
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次事件驱动 audit-cycle-state + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01(case-489)
- **LAST_WORKTREE**: auto/opt-security-1782873915@bf46478(ahead=2,save-checkpoint+resume-checkpoint 双修复)。累计待人工 merge 3 分支 7 commit:auto/opt-security-1782866336@f7dda51(ahead=4)+auto/opt-security-1782872471@05a6c62(ahead=1,incremental-save.py)+auto/opt-security-1782873915@bf46478(ahead=2,save-checkpoint+resume-checkpoint);7 不同文件 merge-tree 干演均 rc=0 clean
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【人工 merge 待办,累计 3 分支 7 commit】用户手动 (a)git merge --squash auto/opt-security-1782866336 && git commit(4 commit 4 不同文件) (b)git merge --squash auto/opt-security-1782872471 && git commit(1 commit incremental-save.py) (c)git merge --squash auto/opt-security-1782873915 && git commit(2 commit save-checkpoint+resume-checkpoint 双修复);merge-tree 干演均 rc=0 clean;merge 后 cleanup 三分支。[2]【case-490=490%4=2≠0 非审计轮·skip 心跳】。[3]【下次全量审计候选】protocol-check.py(未审)/distill-patterns.py/index-cases.py 挑 1 做 security-review。[4]audit-cycle-state 仍 idle(本轮无派生 fix),可继续触发下一轮全量审计直到 hooks/ 全覆盖。
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
<!-- LAST_WORKTREE: auto/opt-security-1782873915@7b4189b(ahead=1,save-checkpoint.py 原子写修复)。累计待人工 merge 3 分支 6 commit:auto/opt-security-1782866336(ahead=4)+auto/opt-security-1782872471(ahead=1)+auto/opt-security-1782873915(ahead=1),6 不同文件 merge-tree 干演均 rc=0 clean -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]人工 (a)git merge --squash auto/opt-security-1782866336 && git commit(4 commit) (b)git merge --squash auto/opt-security-1782872471 && git commit(1 commit incremental-save.py) (c)git merge --squash auto/opt-security-1782873915 && git commit(1 commit save-checkpoint.py 原子写修复);均 rc=0 clean;merge 后 cleanup 三分支。[2]case-489=489%4=1≠0 非审计轮·skip 心跳。[3]case-492=492%4=0 审计轮·DO A 续审未审源码(resume-checkpoint/distill-patterns/index-cases 挑 1)。 -->

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
