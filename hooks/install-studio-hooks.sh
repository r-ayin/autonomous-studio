#!/bin/bash
# polyglot python shim: Linux(python3) / Windows(python)
PY="$(command -v python3 || command -v python || echo python)"
# =============================================================================
# install-studio-hooks.sh — 引擎全栈部署器 (v6.2)
# =============================================================================
# 幂等：每次 skill 激活可安全重跑。
#   1. 部署全部引擎 hook（Python + Shell）到 ~/.claude/hooks/
#   2. 在 ~/.claude/settings.json 注册完整 v6.2 门禁栈
#      （先移除所有本脚本管理的旧条目再写入规范条目 → 消除历史双注册/散条目）
#   3. 其余 settings 内容（claude-spy / claude-brain / permissions / env）原样保留
#
# 规范栈（与 SKILL.md「Hook 栈」一节一一对应）:
#   UserPromptSubmit : decision-observer + discovery-gate
#   PreToolUse ""    : discovery-gate + pipeline-gate
#   PreToolUse Bash  : autonomous-commit-gate
#   PreToolUse E|W   : patterns-write-gate + studio-lint-guard + protocol-check
#   PostToolUse E|W  : post-edit-lint + protocol-check + studio-prd-validate
#                      + studio-progress-check + studio-auto-commit-remind
#   PostToolUse AskUserQuestion : notify-phone
#   Stop             : stop-completion-gate + pipeline-gate + decision-observer
#                      + incremental-save + save-checkpoint + auto-commit
#   PreCompact       : save-checkpoint
#   SessionStart     : resume-checkpoint + codegraph-sync
#   SessionEnd       : save-checkpoint + auto-commit
# =============================================================================

set -e

# 源目录：优先 skill 布局（hooks/ 平级），否则仓库布局（.claude/hooks + hooks/）
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SELF_DIR/.." && pwd)"
HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"

mkdir -p "$HOOKS_DIR"

PY_HOOKS="decision-observer.py discovery-gate.py pipeline-gate.py autonomous-commit-gate.py patterns-write-gate.py protocol-check.py post-edit-lint.py notify-phone.py stop-completion-gate.py incremental-save.py save-checkpoint.py resume-checkpoint.py codegraph-sync.py auto-commit.py"
SH_HOOKS="studio-progress-check.sh studio-prd-validate.sh studio-auto-commit-remind.sh studio-lint-guard.sh check-planning-status.sh"

_find_src() {  # $1=filename → 输出源路径（skill 布局 / 仓库布局兼容）
    for d in "$SELF_DIR" "$REPO_DIR/hooks" "$REPO_DIR/.claude/hooks"; do
        [ -f "$d/$1" ] && { echo "$d/$1"; return 0; }
    done
    return 1
}

# ── 1. 部署 hook 脚本（仅在变化时覆盖）────────────────────────
CHANGED=0
for f in $PY_HOOKS $SH_HOOKS; do
    SRC="$(_find_src "$f" || true)"
    if [ -z "$SRC" ]; then
        echo "WARN: 源缺失 $f（跳过）" >&2
        continue
    fi
    DST="$HOOKS_DIR/$f"
    if [ ! -f "$DST" ] || ! cmp -s "$SRC" "$DST"; then
        cp "$SRC" "$DST" && chmod +x "$DST"
        CHANGED=1
    fi
done

# ── 2. 注册规范栈（remove-managed-then-insert，强幂等）────────
# 安装机 python 探测结果直接烘焙进命令串（Windows=python / Linux=python3）
PYBIN="$(basename "$PY")"
export PYBIN SETTINGS
"$PY" << 'PYEOF'
import json, os

settings_path = os.environ["SETTINGS"]
pybin = os.environ.get("PYBIN", "python3")
H = "${HOME}/.claude/hooks"   # 留给 Claude Code 运行时展开

settings = {}
if os.path.exists(settings_path):
    with open(settings_path, encoding="utf-8") as f:
        settings = json.load(f)

hooks = settings.setdefault("hooks", {})

# 本脚本管理的脚本名（出现即视为托管条目，重建时先移除）
MANAGED = [
    "decision-observer.py", "discovery-gate.py", "pipeline-gate.py",
    "autonomous-commit-gate.py", "patterns-write-gate.py", "protocol-check.py",
    "post-edit-lint.py", "notify-phone.py", "stop-completion-gate.py",
    "incremental-save.py", "save-checkpoint.py", "resume-checkpoint.py",
    "codegraph-sync.py", "auto-commit.py",
    "studio-progress-check.sh", "studio-prd-validate.sh",
    "studio-auto-commit-remind.sh", "studio-lint-guard.sh",
]

