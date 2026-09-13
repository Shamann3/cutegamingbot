"""Отправка сообщений в Telegram (группа + тема)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from config import BOT_TOKEN

logger = logging.getLogger("cute-farm.telegram")

_BOT_USERNAME = os.getenv("BOT_USERNAME", "CuteGamingBot").lstrip("@")
_APP_NAME = os.getenv("WEBAPP_SHORT_NAME", "cute").strip() or "cute"
_STARTAPP_HINTS = (
    ("farm", ("farm", "ферм")),
    ("market", ("market", "бирж", "рынок", "маркет")),
    ("shop", ("shop", "магазин", "шоп")),
    ("craft", ("craft", "крафт")),
    ("inventory", ("inventory", "инвентар")),
)


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
    message_id: int | None = None  # id отправленного сообщения (нужен для закрепа/удаления)


# Категории ошибок, при которых повторять действие бессмысленно: сообщения уже
# нет, либо у бота нет и не появится прав в этот момент. Вызывающий код
# (group_posts.py) закрывает такие записи трекинга, чтобы не долбить Telegram
# одной и той же обречённой операцией каждый цикл.
PERMANENT_FAILURE_CATEGORIES = frozenset(
    {"message_not_found", "cant_delete", "chat_not_found", "deactivated", "blocked"}
)


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
    # Ниже — категории для pin/unpin/delete. Проверяются после общих, чтобы не
    # менять классификацию, на которую уже опирается существующий код рассылок.
    if error_code == 400:
        if "not enough rights" in desc or "not enough permissions" in desc:
            return "no_rights"
        if "message to delete not found" in desc or "message to pin not found" in desc:
            return "message_not_found"
        if "message to unpin not found" in desc or "message identifier is not specified" in desc:
            return "message_not_found"
        if "message can't be deleted" in desc:
            return "cant_delete"
    return "other"


def _is_group_chat(chat_id: str | None) -> bool:
    try:
        return int(str(chat_id or "").strip()) < 0
    except (TypeError, ValueError):
        return False


def _mini_app_url(startapp: str = "") -> str:
    link = f"https://t.me/{_BOT_USERNAME}/{_APP_NAME}"
    start = (startapp or "").strip()
    if start:
        link += f"?startapp={start}"
    return link


def _infer_startapp(url: str, text: str = "") -> str:
    parsed = urlparse(url or "")
    qs = parse_qs(parsed.query)
    for key in ("startapp", "tgWebAppStartParam"):
        values = qs.get(key) or []
        if values and str(values[0]).strip():
            return str(values[0]).strip()
    blob = f"{parsed.path} {text}".lower()
    for startapp, hints in _STARTAPP_HINTS:
        if any(hint in blob for hint in hints):
            return startapp
    return ""


def _is_our_mini_app(url: str) -> bool:
    low = (url or "").strip().lower()
    if not low:
        return False
    if f"t.me/{_BOT_USERNAME.lower()}/" in low:
        return True
    return "cutegaming" in low


def group_safe_button_url(url: str, text: str = "", btn_type: str = "url") -> str:
    """В группах web_app не открывается — наш Mini App превращаем в t.me deep-link."""
    raw = (url or "").strip()
    if not raw:
        return raw
    as_web_app = (btn_type or "").strip() == "web_app"
    low = raw.lower()
    if ("t.me/" in low or low.startswith("tg:")) and not as_web_app:
        return raw
    if as_web_app or _is_our_mini_app(raw):
        return _mini_app_url(_infer_startapp(raw, text) or "farm")
    return raw


def build_inline_keyboard(
    rows: list[list[dict]],
    *,
    group_safe: bool = False,
) -> str | None:
    """rows: [[{"text": str, "url": str, "type": "url"|"web_app"}, ...], ...].
    Пустые/невалидные строки и кнопки без text/url молча пропускаются - вызывающий
    код (group_posts.py) уже провалидировал структуру при сохранении, здесь -
    последняя защита перед отправкой в Telegram. Возвращает JSON для
    reply_markup или None, если после фильтрации кнопок не осталось.

    group_safe=True: web_app → url t.me/bot/app (группы/каналы).
    group_safe=False: web_app остаётся web_app (личка, рассылки в PM).
    """
    keyboard: list[list[dict]] = []
    for row in rows or []:
        buttons = []
        for btn in row or []:
            text = str((btn or {}).get("text") or "").strip()
            url = str((btn or {}).get("url") or "").strip()
            btn_type = str((btn or {}).get("type") or "url").strip()
            if not text or not url:
                continue
            if group_safe:
                buttons.append({"text": text, "url": group_safe_button_url(url, text, btn_type)})
            elif btn_type == "web_app":
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


def _call_bot_api_sync(
    method: str,
    payload: dict[str, str],
    *,
    token: str | None = None,
    timeout: int = 12,
    chat_id: str | None = None,
) -> TelegramSendResult:
    """Один form-encoded POST в Bot API с единой обработкой ошибок.

    На успех вытаскивает message_id из result (у sendMessage/sendPhoto это
    объект сообщения, у pin/unpin/delete — просто true, поэтому проверяем тип).
    """
    bot_token = token or BOT_TOKEN
    if not bot_token:
        return TelegramSendResult(ok=False, category="other", description="Missing bot token or chat_id")

    encoded = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/{method}",
        data=encoded,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            result = json.loads(exc.read().decode())
        except Exception:
            return TelegramSendResult(ok=False, category="other", description=str(exc))
    except Exception as exc:
        logger.exception("Telegram %s failed (chat_id=%s)", method, chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))

    if not result.get("ok"):
        error_code = result.get("error_code")
        description = result.get("description", "")
        category = _classify_error(error_code, description)
        logger.warning("Telegram %s error (chat_id=%s): %s %s", method, chat_id, error_code, description)
        return TelegramSendResult(ok=False, category=category, error_code=error_code, description=description)

    raw = result.get("result")
    message_id = None
    if isinstance(raw, dict) and raw.get("message_id") is not None:
        message_id = int(raw["message_id"])
    return TelegramSendResult(ok=True, message_id=message_id)


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
    if not chat_id:
        return TelegramSendResult(ok=False, category="other", description="Missing bot token or chat_id")

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if thread_id is not None:
        payload["message_thread_id"] = str(thread_id)
    group_safe = _is_group_chat(chat_id)
    reply_markup = build_inline_keyboard(buttons, group_safe=group_safe) if buttons else None
    if reply_markup is None and cta_text and cta_url:
        if group_safe:
            reply_markup = build_inline_keyboard(
                [[{"text": cta_text, "url": cta_url, "type": "web_app"}]],
                group_safe=True,
            )
        else:
            reply_markup = _webapp_button_markup(cta_text, cta_url)
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _call_bot_api_sync("sendMessage", payload, token=token, chat_id=chat_id)


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
    reply_markup = build_inline_keyboard(buttons or [], group_safe=_is_group_chat(chat_id))
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

    message = result.get("result") or {}
    sizes = message.get("photo", [])
    file_id = sizes[-1]["file_id"] if sizes else None
    raw_message_id = message.get("message_id")
    return TelegramSendResult(
        ok=True,
        file_id=file_id,
        message_id=int(raw_message_id) if raw_message_id is not None else None,
    )


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
    if not chat_id:
        return TelegramSendResult(ok=False, category="other", description="Missing bot token or chat_id")

    payload = {"chat_id": chat_id, "photo": file_id}
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = "HTML"
    reply_markup = build_inline_keyboard(buttons or [], group_safe=_is_group_chat(chat_id))
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = _call_bot_api_sync("sendPhoto", payload, token=token, chat_id=chat_id)
    if result.ok:
        result.file_id = file_id
    return result


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


def pin_chat_message_sync(
    *,
    chat_id: str,
    message_id: int,
    disable_notification: bool = True,
    token: str | None = None,
) -> TelegramSendResult:
    if not chat_id or not message_id:
        return TelegramSendResult(ok=False, category="other", description="Missing chat_id or message_id")
    payload = {
        "chat_id": chat_id,
        "message_id": str(message_id),
        "disable_notification": "true" if disable_notification else "false",
    }
    return _call_bot_api_sync("pinChatMessage", payload, token=token, chat_id=chat_id)


async def pin_chat_message(
    *,
    chat_id: str,
    message_id: int,
    disable_notification: bool = True,
    token: str | None = None,
) -> TelegramSendResult:
    try:
        return await asyncio.to_thread(
            pin_chat_message_sync,
            chat_id=chat_id,
            message_id=message_id,
            disable_notification=disable_notification,
            token=token,
        )
    except Exception as exc:
        logger.exception("Telegram pin failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))


def unpin_chat_message_sync(
    *,
    chat_id: str,
    message_id: int | None = None,
    token: str | None = None,
) -> TelegramSendResult:
    if not chat_id:
        return TelegramSendResult(ok=False, category="other", description="Missing chat_id")
    payload = {"chat_id": chat_id}
    if message_id is not None:
        payload["message_id"] = str(message_id)
    return _call_bot_api_sync("unpinChatMessage", payload, token=token, chat_id=chat_id)


async def unpin_chat_message(
    *,
    chat_id: str,
    message_id: int | None = None,
    token: str | None = None,
) -> TelegramSendResult:
    try:
        return await asyncio.to_thread(
            unpin_chat_message_sync,
            chat_id=chat_id,
            message_id=message_id,
            token=token,
        )
    except Exception as exc:
        logger.exception("Telegram unpin failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))


def delete_message_sync(
    *,
    chat_id: str,
    message_id: int,
    token: str | None = None,
) -> TelegramSendResult:
    if not chat_id or not message_id:
        return TelegramSendResult(ok=False, category="other", description="Missing chat_id or message_id")
    payload = {"chat_id": chat_id, "message_id": str(message_id)}
    return _call_bot_api_sync("deleteMessage", payload, token=token, chat_id=chat_id)


async def delete_message(
    *,
    chat_id: str,
    message_id: int,
    token: str | None = None,
) -> TelegramSendResult:
    try:
        return await asyncio.to_thread(
            delete_message_sync,
            chat_id=chat_id,
            message_id=message_id,
            token=token,
        )
    except Exception as exc:
        logger.exception("Telegram delete failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))
