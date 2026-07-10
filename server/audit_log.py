"""Логи покупок и баланса + уведомления в приватную Telegram-группу."""

from __future__ import annotations

import asyncio
import html
import json
import logging
from typing import Any

import asyncpg

from config import AUDIT_LOG_ENABLED, AUDIT_TELEGRAM_CHAT_ID, AUDIT_TELEGRAM_THREAD_ID
from telegram_notify import send_telegram_message

logger = logging.getLogger("cute-farm.audit")

_EVENT_LABELS = {
    "shop_buy": "Покупка на бирже",
    "plot_buy": "Покупка грядки",
    "plot_clear": "Очистка засохшей грядки",
    "craft_success": "Успешный крафт",
    "craft_fail": "Неудачный крафт",
    "market_buy": "Покупка на бирже (P2P)",
    "market_sell": "Продажа на бирже (P2P)",
}


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=False)


def _format_message(
    event_type: str,
    user_id: int,
    *,
    amount: int | None = None,
    balance_before: int | None = None,
    balance_after: int | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    title = _EVENT_LABELS.get(event_type, event_type)
    lines = [
        f"<b>{_escape(title)}</b>",
        f"<tg-emoji emoji-id='5364052602357044385'>🐶</tg-emoji> ID: <code>{_escape(user_id)}</code>",
    ]

    details = details or {}

    if event_type == "shop_buy":
        emoji = details.get("emoji") or "<tg-emoji emoji-id='5884479287171485878'>📦</tg-emoji>"
        name = details.get("name") or details.get("item_id") or "предмет"
        qty = details.get("quantity") or 1
        paid = details.get("paid") or (-amount if amount else 0)
        remains = details.get("remains_after")
        lines.append(f"<code>{_escape(emoji)}</code> <b>{_escape(name)} ×{_escape(qty)}</b>")
        lines.append(f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Списано : {_escape(paid)} кут</b>")
        if remains is not None:
            lines.append(f"<tg-emoji emoji-id='5285134837445838777'>📊</tg-emoji> <b>Остаток на бирже : {_escape(remains)}</b>")
    elif event_type == "plot_buy":
        plot_id = details.get("plot_id")
        price = details.get("price") or (-amount if amount else 0)
        if plot_id is not None:
            lines.append(f"<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> <b>Грядка №{_escape(plot_id)}</b>")
        lines.append(f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Списано : {_escape(price)} кут</b>")
    elif event_type == "plot_clear":
        plot_id = details.get("plot_id")
        cost = details.get("cost") or (-amount if amount else 0)
        if plot_id is not None:
            lines.append(f"<tg-emoji emoji-id='5208923808169222461'>🥀</tg-emoji> <b>Грядка №{_escape(plot_id)}</b>")
        lines.append(f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Списано : {_escape(cost)} кут</b>")
    elif event_type in ("craft_success", "craft_fail"):
        emoji = details.get("result_emoji") or "<tg-emoji emoji-id='5323473579545750037'>🧪</tg-emoji>"
        name = details.get("result_name") or "предмет"
        chance = details.get("success_percent")
        lines.append(f"<tg-emoji emoji-id='5323473579545750037'>🧪</tg-emoji> <b>Рецепт #{_escape(details.get('recipe_id', '?'))}</b>")
        lines.append(f"<tg-emoji emoji-id='5256131095094652290'>🎯</tg-emoji> <b>Результат : {_escape(emoji)} {_escape(name)}</b>")
        if chance is not None:
            lines.append(f"<tg-emoji emoji-id='6010285923017692806'>⬆️</tg-emoji> <b>Шанс : {_escape(chance)}%</b>")
        lines.append("<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Успех</b>" if event_type == "craft_success" else "<tg-emoji emoji-id='5397751602956239123'>🔥</tg-emoji> <b>Провал</b>")
    elif event_type == "market_buy":
        emoji = details.get("emoji") or "<tg-emoji emoji-id='5884479287171485878'>📦</tg-emoji>"
        name = details.get("name") or details.get("item_id") or "предмет"
        qty = details.get("quantity") or 1
        paid = details.get("paid") or (-amount if amount else 0)
        lines.append(f"<code>{_escape(emoji)}</code> <b>{_escape(name)} ×{_escape(qty)}</b>")
        lines.append(f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Списано : {_escape(paid)} кут</b>")
        if details.get("seller_id") is not None:
            lines.append(f"<tg-emoji emoji-id='5280835811405762543'>😎</tg-emoji> <b>Продавец : <code>{_escape(details['seller_id'])}</code></b>")
    elif event_type == "market_sell":
        emoji = details.get("emoji") or "<tg-emoji emoji-id='5884479287171485878'>📦</tg-emoji>"
        name = details.get("name") or details.get("item_id") or "предмет"
        qty = details.get("quantity") or 1
        gross = details.get("gross") or 0
        commission = details.get("commission") or 0
        payout = details.get("payout") or (amount if amount else 0)
        lines.append(f"<code>{_escape(emoji)}</code> <b>{_escape(name)} ×{_escape(qty)}</b>")
        lines.append(f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Сумма : {_escape(gross)} кут</b>")
        lines.append(f"<tg-emoji emoji-id='5436161684462932267'>📉</tg-emoji> <b>Комиссия : {_escape(commission)} кут</b>")
        lines.append(f"<tg-emoji emoji-id='5251676977785483690'>✨</tg-emoji> <b>Выплата : +{_escape(payout)} кут</b>")
        if details.get("buyer_id") is not None:
            lines.append(f"<tg-emoji emoji-id='5364052602357044385'>🐶</tg-emoji> <b>Покупатель : <code>{_escape(details['buyer_id'])}</code></b>")
    elif amount is not None:
        sign = "+" if amount > 0 else ""
        lines.append(f"<tg-emoji emoji-id='5375296873982604963'>💰</tg-emoji> <b>Изменение : {sign}{_escape(amount)} кут</b>")

    if balance_before is not None and balance_after is not None:
        lines.append(
            f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Баланс : {_escape(balance_before)} → {_escape(balance_after)} кут</b>"
        )
    elif balance_after is not None:
        lines.append(f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Баланс : {_escape(balance_after)} кут</b>")

    return "\n".join(lines)


async def _insert_event(
    pool: asyncpg.Pool,
    event_type: str,
    user_id: int,
    *,
    amount: int | None = None,
    balance_before: int | None = None,
    balance_after: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    payload = json.dumps(details or {}, ensure_ascii=False)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_events (
                user_id, event_type, amount, balance_before, balance_after, details
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            user_id,
            event_type,
            amount,
            balance_before,
            balance_after,
            payload,
        )


async def _notify_telegram(text: str) -> None:
    if not (AUDIT_LOG_ENABLED and AUDIT_TELEGRAM_CHAT_ID):
        return
    try:
        await send_telegram_message(
            text,
            chat_id=AUDIT_TELEGRAM_CHAT_ID,
            thread_id=AUDIT_TELEGRAM_THREAD_ID,
        )
    except Exception:
        logger.exception("Audit Telegram notify failed")


async def record_balance_event(
    pool: asyncpg.Pool | None,
    event_type: str,
    user_id: int,
    *,
    amount: int | None = None,
    balance_before: int | None = None,
    balance_after: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    if not AUDIT_LOG_ENABLED:
        return

    if pool is not None:
        try:
            await _insert_event(
                pool,
                event_type,
                user_id,
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                details=details,
            )
        except Exception:
            logger.exception("Audit DB insert failed (%s)", event_type)

    message = _format_message(
        event_type,
        user_id,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        details=details,
    )
    asyncio.create_task(_notify_telegram(message))


def schedule_balance_event(
    pool: asyncpg.Pool | None,
    event_type: str,
    user_id: int,
    *,
    amount: int | None = None,
    balance_before: int | None = None,
    balance_after: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Не блокирует покупку: лог и Telegram в фоне."""
    if not AUDIT_LOG_ENABLED:
        return
    asyncio.create_task(
        record_balance_event(
            pool,
            event_type,
            user_id,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            details=details,
        )
    )
