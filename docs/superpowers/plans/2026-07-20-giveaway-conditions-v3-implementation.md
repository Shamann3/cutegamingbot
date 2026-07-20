# Розыгрыши v3 — условия «подписка на канал» и «пригласить друзей» — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new giveaway condition kinds — `channel_sub` (подписка на Telegram-канал) и `referral_count` (пригласить N друзей, через уже существующий счётчик `users.refferals`) — к уже работающему конструктору условий розыгрышей.

**Architecture:** `channel_sub` требует внешнего HTTP-вызова к Telegram Bot API (`getChatMember`), кэшируемого в новой таблице `giveaway_channel_sub_cache` (TTL 10 мин для списка/детали, живая проверка без кэша непосредственно перед участием). `referral_count` — чистое сравнение уже существующей колонки `users.refferals` с целевым значением, без внешних вызовов. Оба типа регистрируются в уже существующем реестре условий (`server/giveaway_conditions.py`), не меняя общую архитектуру конструктора условий.

**Tech Stack:** FastAPI + asyncpg (backend), aiohttp (Telegram Bot API), React + Vite (webapp + admin panel), pytest (backend unit tests) — тот же стек, что и v1/v2, новая зависимость не нужна (aiohttp уже используется в `server/telegram_notify.py`).

## Global Constraints

- Следовать `docs/superpowers/specs/2026-07-20-giveaway-conditions-v3-design.md` — это источник истины для каждого решения ниже.
- Условие «Запуск бота» НЕ реализуется отдельно — оно эквивалентно `referral_count` (см. спеку, раздел «Контекст»).
- Никогда не делать внешний HTTP-вызов (к Telegram), удерживая соединение из пула `asyncpg` или блокировку строки (`FOR UPDATE`) — тот же принцип, что уже соблюдался в v2 для `db.py`.
- Ошибка/недоступность Telegram API при проверке подписки → трактуется как «не подписан» (fail-closed), никогда не как «подписан».
- Перед реальным участием (`participate_in_giveaway`) проверка `channel_sub` всегда живая (`force_refresh=True`), кэш не используется.
- Все новые/изменённые строки в вебаппе и админке — на русском.
- Нет живого Postgres в этом окружении — методы, трогающие БД или сеть, верифицируются через `python -m py_compile` + внимательный ручной review, а не через живой smoke-тест. Только чистая логика (проверки условий, TTL, статус-маппинг) покрывается настоящими TDD-тестами через pytest.

---

### Task 1: Чистая логика — новые чекеры условий + pure-хелперы telegram_membership (TDD) + миграция схемы

**Files:**
- Modify: `server/giveaway_conditions.py`
- Modify: `server/tests/test_giveaway_conditions.py`
- Create: `server/telegram_membership.py`
- Create: `server/tests/test_telegram_membership.py`
- Modify: `server/schema.sql` (после блока `giveaway_entries`, который сейчас заканчивается на строке 1064)

**Interfaces:**
- Производит: `check_referral_count(ctx, cond) -> bool`, `check_channel_sub(ctx, cond) -> bool` (добавлены в `CONDITION_CHECKERS`, `VALID_CONDITION_KINDS` расширен до `{"balance", "harvest_count", "item_count", "channel_sub", "referral_count"}`).
- Производит: `_is_member_status(status: str | None) -> bool`, `_is_cache_fresh(checked_at: datetime, now: datetime, ttl_minutes: int = 10) -> bool`, `TTL_MINUTES = 10` в `server/telegram_membership.py` — потребляются Task 2 косвенно через `resolve_channel_sub` (та же файл, не тестируется напрямую в этой задаче — см. Task 2).
- Схема: `giveaway_conditions.kind` теперь допускает `'channel_sub'`, `'referral_count'`; новая таблица `giveaway_channel_sub_cache(user_id, channel, is_member, checked_at)`.

- [ ] **Step 1: Написать падающие тесты для новых чекеров условий**

В `server/tests/test_giveaway_conditions.py` найти:

```python
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
```

Заменить на (добавляет тесты новых типов, а `test_unknown_kind_is_not_satisfied` теперь ссылается на `quest_count` — единственный тип из докстринга модуля, который всё ещё не реализован, раз `channel_sub` этой задачей перестаёт быть «неизвестным»):

