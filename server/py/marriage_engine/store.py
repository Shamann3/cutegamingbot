# -*- coding: utf-8 -*-
"""Книга браков. Пул передаёт вызывающий код, этот модуль сам ни к чему не подключается."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from marriage_engine.rules import (
    act_plan,
    add_spark_care,
    as_aware,
    gift_catalog,
    nudge_spark,
    person_html,
    seal_today,
    settings_view,
    settle_spark,
    spark_side,
    spark_split,
    moon_up,
    dawn_up,
    face_from_dex,
    own_ribbon,
    tone_after,
    tone_label,
    tone_score,
)

_MSK = timezone(timedelta(hours=3))
_ready = False
_cfg_cache = {"mono": 0.0, "body": None}
_spark_cache: dict = {}


def drop_spark_cache(book_id=None) -> None:
    if book_id is None:
        _spark_cache.clear()
        return
    book = int(book_id)
    for key in [item for item in _spark_cache if item[0] == book]:
        _spark_cache.pop(key, None)


def _spark_same(before: dict, after: dict) -> bool:
    left = _spark_copy_local(before)
    keys = (
        "spark_days", "spark_best", "care_total", "care_payer", "care_partner",
        "spark_day", "spark_lost", "shield", "fade_extra",
    )
    for key in keys:
        if left.get(key) != after.get(key):
            return False

    def clock(value):
        if isinstance(value, datetime):
            return value.replace(microsecond=0)
        return value

    return clock(left.get("fade_until")) == clock(after.get("fade_until"))


def _spark_copy_local(raw: dict) -> dict:
    src = raw or {}
    day = src.get("spark_day")
    if isinstance(day, datetime):
        day = day.date()
    return {
        "spark_days": int(src.get("spark_days") or 0),
        "spark_best": int(src.get("spark_best") or 0),
        "care_total": int(src.get("care_total") or 0),
        "care_payer": int(src.get("care_payer") or 0),
        "care_partner": int(src.get("care_partner") or 0),
        "spark_day": day,
        "fade_until": src.get("fade_until"),
        "spark_lost": int(src.get("spark_lost") or 0),
        "shield": int(src.get("shield") or 0),
        "fade_extra": int(src.get("fade_extra") or 0),
    }


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
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS ribbon_payer BOOLEAN NOT NULL DEFAULT FALSE"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS ribbon_partner BOOLEAN NOT NULL DEFAULT FALSE"
            )
            await conn.execute(
                """
                UPDATE marriage_book
                SET ribbon_payer = TRUE, ribbon_partner = TRUE
                WHERE ribbon = TRUE AND NOT ribbon_payer AND NOT ribbon_partner
                """
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS bond TEXT NOT NULL DEFAULT ''"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS proposer_id BIGINT"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS thread_on BOOLEAN NOT NULL DEFAULT FALSE"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS talk_payer DATE"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS talk_partner DATE"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS quiet_payer DATE"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS quiet_partner DATE"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS wish_done TEXT NOT NULL DEFAULT ''"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS wish_payer TEXT NOT NULL DEFAULT ''"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS wish_partner TEXT NOT NULL DEFAULT ''"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS wish_day INT NOT NULL DEFAULT 0"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS fade_extra INT NOT NULL DEFAULT 0"
            )
            await conn.execute(
                "ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS shield INT NOT NULL DEFAULT 0"
            )
            await conn.execute("ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS vow_payer DATE")
            await conn.execute("ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS vow_partner DATE")
            await conn.execute("ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS bridge_day DATE")
            await conn.execute("ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS warm_payer DATE")
            await conn.execute("ALTER TABLE marriage_book ADD COLUMN IF NOT EXISTS warm_partner DATE")
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
            try:
                await _seed_gifts(conn)
                await _seed_kitchen(conn)
            except Exception as gift_err:
                print(f"[marriage] предметы: {gift_err}")
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
                   spark_day, fade_until, spark_lost, ribbon,
                   ribbon_payer, ribbon_partner,
                   bond, proposer_id, thread_on, talk_payer, talk_partner,
                   wish_done, wish_payer, wish_partner, wish_day
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


async def set_own_ribbon(pool, book_id: int, user_id: int, on: bool) -> bool:
    """Личная лента. Чужую не трогает. Общая колонка остаётся, если лента есть хотя бы у одного."""
    if not await ensure(pool):
        return False
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT payer_id, partner_id, ribbon_payer, ribbon_partner
            FROM marriage_book
            WHERE id = $1 AND state = 'live'
            """,
            int(book_id),
        )
        if not row:
            return False
        uid = int(user_id)
        if uid == int(row["payer_id"]):
            column = "ribbon_payer"
            other = bool(row["ribbon_partner"])
        elif uid == int(row["partner_id"]):
            column = "ribbon_partner"
            other = bool(row["ribbon_payer"])
        else:
            return False
        await conn.execute(
            f"UPDATE marriage_book SET {column} = $2, ribbon = $3 WHERE id = $1",
            int(book_id),
            bool(on),
            bool(on) or other,
        )
    return True


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
    if cached is not None and now - float(_cfg_cache.get("mono") or 0) < 45:
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
    if pool is not None:
        try:
            async with pool.acquire() as conn:
                view = await _overlay_dex(conn, view)
        except Exception:
            pass
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
            await _write_gifts(conn, view)
            await _seed_kitchen(conn, view)
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
        "shield": row.get("shield"),
        "fade_extra": row.get("fade_extra"),
        "talk_payer": row.get("talk_payer"),
        "talk_partner": row.get("talk_partner"),
    }


