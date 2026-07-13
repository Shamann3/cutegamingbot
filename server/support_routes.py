"""FastAPI-роуты для системы поддержки в админ-панели."""

from __future__ import annotations

import html as _html

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from admin_auth import require_admin_session, _get_client_ip
from admin_audit import log_admin_action
from admin_permissions import ROLE_LABELS
from config import SUPPORT_BOT_TOKEN
from telegram_notify import send_telegram_message
from db import db
import support_db

router = APIRouter(prefix="/admin/api/support", tags=["support"])


def _fmt_dt(dt) -> str | None:
    if dt is None:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def _serialize_ticket(t: dict) -> dict:
    return {
        "id":                t["id"],
        "userId":            t["user_id"],
        "username":          t.get("username"),
        "firstName":         t.get("first_name"),
        "subject":           t.get("subject") or "",
        "status":            t["status"],
        "assignedAdminId":   t.get("assigned_admin_id"),
        "assignedAdminName": t.get("assigned_admin_name"),
        "createdAt":         _fmt_dt(t.get("created_at")),
        "updatedAt":         _fmt_dt(t.get("updated_at")),
        "lastText":          t.get("last_text"),
        "lastFromUser":      t.get("last_from_user"),
        "unread":            int(t.get("unread") or 0),
    }


def _serialize_message(m: dict) -> dict:
    is_system = not m["from_user"] and not m.get("admin_name")
    return {
        "id":          m["id"],
        "fromUser":    m["from_user"],
        "isSystem":    is_system,
        "adminId":     m.get("admin_user_id"),
        "adminName":   m.get("admin_name"),
        "text":        m["text"],
        "photoFileId": m.get("photo_file_id") or m.get("photoFileId"),
        "createdAt":   _fmt_dt(m.get("created_at")),
        "readAt":      _fmt_dt(m.get("read_at")),
    }


async def _admin_display_name(admin_user_id: int) -> str:
    try:
        row = await db.pool.fetchrow(
            "SELECT first_name, username FROM admin_accounts WHERE user_id = $1",
            admin_user_id,
        )
        if row:
            return (
                row["first_name"]
                or (f"@{row['username']}" if row["username"] else f"ID {admin_user_id}")
            )
    except Exception:
        pass
    return f"Администратор"


async def _send_claim_greeting_if_needed(ticket: dict, admin_user_id: int) -> None:
    """Перед ПЕРВЫМ ответом админа после claim отправляет пользователю
    техническое сообщение: кто из сотрудников будет помогать (кликабельно),
    его должность и счётчик закрытых им заявок. Не считается официальным
    ответом админа - в админ-панели рисуется отдельным серым сообщением
    (см. _serialize_message.isSystem)."""
    if ticket.get("greeting_sent"):
        return

    try:
        row = await db.pool.fetchrow(
            "SELECT first_name, username, role FROM admin_accounts WHERE user_id = $1",
            admin_user_id,
        )
    except Exception:
        row = None

    display_name = (
        (row["first_name"] or (f"@{row['username']}" if row and row["username"] else None))
        if row else None
    ) or f"ID {admin_user_id}"
    role_label = ROLE_LABELS.get(row["role"], row["role"]) if row and row.get("role") else "Сотрудник"
    closed_count = await support_db.count_closed_tickets_for_admin(admin_user_id)

    name_link = f'<a href="tg://user?id={admin_user_id}">{_html.escape(display_name)}</a>'
    greeting_text = (
        "<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> <b>Виво Эпсилон</b>\n"
        f"<b><tg-emoji emoji-id='5390858914885568318'>👑</tg-emoji> Вам будет помогать "
        f"{_html.escape(role_label)} {name_link}</b>\n"
        f"<b><tg-emoji emoji-id='5391115556361370746'>👏</tg-emoji> На счёту сотрудника "
        f"{closed_count} закрытых заявок на помощь</b>"
    )

    await support_db.add_system_message(ticket["id"], greeting_text)
    if SUPPORT_BOT_TOKEN:
        try:
            await send_telegram_message(
                greeting_text,
                chat_id=str(ticket["user_id"]),
                token=SUPPORT_BOT_TOKEN,
            )
        except Exception:
            pass
    await support_db.mark_greeting_sent(ticket["id"])


