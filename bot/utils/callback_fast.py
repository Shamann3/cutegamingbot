# -*- coding: utf-8 -*-
"""Совместимость: быстрые callback теперь внутри Мэджик.

Новый код:
    from bot.magic import fire_answer, install_magic
"""
from __future__ import annotations

from bot.magic.answer import fire_answer, safe_answer
from bot.magic.middleware import MagicCallbackMiddleware as FastCallbackMiddleware

__all__ = ["fire_answer", "safe_answer", "FastCallbackMiddleware"]
