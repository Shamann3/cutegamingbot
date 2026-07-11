import asyncio
import logging
import sys
import threading
import time
import traceback

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


# Последний «тик» асинхронного монитора. Обновляется из loop.
# Отдельный поток-сторож сравнивает его с реальным временем: если loop
# завис (тик не обновляется), поток снимает стек ГЛАВНОГО потока —
# так видно, какая именно синхронная функция блокирует процесс.
_last_tick = [time.monotonic()]


def _watchdog(stall_threshold: float):
    main_id = threading.main_thread().ident
    dumped = False
    while True:
        time.sleep(1.0)
        stalled = time.monotonic() - _last_tick[0]

        if stalled >= stall_threshold and not dumped:
            frame = sys._current_frames().get(main_id)
            if frame is not None:
                stack = "".join(traceback.format_stack(frame))
                logger.warning(
                    "[STALL %.1fs] главный поток застрял здесь:\n%s",
                    stalled,
                    stack,
                )
            dumped = True
        elif stalled < stall_threshold:
            dumped = False


async def monitor_event_loop(
    interval: float = 0.2,
    warn_delay: float = 0.5,
    stall_threshold: float = 3.0,
):
    """
    interval - как часто проверять цикл.
    warn_delay - задержка, после которой писать [BLOCK].
    stall_threshold - при зависании дольше этого поток-сторож снимет стек.
    """

    loop = asyncio.get_running_loop()

    # Поток-сторож: работает даже когда loop полностью заморожен.
    threading.Thread(
        target=_watchdog,
        args=(stall_threshold,),
        daemon=True,
        name="loop-watchdog",
    ).start()

    logger.info(
        "[START] interval=%.3fs warn_delay=%.3fs stall_threshold=%.1fs",
        interval,
        warn_delay,
        stall_threshold,
    )

    next_time = loop.time() + interval

    while True:
        await asyncio.sleep(interval)

        _last_tick[0] = time.monotonic()

        now = loop.time()

        delay = now - next_time

        if delay >= warn_delay:
            logger.warning(
                "[BLOCK] EventLoop blocked %.3f sec",
                delay,
            )

        next_time = now + interval
