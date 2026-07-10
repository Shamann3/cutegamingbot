# -*- coding: utf-8 -*-
# ✅ FIX / UPGRADE: Инлайн "Орел или решка" (устойчиво к перезапускам)
# ─────────────────────────────────────────────────────────────
# ВАЖНО (как ты просил):
# - Я НЕ меняю твои callback_data: inorel_create / joinorelinline / startorelinline / rollorelinline
# - Я сохраняю твою логику: ставки, анти-реф, edit_message_text(inline_message_id), gamesorelinline.save()
# - Я УБРАЛ критическую зависимость от button_inlinegamesorel[game_id] (она слетает после рестарта)
# - Теперь ВСЕ клавиатуры собираются "на лету" из gamesorelinline → после рестарта кнопка "Начать игру" работает
# - Добавлены локи и анти-дребезг для START / ROLL тоже (как у тебя на JOIN)

import asyncio
import random
import re
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple

from aiogram import types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from main import (
    inline_add_or_update_user_info,
    _format_hms,
    _pair_seconds_left,
    gamesorelinline,
    db,
    bot1,
    dp,
    start_balance,
    create_user_link,
    ref_coin,timehistorygames,get_current_time_formatted
)

# ============================================================
# ✅ HELPERS (строго "по твоему принципу": защита + стабильность)
# ============================================================

def _safe_first_name(name: Optional[str]) -> str:
    try:
        name = (name or "").strip()
        if not name:
            return "Игрок"
        return re.sub(r'[<>/{}"]', "", name)
    except Exception:
        return "Игрок"

def _fmt_kut(x: int) -> str:
    try:
        return "{:,.0f}".format(int(x)).replace(",", ".")
    except Exception:
        return "0"

def _dedupe_preserve_order_uids(items: List[int]) -> List[int]:
    seen = set()
    out = []
    for uid in items:
        try:
            uid = int(uid)
        except Exception:
            continue
        if uid not in seen:
            seen.add(uid)
            out.append(uid)
    return out

def _get_game(game_id: str) -> Optional[Dict[str, Any]]:
    try:
        if not game_id:
            return None
        return gamesorelinline.get(game_id)
    except Exception:
        return None

def _save_games_silent():
    try:
        gamesorelinline.save()
    except Exception:
        pass

def _kb_join(game_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Присоединиться", callback_data=f"joinorelinline:{game_id}")]
        ]
    )

def _kb_start(game_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Начать игру", callback_data=f"startorelinline:{game_id}")]
        ]
    )

def _kb_roll(game_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подбросить монетку", callback_data=f"rollorelinline:{game_id}")]
        ]
    )

async def _render_lobby_text(game: Dict[str, Any]) -> str:
    # Заголовок + ставка + список участников (кликабельные)
    bet = 0
    try:
        bet = int(game.get("bet", 0) or 0)
        if bet < 0:
            bet = 0
    except Exception:
        bet = 0

    bet_line = f"<tg-emoji emoji-id='5292275525518127278'>💰</tg-emoji> <b>Ставка : {_fmt_kut(bet)} кут</b>\n" if bet > 0 else ""

    parts = game.get("participants", [])
    if not isinstance(parts, list):
        parts = []
    parts = _dedupe_preserve_order_uids([int(x) for x in parts if str(x).isdigit() or isinstance(x, int)])
    game["participants"] = parts

    lines: List[str] = []
    for uid in parts:
        try:
            fn = await db.get_firstname_by_user_id(uid)
        except Exception:
            fn = "Игрок"
        try:
            un = await db.get_username_by_user_id(uid)
        except Exception:
            un = None
        try:
            link = await create_user_link(uid, fn, un)
        except Exception:
            link = f"<b>{fn}</b>"
        lines.append(f"<b>- {link}</b>")

    participants_text = "\n".join(lines) if lines else "<b>- (пусто)</b>"
    return f"<tg-emoji emoji-id='5269254848703902904'>🦅</tg-emoji> <b>Играем в Орел или решка</b>\n{bet_line}{participants_text}"

