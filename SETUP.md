# autodev-engine 安装指南

预计时间：15-30 分钟

## 前置条件

- Windows 10/11 + WSL2
- Python 3.10+
- Claude Code 最新版
- Git 2.40+ + GitHub CLI

可选: Android + Termux + ntfy.sh app

## 步骤 1：克隆

```bash
git clone https://github.com/r-ayin/autodev-engine.git
cd autodev-engine
```

## 步骤 2：部署

替换 CLAUDE_PROJECT_DIR 为你的工作区路径:

```bash
# Skills
cp -r skills/autonomous-studio "$CLAUDE_PROJECT_DIR/.claude/skills/"
cp -r skills/project-protocol "$CLAUDE_PROJECT_DIR/.claude/skills/"
cp -r skills/ralph-bridge "$CLAUDE_PROJECT_DIR/.claude/skills/"

# Hooks
cp hooks/*.py "$CLAUDE_PROJECT_DIR/hooks/"

# Engine seed data
cp engine/calibration.json "$CLAUDE_PROJECT_DIR/decisions/"
cp engine/decision-patterns.md "$CLAUDE_PROJECT_DIR/memory/"
cp engine/autonomous-state.md "$CLAUDE_PROJECT_DIR/memory/"
cp engine/autonomous-suggestions.md "$CLAUDE_PROJECT_DIR/memory/"
```

## 步骤 3：配置 Hook 绑定

参考 config/settings.json.example，将其中的 hooks 段落合并到 .claude/settings.json。

## 步骤 4：(可选) 手机通知

### ntfy.sh (推荐)
1. 安装 ntfy.sh Android app
2. 订阅唯一 topic
3. 编辑 .claude/phone-notify.json:
```json
{
  "enabled": true,
  "ntfy": { "server": "https://ntfy.sh", "topic": "your-topic-name" }
}
```

### Termux TCP 隧道
1. Termux 中运行 tools/termux-listener.py
2. SSH: ssh -R 9999:localhost:9999 user@host
3. 配置 TCP tunnel 指向 127.0.0.1:9999

## 步骤 5：(可选) L6 看门狗

```bash
chmod +x watchdog/watchdog.sh
# 编辑 watchdog.sh 设置 PROJECT_DIR
crontab -e
# 添加: */5 * * * * /path/to/watchdog.sh >> /tmp/autodev-watchdog.log 2>&1
```

Windows 开机自启:
```powershell
powershell -ExecutionPolicy Bypass -File watchdog/watchdog-boot.ps1
```

## 步骤 6：验证

```bash
python hooks/decision-observer.py --help
ls skill/SKILL.md
ls decisions/calibration.json
```

启动 Claude Code -> 观察 SessionStart 输出 -> 说"初始化项目"验证 protocol-check。

## 常见问题

| 问题 | 解决 |
|------|------|
| No module named requests | pip install requests |
| 看门狗不写心跳 | sudo service cron start |
| 通知发送失败 | 检查 ntfy topic / SSH tunnel |
| 引擎未自动激活 | 说"检查心跳"确认 CronCreate |

## 下一步
- ARCHITECTURE.md — 完整架构
- docs/protocol.md — 工作流宪法
- 在 autonomous-state.md 设定目标，说"自主模式"激活引擎
