# -*- coding: utf-8 -*-
"""
Фабрика inline-кнопок Мэджик.

Для НОВОГО кода удобнее создавать кнопки так:

    from bot.magic import btn, markup
    kb = markup([[btn("🌴 Ок", callback_data="ok")]])

Старые InlineKeyboardButton тоже под Мэджик
(через middleware + patch) — их логику менять не нужно.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

try:
    from bot.funcs.gc_emoji import gc_btn as _gc_btn
except Exception:  # pragma: no cover
    _gc_btn = None


def btn(
    text: str,
    *,
    callback_data: Optional[str] = None,
    url: Optional[str] = None,
    icon: Optional[str] = None,
    icon_custom_emoji_id: Optional[str] = None,
    style: str = "default",
    premium_emoji: bool = True,
) -> InlineKeyboardButton:
    """Создать кнопку под контролем Мэджик."""
    eid = icon_custom_emoji_id or icon

    if premium_emoji and _gc_btn is not None and eid is None:
        try:
            return _gc_btn(
                text,
                callback_data=callback_data,
                url=url,
                style="default",
            )
        except Exception:
            pass

    kwargs: Dict[str, Any] = {
        "text": str(text or "·"),
        "style": "default" if style == "primary" else (style or "default"),
    }
    if eid:
        kwargs["icon_custom_emoji_id"] = str(eid)
    if url:
        kwargs["url"] = url
    elif callback_data is not None:
        kwargs["callback_data"] = str(callback_data)

    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs.pop("style", None)
        try:
            return InlineKeyboardButton(**kwargs)
        except TypeError:
            kwargs.pop("icon_custom_emoji_id", None)
            return InlineKeyboardButton(
                text=str(text or "·"),
                **({"url": url} if url else {"callback_data": callback_data}),
            )


def row(*buttons: InlineKeyboardButton) -> List[InlineKeyboardButton]:
    return list(buttons)


def markup(rows: Sequence[Sequence[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])


def simple_kb(
    items: Sequence[Union[InlineKeyboardButton, Dict[str, Any]]],
    *,
    cols: int = 1,
) -> InlineKeyboardMarkup:
    buttons: List[InlineKeyboardButton] = []
    for it in items:
        if isinstance(it, InlineKeyboardButton):
            buttons.append(it)
        else:
            d = dict(it or {})
            buttons.append(
                btn(
                    d.get("text", "·"),
                    callback_data=d.get("callback_data"),
                    url=d.get("url"),
                    icon=d.get("icon") or d.get("icon_custom_emoji_id"),
                    style=d.get("style") or "default",
                )
            )
    cols = max(1, int(cols))
    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(buttons), cols):
        rows.append(buttons[i : i + cols])
    return markup(rows)
