# -*- coding: utf-8 -*-
"""Кейсы: подсказка, кнопки покупки и открытие. Покупка идёт как в водных играх."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.db_create import item_cost
from bot.db_create.items_codec import decode_items, encode_items
from bot.funcs.webapp_links import section_button_fields
from main import db, dp

_py = Path(__file__).resolve().parents[2] / "server" / "py"
if str(_py) not in sys.path:
    sys.path.insert(0, str(_py))

from cases.design import (  # noqa: E402
    KEY,
    button_owner,
    case_by_id,
    face,
    find_target,
    key_text,
    miss_text,
    need_key_text,
    opened_text,
    own_lot_text,
    HISTORY,
    found_text,
    held_text,
    public_case,
    roll_amount,
    stamp_callback,
)

log = logging.getLogger("case_desk")
_ready = False


def _icon(value) -> str:
    raw = str(value or "").strip()
    return raw if raw.isdigit() else ""


def _button(text: str, data: str, style: str, emoji: str) -> InlineKeyboardButton:
    fields = {
        "text": text,
        "callback_data": data,
        "style": style or "default",
    }
    icon = _icon(emoji)
    if icon:
        fields["icon_custom_emoji_id"] = icon
    return InlineKeyboardButton(**fields)


def _open_button(text: str, startapp: str, private: bool, emoji: str) -> InlineKeyboardButton:
    fields = section_button_fields(text, startapp, private=private)
    fields.pop("style", None)
    web_app_url = fields.pop("web_app_url", None)
    if web_app_url:
        fields["web_app"] = WebAppInfo(url=web_app_url)
    fields["style"] = "success"
    icon = _icon(emoji)
    if icon:
        fields["icon_custom_emoji_id"] = icon
    return InlineKeyboardButton(**fields)


def _private(message) -> bool:
    return getattr(getattr(message, "chat", None), "type", "") == "private"


def _count(items: dict, *names: str) -> int:
    wanted = {str(name).strip().lower() for name in names if str(name).strip()}
    total = 0
    for key, value in (items or {}).items():
        if str(key).strip().lower() not in wanted:
            continue
        try:
            total += int(value or 0)
        except (TypeError, ValueError):
            continue
    return total


async def ensure() -> None:
    global _ready
    if _ready:
        return
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS case_rules (
            case_id TEXT PRIMARY KEY,
            max_cute INT NOT NULL,
            bands JSONB NOT NULL
        )
        """
    )
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS case_buy_prompts (
            user_id BIGINT PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            target TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    _ready = True


async def _rules(case_id: str) -> dict:
    await ensure()
    row = None
    try:
        row = await db.pool.fetchrow(
            "SELECT max_cute, bands FROM case_rules WHERE case_id = $1",
            case_id,
        )
    except Exception:
        log.exception("case rules")
    stored = None
    if row:
        bands = row["bands"]
        if isinstance(bands, str):
            bands = json.loads(bands)
        stored = {"max": row["max_cute"], "bands": bands}
    return public_case(stored, case_id)


async def _dex(item: dict):
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


async def _holds(user_id: int, item: dict, items: dict | None = None) -> bool:
    if items is None:
        row = await db.pool.fetchrow("SELECT items FROM users WHERE user_id = $1", int(user_id))
        items = decode_items(row["items"]) if row else {}
    if _count(items, item["name"]) > 0:
        return True
    found = await _dex(item)
    return bool(found and _count(items, str(found["id"])) > 0)


async def _own_lot(user_id: int, item: dict):
    row = await _dex(item)
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


async def _offer(item: dict):
    row = await _dex(item)
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
    return {
        "where": "на бирже" if use_market else "в магазине",
        "place": "биржу" if use_market else "магазин",
        "startapp": f"{'market' if use_market else 'shop'}-{dex_id}",
    }


def _find_button(target: str, user_id: int) -> InlineKeyboardButton:
    item = face(target)
    title = item["name"] if item else "Предмет"
    emoji = item["premium"] if item else ""
    return _button(title, stamp_callback(f"cs:find:{target}", user_id), "success", emoji)


def _case_buttons(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_find_button(case_id, user_id)]
        for case_id in ("small", "mid", "large")
    ])


async def _remember(user_id: int, chat_id: int, message_id: int, target: str) -> None:
    await ensure()
    await db.pool.execute(
        """
        INSERT INTO case_buy_prompts (user_id, chat_id, message_id, target, updated_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET chat_id = EXCLUDED.chat_id,
            message_id = EXCLUDED.message_id,
            target = EXCLUDED.target,
            updated_at = NOW()
        """,
        int(user_id),
        int(chat_id),
        int(message_id),
        target,
    )


