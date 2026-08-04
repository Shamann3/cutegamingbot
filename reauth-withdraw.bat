@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Reauth withdraw userbot - push - DigitalOcean

REM ASCII-only bat. Russian prompts live in the .py scripts.
REM Do NOT run main.py locally with this session while production uses it.

cd /d "%~dp0"

echo.
echo ============================================================
echo   WITHDRAW REAUTH
echo ============================================================
echo.

call "%~dp0_reauth_env.bat"
if errorlevel 1 (
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   STEP 1/3 - login withdraw account [phone/code/2FA]
echo ============================================================
echo.

%PYTHON_CMD% reauth_withdraw_userbot.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] Login failed. Old session kept. Nothing pushed.
    echo         Retry: reauth-withdraw.bat --fresh
    pause
    exit /b 1
)

if not exist "withdraw_userbot_session_new.session" (
    echo.
    echo [ERROR] withdraw_userbot_session_new.session was not created.
    pause
    exit /b 1
)

for %%A in ("withdraw_userbot_session_new.session") do set "NEWSIZE=%%~zA"
if !NEWSIZE! LSS 64 (
    echo [ERROR] Session file too small: !NEWSIZE! bytes
    pause
    exit /b 1
)
echo   OK: new session !NEWSIZE! bytes

echo.
echo ============================================================
echo   STEP 2/3 - replace old session file
echo ============================================================

if exist "withdraw_userbot_session.session"          del /f /q "withdraw_userbot_session.session"
if exist "withdraw_userbot_session.session-journal"  del /f /q "withdraw_userbot_session.session-journal"
if exist "withdraw_userbot_session.session-shm"      del /f /q "withdraw_userbot_session.session-shm"
if exist "withdraw_userbot_session.session-wal"      del /f /q "withdraw_userbot_session.session-wal"
move /y "withdraw_userbot_session_new.session" "withdraw_userbot_session.session" >nul
if errorlevel 1 (
    echo [ERROR] Could not rename session file.
    pause
    exit /b 1
)
echo   OK: withdraw_userbot_session.session updated

echo.
echo ============================================================
echo   STEP 3/3 - git commit + push [DigitalOcean deploy]
echo ============================================================
echo.
set /p CONFIRM=Push session to hosting? [y/n]: 
if /i not "!CONFIRM!"=="y" (
    echo   Cancelled. Session updated LOCALLY only.
    pause
    exit /b 0
)

git add -f "withdraw_userbot_session.session"
git status --short -- "withdraw_userbot_session.session"
git commit -m "chore: reauth withdraw userbot session"
if errorlevel 1 (
    echo [WARN] Empty commit - file may be unchanged for git.
)
git push -u origin HEAD
if errorlevel 1 (
    echo [ERROR] git push failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   DONE. Session pushed. Wait for DigitalOcean rebuild.
echo   Do NOT run main.py locally with this session in parallel.
echo ============================================================
pause
endlocal
