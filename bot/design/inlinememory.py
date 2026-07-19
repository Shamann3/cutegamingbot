# -*- coding: utf-8 -*-
"""
Inline-Мемори - быстрая, защищённая и самолечащаяся версия.
- Единый стиль и уважительные тексты.
- Быстрый UI: дифф-редактирование текста по inline_message_id + кеш.
- Антиспам: мягкий кулдаун по пользователю, идемпотентность join/open.
- Анти-фарм: защита пары «пригласитель-приглашённый».
- Надёжные локи на игру + мягкие тайм-ауты и самолечение зависаний.
- Ровно одна отложенная задача скрытия не-пары на игру.
- Аккуратное завершение: отмена фоновых задач, чистка кешей/локов.
"""

import asyncio, time, random, uuid, logging, re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Set

from aiogram import types
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

# === твоя среда (как у тебя) ===
from main import (
    inline_add_or_update_user_info, games_memory_inline, _format_hms, _pair_seconds_left,
    db, bot1, dp, get_current_time_formatted, timehistorygames, start_balance, create_user_link
)

# Эмодзи-пулы можно импортировать из общей игры (как у тебя)
try:
    from bot.games.memory import stenka, stenkakruto
except Exception:
    # Небольшой безопасный fallback, если импорт временно недоступен
    stenka = {
        1: ["🐶", "🐱", "🐾"],
        2: ["🍒", "🍓", "🍌"],
        3: ["🧋", "🧉", "🍗"],
        4: ["🌺", "🌷", "🌸"],
        5: ["💎", "💧", "💠"],
    }
    stenkakruto = {
        1: ["🐶","🐧","🐙","🐇","🦞","🦎","🐈‍⬛","🦋","🦜","🦢"],
        2: ["🍎","🍌","🍉","🍇","🍒","🍍","🍑","🍓","🫐","🥥"],
        3: ["🥪","🧋","🍕","🍔","🍟","🍱","🍦","🥨","🍪","🍗"],
        4: ["🌸","🌹","🪷","🌻","🌺","🌵","🌷","🌴","🍀","🌼"],
        5: ["💠","🥶","🩵","🧊","✈️","💎","🐬","📘","🎭","💧"],
    }

# ======================= НАСТРОЙКИ =======================
INLINE_USER_COOLDOWN   = 2.05    # антифлуд: минимум между кликами пользователя
INLINE_EDIT_RETRY      = 0.15    # базовая задержка перед повторной попыткой edit
INLINE_MISMATCH_DELAY  = 0.75    # сколько держим открытую не-пару
TOTAL_ROWS, TOTAL_COLS = 4, 5
TOTAL_CELLS            = TOTAL_ROWS * TOTAL_COLS

# мягкий тайм-аут на захват игрового лока (не блокируемся надолго)
LOCK_ACQUIRE_TIMEOUT   = 1.40
# случайный джиттер для снижения коллизий при ретраях
EDIT_JITTER_MAX        = 0.04
# лимит ретраев на правку текста
MAX_EDIT_RETRIES       = 3

DEBUG_INLINE_MEMORY    = True
TRACE                  = True

# ======================= ЛОГГЕР ===========================
LOGGER_NAME = "INLINE-MEMORY"
logger = logging.getLogger(LOGGER_NAME)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(h)
logger.setLevel(logging.DEBUG if (DEBUG_INLINE_MEMORY or TRACE) else logging.INFO)

def tlog(msg: str, *args):  # подробные шаги
    if TRACE:
        logger.debug(msg, *args)

def dlog(msg: str, *args):  # отладка
    if DEBUG_INLINE_MEMORY:
        logger.debug(msg, *args)

# ======================= ФРАЗЫ ============================
PHRASES: Dict[str, List[str]] = {
    "too_fast":       ["Не спеши - пауза 1 сек ⚡️", "Ещё миг… (1 сек)", "Тапы летят быстрее света 🙂"],
    "not_your_turn":  ["Сейчас ход соперника", "Подожди свой ход", "Стоп! Сейчас не твоя очередь."],
    "already_open":   ["Эта клетка уже открыта 👀", "Тут всё видно!", "Выбирай закрытую клетку 🙂"],
    "wait_lock":      ["Погоди секунду…", "Проверяю пару…", "Магия сверки…"],
    "pair_found":     ["Есть пара! 🚀", "Красиво!"],
    "pair_miss":      ["Не сходится ♨️", "Мимо… попробуй снова!", "Пара рядом, но не тут."],
    "invalid":        ["Некорректная клетка 🤔", "Туда нельзя.", "Ай-ай, не то поле."],
    "game_over":      ["Игра уже завершена.", "Партия окончена 🏁", "Поздно - конец игры."],
    "joined":         ["Ты в игре! 🎯", "Подключил тебя 🔌", "Добро пожаловать!"],
    "game_full":      ["Лобби уже полное.", "Двоих достаточно 👥", "Мест нет."],
    "start_only_creator": ["Только создатель может начать игру.", "Нужен автор лобби.", "Разрешение только у создателя."],
}
def _msg(key: str) -> str:
    return random.choice(PHRASES.get(key) or ["Окей."])

