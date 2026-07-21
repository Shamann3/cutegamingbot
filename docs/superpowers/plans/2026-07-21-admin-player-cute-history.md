# История кут игрока во вкладке «Игроки» — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать админу во вкладке «Игроки» видеть полную историю кут игрока (`cutehistory` + `donate`) с точным контрагентом переводов через `p2p_transfers`.

**Architecture:** Новая nullable-колонка `cutehistory.transfer_id` жёстко связывает строку истории с переводом; бот заполняет её в той же транзакции. Сервер читает обе legacy-таблицы напрямую (`db.pool.fetch`), объединяет их в один фид с обогащением контрагента, и отдаёт через новый эндпоинт профиля. Фронт добавляет в блок «История» переключатель источника «Действия / Кут (полная)» с фильтрами.

**Tech Stack:** Python 3 / asyncpg / FastAPI (сервер), React 18 / Vite (админка), Postgres.

## Global Constraints

- Запись обычной истории (`cutehistory_plus`/`cutehistory_minus`), `moneyhistory` и `audit_events` **не менять** — правится только `transfer_currency`.
- Атомарность перевода из [2026-07-14-p2p-transfer-audit-design.md](../specs/2026-07-14-p2p-transfer-audit-design.md) сохраняется: все вставки внутри одной `conn.transaction()`.
- `cutehistory.data` — строка формата `"%H:%M %d.%m.%Y"` (напр. `"14:30 21.07.2026"`); парсинг для сортировки/фильтра только через `to_timestamp(data,'HH24:MI DD.MM.YYYY')`.
- Permission нового эндпоинта — `view_players` (как у `/users/{id}/audit`).
- Тесты сервера — pytest из каталога `server/`: `cd server && python -m pytest tests/ -v`. Тестируются только чистые функции (паттерн репозитория — БД в юнит-тестах не мокается).
- У фронта нет тест-раннера; верификация фронта — `cd admin && npm run build` (без ошибок).
- `kind` элемента истории определяется детерминированно (`transfer` при наличии `transfer_id`, `donate` из таблицы `donate`, иначе `cute`) — никакого «прогона через нейронку».

---

### Task 1: Схема — `cutehistory.transfer_id` + индексы

**Files:**
- Modify: `server/schema.sql` (добавить блок `cutehistory` после блока `p2p_transfers`, ~строка 79)
- Modify: `server/db.py:236-242` (добавить ALTER + индекс в блок миграций, сразу после `ALTER TABLE farm_plots ...`)

**Interfaces:**
- Produces: колонка `cutehistory.transfer_id BIGINT` (nullable), индексы `cutehistory_user_idx`, `cutehistory_transfer_idx`.

- [ ] **Step 1: Добавить CREATE TABLE + user-индекс в `server/schema.sql`**

Вставить после закрывающего блока `p2p_transfers` (после трёх его `CREATE INDEX`, ~строка 79):

```sql
-- Legacy-таблица истории кут (создаётся игровым ботом). Здесь — только
-- CREATE IF NOT EXISTS для свежих БД + индекс по user_id (новый admin-эндпоинт
-- /users/{id}/cute-history фильтрует по user_id). Колонка transfer_id
-- добавляется ALTER-миграцией в db.py (после того как таблица гарантированно есть).
CREATE TABLE IF NOT EXISTS cutehistory (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    "+" BIGINT,
    "-" BIGINT,
    cause TEXT,
    data TEXT,
    first_name TEXT,
    username TEXT,
    balance BIGINT,
    transfer_id BIGINT
);

CREATE INDEX IF NOT EXISTS cutehistory_user_idx ON cutehistory (user_id);
```

- [ ] **Step 2: Добавить ALTER + transfer-индекс в блок миграций `server/db.py`**

Сразу после существующего `ALTER TABLE farm_plots ADD COLUMN IF NOT EXISTS autowater_active ...` (после строки 242) добавить:

```python
            # cutehistory (legacy-таблица бота): колонка связи с p2p_transfers.
            # ALTER идёт после schema.sql, где таблица гарантированно есть
            # (CREATE IF NOT EXISTS). Индекс по transfer_id — только после того,
            # как колонка добавлена.
            try:
                await conn.execute(
                    "ALTER TABLE cutehistory ADD COLUMN IF NOT EXISTS transfer_id BIGINT"
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS cutehistory_transfer_idx "
                    "ON cutehistory (transfer_id)"
                )
            except Exception as _mig_err:
                _mig_logger.warning("cutehistory.transfer_id migration skipped: %s", _mig_err)
```

- [ ] **Step 3: Проверить корректность SQL (парсинг файла)**

