"""Admin: циклические посты в группы проекта (см.
docs/superpowers/specs/2026-07-15-group-post-campaigns-design.md)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from db import db

logger = logging.getLogger("cute-farm.admin.group_posts")

_UTC = timezone.utc


def _normalize_chat_ids(raw: Any) -> list[int]:
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace(",", "\n").split("\n")]
    else:
        parts = [str(p).strip() for p in (raw or [])]
    ids: list[int] = []
    for part in parts:
        if not part:
            continue
        try:
            cid = int(part)
        except ValueError:
            raise ValueError(f"Некорректный chat_id: {part!r}")
        if cid not in ids:
            ids.append(cid)
    if not ids:
        raise ValueError("Укажите хотя бы одну группу (chat_id)")
    return ids


def _normalize_buttons(raw: Any) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for row in raw or []:
        buttons: list[dict] = []
        for btn in row or []:
            text = str((btn or {}).get("text") or "").strip()
            url = str((btn or {}).get("url") or "").strip()
            btn_type = (btn or {}).get("type") or "url"
            if not text or not url:
                continue
            if btn_type not in ("url", "web_app"):
                btn_type = "url"
            buttons.append({"text": text[:64], "url": url[:512], "type": btn_type})
        if buttons:
            rows.append(buttons)
    return rows


def _campaign_row(row) -> dict:
    buttons = row["buttons_json"]
    if isinstance(buttons, str):
        buttons = json.loads(buttons) if buttons else []
    return {
        "id": int(row["id"]),
        "adminUserId": int(row["admin_user_id"]),
        "label": row["label"] or "",
        "chatIds": list(row["chat_ids"] or []),
        "telegramText": row["telegram_text"] or "",
        "hasPhoto": row["photo_bytes"] is not None,
        "buttons": buttons or [],
        "intervalMinutes": int(row["interval_minutes"]),
        "status": row["status"],
        "nextFireAt": row["next_fire_at"].isoformat() if row["next_fire_at"] else None,
        "totalSent": int(row["total_sent"] or 0),
        "lastError": row["last_error"],
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


_CAMPAIGN_FIELDS = """
    id, admin_user_id, label, chat_ids, telegram_text, photo_bytes, photo_mime,
    photo_file_id, buttons_json, interval_minutes, status, next_fire_at,
    total_sent, last_error, created_at, updated_at
"""


async def list_campaigns() -> list[dict]:
    rows = await db.pool.fetch(
        f"SELECT {_CAMPAIGN_FIELDS} FROM group_post_campaigns ORDER BY created_at DESC"
    )
    return [_campaign_row(r) for r in rows]


async def get_campaign(campaign_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        f"SELECT {_CAMPAIGN_FIELDS} FROM group_post_campaigns WHERE id = $1", campaign_id
    )
    return _campaign_row(row) if row else None


async def create_campaign(
    *,
    admin_user_id: int,
    label: str,
    chat_ids: Any,
    telegram_text: str,
    buttons: list | None,
    interval_minutes: int,
    photo_bytes: bytes | None = None,
    photo_mime: str | None = None,
) -> dict:
    ids = _normalize_chat_ids(chat_ids)
    btns = _normalize_buttons(buttons or [])
    text_clean = (telegram_text or "").strip()
    if not text_clean and not photo_bytes:
        raise ValueError("Укажите текст поста или фото")
    if interval_minutes < 1:
        raise ValueError("Интервал должен быть не меньше 1 минуты")

    row = await db.pool.fetchrow(
        """
        INSERT INTO group_post_campaigns (
            admin_user_id, label, chat_ids, telegram_text, photo_bytes, photo_mime,
            buttons_json, interval_minutes, status
        )
        VALUES ($1, $2, $3::bigint[], $4, $5, $6, $7::jsonb, $8, 'active')
        RETURNING id
        """,
        admin_user_id,
        (label or "").strip()[:120],
        ids,
        text_clean,
        photo_bytes,
        photo_mime,
        json.dumps(btns, ensure_ascii=False),
        int(interval_minutes),
    )
    return await get_campaign(int(row["id"]))


async def update_campaign(
    campaign_id: int,
    *,
    label: str | None = None,
    chat_ids: Any = None,
    telegram_text: str | None = None,
    buttons: list | None = None,
    interval_minutes: int | None = None,
    photo_bytes: bytes | None = None,
    photo_mime: str | None = None,
    clear_photo: bool = False,
) -> dict:
    existing = await get_campaign(campaign_id)
    if not existing:
        raise ValueError("Кампания не найдена")

    sets: list[str] = []
    params: list[Any] = []
    idx = 1

    def add(field: str, value: Any, cast: str = "") -> None:
        nonlocal idx
        sets.append(f"{field} = ${idx}{cast}")
        params.append(value)
        idx += 1

    if label is not None:
        add("label", label.strip()[:120])
    if chat_ids is not None:
        add("chat_ids", _normalize_chat_ids(chat_ids), "::bigint[]")
    if telegram_text is not None:
        add("telegram_text", telegram_text.strip())
    if buttons is not None:
        add("buttons_json", json.dumps(_normalize_buttons(buttons), ensure_ascii=False), "::jsonb")
    if interval_minutes is not None:
        if interval_minutes < 1:
            raise ValueError("Интервал должен быть не меньше 1 минуты")
        add("interval_minutes", int(interval_minutes))
    if photo_bytes is not None:
        add("photo_bytes", photo_bytes)
        add("photo_mime", photo_mime)
        add("photo_file_id", None)  # новое фото - сбрасываем кэш file_id
    elif clear_photo:
        add("photo_bytes", None)
        add("photo_mime", None)
        add("photo_file_id", None)

    if not sets:
        return existing

    add("updated_at", datetime.now(_UTC))
    params.append(campaign_id)
    await db.pool.execute(
        f"UPDATE group_post_campaigns SET {', '.join(sets)} WHERE id = ${idx}",
        *params,
    )
    return await get_campaign(campaign_id)


async def set_campaign_status(campaign_id: int, status: str) -> dict:
    if status not in ("active", "paused"):
        raise ValueError("Неверный статус")
    row = await db.pool.fetchrow(
        "UPDATE group_post_campaigns SET status = $2, updated_at = NOW() WHERE id = $1 RETURNING id",
        campaign_id, status,
    )
    if not row:
        raise ValueError("Кампания не найдена")
    return await get_campaign(campaign_id)


async def delete_campaign(campaign_id: int) -> None:
    result = await db.pool.execute("DELETE FROM group_post_campaigns WHERE id = $1", campaign_id)
    if result == "DELETE 0":
        raise ValueError("Кампания не найдена")
