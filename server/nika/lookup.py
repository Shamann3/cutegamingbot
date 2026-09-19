# -*- coding: utf-8 -*-
"""Разбор ссылки / @username / имени / id группы для постановки под Нику."""

from __future__ import annotations

import re
from typing import Any, Dict, List

_TME_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.me|telegram\.dog)/+",
    re.I,
)
_C_LINK = re.compile(r"^c/(\d{5,20})(?:/\d+)*$", re.I)
_INVITE = re.compile(r"^(?:joinchat/|\+)[A-Za-z0-9_-]+$", re.I)
_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def normalize_group_query(raw: str) -> str:
    q = str(raw or "").strip()
    q = _TME_RE.sub("", q)
    q = q.strip().lstrip("@").strip().strip("/")
    if "?" in q:
        q = q.split("?", 1)[0]
    if "#" in q:
        q = q.split("#", 1)[0]
    return q.strip()


def parse_group_ref(raw: str) -> Dict[str, Any]:
    """Один ввод: id, t.me/c/…, @username, ссылка или имя."""
    q = normalize_group_query(raw)
    if not q:
        return {"kind": "empty", "query": ""}
    if _INVITE.match(q):
        return {"kind": "invite", "query": q}
    c_link = _C_LINK.match(q)
    if c_link:
        return {"kind": "id", "chat_id": int(f"-100{c_link.group(1)}"), "query": q}
    compact = q.replace(" ", "")
    if compact.lstrip("-").isdigit():
        return {"kind": "id", "chat_id": int(compact), "query": compact}
    if _USERNAME.match(q):
        return {"kind": "username", "username": q, "query": q}
    return {"kind": "name", "name": q, "query": q}


def _username_of(hit: Dict[str, Any]) -> str:
    return str(hit.get("username") or "").lstrip("@").lower()


def pick_resolved_hit(hits: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """Один точный матч ставим сразу. Несколько — отдаём список."""
    ref = parse_group_ref(query)
    if ref["kind"] == "empty":
        return {
            "ok": False,
            "error": "Нужны id, @username или имя группы.",
            "candidates": [],
        }
    if ref["kind"] == "invite":
        return {
            "ok": False,
            "error": "Это приглашение. Введи @username, имя или id группы.",
            "candidates": [],
        }

    usable = [h for h in hits if not h.get("forbidden")]
    q = str(ref.get("query") or "").lower()

    exact_user = [h for h in usable if _username_of(h) == q]
    if len(exact_user) == 1:
        hit = exact_user[0]
        return {"ok": True, "chatId": int(hit["chatId"]), "match": hit, "candidates": exact_user}

    if ref["kind"] == "id" and ref.get("chat_id") is not None:
        wanted = int(ref["chat_id"])
        by_id = [h for h in usable if int(h.get("chatId") or 0) == wanted]
        if len(by_id) == 1:
            hit = by_id[0]
            return {"ok": True, "chatId": wanted, "match": hit, "candidates": by_id}

    exact_name = [h for h in usable if str(h.get("name") or "").lower() == q]
    if len(exact_name) == 1:
        hit = exact_name[0]
        return {"ok": True, "chatId": int(hit["chatId"]), "match": hit, "candidates": exact_name}

    if len(usable) == 1:
        hit = usable[0]
        return {"ok": True, "chatId": int(hit["chatId"]), "match": hit, "candidates": usable}

    if not usable:
        return {
            "ok": False,
            "error": "Группа не найдена. Введи id, @username или имя так, как она записана в боте.",
            "candidates": [],
        }
    return {
        "ok": False,
        "error": "Нашлось несколько групп. Нажми нужную — и сразу поставим.",
        "candidates": usable,
    }
