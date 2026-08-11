# -*- coding: utf-8 -*-
"""
⚽️ Футбол (футбол/фут) (ставка) - полная версия с Jericho, маскировкой и сериями.
Исправлено: целевые значения гола {3,4,5}, динамический расчёт промаха.
"""

from main import *  # noqa: F401,F403
from bot.games.group_only import reject_if_private_game

import asyncio
import random
import time
import traceback
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, getcontext
from typing import Dict, Any, Optional

from aiogram import F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from bot.funcs.func import get_bot_username_by_token
from bot.funcs.tech_home_log import safe_send_tech_log

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

last_soccer_time: Dict[int, Dict[int, float]] = LazyGameStore("last_soccer_time")
_soccer_streaks: Dict[int, Dict[str, int]] = LazyGameStore("soccer_streaks")

SOCCER_DEBUG = True

# Эмодзи для кнопок
BAD_SHOT_ICON_ID = "5890787425898205095"   # 🚫
LOSS_ICON_ID = "4956499161319998529"       # 💥
WIN_ICON_ID = "5188361519095649349"        # 🎯

# Эмодзи для демо (гарантированный гол)
DEMO_SOCCER_EMOJIS = [
    "<tg-emoji emoji-id='5891020552428064694'>⚽️</tg-emoji>",
    "<tg-emoji emoji-id='5890971512491478559'>⚽️</tg-emoji>",
    "<tg-emoji emoji-id='5891262492230815634'>⚽️</tg-emoji>",
]

# Эмодзи для 0demo (проигрыш)
ZERO_DEMO_SOCCER_EMOJIS = [
    "<tg-emoji emoji-id='5888842767785791286'>⚽</tg-emoji>",
    "<tg-emoji emoji-id='5890793919888756278'>⚽</tg-emoji>",
]

# Маскировочные механики
DEMO_MASK_LOSS_PROB = 0.45               # вероятность подмены WIN → LOSS в demo-режиме
DEMO_MASK_BAD_PROB = 0.05                # вероятность подмены WIN → BAD_SHOT в demo-режиме
DEMO_STREAK_BREAK = 3                    # после скольких побед подряд принудительно LOSS
ZERO_MASK_WIN_PROB = 0.12                # вероятность подмены LOSS → WIN в 0demo-режиме
ZERO_STREAK_BREAK = 3                    # после скольких проигрышей подряд принудительно WIN

# -------------------- Целевые значения dice (гол) --------------------
# У футбольного дайса (⚽) значения от 1 до 5
SOCCER_DICE_MAX_VALUE = 5
SOCCER_TARGET_VALUES = {3, 5, 4}          # гол при 3, 4 или 5

# Вероятности исходов (используются только в обычном режиме)
SOCCER_BAD_SHOT_CHANCE = Decimal("0.08")  # общая вероятность неудачного удара

# Фактическая вероятность промаха = (всего_значений - целевых) / всего_значений
_total_combinations = Decimal(SOCCER_DICE_MAX_VALUE)
_target_count = Decimal(len(SOCCER_TARGET_VALUES))
SOCCER_MISS_PROBABILITY = Decimal(1) - _target_count / _total_combinations

# Условная вероятность неудачного удара при промахе
if SOCCER_MISS_PROBABILITY > 0:
    SOCCER_BAD_CONDITIONAL = SOCCER_BAD_SHOT_CHANCE / SOCCER_MISS_PROBABILITY
else:
    SOCCER_BAD_CONDITIONAL = Decimal(0)

# ----------------------------------------------------------------

# ===================== DEBUG =====================
def _sdbg(tag: str, msg: str) -> None:
    if not SOCCER_DEBUG:
        return
    try:
        print(f"[SOCCER][{tag}] {msg}", flush=True)
    except Exception:
        pass


def _sdbg_err(tag: str, err: Exception) -> None:
    if not SOCCER_DEBUG:
        return
    try:
        print(f"[SOCCER][ERROR][{tag}] {err}", flush=True)
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


def _is_bad_shot_roll_raw() -> bool:
    """Исходная вероятность неудачного удара (для 0demo, без привязки к dice)."""
    try:
        r = Decimal(str(random.random()))
        bad = r < SOCCER_BAD_SHOT_CHANCE
        _sdbg("BAD_RAW", f"rand={r} chance={SOCCER_BAD_SHOT_CHANCE} bad={bad}")
        return bad
    except Exception:
        return False


