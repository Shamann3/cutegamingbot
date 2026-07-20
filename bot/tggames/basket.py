# -*- coding: utf-8 -*-
"""
🏀 Баскетбол (баскет/баскетбол/баскетболл/баскетбал) (ставка)

✅ Три режима: обычный, demo, 0demo.
✅ Интеграция с Jericho (агрессивные ставки, долги, near miss)
✅ Маскировка: demo → подмена выигрыша на проигрыш при сериях побед (demo не списывается)
✅ Маскировка: 0demo → подмена проигрыша на выигрыш при сериях проигрышей (0demo не списывается, долг не гасится)
✅ Сохранение серий побед/проигрышей между играми
✅ Долг гасится только при реальном проигрыше в 0demo (не при маскировке)
✅ После броска всегда показывается результат (текст + кнопка)
✅ Задержка 4.9 секунды во всех режимах (dice или кастомные эмодзи)
"""

from main import *  # noqa: F401,F403

import asyncio
import random
import time
import traceback
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, getcontext
from typing import Dict, Any

from aiogram import F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from bot.funcs.func import get_bot_username_by_token

# Jericho
from main import jericho_check, welcome_back_gift, newbie_safety_net, force_repay_debt

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================
def _save_safe(obj):
    try:
        if hasattr(obj, "save"):
            obj.save()
    except Exception:
        pass


def get_random_eagle_emoji_id() -> str:
    return "5204467307153234577"


# ===================== НАСТРОЙКИ =====================
getcontext().prec = 28

last_basket_time: Dict[int, Dict[int, float]] = LazyGameStore("last_basket_time")
_basket_streaks: Dict[int, Dict[str, int]] = LazyGameStore("basket_streaks")

BASKET_DEBUG = True

# Эмодзи для кнопки "Мяч сдулся" (единый для всех режимов)
FLAT_ICON_ID = "5890740808323173951"

# Два варианта премиум-эмодзи для демо-победы
DEMO_BASKET_EMOJIS = [
    "<tg-emoji emoji-id='5888994487505536067'>🏀</tg-emoji>",
    "<tg-emoji emoji-id='5891181665241271999'>🏀</tg-emoji>",
]

# Три варианта премиум-эмодзи для 0demo
ZERO_DEMO_BASKET_EMOJIS = [
    "<tg-emoji emoji-id='5888765728957402475'>🏀</tg-emoji>",
    "<tg-emoji emoji-id='5890782306297187597'>🏀</tg-emoji>",
    "<tg-emoji emoji-id='5890945283126202225'>🏀</tg-emoji>",
]

# Маскировочные механики
DEMO_MASK_LOSS_PROB = 0.45               # вероятность подмены WIN → LOSS в demo-режиме
DEMO_MASK_FLAT_PROB = 0.05               # вероятность подмены WIN → FLAT в demo-режиме
DEMO_STREAK_BREAK = 3                    # после скольких побед подряд принудительно LOSS
ZERO_MASK_WIN_PROB = 0.12                # вероятность подмены LOSS → WIN в 0demo-режиме
ZERO_STREAK_BREAK = 3                    # после скольких проигрышей подряд принудительно WIN

# Вероятность промаха (не попал в TARGET_VALUES)
_all_values = range(1, 6)
_miss_values = [v for v in _all_values if v not in TARGET_VALUES]
BASKET_MISS_PROBABILITY = Decimal(len(_miss_values)) / Decimal(5)

# Условная вероятность «мяч сдулся» при промахе
if BASKET_MISS_PROBABILITY > 0:
    BASKET_FLAT_CONDITIONAL = min(BASKET_FLAT_CHANCE / BASKET_MISS_PROBABILITY, Decimal(1))
else:
    BASKET_FLAT_CONDITIONAL = Decimal(0)


# ===================== DEBUG =====================
def _kdbg(tag: str, msg: str) -> None:
    if not BASKET_DEBUG:
        return
    try:
        print(f"[BASKET][{tag}] {msg}", flush=True)
    except Exception:
        pass


def _kdbg_err(tag: str, err: Exception) -> None:
    if not BASKET_DEBUG:
        return
    try:
        print(f"[BASKET][ERROR][{tag}] {err}", flush=True)
        print(traceback.format_exc(), flush=True)
    except Exception:
        pass


# ===================== УТИЛИТЫ =====================
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
        return max(0, int(x.quantize(0, rounding=ROUND_DOWN)))
    except Exception:
        return 0


def _parse_bet_to_int(s: str) -> int:
    raw = (s or "").strip().replace(" ", "").replace(",", ".")
    return _to_int_floor(_dec(raw))


def _fmt_int(n: int) -> str:
    try:
        return "{:,.0f}".format(int(n)).replace(",", ".")
    except Exception:
        return str(n)


def _is_flat_roll_raw() -> bool:
    """Исходная вероятность (для 0demo, без привязки к dice)."""
    try:
        r = Decimal(str(random.random()))
        flat = r < BASKET_FLAT_CHANCE
        _kdbg("FLAT_RAW", f"rand={r} chance={BASKET_FLAT_CHANCE} flat={flat}")
        return flat
    except Exception:
        return False


