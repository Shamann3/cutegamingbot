# Розыгрыши (Giveaways) v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Построить полноценную фичу «Розыгрыши» — от БД и бэкенд-логики до админ-панели и фронтенда вебаппа — по спеке [2026-07-20-giveaways-design.md](../specs/2026-07-20-giveaways-design.md).

**Architecture:** FastAPI-сервер (`server/`) хранит розыгрыши/условия/билеты в Postgres, проверяет условия через расширяемый реестр чистых функций, резолвит «мгновенные» розыгрыши синхронно и «по таймеру» — через уже существующий фоновый тик планировщика. Админка (`admin/`) получает новую секцию для CRUD. Вебапп (`src/`) получает клиент+хук с тем же паттерном авто-обновления, что у Заданий, и новые компоненты билета/модалки.

**Tech Stack:** Python/FastAPI/asyncpg (Postgres), React (админка и вебапп), pytest (новый для `server/` — уже был предусмотрен нереализованным планом `2026-07-04-cosmetic-lootbox-backend.md`, но зависимость ещё не добавлена).

## Global Constraints

- Условия участия в v1 — только внутриигровые: `balance`, `harvest_count`, `item_count`. Остальные типы (подписка на канал, счётчик заданий, рефералы) — вне объёма, архитектура реестра должна их принимать без переделки.
- Логика условий одного розыгрыша — строгое И (все обязательны).
- Один билет на человека на розыгрыш — `PRIMARY KEY (giveaway_id, user_id)` в `giveaway_entries`, повторный `participate` идемпотентен (не ошибка).
- Приз `kut` — автоначисление. Приз `manual` (NFT/подарок/Stars) — только отображение (title/emoji/description), автовыплаты нет, выдаёт администрация вручную.
- Победитель по таймеру выбирается `ORDER BY random() LIMIT 1` **в SQL**, не в Python-памяти.
- Никакого нового asyncio-таска/процесса для роздачи по таймеру — используем существующий тик `event_scheduler.py`.
- Никакой кнопки «Проверить» — статус условий обновляется тем же паттерном авто-поллинга, что `useQuests.js` (`ACTIVE_SYNC_MS` + `visibilitychange`).
- Свайп-участие на карточке включён только когда условий нет или все уже выполнены; иначе тап открывает модалку. Карточка помечается `data-no-swipe`, чтобы не конфликтовать с уже существующим `useSwipeTabs.js`.
- Эмодзи — обычная текстовая строка (в проекте нигде нет загрузки картинок для наград/иконок) — не изобретаем upload-пайплайн.
- Не физическое удаление розыгрыша из БД при отмене — только `status='cancelled'`.

---

## File Structure

**Создать:**
- `server/giveaway_conditions.py` — чистый реестр проверки условий, без БД.
- `server/tests/__init__.py`, `server/tests/test_giveaway_conditions.py` — pytest для реестра условий.
- `server/admin_giveaways.py` — admin CRUD (валидация + SQL, как `admin_quests.py`).
- `admin/src/pages/sections/GiveawaysSection.jsx` — новая секция админки.
- `src/lib/giveawaysClient.js` — тонкий API-клиент.
- `src/hooks/useGiveaways.js` — хук с авто-поллингом.
- `src/constants/giveaways.js` — редкость (label/accent).
- `src/components/GiveawayTicketCard.jsx` — билет со свайпом.
- `src/components/GiveawayDetailModal.jsx` — модалка на 3 зоны.

**Модифицировать:**
- `server/schema.sql` — 3 новые таблицы.
- `server/db.py` — методы `Database`: `get_giveaways_state`, `get_giveaway_detail`, `participate_in_giveaway`, `draw_timer_giveaways`.
- `server/app.py` — 3 роута + Pydantic-модель тела запроса.
- `server/event_scheduler.py` — вызов `db.draw_timer_giveaways()` из `_tick()`.
- `server/admin_routes.py` — импорт `admin_giveaways`, 4 роута.
- `server/requirements.txt` — добавить `pytest`.
- `admin/src/constants/panelNav.js` — новая секция в `PANEL_SECTIONS`.
- `admin/src/pages/PanelShell.jsx` — регистрация секции (импорт, `isGiveaways`, рендер, fallback-условие).
- `admin/src/lib/adminClient.js` — `fetchGiveawaysAdmin`, `createGiveawayAdmin`, `patchGiveawayAdmin`, `deleteGiveawayAdmin`.
- `src/components/GiveawaysModule.jsx` — заглушка заменяется реальным списком билетов.
- `src/App.jsx` — состояние `farmSegment`/`setFarmSegment` поднимается из `FarmModule` в `AppShell` (по образцу `tradeSegment`).
- `src/components/FarmModule.jsx` — принимает `farmSegment`/`onFarmSegmentChange` пропами вместо локального `useState`.
- `src/styles/giveaways.css` — стили билетов, модалки, пульсации.

---

## Task 1: Реестр условий участия (чистая логика, TDD)

**Files:**
- Create: `server/giveaway_conditions.py`
- Create: `server/tests/__init__.py` (пустой)
- Create: `server/tests/test_giveaway_conditions.py`
- Modify: `server/requirements.txt`

**Interfaces:**
- Produces: `all_conditions_met(ctx: dict, conditions: list[dict]) -> bool` и `condition_satisfied(ctx: dict, cond: dict) -> bool`, где `ctx = {"balance": int, "harvest_count": int, "items": dict}`, `cond = {"kind": str, "target_value": int, "item_id": str | None}`. Используется в Task 2 (`server/db.py`) для проверки условий на реальных данных пользователя.

- [ ] **Step 1: Добавить pytest в зависимости сервера**

В `server/requirements.txt` добавить строку (в конец файла):

```
pytest==8.3.4
```

- [ ] **Step 2: Написать падающий тест**

Создать `server/tests/__init__.py` (пустой файл).

Создать `server/tests/test_giveaway_conditions.py`:

```python
"""Розыгрыши: чистые функции проверки условий участия, без БД."""
from giveaway_conditions import all_conditions_met, condition_satisfied


def test_balance_condition():
    cond = {"kind": "balance", "target_value": 500}
    ctx_ok = {"balance": 500, "harvest_count": 0, "items": {}}
    ctx_low = {"balance": 499, "harvest_count": 0, "items": {}}
    assert condition_satisfied(ctx_ok, cond) is True
    assert condition_satisfied(ctx_low, cond) is False


def test_harvest_count_condition():
    cond = {"kind": "harvest_count", "target_value": 10}
    assert condition_satisfied({"balance": 0, "harvest_count": 10, "items": {}}, cond) is True
    assert condition_satisfied({"balance": 0, "harvest_count": 9, "items": {}}, cond) is False


def test_item_count_condition():
    cond = {"kind": "item_count", "target_value": 3, "item_id": "Ключ"}
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {"Ключ": 3}}, cond) is True
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {"Ключ": 2}}, cond) is False
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {}}, cond) is False


def test_unknown_kind_is_not_satisfied():
    # Условия из будущих фаз (channel_sub, quest_count, referral_count) не должны
    # падать с исключением — просто "не выполнено" до того, как появится чекер.
    cond = {"kind": "channel_sub", "target_value": 1}
    ctx = {"balance": 999999, "harvest_count": 999999, "items": {}}
    assert condition_satisfied(ctx, cond) is False


def test_all_conditions_met_is_and_logic():
    ctx = {"balance": 500, "harvest_count": 10, "items": {"Ключ": 3}}
    conditions = [
        {"kind": "balance", "target_value": 500},
        {"kind": "harvest_count", "target_value": 10},
        {"kind": "item_count", "target_value": 3, "item_id": "Ключ"},
    ]
    assert all_conditions_met(ctx, conditions) is True

    conditions_with_one_unmet = conditions + [{"kind": "balance", "target_value": 501}]
    assert all_conditions_met(ctx, conditions_with_one_unmet) is False


def test_no_conditions_means_available_to_everyone():
    ctx = {"balance": 0, "harvest_count": 0, "items": {}}
    assert all_conditions_met(ctx, []) is True
```

- [ ] **Step 3: Убедиться, что тест падает**

Run: `cd server && python -m pytest tests/test_giveaway_conditions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'giveaway_conditions'`

- [ ] **Step 4: Реализовать реестр условий**

Создать `server/giveaway_conditions.py`:

```python
"""Розыгрыши: реестр проверяемых условий участия.

Каждое условие — запись в CONDITION_CHECKERS. Новые типы условий
(channel_sub, quest_count, referral_count — следующие фазы) добавляются
сюда новой записью, не трогая участие/список/детали розыгрыша.
"""
from __future__ import annotations

from typing import Callable

VALID_CONDITION_KINDS = frozenset({"balance", "harvest_count", "item_count"})


def check_balance(ctx: dict, cond: dict) -> bool:
    return int(ctx.get("balance") or 0) >= int(cond["target_value"])


def check_harvest_count(ctx: dict, cond: dict) -> bool:
    return int(ctx.get("harvest_count") or 0) >= int(cond["target_value"])


def check_item_count(ctx: dict, cond: dict) -> bool:
    items = ctx.get("items") or {}
    return int(items.get(cond["item_id"], 0)) >= int(cond["target_value"])


CONDITION_CHECKERS: dict[str, Callable[[dict, dict], bool]] = {
    "balance": check_balance,
    "harvest_count": check_harvest_count,
    "item_count": check_item_count,
}


def condition_satisfied(ctx: dict, cond: dict) -> bool:
    checker = CONDITION_CHECKERS.get(cond.get("kind"))
    if checker is None:
        return False
    return checker(ctx, cond)


def all_conditions_met(ctx: dict, conditions: list[dict]) -> bool:
    return all(condition_satisfied(ctx, cond) for cond in conditions)
```

- [ ] **Step 5: Убедиться, что тест проходит**

Run: `cd server && python -m pytest tests/test_giveaway_conditions.py -v`
Expected: PASS (6/6 тестов)

- [ ] **Step 6: Commit**

```bash
git add server/requirements.txt server/giveaway_conditions.py server/tests/__init__.py server/tests/test_giveaway_conditions.py
git commit -m "feat(giveaways): add extensible participation-condition registry"
```

---

## Task 2: Схема БД, бэкенд-логика, роуты, планировщик

