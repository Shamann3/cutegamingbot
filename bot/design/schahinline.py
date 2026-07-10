# -*- coding: utf-8 -*-

# ✅ ВАЖНО:
# - Я НЕ меняю твои callback_data (checkers_create / unique_join_game / unique_start_game / inlineselect / inlinechange / michainlain / shahsurrenderinline)
# - Я сохраняю твою логику (inline_edit, ставки, анти-реф, save(), cooldown REST)
# - Я исправляю критические баги и делаю код “по твоему принципу”: проверки, защита, аккуратные try/except, без лишних падений
# - Добавлена поддержка двух режимов: реалистичный (обязательные взятия, цепочки) и аркадный (простая логика)
# - Переключение режима доступно создателю до начала игры
# - Кнопки используют обычный текст (без icon_custom_emoji_id), премиум-эмодзи только в тексте сообщений
# - Везде используется parse_mode="HTML" и disable_web_page_preview=True

from main import *

import asyncio
import random
import re
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any

from aiogram import types
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from main import inline_add_or_update_user_info, _format_hms, _pair_seconds_left
from bot.games.scah import shahstyles

shah_cooldowns: Dict[int, float] = {}
REST = 2.2

# =====================================================================
# ✅ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (общие)
# =====================================================================
_TG_EMOJI_RE = re.compile(r"<tg-emoji[^>]*>(.*?)</tg-emoji>")

def extract_default_emoji(value: str) -> str:
    if not isinstance(value, str):
        return ""
    m = _TG_EMOJI_RE.search(value)
    return m.group(1) if m else value

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

def _escape_html(text: str) -> str:
    """Экранирует HTML-спецсимволы для безопасного использования в parse_mode='HTML'."""
    if not text:
        return ""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

def _dedupe_preserve_order(items: List[int]) -> List[int]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def choose_style():
    return random.choice(shahstyles)

def initialize_board():
    return [
        ["b", " ", "b", " ", "b", " ", "b", " "],
        [" ", "b", " ", "b", " ", "b", " ", "b"],
        ["b", " ", "b", " ", "b", " ", "b", " "],
        [" ", " ", " ", " ", " ", " ", " ", " "],
        [" ", " ", " ", " ", " ", " ", " ", " "],
        [" ", "w", " ", "w", " ", "w", " ", "w"],
        ["w", " ", "w", " ", "w", " ", "w", " "],
        [" ", "w", " ", "w", " ", "w", " ", "w"]
    ]

def _get_game(game_id: str) -> Optional[Dict[str, Any]]:
    try:
        if not game_id:
            return None
        return inline_game_scah.get(game_id)
    except Exception:
        return None

def _save_games_silent():
    try:
        inline_game_scah.save()
    except Exception:
        pass

