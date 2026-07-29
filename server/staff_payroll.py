"""Payroll v2: периоды зарплаты, настройки выплат, премии, начисление kut с аудитом."""

from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from typing import Any

from db import db

logger = logging.getLogger(__name__)

PERIOD_TYPES = ("day", "week", "month", "year")
PAYOUT_METHODS = ("kut", "stars", "crypto", "card", "other")

DEFAULT_COSIGN = {
    "kut": 800,
    "stars": 300,
    "crypto": 300,
    "card": 300,
    "other": 300,
}


# ---------------------------------------------------------------------------
# Периоды
# ---------------------------------------------------------------------------

def period_start_for(period_type: str, on: date | None = None) -> date:
    """Начало периода, содержащего дату `on` (или сегодня)."""
    d = on or date.today()
    pt = (period_type or "week").strip().lower()
    if pt == "day":
        return d
    if pt == "week":
        return d - timedelta(days=d.weekday())
    if pt == "month":
        return d.replace(day=1)
    if pt == "year":
        return d.replace(month=1, day=1)
    raise ValueError(f"Неизвестный period_type: {period_type}")


def period_end_for(period_type: str, start: date) -> date:
    """Последний день периода (включительно)."""
    pt = (period_type or "week").strip().lower()
    if pt == "day":
        return start
    if pt == "week":
        return start + timedelta(days=6)
    if pt == "month":
        last = calendar.monthrange(start.year, start.month)[1]
        return start.replace(day=last)
    if pt == "year":
        return start.replace(month=12, day=31)
    raise ValueError(f"Неизвестный period_type: {period_type}")


def period_label(period_type: str, start: date) -> str:
    end = period_end_for(period_type, start)
    if period_type == "day":
        return start.isoformat()
    if period_type == "week":
        return f"{start.isoformat()} — {end.isoformat()}"
    if period_type == "month":
        return start.strftime("%Y-%m")
    if period_type == "year":
        return str(start.year)
    return start.isoformat()


# ---------------------------------------------------------------------------
# Настройки выплат
# ---------------------------------------------------------------------------

async def ensure_payout_settings_row() -> None:
    await db.pool.execute(
        "INSERT INTO staff_payout_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING"
    )


