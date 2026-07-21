"""Уведомления игрокам: WebApp (мгновенный push + очередь) + Telegram DM."""

from __future__ import annotations

import asyncio
import html
import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from notification_hub import publish as publish_notification
from telegram_notify import send_telegram_message
from market_rules import MARKET_COMMISSION_PERCENT

logger = logging.getLogger("cute-farm.notify")


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=False)


def _format_notification_row(
    row_id: int,
    event_type: str,
    payload: dict[str, Any],
    created_at: datetime | None,
) -> dict:
    created_iso = None
    if created_at is not None:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_iso = created_at.isoformat()
    return {
        "id": int(row_id),
        "eventType": event_type,
        "payload": payload,
        "createdAt": created_iso,
    }


def format_market_sale_telegram(
    *,
    emoji: str,
    name: str,
    quantity: int,
    gross: int,
    commission: int,
    payout: int,
    balance: int | None = None,
) -> str:
    lines = [
        "<b><tg-emoji emoji-id='5472401690793614752'>🛍️</tg-emoji> Ваш лот на бирже продан!</b>",
        f"<code>{_escape(emoji)}</code> <b>{_escape(name)} ×{_escape(quantity)}</b>",
        f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Сумма сделки : {_escape(gross)} кут</b>",
        f"<tg-emoji emoji-id='5436161684462932267'>📉</tg-emoji> <b>Комиссия {MARKET_COMMISSION_PERCENT}%: −{_escape(commission)} кут</b>",
        f"<tg-emoji emoji-id='5251676977785483690'>✨</tg-emoji> <b>На баланс : +{_escape(payout)} кут</b>",
    ]
    if balance is not None:
        lines.append(f"<tg-emoji emoji-id='5422818196031840237'>💼</tg-emoji> Баланс : {_escape(balance)} кут")
    return "\n".join(lines)


