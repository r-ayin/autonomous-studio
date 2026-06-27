#!/usr/bin/bash
# opt-worktree.sh — 自动优化 worktree 管理器
#
# 设计（用户定）:
#   引擎的自动研究/修复/优化 → 全部进 optimization worktree（不碰 main）
#   → 等人工回复才合并（人看 diff 决定）→ 优化可大胆执行，main 永远安全
#   → 方向差距大时（不同 area）自动开新 worktree，避免方向纠缠
#
# 方向分歧判定（2 层）:
#   direction 格式 "area:subdirection"（如 "engine:distillation"、"moni:quant"）
#   新优化 area == 主 worktree area → 同一 worktree（小差距，累积）
#   新优化 area != 主 worktree area → 开新 worktree auto/opt-{area}-{ts}（大差距，隔离）
#
# 用法（project 在前、command 在后；project 缺省为 .，与底部 case 的提示一致）:
#   opt-worktree.sh [project] init                        # 建主 optimization worktree
#   opt-worktree.sh [project] commit <direction> <msg> [file...]  # 按方向提交到合适 worktree（指定文件避免扫 WIP）
#   opt-worktree.sh [project] list                        # 列所有 opt worktree + 方向 + diffstat
#   opt-worktree.sh [project] show [worktree]             # 给人审：看 diff（不合并）
#   opt-worktree.sh [project] merge <worktree>            # 人工批准后：squash 合并→main + 清理
#   opt-worktree.sh [project] reject <worktree>           # 人工拒绝：归档/删
# 例: opt-worktree.sh shizi commit "docs:governance" "说明" PROGRESS.md GATES.md
set -euo pipefail

PROJECT="${1:-.}"
CMD="${2:-list}"
PROJECT="$(cd "$PROJECT" && pwd)"
# per-project 子目录，避免多项目 worktree 撞车（之前 $PROJECT/../.opt-worktrees 共享导致跨项目冲突）
WT_BASE="$PROJECT/../.opt-worktrees/$(basename "$PROJECT")"
# 动态探测项目默认分支：x-tool/moni 用 master，autonomous-studio 用 main。
# 硬编码 main 会导致 master 项目 worktree add 失败被 || true 吞、随后写 .opt-direction 崩。
detect_main_branch() {
  local b
  b=$(git -C "$1" symbolic-ref --short HEAD 2>/dev/null) || { echo main; return; }
  echo "${b:-main}"
}
MAIN_BRANCH="$(detect_main_branch "$PROJECT")"

area_of() { echo "${1%%:*}"; }
slug() { echo "$1" | tr ':' '-' | tr '/' '-'; }

ensure_main_wt() {
  local dir="$WT_BASE/optimization"
  if [[ ! -d "$dir" ]]; then
    mkdir -p "$WT_BASE"
    git -C "$PROJECT" worktree add -b auto/optimization "$dir" "$MAIN_BRANCH" 2>/dev/null || \
      git -C "$PROJECT" worktree add "$dir" auto/optimization 2>/dev/null || true
    echo "engine:general" > "$dir/.opt-direction"
    echo "✓ 建 optimization worktree: $dir"
  fi
}

current_area() {
  local dir="$WT_BASE/optimization"
  [[ -f "$dir/.opt-direction" ]] && area_of "$(cat "$dir/.opt-direction")" || echo "engine"
}

cmd_init() { ensure_main_wt; }

cmd_commit() {
  local direction="${3:?need direction}"
  local msg="${4:?need commit message}"
  ensure_main_wt
  local cur_area; cur_area=$(current_area)
  local new_area; new_area=$(area_of "$direction")

  # 选目标 worktree：方向 area 一致 → 主 worktree；不一致 → 复用或开新
  local target
  if [[ "$cur_area" == "$new_area" ]]; then
    target="$WT_BASE/optimization"
  else
    # 先找已有的同 area worktree 复用，没有才建新（避免同方向开一堆 worktree）
    # 注意：ls 无匹配时 exit 2，在 `set -euo pipefail` 下会经由管道 abort cmd_commit
    # （曾导致新 area 首次提交静默失败 exit 2、改动留在 main）。用 `|| true` 中和。
    local existing
    existing=$( { ls -d "$WT_BASE"/opt-$(slug "$new_area")-* 2>/dev/null || true; } | head -1 )
    if [[ -n "$existing" ]]; then
      target="$existing"
      echo "→ 复用同 area worktree: $(basename "$target")"
    else
      local ts; ts=$(date +%s)
      target="$WT_BASE/opt-$(slug "$new_area")-$ts"
      mkdir -p "$target"
      git -C "$PROJECT" worktree add -b "auto/opt-$(slug "$new_area")-$ts" "$target" "$MAIN_BRANCH" 2>/dev/null
      echo "$direction" > "$target/.opt-direction"
      echo "↔ 方向分歧（$cur_area → $new_area），开新 worktree: $(basename "$target")"
    fi
  fi

  # 把当前工作区改动同步到 target worktree 提交
  # 策略：若有文件列表（$5+），只 stash 指定文件（避免扫进用户 WIP）；否则 stash 全部（dirty=0 时安全）
  cd "$PROJECT"
  local files="${@:5}"
  if [[ -n "$(git status --porcelain)" ]]; then
    if [[ -n "$files" ]]; then
      git stash push -u -m "opt-$direction" -- $files >/dev/null 2>&1
    else
      echo "⚠️ 未指定文件列表，stash 全部改动（若项目有用户 WIP 会被一并扫进 worktree）" >&2
      git stash push -u -m "opt-$direction" >/dev/null 2>&1
    fi
    cd "$target"
    git stash pop >/dev/null 2>&1 || { echo "⚠️ stash apply 冲突，改动留在 stash，人工处理"; exit 1; }
    git add -A
    git -c user.name="autonomous-studio" -c user.email="opt@auto" commit -q -m "opt($direction): $msg

[auto-optimization on worktree $(basename "$target") — 待人工审合并]"
    echo "✓ 提交到 $(basename "$target")  方向=$direction"
  else
    echo "（无未提交改动，跳过）"
  fi
}

