@echo off
timeout /t 3 /nobreak >nul
taskkill /F /IM Cursor.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul
taskkill /F /IM Cursor.exe /T >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_clean_cursor_state_after_kill.ps1"
