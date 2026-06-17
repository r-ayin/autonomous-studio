---
name: phone-notify
description: Claude Code → Termux → Android 系统通知，用 SSH RemoteForward 反向隧道 + termux-notification，零第三方依赖
metadata:
  type: reference
---

# 手机系统通知方案 ✅ 已就绪

## 架构

```
Claude Code Stop/AskUserQ hook
  → notify-phone.py
    → HTTP POST ntfy.sh/x-tool-claude-a7k3m9
      → Android ntfy app → 系统通知栏 🔔
```

## 文件

| 文件 | 用途 |
|------|------|
| `hooks/notify-phone.py` | Hook 脚本，ntfy 优先 → TCP 隧道备选 |
| `.claude/phone-notify.json` | 通知配置（ntfy topic、优先级） |
| `.claude/settings.json` | Hook 注册：Stop + PostToolUse(AskUserQuestion) |

## 触发规则

| 事件 | 优先级 | 震动 | 去抖 |
|------|--------|------|------|
| AskUserQuestion | high | ✅ | 永不去抖 |
| Stop | high | ✅ | 0s（可配） |

## 手机端

- ntfy app → 订阅 `x-tool-claude-a7k3m9`
- 系统设置开通知权限 + 关电池优化
