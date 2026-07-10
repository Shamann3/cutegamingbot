# -*- coding: utf-8 -*-
"""
Мемори - быстрая, защищённая и самолечащаяся версия под высокую нагрузку.
- Уважительные тексты, без лишнего шума; единый стиль сообщений.
- Быстрый UI: дифф-редактирование, кеш текста/ссылок, сериализация перед сохранением.
- Антиспам: мягкий кулдаун по пользователю; идемпотентность на join/open.
- Анти-фарм: защита пары «пригласитель-приглашённый».
- Надёжные локи: тайм-аут на acquire + самолечение зависаний.
- Один pending-hide за промах; строгая отмена и очистка задач на финише.
- Watchdog: периодическая проверка и авто-восстановление состояния.
- Аккуратное завершение игры: отмена фоновых задач, снятие локов, чистка кэшей.
"""

import sys, asyncio, time, random, uuid, logging
from typing import Dict, Any, List, Tuple, Optional, Set

from aiogram import types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

# ==== твое окружение (как у тебя) ====
from main import (
    button_memory, _format_hms, _pair_seconds_left, games_memory, check_bet_and_set_item,
    db, bot1, dp, get_current_time_formatted, timehistorygames, pending_context, send_invoice_to_user
)
from bot.config.config import *          # TOKEN, donate_bet, timeoutdonate, ref_coin, etc.
from bot.design.buttons import *         # если у тебя тут есть кнопки
# ожидается наличие create_user_link(TG user_id, firstname, username) и get_bot_username_by_token(TOKEN)

# ======================== НАСТРОЙКИ ========================
DEBUG_MEMORY            = True
TRACE                   = True
PROFILE                 = False

TOTAL_ROWS, TOTAL_COLS  = 4, 5
TOTAL_CELLS             = TOTAL_ROWS * TOTAL_COLS

USER_CLICK_COOLDOWN     = 1.05
MISMATCH_HIDE_DELAY     = 1.50
BASE_RETRY_DELAY        = 0.08
MAX_RETRIES_EDIT        = 3
GAME_STUCK_TIMEOUT      = 3.5
HEAL_TICK_SEC           = 1.0
EDIT_JITTER_MAX         = 0.04
LOCK_ACQUIRE_TIMEOUT    = 1.4

# ======================== ЛОГГЕР ============================
LOGGER_NAME = "MEMORY"
logger = logging.getLogger(LOGGER_NAME)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s", "%H:%M:%S")
    handler.setFormatter(fmt)
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG if (DEBUG_MEMORY or TRACE) else logging.INFO)

def tlog(msg: str, *args):
    if TRACE:
        logger.debug(msg, *args)

def dlog(msg: str, *args):
    if DEBUG_MEMORY:
        logger.debug(msg, *args)

# ======================== ФРАЗЫ =============================
PHRASES: Dict[str, List[str]] = {
    "too_fast": [
        "Не спеши - пауза 1 сек ⚡️", "Ещё миг… (минимум 1 сек)", "Тапы летят быстрее света 🙂"
    ],
    "not_your_turn": [
        "Сейчас ход соперника", "Подожди свой ход", "Стоп! Сейчас не твоя очередь."
    ],
    "already_open": [
        "Эта клетка уже открыта 👀", "Тут всё видно!", "Выбирай закрытую клетку 🙂"
    ],
    # "wait_lock" - не используем всплывашку
    "invalid": [
        "Некорректная клетка 🤔", "Туда нельзя.", "Ай-ай, не то поле."
    ],
    "game_over": [
        "Игра уже завершена.", "Партия окончена 🏁", "Поздно - конец игры."
    ],
    "joined": [
        "Ты в игре! 🎯", "Подключил тебя 🔌", "Добро пожаловать!"
    ],
    "game_full": [
        "Лобби уже полное.", "Двоих достаточно 👥", "Мест нет."
    ],
    "start_only_creator": [
        "Только создатель может начать игру.", "Нужен автор лобби.", "Разрешение только у создателя."
    ],
}
def msg(key: str) -> str:
    arr = PHRASES.get(key) or ["Окей."]
    return random.choice(arr)

