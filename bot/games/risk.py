# -*- coding: utf-8 -*-
"""
Риск - полная версия с интеграцией Jericho и маскировочными механиками.
Локально:
  - demo-режим: иногда подменяет WIN → HOME (проигрыш) и прерывает серии побед.
  - 0demo-режим: иногда подменяет LOSE → WIN (выигрыш) и прерывает серии проигрышей.
Долг списывается через force_repay_debt при любом проигрыше в 0demo-режиме.
ВАЖНО: даже при наличии demo/0demo пользователь НЕ может начать игру,
если его основной баланс (или баланс челленджа) меньше ставки.
"""

import asyncio, random, re, time
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, getcontext
from typing import Dict, Set, Tuple, List, Optional

from aiogram import types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramRetryAfter, TelegramNetworkError

from bot.games.group_only import reject_if_private_game
from main import (
    bot1, dp, db,
    TECH_CHAT_ID, create_user_link,
    user_message_risk, active_games_risk,
    pending_context, send_invoice_to_user,
    gc_process_bet, LazyGameStore
)

from bot.config.config import (
    TOKEN, timeoutdonate, donate_bet, ref_coin, RISK_MIN_BET, RISK_MAX_BET, _RISK_MULT_DEFAULT
)

# Импорт функций Jericho
from main import (
    jericho_check, welcome_back_gift, newbie_safety_net, force_repay_debt
)

from bot.funcs.tech_home_log import safe_send_tech_log

try:
    from bot.funcs.func import get_bot_username_by_token
except Exception:
    async def get_bot_username_by_token(token: str) -> str:
        return "CuteGamingBot"

processed_actions_risk = LazyGameStore("processed_actions_risk")


async def _after_risk_closed(owner_id: int, msg_id: Optional[int] = None, chat_id=None):
    """Конец партии: safety-net + tip/личка онбординга."""
    await newbie_safety_net(owner_id)
    if chat_id is None:
        st = active_games_risk.get(owner_id) or {}
        if isinstance(st, dict):
            chat_id = st.get("chat_id")
            if msg_id is None:
                try:
                    msg_id = int(st.get("message_id") or 0) or None
                except Exception:
                    msg_id = None
    try:
        from bot.funcs.onboarding import onboarding_notify_game_finished
        await onboarding_notify_game_finished(owner_id, message_id=msg_id, chat_id=chat_id)
    except Exception as e:
        print(f"[RISK] onboarding tip notify: {e!r}")

try:
    from main import get_random_eagle_emoji_id
except Exception:
    def get_random_eagle_emoji_id():
        return "6028346797368283073"

getcontext().prec = 28

# ---------- щиток Риска ----------
DEBUG_RISK = True
DEBUG_RISK_FIELD = True
SESSION_TTL = 20 * 60
USER_CLICK_COOLDOWN = 0.40
DEDUP_TTL = 60 * 60

# Маскировочные механики
DEMO_MASK_LOSS_PROB = 0.12               # вероятность подмены WIN → HOME в demo-режиме
DEMO_STREAK_BREAK = 3                    # после скольких побед подряд принудительно HOME
ZERO_MASK_WIN_PROB = 0.12                # вероятность подмены LOSE → WIN в 0demo-режиме
ZERO_STREAK_BREAK = 3                    # после скольких проигрышей подряд принудительно WIN

# --------------------------------------

def _load_risk_step_multiplier() -> Decimal:
    try:
        from bot.config.config import RISK_STEP_MULTIPLIER as _CFG
        raw = str(_CFG).strip()
        x = Decimal(raw)
        if (not x.is_finite()) or x <= 0:
            return _RISK_MULT_DEFAULT
        return x
    except Exception:
        return _RISK_MULT_DEFAULT

RISK_STEP_MULTIPLIER = _load_risk_step_multiplier()

_RISK_HOME_CHANCE_DEFAULT = Decimal("0.15")

def _load_risk_home_chance() -> Decimal:
    try:
        from bot.config.config import RISK_HOME_CHANCE as _CFG
        raw = str(_CFG).strip()
        x = Decimal(raw)
        if (not x.is_finite()) or x < 0:
            return _RISK_HOME_CHANCE_DEFAULT
        if x > 1:
            x = x / Decimal("100")
        if x < 0:
            x = Decimal("0")
        if x > 1:
            x = Decimal("1")
        return x
    except Exception:
        return _RISK_HOME_CHANCE_DEFAULT

RISK_HOME_CHANCE = _load_risk_home_chance()

RAN_EMOJIS_MSG = (
    "<tg-emoji emoji-id='5472389656295253790'>🍃</tg-emoji>",
    "<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji>",
    "<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji>"
)

_EMOJI_ID_MAP = {
    "🍃": "5472389656295253790",
    "🌿": "5449850741667668411",
    "🌱": "5449885771420934013",
    "🔥": "5251308237663264052",
    "🧱": "5370842086658546991",
}

EMOJI_START = "<tg-emoji emoji-id='5438449312893792440'>🌵</tg-emoji>"
EMOJI_LOSE = "<tg-emoji emoji-id='5251308237663264052'>🔥</tg-emoji>"
EMOJI_HOME = "<tg-emoji emoji-id='5370842086658546991'>🧱</tg-emoji>"

def EMOJI_END() -> str:
    return f"<tg-emoji emoji-id='{get_random_eagle_emoji_id()}'>🕊</tg-emoji>"

CELL_WIN_SECRET = "ㅤ"
CELL_LOSE_SECRET = "     "
CELL_HOME_SECRET = "\u200b"

SHOW_LOSE = "🔥"
SHOW_HOME = "🧱"

def _is_win_secret(v: str) -> bool:
    return v == CELL_WIN_SECRET

def _is_lose_secret(v: str) -> bool:
    return v == CELL_LOSE_SECRET

def _is_home_secret(v: str) -> bool:
    return v == CELL_HOME_SECRET

def _ts() -> str:
    return time.strftime("%H:%M:%S", time.localtime())

def dbg(stage: str, **kw) -> None:
    if not DEBUG_RISK:
        return
    parts = [f"[{_ts()}][RISK][{stage}]"] + [f"{k}={v}" for k, v in kw.items()]
    try:
        print(" ".join(parts), flush=True)
    except Exception:
        pass

def dbg_err(stage: str, err: Exception) -> None:
    if not DEBUG_RISK:
        return
    try:
        import traceback
        print(
            f"[{_ts()}][RISK][ERROR][{stage}] {err}\n"
            f"{''.join(traceback.format_exception(type(err), err, err.__traceback__))}",
            flush=True
        )
    except Exception:
        pass

def _dbg_field(secret_field: List[List[str]], *, seed: int, user_id: int, chat_id: int, rev: int):
    if not DEBUG_RISK_FIELD:
        return
    try:
        print(
            f"\n[{_ts()}][RISK][FIELD] seed={seed} uid={user_id} "
            f"chat_id={chat_id} rev={rev} home={RISK_HOME_CHANCE} mult={RISK_STEP_MULTIPLIER}",
            flush=True
        )
        for r, row in enumerate(secret_field):
            line = []
            for v in row:
                if _is_win_secret(v):
                    t = "WIN"
                elif _is_lose_secret(v):
                    t = "LOSE"
                elif _is_home_secret(v):
                    t = "HOME"
                else:
                    t = "???"
                line.append(t)
            print(f"[{_ts()}][RISK][FIELD] row={r + 1:02d} -> " + " | ".join(line), flush=True)
        print("", flush=True)
    except Exception:
        pass

