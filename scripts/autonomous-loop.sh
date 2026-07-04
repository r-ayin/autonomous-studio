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
#   autonomous-loop.sh <workspace> [engine-dir]        # 前台跑（看输出）
#   autonomous-loop.sh <workspace> [engine-dir] --bg   # 后台跑（nohup，日志在 /tmp/autonomous-loop-<ts>.log）
#   停: touch <engine-dir>/.claude/.stop_autonomous  或 kill 进程
#
# 引擎自身 cwd = engine-dir（默认 <workspace>/autonomous-studio），
# 不在 workspace 根目录跑——case/state/audit 都落 engine-dir/.claude/。
set -uo pipefail

WORKSPACE="${1:-.}"
ENGINE_DIR="${2:-$WORKSPACE/autonomous-studio}"
BG_FLAG="${3:-}"
WORKSPACE="$(cd "$WORKSPACE" && pwd)"
ENGINE_DIR="$(cd "$ENGINE_DIR" && pwd)"
STOP_MARKER="$ENGINE_DIR/.claude/.stop_autonomous"
mkdir -p "$ENGINE_DIR/.claude"

# --bg: 自举为后台进程（nohup + 日志重定向），父进程退出。
# M-004 fix (audit-2026-07-01-002): 文档声称支持但原代码未实现。
# EC-017 fix: setsid 隔离进程组，防止 --bg 子进程树泄漏到启动终端的进程组。
#   setsid 让 re-exec 的子进程成为新 session leader（新进程组），这样：
#   1. 终端关闭（SIGHUP）不传播给后台循环——nohup 挡 HUP，setsid 断父进程组关联
#   2. kill $BG_PID 或 kill -TERM -$BG_PID 能杀掉整个后台进程树（同组）
#   3. trap `kill 0` 只杀后台自己的进程组，不误杀启动终端的其他进程
#   trap 延迟到 --bg 出口之后安装（launcher 进程不需要也不应该 kill 0）。
if [[ "$BG_FLAG" == "--bg" ]]; then
  LOG_FILE="/tmp/autonomous-loop-$(date +%Y%m%d-%H%M%S).log"
  setsid nohup "$0" "$WORKSPACE" "$ENGINE_DIR" </dev/null >"$LOG_FILE" 2>&1 &
  BG_PID=$!
  echo "[autonomous-loop] 已后台启动 PID=$BG_PID 日志=$LOG_FILE"
  echo "[autonomous-loop] 停: touch $STOP_MARKER  或 kill $BG_PID"
  exit 0
fi

# L-001 fix (audit-2026-07-01-002): Ctrl-C / SIGTERM 时清理 claude -p 子进程，防孤儿
# AS-EC-007 fix (audit-2026-07-02-002): trap 同时清理 run_round 中 mktemp 的临时文件，
#   避免 SIGINT 落在 mktemp→shred 窗口内导致敏感输出泄漏到 /tmp。
# EC-017: trap 放在 --bg exit 之后，只在实际长跑工作进程中安装。
#   launcher 进程（--bg 分支）不安装 trap——它 exit 0 即走，无需 kill 0。
CURRENT_OUT_FILE=""
trap 'echo "[trap] 收到信号，终止子进程组..."; if [ -n "$CURRENT_OUT_FILE" ] && [ -e "$CURRENT_OUT_FILE" ]; then shred -u "$CURRENT_OUT_FILE" 2>/dev/null || rm -f "$CURRENT_OUT_FILE"; fi; kill 0 2>/dev/null; exit 130' INT TERM

# 启动时若停止标记仍存在 → 用户已暂停。外部重启者（沙箱 .start / watchdog）会
# 反复拉起本脚本，必须在启动处立即退出且**不擦除标记**——否则每次重启都擦掉
# 标记后跑一轮，停止信号被击穿（打地鼠）。恢复运行：用户 rm 标记即可。
if [[ -f "$STOP_MARKER" ]]; then
  echo "[$(date +%H:%M:%S)] 启动时检测到停止标记，立即退出（暂停中，保留标记）"
  exit 0
fi

PROMPT='你是 autonomous-studio 引擎的持续自治循环（Ralph Wiggum 模式，每轮新 context）。
当前轮次：推进持久化自动开发研究管线的**一个小工作单位** 或 **一次全量深度审计**（由 audit-cycle-state 决定）。

★ 预算：不设上限（用户 2026-06-27 指示）。普通轮/瞭望轮仍守小工作单位；**全量审计轮解绑深度限制**（可读 5-15 文件、追跨模块数据流、可用 sub-agent 但必须 model=sonnet）。