```python
def test_item_count_condition():
    cond = {"kind": "item_count", "target_value": 3, "item_id": "Ключ"}
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {"Ключ": 3}}, cond) is True
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {"Ключ": 2}}, cond) is False
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {}}, cond) is False


def test_referral_count_condition():
    cond = {"kind": "referral_count", "target_value": 3}
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {}, "referral_count": 3}, cond) is True
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {}, "referral_count": 2}, cond) is False


def test_channel_sub_condition():
    cond = {"kind": "channel_sub", "target_value": 1, "item_id": "cute_channel"}
    ctx_subscribed = {"balance": 0, "harvest_count": 0, "items": {}, "channel_sub": {"cute_channel": True}}
    ctx_not_subscribed = {"balance": 0, "harvest_count": 0, "items": {}, "channel_sub": {"cute_channel": False}}
    ctx_missing = {"balance": 0, "harvest_count": 0, "items": {}, "channel_sub": {}}
    assert condition_satisfied(ctx_subscribed, cond) is True
    assert condition_satisfied(ctx_not_subscribed, cond) is False
    assert condition_satisfied(ctx_missing, cond) is False


def test_unknown_kind_is_not_satisfied():
    # Условия из будущих фаз (quest_count и т.п.) не должны падать с
    # исключением — просто "не выполнено" до того, как появится чекер.
    cond = {"kind": "quest_count", "target_value": 1}
    ctx = {"balance": 999999, "harvest_count": 999999, "items": {}}
    assert condition_satisfied(ctx, cond) is False
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

Run: `cd server && python -m pytest tests/test_giveaway_conditions.py -v`
Expected: `test_referral_count_condition` и `test_channel_sub_condition` — FAIL/ERROR (`KeyError` или неверный результат, т.к. чекеров ещё нет); остальные — PASS как раньше.

- [ ] **Step 3: Реализовать новые чекеры условий**

В `server/giveaway_conditions.py` найти:

```python
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
```

Заменить на:

```python
VALID_CONDITION_KINDS = frozenset({
    "balance", "harvest_count", "item_count", "channel_sub", "referral_count",
})


def check_balance(ctx: dict, cond: dict) -> bool:
    return int(ctx.get("balance") or 0) >= int(cond["target_value"])


def check_harvest_count(ctx: dict, cond: dict) -> bool:
    return int(ctx.get("harvest_count") or 0) >= int(cond["target_value"])


def check_item_count(ctx: dict, cond: dict) -> bool:
    items = ctx.get("items") or {}
    return int(items.get(cond["item_id"], 0)) >= int(cond["target_value"])


def check_referral_count(ctx: dict, cond: dict) -> bool:
    return int(ctx.get("referral_count") or 0) >= int(cond["target_value"])


def check_channel_sub(ctx: dict, cond: dict) -> bool:
    channel_sub = ctx.get("channel_sub") or {}
    return bool(channel_sub.get(cond["item_id"], False))


CONDITION_CHECKERS: dict[str, Callable[[dict, dict], bool]] = {
    "balance": check_balance,
    "harvest_count": check_harvest_count,
    "item_count": check_item_count,
    "referral_count": check_referral_count,
    "channel_sub": check_channel_sub,
}
```

Также обновить докстринг файла — найти:

```python
"""Розыгрыши: реестр проверяемых условий участия.

Каждое условие — запись в CONDITION_CHECKERS. Новые типы условий
(channel_sub, quest_count, referral_count — следующие фазы) добавляются
сюда новой записью, не трогая участие/список/детали розыгрыша.
"""
```

Заменить на:

```python
"""Розыгрыши: реестр проверяемых условий участия.

Каждое условие — запись в CONDITION_CHECKERS. Новые типы условий
(quest_count — следующие фазы) добавляются сюда новой записью, не трогая
участие/список/детали розыгрыша.
"""
```

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `cd server && python -m pytest tests/test_giveaway_conditions.py -v`
Expected: 9 passed (было 6, +3 новых: `test_referral_count_condition`, `test_channel_sub_condition`, и `test_unknown_kind_is_not_satisfied` теперь с `quest_count`)

- [ ] **Step 5: Написать падающие тесты для pure-хелперов telegram_membership**

Создать `server/tests/test_telegram_membership.py`:

```python
"""telegram_membership: чистые функции статус-маппинга и TTL, без сети/БД."""
from datetime import datetime, timedelta, timezone

from telegram_membership import _is_cache_fresh, _is_member_status, TTL_MINUTES

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def test_is_member_status_true_for_member_administrator_creator():
    assert _is_member_status("member") is True
    assert _is_member_status("administrator") is True
    assert _is_member_status("creator") is True


def test_is_member_status_false_for_other_statuses():
    assert _is_member_status("left") is False
    assert _is_member_status("kicked") is False
    assert _is_member_status("restricted") is False
    assert _is_member_status(None) is False
    assert _is_member_status("") is False


def test_is_member_status_case_insensitive():
    assert _is_member_status("Member") is True
    assert _is_member_status("CREATOR") is True


def test_is_cache_fresh_within_ttl():
    checked_at = NOW - timedelta(minutes=5)
    assert _is_cache_fresh(checked_at, NOW, ttl_minutes=TTL_MINUTES) is True


def test_is_cache_fresh_stale_after_ttl():
    checked_at = NOW - timedelta(minutes=11)
    assert _is_cache_fresh(checked_at, NOW, ttl_minutes=TTL_MINUTES) is False


def test_is_cache_fresh_exactly_at_ttl_boundary_is_stale():
    checked_at = NOW - timedelta(minutes=TTL_MINUTES)
    assert _is_cache_fresh(checked_at, NOW, ttl_minutes=TTL_MINUTES) is False
```

- [ ] **Step 6: Запустить тесты и убедиться, что они падают**

Run: `cd server && python -m pytest tests/test_telegram_membership.py -v`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'telegram_membership'`

- [ ] **Step 7: Написать server/telegram_membership.py**

Создать `server/telegram_membership.py`:

```python
"""Проверка подписки пользователя на Telegram-канал для условия giveaway
channel_sub. Живой вызов Telegram Bot API (getChatMember) кэшируется в
giveaway_channel_sub_cache на TTL_MINUTES, чтобы не упираться в лимиты
Telegram при частом опросе списка розыгрышей (каждые 30 сек в вебаппе).
Перед реальным участием (participate_in_giveaway) кэш обходится
(force_refresh=True) — участие никогда не проверяется по устаревшим данным.

Правило пула: этот модуль никогда не держит соединение из pool.acquire()
открытым во время HTTP-вызова к Telegram — чтение кэша, сам HTTP-вызов и
запись кэша обратно — три раздельных шага.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("cute-farm.giveaway-membership")

TTL_MINUTES = 10
_MEMBER_STATUSES = frozenset({"member", "administrator", "creator"})


def _is_member_status(status: str | None) -> bool:
    return (status or "").strip().lower() in _MEMBER_STATUSES


def _is_cache_fresh(checked_at: datetime, now: datetime, ttl_minutes: int = TTL_MINUTES) -> bool:
    return (now - checked_at) < timedelta(minutes=ttl_minutes)


async def _fetch_chat_member_status(channel: str, user_id: int) -> str | None:
    """Живой вызов Telegram Bot API. Возвращает status ('member'/'left'/...)
    или None при любой ошибке (канал не найден, бот не админ канала, таймаут)
    — вызывающий код трактует None как «не подписан» (fail-closed)."""
    import aiohttp
    from config import BOT_TOKEN

    if not BOT_TOKEN:
        return None
    chat_id = channel if channel.startswith("@") else f"@{channel}"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params={"chat_id": chat_id, "user_id": user_id},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
    except Exception:
        logger.exception("getChatMember failed (channel=%s, user_id=%s)", channel, user_id)
        return None
    if not data.get("ok"):
        logger.warning("getChatMember error (channel=%s): %s", channel, data.get("description"))
        return None
    return data.get("result", {}).get("status")


async def resolve_channel_sub(
    pool, user_id: int, channels: set[str], *, force_refresh: bool = False,
) -> dict[str, bool]:
    """Возвращает {channel: is_member} для каждого канала из channels.
    force_refresh=True игнорирует кэш полностью (используется перед реальным
    участием в розыгрыше)."""
    if not channels:
        return {}
    now = datetime.now(timezone.utc)
    result: dict[str, bool] = {}
    stale: list[str] = list(channels)

    if not force_refresh:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT channel, is_member, checked_at FROM giveaway_channel_sub_cache "
                "WHERE user_id = $1 AND channel = ANY($2::text[])",
                user_id, list(channels),
            )
        cached = {r["channel"]: r for r in rows}
        stale = []
        for channel in channels:
            row = cached.get(channel)
            if row and _is_cache_fresh(row["checked_at"], now):
                result[channel] = bool(row["is_member"])
            else:
                stale.append(channel)

    if not stale:
        return result

    fresh_values: dict[str, bool] = {}
    for channel in stale:
        status = await _fetch_chat_member_status(channel, user_id)
        fresh_values[channel] = _is_member_status(status)
    result.update(fresh_values)

    async with pool.acquire() as conn:
        for channel, is_member in fresh_values.items():
            await conn.execute(
                """
                INSERT INTO giveaway_channel_sub_cache (user_id, channel, is_member, checked_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (user_id, channel) DO UPDATE
                    SET is_member = EXCLUDED.is_member, checked_at = EXCLUDED.checked_at
                """,
                user_id, channel, is_member,
            )
    return result
```

- [ ] **Step 8: Запустить тесты и убедиться, что они проходят**

Run: `cd server && python -m pytest tests/test_telegram_membership.py -v`
Expected: 6 passed

- [ ] **Step 9: Верифицировать импортируемость модуля**

Run: `cd server && python -m py_compile telegram_membership.py`
Expected: no output, exit code 0

- [ ] **Step 10: Добавить миграцию схемы**

В `server/schema.sql`, найти конец файла (текущая последняя строка, блок `giveaway_entries`):

```sql
CREATE TABLE IF NOT EXISTS giveaway_entries (
    giveaway_id INT NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (giveaway_id, user_id)
);
```

Добавить сразу после (в конец файла):

```sql

-- v3: новые типы условий участия — подписка на Telegram-канал и «пригласить
-- N друзей» (через уже существующий users.refferals). CHECK на giveaway_conditions.kind
-- создан инлайн через CREATE TABLE IF NOT EXISTS, поэтому на уже существующей
-- живой таблице его нужно пересоздать явно (DROP+ADD, а не EXISTS-гвардинг,
-- т.к. Postgres не поддерживает ADD CONSTRAINT IF NOT EXISTS для CHECK).
ALTER TABLE giveaway_conditions DROP CONSTRAINT IF EXISTS giveaway_conditions_kind_check;
ALTER TABLE giveaway_conditions ADD CONSTRAINT giveaway_conditions_kind_check
    CHECK (kind IN ('balance', 'harvest_count', 'item_count', 'channel_sub', 'referral_count'));

-- Кэш проверки подписки на канал (getChatMember), TTL проверяется в коде
-- (server/telegram_membership.py), не в схеме.
CREATE TABLE IF NOT EXISTS giveaway_channel_sub_cache (
    user_id BIGINT NOT NULL,
    channel TEXT NOT NULL,
    is_member BOOLEAN NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, channel)
);
```