# ======================== ЭМОДЗИ ============================
stenka = {
    1: ["<tg-emoji emoji-id='5422864409879936922'>🐶</tg-emoji>", "<tg-emoji emoji-id='5425113993490494908'>🐱</tg-emoji>", "<tg-emoji emoji-id='5285241408469373771'>🐾</tg-emoji>"],
    2: ["<tg-emoji emoji-id='5422572287679298787'>🍒</tg-emoji>", "<tg-emoji emoji-id='5303252465494293177'>🍓</tg-emoji>", "<tg-emoji emoji-id='5422566068566653045'>🍌</tg-emoji>"],
    3: ["<tg-emoji emoji-id='5345887940121752931'>🧋</tg-emoji>", "<tg-emoji emoji-id='5269317271758600432'>🧉</tg-emoji>", "<tg-emoji emoji-id='5262706084434423407'>🍗</tg-emoji>"],
    4: ["<tg-emoji emoji-id='5346053240528071553'>🌺</tg-emoji>", "<tg-emoji emoji-id='5422567558920303881'>🌷</tg-emoji>", "<tg-emoji emoji-id='5422508378565933097'>🌸</tg-emoji>"],
    5: ["<tg-emoji emoji-id='5249219423268530320'>💎</tg-emoji>", "<tg-emoji emoji-id='5251301580463956522'>💧</tg-emoji>", "<tg-emoji emoji-id='5251693491934751684'>💠</tg-emoji>"],
    6: ["<tg-emoji emoji-id='5199790590279033017'>🌴</tg-emoji>", "<tg-emoji emoji-id='5251344521546965676'>🏄🏻‍♂️</tg-emoji>", "<tg-emoji emoji-id='5193171530279851660'>🦜</tg-emoji>"],  # базовая короткая версия
}
stenkakruto = {
    1: ["🐶","🐧","🐙","🐇","🦞","🦎","🐈‍⬛","🦋","🦜","🦢"],
    2: ["🍎","🍌","🍉","🍇","🍒","🍍","🍑","🍓","🫐","🥥"],
    3: ["🥪","🧋","🍕","🍔","🍟","🍱","🍦","🥨","🍪","🍗"],
    4: ["🌸","🌹","🪷","🌻","🌺","🌵","🌷","🌴","🍀","🌼"],
    5: ["💠","🥶","🩵","🧊","✈️","💎","🐬","📘","🎭","💧"],
    6: ["🏄🏻‍♂️","🦜","💙","🌴","🏝","🛹","🐬","🍍","✨","🌊"],
}


STITCH_STICKERS_6 = [
    "CAACAgIAAxkBAsaK6mmHi7qqDoO1LhnSuT_AUDG3wqOtAAKLdAACYsogSON20N0-SoC8OgQ"
]

# ======================== СОСТОЯНИЯ/КАШИ ===================
user_last_click: Dict[int, float] = {}

# игровые локи
game_locks: Dict[str, asyncio.Lock] = {}
join_locks: Dict[str, asyncio.Lock] = {}

# идемпотентность
_inflight_joins: Set[Tuple[str, int]] = set()
_inflight_opens: Set[Tuple[str, int]] = set()

# фоновые задачи
_watchdogs: Dict[str, asyncio.Task] = {}
_hide_tasks: Dict[str, asyncio.Task] = {}

# кеши UI
_last_text_cache: Dict[Tuple[int, int], str] = {}            # (chat_id, message_id) -> text
_edit_locks: Dict[Tuple[int, int], asyncio.Lock] = {}         # сериализация edit для одного сообщения

def _edit_lock_for(msg: types.Message) -> asyncio.Lock:
    key = (msg.chat.id, msg.message_id)
    lk = _edit_locks.get(key)
    if lk is None:
        lk = asyncio.Lock()
        _edit_locks[key] = lk
    return lk

def _get_join_lock(game_id: str) -> asyncio.Lock:
    lk = join_locks.get(game_id)
    if lk is None:
        lk = asyncio.Lock()
        join_locks[game_id] = lk
    return lk

# ======================== УТИЛИТЫ ===========================
async def check_balance_fast(user_id: int, bet: int) -> bool:
    try:
        bal = await db.get_user_balance(user_id)
        return bal is not None and int(bal) >= int(bet)
    except Exception:
        return False

def log_board_and_pairs(board: List[List[str]], game_id: Optional[str] = None):
    if not DEBUG_MEMORY:
        return
    header = "    " + "   ".join(f"C{j}" for j in range(TOTAL_COLS))
    lines = [header] + [f"R{i}  " + "  ".join(row) for i, row in enumerate(board)]
    dlog("[BOARD%s]\n%s", f' {game_id}' if game_id else "", "\n".join(lines))
    pairs: Dict[str, List[Tuple[int,int]]] = {}
    for i in range(TOTAL_ROWS):
        for j in range(TOTAL_COLS):
            pairs.setdefault(board[i][j], []).append((i, j))
    dlog("[PAIRS%s] %s", f' {game_id}' if game_id else "", " | ".join(f"{k}:{v}" for k, v in pairs.items()))

def log_state(game_id: str, g: Dict[str, Any], note: str = ""):
    if not DEBUG_MEMORY:
        return
    rev = sorted(list(g.get("revealed", set())))
    dlog("[STATE][%s] %s | ver=%s turn=%s locked=%s pending_hide=%s revealed=%s",
         game_id, note, g.get("state_ver"), g.get("turn"), g.get("locked"), g.get("pending_hide"), rev)

def log_move(game_id: str, user_id: int, row: int, col: int, kind: str):
    if TRACE:
        tlog("[MOVE][%s] uid=%s r=%d c=%d kind=%s", game_id, user_id, row, col, kind)

class LockTimeout(Exception):
    pass

async def acquire_with_timeout(lock: asyncio.Lock, timeout: float = LOCK_ACQUIRE_TIMEOUT) -> bool:
    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False

def _normalize_for_save(game: Dict[str, Any]) -> Dict[str, Any]:
    """Сериализация полей перед сохранением (set -> list), защита от мусора."""
    norm = dict(game)
    # множество в список
    if isinstance(norm.get("revealed"), set):
        norm["revealed"] = list(norm["revealed"])
    # pending_hide только валидного формата
    ph = norm.get("pending_hide")
    if ph and not isinstance(ph, dict):
        norm["pending_hide"] = None
    # user_links гарантированно dict
    if not isinstance(norm.get("user_links"), dict):
        norm["user_links"] = {}
    return norm

