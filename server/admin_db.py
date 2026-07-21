"""PostgreSQL: admin accounts и pending TOTP setup."""

from __future__ import annotations

from datetime import timedelta

from asyncpg.exceptions import UniqueViolationError

from db import db
from farm_logic import now


async def get_admin_account(user_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT user_id, username, first_name, registered_at, role, status, login_key
        FROM admin_accounts
        WHERE user_id = $1
        ORDER BY registered_at DESC
        LIMIT 1
        """,
        user_id,
    )
    return dict(row) if row else None


async def get_admin_totp_secret(user_id: int) -> str | None:
    return await db.pool.fetchval(
        """
        SELECT totp_secret FROM admin_accounts
        WHERE user_id = $1
        ORDER BY registered_at DESC
        LIMIT 1
        """,
        user_id,
    )


async def dedupe_admin_accounts() -> int:
    """Удаляет дубликаты admin_accounts (если PK на user_id отсутствует в старой БД)."""
    result = await db.pool.execute(
        """
        DELETE FROM admin_accounts a
        USING admin_accounts b
        WHERE a.user_id = b.user_id
          AND a.ctid < b.ctid
        """
    )
    try:
        return int(str(result).split()[-1])
    except (ValueError, IndexError):
        return 0


async def create_admin_account(
    user_id: int,
    totp_secret: str,
    *,
    username: str | None,
    first_name: str | None,
    role: str = "applicant",
    status: str = "pending",
) -> None:
    await db.pool.execute(
        """
        INSERT INTO admin_accounts (user_id, totp_secret, username, first_name, role, status)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        user_id,
        totp_secret,
        username,
        first_name,
        role,
        status,
    )


async def refresh_owner_totp(
    setup_token: str,
    user_id: int,
    totp_secret: str,
    *,
    username: str | None,
    first_name: str | None,
) -> None:
    """Перепривязка TOTP владельца (если в БД был битый секрет или устаревший QR)."""
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE admin_accounts
                SET totp_secret = $2,
                    username = COALESCE($3, username),
                    first_name = COALESCE($4, first_name),
                    role = 'owner',
                    status = 'active'
                WHERE user_id = $1
                """,
                user_id,
                totp_secret,
                username,
                first_name,
            )
            await conn.execute(
                "DELETE FROM admin_register_pending WHERE setup_token = $1",
                setup_token,
            )


async def confirm_admin_registration(
    setup_token: str,
    user_id: int,
    totp_secret: str,
    *,
    username: str | None,
    first_name: str | None,
    role: str,
    status: str,
    invite_token: str | None,
) -> bool:
    """Атомарно: помечает инвайт использованным + создаёт аккаунт + удаляет pending.

    Возвращает False если инвайт уже использован (гонка), True при успехе.
    """
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            if invite_token:
                result = await conn.execute(
                    """
                    UPDATE admin_invite_tokens
                    SET used_by = $2, used_at = NOW()
                    WHERE token = $1
                      AND used_by IS NULL
                      AND revoked_at IS NULL
                    """,
                    invite_token,
                    user_id,
                )
                if result.split()[-1] == "0":
                    return False
            await conn.execute(
                """
                INSERT INTO admin_accounts (user_id, totp_secret, username, first_name, role, status, login_key)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                user_id, totp_secret, username, first_name, role, status, invite_token,
            )
            await conn.execute(
                "DELETE FROM admin_register_pending WHERE setup_token = $1",
                setup_token,
            )
    return True


async def save_pending_registration(
    setup_token: str,
    user_id: int,
    totp_secret: str,
    key_type: str = "staff",
    invite_token: str | None = None,
) -> None:
    expires_at = now() + timedelta(minutes=15)
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM admin_register_pending WHERE user_id = $1",
                user_id,
            )
            await conn.execute(
                """
                INSERT INTO admin_register_pending
                    (setup_token, user_id, totp_secret, expires_at, key_type, invite_token)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                setup_token,
                user_id,
                totp_secret,
                expires_at,
                key_type,
                invite_token,
            )


async def get_pending_registration(setup_token: str, user_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT setup_token, user_id, totp_secret, expires_at, key_type, invite_token
        FROM admin_register_pending
        WHERE setup_token = $1 AND user_id = $2
        """,
        setup_token,
        user_id,
    )
    if not row:
        return None
    if row["expires_at"] < now():
        await db.pool.execute(
            "DELETE FROM admin_register_pending WHERE setup_token = $1",
            setup_token,
        )
        return None
    return dict(row)


async def get_pending_registration_by_token(setup_token: str) -> dict | None:
    """Pending только по setupToken (для диагностики несовпадения user_id)."""
    row = await db.pool.fetchrow(
        """
        SELECT setup_token, user_id, totp_secret, expires_at, key_type, invite_token
        FROM admin_register_pending
        WHERE setup_token = $1
        """,
        setup_token,
    )
    if not row:
        return None
    if row["expires_at"] < now():
        await db.pool.execute(
            "DELETE FROM admin_register_pending WHERE setup_token = $1",
            setup_token,
        )
        return None
    return dict(row)


async def update_pending_totp_secret(setup_token: str, user_id: int, totp_secret: str) -> None:
    await db.pool.execute(
        """
        UPDATE admin_register_pending
        SET totp_secret = $3
        WHERE setup_token = $1 AND user_id = $2
        """,
        setup_token,
        user_id,
        totp_secret,
    )


async def delete_pending_registration(setup_token: str) -> None:
    await db.pool.execute(
        "DELETE FROM admin_register_pending WHERE setup_token = $1",
        setup_token,
    )


async def cleanup_expired_pending() -> None:
    await db.pool.execute(
        "DELETE FROM admin_register_pending WHERE expires_at < NOW()",
    )


async def get_latest_application(user_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT id, status, created_at, reviewed_at
        FROM admin_applications
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        user_id,
    )
    return dict(row) if row else None


async def create_application(
    user_id: int,
    *,
    username: str | None,
    first_name: str | None,
    answers: dict,
    payout_type: str | None,
    payout_details: str | None,
) -> bool:
    """Создаёт заявку кандидата. Возвращает False, если pending-заявка уже есть."""
    import json

    try:
        await db.pool.execute(
            """
            INSERT INTO admin_applications
                (user_id, username, first_name, answers, payout_type, payout_details)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6)
            """,
            user_id,
            username,
            first_name,
            json.dumps(answers, ensure_ascii=False),
            payout_type,
            payout_details,
        )
    except UniqueViolationError:
        return False
    return True


def _parse_answers(value):
    import json

    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}


