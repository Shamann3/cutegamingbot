# -*- coding: utf-8 -*-
"""Ссылки и флуд в официальной группе. Капча остаётся в group_captcha."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from aiogram import BaseMiddleware
from aiogram.enums import ChatType

_SERVER = Path(__file__).resolve().parents[2] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

from group_guard_rules import (  # noqa: E402
    entities_have_link,
    flood_stamps,
    flood_tripped,
    text_has_link,
)

_attached = False
_flags: dict[int, tuple[dict, float]] = {}
_trusted: dict[int, tuple[set, float]] = {}
_flood: dict[tuple[int, int], list[float]] = {}
_FLAG_TTL = 20.0
_TRUST_TTL = 45.0


def _pool():
    from bot.db_create.db import db
    return getattr(db, "pool", None)


async def _flags_for(chat_id: int) -> dict:
    now = time.monotonic()
    hit = _flags.get(chat_id)
    if hit and now - hit[1] < _FLAG_TTL:
        return hit[0]
    pool = _pool()
    flags = {"links": False, "flood": False}
    if pool is None:
        return flags
    try:
        row = await pool.fetchrow(
            """
            SELECT
              COALESCE(g.custom, FALSE) AS custom,
              COALESCE(g.links, FALSE) AS links,
              COALESCE(g.flood, FALSE) AS flood,
              COALESCE(p.links, FALSE) AS policy_links,
              COALESCE(p.flood, FALSE) AS policy_flood
            FROM epsilon_official_groups o
            LEFT JOIN epsilon_guard g ON g.chat_id = o.chat_id
            LEFT JOIN epsilon_guard_policy p ON p.id = 1
            WHERE o.chat_id = $1 AND o.is_official
            """,
            int(chat_id),
        )
        if row:
            use_own = bool(row["custom"])
            flags = {
                "links": bool(row["links"] if use_own else row["policy_links"]),
                "flood": bool(row["flood"] if use_own else row["policy_flood"]),
            }
    except Exception:
        flags = {"links": False, "flood": False}
    _flags[chat_id] = (flags, now)
    return flags


def _creator_ids() -> set:
    try:
        from config import owner_user_ids
        return {int(item) for item in owner_user_ids()}
    except Exception:
        return set()


_allow: tuple[set, float] = (set(), 0.0)


async def _allow_ids() -> set:
    global _allow
    now = time.monotonic()
    people, stamp = _allow
    if now - stamp < _TRUST_TTL and stamp:
        return people
    pool = _pool()
    found = set()
    if pool is not None:
        try:
            rows = await pool.fetch("SELECT user_id FROM epsilon_guard_allow")
            found = {int(row["user_id"]) for row in rows}
        except Exception:
            found = set()
    _allow = (found, now)
    return found


async def _is_trusted(chat_id: int, user_id: int) -> bool:
    if int(user_id) in _creator_ids() or int(user_id) in await _allow_ids():
        return True
    now = time.monotonic()
    hit = _trusted.get(chat_id)
    if not hit or now - hit[1] >= _TRUST_TTL:
        pool = _pool()
        people = set()
        if pool is not None:
            try:
                rows = await pool.fetch(
                    "SELECT user_id FROM epsilon_seats WHERE chat_id = $1",
                    int(chat_id),
                )
                people = {int(row["user_id"]) for row in rows}
            except Exception:
                people = set()
        _trusted[chat_id] = (people, now)
        hit = _trusted[chat_id]
    return int(user_id) in hit[0]


async def _hit(chat_id: int, user_id: int, kind: str, detail: str) -> None:
    pool = _pool()
    if pool is None:
        return
    try:
        await pool.execute(
            """
            INSERT INTO epsilon_guard_hits (chat_id, user_id, kind, detail)
            VALUES ($1, $2, $3, $4)
            """,
            int(chat_id),
            int(user_id),
            kind,
            detail[:160],
        )
    except Exception:
        return


class OfficialGuardMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        chat = getattr(event, "chat", None)
        user = getattr(event, "from_user", None)
        if chat is None or user is None or getattr(user, "is_bot", False):
            return await handler(event, data)
        if chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
            return await handler(event, data)
        flags = await _flags_for(int(chat.id))
        if not flags["links"] and not flags["flood"]:
            return await handler(event, data)
        if await _is_trusted(int(chat.id), int(user.id)):
            return await handler(event, data)
        text = getattr(event, "text", None) or getattr(event, "caption", None) or ""
        entities = list(getattr(event, "entities", None) or []) + list(getattr(event, "caption_entities", None) or [])
        forwarded = bool(getattr(event, "forward_origin", None) or getattr(event, "forward_from_chat", None))
        if flags["links"] and (text_has_link(text) or entities_have_link(entities) or forwarded):
            await _hit(int(chat.id), int(user.id), "link", "ссылка или пересылка")
            try:
                await event.delete()
            except Exception:
                pass
            return None
        if flags["flood"]:
            key = (int(chat.id), int(user.id))
            stamps = flood_stamps(_flood.get(key, []), time.monotonic())
            _flood[key] = stamps
            if len(_flood) > 4000:
                _flood.clear()
            if flood_tripped(stamps):
                await _hit(int(chat.id), int(user.id), "flood", "слишком часто")
                try:
                    await event.delete()
                except Exception:
                    pass
                return None
        return await handler(event, data)


def attach_group_guard(dp) -> None:
    global _attached
    if _attached:
        return
    dp.message.outer_middleware(OfficialGuardMiddleware())
    _attached = True
    print("[GUARD] защита официальных групп подключена")