# ---------------------------------------------------------------------------
# GET /support/tickets
# ---------------------------------------------------------------------------

@router.get("/tickets")
async def list_tickets(
    status: str = "open",
    admin_user_id: int = Depends(require_admin_session),
):
    if status not in ("open", "closed", "all"):
        raise HTTPException(400, "status должен быть open, closed или all")
    tickets = await support_db.list_tickets(status=status)
    return {"tickets": [_serialize_ticket(t) for t in tickets]}


# ---------------------------------------------------------------------------
# GET /support/tickets/{ticket_id}
# ---------------------------------------------------------------------------

@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: int,
    admin_user_id: int = Depends(require_admin_session),
):
    ticket = await support_db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "Тикет не найден")
    messages = await support_db.get_messages(ticket_id)
    await support_db.mark_user_messages_read(ticket_id)
    return {
        "ticket":   _serialize_ticket(ticket),
        "messages": [_serialize_message(m) for m in messages],
    }


# ---------------------------------------------------------------------------
# POST /support/tickets/{ticket_id}/claim
# ---------------------------------------------------------------------------

@router.post("/tickets/{ticket_id}/claim")
async def claim_ticket(
    ticket_id: int,
    request: Request,
    admin_user_id: int = Depends(require_admin_session),
):
    ticket = await support_db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "Тикет не найден")
    if ticket["status"] == "closed":
        raise HTTPException(400, "Тикет закрыт")

    admin_name = await _admin_display_name(admin_user_id)
    ok = await support_db.claim_ticket(ticket_id, admin_user_id, admin_name)
    if not ok:
        raise HTTPException(409, "Тикет уже взят или недоступен")

    await log_admin_action(
        admin_user_id,
        "support_claim",
        target_type="support_ticket",
        target_id=str(ticket_id),
        target_label=f"Тикет #{ticket_id} — {ticket.get('subject') or 'без темы'}",
        ip=_get_client_ip(request),
    )

    return {"ok": True, "assignedAdminName": admin_name}


# ---------------------------------------------------------------------------
# POST /support/tickets/{ticket_id}/reply
# ---------------------------------------------------------------------------

class ReplyBody(BaseModel):
    text: str = Field(default="", max_length=4000)
    photoFileId: str = Field(default="")
    model_config = {"extra": "forbid"}


@router.post("/tickets/{ticket_id}/reply")
async def reply_to_ticket(
    ticket_id: int,
    body: ReplyBody,
    request: Request,
    admin_user_id: int = Depends(require_admin_session),
):
    if not body.text.strip() and not body.photoFileId.strip():
        raise HTTPException(400, "Текст или фото обязательны")

    ticket = await support_db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "Тикет не найден")
    if ticket["status"] == "closed":
        raise HTTPException(400, "Тикет закрыт")

    await _send_claim_greeting_if_needed(ticket, admin_user_id)

    admin_name = await _admin_display_name(admin_user_id)
    photo_id = body.photoFileId.strip() or None
    await support_db.add_admin_message(
        ticket_id, admin_user_id, admin_name, body.text, photo_id,
    )

    if SUPPORT_BOT_TOKEN:
        try:
            import aiohttp as _aiohttp
            async with _aiohttp.ClientSession() as session:
                if photo_id:
                    # Всегда Telegram file_id
                    await session.post(
                        f"https://api.telegram.org/bot{SUPPORT_BOT_TOKEN}/sendPhoto",
                        json={"chat_id": str(ticket["user_id"]), "photo": photo_id,
                              "caption": body.text or None, "parse_mode": "HTML"},
                    )
                elif body.text.strip():
                    await session.post(
                        f"https://api.telegram.org/bot{SUPPORT_BOT_TOKEN}/sendMessage",
                        json={"chat_id": str(ticket["user_id"]),
                              "text": body.text, "parse_mode": "HTML"},
                    )
        except Exception:
            pass

    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /support/tickets/{ticket_id}/close
