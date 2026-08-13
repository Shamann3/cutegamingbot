# -*- coding: utf-8 -*-
"""
Кости - ультра-защищённая версия:
- Чёткая стейт-машина: CREATED -> STARTED -> ROLLING -> SETTLING -> SETTLED.
- Пер-игровой asyncio.Lock + анти-дребезг на join/roll.
- Идемпотентность: участники/роллы/расчёты не дублируются.
- Сага расчётов: сначала дебет лузеров (с откатом при сбое), затем один кредит победителю.
- Анти-реф защита и финальные мягкие проверки балансов.
- Умное редактирование + flood control с понятным сообщением о задержке.
- Совместимо с Python 3.9 и твоими объектами/именами.
"""

from typing import Optional, Dict, Set, Tuple, List
import asyncio
import random
import re
import time
import html
import json
import hashlib
from datetime import datetime

from aiogram import types, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

# --- твои реальные объекты / конфиг ---
from bot.games.group_only import reject_if_private_game
from main import (
    bot1, dp, db,
    gameskosti, button_kosti, temp_kosti_data,
    get_current_time_formatted, timehistorygames,
    send_invoice_to_user, pending_context,
    _pair_seconds_left, _format_hms,LazyGameStore
)
from bot.config.config import TOKEN, donate_bet, timeoutdonate, ref_coin

# ====== Константы ======
MAX_PARTICIPANTS = 12
DICE_MIN, DICE_MAX = 1, 12
FLOOD_EDIT_MAX_RETRIES = 4
FLOOD_SLEEP_BUFFER_SEC = 1.0

STATE_CREATED  = "CREATED"
STATE_STARTED  = "STARTED"
STATE_ROLLING  = "ROLLING"
STATE_SETTLING = "SETTLING"
STATE_SETTLED  = "SETTLED"

# ====== Локальные защиты ======
# asyncio.Lock нельзя класть в LazyGameStore/Redis — после рестарта ломается.
_join_locks: Dict[int, asyncio.Lock] = {}
_game_locks: Dict[int, asyncio.Lock] = {}
_inflight_joins: Set[Tuple[int, int]] = set()  # (game_id, user_id)
_inflight_rolls: Set[Tuple[int, int]] = set()  # (game_id, user_id)

def _get_lock(bucket: Dict[int, asyncio.Lock], key: int) -> asyncio.Lock:
    lock = bucket.get(key)
    if not isinstance(lock, asyncio.Lock):
        lock = asyncio.Lock()
        bucket[key] = lock
    return lock

def _dedupe_preserve_order(items: List[int]) -> List[int]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

# ====== Умное редактирование + flood control ======
def _kb_signature(kb: Optional[InlineKeyboardMarkup]) -> str:
    if not kb:
        return "∅"
    rows = []
    for row in kb.inline_keyboard:
        r = []
        for btn in row:
            r.append((
                getattr(btn, "text", None),
                getattr(btn, "callback_data", None),
                getattr(btn, "url", None),
                getattr(btn, "switch_inline_query", None),
                getattr(btn, "switch_inline_query_current_chat", None),
            ))
        rows.append(r)
    raw = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _is_flood_error(exc: Exception) -> bool:
    if isinstance(exc, TelegramRetryAfter):
        return True
    low = str(exc).lower()
    return (
        "flood control" in low
        or "too many requests" in low
        or "retry after" in low
        or "retry in" in low
    )

def _extract_retry_after(exc: Exception) -> int:
    ra = getattr(exc, "retry_after", None)
    if ra is not None:
        try:
            return max(1, int(float(ra)))
        except Exception:
            pass
    for pattern in (r"retry in (\d+)", r"retry after (\d+)"):
        m = re.search(pattern, str(exc), re.IGNORECASE)
        if m:
            return max(1, int(m.group(1)))
    return 5

def _format_flood_wait_text(seconds: int) -> str:
    s = max(1, int(seconds))
    return (
        "<tg-emoji emoji-id='5213452215527677338'>⏳</tg-emoji> "
        "<b>Telegram задерживает игру</b>\n"
        "Мессенджер временно ограничил обновления - "
        f"подождите <b>{s} сек.</b>\n"
        "<i>Игра продолжится автоматически…</i>"
    )

