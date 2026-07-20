# Розыгрыши (Giveaways) v2 — вкладки, анонсы, лента победителей

Дата: 2026-07-20
Файлы: `server/*`, `admin/src/*`, `src/*` (полный список — в разделе «Файлы»)
Предыдущая итерация: `docs/superpowers/specs/2026-07-20-giveaways-design.md` (v1 — ядро, уже реализовано и в проде)

## Задача

v1 дал рабочее ядро: билеты-карточки, свайп-участие, модалку деталей, обе механики розыгрыша (instant/timer). Но сейчас список розыгрышей — плоский, без разделения на «сейчас», «скоро» и «уже было», и не даёт социального доказательства («тут реально выигрывают»). v2 добавляет:

1. Сегментированный переключатель **Активные / Скоро / Прошедшие**.
2. Анонсы будущих розыгрышей (администратор задаёт дату старта; до этой даты розыгрыш живёт во вкладке «Скоро», участие заблокировано, но карточку/модалку можно открыть заранее).
3. Историю прошедших розыгрышей — ник победителя (timer) или число получивших приз (instant).
4. Превью участников прямо в карточке (кружки-инициалы + счётчик).
5. Ленту «Счастливчики дня» — компактный ротирующийся блок над нижним меню с последними победами (по таймеру и мгновенными), для ощущения «живой» системы.
6. В админ-панели — поле даты старта при создании/редактировании розыгрыша.

## Объём v2 и то, что сознательно вынесено

**В v2 входит:** всё из списка выше. Никаких новых типов условий участия, никаких изменений в механике розыгрыша самого по себе — это чисто надстройка над готовым ядром v1.

**Явно вне v2:**
- Push/DM-уведомление «розыгрыш начался» при переходе Скоро → Активные — v1 уже шлёт уведомление только победителю по завершении; уведомление о старте не требовалось в брифе, добавлять не будем.
- Пагинация «Прошедших» за пределами последних 30 записей — при текущих объёмах (единицы-десятки розыгрышей) простой `LIMIT` без курсоров достаточен; если объём вырастет — отдельная доработка.
- Настройка ленты победителей (вкл/выкл, частота) в админке — лента либо есть, либо пуста и не рендерится; переключателя «показывать/не показывать» не делаем, это не было запрошено.

## Найдено при самопроверке спеки: instant-розыгрыши никогда не попадали в «Прошедшие»

В v1 `status='completed'` выставляется только timer-розыгрышам (планировщиком, при наступлении `ends_at`). Instant-розыгрыши осознанно никогда не завершаются сами — они висят в `status='active'` бессрочно, копя участников. Единственное действие админа над активным розыгрышем — «Отменить» (`status='cancelled'`), а отменённые розыгрыши не показываются игрокам вовсе (ни в одной вкладке). Это значит, что без изменений раздел «Прошедшие → N игроков получили приз» для instant был бы мёртвой веткой, в которую физически нечему попасть.

**Исправление:** добавляем в админку отдельное действие **«Завершить»** (помимо «Отменить») — доступно только для `draw_type='instant'` в статусе `active`. Переводит `status='completed'`, `drawn_at=NOW()`, `winner_user_id` остаётся `NULL` (как и раньше — у instant нет одного победителя). После этого розыгрыш пропадает из «Активные»/«Скоро» и появляется в «Прошедшие» с счётчиком получивших приз. Timer-розыгрыши по-прежнему завершаются только автоматически (никакого ручного «Завершить» для них не добавляем — не запрашивалось, и уже есть корректный автопуть через таймер).

Метод `Database` (`server/db.py`): `complete_instant_giveaway(giveaway_id)` — `UPDATE giveaways SET status='completed', drawn_at=NOW() WHERE id=$1 AND draw_type='instant' AND status='active'` (тот же паттерн условного апдейта, что уже используют `cancel_giveaway`/`participate_in_giveaway`). Роут: `PATCH /admin/content/giveaways/{id}/complete` или расширение существующего `PATCH .../{id}` телом `{"action": "complete"}` — решается на этапе реализации в пользу того, что проще стыкуется с уже написанным `admin_content_giveaway_patch`.

## Ключевые решения (зафиксированы в брейнсторминге)

