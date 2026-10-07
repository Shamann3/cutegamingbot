# -*- coding: utf-8 -*-
"""Книга браков. Пул передаёт вызывающий код, этот модуль сам ни к чему не подключается."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from marriage_engine.rules import (
    add_spark_care,
    as_aware,
    gift_catalog,
    gift_plan,
    person_html,
    settings_view,
    settle_spark,
    spark_side,
    spark_split,
    tone_after,
    tone_label,
    tone_score,
)

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
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS spark_days INT NOT NULL DEFAULT 0"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS spark_best INT NOT NULL DEFAULT 0"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS care_total INT NOT NULL DEFAULT 0"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS care_payer INT NOT NULL DEFAULT 0"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS care_partner INT NOT NULL DEFAULT 0"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS spark_day DATE"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS fade_until TIMESTAMPTZ"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS spark_lost INT NOT NULL DEFAULT 0"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS ribbon BOOLEAN NOT NULL DEFAULT FALSE"
            )
            try:
                await _ensure_gifts(conn)
            except Exception as gift_err:
                print(f"[marriage] предметы: {gift_err}")
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
            today = datetime.now(_MSK).date()
            await conn.execute(
                """
                UPDATE marriage_book
                SET spark_day = $2,
                    spark_days = 0,
                    care_payer = 0,
                    care_partner = 0,
                    fade_until = NULL,
                    spark_lost = 0
                WHERE id = $1
                """,
                int(book_id),
                today,
            )
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
            SELECT id, payer_id, partner_id, chat_id, price, live_at, tone_points, tone_day,
                   spark_days, spark_best, care_total, care_payer, care_partner,
                   spark_day, fade_until, spark_lost, ribbon
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
        try:
            await _ensure_gifts(conn)
        except Exception as gift_err:
            print(f"[marriage] цены предметов: {gift_err}")
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


def _spark_raw(row: dict) -> dict:
    return {
        "spark_days": row.get("spark_days"),
        "spark_best": row.get("spark_best"),
        "care_total": row.get("care_total"),
        "care_payer": row.get("care_payer"),
        "care_partner": row.get("care_partner"),
        "spark_day": row.get("spark_day"),
        "fade_until": row.get("fade_until"),
        "spark_lost": row.get("spark_lost"),
    }


async def _save_spark(conn, book_id: int, state: dict) -> None:
    await conn.execute(
        """
        UPDATE marriage_book
        SET spark_days = $2,
            spark_best = $3,
            care_total = $4,
            care_payer = $5,
            care_partner = $6,
            spark_day = $7,
            fade_until = $8,
            spark_lost = $9
        WHERE id = $1 AND state = 'live'
        """,
        int(book_id),
        int(state.get("spark_days") or 0),
        int(state.get("spark_best") or 0),
        int(state.get("care_total") or 0),
        int(state.get("care_payer") or 0),
        int(state.get("care_partner") or 0),
        state.get("spark_day"),
        state.get("fade_until"),
        int(state.get("spark_lost") or 0),
    )


async def spark_sync(pool, live: dict, user_id: int, cfg: dict, care: int = 0, acknowledge: bool = False):
    """Сводит прошедшие дни и, если care > 0, добавляет заботу этому человеку."""
    if pool is None or not live or not live.get("id") or not cfg.get("sparkOn", True):
        return None
    if not await ensure(pool):
        return None
    hours = int(cfg.get("rescueHours") or 12)
    now = datetime.now(_MSK)
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT payer_id, spark_days, spark_best, care_total, care_payer, care_partner,
                       spark_day, fade_until, spark_lost
                FROM marriage_book
                WHERE id = $1 AND state = 'live'
                FOR UPDATE
                """,
                int(live["id"]),
            )
            if not row:
                return None
            raw = _spark_raw(dict(row))
            if int(care or 0) > 0:
                view = add_spark_care(
                    raw, spark_side(user_id, row["payer_id"]), int(care), now, hours, cfg,
                )
            else:
                view = settle_spark(raw, now, hours, cfg)
            shown = int(view.get("lost") or 0)
            if acknowledge and shown:
                view["state"]["spark_lost"] = 0
            await _save_spark(conn, int(live["id"]), view["state"])
            view["lost"] = shown
            you, other = spark_split(view["state"], user_id, row["payer_id"])
            view["you"] = you
            view["partner_care"] = other
    return view


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
    if cfg.get("sparkOn", True) and live.get("id"):
        try:
            view = await spark_sync(pool, live, user_id, cfg, 0, False)
        except Exception:
            view = None
        if view:
            if view.get("fading"):
                tone = "искра гаснет"
            elif int(view.get("lost") or 0) > 0:
                tone = "искра погасла"
            elif int((view.get("state") or {}).get("spark_days") or 0) > 0:
                tone = f"искра {int(view['state']['spark_days'])}"
            else:
                tone = "новая искра"
        if live.get("ribbon"):
            tone = f"{tone} · лента" if tone else "лента"
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
            SELECT payer_id, partner_id, live_at, tone_points, tone_day,
                   spark_days, fade_until
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
            "spark_days": row["spark_days"],
            "fade_until": row["fade_until"],
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
            "spark_days": None,
            "fade_until": None,
        })
    out.sort(key=lambda item: as_aware(item["since"]) or datetime.max.replace(tzinfo=timezone.utc))
    return out[: int(limit)]


