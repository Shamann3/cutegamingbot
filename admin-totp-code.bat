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

echo.
echo Installing/checking required Python packages...
"%PY%" -m pip install asyncpg python-dotenv pyotp qrcode[pil] >nul
if errorlevel 1 (
  echo ERROR: Failed to install required packages.
  pause
  exit /b 1
)

echo Reading current admin TOTP secret and generating code...
"%PY%" -c "import asyncio, sys, os, time; sys.path.insert(0, 'server'); from db import db; from admin_auth import resolve_totp_secret; import pyotp; uid=int(os.environ['UID']); exec('async def main():\n    await db.connect()\n    row = await db.pool.fetchrow(\"SELECT user_id, role, status, totp_secret FROM admin_accounts WHERE user_id = $1\", uid)\n    await db.close()\n    if not row:\n        print(\"ERROR: admin account not found for user_id\", uid)\n        return\n    secret = resolve_totp_secret(row[\"totp_secret\"] or \"\", generate_if_invalid=False)\n    if not secret:\n        print(\"ERROR: invalid totp_secret in database\")\n        return\n    totp = pyotp.TOTP(secret, digits=6, interval=30)\n    now = int(time.time())\n    left = 30 - (now %% 30)\n    print(\"user_id:\", uid)\n    print(\"role/status:\", row[\"role\"], row[\"status\"])\n    print(\"secret tail:\", secret[-4:])\n    print(\"CURRENT LOGIN CODE:\", totp.now())\n    print(\"seconds left:\", left)\n    print(\"Use this code immediately in the Login tab.\")\n'); asyncio.run(main())"
if errorlevel 1 (
  echo ERROR: Failed to generate TOTP code.
  pause
  exit /b 1
)

echo.
pause
