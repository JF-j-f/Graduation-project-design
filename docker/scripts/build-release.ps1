param(
    [string]$Namespace = "junfu26",
    [string]$Tag = "latest",
    [string]$LocalMysqlHost = "127.0.0.1",
    [int]$LocalMysqlPort = 3306,
    [string]$LocalMysqlUser = "root",
    [string]$LocalMysqlPassword = "",
    [string]$LocalMysqlDatabase = "musicweb"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$ReleaseData = Join-Path $Root "docker\dist\release-data"
$ReleaseMode = Join-Path $ReleaseData "Mode"
$MysqlFastContext = Join-Path $Root "docker\dist\mysql-fast-context"
$MysqlExportRoot = $null
$SourceSql = Join-Path $Root "Data\musicweb.sql"
$SanitizedSql = Join-Path $ReleaseData "musicweb.sql"
$SourceMode = Join-Path $Root "Project\MusicMode\Mode"
$ConfigGenerator = Join-Path $Root "docker\release\runtime\validate_and_generate_config.py"
$MysqlFastEntrypoint = Join-Path $Root "docker\release\mysql-fast\entrypoint.sh"
$MysqlSeedContainer = "musicweb-mysql-fast-seed-build"
$MysqlSeedRootPassword = "musicweb-seed-root"
$MysqlSeedUserPassword = "musicweb-seed-user"
$CoreMysqlTables = @("songs", "play_history", "users")

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

function Invoke-DockerCommandAllowFailure {
    param([string[]]$Arguments)

    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        docker @Arguments 1>$null 2>$null
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
}

function Get-LocalMysqlBaseArguments {
    $Arguments = @(
        "--host=$LocalMysqlHost",
        "--port=$LocalMysqlPort",
        "--user=$LocalMysqlUser",
        "--default-character-set=utf8mb4"
    )

    if (-not [string]::IsNullOrEmpty($LocalMysqlPassword)) {
        $Arguments += "--password=$LocalMysqlPassword"
    }

    return $Arguments
}

function Invoke-LocalMysqlScalar {
    param([string]$Query)

    $Arguments = Get-LocalMysqlBaseArguments
    $Arguments += @("--batch", "--skip-column-names", "--execute=$Query")
    $Output = & mysql @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Local MySQL query failed: $Query"
    }

    return ($Output | Select-Object -First 1)
}

function Invoke-LocalMysqlRows {
    param([string]$Query)

    $Arguments = Get-LocalMysqlBaseArguments
    $Arguments += @("--batch", "--skip-column-names", "--execute=$Query")
    $Output = & mysql @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Local MySQL query failed: $Query"
    }

    return @($Output)
}

function Invoke-LocalMysqlDump {
    param([string[]]$ExtraArguments)

    $Arguments = Get-LocalMysqlBaseArguments
    $Arguments += $ExtraArguments
    & mysqldump @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "mysqldump failed: $($ExtraArguments -join ' ')"
    }
}