async def list_applications(status: str = "pending") -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT id, user_id, username, first_name, answers,
               payout_type, payout_details, status, assigned_role,
               review_note, reviewed_by, reviewed_at, created_at
        FROM admin_applications
        WHERE status = $1
        ORDER BY created_at DESC
        LIMIT 200
        """,
        status,
    )
    return [
        {
            "id": int(r["id"]),
            "userId": int(r["user_id"]),
            "username": r["username"],
            "firstName": r["first_name"],
            "answers": _parse_answers(r["answers"]),
            "payoutType": r["payout_type"],
            "payoutDetails": r["payout_details"],
            "status": r["status"],
            "assignedRole": r["assigned_role"],
            "reviewNote": r["review_note"],
            "reviewedBy": int(r["reviewed_by"]) if r["reviewed_by"] else None,
            "reviewedAt": r["reviewed_at"].isoformat() if r["reviewed_at"] else None,
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def approve_application(application_id: int, role: str, reviewer_id: int) -> dict | None:
    """Одобряет заявку и активирует аккаунт с выданной ролью. Транзакция."""
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            app_row = await conn.fetchrow(
                "SELECT id, user_id, status FROM admin_applications WHERE id = $1 FOR UPDATE",
                application_id,
            )
            if not app_row or app_row["status"] != "pending":
                return None
            user_id = int(app_row["user_id"])

            await conn.execute(
                """
                UPDATE admin_applications
                SET status = 'approved', assigned_role = $2,
                    reviewed_by = $3, reviewed_at = NOW(), updated_at = NOW()
                WHERE id = $1
                """,
                application_id,
                role,
                reviewer_id,
            )
            await conn.execute(
                """
                UPDATE admin_accounts
                SET role = $2, status = 'active', hired_at = NOW(), hired_by = $3
                WHERE user_id = $1
                """,
                user_id,
                role,
                reviewer_id,
            )
    return {"userId": user_id, "role": role}


async def reject_application(application_id: int, reason: str, reviewer_id: int) -> dict | None:
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            app_row = await conn.fetchrow(
                "SELECT id, user_id, status FROM admin_applications WHERE id = $1 FOR UPDATE",
                application_id,
            )
            if not app_row or app_row["status"] != "pending":
                return None
            user_id = int(app_row["user_id"])

            await conn.execute(
                """
                UPDATE admin_applications
                SET status = 'rejected', review_note = $2,
                    reviewed_by = $3, reviewed_at = NOW(), updated_at = NOW()
                WHERE id = $1
                """,
                application_id,
                reason or None,
                reviewer_id,
            )
            # Удаляем admin-аккаунт кандидата, чтобы он мог подать заявку заново.
            # Сама заявка (status='rejected') остаётся в истории.
            await conn.execute(
                "DELETE FROM admin_accounts WHERE user_id = $1 AND role = 'applicant'",
                user_id,
            )
            await conn.execute(
                "DELETE FROM admin_register_pending WHERE user_id = $1",
                user_id,
            )
    return {"userId": user_id}


async def list_staff_members() -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT user_id, username, first_name, role, status,
               hired_at, last_seen_at, curator_id, availability, availability_until,
               curator_username, curator_first_name, active_strikes
        FROM (
            SELECT DISTINCT ON (a.user_id)
                   a.user_id, a.username, a.first_name, a.role, a.status,
                   a.hired_at, a.last_seen_at, a.curator_id, a.availability, a.availability_until,
                   c.username AS curator_username, c.first_name AS curator_first_name,
                   (SELECT COUNT(*) FROM staff_strikes st
                      WHERE st.user_id = a.user_id AND st.expires_at > NOW()) AS active_strikes
            FROM admin_accounts a
            LEFT JOIN admin_accounts c ON c.user_id = a.curator_id
            WHERE a.role <> 'applicant'
            ORDER BY a.user_id
        ) sub
        ORDER BY
            CASE role
                WHEN 'owner' THEN 0
                WHEN 'senior_admin' THEN 1
                WHEN 'junior_admin' THEN 2
                WHEN 'moderator' THEN 3
                ELSE 4
            END,
            hired_at NULLS LAST
        """,
    )
    return [
        {
            "userId": int(r["user_id"]),
            "username": r["username"],
            "firstName": r["first_name"],
            "role": r["role"],
            "status": r["status"],
            "hiredAt": r["hired_at"].isoformat() if r["hired_at"] else None,
            "lastSeenAt": r["last_seen_at"].isoformat() if r["last_seen_at"] else None,
            "curatorId": int(r["curator_id"]) if r["curator_id"] else None,
            "curatorName": (
                r["curator_first_name"]
                or (f"@{r['curator_username']}" if r["curator_username"] else None)
            ),
            "availability": r["availability"] or "active",
            "availabilityUntil": r["availability_until"].isoformat() if r["availability_until"] else None,
            "activeStrikes": int(r["active_strikes"] or 0),
        }
        for r in rows
    ]


