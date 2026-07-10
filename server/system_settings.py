"""Флаги системы (maintenance и др.) — источник правды в PostgreSQL."""

from __future__ import annotations

from config import MAINTENANCE_MODE
from db import db

_maintenance_enabled: bool | None = None


async def ensure_system_settings_row(*, maintenance: bool = False) -> None:
    """Гарантирует строку id=1 без ON CONFLICT (старые БД без PK/UNIQUE на id)."""
    updated = await db.pool.execute(
        "UPDATE system_settings SET updated_at = NOW() WHERE id = 1"
    )
    if updated != "UPDATE 0":
        return
    try:
        await db.pool.execute(
            "INSERT INTO system_settings (id, maintenance) VALUES (1, $1)",
            maintenance,
        )
    except Exception:
        # Строка могла появиться параллельно или схема уже частично починена.
        pass


async def init_system_settings() -> None:
    global _maintenance_enabled
    row = await db.pool.fetchrow("SELECT maintenance FROM system_settings WHERE id = 1")
    if row is None:
        await ensure_system_settings_row(maintenance=MAINTENANCE_MODE)
        row = await db.pool.fetchrow("SELECT maintenance FROM system_settings WHERE id = 1")
        _maintenance_enabled = bool(row["maintenance"]) if row else MAINTENANCE_MODE
    else:
        _maintenance_enabled = bool(row["maintenance"])


def is_maintenance_enabled() -> bool:
    if _maintenance_enabled is not None:
        return _maintenance_enabled
    return MAINTENANCE_MODE


async def get_maintenance_enabled() -> bool:
    global _maintenance_enabled
    row = await db.pool.fetchval("SELECT maintenance FROM system_settings WHERE id = 1")
    if row is None:
        await init_system_settings()
        return is_maintenance_enabled()
    _maintenance_enabled = bool(row)
    return _maintenance_enabled


async def set_maintenance_enabled(enabled: bool, *, admin_user_id: int) -> bool:
    global _maintenance_enabled
    current = await db.pool.fetchrow(
        "SELECT maintenance FROM system_settings WHERE id = 1"
    )
    old_val = bool(current["maintenance"]) if current else None

    updated = await db.pool.execute(
        """
        UPDATE system_settings
        SET maintenance = $1,
            updated_by = $2,
            updated_at = NOW()
        WHERE id = 1
        """,
        enabled,
        admin_user_id,
    )
    if updated == "UPDATE 0":
        await db.pool.execute(
            """
            INSERT INTO system_settings (id, maintenance, updated_by, updated_at)
            VALUES (1, $1, $2, NOW())
            """,
            enabled,
            admin_user_id,
        )

    if old_val is not None and old_val != enabled:
        try:
            await db.pool.execute(
                """
                INSERT INTO settings_history (
                    admin_user_id, category, setting_key, old_value, new_value
                )
                VALUES ($1, 'system', 'maintenance', $2, $3)
                """,
                admin_user_id,
                str(old_val).lower(),
                str(enabled).lower(),
            )
        except Exception:
            pass

    _maintenance_enabled = enabled
    return enabled


async def refresh_maintenance_cache() -> None:
    """Синхронизировать in-memory флаг после изменения через system settings API."""
    global _maintenance_enabled
    row = await db.pool.fetchval("SELECT maintenance FROM system_settings WHERE id = 1")
    if row is not None:
        _maintenance_enabled = bool(row)
