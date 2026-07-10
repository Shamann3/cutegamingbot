"""Admin: экономика — настройки, dex, сводка, массовая выдача кут."""

from __future__ import annotations

from config import ONLINE_WINDOW_SECONDS
from farm_settings import get_max_plots
from craft_definitions import enabled_craft_recipes
from db import db
from dex_catalog import dex_catalog
from economy_settings import get_economy_settings_payload, get_plot_price_step, update_economy_settings
from admin_users import admin_adjust_balance, insert_admin_audit
from shop_catalog import effective_price


async def get_economy_overview() -> dict:
    settings = await get_economy_settings_payload()
    stats = await get_economy_stats()
    plots = get_plot_prices()
    craft = get_craft_recipes()
    return {
        "settings": settings,
        "stats": stats,
        "plots": plots,
        "craftRecipes": craft,
    }


def get_plot_prices() -> list[dict]:
    step = get_plot_price_step()
    max_plots = get_max_plots()
    rows = []
    for plot_id in range(2, max_plots + 1):
        rows.append(
            {
                "plotId": plot_id,
                "price": (plot_id - 1) * step,
            }
        )
    return rows


def get_craft_recipes() -> list[dict]:
    recipes = []
    for recipe in enabled_craft_recipes():
        ing_a, ing_b = recipe.ingredient_ids
        result = dex_catalog.get(recipe.result_id)
        ing_a_entry = dex_catalog.get(ing_a)
        ing_b_entry = dex_catalog.get(ing_b)
        recipes.append(
            {
                "id": recipe.id,
                "key": recipe.key,
                "successPercent": recipe.success_percent,
                "result": _dex_brief(recipe.result_id, result),
                "ingredients": [
                    _dex_brief(ing_a, ing_a_entry),
                    _dex_brief(ing_b, ing_b_entry),
                ],
            }
        )
    return recipes


def _dex_brief(item_id: str, entry) -> dict:
    if entry:
        return {
            "id": str(item_id),
            "name": entry.name,
            "emoji": entry.emoji,
        }
    return {"id": str(item_id), "name": str(item_id), "emoji": "📦"}


async def get_economy_stats(*, top_limit: int = 15) -> dict:
    top_limit = max(1, min(top_limit, 50))
    row = await db.pool.fetchrow(
        """
        SELECT
            COUNT(*)::int AS players,
            COALESCE(SUM(balance), 0)::bigint AS total_kut,
            COALESCE(AVG(balance), 0)::float AS avg_balance
        FROM users
        """
    )
    top_rows = await db.pool.fetch(
        """
        SELECT user_id, username, display_name, first_name, balance, banned
        FROM users
        ORDER BY balance DESC, user_id ASC
        LIMIT $1
        """,
        top_limit,
    )
    online_count = int(
        await db.pool.fetchval(
            """
            SELECT COUNT(*)::int FROM users
            WHERE last_seen_at IS NOT NULL
              AND last_seen_at >= NOW() - ($1 * INTERVAL '1 second')
            """,
            max(15, ONLINE_WINDOW_SECONDS),
        )
        or 0
    )
    dex_count = int(await db.pool.fetchval("SELECT COUNT(*)::int FROM dex") or 0)
    shop_items = int(
        await db.pool.fetchval("SELECT COUNT(*)::int FROM dex WHERE remains > 0") or 0
    )

    top_rich = []
    for r in top_rows:
        name = r["display_name"] or r["first_name"] or str(r["user_id"])
        top_rich.append(
            {
                "userId": int(r["user_id"]),
                "username": r["username"],
                "displayName": name,
                "balance": int(r["balance"] or 0),
                "banned": bool(r["banned"]),
            }
        )

    players = int(row["players"] or 0)
    total_kut = int(row["total_kut"] or 0)
    avg_balance = float(row["avg_balance"] or 0)

    return {
        "players": players,
        "totalKut": total_kut,
        "avgBalance": round(avg_balance, 1),
        "onlineNow": online_count,
        "dexItems": dex_count,
        "shopInStock": shop_items,
        "topRich": top_rich,
    }