def _dbg_click_outcome(*, row: int, col: int, secret_val: str):
    if not DEBUG_RISK_FIELD:
        return
    if _is_win_secret(secret_val):
        out = "WIN"
    elif _is_lose_secret(secret_val):
        out = "LOSE"
    elif _is_home_secret(secret_val):
        out = "HOME"
    else:
        out = "???"
    print(f"[{_ts()}][RISK][CLICK] row={row + 1} col={col + 1} outcome={out}", flush=True)

_risk_session_locks: Dict[int, asyncio.Lock] = {}
_risk_inflight: Set[Tuple[int, int]] = set()
_last_click: Dict[int, float] = {}
_user_start_locks: Dict[int, asyncio.Lock] = {}
_processed_ts: Dict[str, float] = {}
_chat_money_locks: Dict[int, asyncio.Lock] = {}

def _now_mono() -> float:
    return time.monotonic()

def _get_user_lock(user_id: int) -> asyncio.Lock:
    lock = _user_start_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_start_locks[user_id] = lock
        dbg("LOCK_CREATE_USER", user_id=user_id)
    return lock

def _get_session_lock(msg_id: int) -> asyncio.Lock:
    lock = _risk_session_locks.get(msg_id)
    if lock is None:
        lock = asyncio.Lock()
        _risk_session_locks[msg_id] = lock
        dbg("LOCK_CREATE_SESSION", msg_id=msg_id)
    return lock

def _get_chat_lock(chat_id: int) -> asyncio.Lock:
    lock = _chat_money_locks.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        _chat_money_locks[chat_id] = lock
        dbg("LOCK_CREATE_CHAT", chat_id=chat_id)
    return lock

def _fmt_int(n: int) -> str:
    try:
        return "{:,.0f}".format(int(n)).replace(",", ".")
    except Exception:
        return str(n)

def _safe_int(val, default=0) -> int:
    try:
        return int(val)
    except Exception:
        return default

def _dec(val) -> Decimal:
    return Decimal(str(val))

def _str_dec(d: Decimal) -> str:
    return format(d, "f")

def _to_int_floor(x: Decimal) -> int:
    try:
        if x.is_nan():
            return 0
    except Exception:
        return 0
    return max(0, int(x.quantize(0, rounding=ROUND_DOWN)))

def _profit_now(game_data: dict) -> int:
    if not game_data.get("first_success"):
        return 0
    bet = _dec(game_data.get("bet", 0))
    win = _dec(game_data.get("win_amount", bet))
    pure = win - bet
    return max(1, _to_int_floor(pure))

def _store_save_safe(store, stage: str):
    try:
        if hasattr(store, "save"):
            store.save()
            dbg(stage, result="OK")
        else:
            dbg(stage, result="SKIP", reason="no_save_method")
    except Exception as e:
        dbg(stage, result="FAIL", err=str(e))

def _mark_action_processed(key: str):
    processed_actions_risk[key] = 1
    _processed_ts[key] = _now_mono()
    _store_save_safe(processed_actions_risk, "DEDUP_SAVE")
    dbg("DEDUP_SET", key=key)

def _is_action_processed(key: str) -> bool:
    exists = key in processed_actions_risk
    dbg("DEDUP_CHECK", key=key, exists=exists)
    return exists

def _dedup_gc():
    now = _now_mono()
    to_del = [k for k, ts in _processed_ts.items() if (now - ts) > DEDUP_TTL]
    if not to_del:
        return
    for k in to_del:
        _processed_ts.pop(k, None)
        try:
            processed_actions_risk.pop(k, None)
        except Exception:
            pass
    _store_save_safe(processed_actions_risk, "DEDUP_GC")
    dbg("DEDUP_GC_DONE", removed=len(to_del), remain=len(processed_actions_risk))

async def _safe_edit_text(
    message: Optional[types.Message],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = ParseMode.HTML,
    disable_preview: bool = True
):
    try:
        if message is None:
            return
        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_preview
        )
    except (TelegramBadRequest, TelegramAPIError) as e:
        if "message is not modified" in str(e).lower():
            return
        try:
            await asyncio.sleep(0.15)
            await message.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_preview
            )
        except Exception:
            pass
    except Exception:
        pass

async def _safe_edit_reply_markup(message: types.Message, reply_markup: InlineKeyboardMarkup):
    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
    except (TelegramBadRequest, TelegramAPIError) as e:
        if "message is not modified" in str(e).lower():
            return
        try:
            await asyncio.sleep(0.15)
            await message.edit_reply_markup(reply_markup=reply_markup)
        except Exception:
            pass
    except Exception:
        pass

async def _mark_user_game_activity(user_id: int, reason: str = "") -> None:
    try:
        await db.touch_balance_last_active(int(user_id), set_active_status=True)
        dbg("ACTIVITY_TOUCH_OK", user_id=user_id, reason=reason)
    except Exception as e:
        dbg_err(f"ACTIVITY_TOUCH_ERR_{reason}", e)

async def _gc_call(user_id: int, chat_id: int, bet: int, outcome: str, label: str):
    print(f"[GC_HOOK] BEFORE gc_process_bet ({label})")
    try:
        res = await gc_process_bet(user_id=user_id, event_chat_id=chat_id, bet=bet, outcome=outcome)
        print("[GC_HOOK] AFTER gc_process_bet, res =", res)
    except Exception as e:
        import traceback
        print(f"[GC_HOOK][EXC] ({label})", e)
        print(traceback.format_exc())

async def _chat_get_balance(chat_id: int) -> int:
    variants = [
        ("get_chat_balance(bot, chat)", lambda: db.get_chat_balance(bot1, chat_id)),
        ("get_chat_balance(chat)", lambda: db.get_chat_balance(chat_id)),
    ]
    for name, fn in variants:
        try:
            v = await fn()
            return _safe_int(v, 0)
        except TypeError:
            continue
        except Exception as e:
            dbg("CHAT_GET_FAIL", chat_id=chat_id, variant=name, err=repr(e))
    return 0

async def _chat_credit_best_effort(chat_id: int, amount: int) -> bool:
    amt = int(amount)
    if amt <= 0:
        return True
    variants = [
        ("update_chat_balance(bot, chat, +amt)", lambda: db.update_chat_balance(bot1, chat_id, amt)),
        ("update_chat_balance(chat, +amt)", lambda: db.update_chat_balance(chat_id, amt)),
        ("update_chat_balance(chat, bot, +amt)", lambda: db.update_chat_balance(chat_id, bot1, amt)),
    ]
    for name, fn in variants:
        try:
            await fn()
            dbg("CHAT_PLUS_OK", chat_id=chat_id, amt=amt, variant=name)
            return True
        except TypeError:
            continue
        except Exception as e:
            dbg("CHAT_PLUS_FAIL", chat_id=chat_id, amt=amt, variant=name, err=repr(e))
    return False

