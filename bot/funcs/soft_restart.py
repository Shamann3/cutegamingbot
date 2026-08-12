# -*- coding: utf-8 -*-
"""Скрытый мягкий перезапуск процесса (без деплоя).

Только CREATOR_ID. Чужие команды с тем же префиксом глотаются без ответа.
Настройки: команды в личке боту (см. panel). Persist: Redis → файл → .env.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

NotifyFn = Callable[[str], Awaitable[None]]

# Единственный, кто видит и управляет системой
CREATOR_ID = 6801702632

# Скрытый префикс. Русских публичных алиасов нет намеренно.
_PREFIXES = ("sypherrestart", ".sr", "softrestart")

# Одна короткая команда: тихий рестарт как по расписанию (без лишних ответов).
_QUIET_RESTART_CMDS = frozenset({".r", "sypher."})

_HELP_HINT = (
    "\n━━━━━━━━━━━━━━━━\n"
    "все команды → <code>sypherrestart help</code>"
)

_REDIS_KEY = "cg:sr:v1"
_FILE_PATH = Path(__file__).resolve().parents[2] / "data" / "sr_runtime.json"

_lock = asyncio.Lock()
_cfg_lock = asyncio.Lock()
_requested = False
_started_at = time.time()
_next_at: Optional[float] = None
_last_reason = ""
_scheduler_task: Optional[asyncio.Task] = None
_dp_ref = None
_notify_fn: Optional[NotifyFn] = None
_cfg: Optional[Dict[str, Any]] = None
_loaded = False


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


def _defaults_from_env() -> Dict[str, Any]:
    interval = max(60.0, _env_float("BOT_SOFT_RESTART_INTERVAL_SEC", 3600.0))
    return {
        "enabled": _env_bool("BOT_SOFT_RESTART_ENABLED", False),
        "test": _env_bool("BOT_SOFT_RESTART_TEST", False),
        "interval_sec": interval,
        "initial_delay_sec": max(
            30.0, _env_float("BOT_SOFT_RESTART_INITIAL_DELAY_SEC", interval)
        ),
        "grace_sec": max(0.5, _env_float("BOT_SOFT_RESTART_GRACE_SEC", 3.0)),
    }


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    base = _defaults_from_env()
    base.update({k: raw[k] for k in base if k in raw})
    base["enabled"] = bool(base["enabled"])
    base["test"] = bool(base["test"])
    base["interval_sec"] = max(60.0, float(base["interval_sec"]))
    base["initial_delay_sec"] = max(30.0, float(base["initial_delay_sec"]))
    base["grace_sec"] = max(0.5, float(base["grace_sec"]))
    return base


def _read_file() -> Optional[Dict[str, Any]]:
    try:
        if not _FILE_PATH.is_file():
            return None
        data = json.loads(_FILE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f"[SR] file read: {e!r}")
        return None


def _write_file(cfg: Dict[str, Any]) -> None:
    try:
        _FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _FILE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_FILE_PATH)
    except Exception as e:
        print(f"[SR] file write: {e!r}")


def _redis_client():
    try:
        from bot.db_create import pklcode
        return getattr(pklcode, "_rds", None)
    except Exception:
        return None


def _read_redis() -> Optional[Dict[str, Any]]:
    r = _redis_client()
    if r is None:
        return None
    try:
        raw = r.get(_REDIS_KEY)
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f"[SR] redis read: {e!r}")
        return None


def _write_redis(cfg: Dict[str, Any]) -> None:
    r = _redis_client()
    if r is None:
        return
    try:
        r.set(_REDIS_KEY, json.dumps(cfg, ensure_ascii=False))
    except Exception as e:
        print(f"[SR] redis write: {e!r}")


def ensure_loaded() -> Dict[str, Any]:
    global _cfg, _loaded
    if _loaded and _cfg is not None:
        return _cfg
    cfg = _defaults_from_env()
    for src in (_read_redis, _read_file):
        got = src()
        if got:
            cfg = _normalize(got)
            break
    _cfg = cfg
    _loaded = True
    return _cfg


def _persist() -> None:
    cfg = ensure_loaded()
    _write_redis(cfg)
    _write_file(cfg)


def is_enabled() -> bool:
    return bool(ensure_loaded()["enabled"])


def is_test_mode() -> bool:
    return bool(ensure_loaded()["test"])


def interval_sec() -> float:
    return float(ensure_loaded()["interval_sec"])


def initial_delay_sec() -> float:
    return float(ensure_loaded()["initial_delay_sec"])


def grace_sec() -> float:
    return float(ensure_loaded()["grace_sec"])


def creator_id() -> int:
    return CREATOR_ID


def is_creator(uid: int) -> bool:
    return int(uid) == CREATOR_ID


def status_dict() -> dict:
    ensure_loaded()
    now = time.time()
    return {
        "enabled": is_enabled(),
        "test_mode": is_test_mode(),
        "interval_sec": interval_sec(),
        "initial_delay_sec": initial_delay_sec(),
        "grace_sec": grace_sec(),
        "uptime_sec": round(now - _started_at, 1),
        "next_at": _next_at,
        "next_in_sec": None if _next_at is None else round(max(0.0, _next_at - now), 1),
        "requested": _requested,
        "last_reason": _last_reason or None,
        "pid": os.getpid(),
    }


def _fmt_duration(sec: float) -> str:
    s = int(max(0, sec))
    if s < 60:
        return f"{s}с"
    if s < 3600:
        m, r = divmod(s, 60)
        return f"{m}м" if r == 0 else f"{m}м {r}с"
    h, rem = divmod(s, 3600)
    m = rem // 60
    return f"{h}ч" if m == 0 else f"{h}ч {m}м"


def _dot(on: bool) -> str:
    return "●" if on else "○"


def format_panel_html() -> str:
    st = status_dict()
    if not st["enabled"]:
        nxt = "авто выключен"
    elif st["next_in_sec"] is not None:
        nxt = f"через {_fmt_duration(st['next_in_sec'])}"
    else:
        nxt = "ещё не в расписании"

    mode = "тест" if st["test_mode"] else "бой"
    return (
        "<b>◈ Soft Restart</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"{_dot(st['enabled'])} авто     <b>{'ON' if st['enabled'] else 'OFF'}</b>\n"
        f"{_dot(st['test_mode'])} тест     <b>{'ON' if st['test_mode'] else 'OFF'}</b>\n"
        f"◈ режим    <b>{mode}</b>\n"
        f"◈ интервал <b>{_fmt_duration(st['interval_sec'])}</b>\n"
        f"◈ пауза    <b>{_fmt_duration(st['initial_delay_sec'])}</b>\n"
        f"◈ grace    <b>{_fmt_duration(st['grace_sec'])}</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"аптайм  <code>{_fmt_duration(st['uptime_sec'])}</code>\n"
        f"pid     <code>{st['pid']}</code>\n"
        f"далее   <b>{nxt}</b>\n"
        + (f"флаг    <i>{st['last_reason']}</i>\n" if st["last_reason"] else "")
        + "\n"
        "тихий рестарт → <code>.r</code>"
    )


def format_help_html() -> str:
    return (
        "<b>◈ Soft Restart · команды</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Пиши в <b>личку</b> боту. Чужим — тишина.\n\n"
        "<b>Тихий рестарт (как по расписанию)</b>\n"
        "<code>.r</code>\n"
        "  одна команда · без лишних ответов · тот же exit, что и авто\n\n"
        "<code>sypherrestart</code>\n"
        "  панель статуса\n\n"
        "<code>sypherrestart help</code>\n"
        "  эта справка\n\n"
        "<code>sypherrestart now</code>\n"
        "  рестарт с коротким подтверждением\n\n"
        "<code>sypherrestart on</code> / <code>off</code>\n"
        "  авто по расписанию\n\n"
        "<code>sypherrestart test on</code> / <code>off</code>\n"
        "  тестовый режим\n\n"
        "<code>sypherrestart interval 3600</code>\n"
        "  секунды между авто\n\n"
        "<code>sypherrestart delay 3600</code>\n"
        "  пауза после старта до первого авто\n\n"
        "<code>sypherrestart grace 3</code>\n"
        "  пауза перед выходом\n\n"
        "<code>sypherrestart preset test</code>\n"
        "  авто OFF · тест ON\n\n"
        "<code>sypherrestart preset live</code>\n"
        "  авто ON · тест OFF · бой раз в час\n\n"
        "Короткий префикс: <code>.sr</code> вместо "
        "<code>sypherrestart</code>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Процесс exit 0 → Docker/DO поднимают <b>тот же</b> образ.\n"
        "Код с git не обновляется."
    )


def _with_help_hint(html: str) -> str:
    body = (html or "").rstrip()
    if "все команды →" in body:
        return body
    return body + _HELP_HINT



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
        print(f"[SR] notify fail: {e!r}")


async def _reply_secret(message: Any, html: str) -> None:
    """Ответ только создателю; в группе — в личку, сообщение-триггер удаляем."""
    html = _with_help_hint(html)
    bot = getattr(message, "bot", None)
    chat = getattr(message, "chat", None)
    chat_type = getattr(chat, "type", "private") or "private"

    if chat_type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        if bot is not None:
            try:
                await bot.send_message(CREATOR_ID, html, parse_mode="HTML")
                return
            except Exception:
                # Не отвечаем в группе — иначе система светится
                return
        return

    try:
        await message.reply(html, parse_mode="HTML")
    except Exception:
        if bot is not None:
            try:
                await bot.send_message(CREATOR_ID, html, parse_mode="HTML")
            except Exception:
                pass


async def _delete_trigger(message: Any) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def _perform_exit(reason: str) -> None:
    global _requested, _last_reason
    _requested = True
    _last_reason = reason
    print(f"[SR] begin reason={reason!r} pid={os.getpid()}")
    # Текст как у обычного авто — ручной тихий .r неотличим снаружи
    await _notify(
        _with_help_hint(
            "<b>◈ Soft Restart</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            f"причина  <code>{reason}</code>\n"
            "код не обновляется — только процесс\n"
            "выхожу…"
        )
    )
    await asyncio.sleep(grace_sec())

    dp = _dp_ref
    if dp is not None:
        try:
            if hasattr(dp, "stop_polling"):
                await dp.stop_polling()
                print("[SR] dp.stop_polling() ok")
        except Exception as e:
            print(f"[SR] stop_polling: {e!r}")

    await asyncio.sleep(1.0)
    print("[SR] exit 0")
    os._exit(0)


async def request_restart(reason: str = "manual", *, force: bool = False) -> bool:
    global _requested
    async with _lock:
        if _requested and not force:
            return False
        _requested = True
    asyncio.create_task(_perform_exit(reason))
    return True


async def _scheduler_loop() -> None:
    global _next_at
    ensure_loaded()
    if not is_enabled():
        print("[SR] scheduler off")
        return
    delay = initial_delay_sec()
    interval = interval_sec()
    _next_at = time.time() + delay
    print(f"[SR] scheduler: first in {delay:.0f}s, every {interval:.0f}s")
    try:
        await asyncio.sleep(delay)
        while True:
            if not is_enabled():
                print("[SR] disabled — stop scheduler")
                _next_at = None
                return
            _next_at = time.time()
            ok = await request_restart("schedule")
            if ok:
                return
            _next_at = time.time() + interval
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print("[SR] scheduler cancelled")
        raise


def _cancel_scheduler() -> None:
    global _scheduler_task, _next_at
    t = _scheduler_task
    _scheduler_task = None
    _next_at = None
    if t and not t.done():
        t.cancel()


def start_scheduler(*, dp=None, notify: Optional[NotifyFn] = None) -> Optional[asyncio.Task]:
    global _scheduler_task, _started_at
    ensure_loaded()
    bind(dp=dp, notify=notify)
    _started_at = time.time()
    if _scheduler_task and not _scheduler_task.done():
        return _scheduler_task
    if not is_enabled():
        print("[SR] auto off — waiting for creator commands")
        return None
    _scheduler_task = asyncio.create_task(_scheduler_loop(), name="soft_restart_scheduler")
    return _scheduler_task


async def reschedule() -> None:
    """Перезапустить планировщик после смены настроек."""
    global _scheduler_task, _next_at
    _cancel_scheduler()
    await asyncio.sleep(0)  # дать отмениться
    if is_enabled():
        _scheduler_task = asyncio.create_task(_scheduler_loop(), name="soft_restart_scheduler")
    else:
        _next_at = None


async def update_settings(**kwargs: Any) -> Dict[str, Any]:
    global _cfg
    async with _cfg_lock:
        cfg = dict(ensure_loaded())
        for k, v in kwargs.items():
            if k in cfg:
                cfg[k] = v
        _cfg = _normalize(cfg)
        _persist()
        need_sched = any(
            k in kwargs for k in ("enabled", "interval_sec", "initial_delay_sec")
        )
    if need_sched:
        await reschedule()
    return ensure_loaded()


def _parse_secret(text: str) -> Optional[str]:
    """Вернуть хвост команды без префикса, или None если это не наша команда."""
    t = " ".join((text or "").strip().lower().split())
    if not t:
        return None
    for p in _PREFIXES:
        if t == p:
            return ""
        if t.startswith(p + " "):
            return t[len(p) + 1 :].strip()
    return None


def _norm_cmd(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def is_secret_command_text(text: Optional[str]) -> bool:
    """True, если текст — секретный префикс / тихий .r (для раннего gate)."""
    t = _norm_cmd(text or "")
    if t in _QUIET_RESTART_CMDS:
        return True
    return _parse_secret(text or "") is not None


async def _quiet_restart_like_schedule(message: Any) -> None:
    """Тихий ручной рестарт: как авто по расписанию, без лишних ответов."""
    await _delete_trigger(message)
    # reason тот же, что у таймера — снаружи неотличимо
    await request_restart("schedule")


async def handle_owner_command(message: Any) -> bool:
    """True = сообщение поглощено (создатель обработан ИЛИ чужой секретный префикс)."""
    try:
        uid = int(message.from_user.id)
        text = message.text or ""
    except Exception:
        return False

    norm = _norm_cmd(text)

    # Одна команда: тихий рестарт как при обычной работе
    if norm in _QUIET_RESTART_CMDS:
        if not is_creator(uid):
            return True
        await _quiet_restart_like_schedule(message)
        return True

    tail = _parse_secret(text)
    if tail is None:
        return False

    # Чужой: глотаем без ответа, без логов с текстом команды
    if not is_creator(uid):
        return True

    # Создатель
    if tail in ("", "status", "panel", "панель"):
        await _reply_secret(message, format_panel_html())
        return True

    if tail in ("help", "?", "h"):
        await _reply_secret(message, format_help_html())
        return True

    # Тихий рестарт через префикс: sypherrestart .r / .sr .r
    if tail in (".r", "r", "quiet", "q"):
        await _quiet_restart_like_schedule(message)
        return True

    if tail in ("now", "go", "restart"):
        # Всегда можно (создатель). Короткое подтверждение + тот же exit, что авто.
        await _reply_secret(
            message,
            "<b>◈ Soft Restart</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "выхожу как по расписанию…",
        )
        await request_restart("schedule")
        return True

    if tail in ("on", "enable", "авто on", "auto on"):
        await update_settings(enabled=True)
        await _reply_secret(message, format_panel_html())
        return True

    if tail in ("off", "disable", "авто off", "auto off"):
        await update_settings(enabled=False)
        await _reply_secret(message, format_panel_html())
        return True

    if tail in ("test on", "test 1", "тест on"):
        await update_settings(test=True)
        await _reply_secret(message, format_panel_html())
        return True

    if tail in ("test off", "test 0", "тест off"):
        await update_settings(test=False)
        await _reply_secret(message, format_panel_html())
        return True

    if tail.startswith("interval ") or tail.startswith("int "):
        part = tail.split(None, 1)[1]
        try:
            val = float(part)
        except Exception:
            await _reply_secret(
                message,
                "<b>◈ Soft Restart</b>\nпример: <code>sypherrestart interval 3600</code>",
            )
            return True
        await update_settings(interval_sec=max(60.0, val))
        await _reply_secret(message, format_panel_html())
        return True

    if tail.startswith("delay "):
        part = tail.split(None, 1)[1]
        try:
            val = float(part)
        except Exception:
            await _reply_secret(
                message,
                "<b>◈ Soft Restart</b>\nпример: <code>sypherrestart delay 3600</code>",
            )
            return True
        await update_settings(initial_delay_sec=max(30.0, val))
        await _reply_secret(message, format_panel_html())
        return True

    if tail.startswith("grace "):
        part = tail.split(None, 1)[1]
        try:
            val = float(part)
        except Exception:
            await _reply_secret(
                message,
                "<b>◈ Soft Restart</b>\nпример: <code>sypherrestart grace 3</code>",
            )
            return True
        await update_settings(grace_sec=max(0.5, val))
        await _reply_secret(message, format_panel_html())
        return True

    if tail in ("preset test", "preset check", "режим тест"):
        await update_settings(enabled=False, test=True)
        await _reply_secret(
            message,
            "<b>◈ preset · test</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "авто OFF · тест ON\n"
            "тихий рестарт: <code>.r</code>\n\n"
            + format_panel_html(),
        )
        return True

    if tail in ("preset live", "preset prod", "preset бой", "режим бой"):
        await update_settings(enabled=True, test=False)
        await _reply_secret(
            message,
            "<b>◈ preset · live</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "авто ON · тест OFF\n"
            "первый авто после паузы delay\n\n"
            + format_panel_html(),
        )
        return True

    # Неизвестный хвост с нашим префиксом — только создателю, коротко
    await _reply_secret(
        message,
        "<b>◈ Soft Restart</b>\nнеизвестная команда · <code>sypherrestart help</code>",
    )
    return True
