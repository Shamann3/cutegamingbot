# -*- coding: utf-8 -*-
"""Люди, которых бот уже видел в группе.

Сюда попадают и те, кто только зашёл, и те, кто написал сообщение.
«Кто ты» и наказание по username читают эту память, если в базе Кута строки ещё нет.
"""
from __future__ import annotations

import logging

log = logging.getLogger("seen_people")
_ready = False


def username_key(value) -> str:
    return str(value or "").strip().lstrip("@").casefold()


def display_name(first_name: str, last_name: str) -> str:
    return " ".join(part for part in (str(first_name or "").strip(), str(last_name or "").strip()) if part)


async def ensure(pool) -> None:
    global _ready
    if _ready:
        return
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_seen_people (
            chat_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            first_name TEXT NOT NULL DEFAULT '',
            last_name TEXT NOT NULL DEFAULT '',
            seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (chat_id, user_id)
        )
        """
    )
    await pool.execute(
        """
        CREATE INDEX IF NOT EXISTS chat_seen_username_idx
            ON chat_seen_people (lower(username))
        """
    )
    _ready = True


async def _pool():
    try:
        from main import db
    except Exception:
        return None
    return getattr(db, "pool", None)


async def remember_user(chat_id: int, user) -> None:
    pool = await _pool()
    if pool is None or user is None or getattr(user, "is_bot", False):
        return
    try:
        uid = int(getattr(user, "id", 0) or 0)
        chat = int(chat_id)
    except (TypeError, ValueError):
        return
    if uid <= 0 or chat >= 0:
        return
    try:
        await ensure(pool)
        await pool.execute(
            """
            INSERT INTO chat_seen_people (chat_id, user_id, username, first_name, last_name, seen_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (chat_id, user_id) DO UPDATE
            SET username = CASE WHEN EXCLUDED.username <> '' THEN EXCLUDED.username ELSE chat_seen_people.username END,
                first_name = CASE WHEN EXCLUDED.first_name <> '' THEN EXCLUDED.first_name ELSE chat_seen_people.first_name END,
                last_name = CASE WHEN EXCLUDED.last_name <> '' THEN EXCLUDED.last_name ELSE chat_seen_people.last_name END,
                seen_at = NOW()
            """,
            chat,
            uid,
            str(getattr(user, "username", "") or "")[:64],
            str(getattr(user, "first_name", "") or "")[:128],
            str(getattr(user, "last_name", "") or "")[:128],
        )
    except Exception:
        log.exception("remember seen user")


async def remember_message(message) -> None:
    chat = getattr(message, "chat", None)
    try:
        chat_id = int(getattr(chat, "id", 0) or 0)
    except (TypeError, ValueError):
        return
    if chat_id >= 0:
        return
    user = getattr(message, "from_user", None)
    if user is not None:
        await remember_user(chat_id, user)
    for member in getattr(message, "new_chat_members", None) or []:
        await remember_user(chat_id, member)


async def find_username(pool, username: str, chat_id: int | None = None) -> dict | None:
    key = username_key(username)
    if pool is None or not key:
        return None
    try:
        await ensure(pool)
        if chat_id is not None and int(chat_id) < 0:
            row = await pool.fetchrow(
                """
                SELECT user_id, username, first_name, last_name
                FROM chat_seen_people
                WHERE lower(username) = $1
                ORDER BY CASE WHEN chat_id = $2 THEN 0 ELSE 1 END, seen_at DESC
                LIMIT 1
                """,
                key,
                int(chat_id),
            )
        else:
            row = await pool.fetchrow(
                """
                SELECT user_id, username, first_name, last_name
                FROM chat_seen_people
                WHERE lower(username) = $1
                ORDER BY seen_at DESC
                LIMIT 1
                """,
                key,
            )
    except Exception:
        log.exception("find seen username")
        return None
    if not row:
        return None
    return {
        "user_id": int(row["user_id"]),
        "username": str(row["username"] or ""),
        "first_name": str(row["first_name"] or ""),
        "last_name": str(row["last_name"] or ""),
    }


async def chat_candidates(pool, chat_id: int, limit: int = 80) -> list[dict]:
    if pool is None or int(chat_id) >= 0:
        return []
    try:
        await ensure(pool)
        rows = await pool.fetch(
            """
            SELECT user_id, username, first_name, last_name
            FROM chat_seen_people
            WHERE chat_id = $1
            ORDER BY seen_at DESC
            LIMIT $2
            """,
            int(chat_id),
            int(limit),
        )
    except Exception:
        log.exception("seen chat people")
        return []
    people = []
    for row in rows:
        people.append({
            "user_id": int(row["user_id"]),
            "username": str(row["username"] or ""),
            "name": display_name(row["first_name"], row["last_name"]),
        })
    return people
