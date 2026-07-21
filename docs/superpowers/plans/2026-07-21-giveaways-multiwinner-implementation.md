# Розыгрыши — мульти-победители для таймер-розыгрыша — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать таймер-розыгрышу несколько призовых мест с разными призами за каждое место (1-е — NFT, 2-е — 500 КУТ, …), выбирая до N случайных победителей и начисляя каждому приз его места.

**Architecture:** Две новые таблицы (`giveaway_prizes` — приз на место, `giveaway_winners` — кто занял место) + колонка `giveaways.winners_count`. `draw_timer_giveaways` выбирает до `winners_count` различных случайных участников, раздаёт места 1..k в порядке выборки. Механика `instant` не меняется. `giveaways.winner_user_id` сохраняется как денормализованный победитель места 1 — старые розыгрыши и существующий код «главного победителя» работают без миграции данных.

**Tech Stack:** FastAPI + asyncpg (backend), React + Vite (webapp + admin panel), pytest (backend unit tests) — тот же стек, что v1/v2/v3, новых зависимостей нет.

## Global Constraints

- Следовать `docs/superpowers/specs/2026-07-21-giveaways-multiwinner-design.md` — источник истины.
- Только `draw_type='timer'` получает места/призы-по-местам. `instant` не трогаем (единый приз на всех, `winners_count=1`, без строк `giveaway_prizes`/`giveaway_winners`).
- Число победителей = число призовых мест (`winners_count = len(prizes)`); админ не задаёт его отдельно.
- `giveaways.winner_user_id` сохраняется, заполняется победителем **места 1**.
- При нехватке участников (< мест) заполняются только доступные места (k = min(winners_count, число_участников)); при нуле участников — `status='cancelled'` (как сейчас).
- Правило пула соединений: Telegram-DM и `create_admin_message_notification` отправляются ПОСЛЕ выхода из `async with self.pool.acquire()` (существующий паттерн `pending_notifications` в `draw_timer_giveaways`).
- Все новые/изменённые строки webapp и админки — на русском.
- Нет живого Postgres в этой среде — методы, трогающие БД, верифицируются `python -m py_compile` + ручной review; только чистая логика (`giveaway_draw.py`) покрывается настоящим pytest TDD. Фронтенд — `npx vite build` (webapp + admin) и `npx vitest run` (существующие тесты не должны сломаться).

---

### Task 1: Схема + backfill + чистые хелперы розыгрыша (TDD)

**Files:**
- Create: `server/giveaway_draw.py`
- Create: `server/tests/test_giveaway_draw.py`
- Modify: `server/schema.sql` (в конец файла, после блока v3 `giveaway_channel_sub_cache`)

**Interfaces:**
- Produces: `assign_winner_places(entrant_ids: list[int], winners_count: int) -> list[tuple[int, int]]` (возвращает `[(place, user_id), ...]`, place 1..k) и `prize_for_place(prizes: list[dict], place: int) -> dict | None`. Оба потребляются Task 2 (`db.py`).
- Схема: `giveaways.winners_count INT NOT NULL DEFAULT 1`, таблицы `giveaway_prizes`, `giveaway_winners`, backfill места 1 для существующих таймер-розыгрышей.

- [ ] **Step 1: Написать падающие тесты**

Создать `server/tests/test_giveaway_draw.py`:

```python
"""Розыгрыши: чистые функции распределения мест и поиска приза места, без БД."""
from giveaway_draw import assign_winner_places, prize_for_place


def test_assign_places_full_when_enough_entrants():
    assert assign_winner_places([10, 20, 30], 3) == [(1, 10), (2, 20), (3, 30)]


def test_assign_places_caps_at_winners_count():
    assert assign_winner_places([10, 20, 30, 40, 50], 2) == [(1, 10), (2, 20)]


def test_assign_places_fewer_entrants_than_places():
    # 3 места, но только 2 участника — заполняются места 1 и 2, место 3 пустое.
    assert assign_winner_places([10, 20], 3) == [(1, 10), (2, 20)]


def test_assign_places_empty_entrants():
    assert assign_winner_places([], 3) == []


def test_assign_places_order_is_place_order():
    # Порядок входа = порядок мест (вызывающий передаёт уже перемешанный ORDER BY random()).
    assert assign_winner_places([99, 7, 42], 3) == [(1, 99), (2, 7), (3, 42)]


def test_prize_for_place_found():
    prizes = [
        {"place": 1, "prize_type": "manual", "prize_title": "NFT"},
        {"place": 2, "prize_type": "kut", "prize_kut_amount": 500},
    ]
    assert prize_for_place(prizes, 1) == {"place": 1, "prize_type": "manual", "prize_title": "NFT"}
    assert prize_for_place(prizes, 2) == {"place": 2, "prize_type": "kut", "prize_kut_amount": 500}


def test_prize_for_place_missing_returns_none():
    prizes = [{"place": 1, "prize_type": "kut", "prize_kut_amount": 100}]
    assert prize_for_place(prizes, 2) is None
    assert prize_for_place([], 1) is None
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `cd server && python -m pytest tests/test_giveaway_draw.py -v`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'giveaway_draw'`

- [ ] **Step 3: Написать реализацию**

Создать `server/giveaway_draw.py`:

```python
"""Розыгрыши: чистые функции распределения победителей по местам и поиска
приза для места — без обращения к БД, легко покрываются юнит-тестами.

Мульти-победители только у таймер-розыгрыша: до winners_count различных
случайных участников получают места 1..k (k = min(winners_count, число
участников)); каждому месту соответствует свой приз из giveaway_prizes.
"""
from __future__ import annotations


def assign_winner_places(entrant_ids: list[int], winners_count: int) -> list[tuple[int, int]]:
    """entrant_ids уже в нужном порядке (вызывающий передаёт результат
    ORDER BY random()). Возвращает [(place, user_id), ...], place 1..k,
    k = min(winners_count, len(entrant_ids))."""
    k = min(int(winners_count), len(entrant_ids))
    return [(place, entrant_ids[place - 1]) for place in range(1, k + 1)]


def prize_for_place(prizes: list[dict], place: int) -> dict | None:
    for prize in prizes:
        if prize.get("place") == place:
            return prize
    return None
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `cd server && python -m pytest tests/test_giveaway_draw.py -v`
Expected: 8 passed

- [ ] **Step 5: Добавить схему и backfill**

В `server/schema.sql`, в самый конец файла (после блока v3 `giveaway_channel_sub_cache`), добавить:

```sql

-- Мульти-победители таймер-розыгрыша: несколько призовых мест с разными
-- призами за место. Только draw_type='timer'; instant не трогается.
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

-- Backfill: каждый существующий таймер-розыгрыш получает приз места 1 из своих
-- текущих одиночных полей giveaways.prize_*; каждый завершённый — победителя
-- места 1 из winner_user_id. ON CONFLICT DO NOTHING делает это идемпотентным.
INSERT INTO giveaway_prizes (giveaway_id, place, prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description)
SELECT id, 1, prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description
FROM giveaways WHERE draw_type = 'timer'
ON CONFLICT (giveaway_id, place) DO NOTHING;

