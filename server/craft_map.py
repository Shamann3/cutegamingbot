"""Чистые хелперы карты крафта (без БД, для тестируемости)."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def serialize_positions(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    """Строки craft_map_positions -> {itemId: {x, y}}."""
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        item_id = str(row["item_id"])
        out[item_id] = {"x": float(row["x"]), "y": float(row["y"])}
    return out
