"""Прячет топ, пока у создателя открыто окно нулевой статистики."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

_MSK = timezone(timedelta(hours=3))
_CACHE: dict[tuple[str, int], tuple[float, bool]] = {}
_TTL = 10.0


def _today():
    return datetime.now(_MSK).date()


async def season_hides(pool, metric: str, chat_id: int = 0) -> bool:
    if pool is None:
        return False
    key = (str(metric), int(chat_id or 0))
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _TTL:
        return cached[1]
    hidden = False
    try:
        hidden = bool(await pool.fetchval(
            """
            SELECT 1
            FROM epsilon_stat_season
            WHERE metric = $1 AND chat_id = $2
              AND zero_from <= $3 AND zero_until >= $3
            """,
            key[0],
            key[1],
            _today(),
        ))
    except Exception:
        hidden = False
    _CACHE[key] = (now, hidden)
    return hidden


def forget_season_cache() -> None:
    _CACHE.clear()


async def veil_message_snapshot(pool, chat_id: int, payload: dict) -> dict:
    if not payload or not await season_hides(pool, "messages", chat_id):
        return payload
    return {
        "top_users": [],
        "total_messages": 0,
        "user_msg_count": 0,
        "max_messages_user": None,
    }


async def veil_pairs(pool, metric: str, rows):
    if not rows:
        return rows
    if not await season_hides(pool, metric, 0):
        return rows
    return []


async def veil_best_players(pool, board: dict) -> dict:
    return board
