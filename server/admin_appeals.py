"""Апелляции банов игроков."""

from __future__ import annotations

import logging
from typing import Any

from db import db

logger = logging.getLogger(__name__)


def _row(r) -> dict:
    return {
        "id": int(r["id"]),
        "userId": int(r["user_id"]),
        "username": r["username"] or "",
        "firstName": r["first_name"] or "",
        "banReason": r["ban_reason"] or "",
        "appealText": r["appeal_text"] or "",
        "status": r["status"],
        "takenBy": int(r["taken_by"]) if r["taken_by"] else None,
        "takenAt": r["taken_at"].isoformat() if r["taken_at"] else None,
        "resolvedBy": int(r["resolved_by"]) if r["resolved_by"] else None,
        "resolvedAt": r["resolved_at"].isoformat() if r["resolved_at"] else None,
        "resolution": r["resolution"] or "",
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
    }


async def submit_appeal(
    user_id: int,
    appeal_text: str,
    *,
    username: str = "",
    first_name: str = "",
    ban_reason: str = "",
) -> dict:
    """Игрок подаёт апелляцию. Один активный тикет на пользователя."""
    existing = await db.pool.fetchval(
        "SELECT id FROM ban_appeals WHERE user_id = $1 AND status = 'pending'",
        user_id,
    )
    if existing:
        raise ValueError("У вас уже есть активная апелляция на рассмотрении")

    text = (appeal_text or "").strip()
    if not text:
        raise ValueError("Текст апелляции не может быть пустым")
    if len(text) > 1000:
        raise ValueError("Текст апелляции не должен превышать 1000 символов")

    row = await db.pool.fetchrow(
        """
        INSERT INTO ban_appeals
            (user_id, username, first_name, ban_reason, appeal_text)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, created_at
        """,
        user_id,
        (username or "").strip() or None,
        (first_name or "").strip() or None,
        (ban_reason or "").strip() or None,
        text,
    )

    appeal_id = int(row["id"])

    # Уведомляем владельцев и senior_admin
    _notify_new_appeal(user_id, first_name or username or str(user_id), text, appeal_id)

    return {"id": appeal_id, "status": "pending"}


def _notify_new_appeal(user_id: int, name: str, text: str, appeal_id: int) -> None:
    import asyncio
    from staff_notify import notify_owners
    from db import db as _db

    preview = text[:200] + ("..." if len(text) > 200 else "")

    msg = (
        f"<tg-emoji emoji-id='5258274739041883702'>🔍</tg-emoji> <b>Новая апелляция #{appeal_id}</b>\n\n"
        f"<tg-emoji emoji-id='5364052602357044385'>🐶</tg-emoji> <b>Игрок :</b> {name} · <code>{user_id}</code>\n"
        f"<tg-emoji emoji-id='5292226786229236118'>🔄</tg-emoji> <b>Текст :</b> {preview}\n\n"
        f"<i>Откройте панель → Модерация → Апелляции чтобы взять тикет.</i>"
    )

    async def _send():
        notify_owners(msg)
        # Уведомляем всех senior_admin
        try:
            rows = await _db.pool.fetch(
                "SELECT user_id FROM admin_accounts WHERE role = 'senior_admin' AND status = 'active'"
            )
            from staff_notify import notify_staff
            for r in rows:
                notify_staff(int(r["user_id"]), msg)
        except Exception as e:
            logger.warning("appeal notify senior failed: %s", e)

    asyncio.create_task(_send())


