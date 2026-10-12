# -*- coding: utf-8 -*-
"""Остаток защиты, который едет вместе с предметом.

Снятая защита замирает: в сумке время не тикает. NULL — навсегда.
Пустой hold значит «лежит в инвентаре». Непустой — номер лота на бирже.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger("water_shield_charges")

_KIND = {
    "dryumbrella": "dryumbrella",
    "зонтик": "dryumbrella",
    "336": "dryumbrella",
    "drycoat": "drycoat",
    "дождевик": "drycoat",
    "337": "drycoat",
    "dryawning": "dryawning",
    "навес": "dryawning",
    "338": "dryawning",
    "drysafe": "drysafe",
    "сухой сейф": "drysafe",
    "339": "drysafe",
}


def kind_of(ref) -> str | None:
    key = " ".join(str(ref or "").strip().casefold().replace("ё", "е").split())
    return _KIND.get(key)


def leftover_seconds(until, now: datetime) -> int | None:
    """None — навсегда. 0 — срок уже вышел. Иначе целые секунды, которые ещё есть."""
    if until is None:
        return None
    if getattr(until, "tzinfo", None) is None:
        until = until.replace(tzinfo=timezone.utc)
    if getattr(now, "tzinfo", None) is None:
        now = now.replace(tzinfo=timezone.utc)
    left = int((until - now).total_seconds())
    return left if left > 0 else 0


async def ensure(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS water_shield_charges (
            id BIGSERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            kind TEXT NOT NULL,
            seconds_left INT,
            hold TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS water_shield_charges_bag_idx
            ON water_shield_charges (owner_id, kind, hold, id)
        """
    )


async def resolve_kind(conn, ref) -> str | None:
    found = kind_of(ref)
    if found:
        return found
    text = str(ref or "").strip()
    if not text:
        return None
    try:
        row = await conn.fetchrow(
            """
            SELECT name1, name FROM dex
            WHERE id::text = $1 OR name = $1 OR name1 = $1
            LIMIT 1
            """,
            text,
        )
    except Exception:
        return None
    if not row:
        return None
    return kind_of(row["name1"]) or kind_of(row["name"])


async def give(conn, owner_id: int, kind: str, seconds_left: int | None) -> None:
    await ensure(conn)
    await conn.execute(
        """
        INSERT INTO water_shield_charges (owner_id, kind, seconds_left)
        VALUES ($1, $2, $3)
        """,
        int(owner_id),
        str(kind),
        None if seconds_left is None else int(seconds_left),
    )


async def take(conn, owner_id: int, ref) -> tuple[bool, int | None]:
    """Самый старый свободный заряд. (False, None) — обычный полный срок.

    Второй элемент None при найденном заряде значит «навсегда».
    """
    await ensure(conn)
    kind = await resolve_kind(conn, ref)
    if not kind:
        return False, None
    row = await conn.fetchrow(
        """
        SELECT id, seconds_left
        FROM water_shield_charges
        WHERE owner_id = $1 AND kind = $2 AND hold = ''
        ORDER BY id
        LIMIT 1
        FOR UPDATE
        """,
        int(owner_id),
        kind,
    )
    if not row:
        return False, None
    await conn.execute("DELETE FROM water_shield_charges WHERE id = $1", row["id"])
    return True, row["seconds_left"]


async def _ids(conn, where_sql: str, args: list, quantity: int) -> list[int]:
    rows = await conn.fetch(
        f"""
        SELECT id FROM water_shield_charges
        WHERE {where_sql}
        ORDER BY id
        LIMIT {int(quantity)}
        FOR UPDATE
        """,
        *args,
    )
    return [int(row["id"]) for row in rows]


async def move_free(conn, from_id: int, to_id: int, ref, quantity: int) -> int:
    """Подарок и передача: свободные заряды переходят новому владельцу."""
    quantity = int(quantity or 0)
    if quantity <= 0 or int(from_id) == int(to_id):
        return 0
    await ensure(conn)
    kind = await resolve_kind(conn, ref)
    if not kind:
        return 0
    ids = await _ids(
        conn,
        "owner_id = $1 AND kind = $2 AND hold = ''",
        [int(from_id), kind],
        quantity,
    )
    if not ids:
        return 0
    await conn.execute(
        "UPDATE water_shield_charges SET owner_id = $2 WHERE id = ANY($1::bigint[])",
        ids,
        int(to_id),
    )
    return len(ids)


async def park(conn, owner_id: int, ref, quantity: int, hold_id) -> int:
    quantity = int(quantity or 0)
    if quantity <= 0:
        return 0
    await ensure(conn)
    kind = await resolve_kind(conn, ref)
    if not kind:
        return 0
    ids = await _ids(
        conn,
        "owner_id = $1 AND kind = $2 AND hold = ''",
        [int(owner_id), kind],
        quantity,
    )
    if not ids:
        return 0
    await conn.execute(
        "UPDATE water_shield_charges SET hold = $2 WHERE id = ANY($1::bigint[])",
        ids,
        str(hold_id),
    )
    return len(ids)


async def unpark(conn, owner_id: int, ref, quantity: int, hold_id) -> int:
    quantity = int(quantity or 0)
    if quantity <= 0:
        return 0
    await ensure(conn)
    kind = await resolve_kind(conn, ref)
    if not kind:
        return 0
    ids = await _ids(
        conn,
        "owner_id = $1 AND kind = $2 AND hold = $3",
        [int(owner_id), kind, str(hold_id)],
        quantity,
    )
    if not ids:
        return 0
    await conn.execute(
        "UPDATE water_shield_charges SET hold = '' WHERE id = ANY($1::bigint[])",
        ids,
    )
    return len(ids)


async def deliver(conn, buyer_id: int, ref, quantity: int, hold_id) -> int:
    """Продажа: заряды с лота переходят покупателю и снова лежат в сумке."""
    quantity = int(quantity or 0)
    if quantity <= 0:
        return 0
    await ensure(conn)
    kind = await resolve_kind(conn, ref)
    if not kind:
        return 0
    ids = await _ids(
        conn,
        "kind = $1 AND hold = $2",
        [kind, str(hold_id)],
        quantity,
    )
    if not ids:
        return 0
    await conn.execute(
        """
        UPDATE water_shield_charges
        SET owner_id = $2, hold = ''
        WHERE id = ANY($1::bigint[])
        """,
        ids,
        int(buyer_id),
    )
    return len(ids)


async def guard(conn, fn) -> None:
    """Отдельная точка сохранения: сбой заряда не откатывает покупку или подарок."""
    try:
        async with conn.transaction():
            await fn()
    except Exception:
        log.exception("water shield charge")