Run: `cd server && python -c "import pathlib; s=pathlib.Path('schema.sql').read_text(encoding='utf-8'); assert 'CREATE TABLE IF NOT EXISTS cutehistory' in s and 'cutehistory_user_idx' in s; print('schema OK')"`
Expected: печатает `schema OK`

Run: `cd server && python -c "import ast,pathlib; ast.parse(pathlib.Path('db.py').read_text(encoding='utf-8')); print('db.py parses')"`
Expected: печатает `db.py parses`

- [ ] **Step 4: Commit**

```bash
git add server/schema.sql server/db.py
git commit -m "feat(db): add cutehistory.transfer_id column + indexes"
```

---

### Task 2: Бот — `transfer_currency` заполняет `transfer_id`

**Files:**
- Modify: `bot/db_create/db.py:7122-7160` (внутри `transfer_currency`, блок вставок в транзакции)

**Interfaces:**
- Consumes: колонка `cutehistory.transfer_id` (Task 1), таблица `p2p_transfers` с `RETURNING id`.
- Produces: обе строки `cutehistory` перевода (у отправителя `-`, у получателя `+`) получают одинаковый `transfer_id = p2p_transfers.id`.

- [ ] **Step 1: Переставить вставку `p2p_transfers` перед вставками `cutehistory` и передать `transfer_id`**

Заменить текущий блок (строки 7122-7160: два `INSERT INTO cutehistory`, затем `INSERT INTO moneyhistory`, затем `INSERT INTO p2p_transfers ... RETURNING id`) на следующий порядок — сначала p2p (для получения id), затем cutehistory x2 с `transfer_id`, затем moneyhistory:

```python
                transfer_row = await connection.fetchrow(
                    """
                    INSERT INTO p2p_transfers (
                        sender_id, receiver_id, amount,
                        sender_balance_before, sender_balance_after,
                        receiver_balance_before, receiver_balance_after,
                        cause
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                    """,
                    sender_id, receiver_id, amount,
                    sender_before, sender_after,
                    receiver_before, receiver_after,
                    cause,
                )
                transfer_id = int(transfer_row["id"])

                await connection.execute(
                    """
                    INSERT INTO cutehistory ("user_id", "-", cause, data, first_name, username, balance, transfer_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    sender_id, amount, cause, formatted_date,
                    sender_first_name, sender_username, sender_after, transfer_id,
                )
                await connection.execute(
                    """
                    INSERT INTO cutehistory ("user_id", "+", cause, data, first_name, username, balance, transfer_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    receiver_id, amount, cause, formatted_date,
                    receiver_first_name, receiver_username, receiver_after, transfer_id,
                )
                await connection.execute(
                    """
                    INSERT INTO moneyhistory (user_id, user_id2, money, data)
                    VALUES ($1, $2, $3, $4)
                    """,
                    sender_id, receiver_id, amount, timestamp_without_microseconds,
                )
```

(Возврат `TransferResult(transfer_id=int(transfer_row["id"]), ...)` ниже по коду не меняется — `transfer_row` по-прежнему определён.)

- [ ] **Step 2: Проверить, что файл парсится и порядок вставок верный**

Run: `cd bot && python -c "import ast,pathlib; ast.parse(pathlib.Path('db_create/db.py').read_text(encoding='utf-8')); print('db.py parses')"`
Expected: печатает `db.py parses`

Run: `python -c "import re,pathlib; s=pathlib.Path('bot/db_create/db.py').read_text(encoding='utf-8'); i=s.index('async def transfer_currency'); blk=s[i:i+4000]; assert blk.index('INSERT INTO p2p_transfers') < blk.index('INSERT INTO cutehistory'), 'p2p must be inserted before cutehistory'; assert blk.count('transfer_id') >= 3; print('order OK')"`
Expected: печатает `order OK`

- [ ] **Step 3: Commit**

```bash
git add bot/db_create/db.py
git commit -m "feat(transfer): link cutehistory rows to p2p_transfers via transfer_id"
```

---

### Task 3: Backend — чистые функции нормализации + тесты

**Files:**
- Create: `server/admin_cute_history.py` (пока только чистые функции + импорты)
- Create: `server/tests/test_cute_history.py`

**Interfaces:**
- Produces:
  - `cute_direction(plus, minus) -> str` — `"in"` если `plus is not None`, иначе `"out"`.
  - `counterparty_id(direction: str, sender_id, receiver_id) -> int | None` — `receiver_id` при `"out"`, `sender_id` при `"in"`, `None` если любая сторона `None`.
  - `normalize_cute_row(row, name_map: dict) -> dict` — row-mapping с ключами `plus, minus, cause, balance, transfer_id, ts (datetime|None), sender_id, receiver_id`; возвращает элемент фида.
  - `normalize_donate_row(row) -> dict` — row-mapping с ключами `count, ts (datetime|None)`.
  - `merge_and_paginate(cute_items, donate_items, offset, limit) -> list[dict]` — слияние двух списков, сортировка по `ts` DESC (None — в конец), срез `[offset:offset+limit]`.
  - Форма элемента: `{"ts": str|None, "cause": str, "amount": int, "direction": "in"|"out", "balance": int|None, "kind": "transfer"|"cute"|"donate", ["counterparty": {"userId": int, "name": str|None, "username": str|None}]}`.

