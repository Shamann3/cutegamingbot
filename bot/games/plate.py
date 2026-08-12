# -*- coding: utf-8 -*-
"""
Плиты - полная версия с интеграцией Jericho и маскировочными механиками.
Локально:
  - demo-режим: при SAFE противоположная клетка принудительно показывается как TRAP (визуальная обманка),
    иногда подменяет SAFE → COLLAPSE (проигрыш) и прерывает серии побед.
  - 0demo-режим: иногда подменяет TRAP → SAFE (выигрыш) и прерывает серии проигрышей.
Долг списывается через force_repay_debt при любом проигрыше в 0demo-режиме.
"""

import asyncio
import random
import time
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, getcontext
from typing import Dict, Set, Tuple, List, Optional

from aiogram import types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from bot.games.group_only import reject_if_private_game
from main import (
    bot1, dp, db,
    TECH_CHAT_ID, create_user_link,
    user_message_plate, active_games_plate,
    pending_context, send_invoice_to_user,
    phrases12312,
    gc_process_bet, LazyGameStore
)

from bot.config.config import (
    TOKEN, timeoutdonate, donate_bet, ref_coin,
    PLATE_MIN_BET, PLATE_MAX_BET,
    PLATE_COLLAPSE_MIN, PLATE_COLLAPSE_MAX,
    _PLATE_MULT_DEFAULT
)
from bot.funcs.func import get_bot_username_by_token
from bot.funcs.tech_home_log import safe_send_tech_log

# Импорт функций Jericho
from main import (
    jericho_check, welcome_back_gift, newbie_safety_net, force_repay_debt
)

processed_actions_plate = LazyGameStore("processed_actions_plate")


async def _after_plate_closed(owner_id: int, msg_id: Optional[int] = None, chat_id=None):
    """Конец партии: safety-net + tip/личка онбординга."""
    await newbie_safety_net(owner_id)
    if chat_id is None:
        st = active_games_plate.get(owner_id) or {}
        if isinstance(st, dict):
            chat_id = st.get("chat_id")
            if msg_id is None:
                try:
                    msg_id = int(st.get("message_id") or 0) or None
                except Exception:
                    msg_id = None
    try:
        from bot.funcs.onboarding import onboarding_notify_game_finished
        await onboarding_notify_game_finished(owner_id, message_id=msg_id, chat_id=chat_id)
    except Exception as e:
        print(f"[PLATE] onboarding tip notify: {e!r}")

try:
    from main import get_random_eagle_emoji_id
except Exception:
    def get_random_eagle_emoji_id():
        return "6028346797368283073"

getcontext().prec = 28

_PLATE_MULT_DEFAULT2 = Decimal(_PLATE_MULT_DEFAULT)

SESSION_TTL = 20 * 60
USER_CLICK_COOLDOWN = 0.35
DEDUP_TTL = 60 * 60

RAN_EMOJIS = ("<tg-emoji emoji-id='5246916607833304803'>🌹</tg-emoji>",)
DEBUG_PLATE = True

# Маскировочные механики
DEMO_MASK_LOSS_PROB = 0.45               # вероятность подмены SAFE → COLLAPSE в demo-режиме
DEMO_STREAK_BREAK = 3                    # после скольких побед подряд принудительно COLLAPSE
ZERO_MASK_WIN_PROB = 0.12                # вероятность подмены TRAP → SAFE в 0demo-режиме
ZERO_STREAK_BREAK = 3                    # после скольких проигрышей подряд принудительно SAFE

def _load_plate_step_multiplier() -> Decimal:
    try:
        from bot.config.config import PLATE_STEP_MULTIPLIER as _CFG_PLATE_STEP_MULTIPLIER
        raw = str(_CFG_PLATE_STEP_MULTIPLIER).strip()
        x = Decimal(raw)
        if (not x.is_finite()) or x <= 0:
            return _PLATE_MULT_DEFAULT
        return x
    except Exception:
        return _PLATE_MULT_DEFAULT

PLATE_STEP_MULTIPLIER = _load_plate_step_multiplier()

# Клетки
CELL_HIDDEN = " "
CELL_SAFE = "ㅤ"
CELL_TRAP = "     "
CELL_COLLAPSE = "\u200b"

SHOW_SAFE = "5445256208992718797"
SHOW_TRAP = "5429624714173642686"
SHOW_COLLAPSE = "5309784543815827944"

# Отладка
def _ts() -> str: return time.strftime("%H:%M:%S", time.localtime())

def dbg(stage: str, **kw) -> None:
    if not DEBUG_PLATE: return
    parts = [f"[{_ts()}][PLATE][{stage}]"] + [f"{k}={v}" for k, v in kw.items()]
    try: print(" ".join(parts), flush=True)
    except: pass

def dbg_err(stage: str, err: Exception) -> None:
    if not DEBUG_PLATE: return
    try:
        import traceback
        print(f"[{_ts()}][PLATE][ERROR][{stage}] {err}\n{traceback.format_exc()}", flush=True)
    except: pass

