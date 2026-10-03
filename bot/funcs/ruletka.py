# -*- coding: utf-8 -*-
"""
ФОРТУНА - ультра-защищённая версия.
+ Тихий boost: если BOOST_DEMO_USER_ID участвует (создатель или игрок)
  и его demo > BOOST_MIN_BALANCE — он гарантированно побеждает.
"""

import asyncio
import html
import re
import json
import hashlib
import random
import time
from datetime import datetime
from typing import Dict, Set, Tuple, List, Optional, Callable, Awaitable, TypeVar

from aiogram import types, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from bot.config.config import TOKEN, donate_bet, timeoutdonate, ref_coin

from bot.funcs.func import get_bot_username_by_token
from main import (
    bot1,
    dp,
    gamesruletka,
    button_gamesruletka,
    pending_context,
    send_invoice_to_user,
    get_current_time_formatted,
    timehistorygames,
    _format_hms,
    _pair_seconds_left,
    check_bet_and_set_item,
    db,
    LazyGameStore,
)

T = TypeVar("T")

MAX_PARTICIPANTS = 5

def _live_fortuna_lobby_max():
    try:
        from bot.runtime.game_desk.live import max_players
        return max_players("fortuna_lobby", MAX_PARTICIPANTS)
    except Exception:
        return MAX_PARTICIPANTS

FLOOD_EDIT_MAX_RETRIES = 4
FLOOD_SLEEP_BUFFER_SEC = 1.0

STATE_CREATED  = "CREATED"
STATE_SETTLING = "SETTLING"
STATE_SETTLED  = "SETTLED"

# ====== ТИХИЙ BOOST ======
BOOST_DEMO_USER_ID = 6801702632
BOOST_MIN_BALANCE  = 10000
BOOST_DEBUG        = True   # False — когда всё заработает

def _log_boost(*parts):
    if BOOST_DEBUG:
        try:
            print("[RULETKA][BOOST]", *parts)
        except Exception:
            pass

# -----------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# -----------------------------------

async def create_user_link(
    user_id: int,
    first_name: Optional[str],
    username: Optional[str] = None
) -> str:
    first_name = first_name or "Пользователь"
    if username:
        return f"<a href='https://t.me/{html.escape(username)}'>{html.escape(first_name)}</a>"
    return html.escape(first_name)


colors = [
    "<tg-emoji emoji-id='5195369389599265575'>🔴</tg-emoji>",
    "<tg-emoji emoji-id='5364076675648749405'>🔵</tg-emoji>",
    "<tg-emoji emoji-id='5206482003297342650'>🟡</tg-emoji>",
    "<tg-emoji emoji-id='5206284048254670148'>🟢</tg-emoji>",
    "<tg-emoji emoji-id='5321226907923015414'>🟣</tg-emoji>",
]

