# Запуск admin-бота (отдельный от игрового)
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Сначала создай venv: py -3.12 -m venv .venv"
    exit 1
}

Write-Host ""
Write-Host "Admin bot (отдельный Telegram-бот для панели)"
Write-Host "Check server/.env: ADMIN_BOT_TOKEN, ADMIN_WEBAPP_URL, ADMIN_USER_IDS"
Write-Host "Stop: Ctrl+C"
Write-Host ""

.\.venv\Scripts\python.exe admin_bot.py
