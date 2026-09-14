# -*- coding: utf-8 -*-
"""Хендлеры TikTok-заработка. Подключение: attach_tiktok_earn(dp)."""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message

from bot.funcs import tiktok_earn as tt

_album_tasks: dict[int, asyncio.Task] = {}
_album_added: dict[int, int] = {}


class _CollectingPhoto(Filter):
    async def __call__(self, message: Message) -> bool:
        if getattr(message.chat, "type", None) != ChatType.PRIVATE:
            return False
        if not message.from_user or not message.photo:
            return False
        return await tt.is_collecting(message.from_user.id)


class _WaitingNickOrLink(Filter):
    async def __call__(self, message: Message) -> bool:
        if getattr(message.chat, "type", None) != ChatType.PRIVATE:
            return False
        if not message.from_user or not message.text:
            return False
        uid = message.from_user.id
        return await tt.is_waiting_nick(uid) or await tt.is_waiting_link(uid)


class _CollectingNoise(Filter):
    """Текст или файл во время набора скринов - не перехватываем чужие режимы."""

    async def __call__(self, message: Message) -> bool:
        if getattr(message.chat, "type", None) != ChatType.PRIVATE:
            return False
        if not message.from_user:
            return False
        if message.photo:
            return False
        if not (message.text or message.document):
            return False
        if message.text and message.text.startswith("/"):
            return False
        return await tt.is_collecting(message.from_user.id)


class _IdleCommentsPhoto(Filter):
    """Фото на экране комментариев до кнопки - только подсказка, не доказательство."""

    async def __call__(self, message: Message) -> bool:
        if getattr(message.chat, "type", None) != ChatType.PRIVATE:
            return False
        if not message.from_user or not message.photo:
            return False
        if await tt.is_collecting(message.from_user.id):
            return False
        return await tt.is_comments_idle(message.from_user.id)


class _IdleVideosUrl(Filter):
    """Похожая на TikTok ссылка до кнопки - подсказка, не сдача."""

    async def __call__(self, message: Message) -> bool:
        if getattr(message.chat, "type", None) != ChatType.PRIVATE:
            return False
        if not message.from_user or not message.text:
            return False
        if message.text.startswith("/"):
            return False
        if await tt.is_waiting_link(message.from_user.id):
            return False
        if not await tt.is_videos_idle(message.from_user.id):
            return False
        return tt.looks_like_tiktok_url(message.text)

log = logging.getLogger("tiktok_earn")
tiktok_router = Router(name="tiktok_earn")
_attached = False


def _private(event) -> bool:
    chat = getattr(event, "message", None)
    if chat is None:
        chat = event
    src = getattr(chat, "chat", None) or getattr(event, "chat", None)
    return getattr(src, "type", None) == ChatType.PRIVATE


async def _edit_or_send(target: CallbackQuery | Message, text: str, markup) -> None:
    if isinstance(target, CallbackQuery):
        msg = target.message
        try:
            if msg and getattr(msg, "text", None):
                await msg.edit_text(text, reply_markup=markup, parse_mode="HTML")
                return
        except Exception:
            pass
        chat_id = target.from_user.id
        try:
            if msg:
                await msg.delete()
        except Exception:
            pass
        from main import bot1
        await bot1.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
        return
    await target.answer(text, reply_markup=markup, parse_mode="HTML")


async def show_hub(target: CallbackQuery | Message) -> None:
    await tt.ensure_schema()
    if getattr(getattr(target, "from_user", None), "id", None):
        await tt.clear_session(target.from_user.id)
    cfg = await tt.get_settings()
    await _edit_or_send(target, tt.text_hub(cfg), tt.hub_keyboard())