- [ ] **Step 1: Написать тесты `server/tests/test_cute_history.py`**

```python
"""История кут: чистые функции нормализации/слияния, без БД."""
from datetime import datetime, timezone

from admin_cute_history import (
    cute_direction,
    counterparty_id,
    normalize_cute_row,
    normalize_donate_row,
    merge_and_paginate,
)

TS_A = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
TS_B = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)


def test_cute_direction():
    assert cute_direction(100, None) == "in"
    assert cute_direction(None, 50) == "out"


def test_counterparty_id_out_returns_receiver():
    assert counterparty_id("out", 111, 222) == 222


def test_counterparty_id_in_returns_sender():
    assert counterparty_id("in", 111, 222) == 111


def test_counterparty_id_none_when_missing_side():
    assert counterparty_id("out", None, None) is None
    assert counterparty_id("in", 111, None) is None


def test_normalize_cute_transfer_out_attaches_receiver():
    row = {"plus": None, "minus": 500, "cause": "дать", "balance": 1500,
           "transfer_id": 7, "ts": TS_A, "sender_id": 111, "receiver_id": 222}
    item = normalize_cute_row(row, {222: {"name": "Аня", "username": "anya"}})
    assert item["direction"] == "out"
    assert item["amount"] == 500
    assert item["kind"] == "transfer"
    assert item["counterparty"] == {"userId": 222, "name": "Аня", "username": "anya"}
    assert item["ts"] == "2026-07-21T10:00:00+00:00"


def test_normalize_cute_transfer_in_attaches_sender():
    row = {"plus": 500, "minus": None, "cause": "дать", "balance": 2000,
           "transfer_id": 7, "ts": TS_A, "sender_id": 111, "receiver_id": 222}
    item = normalize_cute_row(row, {111: {"name": "Боб", "username": None}})
    assert item["direction"] == "in"
    assert item["kind"] == "transfer"
    assert item["counterparty"]["userId"] == 111


def test_normalize_cute_plain_has_no_counterparty():
    row = {"plus": 200, "minus": None, "cause": "+ выигрыш bingo", "balance": 1700,
           "transfer_id": None, "ts": TS_A, "sender_id": None, "receiver_id": None}
    item = normalize_cute_row(row, {})
    assert item["kind"] == "cute"
    assert "counterparty" not in item
    assert item["amount"] == 200


def test_normalize_donate():
    item = normalize_donate_row({"count": 100, "ts": TS_A})
    assert item == {"ts": "2026-07-21T10:00:00+00:00", "cause": "донат",
                    "amount": 100, "direction": "in", "balance": None, "kind": "donate"}


def test_merge_sorts_desc_across_sources():
    cute = [{"ts": TS_A.isoformat(), "kind": "cute"}]
    donate = [{"ts": TS_B.isoformat(), "kind": "donate"}]
    out = merge_and_paginate(cute, donate, 0, 10)
    assert [i["kind"] for i in out] == ["donate", "cute"]


def test_merge_pagination_offset_limit():
    items = [{"ts": datetime(2026, 7, 21, h, tzinfo=timezone.utc).isoformat(),
              "kind": str(h)} for h in range(5)]
    out = merge_and_paginate(items, [], 1, 2)  # desc: 4,3,2,1,0 -> offset1,limit2 -> 3,2
    assert [i["kind"] for i in out] == ["3", "2"]


def test_merge_none_ts_goes_last():
    out = merge_and_paginate(
        [{"ts": None, "kind": "x"}],
        [{"ts": TS_A.isoformat(), "kind": "y"}],
        0, 10,
    )
    assert [i["kind"] for i in out] == ["y", "x"]
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают (модуля ещё нет)**

Run: `cd server && python -m pytest tests/test_cute_history.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'admin_cute_history'`

- [ ] **Step 3: Реализовать чистые функции в `server/admin_cute_history.py`**

```python
"""Admin: объединённая история кут игрока (cutehistory + donate + p2p_transfers).

Чистые функции нормализации/слияния тестируются юнит-тестами; функция
get_user_cute_history (DB) добавляется в Task 4.
"""
from __future__ import annotations

from typing import Any