# =====================================================================
# ✅ БЕЗОПАСНОЕ РЕДАКТИРОВАНИЕ INLINE-СООБЩЕНИЙ (с повторами при flood)
# =====================================================================
async def safe_inline_edit(
    inline_message_id: str,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML",
    callback_query: Optional[types.CallbackQuery] = None,
    retries: int = 3
) -> bool:
    """Безопасное редактирование inline-сообщения с автоматическим повтором при flood control."""
    user_id = callback_query.from_user.id if callback_query else None
    for attempt in range(1, retries + 1):
        try:
            await bot1.edit_message_text(
                inline_message_id=inline_message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
            return True
        except TelegramBadRequest as e:
            error_str = str(e).lower()
            if "message is not modified" in error_str:
                return True
            match = re.search(r"retry after (\d+)", error_str)
            wait_seconds = int(match.group(1)) if match else None
            if wait_seconds is not None:
                if user_id and callback_query:
                    try:
                        await callback_query.answer(
                            f"⏳ Бот перегружен. Повторная попытка через {wait_seconds} сек.",
                            show_alert=True
                        )
                    except Exception:
                        pass
                await asyncio.sleep(wait_seconds + 0.5)
                continue
            else:
                print(f"Неисправимая ошибка при inline-редактировании: {e}")
                return False
        except Exception as e:
            print(f"Критическая ошибка при inline-редактировании: {e}")
            return False
    return False

async def safe_callback_answer(
    callback_query: types.CallbackQuery,
    text: str,
    show_alert: bool = False,
    retries: int = 2
) -> bool:
    """Безопасный ответ на callback с повторами при flood."""
    for attempt in range(1, retries + 1):
        try:
            await callback_query.answer(text, show_alert=show_alert)
            return True
        except (TelegramAPIError, TelegramBadRequest) as e:
            error_str = str(e).lower()
            match = re.search(r"retry after (\d+)", error_str)
            wait_seconds = int(match.group(1)) if match else None
            if wait_seconds is not None:
                try:
                    await callback_query.answer(
                        f"⏳ Бот перегружен. Повтор через {wait_seconds} сек.",
                        show_alert=True
                    )
                except Exception:
                    pass
                await asyncio.sleep(wait_seconds + 0.5)
                continue
            else:
                return False
        except Exception:
            return False
    return False

# =====================================================================
# ✅ LOCKS / ANTI-SPAM JOIN (как у тебя)
# =====================================================================
_inline_join_locks: Dict[str, asyncio.Lock] = LazyGameStore("_inline_join_locks")
_inline_inflight_joins: Set[Tuple[str, int]] = set()

def _get_inline_lock(game_id: str) -> asyncio.Lock:
    lock = _inline_join_locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _inline_join_locks[game_id] = lock
    return lock

# =====================================================================
# ✅ ЛОГИКА РЕЖИМОВ (исправленная)
# =====================================================================
def get_style_emoji_text(game: dict, turn: str) -> str:
    white_style, black_style = game.get("style", ("", ""))
    if turn == "white":
        emoji = extract_default_emoji(white_style)
        return f"белые {emoji}"
    else:
        emoji = extract_default_emoji(black_style)
        return f"чёрные {emoji}"

# ---------- Аркадный режим (исправлен: дамка не бьёт через свои фигуры) ----------
def _is_path_clear_arcade(board: List[List[str]], r: int, c: int, dr: int, dc: int, steps: int, own_pieces: Set[str]) -> bool:
    """Проверяет, что все клетки между (r,c) и (r+dr*steps, c+dc*steps) не содержат своих фигур."""
    for step in range(1, steps):
        rr = r + dr * step
        cc = c + dc * step
        if board[rr][cc] in own_pieces:
            return False
    return True

def get_valid_moves_arcade(row: int, col: int, turn: str, board: List[List[str]], is_king: bool = False) -> List[Tuple[int, int]]:
    directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    opponent_piece = "b" if turn == "white" else "w"
    opponent_king = "🤴🏼" if turn == "white" else "👑"
    own_pieces = {"w", "👑"} if turn == "white" else {"b", "🤴🏼"}
    valid_moves = []

    if not is_king:
        directions = directions[:2] if turn == "white" else directions[2:]

    for dr, dc in directions:
        # Простые ходы
        r, c = row + dr, col + dc
        while 0 <= r < 8 and 0 <= c < 8:
            if board[r][c] == " ":
                valid_moves.append((r, c))
                if not is_king:
                    break
            else:
                break
            if is_king:
                r += dr
                c += dc
            else:
                break

        # Взятие
        r, c = row + dr, col + dc
        step = 1
        while 0 <= r < 8 and 0 <= c < 8:
            cell = board[r][c]
            if cell in (opponent_piece, opponent_king):
                if _is_path_clear_arcade(board, row, col, dr, dc, step, own_pieces):
                    jump_r, jump_c = r + dr, c + dc
                    if 0 <= jump_r < 8 and 0 <= jump_c < 8 and board[jump_r][jump_c] == " ":
                        valid_moves.append((jump_r, jump_c))
                break
            elif cell in own_pieces:
                break
            if not is_king:
                break
            r += dr
            c += dc
            step += 1

    # Взятие назад для дамок
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
                            valid_moves.append((jump_r, jump_c))
                    break
                elif cell in own_pieces:
                    break
                r -= dr
                c -= dc
                step += 1

    return valid_moves

# ---------- Реалистичный режим (исправлен: проверка чистоты диагонали) ----------
def _is_path_clear_realistic(board: List[List[str]], r: int, c: int, dr: int, dc: int, steps: int, own_pieces: Set[str]) -> bool:
    """Проверяет, что все клетки между (r,c) и (r+dr*steps, c+dc*steps) пусты."""
    for step in range(1, steps):
        rr = r + dr * step
        cc = c + dc * step
        if board[rr][cc] != " ":
            return False
    return True

def _find_captures_from(r: int, c: int, board: List[List[str]], turn: str, is_king: bool, path: List[Tuple[int, int, int, int]], sequences: List[List[Tuple[int, int, int, int]]]):
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
                if current_is_king and not found:
                    continue
                else:
                    break
            elif cell in (opponent, opponent_king):
                # Проверяем, что все клетки между r,c и rr,cc пусты
                if not _is_path_clear_realistic(board, r, c, dr, dc, step, {own, own_king}):
                    break
                jump_r = rr + dr
                jump_c = cc + dc
                if 0 <= jump_r < 8 and 0 <= jump_c < 8 and board[jump_r][jump_c] == " ":
                    new_board = [row[:] for row in board]
                    new_board[rr][cc] = " "
                    new_board[jump_r][jump_c] = new_board[r][c]
                    new_board[r][c] = " "
                    if new_board[jump_r][jump_c] == "w" and jump_r == 0:
                        new_board[jump_r][jump_c] = "👑"
                    elif new_board[jump_r][jump_c] == "b" and jump_r == 7:
                        new_board[jump_r][jump_c] = "🤴🏼"
                    new_path = path + [(rr, cc, jump_r, jump_c)]
                    _find_captures_from(jump_r, jump_c, new_board, turn, True, new_path, sequences)
                    found = True
                break
            else:
                break
    if not found and path:
        sequences.append(path)

def get_all_captures_realistic(board: List[List[str]], turn: str) -> Dict[Tuple[int, int], List[List[Tuple[int, int, int, int]]]]:
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

def get_all_moves_realistic(board: List[List[str]], turn: str) -> Tuple[Dict[Tuple[int, int], List[Tuple[int, int]]], bool, Dict[Tuple[int, int], List[List[Tuple[int, int, int, int]]]]]:
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

def _get_simple_moves_realistic(row: int, col: int, board: List[List[str]], turn: str, is_king: bool) -> List[Tuple[int, int]]:
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

async def apply_move_realistic(board: List[List[str]], from_pos: Tuple[int, int], to_pos: Tuple[int, int], turn: str) -> Tuple[List[List[str]], bool, bool]:
    sr, sc = from_pos
    dr, dc = to_pos
    piece = board[sr][sc]
    capture_occurred = False
    # Если ход на две и более клетки - взятие
    if abs(dr - sr) >= 2 and abs(dc - sc) >= 2:
        capture_occurred = True
        step_r = 1 if dr > sr else -1
        step_c = 1 if dc > sc else -1
        # Ищем первую встречную фигуру противника на линии
        r, c = sr + step_r, sc + step_c
        while (r, c) != (dr, dc):
            cell = board[r][c]
            if cell != " ":
                # Удаляем только одну фигуру (первую)
                board[r][c] = " "
                break
            r += step_r
            c += step_c
    # Перемещаем шашку
    board[dr][dc] = piece
    board[sr][sc] = " "
    # Превращение в дамку
    if piece == "w" and dr == 0:
        board[dr][dc] = "👑"
    elif piece == "b" and dr == 7:
        board[dr][dc] = "🤴🏼"
    # Проверка возможности продолжения взятия
    continue_capture = False
    if capture_occurred:
        captures_after = get_all_captures_realistic(board, turn)
        if (dr, dc) in captures_after:
            continue_capture = True
    return board, capture_occurred, continue_capture

# =====================================================================
# ✅ КНОПКИ ВЫБОРА РЕЖИМА (для лобби)
# =====================================================================
def get_mode_buttons(game_id: str, game: dict) -> List[List[InlineKeyboardButton]]:
    current_mode = game.get("mode", "realistic")
    realistic_text = "Реализм"
    if current_mode == "realistic":
        realistic_text = f"• {realistic_text}"
    arcade_text = "Аркада"
    if current_mode == "arcade":
        arcade_text = f"• {arcade_text}"
    return [
        [
            InlineKeyboardButton(text=realistic_text, callback_data=f"checkers_mode:{game_id}:realistic"),
            InlineKeyboardButton(text=arcade_text, callback_data=f"checkers_mode:{game_id}:arcade")
        ]
    ]

# =====================================================================
# ✅ CREATE GAME (checkers_create)
# =====================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("checkers_create"))
async def create_checkers_game_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    creator_id = user_id

    if await db.is_user_banned(user_id):
        await safe_callback_answer(callback_query, "❗️ Вы заблокированы в боте", show_alert=True)
        return

    first_name = _safe_first_name(callback_query.from_user.first_name)
    username = callback_query.from_user.username
    try:
        await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)
    except Exception:
        pass

    bet_amount = 0
    try:
        data_parts = (callback_query.data or "").split(":")
        bet_amount = int(data_parts[2]) if len(data_parts) > 2 and str(data_parts[2]).isdigit() else 0
        if bet_amount < 0:
            bet_amount = 0
    except Exception:
        bet_amount = 0

    if bet_amount > 0:
        try:
            user_balance = await db.get_user_balance(user_id) or 0
        except Exception:
            user_balance = 0
        if user_balance < bet_amount:
            await safe_callback_answer(callback_query, "💭 Недостаточно средств для игры с такой ставкой.", show_alert=True)
            return

    game_id = str(uuid.uuid4())
    game_style = choose_style()

    inline_game_scah[game_id] = {
        "game_id": game_id,
        "creator": creator_id,
        "participants": [creator_id],
        "players": {},
        "board": initialize_board(),
        "turn": "white",
        "selected_piece": None,
        "inline_message_id": callback_query.inline_message_id,
        "style": game_style,
        "creator_name": first_name,
        "creator_username": username,
        "opponent_name": None,
        "opponent_id": None,
        "opponent_username": None,
        "bet_amount": bet_amount,
        "draw_request": {"white": False, "black": False},
        "mode": "realistic",
        "mode_locked": False,
    }

    mode_buttons = get_mode_buttons(game_id, inline_game_scah[game_id])
    join_button = InlineKeyboardButton(text="Присоединиться", callback_data=f"unique_join_game:{game_id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=mode_buttons + [[join_button]])

    bet_line = f"<tg-emoji emoji-id='5424687267014801006'>♟</tg-emoji> Ставка : {_fmt_kut(bet_amount)} кут\n" if bet_amount > 0 else ""
    white_style, _black_style = game_style

    await safe_inline_edit(
        inline_message_id=callback_query.inline_message_id,
        text=f"♟ <b>Играем в Шашки</b>\n<b>{bet_line}</b>- {white_style} <b>{_escape_html(first_name)}</b>",
        parse_mode="HTML",
        reply_markup=keyboard,
        callback_query=callback_query
    )
    _save_games_silent()
    await safe_callback_answer(callback_query, "❕ Лобби создано!")

# =====================================================================
# ✅ ИЗМЕНЕНИЕ РЕЖИМА (checkers_mode)
# =====================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("checkers_mode:"))
async def change_mode_callback(callback_query: types.CallbackQuery):
    try:
        _, game_id, mode = callback_query.data.split(":")
    except Exception:
        await safe_callback_answer(callback_query, "⚠️ Неверные данные.", show_alert=True)
        return

    user_id = callback_query.from_user.id
    if await db.is_user_banned(user_id):
        await safe_callback_answer(callback_query, "❗️ Вы заблокированы в боте", show_alert=True)
        return

    game = _get_game(game_id)
    if not game:
        await safe_callback_answer(callback_query, "🛠 Игра не существует.", show_alert=True)
        return

    if user_id != game.get("creator"):
        await safe_callback_answer(callback_query, "❕ Только создатель может менять режим.", show_alert=True)
        return

    if game.get("mode_locked", False):
        await safe_callback_answer(callback_query, "❕ Режим уже заблокирован (игра начата).", show_alert=True)
        return

    if mode not in ("realistic", "arcade"):
        return

    game["mode"] = mode
    _save_games_silent()

    bet_amount = game.get("bet_amount", 0)
    bet_line = f"<tg-emoji emoji-id='5424687267014801006'>♟</tg-emoji> Ставка : {_fmt_kut(bet_amount)} кут\n" if bet_amount > 0 else ""
    creator_name = game.get("creator_name") or "Игрок"
    opponent_name = game.get("opponent_name")
    white_style, black_style = game["style"]

    participants = game.get("participants", [])
    lines = []
    for idx, uid in enumerate(participants):
        nm = creator_name if int(uid) == game.get("creator") else opponent_name
        emo = white_style if idx == 0 else black_style
        lines.append(f"- {emo} <b>{_escape_html(nm)}</b>")

    mode_buttons = get_mode_buttons(game_id, game)
    if len(participants) >= 2:
        additional_buttons = [[InlineKeyboardButton(text="Начать игру", callback_data=f"unique_start_game:{game_id}")]]
    else:
        additional_buttons = [[InlineKeyboardButton(text="Присоединиться", callback_data=f"unique_join_game:{game_id}")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=mode_buttons + additional_buttons)

    await safe_inline_edit(
        inline_message_id=game["inline_message_id"],
        text=f"<tg-emoji emoji-id='5424687267014801006'>♟</tg-emoji> <b>Играем в Шашки</b>\n<b>{bet_line}</b>{chr(10).join(lines)}",
        reply_markup=keyboard,
        parse_mode="HTML",
        callback_query=callback_query
    )
    mode_name = "Реализм" if mode == "realistic" else "Аркаду"
    await safe_callback_answer(callback_query, f"Режим изменён на {mode_name}.")

# =====================================================================
# ✅ JOIN GAME (unique_join_game) – ИСПРАВЛЕНА АНТИФЕРМА
# =====================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("unique_join_game:"))
async def join_checkers_game_callback(callback_query: types.CallbackQuery):
    try:
        game_id = (callback_query.data or "").split(":", 1)[1]
    except Exception:
        await safe_callback_answer(callback_query, "⚠️ Неверные данные.", show_alert=True)
        return

    user_id = callback_query.from_user.id
    if await db.is_user_banned(user_id):
        await safe_callback_answer(callback_query, "❗️ Вы заблокированы в боте", show_alert=True)
        return

    first_name = _safe_first_name(callback_query.from_user.first_name)
    username = callback_query.from_user.username
    try:
        await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)
    except Exception:
        pass

    game = _get_game(game_id)
    if not game:
        await safe_callback_answer(callback_query, "🛠 Эта игра больше не существует.", show_alert=True)
        return

    inflight_key = (game_id, user_id)
    if inflight_key in _inline_inflight_joins:
        await safe_callback_answer(callback_query, "⏳ Обрабатываю ваше присоединение...", show_alert=False)
        return

    _inline_inflight_joins.add(inflight_key)
    try:
        lock = _get_inline_lock(game_id)
        async with lock:
            game = _get_game(game_id)
            if not game:
                await safe_callback_answer(callback_query, "🛠 Эта игра больше не существует.", show_alert=True)
                return

            if user_id == int(game.get("creator") or 0):
                await safe_callback_answer(callback_query, "❗️ Вы не можете присоединиться к своей игре.", show_alert=True)
                return

            participants = _dedupe_preserve_order([int(x) for x in game.get("participants", [])])
            game["participants"] = participants

            if len(participants) >= 2:
                await safe_callback_answer(callback_query, "❗️ В игре нет мест.", show_alert=True)
                return

            if user_id in participants:
                await safe_callback_answer(callback_query, "❗️ Вы уже участвуете в этой игре.", show_alert=True)
                return

            # ---------- АНТИФЕРМА (исправлена: ошибки не блокируют) ----------
            try:
                inviter_id = None
                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    # Нет реферера – просто игнорируем
                    pass
                except Exception as e:
                    print(f"[ANTIFARM] Ошибка get_refferer_id_or_error: {e}")

                parts_set = set(participants)
                if inviter_id and inviter_id in parts_set:
                    now = datetime.now()
                    secs = await _pair_seconds_left(db, user_id, inviter_id, now=now)
                    if secs > 0:
                        ts = _format_hms(secs)
                        await safe_callback_answer(callback_query, f"💭 Антиферма: {ts}\n#AntiFarmSystem", show_alert=True)
                        return

                invitees_here = []
                try:
                    invitees_here = await db.get_invitees_in(inviter_id=user_id, candidates=parts_set)
                except Exception as e:
                    print(f"[ANTIFARM] Ошибка get_invitees_in: {e}")

                if invitees_here:
                    now = datetime.now()
                    min_secs = None
                    for invitee_id in invitees_here:
                        try:
                            secs = await _pair_seconds_left(db, user_id, invitee_id, now=now)
                            if secs > 0:
                                min_secs = secs if min_secs is None else min(min_secs, secs)
                        except Exception as e:
                            print(f"[ANTIFARM] Ошибка _pair_seconds_left: {e}")
                    if min_secs:
                        ts = _format_hms(min_secs)
                        await safe_callback_answer(callback_query, f"💭 Антиферма: {ts}\n#AntiFarmSystem", show_alert=True)
                        return
            except Exception as e:
                # Любая ошибка в антиферме не должна блокировать игру – только логируем
                print(f"[ANTIFARM] Неожиданная ошибка: {e}")
            # ---------- КОНЕЦ АНТИФЕРМЫ ----------

            bet_amount = int(game.get("bet_amount", 0) or 0)
            if bet_amount > 0:
                bal = await db.get_user_balance(user_id) or 0
                if bal < bet_amount:
                    await safe_callback_answer(callback_query, "💭 У вас недостаточно средств для игры.", show_alert=True)
                    return

            participants.append(user_id)
            participants = _dedupe_preserve_order(participants)
            game["participants"] = participants
            if not game.get("opponent_id"):
                game["opponent_id"] = user_id
                game["opponent_name"] = first_name
                game["opponent_username"] = username
            elif int(game.get("opponent_id") or 0) != user_id:
                game["participants"] = [p for p in participants if p != user_id]
                await safe_callback_answer(callback_query, "❗️ Место уже занято.", show_alert=True)
                return

            creator_name = game.get("creator_name") or "Игрок"
            opponent_name = game.get("opponent_name") or first_name
            white_style, black_style = game["style"]
            bet_line = f"<tg-emoji emoji-id='5425117176061261659'>💰</tg-emoji> Ставка : {_fmt_kut(bet_amount)} кут\n" if bet_amount > 0 else ""
            lines = []
            for idx, uid in enumerate(game["participants"]):
                nm = creator_name if int(uid) == game.get("creator") else opponent_name
                emo = white_style if idx == 0 else black_style
                lines.append(f"- {emo} <b>{_escape_html(nm)}</b>")

            mode_buttons = get_mode_buttons(game_id, game)
            start_button = [[InlineKeyboardButton(text="Начать игру", callback_data=f"unique_start_game:{game_id}")]]
            keyboard = InlineKeyboardMarkup(inline_keyboard=mode_buttons + start_button)

            await safe_inline_edit(
                inline_message_id=game["inline_message_id"],
                text=f"<tg-emoji emoji-id='5424687267014801006'>♟</tg-emoji> <b>Играем в Шашки</b>\n<b>{bet_line}</b>{chr(10).join(lines)}",
                reply_markup=keyboard,
                parse_mode="HTML",
                callback_query=callback_query
            )
            _save_games_silent()
            await safe_callback_answer(callback_query, "❕ Вы присоединились к игре!", show_alert=False)
    finally:
        _inline_inflight_joins.discard(inflight_key)

# =====================================================================
# ✅ START GAME (unique_start_game)
# =====================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("unique_start_game:"))
async def start_checkers_game_callback(callback_query: types.CallbackQuery):
    try:
        game_id = (callback_query.data or "").split(":", 1)[1]
    except Exception:
        await safe_callback_answer(callback_query, "⚠️ Неверные данные.", show_alert=True)
        return

    user_id = callback_query.from_user.id
    if await db.is_user_banned(user_id):
        await safe_callback_answer(callback_query, "❗️ Вы заблокированы в боте", show_alert=True)
        return

    first_name = _safe_first_name(callback_query.from_user.first_name)
    username = callback_query.from_user.username
    try:
        await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)
    except Exception:
        pass

    game = _get_game(game_id)
    if not game:
        await safe_callback_answer(callback_query, "🛠 Эта игра больше не существует.", show_alert=True)
        return

    if int(user_id) != int(game.get("creator") or 0):
        await safe_callback_answer(callback_query, "️️❗️ Только создатель игры может начать игру.", show_alert=True)
        return

    participants = game.get("participants", [])
    if not isinstance(participants, list) or len(participants) != 2:
        await safe_callback_answer(callback_query, "❗️ Невозможно начать игру. Требуется два участника.", show_alert=True)
        return

    bet_amount = int(game.get("bet_amount", 0) or 0)
    insufficient = []
    for pid in participants:
        bal = await db.get_user_balance(pid) or 0
        if bal < bet_amount:
            insufficient.append(pid)
    if insufficient:
        links = []
        for pid in insufficient:
            fn = await db.get_firstname_by_user_id(pid)
            un = await db.get_username_by_user_id(pid)
            link = await create_user_link(pid, fn, un)
            links.append(link)
        text = f"⛑ <b>Игра остановлена!\nНедостаточно средств у {', '.join(links)}</b>"
        await safe_inline_edit(
            inline_message_id=game["inline_message_id"],
            text=text,
            reply_markup=None,
            parse_mode="HTML",
            callback_query=callback_query
        )
        del inline_game_scah[game_id]
        _save_games_silent()
        return

    game["mode_locked"] = True
    creator_id = int(game.get("creator") or 0)
    opponent_id = int(participants[1])
    game["players"] = {"white": creator_id, "black": opponent_id}
    game["selected_piece"] = None
    game["turn"] = "white"
    game["board"] = initialize_board()
    game["draw_request"] = {"white": False, "black": False}

    try:
        await db.add_game_inline(
            user_id1=creator_id,
            name_user1=game.get("creator_name") or "Игрок 1",
            user_id2=opponent_id,
            name_user2=game.get("opponent_name") or "Игрок 2",
            namegame="shah",
            username1=game.get("creator_username"),
            username2=game.get("opponent_username"),
        )
    except Exception as e:
        print(f"🧩 [ШАШКИ][START][ERROR] add_game_inline: {e}")

    _save_games_silent()
    await safe_callback_answer(callback_query, "❕ Игра началась!", show_alert=False)
    await inline_show_board(callback_query, game_id)
    _save_games_silent()

