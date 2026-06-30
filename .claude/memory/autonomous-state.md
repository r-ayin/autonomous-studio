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

- **最后活跃: 2026-07-01T18:12Z（DO A 强制审计轮 case-380=380%4=0=0 触发代码审计。state NEXT_SUGGESTION[1] 明示换审非 gate 目标(已连续 case-372/376/377/378/379 五轮触 gate)。scout-scan #1 AS score=0.0 无紧迫单位。从候选(a) scripts/scout-scan.py code-review 入手——纯 Python 源码符合审计轮挑有源码项目。通读 1 文件(不超 2 文件预算)做 code-review:subprocess 全 list-form 无 shell=True+全 timeout 3-5s→无注入;index 路径 basename 派生→无遍历;file 读有 2MB 上限→无耗尽。发现真实正确性缺口:count_markers 逐行 _STRIP_STRINGS(line57)无法闭合跨行三引号 docstring,line53 文档化意图(docstring 标记不算债)未覆盖多行 docstring——多行 docstring 内 TODO:/FIXME: 被 _MARKER_RE 误计为真债,残留第 7 类自指虚高。_STRIP_HTML_COMMENTS(line69)缺 DOTALL 同理漏多行 HTML 注释。修复 1 file scripts/scout-scan.py +29/-18 经 opt-worktree→optimization @de8530f pending sanctioned-merge:+_STRIP_TRIPLE 正则整内容一次性剥多行三引号+count_markers 改 fh.read() 整内容先剥三引号再 splitlines 逐行走其余 stripper+_STRIP_HTML_COMMENTS +re.DOTALL。回归:py_compile OK+功能例(多行 docstring 内 TODO:/FIXME: 不计,真 # TODO:/HACK: 仍计)PASS+scout-scan.py 自指仍 0+全量扫描烟测 TODO=0/FIXME=0/HACK=0 无回归。DO B:改动仅 count_markers 字符串剥离逻辑(纯读+regex)不触 subprocess/file写/auth/PII 敏感路径→无需 audit-log 埋点。case-380 outcome=succeeded audit_type=code-review audit_findings=2(low,全修)。pending=1(optimization @de8530f 待 case-381 sanctioned-merge)。main HEAD=4b5522c 干净）**
- **活跃项目**: autonomous-studio-aone 维护——case-380 DO A 代码审计轮:scout-scan.py count_markers 多行 docstring 剥离缺口审计+修复 @de8530f pending。case-372/373/375/376/377/378 全部上线 LIVE。
- **当前阶段**: 审计完成 pending=1(optimization @de8530f);下轮 case-381=381%4=1≠0 非审计普通轮——sanctioned-merge @de8530f squash→main+worktree 清理+全量 scout-scan 烟测
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01
- **LAST_WORKTREE**: optimization @de8530f（area=engine 同主 worktree,1 file scripts/scout-scan.py +29/-18,pending sanctioned-merge 未入 main;scout-scan.py 非 LIVE 部署文件无 LIVE 同步需求;方向 engine:scout-scan-strip;case-380 outcome=succeeded audit_type=code-review audit_findings=2 low 全修;main HEAD=4b5522c 干净 pending=1）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【普通轮·case-381=381%4=1≠0 非审计】sanctioned-merge optimization @de8530f→main squash(1 file scout-scan.py +29/-18,与 main 归档环无源码重叠→clean squash)+worktree 清理+auto/optimization 残留分支 git branch -D。scout-scan.py 非 LIVE 部署文件,合并后即生效无需 cp LIVE。合并后跑全量 scout-scan 烟测确认无回归。[2]【下次审计轮·case-384=384%4=0=DO A 强制审计轮】继续换审非 gate 目标。剩余候选:(a) scripts/opt-worktree.sh security-review(detect_main_branch/ensure_main_wt/cp-guard/_assert_no_collateral_revert/audit_log json_escape 路径 logic,bash 注入面更值得审,优先);(b) scripts/route-health-scorer.py(331 行,外部文件读写/评分 logic);(c) .claude/hooks/autonomous-commit-gate.py 本体(已连续多轮触,优先级低)。[3]【scout-scan 残留低危(非审计轮不碰)】_STRIP_BACKTICKS 仍逐行,多行 markdown 围栏代码块 ``` 不匹配单反引号正则——刻意构造低危,维持轻量扫描器边界,真需精确可上 tree-sitter(见文件尾升级路径注释)。
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
<!-- LAST_WORKTREE: optimization @de8530f（area=engine 同主 worktree,1 file scripts/scout-scan.py +29/-18,pending sanctioned-merge 未入 main;scout-scan.py 非 LIVE 部署文件无 LIVE 同步需求;方向 engine:scout-scan-strip;case-380 DO A 代码审计轮 outcome=succeeded audit_type=code-review audit_findings=2 low 全修;main HEAD=4b5522c 干净 pending=1） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【普通轮·case-381=381%4=1≠0 非审计】sanctioned-merge optimization @de8530f→main squash(1 file scout-scan.py +29/-18,与 main 归档环无源码重叠→clean squash)+worktree 清理+auto/optimization 残留分支 git branch -D。scout-scan.py 非 LIVE 部署文件,合并后即生效无需 cp LIVE。合并后跑全量 scout-scan 烟测确认无回归。[2]【下次审计轮·case-384=384%4=0=DO A 强制审计轮】继续换审非 gate 目标。剩余候选:(a) scripts/opt-worktree.sh security-review(bash 注入面更值得审,优先);(b) scripts/route-health-scorer.py(外部文件读写/评分 logic);(c) gate 本体(已连续多轮触,优先级低)。[3]【scout-scan 残留低危(非审计轮不碰)】_STRIP_BACKTICKS 仍逐行,多行 markdown 围栏代码块 ``` 不匹配单反引号正则——刻意构造低危,维持轻量扫描器边界,真需精确可上 tree-sitter。 -->

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