async def _save_spark(conn, book_id: int, state: dict) -> None:
    drop_spark_cache(book_id)
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
            spark_lost = $9,
            fade_extra = $10,
            shield = $11
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
        int(state.get("fade_extra") or 0),
        int(state.get("shield") or 0),
    )


_SPARK_SQL = """
    SELECT payer_id, spark_days, spark_best, care_total, care_payer, care_partner,
           spark_day, fade_until, spark_lost, fade_extra, shield, talk_payer, talk_partner
    FROM marriage_book
    WHERE id = $1 AND state = 'live'
"""


async def spark_sync(pool, live: dict, user_id: int, cfg: dict, care: int = 0, acknowledge: bool = False):
    """Сводит прошедшие дни. Пока день не сменился, карточка читается без записи."""
    if pool is None or not live or not live.get("id") or not cfg.get("sparkOn", True):
        return None
    if not await ensure(pool):
        return None
    import time
    book = int(live["id"])
    uid = int(user_id)
    stamp = time.monotonic()
    if int(care or 0) <= 0:
        hit = _spark_cache.get((book, uid))
        if hit and stamp - hit[0] < 2:
            return hit[1]
    hours = int(cfg.get("rescueHours") or 12)
    now = datetime.now(_MSK)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SPARK_SQL, book)
        if not row:
            return None
        raw = _spark_raw(dict(row))
        payer = int(row["payer_id"])
        if int(care or 0) > 0:
            view = add_spark_care(raw, spark_side(uid, payer), int(care), now, hours, cfg)
            changed = True
        else:
            view = settle_spark(raw, now, hours, cfg)
            changed = not _spark_same(raw, view["state"])
        if changed:
            async with conn.transaction():
                locked = await conn.fetchrow(_SPARK_SQL + " FOR UPDATE", book)
                if not locked:
                    return None
                raw = _spark_raw(dict(locked))
                payer = int(locked["payer_id"])
                if int(care or 0) > 0:
                    view = add_spark_care(raw, spark_side(uid, payer), int(care), now, hours, cfg)
                else:
                    view = settle_spark(raw, now, hours, cfg)
                await _save_spark(conn, book, view["state"])
        view["lost"] = int(view.get("lost") or 0)
        you, other = spark_split(view["state"], uid, payer)
        view["you"] = you
        view["partner_care"] = other
    if int(care or 0) <= 0:
        _spark_cache[(book, uid)] = (stamp, view)
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
            if int(view.get("lost") or 0) <= 0:
                stage = str((view.get("level") or {}).get("name") or "").strip()
                if stage:
                    tone = f"{tone} · {stage}" if tone else stage
        if tone and live.get("bond") == "family":
            tone = f"{tone} · семья"
        elif tone and live.get("bond") == "bouquet":
            tone = f"{tone} · букет"
        elif tone and live.get("bond") == "propose":
            tone = f"{tone} · предложение"
    return {
        "name_html": found.get(other) or person_html(other, "игрок", ""),
        "since": live.get("live_at"),
        "tone_label": tone,
        "ribbon": own_ribbon(live, user_id),
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


_RETIRED = (
    "mrgword", "mrgbridge", "mrgmirror", "mrgjar", "mrgclock",
    "mrgcoat", "mrgsprout", "mrgseal", "mrgwarm",
)


def _gift_cfg(raw):
    import json
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    return settings_view(raw if isinstance(raw, dict) else None)


async def _insert_dex(conn, name, name1, emoji, price, bio, remains: int = 1000000) -> None:
    """Новая строка dex. Текст для игрока пишется в bio: колонка craft в базе — число."""
    from marriage_engine.design import HEARTS_SHELF
    new_id = await conn.fetchval("SELECT COALESCE(MAX(id), 0) + 1 FROM dex")
    await conn.execute(
        """
        INSERT INTO dex (id, name, name1, emoji, price, dis, remains, sorting, bio)
        VALUES ($1, $2, $3, $4, $5, 0, $6, $7, $8)
        """,
        int(new_id), str(name), str(name1), str(emoji), int(price), int(remains), HEARTS_SHELF, str(bio or ""),
    )


async def _seed_kitchen(conn, cfg=None) -> None:
    """Грядки огурца, помидора и капусты и ужин из них. Повторный запуск ничего не дублирует."""
    await conn.execute("ALTER TABLE farm_crops ADD COLUMN IF NOT EXISTS water_times INT")
    await conn.execute("ALTER TABLE craft_recipes ADD COLUMN IF NOT EXISTS ingredient_c_id TEXT")
    shelf = cfg.get("shelf") if isinstance(cfg, dict) else None
    if not isinstance(shelf, list) or not shelf:
        from marriage_engine.m_helpb import settings_view
        shelf = settings_view(cfg or {}).get("shelf") or []
    grow = {}
    for item in shelf:
        if not isinstance(item, dict) or item.get("effect") != "seed":
            continue
        try:
            minutes = int(item.get("growMin") or 30)
        except (TypeError, ValueError):
            minutes = 30
        try:
            waters = int(item.get("waters") if item.get("waters") is not None else 3)
        except (TypeError, ValueError):
            waters = 3
        grow[str(item.get("name1") or "")] = (max(60, min(1440, minutes) * 60), max(0, min(12, waters)))
    codes = [
        "mrgseedcuke", "mrgseedtom", "mrgseedcab",
        "mrgcuke", "mrgtom", "mrgcab",
        "mrgjuice", "mrgsoup", "mrgsalad",
    ]
    rows = await conn.fetch(
        "SELECT id::text AS id, name1 FROM dex WHERE name1 = ANY($1::text[])",
        codes,
    )
    by = {str(row["name1"]): str(row["id"]) for row in rows}
    crops = (
        ("cuke", "Огурец", "mrgseedcuke", "mrgcuke", 10),
        ("tomato", "Помидор", "mrgseedtom", "mrgtom", 11),
        ("cabbage", "Капуста", "mrgseedcab", "mrgcab", 12),
    )
    for key, name, seed_code, fruit, order in crops:
        if seed_code not in by or fruit not in by:
            continue
        seconds, waters = grow.get(seed_code, (1800, 3))
        row = await conn.fetchrow("SELECT id FROM farm_crops WHERE key = $1", key)
        if row:
            crop_id = int(row["id"])
            await conn.execute(
                """
                UPDATE farm_crops
                SET display_name = $2, seed_item_id = $3, grow_seconds = $4,
                    harvest_tool_item_id = NULL, water_times = $5, enabled = TRUE
                WHERE id = $1
                """,
                crop_id, name, by[seed_code], seconds, waters,
            )
        else:
            crop_id = int(await conn.fetchval(
                """
                INSERT INTO farm_crops (
                    key, display_name, seed_item_id, grow_seconds,
                    harvest_tool_item_id, harvest_tool_cost, sprite_key, sort_order, water_times, enabled
                )
                VALUES ($1, $2, $3, $4, NULL, 1, $1, $5, $6, TRUE)
                RETURNING id
                """,
                key, name, by[seed_code], seconds, order, waters,
            ))
        drop = await conn.fetchval(
            "SELECT id FROM farm_crop_harvest_drops WHERE crop_id = $1 ORDER BY sort_order, id LIMIT 1",
            crop_id,
        )
        if drop:
            await conn.execute(
                """
                UPDATE farm_crop_harvest_drops
                SET item_id = $2, min_amount = 1, max_amount = 1, chance_percent = 100
                WHERE id = $1
                """,
                int(drop), by[fruit],
            )
        else:
            await conn.execute(
                """
                INSERT INTO farm_crop_harvest_drops
                    (crop_id, item_id, min_amount, max_amount, chance_percent, sort_order)
                VALUES ($1, $2, 1, 1, 100, 0)
                """,
                crop_id, by[fruit],
            )
    recipes = (
        ("mrg_juice", "Сок вдвоём", "mrgjuice", "mrgcuke", "mrgtom", None, 20),
        ("mrg_soup", "Суп вдвоём", "mrgsoup", "mrgcab", "mrgtom", None, 21),
        ("mrg_salad", "Салат вдвоём", "mrgsalad", "mrgcuke", "mrgtom", "mrgcab", 22),
    )
    for key, name, result, left, right, third, order in recipes:
        if result not in by or left not in by or right not in by or (third and third not in by):
            continue
        await conn.execute(
            """
            INSERT INTO craft_recipes (
                key, display_name, result_item_id, ingredient_a_id, ingredient_b_id,
                ingredient_c_id, success_percent, sort_order, enabled
            )
            VALUES ($1, $2, $3, $4, $5, $6, 100, $7, TRUE)
            ON CONFLICT (key) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                result_item_id = EXCLUDED.result_item_id,
                ingredient_a_id = EXCLUDED.ingredient_a_id,
                ingredient_b_id = EXCLUDED.ingredient_b_id,
                ingredient_c_id = EXCLUDED.ingredient_c_id,
                success_percent = 100,
                enabled = TRUE
            """,
            key, name, by[result], by[left], by[right], by[third] if third else None, order,
        )


async def _seed_gifts(conn) -> None:
    """Создаёт недостающие строки в dex. Уже лежащие строки не переписывает."""
    raw = None
    try:
        raw = await conn.fetchval("SELECT body FROM marriage_settings WHERE id = 1")
    except Exception:
        raw = None
    cfg = _gift_cfg(raw)
    for gift in gift_catalog(cfg):
        selling = gift.get("on") is not False
        row = await conn.fetchrow("SELECT id, sorting, bio FROM dex WHERE name1 = $1", gift["name1"])
        if row:
            if not str(row["sorting"] or "").strip():
                from marriage_engine.design import HEARTS_SHELF
                await conn.execute(
                    "UPDATE dex SET sorting = $2 WHERE id = $1",
                    int(row["id"]), HEARTS_SHELF,
                )
            bio_now = str(row["bio"] or "").strip()
            line = str(gift.get("line") or "").strip()
            generic = bio_now.startswith("Для брака. Кнопка")
            if line and (not bio_now or generic):
                await conn.execute(
                    "UPDATE dex SET bio = $2 WHERE id = $1 AND (COALESCE(bio, '') = '' OR bio LIKE 'Для брака. Кнопка%')",
                    int(row["id"]), line[:140],
                )
            continue
        await _insert_dex(
            conn, gift["name"], gift["name1"], gift["emoji"], gift["price"],
            gift.get("line") or "", 1000000 if selling else 0,
        )
    await conn.execute(
        "UPDATE dex SET remains = 0 WHERE name1 = ANY($1::text[]) AND remains > 0",
        list(_RETIRED),
    )
    from marriage_engine.m_prize import quiet_row
    quiet = quiet_row(cfg)
    if quiet and await conn.fetchval("SELECT id FROM dex WHERE name1 = $1", quiet["name1"]) is None:
        await _insert_dex(conn, quiet["name"], quiet["name1"], quiet["emoji"], quiet["price"], quiet["blurb"])


async def _write_gifts(conn, cfg: dict) -> None:
    """Сохранение полки из панели записывает те же поля в dex."""
    from marriage_engine.design import HEARTS_SHELF
    for gift in gift_catalog(cfg):
        selling = gift.get("on") is not False
        row = await conn.fetchrow("SELECT id FROM dex WHERE name1 = $1", gift["name1"])
        if row:
            await conn.execute(
                """
                UPDATE dex
                SET price = $2, sorting = $3, name = $4, emoji = $5, bio = $6,
                    remains = CASE
                        WHEN $7 AND remains = 0 THEN 1000000
                        WHEN NOT $7 THEN 0
                        ELSE remains
                    END
                WHERE id = $1
                """,
                int(row["id"]), int(gift["price"]), HEARTS_SHELF, gift["name"], gift["emoji"],
                gift.get("line") or "", selling,
            )
            continue
        await _insert_dex(
            conn, gift["name"], gift["name1"], gift["emoji"], gift["price"],
            gift.get("line") or "", 1000000 if selling else 0,
        )
    await conn.execute(
        "UPDATE dex SET remains = 0 WHERE name1 = ANY($1::text[]) AND remains > 0",
        list(_RETIRED),
    )
    kept = [str(gift.get("name1") or "") for gift in gift_catalog(cfg)]
    kept.append("mrgquiet")
    kept = [code for code in kept if code]
    await conn.execute(
        """
        UPDATE dex SET remains = 0
        WHERE name1 LIKE 'mrg%'
          AND NOT (name1 = ANY($1::text[]))
          AND remains > 0
        """,
        kept,
    )
    from marriage_engine.m_prize import quiet_row
    quiet = quiet_row(cfg)
    if not quiet:
        return
    row = await conn.fetchrow("SELECT id FROM dex WHERE name1 = $1", quiet["name1"])
    if row:
        await conn.execute(
            "UPDATE dex SET price = $2, sorting = $3, name = $4, emoji = $5, bio = $6 WHERE id = $1",
            int(row["id"]), int(quiet["price"]), HEARTS_SHELF, quiet["name"], quiet["emoji"], quiet["blurb"],
        )
    else:
        await _insert_dex(conn, quiet["name"], quiet["name1"], quiet["emoji"], quiet["price"], quiet["blurb"])


async def _overlay_dex(conn, view: dict) -> dict:
    shelf_rows = list(view.get("shelf") or [])
    codes = [str(row.get("name1") or "") for row in shelf_rows if row.get("name1")]
    found_rows = await conn.fetch(
        "SELECT name, name1, emoji, price, remains, bio FROM dex WHERE name1 = ANY($1::text[])",
        codes,
    ) if codes else []
    faces = {str(row["name1"]): dict(row) for row in found_rows}
    shelf = []
    for row in shelf_rows:
        shelf.append(face_from_dex(row, faces.get(str(row.get("name1") or ""))))
    view = dict(view)
    view["shelf"] = shelf
    by = {row["id"]: row for row in shelf}
    for key in ("glow", "candle", "hearth", "match", "ribbon"):
        if key in by:
            view[key + "Price"] = by[key]["price"]
    quiet = await conn.fetchrow(
        "SELECT emoji, price, remains FROM dex WHERE name1 = 'mrgquiet'"
    )
    if quiet:
        view["quietPrice"] = max(0, min(100000, int(quiet["price"] or 0)))
        if str(quiet["emoji"] or "").strip():
            view["quietEmoji"] = str(quiet["emoji"]).strip()[:8]
        if int(quiet["remains"] or 0) <= 0:
            view["quietOn"] = False
    return view


async def dex_code(pool, item_name: str) -> str:
    """Код предмета в dex. Магазин узнаёт брачную вещь по нему, а не по тексту в коде."""
    if pool is None or not str(item_name or "").strip():
        return ""
    if not await ensure(pool):
        return ""
    async with pool.acquire() as conn:
        found = await conn.fetchval(
            "SELECT name1 FROM dex WHERE name = $1 OR name1 = $1 ORDER BY id LIMIT 1",
            str(item_name),
        )
    return str(found or "")


async def _dex_id(conn, name1: str):
    return await conn.fetchval("SELECT id FROM dex WHERE name1 = $1", name1)


async def gift_stock(pool, user_id: int, cfg: dict) -> list:
    from bot.db_create.items_codec import decode_items

    rows = gift_catalog(cfg)
    if pool is None:
        return [{**row, "have": 0} for row in rows]
    from marriage_engine.m_join import RITES
    from marriage_engine.m_prize import quiet_row
    quiet = quiet_row(cfg, force=True)
    codes = [str(row.get("name1") or "") for row in rows]
    codes.extend(str(rite.get("name1") or "") for rite in RITES)
    if quiet:
        codes.append(str(quiet.get("name1") or ""))
    async with pool.acquire() as conn:
        raw = await conn.fetchval("SELECT items FROM users WHERE user_id = $1", int(user_id))
        items = decode_items(raw)
        found_rows = await conn.fetch(
            "SELECT id, name, name1, emoji, price, remains, bio FROM dex WHERE name1 = ANY($1::text[])",
            [code for code in codes if code],
        )
        faces = {str(row["name1"]): row for row in found_rows}

        def _face(row):
            hit = faces.get(str(row.get("name1") or ""))
            shown = face_from_dex(row, dict(hit) if hit else None)
            dex_id = int(hit["id"]) if hit and hit["id"] is not None else None
            return shown, dex_id

        out = []
        for row in rows:
            row, dex_id = _face(row)
            have = _count_items(items, row, dex_id)
            if row.get("on") is False and have <= 0:
                continue
            shown = dict(row)
            if row.get("on") is False:
                shown["buy"] = ""
                shown["price"] = 0
            out.append({**shown, "have": have})
        seen_ids = {row["id"] for row in out}
        seen_names = {row.get("name1") for row in out}
        for rite in RITES:
            if rite["id"] in seen_ids or rite["name1"] in seen_names:
                continue
            rite_row, dex_id = _face(rite)
            have = _count_items(items, rite_row, dex_id)
            if have > 0:
                out.append({**rite_row, "price": 0, "care": 0, "buy": "", "have": have})
        quiet_row_face, dex_id = _face(quiet)
        have = _count_items(items, quiet_row_face, dex_id)
        shown = quiet_row(cfg)
        if shown or have > 0:
            row = dict(shown or quiet)
            if shown is None:
                row["buy"] = ""
                row["price"] = 0
            row["have"] = have
            out.append(row)
    return out


async def grant_gift(pool, user_id: int, kind: str, qty: int = 1) -> bool:
    from bot.db_create.items_codec import decode_items, encode_items

    from marriage_engine.m_prize import quiet_row
    gift = next((row for row in gift_catalog(None) if row["id"] == kind), None)
    if gift is None and kind == "quiet":
        gift = quiet_row({}, force=True)
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


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def _on_day(value, today):
    return _as_date(value) == today


def _spoke(value, today, spark_day):
    found = _as_date(value)
    return found is not None and (found == today or found == spark_day)


async def use_gift(pool, live: dict, user_id: int, kind: str, cfg: dict) -> dict:
    """Списывает один предмет и применяет только долю нажавшего."""
    from bot.db_create.items_codec import decode_items, encode_items

    if pool is None or not live or not live.get("id"):
        return {"ok": False, "reason": "old"}
    from marriage_engine.m_prize import quiet_effect, quiet_row
    gift = next((row for row in gift_catalog(cfg) if row["id"] == kind), None)
    if gift is None and kind == "quiet":
        gift = quiet_row(cfg, force=True)
    if gift is None:
        return await _use_rite(pool, live, user_id, kind)
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
                       spark_day, fade_until, spark_lost, fade_extra, shield, ribbon,
                       ribbon_payer, ribbon_partner,
                       bond, proposer_id, thread_on, talk_payer, talk_partner,
                       quiet_payer, quiet_partner, vow_payer, vow_partner, bridge_day,
                       warm_payer, warm_partner
                FROM marriage_book
                WHERE id = $1 AND state = 'live'
                FOR UPDATE
                """,
                int(live["id"]),
            )
            if not row:
                return {"ok": False, "reason": "old"}
            view = settle_spark(_spark_raw(dict(row)), now, hours, cfg)
            you, other = spark_split(view["state"], int(user_id), int(row["payer_id"]))
            if kind == "quiet":
                side = spark_side(int(user_id), int(row["payer_id"]))
                last = row["quiet_payer"] if side == "payer" else row["quiet_partner"]
                if hasattr(last, "date"):
                    last = last.date()
                plan = quiet_effect(you, int(view.get("need") or 0), last, now.date())
                if not plan["ok"]:
                    return {"ok": False, "reason": plan["reason"]}
                items = _take_one(items, gift, dex_id)
                await conn.execute(
                    "UPDATE users SET items = $2 WHERE user_id = $1",
                    int(user_id), encode_items(items),
                )
                column = "quiet_payer" if side == "payer" else "quiet_partner"
                await conn.execute(
                    f"UPDATE marriage_book SET {column} = $2 WHERE id = $1",
                    int(live["id"]), now.date(),
                )
                view = add_spark_care(view["state"], side, int(plan["care"]), now, hours, cfg)
                await _save_spark(conn, int(live["id"]), view["state"])
                left = _count_items(items, gift, dex_id)
                return {"ok": True, "reason": "", "left": left, "care": int(plan["care"]), "alert": "Тихий день закрыл вашу половину."}
            side = spark_side(int(user_id), int(row["payer_id"]))
            state = view["state"]
            today = now.date()
            spark_day = state.get("spark_day")
            you_talk = row["talk_payer"] if side == "payer" else row["talk_partner"]
            other_talk = row["talk_partner"] if side == "payer" else row["talk_payer"]
            vow_at = row["vow_payer"] if side == "payer" else row["vow_partner"]
            warm_at = row["warm_payer"] if side == "payer" else row["warm_partner"]
            plan = act_plan(
                gift.get("effect") or "self",
                fading=bool(view.get("fading")),
                you=you,
                other=other,
                need=int(view.get("need") or 0),
                ribbon=bool(row["ribbon_payer"] if side == "payer" else row["ribbon_partner"]),
                amount=int(gift.get("care") or 0),
                you_spoke=_spoke(you_talk, today, spark_day),
                both_spoke=_spoke(you_talk, today, spark_day) and _spoke(other_talk, today, spark_day),
                vow_used=_as_date(vow_at) is not None,
                bridge_used=_on_day(row["bridge_day"], today),
                warm_used=_on_day(warm_at, today),
                shield=int(state.get("shield") or 0),
                fade_extra=int(state.get("fade_extra") or 0),
                spark_days=int(state.get("spark_days") or 0),
                spark_lost=int(state.get("spark_lost") or 0),
                open_today=spark_day == today,
                bond=str(row["bond"] or ""),
                is_proposer=int(row["proposer_id"] or 0) == int(user_id),
                night=moon_up(now),
                morning=dawn_up(now),
            )
            if not plan["ok"]:
                return {"ok": False, "reason": plan["reason"]}
            mate = 0
            if plan.get("transfer"):
                payer = int(live.get("payer_id") or row["payer_id"] or 0)
                partner = int(live.get("partner_id") or 0)
                mate = partner if int(user_id) == payer else payer
                if mate <= 0 or mate == int(user_id):
                    return {"ok": False, "reason": "away"}
                if await conn.fetchval("SELECT 1 FROM users WHERE user_id = $1", mate) is None:
                    return {"ok": False, "reason": "away"}
            items = _take_one(items, gift, dex_id)
            await conn.execute(
                "UPDATE users SET items = $2 WHERE user_id = $1",
                int(user_id),
                encode_items(items),
            )
            you_key = "care_payer" if side == "payer" else "care_partner"
            other_key = "care_partner" if side == "payer" else "care_payer"
            state[you_key] = max(0, int(state.get(you_key) or 0) + int(plan["add_you"]))
            state[other_key] = max(0, int(state.get(other_key) or 0) + int(plan["add_other"]))
            state["care_total"] = int(state.get("care_total") or 0) + max(0, int(plan["add_you"])) + max(0, int(plan["add_other"]))
            if plan["talk"] == "you":
                state["talk_payer" if side == "payer" else "talk_partner"] = today
            elif plan["talk"] == "both":
                state["talk_payer"] = today
                state["talk_partner"] = today
            if plan["extra"] is not None:
                state["fade_extra"] = int(plan["extra"])
            if plan["shield"] is not None:
                state["shield"] = int(plan["shield"])
            if plan["days"] is not None:
                state["spark_days"] = int(plan["days"])
                state["spark_best"] = max(int(state.get("spark_best") or 0), int(plan["days"]))
            if plan["lost"] is not None:
                state["spark_lost"] = int(plan["lost"])
            if plan["seal"]:
                seal_today(state, today, int(view.get("need") or 0))
            else:
                state = nudge_spark(state, now, hours, cfg)["state"]
            book = int(live["id"])
            if plan["ribbon"]:
                column = "ribbon_payer" if side == "payer" else "ribbon_partner"
                await conn.execute(
                    f"UPDATE marriage_book SET {column} = TRUE, ribbon = TRUE WHERE id = $1",
                    book,
                )
            if plan["talk"] == "you":
                column = "talk_payer" if side == "payer" else "talk_partner"
                await conn.execute(
                    f"UPDATE marriage_book SET {column} = $2 WHERE id = $1", book, today,
                )
            elif plan["talk"] == "both":
                await conn.execute(
                    "UPDATE marriage_book SET talk_payer = $2, talk_partner = $2 WHERE id = $1",
                    book, today,
                )
            if plan["vow"]:
                column = "vow_payer" if side == "payer" else "vow_partner"
                await conn.execute(
                    f"UPDATE marriage_book SET {column} = $2 WHERE id = $1", book, today,
                )
            if plan["bridge"]:
                await conn.execute("UPDATE marriage_book SET bridge_day = $2 WHERE id = $1", book, today)
            if plan["warm"]:
                column = "warm_payer" if side == "payer" else "warm_partner"
                await conn.execute(
                    f"UPDATE marriage_book SET {column} = $2 WHERE id = $1", book, today,
                )
            if plan.get("bond") in ("propose", "family"):
                if plan.get("set_proposer"):
                    await conn.execute(
                        "UPDATE marriage_book SET bond = $2, proposer_id = $3 WHERE id = $1",
                        book, plan["bond"], int(user_id),
                    )
                else:
                    await conn.execute(
                        "UPDATE marriage_book SET bond = $2 WHERE id = $1",
                        book, plan["bond"],
                    )
            if plan.get("transfer") and mate:
                raw_mate = await conn.fetchval(
                    "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", mate,
                )
                mate_items = decode_items(raw_mate)
                key = str(dex_id) if dex_id is not None else str(gift.get("name") or "")
                try:
                    held = int(mate_items.get(key) or 0)
                except (TypeError, ValueError):
                    held = 0
                mate_items[key] = held + 1
                await conn.execute(
                    "UPDATE users SET items = $2 WHERE user_id = $1",
                    mate, encode_items(mate_items),
                )
            await _save_spark(conn, book, state)
            left = _count_items(items, gift, dex_id)
            touch = " ".join(str(gift.get("touch") or "").replace("<", " ").replace(">", " ").split())
            alert = touch or str(plan.get("alert") or "")
            return {
                "ok": True, "reason": "", "left": left,
                "care": max(0, int(plan["add_you"])), "alert": alert[:200],
            }


_RANK = {"": 0, "bouquet": 1, "propose": 2, "family": 3}
_RITE_ALERT = {
    "bouquet": "Букетный период открыт.",
    "propose": "Вы сделали предложение.",
    "family": "Теперь у вас семейная жизнь.",
    "thread": "Нить держит пару, даже если искра погаснет.",
    "ahead": "Эта ступень уже открыта.",
}


async def mark_reply(pool, user_id: int, target_id: int) -> None:
    if pool is None or not target_id or int(user_id) == int(target_id):
        return
    if not await ensure(pool):
        return
    today = datetime.now(_MSK).date()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, payer_id FROM marriage_book
            WHERE state = 'live' AND (
                (payer_id = $1 AND partner_id = $2) OR (payer_id = $2 AND partner_id = $1)
            )
            """,
            int(user_id), int(target_id),
        )
        if not row:
            return
        column = "talk_payer" if int(row["payer_id"]) == int(user_id) else "talk_partner"
        await conn.execute(
            f"UPDATE marriage_book SET {column} = $2 WHERE id = $1",
            int(row["id"]), today,
        )


