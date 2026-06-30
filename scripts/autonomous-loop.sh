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
当前轮次：推进持久化自动开发研究管线的**一个小工作单位**。

★ 预算：不设上限（用户 2026-06-27 指示）。仍做小工作单位聚焦、不深读大块代码——靠 scout-scan 排序选任务，最小改动+提交。

步骤：
0. 读 .claude/autonomous-constraints.md 全文（**DO NOT 排除项 + DO 审计指令** 两节都要遵守）。其中 DO 节要求：约每 4 轮做一次代码审计工作单位（用 code-review / security-review skill），修改敏感路径时必须补 audit-log 埋点（按 .claude/decisions/audit-log.schema.json），case 增加 audit_type/audit_findings 字段。本轮先判断是否到了审计轮次（看 decisions/ 目录今日 case 数 / 4 取模），到了就走审计路径。
1. 跑 bash scripts/scout-scan.py --workspace '"$WORKSPACE"'（不带 --json，文本报告，轻）→ 拿项目健康快照
2. 报告末尾有「推荐工作单位（按健康度排序）」——**取 #1 项目及其推荐工作单位**（若 #1 被 autonomous-constraints.md 排除则顺延 #2）。仍坚持小工作单位、不深读大块代码。autonomous-studio 不被特殊排除：它若排 #1 说明真有结构性问题，该修就修；但日常自我润色不再因"最近活跃"霸榜。审计轮次优先挑有源代码的项目（跳过纯文档/配置项目）。
3. 最小改动（只改 1-3 个文件，不要 Read 超过 2 个源文件，不要碰 .codebase-index/ 大 JSON）
4. 用 bash scripts/opt-worktree.sh commit <area:subdirection> "<说明>" <文件1> <文件2> 提交（指定文件，避免扫 WIP；禁直接 git commit main——gate 会拦）
5. 汇报 + 喂蒸馏闭环：做了什么 + 哪个 worktree + 下轮建议；并写一条 case 到 autonomous-studio/.claude/decisions/case-YYYY-MM-DD-NNN.json（字段：case_id/agent_id/timestamp/project/work_unit/situation/action/files_changed/worktree/direction/outcome[枚举 succeeded|failed|rolled_back|superseded]/outcome_evidence[引用可观察事实，不接受散文]/next_suggestion/**audit_type**[枚举 code-review|security-review|audit-log-instrumentation|none]/**audit_findings**[数组，每条 {file,line,severity,finding,remediation}，无发现写 []]）。预算已解禁，case 要写实、写全。
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

# 模型策略（用户 2026-06-29 定）：优先 GLM-5.2；遇限流(402/429/quota/overloaded)回退 qwen3.7-max。
# 代理层：env ANTHROPIC_MODEL 经重映射，settings.json 的 model 字段对 claude -p 无效，必须 --model。
PRIMARY_MODEL="GLM-5.2"          # 用户刚设的默认；有独立额度（见 memory glm52-budget-setup）
FALLBACK_MODEL="qwen3.7-max"     # 代理层已验证 200，独立额度，限流时兜底
STICKY_FAIL_THRESHOLD=3          # GLM-5.2 连续限流 N 轮后粘到 fallback，省调用
PROBE_EVERY=10                   # 粘到 fallback 后每 N 轮探一次 GLM-5.2 是否恢复
STICKY_FALLBACK=0
GLM_FAIL_STREAK=0
PROBE_COUNTDOWN=0

# 跑一轮；stdout 显示末 30 行，返回 0 成功 / 1 检测到限流信号
run_round() {
  local model="$1" out
  out=$(claude -p "$PROMPT" --model "$model" --permission-mode bypassPermissions 2>&1)
  echo "$out" | tail -30
  if echo "$out" | grep -qiE '402|429|quota[ _]?exceed|rate[ _]?limit|overloaded|insufficient'; then
    return 1
  fi
  return 0
}

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
  # 模型自适应：优先 GLM-5.2，限流回退 qwen3.7-max（见上方策略变量）
  if (( STICKY_FALLBACK )); then
    # 已粘到 fallback：直接 qwen3.7-max，周期性探 GLM-5.2 恢复
    if (( PROBE_COUNTDOWN <= 0 )); then
      echo "[$(date +%H:%M:%S)] 探测 $PRIMARY_MODEL 是否恢复..."
      if run_round "$PRIMARY_MODEL"; then
        echo "[$(date +%H:%M:%S)] $PRIMARY_MODEL 恢复，解除粘性回退"
        STICKY_FALLBACK=0; GLM_FAIL_STREAK=0
      else
        echo "[$(date +%H:%M:%S)] $PRIMARY_MODEL 仍限流，回退 $FALLBACK_MODEL"
        run_round "$FALLBACK_MODEL" || true
        PROBE_COUNTDOWN=$PROBE_EVERY
      fi
    else
      run_round "$FALLBACK_MODEL" || true
      PROBE_COUNTDOWN=$((PROBE_COUNTDOWN-1))
    fi
  else
    # 正常：先 GLM-5.2，限流即本轮回退 qwen3.7-max
    if run_round "$PRIMARY_MODEL"; then
      GLM_FAIL_STREAK=0
    else
      echo "[$(date +%H:%M:%S)] $PRIMARY_MODEL 限流，回退 $FALLBACK_MODEL"
      run_round "$FALLBACK_MODEL" || true
      GLM_FAIL_STREAK=$((GLM_FAIL_STREAK+1))
      if (( GLM_FAIL_STREAK >= STICKY_FAIL_THRESHOLD )); then
        echo "[$(date +%H:%M:%S)] $PRIMARY_MODEL 连续 $GLM_FAIL_STREAK 轮限流，粘到 $FALLBACK_MODEL（每 $PROBE_EVERY 轮探测恢复）"
        STICKY_FALLBACK=1
        PROBE_COUNTDOWN=$PROBE_EVERY
      fi
    fi
  fi
  echo "[$(date +%H:%M:%S)] 轮次 $ITER 结束，提交在 opt-worktree（待人工 opt-worktree.sh show/merge）"
  sleep 2  # 短暂喘息，避免空转打爆 API
done

echo "=== autonomous-loop 已停（共 $ITER 轮）==="
