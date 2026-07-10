# ============================================================
#  ensure-redis.ps1 - start Redis on Windows (fast, no hangs).
#
#  Tries: already running -> Memurai service -> redis-server.exe
#         -> Docker (only if daemon responds in 2s) -> WSL (5s cap)
#  Exit 0 = Redis ready, 1 = not available.
# ============================================================
param(
    [string]$RedisHost = '127.0.0.1',
    [int]$Port = 6379,
    [int]$TimeoutSec = 20,
    [switch]$Quiet
)

$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
$RedisDataDir = Join-Path $Root '.redis'
$Deadline = (Get-Date).AddSeconds([Math]::Max(5, $TimeoutSec))

function Say  { param([string]$m) if (-not $Quiet) { Write-Host "   [redis] $m" -ForegroundColor DarkGray } }
function Good { param([string]$m) if (-not $Quiet) { Write-Host "   [redis] $m" -ForegroundColor Green } }
function Bad  { param([string]$m) if (-not $Quiet) { Write-Host "   [redis] $m" -ForegroundColor Yellow } }

function Time-LeftSec {
    $left = ($Deadline - (Get-Date)).TotalSeconds
    if ($left -lt 0) { return 0 }
    return [int][Math]::Ceiling($left)
}

function Test-RedisPort {
    param([string]$H, [int]$P)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($H, $P, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(350, $false)
        if ($ok -and $client.Connected) { $client.EndConnect($iar); $client.Close(); return $true }
        $client.Close(); return $false
    } catch { return $false }
}

function Test-RedisPing {
    param([string]$H, [int]$P)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($H, $P, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne(400, $false)) { $client.Close(); return $false }
        $client.EndConnect($iar)
        $stream = $client.GetStream()
        $stream.ReadTimeout = 600
        $ping = [Text.Encoding]::ASCII.GetBytes("PING`r`n")
        $stream.Write($ping, 0, $ping.Length)
        Start-Sleep -Milliseconds 80
        $buf = New-Object byte[] 64
        $n = 0
        try { $n = $stream.Read($buf, 0, $buf.Length) } catch { $n = 0 }
        $client.Close()
        if ($n -le 0) { return $true }
        $reply = [Text.Encoding]::ASCII.GetString($buf, 0, $n)
        return ($reply -match 'PONG' -or $reply -match 'NOAUTH' -or $reply -match 'ERR' -or $reply.StartsWith('+') -or $reply.StartsWith('-'))
    } catch { return $false }
}

function Test-RedisReady {
    param([string]$H, [int]$P)
    return (Test-RedisPort $H $P) -and (Test-RedisPing $H $P)
}

