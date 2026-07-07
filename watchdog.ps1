# =============================================================================
# Autonomous Studio External Watchdog — Windows Native (L6 外部监控层)
# =============================================================================
# watchdog.sh 的 Windows 移植版。独立于 Claude Code 进程的健康守护。
# 单次执行模式：由任务计划程序 (AutonomousStudioWatchdog) 每 5 分钟调一次，
# 不含内部循环（与 Linux 版 watchdog.sh 的 cron 单次语义一致）。
#
# 部署: 运行 watchdog-boot.ps1 一次即自动注册计划任务。
# =============================================================================

$ErrorActionPreference = "SilentlyContinue"

# ── 项目目录解析: CLAUDE_PROJECT_DIR > 脚本所在目录 ──
$ProjectDir = $env:CLAUDE_PROJECT_DIR
if (-not $ProjectDir) {
    # 脚本部署在 <project>/.claude/watchdog.ps1 或 <dist>/watchdog.ps1
    $scriptParent = Split-Path -Parent $PSScriptRoot
    if ((Split-Path -Leaf $PSScriptRoot) -eq ".claude") { $ProjectDir = $scriptParent }
    else { $ProjectDir = $PSScriptRoot }
}

$ClaudeDir      = Join-Path $ProjectDir ".claude"
$Latest         = Join-Path $ClaudeDir "checkpoints\latest.json"
$HeartbeatFile  = Join-Path $ClaudeDir ".watchdog_heartbeat"
$StaleMarker    = Join-Path $ClaudeDir ".watchdog_stale"
$ResumeFlag     = Join-Path $ClaudeDir ".watchdog_resume_needed"
$LockFile       = Join-Path $ClaudeDir ".watchdog.lock"
$LogFile        = Join-Path $ClaudeDir ".watchdog.log"
$DecisionLog    = Join-Path $ClaudeDir "decision-log.jsonl"

function Write-Log($msg) {
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    "[$ts] $msg" | Out-File -Append -FilePath $LogFile -Encoding UTF8
}

if (-not (Test-Path $ClaudeDir)) { exit 0 }  # 非引擎项目守卫

# ── 0. 实例锁（防重叠：独占打开 lock 文件，失败即有实例在跑）──
try {
    $lockStream = [System.IO.File]::Open($LockFile, 'OpenOrCreate', 'ReadWrite', 'None')
} catch {
    exit 0
}

try {
    # ── 1. 心跳 ──
    (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") |
        Out-File -FilePath $HeartbeatFile -Encoding ASCII -NoNewline

    # ── 2. 检查点新鲜度 (>900s → stale) ──
    $age = 0
    if (Test-Path $Latest) {
        $age = [int]((Get-Date) - (Get-Item $Latest).LastWriteTime).TotalSeconds
        if ($age -gt 900) {
            New-Item -ItemType File -Path $StaleMarker -Force | Out-Null
            Write-Log "STALE: checkpoint age ${age}s (>900s)"
        } else {
            Remove-Item $StaleMarker -Force -ErrorAction SilentlyContinue
        }
    }

    # ── 3. Claude 进程检查 ──
    # 优先命令行锚定本项目目录；Windows 下 claude.exe 命令行常不含路径，
    # 匹配不到时回退为全局 claude 进程计数（单用户机可接受）。
    $projPattern = [regex]::Escape($ProjectDir)
    $allClaude = @(Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -match "^claude") -or ($_.CommandLine -match "claude") })
    $anchored = @($allClaude | Where-Object { $_.CommandLine -match $projPattern }).Count
    $claudeProcs = if ($anchored -gt 0) { $anchored } else { @($allClaude | Where-Object { $_.Name -match "^claude" }).Count }
    if ($claudeProcs -eq 0) {
        New-Item -ItemType File -Path $ResumeFlag -Force | Out-Null
        Write-Log "ALERT: No Claude processes running in $ProjectDir"
    } else {
        Remove-Item $ResumeFlag -Force -ErrorAction SilentlyContinue
    }

    # ── 4. decision-log 健康记录 ──
    if (Test-Path $DecisionLog) {
        $lines = (Get-Content $DecisionLog | Measure-Object -Line).Lines
        Write-Log "HEALTH: decision-log $lines lines, checkpoint age ${age}s, claude procs $claudeProcs"
    } else {
        Write-Log "HEALTH: decision-log missing, claude procs $claudeProcs"
    }

    # ── 5. 日志截断（>200 行保留最近 100 行）──
    if (Test-Path $LogFile) {
        $logLines = Get-Content $LogFile
        if ($logLines.Count -gt 200) {
            $logLines | Select-Object -Last 100 | Set-Content $LogFile -Encoding UTF8
        }
    }
} finally {
    $lockStream.Close()
}
