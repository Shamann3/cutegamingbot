"""Миграция: создаёт таблицу admin_invite_tokens и добавляет колонку invite_token
в admin_register_pending.

Запуск:
    python migrate_invite_tokens.py
"""

import asyncio
import logging

from db import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_invite_tokens")

STEPS = [
    """
    CREATE TABLE IF NOT EXISTS admin_invite_tokens (
        id          SERIAL PRIMARY KEY,
        token       TEXT NOT NULL UNIQUE,
        label       TEXT NOT NULL DEFAULT '',
        created_by  BIGINT,
        used_by     BIGINT,
        used_at     TIMESTAMPTZ,
        revoked_at  TIMESTAMPTZ,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_invite_tokens_token
        ON admin_invite_tokens (token)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_invite_tokens_created_by
        ON admin_invite_tokens (created_by)
    """,
    """
    ALTER TABLE admin_register_pending
        ADD COLUMN IF NOT EXISTS invite_token TEXT
    """,
]


async def main() -> None:
    await db.connect()
    for sql in STEPS:
        logger.info("Running: %s", sql.strip().splitlines()[0])
        await db.pool.execute(sql)
    logger.info("Done.")
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
