"""Биржа: категории по dex.sorting, фильтры и пагинация (как в текстовом боте)."""

from __future__ import annotations

from json_db_codec import decode_json_payload, format_payload_text, is_telegram_file_id

SHOP_PAGE_SIZE = 8

ALL_CATEGORY_ID = "all"
OTHER_CATEGORY_ID = "other"

# Порядок как в текстовой бирже: 5 кнопок filter_by_sorting в верхнем ряду
SHOP_SORT_FILTERS: tuple[dict[str, str], ...] = (
    {"id": "sort_games", "sorting": "\U0001f3ae", "emoji": "\U0001f3ae", "label": "Игры"},
    {"id": "sort_flags", "sorting": "\U0001f1eb\U0001f1f7", "emoji": "\U0001f1eb\U0001f1f7", "label": "Флаги"},
    {"id": "sort_keys", "sorting": "\U0001f511", "emoji": "\U0001f511", "label": "Ключи"},
    {"id": "sort_stars", "sorting": "\U0001f31f", "emoji": "\U0001f31f", "label": "Звёзды"},
    {"id": "sort_hearts", "sorting": "\U0001f496", "emoji": "\U0001f496", "label": "Сердца"},
)

SORTING_LABELS: dict[str, str] = {entry["sorting"]: entry["label"] for entry in SHOP_SORT_FILTERS}
SORTING_LABELS[OTHER_CATEGORY_ID] = "Разное"


def category_from_sorting(sorting: str | None, count: int) -> dict:
    if sorting is None:
        return {
            "id": OTHER_CATEGORY_ID,
            "label": "Разное",
            "emoji": "📦",
            "sorting": None,
            "count": count,
        }
    return {
        "id": sorting,
        "label": SORTING_LABELS.get(sorting, sorting),
        "emoji": sorting,
        "sorting": sorting,
        "count": count,
    }


def build_sort_filters(counts_by_sorting: dict[str | None, int]) -> list[dict]:
    """5 фиксированных кнопок сортировки + количество в наличии."""
    filters = []
    for entry in SHOP_SORT_FILTERS:
        sorting = entry["sorting"]
        filters.append(
            {
                "id": entry["id"],
                "sorting": sorting,
                "emoji": entry["emoji"],
                "label": entry["label"],
                "count": counts_by_sorting.get(sorting, 0),
            }
        )
    return filters


def sorting_for_category_id(category_id: str) -> str | None | object:
    """None = все предметы, '__null__' = sorting IS NULL."""
    if category_id in (ALL_CATEGORY_ID, ""):
        return None
    if category_id == OTHER_CATEGORY_ID:
        return "__null__"

    for entry in SHOP_SORT_FILTERS:
        if category_id == entry["id"]:
            return entry["sorting"]

    return category_id


def item_price_row(price: int, discount: int) -> dict:
    price = max(0, int(price or 0))
    discount = max(0, int(discount or 0))
    sale_price = discount if discount > 0 else None
    return {"price": price, "salePrice": sale_price}


def effective_price(price: int, discount: int) -> int:
    """Цена покупки: dis если задана И меньше price (настоящая скидка), иначе price."""
    price = max(0, int(price or 0))
    discount = max(0, int(discount or 0))
    if discount > 0 and discount < price:
        return discount
    return price


def _stick_composition(row: dict) -> dict[str, int]:
    stick = row.get("stick")
    if stick in (None, ""):
        return {}
    if isinstance(stick, dict):
        return decode_json_payload(stick)
    text = str(stick).strip()
    if not text or is_telegram_file_id(text):
        return {}
    return decode_json_payload(text)


