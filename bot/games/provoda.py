# -*- coding: utf-8 -*-
"""
⚡️ Провода - полная версия с интеграцией Jericho и маскировочными механиками.
- Обычный режим: случайные победные/проигрышные + одно замыкание.
- DEMO-режим: все провода победные (кроме замыкания), ставка списывается с demo,
  возможна подмена победы на проигрыш (маскировка).
- 0DEMO-режим: все провода проигрышные (кроме замыкания), ставка списывается с 0demo,
  возможна подмена проигрыша на победу (маскировка), долг гасится только при обычном проигрыше.
ЗАМЫКАНИЕ никогда не списывает demo/0demo, только основной баланс.
ВАЖНО: даже при наличии demo/0demo пользователь НЕ может начать игру,
если его основной баланс (или баланс челленджа) меньше ставки.
"""

from main import *  # noqa
import asyncio
import random
import time
import re
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, getcontext
from typing import Dict, Optional, Tuple, List, Set

from aiogram import types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from bot.funcs.func import get_bot_username_by_token

# Jericho-функции
from main import (
    jericho_check, welcome_back_gift, newbie_safety_net, force_repay_debt
)

getcontext().prec = 28

CB_PREFIX = "wcol"
CB_HDR = "wires_hdr"
CB_CNT = "wires_cnt"
CB_END = "wires_end_stub"
CB_PAID = "wires_paid_stub"

DEBUG_WIRES = True
DEBUG_WIRES_FIELD = True

# Маскировочные механики
DEMO_MASK_LOSS_PROB = 0.12               # вероятность подмены WIN → LOSS в demo-режиме
DEMO_STREAK_BREAK = 3                    # после скольких побед подряд принудительно LOSS
ZERO_MASK_WIN_PROB = 0.12                # вероятность подмены LOSS → WIN в 0demo-режиме
ZERO_STREAK_BREAK = 3                    # после скольких проигрышей подряд принудительно WIN

# Конфигурация цветов проводов с идентификаторами Premium-эмодзи
WIRE_COLORS = [
    {"key": "red",    "emoji_id": "5339546996434812675", "title": "Красный"},
    {"key": "blue",   "emoji_id": "5339513551524481000", "title": "Синий"},
    {"key": "green",  "emoji_id": "5339112148175959615", "title": "Зелёный"},
    {"key": "yellow", "emoji_id": "5339082633160703625", "title": "Жёлтый"},
    {"key": "purple", "emoji_id": "5339146671123087992", "title": "Фиолетовый"},
    {"key": "orange", "emoji_id": "5336936725765700868", "title": "Оранжевый"},
    {"key": "white",  "emoji_id": "5339113303522161846", "title": "Белый"},
]

_wires_session_locks: Dict[int, asyncio.Lock] = {}
_wires_inflight: Set[Tuple[int, int]] = set()
_last_click_wires: Dict[int, float] = {}
_closed_msgs_wires: Set[Tuple[int, int]] = set()


def _ts() -> str:
    return time.strftime("%H:%M:%S", time.localtime())


def dbg(stage: str, **kw) -> None:
    if not DEBUG_WIRES:
        return
    parts = [f"[{_ts()}][WIRES][{stage}]"] + [f"{k}={v}" for k, v in kw.items()]
    try:
        print(" ".join(parts), flush=True)
    except Exception:
        pass


def dbg_err(stage: str, err: Exception) -> None:
    if not DEBUG_WIRES:
        return
    try:
        import traceback
        print(
            f"[{_ts()}][WIRES][ERROR][{stage}] {err}\n"
            f"{''.join(traceback.format_exception(type(err), err, err.__traceback__))}",
            flush=True,
        )
    except Exception:
        pass


def _get_lock(msg_id: int) -> asyncio.Lock:
    lock = _wires_session_locks.get(msg_id)
    if lock is None:
        lock = asyncio.Lock()
        _wires_session_locks[msg_id] = lock
        dbg("LOCK_CREATE", msg_id=msg_id)
    return lock


def _dec(v) -> Decimal:
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
    return max(0, int(x.quantize(0, rounding=ROUND_DOWN)))


def _fmt_int(n: int) -> str:
    try:
        return "{:,.0f}".format(int(n)).replace(",", ".")
    except Exception:
        return str(n)


def _save_safe(obj):
    try:
        obj.save()
    except Exception:
        pass


async def _mark_user_game_activity(user_id: int, reason: str = "") -> None:
    try:
        await db.touch_balance_last_active(int(user_id), set_active_status=True)
        dbg("ACTIVITY_TOUCH_OK", user_id=user_id, reason=reason)
    except Exception as e:
        dbg_err(f"ACTIVITY_TOUCH_ERR_{reason}", e)


async def _safe_edit_text(
    msg: types.Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML",
):
    try:
        await msg.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )
        return True
    except (TelegramBadRequest, TelegramAPIError) as e:
        if "message is not modified" in str(e).lower():
            return True
        try:
            await asyncio.sleep(0.15)
            await msg.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )
            return True
        except Exception:
            return False
    except Exception:
        return False


async def _safe_edit_reply_markup(
    msg: types.Message,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
):
    """Редактирует только клавиатуру сообщения (без параметра style)"""
    try:
        await msg.edit_reply_markup(reply_markup=reply_markup)
        return True
    except (TelegramBadRequest, TelegramAPIError) as e:
        if "message is not modified" in str(e).lower():
            return True
        try:
            await asyncio.sleep(0.15)
            await msg.edit_reply_markup(reply_markup=reply_markup)
            return True
        except Exception:
            return False
    except Exception:
        return False