INSERT INTO giveaway_winners (giveaway_id, place, user_id)
SELECT id, 1, winner_user_id
FROM giveaways WHERE draw_type = 'timer' AND status = 'completed' AND winner_user_id IS NOT NULL
ON CONFLICT (giveaway_id, place) DO NOTHING;
```

- [ ] **Step 6: Verify schema.sql smoke-check**

Run: `cd server && python -c "sql=open('schema.sql',encoding='utf-8').read(); assert 'giveaway_prizes' in sql and 'giveaway_winners' in sql and 'winners_count' in sql; print('OK')"`
Expected: prints `OK`

- [ ] **Step 7: Запустить весь бэкенд-набор**

Run: `cd server && python -m pytest -v`
Expected: все проходят (существующие 23 + 8 новых = 31 passed)

- [ ] **Step 8: Commit**

```bash
git add server/giveaway_draw.py server/tests/test_giveaway_draw.py server/schema.sql
git commit -m "feat(giveaways): add multi-winner schema (prizes/winners tables) + pure draw helpers"
```

---

### Task 2: `db.py` — розыгрыш нескольких победителей

**Files:**
- Modify: `server/db.py`

**Interfaces:**
- Consumes: `assign_winner_places`, `prize_for_place` (Task 1).
- Produces: приватные методы `_giveaway_prizes(self, conn, giveaway_id) -> list[dict]` и `_giveaway_winners(self, conn, giveaway_id) -> list[dict]` (потребляются Task 3). `draw_timer_giveaways` раздаёт места 1..k.

- [ ] **Step 1: Добавить импорт**

В `server/db.py` найти (строка 89):

```python
from giveaway_display import display_name, giveaway_bucket
```

Заменить на:

```python
from giveaway_display import display_name, giveaway_bucket
from giveaway_draw import assign_winner_places, prize_for_place
```

- [ ] **Step 2: Добавить хелперы чтения призов/победителей рядом с `_giveaway_participants`**

В `server/db.py` найти метод `_giveaway_prize_summary` (сразу перед `_giveaway_participants` или рядом; он начинается с `def _giveaway_prize_summary(self, row):`). Сразу ПОСЛЕ конца `_giveaway_prize_summary` (после его `return {...}` для manual-ветки) добавить два метода:

```python
    async def _giveaway_prizes(self, conn, giveaway_id):
        rows = await conn.fetch(
            """
            SELECT place, prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description
            FROM giveaway_prizes WHERE giveaway_id = $1 ORDER BY place
            """,
            giveaway_id,
        )
        return [dict(r) for r in rows]

    async def _giveaway_winners(self, conn, giveaway_id):
        rows = await conn.fetch(
            """
            SELECT w.place, w.user_id, u.username, u.first_name
            FROM giveaway_winners w
            LEFT JOIN users u ON u.user_id = w.user_id
            WHERE w.giveaway_id = $1 ORDER BY w.place
            """,
            giveaway_id,
        )
        return [dict(r) for r in rows]
```

Найти существующий метод-разметку `_giveaway_prize_summary` целиком:

```python
    def _giveaway_prize_summary(self, row):
        if row["prize_type"] == "kut":
            return {
                "type": "kut",
                "amount": int(row["prize_kut_amount"] or 0),
            }
        return {
            "type": "manual",
            "title": row["prize_title"],
            "emoji": row["prize_emoji"],
            "description": row["prize_description"],
        }
```

Заменить на (та же функция + два новых метода после неё):

```python
    def _giveaway_prize_summary(self, row):
        if row["prize_type"] == "kut":
            return {
                "type": "kut",
                "amount": int(row["prize_kut_amount"] or 0),
            }
        return {
            "type": "manual",
            "title": row["prize_title"],
            "emoji": row["prize_emoji"],
            "description": row["prize_description"],
        }

    async def _giveaway_prizes(self, conn, giveaway_id):
        rows = await conn.fetch(
            """
            SELECT place, prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description
            FROM giveaway_prizes WHERE giveaway_id = $1 ORDER BY place
            """,
            giveaway_id,
        )
        return [dict(r) for r in rows]

    async def _giveaway_winners(self, conn, giveaway_id):
        rows = await conn.fetch(
            """
            SELECT w.place, w.user_id, u.username, u.first_name
            FROM giveaway_winners w
            LEFT JOIN users u ON u.user_id = w.user_id
            WHERE w.giveaway_id = $1 ORDER BY w.place
            """,
            giveaway_id,
        )
        return [dict(r) for r in rows]
```

- [ ] **Step 3: Переписать тело выбора победителя в `draw_timer_giveaways`**

В `server/db.py` найти (внутри `draw_timer_giveaways`, блок от выбора одного победителя до `pending_notifications.append`):

```python
                    winner = await conn.fetchval(
                        """
                        SELECT user_id FROM giveaway_entries
                        WHERE giveaway_id = $1
                        ORDER BY random() LIMIT 1
                        """,
                        giveaway_id,
                    )
                    if winner is None:
                        await conn.execute(
                            "UPDATE giveaways SET status = 'cancelled', drawn_at = NOW() WHERE id = $1",
                            giveaway_id,
                        )
                        continue
                    await conn.execute(
                        """
                        UPDATE giveaways
                        SET status = 'completed', winner_user_id = $2, drawn_at = NOW()
                        WHERE id = $1
                        """,
                        giveaway_id, winner,
                    )
                    if giveaway["prize_type"] == "kut":
                        amount = int(giveaway["prize_kut_amount"] or 0)
                        balance_before = await conn.fetchval(
                            "SELECT balance FROM users WHERE user_id = $1", winner
                        )
                        balance_before = int(balance_before or 0)
                        balance_after = balance_before + amount
                        await conn.execute(
                            "UPDATE users SET balance = $2 WHERE user_id = $1",
                            winner, balance_after,
                        )
                        schedule_balance_event(
                            self.pool,
                            "giveaway_reward",
                            winner,
                            amount=amount,
                            balance_before=balance_before,
                            balance_after=balance_after,
                            details={"giveaway_id": giveaway_id, "title": giveaway["title"]},
                        )
                    prize_text = (
                        f"{giveaway['prize_kut_amount']} КУТ"
                        if giveaway["prize_type"] == "kut"
                        else (giveaway["prize_title"] or "приз")
                    )
                    schedule_player_telegram_dm(
                        winner,
                        f"🎉 Вы выиграли в розыгрыше «{giveaway['title']}»! Приз: {prize_text}",
                    )
                    log_game_event(
                        self.pool,
                        "giveaway_drawn",
                        winner,
                        {"giveaway_id": giveaway_id},
                    )
                    pending_notifications.append((winner, giveaway["title"], prize_text))
```

Заменить на:

```python
                    entrant_ids = [
                        r["user_id"]
                        for r in await conn.fetch(
                            """
                            SELECT user_id FROM giveaway_entries
                            WHERE giveaway_id = $1
                            ORDER BY random() LIMIT $2
                            """,
                            giveaway_id, int(giveaway["winners_count"] or 1),
                        )
                    ]
                    if not entrant_ids:
                        await conn.execute(
                            "UPDATE giveaways SET status = 'cancelled', drawn_at = NOW() WHERE id = $1",
                            giveaway_id,
                        )
                        continue
                    prizes = await self._giveaway_prizes(conn, giveaway_id)
                    placed = assign_winner_places(entrant_ids, int(giveaway["winners_count"] or 1))
                    first_winner = placed[0][1]
                    await conn.execute(
                        """
                        UPDATE giveaways
                        SET status = 'completed', winner_user_id = $2, drawn_at = NOW()
                        WHERE id = $1
                        """,
                        giveaway_id, first_winner,
                    )
                    for place, winner in placed:
                        await conn.execute(
                            "INSERT INTO giveaway_winners (giveaway_id, place, user_id) VALUES ($1, $2, $3)",
                            giveaway_id, place, winner,
                        )
                        prize = prize_for_place(prizes, place)
                        if prize is not None and prize["prize_type"] == "kut":
                            amount = int(prize["prize_kut_amount"] or 0)
                            balance_before = await conn.fetchval(
                                "SELECT balance FROM users WHERE user_id = $1", winner
                            )
                            balance_before = int(balance_before or 0)
                            balance_after = balance_before + amount
                            await conn.execute(
                                "UPDATE users SET balance = $2 WHERE user_id = $1",
                                winner, balance_after,
                            )
                            schedule_balance_event(
                                self.pool,
                                "giveaway_reward",
                                winner,
                                amount=amount,
                                balance_before=balance_before,
                                balance_after=balance_after,
                                details={"giveaway_id": giveaway_id, "title": giveaway["title"], "place": place},
                            )
                        if prize is None:
                            prize_text = "приз"
                        elif prize["prize_type"] == "kut":
                            prize_text = f"{prize['prize_kut_amount']} КУТ"
                        else:
                            prize_text = prize["prize_title"] or "приз"
                        schedule_player_telegram_dm(
                            winner,
                            f"🎉 Вы заняли {place} место в розыгрыше «{giveaway['title']}»! Приз: {prize_text}",
                        )
                        log_game_event(
                            self.pool,
                            "giveaway_drawn",
                            winner,
                            {"giveaway_id": giveaway_id, "place": place},
                        )
                        pending_notifications.append((winner, giveaway["title"], place, prize_text))
```

- [ ] **Step 4: Обновить отправку отложенных админ-уведомлений (кортеж теперь 4-элементный)**

Найти:

```python
        for winner, title, prize_text in pending_notifications:
            await create_admin_message_notification(
                self.pool,
                winner,
                title="Вы выиграли в розыгрыше!",
                body=f"«{title}» — приз: {prize_text}",
            )
