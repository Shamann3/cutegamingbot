"""DB-функции для системы поддержки (тикеты + сообщения)."""

from __future__ import annotations

import logging

from db import db

logger = logging.getLogger("cute-farm.support-db")

_DDL = [
    """CREATE TABLE IF NOT EXISTS support_tickets (
        id          SERIAL PRIMARY KEY,
        user_id     BIGINT NOT NULL,
        username    TEXT,
        first_name  TEXT,
        subject     TEXT NOT NULL DEFAULT '',
        status      VARCHAR(20) NOT NULL DEFAULT 'open',
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_uid ON support_tickets (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets (status, updated_at DESC)",
    # Миграции — безопасно добавляют колонки в уже существующую таблицу
    "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS subject TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS assigned_admin_id BIGINT",
    "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS assigned_admin_name TEXT",
    """CREATE TABLE IF NOT EXISTS support_messages (
        id            SERIAL PRIMARY KEY,
        ticket_id     INT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
        from_user     BOOLEAN NOT NULL,
        admin_user_id BIGINT,
        admin_name    TEXT,
        text          TEXT NOT NULL,
        photo_file_id TEXT,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        read_at       TIMESTAMPTZ
    )""",
    "CREATE INDEX IF NOT EXISTS idx_support_messages_tid ON support_messages (ticket_id, created_at)",
    "ALTER TABLE support_messages ADD COLUMN IF NOT EXISTS photo_file_id TEXT",
]


async def ensure_tables() -> None:
    """Создаёт таблицы если их нет. Вызывается из lifespan app.py."""
    async with db.pool.acquire() as conn:
        for stmt in _DDL:
            await conn.execute(stmt)
    logger.info("Support tables OK")


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

async def get_or_create_ticket(
    user_id: int,
    username: str | None,
    first_name: str | None,
    subject: str | None = None,
) -> int:
    """Всегда создаёт новый тикет (subject задан при создании через бот)."""
    return int(await db.pool.fetchval(
        """
        INSERT INTO support_tickets (user_id, username, first_name, subject)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        user_id, username, first_name, subject or "",
    ))


async def list_tickets(status: str = "open", limit: int = 60) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT t.id, t.user_id, t.username, t.first_name, t.subject, t.status,
               t.assigned_admin_id, t.assigned_admin_name,
               t.created_at, t.updated_at,
               (SELECT text FROM support_messages
                WHERE ticket_id = t.id ORDER BY created_at DESC LIMIT 1) AS last_text,
               (SELECT from_user FROM support_messages
                WHERE ticket_id = t.id ORDER BY created_at DESC LIMIT 1) AS last_from_user,
               (SELECT COUNT(*) FROM support_messages
                WHERE ticket_id = t.id AND from_user = TRUE AND read_at IS NULL) AS unread
        FROM support_tickets t
        WHERE ($1 = 'all' OR t.status = $1)
        ORDER BY t.updated_at DESC
        LIMIT $2
        """,
        status, limit,
    )
    return [dict(r) for r in rows]


async def get_ticket(ticket_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        "SELECT * FROM support_tickets WHERE id = $1",
        ticket_id,
    )
    return dict(row) if row else None


async def claim_ticket(ticket_id: int, admin_user_id: int, admin_name: str) -> bool:
    """Берёт тикет в работу. Возвращает True если успешно."""
    result = await db.pool.execute(
        """UPDATE support_tickets
           SET assigned_admin_id = $2, assigned_admin_name = $3, updated_at = NOW()
           WHERE id = $1 AND status = 'open'""",
        ticket_id, admin_user_id, admin_name,
    )
    return result == "UPDATE 1"


async def close_ticket(ticket_id: int) -> None:
    await db.pool.execute(
        "UPDATE support_tickets SET status = 'closed', updated_at = NOW() WHERE id = $1",
        ticket_id,
    )


async def count_open_tickets() -> int:
    return int(await db.pool.fetchval(
        "SELECT COUNT(*) FROM support_tickets WHERE status = 'open'"
    ) or 0)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

async def add_user_message(ticket_id: int, text: str, photo_file_id: str | None = None) -> int:
    msg_id = await db.pool.fetchval(
        """
        INSERT INTO support_messages (ticket_id, from_user, text, photo_file_id)
        VALUES ($1, TRUE, $2, $3)
        RETURNING id
        """,
        ticket_id, text, photo_file_id,
    )
    await db.pool.execute(
        "UPDATE support_tickets SET updated_at = NOW() WHERE id = $1",
        ticket_id,
    )
    return int(msg_id)


async def add_admin_message(
    ticket_id: int, admin_user_id: int, admin_name: str,
    text: str, photo_file_id: str | None = None,
) -> int:
    msg_id = await db.pool.fetchval(
        """
        INSERT INTO support_messages
            (ticket_id, from_user, admin_user_id, admin_name, text, photo_file_id)
        VALUES ($1, FALSE, $2, $3, $4, $5)
        RETURNING id
        """,
        ticket_id, admin_user_id, admin_name, text, photo_file_id,
    )
    await db.pool.execute(
        "UPDATE support_tickets SET updated_at = NOW() WHERE id = $1",
        ticket_id,
    )
    return int(msg_id)


async def get_messages(ticket_id: int) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT id, from_user, admin_user_id, admin_name, text, photo_file_id, created_at, read_at
        FROM support_messages
        WHERE ticket_id = $1
        ORDER BY created_at ASC
        """,
        ticket_id,
    )
    return [dict(r) for r in rows]


async def mark_user_messages_read(ticket_id: int) -> None:
    """Помечает все сообщения от пользователя как прочитанные."""
    await db.pool.execute(
        """
        UPDATE support_messages
        SET read_at = NOW()
        WHERE ticket_id = $1 AND from_user = TRUE AND read_at IS NULL
        """,
        ticket_id,
    )