function Join-ProcessArguments {
    param([string[]]$Arguments)

    $QuotedArguments = foreach ($Argument in $Arguments) {
        if ($Argument -match '[\s"]') {
            '"' + $Argument.Replace('\', '\\').Replace('"', '\"') + '"'
        }
        else {
            $Argument
        }
    }

    return ($QuotedArguments -join ' ')
}

function Invoke-LocalMysqlClientExport {
    param(
        [string]$Query,
        [string]$OutputPath
    )

    $Arguments = Get-LocalMysqlBaseArguments
    $Arguments += @(
        "--database=$LocalMysqlDatabase",
        "--batch",
        "--raw",
        "--quick",
        "--skip-column-names"
    )

    $StartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $StartInfo.FileName = "mysql"
    $StartInfo.Arguments = Join-ProcessArguments $Arguments
    $StartInfo.UseShellExecute = $false
    $StartInfo.RedirectStandardInput = $true
    $StartInfo.RedirectStandardOutput = $true
    $StartInfo.RedirectStandardError = $true
    $StartInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $StartInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

    $Process = New-Object System.Diagnostics.Process
    $Process.StartInfo = $StartInfo

    $Writer = New-Object System.IO.StreamWriter($OutputPath, $false, [System.Text.UTF8Encoding]::new($false))
    try {
        [void]$Process.Start()
        $Process.StandardInput.WriteLine($Query)
        $Process.StandardInput.Close()

        while (-not $Process.StandardOutput.EndOfStream) {
            $Writer.WriteLine($Process.StandardOutput.ReadLine())
        }

        $ErrorOutput = $Process.StandardError.ReadToEnd()
        $Process.WaitForExit()
        if ($Process.ExitCode -ne 0) {
            throw "Local MySQL export query failed: $ErrorOutput"
        }
    }
    finally {
        $Writer.Close()
        if (-not $Process.HasExited) {
            $Process.Kill()
        }
        $Process.Dispose()
    }
}

function Escape-MysqlIdentifier {
    param([string]$Identifier)

    return $Identifier.Replace("``", "````")
}

function Escape-MysqlStringLiteral {
    param([string]$Value)

    return $Value.Replace("\", "\\").Replace("'", "''")
}

function Get-TableExportQuery {
    param([string]$TableName)

    $EscapedDatabase = Escape-MysqlStringLiteral $LocalMysqlDatabase
    $EscapedTableLiteral = Escape-MysqlStringLiteral $TableName
    $Columns = Invoke-LocalMysqlRows "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='$EscapedDatabase' AND TABLE_NAME='$EscapedTableLiteral' ORDER BY ORDINAL_POSITION;"
    if ($Columns.Count -eq 0) {
        throw "No columns found for table '$TableName'."
    }

    $Expressions = foreach ($ColumnName in $Columns) {
        $EscapedColumn = Escape-MysqlIdentifier $ColumnName
        "IFNULL(REPLACE(REPLACE(REPLACE(REPLACE(CAST(``$EscapedColumn`` AS CHAR CHARACTER SET utf8mb4), '\\', '\\\\'), CHAR(9), '\\t'), CHAR(10), '\\n'), CHAR(13), '\\r'), '\\N')"
    }

    $EscapedTable = Escape-MysqlIdentifier $TableName
    return "SELECT CONCAT_WS(CHAR(9), $($Expressions -join ', ')) FROM ``$EscapedTable``;"
}

function Remove-DirectorySafely {
    param(
        [string]$Path,
        [string]$ExpectedLeaf
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return
    }

    $ResolvedPath = (Resolve-Path -LiteralPath $Path).Path
    if ((Split-Path -Leaf $ResolvedPath) -ne $ExpectedLeaf) {
        throw "Refuse to remove unexpected directory: $ResolvedPath"
    }

    try {
        Remove-Item -LiteralPath $ResolvedPath -Recurse -Force -ErrorAction Stop
    }
    catch {
        $CurrentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        # MySQL 服务端导出的 --tab 文件可能归属于 NETWORK SERVICE。
        # 这里仅对受控临时目录接管权限，保证构建结束后不留下大体积一次性文件。
        & takeown /F $ResolvedPath /R /D Y | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to take ownership of temporary directory: $ResolvedPath"
        }

        & icacls $ResolvedPath /grant "${CurrentIdentity}:(OI)(CI)F" /T /C | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to grant cleanup permission for temporary directory: $ResolvedPath"
        }

        Remove-Item -LiteralPath $ResolvedPath -Recurse -Force -ErrorAction Stop
    }
}

function Test-LocalMysqlSourceDatabase {
    Write-Host "Checking local MySQL source database $LocalMysqlDatabase ..."
    $EscapedDatabase = Escape-MysqlStringLiteral $LocalMysqlDatabase
    $DatabaseExists = Invoke-LocalMysqlScalar "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='$EscapedDatabase';"
    if ([int]$DatabaseExists -ne 1) {
        throw "Local MySQL database '$LocalMysqlDatabase' does not exist."
    }

    foreach ($TableName in $CoreMysqlTables) {
        $EscapedTable = Escape-MysqlIdentifier $TableName
        $Count = Invoke-LocalMysqlScalar "SELECT COUNT(*) FROM ``$LocalMysqlDatabase``.``$EscapedTable``;"
        if ([int64]$Count -le 0) {
            throw "Local MySQL table '$TableName' is empty or unavailable."
        }
        Write-Host "  $TableName rows: $Count"
    }
}