- [ ] **Step 11: Верифицировать, что schema.sql всё ещё синтаксически валиден (smoke-check, не настоящий парсер)**

Run: `cd server && python -c "sql = open('schema.sql', encoding='utf-8').read(); assert 'giveaway_channel_sub_cache' in sql and 'channel_sub' in sql; print('OK')"`
Expected: prints `OK`

- [ ] **Step 12: Запустить весь бэкенд-набор тестов**

Run: `cd server && python -m pytest -v`
Expected: все тесты проходят (14 существующих из v1/v2 + 3 новых в test_giveaway_conditions.py + 6 новых в test_telegram_membership.py = 23 passed)

- [ ] **Step 13: Commit**

```bash
git add server/giveaway_conditions.py server/tests/test_giveaway_conditions.py server/telegram_membership.py server/tests/test_telegram_membership.py server/schema.sql
git commit -m "feat(giveaways): add channel_sub/referral_count condition checkers + membership cache schema"
```

---

### Task 2: `db.py` — referral_count в ctx, resolve_channel_sub во всех трёх местах чтения/участия

**Files:**
- Modify: `server/db.py`

**Interfaces:**
- Consumes: `condition_satisfied` (Task 1, `server/giveaway_conditions.py` — уже существовал, но раньше не импортировался в `db.py`), `resolve_channel_sub` (Task 1, `server/telegram_membership.py`).
- Produces: `_giveaway_condition_ctx(conn, user_id)` теперь включает `referral_count`. `get_giveaways_state`, `get_giveaway_detail`, `participate_in_giveaway` теперь резолвят `channel_sub` без удержания соединения из пула во время HTTP-вызова.

- [ ] **Step 1: Обновить импорты**

В `server/db.py` найти (строка 88):

```python
from giveaway_conditions import all_conditions_met
```

Заменить на:

```python
from giveaway_conditions import all_conditions_met, condition_satisfied
from telegram_membership import resolve_channel_sub
```

- [ ] **Step 2: Расширить `_giveaway_condition_ctx` полем `referral_count`**

Найти:

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
```

Заменить на:

```python
    async def _giveaway_condition_ctx(self, conn, user_id):
        row = await conn.fetchrow(
            "SELECT balance, harvest_count, items, refferals FROM users WHERE user_id = $1",
            user_id,
        )
        if not row:
            return {"balance": 0, "harvest_count": 0, "items": {}, "referral_count": 0}
        return {
            "balance": int(row["balance"] or 0),
            "harvest_count": int(row["harvest_count"] or 0),
            "items": parse_items(row["items"]),
            "referral_count": int(row["refferals"] or 0),
        }
```

(`refferals` — уже существующая колонка на этой же физической таблице `users`, используемая существующей реферальной механикой бота; здесь только читается, никогда не пишется.)

- [ ] **Step 3: Восстановить `get_giveaways_state` — разрешать channel_sub одним пакетным вызовом без удержания соединения**

Найти:

```python
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
                participants_count, participants_preview = await self._giveaway_participants(conn, row["id"])
                items.append({
                    "id": row["id"],
                    "title": row["title"],
                    "emoji": row["emoji"],
                    "rarity": row["rarity"],
                    "prize": self._giveaway_prize_summary(row),
                    "drawType": row["draw_type"],
                    "startsAt": row["starts_at"].isoformat() if row["starts_at"] else None,
                    "endsAt": row["ends_at"].isoformat() if row["ends_at"] else None,
                    "status": row["status"],
                    "conditionsCount": len(conditions),
                    "conditionsMet": conditions_met,
                    "joined": bool(row["joined"]),
                    "won": bool(row["winner_user_id"] == user_id) if row["winner_user_id"] else None,
                    "participantsCount": participants_count,
                    "participantsPreview": participants_preview,
                })
        return {"giveaways": items}
```

Заменить на:

```python
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
            rows_conditions = []
            channels = set()
            for row in rows:
                conditions = await self._giveaway_conditions(conn, row["id"])
                participants_count, participants_preview = await self._giveaway_participants(conn, row["id"])
                channels.update(c["item_id"] for c in conditions if c["kind"] == "channel_sub")
                rows_conditions.append((row, conditions, participants_count, participants_preview))
        # channel_sub требует HTTP-вызова к Telegram — резолвим одним пакетным
        # вызовом на все уникальные каналы этой пачки розыгрышей, уже без
        # открытого соединения из пула (см. server/telegram_membership.py).
        ctx["channel_sub"] = await resolve_channel_sub(self.pool, user_id, channels)

        items = []
        for row, conditions, participants_count, participants_preview in rows_conditions:
            conditions_met = all_conditions_met(ctx, conditions)
            items.append({
                "id": row["id"],
                "title": row["title"],
                "emoji": row["emoji"],
                "rarity": row["rarity"],
                "prize": self._giveaway_prize_summary(row),
                "drawType": row["draw_type"],
                "startsAt": row["starts_at"].isoformat() if row["starts_at"] else None,
                "endsAt": row["ends_at"].isoformat() if row["ends_at"] else None,
                "status": row["status"],
                "conditionsCount": len(conditions),
                "conditionsMet": conditions_met,
                "joined": bool(row["joined"]),
                "won": bool(row["winner_user_id"] == user_id) if row["winner_user_id"] else None,
                "participantsCount": participants_count,
                "participantsPreview": participants_preview,
            })
        return {"giveaways": items}
