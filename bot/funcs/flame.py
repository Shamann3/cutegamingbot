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

from flame_copy import (  # noqa: E402
    HISTORY_GRANT,
    HISTORY_RESTORE,
    alert_no_item,
    alert_poor,
    alert_stranger,
    button_cancel,
    button_item,
    button_kuty,
    is_flame_help_text,
    is_restore_command,
    profit_loot,
    profit_next,
    profit_next_done,
    restore_ways,
    screen_profit,
    screen_restore_alive,
    screen_restore_busy,
    screen_restore_cancel,
    screen_restore_done,
    screen_restore_late,
    screen_restore_none,
    screen_restore_off,
    screen_restore_offer,
    screen_streak,
    screen_top,
    screen_top_empty,
    screen_warm,
    top_row,
)
from flame_engine import (  # noqa: E402
    advance,
    bonus_tokens,
    consume_bonus,
    gift_config,
    help_html,
    leaderboard,
    load_board,
    log_loot,
    msk_today,
    profile_line,
    profit_targets,
    restore_state,
    restore_view,
    roll_gift_extra,
    roll_gift_stake,
    rollover,
    streak_of,
    titles_list,
    try_warm_hit,
    _row_settings,
)

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
    """Выдать награды серии/тёплого часа.

    Куты — только с технических групп.
    Предметы — покупка из магазина/биржи за техгруппы (или запасные куты %).
    Ничего не создаём «из воздуха».
    """
    pool = _pool(db)
    fallback_pct = 30
    if pool is not None:
        try:
            conf = await gift_config(pool)
            fallback_pct = int(conf.get("fallback_pct") or 30)
        except Exception:
            pass
    for reward in rewards:
        kind = reward.get("kind")
        amount = int(reward.get("amount") or 1)
        try:
            if kind == "kuty":
                if pool is None or amount < 1:
                    continue
                from flame_bonus_plus import pay_user_from_tech
                paid = await pay_user_from_tech(pool, int(user_id), amount)
                if paid > 0:
                    try:
                        await db.cutehistory_plus(user_id, paid, HISTORY_GRANT)
                    except Exception:
                        pass
            elif kind == "item":
                name = str(reward.get("item_name") or "").strip()
                if not name or pool is None:
                    continue
                from flame_bonus_plus import acquire_bonus_item
                for _ in range(max(1, amount)):
                    got = await acquire_bonus_item(pool, int(user_id), [name], fallback_pct)
                    if not got.get("ok"):
                        break
                    if got.get("source") == "project_kuty":
                        add = int(got.get("project_kuty") or got.get("paid") or 0)
                        if add > 0:
                            try:
                                await db.cutehistory_plus(user_id, add, HISTORY_GRANT)
                            except Exception:
                                pass
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
    await _dm(
        user_id,
        screen_streak(
            result.get("label") or "1 день",
            str(result.get("title") or "").strip(),
            _gift_words(result.get("rewards") or []),
        ),
    )


async def _tell_warm(user_id: int, gift: dict) -> None:
    await _dm(user_id, screen_warm(gift.get("label") or _gift_words([gift])))


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
        return screen_top_empty()
    from bot.funcs.top import stat_person_html
    rows = []
    for index, person in enumerate(people, start=1):
        name = stat_person_html(person["name"], person.get("username"), person["userId"])
        rows.append(top_row(
            index,
            name,
            person["label"],
            person.get("title") or "",
            bool(person.get("record")),
        ))
    return screen_top(rows)


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
    nxt = card.get("next")
    if nxt:
        from flame_engine import _kind_words, span_label
        left = max(1, int(nxt["day"]) - int(card.get("streak") or 0))
        day_word = "день" if left == 1 else ("дня" if 2 <= left <= 4 else "дней")
        next_line = profit_next(
            span_label(int(nxt["day"])),
            left,
            day_word,
            _kind_words(nxt["kind"], nxt["amount"], nxt.get("item_name") or ""),
        )
    else:
        next_line = profit_next_done()
    labels = [row["label"] for row in (card.get("loot") or []) if row.get("label")]
    await _dm(int(card["userId"]), screen_profit(
        title=str(card.get("title") or "").strip(),
        streak=card.get("label") or "1 день",
        rank=str(card.get("rank") or "—"),
        kept=bool(card.get("keptToday")),
        next_line=next_line,
        loot_line=profit_loot(labels),
    ))


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