# =====================================================================
# ✅ ОБРАБОТКА ВЫБОРА / ХОДА (inlineselect)
# =====================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("inlineselect:"))
async def select_piece_callback(callback_query: types.CallbackQuery):
    data = (callback_query.data or "").split(":")
    if len(data) < 4:
        await safe_callback_answer(callback_query, "⚠️ Неверные данные.", show_alert=True)
        return

    game_id = data[1]
    try:
        row = int(data[2])
        col = int(data[3])
    except Exception:
        await safe_callback_answer(callback_query, "⚠️ Неверные координаты.", show_alert=True)
        return

    user_id = callback_query.from_user.id
    if await db.is_user_banned(user_id):
        await safe_callback_answer(callback_query, "❗️ Вы заблокированы в боте", show_alert=True)
        return

    current_time = time.time()
    last_usage = shah_cooldowns.get(user_id, 0.0)
    if current_time - last_usage < REST:
        await safe_callback_answer(callback_query, f"⌚️ Не спешите", show_alert=True)
        return
    shah_cooldowns[user_id] = current_time

    game = _get_game(game_id)
    if not game:
        await safe_callback_answer(callback_query, "🛠 Эта игра больше не существует.", show_alert=True)
        return

    bet_amount = int(game.get("bet_amount", 0) or 0)
    if bet_amount > 0:
        for pid in game.get("participants", []):
            bal = await db.get_user_balance(pid) or 0
            if bal < bet_amount:
                links = []
                for p in game["participants"]:
                    fn = await db.get_firstname_by_user_id(p)
                    un = await db.get_username_by_user_id(p)
                    links.append(await create_user_link(p, fn, un))
                text = f"⛑ <b>Игра остановлена!\nНедостаточно средств у {', '.join(links)}</b>"
                await safe_inline_edit(
                    inline_message_id=game["inline_message_id"],
                    text=text,
                    reply_markup=None,
                    parse_mode="HTML",
                    callback_query=callback_query
                )
                del inline_game_scah[game_id]
                _save_games_silent()
                return

    board = game["board"]
    turn = game["turn"]
    players = game.get("players", {})
    if not players or "white" not in players or "black" not in players:
        await safe_callback_answer(callback_query, "❗️ Игра ещё не началась.", show_alert=True)
        return

    if user_id not in game.get("participants", []):
        await safe_callback_answer(callback_query, "❗️ Вы не являетесь участником этой игры.", show_alert=True)
        return

    if int(players.get(turn) or 0) != user_id:
        await safe_callback_answer(callback_query, "❗️ Сейчас не ваш ход.", show_alert=True)
        return

    mode = game.get("mode", "realistic")
    selected = game.get("selected_piece")

    if selected is None:
        piece = board[row][col]
        own = "w" if turn == "white" else "b"
        own_king = "👑" if turn == "white" else "🤴🏼"
        if piece not in (own, own_king):
            style_text = get_style_emoji_text(game, turn)
            await safe_callback_answer(callback_query, f"❕ Выберите свою шашку ({style_text})")
            return

        is_king = piece in ("👑", "🤴🏼")
        if mode == "realistic":
            moves_dict, must_capture, _ = get_all_moves_realistic(board, turn)
            valid = moves_dict.get((row, col), [])
            if must_capture and not valid:
                await safe_callback_answer(callback_query, "⚠️ Обязательное взятие! Вы должны побить шашку противника.")
                return
        else:
            valid = get_valid_moves_arcade(row, col, turn, board, is_king)

        if not valid:
            await safe_callback_answer(callback_query, "❕ У этой шашки нет ходов. Выберите другую.")
            return

        game["selected_piece"] = (row, col)
        if mode == "realistic" and must_capture:
            await safe_callback_answer(callback_query, "⚡ Обязательное взятие!")
        else:
            await safe_callback_answer(callback_query, "✅ Шашка выбрана.")
        await inline_show_board(callback_query, game_id)
        _save_games_silent()
        return

    sr, sc = selected
    piece = board[sr][sc]
    is_king = piece in ("👑", "🤴🏼")

    valid_move = False
    if mode == "realistic":
        moves_dict, must_capture, _ = get_all_moves_realistic(board, turn)
        if (sr, sc) in moves_dict and (row, col) in moves_dict[(sr, sc)]:
            valid_move = True
    else:
        valid_moves = get_valid_moves_arcade(sr, sc, turn, board, is_king)
        if (row, col) in valid_moves:
            valid_move = True

    if not valid_move:
        piece2 = board[row][col]
        own = "w" if turn == "white" else "b"
        own_king = "👑" if turn == "white" else "🤴🏼"
        if piece2 in (own, own_king):
            new_is_king = piece2 in ("👑", "🤴🏼")
            if mode == "realistic":
                moves_dict2, must_capture2, _ = get_all_moves_realistic(board, turn)
                new_valid = moves_dict2.get((row, col), [])
                if must_capture2 and not new_valid:
                    await safe_callback_answer(callback_query, "⚠️ Обязательное взятие! Вы должны бить.")
                    return
            else:
                new_valid = get_valid_moves_arcade(row, col, turn, board, new_is_king)
            if not new_valid:
                await safe_callback_answer(callback_query, "❕ У этой шашки нет ходов. Выберите другую.")
                return
            game["selected_piece"] = (row, col)
            await safe_callback_answer(callback_query, "✅ Выбрана новая шашка. Теперь выберите клетку.")
            await inline_show_board(callback_query, game_id)
            _save_games_silent()
        else:
            await safe_callback_answer(callback_query, "❌ Недопустимый ход")
        return

    if mode == "realistic":
        new_board, was_capture, continue_capture = await apply_move_realistic(board, (sr, sc), (row, col), turn)
        game["board"] = new_board
        game["selected_piece"] = None
        if continue_capture:
            game["selected_piece"] = (row, col)
            await safe_callback_answer(callback_query, "✅ Взятие! Можно продолжить бить той же шашкой.")
            await inline_show_board(callback_query, game_id)
            _save_games_silent()
            return
        else:
            game["turn"] = "black" if turn == "white" else "white"
            if was_capture:
                await safe_callback_answer(callback_query, "✅ Взятие выполнено! Ход переходит к сопернику.")
            else:
                await safe_callback_answer(callback_query, "✅ Ход выполнен.")
    else:
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

    await inline_show_board(callback_query, game_id)
    _save_games_silent()

    white_left = any(p in ("w", "👑") for row in game["board"] for p in row)
    black_left = any(p in ("b", "🤴🏼") for row in game["board"] for p in row)
    if not white_left or not black_left:
        await end_game(game_id, callback_query)

