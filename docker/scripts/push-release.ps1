param(
    [string]$Namespace = "junfu26",
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"

$Images = @(
    "musicweb-web",
    "musicweb-music-api",
    "musicweb-qq-api",
    "musicweb-unblock",
    "musicweb-recommender",
    "musicweb-data",
    "musicweb-mysql-fast"
)

foreach ($Image in $Images) {
    docker push "${Namespace}/${Image}:${Tag}"
}

Write-Host "Release images pushed to Docker Hub namespace '$Namespace'."
