@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Cute - full stack
cd /d "%~dp0"

echo.
echo  ================================================
echo    Cute - full stack launch
echo    CuteGamingBot + WebApp + API + farm bots
echo  ================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-all.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [start-all] Launch failed. Exit code: %EXIT_CODE%
    pause
)

exit /b %EXIT_CODE%
