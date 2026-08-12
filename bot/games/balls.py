# -*- coding: utf-8 -*-
"""
🎱 Шарик – финальная версия с полным Jericho (mode="-") и корректной историей.
• Jericho анализирует агрессию, мартингейл, долги, баланс.
• DEMO-режим: ball/empty → выигрыш (demo списывается); pop → шар лопнул (основной баланс).
• 0DEMO-режим: ball/empty → проигрыш (0demo списывается); pop → шар лопнул (основной баланс).
• Долг гасится ТОЛЬКО при обычном проигрыше (empty) в любом режиме.
  При pop и при выигрыше долг НЕ трогается.
ВАЖНО: даже при наличии demo/0demo пользователь НЕ может начать игру,
если его основной баланс (или баланс челленджа) меньше ставки.
"""

import asyncio, random, time
from typing import Dict, Optional, Tuple, Set

from aiogram import types
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from main import *
from bot.games.group_only import reject_if_private_game
from bot.funcs.func import get_bot_username_by_token
from bot.funcs.tech_home_log import safe_send_tech_log

_ball_session_locks: Dict[int, asyncio.Lock] = {}
_ball_inflight: Set[Tuple[int, int]] = set()

def _get_lock(msg_id: int) -> asyncio.Lock:
    if msg_id not in _ball_session_locks:
        _ball_session_locks[msg_id] = asyncio.Lock()
    return _ball_session_locks[msg_id]

def _fmt_int(n: int) -> str:
    try: return "{:,.0f}".format(int(n)).replace(",", ".")
    except: return str(n)

def _save_safe(obj):
    try: obj.save()
    except: pass

async def _mark_user_game_activity(uid: int, reason: str = ""):
    try:
        await db.touch_balance_last_active(int(uid), set_active_status=True)
        print(f"[BALL][ACTIVITY] OK {uid} ({reason})")
    except Exception as e:
        print(f"[BALL][ACTIVITY] ERR {uid} ({reason}): {e}")

async def _safe_edit_text(msg, text, reply_markup=None, parse_mode="HTML"):
    try:
        await msg.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
    except (TelegramBadRequest, TelegramAPIError) as e:
        if "message is not modified" in str(e).lower(): return
        try:
            await asyncio.sleep(0.15)
            await msg.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
        except: pass
    except: pass

async def _send_invoice_later(message: Message, uid: int, stars_amount: str, delay: float):
    try:
        await asyncio.sleep(delay)
        ctx = pending_context.get(uid)
        if ctx and not ctx.get("sent"):
            invoice_message = await send_invoice_to_user(message, stars_amount)
            pending_context[uid]["manual_message_id"] = invoice_message.message_id
    except: pass

async def _finalize_ball_game(uid: int):
    """Завершает игру, очищает состояние и гасит долг, если он был накоплен."""
    gs = active_games_ball.get(uid)
    repay = 0
    tip_mid = None
    tip_chat = None
    if isinstance(gs, dict):
        repay = int(gs.get("repay_amount", 0))
        tip_mid = gs.get("message_id")
        tip_chat = gs.get("chat_id")
        gs["closed"] = True
        active_games_ball[uid] = gs
        _save_safe(active_games_ball)
    try:
        if user_message_ball.get(uid):
            tip_mid = tip_mid or user_message_ball.get(uid)
            user_message_ball.pop(uid, None)
            _save_safe(user_message_ball)
    except: pass
    if repay > 0:
        print(f"[BALL][DEBT] Гасим долг {repay}")
        await force_repay_debt(uid, repay)
    await newbie_safety_net(uid)
    try:
        from bot.funcs.onboarding import onboarding_notify_game_finished
        await onboarding_notify_game_finished(uid, message_id=tip_mid, chat_id=tip_chat)
    except Exception:
        pass

async def _deactivate_previous_ball_ui(uid: int):
    st = active_games_ball.get(uid) or {}
    if not st or st.get("closed"): return
    mid = user_message_ball.get(uid)
    cid = st.get("chat_id")
    if not mid or not cid: return
    end_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Игра завершена", callback_data="none")]])
    try:
        emoji_id = get_random_eagle_emoji_id()
        await bot1.edit_message_text(chat_id=cid, message_id=mid,
                                     text=f"<tg-emoji emoji-id='{emoji_id}'>🕊</tg-emoji>",
                                     reply_markup=end_kb, parse_mode="HTML")
    except:
        try: await bot1.edit_message_reply_markup(chat_id=cid, message_id=mid, reply_markup=end_kb)
        except: pass