async def change_member_role(user_id: int, new_role: str, changed_by: int, reason: str) -> dict | None:
    """Меняет роль сотрудника (повышение/понижение). Владельца не трогаем. Пишет историю."""
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT role FROM admin_accounts WHERE user_id = $1 FOR UPDATE",
                user_id,
            )
            if not row or row["role"] == "owner":
                return None
            old_role = row["role"]
            if old_role == new_role:
                return None
            await conn.execute(
                "UPDATE admin_accounts SET role = $2 WHERE user_id = $1",
                user_id, new_role,
            )
            await conn.execute(
                """
                INSERT INTO staff_role_history (user_id, old_role, new_role, changed_by, reason)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id, old_role, new_role, changed_by, reason or None,
            )
    return {"userId": user_id, "oldRole": old_role, "newRole": new_role}


async def list_role_history(user_id: int, limit: int = 50) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT id, old_role, new_role, changed_by, reason, created_at
        FROM staff_role_history
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id, limit,
    )
    return [
        {
            "id": int(r["id"]),
            "oldRole": r["old_role"],
            "newRole": r["new_role"],
            "changedBy": int(r["changed_by"]) if r["changed_by"] else None,
            "reason": r["reason"],
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def set_member_curator(user_id: int, curator_id: int | None) -> bool:
    result = await db.pool.execute(
        "UPDATE admin_accounts SET curator_id = $2 WHERE user_id = $1 AND role <> 'applicant'",
        user_id, curator_id,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def suspend_member(user_id: int, reviewer_id: int) -> bool:
    """Отстраняет сотрудника (роль сохраняется, меняется статус). Владельца нельзя."""
    result = await db.pool.execute(
        """
        UPDATE admin_accounts
        SET status = 'suspended',
            force_reauth_at = NOW(), session_fingerprint = NULL
        WHERE user_id = $1 AND role <> 'owner' AND status = 'active'
        """,
        user_id,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def unsuspend_member(user_id: int, reviewer_id: int) -> bool:
    """Возвращает отстранённого сотрудника к работе (status active, роль не тронута)."""
    result = await db.pool.execute(
        """
        UPDATE admin_accounts
        SET status = 'active'
        WHERE user_id = $1 AND status = 'suspended'
        """,
        user_id,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def delete_suspended_member(user_id: int) -> bool:
    """Полностью удаляет отстранённого сотрудника из БД. Только owner."""
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            # Проверяем что аккаунт существует и отстранён
            row = await conn.fetchrow(
                "SELECT status FROM admin_accounts WHERE user_id = $1",
                user_id,
            )
            if not row or row["status"] != "suspended":
                return False

            # Удаляем все связанные данные
            await conn.execute("DELETE FROM staff_strikes WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM staff_notes WHERE staff_user_id = $1", user_id)
            await conn.execute("DELETE FROM staff_shifts WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM staff_role_history WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM staff_actions WHERE admin_user_id = $1", user_id)
            await conn.execute(
                "DELETE FROM staff_complaints WHERE target_admin_id = $1 OR created_by = $1",
                user_id,
            )
            # salary_payments и salary_appeals каскадно удалятся через FK,
            # иначе удаляем явно
            await conn.execute(
                """
                DELETE FROM salary_payments
                WHERE salary_id IN (SELECT id FROM staff_salaries WHERE user_id = $1)
                """,
                user_id,
            )
            await conn.execute(
                "DELETE FROM salary_appeals WHERE user_id = $1",
                user_id,
            )
            await conn.execute("DELETE FROM staff_salaries WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM admin_activity WHERE admin_user_id = $1", user_id)
            await conn.execute("DELETE FROM admin_applications WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM admin_register_pending WHERE user_id = $1", user_id)
            # Инвайты созданные этим юзером оставляем (аудит), просто обнуляем created_by
            await conn.execute(
                "UPDATE admin_invite_tokens SET created_by = NULL WHERE created_by = $1",
                user_id,
            )
            await conn.execute("DELETE FROM admin_accounts WHERE user_id = $1", user_id)
    return True


def current_week_start():
    """Понедельник текущей недели (date)."""
    today = now().date()
    return today - timedelta(days=today.weekday())


def _salary_row(r) -> dict:
    return {
        "salaryId": int(r["salary_id"]) if r["salary_id"] is not None else None,
        "amount": int(r["amount"]) if r["amount"] is not None else None,
        "paidAmount": int(r["paid_amount"]) if r["paid_amount"] is not None else 0,
        "baseAmount": int(r["base_amount"]) if r["base_amount"] is not None else 0,
        "coefficient": float(r["coefficient"]) if r["coefficient"] is not None else 1.0,
        "bonus": int(r["bonus"]) if r["bonus"] is not None else 0,
        "bonusReason": r["bonus_reason"],
        "penalty": int(r["penalty"]) if r["penalty"] is not None else 0,
        "penaltyReason": r["penalty_reason"],
        "txid": r["txid"],
        "payoutProof": r["payout_proof"],
        "status": r["status"],
        "payoutType": r.get("payout_type") or "other",
        "note": r["note"],
        "setBy": int(r["set_by"]) if r["set_by"] else None,
        "approvedBy": int(r["approved_by"]) if r["approved_by"] else None,
        "paidBy": int(r["paid_by"]) if r["paid_by"] else None,
        "approvedAt": r["approved_at"].isoformat() if r["approved_at"] else None,
        "paidAt": r["paid_at"].isoformat() if r["paid_at"] else None,
    }


async def list_salaries_for_week(week_start) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT a.user_id, a.username, a.first_name, a.role,
               a.payout_type, a.payout_details,
               s.id AS salary_id, s.amount, s.paid_amount, s.status, s.note,
               s.base_amount, s.coefficient, s.bonus, s.bonus_reason,
               s.penalty, s.penalty_reason, s.txid, s.payout_proof,
               s.payout_type, s.set_by, s.approved_by, s.paid_by, s.approved_at, s.paid_at
        FROM admin_accounts a
        LEFT JOIN staff_salaries s
          ON s.user_id = a.user_id AND s.week_start = $1
        WHERE a.status = 'active'
          AND a.role IN ('senior_admin', 'junior_admin', 'moderator')
        ORDER BY
            CASE a.role
                WHEN 'senior_admin' THEN 0
                WHEN 'junior_admin' THEN 1
                WHEN 'moderator' THEN 2
                ELSE 3
            END,
            a.user_id
        """,
        week_start,
    )
    return [
        {
            "userId": int(r["user_id"]),
            "username": r["username"],
            "firstName": r["first_name"],
            "role": r["role"],
            "payoutType": r["payout_type"],
            "payoutDetails": r["payout_details"],
            "salary": _salary_row(r) if r["salary_id"] is not None else None,
        }
        for r in rows
    ]


def compute_salary_total(base: int, coefficient: float, bonus: int, penalty: int) -> int:
    """Итог к выплате = ставка × коэффициент + бонус − штраф (не ниже 0)."""
    total = round(base * coefficient) + bonus - penalty
    return max(0, int(total))


async def upsert_salary(
    user_id: int, week_start, *, base: int, coefficient: float,
    bonus: int, bonus_reason: str | None, penalty: int, penalty_reason: str | None,
    note: str | None, setter_id: int, status: str,
    payout_type: str = "other",
) -> int | None:
    """Создаёт/обновляет зарплату на неделю. Не трогает уже выплаченную."""
    amount = compute_salary_total(base, coefficient, bonus, penalty)
    row = await db.pool.fetchrow(
        """
        INSERT INTO staff_salaries
            (user_id, week_start, amount, base_amount, coefficient,
             bonus, bonus_reason, penalty, penalty_reason, note, set_by, status, payout_type)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        ON CONFLICT (user_id, week_start) DO UPDATE
        SET amount = EXCLUDED.amount,
            base_amount = EXCLUDED.base_amount,
            coefficient = EXCLUDED.coefficient,
            bonus = EXCLUDED.bonus,
            bonus_reason = EXCLUDED.bonus_reason,
            penalty = EXCLUDED.penalty,
            penalty_reason = EXCLUDED.penalty_reason,
            note = EXCLUDED.note,
            set_by = EXCLUDED.set_by,
            status = EXCLUDED.status,
            payout_type = EXCLUDED.payout_type,
            approved_by = NULL, approved_at = NULL,
            txid = NULL, payout_proof = NULL,
            updated_at = NOW()
        WHERE staff_salaries.status <> 'paid'
        RETURNING id
        """,
        user_id, week_start, amount, base, coefficient,
        bonus, bonus_reason or None, penalty, penalty_reason or None,
        note or None, setter_id, status, payout_type,
    )
    return int(row["id"]) if row else None


async def claim_kut_salary(user_id: int) -> dict | None:
    """Сотрудник забирает одобренную ЗП в kut на свой игровой баланс."""
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, amount
                FROM staff_salaries
                WHERE user_id = $1
                  AND status = 'approved'
                  AND payout_type = 'kut'
                ORDER BY week_start DESC
                LIMIT 1
                FOR UPDATE
                """,
                user_id,
            )
            if not row:
                return None
            salary_id = int(row["id"])
            amount = int(row["amount"])
            # Начисляем kut на игровой баланс
            await conn.execute(
                "UPDATE users SET balance = balance + $2 WHERE user_id = $1",
                user_id, amount,
            )
            # Помечаем выплаченной
            await conn.execute(
                """
                UPDATE staff_salaries
                SET status = 'paid', paid_at = NOW(), paid_by = $2,
                    paid_amount = amount, txid = 'kut-self-claim', updated_at = NOW()
                WHERE id = $1
                """,
                salary_id, user_id,
            )
    return {"salaryId": salary_id, "amount": amount}


async def approve_salary(salary_id: int, owner_id: int) -> bool:
    result = await db.pool.execute(
        """
        UPDATE staff_salaries
        SET status = 'approved', approved_by = $2, approved_at = NOW(), updated_at = NOW()
        WHERE id = $1 AND status = 'pending_approval'
        """,
        salary_id, owner_id,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def pay_salary(salary_id: int, owner_id: int, txid: str | None, proof: str | None) -> bool:
    result = await db.pool.execute(
        """
        UPDATE staff_salaries
        SET status = 'paid', paid_by = $2, paid_at = NOW(),
            txid = $3, payout_proof = $4, updated_at = NOW()
        WHERE id = $1 AND status = 'approved'
        """,
        salary_id, owner_id, txid or None, proof or None,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def cancel_salary(salary_id: int) -> bool:
    """Снимает (аннулирует) начисление, если оно ещё не выплачено."""
    result = await db.pool.execute(
        """
        UPDATE staff_salaries
        SET status = 'cancelled', updated_at = NOW()
        WHERE id = $1 AND status <> 'paid'
        """,
        salary_id,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def get_salary_full(salary_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT s.id, s.user_id, s.amount, s.paid_amount, s.status, a.payout_type
        FROM staff_salaries s
        LEFT JOIN admin_accounts a ON a.user_id = s.user_id
        WHERE s.id = $1
        """,
        salary_id,
    )
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "userId": int(row["user_id"]),
        "amount": int(row["amount"]),
        "paidAmount": int(row["paid_amount"] or 0),
        "status": row["status"],
        "payoutType": row["payout_type"],
    }


