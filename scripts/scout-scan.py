#!/usr/bin/env python3
"""scout-scan.py — 确定性项目发现 + 健康扫描 + 文件索引（零 LLM token）

修复缺口：
- 之前"扫描靠 LLM 自觉跑 Bash"→ 确定性脚本，子 agent 只读报告
- 之前"没有 PROJECTS.md"→ 自动发现 workspace 项目，生成/刷新 PROJECTS.md（单一源）
- 之前"不做文件索引"→ 遍历每个项目建文件树 + 符号索引（function/class），存 JSON

GitHub 对标（见报告）：Repomix（打包）、engram（SQLite KG 拦截 file read）、
jCodeMunch（index once retrieve exact）、CodeSage（符号图+语义）、Sverklo（blast radius）。
本脚本是最小本地实现（纯 Python，regex 抽符号；升级路径见尾部注释：tree-sitter/ast-grep）。

用法:
  scout-scan.py --workspace .                    # 扫描+索引+写 PROJECTS.md + health 报告
  scout-scan.py --workspace . --json             # JSON 输出（供 agent 解析）
  scout-scan.py --workspace . --project moni     # 只扫一个项目
"""
import os, sys, json, re, subprocess, argparse, glob
from datetime import datetime, timezone

# 忽略的目录
IGNORE_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache",
               "dist", "build", ".next", ".cache", "venv", "env", ".mypy_cache",
               ".tox", "coverage", ".nyc_output", ".opt-worktrees", ".parallel-worktrees"}
IGNORE_FILES_SUFFIX = (".pyc", ".log", ".lock", ".min.js", ".min.css", ".map")
MAX_FILE_SIZE = 2 * 1024 * 1024  # >2MB 不索引内容
STALE_DAYS = 7

# 符号提取正则（轻量，无 tree-sitter 依赖）
PY_SYM = re.compile(r"^(async\s+)?(def|class)\s+(\w+)", re.M)
JS_TS_SYM = re.compile(r"^(export\s+)?(async\s+)?(function|class|const|let|var)\s+(\w+)", re.M)
MD_HEAD = re.compile(r"^#{1,3}\s+(.+)$", re.M)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def discover_projects(workspace):
    """发现 workspace 下所有项目（有 .git 或 planning/status.json 的目录）"""
    projects = []
    if not os.path.isdir(workspace):
        return projects
    for entry in sorted(os.scandir(workspace), key=lambda e: e.name):
        if not entry.is_dir() or entry.name.startswith(".") or entry.name in IGNORE_DIRS:
            continue
        has_git = os.path.isdir(os.path.join(entry.path, ".git"))
        has_status = os.path.isfile(os.path.join(entry.path, "planning", "status.json"))
        if has_git or has_status:
            projects.append({"name": entry.name, "path": entry.path,
                              "has_git": has_git, "has_studio": has_status})
    return projects


def git_info(path):
    """git 状态快照"""
    info = {"dirty": 0, "last_commit": None, "branch": None}
    try:
        r = subprocess.run(["git", "status", "--porcelain"], cwd=path,
                           capture_output=True, text=True, timeout=5)
        info["dirty"] = len([l for l in r.stdout.splitlines() if l.strip()])
    except Exception:
        pass
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%cr|%H|%s"], cwd=path,
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            parts = r.stdout.strip().split("|", 2)
            info["last_commit"] = {"relative": parts[0], "hash": parts[1],
                                   "subject": parts[2] if len(parts) > 2 else ""}
    except Exception:
        pass
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path,
                           capture_output=True, text=True, timeout=3)
        info["branch"] = r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        pass
    return info


def count_markers(path):
    """TODO/FIXME/HACK 计数"""
    counts = {"TODO": 0, "FIXME": 0, "HACK": 0}
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            if f.endswith(IGNORE_FILES_SUFFIX):
                continue
            fp = os.path.join(root, f)
            try:
                if os.path.getsize(fp) > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            if not f.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".sh", ".go", ".rs")):
                continue
            try:
                with open(fp, encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        for m in counts:
                            if m in line:
                                counts[m] += 1
            except Exception:
                continue
        # 只走一层多（避免大库超时）— 实际 walk 已限 dirs
    return counts


def file_tree_and_symbols(path, max_files=2000):
    """建文件树 + 抽符号索引"""
    tree = []
    symbols = {"functions": [], "classes": [], "headings": []}
    n = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS)
        for f in sorted(files):
            if n >= max_files:
                break
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, path)
            if f.endswith(IGNORE_FILES_SUFFIX):
                continue
            try:
                size = os.path.getsize(fp)
            except OSError:
                continue
            tree.append({"p": rel, "s": size})
            n += 1
            # 抽符号
            if size > MAX_FILE_SIZE:
                continue
            if f.endswith(".py"):
                _extract(fp, rel, PY_SYM, 3, symbols["functions"], symbols["classes"])
            elif f.endswith((".js", ".ts", ".tsx", ".jsx")):
                _extract(fp, rel, JS_TS_SYM, 4, symbols["functions"], symbols["classes"])
            elif f.endswith(".md"):
                try:
                    with open(fp, encoding="utf-8", errors="ignore") as fh:
                        for m in MD_HEAD.finditer(fh.read()):
                            symbols["headings"].append({"f": rel, "t": m.group(1).strip()})
                except Exception:
                    continue
        if n >= max_files:
            break
    return tree[:max_files], symbols, n


