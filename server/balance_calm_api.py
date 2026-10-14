# -*- coding: utf-8 -*-
"""Настройки покоя личного баланса. Только создатель."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admin_auth import get_signed_in_user_id
from admin_soft_restart import is_project_creator

router = APIRouter(prefix="/admin/api/balance-calm", tags=["balance-calm"])


def _creator(user_id: int = Depends(get_signed_in_user_id)) -> int:
    if not is_project_creator(int(user_id)):
        raise HTTPException(status_code=403, detail="Балансы открыты только создателю проекта")
    return int(user_id)


class CalmBody(BaseModel):
    enabled: bool
    games: int = Field(ge=1, le=100)
    hours: int = Field(ge=1, le=168)
    model_config = {"extra": "forbid"}


def _pool():
    from db import db
    if db.pool is None:
        raise HTTPException(status_code=503, detail="База ещё не готова")
    return db.pool


async def _ensure(pool) -> None:
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS balance_calm (
            id SMALLINT PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            games INT NOT NULL DEFAULT 5,
            hours INT NOT NULL DEFAULT 24
        )
        """
    )
    await pool.execute(
        """
        INSERT INTO balance_calm (id, enabled, games, hours)
        VALUES (1, TRUE, 5, 24)
        ON CONFLICT (id) DO NOTHING
        """
    )


def _view(row) -> dict:
    if not row:
        return {"enabled": True, "games": 5, "hours": 24}
    return {
        "enabled": bool(row["enabled"]),
        "games": int(row["games"]),
        "hours": int(row["hours"]),
    }


@router.get("")
async def read_calm(_user_id: int = Depends(_creator)):
    pool = _pool()
    await _ensure(pool)
    row = await pool.fetchrow("SELECT enabled, games, hours FROM balance_calm WHERE id = 1")
    return _view(row)


@router.post("")
async def save_calm(body: CalmBody, _user_id: int = Depends(_creator)):
    pool = _pool()
    await _ensure(pool)
    row = await pool.fetchrow(
        """
        INSERT INTO balance_calm (id, enabled, games, hours)
        VALUES (1, $1, $2, $3)
        ON CONFLICT (id) DO UPDATE
        SET enabled = EXCLUDED.enabled,
            games = EXCLUDED.games,
            hours = EXCLUDED.hours
        RETURNING enabled, games, hours
        """,
        bool(body.enabled),
        int(body.games),
        int(body.hours),
    )
    return _view(row)