async def _chat_debit_best_effort(chat_id: int, amount: int) -> bool:
    amt = int(amount)
    if amt <= 0:
        return True
    variants = [
        ("update_chat_balance_minus(chat, amt)", lambda: db.update_chat_balance_minus(chat_id, amt)),
        ("update_chat_balance_minus(bot, chat, amt)", lambda: db.update_chat_balance_minus(bot1, chat_id, amt)),
        ("update_chat_balance_minus(chat, bot, amt)", lambda: db.update_chat_balance_minus(chat_id, bot1, amt)),
        ("update_chat_balance(bot, chat, -amt)", lambda: db.update_chat_balance(bot1, chat_id, -amt)),
        ("update_chat_balance(chat, -amt)", lambda: db.update_chat_balance(chat_id, -amt)),
        ("update_chat_balance(chat, bot, -amt)", lambda: db.update_chat_balance(chat_id, bot1, -amt)),
    ]
    any_ok = False
    last_err = None
    for name, fn in variants:
        try:
            await fn()
            dbg("CHAT_MINUS_OK", chat_id=chat_id, amt=amt, variant=name)
            any_ok = True
            break
        except TypeError:
            continue
        except Exception as e:
            last_err = e
            dbg("CHAT_MINUS_FAIL", chat_id=chat_id, amt=amt, variant=name, err=repr(e))
    if not any_ok:
        dbg("CHAT_MINUS_ALL_FAILED", chat_id=chat_id, amt=amt, err=repr(last_err))
        return False
    try:
        b1 = await _chat_get_balance(chat_id)
        await asyncio.sleep(0.08)
        b2 = await _chat_get_balance(chat_id)
        dbg("CHAT_MINUS_VERIFY", chat_id=chat_id, before=b1, after=b2, amt=amt)
    except Exception:
        pass
    return True

async def _user_delta(user_id: int, delta: int) -> bool:
    d = int(delta)
    if d == 0:
        return True
    try:
        s = f"+{d}" if d > 0 else str(d)
        await db.update_user_balance(int(user_id), s)
        return True
    except TypeError:
        pass
    except Exception as e:
        dbg("USER_DELTA_FAIL", user_id=user_id, delta=d, err=repr(e))
    try:
        cur = _safe_int(await db.get_user_balance(int(user_id)), 0)
        new_val = cur + d
        if new_val < 0:
            new_val = 0
        await db.update_user_balance(int(user_id), int(new_val))
        return True
    except Exception as e:
        dbg("USER_SET_FAIL", user_id=user_id, delta=d, err=repr(e))
        return False

async def _home_log_risk_failed(*, bot, user_id: int, loss: int) -> None:
    if not TECH_CHAT_ID:
        return
    try:
        receiver_name = ""
        receiver_username = ""
        try:
            receiver_name = await db.get_user_first_name(user_id) or ""
        except Exception:
            pass
        try:
            receiver_username = await db.get_username_by_user_id(user_id) or ""
        except Exception:
            pass

        # Вызов create_user_link оставляем (может иметь побочные эффекты), но для кнопок используем имя напрямую
        name_link1 = await create_user_link(int(user_id), receiver_name, receiver_username)
        await db.add_home_amount(user_id=user_id, amount=loss)

        # Баланс запрашиваем через переданный объект bot, а не через глобальный bot1
        chat_balance = await db.get_chat_balance(bot, -1003855337972)

        # HTML-эмодзи – единственный текст сообщения
        emoji_html = '<tg-emoji emoji-id="5438449312893792440">🌴</tg-emoji>'

        # Кнопка с именем: если есть username → ссылка на профиль, иначе → заглушка со ⭐️
        if receiver_username and isinstance(receiver_username, str):
            profile_url = f"https://t.me/{receiver_username.strip()}"
            row_name_btn = InlineKeyboardButton(
                text=receiver_name or "Игрок",
                url=profile_url
            )
        else:
            row_name_btn = InlineKeyboardButton(
                text=receiver_name or "Игрок",
                callback_data="pass",
                icon_custom_emoji_id="6028338546736107668"   # ⭐️
            )

        inline_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Риск",
                        callback_data="pass",
                        icon_custom_emoji_id="6028346797368283073"  # ✈️
                    )
                ],
                [row_name_btn],
                [
                    InlineKeyboardButton(
                        text=f"+ {_fmt_int(loss)} на чёрный рынок",
                        callback_data="pass"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{_fmt_int(chat_balance)} кут доступно",
                        callback_data="pass"
                    )
                ]
            ]
        )

        # Лог в TECH_CHAT: chat not found не должен ронять партию.
        fallback_text = (
            f"<b>🌴 Риск [ <i>Рискнуть не получилось</i> ]</b>\n"
            f"<i>⭐️ {name_link1}</i>\n"
            f"<blockquote><b>+ {_fmt_int(loss)} на чёрный рынок</b></blockquote>\n"
            f"<blockquote><b>{_fmt_int(chat_balance)} кут доступно для выкупов</b></blockquote>"
        )
        await safe_send_tech_log(
            bot,
            int(TECH_CHAT_ID),
            html=emoji_html,
            reply_markup=inline_kb,
            fallback_html=fallback_text,
            tag="RISK][HOME_LOG_SEND",
        )

    except Exception as e:
        dbg_err("HOME_LOG_ERR", e)

def _make_seed(user_id: int, chat_id: int, rev: int) -> int:
    return (int(time.time() * 1000) ^ (user_id << 1) ^ (chat_id << 2) ^ (rev << 3)) & 0x7FFFFFFF

def _build_secret_field(seed: int, is_demo: bool = False, is_0demo: bool = False) -> List[List[str]]:
    """
    Генерирует секретное поле 10x1.
    - is_demo: только WIN и HOME (без LOSE).
    - is_0demo: только LOSE и HOME (без WIN).
    - иначе случайно WIN/LOSE с шансом HOME.
    """
    rng = random.Random(int(seed))
    field = [[" " for _ in range(1)] for _ in range(10)]
    home_p = float(RISK_HOME_CHANCE)
    home_p = max(0.0, min(1.0, home_p))
    for r in range(10):
        x = rng.random()
        if x < home_p:
            field[r][0] = CELL_HOME_SECRET
        else:
            if is_demo:
                field[r][0] = CELL_WIN_SECRET
            elif is_0demo:
                field[r][0] = CELL_LOSE_SECRET
            else:
                field[r][0] = CELL_WIN_SECRET if rng.choice([True, False]) else CELL_LOSE_SECRET
    return field

def _ui_cell_text(v: str) -> str:
    return " " if (not v or v == " ") else str(v)

def _btn(
    text: str,
    cb: str,
    *,
    style: Optional[str] = None,
    icon_custom_emoji_id: Optional[str] = None,
    url: Optional[str] = None
) -> InlineKeyboardButton:
    kwargs = {}
    if url:
        kwargs["url"] = url
    else:
        kwargs["callback_data"] = cb
    if style is not None:
        kwargs["style"] = style
    if icon_custom_emoji_id is not None:
        kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id
    try:
        return InlineKeyboardButton(text=text, **kwargs)
    except TypeError:
        if url:
            return InlineKeyboardButton(text=text, url=url)
        return InlineKeyboardButton(text=text, callback_data=cb)

def create_keyboard_risk(game_state: List[List[str]], game_data: dict) -> InlineKeyboardMarkup:
    rev = _safe_int(game_data.get("session_rev"), 0)
    owner = _safe_int(game_data.get("owner_id"), 0)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for row_idx, row in enumerate(game_state):
        line = []
        for col_idx, val in enumerate(row):
            text = " "
            emoji_id = _EMOJI_ID_MAP.get(val)
            cb = f"risk_actual_{rev}_{row_idx}_{col_idx}_{owner}"
            if emoji_id:
                line.append(InlineKeyboardButton(
                    text=text,
                    callback_data=cb,
                    icon_custom_emoji_id=emoji_id
                ))
            else:
                line.append(InlineKeyboardButton(text=" ", callback_data=cb))
        kb.inline_keyboard.append(line)
    if game_data.get("first_success"):
        can_take = _profit_now(game_data)
        kb.inline_keyboard.append([_btn(
            f"Можно вывести {_fmt_int(can_take)} кут",
            f"risk_msg_stub_{rev}_{owner}",
            style="success",
            icon_custom_emoji_id="6028338546736107668"
        )])
        kb.inline_keyboard.append([_btn("Закончить игру", f"risk_withdraw_{rev}_{owner}")])
    return kb