**Files:**
- Modify: `server/schema.sql`
- Modify: `server/db.py`
- Modify: `server/app.py`
- Modify: `server/event_scheduler.py`

**Interfaces:**
- Consumes: `all_conditions_met`, `condition_satisfied` из `server/giveaway_conditions.py` (Task 1).
- Consumes существующее: `self.pool` (asyncpg pool на `Database`), `self.ensure_user(user_id)`, `parse_items()`/`items_to_db()` (`user_items.py`), `schedule_balance_event(pool, kind, user_id, *, amount, balance_before, balance_after, details)` (`audit_log.py`), `log_game_event(pool, event, user_id, payload)` (`game_events_log.py`), `schedule_player_telegram_dm(user_id, text)` и `create_admin_message_notification(pool, user_id, *, title, body="", detail="")` (`user_notify.py`).
- Produces: `Database.get_giveaways_state(user_id) -> dict`, `Database.get_giveaway_detail(user_id, giveaway_id) -> dict`, `Database.participate_in_giveaway(user_id, giveaway_id) -> dict`, `Database.draw_timer_giveaways() -> None`. Роуты `GET /api/giveaways`, `GET /api/giveaways/{id}`, `POST /api/giveaways/{id}/participate`. Используется в Task 5 (`giveawaysClient.js`).

- [ ] **Step 1: Добавить таблицы в схему**

В `server/schema.sql` в конец файла добавить:

```sql
CREATE TABLE IF NOT EXISTS giveaways (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    emoji TEXT NOT NULL DEFAULT '🎁',
    rarity TEXT NOT NULL CHECK (rarity IN ('common', 'rare', 'legendary')),
    prize_type TEXT NOT NULL CHECK (prize_type IN ('kut', 'manual')),
    prize_kut_amount INT,
    prize_title TEXT,
    prize_emoji TEXT,
    prize_description TEXT,
    draw_type TEXT NOT NULL CHECK (draw_type IN ('timer', 'instant')),
    ends_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    winner_user_id BIGINT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drawn_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS giveaway_conditions (
    id SERIAL PRIMARY KEY,
    giveaway_id INT NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('balance', 'harvest_count', 'item_count')),
    target_value INT NOT NULL CHECK (target_value >= 1),
    item_id TEXT,
    sort_order INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS giveaway_entries (
    giveaway_id INT NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (giveaway_id, user_id)
);
```

- [ ] **Step 2: Добавить методы в `Database` (server/db.py)**

В `server/db.py`, после блока импортов (после строки с `from user_items import (...)`, т.е. после строки 81), добавить:

```python
from giveaway_conditions import all_conditions_met
```

В конец класса `Database` (после метода `claim_quest_reward`, т.е. после строки 1769, перед `async def get_craft_recipes`) добавить:

```python
    async def _giveaway_condition_ctx(self, conn, user_id):
        row = await conn.fetchrow(
            "SELECT balance, harvest_count, items FROM users WHERE user_id = $1",
            user_id,
        )
        if not row:
            return {"balance": 0, "harvest_count": 0, "items": {}}
        return {
            "balance": int(row["balance"] or 0),
            "harvest_count": int(row["harvest_count"] or 0),
            "items": parse_items(row["items"]),
        }

    async def _giveaway_conditions(self, conn, giveaway_id):
        rows = await conn.fetch(
            """
            SELECT kind, target_value, item_id
            FROM giveaway_conditions
            WHERE giveaway_id = $1
            ORDER BY sort_order
            """,
            giveaway_id,
        )
        return [
            {"kind": r["kind"], "target_value": int(r["target_value"]), "item_id": r["item_id"]}
            for r in rows
        ]

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

    async def get_giveaways_state(self, user_id):
        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            ctx = await self._giveaway_condition_ctx(conn, user_id)
            rows = await conn.fetch(
                """
                SELECT g.*, (e.user_id IS NOT NULL) AS joined
                FROM giveaways g
                LEFT JOIN giveaway_entries e ON e.giveaway_id = g.id AND e.user_id = $1
                WHERE g.enabled = TRUE AND g.status != 'cancelled'
                ORDER BY g.sort_order, g.id
                """,
                user_id,
            )
            items = []
            for row in rows:
                conditions = await self._giveaway_conditions(conn, row["id"])
                conditions_met = all_conditions_met(ctx, conditions)
                items.append({
                    "id": row["id"],
                    "title": row["title"],
                    "emoji": row["emoji"],
                    "rarity": row["rarity"],
                    "prize": self._giveaway_prize_summary(row),
                    "drawType": row["draw_type"],
                    "endsAt": row["ends_at"].isoformat() if row["ends_at"] else None,
                    "status": row["status"],
                    "conditionsCount": len(conditions),
                    "conditionsMet": conditions_met,
                    "joined": bool(row["joined"]),
                    "won": bool(row["winner_user_id"] == user_id) if row["winner_user_id"] else None,
                })
        return {"giveaways": items}

    async def get_giveaway_detail(self, user_id, giveaway_id):
        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
            if not row:
                raise ValueError("Розыгрыш не найден")
            ctx = await self._giveaway_condition_ctx(conn, user_id)
            conditions = await self._giveaway_conditions(conn, giveaway_id)
            joined = await conn.fetchval(
                "SELECT 1 FROM giveaway_entries WHERE giveaway_id = $1 AND user_id = $2",
                giveaway_id, user_id,
            )
            condition_progress = []
            for cond in conditions:
                if cond["kind"] == "balance":
                    current = ctx["balance"]
                elif cond["kind"] == "harvest_count":
                    current = ctx["harvest_count"]
                else:
                    current = ctx["items"].get(cond["item_id"], 0)
                condition_progress.append({
                    "kind": cond["kind"],
                    "targetValue": cond["target_value"],
                    "itemId": cond["item_id"],
                    "current": current,
                    "satisfied": current >= cond["target_value"],
                })
            result = None
            if row["status"] == "completed":
                result = {"won": row["winner_user_id"] == user_id}
            elif row["status"] == "cancelled":
                result = {"won": False}
        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "emoji": row["emoji"],
            "rarity": row["rarity"],
            "prize": self._giveaway_prize_summary(row),
            "drawType": row["draw_type"],
            "endsAt": row["ends_at"].isoformat() if row["ends_at"] else None,
            "status": row["status"],
            "conditions": condition_progress,
            "conditionsMet": all(c["satisfied"] for c in condition_progress),
            "joined": bool(joined),
            "result": result,
        }

    async def participate_in_giveaway(self, user_id, giveaway_id):
        # ВАЖНО: не вызывать self.get_giveaway_detail(...) (сам берёт соединение
        # из пула) пока ещё держим conn из self.pool.acquire() ниже — иначе на
        # секунду занимаем два соединения из пула одновременно. Поэтому ранний
        # выход при already_joined не return'ится изнутри "async with conn",
        # а просто ничего не делает внутри транзакции — единый return после
        # блока сам сходит за актуальным состоянием на уже свободном соединении.
        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT * FROM giveaways WHERE id = $1 FOR UPDATE", giveaway_id
                )
                if not row or row["status"] != "active" or not row["enabled"]:
                    raise ValueError("Розыгрыш недоступен")

                already_joined = await conn.fetchval(
                    "SELECT 1 FROM giveaway_entries WHERE giveaway_id = $1 AND user_id = $2",
                    giveaway_id, user_id,
                )
                if not already_joined:
                    ctx = await self._giveaway_condition_ctx(conn, user_id)
                    conditions = await self._giveaway_conditions(conn, giveaway_id)
                    if not all_conditions_met(ctx, conditions):
                        raise ValueError("Не все условия выполнены")

                    await conn.execute(
                        "INSERT INTO giveaway_entries (giveaway_id, user_id) VALUES ($1, $2)",
                        giveaway_id, user_id,
                    )

                    if row["draw_type"] == "instant" and row["prize_type"] == "kut":
                        balance_before = await conn.fetchval(
                            "SELECT balance FROM users WHERE user_id = $1", user_id
                        )
                        balance_before = int(balance_before or 0)
                        amount = int(row["prize_kut_amount"] or 0)
                        balance_after = balance_before + amount
                        await conn.execute(
                            "UPDATE users SET balance = $2 WHERE user_id = $1",
                            user_id, balance_after,
                        )
                        schedule_balance_event(
                            self.pool,
                            "giveaway_reward",
                            user_id,
                            amount=amount,
                            balance_before=balance_before,
                            balance_after=balance_after,
                            details={"giveaway_id": giveaway_id, "title": row["title"]},
                        )
                    log_game_event(
                        self.pool,
                        "giveaway_participate",
                        user_id,
                        {"giveaway_id": giveaway_id, "draw_type": row["draw_type"]},
                    )
        return await self.get_giveaway_detail(user_id, giveaway_id)

    async def draw_timer_giveaways(self):
        # pending_notifications собираются, пока держим conn, и отправляются
        # ПОСЛЕ того, как async with self.pool.acquire() отпустит соединение —
        # create_admin_message_notification само делает await self.pool.acquire()
        # внутри себя, вызывать его с await, ещё держа conn, значит требовать
        # два соединения из пула одновременно на одну и ту же операцию.
        pending_notifications = []
        async with self.pool.acquire() as conn:
            due = await conn.fetch(
                """
                SELECT id FROM giveaways
                WHERE status = 'active' AND draw_type = 'timer'
                  AND ends_at IS NOT NULL AND ends_at <= NOW()
                """
            )
            for row in due:
                giveaway_id = row["id"]
                async with conn.transaction():
                    giveaway = await conn.fetchrow(
                        "SELECT * FROM giveaways WHERE id = $1 FOR UPDATE", giveaway_id
                    )
                    if not giveaway or giveaway["status"] != "active":
                        continue
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

        for winner, title, prize_text in pending_notifications:
            await create_admin_message_notification(
                self.pool,
                winner,
                title="Вы выиграли в розыгрыше!",
                body=f"«{title}» — приз: {prize_text}",
            )

```

Добавить недостающие импорты в верх `server/db.py` (рядом с уже существующими `from user_notify import create_market_sale_notification, schedule_market_sale_telegram` на строке 62 — заменить эту строку на):

```python
from user_notify import (
    create_admin_message_notification,
    create_market_sale_notification,
    schedule_market_sale_telegram,
    schedule_player_telegram_dm,
)
```