async def take_warm(pool, user_id: int) -> bool:
    """Градус делает ближайший ответ длинным и сразу снимается."""
    if pool is None or not await ensure(pool):
        return False
    today = datetime.now(_MSK).date()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, payer_id, warm_payer, warm_partner
            FROM marriage_book
            WHERE state = 'live' AND (payer_id = $1 OR partner_id = $1)
            ORDER BY live_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            int(user_id),
        )
        if not row:
            return False
        column = "warm_payer" if int(row["payer_id"]) == int(user_id) else "warm_partner"
        if not _on_day(row[column], today):
            return False
        await conn.execute(
            f"UPDATE marriage_book SET {column} = NULL WHERE id = $1",
            int(row["id"]),
        )
    return True


async def reply_touch(pool, user_id: int, target_id: int, text: str) -> str:
    """Ответ партнёру закрывает разговор и тихо кладёт заботу. В чат пишет только два момента."""
    from marriage_engine.m_join import reply_care_amount, reply_spark_line
    await mark_reply(pool, user_id, target_id)
    if pool is None:
        return ""
    live = await live_for(pool, user_id)
    if not live or not live.get("id"):
        return ""
    other = int(live["partner_id"] if int(live["payer_id"]) == int(user_id) else live["payer_id"])
    if other != int(target_id):
        return ""
    cfg = await load_settings(pool)
    if not cfg.get("sparkOn", True):
        return ""
    amount = reply_care_amount(text, cfg.get("replyCare", 1), cfg.get("replyWarm", 3), cfg.get("replyWarmWords", 4))
    if await take_warm(pool, user_id):
        amount = max(amount, int(cfg.get("replyWarm") or 3))
    preview = await spark_sync(pool, live, user_id, cfg, 0, False)
    if not preview:
        return ""
    before, need = int(preview["you"]), int(preview["need"])
    after = before
    if amount > 0:
        viewed = await spark_sync(pool, live, user_id, cfg, amount, False)
        if viewed:
            after, need = int(viewed["you"]), int(viewed["need"])
    found = await names(pool, [other])
    label = found.get(other) or "партнёром"
    return reply_spark_line(
        before, after, need, int(cfg.get("replyAlmost") or 2), label,
        cfg.get("replyDone") or "", cfg.get("replyAlmostText") or "",
    )


