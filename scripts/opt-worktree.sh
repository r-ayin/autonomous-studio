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
# Fail-fast: 当 PROJECT 不是目录时立即报错，避免把 'next-case' 等命令误当路径
# （曾致 'cd: next-case: No such file or directory'：用户省略 project 但写了 command，
#  $1 被当作 PROJECT，CMD 落到默认 list，再 cd "$PROJECT" 失败且无提示）。
# 2026-06-30 case-345 从 root live 副本回graft AS main：root 独有此守卫，AS 缺，
# 整体 cp AS→root 会丢失它（[[opt-worktree-root-as-copy-drift]] 双向漂移收口）。
if [[ ! -d "$PROJECT" ]]; then
  echo "错误: '$PROJECT' 不是目录。用法: opt-worktree.sh [project] <init|commit|list|show|merge|reject|cleanup|next-case|new-case|precommit|install-hooks|install-ref-hooks>" >&2
  exit 2
fi
PROJECT="$(cd "$PROJECT" && pwd)"
# 嵌套根治（standing-wt-from-standing-wt，case-402）：从 standing optimization worktree
# 内跑本脚本时，PROJECT 落在 .opt-worktrees/<proj>/<wt> 内，下方 WT_BASE 会算成
# .../.opt-worktrees/<proj>/<wt>/../.opt-worktrees/<wt> → 双嵌到不存在的空壳目录，
# cmd init 会据此建伪 .opt-worktrees（[[opt-worktree-standing-wt-staleness]] 同源嵌套）。
# 上溯到 .opt-worktrees 之前的真 main checkout，让 WT_BASE 重新锚定真项目根。
case "$PROJECT" in
  */.opt-worktrees/*)
    _real_prefix="${PROJECT%%/.opt-worktrees/*}"   # .opt-worktrees 之前的工作区根
    _rest="${PROJECT#*/.opt-worktrees/}"            # <proj>/<wt>[/<sub>]
    _proj_name="${_rest%%/*}"                       # .opt-worktrees 下与 basename(PROJECT) 同名的真项目目录
    _candidate="$_real_prefix/$_proj_name"
    if [[ -d "$_candidate/.git" || -f "$_candidate/.git" ]]; then
      PROJECT="$_candidate"
    else
      echo "错误: 在 .opt-worktrees 内运行但找不到真 main checkout '$_candidate'——请从项目根目录跑本脚本" >&2
      exit 2
    fi
    ;;