def _is_flat_roll_conditional() -> bool:
    """Условная вероятность «мяч сдулся» при уже случившемся промахе."""
    try:
        r = Decimal(str(random.random()))
        flat = r < BASKET_FLAT_CONDITIONAL
        _kdbg("FLAT_COND", f"rand={r} cond={BASKET_FLAT_CONDITIONAL} flat={flat}")
        return flat
    except Exception:
        return False


def _cooldown_left(chat_id: int, user_id: int) -> int:
    now = time.time()
    duration = delaysssssssssgamesonee.get(chat_id, 5)
    try:
        duration = float(duration)
    except Exception:
        duration = 2.0

    if duration <= 0:
        return 0

    chat_map = last_basket_time.setdefault(chat_id, {})
    last_usage = float(chat_map.get(user_id, 0.0) or 0.0)
    left = duration - (now - last_usage)
    return int(left) if left > 0 else 0


def _cooldown_mark(chat_id: int, user_id: int) -> None:
    chat_map = last_basket_time.setdefault(chat_id, {})
    chat_map[user_id] = time.time()
    _save_safe(last_basket_time)


def _get_streaks(user_id: int) -> Dict[str, int]:
    streaks = _basket_streaks.get(user_id)
    if streaks is None:
        streaks = {"win_streak": 0, "lose_streak": 0}
        _basket_streaks[user_id] = streaks
        _save_safe(_basket_streaks)
    return streaks


def _update_streaks(user_id: int, is_win: bool, is_flat: bool = False) -> None:
    streaks = _get_streaks(user_id)
    if is_flat:
        streaks["win_streak"] = 0
        streaks["lose_streak"] = 0
    elif is_win:
        streaks["win_streak"] = streaks.get("win_streak", 0) + 1
        streaks["lose_streak"] = 0
    else:
        streaks["lose_streak"] = streaks.get("lose_streak", 0) + 1
        streaks["win_streak"] = 0
    _basket_streaks[user_id] = streaks
    _save_safe(_basket_streaks)
    _kdbg("STREAKS", f"user={user_id} win={streaks['win_streak']} lose={streaks['lose_streak']}")


async def _mark_user_game_activity(user_id: int, reason: str = "") -> None:
    try:
        await db.touch_balance_last_active(int(user_id), set_active_status=True)
        _kdbg("ACTIVITY", f"touch ok user_id={user_id} reason={reason}")
    except Exception as e:
        _kdbg("ACTIVITY", f"touch error user_id={user_id} reason={reason}: {e}")


async def _safe_add_xp(user_id: int) -> None:
    try:
        await db.add_xp_to_games(user_id)
    except Exception:
        pass


async def _safe_edit_text(
    msg: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML",
) -> None:
    try:
        await msg.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )
    except (TelegramBadRequest, TelegramAPIError) as e:
        if "message is not modified" in str(e).lower():
            return
        try:
            await asyncio.sleep(0.15)
            await msg.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
    except Exception:
        pass


async def _safe_edit_reply_markup(message: Message, reply_markup: InlineKeyboardMarkup) -> None:
    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
    except (TelegramBadRequest, TelegramAPIError) as e:
        if "message is not modified" in str(e).lower():
            return
        try:
            await asyncio.sleep(0.15)
            await message.edit_reply_markup(reply_markup=reply_markup)
        except Exception:
            pass
    except Exception:
        pass


async def _send_invoice_later(message: Message, user_id: int, stars_amount: str, delay: float) -> None:
    try:
        await asyncio.sleep(max(0.0, float(delay)))
        ctx = pending_context.get(user_id)
        if ctx and not ctx.get("sent"):
            invoice_message = await send_invoice_to_user(message, stars_amount)
            pending_context[user_id]["manual_message_id"] = getattr(invoice_message, "message_id", None)
            _kdbg("DONATE", f"invoice sent user_id={user_id} stars={stars_amount}")
    except Exception as e:
        _kdbg("DONATE", f"invoice later error user_id={user_id}: {e}")


# ===================== WRAPPERS БАЛАНСОВ =====================
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