async def _use_rite(pool, live, user_id, kind):
    from bot.db_create.items_codec import decode_items, encode_items
    from marriage_engine.m_join import RITES
    rite = next((row for row in RITES if row["id"] == kind), None)
    if rite is None or pool is None or not live or not live.get("id"):
        return {"ok": False, "reason": "bad"}
    async with pool.acquire() as conn:
        async with conn.transaction():
            raw_items = await conn.fetchval(
                "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", int(user_id),
            )
            items = decode_items(raw_items)
            dex_id = await _dex_id(conn, rite["name1"])
            if _count_items(items, rite, dex_id) < 1:
                return {"ok": False, "reason": "none"}
            row = await conn.fetchrow(
                "SELECT bond, thread_on FROM marriage_book WHERE id = $1 AND state = 'live' FOR UPDATE",
                int(live["id"]),
            )
            if not row:
                return {"ok": False, "reason": "old"}
            effect = rite["effect"]
            current = str(row["bond"] or "")
            if effect == "thread":
                if row["thread_on"]:
                    return {"ok": False, "reason": "ahead"}
            elif _RANK.get(current, 0) >= _RANK.get(effect, 0):
                return {"ok": False, "reason": "ahead"}
            items = _take_one(items, rite, dex_id)
            await conn.execute(
                "UPDATE users SET items = $2 WHERE user_id = $1", int(user_id), encode_items(items),
            )
            if effect == "thread":
                await conn.execute("UPDATE marriage_book SET thread_on = TRUE WHERE id = $1", int(live["id"]))
            elif effect == "propose":
                await conn.execute(
                    "UPDATE marriage_book SET bond = 'propose', proposer_id = $2 WHERE id = $1",
                    int(live["id"]), int(user_id),
                )
            else:
                await conn.execute(
                    "UPDATE marriage_book SET bond = $2 WHERE id = $1", int(live["id"]), effect,
                )
    return {"ok": True, "reason": "", "care": 0, "alert": _RITE_ALERT.get(effect, "Готово.")}


