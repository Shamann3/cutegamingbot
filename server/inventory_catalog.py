"""Рюкзак игрока: список предметов с описанием (как в основном боте)."""

from __future__ import annotations

from config import (
    AUTOWATER_ITEM_KEY,
    AXE_ITEM_KEY,
    SEED_ITEM_KEY,
    TOBACCO_ITEM_KEY,
    TOBACCO_SEED_ITEM_KEY,
    TREE_ITEM_KEY,
    WATER_ITEM_KEY,
)
from dex_catalog import FARM_ITEM_ORDER, dex_catalog, normalize_items
from shop_catalog import category_from_sorting

INVENTORY_GROUP_FARM = "farm"
INVENTORY_GROUP_GEAR = "gear"
INVENTORY_GROUP_OTHER = "other"

_FARM_IDS = frozenset({
    SEED_ITEM_KEY,
    TREE_ITEM_KEY,
    TOBACCO_SEED_ITEM_KEY,
    TOBACCO_ITEM_KEY,
    WATER_ITEM_KEY,
    AUTOWATER_ITEM_KEY,
})
_GEAR_IDS = frozenset({AXE_ITEM_KEY})


def _inventory_group(item_id: str) -> str:
    if item_id in _FARM_IDS:
        return INVENTORY_GROUP_FARM
    if item_id in _GEAR_IDS:
        return INVENTORY_GROUP_GEAR
    return INVENTORY_GROUP_OTHER


def _entry_description(entry) -> str:
    if entry.bio:
        return entry.bio
    parts: list[str] = []
    if entry.use:
        parts.append(f"Использование : {entry.use}")
    if entry.bonus:
        parts.append(f"Бонус : +{entry.bonus}")
    if entry.craft:
        parts.append(f"Крафт : {entry.craft}")
    return " · ".join(parts)


def _inventory_row(
    item_id: str,
    count: int,
    *,
    meta: str = "",
    sort_rank: int,
    economy: dict | None = None,
) -> dict:
    entry = dex_catalog.get(item_id)
    sorting = entry.sorting if entry else None
    cat = category_from_sorting(sorting, 0)
    group = _inventory_group(item_id)
    if group == INVENTORY_GROUP_FARM:
        category_label = "Ферма"
    elif group == INVENTORY_GROUP_GEAR:
        category_label = "Инструмент"
    else:
        category_label = cat["label"]

    name = entry.name if entry else str(item_id)
    emoji = entry.emoji if entry else "📦"
    description = _entry_description(entry) if entry else ""

    if item_id == AXE_ITEM_KEY and meta:
        description = meta if not description else f"{description} · {meta}"

    row = {
        "id": item_id,
        "name": name,
        "emoji": emoji,
        "count": int(count),
        "group": group,
        "groupLabel": {
            INVENTORY_GROUP_FARM: "Ферма",
            INVENTORY_GROUP_GEAR: "Инструменты",
            INVENTORY_GROUP_OTHER: "Прочее",
        }[group],
        "categoryLabel": category_label,
        "description": description,
        "meta": meta,
        "sortRank": sort_rank,
    }
    if economy:
        row["economy"] = economy
    return row


def build_inventory_items(
    raw_items: dict,
    *,
    axe_meta: str = "",
    economy_by_id: dict[str, dict] | None = None,
) -> list[dict]:
    normalized = normalize_items(raw_items)
    rows: list[dict] = []
    rank = 0

    for dex_id in FARM_ITEM_ORDER:
        count = normalized.get(dex_id, 0)
        if count < 1:
            continue
        meta = ""
        if dex_id == AXE_ITEM_KEY and axe_meta:
            meta = axe_meta
        rows.append(_inventory_row(
            dex_id,
            count,
            meta=meta,
            sort_rank=rank,
            economy=(economy_by_id or {}).get(dex_id),
        ))
        rank += 1

    listed = set(FARM_ITEM_ORDER)
    other_ids = sorted(
        (item_id for item_id, count in normalized.items() if count > 0 and item_id not in listed),
        key=lambda item_id: (dex_catalog.get(item_id).name if dex_catalog.get(item_id) else item_id).lower(),
    )
    for item_id in other_ids:
        rows.append(_inventory_row(
            item_id,
            normalized[item_id],
            sort_rank=rank,
            economy=(economy_by_id or {}).get(item_id),
        ))
        rank += 1

    return rows


def inventory_summary(items: list[dict]) -> dict:
    total_kinds = len(items)
    total_count = sum(int(row.get("count") or 0) for row in items)
    groups = {
        INVENTORY_GROUP_FARM: 0,
        INVENTORY_GROUP_GEAR: 0,
        INVENTORY_GROUP_OTHER: 0,
    }
    for row in items:
        group = row.get("group")
        if group in groups:
            groups[group] += 1
    return {
        "totalKinds": total_kinds,
        "totalCount": total_count,
        "groups": groups,
    }