# =====================================================================
# ✅ ЗАВЕРШЕНИЕ ИГРЫ (исправлена статистика и выдача предмета)
# =====================================================================
async def end_game(game_id: str, callback_query: types.CallbackQuery):
    game = _get_game(game_id)
    if not game:
        return

    board = game["board"]
    white_left = any(p in ("w", "👑") for row in board for p in row)
    black_left = any(p in ("b", "🤴🏼") for row in board for p in row)

    if white_left and black_left:
        return

    winner = "white" if white_left else "black"
    winner_id = int(game["players"].get(winner, 0))
    loser_id = int(game["players"].get("black" if winner == "white" else "white", 0))

    style = game.get("style", ("", ""))
    white_style, black_style = style if isinstance(style, (list, tuple)) and len(style) == 2 else ("", "")
    winner_piece = white_style if winner == "white" else black_style

    try:
        fn = await db.get_firstname_by_user_id(winner_id)
        un = await db.get_username_by_user_id(winner_id)
    except Exception:
        fn, un = "Игрок", None
    name_link = await create_user_link(winner_id, fn, un)

    bet_amount = int(game.get("bet_amount", 0) or 0)
    results_text = f"🏆 {winner_piece} <b>{_escape_html(fn)} Победитель!</b>"

    if bet_amount > 0:
        try:
            winner_balance = await db.get_user_balance(winner_id) or 0
            loser_balance = await db.get_user_balance(loser_id) or 0
            if loser_balance >= bet_amount:
                await db.update_user_balance(winner_id, winner_balance + bet_amount)
                await db.update_user_balance(loser_id, loser_balance - bet_amount)
                await db.touch_balance_last_active(winner_id, set_active_status=True)
                await db.touch_balance_last_active(loser_id, set_active_status=True)
                await db.cutehistory_plus(winner_id, bet_amount, "+ шашки инлайн")
                await db.cutehistory_minus(loser_id, bet_amount, "- шашки инлайн")
                results_text = f"🏆 {winner_piece} <b>{_escape_html(fn)} Победитель!\n</b><tg-emoji emoji-id='5425117176061261659'>💰</tg-emoji> <b>Выигрыш {_fmt_kut(bet_amount)} кут</b>"
            else:
                results_text = f"🏆 {winner_piece} <b>{_escape_html(fn)} Победитель!\n</b>❌ <b>У проигравшего нет средств для выплаты выигрыша</b>"
        except Exception:
            results_text = f"🏆 {winner_piece} <b>{_escape_html(fn)} Победитель!\n</b>❌ <b>Ошибка при выплате выигрыша</b>"

    # Правильная статистика
    try:
        await db.update_user_wins(winner_id, 1, bot1, ref_coin)
        await db.update_user_winamount(winner_id, bet_amount)#
        await db.update_user_loose(loser_id, 1, bot1, ref_coin)#
        await db.update_game_last_activity(winner_id)
        await db.update_game_last_activity(loser_id)
        await db.set_items(winner_id, "Фигурка шашки", 1)
        from main import check_bet_and_set_item
        await check_bet_and_set_item(winner_id, bet_amount)
    except Exception as e:
        print(f"Ошибка обновления статистики: {e}")

    if bet_amount > 0:
        btn = InlineKeyboardButton(text="Создать новую игру", callback_data=f"checkers_create:{winner_id}:{bet_amount}")
    else:
        btn = InlineKeyboardButton(text="Создать новую игру", callback_data="checkers_create")
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn]])

    await safe_inline_edit(
        inline_message_id=game["inline_message_id"],
        text=results_text,
        reply_markup=kb,
        parse_mode="HTML",
        callback_query=callback_query
    )
    del inline_game_scah[game_id]
    _save_games_silent()

