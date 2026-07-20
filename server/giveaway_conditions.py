"""Розыгрыши: реестр проверяемых условий участия.

Каждое условие — запись в CONDITION_CHECKERS. Новые типы условий
(quest_count — следующие фазы) добавляются сюда новой записью, не трогая
участие/список/детали розыгрыша.
"""
from __future__ import annotations

from typing import Callable

VALID_CONDITION_KINDS = frozenset({
    "balance", "harvest_count", "item_count", "channel_sub", "referral_count",
})


def check_balance(ctx: dict, cond: dict) -> bool:
    return int(ctx.get("balance") or 0) >= int(cond["target_value"])


def check_harvest_count(ctx: dict, cond: dict) -> bool:
    return int(ctx.get("harvest_count") or 0) >= int(cond["target_value"])


def check_item_count(ctx: dict, cond: dict) -> bool:
    items = ctx.get("items") or {}
    return int(items.get(cond["item_id"], 0)) >= int(cond["target_value"])


def check_referral_count(ctx: dict, cond: dict) -> bool:
    return int(ctx.get("referral_count") or 0) >= int(cond["target_value"])


def check_channel_sub(ctx: dict, cond: dict) -> bool:
    channel_sub = ctx.get("channel_sub") or {}
    return bool(channel_sub.get(cond["item_id"], False))


CONDITION_CHECKERS: dict[str, Callable[[dict, dict], bool]] = {
    "balance": check_balance,
    "harvest_count": check_harvest_count,
    "item_count": check_item_count,
    "referral_count": check_referral_count,
    "channel_sub": check_channel_sub,
}


def condition_satisfied(ctx: dict, cond: dict) -> bool:
    checker = CONDITION_CHECKERS.get(cond.get("kind"))
    if checker is None:
        return False
    return checker(ctx, cond)


def all_conditions_met(ctx: dict, conditions: list[dict]) -> bool:
    return all(condition_satisfied(ctx, cond) for cond in conditions)
