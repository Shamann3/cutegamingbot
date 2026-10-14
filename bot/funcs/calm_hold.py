# -*- coding: utf-8 -*-
"""Покой баланса: сколько игр за срок уже есть, и включена ли защита от обливания."""
from __future__ import annotations

import time

from bot.funcs.water_games_design import calm_hours, calm_need, calm_progress, calm_seconds

_CACHE: dict = {"at": 0.0, "rules": None}
_CACHE_SEC = 20

_DEFAULT = {"enabled": True, "games": 5, "hours": 24, "seconds": 24 * 3600}


async def ensure_rules(db) -> None:
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS balance_calm (
            id SMALLINT PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            games INT NOT NULL DEFAULT 5,
            hours INT NOT NULL DEFAULT 24,
            seconds INT NOT NULL DEFAULT 86400
        )
        """
    )
    await db.pool.execute(
        "ALTER TABLE balance_calm ADD COLUMN IF NOT EXISTS seconds INT"
    )
    await db.pool.execute(
        """
        INSERT INTO balance_calm (id, enabled, games, hours, seconds)
        VALUES (1, TRUE, 5, 24, 86400)
        ON CONFLICT (id) DO NOTHING
        """
    )
    await db.pool.execute(
        """
        UPDATE balance_calm
           SET seconds = GREATEST(1, hours) * 3600
         WHERE id = 1
           AND (seconds IS NULL OR seconds < 1)
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
            "SELECT enabled, games, hours, seconds FROM balance_calm WHERE id = 1"
        )
    except Exception:
        return dict(_DEFAULT)
    rules = dict(_DEFAULT)
    if row:
        raw_seconds = row["seconds"]
        if raw_seconds is None:
            raw_seconds = int(row["hours"] or 24) * 3600
        seconds = calm_seconds(raw_seconds)
        rules = {
            "enabled": bool(row["enabled"]),
            "games": calm_need(row["games"]),
            "hours": calm_hours(max(1, (seconds + 3599) // 3600)),
            "seconds": seconds,
        }
    _CACHE["at"] = now
    _CACHE["rules"] = dict(rules)
    return rules


def drop_rules_cache() -> None:
    _CACHE["at"] = 0.0
    _CACHE["rules"] = None


async def games_in_window(db, user_id: int, seconds: int) -> tuple[int, int]:
    """Сколько игр ещё в сроке, и сколько секунд осталось до его конца.

    Нет игр — впереди весь срок. Есть игры — срок кончается, когда самая
    ранняя из них выходит из окна. Сбой чтения не включает покой.
    """
    span = calm_seconds(seconds)
    try:
        row = await db.pool.fetchrow(
            """
            SELECT COALESCE(SUM(games), 0) AS played,
                   EXTRACT(EPOCH FROM (MIN(played_at) + ($2::int * INTERVAL '1 second') - NOW())) AS remain
            FROM user_game_ticks
            WHERE user_id = $1
              AND played_at > NOW() - ($2::int * INTERVAL '1 second')
            """,
            int(user_id),
            span,
        )
    except Exception:
        return 0, span
    played = int((row["played"] if row else 0) or 0)
    if played <= 0:
        return 0, span
    remain = row["remain"] if row else None
    if remain is None:
        return played, span
    left = int(remain)
    if left < 0:
        left = 0
    if left > span:
        left = span
    return played, left


async def calm_state(db, user_id: int) -> dict:
    rules = await load_rules(db)
    played = 0
    left_sec = int(rules["seconds"])
    if rules["enabled"]:
        played, left_sec = await games_in_window(db, user_id, rules["seconds"])
    state = calm_progress(played, rules["games"])
    state["hours"] = rules["hours"]
    state["seconds"] = int(rules["seconds"])
    state["left_sec"] = int(left_sec)
    state["enabled"] = bool(rules["enabled"])
    if not rules["enabled"]:
        state["calm"] = False
    return state
