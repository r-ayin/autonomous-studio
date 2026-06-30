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

- **最后活跃: 2026-06-30T15:55Z（DO A 强制审计轮次：364%4=0=0=审计。承接 case-363 NEXT_SUGGESTION[1] 审 opt-worktree.sh cmd_merge。step0 读 constraints DO NOT+DO 全文（本轮 DO A 强制审计；DO B 敏感路径埋点——改 cmd_merge 合并/冲突路径触发）。step1 scout-scan 文本报告 #1=autonomous-studio-aone score=0.0 无明确小工作单位（日常润色被 DO NOT 排除）但本项目有源码按 DO A 审源码。step2 焦点审计 cmd_merge（读 opt-worktree.sh 2 段不超 2 源文件限额）。step3 实测复现真缺口：temp repo git merge --squash side→CONFLICT+Squash commit not updating HEAD exit 1，index 留 UU f.txt 且 .git/MERGE_HEAD 不存在（squash 不记录 merge）；git merge --abort→fatal: There is no merge to abort (MERGE_HEAD missing) exit 128 被 || true 吞=状态不变 UU 残留=no-op 确认（case-361 真缺口复现）；git reset --merge exit 0 干净清理=正确 abort。step4 修复 1 文件 scripts/opt-worktree.sh +27/-2：(a) line-520 abort 加 fallback git merge --abort || git reset -q --merge 真正回滚 $PROJECT 至干净 main；(b) 消息更正冲突在 $PROJECT 非 $dir；(c) DO B 埋点新增 audit_log() bash 函数 append-only 写 $PROJECT/.audit/audit-YYYY-MM-DD.jsonl（.audit/ 已 gitignore 不污染 main）schema 对齐 audit-log.schema.json，在 commit 成功(result=success+newValue=sha)+冲突失败(result=failure)两处调用 result 如实不恒 success。step5 验证 bash -n SYNTAX OK + audit_log 功能测试 jq 校验两条 JSONL 必填字段齐备 id 模式 audit-20260630-155245-dd176a 匹配 + success/failure 双路径 result 如实。step6 提交 opt-worktree.sh . commit audit:opt-worktree-merge→新 worktree opt-audit-1782834799 @6d74b77（方向分歧 engine→audit 自动开新 wt）diffstat 1 文件 +27/-2 fix 行落地确认 audit_log()@37/success@533/failure@543/reset --merge@545。main status 空=干净 fix 隔离 worktree 不入 main HEAD=3aac635。gate 熄火（.autonomous_active marker 不存在同 case-361/362/363）故 archival 直提 main。case-364 outcome=succeeded audit_type=code-review findings=2 files_changed=[scripts/opt-worktree.sh] work_unit=code-audit:autonomous-studio-aone。main HEAD=3aac635 干净 pending=opt-audit-1782834799 @6d74b77 待 case-365 sanctioned-merge。下轮 case-365=365%4=1≠0 非审计普通路径 sanctioned-merge opt-audit-1782834799）**
- **活跃项目**: autonomous-studio-aone 维护——case-364 DO A 审计+修复 opt-worktree.sh cmd_merge squash 冲突 abort no-op（+27/-2 入 worktree opt-audit-1782834799 @6d74b77 待合），main HEAD=3aac635 干净 pending=opt-audit-1782834799
- **当前阶段**: DO A 审计完成，cmd_merge abort 修复+DO B audit-log 埋点已入 worktree opt-audit-1782834799 @6d74b77 待合；下轮 case-365=365%4=1≠0 非审计 sanctioned-merge（本轮新 abort+audit_log 路径首次实跑验证）
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: opt-audit-1782834799 @6d74b77（auto/opt-audit-1782834799，方向 audit:opt-worktree-merge，1 文件 scripts/opt-worktree.sh +27/-2；case-364 outcome=succeeded audit_type=code-review findings=2；pending 待 case-365 sanctioned-merge；main HEAD=3aac635 干净）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【sanctioned-merge·case-365】365%4=1≠0 非审计普通路径。merge opt-audit-1782834799 @6d74b77 入 main（1 文件 +27/-2 纯 opt-worktree.sh 无 case/state 回退）。差异预审 merge-base(main,6d74b77)=3aac635 diff 3aac635..6d74b77 仅 scripts/opt-worktree.sh +27/-2 无重叠。运行 opt-worktree.sh . merge opt-audit-1782834799→本轮新 abort+audit_log 路径首次实跑（成功路径触发 audit_log success 写 .audit/audit-2026-06-30.jsonl）；[2]【审计延后·case-368】368%4=0=DO A 再审 cmd_reject/cmd_cleanup 的 worktree remove+branch -D 路径（删除/批量操作敏感路径 DO B 触发但未埋点——audit_log 目前只盖 cmd_merge，reject/cleanup 删 worktree+分支无审计）；[3]【worktree 卫生·低危延后】main 外残留 optimization worktree @7d41e33 [auto/optimization]（clean 落后 main 2 commit，case-361/363 均声称清理但实际残留）+opt-audit-1782834799 pending——下轮 merge 后 git worktree remove + branch -D 收尾
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
<!-- LAST_WORKTREE: opt-scout-scan-1782833675 @5695a05（已合并入 main c15672f 并清理 worktree+branch；方向 scout-scan:polyglot +4 行 1 文件 scripts/scout-scan.py；case-363 outcome=succeeded audit_type=none findings=[]；main HEAD=c15672f 干净 pending=0） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【审计盲区轮换·case-364】364%4=0=DO A 强制审计换审 scripts/opt-worktree.sh cmd_merge（squash 无 MERGE_HEAD 致 merge --abort no-op 真缺口，可审+补 resume 分支，属敏感路径 subprocess/git exec）； [2]【审计备选·case-364】审 scout-scan.py 索引 FS 写敏感性（.codebase-index/ 写入、路径拼接注入）； [3]【worktree 卫生·低危延后】main 外残留 optimization worktree @7d41e33 [auto/optimization]（clean 落后 main 2 commit，case-361 声称清理但实际残留，下轮 worktree remove + branch -D 收尾） -->

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
