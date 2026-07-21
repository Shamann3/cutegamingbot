# Розыгрыши — мульти-победители для таймер-розыгрыша (разные призы за места)

## Контекст

Сейчас таймер-розыгрыш («Случайно по таймеру») выбирает ровно одного победителя:
`giveaways.winner_user_id` (единственный BIGINT), а `draw_timer_giveaways`
(`server/db.py`) берёт `SELECT user_id FROM giveaway_entries ORDER BY random() LIMIT 1`.
Владелец проекта хочет несколько призовых мест с **разными призами за каждое место**
(1‑е — NFT, 2‑е — 500 КУТ, 3‑е — 200 КУТ и т.п.).

Это отдельная фича поверх уже отгруженных v1/v2/v3. Механика «Мгновенно всем выполнившим»
(`instant`) НЕ меняется — там нет мест, каждый выполнивший условия получает один и тот же
приз (существующее поведение).

## Существующий контекст (уже в коде)

- `giveaways` (`server/schema.sql:1023-1048`): `winner_user_id BIGINT`, единый приз в колонках
  `prize_type` (`'kut'|'manual'`), `prize_kut_amount`, `prize_title`, `prize_emoji`,
  `prize_description`. `draw_type IN ('timer','instant')`. `status IN ('active','completed','cancelled')`.
- `draw_timer_giveaways` (`server/db.py:2040+`): фоновый планировщик (`event_scheduler.py`)
  зовёт его; на каждый истёкший таймер-розыгрыш в транзакции с `FOR UPDATE` выбирает 1
  случайного участника, ставит `status='completed'`, `winner_user_id`, `drawn_at`, начисляет
  КУТ (если приз kut), шлёт Telegram‑DM и `log_game_event('giveaway_drawn')`. При нуле
  участников — `status='cancelled'`. Telegram‑DM и админ‑уведомления откладываются до выхода
  из `async with self.pool.acquire()` (правило пула соединений).
- `winner_user_id` читается в: `get_giveaways_state` (`won`), `get_giveaway_detail`
  (`result.won`, `winnerName`, `recipientsCount`), `get_giveaways_history` (`winnerName`),
  `get_giveaway_winners_feed` (timer_rows join), `_giveaway_to_admin_dict` (`winnerUserId`).
- Приз форматируется хелпером `_giveaway_prize_summary(row)` (`server/db.py`) →
  `{type, amount}` для kut или `{type, title, emoji, description}` для manual.
- Админ‑форма приза: `admin/src/pages/sections/GiveawaysSection.jsx` — селектор
  `PRIZE_TYPE_OPTIONS` (kut/manual) + поля суммы либо названия/эмодзи/описания.
  Бэкенд‑валидация приза: `_validate_prize(...)` в `server/admin_giveaways.py`.
- Схема применяется целиком на старте одним `conn.execute(schema.sql)` (`server/db.py:235`) —
  один неявный транзакционный блок, все `CREATE TABLE IF NOT EXISTS` / `ALTER ... IF NOT EXISTS`
  идемпотентны и повторно‑применимы.

## 1. Модель данных

Две новые таблицы + одна колонка на `giveaways`. Применимо **только к `draw_type='timer'`**.

```sql
ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS winners_count INT NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS giveaway_prizes (
    giveaway_id INT NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,
    place INT NOT NULL CHECK (place >= 1),
    prize_type TEXT NOT NULL CHECK (prize_type IN ('kut', 'manual')),
    prize_kut_amount INT,
    prize_title TEXT,
    prize_emoji TEXT,
    prize_description TEXT,
    PRIMARY KEY (giveaway_id, place)
);

CREATE TABLE IF NOT EXISTS giveaway_winners (
    giveaway_id INT NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,
    place INT NOT NULL CHECK (place >= 1),
    user_id BIGINT NOT NULL,
    won_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (giveaway_id, place)
);
```

- `giveaway_prizes` — по строке на место, каждый приз имеет полную структуру (тот же набор
  полей, что и `giveaways.prize_*`). Места нумеруются 1..N подряд.
- `giveaway_winners` — кто занял какое место после розыгрыша.
- `giveaways.winners_count` — сколько призовых мест у таймер‑розыгрыша (= число строк в
  `giveaway_prizes` для него; для `instant` игнорируется, остаётся 1).
- `giveaways.winner_user_id` **сохраняется** и заполняется победителем **места 1**
  (денормализация) — существующий код отображения «главного победителя» и старые завершённые
  розыгрыши продолжают работать без миграции данных для частого кейса.

**Instant не трогаем:** `instant`‑розыгрыши используют `giveaways.prize_*` как сейчас, строк в
`giveaway_prizes`/`giveaway_winners` у них нет.

**Backfill (в `schema.sql`, идемпотентно):**
- Для каждого существующего `timer`‑розыгрыша — создать `giveaway_prizes` строку **места 1** из
  его текущих `giveaways.prize_*`:
  ```sql
  INSERT INTO giveaway_prizes (giveaway_id, place, prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description)
  SELECT id, 1, prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description
  FROM giveaways WHERE draw_type = 'timer'
  ON CONFLICT (giveaway_id, place) DO NOTHING;
  ```
