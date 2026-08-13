# -*- coding: utf-8 -*-
"""
Callback Bootstrap — регистрация ВСЕХ inline callback-handler'ов проекта.

Данные: bot/runtime/callback_registry_generated.py
  (пересобрать: python -m bot.runtime._gen_callback_registry)

Проблема:
  Многие модули импортируются лениво («кости» в чате) → @dp.callback_query
  не висит на Dispatcher после рестарта → orphan / мёртвые кнопки.

Решение:
  1) EAGER import всех модулей с @callback_query (кроме main / WebApp-серверов).
  2) HOT ROUTER + HOT DISPATCH по полной карте prefix/exact → handler.
  3) WebApp / Mini App не трогаем (нет callback_data на web_app кнопках).
"""

from __future__ import annotations

import importlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("callback_bootstrap")

try:
    from bot.runtime.callback_registry_generated import (
        CALLBACK_MODULES,
        EXACT_HANDLERS,
        PREFIX_HANDLERS,
    )
except Exception as e:  # pragma: no cover
    print(f"⚠️ [CB-BOOT] registry missing: {e!r} — empty fallback", flush=True)
    CALLBACK_MODULES = ()
    PREFIX_HANDLERS = {}
    EXACT_HANDLERS = {}

_bootstrapped = False
_bootstrap_result: Dict[str, Any] = {}
_sorted_prefixes: Optional[List[str]] = None
_hot_router = None
_hot_attached_dp_ids: set = set()


def _get_sorted_prefixes() -> List[str]:
    global _sorted_prefixes
    if _sorted_prefixes is None:
        _sorted_prefixes = sorted(PREFIX_HANDLERS.keys(), key=len, reverse=True)
    return _sorted_prefixes


def bootstrap_callback_handlers(*, force: bool = False) -> Dict[str, Any]:
    """Eager-import всех callback-модулей. Безопасно вызывать много раз."""
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
        "errors": failed[:30],
        "ms": round(elapsed_ms, 1),
        "modules": len(CALLBACK_MODULES),
        "prefixes": len(PREFIX_HANDLERS),
        "exact": len(EXACT_HANDLERS),
    }
    _bootstrapped = True
    print(
        f"✅ [CB-BOOT] handlers ready: ok={len(ok)}/{len(CALLBACK_MODULES)} "
        f"fail={len(failed)} prefixes={len(PREFIX_HANDLERS)} "
        f"exact={len(EXACT_HANDLERS)} in {elapsed_ms:.0f}ms",
        flush=True,
    )
    return dict(_bootstrap_result)


def resolve_handler(callback_data: str) -> Optional[Tuple[str, str, str]]:
    """
    Найти (match_key, module, attr) для callback_data.
    Сначала exact, потом longest prefix.
    """
    data = str(callback_data or "")
    if not data:
        return None
    if data in EXACT_HANDLERS:
        mod, attr = EXACT_HANDLERS[data]
        return data, mod, attr
    for prefix in _get_sorted_prefixes():
        if data.startswith(prefix):
            mod, attr = PREFIX_HANDLERS[prefix]
            return prefix, mod, attr
    return None


# backward-compat alias
def resolve_prefix_handler(callback_data: str) -> Optional[Tuple[str, str, str]]:
    return resolve_handler(callback_data)


async def try_hot_dispatch(query: Any) -> bool:
    """
    Orphan / hot-router: import модуля + прямой вызов handler.
    True = handler найден и вызван (или уже ответили об ошибке).
    """
    data = str(getattr(query, "data", "") or "")
    hit = resolve_handler(data)
    if not hit:
        return False
    _key, mod_name, attr = hit
    try:
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, attr, None)
        if fn is None or not callable(fn):
            print(f"⚠️ [CB-HOT] {mod_name}.{attr} missing for {data[:64]!r}", flush=True)
            return False
        print(f"[CB-HOT] dispatch {data[:64]!r} → {mod_name}.{attr}", flush=True)
        await fn(query)
        return True
    except Exception as e:
        print(f"⚠️ [CB-HOT] {mod_name}.{attr} err: {type(e).__name__}: {e}", flush=True)
        try:
            await query.answer(
                "⚠️ Ошибка обработки кнопки. Попробуйте ещё раз.",
                show_alert=True,
            )
        except Exception:
            pass
        return True


def is_bootstrapped() -> bool:
    return bool(_bootstrapped)


def _get_hot_router():
    """Router: любой известный prefix/exact → hot dispatch (до orphan)."""
    global _hot_router
    if _hot_router is not None:
        return _hot_router

    from aiogram import Router
    from aiogram.types import CallbackQuery

    r = Router(name="callback_hot_dispatch")

    @r.callback_query(lambda c: bool(c.data) and resolve_handler(str(c.data)) is not None)
    async def _hot_prefix_dispatch(query: CallbackQuery):
        ok = await try_hot_dispatch(query)
        if not ok:
            try:
                await query.answer(
                    "⏳ Кнопка временно недоступна. Откройте меню заново.",
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
        print(
            f"✅ [CB-BOOT] hot-router: {len(PREFIX_HANDLERS)} prefixes + "
            f"{len(EXACT_HANDLERS)} exact",
            flush=True,
        )
        return True
    except Exception as e:
        print(f"⚠️ [CB-BOOT] hot-router: {e!r}", flush=True)
        return False


def ensure_handlers_for_dispatcher(dp: Any = None) -> Dict[str, Any]:
    """Единая точка: bootstrap import + hot-router."""
    out = bootstrap_callback_handlers()
    if dp is not None:
        out["hot_router"] = attach_hot_router(dp)
    return out


def registry_stats() -> Dict[str, int]:
    return {
        "modules": len(CALLBACK_MODULES),
        "prefixes": len(PREFIX_HANDLERS),
        "exact": len(EXACT_HANDLERS),
        "bootstrapped": int(_bootstrapped),
    }