async def get_salary_owner(salary_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        "SELECT id, user_id, status FROM staff_salaries WHERE id = $1",
        salary_id,
    )
    return dict(row) if row else None


async def list_my_salaries(user_id: int, limit: int = 8) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT s.id, s.week_start, s.amount, s.status, s.note,
               s.base_amount, s.coefficient, s.bonus, s.bonus_reason,
               s.penalty, s.penalty_reason, s.txid, s.payout_proof,
               s.payout_type, s.approved_at, s.paid_at,
               a.id AS appeal_id, a.status AS appeal_status
        FROM staff_salaries s
        LEFT JOIN salary_appeals a ON a.salary_id = s.id
        WHERE s.user_id = $1
        ORDER BY s.week_start DESC
        LIMIT $2
        """,
        user_id, limit,
    )
    return [
        {
            "salaryId": int(r["id"]),
            "weekStart": r["week_start"].isoformat() if r["week_start"] else None,
            "amount": int(r["amount"]),
            "baseAmount": int(r["base_amount"]) if r["base_amount"] is not None else 0,
            "coefficient": float(r["coefficient"]) if r["coefficient"] is not None else 1.0,
            "bonus": int(r["bonus"]) if r["bonus"] is not None else 0,
            "bonusReason": r["bonus_reason"],
            "penalty": int(r["penalty"]) if r["penalty"] is not None else 0,
            "penaltyReason": r["penalty_reason"],
            "txid": r["txid"],
            "payoutProof": r["payout_proof"],
            "status": r["status"],
            "payoutType": r["payout_type"] or "other",
            "note": r["note"],
            "approvedAt": r["approved_at"].isoformat() if r["approved_at"] else None,
            "paidAt": r["paid_at"].isoformat() if r["paid_at"] else None,
            "appealId": int(r["appeal_id"]) if r["appeal_id"] else None,
            "appealStatus": r["appeal_status"],
        }
        for r in rows
    ]


async def create_salary_appeal(salary_id: int, user_id: int, reason: str) -> bool:
    """Создаёт апелляцию, если зарплата принадлежит пользователю и апелляции ещё нет."""
    owner = await db.pool.fetchrow(
        "SELECT user_id FROM staff_salaries WHERE id = $1",
        salary_id,
    )
    if not owner or int(owner["user_id"]) != user_id:
        return False
    exists = await db.pool.fetchval(
        "SELECT 1 FROM salary_appeals WHERE salary_id = $1 AND status = 'open'",
        salary_id,
    )
    if exists:
        return False
    await db.pool.execute(
        """
        INSERT INTO salary_appeals (salary_id, user_id, reason)
        VALUES ($1, $2, $3)
        """,
        salary_id, user_id, reason or "",
    )
    return True


async def list_open_appeals() -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT ap.id, ap.salary_id, ap.user_id, ap.reason, ap.created_at,
               s.amount, s.week_start, s.status AS salary_status,
               a.username, a.first_name, a.role
        FROM salary_appeals ap
        JOIN staff_salaries s ON s.id = ap.salary_id
        LEFT JOIN admin_accounts a ON a.user_id = ap.user_id
        WHERE ap.status = 'open'
        ORDER BY ap.created_at DESC
        """,
    )
    return [
        {
            "appealId": int(r["id"]),
            "salaryId": int(r["salary_id"]),
            "userId": int(r["user_id"]),
            "username": r["username"],
            "firstName": r["first_name"],
            "role": r["role"],
            "reason": r["reason"],
            "amount": int(r["amount"]),
            "weekStart": r["week_start"].isoformat() if r["week_start"] else None,
            "salaryStatus": r["salary_status"],
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def resolve_salary_appeal(appeal_id: int, resolution: str, reviewer_id: int) -> int | None:
    """Закрывает апелляцию. Возвращает user_id заявителя или None."""
    row = await db.pool.fetchrow(
        """
        UPDATE salary_appeals
        SET status = 'resolved', resolution = $2, reviewed_by = $3, reviewed_at = NOW()
        WHERE id = $1 AND status = 'open'
        RETURNING user_id
        """,
        appeal_id, resolution or None, reviewer_id,
    )
    return int(row["user_id"]) if row else None


async def log_staff_action(
    admin_user_id: int, action_type: str, target_player_id: int | None,
    reason: str, evidence: str,
    *,
    admin_name: str = "",
    target_name: str = "",
    proof_media_id: str | None = None,
    duration_minutes: int | None = None,
    scope: str | None = None,
    chat_id: int | None = None,
    proof_bot_token: str | None = None,
) -> None:
    # proof_bot_token — токен бота, которым загружен пруф (см. schema.sql). Храним
    # рядом с file_id, чтобы архив всегда скачал фото именно этим ботом. Только
    # сервер: в broadcast/ответы API токен НЕ попадает.
    await db.pool.execute(
        """
        INSERT INTO staff_actions
            (admin_user_id, admin_name, action_type, target_player_id, target_name,
             reason, evidence, proof_media_id, duration_minutes, chat_id, scope,
             proof_bot_token)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """,
        admin_user_id, admin_name or "", action_type, target_player_id, target_name or "",
        reason or "", evidence or "", proof_media_id, duration_minutes, chat_id, scope,
        proof_bot_token,
    )

    import asyncio
    from admin_ws import broadcast_to_admins
    asyncio.create_task(broadcast_to_admins({
        "event": "new_moderation_log",
        "data": {
            "actionType": action_type,
            "adminId": admin_user_id,
            "adminName": admin_name or "",
            "targetId": target_player_id,
            "targetName": target_name or "",
            "reason": reason or "",
            "proofMediaId": proof_media_id,
            "durationMinutes": duration_minutes,
            "scope": scope,
            "chatId": chat_id,
        },
    }))


async def list_staff_actions(admin_user_id: int, limit: int = 50) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT id, action_type, target_player_id, reason, evidence, created_at
        FROM staff_actions
        WHERE admin_user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        admin_user_id, limit,
    )
    return [
        {
            "id": int(r["id"]),
            "actionType": r["action_type"],
            "targetPlayerId": int(r["target_player_id"]) if r["target_player_id"] else None,
            "reason": r["reason"],
            "evidence": r["evidence"],
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


def _complaint_row(r) -> dict:
    return {
        "id": int(r["id"]),
        "targetAdminId": int(r["target_admin_id"]) if r["target_admin_id"] else None,
        "targetUsername": r["username"],
        "targetFirstName": r["first_name"],
        "targetRole": r["role"],
        "subject": r["subject"],
        "reason": r["reason"],
        "status": r["status"],
        "evidence": r["evidence"],
        "resolution": r["resolution"],
        "source": r["source"],
        "complainantPlayerId": int(r["complainant_player_id"]) if r["complainant_player_id"] else None,
        "createdBy": int(r["created_by"]) if r["created_by"] else None,
        "takenBy": int(r["taken_by"]) if r["taken_by"] else None,
        "resolvedBy": int(r["resolved_by"]) if r["resolved_by"] else None,
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        "takenAt": r["taken_at"].isoformat() if r["taken_at"] else None,
        "resolvedAt": r["resolved_at"].isoformat() if r["resolved_at"] else None,
    }


_COMPLAINT_SELECT = """
    SELECT c.id, c.target_admin_id, c.subject, c.reason, c.status, c.evidence,
           c.resolution, c.source, c.complainant_player_id,
           c.created_by, c.taken_by, c.resolved_by,
           c.created_at, c.taken_at, c.resolved_at,
           a.username, a.first_name, a.role
    FROM staff_complaints c
    LEFT JOIN admin_accounts a ON a.user_id = c.target_admin_id
"""


async def create_complaint(target_admin_id: int, subject: str, reason: str, created_by: int) -> int:
    row = await db.pool.fetchrow(
        """
        INSERT INTO staff_complaints (target_admin_id, subject, reason, created_by, source)
        VALUES ($1, $2, $3, $4, 'staff')
        RETURNING id
        """,
        target_admin_id, subject or "", reason or "", created_by,
    )
    return int(row["id"])


async def create_player_complaint(
    complainant_player_id: int, target_admin_id: int | None, subject: str, reason: str,
) -> int:
    row = await db.pool.fetchrow(
        """
        INSERT INTO staff_complaints
            (target_admin_id, subject, reason, source, complainant_player_id)
        VALUES ($1, $2, $3, 'player', $4)
        RETURNING id
        """,
        target_admin_id, subject or "", reason or "", complainant_player_id,
    )
    return int(row["id"])


async def list_complaints(status: str | None = None) -> list[dict]:
    if status:
        rows = await db.pool.fetch(
            _COMPLAINT_SELECT + " WHERE c.status = $1 ORDER BY c.created_at DESC LIMIT 200",
            status,
        )
    else:
        rows = await db.pool.fetch(
            _COMPLAINT_SELECT + " ORDER BY c.created_at DESC LIMIT 200",
        )
    return [_complaint_row(r) for r in rows]


async def list_complaints_for_target(target_admin_id: int) -> list[dict]:
    rows = await db.pool.fetch(
        _COMPLAINT_SELECT
        + " WHERE c.target_admin_id = $1 AND c.status <> 'resolved' ORDER BY c.created_at DESC",
        target_admin_id,
    )
    return [_complaint_row(r) for r in rows]


async def take_complaint(complaint_id: int, owner_id: int) -> tuple[bool, int | None]:
    """Берёт жалобу в работу. Возвращает (успех, target_admin_id|None)."""
    row = await db.pool.fetchrow(
        """
        UPDATE staff_complaints
        SET status = 'in_progress', taken_by = $2, taken_at = NOW()
        WHERE id = $1 AND status = 'open'
        RETURNING target_admin_id
        """,
        complaint_id, owner_id,
    )
    if not row:
        return False, None
    return True, int(row["target_admin_id"]) if row["target_admin_id"] else None


async def submit_complaint_evidence(complaint_id: int, target_admin_id: int, evidence: str) -> bool:
    """Модератор прикладывает доказательства к жалобе на себя (в работе)."""
    result = await db.pool.execute(
        """
        UPDATE staff_complaints
        SET evidence = $3
        WHERE id = $1 AND target_admin_id = $2 AND status = 'in_progress'
        """,
        complaint_id, target_admin_id, evidence or "",
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def resolve_complaint(complaint_id: int, resolution: str, owner_id: int) -> tuple[bool, int | None]:
    """Закрывает жалобу. Возвращает (успех, target_admin_id|None)."""
    row = await db.pool.fetchrow(
        """
        UPDATE staff_complaints
        SET status = 'resolved', resolution = $2, resolved_by = $3, resolved_at = NOW()
        WHERE id = $1 AND status <> 'resolved'
        RETURNING target_admin_id
        """,
        complaint_id, resolution or None, owner_id,
    )
    if not row:
        return False, None
    return True, int(row["target_admin_id"]) if row["target_admin_id"] else None


# ---------------------------------------------------------------------------
# Активность администраторов (часы онлайн)
# ---------------------------------------------------------------------------

async def record_admin_activity(user_id: int) -> None:
    """Фиксирует 10-минутный слот присутствия (идемпотентно)."""
    try:
        await db.pool.execute(
            """
            INSERT INTO admin_activity (admin_user_id, slot)
            VALUES ($1, to_timestamp(floor(extract(epoch from now()) / 600) * 600))
            ON CONFLICT DO NOTHING
            """,
            user_id,
        )
    except Exception:
        pass


async def get_online_minutes(user_id: int, since) -> int:
    cnt = await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM admin_activity WHERE admin_user_id = $1 AND slot >= $2",
        user_id, since,
    )
    return int(cnt or 0) * 10


# ---------------------------------------------------------------------------
# Выплаты: частичная / аванс, реестр, долги
# ---------------------------------------------------------------------------

async def add_salary_payment(
    salary_id: int, paid_by: int, amount: int, *,
    method: str | None, kind: str, txid: str | None, proof: str | None,
) -> dict | None:
    """Добавляет выплату (полную/частичную/аванс). Возвращает итог или None."""
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT s.user_id, s.amount, s.paid_amount, s.status, a.payout_type
                FROM staff_salaries s
                LEFT JOIN admin_accounts a ON a.user_id = s.user_id
                WHERE s.id = $1 FOR UPDATE OF s
                """,
                salary_id,
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

            await conn.execute(
                """
                INSERT INTO salary_payments
                    (salary_id, user_id, amount, method, kind, txid, proof, paid_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                salary_id, int(row["user_id"]), pay, pay_method, kind,
                txid or None, proof or None, paid_by,
            )
            new_paid = already + pay
            new_status = "paid" if new_paid >= total else "partially_paid"
            await conn.execute(
                """
                UPDATE staff_salaries
                SET paid_amount = $2, status = $3,
                    paid_by = $4, paid_at = NOW(),
                    txid = COALESCE($5, txid), payout_proof = COALESCE($6, payout_proof),
                    updated_at = NOW()
                WHERE id = $1
                """,
                salary_id, new_paid, new_status, paid_by, txid or None, proof or None,
            )
    return {
        "userId": int(row["user_id"]),
        "total": total,
        "paid": new_paid,
        "remaining": max(0, total - new_paid),
        "status": new_status,
        "amount": pay,
    }


async def list_payments(date_from, date_to, user_id: int | None = None) -> dict:
    """Реестр выплат за период (+сводка по методам и по сотрудникам)."""
    params = [date_from, date_to]
    where = "p.paid_at >= $1 AND p.paid_at < $2"
    if user_id:
        params.append(user_id)
        where += f" AND p.user_id = ${len(params)}"
    rows = await db.pool.fetch(
        f"""
        SELECT p.id, p.salary_id, p.user_id, p.amount, p.method, p.kind,
               p.txid, p.paid_by, p.paid_at,
               a.username, a.first_name, a.role
        FROM salary_payments p
        LEFT JOIN admin_accounts a ON a.user_id = p.user_id
        WHERE {where}
        ORDER BY p.paid_at DESC
        LIMIT 1000
        """,
        *params,
    )
    items = [
        {
            "id": int(r["id"]),
            "salaryId": int(r["salary_id"]),
            "userId": int(r["user_id"]),
            "username": r["username"],
            "firstName": r["first_name"],
            "role": r["role"],
            "amount": int(r["amount"]),
            "method": r["method"],
            "kind": r["kind"],
            "txid": r["txid"],
            "paidBy": int(r["paid_by"]) if r["paid_by"] else None,
            "paidAt": r["paid_at"].isoformat() if r["paid_at"] else None,
        }
        for r in rows
    ]
    by_method: dict[str, int] = {}
    by_user: dict[int, int] = {}
    total = 0
    for it in items:
        total += it["amount"]
        by_method[it["method"] or "—"] = by_method.get(it["method"] or "—", 0) + it["amount"]
        by_user[it["userId"]] = by_user.get(it["userId"], 0) + it["amount"]
    return {"items": items, "total": total, "byMethod": by_method, "byUser": by_user}


async def list_unpaid(week_start) -> list[dict]:
    """Долги: активный стафф без полной выплаты за текущую неделю + старые невыплаченные."""
    rows = await db.pool.fetch(
        """
        SELECT a.user_id, a.username, a.first_name, a.role,
               s.id AS salary_id, s.amount, s.paid_amount, s.status, s.week_start
        FROM admin_accounts a
        LEFT JOIN staff_salaries s
          ON s.user_id = a.user_id AND s.week_start = $1
        WHERE a.status = 'active'
          AND a.role IN ('senior_admin', 'junior_admin', 'moderator')
        ORDER BY a.role, a.user_id
        """,
        week_start,
    )
    result = []
    for r in rows:
        if r["salary_id"] is None:
            result.append({
                "userId": int(r["user_id"]),
                "username": r["username"], "firstName": r["first_name"], "role": r["role"],
                "state": "not_set", "total": 0, "paid": 0, "remaining": 0,
            })
        elif r["status"] != "paid" and r["status"] != "cancelled":
            total = int(r["amount"]); paid = int(r["paid_amount"] or 0)
            result.append({
                "userId": int(r["user_id"]),
                "username": r["username"], "firstName": r["first_name"], "role": r["role"],
                "state": r["status"], "total": total, "paid": paid,
                "remaining": max(0, total - paid),
            })
    return result


async def count_pending_salary_approvals() -> int:
    return int(await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM staff_salaries WHERE status = 'pending_approval'"
    ) or 0)


async def count_unpaid_salaries() -> int:
    return int(await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM staff_salaries WHERE status IN ('approved', 'partially_paid')"
    ) or 0)


# ---------------------------------------------------------------------------
# KPI и отчёты
# ---------------------------------------------------------------------------

async def get_member_stats(user_id: int, since) -> dict:
    actions = await db.pool.fetch(
        """
        SELECT action_type, COUNT(*)::int AS cnt
        FROM staff_actions
        WHERE admin_user_id = $1 AND created_at >= $2
        GROUP BY action_type
        """,
        user_id, since,
    )
    by_action = {r["action_type"]: int(r["cnt"]) for r in actions}
    actions_total = sum(by_action.values())

    taken = int(await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM staff_complaints WHERE taken_by = $1 AND taken_at >= $2",
        user_id, since,
    ) or 0)
    resolved = int(await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM staff_complaints WHERE resolved_by = $1 AND resolved_at >= $2",
        user_id, since,
    ) or 0)
    avg_resp = await db.pool.fetchval(
        """
        SELECT AVG(EXTRACT(EPOCH FROM (taken_at - created_at)))
        FROM staff_complaints
        WHERE taken_by = $1 AND taken_at >= $2 AND taken_at IS NOT NULL
        """,
        user_id, since,
    )
    online_min = await get_online_minutes(user_id, since)

    return {
        "actionsTotal": actions_total,
        "bans": by_action.get("ban", 0),
        "unbans": by_action.get("unban", 0),
        "mutes": by_action.get("mute", 0),
        "complaintsTaken": taken,
        "complaintsResolved": resolved,
        "avgResponseSeconds": int(avg_resp) if avg_resp is not None else None,
        "onlineMinutes": online_min,
    }