```

Заменить на:

```python
        for winner, title, place, prize_text in pending_notifications:
            await create_admin_message_notification(
                self.pool,
                winner,
                title="Вы выиграли в розыгрыше!",
                body=f"«{title}» — {place} место, приз: {prize_text}",
            )
```

- [ ] **Step 5: Verify компилируется**

Run: `cd server && python -m py_compile db.py`
Expected: no output, exit code 0

- [ ] **Step 6: Ручной review-чеклист (нет живой БД)**

Подтвердить чтением диффа:
- Выбор победителей — один запрос `ORDER BY random() LIMIT winners_count`; при пустом результате — `cancelled` (как раньше).
- Начисление КУТ и `giveaway_winners`-инсерт идут внутри существующей `FOR UPDATE`-транзакции; Telegram-DM/админ-уведомления по-прежнему в `pending_notifications` и отправляются после выхода из `async with self.pool.acquire()`.
- `winner_user_id` = победитель места 1 (`placed[0][1]`).
- `_giveaway_prizes` использует переданный `conn` (не берёт своё соединение из пула).

- [ ] **Step 7: Запустить полный бэкенд-набор**

Run: `cd server && python -m pytest -v`
Expected: 31 passed (без изменений от Task 1)

- [ ] **Step 8: Commit**

```bash
git add server/db.py
git commit -m "feat(giveaways): draw up to winners_count winners, credit each place its own prize"
```

---

### Task 3: `db.py` — пути чтения (detail, list, history, feed)

**Files:**
- Modify: `server/db.py`

**Interfaces:**
- Consumes: `_giveaway_prizes`, `_giveaway_winners` (Task 2), `display_name` (существует).
- Produces: `get_giveaway_detail` → `winners`, `prizesByPlace`, `result.place`. `get_giveaways_state` items → `winnersCount`. `get_giveaways_history` items → `winnersCount`. `get_giveaway_winners_feed` → по записи на призёра-места. Имена полей — на них опирается фронтенд (Task 6/7).

- [ ] **Step 1: `get_giveaways_state` — добавить `winnersCount` в item**

В `server/db.py` найти в `get_giveaways_state` формирование item (строки с `"drawType": row["draw_type"],`) — конкретно блок:

```python
                    "prize": self._giveaway_prize_summary(row),
                    "drawType": row["draw_type"],
                    "startsAt": row["starts_at"].isoformat() if row["starts_at"] else None,
```

Заменить на:

```python
                    "prize": self._giveaway_prize_summary(row),
                    "drawType": row["draw_type"],
                    "winnersCount": int(row["winners_count"] or 1),
                    "startsAt": row["starts_at"].isoformat() if row["starts_at"] else None,
```

- [ ] **Step 2: `get_giveaway_detail` — добавить `prizesByPlace`, `winners`, `result.place`**

Найти в `get_giveaway_detail` блок вычисления result/winner_name/recipients (он идёт после `condition_progress` и до финального `return`):

```python
            result = None
            winner_name = None
            recipients_count = None
            if row["status"] == "completed":
                result = {"won": row["winner_user_id"] == user_id}
                if row["draw_type"] == "timer":
                    winner_row = await conn.fetchrow(
                        "SELECT username, first_name FROM users WHERE user_id = $1", row["winner_user_id"],
                    )
                    winner_name = display_name(winner_row["username"], winner_row["first_name"]) if winner_row else None
                else:
                    recipients_count, _ = await self._giveaway_participants(conn, giveaway_id, limit=0)
            elif row["status"] == "cancelled":
                result = {"won": False}
```

Заменить на:

```python
            prizes = await self._giveaway_prizes(conn, giveaway_id) if row["draw_type"] == "timer" else []
            winner_rows = (
                await self._giveaway_winners(conn, giveaway_id)
                if row["draw_type"] == "timer" and row["status"] == "completed"
                else []
            )
            result = None
            winner_name = None
            recipients_count = None
            if row["status"] == "completed":
                won_place = next((w["place"] for w in winner_rows if w["user_id"] == user_id), None)
                result = {"won": row["winner_user_id"] == user_id or won_place is not None, "place": won_place}
                if row["draw_type"] == "timer":
                    first = next((w for w in winner_rows if w["place"] == 1), None)
                    winner_name = display_name(first["username"], first["first_name"]) if first else None
                else:
                    recipients_count, _ = await self._giveaway_participants(conn, giveaway_id, limit=0)
            elif row["status"] == "cancelled":
                result = {"won": False, "place": None}
```

Затем найти финальный `return` в `get_giveaway_detail`:

```python
            "conditions": condition_progress,
            "conditionsMet": all(c["satisfied"] for c in condition_progress),
            "joined": bool(joined),
            "result": result,
            "winnerName": winner_name,
            "recipientsCount": recipients_count,
        }
```

Заменить на:

```python
            "conditions": condition_progress,
            "conditionsMet": all(c["satisfied"] for c in condition_progress),
            "joined": bool(joined),
            "result": result,
            "winnerName": winner_name,
            "recipientsCount": recipients_count,
            "winnersCount": int(row["winners_count"] or 1),
            "prizesByPlace": [
                {"place": p["place"], "prize": self._giveaway_prize_summary(p)} for p in prizes
            ],
            "winners": [
                {
                    "place": w["place"],
                    "displayName": display_name(w["username"], w["first_name"]),
                    "prize": self._giveaway_prize_summary(prize_for_place(prizes, w["place"]))
                    if prize_for_place(prizes, w["place"]) else None,
                }
                for w in winner_rows
            ],
        }
```

(`_giveaway_prize_summary` работает на строке `giveaway_prizes` — там есть все нужные поля `prize_type/prize_kut_amount/prize_title/prize_emoji/prize_description`.)

- [ ] **Step 3: `get_giveaways_history` — добавить `winnersCount`**

Найти в `get_giveaways_history` формирование item:

```python
                "winnerName": display_name(row["winner_username"], row["winner_first_name"]) if is_timer else None,
                "recipientsCount": None if is_timer else int(row["entries_count"] or 0),
                "drawnAt": row["drawn_at"].isoformat() if row["drawn_at"] else None,
```

Заменить на:

```python
                "winnerName": display_name(row["winner_username"], row["winner_first_name"]) if is_timer else None,
                "recipientsCount": None if is_timer else int(row["entries_count"] or 0),
                "winnersCount": int(row["winners_count"] or 1),
                "drawnAt": row["drawn_at"].isoformat() if row["drawn_at"] else None,
```

(`get_giveaways_history` уже делает `SELECT g.*`, поэтому `winners_count` доступен без изменения запроса.)

- [ ] **Step 4: `get_giveaway_winners_feed` — timer-часть по местам**

Найти запрос `timer_rows` в `get_giveaway_winners_feed`:

```python
        timer_rows = await self.pool.fetch(
            """
            SELECT g.title, g.emoji, g.prize_type, g.prize_kut_amount, g.prize_title, g.prize_emoji, g.prize_description,
                   u.username, u.first_name, g.drawn_at AS at
            FROM giveaways g
            LEFT JOIN users u ON u.user_id = g.winner_user_id
            WHERE g.draw_type = 'timer' AND g.status = 'completed' AND g.winner_user_id IS NOT NULL AND g.enabled = TRUE
            ORDER BY g.drawn_at DESC
            LIMIT $1
            """,
            limit,
        )
```

Заменить на (join к `giveaway_winners` + приз места из `giveaway_prizes`):

```python
        timer_rows = await self.pool.fetch(
            """
            SELECT g.title, g.emoji,
                   p.prize_type, p.prize_kut_amount, p.prize_title, p.prize_emoji, p.prize_description,
                   u.username, u.first_name, g.drawn_at AS at
            FROM giveaway_winners w
            JOIN giveaways g ON g.id = w.giveaway_id
            LEFT JOIN giveaway_prizes p ON p.giveaway_id = w.giveaway_id AND p.place = w.place
            LEFT JOIN users u ON u.user_id = w.user_id
            WHERE g.draw_type = 'timer' AND g.status = 'completed' AND g.enabled = TRUE
            ORDER BY g.drawn_at DESC
            LIMIT $1
            """,
            limit,
        )
