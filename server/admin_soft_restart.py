# -*- coding: utf-8 -*-
"""Soft Restart bridge for admin panel (creator-only) + полное расписание."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import PROJECT_CREATOR_ID
from sr_schedule import (
    DEFAULT_CFG,
    mode_label,
    normalize_config,
    preview_next_runs,
)

_ALIVE_WINDOW_SEC = 45.0
_TABLE_READY = False
_LAST_PG_ERROR: Optional[str] = None

GUIDE = {
    "title": "Sypher · полный контроль soft restart",
    "subtitle": "Тёмная сторона процесса · только создатель",
    "flow": [
        "Режим interval — рестарт каждые N секунд после паузы с старта процесса.",
        "Режим hourly — каждый час в выбранную минуту (:MM) по timezone.",
        "Режим times — в конкретные HH:MM по выбранным дням недели.",
        "Пауза (initial_delay) — защита: первый авто не раньше этого с момента старта pid.",
        "Условия: мин. аптайм, тихие часы, лимит рестартов/день, только с супервизором.",
        "Панель и игровой бот связаны через Postgres soft_restart_bridge + файлы data/sr_*.",
        "В личку — одно короткое «ок» после реального подъёма нового процесса.",
    ],
}

PARAM_DOCS: Dict[str, Dict[str, Any]] = {
    "enabled": {
        "title": "Авто-рестарт",
        "short": "Включает планировщик в игровом боте.",
        "detail": "ON → task soft_restart_scheduler считает next_at и вызывает request_restart. OFF → только ручной рестарт.",
        "affects": ["is_enabled()", "start_scheduler / reschedule", "_scheduler_loop"],
        "code": "bot/funcs/soft_restart.py",
    },
    "mode": {
        "title": "Режим расписания",
        "short": "interval | hourly | times — как считать следующий рестарт.",
        "detail": "Меняет формулу compute_next_at в sr_schedule.py. От этого зависит весь countdown.",
        "affects": ["compute_next_at", "_arm_next_from_schedule", "upcoming preview"],
        "code": "bot/funcs/sr_schedule.py → compute_next_at",
    },
    "interval_sec": {
        "title": "Интервал (режим interval)",
        "short": "Пауза между авто-рестартами после первого.",
        "detail": "Только для mode=interval. После неудачного тика next = now + interval_sec.",
        "affects": ["compute_next_at(mode=interval)"],
        "code": "bot/funcs/sr_schedule.py",
    },
    "initial_delay_sec": {
        "title": "Пауза после старта",
        "short": "Минимальное время жизни процесса до первого авто.",
        "detail": "earliest = started_at + initial_delay. Работает во всех режимах.",
        "affects": ["compute_next_at earliest", "защита от рестарт-шторма"],
        "code": "bot/funcs/sr_schedule.py",
    },
    "hourly_minute": {
        "title": "Минута часа (hourly)",
        "short": "Каждый час в :MM (например 0 = XX:00).",
        "detail": "Только mode=hourly. Следующий слот HH:MM в timezone.",
        "affects": ["compute_next_at(mode=hourly)"],
        "code": "bot/funcs/sr_schedule.py",
    },
    "daily_times": {
        "title": "Времена дня (times)",
        "short": "Список HH:MM, когда разрешён авто-рестарт.",
        "detail": "Только mode=times. Ближайший слот среди daily_times × weekdays.",
        "affects": ["compute_next_at(mode=times)"],
        "code": "bot/funcs/sr_schedule.py",
    },
    "weekdays": {
        "title": "Дни недели",
        "short": "Пн=0 … Вс=6 — в какие дни работают daily_times.",
        "detail": "Фильтр для mode=times.",
        "affects": ["compute_next_at weekdays filter"],
        "code": "bot/funcs/sr_schedule.py",
    },
    "timezone": {
        "title": "Часовой пояс",
        "short": "IANA tz для hourly/times и тихих часов (по умолчанию Europe/Moscow).",
        "detail": "ZoneInfo(timezone) при расчёте wall-clock.",
        "affects": ["все wall-clock слоты", "quiet hours", "счётчик restarts_today"],
        "code": "bot/funcs/sr_schedule.py → ZoneInfo",
    },
    "grace_sec": {
        "title": "Grace",
        "short": "Задержка перед hard-exit без супервизора.",
        "detail": "Только _perform_hard_exit. На rolling handoff не влияет.",
        "affects": ["_perform_hard_exit"],
        "code": "bot/funcs/soft_restart.py",
    },
    "conditions.min_uptime_sec": {
        "title": "Мин. аптайм",
        "short": "Не рестартовать, пока процесс живёт меньше N секунд.",
        "detail": "conditions_block_reason → skip tick, пересчёт next.",
        "affects": ["_scheduler_loop skip"],
        "code": "bot/funcs/sr_schedule.py → conditions_block_reason",
    },
    "conditions.quiet_start": {
        "title": "Тихие часы (начало)",
        "short": "С этого HH:MM авто-рестарты пропускаются.",
        "detail": "Вместе с quiet_end образует окно (может через полночь).",
        "affects": ["quiet_hours block"],
        "code": "bot/funcs/sr_schedule.py",
    },
    "conditions.quiet_end": {
        "title": "Тихие часы (конец)",
        "short": "До этого HH:MM авто пропускаются.",
        "detail": "Пусто + пустой start = окно выкл.",
        "affects": ["quiet_hours block"],
        "code": "bot/funcs/sr_schedule.py",
    },
    "conditions.max_restarts_per_day": {
        "title": "Лимит рестартов/день",
        "short": "Защита от шторма по календарному дню timezone.",
        "detail": "Счётчик в sr_history.json / status.restarts_today.",
        "affects": ["conditions_block_reason", "record_restart_event"],
        "code": "bot/funcs/soft_restart.py",
    },
    "conditions.require_supervisor": {
        "title": "Только с handoff",
        "short": "Авто только если rolling-супервизор активен.",
        "detail": "Иначе тик пропускается (ручной рестарт всё ещё можно).",
        "affects": ["conditions_block_reason require_supervisor"],
        "code": "bot/funcs/sr_schedule.py",
    },
    "notify_creator": {
        "title": "ЛС после рестарта",
        "short": "Короткое сообщение создателю, когда новый pid жив.",
        "detail": "notify_restart_alive → bot.send_message(CREATOR_ID).",
        "affects": ["maybe_notify_boot"],
        "code": "bot/funcs/soft_restart.py",
    },
    "test": {
        "title": "Тестовый режим",
        "short": "Метка режима (preset test/live).",
        "detail": "Не меняет handoff; влияет на отображение и пресеты.",
        "affects": ["is_test_mode", "presets"],
        "code": "bot/funcs/soft_restart.py",
    },
}


def is_project_creator(user_id: int) -> bool:
    return int(user_id) == int(PROJECT_CREATOR_ID)


def _data_roots() -> List[Path]:
    roots: List[Path] = []
    env = (os.environ.get("SR_DATA_DIR") or "").strip()
    if env:
        roots.append(Path(env))
    here = Path(__file__).resolve()
    roots.append(here.parent / "data")
    roots.append(here.parents[1] / "data")
    roots.append(here.parents[1] / "server" / "data")
    cwd = Path.cwd()
    roots.append(cwd / "data")
    roots.append(cwd / "server" / "data")
    uniq: List[Path] = []
    seen = set()
    for r in roots:
        try:
            key = str(r.resolve()) if r.exists() else str(r)
        except Exception:
            key = str(r)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq


def _paths(name: str) -> List[Path]:
    return [root / name for root in _data_roots()]


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8", errors="ignore")
        except Exception:
            return {}
    if isinstance(value, str) and value.strip():
        try:
            data = json.loads(value)
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json_all(name: str, data: Dict[str, Any]) -> List[str]:
    written: List[str] = []
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    for path in _paths(name):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(path)
            written.append(str(path))
        except Exception as e:
            print(f"[SR-ADMIN] write {path}: {e!r}")
    return written


async def _ensure_table() -> bool:
    global _TABLE_READY, _LAST_PG_ERROR
    if _TABLE_READY:
        return True
    try:
        from db import db

        if db.pool is None:
            _LAST_PG_ERROR = "db.pool is None"
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
        _TABLE_READY = True
        _LAST_PG_ERROR = None
        return True
    except Exception as e:
        _LAST_PG_ERROR = repr(e)
        print(f"[SR-ADMIN] pg table: {e!r}")
        return False


async def _pg_row() -> Optional[Dict[str, Any]]:
    global _LAST_PG_ERROR
    try:
        if not await _ensure_table():
            return None
        from db import db

        row = await db.pool.fetchrow(
            "SELECT config, status, cmd, config_rev, cmd_rev, updated_at "
            "FROM soft_restart_bridge WHERE id = 1"
        )
        if not row:
            return None
        _LAST_PG_ERROR = None
        return {
            "config": _as_dict(row["config"]),
            "status": _as_dict(row["status"]),
            "cmd": _as_dict(row["cmd"]) if row["cmd"] is not None else None,
            "config_rev": int(row["config_rev"] or 0),
            "cmd_rev": int(row["cmd_rev"] or 0),
            "updated_at": row["updated_at"],
        }
    except Exception as e:
        _LAST_PG_ERROR = repr(e)
        print(f"[SR-ADMIN] pg read: {e!r}")
        return None


async def _pg_write_config(cfg: Dict[str, Any]) -> bool:
    global _LAST_PG_ERROR
    try:
        if not await _ensure_table():
            return False
        from db import db

        await db.pool.execute(
            """
            UPDATE soft_restart_bridge
            SET config = $1::jsonb,
                config_rev = config_rev + 1,
                updated_at = NOW()
            WHERE id = 1
            """,
            json.dumps(cfg, ensure_ascii=False),
        )
        _LAST_PG_ERROR = None
        return True
    except Exception as e:
        _LAST_PG_ERROR = repr(e)
        print(f"[SR-ADMIN] pg config: {e!r}")
        return False


async def _pg_write_cmd(cmd: Dict[str, Any]) -> bool:
    global _LAST_PG_ERROR
    try:
        if not await _ensure_table():
            return False
        from db import db

        await db.pool.execute(
            """
            UPDATE soft_restart_bridge
            SET cmd = $1::jsonb,
                cmd_rev = cmd_rev + 1,
                updated_at = NOW()
            WHERE id = 1
            """,
            json.dumps(cmd, ensure_ascii=False),
        )
        _LAST_PG_ERROR = None
        return True
    except Exception as e:
        _LAST_PG_ERROR = repr(e)
        print(f"[SR-ADMIN] pg cmd: {e!r}")
        return False


def _pick_freshest_status(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    best: Dict[str, Any] = {}
    best_ts = -1.0
    for st in candidates:
        if not st:
            continue
        try:
            ts = float(st.get("published_at") or 0)
        except Exception:
            ts = 0.0
        if ts >= best_ts:
            best_ts = ts
            best = st
    return best


def _read_history() -> Dict[str, Any]:
    for path in _paths("sr_history.json"):
        got = _read_json(path)
        if got:
            return got
    return {}


async def load_config() -> Dict[str, Any]:
    row = await _pg_row()
    if row and row.get("config"):
        return normalize_config(row["config"], defaults=dict(DEFAULT_CFG))
    for path in _paths("sr_runtime.json"):
        got = _read_json(path)
        if got:
            return normalize_config(got, defaults=dict(DEFAULT_CFG))
    return normalize_config(None, defaults=dict(DEFAULT_CFG))


async def load_status() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    now = time.time()
    file_infos = []
    file_statuses: List[Dict[str, Any]] = []
    for path in _paths("sr_status.json"):
        exists = path.is_file()
        age = None
        st = _read_json(path) if exists else None
        if st:
            file_statuses.append(st)
            try:
                pub = float(st.get("published_at") or 0)
                age = round(max(0.0, now - pub), 1) if pub else None
            except Exception:
                age = None
        file_infos.append({"path": str(path), "exists": exists, "age_sec": age})

    row = await _pg_row()
    pg_status = row.get("status") if row else {}
    pg_ok = row is not None
    candidates = list(file_statuses)
    if pg_status:
        candidates.append(pg_status)
    st = _pick_freshest_status(candidates)
    hist = _read_history()
    if not st.get("last_restart_at") and hist.get("last_restart_at") is not None:
        st = dict(st)
        st["last_restart_at"] = hist.get("last_restart_at")
        st["last_restart_reason"] = hist.get("last_restart_reason")
        st["restarts_today"] = hist.get("restarts_today")
        if isinstance(hist.get("events"), list) and not st.get("history"):
            st["history"] = hist["events"][-12:]

    published = 0.0
    try:
        published = float(st.get("published_at") or 0)
    except Exception:
        published = 0.0
    age = (now - published) if published else None
    alive = bool(published and age is not None and age < _ALIVE_WINDOW_SEC)
    stale = bool(published and age is not None and not alive)

    next_at = st.get("next_at")
    next_in = None
    if next_at is not None:
        try:
            next_in = round(max(0.0, float(next_at) - now), 3)
        except Exception:
            next_in = None

    last_at = st.get("last_restart_at")
    since_last = None
    if last_at is not None:
        try:
            since_last = round(max(0.0, now - float(last_at)), 1)
        except Exception:
            since_last = None

    if alive:
        hint = "Игровой бот на связи · heartbeat свежий."
    elif stale:
        hint = f"Последний heartbeat {age:.0f}с назад. Бот завис или код bridge ещё не задеплоен."
    else:
        hint = (
            "Нет heartbeat. Перезапусти игровой main.py с новым soft_restart. "
            "API и бот — одна Postgres (soft_restart_bridge) или общие data/sr_status.json."
        )

    diagnostics = {
        "alive_window_sec": _ALIVE_WINDOW_SEC,
        "pg_ok": pg_ok,
        "pg_error": _LAST_PG_ERROR,
        "pg_has_status": bool(pg_status and pg_status.get("published_at")),
        "pg_config_rev": int(row["config_rev"]) if row else None,
        "files": file_infos,
        "status_age_sec": None if age is None else round(age, 1),
        "stale": stale,
        "hint": hint,
        "data_roots": [str(r) for r in _data_roots()],
    }

    status = {
        "alive": alive,
        "stale": stale,
        "published_at": published or None,
        "pid": st.get("pid"),
        "uptime_sec": st.get("uptime_sec"),
        "started_at": st.get("started_at"),
        "next_at": next_at,
        "next_in_sec": next_in,
        "upcoming": st.get("upcoming") or [],
        "requested": bool(st.get("requested")),
        "last_reason": st.get("last_reason"),
        "last_restart_at": last_at,
        "last_restart_reason": st.get("last_restart_reason"),
        "since_last_restart_sec": since_last if since_last is not None else st.get("since_last_restart_sec"),
        "restarts_today": st.get("restarts_today"),
        "history": st.get("history") or [],
        "block_reason": st.get("block_reason"),
        "mode": st.get("mode"),
        "mode_label": st.get("mode_label"),
        "handoff": bool(st.get("handoff") or st.get("supervisor")),
        "supervisor": bool(st.get("supervisor")),
        "applied": _as_dict(st.get("applied")) or None,
        "bridge_ok": bool(st.get("bridge_ok")),
        "server_now": now,
    }
    return status, diagnostics


async def overview() -> Dict[str, Any]:
    cfg = await load_config()
    status, diagnostics = await load_status()
    started = float(status.get("started_at") or (time.time() - float(status.get("uptime_sec") or 0)))
    if not status.get("upcoming"):
        status["upcoming"] = preview_next_runs(cfg, started_at=started, count=8)
    return {
        "config": cfg,
        "status": status,
        "diagnostics": diagnostics,
        "guide": GUIDE,
        "creatorId": int(PROJECT_CREATOR_ID),
        "paramHelp": {k: v["short"] for k, v in PARAM_DOCS.items()},
        "paramDocs": PARAM_DOCS,
        "modeLabel": mode_label(str(cfg.get("mode") or "interval")),
    }


async def save_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    cfg = await load_config()
    for k, v in patch.items():
        if v is None:
            continue
        if k == "conditions" and isinstance(v, dict):
            cur = dict(cfg.get("conditions") or {})
            cur.update(v)
            cfg["conditions"] = cur
        else:
            cfg[k] = v
    cfg = normalize_config(cfg, defaults=dict(DEFAULT_CFG))
    _write_json_all("sr_runtime.json", cfg)
    await _pg_write_config(cfg)
    cmd = {"op": "apply", "config": cfg, "ts": time.time()}
    _write_json_all("sr_cmd.json", cmd)
    await _pg_write_cmd(cmd)
    return cfg


async def queue_restart(reason: str = "panel") -> Dict[str, Any]:
    cmd = {"op": "restart", "reason": str(reason or "panel")[:64], "ts": time.time()}
    written = _write_json_all("sr_cmd.json", cmd)
    pg_ok = await _pg_write_cmd(cmd)
    return {"ok": True, "queued": True, "cmd": cmd, "pg_ok": pg_ok, "files": written}


async def apply_preset(name: str) -> Dict[str, Any]:
    n = (name or "").strip().lower()
    if n in ("live", "prod", "бой"):
        return await save_settings({"enabled": True, "test": False, "mode": "interval", "interval_sec": 3600, "initial_delay_sec": 3600})
    if n in ("hourly", "час"):
        return await save_settings({"enabled": True, "test": False, "mode": "hourly", "hourly_minute": 0, "initial_delay_sec": 120})
    if n in ("night", "ночь"):
        return await save_settings({"enabled": True, "test": False, "mode": "times", "daily_times": ["03:00"], "weekdays": [0, 1, 2, 3, 4, 5, 6], "initial_delay_sec": 120})
    if n in ("test", "check", "тест"):
        return await save_settings({"enabled": False, "test": True})
    raise ValueError("unknown preset")