def _debug_print_field_plate(field: List[List[str]], header: str = "") -> None:
    if not DEBUG_PLATE: return
    try:
        print(f"[{_ts()}][PLATE][FIELD] {header}")
        for r, row in enumerate(field):
            visual = []
            for cell in row:
                if cell == CELL_SAFE: visual.append("🟩")
                elif cell == CELL_TRAP: visual.append("🟥")
                elif cell == CELL_COLLAPSE: visual.append("🟨")
                elif cell == SHOW_SAFE: visual.append("🍀")
                elif cell == SHOW_TRAP: visual.append("💥")
                elif cell == SHOW_COLLAPSE: visual.append("🧱")
                else: visual.append("⬛")
            print(f"  {r+1:02d} | {'  '.join(visual)}")
        print(f"[{_ts()}][PLATE][FIELD_END]\n")
    except Exception as e:
        dbg_err("FIELD_PRINT_ERR", e)

# Внутренние состояния
_plate_session_locks: Dict[int, asyncio.Lock] = {}
_plate_inflight: Set[Tuple[int, int]] = set()
_last_click: Dict[int, float] = {}
_closed_msgs: Set[Tuple[int, int]] = set()
_user_start_locks: Dict[int, asyncio.Lock] = {}
_processed_ts: Dict[str, float] = {}

def _now_mono() -> float: return time.monotonic()

def _get_user_lock(user_id: int) -> asyncio.Lock:
    lock = _user_start_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_start_locks[user_id] = lock
    return lock

def _get_session_lock(msg_id: int) -> asyncio.Lock:
    lock = _plate_session_locks.get(msg_id)
    if lock is None:
        lock = asyncio.Lock()
        _plate_session_locks[msg_id] = lock
    return lock

# Утилиты
def _fmt_int(n: int) -> str:
    try: return "{:,.0f}".format(int(n)).replace(",", ".")
    except: return str(n)

def _safe_int(val, default=0) -> int:
    try: return int(val)
    except: return default

def _dec(val) -> Decimal: return Decimal(str(val))
def _str_dec(d: Decimal) -> str: return format(d, "f")

def _to_int_floor(x: Decimal) -> int:
    try:
        if x.is_nan(): return 0
    except: return 0
    return max(0, int(x.quantize(0, rounding=ROUND_DOWN)))

def _withdrawable_now(game_data: dict) -> int:
    if not game_data.get("first_success"): return 0
    bet = _dec(game_data.get("bet", 0))
    win = _dec(game_data.get("win_amount", bet))
    pure = win - bet
    return max(1, _to_int_floor(pure))

# Дедупликация
def _store_save_safe(store, stage: str):
    try:
        if hasattr(store, "save"): store.save()
    except Exception as e: pass

def _mark_action_processed(key: str):
    processed_actions_plate[key] = 1
    _processed_ts[key] = _now_mono()

def _is_action_processed(key: str) -> bool:
    return key in processed_actions_plate

def _dedup_gc():
    now = _now_mono()
    to_del = [k for k, ts in _processed_ts.items() if (now - ts) > DEDUP_TTL]
    for k in to_del:
        _processed_ts.pop(k, None)
        try: processed_actions_plate.pop(k, None)
        except: pass

# Безопасное редактирование
async def _safe_edit_text(msg, text, reply_markup=None, parse_mode=ParseMode.HTML, disable_preview=True):
    try:
        if msg is None: return
        await msg.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_preview)
    except (TelegramBadRequest, TelegramAPIError) as e:
        if "message is not modified" in str(e).lower(): return
        try:
            await asyncio.sleep(0.15)
            await msg.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_preview)
        except: pass
    except: pass

async def _safe_edit_reply_markup(msg, reply_markup):
    try: await msg.edit_reply_markup(reply_markup=reply_markup)
    except (TelegramBadRequest, TelegramAPIError) as e:
        if "message is not modified" in str(e).lower(): return
        try:
            await asyncio.sleep(0.15)
            await msg.edit_reply_markup(reply_markup=reply_markup)
        except: pass
    except: pass

# Активность
async def _mark_user_game_activity(user_id: int, reason: str = "") -> None:
    try:
        await db.touch_balance_last_active(int(user_id), set_active_status=True)
        dbg("ACTIVITY_TOUCH_OK", user_id=user_id, reason=reason)
    except Exception as e:
        dbg_err(f"ACTIVITY_TOUCH_ERR_{reason}", e)

# GC
async def _gc_call(user_id: int, chat_id: int, bet: int, outcome: str, label: str):
    try: await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet, outcome=outcome)
    except: pass

# Чат-баланс
async def _chat_get_balance(chat_id: int) -> int:
    try: return _safe_int(await db.get_chat_balance(bot1, chat_id), 0)
    except: return 0

async def _chat_credit_best_effort(chat_id: int, amount: int) -> bool:
    if amount <= 0: return True
    try: await db.update_chat_balance(bot1, chat_id, amount)
    except: return False
    return True

async def _chat_debit_best_effort(chat_id: int, amount: int) -> bool:
    if amount <= 0: return True
    try: await db.update_chat_balance_minus(chat_id, amount)
    except: return False
    return True

# Баланс юзера
async def _user_delta(user_id: int, delta: int) -> bool:
    d = int(delta)
    if d == 0: return True
    try: await db.update_user_balance(int(user_id), f"+{d}" if d > 0 else str(d))
    except:
        cur = _safe_int(await db.get_user_balance(int(user_id)), 0)
        new_val = max(0, cur + d)
        await db.update_user_balance(int(user_id), new_val)
    return True

