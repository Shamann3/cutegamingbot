# -*- coding: utf-8 -*-
"""Уровни баланса группы (★1…★5).

Не путать с «столом» в текстах для игроков — везде «баланс группы».
Конфиг полностью настраивается (админка → creator-only).

Хранение: JSON-файлы в data/group_balance_level/ (без Redis),
чтобы и бот, и admin-сервер читали одно и то же без тяжёлых зависимостей.
"""

from __future__ import annotations

import copy
import json
import math
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────
# Defaults (админка может переписать всё)
# ──────────────────────────────────────────────────────────────────────
DEFAULT_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    # Лимит ставки при 0★ (пока группа без купленных уровней)
    "level_0_cap": 30,
    # Цена ШАГА: сколько ★ нужно, чтобы ДОСТИЧЬ этого уровня с предыдущего
    "prices": {"1": 50, "2": 100, "3": 250, "4": 600, "5": 1000},
    # Потолок ставки по уровню; null/None у ★5 = без лимита уровня
    "stake_caps": {"1": 50, "2": 100, "3": 200, "4": 350, "5": None},
    # Рекомендуемая ставка = floor(бч * pct / 100), не выше потолка ★
    "recommend_pct": 15,
    # Пороги «здоровья» баланса группы относительно лимита уровня
    # ratio = (бч * recommend_pct/100) / effective_cap
    "health_success_min": 1.0,
    "health_primary_min": 0.4,
    # Надбавка к лимиту ставок от живых игроков и донатеров (макс %)
    "atmosphere_enabled": True,
    "atmosphere_max_bonus_pct": 40,
    # Снимок силы группы: TTL секунд (пересчёт по требованию, не на все чаты)
    "society_snapshot_ttl_sec": 1800,
    # Макс. множитель цены уровня от силы общества
    "society_price_max_mult": 3.0,
    "donor_life_weight": 0.6,
    "donor_month_weight": 0.4,
    "society_activity_share": 0.42,
    "society_donor_share": 0.38,
    "society_synergy_share": 0.08,
    "society_activity_curve": 1.28,
    # Метки спонсора в профиле
    "badge_titles": {
        "1": "Спонсор группы",
        "2": "Меценат сообщества",
        "3": "Архитектор баланса",
        "4": "Покровитель круга",
        "5": "Легенда баланса",
    },
    # Тексты / UX
    "raise_button_text": "Открыть ставки шире",
    "system_title": "Баланс группы",
    # Визуальная скидка: list > pay, к оплате всегда pay (= нужда проекта)
    # Проект не уходит в минус: invoice = sum(реальных цен шагов).
    "visual_discount_enabled": True,
    "visual_markup_min": 1.14,
    "visual_markup_max": 1.34,
    # Пакеты уровней «наперёд» (1 / 2 / все оставшиеся)
    "level_packages_enabled": True,
}

# Premium custom emoji на кнопках бч (icon_custom_emoji_id)
ICON_HERO_BEACH = "5251344521546965676"        # большой эмодзи на главном «бч»
ICON_BALANCE_KUT = "6028338546736107668"       # ★ на сумме баланса группы
ICON_RAISE_LEVEL = "5404534885324988233"       # ★ на «Поднять уровень…»
ICON_BACK = "5226660202035554522"              # назад к балансу
ICON_DETAILS = "5472146462362048818"           # «Подробнее» / условия

_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _ROOT / "data" / "group_balance_level"
_LOCK = threading.RLock()


class _JsonStore:
    """Простой dict-like store в JSON-файле (общий для bot + admin server)."""

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
                print(f"[GBL] load {self.name} fail: {e!r}")
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
                print(f"[GBL] save {self.name} fail: {e!r}")
                try:
                    if tmp.exists():
                        tmp.unlink()
                except Exception:
                    pass

    def get(self, key: Any, default=None):
        return self._load().get(str(key), default)

    def __getitem__(self, key):
        return self._load()[str(key)]

    def __setitem__(self, key, value):
        with _LOCK:
            data = self._load()
            data[str(key)] = value
            self._cache = data
            self._save()

    def __contains__(self, key):
        return str(key) in self._load()

    def __len__(self):
        return len(self._load())

    def items(self):
        return list(self._load().items())

    def pop(self, key, default=None):
        with _LOCK:
            data = self._load()
            val = data.pop(str(key), default)
            self._cache = data
            self._save()
            return val

    def clear(self):
        with _LOCK:
            self._cache = {}
            self._save()


_settings_store: _JsonStore = _JsonStore("group_balance_level_settings")
# chat_id(str) → {"level": int, "updated_at": float, "last_sponsor_id": int|None}
_chat_levels: _JsonStore = _JsonStore("group_balance_chat_levels")
# user_id(str) → {"badges": { "3": {"level":3,"chat_id":…,"ts":…}, …}, "max_level": int}
_user_badges: _JsonStore = _JsonStore("group_balance_user_badges")
# История покупок (хвост для админки)
_purchase_log: _JsonStore = _JsonStore("group_balance_purchase_log")
# user_id(str) → {"n": int, "last_chat_id": int, "ts": float} — визиты в «бч»
_user_visits: _JsonStore = _JsonStore("group_balance_user_visits")

_CFG_KEY = "_cfg"
_LOG_KEY = "_events"


def _as_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def bump_gbl_visit(user_id: int, chat_id: int = 0) -> int:
    """Счётчик открытий системы бч — для персонализации обращения."""
    uid = str(int(user_id))
    row = dict(_user_visits.get(uid) or {})
    n = _as_int(row.get("n"), 0) + 1
    row["n"] = n
    row["last_chat_id"] = int(chat_id or 0)
    row["ts"] = time.time()
    _user_visits[uid] = row
    return n


def visit_hook_line(visit_n: int) -> str:
    """Короткая персонализация по визиту — без сленга."""
    n = max(1, int(visit_n or 1))
    if n <= 1:
        return "первый просмотр"
    if n <= 3:
        return "вы уже смотрели этот экран"
    if n <= 7:
        return "с возвращением"
    return "показатели могли обновиться"


def journey_step_label(step: str) -> str:
    """Короткие названия этапов воронки."""
    labels = {
        "meet": "Обзор",
        "decide": "Повышение",
        "finish": "Подтверждение",
        "pay": "Оплата",
    }
    return labels.get(step, step)


def get_settings() -> Dict[str, Any]:
    raw = _settings_store.get(_CFG_KEY)
    if not isinstance(raw, dict) or not raw:
        cfg = copy.deepcopy(DEFAULT_SETTINGS)
        _settings_store[_CFG_KEY] = cfg
        return copy.deepcopy(cfg)
    # Мягкий merge: новые ключи из DEFAULTS не теряются после обновления кода
    merged = copy.deepcopy(DEFAULT_SETTINGS)
    for k, v in raw.items():
        if k in ("prices", "stake_caps", "badge_titles") and isinstance(v, dict):
            merged[k] = {**merged.get(k, {}), **{str(kk): vv for kk, vv in v.items()}}
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
    _settings_store[_CFG_KEY] = cfg
    return copy.deepcopy(cfg)


def reset_settings_to_defaults() -> Dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_SETTINGS)
    _settings_store[_CFG_KEY] = cfg
    return copy.deepcopy(cfg)


