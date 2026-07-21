# -*- coding: utf-8 -*-
"""Общий безопасный редактор сообщений для игр.

Причина: раньше игры (например «мины») редактировали доску сырым
``bot1.edit_message_text`` без обработки flood control. Telegram ограничивает
частоту правок одного и того же сообщения (~1 правка/сек в группах). При
быстрых тапах двух игроков правки вставали в очередь, и один вызов
``EditMessageText`` висел по 3 секунды - это и ощущалось как «лаги в кнопках».

Здесь собрана та же логика, что уже проверена в ``bot/funcs/kosti.py``:
  * дедупликация - если текст и клавиатура не изменились, правку НЕ шлём;
  * ``edit_message_reply_markup`` когда меняется только клавиатура (дешевле);
  * обработка flood control (TelegramRetryAfter / "flood control") с
    ограниченным числом ретраев и понятным уведомлением игроку.

Состояние (``_last_view`` для дедупа и id уведомления о задержке) хранится
в переданном dict игры, поэтому helper не тянет глобальных структур.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Optional

from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup

FLOOD_EDIT_MAX_RETRIES = 4
# Максимум, сколько ждём один flood-интервал перед ретраем. Ретрай без ожидания
# бессмыслен (Telegram вернёт ту же ошибку), а слишком долгое ожидание держит
# обработчик тапа - поэтому уважаем retry_after, но с потолком.
FLOOD_MAX_SLEEP_SEC = 8.0


def _bot():
    # Ленивый импорт, чтобы не ловить циклический импорт при загрузке модуля.
    from main import bot1
    return bot1


def _kb_signature(reply_markup: Optional[InlineKeyboardMarkup]) -> Optional[str]:
    if reply_markup is None:
        return None
    rows = []
    for row in (reply_markup.inline_keyboard or []):
        r = []
        for btn in row:
            r.append((
                getattr(btn, "text", None),
                getattr(btn, "callback_data", None),
                getattr(btn, "url", None),
                getattr(btn, "switch_inline_query", None),
                getattr(btn, "switch_inline_query_current_chat", None),
            ))
        rows.append(r)
    raw = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_flood_error(exc: Exception) -> bool:
    if isinstance(exc, TelegramRetryAfter):
        return True
    low = str(exc).lower()
    return (
        "flood control" in low
        or "too many requests" in low
        or "retry after" in low
        or "retry in" in low
    )


def _extract_retry_after(exc: Exception) -> int:
    ra = getattr(exc, "retry_after", None)
    if ra is not None:
        try:
            return max(1, int(float(ra)))
        except Exception:
            pass
    for pattern in (r"retry in (\d+)", r"retry after (\d+)"):
        m = re.search(pattern, str(exc), re.IGNORECASE)
        if m:
            return max(1, int(m.group(1)))
    return 5


def _format_flood_wait_text(seconds: int) -> str:
    s = max(1, int(seconds))
    return (
        "<tg-emoji emoji-id='5213452215527677338'>⏳</tg-emoji> "
        "<b>Telegram задерживает игру</b>\n"
        "Мессенджер временно ограничил обновления - "
        f"подождите <b>{s} сек.</b>\n"
        "<i>Игра продолжится автоматически…</i>"
    )


async def _clear_flood_notice(game: dict) -> None:
    notice_id = game.pop("_flood_notice_msg_id", None)
    chat_id = game.get("chat_id")
    if notice_id and chat_id:
        try:
            await _bot().delete_message(chat_id, notice_id)
        except Exception:
            pass


async def _show_flood_notice(
    game: dict,
    *,
    chat_id: int,
    message_id: int,
    wait_sec: int,
    reply_markup: Optional[InlineKeyboardMarkup],
    parse_mode: str,
    disable_web_page_preview: bool,
) -> None:
    notice_text = _format_flood_wait_text(wait_sec)
    try:
        await _bot().edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=notice_text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
        return
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
    except Exception as e:
        if not _is_flood_error(e):
            print(f"[SAFE_EDIT][flood notice edit] {e}")

    try:
        sent = await _bot().send_message(
            chat_id,
            notice_text,
            reply_to_message_id=message_id,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
        game["_flood_notice_msg_id"] = sent.message_id
    except Exception as e:
        print(f"[SAFE_EDIT][flood notice send] {e}")


async def safe_game_edit(
    game: dict,
    *,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> bool:
    """Редактирует сообщение игры с дедупликацией и обработкой flood control.

    Возвращает True, если правка отправлена, False - если пропущена (нет
    изменений) или не удалась после ретраев. Никогда не пробрасывает flood -
    ошибку наружу, чтобы не ронять обработчик тапа.
    """
    if not isinstance(game, dict):
        game = {}

    last = game.setdefault("_last_view", {"text": None, "kb_sig": None})
    kb_sig = _kb_signature(reply_markup)

    if last.get("text") == text and last.get("kb_sig") == kb_sig:
        return False

    text_changed = last.get("text") != text

    for attempt in range(1, FLOOD_EDIT_MAX_RETRIES + 1):
        try:
            if text_changed:
                await _bot().edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
            else:
                await _bot().edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup,
                )
            await _clear_flood_notice(game)
            last["text"] = text
            last["kb_sig"] = kb_sig
            return True
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                last["text"] = text
                last["kb_sig"] = kb_sig
                return False
            raise
        except Exception as e:
            if not _is_flood_error(e):
                raise

            wait_sec = _extract_retry_after(e)
            print(
                f"[SAFE_EDIT][flood] chat={chat_id} msg={message_id} "
                f"wait={wait_sec}s attempt={attempt}/{FLOOD_EDIT_MAX_RETRIES}"
            )
            await _show_flood_notice(
                game,
                chat_id=chat_id,
                message_id=message_id,
                wait_sec=wait_sec,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )

            if attempt >= FLOOD_EDIT_MAX_RETRIES:
                print(f"[SAFE_EDIT][flood] не удалось обновить после {attempt} попыток")
                return False

            # Уважаем flood-интервал (с потолком), иначе ретрай упрётся в ту же ошибку.
            await asyncio.sleep(min(float(wait_sec), FLOOD_MAX_SLEEP_SEC))

    return False