- Для каждого **завершённого** `timer`‑розыгрыша с `winner_user_id` — строка `giveaway_winners`
  места 1:
  ```sql
  INSERT INTO giveaway_winners (giveaway_id, place, user_id)
  SELECT id, 1, winner_user_id
  FROM giveaways WHERE draw_type = 'timer' AND status = 'completed' AND winner_user_id IS NOT NULL
  ON CONFLICT (giveaway_id, place) DO NOTHING;
  ```
  `winners_count` существующих таймер‑розыгрышей остаётся `1` (дефолт) — у них одно место, что
  соответствует их прошлой одно‑победительной семантике.

## 2. Логика розыгрыша (`draw_timer_giveaways`)

Заменяет выбор одного победителя на выбор до `winners_count` мест:

1. Прочитать `winners_count` розыгрыша.
2. Выбрать до `winners_count` **различных** случайных участников одним запросом:
   `SELECT user_id FROM giveaway_entries WHERE giveaway_id = $1 ORDER BY random() LIMIT $2`.
3. Если участников **ноль** → `status='cancelled', drawn_at=NOW()` (без изменений).
4. Иначе (k = min(winners_count, число_участников)):
   - Сопоставить участников местам 1..k в порядке выборки (чистый хелпер
     `assign_winner_places`, см. §5).
   - Вставить каждого в `giveaway_winners (giveaway_id, place, user_id)`.
   - `UPDATE giveaways SET status='completed', winner_user_id=<место1>, drawn_at=NOW()`.
   - Для каждого места достать приз из `giveaway_prizes` для этого места (чистый хелпер
     `prize_for_place`). Если приз `kut` — начислить баланс победителю (тот же
     `schedule_balance_event`‑поток, что и сейчас, по разу на победителя). Если `manual`/NFT —
     авто‑начисления нет (админ выдаёт вручную, как сейчас).
   - Отложить Telegram‑DM каждому победителю с указанием **его места и приза**
     (напр. «🎉 Вы заняли 2 место в розыгрыше «X»! Приз: 200 КУТ»).
   - `log_game_event('giveaway_drawn', winner, {...place, giveaway_id})` по разу на победителя.
5. Всё внутри существующей пер‑розыгрышной транзакции с `FOR UPDATE`; Telegram‑DM и
   админ‑уведомления по‑прежнему отправляются после освобождения соединения из пула
   (существующий паттерн `pending_notifications`).

Если у таймер‑розыгрыша по какой‑то причине нет строк `giveaway_prizes` (не должно случаться
после backfill/валидации) — приз места считается отсутствующим, КУТ не начисляется, DM шлётся
с текстом «приз» как fallback (та же защита, что в текущем `prize_text`).

## 3. Пути чтения и отображение

Везде, где показывается победитель, «один победитель» → «список призёров по местам».

- **`get_giveaway_detail`** (модалка игрока): добавить массив `winners` —
  `[{place, displayName, prize}]`, отсортированный по place, для завершённых таймер‑розыгрышей.
  `result.won` («выиграл ли *я*») = «есть ли я в `giveaway_winners`»; если да — в каком месте
  (`result.place`). Для `instant`/незавершённых — как сейчас. Для таймер‑розыгрыша (любой
  статус) добавить `prizesByPlace` — `[{place, prize}]` из `giveaway_prizes`, чтобы модалка
  показывала призовую сетку ещё до розыгрыша.
- **Модалка (webapp, `GiveawayDetailModal.jsx`)**: для завершённого мульти‑местного
  таймер‑розыгрыша показать ранжированный список (🥇 1 место — @user — 500 КУТ, 🥈 2 место — …).
  Если зритель выиграл — подсветить его строку («🎉 Вы заняли 2 место!»). Для незавершённого
  таймер‑розыгрыша с >1 местом — показать призовую сетку мест из `prizesByPlace`.
- **`get_giveaways_history`** + карточка (`GiveawayHistoryCard.jsx`): таймер‑розыгрыш с >1 местом
  показывает `winnersCount` победителей, в заголовке — имя места 1 с хинтом
  («🏆 @user +2 других»). Тап открывает модалку с полным ранжированным списком (уже покрыто §3
  модалкой).
- **`get_giveaway_winners_feed`** (ротация «Счастливчики дня»): каждый призёр — отдельная запись
  ленты (победители места 1 и места 2 оба ротируются), у каждого свой приз этого места. Сейчас
  timer_rows берут `winner_user_id` — заменить на join к `giveaway_winners` + `giveaway_prizes`
  по месту.
- **Карточка билета** (`GiveawayTicketCard.jsx`, active/upcoming): когда `winnersCount > 1` —
  показать «N призовых мест»; чип приза показывает приз **места 1** с хинтом «+N мест».
- **Админ list/detail** (`_giveaway_to_admin_dict`): вернуть список призов по местам (`prizes`:
  `[{place, prizeType, prizeKutAmount, prizeTitle, prizeEmoji, prizeDescription}]`) и, для
  завершённых, победителей по местам (`winners`: `[{place, userId}]`), плюс `winnersCount`.

