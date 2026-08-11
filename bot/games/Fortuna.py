# -*- coding: utf-8 -*-
"""
🎡 Рулетка 0..12 с Jericho, маскировкой, сериями и корректным demo/0demo.
"""
from main import *  # noqa: F401,F403
from bot.games.group_only import reject_if_private_game
from bot.funcs.tech_home_log import safe_send_tech_log

import asyncio
import random
import re
import time
import traceback
from contextlib import asynccontextmanager
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, getcontext
from typing import Dict, Optional, List, Union, Any, Tuple, AsyncIterator, Callable, Awaitable, TypeVar

T = TypeVar("T")

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

try:
    # aiogram 3.7+: TelegramRetryAfter (старого RetryAfter уже нет)
    from aiogram.exceptions import (
        TelegramAPIError,
        TelegramBadRequest,
        TelegramRetryAfter,
    )
    RetryAfter = TelegramRetryAfter  # noqa: N816
except Exception:
    try:
        from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, RetryAfter  # type: ignore
    except Exception:
        class TelegramAPIError(Exception):
            pass

        class TelegramBadRequest(TelegramAPIError):
            pass

        class RetryAfter(TelegramAPIError):
            def __init__(self, retry_after: float = 1.0):
                super().__init__("Too many requests")
                self.retry_after = retry_after

# Jericho
from main import jericho_check, welcome_back_gift, newbie_safety_net, force_repay_debt

# ===================== НАСТРОЙКИ =====================
getcontext().prec = 28

ZERO_STICKER_ID: Optional[str] = None
FORTUNA_DEBUG = True

# Маскировочные механики
DEMO_MASK_LOSS_PROB = 0.45
DEMO_STREAK_BREAK = 3
ZERO_MASK_WIN_PROB = 0.12
ZERO_STREAK_BREAK = 3

# Доп. контроль demo для ставок на одно число:
# даже в demo-режиме такая ставка не должна гарантированно выигрывать.
FORTUNA_DEMO_NUMBER_WIN_PROB_BASE = 0.34
FORTUNA_DEMO_NUMBER_WIN_PROB_MIN = 0.14
FORTUNA_DEMO_NUMBER_WIN_PROB_MAX = 0.55
FORTUNA_DEMO_NUMBER_WIN_STREAK_PENALTY = 0.06
FORTUNA_DEMO_NUMBER_LOSE_STREAK_BONUS = 0.03
FORTUNA_DEMO_NUMBER_STREAK_CAP = 3

# Профиль экономики выпадений (чем ниже коэффициент, тем "жестче" игра).
# Значения применяются как доля от естественного шанса победы по типу ставки.
FORTUNA_WIN_PROFILE = "hard"  # soft / normal / hard
FORTUNA_WIN_PROB_FACTORS = {
    "soft": {
        "number": 0.92,
        "color": 0.95,
        "parity": 0.95,
        "range": 0.93,
    },
    "normal": {
        "number": 0.82,
        "color": 0.88,
        "parity": 0.88,
        "range": 0.85,
    },
    "hard": {
        "number": 0.72,
        "color": 0.82,
        "parity": 0.82,
        "range": 0.78,
    },
}

# Сглаживание длинных луз-стрик: шанс слегка растет, но остается ниже естественного.
FORTUNA_LOSE_STREAK_SOFTEN_FROM = 5
FORTUNA_LOSE_STREAK_SOFTEN_STEP = 0.03
FORTUNA_LOSE_STREAK_SOFTEN_CAP_STEPS = 3
FORTUNA_MIN_NATURAL_SHARE = 0.52
FORTUNA_MAX_NATURAL_SHARE = 0.90

# ===================== ХРАНИЛИЩА / БЛОКИРОВКИ =====================
# ВАЖНО: asyncio.Lock нельзя класть в LazyGameStore/Redis.
# После pickle/unpickle лок «мертвый» или чужого event loop →
# партия зависает на `async with lock` и в чат ничего не уходит.
_message_locks: Dict[str, asyncio.Lock] = {}
_user_locks: Dict[int, asyncio.Lock] = {}
_processing_messages: Dict[str, float] = LazyGameStore("_processing_messages")
_processed_messages: Dict[str, float] = LazyGameStore("_processed_messages")
_settled_events: Dict[str, float] = LazyGameStore("_settled_events")
_settled_events_lock = asyncio.Lock()
_roulette_streaks: Dict[int, Dict[str, int]] = LazyGameStore("_roulette_streaks")

CLEANUP_AFTER_SECONDS = 60 * 10
_CLEANUP_TASK: Optional[asyncio.Task] = None

try:
    last_used_times
except NameError:
    last_used_times: Dict[int, Dict[int, float]] = LazyGameStore("last_used_times")

# ===================== DEBUG =====================
def _fdbg(tag: str, msg: str) -> None:
    if not FORTUNA_DEBUG:
        return
    try:
        print(f"[ROULETTE][{tag}] {msg}", flush=True)
    except Exception:
        pass

def _fdbg_err(tag: str, err: Exception) -> None:
    if not FORTUNA_DEBUG:
        return
    try:
        print(f"[ROULETTE][ERROR][{tag}] {err}", flush=True)
        print(traceback.format_exc(), flush=True)
    except Exception:
        pass

# ===================== СЕРИИ =====================
def _get_streaks(user_id: int) -> Dict[str, int]:
    streaks = _roulette_streaks.get(user_id)
    if streaks is None:
        streaks = {"win_streak": 0, "lose_streak": 0}
        _roulette_streaks[user_id] = streaks
    return streaks

def _update_streaks(user_id: int, is_win: bool, is_home: bool = False) -> None:
    streaks = _get_streaks(user_id)
    if is_home:
        streaks["win_streak"] = 0
        streaks["lose_streak"] = 0
    elif is_win:
        streaks["win_streak"] = streaks.get("win_streak", 0) + 1
        streaks["lose_streak"] = 0
    else:
        streaks["lose_streak"] = streaks.get("lose_streak", 0) + 1
        streaks["win_streak"] = 0
    _roulette_streaks[user_id] = streaks
    _fdbg("STREAKS", f"user={user_id} win={streaks['win_streak']} lose={streaks['lose_streak']}")

# ===================== УТИЛИТЫ =====================
async def _mark_user_game_activity(user_id: int, reason: str = "") -> None:
    try:
        await db.touch_balance_last_active(int(user_id), set_active_status=True)
        _fdbg("ACTIVITY", f"touch ok user_id={user_id} reason={reason}")
    except Exception as e:
        _fdbg("ACTIVITY", f"touch error user_id={user_id} reason={reason}: {e}")

def _msg_key(chat_id: int, message_id: int) -> str:
    """Ключ антидубля: message_id сам по себе пересекается между чатами."""
    return f"{int(chat_id)}:{int(message_id)}"

def _key_from_message(message: Message) -> str:
    return _msg_key(int(message.chat.id), int(message.message_id))

def _fresh_lock() -> asyncio.Lock:
    return asyncio.Lock()

def _get_message_lock(message: Message) -> asyncio.Lock:
    key = _key_from_message(message)
    lock = _message_locks.get(key)
    if lock is None or not isinstance(lock, asyncio.Lock):
        lock = _fresh_lock()
        _message_locks[key] = lock
        return lock
    try:
        # Lock из другого loop нельзя использовать — создаём новый.
        loop = asyncio.get_running_loop()
        lock_loop = getattr(lock, "_loop", None)
        if lock_loop is not None and lock_loop is not loop:
            lock = _fresh_lock()
            _message_locks[key] = lock
    except Exception:
        lock = _fresh_lock()
        _message_locks[key] = lock
    return lock

def _get_user_lock(uid: int) -> asyncio.Lock:
    key = int(uid)
    lock = _user_locks.get(key)
    if lock is None or not isinstance(lock, asyncio.Lock):
        lock = _fresh_lock()
        _user_locks[key] = lock
        return lock
    try:
        loop = asyncio.get_running_loop()
        lock_loop = getattr(lock, "_loop", None)
        if lock_loop is not None and lock_loop is not loop:
            lock = _fresh_lock()
            _user_locks[key] = lock
    except Exception:
        lock = _fresh_lock()
        _user_locks[key] = lock
    return lock

async def _acquire_lock_safe(
    lock: asyncio.Lock,
    *,
    key: Any,
    store: dict,
    timeout: float = 12.0,
    name: str = "lock",
) -> asyncio.Lock:
    """Берём лок с таймаутом; при зависании — новый лок, чтобы партия не молчала."""
    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
        return lock
    except asyncio.TimeoutError:
        print(f"[ROULETTE][LOCK] {name} timeout key={key!r} — recreate", flush=True)
        fresh = _fresh_lock()
        store[key] = fresh
        await asyncio.wait_for(fresh.acquire(), timeout=timeout)
        return fresh


@asynccontextmanager
async def _roulette_lock(
    store: dict,
    key: Any,
    *,
    name: str,
    timeout: float = 12.0,
) -> AsyncIterator[None]:
    lock = store.get(key)
    if not isinstance(lock, asyncio.Lock):
        lock = _fresh_lock()
        store[key] = lock
    held = await _acquire_lock_safe(lock, key=key, store=store, timeout=timeout, name=name)
    try:
        yield
    finally:
        try:
            held.release()
        except Exception:
            pass

