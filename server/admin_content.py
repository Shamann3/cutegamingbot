"""Admin: контент — предметы dex, культуры, дропы, крафт."""

from __future__ import annotations

import re
from typing import Any

from admin_users import insert_admin_audit
from content_registry import (
    all_crops,
    crop_to_admin_dict,
    recipe_to_admin_dict,
    reload_content_registry,
)
from db import db
from dex_catalog import dex_catalog

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")


def _validate_key(key: str) -> str:
    key = (key or "").strip().lower()
    if not _KEY_RE.match(key):
        raise ValueError("Ключ: латиница, цифры, _, от 2 символов (a-z)")
    return key


def _dex_brief(item_id: str) -> dict[str, str]:
    entry = dex_catalog.get(item_id)
    if entry:
        return {"id": entry.id, "name": entry.name, "emoji": entry.emoji}
    return {"id": str(item_id), "name": str(item_id), "emoji": "📦"}


async def _ensure_dex_item(item_id: str, label: str) -> str:
    canon = dex_catalog.canonical_key(str(item_id).strip())
    if not canon:
        raise ValueError(f"{label}: укажите id предмета")
    if not dex_catalog.get(canon):
        raise ValueError(f"{label}: предмет {canon} не найден в dex")
    return canon


async def _invalidate_content() -> None:
    db._shop_catalog_cache.clear()
    await dex_catalog.load(db.pool)
    await reload_content_registry(db.pool)


async def get_content_overview() -> dict:
    from content_registry import all_craft_recipes, ensure_content_registry_loaded
    from quest_registry import all_quests, quest_admin_meta, quest_to_admin_dict

    await ensure_content_registry_loaded(db.pool)
    crops = [crop_to_admin_dict(crop) for crop in all_crops()]
    recipes = [recipe_to_admin_dict(recipe) for recipe in all_craft_recipes()]
    quests = [quest_to_admin_dict(quest) for quest in all_quests()]
    dex_count = int(await db.pool.fetchval("SELECT COUNT(*)::int FROM dex") or 0)
    return {
        "stats": {
            "crops": len(crops),
            "recipes": len(recipes),
            "dexItems": dex_count,
            "quests": len(quests),
        },
        "crops": crops,
        "recipes": recipes,
        "quests": quests,
        "questMeta": quest_admin_meta(),
        "spriteKeys": [
            {"id": "tree", "label": "Дерево"},
            {"id": "tobacco", "label": "Табак"},
            {"id": "generic", "label": "Универсальный"},
        ],
    }


async def list_dex_items_admin(
    *,
    search: str = "",
    limit: int = 50,
    offset: int = 0,
    scope: str = "all",
) -> dict:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    params: list[Any] = []
    where = ["TRUE"]
    q = search.strip()
    if q:
        params.append(f"%{q}%")
        idx = len(params)
        params.append(q)
        exact_idx = len(params)
        where.append(
            f"""(
                name ILIKE ${idx}
                OR COALESCE(name1, '') ILIKE ${idx}
                OR emoji ILIKE ${idx}
                OR emoji = ${exact_idx}
                OR id::text ILIKE ${idx}
            )"""
        )
    scope_norm = (scope or "all").strip().lower()
    if scope_norm == "shop":
        where.append("(COALESCE(remains, 0) > 0 OR COALESCE(price, 0) > 0)")
    where_sql = " AND ".join(where)
    total = int(
        await db.pool.fetchval(f"SELECT COUNT(*)::int FROM dex WHERE {where_sql}", *params)
        or 0
    )
    params.extend([limit, offset])
    order_sql = "name ASC NULLS LAST, id ASC" if q else "name ASC NULLS LAST, id DESC"
    rows = await db.pool.fetch(
        f"""
        SELECT id, name, name1, emoji, price, dis, remains, sorting, bio
        FROM dex
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """,
        *params,
    )
    items = []
    for row in rows:
        item_id = str(row["id"])
        items.append(
            {
                "id": item_id,
                "name": (row["name"] or "").strip() or item_id,
                "name1": (row["name1"] or "").strip(),
                "emoji": (row["emoji"] or "").strip() or "📦",
                "price": int(row["price"] or 0),
                "dis": int(row["dis"] or 0),
                "remains": int(row["remains"] or 0),
                "sorting": row["sorting"],
                "bio": (row["bio"] or "").strip(),
            }
        )
    if scope_norm == "market":
        from market_rules import is_market_listable

        items = [item for item in items if is_market_listable(item["id"])]
        total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def get_dex_item_full(item_id: str) -> dict:
    """Получить все поля предмета dex, включая use/bonus/craft."""
    try:
        dex_id = int(str(item_id).strip())
    except ValueError as exc:
        raise ValueError("Некорректный id предмета") from exc
    row = await db.pool.fetchrow(
        'SELECT id, name, name1, emoji, price, dis, remains, sorting, bio, "use", bonus, craft FROM dex WHERE id = $1',
        dex_id,
    )
    if not row:
        raise ValueError("Предмет не найден")
    return {
        "id": str(row["id"]),
        "name": (row["name"] or "").strip(),
        "name1": (row["name1"] or "").strip(),
        "emoji": (row["emoji"] or "").strip() or "📦",
        "price": int(row["price"] or 0),
        "dis": int(row["dis"] or 0),
        "remains": int(row["remains"] or 0),
        "sorting": row["sorting"],
        "bio": (row["bio"] or "").strip(),
        "use": (row["use"] or "").strip(),
        "bonus": (row["bonus"] or "").strip(),
        "craft": (row["craft"] or "").strip(),
    }


