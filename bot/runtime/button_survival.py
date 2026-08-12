# -*- coding: utf-8 -*-
"""Защита inline-кнопок от перезапусков (text-бот + inline-режим).

Telegram хранит клавиатуру на сообщении. Сессии/токены кнопок — в pkl→Redis.

Гарантии:
  1) Критичные сторы пишутся в Redis сразу (write-through), не ждут debounce.
  2) Перед выходом процесса — полный flush.
  3) После старта / handoff — принудительный adopt из Redis.
  4) Мэджик поднимает цепь кликов (middleware + orphan fallback).

Вызывать:
  protect_before_restart()  — старый процесс перед os._exit / SIGTERM
  protect_after_start(...)  — новый процесс когда Redis уже доступен
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

logger = logging.getLogger("button_survival")

# Токены коротких callback (вывод/подарки) — без них кнопка «устарела»
_CALLBACK_TOKEN_STORES: Set[str] = {
    "PREP_CALLBACK_ACTIONS",
    "GIFT_CALLBACK_ACTIONS",
    "SKIP_CALLBACK_ACTIONS",
    "SPEEDCONC_CALLBACK_ACTIONS",
    "SEND_REQUEST_ACTIONS",
}

# Inline-режим (@бот) — игровые сессии по inline_message_id
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

# Prefix: button_* / games* / active_games* / user_message*
_WRITE_THROUGH_PREFIXES = (
    "button_",
    "games",
    "active_games_",
    "user_message",
    "tank_",
    "bombs_",
    "temp_",
    "GIFT_",
    "PREP_",
    "SKIP_",
    "SPEEDCONC_",
    "SEND_REQUEST_",
    "_KING_MENU_",
    "_KING_DM_",
    "_pending_",
    "onboarding_",
)


def _install_write_through_policy() -> int:
    """Объявить write-through + длинный TTL для критичных сторов кнопок."""
    try:
        from bot.db_create import pklcode as P
    except Exception as e:
        logger.warning("pklcode import: %r", e)
        return 0

    names = set(_CALLBACK_TOKEN_STORES) | set(_INLINE_GAME_STORES)
    # Все уже созданные GameStore, похожие на кнопки/игры
    try:
        for name in list(getattr(P.GameStore, "_instances", {}).keys()):
            if _name_needs_write_through(name):
                names.add(name)
    except Exception:
        pass

    n = 0
    for name in names:
        try:
            P.register_store_write_through(name, True)
            # Кнопки в чатах живут долго — не убивать токены дефолтным 2h TTL
            if name in _CALLBACK_TOKEN_STORES or name.startswith("button_"):
                P.register_store_expiry(name, 7 * 24 * 3600.0)
            elif name in _INLINE_GAME_STORES or name.startswith("games"):
                P.register_store_expiry(name, 3 * 24 * 3600.0)
            n += 1
        except Exception as e:
            logger.warning("policy %s: %r", name, e)
    return n


def _name_needs_write_through(name: str) -> bool:
    if not name:
        return False
    if name in _CALLBACK_TOKEN_STORES or name in _INLINE_GAME_STORES:
        return True
    for p in _WRITE_THROUGH_PREFIXES:
        if name.startswith(p):
            return True
    return False


def protect_before_restart(*, wait_timeout: float = 12.0) -> Dict[str, Any]:
    """Старый процесс: записать все сторы кнопок в Redis до смерти."""
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
    """Новый процесс: политика + adopt Redis (после handoff/cold start)."""
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
    """Async-обёртка: adopt в thread + поднять Мэджик."""
    out = await asyncio.to_thread(protect_after_start, reason=reason, adopt=adopt)
    if revive_magic:
        try:
            from bot.magic.install import revive_magic_system

            out["magic"] = await revive_magic_system(
                dp=dp,
                reason=f"btn_survive:{reason}",
                hard=(reason in ("boot", "handoff")),
                run_audit=(reason in ("boot", "handoff")),
            )
        except Exception as e:
            out["magic_err"] = repr(e)
    return out


def persist_callback_store(store: Any) -> None:
    """Сразу записать стор токенов после register (не ждать debounce)."""
    try:
        inner = store
        if hasattr(store, "_load"):
            inner = store._load()
        if hasattr(inner, "flush"):
            inner.flush()
        elif hasattr(inner, "save"):
            inner.save()
    except Exception as e:
        logger.warning("persist_callback_store: %r", e)
