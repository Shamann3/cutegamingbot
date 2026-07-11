import logging
import sys
import time

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods import TelegramMethod

logger = logging.getLogger("telegram_api")

if not logger.handlers:
    formatter = logging.Formatter(
        "[TG-API %(asctime)s] %(levelname)s %(message)s",
        "%d.%m.%Y %H:%M:%S"
    )

    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler("/app/log_telegram_api.txt", encoding="utf-8"))
    except OSError:
        pass

    for h in handlers:
        h.setFormatter(formatter)
        logger.addHandler(h)

    logger.setLevel(logging.INFO)
    logger.propagate = False


# Служебные методы long-polling — не логируем (только шум).
_SKIP_METHODS = {"GetUpdates", "GetMe"}


class TelegramApiLogger(BaseRequestMiddleware):

    async def __call__(self, make_request, bot, method: TelegramMethod):
        method_name = method.__class__.__name__

        if method_name in _SKIP_METHODS:
            return await make_request(bot, method)

        started = time.perf_counter()

        logger.info(
            "➡ START %-28s",
            method_name
        )

        try:
            result = await make_request(bot, method)

            elapsed = (time.perf_counter() - started) * 1000

            logger.info(
                "✅ END   %-28s %.2f ms",
                method_name,
                elapsed
            )

            return result

        except Exception as e:
            elapsed = (time.perf_counter() - started) * 1000

            logger.exception(
                "❌ FAIL  %-28s %.2f ms %s",
                method_name,
                elapsed,
                repr(e)
            )

            raise