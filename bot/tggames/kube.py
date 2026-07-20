# -*- coding: utf-8 -*-
"""
🎲 Куб (угадайка): "куб (ставка) (число 1..6)"

Режимы:
- Обычный: случайный исход (угадал / промах / кубик потерялся)
- Demo: гарантированное угадывание, ставка с demo‑баланса,
        маскировка на проигрыш при частых победах
- 0demo: гарантированный проигрыш, ставка с 0demo‑баланса,
         маскировка на выигрыш при частых проигрышах

✅ Полная интеграция Jericho, серии, force_repay_debt.
"""

from main import *  # noqa: F401,F403

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

last_kube_time: Dict[int, Dict[int, float]] = LazyGameStore("last_kube_time")
_kube_streaks: Dict[int, Dict[str, int]] = LazyGameStore("kube_streaks")

KUBE_DEBUG = True

# Иконки
KUBE_WIN_EMOJI_ID = "5890971177484029249"   # выигрыш
KUBE_LOSS_ICON_ID = "4956499161319998529"   # промах
KUBE_LOST_ICON_ID = "5890971177484029249"   # кубик потерялся

# Эмодзи чисел (премиум) для demo/0demo
DEMO_KUBE_EMOJIS = {
    1: "<tg-emoji emoji-id='5890885351152553528'>1️⃣</tg-emoji>",
    2: "<tg-emoji emoji-id='5891165086667509023'>2️⃣</tg-emoji>",
    3: "<tg-emoji emoji-id='5888803657813594137'>3️⃣</tg-emoji>",
    4: "<tg-emoji emoji-id='5890915785290813565'>4️⃣</tg-emoji>",
    5: "<tg-emoji emoji-id='5891205850202115734'>5️⃣</tg-emoji>",
    6: "<tg-emoji emoji-id='5891226736628076283'>6️⃣</tg-emoji>",
}

# Маскировочные механики
DEMO_MASK_LOSS_PROB = 0.45
DEMO_STREAK_BREAK = 3          # после скольких побед подряд принудительно проигрыш
ZERO_MASK_WIN_PROB = 0.12
ZERO_STREAK_BREAK = 3          # после скольких проигрышей подряд принудительно выигрыш

# Вероятность «кубик потерялся» (только при промахе)
try:
    KUBE_LOST_CHANCE = Decimal(str(KUBE_LOST_CHANCE))
except NameError:
    KUBE_LOST_CHANCE = Decimal("0.05")

KUBE_MISS_PROBABILITY = Decimal(5) / Decimal(6)
if KUBE_MISS_PROBABILITY > 0:
    KUBE_LOST_CONDITIONAL = min(KUBE_LOST_CHANCE / KUBE_MISS_PROBABILITY, Decimal(1))
else:
    KUBE_LOST_CONDITIONAL = Decimal(0)


# ===================== DEBUG =====================
def _kdbg(tag: str, msg: str) -> None:
    if not KUBE_DEBUG:
        return
    try:
        print(f"[КУБ][{tag}] {msg}", flush=True)
    except Exception:
        pass

def _kdbg_err(tag: str, err: Exception) -> None:
    if not KUBE_DEBUG:
        return
    try:
        print(f"[КУБ][ERROR][{tag}] {err}", flush=True)
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

def _is_cube_lost_roll_raw() -> bool:
    try:
        r = Decimal(str(random.random()))
        lost = r < KUBE_LOST_CHANCE
        _kdbg("LOST_RAW", f"rand={r} chance={KUBE_LOST_CHANCE} lost={lost}")
        return lost
    except Exception:
        return False

def _is_cube_lost_roll_conditional() -> bool:
    try:
        r = Decimal(str(random.random()))
        lost = r < KUBE_LOST_CONDITIONAL
        _kdbg("LOST_COND", f"rand={r} cond={KUBE_LOST_CONDITIONAL} lost={lost}")
        return lost
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
    chat_map = last_kube_time.setdefault(chat_id, {})
    last_usage = float(chat_map.get(user_id, 0.0) or 0.0)
    left = duration - (now - last_usage)
    return int(left) if left > 0 else 0

