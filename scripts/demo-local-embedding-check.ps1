param(
  [string]$BaseUrl = "http://127.0.0.1:8000"
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

Write-Host "[check] login bilingual_admin"
$login = Invoke-Json -Method "POST" -Url "$BaseUrl/api/v1/auth/login" -Body @{
  email = "bilingual_admin@example.local"
  password = "Passw0rd!123"
}
$token = [string]$login.access_token
if (-not $token) {
  throw "login failed"
}

Write-Host "[check] retrieval runtime config"
$config = Invoke-Json -Method "GET" -Url "$BaseUrl/api/v1/system/retrieval-config" -Token $token
Write-Host "  embedding_provider:" $config.embedding_provider
Write-Host "  retrieval_engine:" $config.retrieval_engine
Write-Host "  pgvector_available:" $config.pgvector_available
Write-Host "  pgvector_sql_retrieval_enabled:" $config.pgvector_sql_retrieval_enabled

if ([string]$config.embedding_provider -like "*deterministic-mock*") {
  Write-Host "[warn] runtime is still mock embedding (or local embedding fallback to mock)."
} else {
  Write-Host "[ok] non-mock embedding provider is active."
}

Write-Host "[check] ask smoke query"
$ask = Invoke-Json -Method "POST" -Url "$BaseUrl/api/v1/qa/ask" -Token $token -Body @{
  question = "Summarize the Robot SDK Manual deployment checklist."
  mode = "auto"
  knowledge_base_codes = @()
}
Write-Host "  denied:" $ask.denied
Write-Host "  mode:" $ask.mode
Write-Host "  sources:" (@($ask.sources).Count)

Write-Host "[done] local embedding check finished."
