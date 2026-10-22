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
    roll_gift_extra,
    roll_gift_stake,
    rollover,
    streak_of,
    titles_list,
    try_warm_hit,
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
    head = f"<b>{title}</b>\n" if title else ""
    extra = (
        f"\n\n<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji> "
        f"Вам: <b>{gifts}</b>"
        if gifts
        else ""
    )
    text = (
        f"<tg-emoji emoji-id='5355118129783553944'>⚫️</tg-emoji> "
        f"<b>Огонёк уже {label}</b>\n"
        f"{head}"
        f"<blockquote>День закрыт.\n"
        "Завтра снова наберите норму — серия продолжится.</blockquote>"
        f"{extra}"
    )
    await _dm(user_id, text)


async def _tell_warm(user_id: int, gift: dict) -> None:
    label = gift.get("label") or _gift_words([gift])
    text = (
        f"<tg-emoji emoji-id='5296561370303592127'>🌟</tg-emoji> "
        f"<b>Тёплый час</b>\n"
        f"<blockquote>Вы писали в удачный час — вот награда.</blockquote>\n"
        f"<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji> <b>{label}</b>"
    )
    await _dm(user_id, text)


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
        return (
            "<tg-emoji emoji-id='5354962501643578130'>⚫️</tg-emoji> "
            "<b>Лучшие огоньки</b>\n"
            "<blockquote>Здесь самые длинные серии.\n"
            "<i>Пока пусто — закройте норму дня, и вы появитесь в списке.</i></blockquote>"
        )
    from bot.funcs.top import stat_person_html
    lines = [
        "<tg-emoji emoji-id='5354962501643578130'>⚫️</tg-emoji> <b>Лучшие огоньки</b>",
        "<i>Самые длинные живые серии</i>",
        "",
    ]
    medals = {
        1: "<tg-emoji emoji-id='5294001020039363545'>🏆</tg-emoji>",
        2: "<tg-emoji emoji-id='5458612419116933783'>🏆</tg-emoji>",
        3: "<tg-emoji emoji-id='5469967260380612012'>🏆</tg-emoji>",
    }
    for index, person in enumerate(people, start=1):
        name = stat_person_html(person["name"], person.get("username"), person["userId"])
        mark = " · <i>личный рекорд</i>" if person.get("record") else ""
        title = f" · <b>{person['title']}</b>" if person.get("title") else ""
        prefix = medals.get(index, f"<b>{index}.</b>")
        lines.append(f"{prefix} {name} — <b>{person['label']}</b>{title}{mark}")
    return "\n".join(lines)


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
    streak = card.get("label") or "1 день"
    title = str(card.get("title") or "").strip()
    head = f"<b>{title}</b>\n" if title else ""
    next_line = ""
    nxt = card.get("next")
    if nxt:
        from flame_engine import _kind_words, span_label
        left = int(nxt["day"]) - int(card.get("streak") or 0)
        gift = _kind_words(nxt["kind"], nxt["amount"], nxt.get("item_name") or "")
        day_word = "день" if left == 1 else ("дня" if 2 <= left <= 4 else "дней")
        next_line = (
            f"\n<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji> "
            f"До награды за <b>{span_label(int(nxt['day']))}</b> — ещё <b>{left}</b> {day_word}: {gift}"
        )
    else:
        next_line = "\n<i>Все дневные награды уже собраны — держите серию дальше</i>"
    loot_rows = card.get("loot") or []
    if loot_rows:
        loot_line = (
            "\nСегодня получили: "
            + " · ".join(f"<b>{row['label']}</b>" for row in loot_rows if row.get("label"))
        )
    else:
        loot_line = ""
    kept = (
        "<tg-emoji emoji-id='5321021153219732362'>⚡️</tg-emoji> норма дня <b>закрыта</b>"
        if card.get("keptToday")
        else "<tg-emoji emoji-id='5467519850576354798'>❕</tg-emoji> норма дня <b>ещё открыта</b>"
    )
    text = (
        f"<tg-emoji emoji-id='5355118129783553944'>⚫️</tg-emoji> "
        f"<b>Ваш огонёк сегодня</b>\n{head}"
        f"<blockquote>Серия: <b>{streak}</b> · место: <b>#{card.get('rank') or '—'}</b>\n"
        f"{kept}</blockquote>"
        f"{next_line}{loot_line}"
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
