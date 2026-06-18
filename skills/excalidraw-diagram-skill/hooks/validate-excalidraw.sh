#!/bin/bash
# PostToolUse hook: auto-validate after writing .excalidraw.json files
# Reads $CLAUDE_TOOL_INPUT to find the file path

FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('file_path', data.get('command', '')))
except:
    print('')
" 2>/dev/null)

if [[ "$FILE_PATH" == *.excalidraw.json ]]; then
    SCRIPT="$HOME/.claude/skills/excalidraw-diagram-skill/references/validate_geometry.py"
    if [[ -f "$SCRIPT" && -f "$FILE_PATH" ]]; then
        RESULT=$(python3 "$SCRIPT" "$FILE_PATH" 2>&1)
        EXIT_CODE=$?
        if [[ $EXIT_CODE -ne 0 ]]; then
            echo "⚠️ Excalidraw 验证未通过："
            echo "$RESULT" | grep -E '^\s+-|TOTAL'
            echo ""
            echo "请修复以上问题后再继续。"
            exit 1
        fi
    fi
fi