def _restore_after_load(game: Dict[str, Any]) -> Dict[str, Any]:
    """Восстановление типов после загрузки (list -> set)."""
    if isinstance(game.get("revealed"), list):
        game["revealed"] = set(tuple(x) for x in game["revealed"])
    elif "revealed" not in game or game["revealed"] is None:
        game["revealed"] = set()
    return game

def _save_games_memory(game_id: Optional[str] = None):
    """Безопасное сохранение: нормализация целого хранилища или одной игры."""
    try:
        if game_id:
            g = games_memory.get(game_id)
            if g is not None:
                games_memory[game_id] = _normalize_for_save(g)
        else:
            for gid, g in list(games_memory.items()):
                if g is not None:
                    games_memory[gid] = _normalize_for_save(g)
        games_memory.save()
        # после сохранения - восстановить типы в RAM
        if game_id:
            gg = games_memory.get(game_id)
            if gg is not None:
                games_memory[game_id] = _restore_after_load(gg)
        else:
            for gid, gg in list(games_memory.items()):
                if gg is not None:
                    games_memory[gid] = _restore_after_load(gg)
    except Exception as e:
        logger.exception("save normalize error: %r", e)

# ======== быстрый дифф-редактор с кешем текста ============
async def _edit_text_core(message: types.Message, text: str,
                          reply_markup: Optional[InlineKeyboardMarkup]) -> bool:
    # сериализуем правки на сообщение (мягкий backpressure)
    async with _edit_lock_for(message):
        cache_key = (message.chat.id, message.message_id)
        if _last_text_cache.get(cache_key) == text:
            try:
                await message.edit_reply_markup(reply_markup)
                return True
            except Exception:
                pass
        delay = BASE_RETRY_DELAY + random.random() * EDIT_JITTER_MAX
        for attempt in range(1, MAX_RETRIES_EDIT+1):
            try:
                await message.edit_text(
                    text, reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML, disable_web_page_preview=True
                )
                _last_text_cache[cache_key] = text
                return True
            except TelegramBadRequest as e:
                s = str(e).lower()
                if "message is not modified" in s:
                    _last_text_cache[cache_key] = text
                    return True
                if "message to edit not found" in s or "message can't be edited" in s:
                    break
            except TelegramAPIError as e:
                ra = getattr(e, "retry_after", None)
                await asyncio.sleep(float(ra) + 0.03 if ra else delay)
                delay = min(delay * 2, 0.6)
            except Exception:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 0.6)
        return False

async def safe_edit_text(message: types.Message, text: str,
                         reply_markup: Optional[InlineKeyboardMarkup]) -> None:
    ok = await _edit_text_core(message, text, reply_markup)
    if ok:
        return
    # пробуем хотя бы клавиатуру
    try:
        async with _edit_lock_for(message):
            await message.edit_reply_markup(reply_markup)
        return
    except Exception:
        pass
    # fallback: новый якорь
    try:
        async with _edit_lock_for(message):
            sent = await message.reply(
                text, reply_markup=reply_markup,
                parse_mode=ParseMode.HTML, disable_web_page_preview=True
            )
        # перенос якоря
        for gid, g in list(games_memory.items()):
            try:
                if g and g.get("message_id") == message.message_id and g.get("chat_id") == message.chat.id:
                    g["message_id"] = sent.message_id
                    g["state_ver"] = int(g.get("state_ver", 0)) + 1
                    _save_games_memory(gid)
                    _last_text_cache[(sent.chat.id, sent.message_id)] = text
                    dlog("[ANCHOR] %s moved: %s -> %s", gid, message.message_id, sent.message_id)
                    break
            except Exception:
                pass
    except Exception:
        pass

async def safe_answer(cb: CallbackQuery, text: str = "", show_alert: bool=False) -> None:
    if not text:
        try:
            await cb.answer()
        except Exception:
            pass
        return
    try:
        await cb.answer(text, show_alert=show_alert)
    except Exception:
        pass

# =================== HEAL / WATCHDOG =======================
async def heal_if_needed(game_id: str, message: Optional[types.Message] = None) -> None:
    """Самолечение зависаний и просроченных pending_hide (monotonic)."""
    try:
        g = games_memory.get(game_id)
        if not g or not g.get("game_active"):
            return
        now = time.monotonic()
        ph = g.get("pending_hide")

        # просроченное скрытие - просто откатываем
        if ph and now >= float(ph.get("unlock_at", 0.0)):
            cells: List[Tuple[int,int]] = ph.get("cells", [])
            for r, c in cells:
                if (r, c) not in g.get("revealed", set()):
                    g["texts"][r][c] = " "
            g["turn"] = ph.get("turn_next", g["turn"])
            g["pending_hide"] = None
            g["locked"] = False
            g["state_ver"] = int(g.get("state_ver", 0)) + 1
            _save_games_memory(game_id)
            log_state(game_id, g, "heal:pending_hide")

            if message:
                await safe_edit_text(
                    message,
                    await build_turn_full_text(g, None, False),
                    build_keyboard(game_id, g["texts"])
                )

        # зависший lock - принудительно снимаем
        if g.get("locked"):
            ts_un = float(ph.get("unlock_at", now)) if ph else 0.0
            if not ph or (now - ts_un) > GAME_STUCK_TIMEOUT:
                g["locked"] = False
                g["pending_hide"] = None
                g["state_ver"] = int(g.get("state_ver", 0)) + 1
                _save_games_memory(game_id)
                log_state(game_id, g, "heal:force-unlock")
    except Exception:
        pass

