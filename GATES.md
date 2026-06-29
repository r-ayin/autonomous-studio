# autonomous-studio — 质量门禁

> 最后核验：2026-06-29 (case-123: GATES IMPORTANT gate correction — decision-patterns.md exists & in sync)

## 🔴 CRITICAL（不通过则不得部署）

- [ ] L1 Inline 检查每次回复末尾执行
- [ ] L2 Heartbeat CronCreate 注册存活（每 2 小时，GLM 预算制） — ⚠️ 无 scheduled_tasks.json，L2 心跳未注册
- [ ] L3 Deep CronCreate 注册存活（每 4 小时） — ⚠️ 无 scheduled_tasks.json
- [ ] 核心 Hook 注册存活（decision-observer / save-checkpoint / resume-checkpoint / incremental-save / discovery-gate / protocol-check / stop-completion-gate / post-edit-lint） — ⚠️ 10 个 .py 文件在 .claude/hooks/ 但无 settings.json 注册
- [ ] stop-completion-gate.py 在 Stop 时生效（测试/任务/语法二元门控） — 文件存在，未注册
- [ ] post-edit-lint.py 在 Edit/Write 后生效（自动 lint/关联测试） — 文件存在，未注册
- [x] SKILL.md 可被 Skill 工具正确加载（name: autonomous-studio）
- [x] decision-agent-prompt.md 完整（含七阶段框架 + 冷启动协议）
- [x] calibration.json 格式合法 — .claude/decisions/calibration.json valid JSON
- [x] autonomous-state.md 目标字段非空（且未被 hook 覆写——运行时心跳应写 autonomous-state-runtime.md）
- [x] 不可修改 settings.json（仅限恢复已有注册） — 行为约束；项目级 settings.json 不存在
- [x] 不可删除用户文件 — 行为约束

## 🟡 IMPORTANT（不通过需注释原因）

- [x] decision-log.jsonl 有 ≥1 条真实用户交互记录 — 5 条 seed entries（人工批准合并 + 约束设定 + 预算解禁），created 2026-06-29
- [x] 冷启动毕业指标（20 次交互）已检查 — 135 case files >> 20 threshold，graduated
- [ ] 连续自主行动 <3（未触发冷却）
- [x] calibration patterns 与 decision-patterns.md 同步 — .claude/memory/decision-patterns.md 存在(279行, 13 patterns)；distill-patterns.py --project . 干跑确认 0 条缺失条目，patterns.md 与 calibration.json 一致（verified 2026-06-29）
- [x] 案例归档 ≤30 天未处理 — 78 个 case 文件，最新 2026-06-28（1 天）
- [ ] L3 降频自适应正常工作 — ⚠️ L3 未注册，无法降频
- [x] git status 无运行时文件 churn（tracked+ignored 矛盾集为 0） — verified 2026-06-29: dirty=0, git status clean

## 🟢 NICE（尽量满足）

- [ ] 每次 L2/L3 产出 ≤3 行摘要
- [ ] 子 Agent 输出标准 `<decision>JSON</decision>` 格式
- [ ] 新增案例 ≥7 天已归档到 decision-archive.md
- [ ] 信心分校准数据持续更新
- [x] 并发构建（phase-dev ④）走 worktree 隔离 + 增量合并（非全末尾合并） — opt-worktree.sh 实现
