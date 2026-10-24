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
    announce_label,
    alert_poor,
    alert_stranger,
    button_cancel,
    button_item,
    button_kuty,
    is_flame_help_text,
    is_flame_mine_text,
    is_restore_command,
    kind_words,
    PROFILE_NO_STATUS,
    PROFILE_OUT,
    mine_button_back,
    mine_button_close,
    mine_button_restore,
    mine_button_rewards,
    mine_button_rules,
    mine_button_status,
    mine_button_warm,
    reward_day_card,
    reward_face,
    reward_mark,
    screen_mine,
    screen_mine_fail,
    screen_mine_how,
    screen_mine_off,
    screen_mine_rewards,
    screen_mine_status,
    screen_mine_warm,
    status_help_line,
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
    screen_reward_hall,
    screen_reward_private,
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
    live_streak,
    load_board,
    log_loot,
    msk_today,
    need_for,
    next_paying_day,
    profile_line,
    restore_price,
    rules_cached,
    span_label,
    title_for,
    profit_targets,
    restore_state,
    restore_view,
    roll_gift_extra,
    roll_gift_stake,
    rollover,
    messages_on,
    streak_pair,
    try_warm_hit,
    _row_settings,
)

_MSK = timezone(timedelta(hours=3))
_started = False
_last_text: dict[int, tuple[str, float]] = {}
_settings_cache: dict = {"at": 0.0, "value": None}


def _pool(db):
    return getattr(db, "pool", None)


_chats_cache = {"at": 0.0, "ids": None}


async def official_ids() -> list[int]:
    now = time.time()
    cached = _chats_cache.get("ids")
    if cached is not None and now - float(_chats_cache.get("at") or 0) < 20:
        return cached
    try:
        from bot.admins.mute import official_chats_now
        ids = [int(chat) for chat in await official_chats_now()]
    except Exception:
        ids = list(cached or [])
    _chats_cache["at"] = now
    _chats_cache["ids"] = ids
    return ids


async def cached_settings(db) -> dict:
    now = time.time()
    if _settings_cache["value"] is not None and now - _settings_cache["at"] < 20:
        return _settings_cache["value"]
    pool = _pool(db)
    if pool is None:
        return {}
    try:
        rules = await rules_cached(pool)
        settings = rules.get("settings") or {}
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
    jobs = []
    for day in sorted(by_day):
        for uid in by_day[day]:
            if len(jobs) >= 400:
                break
            jobs.append((uid, day))
        if len(jobs) >= 400:
            break
    if not jobs:
        return
    chat_ids = list(chats)
    gate = asyncio.Semaphore(6)

    async def _one(uid: int, day) -> None:
        async with gate:
            try:
                result = await advance(pool, uid, chat_ids, day)
            except Exception as exc:
                print(f"[FLAME] advance {uid}: {exc}")
                return
            if not result:
                return
            await _pay(db, uid, result.get("rewards") or [])
            await _tell_streak(db, uid, result)

    await asyncio.gather(*(_one(uid, day) for uid, day in jobs))


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


def _gift_labels(rewards: list[dict]) -> list[str]:
    gifts = []
    for reward in rewards or []:
        label = reward.get("label")
        if label:
            gifts.append(str(label))
            continue
        kind = reward.get("kind")
        amount = int(reward.get("amount") or 1)
        if kind in {"kuty", "item", "bonus", "bonus_x2"}:
            label = announce_label(str(kind or ""), amount, str(reward.get("item_name") or ""))
            if label:
                gifts.append(label)
    return gifts


def _gift_words(rewards: list[dict]) -> str:
    return ", ".join(_gift_labels(rewards))


async def _tell_streak(db, user_id: int, result: dict) -> None:
    label = result.get("label") or "1 день"
    title = str(result.get("title") or "").strip()
    gifts = _gift_labels(result.get("rewards") or [])
    if gifts:
        await _dm(user_id, screen_reward_private(label, title, gifts))
        asyncio.create_task(_hall_safe(db, int(user_id), label, gifts))
        return
    await _dm(user_id, screen_streak(label, title, ""))


