# -*- coding: utf-8 -*-
"""Уровни баланса группы (★1…★5).

Не путать с «столом» в текстах для игроков — везде «баланс группы».
Конфиг полностью настраивается (админка → creator-only).

Хранение уровней: таблица chat, столбец group_balance_level (ключ chat_id).
JSON в data/group_balance_level/ — быстрый зеркальный кэш + настройки/бейджи.
"""

from __future__ import annotations

import asyncio
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

# Premium custom emoji — голубой пак из системы челленджей (gc_emoji)
from bot.funcs.gc_emoji import gc_emoji_id, gc_tg  # noqa: E402

ICON_HERO_BEACH = gc_emoji_id("🏝") or "5253567918741923731"
ICON_BALANCE_KUT = gc_emoji_id("💰") or "5224257782013769471"
ICON_RAISE_LEVEL = gc_emoji_id("🏆") or "5188344996356448758"
ICON_CAP_LIMIT = gc_emoji_id("🎯") or "5350460637182993292"
ICON_BACK = gc_emoji_id("🔙") or "5255703720078879038"
ICON_DETAILS = gc_emoji_id("❓") or "5436113877181941026"
ICON_STAR = gc_emoji_id("⭐️") or "6005661956931850799"
ICON_FIRE = gc_emoji_id("🔥") or "5420315771991497307"
ICON_GEM = gc_emoji_id("💎") or "5280922999241859582"
ICON_PALM = gc_emoji_id("🌴") or "5449372007432985754"


def gbl_tg(emoji: str) -> str:
    """Голубой premium-эмодзи из пака челленджей."""
    return gc_tg(emoji)


# Единые kwargs для сообщений бч — без превью групп/ссылок
GBL_MSG_KW: Dict[str, Any] = {
    "parse_mode": "HTML",
    "disable_web_page_preview": True,
}

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
        return "первый раз здесь"
    if n <= 3:
        return "вы уже заходили сюда"
    if n <= 7:
        return "с возвращением"
    return "цифры могли обновиться"


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


def _clamp_level(level: Any) -> int:
    return max(0, min(5, _as_int(level, 0)))


def _mirror_level_local(
    chat_id: int,
    level: int,
    *,
    sponsor_id: Optional[int] = None,
) -> int:
    """Зеркало в JSON-кэш (быстрые sync-чтения между запросами к БД)."""
    level = _clamp_level(level)
    prev = _chat_levels.get(str(int(chat_id))) or {}
    prev_sponsor = prev.get("last_sponsor_id")
    _chat_levels[str(int(chat_id))] = {
        "level": level,
        "updated_at": time.time(),
        "last_sponsor_id": (
            int(sponsor_id) if sponsor_id is not None
            else (int(prev_sponsor) if prev_sponsor is not None else None)
        ),
        "source": "db",
    }
    return level


def get_chat_level(chat_id: int) -> int:
    """Sync-чтение уровня: JSON-зеркало (после старта синхронизировано с chat)."""
    row = _chat_levels.get(str(int(chat_id))) or {}
    return _clamp_level(row.get("level"))


async def _resolve_db():
    try:
        from main import db as _db
        return _db
    except Exception:
        try:
            from bot.db_create.db import db as _db
            return _db
        except Exception:
            return None


