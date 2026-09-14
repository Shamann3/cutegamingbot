"""Сбор реальных фактов сотрудника для карточки игрока.

Лишние запросы — только если user_id есть в admin_accounts как активный staff.
Отсутствующие таблицы пропускаются молча.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from admin_permissions import ROLE_LABELS
from admin_portrait import (
    AdminPortraitFacts,
    assemble_staff_portrait_payload,
    is_project_staff,
    tenure_days_from,
)
from db import db
from panel_access import SECTION_BY_ID, SECTION_TABS, resolve_account_access

log = logging.getLogger("admin.staff_card")

_MOD_TYPES = ("ban", "unban", "mute", "unmute", "kick", "warn", "unwarn")
_AUDIT_ACTIONS = (
    "ban_user",
    "unban_user",
    "balance_change",
    "item_grant",
    "support_close",
)


def _human_access(
    sections: list[str],
    tabs: dict[str, list[str]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    section_labels: list[str] = []
    tab_labels: list[str] = []
    for sid in sections or []:
        sec = SECTION_BY_ID.get(sid)
        if not sec:
            continue
        section_labels.append(sec["label"])
        parent_label = sec["label"]
        for tid in tabs.get(sid) or []:
            meta = next((t for t in SECTION_TABS.get(sid, []) if t["id"] == tid), None)
            if meta:
                tab_labels.append(f"{parent_label} · {meta['label']}")
    return tuple(section_labels), tuple(tab_labels)


async def _safe_int(query: str, *args) -> int | None:
    try:
        val = await db.pool.fetchval(query, *args)
        return int(val or 0)
    except Exception:
        return None


async def _safe_map(query: str, key: str, *args) -> dict[str, int] | None:
    try:
        rows = await db.pool.fetch(query, *args)
    except Exception:
        return None
    out: dict[str, int] = {}
    for r in rows:
        out[str(r[key])] = int(r["cnt"] or 0)
    return out


async def _staff_row(user_id: int) -> Any | None:
    try:
        return await db.pool.fetchrow(
            """
            SELECT role, status, hired_at, registered_at
            FROM admin_accounts
            WHERE user_id = $1
            ORDER BY registered_at DESC NULLS LAST
            LIMIT 1
            """,
            user_id,
        )
    except Exception:
        log.exception("staff portrait: admin_accounts read failed")
        return None


async def load_staff_portrait(user_id: int) -> dict[str, Any] | None:
    """Полный портрет. None — обычный игрок, без лишнего payload."""
    row = await _staff_row(int(user_id))
    if not row:
        return None
    role = row["role"]
    status = row["status"]
    if not is_project_staff(role, status):
        return None

    sections: list[str] = []
    tabs: dict[str, list[str]] = {}
    try:
        _perms, sections, tabs = await resolve_account_access(role, int(user_id), status)
    except Exception:
        log.exception("staff portrait: panel access failed uid=%s", user_id)

    section_labels, tab_labels = _human_access(sections, tabs)

    type_ph = ", ".join(f"'{t}'" for t in _MOD_TYPES)
    action_ph = ", ".join(f"'{t}'" for t in _AUDIT_ACTIONS)

    tickets, replies, tt_comments, tt_videos, mod_map, audit_map = await asyncio.gather(
        _safe_int(
            "SELECT COUNT(*)::int FROM support_tickets "
            "WHERE assigned_admin_id = $1 AND status = 'closed'",
            user_id,
        ),
        _safe_int(
            "SELECT COUNT(*)::int FROM support_messages "
            "WHERE admin_user_id = $1 AND from_user = FALSE",
            user_id,
        ),
        _safe_map(
            """
            SELECT status, COUNT(*)::int AS cnt
            FROM tiktok_comment_cases
            WHERE reviewed_by = $1 AND status IN ('approved', 'rejected')
            GROUP BY status
            """,
            "status",
            user_id,
        ),
        _safe_map(
            """
            SELECT status, COUNT(*)::int AS cnt
            FROM tiktok_videos
            WHERE reviewed_by = $1 AND status IN ('approved', 'rejected')
            GROUP BY status
            """,
            "status",
            user_id,
        ),
        _safe_map(
            f"""
            SELECT action_type, COUNT(*)::int AS cnt
            FROM staff_actions
            WHERE admin_user_id = $1 AND action_type IN ({type_ph})
            GROUP BY action_type
            """,
            "action_type",
            user_id,
        ),
        _safe_map(
            f"""
            SELECT action, COUNT(*)::int AS cnt
            FROM admin_audit_log
            WHERE admin_user_id = $1 AND action IN ({action_ph})
            GROUP BY action
            """,
            "action",
            user_id,
        ),
    )

    tt_approved = None
    tt_rejected = None
    if tt_comments is not None or tt_videos is not None:
        tt_approved = int((tt_comments or {}).get("approved") or 0) + int(
            (tt_videos or {}).get("approved") or 0
        )
        tt_rejected = int((tt_comments or {}).get("rejected") or 0) + int(
            (tt_videos or {}).get("rejected") or 0
        )

    hired = row["hired_at"]
    facts = AdminPortraitFacts(
        user_id=int(user_id),
        role=role,
        role_label=ROLE_LABELS.get(role, role),
        section_labels=section_labels,
        tab_labels=tab_labels,
        tenure_days=tenure_days_from(hired, row["registered_at"]),
        hired_at=hired.isoformat() if hired else None,
        tickets_closed=tickets,
        replies=replies,
        tiktok_approved=tt_approved,
        tiktok_rejected=tt_rejected,
        bans=(mod_map or {}).get("ban") if mod_map is not None else None,
        unbans=(mod_map or {}).get("unban") if mod_map is not None else None,
        mutes=(mod_map or {}).get("mute") if mod_map is not None else None,
        warns=(mod_map or {}).get("warn") if mod_map is not None else None,
        kicks=(mod_map or {}).get("kick") if mod_map is not None else None,
        balance_adjusts=(audit_map or {}).get("balance_change") if audit_map is not None else None,
        item_grants=(audit_map or {}).get("item_grant") if audit_map is not None else None,
    )
    return assemble_staff_portrait_payload(role=role, status=status, facts=facts)
