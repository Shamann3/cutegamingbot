"""Настройки фермы — runtime-override поверх env/code."""

from __future__ import annotations

from config import (
    ADMIN_MAX_PLOTS,
    MAX_PLOTS as ENV_MAX_PLOTS,
    TOBACCO_GROW_SECONDS as ENV_TOBACCO_GROW_SECONDS,
    TREE_GROW_SECONDS as ENV_TREE_GROW_SECONDS,
    WATER_COST_PER_USE as ENV_WATER_COST_PER_USE,
    WATER_INTERVAL_SECONDS as ENV_WATER_INTERVAL_SECONDS,
    WILT_GRACE_SECONDS as ENV_WILT_GRACE_SECONDS,
)
from db import db
from economy_settings import get_plot_price_step
from system_settings import ensure_system_settings_row

_cache: dict[str, int | None] | None = None


async def init_farm_settings() -> None:
    global _cache
    row = await db.pool.fetchrow(
        """
        SELECT tree_grow_seconds, tobacco_grow_seconds, max_plots,
               water_interval_seconds, wilt_grace_seconds, water_cost_per_use
        FROM system_settings WHERE id = 1
        """
    )
    if row is None:
        await ensure_system_settings_row(maintenance=False)
        _cache = _empty_cache()
    else:
        _cache = _row_to_cache(row)


def _empty_cache() -> dict[str, int | None]:
    return {
        "tree_grow_seconds": None,
        "tobacco_grow_seconds": None,
        "max_plots": None,
        "water_interval_seconds": None,
        "wilt_grace_seconds": None,
        "water_cost_per_use": None,
    }


def _row_to_cache(row) -> dict[str, int | None]:
    return {
        "tree_grow_seconds": row["tree_grow_seconds"],
        "tobacco_grow_seconds": row["tobacco_grow_seconds"],
        "max_plots": row["max_plots"],
        "water_interval_seconds": row["water_interval_seconds"],
        "wilt_grace_seconds": row["wilt_grace_seconds"],
        "water_cost_per_use": row["water_cost_per_use"],
    }


async def _refresh_cache() -> None:
    global _cache
    row = await db.pool.fetchrow(
        """
        SELECT tree_grow_seconds, tobacco_grow_seconds, max_plots,
               water_interval_seconds, wilt_grace_seconds, water_cost_per_use
        FROM system_settings WHERE id = 1
        """
    )
    if row is None:
        await init_farm_settings()
        return
    _cache = _row_to_cache(row)


def get_tree_grow_seconds() -> int:
    if _cache and _cache.get("tree_grow_seconds") is not None:
        return int(_cache["tree_grow_seconds"])
    return ENV_TREE_GROW_SECONDS


def get_tobacco_grow_seconds() -> int:
    if _cache and _cache.get("tobacco_grow_seconds") is not None:
        return int(_cache["tobacco_grow_seconds"])
    return ENV_TOBACCO_GROW_SECONDS


def get_max_plots() -> int:
    if _cache and _cache.get("max_plots") is not None:
        return int(_cache["max_plots"])
    return ENV_MAX_PLOTS


def get_water_interval_seconds() -> int:
    if _cache and _cache.get("water_interval_seconds") is not None:
        return int(_cache["water_interval_seconds"])
    return ENV_WATER_INTERVAL_SECONDS


def get_wilt_grace_seconds() -> int:
    if _cache and _cache.get("wilt_grace_seconds") is not None:
        return int(_cache["wilt_grace_seconds"])
    return ENV_WILT_GRACE_SECONDS


def get_water_cost_per_use() -> int:
    if _cache and _cache.get("water_cost_per_use") is not None:
        return int(_cache["water_cost_per_use"])
    return ENV_WATER_COST_PER_USE


def get_plot_prices_preview() -> list[dict]:
    step = get_plot_price_step()
    max_plots = get_max_plots()
    return [
        {"plotId": plot_id, "price": (plot_id - 1) * step}
        for plot_id in range(2, max_plots + 1)
    ]


