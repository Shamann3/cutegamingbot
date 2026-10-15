# -*- coding: utf-8 -*-
"""Старый вход seai:. Морской бой из инлайна убран — только сообщение в группе."""
from __future__ import annotations

from aiogram import Router

from bot.games.sea import INLINE, press

router = Router(name="sea_inline")


def catalog_article(user_id: int):
    """Инлайн-карточка отключена."""
    return None


async def offer_sea(query_text: str, user_id: int, results: list) -> None:
    """Морской бой в инлайн-поиске больше не предлагается."""
    return


@router.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("seai:"))
async def sea_inline_press(query):
    await press(query, INLINE)