async def _safe_answer(cb: CallbackQuery, text: str = "", show_alert: bool = False):
    try:
        await cb.answer(text, show_alert=show_alert, cache_time=0)
    except Exception:
        pass


async def _safe_render_final_state(
    msg: types.Message,
    *,
    html_text: str,
    plain_text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    ok = await _safe_edit_text(msg, html_text, reply_markup=reply_markup, parse_mode="HTML")
    if ok:
        return

    ok = await _safe_edit_text(msg, plain_text, reply_markup=reply_markup, parse_mode=None)
    if ok:
        return

    await _safe_edit_reply_markup(msg, reply_markup=reply_markup)


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
        await db.update_user_balance(int(user_id), int(max(0, cur + amt)))
        return True
    except Exception:
        return False


async def _user_minus(user_id: int, amount: int) -> bool:
    amt = int(amount)
    if amt <= 0:
        return True
    try:
        await db.update_user_balance(int(user_id), f"-{amt}")
        return True
    except Exception:
        pass
    try:
        cur = int(await db.get_user_balance(int(user_id)) or 0)
    except Exception:
        cur = 0
    try:
        await db.update_user_balance(int(user_id), int(max(0, cur - amt)))
        return True
    except Exception:
        return False


async def _send_invoice_later(message: Message, user_id: int, stars_amount: str, delay: float):
    try:
        await asyncio.sleep(delay)
        ctx = pending_context.get(user_id)
        if ctx and not ctx.get("sent"):
            invoice_message = await send_invoice_to_user(message, stars_amount)
            pending_context[user_id]["manual_message_id"] = invoice_message.message_id
    except Exception:
        pass


async def _load_gc_state_for_user(user_id: int) -> dict:
    has_assignment = False
    is_free = False
    current_two = 0
    target_amount = 0
    provoda_max_bet = provoda_MAX_BET

    try:
        gc_bet_limit = await db.gc_get_bet_limit_for_user(user_id)
    except Exception as e:
        gc_bet_limit = None
        print(f"[WIRES][GC_BET_LIMIT] Ошибка: {e}")

    if gc_bet_limit is not None:
        try:
            gc_bet_limit_int = int(gc_bet_limit)
            if gc_bet_limit_int > 0:
                provoda_max_bet = min(provoda_MAX_BET, gc_bet_limit_int)
        except Exception as e:
            print(f"[WIRES][GC_BET_LIMIT] Ошибка преобразования: {e}")

    try:
        assignment = await db.get_active_gc_assignment(user_id)
    except Exception as e:
        assignment = None
        print(f"[WIRES][GC_STATE] Ошибка: {e}")

    if assignment and str(assignment.get("status") or "").lower() == "active":
        has_assignment = True

        try:
            is_free = bool(await db.gc_active_is_free(user_id))
        except Exception:
            is_free = False

        try:
            current_two_val = await db.gc_get_current_two_balance(user_id)
            if current_two_val is not None:
                current_two = int(current_two_val)
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
        "max_bet": provoda_max_bet,
    }


def _find_wires_state_by_message_id(message_id: int) -> Optional[Tuple[int, dict]]:
    try:
        uid = wires_msg_index.get(int(message_id))
        if uid is not None:
            st = active_games_wires.get(int(uid))
            if isinstance(st, dict) and int(st.get("message_id", 0)) == int(message_id):
                return int(uid), st
    except Exception:
        pass

    try:
        for uid, st in list(active_games_wires.items()):
            try:
                if isinstance(st, dict) and int(st.get("message_id", 0)) == int(message_id):
                    return int(uid), st
            except Exception:
                continue
    except Exception:
        pass
    return None


def _debug_print_field(colors: List[dict], win_mask: List[int], short_idx: int):
    if not DEBUG_WIRES_FIELD:
        return
    try:
        print(f"[{_ts()}][WIRES][FIELD]", flush=True)
        line1 = []
        line2 = []
        line3 = []
        for i, color in enumerate(colors):
            line1.append(f"{i}:{color['title']}")
            if i == short_idx:
                line2.append("⚡️")
            elif win_mask[i] == 1:
                line2.append("🍀")
            else:
                line2.append("💥")
            line3.append(color["title"])
        print("  IDX   | " + "  ".join(line1), flush=True)
        print("  OUT   | " + "  ".join(line2), flush=True)
        print("  COLOR | " + " | ".join(line3), flush=True)
        print(f"[{_ts()}][WIRES][FIELD_END]\n", flush=True)
    except Exception as e:
        dbg_err("FIELD_PRINT_ERR", e)