```

- [ ] **Step 4: Переписать `get_giveaway_detail` — резолвить channel_sub и переиспользовать `condition_satisfied`**

Найти:

```python
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
        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "emoji": row["emoji"],
            "rarity": row["rarity"],
            "prize": self._giveaway_prize_summary(row),
            "drawType": row["draw_type"],
            "startsAt": row["starts_at"].isoformat() if row["starts_at"] else None,
            "endsAt": row["ends_at"].isoformat() if row["ends_at"] else None,
            "status": row["status"],
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

        # channel_sub — вне блока conn: HTTP-вызов к Telegram не должен
        # держать соединение из пула открытым (см. server/telegram_membership.py).
        channels = {c["item_id"] for c in conditions if c["kind"] == "channel_sub"}
        ctx["channel_sub"] = await resolve_channel_sub(self.pool, user_id, channels)

        condition_progress = []
        for cond in conditions:
            if cond["kind"] == "balance":
                current = ctx["balance"]
            elif cond["kind"] == "harvest_count":
                current = ctx["harvest_count"]
            elif cond["kind"] == "item_count":
                current = ctx["items"].get(cond["item_id"], 0)
            elif cond["kind"] == "referral_count":
                current = ctx["referral_count"]
            else:
                current = None
            condition_progress.append({
                "kind": cond["kind"],
                "targetValue": cond["target_value"],
                "itemId": cond["item_id"],
                "current": current,
                "satisfied": condition_satisfied(ctx, cond),
            })
        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "emoji": row["emoji"],
            "rarity": row["rarity"],
            "prize": self._giveaway_prize_summary(row),
            "drawType": row["draw_type"],
            "startsAt": row["starts_at"].isoformat() if row["starts_at"] else None,
            "endsAt": row["ends_at"].isoformat() if row["ends_at"] else None,
            "status": row["status"],
            "conditions": condition_progress,
            "conditionsMet": all(c["satisfied"] for c in condition_progress),
            "joined": bool(joined),
            "result": result,
            "winnerName": winner_name,
            "recipientsCount": recipients_count,
        }
```

(Раньше `satisfied` вычислялось вручную (`current >= cond["target_value"]`) дублируя логику `giveaway_conditions.py` — теперь используется тот же `condition_satisfied(ctx, cond)`, что и в `all_conditions_met`, одна логика вместо двух параллельных. `current` для `channel_sub` остаётся `None` — это булево условие, числовой «прогресс» для него не имеет смысла; вебапп не будет ссылаться на `cond.current` для этого типа.)

- [ ] **Step 5: Переписать `participate_in_giveaway` — живая проверка channel_sub до открытия транзакции с блокировкой строки**

Найти:

```python
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
                if not row:
                    raise ValueError("Розыгрыш недоступен")

                already_joined = await conn.fetchval(
                    "SELECT 1 FROM giveaway_entries WHERE giveaway_id = $1 AND user_id = $2",
                    giveaway_id, user_id,
                )
                if not already_joined:
                    if row["status"] != "active" or not row["enabled"]:
                        raise ValueError("Розыгрыш недоступен")
                    if giveaway_bucket(row["status"], row["starts_at"], datetime.now(timezone.utc)) == "upcoming":
                        raise ValueError("Розыгрыш ещё не начался")

                    ctx = await self._giveaway_condition_ctx(conn, user_id)
                    conditions = await self._giveaway_conditions(conn, giveaway_id)
                    if not all_conditions_met(ctx, conditions):
                        raise ValueError("Не все условия выполнены")
```

Заменить на:

```python
    async def participate_in_giveaway(self, user_id, giveaway_id):
        # channel_sub — единственный тип условия с внешним HTTP-вызовом
        # (Telegram); проверяем его здесь, ДО открытия транзакции с
        # блокировкой строки — сетевой вызов никогда не должен идти под
        # FOR UPDATE или с удержанием соединения из пула. force_refresh=True:
        # перед реальным участием кэш полностью игнорируется, проверка живая
        # (условия читаются дважды — здесь и ещё раз под блокировкой ниже —
        # это осознанный компромисс: остальные условия (balance/harvest/item/
        # referral) остаются под тем же FOR UPDATE, что и раньше, без
        # изменений в их атомарности).
        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            conditions_preview = await self._giveaway_conditions(conn, giveaway_id)
        channels = {c["item_id"] for c in conditions_preview if c["kind"] == "channel_sub"}
        channel_sub_ctx = await resolve_channel_sub(self.pool, user_id, channels, force_refresh=True)

        # ВАЖНО: не вызывать self.get_giveaway_detail(...) (сам берёт соединение
        # из пула) пока ещё держим conn из self.pool.acquire() ниже — иначе на
        # секунду занимаем два соединения из пула одновременно. Поэтому ранний
        # выход при already_joined не return'ится изнутри "async with conn",
        # а просто ничего не делает внутри транзакции — единый return после
        # блока сам сходит за актуальным состоянием на уже свободном соединении.
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT * FROM giveaways WHERE id = $1 FOR UPDATE", giveaway_id
                )
                if not row:
                    raise ValueError("Розыгрыш недоступен")

                already_joined = await conn.fetchval(
                    "SELECT 1 FROM giveaway_entries WHERE giveaway_id = $1 AND user_id = $2",
                    giveaway_id, user_id,
                )
                if not already_joined:
                    if row["status"] != "active" or not row["enabled"]:
                        raise ValueError("Розыгрыш недоступен")
                    if giveaway_bucket(row["status"], row["starts_at"], datetime.now(timezone.utc)) == "upcoming":
                        raise ValueError("Розыгрыш ещё не начался")

                    ctx = await self._giveaway_condition_ctx(conn, user_id)
                    ctx["channel_sub"] = channel_sub_ctx
                    conditions = await self._giveaway_conditions(conn, giveaway_id)
                    if not all_conditions_met(ctx, conditions):
                        raise ValueError("Не все условия выполнены")
