# -*- coding: utf-8 -*-
"""Шёпот: в чате карточка, а сам текст видит только адресат."""
from __future__ import annotations

import asyncio
import html
import secrets

from aiogram.types import EphemeralMessageParameters

WHISPER_TTL = 6 * 60 * 60
_ALERT = 200
_WORDS = ("прошептать", "шепнуть")
_BOX: dict[str, dict] = {}


def whisper_body(text: str) -> str | None:
    """Текст после «прошептать» или «шепнуть». None, если это не шёпот."""
    raw = str(text or "").strip()
    low = raw.lower()
    for word in _WORDS:
        if low.startswith(word):
            return raw[len(word):].strip()
    return None


def whisper_page(sender_name: str, text: str) -> str:
    who = " ".join(str(sender_name or "").split()) or "Кто-то"
    body = str(text or "").strip()
    if len(body) > 3500:
        body = body[:3499] + "…"
    return (
        f"<b>Шёпот</b>\n"
        f"<i>от {html.escape(who)}</i>\n\n"
        f"{html.escape(body)}"
    )


def alert_text(text: str) -> str:
    body = " ".join(str(text or "").split())
    if not body:
        return "Пустой шёпот"
    if len(body) <= _ALERT:
        return body
    return body[: _ALERT - 1] + "…"


async def keep_whisper(*, sender_id: int, receiver_id: int, sender_name: str, text: str) -> str:
    token = secrets.token_hex(8)
    _BOX[token] = {
        "sender_id": int(sender_id),
        "receiver_id": int(receiver_id),
        "sender_name": " ".join(str(sender_name or "").split()),
        "text": str(text or "").strip(),
    }
    asyncio.create_task(_expire(token))
    return token


async def _expire(token: str) -> None:
    await asyncio.sleep(WHISPER_TTL)
    _BOX.pop(token, None)


def drop_whisper(token: str) -> None:
    _BOX.pop(str(token or ""), None)


async def present_whisper(callback) -> None:
    """Кнопка «Прочитать шёпот». Текст уходит только адресату."""
    data = str(getattr(callback, "data", "") or "")
    token = data.split(":", 1)[1] if ":" in data else ""
    record = _BOX.get(token)
    user = getattr(callback, "from_user", None)
    user_id = int(getattr(user, "id", 0) or 0)
    if record is None:
        await callback.answer("Шёпот уже пропал", show_alert=True)
        return
    if user_id != int(record["receiver_id"]):
        await callback.answer("Этот шёпот не для вас")
        return
    opened = await _send_private(callback, record)
    if opened:
        drop_whisper(token)
        try:
            await callback.answer()
        except Exception:
            pass
        return
    try:
        await callback.answer(alert_text(record["text"]), show_alert=True)
        drop_whisper(token)
    except Exception as exc:
        print(f"[WHISPER] alert fail {type(exc).__name__}")


async def _send_private(callback, record: dict) -> bool:
    message = getattr(callback, "message", None)
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    bot = getattr(callback, "bot", None) or getattr(message, "bot", None)
    if chat_id is None or bot is None:
        return False
    try:
        await bot.send_message(
            chat_id=int(chat_id),
            text=whisper_page(record["sender_name"], record["text"]),
            parse_mode="HTML",
            disable_web_page_preview=True,
            ephemeral_message_parameters=EphemeralMessageParameters(
                receiver_user_id=int(record["receiver_id"]),
                callback_query_id=str(callback.id),
                replace_callback_query_message=False,
            ),
        )
        return True
    except Exception as exc:
        print(f"[WHISPER] ephemeral fail {type(exc).__name__}")
        return False