def is_restore_text(text: str) -> bool:
    return is_restore_command(text)


def is_flame_help(text: str) -> bool:
    return is_flame_help_text(text)


async def send_flame_help(message, db) -> None:
    """Справка огонька — тот же текст, что вкладка «Огонёк» в хелпе."""
    from bot.design.buttons import btn_help
    from bot.funcs.help import _help_register_message

    text = await help_text(db)
    sent = await message.reply(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=btn_help,
    )
    try:
        _help_register_message(int(message.from_user.id), int(sent.message_id))
    except Exception:
        pass


def _restore_screen(view: dict) -> str:
    code = view.get("code")
    if code == "ready":
        return screen_restore_offer(
            view.get("label") or "серия",
            int(view.get("days_left") or 1),
            restore_ways(
                kuty=int(view.get("kuty") or 0),
                item=str(view.get("item") or ""),
                count=int(view.get("count") or 1),
            ),
        )
    if code == "alive":
        return screen_restore_alive()
    if code == "late":
        return screen_restore_late()
    if code == "none":
        return screen_restore_none()
    return screen_restore_off()


def _restore_keyboard(user_id: int, view: dict):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    rows = []
    if int(view.get("kuty") or 0) > 0:
        rows.append([InlineKeyboardButton(
            text=button_kuty(int(view["kuty"]))[:64],
            callback_data=f"fl:kuty:{int(user_id)}",
            style="success",
        )])
    if view.get("item"):
        rows.append([InlineKeyboardButton(
            text=button_item(str(view["item"]), int(view.get("count") or 1))[:64],
            callback_data=f"fl:item:{int(user_id)}",
            style="primary",
        )])
    rows.append([InlineKeyboardButton(
        text=button_cancel()[:64],
        callback_data=f"fl:no:{int(user_id)}",
        style="danger",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def restore_command(message, db) -> None:
    user = getattr(message, "from_user", None)
    pool = _pool(db)
    if user is None or pool is None:
        return
    try:
        view = await restore_state(pool, int(user.id))
    except Exception as exc:
        print(f"[FLAME] restore {user.id}: {exc}")
        return
    markup = _restore_keyboard(user.id, view) if view.get("code") == "ready" else None
    try:
        await message.reply(
            _restore_screen(view),
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=True,
        )
    except Exception as exc:
        print(f"[FLAME] restore reply {user.id}: {exc}")


async def _locked_restore(conn, user_id: int, day):
    settings = _row_settings(await conn.fetchrow("SELECT * FROM flame_settings WHERE id = 1"))
    row = await conn.fetchrow(
        """
        SELECT streak_days, best_days, lost_streak, lost_on
        FROM flame_users WHERE user_id = $1 FOR UPDATE
        """,
        int(user_id),
    )
    view = restore_view(
        int(row["streak_days"] or 0) if row else 0,
        int(row["lost_streak"] or 0) if row else 0,
        row["lost_on"] if row else None,
        settings,
        day,
    )
    return row, view


async def _write_restored(conn, user_id: int, row, view, day) -> None:
    streak = int(view["streak"])
    best = max(int(row["best_days"] or 0), streak)
    await conn.execute(
        """
        UPDATE flame_users
        SET streak_days = $2,
            best_days = $3,
            last_kept = $4,
            lost_streak = 0,
            lost_on = NULL
        WHERE user_id = $1
        """,
        int(user_id),
        streak,
        best,
        day - timedelta(days=1),
    )


async def _charge_restore(db, user_id: int, pay: str) -> dict:
    pool = _pool(db)
    if pool is None:
        return {"code": "off"}
    day = msk_today()
    if pay == "kuty":
        view = await restore_state(pool, int(user_id), day)
        price = int(view.get("kuty") or 0)
        if view.get("code") != "ready" or price < 1:
            if view.get("code") == "ready":
                view["code"] = "off"
            return view
        charged = await db.update_user_balance(int(user_id), f"-{price}")
        if charged is None:
            view["code"] = "poor"
            return view
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    row, fresh = await _locked_restore(conn, int(user_id), day)
                    if fresh.get("code") != "ready" or row is None:
                        raise _RestoreClosed(fresh)
                    await _write_restored(conn, int(user_id), row, fresh, day)
                    fresh["ok"] = True
                    fresh["paid"] = "kuty"
                    view = fresh
        except _RestoreClosed as closed:
            await _refund_kuty(db, int(user_id), price)
            return closed.view
        except Exception:
            await _refund_kuty(db, int(user_id), price)
            raise
        return view
    if pay != "item":
        return {"code": "off"}

    from bot.db_create.items_codec import decode_items, encode_items

    async with pool.acquire() as conn:
        async with conn.transaction():
            row, view = await _locked_restore(conn, int(user_id), day)
            if view.get("code") != "ready" or row is None:
                return view
            name = str(view.get("item") or "").strip()
            count = int(view.get("count") or 0)
            if not name or count < 1:
                view["code"] = "off"
                return view
            inv = await conn.fetchrow(
                "SELECT items FROM users WHERE user_id = $1 FOR UPDATE",
                int(user_id),
            )
            items = decode_items(inv["items"] if inv else None)
            have = int(items.get(name) or 0)
            if have < count:
                view["code"] = "no_item"
                return view
            left = have - count
            if left <= 0:
                items.pop(name, None)
            else:
                items[name] = left
            await conn.execute(
                "UPDATE users SET items = $1 WHERE user_id = $2",
                encode_items(items),
                int(user_id),
            )
            await _write_restored(conn, int(user_id), row, view, day)
            view["ok"] = True
            view["paid"] = "item"
            return view


class _RestoreClosed(Exception):
    def __init__(self, view: dict):
        self.view = view


async def _refund_kuty(db, user_id: int, price: int) -> None:
    try:
        await db.update_user_balance(int(user_id), f"+{int(price)}")
    except Exception as exc:
        print(f"[FLAME] restore refund {user_id}: {exc}")


async def _edit_restore(call, text: str, markup) -> None:
    try:
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )
    except Exception:
        try:
            await call.message.answer(
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=markup,
            )
        except Exception:
            pass
    try:
        await call.answer()
    except Exception:
        pass


async def flame_click(call) -> None:
    data = str(getattr(call, "data", "") or "")
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "fl":
        return
    action, owner = parts[1], parts[2]
    clicker = int(getattr(getattr(call, "from_user", None), "id", 0) or 0)
    if not owner.isdigit() or int(owner) != clicker:
        try:
            await call.answer(alert_stranger(), show_alert=True)
        except Exception:
            pass
        return
    if action == "no":
        await _edit_restore(call, screen_restore_cancel(), None)
        return
    if action not in ("kuty", "item"):
        try:
            await call.answer()
        except Exception:
            pass
        return
    from main import db
    try:
        view = await _charge_restore(db, clicker, action)
    except Exception as exc:
        print(f"[FLAME] restore pay {clicker}: {exc}")
        try:
            await call.answer(screen_restore_busy(), show_alert=True)
        except Exception:
            pass
        return
    if view.get("ok"):
        if view.get("paid") == "kuty":
            try:
                await db.cutehistory_plus(clicker, -int(view.get("kuty") or 0), HISTORY_RESTORE)
            except Exception:
                pass
        await _edit_restore(call, screen_restore_done(view.get("label") or "серия"), None)
        return
    if view.get("code") == "poor":
        try:
            await call.answer(alert_poor(int(view.get("kuty") or 0)), show_alert=True)
        except Exception:
            pass
        return
    if view.get("code") == "no_item":
        try:
            await call.answer(
                alert_no_item(str(view.get("item") or "предмет"), int(view.get("count") or 1)),
                show_alert=True,
            )
        except Exception:
            pass
        return
    await _edit_restore(call, _restore_screen(view), None)
