# ============================================================
#  Cute - full stack launcher with live status dashboard
#  Order:  DB config -> SSH tunnel -> PostgreSQL test -> Redis
#          -> API (:8000) -> WebApp Vite (:5173)
#          -> main.py (main bot + payment) -> farm bots (game/admin/support)
#          -> ngrok (optional)
#  Every component is logged to .\logs\<name>.log and its real
#  start/fail status is shown in a final dashboard.
#  Run:  start_all.bat   or   .\start-all.ps1
# ============================================================

param(
    [switch]$SkipNgrok,
    [switch]$SkipVite,
    [switch]$SkipApi,
    [switch]$SkipMainBot,
    [switch]$SkipFarmBots,
    [int]$PauseBetweenSteps = 1
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$ServerDir = Join-Path $Root 'server'
$LogDir = Join-Path $Root 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# -------------------- status registry --------------------
$script:Components = [System.Collections.Generic.List[object]]::new()

function Set-ComponentStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Status,   # OK | RUN | FAIL | TIMEOUT | SKIP | WARN
        [string]$Detail = '',
        [string]$Log = ''
    )
    $existing = $script:Components | Where-Object { $_.Name -eq $Name } | Select-Object -First 1
    if ($existing) {
        $existing.Status = $Status
        $existing.Detail = $Detail
        if ($Log) { $existing.Log = $Log }
    } else {
        $script:Components.Add([pscustomobject]@{ Name = $Name; Status = $Status; Detail = $Detail; Log = $Log })
    }
}

