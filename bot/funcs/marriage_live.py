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
    BTN_RIBBON,
    BTN_RIBBON_DO,
    BTN_RIBBON_KEEP,
    BTN_RIBBON_OFF,
    BTN_CARD_LEAVE,
    BTN_GEST,
    BTN_FEAST,
    BTN_GIFT,
    button_rows,
    screen_of_item,
    award_plan,
    care_code,
    due_period,
    quiet_pay,
    GIFT_ALERT,
    gift_text,
    shop_group,
    SHOP_HOME,
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
    TAKE_WORD,
    VERB_PRICE,
    BTN_TONE,
    BTN_TOP,
    BTN_WHAT,
    BTN_YES,
    BUY_PRICE,
    BUY_WORD,
    BUSY,
    CREATOR_ONLY,
    CRAFT_BTN,
    EXPIRED,
    FARM_BTN,
    HEART,
    HOLD_TEXT,
    HOW_TEXT,
    LEAVE_ASK,
    LEAVE_OK,
    LEAVE_THEM,
    LIST_ROW,
    LIST_TITLE,
    NEED_REPLY,
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
    REFUSED,
    SPARK,
    RP,
    RP_DONE,
    RP_NEED_WED,
    RP_ONLY_PAIR,
    RP_PAY_ASK,
    RP_POOR,
    RP_WAIT,
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
    FEAST_EARLY,
    FEAST_ENVELOPE,
    FEAST_FUND_SHORT,
    FEAST_KEEPER_EMPTY,
    FEAST_KEEPER_HOLD,
    FEAST_KEEPER_MISS,
    FEAST_KEEPER_OK,
    FEAST_NONE,
    FEAST_READY,
    FEAST_SORRY,
    GEST_TEXT,
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
    quiet_wish,
    bond_line,
    talk_line,
)
from bot.funcs.marriage_rules import (
    MSK,
    classify,
    mention_in,
    person_html,
    quiet_visible,
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
    verb_wait,
    wait_left_text,
    wedding_date,
    wedding_price,
    which_wedding,
    own_ribbon,
    ribbon_ask,
    ribbon_gone,
    ribbon_home,
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


def _kb(name: str, show=(), **slots) -> InlineKeyboardMarkup:
    """Кнопки экрана из дизайна: подпись, цвет и значок."""
    rows = []
    for row in button_rows(name, show, **slots):
        rows.append([
            _btn(btn["text"], btn["data"], btn.get("style") or "default", btn.get("icon") or "")
            for btn in row
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _kb_ask(book_id: int) -> InlineKeyboardMarkup:
    return _kb("ask_free", book_id=book_id)


def _kb_card(token: str, tone_on: bool, leave: bool = True, feast: bool = False) -> InlineKeyboardMarkup:
    show = []
    if feast:
        show.append("feast")
    if leave:
        show.append("leave")
    return _kb("card", show, token=token)


def _kb_leave(token: str) -> InlineKeyboardMarkup:
    return _kb("leave_ask", token=token)


def _kb_pay(verb_id: str, amount: str) -> InlineKeyboardMarkup:
    return _kb("rp_pay", verb_id=verb_id, amount=amount)


def _use_label(row) -> str:
    have = int(row.get("have") or 0)
    text = str(row.get("use") or TAKE_WORD)
    if have > 0:
        text += " · " + str(have)
    return text[:64]


def _buy_label(row) -> str:
    price = int(row.get("price") or 0)
    return BUY_PRICE.format(price=price) if price else BUY_WORD


def _kb_gifts(rows) -> InlineKeyboardMarkup:
    """Подписи, цвет и значок — с экрана предмета в marriage_design."""
    buttons = []
    for row in rows:
        have = int(row.get("have") or 0)
        if row.get("rite") and have <= 0:
            continue
        price = int(row.get("price") or 0)
        screen = screen_of_item(row.get("id"))
        buy_ok = not row.get("rite") and bool(row.get("buy"))
        if not screen:
            if buy_ok:
                buttons.append([
                    _btn(_buy_label(row), f"mrg:gbuy:{row['id']}", "success"),
                    _btn(_use_label(row), f"mrg:guse:{row['id']}", "primary"),
                ])
            else:
                buttons.append([_btn(_use_label(row), f"mrg:guse:{row['id']}", "primary")])
            continue
        for line in button_rows(screen, price=price, have=have):
            built = []
            for btn in line:
                data = str(btn.get("data") or "")
                buying = ":gbuy:" in data
                if buying and not buy_ok:
                    continue
                text = str(btn.get("text") or "")
                if buying and price and str(price) not in text:
                    text = text + " · " + str(price)
                if not buying and have > 0 and str(have) not in text:
                    text = text + " · " + str(have)
                built.append(_btn(text[:64], data, btn.get("style") or "default", btn.get("icon") or ""))
            if built:
                buttons.append(built)
    buttons.extend(_kb("shop_back").inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _shelf_face(name: str, go: str) -> dict:
    for row in button_rows(name):
        for btn in row:
            parts = str(btn.get("data") or "").split(":")
            if len(parts) >= 2 and parts[1] == go:
                return btn
    return {}


def _kb_back() -> InlineKeyboardMarkup:
    return _kb("back")


def _kb_tone(token: str) -> InlineKeyboardMarkup:
    return _kb("tone", token=token)


def _kb_gest(token: str, cfg: dict) -> InlineKeyboardMarkup:
    prices = {item["id"]: int(verb_price(item, cfg) or 0) for item in RP}
    rows = []
    for row in button_rows("gest", token=token):
        built = []
        for btn in row:
            text = btn["text"]
            parts = str(btn["data"]).split(":")
            if len(parts) >= 3 and parts[1] == "act" and prices.get(parts[2], 0) > 0:
                text = VERB_PRICE.format(label=text, price=prices[parts[2]])
            built.append(_btn(text, btn["data"], btn.get("style") or "default", btn.get("icon") or ""))
        if built:
            rows.append(built)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _kb_guide(extra: str = "", name: str = "what") -> InlineKeyboardMarkup:
    return _kb(name, ("play",) if extra == "play" else ())


def _kb_ribbon(mode: str) -> InlineKeyboardMarkup:
    name = {"ask": "ribbon_ask", "worn": "ribbon_worn"}.get(mode, "ribbon_none")
    return _kb(name)


def _kb_roster(kind: str) -> InlineKeyboardMarkup:
    return _kb("top" if kind == "top" else "list")


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
            if getattr(query, "_mrg_sent", False):
                await _note(query, ALERT_RETRY)
            else:
                await query.answer(ALERT_RETRY, show_alert=True)
        except Exception:
            pass


async def _on_text(message) -> bool:
    text = getattr(message, "text", None) or ""
    kind = classify(text)
    try:
        reply = getattr(message, "reply_to_message", None)
        target = getattr(reply, "from_user", None) if reply is not None else None
        if target is not None and message.from_user is not None and not getattr(target, "is_bot", False):
            if int(target.id) != int(message.from_user.id):
                gesture = bool(kind and kind.get("kind") == "rp")
                if gesture:
                    await store.mark_reply(_pool(), int(message.from_user.id), int(target.id))
                else:
                    note = await store.reply_touch(_pool(), int(message.from_user.id), int(target.id), text)
                    if note:
                        await _reply(message, f"{HEART} <b>{note}</b>")
    except Exception:
        pass
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
    if name == "ribbon_off":
        await _ribbon_phrase(message)
        return True
    if name == "rp":
        return await _rp(message, kind["rp"], kind.get("note") or "", kind.get("verb") or "")
    return False


_QUIET_REPLIES = {}


def keep_names_quiet(message) -> None:
    """Следующая общая рп-фраза не отвечает на сообщение партнёра и не будит его."""
    chat = getattr(getattr(message, "chat", None), "id", None)
    mid = getattr(message, "message_id", None)
    if not chat or not mid:
        return
    _QUIET_REPLIES[(int(chat), int(mid))] = True
    if len(_QUIET_REPLIES) > 300:
        _QUIET_REPLIES.clear()
        _QUIET_REPLIES[(int(chat), int(mid))] = True


def consume_quiet(message) -> bool:
    chat = getattr(getattr(message, "chat", None), "id", None)
    mid = getattr(message, "message_id", None)
    if not chat or not mid:
        return False
    return bool(_QUIET_REPLIES.pop((int(chat), int(mid)), False))


async def _reply(message, text: str, markup=None) -> None:
    await message.reply(
        quiet_visible(text),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=markup,
    )


async def _ribbon_phrase(message) -> None:
    pool = _pool()
    live = await store.live_for(pool, message.from_user.id)
    if not live:
        await _reply(message, _fill(NOT_MARRIED))
        return
    if not live.get("id"):
        await _reply(message, "🎀 <b>Лента открывается в новом браке.</b>")
        return
    if own_ribbon(live, message.from_user.id):
        await _reply(message, ribbon_ask(), _kb_ribbon("ask"))
        return
    await _reply(message, ribbon_home(False), _kb_ribbon("none"))


async def _on_ribbon(query, token: str, user_id: int, pool) -> None:
    live = await store.live_for(pool, user_id)
    if not live:
        await _note(query, ALERT_NO_MARRIAGE)
        return
    if not live.get("id"):
        await _note(query, "Лента открывается в новом браке.")
        return
    worn = own_ribbon(live, user_id)
    if token == "stay":
        await _on_mine(query, pool)
        return
    if token == "off":
        if not worn:
            await query.answer()
            await _edit(query, ribbon_home(False), _kb_ribbon("none"))
            return
        if not await store.set_own_ribbon(pool, int(live["id"]), user_id, False):
            await _note(query, ALERT_RETRY)
            return
        await query.answer("Лента снята.")
        await _edit(query, ribbon_gone(), _kb_ribbon("gone"))
        return
    if token == "ask":
        if not worn:
            await query.answer()
            await _edit(query, ribbon_home(False), _kb_ribbon("none"))
            return
        await query.answer()
        await _edit(query, ribbon_ask(), _kb_ribbon("ask"))
        return
    await query.answer()
    await _edit(query, ribbon_home(worn), _kb_ribbon("worn" if worn else "none"))


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
        quiet_visible(text),
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

    async def _spark_now():
        if live.get("id") and cfg.get("sparkOn", True):
            return await store.spark_sync(pool, live, uid, cfg, 0, True)
        return None

    spark, found = await asyncio.gather(_spark_now(), store.names(pool, [uid, other]))
    a = found.get(uid) or person_html(uid, getattr(user, "first_name", "") or "", getattr(user, "username", "") or "")
    b = found.get(other) or person_html(other, "игрок")
    when = live.get("live_at") or datetime.now(MSK)
    token = str(live["id"]) if live.get("id") else "old"
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
    extra = bond_line(live.get("bond"), live.get("proposer_id"), uid, b)
    if extra:
        text += "\n" + extra
    if live.get("thread_on"):
        text += "\n" + f"{HEART} <b>Нить на месте</b>"
    if own_ribbon(live, uid):
        text += "\n🎀 <b>Лента на вас</b>"
    if "talk_payer" in live:
        today = datetime.now(MSK).date()
        you_key = "talk_payer" if int(live["payer_id"]) == uid else "talk_partner"
        them_key = "talk_partner" if you_key == "talk_payer" else "talk_payer"
        def _spoke(value):
            if value is None:
                return False
            if isinstance(value, datetime):
                return value.date() == today
            return value == today
        text += "\n" + talk_line(_spoke(live.get(you_key)), _spoke(live.get(them_key)))
    streak = int(((spark or {}).get("state") or {}).get("spark_days") or live.get("spark_days") or 0)
    holiday = due_period(streak, live.get("wish_done"), cfg.get("periods"))
    if holiday:
        text += "\n" + HEART + " <b>" + str(holiday["name"]) + "</b>"
    return text, _kb_card(token, bool(spark), True, bool(holiday)), live


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
    return text, _kb_guide("play", "spark_nav")


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
        if shares_general_rp(item, verb) or quiet_wish(verb):
            return False
        await _reply(message, _fill(PROJECT_OFF))
        return True
    if not await store.chat_enabled(pool, message.chat.id):
        if shares_general_rp(item, verb) or quiet_wish(verb):
            return False
        await _reply(message, _fill(OFF))
        return True
    live = await store.live_for(pool, message.from_user.id)
    if not live:
        if shares_general_rp(item, verb) or quiet_wish(verb):
            return False
        await _reply(message, _fill(RP_NEED_WED))
        return True
    other = _other(live, int(message.from_user.id))
    if int(target.id) != other:
        if shares_general_rp(item, verb) or quiet_wish(verb):
            return False
        await _reply(message, _fill(RP_ONLY_PAIR))
        return True
    day = datetime.now(MSK).date()
    shared = shares_general_rp(item, verb)
    wait_left = await store.rp_wait_left(pool, message.from_user.id, item["id"], verb_wait(item, cfg))
    if wait_left > 0:
        await _reply(message, _fill(RP_WAIT, title=verb_button(item["id"], 0, verb_care(item, cfg)), left=wait_left_text(wait_left)))
        return True
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
    await store.rp_touch(pool, message.from_user.id, item["id"])
    gain = await _give_care(pool, live, message.from_user.id, item, cfg)
    if shared:
        if gain:
            await _reply(message, gain.lstrip("\n"))
        keep_names_quiet(message)
        return False
    a = await _html(pool, message.from_user)
    b = await _html(pool, target)
    text = rp_html(item, a, b, note) + gain
    await _reply(message, text)
    return True


async def _gift_screen(query, user_id: int, pool, cfg, live, note: str = "", shelf: str = "") -> None:
    rows = await store.gift_stock(pool, user_id, cfg)
    kind = shelf if shelf in ("fire", "mark", "meal", "quiet") else ""
    if not kind:
        await _edit(query, SHOP_HOME, _kb("shop"))
        return
    picked = [row for row in rows if shop_group(row) == kind]
    text = gift_text(picked, own_ribbon(live, user_id) and kind == "mark", cfg, kind)
    clean = str(note or "").strip()
    if clean:
        text = clean + "\n" + text
    await _edit(query, text, _kb_gifts(picked))


async def _on_bag(query, user_id: int, pool, shelf: str = "0") -> None:
    live = await store.live_for(pool, user_id)
    if not live:
        await _note(query, ALERT_NO_MARRIAGE)
        return
    if not live.get("id"):
        await _note(query, GIFT_ALERT["old"])
        return
    await query.answer()
    await _gift_screen(query, user_id, pool, await _cfg(), live, shelf=shelf)


async def _on_gift_buy(query, kind: str, user_id: int, pool) -> None:
    cfg = await _cfg()
    gift = next((row for row in gift_catalog(cfg) if row["id"] == kind), None)
    if gift is None and kind == "quiet":
        from bot.funcs.marriage_design import quiet_row
        gift = quiet_row(cfg)
    if gift is None:
        await _note(query, GIFT_ALERT["bad"])
        return
    live = await store.live_for(pool, user_id)
    if not live:
        await _note(query, ALERT_NO_MARRIAGE)
        return
    if not live.get("id"):
        await _note(query, GIFT_ALERT["old"])
        return
    price = int(gift["price"] or 0)
    plan = quiet_pay(gift["name"], price, cfg) if kind == "quiet" else None
    taken = await _take(
        query.bot, user_id, price, int(live.get("chat_id") or 0), gift["name"],
        int(plan["chat"]) if plan else 0, int(plan["fund"]) if plan else 0,
    )
    if taken == "poor":
        await _note(query, "Кутов не хватает. Предмет не куплен.")
        return
    if taken == "miss":
        await _note(query, ALERT_TILL)
        return
    try:
        granted = await store.grant_gift(pool, user_id, kind, 1)
    except Exception:
        granted = False
    if not granted:
        await _refund(
            query.bot, user_id, price,
            int(plan["chat"]) if plan else 0, int(plan["fund"]) if plan else 0,
        )
        await _note(query, ALERT_TILL)
        return
    if price > 0:
        await store.note_money(pool, kind, user_id, price, int(live.get("chat_id") or 0))
    await query.answer()
    await _gift_screen(query, user_id, pool, cfg, live, shelf=shop_group(gift or {}))


async def _place_hint_message(query, kind: str, cfg) -> None:
    from aiogram.types import WebAppInfo

    from bot.funcs.marriage_design import gift_catalog, place_hint
    from bot.funcs.webapp_links import section_button_fields

    row = next((item for item in gift_catalog(cfg) if item.get("id") == kind), None)
    hint = place_hint((row or {}).get("name1"))
    message = getattr(query, "message", None)
    if not hint or message is None:
        return
    where = hint.get("where") or "farm"
    face = _shelf_face("item_seedcuke", "guse") if where == "farm" else _shelf_face("item_cuke", "guse")
    label = (face or {}).get("text") or (FARM_BTN if where == "farm" else CRAFT_BTN)
    private = getattr(getattr(message, "chat", None), "type", "") == "private"
    fields = section_button_fields(label, where, private=private, icon=(face or {}).get("icon") or "")
    web_app_url = fields.pop("web_app_url", None)
    if web_app_url:
        fields["web_app"] = WebAppInfo(url=web_app_url)
    button = InlineKeyboardButton(**fields)
    await message.reply(
        hint["text"],
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
    )


async def _on_gift_use(query, kind: str, user_id: int, pool) -> None:
    cfg = await _cfg()
    live = await store.live_for(pool, user_id)
    if not live:
        await _note(query, ALERT_NO_MARRIAGE)
        return
    result = await store.use_gift(pool, live, user_id, kind, cfg)
    if not result.get("ok"):
        reason = result.get("reason") or "bad"
        from bot.funcs.marriage_design import alert_text
        await _note(query, alert_text(reason, cfg))
        if reason in ("field", "cook"):
            await _place_hint_message(query, kind, cfg)
        return
    from bot.funcs.marriage_design import use_card
    face = next((item for item in gift_catalog(cfg) if item.get("id") == kind), None) or {}
    note = str(result.get("alert") or "")
    if not note and kind == "ribbon":
        note = "Лента на вас."
    elif not note and int(result.get("care") or 0) > 0:
        note = "+" + str(int(result.get("care") or 0))
    card = use_card(face.get("emoji") or "", face.get("name") or "Предмет", note) if note else ""
    fresh = await store.live_for(pool, user_id)
    await _gift_screen(query, user_id, pool, cfg, fresh or live, card, shop_group(face))


async def _dispatch(query) -> None:
    data = str(getattr(query, "data", "") or "")
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "mrg":
        await query.answer()
        return
    _arm(query)
    await query.answer()
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
        await _on_bag(query, user_id, pool, token)
        return
    if action == "gbuy":
        await _on_gift_buy(query, token, user_id, pool)
        return
    if action == "feast":
        await _on_feast(query, user_id, pool)
        return
    if action == "wish":
        await _on_wish(query, token, user_id, pool)
        return
    if action == "guse":
        await _on_gift_use(query, token, user_id, pool)
        return
    if action == "rib":
        await _on_ribbon(query, token, user_id, pool)
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
    guide = {"what": ("what", WHAT_TEXT), "use": ("how", HOW_TEXT), "hold": ("hold", HOLD_TEXT)}
    if action in guide:
        name, text = guide[action]
        await query.answer()
        await _edit(query, text, _kb_guide("play" if live else "", name))
        return
    if not live:
        await _note(query, ALERT_NO_MARRIAGE)
        return
    if action == "care":
        if not live.get("id"):
            await query.answer()
            await _edit(query, _fill(TONE_OLD), _kb_back())
            return
        await query.answer()
        await _edit(
            query,
            GEST_TEXT,
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
    nav = {"lvl": "level_nav", "stat": "stat_nav"}.get(action, "spark_nav")
    await query.answer()
    await _edit(query, text, _kb_guide("play", nav))


async def _on_mine(query, pool) -> None:
    cfg = await _cfg()
    screen = await _screen(pool, query.from_user, cfg)
    if screen is None:
        await _note(query, ALERT_NO_MARRIAGE)
        return
    text, markup, _live = screen
    await query.answer()
    await _edit(query, text, markup)


async def _on_tone_btn(query, token: str, user_id: int, pool) -> None:
    live = await store.live_for(pool, user_id)
    if not live or not _owns(live, token, user_id):
        await _note(query, ALERT_NOT_PAIR if live else ALERT_NO_MARRIAGE)
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
        await _note(query, ALERT_NOT_PAIR if live else ALERT_NO_MARRIAGE)
        return
    cfg = await _cfg()
    await query.answer()
    await _edit(
        query,
        GEST_TEXT,
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
        await _note(query, ALERT_NOT_PAIR if live else ALERT_NO_MARRIAGE)
        return
    cfg = await _cfg()
    item = dict(item)
    item["price"] = verb_price(item, cfg)
    other = _other(live, user_id)
    limit = int(cfg.get("rpPerDay") or 1)
    day = datetime.now(MSK).date()
    if await store.rp_taken(pool, user_id, other, item["id"], day, limit):
        await _note(query, ALERT_RP_TODAY)
        return
    price = int(item.get("price") or 0)
    if price > 0 and not cfg.get("enabled", True):
        await _note(query, ALERT_OFF)
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
        await _note(query, ALERT_RP_TODAY)
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
        await _note(query, ALERT_CLOSED)
        return
    payer = int(row["payer_id"])
    partner = int(row["partner_id"])
    if action in ("yes", "no") and user_id != partner:
        await _note(query, ALERT_NOT_INVITED)
        return
    if action == "stop" and user_id != payer:
        await _note(query, ALERT_NOT_PAYER)
        return
    if action == "stop":
        closed = await store.close_ask(pool, book_id, "stop")
        if not closed:
            await _note(query, ALERT_CLOSED)
            return
        await query.answer()
        await _edit(query, _fill(STOPPED))
        return
    if action == "no":
        closed = await store.close_ask(pool, book_id, "no")
        if not closed:
            await _note(query, ALERT_CLOSED)
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
            await _note(query, ALERT_BUSY)
            return
        if too_old:
            await _note(query, f"{minutes} мин. Заявка закрыта.")
            return
        await _note(query, ALERT_CLOSED)
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
        await _note(query, ALERT_TILL)
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
        await _note(query, ALERT_NOT_PAIR if live else ALERT_NO_MARRIAGE)
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
        await _note(query, ALERT_NOT_PAIR if live else ALERT_NO_MARRIAGE)
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
            quiet_visible(_fill(LEAVE_THEM, a=a)),
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
        await _note(query, ALERT_OFF)
        return
    live = await store.live_for(pool, user_id)
    if not live:
        await _note(query, ALERT_NO_MARRIAGE)
        return
    other = _other(live, user_id)
    price = int(item.get("price") or 0)
    day = datetime.now(MSK).date()
    if await store.rp_taken(pool, user_id, other, item["id"], day, limit):
        await _note(query, ALERT_RP_TODAY)
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
        await _note(query, ALERT_TILL_RP)
        return
    if not await store.mark_rp(pool, user_id, other, item["id"], day, limit):
        if price > 0:
            await _refund(query.bot, user_id, price)
        await _note(query, ALERT_RP_TODAY)
        return
    if price > 0:
        await store.note_money(pool, "rp", user_id, price, int(live.get("chat_id") or 0))
    names = await store.names(pool, [user_id, other])
    a = names.get(user_id) or person_html(user_id, query.from_user.first_name or "", query.from_user.username or "")
    b = names.get(other) or person_html(other, "игрок")
    text = rp_html(item, a, b) + await _give_care(pool, live, user_id, item, cfg)
    await query.answer()
    await _edit(query, text, _kb_back())


async def _holiday(pool, user_id, cfg, live):
    spark = None
    if cfg.get("sparkOn", True):
        spark = await store.spark_sync(pool, live, user_id, cfg, 0, True)
    streak = int(((spark or {}).get("state") or {}).get("spark_days") or live.get("spark_days") or 0)
    return due_period(streak, live.get("wish_done"), cfg.get("periods"))


async def _on_feast(query, user_id: int, pool) -> None:
    cfg = await _cfg()
    live = await store.live_for(pool, user_id)
    if not live or not live.get("id"):
        await _note(query, ALERT_NO_MARRIAGE)
        return
    holiday = await _holiday(pool, user_id, cfg, live)
    if not holiday:
        from bot.funcs.marriage_design import FEAST_NONE
        await _note(query, FEAST_NONE)
        return
    from bot.funcs.marriage_design import feast_screen
    shown = []
    enabled = set()
    for row in cfg.get("prizes") or []:
        if not row.get("on"):
            continue
        if row.get("id") == "premium6" and int(holiday["day"]) < 30:
            continue
        shown.append(row)
        enabled.add(str(row.get("id") or ""))
    show = ("late",) if int(holiday.get("day") or 0) >= 30 else ()
    buttons = []
    for line in button_rows("feast", show):
        built = []
        for btn in line:
            data = str(btn.get("data") or "")
            parts = data.split(":")
            if len(parts) >= 3 and parts[1] == "wish" and parts[2] not in enabled:
                continue
            built.append(_btn(str(btn.get("text") or "")[:64], data, btn.get("style") or "default", btn.get("icon") or ""))
        if built:
            buttons.append(built)
    await query.answer()
    await _edit(query, feast_screen(holiday.get("name"), holiday.get("day"), shown), InlineKeyboardMarkup(inline_keyboard=buttons))


async def _spend_fund(bot, chat_id: int, amount: int) -> bool:
    if int(amount) <= 0:
        return True
    db = _db()
    have = await db.get_chatbalance(bot, int(chat_id))
    if int(have or 0) < int(amount):
        return False
    return bool(await db.add_to_chatbalance(bot, int(chat_id), -int(amount)))


async def _fulfill(query, info: dict, cfg: dict, holiday: dict, pool) -> None:
    prize_id = str(info.get("locked") or "")
    fund_chat = int(cfg.get("giftFundChat") or 0)
    fund = int(await _db().get_chatbalance(query.bot, fund_chat) or 0)
    copies = 1
    if prize_id == "care":
        stock = await store.stock_named(pool, care_code(info["day"]))
        copies = 2
    elif prize_id == "ribbon":
        stock = await store.stock_named(pool, "mrribbon")
    elif prize_id in ("premium3", "premium6"):
        stock = await store.stock_premium(pool, prize_id)
    else:
        stock = {"price": 0, "remains": 0, "name1": ""}
    if copies > 1:
        if int(stock.get("remains") or 0) < copies:
            stock = {**stock, "remains": 0}
        else:
            stock = {**stock, "price": int(stock.get("price") or 0) * copies}
    plan = award_plan(
        prize_id, fund, stock.get("price"), stock.get("remains"),
        cfg.get("envelopeKut"), cfg.get("extraKut"),
    )
    if plan["do"] in ("short", "keeper_empty"):
        keeper = await store.find_named_user(pool, cfg.get("premiumKeeper") or "")
        if plan["do"] == "keeper_empty" and keeper:
            try:
                from bot.funcs.marriage_design import FEAST_KEEPER_MISS
                await query.bot.send_message(
                    keeper,
                    FEAST_KEEPER_MISS.format(heart=HEART, name=holiday.get("name") or "Праздник"),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        await _note(
            query,
            FEAST_FUND_SHORT if plan["do"] == "short" else FEAST_KEEPER_EMPTY,
        )
        return
    if not await _spend_fund(query.bot, fund_chat, int(plan.get("amount") or 0)):
        await _note(query, FEAST_FUND_SHORT)
        return
    payer, partner = int(info["payer_id"]), int(info["partner_id"])
    amount = int(plan.get("amount") or 0)
    ok = False
    note = FEAST_READY
    if plan["do"] in ("kut", "sorry"):
        half = amount // 2
        shares = [(payer, amount - half), (partner, half)]
        ok = await store.give_kut(pool, shares)
        note = FEAST_SORRY if plan["do"] == "sorry" else FEAST_ENVELOPE.format(amount=amount)
    elif plan["do"] == "shop":
        people = [payer] if prize_id == "ribbon" else [payer, partner]
        ok = await store.give_named(pool, people, stock.get("name1"), 1)
    elif plan["do"] == "keeper":
        keeper = await store.find_named_user(pool, cfg.get("premiumKeeper") or "")
        ok = bool(keeper) and await store.give_named(pool, [keeper], stock.get("name1"), 1)
        note = FEAST_KEEPER_OK.format(name=cfg.get("premiumKeeper") or "создатель")
        if ok:
            try:
                await query.bot.send_message(
                    keeper,
                    FEAST_KEEPER_HOLD.format(heart=HEART, name=holiday.get("name") or "Праздник"),
                    parse_mode="HTML",
                )
            except Exception:
                pass
    if not ok:
        if amount > 0:
            await _db().add_to_chatbalance(query.bot, fund_chat, amount)
        await _note(query, ALERT_TILL)
        return
    await store.finish_wish(pool, int(info["book_id"]), int(info["day"]))
    await query.answer()
    await _edit(query, f"{HEART} <b>{note}</b>", _kb_back())


async def _on_wish(query, prize_id: str, user_id: int, pool) -> None:
    cfg = await _cfg()
    live = await store.live_for(pool, user_id)
    if not live or not live.get("id"):
        await _note(query, ALERT_NO_MARRIAGE)
        return
    holiday = await _holiday(pool, user_id, cfg, live)
    if not holiday:
        from bot.funcs.marriage_design import FEAST_NONE
        await _note(query, FEAST_NONE)
        return
    if prize_id == "premium6" and int(holiday["day"]) < 30:
        from bot.funcs.marriage_design import FEAST_EARLY
        await _note(query, FEAST_EARLY)
        return
    info = await store.choose_wish(pool, user_id, prize_id, int(holiday["day"]), cfg)
    if not info.get("ok") or not info.get("locked"):
        await _note(query, info.get("alert") or GIFT_ALERT["bad"])
        return
    await _fulfill(query, info, cfg, holiday, pool)


async def _take(bot, user_id: int, price: int, chat_id: int, cause: str, fund_chat: int = 0, fund_part: int = 0) -> str:
    if price <= 0:
        return "free"
    fund_part = max(0, min(int(fund_part or 0), int(price)))
    project = int(price) - fund_part
    db = _db()
    new_balance = await db.update_user_balance(int(user_id), f"-{int(price)}")
    if new_balance is None:
        return "poor"
    from bot.config.config import GAME_COMMISSION_CHAT_ID
    if project > 0:
        ok = await db.add_to_chatbalance(bot, int(GAME_COMMISSION_CHAT_ID), project)
        if not ok:
            await db.update_user_balance(int(user_id), f"+{int(price)}")
            return "miss"
    if fund_part > 0:
        ok = await db.add_to_chatbalance(bot, int(fund_chat), fund_part)
        if not ok:
            if project > 0:
                await db.add_to_chatbalance(bot, int(GAME_COMMISSION_CHAT_ID), -project)
            await db.update_user_balance(int(user_id), f"+{int(price)}")
            return "miss"
    try:
        await db.cutehistory_minus(int(user_id), int(price), cause, chat_id)
    except Exception:
        pass
    return "ok"


async def _refund(bot, user_id: int, price: int, fund_chat: int = 0, fund_part: int = 0) -> None:
    if price <= 0:
        return
    fund_part = max(0, min(int(fund_part or 0), int(price)))
    project = int(price) - fund_part
    db = _db()
    try:
        await db.update_user_balance(int(user_id), f"+{int(price)}")
    except Exception:
        return
    try:
        from bot.config.config import GAME_COMMISSION_CHAT_ID
        if project > 0:
            await db.add_to_chatbalance(bot, int(GAME_COMMISSION_CHAT_ID), -project)
        if fund_part > 0:
            await db.add_to_chatbalance(bot, int(fund_chat), -fund_part)
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


async def _note(query, text: str) -> None:
    clean = " ".join(str(text or "").replace("<", " ").replace(">", " ").split())
    if clean:
        await _edit(query, HEART + " <b>" + clean + "</b>", _kb_back())


def _arm(query) -> None:
    """Первый answer снимает часики. Повторный Telegram уже не ждёт.

    CallbackQuery заморожен: поле answer нельзя заменить обычным присваиванием.
    """
    if getattr(query, "_mrg_arm", False):
        return
    object.__setattr__(query, "_mrg_arm", True)
    original = query.answer

    async def answer(*_args, **_kwargs):
        if getattr(query, "_mrg_sent", False):
            return
        object.__setattr__(query, "_mrg_sent", True)
        try:
            await original()
        except Exception:
            pass

    object.__setattr__(query, "answer", answer)


async def _edit(query, text: str, markup=_CLEAR) -> None:
    try:
        await query.message.edit_text(
            quiet_visible(text),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )
    except Exception:
        return
