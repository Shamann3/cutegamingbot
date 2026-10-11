# -*- coding: utf-8 -*-
"""Водные игры: выстрел, защита, шутка и три шага до покупки."""
from __future__ import annotations

import logging
import random
import re
from datetime import datetime, timedelta, timezone

import aiohttp
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.db_create.items_codec import decode_items, encode_items
from bot.funcs.water_games_design import (
    BTN_BACK,
    BTN_EXTEND,
    DAY_CAP,
    DRY_JOKES,
    EXTEND_FEE,
    ITEMS,
    JOKE_SITE,
    PAIR_DAY_MAX,
    PAIR_GAP_SEC,
    PERCENT_HIGH,
    PERCENT_LOW,
    POOR_BALANCE,
    SHIELDS,
    SHOT_CAP,
    TOWEL_HOURS,
    broke_text,
    btn_join,
    button_rows,
    can_shoot,
    choice_label,
    find_button_rows,
    kept_kind,
    extend_empty_text,
    extend_list_text,
    guide_status,
    shield_profile_line,
    extend_pick_text,
    forever_worn_text,
    fresh_instead_text,
    hours_phrase,
    is_water_ask,
    item_by_key,
    joined_until,
    left_phrase,
    missing_item_text,
    poor_fee_text,
    screen_text,
    settle_umbrella,
    word,
    shields_in_bag,
    stacked_text,
    take_amount,
    take_one_item,
    towel_amount,
    wearing_text,
    worn_text,
)
from bot.funcs.webapp_links import section_button_fields
from main import bot1, db, dp

log = logging.getLogger("water_games")

_ready = False
_joke_at = 0


def _item(name1: str) -> dict:
    found = item_by_key(name1)
    if not found:
        raise KeyError(name1)
    return found


def _emoji_icon(value) -> str:
    raw = str(value or "").strip()
    return raw if raw.isdigit() else ""


def _markup(name: str, message, **slots) -> InlineKeyboardMarkup:
    private = getattr(getattr(message, "chat", None), "type", "") == "private"
    rows = []
    for row in button_rows(name, **slots):
        built = []
        for button in row:
            data = button["data"]
            icon = button.get("emoji") or ""
            if data.startswith("web:"):
                built.append(_open_button(button["text"], data[4:], private, button.get("style") or "primary", icon))
            else:
                built.append(_button(button["text"], data, button.get("style") or "default", icon))
        rows.append(built)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _open_button(text: str, startapp: str, private: bool, style: str = "primary", emoji: str = "") -> InlineKeyboardButton:
    fields = section_button_fields(text, startapp, private=private)
    fields.pop("style", None)
    web_app_url = fields.pop("web_app_url", None)
    if web_app_url:
        fields["web_app"] = WebAppInfo(url=web_app_url)
    fields["style"] = style or "primary"
    icon = _emoji_icon(emoji)
    if icon:
        fields["icon_custom_emoji_id"] = icon
    return InlineKeyboardButton(**fields)


def _home_text() -> str:
    return screen_text("home")


def _rules_text() -> str:
    return screen_text(
        "rules",
        low=PERCENT_LOW,
        high=PERCENT_HIGH,
        cap=SHOT_CAP,
        day=DAY_CAP,
        poor=POOR_BALANCE,
    )


