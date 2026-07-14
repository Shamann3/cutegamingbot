# -*- coding: utf-8 -*-
"""
Башня - финальная версия с Jericho.
При наличии долга автоматически включается 0demo‑режим.
Списание долга происходит только при реальном проигрыше (TRAP/COLLAPSE) в этом режиме.
ВАЖНО: даже при наличии demo/0demo пользователь НЕ может начать игру,
если его основной баланс (или баланс челленджа) меньше ставки.
"""

import asyncio, random, time
from decimal import Decimal, ROUND_DOWN, getcontext
from typing import Dict, Set, Tuple, List, Optional

from aiogram import types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from main import *
from bot.config.config import TOKEN, timeoutdonate, donate_bet, ref_coin
from bot.funcs.func import get_bot_username_by_token

# Jericho, welcome_back_gift, newbie_safety_net, force_repay_debt уже импортированы из main

processed_actions_tank = LazyGameStore("processed_actions_tank")
getcontext().prec = 28
SESSION_TTL = 20 * 60
USER_CLICK_COOLDOWN = 0.35
_TANK_MULT_DEFAULT = Decimal("0.70")

def _load_tank_step_multiplier() -> Decimal:
    try:
        raw = str(TANK_MULTIPLIER_CFG).strip()
        x = Decimal(raw)
        if (not x.is_finite()) or x <= 0: return _TANK_MULT_DEFAULT
        return x
    except: return _TANK_MULT_DEFAULT

TANK_STEP_MULTIPLIER = _load_tank_step_multiplier()
RAN_EMOJIS = ("<tg-emoji emoji-id='5204467307153234577'>🍀</tg-emoji>",)
DEBUG_TANK = True

CELL_HIDDEN, CELL_SAFE, CELL_TRAP, CELL_COLLAPSE = " ", "ㅤ", "     ", "\u200b"
SHOW_SAFE, SHOW_TRAP, SHOW_COLLAPSE = "5458585073060160944", "5465432711218863135", "4970038633403777664"

_tank_session_locks: Dict[int, asyncio.Lock] = {}
_tank_inflight: Set[Tuple[int, int]] = set()
_last_click: Dict[int, float] = {}
_closed_msgs: Set[Tuple[int, int]] = set()
_user_start_locks: Dict[int, asyncio.Lock] = {}

def _now_mono() -> float: return time.monotonic()
def _get_user_lock(uid):
    if uid not in _user_start_locks: _user_start_locks[uid] = asyncio.Lock()
    return _user_start_locks[uid]
def _get_session_lock(mid):
    if mid not in _tank_session_locks: _tank_session_locks[mid] = asyncio.Lock()
    return _tank_session_locks[mid]

def _to_int_floor(x): return max(0, int(Decimal(str(x)).quantize(0, rounding=ROUND_DOWN)))
def _dec(v): return Decimal(str(v))
def _str_dec(d): return format(d, "f")
def _safe_int(v, default=0):
    try: return int(v)
    except: return default
def _withdrawable_now(gd):
    if not gd.get("first_success"): return 0
    return max(1, _to_int_floor(_dec(gd["win_amount"]) - _dec(gd["bet"])))
def _mark_action_processed(k): processed_actions_tank[k] = 1
def _is_action_processed(k): return k in processed_actions_tank

def _debug_print_field(field, header="", is_demo=False, is_0demo=False):
    if not DEBUG_TANK: return
    try:
        print(f"[{time.strftime('%H:%M:%S', time.localtime())}][TANK][ПОЛЕ] {header}")
        for r, row in enumerate(field):
            visual = []
            for cell in row:
                if cell == CELL_SAFE: visual.append("🟩")
                elif cell == CELL_TRAP: visual.append("🟥")
                elif cell == CELL_COLLAPSE: visual.append("🟨")
                elif cell == SHOW_SAFE: visual.append("🍀")
                elif cell == SHOW_TRAP: visual.append("♨️")
                elif cell == SHOW_COLLAPSE: visual.append("🏚")
                else: visual.append("⬛")
            print(f"  {r+1:02d} | {'  '.join(visual)}")
        print(f"[{time.strftime('%H:%M:%S', time.localtime())}][TANK][ПОЛЕ_КОНЕЦ]\n")
    except Exception as e:
        print(f"[TANK] ОШИБКА_ПЕЧАТИ_ПОЛЯ: {e}")

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