# =====================================================================
# ✅ INLINECHANGE (смена выбранной шашки)
# =====================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("inlinechange:"))
async def change_piece_callback(callback_query: types.CallbackQuery):
    data = (callback_query.data or "").split(":")
    if len(data) < 4:
        await safe_callback_answer(callback_query, "⚠️ Неверные данные.", show_alert=True)
        return

    game_id = data[1]
    try:
        row = int(data[2])
        col = int(data[3])
    except Exception:
        await safe_callback_answer(callback_query, "⚠️ Неверные координаты.", show_alert=True)
        return

    user_id = callback_query.from_user.id
    if await db.is_user_banned(user_id):
        await safe_callback_answer(callback_query, "❗️ Вы заблокированы в боте", show_alert=True)
        return

    current_time = time.time()
    last_usage = shah_cooldowns.get(user_id, 0.0)
    if current_time - last_usage < REST:
        await safe_callback_answer(callback_query, f"⌚️ Подождите {int(REST - (current_time - last_usage))} сек", show_alert=True)
        return
    shah_cooldowns[user_id] = current_time

    game = _get_game(game_id)
    if not game:
        await safe_callback_answer(callback_query, "🛠 Эта игра больше не существует.", show_alert=True)
        return

    board = game["board"]
    turn = game["turn"]
    players = game.get("players", {})
    if not players or "white" not in players or "black" not in players:
        await safe_callback_answer(callback_query, "❗️ Игра ещё не началась.", show_alert=True)
        return

    if int(players.get(turn) or 0) != user_id:
        await safe_callback_answer(callback_query, "❗️ Сейчас не ваш ход.", show_alert=True)
        return

    mode = game.get("mode", "realistic")

    sel = game.get("selected_piece")
    if sel is not None:
        sr, sc = sel
        for r in range(8):
            for c in range(8):
                if board[r][c] in ("✖️", "☑️"):
                    board[r][c] = " "

    piece = board[row][col]
    own = "w" if turn == "white" else "b"
    own_king = "👑" if turn == "white" else "🤴🏼"
    if piece not in (own, own_king):
        style_text = get_style_emoji_text(game, turn)
        await safe_callback_answer(callback_query, f"❕ Выберите свою шашку ({style_text})")
        return

    is_king = piece in ("👑", "🤴🏼")
    if mode == "realistic":
        moves_dict, must_capture, _ = get_all_moves_realistic(board, turn)
        valid_moves = moves_dict.get((row, col), [])
        if must_capture and not valid_moves:
            await safe_callback_answer(callback_query, "⚠️ Обязательное взятие! Вы должны побить шашку противника.")
            return
    else:
        valid_moves = get_valid_moves_arcade(row, col, turn, board, is_king)

    if not valid_moves:
        await safe_callback_answer(callback_query, "❕ У этой шашки нет ходов. Выберите другую.")
        return

    for r in range(8):
        for c in range(8):
            if board[r][c] in ("✖️", "☑️"):
                board[r][c] = " "

    for (tr, tc) in valid_moves:
        if abs(tr - row) >= 2:
            board[tr][tc] = "☑️"
        else:
            board[tr][tc] = "✖️"

    game["selected_piece"] = (row, col)
    await safe_callback_answer(callback_query, "❕ Выбрана новая шашка.", show_alert=False)
    await inline_show_board(callback_query, game_id)
    _save_games_silent()

