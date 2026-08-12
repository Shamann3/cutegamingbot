# -*- coding: utf-8 -*-
"""
Middleware Мэджик: единственная входная точка всех callback_query.

Что делает (по порядку):
  1) Проверяет лимиты (антиспам / debounce / cooldown / inflight)
  2) Если клик заблокирован — тихо гасит «часики» (без текста)
  3) Пропускает handler; answer идемпотентен (второй вызов безопасен)
  4) НЕ отвечает заранее пустым answer — иначе show_alert из игр пропадает
     (Telegram разрешает только ОДИН answer на callback)
  5) После handler: если сам не ответил — гасит спиннер в finally
  6) Страховка STUCK_ANSWER_DELAY_SEC — если handler завис

Ставится как outer_middleware — ловит АБСОЛЮТНО ВСЕ callback_query.

Настройки: bot/magic/config.py
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, TYPE_CHECKING

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject

if TYPE_CHECKING:
    from bot.magic.core import Magic

logger = logging.getLogger("magic")


def _wants_user_feedback(*args: Any, **kwargs: Any) -> bool:
    """Handler хочет показать текст/alert пользователю?"""
    if kwargs.get("show_alert"):
        return True
    text = kwargs.get("text")
    if text is None and args:
        text = args[0]
    return bool(text)


class MagicCallbackMiddleware(BaseMiddleware):
    """Все inline-кнопки проходят через эту цепь."""

    def __init__(self, magic: "Magic"):
        super().__init__()
        self.magic = magic

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)

        m = self.magic
        cfg = m.cfg

        try:
            m.stats_callbacks += 1
            uid = int(event.from_user.id) if event.from_user else 0
            cdata = str(event.data or "")

            ok, reason = m.limits.allow(uid, cdata)
            if not ok:
                m.stats_blocked += 1
                if cfg.silent_block:
                    try:
                        await event.answer()
                    except Exception:
                        pass
                return None
        except Exception as e_lim:
            logger.warning("limits err (pass-through): %r", e_lim)

        # Состояние ответа: Telegram принимает answer только один раз.
        # Поэтому Мэджик НЕ гасит спиннер пустым answer до handler —
        # иначе пропадают show_alert / тексты ошибок во всех играх.
        state = {
            "answered": False,
            "had_feedback": False,  # был текст или show_alert
        }
        original_answer = event.answer

        async def answer_once(*args: Any, **kwargs: Any) -> bool:
            feedback = _wants_user_feedback(*args, **kwargs)
            if state["answered"]:
                # Поздний show_alert после пустого answer уже невозможен в TG.
                # Логируем — чтобы такие гонки было видно в логах.
                if feedback and not state["had_feedback"]:
                    logger.warning(
                        "answer with alert/text skipped: callback already answered "
                        "(text=%r show_alert=%r)",
                        kwargs.get("text") if "text" in kwargs else (args[0] if args else ""),
                        kwargs.get("show_alert"),
                    )
                return True
            state["answered"] = True
            if feedback:
                state["had_feedback"] = True
            try:
                return await original_answer(*args, **kwargs)
            except Exception:
                return True

        patched = False
        try:
            object.__setattr__(event, "answer", answer_once)
            patched = True
        except Exception:
            try:
                event.answer = answer_once  # type: ignore[method-assign]
                patched = True
            except Exception:
                patched = False

        # Ранний auto-answer только если явно включён в config (> 0).
        # По умолчанию 0 — чтобы show_alert работал везде.
        early = float(getattr(cfg, "auto_answer_delay_sec", 0.0) or 0.0)
        stuck = float(getattr(cfg, "stuck_answer_delay_sec", 8.0) or 0.0)
        # Какой таймер запускать: early (если >0) иначе stuck-страховка
        delay = early if early > 0 else stuck

        async def _delayed_empty_answer(wait: float) -> None:
            try:
                await asyncio.sleep(wait)
                if state["answered"]:
                    return
                if patched:
                    await answer_once()
                else:
                    try:
                        await original_answer()
                        state["answered"] = True
                    except Exception:
                        state["answered"] = True
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

        auto_task: asyncio.Task | None = None
        if delay > 0:
            auto_task = asyncio.create_task(_delayed_empty_answer(delay))

        inflight_token: int | None = None
        try:
            try:
                inflight_token = m.limits.enter()
            except Exception:
                inflight_token = None
            data["magic"] = m
            return await handler(event, data)
        finally:
            if inflight_token is not None:
                try:
                    m.limits.leave(inflight_token)
                except Exception:
                    pass
            try:
                # Handler закончился — если сам не ответил, гасим часики сейчас
                # (это не мешает show_alert: handler уже имел шанс ответить).
                if not state["answered"]:
                    if auto_task is not None and not auto_task.done():
                        auto_task.cancel()
                    if patched:
                        await answer_once()
                    else:
                        try:
                            await original_answer()
                        except Exception:
                            pass
                elif auto_task is not None and not auto_task.done():
                    auto_task.cancel()
            except Exception:
                pass
            # не копить отменённые tasks на долгом аптайме
            if auto_task is not None and auto_task.done():
                try:
                    auto_task.exception()
                except (asyncio.CancelledError, Exception):
                    pass