```

(`_giveaway_prize_summary(r)` вызывается ниже на этих строках — у них есть все `prize_*` поля из `giveaway_prizes p`. Если у места нет строки приза, `prize_type` будет NULL → `_giveaway_prize_summary` вернёт manual-ветку с пустыми полями; это безопасно, но для таймер-розыгрышей после этой фичи приз места всегда есть.)

- [ ] **Step 5: Verify компилируется**

Run: `cd server && python -m py_compile db.py`
Expected: no output, exit code 0

- [ ] **Step 6: Ручной review-чеклист**

- `_giveaway_prizes`/`_giveaway_winners` в `get_giveaway_detail` вызываются с тем же `conn` из `async with self.pool.acquire()` (внутри блока) — HTTP-вызовов тут нет, правило пула соблюдается тривиально.
- `winnersCount` добавлен в list-item, detail, history-item.
- `get_giveaway_winners_feed`'s timer-запрос теперь по `giveaway_winners` — каждый призёр отдельной строкой; поля приза берутся из `giveaway_prizes` по месту.
- `result.place` — место победившего зрителя или None.

- [ ] **Step 7: Запустить полный бэкенд-набор**

Run: `cd server && python -m pytest -v`
Expected: 31 passed

- [ ] **Step 8: Commit**

```bash
git add server/db.py
git commit -m "feat(giveaways): expose winnersCount/prizesByPlace/winners in detail, list, history, feed"
```

---

### Task 4: Админ-бэкенд — призы по местам в create/update/validate/dict

**Files:**
- Modify: `server/admin_giveaways.py`

**Interfaces:**
- Consumes: ничего нового.
- Produces: `_validate_prizes(prizes: list[dict]) -> list[dict]` (чистит/валидирует список призов по местам). `create_giveaway`/`update_giveaway` принимают `prizes: list[dict] | None`, пишут `giveaway_prizes`, ставят `winners_count`. `_giveaway_to_admin_dict(row, conditions, entries_count, prizes, winners)` возвращает `winnersCount`, `prizes`, `winners`. Потребляются Task 5 (роуты).

- [ ] **Step 1: Добавить `_validate_prizes` и `_replace_prizes` рядом с `_validate_conditions`/`_replace_conditions`**

В `server/admin_giveaways.py` найти конец `_replace_conditions` (метод, заканчивающийся вставкой в `giveaway_conditions`):

```python
async def _replace_conditions(conn, giveaway_id: int, conditions: list[dict]) -> None:
    await conn.execute("DELETE FROM giveaway_conditions WHERE giveaway_id = $1", giveaway_id)
    for cond in conditions:
        await conn.execute(
            """
            INSERT INTO giveaway_conditions (giveaway_id, kind, target_value, item_id, sort_order)
            VALUES ($1, $2, $3, $4, $5)
            """,
            giveaway_id, cond["kind"], cond["target_value"], cond["item_id"], cond["sort_order"],
        )
```

Добавить сразу ПОСЛЕ него:

```python
def _validate_prizes(prizes: list[dict]) -> list[dict]:
    """Список призов по местам для таймер-розыгрыша. Место = индекс+1.
    Каждый приз валидируется теми же правилами, что и одиночный (_validate_prize)."""
    cleaned = []
    for idx, prize in enumerate(prizes or []):
        p_type, kut, title, emoji, desc = _validate_prize(
            prize.get("prize_type") or prize.get("prizeType"),
            prize.get("prize_kut_amount") if prize.get("prize_kut_amount") is not None else prize.get("prizeKutAmount"),
            prize.get("prize_title") if prize.get("prize_title") is not None else prize.get("prizeTitle"),
            prize.get("prize_emoji") if prize.get("prize_emoji") is not None else prize.get("prizeEmoji"),
            prize.get("prize_description") if prize.get("prize_description") is not None else prize.get("prizeDescription"),
        )
        cleaned.append({
            "place": idx + 1,
            "prize_type": p_type,
            "prize_kut_amount": kut,
            "prize_title": title,
            "prize_emoji": emoji,
            "prize_description": desc,
        })
    return cleaned


