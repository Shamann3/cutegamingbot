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


async def cancel_open_star_payouts_for_salary(salary_id: int) -> int:
    """Снимает незавершённые заявки по зарплате перед новой."""
    result = await db.pool.execute(
        """
        UPDATE staff_star_payouts
        SET status = 'cancelled', updated_at = NOW(),
            error = COALESCE(error, 'replaced by new salary request')
        WHERE salary_id = $1
          AND status IN ('queued', 'processing', 'channel_pending', 'failed')
        """,
        salary_id,
    )
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0


WITHDRAW_CHANNELS = ("@CurrencyCute", "-1002552723822")


def _salary_channel_text(
    *,
    amount: int,
    gift_emoji: str,
    name_html: str,
    username: str,
    part: int | None = None,
    parts: int | None = None,
) -> str:
    from html import escape
    amount_str = "{:,.0f}".format(int(amount)).replace(",", ".")
    emoji = escape((gift_emoji or "⭐")[:16] or "⭐")
    uname = (username or "").lstrip("@")
    uname_txt = f" (@{escape(uname)})" if uname else ""
    part_line = ""
    if part and parts and parts > 1:
        part_line = (
            f"\n<b><tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> "
            f"Часть {int(part)}/{int(parts)}</b>"
        )
    return (
        f"<code>{emoji}</code> "
        f"<b>{amount_str} кут в stars "
        f"<tg-emoji emoji-id='5897658922600240288'>⭐️</tg-emoji></b>\n"
        f"<b><tg-emoji emoji-id='5294026527850132517'>🍬</tg-emoji> "
        f"Для <i>{name_html}</i>{uname_txt}</b>\n"
        f"<b><tg-emoji emoji-id='5422818196031840237'>💼</tg-emoji> "
        f"Заявка на выплату зарплаты администратору</b>"
        f"{part_line}\n\n"
        f"<blockquote><b>@CuteGamingBot</b></blockquote>"
    )


async def _send_channel_message_http(
    *,
    text: str,
    approve_token: str,
    reject_token: str,
    refund_token: str,
) -> tuple[int | None, str | None, str | None]:
    """Сразу шлёт в канал через Bot API. Возвращает (message_id, chat_id, error)."""
    import aiohttp

    try:
        from config import BOT_TOKEN
    except Exception:
        BOT_TOKEN = ""
    if not BOT_TOKEN:
        return None, None, "BOT_TOKEN не настроен"

    reply_markup = {
        "inline_keyboard": [[
            {"text": "👎", "callback_data": f"wdact:{reject_token}"},
            {"text": "🥂", "callback_data": f"wdact:{refund_token}"},
            {"text": "👍", "callback_data": f"wdact:{approve_token}"},
        ]],
    }
    last_err = "channel unavailable"
    async with aiohttp.ClientSession() as session:
        for chat_id in WITHDRAW_CHANNELS:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": reply_markup,
            }
            try:
                async with session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    data = await resp.json(content_type=None)
                if isinstance(data, dict) and data.get("ok"):
                    mid = ((data.get("result") or {}).get("message_id"))
                    logger.info("salary channel HTTP ok chat=%s mid=%s", chat_id, mid)
                    return int(mid or 0) or None, str(chat_id), None
                last_err = str((data or {}).get("description") or data)[:300]
                logger.warning("salary channel HTTP fail chat=%s: %s", chat_id, last_err)
            except Exception as e:
                last_err = str(e)[:300]
                logger.warning("salary channel HTTP err chat=%s: %r", chat_id, e)
    return None, None, last_err


