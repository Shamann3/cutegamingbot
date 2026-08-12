# -*- coding: utf-8 -*-
from main import *  # noqa
from bot.games.group_only import reject_if_private_game
from bot.funcs.tech_home_log import safe_send_tech_log
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from typing import Optional, Tuple, Literal
import time
import asyncio
import secrets
import random
import traceback
from datetime import datetime, timedelta, timezone

# ============================================================
# 🎩 TRADE - 3 исхода: вверх / вниз / "сделка сорвалась"
# Экономика:
#   ✅ WIN:    пользователь +ставка, чат-игры -ставка
#   ✅ LOSS:   пользователь -ставка, чат-игры +ставка
#   ✅ BROKEN: пользователь -ставка, чат-игры 0, тех-чат +ставка (+лог)
#
#   🧪 DEMO-режим:   если demo >= ставка → гарантированный WIN,
#                    ставка списывается с demo, профит зачисляется на основной баланс.
#   🧪 0DEMO-режим:  если 0demo >= ставка → гарантированный проигрыш,
#                    ставка списывается с основного баланса И с 0demo.
# ============================================================

# =========================
# НАСТРОЙКИ
# =========================
PAYOUT_MODE = "FIXED"
HOUSE_EDGE = 0.07

BASE_MAX_BET = max_amount_trade

# RNG (криптостойкий)
_rng = secrets.SystemRandom()

Outcome = Literal["up", "down", "broken"]
Direction = Literal["вверх", "вниз"]


# =========================
# УТИЛИТЫ
# =========================
def _fmt(n: int) -> str:
    return "{:,.0f}".format(int(n)).replace(",", ".")


def _parse_direction(word: str) -> Optional[Direction]:
    w = (word or "").lower()
    if w in ("вверх", "верх", "up", "⬆️", "▲"):
        return "вверх"
    if w in ("вниз", "низ", "down", "⬇️", "▼"):
        return "вниз"
    return None


def _pick_outcome() -> Outcome:
    total = Trade_P_OUTCOME_UP + Trade_P_OUTCOME_DOWN + Trade_P_OUTCOME_BROKEN
    if abs(total - 1.0) > 1e-9:
        up = Trade_P_OUTCOME_UP / total
        down = Trade_P_OUTCOME_DOWN / total
        broken = Trade_P_OUTCOME_BROKEN / total
    else:
        up, down, broken = Trade_P_OUTCOME_UP, Trade_P_OUTCOME_DOWN, Trade_P_OUTCOME_BROKEN

    r = _rng.random()
    if r < up:
        return "up"
    if r < up + down:
        return "down"
    return "broken"


def _outcome_ui(outcome: Outcome) -> Tuple[str, str]:
    if outcome == "up":
        return "Вверх", "<tg-emoji emoji-id='5339384049670593248'>↗️</tg-emoji>"
    if outcome == "down":
        return "Вниз", "<tg-emoji emoji-id='5339179750961224703'>📉</tg-emoji>"
    return "Сделка сорвалась", "<tg-emoji emoji-id='5411089297476441876'>🐻</tg-emoji>"


async def _reply_simple(message: Message, text: str, kb: Optional[InlineKeyboardMarkup] = None) -> None:
    await message.reply(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=kb)


def _append_regular_assignment_info_rows(inline_rows: list, has_assignment: bool, is_free: bool) -> None:
    if has_assignment and not is_free:
        inline_rows.append([InlineKeyboardButton(text="У вас обычное задание", callback_data="gc_regular_info")])
        inline_rows.append([InlineKeyboardButton(text="В чём разница?", callback_data="gc_diff_types")])


def _gc_free_mode(has_assignment: bool, is_free: bool) -> bool:
    """Бесплатное задание: ставки только с виртуального баланса челленджа."""
    return bool(has_assignment and is_free)


async def _post_game_activity_update(user_id: int, reason: str = "") -> None:
    try:
        await db.touch_balance_last_active(int(user_id), set_active_status=True)
        await db.update_game_last_activity(user_id)
        print(f"[TRADE] Активность и время игры обновлены для {user_id} (reason={reason})")
    except Exception as e:
        print(f"[TRADE] Ошибка обновления активности/времени для {user_id}: {e}")
        traceback.print_exc()