async def _deactivate_previous_risk_ui(user_id: int) -> None:
    try:
        prev_mid = user_message_risk.get(user_id)
        st = active_games_risk.get(user_id) or {}
        if not prev_mid or not st:
            return
        chat_id = st.get("chat_id")
        if not chat_id:
            return
        end_kb = InlineKeyboardMarkup(inline_keyboard=[[_btn("Игра завершена", "risk_end_stub", style="default")]])
        try:
            await bot1.edit_message_reply_markup(chat_id=int(chat_id), message_id=int(prev_mid), reply_markup=end_kb)
        except Exception:
            try:
                await bot1.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=int(prev_mid),
                    text=EMOJI_END(),
                    reply_markup=end_kb,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
    except Exception as e:
        dbg_err("DEACT_ERR", e)

async def _session_ttl_watcher(chat_id: int, msg_id: int, owner_id: int, ttl: int):
    try:
        await asyncio.sleep(ttl)
        st = active_games_risk.get(owner_id)
        if not st:
            return
        if _safe_int(st.get("message_id"), 0) != int(msg_id):
            return
        if st.get("closed"):
            return
        st["closed"] = True
        active_games_risk[owner_id] = st
        _store_save_safe(active_games_risk, "ACTIVE_SAVE_TTL")
        end_kb = InlineKeyboardMarkup(inline_keyboard=[[_btn("Игра завершена", "risk_end_stub", style="default")]])
        try:
            await bot1.edit_message_reply_markup(chat_id=int(chat_id), message_id=int(msg_id), reply_markup=end_kb)
        except Exception:
            try:
                await bot1.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=int(msg_id),
                    text=EMOJI_END(),
                    reply_markup=end_kb,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
        try:
            user_message_risk.pop(owner_id, None)
            _store_save_safe(user_message_risk, "USERMSG_SAVE_TTL")
        except Exception:
            pass
        _risk_session_locks.pop(int(msg_id), None)
        _dedup_gc()
        await _after_risk_closed(owner_id, msg_id, chat_id)
    except Exception as e:
        dbg_err("TTL_ERR", e)

async def _send_invoice_later(message: Message, user_id: int, stars_amount: str, delay: float):
    try:
        await asyncio.sleep(delay)
        ctx = pending_context.get(user_id)
        if ctx and not ctx.get("sent"):
            invoice_message = await send_invoice_to_user(message, stars_amount)
            pending_context[user_id]["manual_message_id"] = invoice_message.message_id
    except Exception:
        pass

_BET_RE = re.compile(r"(\d{1,18})")

def _extract_bet_from_text(text: str) -> Optional[int]:
    if not text:
        return None
    t = text.strip().lower()
    if not t.startswith("риск"):
        return None
    m = _BET_RE.search(t)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