async def _watchdog_game(game_id: str):
    tlog("[WD][%s] start", game_id)
    try:
        while True:
            g = games_memory.get(game_id)
            if not g or not g.get("game_active"):
                tlog("[WD][%s] stop", game_id)
                break
            await heal_if_needed(game_id, None)
            await asyncio.sleep(HEAL_TICK_SEC)
    except asyncio.CancelledError:
        pass
    except Exception:
        await asyncio.sleep(HEAL_TICK_SEC)

def _ensure_watchdog(game_id: str):
    task = _watchdogs.get(game_id)
    if task is None or task.done():
        _watchdogs[game_id] = asyncio.create_task(_watchdog_game(game_id), name=f"wd:{game_id}")

def _cancel_watchdog(game_id: str):
    t = _watchdogs.pop(game_id, None)
    if t and not t.done():
        t.cancel()

# ======== управление задачей скрытия (ровно одна) =========
def _cancel_hide_task(game_id: str):
    t = _hide_tasks.pop(game_id, None)
    if t and not t.done():
        t.cancel()

def _schedule_hide(game_id: str, message: types.Message):
    _cancel_hide_task(game_id)
    _hide_tasks[game_id] = asyncio.create_task(_apply_pending_hide_after_delay(game_id, message))

# ======================== СЕТКА/КНОПКИ ======================
def build_keyboard(game_id: str, texts_state: List[List[str]]) -> InlineKeyboardMarkup:
    inline: List[List[InlineKeyboardButton]] = []
    for i in range(TOTAL_ROWS):
        row = []
        for j in range(TOTAL_COLS):
            txt = texts_state[i][j]
            cb = f"memory_open:{game_id}:{i}:{j}" if txt == " " else "disabled"  # «disabled» = безопасный no-op
            row.append(InlineKeyboardButton(text=txt, callback_data=cb))
        inline.append(row)
    return InlineKeyboardMarkup(inline_keyboard=inline)

async def create_board(style: int) -> Optional[List[List[str]]]:
    emojis = stenkakruto.get(style, [])
    if not emojis:
        return None
    pool = (emojis * 2)[:TOTAL_CELLS]
    random.shuffle(pool)
    board = [pool[i:i+TOTAL_COLS] for i in range(0, TOTAL_CELLS, TOTAL_COLS)]
    log_board_and_pairs(board)
    return board