async def create_dex_item(
    *,
    name: str,
    emoji: str = "📦",
    name1: str = "",
    price: int = 0,
    dis: int = 0,
    remains: int = 0,
    sorting: str | None = None,
    bio: str = "",
    use: str = "",
    bonus: str = "",
    craft: str = "",
    admin_user_id: int,
) -> dict:
    clean_name = (name or "").strip()
    if len(clean_name) < 2:
        raise ValueError("Название предмета — минимум 2 символа")
    clean_emoji = (emoji or "📦").strip() or "📦"
    new_row = await db.pool.fetchrow(
        """
        INSERT INTO dex (id, name, name1, emoji, price, dis, remains, sorting, bio, "use", bonus, craft)
        VALUES (
            (SELECT COALESCE(MAX(id), 0) + 1 FROM dex),
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
        )
        RETURNING id, name, name1, emoji, price, dis, remains, sorting, bio, "use", bonus, craft
        """,
        clean_name,
        (name1 or "").strip(),
        clean_emoji,
        max(0, int(price)),
        max(0, int(dis)),
        max(0, int(remains)),
        sorting,
        (bio or "").strip(),
        (use or "").strip(),
        (bonus or "").strip(),
        (craft or "").strip(),
    )
    await insert_admin_audit(
        0,
        "admin_dex_create",
        admin_user_id=admin_user_id,
        details={"item_id": str(new_row["id"]), "name": clean_name},
    )
    await _invalidate_content()
    return {
        "id": str(new_row["id"]),
        "name": clean_name,
        "name1": (new_row["name1"] or "").strip(),
        "emoji": clean_emoji,
        "price": int(new_row["price"] or 0),
        "dis": int(new_row["dis"] or 0),
        "remains": int(new_row["remains"] or 0),
        "sorting": new_row["sorting"],
        "bio": (new_row["bio"] or "").strip(),
        "use": (new_row["use"] or "").strip(),
        "bonus": (new_row["bonus"] or "").strip(),
        "craft": (new_row["craft"] or "").strip(),
    }


