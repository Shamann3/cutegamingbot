@echo off
chcp 65001 >nul
title Test SSH + DB CuteHost
cd /d "%~dp0"

echo === 1) SSH tunnel port 15432 ===
netstat -an | findstr /C:":15432" | findstr LISTENING >nul
if errorlevel 1 (
    echo [NO] Tunnel not running. Start start-ssh-cutehost.bat first.
) else (
    echo [OK] Tunnel port 15432 is listening.
)

echo.
echo === 2) PostgreSQL via tunnel ===
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\test-cutehost-db.ps1"
pause
