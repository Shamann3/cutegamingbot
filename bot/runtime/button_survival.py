# -*- coding: utf-8 -*-
"""Тонкая обёртка над Button Lifecycle (обратная совместимость).

Вся логика — в bot.runtime.button_lifecycle.
Этот модуль оставлен, чтобы старые import'ы (soft_restart, main) не ломались.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict


def protect_before_restart(*, wait_timeout: float = 12.0) -> Dict[str, Any]:
    from bot.runtime.button_lifecycle import protect_before_restart as _p

    return _p(wait_timeout=wait_timeout)


def protect_after_start(*, reason: str = "boot", adopt: bool = True) -> Dict[str, Any]:
    from bot.runtime.button_lifecycle import protect_after_start as _p

    return _p(reason=reason, adopt=adopt)


async def protect_after_start_async(
    *,
    reason: str = "boot",
    adopt: bool = True,
    revive_magic: bool = True,
    dp: Any = None,
    bot: Any = None,
    raise_markups: bool = True,
) -> Dict[str, Any]:
    from bot.runtime.button_lifecycle import protect_after_start_async as _p

    # bot можно не передать — попробуем достать из dp / main
    if bot is None:
        try:
            import main as M

            bot = getattr(M, "bot1", None)
        except Exception:
            bot = None

    return await _p(
        bot=bot,
        dp=dp,
        reason=reason,
        adopt=adopt,
        revive_magic=revive_magic,
        raise_markups=raise_markups,
    )


def persist_callback_store(store: Any) -> None:
    from bot.runtime.button_lifecycle import persist_callback_store as _p

    _p(store)
