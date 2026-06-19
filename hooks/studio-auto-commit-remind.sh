#!/bin/bash
# PostToolUse hook: Studio 开发阶段提醒提交代码

FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('file_path', data.get('command', '')))
except:
    print('')
" 2>/dev/null)

# 跳过非代码文件
if [[ "$FILE_PATH" == *".claude/"* ]] || [[ "$FILE_PATH" == *"planning/"* ]] || [[ "$FILE_PATH" == *"node_modules/"* ]]; then
    exit 0
fi

# 找到项目根目录（有 planning/status.json 的目录）
find_project_root() {
    local dir="$1"
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/planning/status.json" ]]; then
            echo "$dir"
            return
        fi
        dir=$(dirname "$dir")
    done
}

PROJECT_DIR=$(find_project_root "$(dirname "$FILE_PATH")")
if [[ -z "$PROJECT_DIR" ]]; then
    exit 0
fi

STATUS_FILE="$PROJECT_DIR/planning/status.json"

# 检查是否在开发阶段
STAGE=$(python3 -c "
import json
try:
    d = json.load(open('$STATUS_FILE'))
    print(d.get('currentStage', ''))
except: print('')
" 2>/dev/null)

if [[ "$STAGE" != "development" ]]; then
    exit 0
fi

# 检查未提交文件数
cd "$PROJECT_DIR"
UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l)

if [[ "$UNCOMMITTED" -ge 3 ]]; then
    echo "Studio 提醒: ${UNCOMMITTED} 个文件未提交，建议 git commit"
fi