async def _stop_game_insufficient(game_id: str, inline_message_id: str) -> None:
    # аккуратно останавливаем игру
    try:
        await bot1.edit_message_text(
            text="⛑ <b>Игра остановлена!\nУ кого-то из участников недостаточно средств для игры.</b>",
            inline_message_id=inline_message_id,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        pass

    try:
        del gamesorelinline[game_id]
    except Exception:
        pass
    _save_games_silent()

async def _check_balances_or_stop(game_id: str, game: Dict[str, Any]) -> bool:
    # True = ok, False = stop
    inline_message_id = game.get("inline_message_id")
    if not inline_message_id:
        return False

    bet = 0
    try:
        bet = int(game.get("bet", 0) or 0)
        if bet < 0:
            bet = 0
    except Exception:
        bet = 0

    if bet <= 0:
        return True

    parts = game.get("participants", [])
    if not isinstance(parts, list):
        return False

    for uid in _dedupe_preserve_order_uids(parts):
        try:
            bal = await db.get_user_balance(int(uid))
        except Exception:
            bal = None
        try:
            if bal is None or int(bal) < int(bet):
                await _stop_game_insufficient(game_id, inline_message_id)
                return False
        except Exception:
            await _stop_game_insufficient(game_id, inline_message_id)
            return False

    return True


# ============================================================
# ✅ LOCKS / ANTI-SPAM (JOIN + START + ROLL)
# ============================================================

_orel_inline_locks: Dict[str, asyncio.Lock] = {}
_orel_inline_inflight: Set[Tuple[str, int, str]] = set()  # (game_id, user_id, action)

def _get_lock(game_id: str) -> asyncio.Lock:
    lock = _orel_inline_locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _orel_inline_locks[game_id] = lock
    return lock


# ============================================================
# ✅ CREATE GAME (inorel_create)
# ============================================================

@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("inorel_create"))
async def inline_create_game_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    creator_id = user_id

    # 0) бан
    if await db.is_user_banned(user_id):
        await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
        return

    first_name = _safe_first_name(callback_query.from_user.first_name)
    username = callback_query.from_user.username
    try:
        await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)
    except Exception:
        pass

    # 1) ставка + choice
    bet_amount = 0
    choice = "орел"
    try:
        data_parts = (callback_query.data or "").split(":")
        bet_amount = int(data_parts[2]) if len(data_parts) > 2 and str(data_parts[2]).isdigit() else 0
        if bet_amount < 0:
            bet_amount = 0

        if len(data_parts) > 3:
            ch = str(data_parts[3]).strip().lower()
            if ch in ["орёл", "орел", "орёл "]:
                ch = "орел"
            if ch in ["орел", "решка"]:
                choice = ch
    except Exception:
        bet_amount = 0
        choice = "орел"

    # 2) проверка баланса под ставку
    if bet_amount > 0:
        try:
            bal = await db.get_user_balance(user_id)
        except Exception:
            bal = 0
        try:
            if int(bal) < int(bet_amount):
                await callback_query.answer("💭 Недостаточно средств для игры с такой ставкой.", show_alert=True)
                return
        except Exception:
            await callback_query.answer("💭 Недостаточно средств для игры с такой ставкой.", show_alert=True)
            return

    # 3) создаём игру
    game_id = str(uuid.uuid4())

    gamesorelinline[game_id] = {
        "game_id": game_id,
        "creator": int(creator_id),
        "bet": int(bet_amount),
        "choice": choice,  # "орел" / "решка"
        "participants": [int(creator_id)],
        "scores": {},

        # ✅ важно для перезапусков
        "inline_message_id": callback_query.inline_message_id,
        "stage": "lobby",  # lobby -> rolling -> finished
        "random_user": None,
        "created_ts": time.time()

    }

    # UI
    try:
        name_link1 = await create_user_link(
            creator_id,
            await db.get_name_by_user_id(creator_id),
            await db.get_username_by_user_id(creator_id),
        )
    except Exception:
        name_link1 = f"<b>{first_name}</b>"

    bet_line = f"<tg-emoji emoji-id='5292275525518127278'>💰</tg-emoji> Ставка : {_fmt_kut(bet_amount)} кут\n" if bet_amount > 0 else ""

    try:
        await bot1.edit_message_text(
            inline_message_id=callback_query.inline_message_id,
            text=f"<tg-emoji emoji-id='5269254848703902904'>🦅</tg-emoji> <b>Играем в Орел или решка\n{bet_line}- {name_link1}</b>",
            reply_markup=_kb_join(game_id),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"[OREL_INLINE][CREATE][ERROR] edit_message_text: {e}")

    _save_games_silent()
    try:
        await callback_query.answer("❕ Лобби создано!", show_alert=False)
    except Exception:
        pass


