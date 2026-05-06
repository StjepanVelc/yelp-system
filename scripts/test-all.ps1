param(
    [ValidateSet("quick", "full")]
    [string]$Profile = "full",
    [int]$LoadRounds = 3,
    [int]$LoadConcurrency = 10,
    [string]$GatewayBaseUrl = "http://localhost:8000",
    [switch]$SkipUnit,
    [switch]$SkipCacheLoad,
    [switch]$KeepServicesRunning
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LocalDevScript = Join-Path $RepoRoot "local-dev.ps1"
$PidsFile = Join-Path $RepoRoot ".local-dev-pids.json"

$ResultsRoot = Join-Path $RepoRoot "test-results"
if (!(Test-Path $ResultsRoot)) {
    New-Item -ItemType Directory -Path $ResultsRoot | Out-Null
}
$RunId = Get-Date -Format "yyyyMMdd-HHmmss"
$RunDir = Join-Path $ResultsRoot $RunId
New-Item -ItemType Directory -Path $RunDir | Out-Null

$Results = @()

function Add-StepResult {
    param(
        [string]$Name,
        [string]$Category,
        [string]$Status,
        [double]$DurationSec,
        [int]$ExitCode,
        [string]$LogFile,
        [string]$Summary
    )

    $script:Results += [pscustomobject]@{
        Name        = $Name
        Category    = $Category
        Status      = $Status
        DurationSec = [math]::Round($DurationSec, 2)
        ExitCode    = $ExitCode
        LogFile     = $LogFile
        Summary     = $Summary
        Timestamp   = (Get-Date).ToString("s")
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [string]$Category,
        [string]$Command,
        [string]$WorkDir = $RepoRoot,
        [int]$ExpectedExit = 0
    )

    Write-Host "\n=== $Name ===" -ForegroundColor Cyan
    $safe = ($Name -replace "[^a-zA-Z0-9._-]", "_").ToLowerInvariant()
    $logFile = Join-Path $RunDir "$safe.log"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    Push-Location $WorkDir
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -Command $Command 2>&1 | Out-String
        $exitCode = if ($LASTEXITCODE -is [int]) { $LASTEXITCODE } else { 0 }
    }
    finally {
        Pop-Location
        $sw.Stop()
    }

    $output | Set-Content -Path $logFile

    $status = if ($exitCode -eq $ExpectedExit) { "PASS" } else { "FAIL" }
    $summary = if ($status -eq "PASS") { "ok" } else { "Expected $ExpectedExit, got $exitCode" }

    Add-StepResult -Name $Name -Category $Category -Status $status -DurationSec $sw.Elapsed.TotalSeconds -ExitCode $exitCode -LogFile $logFile -Summary $summary

    if ($status -eq "PASS") {
        Write-Host "PASS  ($([math]::Round($sw.Elapsed.TotalSeconds,2))s)" -ForegroundColor Green
    }
    else {
        Write-Host "FAIL  ($([math]::Round($sw.Elapsed.TotalSeconds,2))s)" -ForegroundColor Red
        Write-Host "See log: $logFile" -ForegroundColor Yellow
    }
}

function Add-Skipped {
    param(
        [string]$Name,
        [string]$Category,
        [string]$Reason
    )

    $safe = ($Name -replace "[^a-zA-Z0-9._-]", "_").ToLowerInvariant()
    $logFile = Join-Path $RunDir "$safe.log"
    "SKIPPED: $Reason" | Set-Content -Path $logFile

    Add-StepResult -Name $Name -Category $Category -Status "SKIPPED" -DurationSec 0 -ExitCode 0 -LogFile $logFile -Summary $Reason
    Write-Host "SKIP  $Name  ($Reason)" -ForegroundColor DarkYellow
}

function Save-Reports {
    $jsonPath = Join-Path $RunDir "summary.json"
    $txtPath = Join-Path $RunDir "summary.txt"

    $summary = [pscustomobject]@{
        run_id       = $RunId
        profile      = $Profile
        gateway_base = $GatewayBaseUrl
        totals       = [pscustomobject]@{
            pass    = ($Results | Where-Object { $_.Status -eq "PASS" }).Count
            fail    = ($Results | Where-Object { $_.Status -eq "FAIL" }).Count
            skipped = ($Results | Where-Object { $_.Status -eq "SKIPPED" }).Count
            total   = $Results.Count
        }
        results      = $Results
    }

    $summary | ConvertTo-Json -Depth 6 | Set-Content -Path $jsonPath

    $lines = @()
    $lines += "Run ID: $RunId"
    $lines += "Profile: $Profile"
    $lines += "GatewayBaseUrl: $GatewayBaseUrl"
    $lines += ""
    $lines += "Name`tCategory`tStatus`tDurationSec`tExitCode`tSummary"
    foreach ($r in $Results) {
        $lines += "$($r.Name)`t$($r.Category)`t$($r.Status)`t$($r.DurationSec)`t$($r.ExitCode)`t$($r.Summary)"
    }
    $lines | Set-Content -Path $txtPath

    Write-Host "\nReports saved:" -ForegroundColor Cyan
    Write-Host "- $txtPath"
    Write-Host "- $jsonPath"
}

$initiallyRunning = Test-Path $PidsFile
$startedByScript = $false

Write-Host "Test run: $RunId" -ForegroundColor Cyan
Write-Host "Profile: $Profile"
Write-Host "Initial local-dev running: $initiallyRunning"
Write-Host "Output dir: $RunDir"

