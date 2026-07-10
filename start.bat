@echo off

setlocal EnableExtensions

cd /d "%~dp0"

chcp 65001 >nul 2>&1



set "PYTHON="

if exist "venv\Scripts\python.exe" (

    "venv\Scripts\python.exe" -c "import sys; sys.exit(0)" >nul 2>&1

    if not errorlevel 1 set "PYTHON=venv\Scripts\python.exe"

)

if not defined PYTHON (

    where py >nul 2>&1

    if not errorlevel 1 set "PYTHON=py -3"

)

if not defined PYTHON set "PYTHON=python"



echo [start] Python: %PYTHON%

if exist ".env" (

    for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"APP_MODE=" ".env"') do echo [start] .env APP_MODE=%%B

)



%PYTHON% scripts\test_db_connection.py

if errorlevel 1 (

    echo.

    echo [start] Проверка БД не прошла. Бот не запускается.

    echo         test: start-test.bat  ^(локальная cutebase :5432^)

    echo         main: start-main.bat  ^(SSH-туннель :15432^)

    echo              или start-with-winscp.bat

    pause

    exit /b 1

)



set DB_TUNNEL_SKIP_WAIT=1

%PYTHON% main.py

set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" pause

exit /b %EXIT_CODE%