def _cooldown_mark(chat_id: int, user_id: int) -> None:
    chat_map = last_kube_time.setdefault(chat_id, {})
    chat_map[user_id] = time.time()
    _save_safe(last_kube_time)

def _get_streaks(user_id: int) -> Dict[str, int]:
    streaks = _kube_streaks.get(user_id)
    if streaks is None:
        streaks = {"win_streak": 0, "lose_streak": 0}
        _kube_streaks[user_id] = streaks
        _save_safe(_kube_streaks)
    return streaks

def _update_streaks(user_id: int, is_win: bool, is_lost: bool = False) -> None:
    streaks = _get_streaks(user_id)
    if is_lost:
        streaks["win_streak"] = 0
        streaks["lose_streak"] = 0
    elif is_win:
        streaks["win_streak"] = streaks.get("win_streak", 0) + 1
        streaks["lose_streak"] = 0
    else:
        streaks["lose_streak"] = streaks.get("lose_streak", 0) + 1
        streaks["win_streak"] = 0
    _kube_streaks[user_id] = streaks
    _save_safe(_kube_streaks)
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

async def _send_invoice_later(message: Message, user_id: int, stars_amount: str, delay: float) -> None:
    try:
        await asyncio.sleep(max(0.0, float(delay)))
        ctx = pending_context.get(user_id)
        if ctx and not ctx.get("sent"):
            invoice_message = await send_invoice_to_user(message, stars_amount)
            pending_context[user_id]["manual_message_id"] = getattr(invoice_message, "message_id", None)
            _kdbg("DONATE", f"invoice sent user_id={user_id} stars={stars_amount}")
    except Exception as e:
        _kdbg("DONATE", f"invoice later error: {e}")


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

async def _safe_get_balances(user_id: int, chat_id: int) -> tuple[int, int]:
    try:
        balance = int(await db.get_user_balance(user_id) or 0)
    except Exception as e:
        balance = 0
        _kdbg("DB", f"Ошибка get_user_balance({user_id}): {e}")
    try:
        chat_balance = await _chat_get_balance(chat_id)
    except Exception as e:
        chat_balance = 0
        _kdbg("DB", f"Ошибка get_chat_balance({chat_id}): {e}")
    return balance, chat_balance


