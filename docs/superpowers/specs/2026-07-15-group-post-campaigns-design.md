# Циклические посты в группы — дизайн

## Задача

Админ хочет слать посты (текст + опционально фото + произвольные инлайн-кнопки)
в конкретные группы проекта на повторяющемся интервале (например «каждые 10
минут»), с полным контролем: несколько независимых кампаний одновременно,
каждая — свой текст/фото/кнопки/интервал/набор групп, с возможностью
паузы/удаления/редактирования и видимостью, что реально отправилось.

## Контекст (важные находки при разведке)

- Таблица `chat` (`server/schema.sql`) сейчас — это балансы чёрного рынка
  (`chat_id, chatbalance, dexbalance`), НЕ реестр групп с названиями. По
  решению владельца проекта группы для постинга выбираются **только по
  `chat_id`** (админ вводит ID вручную), без подтягивания названия — не
  расширяем эту таблицу.
- В `server/` НЕТ живого поллинга апдейтов от игрового бота (`BOT_TOKEN` /
  @CuteGamingBot) — `server/game_bot.py` прямо документирует, что второй
  поллер под тем же токеном вызывал бы конфликт `getUpdates`. Все исходящие
  сообщения (DM-рассылка, теперь и посты в группы) идут через прямые HTTP-вызовы
  Telegram Bot API (`server/telegram_notify.py`), это не требует поллинга и
  прекрасно работает для одностороннего постинга.
- Из этого следует: инлайн-кнопки могут быть только `url` или `web_app`
  (открывают ссылку/вебапп) — НЕ `callback_data`, потому что обработка нажатия
  callback-кнопки требует живого получения апдейтов от Telegram, которого у
  `server/` нет и создание его — отдельная задача вне рамок этого дизайна.
- Хостинг (DigitalOcean App Platform) не хранит файлы на диске между
  деплоями/рестартами контейнера → фото должны попадать в Postgres (bytea),
  не на файловую систему.

## Решение

Новая под-вкладка **«Посты в группы»** в `admin/src/pages/sections/BroadcastSection.jsx`
(или отдельный компонент `GroupPostsPanel.jsx`, монтируемый там же — решится
на этапе имплементации по объёму кода). Переиспользует уже существующую
инфраструктуру рассылок: `server/event_scheduler.py` (тик раз в 30с),
`server/telegram_notify.py` (отправка + классификация ошибок), паттерн
`_flush_recipient_log`/bulk-insert из `admin_broadcast.py`.

### Схема БД (`server/schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS group_post_campaigns (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id BIGINT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    chat_ids BIGINT[] NOT NULL,
    telegram_text TEXT NOT NULL,
    photo_bytes BYTEA,
    photo_mime TEXT,
    photo_file_id TEXT,          -- кэш после первой успешной отправки, дальше без реаплоада
    buttons_json JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [[{text,url,type}], [...]]
    interval_minutes INT NOT NULL CHECK (interval_minutes >= 1),
    status TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'paused'
    next_fire_at TIMESTAMPTZ,
    total_sent INT NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS group_post_campaigns_active_idx
    ON group_post_campaigns (next_fire_at) WHERE status = 'active';

