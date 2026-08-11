# -*- coding: utf-8 -*-
"""
Middleware Мэджик для Telegram INLINE MODE (@бот запрос).

Зачем:
  • чтобы inline-режим не «висел» при долгом аптайме / тяжёлом handler;
  • таймаут — Telegram ждёт ответ на inline_query считанные секунды;
  • антифлуд тех же лимитов Мэджик;
  • при timeout/ошибке всегда закрываем query.

Не путать с inline-кнопками (callback_query) — они в middleware.py.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, TYPE_CHECKING

from aiogram import BaseMiddleware, Bot
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    TelegramObject,
)

if TYPE_CHECKING:
    from bot.magic.core import Magic

logger = logging.getLogger("magic")


def _timeout_result() -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id=f"magic_iq_timeout_{int(time.time()) % 10_000_000}",
        title="⏳ Подождите секунду…",
        description="Бот занят, повторите запрос",
        input_message_content=InputTextMessageContent(
            message_text="⏳ Бот сейчас занят. Откройте inline ещё раз через секунду."
        ),
    )


async def _safe_answer_iq(
    bot: Bot,
    query_id: str,
    *,
    results: Optional[List[Any]] = None,
    cache_time: int = 1,
) -> bool:
    try:
        await bot.answer_inline_query(
            inline_query_id=query_id,
            results=list(results or []),
            cache_time=int(cache_time),
            is_personal=True,
        )
        return True
    except Exception:
        return False


class MagicInlineQueryMiddleware(BaseMiddleware):
    """Защита всех @dp.inline_query хендлеров."""

    def __init__(self, magic: "Magic"):
        super().__init__()
        self.magic = magic

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, InlineQuery):
            return await handler(event, data)

        m = self.magic
        cfg = m.cfg
        m.stats_inline_queries = getattr(m, "stats_inline_queries", 0) + 1

        bot: Optional[Bot] = data.get("bot")
        uid = int(event.from_user.id) if event.from_user else 0
        q = str(event.query or "")[:64]

        try:
            ok, _reason = m.limits.allow(uid, f"iq:{q or '_'}")
        except Exception:
            ok = True

        if not ok:
            m.stats_inline_blocked = getattr(m, "stats_inline_blocked", 0) + 1
            if bot is not None:
                await _safe_answer_iq(bot, event.id, results=[], cache_time=1)
            return None

        timeout = float(getattr(cfg, "inline_query_timeout_sec", 4.5) or 4.5)
        protect = bool(getattr(cfg, "inline_query_protect", True))

        try:
            if protect and timeout > 0:
                result = await asyncio.wait_for(handler(event, data), timeout=timeout)
            else:
                result = await handler(event, data)

            # Если handler вернулcя, но забыл answer — через 150мс мягко закроем.
            # Если уже ответил — Telegram отклонит второй answer (это ок).
            if bot is not None:
                async def _soft_close() -> None:
                    try:
                        await asyncio.sleep(0.15)
                        await _safe_answer_iq(bot, event.id, results=[], cache_time=1)
                    except Exception:
                        pass

                try:
                    asyncio.create_task(_soft_close())
                except Exception:
                    pass
            return result

        except asyncio.TimeoutError:
            m.stats_inline_timeouts = getattr(m, "stats_inline_timeouts", 0) + 1
            logger.warning(
                "inline_query timeout uid=%s q=%r after %.1fs",
                uid,
                q,
                timeout,
            )
            if bot is not None:
                await _safe_answer_iq(
                    bot,
                    event.id,
                    results=[_timeout_result()],
                    cache_time=1,
                )
            return None

        except Exception as e:
            logger.warning("inline_query err uid=%s: %r", uid, e)
            if bot is not None:
                await _safe_answer_iq(bot, event.id, results=[], cache_time=1)
            raise
