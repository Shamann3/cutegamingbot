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

_OPEN = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)
_TG_TIMEOUT = 2.2
_DB_TIMEOUT = 1.4
_GATE_TIMEOUT = 1.6
_PROMPT_TIMEOUT = 3.0


async def _wait(coro, timeout: float, default=None):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return default
    except Exception:
        return default


def _lock(chat_id: int, user_id: int) -> asyncio.Lock:
    if len(_locks) > 256:
        dead = [key for key, item in _locks.items() if not item.locked()]
        for key in dead[:160]:
            _locks.pop(key, None)
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
        member = await asyncio.wait_for(
            bot.get_chat_member(int(chat_id), int(user_id)),
            timeout=1.8,
        )
        return str(getattr(member, "status", "") or "")
    except Exception:
        return ""


def _bg(coro) -> None:
    try:
        task = asyncio.create_task(coro)
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.done() else None)
    except Exception:
        pass


async def _maybe_unrestrict(bot, chat_id: int, user_id: int) -> None:
    if await _is_staff_muted(chat_id, user_id):
        return
    status = await _member_status(bot, chat_id, user_id)
    if status in {"creator", "administrator"}:
        return
    try:
        await asyncio.wait_for(
            bot.restrict_chat_member(int(chat_id), int(user_id), permissions=_OPEN),
            timeout=1.8,
        )
    except (TelegramBadRequest, TelegramForbiddenError, asyncio.TimeoutError):
        return
    except Exception as e:
        log.debug("unrestrict skip: %s", e)


async def _delete_message(bot, chat_id: int, message_id: Optional[int]) -> None:
    if not message_id:
        return
    try:
        await asyncio.wait_for(bot.delete_message(int(chat_id), int(message_id)), timeout=_TG_TIMEOUT)
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
            await asyncio.wait_for(
                bot.edit_message_text(
                    text,
                    chat_id=int(chat_id),
                    message_id=int(mid),
                    disable_web_page_preview=True,
                    **kwargs,
                ),
                timeout=_TG_TIMEOUT,
            )
            return int(mid)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return int(mid)
        except TypeError:
            try:
                await asyncio.wait_for(
                    bot.edit_message_text(
                        text,
                        chat_id=int(chat_id),
                        message_id=int(mid),
                        **kwargs,
                    ),
                    timeout=_TG_TIMEOUT,
                )
                return int(mid)
            except Exception:
                pass
        except (asyncio.TimeoutError, Exception):
            pass
    send_kwargs = dict(kwargs)
    if thread_id:
        send_kwargs["message_thread_id"] = int(thread_id)
    try:
        msg = await asyncio.wait_for(
            bot.send_message(
                int(chat_id),
                text,
                disable_web_page_preview=True,
                **send_kwargs,
            ),
            timeout=_TG_TIMEOUT,
        )
        return int(msg.message_id)
    except TelegramBadRequest:
        if "message_thread_id" in send_kwargs:
            send_kwargs.pop("message_thread_id", None)
            msg = await asyncio.wait_for(
                bot.send_message(
                    int(chat_id),
                    text,
                    disable_web_page_preview=True,
                    **send_kwargs,
                ),
                timeout=_TG_TIMEOUT,
            )
            return int(msg.message_id)
        raise
    except TypeError:
        send_kwargs.pop("message_thread_id", None)
        try:
            msg = await asyncio.wait_for(
                bot.send_message(int(chat_id), text, **send_kwargs),
                timeout=_TG_TIMEOUT,
            )
            return int(msg.message_id)
        except TypeError:
            msg = await asyncio.wait_for(
                bot.send_message(int(chat_id), text, **kwargs),
                timeout=_TG_TIMEOUT,
            )
            return int(msg.message_id)
    except asyncio.TimeoutError:
        return None


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


