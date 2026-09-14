# -*- coding: utf-8 -*-
"""Хендлеры TikTok-заработка. Подключение: attach_tiktok_earn(dp)."""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, ForceReply, Message

from bot.funcs import tiktok_earn as tt

_album_tasks: dict[int, asyncio.Task] = {}
_album_added: dict[int, int] = {}

log = logging.getLogger("tiktok_earn")
tiktok_router = Router(name="tiktok_earn")
_attached = False


def _private(event) -> bool:
    chat = getattr(event, "message", None)
    if chat is None:
        chat = event
    src = getattr(chat, "chat", None) or getattr(event, "chat", None)
    return getattr(src, "type", None) == ChatType.PRIVATE


def _prompt_ids(target: CallbackQuery | Message) -> tuple[int | None, int | None]:
    msg = target.message if isinstance(target, CallbackQuery) else target
    chat = getattr(msg, "chat", None)
    chat_id = getattr(chat, "id", None) if chat is not None else None
    mid = getattr(msg, "message_id", None)
    return (int(chat_id) if chat_id else None, int(mid) if mid else None)


def _chat_id_of(target: CallbackQuery | Message) -> int:
    if isinstance(target, CallbackQuery):
        msg = target.message
        if msg and getattr(msg, "chat", None):
            return int(msg.chat.id)
        return int(target.from_user.id)
    return int(target.chat.id)


async def _bot():
    from main import bot1
    return bot1