def cute_direction(plus, minus) -> str:
    """Направление строки cutehistory: '+' заполнено → 'in', иначе 'out'."""
    return "in" if plus is not None else "out"


def counterparty_id(direction: str, sender_id, receiver_id):
    """Вторая сторона перевода относительно текущего игрока.

    Строка '-' (out, отправитель) → контрагент = получатель.
    Строка '+' (in, получатель)  → контрагент = отправитель.
    None, если это не перевод (нет p2p-данных).
    """
    if sender_id is None or receiver_id is None:
        return None
    return receiver_id if direction == "out" else sender_id


def _iso(ts) -> str | None:
    return ts.isoformat() if ts is not None else None


def normalize_cute_row(row: Any, name_map: dict) -> dict:
    """Строка cutehistory (+ данные джойна p2p) → элемент фида."""
    plus = row["plus"]
    minus = row["minus"]
    direction = cute_direction(plus, minus)
    amount = int(plus if direction == "in" else minus)
    is_transfer = row["transfer_id"] is not None
    item = {
        "ts": _iso(row["ts"]),
        "cause": row["cause"],
        "amount": amount,
        "direction": direction,
        "balance": int(row["balance"]) if row["balance"] is not None else None,
        "kind": "transfer" if is_transfer else "cute",
    }
    if is_transfer:
        cp_id = counterparty_id(direction, row["sender_id"], row["receiver_id"])
        if cp_id is not None:
            info = name_map.get(cp_id) or {}
            item["counterparty"] = {
                "userId": int(cp_id),
                "name": info.get("name"),
                "username": info.get("username"),
            }
    return item


def normalize_donate_row(row: Any) -> dict:
    """Строка donate → элемент фида (всегда начисление, kind='donate')."""
    return {
        "ts": _iso(row["ts"]),
        "cause": "донат",
        "amount": int(row["count"]),
        "direction": "in",
        "balance": None,
        "kind": "donate",
    }


def merge_and_paginate(cute_items: list, donate_items: list, offset: int, limit: int) -> list:
    """Слить два списка, отсортировать по ts DESC (None — в конец), срез [offset:offset+limit]."""
    combined = list(cute_items) + list(donate_items)
    combined.sort(key=lambda it: (it.get("ts") is not None, it.get("ts") or ""), reverse=True)
    return combined[offset:offset + limit]
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `cd server && python -m pytest tests/test_cute_history.py -v`
Expected: PASS (все тесты зелёные)

- [ ] **Step 5: Commit**

```bash
git add server/admin_cute_history.py server/tests/test_cute_history.py
git commit -m "feat(admin): pure helpers for player cute-history feed + tests"
```

---

### Task 4: Backend — `get_user_cute_history` (DB) + роут

**Files:**
- Modify: `server/admin_cute_history.py` (добавить `async def get_user_cute_history(...)` + `from db import db`)
- Modify: `server/admin_routes.py:206` (или рядом — добавить импорт) и `server/admin_routes.py:2243` (добавить роут после `admin_user_audit`)
- Modify: `server/tests/test_cute_history.py` (добавить тест регистрации роута)

**Interfaces:**
- Consumes: чистые функции из Task 3; `db.pool` (asyncpg); `require_admin_permission` из существующего кода `admin_routes.py`.
- Produces: `get_user_cute_history(user_id, *, date_from, date_to, direction, q, only_transfers, limit, offset) -> {"total": int, "items": list}`; HTTP `GET /admin/api/users/{target_user_id}/cute-history`.

- [ ] **Step 1: Добавить тест регистрации роута в `server/tests/test_cute_history.py`**

Дописать в конец файла:

```python
def test_cute_history_route_registered():
    import os
    os.environ.setdefault("PRODUCTION", "false")
    from app import app
    paths = [getattr(r, "path", "") for r in app.router.routes]
    assert any(p.endswith("/users/{target_user_id}/cute-history") for p in paths), (
        f"cute-history route not registered: {paths}"
    )
```

- [ ] **Step 2: Запустить новый тест — убедиться, что падает (роута нет)**

Run: `cd server && python -m pytest tests/test_cute_history.py::test_cute_history_route_registered -v`
Expected: FAIL — assert (роут ещё не зарегистрирован)

- [ ] **Step 3: Добавить `from db import db` и `get_user_cute_history` в `server/admin_cute_history.py`**

В начало файла, к импортам, добавить:

```python
from db import db
```

В конец файла добавить функцию:

```python
async def get_user_cute_history(
    user_id: int,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    direction: str | None = None,      # "in" | "out" | None
    q: str | None = None,
    only_transfers: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Объединённый фид истории кут игрока: cutehistory (+p2p контрагент) + donate.

    Пагинация merge-стилем: из каждого источника берём offset+limit строк
    (уже отсортированных DESC), сливаем и режем в Python — корректный срез без
    загрузки всей таблицы.
    """
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    fetch_n = offset + limit

    # --- cutehistory WHERE ---
    conds = ["ch.user_id = $1"]
    params: list[Any] = [user_id]
    idx = 2
    if date_from:
        conds.append(f"to_timestamp(ch.data,'HH24:MI DD.MM.YYYY') >= ${idx}::date")
        params.append(date_from)
        idx += 1
    if date_to:
        conds.append(f"to_timestamp(ch.data,'HH24:MI DD.MM.YYYY') < (${idx}::date + INTERVAL '1 day')")
        params.append(date_to)
        idx += 1
    if direction == "in":
        conds.append('ch."+" IS NOT NULL')
    elif direction == "out":
        conds.append('ch."-" IS NOT NULL')
    if q:
        conds.append(f"ch.cause ILIKE '%'||${idx}||'%'")
        params.append(q)
        idx += 1
    if only_transfers:
        conds.append("ch.transfer_id IS NOT NULL")
    where = " AND ".join(conds)

    cute_total = int(await db.pool.fetchval(
        f"SELECT COUNT(*)::int FROM cutehistory ch WHERE {where}", *params
    ) or 0)
    cute_rows = await db.pool.fetch(
        f"""
        SELECT ch."+" AS plus, ch."-" AS minus, ch.cause, ch.balance, ch.transfer_id,
               to_timestamp(ch.data,'HH24:MI DD.MM.YYYY') AS ts,
               p.sender_id, p.receiver_id
        FROM cutehistory ch
        LEFT JOIN p2p_transfers p ON p.id = ch.transfer_id
        WHERE {where}
        ORDER BY ts DESC NULLS LAST
        LIMIT ${idx}
        """,
        *params, fetch_n,
    )

    # --- donate (исключается фильтром "только переводы" и направлением "out") ---
    include_donate = (not only_transfers) and direction != "out"
    donate_rows: list = []
    donate_total = 0
    if include_donate:
        dconds = ["user_id = $1"]
        dparams: list[Any] = [user_id]
        didx = 2
        if date_from:
            dconds.append(f"data::timestamptz >= ${didx}::date")
            dparams.append(date_from)
            didx += 1
        if date_to:
            dconds.append(f"data::timestamptz < (${didx}::date + INTERVAL '1 day')")
            dparams.append(date_to)
            didx += 1
        if q:
            # у донатов единственная причина — слово "донат"
            dconds.append(f"'донат' ILIKE '%'||${didx}||'%'")
            dparams.append(q)
            didx += 1
        dwhere = " AND ".join(dconds)
        donate_total = int(await db.pool.fetchval(
            f"SELECT COUNT(*)::int FROM donate WHERE {dwhere}", *dparams
        ) or 0)
        donate_rows = await db.pool.fetch(
            f"SELECT count, data::timestamptz AS ts FROM donate WHERE {dwhere} "
            f"ORDER BY ts DESC LIMIT ${didx}",
            *dparams, fetch_n,
        )

    # --- имена контрагентов (батч) ---
    cp_ids: set[int] = set()
    for r in cute_rows:
        if r["transfer_id"] is not None:
            cid = counterparty_id(cute_direction(r["plus"], r["minus"]),
                                  r["sender_id"], r["receiver_id"])
            if cid is not None:
                cp_ids.add(int(cid))
    name_map: dict[int, dict] = {}
    if cp_ids:
        name_rows = await db.pool.fetch(
            "SELECT user_id, first_name, username FROM users WHERE user_id = ANY($1::bigint[])",
            list(cp_ids),
        )
        name_map = {
            int(nr["user_id"]): {"name": nr["first_name"], "username": nr["username"]}
            for nr in name_rows
        }

    cute_items = [normalize_cute_row(r, name_map) for r in cute_rows]
    donate_items = [normalize_donate_row(r) for r in donate_rows]
    items = merge_and_paginate(cute_items, donate_items, offset, limit)
    return {"total": cute_total + donate_total, "items": items}
```

- [ ] **Step 4: Зарегистрировать роут в `server/admin_routes.py`**

Добавить импорт рядом с прочими admin-импортами (например под строкой 206 `from admin_logs import ...`):

```python
from admin_cute_history import get_user_cute_history
```

Сразу после функции `admin_user_audit` (после строки 2243) добавить роут:

```python
@router.get("/users/{target_user_id}/cute-history")
async def admin_user_cute_history(
    target_user_id: int,
    dateFrom: str | None = Query(None, max_length=32),
    dateTo: str | None = Query(None, max_length=32),
    direction: str | None = Query(None, pattern="^(in|out)$"),
    q: str | None = Query(None, max_length=200),
    onlyTransfers: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("view_players")),
):
    return await get_user_cute_history(
        target_user_id,
        date_from=dateFrom,
        date_to=dateTo,
        direction=direction,
        q=q,
        only_transfers=onlyTransfers,
        limit=limit,
        offset=offset,
    )
```

