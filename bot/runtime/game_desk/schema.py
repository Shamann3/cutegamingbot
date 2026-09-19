# -*- coding: utf-8 -*-
"""Схема стола игр. Идемпотентно, без DROP."""

from __future__ import annotations

_DDL = """
CREATE TABLE IF NOT EXISTS game_desk_settings (
    id SMALLINT PRIMARY KEY DEFAULT 1,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by BIGINT,
    CONSTRAINT game_desk_settings_singleton CHECK (id = 1)
);

INSERT INTO game_desk_settings (id, payload)
VALUES (1, '{}'::jsonb)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS game_desk_history (
    id BIGSERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL,
    patch JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_game_desk_history_created
    ON game_desk_history (created_at DESC);
"""


async def ensure_game_desk_schema(db) -> None:
    pool = getattr(db, "pool", None)
    if pool is None:
        ensure = getattr(db, "ensure_pool", None)
        if callable(ensure):
            ok = ensure()
            if hasattr(ok, "__await__"):
                ok = await ok
            if not ok:
                raise RuntimeError("Пул соединений не инициализирован (ensure_game_desk_schema).")
            pool = getattr(db, "pool", None)
        if pool is None:
            connect = getattr(db, "connect", None) or getattr(db, "ensure_connected", None)
            if callable(connect):
                maybe = connect()
                if hasattr(maybe, "__await__"):
                    await maybe
                pool = getattr(db, "pool", None)
    if pool is None:
        raise RuntimeError("Пул соединений не инициализирован (ensure_game_desk_schema).")
    async with pool.acquire() as conn:
        await conn.execute(_DDL)
