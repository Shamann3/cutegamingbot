@echo off
chcp 65001 >nul
title CF · Bots
cd /d "%~dp0server"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\start-bots.ps1"
