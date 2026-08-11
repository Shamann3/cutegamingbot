# -*- coding: utf-8 -*-
"""
Ответы на callback внутри Мэджик.

  fire_answer(cb)  — не блокирует handler (создаёт task)
  safe_answer(cb)  — await, глотает ошибки

⚠️ Не вызывай пустой fire_answer()/answer() ПЕРЕД show_alert=True:
Telegram принимает только один answer. Пустой ответ «съест» алерт.

Мэджик гасит спиннер сам в finally, если handler ничего не ответил.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from aiogram.types import CallbackQuery


async def safe_answer(
    cb: CallbackQuery,
    text: str = "",
    *,
    show_alert: bool = False,
    cache_time: Optional[int] = None,
) -> None:
    try:
        kwargs: Dict[str, Any] = {}
        if text:
            kwargs["text"] = text
            kwargs["show_alert"] = bool(show_alert)
        if cache_time is not None:
            kwargs["cache_time"] = int(cache_time)
        await cb.answer(**kwargs)
    except Exception:
        pass


def fire_answer(
    cb: CallbackQuery,
    text: str = "",
    *,
    show_alert: bool = False,
    cache_time: Optional[int] = None,
) -> None:
    """Не блокирует handler на RTT AnswerCallbackQuery."""
    try:
        asyncio.create_task(
            safe_answer(cb, text, show_alert=show_alert, cache_time=cache_time)
        )
    except Exception:
        pass