async def _safe_tech_log_trade_broken(*, bot, user_id: int, loss: int) -> None:
    try:
        await db.update_chat_balance(bot, TECH_CHAT_ID, int(loss))
        receiver_name = await db.get_user_first_name(user_id)
        receiver_username = await db.get_username_by_user_id(user_id)
        name_link1 = await create_user_link(user_id, receiver_name, receiver_username)
        await db.add_home_amount(user_id=user_id, amount=loss)
        chat_balance = await db.get_chat_balance(bot, -1003855337972)   # исправлено: bot1 → bot, т.к. bot приходит в параметрах

        # HTML-эмодзи, которое будет единственным текстом сообщения (📈)
        emoji_html = '<tg-emoji emoji-id="5296306038792808890">📈</tg-emoji>'

        # Кнопка с именем: если есть username → ссылка, иначе → заглушка со звездой
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
                        text="Трейд",
                        callback_data="pass",
                        icon_custom_emoji_id="6028346797368283073"  # ✈️
                    )
                ],
                [row_name_btn],
                [
                    InlineKeyboardButton(
                        text=f"+ {_fmt(loss)} на чёрный рынок",
                        callback_data="pass"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{_fmt(chat_balance)} кут доступно",
                        callback_data="pass"
                    )
                ]
            ]
        )

        # Лог в TECH_CHAT: chat not found не должен ронять партию.
        fallback_text = (
            f"<b>📈 Трейд [ Сделка сорвалась ]</b>\n"
            f"⭐️ {name_link1}\n"
            f"+ {_fmt(loss)} на чёрный рынок\n"
            f"{_fmt(chat_balance)} кут доступно для выкупов"
        )
        await safe_send_tech_log(
            bot,
            TECH_CHAT_ID,
            html=emoji_html,
            reply_markup=inline_kb,
            fallback_html=fallback_text,
            tag="TRADE][BROKEN_LOG_SEND",
        )
    except Exception as e:
        print(f"[TRADE][BROKEN_LOG][EXC] {e}")
        traceback.print_exc()


