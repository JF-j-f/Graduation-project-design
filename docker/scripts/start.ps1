$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$PrivateDir = Join-Path $Root "docker\private"
$EnvExample = Join-Path $Root "docker\.env.example"
$EnvFile = Join-Path $PrivateDir ".env"
$SecretsFile = Join-Path $PrivateDir "secrets.txt"
$CredentialFile = Join-Path $PrivateDir "api_credentials.json"
$CredentialTemplate = Join-Path $Root "docker\templates\api_credentials.json.example"
$SqlFile = Join-Path $Root "Data\musicweb.sql"
$QqCredentialDir = Join-Path $PrivateDir "qq_credentials"

New-Item -ItemType Directory -Force -Path $PrivateDir | Out-Null
New-Item -ItemType Directory -Force -Path $QqCredentialDir | Out-Null

if (-not (Test-Path $EnvFile)) {
    Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
    Write-Host "Created docker/private/.env. Edit it, then run this script again."
    exit 1
}

if (-not (Test-Path $CredentialFile)) {
    Copy-Item -LiteralPath $CredentialTemplate -Destination $CredentialFile
    Write-Host "Created docker/private/api_credentials.json. VIP playback is disabled until cookies are filled."
}

if (-not (Test-Path $SqlFile)) {
    throw "Missing Data/musicweb.sql. MySQL container cannot initialize project data."
}

$EnvMap = @{}
Get-Content -LiteralPath $EnvFile -Encoding UTF8 | ForEach-Object {
    $Line = $_.Trim()
    if ($Line -and -not $Line.StartsWith("#") -and $Line.Contains("=")) {
        $Key, $Value = $Line.Split("=", 2)
        $EnvMap[$Key.Trim()] = $Value.Trim()
    }
}

$SecretKeys = @(
    "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
    "REDIS_HOST", "REDIS_PORT",
    "MUSIC_API_URL", "QQ_API_URL", "UNBLOCK_API_URL",
    "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM",
    "LASTFM_API_KEY", "LASTFM_SHARED_SECRET",
    "SOURCE_WEBAPP_PATH"
)

$SecretLines = @(
    "# ============================================================",
    "# MusicWeb Docker generated private config",
    "# Edit docker/private/.env and rerun this script to sync values",
    "# ============================================================"
)

foreach ($Key in $SecretKeys) {
    $Value = ""
    if ($EnvMap.ContainsKey($Key)) {
        $Value = $EnvMap[$Key]
    }
    $SecretLines += "$Key=$Value"
}

Set-Content -LiteralPath $SecretsFile -Value $SecretLines -Encoding UTF8

Push-Location $Root
try {
    docker compose --env-file docker/private/.env up -d --build
}
finally {
    Pop-Location
}

$WebPort = "8082"
if ($EnvMap.ContainsKey("MUSICWEB_PUBLIC_PORT") -and $EnvMap["MUSICWEB_PUBLIC_PORT"]) {
    $WebPort = $EnvMap["MUSICWEB_PUBLIC_PORT"]
}

Write-Host "Docker compose startup command executed. First MySQL boot imports Data/musicweb.sql."
Write-Host "Web URL: http://localhost:$WebPort/musicweb/"
