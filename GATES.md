# autonomous-studio — 质量门禁

<!-- 最近核验：2026-06-29，通过 settings.json hook 枚举 + 文件存在性静态分析 -->
<!-- 核验方法：[x]=文件/hook 静态确认通过；[ ]=运行时/会话状态需人工或动态验证 -->

## 🔴 CRITICAL（不通过则不得部署）

- [ ] L1 Inline 检查每次回复末尾执行（行为约束，无法静态核验）
- [ ] L2 Heartbeat CronCreate 注册存活（每 2 小时，GLM 预算制）（会话状态，需 CronList 核验）
- [ ] L3 Deep CronCreate 注册存活（每 4 小时）（会话状态，需 CronList 核验）
- [ ] 核心 Hook 注册存活（decision-observer / save-checkpoint / resume-checkpoint / **incremental-save** / discovery-gate / protocol-check / stop-completion-gate / post-edit-lint）⚠️ 7/8 已注册；incremental-save.py 脚本存在但**未在 settings.json 中注册**，其余均已确认
- [x] stop-completion-gate.py 在 Stop 时生效（Stop hook 已注册：`python "…/stop-completion-gate.py"`）
- [x] post-edit-lint.py 在 Edit/Write 后生效（PostToolUse Edit|Write hook 已注册）
- [x] SKILL.md 可被 Skill 工具正确加载（name: autonomous-studio 已确认）
- [x] decision-agent-prompt.md 完整（含七阶段框架 + 冷启动协议）（780 行，§0 冷启动 + §1 研判框架 已确认）
- [x] calibration.json 格式合法（位于 .claude/decisions/calibration.json，valid JSON，64KB）
- [x] autonomous-state.md 目标字段非空（GOAL_STATUS=active，ACTIVE_GOAL 已设置）
- [ ] 不可修改 settings.json（仅限恢复已有注册）（行为约束，无法静态核验）
- [ ] 不可删除用户文件（行为约束，无法静态核验）

## 🟡 IMPORTANT（不通过需注释原因）

- [x] decision-log.jsonl 有 ≥1 条真实用户交互记录（/home/admin/.claude/decisions/decision-log.jsonl: 3 条，含 1 条 user_input）
- [ ] 冷启动毕业指标（20 次交互）已检查
- [ ] 连续自主行动 <3（未触发冷却）
- [ ] calibration patterns 与 decision-patterns.md 同步
- [ ] 案例归档 ≤30 天未处理
- [ ] L3 降频自适应正常工作
- [ ] git status 无运行时文件 churn（tracked+ignored 矛盾集为 0）

## 🟢 NICE（尽量满足）

- [ ] 每次 L2/L3 产出 ≤3 行摘要
- [ ] 子 Agent 输出标准 `<decision>JSON</decision>` 格式
- [ ] 新增案例 ≥7 天已归档到 decision-archive.md
- [ ] 信心分校准数据持续更新
- [ ] 并发构建（phase-dev ④）走 worktree 隔离 + 增量合并（非全末尾合并）

---

## 核验说明

| 门禁项 | 核验方法 | 结果 |
|--------|---------|------|
| Hook 注册 | `cat /home/admin/.claude/settings.json \| python3 -c "..."` 数 event 数 | ✅ 11 类型全覆盖 |
| SKILL.md name | `grep "^name:" SKILL.md` | ✅ autonomous-studio |
| calibration.json | `python3 -c "json.load(open(...))"` | ✅ 无异常 |
| autonomous-state.md | `grep GOAL_STATUS` | ✅ active |
| decision-log.jsonl | `ls -la .claude/decision-log.jsonl` | ❌ 文件缺失 |
| CronCreate L2/L3 | `cat .claude/scheduled_tasks.json` | 空 = 已迁移至 devix |
