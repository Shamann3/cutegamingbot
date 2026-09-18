# -*- coding: utf-8 -*-
"""+ в технических кошельках, кроме чёрного рынка.

Чёрный рынок уже пишет свои плюсы из игр. Здесь — касса комиссий,
фоновые заработки и копилка. Сообщение одно и то же: «+ 1.234».
Частые зачисления склеиваются на несколько секунд, чтобы не упереться
в лимит Telegram и не превратить чат в ленту из пятикутовых вспышек.
Сбор в копилку и возврат на лестницу уходят сразу.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from bot.config.config import (
    BACKGROUND_EARNINGS_CHAT_ID,
    GAME_COMMISSION_CHAT_ID,
    PROFIT_JAR_CHAT_ID,
    TECH_CHAT_ID,
)
from bot.funcs.tech_home_log import safe_send_tech_log

PLUS_CHAT_IDS = frozenset(
    {
        int(GAME_COMMISSION_CHAT_ID),
        int(BACKGROUND_EARNINGS_CHAT_ID),
        int(PROFIT_JAR_CHAT_ID),
    }
)
BLACK_MARKET_CHAT_ID = int(TECH_CHAT_ID)
COALESCE_SEC = 8.0
COALESCE_MAX = 20
IMMEDIATE_REASONS = frozenset({"sweep", "revert"})

_lock = asyncio.Lock()
_pending: Dict[int, Dict[str, Any]] = {}


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


async def _send(bot, chat_id: int, amount: int) -> None:
    if bot is None or amount <= 0:
        return
    html = format_tech_plus(amount)
    await safe_send_tech_log(
        bot,
        int(chat_id),
        html=html,
        fallback_html=html,
        tag="TECH_PLUS",
    )


async def _flush_chat(bot, chat_id: int) -> None:
    async with _lock:
        buf = _pending.pop(int(chat_id), None)
        amount = int(buf["amount"]) if buf else 0
        task = buf.get("task") if buf else None
        if task is not None:
            task.cancel()
    if amount > 0:
        await _send(bot, int(chat_id), amount)


async def _delayed_flush(bot, chat_id: int) -> None:
    try:
        await asyncio.sleep(COALESCE_SEC)
    except asyncio.CancelledError:
        return
    await _flush_chat(bot, chat_id)


async def announce_tech_plus(
    bot,
    chat_id: Any,
    amount: Any,
    *,
    reason: str = "",
    immediate: Optional[bool] = None,
) -> bool:
    """Пишет + в техгруппу. Никогда не бросает наружу — деньги уже прошли."""
    try:
        cid = int(chat_id)
        amt = int(amount)
    except (TypeError, ValueError):
        return False
    if bot is None or amt <= 0 or not should_announce_plus(cid):
        return False

    send_now = bool(immediate) if immediate is not None else (
        str(reason or "").strip().lower() in IMMEDIATE_REASONS
    )
    try:
        if send_now:
            await _flush_chat(bot, cid)
            await _send(bot, cid, amt)
            return True

        flush_now = 0
        async with _lock:
            buf = _pending.get(cid)
            if buf is None:
                buf = {"amount": 0, "n": 0, "task": None}
                _pending[cid] = buf
            buf["amount"] = int(buf["amount"]) + amt
            buf["n"] = int(buf["n"]) + 1
            if buf["n"] >= COALESCE_MAX:
                flush_now = int(buf["amount"])
                buf["amount"] = 0
                buf["n"] = 0
                task = buf.get("task")
                buf["task"] = None
                if task is not None:
                    task.cancel()
            elif buf.get("task") is None:
                buf["task"] = asyncio.create_task(_delayed_flush(bot, cid))
        if flush_now > 0:
            await _send(bot, cid, flush_now)
        return True
    except Exception as exc:
        print(f"[TECH_PLUS] announce fail chat={cid} +{amt}: {type(exc).__name__}: {exc}")
        return False


def schedule_tech_plus(bot, chat_id: Any, amount: Any, *, reason: str = "") -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(announce_tech_plus(bot, chat_id, amount, reason=reason))
