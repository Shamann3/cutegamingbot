# -*- coding: utf-8 -*-
"""Водные игры: выстрел, защита, шутка и три шага до покупки."""
from __future__ import annotations

import logging
import random
import re
from datetime import datetime, timedelta, timezone

import aiohttp
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.db_create.db import InsufficientBalanceError
from bot.db_create.items_codec import decode_items, encode_items
from bot.funcs.water_games_design import (
    BTN_BACK,
    BTN_EXTEND,
    DAY_CAP,
    DRY_JOKES,
    EXTEND_FEE,
    ITEMS,
    JOKE_SITE,
    PERCENT_HIGH,
    PERCENT_LOW,
    POOR_BALANCE,
    SHIELDS,
    SHOT_CAP,
    TOWEL_HOURS,
    broke_text,
    btn_join,
    button_owner,
    button_rows,
    stamp_callback,
    strip_callback_owner,
    can_shoot,
    choice_label,
    find_button_rows,
    kept_kind,
    after_buy_text,
    default_rules,
    fee_group_name,
    normalize_fee_chat,
    normalize_seek_chat,
    pistol_is_blocked,
    pistol_seek_query,
    seek_ask_text,
    seek_handle_from_link,
    seek_loot_line,
    seek_other_gain,
    seek_rules_line,
    seek_spares_attempt,
    seek_yes_label,
    extend_empty_text,
    extend_list_text,
    shield_mark,
    shield_profile_line,
    extend_pick_text,
    forever_worn_text,
    fresh_instead_text,
    hours_phrase,
    is_shield_off,
    is_water_ask,
    item_by_key,
    joined_until,
    left_phrase,
    missing_item_text,
    poor_fee_text,
    public_group_name,
    calm_shot_text,
    left_clock,
    screen_text,
    settle_umbrella,
    split_take,
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


class CalmHold(Exception):
    """Игр хватило: куты этого человека не переводятся."""

    def __init__(self, text: str):
        super().__init__(text)
        self.text = text

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


def _markup(name: str, message, owner_id: int, **slots) -> InlineKeyboardMarkup:
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
                built.append(_button(
                    button["text"],
                    stamp_callback(data, owner_id),
                    button.get("style") or "default",
                    icon,
                ))
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


def _rules_text(rules: dict | None = None) -> str:
    rules = rules or default_rules()
    return screen_text(
        "rules",
        low=rules["percentLow"],
        high=rules["percentHigh"],
        cap=rules["shotCap"],
        day=rules["dayCap"],
        poor=rules["poorBalance"],
        seek=seek_rules_line(rules),
    )


async def _shot_rules() -> dict:
    """Живые числа создателя. Нет строки — остаются стартовые 4–8% и потолки."""
    base = default_rules()
    try:
        row = await db.pool.fetchrow(
            """
            SELECT percent_low, percent_high, shot_cap, day_cap, poor_balance, commission_percent,
                   fee_chat_id, pistol_day_on, pistol_day_max,
                   seek_on, seek_day_max, seek_fee, seek_fee_chat_id
            FROM water_rules WHERE id = 1
            """
        )
    except Exception:
        log.exception("water rules")
        return base
    if not row:
        return base
    low = max(1, min(100, int(row["percent_low"])))
    high = max(1, min(100, int(row["percent_high"])))
    if low > high:
        low, high = high, low
    return {
        "percentLow": low,
        "percentHigh": high,
        "shotCap": max(1, int(row["shot_cap"])),
        "dayCap": max(1, int(row["day_cap"])),
        "poorBalance": max(0, int(row["poor_balance"])),
        "commissionPercent": max(0, min(100, int(row["commission_percent"]))),
        "feeChatId": normalize_fee_chat(row["fee_chat_id"]),
        "pistolDayOn": bool(row["pistol_day_on"]),
        "pistolDayMax": max(0, int(row["pistol_day_max"] or 0)),
        "seekOn": bool(row["seek_on"]),
        "seekDayMax": max(0, int(row["seek_day_max"] or 0)),
        "seekFee": max(0, int(row["seek_fee"] or 0)),
        "seekFeeChatId": normalize_seek_chat(row["seek_fee_chat_id"]),
    }


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
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS water_shot_offers (
            id BIGSERIAL PRIMARY KEY,
            shooter_id BIGINT NOT NULL,
            target_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            amount INT NOT NULL DEFAULT 0,
            percent INT NOT NULL DEFAULT 0,
            kind TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS water_rules (
            id SMALLINT PRIMARY KEY,
            percent_low INT NOT NULL,
            percent_high INT NOT NULL,
            shot_cap INT NOT NULL,
            day_cap INT NOT NULL,
            poor_balance INT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_rules
            ADD COLUMN IF NOT EXISTS commission_percent INT NOT NULL DEFAULT 10
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_splashes
            ADD COLUMN IF NOT EXISTS fee INT NOT NULL DEFAULT 0
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_rules
            ADD COLUMN IF NOT EXISTS fee_chat_id BIGINT NOT NULL DEFAULT -1004324787050
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_rules
            ADD COLUMN IF NOT EXISTS pistol_day_on BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_rules
            ADD COLUMN IF NOT EXISTS pistol_day_max INT NOT NULL DEFAULT 10
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_rules
            ADD COLUMN IF NOT EXISTS seek_on BOOLEAN NOT NULL DEFAULT TRUE
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_rules
            ADD COLUMN IF NOT EXISTS seek_day_max INT NOT NULL DEFAULT 3
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_rules
            ADD COLUMN IF NOT EXISTS seek_fee INT NOT NULL DEFAULT 500
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_rules
            ADD COLUMN IF NOT EXISTS seek_fee_chat_id BIGINT NOT NULL DEFAULT -1004318525471
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS water_seeks (
            id BIGSERIAL PRIMARY KEY,
            shooter_id BIGINT NOT NULL,
            target_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            fee INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await pool.execute(
        """
        CREATE INDEX IF NOT EXISTS water_seeks_shooter_idx
            ON water_seeks (shooter_id, created_at DESC)
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS water_seek_offers (
            id BIGSERIAL PRIMARY KEY,
            shooter_id BIGINT NOT NULL,
            target_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            fee INT NOT NULL DEFAULT 0,
            amount INT NOT NULL DEFAULT 0,
            percent INT NOT NULL DEFAULT 0,
            kind TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_seek_offers
            ADD COLUMN IF NOT EXISTS amount INT NOT NULL DEFAULT 0
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_seek_offers
            ADD COLUMN IF NOT EXISTS percent INT NOT NULL DEFAULT 0
        """
    )
    await pool.execute(
        """
        ALTER TABLE water_seek_offers
            ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT ''
        """
    )
    base = default_rules()
    await pool.execute(
        """
        INSERT INTO water_rules (id, percent_low, percent_high, shot_cap, day_cap, poor_balance, commission_percent)
        VALUES (1, $1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO NOTHING
        """,
        base["percentLow"],
        base["percentHigh"],
        base["shotCap"],
        base["dayCap"],
        base["poorBalance"],
        base["commissionPercent"],
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS water_buy_prompts (
            user_id BIGINT PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            name1 TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
    try:
        await _charges().ensure(pool)
    except Exception:
        log.exception("water shield charges")
    _ready = True


def _charges():
    import sys
    from pathlib import Path

    root = str(Path(__file__).resolve().parents[2] / "server")
    if root not in sys.path:
        sys.path.insert(0, root)
    import water_shield_charges
    return water_shield_charges


def _until_from_charge(found: bool, seconds, spec: dict, now, base=None):
    """Заряд задаёт срок. Нет заряда — срок из каталога. base складывает его с уже надетым."""
    if found and seconds is None:
        return None
    if found and seconds:
        start = now if base is None else base
        if getattr(start, "tzinfo", None) is None:
            start = start.replace(tzinfo=timezone.utc)
        return start + timedelta(seconds=int(seconds))
    if spec.get("hours") is None:
        return None
    if base is None:
        return now + timedelta(hours=int(spec["hours"]))
    return joined_until(base, spec["hours"], now)


async def _apply_charge_until(conn, user_id: int, name1: str, spec: dict, now, base=None):
    found, seconds = await _charges().take(conn, user_id, name1)
    return _until_from_charge(found, seconds, spec, now, base)


def _from_design(screen_name: str, data: str, owner_id: int) -> InlineKeyboardButton:
    for row in button_rows(screen_name):
        for button in row:
            if button.get("data") == data:
                return _button(
                    button["text"],
                    stamp_callback(button["data"], owner_id),
                    button.get("style") or "default",
                    button.get("emoji") or "",
                )
    return _button("Назад", stamp_callback(data, owner_id))


def _need_rows(*, pistol_missing: bool, water_missing: bool, owner_id: int) -> list:
    rows = []
    if pistol_missing:
        rows.append([_from_design("splash_need", "wg:find:pistoletik", owner_id)])
    if water_missing:
        rows.append([_from_design("splash_need", "wg:find:watercraft", owner_id)])
    rows.append([_from_design("splash_need", "wg:home", owner_id)])
    return rows


async def _remember_buy(user_id: int, chat_id: int, message_id: int, name1: str) -> None:
    """Запоминает сообщение с кнопкой покупки, чтобы после покупки его сменить."""
    await db.pool.execute(
        """
        INSERT INTO water_buy_prompts (user_id, chat_id, message_id, name1, updated_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET chat_id = EXCLUDED.chat_id,
            message_id = EXCLUDED.message_id,
            name1 = EXCLUDED.name1,
            updated_at = NOW()
        """,
        int(user_id),
        int(chat_id),
        int(message_id),
        str(name1 or ""),
    )


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
        username = public_group_name(row["username"])
        if not username or username.lower() in seen:
            continue
        seen.add(username.lower())
        title = " ".join(str(row["title"] or username).split())[:32] or username
        buttons.append([InlineKeyboardButton(text=title, url=f"https://t.me/{username}")])
    return buttons


def _off_button(user_id: int) -> InlineKeyboardButton:
    return _button("Снять защиту", stamp_callback("wg:off", int(user_id)), "danger")


async def _guide_view(user_id: int, message):
    """Главный экран. Если защита надета, здесь же видно срок и кнопка, чтобы снять."""
    text = screen_text("home")
    markup = _markup("home", message, owner_id=user_id)
    try:
        shield = await _shield(user_id)
    except Exception:
        log.exception("water home shield")
        shield = None
    if not _still(shield):
        return text, markup
    view = _kind_view(shield["kind"])
    left = "навсегда" if shield["until"] is None else _left_of(shield["until"], datetime.now(timezone.utc))
    text = screen_text(
        "home_worn",
        mark=shield_mark(shield["kind"]),
        name=view["name"],
        left=left,
    )
    rows = list(markup.inline_keyboard)
    rows.append([_off_button(user_id)])
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
        emoji=shield_mark(row["kind"]),
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
        text, markup = await _guide_view(message.from_user.id, message)
    except Exception:
        log.exception("water guide kit")
        text, markup = _home_text(), _markup("home", message, owner_id=message.from_user.id)
    await message.reply(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=markup,
    )


async def maybe_water_text(message) -> bool:
    text = getattr(message, "text", "") or ""
    if is_shield_off(text):
        await unequip_shield(message)
        return True
    if not is_water_ask(text):
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


async def _holds(user_id: int, name1: str, items: dict | None = None) -> bool:
    """Предмет уже в инвентаре: по имени из dex и по числовому id."""
    if items is None:
        items = (await _inventory(user_id))["items"]
    face = _face(name1)
    names = [face["name"]] if face else []
    if names and _count(items, *names) > 0:
        return True
    row = await _dex_row(name1)
    return bool(row and _count(items, str(row["id"])) > 0)


async def _own_lot(user_id: int, name1: str):
    """Активный лот игрока. Кнопка ведёт сразу в окно снятия, не в чужую покупку."""
    row = await _dex_row(name1)
    if not row:
        return None
    found = await db.pool.fetchrow(
        """
        SELECT id FROM market_listings
        WHERE seller_id = $1 AND item_id = $2 AND status = 'active' AND quantity > 0
        ORDER BY created_at ASC
        LIMIT 1
        """,
        int(user_id),
        str(row["id"]),
    )
    if not found:
        return None
    return {"startapp": f"own-{int(row['id'])}"}


def _step_rows(step: str, owner_id: int) -> list:
    if step == "water":
        return [[_from_design("splash_need", "wg:find:watercraft", owner_id)]]
    if step == "pistol":
        return [[_from_design("splash_need", "wg:find:pistoletik", owner_id)]]
    if step == "shoot":
        return [[_from_design("home", "wg:aim", owner_id)]]
    return []


async def _advance_text(user_id: int, kind: str) -> tuple[str, str]:
    item = _face(kind) or {}
    pistol = await _holds(user_id, "pistoletik") or kind == "pistoletik"
    water = await _holds(user_id, "watercraft") or kind == "watercraft"
    return after_buy_text(
        kind=kind,
        emoji=item.get("emoji") or "💧",
        name=item.get("name") or "Предмет",
        pistol=pistol,
        water=water,
    )


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


async def _log(shooter: int, target: int, chat_id: int, amount: int, outcome: str, fee: int = 0) -> None:
    await db.pool.execute(
        """
        INSERT INTO water_splashes (shooter_id, target_id, chat_id, amount, outcome, fee)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        int(shooter), int(target), int(chat_id), int(amount), outcome, int(fee),
    )


async def _keep_project_fee(shooter_id: int, fee: int, chat_id: int) -> int:
    """Забирает комиссию у облившего и кладёт её на баланс выбранной технической группы.

    Если группа сумму не приняла, куты возвращаются облившему.
    """
    fee = int(fee or 0)
    dest = int(chat_id or 0)
    if fee < 1 or dest == 0:
        return 0
    taken = await db.update_user_balance(int(shooter_id), f"-{fee}")
    if taken is None:
        return 0
    try:
        ok = await db.add_to_chatbalance(bot1, dest, fee)
    except Exception:
        log.exception("water fee")
        ok = False
    if not ok:
        await db.update_user_balance(int(shooter_id), f"+{fee}")
        return 0
    try:
        from bot.funcs.tech_plus import announce_tech_plus
        await announce_tech_plus(bot1, dest, fee, reason="water")
    except Exception:
        log.exception("water fee note")
    return fee


async def _pistol_block_text(user_id: int, rules: dict, now) -> str | None:
    if not rules.get("pistolDayOn"):
        return None
    used = int(await db.pool.fetchval(
        """
        SELECT COUNT(*) FROM water_splashes
        WHERE shooter_id = $1 AND created_at > $2
          AND outcome IN ('hit', 'broke', 'shield')
        """,
        int(user_id), now - timedelta(hours=24),
    ) or 0)
    limit = max(1, int(rules.get("pistolDayMax") or 0))
    if not pistol_is_blocked(used, on=True, limit=limit):
        return None
    return screen_text("shot_pistol_day", used=used, limit=limit)


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
        pistol = await _holds(user_id, "pistoletik", items)
        water = await _holds(user_id, "watercraft", items)
        if not pistol or not water:
            missing = word("missing_pistol") if not pistol else word("missing_water")
            await message.reply(
                screen_text("splash_need", missing=missing),
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(
                    pistol_missing=not pistol,
                    water_missing=not water,
                    owner_id=user_id,
                )),
            )
            return
        groups = await _group_button_rows()
        text = screen_text("shot_private")
        if not groups:
            text += "\n<i>Ссылки на группу нет. Зайдите в группу сами.</i>"
        rows = groups + [[_button(BTN_BACK, stamp_callback("wg:home", user_id))]]
        await message.reply(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        return
    reply = message.reply_to_message
    if reply is None or reply.from_user is None:
        await _open_seek(message, user_id)
        return
    target_id = reply.from_user.id
    if int(target_id) == int(user_id):
        await message.reply(screen_text("shot_self"), parse_mode="HTML")
        return
    bag = await _inventory(user_id)
    items = bag["items"]
    if not await _holds(user_id, "pistoletik", items):
        await message.reply(
            screen_text("splash_need", missing=word("missing_pistol")),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(
                pistol_missing=True, water_missing=False, owner_id=user_id,
            )),
        )
        return
    if not await _holds(user_id, "watercraft", items):
        await message.reply(
            screen_text("splash_need", missing=word("missing_water")),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(
                pistol_missing=False, water_missing=True, owner_id=user_id,
            )),
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
    rules = await _shot_rules()
    blocked = await _pistol_block_text(user_id, rules, now)
    if blocked:
        await message.reply(blocked, parse_mode="HTML")
        return
    await _preview_shot(message, user_id, target_id, now, day_start)


def _seek_hint(message):
    text = getattr(message, "text", "") or ""
    query = pistol_seek_query(text)
    hinted = None
    for ent in getattr(message, "entities", None) or []:
        kind = getattr(ent, "type", "")
        if kind == "text_mention" and getattr(ent, "user", None) is not None:
            hinted = ent.user
            continue
        url = ""
        if kind == "text_link":
            url = str(getattr(ent, "url", "") or "")
        elif kind == "url":
            start = int(getattr(ent, "offset", 0) or 0)
            length = int(getattr(ent, "length", 0) or 0)
            url = text[start:start + length]
        handle = seek_handle_from_link(url)
        if handle:
            query = f"@{handle}"
    return query, hinted


def _person_label(row, hinted=None) -> str:
    if hinted is not None:
        parts = []
        for piece in (getattr(hinted, "first_name", ""), getattr(hinted, "last_name", "")):
            text = " ".join(str(piece or "").split())
            if text:
                parts.append(text)
        if parts:
            return " ".join(parts)
        username = " ".join(str(getattr(hinted, "username", "") or "").split())
        if username:
            return f"@{username}"
    if not row:
        return ""
    name = " ".join(str(row["first_name"] or "").split())
    if name:
        return name
    username = " ".join(str(row["username"] or "").split())
    return f"@{username}" if username else ""


async def _seek_used(user_id: int, now) -> int:
    return int(await db.pool.fetchval(
        """
        SELECT COUNT(*) FROM water_seeks
        WHERE shooter_id = $1 AND created_at > $2
        """,
        int(user_id), now - timedelta(hours=24),
    ) or 0)


async def _resolve_seek(query: str, hinted, shooter_id: int):
    """one / self / none / many и строка пользователя."""
    if hinted is not None:
        try:
            uid = int(hinted.id)
        except (TypeError, ValueError):
            uid = 0
        if uid == int(shooter_id):
            return "self", None
        row = await db.pool.fetchrow(
            "SELECT user_id, first_name, username FROM users WHERE user_id = $1",
            uid,
        )
        if not row:
            return "none", None
        return "one", row

    needle = " ".join(str(query or "").split())
    if not needle:
        return "empty", None
    if needle.startswith("@"):
        needle = needle[1:].strip()
    if not needle:
        return "empty", None

    if re.fullmatch(r"\d{5,16}", needle):
        row = await db.pool.fetchrow(
            "SELECT user_id, first_name, username FROM users WHERE user_id = $1",
            int(needle),
        )
        if not row:
            return "none", None
        if int(row["user_id"]) == int(shooter_id):
            return "self", None
        return "one", row

    rows = []
    if re.fullmatch(r"[A-Za-z0-9_]{4,32}", needle):
        rows = await db.pool.fetch(
            """
            SELECT user_id, first_name, username FROM users
            WHERE lower(username) = lower($1) AND user_id > 0
            LIMIT 6
            """,
            needle,
        )
    if not rows:
        rows = await db.pool.fetch(
            """
            SELECT user_id, first_name, username FROM users
            WHERE lower(btrim(first_name)) = lower($1) AND user_id > 0
            LIMIT 6
            """,
            needle,
        )
    people = [row for row in rows if int(row["user_id"]) != int(shooter_id)]
    if not people:
        if rows:
            return "self", None
        return "none", None
    if len(people) > 1:
        return "many", None
    return "one", people[0]


async def _open_seek(message, user_id: int) -> None:
    """Платный поиск человека по @username, id или имени. Ответ на сообщение сюда не входит."""
    query, hinted = _seek_hint(message)
    if not query and hinted is None:
        await message.reply(screen_text("shot_reply"), parse_mode="HTML")
        return
    bag = await _inventory(user_id)
    items = bag["items"]
    if not await _holds(user_id, "pistoletik", items):
        await message.reply(
            screen_text("splash_need", missing=word("missing_pistol")),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(
                pistol_missing=True, water_missing=False, owner_id=user_id,
            )),
        )
        return
    if not await _holds(user_id, "watercraft", items):
        await message.reply(
            screen_text("splash_need", missing=word("missing_water")),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(
                pistol_missing=False, water_missing=True, owner_id=user_id,
            )),
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
    rules = await _shot_rules()
    blocked = await _pistol_block_text(user_id, rules, now)
    if blocked:
        await message.reply(blocked, parse_mode="HTML")
        return
    if not rules.get("seekOn"):
        await message.reply(screen_text("seek_off"), parse_mode="HTML")
        return
    limit = max(1, int(rules.get("seekDayMax") or 0))
    used = await _seek_used(user_id, now)
    if used >= limit:
        await message.reply(screen_text("seek_limit", used=used, limit=limit), parse_mode="HTML")
        return
    try:
        status, row = await _resolve_seek(query, hinted, user_id)
    except Exception:
        log.exception("water seek")
        await message.reply(screen_text("seek_none"), parse_mode="HTML")
        return
    if status == "empty":
        await message.reply(screen_text("shot_reply"), parse_mode="HTML")
        return
    if status == "self":
        await message.reply(screen_text("shot_self"), parse_mode="HTML")
        return
    if status == "many":
        await message.reply(screen_text("seek_many"), parse_mode="HTML")
        return
    if status != "one" or not row:
        await message.reply(screen_text("seek_none"), parse_mode="HTML")
        return
    fee = max(0, int(rules.get("seekFee") or 0))
    quote = await _quote_shot(int(row["user_id"]), rules, now)
    spare = seek_spares_attempt(quote["kind"])
    offer_id = await db.pool.fetchval(
        """
        INSERT INTO water_seek_offers (shooter_id, target_id, chat_id, fee, amount, percent, kind)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        int(user_id), int(row["user_id"]), int(message.chat.id), fee,
        int(quote["amount"]), int(quote["percent"]), str(quote["kind"]),
    )
    left = max(0, limit - used)
    hinted_name = getattr(hinted, "username", "") if hinted is not None else ""
    text = seek_ask_text(
        _person_label(row, hinted),
        fee,
        left,
        seek_loot_line(quote["kind"], quote["amount"], quote["payout"]),
        username=str(row["username"] or hinted_name or ""),
        user_id=int(row["user_id"]),
        elsewhere=seek_other_gain(rules) if spare else 0,
        spare=spare,
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        _button(word("seek_no"), stamp_callback(f"wg:seekno:{int(offer_id)}", user_id), "danger"),
        _button(seek_yes_label(fee), stamp_callback(f"wg:seekyes:{int(offer_id)}", user_id), "success"),
    ]])
    await message.reply(
        text,
        parse_mode="HTML",
        reply_markup=markup,
        disable_web_page_preview=True,
    )


async def _leave_seek(call, offer_id: int) -> None:
    row = await db.pool.fetchrow(
        """
        DELETE FROM water_seek_offers
        WHERE id = $1 AND shooter_id = $2
        RETURNING id
        """,
        int(offer_id), int(call.from_user.id),
    )
    if not row:
        await call.answer(word("offer_gone"), show_alert=True)
        return
    await _edit_call(call, screen_text("seek_cancel"))
    await call.answer()


async def _agree_seek(call, offer_id: int) -> None:
    row = await db.pool.fetchrow(
        """
        DELETE FROM water_seek_offers
        WHERE id = $1 AND shooter_id = $2
        RETURNING shooter_id, target_id, chat_id, fee, amount, percent, kind
        """,
        int(offer_id), int(call.from_user.id),
    )
    if not row:
        await call.answer(word("offer_gone"), show_alert=True)
        return
    user_id = int(row["shooter_id"])
    target_id = int(row["target_id"])
    chat_id = int(row["chat_id"])
    now = datetime.now(timezone.utc)
    rules = await _shot_rules()
    if not rules.get("seekOn"):
        await _edit_call(call, screen_text("seek_off"))
        await call.answer()
        return
    limit = max(1, int(rules.get("seekDayMax") or 0))
    used = await _seek_used(user_id, now)
    if used >= limit:
        await _edit_call(call, screen_text("seek_limit", used=used, limit=limit))
        await call.answer()
        return
    blocked = await _pistol_block_text(user_id, rules, now)
    if blocked:
        await _edit_call(call, blocked)
        await call.answer()
        return
    fee = max(0, int(rules.get("seekFee") or 0))
    spare = seek_spares_attempt(str(row["kind"] or ""))
    live = None
    try:
        live = await _quote_shot(target_id, rules, now)
    except Exception:
        log.exception("water seek quote")
    else:
        spare = seek_spares_attempt(str(live.get("kind") or ""))
    if fee > 0:
        bag = await _inventory(user_id)
        if int(bag["balance"] or 0) < fee:
            await _edit_call(call, screen_text("seek_poor", fee=_money(fee)))
            await call.answer()
            return
        kept = await _keep_project_fee(user_id, fee, int(rules["seekFeeChatId"]))
        if kept < 1:
            await _edit_call(call, screen_text("seek_fail"))
            await call.answer()
            return
        try:
            await db.cutehistory_plus(user_id, -fee, "поиск для облития")
        except Exception:
            log.exception("water seek history")
    if not spare:
        await db.pool.execute(
            """
            INSERT INTO water_seeks (shooter_id, target_id, chat_id, fee)
            VALUES ($1, $2, $3, $4)
            """,
            user_id, target_id, chat_id, fee,
        )
    locked = None
    if not spare and str(row["kind"] or "") == "hit":
        locked = {
            "kind": "hit",
            "amount": int(row["amount"] or 0),
            "percent": int(row["percent"] or 0),
        }
    elif not spare and live and str(live.get("kind") or "") == "hit":
        locked = {
            "kind": "hit",
            "amount": int(live.get("amount") or 0),
            "percent": int(live.get("percent") or 0),
        }
    try:
        await _preview_shot(
            call.message, user_id, target_id, now, now - timedelta(hours=24),
            edit_call=call,
            locked=locked,
        )
    except Exception:
        log.exception("water seek preview")
        await _edit_call(
            call,
            "<b>Поиск оплачен</b>\n"
            "<i>Экран облития не открылся. Ответьте на сообщение этого человека "
            "и напишите «<code>Использовать 🔫</code>» — так повторная плата не нужна.</i>",
        )
    await call.answer()


def _ask_markup(offer_id: int, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        _button(word("leave"), stamp_callback(f"wg:leave:{int(offer_id)}", owner_id), "danger"),
        _button(word("pour"), stamp_callback(f"wg:pour:{int(offer_id)}", owner_id), "success"),
    ]])


def _money(amount: int) -> str:
    return f"{int(amount):,}".replace(",", " ")


def _guard_span(row) -> str:
    if row["until"] is None:
        return "навсегда"
    return "ещё " + _left_of(row["until"], datetime.now(timezone.utc))


def _visible_name(user) -> str:
    if user is None:
        return ""
    parts = []
    for piece in (getattr(user, "first_name", ""), getattr(user, "last_name", "")):
        text = " ".join(str(piece or "").split())
        if text:
            parts.append(text)
    if parts:
        return " ".join(parts)
    username = " ".join(str(getattr(user, "username", "") or "").split())
    return f"@{username}" if username else ""


async def _target_name(target_id: int, message=None) -> str:
    reply = getattr(message, "reply_to_message", None) if message is not None else None
    user = getattr(reply, "from_user", None) if reply is not None else None
    try:
        same = user is not None and int(getattr(user, "id", 0) or 0) == int(target_id)
    except (TypeError, ValueError):
        same = False
    if same:
        found = _visible_name(user)
        if found:
            return found
    try:
        row = await db.pool.fetchrow(
            "SELECT first_name, username FROM users WHERE user_id = $1",
            int(target_id),
        )
    except Exception:
        row = None
    if not row:
        return ""
    name = " ".join(str(row["first_name"] or "").split())
    if name:
        return name
    username = " ".join(str(row["username"] or "").split())
    return f"@{username}" if username else ""


async def _calm_words(target_id: int, calm: dict, message=None) -> str:
    name = await _target_name(target_id, message)
    return calm_shot_text(
        name,
        calm.get("played"),
        calm.get("need"),
        calm.get("left_sec"),
    )


async def _calm_of(user_id: int) -> dict:
    from bot.funcs.calm_hold import calm_state
    try:
        return await calm_state(db, int(user_id))
    except Exception:
        log.exception("water calm")
        return {
            "played": 0, "need": 5, "hours": 24, "seconds": 86400,
            "left_sec": 86400, "calm": False, "enabled": False, "left": 5,
        }


async def _quote_shot(target_id: int, rules: dict, now) -> dict:
    """Сколько этот человек отдаст прямо сейчас. Тот же расчёт, что у выстрела."""
    empty = {"kind": "unknown", "amount": 0, "percent": 0, "payout": 0, "shield": None}
    target_shield = await _shield(target_id)
    if _still(target_shield):
        return {**empty, "kind": "shield", "shield": target_shield}
    calm = await _calm_of(target_id)
    if calm["calm"]:
        return {**empty, "kind": "calm", "calm": calm}
    enemy = await _inventory(target_id)
    if enemy["row"] is None:
        return empty
    if enemy["balance"] < rules["poorBalance"]:
        return {**empty, "kind": "broke"}
    taken_today = int(await db.pool.fetchval(
        """
        SELECT COALESCE(SUM(amount), 0) FROM water_splashes
        WHERE target_id = $1 AND outcome = 'hit' AND created_at > $2
        """,
        int(target_id), now - timedelta(hours=24),
    ) or 0)
    day_left = max(0, rules["dayCap"] - taken_today)
    if day_left < 1:
        return {**empty, "kind": "day"}
    percent = random.randint(rules["percentLow"], rules["percentHigh"])
    amount = take_amount(
        enemy["balance"], percent,
        cap=rules["shotCap"], day_left=day_left, poor=rules["poorBalance"],
    )
    if amount < 1:
        return {**empty, "kind": "dry"}
    payout, _cut = split_take(amount, rules["commissionPercent"])
    return {
        "kind": "hit", "amount": int(amount), "percent": int(percent),
        "payout": int(payout), "shield": None,
    }


async def _preview_shot(message, user_id: int, target_id: int, now, day_start, edit_call=None, locked=None) -> None:
    """Показывает сумму или срок защиты. Вода списывается только после «Облить»."""
    rules = await _shot_rules()
    locked = locked or {}
    target_shield = await _shield(target_id)
    kind = "hit"
    amount = 0
    percent = 0
    if _still(target_shield):
        kind = "shield"
    else:
        calm = await _calm_of(target_id)
        if calm["calm"]:
            text = await _calm_words(target_id, calm, message)
            if edit_call is not None:
                await _edit_call(edit_call, text)
                return
            await message.reply(text, parse_mode="HTML")
            return
        enemy = await _inventory(target_id)
        if enemy["row"] is None:
            await message.reply(screen_text("shot_unknown"), parse_mode="HTML")
            return
        if enemy["balance"] < rules["poorBalance"]:
            kind = "broke"
        else:
            taken_today = int(await db.pool.fetchval(
                """
                SELECT COALESCE(SUM(amount), 0) FROM water_splashes
                WHERE target_id = $1 AND outcome = 'hit' AND created_at > $2
                """,
                int(target_id), day_start,
            ) or 0)
            day_left = max(0, rules["dayCap"] - taken_today)
            if day_left < 1:
                await message.reply(screen_text("shot_day"), parse_mode="HTML")
                return
            percent = int(locked.get("percent") or 0) or random.randint(rules["percentLow"], rules["percentHigh"])
            percent = max(rules["percentLow"], min(rules["percentHigh"], percent))
            amount = take_amount(
                enemy["balance"], percent,
                cap=rules["shotCap"], day_left=day_left, poor=rules["poorBalance"],
            )
            stored = int(locked.get("amount") or 0)
            if stored > 0:
                amount = min(stored, amount)
            if amount < 1:
                await message.reply(screen_text("shot_dry"), parse_mode="HTML")
                return
    offer_id = await db.pool.fetchval(
        """
        INSERT INTO water_shot_offers (shooter_id, target_id, chat_id, amount, percent, kind)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        int(user_id), int(target_id), int(message.chat.id), int(amount), int(percent), kind,
    )
    if kind == "shield":
        view = _kind_view(target_shield["kind"])
        text = screen_text(
            "shot_guard",
            mark=shield_mark(target_shield["kind"]),
            name=view["name"],
            span=_guard_span(target_shield),
        )
    elif kind == "broke":
        text = screen_text("shot_ask_broke")
    else:
        payout, fee = split_take(amount, rules["commissionPercent"])
        text = screen_text("shot_ask", amount=_money(amount))
        if fee:
            text = text + "\n" + screen_text(
                "shot_fee",
                payout=_money(payout),
                fee=_money(fee),
                group=fee_group_name(rules["feeChatId"]),
            )
    markup = _ask_markup(offer_id, user_id)
    if edit_call is not None:
        await _edit_call(edit_call, text, markup)
        return
    await message.reply(text, parse_mode="HTML", reply_markup=markup)


async def _apply_hit(user_id: int, target_id: int, chat_id: int, amount: int, now) -> tuple[str, object]:
    """Перевод через общий путь баланса: база, история и кэш меняются вместе."""
    calm = await _calm_of(target_id)
    if calm.get("calm"):
        raise CalmHold(await _calm_words(target_id, calm))
    rules = await _shot_rules()
    payout, fee = split_take(int(amount), rules["commissionPercent"])
    await db.transfer_currency(int(target_id), int(user_id), int(amount), word("history_shot"))
    kept = await _keep_project_fee(user_id, fee, int(rules["feeChatId"]))
    received = payout if kept else int(amount)
    await _log(user_id, target_id, chat_id, amount, "hit", fee=kept)
    towel = towel_amount(amount)
    until = now + timedelta(hours=TOWEL_HOURS)
    towel_id = await db.pool.fetchval(
        """
        INSERT INTO water_towels (user_id, amount, until)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        int(target_id), int(towel), until,
    )
    text = screen_text(
        "shot_hit",
        amount=_money(received),
        towel=_money(towel),
        hours=hours_phrase(TOWEL_HOURS),
    )
    if kept:
        text = text + "\n" + screen_text(
            "shot_fee",
            payout=_money(received),
            fee=_money(kept),
            group=fee_group_name(rules["feeChatId"]),
        )
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=word("towel_btn", amount=_money(towel)),
            callback_data=stamp_callback(f"wg:towel:{int(towel_id)}", target_id),
            style="success",
        ),
    ]])
    return text, markup


