# -*- coding: utf-8 -*-
import re
import time
import random
import asyncio
from typing import Dict, Set, Tuple, List, Optional
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest

# Импорты из вашего проекта (оставьте как есть)
from bot.config.config import *
from bot.design.buttons import *
from bot.db_create.db import *
from bot.funcs.func import *
from bot.games.group_only import reject_if_private_game
from main import button_gamessha, gamessha, db, bot1, dp, get_current_time_formatted, timehistorygames, \
    pending_context, send_invoice_to_user, _format_hms, _pair_seconds_left

# ---------------------- ЗАЩИТНЫЕ СТРУКТУРЫ (как в TTT) ----------------------
_join_locks_sha: Dict[int, asyncio.Lock] = {}
_inflight_shajoin: Set[Tuple[int, int]] = set()
shah_cooldowns = {}
REST = 2.2


def _get_sha_lock(game_id: int) -> asyncio.Lock:
    if game_id not in _join_locks_sha:
        _join_locks_sha[game_id] = asyncio.Lock()
    return _join_locks_sha[game_id]


def _dedupe_preserve_order(items: List[int]) -> List[int]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ---------------------- СТИЛИ ШАШЕК ----------------------
shahstyles = [(
    "<tg-emoji emoji-id='5255850874248399164'>⚪️</tg-emoji>", "<tg-emoji emoji-id='5424616516018537963'>⚫️</tg-emoji>"), (
    "<tg-emoji emoji-id='5296677514809199813'>⚪️</tg-emoji>", "<tg-emoji emoji-id='5202199611665571551'>⚫️</tg-emoji>"), (
    "<tg-emoji emoji-id='5244710862953941180'>⚪️</tg-emoji>", "<tg-emoji emoji-id='5422812530969967956'>⚫️</tg-emoji>"), (
    "<tg-emoji emoji-id='5289761157173775507'>⚪️</tg-emoji>", "<tg-emoji emoji-id='5226661632259691727'>⚫️</tg-emoji>"), (
    "<tg-emoji emoji-id='5438440765908874600'>⚪️</tg-emoji>", "<tg-emoji emoji-id='5438529285184847871'>⚫️</tg-emoji>"), (
    "<tg-emoji emoji-id='5246891546699136867'>⚪️</tg-emoji>", "<tg-emoji emoji-id='5334675412599480338'>⚫️</tg-emoji>"), (
    "<tg-emoji emoji-id='5165823665324951299'>⚪️</tg-emoji>", "<tg-emoji emoji-id='5165686131882198121'>⚫️</tg-emoji>"), (
    "<tg-emoji emoji-id='5165979207565575234'>⚪️</tg-emoji>", "<tg-emoji emoji-id='5165986320031417432'>⚫️</tg-emoji>")]


def choose_style():
    return random.choice(shahstyles)