```

(Остальная часть функции — `INSERT INTO giveaway_entries`, начисление КУТ для `instant`, `log_game_event`, финальный `return await self.get_giveaway_detail(...)` — не меняется, оставить как есть.)

- [ ] **Step 6: Верифицировать компилируемость**

Run: `cd server && python -m py_compile db.py`
Expected: no output, exit code 0

- [ ] **Step 7: Ручной review-чеклист (нет живой БД в этом окружении)**

Подтвердить чтением диффа:
- `resolve_channel_sub` вызывается ВСЕГДА вне `async with self.pool.acquire() as conn:` блока (ни в одном из трёх мест не остаётся открытого соединения во время вызова) — проверить в каждом из `get_giveaways_state`, `get_giveaway_detail`, `participate_in_giveaway`.
- В `participate_in_giveaway` пре-чек условий (`conditions_preview`) и финальный чек (`conditions`) читают одну и ту же таблицу `giveaway_conditions` — двойное чтение осознанно принято (см. комментарий в коде), не является багом.
- `condition_satisfied` (из `giveaway_conditions.py`) используется в `get_giveaway_detail` вместо дублирующего вручную-написанного сравнения — устраняет параллельный дубль-диспетчер, который раньше был отмечен как технический долг.

- [ ] **Step 8: Запустить полный бэкенд-набор тестов**

Run: `cd server && python -m pytest -v`
Expected: 23 passed (без изменений от Task 1 — этот таск не добавляет новую чистую логику, только подключает уже протестированные хелперы к DB-коду, для которого нужна живая БД)

- [ ] **Step 9: Commit**

```bash
git add server/db.py
git commit -m "feat(giveaways): wire referral_count/channel_sub into condition ctx, list, detail, participate"
```

---

### Task 3: Админ-бэкенд — валидация новых типов условий

**Files:**
- Modify: `server/admin_giveaways.py`

**Interfaces:**
- Produces: `_validate_conditions([...])` теперь принимает `kind='channel_sub'` (требует непустой `item_id`, приводит `@username` к виду без `@`, форсирует `target_value=1`) и `kind='referral_count'` (уже работает через существующий generic `target_value`-путь, без изменений).

- [ ] **Step 1: Расширить `_VALID_CONDITION_KIND` и обработку `item_id` для `channel_sub`**

В `server/admin_giveaways.py` найти:

```python
_VALID_CONDITION_KIND = frozenset({"balance", "harvest_count", "item_count"})
```

Заменить на:

```python
_VALID_CONDITION_KIND = frozenset({
    "balance", "harvest_count", "item_count", "channel_sub", "referral_count",
})
```

Затем найти:

```python
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
```

Заменить на:

```python
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
        elif kind == "channel_sub":
            item_id = str(cond.get("item_id") or cond.get("itemId") or "").strip().lstrip("@")
            if not item_id:
                raise ValueError(f"Условие #{idx + 1}: укажите канал")
            target_value = 1
        cleaned.append({"kind": kind, "target_value": target_value, "item_id": item_id, "sort_order": idx})
    return cleaned
