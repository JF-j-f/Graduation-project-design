param(
    [string]$Namespace = "junfu26",
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$ReleaseData = Join-Path $Root "docker\dist\release-data"
$ReleaseMode = Join-Path $ReleaseData "Mode"
$SourceSql = Join-Path $Root "Data\musicweb.sql"
$SanitizedSql = Join-Path $ReleaseData "musicweb.sql"
$SourceMode = Join-Path $Root "Project\MusicMode\Mode"
$ConfigGenerator = Join-Path $Root "docker\release\runtime\validate_and_generate_config.py"

$RequiredModeFiles = @(
    "recall\song_index.faiss",
    "recall\song_id_map.pkl",
    "recall\als_model.pkl",
    "feature_engineering\encoders_v3.pkl",
    "feature_engineering\user_stats.pkl",
    "feature_engineering\song_stats.pkl",
    "feature_engineering\svd_vecs.pkl",
    "fine_rank\lgbm\lgbm_model.pkl",
    "fine_rank\deepfm\deepfm_model.pth",
    "fine_rank\deepfm\model_config.pkl",
    "coarse_rank\bst\bst_model.pth",
    "coarse_rank\bst\model_config.pkl",
    "fine_rank\ensemble\ensemble_config.pkl",
    "fine_rank\ensemble\meta_learner.pkl"
)

function Get-DirectorySizeMb {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return 0
    }

    $TotalBytes = (Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum

    return [Math]::Round(($TotalBytes / 1MB), 1)
}

function Test-DockerImageExists {
    param([string]$ImageName)

    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        docker image inspect $ImageName 1>$null 2>$null
        return $LASTEXITCODE -eq 0
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
}

function Invoke-ReleaseDockerBuild {
    param(
        [string]$ImageName,
        [string]$Dockerfile,
        [string]$Context
    )

    $FullImageName = "${Namespace}/${ImageName}:${Tag}"
    if (Test-DockerImageExists $FullImageName) {
        Write-Host "Skipping existing image $FullImageName"
        return
    }

    Write-Host "Building $FullImageName..."
    docker build -t $FullImageName -f $Dockerfile $Context
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build $FullImageName."
    }
}

if (-not (Test-Path $SourceSql)) {
    throw "Missing Data/musicweb.sql."
}

if (-not (Test-Path $SourceMode)) {
    throw "Missing Project/MusicMode/Mode."
}

Remove-Item -LiteralPath $ReleaseData -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $ReleaseData | Out-Null

Write-Host "Preparing sanitized SQL for release data image..."
$EmailPattern = '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
$Reader = [System.IO.File]::OpenText($SourceSql)
$Writer = New-Object System.IO.StreamWriter($SanitizedSql, $false, [System.Text.UTF8Encoding]::new($false))
try {
    while (($Line = $Reader.ReadLine()) -ne $null) {
        if ($Line.StartsWith("INSERT INTO ``appeals`` VALUES")) {
            $Line = [regex]::Replace($Line, $EmailPattern, "public-placeholder@example.com")
        }
        $Writer.WriteLine($Line)
    }
}
finally {
    $Reader.Close()
    $Writer.Close()
}

Write-Host "Copying model artifacts into release data context..."
foreach ($RelativePath in $RequiredModeFiles) {
    $SourceFile = Join-Path $SourceMode $RelativePath
    if (-not (Test-Path -LiteralPath $SourceFile)) {
        throw "Missing required model artifact: Project/MusicMode/Mode/$RelativePath"
    }

    $TargetFile = Join-Path $ReleaseMode $RelativePath
    $TargetDirectory = Split-Path -Parent $TargetFile
    New-Item -ItemType Directory -Force -Path $TargetDirectory | Out-Null
    Copy-Item -LiteralPath $SourceFile -Destination $TargetFile -Force
}
Copy-Item -LiteralPath $ConfigGenerator -Destination (Join-Path $ReleaseData "validate_and_generate_config.py") -Force
Write-Host "Release model package size: $(Get-DirectorySizeMb $ReleaseMode) MB"

Push-Location $Root
try {
    Invoke-ReleaseDockerBuild "musicweb-web" "Project/MusicWeb/Dockerfile" "Project/MusicWeb"
    Invoke-ReleaseDockerBuild "musicweb-music-api" "Project/MusicWeb/src/main/webapp/Dockerfile.music-api" "Project/MusicWeb/src/main/webapp"
    Invoke-ReleaseDockerBuild "musicweb-qq-api" "Project/MusicWeb/src/main/webapp/MusicServer/qq_api/Dockerfile" "Project/MusicWeb/src/main/webapp/MusicServer/qq_api"
    Invoke-ReleaseDockerBuild "musicweb-unblock" "Project/MusicWeb/src/main/webapp/MusicServer/unblock/Dockerfile" "Project/MusicWeb/src/main/webapp/MusicServer/unblock"
    Invoke-ReleaseDockerBuild "musicweb-recommender" "Project/MusicMode/Dockerfile" "Project/MusicMode"
    Invoke-ReleaseDockerBuild "musicweb-data" "docker/release/data/Dockerfile" "docker/dist/release-data"
    Invoke-ReleaseDockerBuild "musicweb-all-in-one" "docker/release/all-in-one/Dockerfile" "."
}
finally {
    Pop-Location
    if (Test-Path -LiteralPath $ReleaseData) {
        $ResolvedReleaseData = (Resolve-Path -LiteralPath $ReleaseData).Path
        $ResolvedRoot = (Resolve-Path -LiteralPath $Root).Path
        if (-not $ResolvedReleaseData.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refuse to remove release data outside workspace: $ResolvedReleaseData"
        }
        Remove-Item -LiteralPath $ResolvedReleaseData -Recurse -Force
        Write-Host "Removed temporary release data context."
    }
}

Write-Host "Release images built with namespace '$Namespace' and tag '$Tag'."
