"""Культуры, дропы урожая и крафт — загрузка из БД с кэшем."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

import asyncpg

from config import (
    AUTOWATER_ITEM_KEY,
    AXE_ITEM_KEY,
    SEED_ITEM_KEY,
    TOBACCO_GROW_SECONDS,
    TOBACCO_ITEM_KEY,
    TOBACCO_SEED_ITEM_KEY,
    TREE_GROW_SECONDS,
    TREE_ITEM_KEY,
    WATER_ITEM_KEY,
)
from dex_catalog import dex_catalog


@dataclass(frozen=True)
class HarvestDropDef:
    item_id: str
    min_amount: int
    max_amount: int
    chance_percent: int = 100


@dataclass(frozen=True)
class CropDef:
    db_id: int
    key: str
    display_name: str
    seed_id: str
    grow_seconds: int
    harvest_tool_item_id: str | None
    harvest_tool_cost: int
    water_item_id: str | None
    water_cost_per_use: int | None
    sprite_key: str
    enabled: bool
    harvest_drops: tuple[HarvestDropDef, ...]

    @property
    def id(self) -> str:
        return self.seed_id

    @property
    def requires_harvest_tool(self) -> bool:
        return bool(self.harvest_tool_item_id)

    @property
    def requires_axe(self) -> bool:
        return self.harvest_tool_item_id == AXE_ITEM_KEY

    @property
    def harvest_id(self) -> str:
        if self.harvest_drops:
            return self.harvest_drops[0].item_id
        return ""

    @property
    def harvest_min(self) -> int:
        if self.harvest_drops:
            return self.harvest_drops[0].min_amount
        return 1

    @property
    def harvest_max(self) -> int:
        if self.harvest_drops:
            return self.harvest_drops[0].max_amount
        return 1


@dataclass(frozen=True)
class CraftRecipeDef:
    id: int
    key: str
    display_name: str
    result_id: str
    ingredient_ids: tuple[str, str]
    success_percent: int = 100
    enabled: bool = True
    remains: int = 0
    result_qty: int = 1  # сколько предметов выдаётся при успехе

    def ingredients(self) -> list[dict[str, int | str]]:
        return [{"id": str(item_id), "qty": 1} for item_id in self.ingredient_ids]


_registry_loaded = False
_crops: tuple[CropDef, ...] = ()
_crops_by_seed: dict[str, CropDef] = {}
_craft_recipes: tuple[CraftRecipeDef, ...] = ()


def _fallback_crops() -> tuple[CropDef, ...]:
    return (
        CropDef(
            db_id=0,
            key="tree",
            display_name="Дерево",
            seed_id=SEED_ITEM_KEY,
            grow_seconds=TREE_GROW_SECONDS,
            harvest_tool_item_id=AXE_ITEM_KEY,
            harvest_tool_cost=1,
            water_item_id=None,
            water_cost_per_use=None,
            sprite_key="tree",
            enabled=True,
            harvest_drops=(
                HarvestDropDef(TREE_ITEM_KEY, 1, 1, 100),
            ),
        ),
        CropDef(
            db_id=0,
            key="tobacco",
            display_name="Табак",
            seed_id=TOBACCO_SEED_ITEM_KEY,
            grow_seconds=TOBACCO_GROW_SECONDS,
            harvest_tool_item_id=None,
            harvest_tool_cost=1,
            water_item_id=None,
            water_cost_per_use=None,
            sprite_key="tobacco",
            enabled=True,
            harvest_drops=(
                HarvestDropDef(TOBACCO_ITEM_KEY, 1, 1, 100),
            ),
        ),
    )


def _fallback_craft() -> tuple[CraftRecipeDef, ...]:
    return (
        CraftRecipeDef(
            id=1,
            key="log_water_paper",
            display_name="Бумага",
            result_id="23",
            ingredient_ids=(TREE_ITEM_KEY, WATER_ITEM_KEY),
            success_percent=90,
            enabled=True,
        ),
    )


def _row_to_crop(row, drops: list[HarvestDropDef]) -> CropDef:
    return CropDef(
        db_id=int(row["id"]),
        key=str(row["key"]),
        display_name=(row["display_name"] or "").strip() or str(row["key"]),
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
        sprite_key=(row["sprite_key"] or "generic").strip() or "generic",
        enabled=bool(row["enabled"]),
        harvest_drops=tuple(drops),
    )


async def _fetch_crops(pool: asyncpg.Pool) -> tuple[CropDef, ...]:
    rows = await pool.fetch(
        """
        SELECT id, key, display_name, seed_item_id, grow_seconds,
               harvest_tool_item_id, harvest_tool_cost,
               water_item_id, water_cost_per_use,
               sprite_key, enabled, sort_order
        FROM farm_crops
        ORDER BY sort_order ASC, id ASC
        """
    )
    if not rows:
        return _fallback_crops()

    crop_ids = [int(row["id"]) for row in rows]
    drop_rows = await pool.fetch(
        """
        SELECT crop_id, item_id, min_amount, max_amount, chance_percent, sort_order
        FROM farm_crop_harvest_drops
        WHERE crop_id = ANY($1::int[])
        ORDER BY sort_order ASC, id ASC
        """,
        crop_ids,
    )
    drops_by_crop: dict[int, list[HarvestDropDef]] = {cid: [] for cid in crop_ids}
    for drop in drop_rows:
        drops_by_crop[int(drop["crop_id"])].append(
            HarvestDropDef(
                item_id=str(drop["item_id"]),
                min_amount=int(drop["min_amount"]),
                max_amount=int(drop["max_amount"]),
                chance_percent=int(drop["chance_percent"]),
            )
        )

    crops: list[CropDef] = []
    for row in rows:
        cid = int(row["id"])
        crop_drops = drops_by_crop.get(cid) or []
        crops.append(_row_to_crop(row, crop_drops))
    return tuple(crops) if crops else _fallback_crops()


async def _fetch_craft_legacy(pool: asyncpg.Pool) -> list[CraftRecipeDef]:
    """Читает рецепты из таблицы craft (item1/item2/item — emoji, craftchance, remains=qty)."""
    try:
        rows = await pool.fetch(
            "SELECT id, item1, item2, item, remains, craftchance FROM craft ORDER BY id ASC"
        )
    except Exception:
        return []

    result = []
    seen_pairs: set[str] = set()
    for row in rows:
        ing_a_id = dex_catalog.get_id_by_emoji(str(row["item1"] or "").strip())
        ing_b_id = dex_catalog.get_id_by_emoji(str(row["item2"] or "").strip())
        res_id   = dex_catalog.get_id_by_emoji(str(row["item"]  or "").strip())
        if not ing_a_id or not ing_b_id or not res_id:
            continue

        pair = "|".join(sorted([ing_a_id, ing_b_id]))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        result_entry = dex_catalog.get(res_id)
        display = result_entry.name if result_entry else res_id

        result.append(CraftRecipeDef(
            id=int(row["id"]) + 100_000,  # сдвиг чтобы не конфликтовать с craft_recipes
            key=f"craft_legacy_{row['id']}",
            display_name=display,
            result_id=res_id,
            ingredient_ids=(ing_a_id, ing_b_id),
            success_percent=max(1, min(100, int(row["craftchance"] or 100))),
            enabled=True,
            remains=0,
            result_qty=max(1, int(row["remains"] or 1)),
        ))
    return result


async def _fetch_craft(pool: asyncpg.Pool) -> tuple[CraftRecipeDef, ...]:
    rows = await pool.fetch(
        """
        SELECT id, key, display_name, result_item_id, ingredient_a_id, ingredient_b_id,
               success_percent, enabled, sort_order,
               COALESCE(remains, 0) AS remains,
               COALESCE(result_qty, 1) AS result_qty
        FROM craft_recipes
        ORDER BY sort_order ASC, id ASC
        """
    )
    if not rows:
        return _fallback_craft()
    return tuple(
        CraftRecipeDef(
            id=int(row["id"]),
            key=str(row["key"]),
            display_name=(row["display_name"] or "").strip() or str(row["key"]),
            result_id=str(row["result_item_id"]),
            ingredient_ids=(str(row["ingredient_a_id"]), str(row["ingredient_b_id"])),
            success_percent=int(row["success_percent"]),
            enabled=bool(row["enabled"]),
            remains=int(row["remains"]),
            result_qty=max(1, int(row["result_qty"])),
        )
        for row in rows
    )


async def migrate_legacy_craft_recipes(pool: asyncpg.Pool) -> int:
    """Одноразовый идемпотентный перенос рецептов из старой таблицы craft в
    управляемую craft_recipes.

    Пары ингредиентов, уже присутствующие в craft_recipes (в любом порядке),
    пропускаются. Возвращает число реально перенесённых рецептов. Старую таблицу
    craft НЕ трогаем — её может ещё читать текстовый бот. После переноса
    load_content_registry больше не подмешивает legacy, поэтому источник правды
    один: craft_recipes (вебапп и админка совпадают с базой).

    Выполняется РОВНО ОДИН РАЗ (отметка в content_migrations): иначе рецепт,
    удалённый админом после переноса, возвращался бы при следующем рестарте, ведь
    в старой таблице craft он ещё есть."""
    try:
        already = await pool.fetchval(
            "SELECT 1 FROM content_migrations WHERE key = 'legacy_craft_to_recipes'"
        )
    except Exception:
        # Таблица-маркер ещё не создана (schema применяется в этой же migrate()) —
        # тогда просто пропускаем перенос, он выполнится на следующем старте.
        return 0
    if already:
        return 0

    legacy = await _fetch_craft_legacy(pool)

    existing_rows = await pool.fetch(
        "SELECT ingredient_a_id, ingredient_b_id FROM craft_recipes"
    )
    existing_pairs: set[str] = set()
    for r in existing_rows:
        existing_pairs.add(
            "|".join(sorted([
                dex_catalog.canonical_key(str(r["ingredient_a_id"])),
                dex_catalog.canonical_key(str(r["ingredient_b_id"])),
            ]))
        )

    next_sort = int(
        await pool.fetchval("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM craft_recipes") or 0
    )
    migrated = 0
    for recipe in legacy:
        pair = "|".join(sorted([
            dex_catalog.canonical_key(recipe.ingredient_ids[0]),
            dex_catalog.canonical_key(recipe.ingredient_ids[1]),
        ]))
        if pair in existing_pairs:
            continue
        inserted = await pool.fetchval(
            """
            INSERT INTO craft_recipes (
                key, display_name, result_item_id, ingredient_a_id, ingredient_b_id,
                success_percent, enabled, sort_order, remains, result_qty
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (key) DO NOTHING
            RETURNING id
            """,
            recipe.key,
            recipe.display_name,
            recipe.result_id,
            recipe.ingredient_ids[0],
            recipe.ingredient_ids[1],
            max(1, min(100, int(recipe.success_percent))),
            bool(recipe.enabled),
            next_sort,
            max(0, int(recipe.remains)),
            max(1, int(recipe.result_qty)),
        )
        if inserted is not None:
            existing_pairs.add(pair)
            next_sort += 1
            migrated += 1

    # Отмечаем миграцию выполненной — даже если переносить было нечего (пустая
    # или отсутствующая таблица craft): второй раз запускать её не нужно.
    await pool.execute(
        "INSERT INTO content_migrations (key) VALUES ('legacy_craft_to_recipes') "
        "ON CONFLICT (key) DO NOTHING"
    )
    return migrated


def _seed_lookup_keys(crop: CropDef) -> set[str]:
    keys = {dex_catalog.resolve_item_id(crop.seed_id), crop.key}
    seed_entry = dex_catalog.get(crop.seed_id)
    if seed_entry:
        for alias in (seed_entry.id, seed_entry.name, seed_entry.name1, seed_entry.emoji):
            if alias:
                keys.add(dex_catalog.resolve_item_id(alias))
    return keys


def _rebuild_indexes() -> None:
    global _crops_by_seed
    _crops_by_seed = {}
    for crop in _crops:
        if not crop.enabled:
            continue
        for key in _seed_lookup_keys(crop):
            _crops_by_seed[key] = crop


async def load_content_registry(pool: asyncpg.Pool) -> None:
    global _registry_loaded, _crops, _craft_recipes
    _crops = await _fetch_crops(pool)

    # Источник правды по крафту — только управляемая таблица craft_recipes.
    # Рецепты из старой таблицы craft переносятся в craft_recipes одноразовой
    # идемпотентной миграцией (migrate_legacy_craft_recipes) при старте, поэтому
    # здесь их больше НЕ подмешиваем: иначе вебапп/админка показывали бы рецепты,
    # которых нет в craft_recipes, и их нельзя было бы отредактировать/удалить в
    # панели (рассинхрон «в вебаппе/админке есть, а в базе нет»).
    _craft_recipes = tuple(await _fetch_craft(pool))
    _rebuild_indexes()
    _registry_loaded = True


async def reload_content_registry(pool: asyncpg.Pool) -> None:
    await load_content_registry(pool)


async def ensure_content_registry_loaded(pool: asyncpg.Pool | None) -> None:
    """Перезагрузить культуры из PostgreSQL, если кэш пуст (например после light-connect)."""
    global _registry_loaded
    if _registry_loaded and _crops:
        return
    if pool is None:
        return
    await load_content_registry(pool)


async def seed_default_content(pool: asyncpg.Pool) -> None:
    """Первый запуск: перенос tree/tobacco и базового крафта в БД."""
    count = int(await pool.fetchval("SELECT COUNT(*)::int FROM farm_crops") or 0)
    if count == 0:
        from farm_settings import get_tobacco_grow_seconds, get_tree_grow_seconds

        defaults = (
            ("tree", "Дерево", SEED_ITEM_KEY, get_tree_grow_seconds(), AXE_ITEM_KEY, "tree", TREE_ITEM_KEY),
            (
                "tobacco",
                "Табак",
                TOBACCO_SEED_ITEM_KEY,
                get_tobacco_grow_seconds(),
                AXE_ITEM_KEY,
                "tobacco",
                TOBACCO_ITEM_KEY,
            ),
        )
        for sort_order, (key, name, seed_id, grow, tool_id, sprite, harvest_id) in enumerate(defaults):
            crop_id = await pool.fetchval(
                """
                INSERT INTO farm_crops (
                    key, display_name, seed_item_id, grow_seconds,
                    harvest_tool_item_id, harvest_tool_cost, sprite_key, sort_order
                )
                VALUES ($1, $2, $3, $4, $5, 1, $6, $7)
                RETURNING id
                """,
                key,
                name,
                seed_id,
                grow,
                tool_id,
                sprite,
                sort_order,
            )
            await pool.execute(
                """
                INSERT INTO farm_crop_harvest_drops (crop_id, item_id, min_amount, max_amount, sort_order)
                VALUES ($1, $2, 1, 1, 0)
                """,
                crop_id,
                harvest_id,
            )

    craft_count = int(await pool.fetchval("SELECT COUNT(*)::int FROM craft_recipes") or 0)
    if craft_count == 0:
        await pool.execute(
            """
            INSERT INTO craft_recipes (
                key, display_name, result_item_id, ingredient_a_id, ingredient_b_id, success_percent, sort_order
            )
            VALUES ($1, $2, $3, $4, $5, 90, 0)
            ON CONFLICT (key) DO NOTHING
            """,
            "log_water_paper",
            "Бумага",
            "23",
            TREE_ITEM_KEY,
            WATER_ITEM_KEY,
        )

    await _ensure_autowater_dex(pool)


async def _ensure_autowater_dex(pool: asyncpg.Pool) -> None:
    """Предмет автополива — только крафт, не в магазине (remains=0)."""
    from config import AUTOWATER_ITEM_KEY

    exists = await pool.fetchval(
        "SELECT 1 FROM dex WHERE id = $1",
        int(AUTOWATER_ITEM_KEY),
    )
    if exists:
        return
    await pool.execute(
        """
        INSERT INTO dex (id, name, name1, emoji, price, dis, remains, sorting, bio)
        VALUES ($1, $2, $3, $4, 0, 0, 0, $5, $6)
        """,
        int(AUTOWATER_ITEM_KEY),
        "Автополив",
        "autowater",
        "🚰",
        "farm_gear",
        "Один раз за цикл роста защищает грядку от засухи до урожая. Получается только через крафт.",
    )


def enabled_crops() -> tuple[CropDef, ...]:
    return tuple(crop for crop in _crops if crop.enabled)


def all_crops() -> tuple[CropDef, ...]:
    return _crops


def crops_by_seed() -> dict[str, CropDef]:
    return dict(_crops_by_seed)


def normalize_seed_id(seed_id: str) -> str:
    return dex_catalog.resolve_item_id(str(seed_id).strip())


def get_crop_by_seed(seed_id: str) -> CropDef | None:
    return _crops_by_seed.get(normalize_seed_id(seed_id))


def get_crop_by_key(key: str) -> CropDef | None:
    lookup = str(key or "").strip().lower()
    if not lookup:
        return None
    for crop in enabled_crops():
        if crop.key == lookup:
            return crop
    return None


def get_crop_for_plot(crop_id: str | None) -> CropDef | None:
    if not crop_id:
        for crop in enabled_crops():
            if crop.key == "tree":
                return crop
        return enabled_crops()[0] if enabled_crops() else None
    crop = get_crop_by_seed(crop_id)
    if crop:
        return crop
    return get_crop_by_key(crop_id)


def grow_seconds_for_crop(crop_id: str | None) -> int:
    crop = get_crop_for_plot(crop_id)
    if crop:
        # Для дерева и табака — используем динамические настройки из system_settings
        if crop.key == "tree":
            from farm_settings import get_tree_grow_seconds
            return get_tree_grow_seconds()
        if crop.key == "tobacco":
            from farm_settings import get_tobacco_grow_seconds
            return get_tobacco_grow_seconds()
        return crop.grow_seconds
    return TREE_GROW_SECONDS


def roll_harvest_drops(crop: CropDef) -> list[tuple[str, int]]:
    rolled: list[tuple[str, int]] = []
    for drop in crop.harvest_drops:
        if random.randint(1, 100) > drop.chance_percent:
            continue
        amount = random.randint(drop.min_amount, drop.max_amount)
        if amount > 0:
            rolled.append((drop.item_id, amount))
    return rolled


def water_config_for_crop(crop: CropDef | None) -> tuple[str, int]:
    from farm_settings import get_water_cost_per_use

    if crop and crop.water_item_id:
        item_id = crop.water_item_id
        cost = crop.water_cost_per_use if crop.water_cost_per_use is not None else get_water_cost_per_use()
        return item_id, cost
    return WATER_ITEM_KEY, get_water_cost_per_use()


def is_autowater_item(item_id: str) -> bool:
    return dex_catalog.canonical_key(str(item_id)) == dex_catalog.canonical_key(AUTOWATER_ITEM_KEY)


def resolve_water_item_for_action(
    raw_items: dict,
    crop: CropDef | None,
    requested_item_id: str | None,
) -> tuple[str, int]:
    """Выбор предмета для ручного полива."""
    from user_items import count_item

    default_id, default_cost = water_config_for_crop(crop)
    item_id = default_id
    cost = default_cost

    if requested_item_id:
        requested = dex_catalog.canonical_key(requested_item_id)
        if requested != dex_catalog.canonical_key(default_id):
            raise ValueError("Этим предметом нельзя полить грядку")
        item_id = requested

    if count_item(raw_items, item_id) < cost:
        entry = dex_catalog.get(item_id)
        label = entry.name if entry else "воды"
        raise ValueError(f"У Вас нет {label}. Купите в магазине")
    return item_id, cost


def all_game_item_ids() -> frozenset[str]:
    ids: set[str] = {
        SEED_ITEM_KEY,
        TREE_ITEM_KEY,
        TOBACCO_SEED_ITEM_KEY,
        TOBACCO_ITEM_KEY,
        WATER_ITEM_KEY,
        AUTOWATER_ITEM_KEY,
        AXE_ITEM_KEY,
    }
    for crop in _crops:
        ids.add(dex_catalog.canonical_key(crop.seed_id))
        if crop.harvest_tool_item_id:
            ids.add(dex_catalog.canonical_key(crop.harvest_tool_item_id))
        if crop.water_item_id:
            ids.add(dex_catalog.canonical_key(crop.water_item_id))
        for drop in crop.harvest_drops:
            ids.add(dex_catalog.canonical_key(drop.item_id))
    for recipe in _craft_recipes:
        ids.add(dex_catalog.canonical_key(recipe.result_id))
        for ing in recipe.ingredient_ids:
            ids.add(dex_catalog.canonical_key(ing))
    return frozenset(ids)


def seed_item_ids() -> frozenset[str]:
    return frozenset(dex_catalog.canonical_key(crop.seed_id) for crop in enabled_crops())


def enabled_craft_recipes() -> list[CraftRecipeDef]:
    result = []
    for recipe in _craft_recipes:
        if not recipe.enabled:
            continue
        result.append(recipe)
    return result


def all_craft_recipes() -> tuple[CraftRecipeDef, ...]:
    return _craft_recipes


def get_craft_recipe_by_id(recipe_id: int) -> CraftRecipeDef | None:
    target = int(recipe_id)
    for recipe in _craft_recipes:
        if recipe.id == target:
            return recipe
    return None


def get_craft_recipe(recipe_id: int) -> CraftRecipeDef | None:
    recipe = get_craft_recipe_by_id(recipe_id)
    if recipe and recipe.enabled:
        return recipe
    return None


def ingredient_pair_key(item_ids: tuple[str, ...] | list[str]) -> str:
    canonical = sorted(dex_catalog.canonical_key(str(item_id)) for item_id in item_ids)
    return "|".join(canonical)


def find_recipe_by_ingredient_pair(slot_a: str, slot_b: str) -> CraftRecipeDef | None:
    pair_key = ingredient_pair_key((slot_a, slot_b))
    for recipe in enabled_craft_recipes():
        if ingredient_pair_key(recipe.ingredient_ids) == pair_key:
            return recipe
    return None


def validate_craft_recipes() -> list[str]:
    warnings: list[str] = []
    if not dex_catalog.loaded:
        return warnings

    seen_pairs: dict[str, str] = {}
    seen_keys: set[str] = set()
    for recipe in _craft_recipes:
        if recipe.key in seen_keys:
            warnings.append(f"Craft: повторяющийся key {recipe.key}")
        seen_keys.add(recipe.key)

        pair_key = ingredient_pair_key(recipe.ingredient_ids)
        if pair_key in seen_pairs:
            warnings.append(
                f"Craft: одна пара ингредиентов у {recipe.key} и {seen_pairs[pair_key]}"
            )
        seen_pairs[pair_key] = recipe.key

        for item_id in (*recipe.ingredient_ids, recipe.result_id):
            if not dex_catalog.get(str(item_id)):
                warnings.append(f"Craft [{recipe.key}]: id {item_id} не найден в dex")
    return warnings


def _item_brief(item_id: str) -> dict[str, str]:
    entry = dex_catalog.get(item_id)
    if entry:
        return {"id": entry.id, "name": entry.name, "emoji": entry.emoji}
    return {"id": str(item_id), "name": str(item_id), "emoji": "📦"}


def _display_item_name(item_id: str, *, fallback: str = "Предмет") -> str:
    from config import AXE_ITEM_KEY, AUTOWATER_ITEM_KEY, WATER_ITEM_KEY

    entry = dex_catalog.get(item_id)
    if entry and entry.name and not str(entry.name).strip().isdigit():
        return entry.name
    canon = dex_catalog.canonical_key(str(item_id))
    if canon == AXE_ITEM_KEY:
        return "Топор"
    if canon == WATER_ITEM_KEY:
        return "Вода"
    if canon == AUTOWATER_ITEM_KEY:
        return "Автополив"
    return fallback


def _tool_client(tool_id: str | None, cost: int, raw_items: dict | None) -> dict | None:
    if not tool_id:
        return None
    from config import AXE_ITEM_KEY
    from user_items import count_item_in_storage

    canon = dex_catalog.canonical_key(tool_id)
    count = count_item_in_storage(raw_items, tool_id) if raw_items is not None else 0
    entry = dex_catalog.get(tool_id)
    is_axe = canon == dex_catalog.canonical_key(AXE_ITEM_KEY)
    return {
        "itemId": canon,
        "name": _display_item_name(tool_id, fallback="Топор" if is_axe else "Инструмент"),
        "emoji": entry.emoji if entry else ("🪓" if is_axe else "🛠"),
        "required": True,
        "costPerHarvest": max(1, int(cost)),
        "count": count,
        "owned": count >= max(1, int(cost)),
    }


def crops_for_client(raw_items: dict | None = None) -> list[dict]:
    rows: list[dict] = []
    for crop in enabled_crops():
        seed = dex_catalog.get(crop.seed_id)
        harvest_drops = []
        for drop in crop.harvest_drops:
            brief = _item_brief(drop.item_id)
            harvest_drops.append(
                {
                    "itemId": brief["id"],
                    "name": brief["name"],
                    "emoji": brief["emoji"],
                    "minAmount": drop.min_amount,
                    "maxAmount": drop.max_amount,
                    "chancePercent": drop.chance_percent,
                }
            )
        first = harvest_drops[0] if harvest_drops else None
        harvest_tool = _tool_client(crop.harvest_tool_item_id, crop.harvest_tool_cost, raw_items)
        water_item_id, water_cost = water_config_for_crop(crop)
        water_entry = dex_catalog.get(water_item_id)
        rows.append(
            {
                "id": crop.db_id,
                "key": crop.key,
                "displayName": crop.display_name,
                "seedId": normalize_seed_id(crop.seed_id),
                "seedName": (
                    seed.name
                    if seed and seed.name and not str(seed.name).strip().isdigit()
                    else crop.display_name
                ),
                "seedEmoji": seed.emoji if seed else "🌱",
                "harvestId": first["itemId"] if first else "",
                "harvestName": first["name"] if first else "",
                "harvestEmoji": first["emoji"] if first else "📦",
                "harvestDrops": harvest_drops,
                "requiresAxe": crop.requires_axe,
                "requiresHarvestTool": crop.requires_harvest_tool,
                "harvestTool": harvest_tool,
                "waterItemId": water_item_id,
                "waterCostPerUse": water_cost,
                "waterName": water_entry.name if water_entry else water_item_id,
                "waterEmoji": water_entry.emoji if water_entry else "💧",
                "growSeconds": crop.grow_seconds,
                "spriteKey": crop.sprite_key,
                "enabled": crop.enabled,
            }
        )
    from seed_economy import HARVEST_SEED_DROP_PERCENT

    drop_percent = HARVEST_SEED_DROP_PERCENT
    for row in rows:
        row["seedDropPercent"] = drop_percent
    return rows


def balance_bar_for_client(
    *,
    kut: int,
    seed_counts: dict[str, int],
    raw_items: dict,
    farm_crops: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """Чипы верхней панели фермы: КУТ, семена культур, вода, инструменты."""
    from user_items import count_item

    if farm_crops is None:
        farm_crops = crops_for_client(raw_items)

    chips: list[dict[str, Any]] = [
        {
            "kind": "kut",
            "id": "kut",
            "emoji": "💰",
            "label": "кут",
            "value": int(kut),
        }
    ]

    for crop in farm_crops:
        seed_id = str(crop.get("seedId") or "")
        from user_items import count_seed_for_crop

        crop_def = get_crop_by_key(str(crop.get("key") or ""))
        seed_value = (
            count_seed_for_crop(raw_items, crop_def)
            if crop_def is not None
            else int(seed_counts.get(seed_id, 0))
        )
        chips.append(
            {
                "kind": "crop",
                "id": str(crop.get("key") or seed_id),
                "emoji": crop.get("seedEmoji") or "🌱",
                "label": (
                    crop.get("displayName")
                    or crop.get("seedName")
                    or crop.get("key")
                    or "Культура"
                ),
                "value": seed_value,
                "seedId": seed_id,
            }
        )

    seen_water: set[str] = set()
    for crop in farm_crops:
        water_id = str(crop.get("waterItemId") or "")
        if not water_id or water_id in seen_water:
            continue
        seen_water.add(water_id)
        chips.append(
            {
                "kind": "water",
                "id": water_id,
                "emoji": crop.get("waterEmoji") or "💧",
                "label": crop.get("waterName") or "Вода",
                "value": count_item(raw_items, water_id),
            }
        )
    if not seen_water:
        from config import WATER_ITEM_KEY

        entry = dex_catalog.get(WATER_ITEM_KEY)
        chips.append(
            {
                "kind": "water",
                "id": WATER_ITEM_KEY,
                "emoji": entry.emoji if entry else "💧",
                "label": entry.name if entry else "Вода",
                "value": count_item(raw_items, WATER_ITEM_KEY),
            }
        )

    from config import AUTOWATER_ITEM_KEY

    autowater_entry = dex_catalog.get(AUTOWATER_ITEM_KEY)
    autowater_count = count_item(raw_items, AUTOWATER_ITEM_KEY)
    if autowater_count > 0 or autowater_entry:
        chips.append(
            {
                "kind": "autowater",
                "id": AUTOWATER_ITEM_KEY,
                "emoji": autowater_entry.emoji if autowater_entry else "🚰",
                "label": autowater_entry.name if autowater_entry else "Автополив",
                "value": autowater_count,
            }
        )

    seen_tools: set[str] = set()
    for crop in farm_crops:
        tool = crop.get("harvestTool") or {}
        tool_id = str(tool.get("itemId") or "")
        if not tool_id or tool_id in seen_tools:
            continue
        seen_tools.add(tool_id)
        chips.append(
            {
                "kind": "tool",
                "id": tool_id,
                "emoji": tool.get("emoji") or "🛠",
                "label": tool.get("name") or "Инструмент",
                "value": int(tool.get("count") or 0),
            }
        )

    return chips


def crop_to_admin_dict(crop: CropDef) -> dict[str, Any]:
    seed = dex_catalog.get(crop.seed_id)
    harvest_tool = dex_catalog.get(crop.harvest_tool_item_id) if crop.harvest_tool_item_id else None
    water = dex_catalog.get(crop.water_item_id) if crop.water_item_id else None
    return {
        "id": crop.db_id,
        "key": crop.key,
        "displayName": crop.display_name,
        "seedItemId": crop.seed_id,
        "seedName": seed.name if seed else crop.seed_id,
        "seedEmoji": seed.emoji if seed else "🌱",
        "growSeconds": crop.grow_seconds,
        "harvestToolItemId": crop.harvest_tool_item_id,
        "harvestToolName": harvest_tool.name if harvest_tool else None,
        "harvestToolCost": crop.harvest_tool_cost,
        "waterItemId": crop.water_item_id,
        "waterCostPerUse": crop.water_cost_per_use,
        "waterName": water.name if water else None,
        "spriteKey": crop.sprite_key,
        "enabled": crop.enabled,
        "harvestDrops": [
            {
                "itemId": drop.item_id,
                "minAmount": drop.min_amount,
                "maxAmount": drop.max_amount,
                "chancePercent": drop.chance_percent,
                **_item_brief(drop.item_id),
            }
            for drop in crop.harvest_drops
        ],
    }


def recipe_to_admin_dict(recipe: CraftRecipeDef) -> dict[str, Any]:
    result = _item_brief(recipe.result_id)
    ing_a = _item_brief(recipe.ingredient_ids[0])
    ing_b = _item_brief(recipe.ingredient_ids[1])
    return {
        "id": recipe.id,
        "key": recipe.key,
        "displayName": recipe.display_name,
        "resultItemId": recipe.result_id,
        "resultName": result["name"],
        "resultEmoji": result["emoji"],
        "ingredientAId": recipe.ingredient_ids[0],
        "ingredientAName": ing_a["name"],
        "ingredientAEmoji": ing_a["emoji"],
        "ingredientBId": recipe.ingredient_ids[1],
        "ingredientBName": ing_b["name"],
        "ingredientBEmoji": ing_b["emoji"],
        "successPercent": recipe.success_percent,
        "enabled": recipe.enabled,
        "remains": recipe.remains,
        "resultQty": recipe.result_qty,
    }