-- История по каждому циклу × группе (без FK — тот же осознанный выбор, что
-- у broadcast_recipients после инцидента 2026-07-15 с InvalidForeignKeyError).
CREATE TABLE IF NOT EXISTS group_post_log (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    status TEXT NOT NULL,        -- 'sent' | 'failed'
    fail_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS group_post_log_campaign_idx
    ON group_post_log (campaign_id, id);
```

**Урок из вчерашнего инцидента прямо зашит в спеку**: никаких `REFERENCES`
на существующие таблицы без предварительной проверки, что там реально есть
подходящий unique/primary key constraint в проде. Ссылочная целостность —
на уровне приложения.

### Кнопки — `buttons_json`

Массив рядов, каждый ряд — массив кнопок:
```json
[
  [{"text": "🌾 Открыть ферму", "url": "https://...", "type": "web_app"}],
  [{"text": "💬 Наш чат", "url": "https://t.me/...", "type": "url"},
   {"text": "🎯 Сайт", "url": "https://...", "type": "url"}]
]
```
Без ограничения по числу рядов/кнопок в ряду (по запросу владельца проекта).
Сборка `reply_markup` — новая функция в `server/telegram_notify.py`, обобщающая
уже существующую `_webapp_button_markup` (сейчас она жёстко строит ровно одну
web_app-кнопку для DM-рассылок; станет общей `build_inline_keyboard(rows)`,
которую переиспользует и старый код CTA-кнопки рассылок).

### Фото — загрузка и повторное использование

1. При создании/редактировании кампании админ загружает файл через форму →
   `multipart/form-data` → сохраняется как `photo_bytes`/`photo_mime` в БД.
2. При **первой** успешной отправке (`photo_file_id IS NULL`) —
   `sendPhoto` с бинарником (`multipart/form-data` к Telegram Bot API).
   Response содержит `file_id` → сохраняется в `group_post_campaigns.photo_file_id`.
3. Все последующие циклы (и все остальные `chat_id` в том же цикле, если
   групп несколько) — `sendPhoto` с `photo=<file_id>` вместо файла: мгновенно,
   без реаплоада. `file_id` от Telegram привязан к боту, не к конкретному
   чату — переиспользуется across все `chat_ids` кампании.
4. Если фото не загружено — обычный `sendMessage` (текст + кнопки, как в
   DM-рассылке).
5. Если админ при редактировании кампании загружает **новое** фото —
   `photo_file_id` сбрасывается в `NULL` вместе с обновлением
   `photo_bytes`/`photo_mime`, чтобы следующий цикл заново прошёл шаг 2
   (иначе ушло бы старое фото по старому `file_id`).

### Планировщик — `server/event_scheduler.py`

Новая функция `_fire_group_post_campaigns()`, вызывается из `_tick()` (тик
раз в 30с, уже существующий). Логика:
```
SELECT * FROM group_post_campaigns
WHERE status = 'active' AND next_fire_at <= now()
```
Для каждой кампании: атомарный claim через
`UPDATE ... SET next_fire_at = now() + interval WHERE id = $1 AND next_fire_at = $2`
(тот же паттерн, что у `_fire_daily_rotation_broadcast`, защита от гонок при
нескольких воркерах), затем шлёт пост во все `chat_ids` с задержкой между
отправками (переиспользуем `TELEGRAM_SEND_DELAY` из `admin_broadcast.py`,
чтобы не долбить Telegram API), пишет `group_post_log` bulk-insert'ом,
обновляет `total_sent`/`last_error`.

При **первом** тике после создания кампании (`next_fire_at IS NULL`) —
выставляет расписание на `now() + interval_minutes`, не стреляет сразу же
(та же логика, что у ежедневной ротации — иначе создание кампании с
интервалом 10 минут даёт сюрприз мгновенной первой отправкой без
подтверждения через явную кнопку «Отправить сейчас»).

Несколько кампаний с разными интервалами работают полностью независимо —
каждая свой `next_fire_at`, тикающий планировщик просто выбирает все, кому
пора.

### API (`server/admin_routes.py`, `require_admin_permission("manage_broadcast")`)

- `GET /admin/api/group-posts` — список кампаний + статистика.
- `POST /admin/api/group-posts` — создать (multipart, если есть фото; сейчас
  `admin/src/lib/adminClient.js` заточен под JSON-запросы — понадобится
  отдельный fetch-хелпер с `FormData`, без `Content-Type: application/json`).
- `PATCH /admin/api/group-posts/{id}` — редактировать (текст/кнопки/интервал/группы/фото).
- `POST /admin/api/group-posts/{id}/pause` / `/resume`
- `DELETE /admin/api/group-posts/{id}`
- `POST /admin/api/group-posts/{id}/run-now` — тестовая отправка немедленно,
  не сбивая `next_fire_at` (по аналогии с `run_daily_rotation_now`).
- `GET /admin/api/group-posts/{id}/log?limit&offset` — история отправок.

### Админка

Карточка кампании (список, как история DM-рассылок): название, число
целевых групп, интервал, статус, `total_sent`, кнопки
Пауза/Возобновить/**Отправить сейчас**/Изменить/Удалить. Разворачивая —
превью поста (текст + кнопки + фото) и последние записи `group_post_log`
(успех/ошибка по каждой группе, с причиной — переиспользуем уже готовую
классификацию ошибок `blocked`/`chat_not_found`/`rate_limited`/`other` из
`telegram_notify.py`, хотя для групп `blocked` по смыслу будет значить «бота
кикнули из группы»).

Форма создания/редактирования: поле «Группы» — textarea с chat_id через
запятую/перенос строки (парсится в `BIGINT[]`), текст поста, загрузка фото
(необязательно), конструктор кнопок (добавить ряд / добавить кнопку в ряд /
удалить, без лимита), интервал в минутах (свободное число).

## Обработка ошибок

- Ошибка Telegram по конкретной группе (кикнули бота, группа удалена и т.п.)
  не останавливает кампанию — логируется в `group_post_log`, кампания
  продолжает тикать по расписанию для остальных групп.
- Если ВСЕ `chat_ids` кампании стабильно фейлятся — `last_error` виден в
  карточке, но кампания не ставится на паузу автоматически (админ решает сам,
  когда её выключить — не гадаем за него).
- Повторное подключение сервера (рестарт контейнера) не роняет расписание —
  `next_fire_at` персистентен в БД, как у ежедневной ротации.

## Вне рамок

- Callback-кнопки с обработкой на сервере (нужен живой polling/webhook,
  которого сейчас нет в `server/`) — только `url`/`web_app`.
- Подтягивание названия/аватарки группы по `chat_id` через Telegram API
  (`getChat`) — по решению владельца проекта выбор только по ID.
- Удаление предыдущего поста перед отправкой нового — каждый цикл просто
  новое сообщение (по решению владельца проекта).
- Автопауза кампании при массовых ошибках — админ решает вручную.
- Cron-подобное расписание (конкретные дни недели/часы) — только простой
  повторяющийся интервал в минутах.
