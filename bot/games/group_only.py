# -*- coding: utf-8 -*-
"""Общий запрет запуска игр в личке с ботом.

Все игры проекта вызывают ``reject_if_private_game(message)`` в начале
обработчика (после того, как команда уже распознана как игровая).
Онбординг не затрагивается: он передаёт синтетическое сообщение из группы.
"""

from __future__ import annotations

from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

PRIVATE_GAME_TEXT = (
    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
    "<b>В эту игру можно играть только в публичных группах.</b>"
)
PLAY_GROUP_URL = "https://t.me/CuteGamingChat"
PLAY_BUTTON_ICON = "5303138782004924588"  # как у «Играть в группе» в /start


def is_private_chat(message: Optional[Message]) -> bool:
    if message is None or getattr(message, "chat", None) is None:
        return False
    return str(getattr(message.chat, "type", "") or "") == "private"


def private_game_markup() -> InlineKeyboardMarkup:
    kwargs = {
        "text": "Играть",
        "url": PLAY_GROUP_URL,
        "style": "primary",
        "icon_custom_emoji_id": PLAY_BUTTON_ICON,
    }
    try:
        btn = InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs.pop("style", None)
        kwargs.pop("icon_custom_emoji_id", None)
        try:
            btn = InlineKeyboardButton(**kwargs)
        except TypeError:
            btn = InlineKeyboardButton(text="Играть", url=PLAY_GROUP_URL)
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])


async def reject_if_private_game(message: Message) -> bool:
    """Если чат личный — отвечает CTA и возвращает True (игру нужно прервать)."""
    if not is_private_chat(message):
        return False

    kb = private_game_markup()
    try:
        await message.reply(
            PRIVATE_GAME_TEXT,
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True
    except Exception:
        pass

    # Fallback без премиум-иконки / style
    try:
        plain_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Играть", url=PLAY_GROUP_URL),
        ]])
        await message.reply(
            "☁️ <b>В эту игру можно играть только в публичных группах.</b>",
            reply_markup=plain_kb,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        print(f"[GROUP_ONLY] private reject failed: {e!r}")
    return True