- [ ] **Step 5: Запустить все тесты cute-history — убедиться, что проходят**

Run: `cd server && python -m pytest tests/test_cute_history.py -v`
Expected: PASS (включая `test_cute_history_route_registered`)

- [ ] **Step 6: Commit**

```bash
git add server/admin_cute_history.py server/admin_routes.py server/tests/test_cute_history.py
git commit -m "feat(admin): player cute-history endpoint (cutehistory+donate+p2p)"
```

---

### Task 5: Frontend — клиент + UI фида в блоке «История»

**Files:**
- Modify: `admin/src/lib/adminClient.js` (добавить `fetchAdminUserCuteHistory` рядом с `fetchAdminUserAudit`, ~строка 1003)
- Modify: `admin/src/pages/sections/UsersSection.jsx` (импорт; компонент `CuteHistoryFeed`; переключатель источника и рендер в блоке «История», строки 1196-1254)

**Interfaces:**
- Consumes: `GET /users/{id}/cute-history` (Task 4); форма элемента из Task 3.
- Produces: `fetchAdminUserCuteHistory(userId, params) -> {total, items}`; UI-переключатель «Действия / Кут (полная)» с фильтрами.

- [ ] **Step 1: Добавить клиентскую функцию в `admin/src/lib/adminClient.js`**

Сразу после `fetchAdminUserAudit` (после строки 1008):

```javascript
export async function fetchAdminUserCuteHistory(userId, {
  dateFrom = '', dateTo = '', direction = '', q = '',
  onlyTransfers = false, limit = 50, offset = 0,
} = {}) {
  const params = new URLSearchParams()
  if (dateFrom) params.set('dateFrom', dateFrom)
  if (dateTo) params.set('dateTo', dateTo)
  if (direction) params.set('direction', direction)
  if (q) params.set('q', q)
  if (onlyTransfers) params.set('onlyTransfers', 'true')
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  return adminFetch(`/users/${userId}/cute-history?${params}`)
}
```

- [ ] **Step 2: Импортировать функцию в `UsersSection.jsx`**

В блок импортов из `'../../lib/adminClient'` (строки 3-20) добавить строку:

```javascript
  fetchAdminUserCuteHistory,
```

- [ ] **Step 3: Добавить компонент `CuteHistoryFeed` в `UsersSection.jsx`**

Вставить перед `export default function UsersSection` (перед строкой 517):

