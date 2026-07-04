#!/bin/bash
# Auto-install Studio hooks for autonomous-studio skill.
# Idempotent: safe to run on every skill trigger.
# - Copies hook scripts to ~/.claude/hooks/
# - Injects PostToolUse entries into ~/.claude/settings.json (if not present)

set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"

mkdir -p "$HOOKS_DIR"

# ── 1. Copy hook scripts (only if changed) ────────────────────
CHANGED=0
for f in studio-progress-check.sh studio-prd-validate.sh studio-auto-commit-remind.sh studio-lint-guard.sh; do
    SRC="$SKILL_DIR/hooks/$f"
    DST="$HOOKS_DIR/$f"
    if [[ ! -f "$DST" ]] || ! cmp -s "$SRC" "$DST"; then
        cp "$SRC" "$DST"
        chmod +x "$DST"
        CHANGED=1
    fi
done

# ── 2. Inject hook config into settings.json (if not present) ─
# Use Python for safe JSON manipulation (idempotent: skips already-present entries)
python3 << 'PYEOF'
import json, os

settings_path = os.path.expanduser("~/.claude/settings.json")

# Read or create settings
if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
else:
    settings = {}

hooks = settings.setdefault("hooks", {})
post_tool = hooks.setdefault("PostToolUse", [])
pre_tool = hooks.setdefault("PreToolUse", [])

# Hook entries to inject (PostToolUse)
new_hooks = [
    {
        "matcher": "Write",
        "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/studio-prd-validate.sh", "timeout": 10, "statusMessage": "验证 prd.json 格式..."}]
    },
    {
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/studio-prd-validate.sh", "timeout": 10, "statusMessage": "验证 prd.json 格式..."}]
    },
    {
        "matcher": "Write",
        "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/studio-progress-check.sh", "timeout": 10, "statusMessage": "检查 Studio 进度..."}]
    },
    {
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/studio-progress-check.sh", "timeout": 10, "statusMessage": "检查 Studio 进度..."}]
    },
    {
        "matcher": "Write",
        "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/studio-auto-commit-remind.sh", "timeout": 10, "statusMessage": "检查提交状态..."}]
    },
    {
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/studio-auto-commit-remind.sh", "timeout": 10, "statusMessage": "检查提交状态..."}]
    },
]

# PreToolUse hook entries (lint guard runs BEFORE Write/Edit to reject syntax errors)
new_pre_hooks = [
    {
        "matcher": "Write",
        "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/studio-lint-guard.sh", "timeout": 5, "statusMessage": "语法预检..."}]
    },
    {
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/studio-lint-guard.sh", "timeout": 5, "statusMessage": "语法预检..."}]
    },
]

def _existing_pairs(entries):
    pairs = set()
    for entry in entries:
        matcher = entry.get("matcher", "")
        for h in entry.get("hooks", []):
            cmd = h.get("command", "")
            if "studio-" in cmd:
                pairs.add((matcher, cmd))
    return pairs

# Only add missing PostToolUse entries
existing_post = _existing_pairs(post_tool)
for hook_entry in new_hooks:
    matcher = hook_entry["matcher"]
    cmd = hook_entry["hooks"][0]["command"]
    if (matcher, cmd) not in existing_post:
        post_tool.append(hook_entry)
        existing_post.add((matcher, cmd))

# Only add missing PreToolUse entries
existing_pre = _existing_pairs(pre_tool)
for hook_entry in new_pre_hooks:
    matcher = hook_entry["matcher"]
    cmd = hook_entry["hooks"][0]["command"]
    if (matcher, cmd) not in existing_pre:
        pre_tool.append(hook_entry)
        existing_pre.add((matcher, cmd))

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
PYEOF

echo "Studio hooks installed successfully."
