# -*- coding: utf-8 -*-
"""Сохраняет фото-доказательство в базу сразу, как бот его получил.

Дальше панель показывает эту копию и не зависит от того, ответит ли Telegram
на getFile через день или через месяц.
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

MAX_PROOF_BYTES = 12 * 1024 * 1024
_backfill_started = False
_failed: dict[str, int] = {}


def _image_type(data: bytes) -> str:
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 6 and data[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ""


async def _ensure(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS staff_proof_blobs (
            file_id TEXT PRIMARY KEY,
            body BYTEA NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'image/jpeg',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


async def _store(file_id: str, data: bytes) -> bool:
    kind = _image_type(data)
    if not file_id or not kind or len(data) > MAX_PROOF_BYTES:
        return False
    from main import db

    async with db.pool.acquire() as conn:
        await _ensure(conn)
        await conn.execute(
            """
            INSERT INTO staff_proof_blobs (file_id, body, content_type)
            VALUES ($1, $2, $3)
            ON CONFLICT (file_id) DO NOTHING
            """,
            file_id,
            data,
            kind,
        )
    return True


async def _download(file_id: str) -> bytes:
    from main import bot1

    tg_file = await bot1.get_file(file_id)
    path = getattr(tg_file, "file_path", None) if tg_file else None
    if not path:
        return b""
    buf = await bot1.download_file(path)
    if buf is None:
        return b""
    if isinstance(buf, (bytes, bytearray)):
        return bytes(buf)
    data = buf.read()
    return bytes(data or b"")


async def save_proof_now(file_id: str) -> bool:
    key = (file_id or "").strip()
    if not key or _failed.get(key, 0) >= 3:
        return False
    try:
        data = await _download(key)
        if await _store(key, data):
            _failed.pop(key, None)
            return True
    except Exception:
        logger.exception("proof blob save failed")
    _failed[key] = _failed.get(key, 0) + 1
    return False


def schedule_proof_save(file_id: str) -> None:
    key = (file_id or "").strip()
    if not key:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(save_proof_now(key))


async def _backfill() -> None:
    await asyncio.sleep(2)
    from main import db

    while True:
        try:
            async with db.pool.acquire() as conn:
                await _ensure(conn)
                rows = await conn.fetch(
                    """
                    SELECT s.proof_media_id
                    FROM staff_actions s
                    WHERE s.proof_media_id IS NOT NULL
                      AND s.proof_media_id <> ''
                      AND NOT EXISTS (
                        SELECT 1 FROM staff_proof_blobs b
                        WHERE b.file_id = s.proof_media_id
                      )
                    ORDER BY s.id DESC
                    LIMIT 6
                    """
                )
        except Exception:
            logger.exception("proof backfill query failed")
            await asyncio.sleep(30)
            continue
        pending = []
        for row in rows:
            key = (row["proof_media_id"] or "").strip()
            if key and _failed.get(key, 0) < 3:
                pending.append(key)
        if not pending:
            return
        for key in pending:
            await save_proof_now(key)
            await asyncio.sleep(0.4)
        await asyncio.sleep(1.5)


def start_proof_backfill() -> None:
    """Догоняет старые наказания, у которых в базе ещё нет копии фото."""
    global _backfill_started
    if _backfill_started:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _backfill_started = True
    loop.create_task(_backfill())
