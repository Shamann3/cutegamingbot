@echo off
chcp 65001 >nul
title Support Bot · TEST
cd /d "%~dp0"

findstr /B /C:"APP_MODE=test" "%~dp0.env" >nul 2>&1
if errorlevel 1 (
    call "%~dp0set-mode.bat" test >nul 2>&1
    echo [INFO] APP_MODE=test
    echo.
)

call "%~dp0start.bat"
if errorlevel 1 pause
