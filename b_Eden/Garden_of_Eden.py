"""
🌱 Eden Bot - садовый бот с балансом
"""
import asyncio
import time
import traceback
from typing import List, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ------------------------------------------------------------------
# Внешние зависимости – все используемые символы импортируются явно.
# Убедитесь, что файлы main.py, bot/funcs/balance.py и bot/config/config.py
# существуют и содержат указанные ниже объекты.
# ------------------------------------------------------------------
from main import (stop_timer_from_callback,
    db,
    stop_last_balance_timer,
    balance_message_owner,
    balance_last_msg_by_user,
    balance_cancel_events,
    get_random_emoji_id,
    BAL_STATUS_ACTIVE,
    BAL_STATUS_SLEEP,
    BAL_STATUS_BURNED,
    withdraw_disabled,
    send_withdraw_disabled_message2,
    get_balance_ton_fast,
    SEED_PHRASE,
    TOKEN,
    get_bot_username_by_token,
    pending_withdraw,
    withdrawal_context,
    WITHDRAW_BACK_BALANCE,
    WITHDRAW_BACK_STARS,
    send_withdraw_prompt_once,
    build_withdraw_prompt_text,
    _guard_seconds_left,
    _withdraw_warn_wait_callback,
    _send_or_edit_wait_notice,
    render_conc_stars_screen,
    _pending_apply_back_meta,
    _ctx_apply_back_meta,
)

# Функции из модуля баланса
from bot.funcs.balance import (
    _fmt_wait_smart,
    _burn_balance_and_log_once,

)

# Конфигурация Eden-бота
from bot.config.config import EDEN_TOKEN

# ------------------------------------------------------------
# Объекты Eden-бота
# ------------------------------------------------------------
bot2 = Bot(token=EDEN_TOKEN)
dp2 = Dispatcher()

# ------------------------------------------------------------
# ОБРАБОТЧИКИ
# ------------------------------------------------------------

@dp2.message(Command("start"))
async def start_cmd(message: types.Message):
    """Приветствие садовода."""
    await message.answer(
        f"🌱 <b>Привет, садовод {message.from_user.first_name}!</b>\n\n"
        "🌸 Я бот-садовод Эдема.\n"
        "📋 Команды:\n"
        "/start - приветствие\n"
        "/help - помощь\n"
        "б / баланс / 💸 Баланс - проверить баланс"
    )

@dp2.message(Command("help"))
async def help_cmd(message: types.Message):
    """Помощь."""
    await message.answer(
        "🪴 <b>Помощь по Саду Эдема:</b>\n\n"
        "/start - приветствие\n"
        "/help - эта подсказка\n"
        "б или баланс - проверить баланс\n"
        "💸 Баланс - тоже работает"
    )

