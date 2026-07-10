# Cosmetic Loot Boxes — Backend Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the server-authoritative backend for cosmetic loot boxes ("chests"): data model, opening engine, shards-from-dupes, direct shard purchase, key granting, and the game HTTP API — with no frontend or admin UI yet.

**Architecture:** Hybrid model (spec §3). New relational tables hold cosmetics/sets/ownership/shards/box-catalog/opening-history/per-player-odds. Non-cosmetic rewards (KUT, seeds, functional items) flow into the existing `users.balance` / `users.items`. Pure roll logic lives in a small, unit-tested module (`chest_engine.py`); DB transactions and queries live in `chest_db.py`; routes are added to `app.py` following the existing `@app.post` + pydantic + `Depends(rate_limit)` pattern. Tables are created programmatically via an `ensure_tables()` function called from `app.py` lifespan, mirroring `support_db.py`, and also appended to `schema.sql` for the manual `psql` deploy path.

**Tech Stack:** Python 3.11, FastAPI 0.115, asyncpg 0.30, pydantic 2.10, PostgreSQL 15+. Tests: pytest (newly introduced for pure logic only — no DB fixtures).

## Global Constraints

- Randomness and reward granting happen **only on the server**; the client receives a resolved result (spec §6).
- Chest currency for MVP is **Telegram Stars via the existing donate-bot "key" model** — the backend never talks to Stars directly; it only grants/consumes `chest_key` (spec §4). Native Stars invoicing is out of scope.
- Keys are stored as a counter in existing `users.items['chest_key']` (spec §4, §5).
- Rarities are exactly `'common' | 'rare' | 'legendary'`; base weights 75 / 21 / 4 (spec §2, §6). Weights are **data**, read from `box_catalog.pool`, never hardcoded in logic.
- Shards are **one shared currency**, granted **only from duplicates** (spec §2, §4).
- Every open writes one row per chest to `box_openings` for audit (spec §6, §9).
- Follow existing code patterns: routes in `app.py`, DB ops delegated to a module, `ValueError` → `_client_error`, other `Exception` → `_server_error`.
- New tables use `CREATE TABLE IF NOT EXISTS` + `ALTER ... ADD COLUMN IF NOT EXISTS` (idempotent), mirroring `support_db.py` and `schema.sql`.
- All new code and DB identifiers in English; user-facing strings (none in this backend plan except error messages) match existing Russian error style.

---

### Task 1: Introduce pytest and the pure roll engine (`chest_engine.py`)

Pure, dependency-free roll logic. No DB, no FastAPI — fully unit-testable with a seeded `random.Random`.

**Files:**
- Create: `server/chest_engine.py`
- Create: `server/tests/__init__.py` (empty)
- Create: `server/tests/test_chest_engine.py`
- Modify: `server/requirements.txt` (append `pytest==8.3.4`)

**Interfaces:**
- Produces:
  - `RARITIES: tuple[str, ...]` == `("common", "rare", "legendary")`
  - `resolve_rarity_weights(base: dict[str, int], override: dict[str, int] | None) -> dict[str, int]` — returns `override` when it is a non-empty dict, else `base`.
  - `roll_rarity(weights: dict[str, int], rng: random.Random) -> str` — weighted pick of a rarity key.
  - `pick_item(items_by_rarity: dict[str, list[int]], rarity: str, rng: random.Random) -> int` — uniform pick of a cosmetic id within the rarity; raises `ValueError` if the rarity has no items.
  - `shard_for_dupe(rarity: str, shard_values: dict[str, int]) -> int` — shard count for a duplicate of the given rarity; `0` if rarity absent.

- [ ] **Step 1: Add pytest to requirements**

Append to `server/requirements.txt`:

```
pytest==8.3.4
```

- [ ] **Step 2: Write the failing tests**

Create `server/tests/__init__.py` empty, and `server/tests/test_chest_engine.py`:

```python
import random
import pytest
import chest_engine as ce


def test_rarities_exact():
    assert ce.RARITIES == ("common", "rare", "legendary")


def test_resolve_weights_uses_base_when_no_override():
    base = {"common": 75, "rare": 21, "legendary": 4}
    assert ce.resolve_rarity_weights(base, None) == base
    assert ce.resolve_rarity_weights(base, {}) == base


def test_resolve_weights_uses_override_when_present():
    base = {"common": 75, "rare": 21, "legendary": 4}
    override = {"common": 0, "rare": 0, "legendary": 100}
    assert ce.resolve_rarity_weights(base, override) == override


def test_roll_rarity_is_deterministic_with_seed():
    weights = {"common": 75, "rare": 21, "legendary": 4}
    rng = random.Random(42)
    seq = [ce.roll_rarity(weights, rng) for _ in range(5)]
    rng2 = random.Random(42)
    seq2 = [ce.roll_rarity(weights, rng2) for _ in range(5)]
    assert seq == seq2
    assert all(r in ce.RARITIES for r in seq)


def test_roll_rarity_respects_dominant_weight():
    weights = {"common": 0, "rare": 0, "legendary": 100}
    rng = random.Random(1)
    assert all(ce.roll_rarity(weights, rng) == "legendary" for _ in range(50))


def test_roll_rarity_distribution_roughly_matches():
    weights = {"common": 75, "rare": 21, "legendary": 4}
    rng = random.Random(7)
    counts = {"common": 0, "rare": 0, "legendary": 0}
    for _ in range(10000):
        counts[ce.roll_rarity(weights, rng)] += 1
    assert 0.70 < counts["common"] / 10000 < 0.80
    assert 0.17 < counts["rare"] / 10000 < 0.25
    assert 0.02 < counts["legendary"] / 10000 < 0.06


def test_pick_item_uniform_within_rarity():
    items = {"common": [1, 2, 3], "rare": [10], "legendary": []}
    rng = random.Random(0)
    assert ce.pick_item(items, "rare", rng) == 10
    picks = {ce.pick_item(items, "common", rng) for _ in range(50)}
    assert picks == {1, 2, 3}


def test_pick_item_empty_rarity_raises():
    with pytest.raises(ValueError):
        ce.pick_item({"legendary": []}, "legendary", random.Random(0))


def test_shard_for_dupe():
    values = {"common": 5, "rare": 25, "legendary": 150}
    assert ce.shard_for_dupe("common", values) == 5
    assert ce.shard_for_dupe("legendary", values) == 150
    assert ce.shard_for_dupe("mythic", values) == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run (from `server/`, with the venv active):

```bash
cd server && python -m pytest tests/test_chest_engine.py -v
```

Expected: FAIL / collection error — `ModuleNotFoundError: No module named 'chest_engine'`.

- [ ] **Step 4: Implement `chest_engine.py`**

Create `server/chest_engine.py`:

```python
"""Чистая логика розыгрыша сундуков. Без БД и FastAPI — юнит-тестируемо.

Все веса — данные (из box_catalog.pool), сюда приходят готовыми словарями.
rng передаётся снаружи, чтобы тесты были детерминированными.
"""
from __future__ import annotations

