@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "NOPAUSE=%~1"
title Cute - PostgreSQL 17 + cutebase

echo.
echo  === PostgreSQL 17 (cutebase @ 127.0.0.1:5432) ===
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\ensure-postgres.ps1" -Port 5432
if errorlevel 1 (
    echo.
    echo  [FAIL] PostgreSQL не слушает :5432
    echo.
    echo  Частые причины:
    echo    1^) На диске C: закончилось место  ^(см. Program Files\PostgreSQL\17\data\log\pg_ctl_start.log^)
    echo    2^) Служба postgresql-x64-17 не запущена ^(нужен админ^)
    echo.
    echo  Альтернатива:  set-mode.bat main   ^(серверная БД через SSH :15432^)
    echo.
    if /i not "%NOPAUSE%"=="nopause" pause
    exit /b 1
)

echo  [OK] PostgreSQL слушает :5432
echo.

rem Best-effort: ensure database cutebase exists (ignore errors if already there).
set "PSQL=C:\Program Files\PostgreSQL\17\bin\psql.exe"
if exist "%PSQL%" (
    echo  Проверяю базу cutebase...
    "%PSQL%" -U postgres -h 127.0.0.1 -p 5432 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='cutebase'" 2>nul | findstr /r "^1$" >nul
    if errorlevel 1 (
        echo  Создаю базу cutebase...
        "%PSQL%" -U postgres -h 127.0.0.1 -p 5432 -d postgres -c "CREATE DATABASE cutebase;" 2>nul
        if errorlevel 1 (
            echo  [WARN] Не удалось создать cutebase автоматически.
            echo         Создай вручную или проверь пароль postgres в .pgpass / PGPASSWORD.
        ) else (
            echo  [OK] База cutebase создана.
        )
    ) else (
        echo  [OK] База cutebase уже есть.
    )
)

echo.
if /i not "%NOPAUSE%"=="nopause" pause
exit /b 0
