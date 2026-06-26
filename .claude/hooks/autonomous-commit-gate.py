"""autonomous-commit-gate.py — PreToolUse Hook (matcher: Bash)

强制:autonomous 模式下,引擎不得直接 git commit/push/merge 到 main,
必须走 opt-worktree.sh commit(进 optimization worktree 等人工审合并)。

确定性 backstop——"提示词不是护栏"。LLM 可能忽略 prompt 里"用 opt-worktree"的指示,
但 bash exit 2 阻断它绕不过。只在 autonomous 模式激活时拦(标记文件存在),
用户直接指挥的提交(标记不存在)放行——比如用户手动 git commit main。

触发条件(全部满足才拦):
  1. .claude/.autonomous_active 标记存在(引擎自治激活时建)
  2. 当前分支是 main/master(或命令显式 push origin main)
  3. 命令是 git commit / git push / git merge
"""
import os, sys, json, re, subprocess

if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
MARKER = os.path.join(PROJECT_DIR, ".claude", ".autonomous_active")
MAIN_BRANCHES = {"main", "master"}


def current_branch():
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                           cwd=PROJECT_DIR, capture_output=True, text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


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

    # 只拦 git commit/push/merge
    if not re.search(r"\bgit\s+(commit|push|merge)\b", cmd):
        print("{}")
        return

    # 只在 autonomous 模式激活时拦
    if not os.path.exists(MARKER):
        print("{}")
        return

    # 当前分支是 main/master → 拦
    branch = current_branch()
    targets_main = branch in MAIN_BRANCHES or re.search(r"\bgit\s+push\s+\S*\s+(origin\s+)?(main|master)\b", cmd)

    if targets_main:
        print(json.dumps({
            "decision": "block",
            "reason": (
                "🚫 autonomous 模式激活:禁止直接 commit/push/merge 到 main/master。\n"
                "引擎的自动优化必须进 optimization worktree 等人工审合并——这样 main 永远安全,优化可大胆跑。\n"
                "改用: bash scripts/opt-worktree.sh commit <area:subdirection> \"<提交说明>\"\n"
                "  (方向格式如 engine:distillation / moni:quant;area 不同会自动开新 worktree)\n"
                "提交后人工审: opt-worktree.sh show <worktree> → merge/reject\n"
                "若确需直接提交 main(非自治优化),先 rm .claude/.autonomous_active 退出自治标记。"
            )
        }, ensure_ascii=False))
        sys.exit(2)
    # 当前在 feature/auto 分支 → 放行(本来就该在 worktree 分支提交)
    print("{}")


if __name__ == "__main__":
    main()
