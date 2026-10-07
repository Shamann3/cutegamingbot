# -*- coding: utf-8 -*-
"""Книга браков. Пул передаёт вызывающий код, этот модуль сам ни к чему не подключается."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from bot.funcs.marriage_rules import as_aware, person_html, settings_view, tone_after, tone_label, tone_score

_MSK = timezone(timedelta(hours=3))
_ready = False
_cfg_cache = {"mono": 0.0, "body": None}


async def ensure(pool) -> bool:
    global _ready
    if _ready:
        return True
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marriage_book (
                    id BIGSERIAL PRIMARY KEY,
                    payer_id BIGINT NOT NULL,
                    partner_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    price INT NOT NULL DEFAULT 0,
                    state TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    live_at TIMESTAMPTZ,
                    left_at TIMESTAMPTZ,
                    message_id BIGINT
                )
                """
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS marriage_book_payer ON marriage_book (payer_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS marriage_book_partner ON marriage_book (partner_id)"
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marriage_chat (
                    chat_id BIGINT PRIMARY KEY,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marriage_rp_day (
                    pair_key TEXT NOT NULL,
                    verb_id TEXT NOT NULL,
                    day DATE NOT NULL,
                    times INT NOT NULL DEFAULT 1,
                    PRIMARY KEY (pair_key, verb_id, day)
                )
                """
            )
            await conn.execute(
                "ALTER TABLE marriage_rp_day ADD COLUMN IF NOT EXISTS times INT NOT NULL DEFAULT 1"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS charged BOOLEAN NOT NULL DEFAULT FALSE"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS tone_points INT NOT NULL DEFAULT 80"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS tone_day DATE"
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marriage_settings (
                    id INT PRIMARY KEY,
                    body JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_by BIGINT
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marriage_ledger (
                    id BIGSERIAL PRIMARY KEY,
                    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    kind TEXT NOT NULL,
                    payer_id BIGINT NOT NULL,
                    amount INT NOT NULL,
                    chat_id BIGINT NOT NULL DEFAULT 0
                )
                """
            )
            await conn.execute(
                """
                UPDATE marriage_book
                SET tone_day = (NOW() AT TIME ZONE 'Europe/Moscow')::date,
                    tone_points = COALESCE(tone_points, 80)
                WHERE state = 'live' AND tone_day IS NULL
                """
            )
        _ready = True
        return True
    except Exception as e:
        print(f"[marriage] схема: {e}")
        return False


def _row(row) -> Optional[dict]:
    if row is None:
        return None
    return dict(row)


def _lock_ids(*ids: int) -> list:
    keys = []
    for uid in ids:
        try:
            keys.append(int(uid) & 0x7FFFFFFFFFFFFFFF)
        except (TypeError, ValueError):
            continue
    return sorted(set(keys))


async def _lock_people(conn, *ids: int) -> None:
    for key in _lock_ids(*ids):
        await conn.execute("SELECT pg_advisory_xact_lock($1)", key)


async def _release_stale_billing(conn) -> None:
    promoted = await conn.fetch(
        """
        UPDATE marriage_book
        SET state = 'live',
            live_at = COALESCE(live_at, NOW()),
            tone_day = COALESCE(tone_day, (NOW() AT TIME ZONE 'Europe/Moscow')::date)
        WHERE state = 'billing'
          AND charged IS TRUE
          AND created_at < NOW() - INTERVAL '3 minutes'
        RETURNING payer_id, partner_id, chat_id
        """
    )
    await conn.execute(
        """
        UPDATE marriage_book
        SET state = 'gone'
        WHERE state = 'billing'
          AND charged IS NOT TRUE
          AND created_at < NOW() - INTERVAL '3 minutes'
        """
    )
    for row in promoted:
        people = [int(row["payer_id"]), int(row["partner_id"])]
        await conn.execute(
            """
            UPDATE marriage_book
            SET state = 'gone'
            WHERE state = 'ask'
              AND (payer_id = ANY($1::bigint[]) OR partner_id = ANY($1::bigint[]))
            """,
            people,
        )
        try:
            await mirror_live(None, people[0], people[1], int(row["chat_id"] or 0), conn=conn)
        except Exception:
            continue


async def chat_enabled(pool, chat_id: int) -> bool:
    if not await ensure(pool):
        return True
    async with pool.acquire() as conn:
        flag = await conn.fetchval(
            "SELECT enabled FROM marriage_chat WHERE chat_id = $1",
            int(chat_id),
        )
    return True if flag is None else bool(flag)


async def set_chat(pool, chat_id: int, enabled: bool) -> None:
    if not await ensure(pool):
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO marriage_chat (chat_id, enabled)
            VALUES ($1, $2)
            ON CONFLICT (chat_id) DO UPDATE SET enabled = EXCLUDED.enabled
            """,
            int(chat_id),
            bool(enabled),
        )


async def count_done(pool, payer_id: int) -> int:
    if not await ensure(pool):
        return 0
    async with pool.acquire() as conn:
        n = await conn.fetchval(
            """
            SELECT COUNT(*)::int
            FROM marriage_book
            WHERE payer_id = $1 AND state IN ('live', 'left')
            """,
            int(payer_id),
        )
    return int(n or 0)


async def expire_asks(pool, minutes: int) -> None:
    if not await ensure(pool):
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE marriage_book
            SET state = 'gone'
            WHERE state = 'ask'
              AND created_at < NOW() - make_interval(mins => $1)
            """,
            int(minutes),
        )