# ======================== СОЗДАНИЕ ИГРЫ =====================
@dp.message()
async def memory(message: Message):
    try:
        if not message.text:
            return

        text_raw = message.text.strip()
        text = text_raw.lower()
        parts = text.split()
        if not parts:
            return

        bet_str: Optional[str] = None

        # ✅ строго:
        # "мемори"
        # "мемори <целое число>"
        if parts[0] == "мемори":
            if len(parts) == 1:
                bet_str = "0"
            elif len(parts) == 2:
                # строго целое число, никаких "10k", "10.5", "привет"
                if not parts[1].isdigit():
                    return
                bet_str = parts[1]
            else:
                return

        # ✅ строго:
        # "найди пару"
        # "найди пару <целое число>"
        # "найти пару"
        # "найти пару <целое число>"
        elif parts[0] in ("найди", "найти"):
            if len(parts) == 2 and parts[1] == "пару":
                bet_str = "0"
            elif len(parts) == 3 and parts[1] == "пару":
                if not parts[2].isdigit():
                    return
                bet_str = parts[2]
            else:
                return
        else:
            return

        # финальная страховка (быстро и без лишних ответов)
        if bet_str is None or not bet_str.isdigit():
            return

        bet = int(bet_str)
        creator_id = message.from_user.id

        if not await check_balance_fast(creator_id, bet):
            try:
                bot_username = await get_bot_username_by_token(TOKEN)
            except Exception:
                bot_username = "CuteGamingBot"

            stars = bet * donate_bet
            stars_str = str(int(stars)) if isinstance(stars, float) and float(stars).is_integer() else str(stars)

            pending_context[creator_id] = {"stars_amount": stars_str, "sent": False}
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"💫 Купить {format(bet, ',').replace(',', '.')} кут 💰",
                    url=f"https://t.me/{bot_username}?start=insert_{stars_str}_+"
                )],
                [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")],
            ])

            await message.reply(
                "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
                reply_markup=kb,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            asyncio.create_task(_send_invoice_later(message, creator_id, stars_str))
            return

        style = random.randint(1, 6)

        board = await create_board(style)
        if board is None:
            await message.reply("💭 Ошибка создания игры.", parse_mode="HTML")
            return

        creator_link = await create_user_link(
            creator_id,
            await db.get_firstname_by_user_id(creator_id),
            await db.get_username_by_user_id(creator_id),
        )

        game_id = str(uuid.uuid4())
        games_memory[game_id] = {
            "creator": creator_id,
            "bet": bet,
            "participants": [creator_id],
            "turn": creator_id,
            "board": board,
            "texts": [[" "]*TOTAL_COLS for _ in range(TOTAL_ROWS)],
            "revealed": set(),
            "matches": {creator_id: {"score": 0, "turns": []}},
            "player_moves": {creator_id: []},
            "move": {},
            "style": style,
            "game_active": True,
            "locked": False,
            "pending_hide": None,
            "state_ver": 1,
            "message_id": None,
            "chat_id": message.chat.id,
            "user_links": {creator_id: creator_link},
        }
        _save_games_memory(game_id)
        tlog("[NEW][%s] creator=%s bet=%s style=%s", game_id, creator_id, bet, style)

        if game_id not in game_locks:
            game_locks[game_id] = asyncio.Lock()
        _ensure_watchdog(game_id)

        # (опционально) стикер
        try:
            if style == 1:
                await message.answer_sticker("CAACAgIAAxkBAsadXGmHnoLlUxBlIqhuZgjr77u8Kh8CAAKsdQAC-y5BS_XewqDcR16TOgQ")
            elif style == 2:
                await message.answer_sticker("CAACAgIAAxkBAsaJzmmHiqYx9-3QPmeQpE4PvevYCEY5AAJfgwAC7LTASYKDZYudqj2nOgQ")
            elif style == 3:
                await message.answer_sticker("CAACAgIAAxkBAaxlLmdDBH4fe9JECEtVOa7SrMlyrxWeAAJnWgACxowZSs3z1NBpBhGzNgQ")
            elif style == 4:
                await message.answer_sticker("CAACAgIAAxkBAsaexmmHoCkvcpNF2ftdgjL0bWmaqKvaAALIewACd0MwSlBhJ1bBsjOhOgQ")
            elif style == 5:
                await message.answer_sticker("CAACAgIAAxkBAsaewWmHoCSzSCVZ6mhm1JPPajbvx3elAAKicQAC3J0wSsBrQFjG4l7WOgQ")
            elif style == 6:
                await message.answer_sticker(random.choice(STITCH_STICKERS_6))
        except Exception:
            pass

        join_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Присоединиться", callback_data=f"memoryjoin:{game_id}")]
        ])
        button_memory[game_id] = {}

        game_emojis = stenka[style]
        sent = await message.reply(
            f"{game_emojis[2]} <b>Играем в мемори\n{game_emojis[0]} - {creator_link}</b>",
            reply_markup=join_kb,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        games_memory[game_id]["message_id"] = sent.message_id
        _save_games_memory(game_id)
        log_state(game_id, games_memory[game_id], "created")

    except Exception as e:
        logger.exception("create error: %r", e)

async def _send_invoice_later(message: Message, user_id: int, stars_amount: str):
    try:
        await asyncio.sleep(timeoutdonate)
        ctx = pending_context.get(user_id)
        if ctx and not ctx.get("sent"):
            invoice_message = await send_invoice_to_user(message, stars_amount)
            pending_context[user_id]["manual_message_id"] = invoice_message.message_id
    except Exception:
        pass

# ======================== ПРИСОЕДИНЕНИЕ ====================
@dp.callback_query(lambda c: c.data.startswith("memoryjoin:"))
async def memory_join_game(cb: CallbackQuery):
    user_id = cb.from_user.id
    try:
        game_id = cb.data.split(":", 1)[1]
    except Exception:
        await safe_answer(cb, "⚠️ Неверные данные.", True);
        return

    key = (game_id, user_id)
    if key in _inflight_joins:
        await safe_answer(cb);
        return
    _inflight_joins.add(key)

    try:
        await heal_if_needed(game_id, cb.message)
        lock = _get_join_lock(game_id)
        async with lock:
            g = games_memory.get(game_id)
            if not g or not g.get("game_active"):
                await safe_answer(cb, "💭 Эта игра больше не существует.", True);
                return

            if await db.is_user_banned(user_id):
                await safe_answer(cb, "❗️ Вы заблокированы в боте", True);
                return

            participants = list(dict.fromkeys([int(x) for x in g.get("participants", [])]))
            g["participants"] = participants

            if user_id == g.get("creator"):
                await safe_answer(cb, "❕ Вы создатель этой игры", True);
                return
            if len(participants) >= 2:
                await safe_answer(cb, msg("game_full"), True);
                return

            bet = int(g.get("bet", 0) or 0)
            if bet > 0:
                try:
                    bal = await db.get_user_balance(user_id)
                    if not (bal is not None and int(bal) >= bet):
                        await safe_answer(cb, "💭 Недостаточно средств для участия в игре.", True);
                        return
                except Exception:
                    await safe_answer(cb, "💭 Недостаточно средств для участия в игре.", True);
                    return

            if user_id in participants:
                await safe_answer(cb, msg("joined"));
                return

            # анти-фарм
            parts_set = set(participants)
            try:
                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    inviter_id = None
                if inviter_id and inviter_id in parts_set:
                    secs = await _pair_seconds_left(db, user_id, inviter_id, now=None)
                    if secs > 0:
                        await safe_answer(cb, f"💭 Нельзя присоединиться: в лобби ваш пригласитель.\n⏳ До снятия ограничения: {_format_hms(secs)}\n#AntiFarmSystem", True);
                        return
                invitees_here = await db.get_invitees_in(inviter_id=user_id, candidates=parts_set)
                if invitees_here:
                    min_secs = None
                    for inv_id in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, inv_id, now=None)
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)
                    if min_secs:
                        await safe_answer(cb, f"💭 Нельзя присоединиться: в лобби ваш приглашённый.\n⏳ До снятия ограничения: {_format_hms(min_secs)}\n#AntiFarmSystem", True);
                        return
            except Exception:
                await safe_answer(cb, "💭 Техническая ошибка #1212471", True);
                return

            # атомарно
            if len(g["participants"]) >= 2:
                await safe_answer(cb, msg("game_full"), True);
                return

            g["participants"].append(user_id)
            g["participants"] = list(dict.fromkeys(g["participants"]))
            g.setdefault("player_moves", {})[user_id] = []
            g.setdefault("matches", {})[user_id] = {"score": 0, "turns": []}
            # кеш ссылки участника
            joiner_link = await create_user_link(
                user_id,
                await db.get_firstname_by_user_id(user_id),
                await db.get_username_by_user_id(user_id),
            )
            g.setdefault("user_links", {})[user_id] = joiner_link

            g["state_ver"] = int(g.get("state_ver", 0)) + 1
            _save_games_memory(game_id)

            creator_link = g.get("user_links", {}).get(g["creator"], "Игрок")
            participant_link = joiner_link
            game_emojis = stenka[g["style"]]
            start_kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Начать игру", callback_data=f"memorystart:{game_id}")]]
            )
            win_text = f"\n<tg-emoji emoji-id='5294026527850132517'>💰</tg-emoji> <b>Выигрыш {format(g['bet'], ',').replace(',', '.')} кут</b>" if g['bet'] > 0 else ""
            txt = (f"<b>{game_emojis[2]} Играем в мемори\n"
                   f"{game_emojis[0]} - {creator_link}\n"
                   f"{game_emojis[1]} - {participant_link}</b>{win_text}")

            await safe_edit_text(cb.message, txt, start_kb)
            log_state(game_id, g, "joined")
            await safe_answer(cb, msg("joined"))
    except Exception as e:
        logger.exception("join error: %r", e)
        await safe_answer(cb, "💭 Ошибка присоединения. Повторите позже.", True)
    finally:
        _inflight_joins.discard(key)