# ======================================================================
#                                START
# ======================================================================
@dp.message()
async def risk(message: Message):
    text = (message.text or "").strip()
    if not text:
        return

    bet_amount = _extract_bet_from_text(text)
    if bet_amount is None:
        return

    if bet_amount < int(RISK_MIN_BET):
        await message.reply(
            f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Минимальная ставка {RISK_MIN_BET} кут.</b>",
            parse_mode="HTML"
        )
        return

    if await reject_if_private_game(message):
        return

    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)


    has_assignment = False
    is_free = False
    current_two = 0
    target_amount = 0
    gc_bet_limit = None

    try:
        gc_bet_limit = await db.gc_get_bet_limit_for_user(user_id)
    except Exception:
        gc_bet_limit = None

    try:
        assignment = await db.get_active_gc_assignment(user_id)
        if assignment and (str(assignment.get("status") or "").lower() == "active"):
            has_assignment = True
            try:
                is_free = bool(await db.gc_active_is_free(user_id))
            except Exception:
                is_free = False
            try:
                current_two = int(await db.gc_get_current_two_balance(user_id) or 0)
            except Exception:
                current_two = 0
            try:
                target_amount = int(assignment.get("target_amount") or 0)
            except Exception:
                target_amount = 0
    except Exception:
        pass

    from bot.funcs.group_balance_level import decide_gc_play_mode, format_game_max_bet_html
    gate = decide_gc_play_mode(
        bet=bet_amount,
        game_max_bet=int(RISK_MAX_BET),
        has_assignment=has_assignment,
        is_free=is_free,
        gc_bet_limit=gc_bet_limit,
    )
    if gate.get("mode") == "reject":
        await message.reply(
            format_game_max_bet_html(gate.get("max") or RISK_MAX_BET),
            parse_mode="HTML"
        )
        return
    is_free_play = gate.get("mode") == "free"

    # ─── ИНИЦИАЛИЗАЦИЯ НОВИЧКА ───
    try:
        if await db.get_newbie_expires_at(user_id) is None:
            from datetime import datetime, timedelta, timezone
            expires = datetime.now(timezone.utc) + timedelta(hours=random.uniform(0.5, 24.0))
            await db.set_newbie_expires_at(user_id, expires)
            print(f"[RISK] Установлен newbie_expires_at для {user_id}: {expires}")
    except Exception as e:
        print(f"[RISK] Ошибка инициализации новичка: {e}")

    # ─── Welcome Back ───
    await welcome_back_gift(user_id)

    user_balance = _safe_int(await db.get_user_balance(user_id), 0)
    chat_balance = await _chat_get_balance(chat_id)

    # ─── Расчёт максимального выигрыша для проверки баланса группы ───
    max_profit_steps = 10  # 10 рядов
    max_profit = _to_int_floor(_dec(bet_amount) * _dec(max_profit_steps) * _dec(RISK_STEP_MULTIPLIER))
    # Для челленджа тоже нужен max_profit, но проверка группы общая

    # ---------- ВЫЗОВ JERICHO (только определение режима, без автоматического доливания) ----------
    using_demo = False
    using_0demo = False

    if not has_assignment:
        print(f"[RISK] 🔮 Вызов Jericho (определение режима и долга)")
        decision = await jericho_check(user_id, bet_amount, game_name="риск")
        print("[RISK] Jericho решение:")
        print(decision["debug"])

        demo_balance = int(await db.get_user_demo(user_id) or 0)
        zero_demo_balance = int(await db.get_user_0demo(user_id) or 0)

        if decision["action"] in ("force_win", "force_loss", "near_miss"):
            # Только если реально хватает demo/0demo на ставку целиком
            if decision["action"] == "force_win":
                if demo_balance >= bet_amount:
                    using_demo = True
                    print(f"[RISK] Режим: demo (force_win, demo хватает)")
                else:
                    print(f"[RISK] Режим: force_win, но demo недостаточно → обычный")
            else:  # force_loss / near_miss
                if zero_demo_balance >= bet_amount:
                    using_0demo = True
                    print(f"[RISK] Режим: 0demo (force_loss, 0demo хватает)")
                else:
                    print(f"[RISK] Режим: force_loss, но 0demo недостаточно → обычный")
        else:
            if demo_balance >= bet_amount:
                using_demo = True
                print("[RISK] Режим: demo (хватает на ставку)")
            elif zero_demo_balance >= bet_amount:
                using_0demo = True
                print("[RISK] Режим: 0demo (хватает на ставку)")
            else:
                print("[RISK] Режим: обычный")

    # ─── ПРОВЕРКА БАЛАНСА ПОЛЬЗОВАТЕЛЯ (ОБЯЗАТЕЛЬНА, даже при demo/0demo) ───
    if is_free_play:
        # Бесплатный челлендж: без БЧ и без ★
        if bet_amount > current_two:
            progress_text = f"{current_two}/{target_amount}" if target_amount > 0 else f"{current_two}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [_btn(f"Баланс челленджа : {progress_text} кут", "noop", style="default")],
                [_btn("Недостаточно кут", "noop", style="default")],
            ])
            await message.reply("😓", reply_markup=kb, parse_mode="HTML")
            return
    else:
        # Обычный режим: проверяем основной баланс (даже если using_demo или using_0demo)
        if bet_amount > user_balance:
            try:
                bot_username = await get_bot_username_by_token(TOKEN)
            except Exception:
                bot_username = "CuteGamingBot"

            stars = _dec(bet_amount) * _dec(donate_bet)
            stars_q = stars.quantize(Decimal("1.000000"), rounding=ROUND_HALF_UP).normalize()
            stars_amount = format(stars_q, "f")

            pending_context[user_id] = {"stars_amount": stars_amount, "sent": False}

            rows = [
                [_btn(
                    f"💫 Купить {_fmt_int(bet_amount)} кут 💰",
                    "noop",
                    url=f"https://t.me/{bot_username}?start=insert_{stars_amount}_+"
                )],
                [_btn("Как заработать кут?", "9help_btn22", style="default")],
            ]

            await message.reply(
                "<tg-emoji emoji-id='5458574017814337878'>💰</tg-emoji>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                parse_mode="HTML"
            )
            asyncio.create_task(_send_invoice_later(message, user_id, stars_amount, delay=timeoutdonate))
            return

        # ─── ПРОВЕРКА БАЛАНСА ГРУППЫ (не для free) ───
        if bet_amount > chat_balance:
            await message.reply(
                f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В группе недостаточно средств для игры.</b>\n"
                f"💸 Баланс группы: {_fmt_int(chat_balance)} кут",
                parse_mode="HTML"
            )
            return

        if max_profit > chat_balance:
            await message.reply(
                f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>В группе недостаточно средств для возможного выигрыша.</b>\n"
                f"💸 Баланс группы: {_fmt_int(chat_balance)} кут\n"
                f"📌 Нужно минимум: {_fmt_int(max_profit)} кут",
                parse_mode="HTML"
            )
            return

    try:
        from bot.funcs.group_balance_level import reject_if_bet_over_group_level
        if await reject_if_bet_over_group_level(message, bet_amount, is_free_play=is_free_play):
            return
    except Exception as _gbl_e:
        print(f"[GBL] risk check skip: {_gbl_e!r}")

    async with _get_user_lock(user_id):
        await _deactivate_previous_risk_ui(user_id)

        prev_state = active_games_risk.get(user_id) or {}
        new_rev = _safe_int(prev_state.get("session_rev"), 0) + 1

        rng_seed = _make_seed(user_id, chat_id, new_rev)
        secret_field = _build_secret_field(rng_seed, is_demo=using_demo, is_0demo=using_0demo)

        _dbg_field(secret_field, seed=rng_seed, user_id=user_id, chat_id=chat_id, rev=new_rev)

        game_field = [[" " for _ in range(1)] for _ in range(10)]

        state = {
            "game_field": game_field,
            "secret_field": secret_field,
            "current_row": 0,
            "row_lock": False,
            "bet": int(bet_amount),
            "win_amount": _str_dec(_dec(bet_amount)),
            "owner_id": user_id,
            "chat_id": chat_id,
            "message_id": None,
            "first_success": False,
            "closed": False,
            "withdraw_locked": False,
            "payout_done": False,
            "session_rev": new_rev,
            "has_assignment": has_assignment,
            "is_free": is_free_play,
            "using_demo": using_demo,
            "using_0demo": using_0demo,
            "rng_seed": rng_seed,
            "timestamp": time.time(),
            "win_streak": 0,
            "lose_streak": 0,
        }

        sent = None
        for attempt in range(3):
            try:
                sent = await message.reply(
                    EMOJI_START,
                    parse_mode="HTML",
                    reply_markup=create_keyboard_risk([game_field[0]], state),
                )
                break
            except TelegramRetryAfter as e:
                wait_seconds = int(getattr(e, "retry_after", 1) or 1)
                dbg("START_FLOOD", attempt=attempt + 1, wait=wait_seconds)
                await asyncio.sleep(wait_seconds)
            except (TelegramNetworkError, TelegramAPIError) as e:
                dbg_err("START_TG_FAIL", e)
                break
            except Exception as e:
                dbg_err("START_FAIL", e)
                break

        if not sent:
            return

        msg_id = int(sent.message_id)
        state["message_id"] = msg_id

        active_games_risk[user_id] = state
        _store_save_safe(active_games_risk, "ACTIVE_SAVE_START")

        user_message_risk[user_id] = msg_id
        _store_save_safe(user_message_risk, "USERMSG_SAVE_START")

        asyncio.create_task(_session_ttl_watcher(chat_id, msg_id, user_id, SESSION_TTL))