async def pending_between(pool, a: int, b: int) -> Optional[dict]:
    if not await ensure(pool):
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, payer_id, partner_id, chat_id, price, state, created_at, message_id
            FROM marriage_book
            WHERE state IN ('ask', 'billing')
              AND (
                    (payer_id = $1 AND partner_id = $2)
                 OR (payer_id = $2 AND partner_id = $1)
                 OR payer_id = $1
                 OR partner_id = $1
                 OR payer_id = $2
                 OR partner_id = $2
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            int(a),
            int(b),
        )
    return _row(row)


async def open_ask(pool, payer_id: int, partner_id: int, chat_id: int, price: int) -> Optional[int]:
    """None — человек уже в заявке, в оплате или в браке. Второй ряд не создаётся."""
    if not await ensure(pool):
        return None
    people = [int(payer_id), int(partner_id)]
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _lock_people(conn, *people)
            await _release_stale_billing(conn)
            book_id = await conn.fetchval(
                """
                INSERT INTO marriage_book (payer_id, partner_id, chat_id, price, state)
                SELECT $1, $2, $3, $4, 'ask'
                WHERE NOT EXISTS (
                    SELECT 1 FROM marriage_book
                    WHERE state IN ('ask', 'billing', 'live')
                      AND (payer_id = ANY($5::bigint[]) OR partner_id = ANY($5::bigint[]))
                )
                RETURNING id
                """,
                people[0],
                people[1],
                int(chat_id),
                int(price),
                people,
            )
    return int(book_id) if book_id is not None else None


async def set_message(pool, book_id: int, message_id: int) -> None:
    if not await ensure(pool):
        return
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE marriage_book SET message_id = $2 WHERE id = $1",
            int(book_id),
            int(message_id),
        )


