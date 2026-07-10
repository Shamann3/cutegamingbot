@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
  set "PY=venv\Scripts\python.exe"
) else (
  echo ERROR: Python venv not found. Expected .venv\Scripts\python.exe or venv\Scripts\python.exe
  pause
  exit /b 1
)

set /p UID=Telegram user_id: 
if "%UID%"=="" (
  echo ERROR: user_id is empty.
  pause
  exit /b 1
)

set /p SECRET=Authenticator secret key: 
if "%SECRET%"=="" (
  echo ERROR: secret key is empty.
  pause
  exit /b 1
)

echo.
echo Installing/checking required Python packages...
"%PY%" -m pip install asyncpg python-dotenv pyotp qrcode[pil] >nul
if errorlevel 1 (
  echo ERROR: Failed to install required packages.
  pause
  exit /b 1
)

echo Updating admin TOTP secret...
"%PY%" -c "import asyncio, sys, os; sys.path.insert(0, 'server'); from db import db; uid=int(os.environ['UID']); secret=os.environ['SECRET'].strip().replace(' ', '').upper(); exec('async def main():\n    await db.connect()\n    r = await db.pool.execute(\"UPDATE admin_accounts SET totp_secret = $1 WHERE user_id = $2\", secret, uid)\n    await db.close()\n    print(\"OK: updated\", r, \"for user_id\", uid, \"secret tail\", secret[-4:])\n'); asyncio.run(main())"
if errorlevel 1 (
  echo ERROR: Failed to update TOTP secret.
  pause
  exit /b 1
)

echo.
echo Done. Now open Login and enter a fresh 6-digit code from this Authenticator entry.
pause
