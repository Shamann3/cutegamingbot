# -*- coding: utf-8 -*-
"""Админка игр: каталог, сохранение, комиссия, история. Деньги не двигает."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List

from db import db
from game_desk.catalog import catalog_public, default_payload, game_meta
from game_desk.schema import ensure_game_desk_schema
from game_desk.store import load_payload, merge_payload, save_payload

_schema_ok = False


async def _ensure() -> None:
    global _schema_ok
    if _schema_ok:
        return
    await ensure_game_desk_schema(db)
    _schema_ok = True


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return value


def _preview(settings: Dict[str, Any], game_key: str, pot: int, level: int) -> Dict[str, Any]:
    comm = settings.get("commission") or {}
    if not comm.get("enabled"):
        return {"commission": 0, "rate": 0, "note": "комиссия выключена"}
    if pot < int(comm.get("minPot") or 0):
        return {"commission": 0, "rate": 0, "note": "банк меньше минимума"}
    game = (settings.get("games") or {}).get(game_key) or {}
    rate = max(0.0, min(1.0, float((comm.get("rateByLevel") or {}).get(str(level), 0)) * float(game.get("commissionMult") or 0)))
    amount = math.floor(int(pot) * rate)
    return {"commission": amount, "rate": rate, "note": ""}


async def overview() -> Dict[str, Any]:
    await _ensure()
    settings = await load_payload(db)
    stats: List[Dict[str, Any]] = []
    total = 0
    events = 0
    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT game,
                       COUNT(*)::int AS events,
                       COALESCE(SUM(commission), 0)::bigint AS commission,
                       COALESCE(SUM(pot), 0)::bigint AS pot
                FROM growth_fund_ledger
                GROUP BY game
                """
            )
            meta_row = await conn.fetchrow(
                "SELECT updated_at, updated_by FROM game_desk_settings WHERE id = 1"
            )
            hist = await conn.fetch(
                """
                SELECT id, admin_id, patch, created_at
                FROM game_desk_history
                ORDER BY id DESC
                LIMIT 24
                """
            )
    except Exception:
        rows = []
        meta_row = None
        hist = []
    by_game = {str(r["game"]): r for r in rows}
    for item in catalog_public():
        row = by_game.get(item["key"])
        take = int(row["commission"]) if row else 0
        n = int(row["events"]) if row else 0
        total += take
        events += n
        stats.append({
            "key": item["key"],
            "title": item["title"],
            "kind": item["kind"],
            "commission": take,
            "events": n,
            "pot": int(row["pot"]) if row else 0,
        })
    games = []
    for item in catalog_public():
        state = (settings.get("games") or {}).get(item["key"]) or item["defaults"]
        preview = _preview(settings, item["key"], 100, 3)
        games.append({
            **item,
            "state": state,
            "stats": next((s for s in stats if s["key"] == item["key"]), {}),
            "preview": preview,
        })
    return {
        "settings": settings,
        "defaults": default_payload(),
        "catalog": games,
        "totals": {
            "commission": total,
            "events": events,
            "on": sum(1 for g in games if g["state"].get("enabled")),
            "off": sum(1 for g in games if not g["state"].get("enabled")),
        },
        "history": [
            {
                "id": int(r["id"]),
                "adminId": int(r["admin_id"]),
                "patch": r["patch"],
                "createdAt": _jsonable(r["created_at"]),
            }
            for r in hist
        ],
        "updatedAt": _jsonable(meta_row["updated_at"]) if meta_row and meta_row["updated_at"] else None,
        "updatedBy": int(meta_row["updated_by"]) if meta_row and meta_row["updated_by"] else None,
    }


async def save_settings(patch: Dict[str, Any], admin_id: int) -> Dict[str, Any]:
    await _ensure()
    current = await load_payload(db)
    nxt = merge_payload(current, patch or {})
    await save_payload(db, nxt, admin_id=admin_id, patch=patch or {})
    return await overview()


async def reset_game(game_key: str, admin_id: int) -> Dict[str, Any]:
    meta = game_meta(game_key)
    if not meta:
        raise ValueError("Нет такой игры")
    return await save_settings({"games": {meta["key"]: dict(meta["defaults"])}}, admin_id)