- [ ] **Step 3: Добавить роуты в `server/app.py`**

После блока `class CancelQuestBody` (строка 312), добавить:

```python
class ParticipateGiveawayBody(BaseModel):
    model_config = {"extra": "forbid"}
```

После блока роутов квестов (`quests_claim`, заканчивается строкой 778), добавить:

```python
@app.get("/api/giveaways")
async def giveaways_state(request: Request, user_id: int = Depends(rate_limit)):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        return await db.get_giveaways_state(user_id)
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/giveaways/{giveaway_id}")
async def giveaway_detail(giveaway_id: int, request: Request, user_id: int = Depends(rate_limit)):
    try:
        return await db.get_giveaway_detail(user_id, giveaway_id)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/giveaways/{giveaway_id}/participate")
async def giveaway_participate(
    giveaway_id: int,
    body: ParticipateGiveawayBody,
    user_id: int = Depends(rate_limit),
):
    try:
        return await db.participate_in_giveaway(user_id, giveaway_id)
    except ValueError as e:
        raise _client_error(e)
```

- [ ] **Step 4: Подключить розыгрыш по таймеру в планировщик**

В `server/event_scheduler.py`, найти функцию `_tick()` (строка ~71) с телом:

```python
async def _tick() -> None:

    await _fire_scheduled_broadcasts()

    await _fire_daily_rotation_broadcast()
```

Заменить на:

```python
async def _tick() -> None:

    await _fire_scheduled_broadcasts()

    await _fire_daily_rotation_broadcast()

    await _fire_giveaway_draws()
```

Добавить функцию рядом (после `_tick`, перед следующей функцией файла):

```python
async def _fire_giveaway_draws() -> None:
    from db import db

    try:
        await db.draw_timer_giveaways()
    except Exception:
        logger.exception("Giveaway draw tick error")
```

- [ ] **Step 5: Проверить синтаксис**

Run: `cd server && python -m py_compile db.py app.py event_scheduler.py giveaway_conditions.py`
Expected: без вывода (успешная компиляция), код возврата 0.

- [ ] **Step 6: Живая проверка (если доступен локальный Postgres)**

Если можно поднять `docker-compose up -d postgres` и настроить `server/.env` (см. `server/.env.example`, если есть, иначе `DB_HOST=localhost`, `DB_PORT=5432`, значения из `docker-compose.yml`), запустить сервер (`cd server && uvicorn app:app --reload`) и вручную создать тестовый розыгрыш прямо в БД:

```sql
INSERT INTO giveaways (title, emoji, rarity, prize_type, prize_kut_amount, draw_type, status, enabled)
VALUES ('Тестовый розыгрыш', '🎁', 'common', 'kut', 100, 'instant', 'active', true)
RETURNING id;
-- предположим id=1, без условий (conditions пустые — доступен всем)
```

Затем:
```bash
curl -H "X-Dev-User-Id: 1" http://localhost:8000/api/giveaways
curl -X POST -H "X-Dev-User-Id: 1" -H "Content-Type: application/json" -d '{}' http://localhost:8000/api/giveaways/1/participate
curl -H "X-Dev-User-Id: 1" http://localhost:8000/api/giveaways/1
```
Expected: первый запрос — список с одним розыгрышем, `conditionsMet: true`, `joined: false`; второй — участие проходит, баланс пользователя (`users.balance` для user_id=1) увеличился на 100; третий — `joined: true`, `result: null` (т.к. розыгрыш ещё не отмечен `completed` — для `instant`-типа это ожидаемо: приз уже начислен, но статус розыгрыша остаётся `active`, чтобы другие тоже могли поучаствовать).

Если живой Postgres поднять нельзя в этой среде — пропустить этот шаг, полагаться на Step 5 (компиляция) и внимательную сверку SQL с колонками из Step 1.

- [ ] **Step 7: Commit**

```bash
git add server/schema.sql server/db.py server/app.py server/event_scheduler.py
git commit -m "feat(giveaways): add DB schema, state/participate logic, draw scheduler, API routes"
```

---

## Task 3: Админ-логика (CRUD)

**Files:**
- Create: `server/admin_giveaways.py`
- Modify: `server/admin_routes.py`

**Interfaces:**
- Consumes: `db.pool` (общий singleton `from db import db`), паттерн `admin_quests.py` (валидация + прямой SQL через `db.pool.acquire()`/`conn.transaction()`).
- Produces: `list_giveaways_admin() -> list[dict]`, `create_giveaway(**kwargs) -> dict`, `update_giveaway(giveaway_id, **kwargs) -> dict`, `cancel_giveaway(giveaway_id, *, admin_user_id) -> dict`. Используется в Task 4 (`admin/src/lib/adminClient.js`).

- [ ] **Step 1: Написать `server/admin_giveaways.py`**

```python
"""Admin: розыгрыши призов."""
from __future__ import annotations

from typing import Any

from db import db

_VALID_RARITY = frozenset({"common", "rare", "legendary"})
_VALID_PRIZE_TYPE = frozenset({"kut", "manual"})
_VALID_DRAW_TYPE = frozenset({"timer", "instant"})
_VALID_CONDITION_KIND = frozenset({"balance", "harvest_count", "item_count"})
_UNSET = object()


def _validate_rarity(value: str) -> str:
    value = (value or "").strip().lower()
    if value not in _VALID_RARITY:
        raise ValueError(f"Редкость: {', '.join(sorted(_VALID_RARITY))}")
    return value


def _validate_prize(prize_type: str, prize_kut_amount, prize_title, prize_emoji, prize_description):
    prize_type = (prize_type or "").strip().lower()
    if prize_type not in _VALID_PRIZE_TYPE:
        raise ValueError(f"Тип приза: {', '.join(sorted(_VALID_PRIZE_TYPE))}")
    if prize_type == "kut":
        amount = int(prize_kut_amount or 0)
        if amount < 1:
            raise ValueError("Укажите сумму КУТ")
        return prize_type, amount, None, None, None
    title = (prize_title or "").strip()
    if not title:
        raise ValueError("Укажите название приза")
    emoji = (prize_emoji or "🎁").strip() or "🎁"
    description = (prize_description or "").strip()
    return prize_type, None, title, emoji, description


def _validate_draw(draw_type: str, ends_at):
    draw_type = (draw_type or "").strip().lower()
    if draw_type not in _VALID_DRAW_TYPE:
        raise ValueError(f"Тип розыгрыша: {', '.join(sorted(_VALID_DRAW_TYPE))}")
    if draw_type == "timer" and not ends_at:
        raise ValueError("Укажите дату окончания для розыгрыша по таймеру")
    return draw_type


def _validate_conditions(conditions: list[dict]) -> list[dict]:
    cleaned = []
    for idx, cond in enumerate(conditions or []):
        kind = str(cond.get("kind") or "").strip().lower()
        if kind not in _VALID_CONDITION_KIND:
            raise ValueError(f"Условие #{idx + 1}: тип {', '.join(sorted(_VALID_CONDITION_KIND))}")
        try:
            target_value = max(1, int(cond.get("target_value") or cond.get("targetValue") or 1))
        except (TypeError, ValueError):
            raise ValueError(f"Условие #{idx + 1}: укажите значение")
        item_id = None
        if kind == "item_count":
            item_id = str(cond.get("item_id") or cond.get("itemId") or "").strip()
            if not item_id:
                raise ValueError(f"Условие #{idx + 1}: укажите предмет")
        cleaned.append({"kind": kind, "target_value": target_value, "item_id": item_id, "sort_order": idx})
    return cleaned


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


async def list_giveaways_admin() -> list[dict]:
    rows = await db.pool.fetch("SELECT * FROM giveaways ORDER BY sort_order, id DESC")
    result = []
    for row in rows:
        row = dict(row)
        conditions = await db.pool.fetch(
            "SELECT kind, target_value, item_id FROM giveaway_conditions WHERE giveaway_id = $1 ORDER BY sort_order",
            row["id"],
        )
        entries_count = int(
            await db.pool.fetchval(
                "SELECT COUNT(*)::int FROM giveaway_entries WHERE giveaway_id = $1", row["id"]
            ) or 0
        )
        result.append(_giveaway_to_admin_dict(row, [dict(c) for c in conditions], entries_count))
    return result


async def create_giveaway(
    *,
    title: str,
    description: str = "",
    emoji: str = "🎁",
    rarity: str,
    prize_type: str,
    prize_kut_amount: int | None = None,
    prize_title: str | None = None,
    prize_emoji: str | None = None,
    prize_description: str | None = None,
    draw_type: str,
    ends_at=None,
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
    draw_type = _validate_draw(draw_type, ends_at)
    cleaned_conditions = _validate_conditions(conditions or [])

    sort_order = int(
        await db.pool.fetchval("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM giveaways") or 0
    )

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            giveaway_id = await conn.fetchval(
                """
                INSERT INTO giveaways (
                    title, description, emoji, rarity, prize_type, prize_kut_amount,
                    prize_title, prize_emoji, prize_description, draw_type, ends_at,
                    enabled, sort_order
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING id
                """,
                title, (description or "").strip(), (emoji or "🎁").strip() or "🎁", rarity,
                prize_type, kut_amount, p_title, p_emoji, p_desc, draw_type, ends_at,
                bool(enabled), sort_order,
            )
            await _replace_conditions(conn, int(giveaway_id), cleaned_conditions)

    row = await db.pool.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
    return _giveaway_to_admin_dict(dict(row), cleaned_conditions, 0)


async def update_giveaway(
    giveaway_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    emoji: str | None = None,
    rarity: str | None = None,
    prize_type: str | None = None,
    prize_kut_amount: int | None = _UNSET,
    prize_title: str | None = _UNSET,
    prize_emoji: str | None = _UNSET,
    prize_description: str | None = _UNSET,
    draw_type: str | None = None,
    ends_at=_UNSET,
    conditions: list[dict] | None = None,
    enabled: bool | None = None,
    admin_user_id: int,
) -> dict:
    row = await db.pool.fetchrow("SELECT * FROM giveaways WHERE id = $1", giveaway_id)
    if row is None:
        raise ValueError("Розыгрыш не найден")

    sets: list[str] = ["updated_at = NOW()"]
    params: list[Any] = [giveaway_id]

    if title is not None:
        title_clean = title.strip()
        if not title_clean:
            raise ValueError("Название не может быть пустым")
        params.append(title_clean)
        sets.append(f"title = ${len(params)}")
    if description is not None:
        params.append(description.strip())
        sets.append(f"description = ${len(params)}")
    if emoji is not None:
        params.append((emoji or "🎁").strip() or "🎁")
        sets.append(f"emoji = ${len(params)}")
    if rarity is not None:
        params.append(_validate_rarity(rarity))
        sets.append(f"rarity = ${len(params)}")

    current_prize_type = prize_type if prize_type is not None else row["prize_type"]
    if prize_type is not None or prize_kut_amount is not _UNSET or prize_title is not _UNSET:
        resolved_amount = prize_kut_amount if prize_kut_amount is not _UNSET else row["prize_kut_amount"]
        resolved_title = prize_title if prize_title is not _UNSET else row["prize_title"]
        resolved_emoji = prize_emoji if prize_emoji is not _UNSET else row["prize_emoji"]
        resolved_desc = prize_description if prize_description is not _UNSET else row["prize_description"]
        prize_type_v, kut_amount_v, p_title_v, p_emoji_v, p_desc_v = _validate_prize(
            current_prize_type, resolved_amount, resolved_title, resolved_emoji, resolved_desc
        )
        params.append(prize_type_v); sets.append(f"prize_type = ${len(params)}")
        params.append(kut_amount_v); sets.append(f"prize_kut_amount = ${len(params)}")
        params.append(p_title_v); sets.append(f"prize_title = ${len(params)}")
        params.append(p_emoji_v); sets.append(f"prize_emoji = ${len(params)}")
        params.append(p_desc_v); sets.append(f"prize_description = ${len(params)}")

    if draw_type is not None or ends_at is not _UNSET:
        resolved_ends_at = ends_at if ends_at is not _UNSET else row["ends_at"]
        draw_type_v = _validate_draw(draw_type if draw_type is not None else row["draw_type"], resolved_ends_at)
        params.append(draw_type_v); sets.append(f"draw_type = ${len(params)}")
        params.append(resolved_ends_at); sets.append(f"ends_at = ${len(params)}")

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


async def cancel_giveaway(giveaway_id: int, *, admin_user_id: int) -> dict:
    row = await db.pool.fetchrow("SELECT id, title FROM giveaways WHERE id = $1", giveaway_id)
    if row is None:
        raise ValueError("Розыгрыш не найден")
    await db.pool.execute(
        "UPDATE giveaways SET status = 'cancelled', updated_at = NOW() WHERE id = $1",
        giveaway_id,
    )
    return {"ok": True, "title": row["title"]}
```

