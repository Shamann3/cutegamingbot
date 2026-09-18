# -*- coding: utf-8 -*-
"""Фоновый цикл Ники. Переживает ошибки и не умирает до остановки процесса."""

from __future__ import annotations

import asyncio

from bot.runtime.nika.engine import run_tick
from bot.runtime.nika.schema import ensure_nika_schema

_STARTED = False
_MIN_SLEEP = 15
_MAX_SLEEP = 180


def start_nika_worker(db, bot) -> None:
    global _STARTED
    if _STARTED:
        return
    _STARTED = True

    async def _loop() -> None:
        sleep_for = 30
        while True:
            try:
                summary = await run_tick(db, bot)
                if summary.get("ok"):
                    sleep_for = 30
                    if summary.get("error") in ("skipped", "disabled"):
                        sleep_for = 15
                    if int((summary.get("commands") or {}).get("processed") or 0) > 0:
                        sleep_for = 8
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
    print("[NIKA] worker started (tick ~3 min, heal+commands on every wake)")