def get_chat_level(chat_id: int) -> int:
    row = _chat_levels.get(str(int(chat_id))) or {}
    return max(0, min(5, _as_int(row.get("level"), 0)))


def set_chat_level(
    chat_id: int,
    level: int,
    *,
    sponsor_id: Optional[int] = None,
) -> int:
    level = max(0, min(5, _as_int(level, 0)))
    prev = _chat_levels.get(str(int(chat_id))) or {}
    _chat_levels[str(int(chat_id))] = {
        "level": level,
        "updated_at": time.time(),
        "last_sponsor_id": int(sponsor_id) if sponsor_id else prev.get("last_sponsor_id"),
    }
    return level


def price_to_reach(level: int, cfg: Optional[Dict[str, Any]] = None) -> int:
    """Цена шага, чтобы ДОСТИЧЬ level с (level-1)."""
    cfg = cfg or get_settings()
    prices = cfg.get("prices") or {}
    return max(0, _as_int(prices.get(str(int(level))), 0))


# Умная сила группы: см. bot.funcs.group_society
from bot.funcs.group_society import (  # noqa: E402
    ensure_society_snapshot,
    format_atmosphere_hint,
    format_society_hint,
    peek_society_snapshot,
    price_multiplier_for_level,
    resolve_atmosphere_pct,
    resolve_atmosphere_report,
    effective_level_price as _society_effective_level_price,
)


def next_level_price(chat_id: int, cfg: Optional[Dict[str, Any]] = None) -> Optional[Tuple[int, int]]:
    """(next_level, pay_stars) — реальная цена одного следующего шага для проекта."""
    cfg = cfg or get_settings()
    cur = get_chat_level(chat_id)
    if cur >= 5:
        return None
    nxt = cur + 1
    return nxt, int(step_real_price(chat_id, nxt, cfg))


