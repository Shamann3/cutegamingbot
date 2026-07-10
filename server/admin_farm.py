"""Admin: ферма — настройки, грядки игроков, глобальный сброс."""

from __future__ import annotations

from admin_users import get_user_admin_profile, insert_admin_audit, search_users
from db import db
from farm_crops import crops_for_client
from farm_settings import get_farm_settings_payload, update_farm_settings

_EMPTY_PLOT_SQL = """
UPDATE farm_plots
SET status = 'EMPTY',
    planted_at = NULL,
    ripe_at = NULL,
    dry_at = NULL,
    needs_water = FALSE,
    wilt_at = NULL,
    waters_remaining = 0,
    crop_id = NULL,
    autowater_active = FALSE
"""


async def get_farm_overview() -> dict:
    settings = await get_farm_settings_payload()
    stats = await get_farm_stats()
    return {
        "settings": settings,
        "stats": stats,
        "crops": crops_for_client(),
    }


async def get_farm_stats() -> dict:
    row = await db.pool.fetchrow(
        """
        SELECT
            COUNT(*)::int AS total_plots,
            COUNT(*) FILTER (WHERE status = 'GROWING')::int AS growing,
            COUNT(*) FILTER (WHERE status = 'READY')::int AS ready,
            COUNT(*) FILTER (WHERE status = 'WITHERED')::int AS withered,
            COUNT(*) FILTER (WHERE status = 'EMPTY')::int AS empty,
            COUNT(DISTINCT user_id)::int AS players_with_plots
        FROM farm_plots
        """
    )
    return {
        "totalPlots": int(row["total_plots"] or 0),
        "growing": int(row["growing"] or 0),
        "ready": int(row["ready"] or 0),
        "withered": int(row["withered"] or 0),
        "empty": int(row["empty"] or 0),
        "playersWithPlots": int(row["players_with_plots"] or 0),
    }


async def get_user_farm_admin(user_id: int) -> dict | None:
    profile = await get_user_admin_profile(user_id)
    if not profile:
        return None
    farm = await db.get_farm_state(user_id)
    return {
        "userId": user_id,
        "displayName": profile["displayName"],
        "username": profile.get("username"),
        "ownedPlots": farm.get("ownedPlots", 0),
        "maxPlots": farm.get("maxPlots", 8),
        "plots": farm.get("plots", []),
        "farmCrops": farm.get("farmCrops", []),
        "waterCount": farm.get("waterCount", 0),
    }


async def reset_user_plots(
    user_id: int,
    *,
    plot_id: int | None = None,
    admin_user_id: int,
) -> dict:
    exists = await db.pool.fetchval("SELECT user_id FROM users WHERE user_id = $1", user_id)
    if exists is None:
        raise ValueError("Игрок не найден")

    if plot_id is not None:
        plot_id = int(plot_id)
        from farm_settings import get_max_plots

        if plot_id < 1 or plot_id > get_max_plots():
            raise ValueError("Неверный номер грядки")

        result = await db.pool.execute(
            f"{_EMPTY_PLOT_SQL} WHERE user_id = $1 AND plot_id = $2",
            user_id,
            plot_id,
        )
        if result == "UPDATE 0":
            raise ValueError("Грядка не найдена")
        reset_count = 1
        scope = f"plot:{plot_id}"
    else:
        reset_count = int(
            await db.pool.fetchval(
                """
                WITH updated AS (
                    UPDATE farm_plots
                    SET status = 'EMPTY',
                        planted_at = NULL,
                        ripe_at = NULL,
                        dry_at = NULL,
                        needs_water = FALSE,
                        wilt_at = NULL,
                        waters_remaining = 0,
                        crop_id = NULL,
                        autowater_active = FALSE
                    WHERE user_id = $1
                    RETURNING 1
                )
                SELECT COUNT(*)::int FROM updated
                """,
                user_id,
            )
            or 0
        )
        scope = "all"

    await insert_admin_audit(
        user_id,
        "admin_farm_reset",
        admin_user_id=admin_user_id,
        details={"scope": scope, "plotsReset": reset_count},
    )

    farm = await get_user_farm_admin(user_id)
    return {"ok": True, "plotsReset": reset_count, "farm": farm}


async def global_farm_restart(*, admin_user_id: int) -> dict:
    reset_count = int(
        await db.pool.fetchval(
            """
            WITH updated AS (
                UPDATE farm_plots
                SET status = 'EMPTY',
                    planted_at = NULL,
                    ripe_at = NULL,
                    dry_at = NULL,
                    needs_water = FALSE,
                    wilt_at = NULL,
                    waters_remaining = 0,
                    crop_id = NULL,
                    autowater_active = FALSE
                WHERE status <> 'EMPTY'
                   OR planted_at IS NOT NULL
                   OR crop_id IS NOT NULL
                   OR autowater_active = TRUE
                RETURNING 1
            )
            SELECT COUNT(*)::int FROM updated
            """
        )
        or 0
    )

    await insert_admin_audit(
        0,
        "admin_farm_global_reset",
        admin_user_id=admin_user_id,
        details={"plotsReset": reset_count},
    )

    return {"ok": True, "plotsReset": reset_count}