```

(`referral_count` не требует отдельной ветки — `target_value` уже обрабатывается общим путём выше, `item_id` остаётся `None` как и для `balance`/`harvest_count`.)

- [ ] **Step 2: Верифицировать компилируемость**

Run: `cd server && python -m py_compile admin_giveaways.py`
Expected: no output, exit code 0

- [ ] **Step 3: Запустить полный бэкенд-набор тестов**

Run: `cd server && python -m pytest -v`
Expected: 23 passed (без изменений — эта задача не добавляет новую чистую логику)

- [ ] **Step 4: Commit**

```bash
git add server/admin_giveaways.py
git commit -m "feat(giveaways): validate channel_sub/referral_count conditions on admin create/update"
```

---

### Task 4: Админ-панель — новые опции конструктора условий

**Files:**
- Modify: `admin/src/pages/sections/GiveawaysSection.jsx`

**Interfaces:**
- Consumes: ничего нового с бэкенда (Task 3 уже принимает `kind='channel_sub'`/`'referral_count'` через существующий `conditions` payload).
- Produces: изменения только в этом файле, ничего другого не потребляет.

- [ ] **Step 1: Добавить новые опции в `CONDITION_KIND_OPTIONS`**

В `admin/src/pages/sections/GiveawaysSection.jsx` найти:

```jsx
const CONDITION_KIND_OPTIONS = [
  { value: 'balance', label: 'Баланс КУТ ≥' },
  { value: 'harvest_count', label: 'Урожаев собрано ≥' },
  { value: 'item_count', label: 'Предмет в рюкзаке ≥' },
]
```

Заменить на:

```jsx
const CONDITION_KIND_OPTIONS = [
  { value: 'balance', label: 'Баланс КУТ ≥' },
  { value: 'harvest_count', label: 'Урожаев собрано ≥' },
  { value: 'item_count', label: 'Предмет в рюкзаке ≥' },
  { value: 'channel_sub', label: 'Подписка на Telegram-канал' },
  { value: 'referral_count', label: 'Пригласить друзей ≥' },
]
```

- [ ] **Step 2: Расширить условное поле `itemId` для `channel_sub` и скрыть числовое поле для него**

Найти:

```jsx
                  <input
                    className="panel-users-input"
                    type="number"
                    min={1}
                    value={cond.targetValue}
                    onChange={(e) => updateCondition(idx, { targetValue: e.target.value })}
                    style={{ width: 90 }}
                  />
                  {cond.kind === 'item_count' && (
                    <input
                      className="panel-users-input"
                      placeholder="id предмета"
                      value={cond.itemId}
                      onChange={(e) => updateCondition(idx, { itemId: e.target.value })}
                    />
                  )}
```

Заменить на:

```jsx
                  {cond.kind !== 'channel_sub' && (
                    <input
                      className="panel-users-input"
                      type="number"
                      min={1}
                      value={cond.targetValue}
                      onChange={(e) => updateCondition(idx, { targetValue: e.target.value })}
                      style={{ width: 90 }}
                    />
                  )}
                  {cond.kind === 'item_count' && (
                    <input
                      className="panel-users-input"
                      placeholder="id предмета"
                      value={cond.itemId}
                      onChange={(e) => updateCondition(idx, { itemId: e.target.value })}
                    />
                  )}
                  {cond.kind === 'channel_sub' && (
                    <input
                      className="panel-users-input"
                      placeholder="@username канала"
                      value={cond.itemId}
                      onChange={(e) => updateCondition(idx, { itemId: e.target.value })}
                    />
                  )}
```

- [ ] **Step 3: Форсировать `targetValue: 1` для `channel_sub` при сохранении**

Найти:

```jsx
        conditions: form.conditions.map((c) => ({
          kind: c.kind,
          targetValue: Number(c.targetValue),
          itemId: c.kind === 'item_count' ? c.itemId : null,
        })),
```

Заменить на:

```jsx
        conditions: form.conditions.map((c) => ({
          kind: c.kind,
          targetValue: c.kind === 'channel_sub' ? 1 : Number(c.targetValue),
          itemId: c.kind === 'item_count' || c.kind === 'channel_sub' ? c.itemId : null,
        })),
```

- [ ] **Step 4: Верифицировать сборку**

Run: `cd admin && npx vite build`
Expected: build succeeds, no errors

- [ ] **Step 5: Commit**

```bash
git add admin/src/pages/sections/GiveawaysSection.jsx
git commit -m "feat(admin): add channel_sub/referral_count condition options to giveaway form"
```

---

### Task 5: Вебапп — отображение условия и кнопка «Перейти» для новых типов

**Files:**
- Modify: `src/components/GiveawayDetailModal.jsx`

**Interfaces:**
- Consumes: `openTelegramBotLink(url)` из `src/lib/telegram.js:63` (уже существует — пробует `tg.openTelegramLink` → `tg.openLink` → `window.location.assign`), `getTelegramUser()` из `src/lib/telegram.js:24` (возвращает `{id, ...}` или `null`).
- Produces: изменения только в этом файле.

- [ ] **Step 1: Добавить импорты**

В `src/components/GiveawayDetailModal.jsx` найти:

```jsx
import { useEffect, useState } from 'react'
import Portal from './Portal'
import { fetchGiveaway } from '../lib/giveawaysClient'
import { RARITY_ACCENT, formatGiveawayDeadlineTime, formatGiveawayPrize } from '../constants/giveaways'
```

Заменить на:

```jsx
import { useEffect, useState } from 'react'
import Portal from './Portal'
import { fetchGiveaway } from '../lib/giveawaysClient'
import { RARITY_ACCENT, formatGiveawayDeadlineTime, formatGiveawayPrize } from '../constants/giveaways'
import { openTelegramBotLink, getTelegramUser } from '../lib/telegram'

