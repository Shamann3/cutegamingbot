# Game + admin + support bots
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

function Invoke-Pip {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & $python -m pip @Args
}

# Проверяем, что venv реально работает на этой машине (файл может существовать,
# но ссылаться на несуществующий путь, если .venv скопирован с другого ПК).
$venvOk = $false
if (Test-Path $python) {
    & $python -c 'import sys' 2>$null
    $venvOk = ($LASTEXITCODE -eq 0)
}
if (-not $venvOk) {
    Write-Host '[ERROR] .venv is missing or from another PC.' -ForegroundColor Red
    Write-Host '        Run start-1-server.bat first - it will (re)create the venv.' -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}

& $python -c 'import aiogram' 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing bot dependencies (aiogram)...'
    Invoke-Pip install -q aiogram==3.17.0 --no-deps
    Invoke-Pip install -q 'aiofiles>=23.2.1,<24.2' 'magic-filter>=1.0.12,<1.1' certifi
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[ERROR] Failed to install aiogram' -ForegroundColor Red
        Read-Host 'Press Enter to close'
        exit 1
    }
}

Write-Host ''
Write-Host 'Bots: game + admin + support'
Write-Host 'Check server/.env: BOT_TOKEN, WEBAPP_URL, ADMIN_BOT_TOKEN, SUPPORT_BOT_TOKEN'
Write-Host 'Stop: Ctrl+C'
Write-Host 'Run bots in ONE place only (do not duplicate start-4-bots and start-dev.bat)'
Write-Host ''

& $python bots_runner.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '[ERROR] Bots exited with error' -ForegroundColor Red
    Read-Host 'Press Enter to close'
}