async def get_book(pool, book_id: int) -> Optional[dict]:
    if not await ensure(pool):
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, payer_id, partner_id, chat_id, price, state,
                   created_at, live_at, left_at, message_id
            FROM marriage_book
            WHERE id = $1
            """,
            int(book_id),
        )
    return _row(row)


async def claim_ask(pool, book_id: int, minutes: int) -> Optional[dict]:
    """Переводит заявку в billing, если она ещё ждёт, не протухла и оба свободны."""
    if not await ensure(pool):
        return None
    async with pool.acquire() as conn:
        async with conn.transaction():
            who = await conn.fetchrow(
                "SELECT payer_id, partner_id FROM marriage_book WHERE id = $1",
                int(book_id),
            )
            if not who:
                return None
            await _lock_people(conn, int(who["payer_id"]), int(who["partner_id"]))
            await _release_stale_billing(conn)
            row = await conn.fetchrow(
                """
                UPDATE marriage_book AS m
                SET state = 'billing'
                WHERE m.id = $1
                  AND m.state = 'ask'
                  AND m.created_at >= NOW() - make_interval(mins => $2)
                  AND NOT EXISTS (
                        SELECT 1 FROM marriage_book AS o
                        WHERE o.id <> m.id
                          AND o.state IN ('live', 'billing')
                          AND (
                                o.payer_id IN (m.payer_id, m.partner_id)
                             OR o.partner_id IN (m.payer_id, m.partner_id)
                          )
                  )
                RETURNING id, payer_id, partner_id, chat_id, price, state, message_id
                """,
                int(book_id),
                int(minutes),
            )
    return _row(row)


async def mark_charged(pool, book_id: int) -> None:
    if not await ensure(pool):
        return
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE marriage_book SET charged = TRUE WHERE id = $1",
            int(book_id),
        )


async def finish(pool, book_id: int, state: str, tone_points: Optional[int] = None, tone_day=None) -> None:
    if not await ensure(pool):
        return
    live = datetime.now(timezone.utc) if state == "live" else None
    left = datetime.now(timezone.utc) if state == "left" else None
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE marriage_book
            SET state = $2,
                live_at = COALESCE($3, live_at),
                left_at = COALESCE($4, left_at),
                tone_points = COALESCE($5, tone_points),
                tone_day = COALESCE($6, tone_day)
            WHERE id = $1
            """,
            int(book_id),
            str(state),
            live,
            left,
            tone_points,
            tone_day,
        )
        if state == "live":
            await conn.execute(
                """
                UPDATE marriage_book
                SET state = 'gone'
                WHERE state = 'ask'
                  AND id <> $1
                  AND (
                        payer_id IN (SELECT payer_id FROM marriage_book WHERE id = $1)
                     OR partner_id IN (SELECT payer_id FROM marriage_book WHERE id = $1)
                     OR payer_id IN (SELECT partner_id FROM marriage_book WHERE id = $1)
                     OR partner_id IN (SELECT partner_id FROM marriage_book WHERE id = $1)
                  )
                """,
                int(book_id),
            )


async def close_ask(pool, book_id: int, state: str) -> Optional[dict]:
    if not await ensure(pool):
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE marriage_book
            SET state = $2
            WHERE id = $1 AND state = 'ask'
            RETURNING id, payer_id, partner_id, chat_id, message_id
            """,
            int(book_id),
            str(state),
        )
    return _row(row)


async def live_for(pool, user_id: int) -> Optional[dict]:
    """Живой брак из книги, иначе старая таблица marriages."""
    if not await ensure(pool):
        return None
    uid = int(user_id)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, payer_id, partner_id, chat_id, price, live_at, tone_points, tone_day
            FROM marriage_book
            WHERE state = 'live' AND (payer_id = $1 OR partner_id = $1)
            ORDER BY live_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            uid,
        )
        if row:
            data = dict(row)
            data["source"] = "book"
            return data
        old = await conn.fetchrow(
            """
            SELECT user_id1, user_id2, chat_id, datetime
            FROM marriages
            WHERE status = 1 AND (user_id1 = $1 OR user_id2 = $1)
            ORDER BY datetime DESC NULLS LAST
            LIMIT 1
            """,
            uid,
        )
    if not old:
        return None
    return {
        "id": None,
        "payer_id": int(old["user_id1"]),
        "partner_id": int(old["user_id2"]),
        "chat_id": int(old["chat_id"] or 0),
        "price": 0,
        "live_at": as_aware(old["datetime"]),
        "source": "old",
    }


async def mirror_live(pool, payer_id: int, partner_id: int, chat_id: int, conn=None) -> None:
    if pool is None and conn is None:
        return
    when = datetime.now(_MSK).replace(tzinfo=None)

    async def _write(target) -> None:
        await target.execute(
            """
            DELETE FROM marriages
            WHERE (user_id1 = $1 AND user_id2 = $2)
               OR (user_id1 = $2 AND user_id2 = $1)
            """,
            int(payer_id),
            int(partner_id),
        )
        await target.execute(
            """
            INSERT INTO marriages (user_id1, user_id2, status, datetime, chat_id)
            VALUES ($1, $2, 1, $3, $4)
            """,
            int(payer_id),
            int(partner_id),
            when,
            int(chat_id),
        )

    if conn is not None:
        await _write(conn)
        return
    async with pool.acquire() as owned:
        await _write(owned)


async def mirror_end(pool, a: int, b: int) -> None:
    if pool is None:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM marriages
            WHERE (user_id1 = $1 AND user_id2 = $2)
               OR (user_id1 = $2 AND user_id2 = $1)
            """,
            int(a),
            int(b),
        )


