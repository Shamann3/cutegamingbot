"""Кэш таймаута сессии администратора.

Отдельный модуль, чтобы избежать circular imports
(admin_routes → system_settings_admin → admin_session_cache → config).
"""

from __future__ import annotations

from config import ADMIN_SESSION_MINUTES as _ENV_DEFAULT

_cached: int | None = None


def get_admin_session_minutes_cached() -> int:
    if _cached is not None:
        return _cached
    return _ENV_DEFAULT


async def refresh_session_cache() -> None:
    global _cached
    from db import db
    val = await db.pool.fetchval(
        "SELECT admin_session_minutes FROM system_settings WHERE id = 1"
    )
    _cached = int(val) if val is not None else None