async def choose_wish(pool, user_id: int, prize_id: str, day: int, cfg: dict) -> dict:
    from marriage_engine.m_prize import prizes_view, remember_wish
    prize = next((row for row in prizes_view((cfg or {}).get("prizes")) if row["id"] == str(prize_id) and row["on"]), None)
    if prize is None:
        return {"ok": False, "alert": "Этот подарок выключен."}
    if not await ensure(pool):
        return {"ok": False, "alert": "Книга браков сейчас недоступна."}
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, payer_id, partner_id, wish_payer, wish_partner
            FROM marriage_book
            WHERE state = 'live' AND (payer_id = $1 OR partner_id = $1)
            ORDER BY live_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            int(user_id),
        )
        if not row:
            return {"ok": False, "alert": "Брака нет."}
        side = "payer" if int(row["payer_id"]) == int(user_id) else "partner"
        remembered = remember_wish(str(row["wish_payer"] or ""), str(row["wish_partner"] or ""), side, prize["id"])
        await conn.execute(
            "UPDATE marriage_book SET wish_payer = $2, wish_partner = $3, wish_day = $4 WHERE id = $1",
            int(row["id"]), remembered["payer"], remembered["partner"], int(day),
        )
    if remembered["locked"]:
        alert = ""
    elif remembered["payer"] and remembered["partner"]:
        alert = "Вы выбрали разное. Подарок соберётся, когда выбор совпадёт."
    else:
        alert = "Запомнили. Подарок соберётся, когда партнёр выберет то же."
    return {
        "ok": True,
        "alert": alert,
        "locked": remembered["locked"],
        "day": int(day),
        "book_id": int(row["id"]),
        "payer_id": int(row["payer_id"]),
        "partner_id": int(row["partner_id"]),
        "prize": prize,
    }