async def deliver_salary_payout_to_channel(
    payout_id: int,
    *,
    first_name: str = "",
    part: int | None = None,
    parts: int | None = None,
) -> dict:
    """
    Мгновенный пост заявки зарплаты в канал выводов (как у игроков).
    Токены кнопок пишутся в БД — wdact работает даже без in-memory registry.
    """
    row = await db.pool.fetchrow("SELECT * FROM staff_star_payouts WHERE id = $1", payout_id)
    if not row:
        raise ValueError(f"payout {payout_id} not found")
    if row["status"] in ("completed", "cancelled", "refunded"):
        return _row(row)
    if row["status"] == "channel_pending" and row.get("channel_message_id"):
        return _row(row)

    from html import escape

    user_id = int(row["user_id"])
    username = (row["stars_username"] or "").lstrip("@")
    amount = int(row["amount"])
    gift_emoji = row.get("gift_emoji") or "⭐"
    name = escape(first_name or username or str(user_id))
    name_html = f'<a href="tg://user?id={user_id}">{name}</a>'

    approve_token = uuid.uuid4().hex[:24]
    reject_token = uuid.uuid4().hex[:24]
    refund_token = uuid.uuid4().hex[:24]

    text = _salary_channel_text(
        amount=amount,
        gift_emoji=gift_emoji,
        name_html=name_html,
        username=username,
        part=part,
        parts=parts,
    )
    mid, chat_id, err = await _send_channel_message_http(
        text=text,
        approve_token=approve_token,
        reject_token=reject_token,
        refund_token=refund_token,
    )
    if mid is None:
        await db.pool.execute(
            """
            UPDATE staff_star_payouts
            SET status = 'queued', error = $2, updated_at = NOW()
            WHERE id = $1
            """,
            payout_id, f"channel post: {err}"[:400],
        )
        raise RuntimeError(err or "не удалось отправить в канал выводов")

    updated = await db.pool.fetchrow(
        """
        UPDATE staff_star_payouts
        SET status = 'channel_pending',
            channel_message_id = $2,
            channel_chat_id = $3,
            approve_token = $4,
            reject_token = $5,
            refund_token = $6,
            part_index = $7,
            parts_total = $8,
            error = NULL,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        payout_id, mid, chat_id, approve_token, reject_token, refund_token,
        int(part or 0), int(parts or 0),
    )
    return _row(updated)


async def get_salary_wdact_by_token(token: str) -> dict | None:
    """Payload для wdact: из БД (если API запостила заявку без in-memory registry)."""
    token = (token or "").strip()
    if not token:
        return None
    row = await db.pool.fetchrow(
        """
        SELECT * FROM staff_star_payouts
        WHERE approve_token = $1 OR reject_token = $1 OR refund_token = $1
        LIMIT 1
        """,
        token,
    )
    if not row:
        return None
    if row["status"] in ("completed", "cancelled", "refunded"):
        return None
    if row["approve_token"] == token:
        kind = "approve"
    elif row["reject_token"] == token:
        kind = "reject"
    else:
        kind = "refund"
    username = (row["stars_username"] or "").lstrip("@")
    uid = int(row["user_id"])
    return {
        "kind": kind,
        "request_id": row["request_id"] or f"salstar-{row['id']}",
        "sender_user_id": uid,
        "sender_username": username,
        "sender_first_name": "",
        "recipient_user_id": uid,
        "recipient_username": username,
        "recipient_first_name": "",
        "amount": int(row["amount"]),
        "result_flag": "-",
        "is_friend": False,
        "gift_id": int(row["gift_id"] or 0),
        "gift_emoji": row["gift_emoji"] or "⭐",
        "has_upgrade": int(row["has_upgrade"] or 0),
        "is_salary": True,
        "star_payout_id": int(row["id"]),
        "salary_id": int(row["salary_id"]) if row["salary_id"] else 0,
        "bonus_id": int(row["bonus_id"]) if row.get("bonus_id") else 0,
        "salary_source": row["source"] or "salary",
        "status": "pending",
        "token": token,
    }


def _normalize_gift_items(gifts: list[dict] | None, *, fallback_amount: int) -> list[dict]:
    """Список подарков → [{giftId, giftEmoji, hasUpgrade, stars}, ...]."""
    if not gifts:
        return [{
            "giftId": 0,
            "giftEmoji": "⭐",
            "hasUpgrade": 0,
            "stars": int(fallback_amount),
        }]
    out: list[dict] = []
    for g in gifts:
        if not isinstance(g, dict):
            continue
        stars = int(g.get("stars") or g.get("amount") or 0)
        gift_id = int(g.get("giftId") or g.get("gift_id") or 0)
        if stars <= 0:
            continue
        out.append({
            "giftId": gift_id,
            "giftEmoji": (g.get("giftEmoji") or g.get("gift_emoji") or g.get("emoji") or "⭐")[:32],
            "hasUpgrade": int(g.get("hasUpgrade") or g.get("has_upgrade") or 0),
            "stars": stars,
        })
    if not out:
        return [{
            "giftId": 0,
            "giftEmoji": "⭐",
            "hasUpgrade": 0,
            "stars": int(fallback_amount),
        }]
    return out


async def enqueue_salary_channel_request(
    *,
    salary_id: int,
    user_id: int,
    amount: int,
    requested_by: int,
    stars_username: str | None = None,
    gift_id: int = 0,
    gift_emoji: str = "⭐",
    has_upgrade: int = 0,
    gifts: list[dict] | None = None,
    first_name: str = "",
) -> list[dict]:
    """
    Строгий флоу зарплаты Stars:
    назначена/одобрена/выплата → N заявок в канал (1 подарок = 1 сообщение) → 👍 → userbot.

    Пост в канал делается СРАЗУ через Bot API (не ждём фоновый воркер).
    """
    await cancel_open_star_payouts_for_salary(salary_id)

    if gifts:
        items = _normalize_gift_items(gifts, fallback_amount=amount)
        gift_sum = sum(int(i["stars"]) for i in items)
        if gift_sum != int(amount):
            raise ValueError(
                f"Сумма подарков {gift_sum}⭐ не равна сумме выплаты {amount}⭐. "
                "Подберите подарки так, чтобы сумма совпала (например 50+50+15=115)."
            )
    elif gift_id:
        items = [{
            "giftId": int(gift_id),
            "giftEmoji": gift_emoji or "⭐",
            "hasUpgrade": int(has_upgrade or 0),
            "stars": int(amount),
        }]
    else:
        items = _normalize_gift_items(None, fallback_amount=amount)

    # Имя для ссылки в канале
    if not first_name:
        try:
            first_name = await db.pool.fetchval(
                "SELECT first_name FROM admin_accounts WHERE user_id = $1", user_id
            ) or ""
        except Exception:
            first_name = ""

    posted: list[dict] = []
    parts = len(items)
    for idx, item in enumerate(items, start=1):
        row = await enqueue_star_payout(
            salary_id=salary_id,
            user_id=user_id,
            amount=int(item["stars"]),
            stars_username=stars_username or "",
            method="userbot",
            requested_by=requested_by,
            source="salary",
            kind="payment",
            gift_id=int(item["giftId"] or 0),
            gift_emoji=item["giftEmoji"] or "⭐",
            has_upgrade=int(item["hasUpgrade"] or 0),
        )
        try:
            delivered = await deliver_salary_payout_to_channel(
                int(row["id"]),
                first_name=first_name,
                part=idx if parts > 1 else None,
                parts=parts if parts > 1 else None,
            )
            posted.append(delivered)
        except Exception as e:
            logger.exception("immediate channel post failed payout=%s", row["id"])
            # Остаётся queued — подхватит воркер бота
            failed = await get_star_payout(int(row["id"]))
            if failed:
                failed = {**failed, "error": str(e)[:300]}
                posted.append(failed)
            else:
                posted.append(row)
    return posted