async def _post_game_activity_update(uid, reason=""):
    try:
        await db.touch_balance_last_active(int(uid), set_active_status=True)
        await db.update_game_last_activity(uid)
        print(f"[TANK] Активность обновлена для {uid} ({reason})")
    except Exception as e:
        print(f"[TANK] Ошибка обновления активности: {e}")

async def _gc_call(uid, cid, bet, outcome, label):
    try:
        await gc_process_bet(user_id=uid, event_chat_id=cid, bet=bet, outcome=outcome)
        print(f"[TANK] GC вызов: {label}")
    except Exception as e:
        print(f"[TANK] Ошибка GC вызова ({label}): {e}")

async def _chat_get_balance(cid):
    try: return _safe_int(await db.get_chat_balance(bot1, cid), 0)
    except: return 0

async def _chat_plus(cid, amt):
    if amt <= 0: return
    try: await db.update_chat_balance(bot1, cid, amt)
    except: pass

async def _chat_minus(cid, amt):
    if amt <= 0: return
    try: await db.update_chat_balance_minus(cid, amt)
    except: pass

async def _user_plus(uid, amt):
    if amt <= 0: return True
    try: await db.update_user_balance(int(uid), f"+{amt}")
    except:
        cur = _safe_int(await db.get_user_balance(int(uid)), 0)
        await db.update_user_balance(int(uid), max(0, cur + amt))
    return True

async def _user_minus(uid, amt):
    if amt <= 0: return True
    try:
        new_val = await db.update_user_balance(int(uid), f"-{amt}")
        if new_val is not None:
            return True
    except:
        pass
    try:
        cur = _safe_int(await db.get_user_balance(int(uid)), 0)
        new_val = await db.update_user_balance(int(uid), max(0, cur - amt))
        return new_val is not None
    except:
        return False

async def _home_take_and_log_tower_collapsed(*, bot, user_id: int, loss: int):
    try:
        await _chat_plus(TECH_CHAT_ID, int(loss))

        # Получаем имя и username с защитой от ошибок (единый стиль)
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

        # Баланс запрашиваем через переданный bot, а не bot1
        chat_balance = await db.get_chat_balance(bot, -1003855337972)

        # HTML-эмодзи, единственный текст сообщения (🍀)
        emoji_html = '<tg-emoji emoji-id="5204467307153234577">🍀</tg-emoji>'

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
                        text="Башня",
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
            await bot.send_message(
                TECH_CHAT_ID,
                emoji_html,
                reply_markup=inline_kb,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception:
            # Fallback: обычный HTML-текст без кнопок, если premium-эмодзи не поддерживаются
            fallback_text = (
                f"<b>🍀 Башня [ Сделка не удалась ]</b>\n"
                f"⭐️ {name_link}\n"
                f"+ {_fmt_int(loss)} на чёрный рынок\n"
                f"{_fmt_int(chat_balance)} кут доступно для выкупов"
            )
            await bot.send_message(
                TECH_CHAT_ID,
                fallback_text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        print(f"[TANK] Дом получил: {loss} от {user_id}")
    except Exception as e:
        print(f"[TANK] Ошибка при взятии дома: {e}")

def _fmt_int(n):
    try: return "{:,.0f}".format(int(n)).replace(",", ".")
    except: return str(n)

def _ui_cell_text(v):
    if v in (CELL_SAFE, CELL_TRAP, CELL_COLLAPSE, CELL_HIDDEN): return " "
    if v in (SHOW_SAFE, SHOW_TRAP, SHOW_COLLAPSE): return " "
    return v

def create_keyboard(game_state, game_data):
    rev = _safe_int(game_data.get("session_rev"), 0)
    owner = _safe_int(game_data.get("owner_id"), 0)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for ri, row in enumerate(game_state):
        btns = []
        for ci, val in enumerate(row):
            kwargs = {"text": _ui_cell_text(val), "callback_data": f"tank_actual_{rev}_{ri}_{ci}_{owner}"}
            if val == SHOW_SAFE: kwargs["icon_custom_emoji_id"] = SHOW_SAFE
            elif val == SHOW_TRAP: kwargs["icon_custom_emoji_id"] = SHOW_TRAP
            elif val == SHOW_COLLAPSE: kwargs["icon_custom_emoji_id"] = SHOW_COLLAPSE
            btns.append(InlineKeyboardButton(**kwargs))
        kb.inline_keyboard.append(btns)
    if game_data.get("first_success"):
        wd = _withdrawable_now(game_data)
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"Можно вывести {_fmt_int(wd)} кут", callback_data=f"tank_info_{rev}_{owner}",
                                 style="success", icon_custom_emoji_id="5841191265277841038")
        ])
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="Закончить игру", callback_data=f"tank_withdraw_{rev}_{owner}")
        ])
    return kb

