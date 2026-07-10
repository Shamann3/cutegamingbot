@echo off
chcp 65001 >nul
title Пароль CuteHost (MAIN)
cd /d "%~dp0"

echo ============================================
echo   Пароль postgres для CuteHost (MAIN)
echo   Тот же что в pgAdmin - CuteHost
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\set-cutehost-password.ps1"
set ERR=%errorlevel%

echo.
if not %ERR%==0 (
    echo [ОШИБКА] Код: %ERR%
)
pause
exit /b %ERR%
