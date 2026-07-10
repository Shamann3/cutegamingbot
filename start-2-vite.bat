@echo off
chcp 65001 >nul
title CF · Vite :5173
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-vite.ps1"
