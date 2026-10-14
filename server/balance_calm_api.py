# -*- coding: utf-8 -*-
"""Покой личного баланса и картина кут. Только создатель."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from admin_auth import get_signed_in_user_id
from admin_soft_restart import is_project_creator
from balance_ledger import split_pots

_py = Path(__file__).resolve().parent / "py"
if str(_py) not in sys.path:
    sys.path.insert(0, str(_py))

from water_games.design import calm_need, calm_seconds

router = APIRouter(prefix="/admin/api/balance-calm", tags=["balance-calm"])


def _creator(user_id: int = Depends(get_signed_in_user_id)) -> int:
    if not is_project_creator(int(user_id)):
        raise HTTPException(status_code=403, detail="Балансы открыты только создателю проекта")
    return int(user_id)


class CalmBody(BaseModel):
    enabled: bool
    games: int = Field(ge=1, le=100)
    seconds: int | None = Field(default=None, ge=1, le=7 * 24 * 3600)
    hours: int | None = Field(default=None, ge=1, le=168)
    model_config = {"extra": "forbid"}


def _pool():
    from db import db
    if db.pool is None:
        raise HTTPException(status_code=503, detail="База ещё не готова")
    return db.pool


def _window_seconds(body: CalmBody) -> int:
    if body.seconds is not None:
        return calm_seconds(body.seconds)
    if body.hours is not None:
        return calm_seconds(int(body.hours) * 3600)
    return calm_seconds(24 * 3600)


async def _ensure(pool) -> None:
    await pool.execute(
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
    await pool.execute("ALTER TABLE balance_calm ADD COLUMN IF NOT EXISTS seconds INT")
    await pool.execute(
        """
        INSERT INTO balance_calm (id, enabled, games, hours, seconds)
        VALUES (1, TRUE, 5, 24, 86400)
        ON CONFLICT (id) DO NOTHING
        """
    )
    await pool.execute(
        """
        UPDATE balance_calm
           SET seconds = GREATEST(1, hours) * 3600
         WHERE id = 1
           AND (seconds IS NULL OR seconds < 1)
        """
    )


def _view(row) -> dict:
    if not row:
        seconds = calm_seconds(24 * 3600)
        return {"enabled": True, "games": 5, "hours": 24, "seconds": seconds}
    raw = row["seconds"]
    if raw is None:
        raw = int(row["hours"] or 24) * 3600
    seconds = calm_seconds(raw)
    hours = max(1, min(168, (seconds + 3599) // 3600))
    return {
        "enabled": bool(row["enabled"]),
        "games": calm_need(row["games"]),
        "hours": hours,
        "seconds": seconds,
    }


@router.get("")
async def read_calm(_user_id: int = Depends(_creator)):
    pool = _pool()
    await _ensure(pool)
    row = await pool.fetchrow(
        "SELECT enabled, games, hours, seconds FROM balance_calm WHERE id = 1"
    )
    return _view(row)


@router.post("")
async def save_calm(body: CalmBody, _user_id: int = Depends(_creator)):
    pool = _pool()
    await _ensure(pool)
    seconds = _window_seconds(body)
    hours = max(1, min(168, (seconds + 3599) // 3600))
    games = calm_need(body.games)
    row = await pool.fetchrow(
        """
        INSERT INTO balance_calm (id, enabled, games, hours, seconds)
        VALUES (1, $1, $2, $3, $4)
        ON CONFLICT (id) DO UPDATE
        SET enabled = EXCLUDED.enabled,
            games = EXCLUDED.games,
            hours = EXCLUDED.hours,
            seconds = EXCLUDED.seconds
        RETURNING enabled, games, hours, seconds
        """,
        bool(body.enabled),
        games,
        hours,
        seconds,
    )
    return _view(row)


def _person(row, names: dict) -> dict:
    user_id = int(row["user_id"])
    info = names.get(user_id) or {}
    return {
        "userId": user_id,
        "name": info.get("name") or row.get("first_name"),
        "username": info.get("username") or row.get("username"),
    }


async def _names(pool, user_ids: list[int]) -> dict:
    if not user_ids:
        return {}
    try:
        rows = await pool.fetch(
            "SELECT user_id, first_name, username FROM users WHERE user_id = ANY($1::bigint[])",
            user_ids,
        )
    except Exception:
        return {}
    return {
        int(row["user_id"]): {"name": row["first_name"], "username": row["username"]}
        for row in rows
    }


async def _pots(pool) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    users = 0
    try:
        users = await pool.fetchval("SELECT COALESCE(SUM(balance), 0) FROM users")
    except Exception:
        warnings.append("Балансы игроков сейчас не посчитались")
    living_chat = living_dex = tech_chat = tech_dex = 0
    try:
        row = await pool.fetchrow(
            """
            SELECT
              COALESCE(SUM(chatbalance) FILTER (WHERE NOT COALESCE(is_technical, FALSE)), 0) AS living_chat,
              COALESCE(SUM(dexbalance) FILTER (WHERE NOT COALESCE(is_technical, FALSE)), 0) AS living_dex,
              COALESCE(SUM(chatbalance) FILTER (WHERE COALESCE(is_technical, FALSE)), 0) AS tech_chat,
              COALESCE(SUM(dexbalance) FILTER (WHERE COALESCE(is_technical, FALSE)), 0) AS tech_dex
            FROM chat
            """
        )
        if row:
            living_chat = row["living_chat"]
            living_dex = row["living_dex"]
            tech_chat = row["tech_chat"]
            tech_dex = row["tech_dex"]
    except Exception:
        warnings.append("Балансы групп сейчас не посчитались")
    return split_pots(users, living_chat, living_dex, tech_chat, tech_dex), warnings


async def _top_players(pool) -> tuple[list[dict], list[str]]:
    try:
        rows = await pool.fetch(
            """
            SELECT user_id, COALESCE(SUM(games), 0)::int AS games
            FROM user_game_ticks
            WHERE played_at > NOW() - INTERVAL '7 days'
            GROUP BY user_id
            ORDER BY games DESC, user_id
            LIMIT 12
            """
        )
    except Exception:
        return [], ["Игры за 7 дней сейчас не посчитались"]
    names = await _names(pool, [int(row["user_id"]) for row in rows])
    people = []
    for row in rows:
        person = _person(row, names)
        person["games"] = int(row["games"] or 0)
        people.append(person)
    return people, []


async def _top_ops(pool) -> tuple[list[dict], list[str]]:
    try:
        rows = await pool.fetch(
            """
            SELECT user_id,
                   COUNT(*)::int AS ops,
                   (
                     COALESCE(SUM(COALESCE("+", 0)), 0)
                     + COALESCE(SUM(COALESCE("-", 0)), 0)
                   )::bigint AS moved
            FROM cutehistory
            WHERE id > (SELECT COALESCE(MAX(id), 0) FROM cutehistory) - 20000
            GROUP BY user_id
            ORDER BY ops DESC, moved DESC
            LIMIT 12
            """
        )
    except Exception:
        return [], ["Операции сейчас не посчитались"]
    names = await _names(pool, [int(row["user_id"]) for row in rows])
    people = []
    for row in rows:
        person = _person(row, names)
        person["ops"] = int(row["ops"] or 0)
        person["moved"] = int(row["moved"] or 0)
        people.append(person)
    return people, []


async def _lookup(pool, q: str, focus: int | None) -> tuple[dict, list[str]]:
    text = (q or "").strip().lstrip("@")
    if not text and focus is None:
        return {"query": "", "users": [], "items": []}, []
    warnings: list[str] = []
    users = []
    try:
        if text.isdigit():
            rows = await pool.fetch(
                """
                SELECT user_id, first_name, username, balance
                FROM users
                WHERE user_id = $1
                """,
                int(text),
            )
        elif text:
            rows = await pool.fetch(
                """
                SELECT user_id, first_name, username, balance
                FROM users
                WHERE username ILIKE $1 OR first_name ILIKE $1
                ORDER BY balance DESC NULLS LAST
                LIMIT 8
                """,
                f"%{text}%",
            )
        else:
            rows = await pool.fetch(
                """
                SELECT user_id, first_name, username, balance
                FROM users
                WHERE user_id = $1
                """,
                int(focus),
            )
    except Exception:
        return {"query": text, "users": [], "items": []}, ["Поиск игрока сейчас не открылся"]
    for row in rows:
        users.append({
            "userId": int(row["user_id"]),
            "name": row["first_name"],
            "username": row["username"],
            "balance": int(row["balance"] or 0),
        })
    chosen = focus if focus is not None else (users[0]["userId"] if users else None)
    items = []
    if chosen is not None:
        try:
            history = await pool.fetch(
                """
                SELECT ch.id, ch."+" AS plus, ch."-" AS minus, ch.cause, ch.balance,
                       ch.chat_id, ch.data, ch.transfer_id,
                       c.namechat AS group_name, c.usernamechat AS group_username
                FROM cutehistory ch
                LEFT JOIN chat c ON c.chat_id = ch.chat_id
                WHERE ch.user_id = $1
                ORDER BY ch.id DESC
                LIMIT 40
                """,
                int(chosen),
            )
        except Exception:
            history = []
            warnings.append("История этого игрока сейчас не открылась")
        for row in history:
            plus = int(row["plus"] or 0)
            minus = int(row["minus"] or 0)
            direction = "in" if plus else "out"
            amount = plus if direction == "in" else minus
            item = {
                "id": int(row["id"]),
                "cause": row["cause"],
                "amount": amount,
                "direction": direction,
                "balance": int(row["balance"]) if row["balance"] is not None else None,
                "when": row["data"],
                "transfer": row["transfer_id"] is not None,
            }
            if row["chat_id"] is not None:
                item["group"] = {
                    "chatId": int(row["chat_id"]),
                    "name": row["group_name"],
                    "username": row["group_username"],
                }
            items.append(item)
    return {"query": text, "focus": chosen, "users": users, "items": items}, warnings


@router.get("/ledger")
async def read_ledger(
    q: str = Query(default=""),
    focus: int | None = Query(default=None),
    _user_id: int = Depends(_creator),
):
    pool = _pool()
    warnings: list[str] = []
    try:
        await _ensure(pool)
    except Exception:
        warnings.append("Настройка покоя сейчас не открылась")
    pots, pot_notes = await _pots(pool)
    players, player_notes = await _top_players(pool)
    operations, op_notes = await _top_ops(pool)
    search, search_notes = await _lookup(pool, q, focus)
    warnings.extend(pot_notes)
    warnings.extend(player_notes)
    warnings.extend(op_notes)
    warnings.extend(search_notes)
    return {
        "pots": pots,
        "players": players,
        "operations": operations,
        "search": search,
        "warnings": warnings,
    }
