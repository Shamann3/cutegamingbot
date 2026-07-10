@echo off
chcp 65001 >nul
title CuteHost tunnel :15432
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\start-ssh-tunnel.ps1"
echo.
if errorlevel 1 (
    echo.
    echo === FIX ===
    echo 1. PuTTY as root, paste line from unify-root-password.txt
    echo 2. Or manual tunnel: putty-tunnel-guide.txt
    echo.
)
pause
