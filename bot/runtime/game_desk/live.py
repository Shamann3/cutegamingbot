# -*- coding: utf-8 -*-
"""Живые настройки игр. Кэш на пару секунд, чтобы партия видела правку из панели."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from .catalog import default_game_state, default_payload, resolve_key
from .store import load_payload, normalize_payload

_TTL = 2.0
_cache: Dict[str, Any] = default_payload()
_cache_at = 0.0
_loading = False


def snapshot() -> Dict[str, Any]:
    return _cache if _cache else default_payload()


def ready() -> bool:
    return bool(_cache.get("games"))


def game_state(key: str) -> Dict[str, Any]:
    real = resolve_key(key)
    games = snapshot().get("games") or {}
    found = games.get(real)
    if isinstance(found, dict):
        return found
    return default_game_state(real)


def is_on(key: str) -> bool:
    return bool(game_state(key).get("enabled", True))


def bets(key: str) -> Tuple[int, int]:
    state = game_state(key)
    return int(state.get("minBet") or 0), int(state.get("maxBet") or 0)


def commission_on() -> bool:
    return bool((snapshot().get("commission") or {}).get("enabled", True))


def commission_min_pot() -> int:
    return int((snapshot().get("commission") or {}).get("minPot") or 0)


def commission_rate(level: int) -> float:
    rates = (snapshot().get("commission") or {}).get("rateByLevel") or {}
    return float(rates.get(str(int(level)), rates.get(int(level), 0.0)) or 0.0)


def commission_mult(key: str) -> float:
    return float(game_state(key).get("commissionMult") or 0.0)


def param(key: str, name: str, default: Any) -> Any:
    params = game_state(key).get("params") or {}
    if name in params:
        return params[name]
    return default


def param_decimal(key: str, name: str, default: Any) -> Decimal:
    return Decimal(str(param(key, name, default)))


def param_int(key: str, name: str, default: Any) -> int:
    try:
        return int(round(float(param(key, name, default))))
    except (TypeError, ValueError):
        try:
            return int(default)
        except (TypeError, ValueError):
            return 0


def param_float(key: str, name: str, default: Any) -> float:
    try:
        return float(param(key, name, default))
    except (TypeError, ValueError):
        try:
            return float(default)
        except (TypeError, ValueError):
            return 0.0


def max_players(key: str, default: int) -> int:
    return max(2, param_int(key, "maxPlayers", default))


def session_seconds(key: str, default_minutes: int = 20) -> float:
    minutes = max(1, param_int(key, "sessionMinutes", default_minutes))
    return float(minutes) * 60.0


async def refresh(db=None) -> Dict[str, Any]:
    global _cache, _cache_at, _loading
    now = time.monotonic()
    if _cache_at and now - _cache_at < _TTL:
        return _cache
    if db is None:
        try:
            from main import db as main_db
            db = main_db
        except Exception:
            return _cache
    if _loading:
        return _cache
    _loading = True
    try:
        _cache = normalize_payload(await load_payload(db))
        _cache_at = time.monotonic()
    except Exception:
        if not _cache:
            _cache = default_payload()
    finally:
        _loading = False
    return _cache


def closed_html(key: str) -> str:
    from .catalog import game_meta
    meta = game_meta(key)
    title = (meta or {}).get("title") or "Эта игра"
    return (
        "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
        f"<b>{title} сейчас выключена.</b>"
    )


def min_html(amount: int) -> str:
    return (
        "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
        f"<b>Минимальная ставка {int(amount)} кут.</b>"
    )


def max_html(amount: int) -> str:
    return (
        "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
        f"<b>Максимальная ставка {int(amount)} кут.</b>"
    )


async def reject_desk(message, key: str, bet: Optional[int] = None) -> bool:
    """True — игра уже ответила и её нужно прервать."""
    try:
        await refresh()
    except Exception:
        pass
    if not is_on(key):
        await _reply(message, closed_html(key))
        return True
    if bet is None:
        return False
    try:
        amount = int(bet)
    except (TypeError, ValueError):
        return False
    mn, mx = bets(key)
    if amount < mn:
        await _reply(message, min_html(mn))
        return True
    if mx > 0 and amount > mx:
        await _reply(message, max_html(mx))
        return True
    return False


async def _reply(message, text: str) -> None:
    try:
        await message.reply(text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        try:
            await message.reply(text)
        except Exception:
            pass
