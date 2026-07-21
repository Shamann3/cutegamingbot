# Розыгрыши v2 — вкладки, анонсы, лента победителей — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tab-based Активные/Скоро/Прошедшие sections, scheduled-start giveaways, participant previews on ticket cards, and a rotating "recent winners" feed to the already-shipped Giveaways v1 feature.

**Architecture:** One new nullable column (`giveaways.starts_at`) drives "upcoming vs active" bucketing, computed on read (no new status, no scheduler changes). Two new read-only endpoints (`/api/giveaways/history`, `/api/giveaways/winners-feed`) serve the new tabs/feed. A new admin action (`POST .../complete`) lets admins manually close out `instant` giveaways so they have a path into history, since they never auto-complete.

**Tech Stack:** FastAPI + asyncpg (backend), React + Vite (webapp + admin panel), pytest (backend unit tests), vitest (frontend unit tests) — same stack as v1, no new dependencies.

## Global Constraints

- Follow `docs/superpowers/specs/2026-07-20-giveaways-v2-design.md` exactly; it is the source of truth for every decision below.
- No new `giveaways.status` value — bucketing is computed from `status` + `starts_at`, never stored.
- `cancelled` giveaways remain invisible to players everywhere (existing v1 behavior, unchanged).
- All new/changed webapp strings are in Russian, matching the rest of the app.
- Every new DB-touching method in `server/db.py` must respect the existing connection-pool rule: never `await` a function that does its own `pool.acquire()` while already holding a connection from an outer `acquire()`/transaction.
- No live Postgres is available in this environment (same as v1) — backend integration methods (Tasks 2–4) are verified via `python -m py_compile` + careful manual review, not a live DB smoke test. Only pure logic (Task 1) gets real pytest TDD.

---

### Task 1: Pure bucket/display-name logic (TDD) + schema column

**Files:**
- Create: `server/giveaway_display.py`
- Create: `server/tests/test_giveaway_display.py`
- Modify: `server/schema.sql` (after the `giveaways` table definition, currently ending at line 1043)

**Interfaces:**
- Produces: `giveaway_bucket(status: str, starts_at: datetime | None, now: datetime) -> str` (returns `"active" | "upcoming" | "past"`) and `display_name(username: str | None, first_name: str | None) -> str` (returns `"@username"` or `first_name` or `"Игрок"`). Both consumed by Task 2/3's `db.py` changes.

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_giveaway_display.py`:

```python
"""Розыгрыши: чистые функции bucket/отображаемого имени, без БД."""
from datetime import datetime, timedelta, timezone

from giveaway_display import giveaway_bucket, display_name

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def test_completed_is_past_regardless_of_starts_at():
    assert giveaway_bucket("completed", None, NOW) == "past"
    assert giveaway_bucket("completed", NOW + timedelta(days=1), NOW) == "past"


def test_active_with_no_starts_at_is_active():
    assert giveaway_bucket("active", None, NOW) == "active"


def test_active_with_past_starts_at_is_active():
    assert giveaway_bucket("active", NOW - timedelta(hours=1), NOW) == "active"


def test_active_with_future_starts_at_is_upcoming():
    assert giveaway_bucket("active", NOW + timedelta(hours=1), NOW) == "upcoming"


def test_active_with_starts_at_exactly_now_is_active():
    assert giveaway_bucket("active", NOW, NOW) == "active"


def test_display_name_prefers_username():
    assert display_name("alex_trade", "Alex") == "@alex_trade"


def test_display_name_falls_back_to_first_name():
    assert display_name(None, "Alex") == "Alex"
    assert display_name("", "Alex") == "Alex"


def test_display_name_falls_back_to_generic_label():
    assert display_name(None, None) == "Игрок"
    assert display_name("", "") == "Игрок"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_giveaway_display.py -v`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'giveaway_display'`

- [ ] **Step 3: Write the implementation**

Create `server/giveaway_display.py`:

```python
"""Розыгрыши: чистые функции для вычисления вкладки (bucket) и отображаемого
имени игрока — без обращения к БД, легко покрываются юнит-тестами.
"""
from __future__ import annotations

from datetime import datetime


def giveaway_bucket(status: str, starts_at: datetime | None, now: datetime) -> str:
    """active | upcoming | past — куда попадает розыгрыш в списке игрока.

    cancelled сюда никогда не передаётся — такие розыгрыши уже отфильтрованы
    в SQL (WHERE status != 'cancelled') на уровне get_giveaways_state/history,
    игроку не показываются вовсе.
    """
    if status == "completed":
        return "past"
    if starts_at is not None and starts_at > now:
        return "upcoming"
    return "active"


def display_name(username: str | None, first_name: str | None) -> str:
    if username:
        return f"@{username}"
    if first_name:
        return first_name
    return "Игрок"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && python -m pytest tests/test_giveaway_display.py -v`
Expected: 9 passed

- [ ] **Step 5: Add the schema column**

In `server/schema.sql`, immediately after the `giveaways` table's closing `);` (the block that currently ends at line 1043, right before the `CREATE TABLE IF NOT EXISTS giveaway_conditions` block), add:

```sql
-- v2: розыгрыш может быть анонсирован заранее — starts_at в будущем значит
-- "виден во вкладке «Скоро», участие заблокировано". NULL = доступен сразу
-- (весь существующий v1-контент автоматически остаётся активным).
ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ;
```

- [ ] **Step 6: Verify schema.sql still parses (syntax-only check, no live DB)**

Run: `cd server && python -c "import re; sql = open('schema.sql', encoding='utf-8').read(); assert sql.count('CREATE TABLE') == sql.count(');') or True; print('starts_at' in sql)"`
Expected: prints `True` (confirms the new line was written; this is a smoke check, not a real parser — the ALTER statement follows the exact same `ADD COLUMN IF NOT EXISTS` pattern already used dozens of times elsewhere in this file, so no new syntax is introduced)

- [ ] **Step 7: Run full backend test suite to confirm no regressions**

Run: `cd server && python -m pytest -v`
Expected: all tests pass (6 existing `test_giveaway_conditions.py` + 9 new `test_giveaway_display.py` = 15 passed)

- [ ] **Step 8: Commit**

```bash
git add server/giveaway_display.py server/tests/test_giveaway_display.py server/schema.sql
git commit -m "feat(giveaways): add starts_at column + pure bucket/display-name helpers"
```

---

### Task 2: `db.py` — expose startsAt/participants in the list, guard participation

**Files:**
- Modify: `server/db.py`

**Interfaces:**
- Consumes: `giveaway_bucket`, `display_name` from `server/giveaway_display.py` (Task 1).
- Produces: `get_giveaways_state(user_id)` items now include `startsAt`, `participantsCount`, `participantsPreview` (list of strings). `get_giveaway_detail(user_id, giveaway_id)` now includes `startsAt`. `participate_in_giveaway` now rejects with `ValueError("Розыгрыш ещё не начался")` when the giveaway hasn't started yet. These field names are relied on by Tasks 7/8's frontend code.

- [ ] **Step 1: Add the `timezone` import and the `giveaway_display` import**

In `server/db.py`, find (lines 6-8):

```python
from datetime import timedelta
from datetime import datetime
from pathlib import Path
```

Replace with:

```python
from datetime import timedelta
from datetime import datetime
from datetime import timezone
from pathlib import Path
```

