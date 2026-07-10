"""Фоновая очистка тикетов поддержки старше 7 дней."""

from __future__ import annotations

import asyncio
import logging

from db import db

logger = logging.getLogger("cute-farm.support-cleanup")


async def support_cleanup_loop(stop_event: asyncio.Event) -> None:
    """Раз в сутки удаляет закрытые тикеты старше 7 дней."""
    while not stop_event.is_set():
        try:
            await asyncio.sleep(86_400)  # 24 часа
            deleted = await db.pool.fetchval(
                """
                WITH del AS (
                    DELETE FROM support_tickets
                    WHERE status = 'closed'
                      AND updated_at < NOW() - INTERVAL '7 days'
                    RETURNING id
                )
                SELECT COUNT(*) FROM del
                """
            )
            if deleted:
                logger.info("Support cleanup: удалено %s тикетов", deleted)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("support_cleanup_loop error")
