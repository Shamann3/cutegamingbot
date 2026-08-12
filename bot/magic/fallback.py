# -*- coding: utf-8 -*-
"""Последний шанс для callback: гасим «часики», если никто не обработал.

После рестарта люди жмут старые кнопки (сессии игр уже нет) —
без fallback спиннер крутится вечно. Этот handler должен быть
подключён ПОСЛЕДНИМ роутером.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import CallbackQuery

logger = logging.getLogger("magic")

fallback_router = Router(name="magic_fallback")


@fallback_router.callback_query()
async def _magic_orphan_callback(query: CallbackQuery) -> None:
    """Любой callback без своего handler'а — тихо гасим спиннер."""
    try:
        await query.answer()
    except Exception:
        try:
            # просроченный callback после рестарта — тоже ок
            pass
        except Exception:
            pass
    try:
        data = (query.data or "")[:80]
        logger.info("orphan callback answered data=%r", data)
    except Exception:
        pass
