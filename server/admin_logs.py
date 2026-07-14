"""Admin: audit_events + system_logs (security / API errors)."""

from __future__ import annotations

import json
from typing import Any

from db import db
from error_codes import error_meaning, error_title, is_security_code
from config import ERROR_REPORT_ENABLED

AUDIT_EVENT_LABELS: dict[str, str] = {
    "shop_buy": "Покупка в магазине",
    "plot_buy": "Покупка грядки",
    "plot_clear": "Очистка грядки",
    "craft_success": "Крафт успех",
    "craft_fail": "Крафт провал",
    "market_buy": "Покупка на бирже",
    "market_sell": "Продажа на бирже",
    "admin_balance": "Admin: баланс",
    "admin_item": "Admin: предмет",
    "admin_ban": "Admin: бан",
    "admin_unban": "Admin: разбан",
    "admin_market_cancel": "Admin: снят лот",
    "admin_farm_reset": "Admin: сброс грядок",
    "admin_farm_global_reset": "Admin: глобальный сброс фермы",
    "admin_onboarding_reset": "Admin: сброс обучения",
    "market_list": "Выставление на биржу",
    "admin_bulk_grant": "Admin: массовая выдача",
    "admin_broadcast": "Admin: рассылка",
}

# Только сбои сервера (500, БД, необработанные исключения) — не 4xx и не шум клиента
REAL_ERROR_CATEGORY = "error"


