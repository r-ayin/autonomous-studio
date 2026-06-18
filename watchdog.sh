#!/bin/bash
# =============================================================================
# x-tool External Watchdog (L6 外部监控层)
# =============================================================================
# 运行在 WSL Ubuntu 中，独立于 Claude Code 进程。
# 2026 共识: "Agent 无法抓住自己的生命线"——这是线外的眼睛。
#
# 部署 (WSL Ubuntu 中执行一次):
#   chmod +x /mnt/e/x-tool/.claude/watchdog.sh
#   crontab -e
#   添加: */5 * * * * /mnt/e/x-tool/.claude/watchdog.sh >> /tmp/x-tool-watchdog.log 2>&1
# =============================================================================
set -euo pipefail

PROJECT_DIR="/mnt/e/x-tool"
CHECKPOINT_DIR="$PROJECT_DIR/.claude/checkpoints"
LATEST="$CHECKPOINT_DIR/latest.json"
HEARTBEAT_FILE="$PROJECT_DIR/.claude/.watchdog_heartbeat"
STALE_MARKER="$PROJECT_DIR/.claude/.watchdog_stale"
RESUME_FLAG="$PROJECT_DIR/.claude/.watchdog_resume_needed"
LOCK_FILE="$PROJECT_DIR/.claude/.watchdog.lock"

# ── 0. 实例锁（防止重叠 cron 运行）─────────────────────
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "[$(date -Iseconds)] WATCHDOG: 上一实例仍在运行，跳过"
    exit 0
fi

# ── 1. 健康检查 ────────────────────────────────────────
if [ ! -f "$LATEST" ]; then
    echo "[$(date -Iseconds)] WATCHDOG: checkpoint missing, skipping"
    exit 0
fi

CHECKPOINT_TS=$(python3 -c "
import json
try:
    with open('$LATEST') as f: d = json.load(f)
    ts = d.get('timestamp', '')
    print(ts if ts and ts != 'null' and ts != 'None' else '')
except Exception:
    print('')
" 2>/dev/null)

if [ -z "$CHECKPOINT_TS" ]; then
    echo "[$(date -Iseconds)] WATCHDOG: 无法解析检查点时间戳（文件损坏或缺失）"
    exit 0
fi

NOW_EPOCH=$(date +%s)
CP_EPOCH=$(date -d "$CHECKPOINT_TS" +%s 2>/dev/null || echo 0)
# 防止时间戳解析失败导致误报（epoch=0 会被误判为僵死）
if [ "$CP_EPOCH" -eq 0 ]; then
    echo "[$(date -Iseconds)] WATCHDOG: 无法解析时间戳: $CHECKPOINT_TS"
    exit 0
fi
AGE_SECONDS=$((NOW_EPOCH - CP_EPOCH))
AGE_MINUTES=$((AGE_SECONDS / 60))

# ── 2. 写心跳 ──────────────────────────────────────────
echo "$(date -Iseconds) | checkpoint_age=${AGE_MINUTES}min" > "$HEARTBEAT_FILE"

# ── 3. CC_PROC 始终初始化 ──────────────────────────────
CC_PROC=$(ps aux 2>/dev/null | grep -i "[c]laude" | grep -v watchdog | wc -l || echo 0)

# ── 4. 健康判断 ────────────────────────────────────────
if [ $AGE_MINUTES -gt 15 ]; then
    echo "[$(date -Iseconds)] WARNING: checkpoint ${AGE_MINUTES}min stale"

    if [ "$CC_PROC" -eq 0 ]; then
        echo "[$(date -Iseconds)] CRITICAL: Claude Code process not found"
        echo "session_interrupted_at=$(date -Iseconds)" > "$STALE_MARKER"
        echo "last_checkpoint_age=${AGE_MINUTES}min" >> "$STALE_MARKER"
        echo "recovery_hint=run_resume-checkpoint" >> "$STALE_MARKER"

        echo "watchdog_detected_stale_at=$(date -Iseconds)" > "$RESUME_FLAG"
        echo "last_active_checkpoint=$CHECKPOINT_TS" >> "$RESUME_FLAG"
    else
        echo "[$(date -Iseconds)] WARNING: Process alive but checkpoint not updated"
    fi
else
    # 健康——但不清除僵死标记（留给 SessionStart 读取）
    # 仅在僵死标记存在 >30min 后才清除
    if [ -f "$STALE_MARKER" ]; then
        MARKER_AGE=$(($(date +%s) - $(stat -c %Y "$STALE_MARKER" 2>/dev/null || echo 0)))
        if [ $MARKER_AGE -gt 1800 ]; then
            rm -f "$STALE_MARKER" "$RESUME_FLAG"
        fi
    fi
fi

echo "[$(date -Iseconds)] WATCHDOG: OK (age=${AGE_MINUTES}min, cc_procs=${CC_PROC})"