async def list_dex_items(
    *,
    search: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    params: list = []
    where = ["TRUE"]
    q = (search or "").strip()
    if q:
        params.append(f"%{q}%")
        idx = len(params)
        where.append(
            f"(name ILIKE ${idx} OR emoji ILIKE ${idx})"
        )

    where_sql = " AND ".join(where)
    total = int(
        await db.pool.fetchval(f"SELECT COUNT(*)::int FROM dex WHERE {where_sql}", *params)
        or 0
    )
    params.extend([limit, offset])
    rows = await db.pool.fetch(
        f"""
        SELECT id, name, name1, emoji, price, dis, remains, sorting
        FROM dex
        WHERE {where_sql}
        ORDER BY name NULLS LAST, id
        LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """,
        *params,
    )

    items = []
    for row in rows:
        price = int(row["price"] or 0)
        dis = int(row["dis"] or 0)
        items.append(
            {
                "id": str(row["id"]),
                "name": (row["name"] or "").strip() or str(row["id"]),
                "name1": (row["name1"] or "").strip(),
                "emoji": (row["emoji"] or "").strip() or "📦",
                "price": price,
                "dis": dis,
                "effectivePrice": effective_price(price, dis),
                "remains": int(row["remains"] or 0),
                "sorting": row["sorting"],
            }
        )

    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def update_dex_item(
    item_id: str,
    *,
    price: int | None = None,
    dis: int | None = None,
    remains: int | None = None,
    admin_user_id: int,
) -> dict:
    try:
        dex_id = int(str(item_id).strip())
    except ValueError as exc:
        raise ValueError("Некорректный id предмета") from exc

    if price is not None and price < 0:
        raise ValueError("Цена не может быть отрицательной")
    if dis is not None and dis < 0:
        raise ValueError("Скидка не может быть отрицательной")
    if remains is not None and remains < 0:
        raise ValueError("Остаток не может быть отрицательным")

    sets = []
    params: list = [dex_id]
    if price is not None:
        params.append(price)
        sets.append(f"price = ${len(params)}")
    if dis is not None:
        params.append(dis)
        sets.append(f"dis = ${len(params)}")
    if remains is not None:
        params.append(remains)
        sets.append(f"remains = ${len(params)}")

    if not sets:
        raise ValueError("Нечего обновлять")

    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE dex SET {', '.join(sets)} WHERE id = $1 RETURNING id, name, price, dis, remains",
            *params,
        )
        if row is None:
            raise ValueError("Предмет не найден в dex")

    db._shop_catalog_cache.clear()
    await dex_catalog.load(db.pool)

    await insert_admin_audit(
        0,
        "admin_dex",
        admin_user_id=admin_user_id,
        details={
            "item_id": str(dex_id),
            "price": price,
            "dis": dis,
            "remains": remains,
        },
    )

    price_val = int(row["price"] or 0)
    dis_val = int(row["dis"] or 0)
    return {
        "id": str(row["id"]),
        "name": (row["name"] or "").strip() or str(row["id"]),
        "price": price_val,
        "dis": dis_val,
        "effectivePrice": effective_price(price_val, dis_val),
        "remains": int(row["remains"] or 0),
    }


async def bulk_grant_kut(
    delta: int,
    *,
    target: str,
    note: str = "",
    admin_user_id: int,
) -> dict:
    if delta == 0:
        raise ValueError("Сумма выдачи не может быть 0")
    if abs(delta) > 1_000_000:
        raise ValueError("Слишком большое изменение за один раз")

    target = (target or "all").strip().lower()
    note_clean = note.strip()

    if target == "online":
        window = max(15, ONLINE_WINDOW_SECONDS)
        user_ids = [
            int(r["user_id"])
            for r in await db.pool.fetch(
                """
                SELECT user_id FROM users
                WHERE banned = FALSE
                  AND last_seen_at IS NOT NULL
                  AND last_seen_at >= NOW() - ($1 * INTERVAL '1 second')
                ORDER BY user_id
                """,
                window,
            )
        ]
    elif target == "all":
        user_ids = [
            int(r["user_id"])
            for r in await db.pool.fetch(
                "SELECT user_id FROM users WHERE banned = FALSE ORDER BY user_id"
            )
        ]
    else:
        raise ValueError("target: all или online")

    if not user_ids:
        raise ValueError("Нет игроков для выдачи")

    if len(user_ids) > 50_000:
        raise ValueError("Слишком много игроков — разбейте на части")

    # Single bulk UPDATE instead of O(n) individual transactions.
    # This avoids HTTP timeouts for large player bases and reduces DB load drastically.
    result = await db.pool.execute(
        """
        UPDATE users
        SET balance = balance + $1
        WHERE user_id = ANY($2::bigint[])
          AND banned = FALSE
        """,
        delta,
        user_ids,
    )
    # Parse "UPDATE N" result string
    try:
        success = int(result.split()[-1])
    except Exception:
        success = len(user_ids)
    skipped = len(user_ids) - success

    # Send in-app notifications (non-blocking fire-and-forget per user)
    from admin_player_notify import notify_bulk_kut_grant
    import asyncio

    async def _notify_all():
        rows = await db.pool.fetch(
            "SELECT user_id, balance FROM users WHERE user_id = ANY($1::bigint[])",
            user_ids,
        )
        for r in rows:
            notify_bulk_kut_grant(
                int(r["user_id"]),
                delta=delta,
                balance_after=int(r["balance"]),
                note=note_clean,
            )

    asyncio.create_task(_notify_all())

    await insert_admin_audit(
        0,
        "admin_bulk_grant",
        admin_user_id=admin_user_id,
        amount=delta * success,
        details={
            "target": target,
            "delta": delta,
            "success": success,
            "skipped": skipped,
            "note": note_clean,
        },
    )

    return {
        "target": target,
        "delta": delta,
        "success": success,
        "skipped": skipped,
        "totalKut": delta * success,
    }


__all__ = [
    "bulk_grant_kut",
    "get_economy_overview",
    "get_economy_stats",
    "get_plot_prices",
    "get_craft_recipes",
    "list_dex_items",
    "update_dex_item",
    "update_economy_settings",
]
