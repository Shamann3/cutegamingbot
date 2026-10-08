# -*- coding: utf-8 -*-
"""Разбор срока и нарушителя в любом порядке.

«мут навсегда @id причина» и «мут @id причина навсегда» — одна и та же команда.
Срок ищется по всей фразе, ссылка на человека тоже. Остальное — причина.
"""
from __future__ import annotations

import re
from typing import Callable, Optional, Sequence

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
