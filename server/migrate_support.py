"""Миграция: создаёт таблицы для системы поддержки.

Запуск:
    python migrate_support.py
"""

import asyncio
import logging

from db import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_support")

SQL = """
CREATE TABLE IF NOT EXISTS support_tickets (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    username    TEXT,
    first_name  TEXT,
    subject     TEXT NOT NULL DEFAULT '',
    status      VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status_updated
    ON support_tickets (status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id
    ON support_tickets (user_id);

CREATE TABLE IF NOT EXISTS support_messages (
    id            SERIAL PRIMARY KEY,
    ticket_id     INT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
    from_user     BOOLEAN NOT NULL,
    admin_user_id BIGINT,
    admin_name    TEXT,
    text          TEXT NOT NULL,
    photo_file_id TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_support_messages_ticket
    ON support_messages (ticket_id, created_at);

ALTER TABLE support_messages ADD COLUMN IF NOT EXISTS photo_file_id TEXT;

-- Один открытый тикет на пользователя: схлопываем существующие дубли
-- (оставляем самый новый открытый тикет, остальные закрываем) и ставим
-- уникальный частичный индекс от гонки. См. support_db._DDL.
UPDATE support_tickets t
SET status = 'closed', updated_at = NOW()
WHERE t.status = 'open'
  AND t.id NOT IN (
      SELECT DISTINCT ON (user_id) id
      FROM support_tickets
      WHERE status = 'open'
      ORDER BY user_id, created_at DESC
  );

CREATE UNIQUE INDEX IF NOT EXISTS uq_support_tickets_one_open
    ON support_tickets (user_id) WHERE status = 'open';
"""


async def main() -> None:
    await db.connect()
    try:
        await db.pool.execute(SQL)
        logger.info("Таблицы support_tickets и support_messages созданы (или уже существовали).")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
