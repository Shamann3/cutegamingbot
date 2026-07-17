@echo off
setlocal enabledelayedexpansion
title Reauth withdraw userbot - push - DigitalOcean

REM ============================================================
REM  Reauth the withdraw userbot session and deploy it to DO.
REM
REM  Steps:
REM    1. Log in a NEW session file withdraw_userbot_session_new
REM       (you type phone + Telegram code + 2FA manually).
REM    2. Replace the old dead session with the new one.
REM    3. git add -f the session, commit, push to main
REM       -> DigitalOcean deploy_on_push rebuilds the bot.
REM
REM  WARNING: do NOT run main.py locally with this session while
REM  production on DO uses it - one key from two IPs kills it
REM  (AuthKeyDuplicatedError).
REM ============================================================

cd /d "%~dp0"

echo(
echo ============================================================
echo   STEP 1/3 - log in the withdraw account (phone, code, 2FA)
echo ============================================================
echo(

py reauth_withdraw_userbot.py
if errorlevel 1 (
    echo(
    echo [ERROR] Login script failed. Session NOT replaced, nothing pushed.
    pause
    exit /b 1
)

if not exist "withdraw_userbot_session_new.session" (
    echo(
    echo [ERROR] New file withdraw_userbot_session_new.session was not created. Abort.
    pause
    exit /b 1
)

echo(
echo ============================================================
echo   STEP 2/3 - replace the old session with the new one
echo ============================================================

if exist "withdraw_userbot_session.session"          del /f /q "withdraw_userbot_session.session"
if exist "withdraw_userbot_session.session-journal"  del /f /q "withdraw_userbot_session.session-journal"
move /y "withdraw_userbot_session_new.session" "withdraw_userbot_session.session" >nul
if errorlevel 1 (
    echo [ERROR] Could not rename the new session file. Abort.
    pause
    exit /b 1
)
echo   OK: withdraw_userbot_session.session updated.

echo(
echo ============================================================
echo   STEP 3/3 - commit and push to GitHub (triggers DO deploy)
echo ============================================================
echo(
echo   Will run: git add -f withdraw_userbot_session.session
echo             git commit + git push origin main
echo(
set /p CONFIRM=Push session to hosting? (y/n):
if /i not "%CONFIRM%"=="y" (
    echo   Cancelled. Session updated LOCALLY but NOT pushed.
    pause
    exit /b 0
)

git add -f "withdraw_userbot_session.session"
git commit -m "chore: reauth withdraw userbot session"
if errorlevel 1 (
    echo [WARN] git commit committed nothing (file may be unchanged).
)
git push origin main
if errorlevel 1 (
    echo [ERROR] git push failed. Check repository access.
    pause
    exit /b 1
)

echo(
echo ============================================================
echo   DONE. Session pushed, DigitalOcean will rebuild the bot.
echo   Reminder: do NOT run main.py locally with this session
echo   while it runs in production.
echo ============================================================
pause
endlocal