async def update_dex_item_meta(
    item_id: str,
    *,
    name: str | None = None,
    emoji: str | None = None,
    name1: str | None = None,
    price: int | None = None,
    dis: int | None = None,
    remains: int | None = None,
    sorting: str | None = None,
    bio: str | None = None,
    use: str | None = None,
    bonus: str | None = None,
    craft: str | None = None,
    admin_user_id: int,
) -> dict:
    try:
        dex_id = int(str(item_id).strip())
    except ValueError as exc:
        raise ValueError("Некорректный id предмета") from exc

    sets = []
    params: list[Any] = [dex_id]
    if name is not None:
        clean = name.strip()
        if len(clean) < 2:
            raise ValueError("Название — минимум 2 символа")
        params.append(clean)
        sets.append(f"name = ${len(params)}")
    if emoji is not None:
        params.append((emoji or "📦").strip() or "📦")
        sets.append(f"emoji = ${len(params)}")
    if name1 is not None:
        params.append(name1.strip())
        sets.append(f"name1 = ${len(params)}")
    if price is not None:
        params.append(max(0, int(price)))
        sets.append(f"price = ${len(params)}")
    if dis is not None:
        params.append(max(0, int(dis)))
        sets.append(f"dis = ${len(params)}")
    if remains is not None:
        params.append(max(0, int(remains)))
        sets.append(f"remains = ${len(params)}")
    if sorting is not None:
        params.append(sorting)
        sets.append(f"sorting = ${len(params)}")
    if bio is not None:
        params.append(bio.strip())
        sets.append(f"bio = ${len(params)}")
    if use is not None:
        params.append(use.strip())
        sets.append(f'"use" = ${len(params)}')
    if bonus is not None:
        params.append(bonus.strip())
        sets.append(f"bonus = ${len(params)}")
    if craft is not None:
        params.append(craft.strip())
        sets.append(f"craft = ${len(params)}")

    if not sets:
        raise ValueError("Нечего обновлять")

    row = await db.pool.fetchrow(
        f"""
        UPDATE dex SET {', '.join(sets)}
        WHERE id = $1
        RETURNING id, name, name1, emoji, price, dis, remains, sorting, bio, "use", bonus, craft
        """,
        *params,
    )
    if row is None:
        raise ValueError("Предмет не найден")

    await insert_admin_audit(
        0,
        "admin_dex_update",
        admin_user_id=admin_user_id,
        details={"item_id": str(dex_id)},
    )
    await _invalidate_content()
    return {
        "id": str(row["id"]),
        "name": (row["name"] or "").strip(),
        "name1": (row["name1"] or "").strip(),
        "emoji": (row["emoji"] or "").strip() or "📦",
        "price": int(row["price"] or 0),
        "dis": int(row["dis"] or 0),
        "remains": int(row["remains"] or 0),
        "sorting": row["sorting"],
        "bio": (row["bio"] or "").strip(),
        "use": (row["use"] or "").strip(),
        "bonus": (row["bonus"] or "").strip(),
        "craft": (row["craft"] or "").strip(),
    }


async def delete_dex_item(item_id: str, *, admin_user_id: int) -> dict:
    """Удалить предмет dex с проверкой использования."""
    try:
        dex_id = int(str(item_id).strip())
    except ValueError as exc:
        raise ValueError("Некорректный id предмета") from exc

    item_id_str = str(dex_id)

    # Проверяем использование в культурах (seed_item_id, harvest_tool_item_id, water_item_id)
    crop_uses = await db.pool.fetchval(
        """
        SELECT COUNT(*) FROM farm_crops
        WHERE seed_item_id = $1 OR harvest_tool_item_id = $1 OR water_item_id = $1
          OR EXISTS (
              SELECT 1 FROM farm_crop_harvest_drops d
              WHERE d.crop_id = farm_crops.id AND d.item_id = $1
          )
        """,
        item_id_str,
    )
    if int(crop_uses or 0) > 0:
        raise ValueError(f"Предмет используется в {crop_uses} культур(ах) - сначала удалите их")

    # Проверяем использование в крафт-рецептах
    craft_uses = await db.pool.fetchval(
        """
        SELECT COUNT(*) FROM craft_recipes
        WHERE result_item_id = $1
           OR ingredient_a_id = $1
           OR ingredient_b_id = $1
        """,
        item_id_str,
    )
    if int(craft_uses or 0) > 0:
        raise ValueError(f"Предмет используется в {craft_uses} рецепт(ах) — сначала удалите их")

    # Проверяем активные лоты на бирже
    market_uses = await db.pool.fetchval(
        "SELECT COUNT(*) FROM market_listings WHERE item_id = $1 AND status = 'active'",
        item_id_str,
    )
    if int(market_uses or 0) > 0:
        raise ValueError(f"Предмет есть в {market_uses} активных лотах биржи")

    row = await db.pool.fetchrow(
        "DELETE FROM dex WHERE id = $1 RETURNING id, name",
        dex_id,
    )
    if not row:
        raise ValueError("Предмет не найден")

    await insert_admin_audit(
        0,
        "admin_dex_delete",
        admin_user_id=admin_user_id,
        details={"item_id": item_id_str, "name": str(row["name"])},
    )
    await _invalidate_content()
    return {"deleted": True, "id": item_id_str, "name": str(row["name"])}