步骤：
0. 读 .claude/autonomous-constraints.md 全文（DO NOT 排除项 + DO 审计指令 A/B/C/D 四节）。然后读 .claude/audit-cycle-state.json 决定**本轮类型**：
   - status=idle 或 cycle-complete → **本轮走全量审计路径**：选一个"未深度审过"的项目（看 .claude/audits/ 已有报告避免重复），深度审计（不限于 1-3 文件），产出独立 report 落 .claude/audits/audit-YYYY-MM-DD-NNN.md（不进 case JSON），把 findings 写到 audit-cycle-state.json 的 derived_fixes（每条标 kind: route-fix|direction-shift|structural）。status 改 auditing→fix-in-progress。然后本轮结束（不派生 fix，下轮起逐个派生）。
   - status=fix-in-progress → **本轮走瞭望/研究或派生 fix 路径**：先看 audit-cycle-state.derived_fixes 里有没有 status=pending 的 finding；有 → 派生一个最小 fix case（route-fix 用 opt-worktree 复用，direction-shift 触发新 worktree——opt-worktree.sh 已内置 judge_direction_kind 自动判定，只需把公共接口文件列入改动）；finding 全 pending → 跑 scout-scan 做瞭望快照（轻量，不深读源码），写 case 存档。所有派生 fix 状态变 merged|rejected 后，audit-cycle-state.status 改 cycle-complete（下轮触发新审计）。
   - status=auditing → 不应出现（审计单轮内完成），出现则降级走瞭望轮。
