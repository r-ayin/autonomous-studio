#!/usr/bin/env python3
"""
Claude Code → 手机通知（多通道）

支持的通道:
  1. TCP 隧道 → Termux（本地，零第三方依赖）
  2. ntfy.sh（备选推送服务）
  3. 钉钉 Webhook（新增，支持 Markdown/ActionCard）

原理:
  Termux 端运行 termux-listener.py 监听 127.0.0.1:9999
  SSH 连接时加 RemoteForward 9999 localhost:9999
  本脚本通过 TCP 隧道发消息 → Termux → termux-notification

触发:
  Stop hook        → 低优先级静默通知（执行完毕）
  AskUserQuestion  → 高优先级+震动（需要确认）

零第三方依赖（除钉钉通道外），支持分级通知策略。
"""

import os
import sys
import json
import socket
import subprocess
import time
import urllib.request
from datetime import datetime

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
NOTIFICATION_POLICY_PATH = os.path.join(PROJECT_DIR, ".claude", "decisions", "notification-policy.json")


# ── 配置 ────────────────────────────────────────
def load_config():
    """加载 phone-notify.json 配置"""
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[NOTIFY] 配置读取失败: {e}", file=sys.stderr)
        return {}


def load_notification_policy():
    """加载分级通知策略配置"""
    if not os.path.exists(NOTIFICATION_POLICY_PATH):
        return None
    try:
        with open(NOTIFICATION_POLICY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[NOTIFY] 通知策略读取失败: {e}", file=sys.stderr)
        return None


# ── 免打扰时段检查 ────────────────────────────────
def is_do_not_disturb(policy: dict | None) -> bool:
    """检查当前是否在免打扰时段"""
    if not policy:
        return False

    dnd = policy.get("do_not_disturb", {})
    if not dnd.get("enabled", False):
        return False

    # 获取当前时间（根据配置的时区）
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    current_time = current_hour * 60 + current_minute

    for schedule in dnd.get("schedule", []):
        start_parts = schedule["start"].split(":")
        end_parts = schedule["end"].split(":")
        start_time = int(start_parts[0]) * 60 + int(start_parts[1])
        end_time = int(end_parts[0]) * 60 + int(end_parts[1])

        if start_time <= end_time:
            if start_time <= current_time <= end_time:
                return True
        else:
            # 跨午夜的情况（如 23:00 - 07:00）
            if current_time >= start_time or current_time <= end_time:
                return True

    return False


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
        try:
            sock.close()
        except Exception:
            pass


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


# ── 后端 3: 钉钉 Webhook ──────────────────────────
def notify_via_dingtalk(level: str, title: str, message: str, policy: dict | None) -> bool:
    """通过钉钉 Webhook 发送通知（新增通道）

    支持 Markdown 格式消息，根据通知级别决定是否 @所有人。
    """
    if not policy:
        return False

    channel_cfg = policy.get("channel_config", {}).get("dingtalk", {})
    if not channel_cfg.get("enabled", True):
        return False

    webhook = os.environ.get("DINGTALK_WEBHOOK", "")
    if not webhook:
        return False

    # 构建 Markdown 消息体
    event_mapping = policy.get("event_mapping", {})
    # 根据事件类型获取模板（如果有）
    template = None
    for _event_key, event_cfg in event_mapping.items():
        if level.upper() == event_cfg.get("level", "").upper():
            template = event_cfg.get("dingtalk_template")
            break

    if template:
        # 使用模板格式化消息
        # try 守卫：notification-policy.json 的 dingtalk_template 若格式说明符残缺/引用
        # 不存在的字段，str.format 抛 KeyError/IndexError/ValueError——此前未捕获会
        # 一路冒泡崩 send()/main() 致 hook 非零退出、静默丢通知（含 CRITICAL 确认）。
        # 落兜底纯 markdown，保证通知通道不因模板瑕疵而断（case-388 security-review）。
        try:
            md_text = template.format(
                stage=title,
                score="",
                issue=message,
                suggestion="",
                app_name=title,
                build_id="",
                check_items="",
                batch_count="",
                task_name=title,
                failed_cases="",
                error_message=message,
                reason=message,
                count="",
                duration="",
                conflict_files="",
                workers="",
                artifact="",
                test_count="",
                batch_index="",
                total_batches="",
                observation="",
            )
        except (KeyError, IndexError, ValueError):
            md_text = f"# {title}\n\n{message}"
    else:
        md_text = f"# {title}\n\n{message}"

    body = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": md_text,
        },
        "at": {
            "isAtAll": level.upper() == "CRITICAL",
        },
    }

    try:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            webhook,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("errcode") == 0
    except Exception as e:
        print(f"[NOTIFY] 钉钉通知失败: {e}", file=sys.stderr)
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


# ── 通知级别映射 ──────────────────────────────────
def get_notification_level(policy: dict | None) -> str:
    """根据当前 hook 事件确定通知级别"""
    if not policy:
        return "INFO"

    if HOOK_EVENT == "PostToolUse" and TOOL_NAME == "AskUserQuestion":
        return "CRITICAL"

    if HOOK_EVENT == "Stop":
        return "INFO"

    # 默认 INFO
    return "INFO"


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
    """尝试所有后端，任意成功即返回 True

    支持通道:
      1. TCP 隧道（本地，零第三方依赖）
      2. ntfy.sh（备选推送服务）
      3. 钉钉 Webhook（新增，支持 Markdown 格式）
    """
    config = load_config()
    policy = load_notification_policy()

    if not config.get("enabled", True):
        return False

    if check_debounce(reason, config):
        print(f"[NOTIFY] 去抖跳过 ({reason})", file=sys.stderr)
        return False

    # 检查免打扰时段
    if is_do_not_disturb(policy):
        # CRITICAL 级别不受免打扰限制
        level = get_notification_level(policy)
        if level != "CRITICAL":
            print(f"[NOTIFY] 免打扰时段跳过 ({reason})", file=sys.stderr)
            return False

    # 1. 首选 TCP 隧道（本地，零第三方依赖）
    if notify_via_tunnel(priority, title, message, config):
        save_debounce_ts()
        return True

    # 2. 备选 ntfy.sh
    if notify_via_ntfy(priority, title, message, config):
        save_debounce_ts()
        return True

    # 3. 钉钉 Webhook（新增通道，向后兼容）
    level = get_notification_level(policy)
    if policy is not None and notify_via_dingtalk(level, title, message, policy):
        save_debounce_ts()
        return True

    # 4. 兜底：输出到 stderr（避免 UI 乱码，仅调试用）
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
