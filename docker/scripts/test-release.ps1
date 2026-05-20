param(
    [string]$EnvFile = "docker\.env.release.example"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Push-Location $Root
try {
    docker compose --env-file $EnvFile -f docker-compose.release.yml config --quiet

    $ComposeText = Get-Content -LiteralPath "docker-compose.release.yml" -Raw -Encoding UTF8
    $ForbiddenPatterns = @(
        "./Project",
        "./Data",
        "./docker/private",
        "build:"
    )

    foreach ($Pattern in $ForbiddenPatterns) {
        if ($ComposeText.Contains($Pattern)) {
            throw "Release compose still contains local dependency: $Pattern"
        }
    }

    $TempConfig = Join-Path $env:TEMP ("musicweb-release-config-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $TempConfig | Out-Null
    try {
        $env:CONFIG_OUTPUT_DIR = $TempConfig
        $env:DB_PASSWORD = "test-db-password"
        $env:MYSQL_ROOT_PASSWORD = "test-root-password"
        $env:MAIL_USERNAME = "test@example.com"
        $env:MAIL_PASSWORD = "test-mail-password"
        $env:MAIL_FROM = "test@example.com"
        $env:LASTFM_API_KEY = "test-lastfm-key"
        $env:LASTFM_SHARED_SECRET = "test-lastfm-secret"
        $env:NETEASE_COOKIE = "MUSIC_U=test"
        $env:QQ_MUSIC_COOKIE = "qqmusic_key=test"
        python docker/release/runtime/validate_and_generate_config.py
    }
    finally {
        Remove-Item -LiteralPath $TempConfig -Recurse -Force -ErrorAction SilentlyContinue
    }
}
finally {
    Pop-Location
}

Write-Host "Release compose and config validation checks completed."
