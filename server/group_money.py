# -*- coding: utf-8 -*-
"""Список групп с кутами: от самой богатой до 1 куты на бч."""
from __future__ import annotations

from balance_search import whole


def page_bounds(offset, limit, *, page_size: int = 40) -> tuple[int, int]:
    try:
        start = int(0 if offset is None else offset)
    except (TypeError, ValueError):
        start = 0
    if start < 0:
        start = 0
    if limit is None:
        size = page_size
    else:
        try:
            size = int(limit)
        except (TypeError, ValueError):
            size = page_size
    if size < 1:
        size = 1
    if size > 80:
        size = 80
    return start, size


def shape_totals(row: dict | None, people) -> dict:
    data = row or {}
    people_count = None
    if people is not None:
        try:
            people_count = max(0, int(people or 0))
        except (TypeError, ValueError):
            people_count = 0
    try:
        groups = max(0, int(data.get("groups_with_cute") or 0))
    except (TypeError, ValueError):
        groups = 0
    return {
        "allChat": whole(data.get("all_chat")),
        "livingChat": whole(data.get("living_chat")),
        "technicalChat": whole(data.get("technical_chat")),
        "allDex": whole(data.get("all_dex")),
        "groupsWithCute": groups,
        "peopleWithCute": people_count,
    }


def shape_group(row: dict, rank: int) -> dict:
    chat_id = int(row.get("chat_id"))
    return {
        "rank": int(rank),
        "chatId": chat_id,
        "name": row.get("name") or f"группа {chat_id}",
        "username": row.get("username") or "",
        "link": row.get("link") or "",
        "chat": whole(row.get("chat")),
        "dex": whole(row.get("dex")),
        "technical": bool(row.get("technical")),
        "level": max(0, min(5, int(row.get("level") or 0))),
    }
