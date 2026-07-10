# Set remote postgres password (fixed quoting via base64 script)
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host '[ERROR] venv not found' -ForegroundColor Red
    exit 1
}

$payload = & $python -c @"
import json, base64
from config import DB_PASSWORD, DB_USER
sql = f"ALTER USER {DB_USER} WITH PASSWORD '{DB_PASSWORD.replace(chr(39), chr(39)+chr(39))}';"
script = '#!/bin/bash\nset -e\nsudo -u postgres psql -v ON_ERROR_STOP=1 -c ' + repr(sql) + '\n'
print(base64.b64encode(script.encode('utf-8')).decode('ascii'))
"@

if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host 'Setting remote postgres password from server/.env'
Write-Host 'Enter root SSH password when prompted.'
Write-Host ''

ssh -o ServerAliveInterval=30 root@207.154.219.208 "echo $payload | base64 -d | bash"

if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '[ERROR] Failed. Wrong root SSH password or no server access.' -ForegroundColor Red
    Write-Host 'Use MAIN_DB_TARGET=local in server/.env — works without SSH.' -ForegroundColor Yellow
    exit 1
}

Write-Host ''
Write-Host '[OK] Remote password updated.' -ForegroundColor Green