def _event_key(chat_id: int, message_id: int) -> str:
    return f"roulette:{int(chat_id)}:{int(message_id)}"

async def _claim_settlement_once(event_key: str) -> bool:
    async with _settled_events_lock:
        if event_key in _settled_events:
            return False
        _settled_events[event_key] = time.time()
        return True

def _already_processed(message: Message) -> bool:
    return _key_from_message(message) in _processed_messages

def _mark_processed_message(message: Message) -> None:
    key = _key_from_message(message)
    _processed_messages[key] = time.time()
    _processing_messages.pop(key, None)

def _dec(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(0)

def _to_int_floor(x: Decimal) -> int:
    try:
        if x.is_nan():
            return 0
    except Exception:
        return 0
    try:
        return max(0, int(x.quantize(Decimal("1"), rounding=ROUND_DOWN)))
    except Exception:
        return 0

def _parse_bet_to_int(raw: str) -> int:
    s = (raw or "").strip().replace(" ", "").replace(",", ".")
    return _to_int_floor(_dec(s))

def fmt_int(n: Union[int, float, Decimal]) -> str:
    try:
        return "{:,.0f}".format(float(n)).replace(",", ".")
    except Exception:
        return str(n)

def _fmt_coef(x: Union[float, Decimal, int]) -> str:
    try:
        v = float(x)
        if v.is_integer():
            return f"{int(v)}x"
        return f"{v:.2f}x"
    except Exception:
        return f"{x}x"

def resolve_color(number: int) -> str:
    if int(number) == 0:
        return "зеро"
    if int(number) in [1, 3, 5, 8, 10, 12]:
        return "красное"
    return "черное"

def _number_emoji(number: int) -> str:
    try:
        num = int(number)
    except Exception:
        return "🖤"
    if num == 0:
        return "💚"
    return "❤️‍🔥" if resolve_color(num).startswith("крас") else "🖤"

def _normalize_choice_text(choice: str) -> str:
    s = str(choice or "").strip().lower()
    s = s.replace("ё", "е")
    s = " ".join(s.split())
    return s

def _canonical_roulette_choice(choice: str) -> str:
    s = _normalize_choice_text(choice)
    red_aliases = {"к", "кр", "крас", "красн", "красное", "красный", "red", "r"}
    black_aliases = {"ч", "чер", "черн", "черное", "черный", "black", "b"}
    even_aliases = {
        "п", "пар", "пары", "парное", "парные",
        "чет", "четн", "четное", "четный", "четные",
        "чёт", "чётн", "чётное", "чётный", "чётные",
        "even", "ev",
    }
    odd_aliases = {
        "н", "неч", "нечет", "нечетн", "нечетное", "нечетный", "нечетные",
        "нечёт", "нечётн", "нечётное", "нечётный", "нечётные",
        "непар", "непары", "непарное", "непарный", "непарные",
        "odd", "od",
    }
    if s in red_aliases:
        return "red"
    if s in black_aliases:
        return "black"
    if s in even_aliases:
        return "even"
    if s in odd_aliases:
        return "odd"
    return ""

def _spin_roulette_number() -> int:
    r = _dec(random.random())
    if r < FORTUNA_ZERO_CHANCE:
        num = 0
    else:
        num = random.randint(1, 12)
    _fdbg("SPIN", f"rand={r} zero_chance={FORTUNA_ZERO_CHANCE} -> {num}")
    return int(num)

def _clamp01(v: float) -> float:
    try:
        x = float(v)
    except Exception:
        return 0.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x

def _zero_chance_float() -> float:
    try:
        z = float(FORTUNA_ZERO_CHANCE)
    except Exception:
        z = 1.0 / 13.0
    return _clamp01(z)

def _natural_win_probability(parsed: dict) -> float:
    mode = str(parsed.get("mode") or "")
    zero_chance = _zero_chance_float()
    non_zero_chance = max(0.0, 1.0 - zero_chance)

    if mode == "number":
        try:
            selected = int(parsed.get("selected_number"))
        except Exception:
            return 0.0
        if selected == 0:
            return zero_chance
        return non_zero_chance / 12.0

    if mode in ("color", "parity"):
        return non_zero_chance * 0.5

    if mode == "range":
        try:
            start = int(parsed.get("start_num"))
            end = int(parsed.get("end_num"))
        except Exception:
            return 0.0
        left = max(1, start)
        right = min(12, end)
        width = max(0, right - left + 1)
        return non_zero_chance * (float(width) / 12.0)

    return 0.0

def _target_win_probability(parsed: dict, lose_streak: int = 0) -> float:
    mode = str(parsed.get("mode") or "")
    natural_prob = _natural_win_probability(parsed)
    if natural_prob <= 0:
        return 0.0

    profile = str(FORTUNA_WIN_PROFILE or "hard").strip().lower()
    profile_map = FORTUNA_WIN_PROB_FACTORS.get(profile) or FORTUNA_WIN_PROB_FACTORS["hard"]
    base_factor = float(profile_map.get(mode, profile_map.get("range", 0.78)))

    target_prob = natural_prob * base_factor

    if int(lose_streak or 0) >= FORTUNA_LOSE_STREAK_SOFTEN_FROM:
        extra_steps = int(lose_streak or 0) - int(FORTUNA_LOSE_STREAK_SOFTEN_FROM) + 1
        extra_steps = max(0, min(extra_steps, int(FORTUNA_LOSE_STREAK_SOFTEN_CAP_STEPS)))
        target_prob += natural_prob * (float(FORTUNA_LOSE_STREAK_SOFTEN_STEP) * extra_steps)

    min_prob = natural_prob * float(FORTUNA_MIN_NATURAL_SHARE)
    max_prob = natural_prob * float(FORTUNA_MAX_NATURAL_SHARE)
    if target_prob < min_prob:
        target_prob = min_prob
    if target_prob > max_prob:
        target_prob = max_prob
    return _clamp01(target_prob)

def _spin_roulette_number_for_bet(parsed: dict, lose_streak: int = 0) -> int:
    try:
        win_prob = _target_win_probability(parsed, lose_streak=lose_streak)
        roll = random.random()
        if roll < win_prob:
            num = _force_win_number(parsed)
            outcome = "win"
        else:
            num = _force_loss_number(parsed)
            outcome = "loss"

        _fdbg(
            "SPIN_CTRL",
            f"mode={parsed.get('mode')} lose_streak={lose_streak} "
            f"natural={_natural_win_probability(parsed):.4f} target={win_prob:.4f} "
            f"roll={roll:.4f} outcome={outcome} -> {num}",
        )
        return int(num)
    except Exception as e:
        _fdbg("SPIN_CTRL", f"fallback to base spin due error: {e}")
        return _spin_roulette_number()

def _force_loss_number(parsed: dict) -> int:
    mode = parsed["mode"]
    if mode == "number":
        num = int(parsed["selected_number"])
        return random.choice([x for x in range(0, 13) if x != num])
    if mode == "color":
        if parsed.get("choice_kind") == "red":
            return random.choice([2, 4, 6, 7, 9, 11, 0])
        else:
            return random.choice([1, 3, 5, 8, 10, 12, 0])
    if mode == "parity":
        if parsed.get("choice_kind") == "even":
            return random.choice([1, 3, 5, 7, 9, 11, 0])
        else:
            return random.choice([2, 4, 6, 8, 10, 12, 0])
    if mode == "range":
        start = int(parsed["start_num"])
        end = int(parsed["end_num"])
        pool = [x for x in range(1, 13) if not (start <= x <= end)] + [0]
        return random.choice(pool)
    return 0

def _force_win_number(parsed: dict) -> int:
    mode = parsed["mode"]
    if mode == "number":
        return int(parsed["selected_number"])
    if mode == "color":
        if parsed["choice_kind"] == "red":
            return random.choice([1, 3, 5, 8, 10, 12])
        else:
            return random.choice([2, 4, 6, 7, 9, 11])
    if mode == "parity":
        if parsed["choice_kind"] == "even":
            return random.choice([2, 4, 6, 8, 10, 12])
        else:
            return random.choice([1, 3, 5, 7, 9, 11])
    if mode == "range":
        start = int(parsed["start_num"])
        end = int(parsed["end_num"])
        return random.randint(start, end)
    return 1

async def _safe_add_xp(user_id: int) -> None:
    try:
        await db.add_xp_to_games(user_id)
    except Exception:
        pass

def _roulette_help_text() -> str:
    return (
        "💭 <b>Неверный формат команды!</b>\n"
        "<blockquote><i><b>Примеры:</b>\n"
        "<code>рулетка 10 красное</code>\n"
        "<code>рулетка 10 черное</code>\n"
        "<code>рулетка 10 чет</code>\n"
        "<code>рулетка 10 нечет</code>\n"
        "<code>рулетка 10 7</code>\n"
        "<code>рулетка 10 0</code>\n"
        "<code>рулетка 10 1 6</code>\n"
        "<code>рулетка 10 6 12</code></i></blockquote>"
    )

# ===================== БАЛАНСЫ =====================
async def _chat_get_balance(chat_id: int) -> int:
    try:
        return int(await db.get_chat_balance(bot1, chat_id) or 0)
    except TypeError:
        try:
            return int(await db.get_chat_balance(chat_id) or 0)
        except Exception:
            return 0
    except Exception:
        return 0

async def _chat_plus(chat_id: int, amount: int) -> None:
    amt = int(amount)
    if amt <= 0:
        return
    try:
        await db.update_chat_balance(bot1, chat_id, amt)
        return
    except TypeError:
        pass
    except Exception:
        pass
    try:
        await db.update_chat_balance(chat_id, amt)
        return
    except Exception:
        pass

async def _chat_minus(chat_id: int, amount: int) -> None:
    amt = int(amount)
    if amt <= 0:
        return
    try:
        await db.update_chat_balance_minus(chat_id, amt)
        return
    except TypeError:
        pass
    except Exception:
        pass
    try:
        await db.update_chat_balance_minus(bot1, chat_id, amt)
        return
    except Exception:
        pass
    try:
        await db.update_chat_balance(bot1, chat_id, -amt)
        return
    except Exception:
        pass

async def _user_plus(user_id: int, amount: int) -> bool:
    amt = int(amount)
    if amt <= 0:
        return True
    try:
        await db.update_user_balance(int(user_id), f"+{amt}")
        return True
    except Exception:
        pass
    try:
        cur = int(await db.get_user_balance(int(user_id)) or 0)
    except Exception:
        cur = 0
    try:
        await db.update_user_balance(int(user_id), max(0, cur + amt))
        return True
    except Exception:
        return False

async def _user_minus(user_id: int, amount: int) -> bool:
    amt = int(amount)
    if amt <= 0:
        return True
    try:
        new_val = await db.update_user_balance(int(user_id), f"-{amt}")
        if new_val is not None:
            return True
    except Exception:
        pass
    try:
        cur = int(await db.get_user_balance(int(user_id)) or 0)
    except Exception:
        cur = 0
    try:
        new_val = await db.update_user_balance(int(user_id), max(0, cur - amt))
        return new_val is not None
    except Exception:
        return False

async def _safe_get_balances(user_id: int, chat_id: int) -> Tuple[int, int]:
    try:
        balance = int(await db.get_user_balance(user_id) or 0)
    except Exception as e:
        balance = 0
        _fdbg("DB", f"Ошибка get_user_balance({user_id}): {e}")
    try:
        chat_balance = await _chat_get_balance(chat_id)
    except Exception as e:
        chat_balance = 0
        _fdbg("DB", f"Ошибка get_chat_balance({chat_id}): {e}")
    return balance, chat_balance

# ===================== СТИКЕРЫ =====================
# Принцип как в bot/funcs/ruletka.py:
#   sticker_id = stickers[number]
#   await bot1.send_sticker(chat_id, sticker_id)  (+ flood-retry)
# Пак: cutegamingbotroulet_by_TgEmojiBot (1..12)
FLOOD_STICKER_MAX_RETRIES = 4
FLOOD_SLEEP_BUFFER_SEC = 1.0

stickers: Dict[int, str] = {
    1: "CAACAgIAAx0Ef0PM_gABAqV7anisO2qBmenNqBab8Si-XX0M3YoAApVkAAIqJuhLEFcGzjTeNHk9BA",
    2: "CAACAgIAAx0Ef0PM_gABAqV9anisUA-kBhacCQam0R94bW6lcD4AAr1jAAJQd-BLkRm1LX2Stic9BA",
    3: "CAACAgIAAx0Ef0PM_gABAqV-anisUbwc8HNuGN_yjY3Cq2tC844AAimFAAJW6uBLpD2T13x1wLM9BA",
    4: "CAACAgIAAx0Ef0PM_gABAqPPanZN9d7bBhz4pQNBbAXEfL4IJrgAAolwAAJokuBLWliW8Fe8_c89BA",
    5: "CAACAgIAAx0Ef0PM_gABAqRIanejPsGc1URaP6rsnNYUqbTsxzgAAkZ6AAINgeFL5rEXfzqCeFE9BA",
    6: "CAACAgIAAx0EYB7ghAABKxgfanSzz7EIJUn8ttK_imdxM7e87iIAAsNjAAJAlulLIMuqoSRlNlQ9BA",
    7: "CAACAgIAAx0Ef0PM_gABAqWCanisVodlSQP8VJih6Ep-Ubh7B8IAAktxAAI3UeFL44eifCTuZ789BA",
    8: "CAACAgIAAxUAAWp4rF2-dtAZsfe-tNqOno-QXZ1CAAJGdwACyTvhS18_4MOuvurqPQQ",
    9: "CAACAgIAAx0Ef0PM_gABAqPGanZGGnKEO6da4H9AIMnCTmszCe0AAix3AAJGzeFLzRR3meCPt7o9BA",
    10: "CAACAgIAAx0Ef0PM_gABAqP1and8Zg-Lr6v6z09sIgd9rjd-tQ0AAqaCAAKJyuFLE4xwyz2qOr49BA",
    11: "CAACAgIAAx0Ef0PM_gABAqWFanisW5iMGfxOuXjB-EqMh_RFv-4AAspoAAJj2-BLudsPT85boew9BA",
    12: "CAACAgIAAx0Ef0PM_gABAqWGanisXI47L_ajq2Dne8Td6f27PxsAAoFoAALh8uhLgdFu5aeuQqs9BA",
}

LOSE_PHRASES: List[str] = [
    "Минус вайб.",
    "Не залетело.",
    "Ушел в минус.",
    "Не фартануло.",
    "Промах.",
    "Не прокнуло.",
]

WIN_PHRASES: List[str] = [
    "Залетело.",
    "Разнос.",
    "Чистый вин.",
    "Плюс вайб.",
    "Фартануло.",
    "Это занос.",
    "Сочный вин.",
    "Хорош.",
    "Зашло.",
]

def rand_win_phrase() -> str:
    return random.choice(WIN_PHRASES)

def rand_lose_phrase() -> str:
    return random.choice(LOSE_PHRASES)

@dp.callback_query(lambda c: c.data == "noop")
async def noop_callback(callback_query: CallbackQuery):
    try:
        await callback_query.answer()
    except Exception:
        pass

# ===================== UI РЕЗУЛЬТАТА =====================
def _build_result_kb(
    *,
    random_num: int,
    kind: str,      # "win" / "loss" / "home"
    amount: int = 0,
    coef: float = 0.0,
) -> InlineKeyboardMarkup:
    color = resolve_color(random_num)

    if int(random_num) == 0:
        text_result = "0 зеро"
        result_callback = "noop" if kind == "win" else "callbroulletanswerhome"
        result_icon = "5206569264147893211"
    else:
        text_result = f"{random_num} {color}"
        result_callback = "noop"
        result_icon = "5449505950283078474" if str(color).startswith("крас") else "5202199611665571551"

    btn_result = InlineKeyboardButton(
        text=text_result,
        callback_data=result_callback,
        style="default",
        icon_custom_emoji_id=result_icon,
    )

    if kind == "win":
        btn_status = InlineKeyboardButton(
            text=f"{rand_win_phrase()} +{fmt_int(amount)} кут",
            callback_data="noop",
            style="success",
            icon_custom_emoji_id="5193177023543023121",
        )
        btn_coef = InlineKeyboardButton(
            text=f"{_fmt_coef(coef)}",
            callback_data="callbroulletanswermultiplier",
        )
        inline_keyboard = [[btn_status], [btn_result], [btn_coef]]

    elif kind == "home":
        btn_status = InlineKeyboardButton(
            text="Выпал 0",
            callback_data="callbroulletanswerhome",
            style="primary",
            icon_custom_emoji_id="5192835092606655531",
        )
        btn_burn = InlineKeyboardButton(
            text="Ставка сгорела",
            callback_data="callbroulletanswerhome",
        )
        inline_keyboard = [[btn_status], [btn_result], [btn_burn]]

    else:
        btn_status = InlineKeyboardButton(
            text=f"{rand_lose_phrase()}",
            callback_data="noop",
            style="danger",
            icon_custom_emoji_id="5193209459136045172",
        )
        btn_coef = InlineKeyboardButton(
            text=f"{_fmt_coef(coef)}",
            callback_data="callbroulletanswermultiplier",
        )
        inline_keyboard = [[btn_status], [btn_result], [btn_coef]]

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def _is_flood_error(exc: Exception) -> bool:
    """Как в ruletka.py — flood / RetryAfter."""
    if isinstance(exc, RetryAfter):
        return True
    low = str(exc).lower()
    return (
        "flood control" in low
        or "too many requests" in low
        or "retry after" in low
        or "retry in" in low
    )


def _extract_retry_after(exc: Exception) -> int:
    ra = getattr(exc, "retry_after", None)
    if ra is not None:
        try:
            return max(1, int(float(ra)))
        except Exception:
            pass
    for pattern in (r"retry in (\d+)", r"retry after (\d+)"):
        m = re.search(pattern, str(exc), re.IGNORECASE)
        if m:
            return max(1, int(m.group(1)))
    return 5


async def _call_with_flood_retry(
    factory: Callable[[], Awaitable[T]],
    *,
    tag: str,
    max_tries: int = FLOOD_STICKER_MAX_RETRIES,
) -> Optional[T]:
    """Строго тот же принцип, что в bot/funcs/ruletka.py."""
    for attempt in range(1, max_tries + 1):
        try:
            return await factory()
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return None
            raise
        except Exception as e:
            if not _is_flood_error(e):
                raise
            wait_sec = _extract_retry_after(e)
            print(
                f"[ROULETTE][flood][{tag}] wait={wait_sec}s "
                f"attempt={attempt}/{max_tries}",
                flush=True,
            )
            if attempt >= max_tries:
                raise
            await asyncio.sleep(wait_sec + FLOOD_SLEEP_BUFFER_SEC)
    return None


async def _send_result_visual(
    message: Message,
    *,
    random_num: int,
    kind: str,
    amount: int = 0,
    coef: float = 0.0,
) -> None:
    """Результат рулетки: TG-стикер + кнопки (принцип ruletka.py)."""
    kb = _build_result_kb(
        random_num=int(random_num),
        kind=str(kind),
        amount=int(amount),
        coef=float(coef),
    )

    chat_id = int(message.chat.id)
    reply_to = int(message.message_id)
    num = int(random_num)

    # 0 зеро — отдельный стикер, если задан; иначе орёл с клавиатурой (как раньше).
    if num == 0:
        sticker_id = ZERO_STICKER_ID
    else:
        sticker_id = stickers.get(num)

    sticker_message = None
    if sticker_id:
        try:
            async def _send_sticker():
                return await bot1.send_sticker(
                    chat_id,
                    sticker_id,
                    reply_to_message_id=reply_to,
                )

            sticker_message = await _call_with_flood_retry(_send_sticker, tag="sticker")
        except Exception as e:
            # Якорь мог пропасть — один раз без reply (как flood-safe повтор).
            err = str(e).lower()
            if "reply" in err and "not found" in err:
                try:
                    async def _send_sticker_noreply():
                        return await bot1.send_sticker(chat_id, sticker_id)

                    sticker_message = await _call_with_flood_retry(
                        _send_sticker_noreply, tag="sticker_noreply",
                    )
                except Exception as e2:
                    print(f"[ROULETTE] send_sticker error: {e2}", flush=True)
            else:
                print(f"[ROULETTE] send_sticker error: {e}", flush=True)

    if sticker_message is not None:
        try:
            async def _edit_kb():
                return await bot1.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=sticker_message.message_id,
                    reply_markup=kb,
                )

            await _call_with_flood_retry(_edit_kb, tag="sticker_kb")
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                print(f"[ROULETTE] sticker kb error: {e}", flush=True)
        return

    # Крайний случай (нет file_id / 0 без ZERO_STICKER): сообщение с той же клавиатурой.
    try:
        async def _send_fallback():
            return await bot1.send_message(
                chat_id,
                "<tg-emoji emoji-id='5193099950354898372'>🦅</tg-emoji>",
                reply_to_message_id=reply_to,
                reply_markup=kb,
                parse_mode="HTML",
            )

        await _call_with_flood_retry(_send_fallback, tag="result_fallback")
    except Exception as e:
        print(f"[ROULETTE] send_message fallback error: {e}", flush=True)
        try:
            await bot1.send_message(chat_id, "🦅", reply_markup=kb)
        except Exception as e2:
            print(f"[ROULETTE] send_message plain error: {e2}", flush=True)

