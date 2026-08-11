# -*- coding: utf-8 -*-
"""Совместимость: самолечение кнопок теперь внутри Мэджик."""
from __future__ import annotations

from typing import Any

from bot.magic.health import magic_health_loop
from bot.magic.core import magic


async def button_health_loop(
    *,
    balance_watcher: Any = None,
    interval_sec: float = 300.0,
    lag_sample_sec: float = 0.25,
    lag_warn_sec: float = 0.35,
) -> None:
    if balance_watcher is not None:
        magic.attach_balance_watcher(balance_watcher)
    await magic_health_loop(
        magic,
        interval_sec=interval_sec,
        lag_sample_sec=lag_sample_sec,
        lag_warn_sec=lag_warn_sec,
    )
