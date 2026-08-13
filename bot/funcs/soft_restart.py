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
_REDIS_STATUS_KEY = "cg:sr:status"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = Path(os.environ.get("SR_DATA_DIR") or (_REPO_ROOT / "data"))
_FILE_PATH = _DATA_DIR / "sr_runtime.json"
_STATUS_PATH = _DATA_DIR / "sr_status.json"
_CMD_PATH = _DATA_DIR / "sr_cmd.json"
_SR_DIR = Path(os.environ.get("SR_DIR", "/tmp/cg_sr"))
_bridge_last_error: str = ""


def _data_roots() -> list:
    roots = []
    env = (os.environ.get("SR_DATA_DIR") or "").strip()
    if env:
        roots.append(Path(env))
    roots.append(_REPO_ROOT / "data")
    roots.append(_REPO_ROOT / "server" / "data")
    uniq = []
    seen = set()
    for r in roots:
        key = str(r)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq


def _paths(name: str) -> list:
    return [root / name for root in _data_roots()]

_lock = asyncio.Lock()
_cfg_lock = asyncio.Lock()
_requested = False
_started_at = time.time()
_next_at: Optional[float] = None
_last_reason = ""
_scheduler_task: Optional[asyncio.Task] = None
_release_watch_task: Optional[asyncio.Task] = None
_bridge_task: Optional[asyncio.Task] = None
_dp_ref = None
_notify_fn: Optional[NotifyFn] = None
_cfg: Optional[Dict[str, Any]] = None
_loaded = False
_last_cmd_ts: float = 0.0
_last_cfg_rev: int = -1
_bridge_table_ready = False
_boot_notified = False


def sr_dir() -> Path:
    return _SR_DIR


def supervisor_active() -> bool:
    """True, если нас запустил sr_supervisor (rolling handoff доступен)."""
    if (os.getenv("SR_SUPERVISOR") or "").strip() in ("1", "true", "yes", "on"):
        return True
    return (_SR_DIR / "supervisor_alive").exists()


def is_handoff_child() -> bool:
    return (os.getenv("SR_HANDOFF_CHILD") or "").strip() in ("1", "true", "yes", "on")


def _flag_path(name: str) -> Path:
    return _SR_DIR / name


def _write_flag(name: str, text: str = "1") -> None:
    _SR_DIR.mkdir(parents=True, exist_ok=True)
    _flag_path(name).write_text(text, encoding="utf-8")


def _clear_flag(name: str) -> None:
    try:
        _flag_path(name).unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def mark_child_ready() -> None:
    """Warmup закончен — можно отпускать старый процесс."""
    _write_flag("child_ready")
    print("[SR] child_ready", flush=True)


async def wait_child_go(*, timeout: float = 180.0) -> bool:
    """Ждём сигнал супервизора, что старый отпустил очередь."""
    path = _flag_path("child_go")
    t0 = time.time()
    print("[SR] handoff child: waiting for child_go…", flush=True)
    while time.time() - t0 < timeout:
        if path.exists():
            print("[SR] child_go received — starting traffic", flush=True)
            return True
        await asyncio.sleep(0.15)
    print("[SR] child_go TIMEOUT", flush=True)
    return False


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
    payload = json.dumps(cfg, ensure_ascii=False, indent=2)
    for path in _paths("sr_runtime.json"):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(path)
        except Exception as e:
            print(f"[SR] file write {path}: {e!r}")


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


def _read_any_runtime_file() -> Optional[Dict[str, Any]]:
    for path in _paths("sr_runtime.json"):
        try:
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return _read_file()


def ensure_loaded() -> Dict[str, Any]:
    global _cfg, _loaded
    if _loaded and _cfg is not None:
        return _cfg
    cfg = _defaults_from_env()
    for src in (_read_redis, _read_any_runtime_file):
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
    try:
        _publish_status_sync()
    except Exception:
        pass


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
    cfg = ensure_loaded()
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
        "handoff": supervisor_active(),
        "supervisor": supervisor_active(),
        "published_at": now,
        "bridge_ok": True,
        "bridge_error": _bridge_last_error or None,
        "applied": {
            "enabled": bool(cfg.get("enabled")),
            "test": bool(cfg.get("test")),
            "interval_sec": float(cfg.get("interval_sec")),
            "initial_delay_sec": float(cfg.get("initial_delay_sec")),
            "grace_sec": float(cfg.get("grace_sec")),
        },
    }


def _publish_status_sync() -> None:
    """Снимок для админ-панели во все известные data/ + Redis."""
    st = status_dict()
    payload = json.dumps(st, ensure_ascii=False)
    for path in _paths("sr_status.json"):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(path)
        except Exception as e:
            print(f"[SR] status file {path}: {e!r}")
    try:
        r = _redis_client()
        if r is not None:
            r.set(_REDIS_STATUS_KEY, payload)
    except Exception as e:
        print(f"[SR] status redis: {e!r}")


