# -*- coding: utf-8 -*-
"""Soft Restart bridge for admin panel (creator-only).

Связь с игровым ботом (берём самый свежий источник):
  • Postgres soft_restart_bridge (если API и бот смотрят в одну БД)
  • файлы data/sr_*.json в нескольких известных корнях репозитория
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import PROJECT_CREATOR_ID

_ALIVE_WINDOW_SEC = 45.0
_TABLE_READY = False
_LAST_PG_ERROR: Optional[str] = None

DEFAULT_CFG: Dict[str, Any] = {
    "enabled": False,
    "test": False,
    "interval_sec": 3600.0,
    "initial_delay_sec": 3600.0,
    "grace_sec": 3.0,
}

GUIDE = {
    "title": "Скрытый Soft Restart (Sypher)",
    "subtitle": "Тёмная сторона процесса · только создатель",
    "flow": [
        "Авто — планировщик в игровом боте сам вызывает request_restart по таймеру.",
        "Пауза (initial_delay) — первый sleep после старта процесса / после «Сохранить».",
        "Интервал — sleep между следующими рестартами, если предыдущий не убил процесс.",
        "Grace — sleep только в hard-exit (нет rolling-супервизора) перед stop_polling.",
        "Live = enabled ON + test OFF. Test = enabled OFF + test ON (ручные проверки).",
        "«Рестарт сейчас» пишет cmd в bridge → бот вызывает request_restart (как .r).",
        "В личку — одно короткое «◈ soft restart · … · ок», когда новый pid реально жив.",
        "Если пульс offline — игровой бот не публикует heartbeat (нужен рестарт/деплой main.py).",
    ],
}

# Подробно: что крутит тумблер/ползунок в коде.
PARAM_DOCS: Dict[str, Dict[str, Any]] = {
    "enabled": {
        "title": "Авто-рестарт",
        "short": "Главный выключатель планировщика мягкого рестарта.",
        "detail": (
            "ON — после старта бота крутится _scheduler_loop: сначала ждёт паузу, "
            "потом периодически вызывает request_restart(\"schedule\"). "
            "OFF — цикл не стартует / останавливается; остаются только ручные "
            "«Рестарт сейчас», .r и sypherrestart now."
        ),
        "affects": [
            "is_enabled() → bool из cfg[\"enabled\"]",
            "start_scheduler() создаёт task soft_restart_scheduler только при ON",
            "reschedule() после сохранения с панели пересоздаёт/гасит планировщик",
            "в _scheduler_loop при OFF → выход и next_at = None",
        ],
        "code": "bot/funcs/soft_restart.py → is_enabled, start_scheduler, reschedule, _scheduler_loop",
    },
    "test": {
        "title": "Тестовый режим",
        "short": "Метка режима для панели и пресетов (не меняет сам алгоритм handoff).",
        "detail": (
            "Флаг cfg[\"test\"] / is_test_mode(). Пресет Test включает его и гасит авто; "
            "Live выключает. На rolling handoff и flush кнопок не влияет — только "
            "отображение «режим бой/тест» и дисциплина настроек."
        ),
        "affects": [
            "is_test_mode() и поле test_mode в status/panel",
            "preset test → enabled=False, test=True",
            "preset live → enabled=True, test=False",
        ],
        "code": "bot/funcs/soft_restart.py → is_test_mode, update_settings, preset handlers",
    },
    "initial_delay_sec": {
        "title": "Пауза до первого рестарта",
        "short": "Сколько секунд ждать после старта процесса (или после apply) до первого авто.",
        "detail": (
            "Попадает в cfg[\"initial_delay_sec\"] (мин. 30с). "
            "_arm_next_at(initial_delay_sec()) выставляет next_at = now + pause. "
            "_scheduler_loop делает await asyncio.sleep(delay) один раз, затем входит "
            "в цикл интервалов. Именно это число ты видишь в живом отсчёте сразу после Live."
        ),
        "affects": [
            "initial_delay_sec() / _arm_next_at / первый sleep в _scheduler_loop",
            "status.next_at и countdown в вкладке Sypher",
            "при каждом apply/reschedule отсчёт начинается заново с этой паузы",
        ],
        "code": "bot/funcs/soft_restart.py → initial_delay_sec, _arm_next_at, _scheduler_loop",
    },
    "interval_sec": {
        "title": "Интервал между рестартами",
        "short": "Пауза между попытками авто-рестарта после первой.",
        "detail": (
            "cfg[\"interval_sec\"] (мин. 60с). После неудачного/незавершённого request_restart "
            "планировщик делает _arm_next_at(interval) и sleep(interval). "
            "Если request_restart вернул True (рестарт принят), цикл завершается — "
            "новый процесс снова стартует с initial_delay."
        ),
        "affects": [
            "interval_sec() во втором и дальнейших тиках _scheduler_loop",
            "частота schedule-рестартов в «бою»",
            "не влияет на ручной .r / «Рестарт сейчас»",
        ],
        "code": "bot/funcs/soft_restart.py → interval_sec, _scheduler_loop",
    },
    "grace_sec": {
        "title": "Grace (жёсткий выход)",
        "short": "Задержка перед stop_polling, если нет rolling-супервизора.",
        "detail": (
            "Используется только в _perform_hard_exit (SR_SUPERVISOR выкл / нет флагов). "
            "await asyncio.sleep(grace_sec()) → flush pkl → stop_polling → os._exit. "
            "При rolling handoff grace не участвует: старый ждёт release_old от супервизора."
        ),
        "affects": [
            "grace_sec() в _perform_hard_exit",
            "как быстро оборвётся polling без handoff",
            "не влияет на _perform_handoff_request",
        ],
        "code": "bot/funcs/soft_restart.py → grace_sec, _perform_hard_exit",
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
    # server/admin_soft_restart.py → server/data и repo/data
    roots.append(here.parent / "data")
    roots.append(here.parents[1] / "data")
    roots.append(here.parents[1] / "server" / "data")
    # cwd fallbacks
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


def _normalize(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = dict(DEFAULT_CFG)
    if isinstance(raw, dict):
        for k in base:
            if k in raw:
                base[k] = raw[k]
    base["enabled"] = bool(base["enabled"])
    base["test"] = bool(base["test"])
    base["interval_sec"] = max(60.0, float(base["interval_sec"]))
    base["initial_delay_sec"] = max(30.0, float(base["initial_delay_sec"]))
    base["grace_sec"] = max(0.5, float(base["grace_sec"]))
    return base


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


async def load_config() -> Dict[str, Any]:
    row = await _pg_row()
    if row and row.get("config"):
        return _normalize(row["config"])
    for path in _paths("sr_runtime.json"):
        got = _read_json(path)
        if got:
            return _normalize(got)
    return _normalize(None)


async def load_status() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Вернуть (status_for_ui, diagnostics)."""
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
        file_infos.append(
            {
                "path": str(path),
                "exists": exists,
                "age_sec": age,
            }
        )

    row = await _pg_row()
    pg_status = row.get("status") if row else {}
    pg_ok = row is not None
    candidates = list(file_statuses)
    if pg_status:
        candidates.append(pg_status)
    st = _pick_freshest_status(candidates)

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

    applied = _as_dict(st.get("applied"))

    if alive:
        hint = "Игровой бот на связи · heartbeat свежий."
    elif stale:
        hint = (
            f"Последний heartbeat {age:.0f}с назад (окно {_ALIVE_WINDOW_SEC:.0f}с). "
            "Бот завис, умер или ещё не обновлён новым soft_restart."
        )
    else:
        hint = (
            "Нет heartbeat от игрового бота. "
            "Нужен деплой/рестарт процесса main.py (не admin-bot) с кодом bridge. "
            "API и бот должны видеть одну Postgres (таблица soft_restart_bridge) "
            "или общие файлы data/sr_status.json."
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
        "next_at": next_at,
        "next_in_sec": next_in,
        "requested": bool(st.get("requested")),
        "last_reason": st.get("last_reason"),
        "handoff": bool(st.get("handoff") or st.get("supervisor")),
        "supervisor": bool(st.get("supervisor")),
        "applied": applied or None,
        "bridge_ok": bool(st.get("bridge_ok")),
        "server_now": now,
    }
    return status, diagnostics


