# -*- coding: utf-8 -*-
"""Хендлеры TikTok-заработка. Подключение: attach_tiktok_earn(dp)."""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message

from bot.funcs import tiktok_earn as tt

_album_tasks: dict[int, asyncio.Task] = {}
_album_added: dict[int, int] = {}
_album_msgs: dict[int, list[Message]] = {}
_photo_locks: dict[int, asyncio.Lock] = {}

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


async def _edit_or_send(target: CallbackQuery | Message, text: str, markup) -> Message | None:
    if isinstance(target, CallbackQuery):
        msg = target.message
        try:
            if msg and getattr(msg, "text", None) is not None:
                await msg.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
                return msg
        except Exception:
            pass
        try:
            if msg:
                await msg.delete()
        except Exception:
            pass
        bot1 = await _bot()
        return await bot1.send_message(
            target.from_user.id,
            text,
            reply_markup=markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    return await target.answer(
        text,
        reply_markup=markup,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def _arm_wait_on_message(
    user_id: int,
    message: Message | None,
    kind: str,
    mode: str,
    extra: dict,
) -> None:
    chat_id = getattr(getattr(message, "chat", None), "id", None) if message else None
    mid = getattr(message, "message_id", None) if message else None
    await tt.arm_wait(
        user_id,
        kind,
        mode,
        extra,
        prompt_chat_id=int(chat_id) if chat_id else None,
        prompt_message_id=int(mid) if mid else None,
    )


async def _send_wait_prompt(
    target: CallbackQuery | Message,
    user_id: int,
    text: str,
    kind: str,
    mode: str,
    extra: dict,
    markup,
) -> None:
    extra = dict(extra or {})
    sent = await _edit_or_send(target, text, markup)
    await _arm_wait_on_message(user_id, sent, kind, mode, extra)


async def _reprompt(message: Message, user_id: int, text: str, markup=None) -> None:
    rec = tt.get_wait(user_id) or {}
    session = await tt.get_session(user_id)
    extra = dict(session.get("extra") or rec)
    kind = rec.get("kind") or extra.get("kind") or tt.WAIT_NICK
    if kind == tt.WAIT_PHOTOS:
        mode = tt.MODE_WAIT_PHOTOS
    elif kind == tt.WAIT_TITLE:
        mode = tt.MODE_WAIT_TITLE
    elif kind == tt.WAIT_LINK:
        mode = tt.MODE_WAIT_LINK
    elif kind == tt.WAIT_NICK_EDIT:
        mode = tt.MODE_WAIT_NICK_EDIT
    else:
        mode = tt.MODE_WAIT_NICK
    await _delete_user_message(message)
    await _delete_prompt(user_id)
    bot1 = await _bot()
    prompt = await bot1.send_message(
        message.chat.id,
        text,
        reply_markup=markup or tt.bind_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
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
    nicks = await tt.list_nicks(user_id)
    back = "nicks" if nicks else "hub"
    await _send_wait_prompt(
        target,
        user_id,
        tt.text_need_nick(after, error=error),
        kind,
        mode,
        extra,
        tt.nick_wait_keyboard(back=back),
    )


async def show_hub(target: CallbackQuery | Message) -> None:
    await tt.ensure_schema()
    user_id = getattr(getattr(target, "from_user", None), "id", None)
    has_nicks = False
    if user_id:
        await tt.clear_session(user_id)
        has_nicks = bool(await tt.list_nicks(user_id))
    cfg = await tt.get_settings()
    await _edit_or_send(target, tt.text_hub(cfg, has_nicks=has_nicks), tt.hub_keyboard())


async def show_comments(target: CallbackQuery | Message, user_id: int, notice: str = "") -> None:
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
    extra["origin"] = "comments"
    latest = None if case else await tt.get_latest_comment_case(user_id)
    text = tt.comments_screen_text(
        cfg, nicks, pending=pending_complete, count=count, notice=notice, latest=latest,
    )
    markup = tt.comments_keyboard(
        can_send=not pending_complete,
        count=count,
        needed=needed,
        waiting=not pending_complete,
        complete=pending_complete,
    )
    sent = await _edit_or_send(target, text, markup)
    if kind:
        await _arm_wait_on_message(user_id, sent, kind, mode, extra)
        return
    tt.clear_wait(user_id)
    await tt.set_session(user_id, mode, extra)


async def show_videos(target: CallbackQuery | Message, user_id: int, notice: str = "") -> None:
    nicks = await tt.list_nicks(user_id)
    if not nicks:
        await _arm_nick_screen(target, user_id, "videos")
        return
    cfg = await tt.get_settings()
    videos = await tt.list_user_videos(user_id)
    pending = any(v["status"] == "pending" for v in videos)
    extra = {"after": "videos", "origin": "videos"}
    text = tt.videos_screen_text(cfg, nicks, videos, notice=notice)
    markup = tt.videos_keyboard(videos, waiting=not pending, can_send=not pending)
    sent = await _edit_or_send(target, text, markup)
    if pending:
        tt.clear_wait(user_id)
        await tt.set_session(user_id, tt.MODE_VIDEOS, extra)
        return
    await _arm_wait_on_message(user_id, sent, tt.WAIT_TITLE, tt.MODE_WAIT_TITLE, extra)


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
    if origin in {"videos", tt.MODE_VIDEOS, tt.MODE_WAIT_LINK, tt.MODE_WAIT_TITLE, "mine", "my_videos"}:
        return "videos" if origin in {"videos", tt.MODE_VIDEOS, tt.MODE_WAIT_LINK, tt.MODE_WAIT_TITLE} else "mine"
    return "hub"


async def show_nicks(target: CallbackQuery | Message, user_id: int) -> None:
    tt.clear_wait(user_id)
    nicks = await tt.list_nicks(user_id)
    locked = await tt.has_pending(user_id)
    origin = await _nicks_origin(user_id)
    await tt.set_session(user_id, tt.MODE_NEED_NICK if not nicks else "nicks", {"origin": origin, "after": origin})
    await _edit_or_send(
        target,
        tt.text_nicks(nicks, locked=locked),
        tt.nicks_keyboard(nicks, locked=locked, origin=origin),
    )


async def show_my_videos(target: CallbackQuery | Message, user_id: int, page: int = 0, notice: str = "") -> None:
    tt.clear_wait(user_id)
    videos = await tt.list_user_videos(user_id)
    page, _pages = tt._video_pages(len(videos), page)
    await tt.set_session(user_id, "my_videos", {"origin": "mine", "after": "mine", "videoPage": page})
    text = tt.text_my_videos(videos, page)
    if notice:
        text = f"{notice}\n\n{text}"
    await _edit_or_send(target, text, tt.my_videos_keyboard(videos, page=page))


async def show_video_card(target: CallbackQuery | Message, user_id: int, video_id: int, notice: str = "") -> None:
    tt.clear_wait(user_id)
    item = await tt.get_user_video(user_id, video_id)
    session = await tt.get_session(user_id)
    page = int((session.get("extra") or {}).get("videoPage") or 0)
    if not item:
        await show_my_videos(target, user_id, page)
        return
    await tt.set_session(user_id, "my_videos", {"origin": "mine", "after": "mine", "videoPage": page, "videoId": video_id})
    text = tt.text_video_card(item)
    if notice:
        text = f"{notice}\n\n{text}"
    await _edit_or_send(target, text, tt.video_card_keyboard(item, page=page))


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


@tiktok_router.callback_query(F.data == tt.TT_MY_VIDEOS)
async def on_my_videos(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    await callback.answer()
    await show_my_videos(callback, callback.from_user.id, 0)


@tiktok_router.callback_query(F.data.startswith(tt.TT_VIDEO_PAGE))
async def on_video_page(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    raw = (callback.data or "").replace(tt.TT_VIDEO_PAGE, "", 1)
    try:
        page = int(raw)
    except ValueError:
        page = 0
    await callback.answer()
    await show_my_videos(callback, callback.from_user.id, page)


@tiktok_router.callback_query(F.data.startswith(tt.TT_VIDEO_OPEN))
async def on_video_open(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    raw = (callback.data or "").replace(tt.TT_VIDEO_OPEN, "", 1)
    try:
        video_id = int(raw)
    except ValueError:
        await callback.answer("Ролик не найден", show_alert=True)
        return
    await callback.answer()
    await show_video_card(callback, callback.from_user.id, video_id)


@tiktok_router.callback_query(F.data == tt.TT_NOOP)
async def on_tt_noop(callback: CallbackQuery) -> None:
    await callback.answer()


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
    elif session.get("mode") in {tt.MODE_WAIT_LINK, tt.MODE_WAIT_TITLE, tt.MODE_VIDEOS} or rec.get("kind") in {tt.WAIT_LINK, tt.WAIT_TITLE}:
        extra["origin"] = "videos"
        await tt.set_session(user_id, session.get("mode") or tt.MODE_VIDEOS, extra)
    elif session.get("mode") in {"my_videos", "nicks"} or extra.get("origin") == "mine":
        extra["origin"] = extra.get("origin") or "mine"
        await tt.set_session(user_id, session.get("mode") or "nicks", extra)
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
    if session.get("mode") in {tt.MODE_WAIT_LINK, tt.MODE_WAIT_TITLE, tt.MODE_VIDEOS}:
        after = "videos"
    if session.get("mode") in {"my_videos"} or extra.get("origin") == "mine":
        after = "mine"
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
    await callback.answer()
    notice = tt.text_done_undo(int(state.get("count") or 0), int(state.get("needed") or 15))
    await show_comments(callback, callback.from_user.id, notice=notice)


@tiktok_router.callback_query(F.data == tt.TT_WITHDRAW)
async def on_withdraw(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    try:
        await tt.withdraw_comment_case(callback.from_user.id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer()
    await _edit_or_send(
        callback,
        tt.text_case_withdrawn(),
        tt.done_keyboard(after="comments"),
    )


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
    item = await tt.get_user_video(callback.from_user.id, video_id)
    if not item:
        await show_my_videos(callback, callback.from_user.id)
        return
    await show_video_card(
        callback,
        callback.from_user.id,
        video_id,
        notice=tt.text_done_recheck(item),
    )


@tiktok_router.callback_query(F.data.startswith(tt.TT_RETRY_VIDEO))
async def on_retry_video(callback: CallbackQuery) -> None:
    if not _private(callback):
        await callback.answer()
        return
    raw = (callback.data or "").replace(tt.TT_RETRY_VIDEO, "", 1)
    user_id = callback.from_user.id
    try:
        video_id = int(raw)
    except ValueError:
        await callback.answer("Ролик не найден", show_alert=True)
        return
    item = await tt.get_user_video(user_id, video_id)
    if not item or item.get("status") != "rejected":
        await callback.answer("Снова отправить можно только отклонённый ролик.", show_alert=True)
        return
    pending = [v for v in await tt.list_user_videos(user_id) if v.get("status") == "pending"]
    if pending:
        await callback.answer("Сначала дождитесь ответа по ролику на проверке.", show_alert=True)
        return
    extra = {
        "after": "mine",
        "origin": "mine",
        "replaceVideoId": video_id,
    }
    await callback.answer()
    await _send_wait_prompt(
        callback,
        user_id,
        tt.text_wait_title(replace=True),
        tt.WAIT_TITLE,
        tt.MODE_WAIT_TITLE,
        extra,
        tt.video_wait_keyboard(),
    )


async def _send_collect_progress(message: Message, state: dict, *, delete_user: bool = True) -> None:
    user_id = message.from_user.id
    nicks = await tt.list_nicks(user_id)
    complete = bool(state.get("complete") or state.get("full") or int(state["count"]) >= int(state["needed"]))
    if complete:
        text = tt.text_photos_on_review(
            int(state.get("added") or 0),
            int(state["count"]),
            int(state["needed"]),
            nicks,
        )
    else:
        text = tt.collect_text(
            int(state["count"]),
            int(state["needed"]),
            nicks,
        )
    extra = {"after": "comments", "caseId": state.get("caseId")}
    if delete_user:
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
            disable_web_page_preview=True,
        )
        return
    markup = tt.comments_keyboard(
        can_send=True,
        count=int(state["count"]),
        needed=int(state["needed"]),
        waiting=True,
    )
    prompt = await message.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
    await tt.arm_wait(
        user_id,
        tt.WAIT_PHOTOS,
        tt.MODE_WAIT_PHOTOS,
        extra,
        prompt_chat_id=prompt.chat.id,
        prompt_message_id=prompt.message_id,
    )


async def on_wait_text(message: Message) -> None:
    if not _private(message):
        return
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
    raw = tt.message_link_text(message)
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
                new_nick = await tt.replace_nick(user_id, old, message.text or "")
                notice = tt.text_done_nick_changed(old, new_nick)
            else:
                new_nick = await tt.add_nick(user_id, message.text or "")
                have = await tt.list_nicks(user_id)
                notice = tt.text_done_nick_added(new_nick, have)
        except ValueError as exc:
            have = await tt.list_nicks(user_id)
            await _reprompt(
                message,
                user_id,
                tt.text_need_nick(after, error=str(exc)),
                tt.nick_wait_keyboard(back="nicks" if have else "hub"),
            )
            return
        await _delete_user_message(message)
        await _delete_prompt(user_id)
        tt.clear_wait(user_id)
        dest = after if after in {"comments", "videos", "mine"} else "hub"
        await message.answer(
            notice,
            reply_markup=tt.done_keyboard(after=dest),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return
    if kind == tt.WAIT_TITLE or await tt.is_waiting_title(user_id):
        session = await tt.get_session(user_id)
        extra = dict(session.get("extra") or rec)
        kb = tt.video_wait_keyboard()
        try:
            title = tt.validate_video_title(raw)
        except ValueError as exc:
            await _reprompt(
                message,
                user_id,
                tt.text_wait_title(str(exc), replace=bool(extra.get("replaceVideoId"))),
                kb,
            )
            return
        extra["videoTitle"] = title
        extra["after"] = extra.get("after") or "videos"
        extra["origin"] = "videos"
        await _delete_user_message(message)
        await _delete_prompt(user_id)
        bot1 = await _bot()
        prompt = await bot1.send_message(
            message.chat.id,
            tt.text_wait_link(title),
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        await tt.arm_wait(
            user_id,
            tt.WAIT_LINK,
            tt.MODE_WAIT_LINK,
            extra,
            prompt_chat_id=prompt.chat.id,
            prompt_message_id=prompt.message_id,
        )
        return
    if kind == tt.WAIT_LINK or await tt.is_waiting_link(user_id):
        session = await tt.get_session(user_id)
        extra = dict(session.get("extra") or rec)
        title = str(extra.get("videoTitle") or "")
        replace_id = extra.get("replaceVideoId")
        kb = tt.video_wait_keyboard()
        if not tt.looks_like_tiktok_url(raw):
            await _reprompt(
                message,
                user_id,
                tt.text_link_screen("Это не ссылка на TikTok. Скопируйте ссылку из приложения.", title=title),
                kb,
            )
            return
        try:
            parsed = await tt.submit_video(user_id, raw, title=title, replace_id=replace_id)
        except ValueError as exc:
            await _reprompt(message, user_id, tt.text_link_screen(str(exc), title=title), kb)
            return
        await _delete_user_message(message)
        await _delete_prompt(user_id)
        tt.clear_wait(user_id)
        url = (parsed or {}).get("url") if isinstance(parsed, dict) else None
        sent_title = (parsed or {}).get("title") if isinstance(parsed, dict) else title
        await message.answer(
            tt.text_done_video_sent(url or raw, sent_title or title),
            reply_markup=tt.done_keyboard(after="mine"),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return


async def on_wait_photo(message: Message) -> None:
    if not _private(message):
        return
    user_id = message.from_user.id
    if await tt.expire_wait_if_needed(user_id):
        return
    await tt.restore_wait_from_session(user_id)
    if await tt.expire_wait_if_needed(user_id) or not tt.get_wait(user_id):
        return
    if message.media_group_id:
        tt.remember_album_group(user_id, message.media_group_id)
    await tt.touch_wait(user_id)
    if not await tt.list_nicks(user_id):
        await _delete_user_message(message)
        await _arm_nick_screen(message, user_id, "comments")
        return
    lock = _photo_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _photo_locks[user_id] = lock
    photo = message.photo[-1]
    thumb_id = tt.pick_thumb_file_id(message.photo)
    async with lock:
        hashes = await tt.download_and_hash(message.bot, photo.file_id)
        try:
            state = await tt.add_photo(user_id, photo.file_id, hashes, thumb_id)
        except ValueError as exc:
            await _reprompt(
                message,
                user_id,
                tt.text_need_nick("comments", error=str(exc)),
                tt.nick_wait_keyboard(back="hub"),
            )
            return
    rec = tt.get_wait(user_id) or {}
    if not rec:
        extra = {"after": "comments"}
        await tt.arm_wait(user_id, tt.WAIT_PHOTOS, tt.MODE_WAIT_PHOTOS, extra)
    if message.media_group_id:
        tt.remember_album_group(user_id, message.media_group_id)
        await tt.touch_wait(user_id)
        prev = _album_tasks.pop(user_id, None)
        if prev:
            prev.cancel()
        _album_added[user_id] = _album_added.get(user_id, 0) + int(state.get("added") or 0)
        _album_msgs.setdefault(user_id, []).append(message)

        async def _flush() -> None:
            try:
                await asyncio.sleep(1.2)
                case = await tt.get_pending_comment_case(user_id)
                cfg = await tt.get_settings()
                added = _album_added.pop(user_id, 0)
                msgs = _album_msgs.pop(user_id, [])
                latest = {
                    "added": added,
                    "count": int((case or {}).get("received") or 0),
                    "needed": int((case or {}).get("needed") or cfg["photosRequired"]),
                    "complete": bool(case and case.get("complete")),
                    "caseId": (case or {}).get("id"),
                }
                for item in msgs:
                    await _delete_user_message(item)
                await _send_collect_progress(message, latest, delete_user=False)
            except asyncio.CancelledError:
                return

        _album_tasks[user_id] = asyncio.create_task(_flush())
        return
    await _send_collect_progress(message, state)


async def on_wait_noise(message: Message) -> None:
    if not _private(message):
        return
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
        have = await tt.list_nicks(user_id)
        await _reprompt(
            message,
            user_id,
            tt.text_need_nick(rec.get("after") or "", error="Нужно имя TikTok текстом, не файл."),
            tt.nick_wait_keyboard(back="nicks" if have else "hub"),
        )
        return
    if kind == tt.WAIT_TITLE:
        await _reprompt(
            message,
            user_id,
            tt.text_wait_title("Нужно название ролика текстом, не файл."),
            tt.video_wait_keyboard(),
        )
        return
    if kind == tt.WAIT_LINK:
        await _reprompt(
            message,
            user_id,
            tt.text_link_screen("Нужна ссылка на ролик, не файл."),
            tt.video_wait_keyboard(),
        )
        return
    cfg = await tt.get_settings()
    needed = int(cfg["photosRequired"])
    hint = "Нужно фото комментария, не файл." if message.document else "Отправьте фото комментария."
    case = await tt.get_pending_comment_case(user_id)
    count = int((case or {}).get("received") or 0)
    await _reprompt(
        message,
        user_id,
        tt.text_photo_wait_error(hint, count, needed),
        tt.comments_keyboard(count=count, needed=needed, waiting=True),
    )


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
