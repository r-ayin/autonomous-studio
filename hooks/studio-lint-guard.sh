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
#
# AS-M-001 fix (audit-2026-07-01-007): 旧实现用 `echo "$INPUT" | python3 -c "..."`
# 链式抽字段，content 含换行/引号/shell 元字符时 shell 转义断裂→lint 误判或静默放行。
# 改为单次 python3 完成所有字段抽取+语法校验+JSON 输出，shell 层只做 HOOK_EVENT 早筛。
# hook input 经环境变量 _AS_HOOK_INPUT 传入 python（避免 heredoc/pipe 抢 stdin 的 bash 陷阱）。

HOOK_EVENT="${CLAUDE_HOOK_EVENT:-unknown}"
if [ "$HOOK_EVENT" != "PreToolUse" ]; then
  echo '{}'
  exit 0
fi

# 缓存 stdin 到环境变量（hook input JSON），python 从 env 读，不经 shell 转义
_AS_HOOK_INPUT="$(cat)"
export _AS_HOOK_INPUT

python3 -c '
import sys, json, tempfile, os

def emit_block(reason):
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    sys.exit(0)

def emit_pass():
    print("{}")
    sys.exit(0)

raw = os.environ.get("_AS_HOOK_INPUT", "")
if not raw:
    emit_pass()

try:
    data = json.loads(raw)
except Exception:
    emit_pass()

tool_name = data.get("tool_name", "")
if tool_name not in ("Write", "Edit"):
    emit_pass()

tool_input = data.get("tool_input") or {}
file_path = tool_input.get("file_path", "")
# Write uses "content"; Edit uses "new_string". Extract whichever is present.
content = tool_input.get("content") or tool_input.get("new_string") or ""
if not file_path or content is None:
    emit_pass()

ext = file_path.rsplit(".", 1)[-1] if "." in file_path else ""

if ext == "py":
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8")
        tmp.write(content)
        tmp.close()
        import py_compile
        py_compile.compile(tmp.name, doraise=True)
    except SyntaxError as e:
        msg = str(e).split("\n")[0]
        emit_block(f"Lint guard: Python syntax error.\n{msg}")
    except py_compile.PyCompileError as e:
        msg = str(e).split("\n")[0]
        emit_block(f"Lint guard: Python compile error.\n{msg}")
    except Exception:
        pass
    finally:
        if tmp:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
elif ext == "json":
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        emit_block(f"Lint guard: JSON syntax error: {e}")
    except Exception:
        pass

emit_pass()
'
