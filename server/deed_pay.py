"""Оплата за наказания и за их проверку.

Администратор группы и сотрудник проекта проверяют по очереди. Создателю
хватает любого одного ответа: ждать второго не нужно. Карточку, которую ещё
никто не открыл, создатель может проверить сам — «подходит» сразу пишет
зарплату тому, кто выдал, кем бы он ни был.

Создатель решает, верное ли наказание. В зарплату входят те, чей ответ
с этим совпал: выдавший — если наказание верное, проверявший — если он
заранее сказал то же самое. «Непонятно» не оплачивается.

Нормы проверок включаются сами, когда в технических группах есть кут.
Код держит их так, чтобы за неделю зарплаты забирали не больше 15%
и не трогали последние 40%. Кут списывается только по кнопке «Выплатить».
Ручное сохранение норм останавливает автоподстройку.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from asyncpg.exceptions import DeadlockDetectedError, UniqueViolationError
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from admin_auth import get_any_telegram_user_id
from deed_tune import IDEAL, bucket, fill_days, plan_tune, purse_moved, unit_text
from admin_soft_restart import is_project_creator
from db import db
from deed_sort import (
    ADMIN_ORDER_SQL,
    CHECK_ADMIN,
    CHECK_RATES,
    CHECK_STAFF,
    CLAIM_SECONDS,
    CREATOR_ORDER_SQL,
    CREDIT_ROLES,
    STAGE_ADMIN,
    STAGE_STAFF,
    STAFF_ROLES,
    VERDICT_CLEAR,
    VERDICT_LABELS,
    VERDICT_WRONG,
    VERDICTS,
    admin_stage_done_sql,
    can_apply_lift,
    claim_free_sql,
    creator_open_sql,
    creator_ready_sql,
    ensure_deed_sorts,
    evidence_band,
    lift_actions,
    pick_credits,
    reviewer_roster_sql,
    reviewer_totals_sql,
    self_can_sort,
    self_settle,
    self_is_staff,
    staff_available_sql,
)
from human_actor import human_actor_sql

router = APIRouter(prefix="/deed-pay", tags=["deed-pay"])

TUNE_HOURS = 20

PURSE_SQL = """
SELECT COALESCE(SUM(GREATEST(chatbalance, 0)), 0)::bigint AS purse,
       COUNT(*) FILTER (WHERE COALESCE(chatbalance, 0) > 0)::int AS groups
FROM chat
WHERE COALESCE(is_technical, FALSE) = TRUE
"""

PAID_SPLIT_SQL = """
SELECT action_type,
       COALESCE(SUM(reward_kut), 0)::bigint AS all_n,
       COALESCE(SUM(reward_kut) FILTER (WHERE paid_at > NOW() - INTERVAL '7 days'), 0)::bigint AS week_n,
       COALESCE(SUM(reward_kut) FILTER (WHERE paid_at > NOW() - INTERVAL '30 days'), 0)::bigint AS month_n
FROM epsilon_deed_payouts
WHERE status = 'paid' AND purse = 'tech'
GROUP BY action_type
"""

OWED_SPLIT_SQL = """
SELECT action_type, COALESCE(SUM(reward_kut), 0)::bigint AS n
FROM epsilon_deed_payouts
WHERE status = 'owed' AND purse = 'tech'
GROUP BY action_type
"""

MANUAL_PAID_SQL = """
SELECT COALESCE(SUM(reward_kut), 0)::bigint AS n
FROM epsilon_deed_payouts
WHERE status = 'paid' AND purse = 'manual'
"""

DAYS_SQL = """
SELECT paid_at::date AS day,
       COALESCE(SUM(reward_kut) FILTER (WHERE action_type IN ('ban', 'mute', 'kick', 'warn')), 0)::bigint AS issue,
       COALESCE(SUM(reward_kut) FILTER (WHERE action_type = 'check_admin'), 0)::bigint AS admin,
       COALESCE(SUM(reward_kut) FILTER (WHERE action_type = 'check_staff'), 0)::bigint AS staff
FROM epsilon_deed_payouts
WHERE status = 'paid'
  AND purse = 'tech'
  AND paid_at > NOW() - INTERVAL '14 days'
GROUP BY 1
"""

WEEK_ISSUE_SQL = """
SELECT s.action_type AS action, COUNT(*)::int AS n
FROM epsilon_deed_reviews v
JOIN staff_actions s ON s.id = v.action_id
WHERE v.status = 'kept'
  AND v.reviewed_at > NOW() - INTERVAL '7 days'
  AND s.action_type IN ('ban', 'mute', 'kick', 'warn')
GROUP BY s.action_type
"""

WEEK_CHECK_SQL = """
SELECT CASE c.role WHEN 'admin' THEN 'check_admin' WHEN 'staff' THEN 'check_staff' END AS action,
       COUNT(*)::int AS n
FROM epsilon_deed_credits c
JOIN epsilon_deed_reviews v ON v.action_id = c.action_id
WHERE c.role IN ('admin', 'staff')
  AND v.reviewed_at > NOW() - INTERVAL '7 days'
GROUP BY 1
"""

PEOPLE_SQL = """
SELECT p.admin_id,
       MAX(COALESCE(NULLIF(btrim(u.first_name), ''), NULLIF(btrim(u.username), ''), '')) AS name,
       COALESCE(SUM(p.reward_kut) FILTER (
           WHERE p.status = 'paid' AND p.purse = 'tech' AND p.action_type IN ('ban', 'mute', 'kick', 'warn')
       ), 0)::bigint AS issue_paid,
       COALESCE(SUM(p.reward_kut) FILTER (
           WHERE p.status = 'paid' AND p.purse = 'tech' AND p.action_type = 'check_admin'
       ), 0)::bigint AS admin_paid,
       COALESCE(SUM(p.reward_kut) FILTER (
           WHERE p.status = 'paid' AND p.purse = 'tech' AND p.action_type = 'check_staff'
       ), 0)::bigint AS staff_paid,
       COALESCE(SUM(p.reward_kut) FILTER (
           WHERE p.status = 'owed' AND p.purse = 'tech'
       ), 0)::bigint AS owed
FROM epsilon_deed_payouts p
LEFT JOIN users u ON u.user_id = p.admin_id
GROUP BY p.admin_id
ORDER BY (
    COALESCE(SUM(p.reward_kut) FILTER (WHERE p.status = 'paid' AND p.purse = 'tech'), 0)
) DESC
LIMIT 12
"""

PUNISH = ("ban", "mute", "kick", "warn")
LABELS = {
    "ban": "Бан",
    "mute": "Мут",
    "kick": "Кик",
    "warn": "Предупреждение",
    CHECK_ADMIN: "Проверки администраторов",
    CHECK_STAFF: "Проверки сотрудников",
}
SCOPE_LABELS = {
    "chat": "одна группа",
    "all": "официальные группы",
    "full": "весь проект",
}
# Стартовые нормы наказаний. Проверки заводятся выключенными:
# сумма появится только когда её поставит создатель.
SEED = (
    ("ban", "Баны", 100, 200),
    ("mute", "Муты", 50, 80),
    ("kick", "Кики", 40, 60),
    ("warn", "Предупреждения", 80, 50),
)
_READY = False
UNDO_MINUTES = 10

UNDO_REVIEW_SQL = f"""
DELETE FROM epsilon_deed_reviews
WHERE action_id = $1
  AND reviewer_id = $2
  AND reviewed_at > NOW() - INTERVAL '{UNDO_MINUTES} minutes'
RETURNING status
"""

UNDO_SORT_SQL = f"""
DELETE FROM epsilon_deed_sorts ds
WHERE ds.action_id = $1
  AND ds.sorter_id = $2
  AND ds.sorted_at > NOW() - INTERVAL '{UNDO_MINUTES} minutes'
  AND NOT EXISTS (SELECT 1 FROM epsilon_deed_reviews v WHERE v.action_id = ds.action_id)
  AND NOT EXISTS (SELECT 1 FROM epsilon_deed_staff st WHERE st.action_id = ds.action_id)
RETURNING ds.verdict
"""

UNDO_STAFF_SQL = f"""
DELETE FROM epsilon_deed_staff st
WHERE st.action_id = $1
  AND st.staff_id = $2
  AND st.checked_at > NOW() - INTERVAL '{UNDO_MINUTES} minutes'
  AND NOT EXISTS (SELECT 1 FROM epsilon_deed_reviews v WHERE v.action_id = st.action_id)
  AND (st.lift_status IS NULL OR st.lift_status = 'pending')
RETURNING st.verdict
"""

# Старые решения без списка людей по-прежнему платят тому, кто выдал.
# Новые платят только отмеченным: credits_set отличает эти случаи.
ISSUE_COUNT_SQL = """
SELECT s.admin_user_id AS admin_id, COUNT(*)::int AS n
FROM epsilon_deed_reviews v
JOIN staff_actions s ON s.id = v.action_id
WHERE v.status = 'kept'
  AND s.action_type = $1
  AND s.admin_user_id IS NOT NULL
  AND (
    COALESCE(v.credits_set, FALSE) = FALSE
    OR EXISTS (
      SELECT 1 FROM epsilon_deed_credits c
      WHERE c.action_id = v.action_id
        AND c.role = 'issue'
        AND c.user_id = s.admin_user_id
    )
  )
GROUP BY s.admin_user_id
"""

CHECK_COUNT_SQL = """
SELECT c.user_id AS admin_id, COUNT(*)::int AS n
FROM epsilon_deed_credits c
WHERE c.role = $1
GROUP BY c.user_id
"""

_CHAIN_FROM = """
FROM staff_actions s
LEFT JOIN epsilon_deed_reviews v ON v.action_id = s.id
LEFT JOIN epsilon_deed_sorts ds ON ds.action_id = s.id
LEFT JOIN epsilon_deed_staff st ON st.action_id = s.id
"""

_CARD_SQL = """
    s.id, s.created_at, s.admin_user_id, s.admin_name, s.action_type,
    s.target_player_id, s.target_name, s.reason, s.evidence,
    s.proof_media_id, s.duration_minutes, s.chat_id, s.scope,
    c.namechat AS chat_title,
    tu.photo_url AS target_photo,
    tu.username AS target_username,
    tu.first_name AS target_first,
    au.username AS admin_username,
    au.first_name AS admin_first,
    r.title AS rate_title,
    r.every_n, r.reward_kut, r.enabled AS rate_enabled,
    ds.verdict AS sort_verdict,
    ds.sorter_id,
    COALESCE(NULLIF(btrim(su.first_name), ''), NULLIF(btrim(su.username), ''), '') AS sorter_name,
    v.status AS review_status,
    st.verdict AS staff_verdict,
    st.staff_id,
    st.lift_ask,
    st.lift_status,
    COALESCE(NULLIF(btrim(stu.first_name), ''), NULLIF(btrim(stu.username), ''), '') AS staff_name,
    (
        SELECT COUNT(*)::int FROM staff_actions h
        WHERE h.target_player_id = s.target_player_id
          AND h.action_type IN ('ban', 'mute', 'kick', 'warn', 'unban', 'unmute', 'unwarn')
          AND {human}
    ) AS archive_count
