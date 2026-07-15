"""Admin: циклические посты в группы проекта (см.
docs/superpowers/specs/2026-07-15-group-post-campaigns-design.md)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from db import db
from telegram_notify import (
    send_telegram_message,
    send_telegram_photo_bytes,
    send_telegram_photo_by_file_id,
)

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


TELEGRAM_SEND_DELAY = 0.04  # тот же троттлинг, что у admin_broadcast.py
POST_LOG_FLUSH_SIZE = 100


async def _flush_post_log(campaign_id: int, batch: list[tuple[int, str, str | None]]) -> None:
    """batch: (chat_id, status, fail_reason). Bulk-insert через UNNEST - тот же
    паттерн, что у admin_broadcast.py::_flush_recipient_log."""
    if not batch:
        return
    chat_ids = [b[0] for b in batch]
    statuses = [b[1] for b in batch]
    reasons = [b[2] for b in batch]
    try:
        await db.pool.execute(
            """
            INSERT INTO group_post_log (campaign_id, chat_id, status, fail_reason)
            SELECT $1, c, s, r
            FROM UNNEST($2::bigint[], $3::text[], $4::text[]) AS t(c, s, r)
            """,
            campaign_id, chat_ids, statuses, reasons,
        )
    except Exception:
        logger.exception("Failed to log group post recipients (campaign_id=%s)", campaign_id)


async def _execute_group_post_send(row) -> dict:
    """row: asyncpg Record с полями из _CAMPAIGN_FIELDS. Шлёт пост во все
    chat_ids кампании, возвращает {"sent": int, "failed": int, "fileId": str|None}."""
    campaign_id = int(row["id"])
    chat_ids: list[int] = list(row["chat_ids"] or [])
    text = row["telegram_text"] or ""
    buttons = row["buttons_json"]
    if isinstance(buttons, str):
        buttons = json.loads(buttons) if buttons else []
    photo_bytes = row["photo_bytes"]
    photo_mime = row["photo_mime"] or "image/jpeg"
    file_id = row["photo_file_id"]

    sent = 0
    failed = 0
    log_batch: list[tuple[int, str, str | None]] = []
    new_file_id: str | None = None

    for chat_id in chat_ids:
        if photo_bytes is not None and not file_id and new_file_id is None:
            result = await send_telegram_photo_bytes(
                photo_bytes,
                chat_id=str(chat_id),
                caption=text,
                content_type=photo_mime,
                buttons=buttons,
            )
            if result.ok and result.file_id:
                new_file_id = result.file_id
        elif photo_bytes is not None:
            result = await send_telegram_photo_by_file_id(
                file_id or new_file_id,
                chat_id=str(chat_id),
                caption=text,
                buttons=buttons,
            )
        else:
            result = await send_telegram_message(text, chat_id=str(chat_id), buttons=buttons)

        if result.ok:
            sent += 1
            log_batch.append((chat_id, "sent", None))
        else:
            failed += 1
            log_batch.append((chat_id, "failed", result.category or "other"))

        if len(log_batch) >= POST_LOG_FLUSH_SIZE:
            await _flush_post_log(campaign_id, log_batch)
            log_batch.clear()
        await asyncio.sleep(TELEGRAM_SEND_DELAY)

    await _flush_post_log(campaign_id, log_batch)

    updates = ["total_sent = total_sent + $2", "updated_at = NOW()"]
    params: list[Any] = [campaign_id, sent]
    idx = 3
    if new_file_id:
        updates.append(f"photo_file_id = ${idx}")
        params.append(new_file_id)
        idx += 1
    if failed and failed == len(chat_ids):
        updates.append(f"last_error = ${idx}")
        params.append(f"Не доставлено ни в одну группу ({failed}/{len(chat_ids)})")
        idx += 1
    elif sent:
        updates.append("last_error = NULL")

    await db.pool.execute(
        f"UPDATE group_post_campaigns SET {', '.join(updates)} WHERE id = $1",
        *params,
    )
    return {"sent": sent, "failed": failed, "fileId": new_file_id}


async def _fire_group_post_campaigns() -> None:
    """Вызывается из event_scheduler._tick() каждые 30с."""
    now = datetime.now(_UTC)
    due = await db.pool.fetch(
        """
        SELECT id, interval_minutes, next_fire_at
        FROM group_post_campaigns
        WHERE status = 'active' AND next_fire_at IS NOT NULL AND next_fire_at <= $1
        """,
        now,
    )
    for candidate in due:
        campaign_id = int(candidate["id"])
        interval = int(candidate["interval_minutes"])
        prev_fire_at = candidate["next_fire_at"]
        claimed = await db.pool.fetchrow(
            """
            UPDATE group_post_campaigns
            SET next_fire_at = $3
            WHERE id = $1 AND next_fire_at = $2
            RETURNING id
            """,
            campaign_id, prev_fire_at, now + timedelta(minutes=interval),
        )
        if not claimed:
            continue  # другой тик/воркер уже забрал этот запуск
        row = await db.pool.fetchrow(
            f"SELECT {_CAMPAIGN_FIELDS} FROM group_post_campaigns WHERE id = $1",
            campaign_id,
        )
        if not row or row["status"] != "active":
            continue
        try:
            result = await _execute_group_post_send(row)
            logger.info(
                "Group post campaign fired: id=%s sent=%s failed=%s",
                campaign_id, result["sent"], result["failed"],
            )
        except Exception:
            logger.exception("Group post campaign failed (id=%s)", campaign_id)

    # Кампании без next_fire_at (только что созданные) - выставляем расписание,
    # не стреляем сразу (та же логика, что у ежедневной ротации в admin_broadcast.py).
    fresh = await db.pool.fetch(
        "SELECT id, interval_minutes FROM group_post_campaigns WHERE status = 'active' AND next_fire_at IS NULL"
    )
    for row in fresh:
        await db.pool.execute(
            "UPDATE group_post_campaigns SET next_fire_at = $2 WHERE id = $1 AND next_fire_at IS NULL",
            int(row["id"]), now + timedelta(minutes=int(row["interval_minutes"])),
        )


async def run_campaign_now(campaign_id: int) -> dict:
    """Кнопка «Отправить сейчас» - не трогает next_fire_at."""
    row = await db.pool.fetchrow(
        f"SELECT {_CAMPAIGN_FIELDS} FROM group_post_campaigns WHERE id = $1",
        campaign_id,
    )
    if not row:
        raise ValueError("Кампания не найдена")
    return await _execute_group_post_send(row)


async def list_campaign_log(campaign_id: int, *, limit: int = 50, offset: int = 0) -> dict:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    total = int(
        await db.pool.fetchval(
            "SELECT COUNT(*)::int FROM group_post_log WHERE campaign_id = $1", campaign_id,
        ) or 0
    )
    rows = await db.pool.fetch(
        """
        SELECT chat_id, status, fail_reason, created_at
        FROM group_post_log
        WHERE campaign_id = $1
        ORDER BY id DESC
        LIMIT $2 OFFSET $3
        """,
        campaign_id, limit, offset,
    )
    return {
        "total": total,
        "items": [
            {
                "chatId": int(r["chat_id"]),
                "status": r["status"],
                "failReason": r["fail_reason"],
                "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }
