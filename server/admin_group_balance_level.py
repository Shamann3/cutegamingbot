# -*- coding: utf-8 -*-
"""Admin API helpers for group balance levels (server-only, no bot imports).

Хранение: JSON в server/data/group_balance_level/.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DEFAULT_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    "level_0_cap": 30,
    "prices": {"1": 50, "2": 100, "3": 250, "4": 600, "5": 1000},
    "stake_caps": {"1": 50, "2": 100, "3": 200, "4": 350, "5": None},
    "recommend_pct": 15,
    "health_success_min": 1.0,
    "health_primary_min": 0.4,
    "atmosphere_enabled": True,
    "atmosphere_max_bonus_pct": 40,
    "badge_titles": {
        "1": "Спонсор группы",
        "2": "Меценат сообщества",
        "3": "Архитектор баланса",
        "4": "Покровитель круга",
        "5": "Легенда баланса",
    },
    "raise_button_text": "Поднять уровень группы",
    "system_title": "Баланс группы",
}

PARAM_HELP: Dict[str, str] = {
    "enabled": "Вкл/выкл всю систему уровней баланса группы.",
    "level_0_cap": "Макс. ставка в группе без купленных звёзд (★0).",
    "prices": "Цена шага в Telegram Stars, чтобы ДОСТИЧЬ уровня N с N-1.",
    "stake_caps": "Потолок ставки на уровне. Пусто/null на ★5 = без лимита уровня.",
    "recommend_pct": "% от бч → рекомендуемая ставка (кнопка бч и подсказки).",
    "health_success_min": "Если рек.ставка/лимит ≥ этого — кнопка бч success (зелёная).",
    "health_primary_min": "Если ниже success, но ≥ этого — primary. Иначе danger.",
    "atmosphere_enabled": "Включить надбавку к лимиту от донатеров/активности.",
    "atmosphere_max_bonus_pct": "Максимум надбавки атмосферы в % от базового лимита.",
    "badge_titles": "Названия меток спонсора в достижениях профиля.",
    "raise_button_text": "Текст кнопки апгрейда в экране бч.",
    "system_title": "Заголовок системы (внутренний/админ).",
}

_DATA_DIR = Path(__file__).resolve().parent / "data" / "group_balance_level"
_REPO_DATA = Path(__file__).resolve().parents[1] / "data" / "group_balance_level"
if os.environ.get("GBL_DATA_DIR"):
    _DATA_DIR = Path(os.environ["GBL_DATA_DIR"])
elif _REPO_DATA.exists():
    _DATA_DIR = _REPO_DATA

_LOCK = threading.RLock()


class _JsonStore:
    def __init__(self, name: str):
        self.name = name
        self.path = _DATA_DIR / f"{name}.json"
        self._cache: Optional[Dict[str, Any]] = None
        self._mtime: float = 0.0

    def _ensure_dir(self) -> None:
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _load(self) -> Dict[str, Any]:
        with _LOCK:
            try:
                if self.path.exists():
                    mtime = self.path.stat().st_mtime
                    if self._cache is not None and mtime == self._mtime:
                        return self._cache
                    with self.path.open("r", encoding="utf-8") as f:
                        raw = json.load(f)
                    if isinstance(raw, dict):
                        self._cache = raw
                        self._mtime = mtime
                        return self._cache
            except Exception as e:
                print(f"[GBL-ADMIN] load {self.name} fail: {e!r}")
            self._cache = {}
            self._mtime = 0.0
            return self._cache

    def _save(self) -> None:
        with _LOCK:
            self._ensure_dir()
            data = dict(self._cache or {})
            tmp = self.path.with_suffix(".tmp")
            try:
                with tmp.open("w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self.path)
                try:
                    self._mtime = self.path.stat().st_mtime
                except Exception:
                    self._mtime = time.time()
            except Exception as e:
                print(f"[GBL-ADMIN] save {self.name} fail: {e!r}")
                try:
                    if tmp.exists():
                        tmp.unlink()
                except Exception:
                    pass

    def get(self, key: Any, default=None):
        return self._load().get(str(key), default)

    def __setitem__(self, key, value):
        with _LOCK:
            data = self._load()
            data[str(key)] = value
            self._cache = data
            self._save()


_settings_store = _JsonStore("group_balance_level_settings")
_chat_levels = _JsonStore("group_balance_chat_levels")
_purchase_log = _JsonStore("group_balance_purchase_log")
_LOG_KEY = "events"


def _as_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def get_settings() -> Dict[str, Any]:
    raw = _settings_store.get("settings")
    if not isinstance(raw, dict):
        return copy.deepcopy(DEFAULT_SETTINGS)
    merged = copy.deepcopy(DEFAULT_SETTINGS)
    for k, v in raw.items():
        if k in ("prices", "stake_caps", "badge_titles") and isinstance(v, dict):
            base = dict(merged.get(k) or {})
            base.update({str(kk): vv for kk, vv in v.items()})
            merged[k] = base
        else:
            merged[k] = v
    return merged


def save_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    cfg = get_settings()
    for k, v in (patch or {}).items():
        if k in ("prices", "stake_caps", "badge_titles") and isinstance(v, dict):
            base = dict(cfg.get(k) or {})
            base.update({str(kk): vv for kk, vv in v.items()})
            cfg[k] = base
        else:
            cfg[k] = v
    _settings_store["settings"] = cfg
    return cfg


def reset_settings() -> Dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_SETTINGS)
    _settings_store["settings"] = cfg
    return cfg


def _level_int(chat_id: int) -> int:
    row = _chat_levels.get(str(int(chat_id))) or {}
    return max(0, min(5, _as_int((row or {}).get("level"), 0)))


def _write_level(chat_id: int, level: int, sponsor_id: Optional[int] = None) -> int:
    lvl = max(0, min(5, int(level)))
    prev = _chat_levels.get(str(int(chat_id))) or {}
    row = dict(prev) if isinstance(prev, dict) else {}
    row["level"] = lvl
    row["updated_at"] = time.time()
    if sponsor_id is not None:
        row["sponsor_id"] = int(sponsor_id)
    _chat_levels[str(int(chat_id))] = row
    return lvl


def next_level_price(chat_id: int, cfg: Optional[Dict[str, Any]] = None) -> Optional[Tuple[int, int]]:
    cfg = cfg or get_settings()
    cur = _level_int(chat_id)
    if cur >= 5:
        return None
    to_level = cur + 1
    prices = cfg.get("prices") or {}
    price = _as_int(prices.get(str(to_level)), 0)
    return to_level, price


def effective_stake_cap(chat_id: int, cfg: Optional[Dict[str, Any]] = None) -> Optional[int]:
    cfg = cfg or get_settings()
    level = _level_int(chat_id)
    if level <= 0:
        return _as_int(cfg.get("level_0_cap"), 30)
    caps = cfg.get("stake_caps") or {}
    if level >= 5 and caps.get("5") is None:
        return None
    v = caps.get(str(level))
    if v is None:
        return _as_int(cfg.get("level_0_cap"), 30)
    return int(v)


def stars_label(level: int) -> str:
    level = max(0, min(5, int(level)))
    return "★" * level + "☆" * (5 - level)


def list_recent_purchases(limit: int = 50):
    events = list(_purchase_log.get(_LOG_KEY) or [])
    return list(reversed(events[-max(1, int(limit)):]))


def get_overview() -> Dict[str, Any]:
    cfg = get_settings()
    return {
        "settings": cfg,
        "defaults": DEFAULT_SETTINGS,
        "recent": list_recent_purchases(40),
        "param_help": PARAM_HELP,
    }


def get_chat_level(chat_id: int) -> Dict[str, Any]:
    """Admin payload (dict) — имя как в admin_routes."""
    cfg = get_settings()
    level = _level_int(int(chat_id))
    nxt = next_level_price(int(chat_id), cfg)
    return {
        "chat_id": int(chat_id),
        "level": level,
        "stars": stars_label(level),
        "stake_cap": effective_stake_cap(int(chat_id), cfg=cfg),
        "next": {"level": nxt[0], "price": nxt[1]} if nxt else None,
    }


def set_chat_level(chat_id: int, level: int) -> Dict[str, Any]:
    """Admin setter — возвращает dict для admin_routes."""
    lvl = _write_level(int(chat_id), int(level), sponsor_id=None)
    return {"chat_id": int(chat_id), "level": int(lvl)}
