# -*- coding: utf-8 -*-
"""Вкладка «Браки» в панели сотрудников: цифры, уровни и настройки."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from admin_audit import log_admin_action
from admin_permissions import require_admin_permission
from db import db

router = APIRouter(prefix="/marriages", tags=["marriages"])
MSK = timezone(timedelta(hours=3))
_PY = str(Path(__file__).resolve().parent / "py")
if _PY not in sys.path:
    sys.path.insert(0, _PY)


def _rules():
    from marriage_engine.rules import (
        price_ladder,
        settings_view,
        tone_label,
        tone_score,
        verb_catalog,
    )
    from marriage_engine.store import ensure, load_settings, save_settings

    return {
        "view": settings_view,
        "ladder": price_ladder,
        "label": tone_label,
        "score": tone_score,
        "verbs": verb_catalog,
        "ensure": ensure,
        "load": load_settings,
        "save": save_settings,
    }


def _day(value: Any):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(MSK).date()
    return None


def _window(period: str):
    days = {"day": 1, "week": 7, "month": 30, "year": 365}.get(period, 7)
    today = datetime.now(MSK).date()
    start = today - timedelta(days=days - 1)
    previous = start - timedelta(days=days)
    return days, today, start, previous


def _in(day, start, end) -> bool:
    return day is not None and start <= day <= end


def _name(row: Optional[dict], user_id: int) -> str:
    if not row:
        return str(user_id)
    first = str(row.get("first_name") or "").strip()
    username = str(row.get("username") or "").strip()
    if first:
        return first
    if username:
        return f"@{username}"
    return str(user_id)


class SettingsBody(BaseModel):
    enabled: bool = True
    freeWeddings: int = 3
    firstPaid: int = 15
    doubleUntil: int = 300
    afterPercent: int = 15
    proposalMinutes: int = 10
    rpPerDay: int = 1
    topLimit: int = 10
    showEmptyProfile: bool = True
    toneOn: bool = True
    toneStart: int = 80
    toneGain: int = 12
    toneDecay: int = 8
    rescueHours: int = 12
    sparkOn: bool = True
    glowPrice: int = 12
    glowCare: int = 3
    candlePrice: int = 25
    candleCare: int = 8
    hearthPrice: int = 70
    hearthCare: int = 20
    matchPrice: int = 80
    ribbonPrice: int = 150
    levels: list = Field(default_factory=list)
    verbs: dict = {}


@router.get("/board")
async def marriage_board(
    period: str = "week",
    _admin_id: int = Depends(require_admin_permission("manage_marriages")),
):
    rules = _rules()
    if db.pool is None:
        raise HTTPException(status_code=503, detail="База сейчас недоступна")
    await rules["ensure"](db.pool)
    days, today, start, previous = _window(period)
    begin = datetime.combine(previous, datetime.min.time(), tzinfo=MSK)
    rows = await db.pool.fetch(
        """
        SELECT state, price, live_at, left_at, created_at,
               payer_id, partner_id, tone_points, tone_day,
               spark_days, spark_best, fade_until
        FROM marriage_book
        WHERE state = 'live'
           OR live_at >= $1
           OR left_at >= $1
           OR created_at >= $1
        """,
        begin,
    )
    try:
        old_rows = await db.pool.fetch(
            """
            SELECT user_id1, user_id2, datetime
            FROM marriages
            WHERE status = 1
            """
        )
    except Exception:
        old_rows = []
    ledger = await db.pool.fetch(
        """
        SELECT at, kind, payer_id, amount
        FROM marriage_ledger
        WHERE at >= $1
        ORDER BY id DESC
        """,
        begin,
    )
    settings = await rules["load"](db.pool)
    decay = int(settings.get("toneDecay") or 0)
    book_live = []
    seen = set()
    weddings = prev_weddings = 0
    divorces = prev_divorces = 0
    proposals = prev_proposals = 0
    kut = prev_kut = 0
    spark_lit = spark_fading = spark_best = 0
    by_day = {}
    cursor = start
    while cursor <= today:
        by_day[cursor.isoformat()] = {"date": cursor.isoformat(), "weddings": 0, "kut": 0}
        cursor += timedelta(days=1)

    for row in rows:
        state = str(row["state"] or "")
        live_day = _day(row["live_at"])
        left_day = _day(row["left_at"])
        made_day = _day(row["created_at"])
        price = int(row["price"] or 0)
        if state == "live":
            key = tuple(sorted((int(row["payer_id"]), int(row["partner_id"]))))
            seen.add(key)
            score = rules["score"](row["tone_points"], row["tone_day"], today, decay, row["live_at"])
            streak = int(row["spark_days"] or 0)
            best = int(row["spark_best"] or 0)
            if streak > 0:
                spark_lit += 1
            spark_best = max(spark_best, best, streak)
            fade = row["fade_until"]
            if isinstance(fade, datetime):
                if fade.tzinfo is None:
                    fade = fade.replace(tzinfo=timezone.utc)
                if fade > datetime.now(MSK):
                    spark_fading += 1
            book_live.append({
                "a": int(row["payer_id"]),
                "b": int(row["partner_id"]),
                "since": row["live_at"],
                "tone": rules["label"](score) if settings.get("toneOn") else "",
                "score": score,
            })
        if state in ("live", "left") and _in(live_day, start, today):
            weddings += 1
            kut += price
            bucket = by_day.get(live_day.isoformat())
            if bucket is not None:
                bucket["weddings"] += 1
                bucket["kut"] += price
        elif state in ("live", "left") and _in(live_day, previous, start - timedelta(days=1)):
            prev_weddings += 1
            prev_kut += price
        if state == "left" and _in(left_day, start, today):
            divorces += 1
        elif state == "left" and _in(left_day, previous, start - timedelta(days=1)):
            prev_divorces += 1
        if _in(made_day, start, today):
            proposals += 1
        elif _in(made_day, previous, start - timedelta(days=1)):
            prev_proposals += 1

    for row in old_rows:
        key = tuple(sorted((int(row["user_id1"]), int(row["user_id2"]))))
        if key in seen:
            continue
        seen.add(key)
        book_live.append({
            "a": int(row["user_id1"]),
            "b": int(row["user_id2"]),
            "since": row["datetime"],
            "tone": "",
            "score": None,
        })

    recent = []
    for row in ledger:
        moment = _day(row["at"])
        amount = int(row["amount"] or 0)
        kind = str(row["kind"] or "")
        if kind in ("rp", "glow", "candle", "hearth", "match", "ribbon") and _in(moment, start, today):
            kut += amount
            bucket = by_day.get(moment.isoformat()) if moment else None
            if bucket is not None:
                bucket["kut"] += amount
        elif kind in ("rp", "glow", "candle", "hearth", "match", "ribbon") and _in(moment, previous, start - timedelta(days=1)):
            prev_kut += amount
        if len(recent) < 12:
            title = {"wed": "Свадьба", "glow": "Блик", "candle": "Свеча", "hearth": "Очаг", "match": "Спичка", "ribbon": "Лента"}.get(kind, "Жест")
            recent.append({
                "payerId": int(row["payer_id"]),
                "title": title,
                "amount": amount,
                "at": row["at"].isoformat() if isinstance(row["at"], datetime) else "",
            })

    scored = [item["score"] for item in book_live if item["score"] is not None]
    bands = [
        {"id": "warm", "label": "В тонусе", "count": 0},
        {"id": "calm", "label": "Спокойно", "count": 0},
        {"id": "quiet", "label": "Тихо", "count": 0},
        {"id": "cold", "label": "Остывает", "count": 0},
    ]
    for score in scored:
        label = rules["label"](score)
        slot = {"в тонусе": 0, "спокойно": 1, "тихо": 2, "остывает": 3}[label]
        bands[slot]["count"] += 1

    book_live.sort(key=lambda item: _day(item["since"]) or today)
    ids = []
    for item in book_live[:8]:
        ids.extend((item["a"], item["b"]))
    for item in recent:
        ids.append(item["payerId"])
    names = {}
    if ids:
        try:
            people = await db.pool.fetch(
                """
                SELECT user_id, first_name, username
                FROM users
                WHERE user_id = ANY($1::bigint[])
                """,
                list({int(i) for i in ids}),
            )
            names = {int(row["user_id"]): dict(row) for row in people}
        except Exception:
            names = {}

    pairs = []
    for item in book_live[:8]:
        since = _day(item["since"])
        together = (today - since).days if since else 0
        pairs.append({
            "a": _name(names.get(item["a"]), item["a"]),
            "b": _name(names.get(item["b"]), item["b"]),
            "days": max(0, together),
            "tone": item["tone"],
        })
    for item in recent:
        item["name"] = _name(names.get(item["payerId"]), item["payerId"])

    months = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
    points = []
    for key in sorted(by_day):
        point = by_day[key]
        parts = key.split("-")
        month = months[(int(parts[1]) or 1) - 1]
        point["label"] = f"{int(parts[2])} {month}"
        points.append(point)

    return {
        "period": period if period in ("day", "week", "month", "year") else "week",
        "days": days,
        "live": len(book_live),
        "weddings": weddings,
        "previousWeddings": prev_weddings,
        "divorces": divorces,
        "previousDivorces": prev_divorces,
        "kut": kut,
        "previousKut": prev_kut,
        "proposals": proposals,
        "previousProposals": prev_proposals,
        "toneAvg": round(sum(scored) / len(scored)) if scored else None,
        "sparkLit": spark_lit,
        "sparkFading": spark_fading,
        "sparkBest": spark_best,
        "bands": bands,
        "points": points,
        "pairs": pairs,
        "recent": recent,
        "settings": settings,
        "ladder": rules["ladder"](settings, 12),
        "verbs": rules["verbs"](settings),
    }


@router.post("/settings")
async def marriage_settings(
    body: SettingsBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_marriages")),
):
    rules = _rules()
    if db.pool is None:
        raise HTTPException(status_code=503, detail="База сейчас недоступна")
    saved = await rules["save"](db.pool, body.model_dump(), admin_id)
    await log_admin_action(
        admin_id,
        "marriages.settings",
        target_type="marriages",
        target_id="1",
        target_label="Настройки отношений",
        details=saved,
        ip=request.client.host if request.client else None,
    )
    return {
        "settings": saved,
        "ladder": rules["ladder"](saved, 12),
        "verbs": rules["verbs"](saved),
    }