async def record_old_divorce(pool, payer_id: int, partner_id: int, chat_id: int) -> None:
    """Старый брак без строки в книге тоже считается свадьбой того, кто был user_id1."""
    if not await ensure(pool):
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO marriage_book (payer_id, partner_id, chat_id, price, state, live_at, left_at)
            VALUES ($1, $2, $3, 0, 'left', NOW(), NOW())
            """,
            int(payer_id),
            int(partner_id),
            int(chat_id),
        )


def pair_key(a: int, b: int) -> str:
    x, y = sorted((int(a), int(b)))
    return f"{x}:{y}"


async def rp_taken(pool, a: int, b: int, verb_id: str, day, limit: int = 1) -> bool:
    if not await ensure(pool):
        return False
    cap = max(1, int(limit))
    async with pool.acquire() as conn:
        times = await conn.fetchval(
            """
            SELECT times FROM marriage_rp_day
            WHERE pair_key = $1 AND verb_id = $2 AND day = $3
            """,
            pair_key(a, b),
            str(verb_id),
            day,
        )
    return int(times or 0) >= cap


async def mark_rp(pool, a: int, b: int, verb_id: str, day, limit: int = 1) -> bool:
    """True, если сегодня этот жест ещё помещается в лимит и мы его заняли."""
    if not await ensure(pool):
        return False
    cap = max(1, int(limit))
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO marriage_rp_day (pair_key, verb_id, day, times)
            VALUES ($1, $2, $3, 1)
            ON CONFLICT (pair_key, verb_id, day)
            DO UPDATE SET times = marriage_rp_day.times + 1
            WHERE marriage_rp_day.times < $4
            RETURNING times
            """,
            pair_key(a, b),
            str(verb_id),
            day,
            cap,
        )
    return row is not None


async def names(pool, user_ids: list) -> dict:
    ids = [int(i) for i in user_ids if i]
    if not ids or pool is None:
        return {}
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, first_name, username
            FROM users
            WHERE user_id = ANY($1::bigint[])
            """,
            ids,
        )
    out = {}
    for row in rows:
        out[int(row["user_id"])] = person_html(
            int(row["user_id"]),
            row["first_name"] or "",
            row["username"] or "",
        )
    return out


async def load_settings(pool) -> dict:
    import time
    now = time.monotonic()
    cached = _cfg_cache.get("body")
    if cached is not None and now - float(_cfg_cache.get("mono") or 0) < 15:
        return cached
    raw = None
    if pool is not None and await ensure(pool):
        try:
            async with pool.acquire() as conn:
                raw = await conn.fetchval("SELECT body FROM marriage_settings WHERE id = 1")
        except Exception:
            raw = None
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    view = settings_view(raw if isinstance(raw, dict) else None)
    _cfg_cache["mono"] = now
    _cfg_cache["body"] = view
    return view


def drop_settings_cache() -> None:
    _cfg_cache["mono"] = 0.0
    _cfg_cache["body"] = None


async def save_settings(pool, body: dict, updated_by: int = 0) -> dict:
    import json
    view = settings_view(body)
    if not await ensure(pool):
        return view
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO marriage_settings (id, body, updated_at, updated_by)
            VALUES (1, $1::jsonb, NOW(), $2)
            ON CONFLICT (id) DO UPDATE
            SET body = EXCLUDED.body,
                updated_at = NOW(),
                updated_by = EXCLUDED.updated_by
            """,
            json.dumps(view, ensure_ascii=False),
            int(updated_by or 0),
        )
    drop_settings_cache()
    return view