def _extract(fp, rel, regex, group, fn_list, cls_list):
    try:
        with open(fp, encoding="utf-8", errors="ignore") as fh:
            for m in regex.finditer(fh.read()):
                name = m.group(group)
                kind = m.group(2) if m.lastindex >= 2 else ""
                entry = {"f": rel, "n": name}
                if "class" in (kind or ""):
                    cls_list.append(entry)
                else:
                    fn_list.append(entry)
    except Exception:
        pass


def staleness(path, fname):
    """文件最后更新距今天数"""
    fp = os.path.join(path, fname)
    if not os.path.isfile(fp):
        return None  # 文件不存在
    try:
        mtime = os.path.getmtime(fp)
        days = (datetime.now(timezone.utc).timestamp() - mtime) / 86400
        return round(days, 1)
    except Exception:
        return None


def scan_project(p):
    """扫描单个项目，返回健康报告 + 索引"""
    path = p["path"]
    rep = {
        "name": p["name"],
        "path": path,
        "git": git_info(path),
        "progress_stale_days": staleness(path, "PROGRESS.md"),
        "gates_exists": os.path.isfile(os.path.join(path, "GATES.md")),
        "has_planning": os.path.isdir(os.path.join(path, "planning")),
        "markers": count_markers(path),
    }
    # 文件索引（限制规模，避免大库超时）
    tree, symbols, n = file_tree_and_symbols(path)
    rep["file_count_indexed"] = n
    rep["symbols"] = {"functions": len(symbols["functions"]),
                      "classes": len(symbols["classes"]),
                      "headings": len(symbols["headings"])}
    # 索引落盘到项目 .claude/ 或 workspace 索引目录
    idx_dir = os.path.join(os.path.dirname(path), ".opt-worktrees", "_indexes")
    # 存到 workspace 级索引目录（不污染项目）
    idx_dir = os.path.join(os.path.dirname(path) or ".", ".codebase-index")
    os.makedirs(idx_dir, exist_ok=True)
    with open(os.path.join(idx_dir, f"{p['name']}.json"), "w", encoding="utf-8") as f:
        json.dump({"project": p["name"], "scanned_at": now_iso(),
                   "tree": tree, "symbols": symbols}, f, ensure_ascii=False)
    return rep


def write_projects_md(workspace, projects):
    """生成/刷新 PROJECTS.md（单一源）"""
    md = os.path.join(workspace, "PROJECTS.md")
    lines = ["---", "name: projects", "description: workspace 项目清单（由 scout-scan.py 自动刷新）",
             "metadata:", "  type: reference", "---", "", "# Projects", "",
             "| 项目 | 有git | 有Studio | 路径 |", "|---|---|---|---|"]
    for p in projects:
        lines.append(f"| {p['name']} | {'✓' if p['has_git'] else ' '} | "
                     f"{'✓' if p['has_studio'] else ' '} | `{p['path']}` |")
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--project", help="只扫一个项目")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ws = os.path.abspath(args.workspace)
    projects = discover_projects(ws)
    if args.project:
        projects = [p for p in projects if p["name"] == args.project]

    report = {"scanned_at": now_iso(), "workspace": ws,
              "project_count": len(projects), "projects": []}
    for p in projects:
        report["projects"].append(scan_project(p))

    # 刷新 PROJECTS.md（除非只扫单项目）
    if not args.project and projects:
        write_projects_md(ws, projects)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"=== 瞭望扫描 @ {report['scanned_at']} ===")
        print(f"workspace: {ws} | 发现 {len(projects)} 个项目 | 索引存 .codebase-index/")
        for r in report["projects"]:
            g = r["git"]
            print(f"\n● {r['name']} (branch={g.get('branch')}, dirty={g.get('dirty')})")
            lc = g.get("last_commit")
            print(f"  最近提交: {lc['relative'] if lc else '?'} — {lc['subject'][:50] if lc else ''}")
            ps = r["progress_stale_days"]
            print(f"  PROGRESS.md: {'缺失' if ps is None else f'{ps}天' + (' ⚠️stale' if ps > STALE_DAYS else '')}")
            print(f"  GATES.md: {'有' if r['gates_exists'] else '无'} | planning/: {'有' if r['has_planning'] else '无'}")
            m = r["markers"]
            print(f"  标记: TODO={m['TODO']} FIXME={m['FIXME']} HACK={m['HACK']}")
            print(f"  索引: {r['file_count_indexed']} 文件, "
                  f"fn={r['symbols']['functions']} class={r['symbols']['classes']} h={r['symbols']['headings']}")


if __name__ == "__main__":
    main()

# 升级路径（更强的文件索引，按需接入）:
# - tree-sitter (py tree_sitter): 精确 AST 符号/引用/依赖图
# - ast-grep: 结构化搜索/重写
# - engram (NickCirv/engram): SQLite KG，拦截 agent file read 替换为结构化上下文
# - jCodeMunch: index once, retrieve exact function/class/method
# - Repomix: 打包整库给 LLM（一次性上下文，非索引）
# - CodeSage: 符号图 + 语义搜索
