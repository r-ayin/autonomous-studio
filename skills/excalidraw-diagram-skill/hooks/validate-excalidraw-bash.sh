#!/bin/bash
# PostToolUse hook for Bash: detect if a .excalidraw.json file was modified by a script
# Check recent modifications to excalidraw files in the workspace

SCRIPT="$HOME/.claude/skills/excalidraw-diagram-skill/references/validate_geometry.py"
if [[ ! -f "$SCRIPT" ]]; then
    exit 0
fi

# Find .excalidraw.json files modified in the last 5 seconds
MODIFIED=$(find ~/workspace/excalidraw -name '*.excalidraw.json' -not -path '*/.versions/*' -newer /tmp/.excalidraw-last-check 2>/dev/null)

# Update timestamp marker
touch /tmp/.excalidraw-last-check

HAS_FAILURE=0
if [[ -n "$MODIFIED" ]]; then
    for FILE in $MODIFIED; do
        RESULT=$(python3 "$SCRIPT" "$FILE" 2>&1)
        EXIT_CODE=$?
        if [[ $EXIT_CODE -ne 0 ]]; then
            echo "⚠️ Excalidraw 验证未通过 ($(basename $FILE))："
            echo "$RESULT" | grep -E '^\s+-|TOTAL'
            echo ""
            echo "请修复以上问题后再继续。"
            HAS_FAILURE=1
        fi
    done
fi

if [[ $HAS_FAILURE -eq 1 ]]; then
    exit 1
fi
