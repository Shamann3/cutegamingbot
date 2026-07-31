"""Общий запуск long-polling для admin/support ботов.

На DigitalOcean App Platform во время rolling-деплоя старый и новый
worker короткое время живут вместе. Telegram допускает только один
активный getUpdates на токен — отсюда Conflict и «вечный» backoff
в логах, из-за которого деплой кажется сломанным/долгим.

Порядок старта:
  1. опциональная пауза (BOT_POLLING_START_DELAY) — даём старому
     инстансу получить SIGTERM и закрыть сессию;
  2. delete_webhook — снимаем забытый webhook, если когда-то ставили;
  3. start_polling(drop_pending_updates=True) — чистый захват очереди.

Сигналы (SIGTERM) обрабатывает bots_runner, поэтому здесь
handle_signals=False — иначе два слоя ловят один и тот же сигнал.
"""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher

logger = logging.getLogger("cute-farm.bot-polling")


def _start_delay_sec() -> float:
    raw = os.getenv("BOT_POLLING_START_DELAY", "8")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 8.0


async def prepare_polling(bot: Bot, *, label: str) -> None:
    """Пауза + снятие webhook перед первым getUpdates."""
    delay = _start_delay_sec()
    if delay > 0:
        logger.info("%s: ждём %.0fs перед polling (отпускаем предыдущий инстанс)", label, delay)
        await asyncio.sleep(delay)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("%s: webhook снят, очередь очищена", label)
    except Exception:
        logger.exception("%s: delete_webhook не удался — продолжаем polling", label)


async def run_polling(
    dp: Dispatcher,
    bot: Bot,
    *,
    label: str,
    allowed_updates: list[str] | None = None,
) -> None:
    """Единая точка входа в long-polling с корректным закрытием сессии."""
    await prepare_polling(bot, label=label)
    try:
        kwargs: dict = {
            "drop_pending_updates": True,
            "handle_signals": False,
            "close_bot_session": False,  # сессию закрываем сами в finally
        }
        if allowed_updates is not None:
            kwargs["allowed_updates"] = allowed_updates
        logger.info("%s: start_polling", label)
        await dp.start_polling(bot, **kwargs)
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass
        logger.info("%s: session closed", label)
