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
    "raise_button_text": "Поднять уровень группы",
    "system_title": "Баланс группы",
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
    """(next_level, price_stars) или None если уже ★5.

    Цена = база из настроек × умный множитель силы группы (снимок).
    Перед оплатой/экраном вызывайте ensure_society_snapshot.
    """
    cfg = cfg or get_settings()
    cur = get_chat_level(chat_id)
    if cur >= 5:
        return None
    nxt = cur + 1
    base = price_to_reach(nxt, cfg)
    price = _society_effective_level_price(
        nxt, chat_id=int(chat_id), base_price=base, cfg=cfg,
    )
    return nxt, int(price)


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
        f"<b>Забота о балансе групп</b>\n{body}"
        f"</blockquote>"
    )


def log_purchase(event: Dict[str, Any]) -> None:
    events = list(_purchase_log.get(_LOG_KEY) or [])
    events.append({**event, "ts": time.time()})
    _purchase_log[_LOG_KEY] = events[-300:]


def list_recent_purchases(limit: int = 50) -> List[Dict[str, Any]]:
    events = list(_purchase_log.get(_LOG_KEY) or [])
    return list(reversed(events[-max(1, int(limit)):]))


def apply_level_purchase(
    *,
    chat_id: int,
    user_id: int,
    to_level: int,
    price_stars: int,
) -> Dict[str, Any]:
    """Применяет покупку уровня после успешной оплаты."""
    to_level = max(1, min(5, int(to_level)))
    cur = get_chat_level(chat_id)
    if to_level != cur + 1:
        # Идемпотентность: если уже на этом или выше — ок, бейдж всё равно можно обновить
        if to_level <= cur:
            remember_sponsor_badge(user_id, level=to_level, chat_id=chat_id, price_stars=price_stars)
            return {"ok": True, "level": cur, "already": True}
        return {"ok": False, "error": "level_mismatch", "current": cur, "wanted": to_level}

    set_chat_level(chat_id, to_level, sponsor_id=user_id)
    remember_sponsor_badge(user_id, level=to_level, chat_id=chat_id, price_stars=price_stars)
    log_purchase({
        "chat_id": int(chat_id),
        "user_id": int(user_id),
        "level": int(to_level),
        "price_stars": int(price_stars),
    })
    return {"ok": True, "level": to_level, "already": False}