function Export-LocalMysqlDatabaseForFastSeed {
    param([string]$SchemaDumpPath)

    Test-LocalMysqlSourceDatabase

    $script:MysqlExportRoot = Join-Path $Root "docker\dist\mysql-export"
    Remove-DirectorySafely -Path $script:MysqlExportRoot -ExpectedLeaf "mysql-export"
    New-Item -ItemType Directory -Force -Path $script:MysqlExportRoot | Out-Null

    Write-Host "Exporting local MySQL schema to $SchemaDumpPath ..."
    Invoke-LocalMysqlDump @(
        "--no-data",
        "--routines",
        "--triggers",
        "--events",
        "--single-transaction",
        "--set-gtid-purged=OFF",
        "--result-file=$SchemaDumpPath",
        $LocalMysqlDatabase
    )

    $EscapedDatabaseLiteral = Escape-MysqlStringLiteral $LocalMysqlDatabase
    $Tables = Invoke-LocalMysqlRows "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='$EscapedDatabaseLiteral' AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME;"
    if ($Tables.Count -eq 0) {
        throw "No base tables found in local MySQL database '$LocalMysqlDatabase'."
    }

    Write-Host "Exporting local MySQL tables to client-side tab files under $script:MysqlExportRoot ..."
    foreach ($TableName in $Tables) {
        $DataFile = Join-Path $script:MysqlExportRoot "$TableName.txt"
        $ExportQuery = Get-TableExportQuery -TableName $TableName
        Write-Host "  exporting $TableName ..."
        Invoke-LocalMysqlClientExport -Query $ExportQuery -OutputPath $DataFile
    }
}

function Test-SeedMysqlReady {
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        docker exec $MysqlSeedContainer mysqladmin ping `
            -h 127.0.0.1 `
            -uroot `
            "-p$MysqlSeedRootPassword" `
            --silent 1>$null 2>$null
        return $LASTEXITCODE -eq 0
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
}

