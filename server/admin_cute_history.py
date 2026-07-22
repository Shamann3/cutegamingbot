"""Admin: объединённая история кут игрока (cutehistory + donate + p2p_transfers).

Чистые функции нормализации/слияния тестируются юнит-тестами; функция
get_user_cute_history (DB) добавляется в Task 4.
"""
from __future__ import annotations

import logging
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
    """Направление строки cutehistory: '+' содержит сумму → 'in', иначе 'out'.

    Legacy-таблица хранит неиспользуемую колонку как 0 (а не NULL), поэтому
    проверяем на truthy, а не на None: у списания "+"=0 и "-"=сумма → 'out'.
    """
    return "in" if plus else "out"


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
    """Строка cutehistory (+ данные джойнов) → элемент фида."""
    plus = row["plus"]
    minus = row["minus"]
    direction = cute_direction(plus, minus)
    amount = int((plus if direction == "in" else minus) or 0)
    is_transfer = row["transfer_id"] is not None
    chat_id = row.get("chat_id")
    is_chat_deposit = (not is_transfer) and chat_id is not None
    kind = "transfer" if is_transfer else ("chat_deposit" if is_chat_deposit else "cute")
    item = {
        "ts": _iso(row["ts"]),
        "cause": row["cause"],
        "amount": amount,
        "direction": direction,
        "balance": int(row["balance"]) if row["balance"] is not None else None,
        "kind": kind,
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
    elif is_chat_deposit:
        item["group"] = {
            "chatId": int(chat_id),
            "name": row.get("group_name"),
            "username": row.get("group_username"),
        }
    return item


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
               ch.chat_id,
               to_timestamp(ch.data,'HH24:MI DD.MM.YYYY') AS ts,
               p.sender_id, p.receiver_id,
               c.namechat AS group_name, c.usernamechat AS group_username
        FROM cutehistory ch
        LEFT JOIN p2p_transfers p ON p.id = ch.transfer_id
        LEFT JOIN chat c ON c.chat_id = ch.chat_id
        WHERE {where}
        ORDER BY ts DESC NULLS LAST
        LIMIT ${idx}
        """,
        *params, fetch_n,
    )

    # --- сводка донатов ---
    # Таблица donate содержит только (user_id, count, data=time-без-даты): ни
    # даты, ни id, поэтому донаты нельзя расположить на хронологической оси.
    # Отдаём сводку (сколько раз и на какую сумму), а не строки фида. Best-effort:
    # сбой донатов не должен ронять основной фид cutehistory. Фильтры по дате к
    # донатам неприменимы (даты нет); direction="out"/only_transfers их исключают.
    donations = None
    include_donate = (not only_transfers) and direction != "out"
    if include_donate:
        try:
            drow = await db.pool.fetchrow(
                "SELECT COUNT(*)::int AS n, COALESCE(SUM(count), 0)::bigint AS total "
                "FROM donate WHERE user_id = $1",
                user_id,
            )
            if drow and drow["n"]:
                donations = {"count": int(drow["n"]), "total": int(drow["total"])}
        except Exception as donate_err:
            logging.getLogger("cute-farm").warning(
                "cute-history donations summary skipped: %s", donate_err
            )
            donations = None

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
    items = merge_and_paginate(cute_items, [], offset, limit)
    return {"total": cute_total, "items": items, "donations": donations}
