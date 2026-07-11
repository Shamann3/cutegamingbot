import logging
import time

from aiohttp import ClientSession, ClientTimeout

logger = logging.getLogger("telegram_http")

if not logger.handlers:
    handler = logging.FileHandler("/app/log_telegram_http.txt", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s %(message)s",
            "%d.%m.%Y %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class LoggedClientSession(ClientSession):
    async def _request(self, method, url, **kwargs):
        started = time.perf_counter()

        logger.info("➡ %s %s", method, url)

        try:
            response = await super()._request(method, url, **kwargs)

            elapsed = (time.perf_counter() - started) * 1000

            logger.info(
                "✅ %s %s -> %s %.2f ms",
                method,
                url,
                response.status,
                elapsed,
            )

            return response

        except Exception:
            elapsed = (time.perf_counter() - started) * 1000

            logger.exception(
                "❌ %s %s %.2f ms",
                method,
                url,
                elapsed,
            )

            raise


def create_logged_session(timeout=120):
    return LoggedClientSession(
        timeout=ClientTimeout(total=timeout)
    )