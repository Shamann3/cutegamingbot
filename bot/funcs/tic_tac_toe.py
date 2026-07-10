import asyncio
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any

from aiogram import F, types
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.enums import ParseMode, ChatType
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramAPIError
from aiogram import exceptions as aiogram_exceptions
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.design.buttons import *
from bot.db_create.db import *
from bot.config.config import *
from bot.funcs.func import *

from main import (
    games_tictactoe,
    _format_hms,
    _pair_seconds_left,
    button_games_tictactoe,
    db,
    bot1,
    dp,
    get_current_time_formatted,
    timehistorygames,
    check_bet_and_set_item,
    pending_context,
    send_invoice_to_user,
)

# =========================================================
# PREMIUM TTT DESIGN
# =========================================================

REST = 1.2
tictac_cooldowns: Dict[int, float] = {}

# text -> для текста сообщений
# plain -> для логики игры
# button_ids -> для premium emoji в кнопках
TTT_STYLE_PACKS: List[Dict[str, Any]] = [
    {
        "key": "banana_strawberry",
        "text": (
            "<tg-emoji emoji-id='5390950002551954897'>🍌</tg-emoji>",
            "<tg-emoji emoji-id='5469963154391833732'>🍓</tg-emoji>",
        ),
        "plain": ("🍌", "🍓"),
        "button_ids": ("5390950002551954897", "5469963154391833732"),
    },
    {
        "key": "money_hat",
        "text": (
            "<tg-emoji emoji-id='5359736160224586485'>🎁</tg-emoji>",
            "<tg-emoji emoji-id='5317000922096769303'>🎁</tg-emoji>",
        ),
        "plain": ("💰", "🎩"),
        "button_ids": ("5359736160224586485", "5317000922096769303"),
    },
    {
        "key": "water_fire",
        "text": (
            "<tg-emoji emoji-id='5292223693852798706'>💧</tg-emoji>",
            "<tg-emoji emoji-id='5424972470023104089'>🔥</tg-emoji>",
        ),
        "plain": ("💧", "🔥"),
        "button_ids": ("5393512611968995988", "4956499161319998529"),
    },
    {
        "key": "15",
        "text": (
            "<tg-emoji emoji-id='5289761157173775507'>🧸</tg-emoji>",
            "<tg-emoji emoji-id='5226661632259691727'>🎁</tg-emoji>",
        ),
        "plain": ("💧", "🔥"),
        "button_ids": ("5289761157173775507", "5226661632259691727"),
    },
    {
        "key": "14",
        "text": (
            "<tg-emoji emoji-id='5424616516018537963'>🎁</tg-emoji>",
            "<tg-emoji emoji-id='5255850874248399164'>🎁</tg-emoji>",
        ),
        "plain": ("💧", "🔥"),
        "button_ids": ("5424616516018537963", "5255850874248399164"),
    },
    {
        "key": "13",
        "text": (
            "<tg-emoji emoji-id='5246891546699136867'>🐒</tg-emoji>",
            "<tg-emoji emoji-id='5334675412599480338'>📕</tg-emoji>",
        ),
        "plain": ("💧", "🔥"),
        "button_ids": ("5246891546699136867", "5334675412599480338"),
    },
    {
        "key": "111",
        "text": (
            "<tg-emoji emoji-id='5436371618169389408'>🎁</tg-emoji>",
            "<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji>",
        ),
        "plain": ("💧", "🔥"),
        "button_ids": ("5436371618169389408", "5438440765908874600"),
    },
    {
        "key": "11",
        "text": (
            "<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji>",
            "<tg-emoji emoji-id='5438529285184847871'>🎁</tg-emoji>",
        ),
        "plain": ("💧", "🔥"),
        "button_ids": ("5438440765908874600", "5438529285184847871"),
    },
    {
        "key": "12",
        "text": (
            "<tg-emoji emoji-id='5244710862953941180'>🎁</tg-emoji>",
            "<tg-emoji emoji-id='5422812530969967956'>🎁</tg-emoji>",
        ),
        "plain": ("💧", "🔥"),
        "button_ids": ("5244710862953941180", "5422812530969967956"),
    },
    {
        "key": "1234",
        "text": (
            "<tg-emoji emoji-id='5168270972049949836'>🎁</tg-emoji>",
            "<tg-emoji emoji-id='5168005895258375563'>🎁</tg-emoji>",
        ),
        "plain": ("💧", "🔥"),
        "button_ids": ("5168270972049949836", "5168005895258375563"),
    },
    {
        "key": "12345",
        "text": (
            "<tg-emoji emoji-id='5168039155485115595'>🎁</tg-emoji>",
            "<tg-emoji emoji-id='5165979207565575234'>🎁</tg-emoji>",
        ),
        "plain": ("💧", "🔥"),
        "button_ids": ("5168039155485115595", "5165979207565575234"),
    },
]


