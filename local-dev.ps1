param(
    [ValidateSet("start", "stop", "status")]
    [string]$Action = "start"
)

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$PythonExe = Join-Path $RepoRoot "venv\Scripts\python.exe"
$PidsFile = Join-Path $RepoRoot ".local-dev-pids.json"
$EnvFile = Join-Path $RepoRoot ".env"

if (!(Test-Path $PythonExe)) {
    throw "Python executable not found at $PythonExe. Activate/create venv first."
}

function Import-DotEnv {
    param([string]$Path)

    if (!(Test-Path $Path)) {
        return
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }

        $parts = $trimmed.Split("=", 2)
        if ($parts.Count -ne 2) {
            continue
        }

        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if (![string]::IsNullOrWhiteSpace($key)) {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

function Start-ServiceWindow {
    param(
        [string]$Name,
        [string]$Command
    )

    $startArgs = @{
        FilePath         = "powershell"
        WorkingDirectory = $RepoRoot
        ArgumentList     = @("-NoExit", "-Command", $Command)
        PassThru         = $true
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

function Escape-SingleQuotedValue {
    param([string]$Value)
    return $Value -replace "'", "''"
}

function Resolve-DatabaseUrl {
    $hasPostgresVars = ($env:POSTGRES_HOST -or $env:POSTGRES_PORT -or $env:POSTGRES_DB -or $env:POSTGRES_USER -or $env:POSTGRES_PASSWORD)

    if ($hasPostgresVars) {
        $pgHost = if ($env:POSTGRES_HOST) { $env:POSTGRES_HOST } else { "localhost" }
        $port = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { "5432" }
        $db = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "yelp" }
        $user = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "postgres" }
        $password = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "change_me" }

        $encodedUser = [uri]::EscapeDataString($user)
        $encodedPassword = [uri]::EscapeDataString($password)
        return "postgresql://$encodedUser`:$encodedPassword@$pgHost`:$port/$db"
    }

    if ($env:DATABASE_URL) {
        return $env:DATABASE_URL
    }

    return "postgresql://postgres:change_me@localhost:5432/yelp"
}

function Get-PortOwners {
    param([int[]]$Ports)

    $results = @()
    foreach ($port in $Ports) {
        $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

        foreach ($ownerPid in $listeners) {
            $proc = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
            $results += [pscustomobject]@{
                Port    = $port
                PID     = $ownerPid
                Process = if ($proc) { $proc.ProcessName } else { "<unknown>" }
            }
        }
    }

    return $results
}

switch ($Action) {
    "start" {
        if (Test-Path $PidsFile) {
            Write-Host "Tracked process file already exists: $PidsFile"
            Write-Host "Use: .\\local-dev.ps1 -Action status  OR  .\\local-dev.ps1 -Action stop"
            exit 1
        }

        $requiredPorts = @(3000, 8000, 8001, 8002, 50051)
        $portOwners = Get-PortOwners -Ports $requiredPorts
        if ($portOwners.Count -gt 0) {
            Write-Host "Cannot start local stack because required ports are already in use:" -ForegroundColor Yellow
            $portOwners | Sort-Object Port, PID | Format-Table -AutoSize
            Write-Host ""
            Write-Host "Tip: stop Docker containers or existing local processes, then retry." -ForegroundColor Yellow
            Write-Host "Common command: docker compose down" -ForegroundColor Yellow
            exit 1
        }

        Import-DotEnv -Path $EnvFile

        $databaseUrl = Resolve-DatabaseUrl
        if ($databaseUrl -match "postgresql://user:") {
            Write-Host "Warning: DATABASE_URL uses username 'user'. If your local DB user is 'postgres', update .env accordingly." -ForegroundColor Yellow
        }
        $businessGrpc = if ($env:BUSINESS_SERVICE_GRPC) { $env:BUSINESS_SERVICE_GRPC } else { "localhost:50051" }
        $businessServiceUrl = if ($env:BUSINESS_SERVICE_URL) { $env:BUSINESS_SERVICE_URL } else { "http://localhost:8001" }
        $recommendationServiceUrl = if ($env:RECOMMENDATION_SERVICE_URL) { $env:RECOMMENDATION_SERVICE_URL } else { "http://localhost:8002" }
        $userServiceUrl = if ($env:USER_SERVICE_URL) { $env:USER_SERVICE_URL } else { "http://localhost:8001" }
        $jwtSecret = if ($env:JWT_SECRET) { $env:JWT_SECRET } else { "dev-secret-change-me" }
        $jwtAlgorithm = if ($env:JWT_ALGORITHM) { $env:JWT_ALGORITHM } else { "HS256" }
        $jwtIssuer = if ($env:JWT_ISSUER) { $env:JWT_ISSUER } else { "yelp-auth" }
        $jwtAudience = if ($env:JWT_AUDIENCE) { $env:JWT_AUDIENCE } else { "yelp-api" }
        $businessRequiredRoles = if ($env:BUSINESS_REQUIRED_ROLES) { $env:BUSINESS_REQUIRED_ROLES } else { "business:read" }
        $recommendationRequiredRoles = if ($env:RECOMMENDATION_REQUIRED_ROLES) { $env:RECOMMENDATION_REQUIRED_ROLES } else { "recommendation:read" }

        $businessCmd = "`$env:DATABASE_URL='$(Escape-SingleQuotedValue $databaseUrl)'; & '$PythonExe' -m uvicorn app.main:app --app-dir services/business-service --host 0.0.0.0 --port 8001"
        $recommendationCmd = "`$env:DATABASE_URL='$(Escape-SingleQuotedValue $databaseUrl)'; `$env:BUSINESS_SERVICE_GRPC='$(Escape-SingleQuotedValue $businessGrpc)'; & '$PythonExe' -m uvicorn app.main:app --app-dir services/recommendation-service --host 0.0.0.0 --port 8002"
        $gatewayCmd = "`$env:BUSINESS_SERVICE_URL='$(Escape-SingleQuotedValue $businessServiceUrl)'; `$env:RECOMMENDATION_SERVICE_URL='$(Escape-SingleQuotedValue $recommendationServiceUrl)'; `$env:USER_SERVICE_URL='$(Escape-SingleQuotedValue $userServiceUrl)'; `$env:JWT_SECRET='$(Escape-SingleQuotedValue $jwtSecret)'; `$env:JWT_ALGORITHM='$(Escape-SingleQuotedValue $jwtAlgorithm)'; `$env:JWT_ISSUER='$(Escape-SingleQuotedValue $jwtIssuer)'; `$env:JWT_AUDIENCE='$(Escape-SingleQuotedValue $jwtAudience)'; `$env:BUSINESS_REQUIRED_ROLES='$(Escape-SingleQuotedValue $businessRequiredRoles)'; `$env:RECOMMENDATION_REQUIRED_ROLES='$(Escape-SingleQuotedValue $recommendationRequiredRoles)'; & '$PythonExe' -m uvicorn app.main:app --app-dir services/api-gateway --host 0.0.0.0 --port 8000"
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