async def get_farm_settings_payload() -> dict:
    await _refresh_cache()
    row = await db.pool.fetchrow(
        """
        SELECT tree_grow_seconds, tobacco_grow_seconds, max_plots,
               water_interval_seconds, wilt_grace_seconds, water_cost_per_use,
               updated_by, updated_at
        FROM system_settings WHERE id = 1
        """
    )
    return {
        "treeGrowSeconds": get_tree_grow_seconds(),
        "tobaccoGrowSeconds": get_tobacco_grow_seconds(),
        "maxPlots": get_max_plots(),
        "waterIntervalSeconds": get_water_interval_seconds(),
        "wiltGraceSeconds": get_wilt_grace_seconds(),
        "waterCostPerUse": get_water_cost_per_use(),
        "plotPriceStep": get_plot_price_step(),
        "plotPrices": get_plot_prices_preview(),
        "envDefaults": {
            "treeGrowSeconds": ENV_TREE_GROW_SECONDS,
            "tobaccoGrowSeconds": ENV_TOBACCO_GROW_SECONDS,
            "maxPlots": ENV_MAX_PLOTS,
            "waterIntervalSeconds": ENV_WATER_INTERVAL_SECONDS,
            "wiltGraceSeconds": ENV_WILT_GRACE_SECONDS,
            "waterCostPerUse": ENV_WATER_COST_PER_USE,
        },
        "overrides": {
            "treeGrowSeconds": row["tree_grow_seconds"] if row else None,
            "tobaccoGrowSeconds": row["tobacco_grow_seconds"] if row else None,
            "maxPlots": row["max_plots"] if row else None,
            "waterIntervalSeconds": row["water_interval_seconds"] if row else None,
            "wiltGraceSeconds": row["wilt_grace_seconds"] if row else None,
            "waterCostPerUse": row["water_cost_per_use"] if row else None,
        },
        "updatedBy": int(row["updated_by"]) if row and row["updated_by"] else None,
        "updatedAt": row["updated_at"].isoformat() if row and row["updated_at"] else None,
    }


async def update_farm_settings(
    *,
    tree_grow_seconds: int | None = None,
    tobacco_grow_seconds: int | None = None,
    max_plots: int | None = None,
    water_interval_seconds: int | None = None,
    wilt_grace_seconds: int | None = None,
    water_cost_per_use: int | None = None,
    plot_price_step: int | None = None,
    admin_user_id: int,
) -> dict:
    if tree_grow_seconds is not None and not (30 <= tree_grow_seconds <= 86_400):
        raise ValueError("Рост дерева: от 30 до 86400 сек")
    if tobacco_grow_seconds is not None and not (30 <= tobacco_grow_seconds <= 86_400):
        raise ValueError("Рост табака: от 30 до 86400 сек")
    if max_plots is not None and not (1 <= max_plots <= ADMIN_MAX_PLOTS):
        raise ValueError(f"Лимит грядок: от 1 до {ADMIN_MAX_PLOTS}")
    if water_interval_seconds is not None and not (30 <= water_interval_seconds <= 3600):
        raise ValueError("Интервал полива: от 30 до 3600 сек")
    if wilt_grace_seconds is not None and not (10 <= wilt_grace_seconds <= 3600):
        raise ValueError("Засуха (grace): от 10 до 3600 сек")
    if water_cost_per_use is not None and not (0 <= water_cost_per_use <= 10):
        raise ValueError("Расход воды: от 0 до 10")
    if plot_price_step is not None and not (1 <= plot_price_step <= 1_000_000):
        raise ValueError("Шаг цены грядки: от 1 до 1000000")

    before = await db.pool.fetchrow(
        """
        SELECT tree_grow_seconds, tobacco_grow_seconds, max_plots,
               water_interval_seconds, wilt_grace_seconds, water_cost_per_use,
               plot_price_step
        FROM system_settings WHERE id = 1
        """
    )

    updated = await db.pool.execute(
        """
        UPDATE system_settings SET
            tree_grow_seconds = COALESCE($1, tree_grow_seconds),
            tobacco_grow_seconds = COALESCE($2, tobacco_grow_seconds),
            max_plots = COALESCE($3, max_plots),
            water_interval_seconds = COALESCE($4, water_interval_seconds),
            wilt_grace_seconds = COALESCE($5, wilt_grace_seconds),
            water_cost_per_use = COALESCE($6, water_cost_per_use),
            plot_price_step = COALESCE($7, plot_price_step),
            updated_by = $8,
            updated_at = NOW()
        WHERE id = 1
        """,
        tree_grow_seconds,
        tobacco_grow_seconds,
        max_plots,
        water_interval_seconds,
        wilt_grace_seconds,
        water_cost_per_use,
        plot_price_step,
        admin_user_id,
    )
    if updated == "UPDATE 0":
        await ensure_system_settings_row(maintenance=False)
        before = None
        await db.pool.execute(
            """
            UPDATE system_settings SET
                tree_grow_seconds = COALESCE($1, tree_grow_seconds),
                tobacco_grow_seconds = COALESCE($2, tobacco_grow_seconds),
                max_plots = COALESCE($3, max_plots),
                water_interval_seconds = COALESCE($4, water_interval_seconds),
                wilt_grace_seconds = COALESCE($5, wilt_grace_seconds),
                water_cost_per_use = COALESCE($6, water_cost_per_use),
                plot_price_step = COALESCE($7, plot_price_step),
                updated_by = $8,
                updated_at = NOW()
            WHERE id = 1
            """,
            tree_grow_seconds, tobacco_grow_seconds, max_plots,
            water_interval_seconds, wilt_grace_seconds, water_cost_per_use,
            plot_price_step, admin_user_id,
        )
    await _refresh_cache()
    from economy_settings import refresh_economy_settings_cache
    await refresh_economy_settings_cache()
    await _log_settings_history(
        admin_user_id, before,
        tree_grow_seconds=tree_grow_seconds, tobacco_grow_seconds=tobacco_grow_seconds,
        max_plots=max_plots, water_interval_seconds=water_interval_seconds,
        wilt_grace_seconds=wilt_grace_seconds, water_cost_per_use=water_cost_per_use,
        plot_price_step=plot_price_step,
    )
    # Синхронизируем farm_crops таблицу
    try:
        await db.pool.execute(
            "UPDATE farm_crops SET grow_seconds = $1 WHERE key = 'tree'",
            get_tree_grow_seconds(),
        )
        await db.pool.execute(
            "UPDATE farm_crops SET grow_seconds = $1 WHERE key = 'tobacco'",
            get_tobacco_grow_seconds(),
        )
    except Exception:
        pass
    if max_plots is not None:
        await _trim_plots_above_max(max_plots)
    await _normalize_growing_plots()
    return await get_farm_settings_payload()


