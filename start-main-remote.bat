@echo off
chcp 65001 >nul
title CF · MAIN remote (CuteHost SSH)
cd /d "%~dp0"

echo ============================================
echo   MAIN mode — remote CuteHost via SSH
echo   Needs root SSH password for 207.154.219.208
echo ============================================
echo.

start "CuteHost SSH :15432" cmd /k "%~dp0start-ssh-cutehost.bat"

echo Waiting for SSH tunnel (enter root password in the other window)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$deadline = (Get-Date).AddSeconds(120); " ^
  "while ((Get-Date) -lt $deadline) { " ^
  "  if (Get-NetTCPConnection -LocalPort 15432 -State Listen -ErrorAction SilentlyContinue) { exit 0 }; " ^
  "  Start-Sleep 2; Write-Host -NoNewline '.' " ^
  "}; exit 1"

if errorlevel 1 (
    echo.
    echo [ERROR] SSH tunnel failed. Use MAIN_DB_TARGET=local in server/.env instead.
    pause
    exit /b 1
)

echo.
echo [OK] Tunnel ready. Starting API server...
set CF_TUNNEL_READY=1
set CF_FORCE_REMOTE=1
call "%~dp0start-1-server.bat"
