#!/usr/bin/env python3
"""增量保存（纯后台，无 AI 参与）
由后台 bash 循环每 120 秒调用一次。
只做文件级操作：checkpoint JSON + memory 时间戳更新。
"""

import os
import json
import sys
import fcntl
import re
import tempfile
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
STUDIO_STATUS_FILE = os.path.join(PROJECT_DIR, "planning", "status.json")
CHECKPOINT_DIR = os.path.join(PROJECT_DIR, ".claude", "checkpoints")


def _atomic_write_text(filepath, text):
    """原子写文本：tempfile + flush/fsync + os.replace。失败清理临时文件。

    audit-2026-07-03-017 M-009: session-progress.md 之前 open('w') 截断后写，中途
    kill/断电留半写文件；下次读时 marker regex 匹配不到旧标记 → 重复追加或丢内容。
    改用与 save-checkpoint._atomic_write_json 同模式的原子写。
    """
    dst_dir = os.path.dirname(filepath) or "."
    fd, tmp = tempfile.mkstemp(prefix=".mem-", suffix=".tmp", dir=dst_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, filepath)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
        content = re.sub(r"<!-- auto-saved .*? -->\n?", "", content)
        _atomic_write_text(MEMORY_FILE, content.rstrip() + marker)
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

    # 3. ★ 追加 Studio status.json 快照到检查点（解决遗漏J）
    #    audit-2026-07-03-017 M-010: latest.json 同时被 save-checkpoint.py 与本脚本写入，
    #    无锁时并发 read-modify-write 会丢字段（A 读→B 读→A 写→B 写覆盖 A）。加 flock
    #    互斥；超时拿不到锁则跳过本轮（后台 120s 重试，不阻塞主流程）。
    try:
        if os.path.exists(STUDIO_STATUS_FILE):
            with open(STUDIO_STATUS_FILE, "r", encoding="utf-8") as f:
                studio_status = json.load(f)

            latest_cp = os.path.join(CHECKPOINT_DIR, "latest.json")
            lock_path = latest_cp + ".lock"
            if os.path.exists(latest_cp):
                lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
                try:
                    try:
                        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except (BlockingIOError, OSError):
                        # 另一进程正写 latest.json，本轮跳过，120s 后重试
                        os.close(lock_fd)
                        raise RuntimeError("latest.json locked, skip this tick")

                    with open(latest_cp, "r", encoding="utf-8") as f:
                        cp_data = json.load(f)

                    cp_data["studio_status"] = {
                        "currentStage": studio_status.get("currentStage"),
                        "completedStages": studio_status.get("completedStages", []),
                        "taskType": studio_status.get("taskType"),
                        "notes": studio_status.get("notes"),
                        "locked": studio_status.get("locked"),
                        "engine_autoAdvance": studio_status.get("engine", {}).get("autoAdvance"),
                        "engine_nextActionHint": studio_status.get("engine", {}).get("nextActionHint"),
                        "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }

                    # 原子写 + fsync（case-484 + M-008 同款防御）
                    dst_dir = os.path.dirname(latest_cp)
                    fd, tmp_path = tempfile.mkstemp(prefix=".latest-", suffix=".tmp", dir=dst_dir)
                    try:
                        with os.fdopen(fd, "w", encoding="utf-8") as f:
                            json.dump(cp_data, f, ensure_ascii=False, indent=2)
                            f.flush()
                            os.fsync(f.fileno())
                        os.replace(tmp_path, latest_cp)
                    except Exception:
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass
                        raise
                finally:
                    try:
                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
                    os.close(lock_fd)
    except RuntimeError:
        # 锁竞争跳过，非错误
        pass
    except Exception:
        pass
