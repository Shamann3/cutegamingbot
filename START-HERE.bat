@echo off
chcp 65001 >nul
title START HERE
cd /d "%~dp0"
start "" notepad "%~dp0WINSCP-GUIDE.txt"
echo Opening WINSCP-GUIDE.txt ...
echo.
echo Quick: WinSCP tunnel 15432 -^> 127.0.0.1:5432, login, then start-with-winscp.bat
pause