esac
# per-project 子目录，避免多项目 worktree 撞车（之前 $PROJECT/../.opt-worktrees 共享导致跨项目冲突）
WT_BASE="$PROJECT/../.opt-worktrees/$(basename "$PROJECT")"
# json_escape <string>（case-368 security-review defense-in-depth）：audit_log 的
# reason/identifier/sha 经 printf %s 直拼 JSON，未转义 " 与 \。git refname 禁这些字符
# 故 branch 名派生值实践不可注入；但 $PROJECT 路径 / $(basename "$dir") 非 refname 受控，
# slug() 仅剥 : / 不剥 " \——含 " 会 corrupt JSONL 破 jq 解析。转义 \ " 及控制符保证输出
# 始终合法 JSON。不阻断主流程：空输入 / 异常均原样返回。
json_escape() {
  local s="${1:-}"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  printf '%s' "$s"
}
# audit_log <result> <worktree> <commit-sha|空> <reason>
# DO B（autonomous-constraints.md）：cmd_merge 是 deploy/变更合并敏感路径（git exec + 代码入 main），
# 落地与冲突均记 JSONL 审计日志，schema 对齐 .claude/decisions/audit-log.schema.json。append-only 写
# $PROJECT/.audit/audit-YYYY-MM-DD.jsonl（.audit/ 已 gitignore，不污染 main）。result 如实反映，不恒 success。
# 纯本地 JSONL，不新建库/不接外部系统。审计为可观测性，绝不阻断合并主流程（调用点带 || true）。
# case-368：wt/sha/reason 经 json_escape 后再拼 JSON，闭合 case-366 low 级 finding。
audit_log() {
  local result="$1" wt="$2" sha="$3" reason="$4"
  # action/resource_type 参数化（case-366）：cmd_merge 用默认 deploy/deployment；
  # cmd_reject/cmd_cleanup 删 worktree+分支是 delete/artifact（DO B 删除/批量敏感路径）。
  # 默认值保证既有 cmd_merge 两处调用（line 533/543）行为不变。
  local action="${5:-deploy}" rtype="${6:-deployment}"
  local aud_dir="$PROJECT/.audit" ts id_date rid fpath
  mkdir -p "$aud_dir" 2>/dev/null || return 0
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf '')"
  id_date="$(date -u +%Y%m%d-%H%M%S 2>/dev/null || printf '00000000-000000')"
  rid="$(od -An -tx1 -N3 /dev/urandom 2>/dev/null | tr -d ' \n' || printf '')"
  [[ ${#rid} -ge 6 ]] || rid="$(printf '%06d' "$RANDOM" 2>/dev/null || printf '000000')"
  fpath="$aud_dir/audit-$(date -u +%Y-%m-%d 2>/dev/null || printf '1970-01-01').jsonl"
  # action/rtype 为代码内 enum 字面量（调用方传 delete/artifact 等），不转义；
  # wt/sha/reason 含外部派生值，必转义。
  local wt_e sha_e reason_e
  wt_e="$(json_escape "$wt")"
  sha_e="$(json_escape "$sha")"
  reason_e="$(json_escape "$reason")"
  printf '{"id":"audit-%s-%s","timestamp":"%s","userId":"autonomous-engine","userRole":"engine","action":"%s","resource":{"type":"%s","identifier":"%s","newValue":"%s"},"result":"%s","ip":"local","sensitive":true,"sensitiveLevel":"high","details":{"reason":"%s"}}\n' \
    "$id_date" "$rid" "$ts" "$action" "$rtype" "$wt_e" "$sha_e" "$result" "$reason_e" >> "$fpath" 2>/dev/null || true
}
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
# M-001 fix (audit-2026-07-01-002): strip glob metacharacters to prevent
# ls -d "$WT_BASE"/opt-$(slug ...)-* from matching unintended worktrees when
# area contains * ? [ ]. Also strips shell-special chars for branch-name safety.
slug() { echo "$1" | tr ':' '-' | tr '/' '-' | tr -d '*?[]{}!()'; }

# direction_kind 判定（用户 2026-07-01 定）：审计深度解绑后，原 area-字符串相等判定太粗，
# 改用"是否触及项目公共接口文件"作为强信号——命中 = direction-shift（项目方向更新）→ 强制开新
# worktree 即便 area 同；不命中 = route-fix（原路线修复）→ 走原有 area 复用逻辑。
# 信号源：$PROJECT/.claude/public-interfaces.txt（相对项目根，避免目录改名/移动后硬编码失效；
# 旧版硬编码 /home/admin/workspace/autonomous-studio-aone/... 在目录改名后永远读不到 → direction-shift
# 判定静默降级为 route-fix → cp-guard 拦同文件后续改动 → 引擎卡死。audit-2026-07-01-002 M-003
# 派生时实踩此坑。）
#   每行 `<project_name>:<relative_path>`，# 注释，空行忽略。
# 文件不存在 → 默认 route-fix（向后兼容）。无 files 参数时扫 main 工作区 porcelain。
# 返回 stdout: "route-fix" | "direction-shift"
judge_direction_kind() {
  local proj="$1"; shift
  local -a files=("$@")
  local pi_file="$proj/.claude/public-interfaces.txt"
  [[ -f "$pi_file" ]] || { echo "route-fix"; return 0; }
  local proj_name; proj_name="$(basename "$proj")"
  # 若未传 files，扫 main 工作区改动
  if [[ ${#files[@]} -eq 0 ]]; then
    local p
    while IFS= read -r -d '' p; do
      # AS-EC-013 fix: porcelain -z 对 rename/copy (XY[0] = R|C) 输出两条 NUL record:
      #   "XY newpath\0oldpath\0"。原代码只剥前缀不消费 oldpath → 下一轮 read 把 oldpath
      #   当独立 record 读入，${p#???} 截断后混入 files 数组 → grep 误判 direction-shift。
      #   检测 XY[0] ∈ {R,C} 时额外 read -d '' 消费 oldpath record（丢弃）。
      local _xy="${p:0:2}"
      p="${p#???}"               # 去掉前导 "XY "（status 2 字符 + 空格）
      case "$_xy" in R?|C?) local _oldpath; IFS= read -r -d '' _oldpath || true ;; esac
      [[ -n "$p" ]] && files+=("$p")
    done < <(git -C "$proj" status --porcelain -z 2>/dev/null)
  fi
  [[ ${#files[@]} -eq 0 ]] && { echo "route-fix"; return 0; }
  # 项目名别名生成：public-interfaces.txt 可能用短名（如 autonomous-studio），
  # 而实际目录带后缀（如 autonomous-studio-aone）。生成候选列表依次尝试匹配。
  # 后缀列表覆盖常见开发仓命名约定；无命中则仅用原名（保持向后兼容）。
  local -a name_candidates=("$proj_name")
  local _suffix
  for _suffix in -aone -main -dev -repo -workspace; do
    if [[ "$proj_name" == *"${_suffix}" ]]; then
      name_candidates+=("${proj_name%"${_suffix}"}")
    fi
  done
  local f candidate
  for f in "${files[@]}"; do
    [[ -z "$f" ]] && continue
    for candidate in "${name_candidates[@]}"; do
      # 精确行匹配 "<proj>:<f>"
      if grep -qxF "${candidate}:${f}" "$pi_file" 2>/dev/null; then
        echo "direction-shift"
        return 0
      fi
    done
  done
  echo "route-fix"
  return 0
}


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
  else
    # standing worktree 在历次他枝 merge 后会落后 main（main 推进而本枝未 reset）。
    # 不纠正则下轮同 area cmd_commit 把新改动 cp 到过时内容上（基于旧文件提交，case-365）。
    # 仅当 auto/optimization 是 main 祖先（落后、无 ahead 提交）时 ff-only 快进；
    # 有 ahead 提交一律跳过——保住未合并工作，绝不丢改动（destructive reset 禁用）。
    # 真脏（未合并改动）由 git ff 自身拒绝兜底（非破坏），无需 porcelain 前置守卫。
    if git -C "$PROJECT" merge-base --is-ancestor auto/optimization "$MAIN_BRANCH" 2>/dev/null; then
      local mb_head cur
      mb_head=$(git -C "$PROJECT" rev-parse "$MAIN_BRANCH" 2>/dev/null)
      cur=$(git -C "$dir" rev-parse HEAD 2>/dev/null)
      if [[ -n "$mb_head" && -n "$cur" && "$mb_head" != "$cur" ]]; then
        # .opt-direction 是 worktree 本地方向标记桩（设计上 untracked+info/exclude 忽略）。
        # 但部分 legacy standing 分支曾误提交此桩（main 已 strip，本枝仍 tracked）→
        # ensure_main_wt 写磁盘方向后 git 报 ` M .opt-direction`→porcelain 非空；更甚 git ff
        # 自身因 tracked 文件有本地改动而拒绝（case-371 实踩 1BfrYW9R 966a60f）。若桩是唯一脏项
        # 且 tracked，做 cp/checkout/ff/restore 舞步解锁：桩非真改动绝不丢，与 cmd_commit
        # cp+断言哲学一致[[opt-worktree-stash-silent-failure]]，禁用 stash（静默失败高发）。
        local por non_marker marker_tracked=0 bak=""
        por=$(git -C "$dir" status --porcelain 2>/dev/null || true)
        if [[ -n "$por" ]]; then
          non_marker=$(printf '%s\n' "$por" | grep -vE '\.opt-direction$' || true)
          if [[ -z "$non_marker" ]] \
             && git -C "$dir" ls-files --error-unmatch .opt-direction >/dev/null 2>&1; then
            marker_tracked=1
          fi
        fi
        if [[ "$marker_tracked" == 1 ]]; then
          bak=$(mktemp 2>/dev/null) || true
          [[ -n "$bak" ]] && cp -f "$dir/.opt-direction" "$bak" 2>/dev/null || true
          git -C "$dir" checkout -- .opt-direction >/dev/null 2>&1 || true
        fi
        if git -C "$dir" merge --ff-only "$MAIN_BRANCH" >/dev/null 2>&1; then
          if [[ "$marker_tracked" == 1 ]]; then
            [[ -n "$bak" && -f "$bak" ]] && cp -f "$bak" "$dir/.opt-direction" 2>/dev/null || true
            rm -f "$bak" 2>/dev/null || true
            echo "↻ standing optimization worktree 快进至 $MAIN_BRANCH（$cur → $mb_head，.opt-direction 桩暂存还原解锁）"
          else
            echo "↻ standing optimization worktree 快进至 $MAIN_BRANCH（$cur → $mb_head，落后内容已同步）"
          fi
        else
          [[ -n "$bak" && -f "$bak" ]] && cp -f "$bak" "$dir/.opt-direction" 2>/dev/null || true
          rm -f "$bak" 2>/dev/null || true
          echo "⚠ standing optimization worktree 快进失败（已确认祖先仍失败？真脏由 git 拒绝兜底），跳过不阻断"
        fi
      fi
    fi
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
  # AS-EC-008 fix: 接受可选 $1 作为 git -C 目标目录，消除对 cwd 的隐式依赖。
  # 无参时行为不变（兼容 cmd_precommit 等外部调用方）。
  local _git_dir="${1:-}"
  local _mb; _mb=$(git ${_git_dir:+-C "$_git_dir"} merge-base "$MAIN_BRANCH" HEAD 2>/dev/null || true)
  [[ -n "$_mb" ]] || return 0
  local _staged; _staged=$(git ${_git_dir:+-C "$_git_dir"} diff --cached --name-only 2>/dev/null || true)
  [[ -n "$_staged" ]] || return 0
  local _f _rm _add _overlap
  while IFS= read -r _f; do
    [[ -z "$_f" || "$_f" == ".opt-direction" ]] && continue
    _rm=$(git ${_git_dir:+-C "$_git_dir"} diff --cached -- "$_f" 2>/dev/null | grep -E '^-[^-]' | sed 's/^-//' || true)
    [[ -n "$_rm" ]] || continue
    _add=$(git ${_git_dir:+-C "$_git_dir"} diff "$_mb" HEAD -- "$_f" 2>/dev/null | grep -E '^\+[^+]' | sed 's/^+//' || true)
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

# 删除路径名校验（case-382 security-review）：cmd_merge/reject/show 的 <worktree> 参数
# (CLI $3) 原样拼进 dir="$WT_BASE/$wt"，其中 cmd_merge(L569)/cmd_reject(L588) 有
# `git worktree remove "$dir" --force || rm -rf "$dir"` fallback。wt 未校验为 basename——
# 若传 `../`、`.` 或 `..`，`[[ -d "$dir" ]]` 命中遍历目标后 worktree remove 对未注册路径
# 失败，`|| rm -rf "$dir"` 即删遍历目标（删除敏感路径的路径遍历）。引擎自身只传 basename
# （cmd_list 输出），但删除路径须纵深防御：wt 须为纯 basename（非空、非 . / ..、不含 /）。
_validate_wt_name() {
  local wt="$1"
  if [[ -z "$wt" || "$wt" == "." || "$wt" == ".." || "$wt" == *"/"* ]]; then
    echo "❌ worktree 名非法（须为纯 basename，不含 /，非 . 或 ..）: '$wt'——拒绝以防 rm -rf 路径遍历（case-382）" >&2
    exit 1
  fi
}

# explore-log 回写（B-2 / 阶段③b EXPLORE v3.1）：探索类 worktree（direction 含 "hypothesis:"）
# 合并/拒绝时把 hypothesis + 结论追加到 planning/explore-log.md 研究档案。
# 修补类 worktree（无 hypothesis:）不记 explore-log，避免污染。
# 必须在 worktree 目录被删之前调用（要读 .opt-direction）。
# 用法: _explore_log_append <wt> <sha|空> <status> <conclusion>
#   status: verified / falsified / inconclusive / abandoned
_explore_log_append() {
  local wt="$1" sha="$2" status="$3" conclusion="${4:-}"
  local dir="$WT_BASE/$wt"
  local direction hyp=""
  direction=$(cat "$dir/.opt-direction" 2>/dev/null || printf '')
  # 提取 hypothesis:direction 格式 "area:subdirection | hypothesis: <文本>"
  case "$direction" in
    *"|"*) hyp="${direction##*|}"; hyp="${hyp# }";;
  esac
  # 仅探索类（含 hypothesis:）记录；修补类直接 return
  case "$direction" in
    *hypothesis:*) ;;
    *) return 0 ;;
  esac
  local elog="$PROJECT/planning/explore-log.md"
  mkdir -p "$(dirname "$elog")" 2>/dev/null || true
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf '?')
  {
    printf '\n## %s\n\n' "${hyp:-$direction}"
    printf -- '- 状态: %s\n' "$status"
    printf -- '- 时间: %s\n' "$ts"
    if [[ -n "$sha" ]]; then
      printf -- '- 证据: worktree=%s commit=%s\n' "$wt" "$sha"
    else
      printf -- '- 证据: worktree=%s（未合并）\n' "$wt"
    fi
    [[ -n "$conclusion" ]] && printf -- '- 结论: %s\n' "$conclusion"
    printf -- '- 下一步: 回写 BUSINESS-INTENT.md（verified→已验证假设 / falsified→已证伪假设 / inconclusive→派生新假设）\n'
  } >> "$elog" 2>/dev/null || true
}

# M-002 (audit-2026-07-01-002): cmd_commit 文件列表校验——拒绝绝对路径与含 .. 段的路径，
# 防 _cp_guard "$f" "$target/$f" + rm -f "$f" 对 f=`../../etc/cron.d/evil` 写/删 worktree 外文件。
# 纵深防御：即便引擎只传相对路径，也挡外部注入或手误。合法路径示例: scripts/foo.sh,
# .claude/hooks/bar.py；非法: /etc/passwd, ../sibling/x, a/../../b, ./../c。
_validate_commit_file_path() {
  local f="$1"
  if [[ -z "$f" ]]; then
    echo "❌ commit 文件路径为空——拒绝（M-002 防御）" >&2
    return 1
  fi
  # 绝对路径一律拒
  if [[ "$f" == /* ]]; then
    echo "❌ commit 文件路径为绝对路径，拒绝: '$f'（M-002 防路径遍历）" >&2
    return 1
  fi
  # 拆段检查 ..（避免 `a/../b`、`..`、`foo/..` 等任何形式）
  local IFS='/' seg
  for seg in $f; do
    if [[ "$seg" == ".." ]]; then
      echo "❌ commit 文件路径含 '..' 段，拒绝: '$f'（M-002 防路径遍历）" >&2
      return 1
    fi
  done
  return 0
}

cmd_commit() {
  local direction="${3:?need direction}"
  local msg="${4:?need commit message}"
  ensure_main_wt
  local cur_area; cur_area=$(current_area)
  local new_area; new_area=$(area_of "$direction")
  # direction_kind 判定（用户 2026-07-01）：触及公共接口文件 = direction-shift（强制新 worktree）
  # 不命中 = route-fix（原 area 复用逻辑）。files 是 ${@:5}（暂记，下方 cmd 流程还会重读）
  local -a _files_for_judgment=("${@:5}")
  local direction_kind; direction_kind=$(judge_direction_kind "$PROJECT" "${_files_for_judgment[@]}")
  # 审计修复（case-356）：跟踪本调用是否新建了分歧 worktree。copied=0 中止（line 352）
  # 时须回滚它，否则 git worktree add 建出的 opt-<area>-<ts> worktree+分支成孤儿，
  # 污染 git worktree list / scout-scan（case-353 残留 wt 漂移根因的分歧-wt 面；
  # optimization 持久 wt 由 ensure_main_wt 建、cmd_cleanup 可收，不在此列）。
  local created_new_wt=0
  local new_wt_branch=""

  # 选目标 worktree：direction-shift 优先（强制新 wt）> area 不一致 > area 一致复用 optimization
  local target
  if [[ "$direction_kind" == "direction-shift" ]]; then
    # 公共接口文件被改 → 项目方向更新，强制开新 worktree（即便 area 同）
    local ts; ts=$(date +%s)
    target="$WT_BASE/opt-$(slug "$new_area")-shift-$ts"
    new_wt_branch="auto/opt-$(slug "$new_area")-shift-$ts"
    mkdir -p "$target"
    # worktree add 失败不得吞错继续（audit-002 H-001）：旧实现尾部 `2>/dev/null` 吞掉失败后，
    # 仍向 mkdir 建出的空 dir 写 .opt-direction 桩并设 created_new_wt=1，造成功假象；后续
    # cmd_commit 在非 worktree 上 cp/commit 必败且报错晦涩。改为校验：失败→清空 dir+中止。
    if ! git -C "$PROJECT" worktree add -b "$new_wt_branch" "$target" "$MAIN_BRANCH" 2>/dev/null; then
      echo "❌ direction-shift 建 worktree 失败: $target——检查 $MAIN_BRANCH 可用性 / $new_wt_branch 残留分支 / 路径权限。中止，未写 .opt-direction 桩。" >&2
      rmdir --ignore-fail-on-non-empty "$target" 2>/dev/null || true
      exit 1
    fi
    echo "$direction" > "$target/.opt-direction"
    _ignore_opt_direction_marker "$target"
    created_new_wt=1
    echo "↔ direction-shift（触及公共接口文件，$cur_area → $new_area）→ 强制开新 worktree: $(basename "$target")"
  elif [[ "$direction" == *"hypothesis:"* ]]; then
    # ★ v3.1 探索类：direction 含 hypothesis: → 强制独立 worktree（研究方向隔离 +
    #   .opt-direction 存含 hypothesis 的全 direction，merge/reject 时 _explore_log_append
    #   能读到 hypothesis 回写 explore-log）。复用 optimization 会丢 hypothesis（其 .opt-direction
    #   不随复用更新）。每个 hypothesis 各自隔离，符合"探针"语义。
    local ts; ts=$(date +%s)
    target="$WT_BASE/opt-$(slug "$new_area")-explore-$ts"
    new_wt_branch="auto/opt-$(slug "$new_area")-explore-$ts"
    mkdir -p "$target"
    if ! git -C "$PROJECT" worktree add -b "$new_wt_branch" "$target" "$MAIN_BRANCH" 2>/dev/null; then
      rmdir --ignore-fail-on-non-empty "$target" 2>/dev/null || true
      echo "✗ 探索类 worktree add 失败（分支名撞？路径冲突？），已清空 husk: $(basename "$target")" >&2
      return 1
    fi
    echo "$direction" > "$target/.opt-direction"
    _ignore_opt_direction_marker "$target"
    created_new_wt=1
    echo "↔ 探索类（含 hypothesis，独立探针 worktree）→ 开新 worktree: $(basename "$target")"
  elif [[ "$cur_area" == "$new_area" ]]; then
    target="$WT_BASE/optimization"
  else
    # 先找已有的同 area worktree 复用，没有才建新（避免同方向开一堆 worktree）
    # 注意：ls 无匹配时 exit 2，在 `set -euo pipefail` 下会经由管道 abort cmd_commit
    # （曾导致新 area 首次提交静默失败 exit 2、改动留在 main）。用 `|| true` 中和。
    local existing
    existing=$( { ls -d "$WT_BASE"/opt-$(slug "$new_area")-* 2>/dev/null || true; } | head -1 )
    if [[ -n "$existing" ]]; then
      target="$existing"
      echo "→ 复用同 area worktree (route-fix): $(basename "$target")"
    else
      local ts; ts=$(date +%s)
      target="$WT_BASE/opt-$(slug "$new_area")-$ts"
      new_wt_branch="auto/opt-$(slug "$new_area")-$ts"
      mkdir -p "$target"
      # 失败须清 husk：worktree add 失败（分支名撞/路径冲突）时 mkdir 已建空目录，
      # set -e 下硬 abort 会留空 husk 累积（.opt-worktrees/<proj>/.opt-worktrees/opt-*，
      # 见 case-392 husk 清扫：5 个空壳，4 个源此路径）。失败 rmdir + return 1 让调用方感知。
      if ! git -C "$PROJECT" worktree add -b "$new_wt_branch" "$target" "$MAIN_BRANCH" 2>/dev/null; then
        rmdir --ignore-fail-on-non-empty "$target" 2>/dev/null || true
        echo "✗ worktree add 失败（分支名撞？路径冲突？），已清空 husk: $(basename "$target")" >&2
        return 1
      fi
      echo "$direction" > "$target/.opt-direction"
      _ignore_opt_direction_marker "$target"
      created_new_wt=1
      echo "↔ 方向分歧（$cur_area → $new_area，route-fix 新 area），开新 worktree: $(basename "$target")"
    fi
  fi

  # AS-EC-009 (audit-2026-07-02-002): worktree 级互斥锁——防并发 cmd_commit 同 target 损坏。
  # 场景：两个引擎实例同时 commit 到同一 route-fix worktree（或 direction-shift 撞 ts 概率极低但
  # optimization 持久 wt 复用常见）。无锁时 B 可能在 A 的 ①cp 之后 ③restore 之前进入，看到混合
  # 状态；或 A/B 同时 git add+commit 致 index 竞争 / HEAD 断言误报。flock 在 $target/.opt-lock
  # 上取排他锁，fd 9 持锁覆盖 ①-④ 整段临界区；函数返回（含 ERR trap 退出）时 fd 自动关闭释锁。
  # wait (-w) 默认阻塞等锁；不超时避免引擎轮次卡死——调用方（autonomous-loop）已有外层超时。
  local _lockfile="$target/.opt-lock"
  exec 9>"$_lockfile"
  if ! flock -x 9; then
    echo "❌ 无法获取 worktree 锁 $(basename "$target")/.opt-lock（另一 cmd_commit 持有？）——中止，main 改动保留未动" >&2
    exec 9>&-
    exit 1
  fi
  # 锁内再次校验 target 仍是有效 worktree（等锁期间可能被 cmd_cleanup/cmd_reject 移除）
  if [[ ! -d "$target/.git" && ! -f "$target/.git" ]]; then
    echo "❌ 等锁期间 target worktree 已失效: $(basename "$target")——中止，main 改动保留未动" >&2
    exec 9>&-
    exit 1
  fi

  # 把当前工作区改动同步到 target worktree 提交
  # 弃用 git stash（phantom-stash 误报根因，见 case-028/029/030/032/004 +
  #   [[opt-worktree-stash-silent-failure]]）：`git stash push -u -- <pathspec>`
  #   当 pathspec 只命中 untracked 新文件时，git 报 "No local changes to save" 且 exit 0
  #   但不产 stash；随后 `git stash pop` 无 stash 可弹 exit 1 → 被误报成
  #   "stash apply 冲突，改动留在 stash" —— 实则无 stash、改动滞留 main、worktree 无 commit。
  # 改显式 cp：①指定文件 cp 到 target → ②worktree add+commit → ③main 还原
  #   (tracked → checkout HEAD / untracked 新文件 → rm) → ④断言 worktree 有新 commit 且 main 干净
  # L-002 fix: cd $PROJECT 前将 files 规范化为相对 $PROJECT 的路径,防调用方 cwd ≠ $PROJECT 时
  # 传入的相对路径在 cd 后失效。先 realpath 到绝对(容忍调用方 cwd 相对路径),再 --relative-to
  # 折回 $PROJECT 相对路径——保证 git add/cp 在 worktree 里操作的是 scripts/foo.sh 而非绝对路径。
  # AS-EC-018 (audit-2026-07-02-002): realpath -m 会解析符号链接，当 $PROJECT 或文件路径含 symlink
  # 时，解析后的绝对路径与 $PROJECT 字面前缀不匹配 → --relative-to 产出含 .. 的路径 →
  # _validate_commit_file_path 拒绝。改用 -m -s（no-symlink-resolution）仅做词法规范化，
  # 保留对不存在文件的容忍（-m）同时避免 symlink 导致的路径错位。$PROJECT 也同步规范化确保基准一致。
  local _proj_norm; _proj_norm="$(realpath -m -s "$PROJECT" 2>/dev/null || echo "$PROJECT")"
  local -a _files_raw=("${@:5}")
  local -a _files_norm=()
  for _f in "${_files_raw[@]}"; do
    [[ -z "$_f" ]] && continue
    local _abs; _abs="$(realpath -m -s "$_f" 2>/dev/null || echo "$_f")"
    local _rel; _rel="$(realpath -m -s --relative-to="$_proj_norm" "$_abs" 2>/dev/null || echo "$_abs")"
    _files_norm+=("$_rel")
  done
  cd "$PROJECT"
  local -a files=("${_files_norm[@]}")   # 数组保留含空格的文件名（旧 "${@:5}" 拼成空格串再 for f in $files 会按 IFS 分词，空格文件名断裂）

  # State-only commit guard（audit-2026-07-01-002 follow-up，卡死保护补丁）：
  # fix-in-progress BLOCKED on human merge 时，引擎每轮仍会回写 autonomous-state / audit-cycle-state / case JSON，
  # 若允许这些纯状态文件进 worktree commit，会在 optimization 分支堆积无意义 state-sync commit
  # （实测 60 轮堆了 39 behind + 11 state commit），污染 diff、增加未来 merge 冲突面。
  # 检测：files 非空 且 全部命中 state-file 模式 → 拒绝提交，提示人工 merge。
  # 注：files 为空时走下方 git status 兜底（可能真有源码改动未显式列出），此处仅拦截显式声明的纯状态提交。
  if [[ ${#files[@]} -gt 0 ]]; then
    local _state_only=1
    for _f in "${files[@]}"; do
      case "$_f" in
        .claude/memory/autonomous-state.md) ;;
        .claude/audit-cycle-state.json) ;;
        .claude/decisions/case-*.json) ;;
        *) _state_only=0; break ;;
      esac
    done
    if [[ $_state_only -eq 1 ]]; then
      echo "⏸️  state-only commit blocked: 仅含引擎状态文件（autonomous-state/audit-cycle-state/case JSON），fix-in-progress BLOCKED 阶段禁止堆积 state-sync commit。请先人工 merge pending fixes，或本轮跳过 worktree 提交。" >&2
      return 0
    fi
  fi

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
  # state-only 文件预检（瞭望轮#79）：引擎状态回写文件（autonomous-state.md / audit-cycle-state.json /
  # decisions/case-*.json / audits/audit-*.md）按 MEMORY.md archival-commit-mechanism 应直提 main，
  # 不走 opt-worktree。早期瞭望轮误把它们 cp 进 optimization worktree 造成历史污染 + cp-guard
  # 累积跳过警告。命中此清单 → 跳过并提示调用方走直提路径；不 abort，让同批源码文件继续迁移。
  _is_state_only_file() {
    local p="$1"
    case "$p" in
      .claude/memory/autonomous-state.md) return 0 ;;
      .claude/audit-cycle-state.json) return 0 ;;
      .claude/decisions/case-*.json) return 0 ;;
      .claude/audits/audit-*.md) return 0 ;;
    esac
    return 1
  }
  local copied=0
  if [[ ${#files[@]} -gt 0 ]]; then
    local f
    for f in "${files[@]}"; do
      # M-002 (audit-2026-07-01-002): 路径安全预检——拒绝绝对路径/..遍历，
      # 防 _cp_guard + rm -f 写/删 worktree 外文件。校验失败跳过该文件（不 abort），
      # 让合法文件继续迁移；报错已含 finding id 便于追溯。
      _validate_commit_file_path "$f" || { skipped+=("$f"); continue; }
      _is_state_only_file "$f" && { echo "⏸ state-only skip: $f (按 archival-commit-mechanism 应直提 main，不进 worktree)" >&2; skipped+=("$f"); continue; }
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
      # AS-EC-014 fix: 与 judge_direction_kind 同症——rename/copy porcelain -z 双 record，
      # 不消费 oldpath → cp-guard 拿截断的 oldpath 当文件拷 → 要么报错、要么误拷同名文件。
      local _xy="${p:0:2}"
      p="${p#???}"               # 去掉前导 "XY "（status 2 字符 + 空格）
      case "$p" in *" -> "*) p="${p##* -> }";; esac   # rename 取新路径
      _is_state_only_file "$p" && { echo "⏸ state-only skip: $p (直提 main)" >&2; skipped+=("$p"); continue; }
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
    # 审计修复（case-356）：回滚本调用新建的分歧 worktree——copied=0 中止时它无任何提交内容，
    # 留下即成孤儿 wt+分支（污染 worktree list / scout-scan）。仅清本调用新建者，不动复用/
    # optimization 持久 wt。worktree remove --force 因 wt 无 commit 可净移；branch -D 删空分支。
    # DO B（autonomous-constraints.md）：此回滚是 delete 敏感路径（worktree remove --force +
    # branch -D），与 cmd_reject/cmd_cleanup 对称记 JSONL 审计日志（action=delete, resource=artifact）。
    # result 如实反映：worktree 目录已消失=success（branch -D best-effort，失败仅 reason 标注），
    # 仍在=failure。case-370 闭合全删除路径 audit_log 对称（merge/reject/cleanup/commit-rollback 四路径 LIVE）。
    if (( created_new_wt )) && [[ -n "$new_wt_branch" ]]; then
      git -C "$PROJECT" worktree remove --force "$target" 2>/dev/null || true
      git -C "$PROJECT" branch -D "$new_wt_branch" 2>/dev/null || true
      if [[ ! -d "$target" ]]; then
        audit_log success "$(basename "$target")" "" "rollback divergent worktree on copied=0 abort (no content migrated); branch $new_wt_branch -D (best-effort)" delete artifact || true
      else
        audit_log failure "$(basename "$target")" "" "rollback incomplete on copied=0 abort: $target still exists after remove --force" delete artifact || true
      fi
      echo "   已回滚本调用新建的分歧 worktree: $(basename "$target")（避免孤儿）" >&2
    fi
    exit 1
  fi

  # ② worktree 内提交
  # AS-EC-008 fix: 用 git -C 替代 cd "$target"，消除 cwd side effect。旧实现 cd 后若
  # git commit 失败（hook 拒绝/index lock/空提交等），cwd 留在 worktree；下次 cmd_commit
  # 从错的 cwd 起算相对路径 → stage orphaned files / 误覆盖。git -C 保证 cwd 始终在 $PROJECT。
  git -C "$target" add -A
  # .opt-direction 是 worktree 方向标记桩（untracked 元数据，cmd_new 写入），永不进提交——
  # 恢复 5d0ed82(direction-meta-exclusion) 的剔除逻辑：b476c86(show-truncation-guard) 基于旧基座
  # 构建，其 @@ -126,10 +126,6 @@ hunk 连带删除此行。git add -A 历史上把 .opt-direction 暂存、3 次泄漏
  # 进 shizi/x-tool/opt-docs 提交需 chore 清理；此处显式从索引剔除（已 tracked 则 untrack，
  # 工作树文件保留供 cmd_show 读，未 tracked 则 --ignore-unmatch no-op）。
  git -C "$target" rm -r --cached -q --ignore-unmatch -- .opt-direction 2>/dev/null || true
  # ⑤ 连带 revert 可见性守卫（case-063/064 根因防线，case-065 抽成共用函数）
  # AS-EC-008: 传 $target 让守卫在 worktree 上跑，不依赖 cwd。
  _assert_no_collateral_revert "$target"
  # AS-EC-008: commit 失败时清理已 cp 到 worktree 的文件，避免下次调用 stage orphaned content。
  # trap 仅在本地生效，commit 成功后 unset。清理策略：reset HEAD 取消暂存 + checkout 还原 tracked
  # 文件到 main HEAD 状态 + 删除 untracked 新文件。best-effort，失败仅 warn 不阻断报错传播。
  local _commit_failed_cleanup=""
  _commit_failed_cleanup='
    echo "⚠️ [AS-EC-008 cleanup] commit 失败，清理 worktree 已 cp 文件避免 orphan..." >&2
    git -C "$target" reset HEAD -- . >/dev/null 2>&1 || true
    # tracked 文件还原到 main HEAD（worktree 基于 main 分出，HEAD = main HEAD）
    git -C "$target" checkout HEAD -- . 2>/dev/null || true
    # untracked 新文件删除（cp 过来的新增文件不在 HEAD 中，checkout 不会碰）
    git -C "$target" clean -fd --quiet 2>/dev/null || true
    echo "   cleanup 完成（best-effort）" >&2
  '
  trap "$_commit_failed_cleanup" ERR
  if ! git -C "$target" -c user.name="autonomous-studio" -c user.email="syp02536326@taobao.com" commit -q -m "opt($direction): $msg

[auto-optimization on worktree $(basename "$target") — 待人工审合并]"; then
    # trap 已触发 cleanup；此处追加审计日志后退出。set -e 下 trap ERR 先于 exit 执行。
    audit_log failure "$(basename "$target")" "" "git commit failed after cp; orphan cleanup triggered (AS-EC-008)" commit artifact || true
    echo "❌ worktree commit 失败（已清理 orphaned files），cwd 保持 $PROJECT。请检查 hook/index lock/commit message。" >&2
    exit 1
  fi
  trap - ERR   # commit 成功，解除 cleanup trap

  # ③ 还原 main：tracked → checkout HEAD；untracked 新文件 → rm（已 cp 走）
  cd "$PROJECT"
  if [[ ${#files[@]} -gt 0 ]]; then
    local f2
    for f2 in "${files[@]}"; do
      _is_skipped "$f2" && { echo "⏸ cp-guard 跳过 $f2：保留 main 改动待人工 merge 后重做（不抹除）" >&2; continue; }
      # M-002 (audit-2026-07-01-002): 还原阶段同校验——非法路径既不该被 cp 也不该被 rm。
      # cp 阶段已跳过非法者，此处双保险防手动构造 files 数组绕过。
      _validate_commit_file_path "$f2" || { echo "⏸ M-002 拒绝还原非法路径: $f2" >&2; continue; }
      if git ls-files --error-unmatch "$f2" >/dev/null 2>&1; then
        git checkout HEAD -- "$f2" 2>/dev/null || true   # tracked：还原到 HEAD
      else
        rm -f "$f2"                                       # untracked 新文件：删（已迁走）
      fi
    done
  else
    local p2
    while IFS= read -r -d '' p2; do
      # AS-EC-014 fix (第三处): 还原循环同样需消费 rename oldpath，否则 rm/checkout 作用于截断路径
      local _xy="${p2:0:2}"
      p2="${p2#???}"
      case "$_xy" in R?|C?) local _oldpath; IFS= read -r -d '' _oldpath || true ;; esac
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

  # ⑤ 自动 push opt 分支到 origin（用户 2026-07-01 定）：
  # worktree 分支均为 auto/opt-* 命名，远端 push 安全；main/master 由 reference-transaction
  # hook 拦截直写，且 worktree 分支永不命中 main/master。push 失败不阻断 commit（已落本地），
  # 只 warn——网络/权限问题不应让引擎整轮 fail。
  # AS-L-002 fix: 原 `2>&1 | sed` 会把 stderr 错误消息也加前缀污染、且 if 取 sed 退出码
  # (几乎恒 0) 导致 push 失败时误判为成功。改为分离流 + PIPESTATUS 取 git 真实退出码。
  local wt_branch; wt_branch=$(git -C "$target" symbolic-ref --short HEAD 2>/dev/null)
  if [[ -n "$wt_branch" && "$wt_branch" == auto/opt-* ]]; then
    local push_out push_err
    push_err=$(mktemp)
    push_out=$(git -C "$target" push -u origin "HEAD:${wt_branch}" 2>"$push_err")
    local push_rc=$?
    if [[ -n "$push_out" ]]; then
      printf '%s\n' "$push_out" | sed 's/^/  [push] /'
    fi
    if [[ -s "$push_err" ]]; then
      sed 's/^/  [push:err] /' "$push_err" >&2
    fi
    rm -f "$push_err"
    if (( push_rc == 0 )); then
      echo "✓ 已 push ${wt_branch} → origin/${wt_branch}"
    else
      echo "⚠️ push ${wt_branch} 失败 (rc=${push_rc}，commit 已落本地 worktree，不阻断；下次 merge 时再 push)" >&2
    fi
  fi
}

cmd_list() {
  echo "=== optimization worktrees ==="
  for d in "$WT_BASE"/*; do
    [[ -d "$d" ]] || continue
    local name; name=$(basename "$d")
    local dir; dir=$(cat "$d/.opt-direction" 2>/dev/null || echo "?")
    local diff_stat
    diff_stat=$(git -C "$d" diff --stat "$MAIN_BRANCH" 2>/dev/null | tail -1)
    local commits
    commits=$(git -C "$d" rev-list --count "$MAIN_BRANCH"..HEAD 2>/dev/null || echo 0)
    echo "  $name | 方向=$dir | $commits 提交 | ${diff_stat:-(无 diff)}"
  done
}

cmd_show() {
  local wt="${3:-optimization}"
  _validate_wt_name "$wt"
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
  _validate_wt_name "$wt"
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
  # M-003 fix (audit-2026-07-01-002): 旧 `auto/$(basename "$dir")` 假设分支名 = auto/<目录名>,
  # 但 direction-shift worktree 目录带时间戳后缀、route-fix 复用同 area 时目录名可能与分支
  # 不完全对应——merge 失败或误合错误分支。改用 symbolic-ref 查实际分支名(cmd_push line 568
  # 已用同一模式)。fallback 仅当 symbolic-ref 失败(detached HEAD)才退回 basename 拼接,
  # 并打印警告让审阅者知晓。
  local wt_branch
  wt_branch=$(git -C "$dir" symbolic-ref --short HEAD 2>/dev/null)
  if [[ -z "$wt_branch" ]]; then
    echo "⚠️  worktree $wt HEAD detached,symbolic-ref 失败;退回 basename 拼接(可能不准)" >&2
    wt_branch="auto/$(basename "$dir")"
  fi
  if git merge --squash "$wt_branch" 2>/dev/null; then
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

$(git log --oneline "$MAIN_BRANCH".."$wt_branch" 2>/dev/null | head -5)"
    # ↑ 只列 worktree 相对 main 的 ahead 提交（本 worktree 真实贡献）。旧 `git log --oneline auto/...`
    # 从根起 log 整条分支史，会把 main 已有提交灌进合并消息正文（实测 873f688 正文混入
    # 2aa0eba/0a2124d/4dc2565 等 main 提交，仅 734512b 属该 worktree），误导审阅。
    # M-003: 改用 $wt_branch(symbolic-ref 拿到的真实分支名)替代 basename 拼接。
    local merge_sha; merge_sha="$(git rev-parse HEAD 2>/dev/null || printf '')"
    audit_log success "$wt" "$merge_sha" "squash-merge worktree into $MAIN_BRANCH" || true
    # B-2 / 阶段③b EXPLORE v3.1：探索类 worktree 合并 → 回写 explore-log（verified）
    _explore_log_append "$wt" "$merge_sha" verified "人工批准合并，假设经探针 worktree 验证并落地" || true
    echo "✓ 已 squash 合并 $wt → $MAIN_BRANCH"
    git -C "$PROJECT" worktree remove "$dir" --force 2>/dev/null || rm -rf "$dir"
    # 合并后删本 worktree 实际分支（case-322 收口 + audit-2026-07-02-002 AS-EC-001：旧
    # `auto/$(basename "$dir")` 假设分支名 = auto/<目录名>，但 direction-shift worktree 目录
    # 带时间戳后缀、route-fix 复用同 area 时目录名可能与分支不完全对应——branch -D 删错
    # 分支或静默失败致 stale auto/* ref 残留→下轮 scout-scan 误报待合并。改用 $wt_branch
    # （上方 symbolic-ref 拿到的真实分支名；detached HEAD fallback 已保底）。best-effort
    # 容错：分支已删/解析失败不阻断合并收尾。
    git -C "$PROJECT" branch -D "$wt_branch" 2>/dev/null || true
    echo "✓ worktree 清理（worktree 目录 + 分支 $wt_branch）"
    # 合并使 main 推进；standing optimization worktree 此时落后 main（差本次合并内容）。
    # 仅靠 cmd_commit 首行 ensure_main_wt 自愈（case-363）会留「merge→下次 commit」间的
    # 陈旧窗口：期间任何对 standing WT 的读取（含引擎查 pending case log）看到旧快照，
    # 缺最新 case 文件（2026-07-01 实踩：merge opt-bookkeep-7398 后 standing WT 仍停 7324，
    # 缺 case-2026-07-01-391.json）。合并即 ff，关闭窗口；ff-only+祖先校验保未合并改动不丢。
    ensure_main_wt
  else
    # case-361 真缺口修复：`git merge --squash` 冲突不写 MERGE_HEAD（squash 不记录 merge），
    # 故 `git merge --abort` 报 `fatal: There is no merge to abort (MERGE_HEAD missing)` exit 128
    # 被 `|| true` 吞 = no-op，冲突（UU 入 index）残留 $PROJECT 致重跑再撞同一冲突。fallback
    # `git reset --merge`（实测 exit 0 清掉 UU、非破坏——保留未冲突本地改动）真正回滚 $PROJECT
    # 至干净 $MAIN_BRANCH，去 $dir 修冲突文件提交到 auto/<wt> 后再跑可干净重试。
    audit_log failure "$wt" "" "squash merge conflict, $PROJECT rolled back to clean $MAIN_BRANCH" || true
    echo "❌ 合并冲突：已回滚 $PROJECT 至干净 $MAIN_BRANCH。去 $dir 解决冲突文件、提交到 $wt_branch，再跑 opt-worktree.sh merge \"$PROJECT\" \"$wt\"；或 opt-worktree.sh reject \"$PROJECT\" \"$wt\" 放弃"
    git merge --abort 2>/dev/null || git reset -q --merge 2>/dev/null || true
    exit 1
  fi
}

cmd_reject() {
  local wt="${3:?need worktree}"
  _validate_wt_name "$wt"
  local dir="$WT_BASE/$wt"
  [[ -d "$dir" ]] || { echo "❌ worktree 不存在: $wt"; exit 1; }
  # B-2 / 阶段③b EXPLORE v3.1：探索类 worktree 拒绝 → 回写 explore-log（abandoned）
  # 必须在 worktree 目录被删之前读 .opt-direction。
  _explore_log_append "$wt" "" abandoned "人工拒绝，假设放弃或需重设后重探" || true
  git -C "$PROJECT" worktree remove "$dir" --force 2>/dev/null || rm -rf "$dir"
  git -C "$PROJECT" branch -D "auto/$(basename "$dir")" 2>/dev/null || true
  # DO B（autonomous-constraints.md）：reject 是删除敏感路径（worktree remove + branch -D），
  # 与 cmd_merge 对称记 JSONL 审计日志（action=delete, resource=artifact）。result 如实反映：
  # worktree 目录已消失=success（branch -D best-effort，失败仅 reason 标注），仍在=failure。
  if [[ ! -d "$dir" ]]; then
    audit_log success "$wt" "" "rejected worktree; branch auto/$(basename "$dir") -D (best-effort)" delete artifact || true
  else
    audit_log failure "$wt" "" "reject incomplete: $dir still exists after remove --force" delete artifact || true
  fi
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
    # .opt-direction / .opt-lock 是 worktree 基础设施桩文件（untracked），非真改动，剔后再判脏。
    # .opt-lock = cmd_commit 持锁防并发；.opt-direction = 方向标记。两者均不应阻止 cleanup。
    status_out=$(git -C "$d" status --porcelain 2>/dev/null || true)
    dirty=0
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      [[ "$line" == "?? .opt-direction" ]] && continue
      [[ "$line" == "?? .opt-lock" ]] && continue
      dirty=$((dirty + 1))
    done <<< "$status_out"
    if [[ "$ahead" != "0" || "$dirty" != "0" ]]; then
      skipped=$((skipped + 1))
      continue
    fi
    git -C "$PROJECT" worktree remove "$d" --force 2>/dev/null || rm -rf "$d"
    git -C "$PROJECT" branch -D "auto/$name" 2>/dev/null || true
    # DO B：cleanup 批量删空 worktree（worktree remove + branch -D）是删除/批量敏感路径，
    # 逐条记 JSONL 审计日志（action=delete, resource=artifact），与 cmd_merge/reject 对称。
    # case-412 审计修复：result 如实反映删除是否生效，不恒 success（autonomous-constraints.md
    # DO B 明令"确保 result 字段如实反映成功/失败"）。旧实现无条件 audit_log success——若
    # worktree remove --force 与 rm -rf 双双失败（权限/挂载占用），目录仍在却记 success，审计
    # 日志失真。与 cmd_reject(L610) 对称：按 [[ -d "$d" ]] 实判，branch -D best-effort 仅 reason 标注。
    if [[ ! -d "$d" ]]; then
      audit_log success "$name" "" "cleanup empty worktree (0 commits, dead stub); branch auto/$name -D (best-effort)" delete artifact || true
      echo "✓ 清理空 worktree: $name（0 提交，死桩）"
      removed=$((removed + 1))
    else
      audit_log failure "$name" "" "cleanup incomplete: $d still exists after remove --force + rm -rf" delete artifact || true
      echo "⚠️ 清理失败（目录仍在）: $name" >&2
      skipped=$((skipped + 1))
    fi
  done
  echo "清理完成: 删 $removed / 跳 $skipped（有真提交或未提交改动）"

  # 阶段 2：清理无 linked worktree 的 auto/opt-* 孤儿分支（case-356 fix 已防新 leak，
  # 残留为历史遗留）。仅当分支名匹配 auto/opt-* 且 WT_BASE 下无同名目录时删除。
  local orphan_removed=0 orphan_skipped=0 branch wt_dir
  while IFS= read -r branch; do
    [[ -z "$branch" ]] && continue
    # git branch --list 输出带前导空格和可能的 * 当前分支标记，trim 掉
    branch="${branch#"${branch%%[![:space:]]*}"}"   # 去前导空白
    branch="${branch#\* }"                           # 去当前分支标记
    [[ "$branch" == auto/opt-* ]] || continue
    local slug="${branch#auto/}"
    wt_dir="$WT_BASE/$slug"
    if [[ -d "$wt_dir" ]]; then
      orphan_skipped=$((orphan_skipped + 1))
      continue
    fi
    # case-412 审计修复：branch -D 失败须记 failure，不恒 success（DO B）。
    # 用 git branch -D 的退出码直接判（if-conditional 不触发 set -e）。
    if git -C "$PROJECT" branch -D "$branch" 2>/dev/null; then
      audit_log success "$branch" "" "cleanup orphan branch auto/opt-* (no linked worktree)" delete artifact || true
      echo "✓ 清理孤儿分支: $branch（无 linked worktree）"
      orphan_removed=$((orphan_removed + 1))
    else
      audit_log failure "$branch" "" "orphan branch -D failed (checked out elsewhere? refs/heads still present)" delete artifact || true
      echo "⚠️ 孤儿分支删除失败: $branch（refs/heads 仍在）" >&2
      orphan_skipped=$((orphan_skipped + 1))
    fi
  done < <(git -C "$PROJECT" branch --list 'auto/opt-*' 2>/dev/null)
  echo "孤儿分支清理: 删 $orphan_removed / 跳 $orphan_skipped（有 linked wt）"
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
# 2026-06-30 case-345 从 root live 副本回graft AS main：root 独有，AS 缺，
# 整体 cp AS→root 会丢失它（[[opt-worktree-root-as-copy-drift]] 双向漂移收口）。
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
  init) cmd_init "$@" ;;
  commit) cmd_commit "$@" ;;
  list) cmd_list ;;
  show) cmd_show "$@" ;;
  merge) cmd_merge "$@" ;;
  reject) cmd_reject "$@" ;;
  cleanup) cmd_cleanup ;;
  next-case) cmd_next_case "$@" ;;
  new-case) cmd_new_case "$@" ;;
  precommit) cmd_precommit ;;
  install-hooks) cmd_install_hooks "$@" ;;
  install-ref-hooks) cmd_install_ref_hooks "$@" ;;
  *) echo "用法: opt-worktree.sh <project> <init|commit|list|show|merge|reject|cleanup|next-case|new-case|precommit|install-hooks|install-ref-hooks> ..."; exit 1 ;;
esac