async def _insert_notification(
    pool: asyncpg.Pool,
    user_id: int,
    event_type: str,
    payload: dict[str, Any],
) -> dict | None:
    body = json.dumps(payload, ensure_ascii=False)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_notifications (user_id, event_type, payload)
            VALUES ($1, $2, $3::jsonb)
            RETURNING id, event_type, payload, created_at
            """,
            user_id,
            event_type,
            body,
        )
    if not row:
        return None
    stored_payload = row["payload"]
    if isinstance(stored_payload, str):
        stored_payload = json.loads(stored_payload)
    return _format_notification_row(
        int(row["id"]),
        row["event_type"],
        stored_payload or {},
        row["created_at"],
    )


async def _send_telegram_dm(user_id: int, text: str) -> None:
    try:
        await send_telegram_message(text, chat_id=str(user_id))
    except Exception:
        logger.exception("User Telegram notify failed (user_id=%s)", user_id)


def schedule_player_telegram_dm(user_id: int, text: str) -> None:
    asyncio.create_task(_send_telegram_dm(user_id, text))


async def create_market_sale_notification(
    pool: asyncpg.Pool | None,
    seller_id: int,
    *,
    listing_id: int,
    item_id: str,
    name: str,
    emoji: str,
    quantity: int,
    gross: int,
    commission: int,
    payout: int,
    balance: int | None = None,
    buyer_id: int | None = None,
) -> dict | None:
    payload = {
        "type": "market_sale",
        "listingId": listing_id,
        "itemId": item_id,
        "name": name,
        "emoji": emoji or "📦",
        "quantity": quantity,
        "gross": gross,
        "commission": commission,
        "payout": payout,
        "balance": balance,
        "buyerId": buyer_id,
    }

    notification = None
    if pool is not None:
        try:
            notification = await _insert_notification(pool, seller_id, "market_sale", payload)
        except Exception:
            logger.exception("Notification DB insert failed (market_sale)")
    if notification is None:
        notification = _format_notification_row(
            0,
            "market_sale",
            payload,
            datetime.now(timezone.utc),
        )

    publish_notification(seller_id, notification)
    return notification


def schedule_market_sale_telegram(
    seller_id: int,
    *,
    emoji: str,
    name: str,
    quantity: int,
    gross: int,
    commission: int,
    payout: int,
    balance: int | None = None,
) -> None:
    text = format_market_sale_telegram(
        emoji=emoji or "📦",
        name=name,
        quantity=quantity,
        gross=gross,
        commission=commission,
        payout=payout,
        balance=balance,
    )
    schedule_player_telegram_dm(seller_id, text)


def format_market_purchase_broadcast(
    *,
    emoji: str,
    name: str,
    quantity: int,
    paid: int,
    buyer_name: str | None = None,
    buyer_username: str | None = None,
) -> str:
    """Публичное объявление о покупке на бирже для групповых чатов."""
    uname = (buyer_username or "").lstrip("@").strip()
    if uname:
        label = _escape(buyer_name or f"@{uname}")
        buyer = f"<a href='https://t.me/{_escape(uname)}'>{label}</a>"
    elif buyer_name:
        buyer = _escape(buyer_name)
    else:
        buyer = "Игрок"
    lines = [
        "<b><tg-emoji emoji-id='5406683434124859552'>🛍</tg-emoji> Новая сделка на бирже!</b>",
        "",
        f"<tg-emoji emoji-id='5193065010795911968'>🛍</tg-emoji> <b>{buyer} только что забрал(а) лот :</b>",
        f"<code>{_escape(emoji or '📦')}</code> <b>{_escape(name)} ×{_escape(quantity)}</b>",
        f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>За {_escape(paid)} кут</b>",
        "",
        "<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> <b><i>Торгуй и ты!</i></b>",
    ]
    return "\n".join(lines)


async def _broadcast_market_purchase(text: str) -> None:
    from config import MARKET_BROADCAST_GROUP_IDS

    for chat_id in MARKET_BROADCAST_GROUP_IDS:
        try:
            await send_telegram_message(text, chat_id=str(chat_id))
        except Exception:
            logger.exception("Market purchase broadcast failed (chat_id=%s)", chat_id)


def schedule_market_purchase_broadcast(
    *,
    emoji: str,
    name: str,
    quantity: int,
    paid: int,
    buyer_name: str | None = None,
    buyer_username: str | None = None,
) -> None:
    """Fire-and-forget: шлём объявление о покупке во все группы биржи."""
    text = format_market_purchase_broadcast(
        emoji=emoji or "📦",
        name=name,
        quantity=quantity,
        paid=paid,
        buyer_name=buyer_name,
        buyer_username=buyer_username,
    )
    asyncio.create_task(_broadcast_market_purchase(text))


async def create_admin_message_notification(
    pool: asyncpg.Pool | None,
    user_id: int,
    *,
    title: str,
    body: str = "",
    detail: str = "",
) -> dict | None:
    payload = {
        "type": "admin_message",
        "title": title,
        "body": body,
        "detail": detail or "",
    }
    notification = None
    if pool is not None:
        try:
            notification = await _insert_notification(pool, user_id, "admin_message", payload)
        except Exception:
            logger.exception("Notification DB insert failed (admin_message)")
    if notification is None:
        notification = _format_notification_row(
            0,
            "admin_message",
            payload,
            datetime.now(timezone.utc),
        )
    publish_notification(user_id, notification)
    return notification


async def create_admin_message_notifications_batch(
    pool: asyncpg.Pool | None,
    items: list[tuple[int, str, str, str]],
) -> int:
    """Bulk insert admin_message notifications. items: (user_id, title, body, detail)."""
    if pool is None or not items:
        return 0

    user_ids: list[int] = []
    payloads: list[str] = []
    for user_id, title, body, detail in items:
        payload = {
            "type": "admin_message",
            "title": title,
            "body": body,
            "detail": detail or "",
        }
        user_ids.append(int(user_id))
        payloads.append(json.dumps(payload, ensure_ascii=False))

    try:
        rows = await pool.fetch(
            """
            INSERT INTO user_notifications (user_id, event_type, payload)
            SELECT u, 'admin_message', p::jsonb
            FROM UNNEST($1::bigint[], $2::text[]) AS t(u, p)
            RETURNING id, user_id, event_type, payload, created_at
            """,
            user_ids,
            payloads,
        )
    except Exception:
        logger.exception("Batch admin_message insert failed")
        return 0

    for row in rows:
        stored_payload = row["payload"]
        if isinstance(stored_payload, str):
            stored_payload = json.loads(stored_payload)
        notification = _format_notification_row(
            int(row["id"]),
            row["event_type"],
            stored_payload or {},
            row["created_at"],
        )
        publish_notification(int(row["user_id"]), notification)

    return len(rows)
