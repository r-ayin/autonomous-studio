r"""autonomous-commit-gate.py — PreToolUse Hook (matcher: Bash)

强制:autonomous 模式下,引擎不得直接 git commit/push/merge 到 main/master,
必须走 opt-worktree.sh commit(进 optimization worktree 等人工审合并)。

确定性 backstop——"提示词不是护栏"。LLM 可能忽略 prompt 里"用 opt-worktree"的指示,
但 bash exit 2 阻断它绕不过。只在 autonomous 模式激活时拦(标记文件存在),
用户直接指挥的提交(标记不存在)放行——比如用户手动 git commit main。

触发条件(全部满足才拦):
  1. .claude/.autonomous_active 标记存在(引擎自治激活时建)
  2. 目标分支是 main/master(或 push 显式推 main/master ref)
  3. 子命令是 git commit / git push / git merge

豁免:case 元数据归档——commit 仅触及 .claude/decisions/case-*.json 时放行。
  跨项目 case 按先例(0f77848/06937a9)直提 AS main 归档,这是元数据而非代码优化,
  故即使落在 main 也放行;代码改动仍必须进 worktree。

修复(分支检测+子命令识别双失效,2026-06-27):原 gate 有两处缺口叠加导致形同虚设——
  (a) 子命令正则 `\bgit\s+(commit|push|merge)\b` 要求 git 紧接子命令,但引擎实际跑
      `git -C <path> commit`,中间夹着 -C <path> → 正则永不命中 → 第一道过滤即放行;
  (b) current_branch() 以 PROJECT_DIR(常为 workspace root,非 git repo)为 cwd 跑
      `git rev-parse`→rc=128→空串→永不命中 main。
  现改用 tokenizer 跨过 git 全局选项(-C/-c/--*)取真实子命令,并从 -C 解析目标 repo
  正确识别分支。case-归档豁免配合此修复:分支检测修好后归档 commit 落 main 会被拦,
  需此豁免放行元数据归档(代码 commit 仍拦)。
"""
import os, sys, json, re, subprocess

if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
MARKER = os.path.join(PROJECT_DIR, ".claude", ".autonomous_active")
MAIN_BRANCHES = {"main", "master"}
# case 元数据文件:.claude/decisions/case-*.json(允许任意前导子路径)
CASE_FILE_RE = re.compile(r"(^|/)\.claude/decisions/case-[^/]+\.json$")
# 取一个值的 git 全局选项(-C <path>、-c <k=v>、--git-dir <path>、--work-tree <path>)
_GIT_VALOPTS = {"-C", "-c", "--git-dir", "--work-tree", "-b", "-B"}


def _git_parse(cmd):
    """tokenize 命令,返回 (子命令 or None, 子命令之后的 token 列表)。
    跨过 git 与子命令之间的全局选项:取值的选项(-C <path> 等)连同其值一起跳过,
    其他 -/-- 开头的标志只跳过自身。这样 `git -C <path> commit` 正确识别子命令=commit。
    非 git 命令(无独立 "git" token)返回 (None, [])。"""
    toks = cmd.split()
    try:
        i = toks.index("git")
    except ValueError:
        return None, []
    i += 1
    while i < len(toks):
        t = toks[i]
        if t in _GIT_VALOPTS and i + 1 < len(toks):  # -C <path> 等:跳过两项
            i += 2
            continue
        if t.startswith("-"):  # 其他标志(含 -Cpath 连写、--git-dir=path):跳过自身
            i += 1
            continue
        return t, toks[i + 1:]
    return None, []


def repo_dir_from_cmd(cmd):
    """从 `git -C <path> ...` 解析真实目标 repo 工作目录(多个 -C 依次累积进入)。
    无 -C 时回退 PROJECT_DIR——若后者非 git repo,branch 探测返回空串(等价于"非
    main",放行)。引擎约定用 `git -C <project>` 而非 cd(见 autonomous-loop 纪律)。"""
    toks = cmd.split()
    paths = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t == "-C" and i + 1 < len(toks):
            paths.append(toks[i + 1])
            i += 2
            continue
        if t.startswith("-C") and len(t) > 2:  # -Cpath 连写形式
            paths.append(t[2:])
            i += 1
            continue
        i += 1
    if not paths:
        return PROJECT_DIR
    p = paths[0]
    for extra in paths[1:]:  # git 多个 -C 按出现顺序依次进入
        p = os.path.join(p, extra)
    if not os.path.isabs(p):
        p = os.path.join(PROJECT_DIR, p)
    return p


def current_branch(cmd):
    """目标 repo 的当前分支。从命令解析 -C 定位 repo,再 git rev-parse。"""
    repo = repo_dir_from_cmd(cmd)
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                           cwd=repo, capture_output=True, text=True, timeout=3)
        return (r.stdout.strip() or "") if r.returncode == 0 else ""
    except Exception:
        return ""


def staged_files(repo):
    """取已暂存文件名列表(调用方须已确认子命令是 commit)。探测失败返回 None。"""
    try:
        r = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"],
                           cwd=repo, capture_output=True, text=True, timeout=3)
        if r.returncode != 0:
            return None
        return [f for f in r.stdout.split("\0") if f]
    except Exception:
        return None


def is_case_metadata_only(files):
    """豁免判定:全部已暂存文件都是 .claude/decisions/case-*.json。"""
    if not files:
        return False
    return all(CASE_FILE_RE.search(f) for f in files)


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        print("{}")
        return
    if data.get("tool_name") != "Bash":
        print("{}")
        return
    cmd = (data.get("tool_input") or {}).get("command", "") or ""

    # 用 tokenizer 取子命令(跨过 -C/-c 等 git 全局选项),只拦 commit/push/merge
    sub, rest = _git_parse(cmd)
    if sub not in ("commit", "push", "merge"):
        print("{}")
        return

    # 只在 autonomous 模式激活时拦
    if not os.path.exists(MARKER):
        print("{}")
        return

    # 目标分支是 main/master → 拦(分支从命令的 -C 解析,修复 workspace-root 失效)
    branch = current_branch(cmd)
    targets_main = branch in MAIN_BRANCHES
    if sub == "push":
        # 显式推 main/master ref(如 `git -C <p> push origin main`)→ 即便当前在 feature 分支也拦
        targets_main = targets_main or any(t in MAIN_BRANCHES for t in rest)

    if targets_main:
        # 豁免:case 元数据归档(仅 .claude/decisions/case-*.json)按先例可直提 main
        if sub == "commit":
            files = staged_files(repo_dir_from_cmd(cmd))
            if is_case_metadata_only(files):
                print("{}")
                return
        print(json.dumps({
            "decision": "block",
            "reason": (
                "🚫 autonomous 模式激活:禁止直接 commit/push/merge 到 main/master。\n"
                "引擎的自动优化必须进 optimization worktree 等人工审合并——这样 main 永远安全,优化可大胆跑。\n"
                "改用: bash scripts/opt-worktree.sh commit <area:subdirection> \"<提交说明>\"\n"
                "  (方向格式如 engine:distillation / moni:quant;area 不同会自动开新 worktree)\n"
                "提交后人工审: opt-worktree.sh show <worktree> → merge/reject\n"
                "若确需直接提交 main(非自治优化),先 rm .claude/.autonomous_active 退出自治标记。\n"
                "豁免:仅归档 .claude/decisions/case-*.json 的 case 元数据 commit 可直提 main(按先例)。"
            )
        }, ensure_ascii=False))
        sys.exit(2)
    # 当前在 feature/auto 分支 → 放行(本来就该在 worktree 分支提交)
    print("{}")


if __name__ == "__main__":
    main()