def _build_fallback_description(row: dict) -> str:
    parts: list[str] = []

    composition = _stick_composition(row)
    composition_text = format_payload_text(composition)
    if composition_text:
        parts.append(f"Состав: {composition_text}")

    use_val = row.get("use")
    if use_val not in (None, 0, ""):
        parts.append(f"Использование: {use_val}")

    bonus = row.get("bonus")
    if bonus not in (None, 0, ""):
        parts.append(f"Бонус: +{bonus}")

    craft = row.get("craft")
    if craft not in (None, 0, ""):
        parts.append(f"Крафт: {craft}")

    if not parts:
        return ""
    return " · ".join(parts)


def _resolve_item_description(row: dict) -> str:
    bio = (row.get("bio") or "").strip()
    if bio:
        return bio
    return _build_fallback_description(row)


def item_to_client(row: dict, *, category_id: str | None = None) -> dict:
    sorting = row.get("sorting")
    cat = category_from_sorting(sorting, 0)
    prices = item_price_row(row.get("price"), row.get("dis"))
    composition = _stick_composition(row)
    return {
        "id": str(row["id"]),
        "name": (row.get("name") or "").strip() or str(row["id"]),
        "emoji": (row.get("emoji") or "").strip() or "📦",
        "description": _resolve_item_description(row),
        "bio": _resolve_item_description(row),
        "composition": composition,
        "categoryLabel": cat["label"],
        "remains": max(0, int(row.get("remains") or 0)),
        "sorting": sorting,
        "categoryId": category_id or cat["id"],
        **prices,
    }


def normalize_search_query(search: str | None) -> str:
    return (search or "").strip()[:80]


def normalize_page_size(value: int | None) -> int:
    """8 / 12 / 16 — под 2 / 3 / 4 колонки × 4 ряда."""
    size = int(value or SHOP_PAGE_SIZE)
    if size <= 10:
        return 8
    if size <= 14:
        return 12
    return 16


PRICE_FILTER_ALL = "all"
PRICE_FILTER_CHEAP = "cheap"
PRICE_FILTER_EXPENSIVE = "expensive"
PRICE_FILTER_SALE = "sale"

PRICE_FILTER_IDS = frozenset({
    PRICE_FILTER_ALL,
    PRICE_FILTER_CHEAP,
    PRICE_FILTER_EXPENSIVE,
    PRICE_FILTER_SALE,
})

SORT_BY_NAME = "name"
SORT_BY_PRICE = "price"
SORT_BY_REMAINS = "remains"

SORT_BY_IDS = frozenset({SORT_BY_NAME, SORT_BY_PRICE, SORT_BY_REMAINS})
SORT_ORDER_ASC = "asc"
SORT_ORDER_DESC = "desc"


def normalize_price_filter(value: str | None) -> str:
    key = (value or PRICE_FILTER_ALL).strip().lower()
    return key if key in PRICE_FILTER_IDS else PRICE_FILTER_ALL


def normalize_sort_by(value: str | None) -> str:
    key = (value or SORT_BY_NAME).strip().lower()
    return key if key in SORT_BY_IDS else SORT_BY_NAME


def normalize_sort_order(value: str | None) -> str:
    key = (value or SORT_ORDER_ASC).strip().lower()
    return SORT_ORDER_DESC if key == SORT_ORDER_DESC else SORT_ORDER_ASC


def effective_price_sql() -> str:
    return "COALESCE(NULLIF(dis, 0), price)"


def build_price_filter_clause(price_filter: str) -> str | None:
    price_expr = effective_price_sql()
    if price_filter == PRICE_FILTER_CHEAP:
        return f"{price_expr} <= 100"
    if price_filter == PRICE_FILTER_EXPENSIVE:
        return f"{price_expr} >= 200"
    if price_filter == PRICE_FILTER_SALE:
        return "dis > 0 AND dis < price"
    return None


def build_order_clause(sort_by: str, sort_order: str) -> str:
    direction = "DESC" if sort_order == SORT_ORDER_DESC else "ASC"
    if sort_by == SORT_BY_PRICE:
        return f"{effective_price_sql()} {direction}, name ASC"
    if sort_by == SORT_BY_REMAINS:
        return f"remains {direction}, name ASC"
    return f"name {direction}"