1. **Без нового статуса.** Вместо `status IN ('active','scheduled','completed','cancelled')` — добавляем nullable `giveaways.starts_at TIMESTAMPTZ`. Розыгрыш остаётся `status='active'`; принадлежность вкладке считается на лету сравнением дат. Никаких изменений в `event_scheduler.py` не требуется — переход Скоро → Активные происходит сам по себе, без явного тика/апдейта строки. Это устраняет риск гонки/пропущенного перехода при простое сервера.
2. **Прошедшие instant-розыгрыши** показывают не «победителя» (которого структурно нет — каждый выполнивший условия получает приз независимо), а количество получивших приз: «🎁 12 игроков получили приз».
3. **Лента «Счастливчики дня»** включает и timer-победителей, и участников instant-розыгрышей (иначе лента почти всегда пустует — таймер-розыгрыши редки).
4. **Участники в карточке**: число + кружки-инициалы первых 3-4 (без обращения к Telegram-фото, только первая буква отображаемого имени).
5. **«Скоро»-карточка открывается** как обычно (детали/приз/условия видны), кнопка «Участвовать» заблокирована с текстом даты старта — тот же визуальный паттерн, что уже есть для «условия не выполнены».

## Данные (Postgres, `server/schema.sql`)

Одно изменение — новая колонка в существующей таблице:

```sql
ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ;
```

`NULL` = розыгрыш доступен сразу после создания (текущее поведение v1, обратная совместимость — все существующие розыгрыши автоматически остаются «активными»).

Никаких новых таблиц. Участники и их порядок уже есть в `giveaway_entries (giveaway_id, user_id, joined_at)`.

## Бэкенд (`server/db.py`, `server/app.py`, `server/admin_giveaways.py`, `server/admin_routes.py`)

### Определение bucket'а (только для чтения, нигде не хранится)

```python
def _giveaway_bucket(row, now):
    if row["status"] == "completed":
        return "past"
    if row["starts_at"] and row["starts_at"] > now:
        return "upcoming"
    return "active"  # status == 'active', starts_at пуст или в прошлом
```

`cancelled` — как и в v1, полностью исключается из игрового списка (`WHERE g.status != 'cancelled'`), не показывается ни в одной вкладке.

### `participate_in_giveaway` — новая проверка

Перед проверкой условий (`all_conditions_met`) — если `starts_at` задан и в будущем, возвращать ошибку `"Розыгрыш ещё не начался"` (тот же путь, что уже возвращает ошибки типа «уже участвуете» — без БД-мутации, просто ранний `raise ValueError`).

### `get_giveaways_state(user_id)` — расширение существующего ответа

Для каждого розыгрыша дополнительно:
- `startsAt` — ISO-строка или `null` (как уже сделано для `endsAt`).
- `participantsCount` — `COUNT(*) FROM giveaway_entries WHERE giveaway_id = g.id`.
- `participantsPreview` — до 4 отображаемых имён последних участников (`ORDER BY joined_at DESC LIMIT 4`), каждое — результат той же функции резолва ника, что и в ленте (см. ниже). Отдаём готовые строки, фронт просто берёт первую букву для кружка.

Реализуется как ещё один маленький запрос на розыгрыш внутри существующего цикла (там уже есть N+1 на условия — паттерн уже принят и задокументирован как приемлемый при текущих масштабах в `.superpowers/sdd/progress.md`, Task 2).

Этот эндпоинт как и раньше отдаёт **все** незавершённые (`active`, не `cancelled`) розыгрыши разом — bucketing на «активные» vs «скоро» происходит на фронте по `startsAt`, отдельного запроса не нужно.

### Новый метод + роут: история

`Database.get_giveaways_history(limit=30)`:
```sql
SELECT g.*, 
  (SELECT COUNT(*) FROM giveaway_entries e WHERE e.giveaway_id = g.id) AS entries_count
FROM giveaways g
WHERE g.status = 'completed'
ORDER BY g.drawn_at DESC NULLS LAST, g.id DESC
LIMIT $1
```
Для каждой строки:
- `draw_type == 'timer'` → `winnerName` = резолв ника по `winner_user_id` (см. ниже), `prize` (как и в других ответах).
- `draw_type == 'instant'` → `recipientsCount = entries_count`, `winnerName = null`.

