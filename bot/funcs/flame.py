# -*- coding: utf-8 -*-
"""Живой огонёк: серия, тёплый час, профит, статусы, подарочный бонус."""
from __future__ import annotations

import asyncio
import hashlib
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SERVER = Path(__file__).resolve().parents[2] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from flame_engine import (  # noqa: E402
    advance,
    bonus_tokens,
    claim_restore,
    consume_bonus,
    ember_of,
    gift_config,
    help_html,
    leaderboard,
    load_board,
    log_loot,
    msk_today,
    profile_line,
    profit_targets,
    restore_view,
    roll_gift_extra,
    roll_gift_stake,
    rollover,
    streak_of,
    titles_list,
    try_warm_hit,
    _row_settings,
)
import flame_copy  # noqa: E402

flame_router = Router(name="flame")

_MSK = timezone(timedelta(hours=3))
_started = False
_last_text: dict[int, tuple[str, float]] = {}
_settings_cache: dict = {"at": 0.0, "value": None}


def _pool(db):
    return getattr(db, "pool", None)


async def official_ids() -> list[int]:
    try:
        from bot.admins.mute import official_chats_now
        return [int(chat) for chat in await official_chats_now()]
    except Exception:
        return []


async def cached_settings(db) -> dict:
    now = time.time()
    if _settings_cache["value"] is not None and now - _settings_cache["at"] < 20:
        return _settings_cache["value"]
    pool = _pool(db)
    if pool is None:
        return {}
    try:
        board = await load_board(pool)
        settings = board.get("settings") or {}
    except Exception:
        settings = {}
    _settings_cache["at"] = now
    _settings_cache["value"] = settings
    return settings


def filter_counts(db, message, *, min_words_fallback: int = 2) -> bool:
    """True = сообщение можно засчитать. Анти-фарм: мало слов / тот же текст подряд."""
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    words = len(str(text).split())
    settings = _settings_cache.get("value") or {}
    min_words = int(settings.get("min_words") or min_words_fallback)
    if words < min_words:
        return False
    if not settings.get("block_dup", True):
        return True
    uid = int(getattr(getattr(message, "from_user", None), "id", 0) or 0)
    if uid <= 0:
        return True
    digest = hashlib.sha1(str(text).strip().lower().encode("utf-8", "ignore")).hexdigest()
    prev = _last_text.get(uid)
    now = time.time()
    _last_text[uid] = (digest, now)
    if len(_last_text) > 8000:
        cutoff = now - 600
        dead = [key for key, val in _last_text.items() if val[1] < cutoff]
        for key in dead[:2000]:
            _last_text.pop(key, None)
    if prev and prev[0] == digest and now - prev[1] < 45:
        return False
    return True


async def note_flushed(db, pairs: list[tuple]) -> None:
    pool = _pool(db)
    if pool is None or not pairs:
        return
    chats = set(await official_ids())
    if not chats:
        return
    by_day = {}
    today = msk_today()
    for row in pairs:
        try:
            uid, cid, day = int(row[0]), int(row[1]), row[2]
            if isinstance(day, datetime):
                day = day.date()
        except Exception:
            continue
        if cid not in chats or day < today - timedelta(days=1):
            continue
        by_day.setdefault(day, set()).add(uid)
    done = 0
    for day in sorted(by_day):
        for uid in by_day[day]:
            if done >= 400:
                return
            done += 1
            try:
                result = await advance(pool, uid, list(chats), day)
            except Exception as exc:
                print(f"[FLAME] advance {uid}: {exc}")
                continue
            if not result:
                continue
            await _pay(db, uid, result.get("rewards") or [])
            await _tell_streak(uid, result)


async def note_live_message(db, user_id: int, chat_id: int) -> None:
    """Одно живое сообщение: тёплый час."""
    pool = _pool(db)
    if pool is None:
        return
    chats = set(await official_ids())
    if int(chat_id) not in chats:
        return
    try:
        gift = await try_warm_hit(pool, int(user_id))
    except Exception as exc:
        print(f"[FLAME] warm {user_id}: {exc}")
        return
    if not gift:
        return
    await _pay(db, int(user_id), [gift])
    await _tell_warm(int(user_id), gift)


