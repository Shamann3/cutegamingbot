@echo off
chcp 65001 >nul
title Пароль postgres (локальный TEST)
cd /d "%~dp0"

echo ============================================
echo   Пароль для ЛОКАЛЬНОЙ тестовой БД (test)
echo   Для CuteHost (main): set-cutehost-password.bat
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\set-db-password.ps1"
set ERR=%errorlevel%

echo.
if not %ERR%==0 (
    echo [ОШИБКА] Код: %ERR%
)
pause
exit /b %ERR%