# ---------------------------------------------------------------------------

class CloseBody(BaseModel):
    notify: bool = True
    model_config = {"extra": "forbid"}


@router.post("/tickets/{ticket_id}/close")
async def close_ticket(
    ticket_id: int,
    body: CloseBody = CloseBody(),
    request: Request = None,
    admin_user_id: int = Depends(require_admin_session),
):
    ticket = await support_db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "Тикет не найден")

    await support_db.close_ticket(ticket_id)

    await log_admin_action(
        admin_user_id,
        "support_close",
        target_type="support_ticket",
        target_id=str(ticket_id),
        target_label=f"Тикет #{ticket_id} — {ticket.get('subject') or 'без темы'}",
        ip=_get_client_ip(request) if request else None,
    )

    if body.notify and SUPPORT_BOT_TOKEN:
        try:
            await send_telegram_message(
                "<tg-emoji emoji-id='5429405838345265327'>🔓</tg-emoji> <b>Ваше обращение закрыто.</b>\n"
                "<blockquote><b>Если есть ещё вопросы - напишите /start, создадим новое.</b></blockquote>",
                chat_id=str(ticket["user_id"]),
                token=SUPPORT_BOT_TOKEN,
            )
        except Exception:
            pass

    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /support/stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def support_stats(
    admin_user_id: int = Depends(require_admin_session),
):
    open_count = await support_db.count_open_tickets()
    return {"openTickets": open_count}


# ---------------------------------------------------------------------------
# POST /support/upload-photo
# Загружает фото через SUPPORT_BOT_TOKEN, возвращает file_id
# Используется при прикреплении фото к ответу в саппорте ДО отправки
# ---------------------------------------------------------------------------

@router.post("/tickets/{ticket_id}/reply-with-photo")
async def reply_with_photo(
    ticket_id: int,
    file: UploadFile = File(...),
    text: str = Form(default=""),
    admin_user_id: int = Depends(require_admin_session),
):
    """Отправляет ответ с фото игроку — загрузка и отправка в один шаг при нажатии Send."""
    if not SUPPORT_BOT_TOKEN:
        raise HTTPException(status_code=503, detail="SUPPORT_BOT_TOKEN не настроен")

    ticket = await support_db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "Тикет не найден")
    if ticket["status"] == "closed":
        raise HTTPException(400, "Тикет закрыт")

    await _send_claim_greeting_if_needed(ticket, admin_user_id)

    import aiohttp
    content = await file.read()
    form_data = aiohttp.FormData()
    form_data.add_field("chat_id", str(ticket["user_id"]))
    form_data.add_field("caption", text.strip() or "", )
    form_data.add_field("parse_mode", "HTML")
    form_data.add_field(
        "photo", content,
        filename=file.filename or "photo.jpg",
        content_type=file.content_type or "image/jpeg",
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://api.telegram.org/bot{SUPPORT_BOT_TOKEN}/sendPhoto",
            data=form_data,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            result = await resp.json()

    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=f"Telegram: {result.get('description', 'ошибка отправки')}")

    sizes = result["result"]["photo"]
    file_id = sizes[-1]["file_id"]

    admin_name = await _get_admin_name(admin_user_id)
    await support_db.add_admin_message(ticket_id, admin_user_id, admin_name, text.strip(), file_id)
    return {"ok": True, "fileId": file_id}


async def _get_admin_name(admin_user_id: int) -> str:
    try:
        row = await db.pool.fetchrow(
            "SELECT first_name, username FROM admin_accounts WHERE user_id = $1",
            admin_user_id,
        )
        if row:
            return row["first_name"] or (f"@{row['username']}" if row["username"] else f"#{admin_user_id}")
    except Exception:
        pass
    return f"#{admin_user_id}"