def _gift_keys(gift: dict, dex_id: Any = None) -> set:
    keys = {str(gift.get("name") or ""), str(gift.get("name1") or "")}
    if dex_id is not None:
        keys.add(str(dex_id))
    keys.discard("")
    return keys


def _count_items(items: dict, gift: dict, dex_id: Any = None) -> int:
    keys = _gift_keys(gift, dex_id)
    total = 0
    for key, value in (items or {}).items():
        if str(key) not in keys:
            continue
        try:
            total += int(value or 0)
        except (TypeError, ValueError):
            continue
    return max(0, total)


def _take_one(items: dict, gift: dict, dex_id: Any = None) -> dict:
    keys = _gift_keys(gift, dex_id)
    stored = dict(items or {})
    for key in list(stored.keys()):
        if str(key) not in keys:
            continue
        try:
            have = int(stored.get(key) or 0)
        except (TypeError, ValueError):
            have = 0
        if have <= 0:
            continue
        if have == 1:
            stored.pop(key, None)
        else:
            stored[key] = have - 1
        return stored
    return stored


async def _ensure_gifts(conn) -> None:
    """Три предмета на полке сердец. Цена берётся из настроек брака."""
    import json
    from marriage_engine.design import HEARTS_SHELF

    raw = await conn.fetchval("SELECT body FROM marriage_settings WHERE id = 1")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    cfg = settings_view(raw if isinstance(raw, dict) else None)
    for gift in gift_catalog(cfg):
        row = await conn.fetchrow("SELECT id FROM dex WHERE name1 = $1", gift["name1"])
        if row:
            await conn.execute(
                "UPDATE dex SET price = $2, sorting = $3, name = $4, emoji = $5 WHERE id = $1",
                int(row["id"]),
                int(gift["price"]),
                HEARTS_SHELF,
                gift["name"],
                gift["emoji"],
            )
            continue
        new_id = await conn.fetchval("SELECT COALESCE(MAX(id), 0) + 1 FROM dex")
        await conn.execute(
            """
            INSERT INTO dex (id, name, name1, emoji, price, dis, remains, sorting, bio)
            VALUES ($1, $2, $3, $4, $5, 0, 1000000, $6, $7)
            """,
            int(new_id),
            gift["name"],
            gift["name1"],
            gift["emoji"],
            int(gift["price"]),
            HEARTS_SHELF,
            "Для брака. Кнопка «Предметы» в карточке «Мой брак».",
        )


async def _dex_id(conn, name1: str):
    return await conn.fetchval("SELECT id FROM dex WHERE name1 = $1", name1)


async def gift_stock(pool, user_id: int, cfg: dict) -> list:
    from bot.db_create.items_codec import decode_items

    rows = gift_catalog(cfg)
    if pool is None:
        return [{**row, "have": 0} for row in rows]
    async with pool.acquire() as conn:
        raw = await conn.fetchval("SELECT items FROM users WHERE user_id = $1", int(user_id))
        items = decode_items(raw)
        out = []
        for row in rows:
            dex_id = await _dex_id(conn, row["name1"])
            out.append({**row, "have": _count_items(items, row, dex_id)})
    return out