async def ensure() -> None:
    global _ready
    if _ready:
        return
    pool = db.pool
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS water_splashes (
            id BIGSERIAL PRIMARY KEY,
            shooter_id BIGINT NOT NULL,
            target_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            amount INT NOT NULL DEFAULT 0,
            outcome TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await pool.execute(
        """
        CREATE INDEX IF NOT EXISTS water_splashes_target_idx
            ON water_splashes (target_id, created_at DESC)
        """
    )
    await pool.execute(
        """
        CREATE INDEX IF NOT EXISTS water_splashes_shooter_idx
            ON water_splashes (shooter_id, created_at DESC)
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS water_shields (
            user_id BIGINT PRIMARY KEY,
            kind TEXT NOT NULL,
            until TIMESTAMPTZ,
            drip_until TIMESTAMPTZ,
            half_next BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS water_towels (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            amount INT NOT NULL,
            until TIMESTAMPTZ NOT NULL,
            claimed BOOLEAN NOT NULL DEFAULT FALSE
        )
        """
    )
    await settle_umbrella(pool)
    # «Вода» — чужой предмет крафта. На полку 🔫 кладём только свои товары.
    shelf = [item for item in ITEMS if "price" in item]
    names = [item["name"].lower() for item in shelf]
    keys = [item["name1"] for item in shelf]
    await pool.execute(
        """
        UPDATE dex SET sorting = '🔫'
        WHERE name1 = ANY($1::text[]) OR lower(name) = ANY($2::text[])
        """,
        keys,
        names,
    )
    _ready = True


def _from_design(screen_name: str, data: str) -> InlineKeyboardButton:
    for row in button_rows(screen_name):
        for button in row:
            if button.get("data") == data:
                return _button(
                    button["text"],
                    button["data"],
                    button.get("style") or "default",
                    button.get("emoji") or "",
                )
    return _button("Назад", data)


def _need_rows(*, pistol_missing: bool, water_missing: bool) -> list:
    rows = []
    if pistol_missing:
        rows.append([_from_design("splash_need", "wg:find:pistoletik")])
    if water_missing:
        rows.append([_from_design("splash_need", "wg:find:watercraft")])
    rows.append([_from_design("splash_need", "wg:home")])
    return rows


def _public_group_name(raw: str) -> str:
    text = str(raw or "").strip()
    text = text.replace("https://t.me/", "").replace("http://t.me/", "").lstrip("@")
    text = text.split("/")[0].split("?")[0]
    if not re.fullmatch(r"[A-Za-z0-9_]{4,}", text):
        return ""
    return text


async def _group_button_rows() -> list:
    """Кнопки-ссылки в официальные группы, у которых есть открытый адрес."""
    try:
        rows = await db.pool.fetch(
            """
            SELECT title, username
            FROM epsilon_official_groups
            WHERE is_official AND username <> ''
            ORDER BY title
            LIMIT 8
            """
        )
    except Exception:
        log.exception("water official groups")
        return []
    buttons = []
    seen = set()
    for row in rows:
        username = _public_group_name(row["username"])
        if not username or username.lower() in seen:
            continue
        seen.add(username.lower())
        title = " ".join(str(row["title"] or username).split())[:32] or username
        buttons.append([InlineKeyboardButton(text=title, url=f"https://t.me/{username}")])
    return buttons


async def _shield_sentence(user_id: int) -> str:
    row = await _shield(user_id)
    if not _still(row):
        return "Защиты нет. Вас можно облить."
    view = _kind_view(row["kind"])
    if row["until"] is None:
        left = "навсегда"
    else:
        left = "ещё " + _left_of(row["until"], datetime.now(timezone.utc))
    return f"{view['emoji']} <b>{view['name']}</b> — вас не обливают {left}."


async def _guide_view(user_id: int):
    bag = await _inventory(user_id)
    pistol_name = _item("pistoletik")["name"]
    water_name = _item("watercraft")["name"]
    pistol = _count(bag["items"], pistol_name)
    water = _count(bag["items"], water_name)
    text = guide_status(
        pistol=pistol,
        water=water,
        shield_line=await _shield_sentence(user_id),
    )
    rows = []
    if pistol < 1:
        rows.append([_from_design("splash_need", "wg:find:pistoletik")])
    if water < 1:
        rows.append([_from_design("splash_need", "wg:find:watercraft")])
    if pistol >= 1 and water >= 1:
        rows.append([_from_design("home", "wg:splash")])
    rows.append([_from_design("home", "wg:shield")])
    rows.append([_from_design("home", "wg:rules")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def shield_profile_html(user_id: int) -> str:
    """Строка профиля под флагом. Пустая, если защиты нет или таблицы ещё нет."""
    try:
        row = await _shield(user_id)
    except Exception:
        log.exception("water profile shield")
        return ""
    if not _still(row):
        return ""
    view = _kind_view(row["kind"])
    forever = row["until"] is None
    left = "" if forever else _left_of(row["until"], datetime.now(timezone.utc))
    return shield_profile_line(
        emoji=view["emoji"],
        name=view["name"],
        forever=forever,
        left=left,
        shoot=can_shoot(row["kind"]),
    )


async def open_guide(message) -> None:
    try:
        await ensure()
    except Exception:
        log.exception("water guide shelf")
    try:
        text, markup = await _guide_view(message.from_user.id)
    except Exception:
        log.exception("water guide kit")
        text, markup = _home_text(), _markup("home", message)
    await message.reply(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=markup,
    )


async def maybe_water_text(message) -> bool:
    if not is_water_ask(getattr(message, "text", "") or ""):
        return False
    await open_guide(message)
    return True


async def _inventory(user_id: int) -> dict:
    row = await db.pool.fetchrow("SELECT items, balance FROM users WHERE user_id = $1", int(user_id))
    if not row:
        return {"items": {}, "balance": 0, "row": None}
    return {
        "items": decode_items(row["items"]),
        "balance": int(row["balance"] or 0),
        "row": row,
    }


def _count(items: dict, *names: str) -> int:
    for name in names:
        if int(items.get(name, 0) or 0) > 0:
            return int(items[name])
    lowered = {str(key).lower(): int(value or 0) for key, value in items.items()}
    for name in names:
        if lowered.get(name.lower(), 0) > 0:
            return lowered[name.lower()]
    return 0


def _face(name1: str) -> dict | None:
    found = item_by_key(name1)
    if found:
        return found
    shield = SHIELDS.get(name1)
    if not shield:
        return None
    return {"name1": name1, "name": shield["name"], "emoji": shield["emoji"]}


async def _dex_row(name1: str):
    item = _face(name1)
    if not item:
        return None
    return await db.pool.fetchrow(
        """
        SELECT id, name, name1, emoji, price, remains
        FROM dex
        WHERE name1 = $1 OR lower(name) = lower($2)
        ORDER BY CASE WHEN name1 = $1 THEN 0 ELSE 1 END, id
        LIMIT 1
        """,
        item["name1"],
        item["name"],
    )


async def _offer(name1: str) -> dict | None:
    row = await _dex_row(name1)
    if not row:
        return None
    dex_id = int(row["id"])
    shop = int(row["remains"] or 0) > 0
    market = await db.pool.fetchrow(
        """
        SELECT id, price FROM market_listings
        WHERE item_id = $1 AND status = 'active' AND quantity > 0
        ORDER BY price ASC, id ASC
        LIMIT 1
        """,
        str(dex_id),
    )
    if not shop and not market:
        return None
    shop_price = int(row["price"] or 0)
    market_price = int(market["price"]) if market else None
    use_market = market is not None and (not shop or (market_price is not None and market_price < shop_price))
    face = _face(name1) or {}
    return {
        "id": dex_id,
        "name": row["name"],
        "emoji": row["emoji"] or face.get("emoji") or "☂️",
        "where": word("where_market") if use_market else word("where_shop"),
        "place": word("place_market") if use_market else word("place_shop"),
        "startapp": f"{'market' if use_market else 'shop'}-{dex_id}",
    }


async def _shield(user_id: int):
    row = await db.pool.fetchrow("SELECT kind, until, drip_until, half_next FROM water_shields WHERE user_id = $1", int(user_id))
    return row


def _still(row) -> bool:
    if not row:
        return False
    until = row["until"]
    if until is None:
        return True
    now = datetime.now(timezone.utc)
    if getattr(until, "tzinfo", None) is None:
        until = until.replace(tzinfo=timezone.utc)
    return until > now


async def _joke() -> str:
    global _joke_at
    local = DRY_JOKES[_joke_at % len(DRY_JOKES)]
    _joke_at += 1
    remote = ""
    try:
        timeout = aiohttp.ClientTimeout(total=2.5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(JOKE_SITE) as resp:
                raw = await resp.read()
        text = raw.decode("utf-8", "replace")
        match = re.search(r'"content"\s*:\s*"(.*)"', text, re.S)
        if match:
            remote = match.group(1).replace("\\n", " ").replace("\\r", " ").replace('\\"', '"')
            remote = " ".join(remote.split())
            if len(remote) > 280:
                remote = remote[:277].rstrip() + "…"
    except Exception:
        remote = ""
    return broke_text(local, remote)


async def _log(shooter: int, target: int, chat_id: int, amount: int, outcome: str) -> None:
    await db.pool.execute(
        """
        INSERT INTO water_splashes (shooter_id, target_id, chat_id, amount, outcome)
        VALUES ($1, $2, $3, $4, $5)
        """,
        int(shooter), int(target), int(chat_id), int(amount), outcome,
    )


async def _spend_water(user_id: int, items: dict) -> None:
    key = _item("watercraft")["name"]
    current = _count(items, key)
    if current <= 0:
        for name in list(items):
            if str(name).lower() == key.lower():
                key = name
                current = int(items[name] or 0)
                break
    items[key] = current - 1
    if items[key] <= 0:
        items.pop(key, None)
    await db.pool.execute(
        "UPDATE users SET items = $2 WHERE user_id = $1",
        int(user_id),
        encode_items(items),
    )


async def splash_from_item(message) -> None:
    """Выстрел предметом «Пистолетик». Вода тратится, пистолет остаётся."""
    await ensure()
    user_id = message.from_user.id
    private = getattr(getattr(message, "chat", None), "type", "") == "private"
    if private:
        bag = await _inventory(user_id)
        items = bag["items"]
        pistol = _count(items, _item("pistoletik")["name"])
        water = _count(items, _item("watercraft")["name"])
        if pistol < 1 or water < 1:
            missing = word("missing_pistol") if pistol < 1 else word("missing_water")
            await message.reply(
                screen_text("splash_need", missing=missing),
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(
                    pistol_missing=pistol < 1,
                    water_missing=water < 1,
                )),
            )
            return
        groups = await _group_button_rows()
        text = screen_text("shot_private")
        if not groups:
            text += "\n<i>Открытой ссылки на группу сейчас нет. Зайдите в группу проекта сами.</i>"
        rows = groups + [[_button(BTN_BACK, "wg:home")]]
        await message.reply(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        return
    reply = message.reply_to_message
    if reply is None or reply.from_user is None:
        await message.reply(screen_text("shot_reply"), parse_mode="HTML")
        return
    target_id = reply.from_user.id
    if int(target_id) == int(user_id):
        await message.reply(screen_text("shot_self"), parse_mode="HTML")
        return
    bag = await _inventory(user_id)
    items = bag["items"]
    if _count(items, _item("pistoletik")["name"]) < 1:
        await message.reply(
            screen_text("splash_need", missing=word("missing_pistol")),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(pistol_missing=True, water_missing=False)),
        )
        return
    if _count(items, _item("watercraft")["name"]) < 1:
        await message.reply(
            screen_text("splash_need", missing=word("missing_water")),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(pistol_missing=False, water_missing=True)),
        )
        return
    own = await _shield(user_id)
    if _still(own) and not can_shoot(own["kind"]):
        view = _kind_view(own["kind"])
        await message.reply(
            screen_text("shot_locked", emoji=view["emoji"], name=view["name"]),
            parse_mode="HTML",
        )
        return
    now = datetime.now(timezone.utc)
    day_start = now - timedelta(hours=24)
    pair_hits = await db.pool.fetch(
        """
        SELECT created_at FROM water_splashes
        WHERE shooter_id = $1 AND target_id = $2 AND outcome = 'hit' AND created_at > $3
        ORDER BY created_at DESC
        """,
        int(user_id), int(target_id), day_start,
    )
    if len(pair_hits) >= PAIR_DAY_MAX:
        await message.reply(screen_text("shot_pair_day"), parse_mode="HTML")
        return
    if pair_hits:
        latest = pair_hits[0]["created_at"]
        wait = PAIR_GAP_SEC - (now - latest).total_seconds()
        if wait > 0:
            await message.reply(screen_text("shot_pair_wait", left=left_phrase(int(wait))), parse_mode="HTML")
            return

    target_shield = await _shield(target_id)
    if _still(target_shield):
        await _spend_water(user_id, items)
        await _log(user_id, target_id, message.chat.id, 0, "shield")
        kind = SHIELDS.get(str(target_shield["kind"]), {})
        title = kind.get("line") or word("shield_name")
        await message.reply(
            screen_text("shot_bounce", emoji=kind.get("emoji") or "💧", title=title),
            parse_mode="HTML",
        )
        return

    enemy = await _inventory(target_id)
    if enemy["row"] is None:
        await message.reply(screen_text("shot_unknown"), parse_mode="HTML")
        return
    if enemy["balance"] < POOR_BALANCE:
        await _spend_water(user_id, items)
        await _log(user_id, target_id, message.chat.id, 0, "broke")
        await message.reply(
            screen_text("shot_broke", poor=POOR_BALANCE),
            parse_mode="HTML",
        )
        return

    taken_today = int(await db.pool.fetchval(
        """
        SELECT COALESCE(SUM(amount), 0) FROM water_splashes
        WHERE target_id = $1 AND outcome = 'hit' AND created_at > $2
        """,
        int(target_id), day_start,
    ) or 0)
    day_left = max(0, DAY_CAP - taken_today)
    if day_left < 1:
        await message.reply(screen_text("shot_day"), parse_mode="HTML")
        return
    percent = random.randint(PERCENT_LOW, PERCENT_HIGH)
    if target_shield and target_shield["half_next"]:
        percent = max(PERCENT_LOW, percent // 2)
    amount = take_amount(enemy["balance"], percent, cap=SHOT_CAP, day_left=day_left)
    if amount < 1:
        await message.reply(screen_text("shot_dry"), parse_mode="HTML")
        return
    await _spend_water(user_id, items)
    await db.pool.execute(
        "UPDATE users SET balance = balance - $2 WHERE user_id = $1",
        int(target_id), amount,
    )
    await db.pool.execute(
        "UPDATE users SET balance = balance + $2 WHERE user_id = $1",
        int(user_id), amount,
    )
    try:
        await db.cutehistory_minus(target_id, amount, word("history_shot"))
        await db.cutehistory_plus(user_id, amount, word("history_shot"))
    except Exception:
        log.warning("water history failed", exc_info=True)
    if target_shield and target_shield["half_next"]:
        await db.pool.execute(
            "UPDATE water_shields SET half_next = FALSE WHERE user_id = $1",
            int(target_id),
        )
    await _log(user_id, target_id, message.chat.id, amount, "hit")
    towel = towel_amount(amount)
    until = now + timedelta(hours=TOWEL_HOURS)
    towel_id = await db.pool.fetchval(
        """
        INSERT INTO water_towels (user_id, amount, until)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        int(target_id), towel, until,
    )
    shown = f"{amount:,}".replace(",", " ")
    await message.reply(
        screen_text("shot_hit", amount=shown, hours=hours_phrase(TOWEL_HOURS)),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=word("towel"), callback_data=f"wg:towel:{int(towel_id)}", style="success"),
        ]]),
    )


def _term(spec: dict) -> str:
    if spec.get("hours") is None:
        return hours_phrase(None)
    return hours_phrase(spec["hours"])


def _left_of(until, now) -> str:
    if until is None:
        return hours_phrase(None)
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return left_phrase(int((until - now).total_seconds()))


def _kind_view(kind: str) -> dict:
    spec = SHIELDS.get(str(kind or ""))
    if spec:
        return spec
    return {"name": word("shield_name"), "emoji": "💧", "hours": 0, "line": word("shield_name")}


def _button(text: str, data: str, color: str = "default", emoji: str = "") -> InlineKeyboardButton:
    fields = {
        "text": (str(text or "")[:64] or " "),
        "callback_data": str(data or "")[:64],
        "style": color or "default",
    }
    icon = _emoji_icon(emoji)
    if icon:
        fields["icon_custom_emoji_id"] = icon
    return InlineKeyboardButton(**fields)


def _extend_keyboard(user_id: int, choices: list, *, back: str) -> InlineKeyboardMarkup:
    rows = []
    for choice in choices:
        plus = hours_phrase(choice["hours"]) if choice["hours"] is None else "+" + hours_phrase(choice["hours"])
        label = choice_label(emoji=choice["emoji"], name=choice["name"], count=choice["count"], plus=plus)
        rows.append([_button(label, f"wg:pick:{user_id}:{choice['name1']}", "primary")])
    rows.append([_button(BTN_BACK, back)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _save_shield(conn, user_id: int, name1: str, until, half: bool, drip) -> None:
    await conn.execute(
        """
        INSERT INTO water_shields (user_id, kind, until, drip_until, half_next, updated_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET kind = EXCLUDED.kind,
            until = EXCLUDED.until,
            drip_until = EXCLUDED.drip_until,
            half_next = EXCLUDED.half_next,
            updated_at = NOW()
        """,
        int(user_id), name1, until, drip, bool(half),
    )


def _drip_for(name1: str, until):
    if name1 == "dryumbrella" and until is not None:
        return until + timedelta(minutes=20)
    return None


async def wear_shield(message, name1: str) -> bool:
    """Надевает защиту. True — предмет можно списать. False — он остаётся в инвентаре."""
    await ensure()
    spec = SHIELDS.get(name1)
    if not spec:
        return False
    user_id = int(message.from_user.id)
    current = await _shield(user_id)
    if _still(current) and current["until"] is None:
        view = _kind_view(current["kind"])
        await message.reply(
            forever_worn_text(emoji=view["emoji"], name=view["name"]),
            parse_mode="HTML",
        )
        return False
    if _still(current):
        view = _kind_view(current["kind"])
        left = _left_of(current["until"], datetime.now(timezone.utc))
        await message.reply(
            wearing_text(emoji=view["emoji"], name=view["name"], left=left, fee=EXTEND_FEE),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                _button(BTN_EXTEND, f"wg:more:{user_id}", "primary"),
            ]]),
        )
        return False
    now = datetime.now(timezone.utc)
    if spec["hours"] is None:
        until = None
        half = False
    else:
        until = now + timedelta(hours=int(spec["hours"]))
        half = name1 == "drycoat"
    await db.pool.execute(
        """
        INSERT INTO water_shields (user_id, kind, until, drip_until, half_next, updated_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET kind = EXCLUDED.kind,
            until = EXCLUDED.until,
            drip_until = EXCLUDED.drip_until,
            half_next = EXCLUDED.half_next,
            updated_at = NOW()
        """,
        user_id, name1, until, _drip_for(name1, until), half,
    )
    await message.reply(
        worn_text(
            emoji=spec["emoji"],
            name=spec["name"],
            term=_term(spec),
            shoot=can_shoot(name1),
        ),
        parse_mode="HTML",
    )
    return True


async def _edit_call(call, text: str, markup=None) -> None:
    try:
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )
    except Exception:
        await call.message.answer(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )


def _callback_owner(data: str):
    parts = str(data or "").split(":")
    if len(parts) < 3 or not parts[2].isdigit():
        return None, None
    key = parts[3] if len(parts) > 3 else ""
    return int(parts[2]), key


async def _show_extend_list(call, user_id: int) -> None:
    now = datetime.now(timezone.utc)
    current = await _shield(user_id)
    if not _still(current):
        await _edit_call(
            call,
            screen_text("shield_ended"),
        )
        return
    if current["until"] is None:
        view = _kind_view(current["kind"])
        await _edit_call(call, forever_worn_text(emoji=view["emoji"], name=view["name"]))
        return
    view = _kind_view(current["kind"])
    left = _left_of(current["until"], now)
    bag = await _inventory(user_id)
    choices = shields_in_bag(bag["items"])
    if not choices:
        text = extend_empty_text(emoji=view["emoji"], name=view["name"], left=left)
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [_button(button["text"], button["data"], button.get("style") or "default", button.get("emoji") or "") for button in row]
            for row in find_button_rows()
        ] + [[_button(BTN_BACK, f"wg:worn:{user_id}")]])
    else:
        text = extend_list_text(emoji=view["emoji"], name=view["name"], left=left)
        markup = _extend_keyboard(user_id, choices, back=f"wg:worn:{user_id}")
    await _edit_call(call, text, markup)


async def _show_wearing(call, user_id: int) -> None:
    current = await _shield(user_id)
    if not _still(current):
        await _edit_call(
            call,
            screen_text("shield_ended"),
        )
        return
    view = _kind_view(current["kind"])
    if current["until"] is None:
        await _edit_call(call, forever_worn_text(emoji=view["emoji"], name=view["name"]))
        return
    left = _left_of(current["until"], datetime.now(timezone.utc))
    await _edit_call(
        call,
        wearing_text(emoji=view["emoji"], name=view["name"], left=left, fee=EXTEND_FEE),
        InlineKeyboardMarkup(inline_keyboard=[[_button(BTN_EXTEND, f"wg:more:{user_id}", "primary")]]),
    )


async def _show_pick(call, user_id: int, name1: str) -> None:
    spec = SHIELDS.get(name1)
    if not spec:
        return
    now = datetime.now(timezone.utc)
    current = await _shield(user_id)
    if not _still(current) or current["until"] is None:
        await _show_extend_list(call, user_id)
        return
    bag = await _inventory(user_id)
    owned = {row["name1"]: row for row in shields_in_bag(bag["items"])}
    if name1 not in owned:
        await _edit_call(
            call,
            missing_item_text(spec["name"]),
            InlineKeyboardMarkup(inline_keyboard=[[_button(BTN_BACK, f"wg:more:{user_id}")]]),
        )
        return
    now_left = _left_of(current["until"], now)
    if spec["hours"] is None:
        next_left = hours_phrase(None)
    else:
        nxt = joined_until(current["until"], spec["hours"], now)
        next_left = _left_of(nxt, now)
    text = extend_pick_text(
        emoji=spec["emoji"],
        name=spec["name"],
        add=hours_phrase(spec["hours"]),
        now_left=now_left,
        next_left=next_left,
        fee=EXTEND_FEE,
        shoot=can_shoot(kept_kind(str(current["kind"]), name1)),
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [_button(btn_join(), f"wg:join:{user_id}:{name1}", "success")],
        [_button(BTN_BACK, f"wg:more:{user_id}")],
    ])
    await _edit_call(call, text, markup)


async def _join_shield(call, user_id: int, name1: str) -> None:
    spec = SHIELDS.get(name1)
    if not spec:
        await call.answer(word("no_such_item"), show_alert=True)
        return
    now = datetime.now(timezone.utc)
    result = None
    new_until = None
    result_kind = name1
    balance_left = 0
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", int(user_id))
            user = await conn.fetchrow(
                "SELECT items, balance FROM users WHERE user_id = $1 FOR UPDATE",
                int(user_id),
            )
            if not user:
                result = "missing"
            else:
                balance_left = int(user["balance"] or 0)
                shield = await conn.fetchrow(
                    "SELECT kind, until, half_next FROM water_shields WHERE user_id = $1 FOR UPDATE",
                    int(user_id),
                )
                items = decode_items(user["items"])
                if not _still(shield):
                    taken, ok = take_one_item(items, spec["name"])
                    if not ok:
                        result = "missing"
                    else:
                        if spec["hours"] is None:
                            new_until = None
                            half = False
                        else:
                            new_until = now + timedelta(hours=int(spec["hours"]))
                            half = name1 == "drycoat"
                        await conn.execute(
                            "UPDATE users SET items = $2 WHERE user_id = $1",
                            int(user_id), encode_items(taken),
                        )
                        result_kind = name1
                        await _save_shield(conn, user_id, result_kind, new_until, half, _drip_for(result_kind, new_until))
                        result = "fresh"
                elif shield["until"] is None:
                    result = "forever"
                elif balance_left < EXTEND_FEE:
                    result = "poor"
                else:
                    taken, ok = take_one_item(items, spec["name"])
                    if not ok:
                        result = "missing"
                    else:
                        if spec["hours"] is None:
                            new_until = None
                            half = False
                        else:
                            new_until = joined_until(shield["until"], spec["hours"], now)
                            half = bool(shield["half_next"]) or name1 == "drycoat"
                        status = await conn.execute(
                            """
                            UPDATE users
                            SET balance = balance - $2, items = $3
                            WHERE user_id = $1 AND balance >= $2
                            """,
                            int(user_id), int(EXTEND_FEE), encode_items(taken),
                        )
                        if not str(status).endswith("1"):
                            result = "poor"
                        else:
                            result_kind = kept_kind(str(shield["kind"]), name1)
                            await _save_shield(
                                conn, user_id, result_kind, new_until, half, _drip_for(result_kind, new_until),
                            )
                            result = "ok"
    if result == "poor":
        await _edit_call(
            call,
            poor_fee_text(fee=EXTEND_FEE, balance=balance_left),
            InlineKeyboardMarkup(inline_keyboard=[
                [_button(btn_join(), f"wg:join:{user_id}:{name1}", "success")],
                [_button(BTN_BACK, f"wg:more:{user_id}")],
            ]),
        )
        await call.answer(word("need_fee", fee=EXTEND_FEE), show_alert=True)
        return
    if result == "missing":
        await _edit_call(
            call,
            missing_item_text(spec["name"]),
            InlineKeyboardMarkup(inline_keyboard=[[_button(BTN_BACK, f"wg:more:{user_id}")]]),
        )
        await call.answer(word("item_gone"), show_alert=True)
        return
    if result == "forever":
        view = _kind_view("drysafe")
        await _edit_call(call, forever_worn_text(emoji=view["emoji"], name=view["name"]))
        await call.answer(word("nothing_to_stack"), show_alert=True)
        return
    if result == "fresh":
        await _edit_call(call, fresh_instead_text(
            emoji=spec["emoji"],
            name=spec["name"],
            term=_term(spec),
            shoot=can_shoot(name1),
        ))
        await call.answer(word("worn_no_fee"))
        return
    if result != "ok":
        await call.answer(word("stack_failed"), show_alert=True)
        return
    try:
        await db.cutehistory_minus(user_id, EXTEND_FEE, word("history_stack"))
    except Exception:
        log.warning("water extend history failed", exc_info=True)
    bag = await _inventory(user_id)
    more = shields_in_bag(bag["items"])
    markup = None
    if more:
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            _button(BTN_EXTEND, f"wg:more:{user_id}", "primary"),
        ]])
    view = _kind_view(result_kind)
    left = hours_phrase(None) if new_until is None else _left_of(new_until, datetime.now(timezone.utc))
    await _edit_call(
        call,
        stacked_text(
            emoji=view["emoji"],
            name=view["name"],
            left=left,
            fee=EXTEND_FEE,
            shoot=can_shoot(result_kind),
            spent=spec["name"],
        ),
        markup,
    )
    await call.answer(word("stacked"))


async def _show(call, name: str, text: str, markup=None, **slots) -> None:
    if markup is None:
        markup = _markup(name, call.message, **slots)
    try:
        await call.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
    except Exception:
        await call.message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
    await call.answer()


@dp.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("wg:"))
async def water_click(call):
    await ensure()
    data = call.data
    if data == "wg:home":
        try:
            text, markup = await _guide_view(call.from_user.id)
        except Exception:
            log.exception("water guide kit")
            text, markup = _home_text(), _markup("home", call.message)
        await _show(call, "home", text, markup=markup)
        return
    if data == "wg:rules":
        await _show(call, "rules", _rules_text())
        return
    if data == "wg:shield":
        await _show(call, "shield", screen_text("shield", fee=EXTEND_FEE))
        return
    if data in {"wg:splash", "wg:aim"}:
        bag = await _inventory(call.from_user.id)
        pistol = _count(bag["items"], _item("pistoletik")["name"])
        water = _count(bag["items"], _item("watercraft")["name"])
        if data == "wg:aim":
            if pistol < 1 or water < 1:
                missing = word("missing_pistol") if pistol < 1 else word("missing_water")
                await _show(
                    call,
                    "splash_need",
                    screen_text("splash_need", missing=missing),
                    markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(
                        pistol_missing=pistol < 1,
                        water_missing=water < 1,
                    )),
                )
                return
            text = screen_text("aim")
            markup = _markup("aim", call.message)
            private = getattr(getattr(call.message, "chat", None), "type", "") == "private"
            if private:
                groups = await _group_button_rows()
                if groups:
                    text += "\n\n<i>Кнопки ниже — официальные группы. Зайдите, ответьте на человека и откройте Пистолетик.</i>"
                    markup = InlineKeyboardMarkup(inline_keyboard=list(markup.inline_keyboard) + groups)
                else:
                    text += "\n\n<i>Открытой ссылки на группу сейчас нет. Зайдите в группу проекта сами.</i>"
            await _show(call, "aim", text, markup=markup)
            return
        if pistol < 1 or water < 1:
            missing = word("missing_pistol") if pistol < 1 else word("missing_water")
            await _show(
                call,
                "splash_need",
                screen_text("splash_need", missing=missing),
                markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(
                    pistol_missing=pistol < 1,
                    water_missing=water < 1,
                )),
            )
            return
        await _show(call, "splash_ready", screen_text("splash_ready"))
        return
    if data.startswith(("wg:more:", "wg:worn:", "wg:pick:", "wg:join:")):
        owner, key = _callback_owner(data)
        if owner is None or owner != int(call.from_user.id):
            await call.answer(word("not_yours"), show_alert=True)
            return
        if data.startswith("wg:more:"):
            await _show_extend_list(call, owner)
            await call.answer()
            return
        if data.startswith("wg:worn:"):
            await _show_wearing(call, owner)
            await call.answer()
            return
        if data.startswith("wg:pick:"):
            await _show_pick(call, owner, key)
            await call.answer()
            return
        await _join_shield(call, owner, key)
        return
    if data.startswith("wg:find:"):
        key = data.split(":", 2)[2]
        item = _face(key)
        if item is None:
            await call.answer(word("no_such_item"), show_alert=True)
            return
        offer = await _offer(key)
        if not offer:
            await _show(
                call,
                "miss",
                screen_text("miss", emoji=item["emoji"], name=item["name"]),
                key=key,
            )
            return
        text = screen_text(
            "found",
            emoji=offer["emoji"],
            name=offer["name"],
            where=offer["where"],
            place=offer["place"],
        )
        private = getattr(call.message.chat, "type", "") == "private"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [_open_button(word("open_buy"), offer["startapp"], private, "success")],
            [InlineKeyboardButton(text=BTN_BACK, callback_data="wg:home", style="default")],
        ])
        try:
            await call.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
        except Exception:
            await call.message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
        await call.answer(word("looking"))
        return
    if data.startswith("wg:towel:"):
        try:
            towel_id = int(data.split(":")[2])
        except (IndexError, ValueError):
            await call.answer(word("towel_lost"), show_alert=True)
            return
        row = await db.pool.fetchrow("SELECT user_id, amount, until, claimed FROM water_towels WHERE id = $1", towel_id)
        if not row or row["claimed"] or int(row["user_id"]) != int(call.from_user.id):
            await call.answer(word("towel_not_yours"), show_alert=True)
            return
        if row["until"] <= datetime.now(timezone.utc):
            await call.answer(word("towel_dry"), show_alert=True)
            return
        await db.pool.execute("UPDATE water_towels SET claimed = TRUE WHERE id = $1", towel_id)
        await db.pool.execute(
            "UPDATE users SET balance = balance + $2 WHERE user_id = $1",
            int(call.from_user.id), int(row["amount"]),
        )
        try:
            await db.cutehistory_plus(call.from_user.id, int(row["amount"]), word("history_towel"))
        except Exception:
            log.warning("towel history failed", exc_info=True)
        await call.answer(word("towel_got", amount=int(row["amount"])), show_alert=True)
        return
    await call.answer()
