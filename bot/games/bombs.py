# -*- coding: utf-8 -*-
"""
Бомбы - полная версия с интеграцией Jericho и маскировочными механиками.
Локально:
  - demo-режим: поле без бомб (SAFE + NUKE). Иногда SAFE превращается в BOMB.
  - 0demo-режим: поле без безопасных клеток (BOMB + NUKE). Иногда BOMB превращается в SAFE.
Долг списывается через force_repay_debt при любом проигрыше в 0demo-режиме.
ВАЖНО: даже при наличии demo/0demo пользователь НЕ может начать игру,
если его основной баланс (или баланс челленджа) меньше ставки.
"""

from aiogram import types
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

import asyncio
import random
import time
import re

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Set, Tuple, Dict

from bot.config.config import *  # noqa
from bot.funcs.func import *     # noqa
from bot.db_create.db import *   # noqa
from bot.design.buttons import * # noqa

from bot.games.group_only import reject_if_private_game
from bot.funcs.tech_home_log import safe_send_tech_log
from main import (
    bot1, dp, db,
    bombs_user_game_data, button_bombs_user_game_data,  # noqa
    bombs_positions, user_message_bombss, pressed_users,  # noqa
    pending_context, send_invoice_to_user, phrases12312,
    gc_process_bet,
    TECH_CHAT_ID,
    LazyGameStore,
    jericho_check, welcome_back_gift, newbie_safety_net, force_repay_debt
)

SESSION_TTL = 20 * 60
PHRASES_TOO_FAST = ("Миг… (0.5 сек)", "Не спеши - полсекунды 🙂")

DEBUG_BOMBS = True
DEBUG_BOMBS_FIELD = True
processed_actions_bombs = LazyGameStore("processed_actions_bombs")

# Маскировочные механики
DEMO_MASK_LOSS_PROB = 0.45               # вероятность подмены SAFE → BOMB в demo-режиме
DEMO_STREAK_BREAK = 3                    # после скольких побед подряд принудительно BOMB
ZERO_MASK_WIN_PROB = 0.12                # вероятность подмены BOMB → SAFE в 0demo-режиме
ZERO_STREAK_BREAK = 3                    # после скольких проигрышей подряд принудительно SAFE

try:
    from main import get_random_eagle_emoji_id  # noqa
except Exception:
    def get_random_eagle_emoji_id():
        return "5204467307153234577"

_last_click: Dict[int, float] = {}
_game_locks: Dict[int, asyncio.Lock] = {}
_closed_msgs: Set[Tuple[int, int]] = set()
_inflight: Set[Tuple[int, int]] = set()
_pending_click: Dict[Tuple[int, int], str] = {}


# ------------------------- DEBUG -------------------------
def _ts() -> str:
    return time.strftime("%H:%M:%S", time.localtime())


def dbg(stage: str, **kw) -> None:
    if not DEBUG_BOMBS:
        return
    parts = [f"[{_ts()}][BOMBS][{stage}]"] + [f"{k}={v}" for k, v in kw.items()]
    try:
        print(" ".join(parts), flush=True)
    except Exception:
        pass


def dbg_err(stage: str, e: Exception) -> None:
    if not DEBUG_BOMBS:
        return
    try:
        import traceback
        print(
            f"[{_ts()}][BOMBS][ERROR][{stage}] {e}\n"
            f"{''.join(traceback.format_exception(type(e), e, e.__traceback__))}",
            flush=True
        )
    except Exception:
        pass


# ------------ АКТИВНОСТЬ БАЛАНСА ------------
async def _mark_user_game_activity(user_id: int, reason: str = "") -> None:
    try:
        await db.touch_balance_last_active(int(user_id), set_active_status=True)
        dbg("ACTIVITY_TOUCH_OK", user_id=user_id, reason=reason)
    except Exception as e:
        dbg_err(f"ACTIVITY_TOUCH_ERR_{reason}", e)


# ------------ УТИЛИТЫ ХРАНИЛИЩ ------------
def _store_save_safe(store):
    try:
        store.save()
    except Exception:
        pass


def _mark_action_processed(key: str):
    try:
        processed_actions_bombs[key] = 1
        _store_save_safe(processed_actions_bombs)
    except Exception:
        processed_actions_bombs[key] = 1


def _is_action_processed(key: str) -> bool:
    try:
        return key in processed_actions_bombs
    except Exception:
        return bool(processed_actions_bombs.get(key))


# ------------ МАТЕМАТИКА / ФОРМАТЫ ------------
def _dec(x) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal(0)


def _fmt_kut(x) -> str:
    try:
        return "{:,.0f}".format(Decimal(str(x))).replace(",", ".")
    except Exception:
        return str(x)


def _gain_per_click(grid_size: int = GRID_SIZE, bomb_count: int = BOMB_COUNT, nuke_count: int = 0) -> Decimal:
    safe_cells = grid_size - bomb_count - nuke_count
    if safe_cells <= 0 or grid_size <= 0:
        return Decimal("0")
    p_safe = Decimal(safe_cells) / Decimal(grid_size)
    if p_safe <= 0:
        return Decimal("0")
    k_fair = (Decimal("1") / p_safe) - Decimal("1")
    k = k_fair * (Decimal("1") - HOUSE_EDGE)
    return k.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _current_gain_per_click(nuke_count: int) -> Decimal:
    if INCREMENT_MODE.upper() == "FAIR":
        return _gain_per_click(GRID_SIZE, BOMB_COUNT, nuke_count)
    return max(Decimal("0"), FIXED_GAIN_PER_CLICK).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


