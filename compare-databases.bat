@echo off
chcp 65001 >nul
title Compare local vs CuteHost DB
cd /d "%~dp0server"

echo ============================================
echo   Compare databases (same password from .env)
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\compare-databases.ps1"
pause
