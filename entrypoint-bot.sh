#!/bin/sh
# Точка входа для main.py-воркера на DO.
# Конфигурация main.py живёт в корневом .env. Секреты не храним в образе —
# передаём через переменную DOTENV_B64 (base64 от содержимого .env), а контейнер
# при старте разворачивает её в /app/.env.
set -e

if [ -n "$DOTENV_B64" ]; then
  echo "$DOTENV_B64" | base64 -d > /app/.env
  echo "[bot] .env создан из DOTENV_B64 ($(wc -l < /app/.env) строк)"
else
  echo "[bot] WARNING: DOTENV_B64 не задан — main.py возьмёт дефолты (скорее всего неверные)"
fi

exec "$@"
