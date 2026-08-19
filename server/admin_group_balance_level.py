# -*- coding: utf-8 -*-
"""Admin API helpers for group balance levels (server-only, no bot imports).

Уровни: таблица chat.group_balance_level (ключ chat_id).
JSON в data/group_balance_level/ — зеркало/кэш + настройки.
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
    "society_snapshot_ttl_sec": 1800,
    "society_price_max_mult": 3.0,
    # Смесь донатера: 60% за всё время + 40% за месяц
    "donor_life_weight": 0.6,
    "donor_month_weight": 0.4,
    # Доли от atmosphere_max_bonus_pct (в сумме ≈ 1.0)
    "society_activity_share": 0.42,
    "society_donor_share": 0.38,
    "society_synergy_share": 0.08,
    # Кривая актива: >1 = месяц усилий даёт рост умеренно
    "society_activity_curve": 1.28,
    "badge_titles": {
        "1": "Спонсор группы",
        "2": "Опора группы",
        "3": "Сила группы",
        "4": "Герой группы",
        "5": "Легенда группы",
    },
    "raise_button_text": "Поднять лимит",
    "system_title": "Баланс группы",
}

PARAM_HELP: Dict[str, str] = {
    "enabled": (
        "Главный выключатель системы уровней баланса группы. "
        "Выкл → покупка уровней и лимиты по ★ не действуют (игры без потолка уровня)."
    ),
    "level_0_cap": (
        "Базовый потолок ставки, пока группа на уровне 0 (ещё никто не купил шаг). "
        "На него сверху может лечь бонус «живой группы» (+%)."
    ),
    "prices": (
        "Базовая цена шага в Telegram Stars, чтобы ДОСТИЧЬ уровня N с предыдущего. "
        "Итоговая цена для игрока = база × множитель силы группы (до society_price_max_mult). "
        "Игроку показываем одну цену, без «было/стало»."
    ),
    "stake_caps": (
        "Базовый потолок ставки на уровне N. "
        "Пусто/∞ на уровне 5 = ставки без лимита уровня. "
        "Реальный потолок = база × (1 + бонус живой группы/100)."
    ),
    "recommend_pct": (
        "Рекомендуемая ставка ≈ (баланс группы × этот %) , но не выше текущего потолка. "
        "Показывается в «Условиях группы», влияет на цвет кнопки здоровья бч."
    ),
    "health_success_min": (
        "Цвет кнопки «Статус и условия»: если (рек.ставка / потолок) ≥ этого — success (зелёная). "
        "Значит баланс группы уверенно тянет крупные ставки."
    ),
    "health_primary_min": (
        "Если ниже success, но ≥ этого — primary. Ещё ниже — danger (баланс тонкий относительно лимита)."
    ),
    "atmosphere_enabled": (
        "«Живая группа»: анализ сообщений (30 дней) + донатеров (60% всё время / 40% месяц) → "
        "бонус к макс. ставке и давление на цену уровня. Выкл → бонус 0%, цены без общества."
    ),
    "atmosphere_max_bonus_pct": (
        "Жёсткий потолок бонуса к макс. ставке (например 40). "
        "Реальный +% = доля актива + доля донатов + синергия, не выше этого числа."
    ),
    "society_snapshot_ttl_sec": (
        "Как часто пересчитывать силу группы (сек). Пока снимок свежий — ответ «бч» из кэша (очень быстро). "
        "Просроченный снимок отдаём сразу и обновляем в фоне."
    ),
    "society_price_max_mult": (
        "Макс. множитель цены шага уровня от силы общества (например 3.0 = до ×3 от базы). "
        "1–2 донатера в обычной группе цену ядром не разгоняют — нужно «ядро» донатеров."
    ),
    "donor_life_weight": (
        "Вес доната за ВСЁ время (users.donate) в силе одного донатера. "
        "По умолчанию 0.6. Вместе с donor_month_weight нормализуется до 100%."
    ),
    "donor_month_weight": (
        "Вес доната за последние 30 дней (журнал public.donate). "
        "По умолчанию 0.4. Свежий донат поднимает человека, даже если lifetime меньше."
    ),
    "society_activity_share": (
        "Какая доля от макс. бонуса может дать АКТИВ чата (сообщения 30 дней). "
        "0.42 при макс. 40% → до ~16.8% только от актива (с кривой ещё мягче)."
    ),
    "society_donor_share": (
        "Какая доля от макс. бонуса может дать ЯДРО ДОНАТЕРОВ. "
        "1 донатер почти ничего; толпа сильных — ближе к этой доле."
    ),
    "society_synergy_share": (
        "Бонус, когда актив И донаты высоки одновременно (синергия). Маленькая «вишенка» сверху."
    ),
    "society_activity_curve": (
        "Кривая актива (степень). >1 → месяц усилий растёт умеренно, нельзя «случайно» взять весь бонус. "
        "1.0 = линейно; 1.28 = мягче для средних чатов."
    ),
    "badge_titles": (
        "Запасные названия меток спонсора. Основной текст официальных достижений "
        "gbl_level_1…5 лучше править во вкладке «Достижения» — при покупке подтянется оттуда."
    ),
    "raise_button_text": (
        "Fallback-текст кнопки апгрейда, если не собрался умный CTA («ставки до N»)."
    ),
    "system_title": (
        "Внутреннее имя системы (админка / редкие тексты). На первом экране «бч» игроку не показываем — там только сумма."
    ),
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
        row["last_sponsor_id"] = int(sponsor_id)
    row["source"] = "db"
    _chat_levels[str(int(chat_id))] = row
    return lvl


async def _db():
    from db import db
    return db


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
        "guide": {
            "title": "Умный баланс группы",
            "for_whom": "Только создатель проекта (owner).",
            "flow": [
                "Игрок пишет «бч» → видит только сумму баланса и кнопки.",
                "«Статус и условия» → уровень, потолок ставок, пульс чата, рекомендация.",
                "«Поднять уровень» → покупка шага (Stars/crypto) → авто-достижение gbl_level_N.",
            ],
            "society": (
                "Сила группы = сообщения за 30 дней + донатеры "
                "(60% сумма за всё время + 40% за месяц из журнала donate). "
                "В расчёт донатов идут те, кто ещё и писал в чате. "
                "Бонус к макс. ставке до atmosphere_max_bonus_pct. "
                "Цена уровня растёт до society_price_max_mult, но 1–2 донатера "
                "в обычной группе ядро цен не разгоняют."
            ),
            "speed": (
                "Снимки силы группы кэшируются (TTL). Свежий — мгновенно из памяти; "
                "чуть старый — ответ сразу, пересчёт в фоне; индексы и параллельные SQL."
            ),
        },
    }


async def get_chat_level(chat_id: int) -> Dict[str, Any]:
    """Admin payload (dict) — уровень читается из таблицы chat."""
    cfg = get_settings()
    cid = int(chat_id)
    level = _level_int(cid)
    try:
        db = await _db()
        if hasattr(db, "ensure_group_balance_level_schema"):
            await db.ensure_group_balance_level_schema()
        if hasattr(db, "get_chat_group_balance_level"):
            level = max(0, min(5, int(await db.get_chat_group_balance_level(cid))))
            _write_level(cid, level, sponsor_id=None)
    except Exception as e:
        print(f"[GBL-ADMIN] get_chat_level DB fail chat={cid}: {e!r}")
    # next_level_price читает зеркало — держим его в актуальном виде
    _write_level(cid, level, sponsor_id=None)
    nxt = next_level_price(cid, cfg)
    return {
        "chat_id": cid,
        "level": level,
        "stars": stars_label(level),
        "stake_cap": effective_stake_cap(cid, cfg=cfg),
        "next": {"level": nxt[0], "price": nxt[1]} if nxt else None,
        "storage": "chat.group_balance_level",
    }


async def set_chat_level(chat_id: int, level: int) -> Dict[str, Any]:
    """Admin setter — пишет в chat.group_balance_level по chat_id."""
    cid = int(chat_id)
    lvl = max(0, min(5, int(level)))
    db = await _db()
    if hasattr(db, "ensure_group_balance_level_schema"):
        await db.ensure_group_balance_level_schema()
    saved = await db.set_chat_group_balance_level(cid, lvl, sponsor_id=None)
    _write_level(cid, int(saved), sponsor_id=None)
    return {
        "chat_id": cid,
        "level": int(saved),
        "storage": "chat.group_balance_level",
    }