async def _load_crop_row(crop_id: int):
    row = await db.pool.fetchrow(
        """
        SELECT id, key, display_name, seed_item_id, grow_seconds,
               harvest_tool_item_id, harvest_tool_cost,
               water_item_id, water_cost_per_use,
               sprite_key, enabled, sort_order
        FROM farm_crops WHERE id = $1
        """,
        crop_id,
    )
    if row is None:
        raise ValueError("Культура не найдена")
    drops = await db.pool.fetch(
        """
        SELECT item_id, min_amount, max_amount, chance_percent, sort_order
        FROM farm_crop_harvest_drops
        WHERE crop_id = $1
        ORDER BY sort_order ASC, id ASC
        """,
        crop_id,
    )
    from content_registry import CropDef, HarvestDropDef

    drop_defs = tuple(
        HarvestDropDef(
            item_id=str(d["item_id"]),
            min_amount=int(d["min_amount"]),
            max_amount=int(d["max_amount"]),
            chance_percent=int(d["chance_percent"]),
        )
        for d in drops
    )
    crop = CropDef(
        db_id=int(row["id"]),
        key=str(row["key"]),
        display_name=(row["display_name"] or "").strip(),
        seed_id=str(row["seed_item_id"]),
        grow_seconds=int(row["grow_seconds"]),
        harvest_tool_item_id=(
            str(row["harvest_tool_item_id"]) if row["harvest_tool_item_id"] else None
        ),
        harvest_tool_cost=int(row["harvest_tool_cost"] or 1),
        water_item_id=str(row["water_item_id"]) if row["water_item_id"] else None,
        water_cost_per_use=(
            int(row["water_cost_per_use"])
            if row["water_cost_per_use"] is not None
            else None
        ),
        sprite_key=(row["sprite_key"] or "generic").strip(),
        enabled=bool(row["enabled"]),
        harvest_drops=drop_defs,
    )
    return crop_to_admin_dict(crop)


def _validate_harvest_drops(drops: list[dict]) -> list[dict]:
    if not drops:
        raise ValueError("Добавьте хотя бы один предмет урожая")
    cleaned: list[dict] = []
    for idx, drop in enumerate(drops):
        item_id = str(drop.get("itemId") or drop.get("item_id") or "").strip()
        if not item_id:
            raise ValueError(f"Дроп #{idx + 1}: укажите предмет")
        min_amount = max(1, int(drop.get("minAmount") or drop.get("min_amount") or 1))
        max_amount = max(min_amount, int(drop.get("maxAmount") or drop.get("max_amount") or min_amount))
        chance = max(1, min(100, int(drop.get("chancePercent") or drop.get("chance_percent") or 100)))
        cleaned.append(
            {
                "item_id": item_id,
                "min_amount": min_amount,
                "max_amount": max_amount,
                "chance_percent": chance,
                "sort_order": idx,
            }
        )
    return cleaned


