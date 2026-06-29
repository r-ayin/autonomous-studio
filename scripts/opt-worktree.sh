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
#   opt-worktree.sh [project] next-case                   # 查下一个可用 case 编号（扫 main + 所有 pending worktree，防撞号）
#   opt-worktree.sh [project] new-case                    # 分配并原子预留 case 文件（写空 stub 落盘，杜绝 agent 手挑号撞号）
# 例: opt-worktree.sh shizi commit "docs:governance" "说明" PROGRESS.md GATES.md
set -euo pipefail

PROJECT="${1:-.}"
CMD="${2:-list}"
# Fail-fast: 当 PROJECT 不是目录时立即报错，避免把 'next-case' 等命令误当路径
# （曾致 'cd: next-case: No such file or directory'：用户省略 project 但写了 command，
#  $1 被当作 PROJECT，CMD 落到默认 list，再 cd "$PROJECT" 失败且无提示）。
if [[ ! -d "$PROJECT" ]]; then
  echo "错误: '$PROJECT' 不是目录。用法: opt-worktree.sh [project] <init|commit|list|show|merge|reject|next-case|new-case>" >&2
  exit 2
fi
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
  # 弃用 git stash（phantom-stash 误报根因，见 case-028/029/030/032/004 +
  #   [[opt-worktree-stash-silent-failure]]）：`git stash push -u -- <pathspec>`
  #   当 pathspec 只命中 untracked 新文件时，git 报 "No local changes to save" 且 exit 0
  #   但不产 stash；随后 `git stash pop` 无 stash 可弹 exit 1 → 被误报成
  #   "stash apply 冲突，改动留在 stash" —— 实则无 stash、改动滞留 main、worktree 无 commit。
  # 改显式 cp：①指定文件 cp 到 target → ②worktree add+commit → ③main 还原
  #   (tracked → checkout HEAD / untracked 新文件 → rm) → ④断言 worktree 有新 commit 且 main 干净
  cd "$PROJECT"
  local files="${@:5}"
  if [[ -z "$(git status --porcelain)" ]]; then
    echo "（无未提交改动，跳过）"
    return 0
  fi
  local head_before; head_before=$(git -C "$target" rev-parse HEAD)
  local copied=0

  # ① 迁移改动到 target worktree
  if [[ -n "$files" ]]; then
    local f
    for f in $files; do
      [[ -e "$f" ]] || { echo "⚠️ 指定文件不存在，跳过: $f" >&2; continue; }
      mkdir -p "$target/$(dirname "$f")"
      cp -p "$f" "$target/$f"
      copied=$((copied+1))
    done
  else
    echo "⚠️ 未指定文件列表，cp 全部改动（含用户 WIP 风险，建议显式传文件）" >&2
    local p
    while IFS= read -r -d '' p; do
      p="${p#???}"               # 去掉前导 "XY "（status 2 字符 + 空格）
      case "$p" in *" -> "*) p="${p##* -> }";; esac   # rename 取新路径
      [[ -e "$p" ]] || continue
      mkdir -p "$target/$(dirname "$p")"
      cp -p "$p" "$target/$p"
      copied=$((copied+1))
    done < <(git status --porcelain -z)
  fi

  # 前置断言：cp 命中 0 则拒绝产空 commit（case-207：file 参数全不存在/全被跳过时
  #   曾产仅 .opt-direction 的 bogus commit，且 ④ leak 断言因 $files 在 main 不存在
  #   而误报成功——case-033 漏堵的平行路径）
  if (( copied == 0 )); then
    echo "❌ 断言失败：无任何改动被 cp 到 worktree（命中 0），拒绝产空 commit。" >&2
    echo "  指定文件路径须 project-relative（相对 $PROJECT）。指定了: ${files:-（未指定，自动扫描全部改动）}" >&2
    exit 1
  fi

  # ② worktree 内提交
  cd "$target"
  local gitdir; gitdir=$(git rev-parse --git-dir)
  mkdir -p "$gitdir/info"
  echo ".opt-direction" >> "$gitdir/info/exclude"
  git add -A
  git -c user.name="autonomous-studio" -c user.email="opt@auto" commit -q -m "opt($direction): $msg

