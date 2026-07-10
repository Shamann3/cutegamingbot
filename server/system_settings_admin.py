"""Единый контроллер системных настроек.

Читает из system_settings (одна строка id=1), логирует изменения в settings_history.
Покрывает: экономику, ферму, seed economy, таймаут сессии администратора.
"""

from __future__ import annotations

from typing import Any

from db import db
from system_settings import ensure_system_settings_row

# ---------------------------------------------------------------------------
# Env-defaults (импортируем лениво чтобы избежать circular imports)
# ---------------------------------------------------------------------------

def _env_defaults() -> dict[str, Any]:
    from config import (
        ADMIN_SESSION_MINUTES,
        CLEAR_COST,
        DEFAULT_BALANCE,
        MAX_PLOTS,
        PLOT_PRICE_STEP,
        TOBACCO_GROW_SECONDS,
        TREE_GROW_SECONDS,
        WATER_COST_PER_USE,
        WATER_INTERVAL_SECONDS,
        WILT_GRACE_SECONDS,
    )
    from seed_economy import (
        DAILY_SEED_AMOUNT,
        HARVEST_SEED_DROP_PERCENT,
        STARTER_AXE,
        STARTER_TOBACCO_SEEDS,
        STARTER_TREE_SEEDS,
        STARTER_WATER,
    )
    return {
        # economy
        "defaultBalance": DEFAULT_BALANCE,
        "plotPriceStep": PLOT_PRICE_STEP,
        "clearCost": CLEAR_COST,
        # farm
        "treeGrowSeconds": TREE_GROW_SECONDS,
        "tobaccoGrowSeconds": TOBACCO_GROW_SECONDS,
        "maxPlots": MAX_PLOTS,
        "waterIntervalSeconds": WATER_INTERVAL_SECONDS,
        "wiltGraceSeconds": WILT_GRACE_SECONDS,
        "waterCostPerUse": WATER_COST_PER_USE,
        # seed economy
        "harvestSeedDropPercent": HARVEST_SEED_DROP_PERCENT,
        "dailySeedAmount": DAILY_SEED_AMOUNT,
        "starterTreeSeeds": STARTER_TREE_SEEDS,
        "starterTobaccoSeeds": STARTER_TOBACCO_SEEDS,
        "starterWater": STARTER_WATER,
        "starterAxe": STARTER_AXE,
        # admin
        "adminSessionMinutes": ADMIN_SESSION_MINUTES,
    }


_DB_COL_MAP: dict[str, str] = {
    # economy
    "defaultBalance": "default_balance",
    "plotPriceStep": "plot_price_step",
    "clearCost": "clear_cost",
    # farm
    "treeGrowSeconds": "tree_grow_seconds",
    "tobaccoGrowSeconds": "tobacco_grow_seconds",
    "maxPlots": "max_plots",
    "waterIntervalSeconds": "water_interval_seconds",
    "wiltGraceSeconds": "wilt_grace_seconds",
    "waterCostPerUse": "water_cost_per_use",
    # seed economy
    "harvestSeedDropPercent": "harvest_seed_drop_percent",
    "dailySeedAmount": "daily_seed_amount",
    "starterTreeSeeds": "starter_tree_seeds",
    "starterTobaccoSeeds": "starter_tobacco_seeds",
    "starterWater": "starter_water",
    "starterAxe": "starter_axe",
    # admin
    "adminSessionMinutes": "admin_session_minutes",
    # maintenance is treated separately (bool, not int)
    "maintenance": "maintenance",
}

_COL_DB_MAP = {v: k for k, v in _DB_COL_MAP.items()}

# All numeric/overridable columns (excludes maintenance which is handled separately)
_ALL_COLS = [v for k, v in _DB_COL_MAP.items() if k != "maintenance"]

_VALIDATORS: dict[str, tuple[int, int]] = {
    "defaultBalance": (0, 10_000_000),
    "plotPriceStep": (0, 1_000_000),
    "clearCost": (0, 1_000_000),
    "treeGrowSeconds": (30, 86_400),
    "tobaccoGrowSeconds": (30, 86_400),
    "maxPlots": (1, 100),
    "waterIntervalSeconds": (30, 3_600),
    "wiltGraceSeconds": (10, 3_600),
    "waterCostPerUse": (0, 10),
    "harvestSeedDropPercent": (0, 100),
    "dailySeedAmount": (1, 50),
    "starterTreeSeeds": (0, 100),
    "starterTobaccoSeeds": (0, 100),
    "starterWater": (0, 100),
    "starterAxe": (0, 100),
    "adminSessionMinutes": (5, 1_440),
}

_CATEGORIES: dict[str, str] = {
    "defaultBalance": "economy",
    "plotPriceStep": "economy",
    "clearCost": "economy",
    "treeGrowSeconds": "farm",
    "tobaccoGrowSeconds": "farm",
    "maxPlots": "farm",
    "waterIntervalSeconds": "farm",
    "wiltGraceSeconds": "farm",
    "waterCostPerUse": "farm",
    "harvestSeedDropPercent": "seed",
    "dailySeedAmount": "seed",
    "starterTreeSeeds": "seed",
    "starterTobaccoSeeds": "seed",
    "starterWater": "seed",
    "starterAxe": "seed",
    "adminSessionMinutes": "system",
    "maintenance": "system",
}


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

async def get_all_settings() -> dict:
    """Возвращает все настройки: текущие значения + env-дефолты + overrides."""
    all_select = ', '.join(_ALL_COLS + ["maintenance", "updated_by", "updated_at"])
    row = await db.pool.fetchrow(
        f"SELECT {all_select} FROM system_settings WHERE id = 1"
    )
    env = _env_defaults()

    def _effective(key: str, col: str) -> Any:
        if row and row[col] is not None:
            return row[col]
        return env.get(key)

    overrides: dict[str, Any] = {}
    effective: dict[str, Any] = {}
    for js_key, col in _DB_COL_MAP.items():
        if js_key == "maintenance":
            continue
        db_val = row[col] if row else None
        overrides[js_key] = db_val
        effective[js_key] = db_val if db_val is not None else env.get(js_key)

    return {
        "effective": effective,
        "envDefaults": env,
        "overrides": overrides,
        "maintenance": bool(row["maintenance"]) if row else False,
        "updatedBy": int(row["updated_by"]) if row and row["updated_by"] else None,
        "updatedAt": row["updated_at"].isoformat() if row and row["updated_at"] else None,
    }


def get_admin_session_minutes() -> int:
    """Таймаут сессии: значение из кэша или env."""
    from admin_session_cache import get_admin_session_minutes_cached
    return get_admin_session_minutes_cached()


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