# ===================== ЛОГ "ДОМОЙ" =====================
async def _home_take_and_log_basket_flat(*, user_id: int, loss: int) -> None:
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

        # HTML-эмодзи - единственный текст сообщения
        emoji_html = '<tg-emoji emoji-id="5384088040677319401">🏀</tg-emoji>'

        # Кнопка с именем: если есть username → ссылка на профиль, иначе → заглушка со ⭐️
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
                        text="Баскетбол",
                        callback_data="pass"
                    )
                ],
                [row_name_btn],
                [
                    InlineKeyboardButton(
                        text=f"+ {_fmt_int(loss)} на чёрный рынок",
                        callback_data="pass"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{_fmt_int(chat_balance)} кут доступно",
                        callback_data="pass"
                    )
                ]
            ]
        )

        # Основная отправка с premium-эмодзи и кнопками
        try:
            await bot1.send_message(
                int(TECH_CHAT_ID),
                emoji_html,
                reply_markup=inline_kb,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception:
            # Fallback: обычный HTML-текст без кнопок, если premium-эмодзи не поддерживаются
            await bot1.send_message(
                int(TECH_CHAT_ID),
                f"🏀 Баскетбол [Мяч сдулся]\n<blockquote><b>+ {_fmt_int(loss)} на чёрный рынок</b></blockquote>\n<blockquote><b>{_fmt_int(chat_balance)} кут доступно для выкупов</b></blockquote>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

    except Exception as e:
        _kdbg_err("HOME_FLAT_LOG", e)


# ===================== GC / ЧЕЛЛЕНДЖ =====================
async def _load_gc_state_for_user_basket(user_id: int) -> dict:
    has_assignment = False
    is_free = False
    current_two = 0
    target_amount = 0
    max_bet = basket_BASE_MAX_BET

    try:
        gc_bet_limit = await db.gc_get_bet_limit_for_user(user_id)
        _kdbg("GC_LIMIT", f"gc_get_bet_limit_for_user -> {gc_bet_limit!r}")
    except Exception as e:
        gc_bet_limit = None
        _kdbg("GC_LIMIT", f"error: {e}")

    if gc_bet_limit is not None:
        try:
            gc_bet_limit_int = int(gc_bet_limit)
            if gc_bet_limit_int > 0:
                max_bet = min(max_bet, gc_bet_limit_int)
        except Exception as e:
            _kdbg("GC_LIMIT", f"convert error {gc_bet_limit!r}: {e}")

    try:
        assignment = await db.get_active_gc_assignment(user_id)
        _kdbg("GC_STATE", f"get_active_gc_assignment -> {bool(assignment)}")
    except Exception as e:
        assignment = None
        _kdbg("GC_STATE", f"error: {e}")

    if assignment and str(assignment.get("status") or "").lower() == "active":
        has_assignment = True

        try:
            is_free = bool(await db.gc_active_is_free(user_id))
        except Exception as e:
            is_free = False
            _kdbg("GC_STATE", f"error gc_active_is_free: {e}")

        try:
            current_two_val = await db.gc_get_current_two_balance(user_id)
            current_two = int(current_two_val or 0)
        except Exception as e:
            current_two = 0
            _kdbg("GC_STATE", f"error gc_get_current_two_balance: {e}")

        try:
            target_amount = int(assignment.get("target_amount") or 0)
        except Exception:
            target_amount = 0

        _kdbg("GC_STATE", f"user={user_id} active=1 free={is_free} two={current_two} target={target_amount} max_bet={max_bet}")
    else:
        _kdbg("GC_STATE", f"user={user_id} no active assignment max_bet={max_bet}")

    return {
        "has_assignment": has_assignment,
        "is_free": is_free,
        "current_two": current_two,
        "target_amount": target_amount,
        "max_bet": max_bet,
    }


# ===================== FREE-РЕЖИМ =====================
async def _tgbasket_free_game(
    message: Message,
    user_id: int,
    chat_id: int,
    bet_int: int,
    gc_state: dict,
) -> None:
    left = _cooldown_left(chat_id, user_id)
    if left > 0:
        await message.reply(f"<tg-emoji emoji-id='5253709334835128381'>⌚️</tg-emoji> <b>Подождите {left} сек</b>", parse_mode="HTML")
        _kdbg("CD", f"free cooldown block left={left}s")
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
        await message.reply("😓", reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        _kdbg("FREE", f"not enough two_balance bet={bet_int} two={current_two} target={target_amount}")
        return

    basketball = await message.reply_dice(emoji="🏀")
    await asyncio.sleep(4.9)

    value = getattr(getattr(basketball, "dice", None), "value", None)
    is_hit = int(value or 0) in TARGET_VALUES

    flat_now = (not is_hit) and _is_flat_roll_conditional()
    _kdbg("FREE", f"dice value={value} hit={is_hit} bet={bet_int} flat={flat_now}")

    mult_dec = _dec(multiplier_basket)
    bet_dec = _dec(bet_int)

    if flat_now:
        try:
            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
            _kdbg("GC", f"FREE FLAT gc -{bet_int}")
        except Exception as e:
            _kdbg("GC", f"FREE FLAT gc error: {e}\n{traceback.format_exc()}")

        await _mark_user_game_activity(user_id, reason="flat_free")
        await _safe_add_xp(user_id)

        button = InlineKeyboardButton(
            text="Мяч сдулся",
            callback_data="money_won",
            style="default",
            icon_custom_emoji_id=FLAT_ICON_ID
        )
        await _safe_edit_reply_markup(basketball, InlineKeyboardMarkup(inline_keyboard=[[button]]))
        return

    if is_hit:
        win_amount = (bet_dec * mult_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        profit = max(Decimal(0), win_amount - bet_dec)
        profit_int = int(profit)

        if profit_int > 0:
            try:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
                _kdbg("GC", f"FREE WIN gc +{profit_int}")
            except Exception as e:
                _kdbg("GC", f"FREE WIN gc error: {e}\n{traceback.format_exc()}")

        await _mark_user_game_activity(user_id, reason="win_free")
        await _safe_add_xp(user_id)

        button = InlineKeyboardButton(
            text=f"{_fmt_int(profit_int)} кут | {mult_dec:.1f}x",
            callback_data="money_won",
            style="default",
            icon_custom_emoji_id="5202148759252786291"
        )
        await _safe_edit_reply_markup(basketball, InlineKeyboardMarkup(inline_keyboard=[[button]]))
        return

    # LOSS
    try:
        await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
        _kdbg("GC", f"FREE LOSS gc -{bet_int}")
    except Exception as e:
        _kdbg("GC", f"FREE LOSS gc error: {e}\n{traceback.format_exc()}")

    await _mark_user_game_activity(user_id, reason="loss_free")
    await _safe_add_xp(user_id)

    button = InlineKeyboardButton(
        text="Промах",
        callback_data="money_won",
        style="danger",
        icon_custom_emoji_id="4956499161319998529"
    )
    await _safe_edit_reply_markup(basketball, InlineKeyboardMarkup(inline_keyboard=[[button]]))


# ===================== ОСНОВНОЙ ХЭНДЛЕР =====================
@dp.message(lambda message: bool(message.text) and message.text.split()[0].lower() in ("баскет", "баскетбал", "баскетбол", "баскетболл"))
async def tgbasket(message: Message):
    text = (message.text or "").strip().lower()
    parts = (message.text or "").strip().split()

    if len(parts) != 2:
        await message.reply(
            "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Формат: баскет (ставка)</b>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        _kdbg("FMT", f"bad format text={message.text!r}")
        return

    if message.chat.type == "private":
        await message.reply(
            "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В эту игру можно играть только в публичных группах.</b>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    try:
        bet_int = _parse_bet_to_int(parts[1])
    except Exception:
        await message.reply(
            "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Ставка должна быть числом.</b>",
            parse_mode="HTML"
        )
        return

    if bet_int <= 0:
        await message.reply(
            "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Ставка должна быть больше нуля.</b>",
            parse_mode="HTML"
        )
        return

    if bet_int < basket_MIN_BET:
        await message.reply(
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Минимальная ставка {basket_MIN_BET} кут.</b>",
            parse_mode="HTML"
        )
        return

    if bet_int > basket_BASE_MAX_BET:
        await message.reply(
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Максимальная ставка {basket_BASE_MAX_BET} кут.</b>",
            parse_mode="HTML"
        )
        return

    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)

    _kdbg("START", f"user={user_id} chat={chat_id} bet={bet_int} cmd={text}")

    # Инициализация новичка
    try:
        if await db.get_newbie_expires_at(user_id) is None:
            from datetime import datetime, timedelta, timezone
            expires = datetime.now(timezone.utc) + timedelta(hours=random.uniform(0.5, 24.0))
            await db.set_newbie_expires_at(user_id, expires)
            _kdbg("NEWBIE", f"newbie expires set {expires}")
    except Exception as e:
        _kdbg("NEWBIE", f"error {e}")
    await welcome_back_gift(user_id)

    # GC state
    gc_state = await _load_gc_state_for_user_basket(user_id)
    has_assignment = bool(gc_state.get("has_assignment"))
    is_free = bool(gc_state.get("is_free"))
    max_bet_gc = int(gc_state.get("max_bet") or basket_BASE_MAX_BET)

    if bet_int > max_bet_gc:
        await message.reply(
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Максимальная ставка для этой игры: {_fmt_int(max_bet_gc)} кут.</b>",
            parse_mode="HTML",
        )
        return

    # ----- Логика выбора режима (demo/0demo) с Jericho -----
    using_demo = False
    using_0demo = False
    jericho_action = "normal"

    if not has_assignment:
        try:
            demo_balance = int(await db.get_user_demo(user_id) or 0)
            zero_demo_balance = int(await db.get_user_0demo(user_id) or 0)
        except Exception as e:
            _kdbg("DEMO/0DEMO", f"error: {e}")
            demo_balance = 0
            zero_demo_balance = 0

        _kdbg("BONUS", f"demo={demo_balance} 0demo={zero_demo_balance} bet={bet_int}")

        # Jericho
        _kdbg("JERICHO", f"calling jericho_check user={user_id} bet={bet_int}")
        decision = await jericho_check(user_id, bet_int, game_name="баскетбол")
        jericho_action = decision.get("action", "normal")
        _kdbg("JERICHO", f"action={jericho_action} reason={decision.get('reason','')}")

        demo_enough = demo_balance >= bet_int
        zero_enough = zero_demo_balance >= bet_int

        # Базовый выбор по величине бонусов
        if demo_enough and zero_enough:
            if demo_balance > zero_demo_balance:
                using_demo = True
                _kdbg("BONUS", "base: demo (больше)")
            elif zero_demo_balance > demo_balance:
                using_0demo = True
                _kdbg("BONUS", "base: 0demo (больше)")
            else:
                using_demo = True
                _kdbg("BONUS", "base: demo (равны)")
        elif demo_enough:
            using_demo = True
            _kdbg("BONUS", "base: demo (только demo)")
        elif zero_enough:
            using_0demo = True
            _kdbg("BONUS", "base: 0demo (только 0demo)")
        else:
            _kdbg("BONUS", "base: обычный")

        # Корректировка по Jericho
        win_actions = ("force_win", "aggressive", "martingale", "safe")
        loss_actions = ("force_loss", "near_miss")

        if jericho_action in win_actions:
            if demo_enough:
                using_demo = True
                using_0demo = False
                _kdbg("JERICHO", f"{jericho_action} → switched to demo")
            else:
                _kdbg("JERICHO", f"{jericho_action} but demo insufficient → keep base")
        elif jericho_action in loss_actions:
            if zero_enough:
                using_0demo = True
                using_demo = False
                _kdbg("JERICHO", f"{jericho_action} → switched to 0demo")
            else:
                _kdbg("JERICHO", f"{jericho_action} but 0demo insufficient → keep base")
        else:
            _kdbg("JERICHO", "no relevant action → keep base")

        _kdbg("MODE", f"final: demo={using_demo} 0demo={using_0demo}")

    # FREE-режим
    if has_assignment and is_free:
        _kdbg("MODE", "FREE challenge mode")
        await _tgbasket_free_game(message, user_id, chat_id, bet_int, gc_state)
        return

    # Проверка баланса пользователя
    try:
        balance = int(await db.get_user_balance(user_id) or 0)
    except Exception:
        balance = 0

    if not using_demo and not using_0demo and bet_int > balance:
        bet_dec = Decimal(bet_int)
        stars = bet_dec * _dec(donate_bet)
        stars_q = stars.quantize(Decimal("1.000000"), rounding=ROUND_HALF_UP).normalize()
        stars_amount = format(stars_q, "f")

        try:
            bot_username = await get_bot_username_by_token(TOKEN)
        except Exception:
            bot_username = "CuteGamingBot"

        pending_context[user_id] = {"stars_amount": stars_amount, "sent": False}

        rows = [
            [
                InlineKeyboardButton(
                    text=f"💫 Купить {_fmt_int(bet_int)} кут 💰",
                    url=f"https://t.me/{bot_username}?start=insert_{stars_amount}_+",
                )
            ],
            [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")],
        ]

        if has_assignment and not is_free:
            rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
            rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])

        await message.reply(
            "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

        asyncio.create_task(_send_invoice_later(message, user_id, stars_amount, delay=timeoutdonate))
        _kdbg("DONATE", f"need buy bet={bet_int} stars={stars_amount} bot=@{bot_username}")
        return

    # Проверка баланса группы
    try:
        chat_balance = await _chat_get_balance(chat_id)
    except Exception:
        chat_balance = 0

    if bet_int > chat_balance:
        rows = []
        if has_assignment and not is_free:
            rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
            rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])

        await message.reply(
            "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В группе недостаточно средств для игры.</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        _kdbg("BANK", f"not enough chat bank bet={bet_int} chat_balance={chat_balance}")
        return

    # Кулдаун
    left = _cooldown_left(chat_id, user_id)
    if left > 0:
        await message.reply(
            f"<tg-emoji emoji-id='5253709334835128381'>⌚️</tg-emoji> <b>Подождите {left} сек</b>",
            parse_mode="HTML"
        )
        _kdbg("CD", f"cooldown block left={left}s")
        return
    _cooldown_mark(chat_id, user_id)

    # Загружаем серии
    streaks = _get_streaks(user_id)
    win_streak = streaks.get("win_streak", 0)
    lose_streak = streaks.get("lose_streak", 0)

    # ===================== 0DEMO (гарантированный проигрыш, но с возможной маскировкой на WIN) =====================
    if using_0demo:
        # Отправляем случайный премиум-эмодзи 🏀 (списание 0demo будет ТОЛЬКО при реальном проигрыше)
        sent_emoji = random.choice(ZERO_DEMO_BASKET_EMOJIS)
        sent_msg = await message.reply(sent_emoji, parse_mode="HTML")
        await asyncio.sleep(3)

        # Определяем, будет ли FLAT или LOSS (базовый проигрыш)
        flat_now = _is_flat_roll_raw()

        # МАСКИРОВКА: если длинная серия проигрышей или случай, подменяем на WIN
        should_win = False
        if lose_streak >= ZERO_STREAK_BREAK:
            should_win = True
            _kdbg("0DEMO_MASK", f"streak break: lose_streak={lose_streak} -> WIN")
        elif random.random() < ZERO_MASK_WIN_PROB:
            should_win = True
            _kdbg("0DEMO_MASK", "random chance -> WIN")

        if should_win:
            # МАСКИРОВКА: подмена проигрыша на выигрыш
            # НЕ списываем 0demo, НЕ гасим долг
            mult_dec = _dec(multiplier_basket)
            bet_dec = _dec(bet_int)
            win_amount = (bet_dec * mult_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            profit_int = max(0, int(win_amount - bet_dec))

            try:
                chat_balance = await _chat_get_balance(chat_id)
            except Exception:
                chat_balance = 0

            pay = min(profit_int, max(0, chat_balance))
            if pay > 0:
                await _chat_minus(chat_id, pay)
                await _user_plus(user_id, pay)
                try:
                    await db.cutehistory_plus(user_id, float(pay), "+ баскетбол (0demo маскировка)")
                except Exception as e:
                    _kdbg("HISTORY", f"cutehistory_plus(0demo_mask) error: {e}")
                try:
                    await db.update_user_wins(user_id, 1, bot1, ref_coin)
                except Exception as e:
                    _kdbg("STATS", f"update_user_wins(0demo_mask) error: {e}")

            if has_assignment and profit_int > 0:
                try:
                    await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
                    _kdbg("GC", f"0DEMO_MASK WIN gc +{profit_int}")
                except Exception as e:
                    _kdbg("GC", f"0DEMO_MASK WIN gc error: {e}")

            await _mark_user_game_activity(user_id, reason="0demo_masked_win")
            await _safe_add_xp(user_id)
            _update_streaks(user_id, is_win=True)

            btn_text = f"{_fmt_int(pay)} кут | {mult_dec:.1f}x"
            button = InlineKeyboardButton(
                text=btn_text,
                callback_data="money_won",
                style="default",
                icon_custom_emoji_id="5384088040677319401"
            )
            await _safe_edit_text(
                sent_msg,
                "<tg-emoji emoji-id='5888994487505536067'>🏀</tg-emoji>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
                parse_mode="HTML",
            )
            return

        # Если не подменили – обычный проигрыш (LOSS или FLAT)
        # Сначала списываем 0demo и основной баланс, гасим долг
        try:
            await db.deduct_0demo_amount(user_id, bet_int)
            _kdbg("0DEMO", f"deduct 0demo {bet_int}")
        except Exception as e:
            _kdbg("0DEMO", f"deduct 0demo error: {e}")

        _kdbg("0DEMO_DEBT", f"calling force_repay_debt({user_id}, {bet_int})")
        try:
            await force_repay_debt(user_id, bet_int)
            _kdbg("0DEMO_DEBT", f"force_repay_debt completed for {user_id} amount {bet_int}")
        except Exception as e:
            _kdbg_err("0DEMO_DEBT_FAILED", e)

        if has_assignment:
            try:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                _kdbg("GC", f"0DEMO JAM gc -{bet_int}")
            except Exception as e:
                _kdbg("GC", f"0DEMO JAM gc error: {e}")

        ok_minus = await _user_minus(user_id, bet_int)
        _kdbg("0DEMO_LOSS", f"user_minus={ok_minus} amount={bet_int}")

        try:
            await db.cutehistory_minus(user_id, bet_int, "- баскетбол (0demo)")
        except Exception as e:
            _kdbg("HISTORY", f"cutehistory_minus(0demo) error: {e}")
        try:
            await db.update_user_loose(user_id, 1, bot1, ref_coin)
            await db.update_game_last_activity(user_id)
        except Exception as e:
            _kdbg("STATS", f"update_user_loose(0demo) error: {e}")

        await _mark_user_game_activity(user_id, reason="0demo_loss")
        await _safe_add_xp(user_id)
        _update_streaks(user_id, is_win=False, is_flat=flat_now)

        if flat_now:
            await _home_take_and_log_basket_flat(user_id=user_id, loss=bet_int)
            button = InlineKeyboardButton(
                text="Мяч сдулся",
                callback_data="money_won",
                style="default",
                icon_custom_emoji_id=FLAT_ICON_ID
            )
            final_text = sent_emoji
        else:
            await _chat_plus(chat_id, bet_int)
            button = InlineKeyboardButton(
                text="Промах",
                callback_data="money_won",
                style="danger",
                icon_custom_emoji_id="4956499161319998529"
            )
            final_text = sent_emoji

        await _safe_edit_text(
            sent_msg,
            final_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
            parse_mode="HTML",
        )
        return

    # ===================== DEMO (гарантированный выигрыш, но с возможной маскировкой на LOSS/FLAT) =====================
    if using_demo:
        # Отправляем случайный премиум-эмодзи 🏀 (списание demo будет ТОЛЬКО при реальном выигрыше)
        demo_emoji = random.choice(DEMO_BASKET_EMOJIS)
        sent_msg = await message.reply(demo_emoji, parse_mode="HTML")
        await asyncio.sleep(3)

        # Гарантированное попадание (базово)
        mult_dec = _dec(multiplier_basket)
        bet_dec = _dec(bet_int)
        win_amount = (bet_dec * mult_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        profit_int = max(0, int(win_amount - bet_dec))

        # МАСКИРОВКА: если длинная серия побед или случай, подменяем на LOSS или FLAT
        should_lose = False
        should_flat = False

        if win_streak >= DEMO_STREAK_BREAK:
            should_lose = True
            _kdbg("DEMO_MASK", f"streak break: win_streak={win_streak} -> LOSS")
        else:
            r = random.random()
            if r < DEMO_MASK_FLAT_PROB:
                should_flat = True
                _kdbg("DEMO_MASK", "random chance -> FLAT")
            elif r < DEMO_MASK_FLAT_PROB + DEMO_MASK_LOSS_PROB:
                should_lose = True
                _kdbg("DEMO_MASK", "random chance -> LOSS")

        if should_lose or should_flat:
            # МАСКИРОВКА: подмена выигрыша на проигрыш
            # НЕ списываем demo, ставка идёт с основного баланса как обычный проигрыш
            if has_assignment:
                try:
                    await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                    _kdbg("GC", f"DEMO_MASK LOSS gc -{bet_int}")
                except Exception as e:
                    _kdbg("GC", f"DEMO_MASK LOSS gc error: {e}")

            await _user_minus(user_id, bet_int)
            await _mark_user_game_activity(user_id, reason="demo_masked_loss")
            await _safe_add_xp(user_id)
            _update_streaks(user_id, is_win=False, is_flat=should_flat)

            if should_flat:
                await _home_take_and_log_basket_flat(user_id=user_id, loss=bet_int)
                button = InlineKeyboardButton(
                    text="Мяч сдулся",
                    callback_data="money_won",
                    style="default",
                    icon_custom_emoji_id=FLAT_ICON_ID
                )
            else:
                await _chat_plus(chat_id, bet_int)
                button = InlineKeyboardButton(
                    text="Промах",
                    callback_data="money_won",
                    style="danger",
                    icon_custom_emoji_id="4956499161319998529"
                )

            await _safe_edit_text(
                sent_msg,
                demo_emoji,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
                parse_mode="HTML",
            )
            return

        # Обычный выигрыш demo (не маскированный) – списываем demo
        try:
            await db.deduct_demo_amount(user_id, bet_int)
            _kdbg("DEMO", f"deduct demo {bet_int}")
        except Exception as e:
            _kdbg("DEMO", f"deduct demo error: {e}")

        try:
            chat_balance = await _chat_get_balance(chat_id)
        except Exception:
            chat_balance = 0

        pay = min(profit_int, max(0, chat_balance))
        if pay > 0:
            await _chat_minus(chat_id, pay)
            await _user_plus(user_id, pay)
            try:
                await db.cutehistory_plus(user_id, float(pay), "+ баскетбол")
            except Exception as e:
                _kdbg("HISTORY", f"cutehistory_plus(demo) error: {e}")
            try:
                await db.update_user_wins(user_id, 1, bot1, ref_coin)
            except Exception as e:
                _kdbg("STATS", f"update_user_wins(demo) error: {e}")

        if has_assignment and profit_int > 0:
            try:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
                _kdbg("GC", f"DEMO WIN gc +{profit_int}")
            except Exception as e:
                _kdbg("GC", f"DEMO WIN gc error: {e}")

        await _mark_user_game_activity(user_id, reason="demo_win")
        await _safe_add_xp(user_id)
        _update_streaks(user_id, is_win=True)

        btn_text = f"{_fmt_int(pay)} кут | {mult_dec:.1f}x"
        button = InlineKeyboardButton(
            text=btn_text,
            callback_data="money_won",
            style="default",
            icon_custom_emoji_id="5384088040677319401"
        )
        await _safe_edit_text(
            sent_msg,
            "<tg-emoji emoji-id='5888994487505536067'>🏀</tg-emoji>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
            parse_mode="HTML",
        )
        return

    # ===================== Обычный бросок (dice) =====================
    basketball = await message.reply_dice(emoji="🏀")
    await asyncio.sleep(4.9)

    value = getattr(getattr(basketball, "dice", None), "value", None)
    is_hit = int(value or 0) in TARGET_VALUES
    flat_now = (not is_hit) and _is_flat_roll_conditional()
    _kdbg("DICE", f"value={value} hit={is_hit} flat={flat_now}")

    mult_dec = _dec(multiplier_basket)
    bet_dec = _dec(bet_int)

    # FLAT
    if flat_now:
        if has_assignment:
            try:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                _kdbg("GC", f"FLAT gc -{bet_int}")
            except Exception as e:
                _kdbg("GC", f"FLAT gc error: {e}\n{traceback.format_exc()}")

        ok_minus = await _user_minus(user_id, bet_int)
        _kdbg("FLAT", f"user_minus={ok_minus} amount={bet_int}")

        try:
            await db.cutehistory_minus(user_id, bet_int, "- баскетбол (мяч сдулся)")
        except Exception as e:
            _kdbg("HISTORY", f"cutehistory_minus(flat) error: {e}")
        try:
            await db.update_user_loose(user_id, 1, bot1, ref_coin)
            await db.update_game_last_activity(user_id)
        except Exception as e:
            _kdbg("STATS", f"update_user_loose(flat) error: {e}")

        await _mark_user_game_activity(user_id, reason="flat")
        await _safe_add_xp(user_id)
        _update_streaks(user_id, is_win=False, is_flat=True)

        await _home_take_and_log_basket_flat(user_id=user_id, loss=bet_int)

        button = InlineKeyboardButton(
            text="Мяч сдулся",
            callback_data="money_won",
            style="default",
            icon_custom_emoji_id=FLAT_ICON_ID
        )
        await _safe_edit_reply_markup(basketball, InlineKeyboardMarkup(inline_keyboard=[[button]]))
        return

    # WIN
    if is_hit:
        try:
            balance = int(await db.get_user_balance(user_id) or 0)
        except Exception:
            balance = 0
        try:
            chat_balance = await _chat_get_balance(chat_id)
        except Exception:
            chat_balance = 0

        if balance < bet_int:
            btn_help = InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")
            await message.reply(
                f"💭 <b>Недостаточно средств для игры\n💰 Ваш баланс : {_fmt_int(balance)} кут</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn_help]]),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            _kdbg("RACE", f"balance dropped before payout balance={balance} bet={bet_int}")
            return

        win_amount = (bet_dec * mult_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        win_amount_int = int(win_amount)
        profit_int = max(0, win_amount_int - bet_int)
        _kdbg("WIN", f"win_amount={win_amount_int} profit={profit_int}")

        if chat_balance < win_amount_int:
            pay = max(0, int(chat_balance))
            effective_profit = max(0, pay - bet_int)

            if has_assignment and effective_profit > 0:
                try:
                    await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=effective_profit, outcome="+")
                    _kdbg("GC", f"WIN PARTIAL gc +{effective_profit}")
                except Exception as e:
                    _kdbg("GC", f"WIN PARTIAL gc error: {e}\n{traceback.format_exc()}")

            await _chat_minus(chat_id, pay)
            await _user_plus(user_id, pay)
            await _mark_user_game_activity(user_id, reason="win_partial")
            await _safe_add_xp(user_id)
            _update_streaks(user_id, is_win=True)

            btn = InlineKeyboardButton(
                text="Нажми на меня",
                callback_data=f"errorbasket_{pay}",
                style="default",
                icon_custom_emoji_id="6028346797368283073"
            )
            await _safe_edit_reply_markup(basketball, InlineKeyboardMarkup(inline_keyboard=[[btn]]))
            return

        # полная выплата
        if has_assignment and profit_int > 0:
            try:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
                _kdbg("GC", f"WIN gc +{profit_int}")
            except Exception as e:
                _kdbg("GC", f"WIN gc error: {e}\n{traceback.format_exc()}")

        await _user_plus(user_id, win_amount_int - bet_int)
        await _chat_minus(chat_id, win_amount_int - bet_int)
        await db.update_user_wins(user_id, 1, bot1, ref_coin)
        await db.cutehistory_plus(user_id, float(win_amount_int), "+ баскетбол")

        await _mark_user_game_activity(user_id, reason="win")
        await _safe_add_xp(user_id)
        _update_streaks(user_id, is_win=True)

        button = InlineKeyboardButton(
            text=f"{_fmt_int(profit_int)} кут | {mult_dec:.1f}x",
            callback_data="money_won",
            style="default",
            icon_custom_emoji_id="5384088040677319401"
        )
        await _safe_edit_reply_markup(basketball, InlineKeyboardMarkup(inline_keyboard=[[button]]))
        return

    # LOSS
    if has_assignment:
        try:
            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
            _kdbg("GC", f"LOSS gc -{bet_int}")
        except Exception as e:
            _kdbg("GC", f"LOSS gc error: {e}\n{traceback.format_exc()}")

    await _user_minus(user_id, bet_int)
    await _chat_plus(chat_id, bet_int)
    await db.update_user_loose(user_id, 1, bot1, ref_coin)
    await db.cutehistory_minus(user_id, float(bet_int), "- баскетбол")

    await _mark_user_game_activity(user_id, reason="loss")
    await _safe_add_xp(user_id)
    _update_streaks(user_id, is_win=False)

    button = InlineKeyboardButton(
        text="Промах",
        callback_data="money_won",
        style="danger",
        icon_custom_emoji_id="4956499161319998529"
    )
    await _safe_edit_reply_markup(basketball, InlineKeyboardMarkup(inline_keyboard=[[button]]))


# ===================== CALLBACKS =====================
@dp.callback_query(F.data.startswith("errorbasket_"))
async def errorbasket_alert(callback_query: CallbackQuery):
    data_parts = (callback_query.data or "").split("_", 1)
    pay = data_parts[1] if len(data_parts) > 1 else "неизвестно"
    try:
        await callback_query.answer(
            "💭 На балансе группы недостаточно кут для выплаты выигрыша\n"
            f"💸 Баланс группы : {pay} кут",
            show_alert=True,
        )
    except Exception:
        pass


@dp.callback_query(F.data == "money_won")
async def basket_info_stub(callback_query: CallbackQuery):
    try:
        await callback_query.answer("Результат броска зафиксирован ✅", show_alert=False)
    except Exception:
        pass