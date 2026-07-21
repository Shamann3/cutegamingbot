"""Admin: объединённая история кут игрока (cutehistory + donate + p2p_transfers).

Чистые функции нормализации/слияния тестируются юнит-тестами; функция
get_user_cute_history (DB) добавляется в Task 4.
"""
from __future__ import annotations

from typing import Any


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
