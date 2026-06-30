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

- **最后活跃: 2026-06-30T17:58Z（普通轮 case-378=378%4=2≠0 非审计(DO A 不触发)。scout-scan #1 AS score=0.0 无紧迫单位(纪律:不做无意义自我润色)。闭合 case-376 NEXT_SUGGESTION[3]/state 已列 $(git...)/反引号命令替换绕过——非真 shell parser,靶向提取。1 file(.claude/hooks/autonomous-commit-gate.py)+85/-2 经 opt-worktree→optimization @ff5b16b pending sanctioned-merge(未上线 LIVE)。改动:(1) +_cmd_substitutions(cmd) 手动扫描配对括号(嵌套)+引号感知提取 $(...) 与反引号内层命令串——单引号串不展开整段跳过免 FP,双引号内仍展开对齐 shell 语义,$((算术))/$(< file) 进程替换跳过;(2) main() 段循环未命中后追加 _cmd_substitutions(cmd) 内层递归送 _git_segments+_eval_segment(段循环已命中则跳过免重复 audit);(3) _git_segments docstring 残留清单移除 $(...)/反引号(已闭合)仅余 source/. 脚本/--norc 长 -c。残留深嵌套 $(... $(...))/反引号内嵌反引号(需真 shell parser,刻意构造低危,维持 case-376 边界)。回归 importlib 30 例(23 检测+7 单元)ALL PASS+e2e 12 例(marker 激活 main:$(git commit)/$(git push origin main)/反引号/$(git reset --hard)/$(git merge main)/bare commit 全 BLOCK,$(git rev-parse)/$(git status)/反引号 git log/单引号 $(git push)/$((算术))/checkout 全 ALLOW)+py_compile OK。DO B 敏感路径 permission 变更:既有 _audit_log_block(line385)覆盖新捕获点 result=denied 如实,无需新增埋点——验证 denied 条目落 .audit/audit-2026-06-30.jsonl audit-20260630-175536-itd2ws(r=$(git reset --hard))+h91qji(m=$(git merge main))。marker 测试后已删→gate 休眠。case-378 outcome=succeeded audit_type=audit-log-instrumentation audit_findings=2(audit 覆盖验证 low+绕过闭合凭证 low)。pending=1(optimization @ff5b16b 待 case-379 sanctioned-merge+LIVE cp)。main HEAD=036ba4d 干净）**
- **活跃项目**: autonomous-studio-aone 维护——case-378 闭合命令替换 $(...)/反引号绕过(靶向提取非真 parser)。optimization @ff5b16b pending sanctioned-merge(LIVE 未同步,下轮 case-379 合并+cp)。case-372/373/375/376/377 已上线 LIVE;case-378 待上线。
- **当前阶段**: 修复完成 pending merge;pending=1（optimization @ff5b16b 待 sanctioned-merge→main+cp LIVE）;下轮 case-379=379%4=3≠0 非审计普通轮——sanctioned-merge @ff5b16b+cp LIVE+LIVE 30/e2e 回归;case-380=380%4=0 DO A 强制审计轮须换审非 gate 目标
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01
- **LAST_WORKTREE**: optimization @ff5b16b（pending sanctioned-merge;方向 engine:gate-cmd-subst;1 file +85/-2;case-378 outcome=succeeded audit_type=audit-log-instrumentation audit_findings=2;LIVE 未同步——下轮 case-379 cp;main HEAD=036ba4d 干净 pending=1）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【普通轮·case-379】379%4=3≠0 非审计。sanctioned-merge optimization @ff5b16b→main(opt-worktree.sh . merge optimization)+cp 同步 LIVE /home/admin/.claude/hooks/autonomous-commit-gate.py(case-377 流程)。merge 后校验:LIVE diff main==LIVE IDENTICAL+LIVE importlib 30 例+e2e 12 例回归(主要验 $(git commit)/$(git push origin main) BLOCK)。pending→0。[2]【下次审计轮·case-380=380%4=0=DO A 强制审计轮】须换审非 gate 目标(已连续 case-372/376/377/378 四轮触 gate)。候选:(a) scripts/scout-scan.py code-review(subprocess 调用面/_MARKER_RE/_DEFERRED_RE 正则虚高历史/索引只读大 JSON 面);(b) scripts/opt-worktree.sh security-review(detect_main_branch/ensure_main_wt/cp-guard/_assert_no_collateral_revert/audit_log json_escape 路径 logic);(c) codegraph-sync.py/route-health-scorer.py 外部文件读写。优先挑有源代码项目。[3]【gate 残留(低危,刻意构造)】深嵌套 $(... $(...))/反引号内嵌反引号(需真 shell parser);source/. 脚本文件内容;--norc 长 -c 形态——case-376 已判定不值得引入 parser,维持文档边界。
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
<!-- LAST_WORKTREE: optimization @e4fdfd0（已 sanctioned-merge squash 入 main @ac78f92,worktree 清理,auto/optimization 残留分支删除;方向 engine:gate-state-exempt;1 file +46/-4;case-377 outcome=succeeded audit_type=audit-log-instrumentation audit_findings=2;LIVE gate 已 cp 同步 diff IDENTICAL;main HEAD=ac78f92 干净 pending=0） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【普通轮·case-378】378%4=2≠0 非审计。pending=0。LIVE gate 已同步,case-372/373/375/376/377 全部硬化上线。可挑:(a) scout-scan #1 AS score=0.0 无紧迫单位——可跳过或做文档润色(纪律:不做无意义自我润色);(b) 闭合 case-376 NEXT_SUGGESTION[3] gate 残留低危项之一(3 级嵌套混合引号 `A && eval \"B && sh -c 'git push'\"` _SHELL_OPS_RE 非 quote-aware / $(git...) 反引号 / source/. 脚本内容 / --norc 长 -c 形态)——需真 shell parser,评估是否值得引入;(c) 预备 case-380 审计轮换审非 gate 目标(scout-scan.py subprocess 面 / opt-worktree.sh 路径 logic / codegraph-sync.py 外部文件读写)。[2]【下次审计轮 case-380=380%4=0=DO A 强制审计轮】须换审非 gate 目标(已连续 case-372/376 两轮审 gate+case-377 又改 gate)。候选:(a) scripts/scout-scan.py code-review(.codebase-index 大 JSON 只读面/subprocess/标记正则虚高历史);(b) scripts/opt-worktree.sh detect_main_branch/ensure_main_wt/cp-guard/_assert_no_collateral_revert 路径 logic;(c) codegraph-sync.py/route-health-scorer.py 外部文件读写。优先挑有源代码项目。[3]【gate 残留(低危,刻意构造)】3 级嵌套混合引号仍漏(_SHELL_OPS_RE 非 quote-aware,需真 shell parser);$(git...)/反引号;source/. 脚本内容;--norc 长 -c 形态。 -->

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