Find (line 87, the existing giveaway_conditions import):

```python
from giveaway_conditions import all_conditions_met
```

Replace with:

```python
from giveaway_conditions import all_conditions_met
from giveaway_display import display_name, giveaway_bucket
```

- [ ] **Step 2: Add `_giveaway_participants` helper**

In `server/db.py`, find the `_giveaway_prize_summary` method (currently right before `get_giveaways_state`):

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

    async def get_giveaways_state(self, user_id):
```

Replace with (adds the new helper method between them):

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

    async def _giveaway_participants(self, conn, giveaway_id, limit=4):
        count = await conn.fetchval(
            "SELECT COUNT(*)::int FROM giveaway_entries WHERE giveaway_id = $1",
            giveaway_id,
        )
        rows = await conn.fetch(
            """
            SELECT u.username, u.first_name
            FROM giveaway_entries e
            JOIN users u ON u.user_id = e.user_id
            WHERE e.giveaway_id = $1
            ORDER BY e.joined_at DESC
            LIMIT $2
            """,
            giveaway_id, limit,
        )
        preview = [display_name(r["username"], r["first_name"]) for r in rows]
        return int(count or 0), preview

    async def get_giveaways_state(self, user_id):
```

- [ ] **Step 3: Extend `get_giveaways_state`'s item dict**

Find:

```python
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
```

Replace with:

```python
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

- [ ] **Step 4: Add `startsAt` to `get_giveaway_detail`'s response**

Find (the return statement at the end of `get_giveaway_detail`):

```python
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
```

Replace with:

```python
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
        }
```

- [ ] **Step 5: Guard `participate_in_giveaway` against not-yet-started giveaways**

Find:

```python
                if not already_joined:
                    if row["status"] != "active" or not row["enabled"]:
                        raise ValueError("Розыгрыш недоступен")

                    ctx = await self._giveaway_condition_ctx(conn, user_id)
```

Replace with:

```python
                if not already_joined:
                    if row["status"] != "active" or not row["enabled"]:
                        raise ValueError("Розыгрыш недоступен")
                    if giveaway_bucket(row["status"], row["starts_at"], datetime.now(timezone.utc)) == "upcoming":
                        raise ValueError("Розыгрыш ещё не начался")

                    ctx = await self._giveaway_condition_ctx(conn, user_id)
```

- [ ] **Step 6: Verify the file still compiles**

Run: `cd server && python -m py_compile db.py`
Expected: no output, exit code 0

- [ ] **Step 7: Run the full backend test suite**

Run: `cd server && python -m pytest -v`
Expected: 15 passed (unchanged from Task 1 — this task doesn't add new pytest-covered pure logic, it wires already-tested helpers into DB-touching code that needs a live Postgres to exercise end-to-end)

- [ ] **Step 8: Commit**

```bash
git add server/db.py
git commit -m "feat(giveaways): expose startsAt/participants in list+detail, block participation before start"
```

---

### Task 3: `db.py` — history, manual completion, winners feed

**Files:**
- Modify: `server/db.py`

**Interfaces:**
- Consumes: `_giveaway_prize_summary`, `display_name` (already imported in Task 2).
- Produces: `get_giveaways_history(limit=30)` → `{"giveaways": [...]}`, each item has `id, title, emoji, rarity, prize, drawType, winnerName (str|None), recipientsCount (int|None), drawnAt (str|None)`. `complete_instant_giveaway(giveaway_id)` → `bool` (True if a row was actually completed, False if not found/not eligible — used by Task 4's admin wrapper to decide the error message). `get_giveaway_winners_feed(limit=20)` → `{"winners": [...]}`, each item has `displayName, prize, giveawayTitle, giveawayEmoji, at (ISO string)`. All three consumed by Task 4's routes.

- [ ] **Step 1: Add `get_giveaways_history`**

In `server/db.py`, find the end of `draw_timer_giveaways` (right before `async def get_craft_recipes`):

```python
        for winner, title, prize_text in pending_notifications:
            await create_admin_message_notification(
                self.pool,
                winner,
                title="Вы выиграли в розыгрыше!",
                body=f"«{title}» — приз: {prize_text}",
            )

    async def get_craft_recipes(self, user_id):
```

Replace with (inserts three new methods between them):

```python
        for winner, title, prize_text in pending_notifications:
            await create_admin_message_notification(
                self.pool,
                winner,
                title="Вы выиграли в розыгрыше!",
                body=f"«{title}» — приз: {prize_text}",
            )

    async def get_giveaways_history(self, limit=30):
        rows = await self.pool.fetch(
            """
            SELECT g.*,
              (SELECT COUNT(*)::int FROM giveaway_entries e WHERE e.giveaway_id = g.id) AS entries_count,
              u.username AS winner_username, u.first_name AS winner_first_name
            FROM giveaways g
            LEFT JOIN users u ON u.user_id = g.winner_user_id
            WHERE g.status = 'completed'
            ORDER BY g.drawn_at DESC NULLS LAST, g.id DESC
            LIMIT $1
            """,
            limit,
        )
        items = []
        for row in rows:
            is_timer = row["draw_type"] == "timer"
            items.append({
                "id": row["id"],
                "title": row["title"],
                "emoji": row["emoji"],
                "rarity": row["rarity"],
                "prize": self._giveaway_prize_summary(row),
                "drawType": row["draw_type"],
                "winnerName": display_name(row["winner_username"], row["winner_first_name"]) if is_timer else None,
                "recipientsCount": None if is_timer else int(row["entries_count"] or 0),
                "drawnAt": row["drawn_at"].isoformat() if row["drawn_at"] else None,
            })
        return {"giveaways": items}

    async def complete_instant_giveaway(self, giveaway_id):
        result = await self.pool.execute(
            """
            UPDATE giveaways
            SET status = 'completed', drawn_at = NOW(), updated_at = NOW()
            WHERE id = $1 AND draw_type = 'instant' AND status = 'active'
            """,
            giveaway_id,
        )
        return result == "UPDATE 1"

    async def get_giveaway_winners_feed(self, limit=20):
        timer_rows = await self.pool.fetch(
            """
            SELECT g.title, g.emoji, g.prize_type, g.prize_kut_amount, g.prize_title, g.prize_emoji,
                   u.username, u.first_name, g.drawn_at AS at
            FROM giveaways g
            LEFT JOIN users u ON u.user_id = g.winner_user_id
            WHERE g.draw_type = 'timer' AND g.status = 'completed' AND g.winner_user_id IS NOT NULL
            ORDER BY g.drawn_at DESC
            LIMIT $1
            """,
            limit,
        )
        instant_rows = await self.pool.fetch(
            """
            SELECT g.title, g.emoji, g.prize_type, g.prize_kut_amount, g.prize_title, g.prize_emoji,
                   u.username, u.first_name, e.joined_at AS at
            FROM giveaway_entries e
            JOIN giveaways g ON g.id = e.giveaway_id
            JOIN users u ON u.user_id = e.user_id
            WHERE g.draw_type = 'instant'
            ORDER BY e.joined_at DESC
            LIMIT $1
            """,
            limit,
        )
        merged = sorted(
            [dict(r) for r in timer_rows] + [dict(r) for r in instant_rows],
            key=lambda r: r["at"],
            reverse=True,
        )[:limit]
        winners = [
            {
                "displayName": display_name(r["username"], r["first_name"]),
                "prize": self._giveaway_prize_summary(r),
                "giveawayTitle": r["title"],
                "giveawayEmoji": r["emoji"],
                "at": r["at"].isoformat(),
            }
            for r in merged
        ]
        return {"winners": winners}

    async def get_craft_recipes(self, user_id):
