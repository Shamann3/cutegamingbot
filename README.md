# Cute Farming — документация проекта

Telegram Web App игра-ферма с магазином, биржей, крафтом, квестами и полной админ-панелью.

---

## Содержание

1. [Структура проекта](#структура-проекта)
2. [Локальный запуск](#локальный-запуск)
3. [Деплой на хостинг](#деплой-на-хостинг)
4. [Переменные окружения](#переменные-окружения)
5. [Что включать и выключать](#что-включать-и-выключать)
6. [База данных — все таблицы](#база-данных)
7. [Файлы сервера](#файлы-сервера)
8. [Фронтенд](#фронтенд)

---

## Структура проекта

```
cutefarmer/
├── server/                 # Python бэкенд (FastAPI)
│   ├── app.py              # Точка входа API
│   ├── db.py               # Пул соединений, все игровые операции
│   ├── schema.sql          # Вся схема PostgreSQL
│   ├── .env                # Секреты (не коммитить!)
│   ├── .env.example        # Шаблон .env
│   └── *.py                # Остальные модули
├── src/                    # React фронтенд (основной webapp)
├── admin/                  # React фронтенд (админ webapp)
├── panel/                  # HTML-файлы панели (staff.html и др.)
├── public/                 # Статика игры
├── dist/                   # Собранная игра (после npm run build)
├── deploy/
│   └── digitalocean.md     # Инструкция деплоя на DigitalOcean
├── docker-compose.yml      # Docker для prod-подобного запуска
├── start-dev.ps1           # Главный скрипт локального запуска
├── start-dev.bat           # Обёртка для Windows
├── start-1-server.bat      # Запуск API
├── start-2-vite.bat        # Только фронтенд
├── start-3-ngrok.bat       # ngrok
└── start-4-bots.bat        # Запуск ботов
```

---

## Локальный запуск

### Что нужно установить

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ 
- ngrok 

### Шаг 1 — Скопировать и заполнить .env

```bash
cd server
copy .env.example .env
```

Открой `server/.env` и замени следующее (всё остальное можно не трогать):

```env
# ======================================================
# БОГДАН — вот что нужно поменять для локальной работы:
# ======================================================

# 1. Пароль от своей локальной PostgreSQL (который ставил при установке)
DB_PASSWORD=сюда_свой_пароль

# 2. Свой Telegram ID (узнать можно у бота @userinfobot)
ADMIN_USER_IDS=сюда_свой_telegram_id
VITE_DEV_USER_ID=сюда_свой_telegram_id   # это в корневом .env (не в server/.env)

# 3. Токены ботов — создать в @BotFather
#    Нужно 3 отдельных бота: игровой, admin, поддержка
BOT_TOKEN=токен_игрового_бота
ADMIN_BOT_TOKEN=токен_admin_бота
SUPPORT_BOT_TOKEN=токен_бота_поддержки

# 4. Эти можно оставить любыми для локальной разработки
ADMIN_LOGIN_KEY=bogdan_local_key
ADMIN_JWT_SECRET=bogdan_local_secret_32chars_minimum

# ======================================================
# ЭТО НЕ ТРОГАТЬ — оставить как есть для локалки:
# ======================================================
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_SSL=false
ALLOW_DEV_AUTH=true
PRODUCTION=false
ADMIN_ENABLED=true
```

> Также создай файл `.env` в **корне проекта** (рядом с `package.json`) с одной строкой:
> ```env
> VITE_DEV_USER_ID=сюда_свой_telegram_id
> ```

### Шаг 2 — Установить Python зависимости

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Шаг 3 — Установить Node.js зависимости

```bash
# В корне проекта (игра)
npm install

# Для админ-панели
cd admin && npm install
```

### Шаг 4 — Запустить всё (Windows)

```powershell
# Открывает 4 окна по очереди: API → Vite → ngrok → боты
.\start-dev.ps1
```

Или по одному:

| Скрипт | Что запускает |
|--------|---------------|
| `start-1-server.bat` | FastAPI на порту 8000 |
| `start-2-vite.bat` | Фронтенд на порту 5173 |
| `start-3-ngrok.bat` | ngrok туннель (нужен для Telegram) |
| `start-4-bots.bat` | Все три Telegram-бота |

### Шаг 5 — Прописать ngrok URL

После запуска ngrok скопируй HTTPS URL (вида `https://xxxx.ngrok-free.app`) в `server/.env`:

```env
WEBAPP_URL=https://xxxx.ngrok-free.app
ADMIN_WEBAPP_URL=https://xxxx.ngrok-free.app/panel/
```

Перезапусти API.

### Адреса при локальной разработке

| Что | URL |
|-----|-----|
| API | http://127.0.0.1:8000 |
| Игра в браузере | http://127.0.0.1:5173 |
| Админ-панель | http://127.0.0.1:5173/panel/ |
| Health check | http://127.0.0.1:8000/health |

> Для открытия в Telegram нужен ngrok — Telegram принимает только HTTPS.
> В браузере напрямую работает при `ALLOW_DEV_AUTH=true` и `VITE_DEV_USER_ID=твой_id`.

---

## Деплой на хостинг

### DigitalOcean App Platform (рекомендуется)

Полный гайд: `deploy/digitalocean.md`

**Кратко:**

1. Создать **Managed PostgreSQL** в том же регионе что и App
2. Применить схему БД:
   ```bash
   psql "$DATABASE_URL" -f server/schema.sql
   ```
3. Создать **Web Service** (API):
   - Dockerfile: `server/Dockerfile`
   - Port: `8000`
   - Health check: `/health`
4. Создать **Worker** (боты):
   - Тот же `server/Dockerfile`
   - Run command: `python bots_runner.py`
5. Создать **Static Site** (игра):
   ```bash
   npm run build    # результат → dist/
   ```
6. Создать **Static Site** (админка):
   ```bash
   cd admin && npm run build    # результат → admin/dist/
   ```
7. Выставить все env vars в панели DO (см. раздел ниже)

### Что поменять в .env при деплое на хостинг

```env
# ======================================================
# БОГДАН - что нужно поменять при деплое на хостинг:
# ======================================================

# 1. URL базы данных от хостинга (DigitalOcean вроде должен дать url)
DATABASE_URL=postgresql://user:password@host:port/dbname
DB_SSL=true

# 2. Домен где будет жить webapp (после деплоя Static Site)
WEBAPP_URL=https://твой-домен.ondigitalocean.app
FRONTEND_ORIGIN=https://твой-домен.ondigitalocean.app

# 3. Домен где будет жить админка (тот же домен + /panel/ или отдельный)
ADMIN_WEBAPP_URL=https://твой-домен.ondigitalocean.app/panel/
ADMIN_FRONTEND_ORIGIN=https://твой-домен.ondigitalocean.app

# 4. Токены ботов — те же что и локально (или новые боты если хочешь)
BOT_TOKEN=
ADMIN_BOT_TOKEN=
SUPPORT_BOT_TOKEN=
SUPPORT_BOT_URL=https://t.me/имя_бота_поддержки

# 5. Свой Telegram ID, сюда ставишь те кто смогут зайти по паролю владельца в админку
ADMIN_USER_IDS=свой_telegram_id

# 6. Сгенерировать надёжные ключи
ADMIN_JWT_SECRET=сгенерировать_случайный_64_символа, это случайный секретный ключ, которым сервер подписывает сессии в админ-панели, после того как ты поставил его, не меняй его вообще, если поменяешь сессии в админ-панели будут невалидными
ADMIN_LOGIN_KEY=сгенерировать_случайный_ключ, это ключ чтобы войти в админку, под владельцем

# ======================================================
# ЭТО ПОМЕНЯТЬ НА ПРОДЕ (не трогать локально):
# ======================================================
PRODUCTION=true говорит серверу что он работает на реальном хостинге, а не локально.
ALLOW_DEV_AUTH=false разрешает ли вход в игру без проверки подписи Telegram, тоесть если ты на хостинге включишь, то людей тип может подделать подписи

# ======================================================
# ОПЦИОНАЛЬНО — если хочешь логи в Telegram-группу:
# ======================================================
AUDIT_LOG_ENABLED=true
AUDIT_TELEGRAM_CHAT_ID=id_своей_группы
ERROR_REPORT_ENABLED=true
ERROR_TELEGRAM_CHAT_ID=id_своей_группы
```

> После заполнения `.env` — загрузи эти переменные в панели хостинга (DigitalOcean → App → Settings → Environment Variables).
> Переменные `VITE_*` нужны при **сборке** фронта, а не в runtime — их указывать в настройках сборки Static Site.

---

### Docker Compose (VPS / Droplet)

```bash
cp server/.env.example server/.env
# Заполнить секреты в server/.env (см. раздел выше)

docker compose up -d --build
```

Проверка: `curl http://localhost:8000/health`

| Контейнер | Порт | Что делает |
|-----------|------|------------|
| `postgres` | 5432 | База данных |
| `api` | 8000 | FastAPI сервер |
| `bots` | — | Все три Telegram-бота |

---

## Переменные окружения

Файл: `server/.env` (скопировать из `server/.env.example`)

### База данных

```env
# Вариант 1 — одной строкой (DigitalOcean Managed DB):
DATABASE_URL=postgresql://user:password@host:port/dbname

# Вариант 2 — по частям (локально):
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=admin
DB_SSL=false          # false локально, true на проде
```

### Telegram боты

```env
BOT_TOKEN=            # Игровой бот (из @BotFather)
WEBAPP_URL=           # HTTPS URL игры (ngrok или продовый домен)

ADMIN_BOT_TOKEN=      # Admin-бот (отдельный бот в @BotFather)
ADMIN_WEBAPP_URL=     # URL панели, напр. https://domain.com/panel/

SUPPORT_BOT_TOKEN=    # Бот поддержки (третий отдельный бот)
SUPPORT_BOT_URL=      # https://t.me/your_support_bot
```

### Безопасность и аутентификация

```env
PRODUCTION=false           # true на проде
ALLOW_DEV_AUTH=true        # true только локально
INIT_DATA_MAX_AGE=3600     # Время жизни initData (сек)

ADMIN_ENABLED=true
ADMIN_USER_IDS=123456789   # Telegram ID владельцев через запятую
OWNER_USER_IDS=            # Если пусто — владельцы из ADMIN_USER_IDS
ADMIN_JWT_SECRET=          # openssl rand -hex 32  (мин 32 символа на проде)
ADMIN_LOGIN_KEY=           # Длинный ключ для первого входа владельцев
ADMIN_SESSION_MINUTES=60
```

### CORS

```env
FRONTEND_ORIGIN=http://localhost:5173        # URL игры
ADMIN_FRONTEND_ORIGIN=http://localhost:5174  # URL админки
```

### Уведомления в Telegram (опционально)

```env
AUDIT_LOG_ENABLED=false          # Логи изменений баланса в группу
AUDIT_TELEGRAM_CHAT_ID=          # ID Telegram-группы
AUDIT_TELEGRAM_THREAD_ID=        # ID темы (если группа-форум)

ERROR_REPORT_ENABLED=false       # Ошибки сервера в группу
ERROR_TELEGRAM_CHAT_ID=
ERROR_TELEGRAM_THREAD_ID=
```

### Производительность

```env
UVICORN_WORKERS=2                # Воркеров uvicorn (на проде 2–4)
DB_POOL_MAX=10                   # Макс. соединений с БД на воркер
SHOP_CATALOG_CACHE_SECONDS=45    # Кэш каталога биржи в секундах
RATE_LIMIT_WINDOW=60             # Окно rate limit (сек)
RATE_LIMIT_MAX=80                # Макс. запросов на user_id в окне
GAME_EVENTS_RETENTION_DAYS=90   # Хранить game_events N дней
```

### Фронтенд (`.env` в корне / `admin/.env`)

```env
VITE_API_URL=https://your-api.domain.com
VITE_ADMIN_API_PREFIX=https://your-api.domain.com/admin/api
VITE_DEV_USER_ID=123456789        # Твой ID при ALLOW_DEV_AUTH=true
VITE_ONLINE_PING_MS=20000
```

---

## Что включать и выключать

### Обязательно включить на проде

| Переменная | Значение | Зачем |
|------------|----------|-------|
| `PRODUCTION` | `true` | Включает HSTS, блокирует небезопасный старт |
| `ALLOW_DEV_AUTH` | `false` | Иначе любой может войти за чужой user_id |
| `DB_SSL` | `true` | Зашифрованное соединение с БД |
| `ADMIN_JWT_SECRET` | длинный случайный | Без него сессии админки небезопасны |
| `ADMIN_LOGIN_KEY` | длинный случайный | Без него вход в панель закрыт |

### Только для локальной разработки

| Переменная | Значение |
|------------|----------|
| `ALLOW_DEV_AUTH` | `true` |
| `PRODUCTION` | `false` |
| `DB_SSL` | `false` |
| `VITE_DEV_USER_ID` | Твой Telegram ID |

### Опциональные фичи (выключены по умолчанию)

| Переменная | Что включает |
|------------|-------------|
| `AUDIT_LOG_ENABLED=true` | Логи баланса в Telegram-группу |
| `ERROR_REPORT_ENABLED=true` | Ошибки сервера в Telegram-группу |
| `MAINTENANCE_MODE=true` | Режим тех. обслуживания (игроки видят заглушку) |

---

## База данных

Схема создаётся автоматически при старте сервера из `server/schema.sql`.
Миграции — через `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` в том же файле.

---

### Игроки

#### `users` — профиль каждого игрока

| Колонка | Тип | Что хранит |
|---------|-----|------------|
| `user_id` | BIGINT PK | Telegram ID |
| `balance` | INT | Баланс (кут) |
| `items` | TEXT | Инвентарь JSON: `{"id_предмета": количество}` |
| `tool_durability` | JSONB | Прочность инструментов |
| `quest_progress` | JSONB | Прогресс квестов |
| `daily_seed_claimed_on` | DATE | Дата последней ежедневной выдачи семени |
| `starter_pack_granted` | BOOL | Получен ли стартовый набор |
| `onboarding_done` | BOOL | Завершено ли обучение |
| `onboarding_active` | BOOL | Идёт ли обучение сейчас |
| `onboarding_step` | INT | Текущий шаг обучения |
| `onboarding_demo_logs` | INT | Брёвна собранные в обучении (удаляются после) |
| `username` | TEXT | Username из Telegram |
| `first_name` | TEXT | Имя |
| `last_name` | TEXT | Фамилия |
| `display_name` | TEXT | Отображаемое имя |
| `photo_url` | TEXT | Ссылка на аватарку |
| `banned` | BOOL | Забанен ли |
| `banned_at` | TIMESTAMPTZ | Когда забанен |
| `banned_reason` | TEXT | Причина бана |
| `last_seen_at` | TIMESTAMPTZ | Последняя активность |
| `last_client_ip` | TEXT | Последний IP |
| `last_platform` | TEXT | Платформа (iOS/Android/...) |
| `market_sales_count` | INT | Сколько раз продавал на бирже |
| `market_items_sold` | INT | Сколько предметов продал на бирже |
| `created_at` | TIMESTAMPTZ | Дата регистрации |

#### `user_login_events` — каждый вход в игру

Хранит IP, User-Agent, платформу, разрешение экрана, версию приложения, язык, часовой пояс.

#### `user_notifications` — уведомления для WebApp

Непрочитанные уведомления игрока (например, «твой лот купили»). После доставки через SSE помечаются `web_delivered=true`.

---

### Ферма

#### `farm_plots` — состояние каждой грядки

| Колонка | Тип | Что хранит |
|---------|-----|------------|
| `user_id` | BIGINT | Владелец грядки |
| `plot_id` | INT | Номер грядки (1–150) |
| `status` | TEXT | EMPTY / GROWING / READY / WITHERED |
| `crop_id` | TEXT | ID посаженной культуры |
| `planted_at` | TIMESTAMPTZ | Когда посадили |
| `ripe_at` | TIMESTAMPTZ | Когда будет готово к сбору |
| `dry_at` | TIMESTAMPTZ | Когда нужен следующий полив |
| `wilt_at` | TIMESTAMPTZ | Когда засохнет если не полить |
| `needs_water` | BOOL | Нужен ли полив сейчас |
| `waters_remaining` | INT | Сколько поливов ещё нужно |
| `autowater_active` | BOOL | Установлен ли автополив |

#### `farm_crops` — культуры (настраивается из админки)

Название, ID саженца, время роста (сек), инструмент для сбора, стоимость инструмента, предмет для полива, спрайт, включена/выключена, порядок.

#### `farm_crop_harvest_drops` — таблица дропа урожая

Для каждой культуры: какие предметы падают, в каком количестве (min/max), с каким шансом (%).

---

### Магазин и биржа

#### `dex` — каталог предметов магазина

| Колонка | Тип | Что хранит |
|---------|-----|------------|
| `id` | INT PK | ID предмета |
| `name` | TEXT | Название |
| `emoji` | TEXT | Эмодзи |
| `price` | INT | Цена в кут |
| `dis` | INT | Скидка (%) |
| `remains` | INT | Остаток в магазине |
| `sorting` | TEXT | Категория |
| `bio` | TEXT | Описание |
| `use` / `bonus` / `craft` | TEXT | Доп. инфо |

#### `market_listings` — лоты на бирже

| Колонка | Тип | Что хранит |
|---------|-----|------------|
| `id` | BIGSERIAL PK | — |
| `seller_id` | BIGINT | Продавец |
| `item_id` | TEXT | ID предмета |
| `quantity` | INT | Количество |
| `price` | INT | Цена за штуку |
| `status` | TEXT | active / sold / cancelled |
| `created_at` | TIMESTAMPTZ | — |

---

### Крафт и квесты

#### `craft_recipes` — рецепты крафта

Ключ, название, ID результата, ID ингредиентов (A и B), процент успеха, включён/выключен, порядок.

#### `quests` — квесты

Ключ, период (hourly/daily/weekly), действие (plant/water/harvest/craft/...), цель, название, описание, эмодзи, ограничение по культуре/предмету, активен ли.

#### `quest_rewards` — награды за квест

Для каждого квеста: тип (kut или item), количество, ID предмета.

---

### Аналитика и логи

#### `audit_events` — изменения баланса

Каждая транзакция. Типы: `shop_buy`, `market_list`, `market_sell`, `plot_buy`, `plot_clear`, `quest_reward`, `craft_success`, `craft_fail`.

Хранит: `user_id`, `event_type`, `amount`, `balance_before`, `balance_after`, детали (JSONB).

#### `game_events` — игровые события

Типы: `farm_plant`, `farm_water`, `farm_harvest`, `farm_wither`, `quest_accept`, `quest_complete`.
Автоматически удаляются через `GAME_EVENTS_RETENTION_DAYS` дней.

#### `system_logs` — системные ошибки и подозрительные запросы

Категория, код ошибки, user_id, метод, путь, статус, сообщение, IP, детали.

#### `online_snapshots` — снимки онлайна (каждые N секунд)

#### `online_daily_stats` — пиковый онлайн по дням

---

### Саппорт

#### `support_tickets` — обращения в поддержку

| Колонка | Тип | Что хранит |
|---------|-----|------------|
| `id` | SERIAL PK | — |
| `user_id` | BIGINT | Игрок |
| `username` | TEXT | Username игрока |
| `first_name` | TEXT | Имя игрока |
| `subject` | TEXT | Тема обращения |
| `status` | TEXT | open / closed |
| `assigned_admin_id` | BIGINT | Кто взял тикет |
| `assigned_admin_name` | TEXT | Имя взявшего |
| `created_at` | TIMESTAMPTZ | — |
| `updated_at` | TIMESTAMPTZ | Дата последнего сообщения |

#### `support_messages` — сообщения в тикете

| Колонка | Тип | Что хранит |
|---------|-----|------------|
| `id` | SERIAL PK | — |
| `ticket_id` | INT | Ссылка на тикет |
| `from_user` | BOOL | true = от игрока, false = от админа |
| `admin_user_id` | BIGINT | ID админа (если от админа) |
| `admin_name` | TEXT | Имя админа |
| `text` | TEXT | Текст сообщения |
| `photo_file_id` | TEXT | Telegram file_id прикреплённого фото |
| `created_at` | TIMESTAMPTZ | — |
| `read_at` | TIMESTAMPTZ | Когда прочитано |

---

### Апелляции банов

#### `ban_appeals` — апелляция на бан

| Колонка | Тип | Что хранит |
|---------|-----|------------|
| `id` | BIGSERIAL PK | — |
| `user_id` | BIGINT | Кто подал |
| `ban_reason` | TEXT | Причина бана на момент подачи |
| `appeal_text` | TEXT | Текст апелляции от игрока |
| `status` | TEXT | pending / taken / approved / rejected |
| `taken_by` | BIGINT | Кто взял в работу |
| `taken_at` | TIMESTAMPTZ | — |
| `resolved_by` | BIGINT | Кто вынес решение |
| `resolved_at` | TIMESTAMPTZ | — |
| `resolution` | TEXT | Текст решения |
| `created_at` | TIMESTAMPTZ | — |

#### `ban_appeal_messages` — переписка по апелляции

| Колонка | Тип | Что хранит |
|---------|-----|------------|
| `id` | BIGSERIAL PK | — |
| `appeal_id` | BIGINT | Ссылка на апелляцию |
| `from_user` | BOOL | true = игрок, false = админ |
| `admin_id` | BIGINT | ID админа |
| `admin_name` | TEXT | Имя админа |
| `text` | TEXT | Текст сообщения |
| `photo_file_id` | TEXT | Telegram file_id фото доказательства |
| `created_at` | TIMESTAMPTZ | — |

---

### Модерация

#### `staff_actions` — действия модераторов над игроками

| Колонка | Тип | Что хранит |
|---------|-----|------------|
| `id` | BIGSERIAL PK | — |
| `admin_user_id` | BIGINT | Кто выполнил действие |
| `admin_name` | TEXT | Имя модератора |
| `action_type` | TEXT | ban / unban / mute / warn |
| `target_player_id` | BIGINT | Над кем |
| `target_name` | TEXT | Имя игрока |
| `reason` | TEXT | Причина |
| `evidence` | TEXT | Текстовые доказательства |
| `proof_media_id` | TEXT | Telegram file_id фото-доказательства |
| `duration_minutes` | INT | Длительность мута (минут) |
| `created_at` | TIMESTAMPTZ | — |

#### `player_admin_notes` — заметки о игроках

Внутренние заметки которые модераторы пишут о конкретном игроке.

#### `ip_bans` — блокировки по IP

IP или CIDR, причина, кто заблокировал, когда, срок истечения, активна ли.

---

### Персонал

#### `admin_accounts` — аккаунты в админ-панели

| Колонка | Тип | Что хранит |
|---------|-----|------------|
| `user_id` | BIGINT PK | Telegram ID |
| `totp_secret` | TEXT | Секрет TOTP (2FA) |
| `username` / `first_name` | TEXT | Имя |
| `role` | TEXT | owner / senior_admin / junior_admin / moderator / applicant / suspended |
| `status` | TEXT | active / pending / rejected / suspended |
| `hired_at` | TIMESTAMPTZ | Дата найма |
| `hired_by` | BIGINT | Кто нанял |
| `curator_id` | BIGINT | Куратор (старший закреплённый за этим сотрудником) |
| `rules_accepted_at` | TIMESTAMPTZ | Когда принял правила |
| `payout_type` | TEXT | Способ получения выплат |
| `payout_details` | TEXT | Реквизиты для выплат |
| `availability` | TEXT | active / vacation / afk |
| `availability_until` | TIMESTAMPTZ | До каких пор недоступен |
| `last_ip` | TEXT | Последний IP входа в панель |
| `last_seen_at` | TIMESTAMPTZ | Последний вход |

#### `admin_applications` — заявки кандидатов

user_id, ответы на вопросы анкеты (JSONB), реквизиты, статус (pending/approved/rejected), назначенная роль, кто проверил.

#### `admin_register_pending` — ожидающие регистрацию

Временные записи: токен + TOTP секрет. Удаляются после подтверждения регистрации.

#### `application_questions` — шаблоны вопросов анкеты

Редактируются из панели. Текст вопроса, тип (text/textarea), обязательный ли, порядок.

#### `admin_activity` — активность в панели

10-минутные слоты присутствия каждого сотрудника. Используется для статистики активности.

#### `staff_salaries` — зарплаты по неделям

| Колонка | Тип | Что хранит |
|---------|-----|------------|
| `user_id` | BIGINT | Сотрудник |
| `week_start` | DATE | Начало недели |
| `base_amount` | INT | Базовая ставка |
| `coefficient` | NUMERIC | Коэффициент (0.5–2.0) |
| `bonus` | INT | Бонус |
| `bonus_reason` | TEXT | Причина бонуса |
| `penalty` | INT | Штраф |
| `penalty_reason` | TEXT | Причина штрафа |
| `amount` | INT | Итого к выплате |
| `paid_amount` | INT | Уже выплачено |
| `status` | TEXT | pending_approval / approved / partially_paid / paid / cancelled |
| `txid` | TEXT | ID транзакции выплаты |
| `payout_proof` | TEXT | Скриншот/ссылка доказательства выплаты |

#### `salary_payments` — транзакции выплат

Каждая отдельная выплата или аванс. Хранит: сумму, метод, txid, доказательство, кто оплатил, дату.

#### `pending_payouts` — крупные выплаты ожидающие второго owner'а

Выплаты сверх лимита требуют подтверждения двух владельцев.

#### `salary_appeals` — апелляции сотрудников по зарплате

Сотрудник оспаривает начисление. Хранит: причину, статус (open/resolved), решение, кто рассмотрел.

#### `staff_role_history` — история смены ролей

Кто, когда, какую роль получил/потерял, по какой причине, кто изменил.

#### `staff_notes` — заметки о сотрудниках

Внутренние заметки старших о каждом сотруднике.

#### `staff_strikes` — страйки сотрудников

Предупреждения. Автоматически сгорают через 30 дней.

#### `staff_shifts` — график смен

Плановые смены: начало, конец, заметка, кто создал.

#### `staff_complaints` — жалобы на сотрудников

От персонала или от игроков. Хранит: на кого, суть, доказательства, статус (open/in_progress/resolved), решение.

---

### Система и настройки

#### `system_settings` — глобальные настройки игры

Одна строка, редактируется из панели. Хранит:

| Ключ | Что настраивает |
|------|----------------|
| `maintenance` | Режим тех. обслуживания |
| `default_balance` | Стартовый баланс новых игроков |
| `plot_price_step` | Шаг цены грядок |
| `clear_cost` | Стоимость очистки засохшей грядки |
| `tree_grow_seconds` | Время роста дерева (сек) |
| `max_plots` | Максимум грядок на игрока |
| `water_interval_seconds` | Интервал между поливами (сек) |
| `wilt_grace_seconds` | Через сколько засохнет после «сухой земли» |
| `harvest_seed_drop_percent` | Шанс дропа семени при сборе |
| `daily_seed_amount` | Семян в ежедневной выдаче |
| `admin_session_minutes` | Время жизни сессии в панели |

#### `settings_history` — история изменений настроек

Кто, когда, что поменял (старое значение → новое).

#### `admin_audit_log` — лог всех действий в панели

Каждое действие администратора: кто, что, над кем, с какого IP, детали.

#### `broadcast_templates` — шаблоны рассылок

#### `broadcast_runs` — запуски рассылок

Аудитория, каналы (WebApp + Telegram), статус, количество получателей, доставлено/провалилось.

#### `chat` — балансы технических чатов (чёрный рынок)

#### `_schema_meta` — хэш схемы

Внутренняя. Хранит MD5 `schema.sql` — если не изменился, схема при старте не перезапускается.

---











## Файлы сервера

### Точка входа и ядро

| Файл | Что делает |
|------|------------|
| `app.py` | Точка входа FastAPI. Собирает все роуты, подключает middleware (CORS, security headers, rate limit, maintenance, IP-ban), запускает боты и планировщики при старте. |
| `config.py` | Читает все переменные из `.env`. Содержит проверки безопасности при старте. |
| `db.py` | Пул соединений PostgreSQL. Все игровые операции: посадить/полить/собрать, купить, скрафтить, продать на бирже, квесты. При старте применяет `schema.sql`. |
| `schema.sql` | Вся схема БД. CREATE TABLE и ALTER TABLE для миграций. Применяется автоматически. |
| `bots_runner.py` | Запускает все три бота параллельно. |

### Боты

| Файл | Что делает |
|------|------------|
| `bot.py` | Игровой Telegram-бот. Команды `/start`, `/farm`, `/staff`. Кнопка открытия Web App. |
| `admin_bot.py` | Admin Telegram-бот. Уведомляет владельцев о новых заявках/апелляциях/жалобах. Кнопка открытия панели. |
| `support_bot.py` | Бот поддержки. Принимает обращения от игроков, создаёт тикеты, принимает апелляции банов. Доставляет ответы администраторов. |

### Аутентификация и безопасность

| Файл | Что делает |
|------|------------|
| `auth.py` | Проверяет Telegram `initData` — верифицирует подпись, извлекает `user_id`. Поддерживает `ALLOW_DEV_AUTH` для разработки. |
| `admin_auth.py` | Аутентификация в панели: JWT-сессии, TOTP (2FA), инвайт-токены, rate limiting входа. |
| `admin_auth_rate_limit.py` | Rate limiting попыток входа в панель (по IP). |
| `rate_limit.py` | Rate limiting игровых запросов (по `user_id`). Кэш статуса бана в памяти. |
| `ip_ban.py` | Блокировка по IP-адресу. Синхронный кэш для проверки в middleware без обращения к БД. |
| `security_watch.py` | Детектор подозрительных запросов (SQL injection, XSS и др.) — логирует в `system_logs`. |
| `private_mode.py` | Режим закрытого доступа (whitelist пользователей). |
| `geo_ip.py` | Определение страны по IP (для логов). |

### Игровая логика

| Файл | Что делает |
|------|------------|
| `farm_logic.py` | Чистая логика фермы без БД: apply_plant, apply_water, apply_harvest, sync_growing_plot (пересчёт таймеров). |
| `farm_crops.py` | Каталог культур в памяти из таблицы `farm_crops`. Хелперы для получения культуры по саженцу. |
| `farm_settings.py` | Настройки фермы из `system_settings`: время роста, интервал полива и др. |
| `seed_economy.py` | Экономика семян: стартовый набор, ежедневная выдача, дроп при сборе. |
| `tool_durability.py` | Прочность инструментов (топор). Расходуется при каждом сборе дерева. |

### Предметы и инвентарь

| Файл | Что делает |
|------|------------|
| `user_items.py` | Операции с инвентарём: добавить/взять/посчитать предмет. Работает с JSON в `users.items`. |
| `item_catalog.py` | Нормализация и отображение предметов. |
| `inventory_catalog.py` | Сборка инвентаря для отображения игроку (с рыночными ценами). |
| `dex_catalog.py` | Каталог предметов `dex` в памяти. Загружается при старте сервера. |
| `item_market_stats.py` | Получение актуальных рыночных цен для предметов инвентаря. |

### Магазин и биржа

| Файл | Что делает |
|------|------------|
| `shop_catalog.py` | Логика каталога магазина: фильтры, сортировка, категории, пагинация. |
| `shop_cache.py` | LRU-кэш каталога магазина (по умолчанию 45 сек). |
| `market_catalog.py` | Логика каталога биржи. |
| `market_rules.py` | Правила биржи: лимиты, комиссия, какие предметы можно выставлять. |

### Крафт и квесты

| Файл | Что делает |
|------|------------|
| `craft_catalog.py` | Рецепты крафта в памяти. Проверка наличия ингредиентов. |
| `craft_definitions.py` | Загрузка рецептов из БД и валидация. |
| `quest_catalog.py` | Каталог квестов. |
| `quest_registry.py` | Реестр квестов в памяти (загружается при старте). |
| `quest_progress.py` | Логика прогресса: bump_progress, mark_claimed, apply_rewards. |
| `quest_rotation.py` | Ротация квестов (ежечасные/ежедневные/недельные сбрасываются по таймеру). |
| `content_registry.py` | Общий реестр контента (культуры + рецепты + квесты). |

### Уведомления и связь

| Файл | Что делает |
|------|------------|
| `notification_hub.py` | SSE (Server-Sent Events) хаб — push уведомления игрокам в реальном времени через браузер. |
| `telegram_notify.py` | Отправка сообщений через Telegram Bot API. |
| `user_notify.py` | Уведомления игрокам: о продаже лота на бирже и др. |
| `staff_notify.py` | Уведомления сотрудникам через admin-бота. |
| `admin_player_notify.py` | Рассылка уведомлений игрокам из панели. |

### Роуты API

| Файл | Что делает |
|------|------------|
| `admin_routes.py` | Все HTTP роуты `/admin/api/*`: игроки, модерация, экономика, контент, стафф, рассылки, логи, аналитика. |
| `support_routes.py` | Роуты `/admin/api/support/*`: тикеты поддержки и сообщения. |

### Админ-панель (модули)

| Файл | Что делает |
|------|------------|
| `admin_db.py` | DB-функции для стаффа: аккаунты, роли, зарплаты, страйки, заявки, действия модераторов. |
| `admin_accounts.py` | CRUD аккаунтов администраторов. |
| `admin_users.py` | Операции над игроками из панели: бан, разбан, просмотр профиля, история. |
| `admin_moderation.py` | Логи модерации: список действий, доказательства (фото), статистика по модераторам. |
| `admin_appeals.py` | Апелляции банов: подача, взятие в работу, одобрение/отклонение, переписка. |
| `admin_economy.py` | Управление экономикой: ручное изменение баланса, просмотр транзакций. |
| `admin_market.py` | Управление биржей из панели. |
| `admin_farm.py` | Управление фермой из панели: грядки, культуры. |
| `admin_quests.py` | CRUD квестов из панели. |
| `admin_content.py` | Управление контентом: культуры, рецепты, квесты. |
| `admin_analytics.py` | Аналитика: онлайн, покупки, активность игроков. |
| `admin_broadcast.py` | Рассылки: шаблоны, запуск кампаний в WebApp и Telegram. |
| `admin_audit.py` | Запись лога действий в панели (`admin_audit_log`). |
| `admin_logs.py` | Просмотр системных логов из панели. |
| `admin_permissions.py` | Проверка прав по роли: что кому разрешено делать в панели. |
| `admin_ws.py` | WebSocket хаб для панели — реалтайм события (новый тикет, новое действие) для всех открытых вкладок. |
| `admin_session_cache.py` | Кэш сессий панели в памяти. |

### Вспомогательное

| Файл | Что делает |
|------|------------|
| `audit_log.py` | Запись изменений баланса в `audit_events` и уведомления в Telegram. |
| `game_events_log.py` | Батчевая запись игровых событий в `game_events`. |
| `game_events_maintenance.py` | Периодическая очистка старых записей `game_events`. |
| `event_scheduler.py` | Планировщик фоновых задач: ротация квестов, очистка, снимки онлайна. |
| `presence.py` | Обновление `last_seen_at` и синхронизация профиля из Telegram при каждом пинге. |
| `error_reporter.py` | Отправка ошибок и security-алертов в Telegram-группу. |
| `error_codes.py` | Каталог кодов ошибок (`ERR_*`). |
| `maintenance.py` | Режим тех. обслуживания — блокирует все запросы кроме `/health` и `/admin/`. |
| `system_settings.py` | Чтение/запись `system_settings` из БД. |
| `economy_settings.py` | Настройки экономики (цены, стартовый баланс). |
| `player_profile.py` | Обновление профиля игрока из Telegram initData. |
| `user_client.py` | Формирование ответа клиенту. |
| `json_db_codec.py` | Кодек для JSON-инвентаря в текстовом поле `users.items`. |
| `support_db.py` | DB-функции для тикетов и сообщений поддержки. |

### Миграции (одноразовые скрипты)

| Файл | Когда запускать |
|------|----------------|
| `migrate_support.py` | Создаёт таблицы поддержки (если не применялся `schema.sql`) |
| `migrate_items.py` | Миграция формата хранения предметов (уже применена) |
| `migrate_items_to_names.py` | Переход от числовых ID к ключам (уже применена) |
| `migrate_invite_tokens.py` | Создаёт таблицу `admin_invite_tokens` |
| `reset_onboarding_all.py` | Сброс обучения у всех игроков (утилита, по необходимости) |
| `support_cleanup.py` | Очистка старых закрытых тикетов |

---

## Фронтенд

### Игра (`src/`)

| Файл / папка | Что делает |
|--------------|------------|
| `App.jsx` | Корневой компонент. Таб-навигация (ферма / магазин / биржа / инвентарь / квесты / настройки). |
| `main.jsx` | Точка входа React. Инициализация Telegram Web App SDK. |
| `components/FarmModule.jsx` | Ферма — грядки, посадка, полив, сбор урожая. |
| `components/PlotCard.jsx` | Карточка грядки: статус, таймер, кнопки действий. |
| `components/ShopShelfGrid.jsx` | Каталог магазина. |
| `components/MarketplaceModule.jsx` | Биржа — покупка и продажа. |
| `components/InventoryModule.jsx` | Инвентарь игрока. |
| `components/QuestsModule.jsx` | Квесты. |
| `components/CraftModule.jsx` | Крафт предметов. |
| `components/SettingsModule.jsx` | Настройки игрока. |
| `components/Onboarding.jsx` | Обучение при первом входе. |
| `components/BannedScreen.jsx` | Экран при бане. |
| `components/MaintenanceScreen.jsx` | Экран тех. обслуживания. |
| `components/SaleNotificationLayer.jsx` | Всплывающее уведомление о продаже лота. |
| `context/PlayerSyncContext.jsx` | Синхронизация состояния игрока с сервером. |

### Админ-панель (`admin/`)

Отдельное React приложение. Собирается через `cd admin && npm run build`. Деплоится как отдельный Static Site на `/panel/`.
