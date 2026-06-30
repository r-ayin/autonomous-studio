#!/usr/bin/env python3
"""pipeline-gate.py — studio 管线强制 hook（确定性,不可协商）。

复杂任务必须走管线(triage→prd→development→verify→done),小修直放。
配合 scripts/triage.py（写 <project>/.pipeline/current.json）。

PreToolUse Edit|Write|MultiEdit:
  - 非 studio 项目(无 planning/status.json 祖先)→ 放行
  - 文档/planning/.pipeline 文件 → 放行
  - 无 current.json → 阻断"先 triage"
  - complex 且 stage∉{development,verify} → 阻断"先到 development(走完 PRD)"
  - small → 放行
PreToolUse Bash(git commit/push):
  - 无 current.json → 阻断"先 triage"
  - complex 且 verify_passed=false → 阻断"先 verify"
  - small 但 diff 超规模(files>3 或 +行>50) → 阻断"升级 complex"
Stop: 扫描 studio 项目未收尾(current.stage!=done)→ 提醒
"""
from __future__ import annotations
import datetime
import json
import os
import random
import re
import string
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

DOCS = {"CLAUDE.md", "PROGRESS.md", "GATES.md", "README.md", "PROJECTS.md",
        "PROTOCOL.md", "status.json", "prd.json", "prd.md", ".gitignore"}


def _project_root(start_path: str | None) -> Path | None:
    if not start_path:
        return None
    p = Path(start_path).resolve()
    if not p.exists():
        p = p.parent
    for anc in [p, *p.parents]:
        if (anc / "planning" / "status.json").exists():
            return anc
        if anc.parent == anc:
            break
    return None


def _load_current(root: Path) -> dict | None:
    cp = root / ".pipeline" / "current.json"
    if cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    sys.exit(0)


def _remind(reason: str) -> None:
    print(json.dumps({"decision": "remind", "reason": reason}, ensure_ascii=False))


# git 调用识别（case-432 audit）：旧 `"git " in cmd` 子串只匹配空格分隔，漏过 tab/
# 换行分隔的 `git\tcommit`——与 case-378/428 全路径/分隔符绕过同类向量。改 regex：
# git 作为 token（裸 `git` 或路径形 `.../git`），前后为行首/空白/斜杠/行尾。
# 不覆盖 `$IFS` 变量展开（需 shell 解析，同 case-428 token 法局限，不盲实现）。
_GIT_INVOKED = re.compile(r"(?:^|[\s/])git(?=\s|$)")


def _is_git_commit_or_push(cmd: str) -> bool:
    return bool(_GIT_INVOKED.search(cmd)) and ("commit" in cmd or "push" in cmd)