def step_real_price(
    chat_id: int,
    to_level: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> int:
    """Реальная цена одного шага (то, что нужно проекту)."""
    cfg = cfg or get_settings()
    base = price_to_reach(to_level, cfg)
    return int(_society_effective_level_price(
        int(to_level), chat_id=int(chat_id), base_price=base, cfg=cfg,
    ))


def package_pay_price(
    chat_id: int,
    to_level: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> int:
    """Сумма реальных цен шагов cur+1…to_level — минимум, который должен получить проект."""
    cfg = cfg or get_settings()
    cur = get_chat_level(chat_id)
    to_level = max(1, min(5, int(to_level)))
    if to_level <= cur:
        return 0
    return sum(
        step_real_price(chat_id, lvl, cfg)
        for lvl in range(cur + 1, to_level + 1)
    )


def visual_markup_for_chat(
    chat_id: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> float:
    """Множитель «было» под силу группы: сильнее чат → ярче якорь скидки."""
    cfg = cfg or get_settings()
    lo = max(1.01, _as_float(cfg.get("visual_markup_min"), 1.14))
    hi = max(lo, _as_float(cfg.get("visual_markup_max"), 1.34))
    snap = peek_society_snapshot(int(chat_id)) or {}
    strength = max(
        _as_float(snap.get("society_score"), 0.0),
        _as_float(snap.get("effective_price_pressure"), 0.0),
        min(1.0, _as_float(snap.get("pct"), 0.0) / max(1.0, _as_float(cfg.get("atmosphere_max_bonus_pct"), 40.0))),
    )
    strength = max(0.0, min(1.0, strength))
    return round(lo + (hi - lo) * strength, 4)


def visual_list_price(
    pay_price: int,
    chat_id: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> int:
    """Визуальная цена «до скидки». К оплате всегда pay_price (≥ нужды проекта)."""
    cfg = cfg or get_settings()
    pay = max(0, int(pay_price or 0))
    if pay <= 0:
        return 0
    if not cfg.get("visual_discount_enabled", True):
        return pay
    listed = int(math.ceil(pay * visual_markup_for_chat(chat_id, cfg)))
    return max(pay + 1, listed)


def build_level_packages(
    chat_id: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Пакеты: +1 / +2 / все оставшиеся. pay = нужда проекта, list = якорь."""
    cfg = cfg or get_settings()
    if not cfg.get("enabled", True):
        return []
    cur = get_chat_level(chat_id)
    if cur >= 5:
        return []
    remaining = list(range(cur + 1, 6))
    if not remaining:
        return []

    if not cfg.get("level_packages_enabled", True) or len(remaining) == 1:
        targets = [remaining[0]]
    elif len(remaining) == 2:
        targets = [remaining[0], remaining[-1]]
    else:
        # золотая середина: шаг / +2 уровня / вершина
        targets = [remaining[0], remaining[1], remaining[-1]]

    role_map = {
        1: ("базовый", False),
        2: ("стандарт", True),
        3: ("премиум", False),
    }
    packages: List[Dict[str, Any]] = []
    n_targets = len(targets)
    for idx, to_level in enumerate(targets):
        steps = list(range(cur + 1, to_level + 1))
        step_pays = [step_real_price(chat_id, lvl, cfg) for lvl in steps]
        step_lists = [visual_list_price(p, chat_id, cfg) for p in step_pays]
        pay = int(sum(step_pays))
        listed = int(sum(step_lists))
        # Пакет «все уровни» — чуть выше якорь, скидка выглядит жирнее
        if to_level == remaining[-1] and len(steps) >= 2:
            listed = max(listed, int(math.ceil(listed * 1.08)))
        listed = max(listed, pay + max(1, len(steps)))
        save = max(0, listed - pay)
        save_pct = int(round(100.0 * save / listed)) if listed > 0 else 0
        if n_targets == 1:
            role, recommended = "ваш шаг", True
        elif n_targets == 2:
            role, recommended = (("ваш шаг", False) if idx == 0 else ("весь путь", True))
        else:
            role, recommended = role_map.get(idx + 1, ("пакет", False))
            if idx == 1:
                recommended = True
        cap = stake_cap_for_level(to_level, cfg)
        packages.append({
            "code": f"to_{to_level}",
            "from_level": cur,
            "to_level": int(to_level),
            "steps": len(steps),
            "step_levels": steps,
            "pay": pay,
            "list": listed,
            "save": save,
            "save_pct": save_pct,
            "role": role,
            "recommended": bool(recommended),
            "cap": cap,
            "cap_label": "∞" if (cap is None or to_level >= 5) else str(cap),
            "badge_title": badge_title_for_level(to_level, cfg),
        })
    return packages


def find_level_package(
    chat_id: int,
    to_level: int,
    pay_price: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Найти пакет по целевому уровню и сумме к оплате (защита от подмены)."""
    cfg = cfg or get_settings()
    to_level = int(to_level)
    pay_price = int(pay_price)
    for pkg in build_level_packages(chat_id, cfg):
        if int(pkg["to_level"]) == to_level and int(pkg["pay"]) == pay_price:
            return pkg
    # Допуск: точная нужда проекта на произвольный to_level (не только витрина)
    cur = get_chat_level(chat_id)
    if to_level <= cur or to_level > 5:
        return None
    expected = package_pay_price(chat_id, to_level, cfg)
    if expected > 0 and expected == pay_price:
        listed = visual_list_price(expected, chat_id, cfg)
        if to_level - cur >= 2:
            listed = max(listed, int(math.ceil(listed * 1.08)))
        listed = max(listed, expected + 1)
        return {
            "code": f"to_{to_level}",
            "from_level": cur,
            "to_level": to_level,
            "steps": to_level - cur,
            "step_levels": list(range(cur + 1, to_level + 1)),
            "pay": expected,
            "list": listed,
            "save": listed - expected,
            "save_pct": int(round(100.0 * (listed - expected) / listed)) if listed else 0,
            "role": "пакет",
            "recommended": False,
            "cap": stake_cap_for_level(to_level, cfg),
            "cap_label": (
                "∞" if to_level >= 5 or stake_cap_for_level(to_level, cfg) is None
                else str(stake_cap_for_level(to_level, cfg))
            ),
            "badge_title": badge_title_for_level(to_level, cfg),
        }
    return None


def format_package_price_line(pkg: Dict[str, Any]) -> str:
    """Короткая строка цены со скидкой."""
    pay = int(pkg.get("pay") or 0)
    listed = int(pkg.get("list") or pay)
    pct = int(pkg.get("save_pct") or 0)
    if listed > pay and pct > 0:
        return f"<s>{listed}</s> → <b>{pay}</b>⭐ (−{pct}%)"
    return f"<b>{pay}</b>⭐"


def stake_cap_for_level(level: int, cfg: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """None = без лимита уровня (★5)."""
    cfg = cfg or get_settings()
    level = max(0, min(5, _as_int(level, 0)))
    if level <= 0:
        return max(0, _as_int(cfg.get("level_0_cap"), 30))
    caps = cfg.get("stake_caps") or {}
    raw = caps.get(str(level), caps.get(level))
    if raw is None:
        return None
    return max(0, _as_int(raw, 0))


def effective_stake_cap(
    chat_id: int,
    *,
    atmosphere_pct: float = 0.0,
    cfg: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Итоговый потолок ставки. None = без лимита уровня."""
    cfg = cfg or get_settings()
    if not cfg.get("enabled", True):
        return None
    level = get_chat_level(chat_id)
    base = stake_cap_for_level(level, cfg)
    if base is None:
        return None
    bonus = max(0.0, min(100.0, float(atmosphere_pct)))
    return max(0, int(base * (1.0 + bonus / 100.0)))


def recommended_bet(chat_balance: float, cfg: Optional[Dict[str, Any]] = None) -> int:
    """Комфортная доля от баланса группы (без учёта потолка ★)."""
    cfg = cfg or get_settings()
    pct = max(0.0, _as_float(cfg.get("recommend_pct"), 15.0))
    bal = max(0.0, float(chat_balance or 0))
    return max(0, int(bal * pct / 100.0))


def recommended_play_bet(
    chat_balance: float,
    *,
    chat_id: int,
    atmosphere_pct: float = 0.0,
    cfg: Optional[Dict[str, Any]] = None,
) -> int:
    """Рекомендуемая ставка для игры: доля бч, но не выше открытого потолка ★."""
    cfg = cfg or get_settings()
    rec = recommended_bet(chat_balance, cfg)
    cap = effective_stake_cap(chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg)
    if cap is not None:
        rec = min(rec, int(cap))
    return max(0, int(rec))


def balance_health_style(
    chat_balance: float,
    *,
    chat_id: int,
    atmosphere_pct: float = 0.0,
    cfg: Optional[Dict[str, Any]] = None,
) -> str:
    """success | primary | danger — для кнопки баланса в бч."""
    cfg = cfg or get_settings()
    rec = recommended_bet(chat_balance, cfg)
    cap = effective_stake_cap(chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg)
    # Нет уровня-лимита (★5 / система выкл): здоровье по абсолютной рекомендуемой ставке
    if cap is None:
        if rec >= 100:
            return "success"
        if rec >= 20:
            return "primary"
        return "danger"
    if cap <= 0:
        return "danger"
    ratio = float(rec) / float(cap)
    success_min = _as_float(cfg.get("health_success_min"), 1.0)
    primary_min = _as_float(cfg.get("health_primary_min"), 0.4)
    if ratio >= success_min:
        return "success"
    if ratio >= primary_min:
        return "primary"
    return "danger"


def stars_label(level: int) -> str:
    level = max(0, min(5, int(level)))
    return "★" * level + "☆" * (5 - level)


def badge_title_for_level(level: int, cfg: Optional[Dict[str, Any]] = None) -> str:
    cfg = cfg or get_settings()
    titles = cfg.get("badge_titles") or {}
    return str(titles.get(str(int(level))) or f"Спонсор группы · уровень {int(level)}")


def remember_sponsor_badge(
    user_id: int,
    *,
    level: int,
    chat_id: int,
    price_stars: int,
) -> Dict[str, Any]:
    uid = str(int(user_id))
    row = dict(_user_badges.get(uid) or {})
    badges = dict(row.get("badges") or {})
    key = str(int(level))
    # Храним лучший факт по уровню (первый чат / обновляем ts)
    badges[key] = {
        "level": int(level),
        "chat_id": int(chat_id),
        "price_stars": int(price_stars),
        "ts": time.time(),
        "title": badge_title_for_level(level),
    }
    max_level = max([_as_int(x.get("level"), 0) for x in badges.values()] + [0])
    row = {"badges": badges, "max_level": max_level, "updated_at": time.time()}
    _user_badges[uid] = row
    return row


def get_user_achievements(user_id: int) -> List[Dict[str, Any]]:
    row = _user_badges.get(str(int(user_id))) or {}
    badges = row.get("badges") or {}
    items = list(badges.values()) if isinstance(badges, dict) else []
    items.sort(key=lambda x: _as_int(x.get("level"), 0))
    return items


def format_achievements_blockquote(user_id: int) -> str:
    """HTML-блок для профиля. Пусто, если достижений нет."""
    items = get_user_achievements(user_id)
    if not items:
        return ""
    lines: List[str] = []
    for it in items:
        lvl = _as_int(it.get("level"), 0)
        title = str(it.get("title") or badge_title_for_level(lvl))
        lines.append(
            f"<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji> "
            f"<b>{stars_label(lvl)}</b> · {title}"
        )
    body = "\n".join(lines)
    return (
        f"<blockquote>"
        f"<tg-emoji emoji-id='5318892863780579996'>📖</tg-emoji> "
        f"<b>Уровни групп</b>\n{body}"
        f"</blockquote>"
    )


def log_purchase(event: Dict[str, Any]) -> None:
    events = list(_purchase_log.get(_LOG_KEY) or [])
    events.append({**event, "ts": time.time()})
    _purchase_log[_LOG_KEY] = events[-300:]


def list_recent_purchases(limit: int = 50) -> List[Dict[str, Any]]:
    events = list(_purchase_log.get(_LOG_KEY) or [])
    return list(reversed(events[-max(1, int(limit)):]))


def count_purchases_since(seconds: float = 7 * 86400) -> int:
    """Сколько покупок уровней за окно времени (соц. доказательство)."""
    cutoff = time.time() - max(0.0, float(seconds))
    events = list(_purchase_log.get(_LOG_KEY) or [])
    n = 0
    for ev in events:
        try:
            if float(ev.get("ts") or 0) >= cutoff:
                n += 1
        except Exception:
            continue
    return n


def total_purchase_count() -> int:
    return len(list(_purchase_log.get(_LOG_KEY) or []))


def social_proof_line() -> str:
    """Короткая строка соцдоказательства — только реальные цифры."""
    week = count_purchases_since(7 * 86400)
    total = total_purchase_count()
    if week >= 3:
        return f"за неделю уровни подняли уже <b>{week}</b> раз"
    if total >= 1:
        return f"в проекте уже <b>{total}</b> вкладов в уровни групп"
    return "вы можете открыть путь для этой группы первыми"


def _cap_with_atmosphere(
    base: Optional[int],
    atmosphere_pct: float,
    cfg: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    cfg = cfg or get_settings()
    if base is None:
        return None
    if not cfg.get("atmosphere_enabled", True):
        return max(0, int(base))
    bonus = max(0.0, min(100.0, float(atmosphere_pct or 0)))
    return max(0, int(int(base) * (1.0 + bonus / 100.0)))


def _fmt_lim(cap: Optional[int]) -> str:
    if cap is None:
        return "без лимита уровня"
    return f"до {int(cap)} кут"


def stake_delta_for_step(
    *,
    from_level: int,
    to_level: int,
    atmosphere_pct: float = 0.0,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Личная выгода шага: было → станет → прирост потолка."""
    cfg = cfg or get_settings()
    old_base = stake_cap_for_level(from_level, cfg)
    new_base = stake_cap_for_level(to_level, cfg)
    if to_level >= 5:
        new_base = None
    old_cap = _cap_with_atmosphere(old_base, atmosphere_pct, cfg)
    new_cap = _cap_with_atmosphere(new_base, atmosphere_pct, cfg)
    delta: Optional[int] = None
    if old_cap is not None and new_cap is not None:
        delta = max(0, int(new_cap) - int(old_cap))
    return {
        "old_cap": old_cap,
        "new_cap": new_cap,
        "delta": delta,
        "old_lim": _fmt_lim(old_cap),
        "new_lim": _fmt_lim(new_cap),
    }


def build_price_ladder_html(
    *,
    chat_id: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> str:
    """Витрина пакетов со визуальной скидкой (к оплате — нужда проекта)."""
    cfg = cfg or get_settings()
    packages = build_level_packages(chat_id, cfg)
    if not packages:
        return ""
    lines: List[str] = []
    for pkg in packages:
        mark = " ← выбор большинства" if pkg.get("recommended") else ""
        steps = int(pkg.get("steps") or 1)
        step_bit = "1 шаг" if steps == 1 else f"{steps} шага" if steps < 5 else f"{steps} шагов"
        lines.append(
            f"• <b>{pkg['role']}</b> · ур.<b>{pkg['to_level']}</b> · "
            f"до <b>{pkg['cap_label']}</b> · {step_bit}\n"
            f"  {format_package_price_line(pkg)}{mark}"
        )
    return (
        f"<blockquote>"
        f"<b>Пакеты уровней</b>\n"
        + "\n".join(lines)
        + "\n"
        f"<i>к оплате — цена со скидкой · можно взять сразу несколько уровней</i>"
        f"</blockquote>"
    )


def apply_level_purchase(
    *,
    chat_id: int,
    user_id: int,
    to_level: int,
    price_stars: int,
) -> Dict[str, Any]:
    """Применяет покупку одного или нескольких уровней после оплаты.

    to_level может быть прыжком (0→3). price_stars должен покрывать
    сумму реальных цен шагов (проект не в минусе).
    """
    cfg = get_settings()
    to_level = max(1, min(5, int(to_level)))
    cur = get_chat_level(chat_id)
    if to_level <= cur:
        remember_sponsor_badge(
            user_id, level=to_level, chat_id=chat_id, price_stars=price_stars,
        )
        return {"ok": True, "level": cur, "from_level": cur, "already": True}

    expected = package_pay_price(chat_id, to_level, cfg)
    # После успешной оплаты Stars/crypto применяем уровень всегда.
    # Недоплата возможна только если сила группы выросла между счётом и оплатой —
    # тогда всё равно выдаём купленный пакет (деньги уже получены).
    underpaid = bool(expected > 0 and int(price_stars) < int(expected))

    from_level = cur
    set_chat_level(chat_id, to_level, sponsor_id=user_id)
    for lvl in range(from_level + 1, to_level + 1):
        remember_sponsor_badge(
            user_id, level=lvl, chat_id=chat_id, price_stars=price_stars,
        )
    log_purchase({
        "chat_id": int(chat_id),
        "user_id": int(user_id),
        "level": int(to_level),
        "from_level": int(from_level),
        "steps": int(to_level - from_level),
        "price_stars": int(price_stars),
        "expected_pay": int(expected),
        "underpaid": underpaid,
    })
    return {
        "ok": True,
        "level": to_level,
        "from_level": from_level,
        "already": False,
        "steps": to_level - from_level,
        "underpaid": underpaid,
        "expected": expected,
    }


def _next_level_teaser(chat_id: int, cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Тизер: рекомендуемый пакет со визуальной скидкой."""
    cfg = cfg or get_settings()
    if not cfg.get("enabled", True):
        return None
    packages = build_level_packages(chat_id, cfg)
    if not packages:
        return None
    pkg = next((p for p in packages if p.get("recommended")), packages[0])
    return (
        f"<b>{pkg['role']}</b> · уровень <b>{pkg['to_level']}</b> · "
        f"ставки до <b>{pkg['cap_label']}</b>\n"
        f"{format_package_price_line(pkg)}"
    )


def raise_cta_label(chat_id: int, cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Кнопка повышения — результат после нажатия."""
    cfg = cfg or get_settings()
    if not cfg.get("enabled", True):
        return None
    level = get_chat_level(chat_id)
    if level >= 5:
        return None
    nxt = next_level_price(chat_id, cfg)
    if not nxt:
        return str(cfg.get("raise_button_text") or "Открыть ставки шире")
    to_level, _price = nxt
    caps = cfg.get("stake_caps") or {}
    if to_level >= 5:
        return "Открыть вершину · без лимита"
    cap = caps.get(str(to_level))
    if cap is not None:
        return f"Открыть ставки до {cap}"
    return str(cfg.get("raise_button_text") or "Открыть ставки шире")


def _ru_users_word(n: int) -> str:
    """1 пользователь, 2 пользователя, 5 пользователей."""
    n = abs(int(n or 0))
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return "пользователь"
    if 2 <= n10 <= 4 and not (12 <= n100 <= 14):
        return "пользователя"
    return "пользователей"


def _ru_donors_word(n: int) -> str:
    n = abs(int(n or 0))
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return "донатер"
    if 2 <= n10 <= 4 and not (12 <= n100 <= 14):
        return "донатера"
    return "донатеров"


def _society_pulse_lines(
    report: Dict[str, Any],
    *,
    cfg: Optional[Dict[str, Any]] = None,
    compact: bool = False,
) -> str:
    """Разбор силы группы. compact=True — для короткого экрана «Подробнее»."""
    cfg = cfg or get_settings()
    act = report.get("activity") if isinstance(report.get("activity"), dict) else {}
    don = report.get("donors") if isinstance(report.get("donors"), dict) else {}
    members = _as_int(act.get("members") or report.get("members"), 0)
    writers = _as_int(act.get("writers"), 0)
    donators = _as_int(don.get("donators") or report.get("donators"), 0)
    a = _as_float(act.get("score"), 0.0)
    d = _as_float(don.get("score"), 0.0)
    pct = _as_float(report.get("pct"), 0.0)
    max_pct = _as_int(cfg.get("atmosphere_max_bonus_pct"), 40)
    members_fmt = f"{members:,}".replace(",", ".") if members > 0 else "0"

    if a >= 0.75:
        pulse = "очень живая"
    elif a >= 0.4:
        pulse = "в хорошем ритме"
    elif a >= 0.15:
        pulse = "постепенно оживает"
    else:
        pulse = "пока тихая"

    if d >= 0.7:
        donor_bit = "сильная поддержка донатерами"
    elif d >= 0.35:
        donor_bit = "есть поддержка донатерами"
    elif donators >= 1:
        donor_bit = "донаты уже есть"
    else:
        donor_bit = "рост через общение"

    if compact:
        bits = [f"<b>{pulse}</b>", f"<b>+{pct:g}%</b> / {max_pct}%"]
        if writers > 0 and members > 0:
            bits.append(f"<b>{writers}</b> из ~{members_fmt}")
        elif writers > 0:
            bits.append(f"писали <b>{writers}</b>")
        if donators > 0:
            bits.append(f"<b>{donators}</b> {_ru_donors_word(donators)}")
        else:
            bits.append(donor_bit)
        return " · ".join(bits)

    lines = [
        "<b>Пульс группы</b>",
        f"группа <b>{pulse}</b>.",
    ]
    if members > 0:
        if writers > 0:
            lines.append(
                f"Из ~<b>{members_fmt}</b> {_ru_users_word(members)} за месяц "
                f"писали <b>{writers}</b>."
            )
        else:
            lines.append(
                f"Из ~<b>{members_fmt}</b> {_ru_users_word(members)} за месяц "
                f"почти никто не писал."
            )
    elif writers > 0:
        lines.append(f"За месяц писали <b>{writers}</b>.")
    if donators > 0:
        lines.append(
            f"{donor_bit} · в расчёте <b>{donators}</b> {_ru_donors_word(donators)}."
        )
    else:
        lines.append(f"{donor_bit}.")
    lines.append(
        f"Бонус к потолку: <b>+{pct:g}%</b> (макс. +{max_pct}%)."
    )
    return "\n".join(lines)


def build_details_html(
    *,
    chat_balance: float,
    chat_id: int,
    atmosphere_pct: float = 0.0,
    atmosphere_report: Optional[Dict[str, Any]] = None,
    cfg: Optional[Dict[str, Any]] = None,
    visit_n: int = 1,
) -> str:
    """Короткий обзор: главы в цитатах, минимум текста."""
    cfg = cfg or get_settings()
    level = get_chat_level(chat_id)
    bal = max(0, int(float(chat_balance or 0)))
    bal_fmt = f"{bal:,}".replace(",", ".")
    report = atmosphere_report or {}
    atmo_now = float(report.get("pct") if report else atmosphere_pct) or float(atmosphere_pct or 0)
    rec = recommended_play_bet(
        bal, chat_id=chat_id, atmosphere_pct=atmo_now, cfg=cfg,
    )
    cap = effective_stake_cap(chat_id, atmosphere_pct=atmo_now, cfg=cfg)
    base_cap = stake_cap_for_level(level, cfg)
    if level >= 5:
        base_cap = None
    atmo_on = bool(cfg.get("atmosphere_enabled", True))
    atmo_max = _as_int(cfg.get("atmosphere_max_bonus_pct"), 40)
    caps = cfg.get("stake_caps") or {}
    p0 = _as_int(cfg.get("level_0_cap"), 30)
    teaser = _next_level_teaser(chat_id, cfg)
    hook = visit_hook_line(visit_n)

    def _cap(n: int) -> str:
        if n >= 5:
            return "∞"
        v = caps.get(str(n))
        return str(v) if v is not None else "—"

    if cap is None:
        level_body = f"{stars_label(level)}\nставки <b>без лимита уровня</b>"
    else:
        level_body = f"{stars_label(level)}\nставки <b>до {cap} кут</b>"
        if atmo_on and atmo_now > 0.05 and base_cap is not None:
            level_body += (
                f"\nбаза <b>{base_cap}</b> · живость <b>+{atmo_now:g}%</b> → <b>{cap}</b>"
            )
        level_body += f"\nкомфорт ≈ <b>{rec}</b> кут"

    if atmo_on:
        pulse = _society_pulse_lines(
            report if report else {"pct": atmo_now}, cfg=cfg, compact=True,
        )
        bonus_line = (
            f"активность и поддержка донатеров "
            f"(кто <b>пишет</b> в группе) · до <b>+{atmo_max}%</b>"
        )
    else:
        pulse = "бонус активности выключен"
        bonus_line = "бонус активности сейчас выключен"

    if level >= 5:
        next_block = (
            f"<blockquote>"
            f"<b>Следующий шаг</b>\n"
            f"{stars_label(5)} · выше поднимать некуда"
            f"</blockquote>"
        )
    elif teaser:
        next_block = (
            f"<blockquote>"
            f"<b>Следующий шаг</b>\n"
            f"{teaser}\n"
            f"<i>платите вы — лимит растёт для всех</i>"
            f"</blockquote>"
        )
    else:
        next_block = (
            f"<blockquote>"
            f"<b>Следующий шаг</b>\n"
            f"скоро будет доступен"
            f"</blockquote>"
        )

    return (
        f"<tg-emoji emoji-id='5472146462362048818'>💡</tg-emoji> "
        f"<b>Баланс группы</b>\n"
        f"<i>{journey_step_label('meet')} · ~20 секунд · {hook}</i>\n\n"
        f"<blockquote>"
        f"<b>Касса</b>\n"
        f"<tg-emoji emoji-id='{ICON_BALANCE_KUT}'>⭐️</tg-emoji> "
        f"<b>{bal_fmt} кут</b>\n"
        f"<i>выигрыши — отсюда · проигрыши — сюда</i>"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Уровень {level}</b>\n"
        f"{level_body}"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Пульс</b>\n"
        f"{pulse}"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Смысл</b>\n"
        f"• <b>касса</b> — запас чата на игры\n"
        f"• <b>уровень</b> — базовый потолок всем\n"
        f"• <b>живость</b> — может поднять потолок\n"
        f"• <b>вклад</b> — выше лимит + метка вам"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Важно</b>\n"
        f"вклад не даёт личные куты\n"
        f"бонус не меняет кассу и бесплатные задания\n"
        f"<i>{bonus_line}</i>"
        f"</blockquote>\n\n"
        f"{next_block}\n\n"
        f"<blockquote>"
        f"<b>Потолки</b>\n"
        f"<code>"
        f"0→{p0} · 1→{_cap(1)} · 2→{_cap(2)} · 3→{_cap(3)} · 4→{_cap(4)} · 5→{_cap(5)}"
        f"</code>"
        f"</blockquote>"
    )


def build_details_keyboard(*, chat_id: int, cfg: Optional[Dict[str, Any]] = None):
    """Клавиатура обзора: повышение + назад."""
    from aiogram.types import InlineKeyboardMarkup

    cfg = cfg or get_settings()
    rows = []
    cta = raise_cta_label(chat_id, cfg)
    if cta:
        rows.append([_btn(
            text=cta,
            callback_data="gbl_raise",
            style="primary",
            icon_custom_emoji_id=ICON_RAISE_LEVEL,
        )])
    rows.append([_btn(
        text="К балансу группы",
        callback_data="back_to_balance",
        style="default",
        icon_custom_emoji_id=ICON_BACK,
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _btn(**kwargs):
    """InlineKeyboardButton с мягким fallback без style/icon."""
    from aiogram.types import InlineKeyboardButton
    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs = dict(kwargs)
        kwargs.pop("style", None)
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(**kwargs)


def build_main_screen_html(
    *,
    chat_id: int,
    chat_balance: float,
    atmosphere_pct: float = 0.0,
    atmosphere_report: Optional[Dict[str, Any]] = None,
    cfg: Optional[Dict[str, Any]] = None,
) -> str:
    """Главный «бч» как раньше: только hero premium-эмодзи. Сумма — на кнопке."""
    del chat_id, chat_balance, atmosphere_pct, atmosphere_report, cfg
    return f"<tg-emoji emoji-id='{ICON_HERO_BEACH}'>🏖</tg-emoji>"


def build_main_keyboard(
    *,
    chat_id: int,
    chat_balance: float,
    atmosphere_pct: float = 0.0,
    cfg: Optional[Dict[str, Any]] = None,
):
    """Касса → повышение → обзор."""
    from aiogram.types import InlineKeyboardMarkup

    cfg = cfg or get_settings()
    bal = max(0, int(float(chat_balance or 0)))
    bal_fmt = f"{bal:,}".replace(",", ".")
    style = balance_health_style(
        bal, chat_id=chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg,
    )
    cta = raise_cta_label(chat_id, cfg)

    rows = [
        [_btn(
            text=f"{bal_fmt} кут",
            callback_data="group_balance_overview",
            style=style,
            icon_custom_emoji_id=ICON_BALANCE_KUT,
        )],
    ]
    if cta:
        rows.append([_btn(
            text=cta,
            callback_data="gbl_raise",
            style="primary",
            icon_custom_emoji_id=ICON_RAISE_LEVEL,
        )])
    rows.append([_btn(
        text="Как это устроено",
        callback_data=f"group_balance_details:{bal}",
        style="default",
        icon_custom_emoji_id=ICON_DETAILS,
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_raise_keyboard(*, chat_id: int, cfg: Optional[Dict[str, Any]] = None):
    from aiogram.types import InlineKeyboardMarkup

    cfg = cfg or get_settings()
    packages = build_level_packages(chat_id, cfg)
    rows = []
    for pkg in packages:
        to_level = int(pkg["to_level"])
        pay = int(pkg["pay"])
        pct = int(pkg.get("save_pct") or 0)
        if to_level >= 5:
            base_txt = f"Вершина · {pay}⭐"
        else:
            base_txt = f"До {pkg['cap_label']} · {pay}⭐"
        if pct > 0:
            base_txt = f"{base_txt} (−{pct}%)"
        if pkg.get("recommended"):
            base_txt = f"★ {base_txt}"
        if len(base_txt) > 64:
            base_txt = f"Ур.{to_level} · {pay}⭐" + (f" (−{pct}%)" if pct else "")
        style = "success" if pkg.get("recommended") else "primary"
        rows.append([_btn(
            text=base_txt,
            callback_data=f"gbl_pay:{chat_id}:{to_level}:{pay}",
            style=style,
            icon_custom_emoji_id=ICON_RAISE_LEVEL,
        )])
    rows.append([_btn(
        text="К балансу группы",
        callback_data="back_to_balance",
        style="default",
        icon_custom_emoji_id=ICON_BACK,
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_raise_screen_html(
    *,
    chat_id: int,
    cfg: Optional[Dict[str, Any]] = None,
    badge_title: Optional[str] = None,
    visit_n: int = 1,
    atmosphere_pct: float = 0.0,
) -> str:
    """Экран повышения: пакеты, визуальная скидка, выгода, подарок."""
    cfg = cfg or get_settings()
    cur = get_chat_level(chat_id)
    packages = build_level_packages(chat_id, cfg)
    decide = journey_step_label("decide")
    hook = visit_hook_line(visit_n)
    if not packages:
        return (
            f"<tg-emoji emoji-id='{ICON_RAISE_LEVEL}'>⭐️</tg-emoji> "
            f"<b>Вершина</b>\n"
            f"<i>{decide} · {hook}</i>\n\n"
            f"<blockquote>"
            f"<b>Статус</b>\n"
            f"{stars_label(5)} · ставки <b>без лимита уровня</b>"
            f"</blockquote>"
        )
    rec = next((p for p in packages if p.get("recommended")), packages[0])
    max_pkg = packages[-1]
    title = (
        (badge_title or "").strip()
        or str(rec.get("badge_title") or badge_title_for_level(rec["to_level"], cfg))
    )
    gain = stake_delta_for_step(
        from_level=cur,
        to_level=int(rec["to_level"]),
        atmosphere_pct=atmosphere_pct,
        cfg=cfg,
    )
    gain_max = stake_delta_for_step(
        from_level=cur,
        to_level=int(max_pkg["to_level"]),
        atmosphere_pct=atmosphere_pct,
        cfg=cfg,
    )
    if gain.get("delta"):
        benefit = (
            f"стандарт: {gain['old_lim']} → <b>{gain['new_lim']}</b> "
            f"(<b>+{gain['delta']}</b> кут)\n"
        )
    else:
        benefit = f"стандарт: {gain['old_lim']} → <b>{gain['new_lim']}</b>\n"
    if max_pkg["to_level"] != rec["to_level"]:
        if gain_max.get("delta"):
            benefit += (
                f"премиум: сразу до <b>{gain_max['new_lim']}</b> "
                f"(<b>+{gain_max['delta']}</b> кут всей группе)"
            )
        else:
            benefit += f"премиум: сразу до <b>{gain_max['new_lim']}</b>"
    ladder = build_price_ladder_html(chat_id=chat_id, cfg=cfg)
    proof = social_proof_line()
    return (
        f"<tg-emoji emoji-id='{ICON_RAISE_LEVEL}'>⭐️</tg-emoji> "
        f"<b>Повышение уровня</b>\n"
        f"<i>{decide} · {stars_label(cur)} → пакеты · {hook}</i>\n\n"
        f"<blockquote>"
        f"<b>Выгода группе</b>\n"
        f"{benefit}"
        f"</blockquote>\n\n"
        f"{ladder}\n\n"
        f"<blockquote>"
        f"<b>Подарок за вклад</b>\n"
        f"метка «<b>{title}</b>» и выше по пути · именной анонс"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Скидка группы</b>\n"
        f"рекомендуем «<b>{rec['role']}</b>»: "
        f"{format_package_price_line(rec)}\n"
        f"<i>{proof}</i>\n"
        f"<i>цена пакета подстраивается под силу этой группы</i>\n"
        f"<i>личные куты не начисляются</i>"
        f"</blockquote>"
    )


def gbl_start_payload(chat_id: int, to_level: int, price: int) -> str:
    """Deep-link payload для /start (лимит Telegram ~64 символа)."""
    return f"gblevel_{int(chat_id)}_{int(to_level)}_{int(price)}"


def build_pay_dm_bridge_html(
    *,
    chat_id: int,
    to_level: int,
    price: int,
    cfg: Optional[Dict[str, Any]] = None,
    atmosphere_pct: float = 0.0,
    chat_title: Optional[str] = None,
) -> str:
    """Подтверждение перед ЛС — пакет, скидка, выгода."""
    cfg = cfg or get_settings()
    finish = journey_step_label("finish")
    pkg = find_level_package(chat_id, to_level, price, cfg)
    from_level = int(pkg["from_level"]) if pkg else get_chat_level(chat_id)
    gain = stake_delta_for_step(
        from_level=from_level,
        to_level=to_level,
        atmosphere_pct=atmosphere_pct,
        cfg=cfg,
    )
    title = (
        str(pkg.get("badge_title")) if pkg
        else badge_title_for_level(to_level, cfg)
    )
    group_bit = ""
    if (chat_title or "").strip():
        group_bit = f"группа «<b>{_html_escape(chat_title.strip())}</b>»\n"
    delta_bit = (
        f"\nгруппа получит <b>+{gain['delta']} кут</b> к потолку"
        if gain.get("delta") else ""
    )
    steps = int(pkg["steps"]) if pkg else max(1, int(to_level) - from_level)
    price_line = format_package_price_line(pkg) if pkg else f"<b>{price}</b>⭐"
    role = str(pkg.get("role") or "пакет") if pkg else "пакет"
    return (
        f"<tg-emoji emoji-id='{ICON_RAISE_LEVEL}'>⭐️</tg-emoji> "
        f"<b>{finish}</b>\n"
        f"<i>осталось подтвердить оплату со скидкой</i>\n\n"
        f"<blockquote>"
        f"<b>Пакет «{role}»</b>\n"
        f"{group_bit}"
        f"уровень <b>{from_level}</b> → <b>{to_level}</b> · "
        f"{steps} {_ru_steps_word(steps)}\n"
        f"{gain['old_lim']} → <b>{gain['new_lim']}</b>{delta_bit}"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Ваша цена</b>\n"
        f"{price_line}\n"
        f"метка «<b>{title}</b>» · {social_proof_line()}"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>После нажатия</b>\n"
        f"откроются личные сообщения — счёт на <b>{int(price)} звёзд</b>"
        f"</blockquote>"
    )


def _ru_steps_word(n: int) -> str:
    n = abs(int(n or 0))
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return "шаг"
    if 2 <= n10 <= 4 and not (12 <= n100 <= 14):
        return "шага"
    return "шагов"


def _html_escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_pay_dm_bridge_keyboard(
    *,
    bot_username: str,
    chat_id: int,
    to_level: int,
    price: int,
    cfg: Optional[Dict[str, Any]] = None,
):
    """URL в ЛС — оплата по цене со скидкой (pay = нужда проекта)."""
    from aiogram.types import InlineKeyboardMarkup

    cfg = cfg or get_settings()
    uname = (bot_username or "").lstrip("@").strip() or "CuteGamingBot"
    payload = gbl_start_payload(chat_id, to_level, price)
    pkg = find_level_package(chat_id, to_level, price, cfg)
    pct = int((pkg or {}).get("save_pct") or 0)
    pay_txt = f"Оплатить {price}⭐"
    if pct > 0:
        pay_txt = f"Оплатить {price}⭐ (−{pct}%)"
    if len(pay_txt) > 64:
        pay_txt = f"Оплатить {price} звёзд"
    rows = [
        [_btn(
            text=pay_txt,
            url=f"https://t.me/{uname}?start={payload}",
            style="success",
            icon_custom_emoji_id=ICON_RAISE_LEVEL,
        )],
        [_btn(
            text="К пакетам",
            callback_data="gbl_raise",
            style="default",
            icon_custom_emoji_id=ICON_BACK,
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def strip_tg_emoji(html: str) -> str:
    """Fallback при DOCUMENT_INVALID — обычный unicode из tg-emoji."""
    import re
    return re.sub(
        r"<tg-emoji[^>]*>(.*?)</tg-emoji>",
        lambda m: (m.group(1) or "").strip(),
        html or "",
        flags=re.I | re.S,
    )


def decide_gc_play_mode(
    *,
    bet: int,
    game_max_bet: int,
    has_assignment: bool,
    is_free: bool,
    gc_bet_limit: Optional[int],
) -> Dict[str, Any]:
    """Режим ставки: free / paid / reject.

    Правила:
    - бесплатное задание: betlimit действует только на free-режим;
      ставка выше лимита free → обычная игра (свои куты + БЧ + уровни ★);
    - обычное задание: betlimit сужает потолок paid-режима;
    - free-режим не использует уровни баланса группы (GBL).
    """
    try:
        bet_i = int(bet)
        game_max = max(0, int(game_max_bet))
    except Exception:
        return {"mode": "reject", "max": 0, "reason": "bad_bet"}

    lim: Optional[int] = None
    try:
        if gc_bet_limit is not None:
            lim_i = int(gc_bet_limit)
            if lim_i > 0:
                lim = lim_i
    except Exception:
        lim = None

    if bet_i <= 0:
        return {"mode": "reject", "max": 0, "reason": "bad_bet"}
    if game_max > 0 and bet_i > game_max:
        return {"mode": "reject", "max": game_max, "reason": "game_max"}

    if has_assignment and is_free:
        free_max = lim if lim is not None else (game_max if game_max > 0 else bet_i)
        if bet_i <= free_max:
            return {"mode": "free", "max": free_max, "reason": "free"}
        # Выше потолка бесплатного задания — играем на реальные куты
        return {"mode": "paid", "max": game_max if game_max > 0 else bet_i, "reason": "free_overflow_to_paid"}

    if lim is not None:
        paid_max = min(game_max, lim) if game_max > 0 else lim
        if bet_i > paid_max:
            return {"mode": "reject", "max": paid_max, "reason": "gc_max"}
        return {"mode": "paid", "max": paid_max, "reason": "paid"}

    return {
        "mode": "paid",
        "max": game_max if game_max > 0 else bet_i,
        "reason": "paid",
    }


def format_game_max_bet_html(max_bet: int) -> str:
    mb = max(0, int(max_bet))
    return (
        f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
        f"<b>Максимальная ставка в этой игре {_fmt_int_local(mb)} кут</b>"
    )


def _fmt_int_local(n: int) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return str(n)


async def reject_if_bet_over_group_level(
    message,
    bet: int,
    *,
    is_free_play: bool = False,
) -> bool:
    """Если ставка выше лимита уровня группы — отвечает и возвращает True.

    На бесплатные задания (is_free_play=True) система ★ не распространяется.
    """
    try:
        if is_free_play:
            return False
        cfg = get_settings()
        if not cfg.get("enabled", True):
            return False
        chat = getattr(message, "chat", None)
        if chat is None or str(getattr(chat, "type", "") or "") == "private":
            return False
        chat_id = int(chat.id)
        atmo = 0.0
        try:
            from main import db as _db
            atmo = await resolve_atmosphere_pct(chat_id, db=_db)
        except Exception:
            atmo = 0.0
        cap = effective_stake_cap(chat_id, atmosphere_pct=atmo, cfg=cfg)
        if cap is None:
            return False
        if int(bet) <= int(cap):
            return False
        level = get_chat_level(chat_id)
        cta = raise_cta_label(chat_id, cfg) or "Открыть ставки шире"
        text = (
            f"<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji> "
            f"<b>Лимит ставки</b>\n\n"
            f"<blockquote>"
            f"<b>Сейчас</b>\n"
            f"ставки <b>до {cap} кут</b> · {stars_label(level)}"
            f"</blockquote>\n\n"
            f"<blockquote>"
            f"<b>Как открыть шире</b>\n"
            f"напишите <b>бч</b> → «{cta}»\n"
            f"<tg-spoiler>бесплатные задания этот лимит не затрагивает</tg-spoiler>"
            f"</blockquote>"
        )
        try:
            await message.reply(text, parse_mode="HTML")
        except Exception:
            await message.reply(
                f"⭐ Сейчас ставки до {cap} кут.\n"
                f"Напишите «бч» → «{cta}».",
            )
        return True
    except Exception as e:
        print(f"[GBL] stake reject failed: {e!r}")
        return False


def build_overview_alert(
    *,
    chat_id: int,
    chat_balance: float,
    atmosphere_pct: float = 0.0,
    cfg: Optional[Dict[str, Any]] = None,
    visit_n: int = 1,
) -> str:
    """Короткий alert по кассе (лимит Telegram ~200)."""
    cfg = cfg or get_settings()
    level = get_chat_level(chat_id)
    rec = recommended_play_bet(
        chat_balance, chat_id=chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg,
    )
    cap = effective_stake_cap(chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg)
    lim = "без лимита" if cap is None else f"до {cap}"
    atmo = float(atmosphere_pct or 0)
    head = "Баланс группы" if visit_n <= 1 else "С возвращением"
    line = (
        f"{head}\n"
        f"{stars_label(level)} · ставки {lim}"
        + (f" · +{atmo:g}%" if atmo > 0.05 else "")
        + f"\nКомфорт ≈ {rec}"
    )
    return line[:190]


def build_gift_announcement_html(
    *,
    sponsor_name_html: str,
    to_level: int,
    price_stars: int,
    chat_id: int,
    atmosphere_pct: float = 0.0,
    chat_title: Optional[str] = None,
    from_level: Optional[int] = None,
) -> str:
    """Анонс в группу: кто, куда, за сколько, что открылось."""
    cfg = get_settings()
    prev = int(from_level) if from_level is not None else max(0, int(to_level) - 1)
    gain = stake_delta_for_step(
        from_level=prev,
        to_level=to_level,
        atmosphere_pct=atmosphere_pct,
        cfg=cfg,
    )
    new_lim = gain["new_lim"]
    title = badge_title_for_level(to_level, cfg)
    group_name = (chat_title or "").strip() or f"чат {chat_id}"
    delta_line = ""
    if gain.get("delta"):
        delta_line = f"\nприрост потолка · <b>+{gain['delta']} кут</b> для всех"
    week = count_purchases_since(7 * 86400)
    proof = (
        f"за неделю таких вкладов уже <b>{week}</b>"
        if week >= 2
        else social_proof_line()
    )
    return (
        f"<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji> "
        f"<b>Группу усилили</b>\n\n"
        f"<blockquote>"
        f"<b>Герой</b>\n"
        f"{sponsor_name_html}"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Где</b>\n"
        f"«<b>{_html_escape(group_name)}</b>»\n"
        f"{stars_label(prev)} → <b>{stars_label(to_level)}</b>"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Что открылось</b>\n"
        f"{gain['old_lim']} → <b>{new_lim}</b>{delta_line}"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Вклад</b>\n"
        f"<b>{int(price_stars)} звёзд</b> · метка «<b>{title}</b>»\n"
        f"<i>{proof}</i>\n"
        f"<i>напишите бч — новый потолок уже действует</i>"
        f"</blockquote>"
    )


def build_buyer_hero_html(
    *,
    to_level: int,
    price_stars: int,
    chat_id: int,
    atmosphere_pct: float = 0.0,
    chat_title: Optional[str] = None,
    from_level: Optional[int] = None,
    badge_title: Optional[str] = None,
) -> str:
    """ЛС покупателю: вы герой, факты покупки, скидка, подарок."""
    cfg = get_settings()
    prev = int(from_level) if from_level is not None else max(0, int(to_level) - 1)
    steps = max(1, int(to_level) - prev)
    gain = stake_delta_for_step(
        from_level=prev,
        to_level=to_level,
        atmosphere_pct=atmosphere_pct,
        cfg=cfg,
    )
    title = (badge_title or "").strip() or badge_title_for_level(to_level, cfg)
    group_name = (chat_title or "").strip() or f"чат {chat_id}"
    listed = visual_list_price(int(price_stars), chat_id, cfg)
    if steps >= 2:
        listed = max(listed, int(math.ceil(listed * 1.08)))
    listed = max(listed, int(price_stars) + 1)
    save = max(0, listed - int(price_stars))
    save_pct = int(round(100.0 * save / listed)) if listed else 0
    if gain.get("delta"):
        benefit = (
            f"вы открыли группе <b>+{gain['delta']} кут</b> к потолку ставки\n"
            f"{gain['old_lim']} → <b>{gain['new_lim']}</b>"
        )
    else:
        benefit = (
            f"вы открыли группе ставки <b>{gain['new_lim']}</b>\n"
            f"было: {gain['old_lim']}"
        )
    price_bit = f"оплачено · <b>{int(price_stars)} звёзд</b>"
    if save_pct > 0:
        price_bit += f"\nскидка группы · <s>{listed}</s> → <b>{int(price_stars)}</b> (−{save_pct}%)"
    return (
        f"<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji> "
        f"<b>Вы усилили группу</b>\n"
        f"<i>этот вклад меняет игру для всех</i>\n\n"
        f"<blockquote>"
        f"<b>Ваш вклад</b>\n"
        f"группа «<b>{_html_escape(group_name)}</b>»\n"
        f"уровень <b>{prev}</b> → <b>{to_level}</b> · {stars_label(to_level)}\n"
        f"{steps} {_ru_steps_word(steps)}\n"
        f"{price_bit}"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Что получила группа</b>\n"
        f"{benefit}"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Ваш подарок</b>\n"
        f"метка «<b>{title}</b>» в профиле"
        + (f" и метки пути" if steps > 1 else "")
        + "\n"
        f"именной анонс уже ушёл в группу\n"
        f"<i>{social_proof_line()}</i>"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Дальше</b>\n"
        f"вернитесь в группу или напишите <b>бч</b> — "
        f"новый потолок уже действует"
        f"</blockquote>"
    )
