"""Отправка сообщений в Telegram (группа + тема)."""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from config import BOT_TOKEN

logger = logging.getLogger("cute-farm.telegram")


@dataclass
class TelegramSendResult:
    """Итог попытки отправки. ok=False не бросает исключение - вызывающий код
    сам решает, критично ли это (для рассылок - да, для fire-and-forget
    уведомлений - обычно нет)."""

    ok: bool
    category: str | None = None  # "blocked" | "chat_not_found" | "deactivated" | "rate_limited" | "other"
    error_code: int | None = None
    description: str | None = None


def _classify_error(error_code: int | None, description: str) -> str:
    desc = (description or "").lower()
    if error_code == 403 and "deactivated" in desc:
        return "deactivated"
    if error_code == 403:
        return "blocked"
    if error_code == 400 and ("chat not found" in desc or "user not found" in desc):
        return "chat_not_found"
    if error_code == 429:
        return "rate_limited"
    return "other"


def _webapp_button_markup(cta_text: str, cta_url: str) -> str:
    """Инлайн-кнопка с web_app - открывает вебапп прямо в Telegram, не во внешнем браузере.
    Работает только в личке с ботом (что и есть кейс рассылок - chat_id=user_id)."""
    return json.dumps({
        "inline_keyboard": [[{"text": cta_text, "web_app": {"url": cta_url}}]],
    })


def send_telegram_message_sync(
    text: str,
    *,
    chat_id: str,
    thread_id: int | None = None,
    token: str | None = None,
    cta_text: str | None = None,
    cta_url: str | None = None,
) -> TelegramSendResult:
    bot_token = token or BOT_TOKEN
    if not bot_token or not chat_id:
        return TelegramSendResult(ok=False, category="other", description="Missing bot token or chat_id")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if thread_id is not None:
        payload["message_thread_id"] = str(thread_id)
    if cta_text and cta_url:
        payload["reply_markup"] = _webapp_button_markup(cta_text, cta_url)
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            response.read()
        return TelegramSendResult(ok=True)
    except urllib.error.HTTPError as exc:
        error_code = exc.code
        description = str(exc)
        try:
            raw = exc.read()
            parsed = json.loads(raw) if raw else {}
            error_code = int(parsed.get("error_code", error_code))
            description = str(parsed.get("description", description))
        except Exception:
            pass
        category = _classify_error(error_code, description)
        logger.warning(
            "Telegram HTTP error (chat_id=%s): %s %s", chat_id, error_code, description
        )
        return TelegramSendResult(ok=False, category=category, error_code=error_code, description=description)
    except Exception as exc:
        logger.exception("Telegram send failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))


async def send_telegram_message(
    text: str,
    *,
    chat_id: str,
    thread_id: int | None = None,
    token: str | None = None,
    cta_text: str | None = None,
    cta_url: str | None = None,
) -> TelegramSendResult:
    try:
        return await asyncio.to_thread(
            send_telegram_message_sync,
            text,
            chat_id=chat_id,
            thread_id=thread_id,
            token=token,
            cta_text=cta_text,
            cta_url=cta_url,
        )
    except Exception as exc:
        logger.exception("Telegram send failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))
