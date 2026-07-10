@echo off
chcp 65001 >nul
title Setup SSH key for CuteHost
cd /d "%~dp0"

echo ============================================
echo   SSH key setup (one-time)
echo   After this, tunnel works WITHOUT password
echo ============================================
echo.
echo You will enter ROOT SSH password ONCE (PuTTY password).
echo NOT the postgres password!
echo.

set "PUB=%USERPROFILE%\.ssh\id_ed25519.pub"
if not exist "%PUB%" set "PUB=%USERPROFILE%\.ssh\id_rsa.pub"
if not exist "%PUB%" (
    echo [ERROR] No SSH public key found.
    echo Create one: ssh-keygen -t ed25519
    pause
    exit /b 1
)

echo Public key: %PUB%
echo.
echo Copying key to root@207.154.219.208 ...
type "%PUB%" | ssh -o StrictHostKeyChecking=accept-new root@207.154.219.208 "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

if errorlevel 1 (
    echo.
    echo [ERROR] Failed. Use ROOT password from PuTTY, not postgres.
    pause
    exit /b 1
)

echo.
echo [OK] SSH key installed.
echo Test: start-ssh-cutehost.bat (should connect without password)
echo.
pause
