"""Хранение защиты официальной группы. Включает только создатель проекта."""
from __future__ import annotations

from datetime import date, datetime

from db import db

from group_guard_rules import effective_flags, morning_due, morning_text

_READY = False


async def ensure_guard_tables() -> None:
    global _READY
    if _READY:
        return
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_guard (
            chat_id BIGINT PRIMARY KEY,
            links BOOLEAN NOT NULL DEFAULT FALSE,
            flood BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_by BIGINT
        );
        CREATE TABLE IF NOT EXISTS epsilon_guard_hits (
            id BIGSERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            user_id BIGINT,
            kind TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS epsilon_guard_hits_chat_idx
            ON epsilon_guard_hits (chat_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS epsilon_morning_sent (
            user_id BIGINT NOT NULL,
            sent_on DATE NOT NULL,
            PRIMARY KEY (user_id, sent_on)
        );
        CREATE TABLE IF NOT EXISTS epsilon_guard_policy (
            id INT PRIMARY KEY,
            captcha BOOLEAN NOT NULL DEFAULT TRUE,
            links BOOLEAN NOT NULL DEFAULT FALSE,
            flood BOOLEAN NOT NULL DEFAULT FALSE,
            morning BOOLEAN NOT NULL DEFAULT TRUE,
            morning_hour INT NOT NULL DEFAULT 9
        );
        INSERT INTO epsilon_guard_policy (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
        CREATE TABLE IF NOT EXISTS epsilon_guard_allow (
            user_id BIGINT PRIMARY KEY,
            note TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        ALTER TABLE epsilon_guard ADD COLUMN IF NOT EXISTS custom BOOLEAN;
        UPDATE epsilon_guard SET custom = TRUE WHERE custom IS NULL;
        ALTER TABLE epsilon_guard ALTER COLUMN custom SET DEFAULT FALSE;
        ALTER TABLE epsilon_guard ALTER COLUMN custom SET NOT NULL;
        """
    )
    _READY = True


def _policy_from(row) -> dict:
    if not row:
        return {"captcha": True, "links": False, "flood": False, "morning": True, "morningHour": 9}
    return {
        "captcha": bool(row["captcha"]),
        "links": bool(row["links"]),
        "flood": bool(row["flood"]),
        "morning": bool(row["morning"]),
        "morningHour": int(row["morning_hour"]),
    }


async def load_policy() -> dict:
    await ensure_guard_tables()
    row = await db.pool.fetchrow("SELECT captcha, links, flood, morning, morning_hour FROM epsilon_guard_policy WHERE id = 1")
    return _policy_from(row)


async def guard_view(chat_id: int) -> dict:
    await ensure_guard_tables()
    policy = await load_policy()
    row = await db.pool.fetchrow(
        "SELECT links, flood, custom FROM epsilon_guard WHERE chat_id = $1",
        int(chat_id),
    )
    custom = bool(row and row["custom"])
    captcha = False
    try:
        cap = await db.pool.fetchrow(
            "SELECT enabled FROM group_captcha_settings WHERE chat_id = $1",
            int(chat_id),
        )
        captcha = bool(cap and cap["enabled"]) if cap else bool(policy["captcha"])
    except Exception:
        captcha = bool(policy["captcha"])
    flags = effective_flags(
        custom=custom,
        links=bool(row and row["links"]),
        flood=bool(row and row["flood"]),
        captcha=captcha,
        policy=policy,
    )
    hits = await db.pool.fetch(
        """
        SELECT user_id, kind, detail, created_at
        FROM epsilon_guard_hits
        WHERE chat_id = $1
        ORDER BY created_at DESC
        LIMIT 12
        """,
        int(chat_id),
    )
    captcha_hits = []
    try:
        captcha_hits = await db.pool.fetch(
            """
            SELECT user_id, event, created_at
            FROM group_captcha_events
            WHERE chat_id = $1 AND event IN ('fail', 'timeout', 'kick')
            ORDER BY created_at DESC
            LIMIT 8
            """,
            int(chat_id),
        )
    except Exception:
        captcha_hits = []
    items = [
        {
            "userId": int(item["user_id"]) if item["user_id"] else None,
            "kind": item["kind"],
            "detail": item["detail"] or "",
            "at": item["created_at"].isoformat() if item["created_at"] else None,
        }
        for item in hits
    ]
    for item in captcha_hits:
        items.append({
            "userId": int(item["user_id"]) if item["user_id"] else None,
            "kind": "captcha",
            "detail": item["event"] or "",
            "at": item["created_at"].isoformat() if item["created_at"] else None,
        })
    items.sort(key=lambda item: item["at"] or "", reverse=True)
    return {
        "captcha": flags["captcha"],
        "links": flags["links"],
        "flood": flags["flood"],
        "custom": custom,
        "hits": items[:12],
    }


async def _write_captcha(chat_id: int, captcha: bool, updated_by: int) -> None:
    try:
        await db.pool.execute(
            """
            INSERT INTO group_captcha_settings (chat_id, enabled, disabled_at, disabled_by)
            VALUES ($1, $2, CASE WHEN $2 THEN NULL ELSE NOW() END, CASE WHEN $2 THEN NULL ELSE $3 END)
            ON CONFLICT (chat_id) DO UPDATE
            SET enabled = EXCLUDED.enabled,
                disabled_at = EXCLUDED.disabled_at,
                disabled_by = EXCLUDED.disabled_by
            """,
            int(chat_id),
            bool(captcha),
            int(updated_by),
        )
    except Exception:
        return


async def set_guard(chat_id: int, *, links: bool, flood: bool, captcha: bool, updated_by: int) -> dict:
    await ensure_guard_tables()
    await db.pool.execute(
        """
        INSERT INTO epsilon_guard (chat_id, links, flood, custom, updated_at, updated_by)
        VALUES ($1, $2, $3, TRUE, NOW(), $4)
        ON CONFLICT (chat_id) DO UPDATE
        SET links = EXCLUDED.links,
            flood = EXCLUDED.flood,
            custom = TRUE,
            updated_at = NOW(),
            updated_by = EXCLUDED.updated_by
        """,
        int(chat_id),
        bool(links),
        bool(flood),
        int(updated_by),
    )
    await _write_captcha(int(chat_id), bool(captcha), int(updated_by))
    return await guard_view(chat_id)


async def follow_policy(chat_id: int, updated_by: int) -> dict:
    """Группа снова повторяет общие правила."""
    policy = await load_policy()
    await db.pool.execute(
        """
        INSERT INTO epsilon_guard (chat_id, links, flood, custom, updated_at, updated_by)
        VALUES ($1, $2, $3, FALSE, NOW(), $4)
        ON CONFLICT (chat_id) DO UPDATE
        SET links = EXCLUDED.links,
            flood = EXCLUDED.flood,
            custom = FALSE,
            updated_at = NOW(),
            updated_by = EXCLUDED.updated_by
        """,
        int(chat_id),
        bool(policy["links"]),
        bool(policy["flood"]),
        int(updated_by),
    )
    await _write_captcha(int(chat_id), bool(policy["captcha"]), int(updated_by))
    return await guard_view(chat_id)


async def _apply_policy_where_shared(policy: dict, updated_by: int) -> None:
    rows = await db.pool.fetch(
        """
        SELECT g.chat_id
        FROM epsilon_official_groups g
        LEFT JOIN epsilon_guard e ON e.chat_id = g.chat_id
        WHERE g.is_official AND COALESCE(e.custom, FALSE) = FALSE
        """
    )
    for row in rows:
        chat_id = int(row["chat_id"])
        await db.pool.execute(
            """
            INSERT INTO epsilon_guard (chat_id, links, flood, custom, updated_at, updated_by)
            VALUES ($1, $2, $3, FALSE, NOW(), $4)
            ON CONFLICT (chat_id) DO UPDATE
            SET links = EXCLUDED.links,
                flood = EXCLUDED.flood,
                custom = FALSE,
                updated_at = NOW(),
                updated_by = EXCLUDED.updated_by
            WHERE epsilon_guard.custom = FALSE
            """,
            chat_id,
            bool(policy["links"]),
            bool(policy["flood"]),
            int(updated_by),
        )
        await _write_captcha(chat_id, bool(policy["captcha"]), int(updated_by))


async def set_policy(policy: dict, updated_by: int) -> None:
    hour = int(policy["morningHour"])
    if hour < 0 or hour > 23:
        raise ValueError("hour")
    await ensure_guard_tables()
    await db.pool.execute(
        """
        INSERT INTO epsilon_guard_policy (id, captcha, links, flood, morning, morning_hour)
        VALUES (1, $1, $2, $3, $4, $5)
        ON CONFLICT (id) DO UPDATE
        SET captcha = EXCLUDED.captcha,
            links = EXCLUDED.links,
            flood = EXCLUDED.flood,
            morning = EXCLUDED.morning,
            morning_hour = EXCLUDED.morning_hour
        """,
        bool(policy["captcha"]),
        bool(policy["links"]),
        bool(policy["flood"]),
        bool(policy["morning"]),
        hour,
    )
    stored = await load_policy()
    await _apply_policy_where_shared(stored, updated_by)


async def apply_policy_to_chat(chat_id: int, updated_by: int) -> None:
    """Новая официальная группа получает общие правила, если у неё ещё нет своих."""
    await ensure_guard_tables()
    custom = await db.pool.fetchval(
        "SELECT custom FROM epsilon_guard WHERE chat_id = $1",
        int(chat_id),
    )
    if custom:
        return
    await follow_policy(int(chat_id), updated_by)


def _clean_note(note: str) -> str:
    text = " ".join((note or "").split())
    if len(text) < 2:
        raise ValueError("note")
    return text[:80]


async def add_allow(user_id: int, note: str) -> None:
    await ensure_guard_tables()
    if int(user_id) <= 0:
        raise ValueError("user")
    await db.pool.execute(
        """
        INSERT INTO epsilon_guard_allow (user_id, note)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE SET note = EXCLUDED.note
        """,
        int(user_id),
        _clean_note(note),
    )


async def remove_allow(user_id: int) -> None:
    await ensure_guard_tables()
    await db.pool.execute("DELETE FROM epsilon_guard_allow WHERE user_id = $1", int(user_id))


async def guard_desk() -> dict:
    await ensure_guard_tables()
    policy = await load_policy()
    try:
        rows = await db.pool.fetch(
            """
            SELECT g.chat_id, g.title,
                   COALESCE(e.custom, FALSE) AS custom,
                   COALESCE(e.links, FALSE) AS links,
                   COALESCE(e.flood, FALSE) AS flood,
                   c.enabled AS captcha
            FROM epsilon_official_groups g
            LEFT JOIN epsilon_guard e ON e.chat_id = g.chat_id
            LEFT JOIN group_captcha_settings c ON c.chat_id = g.chat_id
            WHERE g.is_official
            ORDER BY COALESCE(e.custom, FALSE) DESC, g.title
            """
        )
    except Exception:
        rows = await db.pool.fetch(
            """
            SELECT g.chat_id, g.title,
                   COALESCE(e.custom, FALSE) AS custom,
                   COALESCE(e.links, FALSE) AS links,
                   COALESCE(e.flood, FALSE) AS flood,
                   NULL::boolean AS captcha
            FROM epsilon_official_groups g
            LEFT JOIN epsilon_guard e ON e.chat_id = g.chat_id
            WHERE g.is_official
            ORDER BY COALESCE(e.custom, FALSE) DESC, g.title
            """
        )
    groups = []
    for row in rows:
        own_captcha = policy["captcha"] if row["captcha"] is None else bool(row["captcha"])
        flags = effective_flags(
            custom=bool(row["custom"]),
            links=row["links"],
            flood=row["flood"],
            captcha=own_captcha,
            policy=policy,
        )
        groups.append({
            "chatId": int(row["chat_id"]),
            "title": row["title"] or str(row["chat_id"]),
            "custom": bool(row["custom"]),
            **flags,
        })
    people = await db.pool.fetch(
        """
        SELECT a.user_id, a.note, u.first_name
        FROM epsilon_guard_allow a
        LEFT JOIN users u ON u.user_id = a.user_id
        ORDER BY a.created_at DESC
        LIMIT 40
        """
    )
    hits = await db.pool.fetch(
        """
        SELECT h.chat_id, g.title, h.user_id, h.kind, h.detail, h.created_at
        FROM epsilon_guard_hits h
        JOIN epsilon_official_groups g ON g.chat_id = h.chat_id AND g.is_official
        ORDER BY h.created_at DESC
        LIMIT 20
        """
    )
    return {
        "policy": policy,
        "groups": groups,
        "allow": [
            {
                "userId": int(item["user_id"]),
                "note": item["note"] or "",
                "name": item["first_name"] or "",
            }
            for item in people
        ],
        "hits": [
            {
                "chatId": int(item["chat_id"]),
                "title": item["title"] or "",
                "userId": int(item["user_id"]) if item["user_id"] else None,
                "kind": item["kind"],
                "detail": item["detail"] or "",
                "at": item["created_at"].isoformat() if item["created_at"] else None,
            }
            for item in hits
        ],
    }


async def record_hit(chat_id: int, user_id: int | None, kind: str, detail: str = "") -> None:
    await ensure_guard_tables()
    await db.pool.execute(
        """
        INSERT INTO epsilon_guard_hits (chat_id, user_id, kind, detail)
        VALUES ($1, $2, $3, $4)
        """,
        int(chat_id),
        int(user_id) if user_id else None,
        kind,
        (detail or "")[:160],
    )


async def send_morning_if_due(now: datetime | None = None) -> int:
    """Личка администраторам официальных групп. Час задаёт создатель."""
    clock = now or datetime.now()
    await ensure_guard_tables()
    policy = await load_policy()
    if not morning_due(clock.hour, enabled=policy["morning"], morning_hour=policy["morningHour"]):
        return 0
    day = clock.date()
    seats = await db.pool.fetch(
        """
        SELECT s.user_id, s.chat_id, g.title
        FROM epsilon_seats s
        JOIN epsilon_official_groups g ON g.chat_id = s.chat_id AND g.is_official
        ORDER BY s.user_id, g.title
        """
    )
    by_user: dict[int, list] = {}
    for row in seats:
        by_user.setdefault(int(row["user_id"]), []).append(row)
    sent = 0
    for user_id, groups in by_user.items():
        inserted = await db.pool.fetchrow(
            """
            INSERT INTO epsilon_morning_sent (user_id, sent_on)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            RETURNING user_id
            """,
            user_id,
            day,
        )
        if not inserted:
            continue
        notes = []
        for group in groups[:4]:
            notes.append(await _group_morning_row(int(group["chat_id"]), group["title"] or "Группа", day))
        text = morning_text(notes)
        if await _send_dm(user_id, text):
            sent += 1
        else:
            await db.pool.execute(
                "DELETE FROM epsilon_morning_sent WHERE user_id = $1 AND sent_on = $2",
                user_id,
                day,
            )
    return sent


async def _group_morning_row(chat_id: int, title: str, day: date) -> dict:
    today = yesterday = None
    close = 0
    try:
        from datetime import timedelta
        row = await db.pool.fetchrow(
            """
            SELECT
              coalesce(sum(text) FILTER (WHERE date = $2), 0)::bigint AS today,
              coalesce(sum(text) FILTER (WHERE date = $3), 0)::bigint AS yesterday
            FROM chatchange
            WHERE chat_id = $1 AND date >= $3 AND date <= $2
            """,
            chat_id,
            day,
            day - timedelta(days=1),
        )
        if row:
            today = int(row["today"])
            yesterday = int(row["yesterday"])
    except Exception:
        today = yesterday = None
    try:
        close = int(await db.pool.fetchval(
            """
            SELECT count(*) FROM (
                SELECT user_id
                FROM active_warns
                WHERE chat_id = $1
                  AND coalesce(mode, 'chat') = 'chat'
                  AND (expires_at IS NULL OR expires_at > now())
                GROUP BY user_id
                HAVING count(*) >= 2
            ) t
            """,
            chat_id,
        ) or 0)
    except Exception:
        close = 0
    return {"title": title, "today": today, "yesterday": yesterday, "close": close}


async def _send_dm(user_id: int, text: str) -> bool:
    try:
        import aiohttp
        from config import BOT_TOKEN
    except Exception:
        return False
    if not BOT_TOKEN:
        return False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": int(user_id), "text": text[:3500]},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
                return bool(data.get("ok"))
    except Exception:
        return False