# -------------------- pretty output helpers --------------------
function Write-Head { param([string]$Text)
    Write-Host ''
    Write-Host '================================================' -ForegroundColor White
    Write-Host "  $Text" -ForegroundColor White
    Write-Host '================================================' -ForegroundColor White
}
function Write-Step { param([string]$Text) Write-Host ''; Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-OK   { param([string]$Text) Write-Host "   [OK]   $Text" -ForegroundColor Green }
function Write-Warn { param([string]$Text) Write-Host "   [WARN] $Text" -ForegroundColor Yellow }
function Write-Fail { param([string]$Text) Write-Host "   [FAIL] $Text" -ForegroundColor Red }
function Write-Info { param([string]$Text) Write-Host "   $Text" -ForegroundColor DarkGray }

# Big, impossible-to-miss banner showing which database the whole stack uses.
# ASCII-only strings: PowerShell 5.1 on Windows may misread UTF-8 without BOM.
function Write-ModeBanner {
    param([string]$Mode, [string]$Target)
    if ($Mode -eq 'main') {
        $fg = 'Black'; $bg = 'Red'
        $where = if ($Target -eq 'remote') { 'CuteHost PROD @ 127.0.0.1:15432 (SSH)' } else { 'local PostgreSQL @ :5432' }
        $warn = '!!! MAIN DATABASE - LIVE PLAYERS - CHANGES ARE REAL !!!'
    } else {
        $fg = 'Black'; $bg = 'Green'
        $where = 'local cutebase @ localhost:5432 (no SSH)'
        $warn = 'TEST DATABASE - safe sandbox'
    }
    $bar = ('#' * 64)
    Write-Host ''
    Write-Host ("  $bar") -ForegroundColor $bg
    Write-Host ("  ##   APP_MODE = $($Mode.ToUpper())    (MAIN_DB_TARGET = $Target)") -ForegroundColor $fg -BackgroundColor $bg
    Write-Host ("  ##   DB: $where") -ForegroundColor $fg -BackgroundColor $bg
    Write-Host ("  ##   $warn") -ForegroundColor $fg -BackgroundColor $bg
    Write-Host ("  $bar") -ForegroundColor $bg
    Write-Host ''
    Write-Host '   Switch DB: set-mode.bat test  |  set-mode.bat main' -ForegroundColor DarkGray
}

function Status-Color {
    param([string]$Status)
    switch ($Status) {
        'OK'      { return 'Green' }
        'RUN'     { return 'Green' }
        'FAIL'    { return 'Red' }
        'TIMEOUT' { return 'Yellow' }
        'WARN'    { return 'Yellow' }
        'SKIP'    { return 'DarkGray' }
        default   { return 'Gray' }
    }
}

function Show-Dashboard {
    Write-Host ''
    Write-Host '================= SYSTEM STATUS =================' -ForegroundColor White
    foreach ($c in $script:Components) {
        $color = Status-Color $c.Status
        $line = '{0,-24} {1,-8} {2}' -f $c.Name, $c.Status, $c.Detail
        Write-Host ("  " + $line) -ForegroundColor $color
    }
    Write-Host '================================================' -ForegroundColor White
    $failed = @($script:Components | Where-Object { $_.Status -in @('FAIL', 'TIMEOUT') })
    if ($failed.Count -gt 0) {
        Write-Host ''
        Write-Host '  Problems detected. Check the logs:' -ForegroundColor Yellow
        foreach ($f in $failed) {
            if ($f.Log) { Write-Host "   - $($f.Name): $($f.Log)" -ForegroundColor Yellow }
            else { Write-Host "   - $($f.Name): see its window" -ForegroundColor Yellow }
        }
    }
    Write-Host ''
}

# -------------------- python resolution --------------------
function Test-PythonExe {
    param([string]$ExePath)
    if (-not (Test-Path $ExePath)) { return $false }
    try {
        $proc = Start-Process -FilePath $ExePath -ArgumentList @('-c', 'import sys') `
            -Wait -PassThru -WindowStyle Hidden -ErrorAction Stop
        return $proc.ExitCode -eq 0
    } catch { return $false }
}

# Root python (for main.py + helper scripts). Prefer root venv, then py -3, then python.
$script:RootPyExe = $null
$script:RootPyArgs = @('-X', 'utf8', '-W', 'ignore::UserWarning')
$venvPy = Join-Path $Root 'venv\Scripts\python.exe'
if (Test-PythonExe $venvPy) {
    $script:RootPyExe = $venvPy
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $script:RootPyExe = 'py'
    $script:RootPyArgs = @('-3', '-X', 'utf8', '-W', 'ignore::UserWarning')
} else {
    $script:RootPyExe = 'python'
}

function Invoke-RootPython {
    param([Parameter(Mandatory = $true)][string[]]$ScriptArgs)
    & $script:RootPyExe @($script:RootPyArgs + $ScriptArgs)
}

# -------------------- env readers --------------------
function Read-EnvValue {
    param([string]$Key, [string]$Default = '')
    $val = ''
    foreach ($file in @((Join-Path $Root '.env'), (Join-Path $ServerDir '.env'))) {
        if (-not (Test-Path $file)) { continue }
        $hit = Select-String -Path $file -Pattern ("^\s*" + [regex]::Escape($Key) + "\s*=\s*(.+)$") | Select-Object -First 1
        if ($hit) { $val = $hit.Matches.Groups[1].Value.Trim().Trim('"').Trim("'") }
    }
    if ($val) { return $val }
    return $Default
}

# Read a string literal (VAR = "value") from bot/config/config.py WITHOUT importing
# Python. This is the SAME master switch the bot/server read, so the launcher can
# never disagree with the database the stack actually connects to.
$script:ConfigPyFile = Join-Path $Root 'bot\config\config.py'
function Read-ConfigPyVar {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Test-Path $script:ConfigPyFile)) { return '' }
    try {
        $hit = Select-String -Path $script:ConfigPyFile `
            -Pattern ('^\s*' + [regex]::Escape($Name) + '\s*=\s*["'']([^"'']*)["'']') |
            Select-Object -First 1
    } catch { return '' }
    if ($hit) { return $hit.Matches.Groups[1].Value.Trim() }
    return ''
}

# Resolve profile (test/main) and location (local/remote) EXACTLY like
# bot/config/db_config.py:
#   1) config.py  DATABASE_MODE / DATABASE_LOCATION   (master switch, wins)
#   2) .env       APP_MODE / DB_LOCATION / MAIN_DB_TARGET   (fallback)
#   3) auto       (main -> remote, test -> local)
function Resolve-DbSelection {
    $modeAliases = @{ 'main' = 'main'; 'work' = 'main'; 'live' = 'main'; 'prod' = 'main'; 'production' = 'main';
        'test' = 'test'; 'dev' = 'test'; 'local' = 'test'
    }
    $locAliases = @{ 'local' = 'local'; 'localhost' = 'local'; 'pg17' = 'local';
        'remote' = 'remote'; 'cutehost' = 'remote'; 'ssh' = 'remote'; 'server' = 'remote'
    }

    $mode = ''; $modeSrc = ''
    $cfgMode = (Read-ConfigPyVar 'DATABASE_MODE').ToLower()
    if ($modeAliases.ContainsKey($cfgMode)) { $mode = $modeAliases[$cfgMode]; $modeSrc = 'config.py' }
    if (-not $mode) {
        $envMode = (Read-EnvValue 'APP_MODE').ToLower()
        if ($modeAliases.ContainsKey($envMode)) { $mode = $modeAliases[$envMode]; $modeSrc = '.env APP_MODE' }
    }
    if (-not $mode) { $mode = 'test'; $modeSrc = 'default' }

    $loc = ''; $locSrc = ''
    $cfgLoc = (Read-ConfigPyVar 'DATABASE_LOCATION').ToLower()
    if ($locAliases.ContainsKey($cfgLoc)) { $loc = $locAliases[$cfgLoc]; $locSrc = 'config.py' }
    if (-not $loc) {
        $envLoc = (Read-EnvValue 'DB_LOCATION').ToLower()
        if ($locAliases.ContainsKey($envLoc)) { $loc = $locAliases[$envLoc]; $locSrc = '.env DB_LOCATION' }
    }
    if (-not $loc) {
        $envTgt = (Read-EnvValue 'MAIN_DB_TARGET').ToLower()
        if ($locAliases.ContainsKey($envTgt)) { $loc = $locAliases[$envTgt]; $locSrc = '.env MAIN_DB_TARGET' }
    }
    if (-not $loc) {
        if ($mode -eq 'main') { $loc = 'remote' } else { $loc = 'local' }
        $locSrc = 'auto'
    }

    return [pscustomobject]@{ Mode = $mode; Target = $loc; ModeSource = $modeSrc; TargetSource = $locSrc }
}

# -------------------- process / port helpers --------------------
function Stop-StaleListener {
    param([int]$Port, [string[]]$ProcessNames = @('node', 'python'))
    for ($round = 0; $round -lt 3; $round++) {
        $conns = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
        if ($conns.Count -eq 0) { return }
        foreach ($c in $conns) {
            $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and ($ProcessNames -contains $proc.ProcessName)) {
                Write-Info "Stopping stale $($proc.ProcessName) on port $Port (PID $($c.OwningProcess))"
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Seconds 2
    }
}

function Wait-HttpOk {
    param([Parameter(Mandatory = $true)][string]$Url, [int]$TimeoutSec = 90, [string]$Label = $Url)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    Write-Info "waiting for $Label ..."
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return $true }
        } catch { }
        Start-Sleep -Seconds 1
    }
    return $false
}

