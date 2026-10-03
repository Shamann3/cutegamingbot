"""Текст правил из публичного канала Telegram.

Берём сообщения, которые страница канала реально отдала.
Закрытый пост без текста не подменяется заготовкой.
"""
from __future__ import annotations

import html as html_lib
import re
import time
from typing import Awaitable, Callable

CHANNEL = "CuteRules"
_POST = re.compile(r'data-post="([A-Za-z0-9_]+)/(\d+)"')
_TEXT = re.compile(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
_TAG = re.compile(r"<[^>]+>")
_BEFORE = re.compile(r"[?&]before=(\d+)")

Fetch = Callable[[str, bool], Awaitable[tuple[int, str, str]]]

_CACHE: dict = {"at": 0.0, "payload": None}
_OK_TTL = 300
_MISS_TTL = 20


def clear_rules_cache() -> None:
    _CACHE["at"] = 0.0
    _CACHE["payload"] = None


def _plain(fragment: str) -> str:
    text = fragment.replace("<br/>", "\n").replace("<br />", "\n").replace("<br>", "\n")
    text = _TAG.sub("", text)
    text = html_lib.unescape(text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def parse_rules_html(page: str, channel: str = CHANNEL) -> tuple[list[dict], int]:
    """Сообщения с текстом и число постов, у которых текста на странице нет."""
    marks = list(_POST.finditer(page or ""))
    readable: list[dict] = []
    hidden = 0
    wanted = channel.lower()
    for index, mark in enumerate(marks):
        if mark.group(1).lower() != wanted:
            continue
        end = marks[index + 1].start() if index + 1 < len(marks) else len(page)
        chunk = page[mark.start():end]
        post_id = int(mark.group(2))
        found = _TEXT.search(chunk)
        text = _plain(found.group(1)) if found else ""
        if text:
            readable.append({"id": post_id, "text": text})
        elif "message_media_not_supported" in chunk or "text_not_supported" in chunk:
            hidden += 1
    readable.sort(key=lambda item: item["id"])
    return readable, hidden


def _missing(page: str) -> bool:
    if not page:
        return True
    return "tgme_widget_message_error" in page or "Post not found" in page


async def collect_channel_rules(fetch: Fetch, channel: str = CHANNEL) -> dict:
    status, final_url, page = await fetch(f"https://t.me/s/{channel}", False)
    if status == 200 and final_url.rstrip("/").endswith(f"/s/{channel}") and "data-post=" in page:
        readable, hidden = await _pages(fetch, channel, page)
        return _payload(readable, hidden)

    readable: list[dict] = []
    hidden = 0
    misses = 0
    post_id = 1
    while misses < 5 and post_id <= 40:
        post_status, _final, post_page = await fetch(
            f"https://t.me/{channel}/{post_id}?embed=1",
            True,
        )
        if post_status != 200 or _missing(post_page):
            misses += 1
        else:
            misses = 0
            found, concealed = parse_rules_html(post_page, channel)
            if found:
                readable.extend(found)
            else:
                hidden += concealed or 1
        post_id += 1
    return _payload(readable, hidden)


async def _pages(fetch: Fetch, channel: str, first: str) -> tuple[list[dict], int]:
    readable, hidden = parse_rules_html(first, channel)
    seen_before: set[int] = set()
    page = first
    for _ in range(8):
        older = _BEFORE.findall(page)
        if not older:
            break
        before = int(older[0])
        if before in seen_before:
            break
        seen_before.add(before)
        status, _final, page = await fetch(f"https://t.me/s/{channel}?before={before}", True)
        if status != 200:
            break
        more, more_hidden = parse_rules_html(page, channel)
        readable.extend(more)
        hidden += more_hidden
    dedup = {item["id"]: item for item in readable}
    return [dedup[key] for key in sorted(dedup)], hidden


def _payload(readable: list[dict], hidden: int) -> dict:
    if hidden or not readable:
        return {
            "messages": [],
            "hidden": hidden,
            "error": (
                "В канале есть сообщения, но Telegram не отдал их текст на сайт."
                if hidden
                else "В канале правил нет сообщений."
            ),
        }
    return {"messages": readable, "hidden": 0, "error": ""}


async def _live_fetch(url: str, follow: bool) -> tuple[int, str, str]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": "CuteEpsilonPanel/1.0"}) as session:
        async with session.get(url, allow_redirects=follow) as resp:
            body = await resp.text(errors="replace")
            return resp.status, str(resp.url), body


async def load_channel_rules(channel: str = CHANNEL) -> dict:
    now = time.monotonic()
    cached = _CACHE["payload"]
    if cached is not None:
        ttl = _OK_TTL if cached.get("messages") else _MISS_TTL
        if now - float(_CACHE["at"]) < ttl:
            return cached
    payload = await collect_channel_rules(_live_fetch, channel)
    _CACHE["at"] = now
    _CACHE["payload"] = payload
    return payload
