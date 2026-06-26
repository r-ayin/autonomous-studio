# autonomous-studio — 质量门禁

## 🔴 CRITICAL（不通过则不得部署）

- [ ] L1 Inline 检查每次回复末尾执行
- [ ] L2 Heartbeat CronCreate 注册存活（每 2 小时，GLM 预算制）
- [ ] L3 Deep CronCreate 注册存活（每 4 小时）
- [ ] 核心 Hook 注册存活（decision-observer / save-checkpoint / resume-checkpoint / incremental-save / discovery-gate / protocol-check / stop-completion-gate / post-edit-lint）
- [ ] stop-completion-gate.py 在 Stop 时生效（测试/任务/语法二元门控）
- [ ] post-edit-lint.py 在 Edit/Write 后生效（自动 lint/关联测试）
- [ ] SKILL.md 可被 Skill 工具正确加载（name: autonomous-studio）
- [ ] decision-agent-prompt.md 完整（含七阶段框架 + 冷启动协议）
- [ ] calibration.json 格式合法
- [ ] autonomous-state.md 目标字段非空（且未被 hook 覆写——运行时心跳应写 autonomous-state-runtime.md）
- [ ] 不可修改 settings.json（仅限恢复已有注册）
- [ ] 不可删除用户文件

## 🟡 IMPORTANT（不通过需注释原因）

- [ ] decision-log.jsonl 有 ≥1 条真实用户交互记录
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