# ======================= СОСТОЯНИЯ ========================
inline_last_press_times: Dict[int, float] = {}       # антифлуд по пользователю
inline_game_locks: Dict[str, asyncio.Lock] = {}      # локи ходов
_inline_join_locks: Dict[str, asyncio.Lock] = {}     # локи на join

# ровно одна задача скрытия не-пары на игру
_inline_hide_tasks: Dict[str, asyncio.Task] = {}

# идемпотентность (на игра + пользователь)
_inflight_memory_joins: Set[Tuple[str, int]] = set()
_inflight_memory_opens: Set[Tuple[str, int]] = set()

# кеши UI (дифф правки текста) по inline_message_id
_inline_text_cache: Dict[str, str] = {}
_inline_edit_locks: Dict[str, asyncio.Lock] = {}     # сериализация edit_* для одного inline_message_id

def _inline_edit_lock_for(inline_message_id: str) -> asyncio.Lock:
    lk = _inline_edit_locks.get(inline_message_id)
    if lk is None:
        lk = asyncio.Lock()
        _inline_edit_locks[inline_message_id] = lk
    return lk

# ======================= УТИЛИТЫ ==========================
def _dedupe_preserve_order(items: List[int]) -> List[int]:
    seen = set(); out: List[int] = []
    for x in items:
        if x not in seen:
            seen.add(x); out.append(x)
    return out

def _debug_board(board: List[List[str]]) -> None:
    if not DEBUG_INLINE_MEMORY:
        return
    try:
        header = "    " + "   ".join(f"C{j}" for j in range(TOTAL_COLS))
        lines = [header] + [f"R{i}  " + "  ".join(row) for i, row in enumerate(board)]
        dlog("[BOARD]\n%s", "\n".join(lines))
        pairs: Dict[str, List[Tuple[int,int]]] = {}
        for i in range(TOTAL_ROWS):
            for j in range(TOTAL_COLS):
                pairs.setdefault(board[i][j], []).append((i, j))
        dlog("[PAIRS] %s", " | ".join(f"{k}:{v}" for k, v in pairs.items()))
    except Exception:
        pass

async def _acquire_with_timeout(lock: asyncio.Lock, timeout: float = LOCK_ACQUIRE_TIMEOUT) -> bool:
    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False

async def safe_answer(cb: CallbackQuery, text: str = "", show_alert: bool = False) -> None:
    try:
        if text:
            await cb.answer(text, show_alert=show_alert)
        else:
            await cb.answer()
    except Exception:
        pass

def fire_answer(cb: CallbackQuery, text: str = "", show_alert: bool = False) -> None:
    """
    AnswerCallbackQuery «в фоне», без ожидания ответа Telegram.

    По логам AnswerCallbackQuery стоит ~150мс сетевого RTT. Раньше он
    awaited-ился ПЕРЕД правкой доски, и EditMessageText уходил только после
    него - т.е. пользователь ждал два round-trip'а подряд вместо одного.
    Ждать ответ на answer нам незачем: крутилка на кнопке гаснет по факту
    доставки запроса. Теперь answer и edit летят параллельно.
    """
    try:
        asyncio.create_task(safe_answer(cb, text, show_alert))
    except Exception:
        pass