```

- [ ] **Step 2: Verify the file still compiles**

Run: `cd server && python -m py_compile db.py`
Expected: no output, exit code 0

- [ ] **Step 3: Manual review checklist (no live DB in this environment)**

Confirm by reading the diff:
- `get_giveaways_history`/`get_giveaway_winners_feed` only ever call `self.pool.fetch`/`self.pool.execute` directly (no nested `pool.acquire()`), so there is no connection-pool double-checkout risk — these methods never hold an outer `conn` while awaiting something that acquires its own.
- `complete_instant_giveaway` uses a single conditional `UPDATE ... WHERE id = $1 AND draw_type = 'instant' AND status = 'active'` — same atomic-conditional-update pattern already used by `cancel_giveaway` (admin_giveaways.py) and the `already_joined`/status checks in `participate_in_giveaway`, so a row can't be double-completed by concurrent requests.
- `_giveaway_prize_summary(r)` is called with plain dicts from `asyncpg.Record` rows that were explicitly `SELECT`ed to include `prize_type, prize_kut_amount, prize_title, prize_emoji` — exactly the four keys that method reads — so it works unchanged on these narrower row shapes, not just full `giveaways.*` rows.

- [ ] **Step 4: Run the full backend test suite**

Run: `cd server && python -m pytest -v`
Expected: 15 passed (unchanged — no new pure logic added in this task)

- [ ] **Step 5: Commit**

```bash
git add server/db.py
git commit -m "feat(giveaways): add history, manual instant-completion, and winners-feed queries"
```

---

### Task 4: Routes — history/winners-feed endpoints, admin starts_at + complete action

**Files:**
- Modify: `server/app.py`
- Modify: `server/admin_giveaways.py`
- Modify: `server/admin_routes.py`

**Interfaces:**
- Consumes: `db.get_giveaways_history`, `db.get_giveaway_winners_feed`, `db.complete_instant_giveaway` (Task 3).
- Produces: `GET /api/giveaways/history`, `GET /api/giveaways/winners-feed` (webapp-facing, Task 6 consumes them). `POST /admin/api/content/giveaways/{id}/complete` (admin-facing, Task 5 consumes it). `create_giveaway`/`update_giveaway` in `admin_giveaways.py` now accept/return `starts_at`/`startsAt`.

- [ ] **Step 1: Add the two webapp routes**

In `server/app.py`, find:

```python
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


@app.get("/api/shop/catalog")
```

Replace with:

```python
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


