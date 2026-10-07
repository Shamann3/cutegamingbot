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
    BOT,
    BTN_BACK,
    BTN_CARD_LEAVE,
    BTN_GEST,
    BTN_GIFT,
    GIFT_ALERT,
    gift_text,
    BTN_HOLD,
    BTN_HOW,
    BTN_LEAVE,
    BTN_LEVEL,
    BTN_LIST,
    BTN_MINE,
    BTN_NO,
    BTN_SKIP,
    BTN_STAY,
    BTN_STAT,
    BTN_STOP,
    BTN_TONE,
    BTN_TOP,
    BTN_WHAT,
    BTN_YES,
    BUSY,
    CREATOR_ONLY,
    EXPIRED,
    HEART,
    HOLD_TEXT,
    HOW_TEXT,
    LEAVE_ASK,
    LEAVE_OK,
    LEAVE_THEM,
    LIST_ROW,
    LIST_TITLE,
    NEED_REPLY,
    NO_ID,
    NOT_FOUND,
    NOT_MARRIED,
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
    DOT_ID,
    RED_ID,
    REFUSED,
    SPARK,
    RP,
    RP_DONE,
    RP_NEED_WED,
    RP_ONLY_PAIR,
    RP_PAY_ASK,
    RP_POOR,
    RP_TOMORROW,
    SELF,
    SKIP_OK,
    STAY_OK,
    STOPPED,
    TILL_CLOSED,
    TONE_OLD,
    TOP_EMPTY,
    TOP_LIMIT,
    TOP_ROW,
    TOP_TITLE,
    WED_OK_FREE,
    WED_OK_PAID,
    WHAT_TEXT,
    card_text,
    care_line,
    pay_label,
    spark_fire,
    spark_home,
    spark_level,
    spark_stats,
    tone_text,
    verb_button,
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
    tone_brief,
    tone_label,
    tone_score,
    each_share,
    gift_catalog,
    verb_care,
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
    base = {"heart": HEART, "spark": SPARK}
    base.update(vals)
    return tmpl.format(**base)


def _btn(text: str, data: str, style: str = "default", icon: str = "") -> InlineKeyboardButton:
    kwargs = {"text": text, "callback_data": data, "style": style}
    if icon:
        kwargs["icon_custom_emoji_id"] = icon
    return InlineKeyboardButton(**kwargs)


_CLEAR = InlineKeyboardMarkup(inline_keyboard=[])


def _kb_ask(book_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            _btn(BTN_NO, f"mrg:no:{book_id}", "danger", NO_ID),
            _btn(BTN_YES, f"mrg:yes:{book_id}", "success", RED_ID),
        ],
        [_btn(BTN_STOP, f"mrg:stop:{book_id}", "primary")],
    ])


def _kb_card(token: str, tone_on: bool, leave: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [_btn(BTN_GEST, f"mrg:gest:{token}", "primary", RED_ID)],
        [
            _btn(BTN_TONE, "mrg:fire:0", "default", DOT_ID),
            _btn(BTN_LEVEL, "mrg:lvl:0", "default"),
        ],
        [
            _btn(BTN_WHAT, "mrg:what:0", "default"),
            _btn(BTN_HOW, "mrg:use:0", "default"),
        ],
        [_btn(BTN_HOLD, "mrg:hold:0", "default")],
        [_btn(BTN_STAT, "mrg:stat:0", "default")],
        [_btn(BTN_GIFT, "mrg:bag:0", "default", RED_ID)],
    ]
    if leave:
        rows.append([_btn(BTN_CARD_LEAVE, f"mrg:warn:{token}", "danger", NO_ID)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _kb_leave(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn(BTN_STAY, f"mrg:stay:{token}", "success", RED_ID),
        _btn(BTN_LEAVE, f"mrg:leave:{token}", "danger", NO_ID),
    ]])


def _kb_pay(verb_id: str, amount: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(pay_label(amount), f"mrg:pay:{verb_id}", "success", RED_ID)],
        [_btn(BTN_SKIP, f"mrg:skip:{verb_id}", "default")],
    ])


