# Safe disk cleanup for CuteUpdate1 - conservative Docker + caches (ASCII source)
$ErrorActionPreference = 'Continue'
$ReportPath = Join-Path $PSScriptRoot 'cleanup_report.txt'
$Log = [System.Collections.ArrayList]@()

function Log-Line($s) { [void]$Log.Add($s); Write-Host $s }

function Get-DirSizeBytes($path) {
    if (-not (Test-Path -LiteralPath $path)) { return 0 }
    try {
        return (Get-ChildItem -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
    } catch { return 0 }
}

function Remove-DirContentsSafe($path, [ref]$freedRef) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    $before = Get-DirSizeBytes $path
    Get-ChildItem -LiteralPath $path -Force -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop
        } catch {
            Log-Line ("  SKIP locked: {0}" -f $_.FullName)
        }
    }
    $after = Get-DirSizeBytes $path
    $freed = [math]::Max(0, $before - $after)
    $freedRef.Value += $freed
}

function Test-ProtectToken($text) {
    if ([string]::IsNullOrWhiteSpace($text)) { return $false }
    $t = $text.ToLowerInvariant()
    $patterns = @(
        'cute', 'support-bot', 'support_bot', 'supportbot', 'farming',
        'postgres', 'redis', 'mongo', 'mysql', 'cuteupdate1', 'cuteupdate',
        'cutebot', 'cutebase'
    )
    foreach ($p in $patterns) {
        if ($t -like "*$p*") { return $true }
    }
    return $false
}

$categories = @{}
function Add-Cat($name, $bytes) {
    if (-not $categories.ContainsKey($name)) { $categories[$name] = 0 }
    $categories[$name] += [long]$bytes
}

$freeBefore = (Get-PSDrive C).Free
Log-Line ("=== CuteUpdate1 Safe Cleanup {0} ===" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
Log-Line ("C free BEFORE GB: {0:N2}" -f ($freeBefore / 1GB))

$ProjectRoot = 'C:\Users\Asus\PycharmProjects\support-bot-main\CuteUpdate1'
$protectServices = @('postgres', 'api', 'bots')
$protectVolumes = @('postgres_data')
$protectImages = @('postgres:16-alpine')
$composeProjectNames = @(
    'cuteupdate1', 'cuteupdate', 'support-bot-main', 'support_bot_main'
)

$user = $env:USERPROFILE

$desktop = Join-Path $user 'Desktop'
foreach ($pat in @('CursorUserSetup*.exe', 'OpenJDK*.msi')) {
    Get-ChildItem -Path $desktop -Filter $pat -ErrorAction SilentlyContinue | ForEach-Object {
        $sz = $_.Length
        try {
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop
            Add-Cat 'Desktop installers' $sz
            Log-Line ("Removed desktop: {0} ({1:N1} MB)" -f $_.FullName, ($sz / 1MB))
        } catch {
            Log-Line ("SKIP desktop: {0}" -f $_.FullName)
        }
    }
}

$gfnCache = Join-Path $env:LOCALAPPDATA 'NVIDIA Corporation\GeForceNOW\CefCache'
if (Test-Path $gfnCache) {
    $f = 0L
    Remove-DirContentsSafe $gfnCache ([ref]$f)
    Add-Cat 'GeForceNOW cache' $f
    Log-Line ("GeForceNOW CefCache freed MB: {0:N1}" -f ($f / 1MB))
}

$epicBase = Join-Path $env:LOCALAPPDATA 'EpicGamesLauncher'
foreach ($sub in @('Saved\webcache', 'Saved\webcache_4147', 'Saved\Logs', 'Intermediate\WebCache')) {
    $p = Join-Path $epicBase $sub
    if (Test-Path $p) {
        $f = 0L
        Remove-DirContentsSafe $p ([ref]$f)
        Add-Cat 'Epic web/cache' $f
        Log-Line ("Epic {0} MB: {1:N1}" -f $sub, ($f / 1MB))
    }
}

$steam = 'C:\Program Files (x86)\Steam'
foreach ($sub in @('package', 'appcache', 'depotcache', 'logs', 'htmlcache')) {
    $p = Join-Path $steam $sub
    if (Test-Path $p) {
        $f = 0L
        if ($sub -eq 'package') {
            Get-ChildItem $p -Filter '*.tmp' -ErrorAction SilentlyContinue | ForEach-Object {
                $sz = $_.Length
                try {
                    Remove-Item $_.FullName -Force
                    Add-Cat 'Steam cache' $sz
                    $f += $sz
                } catch { }
            }
        } else {
            Remove-DirContentsSafe $p ([ref]$f)
        }
        Add-Cat 'Steam cache' $f
        Log-Line ("Steam\{0} MB: {1:N1}" -f $sub, ($f / 1MB))
    }
}

if (Test-Path 'C:\Temp') {
    $f = 0L
    Remove-DirContentsSafe 'C:\Temp' ([ref]$f)
    Add-Cat 'C Temp' $f
    Log-Line ("C:\Temp MB: {0:N1}" -f ($f / 1MB))
}

$cursorApp = Join-Path $env:APPDATA 'Cursor'
$cursorSkip = @('User', 'Backups', 'Crashpad')
Get-ChildItem $cursorApp -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notin $cursorSkip -and $_.Name -notlike 'state.vscdb*' } |
    ForEach-Object {
        $f = 0L
        Remove-DirContentsSafe $_.FullName ([ref]$f)
        if ($f -gt 0) {
            Add-Cat 'Cursor caches' $f
            Log-Line ("Cursor\{0} MB: {1:N1}" -f $_.Name, ($f / 1MB))
        }
    }

