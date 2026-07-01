#!/usr/bin/env bash
# loop-archive-cases.sh — 循环末尾扫项目 main 的 untracked case-*.json 自动归档
#
# 修复缺口（case-338/339/340 三次踩同）：
#   循环 step5 写 case 到 autonomous-studio/.claude/decisions/，但 step4 的
#   opt-worktree commit 进的是【目标项目】worktree（异库）。当目标项目 ≠ AS 时，
#   case 文件永远进不了任何 worktree，滞留 AS main 成 untracked 孤儿——
#   下一轮 scout-scan 把它当 dirty 信号、cmd_next_case 又可能撞号。
#
# 方案：循环末尾调本脚本，扫 AS main untracked 的 case-*.json，经 opt-worktree
#   commit（area=housekeeping:archive-cases）把它们 cp 进 AS housekeeping worktree
#   提交、main 还原（untracked→rm），自测断言 main 干净 + worktree 有新 commit。
#   归档后 case 落 AS housekeeping worktree 待人工审合并，与正常 opt 提交同路径。
#
# 用法:
#   bash scripts/loop-archive-cases.sh [project]        # 默认 project=autonomous-studio
#
# 退出码: 0=无孤儿或归档成功自测通过；1=自测失败或前置断言失败。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${1:-autonomous-studio}"
DECISIONS_REL=".claude/decisions"

# 解析成绝对路径：本脚本会 cd 进 PROJECT，随后用相对 PROJECT 调 opt-worktree 会
# 因 CWD 已变而 "不是目录"（实踩）。绝对路径从任意 CWD 都成立。
case "$PROJECT" in
  /*) ;;
  *) PROJECT="$PWD/$PROJECT" ;;
esac

if [[ ! -d "$PROJECT/.git" ]] && ! git -C "$PROJECT" rev-parse --git-dir >/dev/null 2>&1; then
  echo "❌ 错误: '$PROJECT' 不是 git 仓库" >&2
  exit 1
fi

cd "$PROJECT"

# --- 收集 main 工作树中 untracked 的 case-*.json ---
# porcelain 格式 "XY <path>"（untracked => "?? <path>"）。strip 前 3 字符（2 状态+空格）
# 后按 case-*.json 路径过滤。rename 取 -> 后新路径。
orphans=()
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  p="${line#???}"                 # 去 "XY " 前缀（# 模式 ??? = 3 个任意字符：2 状态+空格）
  case "$p" in
    *" -> "*) p="${p##* -> }";;
  esac
  case "$p" in
    "$DECISIONS_REL"/case-*.json) orphans+=("$p");;
  esac
done < <(git status --porcelain)

if (( ${#orphans[@]} == 0 )); then
  echo "✓ 无孤儿 case（$PROJECT main 干净，decisions/ 无 untracked case-*.json）"
  exit 0
fi

echo "→ 发现 ${#orphans[@]} 个孤儿 case，归档进 housekeeping worktree："
printf '   %s\n' "${orphans[@]}"

# --- 前置断言：porcelain 报孤儿但磁盘确有文件（防 porcelain 误读产空 commit）---
real=()
for f in "${orphans[@]}"; do
  if [[ -f "$f" ]]; then
    real+=("$f")
  else
    echo "⚠️ porcelain 报告但磁盘缺失，跳过: $f" >&2
  fi
done
if (( ${#real[@]} == 0 )); then
  echo "❌ 断言失败：porcelain 报孤儿但磁盘无一存在，拒绝归档" >&2
  exit 1
fi

# --- 归档提交：opt-worktree cp 指定文件 → worktree commit → main 还原(untracked→rm) ---
# area=housekeeping:archive-cases 与 standing optimization 方向分歧，开新/复用 housekeeping wt
ids=$(printf '%s, ' "${real[@]}" | sed 's/,\s*$//')
msg="归档 ${#real[@]} 个孤儿 case（跨项目轮次滞留 main untracked）: $ids"

bash "$SCRIPT_DIR/opt-worktree.sh" "$PROJECT" commit housekeeping:archive-cases "$msg" "${real[@]}"

# --- 自测：归档后 main 必无 untracked case-*.json ---
left=0
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  p="${line#???}"
  case "$p" in
    *" -> "*) p="${p##* -> }";;
  esac
  case "$p" in
    "$DECISIONS_REL"/case-*.json) left=$((left+1));;
  esac
done < <(git status --porcelain)

if (( left > 0 )); then
  echo "❌ 自测失败：归档后 $PROJECT main 仍剩 $left 个 untracked case-*.json" >&2
  exit 1
fi

echo "✓ 自测通过：$PROJECT main 干净，${#real[@]} 个 case 已入 housekeeping worktree 待合并"