def _is_bad_shot_roll_conditional() -> bool:
    """Условная вероятность неудачного удара при уже случившемся промахе."""
    try:
        r = Decimal(str(random.random()))
        bad = r < SOCCER_BAD_CONDITIONAL
        _sdbg("BAD_COND", f"rand={r} cond={SOCCER_BAD_CONDITIONAL} bad={bad}")
        return bad
    except Exception:
        return False


async def _mark_user_game_activity(user_id: int, reason: str = "") -> None:
    try:
        await db.touch_balance_last_active(int(user_id), set_active_status=True)
        _sdbg("ACTIVITY", f"touch ok user_id={user_id} reason={reason}")
    except Exception as e:
        _sdbg("ACTIVITY", f"touch error user_id={user_id} reason={reason}: {e}")


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
            _sdbg("DONATE", f"invoice sent user_id={user_id} stars={stars_amount}")
    except Exception as e:
        _sdbg("DONATE", f"invoice later error user_id={user_id}: {e}")


def _cooldown_left(chat_id: int, user_id: int) -> int:
    now = time.time()
    duration = delaysssssssssgamesonee.get(chat_id, 5)
    try:
        duration = float(duration)
    except Exception:
        duration = 2.0

    if duration <= 0:
        return 0

    chat_map = last_soccer_time.setdefault(chat_id, {})
    last_usage = float(chat_map.get(user_id, 0.0) or 0.0)
    left = duration - (now - last_usage)
    return int(left) if left > 0 else 0


def _cooldown_mark(chat_id: int, user_id: int) -> None:
    chat_map = last_soccer_time.setdefault(chat_id, {})
    chat_map[user_id] = time.time()
    _save_safe(last_soccer_time)


def _get_streaks(user_id: int) -> Dict[str, int]:
    streaks = _soccer_streaks.get(user_id)
    if streaks is None:
        streaks = {"win_streak": 0, "lose_streak": 0}
        _soccer_streaks[user_id] = streaks
        _save_safe(_soccer_streaks)
    return streaks


def _update_streaks(user_id: int, is_win: bool, is_bad: bool = False) -> None:
    streaks = _get_streaks(user_id)
    if is_bad:
        streaks["win_streak"] = 0
        streaks["lose_streak"] = 0
    elif is_win:
        streaks["win_streak"] = streaks.get("win_streak", 0) + 1
        streaks["lose_streak"] = 0
    else:
        streaks["lose_streak"] = streaks.get("lose_streak", 0) + 1
        streaks["win_streak"] = 0
    _soccer_streaks[user_id] = streaks
    _save_safe(_soccer_streaks)
    _sdbg("STREAKS", f"user={user_id} win={streaks['win_streak']} lose={streaks['lose_streak']}")


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
async def _home_take_and_log_soccer_bad_shot(*, user_id: int, loss: int) -> None:
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
        emoji_html = '<tg-emoji emoji-id="5188361519095649349">⚽️</tg-emoji>'

        # Кнопка с именем: ссылка на профиль, если есть username, иначе заглушка со ⭐️
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
                        text="Футбол",
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

        await safe_send_tech_log(
            bot1,
            int(TECH_CHAT_ID),
            html=emoji_html,
            reply_markup=inline_kb,
            fallback_html=(
                f"⚽ Футбол [Неудачный удар]\n"
                f"<blockquote><b>+ {_fmt_int(loss)} на чёрный рынок</b></blockquote>\n"
                f"<blockquote><b>{_fmt_int(chat_balance)} кут доступно для выкупов</b></blockquote>"
            ),
            tag="HOME_BAD_SHOT_LOG_SEND",
        )

    except Exception as e:
        _sdbg_err("HOME_BAD_SHOT_LOG", e)