$cursorLocal = Join-Path $env:LOCALAPPDATA 'Cursor'
foreach ($sub in @('Cache', 'CachedData', 'Code Cache', 'GPUCache', 'logs', 'Crashpad', 'sentry')) {
    $p = Join-Path $cursorLocal $sub
    if (Test-Path $p) {
        $f = 0L
        Remove-DirContentsSafe $p ([ref]$f)
        Add-Cat 'Cursor caches' $f
    }
}

$projCursor = Join-Path $env:USERPROFILE '.cursor\projects\c-Users-Asus-PycharmProjects-support-bot-main-CuteUpdate1'
foreach ($sub in @('agent-tools', 'checkpoints')) {
    $p = Join-Path $projCursor $sub
    if (Test-Path $p) {
        $f = 0L
        Remove-DirContentsSafe $p ([ref]$f)
        Add-Cat 'Cursor project cache' $f
        Log-Line (".cursor\{0} MB: {1:N1}" -f $sub, ($f / 1MB))
    }
}

$pipCache = Join-Path $env:LOCALAPPDATA 'pip\cache'
if (Test-Path $pipCache) {
    $f = 0L
    Remove-DirContentsSafe $pipCache ([ref]$f)
    Add-Cat 'pip cache' $f
    Log-Line ("pip cache MB: {0:N1}" -f ($f / 1MB))
}

$npmCache = Join-Path $env:APPDATA 'npm-cache'
if (Test-Path $npmCache) {
    $f = 0L
    Remove-DirContentsSafe $npmCache ([ref]$f)
    Add-Cat 'npm cache' $f
}
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if ($npmCmd) {
    npm cache clean --force 2>&1 | ForEach-Object { Log-Line $_ }
}

$jbLocal = Join-Path $env:LOCALAPPDATA 'JetBrains'
if (Test-Path $jbLocal) {
    Get-ChildItem $jbLocal -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $logDir = Join-Path $_.FullName 'log'
        if (Test-Path $logDir) {
            $f = 0L
            Remove-DirContentsSafe $logDir ([ref]$f)
            Add-Cat 'JetBrains logs' $f
        }
    }
}

$dockerOk = $false
$protectedContainers = @()
$removedContainers = @()
$protectedVolumesListed = @()
$protectedImageIdCount = 0

