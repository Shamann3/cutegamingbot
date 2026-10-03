"""Копия фото-доказательства в базе.

Панель читает байты отсюда. Если копии ещё нет, photo-proxy скачивает файл
у Telegram один раз и кладёт его сюда.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MAX_PROOF_BYTES = 12 * 1024 * 1024
_ready = False


def sniff_image_type(data: bytes, header: str = "") -> str:
    """Тип картинки по заголовку ответа или по первым байтам. Пусто — это не фото."""
    raw = (header or "").split(";", 1)[0].strip().lower()
    if raw.startswith("image/") and raw not in {"image/svg+xml"}:
        return raw
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 6 and data[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ""


async def ensure_proof_blobs() -> bool:
    global _ready
    if _ready:
        return True
    try:
        from db import db

        await db.pool.execute(
            """
            CREATE TABLE IF NOT EXISTS staff_proof_blobs (
                file_id TEXT PRIMARY KEY,
                body BYTEA NOT NULL,
                content_type TEXT NOT NULL DEFAULT 'image/jpeg',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    except Exception:
        logger.exception("proof blob table is not ready")
        return False
    _ready = True
    return True


async def load_proof_blob(file_id: str) -> tuple[bytes, str] | None:
    key = (file_id or "").strip()
    if not key or not await ensure_proof_blobs():
        return None
    try:
        from db import db

        row = await db.pool.fetchrow(
            "SELECT body, content_type FROM staff_proof_blobs WHERE file_id = $1",
            key,
        )
    except Exception:
        logger.exception("proof blob read failed")
        return None
    if not row or not row["body"]:
        return None
    body = bytes(row["body"])
    kind = sniff_image_type(body, row["content_type"] or "")
    if not kind:
        return None
    return body, kind


async def save_proof_blob(file_id: str, body: bytes, content_type: str = "") -> bool:
    key = (file_id or "").strip()
    data = bytes(body or b"")
    kind = sniff_image_type(data, content_type)
    if not key or not kind or not data or len(data) > MAX_PROOF_BYTES:
        return False
    if not await ensure_proof_blobs():
        return False
    try:
        from db import db

        await db.pool.execute(
            """
            INSERT INTO staff_proof_blobs (file_id, body, content_type)
            VALUES ($1, $2, $3)
            ON CONFLICT (file_id) DO NOTHING
            """,
            key,
            data,
            kind,
        )
    except Exception:
        logger.exception("proof blob write failed")
        return False
    return True
