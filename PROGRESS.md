# autonomous-studio — 进度

> 持续自治开发引擎（Ralph Wiggum 模式：每轮新 context，单个小工作单位 + 提交 + 退出）。
> 进度按时间倒序，单条对应一次 opt-worktree 提交。

## 当前状态（2026-06-27）

- 自治循环已稳定跑通：scout-scan → 选小工作单位 → 最小改动 → opt-worktree 提交。
- 平台预算硬上限已从 $0.50 提到 $3.00（实测 $0.50 在 17 轮中 16 次撞预算失败）。
- prompt 已轻量化以适配每轮 ~$0.5 平台约束。
- opt-worktree 支持 per-project WT_BASE 子目录 + 同 area 复用已有 worktree。

## 最近提交（自治循环硬化）

- `merge(reconcile)` 主线/worktree 历史分歧收口（2026-06-27）：patch-id 对账后，12 个 pending 分支中 9 个内容已由重放合并落入 main（删枝）；2 个 worktree（opt-cases/opt-scanner-1782570277）净提交经 FF+cherry-pick 合入后删枝；仅 `optimization` worktree 保留——其 case-047 reset-bypass 修复 WIP 未完，待续。
- `fix(commit-gate)` 分支检测+子命令识别双失效修复（case-045，cherry-pick 6d1378a→748528a）：`_git_parse` tokenizer 跨过 `git -C`、`current_branch` 从 `-C` 解析 repo、case-*.json 元数据归档豁免
- `feat(scout-scan)` deferred-marker 约定（cherry-pick 64dbab3→f197a06）：`TODO(deferred)` 不计入 triage 推荐分子，`_DEFERRED_RE` 单独计数；4 个已 triage TODO 转为 deferred 形式
- `fix(autonomous-loop)` prompt 轻量化（每轮 ~$0.5 平台硬上限）
- `fix(autonomous-loop)` max-budget 0.50→3.00（实测 0.50 太低）
- `fix(autonomous-loop)` --max-iterations → --max-budget-usd 0.50（cloudcli claude 无该 flag）
- `fix(autonomous-loop)` prompt 加读 autonomous-constraints.md 排除项
- `fix(opt-worktree)` WT_BASE per-project 子目录，避免跨项目 worktree 撞车
- `fix(opt-worktree)` 同 area 复用已有 worktree

## 待办（小工作单位池）

- [ ] **commit-gate reset/branch/update-ref ref 直写绕过（case-047，进行中）**：WIP 在 `optimization` worktree 未提交——扩拦 `reset`(ref-mover 模式)/`branch -f -d -m`/`update-ref` 对 main 的写；checkout/switch 不拦（opt-worktree.sh 内部用）。续写完应 cherry-pick 入 main（勿整枝合并，worktree 的 scout-scan.py 落后 main 138 行会回退）
- [~] TODO/FIXME/HACK 清理：marker-strip + .venv/skills 第三方包忽略 + deferred 落地后，scout 报 TODO=4 / FIXME=0 / HACK=0（2026-06-27 核验）。剩 4 条为 scout-scan.py 内描述标记约定的注释（非真债），triage 可收尾
- [ ] GATES.md 中 CRITICAL 门禁项大部分未勾选，需逐项核验存活状态
- [ ] 确认 decision-log.jsonl 有 ≥1 条真实用户交互记录（IMPORTANT 门禁）

## 纪律

- 每轮聚焦一个**小**工作单位，做完提交即退出（while 循环重开新 context 继续）。
- 不直接动 main，所有改动走 `scripts/opt-worktree.sh commit`。
- 用户排除项见 `.claude/autonomous-constraints.md`（当前：不做 moni 前端重构）。
