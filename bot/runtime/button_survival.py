# -*- coding: utf-8 -*-
"""Защита inline-кнопок от перезапусков (text-бот + inline-режим).

Telegram хранит клавиатуру на сообщении. Сессии/токены — в pkl→Redis.

Важно:
  • write-through только для ТОКЕНОВ и inline-игр, flush в IO-потоке
    (sync flush в event-loop вешает бота — кнопки «не работают»);
  • перед выходом — полный flush;
  • после handoff — adopt из Redis.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Set

logger = logging.getLogger("button_survival")

# Только то, без чего кнопка гарантированно «устарела» после рестарта
_CALLBACK_TOKEN_STORES: Set[str] = {
    "PREP_CALLBACK_ACTIONS",
    "GIFT_CALLBACK_ACTIONS",
    "SKIP_CALLBACK_ACTIONS",
    "SPEEDCONC_CALLBACK_ACTIONS",
    "SEND_REQUEST_ACTIONS",
    # опции вывода «От бота» (описание/скрытие) — иначе кнопки мёртвые после .r
    "session_data",
    "user_to_session",
}

_INLINE_GAME_STORES: Set[str] = {
    "gamesorelinline",
    "button_inlinegamesorel",
    "gamesmine_inmine",
    "games_memory_inline",
    "rps_games",
    "inline_game_scah",
    "tic_tac_toe_games",
    "game_roulettinduel",
}

# Основные text-игры (write-through через IO-thread, без массового prefix)
_TEXT_GAME_STORES: Set[str] = {
    "gamesorel",
    "button_gamesorel",
    "gamessha",
    "button_gamessha",
    "gamesmine",
    "button_gamesmine",
    "gamesbingo",
    "button_bingo",
    "games_memory",
    "button_memory",
    "gamesknb",
    "button_gamesknb",
    "games_roulett",
    "button_roulett",
    "gamesruletka",
    "button_gamesruletka",
    "gameskosti",
    "button_kosti",
    "games_tictactoe",
    "button_games_tictactoe",
    "tank_active_games",
    "button_tank_active_games",
    "user_messagetank",
    "active_games_plate",
    "button_active_games_plate",
    "user_message_plate",
    "active_games_risk",
    "button_active_games_risk",
    "user_message_risk",
    "bombs_user_game_data",
    "button_bombs_user_game_data",
    "SEND_REQUEST_ACTIONS",
}


def _critical_names() -> Set[str]:
    return set(_CALLBACK_TOKEN_STORES) | set(_INLINE_GAME_STORES) | set(_TEXT_GAME_STORES)


def _install_write_through_policy() -> int:
    """Write-through только для критичных сторов (не для всех button_* подряд)."""
    try:
        from bot.db_create import pklcode as P
    except Exception as e:
        logger.warning("pklcode import: %r", e)
        return 0

    n = 0
    for name in _critical_names():
        try:
            P.register_store_write_through(name, True)
            if name in _CALLBACK_TOKEN_STORES or name.startswith("button_"):
                P.register_store_expiry(name, 7 * 24 * 3600.0)
            else:
                P.register_store_expiry(name, 3 * 24 * 3600.0)
            n += 1
        except Exception as e:
            logger.warning("policy %s: %r", name, e)
    return n


def protect_before_restart(*, wait_timeout: float = 12.0) -> Dict[str, Any]:
    """Старый процесс: записать все сторы в Redis до смерти."""
    out: Dict[str, Any] = {"ok": False}
    try:
        _install_write_through_policy()
        from bot.db_create.pklcode import flush_all_stores_for_handoff

        out.update(flush_all_stores_for_handoff(wait_timeout=wait_timeout) or {})
        out["ok"] = int(out.get("failed", 0) or 0) == 0
        print(f"[BTN-SURVIVE] before_restart flush: {out}", flush=True)
    except Exception as e:
        out["error"] = repr(e)
        print(f"[BTN-SURVIVE] before_restart FAIL: {e!r}", flush=True)
    return out


def protect_after_start(*, reason: str = "boot", adopt: bool = True) -> Dict[str, Any]:
    """Новый процесс: политика + опциональный adopt Redis."""
    out: Dict[str, Any] = {"reason": reason, "policy": 0}
    try:
        out["policy"] = _install_write_through_policy()
    except Exception as e:
        out["policy_err"] = repr(e)

    if adopt:
        try:
            from bot.db_create.pklcode import adopt_stores_after_handoff

            out["adopt"] = adopt_stores_after_handoff()
        except Exception as e:
            out["adopt_err"] = repr(e)

    print(f"[BTN-SURVIVE] after_start ({reason}): {out}", flush=True)
    return out


async def protect_after_start_async(
    *,
    reason: str = "boot",
    adopt: bool = True,
    revive_magic: bool = True,
    dp: Any = None,
) -> Dict[str, Any]:
    out = await asyncio.to_thread(protect_after_start, reason=reason, adopt=adopt)
    if revive_magic:
        try:
            from bot.magic.install import revive_magic_system

            # На boot — лёгкий revive без тяжёлого audit (audit уже был/не нужен
            # для кликабельности). На handoff — hard reset лимитов.
            out["magic"] = await revive_magic_system(
                dp=dp,
                reason=f"btn_survive:{reason}",
                hard=(reason == "handoff"),
                run_audit=False,
            )
        except Exception as e:
            out["magic_err"] = repr(e)
    return out


def persist_callback_store(store: Any) -> None:
    """Немедленная запись токена в Redis через IO-поток (не блокирует клик)."""
    try:
        from bot.db_create import pklcode as P

        inner = store
        if hasattr(store, "_load"):
            inner = store._load()
        name = getattr(inner, "name", None) or "callback"
        # _write_through_save — без deadlock (flush через _io_submit ждать себя)
        if hasattr(inner, "_write_through_save"):
            P._io_submit(str(name), inner._write_through_save, wait=False)
        elif hasattr(inner, "save"):
            inner.save()
    except Exception as e:
        logger.warning("persist_callback_store: %r", e)
