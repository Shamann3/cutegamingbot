"""Плановый ежедневный авто-рестарт контейнера.

DO App Platform не умеет рестарт по расписанию, но worker-компонент
перезапускается автоматически, когда его процесс завершается. Поэтому здесь
отдельный поток-демон спит до заданного времени и вызывает os._exit(0)
платформа поднимает контейнер заново (~20–30с).

Время задаётся в МСК (UTC+3). Контейнер живёт в UTC.
Настройки через env:
    DAILY_RESTART_ENABLED   (default 1)
    DAILY_RESTART_MSK_HOUR  (default 3)
    DAILY_RESTART_MSK_MIN   (default 0)
"""
import os
import sys
import threading
import time
from datetime import datetime, timezone, timedelta


def _seconds_until(hour_utc: int, minute_utc: int) -> float:
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hour_utc, minute=minute_utc, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def start_daily_restart() -> None:
    if os.getenv("DAILY_RESTART_ENABLED", "1") not in ("1", "true", "yes", "on"):
        print("[DAILY_RESTART] выключен (DAILY_RESTART_ENABLED)", flush=True)
        return

    try:
        hour_msk = int(os.getenv("DAILY_RESTART_MSK_HOUR", "3"))
        minute = int(os.getenv("DAILY_RESTART_MSK_MIN", "0"))
    except ValueError:
        hour_msk, minute = 3, 0

    hour_utc = (hour_msk - 3) % 24  # МСК = UTC+3

    def _run():
        announced = False
        while True:
            secs = _seconds_until(hour_utc, minute)
            if not announced:
                print(
                    f"[DAILY_RESTART] следующий плановый рестарт через {secs/3600:.2f} ч "
                    f"(в {hour_msk:02d}:{minute:02d} МСК)",
                    flush=True,
                )
                announced = True
            if secs <= 1:
                print(
                    f"[DAILY_RESTART] {hour_msk:02d}:{minute:02d} МСК плановый выход, "
                    f"App Platform перезапустит контейнер",
                    flush=True,
                )
                sys.stdout.flush()
                os._exit(0)
            # Спим кусками по ≤5 мин и пересчитываем (устойчиво к сдвигам часов).
            time.sleep(min(secs, 300.0))

    threading.Thread(target=_run, daemon=True, name="daily-restart").start()
    print(
        f"[DAILY_RESTART] ✅ запланирован ежедневный рестарт в "
        f"{hour_msk:02d}:{minute:02d} МСК ({hour_utc:02d}:{minute:02d} UTC)",
        flush=True,
    )