def is_managed(cmd: str) -> bool:
    return any(m in cmd for m in MANAGED)

def _filter_command(cmd: str):
    """分段过滤：按 ';' 拆分命令串，仅移除引擎托管片段，
    保留同一条命令里的第三方片段（如 claude-brain plugin hooks）。"""
    if not is_managed(cmd):
        return cmd
    segs = [s.strip() for s in cmd.split(";")]
    kept = [s for s in segs if s and s != "true" and not is_managed(s)]
    if not kept:
        return None
    return "; ".join(kept) + "; true"

def strip_managed(event_rules):
    kept = []
    for rule in event_rules:
        hs = []
        for h in rule.get("hooks", []):
            cmd = h.get("command", "")
            new_cmd = _filter_command(cmd)
            if new_cmd is None:
                continue
            if new_cmd != cmd:
                h = dict(h); h["command"] = new_cmd
            hs.append(h)
        if hs:
            rule = dict(rule); rule["hooks"] = hs
            kept.append(rule)
    return kept

for ev in list(hooks.keys()):
    hooks[ev] = strip_managed(hooks[ev])

def py(script, quiet=True):
    tail = " >/dev/null 2>/dev/null" if quiet else " 2>/dev/null"
    return {"type": "command", "command": f'{pybin} "{H}/{script}"' + tail}

def sh(script, timeout=10, status=None):
    h = {"type": "command", "command": f'bash "{H}/{script}"', "timeout": timeout}
    if status: h["statusMessage"] = status
    return h

def chain(*scripts):
    """多个 python hook 串成一条命令（; 分隔，容错 true 结尾）"""
    cmds = "; ".join(f'{pybin} "{H}/{s}" 2>/dev/null' for s in scripts)
    return {"type": "command", "command": cmds + "; true"}

CANON = {
    "UserPromptSubmit": [
        {"matcher": "", "hooks": [py("decision-observer.py", quiet=False),
                                   py("discovery-gate.py", quiet=False)]},
    ],
    "PreToolUse": [
        {"matcher": "", "hooks": [py("discovery-gate.py", quiet=False),
                                   py("pipeline-gate.py", quiet=False)]},
        {"matcher": "Bash", "hooks": [py("autonomous-commit-gate.py", quiet=False)]},
        {"matcher": "Edit|Write", "hooks": [
            py("patterns-write-gate.py", quiet=False),
            sh("studio-lint-guard.sh", timeout=5, status="语法预检..."),
            py("protocol-check.py", quiet=False),
        ]},
    ],
    "PostToolUse": [
        {"matcher": "Edit|Write", "hooks": [
            py("post-edit-lint.py", quiet=False),
            sh("studio-prd-validate.sh", status="验证 prd.json 格式..."),
            sh("studio-progress-check.sh", status="检查 Studio 进度..."),
            sh("studio-auto-commit-remind.sh", status="检查提交状态..."),
        ]},
        {"matcher": "AskUserQuestion", "hooks": [py("notify-phone.py")]},
    ],
    "Stop": [
        {"matcher": "", "hooks": [
            py("stop-completion-gate.py", quiet=False),
            py("pipeline-gate.py", quiet=False),
            chain("decision-observer.py", "incremental-save.py",
                  "save-checkpoint.py", "auto-commit.py"),
        ]},
    ],
    "PreCompact": [
        {"matcher": "", "hooks": [py("save-checkpoint.py")]},
    ],
    "SessionStart": [
        {"matcher": "", "hooks": [{
            "type": "command",
            # resume-checkpoint 的 stdout 是固件注入，必须保留；codegraph-sync 全静默
            "command": (f'{pybin} "{H}/resume-checkpoint.py" 2>/dev/null; '
                        f'{pybin} "{H}/codegraph-sync.py" >/dev/null 2>/dev/null; true'),
        }]},
    ],
    "SessionEnd": [
        {"matcher": "", "hooks": [chain("save-checkpoint.py", "auto-commit.py")]},
    ],
}

for ev, rules in CANON.items():
    hooks.setdefault(ev, []).extend(rules)

# 清掉被 strip 后可能残留的空事件
settings["hooks"] = {ev: rs for ev, rs in hooks.items() if rs}

tmp = settings_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
os.replace(tmp, settings_path)
print("settings.json 引擎栈已重建 (managed entries: rebuilt)")
PYEOF

echo "Studio hooks installed successfully. (changed=$CHANGED)"