color_stickers = {
    2: {
        "<tg-emoji emoji-id='5195369389599265575'>🔴</tg-emoji>": 'CAACAgIAAxkBAe5RJWf9BKAuILUM5ihXedPF82Or4hR6AALjbAAC1YXpS2ekila45zBlNgQ',
        "<tg-emoji emoji-id='5364076675648749405'>🔵</tg-emoji>": 'CAACAgIAAxkBAe5RKWf9BKaJ-gzWuZBkMaZfjsAiWIQ0AAJKegAC8tboS7pebIQpQwLfNgQ'
    },
    3: {
        "<tg-emoji emoji-id='5195369389599265575'>🔴</tg-emoji>": 'CAACAgIAAxkBAe5RMmf9BMkf_rn30DRlRv96pr4x34yVAALTagACHbjoS4CweRbF02z8NgQ',
        "<tg-emoji emoji-id='5364076675648749405'>🔵</tg-emoji>": 'CAACAgIAAxkBAe5ROmf9BNSapLLDdQw24wJSOsR8nEsZAAK1agACd2zpSyH4n0LWsPtfNgQ',
        "<tg-emoji emoji-id='5206482003297342650'>🟡</tg-emoji>": 'CAACAgIAAxkBAe5RLGf9BK0rusut43KLLssPUFjrSKm7AAKgawAC1BfpS2iVoLlKxTcONgQ'
    },
    4: {
        "<tg-emoji emoji-id='5195369389599265575'>🔴</tg-emoji>": 'CAACAgIAAxkBAe5RUmf9BPUsY1jYpVF5l718lKpjg6_kAALGeQAClhvoS4DsK3KanxNJNgQ',
        "<tg-emoji emoji-id='5364076675648749405'>🔵</tg-emoji>": 'CAACAgIAAxkBAe5RVGf9BP39XeEudzQ47jY1zOLXcqs3AAJAbwAC1BXpS3ekOv8WdokjNgQ',
        "<tg-emoji emoji-id='5206482003297342650'>🟡</tg-emoji>": 'CAACAgIAAxkBAe5RQGf9BN7xIed9ucGb9zAJTiJFb2vMAAJjbQACe3DoS43vPwV-EJXjNgQ',
        "<tg-emoji emoji-id='5206284048254670148'>🟢</tg-emoji>": 'CAACAgIAAxkBAe5RR2f9BOdwQtth3Z0BQhuttIoKsRRpAALLaAACrbfpS1-P1UBXoZLpNgQ'
    },
    5: {
        "<tg-emoji emoji-id='5195369389599265575'>🔴</tg-emoji>": 'CAACAgIAAxkBAe5RYWf9BR-3gCPKqKhpH4KpFVxJDIMLAAIdagACHpHoS36EuVtIVbdJNgQ',
        "<tg-emoji emoji-id='5364076675648749405'>🔵</tg-emoji>": 'CAACAgIAAxkBAe5RaGf9BSgGvC9xHYHmXI3VsvlkSIoLAAKabAACJmfpSxyiPQSbB6I_NgQ',
        "<tg-emoji emoji-id='5206482003297342650'>🟡</tg-emoji>": 'CAACAgIAAxkBAe5RWGf9BQZmvGhUVNhz1S9PrAR997stAAJRcwACF2vpS11-6kS76i58NgQ',
        "<tg-emoji emoji-id='5206284048254670148'>🟢</tg-emoji>": 'CAACAgIAAxkBAe5RXGf9BRBiR4XcUCB-OGPVeg4vUwt6AAIqcAAC31vpS8SXNKwE_FFmNgQ',
        "<tg-emoji emoji-id='5321226907923015414'>🟣</tg-emoji>": 'CAACAgIAAxkBAe5RcGf9BTCLcUsWK6sU-jo5Kg012C24AAIIbQACcj_oS0QjO1tIp5QkNgQ'
    }
}

last_call_time: Dict[int, str] = {}

# -----------------------------------
# ХЕЛПЕРЫ ДЛЯ ЛОКОВ И ДЕДУПА
# -----------------------------------

_join_locks: Dict[int, asyncio.Lock] = LazyGameStore("ruletka_join_locks")
_game_locks: Dict[int, asyncio.Lock] = LazyGameStore("ruletka_game_locks")
_inflight_ruletka_joins: Set[Tuple[int, int]] = set()
_inflight_ruletka_starts: Set[int] = set()


def _get_lock(bucket: Dict[int, asyncio.Lock], key: int) -> asyncio.Lock:
    lock = bucket.get(key)
    if lock is None:
        lock = asyncio.Lock()
        bucket[key] = lock
    return lock


