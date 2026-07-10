"""Retention policy for game_events — prevents unbounded table growth."""

from __future__ import annotations

import logging
import time

from config import GAME_EVENTS_RETENTION_DAYS

logger = logging.getLogger("cute-farm.game-events")

_last_purge_at: float = 0.0
_PURGE_INTERVAL_SECONDS = 24 * 60 * 60


async def maybe_purge_old_game_events() -> int:
    """Delete rows older than GAME_EVENTS_RETENTION_DAYS. Runs at most once per day."""
    global _last_purge_at

    now = time.monotonic()
    if now - _last_purge_at < _PURGE_INTERVAL_SECONDS:
        return 0

    from db import db

    if db.pool is None:
        return 0

    days = max(30, GAME_EVENTS_RETENTION_DAYS)
    try:
        result = await db.pool.execute(
            """
            DELETE FROM game_events
            WHERE created_at < NOW() - ($1 * INTERVAL '1 day')
            """,
            days,
        )
        _last_purge_at = now
        try:
            deleted = int(str(result).split()[-1])
        except (ValueError, IndexError):
            deleted = 0
        if deleted:
            logger.info("game_events: purged %d row(s) older than %d days", deleted, days)
        return deleted
    except Exception:
        logger.exception("game_events purge failed")
        return 0
