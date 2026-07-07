# =============================================================================
# watchdog-boot.ps1 — L6 外部监控注册/自修复脚本 (Windows 原生版 v6.2)
# =============================================================================
# 功能:
#   1. 检查任务计划程序中 AutonomousStudioWatchdog 任务是否存在
#   2. 缺失 → 自动注册（每 5 分钟运行 watchdog.ps1，登录时启动）
#   3. 存在 → 确认处于就绪状态，必要时启用
#
# 与旧版差异: 不再依赖 WSL / cron（v6.2 纯 Windows 原生化）。
# Linux / ECS 环境请继续用 watchdog.sh + 系统 cron。
#
# 部署（普通 PowerShell 执行一次即可，幂等）:
#   powershell -NoProfile -ExecutionPolicy Bypass -File watchdog-boot.ps1
# =============================================================================

$ErrorActionPreference = "SilentlyContinue"
$TaskName = "AutonomousStudioWatchdog"

# ── 项目目录解析: CLAUDE_PROJECT_DIR > 脚本所在目录推断 > E:\x-tool 回退 ──
$BasePath = $env:CLAUDE_PROJECT_DIR
if (-not $BasePath) {
    if ((Split-Path -Leaf $PSScriptRoot) -eq ".claude") {
        $BasePath = Split-Path -Parent $PSScriptRoot
    } elseif (Test-Path (Join-Path $PSScriptRoot ".claude")) {
        $BasePath = $PSScriptRoot
    } else {
        $BasePath = "E:\x-tool"
        Write-Warning "[boot] CLAUDE_PROJECT_DIR 未设置且无法从脚本位置推断; 回退 $BasePath"
    }
}

$WatchdogScript = Join-Path $PSScriptRoot "watchdog.ps1"
$LogFile = Join-Path $BasePath ".claude\.watchdog_boot.log"

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    "$ts | $msg" | Out-File -Append -FilePath $LogFile -Encoding UTF8
}

Write-Log "=== Watchdog Boot 启动 (Windows native, base=$BasePath) ==="

if (-not (Test-Path $WatchdogScript)) {
    Write-Log "ERROR: watchdog.ps1 不存在于 $PSScriptRoot"
    exit 1
}

# ── 检查/注册计划任务 ──
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    if ($existing.State -eq "Disabled") {
        Enable-ScheduledTask -TaskName $TaskName | Out-Null
        Write-Log "任务已存在但被禁用 → 已重新启用"
    } else {
        Write-Log "任务已存在 (State=$($existing.State))，跳过注册"
    }
} else {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$WatchdogScript`"" `
        -WorkingDirectory $BasePath
    # Once 触发 + 每 5 分钟重复 3650 天（实测可用配方；MaxValue 会超 XML Duration 范围）
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes 5) `
        -RepetitionDuration (New-TimeSpan -Days 3650)
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Description "Autonomous Studio L6 watchdog (每5分钟健康检查)" | Out-Null
    Write-Log "已注册计划任务 $TaskName (每 5 分钟)"
    # 立即跑一次
    Start-ScheduledTask -TaskName $TaskName
    Write-Log "已触发首次运行"
}

Write-Log "=== Watchdog Boot 完成 ==="