async def _clear_flood_notice(game: dict) -> None:
    notice_id = game.pop("_flood_notice_msg_id", None)
    chat_id = game.get("chat_id")
    if notice_id and chat_id:
        try:
            await bot1.delete_message(chat_id, notice_id)
        except Exception:
            pass

async def _show_flood_notice(
    game: dict,
    *,
    chat_id: int,
    message_id: int,
    wait_sec: int,
    reply_markup: Optional[InlineKeyboardMarkup],
    parse_mode: str,
    disable_web_page_preview: bool,
) -> None:
    notice_text = _format_flood_wait_text(wait_sec)
    try:
        await bot1.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=notice_text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
        return
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
    except Exception as e:
        if not _is_flood_error(e):
            print(f"[KOSTI][flood notice edit] {e}")

    try:
        sent = await bot1.send_message(
            chat_id,
            notice_text,
            reply_to_message_id=message_id,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
        game["_flood_notice_msg_id"] = sent.message_id
    except Exception as e:
        print(f"[KOSTI][flood notice send] {e}")

async def safe_edit_text_and_markup(
    game: dict,
    *,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup],
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> bool:
    """Редактирует сообщение с дедупликацией и обработкой flood control."""
    last = game.setdefault("_last_view", {"text": None, "kb_sig": None})
    kb_sig = _kb_signature(reply_markup)

    if last["text"] == text and last["kb_sig"] == kb_sig:
        return False

    text_changed = last["text"] != text

    for attempt in range(1, FLOOD_EDIT_MAX_RETRIES + 1):
        try:
            if text_changed:
                await bot1.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
            else:
                await bot1.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup,
                )
            await _clear_flood_notice(game)
            last["text"] = text
            last["kb_sig"] = kb_sig
            return True
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return False
            raise
        except Exception as e:
            if not _is_flood_error(e):
                raise

            wait_sec = _extract_retry_after(e)
            print(
                f"[KOSTI][flood] chat={chat_id} msg={message_id} "
                f"wait={wait_sec}s attempt={attempt}/{FLOOD_EDIT_MAX_RETRIES}"
            )
            await _show_flood_notice(
                game,
                chat_id=chat_id,
                message_id=message_id,
                wait_sec=wait_sec,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )

            if attempt >= FLOOD_EDIT_MAX_RETRIES:
                print(f"[KOSTI][flood] не удалось обновить после {attempt} попыток")
                return False

            await asyncio.sleep(wait_sec + FLOOD_SLEEP_BUFFER_SEC)

    return False

