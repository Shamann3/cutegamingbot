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
_TG_TIMEOUT = 1.6
_DB_TIMEOUT = 0.8
_GATE_TIMEOUT = 0.7
_PROMPT_TIMEOUT = 2.0
_CLICK_DB_TIMEOUT = 0.55
_ACK_TIMEOUT = 1.1
_click_busy: set = set()
_creator_cache: Dict[int, Tuple[int, float]] = {}
_staff_cache: Dict[Tuple[int, int], Tuple[str, float]] = {}
_STAFF_TTL = 180.0
_CREATOR_TTL = 900.0


async def _ack(callback: CallbackQuery, text: str = "", *, alert: bool = False) -> None:
    """Telegram крутит спиннер, пока нет answer. Отвечаем сразу и коротко."""
    try:
        if text:
            await asyncio.wait_for(callback.answer(text, show_alert=alert), timeout=_ACK_TIMEOUT)
        else:
            await asyncio.wait_for(callback.answer(), timeout=_ACK_TIMEOUT)
    except Exception:
        return


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


def _remember_creator(chat_id: int, user_id: int) -> None:
    _creator_cache[int(chat_id)] = (int(user_id), time.monotonic())
    _staff_cache[(int(chat_id), int(user_id))] = ("creator", time.monotonic())


def _cached_creator(chat_id: int) -> Optional[int]:
    hit = _creator_cache.get(int(chat_id))
    if not hit:
        return None
    uid, ts = hit
    if time.monotonic() - ts > _CREATOR_TTL:
        _creator_cache.pop(int(chat_id), None)
        return None
    return int(uid)


async def _member_status(bot, chat_id: int, user_id: int) -> str:
    key = (int(chat_id), int(user_id))
    hit = _staff_cache.get(key)
    if hit and time.monotonic() - hit[1] <= _STAFF_TTL:
        return hit[0]
    try:
        member = await asyncio.wait_for(
            bot.get_chat_member(int(chat_id), int(user_id)),
            timeout=0.8,
        )
        status = str(getattr(member, "status", "") or "")
    except Exception:
        return ""
    _staff_cache[key] = (status, time.monotonic())
    if status == "creator":
        _remember_creator(chat_id, user_id)
    return status


async def _warm_creator(bot, chat_id: int) -> None:
    if _cached_creator(chat_id) is not None:
        return
    try:
        admins = await asyncio.wait_for(bot.get_chat_administrators(int(chat_id)), timeout=1.4)
    except Exception:
        return
    for item in admins or []:
        if str(getattr(item, "status", "") or "") != "creator":
            continue
        user = getattr(item, "user", None)
        uid = int(getattr(user, "id", 0) or 0)
        if uid:
            _remember_creator(chat_id, uid)
        return


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


