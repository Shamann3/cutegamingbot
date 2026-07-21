"""Проверка подписки пользователя на Telegram-канал для условия giveaway
channel_sub. Живой вызов Telegram Bot API (getChatMember) кэшируется в
giveaway_channel_sub_cache на TTL_MINUTES, чтобы не упираться в лимиты
Telegram при частом опросе списка розыгрышей (каждые 30 сек в вебаппе).
Перед реальным участием (participate_in_giveaway) кэш обходится
(force_refresh=True) — участие никогда не проверяется по устаревшим данным.

Правило пула: этот модуль никогда не держит соединение из pool.acquire()
открытым во время HTTP-вызова к Telegram — чтение кэша, сам HTTP-вызов и
запись кэша обратно — три раздельных шага.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("cute-farm.giveaway-membership")

TTL_MINUTES = 10
_MEMBER_STATUSES = frozenset({"member", "administrator", "creator"})


def _is_member_status(status: str | None) -> bool:
    return (status or "").strip().lower() in _MEMBER_STATUSES


def _is_cache_fresh(checked_at: datetime, now: datetime, ttl_minutes: int = TTL_MINUTES) -> bool:
    return (now - checked_at) < timedelta(minutes=ttl_minutes)


async def _fetch_chat_member_status(channel: str, user_id: int) -> str | None:
    """Живой вызов Telegram Bot API. Возвращает status ('member'/'left'/...)
    или None при любой ошибке (канал не найден, бот не админ канала, таймаут)
    — вызывающий код трактует None как «не подписан» (fail-closed)."""
    import aiohttp
    from config import BOT_TOKEN

    if not BOT_TOKEN:
        return None
    chat_id = channel if channel.startswith("@") else f"@{channel}"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params={"chat_id": chat_id, "user_id": user_id},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
    except Exception:
        logger.exception("getChatMember failed (channel=%s, user_id=%s)", channel, user_id)
        return None
    if not data.get("ok"):
        logger.warning("getChatMember error (channel=%s): %s", channel, data.get("description"))
        return None
    return data.get("result", {}).get("status")


async def resolve_channel_sub(
    pool, user_id: int, channels: set[str], *, force_refresh: bool = False,
) -> dict[str, bool]:
    """Возвращает {channel: is_member} для каждого канала из channels.
    force_refresh=True игнорирует кэш полностью (используется перед реальным
    участием в розыгрыше)."""
    if not channels:
        return {}
    now = datetime.now(timezone.utc)
    result: dict[str, bool] = {}
    stale: list[str] = list(channels)

    if not force_refresh:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT channel, is_member, checked_at FROM giveaway_channel_sub_cache "
                "WHERE user_id = $1 AND channel = ANY($2::text[])",
                user_id, list(channels),
            )
        cached = {r["channel"]: r for r in rows}
        stale = []
        for channel in channels:
            row = cached.get(channel)
            if row and _is_cache_fresh(row["checked_at"], now):
                result[channel] = bool(row["is_member"])
            else:
                stale.append(channel)

    if not stale:
        return result

    fresh_values: dict[str, bool] = {}
    for channel in stale:
        status = await _fetch_chat_member_status(channel, user_id)
        fresh_values[channel] = _is_member_status(status)
    result.update(fresh_values)

    async with pool.acquire() as conn:
        for channel, is_member in fresh_values.items():
            await conn.execute(
                """
                INSERT INTO giveaway_channel_sub_cache (user_id, channel, is_member, checked_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (user_id, channel) DO UPDATE
                    SET is_member = EXCLUDED.is_member, checked_at = EXCLUDED.checked_at
                """,
                user_id, channel, is_member,
            )
    return result