def _audit_log_block(cmd: str, reason: str) -> None:
    """审计埋点（DO B：permission 敏感路径——commit/push 流水线门禁拦截）。
    append-only 写 JSONL 到 <PROJECT_DIR>/.audit/audit-YYYY-MM-DD.jsonl，schema 对齐
    .claude/decisions/audit-log.schema.json；与 autonomous-commit-gate._audit_log_block
    对称（case-428 已为 main 直写门禁落埋点，本 gate 覆盖 studio 流水线门禁拦截端）。
    fail-safe——写失败绝不影响拦截决策（吞异常，仍走原 _block exit 0 路径）。"""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        date = now.strftime("%Y%m%d")
        date_dashed = now.strftime("%Y-%m-%d")
        rid = now.strftime("%H%M%S")
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        entry = {
            "id": f"audit-{date}-{rid}-{suffix}",
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "userId": "engine",
            "userRole": "engine",
            "action": "compliance_check",
            "resource": {"type": "permission",
                         "identifier": "studio-pipeline-gate",
                         "newValue": reason[:200]},
            "result": "denied",
            "ip": "local",
            "sensitive": True,
            "sensitiveLevel": "medium",
            "details": {"reason": f"pipeline-gate 拦截:{reason}",
                        "errorMessage": cmd[:200]},
        }
        adir = os.path.join(PROJECT_DIR, ".audit")
        os.makedirs(adir, exist_ok=True)
        with open(os.path.join(adir, f"audit-{date_dashed}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _is_doc_or_meta(file_path: str, root: Path) -> bool:
    name = os.path.basename(file_path)
    if name in DOCS:
        return True
    try:
        rel = os.path.relpath(file_path, str(root))
    except Exception:
        return False
    return rel == ".pipeline" or rel.startswith(".pipeline" + os.sep) or \
        rel == "planning" or rel.startswith("planning" + os.sep)


def _diff_scale(root: Path):
    """返回 (files, added_lines) 估 diff 规模,失败 None。"""
    try:
        # case-392 security-review：原 shell=True + f"git -C {root} ..." 字符串插值，
        # root 虽经 _project_root exists() 门控，但路径名含 shell 元字符时可注入（与
        # autonomous-commit-gate.py case-378 同源类）。改 list 形式彻底去 shell。
        r = subprocess.run(
            ["git", "-C", str(root), "diff", "--cached", "--numstat"],
            capture_output=True, text=True, timeout=10)
        out = r.stdout
        if not out.strip():  # 回退到 unstaged
            r = subprocess.run(
                ["git", "-C", str(root), "diff", "--numstat"],
                capture_output=True, text=True, timeout=10)
            out = r.stdout
        files = added = 0
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit():
                files += 1
                added += int(parts[0])
        return (files, added) if files else None
    except Exception:
        return None


def _parse_git_cwd(cmd: str) -> str | None:
    m = re.search(r"-C\s+(\S+)", cmd)
    return m.group(1) if m else None


def main() -> None:
    event = os.environ.get("CLAUDE_HOOK_EVENT", "")
    tool = os.environ.get("CLAUDE_HOOK_TOOL_NAME", "")
    try:
        hook_input = json.loads(sys.stdin.read()) if sys.stdin.readable() else {}
    except Exception:
        hook_input = {}
    tool_input = hook_input.get("tool_input", {}) if isinstance(hook_input, dict) else {}

    # ── PreToolUse: Edit/Write/MultiEdit ───────────────────
    if event == "PreToolUse" and tool in ("Edit", "Write", "MultiEdit"):
        fp = tool_input.get("file_path", "")
        root = _project_root(fp)
        if not root:
            return  # 非 studio 项目
        if _is_doc_or_meta(fp, root):
            return  # 文档/planning/.pipeline 放行
        cur = _load_current(root)
        if not cur:
            _block(f"studio 项目改动前先 triage: python3 scripts/triage.py --kind small|complex --desc '...'"
                   f"  (project={root.name})")
        if cur.get("kind") == "complex" and cur.get("stage") not in ("development", "verify"):
            _block(f"complex 任务 stage={cur.get('stage')} — 须先走完 PRD 到 development: "
                   f"python3 scripts/triage.py --stage development  (project={root.name})")
        return

    # ── PreToolUse: Bash git commit/push ───────────────────
    if event == "PreToolUse" and tool == "Bash":
        cmd = tool_input.get("command", "")
        if _is_git_commit_or_push(cmd):
            cwd = _parse_git_cwd(cmd) or tool_input.get("cwd") or os.getcwd()
            root = _project_root(cwd)
            if not root:
                return  # 非 studio 项目提交
            cur = _load_current(root)
            if not cur:
                _audit_log_block(cmd, f"commit 前先 triage (project={root.name})")
                _block(f"commit 前先 triage: python3 scripts/triage.py --kind small|complex  (project={root.name})")
            if cur.get("kind") == "complex" and not cur.get("verify_passed"):
                _audit_log_block(cmd, f"complex commit 前须 verify (stage={cur.get('stage')}, project={root.name})")
                _block(f"complex 任务 commit 前须 verify: python3 scripts/triage.py --verify-passed"
                       f"  (stage={cur.get('stage')}, project={root.name})")
            if cur.get("kind") == "small":
                scale = _diff_scale(root)
                if scale and (scale[0] > 3 or scale[1] > 50):
                    _audit_log_block(cmd, f"small diff 超规模 (files={scale[0]}, +{scale[1]}行, project={root.name})")
                    _block(f"小修 triage 但 diff 超规模(files={scale[0]}, +{scale[1]}行) — "
                           f"重新: python3 scripts/triage.py --kind complex --desc '...'  (project={root.name})")
            return

    # ── Stop: 未收尾提醒 ───────────────────────────────────
    if event == "Stop":
        ws = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
        for p in [ws, *([x for x in ws.iterdir() if x.is_dir()] if ws.exists() else [])]:
            try:
                if (p / "planning" / "status.json").exists():
                    cur = _load_current(p)
                    if cur and cur.get("stage") != "done":
                        _remind(f"{p.name}: 改动未收尾(stage={cur.get('stage')}) — "
                                f"python3 scripts/triage.py --done 或继续推进")
            except Exception:
                pass
        return


if __name__ == "__main__":
    main()