async def _pay(db, user_id: int, rewards: list[dict]) -> None:
    for reward in rewards:
        kind = reward.get("kind")
        amount = int(reward.get("amount") or 1)
        try:
            if kind == "kuty":
                balance = await db.get_user_balance(user_id)
                await db.update_user_balance(user_id, int(balance or 0) + amount)
                try:
                    await db.cutehistory_plus(user_id, amount, "огонёк")
                except Exception:
                    pass
            elif kind == "item":
                name = str(reward.get("item_name") or "").strip()
                if name:
                    await db.add_item_to_inventory(user_id, name, amount)
        except Exception as exc:
            print(f"[FLAME] pay {user_id} {kind}: {exc}")


def _gift_words(rewards: list[dict]) -> str:
    gifts = []
    for reward in rewards or []:
        label = reward.get("label")
        if label:
            gifts.append(str(label))
            continue
        kind = reward.get("kind")
        amount = int(reward.get("amount") or 1)
        if kind == "kuty":
            gifts.append(f"{amount} кут")
        elif kind == "item" and reward.get("item_name"):
            gifts.append(str(reward["item_name"]))
        elif kind == "bonus_x2":
            gifts.append("бесплатное открытие бонуса ×2")
        elif kind == "bonus":
            gifts.append("бесплатное открытие бонуса")
    return ", ".join(gifts)


async def _tell_streak(user_id: int, result: dict) -> None:
    gifts = _gift_words(result.get("rewards") or [])
    title = str(result.get("title") or "").strip()
    label = result.get("label") or "1 день"
    await _dm(user_id, flame_copy.screen_streak(label, title, gifts))


async def _tell_warm(user_id: int, gift: dict) -> None:
    label = gift.get("label") or _gift_words([gift])
    await _dm(user_id, flame_copy.screen_warm(label))


async def _dm(user_id: int, text: str) -> None:
    try:
        from main import bot1
        await bot1.send_message(int(user_id), text, parse_mode="HTML")
    except Exception:
        pass


async def has_bonus_token(db, user_id: int) -> bool:
    pool = _pool(db)
    if pool is None:
        return False
    try:
        opens, x2 = await bonus_tokens(pool, int(user_id))
    except Exception:
        return False
    return opens > 0 or x2 > 0


async def take_bonus_token(db, user_id: int) -> str:
    pool = _pool(db)
    if pool is None:
        return ""
    try:
        return await consume_bonus(pool, int(user_id))
    except Exception:
        return ""


async def profile_html(db, user_id: int) -> str:
    pool = _pool(db)
    if pool is None:
        return ""
    try:
        settings = await cached_settings(db)
        if not settings.get("enabled"):
            return ""
        days = await streak_of(pool, int(user_id))
        titles = await titles_list(pool) if settings.get("status_enabled") else []
    except Exception:
        return ""
    return profile_line(days, titles)


async def help_text(db) -> str:
    pool = _pool(db)
    if pool is None:
        return help_html({"settings": {"enabled": False, "base_messages": 200, "min_words": 2}})
    try:
        board = await load_board(pool)
    except Exception:
        return help_html({"settings": {"enabled": False, "base_messages": 200, "min_words": 2}})
    return board.get("help") or help_html(board)


