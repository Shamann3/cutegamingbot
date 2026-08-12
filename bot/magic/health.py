# -*- coding: utf-8 -*-
"""
Самолечение Мэджик при долгом аптайме и наплыве.

Что делает каждые HEALTH_INTERVAL_SEC (см. config.py):
  • trim() лимитов — idle-пользователи, cooldown, stale inflight
  • force_recover при лаге / переполнении inflight
  • trim balance_watcher (если привязан)
  • trim softfail-кэша TG-логгера
  • редкий rebind InlineKeyboard* (не каждый цикл — иначе loop «замирает»)
  • при лаге loop — включает quiet_mode у TG-логгера

Интервал и пороги lag читаются из magic.cfg на каждом круге,
поэтому magic.tune(health_interval_sec=120) подхватывается без рестарта.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.magic.core import Magic

logger = logging.getLogger("magic")

if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(
        logging.Formatter("[MAGIC %(asctime)s] %(message)s", "%d.%m.%Y %H:%M:%S")
    )
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)
    logger.propagate = False


async def magic_health_loop(
    magic: "Magic",
    *,
    interval_sec: float | None = None,
    lag_sample_sec: float | None = None,
    lag_warn_sec: float | None = None,
) -> None:
    """
    Фоновый цикл самолечения.

    Если interval_sec/lag_* не переданы — берутся из magic.cfg
    (и могут меняться на лету через magic.tune).
    """
    if magic._health_started:
        logger.info("health already running")
        return
    magic._health_started = True

    cfg = magic.cfg
    start_interval = float(
        interval_sec if interval_sec is not None else cfg.health_interval_sec
    )
    logger.info(
        "HEALTH START interval=%.0fs mode=%s rebind_every=%s stale=%.0fs",
        start_interval,
        cfg.mode,
        getattr(cfg, "health_rebind_every_n", 20),
        getattr(cfg, "inflight_stale_sec", 45.0),
    )

    while True:
        # каждый круг читаем актуальный конфиг (tune на лету)
        cfg = magic.cfg
        sleep_for = float(
            interval_sec if interval_sec is not None else cfg.health_interval_sec
        )
        sample = float(
            lag_sample_sec
            if lag_sample_sec is not None
            else cfg.health_lag_sample_sec
        )
        warn = float(
            lag_warn_sec if lag_warn_sec is not None else cfg.health_lag_warn_sec
        )

        try:
            await asyncio.sleep(max(5.0, sleep_for))
        except asyncio.CancelledError:
            raise

        try:
            lag = await _measure_loop_lag(sample)
        except Exception:
            lag = -1.0

        snap_before = magic.snapshot()
        need_force = (
            lag >= warn
            or snap_before.get("inflight", 0) > int(cfg.health_inflight_warn)
        )

        healed = {}
        try:
            # rebind решим внутри heal_once по счётчику тиков
            healed = magic.heal_once(force=need_force)
        except Exception as e:
            logger.warning("heal err: %r", e)

        # при сильном лаге — ещё раз жёстко восстановить (кнопки)
        if need_force:
            try:
                healed["force2"] = magic.force_recover()
            except Exception as e:
                healed["force2_err"] = repr(e)

        try:
            from bot.utils import telegram_api_logger as tg_log

            if lag >= warn and hasattr(tg_log, "set_quiet_mode"):
                tg_log.set_quiet_mode(True, reason=f"magic_lag={lag:.3f}s")
            elif lag >= 0 and lag < warn * 0.5 and hasattr(tg_log, "set_quiet_mode"):
                tg_log.set_quiet_mode(False)
        except Exception:
            pass

        try:
            pending = len([t for t in asyncio.all_tasks() if not t.done()])
        except Exception:
            pending = -1

        snap = magic.snapshot()
        if (
            lag >= warn
            or pending > int(cfg.health_pending_warn)
            or snap.get("inflight", 0) > int(cfg.health_inflight_warn)
        ):
            logger.warning(
                "HEAL lag=%.3fs pending=%s snap=%s healed=%s",
                lag,
                pending,
                snap,
                healed,
            )
        else:
            logger.info(
                "OK lag=%.3fs pending=%s mode=%s callbacks=%s blocked=%s inflight=%s stale=%s",
                lag,
                pending,
                cfg.mode,
                snap.get("callbacks"),
                snap.get("blocked_total"),
                snap.get("inflight"),
                snap.get("stale_inflight_total"),
            )


async def _measure_loop_lag(sample_sec: float) -> float:
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    await asyncio.sleep(sample_sec)
    return max(0.0, (loop.time() - t0) - sample_sec)
