# studio-precheck.ps1 -- Windows native precheck (no bash /dev/null dependency)
# Usage: powershell -NoProfile -File .claude/scripts/studio-precheck.ps1 .
# Or:    Get-Content .claude/scripts/studio-precheck.ps1 -Raw | powershell -NoProfile -Command -
param([string]$ProjDir = ".")

$StatusFile = Join-Path $ProjDir "planning/status.json"
$CalFile    = Join-Path $ProjDir ".claude/decisions/calibration.json"
$StateFile  = Join-Path $ProjDir ".claude/memory/autonomous-state.md"
$PromptFile = Join-Path $HOME ".claude/skills/autonomous-studio/decision-agent-prompt.md"

# 1. prompt file exists?
if (-not (Test-Path $PromptFile)) {
    Write-Output "skip:no-prompt-file"
    exit 0
}

# 2. cooldown check
if (Test-Path $CalFile) {
    $ErrorActionPreference = "SilentlyContinue"
    $cal = Get-Content $CalFile -Raw | ConvertFrom-Json
    $cnd = $cal.cooldown.current_consecutive
    $ErrorActionPreference = "Continue"
    if ($cnd -ge 3) {
        Write-Output "skip:cooldown"
        exit 0
    }
}

# 3. goal status
if (Test-Path $StateFile) {
    $content = Get-Content $StateFile -Raw
    if ($content -match "GOAL_STATUS:\s*paused") {
        Write-Output "skip:paused"
        exit 0
    }
}

# 4. autoAdvance / Studio state
if (Test-Path $StatusFile) {
    $ErrorActionPreference = "SilentlyContinue"
    $status = Get-Content $StatusFile -Raw | ConvertFrom-Json
    $ErrorActionPreference = "Continue"
    if ($status -and $status.autoAdvance -eq $false) {
        Write-Output "skip:auto-advance-off"
        exit 0
    }
}

Write-Output "proceed"