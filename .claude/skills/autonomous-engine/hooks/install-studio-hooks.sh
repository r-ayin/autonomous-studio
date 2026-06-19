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
for f in studio-progress-check.sh studio-prd-validate.sh studio-auto-commit-remind.sh; do
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

# Hook entries to inject
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

# Check which (matcher, command) pairs already exist
existing_pairs = set()
for entry in post_tool:
    matcher = entry.get("matcher", "")
    for h in entry.get("hooks", []):
        cmd = h.get("command", "")
        if "studio-" in cmd:
            existing_pairs.add((matcher, cmd))

# Only add missing ones
for hook_entry in new_hooks:
    matcher = hook_entry["matcher"]
    cmd = hook_entry["hooks"][0]["command"]
    if (matcher, cmd) not in existing_pairs:
        post_tool.append(hook_entry)
        existing_pairs.add((matcher, cmd))

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
PYEOF

echo "Studio hooks installed successfully."
