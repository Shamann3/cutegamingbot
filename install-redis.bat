@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Install Redis (Memurai) as auto-start Windows service
cd /d "%~dp0"

echo.
echo  ================================================
echo    One-time Redis setup (Memurai auto-start service)
echo    - installs Redis-compatible server
echo    - starts automatically on every Windows boot
echo    - listens on 127.0.0.1:6379
echo  ================================================
echo.
echo  A UAC prompt will ask for Administrator rights - click "Yes".
echo.

set "PS1=%~dp0scripts\install-redis.ps1"
if not exist "%PS1%" (
    echo [ERROR] Script not found:
    echo   %PS1%
    echo.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [install-redis] finished with code %EXIT_CODE%
)
pause
exit /b %EXIT_CODE%
