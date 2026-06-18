#!/bin/bash
# Auto-install excalidraw validation hooks.
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
for f in validate-excalidraw.sh validate-excalidraw-bash.sh; do
    SRC="$SKILL_DIR/hooks/$f"
    DST="$HOOKS_DIR/$f"
    if [[ ! -f "$DST" ]] || ! cmp -s "$SRC" "$DST"; then
        cp "$SRC" "$DST"
        chmod +x "$DST"
        CHANGED=1
    fi
done

# ── 2. Inject hook config into settings.json (if not present) ─
if [[ -f "$SETTINGS" ]] && grep -q "validate-excalidraw" "$SETTINGS" 2>/dev/null; then
    # Already configured
    exit 0
fi

# Use Python for safe JSON manipulation
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
        "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/validate-excalidraw.sh", "timeout": 10, "statusMessage": "验证 Excalidraw 图表..."}]
    },
    {
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/validate-excalidraw.sh", "timeout": 10, "statusMessage": "验证 Excalidraw 图表..."}]
    },
    {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/validate-excalidraw-bash.sh", "timeout": 10, "statusMessage": "验证 Excalidraw 图表..."}]
    },
]

# Check which matchers already have excalidraw hooks
existing = set()
for entry in post_tool:
    for h in entry.get("hooks", []):
        if "validate-excalidraw" in h.get("command", ""):
            existing.add(entry.get("matcher", ""))

# Only add missing ones
for hook_entry in new_hooks:
    if hook_entry["matcher"] not in existing:
        post_tool.append(hook_entry)

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
PYEOF
