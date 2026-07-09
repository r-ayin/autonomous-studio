"""user-style-write-gate.py — PreToolUse Hook (matcher: Edit|Write|MultiEdit)

强制 user-decision-style.md 的修改只能经 scripts/distill-user-style.py（含 verify-user-style.sh
门禁），不允许 LLM agent 直接 Edit/Write。distill 脚本用 Python open() 直写，不走工具调用，
不受此 hook 限制（与 patterns-write-gate.py 同机制）。

原则（研究）："提示词不是护栏"——LLM 子 agent 可能绕过"不要直接改 user-decision-style.md"
的文本指令，bash/python 阻断不可协商。user-decision-style.md 是蒸馏产物，必须经
transcript→TF-IDF 去重→LLM 蒸馏→门禁链路。
"""
import os, sys, json

if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROTECTED = "memory/user-decision-style.md"


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
    # 归一化比较末尾路径：os.path.normpath 折叠 ./、//、../，防 LLM 用
    # "memory/./user-decision-style.md" / "memory//user-decision-style.md" 等路径混淆
    # 绕过 endswith 字符串匹配（与 patterns-write-gate.py case-480 同源修复）。
    norm = os.path.normpath(fp.replace("\\", "/"))
    prot = os.path.normpath(PROTECTED)
    if norm == prot or norm.endswith("/" + prot):
        print(json.dumps({
            "decision": "block",
            "reason": (
                "user-decision-style.md 是蒸馏产物，禁止直接编辑。\n"
                "user-decision-style.md 的更新必须经 scripts/distill-user-style.py --apply\n"
                "（它从 ~/.claude/projects/*.jsonl 的 type=user 行 TF-IDF 去重 + LLM 蒸馏\n"
                " + 跑 verify-user-style.sh 门禁 + Python open() 直写）。\n"
                "如需新增/修改风格规则：在会话里多给几条同类指示（≥2 条独立输入支撑），\n"
                "然后跑 distill-user-style.py --llm --apply 重新蒸馏。"
            )
        }, ensure_ascii=False))
        sys.exit(2)
    print("{}")


if __name__ == "__main__":
    main()
