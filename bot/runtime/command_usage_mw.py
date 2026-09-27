"""Middleware: учёт вызовов команд CuteGamingBot без блокировки хендлеров."""

from __future__ import annotations

from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class BotCommandUsageMiddleware(BaseMiddleware):
    """outer_middleware: +1 в буфер счётчика при команде / callback."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            from bot.runtime.bot_command_stats import is_bot_command_message, note_bot_command

            if isinstance(event, Message):
                if is_bot_command_message(event):
                    note_bot_command(1)
            elif isinstance(event, CallbackQuery):
                # Нажатие inline-кнопки бота = вызов функции
                if getattr(event, "data", None):
                    note_bot_command(1)
        except Exception:
            pass
        return await handler(event, data)


def attach_bot_command_usage(dp) -> None:
    try:
        dp.message.outer_middleware(BotCommandUsageMiddleware())
        dp.callback_query.outer_middleware(BotCommandUsageMiddleware())
        print("✅ [CMD-STATS] usage middleware attached", flush=True)
    except Exception as e:
        print(f"⚠️ [CMD-STATS] attach failed: {e!r}", flush=True)
