# -*- coding: utf-8 -*-
"""+ в технических кошельках со стороны FastAPI (биржа).

Игровой бот пишет те же «+ 1.234», что и main.py. Чёрный рынок не трогаем —
там уже свои плюсы из игр.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from config import (
    BACKGROUND_EARNINGS_CHAT_ID,
    BOT_TOKEN,
    MODERATION_BOT_TOKEN,
    TECH_CHAT_ID,
)

log = logging.getLogger("tech_plus")

PROFIT_JAR_CHAT_ID = -1004238101266
GAME_COMMISSION_CHAT_ID = -1004324787050

PLUS_CHAT_IDS = frozenset(
    {
        int(GAME_COMMISSION_CHAT_ID),
        int(BACKGROUND_EARNINGS_CHAT_ID),
        int(PROFIT_JAR_CHAT_ID),
    }
)
BLACK_MARKET_CHAT_ID = int(TECH_CHAT_ID)


def fmt_plus_amount(value: Any) -> str:
    try:
        return "{:,.0f}".format(int(value)).replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def format_tech_plus(amount: Any) -> str:
    return f"<blockquote><b>+ {fmt_plus_amount(amount)}</b></blockquote>"


def should_announce_plus(chat_id: Any) -> bool:
    try:
        cid = int(chat_id)
    except (TypeError, ValueError):
        return False
    if cid == BLACK_MARKET_CHAT_ID:
        return False
    return cid in PLUS_CHAT_IDS


async def _send(chat_id: int, amount: int) -> None:
    from telegram_notify import send_telegram_message

    token = MODERATION_BOT_TOKEN or BOT_TOKEN
    await send_telegram_message(
        format_tech_plus(amount),
        chat_id=str(chat_id),
        token=token,
    )


def schedule_tech_plus(chat_id: Any, amount: Any) -> None:
    try:
        cid = int(chat_id)
        amt = int(amount)
    except (TypeError, ValueError):
        return
    if amt <= 0 or not should_announce_plus(cid):
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _run() -> None:
        try:
            await _send(cid, amt)
        except Exception as exc:
            log.warning("tech plus fail chat=%s +%s: %s: %s", cid, amt, type(exc).__name__, exc)

    loop.create_task(_run())
