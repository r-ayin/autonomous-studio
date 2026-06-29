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
               ".tox", "coverage", ".nyc_output", ".opt-worktrees", ".parallel-worktrees",
               "site-packages", ".venv-sidecar"}
# 虚拟环境目录名变体繁多（.venv / .venv-foo / .venv-sidecar / venv-xxx），
# 单靠精确集合匹配会漏（曾致 x-tool 的 聚合ai客服开发/.venv-sidecar/site-packages
# 里 pydantic/h11/PyInstaller 的第三方 FIXME/HACK 被计入项目真债，虚高至 #1）。
# 故任何 .venv 前缀目录一律忽略。
IGNORE_DIR_PREFIXES = (".venv",)
IGNORE_FILES_SUFFIX = (".pyc", ".log", ".lock", ".min.js", ".min.css", ".map")
MAX_FILE_SIZE = 2 * 1024 * 1024  # >2MB 不索引内容
STALE_DAYS = 7

# 符号提取正则（轻量，无 tree-sitter 依赖）
PY_SYM = re.compile(r"^(async\s+)?(def|class)\s+(\w+)", re.M)
JS_TS_SYM = re.compile(r"^(export\s+)?(async\s+)?(function|class|const|let|var)\s+(\w+)", re.M)
MD_HEAD = re.compile(r"^#{1,3}\s+(.+)$", re.M)