async def _home_take_and_log_wires_short(*, bot, user_id: int, loss: int) -> None:
    try:
        await _chat_plus(TECH_CHAT_ID, int(loss))
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
        chat_balance = await db.get_chat_balance(bot, -1003855337972)   # используем bot, не bot1

        # Основной HTML-эмодзи (🎗)
        emoji_html = '<tg-emoji emoji-id="5782990399672946716">🎗</tg-emoji>'

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
                        text="Провода",
                        callback_data="pass",
                        icon_custom_emoji_id="6028346797368283073"  # ✈️
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

        try:
            # Попытка отправить красивое сообщение с кастомным эмодзи и кнопками
            await bot.send_message(
                TECH_CHAT_ID,
                emoji_html,
                reply_markup=inline_kb,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception:
            # Fallback: если premium-эмодзи не прошли, шлём простой текст без кнопок
            fallback_text = (
                f"⚡️ Провода [Замыкание]\n"
                f"<blockquote><b>+ {_fmt_int(loss)} на чёрный рынок</b></blockquote>\n"
                f"<blockquote><b>{_fmt_int(chat_balance)} кут доступно для выкупов</b></blockquote>"
            )
            await bot.send_message(
                TECH_CHAT_ID,
                fallback_text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
    except Exception as e:
        dbg_err("SHORT_LOG_ERR", e)


def _build_keyboard_wires(
    session_rev: int, bet: int, uid: int,
    colors: List[dict], win_mask: List[int], short_idx: int,
    fake_win_count: Optional[int] = None,
) -> InlineKeyboardMarkup:
    length = len(win_mask)
    if fake_win_count is not None:
        wins = fake_win_count
    else:
        wins = int(sum(1 for b in win_mask if b))
    mask_val = 0
    for i, bit in enumerate(win_mask):
        if bit:
            mask_val |= (1 << i)
    mask_hex = format(mask_val, "x")

    header_btn = InlineKeyboardButton(
        text="Перережьте верный провод",
        callback_data=f"{CB_HDR}_{session_rev}_{bet}_{uid}_{length}_{mask_hex}_{short_idx}",
    )
    count_btn = InlineKeyboardButton(
        text=f"Победных: {wins}/{length} • Замыканий: 1",
        callback_data=f"{CB_CNT}_{session_rev}_{bet}_{uid}_{length}_{mask_hex}_{short_idx}",
        style="default",
    )
    wire_row: List[InlineKeyboardButton] = []
    for idx, color in enumerate(colors):
        wire_row.append(
            InlineKeyboardButton(
                text=" ",  # Пустой текст, эмодзи будет через icon_custom_emoji_id
                callback_data=f"{CB_PREFIX}_{session_rev}_{bet}_{uid}_{idx}_{length}_{mask_hex}_{short_idx}",
                style="default",
                icon_custom_emoji_id=color["emoji_id"],
            )
        )
    # Кнопка вывода (если есть выигрыш) – будет success
    # Она добавляется позже отдельно, здесь только провода
    return InlineKeyboardMarkup(inline_keyboard=[[header_btn], [count_btn], wire_row])


def _kb_game_over(text: str = "Игра завершена") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=CB_END, style="default")]])


def _kb_paid(text: str) -> InlineKeyboardMarkup:
    # Кнопка выплаты имеет стиль "success"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=CB_PAID, style="success")]])


async def _deactivate_previous_wires_ui(user_id: int):
    st = active_games_wires.get(user_id) or {}
    msg_id = st.get("message_id")
    chat_id = st.get("chat_id")
    if not msg_id or not chat_id:
        return
    key = (int(chat_id), int(msg_id))
    if key in _closed_msgs_wires:
        return
    st.update({
        "closed": True, "settled": True, "settling": False,
        "result": st.get("result", "aborted"),
    })
    active_games_wires[user_id] = st
    _save_safe(active_games_wires)
    end_kb = _kb_game_over("Игра завершена")
    try:
        emoji_id = get_random_eagle_emoji_id()
        await bot1.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"<tg-emoji emoji-id='{emoji_id}'>🕊</tg-emoji>",
            reply_markup=end_kb, parse_mode="HTML", disable_web_page_preview=True,
        )
    except Exception:
        try:
            await bot1.edit_message_reply_markup(chat_id=chat_id, message_id=msg_id, reply_markup=end_kb)
        except Exception:
            pass
    _closed_msgs_wires.add(key)
    try:
        if user_message_wires.get(user_id) == msg_id:
            user_message_wires.pop(user_id, None)
            _save_safe(user_message_wires)
    except Exception:
        pass
    try:
        if wires_msg_index.get(int(msg_id)) == int(user_id):
            wires_msg_index.pop(int(msg_id), None)
            _save_safe(wires_msg_index)
    except Exception:
        pass


def _finalize_wires_game(user_id: int, result: str = ""):
    st = active_games_wires.get(user_id)
    if st:
        st.update({
            "closed": True, "settled": True, "settling": False,
            "result": result or st.get("result", ""),
        })
        active_games_wires[user_id] = st
        _save_safe(active_games_wires)
        try:
            mid = int(st.get("message_id", 0))
            if mid:
                wires_msg_index.pop(mid, None)
                _save_safe(wires_msg_index)
        except Exception:
            pass
    if user_message_wires.get(user_id):
        user_message_wires.pop(user_id, None)
        _save_safe(user_message_wires)


async def _session_ttl_watcher(chat_id: int, msg_id: int, owner_id: int, ttl: int):
    try:
        await asyncio.sleep(ttl)
        st = active_games_wires.get(owner_id)
        if not st:
            return
        if int(st.get("message_id", 0)) != int(msg_id):
            return
        if st.get("closed"):
            return
        st["closed"] = True
        st["settled"] = True
        st["settling"] = False
        st["result"] = st.get("result", "ttl")
        active_games_wires[owner_id] = st
        _save_safe(active_games_wires)
        key = (int(chat_id), int(msg_id))
        if key not in _closed_msgs_wires:
            end_kb = _kb_game_over("Игра завершена")
            try:
                emoji_id = get_random_eagle_emoji_id()
                await bot1.edit_message_text(
                    chat_id=int(chat_id), message_id=int(msg_id),
                    text=f"<tg-emoji emoji-id='{emoji_id}'>🕊</tg-emoji>",
                    reply_markup=end_kb, parse_mode="HTML", disable_web_page_preview=True,
                )
            except Exception:
                try:
                    await bot1.edit_message_reply_markup(
                        chat_id=int(chat_id), message_id=int(msg_id), reply_markup=end_kb,
                    )
                except Exception:
                    pass
            _closed_msgs_wires.add(key)
        try:
            if user_message_wires.get(owner_id) == msg_id:
                user_message_wires.pop(owner_id, None)
                _save_safe(user_message_wires)
        except Exception:
            pass
        try:
            if wires_msg_index.get(int(msg_id)) == int(owner_id):
                wires_msg_index.pop(int(msg_id), None)
                _save_safe(wires_msg_index)
        except Exception:
            pass
        _wires_session_locks.pop(int(msg_id), None)
    except Exception as e:
        dbg_err("TTL_ERR", e)


