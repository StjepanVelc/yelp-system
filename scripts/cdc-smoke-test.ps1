param(
    [int]$TimeoutSeconds = 45,
    [switch]$SkipBringUp
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $RepoRoot
Set-Location $RepoRoot

function Get-EnvValue {
    param(
        [string]$Name,
        [string]$Default
    )

    if (Test-Path ".env") {
        $line = Get-Content .env | Where-Object { $_ -match "^$Name=" } | Select-Object -First 1
        if ($line) {
            $value = ($line -split "=", 2)[1].Trim()
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                return $value
            }
        }
    }

    return $Default
}

function Get-KeyExists {
    param([string]$Key)

    $out = docker compose exec -e REDISCLI_AUTH=$script:RedisPassword redis redis-cli --raw EXISTS $Key
    if ($LASTEXITCODE -ne 0) {
        throw "Failed Redis EXISTS for key: $Key"
    }

    $last = ($out | Select-Object -Last 1).Trim()
    return [int]$last
}

function Set-KeyWarm {
    param([string]$Key)

    docker compose exec -e REDISCLI_AUTH=$script:RedisPassword redis redis-cli --raw SET $Key warm | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed Redis SET for key: $Key"
    }
}

function Wait-KeyState {
    param(
        [string]$Key,
        [int]$Expected,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $state = Get-KeyExists -Key $Key
        if ($state -eq $Expected) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }

    $final = Get-KeyExists -Key $Key
    throw "Timeout waiting for key state. key=$Key expected=$Expected got=$final"
}

$script:AppEnv = Get-EnvValue -Name "APP_ENV" -Default "development"
$script:RedisPassword = Get-EnvValue -Name "REDIS_PASSWORD" -Default "dev_redis_pass"
$postgresPassword = Get-EnvValue -Name "POSTGRES_PASSWORD" -Default "change_me"

if (-not $SkipBringUp) {
    Write-Host "[1/6] Starting CDC stack..." -ForegroundColor Cyan
    docker compose up -d db redis zookeeper kafka debezium-connect cdc-consumer
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start CDC stack"
    }
}

Write-Host "[2/6] Registering/updating Debezium connector..." -ForegroundColor Cyan
./scripts/register-debezium-connector.ps1 -DatabasePassword $postgresPassword | Out-Null

Write-Host "[3/6] Preparing base business row..." -ForegroundColor Cyan
docker compose exec db psql -U postgres -d yelp -c "INSERT INTO businesses (id,name,city,state,is_open,stars,review_count) VALUES ('cdc-smoke-biz','CDC Smoke Biz','CityA','CA',true,4.0,10) ON CONFLICT (id) DO UPDATE SET city=EXCLUDED.city, is_open=EXCLUDED.is_open;" | Out-Null

$detailsKey = "yelp:$($script:AppEnv):business:details:cdc-smoke-biz:v1"
$recKey = "yelp:$($script:AppEnv):recommendation:by_business:cdc-smoke-biz:5:v1"
$citiesKey = "yelp:$($script:AppEnv):business:cities:all:v1"

Write-Host "[4/6] Testing businesses mapping..." -ForegroundColor Cyan
Set-KeyWarm -Key $detailsKey
Set-KeyWarm -Key $recKey
Set-KeyWarm -Key $citiesKey

docker compose exec db psql -U postgres -d yelp -c "UPDATE businesses SET city='CitySmoke' WHERE id='cdc-smoke-biz';" | Out-Null

Wait-KeyState -Key $detailsKey -Expected 0 -TimeoutSeconds $TimeoutSeconds
Wait-KeyState -Key $recKey -Expected 0 -TimeoutSeconds $TimeoutSeconds
Wait-KeyState -Key $citiesKey -Expected 0 -TimeoutSeconds $TimeoutSeconds

Write-Host "[5/6] Testing reviews mapping..." -ForegroundColor Cyan
Set-KeyWarm -Key $detailsKey
Set-KeyWarm -Key $recKey

$reviewId = "cdc-smoke-review-" + [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
docker compose exec db psql -U postgres -d yelp -c "INSERT INTO reviews (review_id,user_id,business_id,stars,useful,funny,cool,text,date) VALUES ('$reviewId','user-smoke','cdc-smoke-biz',5,0,0,0,'cdc smoke review',CURRENT_DATE::text) ON CONFLICT (review_id) DO NOTHING;" | Out-Null

Wait-KeyState -Key $detailsKey -Expected 1 -TimeoutSeconds $TimeoutSeconds
Wait-KeyState -Key $recKey -Expected 0 -TimeoutSeconds $TimeoutSeconds

Write-Host "[6/6] Success" -ForegroundColor Green
Write-Host "Business mapping: details=deleted, recommendation=deleted, cities=deleted"
Write-Host "Review mapping: details=kept, recommendation=deleted"
Write-Host "Used review id: $reviewId"
