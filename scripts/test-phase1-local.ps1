param(
    [ValidateSet("auto", "manual")]
    [string]$Mode = "auto",
    [switch]$ObservabilityOnly,
    [string]$GatewayUrl = "http://localhost:8000",
    [string]$BusinessUrl = "http://localhost:8001",
    [string]$RecommendationUrl = "http://localhost:8002",
    [string]$IngestionUrl = "http://localhost:8003",
    [string]$PrometheusUrl = "http://localhost:9090",
    [string]$JaegerUrl = "http://localhost:16686",
    [string]$GrafanaUrl = "http://localhost:3001",
    [string]$Token,
    [string]$CorrelationId = "phase1-local-test-001",
    [switch]$StopAfter
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$ObservabilityScript = Join-Path $RepoRoot "scripts\observability-local.ps1"
$LocalDevScript = Join-Path $RepoRoot "local-dev.ps1"

$startedObservability = $false
$startedLocalServices = $false

function Invoke-Script {
    param(
        [string]$ScriptPath,
        [string[]]$Arguments
    )

    & powershell -ExecutionPolicy Bypass -File $ScriptPath @Arguments
    return $LASTEXITCODE
}

function Test-UrlReachable {
    param(
        [string]$Url
    )

    try {
        $null = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 3
        return $true
    }
    catch {
        return $false
    }
}

function Test-UrlStatus {
    param(
        [string]$Name,
        [string]$Url,
        [int]$Expected = 200
    )

    try {
        $resp = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 8
        if ($resp.StatusCode -ne $Expected) {
            Write-Host "[FAIL] $Name -> $Url (status=$($resp.StatusCode), expected=$Expected)" -ForegroundColor Red
            return $false
        }
        Write-Host "[PASS] $Name -> $Url" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "[FAIL] $Name -> $Url ($($_.Exception.Message))" -ForegroundColor Red
        return $false
    }
}

function Test-AuthenticatedGatewayFlow {
    param(
        [string]$BaseUrl,
        [string]$Bearer,
        [string]$Cid
    )

    if ([string]::IsNullOrWhiteSpace($Bearer)) {
        Write-Host "[SKIP] Gateway auth flow (no -Token provided)" -ForegroundColor Yellow
        return $true
    }

    $url = "$BaseUrl/api/businesses?city=Phoenix&limit=2"
    try {
        $resp = Invoke-WebRequest -UseBasicParsing $url -Headers @{
            Authorization      = "Bearer $Bearer"
            "X-Correlation-ID" = $Cid
        } -TimeoutSec 12

        if ($resp.StatusCode -ne 200) {
            Write-Host "[FAIL] Gateway business request status=$($resp.StatusCode)" -ForegroundColor Red
            return $false
        }

        $returnedCid = $resp.Headers["X-Correlation-ID"]
        if ($returnedCid -ne $Cid) {
            Write-Host "[FAIL] Correlation ID mismatch (sent=$Cid, got=$returnedCid)" -ForegroundColor Red
            return $false
        }

        Write-Host "[PASS] Gateway auth request + correlation header" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "[FAIL] Gateway auth flow ($($_.Exception.Message))" -ForegroundColor Red
        return $false
    }
}

Write-Host "Running Phase-1 local smoke test..." -ForegroundColor Cyan

if ($ObservabilityOnly) {
    Write-Host "[MODE] Observability-only: backend service checks will be skipped." -ForegroundColor Cyan
}

if ($Mode -eq "auto") {
    Write-Host "[AUTO] Ensuring observability stack is up..." -ForegroundColor Cyan
    $obsExit = Invoke-Script -ScriptPath $ObservabilityScript -Arguments @("-Action", "start")
    if ($obsExit -eq 0) {
        $startedObservability = $true
    }

    if (-not $ObservabilityOnly -and -not (Test-UrlReachable -Url "$GatewayUrl/health")) {
        Write-Host "[AUTO] Gateway not reachable, starting local services..." -ForegroundColor Cyan
        $svcExit = Invoke-Script -ScriptPath $LocalDevScript -Arguments @("-Action", "start")
        if ($svcExit -eq 0) {
            $startedLocalServices = $true
        }
        else {
            Write-Host "[WARN] local-dev start returned exit code $svcExit. Continuing with checks." -ForegroundColor Yellow
        }
    }
}

$results = @()



if (-not $ObservabilityOnly) {
    $results += Test-UrlStatus -Name "gateway health" -Url "$GatewayUrl/health"
}

if (-not $ObservabilityOnly) {
    $results += Test-UrlStatus -Name "business health" -Url "$BusinessUrl/health"
    $results += Test-UrlStatus -Name "recommendation health" -Url "$RecommendationUrl/health"
    $results += Test-UrlStatus -Name "ingestion health" -Url "$IngestionUrl/health"
}


if (-not $ObservabilityOnly) {
    $results += Test-UrlStatus -Name "gateway metrics" -Url "$GatewayUrl/metrics"
}

if (-not $ObservabilityOnly) {
    $results += Test-UrlStatus -Name "business metrics" -Url "$BusinessUrl/metrics"
    $results += Test-UrlStatus -Name "recommendation metrics" -Url "$RecommendationUrl/metrics"
    $results += Test-UrlStatus -Name "ingestion metrics" -Url "$IngestionUrl/metrics"
}

if (-not $ObservabilityOnly) {
    $results += Test-AuthenticatedGatewayFlow -BaseUrl $GatewayUrl -Bearer $Token -Cid $CorrelationId
}

$results += Test-UrlStatus -Name "prometheus ui" -Url $PrometheusUrl
$results += Test-UrlStatus -Name "jaeger ui" -Url $JaegerUrl
$results += Test-UrlStatus -Name "grafana ui" -Url $GrafanaUrl

try {
    $targets = Invoke-RestMethod "$PrometheusUrl/api/v1/targets" -TimeoutSec 8
    if ($targets.status -eq "success") {
        $active = @($targets.data.activeTargets)
        $upCount = @($active | Where-Object { $_.health -eq "up" }).Count
        Write-Host "[INFO] Prometheus active targets: $($active.Count), up: $upCount"
    }
}
catch {
    Write-Host "[WARN] Could not query Prometheus targets API: $($_.Exception.Message)" -ForegroundColor Yellow
}

if ($results -contains $false) {
    Write-Host "Phase-1 local smoke test: FAILED" -ForegroundColor Red
    if ($StopAfter) {
        if ($startedObservability) {
            $null = Invoke-Script -ScriptPath $ObservabilityScript -Arguments @("-Action", "stop")
        }
        if ($startedLocalServices) {
            $null = Invoke-Script -ScriptPath $LocalDevScript -Arguments @("-Action", "stop")
        }
    }
    exit 1
}

Write-Host "Phase-1 local smoke test: PASSED" -ForegroundColor Green

if ($StopAfter) {
    if ($startedObservability) {
        $null = Invoke-Script -ScriptPath $ObservabilityScript -Arguments @("-Action", "stop")
    }
    if ($startedLocalServices) {
        $null = Invoke-Script -ScriptPath $LocalDevScript -Arguments @("-Action", "stop")
    }
}

exit 0