def _parse_details(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _audit_row(row) -> dict:
    details = _parse_details(row["details"])
    event_type = row["event_type"]
    return {
        "id": int(row["id"]),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "userId": int(row["user_id"]),
        "eventType": event_type,
        "eventLabel": AUDIT_EVENT_LABELS.get(event_type, event_type),
        "amount": row["amount"],
        "balanceBefore": row["balance_before"],
        "balanceAfter": row["balance_after"],
        "details": details,
        "summary": _audit_summary(event_type, details, row["amount"]),
    }


def _audit_summary(event_type: str, details: dict, amount: int | None) -> str:
    if event_type == "shop_buy":
        name = details.get("name") or details.get("item_id") or "предмет"
        qty = details.get("quantity") or 1
        return f"{name} ×{qty}"
    if event_type == "plot_buy":
        plot_id = details.get("plot_id")
        return f"Грядка #{plot_id}" if plot_id else "Грядка"
    if event_type in ("market_buy", "market_sell"):
        name = details.get("name") or details.get("item_id") or "лот"
        qty = details.get("quantity") or 1
        return f"{name} ×{qty}"
    if event_type in ("craft_success", "craft_fail"):
        return details.get("result_name") or f"Рецепт #{details.get('recipe_id', '?')}"
    if event_type == "admin_balance":
        return details.get("note") or "Изменение баланса"
    if event_type == "admin_item":
        return details.get("item_name") or details.get("item_id") or "Предмет"
    if event_type == "admin_market_cancel":
        name = details.get("name") or details.get("item_id") or "лот"
        return f"Снят: {name}"
    if event_type == "market_list":
        name = details.get("name") or details.get("item_id") or "лот"
        qty = details.get("quantity") or 1
        price = details.get("price")
        if price is not None:
            return f"{name} ×{qty} · {price} КУТ/шт"
        return f"{name} ×{qty}"
    if event_type == "admin_bulk_grant":
        return details.get("note") or details.get("reason") or "Массовая выдача"
    if event_type in ("admin_farm_reset", "admin_farm_global_reset"):
        return details.get("note") or "Сброс грядок"
    if event_type in ("admin_ban", "admin_unban"):
        return details.get("reason") or details.get("note") or ""
    if amount not in (None, 0):
        sign = "+" if amount > 0 else ""
        return f"{sign}{amount} КУТ"
    return ""


def _system_log_row(row) -> dict:
    code = row["code"] or ""
    return {
        "id": int(row["id"]),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "category": row["category"],
        "code": code,
        "codeTitle": error_title(code) if code else "",
        "codeMeaning": error_meaning(code) if code else "",
        "security": is_security_code(code),
        "userId": int(row["user_id"]) if row["user_id"] is not None else None,
        "method": row["method"] or "",
        "path": row["path"] or "",
        "status": row["status"],
        "message": row["message"] or "",
        "source": row["source"] or "",
        "clientIp": row["client_ip"] or "",
        "details": _parse_details(row["details"]),
    }


async def get_logs_overview() -> dict:
    audit_total = int(await db.pool.fetchval("SELECT COUNT(*)::int FROM audit_events") or 0)
    audit_today = int(
        await db.pool.fetchval(
            """
            SELECT COUNT(*)::int FROM audit_events
            WHERE created_at >= date_trunc('day', NOW())
            """
        )
        or 0
    )
    security_total = int(
        await db.pool.fetchval(
            "SELECT COUNT(*)::int FROM system_logs WHERE category = 'security'"
        )
        or 0
    )
    security_today = int(
        await db.pool.fetchval(
            """
            SELECT COUNT(*)::int FROM system_logs
            WHERE category = 'security'
              AND created_at >= date_trunc('day', NOW())
            """
        )
        or 0
    )
    error_total = int(
        await db.pool.fetchval(
            "SELECT COUNT(*)::int FROM system_logs WHERE category = $1",
            REAL_ERROR_CATEGORY,
        )
        or 0
    )
    error_today = int(
        await db.pool.fetchval(
            """
            SELECT COUNT(*)::int FROM system_logs
            WHERE category = $1
              AND created_at >= date_trunc('day', NOW())
            """,
            REAL_ERROR_CATEGORY,
        )
        or 0
    )
    audit_types = await db.pool.fetch(
        """
        SELECT event_type, COUNT(*)::int AS cnt
        FROM audit_events
        GROUP BY event_type
        ORDER BY cnt DESC, event_type
        LIMIT 30
        """
    )
    error_codes = await db.pool.fetch(
        """
        SELECT code, COUNT(*)::int AS cnt
        FROM system_logs
        WHERE category IN ('security', 'error')
        GROUP BY code
        ORDER BY cnt DESC, code
        LIMIT 30
        """
    )
    return {
        "auditTotal": audit_total,
        "auditToday": audit_today,
        "securityTotal": security_total,
        "securityToday": security_today,
        "errorTotal": error_total,
        "errorToday": error_today,
        "telegramErrorsEnabled": ERROR_REPORT_ENABLED,
        "auditEventTypes": [
            {
                "value": r["event_type"],
                "label": AUDIT_EVENT_LABELS.get(r["event_type"], r["event_type"]),
                "count": int(r["cnt"]),
            }
            for r in audit_types
        ],
        "systemCodes": [
            {"value": r["code"], "label": error_title(r["code"]), "count": int(r["cnt"])}
            for r in error_codes
        ],
    }


async def list_audit_logs(
    *,
    user_id: int | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    conditions = ["1=1"]
    params: list[Any] = []
    idx = 1

    if user_id is not None and user_id > 0:
        conditions.append(f"user_id = ${idx}")
        params.append(user_id)
        idx += 1

    event_type_norm = (event_type or "").strip()
    if event_type_norm:
        conditions.append(f"event_type = ${idx}")
        params.append(event_type_norm)
        idx += 1

    where = " AND ".join(conditions)
    count_sql = f"SELECT COUNT(*)::int FROM audit_events WHERE {where}"
    total = int(await db.pool.fetchval(count_sql, *params) or 0)

    params.extend([limit, offset])
    rows = await db.pool.fetch(
        f"""
        SELECT id, created_at, user_id, event_type, amount, balance_before, balance_after, details
        FROM audit_events
        WHERE {where}
        ORDER BY created_at DESC, id DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )
    return {
        "total": total,
        "items": [_audit_row(r) for r in rows],
    }


def _transfer_row(row) -> dict:
    return {
        "id": int(row["id"]),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "senderId": int(row["sender_id"]),
        "receiverId": int(row["receiver_id"]),
        "amount": int(row["amount"]),
        "senderBalanceBefore": int(row["sender_balance_before"]),
        "senderBalanceAfter": int(row["sender_balance_after"]),
        "receiverBalanceBefore": int(row["receiver_balance_before"]),
        "receiverBalanceAfter": int(row["receiver_balance_after"]),
        "cause": row["cause"],
    }


async def list_p2p_transfers(
    *,
    sender_id: int | None = None,
    receiver_id: int | None = None,
    user_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Журнал переводов игрок->игрок ("дать"). user_id ищет по обеим сторонам сразу."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    conditions = ["1=1"]
    params: list[Any] = []
    idx = 1

    if user_id is not None and user_id > 0:
        conditions.append(f"(sender_id = ${idx} OR receiver_id = ${idx})")
        params.append(user_id)
        idx += 1
    else:
        if sender_id is not None and sender_id > 0:
            conditions.append(f"sender_id = ${idx}")
            params.append(sender_id)
            idx += 1
        if receiver_id is not None and receiver_id > 0:
            conditions.append(f"receiver_id = ${idx}")
            params.append(receiver_id)
            idx += 1

    if date_from:
        conditions.append(f"created_at >= ${idx}")
        params.append(date_from)
        idx += 1
    if date_to:
        conditions.append(f"created_at <= ${idx}")
        params.append(date_to)
        idx += 1

    where = " AND ".join(conditions)
    total = int(await db.pool.fetchval(f"SELECT COUNT(*)::int FROM p2p_transfers WHERE {where}", *params) or 0)

    params.extend([limit, offset])
    rows = await db.pool.fetch(
        f"""
        SELECT id, created_at, sender_id, receiver_id, amount,
               sender_balance_before, sender_balance_after,
               receiver_balance_before, receiver_balance_after, cause
        FROM p2p_transfers
        WHERE {where}
        ORDER BY created_at DESC, id DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )
    return {
        "total": total,
        "items": [_transfer_row(r) for r in rows],
    }


async def list_system_logs(
    *,
    category: str = "security",
    user_id: int | None = None,
    code: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    category_norm = (category or "security").strip().lower()
    if category_norm in ("errors", "error"):
        categories = (REAL_ERROR_CATEGORY,)
    elif category_norm == "security":
        categories = ("security",)
    else:
        categories = (category_norm,)

    conditions = [f"category = ANY(${1}::text[])"]
    params: list[Any] = [list(categories)]
    idx = 2

    if user_id is not None and user_id > 0:
        conditions.append(f"user_id = ${idx}")
        params.append(user_id)
        idx += 1

    code_norm = (code or "").strip()
    if code_norm:
        conditions.append(f"code = ${idx}")
        params.append(code_norm)
        idx += 1

    where = " AND ".join(conditions)
    total = int(await db.pool.fetchval(f"SELECT COUNT(*)::int FROM system_logs WHERE {where}", *params) or 0)

    params.extend([limit, offset])
    rows = await db.pool.fetch(
        f"""
        SELECT id, created_at, category, code, user_id, method, path, status,
               message, source, client_ip, details
        FROM system_logs
        WHERE {where}
        ORDER BY created_at DESC, id DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )
    return {
        "total": total,
        "items": [_system_log_row(r) for r in rows],
    }