@dp2.message(lambda msg: msg.text and msg.text.lower() in [
    "б", "баланс", "💸 баланс", "мой баланс"
])
async def balance_cmd(message: types.Message):
    """
    Вызывается, когда пользователь пишет «баланс» (или аналогичную команду).
    Показывает текущий баланс с учётом движка (sleep/active/burned),
    челленджи, таймер восстановления и т.п.
    """
    # Проверка текста – если вдруг вызвали для другого сообщения, просто выходим
    if not (message.text and message.text.lower() in [ "б" , "баланс" , "💸 баланс" , "мой баланс" ]):
        return

    owner_id = message.from_user.id
    current_chat_id = message.chat.id
    current_chat_username = getattr(message.chat , "username" , None)

    # Если пользователь открыл баланс повторно – гасим таймер на прошлом балансе
    stop_last_balance_timer(owner_id)

    print(
        f"💰 [BALANCE] Вход. owner_id={owner_id}, chat_id={current_chat_id}, "
        f"chat_username={current_chat_username!r}")

    # ============================================================
    # 1) БАЛАНС ТОЛЬКО ИЗ БД
    # ============================================================
    try:
        bal_raw = await db.get_user_balance(owner_id)
        user_balance = int(bal_raw or 0)
        print(f"💰 [BALANCE] Баланс из БД: {user_balance}")
    except Exception as e:
        print(f"⚠️ [BALANCE] get_user_balance err: {e!r}")
        await message.reply("❓")
        return

    # ============================================================
    # 2) ФОРМАТИРОВАНИЕ
    # ============================================================
    try:
        formatted_balance = "{:,.0f}".format(user_balance).replace("," , ".")
    except Exception as e:
        print(f"⚠️ [BALANCE] format err: {e!r}")
        formatted_balance = str(user_balance)

    # ============================================================
    # 3) ПЕРЕД ВЫВОДОМ БАЛАНСА: engine
    # ============================================================
    bal_status = BAL_STATUS_ACTIVE
    bal_remaining_to_3 = 0
    sleep_played = 0
    sleep_needed = 10
    burned_now = False

    try:
        st , last_active , elapsed , remaining , played , needed , next_after , burned_now = await db.ensure_balance_status_engine(
            owner_id)

        bal_status = int(st or BAL_STATUS_ACTIVE)
        bal_remaining_to_3 = int(remaining or 0)
        sleep_played = int(played or 0)
        sleep_needed = int(needed or 10)
        if sleep_needed <= 0:
            sleep_needed = 10

        print(
            f"🧠 [BALANCE][ENGINE] uid={owner_id} st={bal_status} "
            f"remaining={bal_remaining_to_3}s games={sleep_played}/{sleep_needed} "
            f"burned_now={burned_now} next={next_after}s")
    except Exception as e:
        print(f"❌ [BALANCE][ENGINE] err: {e!r}")
        bal_status = BAL_STATUS_ACTIVE
        bal_remaining_to_3 = 0
        sleep_played = 0
        sleep_needed = 10
        burned_now = False

    # ============================================================
    # 3.1) СПИСЫВАЕМ ТОЛЬКО ЕСЛИ burned_now=True
    # ============================================================
    if burned_now:
        removed_amount = await _burn_balance_and_log_once(db , owner_id)
        if removed_amount > 0:
            user_balance = 0
            formatted_balance = "0"

    # ============================================================
    # 4) ЧЕЛЛЕНДЖ
    # ============================================================
    gc_button_row = None
    gc_group_button = None

    try:
        print(f"🎮 [GC_BAL] get_active_gc_assignment uid={owner_id}")
        gc_assignment = await db.get_active_gc_assignment(owner_id)
        print(f"🎮 [GC_BAL] resp: {gc_assignment!r}")

        if gc_assignment and isinstance(gc_assignment , dict):
            gc_status = (gc_assignment.get("status") or "").lower()
            if gc_status == "active":
                try:
                    gc_current_two = int(gc_assignment.get("two_balance_initial") or 0)
                except Exception:
                    gc_current_two = 0

                try:
                    gc_target_amount = int(gc_assignment.get("target_amount") or 0)
                except Exception:
                    gc_target_amount = 0

                try:
                    reward_amount = int(gc_assignment.get("reward_amount") or gc_assignment.get("reward") or 0)
                except Exception:
                    reward_amount = 0

                try:
                    gc_is_free = await db.gc_active_is_free(owner_id)
                except Exception:
                    gc_is_free = False

                emoji_prefix = "🍻 " if gc_is_free else ""

                if gc_target_amount > 0:
                    gc_text = f"Челлендж: {gc_current_two}/{gc_target_amount} кут"
                else:
                    gc_text = f"Челлендж: {gc_current_two} кут"

                cb_data = f"gc:{owner_id}:{gc_current_two}:{gc_target_amount}:{reward_amount}"
                if len(cb_data.encode("utf-8")) > 64:
                    cb_data = f"gc:{owner_id}:{gc_current_two}:{gc_target_amount}:0"
                    print(f"⚠️ [GC_BAL] callback_data длинная -> урезал: {cb_data!r}")

                if emoji_prefix:
                    gc_button_row = [ InlineKeyboardButton(
                        text=gc_text , callback_data=cb_data , style="default" ,
                        icon_custom_emoji_id="5264737672684907396") ]
                else:
                    gc_button_row = [ InlineKeyboardButton(text=gc_text , callback_data=cb_data) ]

                target_chat_id = gc_assignment.get("target_chat_id")
                target_chat_ref = gc_assignment.get("target_chat_ref")

                in_required_chat = False

                if target_chat_id is not None:
                    try:
                        if int(current_chat_id) == int(target_chat_id):
                            in_required_chat = True
                    except Exception:
                        pass

                if not in_required_chat and target_chat_ref and current_chat_username:
                    ref = str(target_chat_ref).strip()
                    uname_current = str(current_chat_username).lstrip("@").lower()
                    uname_required = None

                    if ref.startswith("@"):
                        uname_required = ref [ 1: ].lower()
                    elif "t.me/" in ref:
                        try:
                            uname_required = ref.split("t.me/" , 1) [ 1 ].split("/") [ 0 ].lstrip("@").lower()
                        except Exception:
                            uname_required = None

                    if uname_required and uname_current == uname_required:
                        in_required_chat = True

                if in_required_chat:
                    gc_group_button = InlineKeyboardButton(
                        text="Вы уже в нужной группе" , callback_data="gc_in_place")
                else:
                    group_url = None
                    group_label = "Группа челленджа"

                    if target_chat_ref:
                        ref = str(target_chat_ref).strip()
                        if ref.startswith("@"):
                            uname = ref [ 1: ]
                            group_url = f"https://t.me/{uname}"
                            group_label = f"Играть в @{uname}"
                        elif "t.me" in ref:
                            group_url = ref if ref.startswith("http") else "https://" + ref.lstrip("/")

                    if group_url is None and target_chat_id:
                        try:
                            cid_int = int(target_chat_id)
                        except Exception:
                            cid_int = None

                        if cid_int is not None:
                            try:
                                uname = await db.get_group_username(cid_int) if hasattr(
                                    db , "get_group_username") else None
                                if uname:
                                    group_url = f"https://t.me/{uname}"
                                    group_label = f"Играть в @{uname}"
                            except Exception:
                                pass

                    if group_url:
                        gc_group_button = InlineKeyboardButton(
                            text=group_label , url=group_url , style="default" ,
                            icon_custom_emoji_id="5359636199155704118")

    except Exception as e:
        print(f"❌ [GC_BAL] err: {e!r}")
        print(traceback.format_exc())

    # ============================================================
    # 5) КЛАВИАТУРА
    # ============================================================
    kb_rows: List [ List [ InlineKeyboardButton ] ] = [ ]

    try:
        st_int = int(bal_status)
    except Exception:
        st_int = BAL_STATUS_ACTIVE

    balance_row_index = len(kb_rows)  # 0
    timer_row_index: Optional [ int ] = None

    if st_int == BAL_STATUS_SLEEP:
        bal_icon_id = "5767199127775481841"
        bal_style = "default"
    elif st_int == BAL_STATUS_BURNED:
        bal_icon_id = "6028338546736107668"
        bal_style = "danger"
    else:
        bal_icon_id = "6028338546736107668"
        bal_style = "default"

    kb_rows.append(
        [ InlineKeyboardButton(
            text=f"{formatted_balance} кут1" , callback_data=f"balance:{owner_id}" , style=bal_style ,
            icon_custom_emoji_id=bal_icon_id) ])

    if st_int == BAL_STATUS_SLEEP:
        remain = int(bal_remaining_to_3 or 0)
        timer_text = f"{_fmt_wait_smart(remain)}"

        timer_row_index = len(kb_rows)
        kb_rows.append(
            [ InlineKeyboardButton(
                text=timer_text , callback_data=f"bal_timer:{owner_id}" , style="default" ,
                icon_custom_emoji_id="5294098794969849195") ])

        prog_text = f"{int(sleep_played)}/{int(sleep_needed)} игр до восстановления"
        kb_rows.append(
            [ InlineKeyboardButton(
                text=prog_text , callback_data=f"bal_sleep_games:{owner_id}" , style="default" ,
                icon_custom_emoji_id="5359595190807962128") ])

        print(f"🟠 [BALANCE][UI] sleep timer={timer_text!r} progress={prog_text!r}")

    elif st_int == BAL_STATUS_BURNED:
        kb_rows.append(
            [ InlineKeyboardButton(
                text="Сгоревший баланс" , callback_data=f"bal_timer:{owner_id}" , style="default" ,
                icon_custom_emoji_id="5193209459136045172") ])
        print("🔥 [BALANCE][UI] burned")

    if gc_button_row:
        kb_rows.append(gc_button_row)

    if gc_group_button:
        kb_rows.append([ gc_group_button ])

    if gc_button_row:
        kb_rows.append(
            [ InlineKeyboardButton(
                text="Завершить задание" , callback_data="cb_gc_abort_menu" , style="default" ,
                icon_custom_emoji_id="5449372007432985754") ])

    kb_rows.append(
        [ InlineKeyboardButton(
            text="Вывод" , callback_data="speedwithdrawal2" , style="default" ,
            icon_custom_emoji_id="5188322825735267247") , InlineKeyboardButton(
            text="Донат" , callback_data=f"donate_info2:{owner_id}" , style="default" ,
            icon_custom_emoji_id="5318892863780579996") ])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    # ============================================================
    # 6) ОТПРАВКА
    # ============================================================
    try:
        emoji_id = get_random_emoji_id()
        sent = await message.reply(
            f"<tg-emoji emoji-id='{emoji_id}'>💰</tg-emoji>" , parse_mode="HTML" , disable_web_page_preview=True ,
            reply_markup=kb)

        balance_message_owner [ (sent.chat.id , sent.message_id) ] = owner_id
        balance_last_msg_by_user [ int(owner_id) ] = (int(sent.chat.id) , int(sent.message_id))

        print(f"💰 [BALANCE] msg=({sent.chat.id},{sent.message_id}) owner_id={owner_id}")

    except Exception as e:
        print(f"⚠️ [BALANCE] reply err: {e!r}")
        return

    # ============================================================
    # 7) ДВИЖУЩИЙСЯ ТАЙМЕР 10 СЕК (ТОЛЬКО SLEEP) + корректная отмена
    # ============================================================
    try:
        if st_int == BAL_STATUS_SLEEP and timer_row_index is not None:
            chat_id = int(sent.chat.id)
            mid = int(sent.message_id)
            key = (chat_id , mid)

            cancel_event = asyncio.Event()
            balance_cancel_events [ key ] = cancel_event

            remain_start = int(bal_remaining_to_3 or 0)
            start_ts = time.time()

            last_timer_text = None
            TICKS = 10

            print(f"🟠 [BALANCE][TIMER] start uid={owner_id} key={key} remain_start={remain_start}s ticks={TICKS}")

            for i in range(TICKS):
                await asyncio.sleep(1)

                if cancel_event.is_set():
                    print(f"🛑 [BALANCE][TIMER] canceled uid={owner_id} key={key} tick={i + 1}/{TICKS}")
                    break

                passed = int(time.time() - start_ts)
                remain_now = max(0 , remain_start - passed)

                if remain_now <= 0:
                    burned_now2 = False
                    try:
                        st2 , _ , _ , _ , _ , _ , _ , burned_now2 = await db.ensure_balance_status_engine(owner_id)
                        st2 = int(st2 or BAL_STATUS_ACTIVE)
                    except Exception as e:
                        print(f"⚠️ [BALANCE][TIMER] engine-on-zero err: {e!r}")
                        st2 = BAL_STATUS_BURNED

                    removed_amount = 0
                    if burned_now2:
                        removed_amount = await _burn_balance_and_log_once(db , owner_id)

                    kb_rows [ timer_row_index ] = [ InlineKeyboardButton(
                        text="Сгоревший баланс" , callback_data=f"bal_timer:{owner_id}" , style="default" ,
                        icon_custom_emoji_id="5193209459136045172") ]

                    if removed_amount > 0:
                        bal_txt = "0 кут"
                    else:
                        try:
                            bn = int(await db.get_user_balance(owner_id) or 0)
                        except Exception:
                            bn = 0
                        try:
                            bal_txt = "{:,.0f}".format(bn).replace("," , ".") + " кут"
                        except Exception:
                            bal_txt = f"{bn} кут"

                    kb_rows [ balance_row_index ] = [ InlineKeyboardButton(
                        text=bal_txt , callback_data=f"balance:{owner_id}" , style="danger" ,
                        icon_custom_emoji_id="6028338546736107668") ]

                    kb_new = InlineKeyboardMarkup(inline_keyboard=kb_rows)
                    try:
                        if not cancel_event.is_set():
                            await sent.edit_reply_markup(reply_markup=kb_new)
                    except Exception:
                        pass

                    print(
                        f"🔥 [BALANCE][TIMER] reached 0 burned_now={burned_now2} removed={removed_amount} uid={owner_id} key={key}")
                    break

                new_timer_text = f"{_fmt_wait_smart(remain_now)}"
                if new_timer_text != last_timer_text:
                    kb_rows [ timer_row_index ] = [ InlineKeyboardButton(
                        text=new_timer_text , callback_data=f"bal_timer:{owner_id}" , style="default" ,
                        icon_custom_emoji_id="5294098794969849195") ]
                    kb_new = InlineKeyboardMarkup(inline_keyboard=kb_rows)
                    try:
                        if not cancel_event.is_set():
                            await sent.edit_reply_markup(reply_markup=kb_new)
                    except Exception:
                        pass
                    last_timer_text = new_timer_text

            balance_cancel_events.pop(key , None)
            print(f"🟠 [BALANCE][TIMER] done uid={owner_id} key={key}")

    except Exception as e:
        print(f"⚠️ [BALANCE][TIMER] err: {e!r}")