try {
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch { }

if (-not $dockerOk) {
    Log-Line 'Docker daemon unavailable - skipped'
} else {
    Log-Line '--- Docker ---'
    $containersJson = docker ps -a --format '{{json .}}' 2>$null
    $allContainers = @()
    foreach ($line in $containersJson) {
        if ($line) { $allContainers += ($line | ConvertFrom-Json) }
    }

    $protectContainerIds = [System.Collections.Generic.HashSet[string]]::new()
    $protectImageIds = [System.Collections.Generic.HashSet[string]]::new()
    $protectVolumeNames = [System.Collections.Generic.HashSet[string]]::new()

    foreach ($v in $protectVolumes) {
        foreach ($proj in $composeProjectNames) {
            [void]$protectVolumeNames.Add("${proj}_${v}")
            [void]$protectVolumeNames.Add("${proj}-$v")
        }
        [void]$protectVolumeNames.Add($v)
    }

    foreach ($c in $allContainers) {
        $name = $c.Names
        $image = $c.Image
        $labels = $c.Labels
        $isRunning = ($c.State -eq 'running')
        $protect = $false

        if ($isRunning) { $protect = $true }
        if (Test-ProtectToken $name) { $protect = $true }
        if (Test-ProtectToken $image) { $protect = $true }
        if ($labels -match 'com.docker.compose.project') {
            if (Test-ProtectToken $labels) { $protect = $true }
            foreach ($svc in $protectServices) {
                if ($labels -match "com.docker.compose.service=$svc") { $protect = $true }
            }
        }
        foreach ($proj in $composeProjectNames) {
            if ($name -like "*$proj*") { $protect = $true }
        }

        if ($protect) {
            [void]$protectContainerIds.Add($c.ID)
            $protectedContainers += ("{0} ({1}) [{2}]" -f $name, $image, $c.State)
            if ($c.ImageID) { [void]$protectImageIds.Add($c.ImageID.Trim()) }
        }
    }

    $imagesJson = docker images --format '{{json .}}' 2>$null
    $allImages = @()
    foreach ($line in $imagesJson) {
        if ($line) { $allImages += ($line | ConvertFrom-Json) }
    }
    foreach ($img in $allImages) {
        $ref = "{0}:{1}" -f $img.Repository, $img.Tag
        if ($protectImages -contains $ref) {
            [void]$protectImageIds.Add($img.ID.Trim())
        }
        if (Test-ProtectToken $img.Repository) {
            [void]$protectImageIds.Add($img.ID.Trim())
        }
        foreach ($proj in $composeProjectNames) {
            if ($img.Repository -like "*$proj*") {
                [void]$protectImageIds.Add($img.ID.Trim())
            }
        }
    }

    $volList = docker volume ls --format '{{.Name}}' 2>$null
    foreach ($vn in $volList) {
        if ($protectVolumeNames.Contains($vn) -or (Test-ProtectToken $vn)) {
            [void]$protectVolumeNames.Add($vn)
            $protectedVolumesListed += $vn
        }
    }

    $protectedImageIdCount = $protectImageIds.Count
    Log-Line ("PROTECT containers: {0}" -f ($protectedContainers -join '; '))
    Log-Line ("PROTECT volumes: {0}" -f ($protectedVolumesListed -join ', '))
    Log-Line ("PROTECT image IDs: {0}" -f $protectedImageIdCount)

    docker builder prune -af 2>&1 | ForEach-Object { Log-Line $_ }
    docker image prune -f 2>&1 | ForEach-Object { Log-Line $_ }

    foreach ($c in $allContainers) {
        if ($protectContainerIds.Contains($c.ID)) { continue }
        if ($c.State -eq 'running') { continue }
        $name = $c.Names
        if (Test-ProtectToken $name) { continue }
        if (Test-ProtectToken $c.Image) { continue }
        Log-Line ("RM container: {0} ({1})" -f $name, $c.Image)
        docker rm $c.ID 2>&1 | ForEach-Object { Log-Line $_ }
        if ($LASTEXITCODE -eq 0) { $removedContainers += $name }
    }

    foreach ($img in $allImages) {
        $id = $img.ID.Trim()
        if ($protectImageIds.Contains($id)) { continue }
        if ($img.Repository -eq '<none>' -and $img.Tag -eq '<none>') {
            Log-Line ("RM dangling image {0}" -f $id)
            docker rmi $id 2>&1 | Out-Null
            continue
        }
        if (Test-ProtectToken $img.Repository) { continue }
        $inUse = $false
        foreach ($c in $allContainers) {
            if ($c.Image -like "$($img.Repository)*") { $inUse = $true; break }
        }
        if ($inUse) { continue }
        Log-Line ("RM unused image: {0}:{1}" -f $img.Repository, $img.Tag)
        docker rmi $id 2>&1 | Out-Null
    }
}

$composeValid = $false
$remainingProject = @()
if ($dockerOk) {
    Push-Location $ProjectRoot
    docker compose config 2>&1 | Out-Null
    $composeValid = ($LASTEXITCODE -eq 0)
    Pop-Location
    docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}' 2>$null | ForEach-Object {
        if (Test-ProtectToken $_) { $remainingProject += $_ }
    }
}