async def _finish_pour(call, offer_id: int) -> None:
    row = await db.pool.fetchrow(
        """
        DELETE FROM water_shot_offers
        WHERE id = $1 AND shooter_id = $2
        RETURNING shooter_id, target_id, chat_id, amount, percent, kind
        """,
        int(offer_id), int(call.from_user.id),
    )
    if not row:
        await call.answer(word("offer_gone"), show_alert=True)
        return
    user_id = int(row["shooter_id"])
    target_id = int(row["target_id"])
    chat_id = int(row["chat_id"])
    bag = await _inventory(user_id)
    items = bag["items"]
    pistol_left = await _holds(user_id, "pistoletik", items)
    water_left = await _holds(user_id, "watercraft", items)
    if not pistol_left or not water_left:
        missing = word("missing_pistol") if not pistol_left else word("missing_water")
        await _edit_call(call, screen_text("splash_need", missing=missing))
        await call.answer()
        return
    now = datetime.now(timezone.utc)
    rules = await _shot_rules()
    blocked = await _pistol_block_text(user_id, rules, now)
    if blocked:
        await _edit_call(call, blocked)
        await call.answer()
        return
    shield = await _shield(target_id)
    if _still(shield):
        await _spend_water(user_id, items)
        await _log(user_id, target_id, chat_id, 0, "shield")
        view = _kind_view(shield["kind"])
        await _edit_call(call, screen_text(
            "shot_bounce",
            title=f"{view['name']}: под защитой {_guard_span(shield)}",
        ))
        await call.answer()
        return
    calm = await _calm_of(target_id)
    if calm["calm"]:
        await _edit_call(call, await _calm_words(target_id, calm, getattr(call, "message", None)))
        await call.answer()
        return
    enemy = await _inventory(target_id)
    if enemy["row"] is None:
        await _edit_call(call, screen_text("shot_unknown"))
        await call.answer()
        return
    if enemy["balance"] < rules["poorBalance"]:
        await _spend_water(user_id, items)
        await _log(user_id, target_id, chat_id, 0, "broke")
        await _edit_call(call, screen_text("shot_broke", poor=rules["poorBalance"]))
        await call.answer()
        return
    if str(row["kind"]) == "broke":
        await _preview_shot(call.message, user_id, target_id, now, now - timedelta(hours=24), edit_call=call)
        await call.answer()
        return
    day_start = now - timedelta(hours=24)
    taken_today = int(await db.pool.fetchval(
        """
        SELECT COALESCE(SUM(amount), 0) FROM water_splashes
        WHERE target_id = $1 AND outcome = 'hit' AND created_at > $2
        """,
        target_id, day_start,
    ) or 0)
    day_left = max(0, rules["dayCap"] - taken_today)
    if day_left < 1:
        await _edit_call(call, screen_text("shot_day"))
        await call.answer()
        return
    percent = int(row["percent"] or 0) or random.randint(rules["percentLow"], rules["percentHigh"])
    amount = take_amount(
        enemy["balance"], percent,
        cap=rules["shotCap"], day_left=day_left, poor=rules["poorBalance"],
    )
    stored = int(row["amount"] or 0)
    if stored > 0:
        amount = min(stored, amount)
    if amount < 1:
        await _edit_call(call, screen_text("shot_dry"))
        await call.answer()
        return
    try:
        text, markup = await _apply_hit(user_id, target_id, chat_id, amount, now)
    except CalmHold as hold:
        await _edit_call(call, hold.text)
        await call.answer()
        return
    except InsufficientBalanceError as exc:
        screen = "shot_gift" if "подароч" in str(exc) else "shot_dry"
        await _edit_call(call, screen_text(screen))
        await call.answer()
        return
    await _spend_water(user_id, items)
    await _edit_call(call, text, markup)
    await call.answer()


