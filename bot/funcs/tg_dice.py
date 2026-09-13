# -*- coding: utf-8 -*-
"""Исход Telegram-dice = то, что видит игрок в анимации.

Документация python-telegram-bot / фактическая анимация Telegram:
  ⚽  4–5 гол, 1–3 мимо (3 — штанга, выглядит «почти», но это промах)
  🏀  4–5 кольцо, 1–3 мимо (3 — удар в дужку)
  🎯  6 центр, 1–5 мимо (5 — соседнее кольцо, не центр)
  🎳  6 страйк, 1–5 не страйк (5 кеглей — не победа)

Если value не пришёл — это не проигрыш. Вызывающий код не должен
списывать ставку «вслепую».
"""

from __future__ import annotations

from typing import Any, Optional, Set

SOCCER_WIN = frozenset({4, 5})
BASKET_WIN = frozenset({4, 5})
DARTS_WIN = frozenset({6})
BOWLING_WIN = frozenset({6})


def read_dice_value(msg: Any) -> Optional[int]:
    raw = getattr(getattr(msg, "dice", None), "value", None)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


def _is_win(value: Optional[int], wins: Set[int] | frozenset) -> bool:
    return value is not None and int(value) in wins


def is_soccer_goal(value: Optional[int]) -> bool:
    return _is_win(value, SOCCER_WIN)


def is_basket_hit(value: Optional[int]) -> bool:
    return _is_win(value, BASKET_WIN)


def is_darts_bullseye(value: Optional[int]) -> bool:
    return _is_win(value, DARTS_WIN)


def is_bowling_strike(value: Optional[int]) -> bool:
    return _is_win(value, BOWLING_WIN)


async def abort_if_unread_dice(message: Any, value: Optional[int], log=None) -> bool:
    """True = бросок не прочитался, ставку трогать нельзя."""
    if value is not None:
        return False
    if log:
        try:
            log("DICE", "value missing — skip settle")
        except Exception:
            pass
    try:
        await message.reply(
            "<b>Бросок не прочитался. Ставка не списана — повторите удар.</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    return True