# ------------------------------------------------------------
# Callback: Донат
# ------------------------------------------------------------
@dp2.callback_query(lambda c: c.data and c.data.startswith("donate_info2:"))
async def cb_donate_info(c: types.CallbackQuery):
    """
    Экран доната:
    - Разрешаем кликать ТОЛЬКО владельцу баланса.
    - Кнопка «Назад» ведёт обратно в cb_balance_refresh через callback_data balance:<owner_id>.
    - Привязываем сообщение к owner_id в balance_message_owner.
    """
    # -------- 0. Достаём owner_id из callback_data --------
    try:
        owner_id_from_cb = int(c.data.split(":", 1)[1])
    except Exception:
        print("⚠️ [DONATE_CB] Некорректный callback_data:", c.data)
        await c.answer("Ошибка данных.", show_alert=True)
        return

    chat_id = c.message.chat.id
    msg_id = c.message.message_id
    stop_timer_from_callback(c.message)

    # -------- 1. Определяем реального владельца сообщения --------
    real_owner_id = owner_id_from_cb
    try:
        stored_owner = balance_message_owner.get((chat_id, msg_id))
        if stored_owner:
            real_owner_id = int(stored_owner)
    except Exception as e:
        print(f"⚠️ [DONATE_CB] Ошибка чтения balance_message_owner: {e}")

    # -------- 2. Блокируем чужие клики --------
    if c.from_user.id != real_owner_id:
        await c.answer("Это чужое сообщение. Откройте своё, написав «баланс» в чат", show_alert=True)
        return

    # -------- 3. Строим клавиатуру --------
    kb = InlineKeyboardMarkup(inline_keyboard=[ ])

    try:
        kb.inline_keyboard.append(
            [ InlineKeyboardButton(
                text="Задонатить" , switch_inline_query_current_chat="донат 100", style="default" ,
                icon_custom_emoji_id="6028338546736107668") ])
    except Exception:
        pass

    kb.inline_keyboard.append(
        [ InlineKeyboardButton(
            text="Назад к балансу" , callback_data=f"balance:{real_owner_id}" , style="default" ,
            icon_custom_emoji_id="5960671702059848143") ])

    await c.message.edit_text(
        "<tg-emoji emoji-id='5296339823005557585'>🏜</tg-emoji>" , reply_markup=kb , parse_mode="HTML" ,
        disable_web_page_preview=True , )

    balance_message_owner[(chat_id, msg_id)] = real_owner_id
    print(
        f"🏜 [DONATE_CB] Экран доната. owner_id={real_owner_id}, "
        f"нажал uid={c.from_user.id}"
    )