async def _leave_shot(call, offer_id: int) -> None:
    row = await db.pool.fetchrow(
        """
        DELETE FROM water_shot_offers
        WHERE id = $1 AND shooter_id = $2
        RETURNING id
        """,
        int(offer_id), int(call.from_user.id),
    )
    if not row:
        await call.answer(word("offer_gone"), show_alert=True)
        return
    await _edit_call(call, screen_text("shot_cancel"))
    await call.answer()


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
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            until = await _apply_charge_until(conn, user_id, name1, spec, now)
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
                user_id, name1, until, _drip_for(name1, until), False,
            )
    term = hours_phrase(None) if until is None else _left_of(until, datetime.now(timezone.utc))
    await message.reply(
        worn_text(
            emoji=spec["emoji"],
            name=spec["name"],
            term=term,
            shoot=can_shoot(name1),
        ),
        parse_mode="HTML",
    )
    return True


async def _unequip(user_id: int) -> str:
    """Снимает защиту и кладёт предмет обратно. Срок замирает и едет с предметом."""
    await ensure()
    user_id = int(user_id)
    now = datetime.now(timezone.utc)
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", user_id)
            row = await conn.fetchrow(
                "SELECT kind, until FROM water_shields WHERE user_id = $1 FOR UPDATE",
                user_id,
            )
            if not _still(row):
                if row:
                    await conn.execute("DELETE FROM water_shields WHERE user_id = $1", user_id)
                return screen_text("shield_off_none") if not row else screen_text("shield_ended")
            spec = SHIELDS.get(str(row["kind"]))
            if not spec:
                return screen_text("shield_off_none")
            user = await conn.fetchrow(
                "SELECT items FROM users WHERE user_id = $1 FOR UPDATE",
                user_id,
            )
            if not user:
                return screen_text("shield_off_none")
            left = _charges().leftover_seconds(row["until"], now)
            if left == 0:
                await conn.execute("DELETE FROM water_shields WHERE user_id = $1", user_id)
                return screen_text("shield_ended")
            await _charges().give(conn, user_id, row["kind"], left)
            items = decode_items(user["items"])
            name = spec["name"]
            items[name] = int(items.get(name, 0) or 0) + 1
            await conn.execute(
                "UPDATE users SET items = $2 WHERE user_id = $1",
                user_id,
                encode_items(items),
            )
            await conn.execute("DELETE FROM water_shields WHERE user_id = $1", user_id)
    mark = shield_mark(row["kind"])
    if left is None:
        return screen_text("shield_removed_forever", mark=mark, name=spec["name"])
    return screen_text("shield_removed", mark=mark, name=spec["name"], left=left_phrase(left))


