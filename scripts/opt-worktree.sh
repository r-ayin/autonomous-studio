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
#   opt-worktree.sh [project] install-hooks [--quiet]     # 装 core.hooksPath=hooks（fresh clone 须跑一次，让 pre-commit 守卫生效）；--quiet 供脚本化场景降噪（成功/缺文件均静默，仅写 config）
#   opt-worktree.sh [project] install-ref-hooks [repo...] # 把 reference-transaction 钩装到子项目仓（case-103 rollout；缺省扫兄弟 git 仓）
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
  # 恢复 d3a1a8e(merge-checkout-guard) 的 detached-HEAD 探测：5d0ed82(direction-meta-exclusion)
  # 基于旧基座构建，其 @@ -30,16 +30,8 @@ hunk 连带把本函数 revert 回盲目 'echo main'——master 项目里 main 不
  # 存在，cmd_merge 的 git checkout main 失败被 || true 吞、squash 提交进 detached HEAD 黑洞。
  local b repo="$1"
  # 正常情况：当前就在某分支上。
  b=$(git -C "$repo" symbolic-ref --short HEAD 2>/dev/null) && { echo "$b"; return; }
  # detached HEAD：symbolic-ref 失败，旧实现盲目回退 'main'——但 master 项目里
  # main 不存在，后续 git checkout main 失败被 || true 吞掉，merge 会在 detached
  # HEAD 上提交进黑洞。改为按 main→master 顺序取真实存在的分支，再兜底首个分支。
  for b in main master; do
    git -C "$repo" rev-parse --verify --quiet "refs/heads/$b" >/dev/null && { echo "$b"; return; }
  done
  b=$(git -C "$repo" for-each-ref --format='%(refname:short)' refs/heads 2>/dev/null | head -1)
  echo "${b:-main}"
}
MAIN_BRANCH="$(detect_main_branch "$PROJECT")"

area_of() { echo "${1%%:*}"; }
slug() { echo "$1" | tr ':' '-' | tr '/' '-'; }

# 防御性根因补强（与 4fcb8bc 互补，非冗余）：worktree 方向标记桩 .opt-direction 写入
# 工作区后，立即登记到该 worktree 专属 info/exclude，让 git 永不追踪它。4fcb8bc 在
# cmd_merge 落地前 unstage+删桩（merge 兜底），但部分 worktree 分支仍可能在 merge 前
# 误提交桩→各项目 main 历史泄漏（dingtalk-auto/x-tool/shizi/skills/1BfrYn9G 均有）。
# info/exclude 从源头阻断：标记留磁盘可读（opt-worktree 自身读它定 area），但 git
# add/commit 永不纳入。用 git --git-path 取 linked worktree 各自独立的 exclude 文件，幂等追加。
_ignore_opt_direction_marker() {
  local wt="$1"
  [[ -z "$wt" ]] && return 0
  local excl; excl=$(git -C "$wt" rev-parse --git-path info/exclude 2>/dev/null) || return 0
  [[ -n "$excl" && -f "$excl" ]] || return 0
  grep -qx -- ".opt-direction" "$excl" 2>/dev/null || printf '%s\n' ".opt-direction" >> "$excl"
}

ensure_main_wt() {
  local dir="$WT_BASE/optimization"
  if [[ ! -d "$dir" ]]; then
    mkdir -p "$WT_BASE"
    # 两次 worktree add 都失败时不得吞错继续——旧实现尾部 `|| true` 吞掉失败后，
    # 仍向 mkdir 建出的空 dir 写 .opt-direction 桩并打印「✓ 建 optimization worktree」，
    # 造成功假象；后续 cmd_commit 在非 worktree 上 cp/commit 必败且报错晦涩（审计发现，
    # 与 cmd_merge line471 失败即中止的纪律不一致）。改为校验：两次都败→清空 dir+中止。
    if ! git -C "$PROJECT" worktree add -b auto/optimization "$dir" "$MAIN_BRANCH" 2>/dev/null && \
       ! git -C "$PROJECT" worktree add "$dir" auto/optimization 2>/dev/null; then
      echo "❌ 建 optimization worktree 失败: $dir——检查 $MAIN_BRANCH 分支可用性 / auto/optimization 残留分支 / 路径权限。中止，未写 .opt-direction 桩。" >&2
      rmdir --ignore-fail-on-non-empty "$dir" 2>/dev/null || true
      exit 1
    fi
    echo "engine:general" > "$dir/.opt-direction"
    _ignore_opt_direction_marker "$dir"
    echo "✓ 建 optimization worktree: $dir"
  fi
}

