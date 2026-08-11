# -*- coding: utf-8 -*-
"""Совместимость: фабрика кнопок теперь живёт в Мэджик.

    from bot.utils.inline_ui import btn, markup, fire_answer
    # то же самое:
    from bot.magic import btn, markup, fire_answer
"""
from __future__ import annotations

from bot.magic.answer import fire_answer, safe_answer
from bot.magic.buttons import btn, markup, row, simple_kb

__all__ = ["btn", "markup", "row", "simple_kb", "fire_answer", "safe_answer"]
