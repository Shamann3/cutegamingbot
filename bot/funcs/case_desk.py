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
    HOW_ICON,
    KEY,
    buy_label,
    button_owner,
    case_by_id,
    closed_text,
    face,
    find_target,
    fund_ids,
    guide_home,
    guide_how,
    is_case_ask,
    key_text,
    miss_text,
    need_key_text,
    opened_text,
    own_lot_text,
    HISTORY,
    found_text,
    open_label,
    owns,
    public_case,
    ready_open_text,
    roll_amount,
    stamp_callback,
    take_plan,
)

log = logging.getLogger("case_desk")
_ready = False


class _FundShort(Exception):
    """Касса изменилась, пока приз списывался. Транзакция откатится."""


def _icon(value) -> str:
    raw = str(value or "").strip()
    return raw if raw.isdigit() else ""


def _button(text: str, data: str, emoji: str) -> InlineKeyboardButton:
    fields = {
        "text": text,
        "callback_data": data,
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
    await db.pool.execute(
        """
        CREATE TABLE IF NOT EXISTS case_opens (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            case_id TEXT NOT NULL,
            amount INT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    _ready = True


def _fund_chat_ids() -> list[int]:
    from bot.funcs.technical_chats import TECHNICAL_CHAT_IDS
    return sorted({int(chat_id) for chat_id in TECHNICAL_CHAT_IDS} | set(fund_ids()))


def _remember_balance(chat_id: int, chatbalance: int, dexbalance: int) -> None:
    try:
        from bot.db_create.db import BalanceSnapshot
        db.__fastlane_set__(int(chat_id), BalanceSnapshot(int(chatbalance), int(dexbalance or 0)))
    except Exception:
        log.exception("case fund cache")


async def _read_funds(conn=None):
    query = """
        SELECT chat_id, COALESCE(chatbalance, 0) AS balance, COALESCE(dexbalance, 0) AS dexbalance
        FROM chat
        WHERE COALESCE(is_technical, FALSE) = TRUE
           OR chat_id = ANY($1::bigint[])
    """
    ids = _fund_chat_ids()
    runner = conn or db.pool
    if conn is not None:
        return await runner.fetch(query + " FOR UPDATE", ids)
    return await runner.fetch(query, ids)


async def _fund_open() -> bool:
    try:
        rows = await _read_funds()
    except Exception:
        log.exception("case fund read")
        return False
    return sum(max(0, int(row["balance"] or 0)) for row in rows) >= 1


async def _draw_fund(amount: int):
    """Списать приз с технических групп целиком. None — кассы не хватило."""
    need = int(amount)
    if need < 1:
        return None
    try:
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                rows = await _read_funds(conn)
                groups = [
                    {"id": int(row["chat_id"]), "balance": int(row["balance"] or 0)}
                    for row in rows
                ]
                plan = take_plan(groups, need)
                if not plan:
                    return None
                snaps = []
                for step in plan:
                    row = await conn.fetchrow(
                        """
                        UPDATE chat
                        SET chatbalance = chatbalance - $1
                        WHERE chat_id = $2 AND COALESCE(chatbalance, 0) >= $1
                        RETURNING chatbalance, dexbalance
                        """,
                        int(step["take"]),
                        int(step["id"]),
                    )
                    if row is None:
                        raise _FundShort()
                    snaps.append((int(step["id"]), int(row["chatbalance"]), int(row["dexbalance"] or 0)))
        for chat_id, chatbalance, dexbalance in snaps:
            _remember_balance(chat_id, chatbalance, dexbalance)
        return plan
    except _FundShort:
        return None
    except Exception:
        log.exception("case fund")
        return None


async def _refund_fund(plan) -> None:
    for step in plan or []:
        try:
            row = await db.pool.fetchrow(
                """
                UPDATE chat
                SET chatbalance = chatbalance + $1
                WHERE chat_id = $2
                RETURNING chatbalance, dexbalance
                """,
                int(step["take"]),
                int(step["id"]),
            )
        except Exception:
            log.exception("case fund refund")
            continue
        if row:
            _remember_balance(int(step["id"]), int(row["chatbalance"]), int(row["dexbalance"] or 0))


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


async def _bag(user_id: int) -> dict:
    row = await db.pool.fetchrow("SELECT items FROM users WHERE user_id = $1", int(user_id))
    return decode_items(row["items"]) if row else {}


async def _holds(user_id: int, item: dict, items: dict | None = None) -> bool:
    if items is None:
        items = await _bag(user_id)
    if owns(items, item):
        return True
    found = await _dex(item)
    return bool(found and owns(items, item, found["id"]))


async def _held_cases(user_id: int, items: dict | None = None) -> list[dict]:
    if items is None:
        items = await _bag(user_id)
    found = []
    for case_id in ("small", "mid", "large"):
        item = face(case_id)
        if item and await _holds(user_id, item, items):
            found.append(item)
    return found


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


def _safe_startapp(startapp: str) -> bool:
    raw = str(startapp or "")
    kind, _, item_id = raw.partition("-")
    return kind in {"shop", "market", "own"} and item_id.isdigit()


def _find_button(target: str, user_id: int, origin: str = "home") -> InlineKeyboardButton:
    item = face(target)
    title = buy_label(item["name"]) if item else "Купить предмет"
    emoji = item["premium"] if item else ""
    step = origin if origin in {"home", "how"} else "home"
    return _button(title, stamp_callback(f"cs:find:{target}:{step}", user_id), emoji)


def _open_case_button(case_id: str, user_id: int) -> InlineKeyboardButton:
    item = face(case_id)
    title = open_label(item["name"]) if item else "Открыть кейс"
    return _button(title, stamp_callback(f"cs:open:{case_id}", user_id), item["premium"] if item else "")


def _back_button(user_id: int, step: str = "home") -> InlineKeyboardButton:
    where = step if step in {"home", "how"} else "home"
    return _guide_button("Назад", where, user_id, "")


def _link_button(text: str, startapp: str, private: bool, emoji: str, user_id: int) -> InlineKeyboardButton:
    """Покупка остаётся на этом сообщении: в личке приложение, в группе та же ссылка."""
    return _open_button(text, startapp, private, emoji)


def _buy_open_button(name: str, startapp: str, private: bool, emoji: str, user_id: int) -> InlineKeyboardButton:
    return _link_button(buy_label(name), startapp, private, emoji, user_id)


def _with_back(rows: list, user_id: int, step: str = "home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[*rows, [_back_button(user_id, step)]])


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


def _guide_button(text: str, step: str, user_id: int, emoji: str = "") -> InlineKeyboardButton:
    return _button(text, stamp_callback(f"cs:guide:{step}", user_id), emoji)


async def _guide_payload(user_id: int, step: str = "home"):
    bag = await _bag(user_id)
    has_key = await _holds(user_id, KEY, bag)
    held = await _held_cases(user_id, bag)
    open_now = await _fund_open()
    if step == "how":
        ceilings = []
        for case_id in ("small", "mid", "large"):
            ceilings.append(int((await _rules(case_id))["max"]))
        rows = []
        if not has_key:
            rows.append([_find_button("key", user_id, "how")])
        for case_id in ("small", "mid", "large"):
            if not any(item["id"] == case_id for item in held):
                rows.append([_find_button(case_id, user_id, "how")])
        rows.append([_back_button(user_id, "home")])
        return guide_how(ceilings), InlineKeyboardMarkup(inline_keyboard=rows)
    rows = []
    if open_now and has_key:
        for item in held:
            rows.append([_open_case_button(item["id"], user_id)])
    if not has_key:
        rows.append([_find_button("key", user_id, "home")])
    for case_id in ("small", "mid", "large"):
        if not any(item["id"] == case_id for item in held):
            rows.append([_find_button(case_id, user_id, "home")])
    rows.append([_guide_button("Как открыть", "how", user_id, HOW_ICON)])
    return guide_home(has_key=has_key, held=held, open_now=open_now), InlineKeyboardMarkup(inline_keyboard=rows)


async def open_guide(message) -> None:
    user_id = int(message.from_user.id)
    try:
        text, markup = await _guide_payload(user_id, "home")
    except Exception:
        log.exception("case guide")
        text = guide_home(has_key=False, held=[])
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [_guide_button("Как открыть", "how", user_id, HOW_ICON)],
        ])
    await message.reply(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=markup,
    )


def _desk_markup(user_id: int, back: bool) -> InlineKeyboardMarkup:
    label = "Назад" if back else "Кейсы"
    icon = "" if back else KEY["premium"]
    return InlineKeyboardMarkup(inline_keyboard=[[_guide_button(label, "home", user_id, icon)]])


async def explain_key(user_id: int, message) -> None:
    held = await _held_cases(user_id)
    if held and await _fund_open():
        rows = [[_open_case_button(item["id"], user_id)] for item in held]
        await message.reply(
            ready_open_text(held, button=True),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_with_back(rows, user_id),
        )
        return
    if held:
        await message.reply(
            closed_text(),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_desk_markup(user_id, back=False),
        )
        return
    shown = await message.reply(
        key_text(),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=_with_back([[_find_button(case_id, user_id)] for case_id in ("small", "mid", "large")], user_id),
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
        reply_markup=_with_back([[_find_button("key", user_id)]], user_id),
    )
    try:
        await _remember(user_id, shown.chat.id, shown.message_id, case_id)
    except Exception:
        log.exception("case need prompt")


async def _say(message, call, text: str, markup: InlineKeyboardMarkup | None) -> None:
    if call is not None:
        await _show(call, text, markup, "")
        return
    await message.reply(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=markup,
    )


async def open_case(db_handle, user_id: int, message, case_id: str, call=None) -> None:
    item = case_by_id(case_id)
    if item is None:
        return
    desk = _desk_markup(user_id, back=call is not None)
    user_data = await db_handle.fetch_all(
        "SELECT items, balance FROM users WHERE user_id=$1",
        (user_id,),
    )
    if not user_data:
        await _say(
            message,
            call,
            "<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> <b>Пользователь не найден.</b>",
            desk,
        )
        return
    row = user_data[0]
    inventory = decode_items(row["items"])
    case_name = item["name"]
    key_name = KEY["name"]
    if _count(inventory, case_name) <= 0:
        await _say(message, call, f"<b>{item['emoji']} {case_name} не найден.</b>", desk)
        return
    if _count(inventory, key_name) <= 0:
        if call is not None:
            await _show(
                call,
                need_key_text(case_id),
                _with_back([[_find_button("key", user_id)]], user_id),
                case_id,
            )
            return
        await need_key(user_id, message, case_id)
        return
    rules = await _rules(case_id)
    amount = roll_amount(rules["bands"])
    plan = await _draw_fund(amount)
    if not plan:
        await _say(message, call, closed_text(), desk)
        return
    current = int(row["balance"] or 0)
    credited = False
    try:
        await db_handle.update_user_balance(user_id, current + amount)
        credited = True
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
    except Exception:
        log.exception("case open")
        await _refund_fund(plan)
        if credited:
            try:
                await db_handle.update_user_balance(user_id, current)
            except Exception:
                log.exception("case open restore")
        await _say(message, call, closed_text(), desk)
        return
    try:
        await item_cost.record_losses(
            db_handle.pool,
            user_id,
            {case_name: 1, key_name: 1},
            reason=item_cost.REASON_CASE_OPEN,
            ref_kind="case",
        )
        await db_handle.cutehistory_plus(user_id, amount, HISTORY[case_id])
        await db_handle.pool.execute(
            "INSERT INTO case_opens (user_id, case_id, amount) VALUES ($1, $2, $3)",
            int(user_id),
            case_id,
            int(amount),
        )
    except Exception:
        log.exception("case open log")
    await _say(message, call, opened_text(case_id, amount, rules["max"]), desk)


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
    if getattr(call, "from_user", None) is None:
        await call.answer("Эта кнопка не ваша", show_alert=True)
        return
    clicker = int(call.from_user.id)
    if owner is None:
        await call.answer("Кнопка устарела", show_alert=True)
        return
    if owner != clicker:
        await call.answer("Эта кнопка не ваша", show_alert=True)
        return
    parts = data.split(":")
    if parts[1:2] == ["guide"]:
        step = parts[2] if len(parts) >= 3 else "home"
        try:
            text, markup = await _guide_payload(clicker, "how" if step == "how" else "home")
            await _show(call, text, markup, "")
            await call.answer()
        except Exception:
            log.exception("case guide")
            await call.answer("Справка сейчас не открылась", show_alert=True)
        return
    if parts[1:2] == ["open"]:
        case_id = parts[2] if len(parts) >= 3 else ""
        if case_by_id(case_id) is None:
            await call.answer("Такого кейса нет", show_alert=True)
            return
        await call.answer()
        try:
            await open_case(db, clicker, call.message, case_id, call=call)
        except Exception:
            log.exception("case open button")
            await _show(call, closed_text(), _desk_markup(clicker, back=True), "")
        return
    if parts[1:2] == ["go"]:
        startapp = parts[2] if len(parts) >= 3 else ""
        if not _safe_startapp(startapp):
            await call.answer("Покупка не открылась", show_alert=True)
            return
        kind, _, raw_id = startapp.partition("-")
        row = await db.pool.fetchrow("SELECT name FROM dex WHERE id = $1", int(raw_id))
        name = str(row["name"]) if row and row["name"] else "предмет"
        title = "Снять лот" if kind == "own" else buy_label(name)
        private = _private(call.message)
        markup = _with_back(
            [[_open_button(title, startapp, private, "")]],
            clicker,
        )
        await _show(call, f"<b>{title}</b>\n<i>Кнопка откроет это здесь.</i>", markup, "")
        await call.answer()
        return
    target = find_target(data)
    item = face(target)
    if item is None:
        await call.answer("Такого предмета нет", show_alert=True)
        return
    origin = parts[3] if len(parts) >= 5 and parts[3] in {"home", "how"} else "home"
    try:
        await ensure()
        if await _holds(clicker, item):
            bag = await _bag(clicker)
            if target == "key":
                held = await _held_cases(clicker, bag)
                if held and await _fund_open():
                    rows = [[_open_case_button(held_item["id"], clicker)] for held_item in held]
                    await _show(call, ready_open_text(held, button=True), _with_back(rows, clicker, origin), "")
                elif held:
                    await _show(call, closed_text(), _with_back([], clicker, origin), "")
                else:
                    rows = [[_find_button(case_id, clicker, origin)] for case_id in ("small", "mid", "large")]
                    await _show(call, key_text(), _with_back(rows, clicker, origin), "cases")
            elif await _holds(clicker, KEY, bag) and await _fund_open():
                await _show(
                    call,
                    ready_open_text([item], button=True),
                    _with_back([[_open_case_button(target, clicker)]], clicker, origin),
                    "",
                )
            elif await _holds(clicker, KEY, bag):
                await _show(call, closed_text(), _with_back([], clicker, origin), "")
            else:
                await _show(
                    call,
                    need_key_text(target),
                    _with_back([[_find_button("key", clicker, origin)]], clicker, origin),
                    target,
                )
            await call.answer()
            return
        lot = await _own_lot(clicker, item)
        private = _private(call.message)
        if lot:
            markup = _with_back(
                [[_link_button("Снять лот", lot["startapp"], private, item["premium"], clicker)]],
                clicker,
                origin,
            )
            await _show(call, own_lot_text(item["name"], item["emoji"], item["premium"]), markup, target)
            await call.answer()
            return
        offer = await _offer(item)
        if not offer:
            await _show(
                call,
                miss_text(item["name"], item["emoji"], item["premium"]),
                _with_back([], clicker, origin),
                "",
            )
            await call.answer()
            return
        note = found_text(item["name"], item["emoji"], item["premium"], offer["where"], offer["place"])
        markup = _with_back(
            [[_buy_open_button(item["name"], offer["startapp"], private, item["premium"], clicker)]],
            clicker,
            origin,
        )
        await _show(call, note, markup, target)
        await call.answer("Смотрю магазин и биржу")
    except Exception:
        log.exception("case find")
        await call.answer("Покупка сейчас не открылась", show_alert=True)
