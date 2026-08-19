"""Экономика семян: дроп с урожая, стартовый набор, ежедневная выдача."""

from __future__ import annotations

import os
import random
from datetime import date, datetime
from zoneinfo import ZoneInfo

from config import (
    ANALYTICS_TZ,
    AXE_ITEM_KEY,
    SEED_ITEM_KEY,
    TOBACCO_SEED_ITEM_KEY,
    WATER_ITEM_KEY,
)
from content_registry import enabled_crops
from dex_catalog import dex_catalog, normalize_items
from user_items import add_item

HARVEST_SEED_DROP_PERCENT = max(
    0, min(100, int(os.getenv("HARVEST_SEED_DROP_PERCENT", "25")))
)
STARTER_TREE_SEEDS = max(0, int(os.getenv("STARTER_TREE_SEEDS", "2")))
STARTER_TOBACCO_SEEDS = max(0, int(os.getenv("STARTER_TOBACCO_SEEDS", "2")))
STARTER_WATER = max(0, int(os.getenv("STARTER_WATER", "2")))
STARTER_AXE = max(0, int(os.getenv("STARTER_AXE", "2")))
DAILY_SEED_AMOUNT = max(1, min(5, int(os.getenv("DAILY_SEED_AMOUNT", "1"))))

# Runtime cache (overrides env values when set via admin panel)
_seed_cache: dict | None = None


async def refresh_seed_settings_cache() -> None:
    global _seed_cache
    from db import db
    row = await db.pool.fetchrow(
        """
        SELECT harvest_seed_drop_percent, daily_seed_amount,
               starter_tree_seeds, starter_tobacco_seeds, starter_water, starter_axe
        FROM system_settings WHERE id = 1
        """
    )
    if row is None:
        _seed_cache = {}
        return
    _seed_cache = {
        "harvest_seed_drop_percent": row["harvest_seed_drop_percent"],
        "daily_seed_amount": row["daily_seed_amount"],
        "starter_tree_seeds": row["starter_tree_seeds"],
        "starter_tobacco_seeds": row["starter_tobacco_seeds"],
        "starter_water": row["starter_water"],
        "starter_axe": row["starter_axe"],
    }


def _sc(key: str, default: int) -> int:
    if _seed_cache and _seed_cache.get(key) is not None:
        return int(_seed_cache[key])
    return default


def get_harvest_seed_drop_percent() -> int:
    return _sc("harvest_seed_drop_percent", HARVEST_SEED_DROP_PERCENT)


def get_daily_seed_amount() -> int:
    return _sc("daily_seed_amount", DAILY_SEED_AMOUNT)


def get_starter_tree_seeds() -> int:
    return _sc("starter_tree_seeds", STARTER_TREE_SEEDS)


def get_starter_tobacco_seeds() -> int:
    return _sc("starter_tobacco_seeds", STARTER_TOBACCO_SEEDS)


def get_starter_water() -> int:
    return _sc("starter_water", STARTER_WATER)


def get_starter_axe() -> int:
    return _sc("starter_axe", STARTER_AXE)


def _analytics_tz() -> ZoneInfo:
    try:
        return ZoneInfo(ANALYTICS_TZ)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def local_today() -> date:
    return datetime.now(_analytics_tz()).date()


def roll_harvest_seed_drop(crop) -> bool:
    """Шанс вернуть 1 семя той же культуры при сборе урожая."""
    pct = get_harvest_seed_drop_percent()
    if pct <= 0:
        return False
    if not crop or not crop.seed_id:
        return False
    return random.randint(1, 100) <= pct


def apply_starter_pack(game_items: dict) -> dict:
    items = normalize_items(game_items)
    if get_starter_tree_seeds() > 0:
        items = add_item(items, SEED_ITEM_KEY, get_starter_tree_seeds())
    if get_starter_tobacco_seeds() > 0:
        items = add_item(items, TOBACCO_SEED_ITEM_KEY, get_starter_tobacco_seeds())
    if get_starter_water() > 0:
        items = add_item(items, WATER_ITEM_KEY, get_starter_water())
    if get_starter_axe() > 0:
        items = add_item(items, AXE_ITEM_KEY, get_starter_axe())
    return items


def seed_drop_client_meta(crop, *, dropped: bool) -> dict | None:
    if not dropped or not crop:
        return None
    seed_id = dex_catalog.canonical_key(crop.seed_id)
    entry = dex_catalog.get(seed_id)
    return {
        "seedDropped": True,
        "seedItemId": seed_id,
        "seedName": entry.name if entry else "Семя",
        "seedEmoji": entry.emoji if entry else "🌱",
        "dropPercent": get_harvest_seed_drop_percent(),
    }


def default_daily_seed_id() -> str:
    for crop in enabled_crops():
        return dex_catalog.canonical_key(crop.seed_id)
    return dex_catalog.canonical_key(SEED_ITEM_KEY)


def normalize_daily_seed_choice(seed_item_id: str | None) -> str:
    if not seed_item_id:
        return default_daily_seed_id()
    canon = dex_catalog.canonical_key(str(seed_item_id).strip())
    allowed = {dex_catalog.canonical_key(crop.seed_id) for crop in enabled_crops()}
    if canon not in allowed:
        raise ValueError("Выберите семена деревьев или табака")
    return canon



def seed_economy_for_client(*, daily_seed_claimed_on: date | None) -> dict:
    today = local_today()
    claimed_today = daily_seed_claimed_on == today if daily_seed_claimed_on else False
    return {
        "harvestDropPercent": get_harvest_seed_drop_percent(),
        "dailySeedAmount": get_daily_seed_amount(),
        "dailySeedClaimedToday": claimed_today,
        "dailySeedAvailable": not claimed_today,
        "starterTreeSeeds": get_starter_tree_seeds(),
        "starterTobaccoSeeds": get_starter_tobacco_seeds(),
    }


def daily_seed_reward_label(seed_item_id: str) -> str:
    entry = dex_catalog.get(seed_item_id)
    if not entry:
        return "семя"
    return f"{entry.emoji} {entry.name}".strip()
