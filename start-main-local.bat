@echo off
chcp 65001 >nul
title CF · MAIN local (без SSH)
cd /d "%~dp0"

echo ============================================
echo   Локальный main БЕЗ SSH (только отладка)
echo   В server/.env поставь: MAIN_DB_TARGET=local
echo   и DB_PORT_MAIN=5432
echo ============================================
echo.
pause
