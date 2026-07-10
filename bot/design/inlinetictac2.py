import asyncio
import html
import random
import re
import time
import uuid

from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any

from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode, ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from bot.funcs.help import wordhelp, brak, ffunc, other, gamehelp, textstore, textglobhelp, textzabhelp, clanss
from bot.design.inlinetictactoe import *
from bot.funcs.tic_tac_toe import TTT_STYLE_PACKS

from main import (
    inline_add_or_update_user_info,
    _format_hms,
    _pair_seconds_left,
    bot1,
    dp,
    db,
    start_balance,
    ref_coin,
    get_current_time_formatted,
    timehistorygames,
)

# =========================================================
# PREMIUM INLINE TTT DESIGN
# =========================================================

INLINE_TTT_REST = 2
inline_ttt_cooldowns: Dict[int, float] = {}

# text -> для текста сообщений
# plain -> для логики игры
# button_ids -> для premium emoji в кнопках


# fallback старые обычные стили, если надо



def _escape(text: Any) -> str:
    return html.escape(str(text or ""))


def _fmt_int(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")


def _board_size_to_int(board_size: str) -> int:
    return 7 if board_size == "7x7" else 5 if board_size == "5x5" else 3


async def create_user_link(user_id: int, first_name: str, username: str = None) -> str:
    first_name = _escape(first_name or "Игрок")
    if username:
        return f"<a href='https://t.me/{_escape(username)}'>{first_name}</a>"
    return first_name


def _get_random_inline_ttt_style() -> Dict[str, Any]:
    return random.choice(TTT_STYLE_PACKS)


def _get_inline_style_text_pair(game: dict) -> Tuple[str, str]:
    style_pack = game.get("style_pack") or {}
    pair = style_pack.get("text")
    if pair and len(pair) == 2:
        return pair[0], pair[1]
    return "❌", "⭕"


def _get_inline_style_plain_pair(game: dict) -> Tuple[str, str]:
    style_pack = game.get("style_pack") or {}
    pair = style_pack.get("plain")
    if pair and len(pair) == 2:
        return pair[0], pair[1]
    return "❌", "⭕"


def _get_inline_style_button_ids(game: dict) -> Tuple[Optional[str], Optional[str]]:
    style_pack = game.get("style_pack") or {}
    pair = style_pack.get("button_ids")
    if pair and len(pair) == 2:
        return pair[0], pair[1]
    return None, None


def _make_text_btn(
    *,
    text: str,
    callback_data: str,
    icon_custom_emoji_id: Optional[str] = None,
) -> InlineKeyboardButton:
    kwargs = {
        "text": text,
        "callback_data": callback_data,
    }
    if icon_custom_emoji_id:
        kwargs["icon_custom_emoji_id"] = str(icon_custom_emoji_id)

    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(**kwargs)


def _make_simple_btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def _build_inline_size_selector(game_id: str, current_size: str, started: bool = False) -> List[InlineKeyboardButton]:
    sizes = ["3x3", "5x5", "7x7"]
    prefix = "2tart_set_board" if started else "3set_board"

    buttons: List[InlineKeyboardButton] = []
    for size in sizes:
        label = f"• {size}" if size == current_size else size
        buttons.append(
            _make_text_btn(
                text=label,
                callback_data=f"{prefix}:{size}:{game_id}",
            )
        )
    return buttons


def _build_inline_lobby_keyboard(game_id: str, started: bool = False) -> InlineKeyboardMarkup:
    game = tic_tac_toe_games.get(game_id)
    if not game:
        return InlineKeyboardMarkup(inline_keyboard=[])

    current_size = game.get("board_size", "3x3")
    top_row = _build_inline_size_selector(game_id, current_size, started=started)

    style_pack = game.get("style_pack") or {}
    btn1, btn2 = _get_inline_style_button_ids(game)

    if not started:
        bottom = _make_text_btn(
            text="Присоединиться",
            callback_data=f"1tic_tac_join:{game_id}:{current_size}",
            icon_custom_emoji_id=btn2,
        )
    else:
        bottom = _make_text_btn(
            text="Начать игру",
            callback_data=f"start_tictactoe:{game_id}:{current_size}",
            icon_custom_emoji_id=btn1,
        )

    return InlineKeyboardMarkup(inline_keyboard=[top_row, [bottom]])


async def _build_inline_participants_text(game: dict) -> str:
    creator_id = int(game["creator"])
    opponent_id = game.get("opponent_id")

    text_1, text_2 = _get_inline_style_text_pair(game)

    creator_firstname = game.get("creator_name") or await db.get_firstname_by_user_id(creator_id)
    creator_username = game.get("creator_username") or await db.get_username_by_user_id(creator_id)
    creator_link = await create_user_link(creator_id, creator_firstname, creator_username)

    lines = [f"<b>{text_1} - {creator_link}</b>"]

    if opponent_id:
        opponent_firstname = game.get("opponent_name") or await db.get_firstname_by_user_id(opponent_id)
        opponent_username = game.get("opponent_username") or await db.get_username_by_user_id(opponent_id)
        opponent_link = await create_user_link(opponent_id, opponent_firstname, opponent_username)
        lines.append(f"<b>{text_2} - {opponent_link}</b>")
    else:
        lines.append(f"<b>{text_2} ?</b>")

    return "\n".join(lines)


def _get_inline_bet_text(game: dict) -> str:
    bet_amount = int(game.get("bet_amount", 0) or 0)
    if bet_amount <= 0:
        return ""
    return f"<tg-emoji emoji-id='5292146637844543370'>💰</tg-emoji> <b>Ставка : {_fmt_int(bet_amount)} кут</b>\n"


async def _render_inline_lobby_text(game: dict) -> str:
    participants_text = await _build_inline_participants_text(game)
    bet_text = _get_inline_bet_text(game)

    return (
        f"<b><tg-emoji emoji-id='5465143921912846619'>💭</tg-emoji> Играем в Крестики-нолики</b>\n"
        f"{bet_text}"
        f"{participants_text}"
    )


async def _sync_inline_user(callback_query: types.CallbackQuery) -> None:
    user_id = callback_query.from_user.id
    first_name = re.sub(r'[<>/{}"]', '', (callback_query.from_user.first_name or "Игрок"))
    username = callback_query.from_user.username
    await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)


