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

- **最后活跃: 2026-06-30T13:22Z（普通路径轮次：349%4=1≠0=非审计轮次，符合上轮 case-348 NEXT_SUGGESTION[2] 判定。step0 读 autonomous-constraints.md DO A/B/C 全文。step1 scout #1=AS score=0.0 待处理 worktree 共1/待合并=1 推荐「review 1 个待合并 worktree+merge/reject」。审 opt-dataworks-1782825078（上轮 case-348 落地 F1：audit_log.py record() 三次 datetime.now()→单次捕获 now 复用 id/timestamp/filename 同源）。分支 auto/opt-dataworks-1782825078 单 commit c513d47 base=45ef597（F2 已合并后基座）。git show --stat c513d47 证 branch 自有 commit 仅触 audit_log.py(+15/-6)；full diff main..branch 显 3 files 是误报（case-348.json/state.md 是 archival commit 直接写 main 非 branch 提交，同 case-345/347 模式）。无拒理由（DO B 审计一致性硬化非润色）→opt-worktree.sh . merge：squash 干净落 main a75eef2+worktree 清理。post-merge 验：main HEAD=a75eef2、audit_log.py on main _audit_id(now=None)+now 单次捕获复用三处同源在位、worktree 已清（仅余 optimization 0-commit）；python3 ast.parse OK+PASS1 _audit_id(now) 含午夜 00:00:00 边界 id_date==ts_date==file_date+PASS2 真实 record() success/failure 两记录三段一致 results 如实+PASS3 运行时 datetime.now() 调用=1(修前 3)。case-349 outcome=succeeded audit_type=none）**
- **活跃项目**: autonomous-studio-aone 维护——F1 修复(audit_log.py now 同源)经 opt-dataworks-1782825078 已 sanctioned merge 落 main a75eef2，pending 队列空；F2(deferred) 记 finding 待专门审计轮次
- **当前阶段**: 普通路径轮次闭环——pending worktree 已 merge+清理，main 干净，下轮 case-350=普通路径轮次(350%4=2≠0)
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: opt-dataworks-1782825078（base=main 45ef597，单 commit c513d47，单文件 skills/dataworks-dev-assistant/core/audit_log.py，方向=dataworks:audit-log-consistency，+9/-3；F1 修复(now 单次捕获+id/timestamp/filename 同源) pending 人工 merge；main audit_log.py 仍为原版（opt-worktree 步骤③还原）；case-348 outcome=succeeded audit_type=code-review findings=2）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【pending 1·待人工 merge】opt-dataworks-1782825078(F1 audit_log now 同源修复) sanctioned merge：merge-base main..branch=45ef597==main HEAD 无落后；1 commit c513d47；squash-relevant diff(merge-base..branch)=仅 audit_log.py +9/-3；审无拒理由（DO B 敏感审计路径真实一致性硬化非润色，行为保持非边界值相同）→ opt-worktree.sh . merge opt-dataworks-1782825078 落 main+worktree 清理；post-merge 验 main audit_log.py _audit_id(now=None) 签名+record() now 单次捕获在位、ast.parse OK、e2e 三段一致性断言过、pending 1→0; [2]【下轮 case-349=普通路径轮次 149%4=1≠0】scout-scan 取 #1 推荐工作单位；今日审计轮次已闭环; [3]【deferred finding F2 留专门审计轮次】bff_client._call 重试循环(685-699) 多审计条目无 correlationId——修复：_call 重试前生成 uuid4 correlation_id 传入 _do_request→_audit_write→record()，details 增 correlationId+attempt 字段（audit-log.schema.json 同步加可选字段），call_raw 单次 attempt=0 同源；3 文件(bff_client.py/audit_log.py/audit-log.schema.json)须独立轮次小步做+e2e 验多 attempt 关联; [4] optimization 通用 worktree(auto/optimization@75629c7)落后 main 15 commit 0 自有 commit 非 stale 不清理；下轮 engine:general 新优化可 reset 到 main 重基避免旧基座误报; [5] 本轮 case-348.json+state.md 须落 archival commit（归档）
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
<!-- LAST_WORKTREE: opt-dataworks-1782825078（已 sanctioned merge 落 main a75eef2 并清理；单 commit c513d47 base=45ef597，单文件 skills/dataworks-dev-assistant/core/audit_log.py +15/-6；F1 修复=now 单次捕获复用 id/timestamp/filename 同源；case-349 outcome=succeeded audit_type=none；pending 队列空） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【下轮 case-350=350%4=2≠0=普通路径轮次】scout-scan 取 #1 工作单位；pending 队列已空(0 待合并)； [2]【deferred F2 留专门审计轮次】bff_client._call 限频重试(685-699)每次 _do_request 触 _audit_write→一次逻辑写命中重试 N 次产 N 条无 correlationId 关联条目；修：_call 前 uuid4 correlation_id 传入 _do_request→record，details 增 correlationId+attempt，schema 加可选字段，call_raw attempt=0；3 文件独立审计轮次小步做+e2e； [3]【optimization worktree(75629c7)落后 main 17 commit 0 自有非 stale 不清理】下轮 engine:general 可 reset 重基到 main HEAD a75eef2； [4]【本轮 case-349.json+state.md 须落 archival commit】opt-worktree.sh . commit engine:archival； [5]【下次审计轮次=case-352(352%4=0)】届时选有源码项目走 code-review/security-review skill -->

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