async def get_leaderboard(since) -> list[dict]:
    members = await db.pool.fetch(
        """
        SELECT user_id, username, first_name, role
        FROM admin_accounts
        WHERE status = 'active' AND role IN ('senior_admin', 'junior_admin', 'moderator')
        """,
    )
    result = []
    for m in members:
        uid = int(m["user_id"])
        stats = await get_member_stats(uid, since)
        score = (
            stats["actionsTotal"]
            + stats["complaintsResolved"] * 3
            + stats["complaintsTaken"]
            + (stats["onlineMinutes"] // 60)
        )
        result.append({
            "userId": uid,
            "username": m["username"],
            "firstName": m["first_name"],
            "role": m["role"],
            "score": score,
            **stats,
        })
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# Заметки о сотрудниках
# ---------------------------------------------------------------------------

async def list_staff_notes(staff_user_id: int) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT id, author_id, text, created_at
        FROM staff_notes WHERE staff_user_id = $1
        ORDER BY created_at DESC LIMIT 100
        """,
        staff_user_id,
    )
    return [
        {
            "id": int(r["id"]),
            "authorId": int(r["author_id"]),
            "text": r["text"],
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def add_staff_note(staff_user_id: int, author_id: int, text: str) -> int:
    row = await db.pool.fetchrow(
        "INSERT INTO staff_notes (staff_user_id, author_id, text) VALUES ($1, $2, $3) RETURNING id",
        staff_user_id, author_id, text,
    )
    return int(row["id"])


async def delete_staff_note(note_id: int) -> bool:
    result = await db.pool.execute("DELETE FROM staff_notes WHERE id = $1", note_id)
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


# ---------------------------------------------------------------------------
# Страйки (с истечением)
# ---------------------------------------------------------------------------

async def add_strike(user_id: int, reason: str, created_by: int, complaint_id: int | None = None) -> int:
    row = await db.pool.fetchrow(
        """
        INSERT INTO staff_strikes (user_id, reason, complaint_id, created_by)
        VALUES ($1, $2, $3, $4) RETURNING id
        """,
        user_id, reason or "", complaint_id, created_by,
    )
    return int(row["id"])


async def list_strikes(user_id: int) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT id, reason, complaint_id, created_by, created_at, expires_at,
               (expires_at > NOW()) AS active
        FROM staff_strikes WHERE user_id = $1
        ORDER BY created_at DESC LIMIT 100
        """,
        user_id,
    )
    return [
        {
            "id": int(r["id"]),
            "reason": r["reason"],
            "complaintId": int(r["complaint_id"]) if r["complaint_id"] else None,
            "createdBy": int(r["created_by"]) if r["created_by"] else None,
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            "expiresAt": r["expires_at"].isoformat() if r["expires_at"] else None,
            "active": bool(r["active"]),
        }
        for r in rows
    ]