async def top_text(db) -> str:
    pool = _pool(db)
    people = []
    if pool is not None:
        try:
            board = await load_board(pool)
            titles = board.get("titles") or []
            people = await leaderboard(pool, 15, titles)
        except Exception:
            people = []
    if not people:
        return flame_copy.screen_top_empty()
    from bot.funcs.top import stat_person_html
    medals = {
        1: "<tg-emoji emoji-id='5294001020039363545'>🏆</tg-emoji>",
        2: "<tg-emoji emoji-id='5458612419116933783'>🏆</tg-emoji>",
        3: "<tg-emoji emoji-id='5469967260380612012'>🏆</tg-emoji>",
    }
    rows = []
    for index, person in enumerate(people, start=1):
        name = stat_person_html(person["name"], person.get("username"), person["userId"])
        mark = " · <i>личный рекорд</i>" if person.get("record") else ""
        title = f" · <b>{person['title']}</b>" if person.get("title") else ""
        prefix = medals.get(index, f"<b>{index}.</b>")
        rows.append(f"{prefix} {name} — <b>{person['label']}</b>{title}{mark}")
    return flame_copy.screen_top(rows)


async def load_gift(db) -> dict:
    pool = _pool(db)
    if pool is None:
        return {"enabled": False, "mult": 1, "kuty_min": 1, "kuty_max": 3, "drops": []}
    try:
        return await gift_config(pool)
    except Exception:
        return {"enabled": False, "mult": 1, "kuty_min": 1, "kuty_max": 3, "drops": []}


def gift_stake(conf: dict) -> int:
    return roll_gift_stake(conf)


def gift_extra(conf: dict) -> dict | None:
    return roll_gift_extra(conf)


async def note_gift_loot(db, user_id: int, kind: str, amount: int = 1, item_name: str = "", label: str = "") -> None:
    pool = _pool(db)
    if pool is None:
        return
    try:
        await log_loot(pool, int(user_id), "gift", kind, amount, item_name, label)
    except Exception:
        pass


async def _profit_loop(db) -> None:
    while True:
        try:
            pool = _pool(db)
            if pool is not None:
                for card in await profit_targets(pool):
                    await _send_profit(card)
        except Exception as exc:
            print(f"[FLAME] profit: {exc}")
        await asyncio.sleep(55)


async def _send_profit(card: dict) -> None:
    from flame_engine import _kind_words, span_label
    streak = card.get("label") or "1 день"
    title = str(card.get("title") or "").strip()
    nxt = card.get("next")
    if nxt:
        left = int(nxt["day"]) - int(card.get("streak") or 0)
        gift = _kind_words(nxt["kind"], nxt["amount"], nxt.get("item_name") or "")
        day_word = "день" if left == 1 else ("дня" if 2 <= left <= 4 else "дней")
        next_line = flame_copy.profit_next(span_label(int(nxt["day"])), left, day_word, gift)
    else:
        next_line = flame_copy.profit_next_done()
    labels = [row["label"] for row in (card.get("loot") or []) if row.get("label")]
    text = flame_copy.screen_profit(
        title=title,
        streak=streak,
        rank=str(card.get("rank") or "—"),
        kept=bool(card.get("keptToday")),
        next_line=next_line,
        loot_line=flame_copy.profit_loot(labels),
    )
    await _dm(int(card["userId"]), text)


async def _loop(db) -> None:
    while True:
        try:
            pool = _pool(db)
            if pool is not None:
                await rollover(pool)
                await cached_settings(db)
        except Exception as exc:
            print(f"[FLAME] rollover: {exc}")
        now = datetime.now(_MSK)
        nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=8, microsecond=0)
        await asyncio.sleep(max(30, (nxt - now).total_seconds()))


RESTORE_WORDS = {
    "вернуть огонёк",
    "вернуть огонек",
    "восстановить огонёк",
    "восстановить огонек",
    "/flameback",
}


def is_restore_text(text: str | None) -> bool:
    return (text or "").strip().lower() in RESTORE_WORDS


