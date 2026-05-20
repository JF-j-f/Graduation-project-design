$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Push-Location $Root
try {
    docker compose --env-file docker/private/.env down
}
finally {
    Pop-Location
}
