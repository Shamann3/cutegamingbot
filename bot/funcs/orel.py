# -*- coding: utf-8 -*-
import asyncio
import random
import time
from datetime import datetime
from typing import Dict, Any, List, Set, Tuple, Optional

from aiogram import types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest

from main import (
    gamesorel, button_gamesorel,  # если button_gamesorel нужен тебе где-то ещё - оставляем
    db, bot1, dp,
    TOKEN, donate_bet, timeoutdonate,
    pending_context, send_invoice_to_user,
    _format_hms, _pair_seconds_left,
    get_current_time_formatted, timehistorygames,
    ref_coin
)

from main import get_bot_username_by_token,create_user_link,LazyGameStore  # у тебя есть эта функция


MAX_OREL_PARTICIPANTS = 2

# ====== Глобальные защитные структуры (как в шашках) ======
_join_locks_orel: Dict[int, asyncio.Lock] = LazyGameStore("_join_locks_orel")
_inflight_orel: Set[Tuple[int, int]] = set()

def _get_orel_lock(game_id: int) -> asyncio.Lock:
    lock = _join_locks_orel.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _join_locks_orel[game_id] = lock
    return lock

def _dedupe_preserve_order(items: List[int]) -> List[int]:
    seen = set()
    out = []
    for x in items:
        try:
            x = int(x)
        except Exception:
            continue
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def _fmt_kut(x: int) -> str:
    try:
        return "{:,.0f}".format(int(x)).replace(",", ".")
    except Exception:
        return "0"

def _kb_join(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Присоединиться", callback_data=f"joinorel:{game_id}")]
    ])

def _kb_start(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начать игру", callback_data=f"startorel:{game_id}")]
    ])

def _kb_roll(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подбросить монетку", callback_data=f"rollorel:{game_id}")]
    ])

