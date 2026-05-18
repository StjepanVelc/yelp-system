param(
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$ObservabilityScript = Join-Path $RepoRoot "scripts\observability-local.ps1"
$LocalDevScript = Join-Path $RepoRoot "local-dev.ps1"
$LocalDevPidsFile = Join-Path $RepoRoot ".local-dev-pids.json"
$StateFile = Join-Path $RepoRoot ".dev-full-state.json"
$RootComposeFile = Join-Path $RepoRoot "docker-compose.yml"

if (!(Test-Path $ObservabilityScript)) {
    throw "Missing observability script: $ObservabilityScript"
}

if (!(Test-Path $LocalDevScript)) {
    throw "Missing local dev script: $LocalDevScript"
}

function Invoke-DevScript {
    param(
        [string]$ScriptPath,
        [string[]]$Arguments
    )

    $argumentList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $ScriptPath)
    if ($Arguments) {
        $argumentList += $Arguments
    }

    $process = Start-Process -FilePath "powershell" -ArgumentList $argumentList -WorkingDirectory $RepoRoot -NoNewWindow -Wait -PassThru

    return [int]$process.ExitCode
}

function Stop-RootComposeIfPresent {
    if (!(Test-Path $RootComposeFile)) {
        return
    }

    Write-Host "Stopping root Docker app services to free local ports..." -ForegroundColor Yellow
    & docker compose -f $RootComposeFile stop nginx frontend api-gateway business-service recommendation-service ingestion-service
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: docker compose stop returned exit code $LASTEXITCODE." -ForegroundColor Yellow
    }
}

function Ensure-RootInfraIfPresent {
    if (!(Test-Path $RootComposeFile)) {
        return
    }

    Write-Host "Ensuring shared infrastructure services are running (db, redis)..." -ForegroundColor Yellow
    & docker compose -f $RootComposeFile up -d db redis
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: docker compose up db redis returned exit code $LASTEXITCODE." -ForegroundColor Yellow
    }
}

function Set-LocalTracingEnvironment {
    [Environment]::SetEnvironmentVariable("OTEL_TRACES_ENABLED", "true", "Process")
    [Environment]::SetEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317", "Process")
    [Environment]::SetEnvironmentVariable("OTEL_EXPORTER_OTLP_INSECURE", "true", "Process")
}

function Test-UrlReady {
    param(
        [string]$Url,
        [int]$TimeoutSec = 3
    )

    try {
        $null = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec $TimeoutSec
        return $true
    }
    catch {
        return $false
    }
}

function Wait-ForUrls {
    param(
        [string[]]$Urls,
        [int]$TimeoutSec = 60,
        [string]$Label = "services"
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $ready = $true
        foreach ($url in $Urls) {
            if (!(Test-UrlReady -Url $url)) {
                $ready = $false
                break
            }
        }

        if ($ready) {
            return $true
        }

        Start-Sleep -Seconds 1
    }

    Write-Host "Timed out waiting for $Label to become ready." -ForegroundColor Yellow
    return $false
}

function Read-LocalDevPids {
    if (!(Test-Path $LocalDevPidsFile)) {
        return @()
    }

    $raw = Get-Content $LocalDevPidsFile -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return @()
    }

    $data = ConvertFrom-Json $raw
    if ($data -is [System.Array]) {
        return @($data)
    }

    return @($data)
}

