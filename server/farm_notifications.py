"""Уведомления фермы: что получено / потрачено (для клиентских плашек)."""

from __future__ import annotations

from content_registry import _item_brief


def notify_item(item_id: str, amount: int) -> dict:
    brief = _item_brief(item_id)
    qty = max(1, int(amount))
    return {
        "itemId": brief["id"],
        "amount": qty,
        "name": brief["name"],
        "emoji": brief["emoji"],
    }


def merge_notify_items(rows: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in rows:
        item_id = str(row.get("itemId", ""))
        if not item_id:
            continue
        if item_id in merged:
            merged[item_id]["amount"] += int(row.get("amount", 0))
        else:
            merged[item_id] = dict(row)
    return list(merged.values())


def attach_farm_notify(state: dict, *, gained: list[dict] | None = None, spent: list[dict] | None = None) -> dict:
    if gained:
        state["farmGained"] = merge_notify_items(gained)
    if spent:
        state["farmSpent"] = merge_notify_items(spent)
    return state
