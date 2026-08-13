# -*- coding: utf-8 -*-
"""Последний шанс для callback.

Порядок:
  1) HOT DISPATCH — известный префикс (kostijoin и т.п.), модуль мог не
     быть импортирован после рестарта → import + вызов handler.
  2) BLC — hydrate opaque-токенов / refresh markup через Telegram.
  3) Честный alert «устарела», без вечного спиннера.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import CallbackQuery

logger = logging.getLogger("magic")

fallback_router = Router(name="magic_fallback")


@fallback_router.callback_query()
async def _magic_orphan_callback(query: CallbackQuery) -> None:
    data = (query.data or "")[:80]

    # 1) Hot-dispatch игровых/меню префиксов (кости, орёл, …)
    try:
        from bot.runtime.callback_bootstrap import try_hot_dispatch

        if await try_hot_dispatch(query):
            logger.info("orphan hot-dispatched data=%r", data)
            return
    except Exception as e:
        logger.warning("hot-dispatch: %r", e)

    # 2) BLC resurrect (opaque tokens + markup refresh)
    try:
        from bot.runtime.button_lifecycle import handle_orphan_callback

        if await handle_orphan_callback(query):
            logger.info("orphan BLC-handled data=%r", data)
            return
    except Exception as e:
        logger.warning("BLC orphan: %r", e)

    # 3) Последний ответ
    try:
        await query.answer(
            "⏳ Кнопка устарела после перезапуска.\nОткройте меню заново.",
            show_alert=True,
        )
    except Exception:
        try:
            await query.answer()
        except Exception:
            pass
    logger.info("orphan callback answered data=%r", data)