import random

RARITIES: tuple[str, ...] = ("common", "rare", "legendary")


def resolve_rarity_weights(
    base: dict[str, int], override: dict[str, int] | None
) -> dict[str, int]:
    """Пер-игроковый override имеет приоритет, если он непустой словарь."""
    if override:
        return override
    return base


def roll_rarity(weights: dict[str, int], rng: random.Random) -> str:
    """Взвешенный выбор редкости. Веса — целые, сумма > 0."""
    total = sum(max(0, int(w)) for w in weights.values())
    if total <= 0:
        raise ValueError("rarity weights sum to zero")
    threshold = rng.uniform(0, total)
    upto = 0.0
    for rarity in RARITIES:
        w = max(0, int(weights.get(rarity, 0)))
        upto += w
        if threshold <= upto:
            return rarity
    # На случай погрешности float — вернуть последнюю ненулевую редкость.
    for rarity in reversed(RARITIES):
        if int(weights.get(rarity, 0)) > 0:
            return rarity
    raise ValueError("no positive-weight rarity")


def pick_item(
    items_by_rarity: dict[str, list[int]], rarity: str, rng: random.Random
) -> int:
    """Равновероятный выбор предмета внутри редкости."""
    pool = items_by_rarity.get(rarity) or []
    if not pool:
        raise ValueError(f"no items for rarity {rarity!r}")
    return pool[rng.randrange(len(pool))]


def shard_for_dupe(rarity: str, shard_values: dict[str, int]) -> int:
    """Сколько осколков даёт дубль данной редкости."""
    return int(shard_values.get(rarity, 0))
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd server && python -m pytest tests/test_chest_engine.py -v
```

Expected: PASS (9 tests).

- [ ] **Step 6: Commit**

```bash
git add server/chest_engine.py server/tests/__init__.py server/tests/test_chest_engine.py server/requirements.txt
git commit -m "feat(chests): pure roll engine + pytest"
```

---

### Task 2: Tables and default catalog seed (`chest_db.py` DDL + `ensure_tables`)

Create all tables and seed a default box + a starter set of cosmetics so the API has data to return. Mirror `support_db.py` structure.

**Files:**
- Create: `server/chest_db.py` (DDL + `ensure_tables` + `seed_defaults` only in this task)
- Modify: `server/app.py` (call `ensure_tables` in lifespan, ~after line 192)
- Modify: `server/schema.sql` (append the same table DDL for the manual psql path)

**Interfaces:**
- Consumes: `from db import db` (global pool, `db.pool.acquire()`), same as `support_db.py`.
- Produces:
  - `async def ensure_tables() -> None` — creates tables + runs `seed_defaults`.
  - Table shapes exactly as in spec §5.
  - Default box code constant `DEFAULT_BOX_CODE = "cosmetic_box"`.

- [ ] **Step 1: Write `chest_db.py` with DDL, seed, and ensure_tables**

Create `server/chest_db.py`:

```python
"""DB-слой косметических сундуков: таблицы, розыгрыш, осколки, ключи, коллекция.

Косметика/сундуки — свои таблицы. Не-косметические награды (КУТ/предметы)
льются в users.balance / users.items через существующий код.
"""
from __future__ import annotations

import json
import logging
import random

from db import db
from user_items import parse_items, items_to_db, add_item

logger = logging.getLogger("cute-farm.chest-db")

DEFAULT_BOX_CODE = "cosmetic_box"
CHEST_KEY_ITEM = "chest_key"

# Курсы и веса по умолчанию (правятся потом из админки, План 3).
DEFAULT_RARITY_WEIGHTS = {"common": 75, "rare": 21, "legendary": 4}
DEFAULT_SHARD_VALUES = {"common": 5, "rare": 25, "legendary": 150}