# ======================== СТАРТ ИГРЫ =======================
@dp.callback_query(lambda c: c.data.startswith('memorystart:'))
async def memory_start_game_callback(cb: CallbackQuery):
    try:
        await safe_answer(cb, "Стартуем! 🎬")
        game_id = cb.data.split(':')[1]
        user_id = cb.from_user.id

        await heal_if_needed(game_id, cb.message)
        g = games_memory.get(game_id)
        if not g:
            await safe_answer(cb, "💭 Эта игра больше не существует.", True);
            return
        if user_id != g['creator']:
            await safe_answer(cb, msg("start_only_creator"), True);
            return
        if len(g['participants']) != 2:
            await safe_answer(cb, "💭 В игре должны участвовать 2 игрока.", True);
            return

        g["game_active"] = True
        g["pending_hide"] = None
        g["locked"] = False
        g["state_ver"] = int(g.get("state_ver", 0)) + 1
        kb = build_keyboard(game_id, g["texts"])
        game_emojis = stenka[g["style"]]
        await safe_edit_text(
            cb.message,
            f"<b>{game_emojis[2]} Находите парные эмодзи и получайте очки</b>",
            kb
        )
        _save_games_memory(game_id)
        log_state(game_id, g, "started")
        _ensure_watchdog(game_id)
    except Exception as e:
        logger.exception("start error: %r", e)
        await safe_answer(cb, "💭 Ошибка запуска. Повторите позже.", True)

