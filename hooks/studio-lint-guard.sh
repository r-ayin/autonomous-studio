#!/bin/bash
# studio-lint-guard.sh — ACI 风格的编辑前语法校验（Tier 0 Hook）
#
# 设计来源：SWE-agent ACI 论文（NeurIPS 2024）的核心发现：
#   "内置 linter 自动拒绝语法错误的编辑"让 agent 成绩翻倍。
#   Claude Code 原生不包含此机制——Write 操作不做语法校验。
#
# 触发时机：PreToolUse（Write/Edit 操作时）
# 行为：对写入的文件做轻量语法检查，失败时阻断并返回错误信息
# 约束：<200ms，仅检查语法不检查逻辑，静默处理不支持的文件类型

HOOK_EVENT="${CLAUDE_HOOK_EVENT:-unknown}"
if [ "$HOOK_EVENT" != "PreToolUse" ]; then
  echo '{}'
  exit 0
fi

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)

if [ "$TOOL_NAME" != "Write" ]; then
  echo '{}'
  exit 0
fi

FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
  echo '{}'
  exit 0
fi

EXT="${FILE_PATH##*.}"
ERROR=""

case "$EXT" in
  py)
    CONTENT=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('content',''))" 2>/dev/null)
    if [ -n "$CONTENT" ]; then
      ERROR=$(echo "$CONTENT" | python3 -c "
import sys, py_compile, tempfile, os
code = sys.stdin.read()
tmp = tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w')
tmp.write(code)
tmp.close()
try:
    py_compile.compile(tmp.name, doraise=True)
except py_compile.PyCompileError as e:
    print(str(e).split('\\n')[0])
finally:
    os.unlink(tmp.name)
" 2>/dev/null)
    fi
    ;;
  json)
    CONTENT=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('content',''))" 2>/dev/null)
    if [ -n "$CONTENT" ]; then
      ERROR=$(echo "$CONTENT" | python3 -c "
import sys, json
try:
    json.loads(sys.stdin.read())
except json.JSONDecodeError as e:
    print(f'JSON syntax error: {e}')
" 2>/dev/null)
    fi
    ;;
  *)
    # 不支持的文件类型，放行
    ;;
esac

if [ -n "$ERROR" ]; then
  python3 -c "
import json
print(json.dumps({
    'decision': 'block',
    'reason': 'Lint guard: syntax error detected. Fix the error before writing.\n$ERROR'
}, ensure_ascii=False))
"
else
  echo '{}'
fi