# =========================================================
# CREATE GAME
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("tic_tac_create"))
async def inline_tic_tac_create_game_callback(callback_query: types.CallbackQuery):
    try:
        creator_id = callback_query.from_user.id
        user_id = callback_query.from_user.id

        await _sync_inline_user(callback_query)

        if await db.is_user_banned(user_id):
            await callback_query.answer("❗️ Вы заблокированы в боте")
            return

        data_parts = callback_query.data.split(":")
        bet_amount = int(data_parts[2]) if len(data_parts) > 2 and str(data_parts[2]).isdigit() else 0

        if bet_amount > 0:
            user_balance = await db.get_user_balance(user_id)
            if user_balance is None or int(user_balance) < bet_amount:
                await callback_query.answer("💭 Недостаточно средств для игры с такой ставкой.", show_alert=True)
                return

        await callback_query.answer()

        game_id = str(uuid.uuid4())
        style_pack = _get_random_inline_ttt_style()
        plain_1, _ = _get_inline_style_plain_pair({"style_pack": style_pack})

        tic_tac_toe_games[game_id] = {
            "game_id": game_id,
            "board": [" "] * 9,
            "turn": creator_id,
            "creator": creator_id,
            "opponent": None,
            "opponent_id": None,
            "symbols": {creator_id: plain_1},
            "style_pack": style_pack,
            "creator_name": callback_query.from_user.first_name or "Игрок 1",
            "creator_username": callback_query.from_user.username,
            "opponent_name": None,
            "opponent_username": None,
            "board_size": "3x3",
            "bet_amount": bet_amount,
            "inline_message_id": callback_query.inline_message_id,
        }

        keyboard = _build_inline_lobby_keyboard(game_id, started=False)
        text = await _render_inline_lobby_text(tic_tac_toe_games[game_id])

        await bot1.edit_message_text(
            text=text,
            inline_message_id=callback_query.inline_message_id,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    except Exception as e:
        print(f"[INLINE_TTT][CREATE] {e}")
    finally:
        try:
            tic_tac_toe_games.save()
        except Exception:
            pass


# =========================================================
# SET BOARD SIZE BEFORE JOIN
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("3set_board:"))
async def inline_tic_tac_set_board_size(callback: types.CallbackQuery):
    try:
        _, board_size, game_id = callback.data.split(":")
        await _sync_inline_user(callback)

        user_id = callback.from_user.id
        if await db.is_user_banned(user_id):
            await callback.answer("❗️ Вы заблокированы в боте")
            return

        game = tic_tac_toe_games.get(game_id)
        if not game:
            await callback.answer("🛠 Игра не найдена.", show_alert=True)
            return

        if callback.from_user.id != game["creator"]:
            await callback.answer("❗️ Только создатель игры может менять формат.", show_alert=True)
            return

        if game["board_size"] == board_size:
            await callback.answer(f"❕ Формат {board_size} уже установлен", show_alert=True)
            return

        game["board_size"] = board_size
        game["board"] = [" "] * (_board_size_to_int(board_size) ** 2)

        keyboard = _build_inline_lobby_keyboard(game_id, started=False)
        await callback.answer(f"❕ Формат игры изменён на {board_size}")

        if callback.inline_message_id:
            await bot1.edit_message_reply_markup(
                inline_message_id=callback.inline_message_id,
                reply_markup=keyboard,
            )

    except Exception as e:
        print(f"[INLINE_TTT][SET_BOARD] {e}")
    finally:
        try:
            tic_tac_toe_games.save()
        except Exception:
            pass