async def list_appeals(*, status: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    conditions: list[str] = ["1=1"]
    params: list[Any] = []
    idx = 1

    if status and status in ("pending", "taken", "approved", "rejected"):
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1

    where = " AND ".join(conditions)
    total = int(await db.pool.fetchval(f"SELECT COUNT(*)::int FROM ban_appeals WHERE {where}", *params) or 0)

    params.extend([limit, offset])
    rows = await db.pool.fetch(
        f"""
        SELECT id, user_id, username, first_name, ban_reason, appeal_text,
               status, taken_by, taken_at, resolved_by, resolved_at, resolution, created_at
        FROM ban_appeals
        WHERE {where}
        ORDER BY
            CASE status WHEN 'pending' THEN 0 WHEN 'taken' THEN 1 ELSE 2 END,
            created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )
    return {"total": total, "items": [_row(r) for r in rows]}


async def take_appeal(appeal_id: int, admin_id: int) -> dict:
    row = await db.pool.fetchrow(
        "SELECT status FROM ban_appeals WHERE id = $1", appeal_id
    )
    if not row:
        raise ValueError("Апелляция не найдена")
    if row["status"] != "pending":
        raise ValueError("Апелляция уже взята или закрыта")

    updated = await db.pool.fetchrow(
        """
        UPDATE ban_appeals
        SET status = 'taken', taken_by = $2, taken_at = NOW()
        WHERE id = $1 AND status = 'pending'
        RETURNING id, status, taken_by, taken_at
        """,
        appeal_id, admin_id,
    )
    if not updated:
        raise ValueError("Апелляция уже взята другим администратором")

    return {"id": appeal_id, "status": "taken"}


async def resolve_appeal(
    appeal_id: int,
    admin_id: int,
    *,
    approve: bool,
    resolution: str = "",
) -> dict:
    row = await db.pool.fetchrow(
        "SELECT status, user_id, first_name, username FROM ban_appeals WHERE id = $1",
        appeal_id,
    )
    if not row:
        raise ValueError("Апелляция не найдена")
    if row["status"] not in ("pending", "taken"):
        raise ValueError("Апелляция уже закрыта")

    new_status = "approved" if approve else "rejected"
    resolution_text = (resolution or "").strip() or ("Апелляция одобрена" if approve else "Апелляция отклонена")

    await db.pool.execute(
        """
        UPDATE ban_appeals
        SET status = $2, resolved_by = $3, resolved_at = NOW(), resolution = $4
        WHERE id = $1
        """,
        appeal_id, new_status, admin_id, resolution_text,
    )

    user_id = int(row["user_id"])

    if approve:
        # Разбан через уже существующую функцию
        from admin_users import admin_set_banned
        try:
            await admin_set_banned(user_id, False, admin_user_id=admin_id, reason="")
        except Exception as e:
            logger.warning("unban on appeal approve failed: %s", e)

    # Уведомляем игрока
    _notify_player_resolution(
        user_id,
        row["first_name"] or row["username"] or str(user_id),
        approve=approve,
        resolution=resolution_text,
    )

    return {"id": appeal_id, "status": new_status, "approved": approve}


def _notify_player_resolution(user_id: int, name: str, *, approve: bool, resolution: str) -> None:
    import asyncio
    from staff_notify import notify_staff

    if approve:
        msg = (
            f"<tg-emoji emoji-id='5208540237524911208'>✅</tg-emoji> <b>Ваша апелляция одобрена</b>\n\n"
            f"<b>Уважаемый {name}, наказание снято</b>\n"
            f"<i>{resolution}</i>\n\n"
            f"<blockquote><b>Пожалуйста, соблюдайте правила проекта.</b></blockquote>"
        )
    else:
        msg = (
            f"<tg-emoji emoji-id='5208788125857366775'>🗽</tg-emoji> <b>Ваша апелляция отклонена</b>\n\n"
            f"<b>Уважаемый {name}, ваша апелляция была рассмотрена и отклонена.</b>\n"
            f"<i>{resolution}</i>\n\n"
            f"<blockquote><b>Если вы считаете это ошибкой — обратитесь в поддержку.</b></blockquote>"
        )

    asyncio.create_task(_send_dm(user_id, msg))


async def _send_dm(user_id: int, text: str) -> None:
    from config import SUPPORT_BOT_TOKEN
    from telegram_notify import send_telegram_message
    try:
        await send_telegram_message(text, chat_id=str(user_id), token=SUPPORT_BOT_TOKEN)
    except Exception as e:
        logger.warning("appeal player notify failed (user_id=%s): %s", user_id, e)


async def get_appeal_messages(appeal_id: int) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT id, from_user, admin_id, admin_name, text, photo_file_id, created_at
        FROM ban_appeal_messages
        WHERE appeal_id = $1
        ORDER BY created_at ASC
        """,
        appeal_id,
    )
    return [
        {
            "id": int(r["id"]),
            "fromUser": r["from_user"],
            "adminId": int(r["admin_id"]) if r["admin_id"] else None,
            "adminName": r["admin_name"] or "",
            "text": r["text"] or "",
            "photoFileId": r["photo_file_id"],
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def send_appeal_message(
    appeal_id: int,
    admin_id: int,
    admin_name: str,
    text: str,
    photo_file_id: str | None = None,
) -> dict:
    row = await db.pool.fetchrow(
        "SELECT user_id, status FROM ban_appeals WHERE id = $1", appeal_id,
    )
    if not row:
        raise ValueError("Апелляция не найдена")
    if row["status"] in ("approved", "rejected"):
        raise ValueError("Апелляция уже закрыта")

    text = (text or "").strip()
    if not text and not photo_file_id:
        raise ValueError("Сообщение не может быть пустым")

    msg_id = await db.pool.fetchval(
        """
        INSERT INTO ban_appeal_messages
            (appeal_id, from_user, admin_id, admin_name, text, photo_file_id)
        VALUES ($1, FALSE, $2, $3, $4, $5)
        RETURNING id
        """,
        appeal_id, admin_id, admin_name, text, photo_file_id,
    )

    # Обновляем updated_at апелляции
    await db.pool.execute(
        "UPDATE ban_appeals SET taken_by = COALESCE(taken_by, $2), status = CASE WHEN status = 'pending' THEN 'taken' ELSE status END WHERE id = $1",
        appeal_id, admin_id,
    )

    # Отправляем игроку в Telegram
    user_id = int(row["user_id"])
    _send_message_to_player(user_id, text, photo_file_id, admin_name)

    return {"id": int(msg_id)}


def _send_message_to_player(user_id: int, text: str, photo_file_id: str | None, admin_name: str) -> None:
    import asyncio
    from config import SUPPORT_BOT_TOKEN

    async def _send():
        import aiohttp
        if not SUPPORT_BOT_TOKEN:
            return
        header = f"<b>Ответ администратора по апелляции:</b>\n\n"
        full_text = header + (text or "")
        try:
            async with aiohttp.ClientSession() as session:
                if photo_file_id:
                    await session.post(
                        f"https://api.telegram.org/bot{SUPPORT_BOT_TOKEN}/sendPhoto",
                        json={
                            "chat_id": user_id,
                            "photo": photo_file_id,
                            "caption": full_text,
                            "parse_mode": "HTML",
                        },
                    )
                else:
                    await session.post(
                        f"https://api.telegram.org/bot{SUPPORT_BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": user_id,
                            "text": full_text,
                            "parse_mode": "HTML",
                        },
                    )
        except Exception as e:
            logger.warning("appeal message to player failed: %s", e)

    asyncio.create_task(_send())


async def add_player_appeal_message(
    appeal_id: int,
    user_id: int,
    text: str,
) -> dict:
    """Игрок отвечает в апелляции через support бот."""
    row = await db.pool.fetchrow(
        "SELECT user_id, status FROM ban_appeals WHERE id = $1", appeal_id,
    )
    if not row or int(row["user_id"]) != user_id:
        raise ValueError("Апелляция не найдена")
    if row["status"] in ("approved", "rejected"):
        raise ValueError("Апелляция уже закрыта")

    msg_id = await db.pool.fetchval(
        """
        INSERT INTO ban_appeal_messages (appeal_id, from_user, text)
        VALUES ($1, TRUE, $2)
        RETURNING id
        """,
        appeal_id, (text or "").strip(),
    )

    # Уведомляем admin кто взял апелляцию
    taken_by = await db.pool.fetchval(
        "SELECT taken_by FROM ban_appeals WHERE id = $1", appeal_id,
    )
    if taken_by:
        import asyncio
        from staff_notify import notify_staff
        asyncio.create_task(_notify_staff_coroutine(int(taken_by), appeal_id, text))

    return {"id": int(msg_id)}


async def _notify_staff_coroutine(admin_id: int, appeal_id: int, text: str) -> None:
    from staff_notify import notify_staff
    preview = text[:200] + ("..." if len(text) > 200 else "")
    notify_staff(admin_id, f"💬 <b>Ответ в апелляции #{appeal_id}:</b>\n{preview}")


async def get_player_appeal_status(user_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        """
        SELECT id, status, resolution, created_at
        FROM ban_appeals WHERE user_id = $1
        ORDER BY created_at DESC LIMIT 1
        """,
        user_id,
    )
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "status": row["status"],
        "resolution": row["resolution"] or "",
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
    }