# ======================================================================
#                             CLICKS
# ======================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("risk_actual_"))
async def risk_process_game_buttons(call: types.CallbackQuery):
    uid = int(call.from_user.id)
    msg_id = int(call.message.message_id)

    now = _now_mono()
    if now - _last_click.get(uid, 0.0) < USER_CLICK_COOLDOWN:
        try:
            await call.answer("⏳ Подожди чуть-чуть…", show_alert=True)
        except Exception:
            pass
        return
    _last_click[uid] = now

    try:
        _, _, rev_s, row_s, col_s, owner_s = call.data.split("_")
        cb_rev = int(rev_s)
        row_index = int(row_s)
        col_index = int(col_s)
        owner_id = int(owner_s)
    except Exception:
        try:
            await call.answer(cache_time=0)
        except Exception:
            pass
        return

    if uid != owner_id:
        try:
            await call.answer("Это не ваша игра.", show_alert=True)
        except Exception:
            pass
        return

    last_msg = user_message_risk.get(owner_id)
    if not last_msg or int(last_msg) != int(msg_id):
        try:
            await call.answer("Откройте вашу последнюю игру.", show_alert=False)
        except Exception:
            pass
        return

    inflight_key = (msg_id, uid)
    if inflight_key in _risk_inflight:
        try:
            await call.answer("⏳ Обрабатываю…", show_alert=True)
        except Exception:
            pass
        return
    _risk_inflight.add(inflight_key)

    lock = _get_session_lock(msg_id)
    async with lock:
        try:
            try:
                await call.answer(cache_time=0)
            except Exception:
                pass

            game_data = active_games_risk.get(owner_id)
            if not game_data or game_data.get("closed"):
                return

            if cb_rev != _safe_int(game_data.get("session_rev"), 0):
                return
            if _safe_int(game_data.get("message_id"), 0) != int(msg_id):
                return

            game_field = game_data.get("game_field")
            secret_field = game_data.get("secret_field")
            if not isinstance(game_field, list) or not isinstance(secret_field, list):
                await _safe_edit_text(call.message, "💥 <b>Ошибка игры. Начните заново.</b>")
                return

            current_row = _safe_int(game_data.get("current_row"), 0)
            bet_amount = _safe_int(game_data.get("bet"), 0)
            if bet_amount <= 0:
                await _safe_edit_text(call.message, "💥 <b>Ошибка состояния. Начните заново.</b>")
                return

            has_assignment = bool(game_data.get("has_assignment"))
            is_free = bool(game_data.get("is_free"))
            using_demo = bool(game_data.get("using_demo"))
            using_0demo = bool(game_data.get("using_0demo"))
            chat_id = _safe_int(game_data.get("chat_id"), int(call.message.chat.id))

            if row_index != current_row:
                return
            if bool(game_data.get("row_lock")):
                return

            action_key = f"cell:{owner_id}:{_safe_int(game_data.get('session_rev'),0)}:{msg_id}:{row_index}:{col_index}"
            if _is_action_processed(action_key):
                return
            _mark_action_processed(action_key)

            game_data["row_lock"] = True
            active_games_risk[owner_id] = game_data
            _store_save_safe(active_games_risk, "ACTIVE_SAVE_ROWLOCK")

            win_streak = game_data.get("win_streak", 0)
            lose_streak = game_data.get("lose_streak", 0)

            secret_val = secret_field[row_index][col_index]

            # ─── МАСКИРОВОЧНЫЕ ПОДМЕНЫ ───
            if using_demo and _is_win_secret(secret_val):
                if win_streak >= DEMO_STREAK_BREAK:
                    secret_val = CELL_HOME_SECRET
                    print(f"[RISK] DEMO streak break: {win_streak} побед подряд → HOME")
                elif random.random() < DEMO_MASK_LOSS_PROB:
                    secret_val = CELL_HOME_SECRET
                    print(f"[RISK] DEMO mask loss: случайный HOME")

            if using_0demo and _is_lose_secret(secret_val):
                if lose_streak >= ZERO_STREAK_BREAK:
                    secret_val = CELL_WIN_SECRET
                    print(f"[RISK] 0DEMO streak break: {lose_streak} проигрышей подряд → WIN")
                elif random.random() < ZERO_MASK_WIN_PROB:
                    secret_val = CELL_WIN_SECRET
                    print(f"[RISK] 0DEMO mask win: случайный WIN")

            _dbg_click_outcome(row=row_index, col=col_index, secret_val=secret_val)

            # ======================== 0DEMO – принудительный проигрыш ========================
            if using_0demo:
                try:
                    await db.deduct_0demo_amount(owner_id, bet_amount)
                    print(f"[RISK][0DEMO] Списано {bet_amount} 0demo у пользователя {owner_id}")
                except Exception as e:
                    print(f"[RISK][0DEMO][EXC] Ошибка списания: {e}")

                if _is_home_secret(secret_val):
                    game_field[row_index][col_index] = SHOW_HOME
                    await _safe_edit_text(call.message, EMOJI_HOME, reply_markup=None, parse_mode="HTML")
                else:
                    game_field[row_index][col_index] = SHOW_LOSE
                    await _safe_edit_text(call.message, EMOJI_LOSE, reply_markup=None, parse_mode="HTML")

                # ─── ВОЗВРАТ ДОЛГА ───
                print("[RISK] 💸 Списываем долг через force_repay_debt")
                await force_repay_debt(owner_id, bet_amount)

                await _mark_user_game_activity(owner_id, reason="0demo_loss")
                game_data["closed"] = True
                game_data["row_lock"] = False
                lose_streak += 1
                win_streak = 0
                game_data["win_streak"] = win_streak
                game_data["lose_streak"] = lose_streak
                active_games_risk[owner_id] = game_data
                _store_save_safe(active_games_risk, "ACTIVE_SAVE_0DEMO")
                try:
                    user_message_risk.pop(owner_id, None)
                    _store_save_safe(user_message_risk, "USERMSG_SAVE_0DEMO")
                except Exception:
                    pass
                _risk_session_locks.pop(int(msg_id), None)
                _dedup_gc()
                await _after_risk_closed(owner_id, msg_id)
                return

            # Обычная обработка (demo / обычная игра)
            ran = random.choice(RAN_EMOJIS_MSG)
            ran_plain = ran.split('>')[1].split('<')[0] if '>' in ran else '🍃'

            # ---------------- WIN ----------------
            if _is_win_secret(secret_val):
                game_field[row_index][col_index] = ran_plain
                if not game_data.get("first_success"):
                    game_data["first_success"] = True

                prev = _dec(game_data.get("win_amount", bet_amount))
                add = _dec(bet_amount) * _dec(RISK_STEP_MULTIPLIER)
                new_win = prev + add
                game_data["win_amount"] = _str_dec(new_win)

                await _safe_edit_text(
                    call.message,
                    EMOJI_START,
                    reply_markup=create_keyboard_risk(game_field[:current_row + 1], game_data),
                    parse_mode="HTML"
                )

                win_streak += 1
                lose_streak = 0
                game_data["win_streak"] = win_streak
                game_data["lose_streak"] = lose_streak

                if current_row == 9:
                    profit = _profit_now(game_data)

                    if using_demo:
                        try:
                            await db.deduct_demo_amount(owner_id, bet_amount)
                            print(f"[RISK][DEMO] Списано {bet_amount} demo у пользователя {owner_id}")
                        except Exception as e:
                            import traceback
                            print(f"[RISK][DEMO][EXC] Ошибка списания demo: {e}")
                            traceback.print_exc()

                        async with _get_chat_lock(chat_id):
                            chat_bal = await _chat_get_balance(chat_id)
                            pay = min(int(profit), max(0, chat_bal))
                            if pay > 0:
                                ok_debit = await _chat_debit_best_effort(chat_id, pay)
                                if ok_debit:
                                    await _user_delta(owner_id, +pay)
                                    try:
                                        await db.cutehistory_plus(owner_id, pay, "+ риск")
                                    except Exception as e:
                                        dbg_err("HISTORY_PLUS_DEMO", e)
                                    try:
                                        await db.update_user_winamount(owner_id, pay)
                                        await db.update_game_last_activity(owner_id)
                                    except Exception as e:
                                        dbg_err("WINAMOUNT_DEMO", e)
                                    try:
                                        await db.update_user_wins(owner_id, 1, bot1, ref_coin)
                                    except Exception as e:
                                        dbg_err("WINS_DEMO", e)
                                    await _mark_user_game_activity(owner_id, reason="win_final")
                            await _safe_edit_text(call.message, f"<b>{ran} 10-й ряд | {_fmt_int(pay if pay > 0 else 0)} кут</b>", parse_mode="HTML")

                    elif has_assignment and is_free:
                        await _safe_edit_text(
                            call.message,
                            f"<b>{ran} 10-й ряд | {_fmt_int(int(profit))} кут (челлендж)</b>",
                            parse_mode="HTML"
                        )
                        if int(profit) > 0:
                            await _gc_call(owner_id, chat_id, int(profit), "+", "WIN_FINAL_FREE")
                        await _mark_user_game_activity(owner_id, reason="win_final_free")
                    else:
                        async with _get_chat_lock(chat_id):
                            chat_bal = await _chat_get_balance(chat_id)
                            pay = min(int(profit), max(0, chat_bal))
                            if pay <= 0:
                                await _safe_edit_text(
                                    call.message,
                                    f"💭 <b>На балансе группы недостаточно кут\n💸 Баланс группы: {_fmt_int(chat_bal)} кут</b>",
                                    parse_mode="HTML"
                                )
                            else:
                                ok_debit = await _chat_debit_best_effort(chat_id, pay)
                                if not ok_debit:
                                    await _safe_edit_text(
                                        call.message,
                                        f"💭 <b>Не удалось списать у группы. Выплата отменена.</b>\n"
                                        f"💸 Баланс группы: {_fmt_int(chat_bal)} кут",
                                        parse_mode="HTML"
                                    )
                                else:
                                    await _user_delta(owner_id, +pay)
                                    if has_assignment:
                                        await _gc_call(owner_id, chat_id, pay, "+", "WIN_FINAL")
                                    try:
                                        await db.cutehistory_plus(owner_id, pay, "+ риск")
                                    except Exception as e:
                                        dbg_err("HISTORY_PLUS_WIN_FINAL", e)
                                    try:
                                        await db.update_user_winamount(owner_id, pay)
                                        await db.update_game_last_activity(owner_id)
                                    except Exception as e:
                                        dbg_err("WINAMOUNT_WIN_FINAL", e)
                                    try:
                                        await db.update_user_wins(owner_id, 1, bot1, ref_coin)
                                    except Exception as e:
                                        dbg_err("WINS_WIN_FINAL", e)
                                    await _mark_user_game_activity(owner_id, reason="win_final")
                                    await _safe_edit_text(
                                        call.message,
                                        f"<b>{ran} 10-й ряд | {_fmt_int(pay)} кут</b>",
                                        parse_mode="HTML"
                                    )

                    end_kb = InlineKeyboardMarkup(inline_keyboard=[[_btn("Игра завершена", "risk_end_stub", style="default")]])
                    await _safe_edit_text(call.message, EMOJI_END(), reply_markup=end_kb, parse_mode="HTML")

                    game_data["closed"] = True
                    game_data["payout_done"] = True
                    game_data["row_lock"] = False
                    active_games_risk[owner_id] = game_data
                    _store_save_safe(active_games_risk, "ACTIVE_SAVE_FINAL")

                    try:
                        user_message_risk.pop(owner_id, None)
                        _store_save_safe(user_message_risk, "USERMSG_SAVE_FINAL")
                    except Exception:
                        pass

                    _risk_session_locks.pop(int(msg_id), None)
                    _dedup_gc()
                    await _after_risk_closed(owner_id, msg_id)
                    return

                game_data["current_row"] = current_row + 1
                game_data["row_lock"] = False
                active_games_risk[owner_id] = game_data
                _store_save_safe(active_games_risk, "ACTIVE_SAVE_NEXTROW")

                await _safe_edit_reply_markup(
                    call.message,
                    create_keyboard_risk(game_field[:game_data["current_row"] + 1], game_data)
                )
                return

            # ---------------- HOME ----------------
            if _is_home_secret(secret_val):
                game_field[row_index][col_index] = SHOW_HOME

                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [_btn("РИСКНУТЬ НЕ ПОЛУЧИЛОСЬ", "risk_end_stub", style="default")]
                ])
                await _safe_edit_text(call.message, EMOJI_HOME, reply_markup=kb, parse_mode="HTML")

                loss = int(bet_amount)

                if using_demo:
                    await _mark_user_game_activity(owner_id, reason="home_demo")
                else:
                    if has_assignment:
                        await _gc_call(owner_id, chat_id, loss, "-", "HOME_FAIL")
                    if has_assignment and is_free:
                        await _mark_user_game_activity(owner_id, reason="home_free")
                    else:
                        ok_u = await _user_delta(owner_id, -loss)
                        if ok_u and TECH_CHAT_ID:
                            await _chat_credit_best_effort(int(TECH_CHAT_ID), loss)
                        await _home_log_risk_failed(bot=bot1, user_id=owner_id, loss=loss)
                        await _mark_user_game_activity(owner_id, reason="home")
                        try:
                            await db.cutehistory_minus(owner_id, loss, "- риск (домой)")
                        except Exception as e:
                            dbg_err("HISTORY_MINUS_HOME", e)
                        try:
                            await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                            await db.update_game_last_activity(owner_id)
                        except Exception as e:
                            dbg_err("LOOSE_HOME", e)

                lose_streak += 1
                win_streak = 0
                game_data["win_streak"] = win_streak
                game_data["lose_streak"] = lose_streak

                game_data["closed"] = True
                game_data["row_lock"] = False
                active_games_risk[owner_id] = game_data
                _store_save_safe(active_games_risk, "ACTIVE_SAVE_HOME")

                try:
                    user_message_risk.pop(owner_id, None)
                    _store_save_safe(user_message_risk, "USERMSG_SAVE_HOME")
                except Exception:
                    pass

                _risk_session_locks.pop(int(msg_id), None)
                _dedup_gc()
                await _after_risk_closed(owner_id, msg_id)
                return

            # ---------------- LOSE ----------------
            if _is_lose_secret(secret_val):
                game_field[row_index][col_index] = SHOW_LOSE

                await _safe_edit_text(call.message, EMOJI_LOSE, reply_markup=None, parse_mode="HTML")

                loss = int(bet_amount)

                if using_demo:
                    await _mark_user_game_activity(owner_id, reason="loss_demo")
                else:
                    if has_assignment:
                        await _gc_call(owner_id, chat_id, loss, "-", "LOSS")
                    if has_assignment and is_free:
                        await _mark_user_game_activity(owner_id, reason="loss_free")
                    else:
                        async with _get_chat_lock(chat_id):
                            ok_u = await _user_delta(owner_id, -loss)
                            if ok_u:
                                await _chat_credit_best_effort(chat_id, loss)
                        await _mark_user_game_activity(owner_id, reason="loss")
                        try:
                            await db.cutehistory_minus(owner_id, loss, "- риск")
                        except Exception as e:
                            dbg_err("HISTORY_MINUS_LOSS", e)
                        try:
                            await db.update_user_loose(owner_id, 1, bot1, ref_coin)
                            await db.update_game_last_activity(owner_id)
                        except Exception as e:
                            dbg_err("LOOSE_LOSS", e)

                lose_streak += 1
                win_streak = 0
                game_data["win_streak"] = win_streak
                game_data["lose_streak"] = lose_streak

                game_data["closed"] = True
                game_data["row_lock"] = False
                active_games_risk[owner_id] = game_data
                _store_save_safe(active_games_risk, "ACTIVE_SAVE_LOSE")

                try:
                    user_message_risk.pop(owner_id, None)
                    _store_save_safe(user_message_risk, "USERMSG_SAVE_LOSE")
                except Exception:
                    pass

                _risk_session_locks.pop(int(msg_id), None)
                _dedup_gc()
                await _after_risk_closed(owner_id, msg_id)
                return

        except Exception as e:
            dbg_err("BTN_ERR", e)
        finally:
            _risk_inflight.discard(inflight_key)
            st2 = active_games_risk.get(owner_id)
            if st2 and _safe_int(st2.get("message_id"), 0) == int(msg_id) and st2.get("row_lock"):
                st2["row_lock"] = False
                active_games_risk[owner_id] = st2
                _store_save_safe(active_games_risk, "ACTIVE_SAVE_UNLOCK_FINALLY")


