param(
    [ValidateSet("start", "stop", "status")]
    [string]$Action = "start"
)

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$PythonExe = Join-Path $RepoRoot "venv\Scripts\python.exe"
$PidsFile = Join-Path $RepoRoot ".local-dev-pids.json"

if (!(Test-Path $PythonExe)) {
    throw "Python executable not found at $PythonExe. Activate/create venv first."
}

function Start-ServiceWindow {
    param(
        [string]$Name,
        [string]$Command
    )

    $startArgs = @{
        FilePath = "powershell"
        WorkingDirectory = $RepoRoot
        ArgumentList = @("-NoExit", "-Command", $Command)
        PassThru = $true
    }

    $proc = Start-Process @startArgs

    [pscustomobject]@{
        name = $Name
        pid  = $proc.Id
    }
}

function Load-TrackedProcesses {
    if (!(Test-Path $PidsFile)) {
        return @()
    }

    $raw = Get-Content $PidsFile -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return @()
    }

    $data = ConvertFrom-Json $raw
    if ($data -is [System.Array]) {
        return $data
    }

    return @($data)
}

switch ($Action) {
    "start" {
        if (Test-Path $PidsFile) {
            Write-Host "Tracked process file already exists: $PidsFile"
            Write-Host "Use: .\\local-dev.ps1 -Action status  OR  .\\local-dev.ps1 -Action stop"
            exit 1
        }

        $businessCmd = "$env:DATABASE_URL='postgresql://postgres:stipe245gaba@localhost:5432/yelp'; & '$PythonExe' -m uvicorn app.main:app --app-dir services/business-service --host 0.0.0.0 --port 8001"
        $recommendationCmd = "$env:DATABASE_URL='postgresql://postgres:stipe245gaba@localhost:5432/yelp'; $env:BUSINESS_SERVICE_GRPC='localhost:50051'; & '$PythonExe' -m uvicorn app.main:app --app-dir services/recommendation-service --host 0.0.0.0 --port 8002"
        $gatewayCmd = "$env:BUSINESS_SERVICE_URL='http://localhost:8001'; $env:RECOMMENDATION_SERVICE_URL='http://localhost:8002'; $env:USER_SERVICE_URL='http://localhost:8001'; $env:JWT_SECRET='dev-secret-change-me'; $env:JWT_ALGORITHM='HS256'; $env:JWT_ISSUER='yelp-auth'; $env:JWT_AUDIENCE='yelp-api'; $env:BUSINESS_REQUIRED_ROLES='business:read'; $env:RECOMMENDATION_REQUIRED_ROLES='recommendation:read'; & '$PythonExe' -m uvicorn app.main:app --app-dir services/api-gateway --host 0.0.0.0 --port 8000"
        $frontendCmd = "npm --prefix services/frontend run dev"

        $processes = @()
        $processes += Start-ServiceWindow -Name "business-service" -Command $businessCmd
        Start-Sleep -Milliseconds 500
        $processes += Start-ServiceWindow -Name "recommendation-service" -Command $recommendationCmd
        Start-Sleep -Milliseconds 500
        $processes += Start-ServiceWindow -Name "api-gateway" -Command $gatewayCmd
        Start-Sleep -Milliseconds 500
        $processes += Start-ServiceWindow -Name "frontend" -Command $frontendCmd

        $processes | ConvertTo-Json | Set-Content $PidsFile

        Write-Host "Local stack started."
        Write-Host "Frontend:              http://localhost:3000"
        Write-Host "API Gateway:           http://localhost:8000"
        Write-Host "Business Service:      http://localhost:8001"
        Write-Host "Recommendation Service:http://localhost:8002"
        Write-Host "Use .\\local-dev.ps1 -Action stop to stop all tracked processes."
    }

    "stop" {
        $processes = Load-TrackedProcesses
        if ($processes.Count -eq 0) {
            Write-Host "No tracked processes found."
            if (Test-Path $PidsFile) {
                Remove-Item $PidsFile -Force
            }
            exit 0
        }

        foreach ($p in $processes) {
            try {
                Stop-Process -Id $p.pid -Force -ErrorAction Stop
                Write-Host "Stopped $($p.name) (PID $($p.pid))"
            }
            catch {
                Write-Host "Could not stop $($p.name) (PID $($p.pid)) - already stopped or missing."
            }
        }

        Remove-Item $PidsFile -Force
        Write-Host "All tracked processes have been stopped."
    }

    "status" {
        $processes = Load-TrackedProcesses
        if ($processes.Count -eq 0) {
            Write-Host "No tracked processes found."
            exit 0
        }

        foreach ($p in $processes) {
            $proc = Get-Process -Id $p.pid -ErrorAction SilentlyContinue
            if ($null -eq $proc) {
                Write-Host "$($p.name): not running (PID $($p.pid))"
            }
            else {
                Write-Host "$($p.name): running (PID $($p.pid))"
            }
        }
    }
}
