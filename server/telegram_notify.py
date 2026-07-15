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
    file_id: str | None = None  # заполняется на успешный sendPhoto с сырыми байтами


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


def build_inline_keyboard(rows: list[list[dict]]) -> str | None:
    """rows: [[{"text": str, "url": str, "type": "url"|"web_app"}, ...], ...].
    Пустые/невалидные строки и кнопки без text/url молча пропускаются - вызывающий
    код (group_posts.py) уже провалидировал структуру при сохранении, здесь -
    последняя защита перед отправкой в Telegram. Возвращает JSON для
    reply_markup или None, если после фильтрации кнопок не осталось."""
    keyboard: list[list[dict]] = []
    for row in rows or []:
        buttons = []
        for btn in row or []:
            text = str((btn or {}).get("text") or "").strip()
            url = str((btn or {}).get("url") or "").strip()
            if not text or not url:
                continue
            if (btn or {}).get("type") == "web_app":
                buttons.append({"text": text, "web_app": {"url": url}})
            else:
                buttons.append({"text": text, "url": url})
        if buttons:
            keyboard.append(buttons)
    if not keyboard:
        return None
    return json.dumps({"inline_keyboard": keyboard})


def _webapp_button_markup(cta_text: str, cta_url: str) -> str | None:
    """Инлайн-кнопка с web_app - открывает вебапп прямо в Telegram, не во внешнем
    браузере. Работает только в личке с ботом (что и есть кейс DM-рассылок -
    chat_id=user_id)."""
    return build_inline_keyboard([[{"text": cta_text, "url": cta_url, "type": "web_app"}]])


def send_telegram_message_sync(
    text: str,
    *,
    chat_id: str,
    thread_id: int | None = None,
    token: str | None = None,
    cta_text: str | None = None,
    cta_url: str | None = None,
    buttons: list[list[dict]] | None = None,
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
    reply_markup = build_inline_keyboard(buttons) if buttons else None
    if reply_markup is None and cta_text and cta_url:
        reply_markup = _webapp_button_markup(cta_text, cta_url)
    if reply_markup:
        payload["reply_markup"] = reply_markup
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
    buttons: list[list[dict]] | None = None,
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
            buttons=buttons,
        )
    except Exception as exc:
        logger.exception("Telegram send failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))


async def send_telegram_photo_bytes(
    photo_bytes: bytes,
    *,
    chat_id: str,
    caption: str = "",
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
    token: str | None = None,
    buttons: list[list[dict]] | None = None,
) -> TelegramSendResult:
    """Первая отправка фото кампании - грузит бинарник в Telegram, возвращает
    file_id (в TelegramSendResult.file_id) для дальнейшего переиспользования
    без реаплоада, см. send_telegram_photo_by_file_id. Использует aiohttp, как
    уже существующий server/admin_routes.py::_upload_photo_to_telegram - здесь
    реальная загрузка файла, не просто форма, urllib для этого неудобен."""
    import aiohttp

    bot_token = token or BOT_TOKEN
    if not bot_token or not chat_id:
        return TelegramSendResult(ok=False, category="other", description="Missing bot token or chat_id")

    data = aiohttp.FormData()
    data.add_field("chat_id", chat_id)
    if caption:
        data.add_field("caption", caption)
        data.add_field("parse_mode", "HTML")
    reply_markup = build_inline_keyboard(buttons or [])
    if reply_markup:
        data.add_field("reply_markup", reply_markup)
    data.add_field("photo", photo_bytes, filename=filename, content_type=content_type)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                data=data,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                result = await resp.json()
    except Exception as exc:
        logger.exception("Telegram sendPhoto (bytes) failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))

    if not result.get("ok"):
        error_code = result.get("error_code")
        description = result.get("description", "")
        category = _classify_error(error_code, description)
        logger.warning("Telegram sendPhoto error (chat_id=%s): %s %s", chat_id, error_code, description)
        return TelegramSendResult(ok=False, category=category, error_code=error_code, description=description)

    sizes = result.get("result", {}).get("photo", [])
    file_id = sizes[-1]["file_id"] if sizes else None
    return TelegramSendResult(ok=True, file_id=file_id)


def send_telegram_photo_by_file_id_sync(
    file_id: str,
    *,
    chat_id: str,
    caption: str = "",
    token: str | None = None,
    buttons: list[list[dict]] | None = None,
) -> TelegramSendResult:
    """Повторные отправки того же фото - без реаплоада, обычный form-post как
    у send_telegram_message_sync (photo=file_id - это просто текстовое поле,
    не файл)."""
    bot_token = token or BOT_TOKEN
    if not bot_token or not chat_id:
        return TelegramSendResult(ok=False, category="other", description="Missing bot token or chat_id")

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": file_id}
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = "HTML"
    reply_markup = build_inline_keyboard(buttons or [])
    if reply_markup:
        payload["reply_markup"] = reply_markup
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            response.read()
        return TelegramSendResult(ok=True, file_id=file_id)
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
        logger.warning("Telegram sendPhoto error (chat_id=%s): %s %s", chat_id, error_code, description)
        return TelegramSendResult(ok=False, category=category, error_code=error_code, description=description)
    except Exception as exc:
        logger.exception("Telegram sendPhoto (file_id) failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))


async def send_telegram_photo_by_file_id(
    file_id: str,
    *,
    chat_id: str,
    caption: str = "",
    token: str | None = None,
    buttons: list[list[dict]] | None = None,
) -> TelegramSendResult:
    try:
        return await asyncio.to_thread(
            send_telegram_photo_by_file_id_sync,
            file_id,
            chat_id=chat_id,
            caption=caption,
            token=token,
            buttons=buttons,
        )
    except Exception as exc:
        logger.exception("Telegram sendPhoto (file_id) failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))