async def create_crop(
    *,
    key: str,
    display_name: str,
    seed_item_id: str,
    grow_seconds: int,
    harvest_tool_item_id: str | None = None,
    harvest_tool_cost: int = 1,
    water_item_id: str | None = None,
    water_cost_per_use: int | None = None,
    sprite_key: str = "generic",
    enabled: bool = True,
    harvest_drops: list[dict],
    admin_user_id: int,
) -> dict:
    key = _validate_key(key)
    exists = await db.pool.fetchval("SELECT 1 FROM farm_crops WHERE key = $1", key)
    if exists:
        raise ValueError(f"Культура с ключом «{key}» уже есть")

    seed_id = await _ensure_dex_item(seed_item_id, "Саженец")
    dup_seed = await db.pool.fetchval(
        "SELECT key FROM farm_crops WHERE seed_item_id = $1", seed_id
    )
    if dup_seed:
        raise ValueError(f"Саженец уже используется культурой «{dup_seed}»")

    tool_id = None
    if harvest_tool_item_id:
        tool_id = await _ensure_dex_item(harvest_tool_item_id, "Инструмент сбора")
    water_id = None
    if water_item_id:
        water_id = await _ensure_dex_item(water_item_id, "Предмет полива")

    drops = _validate_harvest_drops(harvest_drops)
    for drop in drops:
        await _ensure_dex_item(drop["item_id"], "Урожай")

    sort_order = int(
        await db.pool.fetchval("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM farm_crops") or 0
    )

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            crop_id = await conn.fetchval(
                """
                INSERT INTO farm_crops (
                    key, display_name, seed_item_id, grow_seconds,
                    harvest_tool_item_id, harvest_tool_cost,
                    water_item_id, water_cost_per_use,
                    sprite_key, enabled, sort_order
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
                """,
                key,
                (display_name or key).strip(),
                seed_id,
                max(30, int(grow_seconds)),
                tool_id,
                max(1, int(harvest_tool_cost)),
                water_id,
                water_cost_per_use,
                (sprite_key or "generic").strip() or "generic",
                bool(enabled),
                sort_order,
            )
            for drop in drops:
                await conn.execute(
                    """
                    INSERT INTO farm_crop_harvest_drops (
                        crop_id, item_id, min_amount, max_amount, chance_percent, sort_order
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    crop_id,
                    drop["item_id"],
                    drop["min_amount"],
                    drop["max_amount"],
                    drop["chance_percent"],
                    drop["sort_order"],
                )

    await insert_admin_audit(
        0,
        "admin_crop_create",
        admin_user_id=admin_user_id,
        details={"crop_id": int(crop_id), "key": key},
    )
    await _invalidate_content()
    return await _load_crop_row(int(crop_id))


async def update_crop(
    crop_id: int,
    *,
    display_name: str | None = None,
    seed_item_id: str | None = None,
    grow_seconds: int | None = None,
    harvest_tool_item_id: str | None = None,
    harvest_tool_cost: int | None = None,
    water_item_id: str | None = None,
    water_cost_per_use: int | None = None,
    sprite_key: str | None = None,
    enabled: bool | None = None,
    harvest_drops: list[dict] | None = None,
    clear_harvest_tool: bool = False,
    clear_water_item: bool = False,
    admin_user_id: int,
) -> dict:
    row = await db.pool.fetchrow("SELECT id, key FROM farm_crops WHERE id = $1", crop_id)
    if row is None:
        raise ValueError("Культура не найдена")

    sets = []
    params: list[Any] = [crop_id]

    if display_name is not None:
        params.append(display_name.strip())
        sets.append(f"display_name = ${len(params)}")
    if seed_item_id is not None:
        seed_id = await _ensure_dex_item(seed_item_id, "Саженец")
        dup = await db.pool.fetchval(
            "SELECT key FROM farm_crops WHERE seed_item_id = $1 AND id <> $2",
            seed_id,
            crop_id,
        )
        if dup:
            raise ValueError(f"Саженец уже используется культурой «{dup}»")
        params.append(seed_id)
        sets.append(f"seed_item_id = ${len(params)}")
    if grow_seconds is not None:
        params.append(max(30, int(grow_seconds)))
        sets.append(f"grow_seconds = ${len(params)}")
    if clear_harvest_tool:
        sets.append("harvest_tool_item_id = NULL")
    elif harvest_tool_item_id is not None:
        tool_id = await _ensure_dex_item(harvest_tool_item_id, "Инструмент сбора")
        params.append(tool_id)
        sets.append(f"harvest_tool_item_id = ${len(params)}")
    if harvest_tool_cost is not None:
        params.append(max(1, int(harvest_tool_cost)))
        sets.append(f"harvest_tool_cost = ${len(params)}")
    if clear_water_item:
        sets.append("water_item_id = NULL")
        sets.append("water_cost_per_use = NULL")
    elif water_item_id is not None:
        water_id = await _ensure_dex_item(water_item_id, "Предмет полива")
        params.append(water_id)
        sets.append(f"water_item_id = ${len(params)}")
    if water_cost_per_use is not None:
        params.append(max(1, int(water_cost_per_use)))
        sets.append(f"water_cost_per_use = ${len(params)}")
    if sprite_key is not None:
        params.append((sprite_key or "generic").strip() or "generic")
        sets.append(f"sprite_key = ${len(params)}")
    if enabled is not None:
        params.append(bool(enabled))
        sets.append(f"enabled = ${len(params)}")

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            if sets:
                sets.append("updated_at = NOW()")
                await conn.execute(
                    f"UPDATE farm_crops SET {', '.join(sets)} WHERE id = $1",
                    *params,
                )
            if harvest_drops is not None:
                drops = _validate_harvest_drops(harvest_drops)
                for drop in drops:
                    await _ensure_dex_item(drop["item_id"], "Урожай")
                await conn.execute(
                    "DELETE FROM farm_crop_harvest_drops WHERE crop_id = $1", crop_id
                )
                for drop in drops:
                    await conn.execute(
                        """
                        INSERT INTO farm_crop_harvest_drops (
                            crop_id, item_id, min_amount, max_amount, chance_percent, sort_order
                        )
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        crop_id,
                        drop["item_id"],
                        drop["min_amount"],
                        drop["max_amount"],
                        drop["chance_percent"],
                        drop["sort_order"],
                    )

    await insert_admin_audit(
        0,
        "admin_crop_update",
        admin_user_id=admin_user_id,
        details={"crop_id": crop_id, "key": row["key"]},
    )
    await _invalidate_content()
    return await _load_crop_row(crop_id)