def _schedule_db_level_write(
    chat_id: int,
    level: int,
    *,
    sponsor_id: Optional[int] = None,
) -> None:
    """Фоновая запись в chat, если нет await-контекста."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _run() -> None:
        try:
            db = await _resolve_db()
            if db is None or not hasattr(db, "set_chat_group_balance_level"):
                return
            await db.set_chat_group_balance_level(
                int(chat_id), int(level), sponsor_id=sponsor_id,
            )
        except Exception as e:
            print(f"[GBL] background DB write fail chat={chat_id}: {e!r}")

    try:
        loop.create_task(_run())
    except Exception as e:
        print(f"[GBL] schedule DB write fail chat={chat_id}: {e!r}")


async def get_chat_level_async(
    chat_id: int,
    *,
    db=None,
    mirror: bool = True,
) -> int:
    """Авторитетное чтение уровня из таблицы chat."""
    cid = int(chat_id)
    _db = db
    if _db is None:
        _db = await _resolve_db()
    if _db is not None and hasattr(_db, "get_chat_group_balance_level"):
        try:
            sponsor_id = None
            if hasattr(_db, "get_chat_group_balance_level_row"):
                row = await _db.get_chat_group_balance_level_row(cid)
                level = _clamp_level(row.get("level"))
                sponsor_id = row.get("sponsor_id")
            else:
                level = _clamp_level(await _db.get_chat_group_balance_level(cid))
            if mirror:
                _mirror_level_local(cid, level, sponsor_id=sponsor_id)
            return level
        except Exception as e:
            print(f"[GBL] get_chat_level_async DB fail chat={cid}: {e!r}")
    return get_chat_level(cid)


def set_chat_level(
    chat_id: int,
    level: int,
    *,
    sponsor_id: Optional[int] = None,
) -> int:
    """Пишет зеркало сразу и планирует запись в chat.group_balance_level."""
    level = _mirror_level_local(chat_id, level, sponsor_id=sponsor_id)
    _schedule_db_level_write(chat_id, level, sponsor_id=sponsor_id)
    return level


async def set_chat_level_async(
    chat_id: int,
    level: int,
    *,
    sponsor_id: Optional[int] = None,
    db=None,
) -> int:
    """Гарантированная запись уровня в таблицу chat (+ зеркало JSON)."""
    level = _clamp_level(level)
    cid = int(chat_id)
    _mirror_level_local(cid, level, sponsor_id=sponsor_id)
    _db = db
    if _db is None:
        _db = await _resolve_db()
    if _db is None or not hasattr(_db, "set_chat_group_balance_level"):
        raise RuntimeError("Database unavailable for group_balance_level write")
    saved = await _db.set_chat_group_balance_level(
        cid, level, sponsor_id=sponsor_id,
    )
    return _clamp_level(saved)


async def sync_group_balance_levels_with_db(db=None) -> Dict[str, Any]:
    """Старт бота: схема → JSON→chat → chat→JSON. Источник истины — таблица chat."""
    _db = db
    if _db is None:
        _db = await _resolve_db()
    if _db is None:
        return {"ok": False, "error": "no_db"}

    await _db.ensure_group_balance_level_schema()

    # 1) миграция старого JSON-кэша → chat (GREATEST, чтобы не понизить)
    push_rows: List[Tuple[int, int, Optional[int]]] = []
    for key, raw in _chat_levels.items():
        try:
            cid = int(key)
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        lvl = _clamp_level(raw.get("level"))
        if lvl <= 0:
            continue
        sid_raw = raw.get("last_sponsor_id")
        sid = int(sid_raw) if sid_raw is not None else None
        push_rows.append((cid, lvl, sid))

    pushed = 0
    if push_rows and hasattr(_db, "upsert_group_balance_levels_bulk"):
        pushed = await _db.upsert_group_balance_levels_bulk(push_rows)

    # 2) chat → JSON: после рестарта зеркало = БД
    pulled = 0
    if hasattr(_db, "list_chat_group_balance_levels"):
        db_rows = await _db.list_chat_group_balance_levels(only_positive=True)
        for row in db_rows:
            _mirror_level_local(
                int(row["chat_id"]),
                int(row["level"]),
                sponsor_id=row.get("sponsor_id"),
            )
            pulled += 1

    print(
        f"[GBL] levels synced with chat: pushed={pushed} "
        f"json_candidates={len(push_rows)} pulled={pulled}"
    )
    return {
        "ok": True,
        "pushed": int(pushed),
        "json_candidates": len(push_rows),
        "pulled": int(pulled),
    }


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
    """Цена пакета простым языком + визуальная скидка."""
    pay = int(pkg.get("pay") or 0)
    listed = int(pkg.get("list") or pay)
    pct = int(pkg.get("save_pct") or 0)
    if listed > pay and pct > 0:
        return (
            f"было <s>{listed}</s> звёзд → сейчас <b>{pay}</b> звёзд "
            f"(скидка <b>{pct}%</b>)"
        )
    return f"к оплате <b>{pay}</b> звёзд"


def format_profile_link_html(user_id: int, display_name: str) -> str:
    """Кликабельное имя → профиль Telegram."""
    name = _html_escape((display_name or "").strip() or str(user_id))
    return f'<a href="tg://user?id={int(user_id)}">{name}</a>'


def format_group_link_html(
    title: str,
    *,
    url: Optional[str] = None,
    chat_id: int = 0,
) -> str:
    """Кликабельное название группы → t.me / invite."""
    name = _html_escape((title or "").strip() or (f"чат {chat_id}" if chat_id else "группа"))
    link = (url or "").strip()
    if link.startswith("http://") or link.startswith("https://") or link.startswith("tg://"):
        return f'<a href="{_html_escape(link)}">{name}</a>'
    return f"<b>{name}</b>"


def explain_package_plain(pkg: Dict[str, Any]) -> str:
    """Объяснение пакета так, чтобы понял даже новичок."""
    steps = int(pkg.get("steps") or 1)
    to_level = int(pkg.get("to_level") or 1)
    from_level = int(pkg.get("from_level") or 0)
    role = str(pkg.get("role") or "пакет")
    cap_label = str(pkg.get("cap_label") or "?")
    if to_level >= 5:
        open_bit = "ставки <b>без лимита уровня</b>"
    else:
        open_bit = f"ставки <b>до {cap_label} кут</b>"
    if steps == 1:
        path = f"поднять группу с уровня <b>{from_level}</b> на <b>{to_level}</b>"
    else:
        path = (
            f"сразу поднять с уровня <b>{from_level}</b> до <b>{to_level}</b> "
            f"(это <b>{steps}</b> {_ru_steps_word(steps)} сразу)"
        )
    rec = " · <b>обычно выбирают этот</b>" if pkg.get("recommended") else ""
    return (
        f"<b>{role}</b>{rec}\n"
        f"{path}\n"
        f"после покупки: {open_bit}\n"
        f"{format_package_price_line(pkg)}"
    )


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
            f"{gbl_tg('⭐️')} "
            f"<b>{stars_label(lvl)}</b> · {title}"
        )
    body = "\n".join(lines)
    return (
        f"<blockquote>"
        f"{gbl_tg('📋')} "
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
    """Витрина пакетов: простое объяснение + визуальная скидка."""
    cfg = cfg or get_settings()
    packages = build_level_packages(chat_id, cfg)
    if not packages:
        return ""
    blocks = [explain_package_plain(pkg) for pkg in packages]
    return (
        f"<blockquote>"
        f"<b>Что можно купить</b>\n"
        f"<i>звёзды здесь — это плата Telegram Stars, не куты</i>\n\n"
        + "\n\n".join(blocks)
        + "\n\n"
        f"<i>нажимаете кнопку пакета → оплачиваете цену «сейчас» → "
        f"лимит ставок растёт для всей группы</i>"
        f"</blockquote>"
    )


async def apply_level_purchase(
    *,
    chat_id: int,
    user_id: int,
    to_level: int,
    price_stars: int,
    db=None,
) -> Dict[str, Any]:
    """Применяет покупку одного или нескольких уровней после оплаты.

    to_level может быть прыжком (0→3). price_stars должен покрывать
    сумму реальных цен шагов (проект не в минусе).
    Уровень сохраняется в таблицу chat по chat_id.
    """
    cfg = get_settings()
    to_level = max(1, min(5, int(to_level)))
    cur = await get_chat_level_async(chat_id, db=db)
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
    try:
        await set_chat_level_async(
            chat_id, to_level, sponsor_id=user_id, db=db,
        )
    except Exception as e:
        print(f"[GBL] apply_level_purchase DB write fail: {e!r}")
        return {
            "ok": False,
            "error": "db_write_failed",
            "level": cur,
            "from_level": from_level,
            "detail": str(e),
        }
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
        lines_c = [
            f"эта группа сейчас <b>{pulse}</b>",
            f"бонус к ставкам: <b>+{pct:g}%</b> из максимума <b>{max_pct}%</b>",
        ]
        if writers > 0 and members > 0:
            lines_c.append(
                f"за месяц писали <b>{writers}</b> из ~<b>{members_fmt}</b>"
            )
        elif writers > 0:
            lines_c.append(f"за месяц писали <b>{writers}</b>")
        else:
            lines_c.append("за месяц почти никто не писал — бонус слабее")
        if donators > 0:
            lines_c.append(
                f"в расчёте <b>{donators}</b> {_ru_donors_word(donators)} "
                f"(те, кто пишет и поддерживает проект)"
            )
        else:
            lines_c.append(f"{donor_bit}")
        return "\n".join(lines_c)

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
    chat_title: Optional[str] = None,
) -> str:
    """Обзор для новичка: как устроена ИМЕННО эта группа."""
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
    group_name = (chat_title or "").strip()
    where = (
        f"в группе «<b>{_html_escape(group_name)}</b>»"
        if group_name else "в <b>этой группе</b>"
    )

    def _cap(n: int) -> str:
        if n >= 5:
            return "∞"
        v = caps.get(str(n))
        return str(v) if v is not None else "—"

    if bal <= 0:
        bal_hint = (
            "сейчас на балансе группы пусто — "
            "крупные игры на общих кутах почти невозможны\n"
            "<i>как улучшить: напишите «положить …» и пополните баланс группы</i>"
        )
    elif bal < 50:
        bal_hint = (
            "кут мало — группе тесно для частых игр\n"
            "<i>как улучшить: пополните баланс группы</i>"
        )
    else:
        bal_hint = (
            "эти куты общие: выигрыш платится отсюда, проигрыш возвращается сюда"
        )

    if cap is None:
        level_now = (
            f"{stars_label(level)} · уровень <b>{level}</b> из 5\n"
            f"сейчас всем можно ставить <b>без лимита уровня</b>"
        )
        how_cap = ""
        plus_cap = "• ставки уже <b>без лимита уровня</b> — это сильный плюс"
    else:
        level_now = (
            f"{stars_label(level)} · уровень <b>{level}</b> из 5\n"
            f"сейчас всем можно ставить <b>до {cap} кут</b>"
        )
        if atmo_on and atmo_now > 0.05 and base_cap is not None:
            how_cap = (
                f"\nкак так вышло: база уровня = <b>{base_cap}</b>, "
                f"живость группы добавила <b>+{atmo_now:g}%</b> → "
                f"итог <b>{cap}</b>"
            )
            plus_cap = (
                f"• открыт потолок ставок <b>до {cap} кут</b>\n"
                f"• живость уже даёт бонус <b>+{atmo_now:g}%</b> "
                f"(без неё было бы {base_cap})"
            )
        else:
            how_cap = (
                f"\nбаза уровня <b>{level}</b> = <b>{base_cap}</b> кут"
                if base_cap is not None else ""
            )
            plus_cap = f"• открыт потолок ставок <b>до {cap} кут</b>"
        if rec > 0:
            level_now += f"\nудобная ставка сейчас ≈ <b>{rec}</b> кут <i>(ориентир)</i>"
        else:
            level_now += (
                "\nудобная ставка сейчас ≈ <b>0</b> — "
                "сначала нужен баланс группы"
            )

    if atmo_on:
        pulse = _society_pulse_lines(
            report if report else {"pct": atmo_now}, cfg=cfg, compact=True,
        )
        room_to_grow = max(0.0, float(atmo_max) - float(atmo_now))
        if room_to_grow > 0.5:
            grow_atmo = (
                f"• ещё можно добрать до <b>+{atmo_max:g}%</b> "
                f"(сейчас +{atmo_now:g}%, запас ≈ <b>{room_to_grow:g}%</b>) — "
                f"пишите в чат и поддерживайте проект"
            )
        else:
            grow_atmo = (
                f"• бонус живости почти на максимуме (+{atmo_now:g}% из {atmo_max}%) — "
                f"держите активность"
            )
    else:
        pulse = "бонус живости для этой группы сейчас выключен"
        grow_atmo = "• бонус живости выключен — усиливайте группу уровнем"

    plus_lines = [plus_cap]
    if bal > 0:
        plus_lines.append(f"• на балансе группы есть <b>{bal_fmt} кут</b> на общие игры")
    else:
        plus_lines.append("• баланс группы пустой — это слабое место прямо сейчас")
    if atmo_on and atmo_now > 0.05:
        plus_lines.append(
            f"• живой чат уже помогает ставкам (+{atmo_now:g}%)"
        )

    improve = [
        "• <b>писать в группу</b> — растёт живость и бонус к потолку ставок",
        "• <b>поддерживать проект</b> (и писать в чат) — бонус считается сильнее",
        "• <b>пополнить баланс группы</b> кутами — больше общих игр",
    ]
    if level < 5:
        improve.append(
            "• <b>поднять уровень звёздами</b> — базовый потолок ставок выше "
            "<b>для всех</b> + метка вам"
        )
    improve.append(grow_atmo)

    if level >= 5:
        next_block = (
            f"<blockquote>"
            f"<b>Как поднять ещё выше</b>\n"
            f"{stars_label(5)} · уровень уже максимальный\n"
            f"<i>дальше усиливайте группу общением и балансом группы</i>"
            f"</blockquote>"
        )
    elif teaser:
        next_block = (
            f"<blockquote>"
            f"<b>Как поднять ещё выше</b>\n"
            f"{teaser}\n"
            f"<i>платите звёздами вы — лимит ставок растёт для всей группы</i>\n"
            f"<i>кнопка ниже откроет пакеты простыми словами</i>"
            f"</blockquote>"
        )
    else:
        next_block = (
            f"<blockquote>"
            f"<b>Как поднять ещё выше</b>\n"
            f"пакеты скоро появятся — загляните чуть позже"
            f"</blockquote>"
        )

    return (
        f"{gbl_tg('❓')} "
        f"<b>Баланс группы</b>\n"
        f"<i>как всё устроено {where} · ~20 секунд · {hook}</i>\n\n"
        f"<blockquote>"
        f"<b>Баланс группы сейчас</b>\n"
        f"{gbl_tg('💰')} "
        f"<b>{bal_fmt} кут</b>\n"
        f"{bal_hint}"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Уровень этой группы</b>\n"
        f"{level_now}{how_cap}\n"
        f"<i>уровень = насколько крупные ставки открыты всем здесь</i>"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Плюсы для этой группы сейчас</b>\n"
        + "\n".join(plus_lines)
        + f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Пульс этой группы</b>\n"
        f"{pulse}"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Зачем это нужно</b>\n"
        f"• <b>баланс группы</b> — общие куты чата на игры\n"
        f"• <b>уровень</b> — какой базовый потолок ставки открыт всем\n"
        f"• <b>живость</b> — активность может чуть поднять этот потолок\n"
        f"• <b>вклад звёздами</b> — выше лимит для всех + метка вам"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Как сделать группу сильнее</b>\n"
        + "\n".join(improve)
        + f"</blockquote>\n\n"
        f"<blockquote>"
        f"<b>Важно</b>\n"
        f"звёзды за уровень <b>не становятся</b> вашими личными кутами\n"
        f"бонус живости <b>не меняет</b> сумму на балансе группы "
        f"и бесплатные задания\n"
        f"<i>бонус живости максимум +{atmo_max}% к базе уровня</i>"
        f"</blockquote>\n\n"
        f"{next_block}\n\n"
        f"<blockquote>"
        f"<b>Лестница уровней</b>\n"
        f"<code>"
        f"0→{p0} · 1→{_cap(1)} · 2→{_cap(2)} · 3→{_cap(3)} · 4→{_cap(4)} · 5→{_cap(5)}"
        f"</code>\n"
        f"<i>цифры — базовый потолок ставки на каждом уровне</i>"
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
    """Главный «бч»: только hero + лёгкий статусный крючок (без цитат/блоков уровня)."""
    del chat_balance, atmosphere_report, atmosphere_pct
    cfg = cfg or get_settings()
    level = get_chat_level(chat_id)
    if level >= 5:
        hook = (
            f"{gbl_tg('🏆')} <b>эта группа уже на вершине</b>\n"
            f"<i>легенды здесь уже пишут историю</i>"
        )
    elif level >= 3:
        hook = (
            f"{gbl_tg('🔥')} <b>группа сильная — до легенды один шаг</b>\n"
            f"<i>ваш вклад поднимает ставки для всех</i>"
        )
    elif level >= 1:
        hook = (
            f"{gbl_tg('💎')} <b>путь к легенде уже начат</b>\n"
            f"<i>сильнее группа — шире ставки для всех</i>"
        )
    else:
        hook = (
            f"{gbl_tg('🏆')} <b>легенда этой группы ещё ждёт своё имя</b>\n"
            f"<i>один вклад — выше лимит ставок для всего чата</i>"
        )
    return f"{gbl_tg('🏝')}\n\n{hook}"


def build_main_keyboard(
    *,
    chat_id: int,
    chat_balance: float,
    atmosphere_pct: float = 0.0,
    cfg: Optional[Dict[str, Any]] = None,
):
    """Баланс → потолок ставок → повышение → обзор."""
    from aiogram.types import InlineKeyboardMarkup

    cfg = cfg or get_settings()
    bal = max(0, int(float(chat_balance or 0)))
    bal_fmt = f"{bal:,}".replace(",", ".")
    level = get_chat_level(chat_id)
    style = balance_health_style(
        bal, chat_id=chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg,
    )
    cta = raise_cta_label(chat_id, cfg)
    bal_btn = f"{bal_fmt} кут · {stars_label(level)}"
    if len(bal_btn) > 64:
        bal_btn = f"{bal_fmt} кут · ур.{level}"

    cap = effective_stake_cap(chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg)
    if cap is None:
        cap_btn = "ставки без лимита"
    else:
        cap_btn = f"ставки до {cap} кут"
    if len(cap_btn) > 64:
        cap_btn = cap_btn[:61] + "…"

    rows = [
        [_btn(
            text=bal_btn,
            callback_data="group_balance_overview",
            style=style,
            icon_custom_emoji_id=ICON_BALANCE_KUT,
        )],
        [_btn(
            text=cap_btn,
            callback_data="gbl_cap_status",
            style="default",
            icon_custom_emoji_id=ICON_CAP_LIMIT,
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
        steps = int(pkg.get("steps") or 1)
        if steps == 1:
            step_bit = "1 уровень"
        elif steps < 5:
            step_bit = f"{steps} уровня"
        else:
            step_bit = f"{steps} уровней"
        if to_level >= 5:
            base_txt = f"{step_bit} · вершина · {pay}⭐"
        else:
            base_txt = f"{step_bit} · до {pkg['cap_label']} · {pay}⭐"
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
    """Экран повышения — просто для новичка + маркетинг пакетов."""
    cfg = cfg or get_settings()
    cur = get_chat_level(chat_id)
    packages = build_level_packages(chat_id, cfg)
    decide = journey_step_label("decide")
    hook = visit_hook_line(visit_n)
    if not packages:
        return (
            f"{gbl_tg('🏆')} "
            f"<b>Вершина</b>\n"
            f"<i>{decide} · {hook}</i>\n\n"
            f"{gbl_tg('💎')} <b>Сейчас</b>\n"
            f"{stars_label(5)} · ставки <b>без лимита уровня</b>\n"
            f"<i>выше поднимать уже некуда — вы среди легенд</i>"
        )
    rec = next((p for p in packages if p.get("recommended")), packages[0])
    title = (
        (badge_title or "").strip()
        or str(rec.get("badge_title") or badge_title_for_level(rec["to_level"], cfg))
    )
    cur_cap = effective_stake_cap(chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg)
    cur_lim = _fmt_lim(cur_cap)
    ladder = build_price_ladder_html(chat_id=chat_id, cfg=cfg)
    proof = social_proof_line()
    return (
        f"{gbl_tg('🏆')} "
        f"<b>Поднять уровень группы</b>\n"
        f"<i>{decide} · {hook}</i>\n\n"
        f"{gbl_tg('🎯')} <b>Сейчас у группы</b>\n"
        f"{stars_label(cur)} · уровень <b>{cur}</b> из 5\n"
        f"можно ставить <b>{cur_lim}</b>\n"
        f"<i>уровень = насколько крупные ставки открыты всем в чате</i>\n\n"
        f"{ladder}\n\n"
        f"{gbl_tg('🔥')} <b>Что вы получите</b>\n"
        f"• выше лимит ставок <b>для всех</b> в группе\n"
        f"• метку «<b>{title}</b>» в профиле\n"
        f"• сообщение в чат, что вклад сделали именно вы\n"
        f"• шанс стать <b>легендой</b> этой группы\n\n"
        f"{gbl_tg('💎')} <b>Важно простыми словами</b>\n"
        f"платите <b>звёздами Telegram</b> — куты на личный баланс "
        f"<b>не приходят</b>\n"
        f"рекомендуем пакет «<b>{rec['role']}</b>»: "
        f"{format_package_price_line(rec)}\n"
        f"<i>{proof}</i>"
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
    group_html: Optional[str] = None,
) -> str:
    """Подтверждение перед ЛС — простыми словами + скидка."""
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
    if group_html:
        group_bit = f"группа: {group_html}\n"
    elif (chat_title or "").strip():
        group_bit = (
            f"группа: {format_group_link_html(chat_title, chat_id=chat_id)}\n"
        )
    else:
        group_bit = ""
    delta_bit = (
        f"\nвсем станет можно ставить на <b>+{gain['delta']} кут</b> больше"
        if gain.get("delta") else ""
    )
    steps = int(pkg["steps"]) if pkg else max(1, int(to_level) - from_level)
    price_line = (
        format_package_price_line(pkg) if pkg
        else f"к оплате <b>{price}</b> звёзд"
    )
    role = str(pkg.get("role") or "пакет") if pkg else "пакет"
    return (
        f"{gbl_tg('🏆')} "
        f"<b>{finish}</b>\n"
        f"<i>остался один шаг — оплата</i>\n\n"
        f"{gbl_tg('🎯')} <b>Что вы покупаете</b>\n"
        f"{group_bit}"
        f"пакет «<b>{role}</b>»: уровень <b>{from_level}</b> → <b>{to_level}</b>\n"
        f"это <b>{steps}</b> {_ru_steps_word(steps)}\n"
        f"сейчас можно: <b>{gain['old_lim']}</b>\n"
        f"станет можно: <b>{gain['new_lim']}</b>{delta_bit}\n\n"
        f"{gbl_tg('💎')} <b>Сколько платите</b>\n"
        f"{price_line}\n"
        f"подарок вам: метка «<b>{title}</b>»\n"
        f"<i>{social_proof_line()}</i>\n\n"
        f"{gbl_tg('🔥')} <b>Что будет после нажатия</b>\n"
        f"откроются личные сообщения с ботом\n"
        f"там придёт счёт на <b>{int(price)} звёзд</b>\n"
        f"<i>куты на личный баланс не начисляются — вы становитесь легендой группы</i>"
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
        f"{gbl_tg('🌴')} "
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
        _db = None
        try:
            from main import db as _db
            # подтягиваем актуальный уровень из chat перед проверкой лимита
            await get_chat_level_async(chat_id, db=_db)
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
            f"{gbl_tg('⭐️')} "
            f"<b>Лимит ставки</b>\n\n"
            f"{gbl_tg('🎯')} <b>Сейчас</b>\n"
            f"ставки <b>до {cap} кут</b> · {stars_label(level)}\n\n"
            f"{gbl_tg('🏆')} <b>Как открыть шире</b>\n"
            f"напишите <b>бч</b> → «{cta}»\n"
            f"<tg-spoiler>бесплатные задания этот лимит не затрагивает</tg-spoiler>"
        )
        try:
            await message.reply(text, **GBL_MSG_KW)
        except Exception:
            await message.reply(
                f"Сейчас ставки до {cap} кут.\n"
                f"Напишите «бч» → «{cta}».",
                disable_web_page_preview=True,
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
    """Короткий alert по балансу группы (лимит Telegram ~200)."""
    cfg = cfg or get_settings()
    level = get_chat_level(chat_id)
    rec = recommended_play_bet(
        chat_balance, chat_id=chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg,
    )
    cap = effective_stake_cap(chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg)
    lim = "без лимита" if cap is None else f"до {cap} кут"
    atmo = float(atmosphere_pct or 0)
    head = "Баланс группы" if visit_n <= 1 else "С возвращением"
    line = (
        f"{head}\n"
        f"Уровень {level}/5 · {stars_label(level)}\n"
        f"Ставки {lim}"
        + (f" · +{atmo:g}%" if atmo > 0.05 else "")
        + f"\nКомфорт ≈ {rec} кут"
    )
    return line[:190]


def build_cap_status_alert(
    *,
    chat_id: int,
    atmosphere_pct: float = 0.0,
    cfg: Optional[Dict[str, Any]] = None,
) -> str:
    """Alert по кнопке «ставки до N» — статус + мягкий пуш к легенде."""
    cfg = cfg or get_settings()
    level = get_chat_level(chat_id)
    cap = effective_stake_cap(chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg)
    lim = "без лимита уровня" if cap is None else f"до {cap} кут"
    if level >= 5:
        line = (
            f"Ставки {lim}\n"
            f"{stars_label(level)} · вершина\n"
            f"Вы уже среди легенд этой группы"
        )
    else:
        cta = raise_cta_label(chat_id, cfg) or "Открыть ставки шире"
        line = (
            f"Сейчас ставки {lim}\n"
            f"{stars_label(level)} · уровень {level} из 5\n"
            f"Станьте легендой: «{cta}»"
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
    group_html: Optional[str] = None,
) -> str:
    """Анонс в группу: кто (ссылка), куда (ссылка), за сколько, что открылось."""
    cfg = get_settings()
    prev = int(from_level) if from_level is not None else max(0, int(to_level) - 1)
    steps = max(1, int(to_level) - prev)
    gain = stake_delta_for_step(
        from_level=prev,
        to_level=to_level,
        atmosphere_pct=atmosphere_pct,
        cfg=cfg,
    )
    new_lim = gain["new_lim"]
    title = badge_title_for_level(to_level, cfg)
    if group_html:
        where = group_html
    else:
        where = format_group_link_html(
            (chat_title or "").strip() or f"чат {chat_id}",
            chat_id=chat_id,
        )
    delta_line = ""
    if gain.get("delta"):
        delta_line = (
            f"\nвсем можно ставить на <b>+{gain['delta']} кут</b> больше"
        )
    week = count_purchases_since(7 * 86400)
    proof = (
        f"за неделю таких вкладов уже <b>{week}</b>"
        if week >= 2
        else social_proof_line()
    )
    return (
        f"{gbl_tg('🏆')} "
        f"<b>В группе появилась легенда</b>\n\n"
        f"{gbl_tg('🔥')} <b>Кто</b>\n"
        f"{sponsor_name_html}\n"
        f"<i>нажмите на имя — откроется профиль</i>\n\n"
        f"{gbl_tg('🏝')} <b>Какая группа</b>\n"
        f"{where}\n"
        f"{stars_label(prev)} → <b>{stars_label(to_level)}</b> "
        f"(уровень <b>{prev}</b> → <b>{to_level}</b>)\n"
        f"<i>нажмите на название — откроется группа</i>\n\n"
        f"{gbl_tg('🎯')} <b>Что изменилось</b>\n"
        f"раньше: <b>{gain['old_lim']}</b>\n"
        f"теперь: <b>{new_lim}</b>{delta_line}\n"
        f"сделано за <b>{steps}</b> {_ru_steps_word(steps)}\n\n"
        f"{gbl_tg('💎')} <b>Сколько вложили</b>\n"
        f"<b>{int(price_stars)} звёзд</b> Telegram\n"
        f"метка герою: «<b>{title}</b>»\n"
        f"<i>{proof}</i>\n"
        f"<i>напишите бч — чтобы увидеть новые ★ и лимит</i>"
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
    group_html: Optional[str] = None,
) -> str:
    """ЛС покупателю: просто, факты, скидка, кликабельная группа."""
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
    if group_html:
        where = group_html
    else:
        where = format_group_link_html(
            (chat_title or "").strip() or f"чат {chat_id}",
            chat_id=chat_id,
        )
    listed = visual_list_price(int(price_stars), chat_id, cfg)
    if steps >= 2:
        listed = max(listed, int(math.ceil(listed * 1.08)))
    listed = max(listed, int(price_stars) + 1)
    save = max(0, listed - int(price_stars))
    save_pct = int(round(100.0 * save / listed)) if listed else 0
    if gain.get("delta"):
        benefit = (
            f"раньше всем можно было: <b>{gain['old_lim']}</b>\n"
            f"теперь всем можно: <b>{gain['new_lim']}</b>\n"
            f"вы дали группе <b>+{gain['delta']} кут</b> к лимиту ставки"
        )
    else:
        benefit = (
            f"раньше: <b>{gain['old_lim']}</b>\n"
            f"теперь: <b>{gain['new_lim']}</b>"
        )
    price_bit = f"вы заплатили <b>{int(price_stars)} звёзд</b>"
    if save_pct > 0:
        price_bit += (
            f"\nскидка: было <s>{listed}</s> → стало <b>{int(price_stars)}</b> "
            f"(−{save_pct}%)"
        )
    return (
        f"{gbl_tg('🏆')} "
        f"<b>Вы стали ближе к легенде</b>\n"
        f"<i>из-за вас всем стало играть просторнее</i>\n\n"
        f"{gbl_tg('🏝')} <b>Куда вы вложили</b>\n"
        f"{where}\n"
        f"уровень <b>{prev}</b> → <b>{to_level}</b> · {stars_label(to_level)}\n"
        f"это <b>{steps}</b> {_ru_steps_word(steps)}\n"
        f"{price_bit}\n"
        f"<i>нажмите на название группы — откроется чат</i>\n\n"
        f"{gbl_tg('🎯')} <b>Что получила группа</b>\n"
        f"{benefit}\n\n"
        f"{gbl_tg('💎')} <b>Что получили вы</b>\n"
        f"метка «<b>{title}</b>» в профиле"
        + (" и метки за каждый уровень пути" if steps > 1 else "")
        + "\n"
        f"в группе уже есть сообщение с вашим именем\n"
        f"<i>{social_proof_line()}</i>\n\n"
        f"{gbl_tg('🔥')} <b>Дальше</b>\n"
        f"вернитесь в группу или напишите <b>бч</b> — "
        f"там будут новые ★ и новый лимит"
    )


async def resolve_group_link_html(
    bot,
    chat_id: int,
    *,
    chat_title: Optional[str] = None,
) -> Tuple[str, Optional[str], Optional[str]]:
    """(html_link, title, url) — для кликабельного названия группы."""
    title = (chat_title or "").strip() or None
    url: Optional[str] = None
    try:
        chat = await bot.get_chat(int(chat_id))
        title = (
            title
            or getattr(chat, "title", None)
            or getattr(chat, "full_name", None)
            or str(chat_id)
        )
        uname = getattr(chat, "username", None)
        if uname:
            url = f"https://t.me/{uname}"
        else:
            invite = getattr(chat, "invite_link", None)
            if not invite:
                try:
                    invite = await bot.export_chat_invite_link(int(chat_id))
                except Exception:
                    invite = None
            url = invite
    except Exception:
        title = title or f"чат {chat_id}"
    html_link = format_group_link_html(title or str(chat_id), url=url, chat_id=chat_id)
    return html_link, title, url