def _restore_keyboard(user_id: int, ways: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=str(way["label"])[:64], callback_data=f"flback:{int(user_id)}:{way['id']}")]
        for way in ways
    ]
    rows.append([InlineKeyboardButton(text="Отказаться", callback_data=f"flback:{int(user_id)}:no")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _fresh_settings(db) -> dict:
    pool = _pool(db)
    if pool is None:
        return {}
    from flame_engine import ensure_tables
    await ensure_tables(pool)
    row = await pool.fetchrow("SELECT * FROM flame_settings WHERE id = 1")
    return _row_settings(row)


async def offer_restore(message: Message, db) -> None:
    user = message.from_user
    if user is None:
        return
    pool = _pool(db)
    if pool is None:
        return
    settings = await _fresh_settings(db)
    state = await ember_of(pool, int(user.id))
    view = restore_view(
        streak=state["streak"],
        ember_days=state["ember_days"],
        ember_on=state["ember_on"],
        today=msk_today(),
        settings=settings,
    )
    markup = _restore_keyboard(int(user.id), view["ways"]) if view["kind"] == "offer" else None
    await message.reply(
        view["text"],
        parse_mode="HTML",
        reply_markup=markup,
        disable_web_page_preview=True,
    )


async def _item_count(db, user_id: int, name: str) -> int:
    from bot.db_create.items_codec import decode_items
    row = await db.pool.fetchrow("SELECT items FROM users WHERE user_id = $1", int(user_id))
    if not row:
        return 0
    return int(decode_items(row["items"]).get(name) or 0)


async def finish_restore(db, user_id: int, way: str) -> str:
    pool = _pool(db)
    if pool is None:
        return flame_copy.screen_restore_off()
    settings = await _fresh_settings(db)
    state = await ember_of(pool, int(user_id))
    view = restore_view(
        streak=state["streak"],
        ember_days=state["ember_days"],
        ember_on=state["ember_on"],
        today=msk_today(),
        settings=settings,
    )
    if view["kind"] != "offer":
        return view["text"]
    allowed = {item["id"] for item in view["ways"]}
    if way not in allowed:
        return view["text"]

    charged = False
    if way == "kuty":
        price = int(settings["restore_kuty"])
        balance = int(await db.get_user_balance(user_id) or 0)
        if balance < price:
            return flame_copy.screen_restore_poor(price)
        await db.update_user_balance(user_id, balance - price)
        charged = True
        try:
            await db.cutehistory_plus(user_id, -price, "вернуть огонёк")
        except Exception:
            pass
    else:
        name = str(settings["restore_item"] or "").strip()
        count = int(settings["restore_item_count"] or 1)
        if await _item_count(db, user_id, name) < count:
            return flame_copy.screen_restore_no_item(name, count)
        await db.remove_items_craft(user_id, name, count)
        charged = True
        price = 0

    try:
        got = await claim_restore(pool, int(user_id))
    except Exception:
        got = 0
    if got < 1:
        if charged and way == "kuty":
            back = int(await db.get_user_balance(user_id) or 0) + price
            await db.update_user_balance(user_id, back)
            try:
                await db.cutehistory_plus(user_id, price, "вернуть огонёк")
            except Exception:
                pass
        elif charged:
            await db.add_item_to_inventory(user_id, name, count)
        return flame_copy.screen_restore_busy()
    from flame_engine import span_label
    return flame_copy.screen_restore_done(span_label(got))


@flame_router.callback_query(F.data.startswith("flback:"))
async def on_restore_click(call: CallbackQuery) -> None:
    parts = (call.data or "").split(":")
    if len(parts) != 3 or call.from_user is None or call.message is None:
        await call.answer()
        return
    _, owner, way = parts
    if str(call.from_user.id) != owner:
        await call.answer("Эта кнопка не ваша", show_alert=True)
        return
    from bot.db_create.db import db
    if way == "no":
        await call.answer()
        try:
            await call.message.edit_text(flame_copy.screen_restore_cancel(), parse_mode="HTML")
        except Exception:
            pass
        return
    text = await finish_restore(db, int(call.from_user.id), way)
    await call.answer()
    try:
        await call.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await call.message.answer(text, parse_mode="HTML")


def start_flame_worker(db) -> None:
    global _started
    if _started:
        return
    _started = True
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_loop(db))
        loop.create_task(_profit_loop(db))
        loop.create_task(cached_settings(db))
    except RuntimeError:
        _started = False