# ===================== CLEANUP =====================
async def _processed_cleanup_loop():
    while True:
        try:
            now = time.time()
            to_del_processed = []
            to_del_settled = []

            for mid, ts in list(_processed_messages.items()):
                if now - ts > CLEANUP_AFTER_SECONDS:
                    to_del_processed.append(mid)

            for key, ts in list(_settled_events.items()):
                if now - ts > CLEANUP_AFTER_SECONDS:
                    to_del_settled.append(key)

            for mid in to_del_processed:
                _processed_messages.pop(mid, None)
                _message_locks.pop(mid, None)

            for key in to_del_settled:
                _settled_events.pop(key, None)

            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception:
            _fdbg("CLEANUP", traceback.format_exc())
            await asyncio.sleep(5)

def ensure_cleanup_started():
    global _CLEANUP_TASK
    if _CLEANUP_TASK is None or _CLEANUP_TASK.done():
        _CLEANUP_TASK = asyncio.create_task(_processed_cleanup_loop())

# ===================== КУЛДАУН =====================
def _cooldown_left(chat_id: int, user_id: int) -> int:
    now = time.time()
    duration = delaysssssssssgamesonee.get(chat_id, 2)
    try:
        duration = float(duration)
    except Exception:
        duration = 2.0

    if duration <= 0:
        return 0

    chat_map = last_used_times.setdefault(chat_id, {})
    last_usage = float(chat_map.get(user_id, 0.0) or 0.0)
    left = duration - (now - last_usage)
    return int(left) if left > 0 else 0

