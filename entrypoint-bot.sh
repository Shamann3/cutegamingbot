#!/bin/sh
# Точка входа для main.py-воркера на DO.
# Секреты и настройки теперь передаются напрямую через переменные окружения (из app.yaml).
# Файл .env создавать не нужно — всё уже в окружении контейнера.
set -e

# (Блок DOTENV_B64 удалён полностью)

# Telethon userbot sessions must be baked into the image (see .dockerignore
# exceptions). Without them withdrawals stay offline forever.
for sess in main_userbot_session.session withdraw_userbot_session.session; do
  if [ -f "/app/$sess" ]; then
    echo "[bot] session OK: $sess ($(wc -c < "/app/$sess") bytes)"
  else
    echo "[bot] ERROR: missing /app/$sess — check .dockerignore allowlist + git force-add"
  fi
done

# Локальный Redis: здесь живут GameStore/кнопки (gameskosti, greq/prep, BLC).
# БЕЗ AOF после рестарта контейнера все inline-кнопки «умирают» — сессии пустые.
# AOF everysec + лёгкий RDB: переживаем .r и рестарт контейнера; maxmemory с LRU.
mkdir -p /tmp/redis-data
redis-server \
  --daemonize yes \
  --bind 127.0.0.1 \
  --port 6379 \
  --dir /tmp/redis-data \
  --save 60 1000 \
  --appendonly yes \
  --appendfsync everysec \
  --maxmemory 512mb \
  --maxmemory-policy allkeys-lru \
  --protected-mode no
echo "[bot] redis-server 127.0.0.1:6379 (AOF everysec + RDB, maxmemory 512mb) — кнопки переживают рестарт"

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