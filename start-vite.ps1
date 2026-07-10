# Frontend Vite (port 5173)
Set-Location $PSScriptRoot

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host ''
    Write-Host '[ERROR] npm not found. Install Node.js: https://nodejs.org/' -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}

if (-not (Test-Path 'node_modules')) {
    Write-Host ''
    Write-Host 'node_modules missing - running npm install...' -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[ERROR] npm install failed' -ForegroundColor Red
        Read-Host 'Press Enter to close'
        exit 1
    }
}

Write-Host ''
Write-Host 'Game:  http://127.0.0.1:5173/'
Write-Host 'Admin: http://127.0.0.1:5173/panel/'
Write-Host 'Stop:  Ctrl+C'
Write-Host ''

npm run dev
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '[ERROR] Vite exited with error' -ForegroundColor Red
    Read-Host 'Press Enter to close'
}
