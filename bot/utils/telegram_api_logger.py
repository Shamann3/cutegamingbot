import logging
import time

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods import TelegramMethod

logger = logging.getLogger("telegram_api")

if not logger.handlers:
    handler = logging.FileHandler("/app/log_telegram_api.txt", encoding="utf-8")

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(message)s",
        "%d.%m.%Y %H:%M:%S"
    )

    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class TelegramApiLogger(BaseRequestMiddleware):

    async def __call__(self, make_request, bot, method: TelegramMethod):
        started = time.perf_counter()

        method_name = method.__class__.__name__

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