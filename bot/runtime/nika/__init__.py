# -*- coding: utf-8 -*-
"""Система «Ника»: автоподдержание баланса выбранных групп."""

from bot.runtime.nika.policy import SOURCE_LADDER, SWEEP_DEST_CHAT_ID, suggest_caps
from bot.runtime.nika.schema import FIRST_MANAGED_CHAT_ID, FIRST_MANAGED_TARGET, ensure_nika_schema

__all__ = [
    "FIRST_MANAGED_CHAT_ID",
    "FIRST_MANAGED_TARGET",
    "SOURCE_LADDER",
    "SWEEP_DEST_CHAT_ID",
    "ensure_nika_schema",
    "suggest_caps",
]
