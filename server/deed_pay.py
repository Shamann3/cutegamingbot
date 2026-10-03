"""Оплата администратору за подтверждённые наказания.

Очередь берётся из архива staff_actions (бан, мут, кик, предупреждение).
Создатель подтверждает или отклоняет каждую карточку. В зарплату входит
только подтверждённое. Куты списываются с технических групп.

Нормы и суммы задаёт создатель. Сбор заданий только предлагает типы,
которые уже есть в архиве, и не включает выплату сам.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from admin_auth import get_any_telegram_user_id
from admin_soft_restart import is_project_creator
from db import db

router = APIRouter(prefix="/deed-pay", tags=["deed-pay"])

PUNISH = ("ban", "mute", "kick", "warn")
LABELS = {
    "ban": "Бан",
    "mute": "Мут",
    "kick": "Кик",
    "warn": "Предупреждение",
}
SCOPE_LABELS = {
    "chat": "одна группа",
    "all": "официальные группы",
    "full": "весь проект",
}
# Стартовые нормы. Включаются сразу: создатель видит живые цифры и может
# поменять их до первой выплаты. Сумма не уходит, пока он не подтвердит дела
# и не нажмёт «Выплатить».
SEED = (
    ("ban", "Баны", 100, 200),
    ("mute", "Муты", 50, 80),
    ("kick", "Кики", 40, 60),
    ("warn", "Предупреждения", 80, 50),
)
SORTS = {
    "new": "s.created_at DESC, s.id DESC",
    "old": "s.created_at ASC, s.id ASC",
    "admin": "s.admin_name ASC, s.created_at DESC, s.id DESC",
    "action": "s.action_type ASC, s.created_at DESC, s.id DESC",
}
_READY = False


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


async def ensure_deed_tables() -> None:
    global _READY
    if _READY:
        return
    await db.pool.execute(
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
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_deed_reviews (
            action_id BIGINT PRIMARY KEY,
            status TEXT NOT NULL,
            reviewer_id BIGINT NOT NULL,
            reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await db.pool.execute(
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
    for action, title, every_n, reward in SEED:
        await db.pool.execute(
            """
            INSERT INTO epsilon_deed_rates (action_type, title, every_n, reward_kut, purse, enabled)
            VALUES ($1, $2, $3, $4, 'tech', TRUE)
            ON CONFLICT (action_type) DO NOTHING
            """,
            action, title, every_n, reward,
        )
    _READY = True


def _sort(name: str) -> str:
    return SORTS.get(str(name or "new").strip().lower(), SORTS["new"])


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


def _card(row, history: list[dict]) -> dict[str, Any]:
    action = row["action_type"]
    scope = row["scope"] or ("chat" if row["chat_id"] else "all")
    minutes = row["duration_minutes"]
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
    }


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
    (
        SELECT COUNT(*)::int FROM staff_actions h
        WHERE h.target_player_id = s.target_player_id
          AND h.action_type IN ('ban', 'mute', 'kick', 'warn', 'unban', 'unmute', 'unwarn')
    ) AS archive_count
"""


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
        """
        SELECT id, created_at, action_type, reason, admin_name
        FROM staff_actions
        WHERE target_player_id = $1
          AND action_type IN ('ban', 'mute', 'kick', 'warn', 'unban', 'unmute', 'unwarn')
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
    for rate in rates:
        action = rate["action_type"]
        every_n = int(rate["every_n"])
        reward = int(rate["reward_kut"])
        purse = rate["purse"] if rate["purse"] in ("tech", "manual") else "tech"
        counts = await conn.fetch(
            """
            SELECT s.admin_user_id AS admin_id, COUNT(*)::int AS n
            FROM epsilon_deed_reviews v
            JOIN staff_actions s ON s.id = v.action_id
            WHERE v.status = 'kept' AND s.action_type = $1 AND s.admin_user_id IS NOT NULL
            GROUP BY s.admin_user_id
            """,
            action,
        )
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


class RateBody(BaseModel):
    actionType: str
    title: str = ""
    everyN: int = Field(ge=1, le=100000)
    rewardKut: int = Field(ge=0, le=10**12)
    purse: str = "tech"
    enabled: bool = False


class RatesBody(BaseModel):
    items: list[RateBody]


def _filters(action: str, admin_id: int) -> tuple[str, list[Any]]:
    params: list[Any] = [list(PUNISH)]
    parts = [
        "v.action_id IS NULL",
        "s.action_type = ANY($1::text[])",
    ]
    picked = action.strip().lower()
    if picked in PUNISH:
        params.append(picked)
        parts.append(f"s.action_type = ${len(params)}")
    if admin_id:
        params.append(int(admin_id))
        parts.append(f"s.admin_user_id = ${len(params)}")
    return " AND ".join(parts), params


@router.get("/queue")
async def deed_queue(
    sort: str = Query(default="new"),
    action: str = Query(default=""),
    adminId: int = Query(default=0),
    user_id: int = Depends(get_any_telegram_user_id),
):
    _require_creator(user_id)
    await ensure_deed_tables()
    where, params = _filters(action, adminId)
    waiting = int(await db.pool.fetchval(
        f"""
        SELECT COUNT(*)::int
        FROM staff_actions s
        LEFT JOIN epsilon_deed_reviews v ON v.action_id = s.id
        WHERE {where}
        """,
        *params,
    ) or 0)
    admins = await db.pool.fetch(
        f"""
        SELECT s.admin_user_id AS id, MAX(s.admin_name) AS name, COUNT(*)::int AS n
        FROM staff_actions s
        LEFT JOIN epsilon_deed_reviews v ON v.action_id = s.id
        WHERE v.action_id IS NULL AND s.action_type = ANY($1::text[])
        GROUP BY s.admin_user_id
        ORDER BY n DESC
        LIMIT 40
        """,
        list(PUNISH),
    )
    row = await db.pool.fetchrow(
        f"""
        SELECT {_CARD_SQL}
        FROM staff_actions s
        LEFT JOIN epsilon_deed_reviews v ON v.action_id = s.id
        LEFT JOIN chat c ON c.chat_id = s.chat_id
        LEFT JOIN users tu ON tu.user_id = s.target_player_id
        LEFT JOIN users au ON au.user_id = s.admin_user_id
        LEFT JOIN epsilon_deed_rates r ON r.action_type = s.action_type
        WHERE {where}
        ORDER BY {_sort(sort)}
        LIMIT 1
        """,
        *params,
    )
    card = None
    if row:
        shaped = _name_fields(row)
        card = _card(shaped, await _history(shaped.get("target_player_id")))
    return {
        "waiting": waiting,
        "card": card,
        "admins": [
            {"id": int(a["id"] or 0), "name": a["name"] or f"ID {a['id']}", "waiting": int(a["n"])}
            for a in admins
        ],
    }


async def _decide(action_id: int, reviewer_id: int, status: str) -> dict:
    await ensure_deed_tables()
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            src = await conn.fetchrow(
                """
                SELECT id, action_type, admin_user_id
                FROM staff_actions
                WHERE id = $1 AND action_type = ANY($2::text[])
                """,
                action_id, list(PUNISH),
            )
            if not src:
                raise HTTPException(status_code=404, detail="В архиве такой записи нет")
            inserted = await conn.fetchrow(
                """
                INSERT INTO epsilon_deed_reviews (action_id, status, reviewer_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (action_id) DO NOTHING
                RETURNING action_id
                """,
                action_id, status, reviewer_id,
            )
            if not inserted:
                raise HTTPException(status_code=409, detail="Это наказание уже разобрано")
            if status == "kept":
                await _sync_owed(conn)
    from admin_audit import log_admin_action
    await log_admin_action(
        reviewer_id,
        "deed_keep" if status == "kept" else "deed_drop",
        target_type="staff_action",
        target_id=str(action_id),
        details={"status": status},
    )
    return {"ok": True, "id": action_id, "status": status}


@router.post("/queue/{action_id}/keep")
async def deed_keep(action_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    return await _decide(action_id, user_id, "kept")


@router.post("/queue/{action_id}/drop")
async def deed_drop(action_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    return await _decide(action_id, user_id, "dropped")


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


def _rate_row(row) -> dict:
    return {
        "actionType": row["action_type"],
        "title": row["title"] or LABELS.get(row["action_type"], row["action_type"]),
        "everyN": int(row["every_n"]),
        "rewardKut": int(row["reward_kut"]),
        "purse": row["purse"] if row["purse"] in ("tech", "manual") else "tech",
        "enabled": bool(row["enabled"]),
    }


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
            await _sync_owed(conn)
    return await deed_rates(user_id)


@router.post("/rates/collect")
async def deed_collect(user_id: int = Depends(get_any_telegram_user_id)):
    """Предложить задания по типам, которые уже встречаются в архиве."""
    _require_creator(user_id)
    await ensure_deed_tables()
    rows = await db.pool.fetch(
        """
        SELECT action_type, COUNT(*)::int AS n
        FROM staff_actions
        WHERE action_type = ANY($1::text[])
          AND created_at >= NOW() - INTERVAL '90 days'
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
        GROUP BY s.action_type
        """,
        user_id,
    )
    by_action = {row["action_type"]: int(row["n"]) for row in counts}
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
        prog = progress_line(by_action.get(rate["action_type"], 0), int(rate["every_n"]), int(rate["reward_kut"]))
        lines.append({**_rate_row(rate), **prog})
    owed_kut = sum(int(r["reward_kut"]) for r in owed_rows if r["status"] == "owed")
    paid_kut = sum(int(r["reward_kut"]) for r in owed_rows if r["status"] == "paid")
    return {
        "lines": lines,
        "waiting": waiting,
        "dropped": dropped,
        "owedKut": owed_kut,
        "paidKut": paid_kut,
        "payouts": [_payout_row(r) for r in owed_rows],
    }


@router.get("/done")
async def deed_done(
    sort: str = Query(default="new"),
    action: str = Query(default=""),
    adminId: int = Query(default=0),
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
    parts = ["1=1"]
    if action.strip().lower() in PUNISH:
        params.append(action.strip().lower())
        parts.append(f"s.action_type = ${len(params)}")
    if adminId:
        params.append(int(adminId))
        parts.append(f"s.admin_user_id = ${len(params)}")
    if status in ("kept", "dropped"):
        params.append(status)
        parts.append(f"v.status = ${len(params)}")
    rows = await db.pool.fetch(
        f"""
        SELECT v.action_id, v.status, v.reviewed_at,
               s.action_type, s.admin_user_id, s.admin_name, s.target_name,
               s.reason, s.created_at
        FROM epsilon_deed_reviews v
        JOIN staff_actions s ON s.id = v.action_id
        WHERE {' AND '.join(parts)}
        ORDER BY {order}
        LIMIT 40
        """,
        *params,
    )
    return {
        "items": [
            {
                "id": int(r["action_id"]),
                "status": r["status"],
                "reviewedAt": r["reviewed_at"].isoformat() if r["reviewed_at"] else None,
                "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
                "actionType": r["action_type"],
                "actionLabel": LABELS.get(r["action_type"], r["action_type"]),
                "adminId": int(r["admin_user_id"] or 0),
                "adminName": r["admin_name"] or "",
                "targetName": r["target_name"] or "",
                "reason": r["reason"] or "",
            }
            for r in rows
        ]
    }


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
                audit_ev = await credit_kut_with_audit(
                    conn, int(row["admin_id"]), reward,
                    cause="Зарплата за подтверждённые наказания",
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
