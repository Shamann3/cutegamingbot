"""Топор для сбора урожая: 1 топор = 1 сбор дерева или табака."""

from __future__ import annotations

import json
from typing import Any

from config import AXE_ITEM_KEY, AXE_MAX_DURABILITY, AXE_WEAR_PER_TREE_HARVEST
from dex_catalog import dex_catalog, normalize_items
from user_items import count_item, take_item


def parse_tool_durability(raw: Any) -> dict[str, int]:
    if raw in (None, "", 0):
        return {}
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    else:
        return {}

    result: dict[str, int] = {}
    if not isinstance(data, dict):
        return result
    for key, value in data.items():
        try:
            percent = int(value)
        except (TypeError, ValueError):
            continue
        result[str(key)] = max(0, min(AXE_MAX_DURABILITY, percent))
    return result


def tool_durability_to_db(values: dict[str, int]) -> str:
    return json.dumps(values, ensure_ascii=True, separators=(",", ":"))


def axe_durability_percent(tool_durability: dict[str, int], raw_items: dict) -> int | None:
    if count_item(raw_items, AXE_ITEM_KEY) < 1:
        return None
    stored = tool_durability.get(AXE_ITEM_KEY)
    if stored is None:
        return AXE_MAX_DURABILITY
    return max(0, min(AXE_MAX_DURABILITY, int(stored)))


def ensure_axe_durability(tool_durability: dict[str, int], raw_items: dict) -> dict[str, int]:
    values = dict(tool_durability)
    if count_item(raw_items, AXE_ITEM_KEY) >= 1 and AXE_ITEM_KEY not in values:
        values[AXE_ITEM_KEY] = AXE_MAX_DURABILITY
    return values


def register_axe_purchase(tool_durability: dict[str, int]) -> dict[str, int]:
    values = dict(tool_durability)
    values[AXE_ITEM_KEY] = AXE_MAX_DURABILITY
    return values


def apply_harvest_tool(
    raw_items: dict,
    tool_durability: dict[str, int],
    *,
    tool_item_id: str,
    cost: int = 1,
) -> tuple[dict, dict[str, int], int | None]:
    """Списывает инструмент сбора за урожай."""
    from dex_catalog import dex_catalog
    from user_items import count_item_in_storage, take_item_from_storage

    tool_id = dex_catalog.canonical_key(str(tool_item_id))
    cost = max(1, int(cost))
    if count_item_in_storage(raw_items, tool_id) < cost:
        entry = dex_catalog.get(tool_id)
        label = entry.name if entry else "инструмента"
        raise ValueError(f"Нужен {label} для сбора урожая")

    stored = take_item_from_storage(raw_items, tool_id, cost)
    game_items = normalize_items(stored)
    values = dict(tool_durability)
    values.pop(tool_id, None)
    remaining = count_item_in_storage(stored, tool_id)
    return game_items, values, remaining if remaining > 0 else None


def apply_axe_wear(
    raw_items: dict,
    tool_durability: dict[str, int],
    *,
    wear: int = AXE_WEAR_PER_TREE_HARVEST,
) -> tuple[dict, dict[str, int], int | None]:
    """Legacy: 1 топор за сбор."""
    del wear
    return apply_harvest_tool(
        raw_items,
        tool_durability,
        tool_item_id=AXE_ITEM_KEY,
        cost=1,
    )


def harvest_tool_state_for_client(raw_items: dict, crop) -> dict | None:
    from content_registry import CropDef

    if not isinstance(crop, CropDef) or not crop.harvest_tool_item_id:
        return None
    tool_id = crop.harvest_tool_item_id
    count = count_item(raw_items, tool_id)
    cost = max(1, int(crop.harvest_tool_cost))
    entry = dex_catalog.get(tool_id)
    return {
        "itemId": dex_catalog.canonical_key(tool_id),
        "name": entry.name if entry else "Инструмент",
        "emoji": entry.emoji if entry else "🛠",
        "owned": count >= cost,
        "count": count,
        "costPerHarvest": cost,
    }


def axe_state_for_client(raw_items: dict, tool_durability: dict[str, int]) -> dict:
    del tool_durability  # legacy column, больше не влияет на топор
    count = count_item(raw_items, AXE_ITEM_KEY)
    owned = count >= 1
    entry = dex_catalog.get(AXE_ITEM_KEY)
    return {
        "itemId": AXE_ITEM_KEY,
        "name": entry.name if entry else "Топор",
        "emoji": entry.emoji if entry else "🪓",
        "owned": owned,
        "count": count,
        "costPerHarvest": 1,
    }