# ===================== GC / ЧЕЛЛЕНДЖ =====================
async def _load_gc_state_for_user_soccer(user_id: int) -> dict:
    has_assignment = False
    is_free = False
    current_two = 0
    target_amount = 0
    max_bet = soccer_BASE_MAX_BET

    try:
        gc_bet_limit = await db.gc_get_bet_limit_for_user(user_id)
        _sdbg("GC_LIMIT", f"gc_get_bet_limit_for_user -> {gc_bet_limit!r}")
    except Exception as e:
        gc_bet_limit = None
        _sdbg("GC_LIMIT", f"error: {e}")

    if gc_bet_limit is not None:
        try:
            gc_bet_limit_int = int(gc_bet_limit)
            if gc_bet_limit_int > 0:
                max_bet = min(max_bet, gc_bet_limit_int)
        except Exception as e:
            _sdbg("GC_LIMIT", f"convert error {gc_bet_limit!r}: {e}")

    try:
        assignment = await db.get_active_gc_assignment(user_id)
        _sdbg("GC_STATE", f"get_active_gc_assignment -> {bool(assignment)}")
    except Exception as e:
        assignment = None
        _sdbg("GC_STATE", f"error: {e}")

    if assignment and str(assignment.get("status") or "").lower() == "active":
        has_assignment = True

        try:
            is_free = bool(await db.gc_active_is_free(user_id))
        except Exception as e:
            is_free = False
            _sdbg("GC_STATE", f"error gc_active_is_free: {e}")

        try:
            current_two_val = await db.gc_get_current_two_balance(user_id)
            current_two = int(current_two_val or 0)
        except Exception as e:
            current_two = 0
            _sdbg("GC_STATE", f"error gc_get_current_two_balance: {e}")

        try:
            target_amount = int(assignment.get("target_amount") or 0)
        except Exception:
            target_amount = 0

        _sdbg("GC_STATE", f"user={user_id} active=1 free={is_free} two={current_two} target={target_amount} max_bet={max_bet}")
    else:
        _sdbg("GC_STATE", f"user={user_id} no active assignment max_bet={max_bet}")

    return {
        "has_assignment": has_assignment,
        "is_free": is_free,
        "current_two": current_two,
        "target_amount": target_amount,
        "max_bet": max_bet,
    }


