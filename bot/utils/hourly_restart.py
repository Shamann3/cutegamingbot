"""Плановый авто-рестарт контейнера раз в час.

DO App Platform не умеет рестарт по расписанию, но worker-компонент
перезапускается автоматически, когда его процесс завершается. Поэтому здесь
отдельный поток-демон спит заданный интервал и вызывает os._exit(0) —
платформа поднимает контейнер заново (~20–30с).

Настройки через env:
    HOURLY_RESTART_ENABLED   (default 1)
    HOURLY_RESTART_INTERVAL_SEC   (default 3600 = 1 час)
"""
import os
import sys
import threading
import time


def start_hourly_restart() -> None:
    if os.getenv("HOURLY_RESTART_ENABLED", "1") not in ("1", "true", "yes", "on"):
        print("[HOURLY_RESTART] выключен (HOURLY_RESTART_ENABLED)", flush=True)
        return

    try:
        interval_sec = int(os.getenv("HOURLY_RESTART_INTERVAL_SEC", "3600"))
    except ValueError:
        interval_sec = 3600
    if interval_sec <= 0:
        print("[HOURLY_RESTART] выключен (HOURLY_RESTART_INTERVAL_SEC <= 0)", flush=True)
        return

    def _run():
        while True:
            print(
                f"[HOURLY_RESTART] следующий плановый рестарт через {interval_sec / 60:.1f} мин",
                flush=True,
            )
            # Спим кусками по ≤5 мин вместо одного длинного time.sleep —
            # устойчивее к возможным будущим изменениям интервала на лету
            # и не даёт потоку «зависнуть» одним неразрывным вызовом.
            remaining = interval_sec
            while remaining > 0:
                time.sleep(min(remaining, 300.0))
                remaining -= 300.0
            print(
                "[HOURLY_RESTART] плановый выход, App Platform перезапустит контейнер",
                flush=True,
            )
            sys.stdout.flush()
            os._exit(0)

    threading.Thread(target=_run, daemon=True, name="hourly-restart").start()
    print(
        f"[HOURLY_RESTART] ✅ запланирован рестарт каждые {interval_sec} сек "
        f"(~{interval_sec / 3600:.2f} ч)",
        flush=True,
    )