def _cooldown_mark(chat_id: int, user_id: int) -> None:
    chat_map = last_used_times.setdefault(chat_id, {})
    chat_map[user_id] = time.time()

# ===================== ЛОГ ДОМОЙ =====================
async def _home_take_and_log_roulette_zero(*, user_id: int, loss: int) -> None:
    try:
        await _chat_plus(int(TECH_CHAT_ID), int(loss))

        try:
            receiver_name = await db.get_user_first_name(user_id)
        except Exception:
            receiver_name = "Игрок"

        try:
            receiver_username = await db.get_username_by_user_id(user_id)
        except Exception:
            receiver_username = None

        try:
            name_link1 = await create_user_link(user_id, receiver_name, receiver_username)
        except Exception:
            name_link1 = str(receiver_name or "Игрок")

        await db.add_home_amount(user_id=user_id, amount=loss)
        chat_balance = await db.get_chat_balance(bot1, -1003855337972)

        # HTML-эмодзи – единственный текст сообщения
        emoji_html = '<tg-emoji emoji-id="5226711870492126219">🎡</tg-emoji>'

        # Кнопка с именем: ссылка на профиль при username, иначе заглушка со ⭐️
        if receiver_username and isinstance(receiver_username, str):
            profile_url = f"https://t.me/{receiver_username.strip()}"
            row_name_btn = InlineKeyboardButton(
                text=receiver_name or "Игрок",
                url=profile_url
            )
        else:
            row_name_btn = InlineKeyboardButton(
                text=receiver_name or "Игрок",
                callback_data="pass",
                icon_custom_emoji_id="6028338546736107668"   # ⭐️
            )

        inline_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Рулетка",
                        callback_data="pass"
                    )
                ],
                [row_name_btn],
                [
                    InlineKeyboardButton(
                        text=f"+ {fmt_int(loss)} на чёрный рынок",
                        callback_data="pass"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{fmt_int(chat_balance)} кут доступно",
                        callback_data="pass"
                    )
                ]
            ]
        )

        # Лог в TECH_CHAT: chat not found не должен ронять партию.
        fallback_text = (
            f"🎡 Рулетка [Выпал 0]\n"
            f"+ {fmt_int(loss)} на чёрный рынок\n"
            f"<blockquote><b>{fmt_int(chat_balance)} кут доступно для выкупов</b></blockquote>"
        )
        await safe_send_tech_log(
            bot1,
            int(TECH_CHAT_ID),
            html=emoji_html,
            reply_markup=inline_kb,
            fallback_html=fallback_text,
            tag="FORTUNA][HOME_ZERO_LOG_SEND",
        )

    except Exception as e:
        _fdbg_err("HOME_ZERO_LOG", e)
# ===================== GC STATE =====================
async def _load_gc_state_for_user_fortuna(user_id: int) -> dict:
    has_assignment = False
    is_free = False
    current_two = 0
    target_amount = 0
    max_bet = 10**12

    try:
        gc_bet_limit = await db.gc_get_bet_limit_for_user(user_id)
    except Exception as e:
        gc_bet_limit = None
        _fdbg("GC_LIMIT", f"Ошибка gc_get_bet_limit_for_user({user_id}): {e}")

    if gc_bet_limit is not None:
        try:
            gc_bet_limit_int = int(gc_bet_limit)
            if gc_bet_limit_int > 0:
                max_bet = min(max_bet, gc_bet_limit_int)
        except Exception:
            pass

    try:
        assignment = await db.get_active_gc_assignment(user_id)
    except Exception as e:
        assignment = None
        _fdbg("GC_STATE", f"Ошибка get_active_gc_assignment({user_id}): {e}")

    if assignment and str(assignment.get("status") or "").lower() == "active":
        has_assignment = True

        try:
            is_free = bool(await db.gc_active_is_free(user_id))
        except Exception:
            is_free = False

        try:
            current_two_val = await db.gc_get_current_two_balance(user_id)
            current_two = int(current_two_val or 0)
        except Exception:
            current_two = 0

        try:
            target_amount = int(assignment.get("target_amount") or 0)
        except Exception:
            target_amount = 0

    return {
        "has_assignment": has_assignment,
        "is_free": is_free,
        "current_two": current_two,
        "target_amount": target_amount,
        "max_bet": max_bet,
    }