async def show_comments(target: CallbackQuery | Message, user_id: int) -> None:
    nicks = await tt.list_nicks(user_id)
    if not nicks:
        await tt.set_session(user_id, tt.MODE_NEED_NICK, {"after": "comments"})
        await _edit_or_send(target, tt.text_need_nick("comments"), tt.bind_keyboard())
        return
    cfg = await tt.get_settings()
    case = await tt.get_pending_comment_case(user_id)
    needed = int(cfg["photosRequired"])
    if case and case["complete"]:
        await tt.set_session(user_id, tt.MODE_COMMENT_DONE, {"caseId": case["id"]})
        count = case["received"]
        pending_complete = True
    elif case:
        await tt.set_session(user_id, tt.MODE_COMMENTS, {"caseId": case["id"]})
        count = case["received"]
        pending_complete = False
    else:
        await tt.set_session(user_id, tt.MODE_COMMENTS, {})
        count = 0
        pending_complete = False
    await _edit_or_send(
        target,
        tt.comments_screen_text(cfg, nicks, pending=pending_complete, count=count),
        tt.comments_keyboard(
            can_send=not pending_complete,
            count=count,
            needed=needed,
            waiting=False,
            complete=pending_complete,
        ),
    )


async def show_videos(target: CallbackQuery | Message, user_id: int) -> None:
    nicks = await tt.list_nicks(user_id)
    if not nicks:
        await tt.set_session(user_id, tt.MODE_NEED_NICK, {"after": "videos"})
        await _edit_or_send(target, tt.text_need_nick("videos"), tt.bind_keyboard())
        return
    cfg = await tt.get_settings()
    videos = await tt.list_user_videos(user_id)
    pending = any(v["status"] == "pending" for v in videos)
    await tt.set_session(user_id, tt.MODE_VIDEOS, {})
    await _edit_or_send(
        target,
        tt.videos_screen_text(cfg, nicks, videos),
        tt.videos_keyboard(videos, waiting=False, can_send=not pending),
    )


async def _nicks_origin(user_id: int) -> str:
    session = await tt.get_session(user_id)
    extra = session.get("extra") or {}
    origin = extra.get("origin") or extra.get("after") or session.get("mode") or ""
    if origin in {"comments", "photos", tt.MODE_COMMENTS, tt.MODE_WAIT_PHOTOS, "collect_photos", tt.MODE_COMMENT_DONE, tt.MODE_NEED_NICK}:
        if extra.get("after") == "videos":
            return "videos"
        return "comments"
    if origin in {"videos", tt.MODE_VIDEOS, tt.MODE_WAIT_LINK}:
        return "videos"
    return "hub"


async def show_nicks(target: CallbackQuery | Message, user_id: int) -> None:
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
    if session.get("mode") in {tt.MODE_WAIT_PHOTOS, "collect_photos", tt.MODE_COMMENTS, tt.MODE_COMMENT_DONE}:
        extra["origin"] = "comments"
        await tt.set_session(user_id, session.get("mode") or tt.MODE_COMMENTS, extra)
    elif session.get("mode") in {tt.MODE_WAIT_LINK, tt.MODE_VIDEOS}:
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
    after = extra.get("after") or extra.get("origin") or "comments"
    if session.get("mode") in {tt.MODE_WAIT_LINK, tt.MODE_VIDEOS}:
        after = "videos"
    if session.get("mode") in {tt.MODE_WAIT_PHOTOS, "collect_photos", tt.MODE_COMMENTS, tt.MODE_COMMENT_DONE}:
        after = "comments"
    await tt.set_session(
        callback.from_user.id,
        tt.MODE_WAIT_NICK,
        {"after": after},
    )
    await callback.answer()
    await _edit_or_send(callback, tt.text_ask_nick(), tt.bind_keyboard(waiting=True))


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
    await _edit_or_send(
        callback,
        "<b>Какое имя сменить?</b>",
        tt.nick_pick_keyboard(nicks),
    )