current_area() {
  local dir="$WT_BASE/optimization"
  [[ -f "$dir/.opt-direction" ]] && area_of "$(cat "$dir/.opt-direction")" || echo "engine"
}

cmd_init() { ensure_main_wt; _install_hooks "${@:3}"; }

# 安装/校验 core.hooksPath=hooks（case-068 NEXT 可选 A 收口）。
# case-068 已在主仓 git config core.hooksPath=hooks，但 git config 不随提交传播——
# fresh clone（或新机器）须重跑本命令才能让 pre-commit 守卫生效。本函数幂等：
# 写 config + 校验 hooks/pre-commit 是否落地（未合并 optimization 前主仓无此文件，
# 仅告警不阻断——config 先就位，合并后钩子文件一落地即自动生效）。
# --quiet：脚本化/CI 场景降噪——成功与"缺文件（fresh clone 未合并 optimization 的
# 预期态）"均不打印，仅写 config 后 return 0；调用方信任 exit 0（本函数恒不阻断）。
_install_hooks() {
  local quiet=0
  [[ "${1:-}" == "--quiet" ]] && quiet=1
  local hook="$PROJECT/hooks/pre-commit"
  git -C "$PROJECT" config core.hooksPath hooks
  (( quiet )) && return 0
  if [[ -f "$hook" ]]; then
    echo "✓ core.hooksPath=hooks 已装；pre-commit 守卫生效（$hook 存在）"
  else
    echo "⚠ core.hooksPath=hooks 已装，但 $hook 不存在——主仓尚未合并 optimization（含 case-068 钩子）；合并后守卫自动生效"
  fi
}
cmd_install_hooks() { _install_hooks "${@:3}"; }