[auto-optimization on worktree $(basename "$target") — 待人工审合并]"

  # ③ 还原 main：tracked → checkout HEAD；untracked 新文件 → rm（已 cp 走）
  cd "$PROJECT"
  if [[ -n "$files" ]]; then
    local f2
    for f2 in $files; do
      if git ls-files --error-unmatch "$f2" >/dev/null 2>&1; then
        git checkout HEAD -- "$f2" 2>/dev/null || true   # tracked：还原到 HEAD
      else
        rm -f "$f2"                                       # untracked 新文件：删（已迁走）
      fi
    done
  else
    local p2
    while IFS= read -r -d '' p2; do
      p2="${p2#???}"
      case "$p2" in *" -> "*) p2="${p2##* -> }";; esac
      if git ls-files --error-unmatch "$p2" >/dev/null 2>&1; then
        git checkout HEAD -- "$p2" 2>/dev/null || true
      else
        rm -f "$p2"
      fi
    done < <(git status --porcelain -z)
  fi

  # ④ 断言：worktree 必有新 commit + 本次提交的文件在 main 必已还原（撞误报自动 fail 而非静默）
  #    注意只校验本次列入 $files 的文件，不要求整个工作区干净——main 可能含本次未涉及的 WIP/未跟踪文件。
  local head_after; head_after=$(git -C "$target" rev-parse HEAD)
  if [[ "$head_before" == "$head_after" ]]; then
    echo "⚠️ 断言失败：worktree 无新 commit（cp/commit 未生效），改动仍在 main" >&2
    exit 1
  fi
  local leak
  if [[ -n "$files" ]]; then
    leak=$(git status --porcelain -- $files)
  else
    leak=$(git status --porcelain)
  fi
  if [[ -n "$leak" ]]; then
    echo "⚠️ 断言失败：本次提交的文件在 main 仍有残留改动（还原未生效），人工核对：" >&2
    echo "$leak" >&2
    exit 1
  fi
  echo "✓ 提交到 $(basename "$target")  方向=$direction"
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
  # Fail-fast: main working tree 必须干净，否则 squash 会把脏文件混入 merge、失败后状态难恢复。
  # （曾致 opt-tooling-1782713441 merge 误报冲突：main 残留上轮同内容修改，squash 误判为 diverged；
  #   还原 dirty 文件后立即 merge 成功。）
  if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    echo "❌ main working tree 不干净，请先 commit/stash/restore 再 merge:" >&2
    git status --short >&2
    exit 1
  fi
  git checkout "$MAIN_BRANCH" 2>/dev/null || true
  # 分支命名约定（cmd_init）：auto/<worktree-dir-basename>（常设 worktree=auto/optimization，
  #   新 area worktree=auto/opt-<area>-<ts>）。直接 basename 即可。
  #   旧写法 sed 's/^opt-//;s/^/opt-/' 对 opt-* 名是恒等 noop（碰巧能用），但对常设
  #   optimization worktree 产出不存在的 auto/opt-optimization；其 fallback
  #   `git merge --squash "$wt"` 又用裸名（非 auto/ 前缀）也非有效 ref → 两路皆败 →
  #   误报"合并冲突"（case-223 发现，case-226 修）。
  if git merge --squash "auto/$(basename "$dir")" 2>/dev/null; then
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

# 取当天（或指定日）下一个可用 case 编号：扫 main 工作树 + 所有 pending opt worktree 的
# .claude/decisions/ 下 case-{date}-NNN.json，取 max+1。
# 关键：用 ls（盘上文件，含未提交/untracked），不用 git ls-tree（只看已提交）——
# 否则看不见 main 未提交的孤儿 case 文件（曾导致 036/037 撞号：main 仅见 002/003 已提交，
# 引擎再选 004 与 worktree 已存的 004-035 撞）。也扫 pending worktree（case 常写在那）。
cmd_next_case() {
  local date="${3:-$(date +%Y-%m-%d)}"
  local pat="case-${date}-"
  local max=0 n f d
  # 收集所有该扫的 decisions 目录：main + 每个 pending opt worktree
  local dirs=( "$PROJECT/.claude/decisions" )
  for d in "$WT_BASE"/*/; do
    [[ -d "${d}.claude/decisions" ]] && dirs+=( "${d}.claude/decisions" )
  done
  for d in "${dirs[@]}"; do
    for f in "$d"/${pat}*.json; do
      [[ -e "$f" ]] || continue
      n="${f##*${pat}}"            # 去掉前缀（含路径）
      n="${n%.json}"               # 去后缀
      [[ "$n" =~ ^[0-9]+$ ]] || continue
      # 10# 强制十进制：否则前导零被当八进制（037→31，008/009 报错），编号算错
      if (( 10#$n > max )); then max=$((10#$n)); fi
    done
  done
  local next=$((max+1))
  printf -v next3 "%03d" "$next"
  echo "case-${date}-${next3}.json"
}

# new-case: 分配并原子预留 case 文件（落空 stub），杜绝 agent 手挑号撞号。
# 根治 case-id 撞号：next-case 只查号不预留，agent 仍可绕开自挑（case-034/263 均如此）；
# new-case 在同一进程内 scan→create（noclobber=O_CREAT|O_EXCL），stub 落盘即被后续
# 扫描计入，并发两调用各得不同号。agent 拿到路径后覆写 stub 为真实 case 内容。
cmd_new_case() {
  local date="${3:-$(date +%Y-%m-%d)}"
  local name f n
  name=$(cmd_next_case "$@")                       # case-<date>-NNN.json (basename)
  f="$PROJECT/.claude/decisions/$name"
  mkdir -p "$(dirname "$f")"
  # noclobber: 文件已存在则 > 失败 → 增号重试（仅极并发撞号才到这，正常一次成）
  while ! ( set -o noclobber; : > "$f" ) 2>/dev/null; do
    n="${name#case-${date}-}"; n="${n%.json}"; n=$((10#$n + 1))
    printf -v name "case-%s-%03d.json" "$date" "$n"
    f="$PROJECT/.claude/decisions/$name"
  done
  echo "$f"
}

case "$CMD" in
  init) cmd_init ;;
  commit) cmd_commit "$@" ;;
  list) cmd_list ;;
  show) cmd_show "$@" ;;
  merge) cmd_merge "$@" ;;
  reject) cmd_reject "$@" ;;
  next-case) cmd_next_case "$@" ;;
  new-case) cmd_new_case "$@" ;;
  *) echo "用法: opt-worktree.sh <project> <init|commit|list|show|merge|reject|next-case|new-case> ..."; exit 1 ;;
esac