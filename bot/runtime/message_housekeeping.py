"""
Фоновое обслуживание БД — не блокирует ответы пользователю.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Set
from bot.funcs.bingo import LazyGameStore
HOUSEKEEPING_INTERVAL_SEC = 300.0
_PER_USER_LIGHT_INTERVAL_SEC = 60.0
_BALANCE_SYNC_INTERVAL_SEC = 120.0

_housekeeping_last_run = 0.0
_housekeeping_lock = asyncio.Lock()
_housekeeping_worker_started = False
_user_light_last: Dict[int, float] = LazyGameStore("_user_light_last")
_balance_sync_last: Dict[int, float] = LazyGameStore("_balance_sync_last")

# Примечание: учёт сообщений (буферы, накопление, сброс в БД и фоновый цикл)
# полностью вынесен в класс Database (bot/db_create/db.py):
#   db.record_message(user_id, chat_id)          — мгновенный +1 в памяти;
#   db.flush_message_counters()                  — пакетная запись в БД;
#   db.start_message_counter_flush_loop()        — фоновый цикл сброса.
# Здесь мы только вызываем db.record_message() на каждое сообщение.


def _norm_text(text: Optional[str]) -> str:
    return " ".join((text or "").split()).lower()


OWN_PROFILE_COMMANDS = frozenset({
    "профиль мой", "мой профиль", "🎩 профиль‍", "🎩 профиль",
    "профиль", "проф", "кто я", "ктоя", "/profile@cutegamingbot",
    "/profile", "profile", "я кто?", "я кто",
})

WHO_ARE_YOU_COMMANDS = frozenset({
    "кто ты", "ктоты", "кто ты такая", "кто ты такой",
})

PROFILE_COMMANDS = OWN_PROFILE_COMMANDS | WHO_ARE_YOU_COMMANDS


def is_own_profile_command(text: Optional[str]) -> bool:
    return _norm_text(text) in OWN_PROFILE_COMMANDS


def is_who_are_you_command(text: Optional[str]) -> bool:
    return _norm_text(text) in WHO_ARE_YOU_COMMANDS


def is_profile_command(text: Optional[str]) -> bool:
    return is_own_profile_command(text) or is_who_are_you_command(text)


async def run_global_housekeeping(db) -> None:
    global _housekeeping_last_run
    now = time.time()
    if now - _housekeeping_last_run < HOUSEKEEPING_INTERVAL_SEC:
        return
    async with _housekeeping_lock:
        if now - _housekeeping_last_run < HOUSEKEEPING_INTERVAL_SEC:
            return
        _housekeeping_last_run = time.time()
    try:
        await db.remove_expired_refout()
        await db.check_and_remove_expired_bonuses()
        await db.check_and_remove_expired_historygames()
        await db.delete_unfinished_marriages()
        await db.check_and_remove_expired_give_times()
    except Exception as e:
        print(f"[HOUSEKEEPING][WARN] global: {type(e).__name__}: {e}")


def start_global_housekeeping_loop(db) -> None:
    """Один фоновый цикл вместо create_task на каждое сообщение."""
    global _housekeeping_worker_started
    if _housekeeping_worker_started:
        return
    _housekeeping_worker_started = True

    async def _loop() -> None:
        while True:
            try:
                await run_global_housekeeping(db)
            except Exception as e:
                print(f"[HOUSEKEEPING][WARN] loop: {type(e).__name__}: {e}")
            await asyncio.sleep(HOUSEKEEPING_INTERVAL_SEC)

    asyncio.create_task(_loop())


async def _light_user_chat_touch(db, message: Any, start_balance: int, bot) -> None:
    from main import user_cache_balance, vgs_safe_add_or_update

    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)
    now = time.time()
    last = _user_light_last.get(user_id, 0.0)
    if now - last < _PER_USER_LIGHT_INTERVAL_SEC:
        return
    _user_light_last[user_id] = now

    try:
        await vgs_safe_add_or_update(message, db, start_balance, bot=bot)
        await db.update_or_insert_chatall(chat_id, user_id)
        await db.jackchat_mark_activity(chat_id)

        bal_last = _balance_sync_last.get(user_id, 0.0)
        if now - bal_last >= _BALANCE_SYNC_INTERVAL_SEC:
            if user_id not in user_cache_balance:
                await db.sync_balance_cache_from_db(user_id, debug=False)
                _balance_sync_last[user_id] = now
    except Exception as e:
        print(f"[HOUSEKEEPING][WARN] light touch: {type(e).__name__}: {e}")


def _message_word_count(message: Any) -> int:
    """Число слов в тексте/подписи сообщения (по пробелам)."""
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    return len(text.split())


def _min_words_for_count() -> int:
    """Минимум слов, чтобы сообщение засчиталось (из config, дефолт 2)."""
    try:
        from bot.config.config import MESSAGE_MIN_WORDS
        return int(MESSAGE_MIN_WORDS)
    except Exception:
        return 2


def schedule_message_housekeeping(db, message: Any, *, start_balance: int, bot) -> None:
    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)

    # Засчитываем только «содержательные» сообщения — от MESSAGE_MIN_WORDS слов.
    # Короткие односложные («привет») в статистику не идут.
    if _message_word_count(message) >= _min_words_for_count():
        db.record_message(user_id, chat_id)

    asyncio.create_task(_light_user_chat_touch(db, message, start_balance, bot))
