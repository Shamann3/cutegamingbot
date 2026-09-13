# -*- coding: utf-8 -*-
"""Показ и проверка групповой капчи. Подключение: attach_group_captcha(dp)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Tuple

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


def _telegram_needs_plain(err: BaseException) -> bool:
    text = str(err).upper()
    return any(token in text for token in (
        "DOCUMENT_INVALID",
        "CUSTOM_EMOJI",
        "BUTTON_TYPE_INVALID",
        "CAN'T PARSE",
        "CANT PARSE",
    ))


async def _send_or_edit(
    bot,
    *,
    chat_id: int,
    user: Any,
    row: Dict[str, Any],
    payload: Dict[str, Any],
) -> Optional[int]:
    rich_text = gc.card_html(payload, user)
    variants = (
        (rich_text, gc.build_markup(int(row["id"]), int(chat_id), payload, plain=False)),
        (gc.strip_tg_emoji(rich_text), gc.build_markup(int(row["id"]), int(chat_id), payload, plain=True)),
    )
    mid = row.get("message_id")
    last_err: Optional[BaseException] = None
    for text, markup in variants:
        if mid:
            try:
                await bot.edit_message_text(
                    text,
                    chat_id=int(chat_id),
                    message_id=int(mid),
                    parse_mode="HTML",
                    reply_markup=markup,
                    disable_web_page_preview=True,
                )
                return int(mid)
            except TelegramBadRequest as e:
                if "message is not modified" in str(e).lower():
                    return int(mid)
                last_err = e
                if not _telegram_needs_plain(e):
                    break
            except TypeError:
                try:
                    await bot.edit_message_text(
                        text,
                        chat_id=int(chat_id),
                        message_id=int(mid),
                        parse_mode="HTML",
                        reply_markup=markup,
                    )
                    return int(mid)
                except Exception as e:
                    last_err = e
                    if not _telegram_needs_plain(e):
                        break
            except Exception as e:
                last_err = e
                if not _telegram_needs_plain(e):
                    break
        try:
            msg = await bot.send_message(
                int(chat_id),
                text,
                parse_mode="HTML",
                reply_markup=markup,
                disable_web_page_preview=True,
            )
            return int(msg.message_id)
        except TypeError:
            try:
                msg = await bot.send_message(
                    int(chat_id),
                    text,
                    parse_mode="HTML",
                    reply_markup=markup,
                )
                return int(msg.message_id)
            except Exception as e:
                last_err = e
                if not _telegram_needs_plain(e):
                    break
        except Exception as e:
            last_err = e
            if not _telegram_needs_plain(e):
                break
    log.warning("captcha send failed chat=%s user=%s: %s", chat_id, getattr(user, "id", None), last_err)
    return None


async def maybe_prompt_captcha(
    bot,
    *,
    chat_id: int,
    user: Any,
    trigger: str,
    restrict: bool = False,
) -> bool:
    """Показать капчу, если человек ещё не проходил её в этой группе. True — карточка нужна."""
    uid = int(getattr(user, "id", 0) or 0)
    if uid <= 0 or getattr(user, "is_bot", False):
        return False
    pool = _pool()
    if pool is None:
        return False

    if not await gc.is_chat_enabled(pool, chat_id):
        return False
    if await gc.has_passed(pool, chat_id, uid):
        return False

    key = (int(chat_id), uid)
    now = time.monotonic()
    if now - _last_prompt.get(key, 0.0) < _PROMPT_GAP:
        open_row = await gc.get_open_challenge(pool, chat_id, uid)
        if open_row and not gc.challenge_expired(open_row) and open_row.get("message_id"):
            return True

    async with _lock(chat_id, uid):
        if await gc.has_passed(pool, chat_id, uid):
            return False
        if not await gc.is_chat_enabled(pool, chat_id):
            return False

        open_row = await gc.get_open_challenge(pool, chat_id, uid)
        if open_row and not gc.challenge_expired(open_row) and open_row.get("message_id"):
            _last_prompt[key] = now
            if restrict or trigger == "message":
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
        mid = await _send_or_edit(bot, chat_id=chat_id, user=user, row=row, payload=payload)
        if mid:
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
        if restrict:
            await _maybe_restrict(bot, chat_id, uid)
        return True


async def on_user_joined(bot, chat_id: int, user: Any) -> None:
    await maybe_prompt_captcha(bot, chat_id=int(chat_id), user=user, trigger="join", restrict=True)


class CaptchaMessageMiddleware(BaseMiddleware):
    """Старые участники без капчи получают карточку на первом сообщении."""

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
            bot = data.get("bot") or message.bot
            await maybe_prompt_captcha(
                bot,
                chat_id=int(chat.id),
                user=user,
                trigger="message",
                restrict=False,
            )
        except Exception as e:
            log.debug("captcha middleware: %s", e)
        return await handler(event, data)


@captcha_router.callback_query(F.data.startswith("gcA:"))
async def on_captcha_answer(callback: CallbackQuery) -> None:
    parsed = gc.parse_answer_callback(callback.data or "")
    if not parsed:
        await callback.answer()
        return
    challenge_id, pick, mac = parsed
    if not gc.check_sign(mac, "a", challenge_id, pick):
        await callback.answer("Карточка устарела", show_alert=True)
        return

    pool = _pool()
    if pool is None:
        await callback.answer()
        return

    row = await gc.get_challenge(pool, challenge_id)
    if not row:
        await callback.answer("Карточка уже не действует")
        return

    user = callback.from_user
    uid = int(user.id)
    chat_id = int(row["chat_id"])
    if uid != int(row["user_id"]):
        await callback.answer("Это не ваша капча")
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
        await callback.answer("Уже пройдено")
        if callback.message:
            try:
                await callback.message.delete()
            except Exception:
                pass
        await gc.delete_challenge(pool, challenge_id=challenge_id)
        return

    if gc.challenge_expired(row):
        payload = gc.build_challenge()
        await gc.update_challenge(pool, challenge_id, payload=payload, attempts=int(row.get("attempts") or 0))
        row["payload"] = payload
        await _send_or_edit(callback.bot, chat_id=chat_id, user=user, row=row, payload=payload)
        await callback.answer()
        return

    payload = _payload_of(row)
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
    await _send_or_edit(callback.bot, chat_id=chat_id, user=user, row=row, payload=fresh)
    await callback.answer()


@captcha_router.callback_query(F.data.startswith("gcX:"))
async def on_captcha_disable(callback: CallbackQuery) -> None:
    parsed = gc.parse_disable_callback(callback.data or "")
    if not parsed:
        await callback.answer()
        return
    chat_id, mac = parsed
    if not gc.check_sign(mac, "x", chat_id):
        await callback.answer("Карточка устарела", show_alert=True)
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
    dp.message.middleware(CaptchaMessageMiddleware())
    dp.include_router(captcha_router)
    _attached = True
    try:
        loop = asyncio.get_running_loop()

        async def _boot():
            pool = _pool()
            if pool:
                await gc.ensure_tables(pool)

        loop.create_task(_boot())
    except RuntimeError:
        pass
    print("[CAPTCHA] групповая капча подключена")