def extract_default_emoji(value: str) -> str:
    if not isinstance(value, str):
        return ""
    m = re.search(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", value)
    return m.group(1) if m else value


def extract_emoji_id(html_tag: str) -> Optional[str]:
    if not isinstance(html_tag, str):
        return None
    m = re.search(r"emoji-id=['\"]([0-9]+)['\"]", html_tag)
    return m.group(1) if m else None


def get_style_emoji_text(game, turn):
    white_style, black_style = game["style"]
    if turn == "white":
        emoji = extract_default_emoji(white_style)
        return f"белые {emoji}"
    else:
        emoji = extract_default_emoji(black_style)
        return f"чёрные {emoji}"


# ---------------------- ДОСКА ----------------------
def initialize_board():
    return [["b", " ", "b", " ", "b", " ", "b", " "],
            [" ", "b", " ", "b", " ", "b", " ", "b"],
            ["b", " ", "b", " ", "b", " ", "b", " "],
            [" ", " ", " ", " ", " ", " ", " ", " "],
            [" ", " ", " ", " ", " ", " ", " ", " "],
            [" ", "w", " ", "w", " ", "w", " ", "w"],
            ["w", " ", "w", " ", "w", " ", "w", " "],
            [" ", "w", " ", "w", " ", "w", " ", "w"]]


async def check_balance(user_id, bet):
    bal = await db.get_user_balance(user_id)
    return bal is not None and bal >= bet


# ---------------------- АРКАДНЫЙ РЕЖИМ (исправлен) ----------------------
def _is_path_clear_arcade(board, r, c, dr, dc, steps, own_pieces):
    """Проверяет, что все клетки между (r,c) и (r+dr*steps, c+dc*steps) не содержат своих фигур."""
    for step in range(1, steps):
        rr = r + dr * step
        cc = c + dc * step
        if board[rr][cc] in own_pieces:
            return False
    return True


def get_valid_moves_arcade(row, col, turn, board, is_king=False):
    directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    opponent_piece = "b" if turn == "white" else "w"
    opponent_king = "🤴🏼" if turn == "white" else "👑"
    own_pieces = {"w", "👑"} if turn == "white" else {"b", "🤴🏼"}
    valid = []

    if not is_king:
        directions = directions[:2] if turn == "white" else directions[2:]

    for dr, dc in directions:
        # Простые ходы (без взятия)
        r, c = row + dr, col + dc
        if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == " ":
            valid.append((r, c))
        if is_king:
            r += dr
            c += dc
            while 0 <= r < 8 and 0 <= c < 8 and board[r][c] == " ":
                valid.append((r, c))
                r += dr
                c += dc

        # Взятие
        r, c = row + dr, col + dc
        step = 1
        while 0 <= r < 8 and 0 <= c < 8:
            cell = board[r][c]
            if cell in (opponent_piece, opponent_king):
                # Проверяем, что все клетки между началом и противником пусты (или не содержат своих)
                if _is_path_clear_arcade(board, row, col, dr, dc, step, own_pieces):
                    jump_r, jump_c = r + dr, c + dc
                    if 0 <= jump_r < 8 and 0 <= jump_c < 8 and board[jump_r][jump_c] == " ":
                        valid.append((jump_r, jump_c))
                break
            elif cell in own_pieces:
                break  # своя фигура на пути - дальше не идём
            # Если клетка пуста и не король, то для простой шашки дальше не идём
            if not is_king:
                break
            r += dr
            c += dc
            step += 1

    # Возможность взятия назад (для короля)
    if is_king:
        for dr, dc in directions:
            r = row - dr
            c = col - dc
            step = 1
            while 0 <= r < 8 and 0 <= c < 8:
                cell = board[r][c]
                if cell in (opponent_piece, opponent_king):
                    if _is_path_clear_arcade(board, row, col, -dr, -dc, step, own_pieces):
                        jump_r, jump_c = r - dr, c - dc
                        if 0 <= jump_r < 8 and 0 <= jump_c < 8 and board[jump_r][jump_c] == " ":
                            valid.append((jump_r, jump_c))
                    break
                elif cell in own_pieces:
                    break
                r -= dr
                c -= dc
                step += 1

    return valid


# ---------------------- РЕАЛИСТИЧНЫЙ РЕЖИМ (исправлен) ----------------------
def print_board_debug(board, title="Текущая доска"):
    print(f"\n--- {title} ---")
    print("   0 1 2 3 4 5 6 7")
    for i, row in enumerate(board):
        row_str = f"{i}  " + " ".join(cell if cell != " " else "·" for cell in row)
        print(row_str)
    print("------------------")


def _is_path_clear_realistic(board, r, c, dr, dc, steps, own_pieces):
    """Проверяет, что все клетки между (r,c) и (r+dr*steps, c+dc*steps) пусты."""
    for step in range(1, steps):
        rr = r + dr * step
        cc = c + dc * step
        if board[rr][cc] != " ":
            return False
    return True


def _find_captures_from(r, c, board, turn, is_king, path, sequences):
    directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    own = "w" if turn == "white" else "b"
    own_king = "👑" if turn == "white" else "🤴🏼"
    opponent = "b" if turn == "white" else "w"
    opponent_king = "🤴🏼" if turn == "white" else "👑"
    piece = board[r][c]
    current_is_king = is_king or piece in (own_king, opponent_king)

    found = False
    for dr, dc in directions:
        max_steps = 8 if current_is_king else 1
        for step in range(1, max_steps + 1):
            rr = r + dr * step
            cc = c + dc * step
            if not (0 <= rr < 8 and 0 <= cc < 8):
                break

            cell = board[rr][cc]
            if cell == " ":
                # Для дамки продолжаем поиск фигуры противника дальше
                if current_is_king and not found:
                    continue
                else:
                    break
            elif cell in (opponent, opponent_king):
                # Проверяем, что все клетки между r,c и rr,cc пусты
                if not _is_path_clear_realistic(board, r, c, dr, dc, step, {own, own_king}):
                    break
                # Клетка для прыжка
                jump_r = rr + dr
                jump_c = cc + dc
                if 0 <= jump_r < 8 and 0 <= jump_c < 8 and board[jump_r][jump_c] == " ":
                    # Выполняем ход на копии доски для поиска продолжений
                    new_board = [row[:] for row in board]
                    new_board[rr][cc] = " "
                    new_board[jump_r][jump_c] = new_board[r][c]
                    new_board[r][c] = " "
                    # Превращение в дамку
                    if new_board[jump_r][jump_c] == "w" and jump_r == 0:
                        new_board[jump_r][jump_c] = "👑"
                    elif new_board[jump_r][jump_c] == "b" and jump_r == 7:
                        new_board[jump_r][jump_c] = "🤴🏼"
                    new_path = path + [(rr, cc, jump_r, jump_c)]
                    _find_captures_from(jump_r, jump_c, new_board, turn, True, new_path, sequences)
                    found = True
                break  # после нахождения противника дальше по этому направлению не идём
            else:
                # Своя фигура на пути - прерываем
                break

    if not found and path:
        sequences.append(path)


def get_all_captures_realistic(board, turn):
    own = "w" if turn == "white" else "b"
    own_king = "👑" if turn == "white" else "🤴🏼"
    captures = {}
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece == own or piece == own_king:
                is_king = (piece == own_king)
                sequences = []
                _find_captures_from(r, c, board, turn, is_king, [], sequences)
                if sequences:
                    captures[(r, c)] = sequences
    return captures


def get_all_moves_realistic(board, turn):
    captures = get_all_captures_realistic(board, turn)
    if captures:
        moves = {}
        for (r, c), seqs in captures.items():
            first_steps = []
            for seq in seqs:
                if seq:
                    first_steps.append((seq[0][2], seq[0][3]))
            moves[(r, c)] = list(set(first_steps))
        return moves, True, captures
    else:
        moves = {}
        own = "w" if turn == "white" else "b"
        own_king = "👑" if turn == "white" else "🤴🏼"
        for r in range(8):
            for c in range(8):
                piece = board[r][c]
                if piece == own or piece == own_king:
                    is_king = (piece == own_king)
                    simple = _get_simple_moves_realistic(r, c, board, turn, is_king)
                    if simple:
                        moves[(r, c)] = simple
        return moves, False, {}


def _get_simple_moves_realistic(row, col, board, turn, is_king):
    directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    if not is_king:
        directions = directions[:2] if turn == "white" else directions[2:]
    moves = []
    for dr, dc in directions:
        r, c = row + dr, col + dc
        if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == " ":
            moves.append((r, c))
        if is_king:
            r += dr
            c += dc
            while 0 <= r < 8 and 0 <= c < 8 and board[r][c] == " ":
                moves.append((r, c))
                r += dr
                c += dc
    return moves


async def apply_move_realistic(game_id, from_pos, to_pos, turn, board):
    sr, sc = from_pos
    dr, dc = to_pos
    piece = board[sr][sc]
    capture_occurred = False

    # Определяем, был ли захват (расстояние > 1 по одной из диагоналей)
    if abs(dr - sr) >= 2:
        capture_occurred = True
        step_r = 1 if dr > sr else -1
        step_c = 1 if dc > sc else -1
        # Находим фигуру противника, которую нужно удалить
        r, c = sr + step_r, sc + step_c
        while (r, c) != (dr, dc):
            cell = board[r][c]
            # Удаляем только фигуры противника (первую встречную)
            opponent = "b" if turn == "white" else "w"
            opponent_king = "🤴🏼" if turn == "white" else "👑"
            if cell in (opponent, opponent_king):
                board[r][c] = " "
                break
            r += step_r
            c += step_c

    # Перемещаем фигуру
    board[dr][dc] = piece
    board[sr][sc] = " "

    # Превращение в дамку
    if piece == "w" and dr == 0:
        board[dr][dc] = "👑"
    elif piece == "b" and dr == 7:
        board[dr][dc] = "🤴🏼"

    # Проверяем, можно ли продолжить взятие той же шашкой
    continue_capture = False
    if capture_occurred:
        # После хода смотрим, есть ли у этой же шашки обязательные взятия
        new_piece = board[dr][dc]
        is_king = new_piece in ("👑", "🤴🏼")
        captures = get_all_captures_realistic(board, turn)
        if (dr, dc) in captures:
            continue_capture = True

    return board, capture_occurred, continue_capture


# ---------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ БЕЗОПАСНОСТИ ----------------------
async def _notify_flood(callback_query: Optional[CallbackQuery], user_id: int, wait_seconds: int, attempt: int,
                        retries: int):
    text = f"⏳ Бот перегружен. Повторная попытка через {wait_seconds} сек.\nОшибка будет исправлена автоматически (попытка {attempt}/{retries})."
    if callback_query:
        try:
            await callback_query.answer(text, show_alert=True)
            return
        except Exception:
            pass
    try:
        await bot1.send_message(user_id, text)
    except Exception:
        pass


async def safe_edit_message_text(chat_id, message_id, text, reply_markup, parse_mode, callback_query=None,
                                 retries=3):
    user_id = callback_query.from_user.id if callback_query else None
    for attempt in range(1, retries + 1):
        try:
            await bot1.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup,
                parse_mode=parse_mode, disable_web_page_preview=True)
            return True
        except TelegramBadRequest as e:
            error_str = str(e).lower()
            if "message is not modified" in error_str:
                if callback_query:
                    try:
                        await callback_query.answer("⏳ Не нужно нажимать дважды, играйте не спеша.", show_alert=True)
                    except Exception:
                        pass
                return True
            match = re.search(r"retry after (\d+)", error_str)
            wait_seconds = int(match.group(1)) if match else None
            if wait_seconds is not None:
                if user_id:
                    await _notify_flood(callback_query, user_id, wait_seconds, attempt, retries)
                await asyncio.sleep(wait_seconds + 0.5)
                continue
            else:
                print(f"Неисправимая ошибка при редактировании: {e}")
                if callback_query:
                    try:
                        await callback_query.answer(
                            "❌ Произошла техническая ошибка. Пожалуйста, начните игру заново.", show_alert=True)
                    except Exception:
                        pass
                return False
        except Exception as e:
            print(f"Критическая ошибка при редактировании: {e}")
            if callback_query:
                try:
                    await callback_query.answer("⚠️ Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
                except Exception:
                    pass
            return False
    if callback_query:
        try:
            await callback_query.answer(
                f"❌ Не удалось обновить доску после {retries} попыток.\nПожалуйста, создайте игру заново.",
                show_alert=True)
        except Exception:
            pass
    return False


async def safe_callback_answer(callback_query: CallbackQuery, text: str, show_alert: bool = False, retries: int = 2):
    user_id = callback_query.from_user.id
    for attempt in range(1, retries + 1):
        try:
            await callback_query.answer(text, show_alert=show_alert)
            return True
        except (TelegramAPIError, TelegramBadRequest) as e:
            error_str = str(e).lower()
            match = re.search(r"retry after (\d+)", error_str)
            wait_seconds = int(match.group(1)) if match else None
            if wait_seconds is not None:
                flood_text = f"⏳ Бот перегружен. Повторная попытка через {wait_seconds} сек.\nОшибка будет исправлена автоматически (попытка {attempt}/{retries})."
                try:
                    await callback_query.answer(flood_text, show_alert=True)
                except Exception:
                    try:
                        await bot1.send_message(user_id, flood_text)
                    except Exception:
                        pass
                await asyncio.sleep(wait_seconds + 0.5)
                continue
            else:
                print(f"Неисправимая ошибка в callback.answer: {e}")
                return False
        except Exception as e:
            print(f"Критическая ошибка в callback.answer: {e}")
            return False
    return False


# ---------------------- КНОПКИ РЕЖИМА ----------------------
def get_mode_buttons(game_id: int, game: dict) -> List[List[InlineKeyboardButton]]:
    current_mode = game.get("mode", "realistic")
    realistic_text = "Реализм"
    if current_mode == "realistic":
        realistic_text = f"• {realistic_text}"
    arcade_text = "Аркада"
    if current_mode == "arcade":
        arcade_text = f"• {arcade_text}"
    return [[InlineKeyboardButton(text=realistic_text, callback_data=f"shamode:{game_id}:realistic"),
             InlineKeyboardButton(text=arcade_text, callback_data=f"shamode:{game_id}:arcade")]]


# ---------------------- ОСНОВНЫЕ ОБРАБОТЧИКИ (без изменений, но оставлены для целостности) ----------------------
@dp.message()
async def sha(message: Message):
    if not message.text:
        return
    text = message.text.strip()
    parts = text.split()
    if not parts or parts[0].lower() != "шашки":
        return
    if len(parts) > 2:
        return

    if await reject_if_private_game(message):
        return

    bet = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0
    creator_id = message.from_user.id

    if bet > 0 and not await check_balance(creator_id, bet):
        try:
            bot_username = await get_bot_username_by_token(TOKEN)
        except Exception:
            bot_username = "CuteGamingBot"
        multiplier = donate_bet
        result = bet * multiplier
        bet_amount_str = str(int(result)) if isinstance(result, float) and result.is_integer() else str(result)
        bet_amount_win_formatted = "{:,.0f}".format(bet).replace(",", ".")
        pending_context[creator_id] = {"stars_amount": bet_amount_str, "sent": False}
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(
                text=f"💫 Купить {bet_amount_win_formatted} кут 💰",
                url=f"https://t.me/{bot_username}?start=insert_{bet_amount_str}_+")],
                [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")]])
        await message.reply(
            "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
            reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        await asyncio.sleep(timeoutdonate)
        if creator_id in pending_context and not pending_context[creator_id]["sent"]:
            invoice_message = await send_invoice_to_user(message, bet_amount_str)
            pending_context[creator_id]["manual_message_id"] = invoice_message.message_id
        return

    game_id = message.message_id
    game_style = choose_style()
    board = initialize_board()

    gamessha[game_id] = {"creator": creator_id, "bet": bet, "participants": [creator_id], "board": board,
                         "turn": "white", "selected_piece": None, "message_id": None, "style": game_style, "chat_id": None,
                         "mode": "realistic", "mode_locked": False, }

    first_name = await db.get_firstname_by_user_id(creator_id)
    username = await db.get_username_by_user_id(creator_id)
    name_link = await create_user_link(creator_id, first_name, username)
    white_style, black_style = game_style

    mode_buttons = get_mode_buttons(game_id, gamessha[game_id])
    join_button = [[InlineKeyboardButton(text="Присоединиться", callback_data=f"shajoin:{game_id}")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=mode_buttons + join_button)

    msg = await message.reply(
        f"<tg-emoji emoji-id='5424687267014801006'>♟</tg-emoji> <b>Играем в Шашки</b>\n"
        f"<b>- {white_style} {name_link}</b>", reply_markup=keyboard, parse_mode="HTML",
        disable_web_page_preview=True)
    gamessha[game_id]["chat_id"] = msg.chat.id
    gamessha[game_id]["message_id"] = msg.message_id
    gamessha.save()
    print(f"Игра {game_id} создана, режим реализм")


@dp.callback_query(lambda c: c.data.startswith('shamode:'))
async def select_mode_callback(callback: CallbackQuery):
    _, game_id_str, mode = callback.data.split(":")
    game_id = int(game_id_str)
    user_id = callback.from_user.id
    if game_id not in gamessha:
        await safe_callback_answer(callback, "🛠 Игра уже не существует.", show_alert=True)
        return
    game = gamessha[game_id]
    if user_id != game["creator"]:
        await safe_callback_answer(callback, "❕ Только создатель может менять режим.", show_alert=True)
        return
    if game.get("mode_locked", False):
        await safe_callback_answer(callback, "❕ Режим уже заблокирован (игра начата).", show_alert=True)
        return
    if mode not in ("realistic", "arcade"):
        return
    game["mode"] = mode
    gamessha.save()

    first_name = await db.get_firstname_by_user_id(game["creator"])
    username = await db.get_username_by_user_id(game["creator"])
    name_link = await create_user_link(game["creator"], first_name, username)
    white_style, black_style = game["style"]
    participants = game["participants"]
    participants_text = ""
    for idx, uid in enumerate(participants):
        fn = await db.get_firstname_by_user_id(uid)
        un = await db.get_username_by_user_id(uid)
        style_emoji = white_style if idx == 0 else black_style
        link = await create_user_link(uid, fn, un)
        participants_text += f"\n<b>- {style_emoji} {link}</b>"
    total_pot = game['bet'] * len(participants)
    win_amount = max(total_pot - game['bet'], 0)
    win_text = f"\n<tg-emoji emoji-id='5425117176061261659'>💰</tg-emoji> <b>Выигрыш {win_amount} кут</b>" if win_amount > 0 else ""
    mode_name = "Реализм" if mode == "realistic" else "Аркаду"

    mode_buttons = get_mode_buttons(game_id, game)
    if len(participants) >= 2:
        additional_buttons = [[InlineKeyboardButton(text="Начать игру", callback_data=f"shastart:{game_id}")]]
    else:
        additional_buttons = [[InlineKeyboardButton(text="Присоединиться", callback_data=f"shajoin:{game_id}")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=mode_buttons + additional_buttons)

    await safe_edit_message_text(
        chat_id=game["chat_id"], message_id=game["message_id"],
        text=f"<tg-emoji emoji-id='5424687267014801006'>♟</tg-emoji> <b>Играем в Шашки</b>{win_text}{participants_text}",
        reply_markup=keyboard, parse_mode="HTML", callback_query=callback)
    await safe_callback_answer(callback, f"Режим изменён на {mode_name}.", show_alert=True)
    print(f"Игра {game_id}: режим изменён на {mode_name}")


@dp.callback_query(lambda c: c.data.startswith('shajoin:'))
async def scah_join_game_callback(callback_query: CallbackQuery):
    try:
        game_id = int(callback_query.data.split(':')[1])
    except Exception:
        await safe_callback_answer(callback_query, "⚠️ Неверные данные.", show_alert=True)
        return

    user_id = callback_query.from_user.id

    if game_id not in gamessha:
        await safe_callback_answer(callback_query, "🛠 Эта игра больше не существует.", show_alert=True)
        return

    inflight_key = (game_id, user_id)
    if inflight_key in _inflight_shajoin:
        await safe_callback_answer(callback_query, "⏳ Обрабатываю ваше присоединение…", show_alert=True)
        return
    _inflight_shajoin.add(inflight_key)

    try:
        lock = _get_sha_lock(game_id)
        async with lock:
            if game_id not in gamessha:
                await safe_callback_answer(callback_query, "🛠 Эта игра больше не существует.", show_alert=True)
                return

            game = gamessha[game_id]

            if await db.is_user_banned(user_id):
                await safe_callback_answer(callback_query, "❗️ Вы заблокированы в боте", show_alert=True)
                return

            if user_id == int(game.get("creator")):
                await safe_callback_answer(callback_query, "❗️ Вы не можете присоединиться к своей игре.", show_alert=True)
                return

            participants = _dedupe_preserve_order([int(x) for x in game.get("participants", [])])
            game["participants"] = participants

            if len(participants) >= 2:
                await safe_callback_answer(callback_query, "💭 В игре нет мест", show_alert=True)
                return

            if user_id in participants:
                await safe_callback_answer(callback_query, "❗️ Вы уже участвуете в этой игре.", show_alert=True)
                return

            bet = int(game.get("bet", 0) or 0)
            bal = await db.get_user_balance(user_id)
            if bal is None or bal < bet:
                await safe_callback_answer(callback_query, "💭 У вас недостаточно средств для участия.", show_alert=True)
                return

            # АНТИФЕРМА (точная копия из TTT)
            parts_set = set(participants)
            try:
                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    inviter_id = None
                if inviter_id and int(inviter_id) in parts_set:
                    secs = await _pair_seconds_left(db, user_id, int(inviter_id), now=datetime.now())
                    if secs > 0:
                        await safe_callback_answer(
                            callback_query,
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь который пригласил вас в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения : {_format_hms(secs)}\n#AntiFarmSystem", show_alert=True)
                        return

                invitees_here = await db.get_invitees_in(inviter_id=user_id, candidates=parts_set)
                if invitees_here:
                    min_secs = None
                    for invitee_id in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, int(invitee_id), now=datetime.now())
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)
                    if min_secs is not None:
                        await safe_callback_answer(
                            callback_query,
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь которого вы пригласили в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения : {_format_hms(min_secs)}\n#AntiFarmSystem", show_alert=True)
                        return
            except Exception as e:
                print(f"[ANTIFARM ERROR] {e}")

            game["participants"].append(user_id)
            game["participants"] = _dedupe_preserve_order(game["participants"])
            gamessha.save()

            white_style, black_style = game["style"]
            participants_text = ""
            for idx, uid in enumerate(game['participants']):
                fn = await db.get_firstname_by_user_id(uid)
                un = await db.get_username_by_user_id(uid)
                style_emoji = white_style if idx == 0 else black_style
                link = await create_user_link(uid, fn, un)
                participants_text += f"\n<b>- {style_emoji} {link}</b>"
            total_pot = game['bet'] * len(game['participants'])
            win_amount = max(total_pot - game['bet'], 0)
            win_text = f"\n<tg-emoji emoji-id='5425117176061261659'>💰</tg-emoji> <b>Выигрыш {win_amount} кут</b>" if win_amount > 0 else ""

            mode_buttons = get_mode_buttons(game_id, game)
            if len(game['participants']) >= 2:
                additional_buttons = [
                    [InlineKeyboardButton(text="Начать игру", callback_data=f"shastart:{game_id}")]]
            else:
                additional_buttons = [
                    [InlineKeyboardButton(text="Присоединиться", callback_data=f"shajoin:{game_id}")]]
            keyboard = InlineKeyboardMarkup(inline_keyboard=mode_buttons + additional_buttons)

            await safe_edit_message_text(
                chat_id=game["chat_id"], message_id=game["message_id"],
                text=f"<tg-emoji emoji-id='5424687267014801006'>♟</tg-emoji> <b>Играем в Шашки</b>{win_text}{participants_text}",
                reply_markup=keyboard, parse_mode="HTML", callback_query=callback_query)
            await safe_callback_answer(callback_query, "❕ Вы присоединились к игре!", show_alert=True)
            gamessha.save()
    except Exception as e:
        print(f"[SHA JOIN ERROR] {e}")
        try:
            await safe_callback_answer(callback_query, "💭 Ошибка присоединения к лобби.", show_alert=True)
        except Exception:
            pass
    finally:
        _inflight_shajoin.discard(inflight_key)
        try:
            gamessha.save()
        except Exception:
            pass


@dp.callback_query(lambda c: c.data.startswith('shastart:'))
async def scah_start_game_callback(callback_query: types.CallbackQuery):
    game_id = int(callback_query.data.split(':')[1])
    user_id = callback_query.from_user.id
    if game_id not in gamessha:
        await safe_callback_answer(callback_query, "🛠 Игра не существует.", show_alert=True)
        return
    game = gamessha[game_id]
    if user_id != game['creator']:
        await safe_callback_answer(callback_query, "❗️ Только создатель может начать.", show_alert=True)
        return
    if len(game['participants']) != 2:
        await safe_callback_answer(callback_query, "❗️ Нужно два участника.", show_alert=True)
        return
    creator_id = game['creator']
    opponent_id = game['participants'][1]
    game['players'] = {"white": creator_id, "black": opponent_id}
    game['mode_locked'] = True

    required_bet = game['bet']
    insufficient = []
    for p in game['participants']:
        bal = await db.get_user_balance(p)
        if bal is None or bal < required_bet:
            insufficient.append(p)
    if insufficient:
        links = []
        for pid in insufficient:
            fn = await db.get_firstname_by_user_id(pid)
            un = await db.get_username_by_user_id(pid)
            links.append(await create_user_link(pid, fn, un))
        text = f"⛑ <b>Игра остановлена!\nНедостаточно средств у {', '.join(links)}</b>"
        await safe_edit_message_text(
            chat_id=game["chat_id"], message_id=game["message_id"], text=text, reply_markup=None,
            parse_mode="HTML", callback_query=callback_query)
        del gamessha[game_id]
        return
    await safe_callback_answer(callback_query, "❕ Игра началась! Белые ходят первыми.", show_alert=True)
    print(f"Игра {game_id} начата, режим {game['mode']}")
    print_board_debug(game["board"], "Начальная доска")
    await show_board(game["chat_id"], game["message_id"], game_id, callback_query)
    gamessha.save()


async def show_board(chat_id, message_id, game_id, callback_query=None):
    game = gamessha.get(game_id)
    if not game:
        return
    board = game["board"]
    selected = game.get("selected_piece")
    turn = game["turn"]
    players = game["players"]
    mode = game.get("mode", "realistic")
    white_style, black_style = game["style"]
    white_btn = extract_default_emoji(white_style)
    black_btn = extract_default_emoji(black_style)

    current_player_id = players.get(turn)
    if not current_player_id:
        return

    white_pieces = {"w", "👑"}
    black_pieces = {"b", "🤴🏼"}
    white_cnt = sum(1 for row in board for p in row if p in white_pieces)
    black_cnt = sum(1 for row in board for p in row if p in black_pieces)

    display_board = [row[:] for row in board]
    if selected is not None:
        sr, sc = selected
        if mode == "realistic":
            moves_dict, must_capture, captures_dict = get_all_moves_realistic(board, turn)
            if (sr, sc) in moves_dict:
                for (tr, tc) in moves_dict[(sr, sc)]:
                    if abs(tr - sr) >= 2:
                        display_board[tr][tc] = "☑️"
                    else:
                        display_board[tr][tc] = "✖️"
        else:
            piece = board[sr][sc]
            is_king = piece in ("👑", "🤴🏼")
            valid = get_valid_moves_arcade(sr, sc, turn, board, is_king)
            for (tr, tc) in valid:
                if abs(tr - sr) >= 2:
                    display_board[tr][tc] = "☑️"
                else:
                    display_board[tr][tc] = "✖️"

    inline_keyboard = []
    for r in range(8):
        row_buttons = []
        for c in range(8):
            btn_text = None
            icon_id = None
            if selected == (r, c):
                icon_id = "4956721670690702265"
                btn_text = " " if icon_id else "✅"
            else:
                piece = display_board[r][c]
                if piece == "w":
                    icon_id = extract_emoji_id(white_style)
                    if not icon_id:
                        btn_text = white_btn
                elif piece == "b":
                    icon_id = extract_emoji_id(black_style)
                    if not icon_id:
                        btn_text = black_btn
                elif piece == "✖️":
                    icon_id = "5226660202035554522"
                    btn_text = " " if icon_id else "✖️"
                elif piece == "☑️":
                    icon_id = "5454096630372379732"
                    btn_text = " " if icon_id else "☑️"
                elif piece in ("👑", "🤴🏼"):
                    btn_text = piece
                else:
                    btn_text = "  "
            if icon_id:
                btn = InlineKeyboardButton(
                    text=" ", icon_custom_emoji_id=icon_id, callback_data=f"select:{game_id}:{r}:{c}")
            else:
                btn = InlineKeyboardButton(
                    text=btn_text, callback_data=f"select:{game_id}:{r}:{c}")
            row_buttons.append(btn)
        inline_keyboard.append(row_buttons)

    draw_white = game.get("draw_white", False)
    draw_black = game.get("draw_black", False)
    nicha_text = "Закончить ничьей"
    if draw_white and draw_black:
        nicha_text += f" {white_btn} {black_btn}"
    elif draw_white:
        nicha_text += f" {white_btn}"
    elif draw_black:
        nicha_text += f" {black_btn}"
    inline_keyboard.append([InlineKeyboardButton(text=nicha_text, callback_data=f"micha:{game_id}")])
    inline_keyboard.append([InlineKeyboardButton(text="Сдаться", callback_data=f"shahsurrender:{game_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    current_turn_emoji = white_style if turn == "white" else black_style
    first_name = await db.get_firstname_by_user_id(current_player_id)
    username = await db.get_username_by_user_id(current_player_id)
    name_link = await create_user_link(current_player_id, first_name, username)

    text = f"{current_turn_emoji} <b>Сейчас ход {name_link}</b>\n{white_style} : {white_cnt} | {black_style} : {black_cnt}"
    await safe_edit_message_text(
        chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard, parse_mode="HTML",
        callback_query=callback_query)


@dp.callback_query(lambda c: c.data.startswith('select:'))
async def scah_select_piece_callback(callback_query: types.CallbackQuery):
    data = callback_query.data.split(":")
    game_id = int(data[1])
    row = int(data[2])
    col = int(data[3])
    user_id = callback_query.from_user.id

    current_time = time.time()
    last_usage = shah_cooldowns.get(user_id, 0)
    if current_time - last_usage < REST:
        await safe_callback_answer(
            callback_query, f"⌚️ Не спешите", show_alert=True)
        return
    shah_cooldowns[user_id] = current_time

    if game_id not in gamessha:
        await safe_callback_answer(callback_query, "🛠 Игра не существует.", show_alert=True)
        return
    game = gamessha[game_id]
    mode = game.get("mode", "realistic")
    required_bet = game['bet']

    insufficient = []
    for p in game['participants']:
        bal = await db.get_user_balance(p)
        if bal is None or bal < required_bet:
            insufficient.append(p)
    if insufficient:
        links = []
        for pid in insufficient:
            fn = await db.get_firstname_by_user_id(pid)
            un = await db.get_username_by_user_id(pid)
            links.append(await create_user_link(pid, fn, un))
        text = f"⛑ <b>Игра остановлена!\nНедостаточно средств у {', '.join(links)}</b>"
        await safe_edit_message_text(
            chat_id=game["chat_id"], message_id=game["message_id"], text=text, reply_markup=None,
            parse_mode="HTML", callback_query=callback_query)
        del gamessha[game_id]
        return

    board = game["board"]
    turn = game["turn"]
    players = game["players"]
    if user_id != players[turn]:
        await safe_callback_answer(callback_query, "❗️ Сейчас не ваш ход.", show_alert=True)
        return

    if game["selected_piece"] is None:
        piece = board[row][col]
        own = "w" if turn == "white" else "b"
        own_king = "👑" if turn == "white" else "🤴🏼"
        if piece not in (own, own_king):
            style_text = get_style_emoji_text(game, turn)
            await safe_callback_answer(callback_query, f"❕ Выберите свою шашку ({style_text})", show_alert=True)
            return
        is_king = piece in ("👑", "🤴🏼")
        if mode == "realistic":
            moves_dict, must_capture, captures_dict = get_all_moves_realistic(board, turn)
            valid = moves_dict.get((row, col), [])
            if must_capture and not valid:
                await safe_callback_answer(
                    callback_query, "⚠️ Обязательное взятие! Вы должны побить шашку противника.", show_alert=True)
                return
        else:
            valid = get_valid_moves_arcade(row, col, turn, board, is_king)
        if not valid:
            await safe_callback_answer(callback_query, "❕ У этой шашки нет ходов. Выберите другую.", show_alert=True)
            return
        game["selected_piece"] = (row, col)
        if mode == "realistic" and must_capture:
            await safe_callback_answer(callback_query, "⚡ Обязательное взятие!", show_alert=True)
        else:
            await safe_callback_answer(callback_query, "✅ Шашка выбрана.")
        await show_board(game["chat_id"], game["message_id"], game_id, callback_query)
    else:
        sr, sc = game["selected_piece"]
        piece = board[sr][sc]
        is_king = piece in ("👑", "🤴🏼")
        valid = False
        if mode == "realistic":
            moves_dict, must_capture, captures_dict = get_all_moves_realistic(board, turn)
            if (sr, sc) in moves_dict and (row, col) in moves_dict[(sr, sc)]:
                valid = True
        else:
            valid_moves = get_valid_moves_arcade(sr, sc, turn, board, is_king)
            if (row, col) in valid_moves:
                valid = True
        if not valid:
            piece2 = board[row][col]
            own = "w" if turn == "white" else "b"
            own_king = "👑" if turn == "white" else "🤴🏼"
            if piece2 in (own, own_king):
                game["selected_piece"] = (row, col)
                await safe_callback_answer(callback_query, "✅ Выбрана новая шашка. Теперь выберите клетку.")
                await show_board(game["chat_id"], game["message_id"], game_id, callback_query)
            else:
                await safe_callback_answer(callback_query, "❌ Недопустимый ход", show_alert=True)
            return

        if mode == "realistic":
            new_board, was_capture, continue_capture = await apply_move_realistic(
                game_id, (sr, sc), (row, col), turn, board)
            game["board"] = new_board
            game["selected_piece"] = None
            if continue_capture:
                game["selected_piece"] = (row, col)
                await safe_callback_answer(callback_query, "✅ Взятие! Можно продолжить бить той же шашкой")
                await show_board(game["chat_id"], game["message_id"], game_id, callback_query)
                gamessha.save()
                return
            else:
                game["turn"] = "black" if turn == "white" else "white"
                if was_capture:
                    await safe_callback_answer(callback_query, "✅ Взятие выполнено! Ход переходит к сопернику.")
                else:
                    await safe_callback_answer(callback_query, "✅ Ход выполнен. Теперь ход соперника.")
        else:
            # Аркадный режим - удаляем только одну побитую фигуру, если есть
            if abs(row - sr) >= 2 and abs(col - sc) >= 2:
                mid_r, mid_c = (row + sr) // 2, (col + sc) // 2
                board[mid_r][mid_c] = " "
            if turn == "white" and row == 0:
                board[row][col] = "👑"
            elif turn == "black" and row == 7:
                board[row][col] = "🤴🏼"
            else:
                board[row][col] = piece
            board[sr][sc] = " "
            game["selected_piece"] = None
            game["turn"] = "black" if turn == "white" else "white"
            await safe_callback_answer(callback_query, "✅ Ход выполнен.")

        await show_board(game["chat_id"], game["message_id"], game_id, callback_query)

        white_left = any(p in ("w", "👑") for row in game["board"] for p in row)
        black_left = any(p in ("b", "🤴🏼") for row in game["board"] for p in row)
        if not white_left or not black_left:
            winner = "black" if not white_left else "white"
            winner_id = game["players"][winner]
            loser_id = game["players"]["white" if winner == "black" else "black"]
            stake = game["bet"]
            # Атомарный DELTA-режим: SET balance = balance + $2 под Redis-локом.
            # Раньше здесь был read-modify-write (get + SET абсолютного значения),
            # который затирал параллельные изменения баланса и кут «пропадал».
            await db.update_user_balance(winner_id, f"+{int(stake)}")
            await db.update_user_balance(loser_id, f"-{int(stake)}")
            await db.update_user_winamount(winner_id, stake)#
            await db.update_user_wins(winner_id, 1, bot1, ref_coin)
            await db.update_user_loose(loser_id, 1, bot1, ref_coin)#
            await db.update_game_last_activity(winner_id)
            await db.update_game_last_activity(loser_id)
            await db.cutehistory_plus(winner_id, stake, "+ шашки")
            await db.cutehistory_minus(loser_id, stake, "- шашки")
            await db.set_items(winner_id, "Фигурка шашки", 1)
            from main import check_bet_and_set_item
            await check_bet_and_set_item(winner_id, stake)

            white_style, black_style = game["style"]
            winner_emoji = white_style if winner == "white" else black_style
            first_name = await db.get_firstname_by_user_id(winner_id)
            username = await db.get_username_by_user_id(winner_id)
            winner_link = await create_user_link(winner_id, first_name, username)

            win_text = ""
            if stake > 0:
                win_amount = "{:,.0f}".format(stake).replace(",", ".")
                win_text = f"\n💰 <b>Выигрыш {win_amount} кут</b>"

            await safe_edit_message_text(
                chat_id=game["chat_id"], message_id=game["message_id"],
                text=f"{winner_emoji} <b>{winner_link} Победитель!</b>{win_text}", reply_markup=None,
                parse_mode="HTML", callback_query=callback_query)
            del gamessha[game_id]
    gamessha.save()


@dp.callback_query(lambda c: c.data.startswith('micha:'))
async def scah_draw_callback(callback_query: types.CallbackQuery):
    data = callback_query.data.split(":")
    game_id = int(data[1])
    user_id = callback_query.from_user.id
    if game_id not in gamessha:
        await safe_callback_answer(callback_query, "❗️ Игра не существует.", show_alert=True)
        return
    game = gamessha[game_id]
    players = game["players"]
    white_style, black_style = game["style"]
    white_btn = extract_default_emoji(white_style)
    black_btn = extract_default_emoji(black_style)

    if user_id == players["white"]:
        if game.get("draw_white"):
            await safe_callback_answer(callback_query, "❕ Вы уже запросили ничью.", show_alert=True)
            return
        game["draw_white"] = True
        await safe_callback_answer(callback_query, "✅ Вы предложили ничью. Ожидайте ответа.", show_alert=True)
    elif user_id == players["black"]:
        if game.get("draw_black"):
            await safe_callback_answer(callback_query, "❕ Вы уже запросили ничью.", show_alert=True)
            return
        game["draw_black"] = True
        await safe_callback_answer(callback_query, "✅ Вы предложили ничью. Ожидайте ответа.", show_alert=True)
    else:
        await safe_callback_answer(callback_query, "❗️ Вы не участник.", show_alert=True)
        return

    if game.get("draw_white") and game.get("draw_black"):
        white_name = await db.get_firstname_by_user_id(players["white"])
        black_name = await db.get_firstname_by_user_id(players["black"])
        handshake_emoji = "<tg-emoji emoji-id='5463249828450424568'>🤝</tg-emoji>"
        await safe_edit_message_text(
            chat_id=game["chat_id"], message_id=game["message_id"],
            text=f"{handshake_emoji} <b>Игра завершена ничьей</b>\n{white_style} {white_name}\n{black_style} {black_name}",
            reply_markup=None, parse_mode="HTML", callback_query=callback_query)
        del gamessha[game_id]
    else:
        await show_board(game["chat_id"], game["message_id"], game_id, callback_query)
    gamessha.save()


@dp.callback_query(lambda c: c.data.startswith('shahsurrender:'))
async def scah_surrender_callback(callback_query: types.CallbackQuery):
    data = callback_query.data.split(":")
    game_id = int(data[1])
    user_id = callback_query.from_user.id
    if game_id not in gamessha:
        await safe_callback_answer(callback_query, "🛠 Игра не существует.", show_alert=True)
        return
    game = gamessha[game_id]
    players = game["players"]
    white_style, black_style = game["style"]
    if user_id == players["white"]:
        winner_id = players["black"]
        loser_id = players["white"]
        winner_emoji = black_style
        await safe_callback_answer(callback_query, "❕ Вы сдались. Победа присуждена сопернику.", show_alert=True)
    elif user_id == players["black"]:
        winner_id = players["white"]
        loser_id = players["black"]
        winner_emoji = white_style
        await safe_callback_answer(callback_query, "❕ Вы сдались. Победа присуждена сопернику.", show_alert=True)
    else:
        await safe_callback_answer(callback_query, "❗️ Вы не участник.", show_alert=True)
        return
    stake = game["bet"]
    # Атомарный DELTA-режим (см. пояснение выше) — без гонки read-modify-write.
    await db.update_user_balance(winner_id, f"+{int(stake)}")
    await db.update_user_balance(loser_id, f"-{int(stake)}")
    await db.update_user_winamount(winner_id, stake)#
    await db.update_user_wins(winner_id, 1, bot1, ref_coin)
    await db.update_user_loose(loser_id, 1, bot1, ref_coin)#
    await db.update_game_last_activity(winner_id)
    await db.update_game_last_activity(loser_id)
    await db.cutehistory_plus(winner_id, stake, "+ шашки сдача")
    await db.cutehistory_minus(loser_id, stake, "- шашки сдача")
    await db.set_items(winner_id, "Фигурка шашки", 1)
    from main import check_bet_and_set_item
    await check_bet_and_set_item(winner_id, stake)

    first_name = await db.get_firstname_by_user_id(winner_id)
    username = await db.get_username_by_user_id(winner_id)
    winner_link = await create_user_link(winner_id, first_name, username)

    win_text = ""
    if stake > 0:
        win_amount = "{:,.0f}".format(stake).replace(",", ".")
        win_text = f"\n💰 <b>Выигрыш {win_amount} кут</b>"

    await safe_edit_message_text(
        chat_id=game["chat_id"], message_id=game["message_id"],
        text=f"{winner_emoji} <b>{winner_link} победил(-а) - соперник сдался!</b>{win_text}", reply_markup=None,
        parse_mode="HTML", callback_query=callback_query)
    del gamessha[game_id]
    gamessha.save()