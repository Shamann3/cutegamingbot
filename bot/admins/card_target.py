# -*- coding: utf-8 -*-
"""Кого наказывать, если сотрудник ответил на сообщение бота.

Карточка одного человека (профиль, «кто ты», наказание) отдаёт его id.
Статистика, топ и список из нескольких людей цель не назначают: бот сам
нарушителем не становится.
"""
from __future__ import annotations

import re
from typing import Any, Optional


_ID_RE = re.compile(r"(?<![\d-])(\d{5,16})(?!\d)")
_HTML_ID_RE = re.compile(
    r"tg://user\?id=(\d{5,16})|<code>(\d{5,16})</code>",
    re.IGNORECASE,
)
_TG_USER_RE = re.compile(r"(?:tg://user\?id=)(\d{5,16})", re.IGNORECASE)
_STAT_RE = re.compile(
    r"статистик|рейтинг|лидерборд|царь\s+статистик|"
    r"топ\s+(?:чат|игр|сообщ|пользоват|день|недел|месяц)|"
    r"место\s+в\s+топе|несколько\s+человек|зашли\s+сейчас",
    re.IGNORECASE,
)
_RANK_RE = re.compile(r"^\s*\d{1,3}[\.\)]\s+\S")
_MISS_RE = re.compile(r"не\s+наш[её]л|не\s+найден", re.IGNORECASE)


class CardPerson:
    """Человек, которого карточка назвала нарушителем. Не бот."""

    def __init__(self, user_id: int, name: str = "", username: str = ""):
        self.id = int(user_id)
        self.first_name = (name or str(self.id))[:128]
        self.last_name = None
        self.full_name = self.first_name
        self.username = username or None
        self.is_bot = False


def _fold(text: str) -> str:
    return " ".join(str(text or "").casefold().replace("ё", "е").split())


def _utf16_slice(text: str, offset: int, length: int) -> str:
    raw = str(text or "").encode("utf-16-le")
    start = max(0, int(offset)) * 2
    end = max(start, int(offset) + int(length)) * 2
    return raw[start:end].decode("utf-16-le", errors="ignore")


def _line_index(text: str, utf16_offset: int) -> int:
    return _utf16_slice(text, 0, int(utf16_offset)).count("\n")


def _entity_type(entity: Any) -> str:
    kind = getattr(entity, "type", "")
    return str(getattr(kind, "value", kind) or "")


def _plain_ids(fragment: str) -> set[int]:
    found = {int(item) for item in _ID_RE.findall(fragment or "")}
    for left, right in _HTML_ID_RE.findall(fragment or ""):
        found.add(int(left or right))
    return found


def _entity_hits(text: str, entities) -> list[tuple[int, int, bool]]:
    """(номер строки, id, это бот). Смещение Telegram считается в UTF-16."""
    hits = []
    for entity in entities or ():
        try:
            offset = int(getattr(entity, "offset", 0) or 0)
            length = int(getattr(entity, "length", 0) or 0)
        except (TypeError, ValueError):
            continue
        line = _line_index(text, offset)
        kind = _entity_type(entity)
        if kind == "text_mention":
            user = getattr(entity, "user", None)
            try:
                uid = int(getattr(user, "id", 0) or 0)
            except (TypeError, ValueError):
                continue
            if uid > 0:
                hits.append((line, uid, bool(getattr(user, "is_bot", False))))
            continue
        if kind == "text_link":
            match = _TG_USER_RE.search(str(getattr(entity, "url", "") or ""))
            if match:
                hits.append((line, int(match.group(1)), False))
            continue
        if kind == "code":
            fragment = _utf16_slice(text, offset, length).strip()
            if fragment.isdigit() and 5 <= len(fragment) <= 16:
                hits.append((line, int(fragment), False))
    return hits


def _is_list(text: str, ids: set[int]) -> bool:
    folded = _fold(text)
    if _STAT_RE.search(folded):
        return True
    if _MISS_RE.search(folded) and "нарушител" not in folded:
        return True
    ranked = sum(1 for line in str(text or "").splitlines() if _RANK_RE.match(line))
    if ranked >= 3:
        return True
    return len(ids) >= 3


def offender_from_card(text: str, entities=()) -> Optional[int]:
    """Один нарушитель в сообщении бота. None — список, статистика или никого."""
    body = str(text or "")
    if not body.strip():
        return None
    lines = body.splitlines() or [body]
    hits = _entity_hits(body, entities)

    def ids_on(index: int) -> set[int]:
        found = _plain_ids(lines[index])
        for line, uid, is_bot in hits:
            if line == index and not is_bot:
                found.add(int(uid))
        return found

    for index, line in enumerate(lines):
        if "нарушител" not in _fold(line):
            continue
        found = ids_on(index)
        if len(found) == 1:
            return next(iter(found))
        if len(found) > 1:
            return None

    marked = set()
    for line, uid, is_bot in hits:
        if not is_bot:
            marked.add(int(uid))
    if not marked:
        folded = _fold(body)
        for line in lines:
            if "🆔" in line:
                marked.update(_plain_ids(line))
        if not marked and "профил" in folded:
            marked.update(_plain_ids(body))
    if _is_list(body, marked):
        return None
    if len(marked) == 1:
        return next(iter(marked))
    return None


def _service_person(message: Any):
    """Кто зашёл или вышел. Добавивший его в группу целью не становится."""
    members = getattr(message, "new_chat_members", None)
    if members:
        from bot.funcs.who_lookup import join_people

        people = join_people(members)
        if len(people) != 1:
            return None
        person = people[0]
        return CardPerson(person.user_id, person.full_name or person.first_name, person.username)
    left = getattr(message, "left_chat_member", None)
    if left is None or bool(getattr(left, "is_bot", False)):
        return None
    from bot.funcs.who_lookup import TgPerson

    person = TgPerson.from_user(left)
    if person is None or person.is_bot:
        return None
    return CardPerson(person.user_id, person.full_name or person.first_name, person.username)


def reply_target_user(message: Any):
    """На кого отвечает команда.

    Человек — он сам. «Зашёл в группу» — тот, кто зашёл, а не кто его добавил.
    Сообщение бота — нарушитель из карточки.
    Статистика и сообщение без одного id никого не назначают.
    """
    if message is None:
        return None
    if getattr(message, "new_chat_members", None) or getattr(message, "left_chat_member", None):
        return _service_person(message)
    author = getattr(message, "from_user", None)
    if author is None:
        return None
    if not bool(getattr(author, "is_bot", False)):
        return author
    text = getattr(message, "text", None) or ""
    entities = getattr(message, "entities", None) or ()
    if not text:
        text = getattr(message, "caption", None) or ""
        entities = getattr(message, "caption_entities", None) or ()
    user_id = offender_from_card(text, entities)
    if not user_id:
        return None
    return CardPerson(user_id)
