$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Dist = Join-Path $Root "docker\dist"
$DataDist = Join-Path $Dist "Data"
$ImageDist = Join-Path $Dist "images"
$DockerDist = Join-Path $Dist "docker"
$PrivateDir = Join-Path $Root "docker\private"
$EnvFile = Join-Path $PrivateDir ".env"
$SourceSql = Join-Path $Root "Data\musicweb.sql"
$SanitizedSql = Join-Path $DataDist "musicweb.sql"

if (-not (Test-Path $EnvFile)) {
    throw "Missing docker/private/.env. Copy docker/.env.example first and fill it."
}

if (-not (Test-Path $SourceSql)) {
    throw "Missing Data/musicweb.sql. Cannot build offline data package."
}

New-Item -ItemType Directory -Force -Path $DataDist | Out-Null
New-Item -ItemType Directory -Force -Path $ImageDist | Out-Null
New-Item -ItemType Directory -Force -Path $DockerDist | Out-Null

Write-Host "Generating runtime SQL. Only appeals.contact_email is sanitized."
$EmailPattern = '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
$Reader = [System.IO.File]::OpenText($SourceSql)
$Writer = New-Object System.IO.StreamWriter($SanitizedSql, $false, [System.Text.UTF8Encoding]::new($false))
try {
    while (($Line = $Reader.ReadLine()) -ne $null) {
        if ($Line.StartsWith("INSERT INTO ``appeals`` VALUES")) {
            $Line = [regex]::Replace($Line, $EmailPattern, "")
        }
        $Writer.WriteLine($Line)
    }
}
finally {
    $Reader.Close()
    $Writer.Close()
}

Push-Location $Root
try {
    docker pull mysql:8.4
    docker pull redis:7-alpine
    docker compose --env-file docker/private/.env build
    docker save `
        musicweb-web:latest `
        musicweb-music-api:latest `
        musicweb-qq-api:latest `
        musicweb-unblock:latest `
        musicweb-recommender:latest `
        mysql:8.4 `
        redis:7-alpine `
        -o (Join-Path $ImageDist "musicweb-images.tar")

    tar -cf (Join-Path $Dist "musicmode-models.tar") -C "Project/MusicMode" "Mode"
}
finally {
    Pop-Location
}

Copy-Item -LiteralPath (Join-Path $Root "docker-compose.yml") -Destination $Dist -Force
Copy-Item -LiteralPath (Join-Path $Root "docker\.env.example") -Destination $DockerDist -Force
Copy-Item -LiteralPath (Join-Path $Root "docker\templates") -Destination $DockerDist -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Root "docker\scripts") -Destination $DockerDist -Recurse -Force

Write-Host "Offline runtime package generated: docker/dist"
Write-Host "Note: Data/kkbox-music-recommendation-challenge.zip is not included."