# =========================================================
# SET BOARD SIZE AFTER JOIN
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("2tart_set_board:"))
async def inline_tic_tac_set_board_start_size(callback: types.CallbackQuery):
    try:
        _, board_size, game_id = callback.data.split(":")
        await _sync_inline_user(callback)

        game = tic_tac_toe_games.get(game_id)
        if not game:
            await callback.answer("🛠 Игра не найдена.", show_alert=True)
            return

        if callback.from_user.id != game["creator"]:
            await callback.answer("❗️ Только создатель игры может менять формат.", show_alert=True)
            return

        if game["board_size"] == board_size:
            await callback.answer(f"❕ Формат {board_size} уже установлен")
            return

        game["board_size"] = board_size
        game["board"] = [" "] * (_board_size_to_int(board_size) ** 2)

        keyboard = _build_inline_lobby_keyboard(game_id, started=True)
        await callback.answer(f"❕ Формат игры изменён на {board_size}")

        if callback.inline_message_id:
            await bot1.edit_message_reply_markup(
                inline_message_id=callback.inline_message_id,
                reply_markup=keyboard,
            )

    except Exception as e:
        print(f"[INLINE_TTT][SET_BOARD_STARTED] {e}")
    finally:
        try:
            tic_tac_toe_games.save()
        except Exception:
            pass


# =========================================================
# JOIN GAME
# =========================================================

_ttt_inline_join_locks: Dict[str, asyncio.Lock] = {}
_ttt_inline_inflight: Set[Tuple[str, int]] = set()


def _get_ttt_inline_lock(game_id: str) -> asyncio.Lock:
    lock = _ttt_inline_join_locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _ttt_inline_join_locks[game_id] = lock
    return lock