async def explain_key(user_id: int, message) -> None:
    shown = await message.reply(
        key_text(),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=_case_buttons(user_id),
    )
    try:
        await _remember(user_id, shown.chat.id, shown.message_id, "cases")
    except Exception:
        log.exception("case key prompt")


async def need_key(user_id: int, message, case_id: str) -> None:
    shown = await message.reply(
        need_key_text(case_id),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_find_button("key", user_id)]]),
    )
    try:
        await _remember(user_id, shown.chat.id, shown.message_id, case_id)
    except Exception:
        log.exception("case need prompt")


async def open_case(db_handle, user_id: int, message, case_id: str) -> None:
    item = case_by_id(case_id)
    if item is None:
        return
    user_data = await db_handle.fetch_all(
        "SELECT items, balance FROM users WHERE user_id=$1",
        (user_id,),
    )
    if not user_data:
        await message.reply(
            "<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> <b>Пользователь не найден.</b>",
            parse_mode="HTML",
        )
        return
    row = user_data[0]
    inventory = decode_items(row["items"])
    case_name = item["name"]
    key_name = KEY["name"]
    if _count(inventory, case_name) <= 0:
        await message.reply(
            f"<b>{item['emoji']} {case_name} не найден.</b>",
            parse_mode="HTML",
        )
        return
    if _count(inventory, key_name) <= 0:
        await need_key(user_id, message, case_id)
        return
    rules = await _rules(case_id)
    amount = roll_amount(rules["bands"])
    current = int(row["balance"] or 0)
    await db_handle.update_user_balance(user_id, current + amount)
    await db_handle.cutehistory_plus(user_id, amount, HISTORY[case_id])
    await message.reply(
        opened_text(case_id, amount, rules["max"]),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    inventory[key_name] = int(inventory.get(key_name) or 0) - 1
    if inventory[key_name] <= 0:
        inventory.pop(key_name, None)
    inventory[case_name] = int(inventory.get(case_name) or 0) - 1
    if inventory[case_name] <= 0:
        inventory.pop(case_name, None)
    await db_handle.fetch_all(
        "UPDATE users SET items=$1 WHERE user_id=$2",
        (encode_items(inventory), user_id),
    )
    await item_cost.record_losses(
        db_handle.pool,
        user_id,
        {case_name: 1, key_name: 1},
        reason=item_cost.REASON_CASE_OPEN,
        ref_kind="case",
    )


async def _show(call, text: str, markup: InlineKeyboardMarkup | None, target: str) -> None:
    shown = call.message
    try:
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )
    except Exception:
        shown = await call.message.answer(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )
    if target:
        try:
            await _remember(call.from_user.id, shown.chat.id, shown.message_id, target)
        except Exception:
            log.exception("case find prompt")


@dp.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("cs:"))
async def case_click(call):
    data = call.data or ""
    owner = button_owner(data)
    clicker = int(call.from_user.id)
    if owner is None:
        await call.answer("Кнопка устарела", show_alert=True)
        return
    if owner != clicker:
        await call.answer("Эта кнопка не ваша", show_alert=True)
        return
    target = find_target(data)
    item = face(target)
    if item is None:
        await call.answer("Такого предмета нет", show_alert=True)
        return
    try:
        await ensure()
        if await _holds(clicker, item):
            await _show(call, held_text(item["name"], item["emoji"], item["premium"]), InlineKeyboardMarkup(inline_keyboard=[]), "")
            await call.answer()
            return
        lot = await _own_lot(clicker, item)
        private = _private(call.message)
        if lot:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [_open_button("Снять лот", lot["startapp"], private, item["premium"])],
            ])
            await _show(call, own_lot_text(item["name"], item["emoji"], item["premium"]), markup, target)
            await call.answer()
            return
        offer = await _offer(item)
        if not offer:
            await _show(call, miss_text(item["name"], item["emoji"], item["premium"]), InlineKeyboardMarkup(inline_keyboard=[]), "")
            await call.answer()
            return
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [_open_button("Открыть покупку", offer["startapp"], private, item["premium"])],
        ])
        await _show(
            call,
            found_text(item["name"], item["emoji"], item["premium"], offer["where"], offer["place"]),
            markup,
            target,
        )
        await call.answer("Смотрю магазин и биржу")
    except Exception:
        log.exception("case find")
        await call.answer("Покупка сейчас не открылась", show_alert=True)
