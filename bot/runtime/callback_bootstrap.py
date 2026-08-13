# -*- coding: utf-8 -*-
"""
Callback Bootstrap — регистрация ВСЕХ inline-handler'ов до старта polling.

Проблема (кости и др.):
  Модули вроде bot.funcs.kosti импортируются лениво («кости» в чате).
  Декораторы @dp.callback_query срабатывают только при import.
  После рестарта старые кнопки kostijoin:/kostistart: уходят в orphan —
  handler просто не зарегистрирован. Это НЕ баг pkl и не «мёртвая сессия».

Решение:
  1) EAGER import всех модулей с @dp.callback_query при старте процесса.
  2) HOT DISPATCH: если orphan всё же поймал известный префикс —
     импортируем модуль и вызываем handler прямо сейчас (safety net).

Масштаб: один проход на boot (O(модули)), на клик hot-path не трогает.
"""

from __future__ import annotations

import importlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("callback_bootstrap")

# ── Модули, где висят @dp.callback_query ──
CALLBACK_MODULES: Tuple[str, ...] = (
    "bot.funcs.kosti",
    "bot.funcs.orel",
    "bot.funcs.bingo",
    "bot.funcs.ruletka",
    "bot.funcs.Roulett",
    "bot.funcs.knb",
    "bot.funcs.tic_tac_toe",
    "bot.games.scah",
    "bot.games.memory",
    "bot.games.mines",
    "bot.games.tank",
    "bot.games.risk",
    "bot.games.plate",
    "bot.games.bombs",
    "bot.games.provoda",
    "bot.games.balls",
    "bot.games.bullet",
    "bot.games.crash",
    "bot.games.word",
    "bot.games.gild",
    "bot.games.Fortuna",
    "bot.games.game",
    "bot.design.inorel",
    "bot.design.schahinline",
    "bot.design.inlinememory",
    "bot.design.induel",
    "bot.design.inlinekn",
    "bot.design.inmine",
    "bot.design.inlinetictac2",
    "bot.design.inlinetictactoe",
    "bot.design.sub",
    "bot.tggames.darts",
    "bot.tggames.kube",
    "bot.tggames.soccer",
    "bot.tggames.slots",
    "bot.tggames.basket",
    "bot.tggames.bowling",
    "bot.funcs.shop",
    "bot.funcs.Shep",
    "bot.funcs.shepinline",
    "bot.funcs.shophouse",
    "bot.funcs.shopvir",
    "bot.funcs.Gelicopter",
    "bot.funcs.top",
    "bot.funcs.history",
    "bot.funcs.balance",
    "bot.funcs.profile",
    "bot.funcs.promo",
    "bot.funcs.reklama",
    "bot.funcs.Shine",
    "bot.funcs.CuteCoin",
    "bot.funcs.BlackGack",
    "bot.funcs.dzrebi",
    "bot.funcs.garden",
    "bot.funcs.marriage",
    "bot.funcs.help",
    "bot.funcs.onboarding",
    "bot.handlers.chatbalance",
    "bot.handlers.editprofile",
    "bot.handlers.handlers_btns",
    "bot.handlers.useitems",
    "bot.buisnesses.clan_filter",
)

