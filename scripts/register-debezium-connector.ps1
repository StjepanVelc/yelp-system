param(
    [string]$ConnectUrl = "http://localhost:8083",
    [string]$ConnectorFile = "infrastructure/debezium/connector.yelp-postgres.json",
    [string]$ConnectorName = "",
    [string]$DatabasePassword = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $RepoRoot
Set-Location $RepoRoot

if (!(Test-Path $ConnectorFile)) {
    throw "Connector config not found: $ConnectorFile"
}

$raw = Get-Content -Path $ConnectorFile -Raw
$payload = $raw | ConvertFrom-Json

if ($ConnectorName) {
    $payload.name = $ConnectorName
}

if ($DatabasePassword) {
    $payload.config."database.password" = $DatabasePassword
}

if (-not $payload.name) {
    throw "Connector name is missing in JSON and not provided via -ConnectorName"
}

if (-not $payload.config) {
    throw "Connector config is missing in JSON file"
}

$name = [string]$payload.name
$connectorsUrl = "$ConnectUrl/connectors"
$connectorUrl = "$ConnectUrl/connectors/$name"

Write-Host "Checking connector '$name' on $ConnectUrl ..."

$exists = $false
try {
    Invoke-RestMethod -Uri $connectorUrl -Method Get | Out-Null
    $exists = $true
}
catch {
    $exists = $false
}

if ($exists) {
    Write-Host "Connector exists. Updating config..."
    $configJson = ($payload.config | ConvertTo-Json -Depth 50)
    Invoke-RestMethod -Uri "$connectorUrl/config" -Method Put -ContentType "application/json" -Body $configJson | Out-Null
    Write-Host "Connector updated: $name" -ForegroundColor Green
}
else {
    Write-Host "Connector does not exist. Creating..."
    $body = $payload | ConvertTo-Json -Depth 50
    Invoke-RestMethod -Uri $connectorsUrl -Method Post -ContentType "application/json" -Body $body | Out-Null
    Write-Host "Connector created: $name" -ForegroundColor Green
}

Write-Host "Connector status:" -ForegroundColor Cyan
Invoke-RestMethod -Uri "$connectorUrl/status" -Method Get | ConvertTo-Json -Depth 10