async def stock_named(pool, name1: str) -> dict:
    if pool is None:
        return {"name1": name1, "price": 0, "remains": 0, "name": ""}
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name1, name, price, remains FROM dex WHERE name1 = $1",
            name1,
        )
    if not row:
        return {"name1": name1, "price": 0, "remains": 0, "name": ""}
    return {
        "name1": row["name1"],
        "price": int(row["price"] or 0),
        "remains": int(row["remains"] or 0),
        "name": str(row["name"] or ""),
    }


async def stock_premium(pool, key: str) -> dict:
    if pool is None:
        return {"name1": "", "price": 0, "remains": 0, "name": ""}
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT name1, name, price, remains FROM dex
            WHERE position($1 in lower(COALESCE(name1, ''))) > 0
            ORDER BY length(name1)
            LIMIT 1
            """,
            str(key).lower(),
        )
    if not row:
        return {"name1": "", "price": 0, "remains": 0, "name": ""}
    return {
        "name1": str(row["name1"] or ""),
        "price": int(row["price"] or 0),
        "remains": int(row["remains"] or 0),
        "name": str(row["name"] or ""),
    }


async def find_named_user(pool, username: str) -> int:
    if pool is None or not username:
        return 0
    async with pool.acquire() as conn:
        found = await conn.fetchval(
            "SELECT user_id FROM users WHERE lower(username) = lower($1) LIMIT 1",
            str(username).lstrip("@"),
        )
    return int(found or 0)


async def give_named(pool, user_ids, name1: str, qty: int) -> bool:
    from bot.db_create.items_codec import decode_items, encode_items
    people = [int(uid) for uid in user_ids if uid]
    if pool is None or not people or int(qty) <= 0 or not name1:
        return False
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                dex = await conn.fetchrow("SELECT id FROM dex WHERE name1 = $1 FOR UPDATE", name1)
                if not dex:
                    return False
                need = int(qty) * len(people)
                moved = await conn.fetchval(
                    "UPDATE dex SET remains = remains - $2 WHERE id = $1 AND remains >= $2 RETURNING id",
                    int(dex["id"]), need,
                )
                if moved is None:
                    return False
                key = str(dex["id"])
                for uid in people:
                    raw = await conn.fetchval("SELECT items FROM users WHERE user_id = $1 FOR UPDATE", uid)
                    if raw is None and await conn.fetchval("SELECT 1 FROM users WHERE user_id = $1", uid) is None:
                        raise RuntimeError("no user")
                    items = decode_items(raw)
                    try:
                        have = int(items.get(key) or 0)
                    except (TypeError, ValueError):
                        have = 0
                    items[key] = have + int(qty)
                    await conn.execute("UPDATE users SET items = $2 WHERE user_id = $1", uid, encode_items(items))
        return True
    except Exception:
        return False


async def give_kut(pool, shares) -> bool:
    pairs = [(int(uid), int(amount)) for uid, amount in shares if int(amount) > 0]
    if pool is None or not pairs:
        return False
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                for uid, amount in pairs:
                    got = await conn.fetchval(
                        "UPDATE users SET balance = balance + $2 WHERE user_id = $1 RETURNING user_id",
                        uid, amount,
                    )
                    if got is None:
                        raise RuntimeError("no user")
        return True
    except Exception:
        return False


async def finish_wish(pool, book_id: int, day: int) -> None:
    from marriage_engine.m_prize import with_day
    if not await ensure(pool):
        return
    async with pool.acquire() as conn:
        done = await conn.fetchval("SELECT wish_done FROM marriage_book WHERE id = $1", int(book_id))
        await conn.execute(
            """
            UPDATE marriage_book
            SET wish_done = $2, wish_payer = '', wish_partner = '', wish_day = 0
            WHERE id = $1
            """,
            int(book_id), with_day(done, day),
        )