# ======== безопасные редакторы inline-сообщений ============
async def _edit_inline_text_core(inline_message_id: str, text: str,
                                 reply_markup: Optional[InlineKeyboardMarkup]) -> bool:
    async with _inline_edit_lock_for(inline_message_id):
        if _inline_text_cache.get(inline_message_id) == text:
            # только обновим клавиатуру
            try:
                await bot1.edit_message_reply_markup(
                    inline_message_id=inline_message_id,
                    reply_markup=reply_markup
                )
                return True
            except Exception:
                pass

        delay = INLINE_EDIT_RETRY + random.random() * EDIT_JITTER_MAX
        for _ in range(MAX_EDIT_RETRIES):
            try:
                await bot1.edit_message_text(
                    inline_message_id=inline_message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                _inline_text_cache[inline_message_id] = text
                return True
            except TelegramBadRequest as e:
                s = str(e).lower()
                if "message is not modified" in s:
                    _inline_text_cache[inline_message_id] = text
                    return True
                # нельзя редактировать - смысла ретраить нет
                if "message to edit not found" in s or "can't be edited" in s:
                    break
            except TelegramAPIError as e:
                ra = getattr(e, "retry_after", None)
                await asyncio.sleep(float(ra) + 0.03 if ra else delay)
                delay = min(delay * 2, 0.6)
            except Exception:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 0.6)
        return False

