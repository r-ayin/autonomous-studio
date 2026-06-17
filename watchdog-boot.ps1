# watchdog-boot.ps1 — L6 外部监控开机自启脚本
# =============================================================================
# 功能:
#   1. Windows 登录时自动启动 WSL (如果未运行)
#   2. 确保 WSL cron 服务处于 active 状态
#   3. 验证 watchdog crontab 条目存在
#   4. 缺失 → 自动安装
#
# 部署 (管理员 PowerShell 执行一次):
#   $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -File E:\x-tool\.claude\watchdog-boot.ps1"
#   $trigger = New-ScheduledTaskTrigger -AtLogon
#   $principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -RunLevel Highest
#   $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
#   Register-ScheduledTask -TaskName "x-tool-watchdog-boot" -Action $action -Trigger $trigger -Principal $principal -Settings $settings
# =============================================================================

$LogFile = "E:\x-tool\.claude\.watchdog_boot.log"
$WatchdogScript = "/mnt/e/x-tool/.claude/watchdog.sh"
$CronPattern = "*/5 * * * * /mnt/e/x-tool/.claude/watchdog.sh"

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    "$ts | $msg" | Out-File -Append -FilePath $LogFile -Encoding UTF8
}

Write-Log "=== Watchdog Boot 启动 ==="

# ── 1. 确保 WSL 在运行 ───────────────────────────
try {
    $wslRunning = wsl -d Ubuntu -- bash -c "echo OK" 2>&1
    if ($wslRunning -match "OK") {
        Write-Log "WSL Ubuntu 已运行"
    } else {
        Write-Log "WSL 未响应: $wslRunning"
    }
} catch {
    Write-Log "WSL 检查失败: $_"
}

# ── 2. 确保 cron 服务运行 ────────────────────────
try {
    $cronStatus = wsl -d Ubuntu -- bash -c "service cron status 2>&1 || echo 'NOT_RUNNING'"
    if ($cronStatus -match "is running|active") {
        Write-Log "cron 服务已运行"
    } else {
        Write-Log "cron 未运行，尝试启动..."
        $startResult = wsl -d Ubuntu -u root -- bash -c "service cron start 2>&1"
        Write-Log "启动结果: $startResult"
    }
} catch {
    Write-Log "cron 检查失败: $_"
}

# ── 3. 验证 watchdog crontab 存在 ─────────────────
try {
    $cronEntries = wsl -d Ubuntu -- bash -c "crontab -l 2>&1"
    if ($cronEntries -match "watchdog\.sh") {
        Write-Log "watchdog crontab 已注册"
    } else {
        Write-Log "watchdog crontab 缺失，重新安装..."
        $installResult = wsl -d Ubuntu -- bash -c "(crontab -l 2>/dev/null; echo '$CronPattern >> /tmp/x-tool-watchdog.log 2>&1') | crontab - && echo 'INSTALLED'"
        Write-Log "安装结果: $installResult"
    }
} catch {
    Write-Log "crontab 验证失败: $_"
}

# ── 4. 确保 watchdog.sh 可执行 ────────────────────
try {
    wsl -d Ubuntu -- bash -c "chmod +x $WatchdogScript 2>&1"
    Write-Log "watchdog.sh 权限已确认"
} catch {
    Write-Log "chmod 失败: $_"
}

Write-Log "=== Watchdog Boot 完成 ==="