# ===================== ЛОГ "ДОМОЙ" =====================
async def _home_take_and_log_kube_lost(*, user_id: int, loss: int) -> None:
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
        emoji_html = '<tg-emoji emoji-id="5384474763827620477">🎲</tg-emoji>'

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
                        text="Куб",
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
                disable_web_page_preview=True,
            )
        except Exception:
            # Fallback: обычный HTML-текст без кнопок
            await bot1.send_message(
                int(TECH_CHAT_ID),
                f"🎲 Куб [Кубик потерялся]\n<blockquote><b>+ {_fmt_int(loss)} на чёрный рынок</b></blockquote>\n<blockquote><b>{_fmt_int(chat_balance)} кут доступно для выкупов</b></blockquote>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

    except Exception as e:
        _kdbg_err("HOME_LOST_LOG", e)


# ===================== GC / ЧЕЛЛЕНДЖ =====================
async def _load_gc_state_for_user_kube(user_id: int) -> dict:
    has_assignment = False
    is_free = False
    current_two = 0
    target_amount = 0
    max_bet = kube_BASE_MAX_BET
    try:
        gc_bet_limit = await db.gc_get_bet_limit_for_user(user_id)
    except Exception as e:
        gc_bet_limit = None
        _kdbg("GC_LIMIT", f"Ошибка gc_get_bet_limit_for_user({user_id}): {e}")
    if gc_bet_limit is not None:
        try:
            gc_bet_limit_int = int(gc_bet_limit)
            if gc_bet_limit_int > 0:
                max_bet = min(max_bet, gc_bet_limit_int)
        except Exception as e:
            _kdbg("GC_LIMIT", f"Ошибка конвертации лимита {gc_bet_limit!r}: {e}")
    try:
        assignment = await db.get_active_gc_assignment(user_id)
    except Exception as e:
        assignment = None
        _kdbg("GC_STATE", f"Ошибка get_active_gc_assignment({user_id}): {e}")
    if assignment and str(assignment.get("status") or "").lower() == "active":
        has_assignment = True
        try:
            is_free = bool(await db.gc_active_is_free(user_id))
        except Exception as e:
            is_free = False
            _kdbg("GC_STATE", f"Ошибка gc_active_is_free({user_id}): {e}")
        try:
            current_two_val = await db.gc_get_current_two_balance(user_id)
            current_two = int(current_two_val or 0)
        except Exception as e:
            current_two = 0
            _kdbg("GC_STATE", f"Ошибка gc_get_current_two_balance({user_id}): {e}")
        try:
            target_amount = int(assignment.get("target_amount") or 0)
        except Exception:
            target_amount = 0
        _kdbg("GC_STATE", f"ACTIVE=1 FREE={is_free} TWO={current_two} TARGET={target_amount} MAX_BET={max_bet}")
    else:
        _kdbg("GC_STATE", "ACTIVE=0 (нет активного задания)")
    return {
        "has_assignment": has_assignment,
        "is_free": is_free,
        "current_two": current_two,
        "target_amount": target_amount,
        "max_bet": max_bet,
    }


# ===================== FREE-РЕЖИМ =====================
async def _tgkube_free_game(message: Message, user_id: int, chat_id: int, bet_int: int, guess: int, gc_state: dict):
    left = _cooldown_left(chat_id, user_id)
    if left > 0:
        await message.reply(f"<tg-emoji emoji-id='5253709334835128381'>⌚️</tg-emoji> <b>Подождите {left} сек</b>", parse_mode="HTML")
        return
    _cooldown_mark(chat_id, user_id)

    current_two = int(gc_state.get("current_two") or 0)
    target_amount = int(gc_state.get("target_amount") or 0)
    if bet_int > current_two:
        progress = f"{current_two}/{target_amount}" if target_amount > 0 else f"{current_two}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Баланс челленджа: {progress} кут", callback_data="noop")],
            [InlineKeyboardButton(text="Недостаточно виртуальных кут", callback_data="noop")],
        ])
        await message.reply("😓", reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        return

    dice_msg = await message.reply_dice(emoji="🎲")
    await asyncio.sleep(3.8)
    rolled = int(getattr(getattr(dice_msg, "dice", None), "value", 1) or 1)

    mult_dec = _dec(KUBE_MULTIPLIER)
    bet_dec = _dec(bet_int)

    if rolled == guess:
        win_amount = (bet_dec * mult_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        profit = max(Decimal(0), win_amount - bet_dec)
        profit_int = int(profit)
        if profit_int > 0:
            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
        await _mark_user_game_activity(user_id, reason="win_free")
        await _safe_add_xp(user_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"+{_fmt_int(profit_int)} кут | {mult_dec:.1f}x", callback_data="win",
                                  style="default", icon_custom_emoji_id=KUBE_WIN_EMOJI_ID)
        ]])
        await _safe_edit_reply_markup(dice_msg, kb)
        return

    lost_now = _is_cube_lost_roll_conditional()
    _kdbg("FREE", f"rolled={rolled} guess={guess} lost={lost_now}")

    if lost_now:
        await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
        await _mark_user_game_activity(user_id, reason="lost_free")
        await _safe_add_xp(user_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Кубик потерялся", callback_data="money_won", style="primary",
                                  icon_custom_emoji_id=KUBE_LOST_ICON_ID)
        ]])
    else:
        await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
        await _mark_user_game_activity(user_id, reason="loss_free")
        await _safe_add_xp(user_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Промах", callback_data="lose", style="danger",
                                  icon_custom_emoji_id=KUBE_LOSS_ICON_ID)
        ]])
    await _safe_edit_reply_markup(dice_msg, kb)


