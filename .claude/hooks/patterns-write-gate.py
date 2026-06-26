"""patterns-write-gate.py — PreToolUse Hook (matcher: Edit|Write|MultiEdit)

强制 decision-patterns.md 的修改只能经 scripts/distill-patterns.py（含 verify-pattern.sh 门禁），
不允许 LLM agent 直接 Edit/Write。distill 脚本用 Python open() 直写，不走工具调用，不受此 hook 限制。

原则（研究）："提示词不是护栏"——LLM 子 agent 可能绕过"不要直接改 patterns.md"的文本指令，
bash/python 阻断不可协商。patterns.md 是蒸馏产物，必须经 outcome→accuracy 确定性计算 + 门禁。
"""
import os, sys, json

if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROTECTED = "memory/decision-patterns.md"


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        print("{}")
        return
    tool = data.get("tool_name", "")
    if tool not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        print("{}")
        return
    fp = (data.get("tool_input") or {}).get("file_path", "") or ""
    if not fp:
        print("{}")
        return
    # 归一化比较末尾路径
    norm = fp.replace("\\", "/")
    if norm.endswith(PROTECTED) or norm.endswith("/" + PROTECTED):
        print(json.dumps({
            "decision": "block",
            "reason": (
                "decision-patterns.md 是蒸馏产物，禁止直接编辑。\n"
                "patterns.md 的更新必须经 scripts/distill-patterns.py --apply（它会从 case outcome "
                "确定性计算 accuracy + 跑 verify-pattern.sh 门禁 + 同步 calibration.json）。\n"
                "如需新增/修改 pattern：在 case-*.json 的 retrospect.new_pattern_discovered 标注签名前缀，"
                "然后跑 distill-patterns.py。"
            )
        }, ensure_ascii=False))
        sys.exit(2)
    print("{}")


if __name__ == "__main__":
    main()