# prefix → (module, handler_attr); longest match wins
_PREFIX_HANDLERS: Tuple[Tuple[str, str, str], ...] = (
    ("kostijoin:", "bot.funcs.kosti", "kosti_join_game_callback"),
    ("kostistart:", "bot.funcs.kosti", "kosti_start_game_callback"),
    ("kostiroll:", "bot.funcs.kosti", "kosti_roll_callback"),
    ("podrobneekostihui_", "bot.funcs.kosti", "kosti_send_game_results"),
    ("joinorel:", "bot.funcs.orel", "join_game_callback"),
    ("startorel:", "bot.funcs.orel", "start_game_callback"),
    ("rollorel:", "bot.funcs.orel", "roll_callback"),
    ("joinorelinline:", "bot.design.inorel", "inline_join_game_callback"),
    ("startorelinline:", "bot.design.inorel", "inline_start_game_callback"),
    ("rollorelinline:", "bot.design.inorel", "inline_roll_callback"),
    ("inorel_create:", "bot.design.inorel", "inline_create_game_callback"),
    ("joinbingo:", "bot.funcs.bingo", "bingo_join_game_callback"),
    ("startbingo:", "bot.funcs.bingo", "bingo_start_game_callback"),
    ("rollbingo:", "bot.funcs.bingo", "bingo_roll_callback"),
    ("joinruletka:", "bot.funcs.ruletka", "ruletka_join_game_callback"),
    ("startruletka:", "bot.funcs.ruletka", "ruletka_start_game_callback"),
    ("joinroul_", "bot.funcs.Roulett", "Roullet_process_join"),
    ("startroul_", "bot.funcs.Roulett", "Roullet_process_start"),
    ("shootroul_", "bot.funcs.Roulett", "Roullet_process_shoot"),
    ("joinroulinduel_", "bot.design.induel", "induel_Roullet_process_join"),
    ("startroulinduel_", "bot.design.induel", "induel_Roullet_process_start"),
    ("shootroulinduel_", "bot.design.induel", "induel_Roullet_process_shoot"),
    ("joinknb:", "bot.funcs.knb", "knb_join_game_callback"),
    ("startknb:", "bot.funcs.knb", "knb_start_game_callback"),
    ("chooseknb:", "bot.funcs.knb", "knb_choose_callback"),
    ("rps_join:", "bot.design.inlinekn", "inline_knb_join_game_callback"),
    ("start_rps:", "bot.design.inlinekn", "inline_knb_start_game_callback"),
    ("rpschooseknb:", "bot.design.inlinekn", "inline_knb_choose_callback"),
    ("minejoin:", "bot.games.mines", "mines_join_game_callback"),
    ("minestart:", "bot.games.mines", "mines_start_game_callback"),
    ("mineclick:", "bot.games.mines", "mines_mine_click_callback"),
    ("minejoininmine:", "bot.design.inmine", "inline_mine_join_game_callback"),
    ("minestartinmine:", "bot.design.inmine", "inline_mine_start_game_callback"),
    ("mineclickinmine:", "bot.design.inmine", "inline_mine_mine_click_callback"),
    ("shajoin:", "bot.games.scah", "scah_join_game_callback"),
    ("shastart:", "bot.games.scah", "scah_start_game_callback"),
    ("select:", "bot.games.scah", "scah_select_piece_callback"),
    ("shamode:", "bot.games.scah", "select_mode_callback"),
    ("unique_join_game:", "bot.design.schahinline", "join_checkers_game_callback"),
    ("unique_start_game:", "bot.design.schahinline", "start_checkers_game_callback"),
    ("memoryjoin:", "bot.games.memory", "memory_join_game"),
    ("memorystart:", "bot.games.memory", "memory_start_game_callback"),
    ("memory_open:", "bot.games.memory", "memory_open"),
    ("inlinememoryjoin:", "bot.design.inlinememory", "inline_memory_join_memory_game"),
    ("jointictactoe:", "bot.funcs.tic_tac_toe", "tictactoe_join_game_callback"),
    ("starttictactoe:", "bot.funcs.tic_tac_toe", "start_game_callback"),
    ("movetictactoe:", "bot.funcs.tic_tac_toe", "make_move_callback"),
    ("surrendertictactoe:", "bot.funcs.tic_tac_toe", "surrender_callback"),
    ("tank_actual_", "bot.games.tank", "tank_process_game_buttons"),
    ("tank_withdraw", "bot.games.tank", "tank_process_withdraw"),
    ("risk_actual_", "bot.games.risk", "risk_process_game_buttons"),
    ("risk_withdraw", "bot.games.risk", "risk_process_withdraw"),
    ("plate_actual_", "bot.games.plate", "plate_process_game_buttons"),
    ("plate_withdraw", "bot.games.plate", "plate_process_withdraw"),
    ("bomb_", "bot.games.bombs", "bombs_process_bomb_click"),
    ("bostop_", "bot.games.bombs", "bombs_stop_game"),
    ("2412bombsskukota_", "bot.games.bombs", "bombs_bombsskukota_game"),
    ("bulletjoin:", "bot.games.bullet", "join_game_callback"),
    ("bulletstart:", "bot.games.bullet", "start_game_callback"),
)

_bootstrapped = False
_bootstrap_result: Dict[str, Any] = {}
_sorted_prefixes: Optional[List[Tuple[str, str, str]]] = None


def _get_sorted_prefixes() -> List[Tuple[str, str, str]]:
    global _sorted_prefixes
    if _sorted_prefixes is None:
        _sorted_prefixes = sorted(_PREFIX_HANDLERS, key=lambda t: len(t[0]), reverse=True)
    return _sorted_prefixes


