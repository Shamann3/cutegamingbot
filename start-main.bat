@echo off
chcp 65001 >nul
title Support Bot · MAIN (CuteHost)
cd /d "%~dp0"

echo ============================================
echo   MAIN = CuteHost cutebase via SSH
echo ============================================
echo.

call "%~dp0set-mode.bat" main >nul 2>&1

findstr /B /C:"APP_MODE=main" "%~dp0.env" >nul 2>&1
if errorlevel 1 (
    echo [WARN] APP_MODE не main. Запуск: set-mode.bat main
    echo.
)

netstat -an | findstr /C:":15432" | findstr LISTENING >nul
if not errorlevel 1 (
    echo [OK] Tunnel already on port 15432.
    goto :db_test
)

echo Starting tunnel (plink, password from .env)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-ssh-tunnel.ps1" -Background
if errorlevel 1 (
    echo.
    echo === Tunnel failed ===
    echo.
    echo OPTION A - start-main.bat снова после исправления SSH_PASSWORD в .env
    echo OPTION B - WinSCP: Local 15432 -^> 127.0.0.1:5432, затем start-with-winscp.bat
    echo.
    pause
    exit /b 1
)

:db_test
echo.
call "%~dp0start.bat"
if errorlevel 1 pause