async def count_active_strikes(user_id: int) -> int:
    return int(await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM staff_strikes WHERE user_id = $1 AND expires_at > NOW()",
        user_id,
    ) or 0)


async def remove_strike(strike_id: int) -> bool:
    """Досрочно снимает страйк (устанавливает expires_at = NOW())."""
    result = await db.pool.execute(
        "UPDATE staff_strikes SET expires_at = NOW() WHERE id = $1 AND expires_at > NOW()",
        strike_id,
    )
    return result.split()[-1] != "0"


# ---------------------------------------------------------------------------
# Авто-штраф к зарплате (по подтверждённой жалобе)
# ---------------------------------------------------------------------------

async def add_penalty_to_current_salary(user_id: int, add_penalty: int, reason: str, setter_id: int) -> bool:
    week_start = current_week_start()
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, base_amount, coefficient, bonus, penalty, penalty_reason, status
                FROM staff_salaries WHERE user_id = $1 AND week_start = $2 FOR UPDATE
                """,
                user_id, week_start,
            )
            if row and row["status"] == "paid":
                return False
            if row:
                new_penalty = int(row["penalty"] or 0) + add_penalty
                merged_reason = "; ".join(filter(None, [row["penalty_reason"], reason]))
                amount = compute_salary_total(
                    int(row["base_amount"] or 0), float(row["coefficient"] or 1),
                    int(row["bonus"] or 0), new_penalty,
                )
                await conn.execute(
                    """
                    UPDATE staff_salaries
                    SET penalty = $2, penalty_reason = $3, amount = $4, updated_at = NOW()
                    WHERE id = $1
                    """,
                    int(row["id"]), new_penalty, merged_reason, amount,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO staff_salaries
                        (user_id, week_start, amount, base_amount, coefficient,
                         bonus, penalty, penalty_reason, set_by, status)
                    VALUES ($1, $2, 0, 0, 1.0, 0, $3, $4, $5, 'pending_approval')
                    """,
                    user_id, week_start, add_penalty, reason or None, setter_id,
                )
    return True


