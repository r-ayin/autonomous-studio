#!/bin/bash
# PostToolUse hook: 每次写入 prd.json 后自动检查进度

# 从 CLAUDE_TOOL_INPUT 获取文件路径
FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('file_path', ''))
except:
    print('')
" 2>/dev/null)

# 只关心 prd.json
if [[ "$FILE_PATH" != *"planning/prd.json" ]]; then
    exit 0
fi

# 检查是否在 Studio 模式（status.json 存在且 locked=true）
PROJECT_DIR=$(dirname "$(dirname "$FILE_PATH")")
STATUS_FILE="$PROJECT_DIR/planning/status.json"

if [[ ! -f "$STATUS_FILE" ]]; then
    exit 0
fi

# 用 Python 检查: 所有 P0 task 是否都 done + 当前 stage
python3 << PYEOF
import json, sys
from datetime import datetime

status_path = "$STATUS_FILE"
prd_path = "$FILE_PATH"

try:
    with open(status_path) as f:
        status = json.load(f)
    with open(prd_path) as f:
        prd = json.load(f)
except:
    sys.exit(0)

if not status.get('locked', False):
    sys.exit(0)

current_stage = status.get('currentStage', '')
if current_stage != 'development':
    sys.exit(0)

# 统计 P0 任务状态
total_p0 = 0
done_p0 = 0
blocked_p0 = 0
for node in prd.get('nodes', []):
    for task in node.get('tasks', []):
        if task.get('priority') == 'P0':
            total_p0 += 1
            if task.get('status') == 'done':
                done_p0 += 1
            if task.get('blocked'):
                blocked_p0 += 1

# 输出进度
print(f"Studio 进度: {done_p0}/{total_p0} P0 任务完成", end="")
if blocked_p0 > 0:
    print(f" ({blocked_p0} 被阻塞)", end="")

# 如果所有 P0 都完成 → 自动推进 status.json
if total_p0 > 0 and done_p0 >= total_p0 - blocked_p0:
    status['currentStage'] = 'verification'
    if 'development' not in status.get('completedStages', []):
        status.setdefault('completedStages', []).append('development')
    status['lastUpdated'] = datetime.now().isoformat()
    with open(status_path, 'w') as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
    print(f"\n所有 P0 任务完成，已自动推进到验证阶段")
else:
    print()
PYEOF
