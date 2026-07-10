@echo off
chcp 65001 >nul
title CF · API :8000
cd /d "%~dp0"

if not "%CF_TUNNEL_READY%"=="1" (
    findstr /B /C:"APP_MODE=main" "%~dp0server\.env" >nul 2>&1
    if not errorlevel 1 (
        findstr /C:"MAIN_DB_TARGET=local" "%~dp0server\.env" >nul 2>&1
        if errorlevel 1 (
            echo.
            echo MAIN mode uses CuteHost via SSH.
            echo Starting start-main.bat ...
            echo.
            call "%~dp0start-main.bat"
            exit /b %errorlevel%
        )
    )
)

cd /d "%~dp0server"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\start-server.ps1"
if errorlevel 1 pause