async def _hall_safe(db, user_id: int, label: str, gifts: list[str]) -> None:
    try:
        await _announce_reward(db, user_id, label, gifts)
    except Exception as exc:
        print(f"[FLAME] hall {user_id}: {exc}")


_hall_lock = asyncio.Lock()


def _official_targets(chats) -> list[int]:
    targets = []
    seen = set()
    for raw in chats or []:
        try:
            chat_id = int(raw)
        except (TypeError, ValueError):
            continue
        if chat_id >= 0 or chat_id in seen:
            continue
        seen.add(chat_id)
        targets.append(chat_id)
    return targets


async def _send_hall(bot, chat_id: int, text: str) -> None:
    from aiogram.exceptions import TelegramRetryAfter

    for attempt in (1, 2):
        try:
            await bot.send_message(
                chat_id,
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return
        except TelegramRetryAfter as exc:
            wait = float(getattr(exc, "retry_after", 1) or 1) + 0.2
            if attempt == 2:
                print(f"[FLAME] hall {chat_id}: пауза {wait:.0f}с, пропуск")
                return
            await asyncio.sleep(wait)
        except Exception as exc:
            print(f"[FLAME] hall {chat_id}: {exc}")
            return


async def _announce_reward(db, user_id: int, label: str, gifts: list[str]) -> None:
    """Один и тот же короткий текст во все официальные группы проекта."""
    if not gifts:
        return
    pool = _pool(db)
    if pool is None:
        return
    targets = _official_targets(await official_ids())
    if not targets:
        return
    person = await pool.fetchrow(
        """
        SELECT COALESCE(first_name, '') AS first_name,
               COALESCE(username, '') AS username
        FROM users WHERE user_id = $1
        """,
        int(user_id),
    )
    from bot.funcs.top import stat_person_html
    name = stat_person_html(
        (person["first_name"] if person else "") or "Игрок",
        (person["username"] if person else "") or "",
        int(user_id),
    )
    text = screen_reward_hall(name, label, gifts)
    async with _hall_lock:
        from main import bot1
        for chat_id in targets:
            await _send_hall(bot1, chat_id, text)
            await asyncio.sleep(0.35)


async def _tell_warm(user_id: int, gift: dict) -> None:
    await _dm(user_id, screen_warm(gift.get("label") or _gift_words([gift])))


async def _dm(user_id: int, text: str) -> None:
    try:
        from main import bot1
        await bot1.send_message(
            int(user_id),
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
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


async def peek_bonus_kind(db, user_id: int) -> str:
    """Какой бесплатный бонус огонька есть: 'x2', 'open' или ''."""
    pool = _pool(db)
    if pool is None:
        return ""
    try:
        opens, x2 = await bonus_tokens(pool, int(user_id))
    except Exception:
        return ""
    if x2 > 0:
        return "x2"
    if opens > 0:
        return "open"
    return ""


async def take_bonus_token(db, user_id: int, prefer: str = "") -> str:
    pool = _pool(db)
    if pool is None:
        return ""
    try:
        return await consume_bonus(pool, int(user_id), prefer=prefer)
    except Exception:
        return ""


async def profile_html(db, user_id: int) -> str:
    pool = _pool(db)
    if pool is None:
        return ""
    try:
        rules = await rules_cached(pool)
        settings = rules.get("settings") or {}
        if not settings.get("enabled"):
            return ""
        days, best = await streak_pair(pool, int(user_id))
        titles = (rules.get("titles") or []) if settings.get("status_enabled") else []
    except Exception:
        return ""
    return profile_line(days, titles, best)


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


def is_flame_mine(text: str) -> bool:
    return is_flame_mine_text(text)


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


async def _mine_view(
    db,
    user_id: int,
    *,
    with_ladder: bool = False,
    with_progress: bool = True,
    with_warm: bool = False,
) -> dict | None:
    """Одна карточка человека: кэш правил и одна строка серии."""
    pool = _pool(db)
    if pool is None:
        return None
    rules = await rules_cached(pool)
    settings = rules.get("settings") or {}
    today = msk_today()
    row = await pool.fetchrow(
        """
        SELECT streak_days, best_days, last_kept, lost_streak, lost_on
        FROM flame_users WHERE user_id = $1
        """,
        int(user_id),
    )
    raw = int(row["streak_days"] or 0) if row else 0
    record = int(row["best_days"] or 0) if row else 0
    last = row["last_kept"] if row else None
    streak, best, kept = live_streak(raw, record, last, today)
    titles = (rules.get("titles") or []) if settings.get("status_enabled") else []
    badge = title_for(streak, titles) if streak > 0 else None
    now = PROFILE_OUT if streak <= 0 else span_label(streak)
    record_label = span_label(best) if best > 0 else PROFILE_NO_STATUS
    status = badge["title"] if badge else PROFILE_NO_STATUS
    status_emoji = badge["emoji_id"] if badge else ""
    enabled = bool(settings.get("enabled"))
    need = 0
    have = 0
    if enabled and (kept or with_progress):
        need = need_for(
            streak + 1,
            int(settings.get("base_messages") or 200),
            rules.get("steps") or [],
        )
        if with_progress and not kept:
            have = await messages_on(pool, int(user_id), today, await official_ids())
    rewards = rules.get("rewards") or []
    pay = next_paying_day(rewards, best)
    replay = streak < best
    card = ""
    if enabled and with_progress and pay:
        card = await _reward_cards(pool, rewards, {int(pay)})
    prize_today = bool(pay) and not replay and not kept and int(pay) == int(streak) + 1
    ladder = ""
    if with_ladder:
        ladder = await _reward_cards(pool, rewards)
    rises = any(
        int(step.get("from_day") or 0) > 1 and int(step.get("messages") or 0) > 0
        for step in (rules.get("steps") or [])
    )
    lost = int(row["lost_streak"] or 0) if row else 0
    lost_on = row["lost_on"] if row else None
    restore = restore_view(streak, lost, lost_on, settings, today)
    can_restore = bool(restore_price(settings).get("enabled"))
    show_restore = can_restore and (
        restore.get("code") == "ready" or (streak <= 0 and best > 0)
    )
    topics = []
    if show_restore and restore.get("code") == "ready":
        topics.append("restore")
    topics.extend(["rewards", "rules"])
    if settings.get("warm_enabled"):
        topics.append("warm")
    if titles:
        topics.append("status")
    if show_restore and restore.get("code") != "ready":
        topics.append("restore")
    home = ""
    if kept or with_progress or not enabled:
        home = screen_mine(
            now=now,
            record=record_label,
            status=status,
            status_emoji=status_emoji,
            today_done=bool(kept),
            have=have,
            need=need,
            words=int(settings.get("min_words") or 2),
            next_day=span_label(pay) if pay else "",
            next_card=card,
            prize_today=prize_today,
            replay=replay,
            fresh=streak <= 0 and best <= 0,
        )
    status_lines = [
        status_help_line(span_label(int(item.get("from_day") or 0)), str(item.get("title") or ""))
        for item in titles
        if int(item.get("from_day") or 0) > 0 and str(item.get("title") or "").strip()
    ]
    warm_text = ""
    if with_warm and settings.get("warm_enabled"):
        from flame_engine import ensure_warm_hour
        hour_n = await ensure_warm_hour(pool, today, settings)
        hour = ""
        if hour_n is not None:
            hour = f"{int(hour_n):02d}:00–{(int(hour_n) + 1) % 24:02d}:00"
        warm_text = screen_mine_warm(
            warm_from=span_label(int(settings.get("warm_min_day") or 1)),
            every=int(settings.get("warm_every") or 40),
            cap=int(settings.get("warm_cap") or 1),
            hour=hour,
        )
    return {
        "enabled": enabled,
        "topics": topics,
        "home": home,
        "how": screen_mine_how(
            base=int(settings.get("base_messages") or 200),
            words=int(settings.get("min_words") or 2),
            block_dup=bool(settings.get("block_dup", True)),
            rises=rises,
        ),
        "rewards_screen": screen_mine_rewards(ladder, replay),
        "status_screen": screen_mine_status(status_lines),
        "warm_screen": warm_text,
        "restore": restore,
    }


async def _reward_cards(pool, rewards: list, days: set | None = None) -> str:
    """Карточки дней. days=None — вся лестница. Длинный список обрезается у конца."""
    from flame_copy import MINE_REWARDS_MORE
    from flame_engine import _item_faces

    chosen = []
    for row in rewards or []:
        day = int(row.get("day") or 0)
        if day < 1:
            continue
        if days is not None and day not in days:
            continue
        chosen.append(row)
    faces = await _item_faces(pool, [
        str(row.get("item_name") or "")
        for row in chosen
        if str(row.get("kind") or "") == "item"
    ])
    by_day: dict[int, list] = {}
    for row in chosen:
        kind = str(row.get("kind") or "")
        amount = int(row.get("amount") or 1)
        item = str(row.get("item_name") or "")
        words = kind_words(kind, amount, item)
        if not words:
            continue
        face = faces.get(item.strip().casefold(), "") if kind == "item" else ""
        by_day.setdefault(int(row.get("day") or 0), []).append(
            (kind, reward_face(kind, face), words)
        )
    blocks = [
        reward_day_card(reward_mark(day), span_label(day), by_day[day])
        for day in sorted(by_day)
    ]
    if not blocks:
        return ""
    more = ""
    while len("\n\n".join(blocks)) > 3200 and len(blocks) > 1:
        blocks.pop()
        more = "\n\n" + MINE_REWARDS_MORE
    return "\n\n".join(blocks) + more


async def send_flame_mine(message, db) -> None:
    """Личная карточка на фразу «мой огонёк»."""
    user = getattr(message, "from_user", None)
    if user is None:
        return
    try:
        view = await _mine_view(db, int(user.id))
    except Exception as exc:
        print(f"[FLAME] mine {user.id}: {exc}")
        view = None
    if view is None:
        text, markup = screen_mine_fail(), None
    elif not view["enabled"]:
        text, markup = screen_mine_off(), _mine_keyboard(user.id, close_only=True)
    else:
        text = view["home"]
        markup = _mine_keyboard(user.id, topics=view["topics"])
    try:
        await message.reply(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )
    except Exception as exc:
        print(f"[FLAME] mine reply {getattr(user, 'id', 0)}: {exc}")


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


def _icon_button(text: str, data: str, icon: str = "", style: str = "primary"):
    from aiogram.types import InlineKeyboardButton

    kwargs = {
        "text": str(text or "")[:64],
        "callback_data": data,
        "style": style,
    }
    if icon:
        kwargs["icon_custom_emoji_id"] = str(icon)
    return InlineKeyboardButton(**kwargs)


_MINE_TOPICS = {
    "restore": (mine_button_restore, "restore", "5330346824299490543", "success"),
    "rewards": (mine_button_rewards, "rewards", "5438440765908874600", "success"),
    "rules": (mine_button_rules, "how", "5402485258211859739", "primary"),
    "warm": (mine_button_warm, "warm", "5354952069168009105", "primary"),
    "status": (mine_button_status, "status", "5952066863931331270", "primary"),
}


def _mine_keyboard(user_id: int, *, topics: list | None = None, back: bool = False, close_only: bool = False):
    """Короткие разделы по два. Вернуть, тёплый час и закрыть — на всю ширину, чтобы не промахнуться."""
    from aiogram.types import InlineKeyboardMarkup

    uid = int(user_id)
    if back:
        return InlineKeyboardMarkup(inline_keyboard=[[
            _icon_button(mine_button_back(), f"fm:home:{uid}", style="primary"),
        ]])
    if close_only:
        return InlineKeyboardMarkup(inline_keyboard=[[
            _icon_button(mine_button_close(), f"fm:close:{uid}", style="danger"),
        ]])
    wide = {"restore", "warm", "close"}
    items = []
    for key in topics or ["rewards", "rules"]:
        spec = _MINE_TOPICS.get(key)
        if spec is None:
            continue
        label, action, icon, style = spec
        items.append((key, _icon_button(label(), f"fm:{action}:{uid}", icon, style)))
    items.append(("close", _icon_button(mine_button_close(), f"fm:close:{uid}", style="danger")))
    rows = []
    pair = []
    for key, button in items:
        if key in wide:
            if pair:
                rows.append(pair)
                pair = []
            rows.append([button])
            continue
        pair.append(button)
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _restore_keyboard(user_id: int, view: dict, *, back: bool = False):
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
    if back:
        rows.append([_icon_button(mine_button_back(), f"fm:home:{int(user_id)}", style="primary")])
    else:
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
        await _edit_restore(
            call,
            screen_restore_done(view.get("label") or "серия"),
            _mine_keyboard(clicker, back=True),
        )
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


async def _edit_mine(call, text: str, markup) -> None:
    """Сначала гасим часики на кнопке, потом меняем это же сообщение."""
    try:
        await call.answer()
    except Exception:
        pass
    try:
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )
    except Exception as exc:
        if "not modified" in str(exc).lower():
            return
        try:
            await call.message.answer(
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=markup,
            )
        except Exception:
            pass


async def flame_mine_click(call) -> None:
    data = str(getattr(call, "data", "") or "")
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "fm":
        return
    action, owner = parts[1], parts[2]
    clicker = int(getattr(getattr(call, "from_user", None), "id", 0) or 0)
    if not owner.isdigit() or int(owner) != clicker:
        try:
            await call.answer(alert_stranger(), show_alert=True)
        except Exception:
            pass
        return
    if action == "close":
        try:
            await call.answer()
        except Exception:
            pass
        try:
            await call.message.delete()
        except Exception:
            pass
        return
    from main import db
    try:
        view = await _mine_view(
            db,
            clicker,
            with_ladder=action == "rewards",
            with_warm=action == "warm",
            with_progress=action in ("home", "", "next"),
        )
    except Exception as exc:
        print(f"[FLAME] mine click {clicker}: {exc}")
        view = None
    if view is None:
        await _edit_mine(call, screen_mine_fail(), None)
        return
    if not view["enabled"]:
        await _edit_mine(call, screen_mine_off(), _mine_keyboard(clicker, close_only=True))
        return
    if action in ("how", "rules"):
        await _edit_mine(call, view["how"], _mine_keyboard(clicker, back=True))
        return
    if action == "rewards":
        await _edit_mine(call, view["rewards_screen"], _mine_keyboard(clicker, back=True))
        return
    if action == "warm":
        await _edit_mine(call, view["warm_screen"] or view["how"], _mine_keyboard(clicker, back=True))
        return
    if action == "status":
        await _edit_mine(call, view["status_screen"], _mine_keyboard(clicker, back=True))
        return
    if action == "restore":
        restore = view["restore"]
        if restore.get("code") == "ready":
            markup = _restore_keyboard(clicker, restore, back=True)
        else:
            markup = _mine_keyboard(clicker, back=True)
        await _edit_mine(call, _restore_screen(restore), markup)
        return
    await _edit_mine(call, view["home"], _mine_keyboard(clicker, topics=view["topics"]))