# ======================================================================
#                                START
# ======================================================================
@dp.message(lambda message: bool(message.text) and message.text.split()[0].lower() in ("провода", "провод"))
async def provoda(message: Message):
    txt = (message.text or "").strip()
    if not txt:
        return
    parts = txt.split()
    if not parts:
        return
    cmd = parts[0].lower()
    if cmd not in ("провода", "провод"):
        return
    if len(parts) != 2:
        return
    bet_token = (parts[1] or "").strip()
    if not bet_token or not bet_token.isdigit():
        return
    bet_amount = int(bet_token)
    if bet_amount <= 0:
        return
    if bet_amount < provoda_MIN_BET:
        await message.reply(
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Минимальная ставка {provoda_MIN_BET} кут.</b>",
            parse_mode="HTML", disable_web_page_preview=True,
        )
        return
    if bet_amount > provoda_MAX_BET:
        try:
            selected_phrase = random.choice(phrases12312)
        except Exception:
            selected_phrase = "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> Ставка слишком большая."
        await message.reply(f"<b>{selected_phrase}</b>", parse_mode="HTML", disable_web_page_preview=True)
        return
    if message.chat.type == "private":
        await message.reply(
            "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В эту игру можно играть только в публичных группах.</b>",
            parse_mode="HTML", disable_web_page_preview=True,
        )
        return

    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)

    # ----- Инициализация новичка и welcome back -----
    try:
        if await db.get_newbie_expires_at(user_id) is None:
            from datetime import datetime, timedelta, timezone
            expires = datetime.now(timezone.utc) + timedelta(hours=random.uniform(0.5, 24.0))
            await db.set_newbie_expires_at(user_id, expires)
            print(f"[WIRES] Установлен newbie_expires_at для {user_id}: {expires}")
    except Exception as e:
        print(f"[WIRES] Ошибка инициализации новичка: {e}")
    await welcome_back_gift(user_id)

    gc_state = await _load_gc_state_for_user(user_id)
    has_assignment = gc_state["has_assignment"]
    is_free = gc_state["is_free"]
    current_two = gc_state["current_two"]
    target_amount = gc_state["target_amount"]
    max_bet_gc = gc_state["max_bet"]

    if bet_amount > max_bet_gc:
        await message.reply(
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Максимальная ставка в этой игре: {_fmt_int(max_bet_gc)} кут.</b>",
            parse_mode="HTML", disable_web_page_preview=True,
        )
        return

    # ----- Получение балансов demo/0demo -----
    demo_balance = int(await db.get_user_demo(user_id) or 0)
    zero_demo_balance = int(await db.get_user_0demo(user_id) or 0)
    print(f"[WIRES] Балансы: demo={demo_balance}, 0demo={zero_demo_balance}")

    # ----- Логика выбора режима на основе реальных балансов и Jericho -----
    using_demo = False
    using_0demo = False

    # Сначала определим, какие бонусные балансы покрывают ставку
    demo_enough = demo_balance >= bet_amount
    zero_enough = zero_demo_balance >= bet_amount

    # Базовый выбор режима по наличию бонусов
    if demo_enough and zero_enough:
        # Оба покрывают – выбираем тот, у которого баланс больше
        if demo_balance > zero_demo_balance:
            using_demo = True
            print("[WIRES] Базовый выбор: demo (оба покрывают, demo больше)")
        elif zero_demo_balance > demo_balance:
            using_0demo = True
            print("[WIRES] Базовый выбор: 0demo (оба покрывают, 0demo больше)")
        else:
            using_demo = True  # равны – отдаём предпочтение demo
            print("[WIRES] Базовый выбор: demo (оба равны)")
    elif demo_enough:
        using_demo = True
        print("[WIRES] Базовый выбор: demo (только demo покрывает)")
    elif zero_enough:
        using_0demo = True
        print("[WIRES] Базовый выбор: 0demo (только 0demo покрывает)")
    else:
        print("[WIRES] Базовый выбор: обычный (нет demo/0demo)")

    # Теперь учитываем рекомендации Jericho
    if not has_assignment:
        print(f"[WIRES] 🔮 Вызов Jericho (user={user_id}, bet={bet_amount})")
        decision = await jericho_check(user_id, bet_amount, game_name="провода")
        print(decision["debug"])

        action = decision.get("action")
        if action in ("force_win", "force_loss", "near_miss"):
            if action == "force_win":
                # Jericho хочет победу. Если demo хватает, переключаемся на demo.
                if demo_enough:
                    using_demo = True
                    using_0demo = False
                    print("[WIRES] Jericho force_win → переключено на demo (demo хватает)")
                else:
                    print("[WIRES] Jericho force_win, но demo не хватает → оставляем базовый выбор")
            elif action in ("force_loss", "near_miss"):
                # Jericho хочет проигрыш. Если 0demo хватает, переключаемся на 0demo.
                if zero_enough:
                    using_0demo = True
                    using_demo = False
                    print("[WIRES] Jericho force_loss → переключено на 0demo (0demo хватает)")
                else:
                    print("[WIRES] Jericho force_loss, но 0demo не хватает → оставляем базовый выбор")
        else:
            print("[WIRES] Jericho без явной рекомендации → оставляем базовый выбор")
    else:
        print("[WIRES] Есть активное задание → demo/0demo отключены")

    print(f"[WIRES] Итоговый режим: demo={using_demo}, 0demo={using_0demo}")

    # ----- ПРОВЕРКА БАЛАНСА ПОЛЬЗОВАТЕЛЯ (ОБЯЗАТЕЛЬНАЯ) -----
    if has_assignment and is_free:
        if bet_amount > current_two:
            progress = f"{current_two}/{target_amount}" if target_amount and target_amount > 0 else f"{current_two}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"Баланс челленджа: {progress} кут", callback_data="noop")],
                [InlineKeyboardButton(text="Недостаточно кут", callback_data="noop")],
            ])
            await message.reply("😓", reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
            return
    else:
        user_balance = int(await db.get_user_balance(user_id) or 0)
        if bet_amount > user_balance:
            stars = _dec(bet_amount) * _dec(donate_bet)
            stars_q = stars.quantize(Decimal("1.000000"), rounding=ROUND_HALF_UP).normalize()
            stars_amount = format(stars_q, "f")
            try:
                bot_username = await get_bot_username_by_token(TOKEN)
            except Exception:
                bot_username = "CuteGamingBot"
            pending_context[user_id] = {"stars_amount": stars_amount, "sent": False}
            rows = [
                [InlineKeyboardButton(
                    text=f"💫 Купить {_fmt_int(bet_amount)} кут 💰",
                    url=f"https://t.me/{bot_username}?start=insert_{stars_amount}_+",
                )],
                [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")],
            ]
            if has_assignment and not is_free:
                rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
                rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])
            kb = InlineKeyboardMarkup(inline_keyboard=rows)
            await message.reply(
                "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
                reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True,
            )
            asyncio.create_task(_send_invoice_later(message, user_id, stars_amount, delay=timeoutdonate))
            return

    # ----- ПРОВЕРКА БАЛАНСА ГРУППЫ -----
    chat_balance_now = await _chat_get_balance(chat_id)
    max_win = int(bet_amount * PAYOUT_MULTIPLIER)
    if chat_balance_now < max_win:
        await message.reply(
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В группе недостаточно средств для выплаты возможного выигрыша.</b>\n"
            f"💸 Баланс группы: {_fmt_int(chat_balance_now)} кут\n"
            f"📌 Нужно минимум: {_fmt_int(max_win)} кут",
            parse_mode="HTML", disable_web_page_preview=True,
        )
        return

    # ----- Антиспам -----
    now = time.time()
    DURATION = delaysssssssssgamesonee.get(chat_id, 1)
    if DURATION > 0:
        chat_map = last_provoda_time.setdefault(chat_id, {})
        last_usage = float(chat_map.get(user_id, 0.0) or 0.0)
        left = DURATION - (now - last_usage)
        if left > 0:
            await message.reply(f"⌚️ <b>Подождите {int(left)} сек</b>", parse_mode="HTML")
            return
    if DURATION > 0:
        last_provoda_time.setdefault(chat_id, {})[user_id] = now

    if pressed_users_wires.get(user_id):
        await message.reply("⏳ Подождите чуть-чуть…", parse_mode="HTML")
        return
    pressed_users_wires[user_id] = True

    try:
        await _deactivate_previous_wires_ui(user_id)

        prev_state = active_games_wires.get(user_id) or {}
        session_rev = int(prev_state.get("session_rev", 0)) + 1

        wires_count = random.randint(WIRES_MIN, WIRES_MAX)
        colors = random.sample(WIRE_COLORS, k=wires_count)

        all_indices = list(range(wires_count))
        short_idx = random.choice(all_indices)

        if using_demo:
            # Все провода победные, кроме короткого замыкания
            win_mask = [1] * wires_count
            win_mask[short_idx] = 0
            fake_win_count = None
        elif using_0demo:
            # Реально все проигрышные, но UI маскируется под "почти все победные"
            win_mask = [0] * wires_count
            fake_win_count = wires_count - 1   # показываем N-1 победных
        else:
            wins = WIN_BY_COUNT.get(wires_count, 1)
            remaining = [i for i in all_indices if i != short_idx]
            win_indices = set(random.sample(remaining, wins)) if wins <= len(remaining) else set(remaining)
            win_mask = [1 if i in win_indices else 0 for i in range(wires_count)]
            fake_win_count = None

        _debug_print_field(colors, win_mask, short_idx)

        kb = _build_keyboard_wires(session_rev, bet_amount, user_id, colors, win_mask, short_idx,
                                   fake_win_count=fake_win_count)
        sent = await message.reply(
            "<tg-emoji emoji-id='5458371097789472509'>🎗</tg-emoji>",
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

        active_games_wires[user_id] = {
            "owner_id": user_id,
            "chat_id": chat_id,
            "message_id": sent.message_id,
            "bet": int(bet_amount),
            "session_rev": session_rev,
            "closed": False,
            "settling": False,
            "settled": False,
            "result": "",
            "ts": now,
            "wires_count": wires_count,
            "wins": sum(1 for x in win_mask if x),
            "short_idx": int(short_idx),
            "colors": [c["key"] for c in colors],
            "win_mask": win_mask,
            "multiplier": str(PAYOUT_MULTIPLIER),
            "has_assignment": has_assignment,
            "is_free": is_free,
            "using_demo": using_demo,
            "using_0demo": using_0demo,
            "win_streak": 0,
            "lose_streak": 0,
        }
        _save_safe(active_games_wires)

        wires_msg_index[int(sent.message_id)] = int(user_id)
        _save_safe(wires_msg_index)

        user_message_wires[user_id] = sent.message_id
        _save_safe(user_message_wires)

        asyncio.create_task(_session_ttl_watcher(chat_id, sent.message_id, user_id, 20 * 60))

    finally:
        pressed_users_wires[user_id] = False


# ======================================================================
#                               CALLBACKS
# ======================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith(CB_PREFIX + "_"))
async def provoda_callback(callback_query: CallbackQuery):
    msg = callback_query.message
    chat_id = int(msg.chat.id)
    msg_id = int(msg.message_id)
    clicker_id = int(callback_query.from_user.id)

    try:
        _, rev_s, bet_s, uid_s, idx_s, len_s, mask_hex, short_s = callback_query.data.split("_")
        cb_rev = int(rev_s)
        bet_amount = int(bet_s)
        owner_id = int(uid_s)
        idx = int(idx_s)
        length = int(len_s)
        mask_val = int(mask_hex, 16)
        short_idx_cb = int(short_s)
    except Exception:
        await _safe_answer(callback_query, "🛠 Ошибка данных", show_alert=False)
        return

    if clicker_id != owner_id:
        await _safe_answer(callback_query, "Это не ваша игра.", show_alert=False)
        return

    now_mono = time.monotonic()
    if now_mono - _last_click_wires.get(clicker_id, 0.0) < 0.35:
        await _safe_answer(callback_query, "⏳ Подожди чуть-чуть…", show_alert=False)
        return
    _last_click_wires[clicker_id] = now_mono

    inflight_key = (msg_id, clicker_id)
    if inflight_key in _wires_inflight:
        await _safe_answer(callback_query, "⏳ Обрабатываю клик…", show_alert=False)
        return
    _wires_inflight.add(inflight_key)

    lock = _get_lock(msg_id)
    async with lock:
        try:
            await _safe_answer(callback_query)

            found = _find_wires_state_by_message_id(msg_id)
            if found is not None:
                user_id, game = found
                state_available = True
            else:
                user_id = clicker_id
                game = active_games_wires.get(user_id)
                state_available = isinstance(game, dict)

            emoji_id = get_random_eagle_emoji_id()

            if state_available:
                if game.get("settled") or game.get("closed"):
                    end_kb = _kb_game_over("Игра завершена")
                    await _safe_render_final_state(
                        msg,
                        html_text=f"<tg-emoji emoji-id='{emoji_id}'>🕊</tg-emoji>",
                        plain_text="🕊",
                        reply_markup=end_kb,
                    )
                    return
                if game.get("settling"):
                    await _safe_answer(callback_query, "⏳ Завершаю игру…", show_alert=False)
                    return
                if int(game.get("owner_id", 0)) != clicker_id:
                    return
                if int(game.get("message_id", 0)) != msg_id:
                    end_kb = _kb_game_over("Игра завершена")
                    await _safe_render_final_state(
                        msg,
                        html_text=f"<tg-emoji emoji-id='{emoji_id}'>🕊</tg-emoji>",
                        plain_text="🕊",
                        reply_markup=end_kb,
                    )
                    return
                if cb_rev != int(game.get("session_rev", 0)):
                    return
                if bet_amount != int(game.get("bet", 0)):
                    return

                win_mask_list = list(game.get("win_mask", []))
                short_idx = int(game.get("short_idx", -1))
                using_demo = bool(game.get("using_demo"))
                using_0demo = bool(game.get("using_0demo"))
                win_streak = game.get("win_streak", 0)
                lose_streak = game.get("lose_streak", 0)
            else:
                if not (0 <= idx < length) or not (WIRES_MIN <= length <= WIRES_MAX):
                    return
                short_idx = short_idx_cb
                using_demo = False
                using_0demo = False
                win_streak = 0
                lose_streak = 0
                win_mask_list = [(mask_val >> i) & 1 for i in range(length)]

            if not (0 <= idx < len(win_mask_list)):
                return

            is_short = (idx == short_idx)
            is_win = bool(win_mask_list[idx]) and not is_short

            # --- МАСКИРОВОЧНЫЕ ПОДМЕНЫ (только если есть состояние игры) ---
            if state_available:
                # DEMO: если реально победа, может превратиться в проигрыш
                if using_demo and is_win and not is_short:
                    if win_streak >= DEMO_STREAK_BREAK:
                        is_win = False
                        print(f"[WIRES] DEMO streak break: {win_streak} побед подряд → LOSS")
                    elif random.random() < DEMO_MASK_LOSS_PROB:
                        is_win = False
                        print(f"[WIRES] DEMO mask loss: случайный LOSS")

                # 0DEMO: если реально проигрыш (не short), может превратиться в победу
                if using_0demo and not is_win and not is_short:
                    if lose_streak >= ZERO_STREAK_BREAK:
                        is_win = True
                        print(f"[WIRES] 0DEMO streak break: {lose_streak} проигрышей подряд → WIN")
                    elif random.random() < ZERO_MASK_WIN_PROB:
                        is_win = True
                        print(f"[WIRES] 0DEMO mask win: случайный WIN")

            # Обновим счётчики серий
            new_win_streak = win_streak + 1 if is_win else 0
            new_lose_streak = lose_streak + 1 if not is_win and not is_short else 0

            gc_state = await _load_gc_state_for_user(clicker_id)
            has_assignment = gc_state["has_assignment"]
            is_free = gc_state["is_free"]

            if not (has_assignment and is_free) and not using_demo and not using_0demo:
                try:
                    user_balance = int(await db.get_user_balance(clicker_id) or 0)
                except Exception:
                    user_balance = 0
                try:
                    chat_balance_now = await _chat_get_balance(chat_id)
                except Exception:
                    chat_balance_now = 0

                if bet_amount > user_balance:
                    await _safe_answer(callback_query, "✈️ Недостаточно средств", show_alert=False)
                    return
                if bet_amount > chat_balance_now:
                    text = "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В группе недостаточно средств для игры.</b>"
                    rows = []
                    if has_assignment and not is_free:
                        rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
                        rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])
                    kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
                    await _safe_render_final_state(msg, html_text=text, plain_text="В группе недостаточно средств для игры.", reply_markup=kb)
                    if state_available:
                        game.update({"closed": True, "settled": True, "settling": False, "result": "nowin"})
                        active_games_wires[user_id] = game
                        _save_safe(active_games_wires)
                        _finalize_wires_game(user_id, "nowin")
                    return
            else:
                try:
                    chat_balance_now = await _chat_get_balance(chat_id)
                except Exception:
                    chat_balance_now = 0

            now = time.time()

            # ======================= ПОБЕДА =======================
            if is_win and not is_short:
                if state_available:
                    game["settling"] = True
                    active_games_wires[user_id] = game
                    _save_safe(active_games_wires)

                raw_win = int((Decimal(bet_amount) * Decimal(str(PAYOUT_MULTIPLIER))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                profit = max(0, raw_win - bet_amount)

                # Списание demo/0demo (если включены)
                if using_demo:
                    try:
                        await db.deduct_demo_amount(clicker_id, bet_amount)
                        print(f"[WIRES][DEMO] Списано {bet_amount} demo")
                    except Exception as e:
                        dbg_err("DEMO_WIN_DEDUCT_ERR", e)
                elif using_0demo:
                    try:
                        await db.deduct_0demo_amount(clicker_id, bet_amount)
                        print(f"[WIRES][0DEMO] Списано {bet_amount} 0demo")
                    except Exception as e:
                        dbg_err("0DEMO_WIN_DEDUCT_ERR", e)

                if has_assignment:
                    try:
                        await gc_process_bet(user_id=clicker_id, event_chat_id=chat_id, bet=profit, outcome="+")
                    except Exception as e:
                        dbg_err("GC_WIN_ERR", e)

                if has_assignment and is_free:
                    await _mark_user_game_activity(clicker_id, reason="win_free")
                    btn_kb = _kb_paid(f"+{_fmt_int(profit)}")
                    await _safe_render_final_state(msg, html_text="<tg-emoji emoji-id='5235942712988961539'>😎</tg-emoji>", plain_text="⚡️", reply_markup=btn_kb)
                    if state_available:
                        game.update({"settled": True, "closed": True, "settling": False, "result": "win", "win_streak": new_win_streak, "lose_streak": new_lose_streak})
                        active_games_wires[user_id] = game
                        _save_safe(active_games_wires)
                        _finalize_wires_game(user_id, "win")
                    try:
                        await db.add_xp_to_games(clicker_id)
                    except Exception:
                        pass
                    return

                pay = min(profit, max(0, chat_balance_now))
                if pay <= 0:
                    await _safe_render_final_state(
                        msg,
                        html_text=f"💭 <b>На балансе группы недостаточно кут для выплаты выигрыша\n💸 Баланс группы : {chat_balance_now} кут</b>",
                        plain_text=f"На балансе группы недостаточно кут для выплаты выигрыша. Баланс группы: {chat_balance_now} кут",
                        reply_markup=None,
                    )
                    if state_available:
                        game.update({"settled": True, "closed": True, "settling": False, "result": "nowin"})
                        active_games_wires[user_id] = game
                        _save_safe(active_games_wires)
                        _finalize_wires_game(user_id, "nowin")
                    return

                await _chat_minus(chat_id, int(pay))
                await _user_plus(clicker_id, int(pay))
                try:
                    await db.cutehistory_plus(clicker_id, int(pay), "+ провода")
                except Exception as e:
                    dbg_err("HISTORY_PLUS_WIN_ERR", e)
                try:
                    await db.update_user_wins(clicker_id, 1, bot1, ref_coin)
                except Exception as e:
                    dbg_err("WINS_WIN_ERR", e)
                try:
                    await db.update_user_winamount(clicker_id, int(pay))
                    await db.update_game_last_activity(clicker_id)
                except Exception as e:
                    dbg_err("WINAMOUNT_WIN_ERR", e)
                try:
                    await db.add_xp_to_games(clicker_id)
                except Exception:
                    pass
                await _mark_user_game_activity(clicker_id, reason="win")
                btn_kb = _kb_paid(f"{_fmt_int(pay)} кут")
                await _safe_render_final_state(msg, html_text="<tg-emoji emoji-id='5235942712988961539'>😎</tg-emoji>", plain_text="⚡️", reply_markup=btn_kb)
                if state_available:
                    game.update({"settled": True, "closed": True, "settling": False, "result": "win", "win_streak": new_win_streak, "lose_streak": new_lose_streak})
                    active_games_wires[user_id] = game
                    _save_safe(active_games_wires)
                    _finalize_wires_game(user_id, "win")

            # ======================= ЗАМЫКАНИЕ =======================
            elif is_short:
                if state_available:
                    game["settling"] = True
                    active_games_wires[user_id] = game
                    _save_safe(active_games_wires)

                # ЗАМЫКАНИЕ: НЕ СПИСЫВАЕМ demo/0demo, только основной баланс
                if has_assignment:
                    try:
                        await gc_process_bet(user_id=clicker_id, event_chat_id=chat_id, bet=bet_amount, outcome="-")
                    except Exception as e:
                        dbg_err("GC_SHORT_ERR", e)

                if has_assignment and is_free:
                    await _mark_user_game_activity(clicker_id, reason="short_free")
                else:
                    await _user_minus(clicker_id, bet_amount)
                    await _mark_user_game_activity(clicker_id, reason="short")
                    try:
                        await db.cutehistory_minus(clicker_id, bet_amount, "- провода (замыкание)")
                    except Exception as e:
                        dbg_err("HISTORY_MINUS_SHORT_ERR", e)
                    try:
                        await db.update_user_loose(clicker_id, 1, bot1, ref_coin)
                        await db.update_game_last_activity(clicker_id)
                    except Exception as e:
                        dbg_err("LOOSE_SHORT_ERR", e)
                    await _home_take_and_log_wires_short(bot=bot1, user_id=clicker_id, loss=bet_amount)

                btn_kb = _kb_game_over("ЗАМЫКАНИЕ")
                await _safe_render_final_state(msg, html_text="<tg-emoji emoji-id='4958479549265347295'>⚡️</tg-emoji>", plain_text="⚡️", reply_markup=btn_kb)
                if state_available:
                    game.update({"settled": True, "closed": True, "settling": False, "result": "short", "win_streak": 0, "lose_streak": new_lose_streak})
                    active_games_wires[user_id] = game
                    _save_safe(active_games_wires)
                    _finalize_wires_game(user_id, "short")
                try:
                    await db.add_xp_to_games(clicker_id)
                except Exception:
                    pass

            # ======================= ПРОИГРЫШ =======================
            else:  # not is_win and not is_short
                if state_available:
                    game["settling"] = True
                    active_games_wires[user_id] = game
                    _save_safe(active_games_wires)

                # Для обычного проигрыша (не замыкание) списываем demo/0demo, если они были включены
                if using_demo:
                    try:
                        await db.deduct_demo_amount(clicker_id, bet_amount)
                        print(f"[WIRES][DEMO] Списано {bet_amount} demo (LOSS)")
                    except Exception as e:
                        dbg_err("DEMO_LOSS_DEDUCT_ERR", e)
                elif using_0demo:
                    try:
                        await db.deduct_0demo_amount(clicker_id, bet_amount)
                        print(f"[WIRES][0DEMO] Списано {bet_amount} 0demo (LOSS)")
                    except Exception as e:
                        dbg_err("0DEMO_LOSS_DEDUCT_ERR", e)
                    # Возврат долга при 0demo (только для обычного проигрыша, не для замыкания)
                    await force_repay_debt(clicker_id, bet_amount)

                if has_assignment:
                    try:
                        await gc_process_bet(user_id=clicker_id, event_chat_id=chat_id, bet=bet_amount, outcome="-")
                    except Exception as e:
                        dbg_err("GC_LOSS_ERR", e)

                if has_assignment and is_free:
                    await _mark_user_game_activity(clicker_id, reason="loss_free")
                else:
                    await _user_minus(clicker_id, bet_amount)
                    await _mark_user_game_activity(clicker_id, reason="loss")
                    try:
                        await db.cutehistory_minus(clicker_id, bet_amount, "- провода")
                    except Exception as e:
                        dbg_err("HISTORY_MINUS_LOSS_ERR", e)
                    try:
                        await db.update_user_loose(clicker_id, 1, bot1, ref_coin)
                        await db.update_game_last_activity(clicker_id)
                    except Exception as e:
                        dbg_err("LOOSE_LOSS_ERR", e)
                    await _chat_plus(chat_id, bet_amount)

                btn_kb = _kb_game_over("Игра завершена")
                await _safe_render_final_state(msg, html_text="<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji>", plain_text="💥", reply_markup=btn_kb)
                if state_available:
                    game.update({"settled": True, "closed": True, "settling": False, "result": "lose", "win_streak": new_win_streak, "lose_streak": new_lose_streak})
                    active_games_wires[user_id] = game
                    _save_safe(active_games_wires)
                    _finalize_wires_game(user_id, "lose")
                try:
                    await db.add_xp_to_games(clicker_id)
                except Exception:
                    pass

            try:
                last_provoda_time.setdefault(chat_id, {})[clicker_id] = now
            except Exception:
                pass
            try:
                await asyncio.sleep(colld_ball)
            except Exception:
                pass

        finally:
            _wires_inflight.discard(inflight_key)


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith(CB_HDR + "_"))
async def wires_header_hint(c: types.CallbackQuery):
    await _safe_answer(c, "Выберите один из проводов ниже", show_alert=True)


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith(CB_CNT + "_"))
async def wires_count_hint(c: types.CallbackQuery):
    await _safe_answer(c, "Есть победные провода и один провод с замыканием ⚡️", show_alert=True)


@dp.callback_query(lambda c: c.data == CB_END)
async def wires_end_stub(call: types.CallbackQuery):
    await _safe_answer(call, "Игра завершена.", show_alert=False)


@dp.callback_query(lambda c: c.data == CB_PAID)
async def wires_paid_stub(call: types.CallbackQuery):
    await _safe_answer(call, "Выплата зафиксирована ✅", show_alert=False)