# Start a component in its own window with clean Python logging (scripts/run-with-log.ps1).
# We generate a tiny no-parameter launcher that SPLATS a hashtable into the runner.
# Splatting binds by name with no command-line re-parsing, so values that start
# with '-' (like "-X utf8 -W ignore::UserWarning") can never be mis-bound.
function Ps-SingleQuote {
    param([string]$Value)
    return "'" + ($Value -replace "'", "''") + "'"
}

function Start-LoggedWindow {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string]$PythonArgs,
        [Parameter(Mandatory = $true)][string]$Script,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][string]$LauncherPath,
        [hashtable]$ExtraEnv = @{}
    )
    $runner = Join-Path $Root 'scripts\run-with-log.ps1'
    $tunnelReady = "$($env:CF_TUNNEL_READY)"
    $envLines = @(
        ('$env:CF_TUNNEL_READY = ' + (Ps-SingleQuote $tunnelReady))
    )
    foreach ($ek in $ExtraEnv.Keys) {
        $envLines += ('$env:' + $ek + ' = ' + (Ps-SingleQuote "$($ExtraEnv[$ek])"))
    }
    $launcher = @(
        '$ErrorActionPreference = ''Continue'''
    ) + $envLines + @(
        '$params = @{',
        ('    Title            = ' + (Ps-SingleQuote $Title)),
        ('    WorkingDirectory = ' + (Ps-SingleQuote $WorkingDirectory)),
        ('    PythonExe        = ' + (Ps-SingleQuote $PythonExe)),
        ('    PythonArgs       = ' + (Ps-SingleQuote $PythonArgs)),
        ('    Script           = ' + (Ps-SingleQuote $Script)),
        ('    LogPath          = ' + (Ps-SingleQuote $LogPath)),
        '}',
        ('& ' + (Ps-SingleQuote $runner) + ' @params')
    ) -join "`r`n"
    Set-Content -LiteralPath $LauncherPath -Value $launcher -Encoding UTF8
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', $LauncherPath) | Out-Null
    Write-Info "window: $Title  |  log: $LogPath"
}