Новые поля ответа (имена, на которые опирается фронтенд):
- Webapp detail: `winners: [{place, displayName, prize}]`, `prizesByPlace: [{place, prize}]`,
  `result: {won, place}`.
- Webapp list item (`get_giveaways_state`) и history item: `winnersCount` (int).
- Admin dict: `winnersCount` (int), `prizes: [{place, prizeType, prizeKutAmount, prizeTitle, prizeEmoji, prizeDescription}]`,
  `winners: [{place, userId}]`.

## 4. Админ‑панель (`GiveawaysSection.jsx` + `admin_giveaways.py` + `admin_routes.py`)

Форма меняется только при **«Механика розыгрыша» = «Случайно по таймеру»**:

- Новая секция **«Призовые места»** вместо единого редактора приза. Список строк‑мест (1, 2, 3…),
  в каждой — существующий редактор приза инлайн (селектор типа КУТ/ручной + соответствующие поля:
  сумма, либо название/эмодзи/описание). «+ Добавить место» добавляет следующее место; «✕»
  удаляет место (с перенумерацией остальных). Минимум 1 место.
- Для **«Мгновенно всем»** форма без изменений — единый существующий редактор приза.
- **Число победителей = число призовых мест** — админ не задаёт его отдельно; количество строк‑мест
  и есть `winners_count`. Нельзя создать место без приза или приз без места.
- Таблица розыгрышей: колонка **«Мест»** (`winnersCount`, «—» для instant); колонка «Победитель»
  показывает победителя места 1 с хинтом «+N» для мульти‑местных завершённых.

**API‑контракт (admin):**
- `GiveawayCreateBody`/`GiveawayUpdateBody` (`admin_routes.py`): добавить
  `prizes: list[GiveawayPrizeBody]` — по элементу на место, поля
  `prizeType, prizeKutAmount, prizeTitle, prizeEmoji, prizeDescription`. Для `instant` `prizes`
  игнорируется/пустой; единый приз приходит в существующих top‑level полях. Для `timer` — единый
  top‑level приз игнорируется, используется `prizes`.
- `create_giveaway`/`update_giveaway` (`admin_giveaways.py`): для `timer` записать строки
  `giveaway_prizes` (place = индекс+1), проставить `winners_count = len(prizes)`, `winner_user_id`
  оставить NULL до розыгрыша, `giveaways.prize_*` — записать приз места 1 (денормализация,
  чтобы существующее чтение `_giveaway_prize_summary(row)` для «главного приза» работало без
  спец‑кейса). Для `instant` — как сейчас (единый приз, `winners_count=1`, без строк `giveaway_prizes`).
- **Валидация** (`admin_giveaways.py`): `timer` должен иметь ≥ 1 призового места; каждый приз
  места валидируется существующим `_validate_prize` (KUT ≥ 1, либо непустое название для manual).
  При редактировании `timer`‑розыгрыша строки `giveaway_prizes` перезаписываются целиком (DELETE+INSERT,
  как уже делается для `giveaway_conditions` через `_replace_conditions`).

## 5. Миграция, обратная совместимость и тестирование

- **Схема**: `winners_count`, `giveaway_prizes`, `giveaway_winners` через
  `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS` в конце `schema.sql` (после блока v3).
- **Backfill**: два `INSERT ... SELECT ... ON CONFLICT DO NOTHING` (см. §1) там же — идемпотентны,
  безопасны на живой БД с существующими строками, выполняются в общей транзакции применения схемы.
- **Чистые хелперы (реальный TDD, pytest)** — новый файл `server/giveaway_draw.py`:
  - `assign_winner_places(entrant_ids: list[int], winners_count: int) -> list[tuple[int, int]]` —
    возвращает `[(place, user_id), ...]`, place = 1..k, k = min(winners_count, len(entrant_ids));
    порядок входа = порядок мест; пустой вход → `[]`.
  - `prize_for_place(prizes: list[dict], place: int) -> dict | None` — поиск приза по месту в
    списке (prizes уже прочитаны из `giveaway_prizes`), None если нет.
- **DB‑код, роуты, админ‑UI, webapp‑UI** — верификация через `python -m py_compile` +
  внимательный ручной review (живого Postgres в среде нет, как и в v2/v3), а также
  `npx vite build` (webapp + admin) и `npx vitest run` (существующие тесты не должны сломаться).
- **Итог**: бэкенд‑набор тестов зелёный (существующие + новые чистые тесты `giveaway_draw`),
  обе фронтенд‑сборки успешны.

## Границы (что НЕ входит)

- `instant`‑розыгрыши — не трогаем (единый приз на всех).
- Новые типы призов (кроме уже существующих `kut`/`manual`) — не добавляем.
- Ручное завершение таймер‑розыгрыша админом (кнопка «Завершить» есть только у `instant`) —
  не меняем.
- Веса/неравновероятный выбор победителей — нет, выбор равновероятный случайный (как сейчас).
- Пере‑розыгрыш/замена победителя места — вне scope.