async def _delete_user_message(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def _delete_prompt(user_id: int) -> None:
    rec = tt.get_wait(user_id) or {}
    chat_id = rec.get("prompt_chat_id")
    mid = rec.get("prompt_message_id")
    if not (chat_id and mid):
        try:
            extra = ((await tt.get_session(user_id)).get("extra") or {})
            chat_id = extra.get("prompt_chat_id")
            mid = extra.get("prompt_message_id")
        except Exception:
            chat_id = chat_id
            mid = mid
    if not (chat_id and mid):
        return
    try:
        bot1 = await _bot()
        await bot1.delete_message(int(chat_id), int(mid))
    except Exception:
        pass


async def _edit_or_send(target: CallbackQuery | Message, text: str, markup) -> None:
    uid = getattr(getattr(target, "from_user", None), "id", None)
    if isinstance(target, CallbackQuery):
        msg = target.message
        try:
            if msg and getattr(msg, "text", None):
                await msg.edit_text(text, reply_markup=markup, parse_mode="HTML")
                return
        except Exception:
            pass
        try:
            if msg:
                await msg.delete()
        except Exception:
            pass
        bot1 = await _bot()
        await bot1.send_message(target.from_user.id, text, reply_markup=markup, parse_mode="HTML")
        return
    await target.answer(text, reply_markup=markup, parse_mode="HTML")


async def _send_force_reply(user_id: int, chat_id: int, text: str):
    bot1 = await _bot()
    return await bot1.send_message(
        chat_id,
        text,
        reply_markup=ForceReply(selective=True),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def _send_wait_prompt(
    target: CallbackQuery | Message,
    user_id: int,
    text: str,
    kind: str,
    mode: str,
    extra: dict,
) -> None:
    extra = dict(extra or {})
    chat_id = _chat_id_of(target)
    if isinstance(target, CallbackQuery) and target.message:
        try:
            await target.message.delete()
        except Exception:
            pass
    else:
        await _delete_prompt(user_id)
    prompt = await _send_force_reply(user_id, chat_id, text)
    await tt.arm_wait(
        user_id,
        kind,
        mode,
        extra,
        prompt_chat_id=prompt.chat.id,
        prompt_message_id=prompt.message_id,
    )


async def _reprompt(message: Message, user_id: int, text: str) -> None:
    rec = tt.get_wait(user_id) or {}
    session = await tt.get_session(user_id)
    extra = dict(session.get("extra") or rec)
    kind = rec.get("kind") or extra.get("kind") or tt.WAIT_NICK
    if kind == tt.WAIT_PHOTOS:
        mode = tt.MODE_WAIT_PHOTOS
    elif kind == tt.WAIT_LINK:
        mode = tt.MODE_WAIT_LINK
    elif kind == tt.WAIT_NICK_EDIT:
        mode = tt.MODE_WAIT_NICK_EDIT
    else:
        mode = tt.MODE_WAIT_NICK
    await _delete_user_message(message)
    await _delete_prompt(user_id)
    prompt = await _send_force_reply(user_id, message.chat.id, text)
    await tt.arm_wait(
        user_id,
        kind,
        mode,
        extra,
        prompt_chat_id=prompt.chat.id,
        prompt_message_id=prompt.message_id,
    )


async def _cancel_wait(message: Message, user_id: int) -> None:
    await _delete_user_message(message)
    await _delete_prompt(user_id)
    await tt.clear_session(user_id)
    cfg = await tt.get_settings()
    await message.answer(tt.text_hub(cfg), reply_markup=tt.hub_keyboard(), parse_mode="HTML")


async def _arm_nick_screen(
    target: CallbackQuery | Message,
    user_id: int,
    after: str,
    *,
    error: str = "",
    old_nick: str = "",
) -> None:
    extra = {"after": after}
    if old_nick:
        extra["oldNick"] = old_nick
        kind, mode = tt.WAIT_NICK_EDIT, tt.MODE_WAIT_NICK_EDIT
    else:
        kind, mode = tt.WAIT_NICK, tt.MODE_WAIT_NICK
    await _send_wait_prompt(
        target,
        user_id,
        tt.text_need_nick(after, error=error),
        kind,
        mode,
        extra,
    )


async def show_hub(target: CallbackQuery | Message) -> None:
    await tt.ensure_schema()
    if getattr(getattr(target, "from_user", None), "id", None):
        await tt.clear_session(target.from_user.id)
    cfg = await tt.get_settings()
    await _edit_or_send(target, tt.text_hub(cfg), tt.hub_keyboard())


async def show_comments(target: CallbackQuery | Message, user_id: int) -> None:
    nicks = await tt.list_nicks(user_id)
    if not nicks:
        await _arm_nick_screen(target, user_id, "comments")
        return
    cfg = await tt.get_settings()
    case = await tt.get_pending_comment_case(user_id)
    needed = int(cfg["photosRequired"])
    if case and case["complete"]:
        mode, extra = tt.MODE_COMMENT_DONE, {"caseId": case["id"], "after": "comments"}
        count = case["received"]
        pending_complete = True
        kind = None
    elif case:
        mode, extra = tt.MODE_WAIT_PHOTOS, {"caseId": case["id"], "after": "comments"}
        count = case["received"]
        pending_complete = False
        kind = tt.WAIT_PHOTOS
    else:
        mode, extra = tt.MODE_WAIT_PHOTOS, {"after": "comments"}
        count = 0
        pending_complete = False
        kind = tt.WAIT_PHOTOS
    text = tt.comments_screen_text(cfg, nicks, pending=pending_complete, count=count)
    markup = tt.comments_keyboard(
        can_send=not pending_complete,
        count=count,
        needed=needed,
        waiting=not pending_complete,
        complete=pending_complete,
    )
    if kind:
        await _send_wait_prompt(target, user_id, text, kind, mode, extra)
        return
    tt.clear_wait(user_id)
    await tt.set_session(user_id, mode, extra)
    await _edit_or_send(target, text, markup)


async def show_videos(target: CallbackQuery | Message, user_id: int) -> None:
    nicks = await tt.list_nicks(user_id)
    if not nicks:
        await _arm_nick_screen(target, user_id, "videos")
        return
    cfg = await tt.get_settings()
    videos = await tt.list_user_videos(user_id)
    pending = any(v["status"] == "pending" for v in videos)
    extra = {"after": "videos", "origin": "videos"}
    text = tt.videos_screen_text(cfg, nicks, videos)
    markup = tt.videos_keyboard(videos, waiting=not pending, can_send=not pending)
    if pending:
        tt.clear_wait(user_id)
        await tt.set_session(user_id, tt.MODE_VIDEOS, extra)
        await _edit_or_send(target, text, markup)
        return
    await _send_wait_prompt(target, user_id, text, tt.WAIT_LINK, tt.MODE_WAIT_LINK, extra)


async def _nicks_origin(user_id: int) -> str:
    session = await tt.get_session(user_id)
    extra = session.get("extra") or {}
    rec = tt.get_wait(user_id) or {}
    origin = extra.get("origin") or extra.get("after") or rec.get("after") or session.get("mode") or ""
    if origin in {
        "comments", "photos", tt.MODE_COMMENTS, tt.MODE_WAIT_PHOTOS, "collect_photos",
        tt.MODE_COMMENT_DONE, tt.MODE_NEED_NICK, tt.MODE_WAIT_NICK,
    }:
        if extra.get("after") == "videos" or rec.get("after") == "videos":
            return "videos"
        return "comments"
    if origin in {"videos", tt.MODE_VIDEOS, tt.MODE_WAIT_LINK}:
        return "videos"
    return "hub"


async def show_nicks(target: CallbackQuery | Message, user_id: int) -> None:
    tt.clear_wait(user_id)
    nicks = await tt.list_nicks(user_id)
    locked = await tt.has_pending(user_id)
    origin = await _nicks_origin(user_id)
    await _edit_or_send(
        target,
        tt.text_nicks(nicks, locked=locked),
        tt.nicks_keyboard(nicks, locked=locked, origin=origin),
    )


@tiktok_router.callback_query(F.data == tt.TT_HUB)
async def on_hub(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    await callback.answer()
    await show_hub(callback)


@tiktok_router.callback_query(F.data == tt.TT_COMMENTS)
async def on_comments(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    await callback.answer()
    await show_comments(callback, callback.from_user.id)


@tiktok_router.callback_query(F.data == tt.TT_VIDEOS)
async def on_videos(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    await callback.answer()
    await show_videos(callback, callback.from_user.id)


@tiktok_router.callback_query(F.data == tt.TT_NICKS)
async def on_nicks(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    user_id = callback.from_user.id
    session = await tt.get_session(user_id)
    extra = dict(session.get("extra") or {})
    rec = tt.get_wait(user_id) or {}
    if session.get("mode") in {tt.MODE_WAIT_PHOTOS, "collect_photos", tt.MODE_COMMENTS, tt.MODE_COMMENT_DONE} or rec.get("kind") == tt.WAIT_PHOTOS:
        extra["origin"] = "comments"
        await tt.set_session(user_id, session.get("mode") or tt.MODE_COMMENTS, extra)
    elif session.get("mode") in {tt.MODE_WAIT_LINK, tt.MODE_VIDEOS} or rec.get("kind") == tt.WAIT_LINK:
        extra["origin"] = "videos"
        await tt.set_session(user_id, session.get("mode") or tt.MODE_VIDEOS, extra)
    await callback.answer()
    await show_nicks(callback, user_id)


@tiktok_router.callback_query(F.data == tt.TT_NICK_ADD)
async def on_nick_add(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    session = await tt.get_session(callback.from_user.id)
    extra = dict(session.get("extra") or {})
    rec = tt.get_wait(callback.from_user.id) or {}
    after = extra.get("after") or extra.get("origin") or rec.get("after") or "comments"
    if session.get("mode") in {tt.MODE_WAIT_LINK, tt.MODE_VIDEOS}:
        after = "videos"
    if session.get("mode") in {tt.MODE_WAIT_PHOTOS, "collect_photos", tt.MODE_COMMENTS, tt.MODE_COMMENT_DONE}:
        after = "comments"
    await callback.answer()
    await _arm_nick_screen(callback, callback.from_user.id, after)


@tiktok_router.callback_query(F.data == tt.TT_NICK_EDIT)
async def on_nick_edit(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    nicks = await tt.list_nicks(callback.from_user.id)
    if not nicks:
        await callback.answer("Сначала напишите имя TikTok", show_alert=True)
        return
    await callback.answer()
    await _edit_or_send(callback, "<b>Какое имя сменить?</b>", tt.nick_pick_keyboard(nicks))


@tiktok_router.callback_query(F.data.startswith(tt.TT_NICK_PICK))
async def on_nick_pick(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    old = (callback.data or "").replace(tt.TT_NICK_PICK, "", 1)
    session = await tt.get_session(callback.from_user.id)
    extra = dict(session.get("extra") or {})
    after = extra.get("after") or extra.get("origin") or "comments"
    await callback.answer()
    await _arm_nick_screen(callback, callback.from_user.id, after, old_nick=old)


@tiktok_router.callback_query(F.data == tt.TT_SEND_PHOTOS)
async def on_send_photos(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    await callback.answer()
    await show_comments(callback, callback.from_user.id)


@tiktok_router.callback_query(F.data == tt.TT_SEND_LINK)
async def on_send_link(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    await callback.answer()
    await show_videos(callback, callback.from_user.id)


@tiktok_router.callback_query(F.data == tt.TT_CANCEL_COLLECT)
async def on_cancel_collect(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    await callback.answer()
    await show_hub(callback)


@tiktok_router.callback_query(F.data == tt.TT_DONE_WAIT)
async def on_done_wait(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    await callback.answer()
    await show_comments(callback, callback.from_user.id)


@tiktok_router.callback_query(F.data == tt.TT_UNDO_PHOTO)
async def on_undo_photo(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    try:
        state = await tt.undo_photo(callback.from_user.id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer("Убрали")
    await show_comments(callback, callback.from_user.id)


@tiktok_router.callback_query(F.data == tt.TT_SUBMIT_PHOTOS)
async def on_submit_photos(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    user_id = callback.from_user.id
    if not await tt.list_nicks(user_id):
        await callback.answer(tt.text_nick_required_alert(), show_alert=True)
        await show_comments(callback, user_id)
        return
    try:
        case = await tt.submit_comment_case(user_id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    if case.get("complete"):
        await callback.answer("Серия уже на проверке")
    else:
        await callback.answer(f"На проверке {case['received']} из {case['needed']}")
    await show_comments(callback, user_id)


@tiktok_router.callback_query(F.data.startswith(tt.TT_RECHECK))
async def on_recheck(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    raw = (callback.data or "").replace(tt.TT_RECHECK, "", 1)
    try:
        video_id = int(raw)
        await tt.request_recheck(callback.from_user.id, video_id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer()
    await show_videos(callback, callback.from_user.id)


async def _send_collect_progress(message: Message, state: dict) -> None:
    user_id = message.from_user.id
    nicks = await tt.list_nicks(user_id)
    complete = bool(state.get("complete") or state.get("full") or int(state["count"]) >= int(state["needed"]))
    text = tt.text_photos_on_review(
        int(state.get("added") or 0),
        int(state["count"]),
        int(state["needed"]),
        nicks,
    )
    extra = {"after": "comments", "caseId": state.get("caseId")}
    await _delete_user_message(message)
    await _delete_prompt(user_id)
    if complete:
        tt.clear_wait(user_id)
        await tt.set_session(user_id, tt.MODE_COMMENT_DONE, extra)
        await message.answer(
            text,
            reply_markup=tt.comments_keyboard(
                can_send=True,
                count=state["count"],
                needed=state["needed"],
                waiting=False,
                complete=True,
            ),
            parse_mode="HTML",
        )
        return
    prompt = await _send_force_reply(user_id, message.chat.id, text)
    await tt.arm_wait(
        user_id,
        tt.WAIT_PHOTOS,
        tt.MODE_WAIT_PHOTOS,
        extra,
        prompt_chat_id=prompt.chat.id,
        prompt_message_id=prompt.message_id,
    )


async def on_wait_text(message: Message) -> None:
    user_id = message.from_user.id
    if await tt.expire_wait_if_needed(user_id):
        return
    await tt.restore_wait_from_session(user_id)
    if await tt.expire_wait_if_needed(user_id):
        return
    rec = tt.get_wait(user_id) or {}
    if not rec:
        return
    kind = rec.get("kind") or ""
    raw = (message.text or "").strip()
    if tt.is_cancel_input(raw):
        await _cancel_wait(message, user_id)
        return
    if kind in {tt.WAIT_NICK, tt.WAIT_NICK_EDIT} or await tt.is_waiting_nick(user_id):
        session = await tt.get_session(user_id)
        extra = dict(session.get("extra") or rec)
        after = extra.get("after") or rec.get("after") or ""
        try:
            if kind == tt.WAIT_NICK_EDIT or session.get("mode") == tt.MODE_WAIT_NICK_EDIT:
                old = extra.get("oldNick") or rec.get("oldNick") or ""
                await tt.replace_nick(user_id, old, message.text or "")
            else:
                await tt.add_nick(user_id, message.text or "")
        except ValueError as exc:
            await _reprompt(message, user_id, tt.text_need_nick(after, error=str(exc)))
            return
        await _delete_user_message(message)
        await _delete_prompt(user_id)
        tt.clear_wait(user_id)
        if after == "videos":
            await show_videos(message, user_id)
            return
        await show_comments(message, user_id)
        return
    if kind == tt.WAIT_LINK or await tt.is_waiting_link(user_id):
        if not tt.looks_like_tiktok_url(raw):
            await _reprompt(message, user_id, tt.text_link_screen("Это не ссылка TikTok."))
            return
        try:
            await tt.submit_video(user_id, raw)
        except ValueError as exc:
            await _reprompt(message, user_id, tt.text_link_screen(str(exc)))
            return
        await _delete_user_message(message)
        await _delete_prompt(user_id)
        tt.clear_wait(user_id)
        await show_videos(message, user_id)


async def on_wait_photo(message: Message) -> None:
    user_id = message.from_user.id
    if await tt.expire_wait_if_needed(user_id):
        return
    await tt.restore_wait_from_session(user_id)
    if await tt.expire_wait_if_needed(user_id) or not tt.get_wait(user_id):
        return
    if not await tt.list_nicks(user_id):
        await _delete_user_message(message)
        await _arm_nick_screen(message, user_id, "comments")
        return
    photo = message.photo[-1]
    thumb_id = tt.pick_thumb_file_id(message.photo)
    hashes = await tt.download_and_hash(message.bot, photo.file_id)
    try:
        state = await tt.add_photo(user_id, photo.file_id, hashes, thumb_id)
    except ValueError as exc:
        await _reprompt(message, user_id, tt.text_need_nick("comments", error=str(exc)))
        return
    rec = tt.get_wait(user_id) or {}
    if not rec:
        extra = {"after": "comments"}
        await tt.arm_wait(user_id, tt.WAIT_PHOTOS, tt.MODE_WAIT_PHOTOS, extra)
    if message.media_group_id:
        tt.remember_album_group(user_id, message.media_group_id)
        prev = _album_tasks.pop(user_id, None)
        if prev:
            prev.cancel()
        _album_added[user_id] = _album_added.get(user_id, 0) + int(state.get("added") or 0)

        async def _flush() -> None:
            try:
                await asyncio.sleep(0.7)
                case = await tt.get_pending_comment_case(user_id)
                cfg = await tt.get_settings()
                added = _album_added.pop(user_id, 0)
                latest = {
                    "added": added,
                    "count": int((case or {}).get("received") or 0),
                    "needed": int((case or {}).get("needed") or cfg["photosRequired"]),
                    "complete": bool(case and case.get("complete")),
                    "caseId": (case or {}).get("id"),
                }
                await _send_collect_progress(message, latest)
            except asyncio.CancelledError:
                return

        _album_tasks[user_id] = asyncio.create_task(_flush())
        return
    await _send_collect_progress(message, state)


async def on_wait_noise(message: Message) -> None:
    user_id = message.from_user.id
    if await tt.expire_wait_if_needed(user_id):
        return
    await tt.restore_wait_from_session(user_id)
    if await tt.expire_wait_if_needed(user_id):
        return
    rec = tt.get_wait(user_id) or {}
    if not rec:
        return
    kind = rec.get("kind") or ""
    raw = (message.text or "").strip()
    if tt.is_cancel_input(raw):
        await _cancel_wait(message, user_id)
        return
    if kind in {tt.WAIT_NICK, tt.WAIT_NICK_EDIT}:
        await _reprompt(
            message,
            user_id,
            tt.text_need_nick(rec.get("after") or "", error="Нужно имя TikTok, не файл."),
        )
        return
    cfg = await tt.get_settings()
    needed = int(cfg["photosRequired"])
    hint = "Нужно фото, не файл." if message.document else "Сейчас отправьте фото."
    case = await tt.get_pending_comment_case(user_id)
    count = int((case or {}).get("received") or 0)
    await _reprompt(message, user_id, tt.text_photo_wait_error(hint, count, needed))


def attach_tiktok_earn(dp) -> None:
    global _attached
    if _attached:
        return
    # Как process_user_gift_recipient: хендлер на самом dp, фильтр по флагу awaiting.
    dp.message.register(on_wait_text, lambda m: tt.message_matches_wait_text(m))
    dp.message.register(on_wait_photo, lambda m: tt.message_matches_wait_photo(m))
    dp.message.register(on_wait_noise, lambda m: tt.message_matches_wait_noise(m))
    dp.include_router(tiktok_router)
    _attached = True