# ===================== ОСНОВНАЯ ИГРА КУБ =====================
@dp.message(lambda message: bool(message.text) and message.text.split()[0].lower() in ("куб", "кубик"))
async def tgkube(message: Message):
    parts = (message.text or "").strip().split()
    if message.chat.type == "private":
        await message.reply("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В эту игру можно играть только в публичных группах.</b>",
                            parse_mode="HTML", disable_web_page_preview=True)
        return
    if len(parts) == 2:
        await message.reply(
            "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Не хватает числа!</b>\n"
            "✅ <b>Формат:</b> куб (ставка) (число от 1 до 6)\nПример: <code>куб 10 4</code>",
            parse_mode="HTML", disable_web_page_preview=True)
        return
    if len(parts) != 3:
        await message.reply("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Формат: куб (ставка) (число от 1 до 6)</b>",
                            parse_mode="HTML", disable_web_page_preview=True)
        return
    try:
        bet_int = _parse_bet_to_int(parts[1])
        guess = int(parts[2])
    except Exception:
        await message.reply("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Ставка и число должны быть числами.</b>", parse_mode="HTML")
        return
    if bet_int <= 0:
        await message.reply("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Ставка должна быть больше нуля.</b>", parse_mode="HTML")
        return
    if bet_int < kube_MIN_BET:
        await message.reply(f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Минимальная ставка {kube_MIN_BET} кут.</b>", parse_mode="HTML")
        return
    if guess < 1 or guess > 6:
        await message.reply("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Число должно быть от 1 до 6</b>", parse_mode="HTML")
        return

    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)
    _kdbg("START", f"user={user_id} chat={chat_id} bet={bet_int} guess={guess}")

    # Инициализация новичка и приветственный бонус
    try:
        if await db.get_newbie_expires_at(user_id) is None:
            from datetime import datetime, timedelta, timezone
            expires = datetime.now(timezone.utc) + timedelta(hours=random.uniform(0.5, 24.0))
            await db.set_newbie_expires_at(user_id, expires)
            _kdbg("NEWBIE", f"newbie expires set {expires}")
    except Exception as e:
        _kdbg("NEWBIE", f"error {e}")
    await welcome_back_gift(user_id)

    gc_state = await _load_gc_state_for_user_kube(user_id)
    has_assignment = bool(gc_state.get("has_assignment"))
    is_free = bool(gc_state.get("is_free"))
    max_bet_gc = int(gc_state.get("max_bet") or kube_BASE_MAX_BET)

    if bet_int > kube_BASE_MAX_BET:
        await message.reply(f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Максимальная ставка {_fmt_int(kube_BASE_MAX_BET)} кут.</b>", parse_mode="HTML")
        return
    if bet_int > max_bet_gc:
        await message.reply(f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Максимальная ставка для этой игры: {_fmt_int(max_bet_gc)} кут.</b>", parse_mode="HTML")
        return

    # ---------- DEMO / 0DEMO с Jericho ----------
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

        decision = await jericho_check(user_id, bet_int, game_name="куб")
        jericho_action = decision.get("action", "normal")
        _kdbg("JERICHO", f"action={jericho_action} reason={decision.get('reason','')}")

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

        _kdbg("MODE", f"final: demo={using_demo} 0demo={using_0demo}")

    if has_assignment and is_free:
        await _tgkube_free_game(message, user_id, chat_id, bet_int, guess, gc_state)
        return

    left = _cooldown_left(chat_id, user_id)
    if left > 0:
        await message.reply(f"<tg-emoji emoji-id='5253709334835128381'>⌚️</tg-emoji> <b>Подождите {left} сек</b>", parse_mode="HTML")
        return
    _cooldown_mark(chat_id, user_id)

    balance, chat_balance = await _safe_get_balances(user_id, chat_id)

    if not using_demo and not using_0demo and bet_int > balance:
        bet_dec = _dec(bet_int)
        stars = bet_dec * _dec(donate_bet)
        stars_q = stars.quantize(Decimal("1.000000"), rounding=ROUND_HALF_UP).normalize()
        stars_amount = format(stars_q, "f")
        try:
            bot_username = await get_bot_username_by_token(TOKEN)
        except Exception:
            bot_username = "CuteGamingBot"
        pending_context[user_id] = {"stars_amount": stars_amount, "sent": False}
        rows = [
            [InlineKeyboardButton(text=f"💫 Купить {_fmt_int(bet_int)} кут 💰",
                                  url=f"https://t.me/{bot_username}?start=insert_{stars_amount}_+")],
            [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")],
        ]
        if has_assignment and not is_free:
            rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
            rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])
        await message.reply("<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                            parse_mode="HTML", disable_web_page_preview=True)
        asyncio.create_task(_send_invoice_later(message, user_id, stars_amount, delay=timeoutdonate))
        return

    if bet_int > chat_balance:
        rows = []
        if has_assignment and not is_free:
            rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
            rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])
        await message.reply("<tg-emoji emoji-id='5253709334835128381'>⌚️</tg-emoji> <b>В группе недостаточно средств для игры.</b>",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None,
                            parse_mode="HTML", disable_web_page_preview=True)
        return

    # Загружаем серии
    streaks = _get_streaks(user_id)
    win_streak = streaks.get("win_streak", 0)
    lose_streak = streaks.get("lose_streak", 0)

    # ===================== 0DEMO (УЛУЧШЕН) =====================
    if using_0demo:
        # Заранее вычисляем маскировку: принудительный выигрыш при частых проигрышах
        should_win = False
        if lose_streak >= ZERO_STREAK_BREAK:
            should_win = True
            _kdbg("0DEMO_MASK", f"streak break: lose_streak={lose_streak} -> WIN")
        elif random.random() < ZERO_MASK_WIN_PROB:
            should_win = True
            _kdbg("0DEMO_MASK", "random chance -> WIN")

        # Выбираем начальное эмодзи: при маскировке – число догадки, иначе другое число
        if should_win:
            displayed_number = guess
        else:
            other_numbers = [n for n in range(1, 7) if n != guess]
            displayed_number = random.choice(other_numbers)

        initial_emoji = DEMO_KUBE_EMOJIS[displayed_number]
        sent_msg = await message.reply(initial_emoji, parse_mode="HTML", disable_web_page_preview=True)
        await asyncio.sleep(1.0)

        if should_win:
            # Маскировка: выигрыш, не списываем 0demo, не гасим долг
            mult_dec = _dec(KUBE_MULTIPLIER)
            bet_dec = _dec(bet_int)
            win_amount = (bet_dec * mult_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            profit_int = max(0, int(win_amount - bet_dec))
            chat_balance_now = await _chat_get_balance(chat_id)
            pay = min(profit_int, max(0, chat_balance_now))
            if pay > 0:
                await _chat_minus(chat_id, pay)
                await _user_plus(user_id, pay)
                try:
                    await db.cutehistory_plus(user_id, float(pay), "+ куб (0demo маскировка)")
                except Exception as e:
                    _kdbg("HISTORY", f"cutehistory_plus(0demo_mask) error: {e}")
                try:
                    await db.update_user_wins(user_id, 1, bot1, ref_coin)
                except Exception as e:
                    _kdbg("STATS", f"update_user_wins(0demo_mask) error: {e}")
            if has_assignment and profit_int > 0:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
            await _mark_user_game_activity(user_id, reason="0demo_masked_win")
            await _safe_add_xp(user_id)
            _update_streaks(user_id, is_win=True)

            btn_text = f"+{_fmt_int(pay)} кут | {mult_dec:.1f}x"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=btn_text, callback_data="win", style="default",
                                      icon_custom_emoji_id=KUBE_WIN_EMOJI_ID)
            ]])
            await _safe_edit_text(sent_msg, initial_emoji, reply_markup=kb, parse_mode="HTML")
            return

        # Реальный проигрыш: списываем 0demo, гасим долг
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

        lost_now = _is_cube_lost_roll_raw()

        if lost_now:
            if has_assignment:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
            await _user_minus(user_id, bet_int)
            await _mark_user_game_activity(user_id, reason="lost_0demo")
            await _safe_add_xp(user_id)
            try:
                await db.cutehistory_minus(user_id, bet_int, "- куб (0demo lost)")
            except Exception:
                pass
            try:
                await db.update_user_loose(user_id, 1, bot1, ref_coin)
                await db.update_game_last_activity(user_id)
            except Exception:
                pass
            await _home_take_and_log_kube_lost(user_id=user_id, loss=bet_int)
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Кубик потерялся", callback_data="money_won", style="primary",
                                      icon_custom_emoji_id=KUBE_LOST_ICON_ID)
            ]])
        else:
            await _user_minus(user_id, bet_int)
            await _chat_plus(chat_id, bet_int)
            await _mark_user_game_activity(user_id, reason="loss_0demo")
            await _safe_add_xp(user_id)
            try:
                await db.cutehistory_minus(user_id, bet_int, "- куб (0demo loss)")
            except Exception:
                pass
            try:
                await db.update_user_loose(user_id, 1, bot1, ref_coin)
                await db.update_game_last_activity(user_id)
            except Exception:
                pass
            if has_assignment:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Промах", callback_data="lose", style="danger",
                                      icon_custom_emoji_id=KUBE_LOSS_ICON_ID)
            ]])
        _update_streaks(user_id, is_win=False, is_lost=lost_now)
        await _safe_edit_text(sent_msg, initial_emoji, reply_markup=kb, parse_mode="HTML")
        return

    # ===================== DEMO (УЛУЧШЕН) =====================
    if using_demo:
        # Заранее вычисляем маскировку: принудительный проигрыш при частых победах
        should_lose = False
        if win_streak >= DEMO_STREAK_BREAK:
            should_lose = True
            _kdbg("DEMO_MASK", f"streak break: win_streak={win_streak} -> LOSS")
        elif random.random() < DEMO_MASK_LOSS_PROB:
            should_lose = True
            _kdbg("DEMO_MASK", "random chance -> LOSS")

        # Выбираем начальное эмодзи: при проигрыше – другое число, иначе загаданное
        if should_lose:
            other_numbers = [n for n in range(1, 7) if n != guess]
            displayed_number = random.choice(other_numbers)
        else:
            displayed_number = guess

        initial_emoji = DEMO_KUBE_EMOJIS[displayed_number]
        sent_msg = await message.reply(initial_emoji, parse_mode="HTML", disable_web_page_preview=True)
        await asyncio.sleep(1.0)

        mult_dec = _dec(KUBE_MULTIPLIER)
        bet_dec = _dec(bet_int)

        if should_lose:
            # Маскировочный проигрыш: списываем с основного, demo не трогаем
            if has_assignment:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
            await _user_minus(user_id, bet_int)
            await _chat_plus(chat_id, bet_int)
            await _mark_user_game_activity(user_id, reason="demo_masked_loss")
            await _safe_add_xp(user_id)
            _update_streaks(user_id, is_win=False)

            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Промах", callback_data="lose", style="danger",
                                      icon_custom_emoji_id=KUBE_LOSS_ICON_ID)
            ]])
            await _safe_edit_text(sent_msg, initial_emoji, reply_markup=kb, parse_mode="HTML")
            return

        # Реальный выигрыш demo: списываем demo
        try:
            await db.deduct_demo_amount(user_id, bet_int)
            _kdbg("DEMO", f"deduct demo {bet_int}")
        except Exception as e:
            _kdbg("DEMO", f"deduct demo error: {e}")

        win_amount = (bet_dec * mult_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        profit_int = max(0, int(win_amount - bet_dec))
        chat_balance_now = await _chat_get_balance(chat_id)
        pay = min(profit_int, max(0, chat_balance_now))
        if pay > 0:
            await _chat_minus(chat_id, pay)
            await _user_plus(user_id, pay)
            try:
                await db.cutehistory_plus(user_id, float(pay), "+ куб угадайка")
            except Exception as e:
                _kdbg("HISTORY", f"cutehistory_plus(demo) error: {e}")
            try:
                await db.update_user_wins(user_id, 1, bot1, ref_coin)
            except Exception as e:
                _kdbg("STATS", f"update_user_wins(demo) error: {e}")
        if has_assignment and profit_int > 0:
            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
        await _mark_user_game_activity(user_id, reason="demo_win")
        await _safe_add_xp(user_id)
        _update_streaks(user_id, is_win=True)

        btn_text = f"+{_fmt_int(pay)} кут | {mult_dec:.1f}x"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=btn_text, callback_data="win", style="default",
                                  icon_custom_emoji_id=KUBE_WIN_EMOJI_ID)
        ]])
        await _safe_edit_text(sent_msg, initial_emoji, reply_markup=kb, parse_mode="HTML")
        return

    # ---------------- Обычный бросок dice ----------------
    dice_msg = await message.reply_dice(emoji="🎲")
    await asyncio.sleep(3.8)
    rolled = int(getattr(getattr(dice_msg, "dice", None), "value", 1) or 1)

    mult_dec = _dec(KUBE_MULTIPLIER)
    bet_dec = _dec(bet_int)

    if rolled == guess:   # WIN
        balance, chat_balance = await _safe_get_balances(user_id, chat_id)
        win_amount = (bet_dec * mult_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        win_amount_int = int(win_amount)
        profit_int = max(0, win_amount_int - bet_int)
        if chat_balance < profit_int:
            pay = max(0, int(chat_balance))
            if has_assignment and pay > 0:
                await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=pay, outcome="+")
            await _chat_minus(chat_id, pay)
            await _user_plus(user_id, pay)
            await _mark_user_game_activity(user_id, reason="win_partial")
            await _safe_add_xp(user_id)
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text="Нажми на меня", callback_data=f"errorkube_{pay}", style="default",
                icon_custom_emoji_id="6028346797368283073")]])
            await _safe_edit_reply_markup(dice_msg, kb)
            _update_streaks(user_id, is_win=True)
            return
        if has_assignment and profit_int > 0:
            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=profit_int, outcome="+")
        await _user_plus(user_id, win_amount_int - bet_int)
        await _chat_minus(chat_id, win_amount_int - bet_int)
        try:
            await db.cutehistory_plus(user_id, float(win_amount_int), "+ куб угадайка")
        except Exception:
            pass
        try:
            await db.update_user_wins(user_id, 1, bot1, ref_coin)
        except Exception:
            pass
        await _mark_user_game_activity(user_id, reason="win")
        await _safe_add_xp(user_id)
        _update_streaks(user_id, is_win=True)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"+{_fmt_int(profit_int)} кут | {mult_dec:.1f}x",
                                  callback_data="win", style="default",
                                  icon_custom_emoji_id=KUBE_WIN_EMOJI_ID)
        ]])
        await _safe_edit_reply_markup(dice_msg, kb)
        return

    # LOST / LOSS
    lost_now = _is_cube_lost_roll_conditional()
    _kdbg("ROLL", f"rolled={rolled} guess={guess} lost={lost_now}")

    if lost_now:
        if has_assignment:
            await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet_int, outcome="-")
        await _user_minus(user_id, bet_int)
        await _mark_user_game_activity(user_id, reason="lost")
        try:
            await db.cutehistory_minus(user_id, float(bet_int), "- куб (кубик потерялся)")
        except Exception:
            pass
        try:
            await db.update_user_loose(user_id, 1, bot1, ref_coin)
            await db.update_game_last_activity(user_id)
        except Exception:
            pass
        await _home_take_and_log_kube_lost(user_id=user_id, loss=bet_int)
        await _safe_add_xp(user_id)
        _update_streaks(user_id, is_win=False, is_lost=True)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Кубик потерялся", callback_data="money_won", style="primary",
                                  icon_custom_emoji_id=KUBE_LOST_ICON_ID)
        ]])
    else:
        await _user_minus(user_id, bet_int)
        await _mark_user_game_activity(user_id, reason="loss")
        await _chat_plus(chat_id, bet_int)
        try:
            await db.cutehistory_minus(user_id, float(bet_int), "- куб промах")
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
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Промах", callback_data="lose", style="danger",
                                  icon_custom_emoji_id=KUBE_LOSS_ICON_ID)
        ]])
    await _safe_edit_reply_markup(dice_msg, kb)


# ===================== CALLBACKS =====================
@dp.callback_query(F.data.startswith("errorkube_"))
async def errorkube_alert(callback_query: CallbackQuery):
    parts = (callback_query.data or "").split("_", 1)
    pay = parts[1] if len(parts) > 1 else "неизвестно"
    try:
        await callback_query.answer(f"💭 На балансе группы недостаточно кут для выплаты выигрыша\n💸 Баланс группы : {pay} кут",
                                    show_alert=True)
    except Exception:
        pass

@dp.callback_query(F.data.in_(["win", "lose", "money_won"]))
async def kube_info_stub(callback_query: CallbackQuery):
    try:
        await callback_query.answer("Результат броска зафиксирован ✅", show_alert=False)
    except Exception:
        pass