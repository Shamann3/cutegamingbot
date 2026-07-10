"""Крафты: рецепты из craft_definitions + предметы из dex."""

from __future__ import annotations

from typing import Any

from craft_definitions import CraftRecipeDef, enabled_craft_recipes, find_recipe_by_ingredient_pair
from dex_catalog import dex_catalog
from user_items import can_craft, count_item


def normalize_success_percent(value: Any) -> int:
    try:
        percent = int(value)
    except (TypeError, ValueError):
        percent = 100
    return max(1, min(100, percent))


def _ingredient_client(item_id: str, qty: int, raw_items: dict) -> dict:
    canon = dex_catalog.canonical_key(item_id)
    entry = dex_catalog.get(item_id)
    owned = count_item(raw_items, canon)
    return {
        "id": canon,
        "name": entry.name if entry else str(item_id),
        "emoji": entry.emoji if entry else "📦",
        "qty": qty,
        "owned": owned,
        "enough": owned >= qty,
    }


def recipe_to_client(recipe: CraftRecipeDef, raw_items: dict) -> dict | None:
    result_id = str(recipe.result_id).strip()
    if not result_id:
        return None

    ingredients = recipe.ingredients()
    if len(ingredients) < 2:
        return None

    result_entry = dex_catalog.get(result_id)
    ingredient_rows = [
        _ingredient_client(str(ing["id"]), int(ing["qty"]), raw_items)
        for ing in ingredients
    ]
    success_percent = normalize_success_percent(recipe.success_percent)

    return {
        "id": int(recipe.id),
        "key": recipe.key,
        "result": {
            "id": result_entry.id if result_entry else result_id,
            "name": result_entry.name if result_entry else result_id,
            "emoji": result_entry.emoji if result_entry else "📦",
            "qty": recipe.result_qty,
        },
        "ingredients": ingredient_rows,
        "successPercent": success_percent,
        "failPercent": max(0, 100 - success_percent),
        "remains": recipe.remains,
        "canCraft": can_craft(raw_items, ingredients),
    }


def recipes_for_client(raw_items: dict) -> list[dict]:
    rows: list[dict] = []
    for recipe in sorted(enabled_craft_recipes(), key=lambda item: (item.id, item.key)):
        client = recipe_to_client(recipe, raw_items)
        if client:
            rows.append(client)
    return rows


def recipe_for_execute(slot_a: str, slot_b: str) -> CraftRecipeDef | None:
    return find_recipe_by_ingredient_pair(slot_a, slot_b)