# ---------------------------------------------------------------------------
# Доступность (отпуск / афк)
# ---------------------------------------------------------------------------

async def set_availability(user_id: int, availability: str, until) -> bool:
    result = await db.pool.execute(
        """
        UPDATE admin_accounts SET availability = $2, availability_until = $3
        WHERE user_id = $1 AND role <> 'applicant'
        """,
        user_id, availability, until,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


# ---------------------------------------------------------------------------
# Смены и посещаемость
# ---------------------------------------------------------------------------

async def add_shift(user_id: int, starts_at, ends_at, note: str | None, created_by: int) -> int:
    row = await db.pool.fetchrow(
        """
        INSERT INTO staff_shifts (user_id, starts_at, ends_at, note, created_by)
        VALUES ($1, $2, $3, $4, $5) RETURNING id
        """,
        user_id, starts_at, ends_at, note or None, created_by,
    )
    return int(row["id"])


async def delete_shift(shift_id: int) -> bool:
    result = await db.pool.execute("DELETE FROM staff_shifts WHERE id = $1", shift_id)
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def list_shifts(since, user_id: int | None = None) -> list[dict]:
    params = [since]
    where = "s.ends_at >= $1"
    if user_id:
        params.append(user_id)
        where += f" AND s.user_id = ${len(params)}"
    rows = await db.pool.fetch(
        f"""
        SELECT s.id, s.user_id, s.starts_at, s.ends_at, s.note,
               a.username, a.first_name,
               (SELECT COUNT(*) FROM admin_activity ac
                  WHERE ac.admin_user_id = s.user_id
                    AND ac.slot >= s.starts_at AND ac.slot < s.ends_at) AS slots
        FROM staff_shifts s
        LEFT JOIN admin_accounts a ON a.user_id = s.user_id
        WHERE {where}
        ORDER BY s.starts_at
        LIMIT 200
        """,
        *params,
    )
    out = []
    from datetime import datetime, timezone
    now_dt = datetime.now(timezone.utc)
    for r in rows:
        slots = int(r["slots"] or 0)
        starts = r["starts_at"]
        ends = r["ends_at"]
        if ends and ends > now_dt and (not starts or starts > now_dt):
            attendance = "upcoming"
        elif slots > 0:
            attendance = "attended"
        elif ends and ends <= now_dt:
            attendance = "missed"
        else:
            attendance = "ongoing" if slots == 0 else "attended"
        out.append({
            "id": int(r["id"]),
            "userId": int(r["user_id"]),
            "username": r["username"],
            "firstName": r["first_name"],
            "startsAt": starts.isoformat() if starts else None,
            "endsAt": ends.isoformat() if ends else None,
            "note": r["note"],
            "presentMinutes": slots * 10,
            "attendance": attendance,
        })
    return out


# ---------------------------------------------------------------------------
# Шаблоны вопросов анкеты
# ---------------------------------------------------------------------------

DEFAULT_APPLICATION_QUESTIONS = [
    ("experience", "Чем занимаешься? Опыт модерации", "textarea", True),
    ("time", "Сколько времени готов уделять?", "text", True),
    ("age_tz", "Возраст / часовой пояс", "text", True),
    ("motivation", "Почему хочешь к нам?", "textarea", False),
]


async def seed_application_questions() -> None:
    cnt = await db.pool.fetchval("SELECT COUNT(*)::int FROM application_questions")
    if cnt and cnt > 0:
        return
    for i, (qkey, label, qtype, required) in enumerate(DEFAULT_APPLICATION_QUESTIONS):
        await db.pool.execute(
            """
            INSERT INTO application_questions (qkey, label, qtype, required, sort_order)
            VALUES ($1, $2, $3, $4, $5) ON CONFLICT (qkey) DO NOTHING
            """,
            qkey, label, qtype, required, i,
        )


async def list_application_questions(enabled_only: bool = False) -> list[dict]:
    where = "WHERE enabled = TRUE" if enabled_only else ""
    rows = await db.pool.fetch(
        f"SELECT id, qkey, label, qtype, required, sort_order, enabled "
        f"FROM application_questions {where} ORDER BY sort_order, id"
    )
    return [
        {
            "id": int(r["id"]),
            "key": r["qkey"],
            "label": r["label"],
            "type": r["qtype"],
            "required": bool(r["required"]),
            "sortOrder": int(r["sort_order"]),
            "enabled": bool(r["enabled"]),
        }
        for r in rows
    ]


async def upsert_application_question(
    qkey: str, label: str, qtype: str, required: bool, sort_order: int, enabled: bool,
    question_id: int | None,
) -> int:
    if question_id:
        await db.pool.execute(
            """
            UPDATE application_questions
            SET qkey = $2, label = $3, qtype = $4, required = $5, sort_order = $6, enabled = $7
            WHERE id = $1
            """,
            question_id, qkey, label, qtype, required, sort_order, enabled,
        )
        return question_id
    row = await db.pool.fetchrow(
        """
        INSERT INTO application_questions (qkey, label, qtype, required, sort_order, enabled)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING id
        """,
        qkey, label, qtype, required, sort_order, enabled,
    )
    return int(row["id"])


async def delete_application_question(question_id: int) -> bool:
    result = await db.pool.execute("DELETE FROM application_questions WHERE id = $1", question_id)
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


# ---------------------------------------------------------------------------
# Со-подтверждение крупных выплат
# ---------------------------------------------------------------------------

async def create_pending_payout(
    salary_id: int, user_id: int, amount: int, method: str | None,
    kind: str, txid: str | None, proof: str | None, requested_by: int,
) -> int:
    row = await db.pool.fetchrow(
        """
        INSERT INTO pending_payouts
            (salary_id, user_id, amount, method, kind, txid, proof, requested_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id
        """,
        salary_id, user_id, amount, method, kind, txid or None, proof or None, requested_by,
    )
    return int(row["id"])


async def list_pending_payouts() -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT p.id, p.salary_id, p.user_id, p.amount, p.method, p.kind,
               p.requested_by, p.created_at, a.username, a.first_name
        FROM pending_payouts p
        LEFT JOIN admin_accounts a ON a.user_id = p.user_id
        ORDER BY p.created_at DESC
        """,
    )
    return [
        {
            "id": int(r["id"]),
            "salaryId": int(r["salary_id"]),
            "userId": int(r["user_id"]),
            "username": r["username"],
            "firstName": r["first_name"],
            "amount": int(r["amount"]),
            "method": r["method"],
            "kind": r["kind"],
            "requestedBy": int(r["requested_by"]) if r["requested_by"] else None,
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def get_pending_payout(payout_id: int) -> dict | None:
    row = await db.pool.fetchrow("SELECT * FROM pending_payouts WHERE id = $1", payout_id)
    return dict(row) if row else None


async def delete_pending_payout(payout_id: int) -> None:
    await db.pool.execute("DELETE FROM pending_payouts WHERE id = $1", payout_id)


async def get_member_card(user_id: int, since) -> dict:
    """Дашборд сотрудника: KPI + страйки + заметки + текущая зарплата + жалобы."""
    stats = await get_member_stats(user_id, since)
    strikes = await list_strikes(user_id)
    notes = await list_staff_notes(user_id)
    week_start = current_week_start()
    sal = await db.pool.fetchrow(
        """
        SELECT amount, paid_amount, status, base_amount, coefficient, bonus, penalty
        FROM staff_salaries WHERE user_id = $1 AND week_start = $2
        """,
        user_id, week_start,
    )
    complaints_total = int(await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM staff_complaints WHERE target_admin_id = $1", user_id,
    ) or 0)
    complaints_open = int(await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM staff_complaints WHERE target_admin_id = $1 AND status <> 'resolved'",
        user_id,
    ) or 0)
    return {
        "stats": stats,
        "strikes": strikes,
        "activeStrikes": sum(1 for s in strikes if s["active"]),
        "notes": notes,
        "currentSalary": {
            "amount": int(sal["amount"]), "paidAmount": int(sal["paid_amount"] or 0),
            "status": sal["status"],
        } if sal else None,
        "complaintsTotal": complaints_total,
        "complaintsOpen": complaints_open,
    }


async def accept_rules(user_id: int) -> bool:
    result = await db.pool.execute(
        """
        UPDATE admin_accounts
        SET rules_accepted_at = NOW()
        WHERE user_id = $1 AND rules_accepted_at IS NULL
        """,
        user_id,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def bootstrap_owner_accounts() -> int:
    """Промоутит владельцев (config.owner_user_ids) в owner/active.

    Защищает от self-lockout: после добавления колонок role/status все
    существующие аккаунты получают applicant/pending по умолчанию, поэтому
    владельцев нужно явно поднять обратно. Затрагивает только уже
    зарегистрированные admin_accounts — новых строк не создаёт и НЕ трогает
    totp_secret (секрет у каждого владельца свой, задаётся при регистрации).
    """
    from config import owner_user_ids

    owners = owner_user_ids()
    if not owners:
        return 0
    result = await db.pool.execute(
        """
        UPDATE admin_accounts
        SET role = 'owner', status = 'active'
        WHERE user_id = ANY($1::bigint[])
          AND (role <> 'owner' OR status <> 'active')
        """,
        list(owners),
    )
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0


async def get_dashboard_stats() -> dict:
    players = await db.pool.fetchval("SELECT COUNT(*)::int FROM users") or 0
    active_plots = await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM farm_plots WHERE status <> 'EMPTY'"
    ) or 0
    market_active = await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM market_listings WHERE status = 'active'"
    ) or 0
    admins = await db.pool.fetchval("SELECT COUNT(*)::int FROM admin_accounts") or 0
    return {
        "players": players,
        "activePlots": active_plots,
        "marketListings": market_active,
        "adminAccounts": admins,
    }


# ---------------------------------------------------------------------------
# Invite tokens
# ---------------------------------------------------------------------------

import secrets as _secrets


async def create_invite_token(label: str, created_by: int) -> dict:
    token = "INV-" + _secrets.token_urlsafe(24)
    row = await db.pool.fetchrow(
        """
        INSERT INTO admin_invite_tokens (token, label, created_by)
        VALUES ($1, $2, $3)
        RETURNING id, token, label, created_by, used_by, used_at, revoked_at, created_at
        """,
        token,
        label[:200].strip(),
        created_by,
    )
    return _fmt_invite_token(row)


async def list_invite_tokens() -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT t.id, t.token, t.label, t.created_by, t.used_by, t.used_at,
               t.revoked_at, t.created_at,
               u.first_name AS used_first_name, u.username AS used_username
        FROM admin_invite_tokens t
        LEFT JOIN users u ON u.user_id = t.used_by
        ORDER BY t.created_at DESC
        LIMIT 200
        """,
    )
    return [_fmt_invite_token(r) for r in rows]


