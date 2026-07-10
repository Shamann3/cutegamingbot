@echo off
chcp 65001 >nul
title Server (tunnel must be open)
cd /d "%~dp0"

netstat -an | findstr /C:":15432" | findstr LISTENING >nul
if errorlevel 1 (
    echo.
    echo [ERROR] Port 15432 is not open.
    echo.
    echo Open PuTTY tunnel first - see putty-tunnel-guide.txt
    echo   Source 15432  Destination 127.0.0.1:5432
    echo   Login as root, keep PuTTY open
    echo.
    echo Then run this file again.
    pause
    exit /b 1
)

echo [OK] Tunnel detected on :15432
set CF_TUNNEL_READY=1
call "%~dp0start-1-server.bat"
pause
