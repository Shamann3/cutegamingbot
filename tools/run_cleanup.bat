@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0safe_disk_cleanup_run.ps1" > "%~dp0cleanup_stdout.txt" 2>&1
echo EXIT=%ERRORLEVEL%>> "%~dp0cleanup_stdout.txt"