async def _replace_prizes(conn, giveaway_id: int, prizes: list[dict]) -> None:
    await conn.execute("DELETE FROM giveaway_prizes WHERE giveaway_id = $1", giveaway_id)
    for prize in prizes:
        await conn.execute(
            """
            INSERT INTO giveaway_prizes (giveaway_id, place, prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            giveaway_id, prize["place"], prize["prize_type"], prize["prize_kut_amount"],
            prize["prize_title"], prize["prize_emoji"], prize["prize_description"],
        )
```

- [ ] **Step 2: `_giveaway_to_admin_dict` — принять и вернуть prizes/winners/winnersCount**

Найти:

```python
def _giveaway_to_admin_dict(row: dict, conditions: list[dict], entries_count: int) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "emoji": row["emoji"],
        "rarity": row["rarity"],
        "prizeType": row["prize_type"],
        "prizeKutAmount": row["prize_kut_amount"],
        "prizeTitle": row["prize_title"],
        "prizeEmoji": row["prize_emoji"],
        "prizeDescription": row["prize_description"],
        "drawType": row["draw_type"],
        "startsAt": row["starts_at"].isoformat() if row["starts_at"] else None,
        "endsAt": row["ends_at"].isoformat() if row["ends_at"] else None,
        "status": row["status"],
        "winnerUserId": row["winner_user_id"],
        "enabled": row["enabled"],
        "entriesCount": entries_count,
        "conditions": [
            {"kind": c["kind"], "targetValue": c["target_value"], "itemId": c["item_id"]}
            for c in conditions
        ],
    }
```

Заменить на:

```python
def _giveaway_to_admin_dict(row: dict, conditions: list[dict], entries_count: int,
                            prizes: list[dict] | None = None, winners: list[dict] | None = None) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "emoji": row["emoji"],
        "rarity": row["rarity"],
        "prizeType": row["prize_type"],
        "prizeKutAmount": row["prize_kut_amount"],
        "prizeTitle": row["prize_title"],
        "prizeEmoji": row["prize_emoji"],
        "prizeDescription": row["prize_description"],
        "drawType": row["draw_type"],
        "winnersCount": int(row["winners_count"] or 1),
        "startsAt": row["starts_at"].isoformat() if row["starts_at"] else None,
        "endsAt": row["ends_at"].isoformat() if row["ends_at"] else None,
        "status": row["status"],
        "winnerUserId": row["winner_user_id"],
        "enabled": row["enabled"],
        "entriesCount": entries_count,
        "conditions": [
            {"kind": c["kind"], "targetValue": c["target_value"], "itemId": c["item_id"]}
            for c in conditions
        ],
        "prizes": [
            {
                "place": p["place"], "prizeType": p["prize_type"], "prizeKutAmount": p["prize_kut_amount"],
                "prizeTitle": p["prize_title"], "prizeEmoji": p["prize_emoji"], "prizeDescription": p["prize_description"],
            }
            for p in (prizes or [])
        ],
        "winners": [{"place": w["place"], "userId": w["user_id"]} for w in (winners or [])],
    }
```

- [ ] **Step 3: `list_giveaways_admin` — подгружать prizes/winners**

Найти в `list_giveaways_admin` тело цикла (после чтения `conditions` и `entries_count`):

```python
        result.append(_giveaway_to_admin_dict(row, [dict(c) for c in conditions], entries_count))
    return result
```

Заменить на:

```python
        prizes = await db.pool.fetch(
            "SELECT place, prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description "
            "FROM giveaway_prizes WHERE giveaway_id = $1 ORDER BY place",
            row["id"],
        )
        winners = await db.pool.fetch(
            "SELECT place, user_id FROM giveaway_winners WHERE giveaway_id = $1 ORDER BY place",
            row["id"],
        )
        result.append(_giveaway_to_admin_dict(
            row, [dict(c) for c in conditions], entries_count,
            [dict(p) for p in prizes], [dict(w) for w in winners],
        ))
    return result
```

- [ ] **Step 4: `create_giveaway` — принять `prizes`, писать giveaway_prizes + winners_count для timer**

Найти сигнатуру `create_giveaway` — добавить параметр `prizes`. Найти:

```python
    draw_type: str,
    ends_at=None,
    starts_at=None,
    conditions: list[dict] | None = None,
    enabled: bool = True,
    admin_user_id: int,
) -> dict:
    title = (title or "").strip()
    if not title:
        raise ValueError("Укажите название розыгрыша")
    rarity = _validate_rarity(rarity)
    prize_type, kut_amount, p_title, p_emoji, p_desc = _validate_prize(
        prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description
    )
    draw_type = _validate_draw(draw_type, ends_at, starts_at)
    cleaned_conditions = _validate_conditions(conditions or [])
```

Заменить на:

```python
    draw_type: str,
    ends_at=None,
    starts_at=None,
    conditions: list[dict] | None = None,
    prizes: list[dict] | None = None,
    enabled: bool = True,
    admin_user_id: int,
) -> dict:
    title = (title or "").strip()
    if not title:
        raise ValueError("Укажите название розыгрыша")
    rarity = _validate_rarity(rarity)
    draw_type = _validate_draw(draw_type, ends_at, starts_at)
    cleaned_conditions = _validate_conditions(conditions or [])
    # timer: призы по местам; instant: единый приз в top-level полях.
    if draw_type == "timer":
        cleaned_prizes = _validate_prizes(prizes or [])
        if not cleaned_prizes:
            raise ValueError("Укажите хотя бы одно призовое место")
        # giveaways.prize_* денормализуют приз места 1 — существующий вывод
        # «главного приза» (_giveaway_prize_summary(row)) работает без спец-кейса.
        first = cleaned_prizes[0]
        prize_type, kut_amount, p_title, p_emoji, p_desc = (
            first["prize_type"], first["prize_kut_amount"], first["prize_title"],
            first["prize_emoji"], first["prize_description"],
        )
        winners_count = len(cleaned_prizes)
    else:
        prize_type, kut_amount, p_title, p_emoji, p_desc = _validate_prize(
            prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description
        )
        cleaned_prizes = []
        winners_count = 1
```

Найти INSERT и последующий `_replace_conditions`:

```python
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            giveaway_id = await conn.fetchval(
                """
                INSERT INTO giveaways (
                    title, description, emoji, rarity, prize_type, prize_kut_amount,
                    prize_title, prize_emoji, prize_description, draw_type, ends_at,
                    starts_at, enabled, sort_order
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING id
                """,
                title, (description or "").strip(), (emoji or "🎁").strip() or "🎁", rarity,
                prize_type, kut_amount, p_title, p_emoji, p_desc, draw_type, ends_at,
                starts_at, bool(enabled), sort_order,
            )
            await _replace_conditions(conn, int(giveaway_id), cleaned_conditions)

    row = await db.pool.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
    return _giveaway_to_admin_dict(dict(row), cleaned_conditions, 0)
```

Заменить на:

```python
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            giveaway_id = await conn.fetchval(
                """
                INSERT INTO giveaways (
                    title, description, emoji, rarity, prize_type, prize_kut_amount,
                    prize_title, prize_emoji, prize_description, draw_type, ends_at,
                    starts_at, enabled, sort_order, winners_count
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id
                """,
                title, (description or "").strip(), (emoji or "🎁").strip() or "🎁", rarity,
                prize_type, kut_amount, p_title, p_emoji, p_desc, draw_type, ends_at,
                starts_at, bool(enabled), sort_order, winners_count,
            )
            await _replace_conditions(conn, int(giveaway_id), cleaned_conditions)
            if cleaned_prizes:
                await _replace_prizes(conn, int(giveaway_id), cleaned_prizes)

    row = await db.pool.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
    return _giveaway_to_admin_dict(dict(row), cleaned_conditions, 0, cleaned_prizes, [])
```

- [ ] **Step 5: `update_giveaway` — принять `prizes`, перезаписать giveaway_prizes + winners_count для timer**

Найти сигнатуру `update_giveaway` — добавить параметр `prizes`. Найти:

```python
    conditions: list[dict] | None = None,
    enabled: bool | None = None,
    admin_user_id: int,
) -> dict:
    row = await db.pool.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
    if row is None:
        raise ValueError("Розыгрыш не найден")
```

Заменить на:

```python
    conditions: list[dict] | None = None,
    prizes: list[dict] | None = None,
    enabled: bool | None = None,
    admin_user_id: int,
) -> dict:
    row = await db.pool.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
    if row is None:
        raise ValueError("Розыгрыш не найден")
```

Найти конец построения `sets`/`params` — блок `if enabled is not None:` и вычисление `cleaned_conditions`:

```python
    if enabled is not None:
        params.append(bool(enabled))
        sets.append(f"enabled = ${len(params)}")

    cleaned_conditions = _validate_conditions(conditions) if conditions is not None else None

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            if len(sets) > 1:
                await conn.execute(f"UPDATE giveaways SET {', '.join(sets)} WHERE id = $1", *params)
            if cleaned_conditions is not None:
                await _replace_conditions(conn, giveaway_id, cleaned_conditions)
```

Заменить на:

```python
    if enabled is not None:
        params.append(bool(enabled))
        sets.append(f"enabled = ${len(params)}")

    cleaned_conditions = _validate_conditions(conditions) if conditions is not None else None

    # Призы по местам обновляются только если prizes переданы. Итоговый тип
    # розыгрыша (после возможной смены drawType) определяет, писать ли места.
    final_draw_type = draw_type if draw_type is not None else row["draw_type"]
    cleaned_prizes = None
    if prizes is not None and final_draw_type == "timer":
        cleaned_prizes = _validate_prizes(prizes)
        if not cleaned_prizes:
            raise ValueError("Укажите хотя бы одно призовое место")
        first = cleaned_prizes[0]
        params.append(len(cleaned_prizes)); sets.append(f"winners_count = ${len(params)}")
        params.append(first["prize_type"]); sets.append(f"prize_type = ${len(params)}")
        params.append(first["prize_kut_amount"]); sets.append(f"prize_kut_amount = ${len(params)}")
        params.append(first["prize_title"]); sets.append(f"prize_title = ${len(params)}")
        params.append(first["prize_emoji"]); sets.append(f"prize_emoji = ${len(params)}")
        params.append(first["prize_description"]); sets.append(f"prize_description = ${len(params)}")

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            if len(sets) > 1:
                await conn.execute(f"UPDATE giveaways SET {', '.join(sets)} WHERE id = $1", *params)
            if cleaned_conditions is not None:
                await _replace_conditions(conn, giveaway_id, cleaned_conditions)
            if cleaned_prizes is not None:
                await _replace_prizes(conn, giveaway_id, cleaned_prizes)
```

Найти финал `update_giveaway` (сбор ответа):

```python
    updated = await db.pool.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
    final_conditions = await db.pool.fetch(
        "SELECT kind, target_value, item_id FROM giveaway_conditions WHERE giveaway_id = $1 ORDER BY sort_order",
        giveaway_id,
    )
    entries_count = int(
        await db.pool.fetchval(
            "SELECT COUNT(*)::int FROM giveaway_entries WHERE giveaway_id = $1", giveaway_id
        ) or 0
    )
    return _giveaway_to_admin_dict(dict(updated), [dict(c) for c in final_conditions], entries_count)
```

Заменить на:

```python
    updated = await db.pool.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
    final_conditions = await db.pool.fetch(
        "SELECT kind, target_value, item_id FROM giveaway_conditions WHERE giveaway_id = $1 ORDER BY sort_order",
        giveaway_id,
    )
    final_prizes = await db.pool.fetch(
        "SELECT place, prize_type, prize_kut_amount, prize_title, prize_emoji, prize_description "
        "FROM giveaway_prizes WHERE giveaway_id = $1 ORDER BY place",
        giveaway_id,
    )
    final_winners = await db.pool.fetch(
        "SELECT place, user_id FROM giveaway_winners WHERE giveaway_id = $1 ORDER BY place",
        giveaway_id,
    )
    entries_count = int(
        await db.pool.fetchval(
            "SELECT COUNT(*)::int FROM giveaway_entries WHERE giveaway_id = $1", giveaway_id
        ) or 0
    )
    return _giveaway_to_admin_dict(
        dict(updated), [dict(c) for c in final_conditions], entries_count,
        [dict(p) for p in final_prizes], [dict(w) for w in final_winners],
    )
```

- [ ] **Step 6: Verify компилируется**

Run: `cd server && python -m py_compile admin_giveaways.py`
Expected: no output, exit code 0

- [ ] **Step 7: Запустить полный бэкенд-набор**

Run: `cd server && python -m pytest -v`
Expected: 31 passed

- [ ] **Step 8: Commit**

```bash
git add server/admin_giveaways.py
git commit -m "feat(admin): per-place prizes in giveaway create/update/list, derive winners_count"
```

---

### Task 5: Админ-роуты — GiveawayPrizeBody + проброс prizes

**Files:**
- Modify: `server/admin_routes.py`

**Interfaces:**
- Consumes: `create_giveaway`/`update_giveaway` с параметром `prizes` (Task 4).
- Produces: `GiveawayCreateBody`/`GiveawayUpdateBody` принимают `prizes: list[GiveawayPrizeBody]`.

- [ ] **Step 1: Добавить `GiveawayPrizeBody` и поле `prizes` в оба body**

В `server/admin_routes.py` найти:

```python
class GiveawayConditionBody(BaseModel):
    kind: str = Field(min_length=3, max_length=16)
    targetValue: int = Field(default=1, ge=1)
    itemId: str | None = Field(default=None, max_length=128)
    model_config = {"extra": "forbid"}
```

Заменить на (добавляет `GiveawayPrizeBody` рядом):

```python
class GiveawayConditionBody(BaseModel):
    kind: str = Field(min_length=3, max_length=16)
    targetValue: int = Field(default=1, ge=1)
    itemId: str | None = Field(default=None, max_length=128)
    model_config = {"extra": "forbid"}


class GiveawayPrizeBody(BaseModel):
    prizeType: str = Field(min_length=3, max_length=16)
    prizeKutAmount: int | None = Field(default=None, ge=1)
    prizeTitle: str | None = Field(default=None, max_length=120)
    prizeEmoji: str | None = Field(default=None, max_length=16)
    prizeDescription: str | None = Field(default=None, max_length=500)
    model_config = {"extra": "forbid"}
```

Найти в `GiveawayCreateBody`:

```python
    conditions: list[GiveawayConditionBody] = Field(default_factory=list, max_length=10)
    enabled: bool = True
    model_config = {"extra": "forbid"}


class GiveawayUpdateBody(BaseModel):
```

Заменить на:

```python
    conditions: list[GiveawayConditionBody] = Field(default_factory=list, max_length=10)
    prizes: list[GiveawayPrizeBody] = Field(default_factory=list, max_length=20)
    enabled: bool = True
    model_config = {"extra": "forbid"}


class GiveawayUpdateBody(BaseModel):
```

Найти в `GiveawayUpdateBody`:

```python
    conditions: list[GiveawayConditionBody] | None = Field(default=None, max_length=10)
    enabled: bool | None = None
    model_config = {"extra": "forbid"}
```

Заменить на:

```python
    conditions: list[GiveawayConditionBody] | None = Field(default=None, max_length=10)
    prizes: list[GiveawayPrizeBody] | None = Field(default=None, max_length=20)
    enabled: bool | None = None
    model_config = {"extra": "forbid"}
```

- [ ] **Step 2: Пробросить `prizes` в create-роут**

Найти:

```python
            draw_type=body.drawType,
            ends_at=_parse_dt(body.endsAt),
            starts_at=_parse_dt(body.startsAt),
            conditions=[c.model_dump() for c in body.conditions],
            enabled=body.enabled,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "giveaway_create",
```

Заменить на:

```python
            draw_type=body.drawType,
            ends_at=_parse_dt(body.endsAt),
            starts_at=_parse_dt(body.startsAt),
            conditions=[c.model_dump() for c in body.conditions],
            prizes=[p.model_dump() for p in body.prizes],
            enabled=body.enabled,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "giveaway_create",
```

- [ ] **Step 3: Пробросить `prizes` в patch-роут**

Найти:

```python
            conditions=[c.model_dump() for c in body.conditions] if body.conditions is not None else None,
            enabled=body.enabled,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "giveaway_update",
```

Заменить на:

```python
            conditions=[c.model_dump() for c in body.conditions] if body.conditions is not None else None,
            prizes=[p.model_dump() for p in body.prizes] if body.prizes is not None else None,
            enabled=body.enabled,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "giveaway_update",
```

- [ ] **Step 4: Verify компилируется**

Run: `cd server && python -m py_compile admin_routes.py`
Expected: no output, exit code 0

- [ ] **Step 5: Запустить полный бэкенд-набор**

Run: `cd server && python -m pytest -v`
Expected: 31 passed

- [ ] **Step 6: Commit**

```bash
git add server/admin_routes.py
git commit -m "feat(admin): accept prizes[] in giveaway create/update request bodies"
```

---

### Task 6: Админ-панель — редактор призовых мест

**Files:**
- Modify: `admin/src/pages/sections/GiveawaysSection.jsx`

**Interfaces:**
- Consumes: `POST/PATCH` с полем `prizes` (Task 5); ответ содержит `prizes`, `winnersCount`.
- Produces: изменения только в этом файле.

- [ ] **Step 1: Хелперы пустого приза + начальное состояние формы**

В `admin/src/pages/sections/GiveawaysSection.jsx` найти:

```jsx
function emptyForm() {
  return {
    title: '',
    description: '',
    emoji: '🎁',
    rarity: 'common',
    prizeType: 'kut',
    prizeKutAmount: 100,
    prizeTitle: '',
    prizeEmoji: '🎁',
    prizeDescription: '',
    drawType: 'instant',
    startsAt: '',
    endsAt: '',
    enabled: true,
    conditions: [],
  }
}
```

Заменить на:

```jsx
function emptyPrize() {
  return { prizeType: 'kut', prizeKutAmount: 100, prizeTitle: '', prizeEmoji: '🎁', prizeDescription: '' }
}

function emptyForm() {
  return {
    title: '',
    description: '',
    emoji: '🎁',
    rarity: 'common',
    prizeType: 'kut',
    prizeKutAmount: 100,
    prizeTitle: '',
    prizeEmoji: '🎁',
    prizeDescription: '',
    drawType: 'instant',
    startsAt: '',
    endsAt: '',
    enabled: true,
    conditions: [],
    prizes: [emptyPrize()],
  }
}
```

- [ ] **Step 2: `openEdit` — загрузить места из ответа (или из одиночного приза)**

Найти в `openEdit`:

```jsx
    drawType: item.drawType,
    startsAt: item.startsAt ? item.startsAt.slice(0, 16) : '',
    endsAt: item.endsAt ? item.endsAt.slice(0, 16) : '',
    enabled: item.enabled,
    conditions: item.conditions.map((c) => ({
      kind: c.kind, targetValue: c.targetValue, itemId: c.itemId ?? '',
    })),
  })
```

Заменить на:

```jsx
    drawType: item.drawType,
    startsAt: item.startsAt ? item.startsAt.slice(0, 16) : '',
    endsAt: item.endsAt ? item.endsAt.slice(0, 16) : '',
    enabled: item.enabled,
    conditions: item.conditions.map((c) => ({
      kind: c.kind, targetValue: c.targetValue, itemId: c.itemId ?? '',
    })),
    prizes: (item.prizes && item.prizes.length > 0)
      ? item.prizes.map((p) => ({
          prizeType: p.prizeType,
          prizeKutAmount: p.prizeKutAmount ?? 100,
          prizeTitle: p.prizeTitle ?? '',
          prizeEmoji: p.prizeEmoji ?? '🎁',
          prizeDescription: p.prizeDescription ?? '',
        }))
      : [{
          prizeType: item.prizeType,
          prizeKutAmount: item.prizeKutAmount ?? 100,
          prizeTitle: item.prizeTitle ?? '',
          prizeEmoji: item.prizeEmoji ?? '🎁',
          prizeDescription: item.prizeDescription ?? '',
        }],
  })
```

- [ ] **Step 3: Добавить обработчики мест рядом с обработчиками условий**

Найти:

```jsx
  const removeCondition = (idx) => setForm((f) => ({
    ...f,
    conditions: f.conditions.filter((_, i) => i !== idx),
  }))
```

Добавить сразу ПОСЛЕ:

```jsx
  const addPrize = () => setForm((f) => ({ ...f, prizes: [...f.prizes, emptyPrize()] }))

  const updatePrize = (idx, patch) => setForm((f) => ({
    ...f,
    prizes: f.prizes.map((p, i) => (i === idx ? { ...p, ...patch } : p)),
  }))

  const removePrize = (idx) => setForm((f) => ({
    ...f,
    prizes: f.prizes.length > 1 ? f.prizes.filter((_, i) => i !== idx) : f.prizes,
  }))
```

- [ ] **Step 4: `save()` — слать `prizes` для timer**

Найти в `save()`:

```jsx
        drawType: form.drawType,
        startsAt: form.startsAt ? new Date(form.startsAt).toISOString() : null,
        endsAt: form.drawType === 'timer' && form.endsAt ? new Date(form.endsAt).toISOString() : null,
        enabled: form.enabled,
        conditions: form.conditions.map((c) => ({
          kind: c.kind,
          targetValue: c.kind === 'channel_sub' ? 1 : Number(c.targetValue),
          itemId: c.kind === 'item_count' || c.kind === 'channel_sub' ? c.itemId : null,
        })),
      }
```

Заменить на:

```jsx
        drawType: form.drawType,
        startsAt: form.startsAt ? new Date(form.startsAt).toISOString() : null,
        endsAt: form.drawType === 'timer' && form.endsAt ? new Date(form.endsAt).toISOString() : null,
        enabled: form.enabled,
        conditions: form.conditions.map((c) => ({
          kind: c.kind,
          targetValue: c.kind === 'channel_sub' ? 1 : Number(c.targetValue),
          itemId: c.kind === 'item_count' || c.kind === 'channel_sub' ? c.itemId : null,
        })),
        prizes: form.drawType === 'timer'
          ? form.prizes.map((p) => ({
              prizeType: p.prizeType,
              prizeKutAmount: p.prizeType === 'kut' ? Number(p.prizeKutAmount) : null,
              prizeTitle: p.prizeType === 'manual' ? p.prizeTitle : null,
              prizeEmoji: p.prizeType === 'manual' ? p.prizeEmoji : null,
              prizeDescription: p.prizeType === 'manual' ? p.prizeDescription : null,
            }))
          : [],
      }
```

- [ ] **Step 5: Форма — призовые места для timer, единый приз для instant**

Найти существующий блок приза (единый редактор) — от `<label className="admin-modal-field"><span>Тип приза</span>` до закрытия manual-ветки:

```jsx
            <label className="admin-modal-field">
              <span>Тип приза</span>
              <AdminSelect value={form.prizeType} onChange={(v) => setForm({ ...form, prizeType: v })} options={PRIZE_TYPE_OPTIONS} />
            </label>
            {form.prizeType === 'kut' ? (
              <label className="admin-modal-field">
                <span>Сумма КУТ</span>
                <input className="panel-users-input" type="number" min={1} value={form.prizeKutAmount} onChange={(e) => setForm({ ...form, prizeKutAmount: e.target.value })} />
              </label>
            ) : (
              <>
                <label className="admin-modal-field">
                  <span>Название приза</span>
                  <input className="panel-users-input" value={form.prizeTitle} onChange={(e) => setForm({ ...form, prizeTitle: e.target.value })} />
                </label>
                <label className="admin-modal-field">
                  <span>Эмодзи приза</span>
                  <input className="panel-users-input" value={form.prizeEmoji} onChange={(e) => setForm({ ...form, prizeEmoji: e.target.value })} maxLength={8} />
                </label>
                <label className="admin-modal-field">
                  <span>Описание приза (для игрока)</span>
                  <textarea className="admin-modal-textarea" value={form.prizeDescription} onChange={(e) => setForm({ ...form, prizeDescription: e.target.value })} />
                </label>
              </>
            )}
```

Заменить на (instant → как раньше; timer → список мест):

```jsx
            {form.drawType !== 'timer' ? (
              <>
                <label className="admin-modal-field">
                  <span>Тип приза</span>
                  <AdminSelect value={form.prizeType} onChange={(v) => setForm({ ...form, prizeType: v })} options={PRIZE_TYPE_OPTIONS} />
                </label>
                {form.prizeType === 'kut' ? (
                  <label className="admin-modal-field">
                    <span>Сумма КУТ</span>
                    <input className="panel-users-input" type="number" min={1} value={form.prizeKutAmount} onChange={(e) => setForm({ ...form, prizeKutAmount: e.target.value })} />
                  </label>
                ) : (
                  <>
                    <label className="admin-modal-field">
                      <span>Название приза</span>
                      <input className="panel-users-input" value={form.prizeTitle} onChange={(e) => setForm({ ...form, prizeTitle: e.target.value })} />
                    </label>
                    <label className="admin-modal-field">
                      <span>Эмодзи приза</span>
                      <input className="panel-users-input" value={form.prizeEmoji} onChange={(e) => setForm({ ...form, prizeEmoji: e.target.value })} maxLength={8} />
                    </label>
                    <label className="admin-modal-field">
                      <span>Описание приза (для игрока)</span>
                      <textarea className="admin-modal-textarea" value={form.prizeDescription} onChange={(e) => setForm({ ...form, prizeDescription: e.target.value })} />
                    </label>
                  </>
                )}
              </>
            ) : (
              <div className="admin-modal-field">
                <span>Призовые места (место 1 — топ; число мест = число победителей)</span>
                {form.prizes.map((prize, idx) => (
                  <div key={idx} style={{ border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8, padding: 8, marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <strong>{idx + 1} место</strong>
                      {form.prizes.length > 1 && (
                        <button type="button" className="panel-users-btn panel-users-btn-danger" onClick={() => removePrize(idx)}>✕</button>
                      )}
                    </div>
                    <AdminSelect value={prize.prizeType} onChange={(v) => updatePrize(idx, { prizeType: v })} options={PRIZE_TYPE_OPTIONS} />
                    {prize.prizeType === 'kut' ? (
                      <input className="panel-users-input" type="number" min={1} placeholder="Сумма КУТ" style={{ marginTop: 6 }}
                        value={prize.prizeKutAmount} onChange={(e) => updatePrize(idx, { prizeKutAmount: e.target.value })} />
                    ) : (
                      <>
                        <input className="panel-users-input" placeholder="Название приза" style={{ marginTop: 6 }}
                          value={prize.prizeTitle} onChange={(e) => updatePrize(idx, { prizeTitle: e.target.value })} />
                        <input className="panel-users-input" placeholder="Эмодзи приза" maxLength={8} style={{ marginTop: 6 }}
                          value={prize.prizeEmoji} onChange={(e) => updatePrize(idx, { prizeEmoji: e.target.value })} />
                        <textarea className="admin-modal-textarea" placeholder="Описание приза (для игрока)" style={{ marginTop: 6 }}
                          value={prize.prizeDescription} onChange={(e) => updatePrize(idx, { prizeDescription: e.target.value })} />
                      </>
                    )}
                  </div>
                ))}
                <button type="button" className="panel-users-btn" onClick={addPrize}>+ Добавить место</button>
              </div>
            )}
```

- [ ] **Step 6: Таблица — колонка «Мест»**

Найти шапку таблицы:

```jsx
              <th>Старт</th>
              <th>Статус</th>
              <th>Включён</th>
```

Заменить на:

```jsx
              <th>Старт</th>
              <th>Мест</th>
              <th>Статус</th>
              <th>Включён</th>
```

Найти строку данных:

```jsx
                <td>{item.startsAt ? new Date(item.startsAt).toLocaleString('ru-RU') : 'сразу'}</td>
                <td>{item.status}</td>
```

Заменить на:

```jsx
                <td>{item.startsAt ? new Date(item.startsAt).toLocaleString('ru-RU') : 'сразу'}</td>
                <td>{item.drawType === 'timer' ? item.winnersCount : '—'}</td>
                <td>{item.status}</td>
```

- [ ] **Step 7: Verify сборка**

Run: `cd admin && npx vite build`
Expected: build succeeds, no errors

- [ ] **Step 8: Commit**

```bash
git add admin/src/pages/sections/GiveawaysSection.jsx
git commit -m "feat(admin): prize-places editor for timer giveaways + Мест table column"
```

---

### Task 7: Вебапп — список призёров и призовая сетка

**Files:**
- Modify: `src/components/GiveawayDetailModal.jsx`
- Modify: `src/components/GiveawayHistoryCard.jsx`
- Modify: `src/components/GiveawayTicketCard.jsx`
- Modify: `src/styles/giveaways.css`

**Interfaces:**
- Consumes: `winners`, `prizesByPlace`, `result.place`, `winnersCount` из бэкенда (Task 3).
- Produces: изменения только в этих файлах.

- [ ] **Step 1: `GiveawayDetailModal` — список призёров / призовая сетка**

В `src/components/GiveawayDetailModal.jsx` найти зону 3 (действие), блок `detail.result`:

```jsx
              {detail.result ? (
                <div className="giveaway-detail-result">
                  {detail.result.won
                    ? '🎉 Вы выиграли!'
                    : detail.winnerName
                      ? `🏆 Победитель: ${detail.winnerName}`
                      : detail.recipientsCount != null
                        ? `🎁 ${detail.recipientsCount} игроков получили приз`
                        : 'В этот раз не повезло'}
                </div>
              ) : detail.joined ? (
```

Заменить на:

```jsx
              {detail.result ? (
                detail.winners && detail.winners.length > 0 ? (
                  <div className="giveaway-detail-winners">
                    {detail.result.won && (
                      <div className="giveaway-detail-result">🎉 Вы заняли {detail.result.place} место!</div>
                    )}
                    {detail.winners.map((w) => (
                      <div
                        key={w.place}
                        className={`giveaway-detail-winner-row${detail.result.place === w.place ? ' giveaway-detail-winner-row--me' : ''}`}
                      >
                        <span className="giveaway-detail-winner-place">{w.place} место</span>
                        <span className="giveaway-detail-winner-name">{w.displayName}</span>
                        <span className="giveaway-detail-winner-prize">{formatGiveawayPrize(w.prize)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="giveaway-detail-result">
                    {detail.result.won
                      ? '🎉 Вы выиграли!'
                      : detail.winnerName
                        ? `🏆 Победитель: ${detail.winnerName}`
                        : detail.recipientsCount != null
                          ? `🎁 ${detail.recipientsCount} игроков получили приз`
                          : 'В этот раз не повезло'}
                  </div>
                )
              ) : detail.joined ? (
```

- [ ] **Step 2: `GiveawayDetailModal` — призовая сетка мест до розыгрыша**

Найти конец зоны 1 (приз + таймер) — закрывающий `</div>` блока `giveaway-detail-hero`, сразу перед зоной 2 (условия):

```jsx
                <span className="giveaway-detail-badge">
                  {detail.drawType === 'instant'
                    ? <>⚡ Мгновенно всем выполнившим</>
                    : detail.endsAt
                      ? <>🕒 {formatGiveawayDeadlineTime(detail.endsAt)}</>
                      : <>🕒 По таймеру</>}
                </span>
              </div>
```

Заменить на:

```jsx
                <span className="giveaway-detail-badge">
                  {detail.drawType === 'instant'
                    ? <>⚡ Мгновенно всем выполнившим</>
                    : detail.endsAt
                      ? <>🕒 {formatGiveawayDeadlineTime(detail.endsAt)}</>
                      : <>🕒 По таймеру</>}
                </span>
                {!detail.result && detail.prizesByPlace && detail.prizesByPlace.length > 1 && (
                  <div className="giveaway-detail-prizes-grid">
                    {detail.prizesByPlace.map((p) => (
                      <div key={p.place} className="giveaway-detail-prize-place">
                        <span className="giveaway-detail-prize-place-num">{p.place} место</span>
                        <span className="giveaway-detail-prize-place-prize">{formatGiveawayPrize(p.prize)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
```

- [ ] **Step 3: `GiveawayHistoryCard` — «N победителей»**

В `src/components/GiveawayHistoryCard.jsx` найти:

```jsx
        <span className="giveaway-history-result">
          {giveaway.winnerName
            ? `🏆 Победитель: ${giveaway.winnerName}`
            : `🎁 ${giveaway.recipientsCount ?? 0} игроков получили приз`}
        </span>
```

Заменить на:

```jsx
        <span className="giveaway-history-result">
          {giveaway.winnersCount > 1
            ? `🏆 ${giveaway.winnerName ?? 'Победитель'} +${giveaway.winnersCount - 1} мест`
            : giveaway.winnerName
              ? `🏆 Победитель: ${giveaway.winnerName}`
              : `🎁 ${giveaway.recipientsCount ?? 0} игроков получили приз`}
        </span>
```

- [ ] **Step 4: `GiveawayTicketCard` — «N призовых мест»**

В `src/components/GiveawayTicketCard.jsx` найти чипы футера:

```jsx
      <div className="giveaway-ticket-footer">
        {startLabel && <span className="giveaway-ticket-chip">🚀 Старт {startLabel}</span>}
        {deadline && <span className="giveaway-ticket-chip">⏳ До {deadline}</span>}
        <span className="giveaway-ticket-chip giveaway-ticket-chip--prize">{prizeLabel}</span>
      </div>
```

Заменить на:

```jsx
      <div className="giveaway-ticket-footer">
        {startLabel && <span className="giveaway-ticket-chip">🚀 Старт {startLabel}</span>}
        {deadline && <span className="giveaway-ticket-chip">⏳ До {deadline}</span>}
        {giveaway.winnersCount > 1 && <span className="giveaway-ticket-chip">🏆 {giveaway.winnersCount} мест</span>}
        <span className="giveaway-ticket-chip giveaway-ticket-chip--prize">{prizeLabel}</span>
      </div>
```

- [ ] **Step 5: CSS для новых блоков**

В `src/styles/giveaways.css` в конец файла добавить:

```css
.giveaway-detail-winners {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.giveaway-detail-winner-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.7rem;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.giveaway-detail-winner-row--me {
  border-color: rgba(253, 230, 138, 0.6);
  background: rgba(253, 230, 138, 0.12);
}

.giveaway-detail-winner-place {
  flex-shrink: 0;
  font-size: 0.72rem;
  font-weight: 800;
  color: var(--ticket-accent-strong);
}

.giveaway-detail-winner-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.8rem;
}

.giveaway-detail-winner-prize {
  flex-shrink: 0;
  font-size: 0.78rem;
  font-weight: 700;
}

.giveaway-detail-prizes-grid {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-top: 0.6rem;
  width: 100%;
}

.giveaway-detail-prize-place {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.35rem 0.6rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  font-size: 0.76rem;
}

.giveaway-detail-prize-place-num {
  font-weight: 800;
  color: var(--ticket-accent-strong);
}
```

- [ ] **Step 6: Verify сборка**

Run: `npx vite build`
Expected: build succeeds, no errors

- [ ] **Step 7: Commit**

```bash
git add src/components/GiveawayDetailModal.jsx src/components/GiveawayHistoryCard.jsx src/components/GiveawayTicketCard.jsx src/styles/giveaways.css
git commit -m "feat(giveaways): show ranked winners list + per-place prize grid in webapp"
```

---

### Task 8: Финальная верификация

**Files:** нет изменений — только проверка.

- [ ] **Step 1: Полный бэкенд-набор**

Run: `cd server && python -m pytest -v`
Expected: 31 passed

- [ ] **Step 2: Сборки webapp + admin**

Run: `npx vite build && cd admin && npx vite build`
Expected: обе успешны

- [ ] **Step 3: Frontend unit-тесты (существующие)**

Run: `npx vitest run`
Expected: все существующие проходят (новая логика презентационная, отдельных vitest-тестов не добавляем — как и в прошлых фичах)

- [ ] **Step 4: Сквозной ручной review-чеклист (нет живой БД)**

Читая финальный дифф всех задач:
- Админ создаёт timer-розыгрыш с 3 местами → `create_giveaway` пишет 3 строки `giveaway_prizes`, `winners_count=3`, `giveaways.prize_*` = приз места 1.
- Instant-розыгрыш не имеет строк `giveaway_prizes`, `winners_count=1`, единый приз в top-level — форма и валидация как раньше.
- Таймер срабатывает → `draw_timer_giveaways` берёт до 3 случайных участников, раздаёт места 1..k, начисляет КУТ по призу каждого места, `winner_user_id` = место 1, шлёт DM с местом и призом.
- Меньше участников, чем мест (2 из 3) → места 1,2 заполнены, место 3 без победителя, ошибки нет.
- Ноль участников → `status='cancelled'` (как раньше).
- Игрок открывает завершённый мульти-розыгрыш → видит ранжированный список призёров с призами; если сам призёр — своя строка подсвечена, показан «Вы заняли N место».
- Незавершённый мульти-розыгрыш → призовая сетка мест в модалке; на карточке билета «N мест»; в истории «победитель +N мест».
- Лента «Счастливчики дня» → каждый призёр-место отдельной записью со своим призом.
- Старые (до фичи) таймер-розыгрыши: backfill создал им приз места 1 и (для завершённых) победителя места 1 — история/лента/детали работают без потерь.

- [ ] **Step 5: Итоговый commit (если Step 4 выявил правки)**

Если ручной review чист — коммитить нечего. Иначе — исправить и закоммитить с описанием конкретного исправления.