async def _safe_edit_game(
    game: dict,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> bool:
    return await safe_edit_text_and_markup(
        game,
        chat_id=game["chat_id"],
        message_id=game["message_id"],
        text=text,
        reply_markup=reply_markup,
    )

def _pick_winner(scores: Dict[int, int]) -> int:
    """Победитель - максимальный бросок; при ничьей - случайный среди лидеров."""
    best = max(scores.values())
    leaders = [int(uid) for uid, val in scores.items() if val == best]
    return random.choice(leaders)

def _assign_unique_roll(game: dict, user_id: int) -> Optional[int]:
    """Выдать уникальное число 1..12, не повторяя уже занятые."""
    used = set(game.get("scores", {}).values())
    pool = [x for x in range(DICE_MIN, DICE_MAX + 1) if x not in used]
    if not pool:
        return None
    val = random.choice(pool)
    game.setdefault("scores", {})[user_id] = val
    return val

# ====== Хелперы ======
async def _get_balance_as_int(user_id: int) -> int:
    bal = await db.get_user_balance(user_id)
    if bal is None:
        return 0
    try:
        return int(bal)
    except Exception:
        try:
            return int(float(bal))
        except Exception:
            return 0

async def _has_funds(user_id: int, amount: int) -> bool:
    try:
        cur = await _get_balance_as_int(user_id)
        return cur >= int(amount)
    except Exception:
        return False

async def get_bot_username_by_token(token: str) -> str:
    me = await bot1.get_me()
    return me.username

async def create_user_link(user_id: int, first_name: Optional[str], username: Optional[str]) -> str:
    if username:
        return f"<a href='https://t.me/{html.escape(username)}'>{html.escape(first_name or 'Игрок')}</a>"
    if first_name:
        return html.escape(first_name)
    return f"<a href='tg://user?id={user_id}'>Игрок</a>"

async def _rollback_debits(user_ids: List[int], bet: int) -> None:
    for uid in user_ids:
        try:
            ok = await db.update_user_balance(uid, f"+{bet}")
            if ok is None:
                print(f"[KOSTI][rollback] delta +{bet} failed uid={uid}")
                continue
            await db.touch_balance_last_active(uid, set_active_status=True)
            await db.cutehistory_plus(uid, bet, "+ кости (возврат)")
        except Exception as e:
            print(f"[KOSTI][rollback uid={uid}] {e!r}")

async def _abort_game_unlocked(game: dict, game_id: int, reason: str) -> None:
    try:
        await _safe_edit_game(
            game,
            f"⛑ <b>Игра остановлена!</b>\n{html.escape(reason)}",
            reply_markup=None,
        )
    except Exception as e:
        print(f"[KOSTI][abort edit] {e!r}")
    gameskosti.pop(game_id, None)

async def _abort_settle_unlocked(game: dict, game_id: int, reason: str) -> None:
    try:
        await _safe_edit_game(
            game,
            f"⛑ <b>Игра остановлена!</b>\n{html.escape(reason)}",
            reply_markup=None,
        )
    except Exception as e:
        print(f"[KOSTI][settle abort edit] {e!r}")
    game["losses_applied"] = []
    game["winner_applied"] = False
    game["settling"] = False
    gameskosti.save()
    gameskosti.pop(game_id, None)

# ====== Команда "кости [ставка]" ======
@dp.message(F.text)
async def kosti(message: Message):
    if not message.text:
        return

    text = message.text.strip()
    parts = text.split()
    if not parts:
        return

    # строго только "кости" / "кости <число>"
    if parts[0].lower() != "кости":
        return

    if await reject_if_private_game(message):
        return

    if len(parts) == 1:
        bet = 0
    elif len(parts) == 2:
        bet_s = parts[1]
        # строго целое число (без точек/запятых/слов)
        if not bet_s.isdigit():
            return
        bet = int(bet_s)
    else:
        return

    # отрицательные/мусор - игнор
    if bet < 0:
        return

    creator_id = message.from_user.id

    # мягкая проверка средств (ничего не списываем) - только если bet > 0
    if bet > 0 and not await _has_funds(creator_id, bet):
        try:
            bot_username = await get_bot_username_by_token(TOKEN)
        except Exception:
            bot_username = "CuteGamingBot"

        pending_context[creator_id] = {"stars_amount": str(bet), "sent": False}

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"⭐️ Купить {bet:,}".replace(",", ".") + " кут ⭐️",
                url=f"https://t.me/{bot_username}?start=insert_{bet}_+"
            )],
            [InlineKeyboardButton(text="У вас закончились куты", callback_data="9help_btn22")],
            [InlineKeyboardButton(text="Как заработать?", callback_data="9help_btn22")]
        ])

        await message.reply("🤙", reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

        await asyncio.sleep(timeoutdonate)
        if creator_id in pending_context and not pending_context[creator_id].get("sent"):
            invoice = await send_invoice_to_user(message, str(bet))
            pending_context[creator_id]["manual_message_id"] = invoice.message_id
        return

    # создаём игру
    game_id = message.message_id
    gameskosti[game_id] = {
        "state": STATE_CREATED,
        "creator": creator_id,
        "bet": bet,
        "participants": [creator_id],      # int
        "scores": {},                      # uid -> int (бросок)
        "game_started": False,
        "finished": False,

        # расчёты (сагa):
        "settling": False,
        "losses_applied": [],              # uid, с кого списали ставку
        "winner_applied": False,
        "winner_id": None,

        # инфраструктура
        "chat_id": None,
        "message_id": None,

        # отображение
        "_last_view": {"text": None, "kb_sig": None},
        "_tick": None,
    }

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Присоединиться", callback_data=f"kostijoin:{game_id}")]
        ]
    )
    button_kosti[game_id] = {}
    button_kosti[game_id]["keyboard_join"] = keyboard

    first_name = await db.get_firstname_by_user_id(creator_id)
    username = await db.get_username_by_user_id(creator_id)
    name_link = await create_user_link(creator_id, first_name, username)

    # случайная наклейка - Optional
    try:
        if random.randint(1, 100) > 50:
            await message.answer(f"<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji>", parse_mode="HTML", show_alert=True)
    except Exception:
        pass

    msg = await message.reply(
        f"<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji> <b>Играем в кости\n- {name_link}</b>",
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    gameskosti[game_id]["chat_id"] = msg.chat.id
    gameskosti[game_id]["message_id"] = msg.message_id
    # touch: in-place поля chat_id/message_id → Redis (hash dirty)
    try:
        gameskosti.touch(game_id)
    except Exception:
        gameskosti[game_id] = gameskosti[game_id]
        gameskosti.save()

# ====== Присоединение ======
@dp.callback_query(lambda c: c.data.startswith('kostijoin:'))
async def kosti_join_game_callback(callback_query: CallbackQuery):
    game_id = int(callback_query.data.split(':')[1])
    user_id = callback_query.from_user.id

    if game_id not in gameskosti:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    # анти-дребезг
    inflight_key = (game_id, user_id)
    if inflight_key in _inflight_joins:
        await callback_query.answer("⏳ Обрабатываю присоединение...", show_alert=True)
        return
    _inflight_joins.add(inflight_key)

    try:
        async with _get_lock(_join_locks, game_id):
            if game_id not in gameskosti:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            game = gameskosti[game_id]
            if game.get("state") not in (STATE_CREATED, STATE_STARTED):
                await callback_query.answer("💭 Присоединение уже закрыто.", show_alert=True)
                return

            if await db.is_user_banned(user_id):
                await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
                return

            if user_id == game['creator']:
                await callback_query.answer("❕ Нельзя присоединиться к своей игре.", show_alert=True)
                return

            participants = _dedupe_preserve_order([int(x) for x in game.get('participants', [])])
            game['participants'] = participants

            if len(participants) >= MAX_PARTICIPANTS:
                await callback_query.answer("💭 В игре нет мест.", show_alert=True)
                return

            if not await _has_funds(user_id, game['bet']):
                await callback_query.answer("💭 Недостаточно средств для участия.", show_alert=True)
                return

            # анти-реф защита
            try:
                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                except LookupError:
                    inviter_id = None

                parts_set = set(participants)
                if inviter_id and inviter_id in parts_set:
                    now = datetime.now()
                    secs = await _pair_seconds_left(db, user_id, inviter_id, now=now)
                    if secs > 0:
                        ts = _format_hms(secs)
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует пригласивший вас пользователь.\n"
                            f"⏳ До снятия ограничения: {ts}\n#AntiFarmSystem",
                            show_alert=True
                        )
                        return

                invitees_here = await db.get_invitees_in(inviter_id=user_id, candidates=parts_set)
                if invitees_here:
                    now = datetime.now()
                    min_secs = None
                    for invitee_id in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, invitee_id, now=now)
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)
                    if min_secs:
                        ts = _format_hms(min_secs)
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует приглашённый вами пользователь.\n"
                            f"⏳ До снятия ограничения: {ts}\n#AntiFarmSystem",
                            show_alert=True
                        )
                        return
            except Exception:
                await callback_query.answer("💭 Техническая ошибка (код #K1212).", show_alert=True)
                return

            if user_id in game['participants']:
                await callback_query.answer("❕ Вы уже участвуете.", show_alert=True)
                return

            game['participants'].append(user_id)
            game['participants'] = _dedupe_preserve_order(game['participants'])
            # КРИТИЧНО: append in-place → без touch hash-Redis не узнает об игроке
            try:
                gameskosti.touch(game_id)
            except Exception:
                gameskosti[game_id] = game

            # отрисовка
            names = []
            for uid in game['participants']:
                first_name = await db.get_firstname_by_user_id(uid)
                username = await db.get_username_by_user_id(uid)
                names.append(f"<b>- {await create_user_link(uid, first_name, username)}</b>")
            participants_text = "\n".join(names)

            total_pot = game['bet'] * len(game['participants'])
            win_text = ""
            if total_pot > 0:
                winf = "{:,.0f}".format(total_pot - game['bet']).replace(",", ".")
                win_text = f"\n<tg-emoji emoji-id='5292146637844543370'>🕊</tg-emoji> <b>Выигрыш {winf} кут</b>"

            if len(game['participants']) >= MAX_PARTICIPANTS:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="Начать игру", callback_data=f"kostistart:{game_id}")]]
                )
            else:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Присоединиться", callback_data=f"kostijoin:{game_id}")],
                        [InlineKeyboardButton(text="Начать игру", callback_data=f"kostistart:{game_id}")]
                    ]
                )

            try:
                if game_id not in button_kosti:
                    button_kosti[game_id] = {}
                button_kosti[game_id]['keyboard_join2'] = keyboard
                button_kosti.touch(game_id)
            except Exception:
                button_kosti[game_id] = {"keyboard_join2": keyboard}

            await _safe_edit_game(
                game,
                f"<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji> <b>Играем в кости</b>{win_text}\n{participants_text}",
                keyboard,
            )
            try:
                gameskosti.touch(game_id)
            except Exception:
                gameskosti[game_id] = game

    finally:
        _inflight_joins.discard(inflight_key)