async def note_money(pool, kind: str, payer_id: int, amount: int, chat_id: int = 0) -> None:
    if not await ensure(pool) or int(amount) == 0:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO marriage_ledger (kind, payer_id, amount, chat_id)
            VALUES ($1, $2, $3, $4)
            """,
            str(kind),
            int(payer_id),
            int(amount),
            int(chat_id or 0),
        )


async def add_tone(pool, book_id: int, today, decay: int, gain: int):
    if not book_id or not await ensure(pool):
        return None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT tone_points, tone_day, live_at
                FROM marriage_book
                WHERE id = $1 AND state = 'live'
                FOR UPDATE
                """,
                int(book_id),
            )
            if not row:
                return None
            score, day = tone_after(
                row["tone_points"], row["tone_day"], today, decay, gain, row["live_at"],
            )
            await conn.execute(
                "UPDATE marriage_book SET tone_points = $2, tone_day = $3 WHERE id = $1",
                int(book_id),
                int(score),
                day,
            )
    return int(score)


def describe_tone(live: Optional[dict], today, decay: int, tone_on: bool = True) -> str:
    if not live or not tone_on:
        return ""
    if live.get("source") == "old" and live.get("tone_day") is None and live.get("tone_points") is None:
        return ""
    score = tone_score(
        live.get("tone_points") if live.get("tone_points") is not None else 80,
        live.get("tone_day"),
        today,
        decay,
        live.get("live_at"),
    )
    return f"Тонус {score} · {tone_label(score)}"


async def load_profile(pool, user_id: int) -> Optional[dict]:
    if pool is None or not await ensure(pool):
        return None
    live = await live_for(pool, user_id)
    if not live:
        cfg = await load_settings(pool)
        if not cfg.get("showEmptyProfile", True):
            return {"name_html": "", "since": None, "hide_empty": True}
        return {"name_html": "", "since": None}
    other = int(live["partner_id"] if int(live["payer_id"]) == int(user_id) else live["payer_id"])
    found = await names(pool, [other])
    cfg = await load_settings(pool)
    tone = ""
    if cfg.get("toneOn") and live.get("id"):
        score = tone_score(
            live.get("tone_points") if live.get("tone_points") is not None else cfg.get("toneStart", 80),
            live.get("tone_day"),
            datetime.now(_MSK).date(),
            int(cfg.get("toneDecay") or 0),
            live.get("live_at"),
        )
        tone = f"тонус {score}"
    return {
        "name_html": found.get(other) or person_html(other, "игрок", ""),
        "since": live.get("live_at"),
        "tone_label": tone,
    }


async def top_pairs(pool, chat_id: int, limit: int) -> list:
    if not await ensure(pool):
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT payer_id, partner_id, live_at, tone_points, tone_day
            FROM marriage_book
            WHERE state = 'live' AND chat_id = $1 AND live_at IS NOT NULL
            ORDER BY live_at ASC
            LIMIT $2
            """,
            int(chat_id),
            int(limit),
        )
        old_rows = await conn.fetch(
            """
            SELECT user_id1, user_id2, datetime
            FROM marriages
            WHERE status = 1 AND chat_id = $1
            """,
            int(chat_id),
        )
    seen = set()
    out = []
    for row in rows:
        key = pair_key(row["payer_id"], row["partner_id"])
        seen.add(key)
        out.append({
            "a": int(row["payer_id"]),
            "b": int(row["partner_id"]),
            "since": row["live_at"],
            "tone_points": row["tone_points"],
            "tone_day": row["tone_day"],
        })
    for row in old_rows:
        key = pair_key(row["user_id1"], row["user_id2"])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "a": int(row["user_id1"]),
            "b": int(row["user_id2"]),
            "since": as_aware(row["datetime"]),
            "tone_points": None,
            "tone_day": None,
        })
    out.sort(key=lambda item: as_aware(item["since"]) or datetime.max.replace(tzinfo=timezone.utc))
    return out[: int(limit)]
