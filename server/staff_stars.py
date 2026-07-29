"""Очередь зарплатных выплат звёздами (панель ↔ бот через БД)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from db import db

logger = logging.getLogger(__name__)

STAR_METHODS = ("auto", "fragment", "userbot")


def _row(r) -> dict[str, Any]:
    return {
        "id": int(r["id"]),
        "salaryId": int(r["salary_id"]) if r["salary_id"] else None,
        "bonusId": int(r["bonus_id"]) if r.get("bonus_id") else None,
        "source": r["source"] or "salary",
        "userId": int(r["user_id"]),
        "amount": int(r["amount"]),
        "starsUsername": (r["stars_username"] or "").lstrip("@"),
        "method": r["method"],
        "status": r["status"],
        "requestedBy": int(r["requested_by"]) if r["requested_by"] else None,
        "kind": r["kind"] or "payment",
        "error": r["error"],
        "txid": r["txid"],
        "channelMessageId": int(r["channel_message_id"]) if r["channel_message_id"] else None,
        "requestId": r["request_id"],
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        "completedAt": r["completed_at"].isoformat() if r["completed_at"] else None,
    }


async def get_fragment_health() -> dict[str, Any]:
    row = await db.pool.fetchrow(
        """
        SELECT fragment_ok, fragment_ton, fragment_checked_at, fragment_error,
               default_stars_method
        FROM staff_payout_settings WHERE id = 1
        """
    )
    if not row:
        return {
            "ok": None,
            "ton": None,
            "checkedAt": None,
            "error": "Настройки ещё не инициализированы",
            "defaultStarsMethod": "auto",
            "stale": True,
        }
    checked = row["fragment_checked_at"]
    stale = True
    if checked is not None:
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) - checked).total_seconds()
        stale = age > 180  # старше 3 минут — устарело
    return {
        "ok": row["fragment_ok"],
        "ton": float(row["fragment_ton"]) if row["fragment_ton"] is not None else None,
        "checkedAt": checked.isoformat() if checked else None,
        "error": row["fragment_error"],
        "defaultStarsMethod": row["default_stars_method"] or "auto",
        "stale": stale,
    }


async def update_fragment_health(
    *,
    ok: bool,
    ton: float | None = None,
    error: str | None = None,
) -> None:
    await db.pool.execute(
        """
        INSERT INTO staff_payout_settings (id, fragment_ok, fragment_ton, fragment_error, fragment_checked_at)
        VALUES (1, $1, $2, $3, NOW())
        ON CONFLICT (id) DO UPDATE SET
            fragment_ok = EXCLUDED.fragment_ok,
            fragment_ton = EXCLUDED.fragment_ton,
            fragment_error = EXCLUDED.fragment_error,
            fragment_checked_at = NOW()
        """,
        ok, ton, (error or None),
    )


async def enqueue_star_payout(
    *,
    user_id: int,
    amount: int,
    stars_username: str,
    method: str,
    requested_by: int,
    salary_id: int | None = None,
    bonus_id: int | None = None,
    source: str = "salary",
    kind: str = "payment",
) -> dict:
    method = (method or "auto").strip().lower()
    if method not in STAR_METHODS:
        raise ValueError("method: auto | fragment | userbot")
    username = (stars_username or "").strip().lstrip("@")
    if not username or len(username) < 5:
        raise ValueError("Укажите Telegram username для Stars (без @)")
    if amount <= 0:
        raise ValueError("amount must be > 0")
    if source == "salary" and not salary_id:
        raise ValueError("salary_id required")
    if source == "bonus" and not bonus_id:
        raise ValueError("bonus_id required")

    request_id = f"salstar-{uuid.uuid4().hex[:16]}"
    row = await db.pool.fetchrow(
        """
        INSERT INTO staff_star_payouts
            (salary_id, bonus_id, source, user_id, amount, stars_username,
             method, status, requested_by, kind, request_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'queued', $8, $9, $10)
        RETURNING *
        """,
        salary_id, bonus_id, source, user_id, amount, username,
        method, requested_by, kind, request_id,
    )
    return _row(row)


async def list_star_payouts(limit: int = 30, status: str | None = None) -> list[dict]:
    if status:
        rows = await db.pool.fetch(
            """
            SELECT * FROM staff_star_payouts
            WHERE status = $1
            ORDER BY created_at DESC LIMIT $2
            """,
            status, limit,
        )
    else:
        rows = await db.pool.fetch(
            "SELECT * FROM staff_star_payouts ORDER BY created_at DESC LIMIT $1",
            limit,
        )
    return [_row(r) for r in rows]


async def get_star_payout(payout_id: int) -> dict | None:
    row = await db.pool.fetchrow("SELECT * FROM staff_star_payouts WHERE id = $1", payout_id)
    return _row(row) if row else None


async def cancel_star_payout(payout_id: int) -> bool:
    result = await db.pool.execute(
        """
        UPDATE staff_star_payouts
        SET status = 'cancelled', updated_at = NOW()
        WHERE id = $1 AND status IN ('queued', 'failed', 'channel_pending')
        """,
        payout_id,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False
