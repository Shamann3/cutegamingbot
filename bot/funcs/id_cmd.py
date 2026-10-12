# -*- coding: utf-8 -*-
"""Команда .id: числовой id по ответу, себе, @username, ссылке или имени в этом чате."""
from __future__ import annotations

import html
from typing import Optional

from aiogram import F, Router
from aiogram.types import Message

router = Router(name="id_cmd")
_attached = False


def parse_id_command(text: str) -> Optional[str]:
    """None — это не команда. Пустая строка — спросить себя или ответ. Иначе запрос."""
    raw = " ".join(str(text or "").split())
    folded = raw.casefold()
    if folded == ".id":
        return ""
    if not folded.startswith(".id ") and not folded.startswith(".id\t"):
        return None
    return raw[3:].strip()


def username_of(query: str) -> str:
    """Публичный username из @name или t.me/name. Ссылка на пост или закрытый чат — пусто."""
    text = str(query or "").strip()
    lower = text.casefold()
    for prefix in ("https://t.me/", "http://t.me/", "https://telegram.me/", "http://telegram.me/", "t.me/", "telegram.me/"):
        if lower.startswith(prefix):
            text = text[len(prefix):]
            break
    else:
        if text.startswith("@"):
            text = text[1:]
        else:
            return ""
    text = text.split("?", 1)[0].split("#", 1)[0].strip().strip("/")
    head = text.split("/", 1)[0]
    if not head or head.casefold() in {"c", "joinchat", "share", "addstickers", "s"} or head.startswith("+"):
        return ""
    return head


def _esc(value) -> str:
    return html.escape(str(value or ""), quote=False)


def numeric_target(query: str) -> Optional[int]:
    """Числовой id, в том числе id группы со знаком минус."""
    text = str(query or "").strip()
    if text.startswith("-"):
        body = text[1:]
        sign = -1
    else:
        body = text
        sign = 1
    if not body.isdigit() or len(body) > 16:
        return None
    return sign * int(body)


def _card(title: str, user_id: int, username: str = "") -> str:
    from bot.funcs.person_html import person_name_html
    shown = person_name_html(title, username, empty="Пользователь")
    extra = f"\n@{_esc(username)}" if username else ""
    return f"👤 {shown}{extra}\n🆔 <code>{int(user_id)}</code>"


@router.message(F.text.regexp(r"(?i)^\.id(?:\s+\S.*)?$"))
async def on_id(message: Message):
    query = parse_id_command(message.text or "")
    if query is None:
        return
    if query == "":
        reply = message.reply_to_message
        user = getattr(reply, "from_user", None) if reply is not None else None
        if user is not None and not getattr(user, "is_bot", False):
            await message.answer(_card(user.full_name or user.first_name or "Пользователь", user.id, user.username or ""))
            return
        if reply is not None and getattr(reply, "sender_chat", None) is not None:
            await message.answer("🕶 Это сообщение от имени канала или группы. Личного id Telegram не показывает.")
            return
        me = message.from_user
        if me is None:
            return
        await message.answer(_card(f"Ваш аккаунт: {me.full_name or me.first_name or 'вы'}", me.id, me.username or ""))
        return

    number = numeric_target(query)
    if number is not None:
        from bot.funcs.who_lookup import identify_numeric

        kind, found = await identify_numeric(number, get_chat=message.bot.get_chat)
        if found is None:
            await message.answer(
                f"❌ Не удалось получить данные для ID <code>{number}</code>.\n"
                "Возможно, бот ещё не видел этот чат."
            )
            return
        if kind == "person":
            mark = " 🤖" if found.is_bot else ""
            await message.answer(_card(f"{found.full_name or 'Без имени'}{mark}", int(found.user_id), found.username or ""))
            return
        title = found.title or "Без названия"
        title = f"Канал: {title}" if found.kind == "channel" else f"Группа: {title}"
        await message.answer(_card(title, int(found.chat_id or number), found.username or ""))
        return

    username = username_of(query)
    if username:
        from bot.funcs.who_lookup import identify_username

        kind, found = await identify_username(username, get_chat=message.bot.get_chat)
        if found is None:
            await message.answer(
                f"❌ Не удалось найти <code>@{_esc(username)}</code>.\n"
                "Проверьте написание или ответьте на сообщение этого человека."
            )
            return
        if kind == "place":
            title = found.title or username
            title = f"Канал: {title}" if found.kind == "channel" else f"Группа: {title}"
            if not found.chat_id:
                await message.answer(f"📋 {_esc(title)}\n@{_esc(found.username or username)}")
                return
            await message.answer(_card(title, int(found.chat_id), found.username or username))
            return
        mark = " 🤖" if getattr(found, "is_bot", False) else ""
        await message.answer(_card(f"{found.full_name or username}{mark}", int(found.user_id), found.username or username))
        return

    from bot.funcs.seen_people import find_names

    try:
        from main import db
        pool = getattr(db, "pool", None)
    except Exception:
        pool = None
    people = await find_names(pool, int(message.chat.id), query)
    if len(people) == 1:
        person = people[0]
        await message.answer(_card(person["name"] or "Пользователь", person["user_id"], person["username"]))
        return
    if people:
        lines = [f"🔍 По запросу «{_esc(query)}» нашлось несколько человек:"]
        for person in people:
            name = _esc(person["name"] or "без имени")
            nick = f" @{_esc(person['username'])}" if person["username"] else ""
            lines.append(f"• {name}{nick} — <code>{person['user_id']}</code>")
        await message.answer("\n".join(lines))
        return
    await message.answer(
        f"🔍 По запросу «{_esc(query)}» в этом чате никого не нашёл.\n\n"
        "Как ещё можно:\n"
        "• <code>.id @username</code> или ссылка t.me\n"
        "• ответить на сообщение нужного человека"
    )


def attach_id_command(dp) -> None:
    global _attached
    if _attached:
        return
    dp.include_router(router)
    _attached = True