def _get_random_ttt_style() -> Dict[str, Any]:
    return random.choice(TTT_STYLE_PACKS)


def _get_style_text_pair(game: dict) -> Tuple[str, str]:
    style_pack = game.get("style_pack") or {}
    pair = style_pack.get("text")
    if pair and len(pair) == 2:
        return pair[0], pair[1]
    return "❌", "⭕"


def _get_style_plain_pair(game: dict) -> Tuple[str, str]:
    style_pack = game.get("style_pack") or {}
    pair = style_pack.get("plain")
    if pair and len(pair) == 2:
        return pair[0], pair[1]
    return "❌", "⭕"


def _get_style_button_ids(game: dict) -> Tuple[Optional[str], Optional[str]]:
    style_pack = game.get("style_pack") or {}
    pair = style_pack.get("button_ids")
    if pair and len(pair) == 2:
        return pair[0], pair[1]
    return None, None


def _make_inline_btn(
    *,
    callback_data: str,
    text: str = " ",
    icon_custom_emoji_id: Optional[str] = None,
    style: str = "default",
) -> InlineKeyboardButton:
    kwargs = {
        "text": text,
        "callback_data": callback_data,
        "style": style,
    }
    if icon_custom_emoji_id:
        kwargs["icon_custom_emoji_id"] = str(icon_custom_emoji_id)
    return InlineKeyboardButton(**kwargs)


def _make_text_btn(
    *,
    text: str,
    callback_data: str,
    style: str = "default",
    icon_custom_emoji_id: Optional[str] = None,
) -> InlineKeyboardButton:
    kwargs = {
        "text": text,
        "callback_data": callback_data,
        "style": style,
    }
    if icon_custom_emoji_id:
        kwargs["icon_custom_emoji_id"] = str(icon_custom_emoji_id)
    return InlineKeyboardButton(**kwargs)


