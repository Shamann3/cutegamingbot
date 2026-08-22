# Set remote postgres password (NO base64) - передача скрипта через stdin
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host '[ERROR] venv not found' -ForegroundColor Red
    exit 1
}

# Генерируем SQL-команду (кавычки в пароле экранируются правильно)
$sql = & $python -c @"
import sys
sys.path.insert(0, '.')
from config import DB_PASSWORD, DB_USER
escaped_pw = DB_PASSWORD.replace("'", "''")
print(f"ALTER USER {DB_USER} WITH PASSWORD '{escaped_pw}';")
"@

if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host 'Setting remote postgres password from server/.env'
Write-Host 'Enter root SSH password when prompted.'
Write-Host ''

# Формируем bash-скрипт, который будет выполнен на удалённом сервере
$remoteScript = @"
#!/bin/bash
set -e
sudo -u postgres psql -v ON_ERROR_STOP=1 -c '$sql'
"@

# Передаём скрипт через stdin в ssh (без base64)
$remoteScript | ssh -o ServerAliveInterval=30 root@207.154.219.208 "bash -s"

if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '[ERROR] Failed. Wrong root SSH password or no server access.' -ForegroundColor Red
    Write-Host 'Use MAIN_DB_TARGET=local in server/.env — works without SSH.' -ForegroundColor Yellow
    exit 1
}

Write-Host ''
Write-Host '[OK] Remote password updated.' -ForegroundColor Green