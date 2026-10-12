# -*- coding: utf-8 -*-
"""Вкладка создателя «Кейсы»: шансы и потолок. Комиссии нет."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admin_auth import get_signed_in_user_id
from admin_soft_restart import is_project_creator

_py = str(Path(__file__).resolve().parent / "py")
if _py not in sys.path:
    sys.path.insert(0, _py)

from cases.design import average, cases, check_rules, public_case, shop_items  # noqa: E402

router = APIRouter(prefix="/admin/api/cases", tags=["cases"])


def _creator(user_id: int = Depends(get_signed_in_user_id)) -> int:
    if not is_project_creator(int(user_id)):
        raise HTTPException(status_code=403, detail="Кейсы открыты только создателю проекта")
    return int(user_id)


class BandBody(BaseModel):
    chance: int = Field(ge=1, le=100)
    amount: int = Field(ge=1, le=1_000_000)
    model_config = {"extra": "forbid"}


class ShelfBody(BaseModel):
    id: int = Field(ge=1)
    model_config = {"extra": "forbid"}


class PriceBody(ShelfBody):
    price: int = Field(ge=0, le=99_999_999)


class StockBody(ShelfBody):
    remains: int = Field(ge=0, le=99_999_999)


class RulesBody(BaseModel):
    id: str
    max: int = Field(ge=1, le=1_000_000)
    bands: list[BandBody] = Field(min_length=2, max_length=6)
    model_config = {"extra": "forbid"}


def _pool():
    from db import db
    return db.pool


async def _ensure(pool) -> None:
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS case_rules (
            case_id TEXT PRIMARY KEY,
            max_cute INT NOT NULL,
            bands JSONB NOT NULL
        )
        """
    )


def _stored(row) -> dict | None:
    if not row:
        return None
    bands = row["bands"]
    if isinstance(bands, str):
        bands = json.loads(bands)
    return {"max": int(row["max_cute"]), "bands": bands}


def _shelf_names() -> tuple[list[str], list[str]]:
    rows = shop_items()
    return [row["name1"] for row in rows], [row["name"] for row in rows]


async def _shelf(pool) -> list[dict]:
    name1s, names = _shelf_names()
    found = await pool.fetch(
        """
        SELECT id, name, name1, emoji, price, remains
        FROM dex
        WHERE name1 = ANY($1::text[]) OR name = ANY($2::text[])
        ORDER BY id
        """,
        name1s,
        names,
    )
    by_name1 = {}
    by_name = {}
    for row in found:
        if row["name1"]:
            by_name1[str(row["name1"])] = row
        by_name[str(row["name"] or "").lower()] = row
    out = []
    for item in shop_items():
        row = by_name1.get(item["name1"]) or by_name.get(item["name"].lower())
        out.append({
            "id": str(row["id"]) if row else "",
            "name": item["name"],
            "name1": item["name1"],
            "emoji": (row["emoji"] if row and row["emoji"] else item["emoji"]),
            "price": int(row["price"] or 0) if row else 0,
            "remains": int(row["remains"] or 0) if row else 0,
            "missing": row is None,
        })
    return out


async def _touch_shelf(pool, item_id: int, column: str, value: int):
    if column not in {"price", "remains"}:
        raise HTTPException(status_code=400, detail="Это поле нельзя менять")
    name1s, names = _shelf_names()
    row = await pool.fetchrow(
        f"""
        UPDATE dex SET {column} = $2
        WHERE id = $1
          AND (name1 = ANY($3::text[]) OR name = ANY($4::text[]))
        RETURNING id, name, price, remains
        """,
        int(item_id),
        int(value),
        name1s,
        names,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Предмета ещё нет в магазине")
    return row


def _card(item: dict) -> dict:
    return {
        "id": item["id"],
        "name": item["name"],
        "emoji": item["emoji"],
        "max": item["max"],
        "bands": item["bands"],
        "average": round(float(item["average"]), 2),
    }


@router.get("")
async def case_board(_user_id: int = Depends(_creator)):
    pool = _pool()
    await _ensure(pool)
    rows = await pool.fetch("SELECT case_id, max_cute, bands FROM case_rules")
    saved = {str(row["case_id"]): _stored(row) for row in rows}
    return {
        "cases": [_card(public_case(saved.get(item["id"]), item["id"])) for item in cases()],
        "items": await _shelf(pool),
    }


@router.post("/price")
async def save_case_price(body: PriceBody, _user_id: int = Depends(_creator)):
    row = await _touch_shelf(_pool(), body.id, "price", body.price)
    return {"ok": True, "id": str(row["id"]), "name": row["name"], "price": int(row["price"])}


@router.post("/stock")
async def save_case_stock(body: StockBody, _user_id: int = Depends(_creator)):
    row = await _touch_shelf(_pool(), body.id, "remains", body.remains)
    return {"ok": True, "id": str(row["id"]), "name": row["name"], "remains": int(row["remains"] or 0)}


@router.post("/rules")
async def save_case_rules(body: RulesBody, _user_id: int = Depends(_creator)):
    try:
        checked = check_rules(body.id, body.max, [row.model_dump() for row in body.bands])
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Шансы должны сложиться в 100, а самый большой приз равен потолку",
        )
    pool = _pool()
    await _ensure(pool)
    await pool.execute(
        """
        INSERT INTO case_rules (case_id, max_cute, bands)
        VALUES ($1, $2, $3::jsonb)
        ON CONFLICT (case_id) DO UPDATE
        SET max_cute = EXCLUDED.max_cute,
            bands = EXCLUDED.bands
        """,
        checked["id"],
        checked["max"],
        json.dumps(checked["bands"], ensure_ascii=False),
    )
    item = public_case(checked, checked["id"])
    item["average"] = average(checked["bands"])
    return _card(item)