function Wait-RedisReady {
    param([string]$H, [int]$P, [int]$MaxSec)
    $end = (Get-Date).AddSeconds([Math]::Min($MaxSec, (Time-LeftSec)))
    while ((Get-Date) -lt $end) {
        if (Test-RedisReady $H $P) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Invoke-WithTimeout {
    param(
        [string]$Exe,
        [string[]]$ArgList,
        [int]$TimeoutSec = 3
    )
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Exe
        $psi.Arguments = ($ArgList -join ' ')
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        if (-not $p.WaitForExit($TimeoutSec * 1000)) {
            try { $p.Kill() } catch { }
            return $false
        }
        return ($p.ExitCode -eq 0)
    } catch {
        return $false
    }
}

function Test-DockerDaemon {
    $docker = Get-Command 'docker' -ErrorAction SilentlyContinue
    if (-not $docker) { return $false }
    return (Invoke-WithTimeout -Exe $docker.Source -ArgList @('info') -TimeoutSec 2)
}

# ---- start -------------------------------------------------------------------
Say "checking ${RedisHost}:${Port} (budget ${TimeoutSec}s)..."

if (Test-RedisReady $RedisHost $Port) {
    Good "already running on ${RedisHost}:$Port"
    exit 0
}

# 1) Memurai Windows service
$memuraiSvc = Get-Service -Name 'Memurai*' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($memuraiSvc -and (Time-LeftSec) -gt 0) {
    # Закрепляем автозапуск: служба будет подниматься при старте Windows сама.
    try { Set-Service -Name $memuraiSvc.Name -StartupType Automatic -ErrorAction SilentlyContinue } catch { }
    if ($memuraiSvc.Status -ne 'Running') {
        Say "starting Memurai ($($memuraiSvc.Name))..."
        Start-Service -Name $memuraiSvc.Name -ErrorAction SilentlyContinue
    }
    if (Wait-RedisReady $RedisHost $Port ([Math]::Min(8, (Time-LeftSec)))) {
        Good "Memurai up on ${RedisHost}:$Port (autostart=Automatic)"
        exit 0
    }
}

# 2) redis-server.exe / memurai.exe
function Find-RedisServerExe {
    $cmd = Get-Command 'redis-server' -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($c in @(
        'C:\Program Files\Redis\redis-server.exe',
        'C:\Program Files\Memurai\memurai.exe',
        (Join-Path $env:ProgramData 'chocolatey\lib\redis-64\tools\redis-server.exe'),
        (Join-Path $env:USERPROFILE 'scoop\apps\redis\current\redis-server.exe'),
        (Join-Path $Root 'redis\redis-server.exe')
    )) {
        if (Test-Path $c) { return $c }
    }
    return $null
}

$redisExe = Find-RedisServerExe
if ($redisExe -and (Time-LeftSec) -gt 0) {
    New-Item -ItemType Directory -Force -Path $RedisDataDir | Out-Null
    Say "launching $redisExe ..."
    $redisArgs = @('--port', "$Port", '--bind', '127.0.0.1', '--save', '', '--appendonly', 'no', '--dir', "$RedisDataDir")
    Start-Process -FilePath $redisExe -ArgumentList $redisArgs -WindowStyle Hidden | Out-Null
    if (Wait-RedisReady $RedisHost $Port ([Math]::Min(8, (Time-LeftSec)))) {
        Good "redis-server up on ${RedisHost}:$Port"
        exit 0
    }
    Bad 'redis-server started but did not answer PING'
}

# 3) Docker - ONLY if daemon answers quickly (avoids 60s hang when Desktop is off)
if ((Time-LeftSec) -gt 0) {
    if (Test-DockerDaemon) {
        Say 'docker daemon OK, starting cute-redis...'
        $docker = (Get-Command 'docker').Source
        $running = & $docker ps --filter 'name=cute-redis' --filter 'status=running' --format '{{.Names}}' 2>$null
        if ($running -match 'cute-redis') {
            Good 'docker container cute-redis already running'
        } else {
            $exists = & $docker ps -a --filter 'name=cute-redis' --format '{{.Names}}' 2>$null
            if ($exists -match 'cute-redis') {
                & $docker start cute-redis 2>$null | Out-Null
            } else {
                & $docker run -d --name cute-redis -p "${Port}:6379" --restart unless-stopped redis:7-alpine 2>$null | Out-Null
            }
        }
        if (Wait-RedisReady $RedisHost $Port ([Math]::Min(12, (Time-LeftSec)))) {
            Good "docker redis up on ${RedisHost}:$Port"
            exit 0
        }
        Bad 'docker redis did not become ready'
    } else {
        Say 'docker skipped (daemon not running or not installed)'
    }
}

# 4) WSL - short timeout
if ((Time-LeftSec) -gt 0 -and (Get-Command 'wsl' -ErrorAction SilentlyContinue)) {
    Say 'trying WSL redis-server (5s cap)...'
    $null = Invoke-WithTimeout -Exe 'wsl' -ArgList @('-e', 'sh', '-c', "command -v redis-server >/dev/null 2>&1 && redis-server --port $Port --daemonize yes") -TimeoutSec 5
    if (Wait-RedisReady $RedisHost $Port ([Math]::Min(5, (Time-LeftSec)))) {
        Good "WSL redis up on ${RedisHost}:$Port"
        exit 0
    }
}

Bad "Redis not available on ${RedisHost}:$Port"
Bad 'One-time install (run in Admin PowerShell):'
Bad '   winget install Memurai.MemuraiDeveloper'
Bad '   then:  Get-Service Memurai*   (Status should be Running)'
exit 1
