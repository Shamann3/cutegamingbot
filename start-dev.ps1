# Cute Farming dev launcher: API -> Vite -> ngrok -> bots (separate windows).

param(
    [switch]$SkipNgrok,
    [switch]$SkipBots,
    [int]$PauseBetweenSteps = 2
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$ServerDir = Join-Path $Root 'server'

function Stop-StaleListener {
    param([int]$Port, [string[]]$ProcessNames = @('node', 'python'))
    for ($round = 0; $round -lt 3; $round++) {
        $conns = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
        if ($conns.Count -eq 0) { return }
        foreach ($c in $conns) {
            $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and ($ProcessNames -contains $proc.ProcessName)) {
                Write-Host "   Stopping stale $($proc.ProcessName) on port $Port (PID $($c.OwningProcess))" -ForegroundColor Yellow
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Seconds 2
    }
}

function Write-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Wait-HttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSec = 90,
        [string]$Label = $Url
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    Write-Host "   Waiting for $Label ..." -ForegroundColor DarkGray

    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "   OK: $Label" -ForegroundColor Green
                return $true
            }
        } catch {
            # still starting
        }
        Start-Sleep -Seconds 1
    }

    Write-Host "   Timeout: $Label did not respond in ${TimeoutSec}s" -ForegroundColor Yellow
    return $false
}

function Start-DevWindow {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Command
    )

    $launch = @(
        '-NoExit',
        '-ExecutionPolicy', 'Bypass',
        '-Command',
        "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location -LiteralPath '$WorkingDirectory'; $Command"
    )

    Start-Process -FilePath 'powershell.exe' -ArgumentList $launch | Out-Null
    Write-Host "   Window: $Title" -ForegroundColor DarkGray
}

Write-Host ''
Write-Host 'Cute Farming dev startup' -ForegroundColor White
Write-Host "Project root: $Root" -ForegroundColor DarkGray
Write-Host ''

$envFile = Join-Path $ServerDir '.env'
if (Test-Path $envFile) {
    $appMode = (Select-String -Path $envFile -Pattern '^\s*APP_MODE\s*=\s*(\S+)' | Select-Object -First 1).Matches.Groups[1].Value
    if ($appMode -eq 'test') {
        Write-Step '0/4 - PostgreSQL for test mode'
        & (Join-Path $ServerDir 'ensure-postgres.ps1') | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host '   OK: PostgreSQL on port 5432' -ForegroundColor Green
        } else {
            Write-Host '   WARN: PostgreSQL not ready - check services.msc' -ForegroundColor Yellow
        }
        Write-Host ''
    }
}

Stop-StaleListener -Port 8000 -ProcessNames @('python')
Stop-StaleListener -Port 5173 -ProcessNames @('node')

Write-Step '1/4 - API server port 8000'
Start-DevWindow -Title 'CF API 8000' -WorkingDirectory $ServerDir -Command '.\start-server.ps1'

$apiTimeout = 90
if (Test-Path $envFile) {
    $modeForWait = (Select-String -Path $envFile -Pattern '^\s*APP_MODE\s*=\s*(\S+)' | Select-Object -First 1).Matches.Groups[1].Value
    if ($modeForWait -eq 'main') { $apiTimeout = 180 }
}

if (-not (Wait-HttpOk -Url 'http://127.0.0.1:8000/health' -TimeoutSec $apiTimeout -Label 'API /health')) {
    Write-Host 'Continuing, but API may still be starting.' -ForegroundColor Yellow
}
Start-Sleep -Seconds $PauseBetweenSteps

Write-Step '2/4 - Frontend Vite port 5173'
Start-DevWindow -Title 'CF Vite 5173' -WorkingDirectory $Root -Command '.\start-vite.ps1'

if (-not (Wait-HttpOk -Url 'http://127.0.0.1:5173/' -Label 'Vite 5173')) {
    Write-Host 'Continuing, but Vite may still be starting.' -ForegroundColor Yellow
}
Start-Sleep -Seconds $PauseBetweenSteps

if (-not $SkipNgrok) {
    Write-Step '3/4 - ngrok tunnel to 5173'
    $ngrok = Get-Command ngrok -ErrorAction SilentlyContinue
    if ($ngrok) {
        Start-DevWindow -Title 'CF ngrok' -WorkingDirectory $Root -Command '.\start-tunnel.ps1'
        Write-Host '   ngrok started - see URL in the new window' -ForegroundColor Green
        Start-Sleep -Seconds $PauseBetweenSteps
    } else {
        Write-Host '   ngrok not found in PATH - skipped' -ForegroundColor Yellow
        Write-Host '   Install: https://ngrok.com/download' -ForegroundColor DarkGray
    }
} else {
    Write-Step '3/4 - ngrok skipped'
}

if (-not $SkipBots) {
    Write-Step '4/4 - Telegram bots'
    Start-DevWindow -Title 'CF Bots' -WorkingDirectory $ServerDir -Command '.\start-bots.ps1'
    Write-Host '   Bots started in a separate window' -ForegroundColor Green
} else {
    Write-Step '4/4 - bots skipped'
}

Write-Host ''
Write-Host 'Ready.' -ForegroundColor Green
Write-Host '  Game:  http://127.0.0.1:5173/' -ForegroundColor Cyan
Write-Host '  API:   http://127.0.0.1:8000/health' -ForegroundColor DarkGray
Write-Host '  Admin: http://127.0.0.1:5173/panel/' -ForegroundColor DarkGray
Write-Host ''
Start-Process 'http://127.0.0.1:5173/'
Write-Host 'Browser opened. You can close this window - services run in other terminals.' -ForegroundColor DarkGray
Write-Host ''
