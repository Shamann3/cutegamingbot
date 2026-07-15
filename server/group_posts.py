"""Admin: циклические посты в группы проекта (см.
docs/superpowers/specs/2026-07-15-group-post-campaigns-design.md)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any

from db import db
from telegram_notify import (
    send_telegram_message,
    send_telegram_photo_bytes,
    send_telegram_photo_by_file_id,
)

logger = logging.getLogger("cute-farm.admin.group_posts")

_UTC = timezone.utc

# Telegram Bot API: sendPhoto's caption is capped at 1024 chars (sendMessage
# text-only allows up to 4096). A campaign with a photo and text longer than
# this fails delivery to every target group at send time.
_PHOTO_CAPTION_LIMIT = 1024


def _check_caption_limit(text: str, *, has_photo: bool) -> None:
    if has_photo and len(text) > _PHOTO_CAPTION_LIMIT:
        raise ValueError(
            f"Текст поста с фото не может быть длиннее {_PHOTO_CAPTION_LIMIT} "
            f"символов (сейчас: {len(text)})"
        )


# Теги, которые Telegram реально понимает в parse_mode=HTML. Любой другой тег
# или несбалансированные/неверно вложенные теги Telegram отвергает целиком
# ("Bad Request: can't parse entities") - причём отвечает бесполезным byte
# offset, без указания какой тег виноват (см. инцидент). Поэтому ловим это
# при сохранении кампании, а не постфактум при реальной отправке во все группы.
_TG_ALLOWED_HTML_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "span", "tg-spoiler", "a", "code", "pre", "tg-emoji", "blockquote",
}


class _TelegramHtmlValidator(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.error: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if self.error:
            return
        if tag not in _TG_ALLOWED_HTML_TAGS:
            self.error = f"тег <{tag}> не поддерживается Telegram"
            return
        self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if not self.error:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.error:
            return
        if not self.stack:
            self.error = f"лишний закрывающий тег </{tag}> без открывающего"
            return
        if self.stack[-1] != tag:
            self.error = (
                f"неверная вложенность тегов: ожидался </{self.stack[-1]}>, "
                f"встретился </{tag}>"
            )
            return
        self.stack.pop()


def _validate_telegram_html(text: str) -> None:
    if not text or "<" not in text:
        return
    parser = _TelegramHtmlValidator()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        raise ValueError(f"Некорректный HTML в тексте поста: {exc}")
    if parser.error:
        raise ValueError(f"Некорректный HTML в тексте поста: {parser.error}")
    if parser.stack:
        raise ValueError(f"Некорректный HTML в тексте поста: не закрыт тег <{parser.stack[-1]}>")


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
    # list_campaigns() projects a precomputed `has_photo` boolean (to avoid
    # pulling the full photo_bytes BYTEA over the wire); get_campaign() and
    # the send-execution paths select the real photo_bytes column instead.
    if "has_photo" in row.keys():
        has_photo = bool(row["has_photo"])
    else:
        has_photo = row["photo_bytes"] is not None
    return {
        "id": int(row["id"]),
        "adminUserId": int(row["admin_user_id"]),
        "label": row["label"] or "",
        "chatIds": list(row["chat_ids"] or []),
        "telegramText": row["telegram_text"] or "",
        "hasPhoto": has_photo,
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

# Same as _CAMPAIGN_FIELDS but for list views: replaces the raw photo_bytes
# BYTEA (up to 10MB per campaign) with a cheap boolean, since list callers
# only ever need to know whether a photo is attached, not the bytes.
_LIST_CAMPAIGN_FIELDS = """
    id, admin_user_id, label, chat_ids, telegram_text, (photo_bytes IS NOT NULL) AS has_photo,
    photo_mime, photo_file_id, buttons_json, interval_minutes, status, next_fire_at,
    total_sent, last_error, created_at, updated_at
"""


async def list_campaigns() -> list[dict]:
    rows = await db.pool.fetch(
        f"SELECT {_LIST_CAMPAIGN_FIELDS} FROM group_post_campaigns ORDER BY created_at DESC"
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
    _check_caption_limit(text_clean, has_photo=photo_bytes is not None)
    _validate_telegram_html(text_clean)

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

    # Resolve the post-update state to validate the photo-caption length:
    # - explicit new photo_bytes -> will have a photo
    # - clear_photo -> will not have a photo
    # - neither given -> photo state carries over from the existing campaign
    if photo_bytes is not None:
        final_has_photo = True
    elif clear_photo:
        final_has_photo = False
    else:
        final_has_photo = bool(existing["hasPhoto"])
    final_text = (
        telegram_text.strip() if telegram_text is not None else (existing["telegramText"] or "")
    )
    _check_caption_limit(final_text, has_photo=final_has_photo)
    _validate_telegram_html(final_text)

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
    last_failure_reason: str | None = None

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
            reason = result.category or "other"
            # "other" не говорит ни о чём - показываем реальный текст ошибки от
            # Telegram (например "can't parse entities" из-за битого HTML в
            # тексте/кнопках), а не бесполезное слово "other".
            if reason == "other" and result.description:
                reason = result.description[:300]
            log_batch.append((chat_id, "failed", reason))
            if not last_failure_reason:
                last_failure_reason = reason

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
        detail = f" — {last_failure_reason}" if last_failure_reason else ""
        params.append(f"Не доставлено ни в одну группу ({failed}/{len(chat_ids)}){detail}"[:500])
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


async def list_known_chats() -> list[dict]:
    """Группы для выбора в форме кампании - берёт из уже существующей таблицы
    chat (её ведёт легаси-бот, у неё есть namechat - название группы). Не все
    строки обязательно имеют namechat (например технические чаты чёрного
    рынка) - такие показываются просто по chat_id."""
    rows = await db.pool.fetch(
        "SELECT chat_id, namechat FROM chat ORDER BY namechat NULLS LAST, chat_id"
    )
    return [
        {"chatId": int(r["chat_id"]), "name": r["namechat"]}
        for r in rows
    ]


async def get_campaign_photo(campaign_id: int) -> tuple[bytes, str]:
    row = await db.pool.fetchrow(
        "SELECT photo_bytes, photo_mime FROM group_post_campaigns WHERE id = $1",
        campaign_id,
    )
    if not row or row["photo_bytes"] is None:
        raise ValueError("У кампании нет фото")
    return bytes(row["photo_bytes"]), row["photo_mime"] or "image/jpeg"
