"""Экономические настройки — runtime-override поверх env/code.

Шаг цены грядки (plot_price_step) здесь только ЧИТАЕТСЯ (get_plot_price_step) -
это farm_settings.py::update_farm_settings единственное место, где он
редактируется, чтобы не было дублирующих экранов для одного и того же поля."""

from __future__ import annotations

from config import CLEAR_COST as ENV_CLEAR_COST
from config import DEFAULT_BALANCE as ENV_DEFAULT_BALANCE
from config import PLOT_PRICE_STEP as ENV_PLOT_PRICE_STEP
from db import db
from system_settings import ensure_system_settings_row

_cache: dict[str, int | None] | None = None


async def init_economy_settings() -> None:
    global _cache
    row = await db.pool.fetchrow(
        """
        SELECT default_balance, plot_price_step, clear_cost
        FROM system_settings WHERE id = 1
        """
    )
    if row is None:
        await ensure_system_settings_row(maintenance=False)
        _cache = {"default_balance": None, "plot_price_step": None, "clear_cost": None}
    else:
        _cache = {
            "default_balance": row["default_balance"],
            "plot_price_step": row["plot_price_step"],
            "clear_cost": row["clear_cost"],
        }


async def _refresh_cache() -> None:
    global _cache
    row = await db.pool.fetchrow(
        """
        SELECT default_balance, plot_price_step, clear_cost
        FROM system_settings WHERE id = 1
        """
    )
    if row is None:
        await init_economy_settings()
        return
    _cache = {
        "default_balance": row["default_balance"],
        "plot_price_step": row["plot_price_step"],
        "clear_cost": row["clear_cost"],
    }


async def refresh_economy_settings_cache() -> None:
    await _refresh_cache()


def get_default_balance() -> int:
    if _cache and _cache.get("default_balance") is not None:
        return int(_cache["default_balance"])
    return ENV_DEFAULT_BALANCE


def get_plot_price_step() -> int:
    if _cache and _cache.get("plot_price_step") is not None:
        return int(_cache["plot_price_step"])
    return ENV_PLOT_PRICE_STEP


def get_clear_cost() -> int:
    if _cache and _cache.get("clear_cost") is not None:
        return int(_cache["clear_cost"])
    return ENV_CLEAR_COST


async def get_economy_settings_payload() -> dict:
    await _refresh_cache()
    row = await db.pool.fetchrow(
        """
        SELECT default_balance, plot_price_step, clear_cost, updated_by, updated_at
        FROM system_settings WHERE id = 1
        """
    )
    return {
        "defaultBalance": get_default_balance(),
        "plotPriceStep": get_plot_price_step(),
        "clearCost": get_clear_cost(),
        "envDefaults": {
            "defaultBalance": ENV_DEFAULT_BALANCE,
            "plotPriceStep": ENV_PLOT_PRICE_STEP,
            "clearCost": ENV_CLEAR_COST,
        },
        "overrides": {
            "defaultBalance": row["default_balance"] if row else None,
            "plotPriceStep": row["plot_price_step"] if row else None,
            "clearCost": row["clear_cost"] if row else None,
        },
        "updatedBy": int(row["updated_by"]) if row and row["updated_by"] else None,
        "updatedAt": row["updated_at"].isoformat() if row and row["updated_at"] else None,
    }


async def update_economy_settings(
    *,
    default_balance: int | None = None,
    clear_cost: int | None = None,
    admin_user_id: int,
) -> dict:
    if default_balance is not None and default_balance < 0:
        raise ValueError("Стартовый баланс не может быть отрицательным")
    if clear_cost is not None and clear_cost < 0:
        raise ValueError("Стоимость очистки не может быть отрицательной")

    before = await db.pool.fetchrow(
        "SELECT default_balance, clear_cost FROM system_settings WHERE id = 1"
    )

    updated = await db.pool.execute(
        """
        UPDATE system_settings SET
            default_balance = COALESCE($1, default_balance),
            clear_cost = COALESCE($2, clear_cost),
            updated_by = $3,
            updated_at = NOW()
        WHERE id = 1
        """,
        default_balance, clear_cost, admin_user_id,
    )
    if updated == "UPDATE 0":
        await ensure_system_settings_row(maintenance=False)
        before = None
        await db.pool.execute(
            """
            UPDATE system_settings SET
                default_balance = COALESCE($1, default_balance),
                clear_cost = COALESCE($2, clear_cost),
                updated_by = $3,
                updated_at = NOW()
            WHERE id = 1
            """,
            default_balance, clear_cost, admin_user_id,
        )
    await _refresh_cache()
    await _log_settings_history(admin_user_id, before, default_balance=default_balance, clear_cost=clear_cost)
    return await get_economy_settings_payload()


async def _log_settings_history(
    admin_user_id: int,
    before,
    *,
    default_balance: int | None,
    clear_cost: int | None,
) -> None:
    changed = {"defaultBalance": default_balance, "clearCost": clear_cost}
    col_by_key = {"defaultBalance": "default_balance", "clearCost": "clear_cost"}
    rows = []
    for key, new_val in changed.items():
        if new_val is None:
            continue
        old_val = before[col_by_key[key]] if before else None
        if str(new_val) != (str(old_val) if old_val is not None else None):
            rows.append((admin_user_id, "economy", key, str(old_val) if old_val is not None else None, str(new_val)))
    if rows:
        await db.pool.executemany(
            """
            INSERT INTO settings_history (admin_user_id, category, setting_key, old_value, new_value)
            VALUES ($1, $2, $3, $4, $5)
            """,
            rows,
        )