# Дом
async def _home_take_and_log_plate_collapsed(*, bot, user_id: int, loss: int) -> None:
    try:
        await _chat_credit_best_effort(TECH_CHAT_ID, int(loss))

        # Получаем имя и username с защитой от ошибок (как в NUKE)
        try:
            receiver_name = await db.get_user_first_name(user_id)
        except Exception:
            receiver_name = "Игрок"
        try:
            receiver_username = await db.get_username_by_user_id(user_id)
        except Exception:
            receiver_username = None

        name_link = await create_user_link(user_id, receiver_name, receiver_username)
        await db.add_home_amount(user_id=user_id, amount=loss)

        chat_balance = await db.get_chat_balance(bot, -1003855337972)   # используем bot из параметров, не bot1

        emoji_html = '<tg-emoji emoji-id="5246916607833304803">💫</tg-emoji>'

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
                        text="Плиты",
                        callback_data="pass",
                        icon_custom_emoji_id="6028346797368283073"
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

        # Лог в TECH_CHAT: chat not found не должен ронять партию.
        fallback_text = (
            f"<b>💫 Плиты [ Плита рухнула ]</b>\n"
            f"⭐️ {name_link}\n"
            f"+ {_fmt_int(loss)} на чёрный рынок\n"
            f"{_fmt_int(chat_balance)} кут доступно для выкупов"
        )
        await safe_send_tech_log(
            bot,
            TECH_CHAT_ID,
            html=emoji_html,
            reply_markup=inline_kb,
            fallback_html=fallback_text,
            tag="PLATE][HOME_LOG_SEND",
        )
    except:
        pass

# Клавиатура
def create_keyboard_plate(game_state: List[List[str]], game_data: dict) -> InlineKeyboardMarkup:
    rev = _safe_int(game_data.get("session_rev"), 0)
    owner = _safe_int(game_data.get("owner_id"), 0)

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for row_index, row in enumerate(game_state):
        row_buttons = []
        for col_index, value in enumerate(row):
            if value == SHOW_SAFE: icon_id = SHOW_SAFE; text = " "
            elif value == SHOW_TRAP: icon_id = SHOW_TRAP; text = " "
            elif value == SHOW_COLLAPSE: icon_id = SHOW_COLLAPSE; text = " "
            else: icon_id = None; text = " "
            kwargs = {"text": text, "callback_data": f"plate_actual_{rev}_{row_index}_{col_index}_{owner}"}
            if icon_id: kwargs["icon_custom_emoji_id"] = icon_id
            row_buttons.append(InlineKeyboardButton(**kwargs))
        kb.inline_keyboard.append(row_buttons)
    if game_data.get("first_success"):
        can_take = _withdrawable_now(game_data)
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"Можно вывести {_fmt_int(can_take)} кут", callback_data=f"plate_msg_stub_{rev}_{owner}")])
        kb.inline_keyboard.append([InlineKeyboardButton(text="Закончить игру", callback_data=f"plate_withdraw_{rev}_{owner}")])
    return kb

# Генерация поля
def initialize_game_field_plate(is_demo: bool = False, is_0demo: bool = False) -> List[List[str]]:
    field = [[CELL_HIDDEN] * 2 for _ in range(10)]
    if is_0demo:
        for r in range(10):
            collapse_col = random.choice([0, 1])
            other = 1 - collapse_col
            field[r][collapse_col] = CELL_COLLAPSE
            field[r][other] = CELL_TRAP
        _debug_print_field_plate(field, "Инициализация 0DEMO")
        return field
    if is_demo:
        k = random.randint(int(PLATE_COLLAPSE_MIN), int(PLATE_COLLAPSE_MAX))
        collapse_rows = set(random.sample(list(range(10)), k=k))
        for r in range(10):
            if r in collapse_rows:
                collapse_col = random.choice([0, 1])
                other = 1 - collapse_col
                field[r][collapse_col] = CELL_COLLAPSE
                field[r][other] = CELL_SAFE
            else:
                field[r][0] = CELL_SAFE
                field[r][1] = CELL_SAFE
        _debug_print_field_plate(field, f"Инициализация DEMO, collapse_rows={sorted(list(collapse_rows))}")
        return field
    # Обычный
    k = random.randint(int(PLATE_COLLAPSE_MIN), int(PLATE_COLLAPSE_MAX))
    collapse_rows = set(random.sample(list(range(10)), k=k))
    for r in range(10):
        if r in collapse_rows:
            collapse_col = random.choice([0, 1])
            other = 1 - collapse_col
            field[r][collapse_col] = CELL_COLLAPSE
            field[r][other] = random.choice([CELL_SAFE, CELL_TRAP])
        else:
            win_col = random.choice([0, 1])
            field[r][win_col] = CELL_SAFE
            field[r][1 - win_col] = CELL_TRAP
    _debug_print_field_plate(field, f"Инициализация Обычный, collapse_rows={sorted(list(collapse_rows))}")
    return field

# Деактивация предыдущей игры
async def _deactivate_previous_plate_ui(user_id: int) -> None:
    try:
        prev_mid = user_message_plate.get(user_id)
        st = active_games_plate.get(user_id) or {}
        if not prev_mid or not st: return
        chat_id = st.get("chat_id")
        if not chat_id: return
        key = (int(chat_id), int(prev_mid))
        if key in _closed_msgs: return
        end_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Игра завершена", callback_data="plate_end_stub")]])
        try: await bot1.edit_message_reply_markup(chat_id=int(chat_id), message_id=int(prev_mid), reply_markup=end_kb)
        except: pass
        _closed_msgs.add(key)
        st["closed"] = True
        active_games_plate[user_id] = st
    except: pass