async def safe_edit_inline_text(inline_message_id: str, text: str,
                                reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
    ok = await _edit_inline_text_core(inline_message_id, text, reply_markup)
    if ok:
        return
    # fallback - попробуем хотя бы клавиатуру
    try:
        async with _inline_edit_lock_for(inline_message_id):
            await bot1.edit_message_reply_markup(
                inline_message_id=inline_message_id, reply_markup=reply_markup
            )
    except Exception:
        pass

# ======================= КНОПКИ/СЕТКА ======================
def _build_hidden_keyboard(game_id: str) -> InlineKeyboardMarkup:
    inline_keyboard: List[List[InlineKeyboardButton]] = []
    for i in range(TOTAL_ROWS):
        row = [
            InlineKeyboardButton(text=" ", callback_data=f"oinlinememory_open:{game_id}:{i}:{j}")
            for j in range(TOTAL_COLS)
        ]
        inline_keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def _build_keyboard_from_state(game: Dict) -> InlineKeyboardMarkup:
    kb: List[List[InlineKeyboardButton]] = []
    for i in range(TOTAL_ROWS):
        row: List[InlineKeyboardButton] = []
        for j in range(TOTAL_COLS):
            if (i, j) in game["revealed"]:
                row.append(InlineKeyboardButton(text=game["board"][i][j], callback_data="disabled"))
            else:
                row.append(game["keyboard"][i][j])
        kb.append(row)
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def _create_board(style: int) -> Optional[List[List[str]]]:
    emojis = stenkakruto.get(style, [])
    if not emojis:
        return None
    pool = (emojis * 2)[:TOTAL_CELLS]
    random.shuffle(pool)
    board = [pool[i:i+TOTAL_COLS] for i in range(0, TOTAL_CELLS, TOTAL_COLS)]
    _debug_board(board)
    return board

async def _build_turn_text(game: Dict, last_open_emoji: Optional[str] = None, found_pair: bool = False) -> str:
    style = game["style"]
    p1, p2, p3 = stenka[style]
    turn_id = game["turn"]
    # ленивый кеш линков
    try:
        name_link = game.setdefault("user_links", {}).get(turn_id)
        if not name_link:
            name_link = await create_user_link(
                turn_id,
                await db.get_firstname_by_user_id(turn_id),
                await db.get_username_by_user_id(turn_id)
            )
            game["user_links"][turn_id] = name_link
    except Exception:
        name_link = "Игрок"

    opp_id = next((x for x in game["participants"] if x != turn_id), turn_id)
    my_score = game["matches"].get(turn_id, {}).get("score", 0)
    opp_score = game["matches"].get(opp_id, {}).get("score", 0)
    icon_turn = p1 if turn_id == game["creator"] else p2
    last = f" {last_open_emoji}" if last_open_emoji else ""
    pair_line = "<blockquote>🚀 Найдена пара! Сделайте следующий ход.</blockquote>" if found_pair else ""
    return (
        f"{icon_turn} <b>Ход от : {name_link}</b>{last}\n"
        f"{p3} <b>Счёт : {my_score} | {opp_score}</b>\n"
        f"{pair_line}"
    )

# ======================= СЛУЖЕБНОЕ ========================
def _get_join_lock(game_id: str) -> asyncio.Lock:
    lk = _inline_join_locks.get(game_id)
    if lk is None:
        lk = asyncio.Lock()
        _inline_join_locks[game_id] = lk
    return lk

def _get_game_lock(game_id: str) -> asyncio.Lock:
    lk = inline_game_locks.get(game_id)
    if lk is None:
        lk = asyncio.Lock()
        inline_game_locks[game_id] = lk
    return lk

def _cancel_hide_task(game_id: str):
    t = _inline_hide_tasks.pop(game_id, None)
    if t and not t.done():
        t.cancel()

def _schedule_hide(game_id: str, coro_factory):
    _cancel_hide_task(game_id)
    _inline_hide_tasks[game_id] = asyncio.create_task(coro_factory(), name=f"hide:{game_id}")

def _save_inline():
    try:
        games_memory_inline.save()
    except Exception:
        pass

# ======================= СОЗДАНИЕ ==========================
@dp.callback_query(lambda c: c.data.startswith('1tmemory_create'))
async def inline_memory_create_game_callback(cb: CallbackQuery):
    try:
        creator_id = cb.from_user.id
        if await db.is_user_banned(creator_id):
            await cb.answer("❗️ Вы заблокированы в боте")
            return
        await safe_answer(cb, "🎲 Создаю лобби…")

        # callback_data может быть "1tmemory_create" ИЛИ "1tmemory_create:<uid>:<bet>"
        parts = cb.data.split(":")
        bet_amount = 0
        if len(parts) >= 3 and str(parts[2]).isdigit():
            bet_amount = int(parts[2])

        # проверка баланса под ставку
        if bet_amount > 0:
            try:
                bal = await db.get_user_balance(creator_id)
            except Exception:
                bal = 0
            if int(bal or 0) < bet_amount:
                await safe_answer(cb, "❌ Недостаточно средств для такой ставки.", True)
                return

        # профиль - мягко
        try:
            first_name = re.sub(r'[<>/{}"]', '', (cb.from_user.first_name or "Игрок"))
            username   = cb.from_user.username
            await inline_add_or_update_user_info(bot1, creator_id, first_name, username, db, start_balance)
        except Exception:
            pass

        game_style = random.randint(1, 5)
        board = await _create_board(game_style)
        if board is None:
            await safe_answer(cb, "💭 Ошибка создания игры.", True)
            return

        game_id = str(uuid.uuid4())
        inline_id = cb.inline_message_id  # якорь для правок
        if not inline_id:
            await safe_answer(cb, "💭 Нет inline_message_id для правки.", True)
            return

        # первичное состояние игры
        games_memory_inline[game_id] = {
            "creator": creator_id,
            "participants": [creator_id],
            "turn": creator_id,
            "board": board,
            "revealed": set(),
            "matches": {creator_id: {"score": 0, "turns": []}},
            "game_active": True,
            "player_moves": {creator_id: []},
            "move": {},
            "keyboard": [[InlineKeyboardButton(text=" ", callback_data=f"oinlinememory_open:{game_id}:{i}:{j}")
                         for j in range(TOTAL_COLS)] for i in range(TOTAL_ROWS)],
            "locked": False,
            "style": game_style,
            "creator_name": cb.from_user.first_name,
            "creator_username": cb.from_user.username,
            "opponent_name": None,
            "opponent_id": None,
            "opponent_username": None,
            "bet_amount": bet_amount,
            "inline_message_id": inline_id,
            "chat_id": 0,
            "user_links": {},   # кеш ссылок
        }
        inline_game_locks.setdefault(game_id, asyncio.Lock())
        _save_inline()

        bet_line = f"💰 Ставка : {bet_amount:,.0f} кут\n".replace(",", ".") if bet_amount > 0 else ""
        try:
            creator_link = await create_user_link(creator_id, games_memory_inline[game_id]["creator_name"], games_memory_inline[game_id]["creator_username"])
        except Exception:
            creator_link = games_memory_inline[game_id]["creator_name"] or "Игрок"
        game_emojis = stenka[games_memory_inline[game_id]["style"]]
        join_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Присоединиться", callback_data=f"inlinememoryjoin:{game_id}")]
        ])

        await safe_edit_inline_text(
            games_memory_inline[game_id]["inline_message_id"],
            f"{game_emojis[2]} <b>Играем в мемори\n{bet_line}{game_emojis[0]} - {creator_link}</b>",
            join_kb
        )
    except Exception as e:
        logger.exception("create error: %r", e)
        await safe_answer(cb, "💭 Техническая ошибка при создании лобби.", True)