# ======================== ХОД (КЛИК) =======================
@dp.callback_query(lambda c: c.data.startswith("memory_open:"))
async def memory_open(cb: CallbackQuery):
    user_id = cb.from_user.id
    now = time.monotonic()

    if now - user_last_click.get(user_id, 0.0) < USER_CLICK_COOLDOWN:
        await safe_answer(cb, msg("too_fast"), False);
        return
    user_last_click[user_id] = now

    try:
        _, game_id, r_s, c_s = cb.data.split(":")
        row, col = int(r_s), int(c_s)
    except Exception:
        await safe_answer(cb, msg("invalid"), True);
        return

    key = (game_id, user_id)
    if key in _inflight_opens:
        await safe_answer(cb);
        return
    _inflight_opens.add(key)

    try:
        await heal_if_needed(game_id, cb.message)

        g = games_memory.get(game_id)
        if not g or not g.get("game_active"):
            await safe_answer(cb, msg("game_over"), True);
            return

        lock = game_locks.setdefault(game_id, asyncio.Lock())
        if not await acquire_with_timeout(lock, LOCK_ACQUIRE_TIMEOUT):
            await heal_if_needed(game_id, cb.message)
            g2 = games_memory.get(game_id)
            if g2 and g2.get("locked") and not g2.get("pending_hide"):
                g2["locked"] = False
                g2["state_ver"] = int(g2.get("state_ver", 0)) + 1
                _save_games_memory(game_id)
            await safe_answer(cb);
            return

        try:
            g = games_memory.get(game_id)
            if not g or not g.get("game_active"):
                await safe_answer(cb, msg("game_over"), True);
                return

            await heal_if_needed(game_id, cb.message)
            if g.get("locked"):
                await safe_answer(cb);
                return

            if user_id != g["turn"]:
                await safe_answer(cb, msg("not_your_turn"), False);
                return
            if not (0 <= row < TOTAL_ROWS and 0 <= col < TOTAL_COLS):
                await safe_answer(cb, msg("invalid"), True);
                return
            if (row, col) in g.get("revealed", set()):
                await safe_answer(cb, msg("already_open"), False);
                return

            # открываем клетку
            emoji = g["board"][row][col]
            g["texts"][row][col] = emoji
            mv: List[Tuple[int, int]] = g["move"].setdefault(user_id, [])
            if not mv or mv[-1] != (row, col):
                mv.append((row, col))
                g["state_ver"] = int(g.get("state_ver", 0)) + 1
            log_move(game_id, user_id, row, col, "first" if len(mv)%2==1 else "second")

            await safe_edit_text(
                cb.message,
                await build_turn_full_text(g, last_open_emoji=emoji, found_pair=False),
                build_keyboard(game_id, g["texts"])
            )

            # пара/промах
            if len(mv) % 2 == 0:
                c1, c2 = mv[-2], mv[-1]
                e1 = g["board"][c1[0]][c1[1]]
                e2 = g["board"][c2[0]][c2[1]]

                if e1 == e2:
                    g.setdefault("revealed", set()).update([c1, c2])
                    g.setdefault("matches", {}).setdefault(user_id, {"score": 0, "turns": []})
                    g["matches"][user_id]["score"] += 1
                    g["state_ver"] = int(g.get("state_ver", 0)) + 1
                    _save_games_memory(game_id)

                    await safe_edit_text(
                        cb.message,
                        await build_turn_full_text(g, last_open_emoji=emoji, found_pair=True),
                        build_keyboard(game_id, g["texts"])
                    )
                    log_move(game_id, user_id, row, col, "pair")
                else:
                    # промах → мягкая блокировка и отложенное скрытие
                    g["locked"] = True
                    opp = next((x for x in g["participants"] if x != user_id), user_id)
                    g["pending_hide"] = {
                        "cells": [c1, c2],
                        "unlock_at": time.monotonic() + MISMATCH_HIDE_DELAY,
                        "turn_next": opp,
                        "ver": int(g.get("state_ver", 0)) + 1
                    }
                    g["state_ver"] = int(g.get("state_ver", 0)) + 1
                    _save_games_memory(game_id)

                    log_move(game_id, user_id, row, col, "miss")
                    _schedule_hide(game_id, cb.message)

            _save_games_memory(game_id)

            if len(g.get("revealed", set())) == TOTAL_CELLS:
                await finish_game(cb.message, game_id);
                return

        finally:
            if lock.locked():
                lock.release()

        await heal_if_needed(game_id, cb.message)
    except Exception as e:
        logger.exception("open error: %r", e)
        try:
            await safe_answer(cb, "💭 Что-то пошло не так, уже чиним.", True)
        except Exception:
            pass
    finally:
        _inflight_opens.discard(key)

# ====== скрытие после задержки и передача хода ======
async def _apply_pending_hide_after_delay(game_id: str, message: types.Message) -> None:
    try:
        await asyncio.sleep(MISMATCH_HIDE_DELAY)
        g = games_memory.get(game_id)
        if not g or not g.get("game_active"):
            return
        ph = g.get("pending_hide")
        if not ph:
            return
        if ph.get("ver") is not None and ph["ver"] < g.get("state_ver", 0):
            return  # устарело

        # просто закрываем обе клетки обратно
        for r, c in ph.get("cells", []):
            if (r, c) not in g.get("revealed", set()):
                g["texts"][r][c] = " "
                log_move(game_id, g.get("turn", 0), r, c, "hide")

        g["turn"] = ph.get("turn_next", g["turn"])
        g["pending_hide"] = None
        g["locked"] = False
        g["state_ver"] = int(g.get("state_ver", 0)) + 1
        _save_games_memory(game_id)
        log_state(game_id, g, "apply_pending_hide")

        await safe_edit_text(
            message,
            await build_turn_full_text(g, last_open_emoji=None, found_pair=False),
            build_keyboard(game_id, g["texts"])
        )
    except Exception:
        try:
            gg = games_memory.get(game_id)
            if gg:
                gg["locked"] = False
                gg["pending_hide"] = None
                gg["state_ver"] = int(gg.get("state_ver", 0)) + 1
                _save_games_memory(game_id)
        except Exception:
            pass
    finally:
        _hide_tasks.pop(game_id, None)

# ==================== ТЕКСТ ХОДА ===========================
async def build_turn_full_text(g: Dict[str, Any],
                               last_open_emoji: Optional[str] = None,
                               found_pair: bool = False) -> str:
    style = g["style"]
    p1, p2, p3 = stenka[style]
    turn_id = g["turn"]

    name_link = g.get("user_links", {}).get(turn_id)
    if not name_link:
        name_link = await create_user_link(
            turn_id, await db.get_firstname_by_user_id(turn_id), await db.get_username_by_user_id(turn_id)
        )
        g.setdefault("user_links", {})[turn_id] = name_link

    opp_id = next((x for x in g["participants"] if x != turn_id), turn_id)
    my_score = g["matches"].get(turn_id, {}).get("score", 0)
    opp_score = g["matches"].get(opp_id, {}).get("score", 0)
    score = f"{my_score} | {opp_score}"
    icon_turn = p1 if turn_id == g["creator"] else p2
    suffix = "<blockquote>🚀 Найдена пара! Сделайте следующий ход.</blockquote>" if found_pair else ""
    last_emo = f" {last_open_emoji}" if last_open_emoji else ""
    return f"{icon_turn} <b>Ход от : {name_link}</b>{last_emo}\n{p3} <b>Счёт : {score}</b>\n{suffix}"