async def _bridge_ensure_table() -> bool:
    global _bridge_table_ready, _bridge_last_error
    if _bridge_table_ready:
        return True
    try:
        from bot.db_create.db import db

        if getattr(db, "pool", None) is None:
            _bridge_last_error = "db.pool is None"
            return False
        await db.pool.execute(
            """
            CREATE TABLE IF NOT EXISTS soft_restart_bridge (
                id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                config JSONB NOT NULL DEFAULT '{}'::jsonb,
                status JSONB NOT NULL DEFAULT '{}'::jsonb,
                cmd JSONB,
                config_rev BIGINT NOT NULL DEFAULT 0,
                cmd_rev BIGINT NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            INSERT INTO soft_restart_bridge (id) VALUES (1)
            ON CONFLICT (id) DO NOTHING;
            """
        )
        _bridge_table_ready = True
        _bridge_last_error = ""
        return True
    except Exception as e:
        _bridge_last_error = repr(e)
        print(f"[SR] bridge table: {e!r}")
        return False


async def _bridge_publish_status() -> None:
    global _bridge_last_error
    st = status_dict()
    _publish_status_sync()
    try:
        if not await _bridge_ensure_table():
            return
        from bot.db_create.db import db

        await db.pool.execute(
            """
            UPDATE soft_restart_bridge
            SET status = $1::jsonb, updated_at = NOW()
            WHERE id = 1
            """,
            json.dumps(st, ensure_ascii=False),
        )
        _bridge_last_error = ""
    except Exception as e:
        _bridge_last_error = repr(e)
        print(f"[SR] bridge status: {e!r}")


async def _bridge_push_config() -> None:
    global _bridge_last_error
    cfg = ensure_loaded()
    # Дублируем runtime-файл во все корни — панель читает server/data и repo/data
    payload = json.dumps(cfg, ensure_ascii=False, indent=2)
    for path in _paths("sr_runtime.json"):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(path)
        except Exception as e:
            print(f"[SR] runtime file {path}: {e!r}")
    try:
        if not await _bridge_ensure_table():
            return
        from bot.db_create.db import db

        await db.pool.execute(
            """
            UPDATE soft_restart_bridge
            SET config = $1::jsonb, updated_at = NOW()
            WHERE id = 1
            """,
            json.dumps(cfg, ensure_ascii=False),
        )
        _bridge_last_error = ""
    except Exception as e:
        _bridge_last_error = repr(e)
        print(f"[SR] bridge config push: {e!r}")


async def notify_restart_alive(reason: str = "ok") -> None:
    """Одно короткое ЛС создателю: процесс реально поднялся после рестарта."""
    global _boot_notified
    if _boot_notified:
        return
    _boot_notified = True
    reason = (reason or "ok").strip()[:48] or "ok"
    await _notify(
        f"◈ soft restart · <code>{reason}</code> · pid <code>{os.getpid()}</code> · ок"
    )


async def maybe_notify_boot() -> None:
    """Пинг только если это handoff-child или есть флаг после hard-exit."""
    path = _flag_path("notify_on_boot")
    reason = ""
    if path.exists():
        try:
            reason = path.read_text(encoding="utf-8").strip() or "restart"
        except Exception:
            reason = "restart"
        _clear_flag("notify_on_boot")
        await notify_restart_alive(reason)
        return
    if is_handoff_child():
        await notify_restart_alive(_last_reason or "handoff")


