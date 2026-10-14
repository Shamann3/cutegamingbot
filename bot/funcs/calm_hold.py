# -*- coding: utf-8 -*-
"""Покой баланса: сколько игр за срок уже есть, и включена ли защита от обливания."""
from __future__ import annotations

import time

from bot.funcs.water_games_design import calm_hours, calm_need, calm_progress

_CACHE: dict = {"at": 0.0, "rules": None}
_CACHE_SEC = 20

_DEFAULT = {"enabled": True, "games": 5, "hours": 24}


async def ensure_rules(db) -> None:
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS balance_calm (
            id SMALLINT PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            games INT NOT NULL DEFAULT 5,
            hours INT NOT NULL DEFAULT 24
        )
        """
    )
    await db.pool.execute(
        """
        INSERT INTO balance_calm (id, enabled, games, hours)
        VALUES (1, TRUE, 5, 24)
        ON CONFLICT (id) DO NOTHING
        """
    )


async def load_rules(db) -> dict:
    now = time.monotonic()
    cached = _CACHE.get("rules")
    if cached and now - float(_CACHE.get("at") or 0) < _CACHE_SEC:
        return dict(cached)
    try:
        await ensure_rules(db)
        row = await db.pool.fetchrow(
            "SELECT enabled, games, hours FROM balance_calm WHERE id = 1"
        )
    except Exception:
        return dict(_DEFAULT)
    rules = dict(_DEFAULT)
    if row:
        rules = {
            "enabled": bool(row["enabled"]),
            "games": calm_need(row["games"]),
            "hours": calm_hours(row["hours"]),
        }
    _CACHE["at"] = now
    _CACHE["rules"] = dict(rules)
    return rules


def drop_rules_cache() -> None:
    _CACHE["at"] = 0.0
    _CACHE["rules"] = None


async def games_in_window(db, user_id: int, hours: int) -> int:
    span = calm_hours(hours)
    try:
        value = await db.pool.fetchval(
            """
            SELECT COALESCE(SUM(games), 0)
            FROM user_game_ticks
            WHERE user_id = $1
              AND played_at > NOW() - make_interval(hours => $2)
            """,
            int(user_id),
            span,
        )
    except Exception:
        return 0
    return int(value or 0)


async def calm_state(db, user_id: int) -> dict:
    rules = await load_rules(db)
    played = 0
    if rules["enabled"]:
        played = await games_in_window(db, user_id, rules["hours"])
    state = calm_progress(played, rules["games"])
    state["hours"] = rules["hours"]
    state["enabled"] = bool(rules["enabled"])
    if not rules["enabled"]:
        state["calm"] = False
    return state
