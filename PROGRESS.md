# autonomous-studio — 进度

> 持续自治开发引擎（Ralph Wiggum 模式：每轮新 context，单个小工作单位 + 提交 + 退出）。
> 进度按时间倒序，单条对应一次 opt-worktree 提交。

## 当前状态（2026-06-27）

- 自治循环已稳定跑通：scout-scan → 选小工作单位 → 最小改动 → opt-worktree 提交。
- 平台预算硬上限已从 $0.50 提到 $3.00（实测 $0.50 在 17 轮中 16 次撞预算失败）。
- prompt 已轻量化以适配每轮 ~$0.5 平台约束。
- opt-worktree 支持 per-project WT_BASE 子目录 + 同 area 复用已有 worktree。

## 最近提交（自治循环硬化）

- `fix(autonomous-loop)` prompt 轻量化（每轮 ~$0.5 平台硬上限）
- `fix(autonomous-loop)` max-budget 0.50→3.00（实测 0.50 太低）
- `fix(autonomous-loop)` --max-iterations → --max-budget-usd 0.50（cloudcli claude 无该 flag）
- `fix(autonomous-loop)` prompt 加读 autonomous-constraints.md 排除项
- `fix(opt-worktree)` WT_BASE per-project 子目录，避免跨项目 worktree 撞车
- `fix(opt-worktree)` 同 area 复用已有 worktree

## 待办（小工作单位池）

- [~] TODO/FIXME/HACK 清理：scout 报 TODO=45 / FIXME=4 / HACK=4 → 现报 TODO=4 / FIXME=0 / HACK=0（marker-strip + .venv/skills 第三方包忽略修复落地后大幅下降，2026-06-27 核验）。剩 4 条为 scout-scan.py 内描述标记约定的注释（非真债），triage 可收尾
- [ ] GATES.md 中 CRITICAL 门禁项大部分未勾选，需逐项核验存活状态
- [ ] 确认 decision-log.jsonl 有 ≥1 条真实用户交互记录（IMPORTANT 门禁）

## 纪律

- 每轮聚焦一个**小**工作单位，做完提交即退出（while 循环重开新 context 继续）。
- 不直接动 main，所有改动走 `scripts/opt-worktree.sh commit`。
- 用户排除项见 `.claude/autonomous-constraints.md`（当前：不做 moni 前端重构）。