# Simple visible window (no log tee) - for API/Vite/ngrok that have their own checks.
function Start-DevWindow {
    param([string]$Title, [string]$WorkingDirectory, [string]$Command)
    $inner = '$Host.UI.RawUI.WindowTitle = ''' + $Title + '''; Set-Location -LiteralPath ''' + $WorkingDirectory + '''; $env:CF_TUNNEL_READY = ''' + "$($env:CF_TUNNEL_READY)" + '''; ' + $Command
    Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $inner) | Out-Null
}

# Poll a log file until a success, partial, or failure marker appears.
function Wait-LogMarker {
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [string[]]$SuccessPatterns = @(),
        [string[]]$PartialPatterns = @(),
        [string[]]$FailPatterns = @(),
        [int]$TimeoutSec = 90,
        [string]$Label = 'component',
        [switch]$ReturnPartialEarly
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $lastTick = [datetime]::MinValue
    $sawPartial = $false
    Write-Info "waiting for $Label (up to ${TimeoutSec}s) ..."
    while ((Get-Date) -lt $deadline) {
        $text = $null
        if (Test-Path $LogPath) {
            try { $text = Get-Content -LiteralPath $LogPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue } catch { $text = $null }
        }
        if ($text) {
            foreach ($fp in $FailPatterns) {
                if ($fp -and ($text -match $fp)) { return 'FAIL' }
            }
            foreach ($sp in $SuccessPatterns) {
                if ($sp -and ($text -match $sp)) { return 'OK' }
            }
            foreach ($pp in $PartialPatterns) {
                if ($pp -and ($text -match $pp)) {
                    $sawPartial = $true
                    if ($ReturnPartialEarly) { return 'PARTIAL' }
                }
            }
            if (((Get-Date) - $lastTick).TotalSeconds -ge 10) {
                $tail = (Get-Content -LiteralPath $LogPath -Tail 1 -Encoding UTF8 -ErrorAction SilentlyContinue)
                if ($tail) { Write-Info "$Label ... $tail" }
                $lastTick = Get-Date
            }
        }
        Start-Sleep -Milliseconds 400
    }
    if ($sawPartial) { return 'PARTIAL' }
    return 'TIMEOUT'
}

function Ensure-SshTunnel {
    param([int]$TimeoutSec = 120)
    if ([bool](Get-NetTCPConnection -LocalPort 15432 -State Listen -ErrorAction SilentlyContinue)) {
        return $true
    }
    $tunnelScript = Join-Path $Root 'scripts\start-ssh-tunnel.ps1'
    if (-not (Test-Path $tunnelScript)) {
        Write-Warn 'scripts\start-ssh-tunnel.ps1 not found'
        return $false
    }
    Write-Info 'starting SSH tunnel (plink, password from .env)...'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $tunnelScript -Background -Quiet
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if ([bool](Get-NetTCPConnection -LocalPort 15432 -State Listen -ErrorAction SilentlyContinue)) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

# Real TCP connect to 127.0.0.1 (IPv4) - exactly what asyncpg does. A plain
# "Listen socket present" check can lie (IPv6-only bind, or a dying/zombie
# postmaster whose socket lingers), which is how a stale listener made step 2
# report "listening" while step 3 got "connection refused".
function Test-TcpUp {
    param([int]$Port = 5432)
    $client = $null
    try { $client = New-Object System.Net.Sockets.TcpClient; $client.Connect('127.0.0.1', $Port); return $true }
    catch { return $false }
    finally { if ($client) { $client.Close() } }
}

# Bring up the LOCAL PostgreSQL on $Port ROBUSTLY (inline; no external file, no
# admin/UAC, no base64 - so antivirus has nothing to quarantine):
#   1) already reachable (real TCP connect)? -> done
#   2) plain Start-Service (instant if this window happens to be elevated; if it
#      needs admin we just fall through, no prompt)
#   3) pg_ctl start - the primary path: no admin, detached, and started from THIS
#      long-lived launcher process so PostgreSQL stays up for the whole session
# NEVER a console-child postgres.exe (that dies on Ctrl+C / window close with
# 0xC000013A and breaks live connections). Returns $true if reachable afterwards.
function Ensure-LocalPostgres {
    param(
        [int]$Port = 5432,
        [int]$TimeoutSec = 30,
        [string]$ServiceName = 'postgresql-x64-17',
        [string]$PgHome = 'C:\Program Files\PostgreSQL\17'
    )
    if (Test-TcpUp -Port $Port) { return $true }

    # Best-effort: start the Windows service (instant if this window is elevated).
    # No UAC pop-up - if it needs admin we simply fall through to pg_ctl, which
    # needs no admin and detaches from the console.
    $svc = $null
    if ($ServiceName) { $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue }
    if (-not $svc) {
        $svc = Get-Service -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like 'postgresql*' } | Select-Object -First 1
    }
    if ($svc -and $svc.Status -ne 'Running') {
        Write-Info "starting Windows service '$($svc.Name)'..."
        try { Start-Service -Name $svc.Name -ErrorAction Stop }
        catch { Write-Info "service needs admin - using pg_ctl instead ($($_.Exception.Message))" }
        $svcDeadline = (Get-Date).AddSeconds(6)
        while ((Get-Date) -lt $svcDeadline) {
            if (Test-TcpUp -Port $Port) { return $true }
            Start-Sleep -Milliseconds 500
        }
    }

    # Primary robust path: pg_ctl start - no admin, detached from the console, so
    # it survives the launcher window closing (unlike a `start /B postgres.exe`
    # child, which dies with 0xC000013A on Ctrl+C / window close).
    $pgctl = Join-Path $PgHome 'bin\pg_ctl.exe'
    $data = Join-Path $PgHome 'data'
    if ((Test-Path -LiteralPath $pgctl) -and (Test-Path -LiteralPath (Join-Path $data 'postgresql.conf'))) {
        $logDir = Join-Path $data 'log'
        if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
        Write-Info 'starting PostgreSQL via pg_ctl (detached, no admin needed)...'
        try {
            & $pgctl start -D "$data" -l (Join-Path $logDir 'pg_ctl_start.log') -w -t $TimeoutSec 2>&1 |
                ForEach-Object { Write-Info "$_" }
        } catch { Write-Info "pg_ctl error: $($_.Exception.Message)" }
        $deadline = (Get-Date).AddSeconds($TimeoutSec)
        while ((Get-Date) -lt $deadline) {
            if (Test-TcpUp -Port $Port) { return $true }
            Start-Sleep -Milliseconds 500
        }
    } else {
        Write-Info "pg_ctl not found under '$PgHome' - cannot auto-start PostgreSQL"
    }
    return (Test-TcpUp -Port $Port)
}

function Read-RedisEndpoint {
    $rhost = Read-EnvValue 'REDIS_HOST' '127.0.0.1'
    $rport = Read-EnvValue 'REDIS_PORT' '6379'
    $url = Read-EnvValue 'REDIS_URL' ''
    if ($url) {
        try {
            $u = [uri]$url
            if ($u.Host) { $rhost = $u.Host }
            if ($u.Port -gt 0) { $rport = "$($u.Port)" }
        } catch { }
    }
    return [pscustomobject]@{ Host = $rhost; Port = [int]$rport }
}

function Ensure-Redis {
    param([string]$RedisHost = '127.0.0.1', [int]$Port = 6379, [int]$TimeoutSec = 30)
    $script = Join-Path $Root 'scripts\ensure-redis.ps1'
    if (-not (Test-Path $script)) {
        Write-Warn 'scripts\ensure-redis.ps1 not found'
        return $false
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script -RedisHost $RedisHost -Port $Port -TimeoutSec $TimeoutSec
    return ($LASTEXITCODE -eq 0)
}

# ============================================================
#                         START
# ============================================================
Write-Head 'Cute full stack (main bot + API + WebApp + farm bots)'
Write-Host "Project: $Root" -ForegroundColor DarkGray
Write-Host "Logs:    $LogDir" -ForegroundColor DarkGray

$dbSel = Resolve-DbSelection
$appMode = $dbSel.Mode
$mainTarget = $dbSel.Target
Write-ModeBanner -Mode $appMode -Target $mainTarget
Write-Host ("   DB switch source: DATABASE_MODE <- $($dbSel.ModeSource) | DATABASE_LOCATION <- $($dbSel.TargetSource)") -ForegroundColor DarkGray
Write-Host '   (master switch = bot\config\config.py; .env is fallback only)' -ForegroundColor DarkGray

# Redis endpoint is shared with every child process (bot + API + farm bots),
# so the whole stack talks to exactly one Redis instance.
$redis = Read-RedisEndpoint
$env:REDIS_HOST = $redis.Host
$env:REDIS_PORT = "$($redis.Port)"
Write-Host "Redis: $($redis.Host):$($redis.Port)" -ForegroundColor DarkGray
if ($script:RootPyExe -eq $venvPy) { Write-Host "Root Python: $venvPy" -ForegroundColor DarkGray }
else { Write-Host "Root Python: $($script:RootPyExe) $($script:RootPyArgs -join ' ')" -ForegroundColor DarkGray }

if (-not (Test-Path (Join-Path $Root '.env'))) {
    Write-Fail 'Root .env not found. Cannot continue.'
    Set-ComponentStatus -Name 'Config .env' -Status 'FAIL' -Detail 'root .env missing'
    Show-Dashboard
    exit 1
}
Set-ComponentStatus -Name 'Config .env' -Status 'OK' -Detail "APP_MODE=$appMode target=$mainTarget"

# ---------- 1) Unified DB config check ----------
Write-Step '1/9  Unified DB config (bot == WebApp)'
Invoke-RootPython -ScriptArgs @( (Join-Path $Root 'scripts\verify_unified_db.py') )
if ($LASTEXITCODE -ne 0) {
    Write-Fail 'bot and WebApp point to different databases. Fix .env / server/.env.'
    Set-ComponentStatus -Name 'DB config' -Status 'FAIL' -Detail 'bot != server config'
    Show-Dashboard
    exit 1
}
Write-OK 'bot and WebApp share one DB config'
Set-ComponentStatus -Name 'DB config' -Status 'OK' -Detail 'unified'

# ---------- 2) Database link: SSH tunnel (remote) or local PostgreSQL ----------
# The tunnel is needed whenever the LOCATION is remote, for ANY profile
# (test/remote hits the same CuteHost DB as main/remote, just with dev-auth flags).
if ($mainTarget -eq 'remote') {
    Write-Step '2/9  SSH tunnel to CuteHost :15432'
    if (Ensure-SshTunnel) {
        Write-OK 'SSH tunnel is up on :15432'
        Set-ComponentStatus -Name 'DB link' -Status 'OK' -Detail 'SSH tunnel 127.0.0.1:15432'
        $env:CF_TUNNEL_READY = '1'
    } else {
        Write-Fail 'SSH tunnel could not open on :15432 (check SSH_PASSWORD in .env)'
        Set-ComponentStatus -Name 'DB link' -Status 'FAIL' -Detail 'SSH tunnel :15432 not listening'
        Show-Dashboard
        exit 1
    }
} else {
    Write-Step '2/9  Local PostgreSQL (:5432, no SSH)'
    if (Ensure-LocalPostgres -Port 5432) {
        Write-OK 'local PostgreSQL is listening on :5432'
        Set-ComponentStatus -Name 'DB link' -Status 'OK' -Detail "local $appMode :5432 (no tunnel)"
    } else {
        Write-Warn 'nothing is listening on :5432 - local PostgreSQL is not running'
        Write-Info 'start it with  start-0-postgres-cutebase.bat  (PostgreSQL 17 + cutebase)'
        Write-Info 'or use the server DB instead:  set-mode.bat main   (CuteHost via SSH)'
        Set-ComponentStatus -Name 'DB link' -Status 'WARN' -Detail 'local :5432 not listening'
    }
}

# ---------- 3) PostgreSQL connection test (with DB debug) ----------
Write-Step '3/9  PostgreSQL connection test'
$env:DB_TUNNEL_SKIP_WAIT = '1'
$dbTestLog = Join-Path $LogDir 'db-test.log'

function Invoke-DbTest {
    Invoke-RootPython -ScriptArgs @( (Join-Path $Root 'scripts\test_db_connection.py') ) 2>&1 |
        Tee-Object -FilePath $dbTestLog | ForEach-Object { Write-Host "   $_" -ForegroundColor DarkGray }
    return $LASTEXITCODE
}

$dbTestExit = Invoke-DbTest

# LOCAL fallback: if the local DB test fails, run the project's own local-DB
# bring-up (PostgreSQL 17 + cutebase on :5432) and retry once, so `start_all.bat`
# is one click for test/local. Skipped for remote (that path uses the SSH tunnel).
if ($dbTestExit -ne 0 -and $mainTarget -ne 'remote') {
    $pgFix = Join-Path $Root 'start-0-postgres-cutebase.bat'
    if (Test-Path $pgFix) {
        Write-Warn 'local DB test failed - bringing up local PostgreSQL 17 + cutebase...'
        Write-Info "running: $pgFix nopause"
        & $pgFix nopause
        Write-Info 'retrying PostgreSQL connection test...'
        $dbTestExit = Invoke-DbTest
    }
}

$dbLine = (Get-Content -LiteralPath $dbTestLog -Raw -ErrorAction SilentlyContinue)
$dbUsers = ''
if ($dbLine -match 'users=(\d+)') { $dbUsers = "users=$($Matches[1])" }
$via = if ($mainTarget -eq 'remote') { 'via SSH :15432' } else { 'local :5432' }
if ($dbTestExit -eq 0) {
    Write-OK "PostgreSQL reachable ($appMode / $via) $dbUsers"
    Set-ComponentStatus -Name 'PostgreSQL' -Status 'OK' -Detail "$appMode $via $dbUsers" -Log $dbTestLog
} else {
    Write-Fail 'PostgreSQL connection failed - see the diagnosis above and logs\db-test.log.'
    if ($mainTarget -eq 'remote') {
        Write-Info 'remote: check SSH tunnel :15432 and DB_PASSWORD_MAIN in .env.'
    } else {
        Write-Info 'local: run start-0-postgres-cutebase.bat manually, or switch to server DB: set-mode.bat main'
    }
    Set-ComponentStatus -Name 'PostgreSQL' -Status 'FAIL' -Detail "$appMode $via - connection failed" -Log $dbTestLog
    Show-Dashboard
    exit 1
}

# ---------- 4) Redis cache (auto-start, required for speed) ----------
Write-Step '4/9  Redis cache (auto-start)'
Write-Info 'probing 127.0.0.1:6379 (max ~20s; install Memurai if missing)...'
$redisRequired = ((Read-EnvValue 'REDIS_REQUIRED' 'false').ToLower() -in @('1', 'true', 'yes', 'on'))
if (Ensure-Redis -RedisHost $redis.Host -Port $redis.Port -TimeoutSec 20) {
    Write-OK "Redis is ready on $($redis.Host):$($redis.Port)"
    Set-ComponentStatus -Name 'Redis' -Status 'OK' -Detail "$($redis.Host):$($redis.Port)"
} elseif ($redisRequired) {
    Write-Fail 'Redis is REQUIRED (REDIS_REQUIRED=true) but could not be started.'
    Set-ComponentStatus -Name 'Redis' -Status 'FAIL' -Detail 'not reachable, REDIS_REQUIRED=true'
    Show-Dashboard
    exit 1
} else {
    Write-Warn 'Redis not available - stack will run in fallback (slower cache/snapshots).'
    Set-ComponentStatus -Name 'Redis' -Status 'WARN' -Detail 'fallback (install Memurai/Docker)'
}
Start-Sleep -Seconds $PauseBetweenSteps

# ---------- 5) API server (FastAPI :8000) ----------
Stop-StaleListener -Port 8000 -ProcessNames @('python')
Stop-StaleListener -Port 5173 -ProcessNames @('node')

if (-not $SkipApi) {
    Write-Step '5/9  API server (FastAPI :8000)'
    Start-DevWindow -Title 'CF API :8000' -WorkingDirectory $ServerDir -Command '.\start-server.ps1'
    $apiTimeout = if ($appMode -eq 'main') { 180 } else { 90 }
    if (Wait-HttpOk -Url 'http://127.0.0.1:8000/health' -TimeoutSec $apiTimeout -Label 'API /health') {
        Write-OK 'API is answering on http://127.0.0.1:8000/health'
        Set-ComponentStatus -Name 'API server' -Status 'OK' -Detail 'http://127.0.0.1:8000'
    } else {
        Write-Warn 'API did not answer in time - check the CF API :8000 window'
        Set-ComponentStatus -Name 'API server' -Status 'TIMEOUT' -Detail 'no /health response'
    }
    Start-Sleep -Seconds $PauseBetweenSteps
} else {
    Write-Step '5/9  API server (skipped)'
    Set-ComponentStatus -Name 'API server' -Status 'SKIP' -Detail '-SkipApi'
}

# ---------- 6) WebApp frontend (Vite preview :5173) ----------
# ВАЖНО: раздаём ПРОДАКШН-СБОРКУ (preview), а не dev. В dev Telegram WebView
# (особенно на телефоне) кэширует каждый .jsx-модуль отдельно, из-за чего на
# устройство попадает мешанина старого и нового кода и панель выкидывает на вход.
# Preview отдаёт один бандл с хэшем в имени: при любом изменении кода имя файла
# меняется, и кэш физически не может подсунуть старую версию. start-preview.ps1
# сам пересобирает проект (npm run build) перед запуском.
if (-not $SkipVite) {
    Write-Step '6/9  WebApp frontend (preview /production build/ :5173)'
    Start-DevWindow -Title 'CF Vite :5173' -WorkingDirectory $Root -Command '.\start-preview.ps1'
    # Сборка может занять до пары минут — ждём дольше, чем для dev.
    if (Wait-HttpOk -Url 'http://127.0.0.1:5173/' -TimeoutSec 240 -Label 'Vite preview :5173') {
        Write-OK 'WebApp is serving (production build) on http://127.0.0.1:5173/'
        Set-ComponentStatus -Name 'WebApp (Vite)' -Status 'OK' -Detail 'preview http://127.0.0.1:5173/'
    } else {
        Write-Warn 'Vite preview did not answer in time - check the CF Vite :5173 window (build may still run)'
        Set-ComponentStatus -Name 'WebApp (Vite)' -Status 'TIMEOUT' -Detail 'no response (build?)'
    }
    Start-Sleep -Seconds $PauseBetweenSteps
} else {
    Write-Step '6/9  WebApp frontend (skipped)'
    Set-ComponentStatus -Name 'WebApp (Vite)' -Status 'SKIP' -Detail '-SkipVite'
}

# ---------- 7) main.py (main bot + payment bot) ----------
if (-not $SkipMainBot) {
    Write-Step '7/9  Main bot (main.py: main + payment)'
    $mainLog = Join-Path $LogDir 'main-bot.log'
    $mainPyArgs = ($script:RootPyArgs -join ' ')
    Start-LoggedWindow -Title 'CF Main bot (main.py)' -WorkingDirectory $Root `
        -PythonExe $script:RootPyExe -PythonArgs $mainPyArgs -Script 'main.py' -LogPath $mainLog `
        -LauncherPath (Join-Path $LogDir '_run-main-bot.ps1')
    $mainStatus = Wait-LogMarker -LogPath $mainLog -Label 'main bot' -TimeoutSec 360 `
        -SuccessPatterns @('background task started', 'startup inner begin', 'Run polling for bot') `
        -PartialPatterns @('\[MODERATION\]', '\[DB\] APP_MODE=', 'target=main/cutebase', 'Server resent the older message') `
        -FailPatterns @('\[DB\]\[FATAL\]', 'Traceback \(most recent call last\)[\s\S]{0,800}main\.py', 'ImportError:', 'ModuleNotFoundError:')
    switch ($mainStatus) {
        'OK'      { Write-OK 'main.py is polling (main + payment bot)'; Set-ComponentStatus -Name 'Main bot (main.py)' -Status 'RUN' -Detail 'polling' -Log $mainLog }
        'PARTIAL' { Write-OK 'main.py started (import/DB done, polling may still be starting)'; Set-ComponentStatus -Name 'Main bot (main.py)' -Status 'RUN' -Detail 'starting - see CF Main bot window' -Log $mainLog }
        'FAIL'    { Write-Fail 'main.py crashed on startup - see log'; Set-ComponentStatus -Name 'Main bot (main.py)' -Status 'FAIL' -Detail 'startup error' -Log $mainLog }
        'TIMEOUT' { Write-Warn 'main.py still loading - check CF Main bot window (import can take minutes)'; Set-ComponentStatus -Name 'Main bot (main.py)' -Status 'WARN' -Detail 'still loading - see log' -Log $mainLog }
    }
    Start-Sleep -Seconds $PauseBetweenSteps
} else {
    Write-Step '7/9  Main bot (skipped)'
    Set-ComponentStatus -Name 'Main bot (main.py)' -Status 'SKIP' -Detail '-SkipMainBot'
}

function Ensure-FarmBotDeps {
    param([Parameter(Mandatory = $true)][string]$PythonExe)
    & $PythonExe -c 'import aiogram' 2>$null
    if ($LASTEXITCODE -eq 0) { return $true }
    Write-Info 'installing aiogram for farm bots...'
    & $PythonExe -m pip install -q aiogram==3.17.0
    if ($LASTEXITCODE -ne 0) {
        Write-Warn 'could not install aiogram — farm bots will fail (run: server\.venv\Scripts\pip install aiogram==3.17.0)'
        return $false
    }
    Write-OK 'aiogram installed'
    return $true
}

# ---------- 8) Farm bots (game + admin + support) ----------
if (-not $SkipFarmBots) {
    Write-Step '8/9  Farm bots (game + admin + support)'
    $serverPy = Join-Path $ServerDir '.venv\Scripts\python.exe'
    $botsLog = Join-Path $LogDir 'farm-bots.log'
    if (Test-Path $serverPy) {
        Ensure-FarmBotDeps -PythonExe $serverPy | Out-Null
        Start-LoggedWindow -Title 'CF Farm bots' -WorkingDirectory $ServerDir `
            -PythonExe $serverPy -PythonArgs '-X utf8 -W ignore::UserWarning' -Script 'bots_runner.py' -LogPath $botsLog `
            -LauncherPath (Join-Path $LogDir '_run-farm-bots.ps1') `
            -ExtraEnv @{ CF_DB_LIGHT_CONNECT = '1' }
    } else {
        Start-DevWindow -Title 'CF Farm bots' -WorkingDirectory $ServerDir -Command '$env:CF_DB_LIGHT_CONNECT=''1''; .\start-bots.ps1'
    }
    $botsStatus = Wait-LogMarker -LogPath $botsLog -Label 'farm bots' -TimeoutSec 90 -ReturnPartialEarly `
        -SuccessPatterns @('Run polling for bot', 'Start polling', '\[FARM-BOTS\] pollers starting') `
        -PartialPatterns @('\[FARM-BOTS\] database ready', '\[DB\]\[OK\] lightweight connect', '\[FARM-BOTS\] game bot:', 'Admin bot: @', 'Support bot: @') `
        -FailPatterns @('Traceback \(most recent call last\)', 'ImportError:', 'ModuleNotFoundError:', 'TokenValidationError', '\[DB\]\[FATAL\]')
    switch ($botsStatus) {
        'OK'      { Write-OK 'farm bots are polling (game/admin/support)'; Set-ComponentStatus -Name 'Farm bots' -Status 'RUN' -Detail 'game/admin/support' -Log $botsLog }
        'PARTIAL' { Write-OK 'farm bots process started - polling may still be initializing'; Set-ComponentStatus -Name 'Farm bots' -Status 'RUN' -Detail 'starting' -Log $botsLog }
        'FAIL'    { Write-Fail 'farm bots crashed on startup - see log'; Set-ComponentStatus -Name 'Farm bots' -Status 'FAIL' -Detail 'startup error' -Log $botsLog }
        'TIMEOUT' { Write-Warn 'farm bots did not report readiness in time - check CF Farm bots window'; Set-ComponentStatus -Name 'Farm bots' -Status 'WARN' -Detail 'see log' -Log $botsLog }
    }
    Start-Sleep -Seconds $PauseBetweenSteps
} else {
    Write-Step '8/9  Farm bots (skipped)'
    Set-ComponentStatus -Name 'Farm bots' -Status 'SKIP' -Detail '-SkipFarmBots'
}

# ---------- 9) ngrok (optional) ----------
if (-not $SkipNgrok) {
    Write-Step '9/9  ngrok tunnel to Vite :5173'
    $ngrok = Get-Command ngrok -ErrorAction SilentlyContinue
    if ($ngrok) {
        # Запускаем ngrok напрямую, без несуществующего start-tunnel.ps1
        Start-DevWindow -Title 'CF ngrok' -WorkingDirectory $Root -Command 'ngrok http 5173 --log=stdout'
        Write-OK 'ngrok started - copy HTTPS URL to WEBAPP_URL in server/.env'
        Set-ComponentStatus -Name 'ngrok' -Status 'RUN' -Detail 'see CF ngrok window'
    } else {
        Write-Info 'ngrok not in PATH - skipped (local: http://127.0.0.1:5173/)'
        Set-ComponentStatus -Name 'ngrok' -Status 'SKIP' -Detail 'ngrok not installed'
    }
} else {
    Write-Step '9/9  ngrok (skipped)'
    Set-ComponentStatus -Name 'ngrok' -Status 'SKIP' -Detail '-SkipNgrok'
}

# ============================================================
#                        DASHBOARD
# ============================================================
Show-Dashboard

Write-Host '  Endpoints:' -ForegroundColor Cyan
Write-Host '   WebApp game   http://127.0.0.1:5173/' -ForegroundColor Cyan
Write-Host '   Admin panel   http://127.0.0.1:5173/panel/' -ForegroundColor DarkGray
Write-Host '   API health    http://127.0.0.1:8000/health' -ForegroundColor DarkGray
Write-Host ''
Write-Host '  Windows: CF API :8000 | CF Vite :5173 | CF Main bot | CF Farm bots' -ForegroundColor DarkGray
Write-Host '  Stop a service with Ctrl+C in its window.' -ForegroundColor DarkGray
Write-Host ''

if (-not $SkipVite) {
    try { Start-Process 'http://127.0.0.1:5173/' } catch { }
}