def _message_extra(message: Message) -> Dict[str, Any]:
    text = (message.text or message.caption or "").strip()
    extra: Dict[str, Any] = {
        "deleted_message_id": int(message.message_id),
        "deleted": True,
    }
    if text:
        extra["preview"] = text[:80]
    return extra


async def _log_blocked(pool, *, user: Any, chat: Any, chat_id: int, extra: Optional[Dict[str, Any]]) -> None:
    if pool is None:
        return
    try:
        await gc.log_event(
            pool,
            user_id=int(getattr(user, "id", 0) or 0),
            chat_id=int(chat_id),
            event="blocked",
            meta=gc.event_meta(user, chat, extra={"trigger": "message", **(extra or {})}),
        )
    except Exception:
        log.exception("captcha blocked log failed chat=%s user=%s", chat_id, getattr(user, "id", None))


async def maybe_prompt_captcha(
    bot,
    *,
    chat_id: int,
    user: Any,
    trigger: str,
    thread_id: Optional[int] = None,
    chat: Any = None,
    extra_meta: Optional[Dict[str, Any]] = None,
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

    if chat is not None:
        _bg(gc.seed_new_group(pool, chat, user, chat_id=int(chat_id)))
    else:
        _bg(gc.seed_new_group(pool, None, user, chat_id=int(chat_id)))

    if not await _wait(gc.user_needs_captcha(pool, chat_id, uid), _DB_TIMEOUT, False):
        return False

    key = (int(chat_id), uid)
    now = time.monotonic()
    if trigger != "message" and now - _last_prompt.get(key, 0.0) < _PROMPT_GAP:
        open_row = await _wait(gc.get_open_challenge(pool, chat_id, uid), _DB_TIMEOUT, None)
        if open_row and not gc.challenge_expired(open_row) and open_row.get("message_id"):
            return True
    if trigger == "message" and now - _last_prompt.get(key, 0.0) < _MESSAGE_RESEND_GAP:
        await _log_blocked(pool, user=user, chat=chat, chat_id=chat_id, extra=extra_meta)
        return True

    payload = None
    row = None
    open_row = None
    async with _lock(chat_id, uid):
        if not await _wait(gc.user_needs_captcha(pool, chat_id, uid), _DB_TIMEOUT, False):
            return False
        open_row = await _wait(gc.get_open_challenge(pool, chat_id, uid), _DB_TIMEOUT, None)
        if trigger == "message" and time.monotonic() - _last_prompt.get(key, 0.0) < _MESSAGE_RESEND_GAP:
            await _log_blocked(pool, user=user, chat=chat, chat_id=chat_id, extra=extra_meta)
            return True
        if trigger == "message" and open_row and open_row.get("message_id"):
            _bg(_delete_message(bot, chat_id, open_row.get("message_id")))
        elif (
            trigger != "message"
            and open_row
            and not gc.challenge_expired(open_row)
            and open_row.get("message_id")
        ):
            _last_prompt[key] = time.monotonic()
            return True

        payload = gc.build_challenge()
        attempts = int((open_row or {}).get("attempts") or 0)
        row = await _wait(
            gc.save_challenge(
                pool,
                user_id=uid,
                chat_id=int(chat_id),
                payload=payload,
                trigger=trigger,
                message_id=None,
                attempts=attempts,
            ),
            _DB_TIMEOUT,
            None,
        )
        if isinstance(row, dict):
            row["message_id"] = None

    if not row or not payload:
        return False
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
    await _wait(gc.update_challenge(pool, int(row["id"]), message_id=mid), _DB_TIMEOUT, None)
    _bg(gc.log_event(
        pool,
        user_id=uid,
        chat_id=int(chat_id),
        event="shown",
        variant=payload.get("variant"),
        meta=gc.event_meta(user, chat, extra={"trigger": trigger, **(extra_meta or {})}),
    ))
    _last_prompt[key] = time.monotonic()
    print(f"[CAPTCHA] shown chat={chat_id} user={uid} mid={mid} trigger={trigger}")
    return True


async def on_user_joined(bot, chat_id: int, user: Any, thread_id: Optional[int] = None) -> None:
    await maybe_prompt_captcha(
        bot,
        chat_id=int(chat_id),
        user=user,
        trigger="join",
        thread_id=thread_id,
    )


async def _user_needs_captcha(chat_id: int, user_id: int) -> bool:
    pool = _pool()
    if pool is None:
        return False
    return await gc.user_needs_captcha(pool, chat_id, user_id)


class CaptchaGateMiddleware(BaseMiddleware):
    """Пока капча не пройдена — команды бота молчат.
    Сообщение, на которое сработала капча, удаляется. Мута нет."""

    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        message = event if isinstance(event, Message) else None
        if message is None:
            return await handler(event, data)
        chat = message.chat
        if not chat or chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
            return await handler(event, data)
        if message.new_chat_members or message.left_chat_member:
            return await handler(event, data)
        if getattr(message, "migrate_to_chat_id", None) or getattr(message, "migrate_from_chat_id", None):
            return await handler(event, data)
        user = message.from_user
        if not user or user.is_bot:
            return await handler(event, data)
        try:
            needed = await asyncio.wait_for(
                _user_needs_captcha(int(chat.id), int(user.id)),
                timeout=_GATE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.warning("captcha gate timeout chat=%s user=%s", chat.id, user.id)
            return await handler(event, data)
        except Exception:
            log.exception("captcha gate check chat=%s user=%s", chat.id, user.id)
            return await handler(event, data)
        if not needed:
            return await handler(event, data)
        bot = data.get("bot") or message.bot
        extra = _message_extra(message)
        try:
            await asyncio.wait_for(
                maybe_prompt_captcha(
                    bot,
                    chat_id=int(chat.id),
                    user=user,
                    trigger="message",
                    thread_id=getattr(message, "message_thread_id", None),
                    chat=chat,
                    extra_meta=extra,
                ),
                timeout=_PROMPT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.warning("captcha prompt timeout chat=%s user=%s", chat.id, user.id)
        except Exception:
            log.exception("captcha prompt chat=%s user=%s", chat.id, user.id)
        await _delete_message(bot, int(chat.id), message.message_id)
        return None


class CaptchaCallbackGateMiddleware(BaseMiddleware):
    """Игровые кнопки закрыты до капчи. Справка, закрытие и ссылки наружу — нет."""

    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        callback = event if isinstance(event, CallbackQuery) else None
        if callback is None:
            return await handler(event, data)
        raw = callback.data or ""
        if gc.is_free_callback(raw):
            return await handler(event, data)
        message = callback.message
        chat = getattr(message, "chat", None) if message else None
        if not chat or chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
            return await handler(event, data)
        user = callback.from_user
        if not user or user.is_bot:
            return await handler(event, data)
        try:
            needed = await asyncio.wait_for(
                _user_needs_captcha(int(chat.id), int(user.id)),
                timeout=_GATE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return await handler(event, data)
        except Exception:
            return await handler(event, data)
        if not needed:
            return await handler(event, data)
        bot = data.get("bot") or getattr(callback, "bot", None)
        try:
            await callback.answer(gc.GATE_ALERT, show_alert=True)
        except Exception:
            pass
        if bot:
            try:
                await asyncio.wait_for(
                    maybe_prompt_captcha(
                        bot,
                        chat_id=int(chat.id),
                        user=user,
                        trigger="callback",
                        thread_id=getattr(message, "message_thread_id", None),
                        chat=chat,
                        extra_meta={"trigger": "callback", "callback": raw[:40]},
                    ),
                    timeout=_PROMPT_TIMEOUT,
                )
            except asyncio.TimeoutError:
                log.warning("captcha prompt timeout on callback chat=%s user=%s", chat.id, user.id)
            except Exception:
                log.exception("captcha prompt on blocked callback chat=%s user=%s", chat.id, user.id)
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

    row = gc.peek_live(challenge_id)
    pool = _pool()
    if row is None:
        if pool is None:
            await callback.answer()
            return
        try:
            row = await gc.get_challenge(pool, challenge_id)
        except Exception:
            log.exception("captcha get_challenge failed id=%s", challenge_id)
            await callback.answer("Не удалось проверить капчу, нажмите ещё раз", show_alert=True)
            return
    if not row:
        await callback.answer("Эта карточка уже не действует", show_alert=True)
        return

    user = callback.from_user
    uid = int(user.id)
    if uid != int(row["user_id"]):
        await callback.answer("Эта капча предназначена для другого участника")
        return

    msg_chat_id = None
    if callback.message and getattr(callback.message, "chat", None):
        try:
            msg_chat_id = int(callback.message.chat.id)
        except Exception:
            msg_chat_id = None
    stored_chat_id = int(row["chat_id"])
    chat_id = gc.resolve_click_chat_id(row, msg_chat_id)
    if chat_id != stored_chat_id:
        log.warning(
            "captcha chat id drift challenge=%s db=%s msg=%s user=%s",
            challenge_id, stored_chat_id, chat_id, uid,
        )
        gc.patch_live(challenge_id, chat_id=chat_id)
        row["chat_id"] = chat_id
        if pool:
            _bg(gc.remap_chat_id(pool, stored_chat_id, chat_id))
            _bg(gc.seed_new_group(pool, getattr(callback.message, "chat", None), user, chat_id=chat_id))

    if gc.cached_disabled(chat_id) is True:
        await callback.answer("Капча в этой группе выключена", show_alert=True)
        if callback.message:
            _bg(_delete_message(callback.bot, chat_id, callback.message.message_id))
        return

    if gc.cached_passed(chat_id, uid) is True or gc.cached_passed(stored_chat_id, uid) is True:
        gc.note_passed(chat_id, uid)
        await callback.answer("Вы уже прошли капчу", show_alert=True)
        if callback.message:
            _bg(_delete_message(callback.bot, chat_id, callback.message.message_id))
        if pool:
            _bg(gc.delete_challenge(pool, challenge_id=challenge_id))
        return

    thread_id = getattr(callback.message, "message_thread_id", None) if callback.message else None
    if callback.message:
        row["message_id"] = int(callback.message.message_id)

    if gc.challenge_expired(row):
        await callback.answer()
        payload = gc.build_challenge()
        gc.patch_live(challenge_id, payload=payload)
        row["payload"] = payload
        mid = await _send_or_edit(
            callback.bot, chat_id=chat_id, user=user, row=row, payload=payload, thread_id=thread_id,
        )
        if pool:
            _bg(gc.update_challenge(
                pool, challenge_id, payload=payload, attempts=int(row.get("attempts") or 0),
                message_id=mid,
            ))
        return

    payload = gc.hydrate_payload(_payload_of(row))
    result, nxt = gc.is_correct_pick(payload, pick)
    attempts = int(row.get("attempts") or 0)
    print(f"[CAPTCHA] click chat={chat_id} user={uid} pick={pick} result={result}")

    if result == "next" and nxt is not None:
        await callback.answer(gc.NEXT_ALERT)
        gc.patch_live(challenge_id, payload=nxt)
        row["payload"] = nxt
        mid = await _send_or_edit(
            callback.bot, chat_id=chat_id, user=user, row=row, payload=nxt, thread_id=thread_id,
        )
        if pool:
            _bg(gc.update_challenge(pool, challenge_id, payload=nxt, message_id=mid))
        return

    if result == "pass":
        attempts = max(1, attempts)
        gc.note_passed(chat_id, uid)
        gc.note_passed(stored_chat_id, uid)
        gc.forget_live(challenge_id)
        await callback.answer(gc.PASS_ALERT, show_alert=True)
        chat = getattr(callback.message, "chat", None)
        if pool:
            async def _persist_pass() -> None:
                try:
                    await gc.mark_passed(
                        pool,
                        user_id=uid,
                        chat_id=chat_id,
                        variant=payload.get("variant"),
                        attempts=attempts,
                        duration_ms=gc.duration_ms_of(row),
                        trigger=row.get("trigger"),
                        meta=gc.event_meta(user, chat),
                    )
                except Exception:
                    log.exception("captcha pass persist failed chat=%s user=%s", chat_id, uid)
                try:
                    await gc.delete_challenge(pool, challenge_id=challenge_id)
                except Exception:
                    log.exception("captcha challenge delete failed id=%s", challenge_id)
            _bg(_persist_pass())
        else:
            log.warning("captcha pass without db pool chat=%s user=%s", chat_id, uid)
        if callback.message:
            _bg(_delete_message(callback.bot, chat_id, callback.message.message_id))
        _bg(_maybe_unrestrict(callback.bot, chat_id, uid))
        return

    attempts += 1
    await callback.answer()
    fresh = gc.build_challenge()
    gc.patch_live(challenge_id, payload=fresh, attempts=attempts)
    row["attempts"] = attempts
    row["payload"] = fresh
    mid = await _send_or_edit(
        callback.bot, chat_id=chat_id, user=user, row=row, payload=fresh, thread_id=thread_id,
    )
    if not pool:
        log.warning("captcha fail without db pool chat=%s user=%s", chat_id, uid)
        return

    async def _persist_fail() -> None:
        try:
            await gc.update_challenge(pool, challenge_id, payload=fresh, attempts=attempts, message_id=mid)
        except Exception:
            log.exception("captcha fail update failed id=%s", challenge_id)
        try:
            await gc.log_event(
                pool,
                user_id=uid,
                chat_id=chat_id,
                event="fail",
                variant=payload.get("variant"),
                meta=gc.event_meta(
                    user,
                    getattr(callback.message, "chat", None),
                    extra={"pick": pick, "attempts": attempts},
                ),
            )
        except Exception:
            log.exception("captcha fail log failed chat=%s user=%s", chat_id, uid)

    _bg(_persist_fail())


@captcha_router.callback_query(F.data.startswith("gcX:"))
async def on_captcha_disable(callback: CallbackQuery) -> None:
    parsed = gc.parse_disable_callback(callback.data or "")
    if not parsed:
        await callback.answer()
        return
    signed_chat_id, mac = parsed
    if not gc.check_sign(mac, "x", signed_chat_id):
        await callback.answer("Эта карточка уже устарела", show_alert=True)
        return
    chat_id = signed_chat_id
    if callback.message and getattr(callback.message, "chat", None):
        chat_id = int(callback.message.chat.id)

    status = await _member_status(callback.bot, chat_id, int(callback.from_user.id))
    if status != "creator":
        await callback.answer(gc.DISABLE_ALERT, show_alert=True)
        return

    pool = _pool()
    if pool is None:
        await callback.answer()
        return
    await callback.answer("Капча в этой группе выключена", show_alert=True)
    await gc.disable_chat(pool, chat_id, int(callback.from_user.id))
    if int(chat_id) != int(signed_chat_id):
        try:
            await gc.disable_chat(pool, int(signed_chat_id), int(callback.from_user.id))
        except Exception:
            pass
    try:
        await callback.message.delete()
    except Exception:
        pass


@captcha_router.message(F.migrate_to_chat_id)
async def on_group_migrated(message: Message) -> None:
    old_id = int(message.chat.id)
    new_id = int(message.migrate_to_chat_id)
    pool = _pool()
    print(f"[CAPTCHA] group migrated {old_id} -> {new_id}")
    await gc.remap_chat_id(pool, old_id, new_id)


def start_cleanup_task(pool, bot):
    return gc.start_cleanup_task(pool, bot)


async def stop_cleanup_task():
    return await gc.stop_cleanup_task()


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