cmd_list() {
  echo "=== optimization worktrees ==="
  for d in "$WT_BASE"/*; do
    [[ -d "$d" ]] || continue
    local name; name=$(basename "$d")
    local dir; dir=$(cat "$d/.opt-direction" 2>/dev/null || echo "?")
    local stat
    stat=$(git -C "$d" diff --stat "$MAIN_BRANCH" 2>/dev/null | tail -1)
    local commits
    commits=$(git -C "$d" rev-list --count "$MAIN_BRANCH"..HEAD 2>/dev/null || echo 0)
    echo "  $name | 方向=$dir | $commits 提交 | ${stat:-(无 diff)}"
  done
}

cmd_show() {
  local wt="${3:-optimization}"
  local dir="$WT_BASE/$wt"
  [[ -d "$dir" ]] || { echo "❌ worktree 不存在: $wt"; exit 1; }
  echo "=== $wt 的优化 diff（待人工审）==="
  echo "方向: $(cat "$dir/.opt-direction" 2>/dev/null)"
  echo "提交:"
  git -C "$dir" log --oneline "$MAIN_BRANCH"..HEAD 2>/dev/null
  echo "--- diff ---"
  git -C "$dir" diff "$MAIN_BRANCH"...HEAD 2>/dev/null | head -300
  echo "..."
  echo "审完: opt-worktree.sh merge \"$PROJECT\" \"$wt\"   或   opt-worktree.sh reject \"$PROJECT\" \"$wt\""
}

cmd_merge() {
  local wt="${3:?need worktree}"
  local dir="$WT_BASE/$wt"
  [[ -d "$dir" ]] || { echo "❌ worktree 不存在: $wt"; exit 1; }
  cd "$PROJECT"
  git checkout "$MAIN_BRANCH" 2>/dev/null || true
  if git merge --squash "auto/$(basename "$dir" | sed 's/^opt-//;s/^/opt-/')" 2>/dev/null || git merge --squash "$wt" 2>/dev/null; then
    git -c user.name="autonomous-studio" -c user.email="opt@auto" commit -q -m "merge: 人工批准合并 optimization worktree '$wt'

$(git log --oneline auto/$(basename "$dir") 2>/dev/null | head -5)"
    echo "✓ 已 squash 合并 $wt → $MAIN_BRANCH"
    git -C "$PROJECT" worktree remove "$dir" --force 2>/dev/null || rm -rf "$dir"
    echo "✓ worktree 清理"
  else
    echo "❌ 合并冲突，人工处理: cd $dir && 解决后 opt-worktree.sh merge"
    git merge --abort 2>/dev/null || true
    exit 1
  fi
}

cmd_reject() {
  local wt="${3:?need worktree}"
  local dir="$WT_BASE/$wt"
  [[ -d "$dir" ]] || { echo "❌ worktree 不存在: $wt"; exit 1; }
  git -C "$PROJECT" worktree remove "$dir" --force 2>/dev/null || rm -rf "$dir"
  git -C "$PROJECT" branch -D "auto/$(basename "$dir")" 2>/dev/null || true
  echo "✗ 已拒绝并删除 worktree: $wt（分支 auto/$(basename "$dir") 保留可恢复，或手动删）"
}

case "$CMD" in
  init) cmd_init ;;
  commit) cmd_commit "$@" ;;
  list) cmd_list ;;
  show) cmd_show "$@" ;;
  merge) cmd_merge "$@" ;;
  reject) cmd_reject "$@" ;;
  *) echo "用法: opt-worktree.sh <project> <init|commit|list|show|merge|reject> ..."; exit 1 ;;
esac