#!/bin/bash
# PostToolUse hook: 验证 prd.json 格式

FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('file_path', ''))
except:
    print('')
" 2>/dev/null)

if [[ "$FILE_PATH" != *"planning/prd.json" ]]; then
    exit 0
fi

if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

export FILE_PATH
python3 << PYEOF
import json, os, sys

try:
    file_path = os.environ["FILE_PATH"]
    with open(file_path) as f:
        prd = json.load(f)
except json.JSONDecodeError as e:
    print(f"prd.json 格式错误: {e}")
    sys.exit(1)

errors = []

# 必须有 nodes
if 'nodes' not in prd:
    errors.append("缺少 nodes 字段")

# 每个 node 必须有 id, name, tasks
for i, node in enumerate(prd.get('nodes', [])):
    if 'id' not in node:
        errors.append(f"nodes[{i}] 缺少 id")
    if 'tasks' not in node:
        errors.append(f"nodes[{i}] 缺少 tasks")
    for j, task in enumerate(node.get('tasks', [])):
        for field in ['id', 'title', 'status', 'priority']:
            if field not in task:
                errors.append(f"nodes[{i}].tasks[{j}] 缺少 {field}")
        if task.get('status') not in [None, 'pending', 'in_progress', 'done']:
            errors.append(f"nodes[{i}].tasks[{j}] status 值无效: {task.get('status')}")

if errors:
    print("prd.json 验证未通过:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
PYEOF
