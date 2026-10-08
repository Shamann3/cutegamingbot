# -*- coding: utf-8 -*-
"""Разбор срока и нарушителя в любом порядке.

«мут навсегда @id причина» и «мут @id причина навсегда» — одна и та же команда.
Срок ищется по всей фразе, ссылка на человека тоже. Остальное — причина.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, Optional, Sequence, Tuple

FOREVER_WORDS = frozenset({
    "навсегда",
    "всегда",
    "вечность",
    "вечно",
    "бессрочно",
    "бессрочный",
    "навечно",
    "forever",
    "permanent",
    "perm",
    "перманент",
    "перманентно",
})


def _clean(token: str) -> str:
    return re.sub(r"[^\w]+", "", (token or "").casefold(), flags=re.UNICODE)


def is_forever_token(token: str) -> bool:
    return _clean(token) in FOREVER_WORDS


def forever_span_at(parts: Sequence[str], index: int) -> int:
    """1, если слово само по себе «навсегда»; 2 для «на всегда»."""
    if index < 0 or index >= len(parts):
        return 0
    if is_forever_token(parts[index]):
        return 1
    if (
        index + 1 < len(parts)
        and _clean(parts[index]) == "на"
        and is_forever_token(parts[index + 1])
    ):
        return 2
    return 0


def find_duration_span(
    parts: Sequence[str],
    parse_duration: Callable[[str], object],
) -> Optional[tuple[int, int, str]]:
    """Первый срок в фразе: (начало, конец, текст). Конец не входит в срез."""
    count = len(parts)
    for index in range(count):
        wide = forever_span_at(parts, index)
        if wide:
            return index, index + wide, " ".join(parts[index:index + wide])
        # 8858841901 — это id, даже если следом написано «навсегда» или «минут».
        if parts[index].isdigit() and len(parts[index]) >= 5:
            continue
        for span in (1, 2, 3):
            if index + span > count:
                continue
            candidate = " ".join(parts[index:index + span])
            if parse_duration(candidate):
                return index, index + span, candidate
    return None


def is_strong_user_token(token: str) -> bool:
    """@username, ссылка t.me или числовой id. Короткое «10» сюда не входит."""
    text = (token or "").strip()
    if not text:
        return False
    low = text.lower()
    if text.startswith("@") or low.startswith("https://t.me/") or low.startswith("t.me/"):
        return True
    return text.isdigit() and len(text) >= 5


def mention_id(token: str) -> Optional[str]:
    """@8858841901 и голое длинное число — это id, не username."""
    text = (token or "").strip()
    if text.lower().startswith("https://t.me/"):
        text = text.split("/", 3)[-1].split("/")[0]
    elif text.lower().startswith("t.me/"):
        text = text[5:].split("/")[0]
    if text.startswith("@"):
        text = text[1:]
    if text.isdigit() and len(text) >= 5:
        return text
    return None


_USER_URL = re.compile(r"^tg://user\?id=(\d{5,15})$", re.I)
_RESOLVE_URL = re.compile(r"^tg://resolve\?domain=([A-Za-z][A-Za-z0-9_]{3,31})(?:&.*)?$", re.I)
_PROFILE_URL = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t|telegram)\.me/@?([A-Za-z][A-Za-z0-9_]{3,31})/?(?:[?#].*)?$",
    re.I,
)


def handle_from_url(url: Any) -> str:
    """Ссылка на человека — «@id» или «@username». Пусто, если ссылка не на человека."""
    text = str(url or "").strip()
    by_id = _USER_URL.match(text)
    if by_id:
        return "@" + by_id.group(1)
    by_name = _RESOLVE_URL.match(text) or _PROFILE_URL.match(text)
    if by_name:
        return "@" + by_name.group(1)
    return ""


def _entity_kind(entity: Any) -> str:
    raw = getattr(entity, "type", "")
    return str(getattr(raw, "value", raw) or "")


def swap_people(text: str, entities: Iterable[Any] = ()) -> Tuple[str, Dict[int, Any]]:
    """Упоминания без @ превращаются в «@id», ссылки на профиль — в «@username».

    Человек без username упоминается по имени, и в тексте видно только имя.
    Telegram при этом знает, кто это: id лежит в entity. Позиции у Telegram
    в UTF-16, поэтому текст режется по ним, а не по символам Python.
    Возвращает новый текст и людей из упоминаний: {id: User}.
    """
    source = str(text or "")
    found = []
    for entity in entities or ():
        kind = _entity_kind(entity)
        handle = ""
        user = None
        if kind == "text_mention":
            user = getattr(entity, "user", None)
            try:
                uid = int(getattr(user, "id", 0) or 0)
            except (TypeError, ValueError):
                uid = 0
            if uid > 0:
                handle = f"@{uid}"
        elif kind == "text_link":
            handle = handle_from_url(getattr(entity, "url", ""))
        if not handle:
            continue
        try:
            start = int(getattr(entity, "offset", 0) or 0)
            end = start + int(getattr(entity, "length", 0) or 0)
        except (TypeError, ValueError):
            continue
        if end > start >= 0:
            found.append((start, end, handle, user))
    if not found:
        return source, {}

    data = source.encode("utf-16-le")
    size = len(data) // 2
    pieces = []
    people: Dict[int, Any] = {}
    at = 0
    for start, end, handle, user in sorted(found, key=lambda item: item[0]):
        if start < at or end > size:
            continue
        pieces.append(data[at * 2:start * 2].decode("utf-16-le", errors="ignore"))
        pieces.append(f" {handle} ")
        if user is not None:
            people[int(handle[1:])] = user
        at = end
    pieces.append(data[at * 2:].decode("utf-16-le", errors="ignore"))
    return "".join(pieces), people
