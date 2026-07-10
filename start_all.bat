@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Cute - full stack (start_all)
cd /d "%~dp0"

echo.
echo  ================================================
echo    Cute - full stack launch (start_all)
echo  ------------------------------------------------
echo    1) DB config check (bot == WebApp)
echo    2) SSH tunnel to CuteHost (main/remote)
echo    3) PostgreSQL connection test
echo    4) Redis cache        (auto-start, required for speed)
echo    5) API server        (FastAPI :8000)
echo    6) WebApp frontend    (Vite :5173)
echo    7) Main bot           (main.py: main + payment)
echo    8) Farm bots          (game + admin + support)
echo    9) ngrok              (optional)
echo  ------------------------------------------------
echo    Live status dashboard + logs in .\logs\
echo  ================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-all.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [start_all] Launch stopped early. Exit code: %EXIT_CODE%
    echo [start_all] See the messages above and the logs in .\logs\
    pause
)

exit /b %EXIT_CODE%
