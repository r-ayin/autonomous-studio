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
# scout-scan 需要扫描父目录（子项目并列存放），不是引擎自身目录
SCAN_WORKSPACE="$(dirname "$WORKSPACE")"
STOP_MARKER="$WORKSPACE/.claude/.stop_autonomous"
mkdir -p "$WORKSPACE/.claude"

# 清掉旧的停止标记（启动时）
rm -f "$STOP_MARKER"

PROMPT='你是 autonomous-studio 引擎的持续自治循环（Ralph Wiggum 模式，每轮新 context）。
当前轮次：推进持久化自动开发研究管线的**一个小工作单位**。

★ 预算：不设上限（用户 2026-06-27 指示）。仍做小工作单位聚焦、不深读大块代码——靠 scout-scan 排序选任务，最小改动+提交。

步骤：
0. 读 .claude/autonomous-constraints.md 的排除项（DO NOT），严格遵守（如"不做 moni 前端重构"）
1. 跑 bash scripts/scout-scan.py --workspace '"$SCAN_WORKSPACE"'（不带 --json，文本报告，轻）→ 拿项目健康快照
2. 报告末尾有「推荐工作单位（按健康度排序）」——**取 #1 项目及其推荐工作单位**（若 #1 被 autonomous-constraints.md 排除则顺延 #2）。仍坚持小工作单位、不深读大块代码。autonomous-studio 不被特殊排除：它若排 #1 说明真有结构性问题，该修就修；但日常自我润色不再因"最近活跃"霸榜。
3. 最小改动（只改 1-3 个文件，不要 Read 超过 2 个源文件，不要碰 .codebase-index/ 大 JSON）
4. 用 bash scripts/opt-worktree.sh commit <area:subdirection> "<说明>" <文件1> <文件2> 提交（指定文件，避免扫 WIP；禁直接 git commit main——gate 会拦）
5. 汇报 + 喂蒸馏闭环：做了什么 + 哪个 worktree + 下轮建议；并写一条 case 到 autonomous-studio/.claude/decisions/case-YYYY-MM-DD-NNN.json（字段：case_id/agent_id/timestamp/project/work_unit/situation/action/files_changed/worktree/direction/outcome[枚举 succeeded|failed|rolled_back|superseded]/outcome_evidence[引用可观察事实，不接受散文]/next_suggestion）。预算已解禁，case 要写实、写全。
6. **回写状态**（持久化关键，否则目标无法跨 context 传递）：更新 '"$WORKSPACE"'/.claude/memory/autonomous-state.md — GOAL_STATUS(active|paused|done)/ACTIVE_GOAL/LAST_UPDATED(YYYY-MM-DD)/LAST_WORKTREE/LAST_OUTCOME(done|blocked|in_progress)/NEXT_SUGGESTION(≥1 条下轮工作单位）

纪律（用户定，无限制）：
- 不设冷却/连续次数上限——worktree 隔离，main 永远安全，大胆做
- 每轮聚焦一个**小**工作单位，做完提交就退出（while 循环重开新 context 继续）
- 唯一停止：用户说停（.claude/.stop_autonomous 标记）或 kill 进程
- 卡死保护：同错误连续 3 次无进展 → 跳到下个项目'

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
  # 每轮新 context（cloudcli claude 无 --max-iterations）；预算不设上限（用户 2026-06-27），靠 while 重开天然限单轮规模
  # bypassPermissions：不弹权限提示（否则后台卡）；安全由 hook 兜底
  #   - autonomous-commit-gate: 拦 main 提交
  #   - discovery-gate / patterns-write-gate / stop-completion-gate: 各自门禁
  cd "$WORKSPACE"
  claude -p "$PROMPT" \
    --model claude-sonnet-4-6 \
    --permission-mode bypassPermissions 2>&1 | tail -30
  echo "[$(date +%H:%M:%S)] 轮次 $ITER 结束，提交在 opt-worktree（待人工 opt-worktree.sh show/merge）"
  sleep 2  # 短暂喘息，避免空转打爆 API
done

echo "=== autonomous-loop 已停（共 $ITER 轮）==="
