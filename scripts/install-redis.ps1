# install-redis.ps1 - one-time Memurai install (Windows service, auto-start)
param([int]$Port = 6379)

$ErrorActionPreference = 'Continue'

$SelfPath = $MyInvocation.MyCommand.Path
if (-not $SelfPath) { $SelfPath = Join-Path $PSScriptRoot 'install-redis.ps1' }

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)

if (-not $isAdmin) {
    Write-Host 'Requesting Administrator rights (needed to install a service)...' -ForegroundColor Yellow
    try {
        $argLine = "-NoProfile -ExecutionPolicy Bypass -File `"$SelfPath`" -Port $Port"
        Start-Process -FilePath 'powershell.exe' -ArgumentList $argLine -Verb RunAs -Wait
    } catch {
        Write-Host 'Elevation was cancelled. Re-run and click Yes.' -ForegroundColor Red
    }
    exit
}

function Info { param([string]$m) Write-Host "[install-redis] $m" -ForegroundColor Cyan }
function Good { param([string]$m) Write-Host "[install-redis] $m" -ForegroundColor Green }
function Warn { param([string]$m) Write-Host "[install-redis] $m" -ForegroundColor Yellow }

function Test-Redis {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect('127.0.0.1', $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(500, $false)
        if ($ok -and $c.Connected) { $c.EndConnect($iar); $c.Close(); return $true }
        $c.Close(); return $false
    } catch { return $false }
}

function Set-MemuraiAutostart {
    $svc = Get-Service -Name 'Memurai*' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($svc) {
        Set-Service -Name $svc.Name -StartupType Automatic -ErrorAction SilentlyContinue
        & sc.exe failure $svc.Name reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
        if ($svc.Status -ne 'Running') { Start-Service -Name $svc.Name -ErrorAction SilentlyContinue }
        Good "service '$($svc.Name)' -> Automatic + auto-restart on crash"
        return $true
    }
    return $false
}

if (Test-Redis) {
    Good "Redis already listening on 127.0.0.1:$Port"
    Set-MemuraiAutostart | Out-Null
    Read-Host 'Done. Press Enter to close'
    exit 0
}

$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
    Info 'installing Memurai via winget...'
    & winget install --id Memurai.MemuraiDeveloper -e --accept-source-agreements --accept-package-agreements
    Start-Sleep -Seconds 3
    if (Set-MemuraiAutostart) {
        Start-Sleep -Seconds 2
        if (Test-Redis) { Good "Redis ready on 127.0.0.1:$Port (auto-start ON)"; Read-Host 'Press Enter to close'; exit 0 }
    }
}

$choco = Get-Command choco -ErrorAction SilentlyContinue
if ($choco -and -not (Test-Redis)) {
    Info 'installing Memurai via Chocolatey...'
    & choco install memurai-developer -y
    Start-Sleep -Seconds 3
    if (Set-MemuraiAutostart) {
        Start-Sleep -Seconds 2
        if (Test-Redis) { Good "Redis ready on 127.0.0.1:$Port (auto-start ON)"; Read-Host 'Press Enter to close'; exit 0 }
    }
}

$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker -and -not (Test-Redis)) {
    Info 'using Docker container cute-redis (restart=always)...'
    & docker run -d --name cute-redis -p "${Port}:6379" --restart always redis:7-alpine 2>$null | Out-Null
    Start-Sleep -Seconds 4
    if (Test-Redis) { Good "Docker Redis ready on 127.0.0.1:$Port"; Read-Host 'Press Enter to close'; exit 0 }
}

Warn 'Could not install Redis automatically.'
Warn 'Download Memurai: https://www.memurai.com/get-memurai'
Read-Host 'Press Enter to close'
exit 1
