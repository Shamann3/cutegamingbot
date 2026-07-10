@echo off
cd /d %~dp0

if not exist .venv\Scripts\python.exe (
  echo Создаю venv на Python 3.12...
  py -3.12 -m venv .venv
  .venv\Scripts\pip install -r requirements-server.txt
)

echo.
echo Сервер: bore.pub
echo Остановка: Ctrl+C
echo.

REM Важно: python из .venv, НЕ глобальный uvicorn
.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
