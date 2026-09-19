# -*- coding: utf-8 -*-
"""Админка игр: каталог, сохранение, комиссия, аналитика. Деньги не двигает."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from db import db
from game_desk.catalog import catalog_public, default_payload, game_meta, resolve_key
from game_desk.schema import ensure_game_desk_schema
from game_desk.store import load_payload, merge_payload, save_payload

_schema_ok = False
_MONTHS = ("янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")


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


def _aware(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bucket_key(value, trunc: str) -> str:
    if isinstance(value, datetime):
        dt = _aware(value)
        return dt.strftime("%Y-%m-%dT%H") if trunc == "hour" else dt.strftime("%Y-%m-%d")
    text = str(value or "")
    if trunc == "hour":
        return text[:13].replace(" ", "T")
    return text[:10]


def _iter_buckets(since, until, trunc: str) -> List[datetime]:
    step = timedelta(hours=1) if trunc == "hour" else timedelta(days=1)
    cap = 48 if trunc == "hour" else 62
    end = _aware(until)
    start = _aware(since)
    if trunc == "hour":
        end = end.replace(minute=0, second=0, microsecond=0)
        start = start.replace(minute=0, second=0, microsecond=0)
    else:
        end = end.replace(hour=0, minute=0, second=0, microsecond=0)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    out: List[datetime] = []
    cur = end
    while cur >= start and len(out) < cap:
        out.append(cur)
        cur = cur - step
    out.reverse()
    return out


def _label(dt: datetime, trunc: str) -> str:
    d = _aware(dt)
    if trunc == "hour":
        return d.strftime("%H:%M")
    return f"{d.day} {_MONTHS[d.month - 1]}"


def _point(dt: datetime, trunc: str, pot: int, commission: int, events: int) -> Dict[str, Any]:
    return {
        "t": _jsonable(dt),
        "label": _label(dt, trunc),
        "events": int(events),
        "pot": int(pot),
        "commission": int(commission),
        "plus": int(pot),
        "minus": int(commission),
        "net": int(pot) - int(commission),
    }


def _extrema(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    plus_n = sum(1 for p in points if (p.get("net") or 0) > 0)
    minus_n = sum(1 for p in points if (p.get("net") or 0) < 0)
    best = max(points, key=lambda p: p.get("net") or 0) if points else None
    worst = min(points, key=lambda p: p.get("net") or 0) if points else None
    if best and (best.get("net") or 0) <= 0:
        best = None
    if worst and (worst.get("net") or 0) >= 0:
        worst = None
    return {
        "plusBuckets": plus_n,
        "minusBuckets": minus_n,
        "flatBuckets": max(0, len(points) - plus_n - minus_n),
        "best": best,
        "worst": worst,
    }


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


def _fill_series(by_bucket: Dict[str, Dict[str, int]], since, until, trunc: str) -> List[Dict[str, Any]]:
    points = []
    for dt in _iter_buckets(since, until, trunc):
        row = by_bucket.get(_bucket_key(dt, trunc)) or {}
        points.append(_point(dt, trunc, _as_int(row.get("pot")), _as_int(row.get("commission")), _as_int(row.get("events"))))
    return points


async def _load_series(conn, since, until, trunc: str) -> Dict[str, List[Dict[str, Any]]]:
    trunc = "hour" if trunc == "hour" else "day"
    try:
        rows = await conn.fetch(
            f"""
            SELECT game,
                   date_trunc('{trunc}', created_at) AS bucket,
                   COUNT(*)::int AS events,
                   COALESCE(SUM(commission), 0)::bigint AS commission,
                   COALESCE(SUM(pot), 0)::bigint AS pot
            FROM growth_fund_ledger
            WHERE created_at >= $1 AND created_at <= $2
            GROUP BY 1, 2
            """,
            since,
            until,
        )
    except Exception:
        rows = []
    buckets: Dict[str, Dict[str, Dict[str, int]]] = {}
    all_buckets: Dict[str, Dict[str, int]] = {}
    for row in rows:
        key = resolve_key(str(row["game"] or ""))
        stamp = _bucket_key(row["bucket"], trunc)
        cell = buckets.setdefault(key, {}).setdefault(stamp, {"events": 0, "pot": 0, "commission": 0})
        cell["events"] += _as_int(row["events"])
        cell["pot"] += _as_int(row["pot"])
        cell["commission"] += _as_int(row["commission"])
        total = all_buckets.setdefault(stamp, {"events": 0, "pot": 0, "commission": 0})
        total["events"] += _as_int(row["events"])
        total["pot"] += _as_int(row["pot"])
        total["commission"] += _as_int(row["commission"])
    out = {key: _fill_series(vals, since, until, trunc) for key, vals in buckets.items()}
    out["_all"] = _fill_series(all_buckets, since, until, trunc)
    return out


async def overview() -> Dict[str, Any]:
    await _ensure()
    settings = await load_payload(db)
    stats: List[Dict[str, Any]] = []
    total = 0
    events = 0
    now = datetime.now(timezone.utc)
    days_since = now - timedelta(days=62)
    hours_since = now - timedelta(hours=48)
    days: Dict[str, List[Dict[str, Any]]] = {}
    hours: Dict[str, List[Dict[str, Any]]] = {}
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
            days = await _load_series(conn, days_since, now, "day")
            hours = await _load_series(conn, hours_since, now, "hour")
    except Exception:
        rows = []
        meta_row = None
        hist = []
        days = {}
        hours = {}
    by_game = {}
    for r in rows:
        key = resolve_key(str(r["game"] or ""))
        cur = by_game.setdefault(key, {"events": 0, "commission": 0, "pot": 0})
        cur["events"] += _as_int(r["events"])
        cur["commission"] += _as_int(r["commission"])
        cur["pot"] += _as_int(r["pot"])
    for item in catalog_public():
        row = by_game.get(item["key"])
        take = _as_int(row["commission"]) if row else 0
        n = _as_int(row["events"]) if row else 0
        pot = _as_int(row["pot"]) if row else 0
        total += take
        events += n
        stats.append({
            "key": item["key"],
            "title": item["title"],
            "kind": item["kind"],
            "commission": take,
            "events": n,
            "pot": pot,
        })
    empty_days = _fill_series({}, days_since, now, "day")
    empty_hours = _fill_series({}, hours_since, now, "hour")
    games = []
    for item in catalog_public():
        state = (settings.get("games") or {}).get(item["key"]) or item["defaults"]
        preview = _preview(settings, item["key"], 100, 3)
        day_points = days.get(item["key"]) or empty_days
        hour_points = hours.get(item["key"]) or empty_hours
        games.append({
            **item,
            "state": state,
            "stats": next((s for s in stats if s["key"] == item["key"]), {}),
            "preview": preview,
            "days": day_points,
            "hours": hour_points,
            "dayExtrema": _extrema(day_points),
            "hourExtrema": _extrema(hour_points),
        })
    return {
        "settings": settings,
        "defaults": default_payload(),
        "catalog": games,
        "totals": {
            "commission": total,
            "events": events,
            "pot": sum(_as_int((s or {}).get("pot")) for s in stats),
            "on": sum(1 for g in games if g["state"].get("enabled") and not g["state"].get("maintenance")),
            "off": sum(1 for g in games if not g["state"].get("enabled")),
            "maintenance": sum(1 for g in games if g["state"].get("maintenance")),
        },
        "series": {
            "days": days.get("_all") or empty_days,
            "hours": hours.get("_all") or empty_hours,
            "dayExtrema": _extrema(days.get("_all") or empty_days),
            "hourExtrema": _extrema(hours.get("_all") or empty_hours),
            "sinceDays": _jsonable(days_since),
            "sinceHours": _jsonable(hours_since),
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
