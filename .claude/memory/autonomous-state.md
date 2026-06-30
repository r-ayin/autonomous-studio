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

- **最后活跃: 2026-07-01T18:25Z（case-382=382%4=2≠0 非强制审计轮。scout-scan #1=autonomous-studio-aone score=0.0 无紧迫单位(纪律禁自我润色),普通修复轮无可做之物。state NEXT_SUGGESTION[2] 标记 scripts/opt-worktree.sh 为最高优先审计候选。约束 DO A:审计轮替代普通修复轮——空转普通轮不如做真审计。对 opt-worktree.sh(701 行 bash,1 源文件预算内)做 security-review,聚焦删除/注入面。核查:cmd message 双引号仅变量展开不二次求值 $()→无注入;git -C/-- 分隔;grep -F 固定串;json_escape 闭合 case-366;detect_main_branch detached-HEAD 探测无 shell;_assert_no_collateral_revert 进程替换固定串无 regex。发现 1 真缺口(low):cmd_merge(L538)/cmd_reject(L584)/cmd_show(L513) 的 <worktree> CLI $3 原拼 dir=$WT_BASE/$wt,cmd_merge L569/cmd_reject L588 有 `worktree remove --force || rm -rf $dir` fallback——wt 未校验 basename,传 ../ 或 ./.. 致 [[ -d ]] 命中遍历目标+worktree remove 失败+|| rm -rf 删遍历目标(删除敏感路径遍历)。引擎只传 basename 故未被利用但缺口真。修复 1 file scripts/opt-worktree.sh +17:新增 _validate_wt_name()(拒空/./../含 / 的 wt exit1)于 cmd_show/merge/reject 取 wt 后调用。回归:bash -n OK+6 例守卫测试(.. / . / foo/../../etc / ../etc 被 exit1 拒;合法 optimization 穿过进正常 'worktree 不存在';merge .. / reject ../etc 被拒)ALL PASS。DO B:修复触删除敏感路径但未新增敏感操作——cmd_merge/reject 删除路径已有 audit_log(L567/577/594/596),修复仅加前置校验,删除操作本身已埋点→无需新增 audit-log instrumentation。case-382 outcome=succeeded audit_type=security-review audit_findings=1(low 全修)。pending=1(optimization @866b03f 待 case-383 sanctioned-merge)。main HEAD=3be3fde 干净）**
- **活跃项目**: autonomous-studio-aone 维护——case-382 security-review opt-worktree.sh 修复 _validate_wt_name 防 rm -rf 路径遍历→optimization @866b03f pending sanctioned-merge。case-372/373/375/376/377/378 全部上线 LIVE,case-380 scout-scan.py 修复落 main,case-382 opt-worktree.sh 修复 pending。
- **当前阶段**: 审计工作单位完成 pending=1;下轮 case-383=383%4=3≠0 非审计普通轮——sanctioned-merge @866b03f squash→main+worktree 清理+全量 scout-scan 烟测
- **GOAL_STATUS**: active
- **ACTIVE_GOAL**: 持续自治管线（无限制预算，scout-scan 驱动；审计轮次每 4 case 强制 code-review/security-review + 敏感路径 audit-log 埋点）
- **LAST_UPDATED**: 2026-07-01
- **LAST_WORKTREE**: optimization @866b03f（pending sanctioned-merge;1 file scripts/opt-worktree.sh +17 _validate_wt_name 守卫防 rm -rf 路径遍历;与 main 归档环 case-382.json+state.md 无源码重叠→clean squash 待合并;方向 engine:opt-worktree-security;opt-worktree.sh 非 LIVE 部署文件无 LIVE 同步需求;case-382 outcome=succeeded audit_type=security-review audit_findings=1 low 全修;main HEAD=3be3fde 干净 pending=1）
- **LAST_OUTCOME**: done
- **NEXT_SUGGESTION**: [1]【普通轮·case-383=383%4=3≠0 非审计】pending=1(optimization @866b03f 待 sanctioned-merge)。预审:merge-base=3be3fde auto/optimization changeset 仅 scripts/opt-worktree.sh 1 file +17 与 main 归档环(case-382.json+state.md)无源码重叠→clean squash;diff 3be3fde..main -- opt-worktree.sh 空→无冲突面。bash scripts/opt-worktree.sh . merge optimization→main(squash merge)+worktree 清理+auto/optimization 残留分支 git branch -D。opt-worktree.sh 非 LIVE 部署文件(/home/admin/.claude/hooks/ 无 opt-worktree.sh)→无需 cp LIVE。回归:bash -n OK+守卫测试 6 例重跑+全量 scout-scan 烟测 TODO=0/FIXME=0/HACK=0 无回归。[2]【下次审计轮·case-384=384%4=0=DO A 强制审计轮】已审:opt-worktree.sh(case-382)+gate(连续多轮触)+scout-scan.py(case-380)。剩余候选优先级:(a) scripts/route-health-scorer.py(331 行,外部文件读写/评分 logic,未审过,优先);(b) codegraph-sync.py(索引读写,自动更新感知);(c) .claude/hooks/reference-transaction(已部署本体未深审)。[3]【opt-worktree.sh 残留低危(非下轮必碰)】json_escape 未转义 0x00-0x08/0x0b/0x0c/0x0e-0x1f 控制符(JSON 规范要求),wt/sha/reason 派生值实践不含此类字符→理论 JSON 合规性缺口,维持现状。
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
<!-- LAST_WORKTREE: optimization @866b03f（pending sanctioned-merge;1 file scripts/opt-worktree.sh +17 _validate_wt_name 守卫防 rm -rf 路径遍历;与 main 归档环 case-382.json+state.md 无源码重叠→clean squash 待合并;方向 engine:opt-worktree-security;opt-worktree.sh 非 LIVE 部署文件无 LIVE 同步需求;case-382 outcome=succeeded audit_type=security-review audit_findings=1 low 全修;main HEAD=3be3fde 干净 pending=1） -->
<!-- LAST_OUTCOME: done -->
<!-- NEXT_SUGGESTION: [1]【普通轮·case-383=383%4=3≠0 非审计】pending=1(optimization @866b03f 待 sanctioned-merge)。预审:merge-base=3be3fde auto/optimization changeset 仅 scripts/opt-worktree.sh 1 file +17 与 main 归档环(case-382.json+state.md)无源码重叠→clean squash。bash scripts/opt-worktree.sh . merge optimization→main(squash)+worktree 清理+auto/optimization 残留分支 git branch -D。opt-worktree.sh 非 LIVE 部署文件→无需 cp LIVE。回归:bash -n OK+守卫测试 6 例重跑+全量 scout-scan 烟测 TODO=0/FIXME=0/HACK=0 无回归。[2]【下次审计轮·case-384=384%4=0=DO A 强制审计轮】已审 opt-worktree.sh(case-382)+gate+scout-scan.py(case-380)。剩余候选:(a) scripts/route-health-scorer.py(331 行,外部文件读写/评分 logic,未审过,优先);(b) codegraph-sync.py(索引读写);(c) .claude/hooks/reference-transaction(本体未深审)。[3]【opt-worktree.sh 残留低危(非下轮必碰)】json_escape 未转义 0x00-0x08/0x0b/0x0c/0x0e-0x1f 控制符(JSON 规范要求),wt/sha/reason 派生值实践不含此类字符→理论 JSON 合规性缺口,维持现状。 -->

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