# =====================================================================
# ✅ DRAW (michainlain)
# =====================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("michainlain:"))
async def draw_callback(callback_query: types.CallbackQuery):
    try:
        game_id = (callback_query.data or "").split(":", 1)[1]
    except Exception:
        await safe_callback_answer(callback_query, "⚠️ Неверные данные.", show_alert=True)
        return

    user_id = callback_query.from_user.id
    if await db.is_user_banned(user_id):
        await safe_callback_answer(callback_query, "❗️ Вы заблокированы в боте", show_alert=True)
        return

    game = _get_game(game_id)
    if not game:
        await safe_callback_answer(callback_query, "🛠 Эта игра больше не существует.", show_alert=True)
        return

    participants = game.get("participants", [])
    if user_id not in participants:
        await safe_callback_answer(callback_query, "❗️ Вы не участник этой игры.", show_alert=True)
        return

    players = game.get("players", {})
    if not players or "white" not in players or "black" not in players:
        await safe_callback_answer(callback_query, "❗️ Игра ещё не началась.", show_alert=True)
        return

    side = "white" if int(players.get("white") or 0) == user_id else "black"
    draw_request = game.get("draw_request", {"white": False, "black": False})
    if draw_request.get(side):
        await safe_callback_answer(callback_query, "❗️ Вы уже запросили ничью.", show_alert=True)
        return

    draw_request[side] = True
    game["draw_request"] = draw_request

    creator_name = game.get("creator_name") or "Игрок 1"
    opponent_name = game.get("opponent_name") or "Игрок 2"
    white_style, black_style = game["style"]

    if not draw_request.get("white") or not draw_request.get("black"):
        who_wait = opponent_name if side == "white" else creator_name
        await safe_callback_answer(callback_query, f"🤝 Вы запросили ничью. Ожидайте подтверждения от {_escape_html(who_wait)}.", show_alert=True)
        _save_games_silent()
        return

    btn = InlineKeyboardButton(text="Создать новую игру", callback_data="checkers_create")
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn]])
    await safe_inline_edit(
        inline_message_id=game["inline_message_id"],
        text=f"🤝 <b>Игра завершена ничьей</b>\n<b>{white_style} {_escape_html(creator_name)}\n{black_style} {_escape_html(opponent_name)}</b>",
        reply_markup=kb,
        parse_mode="HTML",
        callback_query=callback_query
    )
    del inline_game_scah[game_id]
    _save_games_silent()