# ------------ GC-обёртка ------------
async def _gc_call(user_id: int, chat_id: int, bet: int, outcome: str, label: str):
    print(f"[GC_HOOK][BOMBS] BEFORE gc_process_bet ({label}) bet={bet} outcome={outcome}")
    try:
        res = await gc_process_bet(
            user_id=user_id,
            event_chat_id=chat_id,
            bet=bet,
            outcome=outcome,
        )
        print("[GC_HOOK][BOMBS] AFTER gc_process_bet, res =", res)
    except Exception as e:
        dbg_err("GC_CALL_ERR", e)


# ------------ БЕЗОПАСНЫЕ ОТВЕТЫ / РЕДАКТИРОВАНИЯ ------------
async def _safe_answer(cb: CallbackQuery, text: str = "", show_alert: bool = False) -> None:
    try:
        await cb.answer(text, show_alert=show_alert, cache_time=0)
    except Exception:
        pass


async def _retry_edit(fn, *args, **kwargs):
    delay = EDIT_RETRY_DELAY
    for _ in range(EDIT_RETRY_MAX):
        try:
            return await fn(*args, **kwargs)
        except (TelegramBadRequest, TelegramAPIError) as e:
            low = str(e).lower()
            if "message is not modified" in low:
                return
            retry_after = getattr(e, "retry_after", None)
            await asyncio.sleep(retry_after or delay)
            delay = min(delay * 2, 1.0)
        except Exception:
            await asyncio.sleep(delay)
            delay = min(delay * 2, 1.0)


async def _safe_edit_text(
    msg: Optional[types.Message],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    chat_id: Optional[int] = None,
    message_id: Optional[int] = None
) -> None:
    if msg:
        await _retry_edit(
            msg.edit_text,
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    elif chat_id and message_id:
        await _retry_edit(
            bot1.edit_message_text,
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )


async def _safe_edit_reply_markup(msg: types.Message, reply_markup: InlineKeyboardMarkup) -> None:
    await _retry_edit(msg.edit_reply_markup, reply_markup=reply_markup)


def _get_game_lock(owner_id: int) -> asyncio.Lock:
    lock = _game_locks.get(owner_id)
    if lock is None:
        lock = asyncio.Lock()
        _game_locks[owner_id] = lock
    return lock


# ------------ ОБЁРТКИ БАЛАНСОВ ------------
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
        cur = _dec(await db.get_user_balance(int(user_id)) or 0)
        newv = max(Decimal(0), cur - _dec(amt))
        new_val = await db.update_user_balance(int(user_id), int(newv))
        return new_val is not None
    except Exception:
        return False


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
        cur = _dec(await db.get_user_balance(int(user_id)) or 0)
        newv = max(Decimal(0), cur + _dec(amt))
        await db.update_user_balance(int(user_id), int(newv))
        return True
    except Exception:
        return False


async def _chat_plus(chat_id: int, amount: int) -> None:
    amt = int(amount)
    if amt <= 0:
        return
    try:
        await db.update_chat_balance(bot1, int(chat_id), amt)
        return
    except Exception:
        pass
    try:
        await db.update_chat_balance(int(chat_id), amt)
    except Exception:
        pass


async def _chat_minus(chat_id: int, amount: int) -> None:
    amt = int(amount)
    if amt <= 0:
        return
    try:
        await db.update_chat_balance_minus(int(chat_id), amt)
        return
    except Exception:
        pass
    try:
        await db.update_chat_balance(bot1, int(chat_id), -amt)
    except Exception:
        pass


async def _chat_get_balance(chat_id: int) -> Decimal:
    try:
        return _dec(await db.get_chat_balance(bot1, int(chat_id)) or 0)
    except Exception:
        try:
            return _dec(await db.get_chat_balance(int(chat_id)) or 0)
        except Exception:
            return Decimal(0)


# ------------ “ДОМ”: NUKE лог ------------
async def _home_take_and_log_bombs_nuke(*, user_id: int, loss: int, source_chat_id: int, msg_id: int) -> None:
    try:
        await _chat_plus(int(TECH_CHAT_ID), int(loss))
        try:
            receiver_name = await db.get_user_first_name(int(user_id))
        except Exception:
            receiver_name = "Игрок"
        try:
            receiver_username = await db.get_username_by_user_id(int(user_id))
        except Exception:
            receiver_username = None
        try:
            name_link1 = await create_user_link(int(user_id), receiver_name, receiver_username)
        except Exception:
            name_link1 = str(receiver_name or "Игрок")
        await db.add_home_amount(user_id=user_id, amount=loss)
        chat_balance = await db.get_chat_balance(bot1, -1003855337972)

        bomb_emoji_html = '<tg-emoji emoji-id="5469654973308476699">💣</tg-emoji>'

        # Кнопка с именем: если есть username → ссылка на профиль, иначе → заглушка
        if receiver_username and isinstance(receiver_username, str):
            # Telegram требует полный URL
            profile_url = f"https://t.me/{receiver_username.strip()}"
            row1_btn = InlineKeyboardButton(
                text=f"{receiver_name}",    # без иконки, т.к. url-кнопка не поддерживает icon_custom_emoji_id
                url=profile_url
            )
        else:
            # если username нет, делаем обычную кнопку
            row1_btn = InlineKeyboardButton(
                text=f"{receiver_name}",
                callback_data="pass",
                icon_custom_emoji_id="5447644863644320013"   # иконка применима только здесь
            )

        # Собираем клавиатуру: каждый смысловой блок - одна кнопка в столбце
        inline_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Бомбы",
                        callback_data="pass",
                        icon_custom_emoji_id="6028346797368283073"  # ✈️
                    )
                ],
                [row1_btn],
                [
                    InlineKeyboardButton(
                        text=f"+ {_fmt_kut(loss)} на чёрный рынок",
                        callback_data="pass"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{_fmt_kut(chat_balance)} кут доступно",
                        callback_data="pass"
                    )
                ]
            ]
        )

        # Лог в TECH_CHAT: chat not found не должен ронять партию.
        fallback_text = (
            f"💣 Бомбы [Ядерный удар]\n"
            f"⭐️ {name_link1}\n"
            f"<blockquote><b>+ {_fmt_kut(loss)} на чёрный рынок</b></blockquote>\n"
            f"<blockquote><b>{_fmt_kut(chat_balance)} кут доступно для выкупов</b></blockquote>"
        )
        await safe_send_tech_log(
            bot1,
            int(TECH_CHAT_ID),
            html=bomb_emoji_html,
            reply_markup=inline_kb,
            fallback_html=fallback_text,
            tag="BOMBS][NUKE_LOG_SEND",
        )
    except Exception as e:
        dbg_err("NUKE_LOG_ERR", e)


