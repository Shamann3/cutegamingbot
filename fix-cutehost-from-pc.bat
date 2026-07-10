@echo off
chcp 65001 >nul
title Fix CuteHost postgres (from PC via SSH)
cd /d "%~dp0"

echo ============================================
echo   Fix postgres password ON SERVER via SSH
echo   Uses ROOT password (same as PuTTY login)
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\fix-cutehost-remote.ps1"
set ERR=%errorlevel%

echo.
if %ERR%==0 (
    echo [OK] Server fixed. Now run: start-main.bat
) else (
    echo [ERROR] Failed. Or use PuTTY manually - see putty-fix-database.txt
)
pause
exit /b %ERR%
