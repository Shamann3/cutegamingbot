# -*- coding: utf-8 -*-
"""Какой предмет из dex человек реально держит, когда пишет «использовать»."""
from __future__ import annotations


def _field(row, key: str) -> str:
    try:
        value = row[key]
    except Exception:
        return ""
    return str(value or "").strip()


def held_inventory_key(inventory: dict, *candidates: str) -> str | None:
    """Ключ users.items, под которым лежит этот предмет: имя, id или name1."""
    wanted = []
    for item in candidates:
        text = str(item or "").strip()
        if text and text not in wanted:
            wanted.append(text)
    if not wanted or not isinstance(inventory, dict):
        return None
    folded = {}
    for raw, value in inventory.items():
        folded.setdefault(str(raw).strip().casefold(), str(raw))

    def count(key: str) -> int:
        try:
            return int(inventory.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    for key in wanted:
        if count(key) > 0:
            return key
        real = folded.get(key.casefold())
        if real and count(real) > 0:
            return real
    return None


def pick_held_row(rows, inventory: dict):
    """Строка dex и ключ инвентаря. Чужой предмет с тем же эмодзи не выбирается."""
    held = []
    for row in rows or []:
        key = held_inventory_key(
            inventory,
            _field(row, "name"),
            _field(row, "id"),
            _field(row, "name1"),
            _field(row, "emoji"),
        )
        if key:
            held.append((row, key))
    if not held:
        return None, None
    for row, key in held:
        if key == _field(row, "name"):
            return row, key
    return held[0]