# ======================= JOIN ===============================
@dp.callback_query(lambda c: c.data.startswith("inlinememoryjoin:"))
async def inline_memory_join_memory_game(cb: CallbackQuery):
    user_id = cb.from_user.id
    try:
        game_id = cb.data.split(":", 1)[1]
    except Exception:
        await safe_answer(cb, "⚠️ Неверные данные.", True)
        return
    if await db.is_user_banned(user_id):
        await cb.answer("❗️ Вы заблокированы в боте")
        return
    inflight_key = (game_id, user_id)
    if inflight_key in _inflight_memory_joins:
        await safe_answer(cb, "⏳ Обрабатываю присоединение…")
        return
    _inflight_memory_joins.add(inflight_key)

    try:
        lock = _get_join_lock(game_id)
        async with lock:
            game = games_memory_inline.get(game_id)
            if not game or not game.get("game_active"):
                await safe_answer(cb, _msg("game_over"))
                return

            # профиль - мягко
            try:
                first_name = re.sub(r'[<>/{}"]', '', (cb.from_user.first_name or "Игрок"))
                username = cb.from_user.username
                await inline_add_or_update_user_info(bot1, user_id, first_name, username, db, start_balance)
            except Exception:
                first_name = cb.from_user.first_name or "Игрок"
                username = cb.from_user.username

            if user_id == game.get("creator"):
                await safe_answer(cb, "❕ Вы создатель этой игры", True)
                return

            participants = _dedupe_preserve_order([int(x) for x in game.get("participants", [])])
            game["participants"] = participants
            if len(participants) >= 2:
                await safe_answer(cb, _msg("game_full"), True)
                return
            if user_id in participants:
                await safe_answer(cb, _msg("joined"))
                return

            # анти-фарм (всегда внутри лока)
            parts_set = set(participants)
            try:
                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    inviter_id = None
                if inviter_id and inviter_id in parts_set:
                    secs = await _pair_seconds_left(db, user_id, inviter_id, now=None)
                    if secs > 0:
                        await safe_answer(cb, f"💭 Нельзя присоединиться: в лобби ваш пригласитель.\n⏳ До снятия ограничения: {_format_hms(secs)}\n#AntiFarmSystem", True)
                        return

                invitees_here = await db.get_invitees_in(inviter_id=user_id, candidates=parts_set)
                if invitees_here:
                    min_secs = None
                    for inv_id in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, inv_id, now=None)
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)
                    if min_secs:
                        await safe_answer(cb, f"💭 Нельзя присоединиться: в лобби ваш приглашённый.\n⏳ До снятия ограничения: {_format_hms(min_secs)}\n#AntiFarmSystem", True)
                        return
            except Exception:
                await safe_answer(cb, "💭 Техническая ошибка #1212471", True)
                return

            # ставка - проверка
            bet_amount = int(game.get("bet_amount", 0) or 0)
            if bet_amount > 0:
                try:
                    bal = await db.get_user_balance(user_id)
                except Exception:
                    bal = 0
                enough = (bal is not None) and int(bal) >= bet_amount
                if not enough:
                    await safe_answer(cb, "💭 Недостаточно средств для участия в игре.", True)
                    return

            # бронь места без гонки
            if game.get("opponent_id") and game["opponent_id"] != user_id:
                await safe_answer(cb, "❗️ Место уже занято.", True)
                return

            # добавление
            game["participants"].append(user_id)
            game["participants"] = _dedupe_preserve_order(game["participants"])
            game.setdefault("player_moves", {})[user_id] = []
            game.setdefault("matches", {})[user_id] = {"score": 0, "turns": []}
            game["opponent_id"] = user_id
            game["opponent_name"] = first_name
            game["opponent_username"] = username

            # UI
            try:
                creator_link = await create_user_link(
                    game["creator"], game.get("creator_name"), game.get("creator_username")
                )
            except Exception:
                creator_link = game.get("creator_name") or "Игрок"

            try:
                participant_link = await create_user_link(user_id, first_name, username)
            except Exception:
                participant_link = first_name

            game_emojis = stenka[game["style"]]
            win_text = (
                f"\n💰 <b>Ставка : {bet_amount:,.0f} кут</b>".replace(",", ".")
                if bet_amount > 0 else ""
            )
            start_btn = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Начать игру", callback_data=f"sinlainmemorystart:{game_id}")]]
            )

            await safe_edit_inline_text(
                game["inline_message_id"],
                f"<b>{game_emojis[2]} Играем в мемори\n"
                f"{game_emojis[0]} - {creator_link}\n"
                f"{game_emojis[1]} - {participant_link}</b>{win_text}",
                start_btn
            )
            _save_inline()
            await safe_answer(cb, _msg("joined"))
    except Exception as e:
        logger.exception("join error: %r", e)
        await safe_answer(cb, "💭 Ошибка присоединения к лобби.", True)
    finally:
        _inflight_memory_joins.discard(inflight_key)

