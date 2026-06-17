#!/usr/bin/env python3
"""自动保存检查点 — SSH 断开后恢复会话上下文

触发时机：
  1. PreCompact — 上下文压缩前（正常运行中）
  2. Stop — 会话结束时（含 SSH 断开）
  3. SessionEnd — 会话终止时

恢复方式：
  新会话启动后自动检测并恢复（无需手动操作）
"""

import os
import json
import sys
import subprocess
from datetime import datetime, timezone

# Windows GBK 编码兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run(cmd, timeout=3):
    """安全执行 shell 命令（Windows 兼容——% 符号转义）"""
    try:
        # Windows cmd.exe 会把 %h %s 当成变量展开→需双重转义
        if sys.platform == "win32" and "%" in cmd:
            cmd = cmd.replace("%", "%%")
        return subprocess.check_output(
            cmd, shell=True, cwd=PROJECT_DIR, text=True, encoding="utf-8", timeout=timeout
        ).strip()
    except Exception:
        return ""


# ── 环境变量 ──────────────────────────────────
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
SESSION_ID = os.environ.get("CLAUDE_SESSION_ID", "unknown")
HOOK_EVENT = os.environ.get("CLAUDE_HOOK_EVENT", "unknown")

CHECKPOINT_DIR = os.path.join(PROJECT_DIR, ".claude", "checkpoints")
LATEST_LINK = os.path.join(CHECKPOINT_DIR, "latest.json")
MAX_CHECKPOINTS = 20

os.makedirs(CHECKPOINT_DIR, exist_ok=True)


# ── 收集上下文 ─────────────────────────────────
def collect_git_info():
    """收集 git 状态"""
    branch = run("git branch --show-current")
    status = run("git status --short")[:800]
    last_commit = run("git log -1 --format=\"%h %s\"")
    return {
        "branch": branch,
        "status": status,
        "last_commit": last_commit,
    }


def collect_memory_state():
    """读取当前 memory 文件列表"""
    memory_dir = os.path.join(PROJECT_DIR, ".claude", "memory")
    if not os.path.isdir(memory_dir):
        return []
    files = []
    for f in sorted(os.listdir(memory_dir)):
        if f.endswith(".md") and f != "MEMORY.md":
            mtime = os.path.getmtime(os.path.join(memory_dir, f))
            files.append({"name": f, "mtime": mtime})
    return files


def collect_recent_activity():
    """从 audit log 提取最近活动"""
    audit_log = os.path.join(
        os.path.expanduser("~"), ".claude", "audit", "audit.jsonl"
    )
    if not os.path.exists(audit_log):
        return []

    activities = []
    try:
        with open(audit_log, "r", encoding="utf-8", errors="ignore") as f:
            # 尾部反向读取最后 200 行，避免全量加载大文件
            f.seek(0, 2)
            file_size = f.tell()
            chunk_size = 8192
            lines = []
            pos = file_size
            while pos > 0 and len(lines) < 200:
                read_size = min(chunk_size, pos)
                pos -= read_size
                f.seek(pos)
                chunk = f.read(read_size)
                chunk_lines = chunk.splitlines(keepends=True)
                lines = chunk_lines + lines
            target_lines = lines[-200:] if len(lines) > 200 else lines

        for line in target_lines:
            try:
                entry = json.loads(line)
                if entry.get("session_id") != SESSION_ID:
                    continue

                event = entry.get("_event", "")
                if event == "UserPromptSubmit":
                    activities.append({
                        "event": "prompt",
                        "text": entry.get("prompt", "")[:200],
                        "time": entry.get("_timestamp", ""),
                    })
                elif event == "Stop":
                    # 上一次 stop 的 assistant 回复
                    ctx = entry.get("context", "")[:300]
                    if ctx:
                        activities.append({
                            "event": "stop",
                            "summary": ctx,
                            "time": entry.get("_timestamp", ""),
                        })
            except json.JSONDecodeError:
                continue
    except Exception:
        pass

    return activities[-10:]  # 最近 10 条


def find_task_files():
    """查找活跃的任务文件"""
    tasks = []
    for root, dirs, files in os.walk(Path(PROJECT_DIR) / ".claude"):
        for f in files:
            if f.endswith(".json") and "task" in f.lower():
                tasks.append(os.path.relpath(os.path.join(root, f), PROJECT_DIR))
    return tasks[:10]


# ── 构建检查点 ────────────────────────────────
def build_checkpoint():
    """收集所有上下文并构建检查点"""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    checkpoint = {
        "version": "2.0",
        "timestamp": timestamp,
        "session_id": SESSION_ID,
        "hook_event": HOOK_EVENT,
        "project": PROJECT_DIR,
        "git": collect_git_info(),
        "memory_files": collect_memory_state(),
        "recent_activity": collect_recent_activity(),
        "cwd": os.getcwd(),
        "platform": sys.platform,
    }

    return checkpoint, timestamp


def prune_old_checkpoints():
    """只保留最近 N 个检查点"""
    files = sorted([
        f for f in os.listdir(CHECKPOINT_DIR)
        if f.startswith("checkpoint_") and f.endswith(".json")
    ], reverse=True)

    for old_file in files[MAX_CHECKPOINTS:]:
        p = os.path.join(CHECKPOINT_DIR, old_file)
        try:
            os.remove(p)
        except Exception:
            pass


# ── 写入检查点 ─────────────────────────────────
def write_checkpoint(checkpoint, timestamp):
    """写入检查点文件 + 更新 latest.json"""
    filename = f"checkpoint_{timestamp.replace(':', '-').replace('+', '_')}.json"
    filepath = os.path.join(CHECKPOINT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)

    # 更新 latest.json（用复制而非 symlink，Windows 兼容）
    import shutil
    shutil.copy2(filepath, LATEST_LINK)

    return filepath


# ── 生成恢复指令 ───────────────────────────────
def print_recovery_hint(filepath, checkpoint):
    """输出恢复提示"""
    git_info = checkpoint.get("git", {})
    branch = git_info.get("branch", "N/A")
    activity_count = len(checkpoint.get("recent_activity", []))

    print(f"[CHECKPOINT] 检查点已保存: {os.path.basename(filepath)}")
    print(f"   会话: {SESSION_ID[-8:]}")
    print(f"   分支: {branch}")
    print(f"   最近活动: {activity_count} 条")
    print(f"")
    print(f"[RECOVER] SSH 断开后重连自动恢复")


# ── main ───────────────────────────────────────
if __name__ == "__main__":
    # 兼容 Python 3.6+
    from pathlib import Path

    checkpoint, timestamp = build_checkpoint()
    filepath = write_checkpoint(checkpoint, timestamp)
    prune_old_checkpoints()
    # 仅手动调用时输出（Hook 环境静默，避免 UI 乱码）
    if not os.environ.get("CLAUDE_HOOK_EVENT"):
        print_recovery_hint(filepath, checkpoint)