async def apply_external_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Применить конфиг из админ-панели (файл/PG cmd)."""
    global _cfg, _loaded
    async with _cfg_lock:
        _cfg = _normalize(raw if isinstance(raw, dict) else {})
        _loaded = True
        _persist()
    await reschedule()
    await _bridge_publish_status()
    return ensure_loaded()


async def _consume_cmd(cmd: Dict[str, Any]) -> None:
    global _last_cmd_ts
    if not isinstance(cmd, dict):
        return
    ts = float(cmd.get("ts") or 0)
    if ts and ts <= _last_cmd_ts:
        return
    if ts:
        _last_cmd_ts = ts
    op = str(cmd.get("op") or "").strip().lower()
    if op == "apply":
        cfg = cmd.get("config")
        if isinstance(cfg, dict):
            await apply_external_config(cfg)
            print("[SR] panel apply config", flush=True)
        return
    if op == "restart":
        reason = str(cmd.get("reason") or "panel")[:64]
        print(f"[SR] panel restart reason={reason!r}", flush=True)
        await request_restart(reason)
        return


def _cmd_as_dict(raw) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8", errors="ignore")
        except Exception:
            return None
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None


async def _poll_bridge_once() -> None:
    global _last_cfg_rev, _bridge_last_error
    # 1) файлы команды во всех корнях
    for path in _paths("sr_cmd.json"):
        file_cmd = None
        try:
            if path.is_file():
                file_cmd = _cmd_as_dict(path.read_text(encoding="utf-8"))
        except Exception:
            file_cmd = None
        if isinstance(file_cmd, dict):
            await _consume_cmd(file_cmd)
            try:
                path.unlink()
            except Exception:
                pass

    # 2) Postgres
    try:
        if not await _bridge_ensure_table():
            return
        from bot.db_create.db import db

        row = await db.pool.fetchrow(
            "SELECT config, cmd, config_rev, cmd_rev FROM soft_restart_bridge WHERE id = 1"
        )
        if not row:
            return
        crev = int(row["config_rev"] or 0)
        if crev > _last_cfg_rev:
            _last_cfg_rev = crev
            cfg = row["config"]
            if isinstance(cfg, str):
                cfg = _cmd_as_dict(cfg)
            if isinstance(cfg, dict) and cfg:
                cur = ensure_loaded()
                norm = _normalize(cfg)
                if any(cur.get(k) != norm.get(k) for k in norm):
                    await apply_external_config(norm)
                    print(f"[SR] bridge config_rev={crev}", flush=True)
        cmd = _cmd_as_dict(row["cmd"])
        if isinstance(cmd, dict):
            await _consume_cmd(cmd)
            await db.pool.execute(
                "UPDATE soft_restart_bridge SET cmd = NULL WHERE id = 1"
            )
        _bridge_last_error = ""
    except Exception as e:
        _bridge_last_error = repr(e)
        print(f"[SR] bridge poll: {e!r}")


async def _bridge_loop() -> None:
    try:
        await _bridge_push_config()
        while True:
            try:
                await _poll_bridge_once()
                await _bridge_publish_status()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[SR] bridge loop: {e!r}")
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        raise


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
        "тихий рестарт → <code>.r</code>\n"
        f"handoff  <b>{'ON' if supervisor_active() else 'OFF'}</b>"
    )


def format_help_html() -> str:
    return (
        "<b>◈ Soft Restart · команды</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Основная настройка — вкладка <b>Sypher</b> в админ-панели (только создатель).\n"
        "Пиши в <b>личку</b> боту. Чужим — тишина.\n"
        "После рестарта — одно короткое ЛС <code>◈ soft restart · … · ок</code>.\n\n"
        "<b>Тихий рестарт (rolling, как деплой)</b>\n"
        "<code>.r</code>\n"
        "  новый процесс греется · старый ещё отвечает ·\n"
        "  потом короткий обмен · люди почти не ждут\n\n"

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
        "Rolling handoff: новый греется → старый отпускает → новый принимает.\n"
        "Код с git не обновляется (тот же образ)."
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


async def _stop_polling_graceful() -> None:
    dp = _dp_ref
    if dp is None:
        return
    try:
        if hasattr(dp, "stop_polling"):
            await dp.stop_polling()
            print("[SR] dp.stop_polling() ok", flush=True)
    except Exception as e:
        print(f"[SR] stop_polling: {e!r}", flush=True)


def _flush_pkl_for_buttons() -> dict:
    """Сбросить все GameStore в Redis — иначе кнопки умрут после os._exit."""
    try:
        from bot.runtime.button_survival import protect_before_restart

        return protect_before_restart(wait_timeout=12.0) or {}
    except Exception as e:
        print(f"[SR][PKL] flush fail: {type(e).__name__}: {e}", flush=True)
        return {"error": repr(e)}


async def _release_and_exit(reason: str) -> None:
    """Старый процесс: flush pkl → отпустить очередь → выйти.

    Критично: os._exit обходит atexit. Без flush токены greq/prep/игры
    не попадут в Redis → новый процесс не увидит сессии кнопок.
    """
    global _requested, _last_reason
    _requested = True
    _last_reason = reason
    print(f"[SR] release_and_exit reason={reason!r} pid={os.getpid()}", flush=True)

    # 1) Первый flush — пока ещё можем дописать in-flight
    flush1 = await asyncio.to_thread(_flush_pkl_for_buttons)
    print(f"[SR][PKL] pre-stop flush: {flush1}", flush=True)

    # 2) Стоп polling — новых кликов больше нет
    await _stop_polling_graceful()
    await asyncio.sleep(0.4)

    # 3) Финальный flush — добрать хвост handler'ов
    flush2 = await asyncio.to_thread(_flush_pkl_for_buttons)
    print(f"[SR][PKL] final flush: {flush2}", flush=True)
    _write_flag("pkl_flushed", "1")

    _write_flag("old_released")
    await asyncio.sleep(0.35)
    print("[SR] old_released → exit 0", flush=True)
    os._exit(0)


async def _perform_handoff_request(reason: str) -> None:
    """Rolling handoff через супервизор (новый сначала, потом старый)."""
    global _requested, _last_reason
    _requested = True
    _last_reason = reason
    print(f"[SR] handoff_request reason={reason!r}", flush=True)
    # Без спама: короткое «ок» пришлёт уже новый процесс (maybe_notify_boot).
    _write_flag("notify_on_boot", reason)
    _clear_flag("child_ready")
    _clear_flag("child_go")
    _clear_flag("release_old")
    _clear_flag("old_released")
    _clear_flag("pkl_flushed")
    _write_flag("handoff_request", reason)


async def _perform_hard_exit(reason: str) -> None:
    """Fallback без супервизора: stop + exit (будет простой до нового старта)."""
    global _requested, _last_reason
    _requested = True
    _last_reason = reason
    print(f"[SR] hard exit (no supervisor) reason={reason!r}", flush=True)
    _write_flag("notify_on_boot", reason)
    await asyncio.sleep(grace_sec())
    flush1 = await asyncio.to_thread(_flush_pkl_for_buttons)
    print(f"[SR][PKL] hard pre-stop flush: {flush1}", flush=True)
    await _stop_polling_graceful()
    await asyncio.sleep(0.4)
    flush2 = await asyncio.to_thread(_flush_pkl_for_buttons)
    print(f"[SR][PKL] hard final flush: {flush2}", flush=True)
    await asyncio.sleep(0.3)
    os._exit(0)


async def request_restart(reason: str = "manual", *, force: bool = False) -> bool:
    global _requested
    async with _lock:
        if _requested and not force:
            return False
        _requested = True
    if supervisor_active():
        asyncio.create_task(_perform_handoff_request(reason))
    else:
        asyncio.create_task(_perform_hard_exit(reason))
    return True


async def _watch_release_old() -> None:
    """Супервизор просит отпустить очередь — новый уже готов."""
    path = _flag_path("release_old")
    try:
        while True:
            if path.exists():
                await _release_and_exit(_last_reason or "handoff")
                return
            await asyncio.sleep(0.15)
    except asyncio.CancelledError:
        raise


def _arm_next_at(delay: Optional[float] = None) -> float:
    """Сразу выставить «далее через …» для панели (до первого тика task)."""
    global _next_at
    ensure_loaded()
    d = float(delay if delay is not None else initial_delay_sec())
    d = max(0.0, d)
    _next_at = time.time() + d
    try:
        _publish_status_sync()
    except Exception:
        pass
    return d


async def _scheduler_loop() -> None:
    global _next_at
    ensure_loaded()
    if not is_enabled():
        print("[SR] scheduler off")
        _next_at = None
        return
    delay = _arm_next_at(initial_delay_sec())
    interval = interval_sec()
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
            _arm_next_at(interval)
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
    global _scheduler_task, _release_watch_task, _bridge_task, _started_at
    ensure_loaded()
    bind(dp=dp, notify=notify)
    _started_at = time.time()

    # release_old смотрит только «старый» процесс. Handoff-child — нет,
    # иначе оба выйдут одновременно.
    if (
        supervisor_active()
        and not is_handoff_child()
        and (_release_watch_task is None or _release_watch_task.done())
    ):
        _release_watch_task = asyncio.create_task(
            _watch_release_old(), name="soft_restart_release_watch"
        )
        print("[SR] release_old watcher on (rolling handoff)", flush=True)

    if _bridge_task is None or _bridge_task.done():
        _bridge_task = asyncio.create_task(_bridge_loop(), name="soft_restart_bridge")
        print("[SR] panel bridge on", flush=True)

    # Короткий пинг создателю только после реального рестарта
    asyncio.create_task(maybe_notify_boot(), name="soft_restart_boot_notify")

    if _scheduler_task and not _scheduler_task.done():
        return _scheduler_task
    if not is_enabled():
        print("[SR] auto off — waiting for creator commands / panel")
        _publish_status_sync()
        return None
    _arm_next_at(initial_delay_sec())
    _scheduler_task = asyncio.create_task(_scheduler_loop(), name="soft_restart_scheduler")
    return _scheduler_task


async def reschedule() -> None:
    """Перезапустить планировщик после смены настроек."""
    global _scheduler_task, _next_at
    _cancel_scheduler()
    await asyncio.sleep(0)  # дать отмениться
    if is_enabled():
        # Сразу для панели — иначе «ещё не в расписании» до тика loop
        _arm_next_at(initial_delay_sec())
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
    try:
        await _bridge_push_config()
        await _bridge_publish_status()
    except Exception:
        pass
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
        # Тихо: подтверждение — одно короткое ЛС после подъёма нового процесса.
        await _delete_trigger(message)
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
