@echo off
chcp 65001 >nul
title Test CuteHost DB password
cd /d "%~dp0server"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\test-cutehost-db.ps1"
