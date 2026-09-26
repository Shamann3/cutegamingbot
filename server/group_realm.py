"""Контур администраторов групп.

Официальная группа, должность и права решают, что человек видит.
Сотрудник проекта этим местом не становится.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admin_auth import get_any_telegram_user_id
from config import owner_user_ids
from db import db

router = APIRouter(prefix="/group-realm", tags=["group-realm"])

_READY = False

ALL_RIGHTS = (
    "view_members",
    "view_archive",
    "view_analytics",
    "punish_mute",
    "punish_ban",
    "punish_kick",
    "punish_warn",
    "punish_voice",
    "manage_positions",
)

ACTION_RIGHT = {
    "mute": "punish_mute",
    "unmute": "punish_mute",
    "kick": "punish_kick",
    "warn": "punish_warn",
    "ban": "punish_ban",
    "unban": "punish_ban",
}

LOCAL_ACTIONS = frozenset(ACTION_RIGHT)

PRESETS: tuple[tuple[str, int, tuple[str, ...], bool], ...] = (
    ("Создатель группы", 5, ALL_RIGHTS, False),
    (
        "Администратор",
        3,
        tuple(r for r in ALL_RIGHTS if r != "manage_positions"),
        True,
    ),
    (
        "Модератор",
        2,
        ("view_members", "view_archive", "punish_mute", "punish_kick", "punish_warn"),
        True,
    ),
    ("Хелпер", 1, ("view_members", "punish_warn"), True),
)


def action_right(action: str) -> str | None:
    return ACTION_RIGHT.get((action or "").strip().lower())


def rights_allow(rights: list[str] | set[str], action: str) -> bool:
    need = action_right(action)
    return bool(need) and need in set(rights or [])


def may_edit_position(actor_rank: int, position_rank: int, *, creator: bool) -> bool:
    """Создатель правит любую должность. Остальные — только строго младшую."""
    if creator:
        return True
    return int(position_rank) < int(actor_rank)


def editable_rights(rank: int, requested: list[str] | set[str], *, creator: bool) -> list[str]:
    """Должность создателя группы всегда держит полный набор прав."""
    if int(rank) >= 5:
        return list(ALL_RIGHTS)
    clean = _rights(requested)
    if not creator:
        clean = [item for item in clean if item != "manage_positions"]
    return clean


def may_punish_rank(actor_rank: int, target_rank: int, *, same_person: bool) -> str | None:
    """Наказать можно только того, кто строго младше в этой группе.

    Нет должности — ранг 0, такой человек младше любого администратора.
    Равный и старший не проходят. Себя наказать нельзя.
    """
    if same_person:
        return "Себя наказать нельзя"
    if int(target_rank) >= int(actor_rank):
        return "Наказать можно только того, кто младше вашей должности в этой группе"
    return None


async def ensure_tables() -> None:
    global _READY
    if _READY:
        return
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS epsilon_official_groups (
            chat_id BIGINT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            username TEXT NOT NULL DEFAULT '',
            is_official BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS epsilon_positions (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            title TEXT NOT NULL,
            rank INT NOT NULL,
            rights JSONB NOT NULL DEFAULT '[]',
            accepting BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE INDEX IF NOT EXISTS epsilon_positions_chat_idx
            ON epsilon_positions (chat_id, rank DESC);
        CREATE TABLE IF NOT EXISTS epsilon_seats (
            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            position_id INT NOT NULL,
            appointed_by BIGINT,
            reason TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, chat_id)
        );
        CREATE TABLE IF NOT EXISTS epsilon_group_applications (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            position_id INT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            rules_read BOOLEAN NOT NULL DEFAULT FALSE,
            status TEXT NOT NULL DEFAULT 'pending',
            review_note TEXT NOT NULL DEFAULT '',
            reviewer_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            decided_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS epsilon_group_app_user_idx
            ON epsilon_group_applications (user_id, status);
        CREATE TABLE IF NOT EXISTS epsilon_group_keys (
            user_id BIGINT PRIMARY KEY,
            key_hash TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    _READY = True


def _is_creator(user_id: int) -> bool:
    return int(user_id) in set(owner_user_ids())


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_key() -> tuple[str, str]:
    plain = secrets.token_urlsafe(18)
    return plain, _hash_key(plain)


async def _issue_key(user_id: int) -> str:
    plain, hashed = _new_key()
    await db.pool.execute(
        """
        INSERT INTO epsilon_group_keys (user_id, key_hash)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE SET key_hash = EXCLUDED.key_hash, updated_at = NOW()
        """,
        int(user_id),
        hashed,
    )
    return plain


def _rights(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError:
            raw = []
    else:
        raw = []
    allowed = set(ALL_RIGHTS)
    return [str(item) for item in raw if str(item) in allowed]


async def _seed_positions(chat_id: int) -> None:
    count = await db.pool.fetchval(
        "SELECT COUNT(*)::int FROM epsilon_positions WHERE chat_id = $1",
        int(chat_id),
    )
    if int(count or 0) > 0:
        return
    for title, rank, rights, accepting in PRESETS:
        await db.pool.execute(
            """
            INSERT INTO epsilon_positions (chat_id, title, rank, rights, accepting)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            """,
            int(chat_id),
            title,
            int(rank),
            json.dumps(list(rights)),
            bool(accepting),
        )


async def seats_for(user_id: int) -> list[dict]:
    """Группы, куда этот человек может войти, и права должности."""
    try:
        await ensure_tables()
    except Exception:
        return []
    if _is_creator(user_id):
        rows = await db.pool.fetch(
            """
            SELECT chat_id, title, username
            FROM epsilon_official_groups
            WHERE is_official = TRUE
            ORDER BY title, chat_id
            """
        )
        return [
            {
                "chatId": int(r["chat_id"]),
                "title": r["title"] or str(r["chat_id"]),
                "username": r["username"] or "",
                "position": "Создатель",
                "rank": 5,
                "rights": list(ALL_RIGHTS),
            }
            for r in rows
        ]
    rows = await db.pool.fetch(
        """
        SELECT s.chat_id, g.title, g.username, p.title AS position, p.rank, p.rights
        FROM epsilon_seats s
        JOIN epsilon_official_groups g ON g.chat_id = s.chat_id AND g.is_official
        JOIN epsilon_positions p ON p.id = s.position_id
        WHERE s.user_id = $1
        ORDER BY p.rank DESC, g.title
        """,
        int(user_id),
    )
    return [
        {
            "chatId": int(r["chat_id"]),
            "title": r["title"] or str(r["chat_id"]),
            "username": r["username"] or "",
            "position": r["position"],
            "rank": int(r["rank"]),
            "rights": _rights(r["rights"]),
        }
        for r in rows
    ]


async def _seat_rank(user_id: int, chat_id: int) -> int:
    """Ранг должности в этом чате. Создатель проекта — 5. Без места — 0."""
    if _is_creator(user_id):
        return 5
    row = await db.pool.fetchrow(
        """
        SELECT p.rank
        FROM epsilon_seats s
        JOIN epsilon_positions p ON p.id = s.position_id
        WHERE s.user_id = $1 AND s.chat_id = $2
        """,
        int(user_id),
        int(chat_id),
    )
    if not row:
        return 0
    return int(row["rank"])


async def _access(user_id: int, chat_id: int) -> dict | None:
    groups = await seats_for(user_id)
    for group in groups:
        if int(group["chatId"]) == int(chat_id):
            return group
    return None


def _require_creator(user_id: int) -> None:
    if not _is_creator(user_id):
        raise HTTPException(status_code=403, detail="Только создатель проекта отмечает группы и должности")


class OfficialBody(BaseModel):
    chat_id: int
    title: str = ""
    username: str = ""
    official: bool = True
    model_config = {"extra": "forbid"}


class PositionEditBody(BaseModel):
    title: str = Field(min_length=2, max_length=40)
    rights: list[str] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class AppointBody(BaseModel):
    chat_id: int
    user_id: int = Field(ge=1)
    position_id: int = Field(ge=1)
    reason: str = Field(default="", max_length=300)
    model_config = {"extra": "forbid"}


class ApplyBody(BaseModel):
    chat_id: int
    position_id: int = Field(ge=1)
    body: str = Field(min_length=20, max_length=2000)
    rules_read: bool
    model_config = {"extra": "forbid"}


class DecideBody(BaseModel):
    application_id: int = Field(ge=1)
    approve: bool
    position_id: int | None = Field(default=None, ge=1)
    note: str = Field(default="", max_length=500)
    model_config = {"extra": "forbid"}


class ActBody(BaseModel):
    chat_id: int
    user_id: int = Field(ge=1)
    action: str = Field(min_length=2, max_length=24)
    until_sec: int | None = Field(default=None, ge=1, le=366 * 24 * 3600)
    reason: str = Field(default="", max_length=200)
    model_config = {"extra": "forbid"}


class KeyBody(BaseModel):
    key: str = Field(min_length=8, max_length=200)
    model_config = {"extra": "forbid"}


@router.get("/open")
async def group_open(user_id: int = Depends(get_any_telegram_user_id)):
    await ensure_tables()
    rows = await db.pool.fetch(
        """
        SELECT g.chat_id, g.title, g.username, p.id AS position_id, p.title AS position, p.rank, p.rights
        FROM epsilon_official_groups g
        JOIN epsilon_positions p ON p.chat_id = g.chat_id
        WHERE g.is_official AND p.accepting AND p.rank < 5
        ORDER BY g.title, p.rank DESC
        """
    )
    mine = await db.pool.fetch(
        """
        SELECT id, chat_id, position_id, status, review_note, created_at
        FROM epsilon_group_applications
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 12
        """,
        int(user_id),
    )
    return {
        "positions": [
            {
                "chatId": int(r["chat_id"]),
                "title": r["title"] or str(r["chat_id"]),
                "username": r["username"] or "",
                "positionId": int(r["position_id"]),
                "position": r["position"],
                "rank": int(r["rank"]),
                "rights": _rights(r["rights"]),
            }
            for r in rows
        ],
        "mine": [
            {
                "id": int(r["id"]),
                "chatId": int(r["chat_id"]),
                "positionId": int(r["position_id"]),
                "status": r["status"],
                "note": r["review_note"] or "",
                "at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in mine
        ],
    }


@router.post("/apply")
async def group_apply(body: ApplyBody, user_id: int = Depends(get_any_telegram_user_id)):
    await ensure_tables()
    if not body.rules_read:
        raise HTTPException(status_code=400, detail="Сначала прочитайте правила CuteRules")
    pos = await db.pool.fetchrow(
        """
        SELECT p.id, p.rank, p.accepting, g.is_official
        FROM epsilon_positions p
        JOIN epsilon_official_groups g ON g.chat_id = p.chat_id
        WHERE p.id = $1 AND p.chat_id = $2
        """,
        int(body.position_id),
        int(body.chat_id),
    )
    if not pos or not pos["is_official"] or not pos["accepting"] or int(pos["rank"]) >= 5:
        raise HTTPException(status_code=400, detail="На эту должность набор закрыт")
    seat = await db.pool.fetchval(
        "SELECT 1 FROM epsilon_seats WHERE user_id = $1 AND chat_id = $2",
        int(user_id),
        int(body.chat_id),
    )
    if seat:
        raise HTTPException(status_code=409, detail="Вы уже администратор этой группы")
    pending = await db.pool.fetchval(
        """
        SELECT 1 FROM epsilon_group_applications
        WHERE user_id = $1 AND chat_id = $2 AND status = 'pending'
        """,
        int(user_id),
        int(body.chat_id),
    )
    if pending:
        raise HTTPException(status_code=409, detail="Заявка в эту группу уже на рассмотрении")
    recent_reject = await db.pool.fetchval(
        """
        SELECT decided_at FROM epsilon_group_applications
        WHERE user_id = $1 AND chat_id = $2 AND status = 'rejected'
        ORDER BY decided_at DESC NULLS LAST
        LIMIT 1
        """,
        int(user_id),
        int(body.chat_id),
    )
    if recent_reject:
        if recent_reject.tzinfo is None:
            recent_reject = recent_reject.replace(tzinfo=timezone.utc)
        if recent_reject > datetime.now(timezone.utc) - timedelta(days=7):
            raise HTTPException(status_code=409, detail="Повторная заявка в эту группу откроется через 7 дней после отказа")
    app_id = await db.pool.fetchval(
        """
        INSERT INTO epsilon_group_applications
            (user_id, chat_id, position_id, body, rules_read, status)
        VALUES ($1, $2, $3, $4, TRUE, 'pending')
        RETURNING id
        """,
        int(user_id),
        int(body.chat_id),
        int(body.position_id),
        body.body.strip(),
    )
    return {"ok": True, "id": int(app_id)}


@router.post("/official")
async def group_official(body: OfficialBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    await db.pool.execute(
        """
        INSERT INTO epsilon_official_groups (chat_id, title, username, is_official)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chat_id) DO UPDATE
        SET title = EXCLUDED.title,
            username = EXCLUDED.username,
            is_official = EXCLUDED.is_official
        """,
        int(body.chat_id),
        (body.title or str(body.chat_id))[:120],
        body.username.lstrip("@")[:64],
        bool(body.official),
    )
    if body.official:
        await _seed_positions(int(body.chat_id))
    return {"ok": True, "chatId": int(body.chat_id), "official": bool(body.official)}


async def _can_edit_positions(user_id: int, chat_id: int) -> dict | None:
    if _is_creator(user_id):
        return {"rank": 5, "creator": True}
    access = await _access(user_id, chat_id)
    if not access or "manage_positions" not in set(access["rights"]):
        return None
    return {"rank": int(access["rank"]), "creator": False}


@router.get("/board")
async def rights_board(user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    groups = await seats_for(user_id)
    payload = []
    for group in groups:
        rows = await db.pool.fetch(
            """
            SELECT id, title, rank, rights, accepting
            FROM epsilon_positions
            WHERE chat_id = $1
            ORDER BY rank DESC, id
            """,
            int(group["chatId"]),
        )
        payload.append({
            **group,
            "positions": [
                {
                    "id": int(r["id"]),
                    "title": r["title"],
                    "rank": int(r["rank"]),
                    "rights": _rights(r["rights"]),
                    "accepting": bool(r["accepting"]),
                }
                for r in rows
            ],
        })
    return {"groups": payload}


@router.get("/positions/{chat_id}")
async def group_positions(chat_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    if not await _can_edit_positions(user_id, chat_id):
        raise HTTPException(status_code=403, detail="Права должностей этой группы вам не открыты")
    await ensure_tables()
    rows = await db.pool.fetch(
        """
        SELECT id, title, rank, rights, accepting
        FROM epsilon_positions
        WHERE chat_id = $1
        ORDER BY rank DESC, id
        """,
        int(chat_id),
    )
    return {
        "positions": [
            {
                "id": int(r["id"]),
                "title": r["title"],
                "rank": int(r["rank"]),
                "rights": _rights(r["rights"]),
                "accepting": bool(r["accepting"]),
            }
            for r in rows
        ]
    }


@router.post("/positions/{position_id}")
async def edit_position(
    position_id: int,
    body: PositionEditBody,
    user_id: int = Depends(get_any_telegram_user_id),
):
    await ensure_tables()
    row = await db.pool.fetchrow(
        """
        SELECT p.id, p.chat_id, p.rank
        FROM epsilon_positions p
        JOIN epsilon_official_groups g ON g.chat_id = p.chat_id AND g.is_official
        WHERE p.id = $1
        """,
        int(position_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Такой должности нет")
    actor = await _can_edit_positions(user_id, int(row["chat_id"]))
    if not actor or not may_edit_position(actor["rank"], int(row["rank"]), creator=actor["creator"]):
        raise HTTPException(status_code=403, detail="Эту должность может менять только тот, кто старше неё")
    title = " ".join(body.title.split())
    rights = editable_rights(int(row["rank"]), body.rights, creator=actor["creator"])
    await db.pool.execute(
        """
        UPDATE epsilon_positions
        SET title = $2, rights = $3::jsonb
        WHERE id = $1
        """,
        int(position_id),
        title,
        json.dumps(rights),
    )
    return {"ok": True, "id": int(position_id), "title": title, "rights": rights}


async def drop_group_access(user_id: int) -> dict:
    """Снимает места и личный ключ. Следующий вход потребует новый ключ."""
    await ensure_tables()
    seats = await db.pool.execute(
        "DELETE FROM epsilon_seats WHERE user_id = $1",
        int(user_id),
    )
    keys = await db.pool.execute(
        "DELETE FROM epsilon_group_keys WHERE user_id = $1",
        int(user_id),
    )

    def _count(result: str) -> int:
        try:
            return int(str(result).split()[-1])
        except (ValueError, IndexError):
            return 0

    return {"seats": _count(seats), "keys": _count(keys)}


@router.post("/appoint")
async def group_appoint(body: AppointBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    pos = await db.pool.fetchrow(
        """
        SELECT id FROM epsilon_positions p
        JOIN epsilon_official_groups g ON g.chat_id = p.chat_id AND g.is_official
        WHERE p.id = $1 AND p.chat_id = $2 AND p.rank < 5
        """,
        int(body.position_id),
        int(body.chat_id),
    )
    if not pos:
        raise HTTPException(status_code=400, detail="Должность не найдена в официальной группе")
    await db.pool.execute(
        """
        INSERT INTO epsilon_seats (user_id, chat_id, position_id, appointed_by, reason)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, chat_id) DO UPDATE
        SET position_id = EXCLUDED.position_id,
            appointed_by = EXCLUDED.appointed_by,
            reason = EXCLUDED.reason,
            created_at = NOW()
        """,
        int(body.user_id),
        int(body.chat_id),
        int(body.position_id),
        int(user_id),
        body.reason.strip(),
    )
    entry_key = await _issue_key(int(body.user_id))
    return {"ok": True, "entryKey": entry_key}


@router.get("/applications")
async def group_applications(user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    rows = await db.pool.fetch(
        """
        SELECT a.id, a.user_id, a.chat_id, a.position_id, a.body, a.status, a.review_note, a.created_at,
               g.title AS group_title, p.title AS position, p.rank
        FROM epsilon_group_applications a
        JOIN epsilon_official_groups g ON g.chat_id = a.chat_id
        JOIN epsilon_positions p ON p.id = a.position_id
        WHERE a.status = 'pending'
        ORDER BY a.created_at
        LIMIT 50
        """
    )
    return {
        "items": [
            {
                "id": int(r["id"]),
                "userId": int(r["user_id"]),
                "chatId": int(r["chat_id"]),
                "positionId": int(r["position_id"]),
                "group": r["group_title"] or str(r["chat_id"]),
                "position": r["position"],
                "rank": int(r["rank"]),
                "body": r["body"],
                "at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }


@router.post("/decide")
async def group_decide(body: DecideBody, user_id: int = Depends(get_any_telegram_user_id)):
    _require_creator(user_id)
    await ensure_tables()
    app = await db.pool.fetchrow(
        """
        SELECT id, user_id, chat_id, position_id, status
        FROM epsilon_group_applications
        WHERE id = $1
        """,
        int(body.application_id),
    )
    if not app or app["status"] != "pending":
        raise HTTPException(status_code=404, detail="Заявка уже решена или не найдена")
    note = body.note.strip()
    if not body.approve and not note:
        raise HTTPException(status_code=400, detail="Отказ пишется с причиной")
    if not body.approve:
        await db.pool.execute(
            """
            UPDATE epsilon_group_applications
            SET status = 'rejected', review_note = $2, reviewer_id = $3, decided_at = NOW()
            WHERE id = $1
            """,
            int(app["id"]),
            note,
            int(user_id),
        )
        return {"ok": True, "status": "rejected"}
    position_id = int(body.position_id or app["position_id"])
    pos = await db.pool.fetchrow(
        "SELECT id, rank FROM epsilon_positions WHERE id = $1 AND chat_id = $2",
        position_id,
        int(app["chat_id"]),
    )
    asked = await db.pool.fetchrow(
        "SELECT rank FROM epsilon_positions WHERE id = $1",
        int(app["position_id"]),
    )
    if not pos or not asked or int(pos["rank"]) > int(asked["rank"]) or int(pos["rank"]) >= 5:
        raise HTTPException(status_code=400, detail="Можно одобрить запрошенную должность или более низкую")
    await db.pool.execute(
        """
        INSERT INTO epsilon_seats (user_id, chat_id, position_id, appointed_by, reason)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, chat_id) DO UPDATE
        SET position_id = EXCLUDED.position_id, appointed_by = EXCLUDED.appointed_by, reason = EXCLUDED.reason
        """,
        int(app["user_id"]),
        int(app["chat_id"]),
        position_id,
        int(user_id),
        note or "заявка одобрена",
    )
    await db.pool.execute(
        """
        UPDATE epsilon_group_applications
        SET status = 'approved', review_note = $2, reviewer_id = $3, decided_at = NOW(), position_id = $4
        WHERE id = $1
        """,
        int(app["id"]),
        note,
        int(user_id),
        position_id,
    )
    entry_key = await _issue_key(int(app["user_id"]))
    return {"ok": True, "status": "approved", "entryKey": entry_key}


@router.get("/summary/{chat_id}")
async def group_summary(chat_id: int, user_id: int = Depends(get_any_telegram_user_id)):
    access = await _access(user_id, chat_id)
    if not access:
        raise HTTPException(status_code=403, detail="В этой группе у вас нет должности")
    from admin_groups import _activity_hint, _moderation_counts

    activity = await _activity_hint(int(chat_id))
    mods = await _moderation_counts(int(chat_id))
    return {
        "chat": access,
        "messages30d": activity.get("messages_30d"),
        "writers30d": activity.get("writers_30d"),
        "members": activity.get("members_tracked"),
        "writers": activity.get("top_writers") or [],
        "moderation": {
            "actions30d": mods.get("actions_30d"),
            "mutes": mods.get("mutes"),
            "bans": mods.get("bans"),
            "warns": mods.get("warns"),
            "kicks": mods.get("kicks"),
            "recent": mods.get("recent") or [],
        },
    }


@router.post("/act")
async def group_act(body: ActBody, user_id: int = Depends(get_any_telegram_user_id)):
    access = await _access(user_id, body.chat_id)
    if not access:
        raise HTTPException(status_code=403, detail="В этой группе у вас нет должности")
    action = (body.action or "").strip().lower()
    if action not in LOCAL_ACTIONS:
        raise HTTPException(status_code=400, detail="Это действие живёт только внутри одной группы")
    if not rights_allow(access["rights"], action):
        raise HTTPException(status_code=403, detail="Должность не даёт этого наказания")
    if int(body.user_id) <= 0:
        raise HTTPException(status_code=400, detail="Укажите id человека")
    blocked = may_punish_rank(
        int(access["rank"]),
        await _seat_rank(int(body.user_id), int(body.chat_id)),
        same_person=int(body.user_id) == int(user_id),
    )
    if blocked:
        raise HTTPException(status_code=403, detail=blocked)
    from admin_groups import moderate_action

    result = await moderate_action(
        chat_id=int(body.chat_id),
        user_id=int(body.user_id),
        action=action,
        until_sec=body.until_sec,
        reason=body.reason.strip(),
        admin_id=int(user_id),
    )
    return {"ok": True, "result": result}


@router.post("/key/check")
async def group_key_check(body: KeyBody, user_id: int = Depends(get_any_telegram_user_id)):
    await ensure_tables()
    if _is_creator(user_id):
        return {"ok": True}
    row = await db.pool.fetchrow(
        "SELECT key_hash FROM epsilon_group_keys WHERE user_id = $1",
        int(user_id),
    )
    if not row:
        raise HTTPException(status_code=403, detail="Личный ключ ещё не выдан. Откройте панель из бота или попросите создателя назначить вас снова")
    if not secrets.compare_digest(_hash_key(body.key.strip()), row["key_hash"]):
        raise HTTPException(status_code=403, detail="Ключ не подошёл")
    return {"ok": True}
