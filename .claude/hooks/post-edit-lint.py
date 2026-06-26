"""post-edit-lint.py — PostToolUse Hook (matcher: Edit|Write)

每次 Edit/Write 后自动跑对应语法检查 + 关联测试，把结果作为 additionalContext 注入。
消除"写代码→忘了跑测试→下一轮才发现→再来回"的 token 浪费循环
（MSR 实测：代码评审/修复循环占 59.4% 总 token）。

非阻断：只把发现注入上下文，让 Claude 同轮修复，不 exit 2（避免打断）。
"""
import os
import sys
import json
import subprocess

if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKSPACE_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        print("{}")
        return

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        print("{}")
        return

    tool_input = data.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    if not file_path:
        print("{}")
        return

    findings = []

    # 绝对化
    if not os.path.isabs(file_path):
        file_path = os.path.join(WORKSPACE_ROOT, file_path)
    if not os.path.exists(file_path):
        print("{}")
        return

    ext = file_path.rsplit(".", 1)[-1] if "." in os.path.basename(file_path) else ""

    # Python：py_compile 语法检查
    if ext == "py":
        try:
            cr = subprocess.run(
                ["python", "-m", "py_compile", file_path],
                cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=15)
            if cr.returncode != 0:
                findings.append(f"❌ Python 语法错误: {(cr.stderr or '').strip().splitlines()[-1] if cr.stderr else ''}")
        except Exception as e:
            pass  # 不报错，静默跳过

        # 关联测试文件
        base = os.path.splitext(os.path.basename(file_path))[0]
        d = os.path.dirname(file_path)
        candidates = [
            os.path.join(d, f"test_{base}.py"),
            os.path.join(d, "tests", f"test_{base}.py"),
            os.path.join(d, f"{base}_test.py"),
        ]
        for tf in candidates:
            if os.path.exists(tf):
                try:
                    tr = subprocess.run(
                        ["python", "-m", "pytest", tf, "--tb=short", "-q"],
                        cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=60)
                    tail = (tr.stdout or tr.stderr or "").strip().splitlines()
                    summary = tail[-1] if tail else "(无输出)"
                    if tr.returncode == 0:
                        findings.append(f"✅ 关联测试通过: {tf}\n  {summary}")
                    else:
                        findings.append(f"❌ 关联测试失败: {tf}\n  {summary}")
                except Exception:
                    pass
                break

    # TypeScript/JavaScript：类型检查
    elif ext in ("ts", "tsx", "js", "jsx"):
        if subprocess.run(["which", "npx"], capture_output=True).returncode == 0:
            try:
                tr = subprocess.run(
                    ["npx", "--no-install", "tsc", "--noEmit", file_path],
                    cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=30)
                if tr.returncode != 0 and tr.stdout.strip():
                    findings.append(f"⚠️ 类型检查有提示: {chr(10).join(tr.stdout.strip().splitlines()[:5])}")
            except Exception:
                pass

    if not findings:
        print("{}")
        return

    msg = "**[post-edit-lint] 编辑后自动检查结果**:\n" + "\n".join(f"- {f}" for f in findings)
    print(json.dumps({"hookSpecificOutput": {"additionalContext": msg}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