async def unequip_shield(message) -> None:
    try:
        text = await _unequip(message.from_user.id)
    except Exception:
        log.exception("water unequip")
        text = screen_text("shield_off_none")
    await message.reply(text, parse_mode="HTML", disable_web_page_preview=True)


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
            [_button(
                button["text"],
                stamp_callback(button["data"], user_id),
                button.get("style") or "default",
                button.get("emoji") or "",
            ) for button in row]
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
                        new_until = await _apply_charge_until(conn, user_id, name1, spec, now)
                        half = False
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
                            new_until = await _apply_charge_until(
                                conn, user_id, name1, spec, now, shield["until"],
                            )
                            half = False
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
        term = hours_phrase(None) if new_until is None else _left_of(new_until, datetime.now(timezone.utc))
        await _edit_call(call, fresh_instead_text(
            emoji=spec["emoji"],
            name=spec["name"],
            term=term,
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
        markup = _markup(name, call.message, owner_id=int(call.from_user.id), **slots)
    try:
        await call.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
    except Exception:
        await call.message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
    await call.answer()


@dp.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("wg:"))
async def water_click(call):
    await ensure()
    data = call.data
    clicker = int(call.from_user.id)
    owner = button_owner(data)
    if owner is None:
        await call.answer(word("button_old"), show_alert=True)
        return
    if owner != clicker:
        await call.answer(word("not_your_button"), show_alert=True)
        return
    data = strip_callback_owner(data)
    if data == "wg:off":
        try:
            text = await _unequip(clicker)
        except Exception:
            log.exception("water unequip button")
            text = screen_text("shield_off_none")
        await _show(call, "home", text, markup=_markup("home", call.message, owner_id=clicker))
        return
    if data.startswith("wg:seekno:"):
        try:
            offer_id = int(data.split(":")[2])
        except (IndexError, ValueError):
            await call.answer(word("offer_gone"), show_alert=True)
            return
        await _leave_seek(call, offer_id)
        return
    if data.startswith("wg:seekyes:"):
        try:
            offer_id = int(data.split(":")[2])
        except (IndexError, ValueError):
            await call.answer(word("offer_gone"), show_alert=True)
            return
        await _agree_seek(call, offer_id)
        return
    if data.startswith("wg:leave:"):
        try:
            offer_id = int(data.split(":")[2])
        except (IndexError, ValueError):
            await call.answer(word("offer_gone"), show_alert=True)
            return
        await _leave_shot(call, offer_id)
        return
    if data.startswith("wg:pour:"):
        try:
            offer_id = int(data.split(":")[2])
        except (IndexError, ValueError):
            await call.answer(word("offer_gone"), show_alert=True)
            return
        await _finish_pour(call, offer_id)
        return
    if data == "wg:home":
        try:
            text, markup = await _guide_view(call.from_user.id, call.message)
        except Exception:
            log.exception("water guide kit")
            text, markup = _home_text(), _markup("home", call.message, owner_id=clicker)
        await _show(call, "home", text, markup=markup)
        return
    if data == "wg:rules":
        await _show(call, "rules", _rules_text(await _shot_rules()))
        return
    if data == "wg:shield":
        rows = []
        for row in button_rows("shield"):
            built = []
            for button in row:
                button_data = str(button.get("data") or "")
                if button_data.startswith("wg:find:"):
                    if await _holds(call.from_user.id, button_data.split(":", 2)[2]):
                        continue
                built.append(_button(
                    button["text"],
                    stamp_callback(button_data, clicker),
                    button.get("style") or "default",
                    button.get("emoji") or "",
                ))
            if built:
                rows.append(built)
        try:
            worn = await _shield(call.from_user.id)
        except Exception:
            worn = None
        if _still(worn):
            rows.append([_off_button(clicker)])
        await _show(
            call,
            "shield",
            screen_text("shield", fee=EXTEND_FEE),
            markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        return
    if data in {"wg:splash", "wg:aim"}:
        bag = await _inventory(call.from_user.id)
        pistol = await _holds(call.from_user.id, "pistoletik", bag["items"])
        water = await _holds(call.from_user.id, "watercraft", bag["items"])
        if data == "wg:aim":
            if not pistol or not water:
                missing = word("missing_pistol") if not pistol else word("missing_water")
                await _show(
                    call,
                    "splash_need",
                    screen_text("splash_need", missing=missing),
                    markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(
                        pistol_missing=not pistol,
                        water_missing=not water,
                        owner_id=clicker,
                    )),
                )
                return
            text = screen_text("aim")
            markup = _markup("aim", call.message, owner_id=clicker)
            private = getattr(getattr(call.message, "chat", None), "type", "") == "private"
            if private:
                groups = await _group_button_rows()
                if groups:
                    text += "\n<i>Группы — кнопками ниже.</i>"
                    markup = InlineKeyboardMarkup(inline_keyboard=list(markup.inline_keyboard) + groups)
                else:
                    text += "\n<i>Ссылки на группу нет. Зайдите в группу сами.</i>"
            await _show(call, "aim", text, markup=markup)
            return
        if not pistol or not water:
            missing = word("missing_pistol") if not pistol else word("missing_water")
            await _show(
                call,
                "splash_need",
                screen_text("splash_need", missing=missing),
                markup=InlineKeyboardMarkup(inline_keyboard=_need_rows(
                    pistol_missing=not pistol,
                    water_missing=not water,
                    owner_id=clicker,
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
        if await _holds(call.from_user.id, key):
            text, step = await _advance_text(call.from_user.id, key)
            rows = _step_rows(step, clicker)
            private = getattr(getattr(call.message, "chat", None), "type", "") == "private"
            if step == "shoot" and private:
                groups = await _group_button_rows()
                rows = groups
                if not groups:
                    text += "\n<i>Ссылки на группу нет.</i>"
            await _show(
                call,
                "bought",
                text,
                markup=InlineKeyboardMarkup(inline_keyboard=rows),
            )
            return
        lot = await _own_lot(call.from_user.id, key)
        if lot:
            text = screen_text("own_lot", emoji=item["emoji"], name=item["name"])
            private = getattr(getattr(call.message, "chat", None), "type", "") == "private"
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [_open_button(word("open_unlot"), lot["startapp"], private, "danger")],
                [_button(BTN_BACK, stamp_callback("wg:home", clicker))],
            ])
            shown = call.message
            try:
                await call.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
            except Exception:
                shown = await call.message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
            try:
                await _remember_buy(call.from_user.id, shown.chat.id, shown.message_id, key)
            except Exception:
                log.exception("water buy prompt")
            await call.answer()
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
            [InlineKeyboardButton(text=BTN_BACK, callback_data=stamp_callback("wg:home", clicker), style="default")],
        ])
        shown = call.message
        try:
            await call.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
        except Exception:
            shown = await call.message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
        try:
            await _remember_buy(call.from_user.id, shown.chat.id, shown.message_id, key)
        except Exception:
            log.exception("water buy prompt")
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
        claimed = await db.pool.fetchrow(
            """
            UPDATE water_towels
            SET claimed = TRUE
            WHERE id = $1 AND user_id = $2 AND claimed = FALSE AND until > NOW()
            RETURNING amount
            """,
            towel_id,
            int(call.from_user.id),
        )
        if not claimed:
            await call.answer(word("towel_lost"), show_alert=True)
            return
        amount = int(claimed["amount"])
        updated = await db.update_user_balance(int(call.from_user.id), f"+{amount}")
        if updated is None:
            await db.pool.execute(
                "UPDATE water_towels SET claimed = FALSE WHERE id = $1",
                towel_id,
            )
            await call.answer(word("towel_lost"), show_alert=True)
            return
        try:
            await db.cutehistory_plus(call.from_user.id, amount, word("history_towel"))
        except Exception:
            log.warning("towel history failed", exc_info=True)
        shown = _money(amount)
        await _edit_call(call, screen_text("towel_taken", amount=shown))
        await call.answer(word("towel_got", amount=shown), show_alert=True)
        return
    await call.answer()
