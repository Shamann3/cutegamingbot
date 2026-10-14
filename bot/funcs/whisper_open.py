# -*- coding: utf-8 -*-
"""Шёпот: в чате карточка, а сам текст видит только адресат."""
from __future__ import annotations

import asyncio
import html
import re
import secrets

from aiogram.types import EphemeralMessageParameters

WHISPER_TTL = 6 * 60 * 60
_ALERT = 200
_WORDS = ("прошептать", "шептнуть", "шепнуть")
_BOX: dict[str, dict] = {}
_WAIT: dict[int, dict] = {}
_TOKENS: dict[str, int] = {}
BOT_OPEN = "https://t.me/CuteGamingBot"
_NOT_A_PERSON = {"joinchat", "addstickers", "share", "proxy", "socks", "iv", "login"}
_LINK = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/@?([A-Za-z0-9_]{4,32})/?",
    re.IGNORECASE,
)
_TG_USER = re.compile(r"tg://user\?id=(\d+)", re.IGNORECASE)
_PLAIN_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{3,31}")


def whisper_body(text: str) -> str | None:
    """Текст после команды. None, если это не шёпот."""
    raw = str(text or "").strip()
    low = raw.lower()
    for word in _WORDS:
        if low.startswith(word):
            return raw[len(word):].strip()
    return None


def look_like_target(token: str, *, plain: bool = False) -> tuple[str, str] | None:
    """('username', имя) или ('id', цифры). Иначе это не адрес человека."""
    raw = str(token or "").strip().strip("<>").rstrip(".,);")
    if not raw:
        return None
    if raw.startswith("@"):
        name = raw[1:]
        if re.fullmatch(r"[A-Za-z0-9_]{4,32}", name):
            return ("username", name)
        return None
    found = _TG_USER.fullmatch(raw)
    if found:
        return ("id", found.group(1))
    if raw.isdigit() and len(raw) >= 5:
        return ("id", raw)
    link = _LINK.fullmatch(raw.split("?", 1)[0].split("#", 1)[0])
    if link:
        name = link.group(1)
        if name.lower() in _NOT_A_PERSON:
            return None
        if name.isdigit():
            return ("id", name)
        return ("username", name)
    if plain and _PLAIN_NAME.fullmatch(raw):
        return ("username", raw)
    return None


def split_address(body: str, *, plain: bool = False) -> tuple[tuple[str, str] | None, str]:
    """Первое слово — адрес, остальное — текст шёпота."""
    text = str(body or "").strip()
    if not text:
        return None, ""
    head, _, tail = text.partition(" ")
    target = look_like_target(head, plain=plain)
    if target is None:
        return None, text
    return target, tail.strip()


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


def group_has_secret(body: str) -> bool:
    """В группе после команды уже написан текст. Его нельзя прятать удалением."""
    return bool(str(body or "").strip())


def ask_text(receiver_name: str, *, leaked: bool) -> str:
    who = html.escape(" ".join(str(receiver_name or "").split()) or "этого человека")
    if leaked:
        return (
            "<b>Этот текст уже был в группе.</b>\n"
            "Администратор может открыть удалённое сообщение в недавних действиях.\n"
            f"Напишите другой шёпот для {who} сюда. В группе его не будет."
        )
    return (
        f"<b>Напишите шёпот для {who}.</b>\n"
        "Текст останется в этой переписке. В группе будет только карточка, без слов."
    )


def arm_wait(*, sender_id: int, receiver_id: int, sender_name: str, receiver_name: str, chat_id: int) -> str:
    token = secrets.token_hex(6)
    sender = int(sender_id)
    previous = _WAIT.pop(sender, None)
    if previous:
        _TOKENS.pop(str(previous.get("token") or ""), None)
    _WAIT[sender] = {
        "token": token,
        "receiver_id": int(receiver_id),
        "sender_name": " ".join(str(sender_name or "").split()),
        "receiver_name": " ".join(str(receiver_name or "").split()),
        "chat_id": int(chat_id),
    }
    _TOKENS[token] = sender
    try:
        asyncio.get_running_loop()
        asyncio.create_task(_expire_wait(sender, token))
    except RuntimeError:
        pass
    return token


async def _expire_wait(sender_id: int, token: str) -> None:
    await asyncio.sleep(WHISPER_TTL)
    row = _WAIT.get(int(sender_id))
    if row and row.get("token") == token:
        _WAIT.pop(int(sender_id), None)
        _TOKENS.pop(token, None)


def waiting(sender_id: int) -> dict | None:
    row = _WAIT.get(int(sender_id))
    return dict(row) if row else None


def claim_wait(sender_id: int) -> dict | None:
    row = _WAIT.pop(int(sender_id), None)
    if not row:
        return None
    _TOKENS.pop(str(row.get("token") or ""), None)
    return row


def wait_owner(token: str) -> int | None:
    sender = _TOKENS.get(str(token or ""))
    return int(sender) if sender else None


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
        try:
            await callback.answer()
        except Exception:
            pass
        return
    try:
        await callback.answer(alert_text(record["text"]), show_alert=True)
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
