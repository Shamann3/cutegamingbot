@echo off
setlocal enabledelayedexpansion
title Reauth MAIN userbot - push - DigitalOcean

REM ============================================================
REM  Reauth the MAIN (text) userbot session and deploy it.
REM
REM  Steps:
REM    1. Log in a NEW session file main_userbot_session_new
REM       (you type phone + Telegram code + 2FA manually).
REM    2. Replace the old main_userbot_session with the new one.
REM    3. git add -f the session, commit, push to main
REM       -> DigitalOcean deploy_on_push rebuilds the bot.
REM
REM  The bot registers the MAIN userbot FIRST on startup; without
REM  it the withdraw userbot never comes up either.
REM
REM  WARNING: do NOT run main.py locally with this session while
REM  production uses it - one key from two IPs kills it.
REM ============================================================

cd /d "%~dp0"

echo(
echo ============================================================
echo   STEP 1/3 - log in the MAIN (UA) account (phone, code, 2FA)
echo ============================================================
echo(

py reauth_main_userbot.py
if errorlevel 1 (
    echo(
    echo [ERROR] Login script failed. Session NOT replaced, nothing pushed.
    pause
    exit /b 1
)

if not exist "main_userbot_session_new.session" (
    echo(
    echo [ERROR] New file main_userbot_session_new.session was not created. Abort.
    pause
    exit /b 1
)

echo(
echo ============================================================
echo   STEP 2/3 - replace the old session with the new one
echo ============================================================

if exist "main_userbot_session.session"          del /f /q "main_userbot_session.session"
if exist "main_userbot_session.session-journal"  del /f /q "main_userbot_session.session-journal"
move /y "main_userbot_session_new.session" "main_userbot_session.session" >nul
if errorlevel 1 (
    echo [ERROR] Could not rename the new session file. Abort.
    pause
    exit /b 1
)
echo   OK: main_userbot_session.session updated.

echo(
echo ============================================================
echo   STEP 3/3 - commit and push to GitHub (triggers DO deploy)
echo ============================================================
echo(
set /p CONFIRM=Push MAIN session to hosting? (y/n):
if /i not "%CONFIRM%"=="y" (
    echo   Cancelled. Session updated LOCALLY but NOT pushed.
    pause
    exit /b 0
)

git add -f "main_userbot_session.session"
git commit -m "chore: reauth main userbot session"
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
echo   DONE. Main session pushed, DigitalOcean will rebuild.
echo   Reminder: do NOT run main.py locally with this session
echo   while it runs in production.
echo ============================================================
pause
endlocal
