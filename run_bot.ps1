param(
    [Parameter(Mandatory=$true)][string]$Webhook,
    [Parameter(Mandatory=$true)][string]$Email,
    [string]$DiscordUser = "",
    [switch]$Head,
    [string]$EdgeDriver = "",
    [int]$DebugPort = 0,
    [switch]$TempProfile,
    [switch]$EmitStatus
)

# Simple Windows runner for the bot (use Task Scheduler or PAD to schedule)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$lockFile = Join-Path $scriptDir "run.lock"
$logFile = Join-Path $scriptDir "run_log.txt"

# Prevent overlapping runs (remove stale lock if older than 30 minutes)
if (Test-Path $lockFile) {
    try {
        $age = (Get-Date) - (Get-Item $lockFile).LastWriteTime
        if ($age.TotalMinutes -lt 30) {
            Write-Output "Another run is in progress (lock file exists and is recent). Exiting." | Tee-Object -FilePath $logFile -Append
            exit 0
        } else {
            Write-Output "Stale lock file found; removing." | Tee-Object -FilePath $logFile -Append
            Remove-Item $lockFile -ErrorAction SilentlyContinue
        }
    } catch { Remove-Item $lockFile -ErrorAction SilentlyContinue }
}
New-Item -Path $lockFile -ItemType File -Force | Out-Null

try {
    # Export environment variables used by Python scripts
    $env:DISCORD_WEBHOOK_URL = $Webhook
    $env:EDGE_PROFILE_EMAIL = $Email
    if ($DiscordUser) { $env:DISCORD_USER_ID = $DiscordUser }
    if ($EdgeDriver) { $env:EDGE_DRIVER = $EdgeDriver }
    if ($DebugPort -ne 0) { $env:DEBUG_PORT = $DebugPort.ToString() }
    if ($Head.IsPresent) { $env:HEAD = "1" }
    if ($TempProfile.IsPresent) { $env:TEMP_PROFILE = "1" }

    # Choose python (venv if available). Check several common venv locations.
    $relCandidates = @(
        "venv\Scripts\python.exe",
        "Scripts\python.exe",
        "Scripts\python3.exe"
    )
    # Use Join-Path on each relative path to avoid passing arrays into Join-Path
    $candidates = $relCandidates | ForEach-Object { Join-Path $scriptDir $_ }
    $candidates += "python"
    $python = $null
    foreach ($p in $candidates) {
        if ($p -eq "python") {
            if (-not $python) { $python = "python" }
            break
        }
        if (Test-Path $p) { $python = $p; break }
    }

    # If we found a venv python, ensure its Scripts dir is on PATH so subprocesses use the venv environment.
    if ($python -and ($python -ne "python")) {
        $venvScripts = Split-Path $python -Parent
        Add-Content -Path $logFile -Value "Using virtualenv python: $python"
        # Prepend to PATH
        $env:PATH = "$venvScripts;$env:PATH"
    } else {
        Add-Content -Path $logFile -Value "Using system python (no venv python detected): python"
    }

    $fetchScript = Join-Path $scriptDir "fetch_srs_config.py"
    $regScript   = Join-Path $scriptDir "test_registration.py"

    # Build fetch args
    $fetchArgs = @("--term", "Spring Semester 2026")
    if ($Head.IsPresent) { $fetchArgs += "--head" }
    if ($EdgeDriver) { $fetchArgs += "--edge-driver"; $fetchArgs += $EdgeDriver }
    if ($DebugPort -ne 0) { $fetchArgs += "--debug-port"; $fetchArgs += $DebugPort.ToString() }
    if ($TempProfile.IsPresent) { $fetchArgs += "--temp-profile" }

    Add-Content -Path $logFile -Value "=========================================="
    Add-Content -Path $logFile -Value " Starting Course Registration Bot (Windows) "
    Add-Content -Path $logFile -Value "=========================================="

    Add-Content -Path $logFile -Value "`n[Step 1] Fetching SRS Configuration..."
    Add-Content -Path $logFile -Value "Running: $python $fetchScript $($fetchArgs -join ' ')"
    $out = & $python $fetchScript $fetchArgs 2>&1
    $out | Out-File -FilePath $logFile -Append -Encoding utf8
    $fetchExit = $LASTEXITCODE

    if ($fetchExit -ne 0) {
        Add-Content -Path $logFile -Value "Fetch step failed with exit code $fetchExit. See $logFile"
        if ($EmitStatus.IsPresent) { Write-Output "STATUS: FAIL fetch $fetchExit" }
        exit $fetchExit
    }

    if (-not (Test-Path (Join-Path $scriptDir "config_dump.txt"))) {
        Add-Content -Path $logFile -Value "Error: config_dump.txt not created. Aborting."
        if ($EmitStatus.IsPresent) { Write-Output "STATUS: FAIL config_missing" }
        exit 2
    }

    Add-Content -Path $logFile -Value "`n[Step 2] Running Registration Script..."
    Add-Content -Path $logFile -Value "Target: CRN 10961, Term 202601"
    $out = & $python $regScript "--crn" "10961" "--term" "202601" "--auto" 2>&1
    $out | Out-File -FilePath $logFile -Append -Encoding utf8
    $regExit = $LASTEXITCODE

    Add-Content -Path $logFile -Value "`nDone. Exit code: $regExit"
    if ($EmitStatus.IsPresent) {
        if ($regExit -eq 0) { Write-Output "STATUS: OK" } else { Write-Output "STATUS: FAIL reg $regExit" }
    }
    exit $regExit
}
finally {
    Remove-Item $lockFile -ErrorAction SilentlyContinue
}