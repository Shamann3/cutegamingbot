"""Правила игровой биржи: какие предметы можно выставлять."""

from __future__ import annotations

import math

from config import AUTOWATER_ITEM_KEY, WATER_ITEM_KEY
from content_registry import seed_item_ids
from dex_catalog import dex_catalog
MARKET_MIN_PRICE = 1
MARKET_MAX_PRICE = 999_999
MARKET_MAX_LIST_QUANTITY = 99
MARKET_COMMISSION_PERCENT = 7


def calc_market_commission(gross: int) -> int:
    gross = max(0, int(gross))
    if gross == 0:
        return 0
    return max(1, math.ceil(gross * MARKET_COMMISSION_PERCENT / 100))


def calc_market_seller_payout(gross: int) -> int:
    return max(0, int(gross) - calc_market_commission(gross))


def market_commission_meta() -> dict:
    return {"commissionPercent": MARKET_COMMISSION_PERCENT}


def normalize_market_item_id(item_id: str) -> str:
    return dex_catalog.canonical_key(str(item_id).strip())


def market_blocked_item_ids() -> frozenset[str]:
    blocked = set()
    # Саженцы и вода теперь продаются.
    # blocked.update(seed_item_ids())
    # blocked.add(dex_catalog.canonical_key(WATER_ITEM_KEY))
    try:
        blocked.add(dex_catalog.canonical_key(AUTOWATER_ITEM_KEY))
    except Exception as exc:
        print(f"[MARKET][RULES][WARN] autowater key: {exc!r}")
    return frozenset(blocked)


def is_market_listable(item_id: str) -> bool:
    try:
        canon = normalize_market_item_id(item_id)
        if not canon:
            return False
        return canon not in market_blocked_item_ids()
    except Exception as exc:
        print(f"[MARKET][RULES][WARN] is_market_listable({item_id!r}): {exc!r}")
        return False

def seller_label(user_id: int) -> str:
    tail = str(abs(int(user_id)))[-4:].rjust(4, "0")
    return f"Игрок #{tail}"
