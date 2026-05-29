param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$WebUrl = "http://127.0.0.1:5173",
  [switch]$SkipPermissionMatrix
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
  $PSNativeCommandUseErrorActionPreference = $true
}

function Invoke-Json {
  param(
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Url,
    [object]$Body = $null,
    [string]$Token = ""
  )
  $headers = @{}
  if ($Token) {
    $headers["Authorization"] = "Bearer $Token"
  }
  if ($null -ne $Body) {
    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 5)
  }
  return Invoke-RestMethod -Method $Method -Uri $Url -Headers $headers
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "[check] API health: $BaseUrl/healthz"
$health = Invoke-Json -Method "GET" -Url "$BaseUrl/healthz"
Write-Host "  health response:" ($health | ConvertTo-Json -Compress)

Write-Host "[check] Web availability: $WebUrl"
$webResp = Invoke-WebRequest -Uri $WebUrl -UseBasicParsing -TimeoutSec 5
Write-Host "  web status:" $webResp.StatusCode

Write-Host "[check] Compose services"
docker compose -f infra/docker-compose.yml --env-file .env ps

$accounts = @(
  "visitor@example.local",
  "tech_staff@example.local",
  "sales_staff@example.local",
  "marketing_staff@example.local",
  "support_staff@example.local",
  "hr_staff@example.local",
  "admin_staff@example.local",
  "product_staff@example.local",
  "bilingual_admin@example.local"
)

$tokenByEmail = @{}
foreach ($email in $accounts) {
  $login = Invoke-Json -Method "POST" -Url "$BaseUrl/api/v1/auth/login" -Body @{
    email = $email
    password = "Passw0rd!123"
  }
  if (-not $login.access_token) {
    throw "login failed: $email"
  }
  $tokenByEmail[$email] = [string]$login.access_token
  Write-Host "  [ok] login $email"
}

$adminToken = $tokenByEmail["bilingual_admin@example.local"]
$kbs = Invoke-Json -Method "GET" -Url "$BaseUrl/api/v1/knowledge-bases" -Token $adminToken
$kbCount = @($kbs).Count
Write-Host "[check] Seeded KB count:" $kbCount
if ($kbCount -ne 9) {
  throw "expected 9 knowledge bases, got $kbCount"
}

if (-not $SkipPermissionMatrix) {
  Write-Host "[check] Permission matrix script"
  python scripts/test_permission_matrix.py --base-url $BaseUrl
}

Write-Host "[done] demo-check passed."
