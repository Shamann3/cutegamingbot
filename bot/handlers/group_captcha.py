# -*- coding: utf-8 -*-
"""Показ и проверка групповой капчи. Подключение: attach_group_captcha(dp)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from aiogram import BaseMiddleware, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, ChatPermissions, Message, TelegramObject

from bot.funcs import group_captcha as gc

log = logging.getLogger("group_captcha")

captcha_router = Router(name="group_captcha")

_attached = False
_locks: Dict[Tuple[int, int], asyncio.Lock] = {}
_last_prompt: Dict[Tuple[int, int], float] = {}
_PROMPT_GAP = 8.0
_MESSAGE_RESEND_GAP = 1.1

_RESTRICTED = ChatPermissions(
    can_send_messages=False,
    can_send_media_messages=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)
_OPEN = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)


def _lock(chat_id: int, user_id: int) -> asyncio.Lock:
    key = (int(chat_id), int(user_id))
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


def _pool():
    from bot.db_create.db import db
    return getattr(db, "pool", None)


def _payload_of(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("payload")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        import json
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


async def _is_staff_muted(chat_id: int, user_id: int) -> bool:
    try:
        from bot.admins.mute import _is_muted_in_chat
        return bool(_is_muted_in_chat(int(chat_id), int(user_id)))
    except Exception:
        return False


async def _member_status(bot, chat_id: int, user_id: int) -> str:
    try:
        member = await bot.get_chat_member(int(chat_id), int(user_id))
        return str(getattr(member, "status", "") or "")
    except Exception:
        return ""


async def _maybe_restrict(bot, chat_id: int, user_id: int) -> None:
    status = await _member_status(bot, chat_id, user_id)
    if status in {"creator", "administrator"}:
        return
    try:
        await bot.restrict_chat_member(int(chat_id), int(user_id), permissions=_RESTRICTED)
    except (TelegramBadRequest, TelegramForbiddenError):
        return
    except Exception as e:
        log.debug("restrict skip: %s", e)


async def _maybe_unrestrict(bot, chat_id: int, user_id: int) -> None:
    if await _is_staff_muted(chat_id, user_id):
        return
    status = await _member_status(bot, chat_id, user_id)
    if status in {"creator", "administrator"}:
        return
    try:
        await bot.restrict_chat_member(int(chat_id), int(user_id), permissions=_OPEN)
    except (TelegramBadRequest, TelegramForbiddenError):
        return
    except Exception as e:
        log.debug("unrestrict skip: %s", e)


async def _delete_message(bot, chat_id: int, message_id: Optional[int]) -> None:
    if not message_id:
        return
    try:
        await bot.delete_message(int(chat_id), int(message_id))
    except Exception:
        return


async def _try_deliver(
    bot,
    *,
    chat_id: int,
    mid: Optional[int],
    text: str,
    markup,
    parse_mode: Optional[str],
    entities=None,
    thread_id: Optional[int] = None,
) -> Optional[int]:
    kwargs: Dict[str, Any] = {"reply_markup": markup}
    if entities:
        kwargs["entities"] = entities
    elif parse_mode:
        kwargs["parse_mode"] = parse_mode
    if mid:
        try:
            await bot.edit_message_text(
                text,
                chat_id=int(chat_id),
                message_id=int(mid),
                disable_web_page_preview=True,
                **kwargs,
            )
            return int(mid)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return int(mid)
        except TypeError:
            try:
                await bot.edit_message_text(
                    text,
                    chat_id=int(chat_id),
                    message_id=int(mid),
                    **kwargs,
                )
                return int(mid)
            except Exception:
                pass
        except Exception:
            pass
    send_kwargs = dict(kwargs)
    if thread_id:
        send_kwargs["message_thread_id"] = int(thread_id)
    try:
        msg = await bot.send_message(
            int(chat_id),
            text,
            disable_web_page_preview=True,
            **send_kwargs,
        )
        return int(msg.message_id)
    except TelegramBadRequest:
        if "message_thread_id" in send_kwargs:
            send_kwargs.pop("message_thread_id", None)
            msg = await bot.send_message(
                int(chat_id),
                text,
                disable_web_page_preview=True,
                **send_kwargs,
            )
            return int(msg.message_id)
        raise
    except TypeError:
        send_kwargs.pop("message_thread_id", None)
        try:
            msg = await bot.send_message(int(chat_id), text, **send_kwargs)
            return int(msg.message_id)
        except TypeError:
            msg = await bot.send_message(int(chat_id), text, **kwargs)
            return int(msg.message_id)


async def _send_or_edit(
    bot,
    *,
    chat_id: int,
    user: Any,
    row: Dict[str, Any],
    payload: Dict[str, Any],
    thread_id: Optional[int] = None,
) -> Optional[int]:
    payload = gc.hydrate_payload(payload)
    markup = gc.build_markup(int(row["id"]), int(chat_id), payload)
    mid = row.get("message_id")
    last_err: Optional[BaseException] = None
    # 1) entities + custom_emoji — так Telegram реально рисует премиум.
    # 2) HTML <tg-emoji> — тот же канон, что и в остальном боте.
    tries: List[Dict[str, Any]] = []
    try:
        plain, entities = gc.card_plain_and_entities(payload, user)
        if plain and entities:
            tries.append({"text": plain, "entities": entities, "parse_mode": None})
    except Exception as e:
        last_err = e
        log.warning("captcha entities build failed: %s", e)
    tries.append({"text": gc.card_html(payload, user), "entities": None, "parse_mode": "HTML"})
    for spec in tries:
        try:
            sent = await _try_deliver(
                bot,
                chat_id=chat_id,
                mid=mid,
                text=spec["text"],
                markup=markup,
                parse_mode=spec["parse_mode"],
                entities=spec["entities"],
                thread_id=thread_id,
            )
            if sent:
                return sent
        except Exception as e:
            last_err = e
            continue
    log.warning("captcha send failed chat=%s user=%s: %s", chat_id, getattr(user, "id", None), last_err)
    print(f"[CAPTCHA] SEND FAIL chat={chat_id} user={getattr(user, 'id', None)}: {last_err}")
    return None


async def maybe_prompt_captcha(
    bot,
    *,
    chat_id: int,
    user: Any,
    trigger: str,
    restrict: bool = False,
    thread_id: Optional[int] = None,
) -> bool:
    """Показать капчу, если человек ещё не проходил её в этой группе. True — карточка нужна."""
    uid = int(getattr(user, "id", 0) or 0)
    if uid <= 0 or getattr(user, "is_bot", False):
        return False
    pool = _pool()
    if pool is None:
        print("[CAPTCHA] skip: db pool is None")
        log.warning("captcha skip: db pool is None")
        return False

    if not await gc.is_chat_enabled(pool, chat_id):
        return False
    if await gc.has_passed(pool, chat_id, uid):
        return False

    key = (int(chat_id), uid)
    now = time.monotonic()
    if trigger != "message" and now - _last_prompt.get(key, 0.0) < _PROMPT_GAP:
        open_row = await gc.get_open_challenge(pool, chat_id, uid)
        if open_row and not gc.challenge_expired(open_row) and open_row.get("message_id"):
            return True
    if trigger == "message" and now - _last_prompt.get(key, 0.0) < _MESSAGE_RESEND_GAP:
        return True

    async with _lock(chat_id, uid):
        if await gc.has_passed(pool, chat_id, uid):
            return False
        if not await gc.is_chat_enabled(pool, chat_id):
            return False

        open_row = await gc.get_open_challenge(pool, chat_id, uid)
        if trigger == "message" and time.monotonic() - _last_prompt.get(key, 0.0) < _MESSAGE_RESEND_GAP:
            return True

        # Новое сообщение не прошедшего — новая карточка сразу под ним.
        # Старую убираем, чтобы чат не зарастал копиями.
        if trigger == "message" and open_row and open_row.get("message_id"):
            await _delete_message(bot, chat_id, open_row.get("message_id"))
        elif (
            trigger != "message"
            and open_row
            and not gc.challenge_expired(open_row)
            and open_row.get("message_id")
        ):
            _last_prompt[key] = time.monotonic()
            if restrict:
                await _maybe_restrict(bot, chat_id, uid)
            return True

        payload = gc.build_challenge()
        attempts = int((open_row or {}).get("attempts") or 0)
        row = await gc.save_challenge(
            pool,
            user_id=uid,
            chat_id=int(chat_id),
            payload=payload,
            trigger=trigger,
            message_id=None,
            attempts=attempts,
        )
        row["message_id"] = None
        mid = await _send_or_edit(
            bot,
            chat_id=chat_id,
            user=user,
            row=row,
            payload=payload,
            thread_id=thread_id,
        )
        if not mid:
            _last_prompt.pop(key, None)
            return False
        await gc.update_challenge(pool, int(row["id"]), message_id=mid)
        await gc.log_event(
            pool,
            user_id=uid,
            chat_id=int(chat_id),
            event="shown",
            variant=payload.get("variant"),
            meta={"trigger": trigger},
        )
        _last_prompt[key] = time.monotonic()
        print(f"[CAPTCHA] shown chat={chat_id} user={uid} mid={mid} trigger={trigger}")
        if restrict or trigger == "message":
            await _maybe_restrict(bot, chat_id, uid)
        return True


async def on_user_joined(bot, chat_id: int, user: Any, thread_id: Optional[int] = None) -> None:
    await maybe_prompt_captcha(
        bot,
        chat_id=int(chat_id),
        user=user,
        trigger="join",
        restrict=True,
        thread_id=thread_id,
    )


def _is_slash_command(message: Message) -> bool:
    text = (message.text or message.caption or "").lstrip()
    if text.startswith("/"):
        return True
    for ent in list(message.entities or []) + list(message.caption_entities or []):
        kind = str(getattr(ent, "type", "") or "")
        if kind in {"bot_command", "BotCommand"}:
            return True
    return False


async def _user_needs_captcha(chat_id: int, user_id: int) -> bool:
    pool = _pool()
    if pool is None:
        return False
    if not await gc.is_chat_enabled(pool, chat_id):
        return False
    if await gc.has_passed(pool, chat_id, user_id):
        return False
    return True


class CaptchaGateMiddleware(BaseMiddleware):
    """Пока капча не пройдена — в группе бот не отвечает на команды.
    Карточка уходит только на обычные сообщения."""

    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        message = event if isinstance(event, Message) else None
        if message is None:
            return await handler(event, data)
        chat = message.chat
        if not chat or chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
            return await handler(event, data)
        if message.new_chat_members or message.left_chat_member:
            return await handler(event, data)
        user = message.from_user
        if not user or user.is_bot:
            return await handler(event, data)
        try:
            needed = await _user_needs_captcha(int(chat.id), int(user.id))
        except Exception:
            log.exception("captcha gate check chat=%s user=%s", chat.id, user.id)
            return await handler(event, data)
        if not needed:
            return await handler(event, data)
        if _is_slash_command(message):
            return None
        try:
            bot = data.get("bot") or message.bot
            await maybe_prompt_captcha(
                bot,
                chat_id=int(chat.id),
                user=user,
                trigger="message",
                restrict=False,
                thread_id=getattr(message, "message_thread_id", None),
            )
        except Exception:
            log.exception("captcha prompt chat=%s user=%s", chat.id, user.id)
        return None


class CaptchaCallbackGateMiddleware(BaseMiddleware):
    """Кнопки игр и меню не работают, пока человек не прошёл капчу."""

    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        callback = event if isinstance(event, CallbackQuery) else None
        if callback is None:
            return await handler(event, data)
        raw = callback.data or ""
        if raw.startswith("gcA:") or raw.startswith("gcX:"):
            return await handler(event, data)
        message = callback.message
        chat = getattr(message, "chat", None) if message else None
        if not chat or chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
            return await handler(event, data)
        user = callback.from_user
        if not user or user.is_bot:
            return await handler(event, data)
        try:
            needed = await _user_needs_captcha(int(chat.id), int(user.id))
        except Exception:
            return await handler(event, data)
        if not needed:
            return await handler(event, data)
        try:
            await callback.answer()
        except Exception:
            pass
        return None


@captcha_router.callback_query(F.data.startswith("gcA:"))
async def on_captcha_answer(callback: CallbackQuery) -> None:
    parsed = gc.parse_answer_callback(callback.data or "")
    if not parsed:
        await callback.answer()
        return
    challenge_id, pick, mac = parsed
    if not gc.check_sign(mac, "a", challenge_id, pick):
        await callback.answer("Эта карточка уже устарела", show_alert=True)
        return

    pool = _pool()
    if pool is None:
        await callback.answer()
        return

    row = await gc.get_challenge(pool, challenge_id)
    if not row:
        await callback.answer("Эта карточка уже не действует")
        return

    user = callback.from_user
    uid = int(user.id)
    chat_id = int(row["chat_id"])
    if uid != int(row["user_id"]):
        await callback.answer("Эта капча предназначена для другого участника")
        return
    if callback.message and int(callback.message.chat.id) != chat_id:
        await callback.answer()
        return

    if not await gc.is_chat_enabled(pool, chat_id):
        await callback.answer("Капча в этой группе выключена")
        if callback.message:
            try:
                await callback.message.delete()
            except Exception:
                pass
        return

    if await gc.has_passed(pool, chat_id, uid):
        await callback.answer("Вы уже прошли капчу")
        if callback.message:
            try:
                await callback.message.delete()
            except Exception:
                pass
        await gc.delete_challenge(pool, challenge_id=challenge_id)
        return

    thread_id = getattr(callback.message, "message_thread_id", None) if callback.message else None
    if callback.message:
        row["message_id"] = int(callback.message.message_id)

    if gc.challenge_expired(row):
        payload = gc.build_challenge()
        await gc.update_challenge(pool, challenge_id, payload=payload, attempts=int(row.get("attempts") or 0))
        row["payload"] = payload
        mid = await _send_or_edit(
            callback.bot, chat_id=chat_id, user=user, row=row, payload=payload, thread_id=thread_id,
        )
        if mid:
            await gc.update_challenge(pool, challenge_id, message_id=mid)
        await callback.answer()
        return

    payload = gc.hydrate_payload(_payload_of(row))
    result, nxt = gc.is_correct_pick(payload, pick)
    attempts = int(row.get("attempts") or 0)

    if result == "next" and nxt is not None:
        await gc.update_challenge(pool, challenge_id, payload=nxt)
        await callback.answer()
        return

    if result == "pass":
        attempts = max(1, attempts)
        await gc.mark_passed(
            pool,
            user_id=uid,
            chat_id=chat_id,
            variant=payload.get("variant"),
            attempts=attempts,
            duration_ms=gc.duration_ms_of(row),
            trigger=row.get("trigger"),
        )
        await gc.delete_challenge(pool, challenge_id=challenge_id)
        await _maybe_unrestrict(callback.bot, chat_id, uid)
        if callback.message:
            try:
                await callback.message.delete()
            except Exception:
                pass
        await callback.answer()
        return

    # fail — тихо, новая лёгкая карточка
    attempts += 1
    await gc.log_event(
        pool,
        user_id=uid,
        chat_id=chat_id,
        event="fail",
        variant=payload.get("variant"),
        meta={"pick": pick, "attempts": attempts},
    )
    fresh = gc.build_challenge()
    await gc.update_challenge(pool, challenge_id, payload=fresh, attempts=attempts)
    row["attempts"] = attempts
    row["payload"] = fresh
    mid = await _send_or_edit(
        callback.bot, chat_id=chat_id, user=user, row=row, payload=fresh, thread_id=thread_id,
    )
    if mid:
        await gc.update_challenge(pool, challenge_id, message_id=mid)
    await callback.answer()


@captcha_router.callback_query(F.data.startswith("gcX:"))
async def on_captcha_disable(callback: CallbackQuery) -> None:
    parsed = gc.parse_disable_callback(callback.data or "")
    if not parsed:
        await callback.answer()
        return
    chat_id, mac = parsed
    if not gc.check_sign(mac, "x", chat_id):
        await callback.answer("Эта карточка уже устарела", show_alert=True)
        return
    if not callback.message or int(callback.message.chat.id) != int(chat_id):
        await callback.answer()
        return

    status = await _member_status(callback.bot, chat_id, int(callback.from_user.id))
    if status != "creator":
        await callback.answer(gc.DISABLE_ALERT, show_alert=True)
        return

    pool = _pool()
    if pool is None:
        await callback.answer()
        return
    await gc.disable_chat(pool, chat_id, int(callback.from_user.id))
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Капча в этой группе выключена")


def attach_group_captcha(dp) -> None:
    global _attached
    if _attached:
        return
    # outer: ловит каждое сообщение, даже если хендлер не сматчился,
    # и может остановить команды до остальных роутеров.
    dp.message.outer_middleware(CaptchaGateMiddleware())
    dp.callback_query.outer_middleware(CaptchaCallbackGateMiddleware())
    dp.include_router(captcha_router)
    _attached = True
    print("[CAPTCHA] групповая капча подключена")
