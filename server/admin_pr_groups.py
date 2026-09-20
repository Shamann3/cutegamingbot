# -*- coding: utf-8 -*-
"""Админка «Пиар в группах». Деньги посева двигает бот, здесь только очередь."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admin_auth import require_admin_session
from db import db
from pr_groups_logic import (
    CLAIM_COLUMNS,
    DEFAULT_REJECT_REASONS,
    DEFAULT_TERM_DAYS,
    MAX_LIVE_SEEDS,
    PHOTO_HINTS,
    ST_ACCEPTING,
    ST_LIVE,
    ST_PENDING,
    ST_REJECTED,
    WEEK_SEED_STATUSES,
    group_link,
    left_days_hint,
    recommend_seed,
    recommend_split,
    say,
    reject_text_from,
    spendable_amount,
    weekly_seed_budget,
)

log = logging.getLogger("admin_pr_groups")
router = APIRouter(prefix="/pr-groups", tags=["pr-groups"])
_schema = False


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


async def ensure_pr_schema() -> None:
    global _schema
    if _schema:
        return
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            reject_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        INSERT INTO pr_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
        CREATE TABLE IF NOT EXISTS pr_membership (
            chat_id BIGINT PRIMARY KEY,
            first_joined_at TIMESTAMPTZ,
            last_joined_at TIMESTAMPTZ,
            last_left_at TIMESTAMPTZ,
            last_added_by BIGINT,
            times_joined INTEGER NOT NULL DEFAULT 0,
            is_member BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE TABLE IF NOT EXISTS pr_claims (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL,
            photos JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS pr_notices (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            kind TEXT NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    for col, spec in CLAIM_COLUMNS:
        try:
            await db.pool.execute(f"ALTER TABLE pr_claims ADD COLUMN IF NOT EXISTS {col} {spec}")
        except Exception:
            pass
    _schema = True


async def _money() -> dict[str, Any]:
    from nika.policy import SOURCE_LADDER
    ids = [int(cid) for cid, title in SOURCE_LADDER if title != "копилка"]
    rows = await db.pool.fetch(
        "SELECT chat_id, COALESCE(chatbalance, 0)::bigint AS b FROM chat WHERE chat_id = ANY($1::bigint[])",
        ids,
    )
    by = {int(r["chat_id"]): _as_int(r["b"]) for r in rows}
    earmark = _as_int(await db.pool.fetchval(
        "SELECT COALESCE(SUM(pool_left), 0) FROM pr_claims WHERE status = ANY($1::text[])",
        ["live", "accepting", "fulfilling"],
    ))
    ladder = sum(by.get(int(i), 0) for i in ids) - earmark
    try:
        reserve = _as_int(await db.pool.fetchval(
            """
            SELECT COALESCE(SUM(GREATEST(0,
                COALESCE(s.target_balance, 0) - COALESCE(c.chatbalance, 0)
            )), 0) FROM nika_group_settings s
            JOIN chat c ON c.chat_id = s.chat_id
            WHERE COALESCE(s.enabled, TRUE) = TRUE
            """
        ))
    except Exception:
        reserve = 0
    week_used = _as_int(await db.pool.fetchval(
        """
        SELECT COALESCE(SUM(seed_total), 0) FROM pr_claims
         WHERE status = ANY($1::text[])
           AND COALESCE(accepted_at, updated_at) >= NOW() - INTERVAL '7 days'
        """,
        list(WEEK_SEED_STATUSES),
    ))
    can = spendable_amount(max(0, ladder), reserve)
    return {
        "spendable": can,
        "nikaReserve": reserve,
        "ladderFree": max(0, ladder),
        "weeklyUsed": week_used,
        "weeklyCap": weekly_seed_budget(can),
        "weeklyLeft": max(0, weekly_seed_budget(can) - week_used),
    }


async def _user_bit(user_id: Optional[int]) -> dict[str, Any]:
    if not user_id:
        return {"id": None, "name": "", "username": ""}
    row = await db.pool.fetchrow(
        "SELECT user_id, first_name, username FROM users WHERE user_id = $1",
        int(user_id),
    )
    if not row:
        return {"id": int(user_id), "name": str(user_id), "username": ""}
    return {
        "id": int(row["user_id"]),
        "name": row["first_name"] or str(user_id),
        "username": row["username"] or "",
    }


async def _public_claim(row) -> dict[str, Any]:
    data = dict(row)
    photos = data.get("photos") or []
    if isinstance(photos, str):
        photos = json.loads(photos)
    mem = await db.pool.fetchrow("SELECT * FROM pr_membership WHERE chat_id = $1", int(data["chat_id"]))
    left = None
    if mem and mem["last_left_at"] and mem["times_joined"] and int(mem["times_joined"]) > 1:
        left_at = mem["last_left_at"]
        if getattr(left_at, "tzinfo", None) is None:
            left_at = left_at.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - left_at
        left = max(0, int(delta.total_seconds() // 86400))
    members = _as_int(data.get("member_count"))
    money = await _money()
    rec_total = recommend_seed(members, min(money["spendable"], money["weeklyLeft"]))
    chat_row = await db.pool.fetchrow(
        "SELECT COALESCE(chatbalance, 0)::bigint AS b FROM chat WHERE chat_id = $1",
        int(data["chat_id"]),
    )
    return {
        "id": int(data["id"]),
        "status": data["status"],
        "role": data["role"],
        "chatId": int(data["chat_id"]),
        "title": data.get("chat_title") or str(data["chat_id"]),
        "username": data.get("chat_username") or "",
        "link": group_link(data.get("chat_username"), data["chat_id"]),
        "memberCount": members,
        "user": await _user_bit(data.get("user_id")),
        "creator": await _user_bit(data.get("creator_id")),
        "addedBy": await _user_bit(data.get("added_by")),
        "photos": [
            {"fileId": p.get("file_id"), "label": PHOTO_HINTS[i] if i < len(PHOTO_HINTS) else say("photo_hint_n", n=i + 1)}
            for i, p in enumerate(photos)
        ],
        "left": left_days_hint(left),
        "burned": data.get("status") == "burned",
        "freeze": data.get("freeze"),
        "money": money,
        "recommend": recommend_split(rec_total, members),
        "termDays": _as_int(data.get("term_days"), DEFAULT_TERM_DAYS),
        "seedTotal": _as_int(data.get("seed_total")),
        "tableAmount": _as_int(data.get("table_amount")),
        "poolAmount": _as_int(data.get("pool_amount")),
        "poolLeft": _as_int(data.get("pool_left")),
        "giftSize": _as_int(data.get("gift_size")),
        "seedLock": _as_int(data.get("seed_lock")),
        "nikaOn": bool(data.get("nika_on")),
        "paid": _as_int(data.get("paid_kut")),
        "commission": _as_int(data.get("commission_seen")),
        "liveUntil": _iso(data.get("live_until")),
        "acceptedAt": _iso(data.get("accepted_at")),
        "createdAt": _iso(data.get("created_at")),
        "rejectText": data.get("reject_text") or "",
        "chatBalance": _as_int(chat_row["b"]) if chat_row else 0,
        "alreadyKnown": bool(chat_row),
    }


class AcceptBody(BaseModel):
    seed: int = Field(ge=0, le=100000)
    termDays: int = Field(default=14, ge=1, le=90)
    nikaOn: bool = False


class RejectBody(BaseModel):
    reasonIds: list[str] = []
    customReason: str = ""


class SettingsBody(BaseModel):
    rejectReasons: list[dict[str, str]] = []


@router.get("/overview")
async def overview(admin=Depends(require_admin_session)):
    await ensure_pr_schema()
    pending = _as_int(await db.pool.fetchval("SELECT COUNT(*) FROM pr_claims WHERE status = $1", ST_PENDING))
    live = _as_int(await db.pool.fetchval("SELECT COUNT(*) FROM pr_claims WHERE status = 'live'"))
    money = await _money()
    return {"pending": pending, "live": live, **money}


@router.get("/queue")
async def queue(admin=Depends(require_admin_session)):
    await ensure_pr_schema()
    rows = await db.pool.fetch(
        "SELECT * FROM pr_claims WHERE status = $1 ORDER BY created_at ASC",
        ST_PENDING,
    )
    return {"items": [await _public_claim(r) for r in rows]}


@router.get("/live")
async def live(admin=Depends(require_admin_session)):
    await ensure_pr_schema()
    rows = await db.pool.fetch(
        "SELECT * FROM pr_claims WHERE status = 'live' ORDER BY accepted_at DESC NULLS LAST"
    )
    return {"items": [await _public_claim(r) for r in rows]}


@router.get("/archive")
async def archive(admin=Depends(require_admin_session)):
    await ensure_pr_schema()
    rows = await db.pool.fetch(
        """
        SELECT * FROM pr_claims
         WHERE status = ANY($1::text[])
         ORDER BY updated_at DESC LIMIT 50
        """,
        ["rejected", "ended", "burned", "cancelled", "expired"],
    )
    return {"items": [await _public_claim(r) for r in rows]}


@router.get("/claim/{claim_id}")
async def one_claim(claim_id: int, admin=Depends(require_admin_session)):
    await ensure_pr_schema()
    row = await db.pool.fetchrow("SELECT * FROM pr_claims WHERE id = $1", int(claim_id))
    if not row:
        raise HTTPException(404, "Нет заявки")
    return await _public_claim(row)


@router.post("/claim/{claim_id}/accept")
async def accept(claim_id: int, body: AcceptBody, admin=Depends(require_admin_session)):
    await ensure_pr_schema()
    money = await _money()
    if body.seed > money["spendable"]:
        raise HTTPException(400, "Не хватает суммы, которую можно потратить")
    if body.seed > money["weeklyLeft"]:
        raise HTTPException(400, "Недельный бюджет посева")
    pending = await db.pool.fetchrow("SELECT user_id FROM pr_claims WHERE id = $1 AND status = $2", int(claim_id), ST_PENDING)
    if pending:
        live_now = _as_int(await db.pool.fetchval(
            "SELECT COUNT(*) FROM pr_claims WHERE user_id = $1 AND status = $2",
            int(pending["user_id"]), ST_LIVE,
        ))
        if live_now >= MAX_LIVE_SEEDS:
            raise HTTPException(400, "У этого человека уже 2 живые группы")
    row = await db.pool.fetchrow(
        """
        UPDATE pr_claims
           SET status = $2, seed_total = $3, term_days = $4, nika_on = $5, updated_at = NOW()
         WHERE id = $1 AND status = $6
     RETURNING id
        """,
        int(claim_id), ST_ACCEPTING, int(body.seed), int(body.termDays), bool(body.nikaOn), ST_PENDING,
    )
    if not row:
        raise HTTPException(404, "Заявка уже не в очереди")
    return {"ok": True}


@router.post("/claim/{claim_id}/reject")
async def reject(claim_id: int, body: RejectBody, admin=Depends(require_admin_session)):
    await ensure_pr_schema()
    settings = await db.pool.fetchrow("SELECT reject_reasons FROM pr_settings WHERE id = 1")
    catalog = DEFAULT_REJECT_REASONS
    if settings and settings["reject_reasons"]:
        raw = settings["reject_reasons"]
        if isinstance(raw, str):
            raw = json.loads(raw)
        if raw:
            catalog = raw
    picked = [{"id": i} for i in body.reasonIds]
    text = reject_text_from(picked, body.customReason, catalog)
    row = await db.pool.fetchrow(
        """
        UPDATE pr_claims
           SET status = $2, reject_text = $3, reject_hold_until = NOW() + INTERVAL '48 hours', updated_at = NOW()
         WHERE id = $1 AND status = $4
     RETURNING user_id
        """,
        int(claim_id), ST_REJECTED, text, ST_PENDING,
    )
    if not row:
        raise HTTPException(404, "Заявка уже не в очереди")
    await db.pool.execute(
        "INSERT INTO pr_notices (user_id, kind, payload) VALUES ($1, $2, $3::jsonb)",
        int(row["user_id"]), "rejected", json.dumps({"text": text, "canFix": True}, ensure_ascii=False),
    )
    return {"ok": True}


@router.post("/claim/{claim_id}/nika")
async def toggle_nika(claim_id: int, admin=Depends(require_admin_session)):
    await ensure_pr_schema()
    row = await db.pool.fetchrow(
        """
        UPDATE pr_claims SET nika_on = NOT COALESCE(nika_on, FALSE), updated_at = NOW()
         WHERE id = $1 AND status = 'live'
     RETURNING nika_on
        """,
        int(claim_id),
    )
    if not row:
        raise HTTPException(404, "Нет живой группы")
    return {"nikaOn": bool(row["nika_on"])}


@router.get("/settings")
async def get_settings(admin=Depends(require_admin_session)):
    await ensure_pr_schema()
    row = await db.pool.fetchrow("SELECT reject_reasons FROM pr_settings WHERE id = 1")
    reasons = DEFAULT_REJECT_REASONS
    if row and row["reject_reasons"]:
        raw = row["reject_reasons"]
        if isinstance(raw, str):
            raw = json.loads(raw)
        if raw:
            reasons = raw
    return {
        "rejectReasons": reasons,
        "sharePct": 35,
        "weeklyPct": 15,
        "maxLive": 2,
        "nikaThreshold": 3,
        "nikaStep": 20,
        "nikaHours": 12,
        "nikaCap": 50,
    }


@router.put("/settings")
async def put_settings(body: SettingsBody, admin=Depends(require_admin_session)):
    await ensure_pr_schema()
    reasons = [r for r in body.rejectReasons if str(r.get("label") or "").strip()]
    await db.pool.execute(
        "UPDATE pr_settings SET reject_reasons = $1::jsonb, updated_at = NOW() WHERE id = 1",
        json.dumps(reasons or DEFAULT_REJECT_REASONS, ensure_ascii=False),
    )
    return await get_settings(admin)