async def _log_settings_history(admin_user_id: int, before, **changed: int | None) -> None:
    # snake_case kwarg -> (camelCase setting_key, DB column) - camelCase matches the
    # naming SystemSection.jsx's History tab already knows how to label.
    key_map = {
        "tree_grow_seconds": ("treeGrowSeconds", "tree_grow_seconds"),
        "tobacco_grow_seconds": ("tobaccoGrowSeconds", "tobacco_grow_seconds"),
        "max_plots": ("maxPlots", "max_plots"),
        "water_interval_seconds": ("waterIntervalSeconds", "water_interval_seconds"),
        "wilt_grace_seconds": ("wiltGraceSeconds", "wilt_grace_seconds"),
        "water_cost_per_use": ("waterCostPerUse", "water_cost_per_use"),
        "plot_price_step": ("plotPriceStep", "plot_price_step"),
    }
    rows = []
    for arg_key, new_val in changed.items():
        if new_val is None:
            continue
        setting_key, col = key_map[arg_key]
        old_val = before[col] if before else None
        if str(new_val) != (str(old_val) if old_val is not None else None):
            rows.append((admin_user_id, "farm", setting_key, str(old_val) if old_val is not None else None, str(new_val)))
    if rows:
        await db.pool.executemany(
            """
            INSERT INTO settings_history (admin_user_id, category, setting_key, old_value, new_value)
            VALUES ($1, $2, $3, $4, $5)
            """,
            rows,
        )


async def _trim_plots_above_max(max_plots: int) -> int:
    """Удаляет грядки с номером выше лимита у всех игроков."""
    result = await db.pool.execute(
        "DELETE FROM farm_plots WHERE plot_id > $1",
        int(max_plots),
    )
    try:
        return int(str(result).split()[-1])
    except (ValueError, IndexError):
        return 0


async def _normalize_growing_plots() -> int:
    from farm_logic import normalize_grow_row, now

    current = now()
    fixed = 0
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, plot_id, status, planted_at, ripe_at, dry_at,
                   needs_water, wilt_at, waters_remaining, crop_id
            FROM farm_plots
            WHERE status = 'GROWING'
            """
        )
        for raw in rows:
            row = dict(raw)
            if normalize_grow_row(row, current):
                await conn.execute(
                    """
                    UPDATE farm_plots
                    SET planted_at = $3, ripe_at = $4, dry_at = $5,
                        needs_water = $6, wilt_at = $7, waters_remaining = $8, crop_id = $9
                    WHERE user_id = $1 AND plot_id = $2
                    """,
                    row["user_id"],
                    row["plot_id"],
                    row.get("planted_at"),
                    row.get("ripe_at"),
                    row.get("dry_at"),
                    row.get("needs_water", False),
                    row.get("wilt_at"),
                    int(row.get("waters_remaining") or 0),
                    row.get("crop_id"),
                )
                fixed += 1
    return fixed
