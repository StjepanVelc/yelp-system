param(
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Action = "start"
)

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$ComposeFile = Join-Path $RepoRoot "infrastructure\observability\docker-compose.local.yml"

if (!(Test-Path $ComposeFile)) {
    throw "Missing compose file: $ComposeFile"
}

switch ($Action) {
    "start" {
        docker compose -f $ComposeFile up -d
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Host "Observability stack started (local mode)."
        Write-Host "Prometheus: http://localhost:9090"
        Write-Host "Jaeger:     http://localhost:16686"
        Write-Host "Grafana:    http://localhost:3001"
    }
    "stop" {
        docker compose -f $ComposeFile down
        exit $LASTEXITCODE
    }
    "status" {
        docker compose -f $ComposeFile ps
        exit $LASTEXITCODE
    }
    "restart" {
        docker compose -f $ComposeFile down
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        docker compose -f $ComposeFile up -d
        exit $LASTEXITCODE
    }
}