def _generate_field(mode):
    field = [[CELL_HIDDEN]*5 for _ in range(10)]
    for row in range(10):
        cols = list(range(5)); random.shuffle(cols); collapse_col = cols[0]
        if mode == 'demo':
            for c in range(5): field[row][c] = CELL_COLLAPSE if c == collapse_col else CELL_SAFE
        elif mode == '0demo':
            for c in range(5): field[row][c] = CELL_COLLAPSE if c == collapse_col else CELL_TRAP
        else:
            remain = cols[1:]; safe_cnt = min(random.randint(1,3), max(1, len(remain)-1)); safe_cols = set(remain[:safe_cnt])
            for c in range(5):
                if c == collapse_col: field[row][c] = CELL_COLLAPSE
                elif c in safe_cols: field[row][c] = CELL_SAFE
                else: field[row][c] = CELL_TRAP
    _debug_print_field(field, header="Сгенерировано поле", is_demo=(mode=='demo'), is_0demo=(mode=='0demo'))
    return field

async def _deactivate_previous_game_ui(uid):
    prev_mid = user_messagetank.get(uid)
    st = tank_active_games.get(uid) or {}
    if not prev_mid or not st: return
    chat_id = st.get("chat_id")
    if not chat_id: return
    key = (chat_id, prev_mid)
    if key in _closed_msgs: return
    end_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Игра завершена", callback_data="tank_msg_stub")]])
    try: await bot1.edit_message_reply_markup(chat_id=chat_id, message_id=prev_mid, reply_markup=end_kb)
    except: pass
    _closed_msgs.add(key)
    print(f"[TANK] Предыдущая игра деактивирована для {uid}")

async def _session_ttl_watcher(cid, mid, oid, ttl):
    await asyncio.sleep(ttl)
    st = tank_active_games.get(oid)
    if st and st.get("message_id") == mid and not st.get("closed"):
        st["closed"] = True; tank_active_games[oid] = st
        user_messagetank.pop(oid, None); _tank_session_locks.pop(mid, None)
        print(f"[TANK] Сессия истекла для {oid}")

async def _send_invoice_later(msg, uid, stars_amount, delay):
    try:
        await asyncio.sleep(delay)
        ctx = pending_context.get(uid)
        if ctx and not ctx.get("sent"):
            invoice_message = await send_invoice_to_user(msg, stars_amount)
            pending_context[uid]["manual_message_id"] = invoice_message.message_id
            print(f"[TANK] Счёт отправлен пользователю {uid}")
    except Exception as e:
        print(f"[TANK] Ошибка при отправке счёта: {e}")