async def _safe_edit(chat_id: int, message_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    try:
        await bot1.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except (TelegramAPIError, TelegramBadRequest) as e:
        if "message is not modified" not in str(e).lower():
            print(f"[OREL][EDIT][ERROR] {e}")

def _ensure_game(game_id: int) -> Optional[Dict[str, Any]]:
    """
    Самолечение структуры игры после рестарта:
    - stage
    - participants list
    - scores dict
    - bet int
    - choice normalize
    """
    if game_id not in gamesorel:
        return None

    game = gamesorel[game_id]
    if not isinstance(game, dict):
        return None

    # stage
    if game.get("stage") not in ("lobby", "rolling", "finished"):
        game["stage"] = "lobby"

    # bet
    try:
        bet = int(game.get("bet", 0) or 0)
        if bet < 0:
            bet = 0
    except Exception:
        bet = 0
    game["bet"] = bet

    # participants
    parts = game.get("participants", [])
    if not isinstance(parts, list):
        parts = []
    game["participants"] = _dedupe_preserve_order(parts)

    # scores
    if not isinstance(game.get("scores"), dict):
        game["scores"] = {}

    # choice normalize
    ch = (game.get("choice") or "орел").strip().lower()
    if ch == "орёл":
        ch = "орел"
    if ch not in ("орел", "решка"):
        ch = "орел"
    game["choice"] = ch

    # random_user key
    if "random_user" not in game:
        game["random_user"] = None

    gamesorel[game_id] = game
    return game


# ============================================================
# ✅ CREATE GAME (message)
# ============================================================

@dp.message()
async def orel(message: Message):
    try:
        if not message.text:
            return

        text = message.text.strip()
        parts = text.split()
        if not parts:
            return

        # нормализуем один раз
        p0 = parts[0].lower().replace("ё", "е")

        # допустимые слова
        _coin_words = ("орел", "решка")
        _conj_words = ("или", "и")

        bet = 0
        bet_str = None

        # ✅ Форматы:
        # 1) "орел" / "решка"
        # 2) "орел <число>"
        # 3) "орел или решка"
        # 4) "орел или решка <число>"
        if len(parts) == 1:
            if p0 not in _coin_words:
                return
            bet = 0

        elif len(parts) == 2:
            if p0 not in _coin_words:
                return
            # строго число
            bet_s = parts[1]
            if not bet_s.isdigit():
                return
            bet_str = bet_s

        elif len(parts) == 3:
            p1 = parts[1].lower().replace("ё", "е")
            p2 = parts[2].lower().replace("ё", "е")
            if (p0 in _coin_words) and (p1 in _conj_words) and (p2 in _coin_words):
                bet = 0
            else:
                return

        elif len(parts) == 4:
            p1 = parts[1].lower().replace("ё", "е")
            p2 = parts[2].lower().replace("ё", "е")
            if not ((p0 in _coin_words) and (p1 in _conj_words) and (p2 in _coin_words)):
                return
            bet_s = parts[3]
            if not bet_s.isdigit():
                return
            bet_str = bet_s

        else:
            return

        if bet_str is not None:
            bet = int(bet_str)
            # как у тебя: ставка должна быть > 0, иначе отвечаем
            if bet <= 0:
                await message.reply(
                    "💭 <b>Ставка должна быть больше 0</b>",
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                return

        creator_id = message.from_user.id

        # бан
        if await db.is_user_banned(creator_id):
            await message.reply(
                "❗️ <b>Вы заблокированы в боте</b>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            return

        # баланс (только если bet > 0)
        if bet > 0:
            creator_balance = await db.get_user_balance(creator_id)
            if creator_balance is None or int(creator_balance) < int(bet):
                btn_help = InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")

                multiplier = donate_bet
                result = bet * multiplier
                bet_amount_str = str(int(result)) if isinstance(result, float) and result.is_integer() else str(result)

                bet_fmt = _fmt_kut(bet)
                try:
                    bot_username = await get_bot_username_by_token(TOKEN)
                except Exception:
                    bot_username = "CuteGamingBot"

                pending_context[creator_id] = {"stars_amount": bet_amount_str, "sent": False}

                btn_buy = InlineKeyboardButton(
                    text=f"💫 Купить {bet_fmt} кут 💰",
                    url=f"https://t.me/{bot_username}?start=insert_{bet_amount_str}_+"
                )

                kb = InlineKeyboardMarkup(inline_keyboard=[[btn_buy], [btn_help]])

                await message.reply(
                    "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
                    reply_markup=kb,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )

                await asyncio.sleep(timeoutdonate)

                if creator_id in pending_context and not pending_context[creator_id].get("sent"):
                    invoice_message = await send_invoice_to_user(message, bet_amount_str)
                    pending_context[creator_id]["manual_message_id"] = invoice_message.message_id
                return

        # game_id как у тебя
        game_id = message.message_id

        # выбор стороны (берём из первого слова)
        choice = p0
        if choice not in ("орел", "решка"):
            choice = "орел"

        # creator link
        first_name = await db.get_firstname_by_user_id(creator_id)
        username = await db.get_username_by_user_id(creator_id)
        name_link = await create_user_link(creator_id, first_name, username)

        join_kb = _kb_join(game_id)

        msg = await message.reply(
            f"<tg-emoji emoji-id='5269254848703902904'>🦅</tg-emoji> <b>Играем в Орел или решка\n- {name_link}</b>",
            reply_markup=join_kb,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        gamesorel[game_id] = {
            "creator": int(creator_id),
            "bet": int(bet),
            "participants": [int(creator_id)],
            "scores": {},
            "choice": choice,

            "stage": "lobby",
            "random_user": None,

            "chat_id": int(msg.chat.id),
            "message_id": int(msg.message_id),
        }

        # совместимость как у тебя
        button_gamesorel[game_id] = {"keyboard": join_kb}

        try:
            gamesorel.save()
        except Exception:
            pass

    except Exception as e:
        print(f"[OREL][CREATE][ERROR] {e}")


# ============================================================
# ✅ JOIN (как шашки, строго внутри лока)
# ============================================================

@dp.callback_query(lambda c: c.data.startswith("joinorel:"))
async def join_game_callback(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    try:
        game_id = int(callback_query.data.split(":", 1)[1])
    except Exception:
        await callback_query.answer("⚠️ Неверные данные.", show_alert=True)
        return

    if game_id not in gamesorel:
        await callback_query.answer("🛠 Эта игра больше не существует.")
        return

    inflight_key = (game_id, user_id)
    if inflight_key in _inflight_orel:
        await callback_query.answer("⏳ Обрабатываю ваше присоединение...")
        return

    _inflight_orel.add(inflight_key)
    try:
        lock = _get_orel_lock(game_id)
        async with lock:
            game = _ensure_game(game_id)
            if not game:
                await callback_query.answer("🛠 Эта игра больше не существует.")
                return

            if game.get("stage") != "lobby":
                await callback_query.answer("💭 Игра уже запущена.")
                return

            if await db.is_user_banned(user_id):
                await callback_query.answer("❗️ Вы заблокированы в боте")
                return

            if int(user_id) == int(game.get("creator")):
                await callback_query.answer("❗️ Вы не можете присоединиться к своей игре.")
                return

            participants = _dedupe_preserve_order(game.get("participants", []))
            game["participants"] = participants

            if len(participants) >= MAX_OREL_PARTICIPANTS:
                await callback_query.answer("💭 В игре нет мест")
                return

            if user_id in participants:
                await callback_query.answer("❕ Вы уже участвуете в этой игре.")
                return

            bet = int(game.get("bet", 0) or 0)
            if bet > 0:
                bal = await db.get_user_balance(user_id)
                if bal is None or int(bal) < bet:
                    await callback_query.answer("❗️ У вас недостаточно средств для участия в игре.")
                    return

            # --- анти-реф защита (как у тебя/шашек) ---
            try:
                parts_set = set(participants)

                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    inviter_id = None

                if inviter_id and int(inviter_id) in parts_set:
                    secs = await _pair_seconds_left(db, user_id, int(inviter_id), now=datetime.now())
                    if secs > 0:
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь который пригласил вас в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения : {_format_hms(secs)}\n#AntiFarmSystem",
                            show_alert=True
                        )
                        return

                invitees_here = await db.get_invitees_in(inviter_id=user_id, candidates=parts_set)
                if invitees_here:
                    min_secs = None
                    now_dt = datetime.now()
                    for invitee_id in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, int(invitee_id), now=now_dt)
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)
                    if min_secs:
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь которого вы пригласили в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения : {_format_hms(min_secs)}\n#AntiFarmSystem",
                            show_alert=True
                        )
                        return
            except Exception:
                await callback_query.answer(
                    "💭 Техническая ошибка. Обратитесь к @JerichoCute. Код ошибки: #1212471",
                    show_alert=True
                )
                return

            # --- критическая точка: добавляем атомарно ---
            game["participants"].append(int(user_id))
            game["participants"] = _dedupe_preserve_order(game["participants"])
            gamesorel[game_id] = game
            gamesorel.save()

            # Отвечаем на callback СРАЗУ, как только игрок реально добавлен в
            # лобби - дальше идёт сборка списка участников (запрос в БД на
            # каждого) и редактирование сообщения в Telegram, это может занять
            # больше времени, чем Telegram готов ждать ответ на callback
            # ("query is too old and response timeout expired" под нагрузкой -
            # см. инцидент с задержками в пати).
            await callback_query.answer("❕ Вы присоединились к игре!")

            chat_id = game.get("chat_id")
            message_id = game.get("message_id")

            # UI список участников
            lines = []
            for uid in game["participants"]:
                fn = await db.get_firstname_by_user_id(uid)
                un = await db.get_username_by_user_id(uid)
                link = await create_user_link(uid, fn, un)
                lines.append(f"<b>- {link}</b>")

            total_pot = bet * len(game["participants"])
            win_amount_formatted = _fmt_kut(max(total_pot - bet, 0))
            win_text = f"\n<tg-emoji emoji-id='5292275525518127278'>💲</tg-emoji> <b>Выигрыш {win_amount_formatted} кут</b>" if total_pot > 0 else ""

            keyboard = _kb_start(game_id) if len(game["participants"]) >= 2 else _kb_join(game_id)

            if chat_id is not None and message_id is not None:
                await _safe_edit(
                    int(chat_id),
                    int(message_id),
                    f"<tg-emoji emoji-id='5269254848703902904'>🦅</tg-emoji> <b>Играем в Орёл или решка</b>{win_text}\n" + "\n".join(lines),
                    reply_markup=keyboard
                )

            gamesorel.save()

    finally:
        _inflight_orel.discard(inflight_key)


# ============================================================
# ✅ START
# ============================================================

@dp.callback_query(lambda c: c.data.startswith("startorel:"))
async def start_game_callback(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    try:
        game_id = int(callback_query.data.split(":", 1)[1])
    except Exception:
        await callback_query.answer("⚠️ Неверные данные.", show_alert=True)
        return

    game = _ensure_game(game_id)
    if not game:
        await callback_query.answer("🛠 Эта игра больше не существует.")
        return

    if int(user_id) != int(game.get("creator")):
        await callback_query.answer("💭 Только создатель игры может начать игру.")
        return

    if len(game.get("participants", [])) < 2:
        await callback_query.answer("💭 Невозможно начать игру. Недостаточно участников.")
        return

    # Отвечаем на callback СРАЗУ, до похода в БД за проверкой баланса и
    # редактирования сообщения в Telegram - иначе под нагрузкой Telegram
    # успевает пометить callback как просроченный ("query is too old") прежде
    # чем эти запросы завершатся.
    await callback_query.answer("❕ Игра началась!")

    bet = int(game.get("bet", 0) or 0)

    # проверка баланса у обоих
    if bet > 0:
        for pid in game["participants"]:
            bal = await db.get_user_balance(pid)
            if bal is None or int(bal) < bet:
                chat_id = game.get("chat_id")
                message_id = game.get("message_id")
                if chat_id and message_id:
                    await _safe_edit(int(chat_id), int(message_id),
                                     "⛑ <b>Игра остановлена!\nУ кого-то из участников недостаточно средств для игры.</b>",
                                     reply_markup=None)
                try:
                    del gamesorel[game_id]
                    gamesorel.save()
                except Exception:
                    pass
                return

    game["stage"] = "rolling"
    gamesorel[game_id] = game
    gamesorel.save()

    chat_id = game.get("chat_id")
    message_id = game.get("message_id")

    if chat_id and message_id:
        await _safe_edit(
            int(chat_id),
            int(message_id),
            "<tg-emoji emoji-id='5269254848703902904'>🦅</tg-emoji> <b>Нажмите на кнопку, чтобы подкинуть монетку</b>",
            reply_markup=_kb_roll(game_id)
        )


# ============================================================
# ✅ ROLL
# ============================================================

@dp.callback_query(lambda c: c.data.startswith("rollorel:"))
async def roll_callback(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    try:
        game_id = int(callback_query.data.split(":", 1)[1])
    except Exception:
        await callback_query.answer("⚠️ Неверные данные.", show_alert=True)
        return

    game = _ensure_game(game_id)
    if not game:
        await callback_query.answer("🛠 Эта игра больше не существует.")
        return

    if game.get("stage") != "rolling":
        await callback_query.answer("💭 Игра ещё не началась.")
        return

    if user_id not in game.get("participants", []):
        await callback_query.answer("💭 Вы не участвуете в этой игре.")
        return

    if user_id in game.get("scores", {}):
        await callback_query.answer("❕ Вы уже получили результат.")
        return

    bet = int(game.get("bet", 0) or 0)

    # баланс перед броском
    if bet > 0:
        bal = await db.get_user_balance(user_id)
        if bal is None or int(bal) < bet:
            chat_id = game.get("chat_id")
            message_id = game.get("message_id")
            if chat_id and message_id:
                await _safe_edit(int(chat_id), int(message_id),
                                 "⛑ <b>Игра остановлена!\nУ кого-то из участников недостаточно средств для игры.</b>",
                                 reply_markup=None)
            try:
                del gamesorel[game_id]
                gamesorel.save()
            except Exception:
                pass
            return

    # фиксируем победителя один раз
    if not game.get("random_user"):
        game["random_user"] = int(random.choice(game["participants"]))

    choice = game["choice"]  # "орел" или "решка"
    choice_cap = "Орел" if choice == "орел" else "Решка"
    opposite_cap = "Решка" if choice_cap == "Орел" else "Орел"

    result = choice_cap if int(user_id) == int(game["random_user"]) else opposite_cap
    game["scores"][int(user_id)] = result

    gamesorel[game_id] = game
    gamesorel.save()

    await callback_query.answer(result)

    # если не все бросили - ждём второго
    if len(game["scores"]) < len(game["participants"]):
        return

    # ✅ оба бросили - считаем победителя / проигравшего
    winner_id = int(game["random_user"])
    loser_id = int([uid for uid in game["participants"] if int(uid) != winner_id][0])

    # выплаты
    if bet > 0:
        winner_balance = await db.get_user_balance(winner_id)
        loser_balance = await db.get_user_balance(loser_id)

        if winner_balance is None:
            winner_balance = 0
        if loser_balance is None or int(loser_balance) < bet:
            # стоп (если кто-то обнулился в момент игры)
            chat_id = game.get("chat_id")
            message_id = game.get("message_id")
            if chat_id and message_id:
                await _safe_edit(int(chat_id), int(message_id),
                                 "⛑ <b>Игра остановлена!\nУ кого-то из участников недостаточно средств для игры.</b>",
                                 reply_markup=None)
            try:
                del gamesorel[game_id]
                gamesorel.save()
            except Exception:
                pass
            return

        await db.update_user_balance(winner_id, int(winner_balance) + bet)
        await db.update_user_balance(loser_id, int(loser_balance) - bet)
        await db.touch_balance_last_active(winner_id , set_active_status=True)
        await db.touch_balance_last_active(loser_id , set_active_status=True)

        await db.cutehistory_plus(winner_id, bet, "+ орел или решка")
        await db.cutehistory_minus(loser_id, bet, "- орел или решка")

    total_pot = bet * len(game["participants"])
    win_amount = max(total_pot - bet, 0)
    win_amount_formatted = _fmt_kut(win_amount)

    # стата
    try:
        await db.update_user_wins(winner_id, 1, bot1, ref_coin)
        await db.update_user_loose(loser_id, 1, bot1, ref_coin)#
        await db.update_game_last_activity(winner_id)
        await db.update_game_last_activity(loser_id)
        await db.update_user_winamount(winner_id, win_amount)#
    except Exception:
        pass

    # бонус historygames (оставляю идею твою, но без падений)
    try:
        last_open_time, data_open = await db.get_historygames_times(winner_id)
        now_ts = time.time()
        if last_open_time is None or data_open is None:
            last_open_time = get_current_time_formatted()
            data_open_new = now_ts + timehistorygames
            user_name = await db.get_firstname_by_user_id(winner_id)
            await db.add_historygames(
                int(game["chat_id"]), "1", winner_id, user_name, last_open_time,
                datetime.fromtimestamp(data_open_new).strftime("%Y-%m-%d %H:%M:%S")
            )
        else:
            last_open_time = get_current_time_formatted()
            data_open_new = now_ts + timehistorygames
            await db.update_historygames(
                winner_id, last_open_time,
                datetime.fromtimestamp(data_open_new).strftime("%Y-%m-%d %H:%M:%S")
            )
    except Exception as e:
        print(f"[OREL][HISTORYGAMES][ERROR] {e}")

    # сообщение результата
    first_name = await db.get_firstname_by_user_id(winner_id)
    username = await db.get_username_by_user_id(winner_id)
    name_link = await create_user_link(winner_id, first_name, username)

    win_text = f"\n<tg-emoji emoji-id='5292275525518127278'>💰</tg-emoji> <b>Выигрыш {win_amount_formatted} кут</b>" if total_pot > 0 else ""
    results_text = f"<tg-emoji emoji-id='5262924479226473498'>🏆</tg-emoji> <b>{name_link} [{game['scores'].get(winner_id)}]</b>{win_text}"

    chat_id = game.get("chat_id")
    message_id = game.get("message_id")
    if chat_id and message_id:
        await _safe_edit(int(chat_id), int(message_id), results_text, reply_markup=None)

    # чистим игру
    try:
        del gamesorel[game_id]
        gamesorel.save()
    except Exception:
        pass