- [ ] **Step 2: Подключить роуты в `server/admin_routes.py`**

После строки 166 (`from admin_quests import create_quest, delete_quest, update_quest`), добавить:

```python
from admin_giveaways import (
    cancel_giveaway,
    create_giveaway,
    list_giveaways_admin,
    update_giveaway,
)
```

После блока Pydantic-моделей квестов (`class QuestUpdateBody`, заканчивается строкой 611), добавить:

```python
class GiveawayConditionBody(BaseModel):
    kind: str = Field(min_length=3, max_length=16)
    targetValue: int = Field(default=1, ge=1)
    itemId: str | None = Field(default=None, max_length=128)
    model_config = {"extra": "forbid"}


class GiveawayCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    emoji: str = Field(default="🎁", max_length=16)
    rarity: str = Field(min_length=3, max_length=16)
    prizeType: str = Field(min_length=3, max_length=16)
    prizeKutAmount: int | None = Field(default=None, ge=1)
    prizeTitle: str | None = Field(default=None, max_length=120)
    prizeEmoji: str | None = Field(default=None, max_length=16)
    prizeDescription: str | None = Field(default=None, max_length=500)
    drawType: str = Field(min_length=6, max_length=16)
    endsAt: str | None = Field(default=None, max_length=64)
    conditions: list[GiveawayConditionBody] = Field(default_factory=list, max_length=10)
    enabled: bool = True
    model_config = {"extra": "forbid"}


class GiveawayUpdateBody(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    emoji: str | None = Field(default=None, max_length=16)
    rarity: str | None = Field(default=None, max_length=16)
    prizeType: str | None = Field(default=None, max_length=16)
    prizeKutAmount: int | None = Field(default=None, ge=1)
    prizeTitle: str | None = Field(default=None, max_length=120)
    prizeEmoji: str | None = Field(default=None, max_length=16)
    prizeDescription: str | None = Field(default=None, max_length=500)
    drawType: str | None = Field(default=None, max_length=16)
    endsAt: str | None = Field(default=None, max_length=64)
    conditions: list[GiveawayConditionBody] | None = Field(default=None, max_length=10)
    enabled: bool | None = None
    model_config = {"extra": "forbid"}
```

После блока роутов квестов (`admin_content_quest_delete`, заканчивается строкой 2929), добавить:

```python
@router.get("/content/giveaways")
async def admin_content_giveaways_list(
    _admin_id: int = Depends(require_admin_permission("manage_content")),
):
    return await list_giveaways_admin()


@router.post("/content/giveaways")
async def admin_content_giveaway_create(
    body: GiveawayCreateBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await create_giveaway(
            title=body.title,
            description=body.description,
            emoji=body.emoji,
            rarity=body.rarity,
            prize_type=body.prizeType,
            prize_kut_amount=body.prizeKutAmount,
            prize_title=body.prizeTitle,
            prize_emoji=body.prizeEmoji,
            prize_description=body.prizeDescription,
            draw_type=body.drawType,
            ends_at=_parse_dt(body.endsAt),
            conditions=[c.model_dump() for c in body.conditions],
            enabled=body.enabled,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "giveaway_create",
            target_type="giveaway", target_label=body.title,
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/content/giveaways/{giveaway_id}")
async def admin_content_giveaway_patch(
    giveaway_id: int,
    body: GiveawayUpdateBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await update_giveaway(
            giveaway_id,
            title=body.title,
            description=body.description,
            emoji=body.emoji,
            rarity=body.rarity,
            prize_type=body.prizeType,
            prize_kut_amount=body.prizeKutAmount if body.prizeKutAmount is not None else _UNSET,
            prize_title=body.prizeTitle if body.prizeTitle is not None else _UNSET,
            prize_emoji=body.prizeEmoji if body.prizeEmoji is not None else _UNSET,
            prize_description=body.prizeDescription if body.prizeDescription is not None else _UNSET,
            draw_type=body.drawType,
            ends_at=_parse_dt(body.endsAt) if body.endsAt is not None else _UNSET,
            conditions=[c.model_dump() for c in body.conditions] if body.conditions is not None else None,
            enabled=body.enabled,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "giveaway_update",
            target_type="giveaway", target_id=str(giveaway_id),
            target_label=body.title or f"Розыгрыш #{giveaway_id}",
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/content/giveaways/{giveaway_id}")
async def admin_content_giveaway_cancel(
    giveaway_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await cancel_giveaway(giveaway_id, admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "giveaway_cancel",
            target_type="giveaway", target_id=str(giveaway_id),
            target_label=f"Розыгрыш #{giveaway_id}",
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

`GiveawayUpdateBody`'s route handler references `_UNSET` — это sentinel из `admin_giveaways.py`, нужно импортировать его так же, как `_QU` для квестов (строка 2864: `from admin_quests import _UNSET as _QU`). Добавить рядом с началом функции `admin_content_giveaway_patch`, перед `try:`:

```python
    from admin_giveaways import _UNSET
```

- [ ] **Step 3: Проверить синтаксис**

Run: `cd server && python -m py_compile admin_giveaways.py admin_routes.py`
Expected: без вывода, код возврата 0.

- [ ] **Step 4: Commit**

```bash
git add server/admin_giveaways.py server/admin_routes.py
git commit -m "feat(giveaways): add admin CRUD (create/update/cancel/list)"
```

---

## Task 4: Админ-панель (фронтенд)

**Files:**
- Create: `admin/src/pages/sections/GiveawaysSection.jsx`
- Modify: `admin/src/constants/panelNav.js`
- Modify: `admin/src/pages/PanelShell.jsx`
- Modify: `admin/src/lib/adminClient.js`

**Interfaces:**
- Consumes: `GET/POST/PATCH/DELETE /admin/api/content/giveaways` (Task 3), `AdminSelect` (`admin/src/components/AdminSelect.jsx`, пропы `{value, onChange, options: [{value,label}], disabled, placeholder}`), `AdminActionModal` (`admin/src/components/AdminActionModal.jsx`, пропы `{open, title, description, confirmText, danger, loading, onConfirm, onCancel}`).
- Produces: секция `giveaways`, доступная из сайдбара админки при наличии права `manage_content`.

- [ ] **Step 1: Добавить секцию в навигацию**

В `admin/src/constants/panelNav.js`, после строки `{ id: 'content', ... }`, добавить:

```js
  { id: 'giveaways', label: 'Giveaways',       labelRu: 'Розыгрыши',   permission: 'manage_content' },
```

- [ ] **Step 2: API-клиент**

В `admin/src/lib/adminClient.js`, после блока `deleteContentQuest` (заканчивается строкой 1221), добавить:

```js
export async function fetchGiveawaysAdmin() {
  return adminFetch('/content/giveaways')
}

export async function createGiveawayAdmin(payload) {
  return adminFetch('/content/giveaways', { method: 'POST', body: payload })
}

export async function patchGiveawayAdmin(giveawayId, payload) {
  return adminFetch(`/content/giveaways/${giveawayId}`, { method: 'PATCH', body: payload })
}

export async function deleteGiveawayAdmin(giveawayId) {
  return adminFetch(`/content/giveaways/${giveawayId}`, { method: 'DELETE' })
}
```

- [ ] **Step 3: Написать `GiveawaysSection.jsx`**

```jsx
import { useEffect, useState } from 'react'
import AdminSelect from '../../components/AdminSelect'
import AdminActionModal from '../../components/AdminActionModal'
import {
  fetchGiveawaysAdmin,
  createGiveawayAdmin,
  patchGiveawayAdmin,
  deleteGiveawayAdmin,
} from '../../lib/adminClient'