# ========== СТАРТ ИГРЫ ==========
@dp.message()
async def game_filter_tank(message: Message):
    text = (message.text or "").strip()
    if not text.startswith("башня "): return
    parts = text.split()
    if len(parts) != 2: return
    if not parts[1].isdigit(): return
    bet_amount = int(parts[1])
    if bet_amount < Tank_MIN_BET or bet_amount > Tank_MAX_BET: return

    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.chat.type == "private": return

    print(f"\n[TANK] 🆕 Новая игра: пользователь={user_id}, ставка={bet_amount}")

    try:
        if await db.get_newbie_expires_at(user_id) is None:
            expires = datetime.now(timezone.utc) + timedelta(hours=random.uniform(0.5, 24.0))
            await db.set_newbie_expires_at(user_id, expires)
            print(f"[TANK] Установлено время льготного периода новичка: {expires}")
    except Exception as e:
        print(f"[TANK] Ошибка инициализации новичка: {e}")

    await welcome_back_gift(user_id)

    # ----- Проверка активного челленджа -----
    has_assignment, is_free = False, False
    current_two = 0
    target_amount = 0
    try:
        assignment = await db.get_active_gc_assignment(user_id)
        if assignment and str(assignment.get("status","")).lower() == "active":
            has_assignment = True
            is_free = bool(await db.gc_active_is_free(user_id))
            if is_free:
                current_two = _safe_int(await db.gc_get_current_two_balance(user_id), 0)
                target_amount = _safe_int(assignment.get("target_amount"), 0)
            print(f"[TANK] Активное задание: бесплатное={is_free}, баланс челленджа={current_two}")
    except Exception as e:
        print(f"[TANK] Ошибка проверки задания: {e}")

    # ----- Вызов Jericho (только для определения режима, не для обхода баланса) -----
    print(f"[TANK] 🔮 Вызов Jericho (диагностика долга и режима)")
    decision = await jericho_check(user_id, bet_amount, game_name="башня")
    print("[TANK] Jericho решение:")
    print(decision["debug"])

    demo_balance = _safe_int(await db.get_user_demo(user_id), 0)
    zero_demo_balance = _safe_int(await db.get_user_0demo(user_id), 0)
    print(f"[TANK] Балансы: demo={demo_balance}, 0demo={zero_demo_balance}")

    # ----- Режим (demo/0demo/обычный) на основе Jericho и реальных балансов -----
    using_demo, using_0demo = False, False
    if decision["action"] in ("force_win", "force_loss", "near_miss"):
        if decision["action"] == "force_win":
            if demo_balance >= bet_amount:
                using_demo = True
                print("[TANK] Режим: demo (принудительный выигрыш, хватает demo)")
            else:
                print("[TANK] Режим: force_win, но demo недостаточно → обычная игра")
        else:  # force_loss / near_miss
            if zero_demo_balance >= bet_amount:
                using_0demo = True
                print("[TANK] Режим: 0demo (принудительный проигрыш, хватает 0demo)")
            else:
                print("[TANK] Режим: force_loss, но 0demo недостаточно → обычная игра")
    else:
        # Если Jericho не выдал принуждение, проверяем, хватает ли demo/0demo на ставку целиком
        if demo_balance >= bet_amount:
            using_demo = True
            print("[TANK] Режим: demo (хватает на ставку)")
        elif zero_demo_balance >= bet_amount:
            using_0demo = True
            print("[TANK] Режим: 0demo (хватает на ставку)")
        else:
            print("[TANK] Режим: обычный")

    # ----- ПРОВЕРКА БАЛАНСА ПОЛЬЗОВАТЕЛЯ (ОБЯЗАТЕЛЬНО, даже при demo/0demo) -----
    if has_assignment and is_free:
        # Бесплатный челлендж: используем баланс current_two
        if bet_amount > current_two:
            # Недостаточно валюты челленджа – игра невозможна
            progress_text = f"{current_two}/{target_amount}" if target_amount > 0 else f"{current_two}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=f"Баланс челленджа : {progress_text} кут", callback_data="noop")],
                    [InlineKeyboardButton(text="Недостаточно кут", callback_data="noop")],
                ]
            )
            await message.reply("😓", reply_markup=keyboard)
            return
    else:
        # Обычный режим: проверяем ТОЛЬКО основной баланс
        cur_balance = _safe_int(await db.get_user_balance(user_id), 0)
        if bet_amount > cur_balance:
            # Не хватает основных средств – показываем кнопку покупки, даже если есть demo/0demo
            print("[TANK] Недостаточно основного баланса – показываем инвойс")
            bot_username = await get_bot_username_by_token(TOKEN)
            result = bet_amount * donate_bet
            bet_str = str(int(result)) if isinstance(result, float) and float(result).is_integer() else str(result)
            pending_context[user_id] = {"stars_amount": bet_str, "sent": False}
            rows = [[InlineKeyboardButton(text=f"💫 Купить {_fmt_int(bet_amount)} кут 💰", url=f"https://t.me/{bot_username}?start=insert_{bet_str}_+")],
                    [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")]]
            await message.reply("💰", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
            asyncio.create_task(_send_invoice_later(message, user_id, bet_str, delay=timeoutdonate))
            return

    # ----- Проверка баланса группы -----
    chat_balance = await _chat_get_balance(chat_id)
    if bet_amount > chat_balance:
        await message.reply("<b><tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> В группе недостаточно средств для игры.</b>", parse_mode="HTML")
        return

    # ----- Запуск игры -----
    async with _get_user_lock(user_id):
        await _deactivate_previous_game_ui(user_id)
        prev = tank_active_games.get(user_id) or {}
        new_rev = _safe_int(prev.get("session_rev"), 0) + 1

        mode = 'normal'
        if using_demo: mode = 'demo'
        elif using_0demo: mode = '0demo'
        game_field = _generate_field(mode)

        state = {
            "game_field": game_field, "current_row": 0, "row_lock": False,
            "bet": bet_amount, "win_amount": _str_dec(_dec(bet_amount)),
            "owner_id": user_id, "chat_id": chat_id,
            "first_success": False, "closed": False, "payout_done": False,
            "session_rev": new_rev, "has_assignment": has_assignment,
            "is_free": is_free, "using_demo": using_demo, "using_0demo": using_0demo,
        }
        sent = await message.reply(
            f"<tg-emoji emoji-id='5291960442422325139'>{random.choice(RAN_EMOJIS)}</tg-emoji>",
            parse_mode="HTML", reply_markup=create_keyboard([game_field[0]], state)
        )
        state["message_id"] = sent.message_id
        tank_active_games[user_id] = state
        user_messagetank[user_id] = sent.message_id
        asyncio.create_task(_session_ttl_watcher(chat_id, sent.message_id, user_id, SESSION_TTL))
        print(f"[TANK] Игра запущена, msg_id={sent.message_id}")

# ========== КЛИКИ ==========
@dp.callback_query(lambda c: c.data and c.data.startswith("tank_actual_"))
async def tank_process_game_buttons(call: types.CallbackQuery):
    uid = call.from_user.id; msg_id = call.message.message_id
    now = _now_mono()
    if now - _last_click.get(uid, 0) < USER_CLICK_COOLDOWN:
        await call.answer("⏳"); return
    _last_click[uid] = now

    try:
        _, _, rev_s, row_s, col_s, owner_s = call.data.split("_")
        cb_rev = int(rev_s); row_idx = int(row_s); col_idx = int(col_s); owner_id = int(owner_s)
    except: return

    if uid != owner_id: await call.answer("Не ваша игра", True); return
    if user_messagetank.get(owner_id) != msg_id: await call.answer("Игра устарела"); return

    inflight_key = (msg_id, uid)
    if inflight_key in _tank_inflight: await call.answer("⏳"); return
    _tank_inflight.add(inflight_key)

    lock = _get_session_lock(msg_id)
    async with lock:
        try:
            game_data = tank_active_games.get(owner_id)
            if not game_data or game_data.get("closed"): return
            if cb_rev != game_data.get("session_rev"): return
            if game_data.get("message_id") != msg_id: return
            if game_data.get("row_lock"): return
            game_data["row_lock"] = True
            tank_active_games[owner_id] = game_data

            action_key = f"cell:{owner_id}:{cb_rev}:{msg_id}:{row_idx}:{col_idx}"
            if _is_action_processed(action_key):
                game_data["row_lock"] = False; return
            _mark_action_processed(action_key)

            field = game_data["game_field"]
            if row_idx != game_data["current_row"]:
                game_data["row_lock"] = False; return

            bet = game_data["bet"]
            using_demo = game_data.get("using_demo", False)
            using_0demo = game_data.get("using_0demo", False)
            has_assignment = game_data.get("has_assignment", False)
            is_free = game_data.get("is_free", False)
            chat_id = call.message.chat.id

            cell_val = field[row_idx][col_idx]
            print(f"[TANK] 🖱️ Клик: ряд={row_idx}, кол={col_idx}, тип={cell_val}, demo={using_demo}, 0demo={using_0demo}")

            # ----- 0DEMO (активирован из‑за долга) -----
            if using_0demo:
                await db.deduct_0demo_amount(owner_id, bet)
                print(f"[TANK] 💀 0demo списано: {bet}")

                if cell_val == CELL_COLLAPSE:
                    field[row_idx][col_idx] = SHOW_COLLAPSE
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="БАШНЯ РАЗРУШИЛАСЬ", callback_data="tank_msg_stub", icon_custom_emoji_id="5469913852462242978")]])
                    await _safe_edit_text(call.message, "<tg-emoji emoji-id='5276032951342088188'>🍓</tg-emoji>", reply_markup=kb)
                    loss = bet
                    if has_assignment:
                        await _gc_call(owner_id, chat_id, loss, "-", "COLLAPSE_0DEMO")
                        if not is_free:
                            await _user_minus(owner_id, loss)
                            await db.cutehistory_minus(owner_id, loss, "- башня (0demo collapse)")
                            await _home_take_and_log_tower_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                            await _post_game_activity_update(owner_id, reason="collapse_0demo")
                    else:
                        await _user_minus(owner_id, loss)
                        await db.cutehistory_minus(owner_id, loss, "- башня (0demo collapse)")
                        await _home_take_and_log_tower_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                        await _post_game_activity_update(owner_id, reason="collapse_0demo")
                else:  # TRAP
                    field[row_idx][col_idx] = SHOW_TRAP
                    await _safe_edit_text(call.message, "♨️")
                    loss = bet
                    if has_assignment:
                        await _gc_call(owner_id, chat_id, loss, "-", "TRAP_0DEMO")
                        if not is_free:
                            await _user_minus(owner_id, loss)
                            await db.cutehistory_minus(owner_id, loss, "- башня (0demo trap)")
                            await _chat_plus(chat_id, loss)
                            await _post_game_activity_update(owner_id, reason="loss_0demo")
                    else:
                        await _user_minus(owner_id, loss)
                        await db.cutehistory_minus(owner_id, loss, "- башня (0demo trap)")
                        await _chat_plus(chat_id, loss)
                        await _post_game_activity_update(owner_id, reason="loss_0demo")

                # --- ВОЗВРАТ ДОЛГА (проигрыш в 0demo‑режиме) ---
                print("[TANK] 💸 Списываем долг через force_repay_debt")
                await force_repay_debt(owner_id, bet)

                game_data["closed"] = True
                await _finalize_game(owner_id, msg_id, game_data)
                return

            # ----- DEMO -----
            if using_demo:
                await db.deduct_demo_amount(owner_id, bet)
                print(f"[TANK] 🎁 Demo списано: {bet}")
                if cell_val == CELL_COLLAPSE:
                    field[row_idx][col_idx] = SHOW_COLLAPSE
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="БАШНЯ РАЗРУШИЛАСЬ", callback_data="tank_msg_stub", icon_custom_emoji_id="5469913852462242978")]])
                    await _safe_edit_text(call.message, "<tg-emoji emoji-id='5276032951342088188'>🍓</tg-emoji>", reply_markup=kb)
                    loss = bet
                    if has_assignment:
                        await _gc_call(owner_id, chat_id, loss, "-", "COLLAPSE_DEMO")
                        if not is_free:
                            await _user_minus(owner_id, loss)
                            await db.cutehistory_minus(owner_id, loss, "- башня (demo collapse)")
                            await _home_take_and_log_tower_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                            await _post_game_activity_update(owner_id, reason="collapse_demo")
                    else:
                        await _user_minus(owner_id, loss)
                        await db.cutehistory_minus(owner_id, loss, "- башня (demo collapse)")
                        await _home_take_and_log_tower_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                        await _post_game_activity_update(owner_id, reason="collapse_demo")
                    game_data["closed"] = True
                    await _finalize_game(owner_id, msg_id, game_data)
                    return

                field[row_idx][col_idx] = SHOW_SAFE
                if not game_data.get("first_success"):
                    game_data["first_success"] = True
                for c in range(5):
                    if c != col_idx and field[row_idx][c] not in (SHOW_SAFE, SHOW_TRAP, SHOW_COLLAPSE):
                        field[row_idx][c] = SHOW_TRAP if random.random() < 0.5 else SHOW_SAFE

                prev = _dec(game_data["win_amount"])
                game_data["win_amount"] = _str_dec(prev + _dec(bet) * TANK_STEP_MULTIPLIER)
                print(f"[TANK] 🎉 Demo безопасно, выигрыш растёт: {game_data['win_amount']}")

                if row_idx == 9:
                    profit = int(_withdrawable_now(game_data))
                    pay = min(profit, await _chat_get_balance(chat_id))
                    if pay > 0:
                        await _chat_minus(chat_id, pay)
                        await _user_plus(owner_id, pay)
                        await db.cutehistory_plus(owner_id, pay, "+ башня")
                        await db.update_user_winamount(owner_id, pay)
                        await db.update_user_wins(owner_id, 1, bot1, ref_coin)
                    await _safe_edit_text(call.message, f"<b><tg-emoji emoji-id='5395325195542078574'>🍀</tg-emoji> 10-й ряд | {_fmt_int(pay)} кут</b>")
                    game_data["closed"] = True
                    await _finalize_game(owner_id, msg_id, game_data)
                    return
                else:
                    game_data["current_row"] += 1
                    game_data["row_lock"] = False
                    tank_active_games[owner_id] = game_data
                    await _safe_edit_reply_markup(call.message, create_keyboard(field[:game_data["current_row"]+1], game_data))
                return

            # ----- ОБЫЧНЫЙ РЕЖИМ -----
            if cell_val == CELL_SAFE:
                field[row_idx][col_idx] = SHOW_SAFE
                if not game_data.get("first_success"):
                    game_data["first_success"] = True
                for r in range(game_data["current_row"]+1):
                    for c in range(5):
                        if field[r][c] == CELL_SAFE: field[r][c] = SHOW_SAFE
                        elif field[r][c] == CELL_TRAP: field[r][c] = SHOW_TRAP
                        elif field[r][c] == CELL_COLLAPSE: field[r][c] = SHOW_SAFE

                prev = _dec(game_data["win_amount"])
                game_data["win_amount"] = _str_dec(prev + _dec(bet) * TANK_STEP_MULTIPLIER)
                print(f"[TANK] ✅ Безопасно! Выигрыш: {game_data['win_amount']}")

                if row_idx == 9:
                    profit = int(_withdrawable_now(game_data))
                    print(f"[TANK] 🏆 Финальный выигрыш: {profit}")
                    if has_assignment and is_free:
                        await _safe_edit_text(call.message, f"<b><tg-emoji emoji-id='5395325195542078574'>🍀</tg-emoji> 10-й ряд | {_fmt_int(profit)} кут (челлендж)</b>")
                        if profit > 0: await _gc_call(owner_id, chat_id, profit, "+", "WIN_FINAL_FREE")
                    else:
                        chat_bal = await _chat_get_balance(chat_id)
                        pay = min(profit, max(0, chat_bal))
                        if pay > 0:
                            await _chat_minus(chat_id, pay)
                            await _user_plus(owner_id, pay)
                            if has_assignment: await _gc_call(owner_id, chat_id, pay, "+", "WIN_FINAL")
                            await db.cutehistory_plus(owner_id, pay, "+ башня")
                            await db.update_user_winamount(owner_id, pay)
                            await db.update_user_wins(owner_id, 1, bot1, ref_coin)
                        await _safe_edit_text(call.message, f"<b><tg-emoji emoji-id='5395325195542078574'>🍀</tg-emoji> 10-й ряд | {_fmt_int(pay)} кут</b>")
                    game_data["closed"] = True
                    await _finalize_game(owner_id, msg_id, game_data)
                    return
                else:
                    game_data["current_row"] += 1
                    game_data["row_lock"] = False
                    tank_active_games[owner_id] = game_data
                    await _safe_edit_reply_markup(call.message, create_keyboard(field[:game_data["current_row"]+1], game_data))
                return

            elif cell_val == CELL_COLLAPSE:
                field[row_idx][col_idx] = SHOW_COLLAPSE
                kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="БАШНЯ РАЗРУШИЛАСЬ", callback_data="tank_msg_stub", icon_custom_emoji_id="5469913852462242978")]])
                await _safe_edit_text(call.message, "<tg-emoji emoji-id='5276032951342088188'>🍓</tg-emoji>", reply_markup=kb)
                loss = bet
                if has_assignment:
                    await _gc_call(owner_id, chat_id, loss, "-", "COLLAPSE_HOME")
                    if not is_free:
                        await _user_minus(owner_id, loss)
                        await db.cutehistory_minus(owner_id, loss, "- башня (домой)")
                        await _home_take_and_log_tower_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                else:
                    await _user_minus(owner_id, loss)
                    await db.cutehistory_minus(owner_id, loss, "- башня (домой)")
                    await _home_take_and_log_tower_collapsed(bot=bot1, user_id=owner_id, loss=loss)
                print("[TANK] 💥 Разрушение в обычном режиме (долг не списывается)")
                game_data["closed"] = True
                await _finalize_game(owner_id, msg_id, game_data)
                return

            elif cell_val == CELL_TRAP:
                field[row_idx][col_idx] = SHOW_TRAP
                await _safe_edit_text(call.message, "♨️")
                loss = bet
                if has_assignment:
                    await _gc_call(owner_id, chat_id, loss, "-", "LOSS")
                    if not is_free:
                        await _user_minus(owner_id, loss)
                        await db.cutehistory_minus(owner_id, loss, "- башня")
                        await _chat_plus(chat_id, loss)
                else:
                    await _user_minus(owner_id, loss)
                    await db.cutehistory_minus(owner_id, loss, "- башня")
                    await _chat_plus(chat_id, loss)
                print("[TANK] ♨️ Ловушка в обычном режиме (долг не списывается)")
                game_data["closed"] = True
                await _finalize_game(owner_id, msg_id, game_data)
                return

        except Exception as e:
            print(f"[TANK] КРИТИЧЕСКАЯ ОШИБКА В ОБРАБОТКЕ КЛИКА: {e}")
        finally:
            _tank_inflight.discard(inflight_key)
            st = tank_active_games.get(owner_id)
            if st and st.get("message_id") == msg_id and st.get("row_lock"):
                st["row_lock"] = False
                tank_active_games[owner_id] = st

