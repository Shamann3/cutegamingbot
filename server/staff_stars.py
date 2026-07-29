"""Очередь зарплатных выплат звёздами (панель ↔ бот через БД)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from db import db

logger = logging.getLogger(__name__)

STAR_METHODS = ("auto", "fragment", "userbot")

# Дефолтные подарки (как в bot/design/buttons.py) — fallback, пока бот не синхронизировал live-каталог
DEFAULT_STAR_GIFTS = [
    {"giftId": 5922558454332916696, "stars": 60, "emoji": "🎁", "customEmojiId": "5345935030143196497", "hasUpgrade": False, "source": "manual"},
    {"giftId": 5956217000635139069, "stars": 60, "emoji": "🎁", "customEmojiId": "5379850840691476775", "hasUpgrade": False, "source": "manual"},
    {"giftId": 5801108895304779062, "stars": 60, "emoji": "🎁", "customEmojiId": "5224628072619216265", "hasUpgrade": False, "source": "manual"},
    {"giftId": 5800655655995968830, "stars": 60, "emoji": "🎁", "customEmojiId": "5226661632259691727", "hasUpgrade": False, "source": "manual"},
    {"giftId": 5866352046986232958, "stars": 60, "emoji": "🎁", "customEmojiId": "5289761157173775507", "hasUpgrade": False, "source": "manual"},
    {"giftId": 5893356958802511476, "stars": 60, "emoji": "🎁", "customEmojiId": "5317000922096769303", "hasUpgrade": False, "source": "manual"},
    {"giftId": 5935895822435615975, "stars": 60, "emoji": "🎁", "customEmojiId": "5359736160224586485", "hasUpgrade": False, "source": "manual"},
    {"giftId": 5969796561943660080, "stars": 60, "emoji": "🎁", "customEmojiId": "5393309541620291208", "hasUpgrade": False, "source": "manual"},
    {"giftId": 6026193266406327981, "stars": 60, "emoji": "🎁", "customEmojiId": "5447213743417105726", "hasUpgrade": False, "source": "manual"},
    {"giftId": 5974210632977745012, "stars": 60, "emoji": "🎁", "customEmojiId": "5398092984136802109", "hasUpgrade": False, "source": "manual"},
]


def _row(r) -> dict[str, Any]:
    return {
        "id": int(r["id"]),
        "salaryId": int(r["salary_id"]) if r["salary_id"] else None,
        "bonusId": int(r["bonus_id"]) if r.get("bonus_id") else None,
        "source": r["source"] or "salary",
        "userId": int(r["user_id"]),
        "amount": int(r["amount"]),
        "starsUsername": (r["stars_username"] or "").lstrip("@"),
        "method": r["method"],
        "status": r["status"],
        "requestedBy": int(r["requested_by"]) if r["requested_by"] else None,
        "kind": r["kind"] or "payment",
        "giftId": int(r["gift_id"]) if r.get("gift_id") else 0,
        "giftEmoji": r.get("gift_emoji") or "⭐",
        "hasUpgrade": int(r["has_upgrade"] or 0) if r.get("has_upgrade") is not None else 0,
        "error": r["error"],
        "txid": r["txid"],
        "channelMessageId": int(r["channel_message_id"]) if r["channel_message_id"] else None,
        "requestId": r["request_id"],
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        "completedAt": r["completed_at"].isoformat() if r["completed_at"] else None,
    }


def _gift_cache_row(r) -> dict[str, Any]:
    return {
        "giftId": int(r["gift_id"]),
        "stars": int(r["stars"]),
        "emoji": r["emoji"] or "🎁",
        "customEmojiId": r["custom_emoji_id"] or "",
        "hasUpgrade": bool(r["has_upgrade"]),
        "upgradeStars": int(r["upgrade_stars"] or 0),
        "source": r["source"] or "live",
        "updatedAt": r["updated_at"].isoformat() if r.get("updated_at") else None,
    }


async def get_fragment_health() -> dict[str, Any]:
    row = await db.pool.fetchrow(
        """
        SELECT fragment_ok, fragment_ton, fragment_checked_at, fragment_error,
               default_stars_method
        FROM staff_payout_settings WHERE id = 1
        """
    )
    if not row:
        return {
            "ok": None,
            "ton": None,
            "checkedAt": None,
            "error": "Настройки ещё не инициализированы",
            "defaultStarsMethod": "auto",
            "stale": True,
        }
    checked = row["fragment_checked_at"]
    stale = True
    if checked is not None:
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) - checked).total_seconds()
        stale = age > 180  # старше 3 минут — устарело
    return {
        "ok": row["fragment_ok"],
        "ton": float(row["fragment_ton"]) if row["fragment_ton"] is not None else None,
        "checkedAt": checked.isoformat() if checked else None,
        "error": row["fragment_error"],
        "defaultStarsMethod": row["default_stars_method"] or "auto",
        "stale": stale,
    }


async def update_fragment_health(
    *,
    ok: bool,
    ton: float | None = None,
    error: str | None = None,
) -> None:
    await db.pool.execute(
        """
        INSERT INTO staff_payout_settings (id, fragment_ok, fragment_ton, fragment_error, fragment_checked_at)
        VALUES (1, $1, $2, $3, NOW())
        ON CONFLICT (id) DO UPDATE SET
            fragment_ok = EXCLUDED.fragment_ok,
            fragment_ton = EXCLUDED.fragment_ton,
            fragment_error = EXCLUDED.fragment_error,
            fragment_checked_at = NOW()
        """,
        ok, ton, (error or None),
    )


async def upsert_star_gifts_cache(gifts: list[dict[str, Any]]) -> int:
    """Бот/API пишет live/manual каталог подарков для панели."""
    if not gifts:
        return 0
    n = 0
    async with db.pool.acquire() as conn:
        for g in gifts:
            gift_id = int(g.get("giftId") or g.get("gift_id") or 0)
            stars = int(g.get("stars") or g.get("price") or 0)
            if gift_id <= 0 or stars <= 0:
                continue
            await conn.execute(
                """
                INSERT INTO star_gifts_cache
                    (gift_id, stars, emoji, custom_emoji_id, has_upgrade, upgrade_stars, source, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                ON CONFLICT (gift_id) DO UPDATE SET
                    stars = EXCLUDED.stars,
                    emoji = EXCLUDED.emoji,
                    custom_emoji_id = EXCLUDED.custom_emoji_id,
                    has_upgrade = EXCLUDED.has_upgrade,
                    upgrade_stars = EXCLUDED.upgrade_stars,
                    source = EXCLUDED.source,
                    updated_at = NOW()
                """,
                gift_id,
                stars,
                (g.get("emoji") or "🎁")[:32],
                str(g.get("customEmojiId") or g.get("custom_emoji_id") or "")[:64] or None,
                bool(g.get("hasUpgrade") or g.get("has_upgrade")),
                int(g.get("upgradeStars") or g.get("upgrade_stars") or 0),
                str(g.get("source") or "live")[:16],
            )
            n += 1
    return n


async def fetch_live_gifts_from_telegram() -> list[dict[str, Any]]:
    """Тянет live-каталог через Bot API getAvailableGifts (тот же набор, что у игроков)."""
    import aiohttp
    try:
        from config import BOT_TOKEN
    except Exception:
        BOT_TOKEN = ""
    if not BOT_TOKEN:
        return []

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getAvailableGifts"
    out: list[dict[str, Any]] = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                data = await resp.json(content_type=None)
        if not isinstance(data, dict) or not data.get("ok"):
            logger.warning("getAvailableGifts failed: %s", data)
            return []
        gifts = ((data.get("result") or {}).get("gifts")) or []
        for g in gifts:
            try:
                gift_id = int(g.get("id") or 0)
                stars = int(g.get("star_count") or 0)
                if gift_id <= 0 or stars <= 0:
                    continue
                sticker = g.get("sticker") or {}
                emoji = (sticker.get("emoji") if isinstance(sticker, dict) else None) or "🎁"
                custom = ""
                if isinstance(sticker, dict):
                    custom = str(sticker.get("custom_emoji_id") or "")
                upgrade = g.get("upgrade_star_count")
                out.append({
                    "giftId": gift_id,
                    "stars": stars,
                    "emoji": emoji,
                    "customEmojiId": custom,
                    "hasUpgrade": upgrade is not None,
                    "upgradeStars": int(upgrade or 0),
                    "source": "live",
                })
            except Exception:
                continue
    except Exception:
        logger.exception("fetch_live_gifts_from_telegram failed")
        return []
    return out


async def refresh_star_gifts_from_telegram() -> int:
    """Live Telegram + ручные дефолты → star_gifts_cache."""
    live = await fetch_live_gifts_from_telegram()
    # manuals поверх/рядом — не затирают live с тем же id (ON CONFLICT обновляет)
    merged = list(DEFAULT_STAR_GIFTS) + live
    # если live пришёл с тем же id что manual — live важнее: кладём live последним
    by_id: dict[int, dict[str, Any]] = {}
    for g in merged:
        by_id[int(g["giftId"])] = g
    # live wins
    for g in live:
        by_id[int(g["giftId"])] = g
    return await upsert_star_gifts_cache(list(by_id.values()))


async def list_star_gifts(*, amount: int | None = None, exact: bool = True) -> list[dict[str, Any]]:
    """Каталог подарков: live Telegram + ручные. exact=True → сначала price == amount."""
    # Всегда пытаемся освежить live-каталог (панель не зависит от бота)
    try:
        await refresh_star_gifts_from_telegram()
    except Exception:
        logger.exception("refresh gifts before list failed")

    try:
        rows = await db.pool.fetch(
            "SELECT * FROM star_gifts_cache ORDER BY stars ASC, gift_id ASC"
        )
    except Exception:
        logger.exception("star_gifts_cache read failed")
        rows = []

    items = [_gift_cache_row(r) for r in rows] if rows else []
    if not items:
        items = list(DEFAULT_STAR_GIFTS)
        try:
            await upsert_star_gifts_cache(DEFAULT_STAR_GIFTS)
        except Exception:
            logger.exception("seed star gifts cache failed")

    if amount is None:
        return items
    amount = int(amount)
    exact_matches = [g for g in items if int(g["stars"]) == amount]
    if exact:
        if exact_matches:
            return exact_matches
        return [g for g in items if int(g["stars"]) <= amount]
    # exact=False: всё ≤ amount, точные сверху уже на клиенте; здесь просто фильтр
    return [g for g in items if int(g["stars"]) <= amount] or items


async def enqueue_star_payout(
    *,
    user_id: int,
    amount: int,
    stars_username: str,
    method: str,
    requested_by: int,
    salary_id: int | None = None,
    bonus_id: int | None = None,
    source: str = "salary",
    kind: str = "payment",
    gift_id: int = 0,
    gift_emoji: str = "⭐",
    has_upgrade: int = 0,
) -> dict:
    method = (method or "auto").strip().lower()
    if method not in STAR_METHODS:
        raise ValueError("method: auto | fragment | userbot")
    username = (stars_username or "").strip().lstrip("@")
    if not username or len(username) < 5:
        raise ValueError("Укажите Telegram username для Stars (без @)")
    if amount <= 0:
        raise ValueError("amount must be > 0")
    if source == "salary" and not salary_id:
        raise ValueError("salary_id required")
    if source == "bonus" and not bonus_id:
        raise ValueError("bonus_id required")

    # Для userbot / auto (канал) желателен подарок; 0 = авто-подбор по сумме
    if method in ("userbot", "auto") and gift_id:
        gifts = await list_star_gifts(amount=amount, exact=True)
        known = {int(g["giftId"]) for g in gifts}
        # если каталог пуст по сумме — всё равно принимаем выбранный id (бот проверит при отправке)
        if known and gift_id not in known and gifts:
            # разрешаем и подарки с другой ценой только если exact list пуст
            all_gifts = await list_star_gifts(amount=None)
            all_ids = {int(g["giftId"]) for g in all_gifts}
            if gift_id in all_ids:
                match = next(g for g in all_gifts if int(g["giftId"]) == gift_id)
                if int(match["stars"]) != amount:
                    raise ValueError(
                        f"Подарок стоит {match['stars']}⭐, а сумма выплаты {amount}. "
                        "Измените сумму или выберите другой подарок."
                    )

    request_id = f"salstar-{uuid.uuid4().hex[:16]}"
    row = await db.pool.fetchrow(
        """
        INSERT INTO staff_star_payouts
            (salary_id, bonus_id, source, user_id, amount, stars_username,
             method, status, requested_by, kind, request_id,
             gift_id, gift_emoji, has_upgrade)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'queued', $8, $9, $10, $11, $12, $13)
        RETURNING *
        """,
        salary_id, bonus_id, source, user_id, amount, username,
        method, requested_by, kind, request_id,
        int(gift_id or 0), (gift_emoji or "⭐")[:32], int(has_upgrade or 0),
    )
    return _row(row)


async def list_star_payouts(limit: int = 30, status: str | None = None) -> list[dict]:
    if status:
        rows = await db.pool.fetch(
            """
            SELECT * FROM staff_star_payouts
            WHERE status = $1
            ORDER BY created_at DESC LIMIT $2
            """,
            status, limit,
        )
    else:
        rows = await db.pool.fetch(
            "SELECT * FROM staff_star_payouts ORDER BY created_at DESC LIMIT $1",
            limit,
        )
    return [_row(r) for r in rows]


async def get_star_payout(payout_id: int) -> dict | None:
    row = await db.pool.fetchrow("SELECT * FROM staff_star_payouts WHERE id = $1", payout_id)
    return _row(row) if row else None


async def cancel_star_payout(payout_id: int) -> bool:
    result = await db.pool.execute(
        """
        UPDATE staff_star_payouts
        SET status = 'cancelled', updated_at = NOW()
        WHERE id = $1 AND status IN ('queued', 'failed', 'channel_pending', 'processing')
        """,
        payout_id,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def requeue_star_payout(payout_id: int) -> bool:
    """Вернуть failed/stuck заявку в очередь (после фикса воркера)."""
    result = await db.pool.execute(
        """
        UPDATE staff_star_payouts
        SET status = 'queued', error = NULL, updated_at = NOW()
        WHERE id = $1 AND status IN ('failed', 'processing')
        """,
        payout_id,
    )
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False
