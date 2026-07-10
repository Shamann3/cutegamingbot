@echo off
chcp 65001 >nul
title Cute Farming — запуск dev (без ngrok и ботов)

cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1" -SkipNgrok -SkipBots

echo.
pause
