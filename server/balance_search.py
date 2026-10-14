# -*- coding: utf-8 -*-
"""Поиск человека и раздельные куты: личные и на балансах групп."""
from __future__ import annotations


def escape_like(text: str) -> str:
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def contains_pattern(text: str) -> str:
    return f"%{escape_like(text)}%"


def prefix_pattern(text: str) -> str:
    return f"{escape_like(text)}%"


def plain_query(raw: str) -> str:
    return str(raw or "").strip().lstrip("@").strip()


def query_user_id(text: str) -> int | None:
    plain = plain_query(text)
    if not plain.isdigit() or len(plain) > 18:
        return None
    return int(plain)


def whole(value) -> int:
    try:
        number = int(float(value or 0))
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def has_group_cute(chat, dex=0) -> bool:
    return whole(chat) >= 1 or whole(dex) >= 1


def money_card(balance, groups) -> dict:
    """Личные куты и куты каждой группы — двумя разными числами."""
    rows = []
    seen = set()
    for group in groups or []:
        chat_id = group.get("chatId")
        if chat_id in seen:
            continue
        chat = whole(group.get("chat"))
        dex = whole(group.get("dex"))
        if chat < 1 and dex < 1:
            continue
        seen.add(chat_id)
        rows.append({
            "chatId": int(chat_id),
            "name": group.get("name") or f"группа {chat_id}",
            "username": group.get("username") or "",
            "chat": chat,
            "dex": dex,
            "technical": bool(group.get("technical")),
            "creator": bool(group.get("creator")),
        })
    rows.sort(key=lambda row: (-row["chat"], -row["dex"], row["chatId"]))
    return {
        "personal": whole(balance),
        "groupsChat": sum(row["chat"] for row in rows),
        "groupsDex": sum(row["dex"] for row in rows),
        "groups": rows,
    }