async def overview() -> Dict[str, Any]:
    cfg = await load_config()
    status, diagnostics = await load_status()
    return {
        "config": cfg,
        "status": status,
        "diagnostics": diagnostics,
        "guide": GUIDE,
        "creatorId": int(PROJECT_CREATOR_ID),
        "paramHelp": {k: v["short"] for k, v in PARAM_DOCS.items()},
        "paramDocs": PARAM_DOCS,
    }


async def save_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    cfg = await load_config()
    for k, v in patch.items():
        if k in cfg and v is not None:
            cfg[k] = v
    cfg = _normalize(cfg)
    _write_json_all("sr_runtime.json", cfg)
    await _pg_write_config(cfg)
    cmd = {
        "op": "apply",
        "config": cfg,
        "ts": time.time(),
    }
    _write_json_all("sr_cmd.json", cmd)
    await _pg_write_cmd(cmd)
    return cfg


async def queue_restart(reason: str = "panel") -> Dict[str, Any]:
    cmd = {
        "op": "restart",
        "reason": str(reason or "panel")[:64],
        "ts": time.time(),
    }
    written = _write_json_all("sr_cmd.json", cmd)
    pg_ok = await _pg_write_cmd(cmd)
    return {
        "ok": True,
        "queued": True,
        "cmd": cmd,
        "pg_ok": pg_ok,
        "files": written,
    }


async def apply_preset(name: str) -> Dict[str, Any]:
    n = (name or "").strip().lower()
    if n in ("live", "prod", "бой"):
        return await save_settings({"enabled": True, "test": False})
    if n in ("test", "check", "тест"):
        return await save_settings({"enabled": False, "test": True})
    raise ValueError("unknown preset")