# TTL
async def _session_ttl_watcher(chat_id: int, msg_id: int, owner_id: int, ttl: int):
    await asyncio.sleep(ttl)
    st = active_games_plate.get(owner_id)
    if st and _safe_int(st.get("message_id"), 0) == int(msg_id) and not st.get("closed"):
        st["closed"] = True
        active_games_plate[owner_id] = st
        user_message_plate.pop(owner_id, None)
        _plate_session_locks.pop(int(msg_id), None)
        await _after_plate_closed(owner_id, msg_id, chat_id)

# Инвойс
async def _send_invoice_later(message: Message, user_id: int, stars_amount: str, delay: float):
    try:
        await asyncio.sleep(delay)
        ctx = pending_context.get(user_id)
        if ctx and not ctx.get("sent"):
            invoice_message = await send_invoice_to_user(message, stars_amount)
            pending_context[user_id]["manual_message_id"] = invoice_message.message_id
    except: pass

# ======================================================================
#                                START
# ======================================================================
@dp.message()
async def plate(message: Message):
    text = (message.text or "").strip()
    if not text: return
    parts = text.split()
    if not parts: return
    if parts[0].lower() not in ("плита", "плиты"): return
    if len(parts) != 2: return
    if not parts[1].isdigit(): return
    bet_amount = int(parts[1])
    if await reject_if_private_game(message):
        return
    if bet_amount < PLATE_MIN_BET:
        await message.reply(f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Минимальная ставка {PLATE_MIN_BET} кут.</b>", parse_mode="HTML")
        return
    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)

    # Челленджи + режим ставки (free / paid)
    has_assignment = False; is_free = False; current_two = 0; target_amount = 0
    gc_bet_limit = None
    try:
        gc_bet_limit = await db.gc_get_bet_limit_for_user(user_id)
    except Exception:
        gc_bet_limit = None
    try:
        assignment = await db.get_active_gc_assignment(user_id)
        if assignment and str(assignment.get("status","")).lower() == "active":
            has_assignment = True
            is_free = bool(await db.gc_active_is_free(user_id))
            current_two = int(await db.gc_get_current_two_balance(user_id) or 0)
            target_amount = int(assignment.get("target_amount", 0))
    except Exception:
        pass

    from bot.funcs.group_balance_level import decide_gc_play_mode, format_game_max_bet_html
    gate = decide_gc_play_mode(
        bet=bet_amount,
        game_max_bet=PLATE_MAX_BET,
        has_assignment=has_assignment,
        is_free=is_free,
        gc_bet_limit=gc_bet_limit,
    )
    if gate.get("mode") == "reject":
        await message.reply(format_game_max_bet_html(gate.get("max") or PLATE_MAX_BET), parse_mode="HTML")
        return
    is_free_play = gate.get("mode") == "free"

    # Инициализация новичка
    try:
        if await db.get_newbie_expires_at(user_id) is None:
            from datetime import datetime, timedelta, timezone
            expires = datetime.now(timezone.utc) + timedelta(hours=random.uniform(0.5, 24.0))
            await db.set_newbie_expires_at(user_id, expires)
            print(f"[PLATE] Установлен newbie_expires_at для {user_id}: {expires}")
    except Exception as e:
        print(f"[PLATE] Ошибка инициализации новичка: {e}")

    await welcome_back_gift(user_id)

    chat_balance = await _chat_get_balance(chat_id)
    user_balance = _safe_int(await db.get_user_balance(user_id), 0)

    # Jericho
    using_demo = False; using_0demo = False
    if not has_assignment:
        print(f"[PLATE] 🔮 Вызов Jericho")
        decision = await jericho_check(user_id, bet_amount, game_name="плиты")
        print(decision["debug"])
        demo_balance = int(await db.get_user_demo(user_id) or 0)
        zero_demo_balance = int(await db.get_user_0demo(user_id) or 0)
        if decision["action"] in ("force_win", "force_loss", "near_miss"):
            if decision["action"] == "force_win":
                if demo_balance < bet_amount: await db.add_demo_amount(user_id, bet_amount - demo_balance)
                using_demo = True
            else:
                if zero_demo_balance < bet_amount: await db.add_0demo_amount(user_id, bet_amount - zero_demo_balance)
                using_0demo = True
        else:
            if demo_balance >= bet_amount: using_demo = True
            elif zero_demo_balance >= bet_amount: using_0demo = True

    # Проверка доступности ставки
    if is_free_play:
        if bet_amount > current_two:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"Баланс челленджа : {current_two}/{target_amount} кут", callback_data="noop")], [InlineKeyboardButton(text="Недостаточно кут", callback_data="noop")]])
            await message.reply("😓", reply_markup=kb, parse_mode="HTML")
            return
    else:
        if not using_demo and not using_0demo and bet_amount > user_balance:
            bot_username = await get_bot_username_by_token(TOKEN)
            stars = _dec(bet_amount) * _dec(donate_bet)
            stars_q = stars.quantize(Decimal("1.000000"), rounding=ROUND_HALF_UP).normalize()
            stars_amount = format(stars_q, "f")
            pending_context[user_id] = {"stars_amount": stars_amount, "sent": False}
            rows = [[InlineKeyboardButton(text=f"💫 Купить {_fmt_int(bet_amount)} кут 💰", url=f"https://t.me/{bot_username}?start=insert_{stars_amount}_+")], [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")]]
            await message.reply("<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
            asyncio.create_task(_send_invoice_later(message, user_id, stars_amount, delay=timeoutdonate))
            return
        if bet_amount > chat_balance:
            await message.reply("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В группе недостаточно средств.</b>", parse_mode="HTML")
            return

    try:
        from bot.funcs.group_balance_level import reject_if_bet_over_group_level
        if await reject_if_bet_over_group_level(message, bet_amount, is_free_play=is_free_play):
            return
    except Exception as _gbl_e:
        print(f"[GBL] plate check skip: {_gbl_e!r}")

    async with _get_user_lock(user_id):
        await _deactivate_previous_plate_ui(user_id)
        prev_state = active_games_plate.get(user_id) or {}
        new_rev = _safe_int(prev_state.get("session_rev"), 0) + 1

        if using_demo: game_field = initialize_game_field_plate(is_demo=True)
        elif using_0demo: game_field = initialize_game_field_plate(is_0demo=True)
        else: game_field = initialize_game_field_plate()

        state = {
            "game_field": game_field, "current_row": 0, "row_lock": False,
            "bet": bet_amount, "win_amount": _str_dec(_dec(bet_amount)),
            "owner_id": user_id, "chat_id": chat_id, "message_id": None,
            "first_success": False, "closed": False, "withdraw_locked": False, "payout_done": False,
            "session_rev": new_rev, "has_assignment": has_assignment, "is_free": is_free_play,
            "using_demo": using_demo, "using_0demo": using_0demo,
            "win_streak": 0, "lose_streak": 0,
        }
        sent = await message.reply(f"{random.choice(RAN_EMOJIS)}", parse_mode="HTML", reply_markup=create_keyboard_plate([game_field[0]], state))
        state["message_id"] = sent.message_id
        active_games_plate[user_id] = state
        user_message_plate[user_id] = sent.message_id
        asyncio.create_task(_session_ttl_watcher(chat_id, sent.message_id, user_id, SESSION_TTL))


# ======================================================================
#                             CLICKS
# ======================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("plate_actual_"))
async def plate_process_game_buttons(call: types.CallbackQuery):
    uid = int(call.from_user.id); msg_id = int(call.message.message_id)
    now = _now_mono()
    if now - _last_click.get(uid, 0.0) < USER_CLICK_COOLDOWN:
        await call.answer("⏳"); return
    _last_click[uid] = now
    try:
        _, _, rev_s, row_s, col_s, owner_s = call.data.split("_")
        cb_rev = int(rev_s); row_index = int(row_s); col_index = int(col_s); owner_id = int(owner_s)
    except: return
    if uid != owner_id: await call.answer("Это не ваша игра.", show_alert=True); return
    if user_message_plate.get(owner_id) != msg_id: await call.answer("Откройте вашу последнюю игру.", show_alert=True); return
    inflight_key = (msg_id, uid)
    if inflight_key in _plate_inflight: await call.answer("⏳"); return
    _plate_inflight.add(inflight_key)
    lock = _get_session_lock(msg_id)
    async with lock:
        try:
            game_data = active_games_plate.get(owner_id)
            if not game_data or game_data.get("closed"): return
            if cb_rev != game_data.get("session_rev"): return
            if game_data.get("message_id") != msg_id: return
            game_field = game_data["game_field"]
            if not game_field: return
            current_row = _safe_int(game_data["current_row"], 0)
            bet_amount = _safe_int(game_data["bet"], 0)
            if bet_amount <= 0: return
            has_assignment = bool(game_data.get("has_assignment"))
            is_free = bool(game_data.get("is_free"))
            using_demo = bool(game_data.get("using_demo"))
            using_0demo = bool(game_data.get("using_0demo"))
            chat_id = _safe_int(game_data.get("chat_id"), int(call.message.chat.id))
            if not (has_assignment and is_free) and not using_demo and not using_0demo:
                ub_check = _safe_int(await db.get_user_balance(owner_id), 0)
                if bet_amount > ub_check:
                    await call.answer("💭 Недостаточно кут для игры", show_alert=True); return
            if row_index != current_row: return
            if game_data.get("row_lock"): return
            action_key = f"cell:{owner_id}:{game_data.get('session_rev')}:{msg_id}:{row_index}:{col_index}"
            if _is_action_processed(action_key): return
            _mark_action_processed(action_key)
            game_data["row_lock"] = True
            active_games_plate[owner_id] = game_data

            win_streak = game_data.get("win_streak", 0)
            lose_streak = game_data.get("lose_streak", 0)
            secret_val = game_field[row_index][col_index]

            # МАСКИРОВОЧНЫЕ ПОДМЕНЫ
            if using_demo and secret_val == CELL_SAFE:
                if win_streak >= DEMO_STREAK_BREAK:
                    secret_val = CELL_COLLAPSE; print(f"[PLATE] DEMO streak break: {win_streak} побед подряд → COLLAPSE")
                elif random.random() < DEMO_MASK_LOSS_PROB:
                    secret_val = CELL_COLLAPSE; print(f"[PLATE] DEMO mask loss: случайный COLLAPSE")
            if using_0demo and secret_val == CELL_TRAP:
                if lose_streak >= ZERO_STREAK_BREAK:
                    secret_val = CELL_SAFE; print(f"[PLATE] 0DEMO streak break: {lose_streak} проигрышей подряд → SAFE")
                elif random.random() < ZERO_MASK_WIN_PROB:
                    secret_val = CELL_SAFE; print(f"[PLATE] 0DEMO mask win: случайный SAFE")

            # ======================== 0DEMO ========================
            if using_0demo:
                await db.deduct_0demo_amount(owner_id, bet_amount)
                if secret_val == CELL_COLLAPSE:
                    game_field[row_index][col_index] = SHOW_COLLAPSE
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="ТРОПА РАЗРУШИЛАСЬ", callback_data="plate_end_stub")]])
                    await _safe_edit_text(call.message, "<tg-emoji emoji-id='5255850874248399164'>🎁</tg-emoji>", reply_markup=kb)
                    loss = bet_amount
                    if has_assignment:
                        await _gc_call(owner_id, chat_id, loss, "-", "COLLAPSE_0DEMO")
                        if not is_free:
                            await _user_delta(owner_id, -loss)
                            await db.cutehistory_minus(owner_id, loss, "- плиты (0demo collapse)")
                            await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                            await _home_take_and_log_plate_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                    else:
                        await _user_delta(owner_id, -loss)
                        await db.cutehistory_minus(owner_id, loss, "- плиты (0demo collapse)")
                        await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                        await _home_take_and_log_plate_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                else:
                    game_field[row_index][col_index] = SHOW_TRAP
                    await _safe_edit_text(call.message, "<tg-emoji emoji-id='5318762039076746215'>💥</tg-emoji>")
                    loss = bet_amount
                    if has_assignment:
                        await _gc_call(owner_id, chat_id, loss, "-", "TRAP_0DEMO")
                        if not is_free:
                            await _user_delta(owner_id, -loss)
                            await db.cutehistory_minus(owner_id, loss, "- плиты (0demo trap)")
                            await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                            await _chat_credit_best_effort(chat_id, loss)
                    else:
                        await _user_delta(owner_id, -loss)
                        await db.cutehistory_minus(owner_id, loss, "- плиты (0demo trap)")
                        await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                        await _chat_credit_best_effort(chat_id, loss)
                # Возврат долга
                await force_repay_debt(owner_id, bet_amount)
                lose_streak += 1; win_streak = 0
                game_data["win_streak"] = win_streak; game_data["lose_streak"] = lose_streak
                game_data["closed"] = True; game_data["row_lock"] = False
                active_games_plate[owner_id] = game_data
                user_message_plate.pop(owner_id, None)
                _plate_session_locks.pop(msg_id, None)
                await _after_plate_closed(owner_id, msg_id)
                return

            # ======================== DEMO ========================
            if using_demo:
                if secret_val == CELL_COLLAPSE:
                    await db.deduct_demo_amount(owner_id, bet_amount)
                    game_field[row_index][col_index] = SHOW_COLLAPSE
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="ТРОПА РАЗРУШИЛАСЬ", callback_data="plate_end_stub")]])
                    await _safe_edit_text(call.message, "<tg-emoji emoji-id='5255850874248399164'>🎁</tg-emoji>", reply_markup=kb)
                    loss = bet_amount
                    if has_assignment:
                        await _gc_call(owner_id, chat_id, loss, "-", "COLLAPSE_DEMO")
                        if not is_free:
                            await _user_delta(owner_id, -loss)
                            await db.cutehistory_minus(owner_id, loss, "- плиты (demo collapse)")
                            await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                            await _home_take_and_log_plate_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                    else:
                        await _user_delta(owner_id, -loss)
                        await db.cutehistory_minus(owner_id, loss, "- плиты (demo collapse)")
                        await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                        await _home_take_and_log_plate_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                    lose_streak += 1; win_streak = 0
                    game_data["win_streak"] = win_streak; game_data["lose_streak"] = lose_streak
                    game_data["closed"] = True; game_data["row_lock"] = False
                    active_games_plate[owner_id] = game_data
                    user_message_plate.pop(owner_id, None)
                    _plate_session_locks.pop(msg_id, None)
                    await _after_plate_closed(owner_id, msg_id)
                    return

                # SAFE – выигрыш с визуальной обманкой
                game_field[row_index][col_index] = SHOW_SAFE
                if not game_data.get("first_success"): game_data["first_success"] = True
                # Противоположная клетка всегда показывается как TRAP
                other = 1 - col_index
                if game_field[current_row][other] not in (SHOW_SAFE, SHOW_TRAP, SHOW_COLLAPSE):
                    game_field[current_row][other] = SHOW_TRAP

                prev = _dec(game_data["win_amount"])
                game_data["win_amount"] = _str_dec(prev + _dec(bet_amount) * PLATE_STEP_MULTIPLIER)
                win_streak += 1; lose_streak = 0
                game_data["win_streak"] = win_streak; game_data["lose_streak"] = lose_streak

                profit_now = max(1, _to_int_floor(_dec(game_data["win_amount"]) - _dec(bet_amount)))
                visual_emoji = random.choice(RAN_EMOJIS)
                await _safe_edit_text(call.message, visual_emoji, reply_markup=create_keyboard_plate(game_field[:current_row+1], game_data))
                if current_row == 9:
                    profit = int(profit_now)
                    await db.deduct_demo_amount(owner_id, bet_amount)
                    pay = min(profit, await _chat_get_balance(chat_id))
                    if pay > 0:
                        await _chat_debit_best_effort(chat_id, pay)
                        await _user_delta(owner_id, +pay)
                        await db.cutehistory_plus(owner_id, pay, "+ плиты")
                        await db.update_user_winamount(owner_id, pay)
                        await db.update_user_wins(owner_id, 1, bot1, ref_coin)
                    await _safe_edit_text(call.message, f"<b>{visual_emoji} 10-й ряд | {_fmt_int(pay)} кут</b>")
                    game_data["closed"] = True; game_data["payout_done"] = True
                else:
                    game_data["current_row"] = current_row + 1
                    game_data["row_lock"] = False
                    active_games_plate[owner_id] = game_data
                    await _safe_edit_reply_markup(call.message, create_keyboard_plate(game_field[:game_data["current_row"]+1], game_data))
                    return
                game_data["row_lock"] = False
                active_games_plate[owner_id] = game_data
                user_message_plate.pop(owner_id, None)
                _plate_session_locks.pop(msg_id, None)
                await _after_plate_closed(owner_id, msg_id)
                return

            # ======================== ОБЫЧНЫЙ РЕЖИМ ========================
            if secret_val == CELL_SAFE:
                game_field[row_index][col_index] = SHOW_SAFE
                if not game_data.get("first_success"): game_data["first_success"] = True
                for c in range(2):
                    if game_field[current_row][c] == CELL_SAFE: game_field[current_row][c] = SHOW_SAFE
                    elif game_field[current_row][c] == CELL_TRAP: game_field[current_row][c] = SHOW_TRAP
                    elif game_field[current_row][c] == CELL_COLLAPSE: game_field[current_row][c] = SHOW_SAFE
                prev = _dec(game_data["win_amount"])
                game_data["win_amount"] = _str_dec(prev + _dec(bet_amount) * PLATE_STEP_MULTIPLIER)
                profit_now = max(1, _to_int_floor(_dec(game_data["win_amount"]) - _dec(bet_amount)))
                win_streak += 1; lose_streak = 0
                game_data["win_streak"] = win_streak; game_data["lose_streak"] = lose_streak
                visual_emoji = random.choice(RAN_EMOJIS)
                await _safe_edit_text(call.message, visual_emoji, reply_markup=create_keyboard_plate(game_field[:current_row+1], game_data))
                if current_row == 9:
                    profit = int(profit_now)
                    if has_assignment and is_free:
                        await _safe_edit_text(call.message, f"<b>{visual_emoji} 10-й ряд | {_fmt_int(profit)} кут (челлендж)</b>")
                        if profit > 0: await _gc_call(owner_id, chat_id, profit, "+", "WIN_FINAL_FREE")
                    else:
                        chat_bal = await _chat_get_balance(chat_id)
                        pay = min(profit, max(0, chat_bal))
                        if pay > 0:
                            await _chat_debit_best_effort(chat_id, pay)
                            await _user_delta(owner_id, +pay)
                            if has_assignment: await _gc_call(owner_id, chat_id, pay, "+", "WIN_FINAL")
                            await db.cutehistory_plus(owner_id, pay, "+ плиты")
                            await db.update_user_winamount(owner_id, pay)
                            await db.update_user_wins(owner_id, 1, bot1, ref_coin)
                        await _safe_edit_text(call.message, f"<b>{visual_emoji} 10-й ряд | {_fmt_int(pay)} кут</b>")
                    game_data["closed"] = True; game_data["payout_done"] = True
                else:
                    game_data["current_row"] = current_row + 1
                    game_data["row_lock"] = False
                    active_games_plate[owner_id] = game_data
                    await _safe_edit_reply_markup(call.message, create_keyboard_plate(game_field[:game_data["current_row"]+1], game_data))
                    return
                game_data["row_lock"] = False
                active_games_plate[owner_id] = game_data
                user_message_plate.pop(owner_id, None)
                _plate_session_locks.pop(msg_id, None)
                await _after_plate_closed(owner_id, msg_id)
                return

            elif secret_val == CELL_COLLAPSE:
                game_field[row_index][col_index] = SHOW_COLLAPSE
                kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="ТРОПА РАЗРУШИЛАСЬ", callback_data="plate_end_stub")]])
                await _safe_edit_text(call.message, "<tg-emoji emoji-id='5255850874248399164'>🎁</tg-emoji>", reply_markup=kb)
                loss = bet_amount
                if has_assignment:
                    await _gc_call(owner_id, chat_id, loss, "-", "COLLAPSE_HOME")
                    if not is_free:
                        await _user_delta(owner_id, -loss)
                        await db.cutehistory_minus(owner_id, loss, "- плиты (домой)")
                        await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                        await _home_take_and_log_plate_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                else:
                    await _user_delta(owner_id, -loss)
                    await db.cutehistory_minus(owner_id, loss, "- плиты (домой)")
                    await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                    await _home_take_and_log_plate_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                lose_streak += 1; win_streak = 0
                game_data["win_streak"] = win_streak; game_data["lose_streak"] = lose_streak
                game_data["closed"] = True; game_data["row_lock"] = False
                active_games_plate[owner_id] = game_data
                user_message_plate.pop(owner_id, None)
                _plate_session_locks.pop(msg_id, None)
                await _after_plate_closed(owner_id, msg_id)
                return

            elif secret_val == CELL_TRAP:
                game_field[row_index][col_index] = SHOW_TRAP
                await _safe_edit_text(call.message, "💥")
                loss = bet_amount
                if has_assignment:
                    await _gc_call(owner_id, chat_id, loss, "-", "LOSS")
                    if not is_free:
                        await _user_delta(owner_id, -loss)
                        await db.cutehistory_minus(owner_id, loss, "- плиты")
                        await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                        await _chat_credit_best_effort(chat_id, loss)
                else:
                    await _user_delta(owner_id, -loss)
                    await db.cutehistory_minus(owner_id, loss, "- плиты")
                    await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                    await _chat_credit_best_effort(chat_id, loss)
                lose_streak += 1; win_streak = 0
                game_data["win_streak"] = win_streak; game_data["lose_streak"] = lose_streak
                game_data["closed"] = True; game_data["row_lock"] = False
                active_games_plate[owner_id] = game_data
                user_message_plate.pop(owner_id, None)
                _plate_session_locks.pop(msg_id, None)
                await _after_plate_closed(owner_id, msg_id)
                return

        except Exception as e:
            dbg_err("BTN_ERR", e)
        finally:
            _plate_inflight.discard(inflight_key)
            st = active_games_plate.get(owner_id)
            if st and st.get("message_id") == msg_id and st.get("row_lock"):
                st["row_lock"] = False
                active_games_plate[owner_id] = st