# ===================== FREE-РЕЖИМ =====================
async def _tgsoccer_free_game(
    message: Message,
    user_id: int,
    chat_id: int,
    bet_int: int,
    gc_state: dict,
) -> None:
    left = _cooldown_left(chat_id, user_id)
    if left > 0:
        await message.reply(f"<tg-emoji emoji-id='5253709334835128381'>⌚️</tg-emoji> <b>Подождите {left} сек</b>", parse_mode="HTML")
        _sdbg("CD", f"free cooldown block left={left}s")
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
        _sdbg("FREE", f"not enough two_balance bet={bet_int} two={current_two} target={target_amount}")
        return

    soccer = await message.reply_dice(emoji="⚽")
    await asyncio.sleep(4.5)

    value = getattr(getattr(soccer, "dice", None), "value", None)
    is_goal = int(value or 0) in SOCCER_TARGET_VALUES
    bad_shot_now = (not is_goal) and _is_bad_shot_roll_conditional()

    _sdbg("FREE", f"dice value={value} is_goal={is_goal} bad_shot={bad_shot_now}")

    mult_dec = _dec(multiplier_soccer)
    bet_dec = _dec(bet_int)

    if bad_shot_now:
        try:
            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
            _sdbg("GC", f"FREE BAD_SHOT gc -{bet_int}")
        except Exception as e:
            _sdbg("GC", f"FREE BAD_SHOT gc error: {e}\n{traceback.format_exc()}")

        await _mark_user_game_activity(user_id, reason="bad_shot_free")
        await _safe_add_xp(user_id)

        button = InlineKeyboardButton(
            text="Неудачный удар",
            callback_data="money_won",
            style="primary",
            icon_custom_emoji_id=BAD_SHOT_ICON_ID
        )
        await _safe_edit_reply_markup(soccer, InlineKeyboardMarkup(inline_keyboard=[[button]]))
        return

    if is_goal:
        win_amount = (bet_dec * mult_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        profit = max(Decimal(0), win_amount - bet_dec)
        profit_int = int(profit)

        if profit_int > 0:
            try:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
                _sdbg("GC", f"FREE WIN gc +{profit_int}")
            except Exception as e:
                _sdbg("GC", f"FREE WIN gc error: {e}\n{traceback.format_exc()}")

        await _mark_user_game_activity(user_id, reason="win_free")
        await _safe_add_xp(user_id)

        button = InlineKeyboardButton(
            text=f"{_fmt_int(profit_int)} кут | {mult_dec:.1f}x",
            callback_data="money_won",
            style="default",
            icon_custom_emoji_id=WIN_ICON_ID
        )
        await _safe_edit_reply_markup(soccer, InlineKeyboardMarkup(inline_keyboard=[[button]]))
        return

    # LOSS
    try:
        await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
        _sdbg("GC", f"FREE LOSS gc -{bet_int}")
    except Exception as e:
        _sdbg("GC", f"FREE LOSS gc error: {e}\n{traceback.format_exc()}")

    await _mark_user_game_activity(user_id, reason="loss_free")
    await _safe_add_xp(user_id)

    button = InlineKeyboardButton(
        text="Мимо ворот",
        callback_data="money_won",
        style="danger",
        icon_custom_emoji_id=LOSS_ICON_ID
    )
    await _safe_edit_reply_markup(soccer, InlineKeyboardMarkup(inline_keyboard=[[button]]))


# ===================== ОСНОВНОЙ ХЭНДЛЕР =====================
@dp.message(lambda message: bool(message.text) and message.text.split()[0].lower() in ("футбол", "фут"))
async def tgsoccer(message: Message):
    if await reject_if_private_game(message):
        return
    text = (message.text or "").strip().lower()
    parts = (message.text or "").strip().split()

    if len(parts) != 2:
        await message.reply(
            "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Формат: футбол (ставка)</b>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        _sdbg("FMT", f"bad format text={message.text!r}")
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

    if bet_int < soccer_MIN_BET:
        await message.reply(
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Минимальная ставка {soccer_MIN_BET} кут.</b>",
            parse_mode="HTML"
        )
        return

    if bet_int > soccer_BASE_MAX_BET:
        await message.reply(
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Максимальная ставка {soccer_BASE_MAX_BET} кут.</b>",
            parse_mode="HTML"
        )
        return

    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)

    _sdbg("START", f"user={user_id} chat={chat_id} bet={bet_int} cmd={text}")

    # Инициализация новичка
    try:
        if await db.get_newbie_expires_at(user_id) is None:
            from datetime import datetime, timedelta, timezone
            expires = datetime.now(timezone.utc) + timedelta(hours=random.uniform(0.5, 24.0))
            await db.set_newbie_expires_at(user_id, expires)
            _sdbg("NEWBIE", f"newbie expires set {expires}")
    except Exception as e:
        _sdbg("NEWBIE", f"error {e}")
    await welcome_back_gift(user_id)

    # GC state
    gc_state = await _load_gc_state_for_user_soccer(user_id)
    has_assignment = bool(gc_state.get("has_assignment"))
    is_free = bool(gc_state.get("is_free"))
    max_bet_gc = int(gc_state.get("max_bet") or soccer_BASE_MAX_BET)

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
            _sdbg("DEMO/0DEMO", f"error: {e}")
            demo_balance = 0
            zero_demo_balance = 0

        _sdbg("BONUS", f"demo={demo_balance} 0demo={zero_demo_balance} bet={bet_int}")

        # Jericho
        _sdbg("JERICHO", f"calling jericho_check user={user_id} bet={bet_int}")
        decision = await jericho_check(user_id, bet_int, game_name="футбол")
        jericho_action = decision.get("action", "normal")
        _sdbg("JERICHO", f"action={jericho_action} reason={decision.get('reason','')}")

        demo_enough = demo_balance >= bet_int
        zero_enough = zero_demo_balance >= bet_int

        # Базовый выбор по величине бонусов
        if demo_enough and zero_enough:
            if demo_balance > zero_demo_balance:
                using_demo = True
                _sdbg("BONUS", "base: demo (больше)")
            elif zero_demo_balance > demo_balance:
                using_0demo = True
                _sdbg("BONUS", "base: 0demo (больше)")
            else:
                using_demo = True
                _sdbg("BONUS", "base: demo (равны)")
        elif demo_enough:
            using_demo = True
            _sdbg("BONUS", "base: demo (только demo)")
        elif zero_enough:
            using_0demo = True
            _sdbg("BONUS", "base: 0demo (только 0demo)")
        else:
            _sdbg("BONUS", "base: обычный")

        # Корректировка по Jericho
        win_actions = ("force_win", "aggressive", "martingale", "safe")
        loss_actions = ("force_loss", "near_miss")

        if jericho_action in win_actions:
            if demo_enough:
                using_demo = True
                using_0demo = False
                _sdbg("JERICHO", f"{jericho_action} → switched to demo")
            else:
                _sdbg("JERICHO", f"{jericho_action} but demo insufficient → keep base")
        elif jericho_action in loss_actions:
            if zero_enough:
                using_0demo = True
                using_demo = False
                _sdbg("JERICHO", f"{jericho_action} → switched to 0demo")
            else:
                _sdbg("JERICHO", f"{jericho_action} but 0demo insufficient → keep base")
        else:
            _sdbg("JERICHO", "no relevant action → keep base")

        _sdbg("MODE", f"final: demo={using_demo} 0demo={using_0demo}")

    # FREE-режим
    if has_assignment and is_free:
        _sdbg("MODE", "FREE challenge mode")
        await _tgsoccer_free_game(message, user_id, chat_id, bet_int, gc_state)
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
        _sdbg("DONATE", f"need buy bet={bet_int} stars={stars_amount} bot=@{bot_username}")
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
        _sdbg("BANK", f"not enough chat bank bet={bet_int} chat_balance={chat_balance}")
        return

    # Кулдаун
    left = _cooldown_left(chat_id, user_id)
    if left > 0:
        await message.reply(
            f"<tg-emoji emoji-id='5253709334835128381'>⌚️</tg-emoji> <b>Подождите {left} сек</b>",
            parse_mode="HTML"
        )
        _sdbg("CD", f"cooldown block left={left}s")
        return
    _cooldown_mark(chat_id, user_id)

    # Загружаем серии
    streaks = _get_streaks(user_id)
    win_streak = streaks.get("win_streak", 0)
    lose_streak = streaks.get("lose_streak", 0)

    # ===================== 0DEMO (УЛУЧШЕН) =====================
    if using_0demo:
        # Заранее вычисляем, будет ли принудительный выигрыш (маскировка)
        should_win = False
        if lose_streak >= ZERO_STREAK_BREAK:
            should_win = True
            _sdbg("0DEMO_MASK", f"streak break: lose_streak={lose_streak} -> WIN")
        elif random.random() < ZERO_MASK_WIN_PROB:
            should_win = True
            _sdbg("0DEMO_MASK", "random chance -> WIN")

        # Выбираем начальное эмодзи в зависимости от ожидаемого исхода
        if should_win:
            initial_emoji = random.choice(DEMO_SOCCER_EMOJIS)      # выигрышное
        else:
            initial_emoji = random.choice(ZERO_DEMO_SOCCER_EMOJIS) # проигрышное

        sent_msg = await message.reply(initial_emoji, parse_mode="HTML")
        await asyncio.sleep(3)

        # Если не маскировка - определяем тип проигрыша
        bad_shot_now = False
        if not should_win:
            bad_shot_now = _is_bad_shot_roll_raw()

        if should_win:
            # Маскировка на выигрыш: НЕ списываем 0demo, не гасим долг
            mult_dec = _dec(multiplier_soccer)
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
                    await db.cutehistory_plus(user_id, float(pay), "+ футбол (0demo маскировка)")
                except Exception as e:
                    _sdbg("HISTORY", f"cutehistory_plus(0demo_mask) error: {e}")
                try:
                    await db.update_user_wins(user_id, 1, bot1, ref_coin)
                except Exception as e:
                    _sdbg("STATS", f"update_user_wins(0demo_mask) error: {e}")

            if has_assignment and profit_int > 0:
                try:
                    await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
                    _sdbg("GC", f"0DEMO_MASK WIN gc +{profit_int}")
                except Exception as e:
                    _sdbg("GC", f"0DEMO_MASK WIN gc error: {e}")

            await _mark_user_game_activity(user_id, reason="0demo_masked_win")
            await _safe_add_xp(user_id)
            _update_streaks(user_id, is_win=True)

            btn_text = f"{_fmt_int(pay)} кут | {mult_dec:.1f}x"
            button = InlineKeyboardButton(
                text=btn_text,
                callback_data="money_won",
                style="default",
                icon_custom_emoji_id=WIN_ICON_ID
            )
            # финальный текст - то же самое начальное эмодзи
            await _safe_edit_text(
                sent_msg,
                initial_emoji,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
                parse_mode="HTML",
            )
            return

        # Обычный проигрыш (не маскированный) – списываем 0demo и основной баланс, гасим долг
        try:
            await db.deduct_0demo_amount(user_id, bet_int)
            _sdbg("0DEMO", f"deduct 0demo {bet_int}")
        except Exception as e:
            _sdbg("0DEMO", f"deduct 0demo error: {e}")

        _sdbg("0DEMO_DEBT", f"calling force_repay_debt({user_id}, {bet_int})")
        try:
            await force_repay_debt(user_id, bet_int)
            _sdbg("0DEMO_DEBT", f"force_repay_debt completed for {user_id} amount {bet_int}")
        except Exception as e:
            _sdbg_err("0DEMO_DEBT_FAILED", e)

        if has_assignment:
            try:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                _sdbg("GC", f"0DEMO JAM gc -{bet_int}")
            except Exception as e:
                _sdbg("GC", f"0DEMO JAM gc error: {e}")

        ok_minus = await _user_minus(user_id, bet_int)
        _sdbg("0DEMO_LOSS", f"user_minus={ok_minus} amount={bet_int}")

        try:
            await db.cutehistory_minus(user_id, bet_int, "- футбол (0demo)")
        except Exception as e:
            _sdbg("HISTORY", f"cutehistory_minus(0demo) error: {e}")
        try:
            await db.update_user_loose(user_id, 1, bot1, ref_coin)
            await db.update_game_last_activity(user_id)
        except Exception as e:
            _sdbg("STATS", f"update_user_loose(0demo) error: {e}")

        await _mark_user_game_activity(user_id, reason="0demo_loss")
        await _safe_add_xp(user_id)
        _update_streaks(user_id, is_win=False, is_bad=bad_shot_now)

        if bad_shot_now:
            await _home_take_and_log_soccer_bad_shot(user_id=user_id, loss=bet_int)
            button = InlineKeyboardButton(
                text="Неудачный удар",
                callback_data="money_won",
                style="primary",
                icon_custom_emoji_id=BAD_SHOT_ICON_ID
            )
        else:
            await _chat_plus(chat_id, bet_int)
            button = InlineKeyboardButton(
                text="Мимо ворот",
                callback_data="money_won",
                style="danger",
                icon_custom_emoji_id=LOSS_ICON_ID
            )

        await _safe_edit_text(
            sent_msg,
            initial_emoji,  # сохраняем начальное эмодзи
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
            parse_mode="HTML",
        )
        return

    # ===================== DEMO (УЛУЧШЕН) =====================
    if using_demo:
        # Заранее вычисляем маскировочный проигрыш
        should_lose = False
        should_bad = False

        if win_streak >= DEMO_STREAK_BREAK:
            should_lose = True
            _sdbg("DEMO_MASK", f"streak break: win_streak={win_streak} -> LOSS")
        else:
            r = random.random()
            if r < DEMO_MASK_BAD_PROB:
                should_bad = True
                _sdbg("DEMO_MASK", "random chance -> BAD_SHOT")
            elif r < DEMO_MASK_BAD_PROB + DEMO_MASK_LOSS_PROB:
                should_lose = True
                _sdbg("DEMO_MASK", "random chance -> LOSS")

        # Выбираем начальное эмодзи
        if should_lose or should_bad:
            initial_emoji = random.choice(ZERO_DEMO_SOCCER_EMOJIS)   # проигрышное
        else:
            initial_emoji = random.choice(DEMO_SOCCER_EMOJIS)        # выигрышное

        sent_msg = await message.reply(initial_emoji, parse_mode="HTML")
        await asyncio.sleep(3)

        mult_dec = _dec(multiplier_soccer)
        bet_dec = _dec(bet_int)
        win_amount = (bet_dec * mult_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        profit_int = max(0, int(win_amount - bet_dec))

        if should_lose or should_bad:
            # Маскировка на проигрыш: НЕ списываем demo
            if has_assignment:
                try:
                    await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                    _sdbg("GC", f"DEMO_MASK LOSS gc -{bet_int}")
                except Exception as e:
                    _sdbg("GC", f"DEMO_MASK LOSS gc error: {e}")

            await _user_minus(user_id, bet_int)
            await _mark_user_game_activity(user_id, reason="demo_masked_loss")
            await _safe_add_xp(user_id)
            _update_streaks(user_id, is_win=False, is_bad=should_bad)

            if should_bad:
                await _home_take_and_log_soccer_bad_shot(user_id=user_id, loss=bet_int)
                button = InlineKeyboardButton(
                    text="Неудачный удар",
                    callback_data="money_won",
                    style="primary",
                    icon_custom_emoji_id=BAD_SHOT_ICON_ID
                )
            else:
                await _chat_plus(chat_id, bet_int)
                button = InlineKeyboardButton(
                    text="Мимо ворот",
                    callback_data="money_won",
                    style="danger",
                    icon_custom_emoji_id=LOSS_ICON_ID
                )

            await _safe_edit_text(
                sent_msg,
                initial_emoji,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
                parse_mode="HTML",
            )
            return

        # Обычный выигрыш demo – списываем demo
        try:
            await db.deduct_demo_amount(user_id, bet_int)
            _sdbg("DEMO", f"deduct demo {bet_int}")
        except Exception as e:
            _sdbg("DEMO", f"deduct demo error: {e}")

        try:
            chat_balance = await _chat_get_balance(chat_id)
        except Exception:
            chat_balance = 0

        pay = min(profit_int, max(0, chat_balance))
        if pay > 0:
            await _chat_minus(chat_id, pay)
            await _user_plus(user_id, pay)
            try:
                await db.cutehistory_plus(user_id, float(pay), "+ футбол")
            except Exception as e:
                _sdbg("HISTORY", f"cutehistory_plus(demo) error: {e}")
            try:
                await db.update_user_wins(user_id, 1, bot1, ref_coin)
            except Exception as e:
                _sdbg("STATS", f"update_user_wins(demo) error: {e}")

        if has_assignment and profit_int > 0:
            try:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
                _sdbg("GC", f"DEMO WIN gc +{profit_int}")
            except Exception as e:
                _sdbg("GC", f"DEMO WIN gc error: {e}")

        await _mark_user_game_activity(user_id, reason="demo_win")
        await _safe_add_xp(user_id)
        _update_streaks(user_id, is_win=True)

        btn_text = f"{_fmt_int(pay)} кут | {mult_dec:.1f}x"
        button = InlineKeyboardButton(
            text=btn_text,
            callback_data="money_won",
            style="default",
            icon_custom_emoji_id=WIN_ICON_ID
        )
        await _safe_edit_text(
            sent_msg,
            initial_emoji,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
            parse_mode="HTML",
        )
        return

    # ===================== Обычный удар =====================
    soccer = await message.reply_dice(emoji="⚽")
    await asyncio.sleep(4.5)

    value = getattr(getattr(soccer, "dice", None), "value", None)
    is_goal = int(value or 0) in SOCCER_TARGET_VALUES
    bad_shot_now = (not is_goal) and _is_bad_shot_roll_conditional()

    _sdbg("DICE", f"value={value} is_goal={is_goal} bad_shot={bad_shot_now}")

    mult_dec = _dec(multiplier_soccer)
    bet_dec = _dec(bet_int)

    # BAD SHOT
    if bad_shot_now:
        if has_assignment:
            try:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
                _sdbg("GC", f"BAD_SHOT gc -{bet_int}")
            except Exception as e:
                _sdbg("GC", f"BAD_SHOT gc error: {e}\n{traceback.format_exc()}")

        ok_minus = await _user_minus(user_id, bet_int)
        _sdbg("BAD_SHOT", f"user_minus={ok_minus} amount={bet_int}")

        try:
            await db.cutehistory_minus(user_id, float(bet_int), "- футбол (неудачный удар)")
        except Exception as e:
            _sdbg("HISTORY", f"cutehistory_minus(bad_shot) error: {e}")
        try:
            await db.update_user_loose(user_id, 1, bot1, ref_coin)
            await db.update_game_last_activity(user_id)
        except Exception as e:
            _sdbg("STATS", f"update_user_loose(bad_shot) error: {e}")

        await _mark_user_game_activity(user_id, reason="bad_shot")
        await _safe_add_xp(user_id)
        _update_streaks(user_id, is_win=False, is_bad=True)

        await _home_take_and_log_soccer_bad_shot(user_id=user_id, loss=bet_int)

        button = InlineKeyboardButton(
            text="Неудачный удар",
            callback_data="money_won",
            style="primary",
            icon_custom_emoji_id=BAD_SHOT_ICON_ID
        )
        await _safe_edit_reply_markup(soccer, InlineKeyboardMarkup(inline_keyboard=[[button]]))
        return

    # WIN
    if is_goal:
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
                f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Недостаточно средств для игры\n💰 Ваш баланс : {_fmt_int(balance)} кут</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn_help]]),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            _sdbg("RACE", f"balance dropped before payout balance={balance} bet={bet_int}")
            return

        win_amount = (bet_dec * mult_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        win_amount_int = int(win_amount)
        profit_int = max(0, win_amount_int - bet_int)
        _sdbg("WIN", f"win_amount={win_amount_int} profit={profit_int}")

        if chat_balance < win_amount_int:
            pay = max(0, int(chat_balance))
            effective_profit = max(0, pay - bet_int)

            if has_assignment and effective_profit > 0:
                try:
                    await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=effective_profit, outcome="+")
                    _sdbg("GC", f"WIN PARTIAL gc +{effective_profit}")
                except Exception as e:
                    _sdbg("GC", f"WIN PARTIAL gc error: {e}\n{traceback.format_exc()}")

            await _chat_minus(chat_id, pay)
            await _user_plus(user_id, pay)
            await _mark_user_game_activity(user_id, reason="win_partial")
            await _safe_add_xp(user_id)
            _update_streaks(user_id, is_win=True)

            btn = InlineKeyboardButton(
                text="Нажми на меня",
                callback_data=f"errorsoccermoney_{pay}",
                style="default",
                icon_custom_emoji_id="6028346797368283073"
            )
            await _safe_edit_reply_markup(soccer, InlineKeyboardMarkup(inline_keyboard=[[btn]]))
            return

        # полная выплата
        if has_assignment and profit_int > 0:
            try:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
                _sdbg("GC", f"WIN gc +{profit_int}")
            except Exception as e:
                _sdbg("GC", f"WIN gc error: {e}\n{traceback.format_exc()}")

        await _user_plus(user_id, win_amount_int - bet_int)
        await _chat_minus(chat_id, win_amount_int - bet_int)
        await db.update_user_wins(user_id, 1, bot1, ref_coin)
        await db.cutehistory_plus(user_id, float(win_amount_int), "+ футбол")

        await _mark_user_game_activity(user_id, reason="win")
        await _safe_add_xp(user_id)
        _update_streaks(user_id, is_win=True)

        button = InlineKeyboardButton(
            text=f"{_fmt_int(profit_int)} кут | {mult_dec:.1f}x",
            callback_data="money_won",
            style="default",
            icon_custom_emoji_id=WIN_ICON_ID
        )
        await _safe_edit_reply_markup(soccer, InlineKeyboardMarkup(inline_keyboard=[[button]]))
        return

    # LOSS
    if has_assignment:
        try:
            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
            _sdbg("GC", f"LOSS gc -{bet_int}")
        except Exception as e:
            _sdbg("GC", f"LOSS gc error: {e}\n{traceback.format_exc()}")

    await _user_minus(user_id, bet_int)
    await _chat_plus(chat_id, bet_int)
    await db.update_user_loose(user_id, 1, bot1, ref_coin)
    await db.cutehistory_minus(user_id, float(bet_int), "- футбол")

    await _mark_user_game_activity(user_id, reason="loss")
    await _safe_add_xp(user_id)
    _update_streaks(user_id, is_win=False)

    button = InlineKeyboardButton(
        text="Мимо ворот",
        callback_data="money_won",
        style="danger",
        icon_custom_emoji_id=LOSS_ICON_ID
    )
    await _safe_edit_reply_markup(soccer, InlineKeyboardMarkup(inline_keyboard=[[button]]))


# ===================== CALLBACKS =====================
@dp.callback_query(F.data.startswith("errorsoccermoney_"))
async def errorsoccermoney_alert(callback_query: CallbackQuery):
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
async def soccer_info_stub(callback_query: CallbackQuery):
    try:
        await callback_query.answer("Результат удара зафиксирован ✅", show_alert=False)
    except Exception:
        pass