# ======================= СТАРТ =============================
@dp.callback_query(lambda c: c.data.startswith('sinlainmemorystart:'))
async def inline_memory_start_game_callback(cb: CallbackQuery):
    try:
        await safe_answer(cb, "Стартуем! 🎬")
        game_id = cb.data.split(':')[1]
        user_id = cb.from_user.id

        game = games_memory_inline.get(game_id)
        if not game:
            await safe_answer(cb, "💭 Эта игра больше не существует.", True)
            return
        if user_id != game['creator']:
            await safe_answer(cb, _msg("start_only_creator"), True)
            return
        if len(game['participants']) != 2:
            await safe_answer(cb, "💭 В игре должны участвовать 2 игрока.", True)
            return

        # проверка на ставку перед стартом (на всякий)
        bet_amount = int(game.get('bet_amount', 0) or 0)
        if bet_amount > 0:
            try:
                bal = await db.get_user_balance(user_id)
            except Exception:
                bal = 0
            if int(bal or 0) < bet_amount:
                await safe_answer(cb, "💭 Недостаточно средств для игры.", True)
                return

        game["game_active"] = True
        game["locked"] = False
        game["move"] = {}
        game.setdefault("revealed", set())
        # стартовая клавиатура
        kb = _build_hidden_keyboard(game_id)
        game["keyboard"] = kb.inline_keyboard  # синхрон хранимого состояния с кнопками
        game_emojis = stenka[game["style"]]
        await safe_edit_inline_text(
            game["inline_message_id"],
            f"<b>{game_emojis[2]} Находите парные эмодзи и получайте очки</b>",
            kb
        )
        _save_inline()
    except Exception as e:
        logger.exception("start error: %r", e)
        await safe_answer(cb, "💭 Ошибка запуска игры.", True)