# =====================================================================
# ✅ SURRENDER (shahsurrenderinline) – исправлена статистика
# =====================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("shahsurrenderinline:"))
async def surrender_callback(callback_query: types.CallbackQuery):
    try:
        game_id = (callback_query.data or "").split(":", 1)[1]
    except Exception:
        await safe_callback_answer(callback_query, "⚠️ Неверные данные.", show_alert=True)
        return

    user_id = callback_query.from_user.id
    if await db.is_user_banned(user_id):
        await safe_callback_answer(callback_query, "❗️ Вы заблокированы в боте", show_alert=True)
        return

    game = _get_game(game_id)
    if not game:
        await safe_callback_answer(callback_query, "🛠 Эта игра больше не существует.", show_alert=True)
        return

    players = game.get("players", {})
    if not players or "white" not in players or "black" not in players:
        await safe_callback_answer(callback_query, "❗️ Игра ещё не началась.", show_alert=True)
        return

    style = game.get("style", ("", ""))
    white_style, black_style = style if isinstance(style, (list, tuple)) and len(style) == 2 else ("", "")

    if int(user_id) == int(players.get("white") or 0):
        winner_id = int(players.get("black") or 0)
        loser_id = int(players.get("white") or 0)
        winner_piece = black_style
    elif int(user_id) == int(players.get("black") or 0):
        winner_id = int(players.get("white") or 0)
        loser_id = int(players.get("black") or 0)
        winner_piece = white_style
    else:
        await safe_callback_answer(callback_query, "❗️ Вы не являетесь участником этой игры.", show_alert=True)
        return

    try:
        fn = await db.get_firstname_by_user_id(winner_id)
        un = await db.get_username_by_user_id(winner_id)
    except Exception:
        fn, un = "Игрок", None
    name_link = await create_user_link(winner_id, fn, un)

    bet_amount = int(game.get("bet_amount", 0) or 0)
    results_text = f"🏳️ {winner_piece} <b>{_escape_html(fn)} победил(-а) - соперник сдался!</b>"

    if bet_amount > 0:
        try:
            winner_balance = await db.get_user_balance(winner_id) or 0
            loser_balance = await db.get_user_balance(loser_id) or 0
            if loser_balance >= bet_amount:
                await db.update_user_balance(winner_id, winner_balance + bet_amount)
                await db.update_user_balance(loser_id, loser_balance - bet_amount)
                await db.cutehistory_plus(winner_id, bet_amount, "инлайн шашки сдача")
                await db.cutehistory_minus(loser_id, bet_amount, "инлайн шашки сдача")
                results_text = f"🏳️ {winner_piece} <b>{_escape_html(fn)} победил(-а) - соперник сдался!\n</b><tg-emoji emoji-id='5425117176061261659'>💰</tg-emoji> <b>Выигрыш {_fmt_kut(bet_amount)} кут</b>"
            else:
                results_text = f"🏳️ {winner_piece} <b>{_escape_html(fn)} победил(-а) - соперник сдался!\n</b>❌ <b>У проигравшего нет средств для выплаты выигрыша</b>"
        except Exception:
            results_text = f"🏳️ {winner_piece} <b>{_escape_html(fn)} победил(-а) - соперник сдался!\n</b>❌ <b>Ошибка при выплате выигрыша</b>"

    # Правильная статистика
    try:
        await db.update_user_wins(winner_id, 1, bot1, ref_coin)
        await db.update_user_winamount(winner_id, bet_amount)#
        await db.update_user_loose(loser_id, 1, bot1, ref_coin)#
        await db.update_game_last_activity(winner_id)
        await db.update_game_last_activity(loser_id)

        await db.set_items(winner_id, "Фигурка шашки", 1)
        from main import check_bet_and_set_item
        await check_bet_and_set_item(winner_id, bet_amount)
    except Exception as e:
        print(f"Ошибка обновления статистики при сдаче: {e}")

    if bet_amount > 0:
        btn = InlineKeyboardButton(text="Создать новую игру", callback_data=f"checkers_create:{winner_id}:{bet_amount}")
    else:
        btn = InlineKeyboardButton(text="Создать новую игру", callback_data="checkers_create")
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn]])

    await safe_inline_edit(
        inline_message_id=game["inline_message_id"],
        text=results_text,
        reply_markup=kb,
        parse_mode="HTML",
        callback_query=callback_query
    )
    del inline_game_scah[game_id]
    _save_games_silent()

