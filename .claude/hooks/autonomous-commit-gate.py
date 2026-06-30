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
import os, sys, json, re, subprocess, datetime, random, string

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
# 拦截的 git 子命令(commit/push/merge/reset/branch/update-ref);豁免 checkout/switch(opt-worktree 内部用)
_GUARDED = {"commit", "push", "merge", "reset", "branch", "update-ref"}
# shell 顺序/管道控制符——命令链按此拆段逐段评估,堵 `A && git commit` 类绕过(见 _git_segments)
_SHELL_OPS_RE = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")


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
    也识别 --git-dir/--work-tree(--git-dir=<path> 与空格形式):--work-tree 直接作为
    工作目录;--git-dir=<...>/.git 取其父目录,裸仓(无 .git 后缀)无工作树→回退
    PROJECT_DIR。优先级 work-tree > git-dir > -C(显式指向 strongest 信号)。无上述
    任一时回退 PROJECT_DIR——若后者非 git repo,branch 探测返回空串(等价于"非
    main",放行)。引擎约定用 `git -C <project>` 而非 cd(见 autonomous-loop 纪律)。"""
    toks = cmd.split()
    paths = []
    git_dir = None
    work_tree = None
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
        if t == "--work-tree" and i + 1 < len(toks):
            work_tree = toks[i + 1]
            i += 2
            continue
        if t.startswith("--work-tree="):
            work_tree = t[len("--work-tree="):]
            i += 1
            continue
        if t == "--git-dir" and i + 1 < len(toks):
            git_dir = toks[i + 1]
            i += 2
            continue
        if t.startswith("--git-dir="):
            git_dir = t[len("--git-dir="):]
            i += 1
            continue
        i += 1
    if work_tree:
        p = work_tree
    elif git_dir:
        # /x/.git → /x;相对 ".git" → ".";裸仓(无 .git 后缀)无工作树→回退 PROJECT_DIR
        if git_dir.endswith(os.sep + ".git") or os.path.basename(git_dir) == ".git":
            p = os.path.dirname(git_dir) or "."
        else:
            return PROJECT_DIR
    elif not paths:
        return PROJECT_DIR
    else:
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


def _git_segments(cmd):
    """把命令按 shell 顺序/管道控制符拆段(&&、||、;、|、换行),逐段独立评估。
    修命令链绕过:`A && git commit` 里危险 git 在链后段,原 `_git_parse` 用 `index("git")`
    只取首个 git token——若前段也含 git(如 `git -C . status && git -C . commit`),commit
    会被当成前段参数而放行;逐段评估即可命中后段真实 commit。分支与 repo 按本段 -C 解析,
    故跨 repo 链(`-C A status && -C B commit`)也能正确定位 B 的分支。
    残留:命令替换 $(git ...)/反引号不在拆分范围(需 LLM 刻意构造,低危)。"""
    return [seg for seg in _SHELL_OPS_RE.split(cmd) if seg]


def _push_refs_main(rest):
    """push 的 refspec 是否触及 main/master。覆盖裸 ref、HEAD:main、main:main、+force 前缀。"""
    for t in rest:
        if t in MAIN_BRANCHES:
            return True
        if any(p in MAIN_BRANCHES for p in t.lstrip("+").split(":")):
            return True
    return False


def _eval_segment(seg):
    """评估单段命令,返回 block_detail 文本或 None(未命中/豁免)。"""
    sub, rest = _git_parse(seg)
    if sub not in _GUARDED:
        return None
    branch = current_branch(seg)
    repo = repo_dir_from_cmd(seg)
    if sub in ("commit", "push", "merge"):
        # 目标分支是 main/master → 拦(分支从本段 -C 解析)
        targets_main = branch in MAIN_BRANCHES
        if sub == "push":
            # 显式推 main/master ref(含 HEAD:main / main:main / +force)→ 即便在 feature 分支也拦
            targets_main = targets_main or _push_refs_main(rest)
        if targets_main:
            # 豁免:case 元数据归档(仅 .claude/decisions/case-*.json)按先例可直提 main
            if sub == "commit" and is_case_metadata_only(staged_files(repo)):
                return None
            return f"直接 {sub} 到 main/master"
    elif sub == "reset":
        # ref-mover 模式(--hard/--soft/--mixed)在 main 移动分支指针 → 拦;无模式标志的暂存区操作放行
        _REF_MOVER_FLAGS = {"--hard", "--soft", "--mixed"}
        if any(t in _REF_MOVER_FLAGS for t in rest) and branch in MAIN_BRANCHES:
            return "git reset --hard/--soft/--mixed 在 main 分支（移动分支指针）"
    elif sub == "branch":
        # -f/-D/-d/-m/-M 触及 main/master → 拦;纯列分支或新建分支放行
        _BR_DANGEROUS = {"-f", "--force", "-D", "-d", "--delete", "-m", "-M", "--move"}
        has_dangerous = any(t in _BR_DANGEROUS for t in rest)
        branch_names = [t for t in rest if not t.startswith("-")]
        if has_dangerous and any(b in MAIN_BRANCHES for b in branch_names):
            flags_used = " ".join(t for t in rest if t.startswith("-"))
            return f"git branch {flags_used} 操作 main/master"
    elif sub == "update-ref":
        # git update-ref refs/heads/main <sha> 直接写 main ref → 拦
        _MAIN_REFS = {f"refs/heads/{b}" for b in MAIN_BRANCHES}
        if any(t in _MAIN_REFS for t in rest):
            return "git update-ref 直接写 refs/heads/main/master"
    return None


def _audit_log_block(cmd, block_detail):
    """审计埋点(按 .claude/decisions/audit-log.schema.json):gate 拦下 main 直写尝试时
    append-only 写一条 JSONL 到 <PROJECT_DIR>/.audit/audit-YYYY-MM-DD.jsonl。
    fail-safe——日志写失败绝不影响拦截决策(吞异常,仍按原 block 路径 exit 2)。"""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        date = now.strftime("%Y%m%d")        # id 用紧凑 8 位(对齐 schema id 模式)
        date_dashed = now.strftime("%Y-%m-%d")  # 文件名用 dashed(对齐约束文档 .audit/audit-YYYY-MM-DD.jsonl)
        rid = now.strftime("%H%M%S")
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        entry = {
            "id": f"audit-{date}-{rid}-{suffix}",
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "userId": "engine",
            "userRole": "engine",
            "action": "compliance_check",
            "resource": {"type": "permission", "identifier": "git-main-write",
                         "newValue": block_detail},
            "result": "denied",
            "ip": "local",
            "sensitive": True,
            "sensitiveLevel": "high",
            "details": {"reason": f"autonomous-commit-gate 拦截:{block_detail}",
                        "errorMessage": cmd[:200]},
        }
        adir = os.path.join(PROJECT_DIR, ".audit")
        os.makedirs(adir, exist_ok=True)
        with open(os.path.join(adir, f"audit-{date_dashed}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 审计写失败不影响拦截决策


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        print("{}")
        return
    if data.get("tool_name") != "Bash":
        print("{}")
        return
    # 只在 autonomous 模式激活时拦(标记存在);用户直接指挥的提交(标记不存在)放行
    if not os.path.exists(MARKER):
        print("{}")
        return
    cmd = (data.get("tool_input") or {}).get("command", "") or ""

    # 逐段评估命令链——堵 `A && git commit` 类绕过(原 index("git") 只看首个 git token)
    block_detail = None
    for seg in _git_segments(cmd):
        block_detail = _eval_segment(seg)
        if block_detail is not None:
            break

    if block_detail is None:
        print("{}")
        return

    _audit_log_block(cmd, block_detail)  # 审计埋点(fail-safe,不影响拦截)
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"🚫 autonomous 模式激活:禁止 {block_detail}。\n"
            "引擎的自动优化必须进 optimization worktree 等人工审合并——这样 main 永远安全,优化可大胆跑。\n"
            "改用: bash scripts/opt-worktree.sh commit <area:subdirection> \"<提交说明>\"\n"
            "  (方向格式如 engine:distillation / moni:quant;area 不同会自动开新 worktree)\n"
            "提交后人工审: opt-worktree.sh show <worktree> → merge/reject\n"
            "若确需直接修改 main(非自治优化),先 rm .claude/.autonomous_active 退出自治标记。\n"
            "豁免:仅归档 .claude/decisions/case-*.json 的 case 元数据 commit 可直提 main(按先例)。"
        )
    }, ensure_ascii=False))
    sys.exit(2)


if __name__ == "__main__":
    main()
