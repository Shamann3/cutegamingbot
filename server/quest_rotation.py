"""Ротация заданий по расписанию: 2 часовых, 3 дневных, 1 недельный."""

from __future__ import annotations

import hashlib
import random
from typing import TYPE_CHECKING

from quest_registry import enabled_quests, quests_for_period

if TYPE_CHECKING:
    from quest_registry import QuestDef

# Сколько заданий показывается в ротации за период.
PERIOD_SLOT_LIMITS: dict[str, int] = {
    "hourly": 2,
    "daily": 3,
    "weekly": 1,
}
# Сколько заданий можно взять одновременно (одно на период).
PERIOD_ACCEPT_LIMIT: dict[str, int] = {
    "hourly": 1,
    "daily": 1,
    "weekly": 1,
}


def is_event_quest(quest: "QuestDef") -> bool:
    """Ивентовые квесты (даты / recurrence) — отдельно от ротации."""
    return (
        quest.active_from is not None
        or quest.active_until is not None
        or quest.recurrence is not None
    )


def pool_quests_for_period(period: str) -> list["QuestDef"]:
    return [
        quest
        for quest in quests_for_period(period)
        if not is_event_quest(quest) and quest.action != "claim_daily_seed"
    ]


def event_quests() -> tuple["QuestDef", ...]:
    return tuple(quest for quest in enabled_quests() if is_event_quest(quest))


def rotated_quests_for_period(period: str, period_key: str) -> list["QuestDef"]:
    """Детерминированный выбор N заданий из пула на текущий period_key."""
    pool = pool_quests_for_period(period)
    limit = PERIOD_SLOT_LIMITS.get(period, 1)
    if not pool:
        return []
    if len(pool) <= limit:
        return sorted(pool, key=lambda q: (q.sort_order, q.key))

    seed = int(
        hashlib.sha256(f"{period}:{period_key}".encode()).hexdigest()[:12],
        16,
    )
    rng = random.Random(seed)
    shuffled = list(pool)
    rng.shuffle(shuffled)
    picked = shuffled[:limit]
    return sorted(picked, key=lambda q: (q.sort_order, q.key))


def visible_quest_keys_for_period(period: str, period_key: str) -> frozenset[str]:
    keys = {q.key for q in rotated_quests_for_period(period, period_key)}
    for quest in quests_for_period(period):
        if quest.action == "claim_daily_seed" and not is_event_quest(quest):
            keys.add(quest.key)
    return frozenset(keys)


def quest_in_current_rotation(quest: "QuestDef", period_key: str) -> bool:
    if is_event_quest(quest):
        return True
    if quest.action == "claim_daily_seed":
        return True
    return quest.key in visible_quest_keys_for_period(quest.period, period_key)