# ======================================================================
#                             WITHDRAW
# ======================================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("risk_withdraw_"))
async def risk_process_withdraw(call: types.CallbackQuery):
    uid = int(call.from_user.id)
    msg_id = int(call.message.message_id)

    try:
        _, _, rev_s, owner_s = call.data.split("_")
        cb_rev = int(rev_s)
        owner_id = int(owner_s)
    except Exception:
        try:
            await call.answer(cache_time=0)
        except Exception:
            pass
        return

    if uid != owner_id:
        try:
            await call.answer("Это не ваша игра.", show_alert=True)
        except Exception:
            pass
        return

    last_msg = user_message_risk.get(owner_id)
    if not last_msg or int(last_msg) != int(msg_id):
        try:
            await call.answer("Откройте вашу последнюю игру.", show_alert=False)
        except Exception:
            pass
        return

    lock = _get_session_lock(msg_id)
    async with lock:
        try:
            game_data = active_games_risk.get(owner_id)
            if not game_data or game_data.get("closed"):
                return

            if cb_rev != _safe_int(game_data.get("session_rev"), 0):
                return
            if _safe_int(game_data.get("message_id"), 0) != int(msg_id):
                return

            if not game_data.get("first_success"):
                try:
                    await call.answer("Сначала попади хотя бы один раз 🍃", show_alert=True)
                except Exception:
                    pass
                return

            if game_data.get("payout_done") or game_data.get("withdraw_locked"):
                return

            using_demo = bool(game_data.get("using_demo"))
            using_0demo = bool(game_data.get("using_0demo"))
            if using_0demo:
                await call.answer("Игра завершена.", show_alert=False)
                return

            game_data["withdraw_locked"] = True
            active_games_risk[owner_id] = game_data
            _store_save_safe(active_games_risk, "ACTIVE_SAVE_WITHDRAW_LOCK")

            action_key = f"wd:{owner_id}:{_safe_int(game_data.get('session_rev'),0)}:{msg_id}"
            if _is_action_processed(action_key):
                return
            _mark_action_processed(action_key)

            chat_id = _safe_int(game_data.get("chat_id"), int(call.message.chat.id))
            has_assignment = bool(game_data.get("has_assignment"))
            is_free = bool(game_data.get("is_free"))

            profit = int(_profit_now(game_data))

            # ---------- DEMO ----------
            if using_demo:
                try:
                    await db.deduct_demo_amount(owner_id, int(game_data["bet"]))
                    print(f"[RISK][DEMO] Списано {game_data['bet']} demo у пользователя {owner_id}")
                except Exception as e:
                    import traceback
                    print(f"[RISK][DEMO][EXC] Ошибка списания demo: {e}")
                    traceback.print_exc()

                async with _get_chat_lock(chat_id):
                    chat_bal = await _chat_get_balance(chat_id)
                    pay = min(int(profit), max(0, chat_bal))
                    if pay > 0:
                        ok_debit = await _chat_debit_best_effort(chat_id, pay)
                        if ok_debit:
                            await _user_delta(owner_id, +pay)
                            try:
                                await db.cutehistory_plus(owner_id, pay, "+ риск")
                            except Exception as e:
                                dbg_err("HISTORY_PLUS_DEMO_WD", e)
                            try:
                                await db.update_user_winamount(owner_id, pay)
                                await db.update_game_last_activity(owner_id)
                            except Exception as e:
                                dbg_err("WINAMOUNT_DEMO_WD", e)
                            try:
                                await db.update_user_wins(owner_id, 1, bot1, ref_coin)
                            except Exception as e:
                                dbg_err("WINS_DEMO_WD", e)
                            await _mark_user_game_activity(owner_id, reason="withdraw")
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [_btn(f"{_fmt_int(pay)} кут", f"risk_paid_stub_{cb_rev}_{owner_id}", style="default")],
                    [_btn("Выплата", f"risk_msg_stub_{cb_rev}_{owner_id}", style="default")],
                ])
                await _safe_edit_text(call.message, "<tg-emoji emoji-id='5435866680339233166'>🌴</tg-emoji>", reply_markup=kb, parse_mode="HTML")

            elif has_assignment and is_free:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [_btn(f"{_fmt_int(int(profit))} кут", f"risk_paid_stub_{cb_rev}_{owner_id}", style="default")],
                    [_btn("Выплата (челлендж)", f"risk_msg_stub_{cb_rev}_{owner_id}", style="default")],
                ])
                await _safe_edit_text(
                    call.message,
                    "<tg-emoji emoji-id='5435866680339233166'>🌴</tg-emoji>",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                if int(profit) > 0:
                    await _gc_call(owner_id, chat_id, int(profit), "+", "WITHDRAW_FREE")
                await _mark_user_game_activity(owner_id, reason="withdraw_free")

            else:
                async with _get_chat_lock(chat_id):
                    chat_bal = await _chat_get_balance(chat_id)
                    pay = min(int(profit), max(0, chat_bal))
                    if pay <= 0:
                        await _safe_edit_text(
                            call.message,
                            f"💭 <b>На балансе группы недостаточно кут\n💸 Баланс группы: {_fmt_int(chat_bal)} кут</b>",
                            parse_mode="HTML"
                        )
                    else:
                        ok_debit = await _chat_debit_best_effort(chat_id, pay)
                        if not ok_debit:
                            await _safe_edit_text(
                                call.message,
                                f"💭 <b>Не удалось списать у группы. Выплата отменена.</b>\n"
                                f"💸 Баланс группы: {_fmt_int(chat_bal)} кут",
                                parse_mode="HTML"
                            )
                        else:
                            await _user_delta(owner_id, +pay)
                            if has_assignment:
                                await _gc_call(owner_id, chat_id, pay, "+", "WITHDRAW")
                            try:
                                await db.cutehistory_plus(owner_id, pay, "+ риск")
                            except Exception as e:
                                dbg_err("HISTORY_PLUS_WITHDRAW", e)
                            try:
                                await db.update_user_winamount(owner_id, pay)
                                await db.update_game_last_activity(owner_id)
                            except Exception as e:
                                dbg_err("WINAMOUNT_WITHDRAW", e)
                            try:
                                await db.update_user_wins(owner_id, 1, bot1, ref_coin)
                            except Exception as e:
                                dbg_err("WINS_WITHDRAW", e)
                            await _mark_user_game_activity(owner_id, reason="withdraw")
                            kb = InlineKeyboardMarkup(inline_keyboard=[
                                [_btn(f"{_fmt_int(pay)} кут", f"risk_paid_stub_{cb_rev}_{owner_id}", style="default")],
                                [_btn("Выплата", f"risk_msg_stub_{cb_rev}_{owner_id}", style="default")],
                            ])
                            await _safe_edit_text(
                                call.message,
                                "<tg-emoji emoji-id='5435866680339233166'>🌴</tg-emoji>",
                                reply_markup=kb,
                                parse_mode="HTML"
                            )

            game_data["payout_done"] = True
            game_data["closed"] = True
            active_games_risk[owner_id] = game_data
            _store_save_safe(active_games_risk, "ACTIVE_SAVE_WD_CLOSE")

            try:
                user_message_risk.pop(owner_id, None)
                _store_save_safe(user_message_risk, "USERMSG_SAVE_WD_CLOSE")
            except Exception:
                pass

            _risk_session_locks.pop(int(msg_id), None)
            _dedup_gc()
            await _after_risk_closed(owner_id, msg_id)

        except Exception as e:
            dbg_err("WITHDRAW_ERR", e)


# ------------------------- Заглушки -------------------------
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("risk_msg_stub_"))
async def risk_msg_stub(call: types.CallbackQuery):
    try:
        await call.answer("Информационная кнопка 💬", show_alert=False)
    except Exception:
        pass

@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("risk_paid_stub_"))
async def risk_paid_stub(call: types.CallbackQuery):
    try:
        await call.answer("Выплата зафиксирована ✅", show_alert=False)
    except Exception:
        pass

@dp.callback_query(lambda c: isinstance(c.data, str) and c.data == "risk_end_stub")
async def risk_end_stub(call: types.CallbackQuery):
    try:
        await call.answer("Игра завершена.", show_alert=False)
    except Exception:
        pass