# ===================== ПАРСИНГ СТАВКИ =====================
def _parse_roulette_choice(parts: List[str]) -> dict:
    result = {
        "ok": False,
        "mode": None,
        "selected_number": None,
        "start_num": None,
        "end_num": None,
        "multiplier": None,
        "choice": None,
        "choice_kind": None,
        "error": None,
    }

    if len(parts) == 3:
        raw_choice = parts[2] or ""
        choice = _normalize_choice_text(raw_choice)
        canonical = _canonical_roulette_choice(raw_choice)

        result["choice"] = choice
        result["choice_kind"] = canonical

        if choice.isdigit():
            selected_number = int(choice)
            if not (0 <= selected_number <= 12):
                result["error"] = "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Выберите число от 0 до 12!</b>"
                return result

            result["ok"] = True
            result["mode"] = "number"
            result["selected_number"] = selected_number
            result["multiplier"] = 11.0
            return result

        if canonical in ("red", "black"):
            result["ok"] = True
            result["mode"] = "color"
            result["multiplier"] = 2.0
            return result

        if canonical in ("even", "odd"):
            result["ok"] = True
            result["mode"] = "parity"
            result["multiplier"] = 2.0
            return result

        result["error"] = _roulette_help_text()
        return result

    if len(parts) == 4:
        try:
            start_num = int(parts[2])
            end_num = int(parts[3])
        except Exception:
            result["error"] = "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Неверный формат диапазона.</b>"
            return result

        if start_num > end_num or start_num < 1 or end_num > 12 or (start_num == 1 and end_num == 12):
            result["error"] = "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Неверный формат диапазона.</b>"
            return result

        result["ok"] = True
        result["mode"] = "range"
        result["start_num"] = start_num
        result["end_num"] = end_num
        result["multiplier"] = float(calculate_multiplier(start_num, end_num))
        return result

    result["error"] = _roulette_help_text()
    return result