Роут: `GET /api/giveaways/history` → `{"giveaways": [...]}`.

### Новый метод + роут: лента победителей

`Database.get_giveaway_winners_feed(limit=20)` — две выборки, слитые и отсортированные по времени в Python:

1. Timer-победители: `SELECT g.id AS giveaway_id, g.title, g.emoji, g.prize_kut_amount, g.prize_type, g.prize_title, g.prize_emoji, g.winner_user_id AS user_id, g.drawn_at AS at FROM giveaways g WHERE g.draw_type='timer' AND g.status='completed' AND g.winner_user_id IS NOT NULL ORDER BY g.drawn_at DESC LIMIT $1`
2. Instant-участники: `SELECT e.giveaway_id, g.title, g.emoji, g.prize_kut_amount, g.prize_type, g.prize_title, g.prize_emoji, e.user_id, e.joined_at AS at FROM giveaway_entries e JOIN giveaways g ON g.id = e.giveaway_id WHERE g.draw_type='instant' ORDER BY e.joined_at DESC LIMIT $1`

Мёржим по `at DESC`, берём первые `limit`, резолвим ники, отдаём (поле `prize` — тот же структурированный объект `{type, amount|title/emoji}`, что уже отдают `get_giveaways_state`/`get_giveaway_detail` через `_giveaway_prize_summary`, а не готовая строка — фронт форматирует его уже существующей `formatGiveawayPrize()` из `src/constants/giveaways.js`, как и везде):
```json
{"winners": [{"displayName": "@alex_trade", "prize": {"type": "kut", "amount": 500}, "giveawayTitle": "Супер-Ферма", "giveawayEmoji": "🌾", "at": "2026-07-20T10:15:00Z"}]}
```
Роут: `GET /api/giveaways/winners-feed`.

### Резолв отображаемого имени (общая функция)

```python
def _display_name(username, first_name):
    if username:
        return f"@{username}"
    return first_name or "Игрок"
```
Используется и в `participantsPreview`, и в истории, и в ленте — единообразный вид везде.

### Админка (`server/admin_giveaways.py`, `server/admin_routes.py`)

- `_validate_draw` дополняется: если `starts_at` и `ends_at` оба заданы — `starts_at < ends_at`, иначе `ValueError`.
- `create_giveaway`/`update_giveaway` принимают и сохраняют `starts_at`.
- `_giveaway_to_admin_dict` включает `startsAt`.

## Фронтенд (`src/`)

### Данные

- `useGiveaways` (существующий хук, 30-сек поллинг) — без изменений в контракте запроса, но теперь читает `startsAt`/`participantsCount`/`participantsPreview` из ответа и отдаёт их наружу как есть (просто новые поля в объектах `giveaways`).
- Новый хук `useGiveawayHistory()` — грузит `/api/giveaways/history` один раз при первом открытии вкладки «Прошедшие» (лениво, не при маунте модуля), без поллинга.
- Новый хук `useGiveawayWinnersFeed()` — грузит `/api/giveaways/winners-feed` при маунте `GiveawaysModule`, обновляет раз в 60 сек (не требует секундной свежести).

### `GiveawaysModule.jsx`

- Сегментированный переключатель — переиспользует существующие CSS-классы `.segment-tabs`/`.segment-tab`/`.segment-tab-active` (тот же паттерн, что у Ферма/Торговля/Профиль). Вкладки: «🟢 Активные (N)», «⌛ Скоро», «🏆 Прошедшие» — счётчик только у «Активные».
- Бакетинг на клиенте: `giveaways.filter(g => !g.startsAt || new Date(g.startsAt) <= now)` → активные; `giveaways.filter(g => g.startsAt && new Date(g.startsAt) > now)` → скоро.
- Сортировка внутри каждой вкладки: `legendary` → `rare` → `common` (используя существующий `RARITY_ORDER`), внутри редкости — порядок как пришёл с бэкенда (уже отсортирован по `sort_order, id`).
- Вкладка «Прошедшие» рендерит отдельный список карточек-«квитанций» (не билетов — они не кликабельны, не свайпаются): эмодзи, название, приз, и либо «🏆 Победитель: @ник», либо «🎁 N игроков получили приз», дата.
- Лента победителей — новый компонент `GiveawayWinnersFeed.jsx`, рендерится в `GiveawaysModule` над `TabBar` (внутри модуля, не глобально — видна только на вкладке «Розыгрыши»). Одна строка за раз, автосмена каждые 4 сек с fade-переходом. Если лента пуста — компонент не рендерит ничего (`return null`).

