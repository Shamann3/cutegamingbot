@echo off
chcp 65001 >nul
title Cute Farming — запуск dev

cd /d "%~dp0"

echo.
echo  Cute Farming — поочередный запуск (API -^> Vite -^> ngrok -^> боты)
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1"

echo.
pause
