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
    """Текст или файл во время набора скринов — не перехватываем чужие режимы."""

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
        await tt.set_session(user_id, "await_nick", {"after": "comments"})
        await _edit_or_send(target, tt.text_need_nick("comments"), tt.bind_keyboard())
        return
    cfg = await tt.get_settings()
    pending = await tt.has_pending(user_id)
    count = 0
    if pending:
        await tt.clear_session(user_id)
    else:
        session = await tt.get_session(user_id)
        extra = dict(session.get("extra") or {})
        photos = list(extra.get("photos") or []) if session.get("mode") == "collect_photos" else []
        await tt.set_session(user_id, "collect_photos", {"photos": photos})
        count = len(photos)
    needed = int(cfg["photosRequired"])
    await _edit_or_send(
        target,
        tt.comments_screen_text(cfg, nicks, pending=pending, count=count),
        tt.comments_keyboard(can_send=not pending, count=count, needed=needed),
    )


async def show_videos(target: CallbackQuery | Message, user_id: int) -> None:
    nicks = await tt.list_nicks(user_id)
    if not nicks:
        await tt.set_session(user_id, "await_nick", {"after": "videos"})
        await _edit_or_send(target, tt.text_need_nick("videos"), tt.bind_keyboard())
        return
    cfg = await tt.get_settings()
    videos = await tt.list_user_videos(user_id)
    if any(v["status"] == "pending" for v in videos):
        await tt.clear_session(user_id)
    else:
        await tt.set_session(user_id, "await_video_link", {})
    await _edit_or_send(
        target,
        tt.videos_screen_text(cfg, nicks, videos),
        tt.videos_keyboard(videos),
    )


async def _nicks_origin(user_id: int) -> str:
    session = await tt.get_session(user_id)
    extra = session.get("extra") or {}
    origin = extra.get("origin") or extra.get("after") or ""
    if origin in {"comments", "photos"}:
        return "comments"
    if origin == "videos":
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
    if session.get("mode") == "collect_photos":
        extra["origin"] = "comments"
        await tt.set_session(user_id, "collect_photos", extra)
    elif session.get("mode") == "await_video_link":
        extra["origin"] = "videos"
        await tt.set_session(user_id, "await_video_link", extra)
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
    if session.get("mode") == "await_video_link":
        after = "videos"
    if session.get("mode") == "collect_photos":
        after = "comments"
    await tt.set_session(
        callback.from_user.id,
        "await_nick",
        {"after": after, "photos": extra.get("photos") or []},
    )
    await callback.answer()
    await _edit_or_send(callback, tt.text_ask_nick(), tt.bind_keyboard())


@tiktok_router.callback_query(F.data == tt.TT_NICK_EDIT)
async def on_nick_edit(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    nicks = await tt.list_nicks(callback.from_user.id)
    if not nicks:
        await callback.answer("Сначала добавь ник", show_alert=True)
        return
    await callback.answer()
    await _edit_or_send(callback, "<b>Какой ник изменить?</b>", tt.nick_pick_keyboard(nicks))


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
    await tt.set_session(callback.from_user.id, "await_nick_edit", extra)
    await callback.answer()
    origin = extra.get("origin") or extra.get("after") or "hub"
    if origin == "photos":
        origin = "comments"
    await _edit_or_send(
        callback,
        f"<b>Новый ник вместо @{old}</b>\n\n{tt.text_ask_nick()}",
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
    await tt.clear_session(callback.from_user.id)
    await callback.answer("Набор отменён")
    await show_comments(callback, callback.from_user.id)


@tiktok_router.callback_query(F.data == tt.TT_UNDO_PHOTO)
async def on_undo_photo(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    state = await tt.undo_photo(callback.from_user.id)
    await callback.answer("Убрали последний кадр")
    user_id = callback.from_user.id
    cfg = await tt.get_settings()
    nicks = await tt.list_nicks(user_id)
    await _edit_or_send(
        callback,
        tt.comments_screen_text(cfg, nicks, pending=False, count=state["count"]),
        tt.comments_keyboard(can_send=True, count=state["count"], needed=state["needed"]),
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
    session = await tt.get_session(user_id)
    photos = list((session.get("extra") or {}).get("photos") or [])
    try:
        await tt.submit_comment_case(user_id, photos)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer()
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
    cfg = await tt.get_settings()
    nicks = await tt.list_nicks(user_id)
    await message.answer(
        tt.comments_screen_text(cfg, nicks, pending=False, count=state["count"]),
        reply_markup=tt.comments_keyboard(
            can_send=True, count=state["count"], needed=state["needed"]
        ),
        parse_mode="HTML",
    )


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

        async def _flush() -> None:
            try:
                await asyncio.sleep(0.7)
                session = await tt.get_session(user_id)
                photos = list((session.get("extra") or {}).get("photos") or [])
                cfg = await tt.get_settings()
                latest = {"count": len(photos), "needed": int(cfg["photosRequired"])}
                await _send_collect_progress(message, latest)
            except asyncio.CancelledError:
                return

        _album_tasks[user_id] = asyncio.create_task(_flush())
        return
    await _send_collect_progress(message, state)


@tiktok_router.message(_CollectingNoise())
async def on_collect_noise(message: Message) -> None:
    session = await tt.get_session(message.from_user.id)
    photos = list((session.get("extra") or {}).get("photos") or [])
    cfg = await tt.get_settings()
    needed = int(cfg["photosRequired"])
    hint = "Пришли скрин как фото, не как файл." if message.document else "Сейчас жду скриншоты. Текст не приму."
    nicks = await tt.list_nicks(message.from_user.id)
    await message.answer(
        f"<b>{hint}</b>\n{tt.comments_screen_text(cfg, nicks, pending=False, count=len(photos))}",
        reply_markup=tt.comments_keyboard(can_send=True, count=len(photos), needed=needed),
        parse_mode="HTML",
    )


@tiktok_router.message(_WaitingNickOrLink())
async def on_text(message: Message) -> None:
    user_id = message.from_user.id
    if await tt.is_waiting_nick(user_id):
        session = await tt.get_session(user_id)
        try:
            if session.get("mode") == "await_nick_edit":
                old = (session.get("extra") or {}).get("oldNick") or ""
                nick = await tt.replace_nick(user_id, old, message.text or "")
            else:
                nick = await tt.add_nick(user_id, message.text or "")
        except ValueError as exc:
            await message.answer(f"<b>{exc}</b>", parse_mode="HTML")
            return
        after = (session.get("extra") or {}).get("after") or ""
        kept = list((session.get("extra") or {}).get("photos") or [])
        await tt.clear_session(user_id)
        await message.answer(f"<b>Ник @{nick} привязан.</b>\n<b>Продолжаем с того же направления.</b>", parse_mode="HTML")
        if after == "videos":
            await show_videos(message, user_id)
            return
        if kept:
            await tt.set_session(user_id, "collect_photos", {"photos": kept})
        await show_comments(message, user_id)
        return
    if await tt.is_waiting_link(user_id):
        try:
            await tt.submit_video(user_id, message.text or "")
        except ValueError as exc:
            await message.answer(f"<b>{exc}</b>", parse_mode="HTML")
            return
        await message.answer(
            "<b>Приняли.</b> <b>Видео на проверке. Когда укажем просмотры - начислим куты за полные тысячи.</b>",
            parse_mode="HTML",
        )
        await show_videos(message, user_id)


def attach_tiktok_earn(dp) -> None:
    global _attached
    if _attached:
        return
    dp.include_router(tiktok_router)
    _attached = True
