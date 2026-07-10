# Продакшен на DigitalOcean

Единый гайд по деплою Cute Farming. Локальная разработка — скрипты в корне (`start-dev.ps1`, `start-*.bat`); продакшен — этот документ.

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│  DigitalOcean App Platform                                  │
│                                                             │
│  Static Site: game     Static Site: admin                   │
│  (Vite build dist/)    (admin/dist/)                        │
│         │                      │                            │
│         └──────────┬───────────┘                            │
│                    ▼                                        │
│            Web Service: api                                 │
│            server/Dockerfile → uvicorn :8000                │
│                    │                                        │
│         ┌──────────┴──────────┐                             │
│         ▼                     ▼                             │
│  Worker: bots          Managed PostgreSQL                   │
│  bots_runner.py        (SSL, DATABASE_URL)                  │
└─────────────────────────────────────────────────────────────┘
         ▲                     ▲
         │                     │
    Telegram game-bot      Telegram admin-bot
```

| Компонент | Что деплоить | Команда / путь |
|-----------|--------------|----------------|
| API | Web Service | `server/Dockerfile`, порт `8000`, health `/health` |
| Боты | Worker (опционально) | `python bots_runner.py` |
| Игра | Static Site | `npm run build` → `dist/` |
| Админка | Static Site | `npm run build --prefix admin` → `admin/dist/` |
| БД | Managed PostgreSQL | Привязать к App, `DATABASE_URL` |

---

## Быстрый чеклист

1. [ ] Managed PostgreSQL в том же регионе, что и App
2. [ ] Web Service `api` из `server/Dockerfile`
3. [ ] Worker `bots` (если нужны Telegram-боты на сервере)
4. [ ] Static Site для игры + Static Site для `/panel/`
5. [ ] Env vars на API (см. ниже)
6. [ ] `VITE_API_URL` при сборке фронтов
7. [ ] Webhook URL ботов → публичный URL API (если боты на DO)
8. [ ] `schema.sql` применён к БД
9. [ ] `PRODUCTION=true`, `ALLOW_DEV_AUTH=false`

---

## 1. База данных

```bash
psql "$DATABASE_URL" -f server/schema.sql
```

Для Managed DB включите SSL: `DB_SSL=true` или используйте `DATABASE_URL` из панели DO (SSL уже в строке).

---

## 2. API (Web Service)

**Build:** Dockerfile path → `server/Dockerfile`  
**HTTP port:** `8000`  
**Health check:** `/health`  
**Run command** (по умолчанию в Dockerfile):

```bash
python -m uvicorn app:app --host 0.0.0.0 --port $PORT --workers ${UVICORN_WORKERS:-2}
```

### Обязательные переменные (API)

```env
PRODUCTION=true
ALLOW_DEV_AUTH=false

DATABASE_URL=postgresql://...
DB_SSL=true

BOT_TOKEN=
WEBAPP_URL=https://your-game.ondigitalocean.app
ADMIN_BOT_TOKEN=
ADMIN_WEBAPP_URL=https://your-admin.ondigitalocean.app/panel/

FRONTEND_ORIGIN=https://your-game.ondigitalocean.app
ADMIN_FRONTEND_ORIGIN=https://your-admin.ondigitalocean.app

ADMIN_ENABLED=true
ADMIN_USER_IDS=123456789
ADMIN_JWT_SECRET=          # openssl rand -hex 32
ADMIN_INVITE_KEY=
ADMIN_LOGIN_KEY=

UVICORN_WORKERS=2
DB_POOL_MIN=5
DB_POOL_MAX=50
SSE_MAX_CONNECTIONS=500
SSE_MAX_PER_USER=2
GAME_EVENTS_RETENTION_DAYS=90
GAME_EVENTS_MAX_PENDING=200
GAME_EVENTS_INSERT_CONCURRENCY=12
```

### Рекомендуемые для фронта (build-time)

В корне проекта (`.env` при `npm run build`):

```env
VITE_API_URL=https://your-api.ondigitalocean.app
VITE_FARM_POLL_MS=15000
```

В `admin/.env` при сборке админки:

```env
VITE_ADMIN_API_PREFIX=https://your-api.ondigitalocean.app/admin/api
```

---

## 3. Worker: боты

Отдельный компонент App Platform:

- **Тот же** `server/Dockerfile`
- **Run command:** `python bots_runner.py`
- **Те же** env vars, что у API (BOT_TOKEN, DATABASE_URL, …)

Локально боты: `server/start-bots.ps1` или `server/start-bot.ps1` (только игровой).

---

## 4. Статика (игра + админка)

### Игра

```bash
npm ci
# .env с VITE_API_URL
npm run build
```

Деплой содержимого `dist/` как Static Site. `serve.json` в `public/` уже настроен для SPA.

### Админка

```bash
cd admin && npm ci && npm run build
```

Деплой `admin/dist/`. В App Platform укажите route `/panel` или отдельный поддомен.

---

## 5. Docker Compose (Droplet / локальный prod-like)

Из корня репозитория:

```bash
cp server/.env.example server/.env   # заполнить секреты
docker compose up -d --build
```

| Сервис | Порт | Описание |
|--------|------|----------|
| `postgres` | 5432 | Локальная БД (для prod лучше Managed DB) |
| `api` | 8000 | FastAPI |
| `bots` | — | Оба Telegram-бота |

Проверка: `curl http://localhost:8000/health`

---

## 6. Локальная разработка (скрипты)

| Скрипт | Назначение |
|--------|------------|
| `start-dev.ps1` | **Главный** — API → Vite → ngrok → боты (по очереди) |
| `start-dev.bat` / `start-dev-local.bat` | Обёртки для Windows |
| `start-1-server.bat` | Только FastAPI `:8000` |
| `start-2-vite.bat` | Только Vite `:5173` |
| `start-3-ngrok.bat` | ngrok для Telegram Web App |
| `start-4-bots.bat` | Оба бота |
| `server/start-server.ps1` | API из `server/` |
| `server/start-bots.ps1` | Боты из `server/` |

Подробности локального `.env` — в `README.md` и `server/.env.example`.

---

## 7. Масштабирование (ориентиры)

| Онлайн | Настройки |
|--------|-----------|
| ~50 | `UVICORN_WORKERS=2`, `DB_POOL_MAX=50`, poll 15–20 с |
| ~500 | Redis для rate-limit/SSE, LB, больше workers |
| 5k+ registered | Managed PG с репликой, отдельный worker для рассылок |

In-memory состояние (rate limit, SSE hub, shop cache) **не шарится** между workers — при `UVICORN_WORKERS > 1` это ожидаемо; для строгой консистентности нужен Redis.

---

## 8. Railway (legacy)

`server/railway.json` остаётся для совместимости. Новый деплой — **DigitalOcean** (Dockerfile + App Platform). При миграции с Railway перенесите env vars и `schema.sql`, обновите `WEBAPP_URL` / CORS origins.

---

## 9. После деплоя

1. `GET /health` → `200`
2. `GET /api/status` — режим обслуживания, версия
3. Открыть игру в Telegram → ферма грузится
4. `/panel/` → вход админа + TOTP
5. Тестовая покупка / сбор урожая — баланс обновляется
6. Логи API и worker без ошибок подключения к БД
