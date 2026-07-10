@echo off
chcp 65001 >nul
title Sync CuteHost postgres password
cd /d "%~dp0"

echo ============================================
echo   Set remote postgres password = .env value
echo   Server: 207.154.219.208 (root SSH)
echo ============================================
echo.
echo pgAdmin may connect via Unix socket without TCP password.
echo This sets the TCP password on the server to match server/.env
echo.
echo You will enter root SSH password once.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\sync-cutehost-password.ps1"
pause
