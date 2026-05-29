param(
  [switch]$ResetVolumes
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
  $PSNativeCommandUseErrorActionPreference = $true
}
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$composeArgs = @("-f", "infra/docker-compose.yml", "--env-file", ".env", "down")
if ($ResetVolumes) {
  $composeArgs += "-v"
}

docker compose @composeArgs
