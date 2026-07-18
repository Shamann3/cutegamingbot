@echo off
setlocal enabledelayedexpansion
title Reauth BOTH userbots (UA main + NO withdraw) - push - DigitalOcean

REM ============================================================
REM  Reauth BOTH userbot sessions in one go, then deploy.
REM
REM  Order matters: the bot registers the MAIN (UA) userbot first
REM  on startup, and only then the WITHDRAW (NO) one. So we log in
REM  MAIN first, WITHDRAW second, then push both together.
REM
REM  You type phone + code + 2FA manually for EACH account.
REM
REM  TIP against the "code was shared" block: on each phone first do
REM  Settings -> Devices -> Terminate all other sessions, so the
REM  login code arrives by SMS.
REM
REM  WARNING: do NOT run main.py locally with these sessions while
REM  production uses them - one key from two IPs kills it.
REM ============================================================

cd /d "%~dp0"

echo(
echo ############################################################
echo #  1/5 - LOG IN MAIN (Ukrainian) account
echo #        enter UA phone + code + 2FA
echo ############################################################
echo(

py reauth_main_userbot.py
if errorlevel 1 (
    echo(
    echo [ERROR] MAIN login failed. Nothing replaced, nothing pushed.
    pause
    exit /b 1
)
if not exist "main_userbot_session_new.session" (
    echo [ERROR] main_userbot_session_new.session was not created. Abort.
    pause
    exit /b 1
)

echo(
echo ############################################################
echo #  2/5 - LOG IN WITHDRAW (Norwegian +4796751305) account
echo #        enter NO phone + code + 2FA
echo ############################################################
echo(

py reauth_withdraw_userbot.py
if errorlevel 1 (
    echo(
    echo [ERROR] WITHDRAW login failed. MAIN not replaced, nothing pushed.
    echo         Re-run the batch to try again.
    if exist "main_userbot_session_new.session" del /f /q "main_userbot_session_new.session"
    pause
    exit /b 1
)
if not exist "withdraw_userbot_session_new.session" (
    echo [ERROR] withdraw_userbot_session_new.session was not created. Abort.
    if exist "main_userbot_session_new.session" del /f /q "main_userbot_session_new.session"
    pause
    exit /b 1
)

echo(
echo ############################################################
echo #  3/5 - replace MAIN session file
echo ############################################################
if exist "main_userbot_session.session"          del /f /q "main_userbot_session.session"
if exist "main_userbot_session.session-journal"  del /f /q "main_userbot_session.session-journal"
move /y "main_userbot_session_new.session" "main_userbot_session.session" >nul
if errorlevel 1 (
    echo [ERROR] Could not rename MAIN session. Abort.
    pause
    exit /b 1
)
echo   OK: main_userbot_session.session updated.

echo(
echo ############################################################
echo #  4/5 - replace WITHDRAW session file
echo ############################################################
if exist "withdraw_userbot_session.session"          del /f /q "withdraw_userbot_session.session"
if exist "withdraw_userbot_session.session-journal"  del /f /q "withdraw_userbot_session.session-journal"
move /y "withdraw_userbot_session_new.session" "withdraw_userbot_session.session" >nul
if errorlevel 1 (
    echo [ERROR] Could not rename WITHDRAW session. Abort.
    pause
    exit /b 1
)
echo   OK: withdraw_userbot_session.session updated.

echo(
echo ############################################################
echo #  5/5 - commit and push BOTH sessions (triggers DO deploy)
echo ############################################################
echo(
set /p CONFIRM=Push BOTH sessions to hosting? (y/n):
if /i not "%CONFIRM%"=="y" (
    echo   Cancelled. Sessions updated LOCALLY but NOT pushed.
    pause
    exit /b 0
)

git add -f "main_userbot_session.session" "withdraw_userbot_session.session"
git commit -m "chore: reauth main + withdraw userbot sessions"
if errorlevel 1 (
    echo [WARN] git commit committed nothing (files may be unchanged).
)
git push origin main
if errorlevel 1 (
    echo [ERROR] git push failed. Check repository access.
    pause
    exit /b 1
)

echo(
echo ############################################################
echo #  DONE. Both sessions pushed, DigitalOcean will rebuild.
echo #  Reminder: do NOT run main.py locally with these sessions
echo #  while they run in production.
echo ############################################################
pause
endlocal