# ==================== ФИНИШ И ОЧИСТКА ======================
def _cleanup_runtime_for_game(game_id: str, g: Optional[Dict[str, Any]]):
    """Жёсткая очистка всего, что могло остаться после игры."""
    _cancel_hide_task(game_id)
    _cancel_watchdog(game_id)
    # чистим локи
    game_locks.pop(game_id, None)
    join_locks.pop(game_id, None)
    # чистим inflight
    for key in list(_inflight_joins):
        if key[0] == game_id:
            _inflight_joins.discard(key)
    for key in list(_inflight_opens):
        if key[0] == game_id:
            _inflight_opens.discard(key)
    # удаляем якорь-кеши
    try:
        chat_id = g.get("chat_id") if g else None
        message_id = g.get("message_id") if g else None
        if chat_id and message_id:
            _last_text_cache.pop((chat_id, message_id), None)
            _edit_locks.pop((chat_id, message_id), None)
    except Exception:
        pass
    # кнопки
    try:
        button_memory.pop(game_id, None)
    except Exception:
        pass

async def finish_game(message: types.Message, game_id: str) -> None:
    try:
        g = games_memory.get(game_id)
        if not g:
            return

        user_scores = {u: g["matches"].get(u, {}).get("score", 0) for u in g["participants"]}
        style = g["style"]; p1, p2, p3 = stenka[style]
        vals = list(user_scores.values())

        # полный разбор 10 пар: ничья 5/5
        if len(vals) == 2 and vals.count(5) == 2:
            txt = (f"<b>{p3} Ничья! Оба игрока набрали одинаковое количество очков</b>\n"
                   f"<b>{p3} Счёт : 5 / 5</b>\n"
                   f"<b>Поздравляем с завершением игры!</b>")
            await safe_edit_text(message, txt, build_keyboard(game_id, g["texts"]))
            g["game_active"] = False
            g["pending_hide"] = None
            g["locked"] = False
            g["state_ver"] = int(g.get("state_ver", 0)) + 1
            _save_games_memory(game_id)
            log_state(game_id, g, "finish:draw")
            _cleanup_runtime_for_game(game_id, g)
            return

        winner = max(user_scores, key=user_scores.get)
        opponent_id = next((x for x in g["participants"] if x != winner), winner)
        # ссылка победителя из кеша
        winner_link = g.get("user_links", {}).get(winner)
        if not winner_link:
            winner_link = await create_user_link(
                winner, await db.get_firstname_by_user_id(winner), await db.get_username_by_user_id(winner)
            )
            g.setdefault("user_links", {})[winner] = winner_link

        bet = int(g['bet'])
        txt = (f"<b>{(p1 if winner == g['creator'] else p2)} Победитель : {winner_link}</b>\n"
               f"<b>{p3} Счёт : {user_scores[winner]} / {user_scores.get(opponent_id, 0)}</b>")
        txt += (f"\n<b><tg-emoji emoji-id='5294026527850132517'>💰</tg-emoji> Выигрыш {format(bet, ',').replace(',', '.')} кут</b>"
                if bet > 0 else "\n<b>Поздравляем с победой!</b>")

        # выплаты
        try:
            cur_w = await db.get_user_balance(winner) or 0
            cur_l = await db.get_user_balance(opponent_id) or 0
            await db.update_user_balance(opponent_id, round(cur_l - bet))
            await db.update_user_balance(winner, round(cur_w + bet))
            await db.cutehistory_plus(winner, bet, "+ мемори")
            await db.cutehistory_minus(opponent_id, bet, "- мемори")
            await db.update_user_winamount(winner, bet)#
            await db.update_user_wins(winner, 1, bot1, ref_coin)
            await db.update_user_loose(opponent_id, 1, bot1, ref_coin)#
            await db.update_game_last_activity(winner)
            await db.update_game_last_activity(opponent_id)
            await check_bet_and_set_item(winner, bet)
            await db.touch_balance_last_active(winner , set_active_status=True)
            await db.touch_balance_last_active(opponent_id , set_active_status=True)
        except Exception as e:
            logger.exception("payout error: %r", e)

        # бонусная «история игр»
        try:
            winner_id = winner
            chat_id = g.get("chat_id", message.chat.id)
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
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data_open_ts))
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
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data_open_ts))
                )
        except Exception:
            pass

        await safe_edit_text(message, txt, build_keyboard(game_id, g["texts"]))
        g["game_active"] = False
        g["pending_hide"] = None
        g["locked"] = False
        g["state_ver"] = int(g.get("state_ver", 0)) + 1
        _save_games_memory(game_id)
        log_state(game_id, g, "finish")
        _cleanup_runtime_for_game(game_id, g)
    except Exception as e:
        logger.exception("finish error: %r", e)