# ======================= ХОД (КЛЕТКА) ======================
@dp.callback_query(lambda c: c.data.startswith("oinlinememory_open:"))
async def inline_memory_memory_open111(cb: CallbackQuery):
    uid = cb.from_user.id
    now = time.monotonic()
    if now - inline_last_press_times.get(uid, 0.0) < INLINE_USER_COOLDOWN:
        await safe_answer(cb, _msg("too_fast"))
        return
    inline_last_press_times[uid] = now

    # идемпотентность на игрока/игру
    try:
        _, game_id, r_s, c_s = cb.data.split(":")
        row, col = int(r_s), int(c_s)
    except Exception:
        await safe_answer(cb, _msg("invalid"), True)
        return

    inflight_key = (game_id, uid)
    if inflight_key in _inflight_memory_opens:
        await safe_answer(cb)  # уже в работе
        return
    _inflight_memory_opens.add(inflight_key)

    try:
        game = games_memory_inline.get(game_id)
        if not game or not game.get("game_active"):
            await safe_answer(cb, _msg("game_over"))
            return

        # профиль - мягко
        try:
            first_name = re.sub(r'[<>/{}"]', '', (cb.from_user.first_name or "Игрок"))
            username = cb.from_user.username
            await inline_add_or_update_user_info(bot1, uid, first_name, username, db, start_balance)
        except Exception:
            pass

        lock = _get_game_lock(game_id)
        # если уже «заблокировано» скрытием - мягко сообщим
        if lock.locked() and game.get("locked"):
            await safe_answer(cb, _msg("wait_lock"))
            return

        if not await _acquire_with_timeout(lock, LOCK_ACQUIRE_TIMEOUT):
            await safe_answer(cb)  # мягкий пропуск при перегрузе
            return

        try:
            game = games_memory_inline.get(game_id)
            if not game or not game.get("game_active"):
                await safe_answer(cb, _msg("game_over"))
                return

            if game.get("locked"):
                await safe_answer(cb, _msg("wait_lock"))
                return
            if uid != game["turn"]:
                await safe_answer(cb, _msg("not_your_turn"))
                return
            if not (0 <= row < TOTAL_ROWS and 0 <= col < TOTAL_COLS):
                await safe_answer(cb, _msg("invalid"))
                return
            if (row, col) in game.get("revealed", set()):
                await safe_answer(cb, _msg("already_open"))
                return

            # открыть клетку
            emoji = game["board"][row][col]
            game["keyboard"][row][col] = InlineKeyboardButton(text=emoji, callback_data="disabled")
            mv: List[Tuple[int, int]] = game["move"].setdefault(uid, [])
            if not mv or mv[-1] != (row, col):
                mv.append((row, col))

            # обновим текст/клавиатуру
            # ПЕРФ: раньше на парном ходе шло ДВА последовательных
            # EditMessageText - сначала «клетка открыта», сразу за ним
            # «найдена пара». Каждый - отдельный сетевой round-trip к Telegram
            # (~100-170мс по логам TG-API), итого ~300мс на один клик.
            # Второй кадр полностью перекрывает первый (та же доска + строка
            # про пару), поэтому промежуточный кадр не нужен: сверяем пару
            # ДО отрисовки и шлём один финальный edit.
            # Порядок безопасен: _build_turn_text/_build_keyboard_from_state
            # читают turn/matches/revealed и не смотрят на locked, а
            # _hide_pair_after_delay сначала спит и идёт через тот же
            # per-message лок правки.
            found_pair = False

            # если выбрано 2 клетки - сверяем
            if len(mv) % 2 == 0:
                c1, c2 = mv[-2], mv[-1]
                e1 = game["board"][c1[0]][c1[1]]
                e2 = game["board"][c2[0]][c2[1]]

                if e1 == e2:
                    found_pair = True
                    game.setdefault("revealed", set()).update([c1, c2])
                    game.setdefault("matches", {}).setdefault(uid, {"score": 0, "turns": []})
                    game["matches"][uid]["score"] += 1
                    fire_answer(cb, _msg("pair_found"))
                else:
                    # не-пара - блокируем и скрываем позже, передаём ход сопернику
                    game["locked"] = True
                    def _coro():
                        return _hide_pair_after_delay(game_id, uid, [c1, c2])
                    _schedule_hide(game_id, _coro)
                    fire_answer(cb, _msg("pair_miss"))
            else:
                # ВАЖНО: на «первой» клетке хода answerCallbackQuery не
                # отправлялся вообще (в логах на kind=first виден только
                # EditMessageText). Из-за этого крутилка на кнопке висела до
                # тайм-аута на стороне Telegram - визуально это и читалось как
                # «кнопка тупит», даже когда доска уже перерисовалась.
                fire_answer(cb)

            kb = _build_keyboard_from_state(game)
            txt = await _build_turn_text(game, last_open_emoji=emoji, found_pair=found_pair)
            await safe_edit_inline_text(game["inline_message_id"], txt, kb)

            _save_inline()

            # конец?
            if len(game.get("revealed", set())) == TOTAL_CELLS:
                await _inline_finish_game(game_id)
        finally:
            if lock.locked():
                lock.release()
    except Exception as e:
        logger.exception("open error: %r", e)
        await safe_answer(cb, "💭 Что-то пошло не так, уже чиним.", True)
    finally:
        _inflight_memory_opens.discard(inflight_key)

# ========== скрытие не-пары и передача хода ==========
async def _hide_pair_after_delay(game_id: str, uid: int, cells: List[Tuple[int, int]]) -> None:
    try:
        await asyncio.sleep(INLINE_MISMATCH_DELAY)
        game = games_memory_inline.get(game_id)
        if not game or not game.get("game_active"):
            return

        # закрываем только если клетки не оказались открытыми в составе пары
        for r, c in cells:
            if (r, c) not in game.get("revealed", set()):
                game["keyboard"][r][c] = InlineKeyboardButton(
                    text=" ", callback_data=f"oinlinememory_open:{game_id}:{r}:{c}"
                )
        # передаём ход
        parts = game["participants"]
        if len(parts) == 2:
            game["turn"] = parts[1] if parts[0] == uid else parts[0]
        game["locked"] = False

        await safe_edit_inline_text(
            game["inline_message_id"],
            await _build_turn_text(game),
            _build_keyboard_from_state(game)
        )
        _save_inline()
    except Exception:
        try:
            g = games_memory_inline.get(game_id)
            if g:
                g["locked"] = False
        except Exception:
            pass
    finally:
        _inline_hide_tasks.pop(game_id, None)

