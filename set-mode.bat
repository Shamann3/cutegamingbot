@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" (
    echo.
    echo  Переключение базы данных ^(главный переключатель = bot\config\config.py^):
    echo    set-mode.bat test           - тест  + локально   ^(127.0.0.1:5432, без SSH^)
    echo    set-mode.bat main           - боевая + сервер    ^(127.0.0.1:15432, SSH-туннель^)
    echo    set-mode.bat test remote    - тестовый профиль, но БД на сервере
    echo    set-mode.bat main local     - боевой профиль на локальной БД
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\set-db-mode.ps1" -Show
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\set-db-mode.ps1" -Mode "%~1" -Location "%~2"
if errorlevel 1 (
    echo [ERROR] Не удалось переключить режим.
    exit /b 1
)

echo  Запуск:  start_all.bat   ^(единый лаунчер для всех режимов^)
echo.
endlocal
