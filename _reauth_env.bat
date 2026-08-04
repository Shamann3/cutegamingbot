@echo off
REM Shared helper for reauth-*.bat. Sets PYTHON_CMD (needs telethon).

set "PYTHON_CMD="

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import telethon" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
        goto :python_ok
    )
    py -c "import telethon" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py"
        goto :python_ok
    )
)

where python >nul 2>&1
if not errorlevel 1 (
    python -c "import telethon" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
        goto :python_ok
    )
)

where python3 >nul 2>&1
if not errorlevel 1 (
    python3 -c "import telethon" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=python3"
        goto :python_ok
    )
)

echo [ERROR] Python + telethon not found.
echo         Install: pip install telethon
exit /b 1

:python_ok
echo   Python: %PYTHON_CMD%
exit /b 0