def _kb_gifts(rows) -> InlineKeyboardMarkup:
    buttons = []
    for row in rows:
        buttons.append([
            _btn(row["buy"], f"mrg:gbuy:{row['id']}", "success", RED_ID),
            _btn(row["use"], f"mrg:guse:{row['id']}", "primary", RED_ID),
        ])
    buttons.append([_btn(BTN_BACK, "mrg:mine:0", "default")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn(BTN_BACK, "mrg:mine:0", "default"),
    ]])


def _kb_tone(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(verb_button("hug"), f"mrg:act:hug:{token}", "primary", RED_ID)],
        [_btn(BTN_BACK, "mrg:mine:0", "default")],
    ])


def _kb_gest(token: str, cfg: dict) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for item in RP:
        price = verb_price(item, cfg)
        care = verb_care(item, cfg)
        row.append(_btn(
            verb_button(item["id"], price, care),
            f"mrg:act:{item['id']}:{token}",
            "primary",
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        _btn(BTN_HOLD, "mrg:hold:0", "default"),
        _btn(BTN_BACK, "mrg:mine:0", "default"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _kb_guide(extra: str = "") -> InlineKeyboardMarkup:
    rows = [[
        _btn(BTN_WHAT, "mrg:what:0", "default"),
        _btn(BTN_HOW, "mrg:use:0", "default"),
    ], [
        _btn(BTN_HOLD, "mrg:hold:0", "default"),
        _btn(BTN_BACK, "mrg:mine:0", "default"),
    ]]
    if extra == "play":
        rows.insert(0, [_btn(BTN_GEST, "mrg:care:0", "primary", RED_ID)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _kb_roster(kind: str) -> InlineKeyboardMarkup:
    other = (
        _btn(BTN_LIST, "mrg:list:0", "primary")
        if kind == "top"
        else _btn(BTN_TOP, "mrg:top:0", "primary")
    )
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn(BTN_MINE, "mrg:mine:0", "default"),
        other,
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
    if name == "tone":
        await _tone(message)
        return True
    if name == "leave":
        await _leave_ask(message)
        return True
    if name == "top":
        await _roster(message, "top")
        return True
    if name == "list":
        await _roster(message, "list")
        return True
    if name == "wed":
        await _wed(message, kind.get("tail") or "")
        return True
    if name == "rp":
        return await _rp(message, kind["rp"], kind.get("note") or "", kind.get("verb") or "")
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
            free=int(cfg.get("freeWeddings") or 0),
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
    cfg = await _cfg()
    screen = await _screen(pool, message.from_user, cfg)
    if screen is None:
        await _reply(message, _fill(NOT_MARRIED))
        return
    text, markup, _live = screen
    await _reply(message, text, markup)


async def _tone(message) -> None:
    pool = _pool()
    cfg = await _cfg()
    view = await _tone_screen(pool, message.from_user, cfg)
    if view is None:
        live = await store.live_for(pool, message.from_user.id)
        if not live:
            await _reply(message, _fill(NOT_MARRIED))
            return
        if not live.get("id"):
            await _reply(message, _fill(TONE_OLD))
            return
        await _card(message)
        return
    text, markup = view
    await _reply(message, text, markup)


async def _screen(pool, user, cfg):
    live = await store.live_for(pool, user.id)
    if not live:
        return None
    uid = int(user.id)
    other = _other(live, uid)
    found = await store.names(pool, [uid, other])
    a = found.get(uid) or person_html(uid, getattr(user, "first_name", "") or "", getattr(user, "username", "") or "")
    b = found.get(other) or person_html(other, "игрок")
    when = live.get("live_at") or datetime.now(MSK)
    token = str(live["id"]) if live.get("id") else "old"
    spark = None
    if live.get("id") and cfg.get("sparkOn", True):
        spark = await store.spark_sync(pool, live, uid, cfg, 0, True)
    if spark:
        text = spark_home(
            a, b,
            together_label(when, datetime.now(MSK)),
            wedding_date(when),
            spark, spark["you"], spark["partner_care"], b,
        )
    else:
        text = card_text(
            a, b,
            together_label(when, datetime.now(MSK)),
            wedding_date(when),
            "",
        )
    return text, _kb_card(token, bool(spark), True), live


async def _tone_screen(pool, user, cfg):
    live = await store.live_for(pool, user.id)
    if not live or not live.get("id") or not cfg.get("sparkOn", True):
        return None
    spark = await store.spark_sync(pool, live, user.id, cfg, 0, True)
    if not spark:
        return None
    other = _other(live, int(user.id))
    names = await store.names(pool, [other])
    partner = names.get(other) or person_html(other, "игрок")
    text = spark_fire(
        spark, spark["you"], spark["partner_care"], partner, int(cfg.get("rescueHours") or 12),
    )
    return text, _kb_guide("play")


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


async def _roster(message, kind: str) -> None:
    if not _group(message):
        await _reply(message, _fill(PRIVATE, minutes=PROPOSAL_MINUTES))
        return
    pool = _pool()
    if not await store.chat_enabled(pool, message.chat.id):
        await _reply(message, _fill(OFF))
        return
    cfg = await _cfg()
    text = await _roster_text(pool, message.chat.id, cfg, kind)
    await _reply(message, text, _kb_roster(kind))


async def _roster_text(pool, chat_id: int, cfg: dict, kind: str) -> str:
    rows = await store.top_pairs(pool, chat_id, int(cfg.get("topLimit") or TOP_LIMIT))
    if not rows:
        return _fill(TOP_EMPTY)
    ids = []
    for row in rows:
        ids.extend((row["a"], row["b"]))
    found = await store.names(pool, ids)
    now = datetime.now(MSK)
    lines = [_fill(TOP_TITLE if kind == "top" else LIST_TITLE)]
    show_spark = kind == "list" and bool(cfg.get("sparkOn", True))
    for i, row in enumerate(rows, start=1):
        span = together_label(row["since"], now)
        if span != "вместе":
            span = f"вместе {span}"
        a = found.get(row["a"]) or person_html(row["a"], "игрок")
        b = found.get(row["b"]) or person_html(row["b"], "игрок")
        if show_spark and row.get("spark_days") is not None:
            fade = row.get("fade_until")
            fading = False
            if isinstance(fade, datetime):
                moment = fade if fade.tzinfo is not None else fade.replace(tzinfo=MSK)
                fading = moment > now
            if fading:
                meta = f"{span} · искра гаснет"
            elif int(row.get("spark_days") or 0) > 0:
                meta = f"{span} · искра {int(row['spark_days'])}"
            else:
                meta = f"{span} · новая искра"
            lines.append(LIST_ROW.format(n=i, a=a, b=b, meta=meta))
        else:
            lines.append(TOP_ROW.format(n=i, a=a, b=b, span=span))
    return "\n".join(lines)


async def _touch_tone(pool, live, cfg):
    if not cfg.get("toneOn") or not live or not live.get("id"):
        return None
    try:
        return await store.add_tone(
            pool,
            int(live["id"]),
            datetime.now(MSK).date(),
            int(cfg.get("toneDecay") or 0),
            int(cfg.get("toneGain") or 0),
        )
    except Exception:
        return None


async def _give_care(pool, live, user_id, item, cfg) -> str:
    if not live or not live.get("id") or not cfg.get("sparkOn", True):
        return ""
    amount = verb_care(item, cfg)
    if amount <= 0:
        return ""
    try:
        view = await store.spark_sync(pool, live, user_id, cfg, amount, True)
    except Exception:
        return ""
    if not view:
        return ""
    return "\n" + care_line(
        amount,
        view["you"],
        view["need"],
        view["partner_care"],
        bool(view.get("saved")),
        bool(view.get("both_done")),
        bool(view.get("fading")) and not view.get("saved"),
    )


def _tone_after_line(live, cfg, score) -> str:
    today = datetime.now(MSK).date()
    brief = tone_brief(
        live.get("tone_points") if live.get("tone_points") is not None else int(cfg.get("toneStart") or 80),
        live.get("tone_day"),
        today,
        int(cfg.get("toneDecay") or 0),
        int(cfg.get("toneGain") or 0),
    )
    if not brief["fresh"]:
        return f"Тонус {int(score)} · сегодня уже учтён"
    return f"Тонус {int(score)} · {tone_label(int(score))}"


async def _rp(message, item: dict, note: str, verb: str = "") -> bool:
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
        if shares_general_rp(item, verb):
            return False
        await _reply(message, _fill(PROJECT_OFF))
        return True
    if not await store.chat_enabled(pool, message.chat.id):
        if shares_general_rp(item, verb):
            return False
        await _reply(message, _fill(OFF))
        return True
    live = await store.live_for(pool, message.from_user.id)
    if not live:
        if shares_general_rp(item, verb):
            return False
        await _reply(message, _fill(RP_NEED_WED))
        return True
    other = _other(live, int(message.from_user.id))
    if int(target.id) != other:
        if shares_general_rp(item, verb):
            return False
        await _reply(message, _fill(RP_ONLY_PAIR))
        return True
    day = datetime.now(MSK).date()
    if await store.rp_taken(pool, message.from_user.id, other, item["id"], day, limit):
        await _reply(message, _fill(RP_TOMORROW, title=verb_button(item["id"])))
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
            _fill(RP_PAY_ASK, title=verb_button(item["id"]), price=_kut(price)),
            _kb_pay(item["id"], _kut(price)),
        )
        return True
    if not await store.mark_rp(pool, message.from_user.id, other, item["id"], day, limit):
        await _reply(message, _fill(RP_TOMORROW, title=verb_button(item["id"])))
        return True
    a = await _html(pool, message.from_user)
    b = await _html(pool, target)
    text = rp_html(item, a, b, note)
    text += await _give_care(pool, live, message.from_user.id, item, cfg)
    await _reply(message, text)
    return True


async def _gift_screen(query, user_id: int, pool, cfg, live) -> None:
    rows = await store.gift_stock(pool, user_id, cfg)
    await _edit(
        query,
        gift_text(rows, bool(live.get("ribbon"))),
        _kb_gifts(rows),
    )


async def _on_bag(query, user_id: int, pool) -> None:
    live = await store.live_for(pool, user_id)
    if not live:
        await query.answer(ALERT_NO_MARRIAGE, show_alert=True)
        return
    if not live.get("id"):
        await query.answer(GIFT_ALERT["old"], show_alert=True)
        return
    await query.answer()
    await _gift_screen(query, user_id, pool, await _cfg(), live)


async def _on_gift_buy(query, kind: str, user_id: int, pool) -> None:
    cfg = await _cfg()
    gift = next((row for row in gift_catalog(cfg) if row["id"] == kind), None)
    if gift is None:
        await query.answer(GIFT_ALERT["bad"], show_alert=True)
        return
    live = await store.live_for(pool, user_id)
    if not live:
        await query.answer(ALERT_NO_MARRIAGE, show_alert=True)
        return
    if not live.get("id"):
        await query.answer(GIFT_ALERT["old"], show_alert=True)
        return
    price = int(gift["price"] or 0)
    taken = await _take(query.bot, user_id, price, int(live.get("chat_id") or 0), gift["name"])
    if taken == "poor":
        await query.answer("Кутов не хватает. Предмет не куплен.", show_alert=True)
        return
    if taken == "miss":
        await query.answer(ALERT_TILL, show_alert=True)
        return
    try:
        granted = await store.grant_gift(pool, user_id, kind, 1)
    except Exception:
        granted = False
    if not granted:
        await _refund(query.bot, user_id, price)
        await query.answer(ALERT_TILL, show_alert=True)
        return
    if price > 0:
        await store.note_money(pool, kind, user_id, price, int(live.get("chat_id") or 0))
    await query.answer()
    await _gift_screen(query, user_id, pool, cfg, live)


async def _on_gift_use(query, kind: str, user_id: int, pool) -> None:
    cfg = await _cfg()
    live = await store.live_for(pool, user_id)
    if not live:
        await query.answer(ALERT_NO_MARRIAGE, show_alert=True)
        return
    result = await store.use_gift(pool, live, user_id, kind, cfg)
    if not result.get("ok"):
        await query.answer(GIFT_ALERT.get(result.get("reason") or "bad", GIFT_ALERT["bad"]), show_alert=True)
        return
    care = int(result.get("care") or 0)
    if kind == "ribbon":
        await query.answer("Лента на паре.")
    elif care > 0:
        await query.answer(f"+{care} заботы только вам. Лишнее сгорит по вашей норме.", show_alert=True)
    else:
        await query.answer()
    fresh = await store.live_for(pool, user_id)
    await _gift_screen(query, user_id, pool, cfg, fresh or live)


async def _dispatch(query) -> None:
    data = str(getattr(query, "data", "") or "")
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "mrg":
        await query.answer()
        return
    action, token = parts[1], parts[2]
    user_id = int(query.from_user.id)
    pool = _pool()
    if action == "act":
        if len(parts) < 4:
            await query.answer()
            return
        await _on_act(query, parts[2], parts[3], user_id, pool)
        return
    if action == "skip":
        await query.answer()
        await _edit(query, _fill(SKIP_OK), _kb_back())
        return
    if action == "mine":
        await _on_mine(query, pool)
        return
    if action in ("fire", "lvl", "stat", "what", "use", "hold", "care"):
        await _on_guide(query, action, pool)
        return
    if action == "tone":
        await _on_tone_btn(query, token, user_id, pool)
        return
    if action == "gest":
        await _on_gest(query, token, user_id, pool)
        return
    if action == "bag":
        await _on_bag(query, user_id, pool)
        return
    if action == "gbuy":
        await _on_gift_buy(query, token, user_id, pool)
        return
    if action == "guse":
        await _on_gift_use(query, token, user_id, pool)
        return
    if action in ("list", "top"):
        await _on_roster_btn(query, action, pool)
        return
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


async def _on_guide(query, action: str, pool) -> None:
    user = query.from_user
    cfg = await _cfg()
    live = await store.live_for(pool, user.id)
    if action == "what":
        await query.answer()
        await _edit(query, WHAT_TEXT, _kb_guide("play" if live else ""))
        return
    if action == "use":
        await query.answer()
        await _edit(query, HOW_TEXT, _kb_guide("play" if live else ""))
        return
    if action == "hold":
        await query.answer()
        await _edit(query, HOLD_TEXT, _kb_guide("play" if live else ""))
        return
    if not live:
        await query.answer(ALERT_NO_MARRIAGE, show_alert=True)
        return
    if action == "care":
        if not live.get("id"):
            await query.answer()
            await _edit(query, _fill(TONE_OLD), _kb_back())
            return
        await query.answer()
        await _edit(
            query,
            _fill("{heart} <b>Поддержать пару</b>\n{spark} <i>Число на кнопке — забота. Её нужно дать и вам, и паре.</i>"),
            _kb_gest(str(live["id"]), cfg),
        )
        return
    spark = await store.spark_sync(pool, live, user.id, cfg, 0, True) if live.get("id") else None
    if spark is None:
        await query.answer()
        await _edit(query, _fill(TONE_OLD), _kb_back())
        return
    other = _other(live, int(user.id))
    names = await store.names(pool, [other])
    partner = names.get(other) or person_html(other, "игрок")
    if action == "lvl":
        text = spark_level(spark)
    elif action == "stat":
        text = spark_stats(spark, spark["you"], spark["partner_care"], partner)
    else:
        text = spark_fire(spark, spark["you"], spark["partner_care"], partner, int(cfg.get("rescueHours") or 12))
    await query.answer()
    await _edit(query, text, _kb_guide("play"))


async def _on_mine(query, pool) -> None:
    cfg = await _cfg()
    screen = await _screen(pool, query.from_user, cfg)
    if screen is None:
        await query.answer(ALERT_NO_MARRIAGE, show_alert=True)
        return
    text, markup, _live = screen
    await query.answer()
    await _edit(query, text, markup)


async def _on_tone_btn(query, token: str, user_id: int, pool) -> None:
    live = await store.live_for(pool, user_id)
    if not live or not _owns(live, token, user_id):
        await query.answer(ALERT_NOT_PAIR if live else ALERT_NO_MARRIAGE, show_alert=True)
        return
    cfg = await _cfg()
    view = await _tone_screen(pool, query.from_user, cfg)
    if view is None:
        await query.answer()
        if not live.get("id"):
            await _edit(query, _fill(TONE_OLD), _kb_back())
            return
        screen = await _screen(pool, query.from_user, cfg)
        if screen is None:
            return
        text, markup, _row = screen
        await _edit(query, text, markup)
        return
    text, markup = view
    await query.answer()
    await _edit(query, text, markup)


async def _on_gest(query, token: str, user_id: int, pool) -> None:
    live = await store.live_for(pool, user_id)
    if not live or not _owns(live, token, user_id):
        await query.answer(ALERT_NOT_PAIR if live else ALERT_NO_MARRIAGE, show_alert=True)
        return
    cfg = await _cfg()
    await query.answer()
    await _edit(
        query,
        _fill("{heart} <b>Поддержать пару</b>\n{spark} <i>Число на кнопке — забота. Её дают оба.</i>"),
        _kb_gest(token, cfg),
    )


async def _on_roster_btn(query, kind: str, pool) -> None:
    message = getattr(query, "message", None)
    if message is None or not _group(message):
        await query.answer()
        await _edit(query, _fill(PRIVATE))
        return
    if not await store.chat_enabled(pool, message.chat.id):
        await query.answer()
        await _edit(query, _fill(OFF))
        return
    cfg = await _cfg()
    text = await _roster_text(pool, message.chat.id, cfg, kind)
    await query.answer()
    await _edit(query, text, _kb_roster(kind))


async def _on_act(query, verb_id: str, token: str, user_id: int, pool) -> None:
    item = rp_by_id(verb_id)
    if item is None:
        await query.answer()
        return
    live = await store.live_for(pool, user_id)
    if not live or not _owns(live, token, user_id):
        await query.answer(ALERT_NOT_PAIR if live else ALERT_NO_MARRIAGE, show_alert=True)
        return
    cfg = await _cfg()
    item = dict(item)
    item["price"] = verb_price(item, cfg)
    other = _other(live, user_id)
    limit = int(cfg.get("rpPerDay") or 1)
    day = datetime.now(MSK).date()
    if await store.rp_taken(pool, user_id, other, item["id"], day, limit):
        await query.answer(ALERT_RP_TODAY, show_alert=True)
        return
    price = int(item.get("price") or 0)
    if price > 0 and not cfg.get("enabled", True):
        await query.answer(ALERT_OFF, show_alert=True)
        return
    if price > 0:
        have = await _db().get_user_balance(user_id)
        if have is None or int(have) < price:
            await query.answer()
            await _edit(query, _fill(
                RP_POOR, title=verb_button(item["id"]), price=_kut(price), have=_kut(have or 0),
            ), _kb_back())
            return
        await query.answer()
        await _edit(
            query,
            _fill(RP_PAY_ASK, title=verb_button(item["id"]), price=_kut(price)),
            _kb_pay(item["id"], _kut(price)),
        )
        return
    if not await store.mark_rp(pool, user_id, other, item["id"], day, limit):
        await query.answer(ALERT_RP_TODAY, show_alert=True)
        return
    names = await store.names(pool, [user_id, other])
    a = names.get(user_id) or person_html(user_id, query.from_user.first_name or "", query.from_user.username or "")
    b = names.get(other) or person_html(other, "игрок")
    text = rp_html(item, a, b) + await _give_care(pool, live, user_id, item, cfg)
    await query.answer()
    await _edit(query, text, _kb_back())


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
    rows = cfg.get("levels") if isinstance(cfg.get("levels"), list) else []
    goal = int(rows[0].get("goal") or 10) if rows and isinstance(rows[0], dict) else 10
    each = each_share(goal)
    text = _fill(WED_OK_FREE, a=a, b=b, each=each) if price <= 0 else _fill(WED_OK_PAID, a=a, b=b, price=_kut(price), each=each)
    await query.answer()
    await _edit(query, text, _kb_card(str(book_id), bool(cfg.get("toneOn", True)), leave=False))


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
        kept = str(live["id"]) if live.get("id") else "old"
        cfg = await _cfg()
        await query.answer()
        await _edit(query, _fill(STAY_OK), _kb_card(kept, bool(cfg.get("toneOn", True)) and kept != "old"))
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
    names = await store.names(pool, [user_id, other])
    a = names.get(user_id) or person_html(user_id, query.from_user.first_name or "", query.from_user.username or "")
    b = names.get(other) or person_html(other, "игрок")
    text = rp_html(item, a, b) + await _give_care(pool, live, user_id, item, cfg)
    await query.answer()
    await _edit(query, text, _kb_back())


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
