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

- **最后活跃: 2026-06-30T14:28Z（审计轮次：356%4=0=DO A 强制 code-review，符合上轮 case-355 NEXT_SUGGESTION[2] 判定。step0 读 constraints DO A/B/C 全文（本轮触发 A 审计；opt-worktree.sh 非敏感路径不触发 B audit-log 埋点——与 case-352 同判定「引擎内部plumbing硬化非敏感操作」）。step1 `python3 scout-scan.py --workspace .` #1=autonomous-studio-aone score=0.0（有源码项目✓，符合 DO A.1 跳过纯文档/配置要求）。DO A.2 按 case-354/355 连续 NEXT_SUGGESTION 续审 scripts/opt-worktree.sh cmd_commit（line 209-430，git/subprocess/FS 编排敏感 plumbing）。逐行审计定位 1 真问题：cmd_commit 方向分歧分支（cur_area!=new_area 无同 area wt 可复用）line 231 `git worktree add -b auto/opt-<area>-<ts>` 建新分歧 wt+分支发生在 line 315 cp 循环前；若全文件 cp-guard 跳过/不存在→copied=0→line 355 exit 1 旧版不回滚→孤儿 wt+分支残留污染 git worktree list/scout-scan（case-353 残留 wt 漂移根因的分歧-wt 面；optimization 持久 wt 面由 ensure_main_wt 建、cmd_cleanup 可收，分歧 wt 无自动回收）。最小改 1 文件 scripts/opt-worktree.sh +17/-1：加 created_new_wt/new_wt_branch 跟踪 + copied=0 bail 块 worktree remove --force+branch -D 回滚（仅清本调用新建者，不动复用/optimization 持久 wt）。验证 bash -n OK + /tmp 复现场景（分歧方向+bogus 文件→copied=0）实跑证实 `Deleted branch auto/opt-data-1782829821`+wt 移除+worktree list 复净✓。提交 `opt-worktree.sh . commit engine:audit` → optimization worktree commit 7c6196b（stack 于 case-355 .gitignore fix 9036e71 之上，同 area 复用 wt，cp-guard 通过）。main HEAD 未动（4dde0e4）。case-356 outcome=succeeded audit_type=code-review audit_findings=2[medium 已修+low 延后] files_changed=[scripts/opt-worktree.sh]）**
- **活跃项目**: autonomous-studio-aone 维护——审计轮次 code-review opt-worktree.sh cmd_commit，修复 copied=0 bail 路径分歧 wt 孤儿 leak，optimization worktree 7c6196b（+9036e71）待 sanctioned merge，pending=1
- **当前阶段**: 审计轮闭环——optimization worktree @7c6196b（2 commits ahead：audit fix + .gitignore hygiene）待 sanctioned merge，main 干净(4dde0e4 HEAD 未动，仍显 ?? PROJECTS.md 待 merge 后消除)，下轮 case-357=357%4=3≠0=非审计普通路径
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: optimization（auto/optimization @ 7c6196b，2 commits ahead of main 4dde0e4：7c6196b audit fix opt-worktree.sh +17/-1 + 9036e71 .gitignore +2，方向=engine:audit，待人工 sanctioned merge；case+state 按 [[archival-commit-mechanism]] 直提 main；case-356 outcome=succeeded audit_type=code-review findings=2）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【sanctioned merge 待办】optimization worktree @7c6196b 现 2 commits ahead（7c6196b audit fix + 9036e71 .gitignore）待人工审合并落 main——`bash scripts/opt-worktree.sh . merge`：审 diff（opt-worktree.sh +17/-1 纯 bail 路径回滚无敏感路径 + .gitignore +2）→ squash 落 main → worktree 清理；merge 后 main `git status` 不再显 ?? PROJECTS.md；[2]【次级发现·延后】`git branch` 残留 5 个 pre-fix 孤儿分支 auto/opt-dataworks-*（1782819568/2148/3706/5078/6672，无 linked worktree=本次修复所防 leak 的历史遗留物）。属 DO B 删除/批量操作敏感类，本轮不批量删；下轮可逐个 `git branch -D` 或扩 cmd_cleanup(line523-549) 覆盖无 wt 的 auto/opt-* 孤儿分支；[3]【case-357=357%4=3≠0=非审计普通路径】scout-scan 驱动选 #1 小工作单位，或先 merge 上轮 2 commits 再续；[4]【审计盲区轮换】case-352 审 ensure_main_wt、case-356 审 cmd_commit bail 路径——下个审计轮 case-360=360%4=0 换审 .claude/hooks/autonomous-commit-gate.py（main 守卫本身）或 scripts/scout-scan.py 标记计数/排除逻辑避单文件连续审盲区
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
<!-- LAST_WORKTREE: optimization（auto/optimization @ 7c6196b，2 commits ahead of main 4dde0e4：7c6196b audit fix opt-worktree.sh +17/-1 + 9036e71 .gitignore +2，方向=engine:audit，待人工 sanctioned merge；case-356 outcome=succeeded audit_type=code-review findings=2） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【sanctioned merge 待办】optimization @7c6196b（2 commits: audit fix + .gitignore）待 `opt-worktree.sh . merge` 审 diff squash 落 main + 清理； [2]【次级发现·延后】5 个 pre-fix 孤儿分支 auto/opt-dataworks-*（无 linked wt=本次修复所防 leak 历史遗留，DO B 删除/批量敏感本轮不删，下轮逐个 branch -D 或扩 cmd_cleanup）； [3]【case-357=357%4=3≠0=非审计普通路径】scout-scan 选 #1 小工作单位或先 merge； [4]【审计盲区轮换】case-360 换审 autonomous-commit-gate.py/scout-scan.py -->

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
