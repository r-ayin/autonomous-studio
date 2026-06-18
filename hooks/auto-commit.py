#!/usr/bin/env python3
"""auto-commit.py — 项目文件强约束自动提交 + PROGRESS.md 更新

触发: Stop (每轮结束) / SessionEnd (SSH断开保护)
行为: 扫描所有项目仓库 → 有变更 → git add + commit + 更新 PROGRESS.md
规则: 绝不 push，跳过 .claude/ 等内部文件，merge 冲突时跳过并告警
"""

import os
import sys
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# ── Windows UTF-8 兼容 ───────────────────────────────
if sys.platform == "win32":
    for s in (sys.stdin, sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except: pass

WORKSPACE_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
HOOK_EVENT = os.environ.get("CLAUDE_HOOK_EVENT", "")

# ── 项目仓库注册 ──────────────────────────────────────
# is_subrepo=True → 有独立 .git 和 remote
KNOWN_REPOS = [
    {"name": "moni",           "path": "moni",            "is_subrepo": True},
    {"name": "wanxia",         "path": "wanxia",          "is_subrepo": True},
    {"name": "pachong-master", "path": "pachong-master",  "is_subrepo": True},
    # 🚫 x-tool 不属于引擎管辖，不在列表中
    # 引擎仅管理自身仓库 r-ayin/autonomous-studio 的 commit+push
    # 各项目仓库由 auto-commit 自动 commit（本地），但 push 由用户手动触发
]

# ── 排除规则 ──────────────────────────────────────────
EXCLUDED_PREFIXES = (
    ".claude", "node_modules", ".venv", "__pycache__",
    ".git", ".pytest_cache", "Inno Setup 6", "Telegram Desktop",
)

# 根仓库中属于子仓库的路径（由 _belongs_to_subrepo 动态判断）
SUBREPO_NAMES = {r["name"] for r in KNOWN_REPOS if r["is_subrepo"]}

# ── 工具函数 ──────────────────────────────────────────

def git(repo_path: str, args: list, timeout: int = 15):
    """执行 git 命令，返回 (returncode, stdout, stderr)"""
    try:
        r = subprocess.run(
            ["git"] + args, cwd=repo_path,
            capture_output=True, text=True, encoding="utf-8",
            timeout=timeout,
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -2, "", str(e)


def is_excluded(file_path: str) -> bool:
    """检查路径是否应跳过"""
    fp = file_path.replace("\\", "/")
    for prefix in EXCLUDED_PREFIXES:
        if fp == prefix or fp.startswith(prefix + "/"):
            return True
    return False


def belongs_to_subrepo(file_path: str) -> bool:
    """检查根仓库中的文件是否属于某个子仓库"""
    fp = file_path.replace("\\", "/")
    for name in SUBREPO_NAMES:
        if fp == name or fp.startswith(name + "/"):
            return True
    return False


def has_merge_conflict(repo_path: str) -> bool:
    """检测是否处于 merge 冲突状态"""
    rc, out, _ = git(repo_path, ["status", "--porcelain"])
    if rc != 0:
        return False
    conflict_prefixes = {"UU", "DD", "AA", "UD", "DU", "AU", "UA"}
    for line in out.split("\n"):
        if len(line) >= 2 and line[:2] in conflict_prefixes:
            return True
    return False


# ── 变更检测 ──────────────────────────────────────────

def get_project_changes(repo_path: str, is_subrepo: bool) -> list:
    """获取仓库中的项目文件变更列表，排除内部文件"""
    rc, out, _ = git(repo_path, ["status", "--porcelain"])
    if rc != 0 or not out:
        return []

    changes = []
    for line in out.split("\n"):
        # git status --porcelain 格式: XY<空格>PATH
        # XY 是固定2字符状态码，之后可能有多余空白
        # 安全解析: 取前2字符为status，第3字符起trim后为path
        if not line or len(line) < 3:
            continue
        status = line[:2].strip()
        file_path = line[2:].strip()

        if is_excluded(file_path):
            continue
        if not is_subrepo and belongs_to_subrepo(file_path):
            continue

        changes.append({"path": file_path.replace("\\", "/"),
                        "status": status})
    return changes


# ── Commit 消息生成 ────────────────────────────────────

def classify_change_type(changes: list) -> str:
    """从变更文件列表推断 commit 类型"""
    paths = [c["path"] for c in changes]

    # docs: 仅 .md 文件
    if all(p.endswith(".md") for p in paths):
        return "docs"

    # test: 仅 test/spec 文件
    if all("test" in p.lower() or "spec" in p.lower() for p in paths):
        return "test"

    # fix: 路径含 fix/bug/patch
    if any("fix" in p.lower() or "bug" in p.lower() for p in paths):
        return "fix"

    # refactor: 路径含 refactor
    if any("refactor" in p.lower() for p in paths):
        return "refactor"

    # chore: 仅配置文件
    config_exts = (".gitignore", ".env.example", ".yaml", ".yml", ".toml", ".cfg")
    if all(p.endswith(config_exts) or os.path.basename(p) in ("Dockerfile", "Makefile")
           for p in paths):
        return "chore"

    # feat: 有新文件
    if any(c["status"] in ("A", "??") for c in changes):
        return "feat"

    # 默认
    return "chore"


def generate_commit_message(repo_name: str, changes: list) -> str:
    """生成 Conventional Commit 消息"""
    change_type = classify_change_type(changes)

    # 中文类型映射
    type_cn = {
        "feat": "新增", "fix": "修复", "chore": "配置",
        "docs": "文档", "refactor": "重构", "test": "测试",
    }.get(change_type, "更新")

    # 作用域
    scope = repo_name
    subdirs = [c["path"].split("/")[0] for c in changes
               if "/" in c["path"]]
    if subdirs and len(set(subdirs)) == 1 and subdirs[0] != repo_name:
        scope = f"{repo_name}/{subdirs[0]}"

    # 文件摘要（最多显示 5 个文件名）
    file_names = []
    for c in changes[:5]:
        bn = os.path.basename(c["path"])
        name_no_ext = os.path.splitext(bn)[0]
        file_names.append(name_no_ext)
    if len(changes) > 5:
        file_names.append(f"+{len(changes) - 5}")

    file_summary = "/".join(file_names)

    # 主题行
    subject = f"{change_type}({scope}): {type_cn}（{len(changes)} 文件） — {file_summary}"

    # 正文
    status_label = {"M": "修改", "A": "新增", "D": "删除",
                    "??": "新增", "MM": "修改", "AM": "新增修改",
                    "R": "重命名"}
    body_lines = []
    for c in changes:
        label = status_label.get(c["status"], c["status"])
        body_lines.append(f"  {label}  {c['path']}")

    return subject + "\n\n" + "\n".join(body_lines)


# ── PROGRESS.md 更新 ──────────────────────────────────

def update_progress_md(project_path: str, changes: list, commit_msg: str):
    """在 PROGRESS.md 的变更历史表顶部追加新行"""
    progress_path = os.path.join(project_path, "PROGRESS.md")
    if not os.path.isfile(progress_path):
        return

    with open(progress_path, "r", encoding="utf-8") as f:
        content = f.read()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    change_type = classify_change_type(changes)
    type_cn = {"feat": "新增", "fix": "修复", "chore": "配置",
               "docs": "文档", "refactor": "重构", "test": "测试"}
    change_label = type_cn.get(change_type, "变更")

    # 提交描述：取第一行去掉 type(scope): 前缀
    subject = commit_msg.split("\n")[0] if commit_msg else f"{change_label} 自动提交"
    desc = re.sub(r'^\w+\([^)]+\):\s*', '', subject)
    if len(desc) > 80:
        desc = desc[:77] + "..."

    new_row = f"| {today} | {change_label} | {desc} | Claude (auto) |"

    # 按行处理，找到变更历史表格并插入新行
    lines = content.split("\n")
    result = []
    in_history_section = False
    in_table = False
    header_row_idx = -1
    sep_row_idx = -1
    inserted = False

    for i, line in enumerate(lines):
        # 检测「变更历史」段落
        if re.match(r'^##\s*变更历史\s*$', line.strip()):
            in_history_section = True
            in_table = False
            header_row_idx = -1
            sep_row_idx = -1
            inserted = False
            result.append(line)
            continue

        # 在变更历史段落内检测表头
        if in_history_section and not in_table:
            if "| 时间 |" in line and "| 描述 |" in line:
                in_table = True
                header_row_idx = i
                result.append(line)
                continue

        # 检测分隔行（仅含 | - : 空格和空白）
        if in_table and not inserted:
            stripped = line.strip()
            if stripped.startswith("|") and re.match(r'^[\|\s\-:]+$', stripped):
                result.append(line)
                result.append(new_row)
                inserted = True
                continue

        # 遇到下一个 ## 段落 → 结束变更历史
        if in_history_section and in_table and line.strip().startswith("## "):
            in_history_section = False
            in_table = False

        result.append(line)

    new_content = "\n".join(result)
    with open(progress_path, "w", encoding="utf-8") as f:
        f.write(new_content)


# ── 核心逻辑 ──────────────────────────────────────────

def do_commit(repo_name: str, repo_path: str, is_subrepo: bool,
              suppress_output: bool = False) -> bool:
    """对一个仓库执行自动提交

    Returns: True if committed, False otherwise
    """
    resolved = os.path.join(WORKSPACE_ROOT, repo_path)
    resolved = os.path.abspath(resolved)

    # 检测 merge 冲突
    if has_merge_conflict(resolved):
        if not suppress_output:
            print(f"  [AUTO-COMMIT] ⚠️ {repo_name}: 检测到合并冲突，跳过自动提交",
                  file=sys.stderr)
        return False

    # 获取项目文件变更
    changes = get_project_changes(resolved, is_subrepo)
    if not changes:
        return False

    # 生成 commit 消息
    commit_msg = generate_commit_message(repo_name, changes)

    # 先更新 PROGRESS.md（让这次提交包含 PROGRESS.md 的变更）
    proj_path = resolved
    update_progress_md(proj_path, changes, commit_msg)

    # Stage 所有文件（含刚更新的 PROGRESS.md）
    rc, _, err = git(resolved, ["add", "-A"])
    if rc != 0:
        if not suppress_output:
            print(f"  [AUTO-COMMIT] ⚠️ {repo_name}: git add 失败 — {err[:100]}",
                  file=sys.stderr)
        return False

    # Commit
    rc, out, err = git(resolved, ["commit", "-m", commit_msg])
    if rc != 0:
        if "nothing to commit" in err.lower() + (out or "").lower():
            return False
        if not suppress_output:
            print(f"  [AUTO-COMMIT] ⚠️ {repo_name}: commit 失败 — {err[:100]}",
                  file=sys.stderr)
        return False

    if not suppress_output:
        print(f"  [AUTO-COMMIT] ✅ {repo_name}: {len(changes)} 文件已提交",
              file=sys.stderr)

    return True


# ── 入口 ──────────────────────────────────────────────

def main():
    if HOOK_EVENT not in ("Stop", "SessionEnd"):
        return

    suppress_output = HOOK_EVENT == "SessionEnd"

    committed_any = False
    for repo in KNOWN_REPOS:
        try:
            if do_commit(repo["name"], repo["path"],
                         repo["is_subrepo"], suppress_output):
                committed_any = True
        except Exception as e:
            if not suppress_output:
                print(f"  [AUTO-COMMIT] ❌ {repo['name']}: 异常 — {e}",
                      file=sys.stderr)

    if committed_any and not suppress_output:
        print("  [AUTO-COMMIT] ── 本轮变更已全部提交", file=sys.stderr)


if __name__ == "__main__":
    main()