# ===================== FREE GAME (без изменений) =====================
async def _fortuna_free_game(
    message: Message,
    user_id: int,
    chat_id: int,
    bet_int: int,
    parts: List[str],
    gc_state: dict,
):
    ensure_cleanup_started()
    msg_key = _key_from_message(message)
    # гарантируем наличие локов в in-memory dict
    _get_message_lock(message)
    _get_user_lock(user_id)

    async with _roulette_lock(_message_locks, msg_key, name="msg"):
        if _already_processed(message):
            return

        async with _roulette_lock(_user_locks, int(user_id), name="user"):
            if _already_processed(message):
                return

            _processing_messages[msg_key] = time.time()

            try:
                left = _cooldown_left(chat_id, user_id)
                if left > 0:
                    try:
                        await bot1.send_message(
                            chat_id,
                            f"<tg-emoji emoji-id='5253709334835128381'>⌚️</tg-emoji> <b>Пожалуйста, подождите {left} сек</b>",
                            reply_to_message_id=message.message_id,
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                    _mark_processed_message(message)
                    return

                _cooldown_mark(chat_id, user_id)

                current_two = int(gc_state.get("current_two") or 0)
                target_amount = int(gc_state.get("target_amount") or 0)

                if bet_int > current_two:
                    progress = f"{current_two}/{target_amount}" if target_amount > 0 else f"{current_two}"
                    kb = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text=f"Баланс челленджа: {progress} кут", callback_data="noop")],
                            [InlineKeyboardButton(text="Недостаточно виртуальных кут", callback_data="noop")],
                        ]
                    )
                    try:
                        await bot1.send_message(chat_id, "😓", reply_to_message_id=message.message_id, reply_markup=kb)
                    except Exception:
                        pass
                    _mark_processed_message(message)
                    return

                parsed = _parse_roulette_choice(parts)
                if not parsed["ok"]:
                    try:
                        await bot1.send_message(chat_id, parsed["error"], reply_to_message_id=message.message_id, parse_mode="HTML")
                    except Exception:
                        pass
                    _mark_processed_message(message)
                    return

                streaks = _get_streaks(user_id)
                lose_streak = int(streaks.get("lose_streak", 0) or 0)
                random_num = _spin_roulette_number_for_bet(parsed, lose_streak=lose_streak)
                mult = float(parsed["multiplier"] or 0.0)

                # 0 и ставка на 0 => WIN
                if parsed["mode"] == "number" and int(parsed["selected_number"]) == 0 and random_num == 0:
                    profit = max(0, int(round(bet_int * mult - bet_int)))

                    if profit > 0:
                        try:
                            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit, outcome="+")
                        except Exception:
                            _fdbg("GC", f"[FREE][ZERO][WIN] error:\n{traceback.format_exc()}")

                    await _mark_user_game_activity(user_id, reason="free_zero_win")
                    await _safe_add_xp(user_id)
                    await _send_result_visual(message, random_num=0, kind="win", amount=profit, coef=mult)
                    _mark_processed_message(message)
                    return

                # 0 и НЕ ставка на 0 => HOME
                if random_num == 0:
                    try:
                        await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                    except Exception:
                        _fdbg("GC", f"[FREE][HOME] error:\n{traceback.format_exc()}")

                    await _mark_user_game_activity(user_id, reason="free_home_zero")
                    await _safe_add_xp(user_id)
                    await _send_result_visual(message, random_num=0, kind="home", amount=0, coef=0.0)
                    _mark_processed_message(message)
                    return

                if parsed["mode"] == "number":
                    selected_number = int(parsed["selected_number"])

                    if random_num == selected_number:
                        profit = max(0, int(round(bet_int * mult - bet_int)))
                        if profit > 0:
                            try:
                                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit, outcome="+")
                            except Exception:
                                _fdbg("GC", f"[FREE][NUMBER][WIN] error:\n{traceback.format_exc()}")
                        await _mark_user_game_activity(user_id, reason="free_number_win")
                        await _safe_add_xp(user_id)
                        await _send_result_visual(message, random_num=random_num, kind="win", amount=profit, coef=mult)
                    else:
                        try:
                            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                        except Exception:
                            _fdbg("GC", f"[FREE][NUMBER][LOSS] error:\n{traceback.format_exc()}")
                        await _mark_user_game_activity(user_id, reason="free_number_loss")
                        await _safe_add_xp(user_id)
                        await _send_result_visual(message, random_num=random_num, kind="loss", amount=0, coef=mult)

                    _mark_processed_message(message)
                    return

                if parsed["mode"] == "color":
                    rolled_is_red = resolve_color(random_num).startswith("крас")
                    choice_kind = str(parsed.get("choice_kind") or "")
                    user_red = (choice_kind == "red")
                    user_black = (choice_kind == "black")
                    is_win = (rolled_is_red and user_red) or ((not rolled_is_red) and user_black)

                    if is_win:
                        profit = max(0, int(round(bet_int * mult - bet_int)))
                        if profit > 0:
                            try:
                                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit, outcome="+")
                            except Exception:
                                _fdbg("GC", f"[FREE][COLOR][WIN] error:\n{traceback.format_exc()}")
                        await _mark_user_game_activity(user_id, reason="free_color_win")
                        await _safe_add_xp(user_id)
                        await _send_result_visual(message, random_num=random_num, kind="win", amount=profit, coef=mult)
                    else:
                        try:
                            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                        except Exception:
                            _fdbg("GC", f"[FREE][COLOR][LOSS] error:\n{traceback.format_exc()}")
                        await _mark_user_game_activity(user_id, reason="free_color_loss")
                        await _safe_add_xp(user_id)
                        await _send_result_visual(message, random_num=random_num, kind="loss", amount=0, coef=mult)

                    _mark_processed_message(message)
                    return

                if parsed["mode"] == "parity":
                    rolled_is_even = (random_num % 2 == 0)
                    choice_kind = str(parsed.get("choice_kind") or "")
                    user_even = (choice_kind == "even")
                    user_odd = (choice_kind == "odd")
                    is_win = (user_even and rolled_is_even) or (user_odd and not rolled_is_even)

                    if is_win:
                        profit = max(0, int(round(bet_int * mult - bet_int)))
                        if profit > 0:
                            try:
                                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit, outcome="+")
                            except Exception:
                                _fdbg("GC", f"[FREE][PARITY][WIN] error:\n{traceback.format_exc()}")
                        await _mark_user_game_activity(user_id, reason="free_parity_win")
                        await _safe_add_xp(user_id)
                        await _send_result_visual(message, random_num=random_num, kind="win", amount=profit, coef=mult)
                    else:
                        try:
                            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                        except Exception:
                            _fdbg("GC", f"[FREE][PARITY][LOSS] error:\n{traceback.format_exc()}")
                        await _mark_user_game_activity(user_id, reason="free_parity_loss")
                        await _safe_add_xp(user_id)
                        await _send_result_visual(message, random_num=random_num, kind="loss", amount=0, coef=mult)

                    _mark_processed_message(message)
                    return

                if parsed["mode"] == "range":
                    start_num = int(parsed["start_num"])
                    end_num = int(parsed["end_num"])

                    if start_num <= random_num <= end_num:
                        profit = max(0, int(round(bet_int * mult - bet_int)))
                        if profit > 0:
                            try:
                                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit, outcome="+")
                            except Exception:
                                _fdbg("GC", f"[FREE][RANGE][WIN] error:\n{traceback.format_exc()}")
                        await _mark_user_game_activity(user_id, reason="free_range_win")
                        await _safe_add_xp(user_id)
                        await _send_result_visual(message, random_num=random_num, kind="win", amount=profit, coef=mult)
                    else:
                        try:
                            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                        except Exception:
                            _fdbg("GC", f"[FREE][RANGE][LOSS] error:\n{traceback.format_exc()}")
                        await _mark_user_game_activity(user_id, reason="free_range_loss")
                        await _safe_add_xp(user_id)
                        await _send_result_visual(message, random_num=random_num, kind="loss", amount=0, coef=mult)

                    _mark_processed_message(message)
                    return

                _mark_processed_message(message)
                return

            except Exception:
                print(f"[ROULETTE][FREE] {traceback.format_exc()}", flush=True)
                try:
                    await bot1.send_message(
                        chat_id,
                        "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                        "<b>Не удалось завершить спин. Попробуйте ещё раз.</b>",
                        reply_to_message_id=message.message_id,
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
                _mark_processed_message(message)
                return

# ===================== PAID GAME (основной режим с Jericho) =====================
async def _fortuna_paid_game(
    message: Message,
    user_id: int,
    chat_id: int,
    bet_int: int,
    parts: List[str],
    has_assignment: bool,
    using_demo: bool = False,
    using_0demo: bool = False,
):
    ensure_cleanup_started()
    msg_key = _key_from_message(message)
    _get_message_lock(message)
    _get_user_lock(user_id)
    event_key = _event_key(chat_id, message.message_id)

    async with _roulette_lock(_message_locks, msg_key, name="msg"):
        if _already_processed(message):
            return

        async with _roulette_lock(_user_locks, int(user_id), name="user"):
            if _already_processed(message):
                return

            _processing_messages[msg_key] = time.time()

            try:
                left = _cooldown_left(chat_id, user_id)
                if left > 0:
                    try:
                        await bot1.send_message(
                            chat_id,
                            f"<tg-emoji emoji-id='5253709334835128381'>⌚️</tg-emoji> <b>Пожалуйста, подождите {left} сек</b>",
                            reply_to_message_id=message.message_id,
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                    _mark_processed_message(message)
                    return

                _cooldown_mark(chat_id, user_id)

                parsed = _parse_roulette_choice(parts)
                if not parsed["ok"]:
                    try:
                        await bot1.send_message(chat_id, parsed["error"], reply_to_message_id=message.message_id, parse_mode="HTML")
                    except Exception:
                        pass
                    _mark_processed_message(message)
                    return

                balance, chat_balance = await _safe_get_balances(user_id, chat_id)

                # --- Проверка баланса (только для обычного режима) ---
                if not using_demo and not using_0demo and bet_int > balance:
                    from bot.funcs.func import get_bot_username_by_token
                    try:
                        bot_username = await get_bot_username_by_token(TOKEN)
                    except Exception:
                        bot_username = "CuteGamingBot"

                    stars = _dec(bet_int) * _dec(donate_bet)
                    stars_q = stars.quantize(Decimal("1.000000"), rounding=ROUND_HALF_UP).normalize()
                    stars_amount = format(stars_q, "f")

                    pending_context[user_id] = {"stars_amount": stars_amount, "sent": False}

                    rows = [
                        [InlineKeyboardButton(text=f"💫 Купить {fmt_int(bet_int)} кут 💰", url=f"https://t.me/{bot_username}?start=insert_{stars_amount}_+")],
                        [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")],
                    ]
                    if has_assignment:
                        rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
                        rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])

                    try:
                        await bot1.send_message(
                            chat_id,
                            "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
                            reply_to_message_id=message.message_id,
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

                    async def _send_invoice_later():
                        try:
                            await asyncio.sleep(timeoutdonate)
                            ctx = pending_context.get(user_id)
                            if ctx and not ctx.get("sent"):
                                invoice_message = await send_invoice_to_user(message, stars_amount)
                                pending_context[user_id]["manual_message_id"] = getattr(invoice_message, "message_id", None)
                        except Exception:
                            _fdbg("DONATE", traceback.format_exc())

                    asyncio.create_task(_send_invoice_later())
                    _mark_processed_message(message)
                    return

                # --- Проверка баланса группы ---
                if bet_int > chat_balance:
                    text_err = "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В группе недостаточно средств для игры.</b>"
                    rows = []
                    if has_assignment:
                        rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
                        rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])
                    kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
                    try:
                        await bot1.send_message(chat_id, text_err, reply_to_message_id=message.message_id, reply_markup=kb, parse_mode="HTML")
                    except Exception:
                        pass
                    _mark_processed_message(message)
                    return

                # --- Проверка максимальной ставки ---
                try:
                    selected_phrase = random.choice(phrases12312)
                except Exception:
                    selected_phrase = None
                if not using_demo and not using_0demo and selected_phrase and bet_int > FORTUNA_MAXIMUM_BET_AMOUNT:
                    try:
                        await bot1.send_message(chat_id, f"<b>{selected_phrase}</b>", reply_to_message_id=message.message_id, parse_mode="HTML")
                    except Exception:
                        pass
                    _mark_processed_message(message)
                    return

                # --- Загружаем серии ---
                streaks = _get_streaks(user_id)
                win_streak = streaks.get("win_streak", 0)
                lose_streak = streaks.get("lose_streak", 0)

                # --- МАСКИРОВКА И РЕЗУЛЬТАТ ---
                if using_0demo:
                    # Определяем, сработает ли принудительный выигрыш (маскировка)
                    should_win = False
                    if lose_streak >= ZERO_STREAK_BREAK:
                        should_win = True
                        _fdbg("0DEMO_MASK", f"streak break: lose_streak={lose_streak} -> WIN")
                    elif random.random() < ZERO_MASK_WIN_PROB:
                        should_win = True
                        _fdbg("0DEMO_MASK", "random chance -> WIN")

                    if should_win:
                        # Маскировка – выигрыш, не списываем 0demo и не гасим долг
                        random_num = _force_win_number(parsed)
                        _fdbg("0DEMO_MASK", f"masked win -> {random_num}")
                        mult = float(parsed["multiplier"] or 0.0)
                        profit = int(round(bet_int * mult - bet_int))
                        if profit < 0: profit = 0
                        actual_profit = min(profit, int(chat_balance or 0))

                        # зачисляем выигрыш
                        if actual_profit > 0:
                            await _user_plus(user_id, actual_profit)
                            await _chat_minus(chat_id, actual_profit)
                            try:
                                await db.cutehistory_plus(user_id, float(actual_profit), "+ рулетка (0demo маскировка)")
                            except Exception:
                                pass
                            try:
                                await db.update_user_wins(user_id, 1, bot1, ref_coin)
                            except Exception:
                                pass
                        if has_assignment and actual_profit > 0:
                            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=actual_profit, outcome="+")
                        await _mark_user_game_activity(user_id, reason="0demo_masked_win")
                        await _safe_add_xp(user_id)
                        _update_streaks(user_id, is_win=True)

                        await _send_result_visual(message, random_num=random_num, kind="win", amount=actual_profit, coef=mult)
                        _mark_processed_message(message)
                        return

                    # Реальный проигрыш (0demo) – списываем 0demo, гасим долг
                    try:
                        await db.deduct_0demo_amount(user_id, bet_int)
                        _fdbg("0DEMO", f"deduct 0demo {bet_int}")
                    except Exception as e:
                        _fdbg("0DEMO", f"deduct 0demo error: {e}")

                    _fdbg("0DEMO_DEBT", f"calling force_repay_debt({user_id}, {bet_int})")
                    try:
                        await force_repay_debt(user_id, bet_int)
                    except Exception as e:
                        _fdbg_err("0DEMO_DEBT_FAILED", e)

                    random_num = _force_loss_number(parsed)
                    _fdbg("0DEMO", f"forced loss -> {random_num}")

                    # Обработка исхода
                    if random_num == 0:
                        # HOME
                        if not await _claim_settlement_once(event_key):
                            _mark_processed_message(message)
                            return
                        await _user_minus(user_id, bet_int)
                        if has_assignment:
                            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                        await _mark_user_game_activity(user_id, reason="home_0demo")
                        try:
                            await db.cutehistory_minus(user_id, float(bet_int), "- рулетка (0demo home)")
                        except Exception:
                            pass
                        try:
                            await db.update_user_loose(user_id, 1, bot1, ref_coin)
                            await db.update_game_last_activity(user_id)
                        except Exception:
                            pass
                        await _home_take_and_log_roulette_zero(user_id=user_id, loss=bet_int)
                        await _safe_add_xp(user_id)
                        _update_streaks(user_id, is_win=False, is_home=True)
                        await _send_result_visual(message, random_num=0, kind="home", amount=0, coef=0.0)
                    else:
                        # LOSS
                        if not await _claim_settlement_once(event_key):
                            _mark_processed_message(message)
                            return
                        await _user_minus(user_id, bet_int)
                        await _chat_plus(chat_id, bet_int)
                        if has_assignment:
                            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                        await _mark_user_game_activity(user_id, reason="loss_0demo")
                        try:
                            await db.cutehistory_minus(user_id, float(bet_int), "- рулетка (0demo)")
                        except Exception:
                            pass
                        try:
                            await db.update_user_loose(user_id, 1, bot1, ref_coin)
                            await db.update_game_last_activity(user_id)
                        except Exception:
                            pass
                        await _safe_add_xp(user_id)
                        _update_streaks(user_id, is_win=False)
                        mult = float(parsed["multiplier"] or 0.0)
                        await _send_result_visual(message, random_num=random_num, kind="loss", amount=0, coef=mult)

                    _mark_processed_message(message)
                    return

                if using_demo:
                    # Определяем, будет ли принудительный проигрыш (маскировка)
                    should_lose = False
                    if win_streak >= DEMO_STREAK_BREAK:
                        should_lose = True
                        _fdbg("DEMO_MASK", f"streak break: win_streak={win_streak} -> LOSS/HOME")
                    elif random.random() < DEMO_MASK_LOSS_PROB:
                        should_lose = True
                        _fdbg("DEMO_MASK", "random chance -> LOSS/HOME")

                    # Для режима "ставка на число" в demo добавляем отдельный вероятностный фильтр:
                    # win остаются чаще, чем в обычной игре, но уже не 100% каждый раунд.
                    if not should_lose and str(parsed.get("mode") or "") == "number":
                        ws = max(0, min(int(win_streak or 0), int(FORTUNA_DEMO_NUMBER_STREAK_CAP)))
                        ls = max(0, min(int(lose_streak or 0), int(FORTUNA_DEMO_NUMBER_STREAK_CAP)))
                        number_demo_win_prob = float(FORTUNA_DEMO_NUMBER_WIN_PROB_BASE)
                        number_demo_win_prob -= ws * float(FORTUNA_DEMO_NUMBER_WIN_STREAK_PENALTY)
                        number_demo_win_prob += ls * float(FORTUNA_DEMO_NUMBER_LOSE_STREAK_BONUS)
                        number_demo_win_prob = _clamp01(number_demo_win_prob)
                        number_demo_win_prob = max(
                            float(FORTUNA_DEMO_NUMBER_WIN_PROB_MIN),
                            min(float(FORTUNA_DEMO_NUMBER_WIN_PROB_MAX), number_demo_win_prob),
                        )

                        number_roll = random.random()
                        if number_roll >= number_demo_win_prob:
                            should_lose = True
                            _fdbg(
                                "DEMO_NUMBER",
                                f"roll={number_roll:.4f} >= prob={number_demo_win_prob:.4f} -> LOSS",
                            )
                        else:
                            _fdbg(
                                "DEMO_NUMBER",
                                f"roll={number_roll:.4f} < prob={number_demo_win_prob:.4f} -> WIN",
                            )

                    if should_lose:
                        # Маскировочный проигрыш, demo не списываем
                        # Генерируем гарантированно проигрышное число (может быть 0)
                        random_num = _force_loss_number(parsed)
                        _fdbg("DEMO_MASK", f"masked loss -> {random_num}")
                        mult = float(parsed["multiplier"] or 0.0)

                        if random_num == 0:
                            # HOME
                            if not await _claim_settlement_once(event_key):
                                _mark_processed_message(message)
                                return
                            if has_assignment:
                                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                            await _user_minus(user_id, bet_int)
                            await _mark_user_game_activity(user_id, reason="demo_masked_home")
                            try:
                                await db.cutehistory_minus(user_id, float(bet_int), "- рулетка (demo маскировка home)")
                            except Exception:
                                pass
                            try:
                                await db.update_user_loose(user_id, 1, bot1, ref_coin)
                                await db.update_game_last_activity(user_id)
                            except Exception:
                                pass
                            await _home_take_and_log_roulette_zero(user_id=user_id, loss=bet_int)
                            await _safe_add_xp(user_id)
                            _update_streaks(user_id, is_win=False, is_home=True)
                            await _send_result_visual(message, random_num=0, kind="home", amount=0, coef=0.0)
                        else:
                            # LOSS
                            if not await _claim_settlement_once(event_key):
                                _mark_processed_message(message)
                                return
                            if has_assignment:
                                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                            await _user_minus(user_id, bet_int)
                            await _chat_plus(chat_id, bet_int)
                            await _mark_user_game_activity(user_id, reason="demo_masked_loss")
                            try:
                                await db.cutehistory_minus(user_id, float(bet_int), "- рулетка (demo маскировка)")
                            except Exception:
                                pass
                            try:
                                await db.update_user_loose(user_id, 1, bot1, ref_coin)
                                await db.update_game_last_activity(user_id)
                            except Exception:
                                pass
                            await _safe_add_xp(user_id)
                            _update_streaks(user_id, is_win=False)
                            await _send_result_visual(message, random_num=random_num, kind="loss", amount=0, coef=mult)

                        _mark_processed_message(message)
                        return

                    # Обычный выигрыш demo – списываем demo
                    try:
                        await db.deduct_demo_amount(user_id, bet_int)
                        _fdbg("DEMO", f"deduct demo {bet_int}")
                    except Exception as e:
                        _fdbg("DEMO", f"deduct demo error: {e}")

                    random_num = _force_win_number(parsed)
                    mult = float(parsed["multiplier"] or 0.0)
                    profit = int(round(bet_int * mult - bet_int))
                    if profit < 0: profit = 0
                    actual_profit = min(profit, int(chat_balance or 0))

                    if not await _claim_settlement_once(event_key):
                        _mark_processed_message(message)
                        return
                    if actual_profit > 0:
                        await _user_plus(user_id, actual_profit)
                        await _chat_minus(chat_id, actual_profit)
                        try:
                            await db.cutehistory_plus(user_id, float(actual_profit), "+ рулетка")
                        except Exception:
                            pass
                        try:
                            await db.update_user_wins(user_id, 1, bot1, ref_coin)
                        except Exception:
                            pass
                    if has_assignment and actual_profit > 0:
                        await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=actual_profit, outcome="+")
                    await _mark_user_game_activity(user_id, reason="demo_win")
                    await _safe_add_xp(user_id)
                    _update_streaks(user_id, is_win=True)

                    await _send_result_visual(message, random_num=random_num, kind="win", amount=actual_profit, coef=mult)
                    _mark_processed_message(message)
                    return

                # ========== ОБЫЧНЫЙ РЕЖИМ (без demo/0demo) ==========
                random_num = _spin_roulette_number_for_bet(parsed, lose_streak=lose_streak)
                mult = float(parsed["multiplier"] or 0.0)

                # вспомогательные функции (из оригинального кода)
                async def apply_home_zero():
                    if not await _claim_settlement_once(event_key):
                        return
                    _fdbg("HOME", f"user={user_id} chat={chat_id} bet={bet_int}")
                    if has_assignment:
                        await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                    await _user_minus(user_id, bet_int)
                    await _mark_user_game_activity(user_id, reason="home_zero")
                    try:
                        await db.cutehistory_minus(user_id, float(bet_int), "- рулетка (выпал 0)")
                    except Exception:
                        pass
                    try:
                        await db.update_user_loose(user_id, 1, bot1, ref_coin)
                        await db.update_game_last_activity(user_id)
                    except Exception:
                        pass
                    await _home_take_and_log_roulette_zero(user_id=user_id, loss=bet_int)
                    await _safe_add_xp(user_id)
                    _update_streaks(user_id, is_win=False, is_home=True)
                    await _send_result_visual(message, random_num=0, kind="home", amount=0, coef=0.0)

                async def apply_win(random_num_value: int, multiplier: float, gc_tag: str):
                    if not await _claim_settlement_once(event_key):
                        return
                    _, current_chat_balance = await _safe_get_balances(user_id, chat_id)
                    total_win = int(round(bet_int * multiplier))
                    profit = max(0, total_win - bet_int)
                    actual_profit = min(profit, int(current_chat_balance or 0))
                    if actual_profit < 0:
                        actual_profit = 0
                    if actual_profit > 0:
                        await _user_plus(user_id, actual_profit)
                        await _mark_user_game_activity(user_id, reason=f"win_{gc_tag.lower()}")
                        await _chat_minus(chat_id, actual_profit)
                        try:
                            await db.cutehistory_plus(user_id, float(actual_profit), "+ рулетка")
                        except Exception:
                            pass
                        try:
                            await db.update_user_wins(user_id, 1, bot1, ref_coin)
                        except Exception:
                            pass
                    else:
                        await _mark_user_game_activity(user_id, reason=f"win_{gc_tag.lower()}_zero_profit")
                    if has_assignment and actual_profit > 0:
                        await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=actual_profit, outcome="+")
                    await _safe_add_xp(user_id)
                    _update_streaks(user_id, is_win=True)
                    await _send_result_visual(message, random_num=random_num_value, kind="win", amount=actual_profit, coef=multiplier)

                async def apply_loss(random_num_value: int, multiplier_for_view: float, gc_tag: str):
                    if not await _claim_settlement_once(event_key):
                        return
                    await _user_minus(user_id, bet_int)
                    await _mark_user_game_activity(user_id, reason=f"loss_{gc_tag.lower()}")
                    await _chat_plus(chat_id, bet_int)
                    try:
                        await db.cutehistory_minus(user_id, float(bet_int), "- рулетка")
                    except Exception:
                        pass
                    try:
                        await db.update_user_loose(user_id, 1, bot1, ref_coin)
                        await db.update_game_last_activity(user_id)
                    except Exception:
                        pass
                    if has_assignment:
                        await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                    await _safe_add_xp(user_id)
                    _update_streaks(user_id, is_win=False)
                    await _send_result_visual(message, random_num=random_num_value, kind="loss", amount=0, coef=multiplier_for_view)

                # разбор режимов ставки
                if parsed["mode"] == "number" and int(parsed["selected_number"]) == 0 and random_num == 0:
                    await apply_win(0, mult, "ZERO_NUMBER")
                    _mark_processed_message(message)
                    return

                if random_num == 0:
                    await apply_home_zero()
                    _mark_processed_message(message)
                    return

                if parsed["mode"] == "number":
                    selected_number = int(parsed["selected_number"])
                    if random_num == selected_number:
                        await apply_win(random_num, mult, "NUMBER")
                    else:
                        await apply_loss(random_num, mult, "NUMBER")
                    _mark_processed_message(message)
                    return

                if parsed["mode"] == "color":
                    rolled_is_red = resolve_color(random_num).startswith("крас")
                    choice_kind = str(parsed.get("choice_kind") or "")
                    user_red = (choice_kind == "red")
                    user_black = (choice_kind == "black")
                    if (rolled_is_red and user_red) or ((not rolled_is_red) and user_black):
                        await apply_win(random_num, mult, "COLOR")
                    else:
                        await apply_loss(random_num, mult, "COLOR")
                    _mark_processed_message(message)
                    return

                if parsed["mode"] == "parity":
                    rolled_is_even = (random_num % 2 == 0)
                    choice_kind = str(parsed.get("choice_kind") or "")
                    user_even = (choice_kind == "even")
                    user_odd = (choice_kind == "odd")
                    if (user_even and rolled_is_even) or (user_odd and not rolled_is_even):
                        await apply_win(random_num, mult, "PARITY")
                    else:
                        await apply_loss(random_num, mult, "PARITY")
                    _mark_processed_message(message)
                    return

                if parsed["mode"] == "range":
                    start_num = int(parsed["start_num"])
                    end_num = int(parsed["end_num"])
                    if start_num <= random_num <= end_num:
                        await apply_win(random_num, mult, "RANGE")
                    else:
                        await apply_loss(random_num, mult, "RANGE")
                    _mark_processed_message(message)
                    return

                _mark_processed_message(message)

            except Exception:
                print(f"[ROULETTE][PAID] {traceback.format_exc()}", flush=True)
                try:
                    await bot1.send_message(
                        chat_id,
                        "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                        "<b>Не удалось завершить спин. Попробуйте ещё раз.</b>",
                        reply_to_message_id=message.message_id,
                        parse_mode="HTML",
                    )
                except Exception:
                    try:
                        await bot1.send_message(
                            chat_id,
                            "☁️ <b>Не удалось завершить спин. Попробуйте ещё раз.</b>",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                _mark_processed_message(message)

# ===================== MAIN HANDLER =====================
@dp.message(lambda message: bool(message.text) and message.text.split()[0].lower() in ("рул", "рулетка"))
async def Fortuna(message: Message):
    ensure_cleanup_started()

    try:
        if _already_processed(message):
            return

        if await reject_if_private_game(message):
            return

        parts = (message.text or "").strip().split()

        if len(parts) <= 2:
            try:
                await bot1.send_message(
                    message.chat.id,
                    _roulette_help_text(),
                    reply_to_message_id=message.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass
            _mark_processed_message(message)
            return

        bet_int = _parse_bet_to_int(parts[1])

        if bet_int <= 0:
            try:
                await bot1.send_message(
                    message.chat.id,
                    "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Неверный формат ставки!</b>",
                    reply_to_message_id=message.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass
            _mark_processed_message(message)
            return

        if bet_int < FORTUNA_MIN_BET:
            try:
                await bot1.send_message(
                    message.chat.id,
                    f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Ставка должна быть больше {FORTUNA_MIN_BET} кут</b>",
                    reply_to_message_id=message.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass
            _mark_processed_message(message)
            return

        if bet_int > FORTUNA_MAXIMUM_BET_AMOUNT:
            try:
                await bot1.send_message(
                    message.chat.id,
                    f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Максимальная сумма ставки - {fmt_int(FORTUNA_MAXIMUM_BET_AMOUNT)} кут.</b>",
                    reply_to_message_id=message.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass
            _mark_processed_message(message)
            return

        user_id = int(message.from_user.id)
        chat_id = int(message.chat.id)

        _processing_messages[_key_from_message(message)] = time.time()
        _fdbg("START", f"user={user_id} chat={chat_id} bet={bet_int} text={message.text!r}")

        # Инициализация новичка и welcome_back_gift
        try:
            if await db.get_newbie_expires_at(user_id) is None:
                from datetime import datetime, timedelta, timezone
                expires = datetime.now(timezone.utc) + timedelta(hours=random.uniform(0.5, 24.0))
                await db.set_newbie_expires_at(user_id, expires)
                _fdbg("NEWBIE", f"newbie expires set {expires}")
        except Exception as e:
            _fdbg("NEWBIE", f"error {e}")
        await welcome_back_gift(user_id)

        gc_state = await _load_gc_state_for_user_fortuna(user_id)
        has_assignment = bool(gc_state["has_assignment"])
        is_free = bool(gc_state["is_free"])
        max_bet_gc = int(gc_state["max_bet"] or (10**12))

        if bet_int > max_bet_gc:
            try:
                await bot1.send_message(
                    chat_id,
                    f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Максимальная ставка для этой игры: {fmt_int(max_bet_gc)} кут.</b>",
                    reply_to_message_id=message.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass
            _mark_processed_message(message)
            return

        # ---------- DEMO / 0DEMO с Jericho ----------
        using_demo = False
        using_0demo = False
        if not has_assignment:
            try:
                demo_balance = int(await db.get_user_demo(user_id) or 0)
                zero_demo_balance = int(await db.get_user_0demo(user_id) or 0)
            except Exception as e:
                _fdbg("DEMO/0DEMO", f"error: {e}")
                demo_balance = 0
                zero_demo_balance = 0

            _fdbg("BONUS", f"demo={demo_balance} 0demo={zero_demo_balance} bet={bet_int}")

            decision = await jericho_check(user_id, bet_int, game_name="рулетка")
            jericho_action = decision.get("action", "normal")
            _fdbg("JERICHO", f"action={jericho_action} reason={decision.get('reason','')}")

            demo_enough = demo_balance >= bet_int
            zero_enough = zero_demo_balance >= bet_int

            if demo_enough and zero_enough:
                if demo_balance > zero_demo_balance:
                    using_demo = True
                elif zero_demo_balance > demo_balance:
                    using_0demo = True
                else:
                    using_demo = True
            elif demo_enough:
                using_demo = True
            elif zero_enough:
                using_0demo = True

            win_actions = ("force_win", "aggressive", "martingale", "safe")
            loss_actions = ("force_loss", "near_miss")

            if jericho_action in win_actions:
                if demo_enough:
                    using_demo = True
                    using_0demo = False
            elif jericho_action in loss_actions:
                if zero_enough:
                    using_0demo = True
                    using_demo = False

            _fdbg("MODE", f"final: demo={using_demo} 0demo={using_0demo}")

        if has_assignment and is_free:
            print(f"[ROULETTE][ENTER] free user={user_id} chat={chat_id} bet={bet_int}", flush=True)
            await _fortuna_free_game(message, user_id, chat_id, bet_int, parts, gc_state)
            return

        print(
            f"[ROULETTE][ENTER] paid user={user_id} chat={chat_id} bet={bet_int} "
            f"demo={using_demo} 0demo={using_0demo}",
            flush=True,
        )
        await _fortuna_paid_game(
            message, user_id, chat_id, bet_int, parts,
            has_assignment,
            using_demo=using_demo,
            using_0demo=using_0demo,
        )

    except Exception:
        # Всегда в лог — иначе онбординг «молчит» при падении партии.
        print(f"[ROULETTE][MAIN] {traceback.format_exc()}", flush=True)
        try:
            await bot1.send_message(
                int(message.chat.id),
                "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
                "<b>Не удалось завершить спин. Попробуйте ещё раз.</b>",
                reply_to_message_id=getattr(message, "message_id", None),
                parse_mode="HTML",
            )
        except Exception:
            try:
                await bot1.send_message(
                    int(message.chat.id),
                    "☁️ <b>Не удалось завершить спин. Попробуйте ещё раз.</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        try:
            _mark_processed_message(message)
        except Exception:
            pass

# ===================== CALLBACKS =====================
@dp.callback_query(lambda c: c.data.startswith("callbroulletanswermultiplier"))
async def fortuna_multiplier_info(callback_query: CallbackQuery):
    try:
        await callback_query.answer(
            "🎩 Коэффициент показывает размер выплаты при выигрыше.\n\n"
            "📌 Пример:\n"
            "Ставка: 100\n"
            "Коэффициент: 11.0\n"
            "Выплата = 100 × 11.0 = 1100\n\n"
            "🎉 Чистая прибыль составит 1000 кут\n\n"
            "❗ Если игрок поставил именно на 0 и выпал 0 - это выигрыш.\n"
            "❗ Если 0 выпал при любой другой ставке - ставка сгорает.",
            show_alert=True,
        )
    except Exception:
        pass

@dp.callback_query(lambda c: c.data == "callbroulletanswerhome")
async def fortuna_home_info(callback_query: CallbackQuery):
    try:
        await callback_query.answer(
            "🏠 Выпал 0.\n"
            "Если игрок не ставил именно на 0, это специальный исход.\n"
            "В таком случае ставка не идёт в баланс группы, а сгорает.",
            show_alert=True,
        )
    except Exception:
        pass