# Production build + Vite preview on :5173 (for Telegram via ngrok).
# start_all.bat step 6 calls this script. Rebuild after code changes.

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot

function Stop-StalePreviewPort {
    param([int]$Port = 5173)
    for ($round = 0; $round -lt 3; $round++) {
        $conns = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
        if ($conns.Count -eq 0) { return }
        foreach ($c in $conns) {
            $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -in @('node')) {
                Write-Host "Stopping stale Vite on port $Port (PID $($c.OwningProcess))..." -ForegroundColor Yellow
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Seconds 2
    }
}

Write-Host ''
Write-Host 'Cute Farming - preview (production bundle on :5173)' -ForegroundColor Cyan
Write-Host ''

Set-Location $Root

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host '[ERROR] npm not found. Install Node.js: https://nodejs.org/' -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}

if (-not (Test-Path 'node_modules')) {
    Write-Host 'node_modules missing - running npm install...' -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[ERROR] npm install failed' -ForegroundColor Red
        Read-Host 'Press Enter to close'
        exit 1
    }
}

Stop-StalePreviewPort -Port 5173

Write-Host 'Building game + panel...' -ForegroundColor Cyan
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] npm run build failed' -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}

Write-Host ''
Write-Host 'Game:  http://127.0.0.1:5173/'
Write-Host 'Admin: http://127.0.0.1:5173/panel/'
Write-Host 'Stop:  Ctrl+C'
Write-Host ''

npm run preview
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '[ERROR] preview exited with error' -ForegroundColor Red
    Read-Host 'Press Enter to close'
}