""".format(human=human_actor_sql("h"))

_CARD_FROM = """
FROM staff_actions s
LEFT JOIN epsilon_deed_reviews v ON v.action_id = s.id
LEFT JOIN epsilon_deed_sorts ds ON ds.action_id = s.id
LEFT JOIN users su ON su.user_id = ds.sorter_id
LEFT JOIN epsilon_deed_staff st ON st.action_id = s.id
LEFT JOIN users stu ON stu.user_id = st.staff_id
LEFT JOIN chat c ON c.chat_id = s.chat_id
LEFT JOIN users tu ON tu.user_id = s.target_player_id
LEFT JOIN users au ON au.user_id = s.admin_user_id
LEFT JOIN epsilon_deed_rates r ON r.action_type = s.action_type
"""


def milestones_for(confirmed: int, every_n: int) -> int:
    if every_n <= 0 or confirmed <= 0:
        return 0
    return int(confirmed) // int(every_n)


def plan_take(purses: list[tuple[int, int]], amount: int) -> list[tuple[int, int]]:
    """Сколько забрать с каждой технической группы. Список уже от богатой к бедной."""
    left = int(amount)
    if left <= 0:
        raise ValueError("Сумма выплаты должна быть больше нуля")
    taken: list[tuple[int, int]] = []
    for chat_id, balance in purses:
        if left <= 0:
            break
        have = int(balance or 0)
        if have <= 0:
            continue
        bite = have if have < left else left
        taken.append((int(chat_id), bite))
        left -= bite
    if left > 0:
        raise ValueError("В технических группах не хватает кут")
    return taken


def progress_line(confirmed: int, every_n: int, reward: int) -> dict[str, int]:
    step = milestones_for(confirmed, every_n)
    into = int(confirmed) - step * int(every_n) if every_n > 0 else int(confirmed)
    left = int(every_n) - into if every_n > 0 else 0
    return {
        "confirmed": int(confirmed),
        "into": into,
        "left": left,
        "nextReward": int(reward) if reward > 0 and every_n > 0 else 0,
    }


def _require_creator(user_id: int) -> None:
    if not is_project_creator(user_id):
        raise HTTPException(status_code=403, detail="Только создатель проекта")


def _reject_creator_stage(user_id: int) -> None:
    if is_project_creator(user_id):
        raise HTTPException(
            status_code=403,
            detail="Создатель решает карточку последним, когда её уже проверили",
        )


async def _require_staff(user_id: int) -> None:
    from config import is_plain_user

    if is_plain_user(user_id):
        raise HTTPException(status_code=403, detail="Нет доступа к панели")
    _reject_creator_stage(user_id)
    row = await db.pool.fetchval(
        """
        SELECT 1 FROM admin_accounts
        WHERE user_id = $1 AND status = 'active' AND role = ANY($2::text[])
        """,
        int(user_id),
        list(STAFF_ROLES),
    )
    if not row:
        raise HTTPException(
            status_code=403,
            detail="Эту проверку делают модераторы, младшие и старшие администраторы проекта",
        )


async def ensure_deed_tables() -> None:
    """Схема одна на все воркеры. Без замка два процесса создают одну таблицу
    и один из них падает: тип epsilon_deed_tune уже есть."""
    global _READY
    if _READY:
        return
    async with db.pool.acquire() as conn:
        for attempt in range(2):
            try:
                async with conn.transaction():
                    await conn.execute(
                        "SELECT pg_advisory_xact_lock(hashtext('epsilon_deed_tables'))"
                    )
                    await _install_deed_tables(conn)
                break
            except (UniqueViolationError, DeadlockDetectedError):
                if attempt:
                    raise
    await ensure_deed_sorts()
    _READY = True


async def _install_deed_tables(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_deed_rates (
            action_type TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            every_n INT NOT NULL,
            reward_kut BIGINT NOT NULL,
            purse TEXT NOT NULL DEFAULT 'tech',
            enabled BOOLEAN NOT NULL DEFAULT TRUE
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_deed_reviews (
            action_id BIGINT PRIMARY KEY,
            status TEXT NOT NULL,
            reviewer_id BIGINT NOT NULL,
            reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await conn.execute(
        """
        ALTER TABLE epsilon_deed_reviews
            ADD COLUMN IF NOT EXISTS credits_set BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    await conn.execute(
        """
        ALTER TABLE epsilon_deed_reviews
            ADD COLUMN IF NOT EXISTS self_verdict TEXT
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_deed_credits (
            action_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY (action_id, user_id, role)
        )
        """
    )
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS epsilon_deed_credits_user_idx
            ON epsilon_deed_credits (user_id, role)
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_deed_payouts (
            id BIGSERIAL PRIMARY KEY,
            admin_id BIGINT NOT NULL,
            action_type TEXT NOT NULL,
            milestone INT NOT NULL,
            reward_kut BIGINT NOT NULL,
            purse TEXT NOT NULL,
            status TEXT NOT NULL,
            paid_at TIMESTAMPTZ,
            note TEXT,
            UNIQUE (admin_id, action_type, milestone)
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_deed_tune (
            id INT PRIMARY KEY,
            auto BOOLEAN NOT NULL DEFAULT TRUE,
            tuned_at TIMESTAMPTZ,
            scale_num INT NOT NULL DEFAULT 1,
            scale_den INT NOT NULL DEFAULT 1,
            purse_kut BIGINT NOT NULL DEFAULT 0,
            budget_kut BIGINT NOT NULL DEFAULT 0,
            week_cost_kut BIGINT NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT ''
        )
        """
    )
    await conn.execute(
        """
        INSERT INTO epsilon_deed_tune (id, auto)
        VALUES (1, TRUE)
        ON CONFLICT (id) DO NOTHING
        """
    )
    for action, title, every_n, reward in SEED:
        await conn.execute(
            """
            INSERT INTO epsilon_deed_rates (action_type, title, every_n, reward_kut, purse, enabled)
            VALUES ($1, $2, $3, $4, 'tech', TRUE)
            ON CONFLICT (action_type) DO NOTHING
            """,
            action, title, every_n, reward,
        )
    for action, title in CHECK_RATES:
        await conn.execute(
            """
            INSERT INTO epsilon_deed_rates (action_type, title, every_n, reward_kut, purse, enabled)
            VALUES ($1, $2, 100, 0, 'tech', FALSE)
            ON CONFLICT (action_type) DO NOTHING
            """,
            action, title,
        )


def _person(row, prefix: str) -> str:
    name = (row.get(f"{prefix}_name") or "").strip()
    username = (row.get(f"{prefix}_username") or "").strip()
    if name and username:
        return f"{name} (@{username})"
    if name:
        return name
    if username:
        return f"@{username}"
    raw = row.get(f"{prefix}_id")
    return f"ID {raw}" if raw else ""


def _chain(row) -> list[dict]:
    items = []
    verdict = (row.get("sort_verdict") or "").strip()
    if verdict:
        items.append({
            "role": "admin",
            "id": int(row.get("sorter_id") or 0),
            "name": (row.get("sorter_name") or "").strip() or "Администратор",
            "verdict": verdict,
            "label": VERDICT_LABELS.get(verdict, ""),
        })
    staff_verdict = (row.get("staff_verdict") or "").strip()
    if staff_verdict:
        items.append({
            "role": "staff",
            "id": int(row.get("staff_id") or 0),
            "name": (row.get("staff_name") or "").strip() or "Сотрудник",
            "verdict": staff_verdict,
            "label": VERDICT_LABELS.get(staff_verdict, ""),
            "liftAsk": bool(row.get("lift_ask")),
        })
    return items


def _credits_view(row) -> list[dict]:
    people = []
    issuer = int(row.get("admin_user_id") or 0)
    if issuer:
        people.append({
            "role": "issue",
            "userId": issuer,
            "name": (row.get("admin_name") or "").strip() or "Администратор",
            "verdict": "",
            "label": "Выдал наказание",
            "payable": "keep",
        })
    for step in _chain(row):
        verdict = step["verdict"]
        if verdict == "clear":
            payable = "keep"
        elif verdict == "wrong":
            payable = "drop"
        else:
            payable = "never"
        people.append({
            "role": step["role"],
            "userId": step["id"],
            "name": step["name"],
            "verdict": verdict,
            "label": step["label"],
            "payable": payable,
        })
    return people


def _lift_view(row) -> dict | None:
    if not row.get("lift_ask"):
        return None
    status = (row.get("lift_status") or "pending").strip() or "pending"
    ok, why = can_apply_lift(
        row.get("action_type") or "",
        row.get("scope"),
        int(row.get("chat_id") or 0),
        int(row.get("target_player_id") or 0),
    )
    return {
        "status": status,
        "by": (row.get("staff_name") or "").strip() or "Сотрудник",
        "canLift": bool(ok) and status == "pending",
        "blocked": "" if ok else why,
    }


def _credit_people(row) -> list[tuple[str, int, str]]:
    people = [( "issue", int(row.get("admin_user_id") or 0), "" )]
    verdict = (row.get("sort_verdict") or "").strip()
    if verdict:
        people.append(("admin", int(row.get("sorter_id") or 0), verdict))
    staff_verdict = (row.get("staff_verdict") or "").strip()
    if staff_verdict:
        people.append(("staff", int(row.get("staff_id") or 0), staff_verdict))
    return people


def _card(row, history: list[dict]) -> dict[str, Any]:
    action = row["action_type"]
    scope = row["scope"] or ("chat" if row["chat_id"] else "all")
    minutes = row["duration_minutes"]
    verdict = (row.get("sort_verdict") or "").strip()
    chain = _chain(row)
    return {
        "id": int(row["id"]),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "actionType": action,
        "actionLabel": LABELS.get(action, action),
        "scope": scope,
        "scopeLabel": SCOPE_LABELS.get(scope, scope or ""),
        "chatId": int(row["chat_id"]) if row["chat_id"] else 0,
        "chatTitle": row["chat_title"] or "",
        "adminId": int(row["admin_user_id"]) if row["admin_user_id"] else 0,
        "adminName": row["admin_name"] or _person(row, "admin"),
        "targetId": int(row["target_player_id"]) if row["target_player_id"] else None,
        "targetName": row["target_name"] or _person(row, "target"),
        "targetPhoto": (row["target_photo"] or "").strip() or None,
        "reason": row["reason"] or "",
        "evidence": row["evidence"] or "",
        "hasProof": bool(row["proof_media_id"]),
        "proofMediaId": row["proof_media_id"] or None,
        "durationMinutes": int(minutes) if minutes is not None else None,
        "archiveCount": int(row["archive_count"] or 0),
        "history": history,
        "rateTitle": row["rate_title"] or LABELS.get(action, action),
        "everyN": int(row["every_n"] or 0),
        "rewardKut": int(row["reward_kut"] or 0),
        "rateEnabled": bool(row["rate_enabled"]),
        "sortVerdict": verdict or None,
        "sortLabel": VERDICT_LABELS.get(verdict, ""),
        "sorterName": (row.get("sorter_name") or "").strip() if verdict else "",
        "chain": chain,
        "credits": _credits_view(row),
        "lift": _lift_view(row),
        "reviewStatus": (row.get("review_status") or "") or None,
        "direct": not chain,
        "band": evidence_band(bool(row.get("proof_media_id")), row.get("reason") or ""),
    }


def _name_fields(row) -> dict:
    data = dict(row)
    data["target_name"] = data.get("target_name") or ""
    data["target_username"] = data.get("target_username") or ""
    if not data["target_name"]:
        data["target_name"] = (data.get("target_first") or "").strip()
    data["admin_username"] = data.get("admin_username") or ""
    if not (data.get("admin_name") or "").strip():
        data["admin_name"] = (data.get("admin_first") or "").strip()
    data["admin_id"] = data.get("admin_user_id")
    data["target_id"] = data.get("target_player_id")
    return data


async def _history(target_id: int | None) -> list[dict]:
    if not target_id:
        return []
    rows = await db.pool.fetch(
        f"""
        SELECT id, created_at, action_type, reason, admin_name
        FROM staff_actions
        WHERE target_player_id = $1
          AND action_type IN ('ban', 'mute', 'kick', 'warn', 'unban', 'unmute', 'unwarn')
          AND {human_actor_sql()}
        ORDER BY created_at DESC, id DESC
        LIMIT 5
        """,
        target_id,
    )
    out = []
    for row in rows:
        out.append({
            "id": int(row["id"]),
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "actionLabel": LABELS.get(row["action_type"], row["action_type"]),
            "reason": row["reason"] or "",
            "adminName": row["admin_name"] or "",
        })
    return out


async def _load_card(action_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        f"SELECT {_CARD_SQL} {_CARD_FROM} WHERE s.id = $1",
        int(action_id),
    )
    if not row:
        return None
    shaped = _name_fields(row)
    return _card(shaped, await _history(shaped.get("target_player_id")))


async def _count(where: str, params: list) -> int:
    return int(await db.pool.fetchval(
        f"SELECT COUNT(*)::int {_CHAIN_FROM} WHERE {where}",
        *params,
    ) or 0)


async def _claim(conn, action_id: int, stage: str, user_id: int) -> bool:
    row = await conn.fetchrow(
        """
        INSERT INTO epsilon_deed_claims (action_id, stage, user_id, until_at)
        VALUES ($1, $2, $3, NOW() + ($4 * INTERVAL '1 second'))
        ON CONFLICT (action_id, stage) DO UPDATE
            SET user_id = EXCLUDED.user_id,
                until_at = EXCLUDED.until_at
            WHERE epsilon_deed_claims.until_at <= NOW()
               OR epsilon_deed_claims.user_id = EXCLUDED.user_id
        RETURNING action_id
        """,
        int(action_id),
        stage,
        int(user_id),
        CLAIM_SECONDS,
    )
    return row is not None


async def _grab(where: str, params: list, stage: str, user_id: int, order_sql: str):
    """Берём одну свободную карточку и запоминаем фото следующей, чтобы оно открылось сразу."""
    rows = await db.pool.fetch(
        f"""
        SELECT s.id, NULLIF(btrim(s.proof_media_id), '') AS proof
        {_CHAIN_FROM}
        WHERE {where}
        ORDER BY {order_sql}
        LIMIT 8
        """,
        *params,
    )
    chosen = None
    async with db.pool.acquire() as conn:
        for row in rows:
            if await _claim(conn, int(row["id"]), stage, user_id):
                chosen = int(row["id"])
                break
    proof = None
    if chosen is not None:
        for row in rows:
            if int(row["id"]) != chosen and row["proof"]:
                proof = row["proof"]
                break
    return chosen, proof


async def _grab_pair(where: str, params: list, user_id: int, order_sql: str):
    """Создатель забирает карточку у обеих колод сразу, чтобы её не открыли двое."""
    rows = await db.pool.fetch(
        f"""
        SELECT s.id, NULLIF(btrim(s.proof_media_id), '') AS proof
        {_CHAIN_FROM}
        WHERE {where}
        ORDER BY {order_sql}
        LIMIT 8
        """,
        *params,
    )
    chosen = None
    async with db.pool.acquire() as conn:
        for row in rows:
            action_id = int(row["id"])
            if not await _claim(conn, action_id, STAGE_ADMIN, user_id):
                continue
            if not await _claim(conn, action_id, STAGE_STAFF, user_id):
                await _drop_claim(conn, action_id, STAGE_ADMIN)
                continue
            chosen = action_id
            break
    proof = None
    if chosen is not None:
        for row in rows:
            if int(row["id"]) != chosen and row["proof"]:
                proof = row["proof"]
                break
    return chosen, proof


async def _drop_claim(conn, action_id: int, stage: str) -> None:
    await conn.execute(
        "DELETE FROM epsilon_deed_claims WHERE action_id = $1 AND stage = $2",
        int(action_id),
        stage,
    )


async def _write_milestones(conn, action: str, every_n: int, reward: int, purse: str, counts) -> None:
    seen = []
    for row in counts:
        admin_id = int(row["admin_id"])
        seen.append(admin_id)
        top = milestones_for(int(row["n"]), every_n)
        for milestone in range(1, top + 1):
            await conn.execute(
                """
                INSERT INTO epsilon_deed_payouts
                    (admin_id, action_type, milestone, reward_kut, purse, status)
                VALUES ($1, $2, $3, $4, $5, 'owed')
                ON CONFLICT (admin_id, action_type, milestone) DO NOTHING
                """,
                admin_id, action, milestone, reward, purse,
            )
        await conn.execute(
            """
            UPDATE epsilon_deed_payouts
            SET reward_kut = $3, purse = $4
            WHERE admin_id = $1 AND action_type = $2 AND status = 'owed'
            """,
            admin_id, action, reward, purse,
        )
        await conn.execute(
            """
            DELETE FROM epsilon_deed_payouts
            WHERE admin_id = $1 AND action_type = $2 AND status = 'owed' AND milestone > $3
            """,
            admin_id, action, top,
        )
    if seen:
        await conn.execute(
            """
            DELETE FROM epsilon_deed_payouts
            WHERE action_type = $1 AND status = 'owed' AND NOT (admin_id = ANY($2::bigint[]))
            """,
            action, seen,
        )
    else:
        await conn.execute(
            "DELETE FROM epsilon_deed_payouts WHERE action_type = $1 AND status = 'owed'",
            action,
        )


async def _sync_owed(conn) -> None:
    rates = await conn.fetch(
        """
        SELECT action_type, every_n, reward_kut, purse
        FROM epsilon_deed_rates
        WHERE enabled = TRUE AND reward_kut > 0 AND every_n > 0
        """
    )
    live = {row["action_type"] for row in rates}
    if live:
        await conn.execute(
            """
            DELETE FROM epsilon_deed_payouts
            WHERE status = 'owed' AND NOT (action_type = ANY($1::text[]))
            """,
            list(live),
        )
    else:
        await conn.execute("DELETE FROM epsilon_deed_payouts WHERE status = 'owed'")
        return
    role_of = {CHECK_ADMIN: "admin", CHECK_STAFF: "staff"}
    for rate in rates:
        action = rate["action_type"]
        every_n = int(rate["every_n"])
        reward = int(rate["reward_kut"])
        purse = rate["purse"] if rate["purse"] in ("tech", "manual") else "tech"
        if action in role_of:
            counts = await conn.fetch(CHECK_COUNT_SQL, role_of[action])
        elif action in PUNISH:
            counts = await conn.fetch(ISSUE_COUNT_SQL, action)
        else:
            continue
        await _write_milestones(conn, action, every_n, reward, purse, counts)


class RateBody(BaseModel):
    actionType: str
    title: str = ""
    everyN: int = Field(ge=1, le=100000)
    rewardKut: int = Field(ge=0, le=10**12)
    purse: str = "tech"
    enabled: bool = False


class RatesBody(BaseModel):
    items: list[RateBody]


class SortBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: str = Field(default="", max_length=16)


class StaffBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: str = Field(default="", max_length=16)
    lift: bool = False


class CreditIn(BaseModel):
    role: str = ""
    userId: int = 0


class DecideBody(BaseModel):
    credits: list[CreditIn] | None = None


def _payable(pairs: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Создатель только решает зарплату. Себе записать её нельзя."""
    out: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for role, user_id in pairs:
        person = int(user_id or 0)
        if person <= 0 or is_project_creator(person) or (role, person) in seen:
            continue
        seen.add((role, person))
        out.append((role, person))
    return out


def _asked_set(credits: list[CreditIn] | None) -> set[tuple[str, int]] | None:
    if credits is None:
        return None
    asked = set()
    for item in credits[:8]:
        role = (item.role or "").strip()
        if role not in CREDIT_ROLES:
            continue
        user_id = int(item.userId or 0)
        if user_id > 0:
            asked.add((role, user_id))
    return asked


def _filters(action: str, admin_id: int, sorter_id: int = 0) -> tuple[str, list[Any]]:
    params: list[Any] = [list(PUNISH)]
    parts = [
        "s.action_type = ANY($1::text[])",
        human_actor_sql("s"),
        creator_ready_sql("s"),
    ]
    picked = action.strip().lower()
    if picked in PUNISH:
        params.append(picked)
        parts.append(f"s.action_type = ${len(params)}")
    if admin_id:
        params.append(int(admin_id))
        parts.append(f"s.admin_user_id = ${len(params)}")
    if sorter_id:
        params.append(int(sorter_id))
        parts.append(_by_person(len(params), "s.id"))
    return " AND ".join(parts), params


def _by_person(slot: int, action_id_sql: str) -> str:
    """Карточки, где этот человек ответил как администратор группы или как сотрудник."""
    return (
        f"(ds.sorter_id = ${slot} OR EXISTS ("
        f"SELECT 1 FROM epsilon_deed_staff mark "
        f"WHERE mark.action_id = {action_id_sql} AND mark.staff_id = ${slot}))"
    )


def _reviewer_name(row) -> str:
    name = (row["name"] or "").strip()
    username = (row["username"] or "").strip().lstrip("@")
    if name and username:
        return f"{name} (@{username})"
    if name:
        return name
    if username:
        return f"@{username}"
    return f"ID {int(row['id'])}"


def _reviewer(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": _reviewer_name(row),
        "title": (row["title"] or "").strip(),
        "reviewed": int(row["reviewed"] or 0),
        "clear": int(row["clear_n"] or 0),
        "wrong": int(row["wrong_n"] or 0),
        "weak": int(row["weak_n"] or 0),
        "kept": int(row["kept_n"] or 0),
        "dropped": int(row["dropped_n"] or 0),
        "waiting": int(row["open_n"] or 0),
        "lastAt": row["last_at"].isoformat() if row["last_at"] else None,
    }


@router.get("/reviewers")
async def deed_reviewers(user_id: int = Depends(get_any_telegram_user_id)):
    """Сколько карточек разобрал каждый, и чем это кончилось у создателя."""
    _require_creator(user_id)
    from group_realm import ensure_tables

    await ensure_tables()
    await ensure_deed_tables()
    rows = await db.pool.fetch(reviewer_roster_sql())
    fate = await db.pool.fetchrow(reviewer_totals_sql())
    people = [_reviewer(row) for row in rows]
    totals = {
        "admins": len(people),
        "reviewed": sum(item["reviewed"] for item in people),
        "clear": sum(item["clear"] for item in people),
        "wrong": sum(item["wrong"] for item in people),
        "weak": sum(item["weak"] for item in people),
        "kept": int(fate["kept_n"] or 0) if fate else 0,
        "dropped": int(fate["dropped_n"] or 0) if fate else 0,
        "waiting": int(fate["open_n"] or 0) if fate else 0,
    }
    return {"people": people, "totals": totals}


@router.get("/queue")
async def deed_queue(
    sort: str = Query(default="new"),
    action: str = Query(default=""),
    adminId: int = Query(default=0),
    sorterId: int = Query(default=0),
    user_id: int = Depends(get_any_telegram_user_id),
):
    _require_creator(user_id)
    await ensure_deed_tables()
    del sort  # порядок цепочки фиксированный: заявка, согласие, спор, «непонятно»
    where, params = _filters(action, adminId, sorterId)
    waiting = await _count(where, params)
    heads = await db.pool.fetch(
        f"""
        SELECT s.id, NULLIF(btrim(s.proof_media_id), '') AS proof
        {_CHAIN_FROM}
        WHERE {where}
        ORDER BY {CREATOR_ORDER_SQL}
        LIMIT 2
        """,
        *params,
    )
    card = await _load_card(int(heads[0]["id"])) if heads else None
    next_proof = None
    if len(heads) > 1:
        next_proof = heads[1]["proof"] or None
    admin_where, admin_params = _filters(action, 0)
    admins = await db.pool.fetch(
        f"""
        SELECT s.admin_user_id AS id, MAX(s.admin_name) AS name, COUNT(*)::int AS n
        {_CHAIN_FROM}
        WHERE {admin_where}
        GROUP BY s.admin_user_id
        ORDER BY n DESC
        LIMIT 40
        """,
        *admin_params,
    )
    return {
        "waiting": waiting,
        "card": card,
        "nextProofMediaId": next_proof,
        "admins": [
            {"id": int(a["id"] or 0), "name": a["name"] or f"ID {a['id']}", "waiting": int(a["n"])}
            for a in admins
        ],
    }


async def _decide(action_id: int, reviewer_id: int, status: str, asked: set[tuple[str, int]] | None) -> dict:
    _require_creator(reviewer_id)
    await ensure_deed_tables()
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            src = await conn.fetchrow(
                f"""
                SELECT s.id, s.action_type, s.admin_user_id,
                       ds.verdict AS sort_verdict, ds.sorter_id,
                       st.verdict AS staff_verdict, st.staff_id,
                       st.lift_ask, st.lift_status
                {_CHAIN_FROM}
                WHERE s.id = $1 AND s.action_type = ANY($2::text[])
                """,
                action_id, list(PUNISH),
            )
            if not src:
                raise HTTPException(status_code=404, detail="В архиве такой записи нет")
            existing = await conn.fetchval(
                "SELECT status FROM epsilon_deed_reviews WHERE action_id = $1",
                action_id,
            )
            if existing:
                raise HTTPException(status_code=409, detail="Это наказание уже решено")
            chosen = _payable(pick_credits(status, _credit_people(src), asked))
            inserted = await conn.fetchrow(
                """
                INSERT INTO epsilon_deed_reviews (action_id, status, reviewer_id, credits_set)
                VALUES ($1, $2, $3, TRUE)
                ON CONFLICT (action_id) DO NOTHING
                RETURNING action_id
                """,
                action_id, status, reviewer_id,
            )
            if not inserted:
                raise HTTPException(status_code=409, detail="Это наказание уже решено")
            for role, person_id in chosen:
                await conn.execute(
                    """
                    INSERT INTO epsilon_deed_credits (action_id, user_id, role)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (action_id, user_id, role) DO NOTHING
                    """,
                    action_id, person_id, role,
                )
            await _sync_owed(conn)
            lift_open = bool(src["lift_ask"]) and (src["lift_status"] or "") == "pending"
    from admin_audit import log_admin_action
    await log_admin_action(
        reviewer_id,
        "deed_keep" if status == "kept" else "deed_drop",
        target_type="staff_action",
        target_id=str(action_id),
        details={"status": status, "credits": len(chosen)},
    )
    return {"ok": True, "id": action_id, "status": status, "liftOpen": lift_open}


@router.post("/queue/{action_id}/keep")
async def deed_keep(
    action_id: int,
    body: DecideBody = Body(default_factory=DecideBody),
    user_id: int = Depends(get_any_telegram_user_id),
):
    _require_creator(user_id)
    return await _decide(action_id, user_id, "kept", _asked_set(body.credits))


@router.post("/queue/{action_id}/drop")
async def deed_drop(
    action_id: int,
    body: DecideBody = Body(default_factory=DecideBody),
    user_id: int = Depends(get_any_telegram_user_id),
):
    _require_creator(user_id)
    return await _decide(action_id, user_id, "dropped", _asked_set(body.credits))


@router.post("/queue/{action_id}/undo")
async def deed_undo(action_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    """Создатель возвращает решение по зарплате, пока выплата не ушла. Снятие наказания это не возвращает."""
    _require_creator(user_id)
    await ensure_deed_tables()
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            gone = await conn.fetchrow(UNDO_REVIEW_SQL, int(action_id), int(user_id))
            if not gone:
                raise HTTPException(
                    status_code=409,
                    detail=f"Вернуть можно только своё решение за последние {UNDO_MINUTES} минут",
                )
            await conn.execute(
                "DELETE FROM epsilon_deed_credits WHERE action_id = $1",
                int(action_id),
            )
            await _sync_owed(conn)
    from admin_audit import log_admin_action
    await log_admin_action(
        user_id,
        "deed_undo",
        target_type="staff_action",
        target_id=str(action_id),
        details={"status": gone["status"]},
    )
    return {"ok": True, "id": int(action_id), "status": gone["status"]}


def _work_where() -> str:
    """Чужое наказание без ответа администратора, которое сейчас никто не держит."""
    return " AND ".join([
        "v.action_id IS NULL",
        "ds.action_id IS NULL",
        "s.action_type = ANY($1::text[])",
        human_actor_sql("s"),
        self_can_sort("s", "$2"),
        claim_free_sql(STAGE_ADMIN, "$2"),
    ])


def _staff_where() -> str:
    """Этап администратора уже закрыт, сотрудник ещё не ответил, карточку не держит коллега."""
    return " AND ".join([
        "v.action_id IS NULL",
        "st.action_id IS NULL",
        "s.action_type = ANY($1::text[])",
        human_actor_sql("s"),
        self_is_staff("$2"),
        "COALESCE(s.admin_user_id, 0) <> $2",
        "COALESCE(ds.sorter_id, 0) <> $2",
        admin_stage_done_sql("s"),
        claim_free_sql(STAGE_STAFF, "$2"),
    ])


async def _open_deck(where: str, params: list, stage: str, user_id: int, order_sql: str) -> dict:
    waiting = await _count(where, params)
    chosen, proof = await _grab(where, params, stage, user_id, order_sql)
    card = await _load_card(chosen) if chosen else None
    return {"waiting": waiting, "card": card, "nextProofMediaId": proof}


@router.get("/work")
async def deed_work(user_id: int = Depends(get_any_telegram_user_id)):
    _reject_creator_stage(user_id)
    from group_realm import ensure_tables

    await ensure_tables()
    await ensure_deed_tables()
    await _require_work_page(user_id)
    return await _open_deck(_work_where(), [list(PUNISH), int(user_id)], STAGE_ADMIN, user_id, ADMIN_ORDER_SQL)


@router.get("/pulse")
async def deed_pulse(user_id: int = Depends(get_any_telegram_user_id)):
    """Сколько карточек ждёт на каждом этапе. Ни одну из рук не забирает."""
    await ensure_deed_tables()
    uid = int(user_id)
    out = {"work": None, "staff": None, "own": None, "queue": None}
    if is_project_creator(uid):
        out["own"] = await _count(_own_where(), [list(PUNISH), uid])
        where, params = _filters("", 0, 0)
        out["queue"] = await _count(where, params)
        return out
    from config import is_plain_user
    from group_realm import seat_sees, seats_for

    if seat_sees(await seats_for(uid), "work"):
        out["work"] = await _count(_work_where(), [list(PUNISH), uid])
    if not is_plain_user(uid):
        staff = await db.pool.fetchval(
            """
            SELECT 1 FROM admin_accounts
            WHERE user_id = $1 AND status = 'active' AND role = ANY($2::text[])
            """,
            uid,
            list(STAFF_ROLES),
        )
        if staff:
            out["staff"] = await _count(_staff_where(), [list(PUNISH), uid])
    return out


@router.get("/staff/count")
async def deed_staff_count(user_id: int = Depends(get_any_telegram_user_id)):
    """Сколько карточек ждёт, не забирая ни одну себе."""
    await _require_staff(user_id)
    await ensure_deed_tables()
    waiting = await _count(_staff_where(), [list(PUNISH), int(user_id)])
    return {"waiting": waiting}


@router.get("/staff")
async def deed_staff(user_id: int = Depends(get_any_telegram_user_id)):
    await _require_staff(user_id)
    await ensure_deed_tables()
    return await _open_deck(
        _staff_where(), [list(PUNISH), int(user_id)], STAGE_STAFF, user_id, ADMIN_ORDER_SQL,
    )


def _own_where() -> str:
    """Чужая карточка без ответа, которую ещё могут взять администратор или сотрудник."""
    return " AND ".join([
        "s.action_type = ANY($1::text[])",
        human_actor_sql("s"),
        "COALESCE(s.admin_user_id, 0) <> $2",
        creator_open_sql("s", "$2"),
    ])


async def _open_own(user_id: int) -> dict:
    params = [list(PUNISH), int(user_id)]
    where = _own_where()
    waiting = await _count(where, params)
    chosen, proof = await _grab_pair(where, params, int(user_id), ADMIN_ORDER_SQL)
    card = await _load_card(chosen) if chosen else None
    return {"waiting": waiting, "card": card, "nextProofMediaId": proof}


@router.get("/own")
async def deed_own(user_id: int = Depends(get_any_telegram_user_id)):
    """Наказания, которые создатель проверяет сам и сразу отправляет в зарплату."""
    _require_creator(user_id)
    await ensure_deed_tables()
    return await _open_own(user_id)


@router.post("/own/{action_id}")
async def deed_own_sort(
    action_id: int,
    body: SortBody,
    user_id: int = Depends(get_any_telegram_user_id),
):
    _require_creator(user_id)
    verdict = (body.verdict or "").strip().lower()
    if verdict not in VERDICTS:
        raise HTTPException(status_code=400, detail="Выберите ответ: подходит, выдано неправильно или непонятно")
    await ensure_deed_tables()
    where = _own_where()
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            src = await conn.fetchrow(
                f"""
                SELECT s.id, s.admin_user_id
                {_CHAIN_FROM}
                WHERE s.id = $3 AND {where}
                """,
                list(PUNISH),
                int(user_id),
                int(action_id),
            )
            if not src:
                await _drop_claim(conn, int(action_id), STAGE_ADMIN)
                await _drop_claim(conn, int(action_id), STAGE_STAFF)
                raise HTTPException(status_code=409, detail="Эту карточку уже проверяют")
            status, credits = self_settle(verdict, int(src["admin_user_id"] or 0))
            if int(src["admin_user_id"] or 0) == int(user_id):
                status, credits = "dropped", []
            credits = _payable(credits)
            inserted = await conn.fetchrow(
                """
                INSERT INTO epsilon_deed_reviews
                    (action_id, status, reviewer_id, credits_set, self_verdict)
                VALUES ($1, $2, $3, TRUE, $4)
                ON CONFLICT (action_id) DO NOTHING
                RETURNING action_id
                """,
                int(action_id),
                status,
                int(user_id),
                verdict,
            )
            if not inserted:
                raise HTTPException(status_code=409, detail="Это наказание уже решено")
            for role, person_id in credits:
                await conn.execute(
                    """
                    INSERT INTO epsilon_deed_credits (action_id, user_id, role)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (action_id, user_id, role) DO NOTHING
                    """,
                    int(action_id), person_id, role,
                )
            await _drop_claim(conn, int(action_id), STAGE_ADMIN)
            await _drop_claim(conn, int(action_id), STAGE_STAFF)
            await _sync_owed(conn)
    from admin_audit import log_admin_action
    await log_admin_action(
        user_id,
        "deed_keep" if status == "kept" else "deed_drop",
        target_type="staff_action",
        target_id=str(action_id),
        details={"status": status, "self": verdict, "credits": len(credits)},
    )
    return {
        "ok": True,
        "id": int(action_id),
        "verdict": verdict,
        "label": VERDICT_LABELS[verdict],
        "status": status,
        "paid": verdict == VERDICT_CLEAR and bool(credits),
    }


async def _require_work_page(user_id: int) -> None:
    """Колода администратора открыта только должности, у которой включена «Работа»."""
    from group_realm import seat_sees, seats_for

    groups = await seats_for(user_id)
    if not seat_sees(groups, "work"):
        raise HTTPException(status_code=403, detail="Должность не открывает работу")


async def _stage_after_admin(action_id: int) -> str:
    found = await db.pool.fetchval(
        f"""
        SELECT 1
        FROM staff_actions s
        LEFT JOIN epsilon_deed_sorts ds ON ds.action_id = s.id
        WHERE s.id = $1 AND {staff_available_sql("s")}
        """,
        int(action_id),
    )
    return "staff" if found else "creator"


@router.post("/work/{action_id}")
async def deed_work_sort(
    action_id: int,
    body: SortBody,
    user_id: int = Depends(get_any_telegram_user_id),
):
    _reject_creator_stage(user_id)
    verdict = (body.verdict or "").strip().lower()
    if verdict not in VERDICTS:
        raise HTTPException(status_code=400, detail="Выберите ответ: подходит, выдано неправильно или непонятно")
    from group_realm import ensure_tables

    await ensure_tables()
    await ensure_deed_tables()
    await _require_work_page(user_id)
    where = _work_where()
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                f"""
                SELECT s.id
                {_CHAIN_FROM}
                WHERE s.id = $3 AND {where}
                """,
                list(PUNISH),
                int(user_id),
                int(action_id),
            )
            if not row:
                await _reject_admin(conn, int(action_id), int(user_id))
            inserted = await conn.fetchrow(
                """
                INSERT INTO epsilon_deed_sorts (action_id, verdict, sorter_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (action_id) DO NOTHING
                RETURNING action_id
                """,
                int(action_id),
                verdict,
                int(user_id),
            )
            if not inserted:
                raise HTTPException(status_code=409, detail="На это наказание уже ответили")
            await _drop_claim(conn, int(action_id), STAGE_ADMIN)
    nxt = await _stage_after_admin(int(action_id))
    return {
        "ok": True,
        "id": int(action_id),
        "verdict": verdict,
        "label": VERDICT_LABELS[verdict],
        "next": nxt,
    }


async def _reject_if_paid(conn, action_id: int) -> None:
    reviewed = await conn.fetchval(
        "SELECT 1 FROM epsilon_deed_reviews WHERE action_id = $1",
        action_id,
    )
    if reviewed:
        raise HTTPException(status_code=409, detail="Создатель уже отправил это наказание в зарплату")


async def _reject_admin(conn, action_id: int, user_id: int) -> None:
    await _reject_if_paid(conn, action_id)
    owner = await conn.fetchval(
        "SELECT admin_user_id FROM staff_actions WHERE id = $1",
        action_id,
    )
    if owner and int(owner) == int(user_id):
        raise HTTPException(status_code=403, detail="Своё наказание проверяет другой администратор")
    taken = await conn.fetchval(
        "SELECT 1 FROM epsilon_deed_sorts WHERE action_id = $1",
        action_id,
    )
    if taken:
        raise HTTPException(status_code=409, detail="На это наказание уже ответили")
    raise HTTPException(status_code=409, detail="Эту карточку уже проверяет другой администратор")


@router.post("/work/{action_id}/undo")
async def deed_work_undo(action_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    """Администратор снимает свой ответ, пока сотрудник или создатель его не взяли."""
    _reject_creator_stage(user_id)
    await ensure_deed_tables()
    gone = await db.pool.fetchrow(UNDO_SORT_SQL, int(action_id), int(user_id))
    if not gone:
        decided = await db.pool.fetchval(
            "SELECT 1 FROM epsilon_deed_reviews WHERE action_id = $1",
            int(action_id),
        )
        if decided:
            raise HTTPException(status_code=409, detail="Создатель уже решил это наказание")
        staff = await db.pool.fetchval(
            "SELECT 1 FROM epsilon_deed_staff WHERE action_id = $1",
            int(action_id),
        )
        if staff:
            raise HTTPException(status_code=409, detail="Сотрудник проекта уже проверил это наказание")
        raise HTTPException(
            status_code=409,
            detail=f"Вернуть можно только свой ответ за последние {UNDO_MINUTES} минут",
        )
    return {"ok": True, "id": int(action_id), "verdict": gone["verdict"]}


@router.post("/staff/{action_id}")
async def deed_staff_sort(
    action_id: int,
    body: StaffBody,
    user_id: int = Depends(get_any_telegram_user_id),
):
    await _require_staff(user_id)
    verdict = VERDICT_WRONG if body.lift else (body.verdict or "").strip().lower()
    if verdict not in VERDICTS:
        raise HTTPException(status_code=400, detail="Выберите ответ: подходит, выдано неправильно или непонятно")
    await ensure_deed_tables()
    where = _staff_where()
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                f"""
                SELECT s.id, s.action_type, s.scope, s.chat_id, s.target_player_id
                {_CHAIN_FROM}
                WHERE s.id = $3 AND {where}
                """,
                list(PUNISH),
                int(user_id),
                int(action_id),
            )
            if not row:
                await _reject_staff(conn, int(action_id), int(user_id))
            if body.lift:
                ok, why = can_apply_lift(
                    row["action_type"], row["scope"], int(row["chat_id"] or 0), int(row["target_player_id"] or 0),
                )
                if not ok:
                    raise HTTPException(
                        status_code=409,
                        detail=why + " Отметьте наказание неправильным: создатель увидит это и не засчитает его.",
                    )
            inserted = await conn.fetchrow(
                """
                INSERT INTO epsilon_deed_staff
                    (action_id, verdict, lift_ask, lift_status, staff_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (action_id) DO NOTHING
                RETURNING action_id
                """,
                int(action_id),
                verdict,
                bool(body.lift),
                "pending" if body.lift else None,
                int(user_id),
            )
            if not inserted:
                raise HTTPException(status_code=409, detail="На это наказание уже ответил сотрудник проекта")
            await _drop_claim(conn, int(action_id), STAGE_STAFF)
    return {
        "ok": True,
        "id": int(action_id),
        "verdict": verdict,
        "label": VERDICT_LABELS[verdict],
        "lift": bool(body.lift),
        "next": "creator",
    }


async def _reject_staff(conn, action_id: int, user_id: int) -> None:
    await _reject_if_paid(conn, action_id)
    owner = await conn.fetchval(
        "SELECT admin_user_id FROM staff_actions WHERE id = $1",
        action_id,
    )
    if owner and int(owner) == int(user_id):
        raise HTTPException(status_code=403, detail="Своё наказание проверяет кто-то другой")
    sorter = await conn.fetchval(
        "SELECT sorter_id FROM epsilon_deed_sorts WHERE action_id = $1",
        action_id,
    )
    if sorter and int(sorter) == int(user_id):
        raise HTTPException(status_code=403, detail="Вы уже проверили это наказание как администратор группы")
    staff = await conn.fetchval(
        "SELECT 1 FROM epsilon_deed_staff WHERE action_id = $1",
        action_id,
    )
    if staff:
        raise HTTPException(status_code=409, detail="На это наказание уже ответил сотрудник проекта")
    if not sorter:
        raise HTTPException(status_code=409, detail="Сначала это наказание проверяет администратор группы")
    raise HTTPException(status_code=409, detail="Эту карточку уже проверяет другой сотрудник")


@router.post("/staff/{action_id}/undo")
async def deed_staff_undo(action_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    await _require_staff(user_id)
    await ensure_deed_tables()
    gone = await db.pool.fetchrow(UNDO_STAFF_SQL, int(action_id), int(user_id))
    if not gone:
        decided = await db.pool.fetchval(
            "SELECT 1 FROM epsilon_deed_reviews WHERE action_id = $1",
            int(action_id),
        )
        if decided:
            raise HTTPException(status_code=409, detail="Создатель уже решил это наказание")
        closed = await db.pool.fetchval(
            """
            SELECT lift_status FROM epsilon_deed_staff
            WHERE action_id = $1 AND staff_id = $2
            """,
            int(action_id),
            int(user_id),
        )
        if closed and closed not in ("pending",):
            raise HTTPException(status_code=409, detail="Заявку на разблокировку уже решили")
        raise HTTPException(
            status_code=409,
            detail=f"Вернуть можно только свой ответ за последние {UNDO_MINUTES} минут",
        )
    return {"ok": True, "id": int(action_id), "verdict": gone["verdict"]}


async def _release_stuck_lifts() -> None:
    await db.pool.execute(
        """
        UPDATE epsilon_deed_staff
        SET lift_status = 'pending', lift_decided_by = NULL, lift_decided_at = NULL
        WHERE lift_status = 'lifting'
          AND lift_decided_at < NOW() - INTERVAL '2 minutes'
        """
    )


async def _clear_warns(user_id: int, chat_id: int, *, everyone: bool, admin_id: int, reason: str) -> None:
    if everyone:
        await db.pool.execute("DELETE FROM active_warns WHERE user_id = $1", int(user_id))
        scope = "all"
    else:
        await db.pool.execute(
            "DELETE FROM active_warns WHERE user_id = $1 AND chat_id = $2",
            int(user_id), int(chat_id),
        )
        scope = "chat"
    await db.pool.execute(
        """
        INSERT INTO staff_actions
            (admin_user_id, admin_name, target_player_id, action_type, reason, chat_id, scope, created_at)
        VALUES ($1, 'Админ-панель', $2, 'unwarn', $3, $4, $5, NOW())
        """,
        int(admin_id), int(user_id), reason, int(chat_id or 0), scope,
    )


async def _note_lift(admin_id: int, target: int, chat_id: int, scope: str, action_type: str, reason: str) -> None:
    visible = {"ban": "unban", "mute": "unmute", "warn": "unwarn"}.get(action_type)
    if not visible:
        return
    await db.pool.execute(
        """
        INSERT INTO staff_actions
            (admin_user_id, admin_name, target_player_id, action_type, reason, chat_id, scope, created_at)
        VALUES ($1, 'Админ-панель', $2, $3, $4, $5, $6, NOW())
        """,
        int(admin_id), int(target), visible, reason, int(chat_id or 0), scope or "chat",
    )


async def _apply_lift(row, admin_id: int) -> None:
    action = row["action_type"]
    scope = row["scope"] or "chat"
    chat = int(row["chat_id"] or 0)
    target = int(row["target_player_id"] or 0)
    ok, why = can_apply_lift(action, scope, chat, target)
    if not ok:
        raise HTTPException(status_code=409, detail=why)
    reason = "После проверки наказание снято"
    visible = False
    from admin_groups import moderate_action

    for act in lift_actions(action, scope) or ():
        if act in ("unwarn_chat", "unwarn_all"):
            await _clear_warns(
                target, chat, everyone=(act == "unwarn_all"), admin_id=admin_id, reason=reason,
            )
            visible = True
            continue
        if act == "bot_unban":
            from admin_users import admin_set_banned
            await admin_set_banned(target, False, admin_user_id=int(admin_id), reason=reason, notify=False)
            continue
        result = await moderate_action(
            chat_id=chat,
            user_id=target,
            action=act,
            reason=reason,
            admin_id=int(admin_id),
        )
        if not result.get("ok"):
            detail = result.get("detail") or result.get("telegram") or "Не удалось снять наказание"
            raise HTTPException(status_code=409, detail=str(detail)[:200])
        if act in ("unban", "unmute", "unwarn"):
            visible = True
    if not visible:
        await _note_lift(admin_id, target, chat, scope, action, reason)
    try:
        from admin_player_notify import notify_punishment_lifted
        notify_punishment_lifted(target, action_type=action)
    except Exception:
        return


async def _lock_lift(action_id: int, user_id: int):
    row = await db.pool.fetchrow(
        """
        UPDATE epsilon_deed_staff st
        SET lift_status = 'lifting', lift_decided_by = $2, lift_decided_at = NOW()
        FROM staff_actions s
        WHERE st.action_id = s.id
          AND st.action_id = $1
          AND st.lift_ask = TRUE
          AND st.lift_status = 'pending'
        RETURNING s.action_type, s.scope, s.chat_id, s.target_player_id
        """,
        int(action_id), int(user_id),
    )
    if not row:
        raise HTTPException(status_code=409, detail="Заявки на разблокировку нет или её уже решили")
    return row


@router.post("/queue/{action_id}/lift")
async def deed_lift(action_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    """Снять ровно то наказание, которое выдали, и написать об этом игроку."""
    _require_creator(user_id)
    await ensure_deed_tables()
    await _release_stuck_lifts()
    row = await _lock_lift(action_id, user_id)
    try:
        await _apply_lift(row, user_id)
    except Exception:
        await db.pool.execute(
            """
            UPDATE epsilon_deed_staff
            SET lift_status = 'pending', lift_decided_by = NULL, lift_decided_at = NULL
            WHERE action_id = $1 AND lift_status = 'lifting'
            """,
            int(action_id),
        )
        raise
    await db.pool.execute(
        """
        UPDATE epsilon_deed_staff
        SET lift_status = 'lifted', lift_decided_at = NOW(), lift_decided_by = $2
        WHERE action_id = $1
        """,
        int(action_id), int(user_id),
    )
    from admin_audit import log_admin_action
    await log_admin_action(
        user_id,
        "deed_lift",
        target_type="staff_action",
        target_id=str(action_id),
        details={"action": row["action_type"], "scope": row["scope"]},
    )
    return {"ok": True, "id": int(action_id), "status": "lifted"}


@router.post("/queue/{action_id}/lift-reject")
async def deed_lift_reject(action_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_deed_tables()
    gone = await db.pool.fetchrow(
        """
        UPDATE epsilon_deed_staff
        SET lift_status = 'rejected', lift_decided_at = NOW(), lift_decided_by = $2
        WHERE action_id = $1 AND lift_ask = TRUE AND lift_status = 'pending'
        RETURNING action_id
        """,
        int(action_id), int(user_id),
    )
    if not gone:
        raise HTTPException(status_code=409, detail="Заявки на разблокировку нет или её уже решили")
    from admin_audit import log_admin_action
    await log_admin_action(
        user_id,
        "deed_lift_reject",
        target_type="staff_action",
        target_id=str(action_id),
        details={},
    )
    return {"ok": True, "id": int(action_id), "status": "rejected"}


def _rate_row(row) -> dict:
    return {
        "actionType": row["action_type"],
        "title": row["title"] or LABELS.get(row["action_type"], row["action_type"]),
        "everyN": int(row["every_n"]),
        "rewardKut": int(row["reward_kut"]),
        "purse": row["purse"] if row["purse"] in ("tech", "manual") else "tech",
        "enabled": bool(row["enabled"]),
    }


@router.get("/rates")
async def deed_rates(user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_deed_tables()
    rows = await db.pool.fetch(
        """
        SELECT action_type, title, every_n, reward_kut, purse, enabled
        FROM epsilon_deed_rates
        ORDER BY action_type
        """
    )
    return {"items": [_rate_row(r) for r in rows]}


@router.put("/rates")
async def deed_save_rates(body: RatesBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_deed_tables()
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            for item in body.items:
                action = item.actionType.strip().lower()
                if not action or len(action) > 32:
                    raise HTTPException(status_code=400, detail="Некорректный тип задания")
                purse = item.purse if item.purse in ("tech", "manual") else "tech"
                title = (item.title or LABELS.get(action, action)).strip()[:80]
                await conn.execute(
                    """
                    INSERT INTO epsilon_deed_rates
                        (action_type, title, every_n, reward_kut, purse, enabled)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (action_type) DO UPDATE SET
                        title = EXCLUDED.title,
                        every_n = EXCLUDED.every_n,
                        reward_kut = EXCLUDED.reward_kut,
                        purse = EXCLUDED.purse,
                        enabled = EXCLUDED.enabled
                    """,
                    action, title, int(item.everyN), int(item.rewardKut), purse, bool(item.enabled),
                )
            await conn.execute(
                """
                INSERT INTO epsilon_deed_tune (id, auto)
                VALUES (1, FALSE)
                ON CONFLICT (id) DO UPDATE SET auto = FALSE
                """
            )
            await _sync_owed(conn)
    return await deed_rates(user_id)


@router.post("/rates/collect")
async def deed_collect(user_id: int = Depends(get_any_telegram_user_id)):
    """Предложить задания по типам, которые уже встречаются в архиве."""
    _require_creator(user_id)
    await ensure_deed_tables()
    rows = await db.pool.fetch(
        f"""
        SELECT action_type, COUNT(*)::int AS n
        FROM staff_actions
        WHERE action_type = ANY($1::text[])
          AND created_at >= NOW() - INTERVAL '90 days'
          AND {human_actor_sql()}
        GROUP BY action_type
        """,
        list(PUNISH),
    )
    added = []
    for row in rows:
        action = row["action_type"]
        title = LABELS.get(action, action)
        inserted = await db.pool.fetchrow(
            """
            INSERT INTO epsilon_deed_rates (action_type, title, every_n, reward_kut, purse, enabled)
            VALUES ($1, $2, 100, 0, 'tech', FALSE)
            ON CONFLICT (action_type) DO NOTHING
            RETURNING action_type
            """,
            action, title,
        )
        if inserted:
            added.append({"actionType": action, "title": title, "seen": int(row["n"])})
    items = await db.pool.fetch(
        "SELECT action_type, title, every_n, reward_kut, purse, enabled FROM epsilon_deed_rates ORDER BY action_type"
    )
    return {"added": added, "items": [_rate_row(r) for r in items]}


def _payout_row(row) -> dict:
    return {
        "id": int(row["id"]),
        "adminId": int(row["admin_id"]),
        "adminName": row["admin_name"] or f"ID {row['admin_id']}",
        "actionType": row["action_type"],
        "actionLabel": LABELS.get(row["action_type"], row["action_type"]),
        "milestone": int(row["milestone"]),
        "rewardKut": int(row["reward_kut"]),
        "purse": row["purse"],
        "status": row["status"],
        "paidAt": row["paid_at"].isoformat() if row["paid_at"] else None,
        "note": row["note"] or "",
    }


@router.get("/payouts")
async def deed_payouts(user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_deed_tables()
    rows = await db.pool.fetch(
        """
        SELECT p.id, p.admin_id, p.action_type, p.milestone, p.reward_kut,
               p.purse, p.status, p.paid_at, p.note,
               COALESCE(NULLIF(u.first_name, ''), NULLIF(u.username, ''), '') AS admin_name
        FROM epsilon_deed_payouts p
        LEFT JOIN users u ON u.user_id = p.admin_id
        ORDER BY CASE WHEN p.status = 'owed' THEN 0 ELSE 1 END, p.id DESC
        LIMIT 40
        """
    )
    return {"items": [_payout_row(r) for r in rows]}


@router.get("/mine")
async def deed_mine(user_id: int = Depends(get_any_telegram_user_id)):
    await ensure_deed_tables()
    rates = await db.pool.fetch(
        """
        SELECT action_type, title, every_n, reward_kut, purse, enabled
        FROM epsilon_deed_rates
        WHERE enabled = TRUE
        ORDER BY action_type
        """
    )
    counts = await db.pool.fetch(
        """
        SELECT s.action_type, COUNT(*)::int AS n
        FROM epsilon_deed_reviews v
        JOIN staff_actions s ON s.id = v.action_id
        WHERE v.status = 'kept' AND s.admin_user_id = $1
          AND (
            COALESCE(v.credits_set, FALSE) = FALSE
            OR EXISTS (
              SELECT 1 FROM epsilon_deed_credits c
              WHERE c.action_id = v.action_id AND c.role = 'issue' AND c.user_id = s.admin_user_id
            )
          )
        GROUP BY s.action_type
        """,
        user_id,
    )
    by_action = {row["action_type"]: int(row["n"]) for row in counts}
    check_rows = await db.pool.fetch(
        """
        SELECT role, COUNT(*)::int AS n
        FROM epsilon_deed_credits
        WHERE user_id = $1 AND role IN ('admin', 'staff')
        GROUP BY role
        """,
        user_id,
    )
    by_role = {row["role"]: int(row["n"]) for row in check_rows}
    is_staff = bool(await db.pool.fetchval(
        """
        SELECT 1 FROM admin_accounts
        WHERE user_id = $1 AND status = 'active' AND role = ANY($2::text[])
        """,
        user_id, list(STAFF_ROLES),
    ))
    waiting = int(await db.pool.fetchval(
        """
        SELECT COUNT(*)::int
        FROM staff_actions s
        LEFT JOIN epsilon_deed_reviews v ON v.action_id = s.id
        WHERE v.action_id IS NULL AND s.admin_user_id = $1
          AND s.action_type = ANY($2::text[])
        """,
        user_id, list(PUNISH),
    ) or 0)
    checks_open = int(await db.pool.fetchval(
        """
        SELECT (
            SELECT COUNT(*)::int
            FROM epsilon_deed_sorts ds
            LEFT JOIN epsilon_deed_reviews v ON v.action_id = ds.action_id
            WHERE ds.sorter_id = $1 AND v.action_id IS NULL
        ) + (
            SELECT COUNT(*)::int
            FROM epsilon_deed_staff st
            LEFT JOIN epsilon_deed_reviews v ON v.action_id = st.action_id
            WHERE st.staff_id = $1 AND v.action_id IS NULL
        )
        """,
        user_id,
    ) or 0)
    dropped = int(await db.pool.fetchval(
        """
        SELECT COUNT(*)::int
        FROM epsilon_deed_reviews v
        JOIN staff_actions s ON s.id = v.action_id
        WHERE v.status = 'dropped' AND s.admin_user_id = $1
        """,
        user_id,
    ) or 0)
    owed_rows = await db.pool.fetch(
        """
        SELECT p.*, COALESCE(u.first_name, u.username, '') AS admin_name
        FROM epsilon_deed_payouts p
        LEFT JOIN users u ON u.user_id = p.admin_id
        WHERE p.admin_id = $1
        ORDER BY p.status, p.id DESC
        LIMIT 30
        """,
        user_id,
    )
    lines = []
    for rate in rates:
        action = rate["action_type"]
        if action == CHECK_ADMIN:
            confirmed = by_role.get("admin", 0)
            if confirmed == 0 and is_staff:
                continue
        elif action == CHECK_STAFF:
            confirmed = by_role.get("staff", 0)
            if confirmed == 0 and not is_staff:
                continue
        else:
            confirmed = by_action.get(action, 0)
        prog = progress_line(confirmed, int(rate["every_n"]), int(rate["reward_kut"]))
        lines.append({**_rate_row(rate), **prog})
    owed_kut = sum(int(r["reward_kut"]) for r in owed_rows if r["status"] == "owed")
    paid_kut = sum(int(r["reward_kut"]) for r in owed_rows if r["status"] == "paid")
    return {
        "lines": lines,
        "waiting": waiting,
        "checksOpen": checks_open,
        "dropped": dropped,
        "owedKut": owed_kut,
        "paidKut": paid_kut,
        "payouts": [_payout_row(r) for r in owed_rows],
    }


def self_claim_gate(row, user_id: int) -> str | None:
    """Пусто — человек может забрать свою техвыплату. Иначе причина отказа."""
    if not row:
        return "Выплаты нет"
    if int(row["admin_id"] or 0) != int(user_id):
        return "Это чужая зарплата"
    if row["status"] != "owed":
        return "Эта выплата уже закрыта"
    purse = row["purse"] if row["purse"] in ("tech", "manual") else "tech"
    if purse != "tech":
        return "Эту сумму отдаёт создатель лично. Напишите ему и договоритесь."
    if int(row["reward_kut"] or 0) <= 0:
        return "Сумма нормы равна нулю"
    return None


@router.post("/mine/{payout_id}/claim")
async def deed_claim(payout_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    """Норма уже засчитана создателем. Человек забирает только свою сумму из технических групп."""
    await ensure_deed_tables()
    audit_ev = None
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, admin_id, action_type, reward_kut, purse, status, milestone
                FROM epsilon_deed_payouts
                WHERE id = $1
                FOR UPDATE
                """,
                int(payout_id),
            )
            why = self_claim_gate(row, user_id)
            if why:
                status = 404 if why == "Выплаты нет" else 403 if why == "Это чужая зарплата" else 409
                raise HTTPException(status_code=status, detail=why)
            reward = int(row["reward_kut"])
            try:
                taken = await _take_technical(conn, reward)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            from staff_payroll import credit_kut_with_audit
            cause = (
                "Зарплата за проверки"
                if row["action_type"] in (CHECK_ADMIN, CHECK_STAFF)
                else "Зарплата за подтверждённые наказания"
            )
            audit_ev = await credit_kut_with_audit(
                conn, int(user_id), reward,
                cause=cause,
                event_type="deed_pay_kut",
                details={
                    "payoutId": int(row["id"]),
                    "action": row["action_type"],
                    "milestone": int(row["milestone"]),
                    "fromTechnical": taken,
                    "self": True,
                },
            )
            note = "Кут с технических групп: " + ", ".join(
                f"{item['amount']} из {item['chatId']}" for item in taken
            )
            await conn.execute(
                """
                UPDATE epsilon_deed_payouts
                SET status = 'paid', paid_at = NOW(), note = $2
                WHERE id = $1 AND admin_id = $3 AND status = 'owed'
                """,
                int(payout_id), note, int(user_id),
            )
    if audit_ev:
        from staff_payroll import schedule_kut_audit
        schedule_kut_audit(audit_ev)
    from admin_audit import log_admin_action
    await log_admin_action(
        user_id,
        "deed_claim",
        target_type="deed_payout",
        target_id=str(payout_id),
        details={"reward": int(row["reward_kut"])},
    )
    return {"ok": True, "id": int(payout_id), "rewardKut": int(row["reward_kut"])}


def _done_item(row) -> dict:
    data = dict(row)
    chain = _chain(data)
    verdict = (data.get("sort_verdict") or "").strip()
    self_verdict = (data.get("self_verdict") or "").strip()
    return {
        "id": int(data["action_id"]),
        "status": data["status"],
        "reviewedAt": data["reviewed_at"].isoformat() if data["reviewed_at"] else None,
        "createdAt": data["created_at"].isoformat() if data["created_at"] else None,
        "actionType": data["action_type"],
        "actionLabel": LABELS.get(data["action_type"], data["action_type"]),
        "adminId": int(data["admin_user_id"] or 0),
        "adminName": data["admin_name"] or "",
        "targetName": data["target_name"] or "",
        "reason": data["reason"] or "",
        "hasProof": bool(data["proof_media_id"]),
        "proofMediaId": data["proof_media_id"] or None,
        "sortVerdict": verdict or None,
        "sortLabel": VERDICT_LABELS.get(verdict, ""),
        "sorterName": (data.get("sorter_name") or "").strip() if verdict else "",
        "selfVerdict": self_verdict or None,
        "selfLabel": VERDICT_LABELS.get(self_verdict, ""),
        "chain": chain,
        "liftStatus": (data.get("lift_status") or "") or None,
        "unclearNames": [],
    }


def _split_sums(rows, field: str) -> dict[str, int]:
    out = {"issue": 0, "admin": 0, "staff": 0}
    for row in rows:
        kind = bucket(row["action_type"])
        if kind:
            out[kind] += int(row[field] or 0)
    out["all"] = out["issue"] + out["admin"] + out["staff"]
    return out


async def _load_tune_inputs(conn):
    purse_row = await conn.fetchrow(PURSE_SQL)
    purse = int(purse_row["purse"] or 0)
    groups = int(purse_row["groups"] or 0)
    owed_rows = await conn.fetch(OWED_SPLIT_SQL)
    owed = _split_sums(owed_rows, "n")
    counts: dict[str, int] = {}
    for row in await conn.fetch(WEEK_ISSUE_SQL):
        counts[row["action"]] = int(row["n"] or 0)
    for row in await conn.fetch(WEEK_CHECK_SQL):
        if row["action"]:
            counts[row["action"]] = int(row["n"] or 0)
    rates = [
        {
            "action": row["action_type"],
            "every_n": int(row["every_n"]),
            "reward": int(row["reward_kut"]),
            "purse": row["purse"],
            "enabled": bool(row["enabled"]),
            "title": row["title"],
        }
        for row in await conn.fetch(
            "SELECT action_type, title, every_n, reward_kut, purse, enabled FROM epsilon_deed_rates"
        )
    ]
    owed_actions = {row["action_type"] for row in owed_rows if int(row["n"] or 0) > 0}
    return purse, groups, owed["all"], counts, rates, owed_actions


async def _apply_tune(conn, *, force: bool) -> bool:
    state = await conn.fetchrow("SELECT auto, tuned_at, purse_kut FROM epsilon_deed_tune WHERE id = 1")
    if not state:
        await conn.execute("INSERT INTO epsilon_deed_tune (id, auto) VALUES (1, TRUE) ON CONFLICT (id) DO NOTHING")
        state = await conn.fetchrow("SELECT auto, tuned_at, purse_kut FROM epsilon_deed_tune WHERE id = 1")
    if not force and not state["auto"]:
        return False
    purse, groups, owed, counts, rates, owed_actions = await _load_tune_inputs(conn)
    fresh = state["tuned_at"] is None
    stale = fresh or state["tuned_at"] < datetime.now(timezone.utc) - timedelta(hours=TUNE_HOURS)
    if not force and not stale and not purse_moved(int(state["purse_kut"] or 0), purse):
        return False
    plan = plan_tune(purse, owed, counts, rates, owed_actions, groups)
    for item in plan["updates"]:
        await conn.execute(
            """
            INSERT INTO epsilon_deed_rates (action_type, title, every_n, reward_kut, purse, enabled)
            VALUES ($1, $2, $3, $4, 'tech', $5)
            ON CONFLICT (action_type) DO UPDATE SET
                reward_kut = EXCLUDED.reward_kut,
                enabled = EXCLUDED.enabled,
                purse = 'tech'
            """,
            item["action"],
            item["title"],
            int(item["every_n"]),
            int(item["reward"]),
            bool(item["enabled"]),
        )
    await conn.execute(
        """
        INSERT INTO epsilon_deed_tune
            (id, auto, tuned_at, scale_num, scale_den, purse_kut, budget_kut, week_cost_kut, note)
        VALUES (1, TRUE, NOW(), $1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE SET
            auto = TRUE,
            tuned_at = NOW(),
            scale_num = EXCLUDED.scale_num,
            scale_den = EXCLUDED.scale_den,
            purse_kut = EXCLUDED.purse_kut,
            budget_kut = EXCLUDED.budget_kut,
            week_cost_kut = EXCLUDED.week_cost_kut,
            note = EXCLUDED.note
        """,
        int(plan["num"]),
        int(plan["den"]),
        int(purse),
        int(plan["budget"]),
        int(plan["full"]),
        plan["note"],
    )
    await _sync_owed(conn)
    return True


def _rate_view(row) -> dict:
    every = int(row["every_n"])
    reward = int(row["reward_kut"])
    ideal = IDEAL.get(row["action_type"])
    ideal_reward = reward_for_row(every, ideal) if ideal else reward
    return {
        "actionType": row["action_type"],
        "title": row["title"],
        "everyN": every,
        "rewardKut": reward,
        "enabled": bool(row["enabled"]),
        "purse": row["purse"] if row["purse"] in ("tech", "manual") else "tech",
        "unit": unit_text(every, reward),
        "idealUnit": unit_text(ideal[0], ideal[1]) if ideal else "",
        "idealReward": ideal_reward,
    }


def reward_for_row(every: int, ideal: tuple) -> int:
    from deed_tune import reward_for
    return reward_for(every, ideal[0], ideal[1], 1, 1)


async def _analytics_body(conn) -> dict:
    purse_row = await conn.fetchrow(PURSE_SQL)
    purse = int(purse_row["purse"] or 0)
    groups = int(purse_row["groups"] or 0)
    paid_rows = await conn.fetch(PAID_SPLIT_SQL)
    paid_all = _split_sums(paid_rows, "all_n")
    paid_week = _split_sums(paid_rows, "week_n")
    paid_month = _split_sums(paid_rows, "month_n")
    owed = _split_sums(await conn.fetch(OWED_SPLIT_SQL), "n")
    manual = int((await conn.fetchrow(MANUAL_PAID_SQL))["n"] or 0)
    days = fill_days([dict(row) for row in await conn.fetch(DAYS_SQL)], datetime.now(timezone.utc).date())
    people = []
    for row in await conn.fetch(PEOPLE_SQL):
        issue = int(row["issue_paid"] or 0)
        admin = int(row["admin_paid"] or 0)
        staff = int(row["staff_paid"] or 0)
        if issue + admin + staff + int(row["owed"] or 0) <= 0:
            continue
        people.append({
            "id": int(row["admin_id"]),
            "name": (row["name"] or "").strip() or f"ID {int(row['admin_id'])}",
            "issue": issue,
            "admin": admin,
            "staff": staff,
            "paid": issue + admin + staff,
            "owed": int(row["owed"] or 0),
        })
    tune = await conn.fetchrow(
        "SELECT auto, tuned_at, scale_num, scale_den, budget_kut, note FROM epsilon_deed_tune WHERE id = 1"
    )
    rates = [
        _rate_view(row)
        for row in await conn.fetch(
            "SELECT action_type, title, every_n, reward_kut, purse, enabled FROM epsilon_deed_rates ORDER BY action_type"
        )
    ]
    room_budget = int(tune["budget_kut"] or 0) if tune else 0
    return {
        "purse": purse,
        "groups": groups,
        "reserve": purse * 2 // 5,
        "weekBudget": room_budget,
        "paid": {"all": paid_all, "week": paid_week, "month": paid_month},
        "owed": owed,
        "manualPaid": manual,
        "days": days,
        "people": people,
        "tune": {
            "auto": bool(tune["auto"]) if tune else True,
            "tunedAt": tune["tuned_at"].isoformat() if tune and tune["tuned_at"] else None,
            "scaleNum": int(tune["scale_num"] or 1) if tune else 1,
            "scaleDen": int(tune["scale_den"] or 1) if tune else 1,
            "note": (tune["note"] if tune else "") or "",
        },
        "rates": rates,
    }


class TuneBody(BaseModel):
    auto: bool = True
    now: bool = True


@router.get("/analytics")
async def deed_analytics(user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_deed_tables()
    changed = False
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            changed = await _apply_tune(conn, force=False)
        body = await _analytics_body(conn)
    body["tunedNow"] = changed
    return body


@router.post("/rates/tune")
async def deed_tune_now(body: TuneBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_deed_tables()
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            if not body.auto:
                await conn.execute(
                    """
                    INSERT INTO epsilon_deed_tune (id, auto)
                    VALUES (1, FALSE)
                    ON CONFLICT (id) DO UPDATE SET auto = FALSE
                    """
                )
            elif body.now:
                await _apply_tune(conn, force=True)
            else:
                await conn.execute(
                    """
                    INSERT INTO epsilon_deed_tune (id, auto)
                    VALUES (1, TRUE)
                    ON CONFLICT (id) DO UPDATE SET auto = TRUE
                    """
                )
        result = await _analytics_body(conn)
    result["tunedNow"] = bool(body.auto and body.now)
    return result


@router.get("/done")
async def deed_done(
    sort: str = Query(default="new"),
    action: str = Query(default=""),
    adminId: int = Query(default=0),
    sorterId: int = Query(default=0),
    status: str = Query(default=""),
    user_id: int = Depends(get_any_telegram_user_id),
):
    _require_creator(user_id)
    await ensure_deed_tables()
    order = {
        "new": "v.reviewed_at DESC, v.action_id DESC",
        "old": "v.reviewed_at ASC, v.action_id ASC",
        "admin": "s.admin_name ASC, v.reviewed_at DESC",
        "action": "s.action_type ASC, v.reviewed_at DESC",
    }.get(sort, "v.reviewed_at DESC, v.action_id DESC")
    params: list[Any] = []
    parts = ["1=1", human_actor_sql("s")]
    if action.strip().lower() in PUNISH:
        params.append(action.strip().lower())
        parts.append(f"s.action_type = ${len(params)}")
    if adminId:
        params.append(int(adminId))
        parts.append(f"s.admin_user_id = ${len(params)}")
    if status in ("kept", "dropped"):
        params.append(status)
        parts.append(f"v.status = ${len(params)}")
    if sorterId:
        params.append(int(sorterId))
        parts.append(_by_person(len(params), "v.action_id"))
    rows = await db.pool.fetch(
        f"""
        SELECT v.action_id, v.status, v.reviewed_at, v.self_verdict,
               s.action_type, s.admin_user_id, s.admin_name, s.target_name,
               s.reason, s.created_at, s.proof_media_id,
               ds.verdict AS sort_verdict, ds.sorter_id,
               COALESCE(NULLIF(btrim(su.first_name), ''), NULLIF(btrim(su.username), ''), '') AS sorter_name,
               st.verdict AS staff_verdict, st.staff_id, st.lift_ask, st.lift_status,
               COALESCE(NULLIF(btrim(stu.first_name), ''), NULLIF(btrim(stu.username), ''), '') AS staff_name
        FROM epsilon_deed_reviews v
        JOIN staff_actions s ON s.id = v.action_id
        LEFT JOIN epsilon_deed_sorts ds ON ds.action_id = v.action_id
        LEFT JOIN users su ON su.user_id = ds.sorter_id
        LEFT JOIN epsilon_deed_staff st ON st.action_id = v.action_id
        LEFT JOIN users stu ON stu.user_id = st.staff_id
        WHERE {' AND '.join(parts)}
        ORDER BY {order}
        LIMIT 40
        """,
        *params,
    )
    return {"items": [_done_item(r) for r in rows]}


async def _take_technical(conn, amount: int) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT chat_id, COALESCE(chatbalance, 0) AS bal
        FROM chat
        WHERE COALESCE(is_technical, FALSE) = TRUE
          AND COALESCE(chatbalance, 0) > 0
        ORDER BY chatbalance DESC
        FOR UPDATE
        """
    )
    plan = plan_take([(int(r["chat_id"]), int(r["bal"])) for r in rows], amount)
    taken = []
    for chat_id, bite in plan:
        await conn.execute(
            "UPDATE chat SET chatbalance = chatbalance - $2 WHERE chat_id = $1",
            chat_id, bite,
        )
        taken.append({"chatId": chat_id, "amount": bite})
    return taken


@router.post("/payouts/{payout_id}/pay")
async def deed_pay(payout_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_deed_tables()
    audit_ev = None
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, admin_id, action_type, reward_kut, purse, status, milestone
                FROM epsilon_deed_payouts
                WHERE id = $1
                FOR UPDATE
                """,
                payout_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Выплаты нет")
            if row["status"] != "owed":
                raise HTTPException(status_code=409, detail="Эта выплата уже закрыта")
            reward = int(row["reward_kut"])
            if reward <= 0:
                raise HTTPException(status_code=400, detail="Сумма нормы равна нулю")
            purse = row["purse"] if row["purse"] in ("tech", "manual") else "tech"
            note = ""
            if purse == "tech":
                try:
                    taken = await _take_technical(conn, reward)
                except ValueError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                from staff_payroll import credit_kut_with_audit
                cause = (
                    "Зарплата за проверки"
                    if row["action_type"] in (CHECK_ADMIN, CHECK_STAFF)
                    else "Зарплата за подтверждённые наказания"
                )
                audit_ev = await credit_kut_with_audit(
                    conn, int(row["admin_id"]), reward,
                    cause=cause,
                    event_type="deed_pay_kut",
                    details={
                        "payoutId": int(row["id"]),
                        "action": row["action_type"],
                        "milestone": int(row["milestone"]),
                        "fromTechnical": taken,
                    },
                )
                note = "Кут с технических групп: " + ", ".join(
                    f"{item['amount']} из {item['chatId']}" for item in taken
                )
            else:
                note = "Создатель отметил выплату лично, без списания кут."
            await conn.execute(
                """
                UPDATE epsilon_deed_payouts
                SET status = 'paid', paid_at = NOW(), note = $2
                WHERE id = $1
                """,
                payout_id, note,
            )
    if audit_ev:
        from staff_payroll import schedule_kut_audit
        schedule_kut_audit(audit_ev)
    from admin_audit import log_admin_action
    await log_admin_action(
        user_id,
        "deed_pay",
        target_type="deed_payout",
        target_id=str(payout_id),
        details={"purse": purse},
    )
    return {"ok": True, "id": payout_id, "note": note}