# ====== Старт ======
@dp.callback_query(lambda c: c.data.startswith('kostistart:'))
async def kosti_start_game_callback(callback_query: CallbackQuery):
    game_id = int(callback_query.data.split(':')[1])
    user_id = callback_query.from_user.id

    if game_id not in gameskosti:
        await callback_query.answer("🛠 Игра не существует", show_alert=True)
        return

    async with _get_lock(_game_locks, game_id):
        if game_id not in gameskosti:
            await callback_query.answer("🛠 Игра не существует", show_alert=True)
            return

        game = gameskosti[game_id]
        if game.get('game_started'):
            await callback_query.answer("ℹ️ Игра уже запущена.", show_alert=True)
            return
        if user_id != game['creator']:
            await callback_query.answer("💭 Только создатель может начать.", show_alert=True)
            return

        parts = _dedupe_preserve_order([int(x) for x in game.get('participants', [])])
        game['participants'] = parts
        if len(parts) < 2:
            # После рестарта иногда в RAM устаревший снимок — один forced reload
            try:
                if hasattr(gameskosti, "_load"):
                    inner = gameskosti._load()
                else:
                    inner = gameskosti
                from bot.db_create.pklcode import GameStore_reload_from_redis_forced
                GameStore_reload_from_redis_forced(inner)
                game = gameskosti[game_id]
                parts = _dedupe_preserve_order([int(x) for x in game.get('participants', [])])
                game['participants'] = parts
            except Exception:
                pass
            if len(parts) < 2:
                await callback_query.answer("💭 Недостаточно участников (нужно ≥ 2).", show_alert=True)
                return

        # финальная мягкая проверка
        bet = int(game['bet'])
        lacking = []
        for pid in parts:
            if not await _has_funds(int(pid), bet):
                first_name = await db.get_firstname_by_user_id(pid)
                username  = await db.get_username_by_user_id(pid)
                link      = await create_user_link(pid, first_name, username)
                lacking.append(f"<b>- {link}</b>")
        if lacking:
            await _safe_edit_game(
                game,
                "⛑ <b>Игра остановлена!</b>\nУ кого-то недостаточно средств:\n" + "\n".join(lacking),
                reply_markup=None,
            )
            gameskosti.pop(game_id, None)
            await callback_query.answer("⛑ Остановлено: недостаточно средств.", show_alert=True)
            return

        game['state'] = STATE_STARTED
        game['game_started'] = True
        try:
            gameskosti.touch(game_id)
        except Exception:
            gameskosti[game_id] = game

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="5", callback_data=f"kostiroll:{game_id}")]]
        )
        try:
            if game_id not in button_kosti:
                button_kosti[game_id] = {}
            button_kosti[game_id]['keyboard_roll'] = keyboard
            button_kosti.touch(game_id)
        except Exception:
            button_kosti[game_id] = {"keyboard_roll": keyboard}
        await _safe_edit_game(
            game,
            "<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji> <b>Нажмите, чтобы получить случайное число</b>",
            keyboard,
        )

    await callback_query.answer("🚀 Игра началась!")
    asyncio.create_task(_countdown_and_autofill(game_id))