async def delete_crop(crop_id: int, *, admin_user_id: int) -> dict:
    row = await db.pool.fetchrow("SELECT key FROM farm_crops WHERE id = $1", crop_id)
    if row is None:
        raise ValueError("Культура не найдена")
    count = int(await db.pool.fetchval("SELECT COUNT(*)::int FROM farm_crops") or 0)
    if count <= 1:
        raise ValueError("Нельзя удалить последнюю культуру")
    await db.pool.execute("DELETE FROM farm_crops WHERE id = $1", crop_id)
    await insert_admin_audit(
        0,
        "admin_crop_delete",
        admin_user_id=admin_user_id,
        details={"crop_id": crop_id, "key": row["key"]},
    )
    await _invalidate_content()
    return {"deleted": True, "id": crop_id}


async def create_craft_recipe(
    *,
    key: str,
    display_name: str = "",
    result_item_id: str,
    ingredient_a_id: str,
    ingredient_b_id: str,
    success_percent: int = 100,
    enabled: bool = True,
    remains: int = 0,
    result_qty: int = 1,
    admin_user_id: int,
) -> dict:
    key = _validate_key(key)
    exists = await db.pool.fetchval("SELECT 1 FROM craft_recipes WHERE key = $1", key)
    if exists:
        raise ValueError(f"Рецепт «{key}» уже есть")

    result_id = await _ensure_dex_item(result_item_id, "Результат")
    ing_a = await _ensure_dex_item(ingredient_a_id, "Ингредиент A")
    ing_b = await _ensure_dex_item(ingredient_b_id, "Ингредиент B")

    pair_exists = await db.pool.fetchval(
        """
        SELECT key FROM craft_recipes
        WHERE (
            (ingredient_a_id = $1 AND ingredient_b_id = $2)
            OR (ingredient_a_id = $2 AND ingredient_b_id = $1)
        )
        """,
        ing_a,
        ing_b,
    )
    if pair_exists:
        raise ValueError(f"Такая пара уже есть в рецепте «{pair_exists}»")

    sort_order = int(
        await db.pool.fetchval("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM craft_recipes") or 0
    )
    recipe_id = await db.pool.fetchval(
        """
        INSERT INTO craft_recipes (
            key, display_name, result_item_id, ingredient_a_id, ingredient_b_id,
            success_percent, enabled, sort_order, remains, result_qty
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
        """,
        key,
        (display_name or key).strip(),
        result_id,
        ing_a,
        ing_b,
        max(1, min(100, int(success_percent))),
        bool(enabled),
        sort_order,
        max(0, int(remains)),
        max(1, int(result_qty)),
    )
    await insert_admin_audit(
        0,
        "admin_craft_create",
        admin_user_id=admin_user_id,
        details={"recipe_id": int(recipe_id), "key": key},
    )
    await _invalidate_content()
    from content_registry import get_craft_recipe_by_id

    recipe = get_craft_recipe_by_id(int(recipe_id))
    if not recipe:
        raise ValueError("Рецепт создан, но не загрузился")
    return recipe_to_admin_dict(recipe)


