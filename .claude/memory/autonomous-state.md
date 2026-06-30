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

- **最后活跃: 2026-06-30T14:22Z（普通路径轮次：355%4=3≠0=非审计轮次，符合上轮 case-354 NEXT_SUGGESTION[1] 判定。step0 读 constraints DO A/B/C 全文（本轮非审计不触发 A；改 .gitignore 非敏感路径不触发 B）。step1 `python3 scout-scan.py --workspace .` #1=AS score=0.0 无明确新单位（延期 triage TODO=4 不计推荐）。step2 不接受「无单位即跳过」亦不为润色而润色（DO NOT 禁日常自我润色），核 git 实态找真结构性问题：`git status` 持续 `?? PROJECTS.md`——追溯 scout-scan.py:593 每 full scan 调 write_projects_md(line564 写 workspace 根) 生成 PROJECTS.md，frontmatter 自述「由 scout-scan.py 自动刷新」=生成物，`git log`/`git ls-files` 均空=从未 tracked，但 .gitignore 未排除→引擎 step1 每轮污染 main 工作树留 untracked 生成文件（扫描器污染其扫描树+可能被 commit-gate WIP 误扫）=AS 自身真结构性卫生缺陷。最小改 1 文件：.gitignore 在 .codebase-index/ 后追加 PROJECTS.md（生成物归位运行时状态段，不删已存在文件、不触 scout-scan.py 源码）。验证 git check-ignore PROJECTS.md→IGNORED ✓ + git status 仅 ` M .gitignore`。`opt-worktree.sh . commit engine:hygiene` → optimization worktree commit 9036e71（.gitignore +2/-0，1 file 2 insertions）。main HEAD 未动(d0e6776)，fix 存 optimization 待 sanctioned merge（合并前 main 仍显 ?? PROJECTS.md 符合预期）。case-355 outcome=succeeded audit_type=none findings=[] files_changed=[.gitignore]）**
- **活跃项目**: autonomous-studio-aone 维护——普通路径轮次修 gitignore 排除 scout-scan 生成物 PROJECTS.md（每轮 main 工作树卫生），optimization worktree 9036e71 待 sanctioned merge，pending=1
- **当前阶段**: 普通路径闭环——optimization worktree 9036e71（.gitignore +2）待 sanctioned merge，main 干净(d0e6776 HEAD 未动，仍显 ?? PROJECTS.md 待 merge 后消除)，下轮 case-356=356%4=0=审计轮次
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: optimization（auto/optimization @ 9036e71，1 commit ahead of main d0e6776，diff=.gitignore +2/-0，方向=engine:hygiene，待人工 sanctioned merge；case+state 按 [[archival-commit-mechanism]] 直提 main；case-355 outcome=succeeded audit_type=none findings=[]）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【sanctioned merge 待办】optimization worktree 9036e71（.gitignore +2 忽略 PROJECTS.md）待人工审合并落 main；下轮可先 merge 再续——`bash scripts/opt-worktree.sh . merge`：审 diff（2 行纯 .gitignore 追加，无源码/无敏感路径）→ squash 落 main → worktree 清理；merge 后 main `git status` 将不再有 ?? PROJECTS.md；[2]【case-356=356%4=0=下次审计轮次】DO A 强制 code-review/security-review：续审 opt-worktree.sh cmd_commit(line209-430)——case-354 已指 latent 残留漏洞 line212 ensure_main_wt（副作用建 wt）先于 line315 cp 循环，全文件被 cp-guard 跳过则 copied=0 exit1(line352) 但已建空 wt 不清（case-353 死桩根因），审计评估 copied=0 exit 分支补 cleanup 或前置 ensure_main_wt 时机，敏感 plumbing 须由审计轮正式审；或换审 .claude/hooks/autonomous-commit-gate.py+scripts/scout-scan.py 避单文件连续审盲区（scout-scan.py 本轮已浅触未改源码，下轮可正式 code-review 其标记计数/排除逻辑）；[3]【本轮 case-355.json+state.md 须落 archival commit】按 [[archival-commit-mechanism]] 直提 main 指定两文件（不走 opt-worktree——cp-guard 跳 state.md）；.gitignore fix 已在 optimization worktree 9036e71，勿与 archival 混入同一 opt-worktree commit
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
<!-- LAST_WORKTREE: optimization（auto/optimization @ 9036e71，1 commit ahead of main d0e6776，diff=.gitignore +2/-0，方向=engine:hygiene，待人工 sanctioned merge；case-355 outcome=succeeded audit_type=none findings=[]） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【sanctioned merge 待办】optimization 9036e71（.gitignore +2 忽略 scout-scan 生成物 PROJECTS.md）待人工审合并落 main——`opt-worktree.sh . merge` 审 diff（2 行纯 .gitignore 无源码无敏感路径）→ squash 落 main → worktree 清理；merge 后 main 不再显 ?? PROJECTS.md； [2]【case-356=356%4=0=审计轮次】DO A 强制 code-review/security-review 续审 opt-worktree.sh cmd_commit(line209-430) latent 残留漏洞（line212 ensure_main_wt 副作用建 wt 先于 line315 cp 循环，copied=0 exit1 line352 时空 wt 不清=case-353 死桩根因）或换审 autonomous-commit-gate.py+scout-scan.py 避单文件连续审盲区； [3]【本轮 case-355.json+state.md 须落 archival commit】按 [[archival-commit-mechanism]] 直提 main 指定两文件（不走 opt-worktree cp-guard 跳 state.md）；.gitignore fix 已在 optimization 9036e71 勿混入 -->

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
