# -*- coding: utf-8 -*-
"""Живые браки: фразы в чате и кнопки заявки.

Тексты и цены — в marriage_design. Сюда их не копируют.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.funcs import marriage_store as store
from bot.funcs.marriage_design import (
    ALERT_BUSY,
    ALERT_CLOSED,
    ALERT_EXPIRED,
    ALERT_NO_MARRIAGE,
    ALERT_OFF,
    ALERT_NOT_INVITED,
    ALERT_NOT_PAIR,
    ALERT_NOT_PAYER,
    ALERT_RETRY,
    ALERT_RP_TODAY,
    ALERT_TILL,
    ALERT_TILL_RP,
    ALREADY_THEM,
    ALREADY_YOU,
    BTN_CARD_LEAVE,
    BTN_LEAVE,
    BTN_NO,
    BTN_STAY,
    BTN_STOP,
    BTN_YES,
    BOT,
    BUSY,
    CARD,
    CREATOR_ONLY,
    DOVE,
    EXPIRED,
    GONE,
    LEAVE_ASK,
    LEAVE_OK,
    LEAVE_THEM,
    NEED_REPLY,
    NOT_FOUND,
    NOT_MARRIED,
    NO,
    HEART,
    OFF,
    OFF_ALREADY,
    OFF_OK,
    ON_ALREADY,
    ON_OK,
    POOR,
    POOR_LATE,
    PRIVATE,
    PROJECT_OFF,
    PROPOSAL_MINUTES,
    PROPOSE_FREE,
    PROPOSE_PAID,
    REFUSED,
    RING,
    RP_NEED_WED,
    RP_ONLY_PAIR,
    RP_PAY_ASK,
    RP_POOR,
    RP_TOMORROW,
    SELF,
    STAY_OK,
    STOPPED,
    TILL_CLOSED,
    TOP_EMPTY,
    TOP_LIMIT,
    TOP_ROW,
    TOP_TITLE,
    WED_OK_FREE,
    WED_OK_PAID,
    pay_label,
)
from bot.funcs.marriage_rules import (
    MSK,
    classify,
    mention_in,
    person_html,
    rp_by_id,
    shares_general_rp,
    as_aware,
    together_label,
    verb_list,
    verb_price,
    wedding_date,
    wedding_price,
    which_wedding,
    rp_html,
)


def _db():
    from bot.db_create.db import db as database
    return database


def _pool():
    return getattr(_db(), "pool", None)


async def _cfg() -> dict:
    try:
        return await store.load_settings(_pool())
    except Exception:
        from bot.funcs.marriage_rules import settings_view
        return settings_view(None)


async def current_help_text() -> str:
    from bot.funcs.marriage_design import help_page
    try:
        return help_page(await _cfg())
    except Exception:
        return help_page(None)


def _fill(tmpl: str, **vals) -> str:
    base = {"ring": RING, "dove": DOVE, "no": NO, "heart": HEART}
    base.update(vals)
    return tmpl.format(**base)


_CLEAR = InlineKeyboardMarkup(inline_keyboard=[])


def _kb_ask(book_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=BTN_YES, callback_data=f"mrg:yes:{book_id}"),
            InlineKeyboardButton(text=BTN_NO, callback_data=f"mrg:no:{book_id}"),
        ],
        [InlineKeyboardButton(text=BTN_STOP, callback_data=f"mrg:stop:{book_id}")],
    ])


def _kb_card(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=BTN_CARD_LEAVE, callback_data=f"mrg:warn:{token}"),
    ]])


def _kb_leave(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=BTN_STAY, callback_data=f"mrg:stay:{token}"),
        InlineKeyboardButton(text=BTN_LEAVE, callback_data=f"mrg:leave:{token}"),
    ]])


def _kb_pay(verb_id: str, amount: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=pay_label(amount), callback_data=f"mrg:pay:{verb_id}"),
    ]])


async def on_text(message) -> bool:
    """True — фраза брака уже отвечена, общее рп для неё не нужно."""
    try:
        return await _on_text(message)
    except Exception as e:
        print(f"[marriage] {type(e).__name__}: {e}")
        return False


async def dispatch(query) -> None:
    try:
        await _dispatch(query)
    except Exception as e:
        print(f"[marriage] кнопка {type(e).__name__}: {e}")
        try:
            await query.answer(ALERT_RETRY, show_alert=True)
        except Exception:
            pass


async def _on_text(message) -> bool:
    text = getattr(message, "text", None) or ""
    kind = classify(text)
    if kind is None or message.from_user is None:
        return False
    name = kind["kind"]
    if name == "on":
        await _switch(message, True)
        return True
    if name == "off":
        await _switch(message, False)
        return True
    if name == "card":
        await _card(message)
        return True
    if name == "leave":
        await _leave_ask(message)
        return True
    if name == "top":
        await _top(message)
        return True
    if name == "wed":
        await _wed(message, kind.get("tail") or "")
        return True
    if name == "rp":
        return await _rp(message, kind["rp"], kind.get("note") or "")
    return False


async def _reply(message, text: str, markup=None) -> None:
    await message.reply(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=markup,
    )


async def _switch(message, enabled: bool) -> None:
    if not _group(message):
        await _reply(message, _fill(PRIVATE, minutes=PROPOSAL_MINUTES))
        return
    db = _db()
    creator = await db.get_group_creator(message.chat.id)
    if creator is None or int(creator) != int(message.from_user.id):
        await _reply(message, _fill(CREATOR_ONLY))
        return
    pool = _pool()
    cfg = await _cfg()
    if enabled and not cfg.get("enabled", True):
        await _reply(message, _fill(PROJECT_OFF))
        return
    current = await store.chat_enabled(pool, message.chat.id)
    if current is enabled:
        await _reply(message, _fill(ON_ALREADY if enabled else OFF_ALREADY))
        return
    await store.set_chat(pool, message.chat.id, enabled)
    await _reply(message, _fill(ON_OK if enabled else OFF_OK))


async def _wed(message, tail: str) -> None:
    if not _group(message):
        await _reply(message, _fill(PRIVATE, minutes=PROPOSAL_MINUTES))
        return
    pool = _pool()
    cfg = await _cfg()
    minutes = int(cfg.get("proposalMinutes") or PROPOSAL_MINUTES)
    if not cfg.get("enabled", True):
        await _reply(message, _fill(PROJECT_OFF))
        return
    if not await store.chat_enabled(pool, message.chat.id):
        await _reply(message, _fill(OFF))
        return
    await store.expire_asks(pool, minutes)
    partner = await _partner(message, tail)
    if partner is False:
        await _reply(message, _fill(NEED_REPLY, minutes=minutes))
        return
    if partner is None:
        await _reply(message, _fill(NOT_FOUND))
        return
    if getattr(partner, "is_bot", False):
        await _reply(message, _fill(BOT))
        return
    payer_id = int(message.from_user.id)
    partner_id = int(partner.id)
    if partner_id == payer_id:
        await _reply(message, _fill(SELF))
        return
    mine = await store.live_for(pool, payer_id)
    if mine:
        other = _other(mine, payer_id)
        names = await store.names(pool, [other])
        await _reply(message, _fill(ALREADY_YOU, b=names.get(other) or person_html(other, "игрок")))
        return
    theirs = await store.live_for(pool, partner_id)
    if theirs:
        b = await _html(pool, partner)
        await _reply(message, _fill(ALREADY_THEM, b=b))
        return
    if await store.pending_between(pool, payer_id, partner_id):
        await _reply(message, _fill(BUSY))
        return
    done = await store.count_done(pool, payer_id)
    price = wedding_price(done, cfg)
    if price > 0:
        have = await _db().get_user_balance(payer_id)
        if have is None or int(have) < price:
            await _reply(message, _fill(POOR, price=_kut(price), have=_kut(have or 0)))
            return
    book_id = await store.open_ask(pool, payer_id, partner_id, message.chat.id, price)
    if book_id is None:
        again = await store.live_for(pool, payer_id)
        if again:
            other = _other(again, payer_id)
            names = await store.names(pool, [other])
            await _reply(message, _fill(ALREADY_YOU, b=names.get(other) or person_html(other, "игрок")))
            return
        if await store.live_for(pool, partner_id):
            await _reply(message, _fill(ALREADY_THEM, b=await _html(pool, partner)))
            return
        await _reply(message, _fill(BUSY))
        return
    a = await _html(pool, message.from_user)
    b = await _html(pool, partner)
    if price <= 0:
        text = _fill(
            PROPOSE_FREE,
            a=a, b=b,
            which=which_wedding(done),
            minutes=minutes,
        )
    else:
        text = _fill(
            PROPOSE_PAID,
            a=a, b=b,
            which=which_wedding(done),
            price=_kut(price),
            minutes=minutes,
        )
    sent = await message.answer(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=_kb_ask(book_id),
    )
    await store.set_message(pool, book_id, sent.message_id)
    _arm(message.bot, message.chat.id, sent.message_id, book_id, minutes)


def _arm(bot, chat_id: int, message_id: int, book_id: int, minutes: int) -> None:
    async def _fade() -> None:
        try:
            await asyncio.sleep(max(1, int(minutes)) * 60)
            row = await store.close_ask(_pool(), book_id, "gone")
            if not row:
                return
            await bot.edit_message_text(
                _fill(EXPIRED, minutes=int(minutes)),
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=_CLEAR,
            )
        except Exception:
            return

    try:
        asyncio.get_running_loop().create_task(_fade())
    except RuntimeError:
        return


async def _card(message) -> None:
    pool = _pool()
    live = await store.live_for(pool, message.from_user.id)
    if not live:
        await _reply(message, _fill(NOT_MARRIED))
        return
    uid = int(message.from_user.id)
    other = _other(live, uid)
    found = await store.names(pool, [uid, other])
    a = found.get(uid) or person_html(uid, message.from_user.first_name or "", message.from_user.username or "")
    b = found.get(other) or person_html(other, "игрок")
    when = live.get("live_at") or datetime.now(MSK)
    cfg = await _cfg()
    tone = store.describe_tone(live, datetime.now(MSK).date(), int(cfg.get("toneDecay") or 0), bool(cfg.get("toneOn", True)))
    text = _fill(
        CARD,
        a=a, b=b,
        span=together_label(when, datetime.now(MSK)),
        date=wedding_date(when),
        verbs=verb_list(),
        tone=tone or "Жест раз в сутки пишется ответом на сообщение пары.",
    )
    token = str(live["id"]) if live.get("id") else "old"
    await _reply(message, text, _kb_card(token))


async def _leave_ask(message) -> None:
    pool = _pool()
    live = await store.live_for(pool, message.from_user.id)
    if not live:
        await _reply(message, _fill(NOT_MARRIED))
        return
    other = _other(live, int(message.from_user.id))
    names = await store.names(pool, [other])
    token = str(live["id"]) if live.get("id") else "old"
    await _reply(
        message,
        _fill(LEAVE_ASK, b=names.get(other) or person_html(other, "игрок")),
        _kb_leave(token),
    )


async def _top(message) -> None:
    if not _group(message):
        await _reply(message, _fill(PRIVATE, minutes=PROPOSAL_MINUTES))
        return
    pool = _pool()
    if not await store.chat_enabled(pool, message.chat.id):
        await _reply(message, _fill(OFF))
        return
    cfg = await _cfg()
    rows = await store.top_pairs(pool, message.chat.id, int(cfg.get("topLimit") or TOP_LIMIT))
    if not rows:
        await _reply(message, _fill(TOP_EMPTY))
        return
    ids = []
    for row in rows:
        ids.extend((row["a"], row["b"]))
    found = await store.names(pool, ids)
    now = datetime.now(MSK)
    lines = [_fill(TOP_TITLE)]
    for i, row in enumerate(rows, start=1):
        span = together_label(row["since"], now)
        if span != "вместе":
            span = f"вместе {span}"
        lines.append(TOP_ROW.format(
            n=i,
            a=found.get(row["a"]) or person_html(row["a"], "игрок"),
            b=found.get(row["b"]) or person_html(row["b"], "игрок"),
            span=span,
        ))
    await _reply(message, "\n".join(lines))


async def _touch_tone(pool, live, cfg) -> None:
    if not cfg.get("toneOn") or not live or not live.get("id"):
        return
    try:
        await store.add_tone(
            pool,
            int(live["id"]),
            datetime.now(MSK).date(),
            int(cfg.get("toneDecay") or 0),
            int(cfg.get("toneGain") or 0),
        )
    except Exception:
        return


async def _rp(message, item: dict, note: str) -> bool:
    if not _group(message):
        return False
    cfg = await _cfg()
    item = dict(item)
    item["price"] = verb_price(item, cfg)
    limit = int(cfg.get("rpPerDay") or 1)
    reply = getattr(message, "reply_to_message", None)
    target = getattr(reply, "from_user", None) if reply is not None else None
    if target is None:
        return False
    pool = _pool()
    if not cfg.get("enabled", True):
        if shares_general_rp(item):
            return False
        await _reply(message, _fill(PROJECT_OFF))
        return True
    if not await store.chat_enabled(pool, message.chat.id):
        if shares_general_rp(item):
            return False
        await _reply(message, _fill(OFF))
        return True
    live = await store.live_for(pool, message.from_user.id)
    if not live:
        if shares_general_rp(item):
            return False
        await _reply(message, _fill(RP_NEED_WED))
        return True
    other = _other(live, int(message.from_user.id))
    if int(target.id) != other:
        if shares_general_rp(item):
            return False
        await _reply(message, _fill(RP_ONLY_PAIR))
        return True
    day = datetime.now(MSK).date()
    if await store.rp_taken(pool, message.from_user.id, other, item["id"], day, limit):
        await _reply(message, RP_TOMORROW.format(dove=DOVE, title=item["verbs"][0]))
        return True
    price = int(item.get("price") or 0)
    if price > 0:
        have = await _db().get_user_balance(message.from_user.id)
        if have is None or int(have) < price:
            await _reply(message, _fill(
                RP_POOR, title=item["verbs"][0], price=_kut(price), have=_kut(have or 0),
            ))
            return True
        await _reply(
            message,
            RP_PAY_ASK.format(
                emoji=item["emoji"],
                title=item["verbs"][0],
                price=_kut(price),
                dove=DOVE,
                button=pay_label(_kut(price)),
            ),
            _kb_pay(item["id"], _kut(price)),
        )
        return True
    if not await store.mark_rp(pool, message.from_user.id, other, item["id"], day, limit):
        await _reply(message, RP_TOMORROW.format(dove=DOVE, title=item["verbs"][0]))
        return True
    await _touch_tone(pool, live, cfg)
    a = await _html(pool, message.from_user)
    b = await _html(pool, target)
    await _reply(message, rp_html(item, a, b, note))
    return True


async def _dispatch(query) -> None:
    data = str(getattr(query, "data", "") or "")
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "mrg":
        await query.answer()
        return
    action, token = parts[1], parts[2]
    user_id = int(query.from_user.id)
    pool = _pool()
    if action in ("yes", "no", "stop"):
        await _on_ask(query, action, int(token), user_id, pool)
        return
    if action == "warn":
        await _on_warn(query, token, user_id, pool)
        return
    if action in ("leave", "stay"):
        await _on_leave(query, action, token, user_id, pool)
        return
    if action == "pay":
        await _on_pay(query, token, user_id, pool)
        return
    await query.answer()


async def _on_ask(query, action: str, book_id: int, user_id: int, pool) -> None:
    row = await store.get_book(pool, book_id)
    if not row or row["state"] != "ask":
        await query.answer(ALERT_CLOSED, show_alert=True)
        return
    payer = int(row["payer_id"])
    partner = int(row["partner_id"])
    if action in ("yes", "no") and user_id != partner:
        await query.answer(ALERT_NOT_INVITED, show_alert=True)
        return
    if action == "stop" and user_id != payer:
        await query.answer(ALERT_NOT_PAYER, show_alert=True)
        return
    if action == "stop":
        closed = await store.close_ask(pool, book_id, "stop")
        if not closed:
            await query.answer(ALERT_CLOSED, show_alert=True)
            return
        await query.answer()
        await _edit(query, _fill(STOPPED))
        return
    if action == "no":
        closed = await store.close_ask(pool, book_id, "no")
        if not closed:
            await query.answer(ALERT_CLOSED, show_alert=True)
            return
        names = await store.names(pool, [partner])
        await query.answer()
        await _edit(query, _fill(REFUSED, b=names.get(partner) or person_html(partner, "игрок")))
        return
    cfg = await _cfg()
    minutes = int(cfg.get("proposalMinutes") or PROPOSAL_MINUTES)
    claimed = await store.claim_ask(pool, book_id, minutes)
    if not claimed:
        fresh = await store.get_book(pool, book_id)
        created = as_aware(fresh.get("created_at")) if fresh else None
        still_waiting = bool(fresh and fresh.get("state") == "ask" and created)
        too_old = False
        if still_waiting:
            from datetime import timedelta, timezone
            too_old = datetime.now(timezone.utc) - created > timedelta(minutes=minutes)
        if still_waiting and not too_old:
            await query.answer(ALERT_BUSY, show_alert=True)
            return
        if too_old:
            await query.answer(f"Прошло {minutes} минут, заявка закрылась. Куты не списаны.", show_alert=True)
            return
        await query.answer(ALERT_CLOSED, show_alert=True)
        return
    price = int(claimed["price"] or 0)
    taken = await _take(query.bot, payer, price, int(claimed["chat_id"]), "свадьба")
    if taken == "poor":
        await store.finish(pool, book_id, "gone")
        await query.answer()
        await _edit(query, _fill(POOR_LATE, price=_kut(price)))
        return
    if taken == "miss":
        await store.finish(pool, book_id, "gone")
        await query.answer(ALERT_TILL, show_alert=True)
        await _edit(query, _fill(TILL_CLOSED))
        return
    if price > 0:
        await store.mark_charged(pool, book_id)
    await store.finish(
        pool,
        book_id,
        "live",
        tone_points=int(cfg.get("toneStart") or 80),
        tone_day=datetime.now(MSK).date(),
    )
    if price > 0:
        await store.note_money(pool, "wed", payer, price, int(claimed["chat_id"] or 0))
    try:
        await store.mirror_live(pool, payer, partner, int(claimed["chat_id"]))
    except Exception as e:
        print(f"[marriage] старая таблица: {e}")
    names = await store.names(pool, [payer, partner])
    a = names.get(payer) or person_html(payer, "игрок")
    b = names.get(partner) or person_html(partner, "игрок")
    text = _fill(WED_OK_FREE, a=a, b=b) if price <= 0 else _fill(WED_OK_PAID, a=a, b=b, price=_kut(price))
    await query.answer()
    await _edit(query, text)


def _owns(live: dict, token: str, user_id: int) -> bool:
    if int(user_id) not in (int(live["payer_id"]), int(live["partner_id"])):
        return False
    if token == "old":
        return live.get("source") == "old"
    return str(live.get("id")) == token


async def _on_warn(query, token: str, user_id: int, pool) -> None:
    live = await store.live_for(pool, user_id)
    if not live or not _owns(live, token, user_id):
        await query.answer(ALERT_NOT_PAIR if live else ALERT_NO_MARRIAGE, show_alert=True)
        return
    other = _other(live, user_id)
    names = await store.names(pool, [other])
    await query.answer()
    await _edit(
        query,
        _fill(LEAVE_ASK, b=names.get(other) or person_html(other, "игрок")),
        _kb_leave(token),
    )


async def _on_leave(query, action: str, token: str, user_id: int, pool) -> None:
    live = await store.live_for(pool, user_id)
    if not live or not _owns(live, token, user_id):
        await query.answer(ALERT_NOT_PAIR if live else ALERT_NO_MARRIAGE, show_alert=True)
        return
    other = _other(live, user_id)
    if action == "stay":
        await query.answer()
        await _edit(query, _fill(STAY_OK))
        return
    if live.get("id"):
        await store.finish(pool, int(live["id"]), "left")
    else:
        await store.record_old_divorce(pool, int(live["payer_id"]), int(live["partner_id"]), int(live["chat_id"] or 0))
    await store.mirror_end(pool, int(live["payer_id"]), int(live["partner_id"]))
    names = await store.names(pool, [user_id, other])
    a = names.get(user_id) or person_html(user_id, query.from_user.first_name or "", query.from_user.username or "")
    b = names.get(other) or person_html(other, "игрок")
    await query.answer()
    await _edit(query, _fill(LEAVE_OK, a=a, b=b))
    try:
        await query.bot.send_message(
            other,
            _fill(LEAVE_THEM, a=a),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        return


async def _on_pay(query, verb_id: str, user_id: int, pool) -> None:
    item = rp_by_id(verb_id)
    if item is None:
        await query.answer()
        return
    cfg = await _cfg()
    item = dict(item)
    item["price"] = verb_price(item, cfg)
    limit = int(cfg.get("rpPerDay") or 1)
    if not cfg.get("enabled", True):
        await query.answer(ALERT_OFF, show_alert=True)
        return
    live = await store.live_for(pool, user_id)
    if not live:
        await query.answer(ALERT_NO_MARRIAGE, show_alert=True)
        return
    other = _other(live, user_id)
    price = int(item.get("price") or 0)
    day = datetime.now(MSK).date()
    if await store.rp_taken(pool, user_id, other, item["id"], day, limit):
        await query.answer(ALERT_RP_TODAY, show_alert=True)
        return
    taken = await _take(query.bot, user_id, price, int(live.get("chat_id") or 0), "жест брака")
    if taken == "poor":
        have = await _db().get_user_balance(user_id)
        await query.answer()
        await _edit(query, _fill(
            RP_POOR, title=item["verbs"][0], price=_kut(price), have=_kut(have or 0),
        ))
        return
    if taken == "miss":
        await query.answer(ALERT_TILL_RP, show_alert=True)
        return
    if not await store.mark_rp(pool, user_id, other, item["id"], day, limit):
        if price > 0:
            await _refund(query.bot, user_id, price)
        await query.answer(ALERT_RP_TODAY, show_alert=True)
        return
    if price > 0:
        await store.note_money(pool, "rp", user_id, price, int(live.get("chat_id") or 0))
    await _touch_tone(pool, live, cfg)
    names = await store.names(pool, [user_id, other])
    a = names.get(user_id) or person_html(user_id, query.from_user.first_name or "", query.from_user.username or "")
    b = names.get(other) or person_html(other, "игрок")
    await query.answer()
    await _edit(query, rp_html(item, a, b))


async def _take(bot, user_id: int, price: int, chat_id: int, cause: str) -> str:
    if price <= 0:
        return "free"
    db = _db()
    new_balance = await db.update_user_balance(int(user_id), f"-{int(price)}")
    if new_balance is None:
        return "poor"
    from bot.config.config import GAME_COMMISSION_CHAT_ID
    ok = await db.add_to_chatbalance(bot, int(GAME_COMMISSION_CHAT_ID), int(price))
    if not ok:
        await db.update_user_balance(int(user_id), f"+{int(price)}")
        return "miss"
    try:
        await db.cutehistory_minus(int(user_id), int(price), cause, chat_id)
    except Exception:
        pass
    return "ok"


async def _refund(bot, user_id: int, price: int) -> None:
    if price <= 0:
        return
    db = _db()
    try:
        await db.update_user_balance(int(user_id), f"+{int(price)}")
    except Exception:
        return
    try:
        from bot.config.config import GAME_COMMISSION_CHAT_ID
        await db.add_to_chatbalance(bot, int(GAME_COMMISSION_CHAT_ID), -int(price))
    except Exception:
        return


async def _partner(message, tail: str):
    reply = getattr(message, "reply_to_message", None)
    if reply is not None and getattr(reply, "from_user", None) is not None:
        return reply.from_user
    for ent in getattr(message, "entities", None) or []:
        if getattr(ent, "type", "") == "text_mention" and getattr(ent, "user", None) is not None:
            return ent.user
    token = mention_in(tail)
    if not token:
        return False
    if token.isdigit():
        return SimpleNamespace(id=int(token), is_bot=False, first_name="", username="")
    getter = getattr(_db(), "get_user_id_by_username", None)
    if getter is None:
        return None
    found = await getter(token)
    if not found:
        return None
    return SimpleNamespace(id=int(found), is_bot=False, first_name="", username=token)


async def _html(pool, user) -> str:
    first = getattr(user, "first_name", "") or ""
    username = getattr(user, "username", "") or ""
    if first or username:
        return person_html(int(user.id), first, username)
    found = await store.names(pool, [int(user.id)])
    return found.get(int(user.id)) or person_html(int(user.id), "игрок", "")


def _other(live: dict, user_id: int) -> int:
    if int(live["payer_id"]) == int(user_id):
        return int(live["partner_id"])
    return int(live["payer_id"])


def _group(message) -> bool:
    return getattr(getattr(message, "chat", None), "type", "") in ("group", "supergroup")


def _kut(value) -> str:
    try:
        return f"{int(value)}"
    except (TypeError, ValueError):
        return "0"


async def _edit(query, text: str, markup=_CLEAR) -> None:
    try:
        await query.message.edit_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )
    except Exception:
        return
