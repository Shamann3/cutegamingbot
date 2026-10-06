# -*- coding: utf-8 -*-
"""Кого записать в users, когда человека ещё нет в базе Кута.

Чистые правила. Сеть и база живут в наказаниях и в панели.
«Кто ты» этими правилами не пользуется: отсутствующий человек там
просто не найден в боте.
"""
from __future__ import annotations

import re
from typing import Any, Optional

_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")

# Новая строка получает имя и username. Баланс и дата регистрации
# в UPDATE не входят: у уже играющего человека их нельзя затирать.
ADOPT_USER_SQL = """
INSERT INTO users (user_id, first_name, username)
VALUES ($1, $2, $3)
ON CONFLICT (user_id) DO UPDATE
SET first_name = CASE
      WHEN (
        users.first_name IS NULL
        OR btrim(users.first_name) = ''
        OR users.first_name = users.user_id::text
      )
      AND EXCLUDED.first_name IS NOT NULL
      AND btrim(EXCLUDED.first_name) <> ''
      AND EXCLUDED.first_name <> EXCLUDED.user_id::text
      THEN EXCLUDED.first_name
      ELSE users.first_name
    END,
    username = CASE
      WHEN EXCLUDED.username IS NOT NULL
        AND btrim(EXCLUDED.username) <> ''
        AND (users.username IS NULL OR btrim(users.username) = '')
      THEN EXCLUDED.username
      ELSE users.username
    END
"""


def normalize_username(value: Any) -> str:
    text = str(value or "").strip()
    if "t.me/" in text.lower():
        text = text.split("/")[-1]
    text = text.split("?")[0].strip().lstrip("@")
    if not _USERNAME.match(text):
        return ""
    return text


def name_is_placeholder(name: Any, user_id: int) -> bool:
    text = " ".join(str(name or "").split())
    if not text:
        return True
    try:
        return text == str(int(user_id))
    except (TypeError, ValueError):
        return False


def needs_telegram_profile(in_database: bool, first_name: Any, user_id: int) -> bool:
    """Telegram нужен только если в Куте нет живого имени."""
    if not in_database:
        return True
    return name_is_placeholder(first_name, user_id)


def person_from_user_fields(
    user_id: Any,
    first_name: Any,
    last_name: Any,
    username: Any,
    *,
    is_bot: bool = False,
) -> Optional[dict]:
    if is_bot:
        return None
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    if uid <= 0:
        return None
    first = " ".join(str(first_name or "").split())
    last = " ".join(str(last_name or "").split())
    name = " ".join(part for part in (first, last) if part).strip()
    if not name:
        name = str(uid)
    if len(name) > 128:
        name = name[:128].rstrip()
    uname = normalize_username(username)
    return {"user_id": uid, "first_name": name, "username": uname or None}


def person_from_telegram_chat(payload: Any) -> Optional[dict]:
    """Ответ getChat. Группа и канал человеком не становятся."""
    if not isinstance(payload, dict):
        return None
    if str(payload.get("type") or "") != "private":
        return None
    return person_from_user_fields(
        payload.get("id"),
        payload.get("first_name"),
        payload.get("last_name"),
        payload.get("username"),
        is_bot=bool(payload.get("is_bot")),
    )


def person_from_chat_member(payload: Any) -> Optional[dict]:
    if not isinstance(payload, dict):
        return None
    user = payload.get("user")
    if not isinstance(user, dict):
        return None
    return person_from_user_fields(
        user.get("id"),
        user.get("first_name"),
        user.get("last_name"),
        user.get("username"),
        is_bot=bool(user.get("is_bot")),
    )