def bootstrap_callback_handlers(*, force: bool = False) -> Dict[str, Any]:
    """Eager-import всех callback-модулей. Вызывать ДО attach_magic_fallback."""
    global _bootstrapped, _bootstrap_result
    if _bootstrapped and not force:
        return dict(_bootstrap_result)

    t0 = time.perf_counter()
    ok: List[str] = []
    failed: List[Dict[str, str]] = []

    for name in CALLBACK_MODULES:
        try:
            importlib.import_module(name)
            ok.append(name)
        except Exception as e:
            failed.append({"module": name, "error": f"{type(e).__name__}: {e}"})
            print(f"⚠️ [CB-BOOT] import fail {name}: {type(e).__name__}: {e}", flush=True)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    _bootstrap_result = {
        "ok": len(ok),
        "failed": len(failed),
        "errors": failed[:20],
        "ms": round(elapsed_ms, 1),
    }
    _bootstrapped = True
    print(
        f"✅ [CB-BOOT] handlers ready: ok={len(ok)} fail={len(failed)} "
        f"in {elapsed_ms:.0f}ms",
        flush=True,
    )
    return dict(_bootstrap_result)


def resolve_prefix_handler(callback_data: str) -> Optional[Tuple[str, str, str]]:
    data = str(callback_data or "")
    if not data:
        return None
    for prefix, mod, attr in _get_sorted_prefixes():
        if data.startswith(prefix):
            return prefix, mod, attr
    return None


async def try_hot_dispatch(query: Any) -> bool:
    """
    Orphan safety-net: модуль не импортирован → import + прямой вызов handler.
    True = handler найден и вызван (или уже ответили об ошибке).
    """
    data = str(getattr(query, "data", "") or "")
    hit = resolve_prefix_handler(data)
    if not hit:
        return False
    _prefix, mod_name, attr = hit
    try:
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, attr, None)
        if fn is None or not callable(fn):
            print(f"⚠️ [CB-HOT] {mod_name}.{attr} missing for {data[:48]!r}", flush=True)
            return False
        print(f"[CB-HOT] dispatch {data[:64]!r} → {mod_name}.{attr}", flush=True)
        await fn(query)
        return True
    except Exception as e:
        print(f"⚠️ [CB-HOT] {mod_name}.{attr} err: {type(e).__name__}: {e}", flush=True)
        try:
            await query.answer("⚠️ Ошибка обработки кнопки. Попробуйте ещё раз.", show_alert=True)
        except Exception:
            pass
        return True


def is_bootstrapped() -> bool:
    return bool(_bootstrapped)


# ── Hot-router: ловит известные префиксы ДО orphan-fallback ──
_hot_router = None
_hot_attached_dp_ids: set = set()


def _get_hot_router():
    """Router с одним handler'ом на все известные игровые префиксы."""
    global _hot_router
    if _hot_router is not None:
        return _hot_router

    from aiogram import Router
    from aiogram.types import CallbackQuery

    r = Router(name="callback_hot_dispatch")

    @r.callback_query(lambda c: bool(c.data) and resolve_prefix_handler(str(c.data)) is not None)
    async def _hot_prefix_dispatch(query: CallbackQuery):
        # Прямой вызов handler'а игры (с lazy-import). Не полагаемся на то,
        # что модуль уже был импортирован при старте.
        ok = await try_hot_dispatch(query)
        if not ok:
            try:
                await query.answer(
                    "⏳ Кнопка временно недоступна. Откройте игру заново.",
                    show_alert=True,
                )
            except Exception:
                pass

    _hot_router = r
    return r


def attach_hot_router(dp: Any) -> bool:
    """Подключить hot-router. Вызывать ДО attach_magic_fallback."""
    try:
        dp_id = id(dp)
        if dp_id in _hot_attached_dp_ids:
            return False
        dp.include_router(_get_hot_router())
        _hot_attached_dp_ids.add(dp_id)
        print("✅ [CB-BOOT] hot-router подключён (до orphan-fallback)", flush=True)
        return True
    except Exception as e:
        print(f"⚠️ [CB-BOOT] hot-router: {e!r}", flush=True)
        return False


def ensure_handlers_for_dispatcher(dp: Any = None) -> Dict[str, Any]:
    """Единая точка: bootstrap import + hot-router. Безопасно вызывать много раз."""
    out = bootstrap_callback_handlers()
    if dp is not None:
        out["hot_router"] = attach_hot_router(dp)
    return out

