# -*- coding: utf-8 -*-
"""Инлайн «морской бой».

Сроки, поле, флот и сама партия — в bot/games/sea.py.
Здесь только карточка в инлайн-запросе и вход кнопок seai:.
"""
from __future__ import annotations

import uuid

from aiogram import Router
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from bot.games.sea import INLINE, invite_text, parse_sea, press

router = Router(name="sea_inline")
_THUMB = "https://postimg.cc/tYLyWncT"


def _article(title: str, description: str, text: str, markup=None) -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id=uuid.uuid4().hex,
        title=title,
        description=description,
        input_message_content=InputTextMessageContent(message_text=text, parse_mode="HTML"),
        reply_markup=markup,
        thumb_url=_THUMB,
    )


def catalog_article(user_id: int) -> InlineQueryResultArticle:
    """Карточка без ставки для общего списка игр."""
    button = InlineKeyboardButton(text="Создать игру", callback_data=f"seai:n:{int(user_id)}:0")
    return _article(
        "Морской бой",
        "🛥 Начать игру в морской бой",
        invite_text(0),
        InlineKeyboardMarkup(inline_keyboard=[[button]]),
    )


async def offer_sea(query_text: str, user_id: int, results: list) -> None:
    try:
        await _offer(query_text, int(user_id), results)
    except Exception as exc:
        print(f"[SEA] offer {type(exc).__name__}")


async def _offer(query_text: str, user_id: int, results: list) -> None:
    kind, bet = parse_sea(query_text or "")
    if kind == "ignore":
        return
    if kind != "play":
        results.append(_article(
            "Морской бой",
            "🛥 Начать игру в морской бой",
            "<tg-emoji emoji-id='6001395499628762723'>🎁</tg-emoji> <b>Морской бой</b>\nНапишите : <code>@CuteGamingBot морской бой</code> или <code>@CuteGamingBot морской бой 10</code>",
        ))
        return
    bet = int(bet or 0)
    if bet > 0:
        from bot.funcs.stake_gate import read_stake_balance
        have = int(await read_stake_balance(user_id) or 0)
        if have < bet:
            have_text = f"{have:,}".replace(",", ".")
            results.append(_article(
                "💰 Не хватает кут",
                f"На балансе {have_text}",
                "<tg-emoji emoji-id='6001395499628762723'>🎁</tg-emoji> <b>Морской бой</b>\n<i>На балансе меньше ставки.</i>",
            ))
            return
    shown = "Без ставки" if bet <= 0 else "Ставка " + f"{bet:,}".replace(",", ".") + " кут"
    button = InlineKeyboardButton(text="Создать игру", callback_data=f"seai:n:{user_id}:{bet}")
    results.append(_article(
        "Морской бой",
        shown,
        invite_text(bet),
        InlineKeyboardMarkup(inline_keyboard=[[button]]),
    ))


@router.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("seai:"))
async def sea_inline_press(query):
    await press(query, INLINE)