# 债务标记计数修正：
#   1) 剥离字符串字面量——字典键 {"FIXME":0}、f-string、docstring 里的标记名不算债务
#      （此前 scout-scan.py 自身被自指误算为 FIXME=9/HACK=9，全来自 counts={"FIXME":0} 这类键）
#   2) 只认 MARKER: / MARKER - 形式（通用债务注释约定）；散文提及 "FIXME/HACK 比 TODO..."
#      或 "TODO/FIXME/HACK 标记的代码" 不算债务标记
_STRIP_STRINGS = re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\'')
# 剥离 JS/TS 模板字符串字面量（反引号）：scaffold 生成器 new.ts 将 TODO 占位符嵌入模板字符串，
# 如 `// TODO: implement test logic`，跨行不被单行字符串剥离，导致 stagehand-analysis 等项目
# 误计 TODO=3（模板占位）+ 上游 TODO（不可动）。反引号字符串以全文内容模式剥离（re.DOTALL）。
_STRIP_TEMPLATE_LITERALS = re.compile(r'`(?:[^`\\]|\\.)*`', re.DOTALL)
# 剥离全角括号占位符 【TODO...】 等：scaffold 生成器（如 luban/tools/
# scaffold-skill.sh）用 【TODO 做什么】 作为待用户填写的模板提示，不是真债务注释。
# 此前 14/17 个 TODO 全来自 scaffold-skill.sh 的占位提示，致 autonomous-studio 健康分虚高霸榜。
# 真债务是行内注释形式的标记（TODO/FIXME/HACK 后跟冒号或破折号），落在 【】 之外，不受影响。
_STRIP_PLACEHOLDERS = re.compile(r"【[^】]*】")
# 剥离 HTML 注释占位符 <!-- TODO... --> / <!-- TODO -->：project-protocol 自举生成的
# 子项目 CLAUDE.md/PROGRESS.md 三件套用 <!-- TODO: 一句话描述... --> / <!-- TODO -->
# 作为"待人工补充"的模板桩（见 .claude/decision-archive.md:511 约定：留空标记
# `<!-- TODO -->` 待人工补充）。HTML 注释非可执行代码，按项目约定属占位提示不算真债。
# 此前 x-tool 的 TODO=44 中 38 个全来自这类桩，致其标记密度虚高霸榜 #1。
# 真债务行内注释（井号或双斜杠后跟标记加冒号）不在 HTML 注释里，不受影响。
_STRIP_HTML_COMMENTS = re.compile(r"<!--.*?-->")
# 剥离 markdown 行内代码反引号 `...`：与字符串字面量/HTML 注释同类，行内代码是
# 引述/示意片段而非可执行债务——如本文件注释里 `// TODO implement test logic` 是
# 在解释剥离逻辑的引例，非真债。此前 .py/.md/.sh 注释中反引号引例的 TODO 标记被误计，
# 致 scout-scan.py 自指 2 命中（JS/TS 已由 _STRIP_TEMPLATE_LITERALS 整文剥离，此处
# 补 .py/.md/.sh 行内反引号缺口）。三反引号围栏代码块（```）是另一形式，行内正则
# 不匹配，围栏内真债仍被计数，不受影响。
_STRIP_BACKTICKS = re.compile(r"`[^`\n]*`")
_MARKER_RE = {m: re.compile(rf"\b{m}\b\s*[:-]") for m in ("TODO", "FIXME", "HACK")}
# 延期债约定：债务标记单词后接 (deferred) 后缀（标记与括号间可有空白），表示已 triage 标注
# 但确认延期（非清掉、非盲实现）的债——与 moni broker_qmt.py 既有约定一致。主 _MARKER_RE
# 因左括号非 [:-] 天然不匹配此形式，故延期债不计入 triage 推荐分子；此处单独计数只为可见性——
# 修复"merged 后标注式 triage 仍被每轮重推 triage"盲点（memory: scout-scan-recommend-blind-
# to-pending-worktrees 的 merged 子项：pending-worktree 检测只覆盖未合并，已合并到 main 的
# 标注式 triage 仍被重推）。注释行不字面写出该约定形式，避免本文件自指误算（同类缺口见
# memory: scout-scan-marker-self-inflation）。
_DEFERRED_RE = {m: re.compile(rf"\b{m}\b\s*\(\s*deferred\b") for m in ("TODO", "FIXME", "HACK")}


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
    """TODO/FIXME/HACK 计数（仅计代码注释中的真标记：剥离字符串字面量 + 要求 MARKER:/- 形式）。

    同时返回含真标记的 repo-relative 文件集合，供 pending_triage_in_worktrees 判定
    "这些标记是否已在某个待合并 opt-worktree 里被 triage"——让引擎区分"真未 triage"与
    "已 triage 待合并"，避免反复重选同一标记任务（autonomous-studio 4 个 TODO 已在
    opt-skills worktree triage、main 仍计 4→不应再推 triage，应推合并）。
    """
    counts = {"TODO": 0, "FIXME": 0, "HACK": 0}
    deferred = {"TODO": 0, "FIXME": 0, "HACK": 0}
    mfiles = set()
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS
                   and not d.startswith(IGNORE_DIR_PREFIXES)]
        for f in files:
            if f.endswith(IGNORE_FILES_SUFFIX):
                continue
            fp = os.path.join(root, f)
            try:
                if os.path.getsize(fp) > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            # 债务标记是代码注释约定，markdown 是文档/散文：.md 中 `# TODO:` 在标题、
            # `TODO:` 在描述性正文都匹配 MARKER 形式但非真债。此前 autonomous-studio 的 4 个
            # active TODO 全来自 decision-archive.md 标题/state.md 正文散文（真代码 TODO 均为
            # `TODO(deferred)` 形式，只计 deferred），致其虚假霸榜 #1。剥离规则逐个补丁（【TODO】/
            # `<!-- TODO -->` / 反引号引例）是打地鼠，排除 .md 一劳永逸。file_tree_and_symbols
            # 仍独立索引 .md 标题，此处仅影响 marker 计数。
            if not f.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".go", ".rs")):
                continue
            rel = os.path.relpath(fp, path)
            hit = False
            is_js_ts = f.endswith((".js", ".ts", ".tsx", ".jsx"))
            try:
                with open(fp, encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                # 对 JS/TS 文件先剥离多行模板字符串（反引号），避免模板占位符 TODO 被误计
                if is_js_ts:
                    content = _STRIP_TEMPLATE_LITERALS.sub("''", content)
                for line in content.splitlines():
                    # 剥离字符串字面量 counts={"FIXME":0} / f"...FIXME..." 不再自指误算
                    stripped = _STRIP_STRINGS.sub("", line)
                    # 剥离全角括号占位符 【TODO...】 scaffold 模板提示不算真债务
                    stripped = _STRIP_PLACEHOLDERS.sub("", stripped)
                    # 剥离 HTML 注释占位符 <!-- TODO... --> project-protocol 模板桩不算真债务
                    stripped = _STRIP_HTML_COMMENTS.sub("", stripped)
                    # 剥离 markdown 行内代码反引号引例（示意片段非真债，见 _STRIP_BACKTICKS 注释）
                    stripped = _STRIP_BACKTICKS.sub("", stripped)
                    for m, rx in _DEFERRED_RE.items():
                        if rx.search(stripped):
                            deferred[m] += 1
                            hit = True
                    for m, rx in _MARKER_RE.items():
                        if rx.search(stripped):
                            counts[m] += 1
                            hit = True
            except Exception:
                continue
            if hit:
                mfiles.add(rel)
        # 只走一层多（避免大库超时）— 实际 walk 已限 dirs
    return counts, mfiles, deferred


def file_tree_and_symbols(path, max_files=2000):
    """建文件树 + 抽符号索引"""
    tree = []
    symbols = {"functions": [], "classes": [], "headings": []}
    n = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS
                         and not d.startswith(IGNORE_DIR_PREFIXES))
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


