# -*- coding: utf-8 -*-
"""Фоновый цикл Ники. Переживает ошибки и не умирает до остановки процесса."""

from __future__ import annotations

import asyncio

from bot.runtime.nika.engine import run_tick
from bot.runtime.nika.schema import ensure_nika_schema

_STARTED = False
_MIN_SLEEP = 8
_MAX_SLEEP = 180


def _tick_sleep(summary: dict) -> int:
    tick = int((summary or {}).get("tick_interval_sec") or 20)
    if tick < _MIN_SLEEP:
        tick = _MIN_SLEEP
    if tick > _MAX_SLEEP:
        tick = _MAX_SLEEP
    if (summary or {}).get("error") in ("skipped", "disabled"):
        return min(tick, 12)
    if int(((summary or {}).get("commands") or {}).get("processed") or 0) > 0:
        return min(tick, 8)
    return tick


def start_nika_worker(db, bot) -> None:
    global _STARTED
    if _STARTED:
        return
    _STARTED = True

    async def _loop() -> None:
        sleep_for = 12
        while True:
            try:
                summary = await run_tick(db, bot)
                if summary.get("ok"):
                    sleep_for = _tick_sleep(summary)
                else:
                    sleep_for = min(_MAX_SLEEP, max(_MIN_SLEEP, sleep_for * 2))
                    print(f"[NIKA][LOOP] tick not ok: {summary.get('error')}; retry in {sleep_for}s")
                    try:
                        await ensure_nika_schema(db)
                    except Exception as heal_exc:
                        print(f"[NIKA][LOOP] schema heal: {type(heal_exc).__name__}: {heal_exc}")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                sleep_for = min(_MAX_SLEEP, max(_MIN_SLEEP, sleep_for * 2))
                print(f"[NIKA][LOOP] {type(exc).__name__}: {exc}; retry in {sleep_for}s")
                try:
                    await ensure_nika_schema(db)
                except Exception as heal_exc:
                    print(f"[NIKA][LOOP] schema heal: {type(heal_exc).__name__}: {heal_exc}")
            await asyncio.sleep(sleep_for)

    asyncio.create_task(_loop())
    print("[NIKA] worker started (sweep follows creator speed, heal+commands on every wake)")