def _build_board_keyboard(game_id: int, with_surrender: bool = True, freeze_board: bool = False) -> InlineKeyboardMarkup:
    game = games_tictactoe.get(game_id)
    if not game:
        return InlineKeyboardMarkup(inline_keyboard=[])

    board = game.get("board", [])
    board_size = {"7x7": 7, "5x5": 5, "3x3": 3}.get(game.get("board_size", "3x3"), 3)

    plain_1, plain_2 = _get_style_plain_pair(game)
    btn_1, btn_2 = _get_style_button_ids(game)

    rows: List[List[InlineKeyboardButton]] = []

    for row_start in range(0, len(board), board_size):
        row_buttons: List[InlineKeyboardButton] = []

        for i in range(row_start, min(row_start + board_size, len(board))):
            cell_value = board[i]
            cb = "noop_ttt" if freeze_board else f"movetictactoe:{game_id}:{i}"

            if cell_value == plain_1:
                row_buttons.append(
                    _make_inline_btn(
                        callback_data=cb,
                        text=" ",
                        icon_custom_emoji_id=btn_1,
                        style="default",
                    )
                )
            elif cell_value == plain_2:
                row_buttons.append(
                    _make_inline_btn(
                        callback_data=cb,
                        text=" ",
                        icon_custom_emoji_id=btn_2,
                        style="default",
                    )
                )
            else:
                row_buttons.append(
                    _make_inline_btn(
                        callback_data=cb,
                        text=" ",
                        style="default",
                    )
                )

        rows.append(row_buttons)

    if with_surrender and not freeze_board:
        rows.append([
            _make_text_btn(
                text="Сдаться",
                callback_data=f"surrendertictactoe:{game_id}",
                style="default",
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_size_selector(game_id: int, started: bool = False) -> List[InlineKeyboardButton]:
    game = games_tictactoe.get(game_id)
    if not game:
        return []

    current_size = game.get("board_size", "3x3")
    sizes = ["3x3", "5x5", "7x7"]
    prefix = "tart_set_board" if started else "set_board"

    buttons: List[InlineKeyboardButton] = []
    for size in sizes:
        label = f"• {size}" if size == current_size else size
        buttons.append(
            _make_text_btn(
                text=label,
                callback_data=f"{prefix}:{size}:{game_id}",
                style="default",
            )
        )
    return buttons


def build_ttt_keyboard(game_id: int) -> InlineKeyboardMarkup:
    game = games_tictactoe.get(game_id)
    if not game:
        return InlineKeyboardMarkup(inline_keyboard=[])

    top_row = _build_size_selector(game_id, started=len(game.get("participants", [])) >= 2)

    if len(game.get("participants", [])) < 2:
        bottom_button = _make_text_btn(
            text="Присоединиться",
            callback_data=f"jointictactoe:{game_id}",
            style="default",
        )
    else:
        bottom_button = _make_text_btn(
            text="Начать игру",
            callback_data=f"starttictactoe:{game_id}",
            style="default",
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[top_row, [bottom_button]]
    )


# =========================================================
# GAME HELPERS
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


async def check_bet(user_id, bet_amount):
    try:
        current_balance = await db.get_user_balance(user_id)

        if current_balance < bet_amount:
            print(f"Недостаточно средств для пользователя {user_id}. Баланс: {current_balance}, Ставка: {bet_amount}")
            return False

        await db.update_user_balance(user_id, current_balance - bet_amount)
        await db.cutehistory_minus(user_id, bet_amount, "- Крестики нолики")

        print(f"Ставка успешно сделана пользователем {user_id}. Баланс после ставки: {current_balance - bet_amount}")
        return True
    except Exception as e:
        print(f"Ошибка в check_bet_and_set_item для пользователя {user_id}: {e}")
        return False


async def checktictactoe_bet_and_set_item(user_id, bet_amount):
    try:
        current_balance = await db.get_user_balance(user_id)

        if current_balance < bet_amount:
            print(f"Недостаточно средств для пользователя {user_id}. Баланс: {current_balance}, Ставка: {bet_amount}")
            return False

        await db.update_user_balance(user_id, current_balance + bet_amount)
        await db.cutehistory_plus(user_id, bet_amount, "+ Крестики нолики")

        print(f"Ставка успешно сделана пользователем {user_id}. Баланс после ставки: {current_balance + bet_amount}")
        return True
    except Exception as e:
        print(f"Ошибка в check_bet_and_set_item для пользователя {user_id}: {e}")
        return False


# =========================================================
# START GAME
# =========================================================

@dp.message()
async def tic_tac_toe(message: Message):
    try:
        if not message.text:
            return

        text = message.text.strip()
        parts = text.split()
        if not parts:
            return

        bet = 0
        bet_str = None
        p0 = parts[0].lower()

        if p0 == "кн":
            if len(parts) == 1:
                bet = 0
            elif len(parts) == 2:
                bet_s = parts[1]
                if not bet_s.isdigit():
                    return
                bet_str = bet_s
            else:
                return

        elif p0 == "крестики":
            if len(parts) == 2 and parts[1].lower() == "нолики":
                bet = 0
            elif len(parts) == 3 and parts[1].lower() == "нолики":
                bet_s = parts[2]
                if not bet_s.isdigit():
                    return
                bet_str = bet_s
            else:
                return
        else:
            return

        bet = int(bet_str) if bet_str is not None else 0

        if bet < 0:
            return

        creator_id = message.from_user.id

        if bet > 0:
            creator_balance = await db.get_user_balance(creator_id)
            if creator_balance is None:
                return

            if int(creator_balance) < int(bet):
                from bot.funcs.help import callbaYTRWEQck_main  # noqa: F401

                button = InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")

                multiplier = donate_bet
                result = bet * multiplier
                bet_amount_str = str(int(result)) if isinstance(result, float) and result.is_integer() else str(result)
                bet_amount_win_formated = "{:,.0f}".format(bet).replace(",", ".")

                try:
                    bot_username = await get_bot_username_by_token(TOKEN)
                except Exception:
                    bot_username = "CuteGamingBot"

                user_id = creator_id
                pending_context[user_id] = {"stars_amount": bet_amount_str, "sent": False}

                button1 = InlineKeyboardButton(
                    text=f"💫 Купить {bet_amount_win_formated} кут 💰",
                    url=f"https://t.me/{bot_username}?start=insert_{bet_amount_str}_+"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[button1], [button]])

                await message.reply(
                    "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )

                await asyncio.sleep(timeoutdonate)

                if user_id in pending_context and not pending_context[user_id].get("sent"):
                    stars_amount = pending_context[user_id]["stars_amount"]
                    invoice_message = await send_invoice_to_user(message, stars_amount)
                    pending_context[user_id]["manual_message_id"] = invoice_message.message_id
                return

        game_id = message.message_id
        style_pack = _get_random_ttt_style()
        text_symbol_1, text_symbol_2 = style_pack["text"]

        games_tictactoe[game_id] = {
            "creator": creator_id,
            "bet": bet,
            "participants": [creator_id],
            "board": [" "] * 9,
            "turn": creator_id,
            "style_pack": style_pack,
            "board_size": "3x3",
            "chat_id": None,
            "message_id": None,
        }

        keyboard = build_ttt_keyboard(game_id)

        button_games_tictactoe[game_id] = {}
        button_games_tictactoe[game_id]["keyboard_join"] = keyboard

        first_name = await db.get_firstname_by_user_id(creator_id)
        username = await db.get_username_by_user_id(creator_id)
        name_link = await create_user_link(creator_id, first_name, username)

        msg = await message.reply(
            f"<b><tg-emoji emoji-id='5465143921912846619'>💭</tg-emoji> Играем в Крестики-нолики</b>\n"
            f"<b>{text_symbol_1} - {name_link}</b>\n"
            f"<b>{text_symbol_2} ?</b>",
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        games_tictactoe[game_id]["chat_id"] = msg.chat.id
        games_tictactoe[game_id]["message_id"] = msg.message_id

        try:
            games_tictactoe.save()
        except Exception:
            pass

    except Exception as e:
        print(f"Ошибка в tic_tac_toe: {e}")


# =========================================================
# BOARD SIZE
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("set_board:"))
async def set_board_size(callback: types.CallbackQuery):
    try:
        _, board_size, game_id = callback.data.split(":")
        game_id = int(game_id)
        game = games_tictactoe.get(game_id)

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
        game["board"] = [" "] * (49 if board_size == "7x7" else 25 if board_size == "5x5" else 9)

        await callback.answer(f"❕ Формат игры изменён на {board_size}")

        keyboard = build_ttt_keyboard(game_id)
        button_games_tictactoe[game_id]["keyboard_124125"] = keyboard

        await callback.message.edit_reply_markup(reply_markup=keyboard)

    except Exception as e:
        print(f"Ошибка в set_board_size: {e}")

    try:
        games_tictactoe.save()
    except Exception:
        pass


@dp.callback_query(lambda c: c.data.startswith("tart_set_board:"))
async def set_board_start_size(callback: types.CallbackQuery):
    try:
        _, board_size, game_id = callback.data.split(":")
        game_id = int(game_id)
        game = games_tictactoe.get(game_id)

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
        game["board"] = [" "] * (49 if board_size == "7x7" else 25 if board_size == "5x5" else 9)

        await callback.answer(f"❕ Формат игры изменён на {board_size}")

        keyboard = build_ttt_keyboard(game_id)
        button_games_tictactoe[game_id]["keyboard_safda"] = keyboard

        await callback.message.edit_reply_markup(reply_markup=keyboard)

    except Exception as e:
        print(f"Ошибка в set_board_start_size: {e}")

    try:
        games_tictactoe.save()
    except Exception:
        pass


# =========================================================
# JOIN GAME
# =========================================================

_ttt_join_locks: Dict[int, asyncio.Lock] = {}
_ttt_inflight: Set[Tuple[int, int]] = set()
MAX_TTT_PLAYERS = 2


def _get_ttt_lock(game_id: int) -> asyncio.Lock:
    lock = _ttt_join_locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _ttt_join_locks[game_id] = lock
    return lock


def _dedupe_preserve_order(items: List[int]) -> List[int]:
    seen = set()
    out = []
    for x in items:
        x = int(x)
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


@dp.callback_query(lambda c: c.data and c.data.startswith("jointictactoe:"))
async def tictactoe_join_game_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    try:
        game_id = int(callback_query.data.split(":", 1)[1])
    except Exception:
        await callback_query.answer("⚠️ Неверные данные.", show_alert=True)
        return

    if game_id not in games_tictactoe:
        await callback_query.answer("🛠 Эта игра больше не существует.")
        return

    inflight_key = (game_id, user_id)
    if inflight_key in _ttt_inflight:
        await callback_query.answer("⏳ Обрабатываю ваше присоединение…")
        return
    _ttt_inflight.add(inflight_key)

    try:
        lock = _get_ttt_lock(game_id)
        async with lock:
            if game_id not in games_tictactoe:
                await callback_query.answer("🛠 Эта игра больше не существует.")
                return

            game = games_tictactoe[game_id]

            if await db.is_user_banned(user_id):
                await callback_query.answer("❗️ Вы заблокированы в боте")
                return

            if user_id == int(game.get("creator")):
                await callback_query.answer("❗️ Вы не можете присоединиться к своей игре.")
                return

            participants = _dedupe_preserve_order([int(x) for x in game.get("participants", [])])
            game["participants"] = participants

            if len(participants) >= MAX_TTT_PLAYERS:
                await callback_query.answer("💭 В игре нет мест")
                return

            if user_id in participants:
                await callback_query.answer("❗️ Вы уже участвуете в этой игре.")
                return

            bet = int(game.get("bet", 0) or 0)
            try:
                bal = await db.get_user_balance(user_id)
                enough = (bal is not None) and int(bal) >= bet
            except Exception:
                enough = False

            if not enough:
                await callback_query.answer("💭 У вас недостаточно средств для участия.")
                return

            parts_set = set(game["participants"])
            try:
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
                    for invitee_id in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, int(invitee_id), now=datetime.now())
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

            if len(game["participants"]) >= MAX_TTT_PLAYERS:
                await callback_query.answer("💭 В игре нет мест")
                return

            game["participants"].append(user_id)
            game["participants"] = _dedupe_preserve_order(game["participants"])
            games_tictactoe.save()

            style_text_1, style_text_2 = _get_style_text_pair(game)

            participants_lines = []
            for idx, uid in enumerate(game["participants"]):
                first_name = await db.get_firstname_by_user_id(uid)
                username = await db.get_username_by_user_id(uid)
                name_link = await create_user_link(uid, first_name, username)
                style_char = style_text_1 if idx == 0 else style_text_2
                participants_lines.append(f"<b>{style_char} - {name_link}</b>")

            participants_text = "\n".join(participants_lines)

            total_pot = bet * len(game["participants"])
            win_text = f"<tg-emoji emoji-id='5292146637844543370'>💲</tg-emoji> <b>Выигрыш {max(total_pot - bet, 0)} кут</b>\n" if bet > 0 else ""

            keyboard = build_ttt_keyboard(game_id)
            button_games_tictactoe[game_id]["keyboard_sdgjgkgf"] = keyboard

            try:
                await callback_query.message.edit_text(
                    "<b><tg-emoji emoji-id='5465143921912846619'>💭</tg-emoji> Играем в Крестики-нолики</b>\n"
                    f"{win_text}"
                    f"{participants_text}",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            except (TelegramAPIError, TelegramBadRequest) as e:
                if "message is not modified" not in str(e).lower():
                    print(f"[TTT] edit_message_text error: {e}")

            await callback_query.answer("❕ Вы присоединились к игре!")

    except Exception as e:
        print(f"[TTT] join error: {e}")
        try:
            await callback_query.answer("💭 Ошибка присоединения к лобби.", show_alert=True)
        except Exception:
            pass
    finally:
        _ttt_inflight.discard((game_id, user_id))
        try:
            games_tictactoe.save()
        except Exception:
            pass


# =========================================================
# START MATCH
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("starttictactoe:"))
async def start_game_callback(callback_query: types.CallbackQuery):
    try:
        game_id = int(callback_query.data.split(":")[1])
        user_id = callback_query.from_user.id

        if game_id not in games_tictactoe:
            await callback_query.answer("🛠 Эта игра больше не существует.")
            return

        game = games_tictactoe[game_id]
        chat_id = game["chat_id"]
        message_id = game["message_id"]

        if user_id != game["creator"]:
            await callback_query.answer("❗️ Только создатель игры может начать её.")
            return

        if len(game["participants"]) < 2:
            await callback_query.answer("❗️ Недостаточно участников для начала игры.")
            return

        bet = int(game["bet"])
        current_balance = await db.get_user_balance(user_id)
        if current_balance is None or current_balance < bet:
            await callback_query.answer("💭 У вас недостаточно средств для игры.")
            return

        await callback_query.answer()

        tictac_funds_users = []

        for participant_id in game["participants"]:
            if isinstance(participant_id, tuple):
                participant_id = participant_id[0]

            if not isinstance(participant_id, int):
                try:
                    participant_id = int(participant_id)
                except ValueError:
                    print(f"Неверный идентификатор участника: {participant_id}")
                    continue

            current_balance = await db.get_user_balance(participant_id)

            if current_balance is None or current_balance < bet:
                first_name = await db.get_firstname_by_user_id(participant_id)
                username = await db.get_username_by_user_id(participant_id)
                name_link = await create_user_link(participant_id, first_name, username)
                tictac_funds_users.append(f"<b>- {name_link}</b>")

        if tictac_funds_users:
            insufficient_funds_message = (
                "⛑ <b>Игра остановлена!\nУ кого-то из участников недостаточно средств для игры.</b>\n"
                + "\n".join(tictac_funds_users)
            )
            await bot1.edit_message_text(
                insufficient_funds_message,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            del games_tictactoe[game_id]
            return

        board_size = {"7x7": 7, "5x5": 5, "3x3": 3}.get(game["board_size"], 3)
        board = [" " for _ in range(board_size * board_size)]

        game.update({"board": board, "turn": game["creator"]})
        game["opponent"] = game["participants"][1]

        plain_1, plain_2 = _get_style_plain_pair(game)
        text_1, _ = _get_style_text_pair(game)

        game["symbols"] = {
            game["creator"]: plain_1,
            game["opponent"]: plain_2,
        }

        choices_keyboard = _build_board_keyboard(game_id, with_surrender=True, freeze_board=False)
        button_games_tictactoe[game_id]["keyboard_asgasgbzx"] = choices_keyboard

        creator_firstname = await db.get_firstname_by_user_id(game["creator"])
        username = await db.get_username_by_user_id(game["creator"])
        name_link = await create_user_link(game["creator"], creator_firstname, username)

        await bot1.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"{text_1} <b>Первый ход : {name_link}</b>",
            reply_markup=choices_keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        print(f"Ошибка в start_game_callback: {e}")

    try:
        games_tictactoe.save()
    except Exception:
        pass


# =========================================================
# MOVE
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("movetictactoe:"))
async def make_move_callback(callback_query: types.CallbackQuery):
    data_parts = callback_query.data.split(":")
    game_id = int(data_parts[1])
    move_index = int(data_parts[2])
    user_id = callback_query.from_user.id

    if game_id not in games_tictactoe:
        await callback_query.answer("🛠 Эта игра больше не существует.")
        return

    game = games_tictactoe[game_id]
    chat_id = game["chat_id"]
    message_id = game["message_id"]

    current_time = time.time()
    if current_time - tictac_cooldowns.get(user_id, 0) < REST:
        remaining_time = REST - (current_time - tictac_cooldowns[user_id])
        await callback_query.answer(f"⌚️ Подождите {int(remaining_time)} секунд", show_alert=True)
        return

    tictac_cooldowns[user_id] = current_time

    bet_amount = int(game["bet"])
    tictac_funds_users = []

    for participant_id in game["participants"]:
        if isinstance(participant_id, tuple):
            participant_id = participant_id[0]

        if not isinstance(participant_id, int):
            try:
                participant_id = int(participant_id)
            except ValueError:
                print(f"Неверный идентификатор участника: {participant_id}")
                continue

        current_balance = await db.get_user_balance(participant_id)

        if current_balance is None or current_balance < bet_amount:
            first_name = await db.get_firstname_by_user_id(participant_id)
            username = await db.get_username_by_user_id(participant_id)
            name_link = await create_user_link(participant_id, first_name, username)
            tictac_funds_users.append(f"<b>- {name_link}</b>")

    if tictac_funds_users:
        insufficient_funds_message = (
            "⛑ <b>Игра остановлена!\nУ кого-то из участников недостаточно средств для игры.</b>\n"
            + "\n".join(tictac_funds_users)
        )
        await bot1.edit_message_text(
            insufficient_funds_message,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        del games_tictactoe[game_id]
        return

    if user_id not in game["participants"]:
        await callback_query.answer("❗️ Вы не участвуете в этой игре.")
        return

    if user_id != game["turn"]:
        await callback_query.answer("❗️ Сейчас не ваш ход.")
        return

    board = game["board"]
    if board[move_index] != " ":
        await callback_query.answer("❗️ Эта ячейка уже занята.")
        return

    await callback_query.answer()

    symbol = game["symbols"][user_id]
    board[move_index] = symbol

    board_size = {"7x7": 7, "5x5": 5, "3x3": 3}.get(game["board_size"], 3)

    if check_winner(board, symbol, board_size):
        winner_id = user_id
        loser_id = game["opponent"] if user_id == game["creator"] else game["creator"]

        bet = int(game["bet"])
        await check_bet_and_set_item(winner_id, bet)

        loser_balance = await db.get_user_balance(loser_id)
        winner_balance = await db.get_user_balance(winner_id)

        await db.update_user_balance(loser_id, loser_balance - bet)
        await db.update_user_balance(winner_id, winner_balance + bet)
        await db.touch_balance_last_active(winner_id, set_active_status=True)
        await db.touch_balance_last_active(loser_id, set_active_status=True)

        await db.cutehistory_minus(loser_id, bet, "- Крестики нолики")
        await db.cutehistory_plus(winner_id, bet, "+ Крестики нолики")

        await db.update_user_wins(winner_id, 1, bot1, ref_coin)
        await db.update_user_winamount(winner_id, bet)#
        await db.update_user_loose(loser_id, 1, bot1, ref_coin)#
        await db.update_game_last_activity(winner_id)
        await db.update_game_last_activity(loser_id)

        user_message_count_formatted = "{:,.0f}".format(bet).replace(",", ".")
        win_text = (
            f"\n<tg-emoji emoji-id='5292146637844543370'>💰</tg-emoji> <b>Выигрыш {user_message_count_formatted} кут</b>"
            if bet > 0 else ""
        )

        first_name = await db.get_firstname_by_user_id(winner_id)
        username = await db.get_username_by_user_id(winner_id)
        name_link = await create_user_link(winner_id, first_name, username)

        choices_keyboard = _build_board_keyboard(game_id, with_surrender=False, freeze_board=True)
        button_games_tictactoe[game_id]["keyboard_ewqr"] = choices_keyboard

        chat_name = "1"

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
                datetime.fromtimestamp(data_open).strftime("%Y-%m-%d %H:%M:%S")
            )
        else:
            try:
                data_open_timestamp = data_open.timestamp()
            except Exception as e:
                print(f"Ошибка при преобразовании data_open в метку времени: {e}")
                return

            try:
                if current_time_ts < data_open_timestamp:
                    last_open_time = get_current_time_formatted()
                    data_open = current_time_ts + timehistorygames
                    await db.update_historygames(
                        winner_id,
                        last_open_time,
                        datetime.fromtimestamp(data_open).strftime("%Y-%m-%d %H:%M:%S")
                    )
                else:
                    last_open_time = get_current_time_formatted()
                    data_open = current_time_ts + timehistorygames
                    await db.update_historygames(
                        winner_id,
                        last_open_time,
                        datetime.fromtimestamp(data_open).strftime("%Y-%m-%d %H:%M:%S")
                    )
            except Exception as e:
                print(f"Ошибка при проверке или обновлении бонуса: {e}")
                return

        await bot1.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=(f"<tg-emoji emoji-id='5262688775716234060'>🏆</tg-emoji> <b>Победа для {name_link}!</b>{win_text}"),
            reply_markup=choices_keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        del games_tictactoe[game_id]
        return

    if " " not in board:
        choices_keyboard = _build_board_keyboard(game_id, with_surrender=False, freeze_board=True)
        button_games_tictactoe[game_id]["keyboard_join"] = choices_keyboard

        await bot1.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="<tg-emoji emoji-id='5357080225463149588'>🤝</tg-emoji> <b>Ничья!</b>",
            reply_markup=choices_keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        del games_tictactoe[game_id]
        return

    game["turn"] = game["opponent"] if user_id == game["creator"] else game["creator"]

    choices_keyboard = _build_board_keyboard(game_id, with_surrender=True, freeze_board=False)
    next_turn_user = game["turn"]

    first_name = await db.get_firstname_by_user_id(next_turn_user)
    username = await db.get_username_by_user_id(next_turn_user)
    name_link = await create_user_link(next_turn_user, first_name, username)

    next_turn_symbol_plain = game["symbols"][next_turn_user]
    plain_1, plain_2 = _get_style_plain_pair(game)
    text_1, text_2 = _get_style_text_pair(game)
    next_turn_symbol = text_1 if next_turn_symbol_plain == plain_1 else text_2

    button_games_tictactoe[game_id]["keyboard_bonbjb"] = choices_keyboard

    await bot1.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=f"{next_turn_symbol} <b>Ход {name_link}</b>",
        reply_markup=choices_keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    try:
        games_tictactoe.save()
    except Exception:
        pass


def format_board(board):
    size = int(len(board) ** 0.5)
    formatted_rows = []
    for i in range(size):
        row = " | ".join(board[i * size:(i + 1) * size])
        formatted_rows.append(row)
    return "\n".join(formatted_rows)


# =========================================================
# SURRENDER
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("surrendertictactoe:"))
async def surrender_callback(callback_query: types.CallbackQuery):
    try:
        data_parts = callback_query.data.split(":")
        game_id = int(data_parts[1])
        user_id = callback_query.from_user.id

        if game_id not in games_tictactoe:
            try:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=False)
            except Exception:
                pass
            return

        game = games_tictactoe[game_id]

        if game.get("surrender_processed"):
            try:
                await callback_query.answer("⏳ Ход уже обработан.", show_alert=False)
            except Exception:
                pass
            return

        game["surrender_processed"] = True

        chat_id = game["chat_id"]
        message_id = game["message_id"]

        if user_id not in game.get("participants", []):
            try:
                await callback_query.answer("❗️ Вы не участвуете в этой игре.")
            except Exception:
                pass
            game["surrender_processed"] = False
            return

        opponent_id = game["opponent"] if user_id == game["creator"] else game["creator"]

        surrenderer_firstname = await db.get_firstname_by_user_id(user_id)
        winner_firstname = await db.get_firstname_by_user_id(opponent_id)

        bet = int(game.get("bet", 0))

        surrenderer_balance = await db.get_user_balance(user_id)
        if surrenderer_balance is None:
            try:
                await callback_query.answer("🛠 Ошибка при получении вашего баланса.")
            except Exception:
                pass
            game["surrender_processed"] = False
            return

        if bet > 0 and surrenderer_balance < bet:
            try:
                await callback_query.answer("❗️ У вас недостаточно средств для сдачи.")
            except Exception:
                pass
            game["surrender_processed"] = False
            return

        winner_balance_before = await db.get_user_balance(opponent_id)
        if winner_balance_before is None:
            winner_balance_before = 0

        try:
            await callback_query.answer()
        except Exception:
            pass

        if bet > 0:
            await db.update_user_balance(user_id, surrenderer_balance - bet)
            await db.update_user_balance(opponent_id, winner_balance_before + bet)
            await db.cutehistory_plus(opponent_id, bet, "+ Крестики нолики сдача")
            await db.cutehistory_minus(user_id, bet, "- Крестики нолики сдача")

        if bet > 0:
            await db.update_user_winamount(opponent_id, bet)#
            await db.update_game_last_activity(opponent_id)

        await db.update_user_wins(opponent_id, 1, bot1, ref_coin)
        await db.update_user_loose(user_id, 1, bot1, ref_coin)#
        await db.update_game_last_activity(user_id)
        await db.update_game_last_activity(opponent_id)

        from main import check_bet_and_set_item
        if bet > 0:
            await check_bet_and_set_item(opponent_id, bet)

        text_options = [
            "опустил(-а) руки",
            "прекратил(-а) сопротивление",
            "сдался(-ась) без боя",
            "капитулировал(-а)",
        ]
        random_text = random.choice(text_options)

        surrenderer_username = await db.get_username_by_user_id(user_id)
        opponent_username = await db.get_username_by_user_id(opponent_id)
        name_link_winner = await create_user_link(opponent_id, winner_firstname, opponent_username)
        name_link_loser = await create_user_link(user_id, surrenderer_firstname, surrenderer_username)

        choices_keyboard = _build_board_keyboard(game_id, with_surrender=False, freeze_board=True)
        button_games_tictactoe[game_id]["keybotyiubnard_join"] = choices_keyboard

        if bet > 0:
            user_message_count_formatted = "{:,.0f}".format(bet).replace(",", ".")
            win_text = f"\n<tg-emoji emoji-id='5292146637844543370'>💰</tg-emoji> <b>Выигрыш {user_message_count_formatted} кут</b>"
        else:
            win_text = ""

        await bot1.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=(
                f"<tg-emoji emoji-id='5411285332668720752'>🏳️</tg-emoji> "
                f"<b>{name_link_loser} {random_text}</b>\n"
                f"<tg-emoji emoji-id='5262688775716234060'>🏆</tg-emoji> "
                f"<b>{name_link_winner}</b>{win_text}"
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=choices_keyboard
        )

        del games_tictactoe[game_id]

    except Exception as e:
        print(f"[ERR] surrender_callback: {e}")
    finally:
        try:
            games_tictactoe.save()
        except Exception as se:
            print(f"[WARN] games_tictactoe.save() failed: {se}")


# =========================================================
# NOOP
# =========================================================

@dp.callback_query(lambda c: c.data == "noop_ttt")
async def noop_ttt_callback(callback_query: types.CallbackQuery):
    try:
        await callback_query.answer()
    except Exception:
        pass