# ====== Ролл ======
@dp.callback_query(lambda c: c.data.startswith('kostiroll:'))
async def kosti_roll_callback(callback_query: CallbackQuery):
    game_id = int(callback_query.data.split(':')[1])
    user_id = callback_query.from_user.id

    if game_id not in gameskosti:
        await callback_query.answer("🛠 Игра не существует.", show_alert=True)
        return

    # анти-дребезг на ролл
    inflight = (game_id, user_id)
    if inflight in _inflight_rolls:
        await callback_query.answer("⏳ Обрабатываю ваш бросок...", show_alert=True)
        return
    _inflight_rolls.add(inflight)

    need_settle = False   # <--- добавили флаг
    try:
        async with _get_lock(_game_locks, game_id):
            if game_id not in gameskosti:
                await callback_query.answer("🛠 Игра не существует.", show_alert=True)
                return

            game = gameskosti[game_id]
            if game.get('finished'):
                await callback_query.answer("ℹ️ Игра уже завершена.", show_alert=True)
                return
            if game.get('state') not in (STATE_STARTED, STATE_ROLLING):
                await callback_query.answer("💭 Броски сейчас недоступны.", show_alert=True)
                return
            if user_id not in game['participants']:
                await callback_query.answer("💭 Вы не участвуете.", show_alert=True)
                return
            if user_id in game['scores']:
                await callback_query.answer(f"❕ Ваше число: {game['scores'][user_id]}", show_alert=True)
                return

            # мягкая проверка
            bet = int(game['bet'])
            if not await _has_funds(user_id, bet):
                await _abort_game_unlocked(game, game_id, "У кого-то из участников недостаточно средств.")
                return

            val = _assign_unique_roll(game, user_id)
            if val is None:
                await callback_query.answer("⚠ Нет доступных чисел!", show_alert=True)
                return
            game['state'] = STATE_ROLLING
            gameskosti.save()

            await callback_query.answer(f"❕ Ваше число: {val}", show_alert=True)

            # все кинули? - только отмечаем и выходим из лока
            if len(game['scores']) == len(game['participants']):
                game['finished'] = True
                gameskosti.save()
                need_settle = True   # <--- отмечаем, что пора считать

    finally:
        _inflight_rolls.discard(inflight)

    # СТАРТ РАСЧЁТОВ УЖЕ БЕЗ ЛОКА! (не будет дедлока)
    if need_settle:
        await _show_and_settle(game_id)

