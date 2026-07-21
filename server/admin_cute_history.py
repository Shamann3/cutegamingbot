"""Admin: объединённая история кут игрока (cutehistory + donate + p2p_transfers).

Чистые функции нормализации/слияния тестируются юнит-тестами; функция
get_user_cute_history (DB) добавляется в Task 4.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from db import db


def _parse_date(value):
    """'YYYY-MM-DD' -> datetime.date for asyncpg date binding; None/invalid -> None.

    asyncpg encodes a ``$N::date`` parameter with its date codec, which calls
    ``.toordinal()`` and therefore requires a ``datetime.date`` — a raw string
    raises ``DataError: 'str' object has no attribute 'toordinal'``. The date
    filters must be converted before they are bound.
    """
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def cute_direction(plus, minus) -> str:
    """Направление строки cutehistory: '+' заполнено → 'in', иначе 'out'."""
    return "in" if plus is not None else "out"


def counterparty_id(direction: str, sender_id, receiver_id):
    """Вторая сторона перевода относительно текущего игрока.

    Строка '-' (out, отправитель) → контрагент = получатель.
    Строка '+' (in, получатель)  → контрагент = отправитель.
    None, если это не перевод (нет p2p-данных).
    """
    if sender_id is None or receiver_id is None:
        return None
    return receiver_id if direction == "out" else sender_id


def _iso(ts) -> str | None:
    return ts.isoformat() if ts is not None else None


def normalize_cute_row(row: Any, name_map: dict) -> dict:
    """Строка cutehistory (+ данные джойна p2p) → элемент фида."""
    plus = row["plus"]
    minus = row["minus"]
    direction = cute_direction(plus, minus)
    amount = int(plus if direction == "in" else minus)
    is_transfer = row["transfer_id"] is not None
    item = {
        "ts": _iso(row["ts"]),
        "cause": row["cause"],
        "amount": amount,
        "direction": direction,
        "balance": int(row["balance"]) if row["balance"] is not None else None,
        "kind": "transfer" if is_transfer else "cute",
    }
    if is_transfer:
        cp_id = counterparty_id(direction, row["sender_id"], row["receiver_id"])
        if cp_id is not None:
            info = name_map.get(cp_id) or {}
            item["counterparty"] = {
                "userId": int(cp_id),
                "name": info.get("name"),
                "username": info.get("username"),
            }
    return item


def normalize_donate_row(row: Any) -> dict:
    """Строка donate → элемент фида (всегда начисление, kind='donate')."""
    return {
        "ts": _iso(row["ts"]),
        "cause": "донат",
        "amount": int(row["count"]),
        "direction": "in",
        "balance": None,
        "kind": "donate",
    }


def merge_and_paginate(cute_items: list, donate_items: list, offset: int, limit: int) -> list:
    """Слить два списка, отсортировать по ts DESC (None — в конец), срез [offset:offset+limit]."""
    combined = list(cute_items) + list(donate_items)
    combined.sort(key=lambda it: (it.get("ts") is not None, it.get("ts") or ""), reverse=True)
    return combined[offset:offset + limit]


async def get_user_cute_history(
    user_id: int,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    direction: str | None = None,      # "in" | "out" | None
    q: str | None = None,
    only_transfers: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Объединённый фид истории кут игрока: cutehistory (+p2p контрагент) + donate.

    Пагинация merge-стилем: из каждого источника берём offset+limit строк
    (уже отсортированных DESC), сливаем и режем в Python — корректный срез без
    загрузки всей таблицы.
    """
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    fetch_n = offset + limit
    # asyncpg binds $N::date via its date codec (needs datetime.date, not str)
    date_from = _parse_date(date_from)
    date_to = _parse_date(date_to)

    # --- cutehistory WHERE ---
    conds = ["ch.user_id = $1"]
    params: list[Any] = [user_id]
    idx = 2
    if date_from:
        conds.append(f"to_timestamp(ch.data,'HH24:MI DD.MM.YYYY') >= ${idx}::date")
        params.append(date_from)
        idx += 1
    if date_to:
        conds.append(f"to_timestamp(ch.data,'HH24:MI DD.MM.YYYY') < (${idx}::date + INTERVAL '1 day')")
        params.append(date_to)
        idx += 1
    if direction == "in":
        conds.append('ch."+" IS NOT NULL')
    elif direction == "out":
        conds.append('ch."-" IS NOT NULL')
    if q:
        conds.append(f"ch.cause ILIKE '%'||${idx}||'%'")
        params.append(q)
        idx += 1
    if only_transfers:
        conds.append("ch.transfer_id IS NOT NULL")
    where = " AND ".join(conds)

    cute_total = int(await db.pool.fetchval(
        f"SELECT COUNT(*)::int FROM cutehistory ch WHERE {where}", *params
    ) or 0)
    cute_rows = await db.pool.fetch(
        f"""
        SELECT ch."+" AS plus, ch."-" AS minus, ch.cause, ch.balance, ch.transfer_id,
               to_timestamp(ch.data,'HH24:MI DD.MM.YYYY') AS ts,
               p.sender_id, p.receiver_id
        FROM cutehistory ch
        LEFT JOIN p2p_transfers p ON p.id = ch.transfer_id
        WHERE {where}
        ORDER BY ts DESC NULLS LAST
        LIMIT ${idx}
        """,
        *params, fetch_n,
    )

    # --- donate (исключается фильтром "только переводы" и направлением "out") ---
    include_donate = (not only_transfers) and direction != "out"
    donate_rows: list = []
    donate_total = 0
    if include_donate:
        dconds = ["user_id = $1"]
        dparams: list[Any] = [user_id]
        didx = 2
        if date_from:
            dconds.append(f"data::timestamptz >= ${didx}::date")
            dparams.append(date_from)
            didx += 1
        if date_to:
            dconds.append(f"data::timestamptz < (${didx}::date + INTERVAL '1 day')")
            dparams.append(date_to)
            didx += 1
        if q:
            # у донатов единственная причина — слово "донат"
            dconds.append(f"'донат' ILIKE '%'||${didx}||'%'")
            dparams.append(q)
            didx += 1
        dwhere = " AND ".join(dconds)
        donate_total = int(await db.pool.fetchval(
            f"SELECT COUNT(*)::int FROM donate WHERE {dwhere}", *dparams
        ) or 0)
        donate_rows = await db.pool.fetch(
            f"SELECT count, data::timestamptz AS ts FROM donate WHERE {dwhere} "
            f"ORDER BY ts DESC LIMIT ${didx}",
            *dparams, fetch_n,
        )

    # --- имена контрагентов (батч) ---
    cp_ids: set[int] = set()
    for r in cute_rows:
        if r["transfer_id"] is not None:
            cid = counterparty_id(cute_direction(r["plus"], r["minus"]),
                                  r["sender_id"], r["receiver_id"])
            if cid is not None:
                cp_ids.add(int(cid))
    name_map: dict[int, dict] = {}
    if cp_ids:
        name_rows = await db.pool.fetch(
            "SELECT user_id, first_name, username FROM users WHERE user_id = ANY($1::bigint[])",
            list(cp_ids),
        )
        name_map = {
            int(nr["user_id"]): {"name": nr["first_name"], "username": nr["username"]}
            for nr in name_rows
        }

    cute_items = [normalize_cute_row(r, name_map) for r in cute_rows]
    donate_items = [normalize_donate_row(r) for r in donate_rows]
    items = merge_and_paginate(cute_items, donate_items, offset, limit)
    return {"total": cute_total + donate_total, "items": items}
