# -*- coding: utf-8 -*-
"""Вкладка создателя «Водные игры»: статистика и цены предметов."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admin_auth import get_signed_in_user_id
from admin_soft_restart import is_project_creator

router = APIRouter(prefix="/admin/api/water-games", tags=["water-games"])

KEYS = (
    "pistoletik",
    "waterpistol",
    "dryumbrella",
    "drycoat",
    "dryawning",
    "drysafe",
)
NAMES = (
    "Пистолетик",
    "Вода ( для пистолетика )",
    "Зонтик",
    "Дождевик",
    "Навес",
    "Сухой сейф",
)


def _creator(user_id: int = Depends(get_signed_in_user_id)) -> int:
    if not is_project_creator(int(user_id)):
        raise HTTPException(status_code=403, detail="Водные игры открыты только создателю проекта")
    return int(user_id)


class PriceBody(BaseModel):
    id: int = Field(ge=1)
    price: int = Field(ge=0, le=99_999_999)
    model_config = {"extra": "forbid"}


def _pool():
    from db import db
    return db.pool


async def _ensure(pool) -> None:
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS water_splashes (
            id BIGSERIAL PRIMARY KEY,
            shooter_id BIGINT NOT NULL,
            target_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            amount INT NOT NULL DEFAULT 0,
            outcome TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS water_shields (
            user_id BIGINT PRIMARY KEY,
            kind TEXT NOT NULL,
            until TIMESTAMPTZ,
            drip_until TIMESTAMPTZ,
            half_next BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    import sys
    from pathlib import Path
    py = str(Path(__file__).resolve().parent / "py")
    if py not in sys.path:
        sys.path.insert(0, py)
    from water_games.design import settle_umbrella
    await settle_umbrella(pool)


@router.get("")
async def water_board(_user_id: int = Depends(_creator)):
    pool = _pool()
    await _ensure(pool)
    items = await pool.fetch(
        """
        SELECT id, name, name1, emoji, price, remains
        FROM dex
        WHERE name1 = ANY($1::text[]) OR name = ANY($2::text[])
        ORDER BY id
        """,
        list(KEYS),
        list(NAMES),
    )
    totals = await pool.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE outcome = 'hit')::int AS hits,
            COUNT(*) FILTER (WHERE outcome = 'broke')::int AS broke,
            COUNT(*) FILTER (WHERE outcome = 'shield')::int AS bounced,
            COALESCE(SUM(amount) FILTER (WHERE outcome = 'hit'), 0)::bigint AS moved,
            COUNT(*) FILTER (WHERE outcome = 'hit' AND created_at > NOW() - INTERVAL '1 day')::int AS hits_today,
            COALESCE(SUM(amount) FILTER (WHERE outcome = 'hit' AND created_at > NOW() - INTERVAL '1 day'), 0)::bigint AS moved_today
        FROM water_splashes
        """
    )
    pours = await pool.fetch(
        """
        SELECT shooter_id AS user_id,
               COUNT(*)::int AS pours,
               COUNT(*) FILTER (WHERE outcome = 'hit')::int AS hits,
               COALESCE(SUM(amount) FILTER (WHERE outcome = 'hit'), 0)::bigint AS taken
        FROM water_splashes
        GROUP BY shooter_id
        ORDER BY pours DESC, hits DESC, taken DESC
        LIMIT 40
        """
    )
    soaked = await pool.fetch(
        """
        SELECT target_id AS user_id,
               COUNT(*)::int AS pours,
               COUNT(*) FILTER (WHERE outcome = 'hit')::int AS hits,
               COALESCE(SUM(amount) FILTER (WHERE outcome = 'hit'), 0)::bigint AS lost
        FROM water_splashes
        GROUP BY target_id
        ORDER BY pours DESC, hits DESC, lost DESC
        LIMIT 40
        """
    )
    pairs = await pool.fetch(
        """
        SELECT shooter_id, target_id,
               COUNT(*)::int AS times,
               COUNT(*) FILTER (WHERE outcome = 'hit')::int AS hits,
               COALESCE(SUM(amount) FILTER (WHERE outcome = 'hit'), 0)::bigint AS taken
        FROM water_splashes
        GROUP BY shooter_id, target_id
        ORDER BY times DESC, hits DESC, taken DESC
        LIMIT 40
        """
    )
    recent = await pool.fetch(
        """
        SELECT shooter_id, target_id, amount, outcome, created_at
        FROM water_splashes
        ORDER BY created_at DESC
        LIMIT 12
        """
    )
    shields = await pool.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE until IS NULL OR until > NOW())::int AS live,
            COUNT(*) FILTER (WHERE kind = 'drysafe' AND until IS NULL)::int AS forever
        FROM water_shields
        """
    )
    ids = set()
    for row in list(pours) + list(soaked) + list(recent) + list(pairs):
        if "user_id" in row.keys():
            ids.add(int(row["user_id"]))
        if "shooter_id" in row.keys():
            ids.add(int(row["shooter_id"]))
            ids.add(int(row["target_id"]))
    names = {}
    if ids:
        people = await pool.fetch(
            "SELECT user_id, first_name FROM users WHERE user_id = ANY($1::bigint[])",
            list(ids),
        )
        for person in people:
            label = str(person["first_name"] or "").replace("@", "").strip()
            names[int(person["user_id"])] = label

    def person(user_id: int) -> dict:
        return {"userId": int(user_id), "name": names.get(int(user_id)) or "Игрок"}

    return {
        "totals": {
            "hits": int(totals["hits"] or 0) if totals else 0,
            "broke": int(totals["broke"] or 0) if totals else 0,
            "bounced": int(totals["bounced"] or 0) if totals else 0,
            "moved": int(totals["moved"] or 0) if totals else 0,
            "hitsToday": int(totals["hits_today"] or 0) if totals else 0,
            "movedToday": int(totals["moved_today"] or 0) if totals else 0,
            "shields": int(shields["live"] or 0) if shields else 0,
            "forever": int(shields["forever"] or 0) if shields else 0,
        },
        "pours": [
            {
                **person(row["user_id"]),
                "pours": int(row["pours"]),
                "hits": int(row["hits"]),
                "taken": int(row["taken"]),
            }
            for row in pours
        ],
        "soaked": [
            {
                **person(row["user_id"]),
                "pours": int(row["pours"]),
                "hits": int(row["hits"]),
                "lost": int(row["lost"]),
            }
            for row in soaked
        ],
        "pairs": [
            {
                "shooter": person(row["shooter_id"]),
                "target": person(row["target_id"]),
                "times": int(row["times"]),
                "hits": int(row["hits"]),
                "taken": int(row["taken"]),
            }
            for row in pairs
        ],
        "recent": [
            {
                "shooter": person(row["shooter_id"]),
                "target": person(row["target_id"]),
                "amount": int(row["amount"] or 0),
                "outcome": row["outcome"],
                "at": row["created_at"].isoformat() if row["created_at"] else "",
            }
            for row in recent
        ],
        "items": [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "name1": row["name1"] or "",
                "emoji": row["emoji"] or "💧",
                "price": int(row["price"] or 0),
                "remains": int(row["remains"] or 0),
            }
            for row in items
        ],
    }


@router.post("/price")
async def water_price(body: PriceBody, _user_id: int = Depends(_creator)):
    pool = _pool()
    row = await pool.fetchrow(
        """
        UPDATE dex SET price = $2
        WHERE id = $1
          AND (name1 = ANY($3::text[]) OR name = ANY($4::text[]))
        RETURNING id, name, price
        """,
        int(body.id),
        int(body.price),
        list(KEYS),
        list(NAMES),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Предмета ещё нет в dex")
    return {"ok": True, "id": str(row["id"]), "name": row["name"], "price": int(row["price"])}