# ====== Отсчёт и автодобив ======
async def _countdown_and_autofill(game_id: int):
    if game_id not in gameskosti:
        return

    # фиксируем параметры вне цикла
    async with _get_lock(_game_locks, game_id):
        game = gameskosti.get(game_id)
        if not game:
            return
        participants = list(game['participants'])

    for i in range(5, 0, -1):
        # Правку обратного отсчёта (сеть + возможный flood-sleep) выносим ЗА лок,
        # иначе тап «ролл» ждёт завершения этой правки - залипание кнопки.
        do_edit = False
        kb = None
        game = None
        async with _get_lock(_game_locks, game_id):
            game = gameskosti.get(game_id)
            if not game:
                return
            if all(uid in game['scores'] for uid in participants) or game.get('finished'):
                break

            if game.get("_tick") != i:
                game["_tick"] = i
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text=f"{i}", callback_data=f"kostiroll:{game_id}")]]
                )
                button_kosti[game_id]['keyboard_roll'] = kb
                do_edit = True

        if do_edit:
            await _safe_edit_game(
                game,
                "<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji> <b>Нажмите, чтобы получить случайное число</b>",
                kb,
            )

        await asyncio.sleep(1)

    need_settle = False
    async with _get_lock(_game_locks, game_id):
        game = gameskosti.get(game_id)
        if not game:
            return

        if game.get('state') in (STATE_SETTLING, STATE_SETTLED):
            return

        for uid in list(game['participants']):
            if uid not in game['scores']:
                if _assign_unique_roll(game, uid) is None:
                    print(f"[KOSTI][autofill] нет свободных чисел game={game_id} uid={uid}")

        if not game.get('finished'):
            game['finished'] = True
            gameskosti.save()
            need_settle = True

    if need_settle:
        await _show_and_settle(game_id)

