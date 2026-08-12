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

# Telethon userbot sessions must be baked into the image (see .dockerignore
# exceptions). Without them withdrawals stay offline forever.
for sess in main_userbot_session.session withdraw_userbot_session.session; do
  if [ -f "/app/$sess" ]; then
    echo "[bot] session OK: $sess ($(wc -c < "/app/$sess") bytes)"
  else
    echo "[bot] ERROR: missing /app/$sess — check .dockerignore allowlist + git force-add"
  fi
done

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

# Rolling deploy on DigitalOcean: old + new containers briefly overlap.
# If both Telethon sessions connect from different IPs, Telegram kills the
# auth key forever (AuthKeyDuplicatedError). Wait so the old worker can exit.
USERBOT_CONNECT_DELAY_SEC="${USERBOT_CONNECT_DELAY_SEC:-30}"
case "$USERBOT_CONNECT_DELAY_SEC" in
  ''|*[!0-9]*) USERBOT_CONNECT_DELAY_SEC=30 ;;
esac
if [ "$USERBOT_CONNECT_DELAY_SEC" -gt 0 ]; then
  echo "[bot] waiting ${USERBOT_CONNECT_DELAY_SEC}s before Telethon connect (avoid AuthKeyDuplicated on deploy)"
  sleep "$USERBOT_CONNECT_DELAY_SEC"
fi

# PID-1 = супервизор: soft-restart делает rolling handoff внутри контейнера
# (новый прогревается, старый ещё отвечает — как при деплое на DO).
# Без супервизора exit 0 ронял бы весь контейнер → долгий простой.
export SR_SUPERVISOR=1
export SR_DIR="${SR_DIR:-/tmp/cg_sr}"
echo "[bot] soft-restart supervisor → $*"
exec python -u /app/bot/runtime/sr_supervisor.py "$@"
