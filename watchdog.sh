#!/bin/bash
# =============================================================================
# Autonomous Studio External Watchdog (L6 外部监控层)
# =============================================================================
# 独立于 Claude Code 进程的健康守护。
# 2026 共识: "Agent 无法抓住自己的生命线"——这是线外的眼睛。
#
# 部署方式（按环境选择）:
#   Linux 沙箱:  nohup bash watchdog.sh &
#   WSL Ubuntu:  crontab -e → */5 * * * * /path/to/watchdog.sh >> /tmp/watchdog.log 2>&1
#   Termux:      nohup bash watchdog.sh &
# =============================================================================
set -euo pipefail

# ── 自动检测项目目录（优先环境变量，否则使用脚本所在目录的父目录）──
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
CHECKPOINT_DIR="$PROJECT_DIR/.claude/checkpoints"
LATEST="$CHECKPOINT_DIR/latest.json"
HEARTBEAT_FILE="$PROJECT_DIR/.claude/.watchdog_heartbeat"
STALE_MARKER="$PROJECT_DIR/.claude/.watchdog_stale"
RESUME_FLAG="$PROJECT_DIR/.claude/.watchdog_resume_needed"
LOCK_FILE="$PROJECT_DIR/.claude/.watchdog.lock"
LOG_FILE="$PROJECT_DIR/.claude/.watchdog.log"

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $1" >> "$LOG_FILE"
}

# ── 0. 实例锁（防止重叠运行）─────────────────────
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "[$(date -Iseconds)] WATCHDOG: 上一实例仍在运行，跳过"
    exit 0
fi

log "Watchdog started (PID $$, PROJECT_DIR=$PROJECT_DIR)"

# ── 主循环（沙箱模式用循环代替 cron）─────────────
while true; do
    date -u '+%Y-%m-%dT%H:%M:%SZ' > "$HEARTBEAT_FILE"

    # ── 1. 检查点新鲜度 ──────────────────────────
    AGE=0
    if [ -f "$LATEST" ]; then
        AGE=$(( $(date +%s) - $(stat -c %Y "$LATEST" 2>/dev/null || stat -f %m "$LATEST" 2>/dev/null || echo 0) ))
        if [ $AGE -gt 900 ]; then
            touch "$STALE_MARKER"
            log "STALE: checkpoint age ${AGE}s (>900s)"
        else
            rm -f "$STALE_MARKER"
        fi
    fi

    # ── 2. Claude 进程检查 ────────────────────────
    CLAUDE_PROCS=$(pgrep -c claude 2>/dev/null || echo 0)
    if [ "$CLAUDE_PROCS" -eq 0 ]; then
        touch "$RESUME_FLAG"
        log "ALERT: No Claude processes running"
    else
        rm -f "$RESUME_FLAG"
    fi

    # ── 3. decision-log 增长检查 ──────────────────
    DECISION_LOG="$PROJECT_DIR/.claude/decision-log.jsonl"
    if [ -f "$DECISION_LOG" ]; then
        LINES=$(wc -l < "$DECISION_LOG")
        log "HEALTH: decision-log ${LINES} lines, checkpoint age ${AGE:-unknown}s, claude procs ${CLAUDE_PROCS}"
    else
        log "HEALTH: decision-log missing, claude procs ${CLAUDE_PROCS}"
    fi

    # ── 4. 日志截断（保留最近 200 行）────────────
    # M-001 hardening: cp→tail→mv 三段式避免 tail 读期间并发 append 被 mv 覆盖丢失。
    # flock 已持 fd 200，但显式 cp 到 .bak 让 tail 读稳定快照，消除增量读边界丢行风险。
    if [ -f "$LOG_FILE" ] && [ $(wc -l < "$LOG_FILE") -gt 200 ]; then
        cp "$LOG_FILE" "$LOG_FILE.bak" \
            && tail -100 "$LOG_FILE.bak" > "$LOG_FILE.tmp" \
            && mv "$LOG_FILE.tmp" "$LOG_FILE" \
            && rm -f "$LOG_FILE.bak"
    fi

    sleep 300
done