# ====== Показ результата и расчёты ======
async def _show_and_settle(game_id: int):
    async with _get_lock(_game_locks, game_id):
        game = gameskosti.get(game_id)
        if not game:
            return

        if game.get('state') in (STATE_SETTLING, STATE_SETTLED):
            return

        bet = int(game['bet'])
        participants = list(game['participants'])
        scores = dict(game.get('scores', {}))
        if not scores or not participants:
            gameskosti.pop(game_id, None)
            return

        if len(scores) < len(participants):
            for uid in participants:
                if uid not in scores:
                    _assign_unique_roll(game, int(uid))
            scores = dict(game.get('scores', {}))

        winner_id = _pick_winner({int(k): int(v) for k, v in scores.items()})
        game['winner_id'] = winner_id
        total_pot = bet * len(participants)
        gain = total_pot - bet

        for uid in participants:
            if not await _has_funds(int(uid), bet):
                await _abort_game_unlocked(game, game_id, "У кого-то из участников недостаточно средств.")
                return

        winf = "{:,.0f}".format(gain).replace(",", ".")
        w_link = await create_user_link(
            winner_id,
            await db.get_firstname_by_user_id(winner_id),
            await db.get_username_by_user_id(winner_id)
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Подробнее", callback_data=f"podrobneekostihui_{game_id}")]]
        )
        button_kosti[game_id]['keyboard_result'] = kb

        text = f"<tg-emoji emoji-id='5262924479226473498'>🏆</tg-emoji> <b>{w_link}</b>"
        if total_pot >= 1:
            text += f"\n<tg-emoji emoji-id='5294026527850132517'>💲</tg-emoji> <b>Выигрыш {winf} кут</b>"

        try:
            await _safe_edit_game(game, text, kb)
        except Exception as e:
            print(f"[KOSTI][result edit] {e!r}")

        asyncio.create_task(store_temp_game_data(str(game_id), participants, scores, winner_id))

        game['state'] = STATE_SETTLING
        gameskosti.save()

    await _settle_saga(game_id)

