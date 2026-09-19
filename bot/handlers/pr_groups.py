# -*- coding: utf-8 -*-
"""Пиар в группах: личка, подтверждение создателя, вход/выход бота."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram import F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

_SERVER = Path(__file__).resolve().parents[2] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

from bot.funcs import pr_groups as pr
from pr_groups_logic import (  # noqa: E402
    FIRST_NO_HOLD_HOURS,
    MAX_LIVE_SEEDS,
    MAX_PENDING,
    PHOTOS_REQUIRED,
    ROLE_OWNER,
    ROLE_RECO,
    ST_CONFIRM_RETRY,
    ST_EXPIRED,
    ST_LIVE,
    ST_PENDING,
    ST_PHOTOS,
    ST_WAIT_CONFIRM,
    looks_like_confirm,
    text_accepted,
    text_after_photos_owner,
    text_after_photos_reco,
    text_banned_31,
    text_cancelled,
    text_confirm_no_first,
    text_confirm_no_second,
    text_confirm_prompt,
    text_confirm_yes,
    text_entry,
    text_freeze_admin,
    text_freeze_public,
    text_gift,
    text_gift_locked,
    text_group_busy,
    text_kicked,
    text_need_admin,
    text_need_photo,
    text_need_photos_first,
    text_need_public,
    text_not_creator,
    text_photos_expired,
    text_confirm_expired,
    text_no_groups,
    text_not_your_claim,
    text_photo_progress,
    text_pick_group,
    text_pick_role,
    text_two_live,
    text_two_pending,
    text_wait_photo,
    text_wrong_group,
    text_wrong_owner,
)

log = logging.getLogger("pr_groups")
router = Router(name="pr_groups")
_attached = False
_tick_started = False


async def _bot():
    from main import bot1
    return bot1


async def _edit(target: CallbackQuery | Message, text: str, markup=None) -> Message | None:
    bot = await _bot()
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
        return await bot.send_message(
            target.from_user.id, text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True,
        )
    return await target.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


async def _inspect_chat(bot, chat_id: int) -> dict:
    chat = await bot.get_chat(chat_id)
    username = getattr(chat, "username", None) or ""
    title = getattr(chat, "title", None) or str(chat_id)
    try:
        members = int(await bot.get_chat_member_count(chat_id))
    except Exception:
        members = 0
    me = await bot.get_me()
    try:
        self_m = await bot.get_chat_member(chat_id, me.id)
        is_admin = self_m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    except Exception:
        is_admin = False
    creator_id = None
    try:
        admins = await bot.get_chat_administrators(chat_id)
        for a in admins:
            if a.status == ChatMemberStatus.CREATOR:
                creator_id = int(a.user.id)
                break
    except Exception:
        pass
    return {
        "chat_id": int(chat_id),
        "title": title,
        "username": username,
        "member_count": members,
        "public": bool(username),
        "bot_admin": is_admin,
        "creator_id": creator_id,
        "type": getattr(chat, "type", None),
    }


async def _eligible_groups(user_id: int) -> list[dict]:
    bot = await _bot()
    out = []
    for row in await pr.recent_joins_for_user(user_id):
        chat_id = int(row["chat_id"])
        if await pr.group_busy(chat_id, except_user=user_id):
            continue
        if await pr.user_banned(user_id, chat_id):
            continue
        try:
            info = await _inspect_chat(bot, chat_id)
        except Exception:
            continue
        if info["type"] not in (ChatType.GROUP, ChatType.SUPERGROUP, "group", "supergroup"):
            continue
        if not info["public"] or not info["bot_admin"]:
            continue
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
                continue
        except Exception:
            continue
        info["added_by"] = row.get("last_added_by")
        info["joined_at"] = row.get("last_joined_at")
        out.append(info)
    return out


async def _open_hub(target: CallbackQuery | Message) -> None:
    await pr.ensure_schema()
    start_pr_ticker()
    await _edit(target, text_entry(), pr.entry_keyboard())


@router.callback_query(F.data == pr.PR_HUB)
async def on_hub(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    await _open_hub(cb)


@router.callback_query(F.data == pr.PR_START)
async def on_start(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    await pr.ensure_schema()
    uid = int(cb.from_user.id)
    if await pr.count_status(uid, {ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY, ST_PENDING}) >= MAX_PENDING:
        await _edit(cb, text_two_pending())
        return
    if await pr.count_status(uid, {ST_LIVE}) >= MAX_LIVE_SEEDS:
        await _edit(cb, text_two_live())
        return
    groups = await _eligible_groups(uid)
    if not groups:
        await _edit(cb, text_no_groups())
        return
    if len(groups) == 1:
        await _begin_role(cb, uid, groups[0])
        return
    await pr.set_session(uid, claim_id=None, mode="pick", extra={"groups": [g["chat_id"] for g in groups]})
    await _edit(cb, text_pick_group(), pr.groups_keyboard(groups))


@router.callback_query(F.data.startswith(pr.PR_PICK))
async def on_pick(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    try:
        chat_id = int(cb.data.split(":", 2)[-1])
    except Exception:
        return
    bot = await _bot()
    try:
        info = await _inspect_chat(bot, chat_id)
    except Exception:
        await _edit(cb, text_no_groups())
        return
    mem = await pr.get_membership(chat_id)
    info["added_by"] = (mem or {}).get("last_added_by")
    info["joined_at"] = (mem or {}).get("last_joined_at")
    await _begin_role(cb, uid, info)


async def _user_in_group(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(int(chat_id), int(user_id))
        return member.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
    except Exception:
        return False


async def _begin_role(target, uid: int, info: dict) -> None:
    if not info.get("public"):
        await _edit(target, text_need_public())
        return
    if not info.get("bot_admin"):
        await _edit(target, text_need_admin())
        return
    bot = await _bot()
    if not await _user_in_group(bot, int(info["chat_id"]), uid):
        await _edit(target, text_no_groups())
        return
    if await pr.user_banned(uid, int(info["chat_id"])):
        await _edit(target, text_banned_31())
        return
    if await pr.group_busy(int(info["chat_id"]), except_user=uid):
        await _edit(target, text_group_busy())
        return
    await pr.set_session(uid, claim_id=None, mode="role", extra=info)
    await _edit(target, text_pick_role(info.get("title") or ""), pr.role_keyboard())


async def _open_photos(target, uid: int, info: dict, role: str) -> None:
    claim = await pr.create_claim(
        user_id=uid,
        chat_id=int(info["chat_id"]),
        role=role,
        title=str(info.get("title") or ""),
        username=str(info.get("username") or ""),
        member_count=int(info.get("member_count") or 0),
        added_by=info.get("added_by"),
        creator_id=info.get("creator_id"),
        joined_at=info.get("joined_at"),
    )
    await pr.set_session(uid, claim_id=int(claim["id"]), mode="photos", extra={"n": 0})
    await _edit(target, text_wait_photo(0, 0), pr.cancel_keyboard())


@router.callback_query(F.data == pr.PR_OWNER)
async def on_owner(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    session = await pr.get_session(uid) or {}
    info = dict(session.get("extra") or {})
    if session.get("mode") != "role" or not info.get("chat_id"):
        await _open_hub(cb)
        return
    if int(info.get("creator_id") or 0) != uid:
        await _edit(cb, text_wrong_owner(), pr.role_keyboard())
        return
    await _open_photos(cb, uid, info, ROLE_OWNER)


@router.callback_query(F.data == pr.PR_RECO)
async def on_reco(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    session = await pr.get_session(uid) or {}
    info = dict(session.get("extra") or {})
    if session.get("mode") != "role" or not info.get("chat_id"):
        await _open_hub(cb)
        return
    await _open_photos(cb, uid, info, ROLE_RECO)


@router.callback_query(F.data == pr.PR_CANCEL)
async def on_cancel(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    session = await pr.get_session(uid) or {}
    if session.get("claim_id"):
        claim = await pr.claim_by_id(int(session["claim_id"]))
        if claim and claim["status"] in {ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY, ST_PENDING}:
            await pr.cancel_claim(int(claim["id"]))
    await pr.clear_session(uid)
    await _edit(cb, text_cancelled())


def message_matches_photo(message: Message) -> bool:
    if not message or getattr(message.chat, "type", None) != "private":
        return False
    # session check is async; cheap prefilter — photo only
    return bool(message.photo)


async def on_wait_photo(message: Message) -> None:
    uid = int(message.from_user.id)
    session = await pr.get_session(uid)
    if not session or session.get("mode") != "photos" or not session.get("claim_id"):
        return
    claim = await pr.claim_by_id(int(session["claim_id"]))
    if not claim or claim["status"] != ST_PHOTOS:
        if claim and claim["status"] == ST_EXPIRED:
            await message.answer(text_photos_expired(), parse_mode="HTML")
            await pr.clear_session(uid)
        return
    if not message.photo:
        await message.answer(text_need_photo(), parse_mode="HTML")
        return
    file_id = message.photo[-1].file_id
    claim = await pr.add_photo(int(claim["id"]), file_id)
    have = len(claim.get("photos") or [])
    if have < PHOTOS_REQUIRED:
        await message.answer(text_wait_photo(have, have), reply_markup=pr.cancel_keyboard(), parse_mode="HTML")
        return
    await pr.clear_session(uid)
    if claim["role"] == ROLE_OWNER:
        await message.answer(text_after_photos_owner(), parse_mode="HTML")
    else:
        await message.answer(text_after_photos_reco(), parse_mode="HTML")


@router.message(F.chat.type.in_({"group", "supergroup"}), F.text)
async def on_confirm_command(message: Message) -> None:
    if not looks_like_confirm(message.text or ""):
        return
    uid = int(message.from_user.id)
    chat_id = int(message.chat.id)
    claim = await pr.active_claim_for_user(uid)
    if not claim or int(claim["chat_id"]) != chat_id:
        if claim and int(claim["chat_id"]) != chat_id:
            await message.reply(text_wrong_group(), parse_mode="HTML")
        elif not claim:
            return
        else:
            await message.reply(text_not_your_claim(), parse_mode="HTML")
        return
    if claim["role"] != ROLE_RECO:
        return
    if claim["status"] == ST_PHOTOS:
        await message.reply(text_need_photos_first(), parse_mode="HTML")
        return
    if claim["status"] not in {ST_WAIT_CONFIRM, ST_CONFIRM_RETRY}:
        return
    token = int(claim.get("confirm_token") or 0) + 1
    sent = await message.reply(
        text_confirm_prompt(uid, message.from_user.first_name or "игрок"),
        reply_markup=pr.confirm_keyboard(int(claim["id"]), token),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await pr.save_claim(
        int(claim["id"]),
        confirm_token=token,
        confirm_message_id=sent.message_id,
        confirm_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )


@router.callback_query(F.data.startswith(pr.PR_YES) | F.data.startswith(pr.PR_NO))
async def on_confirm_click(cb: CallbackQuery) -> None:
    data = cb.data or ""
    yes = data.startswith(pr.PR_YES)
    parts = data.split(":")
    token = None
    try:
        claim_id = int(parts[1])
        if len(parts) > 2:
            token = int(parts[2])
    except Exception:
        try:
            await cb.answer()
        except Exception:
            pass
        return
    claim = await pr.claim_by_id(claim_id)
    if not claim:
        try:
            await cb.answer()
        except Exception:
            pass
        return
    expires = claim.get("confirm_expires_at")
    if expires and getattr(expires, "tzinfo", None) is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires <= datetime.now(timezone.utc):
        try:
            await cb.answer()
        except Exception:
            pass
        try:
            await cb.message.edit_text(text_confirm_expired(), parse_mode="HTML")
        except Exception:
            pass
        return
    if token is not None and int(claim.get("confirm_token") or 0) != token:
        try:
            await cb.answer()
        except Exception:
            pass
        try:
            await cb.message.edit_text(text_confirm_expired(), parse_mode="HTML")
        except Exception:
            pass
        return
    mid = claim.get("confirm_message_id")
    if mid and cb.message and int(cb.message.message_id) != int(mid):
        try:
            await cb.answer()
        except Exception:
            pass
        return
    chat_id = int(claim["chat_id"])
    bot = await _bot()
    try:
        member = await bot.get_chat_member(chat_id, cb.from_user.id)
        is_creator = member.status == ChatMemberStatus.CREATOR
    except Exception:
        is_creator = False
    if not is_creator:
        try:
            await cb.answer()
        except Exception:
            pass
        try:
            await cb.message.reply(text_not_creator(), parse_mode="HTML")
        except Exception:
            pass
        return
    if claim["status"] not in {ST_WAIT_CONFIRM, ST_CONFIRM_RETRY}:
        try:
            await cb.answer()
        except Exception:
            pass
        return
    if yes:
        await pr.save_claim(claim_id, status=ST_PENDING, confirmed_at=datetime.now(timezone.utc), confirm_attempt=int(claim.get("confirm_attempt") or 0))
        try:
            await cb.message.edit_text(text_confirm_yes(), parse_mode="HTML")
        except Exception:
            pass
        try:
            await cb.answer()
        except Exception:
            pass
        return
    attempt = int(claim.get("confirm_attempt") or 0) + 1
    if attempt <= 1:
        await pr.save_claim(
            claim_id,
            status=ST_CONFIRM_RETRY,
            confirm_attempt=1,
            slot_hold_until=datetime.now(timezone.utc) + timedelta(hours=FIRST_NO_HOLD_HOURS),
        )
        try:
            await cb.message.edit_text(text_confirm_no_first(), parse_mode="HTML")
        except Exception:
            pass
    else:
        await pr.save_claim(
            claim_id,
            status=ST_EXPIRED,
            confirm_attempt=2,
            banned_until=datetime.now(timezone.utc) + timedelta(days=31),
        )
        try:
            await cb.message.edit_text(text_confirm_no_second(), parse_mode="HTML")
        except Exception:
            pass
    try:
        await cb.answer()
    except Exception:
        pass


@router.my_chat_member()
async def on_my_chat(event: ChatMemberUpdated) -> None:
    chat = event.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    old = event.old_chat_member.status
    new = event.new_chat_member.status
    was = old in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR, ChatMemberStatus.RESTRICTED)
    now = new in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR, ChatMemberStatus.RESTRICTED)
    chat_id = int(chat.id)
    await pr.ensure_schema()
    start_pr_ticker()
    if now and not was:
        adder = getattr(event.from_user, "id", None)
        await pr.record_join(chat_id, adder)
        return
    if was and not now:
        await pr.record_leave(chat_id)
        claim = await pr.live_claim_for_chat(chat_id)
        if claim:
            bot = await _bot()
            await pr.end_claim(bot, claim, reason="kicked")
            try:
                await bot.send_message(int(claim["user_id"]), text_kicked(), parse_mode="HTML")
            except Exception:
                pass
        return
    if now and new != ChatMemberStatus.ADMINISTRATOR and new != ChatMemberStatus.CREATOR:
        claim = await pr.live_claim_for_chat(chat_id)
        if claim and not claim.get("freeze"):
            await pr.save_claim(int(claim["id"]), freeze="admin")
            try:
                bot = await _bot()
                await bot.send_message(int(claim["user_id"]), text_freeze_admin(), parse_mode="HTML")
            except Exception:
                pass
    if now and new in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        claim = await pr.live_claim_for_chat(chat_id)
        if claim and claim.get("freeze") == "admin":
            await pr.save_claim(int(claim["id"]), freeze=None)


async def watch_public_flag(bot, chat_id: int) -> None:
    try:
        chat = await bot.get_chat(chat_id)
    except Exception:
        return
    claim = await pr.live_claim_for_chat(chat_id)
    if not claim:
        return
    public = bool(getattr(chat, "username", None))
    if not public and claim.get("freeze") != "public":
        await pr.save_claim(int(claim["id"]), freeze="public")
        try:
            await bot.send_message(int(claim["user_id"]), text_freeze_public(), parse_mode="HTML")
        except Exception:
            pass
    if public and claim.get("freeze") == "public":
        await pr.save_claim(int(claim["id"]), freeze=None)


async def _ticker() -> None:
    await asyncio.sleep(8)
    while True:
        try:
            bot = await _bot()
            await pr.housekeep(bot)
            for claim in await pr.list_live():
                await watch_public_flag(bot, int(claim["chat_id"]))
        except Exception:
            log.debug("pr ticker", exc_info=True)
        await asyncio.sleep(60)


def start_pr_ticker() -> None:
    global _tick_started
    if _tick_started:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _tick_started = True
    loop.create_task(_ticker())


def attach_pr_groups(dp) -> None:
    global _attached
    if _attached:
        return
    dp.include_router(router)
    _attached = True
    start_pr_ticker()


async def notify_accepted(user_id: int, term_days: int) -> None:
    bot = await _bot()
    try:
        await bot.send_message(int(user_id), text_accepted(term_days), parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        pass


async def notify_rejected(user_id: int, html: str) -> None:
    bot = await _bot()
    try:
        await bot.send_message(int(user_id), html, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        pass


async def send_gift_notice(message: Message, user_id: int, name: str, amount: int) -> None:
    try:
        await message.answer(text_gift(user_id, name, amount), parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        pass


async def send_gift_locked(message: Message) -> None:
    try:
        await message.reply(text_gift_locked(), parse_mode="HTML")
    except Exception:
        pass