def _find_ball_state_by_message_id(mid: int) -> Optional[tuple[int, dict]]:
    for uid, st in list(active_games_ball.items()):
        try:
            if isinstance(st, dict) and int(st.get("message_id", 0)) == mid:
                return uid, st
        except: continue
    return None

_BTN_TYPES = {"ball": ("✅ Выигрыш", "WIN"), "empty": ("❌ Проигрыш", "LOSS"), "pop": ("🫧 Шар лопнул", "POP")}

def _describe_field_with_mode(kb: InlineKeyboardMarkup, using_demo: bool, using_0demo: bool) -> str:
    mode_str = "DEMO" if using_demo else ("0DEMO" if using_0demo else "Обычный")
    header = f"🎱 Игровое поле (режим: {mode_str})"
    lines = []
    for i, btn in enumerate(kb.inline_keyboard[0], start=1):
        kind = btn.callback_data.split("_")[0]
        if kind == "pop":
            desc = "🫧 Шар лопнул (POP)"
        elif using_demo:
            desc = "(DEMO) Выигрыш"
        elif using_0demo:
            desc = "(0DEMO) Проигрыш"
        else:
            emoji, name = _BTN_TYPES.get(kind, ("❓", "???"))
            desc = f"{emoji} {name}"
        lines.append(f"  [{i}] {desc}   ({btn.callback_data})")
    return f"{header}\n" + "\n".join(lines)

def _build_keyboard_ball(session_rev: int, bet: int, uid: int) -> InlineKeyboardMarkup:
    btns = [
        InlineKeyboardButton(text=" ", callback_data=f"ball_{session_rev}_{bet}_{uid}"),
        InlineKeyboardButton(text=" ", callback_data=f"empty_{session_rev}_{bet}_{uid}"),
        InlineKeyboardButton(text=" ", callback_data=f"pop_{session_rev}_{bet}_{uid}"),
    ]
    random.shuffle(btns)
    return InlineKeyboardMarkup(inline_keyboard=[btns])

async def _load_gc_state_for_user(uid: int) -> dict:
    has_assignment = False; is_free = False; current_two = 0; target_amount = 0
    gc_bet_limit = None
    try:
        gc_bet_limit = await db.gc_get_bet_limit_for_user(uid)
    except Exception as e:
        print(f"[BALL][GC] Лимит ошибка: {e}"); gc_bet_limit = None
    try:
        lim = int(gc_bet_limit) if gc_bet_limit is not None else 0
        if lim <= 0:
            gc_bet_limit = None
        else:
            gc_bet_limit = lim
    except Exception as e:
        print(f"[BALL][GC] Преобразование лимита: {e}")
        gc_bet_limit = None
    try:
        assignment = await db.get_active_gc_assignment(uid)
    except Exception as e:
        print(f"[BALL][GC] Задание ошибка: {e}"); assignment = None
    if assignment and str(assignment.get("status") or "").lower() == "active":
        has_assignment = True
        try: is_free = bool(await db.gc_active_is_free(uid))
        except Exception as e: print(f"[BALL][GC] free ошибка: {e}")
        try:
            v = await db.gc_get_current_two_balance(uid); current_two = int(v or 0)
        except Exception as e: print(f"[BALL][GC] баланс челленджа ошибка: {e}")
        try: target_amount = int(assignment.get("target_amount") or 0)
        except: pass
    return {
        "has_assignment": has_assignment, "is_free": is_free,
        "current_two": int(current_two), "target_amount": int(target_amount),
        "gc_bet_limit": gc_bet_limit,
        "max_bet": int(Balls_MAX_BET),
    }

def _append_regular_assignment_info_rows(rows: list, has_assignment: bool, is_free: bool) -> None:
    if has_assignment and not is_free:
        rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
        rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])