# ======================= ФИНИШ =============================
async def _inline_finish_game(game_id: str) -> None:
    try:
        game = games_memory_inline.get(game_id)
        if not game:
            return
        style = game["style"]
        p1, p2, p3 = stenka[style]

        scores_map = {u: game["matches"].get(u, {}).get("score", 0) for u in game["participants"]}
        scores = list(scores_map.values())
        # ничья 5/5 для 20 клеток (10 пар)
        if len(scores) == 2 and scores.count(5) == 2:
            text = (f"<b>{p3} Ничья! Оба игрока набрали одинаковое количество очков</b>\n"
                    f"<b>{p3} Счёт : 5 / 5</b>\n<b>Поздравляем с завершением игры!</b>")
            await safe_edit_inline_text(game["inline_message_id"], text, _build_keyboard_from_state(game))
            game["game_active"] = False
            _save_inline()
            return

        winner_id = max(scores_map, key=scores_map.get)
        loser_id  = next(x for x in game["participants"] if x != winner_id)
        try:
            winner_link = await create_user_link(
                winner_id, await db.get_firstname_by_user_id(winner_id), await db.get_username_by_user_id(winner_id)
            )
        except Exception:
            winner_link = "Победитель"

        icon = (p1 if winner_id == game["creator"] else p2)
        text = (f"<b>{icon} Победитель : {winner_link}</b>\n"
                f"<b>{p3} Счёт : {scores_map[winner_id]} / {scores_map.get(loser_id, 0)}</b>")

        # выплаты (честные, без комиссий)
        bet_amount = int(game.get("bet_amount", 0) or 0)
        if bet_amount > 0:
            try:
                loser_balance  = int(await db.get_user_balance(loser_id)  or 0)
                winner_balance = int(await db.get_user_balance(winner_id) or 0)
                if loser_balance >= bet_amount:
                    await db.update_user_balance(loser_id,  loser_balance  - bet_amount)
                    await db.update_user_balance(winner_id, winner_balance + bet_amount)
                    await db.touch_balance_last_active(winner_id , set_active_status=True)
                    await db.touch_balance_last_active(loser_id , set_active_status=True)
                    await db.cutehistory_plus(winner_id, bet_amount, "+ мемори инлайн")
                    await db.cutehistory_minus(loser_id, bet_amount, "- мемори инлайн")
                    text += f"\n<b>💰 Выигрыш {bet_amount:,.0f} кут</b>".replace(",", ".")
                else:
                    text += "\n<b>❌ У проигравшего нет средств для выплаты выигрыша.</b>"
            except Exception as e:
                logger.exception("payout error: %r", e)
                text += "\n<b>⚠️ Временная ошибка выплаты. Запишем результат и проверим позже.</b>"

        # статистика побед/поражений - мягко
        try:
            await db.update_user_wins(winner_id, 1, bot1, 0)
            await db.update_user_loose(loser_id, 1, bot1, 0)#
            await db.update_game_last_activity(winner_id)
            await db.update_game_last_activity(loser_id)
        except Exception:
            pass

        # «история игр» - мягко
        try:
            chat_id = game.get("chat_id", 0)
            chat_name = "1"
            last_open_time, data_open = await db.get_historygames_times(winner_id)
            now_ts = time.time()
            if last_open_time is None or data_open is None:
                last_open_time = get_current_time_formatted()
                data_open_ts = now_ts + timehistorygames
                user_name = await db.get_firstname_by_user_id(winner_id)
                await db.add_historygames(
                    chat_id, chat_name, winner_id, user_name,
                    last_open_time,
                    datetime.fromtimestamp(data_open_ts).strftime("%Y-%m-%d %H:%M:%S")
                )
            else:
                try:
                    data_open_ts = data_open if isinstance(data_open, (int, float)) else data_open.timestamp()
                except Exception:
                    data_open_ts = now_ts - 1
                last_open_time = get_current_time_formatted()
                data_open_ts = now_ts + timehistorygames
                await db.update_historygames(
                    winner_id, last_open_time,
                    datetime.fromtimestamp(data_open_ts).strftime("%Y-%m-%d %H:%M:%S")
                )
        except Exception:
            pass

        # кнопка «Создать новую»
        if bet_amount > 0:
            btn_create = InlineKeyboardButton(text="Создать новую игру", callback_data=f"1tmemory_create:{winner_id}:{bet_amount}")
        else:
            btn_create = InlineKeyboardButton(text="Создать новую игру", callback_data="1tmemory_create")
        kb = _build_keyboard_from_state(game)
        kb.inline_keyboard.append([btn_create])

        await safe_edit_inline_text(game["inline_message_id"], text, kb)
        game["game_active"] = False
        _save_inline()
    except Exception:
        # жёсткий fallback - просто пометим игру завершённой
        try:
            g = games_memory_inline.get(game_id)
            if g:
                g["game_active"] = False
                _save_inline()
        except Exception:
            pass
