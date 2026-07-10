"""Backward-compatible re-exports — см. quest_registry."""

from quest_registry import (
    QuestDef,
    QuestRewardDef,
    all_quests,
    enabled_quests,
    quest_by_key,
    quests_for_period,
)

__all__ = [
    "QuestDef",
    "QuestRewardDef",
    "all_quests",
    "enabled_quests",
    "quest_by_key",
    "quests_for_period",
]
