"""Отправка сообщений в Telegram (группа + тема)."""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from config import BOT_TOKEN

logger = logging.getLogger("cute-farm.telegram")


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
) -> None:
    bot_token = token or BOT_TOKEN
    if not bot_token or not chat_id:
        return

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
    with urllib.request.urlopen(request, timeout=12) as response:
        response.read()


async def send_telegram_message(
    text: str,
    *,
    chat_id: str,
    thread_id: int | None = None,
    token: str | None = None,
    cta_text: str | None = None,
    cta_url: str | None = None,
) -> None:
    try:
        await asyncio.to_thread(
            send_telegram_message_sync,
            text,
            chat_id=chat_id,
            thread_id=thread_id,
            token=token,
            cta_text=cta_text,
            cta_url=cta_url,
        )
    except urllib.error.HTTPError as exc:
        logger.warning("Telegram HTTP error: %s", exc)
    except Exception:
        logger.exception("Telegram send failed")
