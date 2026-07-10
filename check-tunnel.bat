@echo off
chcp 65001 >nul
title Check SSH tunnel :15432
cd /d "%~dp0"

netstat -an | findstr /C:":15432" | findstr LISTENING >nul
if errorlevel 1 (
    echo [NO] Port 15432 is NOT listening.
    echo.
    echo Run start-main.bat  ^(plink auto^)
    echo Or WinSCP tunnel: Local 15432 -^> 127.0.0.1:5432
) else (
    echo [OK] SSH tunnel is active on port 15432.
    netstat -an | findstr /C:":15432" | findstr LISTENING
)
echo.
pause