# ------------ ПОЛЕ / DEBUG-ПЕЧАТЬ ------------
def _debug_print_field(bombs_set: Set[int], nukes_set: Set[int]) -> None:
    if not DEBUG_BOMBS_FIELD:
        return
    try:
        print(f"[{_ts()}][BOMBS][FIELD] full outcomes:", flush=True)
        for r in range(ROW_LEN):
            row = []
            for c in range(ROW_LEN):
                idx = r * ROW_LEN + c
                if idx in nukes_set:
                    row.append("☢️")
                elif idx in bombs_set:
                    row.append("💥")
                else:
                    row.append("🍀")
            print(f"  {r + 1:02d} | {'  '.join(row)}", flush=True)
        print(f"[{_ts()}][BOMBS][FIELD_IDX] indexes:", flush=True)
        for r in range(ROW_LEN):
            row = []
            for c in range(ROW_LEN):
                idx = r * ROW_LEN + c
                row.append(f"{idx:02d}")
            print(f"  {r + 1:02d} | {'  '.join(row)}", flush=True)
        print(f"[{_ts()}][BOMBS][FIELD_END]\n", flush=True)
    except Exception:
        pass


# ------------ КЛАВИАТУРА ------------
def _build_bombs_markup(owner_id: int, bet: Decimal, opened: Set[int], withdraw_now: Decimal, session_rev: int) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for i in range(GRID_SIZE):
        if i % ROW_LEN == 0:
            rows.append([])
        if i in opened:
            rows[-1].append(InlineKeyboardButton(text=" ", callback_data="none", style="success"))
        else:
            rows[-1].append(
                InlineKeyboardButton(
                    text=" ",
                    callback_data=f"bomb_{owner_id}_{int(bet)}_{i}_{session_rev}",
                    style="default"
                )
            )
    if withdraw_now > 0:
        rows.append([InlineKeyboardButton(
            text=f"{_fmt_kut(withdraw_now)} кут",
            callback_data=f"2412bombsskukota_{_fmt_kut(withdraw_now)}",
            style="success",
            icon_custom_emoji_id="6028338546736107668"
        )])
        rows.append([InlineKeyboardButton(
            text="Остановить игру",
            callback_data=f"bostop_{owner_id}_{int(bet)}_{session_rev}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ------------ СЕРВИС ------------
async def _deactivate_previous_game_ui(user_id: int) -> None:
    try:
        prev_msg_id = user_message_bombss.get(user_id)
        if not prev_msg_id:
            return
        prev_data = bombs_user_game_data.get(user_id) or {}
        chat_id = prev_data.get("chat_id")
        if not chat_id:
            return
        key = (int(chat_id), int(prev_msg_id))
        if key in _closed_msgs:
            return
        end_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Игра завершена", callback_data="none", style="default")]]
        )
        try:
            emoji_id = get_random_eagle_emoji_id()
            await bot1.edit_message_text(
                chat_id=chat_id,
                message_id=prev_msg_id,
                text=f"<tg-emoji emoji-id='{emoji_id}'>🕊</tg-emoji>",
                reply_markup=end_kb,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            try:
                await bot1.edit_message_reply_markup(chat_id=chat_id, message_id=prev_msg_id, reply_markup=end_kb)
            except Exception:
                pass
        _closed_msgs.add(key)
        _finalize_game(user_id, prev_msg_id)
    except Exception:
        pass


def _finalize_game(uid: int, msg_id: Optional[int] = None) -> None:
    tip_chat = None
    try:
        st = bombs_user_game_data.get(uid) or {}
        if isinstance(st, dict):
            tip_chat = st.get("chat_id")
        if msg_id and bombs_user_game_data.get(uid, {}).get("message_id") == msg_id:
            bombs_user_game_data.pop(uid, None)
    except Exception:
        bombs_user_game_data.pop(uid, None)
    try:
        if user_message_bombss.get(uid) == msg_id:
            user_message_bombss.pop(uid, None)
    except Exception:
        pass
    try:
        bombs_positions.pop(uid, None)
    except Exception:
        pass
    _store_save_safe(bombs_user_game_data)
    _store_save_safe(bombs_positions)
    _store_save_safe(user_message_bombss)
    asyncio.create_task(newbie_safety_net(uid))
    async def _ob_done():
        try:
            from bot.funcs.onboarding import onboarding_notify_game_finished
            await onboarding_notify_game_finished(uid, message_id=msg_id, chat_id=tip_chat)
        except Exception:
            pass
    asyncio.create_task(_ob_done())


async def _session_ttl_watcher(owner_id: int, msg_id: int, chat_id: int):
    try:
        await asyncio.sleep(SESSION_TTL)
        key = (int(chat_id), int(msg_id))
        if key in _closed_msgs:
            return
        end_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Игра завершена", callback_data="none")]]
        )
        emoji_id = get_random_eagle_emoji_id()
        await _safe_edit_text(None, f"<tg-emoji emoji-id='{emoji_id}'>🕊</tg-emoji>", end_kb, chat_id=chat_id, message_id=msg_id)
        _closed_msgs.add(key)
        _finalize_game(owner_id, msg_id)
    except Exception:
        pass


# ========================= СТАРТ ИГРЫ =========================
@dp.message(lambda m: isinstance(m.text, str) and re.match(r"^\s*(бомбы|бомба)\b", m.text.strip().lower()))
async def bombs(message: Message):
    if await reject_if_private_game(message):
        return
    text_raw = (message.text or "").strip()
    if not text_raw:
        return

    parts_raw = text_raw.split()
    if not parts_raw:
        return

    cmd = parts_raw[0].lower()
    if cmd not in ("бомба", "бомбы"):
        return

    if len(parts_raw) >= 2:
        bet_token = (parts_raw[1] or "").strip()
    else:
        bet_token = ""

    if not bet_token:
        m = re.search(r"(\d{1,12})", text_raw)
        if not m:
            return
        bet_token = m.group(1)

    if not bet_token.isdigit():
        m = re.search(r"(\d{1,12})", text_raw)
        if not m:
            return
        bet_token = m.group(1)

    bet_int = int(bet_token)
    if bet_int <= 0:
        return

    if bet_int < int(bomb_MIN_BET):
        await message.reply(
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Минимальная ставка {bomb_MIN_BET} кут.</b>",
            parse_mode="HTML", disable_web_page_preview=True
        )
        return

    bet_dec = _dec(bet_int)

    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)


    max_bet = int(bomb_MAX_BET)
    try:
        gc_bet_limit = await db.gc_get_bet_limit_for_user(user_id)
        if gc_bet_limit is not None:
            try:
                lim = int(gc_bet_limit)
                if lim > 0:
                    max_bet = min(max_bet, lim)
            except Exception:
                pass
    except Exception as e:
        dbg_err("BET_LIMIT_ERR", e)

    if bet_int > int(max_bet):
        await message.reply(
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Максимальная ставка в этой игре {_fmt_kut(max_bet)} кут</b>",
            parse_mode="HTML", disable_web_page_preview=True
        )
        return

    # ---------- ЧЕЛЛЕНДЖ ----------
    has_assignment = False
    is_free = False
    current_two = 0
    target_amount = 0

    try:
        assignment = await db.get_active_gc_assignment(user_id)
        if assignment and (str(assignment.get("status") or "").lower() == "active"):
            has_assignment = True
            try:
                is_free = bool(await db.gc_active_is_free(user_id))
            except Exception:
                is_free = False
            try:
                current_two = int(await db.gc_get_current_two_balance(user_id) or 0)
            except Exception:
                current_two = 0
            try:
                target_amount = int(assignment.get("target_amount") or 0)
            except Exception:
                target_amount = 0
    except Exception as e:
        dbg_err("GC_ASSIGN_READ_ERR", e)

    # ---------- НОВИЧОК И WELCOME BACK ----------
    try:
        if await db.get_newbie_expires_at(user_id) is None:
            from datetime import datetime, timedelta, timezone
            expires = datetime.now(timezone.utc) + timedelta(hours=random.uniform(0.5, 24.0))
            await db.set_newbie_expires_at(user_id, expires)
            print(f"[BOMBS] Установлен newbie_expires_at для {user_id}: {expires}")
    except Exception as e:
        print(f"[BOMBS] Ошибка инициализации новичка: {e}")
    await welcome_back_gift(user_id)

    # ---------- JERICHO (только определение режима, без автоматического доливания) ----------
    using_demo = False
    using_0demo = False

    demo_balance = int(await db.get_user_demo(user_id) or 0)
    zero_demo_balance = int(await db.get_user_0demo(user_id) or 0)
    print(f"[BOMBS] Балансы: demo={demo_balance}, 0demo={zero_demo_balance}")

    if not has_assignment:
        print(f"[BOMBS] 🔮 Вызов Jericho")
        decision = await jericho_check(user_id, bet_int, game_name="бомбы")
        print(decision["debug"])

        if decision["action"] in ("force_win", "force_loss", "near_miss"):
            if decision["action"] == "force_win":
                if demo_balance >= bet_int:
                    using_demo = True
                    print("[BOMBS] Режим: demo (force_win, demo хватает)")
                else:
                    print("[BOMBS] Режим: force_win, но demo недостаточно → обычный")
            else:  # force_loss / near_miss
                if zero_demo_balance >= bet_int:
                    using_0demo = True
                    print("[BOMBS] Режим: 0demo (force_loss, 0demo хватает)")
                else:
                    print("[BOMBS] Режим: force_loss, но 0demo недостаточно → обычный")
        else:
            if demo_balance >= bet_int:
                using_demo = True
                print("[BOMBS] Режим: demo (хватает на ставку)")
            elif zero_demo_balance >= bet_int:
                using_0demo = True
                print("[BOMBS] Режим: 0demo (хватает на ставку)")
            else:
                print("[BOMBS] Режим: обычный")

    # ---------- ПРОВЕРКА БАЛАНСА ПОЛЬЗОВАТЕЛЯ (ОБЯЗАТЕЛЬНАЯ) ----------
    if has_assignment and is_free:
        if bet_int > current_two:
            progress_text = f"{current_two}/{target_amount}" if target_amount > 0 else f"{current_two}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=f"Баланс челленджа : {progress_text} кут", callback_data="noop")],
                    [InlineKeyboardButton(text="Недостаточно кут", callback_data="noop")],
                ],
            )
            await message.reply("😓", reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
            return
    else:
        # Обычный режим – проверяем основной баланс (даже если using_demo/using_0demo)
        user_balance = _dec(await db.get_user_balance(user_id) or 0)
        if bet_dec > user_balance:
            try:
                bot_username = await get_bot_username_by_token(TOKEN)
            except Exception:
                bot_username = "CuteGamingBot"

            stars = (bet_dec * _dec(donate_bet)).quantize(Decimal("1.000000"), rounding=ROUND_HALF_UP)
            stars_str = format(stars.normalize(), "f")
            pending_context[user_id] = {"stars_amount": stars_str, "sent": False}

            rows = [
                [InlineKeyboardButton(
                    text=f"💫 Купить {_fmt_kut(bet_int)} кут 💰",
                    url=f"https://t.me/{bot_username}?start=insert_{stars_str}_+"
                )],
                [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")],
            ]
            if has_assignment and not is_free:
                rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
                rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])

            await message.reply(
                "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            async def _bg_invoice():
                try:
                    await asyncio.sleep(timeoutdonate)
                    ctx = pending_context.get(user_id)
                    if ctx and not ctx.get("sent"):
                        invoice_message = await send_invoice_to_user(message, stars_str)
                        pending_context[user_id]["manual_message_id"] = invoice_message.message_id
                except Exception:
                    pass

            asyncio.create_task(_bg_invoice())
            return

    # ---------- ПРОВЕРКА БАЛАНСА ГРУППЫ ----------
    chat_balance = await _chat_get_balance(chat_id)
    if bet_dec > chat_balance:
        rows = []
        if has_assignment and not is_free:
            rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
            rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])

        await message.reply(
            "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В группе недостаточно средств для игры.</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    lock = _get_game_lock(user_id)
    async with lock:
        await _deactivate_previous_game_ui(user_id)

        prev = bombs_user_game_data.get(user_id) or {}
        session_rev = int(prev.get("session_rev", 0)) + 1

        all_idxs = list(range(GRID_SIZE))
        random.shuffle(all_idxs)

        # Генерация поля с учётом demo / 0demo
        if using_0demo:
            nuke_count = random.randint(NUKE_MIN, NUKE_MAX)
            nukes_set = set(random.sample(all_idxs, nuke_count))
            bombs_set = set(all_idxs) - nukes_set
        elif using_demo:
            bombs_set = set()
            nuke_count = random.randint(NUKE_MIN, NUKE_MAX)
            nukes_set = set(all_idxs[:nuke_count])
        else:
            bombs_set = set(all_idxs[:BOMB_COUNT])
            nuke_count = random.randint(NUKE_MIN, NUKE_MAX)
            rest = [x for x in all_idxs[BOMB_COUNT:] if x not in bombs_set]
            nukes_set = set(rest[:nuke_count])

        bombs_positions[user_id] = {"bombs": bombs_set, "nukes": nukes_set}
        _debug_print_field(bombs_set, nukes_set)

        opened: Set[int] = set()
        withdraw_now = Decimal(0)
        markup = _build_bombs_markup(user_id, bet_dec, opened, withdraw_now, session_rev)

        msg = await message.reply(
            "<tg-emoji emoji-id='5469654973308476699'>💣</tg-emoji>",
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

        user_message_bombss[user_id] = msg.message_id
        bombs_user_game_data[user_id] = {
            "message_id": msg.message_id,
            "bet_amount": str(bet_dec),
            "current_win": str(bet_dec),
            "chat_id": int(chat_id),
            "opened": list(opened),
            "session_rev": session_rev,
            "withdraw_locked": False,
            "payout_done": False,
            "has_assignment": has_assignment,
            "is_free": is_free,
            "nuke_count": int(nuke_count),
            "using_demo": using_demo,
            "using_0demo": using_0demo,
            "win_streak": 0,
            "lose_streak": 0,
        }

        _store_save_safe(bombs_positions)
        _store_save_safe(bombs_user_game_data)
        _store_save_safe(user_message_bombss)

        asyncio.create_task(_session_ttl_watcher(user_id, msg.message_id, int(chat_id)))


# ==================== КЛИК ПО КЛЕТКЕ ====================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("bomb_"))
async def bombs_process_bomb_click(callback_query: CallbackQuery):
    uid = int(callback_query.from_user.id)
    msg_id = int(callback_query.message.message_id)
    inflight_key = (msg_id, uid)

    now = time.monotonic()
    if now - _last_click.get(uid, 0.0) < USER_CLICK_COOLDOWN:
        await _safe_answer(callback_query, random.choice(PHRASES_TOO_FAST))
        if inflight_key in _inflight:
            _pending_click[inflight_key] = callback_query.data
        return
    _last_click[uid] = now

    if inflight_key in _inflight:
        _pending_click[inflight_key] = callback_query.data
        await _safe_answer(callback_query, "⏳ Принял. Выполню следом.")
        return

    _inflight.add(inflight_key)
    try:
        await _handle_bomb_click_inner(callback_query, callback_query.data)

        pending = _pending_click.pop(inflight_key, None)
        if pending:
            await _handle_bomb_click_inner(callback_query, pending)

    finally:
        _inflight.discard(inflight_key)


async def _handle_bomb_click_inner(callback_query: CallbackQuery, data: str):
    uid = int(callback_query.from_user.id)
    msg_id = int(callback_query.message.message_id)

    await _safe_answer(callback_query, "")

    parts = data.split("_")
    if len(parts) != 5:
        await _safe_answer(callback_query, "🛠 Ошибка в данных.")
        return

    owner_id = int(parts[1])
    idx = int(parts[3])
    cb_rev = int(parts[4])

    if uid != owner_id:
        await _safe_answer(callback_query, "Это не ваша игра.", True)
        return

    if user_message_bombss.get(uid) != msg_id:
        await _safe_answer(callback_query, "Откройте вашу последнюю игру.", False)
        return

    game = bombs_user_game_data.get(owner_id)
    if not game or int(game.get("message_id", 0)) != msg_id:
        await _safe_answer(callback_query, "🛠 Игра не найдена.")
        return

    session_rev = int(game.get("session_rev", 0))
    if cb_rev != session_rev:
        await _safe_answer(callback_query, "🔄 Клавиатура устарела. Начните заново.", True)
        return

    lock = _get_game_lock(owner_id)
    async with lock:
        action_key = f"cell:{uid}:{session_rev}:{msg_id}:{idx}"
        if _is_action_processed(action_key):
            await _safe_answer(callback_query, "⏳ Уже обработано.")
            return
        _mark_action_processed(action_key)

        has_assignment = bool(game.get("has_assignment"))
        is_free = bool(game.get("is_free"))
        using_demo = bool(game.get("using_demo"))
        using_0demo = bool(game.get("using_0demo"))
        chat_id = int(game.get("chat_id"))

        base_bet = _dec(game.get("bet_amount", "0"))
        if base_bet <= 0:
            await _safe_edit_text(callback_query.message, "💥 <b>Ошибка состояния игры. Начните заново.</b>")
            _finalize_game(uid, msg_id)
            return

        # Проверка баланса только для обычного режима (без demo/0demo и не free-челлендж)
        if not (has_assignment and is_free) and not using_demo and not using_0demo:
            try:
                user_balance = _dec(await db.get_user_balance(uid) or 0)
            except Exception:
                user_balance = Decimal(0)

            group_balance = await _chat_get_balance(chat_id)

            if user_balance < base_bet:
                await _safe_edit_text(
                    callback_query.message,
                    f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Недостаточно средств для игры\n💰 Ваш баланс : {_fmt_kut(user_balance)} кут</b>"
                )
                return

            if group_balance < base_bet:
                await _safe_edit_text(
                    callback_query.message,
                    f"💭 <b>Недостаточно средств на балансе группы для игры\n"
                    f"💸 Баланс группы : {_fmt_kut(group_balance)} кут</b>"
                )
                return

        # Счётчики серий
        win_streak = game.get("win_streak", 0)
        lose_streak = game.get("lose_streak", 0)

        raw_pos = bombs_positions.get(owner_id)
        if isinstance(raw_pos, set):
            bombs_set = set(raw_pos)
            nukes_set = set()
        elif isinstance(raw_pos, dict):
            bombs_set = set(raw_pos.get("bombs", set()))
            nukes_set = set(raw_pos.get("nukes", set()))
        else:
            bombs_set = set()
            nukes_set = set()

        opened: Set[int] = set(game.get("opened", []))

        if idx in opened:
            await _safe_answer(callback_query, "Эта клетка уже открыта.")
            return

        # Реальный исход до подмены
        if idx in nukes_set:
            real_outcome = "NUKE"
        elif idx in bombs_set:
            real_outcome = "BOMB"
        else:
            real_outcome = "SAFE"

        # --- МАСКИРОВОЧНЫЕ ПОДМЕНЫ ---
        if using_demo and real_outcome == "SAFE":
            if win_streak >= DEMO_STREAK_BREAK:
                real_outcome = "BOMB"
                print(f"[BOMBS] DEMO streak break: {win_streak} побед подряд → BOMB")
            elif random.random() < DEMO_MASK_LOSS_PROB:
                real_outcome = "BOMB"
                print(f"[BOMBS] DEMO mask loss: случайный BOMB")

        if using_0demo and real_outcome == "BOMB":
            if lose_streak >= ZERO_STREAK_BREAK:
                real_outcome = "SAFE"
                print(f"[BOMBS] 0DEMO streak break: {lose_streak} проигрышей подряд → SAFE")
            elif random.random() < ZERO_MASK_WIN_PROB:
                real_outcome = "SAFE"
                print(f"[BOMBS] 0DEMO mask win: случайный SAFE")

        # ---------- NUKE ----------
        if real_outcome == "NUKE":
            end_kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(
                    text="ЯДЕРКА",
                    callback_data="none",
                    style="default",
                    icon_custom_emoji_id="5210708139447428888"
                )]]
            )
            await _safe_edit_text(
                callback_query.message,
                "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji>",
                end_kb
            )

            loss_int = int(base_bet)

            if using_demo:
                try:
                    await db.deduct_demo_amount(uid, loss_int)
                except Exception as e:
                    print(f"[BOMBS][DEMO] Ошибка списания demo при NUKE: {e}")
            elif using_0demo:
                try:
                    await db.deduct_0demo_amount(uid, loss_int)
                except Exception as e:
                    print(f"[BOMBS][0DEMO] Ошибка списания 0demo при NUKE: {e}")
                # Возврат долга в 0demo режиме
                await force_repay_debt(uid, loss_int)

            if has_assignment:
                await _gc_call(uid, chat_id, loss_int, "-", "NUKE_HOME")

            if has_assignment and is_free:
                await _mark_user_game_activity(uid, reason="nuke_free")
            else:
                await _user_minus(uid, loss_int)
                await _mark_user_game_activity(uid, reason="nuke")
                try:
                    await db.cutehistory_minus(uid, loss_int, "- бомбы (ядерка домой)")
                except Exception as e:
                    dbg_err("HISTORY_MINUS_NUKE", e)
                try:
                    await db.update_user_loose(uid, 1, bot1, ref_coin)
                    await db.update_game_last_activity(uid)
                except Exception as e:
                    dbg_err("LOOSE_NUKE", e)
                await _home_take_and_log_bombs_nuke(
                    user_id=uid,
                    loss=loss_int,
                    source_chat_id=chat_id,
                    msg_id=msg_id
                )

            lose_streak += 1
            win_streak = 0
            game["win_streak"] = win_streak
            game["lose_streak"] = lose_streak
            bombs_user_game_data[uid] = game
            _finalize_game(uid, msg_id)
            return

        # ---------- BOMB ----------
        if real_outcome == "BOMB":
            end_kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Игра завершена", callback_data="none", style="default")]]
            )
            await _safe_edit_text(
                callback_query.message,
                "<tg-emoji emoji-id='5429444544590541909'>💥</tg-emoji>",
                end_kb
            )

            loss_int = int(base_bet)

            if using_demo:
                try:
                    await db.deduct_demo_amount(uid, loss_int)
                except Exception as e:
                    print(f"[BOMBS][DEMO] Ошибка списания demo при BOMB: {e}")
            elif using_0demo:
                try:
                    await db.deduct_0demo_amount(uid, loss_int)
                except Exception as e:
                    print(f"[BOMBS][0DEMO] Ошибка списания 0demo при BOMB: {e}")
                await force_repay_debt(uid, loss_int)

            if has_assignment:
                await _gc_call(uid, chat_id, loss_int, "-", "LOSS")

            if has_assignment and is_free:
                await _mark_user_game_activity(uid, reason="loss_free")
            else:
                await _user_minus(uid, loss_int)
                await _mark_user_game_activity(uid, reason="loss")
                try:
                    await db.cutehistory_minus(uid, loss_int, "- бомбы")
                except Exception as e:
                    dbg_err("HISTORY_MINUS_LOSS", e)
                await _chat_plus(chat_id, loss_int)
                try:
                    await db.update_user_loose(uid, 1, bot1, ref_coin)
                    await db.update_game_last_activity(uid)
                except Exception as e:
                    dbg_err("LOOSE_LOSS", e)

            lose_streak += 1
            win_streak = 0
            game["win_streak"] = win_streak
            game["lose_streak"] = lose_streak
            bombs_user_game_data[uid] = game
            _finalize_game(uid, msg_id)
            return

        # ---------- SAFE ----------
        nuke_count = int(game.get("nuke_count", len(nukes_set) or 0))
        gain_k = _current_gain_per_click(nuke_count)

        cur_win = _dec(game.get("current_win", game.get("bet_amount", "0")))
        cur_win = (cur_win + (base_bet * gain_k)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        opened.add(idx)
        game["opened"] = list(opened)
        game["current_win"] = str(cur_win)

        win_streak += 1
        lose_streak = 0
        game["win_streak"] = win_streak
        game["lose_streak"] = lose_streak

        withdraw_now = max(Decimal(0), (cur_win - base_bet)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        new_markup = _build_bombs_markup(owner_id, base_bet, opened, withdraw_now, session_rev)
        await _safe_edit_reply_markup(callback_query.message, new_markup)

        bombs_user_game_data[owner_id] = game
        _store_save_safe(bombs_user_game_data)
        _store_save_safe(bombs_positions)


# --------- КНОПКА С СУММОЙ ---------
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("2412bombsskukota_"))
async def bombs_bombsskukota_game(callback_query: CallbackQuery):
    parts = callback_query.data.split("_", 1)
    if len(parts) != 2:
        await _safe_answer(callback_query, "Ошибка: Невалидные данные.", True)
        return
    kut = parts[1]
    phrases = [
        "У тебя уже {kut} кут. Забрать или рискнуть дальше?",
        "Сейчас у тебя {kut} кут. Решай: забрать или продолжить?",
        "Уже {kut} кут. Может, хватит? Или ещё один шаг?",
        "{kut} кут заработано. Забрать или сыграть ещё?",
    ]
    await _safe_answer(callback_query, random.choice(phrases).format(kut=kut), True)


# ================== ОСТАНОВИТЬ ИГРУ (ВЫВОД) ==================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("bostop_"))
async def bombs_stop_game(callback_query: CallbackQuery):
    uid = int(callback_query.from_user.id)
    parts = callback_query.data.split("_")
    if len(parts) != 4:
        await _safe_answer(callback_query, "🛠 Ошибка в данных.")
        return

    owner_id = int(parts[1])
    cb_rev = int(parts[3])

    if uid != owner_id:
        await _safe_answer(callback_query, "Это не ваша игра.", True)
        return

    msg_id = int(callback_query.message.message_id)
    if user_message_bombss.get(uid) != msg_id:
        await _safe_answer(callback_query, "Откройте вашу последнюю игру.", False)
        return

    await _safe_answer(callback_query, "")

    game = bombs_user_game_data.get(owner_id)
    if not game:
        return

    session_rev = int(game.get("session_rev", 0))
    if cb_rev != session_rev:
        await _safe_answer(callback_query, "🔄 Клавиатура устарела. Начните заново.", True)
        return

    lock = _get_game_lock(owner_id)
    async with lock:
        if game.get("payout_done") or game.get("withdraw_locked"):
            return
        game["withdraw_locked"] = True
        bombs_user_game_data[owner_id] = game
        _store_save_safe(bombs_user_game_data)

        action_key = f"wd:{uid}:{session_rev}:{msg_id}"
        if _is_action_processed(action_key):
            return
        _mark_action_processed(action_key)

        has_assignment = bool(game.get("has_assignment"))
        is_free = bool(game.get("is_free"))
        using_demo = bool(game.get("using_demo"))
        using_0demo = bool(game.get("using_0demo"))

        cur_win = _dec(game.get("current_win", game.get("bet_amount", "0")))
        base_bet = _dec(game.get("bet_amount", "0"))
        chat_id = int(game.get("chat_id"))

        net_win = max(Decimal(0), (cur_win - base_bet)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        net_win_int = int(net_win)

        if using_0demo:
            await _safe_answer(callback_query, "Игра завершена.", show_alert=False)
            _finalize_game(uid, msg_id)
            return

        # ---------- DEMO ----------
        if using_demo:
            try:
                await db.deduct_demo_amount(owner_id, int(base_bet))
            except Exception as e:
                print(f"[BOMBS][DEMO] Ошибка списания demo при выводе: {e}")

            group_balance = await _chat_get_balance(chat_id)
            pay = min(net_win, group_balance.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            pay_int = int(max(Decimal(0), pay))
            if pay_int > 0:
                await _chat_minus(chat_id, pay_int)
                await _user_plus(uid, pay_int)
                try:
                    await db.cutehistory_plus(uid, pay_int, "+ бомбы")
                except Exception as e:
                    dbg_err("HISTORY_PLUS_WITHDRAW_DEMO", e)
                try:
                    await db.update_user_winamount(uid, pay_int)
                    await db.update_game_last_activity(uid)
                except Exception as e:
                    dbg_err("WINAMOUNT_WITHDRAW_DEMO", e)
                try:
                    await db.update_user_wins(uid, 1, bot1, ref_coin)
                except Exception as e:
                    dbg_err("WINS_WITHDRAW_DEMO", e)
                await _mark_user_game_activity(uid, reason="withdraw_demo")

            final_kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=f"{_fmt_kut(pay_int)} кут", callback_data="win_amount_callback")]]
            )
            await _safe_edit_text(
                callback_query.message,
                "<tg-emoji emoji-id='5294026527850132517'>🚀</tg-emoji>",
                final_kb
            )

        elif has_assignment and is_free:
            final_kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=f"{_fmt_kut(net_win)} кут", callback_data="win_amount_callback")]]
            )
            await _safe_edit_text(
                callback_query.message,
                "<tg-emoji emoji-id='5294026527850132517'>🚀</tg-emoji>",
                final_kb
            )

            if net_win_int > 0:
                await _gc_call(uid, chat_id, net_win_int, "+", "WITHDRAW_FREE")

            await _mark_user_game_activity(uid, reason="withdraw_free")

        else:
            group_balance = await _chat_get_balance(chat_id)
            pay = min(net_win, group_balance.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            pay_int = int(max(Decimal(0), pay))

            if pay_int <= 0:
                await _safe_edit_text(
                    callback_query.message,
                    f"💭 <b>Недостаточно средств на балансе группы для выплаты выигрыша\n"
                    f"💸 Баланс группы : {_fmt_kut(group_balance)} кут</b>"
                )
                game["payout_done"] = True
                bombs_user_game_data[owner_id] = game
                _store_save_safe(bombs_user_game_data)
                _finalize_game(uid, msg_id)
                return

            await _chat_minus(chat_id, pay_int)
            await _user_plus(uid, pay_int)

            if has_assignment:
                await _gc_call(uid, chat_id, pay_int, "+", "WITHDRAW")

            try:
                await db.cutehistory_plus(uid, pay_int, "+ бомбы")
            except Exception as e:
                dbg_err("HISTORY_PLUS_WITHDRAW", e)

            try:
                await db.update_user_winamount(uid, pay_int)
                await db.update_game_last_activity(uid)
            except Exception as e:
                dbg_err("WINAMOUNT_WITHDRAW", e)

            try:
                await db.update_user_wins(uid, 1, bot1, ref_coin)
            except Exception as e:
                dbg_err("WINS_WITHDRAW", e)

            await _mark_user_game_activity(uid, reason="withdraw")

            final_kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=f"{_fmt_kut(pay_int)} кут", callback_data="win_amount_callback")]]
            )
            await _safe_edit_text(
                callback_query.message,
                "<tg-emoji emoji-id='5294026527850132517'>🚀</tg-emoji>",
                final_kb
            )

        game["payout_done"] = True
        bombs_user_game_data[owner_id] = game
        _store_save_safe(bombs_user_game_data)
        _finalize_game(uid, msg_id)