async def update_craft_recipe(
    recipe_id: int,
    *,
    display_name: str | None = None,
    result_item_id: str | None = None,
    ingredient_a_id: str | None = None,
    ingredient_b_id: str | None = None,
    success_percent: int | None = None,
    enabled: bool | None = None,
    remains: int | None = None,
    result_qty: int | None = None,
    admin_user_id: int,
) -> dict:
    row = await db.pool.fetchrow(
        "SELECT id, key, ingredient_a_id, ingredient_b_id FROM craft_recipes WHERE id = $1",
        recipe_id,
    )
    if row is None:
        raise ValueError("Рецепт не найден")

    ing_a = str(row["ingredient_a_id"])
    ing_b = str(row["ingredient_b_id"])
    if ingredient_a_id is not None:
        ing_a = await _ensure_dex_item(ingredient_a_id, "Ингредиент A")
    if ingredient_b_id is not None:
        ing_b = await _ensure_dex_item(ingredient_b_id, "Ингредиент B")

    pair_exists = await db.pool.fetchval(
        """
        SELECT key FROM craft_recipes
        WHERE id <> $1
        AND (
            (ingredient_a_id = $2 AND ingredient_b_id = $3)
            OR (ingredient_a_id = $3 AND ingredient_b_id = $2)
        )
        """,
        recipe_id,
        ing_a,
        ing_b,
    )
    if pair_exists:
        raise ValueError(f"Такая пара уже есть в рецепте «{pair_exists}»")

    result_id = None
    if result_item_id is not None:
        result_id = await _ensure_dex_item(result_item_id, "Результат")

    sets = []
    params: list[Any] = [recipe_id]
    if display_name is not None:
        params.append(display_name.strip())
        sets.append(f"display_name = ${len(params)}")
    if result_id is not None:
        params.append(result_id)
        sets.append(f"result_item_id = ${len(params)}")
    params.append(ing_a)
    sets.append(f"ingredient_a_id = ${len(params)}")
    params.append(ing_b)
    sets.append(f"ingredient_b_id = ${len(params)}")
    if success_percent is not None:
        params.append(max(1, min(100, int(success_percent))))
        sets.append(f"success_percent = ${len(params)}")
    if enabled is not None:
        params.append(bool(enabled))
        sets.append(f"enabled = ${len(params)}")
    if remains is not None:
        params.append(max(0, int(remains)))
        sets.append(f"remains = ${len(params)}")
    if result_qty is not None:
        params.append(max(1, int(result_qty)))
        sets.append(f"result_qty = ${len(params)}")

    if sets:
        sets.append("updated_at = NOW()")
        await db.pool.execute(
            f"UPDATE craft_recipes SET {', '.join(sets)} WHERE id = $1",
            *params,
        )

    await insert_admin_audit(
        0,
        "admin_craft_update",
        admin_user_id=admin_user_id,
        details={"recipe_id": recipe_id, "key": row["key"]},
    )
    await _invalidate_content()
    from content_registry import get_craft_recipe_by_id

    recipe = get_craft_recipe_by_id(recipe_id)
    if not recipe:
        raise ValueError("Рецепт не найден после обновления")
    return recipe_to_admin_dict(recipe)


async def delete_craft_recipe(recipe_id: int, *, admin_user_id: int) -> dict:
    row = await db.pool.fetchrow("SELECT key FROM craft_recipes WHERE id = $1", recipe_id)
    if row is None:
        raise ValueError("Рецепт не найден")
    await db.pool.execute("DELETE FROM craft_recipes WHERE id = $1", recipe_id)
    await insert_admin_audit(
        0,
        "admin_craft_delete",
        admin_user_id=admin_user_id,
        details={"recipe_id": recipe_id, "key": row["key"]},
    )
    await _invalidate_content()
    return {"deleted": True, "id": recipe_id}
