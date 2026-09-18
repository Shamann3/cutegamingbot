# -*- coding: utf-8 -*-
"""Инциденты Ники: только то, что автоматика уже не смогла починить.

Обычная жизнь системы (кулдаун, мёртвая зона, суточный потолок) сюда
не пишется. Карточка появляется, когда столу нечем доливать или перевод
застрял так, что нужен человек с кнопкой.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

CODE_EMPTY_LADDER = "empty_ladder"
CODE_REFUND_STUCK = "refund_stuck"
CODE_TRANSFER_BROKEN = "transfer_broken"

COMMAND_KINDS = (
    "force_tick",
    "force_topup",
    "force_sweep",
    "retry_heal",
    "revert",
    "pause_group",
    "pause_all",
    "enable_group",
    "enable_all",
)

MONEY_COMMANDS = frozenset({"force_tick", "force_topup", "force_sweep", "retry_heal", "revert"})
SWITCH_COMMANDS = frozenset({"pause_group", "pause_all", "enable_group", "enable_all"})

SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"


def actions_for(code: str) -> List[Dict[str, str]]:
    if code == CODE_EMPTY_LADDER:
        return [
            {
                "id": "force_tick",
                "label": "Проверить снова",
                "hint": "Ника ещё раз посмотрит техгруппы и попробует долить сама.",
            },
            {
                "id": "force_topup",
                "label": "Долить из того, что есть",
                "hint": "Один осторожный шаг по лестнице. Если везде ноль — ничего не спишет.",
            },
            {
                "id": "pause_group",
                "label": "Пауза этой группы",
                "hint": "Автодолив этой группы останавливается, остальные не трогаем.",
            },
            {
                "id": "pause_all",
                "label": "Выключить всю Нику",
                "hint": "Аварийный стоп. Куты больше не двигаются, пока не включишь.",
            },
        ]
    if code == CODE_REFUND_STUCK:
        return [
            {
                "id": "retry_heal",
                "label": "Вернуть куты источнику",
                "hint": "Повторить откат застрявшего перевода. Не создаёт новые куты.",
            },
            {
                "id": "force_tick",
                "label": "Проверить снова",
                "hint": "Ещё один проход самолечения.",
            },
        ]
    if code == CODE_TRANSFER_BROKEN:
        return [
            {
                "id": "revert",
                "label": "Вернуть этот перевод",
                "hint": "Куты едут обратно: получатель → источник, одной транзакцией.",
            },
            {
                "id": "retry_heal",
                "label": "Вернуть куты источнику",
                "hint": "Повторить откат. Новых кут не создаёт.",
            },
            {
                "id": "pause_all",
                "label": "Выключить всю Нику",
                "hint": "Аварийный стоп, пока разбираешь перевод.",
            },
        ]
    return [
        {
            "id": "force_tick",
            "label": "Проверить снова",
            "hint": "Ника повторит диагностику.",
        }
    ]


def fingerprint_empty_ladder(chat_id: int) -> str:
    return f"empty_ladder:{int(chat_id)}"


def fingerprint_refund(log_id: int) -> str:
    return f"refund_stuck:{int(log_id)}"


def fingerprint_transfer(log_id: int) -> str:
    return f"transfer_broken:{int(log_id)}"


async def raise_incident(
    conn,
    *,
    code: str,
    fingerprint: str,
    title: str,
    body: str,
    chat_id: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    severity: str = SEVERITY_CRITICAL,
) -> Optional[int]:
    actions = actions_for(code)
    payload = payload or {}
    existing = await conn.fetchrow(
        """
        SELECT id FROM nika_incidents
        WHERE fingerprint = $1 AND status = 'open'
        LIMIT 1
        """,
        fingerprint,
    )
    if existing:
        await conn.execute(
            """
            UPDATE nika_incidents
            SET title = $2,
                body = $3,
                payload = $4::jsonb,
                actions = $5::jsonb,
                occurrence_count = occurrence_count + 1,
                updated_at = NOW()
            WHERE id = $1
            """,
            int(existing["id"]),
            title[:240],
            body[:4000],
            json.dumps(payload, ensure_ascii=False),
            json.dumps(actions, ensure_ascii=False),
        )
        return int(existing["id"])
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO nika_incidents (
                fingerprint, code, severity, title, body, chat_id, payload, actions
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)
            RETURNING id
            """,
            fingerprint,
            code,
            severity,
            title[:240],
            body[:4000],
            int(chat_id) if chat_id is not None else None,
            json.dumps(payload, ensure_ascii=False),
            json.dumps(actions, ensure_ascii=False),
        )
        return int(row["id"]) if row else None
    except Exception as exc:
        name = type(exc).__name__
        if "UniqueViolation" not in name and "unique" not in str(exc).lower():
            raise
        existing = await conn.fetchrow(
            """
            SELECT id FROM nika_incidents
            WHERE fingerprint = $1 AND status = 'open'
            LIMIT 1
            """,
            fingerprint,
        )
        if not existing:
            return None
        await conn.execute(
            """
            UPDATE nika_incidents
            SET title = $2,
                body = $3,
                payload = $4::jsonb,
                actions = $5::jsonb,
                occurrence_count = occurrence_count + 1,
                updated_at = NOW()
            WHERE id = $1
            """,
            int(existing["id"]),
            title[:240],
            body[:4000],
            json.dumps(payload, ensure_ascii=False),
            json.dumps(actions, ensure_ascii=False),
        )
        return int(existing["id"])