try {
    if (-not $SkipUnit -and $Profile -eq "full") {
        if ($initiallyRunning) {
            Invoke-Step -Name "Stop local-dev (for unit tests)" -Category "orchestration" -Command ".\local-dev.ps1 -Action stop"
        }

        Invoke-Step -Name "Unit tests - business-service" -Category "unit" -WorkDir (Join-Path $RepoRoot "services/business-service") -Command "$env:PYTHONPATH='.'; python -m pytest tests -q"
        Invoke-Step -Name "Unit tests - recommendation-service" -Category "unit" -WorkDir (Join-Path $RepoRoot "services/recommendation-service") -Command "$env:PYTHONPATH='.'; python -m pytest tests -q"
        Invoke-Step -Name "Unit tests - api-gateway" -Category "unit" -WorkDir (Join-Path $RepoRoot "services/api-gateway") -Command "$env:PYTHONPATH='.'; python -m pytest tests -q"
        Invoke-Step -Name "Unit tests - ingestion-service" -Category "unit" -WorkDir (Join-Path $RepoRoot "services/ingestion-service") -Command "$env:PYTHONPATH='.'; python -m pytest tests -q"
    }
    elseif ($SkipUnit) {
        Add-Skipped -Name "Unit tests" -Category "unit" -Reason "Skipped by -SkipUnit"
    }
    else {
        Add-Skipped -Name "Unit tests" -Category "unit" -Reason "Profile=quick"
    }

    if (!(Test-Path $PidsFile)) {
        Invoke-Step -Name "Start local-dev" -Category "orchestration" -Command ".\local-dev.ps1 -Action start"
        if (Test-Path $PidsFile) {
            $startedByScript = $true
        }
    }

    Invoke-Step -Name "HTTP health - gateway" -Category "integration" -Command "`$r = Invoke-WebRequest -UseBasicParsing '$GatewayBaseUrl/health' -TimeoutSec 10; if (`$r.StatusCode -ne 200) { throw 'Expected 200' }; Write-Output `$r.Content"
    Invoke-Step -Name "HTTP health - business" -Category "integration" -Command "`$r = Invoke-WebRequest -UseBasicParsing 'http://localhost:8001/health' -TimeoutSec 10; if (`$r.StatusCode -ne 200) { throw 'Expected 200' }; Write-Output `$r.Content"
    Invoke-Step -Name "HTTP health - recommendation" -Category "integration" -Command "`$r = Invoke-WebRequest -UseBasicParsing 'http://localhost:8002/health' -TimeoutSec 10; if (`$r.StatusCode -ne 200) { throw 'Expected 200' }; Write-Output `$r.Content"

    Invoke-Step -Name "Auth negative - no token returns 401" -Category "security" -Command "try { Invoke-WebRequest -UseBasicParsing '$GatewayBaseUrl/businesses?city=Phoenix' -TimeoutSec 10 | Out-Null; throw 'Expected 401' } catch [System.Net.WebException] { `$code = [int]`$_.Exception.Response.StatusCode; if (`$code -ne 401) { throw ('Expected 401, got ' + `$code) }; Write-Output '401 as expected' }"

    Invoke-Step -Name "Cache stats endpoint - business" -Category "cache" -Command "`$r = Invoke-WebRequest -UseBasicParsing 'http://localhost:8001/cache/stats' -TimeoutSec 10; if (`$r.StatusCode -ne 200) { throw 'Expected 200' }; Write-Output `$r.Content"
    Invoke-Step -Name "Cache stats endpoint - recommendation" -Category "cache" -Command "`$r = Invoke-WebRequest -UseBasicParsing 'http://localhost:8002/cache/stats' -TimeoutSec 10; if (`$r.StatusCode -ne 200) { throw 'Expected 200' }; Write-Output `$r.Content"

    if (-not $SkipCacheLoad) {
        Invoke-Step -Name "Cache load test" -Category "cache" -WorkDir $RepoRoot -Command "python scripts/cache_load_test.py load --rounds $LoadRounds --concurrency $LoadConcurrency"
        Invoke-Step -Name "Cache stats snapshot" -Category "cache" -WorkDir $RepoRoot -Command "python scripts/cache_load_test.py stats"
    }
    else {
        Add-Skipped -Name "Cache load test" -Category "cache" -Reason "Skipped by -SkipCacheLoad"
    }
}
finally {
    if ($startedByScript -and -not $KeepServicesRunning) {
        Invoke-Step -Name "Stop local-dev (cleanup)" -Category "orchestration" -Command ".\local-dev.ps1 -Action stop"
    }

    if ($initiallyRunning -and !(Test-Path $PidsFile)) {
        Invoke-Step -Name "Restore local-dev state" -Category "orchestration" -Command ".\local-dev.ps1 -Action start"
    }

    Save-Reports

    $fails = ($Results | Where-Object { $_.Status -eq "FAIL" }).Count
    $passes = ($Results | Where-Object { $_.Status -eq "PASS" }).Count
    $skips = ($Results | Where-Object { $_.Status -eq "SKIPPED" }).Count

    Write-Host "\nSummary: PASS=$passes  FAIL=$fails  SKIPPED=$skips" -ForegroundColor Cyan
    if ($fails -gt 0) {
        exit 1
    }
}