async def _safe_tech_log_pop(*, bot, loss: int, uid: int = None, user_id: int = None) -> None:
    uid = uid if uid is not None else user_id
    if uid is None:
        return
    try:
        await db.update_chat_balance(bot, TECH_CHAT_ID, int(loss))
        receiver_name = await db.get_user_first_name(uid)
        receiver_username = await db.get_username_by_user_id(uid)
        name_link = await create_user_link(uid, receiver_name, receiver_username)
        await db.add_home_amount(user_id=uid, amount=loss)
        chat_balance = await db.get_chat_balance(bot, -1003855337972)   # используем переданный bot, не bot1

        # HTML-эмодзи, единственное содержимое сообщения
        emoji_html = '<tg-emoji emoji-id="5363877049863786071">🎱</tg-emoji>'

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
                        text="Шарик",
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

        # Лог в TECH_CHAT: chat not found не должен ронять партию.
        fallback_text = (
            f"<b>🎱 Шарик [ Шар исчез ]</b>\n"
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
            tag="BALL][POP_LOG_SEND",
        )

    except Exception as e:
        import traceback; print(f"[BALL][POP_LOG] {e}"); traceback.print_exc()

# ============================================================
# СТАРТ ИГРЫ
# ============================================================
@dp.message()
async def balls(message: Message):
    text_raw = (message.text or "").strip()
    if not text_raw: return
    parts = text_raw.split()
    if not parts or parts[0].lower() not in ("шар", "шарик") or len(parts) != 2: return
    bet_token = (parts[1] or "").strip()
    if not bet_token.isdigit(): return
    bet_amount = int(bet_token)
    if await reject_if_private_game(message):
        return

    if bet_amount <= 0 or bet_amount < Balls_MIN_BET:
        await message.reply(f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Минимальная ставка {Balls_MIN_BET} кут.</b>", parse_mode="HTML")
        return

    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)

    gc_state = await _load_gc_state_for_user(user_id)
    has_assignment = bool(gc_state["has_assignment"])
    is_free = bool(gc_state["is_free"])
    current_two = int(gc_state["current_two"])
    target_amount = int(gc_state["target_amount"])
    from bot.funcs.group_balance_level import decide_gc_play_mode, format_game_max_bet_html
    gate = decide_gc_play_mode(
        bet=bet_amount,
        game_max_bet=Balls_MAX_BET,
        has_assignment=has_assignment,
        is_free=is_free,
        gc_bet_limit=gc_state.get("gc_bet_limit"),
    )
    if gate.get("mode") == "reject":
        await message.reply(format_game_max_bet_html(gate.get("max") or Balls_MAX_BET), parse_mode="HTML")
        return
    is_free_play = gate.get("mode") == "free"

    # Новичок + welcome back
    try:
        if await db.get_newbie_expires_at(user_id) is None:
            expires = datetime.now(timezone.utc) + timedelta(hours=random.uniform(0.5, 24.0))
            await db.set_newbie_expires_at(user_id, expires)
            print(f"[BALL] newbie_expires_at установлен: {expires}")
    except Exception as e:
        print(f"[BALL] Ошибка newbie_expires_at: {e}")
    await welcome_back_gift(user_id)

    # ----- Вызов Jericho (только для определения режима, без автоматического доливания) -----
    print(f"\n{'='*60}\n[BALL] Jericho (mode='-') user={user_id} bet={bet_amount}")
    decision = await jericho_check(user_id, bet_amount, game_name="шарик", mode="-")
    print(f"[BALL][JERICHO] action={decision['action']}, reason={decision['reason']}\n{decision['debug']}\n{'='*60}")

    # ----- Режим на основе Jericho и реальных балансов -----
    using_demo = False
    using_0demo = False

    demo_balance = int(await db.get_user_demo(user_id) or 0)
    zero_demo_balance = int(await db.get_user_0demo(user_id) or 0)
    print(f"[BALL] Лимиты: demo={demo_balance}, 0demo={zero_demo_balance}")

    if has_assignment:
        print("[BALL] Активное задание – demo/0demo отключены.")
    else:
        if decision["action"] in ("force_win", "force_loss", "near_miss"):
            # Используем demo/0demo только если их хватает на ставку целиком
            if decision["action"] == "force_win":
                if demo_balance >= bet_amount:
                    using_demo = True
                    print("[BALL] Режим: demo (force_win, demo хватает)")
                else:
                    print("[BALL] Режим: force_win, но demo недостаточно → обычный")
            else:  # force_loss / near_miss
                if zero_demo_balance >= bet_amount:
                    using_0demo = True
                    print("[BALL] Режим: 0demo (force_loss, 0demo хватает)")
                else:
                    print("[BALL] Режим: force_loss, но 0demo недостаточно → обычный")
        else:
            if demo_balance >= bet_amount:
                using_demo = True
                print("[BALL] Режим: demo (хватает на ставку)")
            elif zero_demo_balance >= bet_amount:
                using_0demo = True
                print("[BALL] Режим: 0demo (хватает на ставку)")
            else:
                print("[BALL] Режим: обычный")

    # ----- ПРОВЕРКА БАЛАНСА ПОЛЬЗОВАТЕЛЯ (ОБЯЗАТЕЛЬНАЯ, даже при demo/0demo) -----
    if is_free_play:
        # Бесплатный челлендж: используем баланс челленджа (без БЧ и без ★)
        if bet_amount > current_two:
            progress_text = f"{current_two}/{target_amount}" if target_amount > 0 else f"{current_two}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"Баланс челленджа: {progress_text} кут", callback_data="noop")],
                [InlineKeyboardButton(text="Недостаточно кут", callback_data="noop")],
            ])
            await message.reply("😓", reply_markup=kb, parse_mode="HTML")
            return
    else:
        # Обычный режим: проверяем ТОЛЬКО основной баланс (даже при using_demo/using_0demo)
        user_balance = int(await db.get_user_balance(user_id) or 0)
        if bet_amount > user_balance:
            bot_username = await get_bot_username_by_token(TOKEN)
            stars_amount = str(int(bet_amount * float(donate_bet))) if donate_bet else str(bet_amount)
            pending_context[user_id] = {"stars_amount": stars_amount, "sent": False}
            rows = [
                [InlineKeyboardButton(text=f"💫 Купить {_fmt_int(bet_amount)} кут 💰",
                                      url=f"https://t.me/{bot_username}?start=insert_{stars_amount}_+")],
                [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")],
            ]
            _append_regular_assignment_info_rows(rows, has_assignment, is_free)
            kb = InlineKeyboardMarkup(inline_keyboard=rows)
            await message.reply("<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>", reply_markup=kb, parse_mode="HTML")
            asyncio.create_task(_send_invoice_later(message, user_id, stars_amount, delay=timeoutdonate))
            return

        # ----- ПРОВЕРКА БАЛАНСА ГРУППЫ (не для free) -----
        chat_balance = int(await db.get_chat_balance(bot1, chat_id) or 0)
        if bet_amount > chat_balance:
            rows = []
            _append_regular_assignment_info_rows(rows, has_assignment, is_free)
            kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
            await message.reply("<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В группе недостаточно средств для игры.</b>", reply_markup=kb, parse_mode="HTML")
            return

    try:
        from bot.funcs.group_balance_level import reject_if_bet_over_group_level
        if await reject_if_bet_over_group_level(message, bet_amount, is_free_play=is_free_play):
            return
    except Exception as _gbl_e:
        print(f"[GBL] balls check skip: {_gbl_e!r}")

    # ----- АНТИСПАМ -----
    now = time.time()
    DURATION = delaysssssssssgamesonee.get(chat_id, 0.5)
    if DURATION > 0:
        if chat_id not in last_balls_time: last_balls_time[chat_id] = {}
        last_usage = float(last_balls_time[chat_id].get(user_id, 0))
        if now - last_usage < DURATION:
            remaining = int(DURATION - (now - last_usage))
            await message.reply(f"<tg-emoji emoji-id='5253535126666634933'>⌚️</tg-emoji> <b>Подождите немного</b>", parse_mode="HTML")
            return
        last_balls_time[chat_id][user_id] = now

    if pressed_users_ball.get(user_id):
        await message.reply("<tg-emoji emoji-id='5253535126666634933'>⌚️</tg-emoji> <b>Подождите чуть-чуть…</b>", parse_mode="HTML")
        return

    # ----- ЗАПУСК ИГРЫ -----
    pressed_users_ball[user_id] = True
    try:
        await _deactivate_previous_ball_ui(user_id)
        prev_state = active_games_ball.get(user_id) or {}
        session_rev = int(prev_state.get("session_rev", 0)) + 1
        kb = _build_keyboard_ball(session_rev, bet_amount, user_id)
        msg = await message.reply("<tg-emoji emoji-id='5418138833457793454'>🎱</tg-emoji>", reply_markup=kb, parse_mode="HTML")
        active_games_ball[user_id] = {
            "owner_id": user_id, "chat_id": chat_id,
            "message_id": msg.message_id, "bet": bet_amount,
            "session_rev": session_rev, "closed": False, "ts": now,
            "has_assignment": has_assignment, "is_free": is_free_play,
            "using_demo": using_demo, "using_0demo": using_0demo,
            "repay_amount": 0
        }
        _save_safe(active_games_ball)
        user_message_ball[user_id] = msg.message_id
        _save_safe(user_message_ball)
        print(_describe_field_with_mode(kb, using_demo, using_0demo))
        print(f"[BALL] Игра создана msg={msg.message_id}\n")
    finally:
        pressed_users_ball[user_id] = False


# ===================== ОБРАБОТКА НАЖАТИЙ =====================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith(("ball_", "empty_", "pop_")))
async def process_callback_ball(callback_query: CallbackQuery):
    msg = callback_query.message
    chat_id = int(msg.chat.id)
    msg_id = int(msg.message_id)
    clicker_id = int(callback_query.from_user.id)

    try:
        kind, rev_s, bet_s, uid_s = callback_query.data.split("_")
        cb_rev = int(rev_s); bet_amount = int(bet_s); owner_id = int(uid_s)
    except:
        await callback_query.answer("🛠 Ошибка данных", show_alert=False)
        return
    if clicker_id != owner_id:
        await callback_query.answer("Это не ваша игра.", show_alert=False)
        return

    inflight_key = (msg_id, clicker_id)
    if inflight_key in _ball_inflight:
        await callback_query.answer("⏳"); return
    _ball_inflight.add(inflight_key)

    lock = _get_lock(msg_id)
    async with lock:
        try:
            await callback_query.answer()
            found = _find_ball_state_by_message_id(msg_id)
            gs = found[1] if found else active_games_ball.get(clicker_id)
            if not isinstance(gs, dict) or gs.get("closed"):
                await _safe_edit_text(msg, "🕊", InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Игра завершена", callback_data="ball_end_stub")]]))
                return
            if int(gs.get("owner_id", 0)) != clicker_id or int(gs.get("message_id", 0)) != msg_id:
                await _safe_edit_text(msg, "🕊", InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Игра завершена", callback_data="ball_end_stub")]]))
                return
            if cb_rev != int(gs.get("session_rev", 0)) or bet_amount != int(gs.get("bet", 0)):
                return

            has_assignment = bool(gs["has_assignment"])
            is_free = bool(gs["is_free"])
            using_demo = bool(gs["using_demo"])
            using_0demo = bool(gs["using_0demo"])

            user_balance = int(await db.get_user_balance(clicker_id) or 0)
            chat_balance = int(await db.get_chat_balance(bot1, chat_id) or 0)

            # ---------- POP: всегда шар лопнул, demo/0demo не списываются, долг не гасится ----------
            if kind == "pop":
                loss = bet_amount
                if loss > user_balance:
                    await _safe_edit_text(msg, "<tg-emoji emoji-id='5465143921912846619'>💭</tg-emoji> <b>Недостаточно средств для этого действия.</b>", reply_markup=None)
                    await _finalize_ball_game(clicker_id)
                    return

                icon_id = "4958577444454925201"
                emoji_text = "<tg-emoji emoji-id='4958799300990600199'>🍄</tg-emoji>"
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"- {_fmt_int(loss)} кут", callback_data="ball_end_stub",
                                          style="danger", icon_custom_emoji_id=icon_id)],
                    [InlineKeyboardButton(text="Шар исчез", callback_data="ball_end_stub",
                                          style="default", icon_custom_emoji_id="6041716699848249286")],
                ])
                await _safe_edit_text(msg, emoji_text, reply_markup=kb)

                if has_assignment: await gc_process_bet(user_id=clicker_id, event_chat_id=chat_id, bet=loss, outcome="-")
                if has_assignment and is_free:
                    await _mark_user_game_activity(clicker_id, reason="pop_free")
                else:
                    cur_main = int(await db.get_user_balance(clicker_id) or 0)
                    await db.update_user_balance(clicker_id, max(0, cur_main - loss))
                    await db.cutehistory_minus(clicker_id, loss, "- шарик (pop)")
                    await _safe_tech_log_pop(bot=bot1, uid=clicker_id, loss=loss)
                    await db.update_user_loose(clicker_id, 1, bot1, ref_coin)
                    await _mark_user_game_activity(clicker_id, reason="pop")

                print(f"[BALL][POP] Проигрыш {loss}, долг НЕ гасится.")
                await _finalize_ball_game(clicker_id)
                return

            # ---------- BALL (WIN) ----------
            if kind == "ball":
                profit = bet_amount

                if using_demo:
                    # Списание demo
                    await db.deduct_demo_amount(clicker_id, bet_amount)
                    print(f"[BALL][DEMO] Списано demo: {bet_amount}")

                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"+ {_fmt_int(profit)} кут", callback_data="ball_paid_stub",
                                          style="success", icon_custom_emoji_id="5451814216031809603")],
                    [InlineKeyboardButton(text="Победа", callback_data="ball_paid_stub",
                                          style="default", icon_custom_emoji_id="6041720006973067267")],
                ])
                await _safe_edit_text(msg, "<tg-emoji emoji-id='5206284048254670148'>🎁</tg-emoji>", reply_markup=kb)

                if has_assignment:
                    await gc_process_bet(user_id=clicker_id, event_chat_id=chat_id, bet=profit, outcome="+")
                if has_assignment and is_free:
                    await _mark_user_game_activity(clicker_id, reason="win_free")
                else:
                    cur_main = int(await db.get_user_balance(clicker_id) or 0)
                    await db.update_user_balance(clicker_id, cur_main + profit)
                    await db.cutehistory_plus(clicker_id, profit, "+ шарик")
                    await db.update_chat_balance_minus(chat_id, profit)
                    await db.update_user_wins(clicker_id, 1, bot1, ref_coin)
                    await db.update_user_winamount(clicker_id, profit)
                    await db.add_xp_to_games(clicker_id)
                    await _mark_user_game_activity(clicker_id, reason="win")

                print(f"[BALL] Выигрыш, долг не списывается.")
                await _finalize_ball_game(clicker_id)
                return

            # ---------- EMPTY (LOSS) ----------
            if kind == "empty":
                loss = bet_amount

                if using_0demo:
                    # Списание 0demo
                    await db.deduct_0demo_amount(clicker_id, bet_amount)
                    print(f"[BALL][0DEMO] Списано 0demo: {bet_amount}")

                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"- {_fmt_int(loss)} кут", callback_data="ball_end_stub",
                                          style="danger", icon_custom_emoji_id="5427232022252764138")],
                    [InlineKeyboardButton(text="Проигрыш", callback_data="ball_end_stub",
                                          style="default", icon_custom_emoji_id="6041716699848249286")],
                ])
                await _safe_edit_text(msg, "<tg-emoji emoji-id='5278309679145969175'>❤️</tg-emoji>", reply_markup=kb)

                if has_assignment:
                    await gc_process_bet(user_id=clicker_id, event_chat_id=chat_id, bet=loss, outcome="-")
                if has_assignment and is_free:
                    await _mark_user_game_activity(clicker_id, reason="loss_free")
                else:
                    cur_main = int(await db.get_user_balance(clicker_id) or 0)
                    await db.update_user_balance(clicker_id, max(0, cur_main - loss))
                    await db.cutehistory_minus(clicker_id, loss, "- шарик")
                    await db.update_chat_balance(bot1, chat_id, loss)
                    await db.update_user_loose(clicker_id, 1, bot1, ref_coin)
                    await _mark_user_game_activity(clicker_id, reason="loss")

                gs["repay_amount"] = loss
                active_games_ball[clicker_id] = gs
                _save_safe(active_games_ball)
                print(f"[BALL] Проигрыш, долг будет погашен.")
                await _finalize_ball_game(clicker_id)
                return

        finally:
            _ball_inflight.discard(inflight_key)
            try:
                cid = int(callback_query.message.chat.id)
                if cid not in last_balls_time: last_balls_time[cid] = {}
                last_balls_time[cid][clicker_id] = time.time()
            except: pass


# ---------- Заглушки ----------
@dp.callback_query(lambda c: c.data == "ball_end_stub")
async def ball_end_stub(call: CallbackQuery): await call.answer("Игра завершена.", show_alert=False)

@dp.callback_query(lambda c: c.data == "ball_paid_stub")
async def ball_paid_stub(call: CallbackQuery): await call.answer("Выплата зафиксирована ✅", show_alert=False)