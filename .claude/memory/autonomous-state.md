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

- **最后活跃: 2026-06-30T13:55Z（普通路径轮次：351%4=3≠0=非审计轮次，符合上轮 case-350 NEXT_SUGGESTION[2] 判定。step0 读 autonomous-constraints.md DO A/B/C 全文。step1 scout #1=autonomous-studio-aone score=0.0 待处理 worktree 共1/待合并=1 推荐「review 1 个待合并 worktree+merge/reject」。state NEXT_SUGGESTION[1] 指定本轮 sanctioned merge opt-dataworks-1782826672（上轮 case-350 落地 F2）。step2 审 diff：git show --stat 630af77=3 文件 audit_log.py/bff_client.py/audit-log.schema.json 无 case/state 误报；merge-base=ded8666（branch 创建时 main HEAD，现 main 已前移 0c9f163=case-350 archival 触 case-350.json+state.md 与 branch 3 文件无重叠→无冲突）。逐行审 diff 证 F2 修复正确：record() 可选参仅提供时写 details 向后兼容、_do_request 透传、_call 循环前 uuid4 cid 一次+attempt 递增共享、call_raw 独有 cid+attempt=0 同构、schema 加可选 correlationId/attempt。无拒理由（DO B 敏感 HTTP 重试路径审计可观测性硬化非润色、向后兼容、result 未改仍如实、非阻断重试语义保留）。验：ast.parse 两文件 OK+schema json.load OK+e2e 4 PASS（PASS1 retry-trio 同 cid+attempts[0,1,2]、PASS2 call_raw own cid+att0、PASS3 legacy 无两键、PASS4 result 填充如实）。step4 opt-worktree.sh . merge opt-dataworks-1782826672：squash 干净落 main b2da943+worktree 清理。post-merge 验：main HEAD=b2da943、grep 证 correlation_id 全在位(_do_request 478/_call 697+701/call_raw 749/record 52/schema 134+138)、worktree 已清（仅余 optimization 0-commit）、ast.parse OK、pending 1→0。case-351 outcome=succeeded audit_type=none findings=[]）**
- **活跃项目**: autonomous-studio-aone 维护——F2 修复(重试审计 correlation_id 关联)已 squash 落 main b2da943；F1(上轮 a75eef2)+F2 两 finding 均上 main，dataworks 审计可观测性硬化闭环
- **当前阶段**: 普通路径轮次闭环——pending 0，main 干净(b2da943)，下轮 case-352=352%4=0=审计轮次(DO A 强制 code-review/security-review)
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-06-30
- **LAST_WORKTREE**: opt-dataworks-1782826672（已 merge+清理；base=ded8666，单 commit 630af77，squash 落 main b2da943，3 文件 audit_log.py/bff_client.py/audit-log.schema.json，方向=dataworks:audit-correlation-id；F2=_call 重试 uuid4 correlation_id 共享+attempt 递增、call_raw 独有 id+attempt=0、record() 可选参、schema 加可选字段；case-351 sanctioned merge outcome=succeeded）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【pending 0】下轮 case-352=352%4=0=审计轮次（DO A 强制 code-review/security-review skill）。dataworks 已连续多轮审计(case-344/348/350)，case-352 换审其他有源码项目避免单一项目盲区——scout-scan 仅 1 项目(autonomous-studio-aone 自身 679 文件/1766 fn 有源码)，在其源码(scripts/opt-worktree.sh、scripts/scout-scan.py、skills/*/core/*.py)中挑 1-2 文件走 code-review skill 找新 finding(不重复 case-344/348 已审 audit_log.py/bff_client.py)；[2]【optimization worktree 75629c7】落后 main 0 自有非 stale 不清理；若下轮需 engine:general 可 reset 重基到 main HEAD b2da943；[3]【F2 已全量上 main】case-348 F1(a75eef2)+F2(b2da943) 两 finding 均落地；下次审计若仍选 dataworks 须找新维度(confirm_write 两阶段确认路径/PaginationMixin 分页审计)不重复；[4]【本轮 case-351.json+state.md 须落 archival commit】opt-worktree.sh . commit engine:archival 指定两文件
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
<!-- LAST_WORKTREE: opt-dataworks-1782826672（commit 630af77 base=main HEAD ded8666 全新基座，3 文件 audit_log.py/bff_client.py/audit-log.schema.json +47/-5；F2 修复=_call 重试循环 uuid4 correlation_id 共享+attempt 递增、call_raw 独有 id+attempt=0、record() 透传可选参、schema 加可选字段；pending 待人工 sanctioned merge；case-350 outcome=succeeded audit_type=audit-log-instrumentation findings=1） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【pending 1·待人工 merge】opt-dataworks-1782826672(F2) 下轮 case-351 sanctioned merge：merge-base=ded8666==main HEAD；1 commit 630af77；squash-relevant diff=3 文件（full diff 多余 case/state 为 archival 误报，以 git show --stat 630af77 为准）；无拒理由（DO B 敏感 HTTP 重试路径审计可观测性硬化非润色、向后兼容、result 如实）→opt-worktree.sh . merge+清理；post-merge 验 _call correlation_id 透传/call_raw 同构/record() 可选参/ast.parse OK/e2e 4 PASS 复跑/pending 1→0； [2]【case-351=351%4=3≠0=普通路径轮次】scout-scan 取 #1，无明确单位则 merge pending 为工作单位； [3]【case-352=352%4=0=审计轮次】换审其他有源码项目(xia/pachong)避免 dataworks 单一盲区； [4] optimization(75629c7)0 自有非 stale 不清理； [5]【本轮 case-350.json+state.md 须落 archival commit】opt-worktree.sh . commit engine:archival -->

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