# =====================================================================
# ✅ ОТОБРАЖЕНИЕ ДОСКИ (inline_show_board)
# =====================================================================
async def inline_show_board(callback_query: types.CallbackQuery, game_id: str):
    game = _get_game(game_id)
    if not game:
        return

    board = game["board"]
    selected_piece = game.get("selected_piece")
    turn = game["turn"]
    players = game.get("players", {})
    mode = game.get("mode", "realistic")

    style = game.get("style", ("", ""))
    if not isinstance(style, (tuple, list)) or len(style) != 2:
        return
    white_piece_html, black_piece_html = style
    white_piece_btn = extract_default_emoji(white_piece_html) or "⚪"
    black_piece_btn = extract_default_emoji(black_piece_html) or "⚫"

    current_player_id = players.get(turn)
    if not current_player_id:
        return

    white_cnt = sum(1 for row in board for p in row if p in ("w", "👑"))
    black_cnt = sum(1 for row in board for p in row if p in ("b", "🤴🏼"))

    display_board = [row[:] for row in board]

    if selected_piece is not None:
        sr, sc = selected_piece
        if mode == "realistic":
            moves_dict, must_capture, _ = get_all_moves_realistic(board, turn)
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
            if selected_piece == (r, c):
                btn_text = "✅"
            else:
                piece = display_board[r][c]
                if piece == "w":
                    btn_text = white_piece_btn
                elif piece == "b":
                    btn_text = black_piece_btn
                elif piece == "✖️":
                    btn_text = "✖️"
                elif piece == "☑️":
                    btn_text = "☑️"
                elif piece in ("👑", "🤴🏼"):
                    btn_text = piece
                else:
                    btn_text = "  "
            row_buttons.append(InlineKeyboardButton(text=btn_text, callback_data=f"inlineselect:{game_id}:{r}:{c}"))
        inline_keyboard.append(row_buttons)

    draw_request = game.get("draw_request", {"white": False, "black": False})
    nicha_text = "Закончить ничьей"
    if draw_request.get("white") and draw_request.get("black"):
        nicha_text += f" {white_piece_btn} {black_piece_btn}"
    elif draw_request.get("white"):
        nicha_text += f" {white_piece_btn}"
    elif draw_request.get("black"):
        nicha_text += f" {black_piece_btn}"
    inline_keyboard.append([InlineKeyboardButton(text=nicha_text, callback_data=f"michainlain:{game_id}")])
    inline_keyboard.append([InlineKeyboardButton(text="Сдаться", callback_data=f"shahsurrenderinline:{game_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    current_turn_emoji = white_piece_html if turn == "white" else black_piece_html
    current_player_name = (game.get("creator_name") if turn == "white" else game.get("opponent_name")) or "Игрок"
    piece_count_text = f"{white_piece_html} : <b>{white_cnt}</b> | {black_piece_html} : <b>{black_cnt}</b>"

    await safe_inline_edit(
        inline_message_id=game["inline_message_id"],
        text=f"{current_turn_emoji} <b>Сейчас ход {_escape_html(current_player_name)}</b>\n{piece_count_text}",
        reply_markup=keyboard,
        parse_mode="HTML",
        callback_query=callback_query
    )
    _save_games_silent()