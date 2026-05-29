param(
  [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

function Get-DotEnvValue {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Default
  )
  if (-not (Test-Path ".env")) {
    return $Default
  }
  $line = Get-Content ".env" | Where-Object { $_ -match "^\s*$Name\s*=" } | Select-Object -First 1
  if (-not $line) {
    return $Default
  }
  $value = ($line -split "=", 2)[1].Trim()
  return $value.Trim('"').Trim("'")
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker CLI not found. Please install Docker Desktop first."
}

try {
  docker info | Out-Null
} catch {
  throw "Docker daemon is not running. Start Docker Desktop and retry."
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "[init] .env not found. Copied .env.example -> .env"
}

$apiPort = Get-DotEnvValue -Name "API_PORT" -Default "8000"
$webPort = Get-DotEnvValue -Name "WEB_PORT" -Default "5173"

$composeArgs = @("-f", "infra/docker-compose.yml", "--env-file", ".env")
docker compose @composeArgs up -d --build

$healthUrl = "http://127.0.0.1:$apiPort/healthz"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$ready = $false
while ((Get-Date) -lt $deadline) {
  try {
    $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 3
    if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
      $ready = $true
      break
    }
  } catch {
    Start-Sleep -Seconds 2
    continue
  }
}

if (-not $ready) {
  Write-Host "[error] API health check timeout: $healthUrl"
  docker compose @composeArgs ps
  exit 1
}

Write-Host ""
Write-Host "Demo is ready."
Write-Host "Web: http://localhost:$webPort"
Write-Host "API Docs: http://localhost:$apiPort/docs"
Write-Host ""
Write-Host "Demo login:"
Write-Host "visitor@example.local"
Write-Host "tech_staff@example.local"
Write-Host "sales_staff@example.local"
Write-Host "product_staff@example.local"
Write-Host "bilingual_admin@example.local"
Write-Host ""
Write-Host "Next checks:"
Write-Host "python scripts/test_permission_matrix.py --base-url http://127.0.0.1:$apiPort"
