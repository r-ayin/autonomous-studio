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
from datetime import datetime

PORT = 9999
HOST = "127.0.0.1"


def send_notification(priority: str, title: str, message: str):
    """调用 termux-notification 弹出 Android 系统通知"""
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
        subprocess.run(cmd, timeout=5, capture_output=True)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 通知失败: {e}", file=sys.stderr)


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