function Test-ProcessAlive {
    param([int]$ProcessId)

    return [bool](Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Get-LocalDevState {
    $tracked = Read-LocalDevPids
    if ($tracked.Count -eq 0) {
        return [pscustomobject]@{
            running = $false
            stale   = $false
            tracked = @()
            alive   = @()
        }
    }

    $alive = @($tracked | Where-Object { $_.pid -and (Test-ProcessAlive -ProcessId ([int]$_.pid)) })
    $running = $alive.Count -gt 0
    $stale = $alive.Count -ne $tracked.Count

    return [pscustomobject]@{
        running = $running
        stale   = $stale
        tracked = $tracked
        alive   = $alive
    }
}

function Test-ObservabilityState {
    $prometheusReady = Test-UrlReady -Url "http://localhost:9090/-/ready"
    $jaegerReady = Test-UrlReady -Url "http://localhost:16686"
    $grafanaReady = Test-UrlReady -Url "http://localhost:3001"

    return [pscustomobject]@{
        running    = ($prometheusReady -and $jaegerReady -and $grafanaReady)
        prometheus = $prometheusReady
        jaeger     = $jaegerReady
        grafana    = $grafanaReady
    }
}

function Save-State {
    param(
        [bool]$ObservabilityStartedByScript,
        [bool]$LocalDevStartedByScript
    )

    $state = [pscustomobject]@{
        started_at            = (Get-Date).ToString("s")
        observability_started = $ObservabilityStartedByScript
        local_dev_started     = $LocalDevStartedByScript
        otel_endpoint         = "http://localhost:4317"
    }

    $state | ConvertTo-Json | Set-Content -Path $StateFile
}

function Read-State {
    if (!(Test-Path $StateFile)) {
        return $null
    }

    $raw = Get-Content $StateFile -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return $null
    }

    return $raw | ConvertFrom-Json
}

function Stop-StaleLocalDevIfNeeded {
    $state = Get-LocalDevState
    if ($state.tracked.Count -eq 0) {
        return
    }

    if ($state.running) {
        Write-Host "Stopping existing local-dev stack before start..." -ForegroundColor Yellow
        $exitCode = Invoke-DevScript -ScriptPath $LocalDevScript -Arguments @("-Action", "stop")
        if ($exitCode -ne 0) {
            Write-Host "Warning: local-dev stop returned exit code $exitCode." -ForegroundColor Yellow
        }
        return
    }

    if (Test-Path $LocalDevPidsFile) {
        Write-Host "Removing stale local-dev PID file." -ForegroundColor Yellow
        Remove-Item $LocalDevPidsFile -Force
    }
}

function Remove-State {
    if (Test-Path $StateFile) {
        Remove-Item $StateFile -Force
    }
}

function Start-ObservabilityIfNeeded {
    $state = Test-ObservabilityState
    if ($state.running) {
        Write-Host "Observability stack already running." -ForegroundColor DarkGreen
        return $false
    }

    $exitCode = Invoke-DevScript -ScriptPath $ObservabilityScript -Arguments @("-Action", "start")
    if ($exitCode -ne 0) {
        throw "Failed to start observability stack (exit code $exitCode)."
    }

    if (!(Wait-ForUrls -Urls @(
                "http://localhost:9090/-/ready",
                "http://localhost:16686",
                "http://localhost:3001"
            ) -TimeoutSec 60 -Label "observability stack")) {
        throw "Observability stack did not become ready in time."
    }

    return $true
}

function Stop-ObservabilityIfStarted {
    param([bool]$StartedByScript)

    if (!$StartedByScript) {
        return
    }

    $exitCode = Invoke-DevScript -ScriptPath $ObservabilityScript -Arguments @("-Action", "stop")
    if ($exitCode -ne 0) {
        Write-Host "Warning: observability stop returned exit code $exitCode." -ForegroundColor Yellow
    }
}

function Start-LocalDevIfNeeded {
    $state = Get-LocalDevState
    if ($state.running) {
        if ($state.stale) {
            Write-Host "Local stack is already running, but the PID file is stale." -ForegroundColor Yellow
        }
        else {
            Write-Host "Local stack already running." -ForegroundColor DarkGreen
        }

        return $false
    }

    if ($state.stale -and (Test-Path $LocalDevPidsFile)) {
        Write-Host "Removing stale local-dev PID file." -ForegroundColor Yellow
        Remove-Item $LocalDevPidsFile -Force
    }

    $exitCode = Invoke-DevScript -ScriptPath $LocalDevScript -Arguments @("-Action", "start")
    if ($exitCode -ne 0) {
        throw "Failed to start local stack (exit code $exitCode)."
    }

    if (!(Wait-ForUrls -Urls @(
                "http://localhost:8000/health",
                "http://localhost:8001/health",
                "http://localhost:8002/health",
                "http://localhost:8003/health",
                "http://localhost:3000"
            ) -TimeoutSec 90 -Label "local stack")) {
        throw "Local stack did not become ready in time."
    }

    return $true
}

function Stop-LocalDevIfStarted {
    param([bool]$StartedByScript)

    if (!$StartedByScript) {
        return
    }

    $exitCode = Invoke-DevScript -ScriptPath $LocalDevScript -Arguments @("-Action", "stop")
    if ($exitCode -ne 0) {
        Write-Host "Warning: local-dev stop returned exit code $exitCode." -ForegroundColor Yellow
    }
}

function Write-CurrentStatus {
    $obs = Test-ObservabilityState
    $local = Get-LocalDevState
    $saved = Read-State

    Write-Host "Dev-full status" -ForegroundColor Cyan
    Write-Host "Observability: $($obs.running)" 
    Write-Host "Local stack:   $($local.running)"
    if ($null -ne $saved) {
        Write-Host "Tracked since: $($saved.started_at)"
        Write-Host "Started by this script: observability=$($saved.observability_started) local=$($saved.local_dev_started)"
    }

    Write-Host ""
    Write-Host "URLs:" -ForegroundColor Cyan
    Write-Host "- Frontend:      http://localhost:3000"
    Write-Host "- API Gateway:   http://localhost:8000"
    Write-Host "- Business:      http://localhost:8001"
    Write-Host "- Recommendation: http://localhost:8002"
    Write-Host "- Ingestion:     http://localhost:8003"
    Write-Host "- Prometheus:    http://localhost:9090"
    Write-Host "- Jaeger:        http://localhost:16686"
    Write-Host "- Grafana:       http://localhost:3001"
}

switch ($Action) {
    "start" {
        Set-LocalTracingEnvironment

        $observabilityStarted = $false
        $localDevStarted = $false

        try {
            Stop-StaleLocalDevIfNeeded
            Stop-RootComposeIfPresent
            Ensure-RootInfraIfPresent
            $observabilityStarted = Start-ObservabilityIfNeeded
            $localDevStarted = Start-LocalDevIfNeeded
            Save-State -ObservabilityStartedByScript $observabilityStarted -LocalDevStartedByScript $localDevStarted

            Write-Host "Dev-full stack is ready." -ForegroundColor Green
            Write-CurrentStatus
        }
        catch {
            if ($localDevStarted) {
                Stop-LocalDevIfStarted -StartedByScript $true
            }

            if ($observabilityStarted) {
                Stop-ObservabilityIfStarted -StartedByScript $true
            }

            Remove-State
            throw
        }
    }

    "stop" {
        $state = Read-State
        if ($null -eq $state) {
            Write-Host "No dev-full state file found. Nothing to stop." -ForegroundColor Yellow
            exit 0
        }

        Stop-LocalDevIfStarted -StartedByScript ([bool]$state.local_dev_started)
        Stop-ObservabilityIfStarted -StartedByScript ([bool]$state.observability_started)
        Remove-State

        Write-Host "Dev-full stack stopped." -ForegroundColor Green
    }

    "status" {
        Write-CurrentStatus
    }

    "restart" {
        & powershell -ExecutionPolicy Bypass -File $MyInvocation.MyCommand.Path -Action stop
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        & powershell -ExecutionPolicy Bypass -File $MyInvocation.MyCommand.Path -Action start
    }
}