function New-MysqlFastBuildContext {
    param([string]$ImageName)

    if (Test-DockerImageExists $ImageName) {
        Write-Host "Skipping MySQL fast seed generation because $ImageName already exists"
        return
    }

    if (-not (Test-Path -LiteralPath $MysqlFastEntrypoint)) {
        throw "Missing docker/release/mysql-fast/entrypoint.sh."
    }

    Remove-Item -LiteralPath $MysqlFastContext -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $MysqlFastContext | Out-Null
    Copy-Item -LiteralPath $MysqlFastEntrypoint -Destination (Join-Path $MysqlFastContext "entrypoint.sh") -Force

    $SchemaDumpPath = Join-Path $MysqlFastContext "schema.sql"
    $LoadDataSqlPath = Join-Path $MysqlFastContext "load-data.sql"
    Export-LocalMysqlDatabaseForFastSeed -SchemaDumpPath $SchemaDumpPath

    $EscapedDatabaseLiteral = Escape-MysqlStringLiteral $LocalMysqlDatabase
    $Tables = Invoke-LocalMysqlRows "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='$EscapedDatabaseLiteral' AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME;"
    if ($Tables.Count -eq 0) {
        throw "No base tables found in local MySQL database '$LocalMysqlDatabase'."
    }

    $LoadSqlBuilder = New-Object System.Text.StringBuilder
    [void]$LoadSqlBuilder.AppendLine("SET GLOBAL local_infile = 1;")
    [void]$LoadSqlBuilder.AppendLine("SET SESSION FOREIGN_KEY_CHECKS = 0;")
    [void]$LoadSqlBuilder.AppendLine("SET SESSION UNIQUE_CHECKS = 0;")
    [void]$LoadSqlBuilder.AppendLine("USE ``$LocalMysqlDatabase``;")
    foreach ($TableName in $Tables) {
        $EscapedTable = Escape-MysqlIdentifier $TableName
        $EscapedTableFile = Escape-MysqlStringLiteral $TableName
        [void]$LoadSqlBuilder.AppendLine("LOAD DATA LOCAL INFILE '/tmp/musicweb-export/$EscapedTableFile.txt' INTO TABLE ``$EscapedTable`` CHARACTER SET utf8mb4 FIELDS TERMINATED BY '\t' ESCAPED BY '\\' LINES TERMINATED BY '\n';")
    }
    [void]$LoadSqlBuilder.AppendLine("UPDATE ``appeals`` SET ``contact_email`` = '' WHERE ``contact_email`` IS NOT NULL AND ``contact_email`` <> '';")
    [void]$LoadSqlBuilder.AppendLine("SET SESSION UNIQUE_CHECKS = 1;")
    [void]$LoadSqlBuilder.AppendLine("SET SESSION FOREIGN_KEY_CHECKS = 1;")
    [System.IO.File]::WriteAllText($LoadDataSqlPath, $LoadSqlBuilder.ToString(), [System.Text.UTF8Encoding]::new($false))

    Write-Host "Preparing pre-initialized MySQL seed with LOAD DATA. This one-time publisher step can take a long time..."
    Invoke-DockerCommandAllowFailure @("rm", "-f", $MysqlSeedContainer) | Out-Null

    docker run -d `
        --name $MysqlSeedContainer `
        -e "MYSQL_ROOT_PASSWORD=$MysqlSeedRootPassword" `
        -e "MYSQL_ROOT_HOST=%" `
        -e "MYSQL_DATABASE=$LocalMysqlDatabase" `
        -e "MYSQL_USER=musicweb" `
        -e "MYSQL_PASSWORD=$MysqlSeedUserPassword" `
        mysql:8.4 `
        --character-set-server=utf8mb4 `
        --collation-server=utf8mb4_unicode_ci `
        --default-time-zone=+08:00 `
        --max-allowed-packet=512M `
        --local-infile=1 `
        --innodb-flush-log-at-trx-commit=2 `
        --sync-binlog=0

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start temporary MySQL seed container."
    }

    $WaitRounds = 0
    while (-not (Test-SeedMysqlReady)) {
        Start-Sleep -Seconds 30
        $WaitRounds++

        $RunningState = docker inspect -f "{{.State.Running}}" $MysqlSeedContainer 2>$null
        if ($LASTEXITCODE -ne 0 -or $RunningState -ne "true") {
            docker logs --tail 120 $MysqlSeedContainer
            throw "Temporary MySQL seed container stopped before becoming ready."
        }

        if (($WaitRounds % 20) -eq 0) {
            Write-Host "Still importing release SQL into MySQL seed container... elapsed $([Math]::Round($WaitRounds / 2, 1)) minutes"
        }
    }

    Write-Host "Temporary MySQL is ready. Copying schema and exported data into container..."
    docker cp $SchemaDumpPath "${MysqlSeedContainer}:/tmp/musicweb-schema.sql"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy schema dump into temporary MySQL container."
    }

    docker cp $script:MysqlExportRoot "${MysqlSeedContainer}:/tmp/musicweb-export"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy tab export files into temporary MySQL container."
    }

    docker cp $LoadDataSqlPath "${MysqlSeedContainer}:/tmp/musicweb-load.sql"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy LOAD DATA script into temporary MySQL container."
    }

    Write-Host "Importing schema into temporary MySQL container..."
    docker exec $MysqlSeedContainer sh -c "mysql -uroot -p$MysqlSeedRootPassword $LocalMysqlDatabase < /tmp/musicweb-schema.sql"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to import schema into temporary MySQL container."
    }

    Write-Host "Loading exported data into temporary MySQL container..."
    docker exec $MysqlSeedContainer sh -c "mysql --local-infile=1 -uroot -p$MysqlSeedRootPassword < /tmp/musicweb-load.sql"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to load exported data into temporary MySQL container."
    }

    Write-Host "Verifying MySQL seed data..."
    foreach ($TableName in $CoreMysqlTables) {
        $EscapedTable = Escape-MysqlIdentifier $TableName
        $ExpectedCount = Invoke-LocalMysqlScalar "SELECT COUNT(*) FROM ``$LocalMysqlDatabase``.``$EscapedTable``;"
        $ActualCount = docker exec $MysqlSeedContainer mysql -uroot "-p$MysqlSeedRootPassword" -N -e "SELECT COUNT(*) FROM ``$LocalMysqlDatabase``.``$EscapedTable``;"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to verify MySQL seed table '$TableName'."
        }
        if ([int64]$ActualCount -ne [int64]$ExpectedCount) {
            throw "Seed table '$TableName' row count mismatch. expected=$ExpectedCount actual=$ActualCount"
        }
        Write-Host "  $TableName rows verified: $ActualCount"
    }

    Write-Host "MySQL seed import completed. Copying initialized datadir..."
    docker exec $MysqlSeedContainer mysql -uroot "-p$MysqlSeedRootPassword" -N -e "SELECT COUNT(*) FROM ``$LocalMysqlDatabase``.``songs``;"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to verify MySQL seed data."
    }

    docker stop $MysqlSeedContainer | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to stop temporary MySQL seed container."
    }

    docker cp "${MysqlSeedContainer}:/var/lib/mysql" $MysqlFastContext
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy MySQL seed datadir."
    }

    docker rm $MysqlSeedContainer | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to remove temporary MySQL seed container."
    }

    $CopiedMysqlSystemTable = Join-Path $MysqlFastContext "mysql\mysql"
    if (-not (Test-Path -LiteralPath $CopiedMysqlSystemTable)) {
        throw "Copied MySQL seed datadir is incomplete."
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
            $Line = [regex]::Replace($Line, $EmailPattern, "")
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
    $MysqlFastImage = "${Namespace}/musicweb-mysql-fast:${Tag}"
    New-MysqlFastBuildContext $MysqlFastImage

    Invoke-ReleaseDockerBuild "musicweb-web" "Project/MusicWeb/Dockerfile" "Project/MusicWeb"
    Invoke-ReleaseDockerBuild "musicweb-music-api" "Project/MusicWeb/src/main/webapp/Dockerfile.music-api" "Project/MusicWeb/src/main/webapp"
    Invoke-ReleaseDockerBuild "musicweb-qq-api" "Project/MusicWeb/src/main/webapp/MusicServer/qq_api/Dockerfile" "Project/MusicWeb/src/main/webapp/MusicServer/qq_api"
    Invoke-ReleaseDockerBuild "musicweb-unblock" "Project/MusicWeb/src/main/webapp/MusicServer/unblock/Dockerfile" "Project/MusicWeb/src/main/webapp/MusicServer/unblock"
    Invoke-ReleaseDockerBuild "musicweb-recommender" "Project/MusicMode/Dockerfile" "Project/MusicMode"
    Invoke-ReleaseDockerBuild "musicweb-data" "docker/release/data/Dockerfile" "docker/dist/release-data"
    Invoke-ReleaseDockerBuild "musicweb-mysql-fast" "docker/release/mysql-fast/Dockerfile" "docker/dist/mysql-fast-context"
}
finally {
    Pop-Location
    Invoke-DockerCommandAllowFailure @("rm", "-f", $MysqlSeedContainer) | Out-Null
    if (Test-Path -LiteralPath $ReleaseData) {
        $ResolvedReleaseData = (Resolve-Path -LiteralPath $ReleaseData).Path
        $ResolvedRoot = (Resolve-Path -LiteralPath $Root).Path
        if (-not $ResolvedReleaseData.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refuse to remove release data outside workspace: $ResolvedReleaseData"
        }
        Remove-Item -LiteralPath $ResolvedReleaseData -Recurse -Force
        Write-Host "Removed temporary release data context."
    }
    if (Test-Path -LiteralPath $MysqlFastContext) {
        $ResolvedMysqlFastContext = (Resolve-Path -LiteralPath $MysqlFastContext).Path
        $ResolvedRoot = (Resolve-Path -LiteralPath $Root).Path
        if (-not $ResolvedMysqlFastContext.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refuse to remove MySQL fast context outside workspace: $ResolvedMysqlFastContext"
        }
        Remove-Item -LiteralPath $ResolvedMysqlFastContext -Recurse -Force
        Write-Host "Removed temporary MySQL fast image context."
    }
    if (-not [string]::IsNullOrWhiteSpace($script:MysqlExportRoot)) {
        Remove-DirectorySafely -Path $script:MysqlExportRoot -ExpectedLeaf "mysql-export"
        Write-Host "Removed temporary local MySQL export directory."
    }
}

Write-Host "Release images built with namespace '$Namespace' and tag '$Tag'."
