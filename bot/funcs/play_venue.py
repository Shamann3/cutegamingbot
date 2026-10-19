# -*- coding: utf-8 -*-
"""Площадка для игр из онбординга: официальная группа с наибольшей казной.

Правила:
  1) Среди официальных групп берём ту, где больше всего кут (chat.chatbalance).
  2) При равенстве кут — самая активная (chat.text — счётчик сообщений).
  3) Группы с закрытым входом (group_door.bad_since) пропускаем, чтобы
     игрок не упирался в «играть нельзя», пока в другой группе казна есть.
  4) При запуске со ставкой — среди групп, которые могут покрыть ставку,
     предпочитаем ту, где человек уже состоит.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional, Sequence

MemberCheck = Callable[[int, int], Awaitable[bool]]

_CACHE_TTL = 40.0
_cache_at = 0.0
_cache_rows: List["PlayVenue"] = []


@dataclass(frozen=True)
class PlayVenue:
    chat_id: int
    username: str
    title: str
    balance: int
    activity: int

    @property
    def ref(self) -> str:
        name = str(self.username or "").strip().lstrip("@")
        if name and name.replace("_", "").isalnum():
            return f"@{name}"
        title = " ".join(str(self.title or "").split())
        return title or "в группе клуба"

    @property
    def open_url(self) -> str:
        name = str(self.username or "").strip().lstrip("@")
        if name and name.replace("_", "").isalnum():
            return f"https://t.me/{name}"
        s = str(int(self.chat_id))
        if s.startswith("-100"):
            return f"https://t.me/c/{s[4:]}"
        return f"https://t.me/{s}"


def _fallback_venue(
    chat_id: int,
    username: str = "",
    *,
    balance: int = 0,
    activity: int = 0,
    title: str = "",
) -> PlayVenue:
    return PlayVenue(
        chat_id=int(chat_id),
        username=str(username or "").strip().lstrip("@"),
        title=str(title or "").strip(),
        balance=max(0, int(balance or 0)),
        activity=max(0, int(activity or 0)),
    )


def _rank_key(venue: PlayVenue) -> tuple:
    return (int(venue.balance), int(venue.activity), -int(venue.chat_id))


def _pick_best(venues: Sequence[PlayVenue]) -> Optional[PlayVenue]:
    if not venues:
        return None
    return max(venues, key=_rank_key)


async def _load_official_rows(pool) -> List[PlayVenue]:
    """Официальные группы + баланс + активность. Без закрытого входа."""
    # Два варианта SQL: с group_door и без (таблица может ещё не существовать).
    queries = (
        """
        SELECT
            g.chat_id,
            COALESCE(NULLIF(TRIM(g.username), ''), NULLIF(TRIM(c.usernamechat), ''), '') AS username,
            COALESCE(NULLIF(TRIM(g.title), ''), NULLIF(TRIM(c.namechat), ''), '') AS title,
            COALESCE(c.chatbalance, 0)::bigint AS balance,
            COALESCE(c.text, 0)::bigint AS activity
        FROM epsilon_official_groups g
        LEFT JOIN chat c ON c.chat_id = g.chat_id
        LEFT JOIN group_door d ON d.chat_id = g.chat_id
        WHERE g.is_official IS TRUE
          AND COALESCE(c.is_technical, FALSE) = FALSE
          AND d.bad_since IS NULL
        ORDER BY balance DESC, activity DESC, g.chat_id ASC
        """,
        """
        SELECT
            g.chat_id,
            COALESCE(NULLIF(TRIM(g.username), ''), NULLIF(TRIM(c.usernamechat), ''), '') AS username,
            COALESCE(NULLIF(TRIM(g.title), ''), NULLIF(TRIM(c.namechat), ''), '') AS title,
            COALESCE(c.chatbalance, 0)::bigint AS balance,
            COALESCE(c.text, 0)::bigint AS activity
        FROM epsilon_official_groups g
        LEFT JOIN chat c ON c.chat_id = g.chat_id
        WHERE g.is_official IS TRUE
          AND COALESCE(c.is_technical, FALSE) = FALSE
        ORDER BY balance DESC, activity DESC, g.chat_id ASC
        """,
    )
    last_err: Optional[BaseException] = None
    for sql in queries:
        try:
            rows = await pool.fetch(sql)
            out: List[PlayVenue] = []
            for row in rows or []:
                try:
                    out.append(
                        PlayVenue(
                            chat_id=int(row["chat_id"]),
                            username=str(row["username"] or "").strip().lstrip("@"),
                            title=str(row["title"] or "").strip(),
                            balance=max(0, int(row["balance"] or 0)),
                            activity=max(0, int(row["activity"] or 0)),
                        )
                    )
                except Exception:
                    continue
            return out
        except Exception as exc:
            last_err = exc
            continue
    if last_err:
        print(f"[PLAY_VENUE] load official fail: {last_err!r}")
    return []


async def _enrich_fallback(pool, venue: PlayVenue) -> PlayVenue:
    """Подтянуть баланс/юзернейм для запасного клуба, если его нет в списке."""
    try:
        row = await pool.fetchrow(
            """
            SELECT
                COALESCE(NULLIF(TRIM(usernamechat), ''), '') AS username,
                COALESCE(NULLIF(TRIM(namechat), ''), '') AS title,
                COALESCE(chatbalance, 0)::bigint AS balance,
                COALESCE(text, 0)::bigint AS activity
            FROM chat
            WHERE chat_id = $1
            """,
            int(venue.chat_id),
        )
        if not row:
            return venue
        return PlayVenue(
            chat_id=int(venue.chat_id),
            username=str(row["username"] or venue.username or "").strip().lstrip("@"),
            title=str(row["title"] or venue.title or "").strip(),
            balance=max(0, int(row["balance"] or 0)),
            activity=max(0, int(row["activity"] or 0)),
        )
    except Exception as exc:
        print(f"[PLAY_VENUE] enrich fallback {venue.chat_id}: {exc!r}")
        return venue


async def list_official_play_venues(
    *,
    fallback_chat_id: int,
    fallback_username: str = "",
    force: bool = False,
) -> List[PlayVenue]:
    """Кэшированный список площадок, отсортированный по кутам и активности."""
    global _cache_at, _cache_rows
    now = time.monotonic()
    if not force and _cache_rows and (now - _cache_at) < _CACHE_TTL:
        return list(_cache_rows)

    from bot.db_create.db import db

    pool = getattr(db, "pool", None)
    venues: List[PlayVenue] = []
    if pool is not None:
        venues = await _load_official_rows(pool)

    seen = {int(v.chat_id) for v in venues}
    fb_id = int(fallback_chat_id or 0)
    if fb_id and fb_id not in seen:
        fb = _fallback_venue(fb_id, fallback_username)
        if pool is not None:
            fb = await _enrich_fallback(pool, fb)
        venues.append(fb)

    venues.sort(key=_rank_key, reverse=True)
    if venues:
        _cache_rows = list(venues)
        _cache_at = now
    return list(venues)


async def pick_official_play_venue(
    *,
    fallback_chat_id: int,
    fallback_username: str = "",
    min_balance: int = 0,
    user_id: Optional[int] = None,
    member_check: Optional[MemberCheck] = None,
) -> PlayVenue:
    """Выбрать площадку: макс. куты → активность → членство игрока.

    min_balance > 0 — среди групп, которые тянут ставку.
    Если таких нет — всё равно вернём самую богатую (экран «казна пуста»
    покажем только когда и у неё баланс ниже ставки).
    """
    venues = await list_official_play_venues(
        fallback_chat_id=fallback_chat_id,
        fallback_username=fallback_username,
    )
    if not venues:
        return _fallback_venue(fallback_chat_id, fallback_username)

    need = max(0, int(min_balance or 0))
    solvent = [v for v in venues if int(v.balance) >= need] if need > 0 else list(venues)
    pool = solvent or list(venues)

    # Среди подходящих — предпочесть группу, где человек уже есть.
    if user_id and member_check and len(pool) > 1:
        # Сначала самые богатые/активные — меньше проверок в среднем.
        ranked = sorted(pool, key=_rank_key, reverse=True)
        for venue in ranked:
            try:
                if await member_check(int(user_id), int(venue.chat_id)):
                    return venue
            except Exception as exc:
                print(f"[PLAY_VENUE] member check {venue.chat_id}: {exc!r}")
                continue

    best = _pick_best(pool)
    return best or _fallback_venue(fallback_chat_id, fallback_username)


def invalidate_play_venue_cache() -> None:
    global _cache_at, _cache_rows
    _cache_at = 0.0
    _cache_rows = []


async def any_official_can_pay(
    bet: int,
    *,
    fallback_chat_id: int,
    fallback_username: str = "",
) -> bool:
    """True, если хоть одна официальная группа тянет ставку."""
    need = max(0, int(bet or 0))
    if need <= 0:
        return True
    venues = await list_official_play_venues(
        fallback_chat_id=fallback_chat_id,
        fallback_username=fallback_username,
    )
    return any(int(v.balance) >= need for v in venues)