# ====== Сага расчётов ======
async def _settle_saga(game_id: int):
    async with _get_lock(_game_locks, game_id):
        game = gameskosti.get(game_id)
        if not game:
            return

        if game.get('state') == STATE_SETTLED:
            return
        if game.get('state') != STATE_SETTLING:
            return
        if game.get('settling'):
            return

        game['settling'] = True
        gameskosti.save()

        bet = int(game['bet'])
        participants = list(game['participants'])
        winner_id = int(game.get('winner_id') or 0)
        total_pot = bet * len(participants)
        gain = total_pot - bet

        # A) дебет лузеров по одному (идемпотентно)
        losses_applied = set(int(u) for u in game.get('losses_applied', []))
        losers = [int(u) for u in participants if int(u) != winner_id]

        debited_now: List[int] = []
        for uid in losers:
            if uid in losses_applied:
                continue

            if not await _has_funds(uid, bet):
                await _rollback_debits(debited_now, bet)
                await _abort_settle_unlocked(game, game_id, "У кого-то недостаточно средств.")
                return

            try:
                ok_new = await db.update_user_balance(uid, f"-{bet}")
                await db.touch_balance_last_active(uid, set_active_status=True)
                if ok_new is None:
                    raise RuntimeError(f"delta debit failed uid={uid}")
                await db.cutehistory_minus(uid, bet, "- кости")
                await db.update_user_loose(uid, 1, bot1, ref_coin)
                await db.update_game_last_activity(uid)
            except Exception as e:
                print(f"[KOSTI][debit] uid={uid} err={e!r}")
                await _rollback_debits(debited_now, bet)
                await _abort_settle_unlocked(game, game_id, "Техническая ошибка взаиморасчётов.")
                return

            debited_now.append(uid)
            losses_applied.add(uid)
            game['losses_applied'] = list(losses_applied)
            gameskosti.save()

        if not game.get('winner_applied', False):
            try:
                ok_new_w = await db.update_user_balance(winner_id, f"+{gain}")
                await db.touch_balance_last_active(winner_id, set_active_status=True)
                if ok_new_w is None:
                    raise RuntimeError(f"winner credit failed uid={winner_id}")
                await db.cutehistory_plus(winner_id, gain, "+ кости")
                await db.update_user_wins(winner_id, 1, bot1, ref_coin)
                await db.update_user_winamount(winner_id, gain)
                await db.update_game_last_activity(winner_id)
            except Exception as e:
                print(f"[KOSTI][credit winner] uid={winner_id} err={e!r}")
                await _rollback_debits(list(losses_applied), bet)
                await _abort_settle_unlocked(game, game_id, "Техническая ошибка взаиморасчётов.")
                return

            game['winner_applied'] = True
            gameskosti.save()

        try:
            last_open_time, data_open = await db.get_historygames_times(winner_id)
            current_time = time.time()
            if last_open_time is None or data_open is None:
                last_open_time = get_current_time_formatted()
                data_open_ts = current_time + timehistorygames
                user_name = await db.get_firstname_by_user_id(winner_id)
                await db.add_historygames(
                    game["chat_id"], "1", winner_id, user_name,
                    last_open_time, datetime.fromtimestamp(data_open_ts).strftime("%Y-%m-%d %H:%M:%S")
                )
            else:
                last_open_time = get_current_time_formatted()
                next_open_ts = current_time + timehistorygames
                await db.update_historygames(
                    winner_id, last_open_time,
                    datetime.fromtimestamp(next_open_ts).strftime("%Y-%m-%d %H:%M:%S")
                )
        except Exception as e:
            print(f"[KOSTI][history] {e!r}")

        game['state'] = STATE_SETTLED
        game['settling'] = False
        gameskosti.save()
        try:
            del gameskosti[game_id]
        except KeyError:
            pass

# ====== Временное хранилище результатов (для попапа) ======
async def store_temp_game_data(game_id: str, participants: list, scores: dict, winner_id: int, ttl: int = 180):
    gid = str(game_id)
    temp_kosti_data[gid] = {"participants": participants, "scores": scores, "winner_id": winner_id}
    temp_kosti_data.save()
    await asyncio.sleep(ttl)
    temp_kosti_data.pop(gid, None)

# ====== Попап "Подробнее" ======
@dp.callback_query(lambda c: c.data.startswith('podrobneekostihui_'))
async def kosti_send_game_results(callback_query: CallbackQuery):
    game_id = callback_query.data.split("podrobneekostihui_")[1].strip()
    game = temp_kosti_data.get(str(game_id))
    if not game:
        await callback_query.answer("⏰ Срок действия данных истек", show_alert=True)
        return

    lines = []
    for uid in game['participants']:
        try:
            first_name = await db.get_firstname_by_user_id(uid)
            val = game['scores'].get(uid, "-")
            if uid == game['winner_id']:
                lines.append(f"- {first_name} : {val} 🏆")
            else:
                lines.append(f"- {first_name} : {val}")
        except Exception:
            pass

    if not lines:
        await callback_query.answer("⏰ Результаты отсутствуют или не были обработаны.", show_alert=True)
        return

    await callback_query.answer(
        "Каждый бросает число от 1 до 12.\nПобеждает максимальное число.\n\n" + "\n".join(lines),
        show_alert=True
    )
