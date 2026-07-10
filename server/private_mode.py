"""Приватный режим — управляется переменной PRIVATE_MODE в .env.

PRIVATE_MODE=1  → доступ только для PRIVATE_USER_IDS
PRIVATE_MODE=0  → никто не проходит (полная блокировка)
PRIVATE_MODE не задан / пусто → все проходят (открытый режим)
"""

import os
import random


def _parse_ids(value: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in (value or "").split(","):
        raw = part.strip()
        if raw:
            try:
                ids.add(int(raw))
            except ValueError:
                pass
    return frozenset(ids)


_raw_mode = os.getenv("PRIVATE_MODE", "").strip()

# "1" = вайтлист, "0" = полная блокировка, иначе = открыто
PRIVATE_MODE: str | None = _raw_mode if _raw_mode in ("0", "1") else None

_ALLOWED_IDS: frozenset[int] = _parse_ids(os.getenv("PRIVATE_USER_IDS", ""))

_BOT_MESSAGES = [
    "бот временно недоступен\n\n[err: db_conn_timeout 0x00000517]",
    "internal error\n\ncode: 503\ntrace: farm_core::init → null deref",
    "ошибка соединения с сервером\n\nповторите через несколько минут",
    "сервис перегружен\n\n[queue overflow, retry later]",
]


def is_allowed(user_id: int) -> bool:
    if PRIVATE_MODE is None:
        return True
    if PRIVATE_MODE == "0":
        return False
    # PRIVATE_MODE == "1": только вайтлист
    return int(user_id) in _ALLOWED_IDS


def bot_block_message() -> str:
    return random.choice(_BOT_MESSAGES)
