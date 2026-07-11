import asyncio
import logging
import sys
import time

logger = logging.getLogger("event_loop")

if not logger.handlers:
    formatter = logging.Formatter(
        "[EVENTLOOP %(asctime)s] %(message)s",
        "%d.%m.%Y %H:%M:%S"
    )

    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler("/app/log_event_loop.txt", encoding="utf-8"))
    except OSError:
        pass

    for h in handlers:
        h.setFormatter(formatter)
        logger.addHandler(h)

    logger.setLevel(logging.INFO)
    logger.propagate = False


async def monitor_event_loop(
    interval: float = 0.2,
    warn_delay: float = 0.5,
):
    """
    interval - как часто проверять цикл.
    warn_delay - задержка, после которой писать предупреждение.
    """

    loop = asyncio.get_running_loop()

    logger.info(
        "[START] interval=%.3fs warn_delay=%.3fs",
        interval,
        warn_delay,
    )

    next_time = loop.time() + interval

    while True:
        await asyncio.sleep(interval)

        now = loop.time()

        delay = now - next_time

        if delay >= warn_delay:
            logger.warning(
                "[BLOCK] EventLoop blocked %.3f sec",
                delay,
            )

        next_time = now + interval