async def get_payout_settings() -> dict[str, Any]:
    await ensure_payout_settings_row()
    row = await db.pool.fetchrow("SELECT * FROM staff_payout_settings WHERE id = 1")
    if not row:
        return {
            "cosignKut": DEFAULT_COSIGN["kut"],
            "cosignStars": DEFAULT_COSIGN["stars"],
            "cosignCrypto": DEFAULT_COSIGN["crypto"],
            "cosignCard": DEFAULT_COSIGN["card"],
            "cosignOther": DEFAULT_COSIGN["other"],
            "defaultStarsMethod": "auto",
            "updatedBy": None,
            "updatedAt": None,
        }
    return {
        "cosignKut": int(row["cosign_kut"]),
        "cosignStars": int(row["cosign_stars"]),
        "cosignCrypto": int(row["cosign_crypto"]),
        "cosignCard": int(row["cosign_card"]),
        "cosignOther": int(row["cosign_other"]),
        "defaultStarsMethod": row["default_stars_method"] or "auto",
        "updatedBy": int(row["updated_by"]) if row["updated_by"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


async def update_payout_settings(
    *,
    updated_by: int,
    cosign_kut: int | None = None,
    cosign_stars: int | None = None,
    cosign_crypto: int | None = None,
    cosign_card: int | None = None,
    cosign_other: int | None = None,
    default_stars_method: str | None = None,
) -> dict[str, Any]:
    await ensure_payout_settings_row()
    cur = await get_payout_settings()
    kut = cosign_kut if cosign_kut is not None else cur["cosignKut"]
    stars = cosign_stars if cosign_stars is not None else cur["cosignStars"]
    crypto = cosign_crypto if cosign_crypto is not None else cur["cosignCrypto"]
    card = cosign_card if cosign_card is not None else cur["cosignCard"]
    other = cosign_other if cosign_other is not None else cur["cosignOther"]
    method = (default_stars_method or cur["defaultStarsMethod"]).strip().lower()
    if method not in ("auto", "fragment", "userbot"):
        raise ValueError("defaultStarsMethod: auto | fragment | userbot")
    for name, val in (
        ("cosignKut", kut),
        ("cosignStars", stars),
        ("cosignCrypto", crypto),
        ("cosignCard", card),
        ("cosignOther", other),
    ):
        if not isinstance(val, int) or val < 0 or val > 100_000_000:
            raise ValueError(f"{name}: ожидается целое 0…100000000")

    await db.pool.execute(
        """
        UPDATE staff_payout_settings
        SET cosign_kut = $2, cosign_stars = $3, cosign_crypto = $4,
            cosign_card = $5, cosign_other = $6,
            default_stars_method = $7,
            updated_by = $8, updated_at = NOW()
        WHERE id = 1
        """,
        1, kut, stars, crypto, card, other, method, updated_by,
    )
    return await get_payout_settings()


async def cosign_threshold_for(method: str | None) -> int:
    settings = await get_payout_settings()
    key = (method or "other").strip().lower()
    mapping = {
        "kut": settings["cosignKut"],
        "stars": settings["cosignStars"],
        "crypto": settings["cosignCrypto"],
        "card": settings["cosignCard"],
        "other": settings["cosignOther"],
    }
    return int(mapping.get(key, settings["cosignOther"]))


async def needs_cosign(amount: int, method: str | None) -> bool:
    threshold = await cosign_threshold_for(method)
    if threshold <= 0:
        return False
    return amount >= threshold


# ---------------------------------------------------------------------------
# Начисление kut с аудитом (cutehistory + audit_events)
# ---------------------------------------------------------------------------

async def credit_kut_with_audit(
    conn,
    user_id: int,
    amount: int,
    *,
    cause: str,
    event_type: str = "staff_salary_kut",
    details: dict | None = None,
) -> dict:
    """FOR UPDATE баланс → +amount → cutehistory.

    Возвращает dict для schedule_balance_event после commit.
    """
    if amount <= 0:
        raise ValueError("amount must be > 0")

    before = await conn.fetchval(
        "SELECT balance FROM users WHERE user_id = $1 FOR UPDATE",
        user_id,
    )
    if before is None:
        await conn.execute(
            "INSERT INTO users (user_id, balance, items) VALUES ($1, 0, '{}') ON CONFLICT DO NOTHING",
            user_id,
        )
        before = 0
    before = int(before)
    after = before + amount
    await conn.execute(
        "UPDATE users SET balance = $2 WHERE user_id = $1",
        user_id, after,
    )

    first_name = await conn.fetchval(
        "SELECT first_name FROM admin_accounts WHERE user_id = $1", user_id
    )
    username = await conn.fetchval(
        "SELECT username FROM admin_accounts WHERE user_id = $1", user_id
    )
    from datetime import datetime
    stamped = datetime.now().strftime("%H:%M %d.%m.%Y")
    try:
        await conn.execute(
            """
            INSERT INTO cutehistory
                ("user_id", "+", cause, data, first_name, username, balance)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            user_id, amount, cause, stamped,
            first_name or "", username or "", after,
        )
    except Exception:
        logger.exception("cutehistory insert failed for staff kut credit user=%s", user_id)

    return {
        "event_type": event_type,
        "user_id": user_id,
        "amount": amount,
        "balance_before": before,
        "balance_after": after,
        "details": details or {},
    }


def schedule_kut_audit(ev: dict | None) -> None:
    """После успешного commit транзакции."""
    if not ev:
        return
    from audit_log import schedule_balance_event
    try:
        schedule_balance_event(
            db.pool,
            ev["event_type"],
            ev["user_id"],
            amount=ev["amount"],
            balance_before=ev["balance_before"],
            balance_after=ev["balance_after"],
            details=ev["details"],
        )
    except Exception:
        logger.exception("schedule_balance_event failed for staff kut")

# ---------------------------------------------------------------------------
# Реквизиты сотрудника
# ---------------------------------------------------------------------------

async def get_staff_payout_profile(user_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT user_id, username, first_name, payout_type, payout_details,
               stars_username, crypto_network, crypto_address,
               card_bank, card_number, card_holder, card_sbp_phone
        FROM admin_accounts WHERE user_id = $1
        """,
        user_id,
    )
    if not row:
        return None
    return {
        "userId": int(row["user_id"]),
        "username": row["username"],
        "firstName": row["first_name"],
        "payoutType": row["payout_type"],
        "payoutDetails": row["payout_details"],
        "starsUsername": row["stars_username"] or (row["username"] or ""),
        "cryptoNetwork": row["crypto_network"] or "",
        "cryptoAddress": row["crypto_address"] or "",
        "cardBank": row["card_bank"] or "",
        "cardNumber": row["card_number"] or "",
        "cardHolder": row["card_holder"] or "",
        "cardSbpPhone": row["card_sbp_phone"] or "",
    }


async def update_staff_payout_profile(
    user_id: int,
    *,
    payout_type: str | None = None,
    payout_details: str | None = None,
    stars_username: str | None = None,
    crypto_network: str | None = None,
    crypto_address: str | None = None,
    card_bank: str | None = None,
    card_number: str | None = None,
    card_holder: str | None = None,
    card_sbp_phone: str | None = None,
) -> dict | None:
    cur = await get_staff_payout_profile(user_id)
    if not cur:
        return None
    pt = (payout_type if payout_type is not None else cur["payoutType"]) or "other"
    if pt not in PAYOUT_METHODS:
        raise ValueError("Неизвестный payoutType")

    await db.pool.execute(
        """
        UPDATE admin_accounts SET
            payout_type = $2,
            payout_details = COALESCE($3, payout_details),
            stars_username = $4,
            crypto_network = $5,
            crypto_address = $6,
            card_bank = $7,
            card_number = $8,
            card_holder = $9,
            card_sbp_phone = $10
        WHERE user_id = $1
        """,
        user_id,
        pt,
        payout_details if payout_details is not None else cur["payoutDetails"],
        (stars_username if stars_username is not None else cur["starsUsername"]) or None,
        (crypto_network if crypto_network is not None else cur["cryptoNetwork"]) or None,
        (crypto_address if crypto_address is not None else cur["cryptoAddress"]) or None,
        (card_bank if card_bank is not None else cur["cardBank"]) or None,
        (card_number if card_number is not None else cur["cardNumber"]) or None,
        (card_holder if card_holder is not None else cur["cardHolder"]) or None,
        (card_sbp_phone if card_sbp_phone is not None else cur["cardSbpPhone"]) or None,
    )
    return await get_staff_payout_profile(user_id)


# ---------------------------------------------------------------------------
# Премии
# ---------------------------------------------------------------------------

def _bonus_row(r) -> dict:
    return {
        "bonusId": int(r["id"]),
        "userId": int(r["user_id"]),
        "amount": int(r["amount"]),
        "paidAmount": int(r["paid_amount"] or 0),
        "reason": r["reason"] or "",
        "note": r["note"],
        "payoutType": r["payout_type"] or "other",
        "status": r["status"],
        "txid": r["txid"],
        "payoutProof": r["payout_proof"],
        "setBy": int(r["set_by"]) if r["set_by"] else None,
        "approvedBy": int(r["approved_by"]) if r["approved_by"] else None,
        "paidBy": int(r["paid_by"]) if r["paid_by"] else None,
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        "approvedAt": r["approved_at"].isoformat() if r["approved_at"] else None,
        "paidAt": r["paid_at"].isoformat() if r["paid_at"] else None,
        "username": r.get("username"),
        "firstName": r.get("first_name"),
        "role": r.get("role"),
    }


async def create_bonus(
    user_id: int, *, amount: int, reason: str, note: str | None,
    payout_type: str, setter_id: int, status: str,
) -> int:
    row = await db.pool.fetchrow(
        """
        INSERT INTO staff_bonuses
            (user_id, amount, reason, note, payout_type, set_by, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        user_id, amount, reason or "", note or None, payout_type, setter_id, status,
    )
    return int(row["id"])


async def list_bonuses(limit: int = 50, status: str | None = None) -> list[dict]:
    if status:
        rows = await db.pool.fetch(
            """
            SELECT b.*, a.username, a.first_name, a.role
            FROM staff_bonuses b
            LEFT JOIN admin_accounts a ON a.user_id = b.user_id
            WHERE b.status = $1
            ORDER BY b.created_at DESC
            LIMIT $2
            """,
            status, limit,
        )
    else:
        rows = await db.pool.fetch(
            """
            SELECT b.*, a.username, a.first_name, a.role
            FROM staff_bonuses b
            LEFT JOIN admin_accounts a ON a.user_id = b.user_id
            ORDER BY b.created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [_bonus_row(r) for r in rows]


async def list_my_bonuses(user_id: int, limit: int = 20) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT b.*, NULL::text AS username, NULL::text AS first_name, NULL::text AS role
        FROM staff_bonuses b
        WHERE b.user_id = $1
        ORDER BY b.created_at DESC
        LIMIT $2
        """,
        user_id, limit,
    )
    return [_bonus_row(r) for r in rows]


async def get_bonus(bonus_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT b.*, a.username, a.first_name, a.role
        FROM staff_bonuses b
        LEFT JOIN admin_accounts a ON a.user_id = b.user_id
        WHERE b.id = $1
        """,
        bonus_id,
    )
    return _bonus_row(row) if row else None


async def approve_bonus(bonus_id: int, owner_id: int) -> bool:
    result = await db.pool.execute(
        """
        UPDATE staff_bonuses
        SET status = 'approved', approved_by = $2, approved_at = NOW(), updated_at = NOW()
        WHERE id = $1 AND status = 'pending_approval'
        """,
        bonus_id, owner_id,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def cancel_bonus(bonus_id: int) -> bool:
    result = await db.pool.execute(
        """
        UPDATE staff_bonuses
        SET status = 'cancelled', updated_at = NOW()
        WHERE id = $1 AND status NOT IN ('paid', 'cancelled')
        """,
        bonus_id,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def add_bonus_payment(
    bonus_id: int, paid_by: int, amount: int, *,
    method: str | None, kind: str, txid: str | None, proof: str | None,
) -> dict | None:
    audit_ev = None
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM staff_bonuses WHERE id = $1 FOR UPDATE",
                bonus_id,
            )
            if not row or row["status"] not in ("approved", "partially_paid"):
                return None
            total = int(row["amount"])
            already = int(row["paid_amount"] or 0)
            remaining = max(0, total - already)
            if remaining <= 0:
                return None
            pay = min(amount, remaining)
            pay_method = method or row["payout_type"]

            if pay_method == "kut":
                audit_ev = await credit_kut_with_audit(
                    conn, int(row["user_id"]), pay,
                    cause="Премия (kut)",
                    event_type="staff_bonus_kut",
                    details={"bonusId": bonus_id, "kind": kind},
                )

            await conn.execute(
                """
                INSERT INTO bonus_payments
                    (bonus_id, user_id, amount, method, kind, txid, proof, paid_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                bonus_id, int(row["user_id"]), pay, pay_method, kind,
                txid or None, proof or None, paid_by,
            )
            new_paid = already + pay
            new_status = "paid" if new_paid >= total else "partially_paid"
            await conn.execute(
                """
                UPDATE staff_bonuses
                SET paid_amount = $2, status = $3,
                    paid_by = $4, paid_at = NOW(),
                    txid = COALESCE($5, txid), payout_proof = COALESCE($6, payout_proof),
                    updated_at = NOW()
                WHERE id = $1
                """,
                bonus_id, new_paid, new_status, paid_by, txid or None, proof or None,
            )
    schedule_kut_audit(audit_ev)
    return {
        "userId": int(row["user_id"]),
        "total": total,
        "paid": new_paid,
        "remaining": max(0, total - new_paid),
        "status": new_status,
        "amount": pay,
    }


async def claim_kut_bonus(user_id: int) -> dict | None:
    """Сотрудник забирает одобренную премию в kut (остаток)."""
    audit_ev = None
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, amount, paid_amount
                FROM staff_bonuses
                WHERE user_id = $1
                  AND status IN ('approved', 'partially_paid')
                  AND payout_type = 'kut'
                  AND amount > COALESCE(paid_amount, 0)
                ORDER BY created_at DESC
                LIMIT 1
                FOR UPDATE
                """,
                user_id,
            )
            if not row:
                return None
            bonus_id = int(row["id"])
            remaining = int(row["amount"]) - int(row["paid_amount"] or 0)
            if remaining <= 0:
                return None
            audit_ev = await credit_kut_with_audit(
                conn, user_id, remaining,
                cause="Премия (kut, самовыдача)",
                event_type="staff_bonus_kut",
                details={"bonusId": bonus_id, "kind": "self_claim"},
            )
            await conn.execute(
                """
                INSERT INTO bonus_payments
                    (bonus_id, user_id, amount, method, kind, txid, paid_by)
                VALUES ($1, $2, $3, 'kut', 'payment', 'kut-self-claim', $2)
                """,
                bonus_id, user_id, remaining,
            )
            await conn.execute(
                """
                UPDATE staff_bonuses
                SET status = 'paid', paid_at = NOW(), paid_by = $2,
                    paid_amount = amount, txid = 'kut-self-claim', updated_at = NOW()
                WHERE id = $1
                """,
                bonus_id, user_id,
            )
    schedule_kut_audit(audit_ev)
    return {"bonusId": bonus_id, "amount": remaining}


# ---------------------------------------------------------------------------
# Шаблоны договоров
# ---------------------------------------------------------------------------

async def list_contract_templates(enabled_only: bool = False) -> list[dict]:
    if enabled_only:
        rows = await db.pool.fetch(
            """
            SELECT * FROM salary_contract_templates
            WHERE enabled = TRUE
            ORDER BY sort_order, id
            """
        )
    else:
        rows = await db.pool.fetch(
            "SELECT * FROM salary_contract_templates ORDER BY sort_order, id"
        )
    return [
        {
            "id": int(r["id"]),
            "name": r["name"],
            "body": r["body"] or "",
            "payoutType": r["payout_type"],
            "enabled": bool(r["enabled"]),
            "sortOrder": int(r["sort_order"] or 0),
            "updatedBy": int(r["updated_by"]) if r["updated_by"] else None,
            "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]


async def upsert_contract_template(
    *,
    template_id: int | None,
    name: str,
    body: str,
    payout_type: str | None,
    enabled: bool,
    sort_order: int,
    updated_by: int,
) -> int:
    if template_id:
        await db.pool.execute(
            """
            UPDATE salary_contract_templates
            SET name = $2, body = $3, payout_type = $4, enabled = $5,
                sort_order = $6, updated_by = $7, updated_at = NOW()
            WHERE id = $1
            """,
            template_id, name, body, payout_type, enabled, sort_order, updated_by,
        )
        return template_id
    row = await db.pool.fetchrow(
        """
        INSERT INTO salary_contract_templates
            (name, body, payout_type, enabled, sort_order, updated_by)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING id
        """,
        name, body, payout_type, enabled, sort_order, updated_by,
    )
    return int(row["id"])


async def delete_contract_template(template_id: int) -> bool:
    result = await db.pool.execute(
        "DELETE FROM salary_contract_templates WHERE id = $1", template_id
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


def render_contract(
    body: str,
    *,
    amount: int,
    staff_name: str,
    staff_username: str,
    payout_type: str,
    details: dict[str, str],
    period_label_text: str = "",
) -> str:
    """Простая подстановка плейсхолдеров в шаблон договора."""
    repl = {
        "{{amount}}": str(amount),
        "{{name}}": staff_name or "",
        "{{username}}": staff_username or "",
        "{{payout_type}}": payout_type or "",
        "{{period}}": period_label_text or "",
        "{{crypto_network}}": details.get("cryptoNetwork", ""),
        "{{crypto_address}}": details.get("cryptoAddress", ""),
        "{{card_bank}}": details.get("cardBank", ""),
        "{{card_number}}": details.get("cardNumber", ""),
        "{{card_holder}}": details.get("cardHolder", ""),
        "{{card_sbp}}": details.get("cardSbpPhone", ""),
        "{{stars_username}}": details.get("starsUsername", ""),
    }
    out = body or ""
    for k, v in repl.items():
        out = out.replace(k, v)
    return out
