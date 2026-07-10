@echo off
setlocal

cd /d "%~dp0"

if exist "server\.venv\Scripts\python.exe" (
  set "PY=server\.venv\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
  set "PY=venv\Scripts\python.exe"
) else (
  echo ERROR: Python venv not found.
  pause
  exit /b 1
)

set /p UID=Telegram user_id: 
if "%UID%"=="" (
  echo ERROR: user_id is empty.
  pause
  exit /b 1
)

set /p CODE=6-digit code from Authenticator: 
if "%CODE%"=="" (
  echo ERROR: code is empty.
  pause
  exit /b 1
)

"%PY%" scripts\debug_admin_register_code.py "%UID%" "%CODE%"

pause