const BOT_USERNAME = 'CuteGamingBot'
```

- [ ] **Step 2: Добавить подписи условий для новых типов**

Найти:

```jsx
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
```

Заменить на:

```jsx
const CONDITION_LABEL = {
  balance: (cond) => `Баланс: ${cond.current} из ${cond.targetValue} КУТ`,
  harvest_count: (cond) => `Урожаев собрано: ${cond.current} из ${cond.targetValue}`,
  item_count: (cond) => `Предмет «${cond.itemId}»: ${cond.current} из ${cond.targetValue}`,
  channel_sub: (cond) => `Подписка на @${cond.itemId}`,
  referral_count: (cond) => `Приглашено друзей: ${cond.current} из ${cond.targetValue}`,
}

const CONDITION_NAV_TARGET = {
  balance: 'trade',
  harvest_count: 'farm',
  item_count: 'farm-inventory',
}
```

(`CONDITION_NAV_TARGET` намеренно не расширяется — `channel_sub`/`referral_count` не используют внутреннюю навигацию по вкладкам, у них свой обработчик кнопки «Перейти», см. Step 3.)

- [ ] **Step 3: Особая логика кнопки «Перейти» для `channel_sub`/`referral_count`**

Найти:

```jsx
                        {!cond.satisfied && (
                          <button
                            type="button"
                            className="giveaway-detail-condition-goto"
                            onClick={() => onNavigateCondition(CONDITION_NAV_TARGET[cond.kind] ?? 'farm')}
                          >
                            Перейти
                          </button>
                        )}
```

Заменить на:

```jsx
                        {!cond.satisfied && cond.kind === 'channel_sub' && (
                          <button
                            type="button"
                            className="giveaway-detail-condition-goto"
                            onClick={() => openTelegramBotLink(`https://t.me/${cond.itemId}`)}
                          >
                            Перейти
                          </button>
                        )}
                        {!cond.satisfied && cond.kind === 'referral_count' && (
                          <button
                            type="button"
                            className="giveaway-detail-condition-goto"
                            onClick={() => {
                              const userId = getTelegramUser()?.id
                              if (!userId) return
                              const inviteLink = `https://t.me/${BOT_USERNAME}?start=${userId}`
                              openTelegramBotLink(`https://t.me/share/url?url=${encodeURIComponent(inviteLink)}`)
                            }}
                          >
                            Перейти
                          </button>
                        )}
                        {!cond.satisfied && cond.kind !== 'channel_sub' && cond.kind !== 'referral_count' && (
                          <button
                            type="button"
                            className="giveaway-detail-condition-goto"
                            onClick={() => onNavigateCondition(CONDITION_NAV_TARGET[cond.kind] ?? 'farm')}
                          >
                            Перейти
                          </button>
                        )}
```

- [ ] **Step 4: Верифицировать сборку**

Run: `npx vite build`
Expected: build succeeds, no errors

- [ ] **Step 5: Commit**

```bash
git add src/components/GiveawayDetailModal.jsx
git commit -m "feat(giveaways): show channel_sub/referral_count conditions with dedicated CTA"
```

---

### Task 6: Финальная верификация

**Files:** нет изменений — только проверка.

- [ ] **Step 1: Полный бэкенд-набор тестов**

Run: `cd server && python -m pytest -v`
Expected: 23 passed

- [ ] **Step 2: Сборка вебаппа и админки**

Run: `npx vite build && cd admin && npx vite build`
Expected: оба build succeed без ошибок

- [ ] **Step 3: Frontend unit-тесты (существующие, не должны сломаться)**

Run: `npx vitest run`
Expected: все существующие тесты проходят без изменений (эта задача не добавляет новых frontend unit-тестов — новая логика в `GiveawayDetailModal.jsx`/`GiveawaysSection.jsx` — презентационная, покрывается только py_compile/build/ручным review, как и остальной giveaways UI)

- [ ] **Step 4: Сквозной ручной review-чеклист (нет живой БД в этом окружении)**

Пройти по каждому пункту, читая финальный дифф всех задач:
- Админ создаёт розыгрыш с условием `channel_sub` (`@some_channel`) → `_validate_conditions` (Task 3) сохраняет `item_id='some_channel'` (без `@`), `target_value=1`.
- Игрок открывает список розыгрышей → `get_giveaways_state` (Task 2) собирает уникальные каналы по всей пачке, один пакетный вызов `resolve_channel_sub` (не по одному на розыгрыш).
- Игрок открывает детали розыгрыша с невыполненным `channel_sub` → видит подпись «Подписка на @some_channel» и кнопку «Перейти», открывающую сам канал.
- Игрок нажимает «Участвовать» → `participate_in_giveaway` (Task 2) делает живую (без кэша) проверку `channel_sub` до захвата блокировки строки — сетевой вызов никогда не идёт под `FOR UPDATE`.
- Условие `referral_count` использует `users.refferals` напрямую — ничего не проверяет во внешнем API, работает как `balance`/`harvest_count`.
- Ошибка Telegram API (таймаут/канал не найден) → `_fetch_chat_member_status` возвращает `None` → `_is_member_status(None)` → `False` → условие «не выполнено» (fail-closed), не бросает исключение и не ломает список/детали розыгрыша.

- [ ] **Step 5: Итоговый commit (если Step 4 выявил правки)**

Если ручной review не выявил проблем — коммитить нечего, задача завершена на Step 4. Если выявил — исправить и закоммитить с сообщением, описывающим конкретное исправление.
