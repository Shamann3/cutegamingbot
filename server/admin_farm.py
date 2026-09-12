"""Admin: ферма — настройки, грядки игроков, глобальный сброс."""

from __future__ import annotations

from admin_users import get_user_admin_profile, search_users
from db import db
from farm_crops import crops_for_client
from farm_logic import (
    apply_harvest,
    apply_plant,
    apply_water,
    now,
    sync_growing_plot,
)
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

_ADMIN_PLOT_ACTIONS = frozenset({"water", "harvest", "clear", "force_ripe", "plant"})


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


async def admin_plot_action(
    user_id: int,
    plot_id: int,
    action: str,
    *,
    admin_user_id: int,
    crop_id: str | None = None,
) -> dict:
    """Полный контроль грядки: полив / сбор / очистка / дозревание / посадка.

    Действия бесплатны для игрока (предметы полива/инструменты не списываются).
    Урожай при harvest уходит в инвентарь игрока.
    """
    action = (action or "").strip().lower()
    if action not in _ADMIN_PLOT_ACTIONS:
        raise ValueError("Неизвестное действие")

    exists = await db.pool.fetchval("SELECT user_id FROM users WHERE user_id = $1", user_id)
    if exists is None:
        raise ValueError("Игрок не найден")

    plot_id = int(plot_id)
    from farm_settings import get_max_plots

    if plot_id < 1 or plot_id > get_max_plots():
        raise ValueError("Неверный номер грядки")

    gained: list[dict] = []
    message = ""

    if action == "clear":
        await db.get_farm_state(user_id)
        await db.pool.execute(
            f"{_EMPTY_PLOT_SQL} WHERE user_id = $1 AND plot_id = $2",
            user_id,
            plot_id,
        )
        message = f"Грядка #{plot_id} очищена"
    elif action == "water":
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                row = await db._get_plot(conn, user_id, plot_id, for_update=True)
                if not row:
                    raise ValueError("Грядка не найдена")
                current = now()
                row = sync_growing_plot(row, current)
                if row["status"] != "GROWING":
                    raise ValueError("Поливать можно только растущую культуру")
                row = apply_water(row, current)
                await db._save_plot(conn, user_id, row)
        message = f"Грядка #{plot_id} полита (без списания предметов)"
    elif action == "force_ripe":
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                row = await db._get_plot(conn, user_id, plot_id, for_update=True)
                if not row:
                    raise ValueError("Грядка не найдена")
                current = now()
                row = sync_growing_plot(row, current)
                if row["status"] not in ("GROWING", "READY"):
                    raise ValueError("Дозреть можно только растущую культуру")
                if not row.get("crop_id"):
                    raise ValueError("На грядке нет культуры")
                row["status"] = "READY"
                row["needs_water"] = False
                row["wilt_at"] = None
                row["dry_at"] = None
                row["waters_remaining"] = 0
                row["ripe_at"] = current
                await db._save_plot(conn, user_id, row)
        message = f"Грядка #{plot_id} доведена до READY"
    elif action == "plant":
        if not crop_id:
            raise ValueError("Укажите культуру для посадки")
        from content_registry import get_crop_by_key, get_crop_for_plot

        crop = get_crop_by_key(str(crop_id)) or get_crop_for_plot(str(crop_id))
        if not crop:
            try:
                from content_registry import get_crop_by_seed

                crop = get_crop_by_seed(str(crop_id))
            except Exception:
                crop = None
        if not crop:
            raise ValueError("Культура не найдена")
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                row = await db._get_plot(conn, user_id, plot_id, for_update=True)
                if not row:
                    raise ValueError("Грядка не найдена")
                current = now()
                row = sync_growing_plot(row, current)
                if row["status"] not in ("EMPTY", "WITHERED"):
                    raise ValueError("Сажать можно только на пустую/засохшую грядку")
                row = apply_plant(row, current, crop_id=crop.key)
                await db._save_plot(conn, user_id, row)
        message = f"На грядку #{plot_id} посажено: {crop.display_name}"
    elif action == "harvest":
        gained, message = await _admin_force_harvest(user_id, plot_id)

    farm = await get_user_farm_admin(user_id)
    return {
        "ok": True,
        "action": action,
        "plotId": plot_id,
        "message": message,
        "gained": gained,
        "farm": farm,
        "adminUserId": int(admin_user_id),
    }


async def _admin_force_harvest(user_id: int, plot_id: int) -> tuple[list[dict], str]:
    """Сбор без инструмента — дропы в инвентарь игрока."""
    import random

    from content_registry import get_crop_for_plot, roll_harvest_drops
    from dex_catalog import canonical_key, merge_items_for_storage, normalize_items
    from farm_notifications import notify_item
    from user_items import add_item, items_to_db, parse_items

    gained_rows: list[dict] = []
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            user_row = await conn.fetchrow(
                "SELECT items FROM users WHERE user_id = $1 FOR UPDATE",
                user_id,
            )
            if not user_row:
                raise ValueError("Профиль не найден")
            raw_items = parse_items(user_row["items"])
            row = await db._get_plot(conn, user_id, plot_id, for_update=True)
            if not row:
                raise ValueError("Грядка не найдена")
            row = sync_growing_plot(row, now())
            if row["status"] != "READY":
                raise ValueError("Урожай ещё не готов — сначала доведите до READY")
            crop = get_crop_for_plot(row.get("crop_id"))
            if not crop:
                raise ValueError("Неизвестная культура на грядке")
            amount = random.randint(crop.harvest_min, crop.harvest_max)
            game_items = normalize_items(raw_items)
            drops = roll_harvest_drops(crop)
            if not drops:
                drops = [(crop.harvest_id, amount)] if crop.harvest_id else []
            for item_id, drop_amount in drops:
                canon_item_id = canonical_key(item_id)
                game_items = add_item(game_items, canon_item_id, drop_amount)
                gained_rows.append(notify_item(item_id, drop_amount))
            stored = merge_items_for_storage(raw_items, game_items)
            row = apply_harvest(row)
            await db._save_plot(conn, user_id, row)
            await conn.execute(
                """
                UPDATE users
                SET items = $2,
                    harvest_count = harvest_count + 1
                WHERE user_id = $1
                """,
                user_id,
                items_to_db(stored),
            )

    label = ", ".join(
        f"{g.get('emoji', '')} {g.get('name') or g.get('itemId')} ×{g.get('amount', 1)}".strip()
        for g in gained_rows
    ) or "пусто"
    return gained_rows, f"Собрано с грядки #{plot_id}: {label}"


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

    return {"ok": True, "plotsReset": reset_count}
