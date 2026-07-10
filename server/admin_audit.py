"""Лог действий администраторов.

Пишет в `admin_audit_log` — отдельно от игровых `audit_events`.
Используется для аудита изменений настроек, банов, квестов, IP-банов и т.д.
"""

from __future__ import annotations

import json
from typing import Any

from db import db

# ---------------------------------------------------------------------------
# Human-readable action labels
# ---------------------------------------------------------------------------

_ACTION_LABELS: dict[str, str] = {
    "login": "🔑 Вход",
    "logout": "🚪 Выход",
    "force_reauth": "🔒 Сброс сессии",
    "ban_user": "🚫 Бан пользователя",
    "unban_user": "✅ Разбан пользователя",
    "balance_change": "💰 Изменение баланса",
    "item_grant": "📦 Выдача предмета",
    "settings_change": "⚙️ Изменение настроек",
    "quest_create": "📋 Создание квеста",
    "quest_update": "✏️ Изменение квеста",
    "quest_delete": "🗑 Удаление квеста",
    "dex_item_create": "📦 Создание DEX-предмета",
    "dex_item_update": "✏️ Изменение DEX-предмета",
    "dex_item_delete": "🗑 Удаление DEX-предмета",
    "ip_ban_add": "🚫 Дать IP-бан",
    "ip_ban_remove": "✅ Снятие IP-бана",
    "broadcast_schedule": "📢 Планирование рассылки",
    "broadcast_cancel": "❌ Отмена рассылки",
    "maintenance_toggle": "🔧 Переключение обслуживания",
    "support_claim":  "💬 Взял тикет поддержки",
    "support_close":  "🔒 Закрыл тикет поддержки",
    "rules_accept":   "📜 Принял правила",
}


def action_label(action: str) -> str:
    return _ACTION_LABELS.get(action, action)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

async def log_admin_action(
    admin_user_id: int,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    target_label: str | None = None,
    details: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    try:
        await db.pool.execute(
            """
            INSERT INTO admin_audit_log
                (admin_user_id, action, target_type, target_id, target_label, details, ip)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
            """,
            admin_user_id,
            action,
            target_type,
            str(target_id) if target_id is not None else None,
            target_label,
            json.dumps(details or {}, ensure_ascii=False),
            ip,
        )
    except Exception:
        pass  # Never let audit logging break the main operation


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

async def list_admin_audit(
    *,
    admin_user_id: int | None = None,
    action: str | None = None,
    target_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit = max(1, min(100, limit))
    offset = max(0, offset)

    conditions = []
    params: list[Any] = []

    if admin_user_id is not None:
        params.append(admin_user_id)
        conditions.append(f"admin_user_id = ${len(params)}")
    if action:
        params.append(action)
        conditions.append(f"action = ${len(params)}")
    if target_type:
        params.append(target_type)
        conditions.append(f"target_type = ${len(params)}")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = int(
        await db.pool.fetchval(
            f"SELECT COUNT(*)::int FROM admin_audit_log {where}", *params
        ) or 0
    )

    params.extend([limit, offset])
    rows = await db.pool.fetch(
        f"""
        SELECT id, admin_user_id, action, target_type, target_id, target_label,
               details, ip, created_at
        FROM admin_audit_log
        {where}
        ORDER BY created_at DESC
        LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """,
        *params,
    )

    return {
        "items": [
            {
                "id": int(r["id"]),
                "adminUserId": int(r["admin_user_id"]),
                "action": r["action"],
                "actionLabel": action_label(r["action"]),
                "targetType": r["target_type"],
                "targetId": r["target_id"],
                "targetLabel": r["target_label"],
                "details": r["details"] or {},
                "ip": r["ip"],
                "createdAt": r["created_at"].isoformat(),
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def list_admin_action_types() -> list[str]:
    rows = await db.pool.fetch(
        "SELECT DISTINCT action FROM admin_audit_log ORDER BY action"
    )
    return [r["action"] for r in rows]
