# Save CuteHost postgres password to server/.env (MAIN / SSH mode)
param()

$ErrorActionPreference = 'Continue'
$envFile = Join-Path $PSScriptRoot '.env'

Write-Host '============================================'
Write-Host '  CuteHost postgres password (MAIN mode)'
Write-Host '  Same as pgAdmin -> CuteHost -> Connection'
Write-Host '============================================'
Write-Host ''

$newPass = Read-Host 'Enter postgres password for CuteHost'
if ([string]::IsNullOrWhiteSpace($newPass)) {
    Write-Host '[ERROR] Password is empty.' -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $envFile)) {
    Write-Host "[ERROR] Not found: $envFile" -ForegroundColor Red
    exit 1
}

$escaped = $newPass.Replace('"', '\"')
$content = Get-Content $envFile -Raw -Encoding UTF8
$content = $content -replace 'DB_PASSWORD_MAIN=.*', "DB_PASSWORD_MAIN=`"$escaped`""
Set-Content $envFile $content -Encoding UTF8 -NoNewline

Write-Host ''
Write-Host '[OK] DB_PASSWORD_MAIN saved to server/.env' -ForegroundColor Green
Write-Host ''
Write-Host 'Next: start-main.bat'
Write-Host ''
exit 0