$stateDb = Join-Path $env:APPDATA 'Cursor\User\globalStorage\state.vscdb'
$stateDbSize = 0L
if (Test-Path $stateDb) { $stateDbSize = (Get-Item $stateDb).Length }

$freeAfter = (Get-PSDrive C).Free
$freedTotal = $freeAfter - $freeBefore

Log-Line ''
Log-Line '=== SUMMARY ==='
Log-Line ("C free BEFORE GB: {0:N2}" -f ($freeBefore / 1GB))
Log-Line ("C free AFTER GB: {0:N2}" -f ($freeAfter / 1GB))
Log-Line ("Disk delta GB: {0:N2} (MB: {1:N0})" -f ($freedTotal / 1GB), ($freedTotal / 1MB))
Log-Line 'Categories MB:'
foreach ($k in ($categories.Keys | Sort-Object)) {
    Log-Line ("  {0}: {1:N1}" -f $k, ($categories[$k] / 1MB))
}
Log-Line ("Docker removed containers: {0}" -f ($removedContainers -join ', '))
Log-Line ("docker compose config valid: {0}" -f $composeValid)
Log-Line 'Remaining project-related containers:'
$remainingProject | ForEach-Object { Log-Line ("  {0}" -f $_) }
Log-Line ("state.vscdb MB (untouched): {0:N0}" -f ($stateDbSize / 1MB))

$utf8 = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText($ReportPath, ($Log -join [Environment]::NewLine), $utf8)

# Russian summary file for user
$ru = @(
    "Otchyot ochistki CuteUpdate1"
    ("Data: {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm'))
    ("C svobodno DO: {0:N2} GB" -f ($freeBefore / 1GB))
    ("C svobodno POSLE: {0:N2} GB" -f ($freeAfter / 1GB))
    ("Osvobozhdeno na C: {0:N2} GB ({1:N0} MB)" -f ($freedTotal / 1GB), ($freedTotal / 1MB))
    ""
    "Kategorii (MB):"
)
foreach ($k in ($categories.Keys | Sort-Object)) {
    $ru += ("  - {0}: {1:N1} MB" -f $k, ($categories[$k] / 1MB))
}
$ru += @(
    ""
    "Docker ZASHCHISHCHENO konteynery:"
)
$protectedContainers | ForEach-Object { $ru += ("  * {0}" -f $_) }
$ru += @(
    "Docker ZASHCHISHCHENO tomа: " + ($protectedVolumesListed -join ', ')
    "Docker UDALENO konteynery: " + ($(if ($removedContainers.Count) { $removedContainers -join ', ' } else { '(net)' }))
    ("docker-compose valid: {0}" -f $composeValid)
    "Ostavshiesya project konteynery:"
)
$remainingProject | ForEach-Object { $ru += ("  - {0}" -f $_) }
$ru += @(
    ""
    ("state.vscdb razmer (NE trogali): {0:N2} GB" -f ($stateDbSize / 1GB))
)
if ($freeAfter -lt 10GB -and $stateDbSize -gt 500MB) {
    $ru += "Primechanie: na C malo mesta; state.vscdb mozhet byt bolshim."
}

$ruPath = Join-Path $PSScriptRoot 'cleanup_report_ru.txt'
[System.IO.File]::WriteAllText($ruPath, ($ru -join [Environment]::NewLine), $utf8)