# ------------------------------------------------------------
# Callback: Быстрый вывод (speed withdrawal)
# ------------------------------------------------------------
@dp2.callback_query(lambda c: isinstance(c.data , str) and c.data.startswith("speedwithdrawal2"))
async def speed_withdrawal_callback(c: types.CallbackQuery):
    # ============================================================
    # 0) Парсим callback_data
    # ============================================================
    available_amount = None
    has_extra_token = False
    raw_token = None
    stop_timer_from_callback(c.message)
    try:
        data = (c.data or "").strip()
        parts = data.split(":")
        print(f"🧩 [WITHDRAW][SPEED][PARSE] data={data!r} parts={parts}")

        if len(parts) >= 2:
            raw_amount = (parts [ 1 ] or "").strip()
            if raw_amount.isdigit():
                available_amount = int(raw_amount)

        if len(parts) >= 3:
            has_extra_token = True
            raw_token = (parts [ 2 ] or "").strip()

        print(
            f"🧾 [WITHDRAW][SPEED][PARSE] available_amount={available_amount} "
            f"has_extra_token={has_extra_token} token={raw_token!r}")
    except Exception as e:
        print(f"💥 [WITHDRAW][SPEED][PARSE][ERROR] {type(e).__name__}: {e}")
        available_amount = None
        has_extra_token = False
        raw_token = None

    # ============================================================
    # 1) Базовая информация
    # ============================================================
    user_id = int(getattr(c.from_user , "id" , 0) or 0)
    chat_id = int(getattr(getattr(c , "message" , None) , "chat" , None).id) if getattr(c , "message" , None) else 0
    msg_id = int(getattr(getattr(c , "message" , None) , "message_id" , 0) or 0)

    try:
        owner_id_for_back = int(balance_message_owner.get((chat_id , msg_id) , user_id))
    except Exception:
        owner_id_for_back = user_id

    print(
        f"🟦 [WITHDRAW][SPEED] uid={user_id} chat={chat_id} msg={msg_id} "
        f"owner={owner_id_for_back} avail={available_amount} extra={has_extra_token} data={c.data!r}")

    # ============================================================
    # 2) Защита: чужое сообщение
    # ============================================================
    if user_id != owner_id_for_back:
        print(f"🔒 [WITHDRAW][SPEED] ❌ чужое сообщение owner={owner_id_for_back} user={user_id}")
        try:
            await c.answer("Это чужое сообщение.\nОткройте своё, написав «баланс» в чат" , show_alert=True)
        except Exception:
            pass
        return

    try:
        await c.answer("💭 Проверяем возможность вывода…" , show_alert=False)
    except Exception:
        pass

    # ============================================================
    # 3) Глобальный запрет вывода
    # ============================================================
    try:
        if withdraw_disabled:
            print("⛔ [WITHDRAW][SPEED] withdraw_disabled=True")
            try:
                await send_withdraw_disabled_message2(c)
            except Exception:
                pass
            return
    except Exception as e:
        print(f"🟨 [WITHDRAW][SPEED] withdraw_disabled check error: {type(e).__name__}: {e}")

    # ============================================================
    # 4) Username обязателен
    # ============================================================
    if not getattr(c.from_user , "username" , None):
        print("👤 [WITHDRAW][SPEED] ❌ нет username")
        try:
            await c.answer("❕ Для вывода необходимо установить username в Telegram." , show_alert=True)
        except Exception:
            pass
        return

    # ============================================================
    # 5) Выбор back_flag
    # ============================================================
    back_flag_for_ctx = WITHDRAW_BACK_BALANCE
    try:
        back_flag_for_ctx = WITHDRAW_BACK_STARS if has_extra_token else WITHDRAW_BACK_BALANCE
        print(
            f"🧭 [WITHDRAW][SPEED][BACK] has_extra_token={has_extra_token} -> back_flag_for_ctx={back_flag_for_ctx}")
    except Exception as e:
        print(f"💥 [WITHDRAW][SPEED][BACK][ERROR] {type(e).__name__}: {e}")
        back_flag_for_ctx = WITHDRAW_BACK_BALANCE

    # ============================================================
    # 6) ЖЕЛЕЗНОЕ ПРАВИЛО TON
    # ============================================================
    balance_ton = 0.0
    try:
        balance_ton = float(await get_balance_ton_fast(SEED_PHRASE))
        print(f"🟩 [WITHDRAW][SPEED][TON] balance_ton={balance_ton:.6f}")
    except Exception as e:
        print(f"💥 [WITHDRAW][SPEED][TON][ERROR] get_balance_ton_fast: {type(e).__name__}: {e}")
        balance_ton = 0.0

    # ============================================================
    # 7) TON <= 1 -> redirect to deep_conc_stars (обычный вывод)
    # ============================================================
    if balance_ton <= 1:
        print("🧱 [WITHDRAW][SPEED][TON] ❌ TON <= 1 -> redirect to deep_conc_stars")

        if c.message and c.message.chat.type != "private":
            try:
                bot_username = await get_bot_username_by_token(TOKEN)
                print(f"🤖 [WITHDRAW][SPEED][GROUP] bot_username={bot_username!r}")
            except Exception as e:
                print(f"💥 [WITHDRAW][SPEED][GROUP] get_bot_username_by_token: {type(e).__name__}: {e}")
                bot_username = None

            if not bot_username:
                try:
                    await c.answer("Ошибка определения бота." , show_alert=True)
                except Exception:
                    pass
                return

            try:
                pending_withdraw [ user_id ] = {"sent": False , "entry": "speedwithdrawal" ,
                                                "available_amount": available_amount}
                _pending_apply_back_meta(
                    pending_withdraw [ user_id ] , back_flag=WITHDRAW_BACK_BALANCE ,
                    owner_id_for_back=owner_id_for_back , )
                print("🧷 [WITHDRAW][SPEED][PENDING] сохранён pending (TON<=1) back=BALANCE")
            except Exception as e:
                print(f"💥 [WITHDRAW][SPEED][PENDING][ERROR] {type(e).__name__}: {e}")

            kb = InlineKeyboardMarkup(
                inline_keyboard=[ [ InlineKeyboardButton(
                    text="Открыть вывод в боте" , url=f"https://t.me/{bot_username}?start=deep_conc_stars" ,
                    style="default" , icon_custom_emoji_id="6028338546736107668") ] , [ InlineKeyboardButton(
                    text="Назад к балансу" , callback_data=f"balance:{owner_id_for_back}" , style="default" ,
                    icon_custom_emoji_id="5960671702059848143") ] , ])

            try:
                emoji_id = get_random_emoji_id()
                await c.message.edit_text(
                    f"<tg-emoji emoji-id='{emoji_id}'>💰</tg-emoji>" , reply_markup=kb , parse_mode="HTML")
                print("🧭 [WITHDRAW][SPEED][GROUP] redirected -> deep_conc_stars")
            except Exception as e:
                print(f"💥 [WITHDRAW][SPEED][GROUP] edit_text: {type(e).__name__}: {e}")
                try:
                    await c.message.edit_reply_markup(reply_markup=kb)
                except Exception:
                    pass

            try:
                await c.answer("⚠️ TON 0 - доступен обычный вывод." , show_alert=True)
            except Exception:
                pass
            return

        # ЛС: обычный вывод
        try:
            await render_conc_stars_screen(c.message , user_id , speed_flag="-")
        except Exception as e:
            print(f"💥 [WITHDRAW][SPEED][PRIVATE] render_conc_stars_screen: {type(e).__name__}: {e}")

        try:
            await c.answer("⚠️ TON 0 - открыт обычный вывод." , show_alert=True)
        except Exception:
            pass
        return

    # ============================================================
    # ✅ 8) TON есть -> speedwithdrawal
    # ============================================================

    # ------------------------------------------------------------------
    # 🌍 ГРУППА / КАНАЛ: ТОЛЬКО deep-link + pending. НЕТ авто-prompt в ЛС.
    # ------------------------------------------------------------------
    if c.message and c.message.chat.type != "private":
        try:
            bot_username = await get_bot_username_by_token(TOKEN)
            print(f"🤖 [WITHDRAW][SPEED][GROUP] bot_username={bot_username!r}")
        except Exception as e:
            print(f"💥 [WITHDRAW][SPEED][GROUP] get_bot_username_by_token: {type(e).__name__}: {e}")
            bot_username = None

        if not bot_username:
            try:
                await c.answer("Ошибка определения бота." , show_alert=True)
            except Exception:
                pass
            return

        try:
            pending_withdraw [ user_id ] = {"sent": False , "entry": "speedwithdrawal" ,
                                            "available_amount": available_amount}
            _pending_apply_back_meta(
                pending_withdraw [ user_id ] , back_flag=WITHDRAW_BACK_BALANCE ,
                owner_id_for_back=owner_id_for_back , )
            print(f"🧰 [WITHDRAW][SPEED][GROUP] pending сохранён uid={user_id} avail={available_amount}")
        except Exception as e:
            print(f"💥 [WITHDRAW][SPEED][GROUP] pending set: {type(e).__name__}: {e}")

        kb = InlineKeyboardMarkup(
            inline_keyboard=[ [ InlineKeyboardButton(
                text="Открыть вывод в боте" , url=f"https://t.me/{bot_username}?start=withdraw" , style="default" ,
                icon_custom_emoji_id="6028338546736107668") ] , [ InlineKeyboardButton(
                text="Назад к балансу" , callback_data=f"balance:{owner_id_for_back}" , style="default" ,
                icon_custom_emoji_id="5960671702059848143") ] , ])

        try:
            emoji_id = get_random_emoji_id()
            await c.message.edit_text(
                f"<tg-emoji emoji-id='{emoji_id}'>💰</tg-emoji>" , reply_markup=kb , parse_mode="HTML")
            try:
                balance_message_owner [ (chat_id , msg_id) ] = owner_id_for_back
            except Exception:
                pass
            print("🧭 [WITHDRAW][SPEED][GROUP] показан deeplink на /start withdraw (без auto prompt)")
        except Exception as e:
            print(f"💥 [WITHDRAW][SPEED][GROUP] edit_text: {type(e).__name__}: {e}")
            try:
                await c.message.edit_reply_markup(reply_markup=kb)
            except Exception:
                pass

        return

    # ------------------------------------------------------------------
    # 🔒 ЛИЧНЫЕ СООБЩЕНИЯ: отправляем prompt ОДИН раз
    # ------------------------------------------------------------------
    pctx = None
    try:
        pctx = pending_withdraw.get(user_id)
    except Exception:
        pctx = None

    if isinstance(pctx , dict) and pctx.get("manual_message_id"):
        try:
            await c.bot.delete_message(user_id , int(pctx [ "manual_message_id" ]))
            print("🧹 [WITHDRAW][PRIVATE] удалил старый manual_message_id")
        except Exception:
            pass
        try:
            pending_withdraw.pop(user_id , None)
        except Exception:
            pass

    try:
        withdrawal_context [ user_id ] = {"awaiting_amount": True , "origin_chat_id": chat_id ,
            "origin_message_id": msg_id , }
    except Exception:
        withdrawal_context [ user_id ] = {"awaiting_amount": True}

    try:
        _ctx_apply_back_meta(
            withdrawal_context [ user_id ] , back_flag=back_flag_for_ctx , owner_id_for_back=owner_id_for_back , )
        print("🧷 [WITHDRAW][PRIVATE] meta(back_flag/owner) сохранена в ctx")
    except Exception as e:
        print(f"🟨 [WITHDRAW][PRIVATE] meta(back) warn: {type(e).__name__}: {e}")

    try:
        await c.message.delete()
    except Exception:
        pass

    prompt_msg = None
    try:
        prompt_msg = await send_withdraw_prompt_once(
            message_obj=c.message , user_id=user_id , text=build_withdraw_prompt_text(available_amount) ,
            available_amount=available_amount , back_flag=back_flag_for_ctx , owner_id_for_back=owner_id_for_back ,
            src="speedwithdrawal_private" , )
    except Exception as e:
        print(f"💥 [WITHDRAW][PRIVATE] send_withdraw_prompt_once error: {type(e).__name__}: {e}")
        try:
            await c.answer("Ошибка запуска вывода." , show_alert=True)
        except Exception:
            pass
        return

    # ✅ если prompt не отправили – показываем wait ОДИН раз
    if prompt_msg is None:
        left = 0
        try:
            left = int(_guard_seconds_left(user_id))
        except Exception:
            left = 0

        print(f"🛡️ [WITHDRAW][PRIVATE] prompt не отправлен -> WAIT_NOTICE left={left}s")

        try:
            await _withdraw_warn_wait_callback(c , user_id)
        except Exception:
            pass

        try:
            await _send_or_edit_wait_notice(
                message_obj=c.message , user_id=user_id , left=left if left > 0 else 1 ,
                src="speedwithdrawal_private_wait" , )
        except Exception as e:
            print(f"💥 [WITHDRAW][PRIVATE][WAIT_NOTICE_ERROR] {type(e).__name__}: {e}")

        return

    try:
        await c.answer()
    except Exception:
        pass

# ------------------------------------------------------------
# ЗАПУСК
# ------------------------------------------------------------
async def run_eden():
    """Запускает Eden-бота."""
    print("🌱 Eden-бот запущен")
    await bot2.delete_webhook(drop_pending_updates=True)
    await dp2.start_polling(bot2)