# История кут игрока во вкладке «Игроки» (admin)

## Проблема

Во вкладке **Игроки** (`admin/src/pages/sections/UsersSection.jsx`) внизу есть блок
**«История · События»**, но он показывает только `audit_events` — серверные игровые
события (магазин, ферма, admin-действия). Полной истории движений кут игрока из
legacy-таблицы `cutehistory` (ставки/выигрыши в играх, переводы «дать», начисления,
покупки) в панели нет. Админ не может по ID/username игрока увидеть все траты и
переводы, как это делается прямым SQL:

```sql
SELECT * FROM cutehistory WHERE user_id = 7785327280 AND data LIKE '%21.07.2026%';
```

Отдельная боль — **переводы**. `transfer_currency` пишет в `cutehistory` строку с
`cause = "дать"` без указания контрагента, поэтому по одной таблице нельзя понять,
кому игрок отдал кут или от кого получил. Полная связка отправитель→получатель уже
пишется в таблицу `p2p_transfers` (добавлена в
[2026-07-14-p2p-transfer-audit-design.md](2026-07-14-p2p-transfer-audit-design.md)),
но связи «конкретная строка cutehistory ↔ конкретный перевод» нет.

## Данные (текущее состояние)

- **`cutehistory`** (legacy, создаётся вне репозитория): колонки
  `user_id, "+", "-", cause, data, first_name, username, balance`. У строки заполнена
  ровно одна из колонок `"+"`/`"-"` (направление). Поле `data` — **строка** формата
  `"HH:MM DD.MM.YYYY"` (`strftime("%H:%M %d.%m.%Y")`), не timestamp — отсюда `LIKE` в
  запросах и некорректная строковая сортировка в существующем коде.
- **`donate`** (legacy): `user_id, count (numeric), data (timestamp)` — покупки за
  Telegram Stars. `data` здесь — настоящий timestamp.
- **`p2p_transfers`**: `id, created_at, sender_id, receiver_id, amount,
  sender_balance_*, receiver_balance_*, cause` — одна строка на перевод.
- `server/` подключён к той же Postgres (`db.pool.fetch`), что и бот — читает все эти
  таблицы напрямую (как уже делает `admin_logs.list_p2p_transfers`).

## Решение

Объединённый фид истории кут игрока в блоке «История» вкладки Игроки, с точной
связью переводов через новую колонку `cutehistory.transfer_id`.

### 1. Схема: `cutehistory.transfer_id`

Добавить nullable колонку и индекс. Bootstrap — в `server/schema.sql` (там же, где
создаётся `p2p_transfers`, выполняется при старте `server/app.py`; бот и сервер
смотрят в одну БД, поэтому достаточно серверного bootstrap):

```sql
ALTER TABLE cutehistory ADD COLUMN IF NOT EXISTS transfer_id BIGINT;
CREATE INDEX IF NOT EXISTS cutehistory_user_idx ON cutehistory (user_id);
CREATE INDEX IF NOT EXISTS cutehistory_transfer_idx ON cutehistory (transfer_id);
```

`cutehistory_user_idx` нужен, потому что новый эндпоинт фильтрует по `user_id` —
без индекса это seq scan по большой legacy-таблице.

> Предполагается, что `cutehistory` уже существует в БД (её создаёт legacy-бот).
> `ADD COLUMN IF NOT EXISTS` — безопасно повторяемо. На этапе плана исполнитель
> проверяет фактическую схему таблицы перед правкой.

### 2. Бот: `transfer_currency` заполняет `transfer_id`

В `bot/db_create/db.py::transfer_currency` (внутри уже существующей транзакции)
переставить `INSERT INTO p2p_transfers ... RETURNING id` **перед** двумя вставками в
`cutehistory` и передать полученный `id` в обе строки:

```python
transfer_row = await connection.fetchrow(
    "INSERT INTO p2p_transfers (...) VALUES (...) RETURNING id", ...
)
transfer_id = int(transfer_row["id"])

await connection.execute(
    'INSERT INTO cutehistory ("user_id","-",cause,data,first_name,username,balance,transfer_id) '
    'VALUES ($1,$2,$3,$4,$5,$6,$7,$8)',
    sender_id, amount, cause, formatted_date, sender_first_name, sender_username,
    sender_after, transfer_id,
)
await connection.execute(
    'INSERT INTO cutehistory ("user_id","+",cause,data,first_name,username,balance,transfer_id) '
    'VALUES ($1,$2,$3,$4,$5,$6,$7,$8)',
    receiver_id, amount, cause, formatted_date, receiver_first_name, receiver_username,
    receiver_after, transfer_id,
)
```

Всё в одной транзакции — атомарность и порядок из p2p-спека сохраняются. `moneyhistory`
insert и возврат `TransferResult` не меняются. Обычные (не переводные) вызовы
`cutehistory_plus`/`cutehistory_minus` не трогаем — там `transfer_id` остаётся `NULL`.

### 3. Backend: `get_user_cute_history`

Новый модуль `server/admin_cute_history.py` (отдельный, чтобы не раздувать
`admin_users.py`), функция:

```python
async def get_user_cute_history(
    user_id: int, *, date_from=None, date_to=None, direction=None,
    q=None, only_transfers=False, limit=50, offset=0,
) -> dict
```

**Источник A — cutehistory** (основной фид), с точным JOIN на перевод:

```sql
SELECT ch."+", ch."-", ch.cause, ch.data, ch.balance, ch.transfer_id,
       to_timestamp(ch.data, 'HH24:MI DD.MM.YYYY') AS ts,
       p.sender_id, p.receiver_id
FROM cutehistory ch
LEFT JOIN p2p_transfers p ON p.id = ch.transfer_id
WHERE ch.user_id = $1
  [AND to_timestamp(ch.data,'HH24:MI DD.MM.YYYY') >= $date_from]
  [AND to_timestamp(ch.data,'HH24:MI DD.MM.YYYY') <  $date_to]
  [AND ch."+" IS NOT NULL]      -- direction=in
  [AND ch."-" IS NOT NULL]      -- direction=out
  [AND ch.cause ILIKE '%'||$q||'%']
  [AND ch.transfer_id IS NOT NULL]  -- only_transfers
ORDER BY ts DESC NULLS LAST
```

- `to_timestamp(data, ...)` даёт корректную хронологию и фильтр по дате (заодно
  чинит строковую сортировку). Postgres `to_timestamp` терпим к формату.
- Направление строки: `"+"` → `in`, `"-"` → `out`.
- Контрагент перевода: если `transfer_id` есть — берём вторую сторону из `p`
  (для строки-`"-"` контрагент = `receiver_id`; для `"+"` = `sender_id`). Имя/username
  контрагента резолвим батч-запросом по собранным id (одним `SELECT user_id, first_name,
  username FROM users WHERE user_id = ANY($1)`), чтобы не делать N запросов.
- `transfer_id IS NULL` (обычные операции и **старые** переводы, сделанные до внедрения
  колонки) → строка показывается без контрагента. Это осознанное ограничение:
  ретроспективно контрагента для старых «дать» не восстанавливаем.

**Источник B — donate** (когда `only_transfers=False`): `SELECT user_id, count, data
FROM donate WHERE user_id=$1` + те же фильтры по дате; помечаем `kind:"donate"`,
`direction:"in"`, `amount = count`.

**Слияние и пагинация.** Оба источника нормализуются в единый список элементов и
сортируются по `ts DESC`, затем применяется `limit/offset` на сервере. `total` —
сумма COUNT по обоим источникам с учётом фильтров. (Донаты не участвуют, если
`only_transfers` или `direction=out`.)

Возврат:

```json
{
  "total": 123,
  "items": [
    {"ts": "...ISO...", "cause": "дать", "amount": 500, "direction": "out",
     "balance": 1500, "kind": "transfer",
     "counterparty": {"userId": 111, "name": "Аня", "username": "anya"}},
    {"ts": "...", "cause": "+ выигрыш bingo", "amount": 200, "direction": "in",
     "balance": 1700, "kind": "cute"},
    {"ts": "...", "cause": "донат", "amount": 100, "direction": "in",
     "kind": "donate"}
  ]
}
```

