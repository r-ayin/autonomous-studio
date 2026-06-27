#!/usr/bin/bash
# autonomous-loop.sh — 持续持久化自动开发研究管线（Ralph Wiggum 模式）
#
# 用户定：
#   - 不再 cron 定时（2h/4h 太长），而是察觉空闲就**一直触发，直到人说停**
#   - 取消 3 次限制和任何其他限制（提交进其他 worktree，main 安全，无需保守）
#   - 自动研究/开发/修复/优化一切，缺文件就补，建文件索引
#
# 机制：while 死循环，每轮 claude -p 起一个**新 context** 做一个工作单位，
# 提交到 opt-worktree，退出，循环重开。直到：
#   - 用户 kill 进程（Ctrl-C / kill）
#   - 或 .claude/.stop_autonomous 标记存在（用户说"停"时建）
#
# 每轮 bounded（--max-iterations 防 claude -p 单轮卡死），但 while 无上限。
#
# 用法:
#   autonomous-loop.sh <workspace> [skill-dir]        # 前台跑（看输出）
#   autonomous-loop.sh <workspace> [skill-dir] --bg   # 后台跑（nohup）
#   停: touch <workspace>/.claude/.stop_autonomous  或 kill 进程
set -uo pipefail

WORKSPACE="${1:-.}"
SKILL_DIR="${2:-$WORKSPACE/autonomous-studio}"
WORKSPACE="$(cd "$WORKSPACE" && pwd)"
STOP_MARKER="$WORKSPACE/.claude/.stop_autonomous"
mkdir -p "$WORKSPACE/.claude"

# 清掉旧的停止标记（启动时）
rm -f "$STOP_MARKER"

PROMPT='你是 autonomous-studio 引擎的持续自治循环（Ralph Wiggum 模式，每轮新 context）。
当前轮次：推进持久化自动开发研究管线的**一个工作单位**。

步骤：
0. 读 .claude/autonomous-constraints.md 的排除项（DO NOT），严格遵守（如"不做 moni 前端重构"）
1. 读 .claude/memory/autonomous-state.md 的 GOAL_STATUS + active goal（若有）
2. 跑 bash scripts/scout-scan.py --workspace '"$WORKSPACE"' --json  → 拿项目健康+索引（确定性，零 token）
3. 从扫描结果选一个最高价值工作单位（P0 阻塞/数据丢失/安全 > P1 质量/测试/重构 > P2 新功能）：
   - 探究该项目：读代码理解实现、跑测试看状态、对比设计
   - 主动开发/修复/优化
   - 缺文件就建（PROGRESS.md / GATES.md / 测试 / 配置 / 文档）
4. 改动用 bash scripts/opt-worktree.sh commit <area:subdirection> "<说明>" 提交
   （禁直接 git commit main——autonomous-commit-gate 会拦；area 如 engine:distillation / moni:quant）
5. 把本轮决策写 .claude/decisions/case-YYYY-MM-DD-NNN.json（含 outcome 枚举 + outcome_evidence）
6. 一行汇报：做了什么 + 改了哪些文件 + 提交到哪个 worktree + 下轮建议

纪律（用户定，无限制）：
- 不设冷却/连续次数上限——worktree 隔离，main 永远安全，大胆做
- 最坏只是某 worktree 被拒，main 不受影响
- 每轮聚焦一个工作单位，做完提交就退出（while 循环重开新 context 继续）
- 唯一停止条件：用户说停（建 .claude/.stop_autonomous 标记）或 kill 进程
- 卡死保护（不是限制，是防死循环）：同错误连续 3 次无进展 → 写 case 标 blocked，跳到下个项目'

echo "=== autonomous-loop 启动 @ $(date) ==="
echo "workspace: $WORKSPACE"
echo "停止: touch $STOP_MARKER  或  kill $$"
echo ""

ITER=0
while true; do
  # 检查停止标记
  if [[ -f "$STOP_MARKER" ]]; then
    echo "[$(date +%H:%M:%S)] 收到停止标记，退出循环（共 $ITER 轮）"
    rm -f "$STOP_MARKER"
    break
  fi
  ITER=$((ITER+1))
  echo "[$(date +%H:%M:%S)] === 轮次 $ITER ==="
  # 每轮新 context，--max-budget-usd 限单轮开销防跑飞（cloudcli claude 无 --max-iterations）
  # bypassPermissions：不弹权限提示（否则后台卡）；安全由 hook 兜底
  #   - autonomous-commit-gate: 拦 main 提交
  #   - discovery-gate / patterns-write-gate / stop-completion-gate: 各自门禁
  cd "$WORKSPACE"
  claude -p "$PROMPT" \
    --permission-mode bypassPermissions \
    --max-budget-usd 0.50 2>&1 | tail -30
  echo "[$(date +%H:%M:%S)] 轮次 $ITER 结束，提交在 opt-worktree（待人工 opt-worktree.sh show/merge）"
  sleep 2  # 短暂喘息，避免空转打爆 API
done

echo "=== autonomous-loop 已停（共 $ITER 轮）==="
