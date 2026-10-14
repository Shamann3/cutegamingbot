# -*- coding: utf-8 -*-
"""Кто написал сообщение, на которое ответил бот.

Telegram в ответе на ответ бота не присылает человека внутри.
Пока бот жив, он сам помнит: это сообщение человека и этот ответ бота.
"""
from __future__ import annotations

from collections import OrderedDict

from aiogram import BaseMiddleware
from aiogram.client.session.middlewares.base import BaseRequestMiddleware

_LIMIT = 8000
_AUTHORS: OrderedDict = OrderedDict()
_BOT_REPLIES: OrderedDict = OrderedDict()


def reset_reply_origin() -> None:
    _AUTHORS.clear()
    _BOT_REPLIES.clear()


def _keep(store: OrderedDict, key, value) -> None:
    store[key] = value
    store.move_to_end(key)
    while len(store) > _LIMIT:
        store.popitem(last=False)


def _chat_id(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def note_human(chat_id, message_id, user_id) -> None:
    chat = _chat_id(chat_id)
    try:
        mid = int(message_id)
        uid = int(user_id)
    except (TypeError, ValueError):
        return
    if chat is None or mid <= 0 or uid <= 0:
        return
    _keep(_AUTHORS, (chat, mid), uid)


def note_bot_reply(chat_id, bot_message_id, reply_to_message_id) -> None:
    """Ответ бота указывает на человека, чьё сообщение он закрыл."""
    chat = _chat_id(chat_id)
    try:
        bot_mid = int(bot_message_id)
        origin_mid = int(reply_to_message_id)
    except (TypeError, ValueError):
        return
    if chat is None or bot_mid <= 0 or origin_mid <= 0:
        return
    person = _AUTHORS.get((chat, origin_mid))
    if person is None:
        person = _BOT_REPLIES.get((chat, origin_mid))
    if person is None:
        return
    _keep(_BOT_REPLIES, (chat, bot_mid), int(person))


def person_behind(chat_id, message_id) -> int | None:
    chat = _chat_id(chat_id)
    try:
        mid = int(message_id)
    except (TypeError, ValueError):
        return None
    if chat is None or mid <= 0:
        return None
    person = _BOT_REPLIES.get((chat, mid))
    return int(person) if person else None


def note_update(event) -> None:
    message = getattr(event, "message", None) or getattr(event, "edited_message", None)
    if message is None and getattr(event, "from_user", None) is not None and getattr(event, "message_id", None):
        message = event
    if message is None:
        return
    user = getattr(message, "from_user", None)
    if user is None or getattr(user, "is_bot", False):
        return
    chat = getattr(message, "chat", None)
    note_human(getattr(chat, "id", None), getattr(message, "message_id", None), getattr(user, "id", None))


def _reply_id(method) -> int | None:
    params = getattr(method, "reply_parameters", None)
    mid = getattr(params, "message_id", None) if params is not None else None
    if mid is None and isinstance(params, dict):
        mid = params.get("message_id")
    if mid is None:
        mid = getattr(method, "reply_to_message_id", None)
    try:
        value = int(mid)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def note_outgoing(method, result) -> None:
    reply_to = _reply_id(method)
    if reply_to is None or result is None:
        return
    messages = result if isinstance(result, list) else [result]
    for sent in messages:
        chat = getattr(getattr(sent, "chat", None), "id", None)
        if chat is None:
            chat = getattr(method, "chat_id", None)
        note_bot_reply(chat, getattr(sent, "message_id", None), reply_to)


class ReplyOriginMiddleware(BaseRequestMiddleware):
    """После отправки запоминает, какому человеку ответил бот."""

    async def __call__(self, make_request, bot, method):
        result = await make_request(bot, method)
        try:
            note_outgoing(method, result)
        except Exception:
            pass
        return result


class ReplyOriginUpdate(BaseMiddleware):
    """Входящее сообщение человека запоминается до ответа бота."""

    async def __call__(self, handler, event, data):
        try:
            note_update(event)
        except Exception:
            pass
        return await handler(event, data)


def person_behind_bot_message(reply, *, chat_id=None) -> int | None:
    """Человек, на чьё сообщение бот ответил этим сообщением."""
    if reply is None:
        return None
    nested = getattr(reply, "reply_to_message", None)
    nested_user = getattr(nested, "from_user", None) if nested is not None else None
    if nested_user is not None and not getattr(nested_user, "is_bot", False):
        try:
            uid = int(nested_user.id)
        except (TypeError, ValueError):
            uid = 0
        if uid > 0:
            return uid
    chat = chat_id
    if chat is None:
        chat = getattr(getattr(reply, "chat", None), "id", None)
    return person_behind(chat, getattr(reply, "message_id", None))
