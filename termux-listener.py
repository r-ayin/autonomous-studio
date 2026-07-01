#!/usr/bin/env python3
"""
Termux 端通知监听器 — 接收 Windows Claude Code 的通知并弹出 Android 系统通知

用法（在 Termux 中运行）:
  python3 termux-listener.py

前置条件:
  pkg install termux-api python

原理:
  1. 本脚本监听 127.0.0.1:9999
  2. SSH 连接时 RemoteForward 9999 到 Windows 的 9999
  3. Windows hook 脚本通过隧道发 TCP 消息
  4. 本脚本收到后调用 termux-notification 弹出 Android 通知

SSH 配置（一次性）:
  ~/.ssh/config 中加:
    Host windows-machine
        RemoteForward 9999 localhost:9999

  或者在命令行:
    ssh -R 9999:localhost:9999 user@host
"""

import socket
import subprocess
import sys
import os
import re
import json
import secrets
from datetime import datetime, timezone

PORT = 9999
HOST = "127.0.0.1"
MAX_MESSAGE_LEN = 500
VALID_PRIORITIES = {"default", "high", "low", "min", "max"}
AUDIT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".audit")


def _audit_log(action: str, resource: dict, result: str, details: dict | None = None):
    """Append one JSONL entry to .audit/audit-YYYY-MM-DD.jsonl per audit-log.schema.json.
    Best-effort: never raises into caller path; notification delivery must not fail due to logging."""
    try:
        os.makedirs(AUDIT_DIR, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = os.path.join(AUDIT_DIR, f"audit-{day}.jsonl")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rand6 = secrets.token_hex(3)
        event_id = f"audit-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{rand6}"
        entry = {
            "id": event_id,
            "timestamp": ts,
            "userId": "autonomous-engine",
            "userRole": "engine",
            "action": action,
            "resource": resource,
            "result": result,
            "ip": "local",
        }
        if details:
            entry["details"] = details
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[!] audit-log write failed (non-fatal): {e}", file=sys.stderr)


def _sanitize(text: str, max_len: int = MAX_MESSAGE_LEN) -> str:
    """剥离控制字符（含换行/null）并截断，防止 termux-notification 解析注入或 UTF-8 半截"""
    # 移除 \x00-\x1f（含 \n\r\t）和 \x7f；保留空格
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    # 合并连续空白
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1] + "…"
    return cleaned


def send_notification(priority: str, title: str, message: str):
    """调用 termux-notification 弹出 Android 系统通知"""
    # priority 白名单校验（H-001）
    if priority not in VALID_PRIORITIES:
        print(f"[!] invalid priority '{priority}' — falling back to default", file=sys.stderr)
        priority = "default"

    cmd = [
        "termux-notification",
        "--title", title,
        "--content", message,
        "--priority", priority,
    ]

    # 高优先级加震动
    if priority == "high":
        cmd.extend(["--vibrate", "300,100,300"])

    try:
        result = subprocess.run(cmd, timeout=5, capture_output=True)
        if result.returncode != 0:
            stderr_snippet = (result.stderr or b"").decode("utf-8", errors="replace")[:200]
            print(f"[!] termux-notification exited {result.returncode}: {stderr_snippet}", file=sys.stderr)
            _audit_log(
                "notify",
                {"type": "notification", "identifier": title},
                "failure",
                {"priority": priority, "exit_code": result.returncode, "stderr": stderr_snippet},
            )
            return False
        _audit_log(
            "notify",
            {"type": "notification", "identifier": title},
            "success",
            {"priority": priority},
        )
        return True
    except subprocess.TimeoutExpired:
        print("[!] termux-notification timed out after 5s", file=sys.stderr)
        _audit_log(
            "notify",
            {"type": "notification", "identifier": title},
            "failure",
            {"priority": priority, "reason": "timeout_5s"},
        )
        return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 通知失败: {e}", file=sys.stderr)
        _audit_log(
            "notify",
            {"type": "notification", "identifier": title},
            "failure",
            {"priority": priority, "reason": str(e)[:200]},
        )
        return False


def main():
    # 检查 termux-notification 是否可用
    if not os.path.exists("/data/data/com.termux/files/usr/bin/termux-notification"):
        print("❌ termux-notification 未安装！")
        print("   运行: pkg install termux-api")
        sys.exit(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind((HOST, PORT))
        sock.listen(5)
        print(f"✅ Claude 通知监听器已启动: {HOST}:{PORT}")
        print(f"   等待 Windows 端连接...")
        print(f"   (按 Ctrl+C 停止)")
    except OSError as e:
        print(f"❌ 端口 {PORT} 被占用: {e}")
        print(f"   试试: kill $(lsof -t -i:{PORT})")
        sys.exit(1)

    while True:
        try:
            conn, addr = sock.accept()
            with conn:
                data = conn.recv(1024).decode("utf-8", errors="ignore").strip()

                if not data:
                    continue

                # 协议: PRIORITY|TITLE|MESSAGE
                parts = data.split("|", 2)
                priority = parts[0] if len(parts) > 0 else "default"
                title = parts[1] if len(parts) > 1 else "Claude Code"
                message = parts[2] if len(parts) > 2 else data

                # H-001: sanitize external input before it reaches termux-notification
                title = _sanitize(title, max_len=100)
                message = _sanitize(message, max_len=MAX_MESSAGE_LEN)
                if not title:
                    title = "Claude Code"
                if not message:
                    continue

                now = datetime.now().strftime("%H:%M:%S")
                print(f"[{now}] {priority} | {title} | {message}")

                send_notification(priority, title, message)

        except (socket.timeout, ConnectionResetError):
            continue
        except KeyboardInterrupt:
            print("\n👋 监听器已停止")
            break
        except Exception as e:
            print(f"[!] 错误: {e}", file=sys.stderr)
            continue

    sock.close()


if __name__ == "__main__":
    main()