@dp.callback_query(lambda c: c.data and c.data.startswith("1tic_tac_join:"))
async def inline_tic_tac_join_game_callback(callback_query: types.CallbackQuery):
    game_id = "?"
    user_id = callback_query.from_user.id

    try:
        parts = callback_query.data.split(":")
        if len(parts) < 3:
            await callback_query.answer("🛠 Неверные данные игры.", show_alert=True)
            return

        game_id = parts[1]
        requested_board_size = parts[2]

        await _sync_inline_user(callback_query)

        game = tic_tac_toe_games.get(game_id)
        if not game:
            await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
            return

        inflight_key = (game_id, user_id)
        if inflight_key in _ttt_inline_inflight:
            await callback_query.answer("⏳ Обрабатываю ваше присоединение…")
            return
        _ttt_inline_inflight.add(inflight_key)

        lock = _get_ttt_inline_lock(game_id)
        async with lock:
            game = tic_tac_toe_games.get(game_id)
            if not game:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            creator_id = int(game["creator"])
            if user_id == creator_id:
                await callback_query.answer("❗️ Вы не можете присоединиться к своей игре.", show_alert=True)
                return

            if game.get("opponent") is not None:
                await callback_query.answer("❗️ Игра уже заполнена.", show_alert=True)
                return

            bet_amount = int(game.get("bet_amount", 0) or 0)
            if bet_amount > 0:
                try:
                    bal = await db.get_user_balance(user_id)
                    enough = (bal is not None) and int(bal) >= bet_amount
                except Exception:
                    enough = False

                if not enough:
                    await callback_query.answer("❌ Недостаточно средств для игры.", show_alert=True)
                    return

            try:
                if hasattr(db, "remove_expired_refout"):
                    await db.remove_expired_refout()
                elif hasattr(db, "cleanup_expired_refout"):
                    await db.cleanup_expired_refout()
            except Exception:
                pass

            participants_user_ids = {creator_id}
            if game.get("opponent"):
                try:
                    participants_user_ids.add(int(game["opponent"]))
                except Exception:
                    pass

            try:
                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    inviter_id = None

                if inviter_id is not None:
                    inviter_id = int(inviter_id)

                if inviter_id and inviter_id in participants_user_ids:
                    secs = await _pair_seconds_left(db, user_id, inviter_id, now=datetime.now())
                    if secs > 0:
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь, который пригласил вас в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения: {_format_hms(secs)}\n#AntiFarmSystem",
                            show_alert=True,
                        )
                        return
            except Exception:
                await callback_query.answer(
                    "💭 Техническая ошибка. Обратитесь к @JerichoCute. Код ошибки: #1212471",
                    show_alert=True,
                )
                return

            try:
                invitees_here = await db.get_invitees_in(
                    inviter_id=user_id,
                    candidates=list(participants_user_ids),
                )
                if invitees_here:
                    min_secs: Optional[int] = None
                    for inv_id in invitees_here:
                        try:
                            inv_id = int(inv_id)
                        except Exception:
                            continue
                        secs = await _pair_seconds_left(db, user_id, inv_id, now=datetime.now())
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)

                    if min_secs is not None:
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь, которого вы пригласили в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения: {_format_hms(min_secs)}\n#AntiFarmSystem",
                            show_alert=True,
                        )
                        return
            except Exception:
                await callback_query.answer(
                    "💭 Техническая ошибка. Обратитесь к @JerichoCute. Код ошибки: #1212471",
                    show_alert=True,
                )
                return

            if game.get("opponent") is not None:
                await callback_query.answer("❗️ Игра уже заполнена.", show_alert=True)
                return

            game["opponent"] = user_id
            game["opponent_id"] = user_id
            game["opponent_name"] = callback_query.from_user.first_name or "Игрок 2"
            game["opponent_username"] = callback_query.from_user.username

            plain_1, plain_2 = _get_inline_style_plain_pair(game)
            game.setdefault("symbols", {})
            game["symbols"].setdefault(creator_id, plain_1)
            game["symbols"][user_id] = plain_2

            if requested_board_size in {"3x3", "5x5", "7x7"}:
                game["board_size"] = requested_board_size

            keyboard = _build_inline_lobby_keyboard(game_id, started=True)
            text = await _render_inline_lobby_text(game)

            try:
                await bot1.edit_message_text(
                    text=text,
                    inline_message_id=game.get("inline_message_id"),
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except (TelegramAPIError, TelegramBadRequest) as e:
                if "message is not modified" not in str(e).lower():
                    print(f"[INLINE_TTT][JOIN][EDIT] {e}")

            await callback_query.answer("❕ Вы присоединились к игре!")

    except Exception as e:
        print(f"[INLINE_TTT][JOIN] {e}")
        try:
            await callback_query.answer("💭 Ошибка присоединения к лобби.", show_alert=True)
        except Exception:
            pass
    finally:
        _ttt_inline_inflight.discard((game_id, user_id))
        try:
            tic_tac_toe_games.save()
        except Exception:
            pass


# =========================================================
# START GAME
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("start_tictactoe:"))
async def inline_tic_tac_start_game_callback(callback_query: types.CallbackQuery):
    try:
        game_id, board_size = callback_query.data.split(":")[1:]
        await _sync_inline_user(callback_query)

        game = tic_tac_toe_games.get(game_id)
        if not game:
            await callback_query.answer("🛠 Игра не найдена.", show_alert=True)
            return

        if int(game["creator"]) != callback_query.from_user.id:
            await callback_query.answer("❗️ Только создатель игры может начать её.", show_alert=True)
            return

        if not game.get("opponent_id"):
            await callback_query.answer("❗️ Недостаточно участников для начала игры.", show_alert=True)
            return

        bet_amount = int(game.get("bet_amount", 0) or 0)

        if bet_amount > 0:
            creator_balance = await db.get_user_balance(callback_query.from_user.id)
            if creator_balance is None or int(creator_balance) < bet_amount:
                await callback_query.answer("❌ Недостаточно средств для игры.", show_alert=True)
                return

            opponent_balance = await db.get_user_balance(game["opponent_id"])
            if opponent_balance is None or int(opponent_balance) < bet_amount:
                await callback_query.answer("❌ У второго игрока недостаточно средств.", show_alert=True)
                return

        creator_id = int(game["creator"])
        participant_id = int(game["opponent_id"])

        creator_username = game.get("creator_username")
        creator_name = game.get("creator_name", "Игрок 1")
        participant_username = game.get("opponent_username")
        participant_name = game.get("opponent_name", "Игрок 2")

        await db.add_game_inline(
            user_id1=creator_id,
            name_user1=creator_name,
            user_id2=participant_id,
            name_user2=participant_name,
            namegame="tictac",
            username1=creator_username,
            username2=participant_username,
        )

        board_size_int = _board_size_to_int(game.get("board_size", "3x3"))
        game["board"] = [" "] * (board_size_int * board_size_int)
        game["turn"] = creator_id

        plain_1, plain_2 = _get_inline_style_plain_pair(game)
        game["symbols"] = {
            creator_id: plain_1,
            participant_id: plain_2,
        }

        await display_board(game_id, game.get("inline_message_id"))
        await callback_query.answer("❕ Игра началась!")

    except Exception as e:
        print(f"[INLINE_TTT][START] {e}")
        print("Произошла ошибка при старте игры.")
    finally:
        try:
            tic_tac_toe_games.save()
        except Exception:
            pass


