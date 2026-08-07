"""Запуск admin- и support-ботов с одним пулом БД.

Graceful shutdown по SIGTERM критичен для DigitalOcean: без него старый
worker продолжает держать getUpdates, пока новый уже стартовал →
TelegramConflictError и экспоненциальный backoff в логах деплоя.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from config import ADMIN_BOT_TOKEN, ADMIN_ENABLED, SUPPORT_BOT_TOKEN
from admin_bot import run_admin_bot
from support_bot import run_support_bot
from db import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cute-farm.bots")


def _boot(msg: str) -> None:
    """Ранний маркер старта — виден в farm-bots.log для start-all.ps1."""
    line = f"[FARM-BOTS] {msg}"
    print(line, flush=True)
    logger.info(msg)


async def _run_with_network_retry(label: str, factory, *, attempts: int = 6):
    """Старт admin/support с повтором на сетевых таймаутах (Windows WinError 121)."""
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            await factory()
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_exc = exc
            name = type(exc).__name__
            msg = str(exc)
            transient = any(
                needle in msg.lower()
                for needle in (
                    "timeout",
                    "semaphore",
                    "cannot connect",
                    "clientconnector",
                    "temporary failure",
                    "name or service not known",
                    "network",
                )
            ) or name in {"ClientConnectorError", "TelegramNetworkError", "TimeoutError"}
            if not transient or attempt >= attempts:
                raise
            delay = min(30.0, 2.0 * attempt)
            logger.warning(
                "%s: сеть недоступна (%s: %s) — повтор %d/%d через %.0fs",
                label, name, msg, attempt, attempts, delay,
            )
            await asyncio.sleep(delay)
    if last_exc is not None:
        raise last_exc


async def main() -> None:
    # BOT_TOKEN == TOKEN у cutebot (main.py) — это один и тот же бот.
    # cutebot уже поллит и уже выставляет кнопку меню WebApp через
    # существующий bot1, поэтому здесь мы вообще не создаём Bot(BOT_TOKEN) —
    # ни поллинга, ни разовых вызовов. Компонент bots отвечает только за
    # admin_bot/support_bot (свои отдельные токены).
    _boot("starting admin + support bots...")
    await db.ensure_connected()
    _boot("database ready — launching pollers...")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop(signame: str = "signal") -> None:
        if not stop.is_set():
            _boot(f"shutdown requested ({signame})")
            stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _request_stop, sig.name)
        except (NotImplementedError, RuntimeError, AttributeError):
            # Windows / окружения без add_signal_handler
            try:
                signal.signal(sig, lambda *_: _request_stop("signal"))
            except Exception:
                pass

    coros = []
    labels = []
    if ADMIN_ENABLED and ADMIN_BOT_TOKEN:
        coros.append(lambda: _run_with_network_retry("admin-bot", run_admin_bot))
        labels.append("admin")
    else:
        logger.warning(
            "Admin bot не запущен — задай ADMIN_ENABLED=true и ADMIN_BOT_TOKEN в .env"
        )
    if SUPPORT_BOT_TOKEN:
        coros.append(lambda: _run_with_network_retry("support-bot", run_support_bot))
        labels.append("support")
    else:
        logger.warning("Support bot не запущен — задай SUPPORT_BOT_TOKEN в .env")

    if not coros:
        logger.warning(
            "Нет активных пойлеров (admin_bot/support_bot не заданы) — процесс остаётся жив"
        )
        await stop.wait()
        await db.close()
        return

    tasks = [
        asyncio.create_task(factory(), name=f"bot-{label}")
        for factory, label in zip(coros, labels)
    ]
    stopper = asyncio.create_task(stop.wait(), name="stop-waiter")
    _boot(f"pollers starting ({len(tasks)} bot(s))...")

    try:
        done, _pending = await asyncio.wait(
            {*tasks, stopper},
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Если один из ботов упал сам — поднимаем исключение после отмены остальных.
        for t in done:
            if t is stopper or t.cancelled():
                continue
            exc = t.exception()
            if exc is not None:
                logger.error("poller crashed: %s", exc)
                raise exc
    finally:
        _boot("stopping pollers...")
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        stopper.cancel()
        await asyncio.gather(stopper, return_exceptions=True)
        await db.close()
        _boot("stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _boot("stopped by user")
        sys.exit(0)