@app.get("/api/giveaways/history")
async def giveaways_history(request: Request, user_id: int = Depends(rate_limit)):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        return await db.get_giveaways_history()
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/giveaways/winners-feed")
async def giveaways_winners_feed(request: Request, user_id: int = Depends(rate_limit)):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        return await db.get_giveaway_winners_feed()
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/shop/catalog")
```

(Both new routes require `Depends(rate_limit)` like every other authenticated route in this file, even though the data itself isn't user-specific — this matches the existing convention of every `/api/*` route requiring a resolved `user_id`, and keeps the same rate-limiting protection.)

- [ ] **Step 2: Add `starts_at` handling to `admin_giveaways.py`'s `_validate_draw`**

In `server/admin_giveaways.py`, find:

```python
def _validate_draw(draw_type: str, ends_at):
    draw_type = (draw_type or "").strip().lower()
    if draw_type not in _VALID_DRAW_TYPE:
        raise ValueError(f"Тип розыгрыша: {', '.join(sorted(_VALID_DRAW_TYPE))}")
    if draw_type == "timer" and not ends_at:
        raise ValueError("Укажите дату окончания для розыгрыша по таймеру")
    return draw_type
```

Replace with:

```python
def _validate_draw(draw_type: str, ends_at, starts_at=None):
    draw_type = (draw_type or "").strip().lower()
    if draw_type not in _VALID_DRAW_TYPE:
        raise ValueError(f"Тип розыгрыша: {', '.join(sorted(_VALID_DRAW_TYPE))}")
    if draw_type == "timer" and not ends_at:
        raise ValueError("Укажите дату окончания для розыгрыша по таймеру")
    if starts_at and ends_at and starts_at >= ends_at:
        raise ValueError("Дата начала должна быть раньше даты окончания")
    return draw_type
```

- [ ] **Step 3: Add `starts_at` to `_giveaway_to_admin_dict`**

Find:

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

Replace with:

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

- [ ] **Step 4: Add `starts_at` to `create_giveaway`**

Find:

```python
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
```

Replace with:

```python
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

- [ ] **Step 5: Add `starts_at` to `update_giveaway`**

Find:

```python
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
```

Replace with:

```python
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
    starts_at=_UNSET,
    conditions: list[dict] | None = None,
    enabled: bool | None = None,
    admin_user_id: int,
) -> dict:
```

Then find:

```python
    if draw_type is not None or ends_at is not _UNSET:
        resolved_ends_at = ends_at if ends_at is not _UNSET else row["ends_at"]
        draw_type_v = _validate_draw(draw_type if draw_type is not None else row["draw_type"], resolved_ends_at)
        params.append(draw_type_v); sets.append(f"draw_type = ${len(params)}")
        params.append(resolved_ends_at); sets.append(f"ends_at = ${len(params)}")
```

Replace with:

```python
    if draw_type is not None or ends_at is not _UNSET or starts_at is not _UNSET:
        resolved_ends_at = ends_at if ends_at is not _UNSET else row["ends_at"]
        resolved_starts_at = starts_at if starts_at is not _UNSET else row["starts_at"]
        draw_type_v = _validate_draw(
            draw_type if draw_type is not None else row["draw_type"],
            resolved_ends_at, resolved_starts_at,
        )
        params.append(draw_type_v); sets.append(f"draw_type = ${len(params)}")
        params.append(resolved_ends_at); sets.append(f"ends_at = ${len(params)}")
        params.append(resolved_starts_at); sets.append(f"starts_at = ${len(params)}")
```

- [ ] **Step 6: Add `complete_instant_giveaway` wrapper to `admin_giveaways.py`**

At the end of `server/admin_giveaways.py` (after `cancel_giveaway`), add:

```python
async def complete_giveaway(giveaway_id: int, *, admin_user_id: int) -> dict:
    row = await db.pool.fetchrow(
        "SELECT id, title, draw_type, status FROM giveaways WHERE id = $1", giveaway_id
    )
    if row is None:
        raise ValueError("Розыгрыш не найден")
    if row["draw_type"] != "instant":
        raise ValueError("Завершить вручную можно только мгновенный розыгрыш — таймерные завершаются сами")
    if row["status"] != "active":
        raise ValueError("Розыгрыш уже завершён или отменён")
    ok = await db.complete_instant_giveaway(giveaway_id)
    if not ok:
        raise ValueError("Не удалось завершить — розыгрыш уже изменился, обновите список")
    return {"ok": True, "title": row["title"]}
```

- [ ] **Step 7: Add `starts_at` to `GiveawayCreateBody`/`GiveawayUpdateBody` and wire the new fields through the create/patch routes**

In `server/admin_routes.py`, find:

```python
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
    drawType: str = Field(min_length=5, max_length=16)
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

Replace with:

```python
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
    drawType: str = Field(min_length=5, max_length=16)
    startsAt: str | None = Field(default=None, max_length=64)
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
    startsAt: str | None = Field(default=None, max_length=64)
    endsAt: str | None = Field(default=None, max_length=64)
    conditions: list[GiveawayConditionBody] | None = Field(default=None, max_length=10)
    enabled: bool | None = None
    model_config = {"extra": "forbid"}
```

Now find the import block:

```python
from admin_giveaways import (
    cancel_giveaway,
    create_giveaway,
    list_giveaways_admin,
    update_giveaway,
)
```

Replace with:

```python
from admin_giveaways import (
    cancel_giveaway,
    complete_giveaway,
    create_giveaway,
    list_giveaways_admin,
    update_giveaway,
)
```

Now find the create route:

```python
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
```

Replace with:

```python
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
            starts_at=_parse_dt(body.startsAt),
            conditions=[c.model_dump() for c in body.conditions],
            enabled=body.enabled,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "giveaway_create",
```

Now find the patch route:

```python
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
```

Replace with:

```python
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
            starts_at=_parse_dt(body.startsAt) if body.startsAt is not None else _UNSET,
            conditions=[c.model_dump() for c in body.conditions] if body.conditions is not None else None,
            enabled=body.enabled,
            admin_user_id=admin_id,
        )
```

- [ ] **Step 8: Add the `complete` route**

Find:

```python
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

Replace with:

```python
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


@router.post("/content/giveaways/{giveaway_id}/complete")
async def admin_content_giveaway_complete(
    giveaway_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await complete_giveaway(giveaway_id, admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "giveaway_complete",
            target_type="giveaway", target_id=str(giveaway_id),
            target_label=f"Розыгрыш #{giveaway_id}",
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 9: Verify all three files compile**

Run: `cd server && python -m py_compile app.py admin_giveaways.py admin_routes.py`
Expected: no output, exit code 0

- [ ] **Step 10: Run the full backend test suite**

Run: `cd server && python -m pytest -v`
Expected: 15 passed

- [ ] **Step 11: Commit**

```bash
git add server/app.py server/admin_giveaways.py server/admin_routes.py
git commit -m "feat(giveaways): history/winners-feed routes, admin starts_at + complete action"
```

---

### Task 5: Admin panel — "Дата начала" field, table column, "Завершить" action

**Files:**
- Modify: `admin/src/lib/adminClient.js`
- Modify: `admin/src/pages/sections/GiveawaysSection.jsx`

**Interfaces:**
- Consumes: `POST /admin/api/content/giveaways/{id}/complete` (Task 4).
- Produces: `completeGiveawayAdmin(giveawayId)` in `adminClient.js`, consumed only within `GiveawaysSection.jsx` in this task.

- [ ] **Step 1: Add the admin client function**

In `admin/src/lib/adminClient.js`, find:

```js
export async function deleteGiveawayAdmin(giveawayId) {
  return adminFetch(`/content/giveaways/${giveawayId}`, { method: 'DELETE' })
}
```

Replace with:

```js
export async function deleteGiveawayAdmin(giveawayId) {
  return adminFetch(`/content/giveaways/${giveawayId}`, { method: 'DELETE' })
}

export async function completeGiveawayAdmin(giveawayId) {
  return adminFetch(`/content/giveaways/${giveawayId}/complete`, { method: 'POST' })
}
```

- [ ] **Step 2: Import it and add `completeTarget` state**

In `admin/src/pages/sections/GiveawaysSection.jsx`, find:

```jsx
import {
  fetchGiveawaysAdmin,
  createGiveawayAdmin,
  patchGiveawayAdmin,
  deleteGiveawayAdmin,
} from '../../lib/adminClient'
```

Replace with:

```jsx
import {
  fetchGiveawaysAdmin,
  createGiveawayAdmin,
  patchGiveawayAdmin,
  deleteGiveawayAdmin,
  completeGiveawayAdmin,
} from '../../lib/adminClient'
```

Find:

```jsx
  const [form, setForm] = useState(null) // null = список, объект = форма создания/редактирования
  const [saving, setSaving] = useState(false)
  const [cancelTarget, setCancelTarget] = useState(null)
```

Replace with:

```jsx
  const [form, setForm] = useState(null) // null = список, объект = форма создания/редактирования
  const [saving, setSaving] = useState(false)
  const [cancelTarget, setCancelTarget] = useState(null)
  const [completeTarget, setCompleteTarget] = useState(null)
```

- [ ] **Step 3: Add `startsAt` to the form state**

Find:

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
    endsAt: '',
    enabled: true,
    conditions: [],
  }
}
```

Replace with:

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

Find:

```jsx
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
```

Replace with:

```jsx
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
    startsAt: item.startsAt ? item.startsAt.slice(0, 16) : '',
    endsAt: item.endsAt ? item.endsAt.slice(0, 16) : '',
    enabled: item.enabled,
    conditions: item.conditions.map((c) => ({
      kind: c.kind, targetValue: c.targetValue, itemId: c.itemId ?? '',
    })),
  })
```

Find (inside `save()`):

```jsx
        drawType: form.drawType,
        endsAt: form.drawType === 'timer' && form.endsAt ? new Date(form.endsAt).toISOString() : null,
        enabled: form.enabled,
```

Replace with:

```jsx
        drawType: form.drawType,
        startsAt: form.startsAt ? new Date(form.startsAt).toISOString() : null,
        endsAt: form.drawType === 'timer' && form.endsAt ? new Date(form.endsAt).toISOString() : null,
        enabled: form.enabled,
```

- [ ] **Step 4: Add the "Дата начала" field to the form**

Find:

```jsx
            <label className="admin-modal-field">
              <span>Название</span>
              <input className="panel-users-input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </label>
            <label className="admin-modal-field">
              <span>Описание</span>
```

Replace with:

```jsx
            <label className="admin-modal-field">
              <span>Название</span>
              <input className="panel-users-input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </label>
            <label className="admin-modal-field">
              <span>Дата начала (необязательно — пусто значит «сразу»)</span>
              <input className="panel-users-input" type="datetime-local" value={form.startsAt} onChange={(e) => setForm({ ...form, startsAt: e.target.value })} />
            </label>
            <label className="admin-modal-field">
              <span>Описание</span>
```

- [ ] **Step 5: Add the "Старт" table column**

Find:

```jsx
        <table className="panel-economy-dex-table">
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
```

Replace with:

```jsx
        <table className="panel-economy-dex-table">
          <thead>
            <tr>
              <th>Приз</th>
              <th>Редкость</th>
              <th>Тип</th>
              <th>Старт</th>
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
                <td>{item.startsAt ? new Date(item.startsAt).toLocaleString('ru-RU') : 'сразу'}</td>
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
                  {item.status === 'active' && item.drawType === 'instant' && (
                    <button
                      type="button"
                      className="panel-users-btn"
                      onClick={() => setCompleteTarget(item)}
                    >
                      Завершить
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
```

- [ ] **Step 6: Add the confirm handler and modal**

Find:

```jsx
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
```

Replace with:

```jsx
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

  const confirmComplete = async () => {
    if (!completeTarget) return
    setSaving(true)
    try {
      await completeGiveawayAdmin(completeTarget.id)
      setCompleteTarget(null)
      await load()
    } catch (e) {
      setError(e?.message || 'Ошибка завершения')
    } finally {
      setSaving(false)
    }
  }
```

Find:

```jsx
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

Replace with:

```jsx
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

      <AdminActionModal
        open={Boolean(completeTarget)}
        title="Завершить розыгрыш?"
        description={completeTarget ? `«${completeTarget.title}» — уйдёт из «Активных»/«Скоро» и появится во вкладке «Прошедшие» игроков с числом получивших приз.` : ''}
        confirmText="Завершить"
        loading={saving}
        onConfirm={confirmComplete}
        onCancel={() => setCompleteTarget(null)}
      />
    </div>
  )
}
```

- [ ] **Step 7: Build the admin panel to catch JSX/import errors**

Run: `cd admin && npm run build`
Expected: build succeeds, no errors

- [ ] **Step 8: Commit**

```bash
git add admin/src/lib/adminClient.js admin/src/pages/sections/GiveawaysSection.jsx
git commit -m "feat(giveaways): admin starts_at field, start column, complete action for instant giveaways"
```

---

### Task 6: Webapp data layer — client functions + history/feed hooks

**Files:**
- Modify: `src/lib/giveawaysClient.js`
- Create: `src/hooks/useGiveawayHistory.js`
- Create: `src/hooks/useGiveawayWinnersFeed.js`

**Interfaces:**
- Consumes: `GET /api/giveaways/history`, `GET /api/giveaways/winners-feed` (Task 4), `apiRequest` from `src/lib/apiClient.js` (existing).
- Produces: `fetchGiveawayHistory()`, `fetchGiveawayWinnersFeed()` (both consumed by the two new hooks in this task). `useGiveawayHistory()` → `{ giveaways: array|null, loading: bool, error: string|null, load: () => Promise<void> }` (`giveaways === null` means "never loaded yet" — Task 7's `GiveawaysModule` uses this to lazily trigger `load()` the first time the "Прошедшие" tab is opened). `useGiveawayWinnersFeed()` → `{ winners: array }` (self-polling every 60s, fails silently — consumed by Task 8's `GiveawayWinnersFeed.jsx`).

- [ ] **Step 1: Add the two client functions**

In `src/lib/giveawaysClient.js`, find:

```js
export function participateInGiveaway(giveawayId) {
  return apiRequest(`/api/giveaways/${giveawayId}/participate`, {
    method: 'POST',
    body: {},
  })
}
```

Replace with:

```js
export function participateInGiveaway(giveawayId) {
  return apiRequest(`/api/giveaways/${giveawayId}/participate`, {
    method: 'POST',
    body: {},
  })
}

export function fetchGiveawayHistory() {
  return apiRequest('/api/giveaways/history')
}

export function fetchGiveawayWinnersFeed() {
  return apiRequest('/api/giveaways/winners-feed')
}
```

- [ ] **Step 2: Create `useGiveawayHistory`**

Create `src/hooks/useGiveawayHistory.js`:

```js
import { useCallback, useState } from 'react'
import { fetchGiveawayHistory } from '../lib/giveawaysClient'

export function useGiveawayHistory() {
  const [giveaways, setGiveaways] = useState(null) // null = ещё не грузили
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchGiveawayHistory()
      setGiveaways(data?.giveaways ?? [])
      setError(null)
    } catch (err) {
      setError(err?.message ?? 'Ошибка загрузки истории')
    } finally {
      setLoading(false)
    }
  }, [])

  return { giveaways, loading, error, load }
}
```

- [ ] **Step 3: Create `useGiveawayWinnersFeed`**

Create `src/hooks/useGiveawayWinnersFeed.js`:

```js
import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchGiveawayWinnersFeed } from '../lib/giveawaysClient'

const REFRESH_MS = 60000

export function useGiveawayWinnersFeed() {
  const [winners, setWinners] = useState([])
  const mountedRef = useRef(false)

  const load = useCallback(async () => {
    try {
      const data = await fetchGiveawayWinnersFeed()
      if (mountedRef.current) setWinners(data?.winners ?? [])
    } catch {
      // Лента — необязательный декоративный элемент, не должна ронять модуль
      // ошибкой загрузки; при сбое просто остаётся пустой/старой.
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    load()
    const timer = window.setInterval(load, REFRESH_MS)
    return () => {
      mountedRef.current = false
      window.clearInterval(timer)
    }
  }, [load])

  return { winners }
}
```

- [ ] **Step 4: Build to catch syntax errors**

Run: `npx vite build`
Expected: build succeeds (these hooks aren't wired into any component yet, so the build just confirms valid JS/imports)

- [ ] **Step 5: Commit**

```bash
git add src/lib/giveawaysClient.js src/hooks/useGiveawayHistory.js src/hooks/useGiveawayWinnersFeed.js
git commit -m "feat(giveaways): webapp client + hooks for history and winners feed"
```

---

### Task 7: `GiveawaysModule.jsx` — tabs, bucketing, sorting, history card

**Files:**
- Modify: `src/components/GiveawaysModule.jsx`
- Create: `src/components/GiveawayHistoryCard.jsx`
- Modify: `src/styles/giveaways.css`

**Interfaces:**
- Consumes: `useGiveawayHistory` (Task 6), `RARITY_ORDER`/`formatGiveawayPrize` (`src/constants/giveaways.js`, existing), `.segment-tabs`/`.segment-tab`/`.segment-tab-active` (`src/index.css`, existing — same pattern used by Farm/Trade/Profile).
- Produces: `<GiveawayHistoryCard giveaway={...} />` where `giveaway` has `{id, title, emoji, rarity, prize, winnerName, recipientsCount, drawnAt}` (matches `get_giveaways_history`'s item shape from Task 3) — no other file consumes this component besides `GiveawaysModule.jsx` in this same task.

- [ ] **Step 1: Create `GiveawayHistoryCard.jsx`**

Create `src/components/GiveawayHistoryCard.jsx`:

```jsx
import { RARITY_ACCENT, formatGiveawayPrize } from '../constants/giveaways'

export default function GiveawayHistoryCard({ giveaway }) {
  const accent = RARITY_ACCENT[giveaway.rarity] ?? RARITY_ACCENT.common

  return (
    <div
      className="giveaway-history-card"
      style={{ '--ticket-accent-strong': accent.strong, '--ticket-accent-glow': accent.glow }}
    >
      <span className="giveaway-history-emoji" aria-hidden>{giveaway.emoji}</span>
      <div className="giveaway-history-info">
        <span className="giveaway-history-title">{giveaway.title}</span>
        <span className="giveaway-history-result">
          {giveaway.winnerName
            ? `🏆 Победитель: ${giveaway.winnerName}`
            : `🎁 ${giveaway.recipientsCount ?? 0} игроков получили приз`}
        </span>
      </div>
      <span className="giveaway-history-prize">{formatGiveawayPrize(giveaway.prize)}</span>
    </div>
  )
}
```

- [ ] **Step 2: Rewrite `GiveawaysModule.jsx` with tabs and bucketing**

Replace the entire file `src/components/GiveawaysModule.jsx` with:

```jsx
import { useMemo, useState } from 'react'
import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import GiveawayTicketCard from './GiveawayTicketCard'
import GiveawayDetailModal from './GiveawayDetailModal'
import GiveawayHistoryCard from './GiveawayHistoryCard'
import { useGiveaways } from '../hooks/useGiveaways'
import { useGiveawayHistory } from '../hooks/useGiveawayHistory'
import { RARITY_ORDER } from '../constants/giveaways'
import '../styles/giveaways.css'

const TABS = [
  { id: 'active', label: '🟢 Активные' },
  { id: 'upcoming', label: '⌛ Скоро' },
  { id: 'past', label: '🏆 Прошедшие' },
]

function sortByRarity(list) {
  return [...list].sort((a, b) => RARITY_ORDER.indexOf(b.rarity) - RARITY_ORDER.indexOf(a.rarity))
}

export default function GiveawaysModule({ isActive = true, onNavigateCondition }) {
  const { giveaways, initialLoading, error, participate, participatingId, clearError } = useGiveaways({ isActive })
  const history = useGiveawayHistory()
  const [openId, setOpenId] = useState(null)
  const [tab, setTab] = useState('active')

  const handleOpenDetail = (id) => {
    clearError()
    setOpenId(id)
  }

  const handleNavigateCondition = (target) => {
    setOpenId(null)
    onNavigateCondition?.(target)
  }

  const handleTabChange = (id) => {
    setTab(id)
    if (id === 'past' && history.giveaways === null) history.load()
  }

  const now = Date.now()
  // status === 'active' здесь не избыточно: get_giveaways_state отдаёт и уже
  // завершённые (status='completed') розыгрыши тоже — чтобы игрок успел
  // увидеть «вы выиграли»/«завершён» в статус-лейбле карточки на один
  // цикл поллинга. Теперь у завершённых есть отдельный дом (вкладка
  // «Прошедшие», через useGiveawayHistory) — здесь их явно исключаем, иначе
  // они годами копились бы в «Активных».
  const activeList = useMemo(
    () => sortByRarity(giveaways.filter((g) => (
      g.status === 'active' && (!g.startsAt || new Date(g.startsAt).getTime() <= now)
    ))),
    [giveaways, now],
  )
  const upcomingList = useMemo(
    () => sortByRarity(giveaways.filter((g) => (
      g.status === 'active' && g.startsAt && new Date(g.startsAt).getTime() > now
    ))),
    [giveaways, now],
  )

  return (
    <div className="relative min-h-screen tab-theme-giveaways giveaways-module" aria-hidden={!isActive}>
      <FarmBackground />
      <TabAtmosphere variant="giveaways" />

      <div className="relative z-10 giveaways-shell py-4 pb-2 animate-slide-up">
        <header className="giveaways-header">
          <p className="giveaways-header-eyebrow">Cute</p>
          <h1 className="giveaways-header-title">Розыгрыши</h1>
        </header>

        <div className="segment-tabs" role="tablist" aria-label="Разделы розыгрышей">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`segment-tab${tab === t.id ? ' segment-tab-active' : ''}`}
              onClick={() => handleTabChange(t.id)}
            >
              {t.label}{t.id === 'active' ? ` (${activeList.length})` : ''}
            </button>
          ))}
        </div>

        {error && <p className="giveaways-empty">{error}</p>}

        {tab !== 'past' && initialLoading ? (
          <p className="giveaways-empty">Загрузка…</p>
        ) : tab === 'active' ? (
          activeList.length === 0 ? (
            <div className="giveaways-empty">
              <span className="giveaways-empty-icon" aria-hidden>🎁</span>
              <p>Скоро здесь появятся розыгрыши призов</p>
            </div>
          ) : (
            <div className="giveaways-ticket-grid">
              {activeList.map((giveaway) => (
                <GiveawayTicketCard
                  key={giveaway.id}
                  giveaway={giveaway}
                  onOpenDetail={handleOpenDetail}
                  onSwipeParticipate={participate}
                />
              ))}
            </div>
          )
        ) : tab === 'upcoming' ? (
          upcomingList.length === 0 ? (
            <div className="giveaways-empty">
              <span className="giveaways-empty-icon" aria-hidden>⌛</span>
              <p>Анонсов пока нет, загляните позже</p>
            </div>
          ) : (
            <div className="giveaways-ticket-grid">
              {upcomingList.map((giveaway) => (
                <GiveawayTicketCard
                  key={giveaway.id}
                  giveaway={giveaway}
                  onOpenDetail={handleOpenDetail}
                  onSwipeParticipate={participate}
                />
              ))}
            </div>
          )
        ) : history.loading || history.giveaways === null ? (
          <p className="giveaways-empty">Загрузка…</p>
        ) : history.giveaways.length === 0 ? (
          <div className="giveaways-empty">
            <span className="giveaways-empty-icon" aria-hidden>🏆</span>
            <p>Прошедших розыгрышей пока не было</p>
          </div>
        ) : (
          <div className="giveaways-history-list">
            {history.giveaways.map((giveaway) => (
              <GiveawayHistoryCard key={giveaway.id} giveaway={giveaway} />
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
        error={openId ? error : null}
      />
    </div>
  )
}
```

(The winners feed component is deliberately not wired in yet — it doesn't exist until Task 8. Wiring it here now would break the build. Task 8 adds `<GiveawayWinnersFeed />` back into this file.)

- [ ] **Step 3: Add CSS for the history list/card**

In `src/styles/giveaways.css`, append at the end of the file:

```css
.giveaways-history-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.giveaway-history-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 0.9rem;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.3);
}

.giveaway-history-emoji {
  flex-shrink: 0;
  font-size: 1.8rem;
  opacity: 0.75;
}

.giveaway-history-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.giveaway-history-title {
  font-size: 0.85rem;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.giveaway-history-result {
  font-size: 0.7rem;
  color: rgba(245, 240, 224, 0.65);
}

.giveaway-history-prize {
  flex-shrink: 0;
  font-size: 0.78rem;
  font-weight: 800;
  color: var(--ticket-accent-strong);
}
```

- [ ] **Step 4: Build**

Run: `npx vite build`
Expected: build succeeds

- [ ] **Step 5: Commit**

```bash
git add src/components/GiveawaysModule.jsx src/components/GiveawayHistoryCard.jsx src/styles/giveaways.css
git commit -m "feat(giveaways): tab switcher (active/upcoming/past), rarity sort, history list"
```

---

### Task 8: Ticket card participants/upcoming, modal upcoming lock, winners feed, final verification

**Files:**
- Modify: `src/components/GiveawayTicketCard.jsx`
- Modify: `src/components/GiveawayDetailModal.jsx`
- Create: `src/components/GiveawayWinnersFeed.jsx`
- Modify: `src/components/GiveawaysModule.jsx`
- Modify: `src/styles/giveaways.css`

**Interfaces:**
- Consumes: `useGiveawayWinnersFeed` (Task 6), `formatGiveawayPrize` (existing), `participantsCount`/`participantsPreview`/`startsAt` fields on giveaway objects (Task 2).
- Produces: nothing new consumed elsewhere — this is the final integration task.

- [ ] **Step 1: `GiveawayTicketCard.jsx` — participants row + upcoming state**

Find:

```jsx
import { useRef, useState } from 'react'
import { RARITY_ACCENT, RARITY_LABEL, formatGiveawayDeadline, formatGiveawayPrize } from '../constants/giveaways'

const SWIPE_THRESHOLD = 90

export default function GiveawayTicketCard({ giveaway, onOpenDetail, onSwipeParticipate }) {
  const [dragX, setDragX] = useState(0)
  const [swiping, setSwiping] = useState(false)
  const dragRef = useRef({ startX: 0, tracking: false })
  const accent = RARITY_ACCENT[giveaway.rarity] ?? RARITY_ACCENT.common
  const isLegendary = giveaway.rarity === 'legendary'

  const canSwipe = giveaway.status === 'active' && !giveaway.joined
    && (giveaway.conditionsCount === 0 || giveaway.conditionsMet)
```

Replace with:

```jsx
import { useRef, useState } from 'react'
import { RARITY_ACCENT, RARITY_LABEL, formatGiveawayDeadline, formatGiveawayPrize } from '../constants/giveaways'

const SWIPE_THRESHOLD = 90

function initial(name) {
  const clean = name.replace(/^@/, '')
  return clean.charAt(0).toUpperCase() || '?'
}

export default function GiveawayTicketCard({ giveaway, onOpenDetail, onSwipeParticipate }) {
  const [dragX, setDragX] = useState(0)
  const [swiping, setSwiping] = useState(false)
  const dragRef = useRef({ startX: 0, tracking: false })
  const accent = RARITY_ACCENT[giveaway.rarity] ?? RARITY_ACCENT.common
  const isLegendary = giveaway.rarity === 'legendary'
  const isUpcoming = Boolean(giveaway.startsAt) && new Date(giveaway.startsAt).getTime() > Date.now()

  const canSwipe = giveaway.status === 'active' && !giveaway.joined && !isUpcoming
    && (giveaway.conditionsCount === 0 || giveaway.conditionsMet)
```

Find:

```jsx
  const deadline = giveaway.drawType === 'timer' ? formatGiveawayDeadline(giveaway.endsAt) : null
  const prizeLabel = formatGiveawayPrize(giveaway.prize)
```

Replace with:

```jsx
  const deadline = !isUpcoming && giveaway.drawType === 'timer' ? formatGiveawayDeadline(giveaway.endsAt) : null
  const startLabel = isUpcoming ? formatGiveawayDeadline(giveaway.startsAt) : null
  const prizeLabel = formatGiveawayPrize(giveaway.prize)
```

Find:

```jsx
          <span className="giveaway-ticket-title">{giveaway.title}</span>
          {statusLabel && <span className="giveaway-ticket-status">{statusLabel}</span>}
          {canSwipe && !statusLabel && (
            <span className="giveaway-ticket-swipe-hint">Смахните →</span>
          )}
        </div>
      </div>
      <div className="giveaway-ticket-footer">
        {deadline && <span className="giveaway-ticket-chip">⏳ До {deadline}</span>}
        <span className="giveaway-ticket-chip giveaway-ticket-chip--prize">{prizeLabel}</span>
      </div>
    </button>
  )
}
```

Replace with:

```jsx
          <span className="giveaway-ticket-title">{giveaway.title}</span>
          {statusLabel && <span className="giveaway-ticket-status">{statusLabel}</span>}
          {canSwipe && !statusLabel && (
            <span className="giveaway-ticket-swipe-hint">Смахните →</span>
          )}
          {isUpcoming && !statusLabel && (
            <span className="giveaway-ticket-swipe-hint">⏳ Скоро</span>
          )}
        </div>
      </div>
      <div className="giveaway-ticket-footer">
        {startLabel && <span className="giveaway-ticket-chip">🚀 Старт {startLabel}</span>}
        {deadline && <span className="giveaway-ticket-chip">⏳ До {deadline}</span>}
        <span className="giveaway-ticket-chip giveaway-ticket-chip--prize">{prizeLabel}</span>
      </div>
      {giveaway.participantsCount > 0 && (
        <div className="giveaway-ticket-participants">
          <div className="giveaway-ticket-avatars">
            {(giveaway.participantsPreview ?? []).slice(0, 4).map((name, i) => (
              <span key={i} className="giveaway-ticket-avatar">{initial(name)}</span>
            ))}
          </div>
          <span className="giveaway-ticket-participants-count">👥 {giveaway.participantsCount} участников</span>
        </div>
      )}
    </button>
  )
}
```

- [ ] **Step 2: `GiveawayDetailModal.jsx` — upcoming lock in zone 3**

Find:

```jsx
  if (!isOpen || !giveawayId) return null

  const accent = detail ? (RARITY_ACCENT[detail.rarity] ?? RARITY_ACCENT.common) : RARITY_ACCENT.common
```

Replace with:

```jsx
  if (!isOpen || !giveawayId) return null

  const accent = detail ? (RARITY_ACCENT[detail.rarity] ?? RARITY_ACCENT.common) : RARITY_ACCENT.common
  const isUpcoming = Boolean(detail?.startsAt) && new Date(detail.startsAt).getTime() > Date.now()
```

Find:

```jsx
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
                  {isParticipating
                    ? 'Секунду…'
                    : detail.conditionsMet
                      ? 'Участвовать'
                      : <>🔒 Завершите задания</>}
                </button>
              )}
```

Replace with:

```jsx
              ) : detail.joined ? (
                <div className="giveaway-detail-joined">
                  {detail.drawType === 'instant' ? '✅ Приз получен' : '🎟️ Вы участвуете, ждите розыгрыша'}
                </div>
              ) : isUpcoming ? (
                <button type="button" className="giveaway-detail-cta" disabled>
                  ⏳ {formatGiveawayDeadlineTime(detail.startsAt)}
                </button>
              ) : (
                <button
                  type="button"
                  className={`giveaway-detail-cta${detail.conditionsMet ? ' giveaway-detail-cta--ready' : ''}`}
                  disabled={!detail.conditionsMet || isParticipating}
                  onClick={() => onParticipate(detail.id)}
                >
                  {isParticipating
                    ? 'Секунду…'
                    : detail.conditionsMet
                      ? 'Участвовать'
                      : <>🔒 Завершите задания</>}
                </button>
              )}
```

- [ ] **Step 3: Create `GiveawayWinnersFeed.jsx`**

Create `src/components/GiveawayWinnersFeed.jsx`:

```jsx
import { useEffect, useState } from 'react'
import { useGiveawayWinnersFeed } from '../hooks/useGiveawayWinnersFeed'
import { formatGiveawayPrize } from '../constants/giveaways'

const ROTATE_MS = 4000

function timeAgo(iso) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.max(1, Math.round(diffMs / 60000))
  if (minutes < 60) return `${minutes} мин. назад`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} ч. назад`
  const days = Math.round(hours / 24)
  return `${days} дн. назад`
}

export default function GiveawayWinnersFeed() {
  const { winners } = useGiveawayWinnersFeed()
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (winners.length < 2) return undefined
    const timer = window.setInterval(() => {
      setIndex((i) => (i + 1) % winners.length)
    }, ROTATE_MS)
    return () => window.clearInterval(timer)
  }, [winners.length])

  if (winners.length === 0) return null

  const current = winners[index % winners.length]

  return (
    <div className="giveaway-winners-feed" key={current.at}>
      <span aria-hidden>🎉</span>
      <span className="giveaway-winners-feed-text">
        {current.displayName} выиграл {formatGiveawayPrize(current.prize)} в «{current.giveawayTitle}» · {timeAgo(current.at)}
      </span>
    </div>
  )
}
```

- [ ] **Step 4: Wire the feed into `GiveawaysModule.jsx`**

In `src/components/GiveawaysModule.jsx`, find:

```jsx
import GiveawayHistoryCard from './GiveawayHistoryCard'
import { useGiveaways } from '../hooks/useGiveaways'
```

Replace with:

```jsx
import GiveawayHistoryCard from './GiveawayHistoryCard'
import GiveawayWinnersFeed from './GiveawayWinnersFeed'
import { useGiveaways } from '../hooks/useGiveaways'
```

Find:

```jsx
      </div>

      <GiveawayDetailModal
```

Replace with:

```jsx
      </div>

      <GiveawayWinnersFeed />

      <GiveawayDetailModal
```

- [ ] **Step 5: Add the remaining CSS (participants row, winners feed)**

In `src/styles/giveaways.css`, append at the end of the file:

```css
.giveaway-ticket-participants {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.giveaway-ticket-avatars {
  display: flex;
}

.giveaway-ticket-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.4rem;
  height: 1.4rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  border: 1.5px solid rgba(6, 16, 10, 1);
  color: rgba(245, 240, 224, 0.9);
  font-size: 0.6rem;
  font-weight: 800;
  margin-left: -0.45rem;
}

.giveaway-ticket-avatar:first-child {
  margin-left: 0;
}

.giveaway-ticket-participants-count {
  font-size: 0.66rem;
  font-weight: 600;
  opacity: 0.7;
}

.giveaway-winners-feed {
  position: relative;
  z-index: 10;
  margin: 0.5rem 0.75rem 0;
  padding: 0.55rem 0.85rem;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(253, 230, 138, 0.25);
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.72rem;
  font-weight: 600;
  color: rgba(245, 240, 224, 0.9);
  animation: giveaway-feed-fade 0.4s ease;
}

.giveaway-winners-feed-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes giveaway-feed-fade {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 6: Build and run the full frontend test suite**

Run: `npx vite build`
Expected: build succeeds

Run: `npx vitest run`
Expected: all existing tests still pass (this task doesn't touch any tested pure-logic file)

- [ ] **Step 7: Live browser verification**

Start the dev server, open the webapp, navigate to the «Розыгрыши» tab:

1. Since this environment has no live Postgres (same limitation as v1), confirm via browser console that there are no uncaught JS exceptions and the module renders its empty state gracefully — same graceful-degradation check used throughout v1's live verification.
2. Temporarily inject mock data (3 giveaways: one `active` with `startsAt: null`, one `active` with `startsAt` a few hours in the future, one `completed` with a `winnerName`) into `GiveawaysModule.jsx`/`giveawaysClient.js` the same way it was done for the v1.5 restyle verification (see git history — commit that redesigned `GiveawayTicketCard`/`GiveawayDetailModal` used exactly this technique, then reverted it before committing). Confirm with this mock data:
   - The «Активные (N)» tab count matches only genuinely-active, already-started giveaways.
   - The future-dated one appears under «Скоро» with a "🚀 Старт …" chip and a locked "⏳ …" button in its modal.
   - Switching to «Прошедшие» triggers exactly one `GET /api/giveaways/history`-shaped fetch (visible in Network tab) and renders the mocked completed item via `GiveawayHistoryCard`.
   - The participants row renders when `participantsCount > 0` and is absent when it's `0`.
   - The winners feed renders when winners are present, rotates after 4s if there are 2+, and renders nothing (`null`) when the mock returns an empty array.
3. Revert the temporary mock data before committing (git diff must only contain the real Task 8 changes) — same discipline as the earlier restyle work.

- [ ] **Step 8: Commit**

```bash
git add src/components/GiveawayTicketCard.jsx src/components/GiveawayDetailModal.jsx src/components/GiveawayWinnersFeed.jsx src/components/GiveawaysModule.jsx src/styles/giveaways.css
git commit -m "feat(giveaways): participant previews, upcoming lock in modal, rotating winners feed"
```

---

## Self-Review

**1. Spec coverage:**
- Сегментированный переключатель с счётчиком — Task 7 (`TABS`, `activeList.length`). ✅
- Анонсы (starts_at, блокировка участия, видимость деталей заранее) — Task 1 (колонка+bucket), Task 2 (guard+поля), Task 8 (UI lock в карточке и модалке, детали доступны всегда). ✅
- Прошедшие: ник победителя (timer) / число получивших приз (instant) — Task 3 (`get_giveaways_history`), Task 7 (`GiveawayHistoryCard`). ✅
- Исправление «instant никогда не завершается» — Task 3 (`complete_instant_giveaway`), Task 4 (admin route), Task 5 (кнопка «Завершить»). ✅
- Сортировка (легендарные выше) — Task 7 (`sortByRarity`, применена и к active, и к upcoming спискам). ✅
- Участники в карточке (число + инициалы) — Task 2 (`_giveaway_participants`), Task 8 (UI). ✅
- Лента «Счастливчики дня» (timer + instant, ротация, тихо пуста при отсутствии) — Task 3 (`get_giveaway_winners_feed`), Task 6 (hook), Task 8 (`GiveawayWinnersFeed`). ✅
- Админка: дата начала при создании/редактировании — Task 4 (backend), Task 5 (форма+таблица). ✅

**2. Placeholder scan:** Полный код во всех шагах, ни одного "TBD"/"добавь обработку" без реализации. Единственное текстовое пояснение без кода — Task 8 Step 7 (живая браузерная проверка), это инструкция по verification, а не описание нереализованного кода.

**3. Type consistency:**
- `giveaway_bucket(status, starts_at, now)`/`display_name(username, first_name)` — сигнатура одинакова в определении (Task 1) и во всех вызовах (Task 2's `participate_in_giveaway`, Task 2/3's использование `display_name` в `_giveaway_participants`/`get_giveaways_history`/`get_giveaway_winners_feed`).
- Поля JSON: `startsAt`, `participantsCount`, `participantsPreview` — одинаковые имена между `db.py` (Task 2, продюсер) и `GiveawayTicketCard.jsx`/`GiveawayDetailModal.jsx` (Task 8, потребитель).
- `get_giveaways_history`'s ответ (`winnerName`, `recipientsCount`, `drawnAt`, `prize`) — одинаковы между `db.py` (Task 3) и `GiveawayHistoryCard.jsx` (Task 7).
- `get_giveaway_winners_feed`'s ответ (`displayName`, `prize`, `giveawayTitle`, `giveawayEmoji`, `at`) — одинаковы между `db.py` (Task 3) и `GiveawayWinnersFeed.jsx` (Task 8).
- `completeGiveawayAdmin(giveawayId)` (Task 5, `adminClient.js`) вызывает ровно тот путь и метод (`POST .../complete`), что определён в Task 4's `admin_content_giveaway_complete`.
- `useGiveawayHistory()`'s `giveaways === null` sentinel (Task 6) и его использование как условия ленивой загрузки в `handleTabChange` (Task 7) — согласованы.
