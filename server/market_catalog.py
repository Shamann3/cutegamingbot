"""Игровая биржа: лоты игроков, фильтры и сортировка (как в магазине)."""

from __future__ import annotations

from shop_catalog import (
    ALL_CATEGORY_ID,
    OTHER_CATEGORY_ID,
    PRICE_FILTER_ALL,
    PRICE_FILTER_CHEAP,
    PRICE_FILTER_EXPENSIVE,
    PRICE_FILTER_SALE,
    SORT_BY_NAME,
    SORT_BY_PRICE,
    SORT_BY_REMAINS,
    SORT_ORDER_DESC,
    build_sort_filters,
    category_from_sorting,
    normalize_page_size,
    normalize_price_filter,
    normalize_search_query,
    normalize_sort_by,
    normalize_sort_order,
    sorting_for_category_id,
    _resolve_item_description,
    _stick_composition,
)
from player_profile import seller_fields_from_row


def _seller_profile_row(row: dict) -> dict:
    return {
        "user_id": row.get("seller_id"),
        "username": row.get("seller_username"),
        "first_name": row.get("seller_first_name"),
        "last_name": row.get("seller_last_name"),
        "display_name": row.get("seller_display_name"),
        "photo_url": row.get("seller_photo_url"),
    }


def build_market_price_filter_clause(price_filter: str) -> str | None:
    if price_filter == PRICE_FILTER_CHEAP:
        return "l.price <= 100"
    if price_filter == PRICE_FILTER_EXPENSIVE:
        return "l.price >= 200"
    if price_filter == PRICE_FILTER_SALE:
        return None
    return None


def build_market_order_clause(sort_by: str, sort_order: str) -> str:
    direction = "DESC" if sort_order == SORT_ORDER_DESC else "ASC"
    if sort_by == SORT_BY_PRICE:
        return f"l.price {direction}, d.name ASC"
    if sort_by == SORT_BY_REMAINS:
        return f"l.quantity {direction}, d.name ASC"
    return f"d.name {direction}"


def listing_to_client(row: dict, *, viewer_id: int | None = None) -> dict:
    sorting = row.get("sorting")
    cat = category_from_sorting(sorting, 0)
    composition = _stick_composition(row)
    seller_id = int(row["seller_id"])
    seller = seller_fields_from_row(_seller_profile_row(row), viewer_id=viewer_id)
    return {
        "id": str(row["listing_id"]),
        **seller,
        "itemId": str(row["item_id"]),
        "name": (row.get("name") or "").strip() or str(row["item_id"]),
        "emoji": (row.get("emoji") or "").strip() or "📦",
        "description": _resolve_item_description(row),
        "bio": _resolve_item_description(row),
        "composition": composition,
        "categoryLabel": cat["label"],
        "sorting": sorting,
        "categoryId": cat["id"],
        "quantity": max(0, int(row.get("quantity") or 0)),
        "price": max(0, int(row.get("price") or 0)),
        "remains": max(0, int(row.get("quantity") or 0)),
        "isMine": viewer_id is not None and seller_id == int(viewer_id),
        "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def sellable_item_to_client(entry, *, count: int) -> dict:
    return {
        "itemId": entry.id,
        "name": entry.name,
        "emoji": entry.emoji,
        "count": int(count),
    }
