#!/usr/bin/env python3
"""增量保存（纯后台，无 AI 参与）
由后台 bash 循环每 120 秒调用一次。
只做文件级操作：checkpoint JSON + memory 时间戳更新。
"""

import os
import json
import sys
from datetime import datetime, timezone

# Windows GBK 编码兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
MEMORY_FILE = os.path.join(PROJECT_DIR, ".claude", "memory", "session-progress.md")
CHECKPOINT_SCRIPT = os.path.join(PROJECT_DIR, ".claude", "hooks", "save-checkpoint.py")


def update_memory_timestamp():
    """在 memory 文件末尾追加时间戳（轻量级增量标记）"""
    if not os.path.exists(MEMORY_FILE):
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    marker = f"\n<!-- auto-saved {now} -->\n"

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # 替换上一次的 auto-saved 标记，只保留最新
        import re
        content = re.sub(r"<!-- auto-saved .*? -->\n?", "", content)

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write(content.rstrip() + marker)
    except Exception:
        pass


if __name__ == "__main__":
    # 1. 运行 checkpoint 保存（调用现有脚本的核心逻辑）
    try:
        import subprocess
        subprocess.run(
            [sys.executable, CHECKPOINT_SCRIPT],
            cwd=PROJECT_DIR,
            timeout=10,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    # 2. 更新 memory 时间戳
    update_memory_timestamp()