@tiktok_router.callback_query(F.data.startswith(tt.TT_NICK_PICK))
async def on_nick_pick(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    old = (callback.data or "").replace(tt.TT_NICK_PICK, "", 1)
    session = await tt.get_session(callback.from_user.id)
    extra = dict(session.get("extra") or {})
    extra["oldNick"] = old
    extra["after"] = extra.get("after") or extra.get("origin") or "comments"
    await tt.set_session(callback.from_user.id, tt.MODE_WAIT_NICK_EDIT, extra)
    await callback.answer()
    origin = extra.get("origin") or extra.get("after") or "hub"
    if origin == "photos":
        origin = "comments"
    await _edit_or_send(
        callback,
        f"<b>Новое имя вместо @{old}</b>\n\n{tt.text_ask_nick()}",
        tt.nicks_keyboard(
            await tt.list_nicks(callback.from_user.id),
            locked=False,
            origin=origin if origin in {"comments", "videos"} else "hub",
        ),
    )


@tiktok_router.callback_query(F.data == tt.TT_SEND_PHOTOS)
async def on_send_photos(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    user_id = callback.from_user.id
    if not await tt.list_nicks(user_id):
        await callback.answer(tt.text_nick_required_alert(), show_alert=True)
        await show_comments(callback, user_id)
        return
    case = await tt.get_pending_comment_case(user_id)
    if case and case["complete"]:
        await callback.answer("Серия уже на проверке")
        await show_comments(callback, user_id)
        return
    extra = {"caseId": case["id"]} if case else {}
    await tt.set_session(user_id, tt.MODE_WAIT_PHOTOS, extra)
    cfg = await tt.get_settings()
    count = int((case or {}).get("received") or 0)
    needed = int(cfg["photosRequired"])
    await callback.answer()
    await _edit_or_send(
        callback,
        tt.text_wait_photos(count, needed),
        tt.comments_keyboard(waiting=True, count=count, needed=needed),
    )


@tiktok_router.callback_query(F.data == tt.TT_SEND_LINK)
async def on_send_link(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    user_id = callback.from_user.id
    if not await tt.list_nicks(user_id):
        await callback.answer(tt.text_nick_required_alert(), show_alert=True)
        await show_videos(callback, user_id)
        return
    videos = await tt.list_user_videos(user_id)
    if any(v["status"] == "pending" for v in videos):
        await callback.answer("Ссылка уже на проверке")
        await show_videos(callback, user_id)
        return
    await tt.set_session(user_id, tt.MODE_WAIT_LINK, {"origin": "videos"})
    await callback.answer()
    await _edit_or_send(callback, tt.text_wait_link(), tt.videos_keyboard(videos, waiting=True, can_send=False))


@tiktok_router.callback_query(F.data == tt.TT_CANCEL_COLLECT)
async def on_cancel_collect(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    session = await tt.get_session(callback.from_user.id)
    extra = session.get("extra") or {}
    after = extra.get("after") or extra.get("origin") or ""
    mode = session.get("mode") or ""
    await callback.answer()
    if mode == tt.MODE_WAIT_LINK or after == "videos" or mode == tt.MODE_VIDEOS:
        await show_videos(callback, callback.from_user.id)
        return
    await show_comments(callback, callback.from_user.id)


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
    user_id = callback.from_user.id
    cfg = await tt.get_settings()
    nicks = await tt.list_nicks(user_id)
    pending_complete = bool(state.get("complete"))
    waiting = (await tt.session_mode(user_id)) in tt.PHOTO_WAIT_MODES
    await _edit_or_send(
        callback,
        tt.comments_screen_text(cfg, nicks, pending=pending_complete, count=state["count"]),
        tt.comments_keyboard(
            can_send=True,
            count=state["count"],
            needed=state["needed"],
            waiting=waiting and not pending_complete,
            complete=pending_complete,
        ),
    )


@tiktok_router.callback_query(F.data == tt.TT_SUBMIT_PHOTOS)
async def on_submit_photos(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    user_id = callback.from_user.id
    if not await tt.list_nicks(user_id):
        await tt.clear_session(user_id)
        await callback.answer(tt.text_nick_required_alert(), show_alert=True)
        await _edit_or_send(callback, tt.text_need_nick("comments"), tt.bind_keyboard())
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
    await message.answer(
        tt.text_photos_on_review(
            int(state.get("added") or 0),
            int(state["count"]),
            int(state["needed"]),
            nicks,
        ),
        reply_markup=tt.comments_keyboard(
            can_send=True,
            count=state["count"],
            needed=state["needed"],
            waiting=not bool(state.get("complete") or state.get("full")),
            complete=bool(state.get("complete") or state.get("full")),
        ),
        parse_mode="HTML",
    )


@tiktok_router.message(_IdleCommentsPhoto())
async def on_idle_comments_photo(message: Message) -> None:
    mode = await tt.session_mode(message.from_user.id)
    if mode == tt.MODE_NEED_NICK:
        await message.answer(tt.text_press_bind_nick(), parse_mode="HTML")
        return
    if mode == tt.MODE_COMMENT_DONE:
        await message.answer(
            "<b>Уже на проверке.</b>\n<i>Новые фото сейчас не нужны.</i>",
            parse_mode="HTML",
        )
        return
    await message.answer(tt.text_press_send_photos(), parse_mode="HTML")


@tiktok_router.message(_IdleVideosUrl())
async def on_idle_videos_url(message: Message) -> None:
    await message.answer(tt.text_press_send_link(), parse_mode="HTML")


@tiktok_router.message(_CollectingPhoto())
async def on_photo(message: Message) -> None:
    user_id = message.from_user.id
    if not await tt.list_nicks(user_id):
        await tt.clear_session(user_id)
        await message.answer(tt.text_need_nick("comments"), reply_markup=tt.bind_keyboard(), parse_mode="HTML")
        return
    photo = message.photo[-1]
    thumb_id = tt.pick_thumb_file_id(message.photo)
    hashes = await tt.download_and_hash(message.bot, photo.file_id)
    try:
        state = await tt.add_photo(user_id, photo.file_id, hashes, thumb_id)
    except ValueError as exc:
        await tt.clear_session(user_id)
        await message.answer(f"<b>{exc}</b>\n\n{tt.text_need_nick('comments')}", reply_markup=tt.bind_keyboard(), parse_mode="HTML")
        return
    if message.media_group_id:
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
                }
                await _send_collect_progress(message, latest)
            except asyncio.CancelledError:
                return

        _album_tasks[user_id] = asyncio.create_task(_flush())
        return
    await _send_collect_progress(message, state)


@tiktok_router.message(_CollectingNoise())
async def on_collect_noise(message: Message) -> None:
    cfg = await tt.get_settings()
    needed = int(cfg["photosRequired"])
    hint = "Нужно фото, не файл." if message.document else "Сейчас отправьте фото."
    case = await tt.get_pending_comment_case(message.from_user.id)
    count = int((case or {}).get("received") or 0)
    await message.answer(
        f"<b>{hint}</b>",
        reply_markup=tt.comments_keyboard(waiting=True, count=count, needed=needed),
        parse_mode="HTML",
    )


@tiktok_router.message(_WaitingNickOrLink())
async def on_text(message: Message) -> None:
    user_id = message.from_user.id
    if await tt.is_waiting_nick(user_id):
        session = await tt.get_session(user_id)
        try:
            if session.get("mode") == tt.MODE_WAIT_NICK_EDIT:
                old = (session.get("extra") or {}).get("oldNick") or ""
                nick = await tt.replace_nick(user_id, old, message.text or "")
            else:
                nick = await tt.add_nick(user_id, message.text or "")
        except ValueError as exc:
            await message.answer(f"<b>{exc}</b>", parse_mode="HTML")
            return
        after = (session.get("extra") or {}).get("after") or ""
        await tt.clear_session(user_id)
        if after == "videos":
            await show_videos(message, user_id)
            return
        await show_comments(message, user_id)
        return
    if await tt.is_waiting_link(user_id):
        try:
            await tt.submit_video(user_id, message.text or "")
        except ValueError as exc:
            await message.answer(f"<b>{exc}</b>", parse_mode="HTML")
            return
        await show_videos(message, user_id)


def attach_tiktok_earn(dp) -> None:
    global _attached
    if _attached:
        return
    dp.include_router(tiktok_router)
    _attached = True
