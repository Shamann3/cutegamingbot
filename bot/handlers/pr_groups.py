# -*- coding: utf-8 -*-
"""Пиар в группах: личка, подтверждение создателя, вход/выход бота."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from aiogram import F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

_SERVER = Path(__file__).resolve().parents[2] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

from bot.funcs import pr_groups as pr
from pr_groups_logic import (  # noqa: E402
    FIRST_NO_HOLD_HOURS,
    LINK_MODES,
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
    looks_like_help,
    parse_group_ref,
    extract_group_ref,
    chat_id_from_ref,
    text_accepted,
    text_after_photos_reco,
    text_after_proofs_owner,
    text_after_proofs_reco,
    text_are_owner_switch,
    text_banned_31,
    text_bot_joined,
    text_bot_not_there,
    text_cancelled,
    text_cant_add,
    text_choose_role,
    text_confirm_expired,
    text_confirm_no_first,
    text_confirm_no_second,
    text_confirm_prompt,
    text_confirm_yes,
    text_entry,
    text_freeze_admin,
    text_freeze_public,
    text_forward_no_group,
    text_gift,
    text_gift_locked,
    text_group_busy,
    text_group_not_found,
    text_how,
    text_how_admin,
    text_how_public,
    text_kicked,
    text_mine,
    text_link_invite,
    text_need_admin,
    text_need_link,
    text_need_photo,
    text_need_photos_first,
    text_need_public,
    text_not_a_group,
    text_not_creator,
    text_not_in_group,
    text_not_owner_switch,
    text_not_your_claim,
    text_photos_expired,
    text_pick_group,
    text_owner_no_confirm,
    text_resume_claim,
    text_two_live,
    text_two_pending,
    text_wait_photo,
    text_wrote_confirm,
    text_wrong_group,
    text_wrong_owner,
)

log = logging.getLogger("pr_groups")
router = Router(name="pr_groups")
_attached = False
_tick_started = False
_photo_locks: dict[int, asyncio.Lock] = {}
_album_used: dict[int, str] = {}


def _photo_lock(user_id: int) -> asyncio.Lock:
    lock = _photo_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _photo_locks[user_id] = lock
    return lock


def _claim_extra(claim: dict, extra: dict | None = None) -> dict:
    base = dict(extra or {})
    base["n"] = len(claim.get("photos") or [])
    base["chat_id"] = claim.get("chat_id") or base.get("chat_id")
    base["title"] = claim.get("chat_title") or base.get("title") or ""
    base["username"] = claim.get("chat_username") or base.get("username") or ""
    base["role"] = claim.get("role") or base.get("role")
    return base


_bot_uname = ""


async def _bot():
    from main import bot1
    return bot1


async def _bot_username() -> str:
    global _bot_uname
    if _bot_uname:
        return _bot_uname
    bot = await _bot()
    me = await bot.get_me()
    _bot_uname = (getattr(me, "username", None) or "CuteGamingBot").lstrip("@")
    return _bot_uname


async def _push(uid: int, text: str, markup=None) -> None:
    bot = await _bot()
    await bot.send_message(
        int(uid), text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True,
    )


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
    is_member = False
    is_admin = False
    try:
        self_m = await bot.get_chat_member(chat_id, me.id)
        is_member = self_m.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
        is_admin = self_m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    except Exception:
        pass
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
        "bot_member": is_member,
        "bot_admin": is_admin,
        "creator_id": creator_id,
        "type": getattr(chat, "type", None),
    }


async def _scan_user_groups(user_id: int) -> dict:
    bot = await _bot()
    ready, no_public, no_admin = [], [], []
    for row in await pr.recent_joins_for_user(user_id):
        chat_id = int(row["chat_id"])
        if await pr.user_banned(user_id, chat_id):
            continue
        if await pr.group_busy(chat_id, except_user=user_id):
            continue
        try:
            info = await _inspect_chat(bot, chat_id)
        except Exception:
            continue
        if info["type"] not in (ChatType.GROUP, ChatType.SUPERGROUP, "group", "supergroup"):
            continue
        if not await _user_in_group(bot, chat_id, user_id):
            continue
        info["added_by"] = row.get("last_added_by")
        info["joined_at"] = row.get("last_joined_at")
        if info["public"] and info["bot_admin"]:
            ready.append(info)
        elif info["bot_admin"] and not info["public"]:
            no_public.append(info)
        else:
            no_admin.append(info)
    return {"ready": ready, "no_public": no_public, "no_admin": no_admin}


def _intent_of(extra: dict | None, session: dict | None = None) -> str:
    blob = dict(extra or {})
    if session:
        blob.update(session.get("extra") or {})
    intent = str(blob.get("intent") or "")
    if intent in {ROLE_OWNER, ROLE_RECO}:
        return intent
    return ""


async def _open_choose(target, uid: int, extra: dict | None = None) -> None:
    base = dict(extra or {})
    base.pop("intent", None)
    await pr.set_session(uid, claim_id=None, mode="choose", extra=base)
    await _edit(target, text_choose_role(), pr.choose_keyboard())


async def _open_hub(target: CallbackQuery | Message) -> None:
    await pr.ensure_schema()
    start_pr_ticker()
    uid = int(target.from_user.id)
    rows = await pr.list_user_claims(uid)
    await _edit(target, text_entry(), pr.entry_keyboard(mine=bool(rows)))


async def _show_how(target, uid: int, scan: dict | None = None) -> None:
    session = await pr.get_session(uid) or {}
    intent = _intent_of(session.get("extra"), session)
    scan = scan or await _scan_user_groups(uid)
    extra = dict(session.get("extra") or {})
    extra["intent"] = intent
    extra["no_public"] = [g["chat_id"] for g in scan["no_public"]]
    extra["no_admin"] = [g["chat_id"] for g in scan["no_admin"]]
    uname = await _bot_username()
    if not scan["ready"] and len(scan["no_public"]) == 1 and not scan["no_admin"]:
        group = scan["no_public"][0]
        extra["chat_id"] = group.get("chat_id")
        extra["title"] = group.get("title") or ""
        await pr.set_session(uid, claim_id=None, mode="how_public", extra=extra)
        await _edit(target, text_need_public(group.get("title") or ""), pr.how_public_keyboard(uname, intent=intent))
        return
    if not scan["ready"] and len(scan["no_admin"]) == 1 and not scan["no_public"]:
        group = scan["no_admin"][0]
        extra["chat_id"] = group.get("chat_id")
        extra["title"] = group.get("title") or ""
        await pr.set_session(uid, claim_id=None, mode="how_admin", extra=extra)
        await _edit(target, text_need_admin(group.get("title") or "", intent=intent), pr.how_admin_keyboard(uname, intent=intent))
        return
    extra.pop("chat_id", None)
    await pr.set_session(uid, claim_id=None, mode="how", extra=extra)
    await _edit(
        target,
        text_how(intent=intent, no_public=scan["no_public"], no_admin=scan["no_admin"]),
        pr.how_keyboard(
            intent=intent,
            no_public=bool(scan["no_public"]),
            no_admin=bool(scan["no_admin"]),
            bot_username=uname,
        ),
    )


async def _resume_claim_screen(target, uid: int, claim: dict) -> None:
    status = claim["status"]
    title = claim.get("chat_title") or ""
    extra = _claim_extra(claim)
    if status == ST_PHOTOS:
        have = len(claim.get("photos") or [])
        extra["n"] = have
        await pr.set_session(uid, claim_id=int(claim["id"]), mode="photos", extra=extra)
        await _edit(target, text_wait_photo(have, have), pr.photo_keyboard(have))
        return
    if status in {ST_WAIT_CONFIRM, ST_CONFIRM_RETRY}:
        extra["username"] = claim.get("chat_username") or extra.get("username") or ""
        await pr.set_session(uid, claim_id=int(claim["id"]), mode="wait_confirm", extra=extra)
        await _edit(target, text_after_photos_reco(title), pr.after_reco_keyboard(extra["username"]))
        return
    await pr.set_session(uid, claim_id=int(claim["id"]), mode="view", extra=extra)
    await _edit(target, text_resume_claim(title, status), pr.resume_keyboard(status))


async def _try_advance(target, uid: int) -> None:
    await pr.ensure_schema()
    open_claim = await pr.active_claim_for_user(uid)
    if open_claim and open_claim["status"] in {ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY}:
        await _resume_claim_screen(target, uid, open_claim)
        return
    if await pr.count_status(uid, {ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY, ST_PENDING}) >= MAX_PENDING:
        await _edit(target, text_two_pending(), pr.pending_keyboard())
        return
    if await pr.count_status(uid, {ST_LIVE}) >= MAX_LIVE_SEEDS:
        await _edit(target, text_two_live(), pr.pending_keyboard())
        return
    session = await pr.get_session(uid) or {}
    intent = _intent_of(session.get("extra"), session)
    if not intent:
        await _open_choose(target, uid, session.get("extra") or {})
        return
    scan = await _scan_user_groups(uid)
    ready = list(scan["ready"])
    if intent == ROLE_OWNER:
        ready = [g for g in ready if int(g.get("creator_id") or 0) in {0, uid}]
    elif intent == ROLE_RECO:
        ready = [g for g in ready if int(g.get("creator_id") or 0) != uid]
    if len(ready) == 1:
        await _begin_proofs(target, uid, ready[0])
        return
    if len(ready) > 1:
        extra = dict(session.get("extra") or {})
        extra["intent"] = intent
        extra["groups"] = [g["chat_id"] for g in ready]
        await pr.set_session(uid, claim_id=None, mode="pick", extra=extra)
        await _edit(target, text_pick_group(), pr.groups_keyboard(ready))
        return
    await _show_how(target, uid, scan)


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
    uid = int(cb.from_user.id)
    await pr.ensure_schema()
    start_pr_ticker()
    open_claim = await pr.active_claim_for_user(uid)
    if open_claim and open_claim["status"] in {ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY}:
        await _resume_claim_screen(cb, uid, open_claim)
        return
    if await pr.count_status(uid, {ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY, ST_PENDING}) >= MAX_PENDING:
        await _edit(cb, text_two_pending(), pr.pending_keyboard())
        return
    if await pr.count_status(uid, {ST_LIVE}) >= MAX_LIVE_SEEDS:
        await _edit(cb, text_two_live(), pr.pending_keyboard())
        return
    session = await pr.get_session(uid) or {}
    extra = dict(session.get("extra") or {})
    extra.pop("intent", None)
    await _open_choose(cb, uid, extra)


@router.callback_query(F.data == pr.PR_CHECK)
async def on_check(cb: CallbackQuery) -> None:
    try:
        await cb.answer("Смотрю группы…")
    except Exception:
        pass
    await _try_advance(cb, int(cb.from_user.id))


@router.callback_query(F.data == pr.PR_HOW)
async def on_how(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    await _show_how(cb, uid)


@router.callback_query(F.data == pr.PR_PUBLIC)
async def on_how_public(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    session = await pr.get_session(uid) or {}
    extra = dict(session.get("extra") or {})
    extra["intent"] = _intent_of(extra, session)
    await pr.set_session(uid, claim_id=None, mode="how_public", extra=extra)
    await _edit(cb, text_how_public(), pr.how_public_keyboard(await _bot_username(), intent=extra["intent"]))


@router.callback_query(F.data == pr.PR_ADMIN)
async def on_how_admin(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    session = await pr.get_session(uid) or {}
    extra = dict(session.get("extra") or {})
    extra["intent"] = _intent_of(extra, session)
    await pr.set_session(uid, claim_id=None, mode="how_admin", extra=extra)
    await _edit(cb, text_how_admin(intent=extra["intent"]), pr.how_admin_keyboard(await _bot_username(), intent=extra["intent"]))


@router.callback_query(F.data == pr.PR_MINE)
async def on_mine(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    rows = await pr.list_user_claims(uid)
    await pr.set_session(uid, claim_id=None, mode="mine", extra={})
    await _edit(cb, text_mine(rows), pr.mine_keyboard(rows))


@router.callback_query(F.data.startswith(pr.PR_OPEN))
async def on_open_claim(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    try:
        claim_id = int((cb.data or "").split(":")[-1])
    except Exception:
        await _open_hub(cb)
        return
    claim = await pr.claim_by_id(claim_id)
    if not claim or int(claim.get("user_id") or 0) != uid:
        await _edit(cb, text_not_your_claim(), pr.hub_only_keyboard())
        return
    await _resume_claim_screen(cb, uid, claim)


@router.callback_query(F.data == pr.PR_UNDO)
async def on_undo(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    session = await pr.get_session(uid) or {}
    if session.get("mode") != "photos" or not session.get("claim_id"):
        await _open_hub(cb)
        return
    claim = await pr.pop_photo(int(session["claim_id"]))
    if not claim:
        await _open_hub(cb)
        return
    have = len(claim.get("photos") or [])
    extra = _claim_extra(claim, session.get("extra") or {})
    extra["n"] = have
    await pr.set_session(uid, claim_id=int(claim["id"]), mode="photos", extra=extra)
    await _edit(cb, text_wait_photo(have, have), pr.photo_keyboard(have))


@router.callback_query(F.data == pr.PR_WROTE)
async def on_wrote(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    session = await pr.get_session(int(cb.from_user.id)) or {}
    username = str((session.get("extra") or {}).get("username") or "")
    await _edit(cb, text_wrote_confirm(), pr.after_reco_keyboard(username))


@router.callback_query(F.data == pr.PR_BACK)
async def on_back(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    session = await pr.get_session(uid) or {}
    mode = session.get("mode")
    extra = dict(session.get("extra") or {})
    if mode in LINK_MODES or mode == "pick":
        await _open_choose(cb, uid, extra)
        return
    if mode == "photos" and session.get("claim_id"):
        claim = await pr.claim_by_id(int(session["claim_id"]))
        if claim and claim["status"] == ST_PHOTOS:
            await pr.cancel_claim(int(claim["id"]))
        extra["intent"] = extra.get("intent") or (claim.get("role") if claim else "") or extra.get("intent")
        extra.pop("n", None)
        await pr.set_session(uid, claim_id=None, mode="how", extra=extra)
        await _show_how(cb, uid)
        return
    if mode == "mismatch":
        await _open_choose(cb, uid, extra)
        return
    await _open_hub(cb)


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
        await _show_how(cb, uid)
        return
    mem = await pr.get_membership(chat_id)
    info["added_by"] = (mem or {}).get("last_added_by")
    info["joined_at"] = (mem or {}).get("last_joined_at")
    await _begin_proofs(cb, uid, info)


async def _user_in_group(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(int(chat_id), int(user_id))
        return member.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
    except Exception:
        return False


async def _begin_proofs(target, uid: int, info: dict) -> None:
    session = await pr.get_session(uid) or {}
    extra = dict(session.get("extra") or {})
    extra.update(info)
    extra["chat_id"] = int(info["chat_id"])
    intent = _intent_of(extra, session)
    extra["intent"] = intent
    title = str(info.get("title") or extra.get("title") or "")
    uname = await _bot_username()
    if not info.get("bot_member", True) and not info.get("bot_admin"):
        await pr.set_session(uid, claim_id=None, mode="how", extra=extra)
        await _edit(target, text_bot_not_there(title, intent=intent), pr.add_group_keyboard(uname, intent=intent))
        return
    if not info.get("public"):
        await pr.set_session(uid, claim_id=None, mode="how_public", extra=extra)
        await _edit(target, text_need_public(title), pr.how_public_keyboard(uname, intent=intent))
        return
    if not info.get("bot_admin"):
        await pr.set_session(uid, claim_id=None, mode="how_admin", extra=extra)
        await _edit(target, text_need_admin(title, intent=intent), pr.how_admin_keyboard(uname, intent=intent))
        return
    bot = await _bot()
    if not await _user_in_group(bot, int(info["chat_id"]), uid):
        await pr.set_session(uid, claim_id=None, mode="how", extra=extra)
        await _edit(target, text_not_in_group(title), pr.add_group_keyboard(uname, intent=intent))
        return
    if await pr.user_banned(uid, int(info["chat_id"])):
        await _edit(target, text_banned_31(), pr.hub_only_keyboard())
        return
    busy = await pr.group_busy(int(info["chat_id"]), except_user=uid)
    if busy:
        owner_took = int(busy.get("user_id") or 0) == int(info.get("creator_id") or -1)
        await _edit(target, text_group_busy(owner=owner_took), pr.hub_only_keyboard())
        return
    creator_id = int(info.get("creator_id") or extra.get("creator_id") or 0)
    extra["creator_id"] = creator_id or extra.get("creator_id")
    if not intent:
        await _open_choose(target, uid, extra)
        return
    if intent == ROLE_OWNER and creator_id and creator_id != uid:
        extra["intent"] = ROLE_OWNER
        await pr.set_session(uid, claim_id=None, mode="mismatch", extra=extra)
        await _edit(target, text_not_owner_switch(title), pr.switch_to_reco_keyboard())
        return
    if intent == ROLE_RECO and creator_id and creator_id == uid:
        extra["intent"] = ROLE_RECO
        await pr.set_session(uid, claim_id=None, mode="mismatch", extra=extra)
        await _edit(target, text_are_owner_switch(title), pr.switch_to_owner_keyboard())
        return
    await _open_photos(target, uid, extra, ROLE_OWNER if intent == ROLE_OWNER else ROLE_RECO)


async def _begin_role(target, uid: int, info: dict) -> None:
    await _begin_proofs(target, uid, info)


async def _begin_role_dm(uid: int, info: dict) -> None:
    session = await pr.get_session(uid) or {}
    extra = dict(session.get("extra") or {})
    extra.update(info)
    extra["intent"] = _intent_of(extra, session)
    await pr.set_session(uid, claim_id=None, mode=session.get("mode") or "how", extra=extra)
    await _begin_proofs_dm(uid, extra)


async def _begin_proofs_dm(uid: int, info: dict) -> None:
    session = await pr.get_session(uid) or {}
    extra = dict(session.get("extra") or {})
    extra.update(info)
    extra["chat_id"] = int(info["chat_id"])
    intent = _intent_of(extra, session)
    extra["intent"] = intent

    async def _send(text: str, markup=None):
        await _push(uid, text, markup)

    title = str(info.get("title") or "")
    uname = await _bot_username()
    if not info.get("bot_member", True) and not info.get("bot_admin"):
        await pr.set_session(uid, claim_id=None, mode="how", extra=extra)
        await _send(text_bot_not_there(title, intent=intent), pr.add_group_keyboard(uname, intent=intent))
        return
    if not info.get("public"):
        await pr.set_session(uid, claim_id=None, mode="how_public", extra=extra)
        await _send(text_need_public(title), pr.how_public_keyboard(uname, intent=intent))
        return
    if not info.get("bot_admin"):
        await pr.set_session(uid, claim_id=None, mode="how_admin", extra=extra)
        await _send(text_need_admin(title, intent=intent), pr.how_admin_keyboard(uname, intent=intent))
        return
    bot_api = await _bot()
    if not await _user_in_group(bot_api, int(info["chat_id"]), uid):
        await pr.set_session(uid, claim_id=None, mode="how", extra=extra)
        await _send(text_not_in_group(title), pr.add_group_keyboard(uname, intent=intent))
        return
    if await pr.user_banned(uid, int(info["chat_id"])):
        await _send(text_banned_31(), pr.hub_only_keyboard())
        return
    busy = await pr.group_busy(int(info["chat_id"]), except_user=uid)
    if busy:
        owner_took = int(busy.get("user_id") or 0) == int(info.get("creator_id") or -1)
        await _send(text_group_busy(owner=owner_took), pr.hub_only_keyboard())
        return
    creator_id = int(info.get("creator_id") or 0)
    extra["creator_id"] = creator_id
    if not intent:
        await pr.set_session(uid, claim_id=None, mode="choose", extra=extra)
        await _send(text_choose_role(), pr.choose_keyboard())
        return
    if intent == ROLE_OWNER and creator_id and creator_id != uid:
        await pr.set_session(uid, claim_id=None, mode="mismatch", extra=extra)
        await _send(text_not_owner_switch(title), pr.switch_to_reco_keyboard())
        return
    if intent == ROLE_RECO and creator_id and creator_id == uid:
        await pr.set_session(uid, claim_id=None, mode="mismatch", extra=extra)
        await _send(text_are_owner_switch(title), pr.switch_to_owner_keyboard())
        return
    await _open_photos_dm(uid, extra, ROLE_OWNER if intent == ROLE_OWNER else ROLE_RECO)


def _is_forwarded(message: Message) -> bool:
    return bool(
        getattr(message, "forward_origin", None)
        or getattr(message, "forward_from_chat", None)
        or getattr(message, "forward_from", None)
        or getattr(message, "forward_sender_name", None)
        or getattr(message, "forward_date", None)
    )


def _entity_urls(message: Message) -> list[str]:
    urls: list[str] = []
    for ent in list(getattr(message, "entities", None) or []) + list(getattr(message, "caption_entities", None) or []):
        url = getattr(ent, "url", None)
        if url:
            urls.append(str(url))
    return urls


async def _info_from_chat_id(chat_id: int, uid: int) -> dict:
    bot = await _bot()
    info = await _inspect_chat(bot, int(chat_id))
    mem = await pr.get_membership(int(chat_id))
    if not mem and info.get("bot_member"):
        await pr.record_join(int(chat_id), uid)
        mem = await pr.get_membership(int(chat_id))
    info["added_by"] = (mem or {}).get("last_added_by") or uid
    info["joined_at"] = (mem or {}).get("last_joined_at")
    return info


async def _resolve_group_and_begin(target, uid: int, *, chat_id: int | None = None, ref: dict | None = None) -> None:
    uname = await _bot_username()
    session = await pr.get_session(uid) or {}
    intent = _intent_of(session.get("extra"), session)
    bot = await _bot()
    try:
        if chat_id is not None:
            info = await _info_from_chat_id(int(chat_id), uid)
        elif ref and ref.get("kind") == "username":
            chat = await bot.get_chat("@" + ref["value"])
            if str(getattr(chat, "type", "") or "") not in {
                ChatType.GROUP, ChatType.SUPERGROUP, "group", "supergroup",
            }:
                await _edit(target, text_not_a_group(), pr.add_group_keyboard(uname, intent=intent))
                return
            info = await _info_from_chat_id(int(chat.id), uid)
        elif chat_id_from_ref(ref) is not None:
            info = await _info_from_chat_id(int(chat_id_from_ref(ref)), uid)
        else:
            await _edit(target, text_need_link(), pr.how_keyboard(bot_username=uname, intent=intent))
            return
    except Exception:
        await _edit(target, text_group_not_found(), pr.add_group_keyboard(uname, intent=intent))
        return
    if str(info.get("type") or "") not in {
        ChatType.GROUP, ChatType.SUPERGROUP, "group", "supergroup",
    }:
        await _edit(target, text_not_a_group(), pr.add_group_keyboard(uname, intent=intent))
        return
    await _begin_proofs(target, uid, info)


async def on_wait_link(message: Message) -> None:
    uid = int(message.from_user.id)
    session = await pr.get_session(uid)
    if not session or session.get("mode") not in LINK_MODES:
        return
    intent = _intent_of(session.get("extra"), session)
    uname = await _bot_username()
    text = str(getattr(message, "text", None) or getattr(message, "caption", None) or "")
    if text.startswith("/"):
        return
    if looks_like_help(text) and not parse_group_ref(text):
        await _show_how(message, uid)
        return
    if _is_forwarded(message):
        await message.answer(
            text_forward_no_group(),
            reply_markup=pr.how_keyboard(bot_username=uname, intent=intent),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return
    ref = extract_group_ref(text=text, urls=_entity_urls(message))
    if ref is None:
        await message.answer(
            text_need_link(),
            reply_markup=pr.how_keyboard(bot_username=uname, intent=intent),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return
    if ref["kind"] == "invite":
        await message.answer(
            text_link_invite(),
            reply_markup=pr.how_public_keyboard(uname, intent=intent),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return
    await _resolve_group_and_begin(message, uid, ref=ref)


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
    extra = dict(info)
    extra["n"] = 0
    extra["role"] = role
    extra["intent"] = role
    await pr.set_session(uid, claim_id=int(claim["id"]), mode="photos", extra=extra)
    await _edit(target, text_wait_photo(0, 0), pr.photo_keyboard(0))


async def _open_photos_dm(uid: int, info: dict, role: str) -> None:
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
    extra = dict(info)
    extra["n"] = 0
    extra["role"] = role
    extra["intent"] = role
    await pr.set_session(uid, claim_id=int(claim["id"]), mode="photos", extra=extra)
    await _push(uid, text_wait_photo(0, 0), pr.photo_keyboard(0))


@router.callback_query(F.data == pr.PR_CANT)
async def on_cant_add(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    session = await pr.get_session(uid) or {}
    extra = dict(session.get("extra") or {})
    extra["intent"] = ROLE_RECO
    await pr.set_session(uid, claim_id=None, mode="how", extra=extra)
    await _edit(cb, text_cant_add(), pr.cant_add_keyboard(await _bot_username()))


@router.callback_query(F.data == pr.PR_OWNER)
async def on_owner(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    session = await pr.get_session(uid) or {}
    extra = dict(session.get("extra") or {})
    extra["intent"] = ROLE_OWNER
    await pr.set_session(uid, claim_id=None, mode=session.get("mode") or "choose", extra=extra)
    if extra.get("chat_id"):
        try:
            info = await _info_from_chat_id(int(extra["chat_id"]), uid)
        except Exception:
            info = extra
        info.update({k: extra[k] for k in extra if k not in info})
        await _begin_proofs(cb, uid, info)
        return
    await _try_advance(cb, uid)


@router.callback_query(F.data == pr.PR_RECO)
async def on_reco(cb: CallbackQuery) -> None:
    try:
        await cb.answer()
    except Exception:
        pass
    uid = int(cb.from_user.id)
    session = await pr.get_session(uid) or {}
    extra = dict(session.get("extra") or {})
    extra["intent"] = ROLE_RECO
    await pr.set_session(uid, claim_id=None, mode=session.get("mode") or "choose", extra=extra)
    if extra.get("chat_id"):
        try:
            info = await _info_from_chat_id(int(extra["chat_id"]), uid)
        except Exception:
            info = extra
        info.update({k: extra[k] for k in extra if k not in info})
        await _begin_proofs(cb, uid, info)
        return
    await _try_advance(cb, uid)


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
    await _edit(cb, text_cancelled(), pr.after_cancel_keyboard())


def message_matches_photo(message: Message) -> bool:
    if not message or getattr(message.chat, "type", None) != "private":
        return False
    return bool(pr.image_file_id(message))


async def _finish_photos(message: Message, uid: int, claim: dict, extra: dict) -> None:
    title = claim.get("chat_title") or extra.get("title") or ""
    username = claim.get("chat_username") or extra.get("username") or ""
    extra = _claim_extra(claim, extra)
    if claim["role"] == ROLE_OWNER:
        await pr.set_session(uid, claim_id=int(claim["id"]), mode="pending", extra=extra)
        await message.answer(text_after_proofs_owner(), reply_markup=pr.after_owner_keyboard(), parse_mode="HTML")
        return
    await pr.set_session(uid, claim_id=int(claim["id"]), mode="wait_confirm", extra=extra)
    await message.answer(
        text_after_photos_reco(title),
        reply_markup=pr.after_reco_keyboard(username),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def on_wait_photo(message: Message) -> None:
    uid = int(message.from_user.id)
    session = await pr.get_session(uid)
    if not session or session.get("mode") != "photos" or not session.get("claim_id"):
        return
    claim = await pr.claim_by_id(int(session["claim_id"]))
    if not claim or claim["status"] != ST_PHOTOS:
        if claim and claim["status"] == ST_EXPIRED:
            await message.answer(text_photos_expired(), reply_markup=pr.after_cancel_keyboard(), parse_mode="HTML")
            await pr.clear_session(uid)
        return
    have = len(claim.get("photos") or [])
    extra = dict(session.get("extra") or {})
    if looks_like_help(getattr(message, "text", None)):
        await message.answer(text_wait_photo(have, have), reply_markup=pr.photo_keyboard(have), parse_mode="HTML")
        return
    album_id = getattr(message, "media_group_id", None)
    if album_id and _album_used.get(uid) == str(album_id):
        return
    file_id = pr.image_file_id(message)
    if not file_id:
        kind = pr.photo_noise_kind(message)
        await message.answer(text_need_photo(kind), reply_markup=pr.photo_keyboard(have), parse_mode="HTML")
        return
    async with _photo_lock(uid):
        claim = await pr.claim_by_id(int(session["claim_id"]))
        if not claim or claim["status"] != ST_PHOTOS:
            return
        if album_id:
            if _album_used.get(uid) == str(album_id):
                return
            _album_used[uid] = str(album_id)
        before = len(claim.get("photos") or [])
        claim = await pr.add_photo(int(claim["id"]), file_id)
        have = len(claim.get("photos") or [])
        extra = _claim_extra(claim, extra)
        extra["n"] = have
        await pr.set_session(uid, claim_id=int(claim["id"]), mode="photos", extra=extra)
        if have == before:
            await message.answer(text_need_photo("dup"), reply_markup=pr.photo_keyboard(have), parse_mode="HTML")
            return
        if have < PHOTOS_REQUIRED:
            await message.answer(text_wait_photo(have, have), reply_markup=pr.photo_keyboard(have), parse_mode="HTML")
            return
    await _finish_photos(message, uid, claim, extra)


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
        if claim["status"] in {ST_PENDING, ST_PHOTOS, ST_LIVE}:
            await message.reply(text_owner_no_confirm(), parse_mode="HTML")
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
            await bot.send_message(
                int(claim["user_id"]),
                text_after_proofs_reco(),
                reply_markup=pr.after_owner_keyboard(),
                parse_mode="HTML",
            )
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
        try:
            await bot.send_message(
                int(claim["user_id"]),
                text_confirm_no_first(),
                reply_markup=pr.after_reco_keyboard(claim.get("chat_username") or ""),
                parse_mode="HTML",
            )
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
            await bot.send_message(
                int(claim["user_id"]),
                text_confirm_no_second(),
                reply_markup=pr.hub_only_keyboard(),
                parse_mode="HTML",
            )
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
        if adder:
            try:
                bot = await _bot()
                info = await _inspect_chat(bot, chat_id)
                info["added_by"] = adder
                info["joined_at"] = datetime.now(timezone.utc)
                await _begin_role_dm(int(adder), info)
            except Exception:
                title = getattr(chat, "title", None) or str(chat_id)
                try:
                    bot = await _bot()
                    await bot.send_message(
                        int(adder),
                        text_bot_joined(title),
                        reply_markup=pr.joined_keyboard(),
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass
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
        if old not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            who = getattr(event.from_user, "id", None)
            mem = await pr.get_membership(chat_id)
            seen: list[int] = []
            for cand in (who, (mem or {}).get("last_added_by")):
                if cand and int(cand) not in seen:
                    seen.append(int(cand))
            try:
                bot = await _bot()
                info = await _inspect_chat(bot, chat_id)
                info["added_by"] = (mem or {}).get("last_added_by") or who
                info["joined_at"] = (mem or {}).get("last_joined_at")
            except Exception:
                return
            for cand in seen:
                session = await pr.get_session(cand) or {}
                if session.get("mode") in LINK_MODES:
                    try:
                        await _begin_role_dm(cand, info)
                    except Exception:
                        pass
                    break


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
        await bot.send_message(
            int(user_id),
            text_accepted(term_days),
            reply_markup=pr.after_owner_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
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