async def _announce_passed(bot, chat_id: int, thread_id: Optional[int] = None) -> None:
    """В чат — ровно то сообщение, которое должно увидеть человек после успеха."""
    send_kwargs: Dict[str, Any] = {
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if thread_id:
        send_kwargs["message_thread_id"] = int(thread_id)
    try:
        await asyncio.wait_for(
            bot.send_message(int(chat_id), gc.PASS_HTML, **send_kwargs),
            timeout=_TG_TIMEOUT,
        )
        return
    except TypeError:
        send_kwargs.pop("message_thread_id", None)
        send_kwargs.pop("disable_web_page_preview", None)
    except Exception:
        send_kwargs = {"parse_mode": "HTML"}
    try:
        await asyncio.wait_for(
            bot.send_message(int(chat_id), gc.PASS_HTML, **send_kwargs),
            timeout=_TG_TIMEOUT,
        )
    except Exception:
        try:
            await asyncio.wait_for(
                bot.send_message(int(chat_id), gc.PASS_ALERT),
                timeout=_TG_TIMEOUT,
            )
        except Exception:
            return


async def _finish_pass(
    bot,
    *,
    chat_id: int,
    user_id: int,
    old_mid: Optional[int],
    thread_id: Optional[int],
) -> None:
    if old_mid:
        await _delete_message(bot, chat_id, old_mid)
    await _announce_passed(bot, chat_id, thread_id)
    await _maybe_unrestrict(bot, chat_id, user_id)


async def _write_fresh_captcha(
    bot,
    row: Dict[str, Any],
    payload: Dict[str, Any],
    chat_id: int,
    user: Any,
    thread_id: Optional[int],
    pool,
    challenge_id: int,
    attempts: Optional[int] = None,
) -> None:
    """Старую карточку убрать и написать новую — так ошибка сразу видна."""
    old_mid = row.get("message_id")
    if old_mid:
        await _delete_message(bot, chat_id, old_mid)
    row["message_id"] = None
    mid = await _send_or_edit(
        bot, chat_id=chat_id, user=user, row=row, payload=payload, thread_id=thread_id,
    )
    if mid:
        row["message_id"] = mid
        gc.patch_live(challenge_id, message_id=mid, payload=payload)
        if attempts is not None:
            gc.patch_live(challenge_id, attempts=attempts)
    uid = int(getattr(user, "id", 0) or row.get("user_id") or 0)
    if uid:
        _last_prompt[(int(chat_id), uid)] = time.monotonic()
    if pool:
        kwargs: Dict[str, Any] = {"payload": payload, "message_id": mid}
        if attempts is not None:
            kwargs["attempts"] = attempts
        try:
            await gc.update_challenge(pool, challenge_id, **kwargs)
        except Exception:
            log.exception("captcha reissue persist failed id=%s", challenge_id)


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
    _bg(_warm_creator(bot, int(chat_id)))
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


async def _try_text_captcha(bot, message: Message, chat, user) -> bool:
    """True — сообщение разобрали как ответ на капчу, дальше гейт молчит."""
    text = (message.text or message.caption or "").strip()
    if not text:
        return False
    chat_id = int(chat.id)
    uid = int(user.id)
    row = gc.peek_live_user(chat_id, uid)
    pool = _pool()
    if row is None and pool is not None:
        row = await _wait(gc.get_open_challenge(pool, chat_id, uid), _CLICK_DB_TIMEOUT, None)
        if row:
            gc.remember_live(row)
    if not row or gc.challenge_expired(row):
        return False
    payload = gc.hydrate_payload(_payload_of(row))
    result, pick, nxt = gc.match_chat_answer(payload, text)
    if result == "miss":
        return False
    challenge_id = int(row["id"])
    stored_chat_id = int(row.get("chat_id") or chat_id)
    thread_id = getattr(message, "message_thread_id", None)
    _bg(_delete_message(bot, chat_id, message.message_id))
    print(f"[CAPTCHA] text chat={chat_id} user={uid} pick={pick} result={result}")

    if result == "next" and nxt is not None:
        gc.patch_live(challenge_id, payload=nxt)
        row["payload"] = nxt
        _bg(_refresh_card(bot, row, nxt, chat_id, user, thread_id, pool, challenge_id))
        return True

    if result == "pass":
        gc.note_passed(chat_id, uid)
        gc.note_passed(stored_chat_id, uid)
        gc.forget_live(challenge_id)
        _bg(_finish_pass(
            bot,
            chat_id=chat_id,
            user_id=uid,
            old_mid=row.get("message_id"),
            thread_id=thread_id,
        ))
        if pool:
            async def _persist_pass() -> None:
                try:
                    await gc.mark_passed(
                        pool,
                        user_id=uid,
                        chat_id=chat_id,
                        variant=payload.get("variant"),
                        attempts=max(1, int(row.get("attempts") or 0)),
                        duration_ms=gc.duration_ms_of(row),
                        trigger="text",
                        meta=gc.event_meta(user, chat, extra={"pick": pick, "via": "text"}),
                    )
                except Exception:
                    log.exception("captcha text pass persist failed chat=%s user=%s", chat_id, uid)
                try:
                    await gc.delete_challenge(pool, challenge_id=challenge_id)
                except Exception:
                    log.exception("captcha challenge delete failed id=%s", challenge_id)
            _bg(_persist_pass())
        return True

    attempts = int(row.get("attempts") or 0) + 1
    fresh = gc.build_challenge()
    gc.patch_live(challenge_id, payload=fresh, attempts=attempts)
    row["attempts"] = attempts
    row["payload"] = fresh
    _bg(_write_fresh_captcha(bot, row, fresh, chat_id, user, thread_id, pool, challenge_id, attempts=attempts))
    if pool:
        _bg(gc.log_event(
            pool,
            user_id=uid,
            chat_id=chat_id,
            event="fail",
            variant=payload.get("variant"),
            meta=gc.event_meta(user, chat, extra={"pick": pick, "attempts": attempts, "via": "text"}),
        ))
    return True


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
        answered = await _try_text_captcha(bot, message, chat, user)
        if answered:
            return None
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
        cached = gc.cached_passed(int(chat.id), int(user.id))
        if cached is True:
            return await handler(event, data)
        if cached is False:
            needed = True
        else:
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
        await _ack(callback, gc.GATE_ALERT, alert=True)
        if bot:
            _bg(maybe_prompt_captcha(
                bot,
                chat_id=int(chat.id),
                user=user,
                trigger="callback",
                thread_id=getattr(message, "message_thread_id", None),
                chat=chat,
                extra_meta={"trigger": "callback", "callback": raw[:40]},
            ))
        return None


@captcha_router.callback_query(F.data.startswith("gcA:"))
async def on_captcha_answer(callback: CallbackQuery) -> None:
    parsed = gc.parse_answer_callback(callback.data or "")
    if not parsed:
        await _ack(callback)
        return
    challenge_id, pick, mac = parsed
    if not gc.check_sign(mac, "a", challenge_id, pick):
        await _ack(callback, "Эта карточка уже устарела", alert=True)
        return

    row = gc.peek_live(challenge_id)
    pool = _pool()
    if row is None and pool is not None:
        row = await _wait(gc.get_challenge(pool, challenge_id), _CLICK_DB_TIMEOUT, None)
    if not row:
        await _ack(callback, "Нажмите ещё раз", alert=True)
        return

    user = callback.from_user
    uid = int(user.id)
    if uid != int(row["user_id"]):
        await _ack(callback, "Эта капча предназначена для другого участника")
        return
    if challenge_id in _click_busy:
        await _ack(callback)
        return
    _click_busy.add(challenge_id)

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

    try:
        await _handle_captcha_pick(
            callback, row, challenge_id, pick, mac, uid, user, chat_id, stored_chat_id, pool,
        )
    finally:
        _click_busy.discard(challenge_id)


async def _handle_captcha_pick(
    callback, row, challenge_id, pick, mac, uid, user, chat_id, stored_chat_id, pool,
) -> None:
    if gc.cached_disabled(chat_id) is True:
        await _ack(callback, "Капча в этой группе выключена", alert=True)
        if callback.message:
            _bg(_delete_message(callback.bot, chat_id, callback.message.message_id))
        return

    if gc.cached_passed(chat_id, uid) is True or gc.cached_passed(stored_chat_id, uid) is True:
        gc.note_passed(chat_id, uid)
        await _ack(callback, "Вы уже прошли капчу", alert=True)
        if callback.message:
            _bg(_delete_message(callback.bot, chat_id, callback.message.message_id))
        if pool:
            _bg(gc.delete_challenge(pool, challenge_id=challenge_id))
        return

    thread_id = getattr(callback.message, "message_thread_id", None) if callback.message else None
    if callback.message:
        row["message_id"] = int(callback.message.message_id)

    if gc.challenge_expired(row):
        await _ack(callback)
        payload = gc.build_challenge()
        gc.patch_live(challenge_id, payload=payload)
        row["payload"] = payload
        _bg(_refresh_card(callback.bot, row, payload, chat_id, user, thread_id, pool, challenge_id))
        return

    payload = gc.hydrate_payload(_payload_of(row))
    result, nxt = gc.is_correct_pick(payload, pick)
    attempts = int(row.get("attempts") or 0)
    print(f"[CAPTCHA] click chat={chat_id} user={uid} pick={pick} result={result}")

    if result == "next" and nxt is not None:
        await _ack(callback, gc.NEXT_ALERT)
        gc.patch_live(challenge_id, payload=nxt)
        row["payload"] = nxt
        _bg(_refresh_card(callback.bot, row, nxt, chat_id, user, thread_id, pool, challenge_id))
        return

    if result == "pass":
        attempts = max(1, attempts)
        gc.note_passed(chat_id, uid)
        gc.note_passed(stored_chat_id, uid)
        gc.forget_live(challenge_id)
        await _ack(callback, gc.PASS_ALERT)
        chat = getattr(callback.message, "chat", None)
        old_mid = int(callback.message.message_id) if callback.message else row.get("message_id")
        _bg(_finish_pass(
            callback.bot,
            chat_id=chat_id,
            user_id=uid,
            old_mid=old_mid,
            thread_id=thread_id,
        ))
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
        return

    attempts += 1
    await _ack(callback)
    fresh = gc.build_challenge()
    gc.patch_live(challenge_id, payload=fresh, attempts=attempts)
    row["attempts"] = attempts
    row["payload"] = fresh
    _bg(_write_fresh_captcha(callback.bot, row, fresh, chat_id, user, thread_id, pool, challenge_id, attempts=attempts))
    if not pool:
        log.warning("captcha fail without db pool chat=%s user=%s", chat_id, uid)
        return

    async def _persist_fail() -> None:
        try:
            await gc.update_challenge(pool, challenge_id, payload=fresh, attempts=attempts)
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


async def _refresh_card(bot, row, payload, chat_id, user, thread_id, pool, challenge_id, attempts=None) -> None:
    mid = await _send_or_edit(
        bot, chat_id=chat_id, user=user, row=row, payload=payload, thread_id=thread_id,
    )
    if pool:
        kwargs = {"payload": payload, "message_id": mid}
        if attempts is not None:
            kwargs["attempts"] = attempts
        try:
            await gc.update_challenge(pool, challenge_id, **kwargs)
        except Exception:
            log.exception("captcha refresh persist failed id=%s", challenge_id)


@captcha_router.callback_query(F.data.startswith("gcX:"))
async def on_captcha_disable(callback: CallbackQuery) -> None:
    parsed = gc.parse_disable_callback(callback.data or "")
    if not parsed:
        await _ack(callback)
        return
    signed_chat_id, mac = parsed
    if not gc.check_sign(mac, "x", signed_chat_id):
        await _ack(callback, "Эта карточка уже устарела", alert=True)
        return
    chat_id = signed_chat_id
    if callback.message and getattr(callback.message, "chat", None):
        chat_id = int(callback.message.chat.id)

    uid = int(callback.from_user.id)
    owner = _cached_creator(chat_id) or _cached_creator(signed_chat_id)
    if owner is not None:
        is_owner = uid == int(owner)
    else:
        is_owner = (await _member_status(callback.bot, chat_id, uid)) == "creator"
    if not is_owner:
        await _ack(callback, gc.DISABLE_ALERT, alert=True)
        return

    pool = _pool()
    if pool is None:
        await _ack(callback)
        return
    await _ack(callback, "Капча в этой группе выключена", alert=True)

    async def _do_disable() -> None:
        try:
            await gc.disable_chat(pool, chat_id, uid)
        except Exception:
            log.exception("captcha disable failed chat=%s", chat_id)
        if int(chat_id) != int(signed_chat_id):
            try:
                await gc.disable_chat(pool, int(signed_chat_id), uid)
            except Exception:
                pass
        if callback.message:
            await _delete_message(callback.bot, chat_id, callback.message.message_id)

    _bg(_do_disable())


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
