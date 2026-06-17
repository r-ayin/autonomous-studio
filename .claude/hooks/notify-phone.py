#!/usr/bin/env python3
"""
Claude Code → Termux → Android 系统通知

原理:
  Termux 端运行 termux-listener.py 监听 127.0.0.1:9999
  SSH 连接时加 RemoteForward 9999 localhost:9999
  本脚本通过 TCP 隧道发消息 → Termux → termux-notification

触发:
  Stop hook        → 低优先级静默通知（执行完毕）
  AskUserQuestion  → 高优先级+震动（需要确认）

零第三方依赖，只用 Termux 自带能力。
"""

import os
import sys
import json
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

# ── Windows GBK 兼容 ─────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── 环境变量 ────────────────────────────────────
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
HOOK_EVENT = os.environ.get("CLAUDE_HOOK_EVENT", "")
TOOL_NAME = os.environ.get("CLAUDE_TOOL_NAME", "")

CONFIG_PATH = os.path.join(PROJECT_DIR, ".claude", "phone-notify.json")
DEBOUNCE_FILE = os.path.join(PROJECT_DIR, ".claude", ".last_phone_notify")


# ── 配置 ────────────────────────────────────────
def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[NOTIFY] 配置读取失败: {e}", file=sys.stderr)
        return {}


# ── 后端 1: TCP 隧道 → Termux ────────────────────
def notify_via_tunnel(priority: str, title: str, message: str, config: dict) -> bool:
    """通过 SSH 反向隧道发 TCP 消息给 Termux

    Termux 端 termux-listener.py 收到后调用 termux-notification。
    """
    tunnel_cfg = config.get("tunnel", {})
    host = tunnel_cfg.get("host", "127.0.0.1")
    port = tunnel_cfg.get("port", 9999)
    timeout = tunnel_cfg.get("timeout", 2)

    # 协议: PRIORITY|TITLE|MESSAGE
    payload = f"{priority}|{title}|{message}"

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.sendall(payload.encode("utf-8"))
        return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False
    finally:
        sock.close()


# ── 后端 2: ntfy.sh ──────────────────────────────
def notify_via_ntfy(priority: str, title: str, message: str, config: dict) -> bool:
    """通过 ntfy.sh 发 Android 通知（备选方案）"""
    ntfy_cfg = config.get("ntfy", {})
    server = ntfy_cfg.get("server", "https://ntfy.sh")
    topic = ntfy_cfg.get("topic", "")

    if not topic:
        return False

    url = f"{server}/{topic}"

    # ntfy priority: min=1, low=2, default=3, high=4, max=5
    ntfy_prio = {"min": "1", "low": "2", "default": "3", "high": "4", "max": "5"}

    curl_cmd = [
        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
        "-d", message,
        "-H", f"Title: {title}",
        "-H", f"Priority: {ntfy_prio.get(priority, '3')}",
        "-H", "Tags: robot",
        url,
    ]

    try:
        result = subprocess.run(curl_cmd, capture_output=True, timeout=10, text=True, encoding="utf-8")
        return result.stdout.strip() == "200"
    except Exception:
        return False


# ── 去抖 ────────────────────────────────────────
def check_debounce(reason: str, config: dict) -> bool:
    """返回 True = 应跳过通知

    confirm（需要确认）→ 永不去抖
    stop（执行完毕）→ 按配置的去抖间隔
    """
    if reason == "confirm":
        return False

    prefs = config.get("preferences", {})
    debounce_sec = prefs.get("stop_debounce_seconds", 0)

    if debounce_sec <= 0:
        return False

    try:
        if os.path.exists(DEBOUNCE_FILE):
            with open(DEBOUNCE_FILE, "r") as f:
                last_ts = float(f.read().strip())
            if time.time() - last_ts < debounce_sec:
                return True
    except (ValueError, OSError):
        pass

    return False


def save_debounce_ts():
    try:
        with open(DEBOUNCE_FILE, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass


# ── 主逻辑 ──────────────────────────────────────
def determine_reason_and_priority(config: dict) -> tuple:
    """返回 (reason, priority)"""
    prefs = config.get("preferences", {})

    if HOOK_EVENT == "PostToolUse" and TOOL_NAME == "AskUserQuestion":
        return ("confirm", "high")

    if HOOK_EVENT == "Stop":
        stop_prio = prefs.get("stop_priority", "min")
        return ("stop", stop_prio)

    return ("unknown", "default")


def send(title: str, message: str, reason: str, priority: str) -> bool:
    """尝试所有后端，任意成功即返回 True"""
    config = load_config()

    if not config.get("enabled", True):
        return False

    if check_debounce(reason, config):
        print(f"[NOTIFY] 去抖跳过 ({reason})", file=sys.stderr)
        return False

    # 1. 首选 TCP 隧道（本地，零第三方依赖）
    if notify_via_tunnel(priority, title, message, config):
        save_debounce_ts()
        return True

    # 2. 备选 ntfy.sh
    if notify_via_ntfy(priority, title, message, config):
        save_debounce_ts()
        return True

    # 3. 兜底：输出到 stderr（避免 UI 乱码，仅调试用）
    if os.environ.get("NOTIFY_DEBUG"):
        print(f"\n🔔 [{title}] {message}", file=sys.stderr)
    return False


def main():
    config = load_config()
    reason, priority = determine_reason_and_priority(config)

    now = datetime.now().strftime("%H:%M")

    if reason == "confirm":
        title = "⚠️ Claude 需要你的确认"
        message = f"Claude Code 正在等待你的回复，回 Termux 查看。"
    elif reason == "stop":
        title = f"Claude 已回复 ({now})"
        message = "回到 Termux 继续对话。"
    else:
        title = "Claude Code"
        message = "有新的回复。"

    send(title, message, reason, priority)


if __name__ == "__main__":
    main()