```javascript
// ---- Полная история кут (cutehistory + donate + переводы) ----
const CUTE_PAGE = 50

function CounterpartyLine({ direction, cp }) {
  const name = cp.username ? `@${cp.username}` : (cp.name || 'игрок')
  const arrow = direction === 'out' ? '→' : '←'
  return (
    <p className="panel-shelf-muted">
      {arrow} {name} <span style={{ opacity: 0.6 }}>(id {cp.userId})</span>
    </p>
  )
}

function CuteHistoryFeed({ userId }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  // filters
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [direction, setDirection] = useState('')      // '' | 'in' | 'out'
  const [q, setQ] = useState('')
  const [onlyTransfers, setOnlyTransfers] = useState(false)

  const load = useCallback(async (nextOffset) => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchAdminUserCuteHistory(userId, {
        dateFrom, dateTo, direction, q, onlyTransfers,
        limit: CUTE_PAGE, offset: nextOffset,
      })
      setTotal(data.total || 0)
      setItems((prev) => nextOffset === 0 ? (data.items || []) : [...prev, ...(data.items || [])])
      setOffset(nextOffset)
    } catch (e) {
      setError(e.message || 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }, [userId, dateFrom, dateTo, direction, q, onlyTransfers])

  // первичная загрузка и перезагрузка при смене фильтров
  useEffect(() => { load(0) }, [load])

  return (
    <div className="pu-cute">
      <div className="pu-cute-filters">
        <input type="date" className="panel-users-input" value={dateFrom}
               onChange={(e) => setDateFrom(e.target.value)} />
        <input type="date" className="panel-users-input" value={dateTo}
               onChange={(e) => setDateTo(e.target.value)} />
        <select className="panel-users-input" value={direction}
                onChange={(e) => setDirection(e.target.value)}>
          <option value="">Все</option>
          <option value="in">Начисления</option>
          <option value="out">Списания</option>
        </select>
        <input className="panel-users-input" placeholder="Поиск по причине…" value={q}
               onChange={(e) => setQ(e.target.value)} />
        <label className="pu-cute-check">
          <input type="checkbox" checked={onlyTransfers}
                 onChange={(e) => setOnlyTransfers(e.target.checked)} />
          Только переводы
        </label>
      </div>

      {error && <p className="panel-shelf-error">{error}</p>}
      {!loading && items.length === 0 && <p className="panel-shelf-muted">Записей нет</p>}

      <ul className="panel-users-audit-list">
        {items.map((it, i) => (
          <li key={i} className="panel-users-audit-item">
            <div className="panel-users-audit-head">
              <span className="panel-users-audit-type">
                {it.cause || '—'}
                {it.kind === 'donate' && <span className="pu-cute-badge">донат</span>}
                {it.kind === 'transfer' && <span className="pu-cute-badge pu-cute-badge-tr">перевод</span>}
              </span>
              <time className="panel-users-audit-time">{formatDate(it.ts)}</time>
            </div>
            <p className={`panel-users-audit-amount ${it.direction === 'in' ? 'pu-cute-in' : 'pu-cute-out'}`}>
              {it.direction === 'in' ? '+' : '−'}{Math.abs(it.amount)} kut
            </p>
            {it.balance != null && (
              <p className="panel-shelf-muted">Баланс: {it.balance}</p>
            )}
            {it.counterparty && (
              <CounterpartyLine direction={it.direction} cp={it.counterparty} />
            )}
          </li>
        ))}
      </ul>

      {items.length < total && (
        <button className="panel-users-btn" disabled={loading}
                onClick={() => load(offset + CUTE_PAGE)}>
          {loading ? '…' : `Ещё (${items.length}/${total})`}
        </button>
      )}

      <style>{`
        .pu-cute-filters { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; align-items: center; }
        .pu-cute-filters .panel-users-input { flex: 1 1 120px; min-width: 100px; }
        .pu-cute-check { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #cccccc; white-space: nowrap; }
        .pu-cute-badge { margin-left: 6px; font-size: 10px; padding: 1px 6px; border-radius: 6px; background: #2a2a30; color: #d0a94a; vertical-align: middle; }
        .pu-cute-badge-tr { color: #6fb1ff; }
        .pu-cute-in { color: #57c785; }
        .pu-cute-out { color: #e06666; }
      `}</style>
    </div>
  )
}
```

- [ ] **Step 4: Добавить переключатель источника и рендер в блок «История»**

В блоке `.panel-users-audit-block` (строки 1196-1254) добавить состояние источника и условный рендер. Сначала — состояние: в теле `UsersSection`, рядом с `const [profileTab, setProfileTab] = useState('profile')` (строка 533), добавить:

```javascript
  const [historySource, setHistorySource] = useState('audit')  // 'audit' | 'cute'
```

Затем заменить содержимое `<div className="panel-users-audit-block">` — вставить переключатель сразу после `<h3 ...>События…</h3>` (после строки 1200) и обернуть текущий рендер audit в условие `historySource === 'audit'`, добавив ветку `'cute'`:

```javascript
            <div className="panel-users-audit-block">
              <p className="panel-shelf-label">История</p>
              <h3 className="panel-users-subtitle panel-users-subtitle-tight">
                {historySource === 'audit'
                  ? <>События {hasProfile ? `(${audit?.total ?? 0})` : ''}</>
                  : 'Кут — полная история'}
              </h3>

              {hasProfile && (
                <div className="pu-hist-switch">
                  <button
                    className={`pu-hist-tab${historySource === 'audit' ? ' active' : ''}`}
                    onClick={() => setHistorySource('audit')}
                  >Действия</button>
                  <button
                    className={`pu-hist-tab${historySource === 'cute' ? ' active' : ''}`}
                    onClick={() => setHistorySource('cute')}
                  >Кут (полная)</button>
                </div>
              )}

              {hasProfile && historySource === 'cute' && (
                <CuteHistoryFeed userId={profile.userId} />
              )}

              {historySource === 'audit' && (<>
                {/* --- существующий рендер audit без изменений --- */}
                {!hasProfile && (
                  <ul className="panel-users-audit-list panel-users-audit-list-empty">
                    {[1, 2, 3].map((n) => (
                      <li key={n} className="panel-users-audit-ghost">
                        <span className="panel-users-ghost-bar panel-users-ghost-bar-wide" />
                      </li>
                    ))}
                  </ul>
                )}

                {hasProfile && (audit?.events || []).length === 0 && (
                  <p className="panel-shelf-muted">Записей пока нет</p>
                )}

                {hasProfile && (audit?.events || []).length > 0 && (
                  <ul className="panel-users-audit-list">
                    {audit.events.map((ev) => (
                      <li key={ev.id} className="panel-users-audit-item">
                        <div className="panel-users-audit-head">
                          <span className="panel-users-audit-type">
                            {EVENT_LABELS[ev.eventType] || ev.eventType}
                          </span>
                          <time className="panel-users-audit-time">{formatDate(ev.createdAt)}</time>
                        </div>
                        {ev.amount != null && (
                          <p className="panel-users-audit-amount">
                            {ev.amount > 0 ? '+' : ''}
                            {ev.amount} kut
                          </p>
                        )}
                        {ev.balanceBefore != null && ev.balanceAfter != null && (
                          <p className="panel-shelf-muted">
                            Баланс: {ev.balanceBefore} → {ev.balanceAfter}
                          </p>
                        )}
                        {ev.details?.item_id && (
                          <p className="panel-shelf-muted">
                            Предмет: {ev.details.item_id}
                            {ev.details.count_after != null && ` (осталось ${ev.details.count_after})`}
                          </p>
                        )}
                        {ev.details?.admin_user_id && (
                          <p className="panel-shelf-muted">Admin ID: {ev.details.admin_user_id}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}

                {!hasProfile && !loading && (
                  <EmptyHint>История действий игрока</EmptyHint>
                )}
              </>)}
            </div>
```

И добавить стили переключателя — в существующий большой `<style>` секции нет; используем локальный маленький блок. Добавить сразу после закрывающего `</div>` блока `.panel-users-audit-block` инлайновый стиль (или включить в стили `CuteHistoryFeed`). Проще — добавить в `<style>` внутри `CuteHistoryFeed` правила и для `.pu-hist-switch` (они всё равно на одной странице):

В `<style>` компонента `CuteHistoryFeed` (Step 3) добавить в конец:

```css
        .pu-hist-switch { display: inline-flex; gap: 4px; margin: 6px 0 10px; }
        .pu-hist-tab { font-size: 12px; padding: 4px 10px; border-radius: 8px; border: 1px solid #1c1c20; background: #0a0a0c; color: #aaa; cursor: pointer; }
        .pu-hist-tab.active { background: #1c1c22; color: #fff; }
```

> Примечание: `.pu-hist-switch` рендерится, даже когда активен `historySource==='audit'` (переключатель всегда виден при наличии профиля), а стили монтируются вместе с `CuteHistoryFeed` только при переключении на «Кут». Чтобы переключатель был стилизован в обоих режимах, вынести эти три правила в отдельный `<style>` рядом с переключателем (внутри блока `.panel-users-audit-block`, до условного рендера), а не только в `CuteHistoryFeed`.

- [ ] **Step 5: Собрать фронт — убедиться, что нет ошибок**

Run: `cd admin && npm run build`
Expected: сборка проходит без ошибок (`✓ built in …`)

- [ ] **Step 6: Commit**

```bash
git add admin/src/lib/adminClient.js admin/src/pages/sections/UsersSection.jsx
git commit -m "feat(admin-ui): full cute-history feed with transfers in Players tab"
```

---

## Self-Review

**Spec coverage:**
- Схема `cutehistory.transfer_id` + индексы → Task 1. ✅
- Бот заполняет `transfer_id` в одной транзакции → Task 2. ✅
- `get_user_cute_history` (cutehistory + LEFT JOIN p2p + donate, парсинг `to_timestamp`, фильтры, пагинация, батч-имена) → Task 3 (чистое) + Task 4 (DB). ✅
- Роут `GET /users/{id}/cute-history` под `view_players` → Task 4. ✅
- Frontend: клиент + переключатель «Действия/Кут (полная)» + фильтры (дата/направление/поиск/только переводы) + контрагенты + бейдж донатов + пагинация «Ещё» → Task 5. ✅
- Ленивая загрузка фида (только при переключении на «Кут») → Task 5, `CuteHistoryFeed` монтируется лишь при `historySource==='cute'`. ✅
- Вне рамок (не менять cutehistory_plus/minus, audit_events; без ИИ-классификации; без глобального поиска) → соблюдено, правок этих мест в задачах нет. ✅

**Placeholder scan:** плейсхолдеров нет — во всех шагах реальный код и точные команды.

**Type consistency:** форма элемента (`ts, cause, amount, direction, balance, kind, counterparty{userId,name,username}`) одинакова в Task 3 (нормализация), Task 4 (возврат) и Task 5 (рендер). Имена функций (`cute_direction`, `counterparty_id`, `normalize_cute_row`, `normalize_donate_row`, `merge_and_paginate`, `get_user_cute_history`, `fetchAdminUserCuteHistory`) согласованы между задачами. Query-параметры (`dateFrom, dateTo, direction, q, onlyTransfers, limit, offset`) совпадают между клиентом (Task 5) и роутом (Task 4).
