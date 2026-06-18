#!/bin/bash
# PostToolUse hook: check if .planning/status.json needs updating after git commit
# Runs after Bash tool - detects if a git commit just happened on .planning/ files

TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

# Only check after Bash commands that contain "git commit"
if ! echo "$TOOL_INPUT" | grep -q "git commit"; then
  exit 0
fi

# Check if we're in a git repo with .planning/ directory
if [ ! -d ".planning" ] && [ ! -d "$(git rev-parse --show-toplevel 2>/dev/null)/.planning" ]; then
  exit 0
fi

PROJ_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
STATUS_FILE="$PROJ_ROOT/.planning/status.json"

# Check if any .planning/ files were just committed (requirements.md, prd.md, tech-plan.md)
COMMITTED_PLANNING=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep "^\.planning/" | grep -v "status.json")

if [ -n "$COMMITTED_PLANNING" ]; then
  # Planning files were committed - check if status.json was also updated
  STATUS_UPDATED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep "status.json")

  if [ -z "$STATUS_UPDATED" ]; then
    echo "⚠️ .planning/ 文件已提交但 status.json 未更新！"
    echo "已提交的文件: $COMMITTED_PLANNING"
    echo "请更新 .planning/status.json 的 currentStage 和 completedStages。"
    exit 1
  fi
fi

# Check if source code was committed but status.json still shows pre-development stage
if [ -f "$STATUS_FILE" ]; then
  CURRENT_STAGE=$(python3 -c "import json; print(json.load(open('$STATUS_FILE')).get('currentStage',''))" 2>/dev/null)
  CODE_COMMITTED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -E "\.(tsx?|jsx?|css|html)$" | head -1)

  if [ -n "$CODE_COMMITTED" ] && [ "$CURRENT_STAGE" = "development" ]; then
    # Code committed while in development stage - remind to advance
    echo "💡 代码已提交。开发完成后记得把 status.json 的 currentStage 更新为 verification。"
  fi
fi
