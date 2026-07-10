@echo off
chcp 65001 >nul
title CF · ngrok
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-tunnel.ps1"