async def resolve_fingerprint(conn, fingerprint: str, *, note: str = "", by: Optional[int] = None) -> bool:
    row = await conn.fetchrow(
        """
        UPDATE nika_incidents
        SET status = 'resolved',
            resolved_at = NOW(),
            resolved_by = $2,
            resolve_note = $3,
            updated_at = NOW()
        WHERE fingerprint = $1 AND status = 'open'
        RETURNING id
        """,
        fingerprint,
        by,
        (note or "")[:500],
    )
    return row is not None


async def resolve_id(conn, incident_id: int, *, note: str = "", by: Optional[int] = None) -> bool:
    row = await conn.fetchrow(
        """
        UPDATE nika_incidents
        SET status = 'resolved',
            resolved_at = NOW(),
            resolved_by = $2,
            resolve_note = $3,
            updated_at = NOW()
        WHERE id = $1 AND status <> 'resolved'
        RETURNING id
        """,
        int(incident_id),
        by,
        (note or "")[:500],
    )
    return row is not None


async def count_open_critical(conn) -> int:
    value = await conn.fetchval(
        """
        SELECT COUNT(*)::int
        FROM nika_incidents
        WHERE status = 'open' AND severity = 'critical'
        """
    )
    return int(value or 0)


async def list_open(conn, *, limit: int = 40) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT *
        FROM nika_incidents
        WHERE status = 'open'
        ORDER BY
            CASE severity WHEN 'critical' THEN 0 ELSE 1 END,
            updated_at DESC
        LIMIT $1
        """,
        int(max(1, min(100, limit))),
    )
    return [dict(row) for row in rows]


async def list_recent(conn, *, limit: int = 40) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT *
        FROM nika_incidents
        ORDER BY
            CASE status WHEN 'open' THEN 0 WHEN 'ack' THEN 1 ELSE 2 END,
            CASE severity WHEN 'critical' THEN 0 ELSE 1 END,
            updated_at DESC
        LIMIT $1
        """,
        int(max(1, min(100, limit))),
    )
    return [dict(row) for row in rows]


async def ack_id(conn, incident_id: int, *, by: Optional[int] = None) -> bool:
    row = await conn.fetchrow(
        """
        UPDATE nika_incidents
        SET status = 'ack',
            updated_at = NOW(),
            resolved_by = COALESCE($2, resolved_by)
        WHERE id = $1 AND status = 'open'
        RETURNING id
        """,
        int(incident_id),
        by,
    )
    return row is not None


async def fetch_by_id(conn, incident_id: int) -> Optional[Dict[str, Any]]:
    row = await conn.fetchrow(
        "SELECT * FROM nika_incidents WHERE id = $1",
        int(incident_id),
    )
    return dict(row) if row else None


async def enqueue_command(conn, kind: str, payload: Dict[str, Any], requested_by: int) -> int:
    kind = str(kind or "").strip()
    if kind not in COMMAND_KINDS:
        raise ValueError(f"unknown_command:{kind}")
    row = await conn.fetchrow(
        """
        INSERT INTO nika_operator_commands (kind, payload, requested_by)
        VALUES ($1, $2::jsonb, $3)
        RETURNING id
        """,
        str(kind),
        json.dumps(payload or {}, ensure_ascii=False),
        int(requested_by),
    )
    return int(row["id"])
