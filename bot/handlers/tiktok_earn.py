# -*- coding: utf-8 -*-
"""Хендлеры TikTok-заработка. Подключение: attach_tiktok_earn(dp)."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message

from bot.funcs import tiktok_earn as tt


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
    await _edit_or_send(target, tt.text_hub(), tt.hub_keyboard())


async def show_comments(target: CallbackQuery | Message, user_id: int) -> None:
    nicks = await tt.list_nicks(user_id)
    if not nicks:
        await _edit_or_send(target, tt.text_need_nick(), tt.bind_keyboard())
        return
    cfg = await tt.get_settings()
    pending = await tt.has_pending(user_id)
    can_send = not pending
    extra = "\n\n<b>Проверяем аккаунт:</b> " + ", ".join(f"@{n}" for n in nicks)
    if pending:
        extra += "\n\n<i>Эта пачка ещё на проверке. Как ответим — можно прислать новую.</i>"
    await _edit_or_send(target, tt.text_comments(cfg) + extra, tt.comments_keyboard(can_send=can_send))


async def show_videos(target: CallbackQuery | Message, user_id: int) -> None:
    nicks = await tt.list_nicks(user_id)
    if not nicks:
        await _edit_or_send(target, tt.text_need_nick(), tt.bind_keyboard())
        return
    cfg = await tt.get_settings()
    videos = await tt.list_user_videos(user_id)
    extra = ""
    live = [v for v in videos if v["status"] == "live"]
    pending = [v for v in videos if v["status"] == "pending"]
    if pending:
        extra += "\n\n<i>Ссылка на проверке. Когда укажем просмотры — начислим куты за полные тысячи.</i>"
    if live:
        extra += "\n\n<b>Твои ролики</b>"
        for v in live[:5]:
            mark = " · ждём перепроверку" if v["recheckPending"] else f" · учтено {v['lastViews']}"
            extra += f"\n<code>{v['url']}</code>{mark}"
    await _edit_or_send(target, tt.text_videos(cfg) + extra, tt.videos_keyboard(videos))


async def show_nicks(target: CallbackQuery | Message, user_id: int) -> None:
    nicks = await tt.list_nicks(user_id)
    locked = await tt.has_pending(user_id)
    await _edit_or_send(target, tt.text_nicks(nicks, locked=locked), tt.nicks_keyboard(nicks, locked=locked))


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
    await callback.answer()
    await show_nicks(callback, callback.from_user.id)


@tiktok_router.callback_query(F.data == tt.TT_NICK_ADD)
async def on_nick_add(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    await tt.set_session(callback.from_user.id, "await_nick", {"after": "comments"})
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
    await tt.set_session(callback.from_user.id, "await_nick_edit", {"oldNick": old})
    await callback.answer()
    await _edit_or_send(
        callback,
        f"<b>Новый ник вместо @{old}</b>\n\n{tt.text_ask_nick()}",
        tt.nicks_keyboard(await tt.list_nicks(callback.from_user.id), locked=False),
    )


@tiktok_router.callback_query(F.data == tt.TT_SEND_PHOTOS)
async def on_send_photos(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    user_id = callback.from_user.id
    if not await tt.list_nicks(user_id):
        await tt.set_session(user_id, "await_nick", {"after": "photos"})
        await callback.answer(tt.text_nick_required_alert(), show_alert=True)
        await _edit_or_send(callback, tt.text_need_nick(), tt.bind_keyboard())
        return
    if await tt.has_pending(user_id):
        await callback.answer("Эта пачка ещё на проверке. Как ответим — можно прислать новую.", show_alert=True)
        return
    cfg = await tt.get_settings()
    await tt.set_session(user_id, "collect_photos", {"photos": []})
    await callback.answer()
    await _edit_or_send(
        callback,
        tt.collect_text(0, int(cfg["photosRequired"])),
        tt.collect_keyboard(0, int(cfg["photosRequired"])),
    )


@tiktok_router.callback_query(F.data == tt.TT_SEND_LINK)
async def on_send_link(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    user_id = callback.from_user.id
    if not await tt.list_nicks(user_id):
        await tt.set_session(user_id, "await_nick", {"after": "videos"})
        await callback.answer(tt.text_nick_required_alert(), show_alert=True)
        await _edit_or_send(callback, tt.text_need_nick(), tt.bind_keyboard())
        return
    await tt.set_session(user_id, "await_video_link", {})
    await callback.answer()
    await _edit_or_send(
        callback,
        "<b>Пришли ссылку на видео TikTok.</b>\n<i>tiktok.com или vm.tiktok.com</i>",
        tt.videos_keyboard(await tt.list_user_videos(user_id)),
    )


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
    await _edit_or_send(
        callback,
        tt.collect_text(state["count"], state["needed"]),
        tt.collect_keyboard(state["count"], state["needed"]),
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
        await _edit_or_send(callback, tt.text_need_nick(), tt.bind_keyboard())
        return
    session = await tt.get_session(user_id)
    photos = list((session.get("extra") or {}).get("photos") or [])
    try:
        await tt.submit_comment_case(user_id, photos)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer()
    await _edit_or_send(
        callback,
        "<b>Скриншоты на проверке.</b>\n<i>Новую пачку можно отправить после ответа.</i>",
        tt.hub_keyboard(),
    )


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
    await _edit_or_send(
        callback,
        "<b>Запрос ушёл.</b>\n<i>Админ впишет текущие просмотры — доплатим разницу.</i>",
        tt.videos_keyboard(await tt.list_user_videos(callback.from_user.id)),
    )


@tiktok_router.message(_CollectingPhoto())
async def on_photo(message: Message) -> None:
    user_id = message.from_user.id
    if not await tt.list_nicks(user_id):
        await tt.clear_session(user_id)
        await message.answer(tt.text_need_nick(), reply_markup=tt.bind_keyboard(), parse_mode="HTML")
        return
    photo = message.photo[-1]
    hashes = await tt.download_and_hash(message.bot, photo.file_id)
    try:
        state = await tt.add_photo(user_id, photo.file_id, hashes)
    except ValueError as exc:
        await tt.clear_session(user_id)
        await message.answer(f"<b>{exc}</b>\n\n{tt.text_need_nick()}", reply_markup=tt.bind_keyboard(), parse_mode="HTML")
        return
    await message.answer(
        tt.collect_text(state["count"], state["needed"]),
        reply_markup=tt.collect_keyboard(state["count"], state["needed"]),
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
        await tt.clear_session(user_id)
        await message.answer(f"<b>Ник @{nick} привязан.</b>\n<i>Теперь можно отправлять скриншоты и ссылки.</i>", parse_mode="HTML")
        if after == "photos":
            if await tt.has_pending(user_id):
                await show_comments(message, user_id)
                return
            cfg = await tt.get_settings()
            await tt.set_session(user_id, "collect_photos", {"photos": []})
            await message.answer(
                tt.collect_text(0, int(cfg["photosRequired"])),
                reply_markup=tt.collect_keyboard(0, int(cfg["photosRequired"])),
                parse_mode="HTML",
            )
            return
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
        await message.answer(
            "<b>Приняли.</b> <i>Видео на проверке. Когда укажем просмотры — начислим куты за полные тысячи.</i>",
            parse_mode="HTML",
            reply_markup=tt.hub_keyboard(),
        )


def attach_tiktok_earn(dp) -> None:
    global _attached
    if _attached:
        return
    dp.include_router(tiktok_router)
    _attached = True
