"""Уведомления персоналу и владельцам через admin-бота (Telegram DM)."""

from __future__ import annotations

import asyncio
import logging

from config import ADMIN_BOT_TOKEN, owner_user_ids
from telegram_notify import send_telegram_message

logger = logging.getLogger("cute-farm.staff-notify")


async def _dm(user_id: int, text: str) -> None:
    try:
        await send_telegram_message(text, chat_id=str(user_id), token=ADMIN_BOT_TOKEN)
    except Exception:
        logger.exception("staff notify failed (user_id=%s)", user_id)


def notify_staff(user_id: int, text: str) -> None:
    """Fire-and-forget DM сотруднику через admin-бота."""
    if not ADMIN_BOT_TOKEN or not user_id:
        return
    asyncio.create_task(_dm(int(user_id), text))


def notify_owners(text: str, *, exclude: int | None = None) -> None:
    """Fire-and-forget DM всем владельцам (owner_user_ids)."""
    if not ADMIN_BOT_TOKEN:
        return
    for owner_id in owner_user_ids():
        if exclude is not None and owner_id == exclude:
            continue
        asyncio.create_task(_dm(int(owner_id), text))


async def build_salary_reminder() -> str | None:
    """Текст напоминания по зарплатам или None, если всё закрыто."""
    from admin_db import count_pending_salary_approvals, count_unpaid_salaries

    pending = await count_pending_salary_approvals()
    unpaid = await count_unpaid_salaries()
    if not pending and not unpaid:
        return None
    parts = ["<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>Напоминание по зарплатам</b>"]
    if pending:
        parts.append(f"<tg-emoji emoji-id='5472401690793614752'>🛍️</tg-emoji> {pending} <b>начислений ждут одобрения</b>")
    if unpaid:
        parts.append(f"<tg-emoji emoji-id='5472030678633684592'>💸</tg-emoji> {unpaid} <b>начислений ещё не выплачены</b>")
    return "\n".join(parts)


async def staff_salary_reminder_loop(stop_event) -> None:
    """Раз в день (~12:00 по времени сервера) напоминает владельцам про зарплаты."""
    if not ADMIN_BOT_TOKEN:
        return
    while not stop_event.is_set():
        try:
            await asyncio.sleep(3600)  # проверка раз в час
            import datetime
            if datetime.datetime.now().hour != 12:
                continue
            text = await build_salary_reminder()
            if text:
                notify_owners(text)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("staff salary reminder loop error")
