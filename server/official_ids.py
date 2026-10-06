"""Какие чаты считаются официальными группами проекта.

Жёсткий список в настройках мута остаётся. Группы, отмеченные в панели,
добавляются к нему. Личные чаты и исключённые группы не входят.
"""
from __future__ import annotations


def merged_official_ids(hardcoded, live, excluded=()) -> list[int]:
    skip = set()
    for raw in excluded or ():
        try:
            skip.add(int(raw))
        except (TypeError, ValueError):
            continue
    out: list[int] = []
    seen: set[int] = set()
    for raw in list(hardcoded or ()) + list(live or ()):
        try:
            cid = int(raw)
        except (TypeError, ValueError):
            continue
        if cid >= 0 or cid in skip or cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def chat_is_official(chat_id, *, hardcoded, live, excluded=()) -> bool:
    try:
        cid = int(chat_id)
    except (TypeError, ValueError):
        return False
    return cid in set(merged_official_ids(hardcoded, live, excluded))