def pending_in_opt_worktrees(path, filename):
    """检查 filename 是否在某个待合并的 opt worktree 里已落地（main 上缺但 worktree 已提交）。

    让引擎区分"真缺失"与"已做待合并"，避免反复重选同一缺文件任务
    （如 x-tool/PROGRESS.md 已在 opt-docs worktree、main 仍缺→别再推荐补，应推合并）。
    """
    wt_root = os.path.join(os.path.dirname(path), ".opt-worktrees", os.path.basename(path))
    if not os.path.isdir(wt_root):
        return []
    try:
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path,
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return []
    if not base:
        return []
    hits = []
    for entry in sorted(os.scandir(wt_root), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        try:
            r = subprocess.run(["git", "diff", "--name-only", f"{base}..HEAD"],
                               cwd=entry.path, capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and filename in r.stdout.splitlines():
                hits.append(entry.name)
        except Exception:
            continue
    return hits


def pending_triage_in_worktrees(path, marker_files):
    """含真标记的文件是否在某待合并 opt-worktree 的 diff 里——是则该 worktree 可能已 triage 这些 TODO/FIXME/HACK。

    与 pending_in_opt_worktrees（按单文件名查 PROGRESS/GATES）同构，但按 marker 文件集合查：
    若 marker 文件已在 worktree 动过，main 上的标记计数就是"已 triage 待合并"而非"真未处理"，
    引擎应推合并而非重做 triage。
    """
    if not marker_files:
        return []
    wt_root = os.path.join(os.path.dirname(path), ".opt-worktrees", os.path.basename(path))
    if not os.path.isdir(wt_root):
        return []
    try:
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path,
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return []
    if not base:
        return []
    mset = set(marker_files)
    hits = []
    for entry in sorted(os.scandir(wt_root), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        try:
            r = subprocess.run(["git", "diff", "--name-only", f"{base}..HEAD"],
                               cwd=entry.path, capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and mset & set(r.stdout.splitlines()):
                hits.append(entry.name)
        except Exception:
            continue
    return hits


def pending_planning_in_worktrees(path):
    """planning/ 目录是否在某待合并 opt-worktree 的 diff 里（main 上无但 worktree 已建）。

    与 pending_in_opt_worktrees（按单文件名查 PROGRESS/GATES）同构，但按目录前缀查：
    若 planning/ 已在某 worktree 的 diff 里，main 上"无 planning/"就是"已做待合并"而非
    "真缺失"，引擎应推合并而非重做（补了也会和 worktree 冲突）。

    修复盲区：sunset-prediction opt-planning-1782557428 已建 planning/ROADMAP.md，
    但 main 仍无 planning/→此前 scout 不感知，持续报"无 planning/" score=1.0 霸榜 #1，
    致 3 轮（case-021/022/023）撞同一已做工作单位、全部 superseded 零落地。
    """
    wt_root = os.path.join(os.path.dirname(path), ".opt-worktrees", os.path.basename(path))
    if not os.path.isdir(wt_root):
        return []
    try:
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path,
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return []
    if not base:
        return []
    hits = []
    for entry in sorted(os.scandir(wt_root), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        try:
            r = subprocess.run(["git", "diff", "--name-only", f"{base}..HEAD"],
                               cwd=entry.path, capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and any(p.startswith("planning/") for p in r.stdout.splitlines()):
                hits.append(entry.name)
        except Exception:
            continue
    return hits


def health_priority(r):
    """计算项目健康度优先级：分数越高 = 越需要被照顾。

    设计意图：打破引擎"自由心证总挑 autonomous-studio"的自反馈环路。
    关键约束——
      * 只用**结构性健康信号**（缺 PROGRESS/GATES、stale、标记密度），**不用 last_commit 新旧**：
        因 opt-worktree 流程下提交进 worktree、main 总是 stale，用提交新旧会反向把
        刚动过的宿主项目顶高，反而强化自选择。
      * autonomous-studio **不被排除**：它若真有结构性问题（缺文档/stale/标记堆积）仍会
        排到前面被修——满足"引擎真有 bug 就该修"的要求；只是日常自我润色不再因
        "最近活跃+可嚼"而霸榜。
    """
    score = 0.0
    reasons = []
    ps = r["progress_stale_days"]
    pend_prog = r.get("progress_pending_wts", [])
    pend_gates = r.get("gates_pending_wts", [])
    pend_triage = r.get("triage_pending_wts", [])
    pend_planning = r.get("planning_pending_wts", [])
    if ps is None:
        if pend_prog:
            score += 1  # 已在 worktree 待合并，大幅降权——别再推荐重做
            reasons.append(f"PROGRESS.md 待合并({','.join(pend_prog)})")
        else:
            score += 5
            reasons.append("缺 PROGRESS.md")
    elif ps > STALE_DAYS:
        score += 3
        reasons.append(f"PROGRESS.md stale {ps}天")
    if not r["gates_exists"]:
        if pend_gates:
            score += 1
            reasons.append(f"GATES.md 待合并({','.join(pend_gates)})")
        else:
            score += 4
            reasons.append("缺 GATES.md")
    if not r["has_planning"]:
        if pend_planning:
            # planning/ 已在某 worktree 待合并——不加分（别再推荐补，应推合并），
            # 否则该项目会因"无 planning/"持续霸榜 #1 让引擎重做已做工作（3 轮撞盲区）
            reasons.append(f"planning/ 待合并({','.join(pend_planning)})")
        else:
            score += 1
            reasons.append("无 planning/")
    m = r["markers"]
    total = m["TODO"] + m["FIXME"] + m["HACK"]
    n = max(r["file_count_indexed"], 1)
    density = total / n
    score += min(density * 10, 5)  # 密度贡献封顶，防大库绝对值碾压
    if total:
        reasons.append(f"标记 TODO/FIXME/HACK={m['TODO']}/{m['FIXME']}/{m['HACK']} 密度{density:.3f}")
    d = r.get("markers_deferred", {})
    d_total = d.get("TODO", 0) + d.get("FIXME", 0) + d.get("HACK", 0)
    if d_total:
        reasons.append(f"延期(已triage) TODO/FIXME/HACK={d.get('TODO', 0)}/{d.get('FIXME', 0)}/{d.get('HACK', 0)}（不计入triage推荐）")
    # FIXME/HACK 比 TODO 更可操作，额外加权（封顶）
    score += min((m["FIXME"] + m["HACK"]) * 0.2, 4)
    # marker 文件已在待合并 worktree 动过——main 上的标记是"已 triage 待合并"而非"真未处理"，
    # 降权使其不再因待合并债务霸榜 #1 让引擎重做（应推合并，不是重 triage）
    if pend_triage:
        score -= 1
        reasons.append(f"marker 文件待合并({','.join(pend_triage)})，可能已 triage")

    # 推荐一个**具体的小工作单位**——优先选可操作项，"等合并"降为备选
    # 修复：此前用 first-match 优先级链，"缺 PROGRESS + pending"先于"缺 GATES（可补）"
    # 命中，导致推荐列表全是不可操作的"等合并"，真正可做的工作被掩盖。
    actionable = []
    blocked = []
    if ps is None and pend_prog:
        blocked.append(f"等合并 PROGRESS.md（已在 {','.join(pend_prog)} worktree，别重做）")
    if ps is None and not pend_prog:
        actionable.append("补 PROGRESS.md（1 文件，无需深读代码）")
    if not r["gates_exists"] and pend_gates:
        blocked.append(f"等合并 GATES.md（已在 {','.join(pend_gates)} worktree）")
    if not r["gates_exists"] and not pend_gates:
        actionable.append("补 GATES.md（1 文件，无需深读代码）")
    if ps is not None and ps > STALE_DAYS:
        actionable.append(f"刷新 PROGRESS.md（已 stale {ps}天）")
    if m["FIXME"] + m["HACK"] > 0 and pend_triage:
        blocked.append(f"等合并 {','.join(pend_triage)} worktree（marker 文件已动，可能已 triage FIXME/HACK，别重做）")
    if m["FIXME"] + m["HACK"] > 0 and not pend_triage:
        actionable.append(f"triage {m['FIXME'] + m['HACK']} 个 FIXME/HACK（取前 1-2 个修）")
    if m["TODO"] > 0 and pend_triage and not (m["FIXME"] + m["HACK"] > 0):
        blocked.append(f"等合并 {','.join(pend_triage)} worktree（marker 文件已动，可能已 triage TODO，别重做）")
    if m["TODO"] > 0 and not pend_triage:
        actionable.append(f"triage 前 1-2 个 TODO（标注或清掉）")
    if not r["has_planning"] and pend_planning:
        blocked.append(f"等合并 planning/（已在 {','.join(pend_planning)} worktree，别重做）")
    if not r["has_planning"] and not pend_planning:
        actionable.append("补 planning/ 目录（路线图文档，无需深读代码）")

    if actionable:
        unit = actionable[0]
    elif blocked:
        unit = blocked[0]
    else:
        unit = "无明确小工作单位——可跳过或做文档润色"
    is_actionable = bool(actionable)
    return {"score": round(score, 2), "reasons": reasons, "work_unit": unit,
            "actionable": is_actionable}


def scan_project(p):
    """扫描单个项目，返回健康报告 + 索引"""
    path = p["path"]
    m_counts, m_files, m_deferred = count_markers(path)
    rep = {
        "name": p["name"],
        "path": path,
        "git": git_info(path),
        "progress_stale_days": staleness(path, "PROGRESS.md"),
        "progress_pending_wts": pending_in_opt_worktrees(path, "PROGRESS.md"),
        "gates_exists": os.path.isfile(os.path.join(path, "GATES.md")),
        "gates_pending_wts": pending_in_opt_worktrees(path, "GATES.md"),
        "has_planning": os.path.isdir(os.path.join(path, "planning")),
        "planning_pending_wts": pending_planning_in_worktrees(path),
        "markers": m_counts,
        "markers_deferred": m_deferred,
        "marker_files": sorted(m_files),
        "triage_pending_wts": pending_triage_in_worktrees(path, m_files),
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

    # Fallback: workspace 本身是一个 git 项目（而非项目容器）时自动上移到父目录。
    # 场景：loop prompt 写死 --workspace /…/autonomous-studio，但实际容器是其父目录。
    if not projects and not args.project:
        ws_is_project = os.path.isdir(os.path.join(ws, ".git")) or \
                        os.path.isfile(os.path.join(ws, "planning", "status.json"))
        if ws_is_project:
            parent_ws = os.path.dirname(ws)
            parent_projects = discover_projects(parent_ws)
            if parent_projects:
                ws = parent_ws
                projects = parent_projects

    if args.project:
        projects = [p for p in projects if p["name"] == args.project]

    report = {"scanned_at": now_iso(), "workspace": ws,
              "project_count": len(projects), "projects": []}
    for p in projects:
        report["projects"].append(scan_project(p))

    # 刷新 PROJECTS.md（除非只扫单项目）
    if not args.project and projects:
        write_projects_md(ws, projects)

    # 健康度优先级排序 → 确定性推荐工作单位
    # （打破引擎自由心证总挑 autonomous-studio 的自反馈环路）
    recs = []
    for r in report["projects"]:
        hp = health_priority(r)
        recs.append({"name": r["name"], "score": hp["score"],
                     "reasons": hp["reasons"], "work_unit": hp["work_unit"],
                     "actionable": hp.get("actionable", True)})
    recs.sort(key=lambda x: (x.get("actionable", True), x["score"]), reverse=True)
    report["recommendations"] = recs

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
            pend_p = r.get("progress_pending_wts", [])
            prog = "缺失" if ps is None else f"{ps}天" + (" ⚠️stale" if ps > STALE_DAYS else "")
            if ps is None and pend_p:
                prog += f" ⏳待合并({','.join(pend_p)})"
            print(f"  PROGRESS.md: {prog}")
            gp = r.get("gates_pending_wts", [])
            gates = "有" if r["gates_exists"] else ("无" + (f" ⏳待合并({','.join(gp)})" if gp else ""))
            print(f"  GATES.md: {gates} | planning/: {'有' if r['has_planning'] else '无'}")
            m = r["markers"]
            print(f"  标记: TODO={m['TODO']} FIXME={m['FIXME']} HACK={m['HACK']}")
            d = r.get("markers_deferred", {})
            if d.get("TODO", 0) + d.get("FIXME", 0) + d.get("HACK", 0):
                print(f"  延期(已triage): TODO={d.get('TODO', 0)} FIXME={d.get('FIXME', 0)} HACK={d.get('HACK', 0)}")
            print(f"  索引: {r['file_count_indexed']} 文件, "
                  f"fn={r['symbols']['functions']} class={r['symbols']['classes']} h={r['symbols']['headings']}")

        # 推荐工作单位（按健康度排序）——给引擎确定性选材，避免自由心证总挑自己
        print("\n=== 推荐工作单位（按健康度排序，越高越该被照顾）===")
        print("说明：分数基于结构性健康信号（缺文档/stale/标记密度），不依赖提交新旧；")
        print("      autonomous-studio 不被排除，按健康度公平排名（引擎真有 bug 仍可被选中）。")
        for i, rc in enumerate(recs[:3], 1):
            tag = "" if rc.get("actionable", True) else " ⏳blocked"
            print(f"  #{i} {rc['name']} (score={rc['score']}{tag}) — {rc['work_unit']}")
            print(f"      理由: {'; '.join(rc['reasons']) or '健康度良好'}")
        if recs and recs[0]["score"] == 0:
            print("  （所有项目健康度良好，无紧迫小工作单位——可做文档润色或跳过）")
        # 死锁信号：所有项目均 blocked（top 仍 > 0 但无可操作项）——明确告知需合并哪些
        # worktree 到 main 才能解锁。此前此态被静默吞掉，引擎只看到 blocked #1 不断撞墙
        # （曾导致 ≥5 次 skills gitignore 重复提交：循环反复重做已在 worktree 的工作）。
        actionable_recs = [rc for rc in recs if rc.get("actionable", True)]
        if recs and not actionable_recs and recs[0]["score"] != 0:
            pend = set()
            for r in report["projects"]:
                for k in ("progress_pending_wts", "gates_pending_wts",
                          "triage_pending_wts", "planning_pending_wts"):
                    for w in (r.get(k) or []):
                        pend.add(w)
            print("  ⚠️ 无可操作工作单位——全部项目 blocked，需人工合并以下 worktree 到 main 解锁：")
            for w in sorted(pend):
                print(f"     • {w}")
            print("  （合并任一即可解锁对应项目；引擎不自动 push，故必须人工合并。）")


if __name__ == "__main__":
    main()

# 升级路径（更强的文件索引，按需接入）:
# - tree-sitter (py tree_sitter): 精确 AST 符号/引用/依赖图
# - ast-grep: 结构化搜索/重写
# - engram (NickCirv/engram): SQLite KG，拦截 agent file read 替换为结构化上下文
# - jCodeMunch: index once, retrieve exact function/class/method
# - Repomix: 打包整库给 LLM（一次性上下文，非索引）
# - CodeSage: 符号图 + 语义搜索
