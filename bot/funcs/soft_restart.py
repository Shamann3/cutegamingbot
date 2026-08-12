# -*- coding: utf-8 -*-
"""Мягкий перезапуск процесса бота (без деплоя файлов).

ЧТО ЭТО
  Бот сам завершает процесс (exit 0). Docker / DigitalOcean поднимают
  ТОТ ЖЕ образ заново — как после деплоя, но без git/push.
  Код и файлы НЕ обновляются: только «свежий» процесс (память, соединения).

ЗАЧЕМ
  Раз в час «проветрить» процесс: меньше утечек памяти / залипших сокетов.

ГДЕ НАСТРАИВАТЬ
  Корневой .env (и те же ключи в Env на DigitalOcean для worker бота).
  См. блок «МЯГКИЙ ПЕРЕЗАПУСК» в .env / .env.example.

КОМАНДЫ В TELEGRAM (только owner / ADMIN_IDS)
  sypherrestart help     — краткая справка
  sypherrestart status   — аптайм, pid, через сколько следующий авто-рестарт
  sypherrestart now      — перезапустить прямо сейчас (удобно для проверки)

ТИПИЧНЫЙ ПУТЬ
  1) Проверка:  ENABLED=0  TEST=1  → ручной now, смотрим что бот ожил
  2) Бой:       ENABLED=1  TEST=0  → авто раз в INTERVAL_SEC (обычно 3600)

ПЕРЕМЕННЫЕ ОКЖЕНИЯ
  BOT_SOFT_RESTART_ENABLED          1/0 — авто по расписанию
  BOT_SOFT_RESTART_TEST             1/0 — тестовый режим (ручные проверки)
  BOT_SOFT_RESTART_INTERVAL_SEC     секунды между авто-рестартами (мин. 60)
  BOT_SOFT_RESTART_INITIAL_DELAY_SEC  пауза после старта до ПЕРВОГО авто
  BOT_SOFT_RESTART_GRACE_SEC        пауза перед exit (успеть ответить в чат)
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Awaitable, Callable, Optional, Set

NotifyFn = Callable[[str], Awaitable[None]]

_lock = asyncio.Lock()
_requested = False
_started_at = time.time()
_next_at: Optional[float] = None
_last_reason = ""
_scheduler_task: Optional[asyncio.Task] = None
_dp_ref = None
_notify_fn: Optional[NotifyFn] = None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except Exception:
        return float(default)


def is_enabled() -> bool:
    """Авто-рестарт по таймеру. По умолчанию выкл — включай явно в .env."""
    return _env_bool("BOT_SOFT_RESTART_ENABLED", False)


def is_test_mode() -> bool:
    """Тестовый режим: удобные ответы + ручной now без боя авто."""
    return _env_bool("BOT_SOFT_RESTART_TEST", False)


def interval_sec() -> float:
    return max(60.0, _env_float("BOT_SOFT_RESTART_INTERVAL_SEC", 3600.0))


def initial_delay_sec() -> float:
    # По умолчанию = интервал: первый час после старта живём спокойно
    return max(30.0, _env_float("BOT_SOFT_RESTART_INITIAL_DELAY_SEC", interval_sec()))


def grace_sec() -> float:
    return max(0.5, _env_float("BOT_SOFT_RESTART_GRACE_SEC", 3.0))


def status_dict() -> dict:
    now = time.time()
    return {
        "enabled": is_enabled(),
        "test_mode": is_test_mode(),
        "interval_sec": interval_sec(),
        "initial_delay_sec": initial_delay_sec(),
        "uptime_sec": round(now - _started_at, 1),
        "next_at": _next_at,
        "next_in_sec": None if _next_at is None else round(max(0.0, _next_at - now), 1),
        "requested": _requested,
        "last_reason": _last_reason or None,
        "pid": os.getpid(),
    }


def format_status_html() -> str:
    st = status_dict()
    if not st["enabled"]:
        next_line = "авто выключен (только ручной now)"
    elif st["next_at"] is not None:
        next_line = f"через <b>{st['next_in_sec']}</b> сек"
    else:
        next_line = "ещё не запланирован (планировщик не стартовал)"
    mode = "тестовый" if st["test_mode"] else "боевой"
    on = "вкл" if st["enabled"] else "выкл"
    return (
        f"<b>Мягкий перезапуск</b> · режим: <b>{mode}</b>\n"
        f"Авто по часу: <b>{on}</b> · интервал <b>{int(st['interval_sec'])}</b> сек\n"
        f"Аптайм: <b>{int(st['uptime_sec'])}</b> сек · pid <code>{st['pid']}</code>\n"
        f"Следующий авто: {next_line}\n"
        f"Сейчас запрошен выход: <b>{'да' if st['requested'] else 'нет'}</b>"
        + (f"\nПричина: <i>{st['last_reason']}</i>" if st["last_reason"] else "")
        + "\n\n<code>sypherrestart help</code> · "
        "<code>sypherrestart status</code> · "
        "<code>sypherrestart now</code>"
    )


def bind(*, dp=None, notify: Optional[NotifyFn] = None) -> None:
    global _dp_ref, _notify_fn
    if dp is not None:
        _dp_ref = dp
    if notify is not None:
        _notify_fn = notify


async def _notify(text: str) -> None:
    if not _notify_fn:
        return
    try:
        await _notify_fn(text)
    except Exception as e:
        print(f"[SOFT_RESTART] notify fail: {e!r}")


async def _perform_exit(reason: str) -> None:
    """Остановить polling и выйти 0 — Docker/DO поднимут тот же образ."""
    global _requested, _last_reason
    _requested = True
    _last_reason = reason
    print(f"[SOFT_RESTART] begin reason={reason!r} pid={os.getpid()}")
    await _notify(
        f"🔁 <b>Мягкий перезапуск</b>\n"
        f"Причина: <code>{reason}</code>\n"
        f"Код не обновляется — только процесс. Сейчас выхожу…"
    )
    await asyncio.sleep(grace_sec())

    dp = _dp_ref
    if dp is not None:
        try:
            if hasattr(dp, "stop_polling"):
                await dp.stop_polling()
                print("[SOFT_RESTART] dp.stop_polling() ok")
        except Exception as e:
            print(f"[SOFT_RESTART] stop_polling: {e!r}")

    await asyncio.sleep(1.0)
    print(f"[SOFT_RESTART] exit 0 (platform must restart same image)")
    os._exit(0)


async def request_restart(reason: str = "manual", *, force: bool = False) -> bool:
    """Запросить мягкий рестарт. Повторные вызовы игнорируются."""
    global _requested
    async with _lock:
        if _requested and not force:
            return False
        _requested = True
    asyncio.create_task(_perform_exit(reason))
    return True


async def _scheduler_loop() -> None:
    global _next_at
    if not is_enabled():
        print("[SOFT_RESTART] scheduler off (BOT_SOFT_RESTART_ENABLED=0)")
        return
    delay = initial_delay_sec()
    interval = interval_sec()
    _next_at = time.time() + delay
    print(
        f"[SOFT_RESTART] scheduler on: first in {delay:.0f}s, "
        f"then every {interval:.0f}s, test={is_test_mode()}"
    )
    try:
        await asyncio.sleep(delay)
        while True:
            if not is_enabled():
                print("[SOFT_RESTART] disabled mid-flight — stop scheduler")
                return
            _next_at = time.time()
            ok = await request_restart("schedule_hourly")
            if ok:
                return
            _next_at = time.time() + interval
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print("[SOFT_RESTART] scheduler cancelled")
        raise


def start_scheduler(*, dp=None, notify: Optional[NotifyFn] = None) -> Optional[asyncio.Task]:
    """Запуск фонового планировщика (вызывать после старта polling)."""
    global _scheduler_task, _started_at
    bind(dp=dp, notify=notify)
    _started_at = time.time()
    if _scheduler_task and not _scheduler_task.done():
        return _scheduler_task
    if not is_enabled():
        print(
            "[SOFT_RESTART] авто выкл "
            f"(TEST={'on' if is_test_mode() else 'off'}) — ждут команды sypherrestart"
        )
        return None
    _scheduler_task = asyncio.create_task(_scheduler_loop(), name="soft_restart_scheduler")
    return _scheduler_task


def owner_ids() -> Set[int]:
    try:
        from bot.config.config import ADMIN_IDS
        return set(int(x) for x in (ADMIN_IDS or set()))
    except Exception:
        return {6801702632}


async def handle_owner_command(message: Any) -> bool:
    """Обработка команд владельца. True = команда распознана."""
    try:
        uid = int(message.from_user.id)
        text = (message.text or "").strip().lower()
    except Exception:
        return False
    if uid not in owner_ids():
        return False

    aliases_status = {
        "sypherrestart status",
        "sypherrestart статус",
        "перезапуск статус",
        "softrestart status",
    }
    aliases_now = {
        "sypherrestart",
        "sypherrestart now",
        "sypherrestart сейчас",
        "перезапуск бота",
        "перезапуск бота сейчас",
        "softrestart",
        "softrestart now",
    }
    aliases_help = {
        "sypherrestart help",
        "sypherrestart помощь",
        "перезапуск помощь",
    }

    if text in aliases_help or text == "sypherrestart ?":
        await message.reply(
            "<b>Мягкий перезапуск</b>\n"
            "Процесс бота завершается → Docker/DO поднимает <b>тот же</b> образ.\n"
            "Файлы/код с git <b>не</b> обновляются.\n\n"
            "<b>Команды</b>\n"
            "• <code>sypherrestart status</code> — жив ли планировщик, аптайм\n"
            "• <code>sypherrestart now</code> — перезапустить сейчас\n\n"
            "<b>Настройка в .env</b>\n"
            "• проверка: <code>BOT_SOFT_RESTART_TEST=1</code> "
            "и <code>BOT_SOFT_RESTART_ENABLED=0</code>\n"
            "• бой: <code>ENABLED=1</code>, <code>TEST=0</code> "
            "(авто раз в час)\n\n"
            "Подробности — блок «МЯГКИЙ ПЕРЕЗАПУСК» в корневом <code>.env</code>.",
            parse_mode="HTML",
        )
        return True

    if text in aliases_status:
        await message.reply(format_status_html(), parse_mode="HTML")
        return True

    if text in aliases_now:
        # Ручной now: нужен TEST=1 или ENABLED=1 (чтобы случайно не ронять прод без флага)
        if not is_test_mode() and not is_enabled():
            await message.reply(
                "Сейчас нельзя: авто выкл и тест-режим тоже выкл.\n\n"
                "Для проверки поставь в .env:\n"
                "<code>BOT_SOFT_RESTART_TEST=1</code>\n"
                "<code>BOT_SOFT_RESTART_ENABLED=0</code>\n"
                "и перезапусти процесс бота обычным способом один раз.",
                parse_mode="HTML",
            )
            return True
        warn = ""
        if not is_test_mode():
            warn = "\n<i>TEST выкл — это боевой ручной рестарт.</i>"
        await message.reply(
            "🔁 Запускаю мягкий перезапуск…" + warn,
            parse_mode="HTML",
        )
        await request_restart("manual_owner" + ("_test" if is_test_mode() else ""))
        return True

    return False
