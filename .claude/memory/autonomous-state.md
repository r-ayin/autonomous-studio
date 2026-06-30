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

- **最后活跃: 2026-06-30T04:51Z（scout:父级轮转 — #1 huiyis(score=2.0)等合并 opt-docs-1782793013 别重做 / #2 autonomous-studio(score=0.03 推幽灵 triage TODO) / #3 1BfrYn9G(review 2 待合并 worktree) 三者全 blocked 于 pending 人工 merge, 自治 gate 拦无法 merge。核实 AS #2 是幽灵: main working-tree TODO=4 = decision-archive.md:856/864/872 三条案例标题散文(pending opt-scanner-1782794236 IGNORE_DIRS +decisions 已修) + autonomous-state.md:17 未提交记忆散文(瞬态; 干净树验 pending fix 后 AS TODO=0), 无真代码债。遵 NEXT_SUGGESTION『全 blocked 顺延扫父级取真可自治 #1』: 逐项核验 skills/stagehand-analysis/x-tool/quanzhan/shizi active TODO=0(仅 deferred), 唯 agent-dashboard active TODO=1 且 0 待合并 worktree dirty=0 = 真·未阻塞 target。count_markers 定位 frontend/src/App.tsx:172 真 TODO 债(handleSendMessage 桩, 原注释拟 POST 后端消息 API)。核查后端 main.py:486 @sio.event agent_message→message_injector.inject 是 Socket.IO 非 REST, 无 /messages 路由; 前端已有 socketManager.sendMessage 单例(socketManager.ts:162, messageStore.ts:45 同款)。最小改 1 文件 2 处: import +socketManager / handleSendMessage 调 socketManager.sendMessage 清 TODO。area dashboard≠engine → opt-worktree 自动开新隔离 opt-dashboard-1782795095(e7982d2 +4/-2)。验 worktree TODO=0、main 干净。case-336。pending 人工 merge 仍是 #1-3 阻塞源）**
- **活跃项目**: 持续自治管线巡检——按 scout-scan 健康度排序轮转
- **当前阶段**: 父级多项目轮转巡检——AS 仓 scout 失明待人工 merge opt-scout，期间切 --workspace /home/admin/workspace 取真 #1 推进
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: opt-dashboard-1782795095 (e7982d2 — dashboard:message-send — agent-dashboard App.tsx:172 真 TODO 清债: handleSendMessage 桩接入 socketManager.sendMessage 单例(后端消息通道是 Socket.IO @sio.event agent_message 非 REST POST, 无 /messages 路由; socketManager.ts:162/messageStore.ts:45 同款); 1 文件 +4/-2 待人工 merge; worktree TODO=0、main 干净; 真·可自治#1 因父级#1-3全blocked于人工merge)
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: 【需人工·低阻力】(1) opt-worktree.sh /home/admin/workspace/agent-dashboard merge opt-dashboard-1782795095 落地 handleSendMessage Socket.IO 接入(1 文件 +4/-2 零冲突), merge 后 agent-dashboard active TODO=0 永久健康。(2) 仍 pending 人工 merge 阻塞源(自治 gate 拦无法 merge): huiyis/opt-docs-1782793013(3 文件 +102)、AS 仓 opt-scanner-1782794236(scanner 第5类虚高修复, merge 后 AS TODO=0 永久退出幽灵 #2)+opt-scout-1782792420(解引擎 0 项目失明)、1BfrYn9G 2 worktree、dingtalk-auto/kaoqin/pc_agent 各 1。(3) 下轮自治: 父级 #1-3 仍 blocked 则继续顺延——候选 browser-use(active TODO=32 疑第三方 vendored 噪声, 核实是否该加 IGNORE)/或各项目 deferred TODO 中可真解者(shizi deferred=1 最小); 若全无真债则本轮型 blocked-only 可写 case 存档等人工 merge 推进。
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
<!-- LAST_WORKTREE: agent-dashboard/opt-dashboard-1782795095 (e7982d2: dashboard:message-send — App.tsx:172 真 TODO 清债, handleSendMessage 接入 socketManager.sendMessage 单例; 后端消息通道是 Socket.IO(@sio.event agent_message→message_injector.inject)非 REST POST 无 /messages 路由; 1 文件 +4/-2 待人工 merge; worktree TODO=0 main 干净) -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【需人工·低阻力】opt-worktree.sh /home/admin/workspace/agent-dashboard merge opt-dashboard-1782795095 落地 handleSendMessage Socket.IO 接入(1 文件 +4/-2 零冲突)，merge 后 agent-dashboard active TODO=0 永久健康; [2] 仍 pending 人工 merge 阻塞源: huiyis/opt-docs-1782793013、AS 仓 opt-scanner-1782794236(merge 后 AS 退出幽灵 #2)+opt-scout-1782792420(解引擎失明)、1BfrYn9G 2 worktree、dingtalk-auto/kaoqin/pc_agent 各 1——自治 gate 拦无法 merge; [3] 下轮自治: 父级 #1-3 仍 blocked 继续顺延——候选 browser-use(active TODO=32 疑 vendored 噪声核实加 IGNORE)/shizi deferred=1 可真解; 全无真债则 blocked-only 存档等人工 merge -->

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