def _next_level_teaser(chat_id: int, cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Тизер следующего шага — выгода и статус, одна цена без «базы»."""
    cfg = cfg or get_settings()
    if not cfg.get("enabled", True):
        return None
    nxt = next_level_price(chat_id, cfg)
    if not nxt:
        return None
    to_level, price = nxt
    caps = cfg.get("stake_caps") or {}
    if to_level >= 5:
        benefit = "ставки без лимита"
    else:
        benefit = f"ставки до {caps.get(str(to_level), '?')} кут"
    return (
        f"уровень {to_level} · {benefit} · вклад <b>{price} звёзд</b>"
    )


def raise_cta_label(chat_id: int, cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Кнопка апгрейда — продаём результат (ставки / статус), не «наценку»."""
    cfg = cfg or get_settings()
    if not cfg.get("enabled", True):
        return None
    level = get_chat_level(chat_id)
    if level >= 5:
        return None
    nxt = next_level_price(chat_id, cfg)
    if not nxt:
        return str(cfg.get("raise_button_text") or "Поднять уровень группы")
    to_level, _price = nxt
    caps = cfg.get("stake_caps") or {}
    if to_level >= 5:
        return "Открыть вершину · без лимита ставок"
    cap = caps.get(str(to_level))
    if cap is not None:
        return f"Поднять группу до уровня {to_level} · ставки до {cap}"
    return str(cfg.get("raise_button_text") or "Поднять уровень группы")


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


def _society_pulse_lines(report: Dict[str, Any], *, cfg: Optional[Dict[str, Any]] = None) -> str:
    """Короткий разбор силы группы — понятно новичку."""
    cfg = cfg or get_settings()
    act = report.get("activity") if isinstance(report.get("activity"), dict) else {}
    don = report.get("donors") if isinstance(report.get("donors"), dict) else {}
    members = _as_int(act.get("members") or report.get("members"), 0)
    writers = _as_int(act.get("writers"), 0)
    qualified = _as_int(act.get("qualified"), 0)
    donators = _as_int(don.get("donators") or report.get("donators"), 0)
    a = _as_float(act.get("score"), 0.0)
    d = _as_float(don.get("score"), 0.0)
    pct = _as_float(report.get("pct"), 0.0)
    max_pct = _as_int(cfg.get("atmosphere_max_bonus_pct"), 40)
    members_fmt = f"{members:,}".replace(",", ".") if members > 0 else "0"

    if a >= 0.75:
        pulse = "группа очень живая"
    elif a >= 0.4:
        pulse = "группа в хорошем ритме"
    elif a >= 0.15:
        pulse = "группа постепенно оживает"
    else:
        pulse = "группа пока тихая"

    if d >= 0.7:
        donor_line = "сильная поддержка донатерами"
    elif d >= 0.35:
        donor_line = "есть заметная поддержка донатерами"
    elif donators >= 1:
        donor_line = "донаты уже есть, ядро ещё растёт"
    else:
        donor_line = "рост идёт через общение в чате"

    lines = [
        f"<b>Пульс группы</b>",
        f"{pulse}.",
    ]
    if members > 0:
        if writers > 0:
            lines.append(
                f"Из ~<b>{members_fmt}</b> {_ru_users_word(members)} в группе "
                f"за месяц писали <b>{writers}</b>."
            )
        else:
            lines.append(
                f"Из ~<b>{members_fmt}</b> {_ru_users_word(members)} в группе "
                f"за месяц почти никто не писал."
            )
    elif writers > 0:
        lines.append(f"За месяц писали <b>{writers}</b>.")
    if qualified > 0 and qualified != writers:
        lines.append(f"В устойчивом ритме чата: <b>{qualified}</b>.")
    if donators > 0:
        lines.append(
            f"{donor_line} · в расчёте <b>{donators}</b> {_ru_donors_word(donators)} "
            f"(кто писал и поддерживал проект)."
        )
    else:
        lines.append(f"{donor_line}.")
    lines.append(
        f"Бонус к потолку ставки сейчас: <b>+{pct:g}%</b> "
        f"(максимум в проекте +{max_pct}%)."
    )
    return "\n".join(lines)


def build_details_html(
    *,
    chat_balance: float,
    chat_id: int,
    atmosphere_pct: float = 0.0,
    atmosphere_report: Optional[Dict[str, Any]] = None,
    cfg: Optional[Dict[str, Any]] = None,
) -> str:
    """«Подробнее»: все детали коротко и ясно для новичка."""
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

    def _cap(n: int) -> str:
        if n >= 5:
            return "∞"
        v = caps.get(str(n))
        return str(v) if v is not None else "—"

    if cap is None:
        lim_block = (
            f"Сейчас можно ставить <b>без лимита уровня</b>.\n"
            f"Группа на вершине — потолок уровня вас не ограничивает."
        )
    else:
        lim_block = f"Сейчас в обычных играх группы ставки <b>до {cap} кут</b>."
        if atmo_on and atmo_now > 0.05 and base_cap is not None:
            lim_block += (
                f"\nКак получилось: база уровня {level} — <b>{base_cap}</b> кут, "
                f"живая группа дала <b>+{atmo_now:g}%</b> → итого <b>{cap}</b>."
            )
        elif base_cap is not None:
            lim_block += f"\nЭто базовый потолок уровня <b>{level}</b>."

    if level >= 5:
        finale = (
            f"<tg-emoji emoji-id='{ICON_RAISE_LEVEL}'>⭐️</tg-emoji> "
            f"<b>Вершина открыта</b>\n"
            f"{stars_label(5)} · выше поднимать некуда."
        )
    elif teaser:
        finale = (
            f"<tg-emoji emoji-id='{ICON_RAISE_LEVEL}'>⭐️</tg-emoji> "
            f"<b>Как поднять потолок</b>\n"
            f"{teaser}\n"
            f"<i>Оплата открывает всем в чате больший лимит — "
            f"и метку вам в профиле.</i>"
        )
    else:
        finale = (
            f"<tg-emoji emoji-id='{ICON_RAISE_LEVEL}'>⭐️</tg-emoji> "
            f"<b>Следующий уровень скоро</b>\n"
            f"Загляните чуть позже."
        )

    if atmo_on:
        pulse = _society_pulse_lines(report if report else {"pct": atmo_now}, cfg=cfg)
        bonus_how = (
            f"Чем активнее чат и заметнее поддержка донатерами "
            f"(считаем тех, кто <b>пишет</b> в группе), "
            f"тем выше может быть потолок — до <b>+{atmo_max}%</b> к базе уровня.\n"
            f"Пример: база 100 и +20% → ставки до 120 кут."
        )
    else:
        pulse = "<b>Пульс группы</b>\nБонус от живой группы сейчас выключен."
        bonus_how = "Бонус к потолку от активности чата отключён администратором."

    return (
        f"<tg-emoji emoji-id='5472146462362048818'>💡</tg-emoji> "
        f"<b>Баланс группы — коротко</b>\n\n"
        f"<tg-emoji emoji-id='{ICON_BALANCE_KUT}'>⭐️</tg-emoji> "
        f"На балансе группы: <b>{bal_fmt}</b> кут\n"
        f"<i>Общая касса чата: выигрыши платятся отсюда, проигрыши возвращаются сюда.</i>\n\n"
        f"<tg-emoji emoji-id='5267229058659264159'>🟢</tg-emoji> "
        f"Уровень группы: <b>{level}</b> · {stars_label(level)}\n"
        f"{lim_block}\n"
        f"<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji> "
        f"Комфортная ставка сейчас ≈ <b>{rec}</b> кут "
        f"<i>(ориентир, не обязанность)</i>\n\n"
        f"<blockquote>"
        f"{pulse}\n\n"
        f"<b>Зачем это новичку</b>\n"
        f"• <b>Баланс</b> — сколько кут у чата на игры\n"
        f"• <b>Уровень</b> — какой базовый потолок ставки открыт всем\n"
        f"• <b>Живая группа</b> — активность может чуть поднять этот потолок\n"
        f"• <b>Поднять уровень</b> — вклад звёздами → выше лимит для всех + метка вам\n\n"
        f"<b>Что бонус не меняет</b>\n"
        f"• сумму на балансе группы\n"
        f"• ваши личные куты\n"
        f"• бесплатные задания\n\n"
        f"<b>Как считается бонус</b>\n"
        f"{bonus_how}"
        f"</blockquote>\n\n"
        f"{finale}\n\n"
        f"<b>Базовые потолки по уровням</b>\n"
        f"<code>"
        f"ур.0 {p0} → ур.1 {_cap(1)} → ур.2 {_cap(2)} → ур.3 {_cap(3)}\n"
        f"ур.4 {_cap(4)} → ур.5 {_cap(5)}"
        f"</code>"
    )


def build_details_keyboard(*, chat_id: int, cfg: Optional[Dict[str, Any]] = None):
    """Клавиатура экрана условий: путь к повышению + назад."""
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
    """Как раньше: сумма на кнопке → апгрейд → Подробнее."""
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
        text="Подробнее",
        callback_data=f"group_balance_details:{bal}",
        style="default",
        icon_custom_emoji_id=ICON_DETAILS,
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_raise_keyboard(*, chat_id: int, cfg: Optional[Dict[str, Any]] = None):
    from aiogram.types import InlineKeyboardMarkup

    cfg = cfg or get_settings()
    nxt = next_level_price(chat_id, cfg)
    rows = []
    if nxt:
        to_level, price = nxt
        caps = cfg.get("stake_caps") or {}
        if to_level >= 5:
            pay_txt = f"Открыть вершину · {price} звёзд"
        else:
            pay_txt = f"Открыть ставки до {caps.get(str(to_level), '?')} · {price} звёзд"
        rows.append([_btn(
            text=pay_txt,
            callback_data=f"gbl_pay:{chat_id}:{to_level}:{price}",
            style="success",
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
) -> str:
    """Экран апгрейда: продаём результат и статус, одна цена без сравнений."""
    cfg = cfg or get_settings()
    cur = get_chat_level(chat_id)
    nxt = next_level_price(chat_id, cfg)
    if not nxt:
        return (
            f"<tg-emoji emoji-id='{ICON_RAISE_LEVEL}'>⭐️</tg-emoji> "
            f"<b>Вершина уже ваша</b>\n\n"
            f"{stars_label(5)} · ставки без лимита уровня\n"
            f"Группа на пике статуса. Спасибо за вклад."
        )
    to_level, price = nxt
    caps = cfg.get("stake_caps") or {}
    if to_level >= 5:
        new_lim = "ставки <b>без лимита уровня</b>"
        outcome = "группа выходит на вершину статуса в проекте"
    else:
        new_lim = f"ставки <b>до {caps.get(str(to_level), '?')} кут</b>"
        outcome = "больше пространства для игры всей группе"
    title = (badge_title or "").strip() or badge_title_for_level(to_level, cfg)
    return (
        f"<tg-emoji emoji-id='{ICON_RAISE_LEVEL}'>⭐️</tg-emoji> "
        f"<b>Поднимите уровень группы</b>\n"
        f"{stars_label(cur)} → {stars_label(to_level)}\n\n"
        f"Сейчас: уровень <b>{cur}</b>\n"
        f"Станет: уровень <b>{to_level}</b> · {new_lim}\n"
        f"<i>Вы открываете {outcome} — и свою метку в мире проекта.</i>\n\n"
        f"<blockquote>"
        f"<b>Что вы даёте группе</b>\n"
        f"• новый потолок ставок для всех\n"
        f"• более высокий статус чата\n"
        f"• анонс вашего вклада"
        f"</blockquote>\n\n"
        f"<tg-emoji emoji-id='5318892863780579996'>🎩</tg-emoji> "
        f"Вам — метка «<b>{title}</b>» в профиле\n"
        f"<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji> "
        f"Вклад шага: <b>{price} звёзд</b>\n"
        f"<i>Куты на личный баланс не начисляются — вы усиливаете общую игру.</i>"
    )


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
        raise_txt = str(cfg.get("raise_button_text") or "Поднять уровень группы")
        text = (
            f"<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji> "
            f"<b>Сейчас ставки до {cap} кут</b>\n"
            f"Уровень группы: {stars_label(level)}.\n"
            f"Чтобы открыть крупнее для всех — "
            f"напишите «бч» → «{raise_txt}»."
        )
        try:
            await message.reply(text, parse_mode="HTML")
        except Exception:
            await message.reply(
                f"⭐ Сейчас ставки до {cap} кут. "
                f"Напишите «бч» → «{raise_txt}».",
            )
        return True
    except Exception as e:
        print(f"[GBL] stake reject failed: {e!r}")
        return False


def build_gift_announcement_html(
    *,
    sponsor_name_html: str,
    to_level: int,
    price_stars: int,
    chat_id: int,
    atmosphere_pct: float = 0.0,
) -> str:
    cfg = get_settings()
    cap = effective_stake_cap(chat_id, atmosphere_pct=atmosphere_pct, cfg=cfg)
    if to_level >= 5:
        lim = "без лимита уровня"
    elif cap is None:
        lim = "без лимита уровня"
    else:
        lim = f"до {cap} кут"
    title = badge_title_for_level(to_level, cfg)
    return (
        f"<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji> "
        f"<b>Новый статус группы</b>\n\n"
        f"{sponsor_name_html} поднимает чат до "
        f"<b>{stars_label(to_level)}</b>\n"
        f"Теперь ставки: <b>{lim}</b>\n\n"
        f"<blockquote>"
        f"<b>{title}</b>\n"
        f"Чем выше уровень группы — тем выше вес тех, кто её усиливает."
        f"</blockquote>"
    )