`kind`: `transfer` (есть `transfer_id`), `cute` (обычная строка cutehistory),
`donate`. Классификация — детерминированная (по `transfer_id` и источнику), без
«прогона через нейронку».

### 4. Роут

`server/admin_routes.py`:

```python
@router.get("/users/{target_user_id}/cute-history")
async def admin_user_cute_history(
    target_user_id: int,
    dateFrom: str | None = Query(None, max_length=32),
    dateTo: str | None = Query(None, max_length=32),
    direction: str | None = Query(None),          # "in" | "out" | None
    q: str | None = Query(None, max_length=200),
    onlyTransfers: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("view_players")),
):
    return await get_user_cute_history(target_user_id, ...)
```

Permission `view_players` — как у существующего `/users/{id}/audit`.

### 5. Frontend

- `admin/src/lib/adminClient.js`: `fetchAdminUserCuteHistory(userId, { dateFrom,
  dateTo, direction, q, onlyTransfers, limit, offset })` → `GET
  /users/{id}/cute-history`.
- `admin/src/pages/sections/UsersSection.jsx`, блок «История · События»:
  - Сегмент-переключатель источника: **«Действия»** (текущий `audit`) /
    **«Кут (полная)»** (новый фид). По умолчанию — «Действия» (не менять привычное
    поведение).
  - Для «Кут (полная)» — панель фильтров: дата от/до (`<input type="date">`),
    сегмент направления (Все / Начисления / Списания), поиск по cause (`<input>` с
    debounce), чекбокс «Только переводы». Кнопка «Ещё» для пагинации (offset += limit).
  - Рендер строки: время, cause, сумма со знаком и цветом (+ зелёный / − красный),
    баланс на момент. Для `kind:"transfer"` — строка контрагента: `→ Имя @username
    (id)` при `out`, `← Имя @username (id)` при `in`. Для `kind:"donate"` — бейдж
    «донат». Новый под-компонент `CuteHistoryFeed` внутри файла (рядом с существующими
    вкладками), стили — в стиле текущих карточек `.panel-users-audit-*`.
  - Фид загружается лениво — только при первом переключении на «Кут (полная)», не
    при загрузке профиля (не нагружать открытие игрока лишним запросом).

## Вне рамок

- Не меняем запись обычной истории (`cutehistory_plus`/`cutehistory_minus`) и
  `moneyhistory`; правим только `transfer_currency` для заполнения `transfer_id`.
- Не восстанавливаем контрагента для переводов, сделанных до внедрения `transfer_id`
  (у них `transfer_id IS NULL`).
- Не трогаем `audit_events` и текущий блок «Действия» — он остаётся первым/дефолтным
  источником.
- Не переклассифицируем причины ИИ-моделью; `kind` определяется детерминированно.
- Глобальный (не привязанный к игроку) поиск по cutehistory не делаем — это профиль
  конкретного игрока; журнал переводов по всем уже есть во вкладке Логи → Переводы.

## Проверка

- **Схема**: после старта сервера у `cutehistory` есть колонка `transfer_id` и индексы
  (idempotent при повторном старте).
- **Бот**: новый перевод «дать» → обе строки `cutehistory` (у отправителя `-`, у
  получателя `+`) имеют одинаковый `transfer_id`, равный `p2p_transfers.id`; баланс
  списан/начислен ровно один раз (регресс p2p-спека сохранён).
- **Backend**: `get_user_cute_history` для игрока-отправителя показывает строку «дать»
  с `direction:"out"` и `counterparty = получатель`; для получателя — `in` и
  `counterparty = отправитель`. Старая «дать»-строка (без `transfer_id`) — без
  контрагента. Фильтры дата/направление/cause/only_transfers сужают выдачу корректно;
  донаты видны, когда фильтр их допускает; пагинация не теряет и не дублирует строки.
- **Frontend**: переключатель «Действия/Кут (полная)» работает; фильтры шлют
  корректные query; переводы показывают контрагента, донаты — бейдж; «Ещё» дозагружает.