# =========================================================
# DISPLAY BOARD
# ВАЖНО: ДИЗАЙН КНОПОК В САМОЙ ИГРЕ НЕ ТРОГАЕМ
# =========================================================

async def display_board(game_id: str, inline_message_id: str):
    game = tic_tac_toe_games.get(game_id)
    if not game:
        return

    board_size_str = game["board_size"]
    board_size = _board_size_to_int(board_size_str)
    board = game["board"]

    buttons = [
        [
            InlineKeyboardButton(
                text=board[i * board_size + j] if board[i * board_size + j] != " " else " ",
                callback_data=f"inlinemovetictactoe:{game_id}:{i * board_size + j}"
            )
            for j in range(board_size)
        ]
        for i in range(board_size)
    ]

    buttons.append([
        InlineKeyboardButton(
            text="Сдаться",
            callback_data=f"inlinesurrendertictactoe:{game_id}"
        )
    ])

    choices_keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    current_player_id = int(game["turn"])
    text_1, text_2 = _get_inline_style_text_pair(game)
    plain_1, plain_2 = _get_inline_style_plain_pair(game)

    current_symbol_plain = game["symbols"][current_player_id]
    current_symbol = text_1 if current_symbol_plain == plain_1 else text_2

    if current_player_id == int(game["creator"]):
        current_name = game.get("creator_name", "Игрок 1")
        current_username = game.get("creator_username")
    else:
        current_name = game.get("opponent_name", "Игрок 2")
        current_username = game.get("opponent_username")

    current_link = await create_user_link(current_player_id, current_name, current_username)

    await bot1.edit_message_text(
        text=f"{current_symbol} <b>Ход {current_link}</b>",
        inline_message_id=inline_message_id,
        reply_markup=choices_keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# =========================================================
# MOVE
# ВАЖНО: КНОПКИ ПОЛЯ НЕ УЛУЧШАЕМ
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("inlinemovetictactoe:"))
async def inline_tic_tac_make_move_callback(callback_query: types.CallbackQuery):
    try:
        game_id, position = callback_query.data.split(":")[1:3]
        position = int(position)
        user_id = callback_query.from_user.id

        await _sync_inline_user(callback_query)

        game = tic_tac_toe_games.get(game_id)
        if game is None:
            await callback_query.answer("🛠 Эта игра больше не существует.")
            return

        inline_message_id = game.get("inline_message_id")

        now = time.time()
        if now - inline_ttt_cooldowns.get(user_id, 0) < INLINE_TTT_REST:
            remaining_time = INLINE_TTT_REST - (now - inline_ttt_cooldowns[user_id])
            await callback_query.answer(f"⌚️ Подождите {int(remaining_time) + 1} сек.", show_alert=True)
            return
        inline_ttt_cooldowns[user_id] = now

        if user_id not in [int(game["creator"]), int(game["opponent"])]:
            await callback_query.answer("❗️ Вы не участвуете в этой игре.")
            return

        if int(game["turn"]) != user_id:
            await callback_query.answer("❗️ Это не ваш ход.")
            return

        board_size = _board_size_to_int(game["board_size"])

        if game["board"][position] != " ":
            await callback_query.answer("❗️ Это поле уже занято.")
            return

        await callback_query.answer()

        game["board"][position] = game["symbols"][user_id]
        symbol = game["symbols"][user_id]

        if check_winner(game["board"], symbol, board_size):
            winner_id = user_id
            loser_id = int(game["creator"]) if user_id == int(game["opponent"]) else int(game["opponent"])

            winner_name = game["creator_name"] if winner_id == int(game["creator"]) else game["opponent_name"]
            winner_username = game["creator_username"] if winner_id == int(game["creator"]) else game["opponent_username"]

            winner_link = await create_user_link(winner_id, winner_name, winner_username)

            winner_balance = await db.get_user_balance(winner_id)
            loser_balance = await db.get_user_balance(loser_id)
            bet_amount = int(game.get("bet_amount", 0) or 0)

            chat_id = 0
            chat_name = "inline"

            last_open_time, data_open = await db.get_historygames_times(winner_id)
            current_time_ts = time.time()

            if last_open_time is None or data_open is None:
                last_open_time = get_current_time_formatted()
                data_open = current_time_ts + timehistorygames
                user_name = await db.get_firstname_by_user_id(winner_id)
                await db.add_historygames(
                    chat_id,
                    chat_name,
                    winner_id,
                    user_name,
                    last_open_time,
                    datetime.fromtimestamp(data_open).strftime("%Y-%m-%d %H:%M:%S"),
                )
            else:
                try:
                    data_open_timestamp = data_open.timestamp()
                except Exception as e:
                    print(f"[INLINE_TTT][BONUS][TIMESTAMP] {e}")
                    data_open_timestamp = None

                if data_open_timestamp is not None:
                    last_open_time = get_current_time_formatted()
                    data_open = current_time_ts + timehistorygames
                    await db.update_historygames(
                        winner_id,
                        last_open_time,
                        datetime.fromtimestamp(data_open).strftime("%Y-%m-%d %H:%M:%S"),
                    )

            await db.update_user_loose(loser_id, 1, bot1, ref_coin)#
            await db.update_user_wins(winner_id, 1, bot1, ref_coin)
            await db.update_game_last_activity(loser_id)
            await db.update_game_last_activity(winner_id)

            if bet_amount > 0:
                if loser_balance is not None and int(loser_balance) >= bet_amount:
                    await db.update_user_balance(winner_id, int(winner_balance or 0) + bet_amount)
                    await db.update_user_balance(loser_id, int(loser_balance) - bet_amount)
                    await db.touch_balance_last_active(winner_id, set_active_status=True)
                    await db.touch_balance_last_active(loser_id, set_active_status=True)
                    await db.cutehistory_plus(winner_id, bet_amount, "инлайн кн")
                    await db.cutehistory_minus(loser_id, bet_amount, "инлайн кн")

                    results_text = (
                        f"<tg-emoji emoji-id='5262688775716234060'>🏆</tg-emoji> "
                        f"<b>Победа для {winner_link}!</b>\n"
                        f"<tg-emoji emoji-id='5292146637844543370'>💰</tg-emoji> "
                        f"<b>Выигрыш {_fmt_int(bet_amount)} кут</b>"
                    )
                else:
                    results_text = (
                        f"<tg-emoji emoji-id='5262688775716234060'>🏆</tg-emoji> "
                        f"<b>Победа для {winner_link}!</b>\n"
                        f"<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> "
                        f"<b>У проигравшего нет средств для выплаты выигрыша.</b>"
                    )

                btn_create_game = _make_text_btn(
                    text="Создать новую игру",
                    callback_data=f"tic_tac_create:{winner_id}:{bet_amount}",
                    icon_custom_emoji_id="5438440765908874600",
                )
            else:
                results_text = (
                    f"<tg-emoji emoji-id='5262688775716234060'>🏆</tg-emoji> "
                    f"<b>Победа для {winner_link}!</b>"
                )
                btn_create_game = _make_text_btn(
                    text="Создать новую игру",
                    callback_data="tic_tac_create",
                    icon_custom_emoji_id="5438440765908874600",
                )

            board = game["board"]
            board_size_str = game["board_size"]
            board_size_int = _board_size_to_int(board_size_str)

            buttons = [
                [
                    InlineKeyboardButton(
                        text=board[i * board_size_int + j] if board[i * board_size_int + j] != " " else " ",
                        callback_data=f"inlinemovetictactoe:{game_id}:{i * board_size_int + j}"
                    )
                    for j in range(board_size_int)
                ]
                for i in range(board_size_int)
            ]
            buttons.append([btn_create_game])

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await bot1.edit_message_text(
                text=results_text,
                inline_message_id=inline_message_id,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

            del tic_tac_toe_games[game_id]
            return

        if " " not in game["board"]:
            btn_create_game = _make_text_btn(
                text="Создать новую игру",
                callback_data="tic_tac_create",
                icon_custom_emoji_id="5438440765908874600",
            )

            board = game["board"]
            board_size_str = game["board_size"]
            board_size_int = _board_size_to_int(board_size_str)

            buttons = [
                [
                    InlineKeyboardButton(
                        text=board[i * board_size_int + j] if board[i * board_size_int + j] != " " else " ",
                        callback_data=f"inlinemovetictactoe:{game_id}:{i * board_size_int + j}"
                    )
                    for j in range(board_size_int)
                ]
                for i in range(board_size_int)
            ]
            buttons.append([btn_create_game])

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await bot1.edit_message_text(
                text="<tg-emoji emoji-id='5357080225463149588'>🤝</tg-emoji> <b>Ничья!</b>",
                inline_message_id=inline_message_id,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

            del tic_tac_toe_games[game_id]
            await callback_query.answer("❕ Ничья!")
            return

        game["turn"] = int(game["creator"]) if int(game["turn"]) == int(game["opponent"]) else int(game["opponent"])
        await display_board(game_id, inline_message_id)

    except Exception as e:
        print(f"[INLINE_TTT][MOVE] {e}")
        try:
            await callback_query.answer("💭 Ошибка хода.", show_alert=True)
        except Exception:
            pass
    finally:
        try:
            tic_tac_toe_games.save()
        except Exception:
            pass


# =========================================================
# SURRENDER
# ВАЖНО: КНОПКИ ПОЛЯ НЕ УЛУЧШАЕМ
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("inlinesurrendertictactoe:"))
async def inline_tic_tac_surrender_callback(callback_query: types.CallbackQuery):
    try:
        game_id = callback_query.data.split(":")[1]
        user_id = callback_query.from_user.id

        await _sync_inline_user(callback_query)

        game = tic_tac_toe_games.get(game_id)
        if game is None:
            await callback_query.answer("🛠 Эта игра больше не существует.")
            return

        inline_message_id = game.get("inline_message_id")

        if user_id not in [int(game["creator"]), int(game["opponent"])]:
            await callback_query.answer("❗️ Вы не участвуете в этой игре.")
            return

        if user_id == int(game["creator"]):
            winner_id = int(game["opponent"])
            winner_name = game["opponent_name"]
            winner_username = game["opponent_username"]
            loser_name = game["creator_name"]
            loser_id = int(game["creator"])
        else:
            winner_id = int(game["creator"])
            winner_name = game["creator_name"]
            winner_username = game["creator_username"]
            loser_name = game["opponent_name"]
            loser_id = int(game["opponent"])

        winner_link = await create_user_link(winner_id, winner_name, winner_username)

        bet_amount = int(game.get("bet_amount", 0) or 0)
        await db.update_user_wins(winner_id, 1, bot1, ref_coin)
        await db.update_user_loose(loser_id, 1, bot1, ref_coin)#
        await db.update_game_last_activity(winner_id)
        await db.update_game_last_activity(loser_id)

        if bet_amount > 0:
            winner_balance = await db.get_user_balance(winner_id)
            loser_balance = await db.get_user_balance(loser_id)

            if loser_balance is None or int(loser_balance) < bet_amount:
                await callback_query.answer("❌ Недостаточно средств для выплаты выигрыша победителю", show_alert=True)
                return

            await db.update_user_balance(winner_id, int(winner_balance or 0) + bet_amount)
            await db.update_user_balance(loser_id, int(loser_balance) - bet_amount)
            await db.cutehistory_plus(winner_id, bet_amount, "инлайн кн сдача")
            await db.cutehistory_minus(loser_id, bet_amount, "инлайн кн сдача")

            results_text = (
                f"<tg-emoji emoji-id='5411285332668720752'>🏳️</tg-emoji> "
                f"<b>Игра завершена! {_escape(loser_name)} сдался.</b>\n"
                f"<tg-emoji emoji-id='5262688775716234060'>🏆</tg-emoji> "
                f"<b>{winner_link}</b>\n"
                f"<tg-emoji emoji-id='5292146637844543370'>💰</tg-emoji> "
                f"<b>Выигрыш {_fmt_int(bet_amount)} кут</b>"
            )

            btn_create_game = _make_text_btn(
                text="Создать новую игру",
                callback_data=f"tic_tac_create:{winner_id}:{bet_amount}",
                icon_custom_emoji_id="5438440765908874600",
            )
        else:
            results_text = (
                f"<tg-emoji emoji-id='5411285332668720752'>🏳️</tg-emoji> "
                f"<b>Игра завершена! {_escape(loser_name)} сдался.</b>\n"
                f"<tg-emoji emoji-id='5262688775716234060'>🏆</tg-emoji> "
                f"<b>{winner_link}</b>"
            )
            btn_create_game = _make_text_btn(
                text="Создать новую игру",
                callback_data="tic_tac_create",
                icon_custom_emoji_id="5438440765908874600",
            )

        board = game["board"]
        board_size_str = game["board_size"]
        board_size_int = _board_size_to_int(board_size_str)

        buttons = [
            [
                InlineKeyboardButton(
                    text=board[i * board_size_int + j] if board[i * board_size_int + j] != " " else " ",
                    callback_data=f"inlinemovetictactoe:{game_id}:{i * board_size_int + j}"
                )
                for j in range(board_size_int)
            ]
            for i in range(board_size_int)
        ]
        buttons.append([btn_create_game])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await bot1.edit_message_text(
            text=results_text,
            inline_message_id=inline_message_id,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

        del tic_tac_toe_games[game_id]
        await callback_query.answer("❕ Вы сдались.")

    except Exception as e:
        print(f"[INLINE_TTT][SURRENDER] {e}")
        try:
            await callback_query.answer("💭 Ошибка при сдаче.", show_alert=True)
        except Exception:
            pass
    finally:
        try:
            tic_tac_toe_games.save()
        except Exception:
            pass


# =========================================================
# WIN CHECK
# =========================================================

def check_winner(board, symbol, board_size):
    if board_size == 3:
        win_condition = 3
    elif board_size == 5:
        win_condition = 4
    elif board_size == 7:
        win_condition = 6
    else:
        return False

    for row in range(board_size):
        count = 0
        for col in range(board_size):
            if board[row * board_size + col] == symbol:
                count += 1
                if count >= win_condition:
                    return True
            else:
                count = 0

    for col in range(board_size):
        count = 0
        for row in range(board_size):
            if board[row * board_size + col] == symbol:
                count += 1
                if count >= win_condition:
                    return True
            else:
                count = 0

    for start_row in range(board_size - win_condition + 1):
        for start_col in range(board_size - win_condition + 1):
            count = 0
            for i in range(win_condition):
                if board[(start_row + i) * board_size + (start_col + i)] == symbol:
                    count += 1
                    if count >= win_condition:
                        return True
                else:
                    break

    for start_row in range(board_size - win_condition + 1):
        for start_col in range(win_condition - 1, board_size):
            count = 0
            for i in range(win_condition):
                if board[(start_row + i) * board_size + (start_col - i)] == symbol:
                    count += 1
                    if count >= win_condition:
                        return True
                else:
                    break

    return False


# =========================================================
# NOOP
# =========================================================

@dp.callback_query(lambda c: c.data == "noop_inline_ttt")
async def noop_inline_ttt_callback(callback_query: types.CallbackQuery):
    try:
        await callback_query.answer()
    except Exception:
        pass