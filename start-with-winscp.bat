@echo off
chcp 65001 >nul
title WinSCP + CuteHost
cd /d "%~dp0"

echo.
echo  ============================================================
echo    CUTEHOST через WinSCP
echo  ============================================================
echo.
echo  1. WinSCP -^> сессия 207.154.219.208 -^> Advanced -^> Tunnel
echo     Local 15432 -^> 127.0.0.1:5432
echo     Login и НЕ ЗАКРЫВАЙ WinSCP
echo.
echo  2. check-tunnel.bat
echo.
echo  3. start-main.bat  или  start.bat
echo  ============================================================
echo.

netstat -an | findstr /C:":15432" | findstr LISTENING >nul
if errorlevel 1 (
    echo  [!] Port 15432 is NOT open yet.
    echo      Connect WinSCP with tunnel first.
    echo.
    pause
    exit /b 1
)

echo  [OK] Tunnel port 15432 is open.
echo.
choice /C YN /M "Start support bot now"
if errorlevel 2 exit /b 0

call "%~dp0start.bat"
if errorlevel 1 pause
