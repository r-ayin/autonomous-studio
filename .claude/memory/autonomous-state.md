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

- **最后活跃: 2026-07-01T17:22Z（DO A 强制审计轮 case-376=376%4=0=0。security-review pending optimization @9d97d2e(case-375 新写 _tokenize/_unwrap_once/_unwrap_indirect/_git_segments)——importlib 实测发现 3 类引号/壳绕过(均低危,需受护 agent 刻意构造,但比已记录 $(git...) 残留更自然):[f1] `A && eval "git commit"` 漏过(_unwrap_indirect 仅整命令剥层,段上 eval/sh -c 不展开→index(git) 失败;sh -c 同形);[f2] `eval "git commit" -m wip` 漏过(eval 分支限 len(rest)==1,真实 shell eval 拼接所有参数)。修复:_unwrap_once eval 分支 `len(rest)==1`→`rest` 非空即 `" ".join(rest)`(还原 eval 多参数拼接);_git_segments 拆段后逐段 _unwrap_indirect+递归(inner 再含链则 _git_segments 递归,幂等+8层上限终止)。case-104 路径直编 opt-wt+precommit 守卫静默通过+worktree 内 commit @0b322a9(1 file +25/-8)。回归 20 例:5 finding 全 CAUGHT+case-375 原覆盖 8 例仍 CAUGHT+非 git 7 例不误拦+py_compile OK。sanctioned-merge optimization→squash→main @de365a0+worktree 清理+删 auto/optimization 分支。main gate 行为回归 17 例 ALL PASS。audit-20260630-172215-a8f77f action=deploy newValue=de365a0 result=success LIVE。**部署态额外发现[f4 medium]**:LIVE gate /home/admin/.claude/hooks/autonomous-commit-gate.py 为旧版(cmd.split() 无 shlex/_tokenize/_unwrap/_git_segments/--git-dir repo_dir),case-372/373/375/376 全部硬化未上线!当前 marker .autonomous_active 从不被脚本创建→gate 休眠故暂不致害,但同步前须先 broaden is_case_metadata_only 兼容 state.md(免激活后阻断归档)。已排队 case-377 闭合。case-376 outcome=succeeded audit_type=security-review audit_findings=4(3 已修+1 部署态排队)。pending=0）**
- **活跃项目**: autonomous-studio-aone 维护——case-376 DO A 审计轮 security-review pending @9d97d2e 发现 3 类引号/壳绕过并修复+_git_segments 逐段递归剥壳,sanctioned-merge 入 main @de365a0;另揭 LIVE gate 旧版未同步(排队 case-377)
- **当前阶段**: 审计+修复+合并完成;pending=0（无待合并 worktree）;下轮 case-377=377%4=1≠0 非审计普通轮——优先同步 LIVE gate(cp 仓内 main 版→/home/admin/.claude/hooks/)+先 broaden is_case_metadata_only 兼容 state.md 豁免+py_compile+行为回归
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01
- **LAST_WORKTREE**: optimization @0b322a9（已 sanctioned-merge 入 main @de365a0 squash,worktree 清理,auto/optimization 分支删除;方向 audit(engine:gate-tokenizer+audit-fix),审计 @9d97d2e 发现 3 类绕过→@0b322a9 修复→main 取已修复版;1 file 累计 +73/-8 vs merge-base 0859ed4;case-376 outcome=succeeded audit_type=security-review audit_findings=4;main HEAD=de365a0 干净 pending=0）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【普通轮·case-377】377%4=1≠0 非审计。pending=0。优先同步 LIVE gate:/home/admin/.claude/hooks/autonomous-commit-gate.py 为旧版(cmd.split 无 shlex/_tokenize/_unwrap/_git_segments/--git-dir repo_dir),case-372/373/375/376 硬化未上线(见 case-376 audit_findings[3])。step:① 先 broaden is_case_metadata_only(或 CASE_FILE_RE)兼容 .claude/memory/autonomous-state.md 豁免(免 gate 激活后阻断归档环 case+state.md)——进 opt-worktree 审改项目 gate 1-2 行;② cp .claude/hooks/autonomous-commit-gate.py(main 已修复版)→ /home/admin/.claude/hooks/(仓外动作不进 worktree);③ py_compile + grep join(rest)/_git_segments/shlex 命中 + 行为回归 17 例;④ 验 marker 休眠态归档仍自由。[2]【下次审计轮 case-380=380%4=0=DO A 强制审计轮】须换审非 gate 目标(已连续 case-372/376 两轮审 gate)。候选:(a) scripts/scout-scan.py code-review(.codebase-index 大 JSON 只读面/subprocess);(b) scripts/opt-worktree.sh detect_main_branch/ensure_main_wt/cp-guard/_assert_no_collateral_revert 路径 logic;(c) codegraph-sync.py/route-health-scorer.py 外部文件读写。优先挑有源代码项目。[3]【gate 残留(低危,刻意构造)】(a) 3 级嵌套混合引号仍漏(_SHELL_OPS_RE 非 quote-aware);(b) $(git...)/反引号;(c) source/. 脚本内容;(d) --norc 长 -c 形态。
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
<!-- LAST_WORKTREE: optimization @0b322a9（已 sanctioned-merge 入 main @de365a0 squash,worktree 清理,auto/optimization 分支删除;方向 audit(engine:gate-tokenizer+audit-fix),审计 @9d97d2e 发现 3 类绕过→@0b322a9 修复→main 取已修复版;1 file 累计 +73/-8 vs merge-base 0859ed4;case-376 outcome=succeeded audit_type=security-review audit_findings=4;main HEAD=de365a0 干净 pending=0） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【普通轮·case-377】377%4=1≠0 非审计。pending=0。优先同步 LIVE gate:/home/admin/.claude/hooks/autonomous-commit-gate.py 为旧版(cmd.split 无 shlex/_tokenize/_unwrap/_git_segments/--git-dir repo_dir),case-372/373/375/376 硬化未上线(见 case-376 audit_findings[3])。step:① 先 broaden is_case_metadata_only(或 CASE_FILE_RE)兼容 .claude/memory/autonomous-state.md 豁免(免 gate 激活后阻断归档环 case+state.md)——进 opt-worktree 审改项目 gate 1-2 行;② cp .claude/hooks/autonomous-commit-gate.py(main 已修复版)→ /home/admin/.claude/hooks/(仓外动作不进 worktree);③ py_compile + grep join(rest)/_git_segments/shlex 命中 + 行为回归 17 例;④ 验 marker 休眠态归档仍自由。[2]【下次审计轮 case-380=380%4=0=DO A 强制审计轮】须换审非 gate 目标(已连续 case-372/376 两轮审 gate)。候选:(a) scripts/scout-scan.py code-review(.codebase-index 大 JSON 只读面/subprocess);(b) scripts/opt-worktree.sh detect_main_branch/ensure_main_wt/cp-guard/_assert_no_collateral_revert 路径 logic;(c) codegraph-sync.py/route-health-scorer.py 外部文件读写。优先挑有源代码项目。[3]【gate 残留(低危,刻意构造)】(a) 3 级嵌套混合引号仍漏(_SHELL_OPS_RE 非 quote-aware);(b) $(git...)/反引号;(c) source/. 脚本内容;(d) --norc 长 -c 形态。 -->

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
