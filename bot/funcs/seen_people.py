# -*- coding: utf-8 -*-
"""Люди, которых бот уже видел.

Каждое сообщение сразу пишет человека в users: id, имя, username.
Баланс и пригласитель при этом не трогаются.
В группе то же сообщение запоминает его ещё и в этом чате.
Дальше «кто ты», наказание и панель читают уже эту строку.
"""
from __future__ import annotations

import asyncio
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


_ACCOUNT_SQL = """
INSERT INTO users (user_id, first_name, username)
VALUES ($1, $2, $3)
ON CONFLICT (user_id) DO UPDATE
SET first_name = CASE
      WHEN EXCLUDED.first_name IS NOT NULL
        AND btrim(EXCLUDED.first_name) <> ''
        AND EXCLUDED.first_name <> EXCLUDED.user_id::text
      THEN EXCLUDED.first_name
      ELSE users.first_name
    END,
    username = CASE
      WHEN EXCLUDED.username IS NOT NULL AND btrim(EXCLUDED.username) <> ''
      THEN EXCLUDED.username
      ELSE users.username
    END
"""


async def remember_account(user) -> None:
    """Строка users. Баланс и пригласитель не пишутся и не затираются."""
    pool = await _pool()
    if pool is None or user is None or getattr(user, "is_bot", False):
        return
    try:
        uid = int(getattr(user, "id", 0) or 0)
    except (TypeError, ValueError):
        return
    if uid <= 0:
        return
    first = str(getattr(user, "first_name", "") or "")[:128]
    last = str(getattr(user, "last_name", "") or "")[:128]
    name = display_name(first, last)[:128]
    username = str(getattr(user, "username", "") or "").lstrip("@")[:64]
    try:
        await pool.execute(_ACCOUNT_SQL, uid, name, username)
    except Exception:
        log.exception("remember account")


async def find_names(pool, chat_id: int, query: str, limit: int = 8) -> list[dict]:
    """Люди этого чата, которых бот уже видел, по имени."""
    text = " ".join(str(query or "").split())
    if pool is None or int(chat_id) >= 0 or not text or len(text) > 64:
        return []
    pattern = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    try:
        await ensure(pool)
        rows = await pool.fetch(
            """
            SELECT user_id, username, first_name, last_name
            FROM chat_seen_people
            WHERE chat_id = $1
              AND (
                first_name ILIKE $2 ESCAPE '\\'
                OR last_name ILIKE $2 ESCAPE '\\'
                OR btrim(first_name || ' ' || last_name) ILIKE $2 ESCAPE '\\'
              )
            ORDER BY seen_at DESC
            LIMIT $3
            """,
            int(chat_id),
            f"%{pattern}%",
            int(limit),
        )
    except Exception:
        log.exception("seen names")
        return []
    people = []
    for row in rows:
        people.append({
            "user_id": int(row["user_id"]),
            "username": str(row["username"] or ""),
            "name": display_name(row["first_name"], row["last_name"]),
        })
    return people


def _chat_id_of(message) -> int:
    chat = getattr(message, "chat", None)
    try:
        return int(getattr(chat, "id", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _people_on(message) -> list:
    """Автор сообщения, кто вошёл и кто вышел. Без повторов и без ботов."""
    found = []
    seen = set()
    candidates = [getattr(message, "from_user", None), getattr(message, "left_chat_member", None)]
    candidates.extend(getattr(message, "new_chat_members", None) or [])
    for user in candidates:
        if user is None or getattr(user, "is_bot", False):
            continue
        try:
            uid = int(getattr(user, "id", 0) or 0)
        except (TypeError, ValueError):
            continue
        if uid <= 0 or uid in seen:
            continue
        seen.add(uid)
        found.append(user)
    return found


async def remember_message(message) -> None:
    chat_id = _chat_id_of(message)
    if chat_id >= 0:
        return
    for user in _people_on(message):
        await remember_user(chat_id, user)


_UPDATE_FIELDS = ("message", "edited_message", "channel_post", "edited_channel_post")


def sight_targets(event):
    """Новое сообщение, правка и пост канала. Одно и то же дважды не берём."""
    if event is None:
        return []
    nested = [getattr(event, name, None) for name in _UPDATE_FIELDS]
    nested = [item for item in nested if item is not None and getattr(item, "chat", None) is not None]
    if nested:
        return nested
    if getattr(event, "chat", None) is not None:
        return [event]
    return []


async def remember_sight(message) -> None:
    """Сразу записать людей этого сообщения. Дальше их уже ищут в базе."""
    if message is None:
        return
    chat_id = _chat_id_of(message)
    for user in _people_on(message):
        await remember_account(user)
        if chat_id < 0:
            await remember_user(chat_id, user)


async def remember_membership(chat_id, user) -> None:
    """Вход и выход без текста: человек всё равно появляется в базе."""
    await remember_account(user)
    try:
        cid = int(chat_id)
    except (TypeError, ValueError):
        return
    if cid < 0:
        await remember_user(cid, user)


# Ждём запись до обработчика, но не держим бота, если база молчит.
# Сама запись при этом не отменяется и дописывается следом.
SIGHT_WAIT = 1.5


def _memberships(event) -> list:
    found = []
    for name in ("chat_member", "my_chat_member"):
        member = getattr(event, name, None)
        if member is None:
            continue
        user = getattr(getattr(member, "new_chat_member", None), "user", None)
        chat = getattr(member, "chat", None)
        if user is None or chat is None:
            continue
        found.append((chat, user))
    return found


async def remember_event(event) -> None:
    for message in sight_targets(event):
        await remember_sight(message)
    for chat, user in _memberships(event):
        try:
            chat_id = int(getattr(chat, "id", 0) or 0)
        except (TypeError, ValueError):
            continue
        await remember_membership(chat_id, user)


async def await_sight(event) -> None:
    """Записать людей апдейта до того, как команда начнёт их искать."""
    task = asyncio.create_task(remember_event(event))
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=SIGHT_WAIT)
    except Exception:
        return


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
