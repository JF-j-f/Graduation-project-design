param(
    [string]$InstallDir = "$PWD\musicweb-docker",
    [string]$RawBaseUrl = "https://raw.githubusercontent.com/JF-j-f/Graduation-project-design/main"
)

$ErrorActionPreference = "Stop"

function Test-DockerCommand {
    try {
        docker version | Out-Null
    } catch {
        throw "Docker is not available. Please install and start Docker Desktop, then run this script again."
    }
}

function Download-ReleaseFile {
    param(
        [string]$SourceUrl,
        [string]$TargetPath
    )

    try {
        Invoke-WebRequest -Uri $SourceUrl -OutFile $TargetPath
    } catch {
        throw "Download failed: $SourceUrl. Please check network access, GitHub access, or repository URL."
    }
}

function Read-EnvFile {
    param([string]$EnvPath)

    $envValues = @{}
    Get-Content -LiteralPath $EnvPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $key, $value = $line.Split("=", 2)
        $envValues[$key.Trim()] = $value.Trim()
    }

    return $envValues
}

function Test-RequiredEnv {
    param([string]$EnvPath)

    $requiredKeys = @(
        "DB_PASSWORD",
        "MYSQL_ROOT_PASSWORD",
        "MAIL_USERNAME",
        "MAIL_PASSWORD",
        "MAIL_FROM",
        "LASTFM_API_KEY",
        "LASTFM_SHARED_SECRET",
        "NETEASE_COOKIE",
        "QQ_MUSIC_COOKIE"
    )

    $envValues = Read-EnvFile -EnvPath $EnvPath
    $missingKeys = @()
    foreach ($requiredKey in $requiredKeys) {
        if (-not $envValues.ContainsKey($requiredKey) -or [string]::IsNullOrWhiteSpace($envValues[$requiredKey])) {
            $missingKeys += $requiredKey
        }
    }

    if ($missingKeys.Count -gt 0) {
        Write-Host "Missing required config values:" -ForegroundColor Yellow
        $missingKeys | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
        return $false
    }

    return $true
}

Test-DockerCommand

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Set-Location -LiteralPath $InstallDir

$composePath = Join-Path $InstallDir "docker-compose.release.yml"
$envPath = Join-Path $InstallDir ".env"

Download-ReleaseFile `
    -SourceUrl "$RawBaseUrl/docker-compose.release.yml" `
    -TargetPath $composePath

if (-not (Test-Path -LiteralPath $envPath)) {
    Download-ReleaseFile `
        -SourceUrl "$RawBaseUrl/docker/.env.release.example" `
        -TargetPath $envPath
}

Write-Host "MusicWeb release files were downloaded to: $InstallDir"
Write-Host "Fill all required cookies, keys, mail auth code, and database passwords in the opened .env file."
Start-Process -FilePath notepad.exe -ArgumentList "`"$envPath`"" -Wait

if (-not (Test-RequiredEnv -EnvPath $envPath)) {
    throw "Config is incomplete. Startup stopped. Fill .env and run this script again."
}

docker compose --env-file $envPath -f $composePath up -d
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose startup failed with exit code $LASTEXITCODE. Check Docker Desktop, network access, and image pull errors, then run this script again."
}

Write-Host ""
Write-Host "MusicWeb startup was submitted. First image pull and database initialization can take several minutes."
Write-Host "Open: http://localhost:8082/musicweb/"
