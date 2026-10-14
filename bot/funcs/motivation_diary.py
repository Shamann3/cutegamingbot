# -*- coding: utf-8 -*-
"""Дневник мотивации: живая цитата, а если сеть молчит — своя страница."""
from __future__ import annotations

import html
import random
from typing import Awaitable, Callable

SOURCES = (
    "https://zenquotes.io/api/random",
    "https://dummyjson.com/quotes/random",
)

# Короткие настоящие фразы. Ими дневник пользуется, только если оба источника молчат
# или английский текст не удалось перевести.
LOCAL = (
    ("Делай, что можешь, с тем, что имеешь, там, где ты есть.", "Теодор Рузвельт"),
    ("Путь в тысячу вёрст начинается с одного шага.", "Лао-цзы"),
    ("Не ошибается тот, кто ничего не делает.", "Теодор Рузвельт"),
    ("Счастье зависит от нас самих.", "Аристотель"),
    ("Верь, что сможешь, и ты уже на полпути.", "Теодор Рузвельт"),
    ("Трудности готовят обычных людей к необычной судьбе.", "К. С. Льюис"),
    ("Начни там, где ты есть. Используй то, что есть. Делай, что можешь.", "Артур Эш"),
    ("Единственный способ сделать работу хорошо — любить то, что делаешь.", "Стив Джобс"),
    ("Падать не страшно. Страшно не подняться.", "Мэри Пикфорд"),
    ("Будущее зависит от того, что ты делаешь сегодня.", "Махатма Ганди"),
    ("Смелость — это не отсутствие страха, а шаг вперёд вместе с ним.", "Нельсон Мандела"),
    ("Маленький шаг каждый день всё равно приводит к цели.", "японская пословица"),
)

_LAST = ""


def _clean(value) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\xa0", " ").split()).strip()


def quote_from_payload(payload) -> tuple[str, str] | None:
    """Достаёт текст и автора из ответа zenquotes или dummyjson."""
    row = None
    if isinstance(payload, list) and payload:
        row = payload[0] if isinstance(payload[0], dict) else None
    elif isinstance(payload, dict):
        row = payload
    if not row:
        return None
    text = _clean(row.get("q") or row.get("quote") or row.get("content"))
    author = _clean(row.get("a") or row.get("author"))
    if len(text) < 8 or len(text) > 500:
        return None
    if author.lower() in {"unknown", "anonymous"}:
        author = ""
    return text, author


def _cyrillic(text: str) -> bool:
    for char in text.lower():
        if "а" <= char <= "я" or char == "ё":
            return True
    return False


def page_html(text: str, author: str = "") -> str:
    body = html.escape(_clean(text))
    who = _clean(author)
    if not body:
        body = html.escape(LOCAL[0][0])
        who = LOCAL[0][1]
    if who:
        return f"<b>{body}</b>\n<i>{html.escape(who)}</i>"
    return f"<b>{body}</b>"


def local_quote() -> tuple[str, str]:
    global _LAST
    pool = [row for row in LOCAL if row[0] != _LAST] or list(LOCAL)
    picked = random.choice(pool)
    _LAST = picked[0]
    return picked


async def read_quote(fetch: Callable[[str], Awaitable[tuple[int, object]]]) -> tuple[str, str] | None:
    for url in SOURCES:
        try:
            status, payload = await fetch(url)
        except Exception:
            continue
        if int(status or 0) != 200:
            continue
        found = quote_from_payload(payload)
        if found:
            return found
    return None


async def _live_fetch(url: str) -> tuple[int, object]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=4)
    headers = {"User-Agent": "CuteGamingBot/1.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url) as response:
            if response.status != 200:
                return response.status, None
            return 200, await response.json(content_type=None)


def _usable_russian(original: str, translated: str) -> str:
    line = _clean(translated)
    if not line or line.lower() == original.lower() or not _cyrillic(line):
        return ""
    return line


def _mymemory(text: str) -> str:
    from deep_translator import MyMemoryTranslator
    return MyMemoryTranslator(source="english", target="russian").translate(text)


async def into_russian(
    text: str,
    *,
    translate: Callable[[str], Awaitable[str]] | None = None,
    memory: Callable[[str], str] | None = None,
) -> str:
    """Сначала общий переводчик бота, затем MyMemory, если Google молчит."""
    if _cyrillic(text):
        return text
    if translate is None:
        from bot.funcs.translate_gate import translate_async

        async def translate(value: str) -> str:
            return await translate_async(value, "ru", "en")
    try:
        russian = _usable_russian(text, await translate(text))
    except Exception:
        russian = ""
    if russian:
        return russian
    remember = memory or _mymemory
    try:
        import asyncio
        russian = _usable_russian(text, await asyncio.to_thread(remember, text))
    except Exception:
        russian = ""
    return russian


async def open_diary(
    *,
    fetch: Callable[[str], Awaitable[tuple[int, object]]] | None = None,
    translate: Callable[[str], Awaitable[str]] | None = None,
    memory: Callable[[str], str] | None = None,
) -> str:
    """Страница дневника. Сеть и перевод не роняют предмет."""
    getter = fetch or _live_fetch
    found = None
    try:
        found = await read_quote(getter)
    except Exception:
        found = None

    if found:
        text, author = found
        russian = await into_russian(text, translate=translate, memory=memory)
        if russian:
            return page_html(russian, author)

    line, who = local_quote()
    return page_html(line, who)
