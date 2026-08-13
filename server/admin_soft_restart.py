# -*- coding: utf-8 -*-
"""Soft Restart bridge for admin panel (creator-only).

Связь с игровым ботом:
  • общий каталог data/sr_*.json (если процессы на одном хосте)
  • таблица soft_restart_bridge в Postgres (если общая БД)

Бот публикует status и читает config/cmd. Панель только пишет команды и читает статус.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from config import PROJECT_CREATOR_ID

_DATA_DIR = Path(os.environ.get("SR_DATA_DIR") or (Path(__file__).resolve().parents[1] / "data"))
_CFG_PATH = _DATA_DIR / "sr_runtime.json"
_STATUS_PATH = _DATA_DIR / "sr_status.json"
_CMD_PATH = _DATA_DIR / "sr_cmd.json"

_TABLE_READY = False

DEFAULT_CFG: Dict[str, Any] = {
    "enabled": False,
    "test": False,
    "interval_sec": 3600.0,
    "initial_delay_sec": 3600.0,
    "grace_sec": 3.0,
}

GUIDE = {
    "title": "Скрытый Soft Restart",
    "subtitle": "Тёмная сторона процесса · только создатель",
    "flow": [
        "Авто — бот сам делает rolling-рестарт по таймеру, игроки почти не замечают.",
        "Пауза — сколько ждать после старта процесса до первого авто-рестарта.",
        "Интервал — как часто повторять рестарт после первого.",
        "Grace — короткая задержка перед жёстким выходом, если супервизора нет.",
        "Live — авто ON, тест OFF. Test — авто OFF, удобно проверять руками.",
        "«Рестарт сейчас» — тот же путь, что и по расписанию (rolling handoff).",
        "В личку приходит одно короткое сообщение, когда новый процесс реально жив.",
    ],
}


def is_project_creator(user_id: int) -> bool:
    return int(user_id) == int(PROJECT_CREATOR_ID)


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


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


async def _ensure_table() -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return
    from db import db

    if db.pool is None:
        return
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


async def _pg_row() -> Optional[Dict[str, Any]]:
    try:
        await _ensure_table()
        from db import db

        if db.pool is None:
            return None
        row = await db.pool.fetchrow(
            "SELECT config, status, cmd, config_rev, cmd_rev, updated_at "
            "FROM soft_restart_bridge WHERE id = 1"
        )
        if not row:
            return None
        return dict(row)
    except Exception as e:
        print(f"[SR-ADMIN] pg read: {e!r}")
        return None


async def _pg_write_config(cfg: Dict[str, Any]) -> None:
    try:
        await _ensure_table()
        from db import db

        if db.pool is None:
            return
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
    except Exception as e:
        print(f"[SR-ADMIN] pg config: {e!r}")


async def _pg_write_cmd(cmd: Dict[str, Any]) -> None:
    try:
        await _ensure_table()
        from db import db

        if db.pool is None:
            return
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
    except Exception as e:
        print(f"[SR-ADMIN] pg cmd: {e!r}")


async def load_config() -> Dict[str, Any]:
    row = await _pg_row()
    if row and isinstance(row.get("config"), dict) and row["config"]:
        return _normalize(row["config"])
    file_cfg = _read_json(_CFG_PATH)
    if file_cfg:
        return _normalize(file_cfg)
    return _normalize(None)


async def load_status() -> Dict[str, Any]:
    row = await _pg_row()
    st: Dict[str, Any] = {}
    if row and isinstance(row.get("status"), dict):
        st = dict(row["status"])
    else:
        file_st = _read_json(_STATUS_PATH)
        if file_st:
            st = dict(file_st)

    now = time.time()
    published = float(st.get("published_at") or 0)
    alive = bool(published and (now - published) < 20.0)
    next_at = st.get("next_at")
    next_in = None
    if next_at is not None:
        try:
            next_in = round(max(0.0, float(next_at) - now), 3)
        except Exception:
            next_in = None

    return {
        "alive": alive,
        "published_at": published or None,
        "pid": st.get("pid"),
        "uptime_sec": st.get("uptime_sec"),
        "next_at": next_at,
        "next_in_sec": next_in,
        "requested": bool(st.get("requested")),
        "last_reason": st.get("last_reason"),
        "handoff": bool(st.get("handoff")),
        "supervisor": bool(st.get("supervisor")),
        "server_now": now,
    }


async def overview() -> Dict[str, Any]:
    cfg = await load_config()
    status = await load_status()
    return {
        "config": cfg,
        "status": status,
        "guide": GUIDE,
        "creatorId": int(PROJECT_CREATOR_ID),
        "paramHelp": {
            "enabled": "Главный выключатель авто-рестарта. OFF — только ручной «сейчас» / .r.",
            "test": "Тестовый режим: помечает систему как тест (авто обычно выкл через preset test).",
            "interval_sec": "Пауза между последующими авто-рестартами (после первого).",
            "initial_delay_sec": "Пауза после старта процесса до первого авто-рестарта.",
            "grace_sec": "Задержка перед жёстким выходом, если rolling-супервизора нет.",
        },
    }


async def save_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    cfg = await load_config()
    for k, v in patch.items():
        if k in cfg and v is not None:
            cfg[k] = v
    cfg = _normalize(cfg)
    _write_json(_CFG_PATH, cfg)
    await _pg_write_config(cfg)
    cmd = {
        "op": "apply",
        "config": cfg,
        "ts": time.time(),
    }
    _write_json(_CMD_PATH, cmd)
    await _pg_write_cmd(cmd)
    return cfg


async def queue_restart(reason: str = "panel") -> Dict[str, Any]:
    cmd = {
        "op": "restart",
        "reason": str(reason or "panel")[:64],
        "ts": time.time(),
    }
    _write_json(_CMD_PATH, cmd)
    await _pg_write_cmd(cmd)
    return {"ok": True, "queued": True, "cmd": cmd}


async def apply_preset(name: str) -> Dict[str, Any]:
    n = (name or "").strip().lower()
    if n in ("live", "prod", "бой"):
        return await save_settings({"enabled": True, "test": False})
    if n in ("test", "check", "тест"):
        return await save_settings({"enabled": False, "test": True})
    raise ValueError("unknown preset")