# =========================
# ХЕНДЛЕР
# =========================
@dp.message()
async def trade(message: Message):
    if not message.text:
        return

    text = message.text.strip()
    if not text:
        return

    parts = text.split()
    if not parts or parts[0].lower() != "трейд":
        return

    if len(parts) != 3:
        return

    dir_a = _parse_direction(parts[1])
    dir_b = _parse_direction(parts[2])

    if dir_a and not dir_b:
        direction: Direction = dir_a
        amount_token = parts[2]
    elif dir_b and not dir_a:
        direction = dir_b
        amount_token = parts[1]
    else:
        return

    amount_token = (amount_token or "").strip()
    if not amount_token.isdigit():
        return

    bet_amount = int(amount_token)

    if bet_amount <= 0:
        return

    if bet_amount <= min_amount_trade:
        await _reply_simple(
            message,
            "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> "
            "<b>Ставка должна быть больше 1 для расчёта выигрыша</b>",
        )
        return

    if await reject_if_private_game(message):
        return


    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)

    # ------------------------------------------------------------------
    # 🆕 Инициализация льготного периода новичка
    # ------------------------------------------------------------------
    try:
        newbie_exp = await db.get_newbie_expires_at(user_id)
        if newbie_exp is None:
            random_hours = random.uniform(0.5, 24.0)
            expires = datetime.now(timezone.utc) + timedelta(hours=random_hours)
            await db.set_newbie_expires_at(user_id, expires)
            print(f"[TRADE] Установлен newbie_expires_at для {user_id}: {expires}")
    except Exception as e:
        print(f"[TRADE] Ошибка инициализации newbie_expires_at: {e}")

    # --- балансы (первичное чтение) ---
    current_balance = int(await db.get_user_balance(user_id) or 0)
    chat_total_balance = int(await db.get_chat_balance(bot1, chat_id) or 0)

    # =====================
    # ЛОГИКА ЧЕЛЛЕНДЖЕЙ
    # =====================
    assignment = None
    has_assignment = False
    is_free = False
    current_two: int = 0
    target_amount: int = 0
    gc_bet_limit = None

    try:
        gc_bet_limit = await db.gc_get_bet_limit_for_user(user_id)
    except Exception as e:
        print(f"[TRADE][BET_LIMIT] Ошибка gc_get_bet_limit_for_user({user_id}): {e}")
        traceback.print_exc()
        gc_bet_limit = None

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
        print("[GC_HOOK][EXC] Ошибка при чтении активного задания:", e)
        traceback.print_exc()
        has_assignment = False
        is_free = False
        current_two = 0
        target_amount = 0

    from bot.funcs.group_balance_level import (
        decide_gc_play_mode,
        format_game_max_bet_html,
        reject_if_bet_over_group_level,
    )
    gate = decide_gc_play_mode(
        bet=bet_amount,
        game_max_bet=int(BASE_MAX_BET),
        has_assignment=has_assignment,
        is_free=is_free,
        gc_bet_limit=gc_bet_limit,
    )
    if gate.get("mode") == "reject":
        await _reply_simple(message, format_game_max_bet_html(gate.get("max") or BASE_MAX_BET))
        return
    is_free_play = gate.get("mode") == "free"

    # === ПРОВЕРКА ДОСТУПНОСТИ СТАВКИ ===
    if is_free_play:
        # Бесплатный челлендж: без БЧ и без ★
        if bet_amount > current_two:
            progress_text = f"{current_two}/{target_amount}" if target_amount > 0 else f"{current_two}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=f"Баланс челленджа : {progress_text} кут", callback_data="noop")],
                    [InlineKeyboardButton(text="Недостаточно кут", callback_data="noop")],
                ]
            )
            await _reply_simple(message, "😓", keyboard)
            return
    else:
        # Обычный режим: проверяем ТОЛЬКО основной баланс (даже если есть demo/0demo)
        if bet_amount > current_balance:
            from bot.funcs.help import callbaYTRWEQck_main  # noqa: F401

            button_help = InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")

            multiplier = donate_bet
            result = bet_amount * multiplier
            bet_amount_str = str(int(result)) if isinstance(result, float) and result.is_integer() else str(result)

            bot_username = await get_bot_username_by_token(TOKEN)
            pending_context[user_id] = {"stars_amount": bet_amount_str, "sent": False}

            button_buy = InlineKeyboardButton(
                text=f"💫 Купить {_fmt(bet_amount)} кут 💰",
                url=f"https://t.me/{bot_username}?start=insert_{bet_amount_str}_+",
            )

            rows = [[button_buy], [button_help]]
            _append_regular_assignment_info_rows(rows, has_assignment, is_free)

            keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
            await _reply_simple(message, "💰", keyboard)

            await asyncio.sleep(timeoutdonate)
            if user_id in pending_context and not pending_context[user_id].get("sent"):
                stars_amount = pending_context[user_id]["stars_amount"]
                invoice_message = await send_invoice_to_user(message, stars_amount)
                pending_context[user_id]["manual_message_id"] = invoice_message.message_id

            return

        # Проверка баланса группы
        if bet_amount > chat_total_balance:
            rows = []
            _append_regular_assignment_info_rows(rows, has_assignment, is_free)
            reply_markup = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
            await _reply_simple(
                message,
                "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В группе недостаточно средств для игры.</b>",
                reply_markup,
            )
            return

        try:
            if await reject_if_bet_over_group_level(message, bet_amount, is_free_play=False):
                return
        except Exception as _gbl_e:
            print(f"[GBL] trade check skip: {_gbl_e!r}")

    # =====================
    # АНТИСПАМ
    # =====================
    now = time.time()
    duration = delaysssssssssgamesonee.get(chat_id, 1.7)
    if duration > 0:
        if chat_id not in last_trade_time:
            last_trade_time[chat_id] = {}
        last_usage = float(last_trade_time[chat_id].get(user_id, 0))
        if now - last_usage < duration:
            remaining = int(duration - (now - last_usage))
            await _reply_simple(
                message,
                f"<tg-emoji emoji-id='5256145216947118159'>⌚️</tg-emoji> <b>Подождите {remaining} сек</b>",
            )
            return
        last_trade_time[chat_id][user_id] = now

    # ⏳ Welcome Back – только вне бесплатного челленджа (там нет реального баланса)
    if not is_free_play:
        await welcome_back_gift(user_id)

    using_demo = False
    using_0demo = False

    # ===================================================================
    # 🔥 АВТОПИЛОТ (JERICHO) – отключён при активном задании (как в шариках/бомбах)
    # ===================================================================
    if has_assignment:
        outcome = _pick_outcome()
        print(f"[TRADE] Активное задание – автопилот/demo/0demo отключены, исход: {outcome}")
    else:
        print("=" * 60)
        print(f"[TRADE] Вызываю автопилот для user={user_id}, bet={bet_amount}")
        decision = await jericho_check(user_id, bet_amount, game_name="трейд", mode="-")
        print(decision["debug"])
        print("=" * 60)

        if decision["action"] in ("force_win", "force_loss", "near_miss"):
            if decision["action"] == "force_win":
                outcome = "up" if direction == "вверх" else "down"
                using_demo = (decision.get("reason") == "demo")
            elif decision["action"] in ("force_loss", "near_miss"):
                outcome = "down" if direction == "вверх" else "up"
                using_0demo = True
            print(f"[TRADE][AUTOPILOT] {decision['action']}, reason={decision['reason']}")
        else:
            outcome = _pick_outcome()
            print(f"[TRADE] Честный исход: {outcome}")

    outcome_text, head_emoji = _outcome_ui(outcome)
    is_win = (outcome == "up" and direction == "вверх") or (outcome == "down" and direction == "вниз")
    is_broken = (outcome == "broken")

    # ============================================
    #  ПРИМЕНЕНИЕ ИСХОДА
    # ============================================
    # Заранее готовим клавиатуру (зависит от win/loss)
    if is_win:
        profit = bet_amount
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"+ {_fmt(profit)} кут", callback_data="trade_stub",
                                      style="success", icon_custom_emoji_id="5206284048254670148")],
                [InlineKeyboardButton(text=outcome_text, callback_data="trade_stub",
                                      style="default", icon_custom_emoji_id="6041720006973067267")],
            ]
        )
    else:
        loss = bet_amount
        direction_text_ui = "Сделка сорвалась" if is_broken else (outcome_text if outcome_text else "Не угадал")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"- {_fmt(loss)} кут", callback_data="trade_stub",
                                      style="danger", icon_custom_emoji_id="5427244146945459253")],
                [InlineKeyboardButton(text=direction_text_ui, callback_data="trade_stub",
                                      style="default", icon_custom_emoji_id="6041716699848249286")],
            ]
        )

    # Отправляем результат игры сразу (пользователь видит исход до обновления БД)
    await message.reply(head_emoji, parse_mode="HTML", reply_markup=kb)

    # --------------------------------------------
    #  ОБНОВЛЕНИЕ БАЛАНСОВ
    # --------------------------------------------
    try:
        gc_outcome = "+" if is_win else "-"
        gc_free_mode = bool(is_free_play)

        if has_assignment:
            try:
                await gc_process_bet(
                    user_id=user_id,
                    event_chat_id=chat_id,
                    bet=bet_amount,
                    outcome=gc_outcome,
                )
            except Exception as e:
                print("[GC_HOOK][EXC] gc_process_bet:", e)
                traceback.print_exc()

        if gc_free_mode:
            # Бесплатный челлендж: только виртуальный баланс задания, основной баланс не трогаем
            await _post_game_activity_update(
                user_id,
                reason="win_free" if is_win else ("broken_free" if is_broken else "loss_free"),
            )
        elif is_win:
            # --- WIN (реальные куты) ---
            if using_demo:
                try:
                    await db.deduct_demo_amount(user_id, bet_amount)
                    print(f"[TRADE][DEMO] Списано {bet_amount} demo у {user_id}")
                except Exception as e:
                    print(f"[TRADE][DEMO][EXC] Ошибка списания demo: {e}")

            cur_main = int(await db.get_user_balance(user_id) or 0)
            await db.update_user_balance(user_id, cur_main + profit)

            try:
                await db.cutehistory_plus(user_id, profit, "+ трейд")
            except Exception as e:
                print("[TRADE][HISTORY_PLUS][EXC]", e)

            await db.update_chat_balance_minus(chat_id, profit)

            try:
                await db.update_user_wins(user_id, 1, bot1, ref_coin)
                await db.update_user_winamount(user_id, profit)
                await db.add_xp_to_games(user_id)
            except Exception as e:
                print("[TRADE][STATS][EXC]", e)

            await _post_game_activity_update(user_id, reason="win")
            await newbie_safety_net(user_id)
        else:
            # --- LOSS / BROKEN (реальные куты) ---
            if using_0demo:
                try:
                    await db.deduct_0demo_amount(user_id, bet_amount)
                    print(f"[TRADE][0DEMO] Списано {bet_amount} 0demo у {user_id}")
                except Exception as e:
                    print(f"[TRADE][0DEMO][EXC] Ошибка списания 0demo: {e}")

                print("[TRADE] Списываем долг через force_repay_debt")
                await force_repay_debt(user_id, loss)

            cur_main = int(await db.get_user_balance(user_id) or 0)
            new_main = max(0, cur_main - loss)
            await db.update_user_balance(user_id, new_main)

            try:
                await db.cutehistory_minus(user_id, loss, "- трейд")
            except Exception as e:
                print("[TRADE][HISTORY_MINUS][EXC]", e)

            try:
                await db.update_user_loose(user_id, 1, bot1, ref_coin)
            except Exception as e:
                print("[TRADE][LOOSE][EXC]", e)

            if not is_broken:
                await db.update_chat_balance(bot1, chat_id, loss)
            else:
                await _safe_tech_log_trade_broken(bot=bot1, user_id=user_id, loss=loss)

            await _post_game_activity_update(
                user_id,
                reason="broken" if is_broken else "loss",
            )
            await newbie_safety_net(user_id)

    except Exception as e:
        print(f"[TRADE][FATAL] Ошибка при обновлении балансов: {e}")
        traceback.print_exc()
        # Не перевыбрасываем исключение, чтобы бот не падал