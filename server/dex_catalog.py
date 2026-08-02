"""Каталог предметов из таблицы dex (id → name, emoji, name1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncpg

from config import (
    AUTOWATER_ITEM_KEY,
    AXE_ITEM_KEY,
    SEED_ITEM_KEY,
    TOBACCO_ITEM_KEY,
    TOBACCO_SEED_ITEM_KEY,
    TREE_ITEM_KEY,
    WATER_ITEM_KEY,
)

FARM_ITEM_KEYS = frozenset({SEED_ITEM_KEY, TREE_ITEM_KEY})
GAME_ITEM_KEYS = frozenset({
    SEED_ITEM_KEY,
    TREE_ITEM_KEY,
    TOBACCO_SEED_ITEM_KEY,
    TOBACCO_ITEM_KEY,
    WATER_ITEM_KEY,
    AUTOWATER_ITEM_KEY,
    AXE_ITEM_KEY,
})
FARM_ITEM_ORDER = (
    SEED_ITEM_KEY,
    TOBACCO_SEED_ITEM_KEY,
    TREE_ITEM_KEY,
    TOBACCO_ITEM_KEY,
    WATER_ITEM_KEY,
    AUTOWATER_ITEM_KEY,
    AXE_ITEM_KEY,
)

DEFAULT_HINT_FARM = "Предмет фермы"
DEFAULT_HINT = "Предмет из рюкзака"


@dataclass(frozen=True)
class DexEntry:
    id: str
    name: str
    name1: str
    emoji: str
    bio: str = ""
    sorting: str | None = None
    use: str = ""
    bonus: str = ""
    craft: str = ""


class DexCatalog:
    def __init__(self) -> None:
        self._by_id: dict[str, DexEntry] = {}
        self._alias_to_id: dict[str, str] = {}
        self._alias_lower: dict[str, str] = {}
        self._by_emoji: dict[str, str] = {}  # emoji → first matching id

    @property
    def loaded(self) -> bool:
        return bool(self._by_id)

    def _register_alias(self, alias: str, dex_id: str) -> None:
        alias = str(alias or "").strip()
        dex_id = str(dex_id or "").strip()
        if not alias or not dex_id:
            return
        self._alias_to_id[alias] = dex_id
        lower = alias.casefold()
        if lower:
            self._alias_lower[lower] = dex_id

    async def load(self, pool: asyncpg.Pool) -> None:
        rows = await pool.fetch(
            "SELECT id, name, name1, emoji, bio, sorting, use, bonus, craft FROM dex"
        )
        by_id: dict[str, DexEntry] = {}
        alias_to_id: dict[str, str] = {}
        alias_lower: dict[str, str] = {}
        by_emoji: dict[str, str] = {}

        for row in rows:
            entry = DexEntry(
                id=str(row["id"]),
                name=(row["name"] or "").strip() or str(row["id"]),
                name1=(row["name1"] or "").strip(),
                emoji=(row["emoji"] or "").strip() or "📦",
                bio=(row["bio"] or "").strip(),
                sorting=row["sorting"],
                use=str(row["use"] or "").strip() if row["use"] not in (None, 0) else "",
                bonus=str(row["bonus"] or "").strip() if row["bonus"] not in (None, 0) else "",
                craft=str(row["craft"] or "").strip() if row["craft"] not in (None, 0) else "",
            )
            by_id[entry.id] = entry
            for alias in (entry.id, entry.name1, entry.name):
                if alias:
                    alias_to_id[alias] = entry.id
                    alias_lower[alias.casefold()] = entry.id
            if entry.emoji and entry.emoji not in by_emoji:
                by_emoji[entry.emoji] = entry.id
                alias_to_id[entry.emoji] = entry.id

        self._by_id = by_id
        self._alias_to_id = alias_to_id
        self._alias_lower = alias_lower
        self._by_emoji = by_emoji
        self.link_farm_item_aliases()

    def register_alias(self, alias: str, dex_id: str) -> None:
        """Публичная регистрация алиаса (legacy-ключ, конфиг-id → dex id)."""
        self._register_alias(alias, dex_id)

    def find_id_by_hints(self, *hints: str) -> str | None:
        """Найти dex id по подстроке name/name1 или точному emoji."""
        for hint in hints:
            token = str(hint or "").strip()
            if not token:
                continue
            if token in self._by_emoji:
                return self._by_emoji[token]
            if token in self._alias_to_id:
                return self._alias_to_id[token]
            needle = token.casefold()
            for entry in self._by_id.values():
                name = entry.name.casefold()
                name1 = entry.name1.casefold()
                if needle in name or (name1 and needle in name1):
                    return entry.id
        return None

    def link_farm_item_aliases(self) -> None:
        """Связать env/legacy-ключи фермы с каноническими dex id (name / emoji)."""
        from config import (
            AUTOWATER_ITEM_KEY,
            AUTOWATER_ITEM_KEYS,
            AXE_ITEM_KEY,
            AXE_ITEM_KEYS,
            LOG_ITEM_KEYS,
            SEED_ITEM_KEY,
            SEED_ITEM_KEYS,
            TOBACCO_ITEM_KEY,
            TOBACCO_ITEM_KEYS,
            TOBACCO_SEED_ITEM_KEY,
            TOBACCO_SEED_ITEM_KEYS,
            TREE_ITEM_KEY,
            WATER_ITEM_KEY,
            WATER_ITEM_KEYS,
        )

        groups: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
            (SEED_ITEM_KEY, SEED_ITEM_KEYS, ("саженец дерева", "sajeneztree", "🌱")),
            (TOBACCO_SEED_ITEM_KEY, TOBACCO_SEED_ITEM_KEYS, ("саженец табак", "sajeneztabachok", "🍃")),
            (TREE_ITEM_KEY, LOG_ITEM_KEYS, ("бревн", "justtree", "🪵")),
            (TOBACCO_ITEM_KEY, TOBACCO_ITEM_KEYS, ("🍂", "лист табак", "урожай табак")),
            (AXE_ITEM_KEY, AXE_ITEM_KEYS, ("топор", "🪓")),
            (WATER_ITEM_KEY, WATER_ITEM_KEYS, ("вода", "💧")),
            (AUTOWATER_ITEM_KEY, AUTOWATER_ITEM_KEYS, ("автополив", "🚰")),
        )

        for primary, legacy_keys, hints in groups:
            target = self.find_id_by_hints(*hints)
            if not target and primary in self._by_id:
                target = primary
            if not target:
                target = self.canonical_key(primary)
            for alias in (primary, *legacy_keys):
                self._register_alias(str(alias), target)
            entry = self.get(target)
            if entry:
                self._register_alias(entry.id, target)
                self._register_alias(entry.name, target)
                if entry.name1:
                    self._register_alias(entry.name1, target)
                if entry.emoji:
                    self._register_alias(entry.emoji, target)

    def get_id_by_emoji(self, emoji: str) -> str | None:
        """Возвращает dex id первого предмета с данным emoji."""
        return self._by_emoji.get((emoji or "").strip())

    def resolve_item_id(self, ref: str) -> str:
        """Канонический dex id: id, name, name1, emoji или legacy-ключ."""
        return self.canonical_key(str(ref or "").strip())

    def canonical_key(self, key: str) -> str:
        key = str(key).strip()
        if not key:
            return key
        if key in self._alias_to_id:
            return self._alias_to_id[key]
        lower = key.casefold()
        if lower in self._alias_lower:
            return self._alias_lower[lower]
        if key in self._by_emoji:
            return self._by_emoji[key]
        if key in self._by_id:
            return key
        return key

    def get(self, key: str) -> DexEntry | None:
        canon = self.resolve_item_id(key)
        return self._by_id.get(canon)

    def display_name(self, key: str, *, fallback: str = "Предмет") -> str:
        entry = self.get(key)
        if entry and entry.name and not entry.name.strip().isdigit():
            return entry.name
        return fallback

    def count_in_raw_items(self, raw_items: dict, item_ref: str) -> int:
        """Сумма по всем ключам users.items, которые указывают на один dex-предмет."""
        target = self.resolve_item_id(item_ref)
        total = 0
        for key, value in (raw_items or {}).items():
            if self.resolve_item_id(str(key)) == target:
                total += _to_count(value)
        return total

    def take_from_raw_items(self, raw_items: dict, item_ref: str, amount: int) -> dict:
        """Списать предмет из users.items, убрав все alias-ключи."""
        target = self.resolve_item_id(item_ref)
        amount = max(0, int(amount))
        if self.count_in_raw_items(raw_items, target) < amount:
            raise ValueError("У Вас недостаточно предметов")
        stored = dict(raw_items or {})
        left = amount
        for key in list(stored.keys()):
            if self.resolve_item_id(str(key)) != target:
                continue
            have = _to_count(stored.get(key))
            if have <= 0:
                continue
            take = min(have, left)
            remaining = have - take
            if remaining > 0:
                stored[key] = remaining
            else:
                stored.pop(key, None)
            left -= take
            if left <= 0:
                break
        return apply_item_count_to_storage(stored, target, self.count_in_raw_items(stored, target))

    def add_to_raw_items(self, raw_items: dict, item_ref: str, amount: int) -> dict:
        """Добавить предмет в users.items (для возврата купона с legacy-брони)."""
        target = self.resolve_item_id(item_ref)
        amount = max(0, int(amount))
        if amount <= 0:
            return dict(raw_items or {})
        current = self.count_in_raw_items(raw_items, target)
        return apply_item_count_to_storage(raw_items or {}, target, current + amount)

    def as_client_dict(self) -> dict[str, dict[str, str]]:
        return {
            entry.id: {
                "id": entry.id,
                "name": entry.name,
                "name1": entry.name1,
                "emoji": entry.emoji,
            }
            for entry in self._by_id.values()
        }


dex_catalog = DexCatalog()


def _to_count(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def normalize_items(items: dict) -> dict:
    """Все алиасы (name1, русское имя) → dex id."""
    merged: dict[str, int] = {}
    for key, count in items.items():
        n = _to_count(count)
        if n <= 0:
            continue
        canon = dex_catalog.canonical_key(str(key))
        merged[canon] = merged.get(canon, 0) + n
    return merged


def _aliases_for_dex_id(dex_id: str) -> list[str]:
    aliases: list[str] = []
    for alias, target in dex_catalog._alias_to_id.items():
        if target == dex_id and alias != dex_id:
            aliases.append(alias)
    return aliases


def merge_items_for_storage(original: dict, game_items: dict) -> dict:
    """Синхронизирует игровые предметы (dex id) в JSON; прочие ключи не трогаем."""
    from content_registry import all_game_item_ids

    stored = dict(original)
    for dex_id in all_game_item_ids():
        for alias in _aliases_for_dex_id(dex_id):
            stored.pop(alias, None)
        count = _to_count(game_items.get(dex_id, 0))
        if count > 0:
            stored[dex_id] = count
        else:
            stored.pop(dex_id, None)
    return stored


def apply_item_count_to_storage(original: dict, item_id: str, count: int) -> dict:
    """Записывает количество одного предмета (dex id) в users.items, убирая все алиасы."""
    canon = dex_catalog.resolve_item_id(str(item_id))
    stored = dict(original)
    for key in list(stored.keys()):
        if dex_catalog.resolve_item_id(str(key)) == canon:
            stored.pop(key, None)
    qty = _to_count(count)
    if qty > 0:
        stored[canon] = qty
    return stored


def _label(name: str, count: int) -> str:
    if count == 1:
        return name
    return name


def _row_from_key(key: str, count: int, is_farm: bool) -> dict:
    entry = dex_catalog.get(key)
    if entry:
        return {
            "key": entry.id,
            "count": count,
            "name": entry.name,
            "emoji": entry.emoji,
            "hint": DEFAULT_HINT_FARM if is_farm else DEFAULT_HINT,
            "label": _label(entry.name, count),
            "isFarm": is_farm,
        }
    name = str(key)
    return {
        "key": name,
        "count": count,
        "name": name,
        "emoji": "📦",
        "hint": DEFAULT_HINT,
        "label": _label(name, count),
        "isFarm": is_farm,
    }


def farm_item_ids_for_client() -> dict[str, str]:
    """Канонические dex id предметов фермы для клиента."""
    return {
        "seed": dex_catalog.resolve_item_id(SEED_ITEM_KEY),
        "tree": dex_catalog.resolve_item_id(TREE_ITEM_KEY),
        "tobaccoSeed": dex_catalog.resolve_item_id(TOBACCO_SEED_ITEM_KEY),
        "tobacco": dex_catalog.resolve_item_id(TOBACCO_ITEM_KEY),
        "axe": dex_catalog.resolve_item_id(AXE_ITEM_KEY),
        "water": dex_catalog.resolve_item_id(WATER_ITEM_KEY),
        "autowater": dex_catalog.resolve_item_id(AUTOWATER_ITEM_KEY),
    }


def _resolved_farm_order() -> tuple[str, ...]:
    return tuple(dex_catalog.resolve_item_id(key) for key in FARM_ITEM_ORDER)


def items_for_display(raw_items: dict) -> dict[str, list[dict]]:
    normalized = normalize_items(raw_items)
    primary: list[dict] = []
    farm_order = _resolved_farm_order()
    farm_keys = {dex_catalog.resolve_item_id(k) for k in FARM_ITEM_KEYS}
    for dex_id in farm_order:
        count = normalized.get(dex_id, 0)
        if count > 0:
            is_farm = dex_id in farm_keys or dex_id in {
                dex_catalog.resolve_item_id(TOBACCO_SEED_ITEM_KEY),
                dex_catalog.resolve_item_id(TOBACCO_ITEM_KEY),
                dex_catalog.resolve_item_id(WATER_ITEM_KEY),
                dex_catalog.resolve_item_id(AXE_ITEM_KEY),
            }
            primary.append(_row_from_key(dex_id, count, is_farm=is_farm))

    other: list[dict] = []
    listed_ids = set(farm_order)
    seen: set[str] = set()

    for key, count in raw_items.items():
        n = _to_count(count)
        if n <= 0:
            continue
        canon = dex_catalog.canonical_key(str(key))
        if canon in listed_ids:
            continue
        raw_key = str(key)
        if raw_key in seen:
            continue
        seen.add(raw_key)
        other.append(_row_from_key(raw_key, n, is_farm=False))

    return {"primary": primary, "other": other}