_DDL = [
    """CREATE TABLE IF NOT EXISTS cosmetic_items (
        id          SERIAL PRIMARY KEY,
        code        TEXT NOT NULL UNIQUE,
        name        TEXT NOT NULL DEFAULT '',
        emoji       TEXT NOT NULL DEFAULT '📦',
        slot        TEXT NOT NULL,
        rarity      TEXT NOT NULL,
        set_code    TEXT,
        shard_cost  INT NOT NULL DEFAULT 0,
        active      BOOLEAN NOT NULL DEFAULT TRUE
    )""",
    "CREATE INDEX IF NOT EXISTS idx_cosmetic_items_active ON cosmetic_items (active, rarity)",
    """CREATE TABLE IF NOT EXISTS cosmetic_sets (
        code          TEXT PRIMARY KEY,
        name          TEXT NOT NULL DEFAULT '',
        reward_type   TEXT NOT NULL DEFAULT 'title',
        reward_value  TEXT NOT NULL DEFAULT '',
        active        BOOLEAN NOT NULL DEFAULT TRUE
    )""",
    """CREATE TABLE IF NOT EXISTS user_cosmetics (
        user_id      BIGINT NOT NULL,
        cosmetic_id  INT NOT NULL REFERENCES cosmetic_items(id) ON DELETE CASCADE,
        obtained_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        equipped     BOOLEAN NOT NULL DEFAULT FALSE,
        PRIMARY KEY (user_id, cosmetic_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_user_cosmetics_uid ON user_cosmetics (user_id)",
    """CREATE TABLE IF NOT EXISTS user_shards (
        user_id  BIGINT PRIMARY KEY,
        balance  INT NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS box_catalog (
        code         TEXT PRIMARY KEY,
        name         TEXT NOT NULL DEFAULT '',
        price_stars  INT NOT NULL DEFAULT 25,
        pool         JSONB NOT NULL DEFAULT '{}'::jsonb,
        active       BOOLEAN NOT NULL DEFAULT TRUE,
        starts_at    TIMESTAMPTZ,
        ends_at      TIMESTAMPTZ
    )""",
    """CREATE TABLE IF NOT EXISTS box_openings (
        id                BIGSERIAL PRIMARY KEY,
        user_id           BIGINT NOT NULL,
        box_code          TEXT NOT NULL,
        cosmetic_id       INT,
        reward_kind       TEXT NOT NULL,
        reward_ref        TEXT,
        rarity            TEXT,
        was_dupe          BOOLEAN NOT NULL DEFAULT FALSE,
        shards_granted    INT NOT NULL DEFAULT 0,
        keys_spent        INT NOT NULL DEFAULT 1,
        override_applied  BOOLEAN NOT NULL DEFAULT FALSE,
        opened_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_box_openings_feed ON box_openings (opened_at DESC) WHERE rarity IN ('rare','legendary')",
    "CREATE INDEX IF NOT EXISTS idx_box_openings_uid ON box_openings (user_id, opened_at DESC)",
    """CREATE TABLE IF NOT EXISTS player_chest_odds (
        user_id     BIGINT PRIMARY KEY,
        weights     JSONB NOT NULL DEFAULT '{}'::jsonb,
        note        TEXT,
        set_by      BIGINT,
        expires_at  TIMESTAMPTZ,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
]

# Стартовый контент, чтобы API было что отдавать. ON CONFLICT DO NOTHING —
# идемпотентно, не перетирает изменённое из админки.
_SEED_SETS = [
    ("spring", "🌸 Весенняя серия", "frame", "Цветущий"),
    ("pets", "🐉 Мифические питомцы", "title", "Укротитель"),
]

# (code, name, emoji, slot, rarity, set_code, shard_cost)
_SEED_ITEMS = [
    ("spring_flower", "Весенний цветок", "🌸", "background", "rare", "spring", 40),
    ("spring_tulip", "Тюльпан", "🌷", "plot", "common", "spring", 10),
    ("spring_sun", "Подсолнух", "🌻", "plot", "common", "spring", 10),
    ("spring_bfly", "Бабочка-фея", "🦋", "pet", "rare", "spring", 40),
    ("pet_dragon", "Дракон-хранитель", "🐉", "pet", "legendary", "pets", 150),
    ("pet_unicorn", "Единорог", "🦄", "pet", "legendary", "pets", 150),
    ("pet_wyrm", "Виверна", "🐲", "pet", "legendary", "pets", 150),
    ("frame_vine", "Рамка «Лоза»", "🌿", "frame", "common", None, 10),
    ("bg_sunset", "Фон «Закат»", "🌅", "background", "rare", None, 40),
]


async def ensure_tables() -> None:
    """Создаёт таблицы если их нет и засевает дефолтный контент. Из lifespan."""
    async with db.pool.acquire() as conn:
        for stmt in _DDL:
            await conn.execute(stmt)
        await _seed_defaults(conn)
    logger.info("Chest tables OK")


async def _seed_defaults(conn) -> None:
    for code, name, rtype, rval in _SEED_SETS:
        await conn.execute(
            """INSERT INTO cosmetic_sets (code, name, reward_type, reward_value)
               VALUES ($1,$2,$3,$4) ON CONFLICT (code) DO NOTHING""",
            code, name, rtype, rval,
        )
    for code, name, emoji, slot, rarity, set_code, shard_cost in _SEED_ITEMS:
        await conn.execute(
            """INSERT INTO cosmetic_items
               (code, name, emoji, slot, rarity, set_code, shard_cost)
               VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (code) DO NOTHING""",
            code, name, emoji, slot, rarity, set_code, shard_cost,
        )
    await conn.execute(
        """INSERT INTO box_catalog (code, name, price_stars, pool, active)
           VALUES ($1,$2,$3,$4,TRUE) ON CONFLICT (code) DO NOTHING""",
        DEFAULT_BOX_CODE,
        "Косметический сундук",
        25,
        json.dumps({"rarity_weights": DEFAULT_RARITY_WEIGHTS,
                    "shard_values": DEFAULT_SHARD_VALUES}),
    )
```

- [ ] **Step 2: Call `ensure_tables` in the lifespan**

In `server/app.py`, right after the support-tables block (currently ends at line 192), add:

```python
    from chest_db import ensure_tables as ensure_chest_tables
    try:
        await ensure_chest_tables()
    except Exception:
        logger.warning("Chest tables init failed — check DB permissions")
```

- [ ] **Step 3: Append the same DDL to `schema.sql`**

At the end of `server/schema.sql`, append the seven `CREATE TABLE IF NOT EXISTS` statements and their indexes from `_DDL` above (copy them verbatim, one after another, as plain SQL). This keeps the manual `psql -f server/schema.sql` deploy path complete. Do **not** add the seed INSERTs here (seeding stays in Python `ensure_tables`).

- [ ] **Step 4: Verify tables are created and seeded**

Start the server (from repo root: `server/.venv/Scripts/activate` then `python server/app.py`, or the usual `start-1-server.bat`). Watch the log for `Chest tables OK`. Then query:

```bash
psql "$DATABASE_URL" -c "SELECT code, rarity, slot FROM cosmetic_items ORDER BY id;"
psql "$DATABASE_URL" -c "SELECT code, price_stars, pool FROM box_catalog;"
```

Expected: 9 cosmetic rows, 1 box row with `price_stars = 25` and a `pool` JSON containing `rarity_weights` and `shard_values`.

- [ ] **Step 5: Commit**

```bash
git add server/chest_db.py server/app.py server/schema.sql
git commit -m "feat(chests): tables, default catalog seed, lifespan init"
```

---

### Task 3: Chest state + key granting (`chest_db.py`)

Read-side state for the client (keys, shards, box price, published chances) and the key-grant entry point the donate bot will call.

**Files:**
- Modify: `server/chest_db.py` (add functions)

**Interfaces:**
- Consumes: tables from Task 2; `parse_items`, `items_to_db`, `add_item` from `user_items`.
- Produces:
  - `async def get_chest_state(user_id: int) -> dict` — returns
    `{"keys": int, "shards": int, "box": {"code","name","priceStars"}, "chances": {"common": float, "rare": float, "legendary": float}}`.
    `chances` are the **published, base** percentages from `box_catalog.pool.rarity_weights` (never the per-player override — spec §9).
  - `async def grant_keys(user_id: int, count: int) -> int` — adds `count` to `users.items['chest_key']`, returns the new key total. `count` must be a positive int, else `ValueError`.
  - `async def _get_keys(conn, user_id: int) -> int` — helper reading the counter.

- [ ] **Step 1: Add helpers and read/grant functions to `chest_db.py`**

Append to `server/chest_db.py`:

```python
def _weights_to_percent(weights: dict[str, int]) -> dict[str, float]:
    total = sum(max(0, int(w)) for w in weights.values()) or 1
    return {r: round(100 * max(0, int(weights.get(r, 0))) / total, 2)
            for r in ("common", "rare", "legendary")}


async def _get_keys(conn, user_id: int) -> int:
    row = await conn.fetchrow("SELECT items FROM users WHERE user_id=$1", user_id)
    if not row:
        return 0
    return int(parse_items(row["items"]).get(CHEST_KEY_ITEM, 0))


async def _load_box(conn, code: str) -> dict:
    row = await conn.fetchrow(
        "SELECT code, name, price_stars, pool FROM box_catalog WHERE code=$1 AND active", code)
    if not row:
        raise ValueError("Сундук недоступен")
    pool = row["pool"] if isinstance(row["pool"], dict) else json.loads(row["pool"] or "{}")
    return {
        "code": row["code"],
        "name": row["name"],
        "priceStars": int(row["price_stars"]),
        "rarity_weights": pool.get("rarity_weights", DEFAULT_RARITY_WEIGHTS),
        "shard_values": pool.get("shard_values", DEFAULT_SHARD_VALUES),
    }


async def get_chest_state(user_id: int) -> dict:
    async with db.pool.acquire() as conn:
        box = await _load_box(conn, DEFAULT_BOX_CODE)
        keys = await _get_keys(conn, user_id)
        shard_row = await conn.fetchrow(
            "SELECT balance FROM user_shards WHERE user_id=$1", user_id)
        shards = int(shard_row["balance"]) if shard_row else 0
    return {
        "keys": keys,
        "shards": shards,
        "box": {"code": box["code"], "name": box["name"], "priceStars": box["priceStars"]},
        "chances": _weights_to_percent(box["rarity_weights"]),
    }


async def grant_keys(user_id: int, count: int) -> int:
    if not isinstance(count, int) or count <= 0:
        raise ValueError("count must be a positive integer")
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)
            row = await conn.fetchrow(
                "SELECT items FROM users WHERE user_id=$1 FOR UPDATE", user_id)
            items = parse_items(row["items"])
            items = add_item(items, CHEST_KEY_ITEM, count)
            await conn.execute(
                "UPDATE users SET items=$2 WHERE user_id=$1", user_id, items_to_db(items))
            return int(items.get(CHEST_KEY_ITEM, 0))
```

- [ ] **Step 2: Verify with a manual grant + state read**

Use a Python REPL against the running DB, or a scratch script `server/_scratch_chest.py`:

```python
import asyncio, db, chest_db
async def main():
    await db.db.connect()
    print("granted total:", await chest_db.grant_keys(999001, 3))
    print("state:", await chest_db.get_chest_state(999001))
    await db.db.close()
asyncio.run(main())
```

Run: `cd server && python _scratch_chest.py`
Expected: `granted total: 3` and a state dict with `keys: 3`, `shards: 0`, `box.priceStars: 25`, `chances` ≈ `{common: 75.0, rare: 21.0, legendary: 4.0}`. Delete the scratch file after.

- [ ] **Step 3: Commit**

```bash
git add server/chest_db.py
git commit -m "feat(chests): chest state read + key granting"
```

---

### Task 4: The opening transaction (`chest_db.py`)

The core server-authoritative open. One transaction, `FOR UPDATE` on the player, keys checked/deducted, per-chest roll (with per-player override), dupe→shards, cosmetic ownership insert, audit rows.

**Files:**
- Modify: `server/chest_db.py` (add `open_chests`)

**Interfaces:**
- Consumes: `chest_engine.resolve_rarity_weights`, `roll_rarity`, `pick_item`, `shard_for_dupe`; helpers from Task 3.
- Produces:
  - `async def open_chests(user_id: int, count: int) -> dict` — returns
    `{"results": [ {"cosmeticId": int, "code": str, "name": str, "emoji": str, "rarity": str, "slot": str, "wasDupe": bool, "shardsGranted": int} ... ], "keys": int, "shards": int}`.
  - Raises `ValueError("Недостаточно ключей")` if `keys < count`; `ValueError` if `count` not in `1..10`.

- [ ] **Step 1: Add `open_chests` to `chest_db.py`**

Append to `server/chest_db.py` (add `import chest_engine as ce` at the top with the other imports):

```python
MAX_OPEN_AT_ONCE = 10


async def _load_items_by_rarity(conn) -> tuple[dict[str, list[int]], dict[int, dict]]:
    rows = await conn.fetch(
        "SELECT id, code, name, emoji, slot, rarity FROM cosmetic_items WHERE active")
    by_rarity: dict[str, list[int]] = {"common": [], "rare": [], "legendary": []}
    meta: dict[int, dict] = {}
    for r in rows:
        by_rarity.setdefault(r["rarity"], []).append(r["id"])
        meta[r["id"]] = dict(r)
    return by_rarity, meta


async def _active_override(conn, user_id: int) -> dict | None:
    row = await conn.fetchrow(
        """SELECT weights FROM player_chest_odds
           WHERE user_id=$1 AND (expires_at IS NULL OR expires_at > NOW())""",
        user_id)
    if not row:
        return None
    w = row["weights"] if isinstance(row["weights"], dict) else json.loads(row["weights"] or "{}")
    return w or None


async def open_chests(user_id: int, count: int) -> dict:
    if not isinstance(count, int) or count < 1 or count > MAX_OPEN_AT_ONCE:
        raise ValueError(f"count must be 1..{MAX_OPEN_AT_ONCE}")
    rng = random.Random()
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            urow = await conn.fetchrow(
                "SELECT items FROM users WHERE user_id=$1 FOR UPDATE", user_id)
            if urow is None:
                raise ValueError("Недостаточно ключей")
            items = parse_items(urow["items"])
            keys = int(items.get(CHEST_KEY_ITEM, 0))
            if keys < count:
                raise ValueError("Недостаточно ключей")

            box = await _load_box(conn, DEFAULT_BOX_CODE)
            by_rarity, meta = await _load_items_by_rarity(conn)
            override = await _active_override(conn, user_id)
            weights = ce.resolve_rarity_weights(box["rarity_weights"], override)

            # владение (для определения дублей в рамках одной пачки тоже)
            owned_rows = await conn.fetch(
                "SELECT cosmetic_id FROM user_cosmetics WHERE user_id=$1", user_id)
            owned = {r["cosmetic_id"] for r in owned_rows}

            results = []
            shards_total_delta = 0
            for _ in range(count):
                rarity = ce.roll_rarity(weights, rng)
                if not by_rarity.get(rarity):
                    # редкость без предметов — деградируем к common, чтобы не падать
                    rarity = "common"
                cid = ce.pick_item(by_rarity, rarity, rng)
                m = meta[cid]
                was_dupe = cid in owned
                shards_granted = 0
                if was_dupe:
                    shards_granted = ce.shard_for_dupe(rarity, box["shard_values"])
                    shards_total_delta += shards_granted
                else:
                    owned.add(cid)
                    await conn.execute(
                        """INSERT INTO user_cosmetics (user_id, cosmetic_id)
                           VALUES ($1,$2) ON CONFLICT DO NOTHING""",
                        user_id, cid)
                await conn.execute(
                    """INSERT INTO box_openings
                       (user_id, box_code, cosmetic_id, reward_kind, reward_ref,
                        rarity, was_dupe, shards_granted, keys_spent, override_applied)
                       VALUES ($1,$2,$3,'cosmetic',$4,$5,$6,$7,1,$8)""",
                    user_id, box["code"], cid, m["code"], rarity,
                    was_dupe, shards_granted, override is not None)
                results.append({
                    "cosmeticId": cid, "code": m["code"], "name": m["name"],
                    "emoji": m["emoji"], "rarity": rarity, "slot": m["slot"],
                    "wasDupe": was_dupe, "shardsGranted": shards_granted,
                })

            # списать ключи
            items = add_item(items, CHEST_KEY_ITEM, -count)
            await conn.execute(
                "UPDATE users SET items=$2 WHERE user_id=$1", user_id, items_to_db(items))
            new_keys = int(items.get(CHEST_KEY_ITEM, 0))

            # начислить осколки
            if shards_total_delta:
                await conn.execute(
                    """INSERT INTO user_shards (user_id, balance) VALUES ($1,$2)
                       ON CONFLICT (user_id) DO UPDATE SET balance = user_shards.balance + $2""",
                    user_id, shards_total_delta)
            srow = await conn.fetchrow(
                "SELECT balance FROM user_shards WHERE user_id=$1", user_id)
            new_shards = int(srow["balance"]) if srow else 0

    return {"results": results, "keys": new_keys, "shards": new_shards}
```

- [ ] **Step 2: Verify end-to-end with a scratch script**

`server/_scratch_open.py`:

```python
import asyncio, db, chest_db
async def main():
    await db.db.connect()
    await chest_db.grant_keys(999002, 5)
    out = await chest_db.open_chests(999002, 5)
    print("keys left:", out["keys"], "shards:", out["shards"])
    for r in out["results"]:
        print(r["rarity"], r["name"], "DUPE" if r["wasDupe"] else "NEW",
              "+shards", r["shardsGranted"])
    try:
        await chest_db.open_chests(999002, 1)  # keys should be 0 now
    except ValueError as e:
        print("expected error:", e)
    await db.db.close()
asyncio.run(main())
```

Run: `cd server && python _scratch_open.py`
Expected: `keys left: 0`, 5 result lines (rarities from the pool; some may be DUPE with +shards on repeats), then `expected error: Недостаточно ключей`. Confirm audit rows:

```bash
psql "$DATABASE_URL" -c "SELECT rarity, was_dupe, shards_granted, override_applied FROM box_openings WHERE user_id=999002 ORDER BY id;"
```

Expected: 5 rows. Delete the scratch file after.

- [ ] **Step 3: Commit**

```bash
git add server/chest_db.py
git commit -m "feat(chests): server-authoritative open transaction"
```

---

### Task 5: Collection, shard purchase, equip (`chest_db.py`)

Read the album (owned + locked with prices, grouped by set with progress) and let the player buy a locked cosmetic with shards and equip/unequip within a slot.

**Files:**
- Modify: `server/chest_db.py`

**Interfaces:**
- Produces:
  - `async def get_collection(user_id: int) -> dict` — `{"shards": int, "sets": [ {"code","name","rewardType","rewardValue","owned":int,"total":int,"items":[{"cosmeticId","code","name","emoji","slot","rarity","owned":bool,"equipped":bool,"shardCost":int}]} ], "loose": [ ...same item shape, for items with no set... ]}`.
  - `async def buy_cosmetic_with_shards(user_id: int, cosmetic_id: int) -> dict` — `{"shards": int, "cosmeticId": int}`; raises `ValueError` if already owned / not found / not enough shards.
  - `async def set_equipped(user_id: int, cosmetic_id: int, equipped: bool) -> dict` — `{"cosmeticId","slot","equipped"}`; enforces one-equipped-per-slot; raises `ValueError` if not owned.

- [ ] **Step 1: Add the three functions to `chest_db.py`**

Append to `server/chest_db.py`:

```python
def _item_public(row, owned: bool, equipped: bool) -> dict:
    return {
        "cosmeticId": row["id"], "code": row["code"], "name": row["name"],
        "emoji": row["emoji"], "slot": row["slot"], "rarity": row["rarity"],
        "owned": owned, "equipped": equipped, "shardCost": int(row["shard_cost"]),
    }


async def get_collection(user_id: int) -> dict:
    async with db.pool.acquire() as conn:
        items = await conn.fetch(
            """SELECT id, code, name, emoji, slot, rarity, set_code, shard_cost
               FROM cosmetic_items WHERE active ORDER BY set_code NULLS LAST, id""")
        owned_rows = await conn.fetch(
            "SELECT cosmetic_id, equipped FROM user_cosmetics WHERE user_id=$1", user_id)
        owned = {r["cosmetic_id"]: r["equipped"] for r in owned_rows}
        set_rows = await conn.fetch(
            "SELECT code, name, reward_type, reward_value FROM cosmetic_sets WHERE active")
        srow = await conn.fetchrow("SELECT balance FROM user_shards WHERE user_id=$1", user_id)
        shards = int(srow["balance"]) if srow else 0

    set_meta = {r["code"]: r for r in set_rows}
    sets: dict[str, dict] = {}
    loose: list[dict] = []
    for it in items:
        pub = _item_public(it, it["id"] in owned, bool(owned.get(it["id"], False)))
        sc = it["set_code"]
        if sc and sc in set_meta:
            bucket = sets.setdefault(sc, {
                "code": sc, "name": set_meta[sc]["name"],
                "rewardType": set_meta[sc]["reward_type"],
                "rewardValue": set_meta[sc]["reward_value"],
                "owned": 0, "total": 0, "items": []})
            bucket["items"].append(pub)
            bucket["total"] += 1
            if pub["owned"]:
                bucket["owned"] += 1
        else:
            loose.append(pub)
    return {"shards": shards, "sets": list(sets.values()), "loose": loose}


async def buy_cosmetic_with_shards(user_id: int, cosmetic_id: int) -> dict:
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            item = await conn.fetchrow(
                "SELECT id, shard_cost FROM cosmetic_items WHERE id=$1 AND active", cosmetic_id)
            if not item:
                raise ValueError("Предмет не найден")
            already = await conn.fetchrow(
                "SELECT 1 FROM user_cosmetics WHERE user_id=$1 AND cosmetic_id=$2",
                user_id, cosmetic_id)
            if already:
                raise ValueError("Уже в коллекции")
            srow = await conn.fetchrow(
                "SELECT balance FROM user_shards WHERE user_id=$1 FOR UPDATE", user_id)
            balance = int(srow["balance"]) if srow else 0
            cost = int(item["shard_cost"])
            if balance < cost:
                raise ValueError("Недостаточно осколков")
            await conn.execute(
                """INSERT INTO user_shards (user_id, balance) VALUES ($1, -$2)
                   ON CONFLICT (user_id) DO UPDATE SET balance = user_shards.balance - $2""",
                user_id, cost)
            await conn.execute(
                "INSERT INTO user_cosmetics (user_id, cosmetic_id) VALUES ($1,$2)",
                user_id, cosmetic_id)
            new_row = await conn.fetchrow(
                "SELECT balance FROM user_shards WHERE user_id=$1", user_id)
    return {"shards": int(new_row["balance"]), "cosmeticId": cosmetic_id}


async def set_equipped(user_id: int, cosmetic_id: int, equipped: bool) -> dict:
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            item = await conn.fetchrow(
                """SELECT ci.slot FROM user_cosmetics uc
                   JOIN cosmetic_items ci ON ci.id = uc.cosmetic_id
                   WHERE uc.user_id=$1 AND uc.cosmetic_id=$2""",
                user_id, cosmetic_id)
            if not item:
                raise ValueError("Нет в коллекции")
            slot = item["slot"]
            if equipped:
                # снять всё в этом слоте, затем надеть выбранное
                await conn.execute(
                    """UPDATE user_cosmetics uc SET equipped=FALSE
                       FROM cosmetic_items ci
                       WHERE uc.cosmetic_id=ci.id AND uc.user_id=$1 AND ci.slot=$2""",
                    user_id, slot)
            await conn.execute(
                "UPDATE user_cosmetics SET equipped=$3 WHERE user_id=$1 AND cosmetic_id=$2",
                user_id, cosmetic_id, equipped)
    return {"cosmeticId": cosmetic_id, "slot": slot, "equipped": equipped}
```

- [ ] **Step 2: Verify collection + buy + equip**

`server/_scratch_coll.py`:

```python
import asyncio, db, chest_db
async def main():
    await db.db.connect()
    uid = 999003
    # дать осколков напрямую для теста покупки
    async with db.db.pool.acquire() as c:
        await c.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", uid)
        await c.execute("""INSERT INTO user_shards (user_id,balance) VALUES ($1,200)
                           ON CONFLICT (user_id) DO UPDATE SET balance=200""", uid)
    coll = await chest_db.get_collection(uid)
    first = coll["sets"][0]["items"][0]
    print("buy:", await chest_db.buy_cosmetic_with_shards(uid, first["cosmeticId"]))
    print("equip:", await chest_db.set_equipped(uid, first["cosmeticId"], True))
    try:
        await chest_db.buy_cosmetic_with_shards(uid, first["cosmeticId"])
    except ValueError as e:
        print("expected:", e)
    await db.db.close()
asyncio.run(main())
```

Run: `cd server && python _scratch_coll.py`
Expected: `buy` shows shards reduced by the item's cost; `equip` shows `equipped: True`; `expected: Уже в коллекции`. Delete scratch after.

- [ ] **Step 3: Commit**

```bash
git add server/chest_db.py
git commit -m "feat(chests): collection, shard purchase, equip"
```

---

### Task 6: Live drop feed (`chest_db.py`)

Recent rare/legendary drops with player display name, for the feed UI.

**Files:**
- Modify: `server/chest_db.py`

**Interfaces:**
- Produces:
  - `async def get_drop_feed(limit: int = 20) -> list[dict]` — `[{"name": str, "emoji": str, "itemName": str, "rarity": str, "openedAt": iso8601}]`, only `rarity IN ('rare','legendary')`, newest first. `name` uses the player's display name (`users`→profile helper if available, else `"Игрок"`).

- [ ] **Step 1: Add `get_drop_feed`**

Append to `server/chest_db.py`:

```python
async def get_drop_feed(limit: int = 20) -> list[dict]:
    limit = max(1, min(int(limit), 50))
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT bo.opened_at, bo.rarity, ci.name AS item_name, ci.emoji,
                      COALESCE(NULLIF(u.first_name, ''), 'Игрок') AS player_name
               FROM box_openings bo
               JOIN cosmetic_items ci ON ci.id = bo.cosmetic_id
               LEFT JOIN users u ON u.user_id = bo.user_id
               WHERE bo.rarity IN ('rare','legendary')
               ORDER BY bo.opened_at DESC
               LIMIT $1""",
            limit)
    return [{
        "name": r["player_name"], "emoji": r["emoji"], "itemName": r["item_name"],
        "rarity": r["rarity"], "openedAt": r["opened_at"].isoformat(),
    } for r in rows]
```

> Note: if `users` has no `first_name` column in this DB, replace the `COALESCE(... u.first_name ...)` with a constant `'Игрок'` and drop the join. Verify the column first: `psql "$DATABASE_URL" -c "\\d users"`.

- [ ] **Step 2: Verify feed returns seeded opens**

Reuse data from Task 4 (user 999002 opened 5). Run `server/_scratch_feed.py`:

```python
import asyncio, db, chest_db
async def main():
    await db.db.connect()
    for row in await chest_db.get_drop_feed(10):
        print(row["rarity"], row["name"], row["itemName"])
    await db.db.close()
asyncio.run(main())
```

Run: `cd server && python _scratch_feed.py`
Expected: only rare/legendary rows (possibly empty if all 5 opens were common — if empty, open more chests for a test user until a rare appears, or temporarily seed a legendary-weighted override). Delete scratch after.

- [ ] **Step 3: Commit**

```bash
git add server/chest_db.py
git commit -m "feat(chests): live drop feed query"
```

---

### Task 7: HTTP API routes (`app.py`)

Expose the game API following the existing `@app.post` + pydantic + `Depends(rate_limit)` + `_client_error`/`_server_error` pattern.

**Files:**
- Modify: `server/app.py` (pydantic models near the other action models ~line 278+; routes near the other game routes ~line 913, before `/api/me`)

**Interfaces:**
- Consumes: all `chest_db` functions above; existing `rate_limit`, `_client_error`, `_server_error`.
- Produces HTTP endpoints:
  - `GET  /api/chests/state` → `get_chest_state`
  - `POST /api/chests/open` body `{count:int}` → `open_chests`
  - `GET  /api/chests/collection` → `get_collection`
  - `POST /api/chests/buy` body `{cosmeticId:int}` → `buy_cosmetic_with_shards`
  - `POST /api/chests/equip` body `{cosmeticId:int, equipped:bool}` → `set_equipped`
  - `GET  /api/chests/feed` → `get_drop_feed`

- [ ] **Step 1: Add pydantic models**

In `server/app.py`, near the other `BaseModel` action classes (after `FarmPlantAction`, ~line 278), add:

```python
class ChestOpenAction(BaseModel):
    count: int = Field(ge=1, le=10)


class ChestBuyAction(BaseModel):
    cosmeticId: int = Field(ge=1)


class ChestEquipAction(BaseModel):
    cosmeticId: int = Field(ge=1)
    equipped: bool
```

- [ ] **Step 2: Add the routes**

In `server/app.py`, just before `@app.get("/api/me")` (~line 913), add:

```python
@app.get("/api/chests/state")
async def chests_state(user_id: int = Depends(rate_limit)):
    import chest_db
    return await chest_db.get_chest_state(user_id)


@app.post("/api/chests/open")
async def chests_open(request: Request, body: ChestOpenAction,
                      user_id: int = Depends(rate_limit)):
    import chest_db
    try:
        return await chest_db.open_chests(user_id, body.count)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/chests/collection")
async def chests_collection(user_id: int = Depends(rate_limit)):
    import chest_db
    return await chest_db.get_collection(user_id)


@app.post("/api/chests/buy")
async def chests_buy(request: Request, body: ChestBuyAction,
                     user_id: int = Depends(rate_limit)):
    import chest_db
    try:
        return await chest_db.buy_cosmetic_with_shards(user_id, body.cosmeticId)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/chests/equip")
async def chests_equip(request: Request, body: ChestEquipAction,
                       user_id: int = Depends(rate_limit)):
    import chest_db
    try:
        return await chest_db.set_equipped(user_id, body.cosmeticId, body.equipped)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/chests/feed")
async def chests_feed(user_id: int = Depends(rate_limit)):
    import chest_db
    return await chest_db.get_drop_feed()
```

> Import style note: other routes import `db` at module top. `import chest_db` inside the handler is fine and avoids touching the module-top import block; if the codebase convention you observe is top-level imports, add `import chest_db` near the top instead and drop the inline imports. Match what the file already does.

- [ ] **Step 3: Verify endpoints against the running server**

Start the server. Using a dev auth header (see `ALLOW_DEV_AUTH` / `X-Dev-User-Id` in `.env`), exercise the flow. Replace `<UID>` with your dev user id:

```bash
BASE=http://127.0.0.1:8000
H="X-Dev-User-Id: <UID>"
# grant keys first via scratch grant_keys(<UID>, 3) or the donate bot, then:
curl -s "$BASE/api/chests/state" -H "$H"
curl -s -X POST "$BASE/api/chests/open" -H "$H" -H 'Content-Type: application/json' -d '{"count":3}'
curl -s "$BASE/api/chests/collection" -H "$H"
curl -s "$BASE/api/chests/feed" -H "$H"
```

Expected: `state` returns keys/shards/box/chances; `open` returns 3 results + updated keys/shards (or a 400 with "Недостаточно ключей" if no keys); `collection` returns sets/loose with owned flags; `feed` returns a JSON array.

- [ ] **Step 4: Commit**

```bash
git add server/app.py
git commit -m "feat(chests): game HTTP API routes"
```

---

### Task 8: Donate-bot key-grant integration point (documentation + payload)

The donate bot lives outside this repo. This task pins down the exact contract so whoever owns that bot can grant keys, and records it for the future native-Stars swap.

**Files:**
- Create: `docs/superpowers/chest-key-grant-contract.md`

**Interfaces:**
- Consumes: `chest_db.grant_keys(user_id, count)` (Task 3).
- Produces: a written contract (no code change in this repo beyond the doc).

- [ ] **Step 1: Write the contract doc**

Create `docs/superpowers/chest-key-grant-contract.md`:

```markdown
# Chest key grant contract (MVP, donate-bot path)

## Purchase flow
1. Game opens the donate bot (`CuteGamingBot`) with a start payload meaning
   "grant N chest keys to this user", where N is the quantity chosen in-game
   (price = 25★ × N).
2. After the Stars payment succeeds, the donate bot grants N keys by calling
   `chest_db.grant_keys(user_id, N)` (shares this DB) OR by an authenticated
   internal HTTP call (see below).
3. The player opens chests in-game via `POST /api/chests/open`.

## Proposed start payload
`chest_{N}` where N is 1..10 (validate range on the bot side).
Keep it in the Telegram-allowed charset `[A-Za-z0-9_-]`.
The game builds this payload where it currently builds `insert_{amount}_`
(see `src/constants/donate.js`) — that change is part of the frontend plan,
not this backend plan.

## Grant entry point
- In-process (donate bot shares this codebase): `await chest_db.grant_keys(uid, n)`.
- Out-of-process: add a future internal endpoint `POST /internal/chests/grant`
  guarded by a shared secret. NOT built in MVP — documented here only.

## Future native-Stars swap
When moving to native Stars, replace step 2: on `successful_payment`, parse the
invoice payload for N and call the same `grant_keys(uid, N)`. All in-game opening
logic is unchanged.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/chest-key-grant-contract.md
git commit -m "docs(chests): donate-bot key-grant contract"
```

---

## Self-Review (completed by plan author)

**Spec coverage:**
- §3 hybrid model → Tasks 2 (tables) + 4 (non-cosmetic rewards path via `users.items`/`balance` — note: MVP seed pool is cosmetics-only; KUT/seed drops are supported by the `reward_kind` column and can be added to the pool later without schema change).
- §4 keys model → Tasks 3 (`grant_keys`, key counter) + 8 (contract).
- §5 data model (7 tables) → Task 2.
- §6 opening logic (server-authoritative, override, dupe→shard, audit, published-vs-override chances) → Tasks 1, 3 (`chances` = base only), 4.
- §7 admin → **out of scope (Plan 3)**; tables/override read-path exist so admin can write to them.
- §8 UI → **out of scope (Plan 2)**; all data the UI needs is exposed by Task 7 endpoints.
- §9 risks/fairness → published base chances in `get_chest_state`, full `box_openings` audit, `override_applied` flag (Tasks 3, 4).
- §10 MVP boundaries respected (no native Stars, one shard currency, no pity, no seasonal).

**Placeholder scan:** No TBD/TODO; every code step has complete code; verification steps use runnable scratch scripts with expected output.

**Type consistency:** `resolve_rarity_weights`, `roll_rarity`, `pick_item`, `shard_for_dupe` signatures match between Task 1 (defined + tested) and Task 4 (consumed). `grant_keys`/`get_chest_state` (Task 3) consumed by Task 7 routes. Result dict keys (`cosmeticId`, `wasDupe`, `shardsGranted`, `keys`, `shards`) consistent across Tasks 4/5/7.

**Known follow-ups (not gaps):** Plan 2 (frontend) and Plan 3 (admin) build on these endpoints. The `users.first_name` assumption in Task 6 has an inline verification + fallback.