1. 跑 bash scripts/scout-scan.py --workspace '"$WORKSPACE"'（不带 --json，文本报告，轻）→ 拿项目健康快照（瞭望/修复轮必跑；审计轮可跳过此步直接深审）
2. 报告末尾有「推荐工作单位（按健康度排序）」——瞭望/修复轮取 #1 项目（若 #1 被 autonomous-constraints.md 排除则顺延 #2）。仍坚持小工作单位（**修复阶段** 1-3 文件）；**审计阶段** 不限深度。autonomous-studio 不被特殊排除：它若排 #1 说明真有结构性问题，该修就修；但日常自我润色不再因"最近活跃"霸榜。
3. 修复轮的最小改动（只改 1-3 个文件，不要 Read 超过 2 个源文件——**仅修复轮**；审计轮可读 5-15 文件）；不要碰 .codebase-index/ 大 JSON
4. 用 bash scripts/opt-worktree.sh commit <area:subdirection> "<说明>" <文件1> <文件2> 提交（指定文件，避免扫 WIP；禁直接 git commit main——gate 会拦）。opt-worktree.sh 已内置 direction_kind 判定：触及 .claude/public-interfaces.txt 列出的公共接口文件 → 自动开新 worktree（direction-shift）；不触及 → 复用同 area worktree（route-fix）。你不用手动决定。
5. 汇报 + 喂蒸馏闭环：做了什么 + 哪个 worktree + 下轮建议；并写一条 case 到 .claude/decisions/case-YYYY-MM-DD-NNN.json（字段：case_id/agent_id/timestamp/project/work_unit/situation/action/files_changed/worktree/direction/outcome[枚举 succeeded|failed|rolled_back|superseded]/outcome_evidence[引用可观察事实，不接受散文]/next_suggestion/**audit_type**[枚举 code-review|security-review|audit-log-instrumentation|deep-audit|none]/**audit_findings**[数组，每条 {file,line,severity,finding,remediation,kind}，无发现写 []]/**audit_id**[派生 fix 写父审计 id，非审计 case 写 null]/**audit_depth**[枚举 shallow|deep，瞭望轮=shallow，全量审计轮=deep]）。预算已解禁，case 要写实、写全。**派生 fix case 必须在 audit-cycle-state.json 的 derived_fixes 数组里同步 status=pending→merged|rejected**。
6. **回写状态**（持久化关键，否则目标无法跨 context 传递）：更新 .claude/memory/autonomous-state.md — GOAL_STATUS(active|paused|done)/ACTIVE_GOAL/LAST_UPDATED(YYYY-MM-DD)/LAST_WORKTREE/LAST_OUTCOME(done|blocked|in_progress)/NEXT_SUGGESTION(≥1 条下轮工作单位）。**同时回写 .claude/audit-cycle-state.json**（status/derived_fixes[].status/last_audit_*），不写则审计周期状态丢失。

纪律（用户定，无限制）：
- 不设冷却/连续次数上限——worktree 隔离，main 永远安全，大胆做
- 每轮聚焦一个**小**工作单位（修复轮）或**一次深度审计**（审计轮），做完就退出（while 循环重开新 context 继续）
- 全量审计轮解绑深度但解绑**仅限审计**——审计挖出的问题在派生 fix 时仍拆成最小单位走 opt-worktree
- 唯一停止：用户说停（.claude/.stop_autonomous 标记）或 kill 进程
- 卡死保护：同错误连续 3 次无进展 → 跳到下个项目'

echo "=== autonomous-loop 启动 @ $(date) ==="
echo "workspace: $WORKSPACE"
echo "engine-dir: $ENGINE_DIR"
echo "停止: touch $STOP_MARKER  或  kill $$"
echo ""

# 模型策略（用户 2026-07-04 改）：自动决策引擎默认跑 GLM-5.2，qwen3.7-max 作 402 兜底。
# 原因：用户指示默认改回 GLM-5.2；保留 qwen3.7-max 兜底是因为 GLM-5.2 在连续自治下配额易 402 耗尽（2026-06-29 实测 6264 轮末段数百轮 402 空转），限流时切独立额度的 qwen 续跑。
# 代理层：env ANTHROPIC_MODEL 经重映射，settings.json 的 model 字段对 claude -p 无效，必须 --model。
PRIMARY_MODEL="GLM-5.2"            # 自动模式默认模型（用户 2026-07-04 改回）
FALLBACK_MODEL="qwen3.7-max"      # GLM 402 限流时兜底，代理层独立额度
STICKY_FAIL_THRESHOLD=3           # GLM 连续 3 轮 402 → 粘到 qwen 兜底，每 PROBE_EVERY 轮探测恢复
PROBE_EVERY=5                   # 粘到 qwen 后每 5 轮探测 GLM 是否恢复
STICKY_FALLBACK=0
GLM_FAIL_STREAK=0
PROBE_COUNTDOWN=0

# 跑一轮；stdout 显示末 30 行，返回 0 成功 / 1 检测到限流信号
# H-005 fix（audit-002）：输出落临时文件而非 shell 变量。
#   原实现 out=$(claude -p ... 2>&1) 后 echo|tail + echo|grep 三次复制 MB 级字符串
#   → bash 变量膨胀 + pipe buffer 全量驻留敏感信息（文件内容/工具结果）。
#   改为重定向到 mktemp 临时文件，tail/grep 直接读文件，结束 shred -u 清除。
run_round() {
  local model="$1" out_file rc=0
  out_file=$(mktemp) || return 1
  CURRENT_OUT_FILE="$out_file"
  claude -p "$PROMPT" --model "$model" --permission-mode bypassPermissions >"$out_file" 2>&1 || true
  tail -30 "$out_file"
  # L-003 fix (audit-2026-07-01-002): 收窄限流 grep，避免误匹配 'line 429'/'insufficient coverage' 等正常输出
  # 保留 402/429 裸匹配（几乎只对应 HTTP 状态码）；quota/rate_limit 改为组合词防误中；移除 overloaded/insufficient 单词
  if grep -qiE '\b(402|429)\b|quota[ _]?(exceeded|limit)|rate[ _]?limit(ed)?' "$out_file"; then
    rc=1
  fi
  # AS-EC-007: shred 之前清空 CURRENT_OUT_FILE，缩小 trap 清理窗口；trap 兜底已赋值但未清空的 SIGINT 场景
  CURRENT_OUT_FILE=""
  shred -u "$out_file" 2>/dev/null || rm -f "$out_file"
  return $rc
}

ITER=0
while true; do
  # 检查停止标记（不擦除：外部重启者会反复拉起本脚本，擦除即击穿暂停）
  if [[ -f "$STOP_MARKER" ]]; then
    echo "[$(date +%H:%M:%S)] 收到停止标记，退出循环（共 $ITER 轮，保留标记供重启者识别）"
    break
  fi
  ITER=$((ITER+1))
  echo "[$(date +%H:%M:%S)] === 轮次 $ITER ==="
  # AS-H-001 fix (audit-2026-07-01-007): 循环体包进 subshell，cd 仅在子进程生效。
  # 原实现 cd "$ENGINE_DIR" 在 while 内直接执行，run_round 内的 claude -p 或后续命令
  # 若改 cwd（如 cd 到子项目），下一轮 STOP_MARKER/case 路径基于错误 cwd 计算→
  # 引擎静默写入错误位置或找不到停止标记。subshell 隔离后父 shell cwd 永驻启动目录。
  (
    cd "$ENGINE_DIR" || exit 1
    # 每轮新 context（cloudcli claude 无 --max-iterations）；预算不设上限（用户 2026-06-27），靠 while 重开天然限单轮规模
    # bypassPermissions：不弹权限提示（否则后台卡）；安全由 hook 兜底
    #   - autonomous-commit-gate: 拦 main 提交
    #   - discovery-gate / patterns-write-gate / stop-completion-gate: 各自门禁
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
    # 循环末尾归档孤儿 case（case-341 未竟，多轮遗留）：跨项目轮次写的 case 滞留 AS main
    # 成 untracked→scout 误算 dirty/撞号。扫 AS main untracked case-*.json，cp 进 housekeeping
    # worktree 提交、main 还原。自测守卫已在脚本内；失败不阻断主循环（|| true）。
    bash "$ENGINE_DIR/scripts/loop-archive-cases.sh" autonomous-studio || true
  )
  sleep 2  # 短暂喘息，避免空转打爆 API
done

echo "=== autonomous-loop 已停（共 $ITER 轮）==="