### `GiveawayTicketCard.jsx`

- Новая строка под существующей плашкой (⏳/💰): кружки-инициалы (до 4, `participantsPreview`) + «👥 N участников». Если `participantsCount === 0` — строка не рендерится вовсе (не показываем «👥 0 участников»).
- Если карточка в «Скоро» (`startsAt` в будущем) — свайп-жест (`canSwipe`) отключается (уже покрывается текущим условием `status === 'active'`, просто добавляем `&& !isUpcoming` в `canSwipe`), вместо хинта «Смахните →» показываем «⏳ Скоро».

### `GiveawayDetailModal.jsx`

- Если `startsAt` в будущем — зона 3 показывает не «🔒 Завершите задания», а «⏳ Начнётся 21 июля в 19:00» (тот же приглушённый стиль кнопки, что и у заблокированного состояния), кнопка неактивна независимо от условий.

## Админка (`admin/src/pages/sections/GiveawaysSection.jsx`)

- Новое поле «Дата начала (необязательно)» — `datetime-local`, сразу после «Название»/до «Механика розыгрыша» (рядом по смыслу с «Дата окончания», но не зависит от `drawType`, в отличие от неё).
- В таблице списка — новая колонка «Старт»: дата или «сразу».
- Новая кнопка «Завершить» рядом с «Изменить»/«Отменить» — только для строк с `drawType === 'instant'` и `status === 'active'` (см. раздел про исправление «Прошедшие» выше).

## Файлы

**Бэкенд:**
- `server/schema.sql` — `ALTER TABLE giveaways ADD COLUMN starts_at`.
- `server/db.py` — `_display_name`, расширение `get_giveaways_state`, новые `get_giveaways_history`, `get_giveaway_winners_feed`, `complete_instant_giveaway`, guard в `participate_in_giveaway`.
- `server/app.py` — роуты `GET /api/giveaways/history`, `GET /api/giveaways/winners-feed`.
- `server/admin_giveaways.py`, `server/admin_routes.py` — `starts_at` в валидации/CRUD, действие «Завершить» для instant.

**Фронтенд:**
- `src/hooks/useGiveaways.js` — прокидка новых полей (без изменения формы запроса).
- `src/hooks/useGiveawayHistory.js` (новый), `src/hooks/useGiveawayWinnersFeed.js` (новый).
- `src/lib/giveawaysClient.js` — `fetchGiveawayHistory`, `fetchGiveawayWinnersFeed`.
- `src/components/GiveawaysModule.jsx` — вкладки, бакетинг, сортировка, монтирование ленты.
- `src/components/GiveawayTicketCard.jsx` — участники, «скоро»-состояние.
- `src/components/GiveawayDetailModal.jsx` — «скоро»-состояние в зоне 3.
- `src/components/GiveawayHistoryCard.jsx` (новый) — карточка «квитанция» для «Прошедшие».
- `src/components/GiveawayWinnersFeed.jsx` (новый) — ротирующаяся лента.
- `src/styles/giveaways.css` — стили вкладок (переиспользует `.segment-tabs`), участников, ленты, истории.

**Админка (фронт):**
- `admin/src/pages/sections/GiveawaysSection.jsx` — поле «Дата начала», колонка в таблице, кнопка «Завершить».
- `admin/src/lib/adminClient.js` — вызов действия «Завершить».

## Тестирование

- `server/tests/test_giveaway_conditions.py` не затрагивается (условия не менялись).
- Новый `server/tests/test_giveaway_bucketing.py` — pytest на чистую функцию `_giveaway_bucket(row, now)` (active/upcoming/past по разным комбинациям `status`/`starts_at`) и на `_display_name` (с/без username).
- Живая проверка в браузере: как и в v1, без Postgres в этом окружении — только визуальная/build-проверка, реальный сквозной прогон (создать розыгрыш с будущим `starts_at` в админке → увидеть в «Скоро» → дождаться времени старта → увидеть в «Активные») по инструкции пользователю, если понадобится, но не блокирует реализацию.
