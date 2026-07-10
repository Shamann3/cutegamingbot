"""Чтение/запись users.items (JSON) и users.balance."""

from typing import Any

from json_db_codec import decode_json_payload, encode_json_payload


def parse_items(raw: Any) -> dict:
    return decode_json_payload(raw)


def items_to_db(items: dict) -> str:
    from dex_catalog import dex_catalog

    name_map: dict[str, str] = {}
    if dex_catalog.loaded:
        for key in items:
            entry = dex_catalog.get(str(key))
            if entry and entry.name and entry.name.strip():
                name_map[str(key)] = entry.name.strip()
    return encode_json_payload(items, name_map=name_map or None)


def seed_count(items: dict) -> int:
    from config import SEED_ITEM_KEY

    return count_item_in_storage(items, SEED_ITEM_KEY)


def tobacco_seed_count(items: dict) -> int:
    from config import TOBACCO_SEED_ITEM_KEY

    return count_item_in_storage(items, TOBACCO_SEED_ITEM_KEY)


def water_count(items: dict) -> int:
    from config import WATER_ITEM_KEY

    return count_item_in_storage(items, WATER_ITEM_KEY)


def autowater_count(items: dict) -> int:
    from config import AUTOWATER_ITEM_KEY

    return count_item_in_storage(items, AUTOWATER_ITEM_KEY)


def count_seed_for_crop(raw_items: dict, crop) -> int:
    """Саженцы культуры — через dex (id, name, emoji, legacy)."""
    from content_registry import normalize_seed_id

    return count_item_in_storage(raw_items, normalize_seed_id(crop.seed_id))


def take_seed_from_storage(raw_items: dict, crop, amount: int = 1) -> dict:
    from content_registry import normalize_seed_id

    return take_item_from_storage(raw_items, normalize_seed_id(crop.seed_id), amount)


def plantable_seed_counts(items: dict) -> dict[str, int]:
    from content_registry import enabled_crops, normalize_seed_id

    return {
        normalize_seed_id(crop.seed_id): count_seed_for_crop(items, crop)
        for crop in enabled_crops()
    }


def log_count(items: dict) -> int:
    from config import TREE_ITEM_KEY

    return count_item_in_storage(items, TREE_ITEM_KEY)


def add_item(items: dict, key: str, amount: int) -> dict:
    items = dict(items)
    items[key] = int(items.get(key, 0)) + amount
    return items


def take_item(items: dict, keys: tuple[str, ...], amount: int = 1) -> dict:
    """Списывает amount с первого найденного ключа (нормализованный dict)."""
    items = dict(items)
    left = amount
    for key in keys:
        if key not in items:
            continue
        try:
            have = int(items[key])
        except (TypeError, ValueError):
            have = 0
        if have <= 0:
            continue
        take = min(have, left)
        items[key] = have - take
        if items[key] <= 0:
            del items[key]
        left -= take
        if left <= 0:
            break
    if left > 0:
        raise ValueError("У Вас недостаточно предметов")
    return items


def count_item_in_storage(raw_items: dict, item_id: str) -> int:
    from dex_catalog import dex_catalog

    if dex_catalog.loaded:
        return dex_catalog.count_in_raw_items(raw_items, item_id)
    try:
        return max(0, int((raw_items or {}).get(str(item_id), 0) or 0))
    except (TypeError, ValueError):
        return 0


def take_item_from_storage(raw_items: dict, item_id: str, amount: int) -> dict:
    """Списывает предмет из users.items и сохраняет остаток под dex id."""
    from dex_catalog import dex_catalog

    if dex_catalog.loaded:
        return dex_catalog.take_from_raw_items(raw_items, item_id, amount)
    stored = dict(raw_items or {})
    have = count_item_in_storage(stored, item_id)
    if have < amount:
        raise ValueError("У Вас недостаточно предметов")
    canon = str(item_id)
    stored[canon] = have - amount
    if stored[canon] <= 0:
        stored.pop(canon, None)
    return stored


def plot_buy_price(next_plot_id: int) -> int:
    """Купить грядку #2 → step, #3 → 2*step … (грядка #1 бесплатна)."""
    from economy_settings import get_plot_price_step

    return (next_plot_id - 1) * get_plot_price_step()


def add_shop_item_to_storage(raw_items: dict, dex_id: str, amount: int = 1) -> dict:
    """Добавить купленный предмет в users.items (dex id в JSON)."""
    from content_registry import all_game_item_ids
    from dex_catalog import dex_catalog, merge_items_for_storage, normalize_items

    dex_id = dex_catalog.resolve_item_id(str(dex_id))
    amount = max(1, int(amount))

    if dex_id in all_game_item_ids():
        game_items = normalize_items(raw_items)
        game_items = add_item(game_items, dex_id, amount)
        return merge_items_for_storage(raw_items, game_items)

    stored = dict(raw_items)
    try:
        current = int(stored.get(dex_id, 0) or 0)
    except (TypeError, ValueError):
        current = 0
    stored[dex_id] = current + amount
    return stored


def count_item(raw_items: dict, item_id: str) -> int:
    return count_item_in_storage(raw_items, item_id)


def _ingredient_totals(ingredients: list[dict]) -> dict[str, int]:
    from collections import defaultdict

    from dex_catalog import dex_catalog

    totals: dict[str, int] = defaultdict(int)
    for ing in ingredients:
        try:
            qty = max(1, int(ing["qty"]))
        except (KeyError, TypeError, ValueError):
            raise ValueError("Некорректный рецепт") from None
        canon = dex_catalog.resolve_item_id(str(ing["id"]))
        totals[canon] += qty
    return dict(totals)


def can_craft(raw_items: dict, ingredients: list[dict]) -> bool:
    try:
        totals = _ingredient_totals(ingredients)
    except ValueError:
        return False
    return all(count_item(raw_items, item_id) >= qty for item_id, qty in totals.items())


def take_craft_ingredients(raw_items: dict, ingredients: list[dict]) -> dict:
    from dex_catalog import merge_items_for_storage, normalize_items

    totals = _ingredient_totals(ingredients)
    stored = dict(raw_items)
    for canon, qty in totals.items():
        stored = take_item_from_storage(stored, canon, qty)
    return merge_items_for_storage(raw_items, normalize_items(stored))