async def _finalize_game(owner_id, msg_id, game_data):
    game_data["closed"] = True
    tank_active_games[owner_id] = game_data
    user_messagetank.pop(owner_id, None)
    _tank_session_locks.pop(msg_id, None)
    await newbie_safety_net(owner_id)
    print(f"[TANK] 🏁 Игра завершена для {owner_id}")

# ========== ВЫВОД СРЕДСТВ (БЕЗ ДОЛГА) ==========
@dp.callback_query(lambda c: c.data and c.data.startswith("tank_withdraw_"))
async def tank_process_withdraw(call: types.CallbackQuery):
    uid = call.from_user.id; msg_id = call.message.message_id
    try:
        _, _, rev_s, owner_s = call.data.split("_")
        cb_rev = int(rev_s); owner_id = int(owner_s)
    except: return
    if uid != owner_id: await call.answer("Не ваша игра", True); return
    if user_messagetank.get(owner_id) != msg_id: await call.answer("Игра устарела"); return
    lock = _get_session_lock(msg_id)
    async with lock:
        game_data = tank_active_games.get(owner_id)
        if not game_data or game_data.get("closed"): return
        if cb_rev != game_data.get("session_rev"): return
        if not game_data.get("first_success"): return
        if game_data.get("payout_done"): return
        game_data["payout_done"] = True
        tank_active_games[owner_id] = game_data

        chat_id = call.message.chat.id
        bet = game_data["bet"]
        using_demo = game_data.get("using_demo", False)
        using_0demo = game_data.get("using_0demo", False)
        has_assignment = game_data.get("has_assignment", False)
        is_free = game_data.get("is_free", False)
        profit = max(1, _to_int_floor(_dec(game_data["win_amount"]) - _dec(bet)))
        print(f"[TANK] 💼 Запрос вывода: прибыль={profit}")

        if using_0demo:
            await call.answer("Игра завершена.", show_alert=False); return

        if using_demo:
            await db.deduct_demo_amount(owner_id, int(bet))
            pay = min(profit, await _chat_get_balance(chat_id))
            if pay > 0:
                await _chat_minus(chat_id, pay)
                await _user_plus(owner_id, pay)
                await db.cutehistory_plus(owner_id, pay, "+ башня")
                await db.update_user_winamount(owner_id, pay)
                await db.update_user_wins(owner_id, 1, bot1, ref_coin)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Выплата", callback_data="tank_paid_stub", style="success", icon_custom_emoji_id="5395325195542078574")],
                [InlineKeyboardButton(text=f"{_fmt_int(pay)} кут", callback_data="tank_paid_stub")],
            ])
            await _safe_edit_text(call.message, "<tg-emoji emoji-id='5291960442422325139'>🍀</tg-emoji>", reply_markup=kb)
        elif has_assignment and is_free:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Выплата", callback_data="tank_paid_stub", style="success", icon_custom_emoji_id="5395325195542078574")],
                [InlineKeyboardButton(text=f"{_fmt_int(profit)} кут", callback_data="tank_paid_stub")],
            ])
            await _safe_edit_text(call.message, "<tg-emoji emoji-id='5291960442422325139'>🍀</tg-emoji>", reply_markup=kb)
            if profit > 0: await _gc_call(owner_id, chat_id, int(profit), "+", "WITHDRAW_FREE")
        else:
            chat_bal = await _chat_get_balance(chat_id)
            pay = min(profit, max(0, chat_bal))
            if pay > 0:
                await _chat_minus(chat_id, pay)
                await _user_plus(owner_id, pay)
                if has_assignment: await _gc_call(owner_id, chat_id, pay, "+", "WITHDRAW")
                await db.cutehistory_plus(owner_id, pay, "+ башня")
                await db.update_user_winamount(owner_id, pay)
                await db.update_user_wins(owner_id, 1, bot1, ref_coin)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Выплата", callback_data="tank_paid_stub", style="success", icon_custom_emoji_id="5395325195542078574")],
                [InlineKeyboardButton(text=f"{_fmt_int(pay)} кут", callback_data="tank_paid_stub")],
            ])
            await _safe_edit_text(call.message, "<tg-emoji emoji-id='5291960442422325139'>🍀</tg-emoji>", reply_markup=kb)

        game_data["closed"] = True
        tank_active_games[owner_id] = game_data
        user_messagetank.pop(owner_id, None)
        _tank_session_locks.pop(msg_id, None)
        await newbie_safety_net(owner_id)
        print(f"[TANK] 💸 Вывод завершён для {owner_id}")

# Заглушки
@dp.callback_query(lambda c: c.data and c.data.startswith("tank_msg_stub"))
async def tank_msg_stub(call): await call.answer("💬")

@dp.callback_query(lambda c: c.data and c.data.startswith("tank_paid_stub"))
async def tank_paid_stub(call): await call.answer("✅")