async def revoke_invite_token(token_id: int) -> bool:
    result = await db.pool.execute(
        """
        UPDATE admin_invite_tokens
        SET revoked_at = NOW()
        WHERE id = $1 AND revoked_at IS NULL AND used_by IS NULL
        """,
        token_id,
    )
    return result.split()[-1] != "0"


async def hard_delete_invite_token(token_id: int) -> bool:
    result = await db.pool.execute(
        "DELETE FROM admin_invite_tokens WHERE id = $1",
        token_id,
    )
    return result.split()[-1] != "0"


async def find_valid_invite_token(token_value: str) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT id, token, label, created_by, used_by, used_at, revoked_at, created_at
        FROM admin_invite_tokens
        WHERE token = $1
          AND used_by IS NULL
          AND revoked_at IS NULL
        """,
        token_value,
    )
    return dict(row) if row else None


async def mark_invite_token_used(token_value: str, user_id: int) -> bool:
    result = await db.pool.execute(
        """
        UPDATE admin_invite_tokens
        SET used_by = $2, used_at = NOW()
        WHERE token = $1
          AND used_by IS NULL
          AND revoked_at IS NULL
        """,
        token_value,
        user_id,
    )
    return result.split()[-1] != "0"


def _fmt_invite_token(row) -> dict:
    d = dict(row)
    used_name = None
    if d.get("used_by"):
        used_name = (
            d.pop("used_first_name", None)
            or (f"@{d.pop('used_username', None)}" if d.get("used_username") else None)
            or f"ID {d['used_by']}"
        )
    else:
        d.pop("used_first_name", None)
        d.pop("used_username", None)
    return {
        "id": d["id"],
        "token": d["token"],
        "label": d["label"],
        "createdBy": d["created_by"],
        "usedBy": d.get("used_by"),
        "usedByName": used_name,
        "usedAt": d["used_at"].isoformat() if d.get("used_at") else None,
        "revokedAt": d["revoked_at"].isoformat() if d.get("revoked_at") else None,
        "createdAt": d["created_at"].isoformat() if d.get("created_at") else None,
    }
