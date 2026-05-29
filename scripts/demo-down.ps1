param(
  [switch]$ResetVolumes
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$composeArgs = @("-f", "infra/docker-compose.yml", "--env-file", ".env", "down")
if ($ResetVolumes) {
  $composeArgs += "-v"
}

docker compose @composeArgs