# install-ref-hooks — 把 reference-transaction 钩子批量装到子项目仓（case-103 rollout）
# 背景：case-103 的 hooks/reference-transaction 只护 autonomous-studio-aone 本仓 main；
#   case-047 实发于 shizi（CWD 漂移致 `git reset --hard` 误快进子项目 main，绕过
#   commit-gate）。各子项目仓须各自装钩才护——本子命令把引擎仓 hooks/reference-transaction
#   复制到目标仓生效的 hooks 目录（honors core.hooksPath，缺省 .git/hooks）+ chmod +x，
#   幂等（cmp 一致则跳过）。与 install-hooks 互补：install-hooks 只设 core.hooksPath=hooks
#   （引擎仓自身）；本子命令把 ref 守卫扩散到各子项目仓。
# 源钩须先在引擎仓存在（case-103 已在 optimization worktree 落地 hooks/reference-transaction；
#   未合并到 main 前须以本 worktree（或含该文件的 checkout）为 <project> 运行）；否则报错退出，
#   不静默装空。
# 用法: opt-worktree.sh <project> install-ref-hooks [repo1 repo2 ...]
#   project = 引擎仓（含 hooks/reference-transaction 源）
#   repoN   = 子项目仓路径（装钩目标）；缺省扫 $PROJECT/.. 下各 git 仓（跳过引擎自身）
cmd_install_ref_hooks() {
  local engine="$PROJECT"
  local src="$engine/hooks/reference-transaction"
  [[ -f "$src" ]] || { echo "❌ 引擎仓无 hooks/reference-transaction（case-103 未上 main？在 optimization worktree 内运行或先 merge auto/optimization）: $src" >&2; exit 1; }

  local repos=()
  if (( $# >= 3 )); then
    repos=( "${@:3}" )
  else
    # 缺省：扫引擎仓兄弟目录下各 git 仓（子项目），跳过引擎自身
    local d
    while IFS= read -r -d '' d; do
      [[ "$(cd "$d" && pwd -P)" == "$engine" ]] && continue
      git -C "$d" rev-parse --git-dir >/dev/null 2>&1 || continue
      repos+=( "$(cd "$d" && pwd -P)" )
    done < <(for d in "$engine"/../*/; do [[ -d "$d" ]] && printf '%s\0' "$d"; done)
  fi
  [[ ${#repos[@]} -gt 0 ]] || { echo "（未发现子项目仓；显式传路径：opt-worktree.sh <project> install-ref-hooks <repo>...）"; exit 0; }

  local installed=0 skipped=0 repo
  for repo in "${repos[@]}"; do
    [[ -d "$repo" ]] || { echo "⚠️ 跳过（非目录）: $repo" >&2; continue; }
    git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || { echo "⚠️ 跳过（非 git 仓）: $repo" >&2; continue; }
    # 生效的 hooks 目录：core.hooksPath 优先（相对仓根），否则 .git/hooks
    local hp hooksdir
    hp=$(git -C "$repo" config core.hooksPath 2>/dev/null || true)
    if [[ -n "$hp" ]]; then
      hooksdir="$repo/$hp"
    else
      hooksdir="$(git -C "$repo" rev-parse --absolute-git-dir)/hooks"
    fi
    mkdir -p "$hooksdir"
    local dst="$hooksdir/reference-transaction"
    if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then
      echo "✓ 已最新（跳过）: $(basename "$repo")  → $dst"
      skipped=$((skipped+1))
    else
      cp -p "$src" "$dst"
      chmod +x "$dst"
      echo "✓ 装钩: $(basename "$repo")  → $dst"
      installed=$((installed+1))
    fi
  done
  echo "install-ref-hooks 完成: 新装 $installed / 已最新 $skipped"
}

# 连带 revert 可见性守卫——抽成独立函数供 cmd_commit 与直接 worktree git commit
# 两路径共用（case-065 NEXT 收口：直接提交路径原本不经此守卫，是真实漏洞——近几轮
# engine 自指文件改 opt-worktree.sh 走直接 git commit，case-065 守卫从未被触发）。
# 在 cwd（须为含 HEAD 的 worktree/分支）对已 staged 改动做精确自检：本次 staged
# 删除行 ∩ 本分支相对 $MAIN_BRANCH 合并基的新增行（本分支自身已落地内容）→ 命中即警告。
# 命中说明正删掉一个仅存于本分支的守卫/修复行，极可能旧基座编辑致连带 revert
# （历史 b8458a6/5d0ed82 连 4 commit 毁掉 d3a1a8e/b476c86/5d0ed82 守卫，至 case-063/064
# 审计才发现）。不中止（避免误伤合法重构），把静默 revert 变可见——"审计才发现"→"提交即见"。
_assert_no_collateral_revert() {
  local _mb; _mb=$(git merge-base "$MAIN_BRANCH" HEAD 2>/dev/null || true)
  [[ -n "$_mb" ]] || return 0
  local _staged; _staged=$(git diff --cached --name-only 2>/dev/null || true)
  [[ -n "$_staged" ]] || return 0
  local _f _rm _add _overlap
  while IFS= read -r _f; do
    [[ -z "$_f" || "$_f" == ".opt-direction" ]] && continue
    _rm=$(git diff --cached -- "$_f" 2>/dev/null | grep -E '^-[^-]' | sed 's/^-//' || true)
    [[ -n "$_rm" ]] || continue
    _add=$(git diff "$_mb" HEAD -- "$_f" 2>/dev/null | grep -E '^\+[^+]' | sed 's/^+//' || true)
    [[ -n "$_add" ]] || continue
    _overlap=$(grep -F -x -f <(printf '%s\n' "$_add") <(printf '%s\n' "$_rm") || true)
    if [[ -n "$_overlap" ]]; then
      echo "⚠️ 连带-revert 疑似：$_f 删除了本分支已落地的行——若非有意请立即核对（case-063/064 根因，静默 revert 会毁已提交守卫）：" >&2
      echo "$_overlap" >&2
    fi
  done <<< "$_staged"
}

# 直接 worktree git commit 前的手动守卫入口：agent 在 worktree 内 git add 后、commit 前
# 跑 `opt-worktree.sh <project> precommit` 即得与 cmd_commit 同样的连带-revert 可见性。
# 不改 staged、不中止（与 _assert_no_collateral_revert 语义一致）。
cmd_precommit() { _assert_no_collateral_revert; }

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
      _ignore_opt_direction_marker "$target"
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
  local -a files=("${@:5}")   # 数组保留含空格的文件名（旧 "${@:5}" 拼成空格串再 for f in $files 会按 IFS 分词，空格文件名断裂）
  if [[ -z "$(git status --porcelain)" ]]; then
    echo "（无未提交改动，跳过）"
    return 0
  fi
  local head_before; head_before=$(git -C "$target" rev-parse HEAD)

  # ① 迁移改动到 target worktree
  # cp-overwrite 守卫（case-060）：target 文件若与 main HEAD 不同（前轮未合并的已提交改动），
  # cp 会静默抹掉。检测后跳过+警告，让人工 merge 后能察觉并补做；不中止整批避免阻塞正常流程。
  _cp_guard() {
    local src="$1" dst="$2"
    if [[ -e "$dst" ]]; then
      local main_rel; main_rel="${src#"$PROJECT"/}"
      # 比较 target 现有内容 vs main HEAD 同名文件——不同即 target 有 main 不具备的改动
      if ! git -C "$PROJECT" show "HEAD:$main_rel" >/dev/null 2>&1; then
        # main HEAD 无此文件。若 target 已 track 它（target ahead 含此文件未合并的新增），
        # cp main 工作区版本会抹掉 target 已提交内容（case-104 engine 自指文件类数据丢失风险）→ 跳过。
        # 仅当 target 也未 track（双方均新增）才安全覆盖。
        if git -C "$target" ls-files --error-unmatch "$main_rel" >/dev/null 2>&1; then
          echo "⚠️ cp-guard: $main_rel 在 main HEAD 不存在但 worktree 已 track（前轮未合并新增），跳过以避免覆盖 target 已提交内容。请人工 merge 后重做，或（engine 自指文件）直编 opt-wt 版本后 wt 内提交（case-104）。" >&2
          return 1
        fi
        : # main HEAD 无此文件 且 target 也未 track → 双方新增，安全覆盖（untracked 路径）
      elif ! cmp -s "$dst" <(git -C "$PROJECT" show "HEAD:$main_rel" 2>/dev/null); then
        echo "⚠️ cp-guard: $main_rel 在 worktree 与 main HEAD 不同（前轮未合并改动），跳过以避免覆盖。请人工 merge 后重做。" >&2
        return 1
      fi
    fi
    mkdir -p "$(dirname "$dst")"
    cp -p "$src" "$dst"
    return 0
  }
  # deletion 守卫（case-021）：main 删除了 tracked 文件时，worktree 同步删除。
  # 但 worktree 该文件若与 main HEAD 不同（前轮未合并改动），删除会抹掉 pending →
  # 跳过+警告，与 _cp_guard 同语义（case-060）。返回 0=已同步删除，1=跳过。
  _del_guard() {
    local src="$1" dst="$target/$1"
    if [[ -e "$dst" ]]; then
      local main_rel; main_rel="${src#"$PROJECT"/}"
      if ! git -C "$PROJECT" show "HEAD:$main_rel" >/dev/null 2>&1; then
        # main HEAD 无此文件——非"main 删除已提交文件"的合法同步场景
        #（main index 暂存新增但工作区已删，或 target 自有 ahead 新增）。
        # 此时 cmp 对照空流会让 target 空 tracked 文件误判"相同"进而 git rm
        # 删掉 target 自有已提交文件（case-106 _cp_guard ahead-only 漏洞的删除对称面）→ 跳过。
        echo "⚠️ del-guard: $main_rel 在 main HEAD 不存在（非合法删除同步），跳过以避免误删 worktree 自有 tracked 内容。请人工 merge 后重做，或（engine 自指文件）直编 opt-wt 版本后 wt 内提交（case-104）。" >&2
        return 1
      fi
      if ! cmp -s "$dst" <(git -C "$PROJECT" show "HEAD:$main_rel" 2>/dev/null); then
        echo "⚠️ del-guard: $main_rel 在 worktree 与 main HEAD 不同（前轮未合并改动），跳过删除以避免抹掉。请人工 merge 后重做。" >&2
        return 1
      fi
      git -C "$target" rm -f -- "$src" >/dev/null 2>&1 || rm -f "$dst"
    fi
    echo "→ 同步删除: $src"
    return 0
  }
  # cp-guard 跳过的文件清单：这些文件 main 现存改动与前轮未合并的 worktree 提交冲突，
  # 不 cp 不还原，原样保留在 main 工作区待人工 merge 后重做——杜绝 case-059/060 的静默抹掉。
  local -a skipped=()
  _is_skipped() {
    local x="$1" s
    for s in "${skipped[@]}"; do [[ "$s" == "$x" ]] && return 0; done
    return 1
  }
  local copied=0
  if [[ ${#files[@]} -gt 0 ]]; then
    local f
    for f in "${files[@]}"; do
      if [[ -e "$f" ]]; then
        _cp_guard "$f" "$target/$f" || { skipped+=("$f"); continue; }
      elif git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
        # main 删除了 tracked 文件 → worktree 同步删除（修 case-021：
        # 旧 [[ -e ]]||skip 在文件已删时跳过 cp，worktree git add -A 不复现 deletion，
        # 删除类清理静默丢失，须手动建 worktree 规避）
        _del_guard "$f" || { skipped+=("$f"); continue; }
      else
        echo "⚠️ 指定文件不存在且非 tracked，跳过: $f" >&2
        continue
      fi
      copied=$((copied+1))
    done
  else
    echo "⚠️ 未指定文件列表，cp 全部改动（含用户 WIP 风险，建议显式传文件）" >&2
    local p
    while IFS= read -r -d '' p; do
      p="${p#???}"               # 去掉前导 "XY "（status 2 字符 + 空格）
      case "$p" in *" -> "*) p="${p##* -> }";; esac   # rename 取新路径
      if [[ -e "$p" ]]; then
        _cp_guard "$p" "$target/$p" || { skipped+=("$p"); continue; }
      elif git ls-files --error-unmatch "$p" >/dev/null 2>&1; then
        # 同步 tracked 文件删除（与显式文件分支同修复，见 case-021）
        _del_guard "$p" || { skipped+=("$p"); continue; }
      fi
      copied=$((copied+1))
    done < <(git status --porcelain -z)
  fi
  # 全部文件被 cp-guard 跳过（或不存在）→ 无内容可提交。当前 .opt-direction 被
  # .gitignore 忽略，故 `git add -A` 不 stage 任何真改动，`git commit` 随即以
  # "nothing to commit" 硬失败（set -e abort）——报错晦涩易被误读为脚本故障。
  # 更危险：若日后 .opt-direction 被移出 .gitignore，`git add -A` 会 stage 方向桩，
  # 生成 .opt-direction-only 空提交，head-advance 断言因 HEAD 前进而通过 → 误报成功
  # （历史 de5728b 即此症）。故 cp 前置守卫：copied=0 直接 warn+exit，不进 ②。
  if (( copied == 0 )); then
    echo "⚠️ 无文件被实际迁移（全部被 cp-guard 跳过或不存在）——无内容可提交，中止，不生成空提交。被跳过文件 main 改动已保留，请人工 merge 对应 worktree 后重做。" >&2
    if (( ${#skipped[@]} > 0 )); then echo "   跳过文件: ${skipped[*]}" >&2; fi
    exit 1
  fi

  # ② worktree 内提交
  cd "$target"
  git add -A
  # .opt-direction 是 worktree 方向标记桩（untracked 元数据，cmd_new 写入），永不进提交——
  # 恢复 5d0ed82(direction-meta-exclusion) 的剔除逻辑：b476c86(show-truncation-guard) 基于旧基座
  # 构建，其 @@ -126,10 +126,6 @@ hunk 连带删除此行。git add -A 历史上把 .opt-direction 暂存、3 次泄漏
  # 进 shizi/x-tool/opt-docs 提交需 chore 清理；此处显式从索引剔除（已 tracked 则 untrack，
  # 工作树文件保留供 cmd_show 读，未 tracked 则 --ignore-unmatch no-op）。
  git rm -r --cached -q --ignore-unmatch -- .opt-direction 2>/dev/null || true
  # ⑤ 连带 revert 可见性守卫（case-063/064 根因防线，case-065 抽成共用函数）
  _assert_no_collateral_revert
  git -c user.name="autonomous-studio" -c user.email="syp02536326@taobao.com" commit -q -m "opt($direction): $msg

[auto-optimization on worktree $(basename "$target") — 待人工审合并]"

  # ③ 还原 main：tracked → checkout HEAD；untracked 新文件 → rm（已 cp 走）
  cd "$PROJECT"
  if [[ ${#files[@]} -gt 0 ]]; then
    local f2
    for f2 in "${files[@]}"; do
      _is_skipped "$f2" && { echo "⏸ cp-guard 跳过 $f2：保留 main 改动待人工 merge 后重做（不抹除）" >&2; continue; }
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
      _is_skipped "$p2" && { echo "⏸ cp-guard 跳过 $p2：保留 main 改动待重做" >&2; continue; }
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
  # leak 断言排除 cp-guard 跳过的文件——它们按设计保留在 main（未 cp 未还原），不算泄漏
  local leak=""
  if [[ ${#files[@]} -gt 0 ]]; then
    local -a kept=() ff
    for ff in "${files[@]}"; do _is_skipped "$ff" || kept+=("$ff"); done
    if [[ ${#kept[@]} -gt 0 ]]; then
      leak=$(git status --porcelain -- "${kept[@]}")   # "${kept[@]}" 全展开（旧 -- $files 在 files 改数组后仅展开首元素→漏检其余文件的残留改动）
    fi
  else
    local _line _path
    while IFS= read -r _line; do
      [[ -z "$_line" ]] && continue
      _path="${_line#???}"
      case "$_path" in *" -> "*) _path="${_path##* -> }";; esac
      _is_skipped "$_path" && continue
      leak+="${_line}"$'\n'
    done < <(git status --porcelain)
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
  # head -300 截断时必须告知审阅者有遗漏——5+ 提交的 worktree diff 常超 300 行，
  # 静默截断会让合并门禁审阅漏看改动。先量总行数，截断时打印省略量 + 完整 diff 命令。
  # （b476c86 引入此守卫；b8458a6 基于 b476c86 之前的旧基座构建，diff 连带 revert 了
  # 此 hunk，后续提交均未恢复——本 commit 修复该静默回归。）
  local total
  total=$(git -C "$dir" diff "$MAIN_BRANCH"...HEAD 2>/dev/null | wc -l)
  total="${total// /}"
  git -C "$dir" diff "$MAIN_BRANCH"...HEAD 2>/dev/null | head -300
  if [[ "$total" =~ ^[0-9]+$ ]] && (( total > 300 )); then
    echo "...（diff 共 ${total} 行，仅显示前 300 行——完整 diff: git -C \"$dir\" diff \"$MAIN_BRANCH\"...HEAD）"
  else
    echo "..."
  fi
  echo "审完: opt-worktree.sh merge \"$PROJECT\" \"$wt\"   或   opt-worktree.sh reject \"$PROJECT\" \"$wt\""
}

cmd_merge() {
  local wt="${3:?need worktree}"
  local dir="$WT_BASE/$wt"
  [[ -d "$dir" ]] || { echo "❌ worktree 不存在: $wt"; exit 1; }
  cd "$PROJECT"
  # 切回主分支准备合并。恢复 d3a1a8e(merge-checkout-guard) 的失败即中止：5d0ed82 基于旧基座
  # 构建，其 diff 连带把此行 revert 回 `|| true` 吞掉错误——checkout 失败（detached HEAD + 探测
  # 出错分支、或工作区脏）绝不能被吞，否则 merge 会在错的 HEAD 上 squash 提交进黑洞。失败即中止。
  if ! git checkout "$MAIN_BRANCH" 2>/dev/null; then
    echo "❌ 切回 $MAIN_BRANCH 失败（detached HEAD？工作区脏？分支不存在？），中止合并，未改动 $PROJECT"
    exit 1
  fi
  if git merge --squash "auto/$(basename "$dir")" 2>/dev/null || git merge --squash "$wt" 2>/dev/null; then
    # .opt-direction 是 worktree 本地方向标记桩（untracked 为主，部分 worktree 分支误提交了它）。
    # git merge --squash 把分支差异整批暂存进 main，含此桩 → 历史上每次 merge 都把 .opt-direction
    # 泄漏到 main（dingtalk-auto/x-tool/shizi/skills 等均有「移除泄漏的 .opt-direction」chore 跟在
    # merge 后）。落地前剔除：已暂存则 unstage，工作区有则删，保证 main 不带 worktree 内部元数据。
    if git diff --cached --name-only -- .opt-direction 2>/dev/null | grep -q .; then
      git reset -q HEAD .opt-direction 2>/dev/null || true
      git rm --cached --quiet .opt-direction 2>/dev/null || git restore --staged .opt-direction 2>/dev/null || true
    fi
    rm -f "$PROJECT/.opt-direction"
    git -c user.name="autonomous-studio" -c user.email="syp02536326@taobao.com" commit -q -m "merge: 人工批准合并 optimization worktree '$wt'

$(git log --oneline "$MAIN_BRANCH"..auto/$(basename "$dir") 2>/dev/null | head -5)"
    # ↑ 只列 worktree 相对 main 的 ahead 提交（本 worktree 真实贡献）。旧 `git log --oneline auto/...`
    # 从根起 log 整条分支史，会把 main 已有提交灌进合并消息正文（实测 873f688 正文混入
    # 2aa0eba/0a2124d/4dc2565 等 main 提交，仅 734512b 属该 worktree），误导审阅。
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

# 清理空 opt worktree：commits-ahead=0（建了分支但从没落地提交）的 worktree 是死桩，
# 污染 scout-scan「需人工合并」列表（曾 11/16 项目各有一个空 optimization worktree，
# 0 提交却被当成待合并，致全管线误报「全部 blocked」）。
# 安全：只删 ahead=0 且无未提交改动的；有真提交或脏工作区的一律跳过。可逆：删的只是
# worktree + auto/<name> 分支，main 不动，需要时可 reinit。
cmd_cleanup() {
  local removed=0 skipped=0
  for d in "$WT_BASE"/*; do
    [[ -d "$d" ]] || continue
    local name; name=$(basename "$d")
    [[ "$name" == "_indexes" ]] && continue
    local ahead dirty status_out line
    ahead=$(git -C "$d" rev-list --count "$MAIN_BRANCH"..HEAD 2>/dev/null || echo 0)
    # .opt-direction 是每个 worktree 的方向标记桩（untracked），非真改动，剔后再判脏。
    status_out=$(git -C "$d" status --porcelain 2>/dev/null || true)
    dirty=0
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      [[ "$line" == "?? .opt-direction" ]] && continue
      dirty=$((dirty + 1))
    done <<< "$status_out"
    if [[ "$ahead" != "0" || "$dirty" != "0" ]]; then
      skipped=$((skipped + 1))
      continue
    fi
    git -C "$PROJECT" worktree remove "$d" --force 2>/dev/null || rm -rf "$d"
    git -C "$PROJECT" branch -D "auto/$name" 2>/dev/null || true
    echo "✓ 清理空 worktree: $name（0 提交，死桩）"
    removed=$((removed + 1))
  done
  echo "清理完成: 删 $removed / 跳 $skipped（有真提交或未提交改动）"
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

case "$CMD" in
  init) cmd_init "$@" ;;
  commit) cmd_commit "$@" ;;
  list) cmd_list ;;
  show) cmd_show "$@" ;;
  merge) cmd_merge "$@" ;;
  reject) cmd_reject "$@" ;;
  cleanup) cmd_cleanup ;;
  next-case) cmd_next_case "$@" ;;
  precommit) cmd_precommit ;;
  install-hooks) cmd_install_hooks "$@" ;;
  install-ref-hooks) cmd_install_ref_hooks "$@" ;;
  *) echo "用法: opt-worktree.sh <project> <init|commit|list|show|merge|reject|cleanup|next-case|precommit|install-hooks|install-ref-hooks> ..."; exit 1 ;;
esac