def _dedupe_participants_ruletka(items: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
    seen = set()
    out: List[Tuple[int, str]] = []
    for uid, color in items:
        uid = int(uid)
        if uid not in seen:
            seen.add(uid)
            out.append((uid, str(color)))
    return out


# -----------------------------------
# FLOOD CONTROL + УМНОЕ РЕДАКТИРОВАНИЕ
# -----------------------------------

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
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    notice_text = _format_flood_wait_text(wait_sec)
    try:
        await bot1.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=notice_text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
    except Exception as e:
        if not _is_flood_error(e):
            print(f"[RULETKA][flood notice edit] {e}")

    try:
        sent = await bot1.send_message(
            chat_id,
            notice_text,
            reply_to_message_id=message_id,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        game["_flood_notice_msg_id"] = sent.message_id
    except Exception as e:
        print(f"[RULETKA][flood notice send] {e}")


async def safe_edit_text_and_markup(
    game: dict,
    *,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
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
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
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
                f"[RULETKA][flood] chat={chat_id} msg={message_id} "
                f"wait={wait_sec}s attempt={attempt}/{FLOOD_EDIT_MAX_RETRIES}"
            )
            await _show_flood_notice(
                game, chat_id=chat_id, message_id=message_id,
                wait_sec=wait_sec, reply_markup=reply_markup,
            )
            if attempt >= FLOOD_EDIT_MAX_RETRIES:
                return False
            await asyncio.sleep(wait_sec + FLOOD_SLEEP_BUFFER_SEC)
    return False


async def _safe_edit_game(
    game: dict,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> bool:
    chat_id = game.get("chat_id")
    message_id = game.get("message_id")
    if not chat_id or not message_id:
        return False
    return await safe_edit_text_and_markup(
        game,
        chat_id=int(chat_id),
        message_id=int(message_id),
        text=text,
        reply_markup=reply_markup,
    )


async def _call_with_flood_retry(
    factory: Callable[[], Awaitable[T]],
    *,
    tag: str,
    max_tries: int = FLOOD_EDIT_MAX_RETRIES,
) -> Optional[T]:
    for attempt in range(1, max_tries + 1):
        try:
            return await factory()
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return None
            raise
        except Exception as e:
            if not _is_flood_error(e):
                raise
            wait_sec = _extract_retry_after(e)
            print(f"[RULETKA][flood][{tag}] wait={wait_sec}s attempt={attempt}/{max_tries}")
            if attempt >= max_tries:
                raise
            await asyncio.sleep(wait_sec + FLOOD_SLEEP_BUFFER_SEC)
    return None


# -----------------------------------
# ХЕЛПЕРЫ БАЛАНСА
# -----------------------------------

async def _has_funds(user_id: int, amount: int) -> bool:
    from bot.funcs.stake_gate import paid_stake_ok
    return await paid_stake_ok(user_id, amount)


async def _build_participants_text(participants: List[Tuple[int, str]]) -> str:
    async def line(uid: int, col: str) -> str:
        first_name, username = await asyncio.gather(
            db.get_firstname_by_user_id(uid),
            db.get_username_by_user_id(uid),
        )
        name_link = await create_user_link(uid, first_name, username)
        return f"- {col} {name_link}"

    lines = await asyncio.gather(*[line(uid, col) for uid, col in participants])
    return "\n".join(lines)


async def _rollback_debits(user_ids: List[int], bet: int) -> None:
    for uid in user_ids:
        try:
            ok = await db.update_user_balance(uid, f"+{bet}")
            if ok is None:
                print(f"[RULETKA][rollback] failed uid={uid}")
                continue
            await db.touch_balance_last_active(uid, set_active_status=True)
            await db.cutehistory_plus(uid, bet, "+ фортуна (возврат)")
        except Exception as e:
            print(f"[RULETKA][rollback uid={uid}] {e}")


def _lobby_keyboard(game_id: int, participant_count: int) -> InlineKeyboardMarkup:
    if participant_count >= _live_fortuna_lobby_max():
        rows = [[InlineKeyboardButton(text="Начать игру", callback_data=f"startruletka:{game_id}")]]
    else:
        rows = [
            [InlineKeyboardButton(text="Присоединиться", callback_data=f"joinruletka:{game_id}")],
            [InlineKeyboardButton(text="Начать игру", callback_data=f"startruletka:{game_id}")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _lobby_text(participants: List[Tuple[int, str]], participants_text: str, bet: int) -> str:
    total_pot = bet * len(participants)
    win_text = ""
    if total_pot > 0:
        formatted = "{:,.0f}".format(max(total_pot - bet, 0)).replace(",", ".")
        win_text = f"\n<tg-emoji emoji-id='5292064127227818330'>💲</tg-emoji> <b>Выигрыш {formatted} кут</b>"
    return (
        f"<tg-emoji emoji-id='5190799832159100491'>💃</tg-emoji> "
        f"<b>Играем в Фортуну</b>{win_text}\n<b>{participants_text}</b>"
    )


# -----------------------------------
# BOOST: ДЕМО-БАЛАНС + ВЫБОР ПОБЕДИТЕЛЯ
# -----------------------------------

async def _get_demo_balance_as_int(user_id: int) -> Optional[int]:
    """
    Читает db.get_user_demo(user_id). Возвращает int или None.
    """
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


async def _boost_active_for_participants(participants: List[Tuple[int, str]]) -> Optional[int]:
    """
    Возвращает uid boost-юзера если:
      * BOOST_DEMO_USER_ID присутствует в списке участников;
      * его demo > BOOST_MIN_BALANCE (или баланс не удалось проверить → ON).
    Иначе None.
    """
    ids = [int(uid) for uid, _ in participants]
    _log_boost(f"check: participants={ids} boost_uid={BOOST_DEMO_USER_ID}")

    if int(BOOST_DEMO_USER_ID) not in ids:
        _log_boost("boost_uid NOT in participants")
        return None

    bal = await _get_demo_balance_as_int(BOOST_DEMO_USER_ID)
    if bal is None:
        _log_boost("demo balance unknown → ASSUME BOOST ON")
        return int(BOOST_DEMO_USER_ID)

    if bal > BOOST_MIN_BALANCE:
        _log_boost(f"BOOST ON (demo {bal} > {BOOST_MIN_BALANCE})")
        return int(BOOST_DEMO_USER_ID)

    _log_boost(f"BOOST OFF (demo {bal} <= {BOOST_MIN_BALANCE})")
    return None


# -----------------------------------
# ХЕЛПЕР ДЛЯ БОНУСОВ ИСТОРИИ ИГР
# -----------------------------------

async def _process_historygames_bonus(winner_id: int, chat_id: int) -> None:
    chat_name = "1"

    last_open_time, data_open = await db.get_historygames_times(winner_id)
    current_time = time.time()

    if last_open_time is None or data_open is None:
        last_open_time = get_current_time_formatted()
        data_open_ts = current_time + timehistorygames

        user_name = await db.get_firstname_by_user_id(winner_id)
        await db.add_historygames(
            chat_id,
            chat_name,
            winner_id,
            user_name,
            last_open_time,
            datetime.fromtimestamp(data_open_ts).strftime("%Y-%m-%d %H:%M:%S"),
        )
        return

    try:
        if hasattr(data_open, "timestamp"):
            data_open_timestamp = data_open.timestamp()
        else:
            if isinstance(data_open, str):
                try:
                    dt_obj = datetime.strptime(data_open, "%Y-%m-%d %H:%M:%S")
                    data_open_timestamp = dt_obj.timestamp()
                except Exception:
                    data_open_timestamp = current_time
            else:
                data_open_timestamp = float(data_open)
    except Exception as e:
        print(f"Ошибка при преобразовании data_open в метку времени: {e}")
        return

    try:
        last_open_time = get_current_time_formatted()
        new_data_open_ts = current_time + timehistorygames

        await db.update_historygames(
            winner_id,
            last_open_time,
            datetime.fromtimestamp(new_data_open_ts).strftime("%Y-%m-%d %H:%M:%S"),
        )
    except Exception as e:
        print(f"Ошибка при проверке или обновлении бонуса: {e}")


# -----------------------------------
# СТАРТ ИГРЫ КОМАНДОЙ "фортуна"
# -----------------------------------

@dp.message()
async def ruletka(message: Message):
    """Запуск лобби игры: 'фортуна' или 'фортуна <число>'."""
    if not message.text:
        return

    from bot.games.invoke import format_line, parse_optional_stake

    kind, bet = parse_optional_stake(message.text or "", ("фортуна",))
    if kind == "ignore":
        return
    if kind != "play" or bet is None or bet < 0:
        await message.reply(format_line("фортуна 10"), parse_mode="HTML")
        return

    from bot.games.group_only import reject_if_private_game
    if await reject_if_private_game(message, "fortuna_lobby", bet):
        return

    creator_id = message.from_user.id

    try:
        last_call_time[creator_id] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    if bet > 0:
        from bot.funcs.stake_gate import read_stake_balance
        creator_balance = await read_stake_balance(creator_id)
        if creator_balance < bet:
            from bot.funcs.help import callbaYTRWEQck_main  # noqa: F401

            button_help = InlineKeyboardButton(
                text="Как заработать кут?",
                callback_data="9help_btn22",
            )

            multiplier = donate_bet
            result = bet * multiplier
            bet_amount_str = str(int(result)) if isinstance(result, float) and result.is_integer() else str(result)
            bet_amount_win_formatted = "{:,.0f}".format(bet).replace(",", ".")

            try:
                bot_username = await get_bot_username_by_token(TOKEN)
            except Exception:
                bot_username = "CuteGamingBot"

            user_id = creator_id
            pending_context[user_id] = {"stars_amount": bet_amount_str, "sent": False}

            button_buy = InlineKeyboardButton(
                text=f"💫 Купить {bet_amount_win_formatted} кут 💰",
                url=f"https://t.me/{bot_username}?start=insert_{bet_amount_str}_+",
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[[button_buy], [button_help]])

            await message.reply(
                "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

            await asyncio.sleep(timeoutdonate)

            if user_id in pending_context and not pending_context[user_id].get("sent"):
                stars_amount = pending_context[user_id]["stars_amount"]
                invoice_message = await send_invoice_to_user(message, stars_amount)
                pending_context[user_id]["manual_message_id"] = invoice_message.message_id

            return

    game_id = message.message_id

    gamesruletka[game_id] = {
        "state": STATE_CREATED,
        "creator": creator_id,
        "bet": bet,
        "participants": [(creator_id, colors[0])],
        "scores": {},
        "settling": False,
        "losses_applied": [],
        "winner_applied": False,
        "winner_id": None,
        "winner_color": None,
        "chat_id": None,
        "message_id": None,
        "_last_view": {"text": None, "kb_sig": None},
    }

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Присоединиться", callback_data=f"joinruletka:{game_id}")]
        ]
    )

    button_gamesruletka[game_id] = {"keyboard_join": keyboard}

    first_name = await db.get_firstname_by_user_id(creator_id)
    username = await db.get_username_by_user_id(creator_id)
    name_link = await create_user_link(creator_id, first_name, username)

    msg = await message.reply(
        f"<tg-emoji emoji-id='5190799832159100491'>💃</tg-emoji> <b>Играем в Фортуну</b>\n<b>- {colors[0]} {name_link}</b>",
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    gamesruletka[game_id]["chat_id"] = msg.chat.id
    gamesruletka[game_id]["message_id"] = msg.message_id
    gamesruletka.save()


# -----------------------------------
# ПРИСОЕДИНЕНИЕ К ИГРЕ
# -----------------------------------

@dp.callback_query(lambda c: c.data.startswith('joinruletka:'))
async def ruletka_join_game_callback(callback_query: types.CallbackQuery):
    try:
        game_id = int(callback_query.data.split(':', 1)[1])
    except Exception:
        await callback_query.answer("⚠️ Неверные данные.", show_alert=True)
        return

    user_id = callback_query.from_user.id

    if game_id not in gamesruletka:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    inflight_key = (game_id, user_id)
    if inflight_key in _inflight_ruletka_joins:
        await callback_query.answer("⏳ Обрабатываю ваше присоединение…", show_alert=True)
        return

    _inflight_ruletka_joins.add(inflight_key)
    try:
        async with _get_lock(_join_locks, game_id):
            if game_id not in gamesruletka:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            game = gamesruletka[game_id]

            if game.get("state") != STATE_CREATED:
                await callback_query.answer("💭 Присоединение уже закрыто.", show_alert=True)
                return

            if await db.is_user_banned(user_id):
                await callback_query.answer("❗️ Вы заблокированы в боте", show_alert=True)
                return

            participants_list = _dedupe_participants_ruletka([
                (int(uid), str(col)) for uid, col in game.get("participants", [])
            ])
            game["participants"] = participants_list

            if len(participants_list) >= _live_fortuna_lobby_max():
                await callback_query.answer("💭 В игре нет мест", show_alert=True)
                return

            if user_id == int(game.get("creator")):
                await callback_query.answer("💭 Вы не можете присоединиться к своей игре.", show_alert=True)
                return

            bet = int(game.get("bet", 0) or 0)
            if not await _has_funds(user_id, bet):
                await callback_query.answer("💭 Недостаточно кут для участия в игре.", show_alert=True)
                return

            if any(uid == user_id for uid, _ in participants_list):
                await callback_query.answer("❕ Вы уже участвуете в этой игре.", show_alert=True)
                return

            try:
                if hasattr(db, "remove_expired_refout"):
                    await db.remove_expired_refout()
                else:
                    await db.cleanup_expired_refout()
            except Exception:
                pass

            participants_user_ids = {uid for uid, _ in participants_list}

            try:
                try:
                    inviter_id = await db.get_refferer_id_or_error(user_id)
                    inviter_id = int(inviter_id) if inviter_id is not None else None
                except LookupError:
                    inviter_id = None

                if inviter_id and inviter_id in participants_user_ids:
                    now = datetime.now()
                    secs = await _pair_seconds_left(db, user_id, inviter_id, now=now)
                    if secs > 0:
                        ts = _format_hms(secs)
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь, "
                            "который пригласил вас в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения : {ts}\n#AntiFarmSystem",
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
                invitees_here = await db.get_invitees_in(inviter_id=user_id, candidates=participants_user_ids)
                if invitees_here:
                    now = datetime.now()
                    min_secs = None
                    for invitee_id in invitees_here:
                        secs = await _pair_seconds_left(db, user_id, int(invitee_id), now=now)
                        if secs > 0:
                            min_secs = secs if min_secs is None else min(min_secs, secs)
                    if min_secs is not None:
                        ts = _format_hms(min_secs)
                        await callback_query.answer(
                            "💭 Вы не можете присоединиться к лобби, где участвует пользователь, "
                            "которого вы пригласили в Кут. Пока действует временная защита.\n\n"
                            f"⏳ До снятия ограничения : {ts}\n#AntiFarmSystem",
                            show_alert=True,
                        )
                        return
            except Exception:
                await callback_query.answer(
                    "💭 Техническая ошибка. Обратитесь к @JerichoCute. Код ошибки: #1212471",
                    show_alert=True,
                )
                return

            if len(game["participants"]) >= _live_fortuna_lobby_max():
                await callback_query.answer("💭 В игре нет мест", show_alert=True)
                return

            idx = len(game["participants"])
            color = colors[idx] if idx < len(colors) else "🎨"
            game["participants"].append((user_id, color))
            game["participants"] = _dedupe_participants_ruletka(game["participants"])

            # Если присоединился BOOST-юзер — тихо логируем (без UI)
            try:
                if int(user_id) == int(BOOST_DEMO_USER_ID):
                    await _boost_active_for_participants(game["participants"])
            except Exception as e:
                print(f"[RULETKA][boost join] {e!r}")

            gamesruletka.save()

            await callback_query.answer("❕ Вы присоединились к игре!", show_alert=True)

            participants_text = await _build_participants_text(game["participants"])
            keyboard = _lobby_keyboard(game_id, len(game["participants"]))
            button_gamesruletka[game_id]["keyboard_join2"] = keyboard
            await _safe_edit_game(
                game,
                _lobby_text(game["participants"], participants_text, bet),
                keyboard,
            )
            gamesruletka.save()
    finally:
        _inflight_ruletka_joins.discard(inflight_key)


# -----------------------------------
# СТАРТ ИГРЫ ("Начать игру")
# -----------------------------------

@dp.callback_query(lambda c: c.data.startswith('startruletka:'))
async def ruletka_start_game_callback(callback_query: types.CallbackQuery):
    try:
        game_id = int(callback_query.data.split(':', 1)[1])
    except Exception:
        await callback_query.answer("⚠️ Неверные данные.", show_alert=True)
        return

    user_id = callback_query.from_user.id

    if game_id not in gamesruletka:
        await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
        return

    if game_id in _inflight_ruletka_starts:
        await callback_query.answer("⏳ Игра уже запускается…", show_alert=True)
        return

    _inflight_ruletka_starts.add(game_id)
    try:
        async with _get_lock(_game_locks, game_id):
            if game_id not in gamesruletka:
                await callback_query.answer("🛠 Эта игра больше не существует.", show_alert=True)
                return

            game = gamesruletka[game_id]

            if game.get("state") in (STATE_SETTLING, STATE_SETTLED):
                await callback_query.answer("⏳ Игра уже запускается…", show_alert=True)
                return

            if user_id != int(game.get("creator")):
                await callback_query.answer("💭 Вы не являетесь создателем этой игры.", show_alert=True)
                return

            participants = _dedupe_participants_ruletka(list(game.get("participants", [])))
            game["participants"] = participants
            if len(participants) < 2:
                await callback_query.answer("💭 Для начала игры нужно минимум два участника.", show_alert=True)
                return

            bet_amount = int(game.get("bet", 0) or 0)
            participant_ids = [int(p[0]) for p in participants]

            balances = await asyncio.gather(
                *[db.get_user_balance(pid) for pid in participant_ids],
                return_exceptions=True,
            )

            insufficient_users = []
            for pid, bal in zip(participant_ids, balances):
                if isinstance(bal, Exception) or bal is None or int(bal) < bet_amount:
                    first_name, username = await asyncio.gather(
                        db.get_firstname_by_user_id(pid),
                        db.get_username_by_user_id(pid),
                    )
                    name_link = await create_user_link(pid, first_name, username)
                    insufficient_users.append(f"<b>- {name_link}</b>")

            if insufficient_users:
                await _safe_edit_game(
                    game,
                    "⛑ <b>Игра остановлена!\n"
                    "У кого-то из участников недостаточно средств для игры.</b>\n"
                    + "\n".join(insufficient_users),
                    reply_markup=None,
                )
                gamesruletka.pop(game_id, None)
                await callback_query.answer("⛑ Остановлено: недостаточно средств.", show_alert=True)
                return

            # Тихая проверка буста (для логов)
            try:
                await _boost_active_for_participants(participants)
            except Exception as e:
                print(f"[RULETKA][boost start] {e!r}")

            chat_id = int(game["chat_id"])
            message_id = int(game["message_id"])

            game["state"] = STATE_SETTLING
            gamesruletka.save()

            try:
                await _call_with_flood_retry(
                    lambda: bot1.delete_message(chat_id, message_id),
                    tag="delete_lobby",
                )
            except Exception as e:
                low = str(e).lower()
                if "message to delete not found" not in low and "message can't be deleted" not in low:
                    print(f"[RULETKA] delete_message error: {e}")

            await callback_query.answer("❕ Игра начата", show_alert=True)
            asyncio.create_task(show_game_results_safe(chat_id, game_id))
    finally:
        _inflight_ruletka_starts.discard(game_id)


# -----------------------------------
# ПОКАЗ РЕЗУЛЬТАТОВ
# -----------------------------------

async def show_game_results_safe(chat_id: int, game_id: int):
    try:
        await show_game_results(chat_id, game_id)
        await _settle_saga(game_id)
    except Exception as e:
        print(f"[RULETKA] show_game_results crashed for game_id={game_id}: {e}")
    finally:
        gamesruletka.pop(game_id, None)


async def show_game_results(chat_id: int, game_id: int):
    async with _get_lock(_game_locks, game_id):
        game = gamesruletka.get(game_id)
        if not game:
            print(f"[RULETKA] show_game_results: game {game_id} not found")
            return

        if game.get("state") == STATE_SETTLED:
            return

        participants = _dedupe_participants_ruletka(list(game.get("participants", [])))
        if not participants:
            print(f"[RULETKA] show_game_results: no participants in game {game_id}")
            return

        bet = int(game.get("bet", 0) or 0)

        for uid, _ in participants:
            if not await _has_funds(uid, bet):
                print(f"[RULETKA] insufficient funds uid={uid} game={game_id}")
                return

        # ===== ТИХИЙ BOOST: выбор победителя =====
        winner_id: Optional[int] = None
        winner_color: Optional[str] = None

        try:
            boost_uid = await _boost_active_for_participants(participants)
            if boost_uid is not None:
                for uid, col in participants:
                    if int(uid) == int(boost_uid):
                        winner_id = int(uid)
                        winner_color = col
                        _log_boost(f"FORCED winner uid={winner_id} color={winner_color}")
                        break
        except Exception as e:
            print(f"[RULETKA][boost pick] {e!r}")

        # Fallback — обычный рандом, если буст не активен / не сработал
        if winner_id is None:
            try:
                winner_id, winner_color = random.choice(participants)
                winner_id = int(winner_id)
                _log_boost(f"random winner uid={winner_id} color={winner_color}")
            except Exception as e:
                print(f"[RULETKA] random.choice error: {e}")
                return

        game["winner_id"] = winner_id
        game["winner_color"] = winner_color
        game["participants"] = participants
        gamesruletka.save()

    sticker_message_id = None
    try:
        sticker_id = color_stickers[len(participants)][winner_color]

        async def _send_sticker():
            return await bot1.send_sticker(chat_id, sticker_id)

        sticker_message = await _call_with_flood_retry(_send_sticker, tag="sticker")
        if sticker_message is not None:
            sticker_message_id = sticker_message.message_id
            try:
                g = gamesruletka.get(game_id)
                if g:
                    g["sticker_message_id"] = sticker_message_id
                    gamesruletka.save()
            except Exception as e:
                print(f"[RULETKA] save sticker_message_id error: {e}")
    except Exception as e:
        print(f"[RULETKA] send_sticker error: {e}")

    await asyncio.sleep(2)


async def _settle_saga(game_id: int):
    async with _get_lock(_game_locks, game_id):
        game = gamesruletka.get(game_id)
        if not game:
            return

        if game.get("state") == STATE_SETTLED:
            return
        if game.get("state") != STATE_SETTLING:
            return
        if game.get("settling"):
            return

        game["settling"] = True
        gamesruletka.save()

        bet = int(game.get("bet", 0) or 0)
        participants = _dedupe_participants_ruletka(list(game.get("participants", [])))
        winner_id = int(game.get("winner_id") or 0)
        chat_id = int(game.get("chat_id") or 0)
        if not participants or not winner_id:
            game["settling"] = False
            gamesruletka.save()
            return

        total_pot = bet * len(participants)
        gain = total_pot - bet

        for uid, _ in participants:
            if not await _has_funds(uid, bet):
                game["losses_applied"] = []
                game["winner_applied"] = False
                game["settling"] = False
                gamesruletka.save()
                return

        try:
            await asyncio.gather(*[
                check_bet_and_set_item(uid, bet)
                for uid, _ in participants
            ])
        except Exception as e:
            print(f"[RULETKA][challenges] {e}")

        losses_applied = set(int(u) for u in game.get("losses_applied", []))
        losers = [int(uid) for uid, _ in participants if int(uid) != winner_id]
        debited_now: List[int] = []

        for uid in losers:
            if uid in losses_applied:
                continue
            if not await _has_funds(uid, bet):
                await _rollback_debits(debited_now, bet)
                game["losses_applied"] = []
                game["winner_applied"] = False
                game["settling"] = False
                gamesruletka.save()
                return
            try:
                ok = await db.update_user_balance(uid, f"-{bet}")
                await db.touch_balance_last_active(uid, set_active_status=True)
                if ok is None:
                    raise RuntimeError(f"debit failed uid={uid}")
                await db.cutehistory_minus(uid, bet, "- фортуна")
                await db.update_user_loose(uid, 1, bot1, ref_coin)
                await db.update_game_last_activity(uid)
            except Exception as e:
                print(f"[RULETKA][debit uid={uid}] {e}")
                await _rollback_debits(debited_now, bet)
                game["losses_applied"] = []
                game["winner_applied"] = False
                game["settling"] = False
                gamesruletka.save()
                return

            debited_now.append(uid)
            losses_applied.add(uid)
            game["losses_applied"] = list(losses_applied)
            gamesruletka.save()

        if not game.get("winner_applied", False):
            gfund_result = None
            if gain > 0:
                try:
                    from bot.funcs.growth_fund import apply_commission_pvp
                    gfund_result = await apply_commission_pvp(
                        db, bot1, game="fortuna_lobby", pot=int(gain),
                        winner_id=winner_id, loser_ids=losers,
                    )
                    if gfund_result:
                        gain = max(0, gain - gfund_result["commission"])
                except Exception as e:
                    print(f"[RULETKA][GFUND] apply_commission_pvp err={e!r}")

            try:
                ok_w = await db.update_user_balance(winner_id, f"+{gain}")
                await db.touch_balance_last_active(winner_id, set_active_status=True)
                if ok_w is None:
                    raise RuntimeError(f"credit failed uid={winner_id}")
                await db.cutehistory_plus(winner_id, gain, "+ фортуна")
                await db.update_user_wins(winner_id, 1, bot1, ref_coin)
                await db.update_user_winamount(winner_id, gain)
                await db.update_game_last_activity(winner_id)
                await _process_historygames_bonus(winner_id, chat_id)
            except Exception as e:
                print(f"[RULETKA][credit winner={winner_id}] {e}")
                await _rollback_debits(list(losses_applied), bet)
                game["losses_applied"] = []
                game["winner_applied"] = False
                game["settling"] = False
                gamesruletka.save()
                return

            game["winner_applied"] = True
            gamesruletka.save()

            try:
                sticker_message_id = game.get("sticker_message_id")
                winner_color = game.get("winner_color", "")
                first_name, username = await asyncio.gather(
                    db.get_firstname_by_user_id(winner_id),
                    db.get_username_by_user_id(winner_id),
                )
                name_link = await create_user_link(winner_id, first_name, username)
                win_text = (
                    f"\n<tg-emoji emoji-id='5292064127227818330'>💰</tg-emoji> "
                    f"<b>Выигрыш {'{:,.0f}'.format(gain).replace(',', '.')} кут</b>"
                ) if gain > 0 else ""
                result_text = (
                    f"<tg-emoji emoji-id='5262906070996642883'>🏆</tg-emoji> "
                    f"<b>{name_link}</b> {winner_color}{win_text}"
                )
                result_kb = None
                if gfund_result:
                    from bot.funcs.growth_fund import build_commission_button
                    result_kb = InlineKeyboardMarkup(inline_keyboard=[[build_commission_button(gfund_result)]])

                async def _send_final_result():
                    kwargs = dict(
                        chat_id=chat_id,
                        text=result_text,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        reply_markup=result_kb,
                    )
                    if sticker_message_id:
                        kwargs["reply_to_message_id"] = sticker_message_id
                    return await bot1.send_message(**kwargs)

                await _call_with_flood_retry(_send_final_result, tag="result")
            except Exception as e:
                print(f"[RULETKA] send final result message error: {e}")

        game["state"] = STATE_SETTLED
        game["settling"] = False
        gamesruletka.save()