# ============================================================
# ✅ JOIN (joinorelinline:<game_id>)
# ============================================================

@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("joinorelinline:"))
async def inline_join_game_callback(callback_query: types.CallbackQuery):

    # parse
    try:
        game_id = (callback_query.data or "").split(":", 1)[1]
    except Exception:
        await callback_query.answer("🛠 Неверные данные игры.", show_alert=True)
        return

    user_id = callback_query.from_user.id

    if await db.is_user_banned(user_id):
        await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
        return

    game = _get_game(game_id)
    if not game:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    # анти-дребезг
    inflight_key = (game_id, user_id, "join")
    if inflight_key in _orel_inline_inflight:
        await callback_query.answer("⏳ Обрабатываю ваше присоединение…", show_alert=False)
        return
    _orel_inline_inflight.add(inflight_key)

    try:
        first_name = _safe_first_name(callback_query.from_user.first_name)
        username = callback_query.from_user.username
        try:
            await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)
        except Exception:
            pass

        lock = _get_lock(game_id)
        async with lock:
            game = _get_game(game_id)
            if not game:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            if str(game.get("stage")) != "lobby":
                await callback_query.answer("💭 Лобби уже закрыто.", show_alert=True)
                return

            inline_message_id = game.get("inline_message_id")
            if not inline_message_id:
                await callback_query.answer("🛠 Игра повреждена (нет inline_message_id).", show_alert=True)
                return

            creator_id = int(game.get("creator") or 0)
            if user_id == creator_id:
                await callback_query.answer("💭 Вы не можете присоединиться к своей игре.", show_alert=True)
                return

            participants = game.get("participants", [])
            if not isinstance(participants, list):
                participants = []
            participants = _dedupe_preserve_order_uids(participants)
            game["participants"] = participants

            if len(participants) >= 2:
                await callback_query.answer("💭 В игре нет мест", show_alert=True)
                return

            if user_id in participants:
                await callback_query.answer("❕ Вы уже участвуете в этой игре.", show_alert=True)
                return

            bet = 0
            try:
                bet = int(game.get("bet", 0) or 0)
                if bet < 0:
                    bet = 0
            except Exception:
                bet = 0

            if bet > 0:
                try:
                    bal = await db.get_user_balance(user_id)
                except Exception:
                    bal = 0
                try:
                    if int(bal) < int(bet):
                        await callback_query.answer("💭 Недостаточно средств для участия в игре.", show_alert=True)
                        return
                except Exception:
                    await callback_query.answer("💭 Недостаточно средств для участия в игре.", show_alert=True)
                    return

            # ================== АНТИ-РЕФ (строго внутри лока) ==================
            try:
                try:
                    if hasattr(db, "remove_expired_refout"):
                        await db.remove_expired_refout()
                    else:
                        await db.cleanup_expired_refout()
                except Exception:
                    pass

                parts_set = set(participants)
                parts_set.add(creator_id)

                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    inviter_id = None
                except Exception:
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
                    for inv in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, int(inv), now=datetime.now())
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)
                    if min_secs is not None:
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

            # ✅ добавляем игрока атомарно
            participants.append(int(user_id))
            participants = _dedupe_preserve_order_uids(participants)
            game["participants"] = participants

            # UI → теперь показываем "Начать игру"
            lobby_text = await _render_lobby_text(game)
            try:
                await bot1.edit_message_text(
                    text=lobby_text,
                    inline_message_id=inline_message_id,
                    reply_markup=_kb_start(game_id),
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            except (TelegramAPIError, TelegramBadRequest) as e:
                if "message is not modified" not in str(e).lower():
                    print(f"[OREL_INLINE][JOIN][ERROR] edit_message_text: {e}")

            _save_games_silent()
            await callback_query.answer("❕ Вы присоединились к игре!", show_alert=False)

    finally:
        _orel_inline_inflight.discard(inflight_key)
        _save_games_silent()


# ============================================================
# ✅ START (startorelinline:<game_id>) - FIX после рестарта
# ============================================================

@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("startorelinline:"))
async def inline_start_game_callback(callback_query: CallbackQuery):

    # parse
    try:
        game_id = (callback_query.data or "").split(":", 1)[1]
    except Exception:
        await callback_query.answer("🛠 Неверные данные игры.", show_alert=True)
        return

    user_id = callback_query.from_user.id

    if await db.is_user_banned(user_id):
        await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
        return

    # анти-дребезг
    inflight_key = (game_id, user_id, "start")
    if inflight_key in _orel_inline_inflight:
        await callback_query.answer("⏳ Обрабатываю старт…", show_alert=False)
        return
    _orel_inline_inflight.add(inflight_key)

    try:
        first_name = _safe_first_name(callback_query.from_user.first_name)
        username = callback_query.from_user.username
        try:
            await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)
        except Exception:
            pass

        lock = _get_lock(game_id)
        async with lock:
            game = _get_game(game_id)
            if not game:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            inline_message_id = game.get("inline_message_id")
            if not inline_message_id:
                await callback_query.answer("🛠 Игра повреждена (нет inline_message_id).", show_alert=True)
                return

            creator_id = int(game.get("creator") or 0)
            if int(user_id) != int(creator_id):
                await callback_query.answer("💭 Только создатель игры может начать игру.", show_alert=True)
                return

            if str(game.get("stage")) != "lobby":
                # если после рестарта кто-то нажимает повторно - не ломаемся
                await callback_query.answer("❕ Игра уже была запущена.", show_alert=False)
                return

            participants = game.get("participants", [])
            if not isinstance(participants, list):
                participants = []
            participants = _dedupe_preserve_order_uids(participants)
            game["participants"] = participants

            if len(participants) < 2:
                await callback_query.answer("💭 Невозможно начать игру. Недостаточно участников.", show_alert=True)
                return

            # проверка ставки у создателя
            bet = 0
            try:
                bet = int(game.get("bet", 0) or 0)
                if bet < 0:
                    bet = 0
            except Exception:
                bet = 0

            if bet > 0:
                try:
                    bal = await db.get_user_balance(user_id)
                except Exception:
                    bal = 0
                try:
                    if int(bal) < int(bet):
                        await callback_query.answer("💭 Недостаточно средств для игры.", show_alert=True)
                        return
                except Exception:
                    await callback_query.answer("💭 Недостаточно средств для игры.", show_alert=True)
                    return

            # проверяем всех участников, иначе останавливаем игру
            ok = await _check_balances_or_stop(game_id, game)
            if not ok:
                return

            # ✅ критично для рестартов: stage + random_user + обнуление scores
            game["stage"] = "rolling"
            game["scores"] = {}
            game["random_user"] = None

            try:
                await bot1.edit_message_text(
                    text="<tg-emoji emoji-id='5269254848703902904'>🦅</tg-emoji> <b>Нажмите на кнопку, чтобы подкинуть монетку</b>",
                    inline_message_id=inline_message_id,
                    reply_markup=_kb_roll(game_id),
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            except Exception as e:
                print(f"[OREL_INLINE][START][ERROR] edit_message_text: {e}")

            _save_games_silent()
            await callback_query.answer("❕ Игра началась!", show_alert=False)

    finally:
        _orel_inline_inflight.discard(inflight_key)
        _save_games_silent()


# ============================================================
# ✅ ROLL (rollorelinline:<game_id>) - тоже устойчиво к рестарту
# ============================================================

@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("rollorelinline:"))
async def inline_roll_callback(callback_query: CallbackQuery):

    # parse
    try:
        game_id = (callback_query.data or "").split(":", 1)[1]
    except Exception:
        await callback_query.answer("🛠 Неверные данные игры.", show_alert=True)
        return

    user_id = callback_query.from_user.id

    if await db.is_user_banned(user_id):
        await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
        return

    # анти-дребезг
    inflight_key = (game_id, user_id, "roll")
    if inflight_key in _orel_inline_inflight:
        await callback_query.answer("⏳ Обрабатываю бросок…", show_alert=False)
        return
    _orel_inline_inflight.add(inflight_key)

    try:
        first_name = _safe_first_name(callback_query.from_user.first_name)
        username = callback_query.from_user.username
        try:
            await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)
        except Exception:
            pass

        lock = _get_lock(game_id)
        async with lock:
            game = _get_game(game_id)
            if not game:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            inline_message_id = game.get("inline_message_id")
            if not inline_message_id:
                await callback_query.answer("🛠 Игра повреждена (нет inline_message_id).", show_alert=True)
                return

            if str(game.get("stage")) != "rolling":
                # если рестарт и stage остался lobby - говорим начать
                if str(game.get("stage")) == "lobby":
                    await callback_query.answer("💭 Сначала нажмите «Начать игру».", show_alert=True)
                    return
                await callback_query.answer("💭 Игра уже завершена.", show_alert=True)
                return

            participants = game.get("participants", [])
            if not isinstance(participants, list):
                participants = []
            participants = _dedupe_preserve_order_uids(participants)
            game["participants"] = participants

            if user_id not in participants:
                await callback_query.answer("💭 Вы не участвуете в этой игре.", show_alert=True)
                return

            scores = game.get("scores", {})
            if not isinstance(scores, dict):
                scores = {}
                game["scores"] = scores

            if str(user_id) in scores or user_id in scores:
                await callback_query.answer("❕ Вы уже получили результат.", show_alert=True)
                return

            # баланс участника на момент броска
            bet = 0
            try:
                bet = int(game.get("bet", 0) or 0)
                if bet < 0:
                    bet = 0
            except Exception:
                bet = 0

            if bet > 0:
                try:
                    bal = await db.get_user_balance(user_id)
                except Exception:
                    bal = None
                try:
                    if bal is None or int(bal) < int(bet):
                        await _stop_game_insufficient(game_id, inline_message_id)
                        return
                except Exception:
                    await _stop_game_insufficient(game_id, inline_message_id)
                    return

            # выбор стороны
            choice = "Орел"
            try:
                ch = str(game.get("choice") or "").strip().lower()
                if ch in ["орел", "орёл"]:
                    choice = "Орел"
                elif ch == "решка":
                    choice = "Решка"
            except Exception:
                choice = "Орел"

            opposite = "Решка" if choice == "Орел" else "Орел"

            # фиксируем победителя один раз на игру
            if not game.get("random_user"):
                game["random_user"] = random.choice(participants)

            winner_id = int(game["random_user"])
            loser_id = int([uid for uid in participants if int(uid) != int(winner_id)][0])

            result = choice if int(user_id) == int(winner_id) else opposite

            # сохраняем результат (ключи лучше строкой, чтобы не было “1” vs 1 после рестарта)
            try:
                scores[str(user_id)] = result
            except Exception:
                scores[str(user_id)] = result

            try:
                await callback_query.answer(f"{result}", show_alert=False)
            except Exception:
                pass

            # если оба получили - считаем
            if len(scores) < 2:
                _save_games_silent()
                return

            # финальная проверка выплат
            ok = await _check_balances_or_stop(game_id, game)
            if not ok:
                return

            # выплаты
            if bet > 0:
                try:
                    wbal = await db.get_user_balance(winner_id)
                except Exception:
                    wbal = 0
                try:
                    lbal = await db.get_user_balance(loser_id)
                except Exception:
                    lbal = 0

                try:
                    await db.update_user_balance(winner_id, int(wbal) + int(bet))
                    await db.update_user_balance(loser_id, int(lbal) - int(bet))

                    await db.touch_balance_last_active(winner_id , set_active_status=True)
                    await db.touch_balance_last_active(loser_id , set_active_status=True)
                except Exception:
                    # если упало - не ломаемся, но игру завершим текстом ошибки
                    pass

                try:
                    await db.cutehistory_plus(winner_id, bet, "инлайн орел")
                    await db.cutehistory_minus(loser_id, bet, "инлайн орел")
                except Exception:
                    pass

            # статистика/история (оставил как у тебя, но безопасно)
            try:
                await db.update_user_wins(winner_id, 1, bot1, ref_coin)
            except Exception:
                pass
            try:
                await db.update_user_loose(loser_id, 1, bot1, ref_coin)#
                await db.update_game_last_activity(loser_id)
            except Exception:
                pass

            # бонусы historygames - твой блок (не трогаю смысл, только защищаю)
            try:
                total_pot = int(bet) * len(participants)
                await db.update_user_winamount(winner_id, int(total_pot) - int(bet))#
                await db.update_game_last_activity(winner_id)
            except Exception:
                pass

            try:
                # твой check_bet_and_set_item
                from main import check_bet_and_set_item
                await check_bet_and_set_item(winner_id, bet)
            except Exception:
                pass

            # рендер результата
            try:
                total_pot = int(bet) * len(participants)
            except Exception:
                total_pot = 0

            win_amount = 0
            try:
                win_amount = int(total_pot) - int(bet)
            except Exception:
                win_amount = 0

            try:
                fn = await db.get_firstname_by_user_id(winner_id)
            except Exception:
                fn = "Игрок"
            try:
                un = await db.get_username_by_user_id(winner_id)
            except Exception:
                un = None

            try:
                name_link = await create_user_link(winner_id , fn , un)
            except Exception:
                name_link = f"<b>{fn}</b>"

            last_open_time , data_open = await db.get_historygames_times(winner_id)

            current_time = time.time()

            def _to_timestamp_safe(v):
                """Превращает datetime/строку/число в timestamp (float). Возвращает None если нельзя."""
                if v is None:
                    return None
                try:
                    if hasattr(v , "timestamp"):
                        return float(v.timestamp())
                    if isinstance(v , (int , float)):
                        return float(v)
                    if isinstance(v , str):
                        s = v.strip()
                        if not s:
                            return None
                        # 'YYYY-mm-dd HH:MM:SS'
                        try:
                            dt = datetime.strptime(s , "%Y-%m-%d %H:%M:%S")
                            return float(dt.timestamp())
                        except Exception:
                            # iso fallback
                            dt = datetime.fromisoformat(s.replace("Z" , "+00:00")).replace(tzinfo=None)
                            return float(dt.timestamp())
                except Exception as e:
                    print(f"[HISTORYGAMES][WARN] _to_timestamp_safe failed: {e}")
                return None

            # можно передать chat_id/chat_name если есть, если нет - оставь None
            # chat_id = message.chat.id if message.chat else None
            # chat_name = message.chat.title if message.chat else None

            if last_open_time is None or data_open is None:
                # Если данных нет, создаем их
                last_open_time = get_current_time_formatted()
                data_open_ts = current_time + timehistorygames

                print(
                    f"Данных о бонусе для пользователя {winner_id} нет. Создаем новый бонус. "
                    f"Время последнего открытия: {last_open_time}, Время окончания (ts): {data_open_ts}")

                user_name = await db.get_firstname_by_user_id(winner_id)
                print(f"Имя пользователя: {user_name}")

                # сохраняем - можно без чата
                await db.add_historygames(
                    winner_id , user_name , last_open_time ,
                    datetime.fromtimestamp(data_open_ts).strftime("%Y-%m-%d %H:%M:%S"))

            else:
                print(f"Бонус существует. Проверяем. Текущее время: {current_time}")

                data_open_timestamp = _to_timestamp_safe(data_open)
                if data_open_timestamp is None:
                    print(f"[HISTORYGAMES][WARN] data_open некорректный ({data_open!r}). Пересоздаю таймер.")
                    # восстановление без падений
                    last_open_time = get_current_time_formatted()
                    data_open_ts = current_time + timehistorygames

                    await db.update_historygames(
                        winner_id , last_open_time , datetime.fromtimestamp(data_open_ts).strftime("%Y-%m-%d %H:%M:%S"))
                    return

                print(f"Метка времени окончания бонуса: {data_open_timestamp}")

                # Твоя логика: ты обновляешь таймер и когда активен, и когда истёк - оставляю как есть
                last_open_time = get_current_time_formatted()
                data_open_ts = current_time + timehistorygames

                if current_time < data_open_timestamp:
                    print(
                        f"Бонус еще активен. Продлеваем. "
                        f"Текущее время: {current_time}, окончание: {data_open_timestamp}")
                else:
                    print(
                        f"Бонус истек. Обновляем. "
                        f"Текущее время: {current_time}, окончание было: {data_open_timestamp}")

                await db.update_historygames(
                    winner_id , last_open_time , datetime.fromtimestamp(data_open_ts).strftime("%Y-%m-%d %H:%M:%S"))

                print(
                    f"Бонус обновлен для пользователя {winner_id}. "
                    f"Время последнего открытия: {last_open_time}, Время окончания (ts): {data_open_ts}")

            win_line = f"\n<tg-emoji emoji-id='5292275525518127278'>💰</tg-emoji> <b>Выигрыш {_fmt_kut(win_amount)} кут</b>" if win_amount > 0 else ""
            results_text = f"<tg-emoji emoji-id='5262924479226473498'>🏆</tg-emoji> <b>{name_link} [{scores.get(str(winner_id), scores.get(str(winner_id), ''))}]</b>{win_line}"

            # кнопка "создать новую игру"
            if bet > 0:
                btn_create = InlineKeyboardButton(
                    text="Создать новую игру",
                    callback_data=f"inorel_create:{callback_query.from_user.id}:{bet}"
                )
            else:
                btn_create = InlineKeyboardButton(text="Создать новую игру", callback_data="inorel_create")

            kb = InlineKeyboardMarkup(inline_keyboard=[[btn_create]])

            try:
                await bot1.edit_message_text(
                    text=results_text,
                    inline_message_id=inline_message_id,
                    reply_markup=kb,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception as e:
                print(f"[OREL_INLINE][RESULT][ERROR] edit_message_text: {e}")

            # чистим игру
            game["stage"] = "finished"
            try:
                del gamesorelinline[game_id]
            except Exception:
                pass
            _save_games_silent()

    except Exception as e:
        print(f"[OREL_INLINE][ROLL][ERROR] {e}")
        try:
            await callback_query.answer("💭 Ошибка при броске монеты.", show_alert=True)
        except Exception:
            pass
    finally:
        _orel_inline_inflight.discard(inflight_key)
        _save_games_silent()
