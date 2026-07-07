#!/bin/bash
# polyglot python shim: Linux(python3) / Windows(python)
PY="$(command -v python3 || command -v python || echo python)"
# studio-precheck.sh — 心跳预检，返回 proceed 或 skip:{原因}
# 用法: bash studio-precheck.sh /path/to/project

PROJ_DIR="${1:-.}"
STATUS_FILE="$PROJ_DIR/planning/status.json"
CAL_FILE="$PROJ_DIR/.claude/decisions/calibration.json"
STATE_FILE="$PROJ_DIR/.claude/memory/autonomous-state.md"
PROMPT_FILE="$HOME/.claude/skills/autonomous-studio/decision-agent-prompt.md"

# 1. decision-agent-prompt.md 存在？
if [ ! -f "$PROMPT_FILE" ]; then
  echo "skip:no-prompt-file"
  exit 0
fi

# 2. calibration 冷却检查
if [ -f "$CAL_FILE" ]; then
  CONSECUTIVE=$("$PY" -c "
import json, sys
try:
    d = json.load(open('$CAL_FILE'))
    print(d.get('cooldown', {}).get('current_consecutive', 0))
except: print(0)
" 2>/dev/null)
  if [ "${CONSECUTIVE:-0}" -ge 3 ]; then
    echo "skip:cooldown"
    exit 0
  fi
fi

# 3. 目标状态
if [ -f "$STATE_FILE" ]; then
  GOAL=$(grep "GOAL_STATUS:" "$STATE_FILE" | head -1 | awk '{print $2}')
  if [ "$GOAL" = "paused" ]; then
    echo "skip:paused"
    exit 0
  fi
fi

# 4. autoAdvance 开关
if [ -f "$STATUS_FILE" ]; then
  AUTO=$("$PY" -c "
import json, sys
try:
    d = json.load(open('$STATUS_FILE'))
    print(str(d.get('autoAdvance', True)).lower())
except: print('true')
" 2>/dev/null)
  if [ "$AUTO" = "false" ]; then
    echo "skip:auto-advance-off"
    exit 0
  fi
fi

echo "proceed"
