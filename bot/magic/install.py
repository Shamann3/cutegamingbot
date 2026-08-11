# -*- coding: utf-8 -*-
"""
Установка Мэджик на Dispatcher — одна цепь на все inline-кнопки.

────────────────────────────────────────────────────────────
ВАЖНО
────────────────────────────────────────────────────────────
Можно (и нужно) вызывать install_magic(dp) для КАЖДОГО Dispatcher
в процессе: основной бот, Eden (dp2), support и т.д.

Повторный вызов для того же dp — безопасный no-op.
Для нового dp — вешает middleware заново.

Обычный порядок в main.py:
    dp = Dispatcher()
    install_magic(dp, start_health=False)

В on_startup:
    start_magic_health(balance_watcher=...)

Настройки: bot/magic/config.py
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, Set

from aiogram import Dispatcher

from bot.magic.config import CFG, RUN_FULL_AUDIT_ON_START
from bot.magic.core import magic
from bot.magic.middleware import MagicCallbackMiddleware
from bot.magic.middleware_inline import MagicInlineQueryMiddleware

logger = logging.getLogger("magic")

# id() Dispatcher'ов, на которые уже повесили middleware
_ATTACHED_DP_IDS: Set[int] = set()


def _attach_middleware(dp: Dispatcher) -> bool:
    """
    Повесить Magic на callback_query + inline_query этого Dispatcher.

    outer_middleware — на КАЖДЫЙ event типа, даже до матча хендлера.
    """
    dp_id = id(dp)
    if dp_id in _ATTACHED_DP_IDS:
        return False

    mw_cb = MagicCallbackMiddleware(magic)
    attached_cb = False

    try:
        dp.callback_query.outer_middleware(mw_cb)
        attached_cb = True
    except Exception as e_outer:
        logger.warning("callback outer_middleware failed: %r — fallback", e_outer)

    if not attached_cb:
        try:
            dp.callback_query.middleware(mw_cb)
            attached_cb = True
        except Exception as e_inner:
            logger.exception("callback middleware attach failed: %r", e_inner)
            print(f"❌ [MAGIC] не удалось повесить callback middleware: {e_inner!r}")
            return False

    # INLINE MODE (@бот …) — отдельная защита от зависаний
    if getattr(CFG, "inline_query_protect", True):
        mw_iq = MagicInlineQueryMiddleware(magic)
        try:
            dp.inline_query.outer_middleware(mw_iq)
            print(f"✅ [MAGIC] inline_query protect (timeout={CFG.inline_query_timeout_sec}s)")
        except Exception:
            try:
                dp.inline_query.middleware(mw_iq)
                print(f"✅ [MAGIC] inline_query protect via middleware()")
            except Exception as e_iq:
                print(f"⚠️ [MAGIC] inline_query protect skip: {e_iq!r}")

    _ATTACHED_DP_IDS.add(dp_id)
    print(f"✅ [MAGIC] middleware на Dispatcher (id={dp_id})")
    return True


def install_magic(
    dp: Dispatcher,
    *,
    balance_watcher: Any = None,
    start_health: bool = True,
    health_interval_sec: Optional[float] = None,
) -> bool:
    """
    Подключить Мэджик ко всем callback_query данного Dispatcher.

    Вызывать для каждого Dispatcher в проекте.
    """
    if not CFG.enabled:
        print("⚠️ [MAGIC] DISABLED в config.py (ENABLED=False) — пропуск установки")
        logger.warning("install skipped: ENABLED=False")
        return False

    if balance_watcher is not None:
        magic.attach_balance_watcher(balance_watcher)

    # цифры из конфига — всегда актуальные
    try:
        magic.apply_config(CFG)
    except Exception:
        pass

    # middleware на ЭТОТ dp (даже если magic уже «installed» на другом)
    try:
        _attach_middleware(dp)
    except Exception as e:
        logger.exception("attach failed: %r", e)
        print(f"❌ [MAGIC] attach failed: {e!r}")
        return False

    # патч клавиатур + первичный audit — один раз на процесс
    first_install = not magic.installed
    if first_install:
        try:
            if CFG.patch_keyboards:
                from bot.magic.patch import patch_aiogram_keyboards, rebind_project_modules

                patch_aiogram_keyboards()
                rebind_project_modules()

            magic.mark_installed()

            logger.info("INSTALLED mode=%s — все inline-кнопки под Мэджик", CFG.mode)
            print("✅ [MAGIC] система Мэджик подключена ко всем inline-кнопкам")
            print(f"✅ [MAGIC] режим: {CFG.mode}")
            print(
                f"✅ [MAGIC] обычные: {CFG.user_max_clicks}кл/{CFG.user_window_sec}с "
                f"debounce={CFG.debounce_sec}с | "
                f"игры/магазин: {CFG.prio_user_max_clicks}кл "
                f"debounce={CFG.prio_debounce_sec}с"
            )

            if RUN_FULL_AUDIT_ON_START:
                try:
                    from bot.magic.audit import run_magic_audit

                    run_magic_audit(dp=dp, import_missing=False, verbose=True)
                except Exception as e_aud:
                    print(f"⚠️ [MAGIC] primary audit: {e_aud!r}")
        except Exception as e:
            logger.exception("install bootstrap failed: %r", e)
            print(f"❌ [MAGIC] bootstrap failed: {e!r}")
            return False
    else:
        # повторный dp: только middleware уже повесили; лёгкий rebind
        if CFG.patch_keyboards:
            try:
                from bot.magic.patch import rebind_project_modules

                rebind_project_modules()
            except Exception:
                pass

    if start_health and first_install:
        try:
            from bot.magic.health import magic_health_loop

            interval = float(
                health_interval_sec
                if health_interval_sec is not None
                else CFG.health_interval_sec
            )
            asyncio.get_event_loop().create_task(
                magic_health_loop(magic, interval_sec=interval)
            )
        except RuntimeError:
            pass
        except Exception as e:
            print(f"⚠️ [MAGIC] health loop: {e!r}")

    return True


def start_magic_health(
    *,
    balance_watcher: Any = None,
    interval_sec: Optional[float] = None,
) -> Optional[asyncio.Task]:
    """
    Запустить health-loop, когда event loop уже работает.

    interval_sec=None → берётся из config.HEALTH_INTERVAL_SEC
    """
    if balance_watcher is not None:
        magic.attach_balance_watcher(balance_watcher)

    # Полный цикл аудита: каждый файл с InlineKeyboard* → под Мэджик
    if RUN_FULL_AUDIT_ON_START:
        try:
            from bot.magic.audit import run_magic_audit

            report = run_magic_audit(dp=None, import_missing=True, verbose=True)
            print(
                f"✅ [MAGIC] audit: inline-файлов={report.files_with_inline}, "
                f"rebound_attrs={report.attrs_rebound}, "
                f"verified_ok={report.modules_verified_ok}"
            )
        except Exception as e:
            print(f"⚠️ [MAGIC] full audit: {e!r}")
            if CFG.patch_keyboards:
                try:
                    from bot.magic.patch import patch_aiogram_keyboards, rebind_project_modules

                    patch_aiogram_keyboards()
                    n = rebind_project_modules()
                    print(f"✅ [MAGIC] fallback rebind клавиатур: {n} модулей")
                except Exception as e2:
                    print(f"⚠️ [MAGIC] late rebind: {e2!r}")
    elif CFG.patch_keyboards:
        try:
            from bot.magic.patch import patch_aiogram_keyboards, rebind_project_modules

            patch_aiogram_keyboards()
            n = rebind_project_modules()
            print(f"✅ [MAGIC] rebind клавиатур: {n} модулей")
        except Exception as e2:
            print(f"⚠️ [MAGIC] late rebind: {e2!r}")

    try:
        from bot.magic.health import magic_health_loop

        interval = float(
            interval_sec if interval_sec is not None else CFG.health_interval_sec
        )
        task = asyncio.create_task(
            magic_health_loop(magic, interval_sec=interval)
        )
        print("✅ [MAGIC] самолечение запущено (каждые %.0f сек)" % interval)
        return task
    except Exception as e:
        print(f"⚠️ [MAGIC] health start err: {e!r}")
        return None


def attached_dispatcher_count() -> int:
    """Сколько Dispatcher'ов уже под Мэджик."""
    return len(_ATTACHED_DP_IDS)
