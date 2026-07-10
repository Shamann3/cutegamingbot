"""Лёгкий логгер игровых событий для аналитики.

Пишет в таблицу game_events ВСЕГДА (не зависит от AUDIT_LOG_ENABLED).
Без уведомлений в Telegram — только хранение данных.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg

from config import GAME_EVENTS_INSERT_CONCURRENCY, GAME_EVENTS_MAX_PENDING

logger = logging.getLogger("cute-farm.game-events")

_insert_semaphore = asyncio.Semaphore(max(1, GAME_EVENTS_INSERT_CONCURRENCY))
_pending_inserts = 0


async def _insert(
    pool: asyncpg.Pool,
    event_type: str,
    user_id: int,
    details: dict[str, Any],
) -> None:
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO game_events (user_id, event_type, details)
                VALUES ($1, $2, $3::jsonb)
                """,
                user_id,
                event_type,
                json.dumps(details, ensure_ascii=False),
            )
    except Exception:
        logger.exception("game_events insert failed (%s)", event_type)


async def _run_insert(
    pool: asyncpg.Pool,
    event_type: str,
    user_id: int,
    details: dict[str, Any],
) -> None:
    global _pending_inserts
    try:
        async with _insert_semaphore:
            await _insert(pool, event_type, user_id, details)
    finally:
        _pending_inserts = max(0, _pending_inserts - 1)


def log_game_event(
    pool: asyncpg.Pool | None,
    event_type: str,
    user_id: int,
    details: dict[str, Any] | None = None,
) -> None:
    """Неблокирующая запись игрового события. Ошибки не прокидываются вверх."""
    global _pending_inserts

    if pool is None:
        return

    if _pending_inserts >= max(10, GAME_EVENTS_MAX_PENDING):
        logger.debug("game_events backlog full, dropping %s", event_type)
        return

    _pending_inserts += 1
    asyncio.create_task(
        _run_insert(pool, event_type, user_id, details or {})
    )
