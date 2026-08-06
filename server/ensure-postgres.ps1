# Ensure PostgreSQL 17 is running on port 5432. Exit 0 if OK, 1 if failed.
param(
    [int]$Port = 5432,
    [int]$TimeoutSec = 45
)

$ErrorActionPreference = 'Continue'
$pgHome = 'C:\Program Files\PostgreSQL\17'
$pgData = Join-Path $pgHome 'data'
$pgctl = Join-Path $pgHome 'bin\pg_ctl.exe'
$service = 'postgresql-x64-17'

function Test-PgTcp {
    param([int]$TargetPort = 5432)
    $client = $null
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect('127.0.0.1', $TargetPort)
        return $true
    } catch {
        return $false
    } finally {
        if ($client) { $client.Close() }
    }
}

function Remove-StalePostmasterPid {
    param([string]$DataDir)
    $pidFile = Join-Path $DataDir 'postmaster.pid'
    if (-not (Test-Path -LiteralPath $pidFile)) { return $false }
    try {
        $raw = (Get-Content -LiteralPath $pidFile -TotalCount 1 -ErrorAction Stop).Trim()
        $oldPid = 0
        [void][int]::TryParse($raw, [ref]$oldPid)
        if ($oldPid -le 0) {
            Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
            Write-Host "[..] removed invalid postmaster.pid" -ForegroundColor Yellow
            return $true
        }
        $alive = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($alive) { return $false }
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction Stop
        Write-Host "[..] removed stale postmaster.pid (dead PID $oldPid)" -ForegroundColor Yellow
        return $true
    } catch {
        Write-Host "[!!] could not clear postmaster.pid: $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

function Show-DiskHint {
    try {
        $free = (Get-PSDrive C).Free
        $freeGb = [math]::Round($free / 1GB, 2)
        if ($free -lt 3GB) {
            Write-Host "[!!] На диске C: мало места: ${freeGb} GB. PostgreSQL падает при No space left on device." -ForegroundColor Yellow
        }
    } catch { }
}

if (Test-PgTcp -TargetPort $Port) {
    Write-Host "[OK] PostgreSQL уже слушает порт $Port." -ForegroundColor Green
    exit 0
}

Show-DiskHint

$root = Split-Path $PSScriptRoot -Parent
$compose = Join-Path $root 'docker-compose.yml'
if ((Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path $compose)) {
    Push-Location $root
    docker compose stop postgres 2>$null | Out-Null
    Pop-Location
    Start-Sleep -Seconds 1
}

if (Test-PgTcp -TargetPort $Port) { exit 0 }

Write-Host '[..] PostgreSQL не запущен. Запускаю...'

# Stale lock after crash / kill is the #1 reason pg_ctl hangs or refuses start.
if (Test-Path -LiteralPath $pgData) {
    [void](Remove-StalePostmasterPid -DataDir $pgData)
}

$svc = Get-Service -Name $service -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -ne 'Running') {
    try {
        Start-Service $service -ErrorAction Stop
        Start-Sleep -Seconds 2
    } catch {
        Write-Host '[!!] Службу не удалось запустить (нужен администратор). Пробую pg_ctl...' -ForegroundColor Yellow
    }
}

if (-not (Test-PgTcp -TargetPort $Port)) {
    if ((Test-Path -LiteralPath $pgctl) -and (Test-Path -LiteralPath (Join-Path $pgData 'postgresql.conf'))) {
        $logDir = Join-Path $pgData 'log'
        if (-not (Test-Path -LiteralPath $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        $logFile = Join-Path $logDir 'pg_ctl_start.log'
        Write-Host '[..] starting via pg_ctl (detached)...'
        try {
            & $pgctl start -D "$pgData" -l "$logFile" -w -t $TimeoutSec 2>&1 | ForEach-Object { Write-Host "    $_" }
        } catch {
            Write-Host "[!!] pg_ctl error: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[!!] pg_ctl/data not found under '$pgHome'" -ForegroundColor Yellow
    }
}

$deadline = (Get-Date).AddSeconds([Math]::Max(5, $TimeoutSec))
while (-not (Test-PgTcp -TargetPort $Port) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
}

if (Test-PgTcp -TargetPort $Port) {
    Write-Host "[OK] PostgreSQL слушает порт $Port." -ForegroundColor Green
    exit 0
}

Write-Host "[ОШИБКА] PostgreSQL не запустился на порту $Port." -ForegroundColor Red
$logFile = Join-Path $pgData 'log\pg_ctl_start.log'
if (Test-Path -LiteralPath $logFile) {
    Write-Host "--- last lines of $logFile ---" -ForegroundColor DarkGray
    Get-Content -LiteralPath $logFile -Tail 12 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
}
Write-Host "Проверь место на C: и лог выше. Либо: set-mode.bat main" -ForegroundColor Yellow
exit 1
