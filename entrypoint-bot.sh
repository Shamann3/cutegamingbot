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

# Локальный Redis в этом же контейнере — бот по умолчанию ждёт его на
# 127.0.0.1:6379. Чистый кэш: без RDB/AOF (--save "" --appendonly no),
# с потолком памяти и вытеснением, чтобы не съесть RAM контейнера.
# Потеря данных при рестарте не важна — это кэш/снапшоты, бот их пересоберёт.
redis-server \
  --daemonize yes \
  --bind 127.0.0.1 \
  --port 6379 \
  --save "" \
  --appendonly no \
  --maxmemory 512mb \
  --maxmemory-policy allkeys-lru \
  --protected-mode no \
  --dir /tmp
echo "[bot] redis-server запущен на 127.0.0.1:6379 (кэш, без персистентности, maxmemory 512mb)"

exec "$@"