const RARITY_OPTIONS = [
  { value: 'common', label: 'Обычный' },
  { value: 'rare', label: 'Редкий' },
  { value: 'legendary', label: 'Легендарный' },
]

const PRIZE_TYPE_OPTIONS = [
  { value: 'kut', label: 'КУТ (автоначисление)' },
  { value: 'manual', label: 'NFT / подарок (вручную)' },
]

const DRAW_TYPE_OPTIONS = [
  { value: 'instant', label: 'Мгновенно всем выполнившим' },
  { value: 'timer', label: 'Случайно по таймеру' },
]

const CONDITION_KIND_OPTIONS = [
  { value: 'balance', label: 'Баланс КУТ ≥' },
  { value: 'harvest_count', label: 'Урожаев собрано ≥' },
  { value: 'item_count', label: 'Предмет в рюкзаке ≥' },
]

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
    endsAt: '',
    enabled: true,
    conditions: [],
  }
}

export default function GiveawaysSection() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [form, setForm] = useState(null) // null = список, объект = форма создания/редактирования
  const [saving, setSaving] = useState(false)
  const [cancelTarget, setCancelTarget] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const data = await fetchGiveawaysAdmin()
      setItems(data)
      setError(null)
    } catch (e) {
      setError(e?.message || 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const openCreate = () => setForm(emptyForm())

  const openEdit = (item) => setForm({
    id: item.id,
    title: item.title,
    description: item.description ?? '',
    emoji: item.emoji,
    rarity: item.rarity,
    prizeType: item.prizeType,
    prizeKutAmount: item.prizeKutAmount ?? 100,
    prizeTitle: item.prizeTitle ?? '',
    prizeEmoji: item.prizeEmoji ?? '🎁',
    prizeDescription: item.prizeDescription ?? '',
    drawType: item.drawType,
    endsAt: item.endsAt ? item.endsAt.slice(0, 16) : '',
    enabled: item.enabled,
    conditions: item.conditions.map((c) => ({
      kind: c.kind, targetValue: c.targetValue, itemId: c.itemId ?? '',
    })),
  })

  const addCondition = () => setForm((f) => ({
    ...f,
    conditions: [...f.conditions, { kind: 'balance', targetValue: 1, itemId: '' }],
  }))

  const updateCondition = (idx, patch) => setForm((f) => ({
    ...f,
    conditions: f.conditions.map((c, i) => (i === idx ? { ...c, ...patch } : c)),
  }))

  const removeCondition = (idx) => setForm((f) => ({
    ...f,
    conditions: f.conditions.filter((_, i) => i !== idx),
  }))

  const save = async () => {
    if (!form) return
    setSaving(true)
    try {
      const payload = {
        title: form.title,
        description: form.description,
        emoji: form.emoji,
        rarity: form.rarity,
        prizeType: form.prizeType,
        prizeKutAmount: form.prizeType === 'kut' ? Number(form.prizeKutAmount) : null,
        prizeTitle: form.prizeType === 'manual' ? form.prizeTitle : null,
        prizeEmoji: form.prizeType === 'manual' ? form.prizeEmoji : null,
        prizeDescription: form.prizeType === 'manual' ? form.prizeDescription : null,
        drawType: form.drawType,
        endsAt: form.drawType === 'timer' && form.endsAt ? new Date(form.endsAt).toISOString() : null,
        enabled: form.enabled,
        conditions: form.conditions.map((c) => ({
          kind: c.kind,
          targetValue: Number(c.targetValue),
          itemId: c.kind === 'item_count' ? c.itemId : null,
        })),
      }
      if (form.id) {
        await patchGiveawayAdmin(form.id, payload)
      } else {
        await createGiveawayAdmin(payload)
      }
      setForm(null)
      await load()
    } catch (e) {
      setError(e?.message || 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  const confirmCancel = async () => {
    if (!cancelTarget) return
    setSaving(true)
    try {
      await deleteGiveawayAdmin(cancelTarget.id)
      setCancelTarget(null)
      await load()
    } catch (e) {
      setError(e?.message || 'Ошибка отмены')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="panel-section">
      <div className="panel-section-header">
        <h2>Розыгрыши</h2>
        <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={openCreate}>
          + Новый розыгрыш
        </button>
      </div>

      {error && <p className="panel-error-text">{error}</p>}
      {loading ? (
        <p>Загрузка…</p>
      ) : (
        <table className="panel-table">
          <thead>
            <tr>
              <th>Приз</th>
              <th>Редкость</th>
              <th>Тип</th>
              <th>Статус</th>
              <th>Участников</th>
              <th>Победитель</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.emoji} {item.title}</td>
                <td>{RARITY_OPTIONS.find((r) => r.value === item.rarity)?.label}</td>
                <td>{DRAW_TYPE_OPTIONS.find((d) => d.value === item.drawType)?.label}</td>
                <td>{item.status}</td>
                <td>{item.entriesCount}</td>
                <td>{item.winnerUserId ?? '—'}</td>
                <td>
                  <button type="button" className="panel-users-btn" onClick={() => openEdit(item)}>
                    Изменить
                  </button>
                  {item.status === 'active' && (
                    <button
                      type="button"
                      className="panel-users-btn panel-users-btn-danger"
                      onClick={() => setCancelTarget(item)}
                    >
                      Отменить
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {form && (
        <div className="panel-modal-backdrop" role="presentation" onClick={() => setForm(null)}>
          <div className="admin-modal" role="dialog" onClick={(e) => e.stopPropagation()}>
            <h3>{form.id ? 'Редактировать розыгрыш' : 'Новый розыгрыш'}</h3>

            <label className="admin-modal-field">
              <span>Название</span>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </label>
            <label className="admin-modal-field">
              <span>Описание</span>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </label>
            <label className="admin-modal-field">
              <span>Эмодзи</span>
              <input value={form.emoji} onChange={(e) => setForm({ ...form, emoji: e.target.value })} maxLength={8} />
            </label>
            <label className="admin-modal-field">
              <span>Редкость</span>
              <AdminSelect value={form.rarity} onChange={(v) => setForm({ ...form, rarity: v })} options={RARITY_OPTIONS} />
            </label>

            <label className="admin-modal-field">
              <span>Тип приза</span>
              <AdminSelect value={form.prizeType} onChange={(v) => setForm({ ...form, prizeType: v })} options={PRIZE_TYPE_OPTIONS} />
            </label>
            {form.prizeType === 'kut' ? (
              <label className="admin-modal-field">
                <span>Сумма КУТ</span>
                <input type="number" min={1} value={form.prizeKutAmount} onChange={(e) => setForm({ ...form, prizeKutAmount: e.target.value })} />
              </label>
            ) : (
              <>
                <label className="admin-modal-field">
                  <span>Название приза</span>
                  <input value={form.prizeTitle} onChange={(e) => setForm({ ...form, prizeTitle: e.target.value })} />
                </label>
                <label className="admin-modal-field">
                  <span>Эмодзи приза</span>
                  <input value={form.prizeEmoji} onChange={(e) => setForm({ ...form, prizeEmoji: e.target.value })} maxLength={8} />
                </label>
                <label className="admin-modal-field">
                  <span>Описание приза (для игрока)</span>
                  <textarea value={form.prizeDescription} onChange={(e) => setForm({ ...form, prizeDescription: e.target.value })} />
                </label>
              </>
            )}

            <label className="admin-modal-field">
              <span>Механика розыгрыша</span>
              <AdminSelect value={form.drawType} onChange={(v) => setForm({ ...form, drawType: v })} options={DRAW_TYPE_OPTIONS} />
            </label>
            {form.drawType === 'timer' && (
              <label className="admin-modal-field">
                <span>Дата окончания</span>
                <input type="datetime-local" value={form.endsAt} onChange={(e) => setForm({ ...form, endsAt: e.target.value })} />
              </label>
            )}

            <div className="admin-modal-field">
              <span>Условия участия (все обязательны)</span>
              {form.conditions.map((cond, idx) => (
                <div key={idx} style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                  <AdminSelect
                    value={cond.kind}
                    onChange={(v) => updateCondition(idx, { kind: v })}
                    options={CONDITION_KIND_OPTIONS}
                  />
                  <input
                    type="number"
                    min={1}
                    value={cond.targetValue}
                    onChange={(e) => updateCondition(idx, { targetValue: e.target.value })}
                    style={{ width: 90 }}
                  />
                  {cond.kind === 'item_count' && (
                    <input
                      placeholder="id предмета"
                      value={cond.itemId}
                      onChange={(e) => updateCondition(idx, { itemId: e.target.value })}
                    />
                  )}
                  <button type="button" className="panel-users-btn panel-users-btn-danger" onClick={() => removeCondition(idx)}>
                    ✕
                  </button>
                </div>
              ))}
              <button type="button" className="panel-users-btn" onClick={addCondition}>+ Условие</button>
            </div>

            <label className="admin-modal-field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              <span>Включён</span>
            </label>

            <div className="admin-modal-actions">
              <button type="button" className="panel-users-btn" onClick={() => setForm(null)} disabled={saving}>
                Отмена
              </button>
              <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={save} disabled={saving}>
                {saving ? '…' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}

      <AdminActionModal
        open={Boolean(cancelTarget)}
        title="Отменить розыгрыш?"
        description={cancelTarget ? `«${cancelTarget.title}» — участники не смогут вступить, приз не разыгрывается.` : ''}
        confirmText="Отменить розыгрыш"
        danger
        loading={saving}
        onConfirm={confirmCancel}
        onCancel={() => setCancelTarget(null)}
      />
    </div>
  )
}
```

- [ ] **Step 4: Зарегистрировать секцию в `PanelShell.jsx`**

После строки `import ContentSection from './sections/ContentSection'` (строка 16), добавить:

```js
import GiveawaysSection from './sections/GiveawaysSection'
```

После строки `const isContent = section === 'content'` (строка 116), добавить:

```js
  const isGiveaways = section === 'giveaways'
```

После строки `{isContent && <ContentSection />}` (строка 259), добавить:

```js
          {isGiveaways && <GiveawaysSection />}
```

В строке 270 (длинное условие fallback-плейсхолдера), добавить `!isGiveaways` в цепочку (после `!isContent`):

```js
          {!isDashboard && !isUsers && !isAccounts && !isEconomy && !isMarket && !isFarm && !isContent && !isGiveaways && !isBroadcast && !isLogs && !isAnalytics && !isSettings && !isEvents && !isSecurity && !isStaff && !isSupport && !isModeration && !isChronicle && (
```

- [ ] **Step 5: Собрать админку**

Run: `cd admin && npm run build`
Expected: сборка без ошибок.

- [ ] **Step 6: Commit**

```bash
git add admin/src/constants/panelNav.js admin/src/pages/PanelShell.jsx admin/src/pages/sections/GiveawaysSection.jsx admin/src/lib/adminClient.js
git commit -m "feat(giveaways): add admin panel section for creating/managing giveaways"
```

---

## Task 5: Клиент вебаппа + хук + константы редкости

**Files:**
- Create: `src/lib/giveawaysClient.js`
- Create: `src/hooks/useGiveaways.js`
- Create: `src/constants/giveaways.js`

**Interfaces:**
- Consumes: `apiRequest` (`src/lib/apiClient.js`), `ApiError` (`src/lib/apiClient.js`), `canAuthenticate`/`getAuthErrorMessage` (`src/lib/telegram.js`).
- Produces: `useGiveaways({isActive}) -> { giveaways, initialLoading, refreshing, error, errorCode, participate(giveawayId), reload }`; `fetchGiveaway(id)` для модалки деталей (Task 6); `RARITY_ORDER`, `RARITY_LABEL`, `RARITY_ACCENT` (Task 6).

- [ ] **Step 1: Константы редкости**

Создать `src/constants/giveaways.js`:

```js
export const RARITY_ORDER = ['common', 'rare', 'legendary']

export const RARITY_LABEL = {
  common: 'Обычный',
  rare: 'Редкий',
  legendary: 'Легендарный',
}

// legendary переиспользует тот же розово-золотой акцент, что уже задан
// для самой вкладки «Розыгрыши» в src/styles/tabThemes.css (--tab-accent-strong).
export const RARITY_ACCENT = {
  common: { strong: '#34d399', glow: 'rgba(52, 211, 153, 0.32)' },
  rare: { strong: '#5b9be0', glow: 'rgba(91, 155, 224, 0.32)' },
  legendary: { strong: '#f472b6', glow: 'rgba(244, 114, 182, 0.34)' },
}
```

- [ ] **Step 2: API-клиент**

Создать `src/lib/giveawaysClient.js`:

```js
import { apiRequest } from './apiClient'

export function fetchGiveaways() {
  return apiRequest('/api/giveaways')
}

export function fetchGiveaway(giveawayId) {
  return apiRequest(`/api/giveaways/${giveawayId}`)
}

export function participateInGiveaway(giveawayId) {
  return apiRequest(`/api/giveaways/${giveawayId}/participate`, {
    method: 'POST',
    body: {},
  })
}
```

- [ ] **Step 3: Хук `useGiveaways`**

Создать `src/hooks/useGiveaways.js`:

```js
import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import { fetchGiveaways, participateInGiveaway } from '../lib/giveawaysClient'
import { canAuthenticate, getAuthErrorMessage } from '../lib/telegram'

const ACTIVE_SYNC_MS = 30000

function formatGiveawayError(error) {
  if (error instanceof ApiError) return error.message
  return error?.message ?? 'Ошибка розыгрышей'
}

export function useGiveaways({ isActive = true } = {}) {
  const [giveaways, setGiveaways] = useState([])
  const [initialLoading, setInitialLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [errorCode, setErrorCode] = useState(null)
  const [participatingId, setParticipatingId] = useState(null)
  const mountedRef = useRef(false)

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!canAuthenticate()) {
      setError(getAuthErrorMessage())
      setErrorCode('auth')
      setInitialLoading(false)
      return
    }
    if (!silent) {
      if (!mountedRef.current) setInitialLoading(true)
      else setRefreshing(true)
    }
    try {
      const data = await fetchGiveaways()
      if (!mountedRef.current) return
      setGiveaways(data?.giveaways ?? [])
      setError(null)
      setErrorCode(null)
    } catch (err) {
      if (!mountedRef.current) return
      setError(formatGiveawayError(err))
      setErrorCode(err instanceof ApiError ? err.code : 'error')
    } finally {
      if (mountedRef.current) {
        setInitialLoading(false)
        setRefreshing(false)
      }
    }
  }, [])

  const participate = useCallback(async (giveawayId) => {
    setParticipatingId(giveawayId)
    try {
      await participateInGiveaway(giveawayId)
      await load({ silent: true })
      return true
    } catch (err) {
      setError(formatGiveawayError(err))
      return false
    } finally {
      setParticipatingId(null)
    }
  }, [load])

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    if (!isActive) return undefined
    load({ silent: mountedRef.current })
    const timer = window.setInterval(() => load({ silent: true }), ACTIVE_SYNC_MS)
    const onVisible = () => {
      if (document.visibilityState === 'visible') load({ silent: true })
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [isActive, load])

  return {
    giveaways,
    initialLoading,
    refreshing,
    error,
    errorCode,
    participatingId,
    participate,
    reload: () => load({ silent: true }),
  }
}
```

- [ ] **Step 4: Проверить сборку**

Run: `npm run build`
Expected: без ошибок (эти файлы пока никем не импортируются, но должны быть валидны синтаксически — сборка это подтвердит).

- [ ] **Step 5: Commit**

```bash
git add src/lib/giveawaysClient.js src/hooks/useGiveaways.js src/constants/giveaways.js
git commit -m "feat(giveaways): add webapp API client, polling hook, rarity constants"
```

---

## Task 6: Компоненты — карточка-билет и модалка деталей

**Files:**
- Create: `src/components/GiveawayTicketCard.jsx`
- Create: `src/components/GiveawayDetailModal.jsx`
- Modify: `src/styles/giveaways.css`

**Interfaces:**
- Consumes: `RARITY_LABEL`/`RARITY_ACCENT` (Task 5), `fetchGiveaway` (Task 5), `Portal` (`src/components/Portal.jsx`, проп `lockScroll`).
- Produces: `<GiveawayTicketCard giveaway={...} onOpenDetail={(id) => void} onSwipeParticipate={(id) => Promise<boolean>} />`, `<GiveawayDetailModal giveawayId={id|null} isOpen={bool} onClose={() => void} onParticipate={(id) => Promise<boolean>} onNavigateCondition={(kind, itemId) => void} isParticipating={bool} />`. Используются в Task 7 (`GiveawaysModule.jsx`).

- [ ] **Step 1: Карточка-билет со свайпом**

Создать `src/components/GiveawayTicketCard.jsx`:

```jsx
import { useRef, useState } from 'react'
import { RARITY_ACCENT, RARITY_LABEL } from '../constants/giveaways'

const SWIPE_THRESHOLD = 90

export default function GiveawayTicketCard({ giveaway, onOpenDetail, onSwipeParticipate }) {
  const [dragX, setDragX] = useState(0)
  const [swiping, setSwiping] = useState(false)
  const dragRef = useRef({ startX: 0, tracking: false })
  const accent = RARITY_ACCENT[giveaway.rarity] ?? RARITY_ACCENT.common

  const canSwipe = giveaway.status === 'active' && !giveaway.joined
    && (giveaway.conditionsCount === 0 || giveaway.conditionsMet)

  const onTouchStart = (event) => {
    if (!canSwipe) return
    dragRef.current = { startX: event.touches[0].clientX, tracking: true }
  }

  const onTouchMove = (event) => {
    if (!dragRef.current.tracking) return
    const dx = event.touches[0].clientX - dragRef.current.startX
    setDragX(Math.max(0, dx))
  }

  const onTouchEnd = async () => {
    if (!dragRef.current.tracking) return
    dragRef.current.tracking = false
    if (dragX >= SWIPE_THRESHOLD) {
      setSwiping(true)
      const ok = await onSwipeParticipate(giveaway.id)
      setSwiping(false)
      if (!ok) setDragX(0)
    } else {
      setDragX(0)
    }
  }

  let statusLabel = null
  if (giveaway.status === 'completed') {
    statusLabel = giveaway.won ? '🏆 Вы выиграли!' : 'Розыгрыш завершён'
  } else if (giveaway.status === 'cancelled') {
    statusLabel = 'Розыгрыш отменён'
  } else if (giveaway.joined) {
    statusLabel = giveaway.drawType === 'instant' ? '✅ Приз получен' : '🎟️ Вы в розыгрыше'
  }

  return (
    <button
      type="button"
      data-no-swipe
      className={`giveaway-ticket giveaway-ticket--${giveaway.rarity}${swiping ? ' giveaway-ticket--swiping' : ''}`}
      style={{
        '--ticket-accent-strong': accent.strong,
        '--ticket-accent-glow': accent.glow,
        transform: dragX ? `translateX(${dragX}px)` : undefined,
      }}
      onClick={() => { if (!dragX) onOpenDetail(giveaway.id) }}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
    >
      <span className="giveaway-ticket-rarity">{RARITY_LABEL[giveaway.rarity] ?? giveaway.rarity}</span>
      <span className="giveaway-ticket-emoji" aria-hidden>{giveaway.emoji}</span>
      <span className="giveaway-ticket-title">{giveaway.title}</span>
      {statusLabel && <span className="giveaway-ticket-status">{statusLabel}</span>}
      {canSwipe && !statusLabel && (
        <span className="giveaway-ticket-swipe-hint">Смахните →</span>
      )}
    </button>
  )
}
```

- [ ] **Step 2: Модалка деталей (3 зоны)**

Создать `src/components/GiveawayDetailModal.jsx`:

```jsx
import { useEffect, useState } from 'react'
import Portal from './Portal'
import { fetchGiveaway } from '../lib/giveawaysClient'
import { RARITY_ACCENT, RARITY_LABEL } from '../constants/giveaways'

const CONDITION_LABEL = {
  balance: (cond) => `Баланс: ${cond.current} из ${cond.targetValue} КУТ`,
  harvest_count: (cond) => `Урожаев собрано: ${cond.current} из ${cond.targetValue}`,
  item_count: (cond) => `Предмет «${cond.itemId}»: ${cond.current} из ${cond.targetValue}`,
}

const CONDITION_NAV_TARGET = {
  balance: 'trade',
  harvest_count: 'farm',
  item_count: 'farm-inventory',
}

export default function GiveawayDetailModal({
  giveawayId,
  isOpen,
  onClose,
  onParticipate,
  onNavigateCondition,
  isParticipating,
}) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!isOpen || !giveawayId) {
      setDetail(null)
      return
    }
    setLoading(true)
    fetchGiveaway(giveawayId)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
  }, [isOpen, giveawayId])

  if (!isOpen || !giveawayId) return null

  const accent = detail ? (RARITY_ACCENT[detail.rarity] ?? RARITY_ACCENT.common) : RARITY_ACCENT.common

  return (
    <Portal lockScroll>
      <div className="shop-modal-root" role="presentation" onClick={onClose}>
        <div
          className="shop-modal giveaway-detail-modal"
          role="dialog"
          aria-modal="true"
          onClick={(e) => e.stopPropagation()}
          style={{ '--ticket-accent-strong': accent.strong, '--ticket-accent-glow': accent.glow }}
        >
          <button type="button" className="shop-modal-close" onClick={onClose} aria-label="Закрыть">✕</button>

          {loading || !detail ? (
            <p className="giveaway-detail-loading">Загрузка…</p>
          ) : (
            <>
              {/* Зона 1: приз + таймер */}
              <div className="giveaway-detail-hero">
                <span className="giveaway-detail-hero-emoji" aria-hidden>
                  {detail.prize.type === 'kut' ? '💰' : (detail.prize.emoji ?? '🎁')}
                </span>
                <h2 className="giveaway-detail-title">{detail.title}</h2>
                <p className="giveaway-detail-prize">
                  {detail.prize.type === 'kut'
                    ? `${detail.prize.amount} КУТ`
                    : detail.prize.title}
                </p>
                <span className="giveaway-detail-badge">
                  {detail.drawType === 'instant' ? 'Мгновенно' : 'По таймеру'}
                </span>
              </div>

              {/* Зона 2: условия */}
              <div className="giveaway-detail-conditions">
                {detail.conditions.length === 0 ? (
                  <p className="giveaway-detail-no-conditions">Условий нет — участвуйте сразу</p>
                ) : (
                  detail.conditions.map((cond, idx) => (
                    <div
                      key={idx}
                      className={`giveaway-detail-condition${cond.satisfied ? ' giveaway-detail-condition--done' : ''}`}
                    >
                      <span className="giveaway-detail-condition-check" aria-hidden>
                        {cond.satisfied ? '✅' : '⬜'}
                      </span>
                      <span className="giveaway-detail-condition-label">
                        {(CONDITION_LABEL[cond.kind] ?? (() => cond.kind))(cond)}
                      </span>
                      {!cond.satisfied && (
                        <button
                          type="button"
                          className="giveaway-detail-condition-goto"
                          onClick={() => onNavigateCondition(CONDITION_NAV_TARGET[cond.kind] ?? 'farm')}
                        >
                          Перейти
                        </button>
                      )}
                    </div>
                  ))
                )}
              </div>

              {/* Зона 3: действие */}
              {detail.result ? (
                <div className="giveaway-detail-result">
                  {detail.result.won ? '🎉 Вы выиграли!' : 'В этот раз не повезло'}
                </div>
              ) : detail.joined ? (
                <div className="giveaway-detail-joined">
                  {detail.drawType === 'instant' ? '✅ Приз получен' : '🎟️ Вы участвуете, ждите розыгрыша'}
                </div>
              ) : (
                <button
                  type="button"
                  className={`giveaway-detail-cta${detail.conditionsMet ? ' giveaway-detail-cta--ready' : ''}`}
                  disabled={!detail.conditionsMet || isParticipating}
                  onClick={() => onParticipate(detail.id)}
                >
                  {isParticipating ? 'Секунду…' : 'Участвовать'}
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </Portal>
  )
}
```

- [ ] **Step 3: Стили билета и модалки**

В `src/styles/giveaways.css` (в конец файла) добавить:

```css
.giveaways-ticket-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.6rem;
}

.giveaway-ticket {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3rem;
  padding: 1rem 0.75rem;
  border-radius: 14px;
  border: 1px solid var(--ticket-accent-strong);
  background:
    radial-gradient(circle at 50% 0%, var(--ticket-accent-glow) 0%, transparent 65%),
    linear-gradient(180deg, rgba(10, 24, 16, 0.94) 0%, rgba(6, 16, 10, 0.98) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 0 14px var(--ticket-accent-glow);
  color: #f5f0e0;
  cursor: pointer;
  text-align: center;
  transition: transform 0.15s ease;
}

/* Перфорация по бокам билета — вырезы через radial-gradient маску. */
.giveaway-ticket::before,
.giveaway-ticket::after {
  content: '';
  position: absolute;
  top: 50%;
  width: 14px;
  height: 14px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(4, 10, 7, 1) 60%, transparent 62%);
  transform: translateY(-50%);
}
.giveaway-ticket::before { left: -7px; }
.giveaway-ticket::after { right: -7px; }

.giveaway-ticket--swiping {
  transition: transform 0.2s ease;
  opacity: 0.6;
}

.giveaway-ticket-rarity {
  font-size: 0.58rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ticket-accent-strong);
}

.giveaway-ticket-emoji {
  font-size: 2rem;
  filter: drop-shadow(0 0 8px var(--ticket-accent-glow));
}

.giveaway-ticket-title {
  font-size: 0.82rem;
  font-weight: 700;
}

.giveaway-ticket-status {
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--ticket-accent-strong);
}

.giveaway-ticket-swipe-hint {
  font-size: 0.6rem;
  font-weight: 600;
  opacity: 0.6;
}

.giveaway-detail-modal {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.giveaway-detail-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3rem;
  text-align: center;
}

.giveaway-detail-hero-emoji {
  font-size: 3rem;
  filter: drop-shadow(0 0 14px var(--ticket-accent-glow));
}

.giveaway-detail-title {
  margin: 0;
  font-family: Cinzel, Georgia, serif;
  font-size: 1.2rem;
}

.giveaway-detail-prize {
  margin: 0;
  font-weight: 800;
  color: var(--ticket-accent-strong);
}

.giveaway-detail-badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  border: 1px solid var(--ticket-accent-strong);
  font-size: 0.62rem;
  font-weight: 800;
  text-transform: uppercase;
}

.giveaway-detail-conditions {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.giveaway-detail-condition {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.6rem;
  border-radius: 10px;
  background: rgba(8, 18, 12, 0.6);
  font-size: 0.78rem;
}

.giveaway-detail-condition--done {
  opacity: 0.7;
}

.giveaway-detail-condition-label {
  flex: 1;
  min-width: 0;
}

.giveaway-detail-condition-goto {
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  border: 1px solid var(--ticket-accent-strong);
  background: transparent;
  color: var(--ticket-accent-strong);
  font-size: 0.68rem;
  font-weight: 700;
  cursor: pointer;
}

.giveaway-detail-cta {
  width: 100%;
  padding: 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(212, 175, 55, 0.3);
  background: rgba(148, 163, 184, 0.15);
  color: rgba(255, 255, 255, 0.5);
  font-weight: 800;
  font-size: 0.92rem;
}

.giveaway-detail-cta--ready {
  border-color: #fde68a;
  background: linear-gradient(180deg, #fde68a 0%, #d4a72c 100%);
  color: #2a1808;
  animation: giveaway-cta-pulse 2s ease-in-out infinite;
}

@keyframes giveaway-cta-pulse {
  0%, 100% { box-shadow: 0 0 10px rgba(212, 175, 55, 0.4); }
  50% { box-shadow: 0 0 24px rgba(212, 175, 55, 0.75); }
}

.giveaway-detail-joined,
.giveaway-detail-result {
  text-align: center;
  font-weight: 700;
  padding: 0.75rem;
}
```

- [ ] **Step 4: Проверить сборку**

Run: `npm run build`
Expected: без ошибок.

- [ ] **Step 5: Commit**

```bash
git add src/components/GiveawayTicketCard.jsx src/components/GiveawayDetailModal.jsx src/styles/giveaways.css
git commit -m "feat(giveaways): add ticket card (swipe-to-participate) and 3-zone detail modal"
```

---

## Task 7: Сборка воедино — GiveawaysModule, farmSegment из App.jsx, проверка в браузере

**Files:**
- Modify: `src/components/GiveawaysModule.jsx`
- Modify: `src/App.jsx`
- Modify: `src/components/FarmModule.jsx`

**Interfaces:**
- Consumes: `useGiveaways` (Task 5), `GiveawayTicketCard`/`GiveawayDetailModal` (Task 6), существующий паттерн `tradeSegment`/`setTradeSegment` в `src/App.jsx`.

- [ ] **Step 1: Поднять `farmSegment` в `App.jsx`**

В `src/App.jsx:106-120` (`AppWithOnboarding`) заменить:

```jsx
function AppWithOnboarding() {
  const [tab, setTab] = useState(() => resolveStartTab(getStartTab() ?? 'farm').tab)
  const [tradeSegment, setTradeSegment] = useState(() => resolveStartTab(getStartTab() ?? 'farm').tradeSegment)

  return (
    <OnboardingProvider activeTab={tab}>
      <AppShell
        tab={tab}
        setTab={setTab}
        tradeSegment={tradeSegment}
        setTradeSegment={setTradeSegment}
      />
    </OnboardingProvider>
  )
}
```

на:

```jsx
function AppWithOnboarding() {
  const [tab, setTab] = useState(() => resolveStartTab(getStartTab() ?? 'farm').tab)
  const [tradeSegment, setTradeSegment] = useState(() => resolveStartTab(getStartTab() ?? 'farm').tradeSegment)
  const [farmSegment, setFarmSegment] = useState('plots')

  return (
    <OnboardingProvider activeTab={tab}>
      <AppShell
        tab={tab}
        setTab={setTab}
        tradeSegment={tradeSegment}
        setTradeSegment={setTradeSegment}
        farmSegment={farmSegment}
        setFarmSegment={setFarmSegment}
      />
    </OnboardingProvider>
  )
}
```

В `src/App.jsx:122` заменить сигнатуру:

```jsx
function AppShell({ tab, setTab, tradeSegment, setTradeSegment }) {
```

на:

```jsx
function AppShell({ tab, setTab, tradeSegment, setTradeSegment, farmSegment, setFarmSegment }) {
```

Добавить обработчик перехода из модалки розыгрыша (после `handleGuideNavigateMarket`, перед `useSwipeTabs(...)`, т.е. после строки 147):

```jsx
  const handleGiveawayNavigateCondition = useCallback((target) => {
    if (target === 'trade') {
      setTab('trade')
    } else if (target === 'farm-inventory') {
      setTab('farm')
      setFarmSegment('inventory')
    } else {
      setTab('farm')
      setFarmSegment('plots')
    }
  }, [setTab, setFarmSegment])
```

В `src/App.jsx:188-190` заменить:

```jsx
        <div className={tab === 'farm' ? '' : 'hidden'} aria-hidden={tab !== 'farm'}>
          <FarmModule isActive={tab === 'farm'} />
        </div>
```

на:

```jsx
        <div className={tab === 'farm' ? '' : 'hidden'} aria-hidden={tab !== 'farm'}>
          <FarmModule isActive={tab === 'farm'} farmSegment={farmSegment} onFarmSegmentChange={setFarmSegment} />
        </div>
```

В `src/App.jsx:223-225` заменить:

```jsx
        <div className={tab === 'giveaways' ? '' : 'hidden'} aria-hidden={tab !== 'giveaways'}>
          <GiveawaysModule isActive={tab === 'giveaways'} />
        </div>
```

на:

```jsx
        <div className={tab === 'giveaways' ? '' : 'hidden'} aria-hidden={tab !== 'giveaways'}>
          <GiveawaysModule isActive={tab === 'giveaways'} onNavigateCondition={handleGiveawayNavigateCondition} />
        </div>
```

- [ ] **Step 2: `FarmModule` принимает `farmSegment` пропом**

В `src/components/FarmModule.jsx:33-34` заменить:

```jsx
export default function FarmModule({ isActive = true }) {
  const [farmSegment, setFarmSegment] = useState('plots')
```

на:

```jsx
export default function FarmModule({ isActive = true, farmSegment, onFarmSegmentChange }) {
```

В `src/components/FarmModule.jsx` (внутри JSX сегмент-переключателя) заменить:

```jsx
              onClick={() => setFarmSegment(s.id)}
```

на:

```jsx
              onClick={() => onFarmSegmentChange(s.id)}
```

- [ ] **Step 3: Переписать `GiveawaysModule.jsx`**

Заменить весь файл `src/components/GiveawaysModule.jsx` на:

```jsx
import { useState } from 'react'
import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import GiveawayTicketCard from './GiveawayTicketCard'
import GiveawayDetailModal from './GiveawayDetailModal'
import { useGiveaways } from '../hooks/useGiveaways'
import '../styles/giveaways.css'

export default function GiveawaysModule({ isActive = true, onNavigateCondition }) {
  const { giveaways, initialLoading, error, participate, participatingId } = useGiveaways({ isActive })
  const [openId, setOpenId] = useState(null)

  const handleNavigateCondition = (target) => {
    setOpenId(null)
    onNavigateCondition?.(target)
  }

  return (
    <div className="relative min-h-screen tab-theme-giveaways giveaways-module" aria-hidden={!isActive}>
      <FarmBackground />
      <TabAtmosphere variant="giveaways" />

      <div className="relative z-10 giveaways-shell py-4 pb-2 animate-slide-up">
        <header className="giveaways-header">
          <p className="giveaways-header-eyebrow">Cute</p>
          <h1 className="giveaways-header-title">Розыгрыши</h1>
        </header>

        {error && <p className="giveaways-empty">{error}</p>}

        {initialLoading ? (
          <p className="giveaways-empty">Загрузка…</p>
        ) : giveaways.length === 0 ? (
          <div className="giveaways-empty">
            <span className="giveaways-empty-icon" aria-hidden>🎁</span>
            <p>Скоро здесь появятся розыгрыши призов</p>
          </div>
        ) : (
          <div className="giveaways-ticket-grid">
            {giveaways.map((giveaway) => (
              <GiveawayTicketCard
                key={giveaway.id}
                giveaway={giveaway}
                onOpenDetail={setOpenId}
                onSwipeParticipate={participate}
              />
            ))}
          </div>
        )}
      </div>

      <GiveawayDetailModal
        giveawayId={openId}
        isOpen={Boolean(openId)}
        onClose={() => setOpenId(null)}
        onParticipate={async (id) => {
          const ok = await participate(id)
          if (ok) setOpenId(null)
        }}
        onNavigateCondition={handleNavigateCondition}
        isParticipating={participatingId === openId}
      />
    </div>
  )
}
```

- [ ] **Step 4: Проверить сборку и тесты**

Run: `npm run build`
Expected: без ошибок.

Run: `npx vitest run`
Expected: все существующие тесты по-прежнему проходят (эта задача их не трогает).

- [ ] **Step 5: Живая проверка в браузере**

Запустить дев-сервер, открыть вкладку «Розыгрыши»:
1. Если бэкенд недоступен (нет живого Postgres) — экран покажет ошибку/пустое состояние без падения (проверить через `read_console_messages`, что нет необработанных JS-исключений).
2. Если бэкенд запущен и есть тестовый розыгрыш (см. Task 2 Step 6) — карточка-билет рендерится с редкостью/эмодзи/названием; тап открывает модалку на 3 зоны; для розыгрыша без условий кнопка «Участвовать» сразу активна и пульсирует; после участия — билет показывает статус.
3. Перейти на Ферму — убедиться, что сегменты «Грядки/Инвентарь/Крафт» по-прежнему переключаются (регрессия после подъёма `farmSegment` в `App.jsx`).

- [ ] **Step 6: Commit**

```bash
git add src/components/GiveawaysModule.jsx src/App.jsx src/components/FarmModule.jsx
git commit -m "feat(giveaways): wire ticket list + detail modal into GiveawaysModule, lift farmSegment to App"
```

---

## Self-Review

**1. Spec coverage:**
- Модель данных (3 таблицы) — Task 2 Step 1. ✅
- Расширяемый реестр условий (в v1 — только внутриигровые) — Task 1. ✅
- Обе механики розыгрыша (instant/timer), таймер через существующий тик — Task 2 Steps 2, 4. ✅
- Один билет на человека, идемпотентный `participate` — Task 2 Step 2 (`already_joined` early-return). ✅
- Приз `kut` автоначисление / `manual` только отображение — Task 2 Step 2 (`_giveaway_prize_summary`, начисление только при `prize_type == 'kut'`). ✅
- Уведомление победителя (DM + in-app) — Task 2 Step 2 (`draw_timer_giveaways`). ✅
- Админ-панель CRUD — Task 3, Task 4. ✅
- Авто-обновление без кнопки «Проверить» — Task 5 (`useGiveaways`, тот же паттерн что `useQuests`). ✅
- Свайп-участие только когда условий нет/выполнены, `data-no-swipe` — Task 6 (`GiveawayTicketCard`). ✅
- Модалка на 3 зоны, «Перейти» по условиям, пульсирующая кнопка — Task 6 (`GiveawayDetailModal`). ✅
- Цветовая редкость (зелёный/синий/розово-золотой) — Task 5 (`constants/giveaways.js`). ✅
- Вне v1 (подписка/задания/рефералы/Stars-автовыплата) — нигде не реализовано, реестр условий в Task 1 расширяем под них. ✅

**2. Correctness catch during self-review:** первая черновая версия `participate_in_giveaway`/`draw_timer_giveaways` (Task 2) вызывала `await self.get_giveaway_detail(...)` и `await create_admin_message_notification(self.pool, ...)` — оба сами делают `self.pool.acquire()` — ещё держа внешний `conn` из `self.pool.acquire()`. Это двойной чек-аут соединения из пула на одну операцию. Исправлено: ранний выход при `already_joined` больше не return'ится изнутри блока `async with conn`, а единый `return await self.get_giveaway_detail(...)` стоит после его закрытия; в `draw_timer_giveaways` уведомления собираются в `pending_notifications` и отправляются после того, как соединение отпущено. Sync fire-and-forget хелперы (`schedule_balance_event`, `log_game_event`, `schedule_player_telegram_dm`) остались внутри транзакции — они не блокируют и не делают собственный `await pool.acquire()` (подтверждено по `server/audit_log.py:193-203`), в отличие от `create_admin_message_notification`/`get_giveaway_detail`, которые await'ятся.

**3. Placeholder scan:** Полный код во всех шагах, без "TBD"/"добавить обработку ошибок" без реализации. Комментарии — только там, где объясняют неочевидное (почему `data-no-swipe`, почему легендарная редкость переиспользует акцент вкладки, почему `instant`-розыгрыш не переводится в `status='completed'`).

**4. Type consistency:**
- `all_conditions_met(ctx, conditions)` / `condition_satisfied(ctx, cond)` — сигнатура одинакова в Task 1 (определение+тесты) и Task 2 (использование в `db.py`).
- Ключи `ctx = {"balance", "harvest_count", "items"}` совпадают между `_giveaway_condition_ctx` (Task 2) и чекерами (Task 1).
- Поля JSON-ответа (`conditionsMet`, `drawType`, `endsAt`, `prize.type`/`prize.amount`/`prize.title`/`prize.emoji`/`prize.description`, `joined`, `won`, `result.won`) одинаковы между `server/db.py` (Task 2, продюсер) и фронтендом — `useGiveaways.js`/`GiveawayTicketCard.jsx`/`GiveawayDetailModal.jsx` (Task 5, 6, читают эти же имена).
- `GiveawayTicketCard`'s `onSwipeParticipate`/`onOpenDetail` пропы и `GiveawayDetailModal`'s `onParticipate`/`onNavigateCondition`/`isParticipating` — сигнатуры, определённые в Task 6, используются идентично в `GiveawaysModule.jsx` (Task 7).
- `farmSegment`/`onFarmSegmentChange` — имя пропа согласовано между `App.jsx` (Task 7, продюсер) и `FarmModule.jsx` (Task 7, потребитель) — совпадает с уже существующим паттерном `tradeSegment`/`onSegmentChange` у `TradeModule`.
- `admin_giveaways.py`'s `_UNSET` — используется в `admin_routes.py`'s `admin_content_giveaway_patch` через отдельный `from admin_giveaways import _UNSET` (Task 3, аналогично `_QU` у квестов), не конфликтует с одноимённым sentinel в `admin_quests.py`.
