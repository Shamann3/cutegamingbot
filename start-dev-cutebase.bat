@echo off
chcp 65001 >nul
title Cute Farming — dev с основной БД cutebase

cd /d "%~dp0"

echo.
echo 1/2 — PostgreSQL 17 + cutebase
echo.
call "%~dp0start-0-postgres-cutebase.bat" nopause
if errorlevel 1 (
    echo.
    echo [ОШИБКА] PostgreSQL / cutebase не готовы. Dev не запущен.
    pause
    exit /b 1
)

echo.
echo 2/2 — API + Vite + боты (без ngrok)
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1" -SkipNgrok -SkipBots

echo.
pause
