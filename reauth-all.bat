@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Reauth BOTH userbots - push - DigitalOcean

REM ASCII-only bat. Russian prompts live in the .py scripts.
REM Order: MAIN first, then WITHDRAW, then one push.

cd /d "%~dp0"

echo.
echo ############################################################
echo #  REAUTH BOTH - MAIN then WITHDRAW
echo ############################################################
echo.

call "%~dp0_reauth_env.bat"
if errorlevel 1 (
    pause
    exit /b 1
)

echo.
echo ############################################################
echo #  1/5 - LOGIN MAIN [phone/code/2FA]
echo ############################################################
echo.

%PYTHON_CMD% reauth_main_userbot.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] MAIN login failed. Nothing replaced. Nothing pushed.
    pause
    exit /b 1
)
if not exist "main_userbot_session_new.session" (
    echo [ERROR] main_userbot_session_new.session was not created.
    pause
    exit /b 1
)

echo.
echo ############################################################
echo #  2/5 - LOGIN WITHDRAW [+4796751305 code/2FA]
echo ############################################################
echo.

%PYTHON_CMD% reauth_withdraw_userbot.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] WITHDRAW login failed. MAIN not replaced. Nothing pushed.
    if exist "main_userbot_session_new.session" del /f /q "main_userbot_session_new.session"
    pause
    exit /b 1
)
if not exist "withdraw_userbot_session_new.session" (
    echo [ERROR] withdraw_userbot_session_new.session was not created.
    if exist "main_userbot_session_new.session" del /f /q "main_userbot_session_new.session"
    pause
    exit /b 1
)

echo.
echo ############################################################
echo #  3/5 - replace MAIN session
echo ############################################################
if exist "main_userbot_session.session"          del /f /q "main_userbot_session.session"
if exist "main_userbot_session.session-journal"  del /f /q "main_userbot_session.session-journal"
if exist "main_userbot_session.session-shm"      del /f /q "main_userbot_session.session-shm"
if exist "main_userbot_session.session-wal"      del /f /q "main_userbot_session.session-wal"
move /y "main_userbot_session_new.session" "main_userbot_session.session" >nul
if errorlevel 1 (
    echo [ERROR] Could not rename MAIN session.
    pause
    exit /b 1
)
echo   OK: main_userbot_session.session

echo.
echo ############################################################
echo #  4/5 - replace WITHDRAW session
echo ############################################################
if exist "withdraw_userbot_session.session"          del /f /q "withdraw_userbot_session.session"
if exist "withdraw_userbot_session.session-journal"  del /f /q "withdraw_userbot_session.session-journal"
if exist "withdraw_userbot_session.session-shm"      del /f /q "withdraw_userbot_session.session-shm"
if exist "withdraw_userbot_session.session-wal"      del /f /q "withdraw_userbot_session.session-wal"
move /y "withdraw_userbot_session_new.session" "withdraw_userbot_session.session" >nul
if errorlevel 1 (
    echo [ERROR] Could not rename WITHDRAW session.
    pause
    exit /b 1
)
echo   OK: withdraw_userbot_session.session

echo.
echo ############################################################
echo #  5/5 - git commit + push both sessions
echo ############################################################
echo.
set /p CONFIRM=Push BOTH sessions to hosting? [y/n]: 
if /i not "!CONFIRM!"=="y" (
    echo   Cancelled. Sessions updated LOCALLY only.
    pause
    exit /b 0
)

git add -f "main_userbot_session.session" "withdraw_userbot_session.session"
git status --short -- "main_userbot_session.session" "withdraw_userbot_session.session"
git commit -m "chore: reauth main + withdraw userbot sessions"
if errorlevel 1 (
    echo [WARN] Empty commit - files may be unchanged for git.
)
git push -u origin HEAD
if errorlevel 1 (
    echo [ERROR] git push failed.
    pause
    exit /b 1
)

echo.
echo ############################################################
echo #  DONE. Both sessions pushed. Wait for DigitalOcean.
echo #  Do NOT run main.py locally with these sessions in parallel.
echo ############################################################
pause
endlocal