# ======================================================================
#                             WITHDRAW
# ======================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("plate_withdraw_"))
async def plate_process_withdraw(call: types.CallbackQuery):
    uid = int(call.from_user.id); msg_id = int(call.message.message_id)
    try:
        _, _, rev_s, owner_s = call.data.split("_")
        cb_rev = int(rev_s); owner_id = int(owner_s)
    except: return
    if uid != owner_id: await call.answer("Это не ваша игра.", show_alert=True); return
    if user_message_plate.get(owner_id) != msg_id: await call.answer("Откройте вашу последнюю игру.", show_alert=True); return
    lock = _get_session_lock(msg_id)
    async with lock:
        game_data = active_games_plate.get(owner_id)
        if not game_data or game_data.get("closed"): return
        if cb_rev != game_data.get("session_rev"): return
        if not game_data.get("first_success"): return
        if game_data.get("payout_done") or game_data.get("withdraw_locked"): return
        game_data["withdraw_locked"] = True
        active_games_plate[owner_id] = game_data
        action_key = f"wd:{owner_id}:{game_data.get('session_rev')}:{msg_id}"
        if _is_action_processed(action_key): return
        _mark_action_processed(action_key)

        chat_id = _safe_int(game_data.get("chat_id"), int(call.message.chat.id))
        has_assignment = bool(game_data.get("has_assignment"))
        is_free = bool(game_data.get("is_free"))
        using_demo = bool(game_data.get("using_demo"))
        using_0demo = bool(game_data.get("using_0demo"))
        bet_dec = _dec(game_data.get("bet", 0))
        win_dec = _dec(game_data.get("win_amount", bet_dec))
        profit = max(1, _to_int_floor(win_dec - bet_dec))

        if using_0demo:
            await call.answer("Игра завершена.", show_alert=False); return

        if using_demo:
            await db.deduct_demo_amount(owner_id, int(game_data["bet"]))
            pay = min(int(profit), await _chat_get_balance(chat_id))
            if pay > 0:
                await _chat_debit_best_effort(chat_id, pay)
                await _user_delta(owner_id, +pay)
                await db.cutehistory_plus(owner_id, pay, "+ плиты")
                await db.update_user_winamount(owner_id, pay)
                await db.update_user_wins(owner_id, 1, bot1, ref_coin)
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{_fmt_int(pay)} кут", callback_data="plate_paid_stub")], [InlineKeyboardButton(text="Выплата", callback_data="plate_msg_stub")]])
            await _safe_edit_text(call.message, "<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji>", reply_markup=kb)
        elif has_assignment and is_free:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{_fmt_int(profit)} кут", callback_data="plate_paid_stub")], [InlineKeyboardButton(text="Выплата (челлендж)", callback_data="plate_msg_stub")]])
            await _safe_edit_text(call.message, random.choice(RAN_EMOJIS), reply_markup=kb)
            if profit > 0: await _gc_call(owner_id, chat_id, profit, "+", "WITHDRAW_FREE")
        else:
            pay = min(int(profit), await _chat_get_balance(chat_id))
            if pay > 0:
                await _chat_debit_best_effort(chat_id, pay)
                await _user_delta(owner_id, +pay)
                if has_assignment: await _gc_call(owner_id, chat_id, pay, "+", "WITHDRAW")
                await db.cutehistory_plus(owner_id, pay, "+ плиты")
                await db.update_user_winamount(owner_id, pay)
                await db.update_user_wins(owner_id, 1, bot1, ref_coin)
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{_fmt_int(pay)} кут", callback_data="plate_paid_stub")], [InlineKeyboardButton(text="Выплата", callback_data="plate_msg_stub")]])
            await _safe_edit_text(call.message, "<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji>", reply_markup=kb)

        game_data["payout_done"] = True; game_data["closed"] = True
        active_games_plate[owner_id] = game_data
        user_message_plate.pop(owner_id, None)
        _plate_session_locks.pop(msg_id, None)
        await _after_plate_closed(owner_id, msg_id)


# ------------------------- Заглушки -------------------------
@dp.callback_query(lambda c: c.data.startswith("plate_msg_stub"))
async def plate_msg_stub(call): await call.answer("💬")
@dp.callback_query(lambda c: c.data.startswith("plate_paid_stub"))
async def plate_paid_stub(call): await call.answer("✅")
@dp.callback_query(lambda c: c.data.startswith("plate_end_stub"))
async def plate_end_stub(call): await call.answer("Игра завершена.", show_alert=True)