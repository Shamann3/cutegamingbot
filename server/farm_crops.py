"""Культуры фермы — re-export из content_registry (БД + fallback)."""

from __future__ import annotations

from content_registry import (
    CropDef,
    HarvestDropDef,
    balance_bar_for_client,
    crops_for_client,
    balance_bar_for_client,
    get_crop_by_seed,
    get_crop_for_plot,
    grow_seconds_for_crop,
    normalize_seed_id,
    roll_harvest_drops,
    water_config_for_crop,
    resolve_water_item_for_action,
)

# Legacy aliases — вызывайте all_crops() / crops_by_seed() в runtime после load_content_registry.
from content_registry import all_crops, crops_by_seed

__all__ = [
    "CropDef",
    "HarvestDropDef",
    "balance_bar_for_client",
    "crops_for_client",
    "get_crop_by_seed",
    "get_crop_for_plot",
    "grow_seconds_for_crop",
    "normalize_seed_id",
    "roll_harvest_drops",
    "resolve_water_item_for_action",
    "all_crops",
    "crops_by_seed",
]