async def grant_gift(pool, user_id: int, kind: str, qty: int = 1) -> bool:
    from bot.db_create.items_codec import decode_items, encode_items

    gift = next((row for row in gift_catalog(None) if row["id"] == kind), None)
    if gift is None or pool is None or int(qty) <= 0:
        return False
    if not await ensure(pool):
        return False
    async with pool.acquire() as conn:
        async with conn.transaction():
            raw = await conn.fetchval(
                "SELECT items FROM users WHERE user_id = $1 FOR UPDATE",
                int(user_id),
            )
            if raw is None and await conn.fetchval("SELECT 1 FROM users WHERE user_id = $1", int(user_id)) is None:
                return False
            items = decode_items(raw)
            dex_id = await _dex_id(conn, gift["name1"])
            key = str(dex_id) if dex_id is not None else gift["name"]
            try:
                have = int(items.get(key) or 0)
            except (TypeError, ValueError):
                have = 0
            items[key] = have + int(qty)
            await conn.execute(
                "UPDATE users SET items = $2 WHERE user_id = $1",
                int(user_id),
                encode_items(items),
            )
            if dex_id is not None:
                await conn.execute(
                    "UPDATE dex SET remains = remains - $2 WHERE id = $1 AND remains >= $2",
                    int(dex_id),
                    int(qty),
                )
    return True


async def use_gift(pool, live: dict, user_id: int, kind: str, cfg: dict) -> dict:
    """Списывает один предмет и применяет только долю нажавшего."""
    from bot.db_create.items_codec import decode_items, encode_items

    if pool is None or not live or not live.get("id"):
        return {"ok": False, "reason": "old"}
    gift = next((row for row in gift_catalog(cfg) if row["id"] == kind), None)
    if gift is None:
        return {"ok": False, "reason": "bad"}
    hours = int(cfg.get("rescueHours") or 12)
    now = datetime.now(_MSK)
    async with pool.acquire() as conn:
        async with conn.transaction():
            raw_items = await conn.fetchval(
                "SELECT items FROM users WHERE user_id = $1 FOR UPDATE",
                int(user_id),
            )
            items = decode_items(raw_items)
            dex_id = await _dex_id(conn, gift["name1"])
            if _count_items(items, gift, dex_id) < 1:
                return {"ok": False, "reason": "none"}
            row = await conn.fetchrow(
                """
                SELECT payer_id, spark_days, spark_best, care_total, care_payer, care_partner,
                       spark_day, fade_until, spark_lost, ribbon
                FROM marriage_book
                WHERE id = $1 AND state = 'live'
                FOR UPDATE
                """,
                int(live["id"]),
            )
            if not row:
                return {"ok": False, "reason": "old"}
            view = settle_spark(_spark_raw(dict(row)), now, hours, cfg)
            you, _other = spark_split(view["state"], int(user_id), int(row["payer_id"]))
            plan = gift_plan(
                kind,
                bool(view.get("fading")),
                you,
                int(view.get("need") or 0),
                bool(row["ribbon"]),
                int(gift["care"] or 0),
            )
            if not plan["ok"]:
                return {"ok": False, "reason": plan["reason"]}
            items = _take_one(items, gift, dex_id)
            await conn.execute(
                "UPDATE users SET items = $2 WHERE user_id = $1",
                int(user_id),
                encode_items(items),
            )
            if kind == "ribbon":
                await conn.execute(
                    "UPDATE marriage_book SET ribbon = TRUE WHERE id = $1",
                    int(live["id"]),
                )
            elif int(plan["care"] or 0) > 0:
                view = add_spark_care(
                    view["state"],
                    spark_side(int(user_id), int(row["payer_id"])),
                    int(plan["care"]),
                    now,
                    hours,
                    cfg,
                )
                await _save_spark(conn, int(live["id"]), view["state"])
            left = _count_items(items, gift, dex_id)
    return {"ok": True, "reason": "", "left": left, "care": int(plan["care"] or 0)}
