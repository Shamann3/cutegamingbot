# -*- coding: utf-8 -*-
"""Админка игр: каталог, сохранение, комиссия, история. Деньги не двигает."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

from db import db
from game_desk.catalog import catalog_public, default_payload, game_meta, resolve_key
from game_desk.schema import ensure_game_desk_schema
from game_desk.store import load_payload, merge_payload, save_payload

_schema_ok = False


async def _ensure() -> None:
    global _schema_ok
    if _schema_ok:
        return
    await ensure_game_desk_schema(db)
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_gf_ledger_game_created
                    ON growth_fund_ledger (game, created_at DESC)
                """
            )
    except Exception:
        pass
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


def _day_label(iso: str) -> str:
    try:
        d = date.fromisoformat(iso[:10])
    except Exception:
        return iso
    return f"{d.day:02d}.{d.month:02d}"


def _empty_day(iso: str) -> Dict[str, Any]:
    return {
        "day": iso,
        "label": _day_label(iso),
        "plus": 0,
        "minus": 0,
        "system": 0,
        "events": 0,
        "pot": 0,
        "commission": 0,
    }


def _canon_game(name: Any) -> str:
    try:
        return resolve_key(str(name or ""))
    except Exception:
        return str(name or "")


async def overview() -> Dict[str, Any]:
    await _ensure()
    settings = await load_payload(db)
    stats: List[Dict[str, Any]] = []
    total = 0
    events = 0
    day_rows = []
    recent_rows = []
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
            day_rows = await conn.fetch(
                """
                SELECT game,
                       ((created_at AT TIME ZONE 'UTC')::date) AS day,
                       COUNT(*)::int AS events,
                       COALESCE(SUM(commission), 0)::bigint AS commission,
                       COALESCE(SUM(pot), 0)::bigint AS pot
                FROM growth_fund_ledger
                WHERE created_at >= NOW() - INTERVAL '14 days'
                GROUP BY game, day
                ORDER BY day
                """
            )
            recent_rows = await conn.fetch(
                """
                SELECT game, chat_id, user_id, pot, commission, level, created_at
                FROM growth_fund_ledger
                ORDER BY created_at DESC
                LIMIT 80
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
        day_rows = []
        recent_rows = []
        meta_row = None
        hist = []
    by_game = {}
    for r in rows:
        key = _canon_game(r["game"])
        prev = by_game.get(key)
        if prev:
            by_game[key] = {
                "events": int(prev["events"]) + int(r["events"]),
                "commission": int(prev["commission"]) + int(r["commission"]),
                "pot": int(prev["pot"]) + int(r["pot"]),
            }
        else:
            by_game[key] = {
                "events": int(r["events"]),
                "commission": int(r["commission"]),
                "pot": int(r["pot"]),
            }
    today = date.today()
    day_keys = [(today - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    days_map: Dict[str, Dict[str, Dict[str, int]]] = {}
    flow_acc: Dict[str, Dict[str, int]] = {d: {"plus": 0, "events": 0, "pot": 0} for d in day_keys}
    for r in day_rows:
        key = _canon_game(r["game"])
        day = r["day"].isoformat() if hasattr(r["day"], "isoformat") else str(r["day"])[:10]
        bucket = days_map.setdefault(key, {})
        cur = bucket.get(day) or {"events": 0, "commission": 0, "pot": 0}
        cur["events"] += int(r["events"])
        cur["commission"] += int(r["commission"])
        cur["pot"] += int(r["pot"])
        bucket[day] = cur
        if day in flow_acc:
            flow_acc[day]["plus"] += int(r["commission"])
            flow_acc[day]["events"] += int(r["events"])
            flow_acc[day]["pot"] += int(r["pot"])
    recent_by: Dict[str, List[Dict[str, Any]]] = {}
    for r in recent_rows:
        key = _canon_game(r["game"])
        recent_by.setdefault(key, []).append({
            "game": key,
            "chatId": int(r["chat_id"]),
            "userId": int(r["user_id"]),
            "pot": int(r["pot"] or 0),
            "commission": int(r["commission"] or 0),
            "level": int(r["level"] or 0),
            "createdAt": _jsonable(r["created_at"]),
        })
    analytics: Dict[str, Any] = {}
    for item in catalog_public():
        row = by_game.get(item["key"])
        take = int(row["commission"]) if row else 0
        n = int(row["events"]) if row else 0
        pot = int(row["pot"]) if row else 0
        total += take
        events += n
        days = []
        for day in day_keys:
            rec = (days_map.get(item["key"]) or {}).get(day) or {}
            comm = int(rec.get("commission") or 0)
            ev = int(rec.get("events") or 0)
            p = int(rec.get("pot") or 0)
            days.append({
                "day": day,
                "label": _day_label(day),
                "plus": comm,
                "minus": 0,
                "system": p,
                "events": ev,
                "pot": p,
                "commission": comm,
            })
        stats.append({
            "key": item["key"],
            "title": item["title"],
            "kind": item["kind"],
            "commission": take,
            "events": n,
            "pot": pot,
        })
        analytics[item["key"]] = {
            "days": days,
            "recent": (recent_by.get(item["key"]) or [])[:12],
            "events": n,
            "commission": take,
            "pot": pot,
        }
    games = []
    for item in catalog_public():
        state = (settings.get("games") or {}).get(item["key"]) or item["defaults"]
        preview = _preview(settings, item["key"], 100, 3)
        game_stats = next((s for s in stats if s["key"] == item["key"]), {})
        games.append({
            **item,
            "state": state,
            "stats": game_stats,
            "analytics": analytics.get(item["key"]) or {},
            "preview": preview,
        })
    flow = [_empty_day(d) for d in day_keys]
    for point in flow:
        acc = flow_acc.get(point["day"]) or {}
        point["plus"] = int(acc.get("plus") or 0)
        point["events"] = int(acc.get("events") or 0)
        point["pot"] = int(acc.get("pot") or 0)
        point["system"] = point["pot"]
        point["commission"] = point["plus"]
    return {
        "settings": settings,
        "defaults": default_payload(),
        "catalog": games,
        "analytics": analytics,
        "flow": {"days": flow},
        "totals": {
            "commission": total,
            "events": events,
            "on": sum(1 for g in games if g["state"].get("enabled") and not g["state"].get("maintenance")),
            "off": sum(1 for g in games if not g["state"].get("enabled")),
            "maintenance": sum(1 for g in games if g["state"].get("maintenance")),
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