async def update_settings(
    fields: dict[str, Any],
    *,
    admin_user_id: int,
) -> dict:
    """Обновляет произвольный набор настроек, логирует в settings_history."""
    if not fields:
        raise ValueError("Нечего обновлять")

    validated: dict[str, Any] = {}
    for key, value in fields.items():
        if key not in _DB_COL_MAP:
            raise ValueError(f"Неизвестное поле: {key}")
        if value is None:
            continue
        if key in _VALIDATORS:
            lo, hi = _VALIDATORS[key]
            int_val = int(value)
            if not (lo <= int_val <= hi):
                raise ValueError(f"{key}: значение от {lo} до {hi}")
            validated[key] = int_val
        elif key == "maintenance":
            validated[key] = bool(value)
        else:
            validated[key] = value

    if not validated:
        return await get_all_settings()

    # Fetch current values for history
    cols_needed = [_DB_COL_MAP[k] for k in validated]
    current_row = await db.pool.fetchrow(
        f"SELECT {', '.join(cols_needed)} FROM system_settings WHERE id = 1"
    )

    sets = []
    params: list[Any] = []
    for key, val in validated.items():
        col = _DB_COL_MAP[key]
        params.append(val)
        sets.append(f"{col} = ${len(params)}")

    params.append(admin_user_id)
    sets.append(f"updated_by = ${len(params)}")
    sets.append("updated_at = NOW()")

    # Сначала пробуем UPDATE; если строки нет — вставляем и обновляем снова
    updated = await db.pool.execute(
        f"UPDATE system_settings SET {', '.join(sets)} WHERE id = 1",
        *params,
    )
    if updated == "UPDATE 0":
        await ensure_system_settings_row(maintenance=False)
        await db.pool.execute(
            f"UPDATE system_settings SET {', '.join(sets)} WHERE id = 1",
            *params,
        )

    # Log history
    history_rows = []
    for key, new_val in validated.items():
        col = _DB_COL_MAP[key]
        old_val = current_row[col] if current_row else None
        new_str = str(new_val)
        old_str = str(old_val) if old_val is not None else None
        if new_str != old_str:
            history_rows.append((
                admin_user_id,
                _CATEGORIES.get(key, "system"),
                key,
                old_str,
                new_str,
            ))

    if history_rows:
        await db.pool.executemany(
            """
            INSERT INTO settings_history (admin_user_id, category, setting_key, old_value, new_value)
            VALUES ($1, $2, $3, $4, $5)
            """,
            history_rows,
        )

    # Refresh downstream caches
    await _refresh_downstream_caches(validated)

    return await get_all_settings()


async def _refresh_downstream_caches(changed: dict[str, Any]) -> None:
    economy_keys = {"defaultBalance", "plotPriceStep", "clearCost"}
    farm_keys = {"treeGrowSeconds", "tobaccoGrowSeconds", "maxPlots",
                 "waterIntervalSeconds", "wiltGraceSeconds", "waterCostPerUse"}
    seed_keys = {"harvestSeedDropPercent", "dailySeedAmount",
                 "starterTreeSeeds", "starterTobaccoSeeds", "starterWater", "starterAxe"}
    session_keys = {"adminSessionMinutes"}

    if "maintenance" in changed:
        from system_settings import refresh_maintenance_cache
        await refresh_maintenance_cache()

    if economy_keys & set(changed):
        from economy_settings import refresh_economy_settings_cache
        await refresh_economy_settings_cache()

    if farm_keys & set(changed):
        from farm_settings import _refresh_cache as refresh_farm_cache
        await refresh_farm_cache()
        # Синхронизируем farm_crops с новыми значениями
        from farm_settings import get_tree_grow_seconds, get_tobacco_grow_seconds
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

    if seed_keys & set(changed):
        from seed_economy import refresh_seed_settings_cache
        await refresh_seed_settings_cache()

    if session_keys & set(changed):
        from admin_session_cache import refresh_session_cache
        await refresh_session_cache()

    if "maxPlots" in changed:
        max_val = int(changed["maxPlots"])
        from farm_settings import _trim_plots_above_max, _normalize_growing_plots
        await _trim_plots_above_max(max_val)
        await _normalize_growing_plots()


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

async def get_settings_history(
    *,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit = max(1, min(100, limit))
    offset = max(0, offset)

    where = "TRUE"
    params: list[Any] = []
    if category:
        params.append(category)
        where = f"category = ${len(params)}"

    total = int(
        await db.pool.fetchval(
            f"SELECT COUNT(*)::int FROM settings_history WHERE {where}", *params
        ) or 0
    )
    params.extend([limit, offset])
    rows = await db.pool.fetch(
        f"""
        SELECT id, admin_user_id, category, setting_key, old_value, new_value, created_at
        FROM settings_history
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """,
        *params,
    )
    return {
        "history": [
            {
                "id": int(r["id"]),
                "adminUserId": int(r["admin_user_id"]),
                "category": r["category"],
                "settingKey": r["setting_key"],
                "oldValue": r["old_value"],
                "newValue": r["new_value"],
                "createdAt": r["created_at"].isoformat(),
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
