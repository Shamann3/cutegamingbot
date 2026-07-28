
import os
import asyncio, time, uuid
import json
import asyncio
from decimal import Decimal, getcontext, ROUND_DOWN

from aiogram.types import Message
from datetime import datetime, timezone, date, timedelta
import random




from dataclasses import dataclass
import time
from contextlib import asynccontextmanager
import re
from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import asyncpg
import html
from typing import List, Dict, Optional, Union, Iterable, Set
import locale
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Tuple,Dict
import traceback
from cachetools import LRUCache
from bot.db_create.pklcode import LazyGameStore,GameStore
from bot.db_create.items_codec import decode_items, encode_items, normalize_inventory
from typing import Any, Optional, Dict, List, Union, Iterable, Set, Tuple, Callable, Awaitable
import datetime as dt
from aiogram.exceptions import TelegramAPIError
DEBUG_CRAFT = True  # False – отключить все логи
DEBUG_CRAFT_LEVEL = 2  # 0 – только ошибки, 1 – основное, 2 – детали


CHATHI_OFF = 0
CHATHI_ON = 1


# ============================================================
# ✅ НАСТРОЙКИ СТАТУСОВ БАЛАНСА
# ============================================================


BALANCE_DEBUG = False  # <- поставишь True, если нужны подробные логи баланса
BALANCE_STATUS_1_TO_2_SEC = 3 * 24 * 3600      # 3 дня -> статус 2 (спящий)
BALANCE_STATUS_MAX_TO_3_SEC = 7 * 24 * 3600    # 7 дней -> статус 3 (сгоревший)

SLEEP_RECOVERY_DEFAULT_NEEDED = 25
# статусы
BAL_STATUS_ACTIVE = 1
BAL_STATUS_SLEEP = 2
BAL_STATUS_BURNED = 3


def _bal_dbg(tag: str , msg: str) -> None:
    if not BALANCE_DEBUG:
        return
    try:
        print(f"🧠[{tag}] {msg}")
    except Exception:
        pass









user_cache_balance = GameStore("user_cache_balance")

# ------------------------------------------------------------------ #
#  Согласованность кэша баланса с БД (cache coherence)
# ------------------------------------------------------------------ #
# user_cache_balance это Redis-бэкенд GameStore, который НЕ протухает
# (он в EXCLUDED_STORES). Раньше get_user_balance при cache-hit возвращал
# значение и НИКОГДА не сверялся с БД поэтому устаревший 0 «прилипал»
# навсегда (в т.ч. между рестартами), даже если в БД уже лежит 159.
#
# Решение: лёгкий слой свежести. Для каждого uid помним monotonic-время
# последней СВЕРКИ значения с БД. Пока запись «свежая» (моложе TTL) отдаём
# кэш мгновенно (быстрый горячий путь). Иначе перечитываем БД и ловим правки
# извне: WebApp-сервер, ручной SQL, другой процесс. Карта живёт в ОЗУ и
# сбрасывается при рестарте значит после перезапуска первый запрос по
# каждому пользователю всегда идёт в БД и самоизлечивает залипшие значения.
_balance_fresh_at: Dict[int, float] = {}
try:
    # 0 => никогда не доверять cache-hit (всегда сверяться с БД).
    BALANCE_CACHE_TTL_SEC = max(0.0, float(os.getenv("BALANCE_CACHE_TTL_SEC", "4.0")))
except (TypeError, ValueError):
    BALANCE_CACHE_TTL_SEC = 4.0


def _balance_touch_fresh(user_id) -> None:
    """Отметить, что кэш баланса uid только что согласован с БД (свежий)."""
    try:
        _balance_fresh_at[int(user_id)] = time.monotonic()
    except Exception:
        pass


_user_balance_locks = {}#GameStore("_user_balance_locks")
group_cache = GameStore("group_cache")
user_cache = GameStore("user_cache")
user_last_invite_time = GameStore("user_last_invite_time")
user_request_time = GameStore("user_request_time")
DEBUG_BAL = False  # <- True, если нужны подробные логи баланса/GC в консоли
def _ch_dbg(tag: str, msg: str) -> None:
    # можешь заменить на свой логгер
    print(f"[CHATHI][{tag}] {msg}")

def _dbg(*a):
    if DEBUG_BAL:
        print(*a)

def _vdbg(*args, **kwargs):
    """Отладочный print для шумных фоновых циклов (ДЖЕКЧАТ, MSG_COUNTER,
    ЛИМИТЫ и т.п.) включается тем же DEBUG_VERBOSE, что и в main.py.
    Раньше эти print были безусловными и печатались на каждой итерации
    фоновых циклов (обход ~279 групп, флаш раз в 20с) НЕЗАВИСИМО от того,
    пишет ли кто-то боту команды то есть постоянный синхронный I/O на
    event loop, даже когда бот якобы простаивает. Каждый print с эмодзи
    через пайп логгера на хостинге стоит миллисекунд под реальной
    нагрузкой (много групп, много одновременных сообщений) это накапливается
    и может ощущаться как «команда сработала через раз»."""
    try:
        from bot.config.config import DEBUG_VERBOSE as _DEBUG_VERBOSE
    except Exception:
        _DEBUG_VERBOSE = False
    if _DEBUG_VERBOSE:
        print(*args, **kwargs)
from bot.config.db_config import (
    APP_MODE,
    DB_NAME,
    DB_LOCATION,
    MAIN_DB_TARGET,
    ACTIVE_DB_PROFILE,
    bootstrap_database_env,
    build_db_settings,
    db_connect_target,
    db_connected_line,
    db_debug_log,
    db_mode_summary,
    db_ssl_mode,
    db_pool_min,
    db_pool_max,
    _safe_log,
)

bootstrap_database_env()
db_settings = build_db_settings()

_USER_EMOJI_DEFAULTS = {
    "idemo": "<tg-emoji emoji-id='5438449312893792440'>🪪</tg-emoji>",
    "nameemo": "<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji>",
    "usernameemo": "<tg-emoji emoji-id='5294026527850132517'>🥷</tg-emoji>",
    "balanceemo": "<tg-emoji emoji-id='5206415560153270355'>💰</tg-emoji>",
    "winamountemo": "<tg-emoji emoji-id='5292232455586084206'>🍻</tg-emoji>",
    "marryemo": "💞",
    "repemo": "⭐️",
    "prgl": "<tg-emoji emoji-id='5251308237663264052'>🧩</tg-emoji>",
    "limitemo": "<tg-emoji emoji-id='5292024162557129071'>🧸</tg-emoji>",
    "refemo": "<tg-emoji emoji-id='5266997495497522280'>🥂</tg-emoji>",
    "dataemo": "🗓",
}


def _is_connection_lost_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in {
        "ConnectionRefusedError",
        "ConnectionResetError",
        "ConnectionDoesNotExistError",
        "CannotConnectNowError",
        "PostgresConnectionError",
        "InterfaceError",
        "OSError",
        "TimeoutError",
    }:
        return True
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "connection refused",
            "connect call failed",
            "connection is closed",
            "server closed the connection",
            "terminating connection",
            "cannot connect",
            "connection reset",
        )
    )


_LUA_UNLOCK = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
else
  return 0
end
"""

# ---------- настроки по умолчанию (если нет записи в withdraw_limits) ----------


# ---------- сервисные геттеры ----------
SQL_TODAY_SUM = r"""
WITH bounds AS (
  SELECT
    -- начало текущего дня в Европе/Осло, переведённое в timestamptz
    (date_trunc('day', (now() AT TIME ZONE 'Europe/Oslo')) AT TIME ZONE 'Europe/Oslo') AS start_ts,
    ((date_trunc('day', (now() AT TIME ZONE 'Europe/Oslo')) + INTERVAL '1 day') AT TIME ZONE 'Europe/Oslo') AS end_ts
)
SELECT COALESCE(SUM(w.amount), 0)::BIGINT AS s
FROM withdraw_log w, bounds b
WHERE w.user_id = $1
  AND w.created_at >= b.start_ts
  AND w.created_at <  b.end_ts;
"""
min_connections = db_pool_min()
max_connections = db_pool_max()
cache = LRUCache(maxsize=100)

getcontext().prec = 28

TWOP = Decimal("0.01")

def D(x) -> Decimal:
    """Decimal c округлением до 2 знаков (банковская точность)."""
    return (x if isinstance(x, Decimal) else Decimal(str(x))).quantize(TWOP)
# Используйте ваш логгер - пока просто print
def _log_info(msg: str):
    print(f"[GC_DB_INFO] {msg}")

def _log_ok(msg: str):
    if DEBUG_BAL:
        print(f"[GC_DB_OK] {msg}")

def _log_warn(msg: str):
    if DEBUG_BAL:
        print(f"[GC_DB_WARN] {msg}")

def _log_err(msg: str):
    # Ошибки печатаем всегда они редкие и важные.
    print(f"[GC_DB_ERROR] {msg}")
def _parse_money_text(val) -> Decimal:
    """
    Надёжный парсер для TEXT из БД:
    None / '' -> 0; поддержка запятой; лишние пробелы; любые типы.
    """
    if val is None:
        return D(0)
    s = str(val).strip().replace(",", ".")
    if s == "":
        return D(0)
    try:
        return D(Decimal(s))
    except Exception:
        # если в колонке мусор - не роняемся, считаем 0
        return D(0)

def _format_money_text(amount: Decimal) -> str:
    """Всегда строка ровно с двумя знаками, например '0.00', '1.25'."""
    return f"{D(amount):.2f}"
def fmt_amt(x) -> str:
    d = D(x).normalize()
    s = format(d , 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


# --- НОРМАЛИЗАЦИЯ КЛЮЧА ---
import re
_username_re = re.compile(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)", re.IGNORECASE)
def norm_chat_ref(raw: Union[str, int]) -> str:
    if isinstance(raw, int):
        return str(raw)
    s = str(raw or "").strip()
    m = _username_re.search(s)
    if m: return "@" + m.group(1).lower()
    if s.startswith("@"): return "@" + s[1:].lower()
    if s.replace("-", "").isdigit(): return s
    return "@" + s.lower()
# для совместимости, если где-то в коде уже используется _norm_chat_ref
_norm_chat_ref = norm_chat_ref
async def create_user_link(user_id: int, first_name: str, username: str = None) -> str:
    """Создает ссылку на профиль пользователя."""
    if username:
        # Если есть username, создаем гиперссылку с именем
        user_hyperlink = f"<a href='https://t.me/{html.escape(username)}'>{html.escape(first_name)}</a>"
    elif first_name:
        # Если username нет, используем имя без ссылки
        user_hyperlink = html.escape(first_name)
    else:
        # Если отсутствуют и имя, и username
        return "У пользователя нет имени."

    return user_hyperlink
def _safe_str(v) -> str:
    try:
        return "" if v is None else str(v)
    except Exception:
        return ""







Default_WITHDRAW_DEFAULT_DAILY_LIMIT = 100 # минимальная сумма для вывода / также в табилице users столбец canwithdrawal стоит 100, если хочешь заменить - изменить и там тоже в свойствах базы данных


@dataclass(frozen=True)
class BalanceSnapshot:
    chatbalance: int
    dexbalance: int


class InsufficientBalanceError(Exception):
    """Недостаточно средств для перевода - поднимается Database.transfer_currency()."""


@dataclass(frozen=True)
class TransferResult:
    transfer_id: int
    sender_before: int
    sender_after: int
    receiver_before: int
    receiver_after: int

# -----------------------------
# Внутренний формат кеша баланса
# -----------------------------
@dataclass
class _BalCacheCell:
    value: BalanceSnapshot
    expires_at: float
ANARCH = True   # включить система отладки в балансе групп чата















##

DEBUG_CheckpublickGroup = True


def dbg_CheckpublickGroup(*args):
    if DEBUG_CheckpublickGroup:
        print("[CheckpublickGroup]", *args)


# =========================
#   RESULT MODEL
# =========================
@dataclass
class PublicCheckResult_CheckpublickGroup:
    is_public_CheckpublickGroup: bool
    username_CheckpublickGroup: Optional[str] = None
    source_CheckpublickGroup: str = "none"   # "db" | "cache" | "tg" | "none"
    reason_CheckpublickGroup: str = ""


























# =========================
#   PUBLIC GROUP CHECKER
# =========================
class PublicGroupChecker_CheckpublickGroup:
    """
    Надёжная логика:
      1) Всегда читаем только usernamechat из БД
      2) Если username валиден -> сразу public
      3) Иначе -> cache -> TG fallback
      4) TG даёт финальный ответ
    """

    def __init__(
        self,
        ttl_public_seconds_CheckpublickGroup: int = 1800,   # 30 мин
        ttl_private_seconds_CheckpublickGroup: int = 180,   # 3 мин
        ttl_error_seconds_CheckpublickGroup: int = 30,      # 30 сек
        tg_timeout_seconds_CheckpublickGroup: float = 3.0,
        max_cache_size_CheckpublickGroup: int = 50_000
    ):
        self.ttl_public_seconds_CheckpublickGroup = ttl_public_seconds_CheckpublickGroup
        self.ttl_private_seconds_CheckpublickGroup = ttl_private_seconds_CheckpublickGroup
        self.ttl_error_seconds_CheckpublickGroup = ttl_error_seconds_CheckpublickGroup
        self.tg_timeout_seconds_CheckpublickGroup = tg_timeout_seconds_CheckpublickGroup
        self.max_cache_size_CheckpublickGroup = max_cache_size_CheckpublickGroup

        self._cache_CheckpublickGroup: Dict[int, Tuple[float, PublicCheckResult_CheckpublickGroup]] = {}
        self._singleflight_locks_CheckpublickGroup: Dict[int, asyncio.Lock] = {}
        self._lock_CheckpublickGroup = asyncio.Lock()

    # =========================
    # username utils
    # =========================
    def _normalize_username_CheckpublickGroup(self, username_CheckpublickGroup: Optional[str]) -> Optional[str]:
        if not username_CheckpublickGroup or not isinstance(username_CheckpublickGroup, str):
            return None

        u_CheckpublickGroup = username_CheckpublickGroup.strip()
        if not u_CheckpublickGroup:
            return None

        if u_CheckpublickGroup.startswith("@"):
            u_CheckpublickGroup = u_CheckpublickGroup[1:].strip()

        return u_CheckpublickGroup or None

    def _looks_like_valid_username_CheckpublickGroup(self, username_CheckpublickGroup: Optional[str]) -> bool:
        u_CheckpublickGroup = self._normalize_username_CheckpublickGroup(username_CheckpublickGroup)
        if not u_CheckpublickGroup:
            return False

        if len(u_CheckpublickGroup) < 4:
            return False

        allowed_CheckpublickGroup = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
        return all(ch in allowed_CheckpublickGroup for ch in u_CheckpublickGroup)

    def _choose_ttl_CheckpublickGroup(self, result_CheckpublickGroup: PublicCheckResult_CheckpublickGroup) -> int:
        if result_CheckpublickGroup.is_public_CheckpublickGroup:
            return self.ttl_public_seconds_CheckpublickGroup

        if result_CheckpublickGroup.reason_CheckpublickGroup in ("tg_timeout", "tg_exception"):
            return self.ttl_error_seconds_CheckpublickGroup

        return self.ttl_private_seconds_CheckpublickGroup

    # =========================
    # cache
    # =========================
    async def _get_from_cache_CheckpublickGroup(
        self,
        chat_id_CheckpublickGroup: int
    ) -> Optional[PublicCheckResult_CheckpublickGroup]:
        now_CheckpublickGroup = time.time()

        async with self._lock_CheckpublickGroup:
            item_CheckpublickGroup = self._cache_CheckpublickGroup.get(chat_id_CheckpublickGroup)
            if not item_CheckpublickGroup:
                print(f"[CHECKPUBLICKGROUP][CACHE] Промах кэша chat_id={chat_id_CheckpublickGroup}")
                return None

            exp_CheckpublickGroup, res_CheckpublickGroup = item_CheckpublickGroup
            if exp_CheckpublickGroup <= now_CheckpublickGroup:
                self._cache_CheckpublickGroup.pop(chat_id_CheckpublickGroup, None)
                print(f"[CHECKPUBLICKGROUP][CACHE] Кэш истёк chat_id={chat_id_CheckpublickGroup}")
                return None

            print(f"[CHECKPUBLICKGROUP][CACHE] Попадание в кэш chat_id={chat_id_CheckpublickGroup}")
            return res_CheckpublickGroup





    async def get_referrals_with_details(self , referrer_id: int) -> List [ Dict [ str , Any ] ]:
        """Возвращает список пользователей, у которых refferer_id = referrer_id."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, first_name, username
                FROM users
                WHERE refferer_id = $1
                ORDER BY user_id
                """ , referrer_id)
            return [ dict(row) for row in rows ]


    async def _save_to_cache_CheckpublickGroup(
        self,
        chat_id_CheckpublickGroup: int,
        result_CheckpublickGroup: PublicCheckResult_CheckpublickGroup
    ) -> None:
        ttl_CheckpublickGroup = self._choose_ttl_CheckpublickGroup(result_CheckpublickGroup)
        exp_CheckpublickGroup = time.time() + ttl_CheckpublickGroup

        async with self._lock_CheckpublickGroup:
            if len(self._cache_CheckpublickGroup) >= self.max_cache_size_CheckpublickGroup:
                keys_to_drop = list(self._cache_CheckpublickGroup.keys())[:max(1, self.max_cache_size_CheckpublickGroup // 10)]
                for k in keys_to_drop:
                    self._cache_CheckpublickGroup.pop(k, None)
                print(f"[CHECKPUBLICKGROUP][CACHE] Частичная очистка кэша, удалено={len(keys_to_drop)}")

            self._cache_CheckpublickGroup[chat_id_CheckpublickGroup] = (exp_CheckpublickGroup, result_CheckpublickGroup)

        dbg_CheckpublickGroup(
            f"Cache set chat_id={chat_id_CheckpublickGroup} ttl={ttl_CheckpublickGroup}s -> {result_CheckpublickGroup}"
        )

    # =========================
    # singleflight
    # =========================
    async def _get_chat_lock_CheckpublickGroup(self, chat_id_CheckpublickGroup: int) -> asyncio.Lock:
        async with self._lock_CheckpublickGroup:
            lock_CheckpublickGroup = self._singleflight_locks_CheckpublickGroup.get(chat_id_CheckpublickGroup)
            if lock_CheckpublickGroup is None:
                lock_CheckpublickGroup = asyncio.Lock()
                self._singleflight_locks_CheckpublickGroup[chat_id_CheckpublickGroup] = lock_CheckpublickGroup
            return lock_CheckpublickGroup

    # =========================
    # main
    # =========================
    async def check_public_group_CheckpublickGroup(
        self,
        bot,
        db,
        chat_id_CheckpublickGroup: int
    ) -> PublicCheckResult_CheckpublickGroup:
        print(f"[CHECKPUBLICKGROUP] 🟦 Старт проверки chat_id={chat_id_CheckpublickGroup}")

        # 1) читаем только usernamechat из БД
        username_db_raw_CheckpublickGroup = await db.get_usernamechat_CheckpublickGroup(chat_id_CheckpublickGroup)
        print(f"[CHECKPUBLICKGROUP] 🟨 usernamechat из БД = {username_db_raw_CheckpublickGroup!r}")

        # 2) если username валиден -> сразу public
        if self._looks_like_valid_username_CheckpublickGroup(username_db_raw_CheckpublickGroup):
            username_db_norm_CheckpublickGroup = self._normalize_username_CheckpublickGroup(
                username_db_raw_CheckpublickGroup
            )

            result_CheckpublickGroup = PublicCheckResult_CheckpublickGroup(
                is_public_CheckpublickGroup=True,
                username_CheckpublickGroup=username_db_norm_CheckpublickGroup,
                source_CheckpublickGroup="db",
                reason_CheckpublickGroup="db_public"
            )

            await self._save_to_cache_CheckpublickGroup(chat_id_CheckpublickGroup, result_CheckpublickGroup)
            print(f"[CHECKPUBLICKGROUP] ✅ Возврат PUBLIC из БД: {result_CheckpublickGroup}")
            return result_CheckpublickGroup

        # 3) cache
        print("[CHECKPUBLICKGROUP] 🟪 БД не дала валидный username -> проверяю кэш")
        cached_CheckpublickGroup = await self._get_from_cache_CheckpublickGroup(chat_id_CheckpublickGroup)
        if cached_CheckpublickGroup is not None:
            result_CheckpublickGroup = PublicCheckResult_CheckpublickGroup(
                is_public_CheckpublickGroup=cached_CheckpublickGroup.is_public_CheckpublickGroup,
                username_CheckpublickGroup=cached_CheckpublickGroup.username_CheckpublickGroup,
                source_CheckpublickGroup="cache",
                reason_CheckpublickGroup="cache_hit"
            )
            print(f"[CHECKPUBLICKGROUP] ✅ Возврат из кэша: {result_CheckpublickGroup}")
            return result_CheckpublickGroup

        # 4) singleflight lock
        print("[CHECKPUBLICKGROUP] 🟪 Кэш пуст -> беру lock")
        lock_CheckpublickGroup = await self._get_chat_lock_CheckpublickGroup(chat_id_CheckpublickGroup)

        async with lock_CheckpublickGroup:
            cached2_CheckpublickGroup = await self._get_from_cache_CheckpublickGroup(chat_id_CheckpublickGroup)
            if cached2_CheckpublickGroup is not None:
                result_CheckpublickGroup = PublicCheckResult_CheckpublickGroup(
                    is_public_CheckpublickGroup=cached2_CheckpublickGroup.is_public_CheckpublickGroup,
                    username_CheckpublickGroup=cached2_CheckpublickGroup.username_CheckpublickGroup,
                    source_CheckpublickGroup="cache",
                    reason_CheckpublickGroup="cache_hit"
                )
                print(f"[CHECKPUBLICKGROUP] ✅ Возврат из кэша после lock: {result_CheckpublickGroup}")
                return result_CheckpublickGroup

            # 5) TG fallback
            try:
                print(f"[CHECKPUBLICKGROUP] 🟪 Запрос в Telegram: bot.get_chat({chat_id_CheckpublickGroup})")
                chat_obj_CheckpublickGroup = await asyncio.wait_for(
                    bot.get_chat(chat_id_CheckpublickGroup),
                    timeout=self.tg_timeout_seconds_CheckpublickGroup
                )

                username_tg_raw_CheckpublickGroup = getattr(chat_obj_CheckpublickGroup, "username", None)
                username_tg_norm_CheckpublickGroup = self._normalize_username_CheckpublickGroup(
                    username_tg_raw_CheckpublickGroup
                )

                print(f"[CHECKPUBLICKGROUP] 🟪 username из TG = {username_tg_raw_CheckpublickGroup!r}")
                print(f"[CHECKPUBLICKGROUP] 🟪 username нормализованный = {username_tg_norm_CheckpublickGroup!r}")

                if self._looks_like_valid_username_CheckpublickGroup(username_tg_norm_CheckpublickGroup):
                    result_CheckpublickGroup = PublicCheckResult_CheckpublickGroup(
                        is_public_CheckpublickGroup=True,
                        username_CheckpublickGroup=username_tg_norm_CheckpublickGroup,
                        source_CheckpublickGroup="tg",
                        reason_CheckpublickGroup="tg_public"
                    )

                    ok_update_CheckpublickGroup = await db.update_usernamechat_CheckpublickGroup(
                        chat_id_CheckpublickGroup,
                        username_tg_norm_CheckpublickGroup
                    )
                    print(
                        f"[CHECKPUBLICKGROUP] ✅ TG подтвердил PUBLIC: "
                        f"username={username_tg_norm_CheckpublickGroup!r}, db_update_ok={ok_update_CheckpublickGroup}"
                    )
                else:
                    result_CheckpublickGroup = PublicCheckResult_CheckpublickGroup(
                        is_public_CheckpublickGroup=False,
                        username_CheckpublickGroup=None,
                        source_CheckpublickGroup="tg",
                        reason_CheckpublickGroup="tg_private"
                    )

                    ok_update_CheckpublickGroup = await db.update_usernamechat_CheckpublickGroup(
                        chat_id_CheckpublickGroup,
                        "username отсутствует"
                    )
                    print(
                        f"[CHECKPUBLICKGROUP] ⛔ TG подтвердил PRIVATE/без username, "
                        f"db_update_ok={ok_update_CheckpublickGroup}"
                    )

                await self._save_to_cache_CheckpublickGroup(chat_id_CheckpublickGroup, result_CheckpublickGroup)
                print(f"[CHECKPUBLICKGROUP] ✅ Финальный результат: {result_CheckpublickGroup}")
                return result_CheckpublickGroup

            except asyncio.TimeoutError:
                print(f"[CHECKPUBLICKGROUP] ❌ Таймаут Telegram для chat_id={chat_id_CheckpublickGroup}")

                result_CheckpublickGroup = PublicCheckResult_CheckpublickGroup(
                    is_public_CheckpublickGroup=False,
                    username_CheckpublickGroup=None,
                    source_CheckpublickGroup="tg",
                    reason_CheckpublickGroup="tg_timeout"
                )
                await self._save_to_cache_CheckpublickGroup(chat_id_CheckpublickGroup, result_CheckpublickGroup)
                return result_CheckpublickGroup

            except Exception as e:
                print(f"[CHECKPUBLICKGROUP] ❌ Ошибка TG: {type(e).__name__}: {e}")

                result_CheckpublickGroup = PublicCheckResult_CheckpublickGroup(
                    is_public_CheckpublickGroup=False,
                    username_CheckpublickGroup=None,
                    source_CheckpublickGroup="tg",
                    reason_CheckpublickGroup="tg_exception"
                )
                await self._save_to_cache_CheckpublickGroup(chat_id_CheckpublickGroup, result_CheckpublickGroup)
                return result_CheckpublickGroup


publicChecker_CheckpublickGroup = PublicGroupChecker_CheckpublickGroup(
    ttl_public_seconds_CheckpublickGroup=1800,
    ttl_private_seconds_CheckpublickGroup=180,
    ttl_error_seconds_CheckpublickGroup=30,
    tg_timeout_seconds_CheckpublickGroup=3.0,
    max_cache_size_CheckpublickGroup=50_000
)

print(
    "[CHECKPUBLICKGROUP][INIT] OK class=",
    type(publicChecker_CheckpublickGroup).__name__,
)

class Database:
    def __init__(self, db_settings):
        """
        Инициализация с параметрами подключения.
        """
        if not isinstance(db_settings, dict):
            raise ValueError(f"db_settings должен быть словарём, а не {type(db_settings).__name__}")

        self.db_settings = db_settings
        self.pool = None
        self.connected_database: str = ""
        self._GROUP_LOCKS = {}
        self._ban_check_cache: Dict[int, tuple] = {}
        # Быстрые кэши для «горячих» запросов (снижают round-trip'ы по SSH-туннелю)
        self._group_ban_cache: Dict[int, tuple] = {}   # chat_id -> (monotonic_ts, is_banned)
        self._group_ban_cache_ttl: float = 60.0
        self._username_cache: Dict[int, tuple] = {}     # user_id -> (monotonic_ts, username)
        self._username_cache_ttl: float = 300.0
        self.cache_bio = {}
        self.user_cache = {}
        self.group_cache = {}
        #self.WITHDRAW_DEFAULT_DAILY_LIMIT = 30000  # кут



        # ✅ УНИКАЛЬНЫЕ СЛОВАРИ/ЛОКИ
        self.__LCK_CHATROW_SYNC__: Dict [ int , asyncio.Lock ] = {}

        self.__CACHE_BIOGRAPHY_BLOB__ = {}
        self.__CACHE_USERPROFILE_SLAB__ = {}
        self.__CACHE_CHATMETA_ATLAS__: Dict [ int , Dict [ str , Any ] ] = GameStore("__CACHE_CHATMETA_ATLAS__")

        self.WITHDRAW_DEFAULT_COOLDOWN_SEC = 12 * 1800

        # ------------------------------
        # Настройки производительности баланса
        # ------------------------------
        self.BALANCE_CACHE_TTL = 2.0
        self.BALANCE_NEG_TTL = 30.0
        self.BALANCE_SELECT_TIMEOUT = 2.0
        self.BALANCE_UPDATE_TIMEOUT = 2.0
        self.BALANCE_SYNC_TIMEOUT = 12.0

        # ✅ Отдельные кэши только для баланса (уникальные имена)
        self.__CACHE_CHATBAL_FASTLANE__: Dict [ int , _BalCacheCell ] = {}
        self.__CACHE_CHATBAL_NEGGUARD__: Dict [ int , float ] = {}

        # ------------------------------
        # Учёт сообщений (статистика chatchange / chat.text)
        # Каждое сообщение мгновенно (в памяти, без БД) прибавляется к буферу
        # через record_message(); фоновый цикл раз в _MSG_COUNTER_FLUSH_INTERVAL_SEC
        # пакетно пишет накопленные дельты в БД (flush_message_counters).
        # ------------------------------
        self._pending_user_counts: Dict[Tuple[int, int], int] = {}  # (user_id, chat_id) -> +N
        self._pending_chat_counts: Dict[int, int] = {}              # chat_id           -> +N
        self._msg_counter_worker_started: bool = False
        self.MSG_COUNTER_FLUSH_INTERVAL_SEC: float = 20.0
        self._black_market_shop_deposits_table_ready: bool = False

    async def connect(self):
        """
        Старый принцип: if self.pool → return; иначе create_pool().
        Туннель SSH когда расположение = remote (для любой базы: main/test).
        """
        if self.pool:
            return

        if DB_LOCATION == "remote":
            from bot.config.ssh_tunnel import ensure_ssh_tunnel
            await ensure_ssh_tunnel()

        self.db_settings = build_db_settings()
        raw_password = self.db_settings.get("password")
        password = raw_password if raw_password not in (None, "") else None
        ssl = self.db_settings.get("ssl")
        if ssl is None:
            ssl = db_ssl_mode()

        # Пул через SSH-туннель: открытие нового соединения ДОРОГОЕ (SSH+TLS+auth).
        # Поэтому держим тёплый минимум и НЕ закрываем простаивающие соединения,
        # чтобы всплеск запросов не упирался в холодные подключения.
        warm_min = max(min_connections, 6)
        warm_max = max(max_connections, warm_min)
        kwargs: Dict[str, Any] = dict(
            user=self.db_settings["user"],
            password=password,
            database=self.db_settings["database"],
            host=self.db_settings["host"],
            port=int(self.db_settings["port"]),
            min_size=warm_min,
            max_size=warm_max,
            max_inactive_connection_lifetime=0.0,  # не закрывать тёплые соединения
            command_timeout=45.0,                   # предохранитель от зависших запросов
            statement_cache_size=0,                 # обязательно для DO connection pool
                                                    # (PgBouncer transaction mode) иначе
                                                    # ломаются prepared statements.
        )
        if ssl is not False:
            kwargs["ssl"] = ssl

        db_debug_log(f"[DB] connect → {db_connect_target()}")

        try:
            self.pool = await asyncpg.create_pool(**kwargs)
        except Exception as e:
            self.pool = None
            self.connected_database = ""
            _safe_log(f"[DB][ERROR] {type(e).__name__}: {e}")
            raise

        try:
            async with self.pool.acquire() as conn:
                self.connected_database = await conn.fetchval("SELECT current_database()") or ""
            db_debug_log(db_connected_line(self.connected_database))
        except Exception as e:
            db_debug_log(f"[DB] pool OK, verify skipped: {type(e).__name__}")

    async def close(self):
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def is_connected(self):
        if not self.pool:
            return False
        try:
            async with self.pool.acquire() as connection:
                await connection.fetchval("SELECT 1")
            return True
        except Exception as e:
            _safe_log(f"[DB][WARN] is_connected: {type(e).__name__}: {e}")
            return False

    # -------------------------------
    # 🔴 Единая красная отладка (для DB / системы)
    # -------------------------------
    def _r(self, tag: str, msg: str) -> None:
        print(f"🔴 [{tag}] {msg}")

    # -------------------------------
    # 🟩 JackChat Debug Print (включаемый)
    # -------------------------------
    def _jc(self, tag: str, msg: str) -> None:
        """
        Единый принтер JackChat.
        Включается/выключается переменной JACKCHAT_DEBUG.
        """
        try:
            self._lazy_init_runtime_fields()
            if not bool(getattr(self, "JACKCHAT_DEBUG", False)):
                return
            t = f"{self._jackchat_now():.3f}"
            print(f"🟩 [JACKCHAT][{t}][{tag}] {msg}")
        except Exception:
            return

    def _get_group_lock(self, chat_id: int) -> asyncio.Lock:
        lock = self._GROUP_LOCKS.get(int(chat_id))
        if not lock:
            lock = asyncio.Lock()
            self._GROUP_LOCKS [ int(chat_id) ] = lock
        return lock
    # -------------------------------
    # ✅ Ленивые поля (без правки __init__)
    # -------------------------------
    def _lazy_init_runtime_fields(self) -> None:
        """
        Создаёт служебные поля, если их нет (самолечение структуры).
        """
        # =========================
        # DB pool самовосстановление
        # =========================
        if not hasattr(self, "_pool_lock"):
            self._pool_lock = asyncio.Lock()
        if not hasattr(self, "_pool_last_fail"):
            self._pool_last_fail = 0.0
        if not hasattr(self, "_pool_fail_cooldown"):
            self._pool_fail_cooldown = 2.0

        # =========================
        # Group cache locks (если у тебя используется)
        # =========================
        if not hasattr(self, "GROUP_CACHE_TTL"):
            self.GROUP_CACHE_TTL = 15 * 60  # 15 минут
        if not hasattr(self, "_group_cache_ts"):
            self._group_cache_ts = {}  # chat_id -> ts
        if not hasattr(self, "_group_locks"):
            self._group_locks = {}  # chat_id -> asyncio.Lock

        # ==================================================================
        # ✅ JACKCHAT - НАСТРОЙКИ (в одном месте)
        # ==================================================================
        if not hasattr(self, "JACKCHAT_DEBUG"):
            self.JACKCHAT_DEBUG = False

        if not hasattr(self, "JACKCHAT_ACTIVE_INTERVAL"):
            self.JACKCHAT_ACTIVE_INTERVAL = 60.0
        if not hasattr(self, "JACKCHAT_IDLE_INTERVAL"):
            self.JACKCHAT_IDLE_INTERVAL = 600.0

        if not hasattr(self, "JACKCHAT_FAIL_MIN"):
            self.JACKCHAT_FAIL_MIN = 10.0
        if not hasattr(self, "JACKCHAT_FAIL_MAX"):
            self.JACKCHAT_FAIL_MAX = 180.0

        if not hasattr(self, "JACKCHAT_TICK"):
            self.JACKCHAT_TICK = 1.0
        if not hasattr(self, "JACKCHAT_MAX_PER_TICK"):
            self.JACKCHAT_MAX_PER_TICK = 2

        if not hasattr(self, "JACKCHAT_USER_TTL"):
            self.JACKCHAT_USER_TTL = 180.0

        if not hasattr(self, "JACKCHAT_STATE_TTL"):
            self.JACKCHAT_STATE_TTL = 3600.0

        if not hasattr(self, "JACKCHAT_LOG_EVERY_TICK"):
            self.JACKCHAT_LOG_EVERY_TICK = False

        # ✅ TG защитные лимиты (важно, чтобы не дергать TG каждые 1 сек)
        if not hasattr(self, "JACKCHAT_TG_MIN_INTERVAL"):
            self.JACKCHAT_TG_MIN_INTERVAL = 20.0  # минимум между TG вызовами по одному chat_id
        if not hasattr(self, "JACKCHAT_ACTIVITY_SOON_DELAY"):
            self.JACKCHAT_ACTIVITY_SOON_DELAY = 1.0  # после сообщения ставим check не раньше, чем через 1с

        # =========================
        # JackChat runtime state
        # =========================
        if not hasattr(self, "_jackchat_state"):
            self._jackchat_state: Dict[int, Dict[str, Any]] = {}

        if not hasattr(self, "_jackchat_locks"):
            self._jackchat_locks: Dict[int, asyncio.Lock] = {}

        if not hasattr(self, "_jackchat_task"):
            self._jackchat_task: Optional[asyncio.Task] = None

        if not hasattr(self, "_jackchat_stop"):
            self._jackchat_stop = False

        if not hasattr(self, "_jackchat_user_cache"):
            self._jackchat_user_cache: Dict[int, Dict[str, Any]] = {}

        if not hasattr(self, "_jackchat_last_tick_log"):
            self._jackchat_last_tick_log = 0.0

    async def ensure_king_stats_schema(self) -> None:
        if not await self.ensure_pool():
            raise RuntimeError("Пул соединений не инициализирован (ensure_king_stats_schema).")

        sql = """
        ALTER TABLE chat
            ADD COLUMN IF NOT EXISTS creator_id BIGINT,
            ADD COLUMN IF NOT EXISTS namechat TEXT,
            ADD COLUMN IF NOT EXISTS usernamechat TEXT,
            ADD COLUMN IF NOT EXISTS chatlink TEXT;

        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS king_stats JSONB NOT NULL DEFAULT '{}'::jsonb;

        CREATE TABLE IF NOT EXISTS chat_king_reward_settings (
            chat_id BIGINT PRIMARY KEY,
            creator_id BIGINT,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            min_messages INT NOT NULL DEFAULT 0 CHECK (min_messages >= 0),
            period_kind TEXT NOT NULL DEFAULT 'day',
            reward_p1 JSONB NOT NULL DEFAULT '{}'::jsonb,
            reward_p2 JSONB NOT NULL DEFAULT '{}'::jsonb,
            reward_p3 JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        ALTER TABLE chat_king_reward_settings
            ADD COLUMN IF NOT EXISTS period_kind TEXT NOT NULL DEFAULT 'day';
        ALTER TABLE chat_king_reward_settings
            ADD COLUMN IF NOT EXISTS active_until_ts TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS start_at_ts TIMESTAMPTZ;
        UPDATE chat_king_reward_settings
        SET period_kind = 'day'
        WHERE period_kind IS NULL
           OR COALESCE(period_kind, '') = ''
           OR period_kind NOT IN ('day', 'week', 'month');
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'chk_chat_king_reward_settings_period_kind'
                  AND conrelid = 'chat_king_reward_settings'::regclass
            ) THEN
                ALTER TABLE chat_king_reward_settings
                    ADD CONSTRAINT chk_chat_king_reward_settings_period_kind
                    CHECK (period_kind IN ('day', 'week', 'month'));
            END IF;
        END $$;
        ALTER TABLE chat_king_reward_settings
            ALTER COLUMN min_messages SET DEFAULT 0;
        -- Сносим ЛЮБЫЕ старые CHECK-ограничения на min_messages, не полагаясь на
        -- имя. В проде обнаружилось ограничение ck_king_settings_min_messages,
        -- запрещающее ноль: из-за него падал INSERT в ensure_chat_king_settings_row,
        -- то есть любая первая запись настроек для чата. Перечисление имён такие
        -- случаи не ловит, поэтому ищем по определению ограничения.
        DO $$
        DECLARE
            legacy record;
        BEGIN
            FOR legacy IN
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'chat_king_reward_settings'::regclass
                  AND contype = 'c'
                  AND pg_get_constraintdef(oid) ILIKE '%min_messages%'
                  AND conname <> 'chk_chat_king_reward_settings_min_messages_non_negative'
            LOOP
                EXECUTE format(
                    'ALTER TABLE chat_king_reward_settings DROP CONSTRAINT %I',
                    legacy.conname
                );
            END LOOP;
        END $$;
        UPDATE chat_king_reward_settings
        SET min_messages = 0
        WHERE min_messages IS NULL
           OR min_messages < 0;
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'chk_chat_king_reward_settings_min_messages_non_negative'
                  AND conrelid = 'chat_king_reward_settings'::regclass
            ) THEN
                ALTER TABLE chat_king_reward_settings
                    ADD CONSTRAINT chk_chat_king_reward_settings_min_messages_non_negative
                    CHECK (min_messages >= 0);
            END IF;
        END $$;

        CREATE TABLE IF NOT EXISTS chat_king_daily_results (
            id BIGSERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            stat_date DATE NOT NULL,
            winner_user_id BIGINT,
            top_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            total_messages BIGINT NOT NULL DEFAULT 0,
            announced BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            announced_at TIMESTAMPTZ,
            UNIQUE (chat_id, stat_date)
        );
        ALTER TABLE chat_king_daily_results
            ADD COLUMN IF NOT EXISTS period_type TEXT NOT NULL DEFAULT 'day',
            ADD COLUMN IF NOT EXISTS period_key TEXT NOT NULL DEFAULT '',
            ADD COLUMN IF NOT EXISTS period_from DATE,
            ADD COLUMN IF NOT EXISTS period_to DATE;
        UPDATE chat_king_daily_results
        SET period_type = 'day'
        WHERE COALESCE(period_type, '') = '';
        UPDATE chat_king_daily_results
        SET period_key = TO_CHAR(stat_date, 'YYYY-MM-DD')
        WHERE COALESCE(period_key, '') = '';
        ALTER TABLE chat_king_daily_results
            DROP CONSTRAINT IF EXISTS chat_king_daily_results_chat_id_stat_date_key;
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_chat_king_daily_results_period'
                  AND conrelid = 'chat_king_daily_results'::regclass
            ) THEN
                ALTER TABLE chat_king_daily_results
                    ADD CONSTRAINT uq_chat_king_daily_results_period
                    UNIQUE (chat_id, period_type, period_key);
            END IF;
        END $$;
        CREATE INDEX IF NOT EXISTS idx_chat_king_daily_results_chat_date
            ON chat_king_daily_results (chat_id, stat_date DESC);
        CREATE INDEX IF NOT EXISTS idx_chat_king_daily_results_period
            ON chat_king_daily_results (chat_id, period_type, created_at DESC);

        CREATE TABLE IF NOT EXISTS chat_king_reward_log (
            id BIGSERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            stat_date DATE NOT NULL,
            user_id BIGINT NOT NULL,
            place SMALLINT NOT NULL CHECK (place BETWEEN 1 AND 3),
            kut_awarded BIGINT NOT NULL DEFAULT 0,
            items_awarded_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            delivered BOOLEAN NOT NULL DEFAULT FALSE,
            details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            delivered_at TIMESTAMPTZ,
            UNIQUE (chat_id, stat_date, user_id, place)
        );
        ALTER TABLE chat_king_reward_log
            ADD COLUMN IF NOT EXISTS period_type TEXT NOT NULL DEFAULT 'day',
            ADD COLUMN IF NOT EXISTS period_key TEXT NOT NULL DEFAULT '';
        UPDATE chat_king_reward_log
        SET period_type = 'day'
        WHERE COALESCE(period_type, '') = '';
        UPDATE chat_king_reward_log
        SET period_key = TO_CHAR(stat_date, 'YYYY-MM-DD')
        WHERE COALESCE(period_key, '') = '';
        ALTER TABLE chat_king_reward_log
            DROP CONSTRAINT IF EXISTS chat_king_reward_log_chat_id_stat_date_user_id_place_key;
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_chat_king_reward_log_period_user_place'
                  AND conrelid = 'chat_king_reward_log'::regclass
            ) THEN
                ALTER TABLE chat_king_reward_log
                    ADD CONSTRAINT uq_chat_king_reward_log_period_user_place
                    UNIQUE (chat_id, period_type, period_key, user_id, place);
            END IF;
        END $$;
        CREATE INDEX IF NOT EXISTS idx_chat_king_reward_log_chat_date
            ON chat_king_reward_log (chat_id, stat_date DESC, place ASC);
        CREATE INDEX IF NOT EXISTS idx_chat_king_reward_log_period
            ON chat_king_reward_log (chat_id, period_type, created_at DESC, place ASC);
        """

        async with self.pool.acquire() as conn:
            await conn.execute(sql)

    def _king_place_column(self, place: int) -> str:
        mapping = {1: "reward_p1", 2: "reward_p2", 3: "reward_p3"}
        key = int(place)
        if key not in mapping:
            raise ValueError("Место должно быть 1, 2 или 3")
        return mapping[key]

    def _normalize_king_period_kind(self, value: Any) -> str:
        token = str(value or "").strip().lower()
        if token in {"day", "week", "month"}:
            return token
        return "day"

    def _default_king_period_kind(self) -> str:
        try:
            from bot.config.config import KING_STATS_PERIOD_KIND as _KING_STATS_PERIOD_KIND
        except Exception:
            _KING_STATS_PERIOD_KIND = "day"
        return self._normalize_king_period_kind(_KING_STATS_PERIOD_KIND)

    async def resolve_dex_item_token(self, token: str) -> dict[str, Any] | None:
        """
        Находит предмет в dex по любому токену:
        - id (число)
        - name (точно/без регистра)
        - name1 (алиас)
        - emoji
        Возвращает {id, name, name1, emoji} или None.
        """
        if not await self.ensure_pool():
            return None

        raw = str(token or "").strip()
        if not raw:
            return None

        async with self.pool.acquire() as conn:
            row = None

            if raw.isdigit():
                row = await conn.fetchrow(
                    """
                    SELECT id, name, name1, emoji
                    FROM dex
                    WHERE id = $1
                    LIMIT 1
                    """,
                    int(raw),
                )
                if row:
                    return {
                        "id": int(row["id"]),
                        "name": str(row["name"] or ""),
                        "name1": str(row["name1"] or ""),
                        "emoji": str(row["emoji"] or ""),
                    }

            row = await conn.fetchrow(
                """
                SELECT id, name, name1, emoji
                FROM dex
                WHERE emoji = $1
                   OR LOWER(name) = LOWER($1)
                   OR LOWER(name1) = LOWER($1)
                ORDER BY id ASC
                LIMIT 1
                """,
                raw,
            )
            if row:
                return {
                    "id": int(row["id"]),
                    "name": str(row["name"] or ""),
                    "name1": str(row["name1"] or ""),
                    "emoji": str(row["emoji"] or ""),
                }

            row = await conn.fetchrow(
                """
                SELECT id, name, name1, emoji
                FROM dex
                WHERE name ILIKE $1
                   OR name1 ILIKE $1
                ORDER BY id ASC
                LIMIT 1
                """,
                f"{raw}%",
            )

            if row:
                return {
                    "id": int(row["id"]),
                    "name": str(row["name"] or ""),
                    "name1": str(row["name1"] or ""),
                    "emoji": str(row["emoji"] or ""),
                }
        return None

    def _parse_json_obj(self, value: Any, default: dict[str, Any] | None = None) -> dict[str, Any]:
        fallback = default.copy() if isinstance(default, dict) else {}
        if value is None:
            return fallback
        if isinstance(value, dict):
            return value.copy()
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return fallback
        return fallback

    def _parse_json_list(self, value: Any, default: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        fallback = list(default or [])
        if value is None:
            return fallback
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [item for item in parsed if isinstance(item, dict)]
            except Exception:
                return fallback
        return fallback

    def _normalize_king_reward_payload(self, payload: Any) -> dict[str, Any]:
        source = self._parse_json_obj(payload)
        kut = max(0, int(source.get("kut", 0) or 0))
        raw_items = source.get("items", [])
        if isinstance(raw_items, str):
            try:
                raw_items = json.loads(raw_items)
            except Exception:
                raw_items = []
        if not isinstance(raw_items, list):
            raw_items = []

        merged: dict[str, int] = {}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("item_id") or item.get("id") or "").strip()
            if not item_id:
                continue
            amount = int(item.get("amount") or item.get("qty") or 0)
            if amount <= 0:
                continue
            merged[item_id] = merged.get(item_id, 0) + amount

        items = [{"item_id": key, "amount": value} for key, value in merged.items() if value > 0]
        return {"kut": kut, "items": items}

    def _default_king_settings(self, chat_id: int) -> dict[str, Any]:
        return {
            "chat_id": int(chat_id),
            "creator_id": None,
            "enabled": False,
            "min_messages": 0,
            "period_kind": self._default_king_period_kind(),
            "active_until_ts": None,
            "start_at_ts": None,
            "place_1": {"kut": 0, "items": []},
            "place_2": {"kut": 0, "items": []},
            "place_3": {"kut": 0, "items": []},
        }

    async def ensure_chat_king_settings_row(self, chat_id: int, creator_id: int | None = None) -> None:
        await self.ensure_king_stats_schema()
        default_period_kind = self._default_king_period_kind()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_king_reward_settings (chat_id, creator_id, period_kind)
                VALUES ($1, $2, $3)
                ON CONFLICT (chat_id) DO NOTHING
                """,
                int(chat_id),
                int(creator_id) if creator_id is not None else None,
                default_period_kind,
            )
            if creator_id is not None:
                await conn.execute(
                    """
                    UPDATE chat_king_reward_settings
                    SET creator_id = $2,
                        updated_at = NOW()
                    WHERE chat_id = $1
                    """,
                    int(chat_id),
                    int(creator_id),
                )

    async def get_chat_king_reward_settings(self, chat_id: int) -> dict[str, Any]:
        await self.ensure_king_stats_schema()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT chat_id, creator_id, enabled, min_messages, period_kind, active_until_ts, start_at_ts, reward_p1, reward_p2, reward_p3
                FROM chat_king_reward_settings
                WHERE chat_id = $1
                """,
                int(chat_id),
            )
        if not row:
            return self._default_king_settings(chat_id)
        return {
            "chat_id": int(row["chat_id"]),
            "creator_id": int(row["creator_id"]) if row["creator_id"] is not None else None,
            "enabled": bool(row["enabled"]),
            "min_messages": max(0, int(row["min_messages"] or 0)),
            "period_kind": self._normalize_king_period_kind(row["period_kind"]),
            "active_until_ts": row["active_until_ts"],
            "start_at_ts": row["start_at_ts"],
            "place_1": self._normalize_king_reward_payload(row["reward_p1"]),
            "place_2": self._normalize_king_reward_payload(row["reward_p2"]),
            "place_3": self._normalize_king_reward_payload(row["reward_p3"]),
        }

    async def set_chat_king_enabled(
            self,
            chat_id: int,
            enabled: bool,
            *,
            creator_id: int | None = None,
    ) -> dict[str, Any]:
        await self.ensure_chat_king_settings_row(chat_id, creator_id=creator_id)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_king_reward_settings
                SET enabled = $2,
                    creator_id = COALESCE($3, creator_id),
                    updated_at = NOW()
                WHERE chat_id = $1
                """,
                int(chat_id),
                bool(enabled),
                int(creator_id) if creator_id is not None else None,
            )
        return await self.get_chat_king_reward_settings(chat_id)

    async def set_chat_king_min_messages(
            self,
            chat_id: int,
            min_messages: int,
            *,
            creator_id: int | None = None,
    ) -> dict[str, Any]:
        await self.ensure_chat_king_settings_row(chat_id, creator_id=creator_id)
        min_value = max(0, int(min_messages))
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_king_reward_settings
                SET min_messages = $2,
                    creator_id = COALESCE($3, creator_id),
                    updated_at = NOW()
                WHERE chat_id = $1
                """,
                int(chat_id),
                min_value,
                int(creator_id) if creator_id is not None else None,
            )
        return await self.get_chat_king_reward_settings(chat_id)

    async def set_chat_king_period_kind(
            self,
            chat_id: int,
            period_kind: str,
            *,
            creator_id: int | None = None,
    ) -> dict[str, Any]:
        await self.ensure_chat_king_settings_row(chat_id, creator_id=creator_id)
        period_kind_s = self._normalize_king_period_kind(period_kind)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_king_reward_settings
                SET period_kind = $2,
                    creator_id = COALESCE($3, creator_id),
                    updated_at = NOW()
                WHERE chat_id = $1
                """,
                int(chat_id),
                period_kind_s,
                int(creator_id) if creator_id is not None else None,
            )
        return await self.get_chat_king_reward_settings(chat_id)

    async def set_chat_king_active_until(
            self,
            chat_id: int,
            active_until_ts: datetime | None,
            *,
            creator_id: int | None = None,
    ) -> dict[str, Any]:
        await self.ensure_chat_king_settings_row(chat_id, creator_id=creator_id)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_king_reward_settings
                SET active_until_ts = $2,
                    creator_id = COALESCE($3, creator_id),
                    updated_at = NOW()
                WHERE chat_id = $1
                """,
                int(chat_id),
                active_until_ts,
                int(creator_id) if creator_id is not None else None,
            )
        return await self.get_chat_king_reward_settings(chat_id)

    async def set_chat_king_start_at(
            self,
            chat_id: int,
            start_at_ts: datetime | None,
            *,
            creator_id: int | None = None,
    ) -> dict[str, Any]:
        await self.ensure_chat_king_settings_row(chat_id, creator_id=creator_id)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_king_reward_settings
                SET start_at_ts = $2,
                    creator_id = COALESCE($3, creator_id),
                    updated_at = NOW()
                WHERE chat_id = $1
                """,
                int(chat_id),
                start_at_ts,
                int(creator_id) if creator_id is not None else None,
            )
        return await self.get_chat_king_reward_settings(chat_id)

    async def allocate_creator_item_rewards(
            self,
            creator_id: int | None,
            winners: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Резервирует предметы для выплат "Царя статистики" строго из инвентаря создателя.
        Ничего не "чеканится": если предметов не хватает, возвращаем частичную/нулевую выдачу.
        """
        try:
            creator_id_safe = int(creator_id) if creator_id is not None else None
        except Exception:
            creator_id_safe = None

        result: dict[str, Any] = {
            "ok": True,
            "creator_id": creator_id_safe,
            "alloc_by_user": {},
            "missing_by_user": {},
            "updated": False,
        }

        if creator_id is None:
            return result
        creator_i = int(creator_id)
        if creator_i <= 0:
            return result

        normalized_winners: list[dict[str, Any]] = []
        token_to_name: dict[str, str] = {}
        for row in winners or []:
            try:
                uid = int(row.get("user_id") or 0)
            except Exception:
                uid = 0
            if uid <= 0:
                continue

            planned_items: list[dict[str, Any]] = []
            for item in row.get("planned_items") or []:
                if not isinstance(item, dict):
                    continue
                token = str(item.get("item_id") or "").strip()
                try:
                    amount = max(0, int(item.get("amount") or 0))
                except Exception:
                    amount = 0
                if not token or amount <= 0:
                    continue

                resolved_name = token_to_name.get(token)
                if resolved_name is None:
                    resolved_name = token
                    try:
                        resolved_item = await self.resolve_dex_item_token(token)
                        if resolved_item and str(resolved_item.get("name") or "").strip():
                            resolved_name = str(resolved_item.get("name")).strip()
                    except Exception:
                        resolved_name = token
                    token_to_name[token] = resolved_name

                planned_items.append(
                    {
                        "token": token,
                        "item_id": str(resolved_name),
                        "amount": int(amount),
                    }
                )

            normalized_winners.append({"user_id": uid, "items": planned_items})
            result["alloc_by_user"][uid] = []
            result["missing_by_user"][uid] = []

        if not any(row.get("items") for row in normalized_winners):
            return result

        if not await self.ensure_pool():
            return {"ok": False, "error": "pool_unavailable", "alloc_by_user": {}, "missing_by_user": {}}

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    creator_row = await conn.fetchrow(
                        """
                        SELECT items
                        FROM users
                        WHERE user_id = $1
                        FOR UPDATE
                        """,
                        creator_i,
                    )
                    if not creator_row:
                        for row in normalized_winners:
                            uid = int(row["user_id"])
                            result["missing_by_user"][uid].extend(
                                [{"item_id": str(it["item_id"]), "amount": int(it["amount"])} for it in
                                 row.get("items") or []]
                            )
                        result["reason"] = "creator_not_found"
                        result["alloc_by_user"] = {k: v for k, v in result["alloc_by_user"].items() if v}
                        result["missing_by_user"] = {k: v for k, v in result["missing_by_user"].items() if v}
                        return result

                    inventory_raw = creator_row["items"]
                    inventory_decoded = decode_items(inventory_raw)
                    inventory: dict[str, int] = {}
                    if isinstance(inventory_decoded, dict):
                        for key, value in inventory_decoded.items():
                            item_name = str(key or "").strip()
                            if not item_name:
                                continue
                            try:
                                qty = int(value or 0)
                            except Exception:
                                qty = 0
                            if qty > 0:
                                inventory[item_name] = qty

                    changed = False
                    for row in normalized_winners:
                        uid = int(row["user_id"])
                        for item in row.get("items") or []:
                            token = str(item.get("token") or "").strip()
                            item_name = str(item.get("item_id") or "").strip()
                            need = max(0, int(item.get("amount") or 0))
                            if not item_name or need <= 0:
                                continue

                            deduct_key = item_name
                            have = max(0, int(inventory.get(deduct_key, 0)))
                            if have <= 0 and token and token != item_name:
                                token_have = max(0, int(inventory.get(token, 0)))
                                if token_have > 0:
                                    have = token_have
                                    deduct_key = token

                            give = min(need, have)
                            if give > 0:
                                remaining = have - give
                                if remaining > 0:
                                    inventory[deduct_key] = remaining
                                else:
                                    inventory.pop(deduct_key, None)
                                changed = True
                                result["alloc_by_user"][uid].append({"item_id": item_name, "amount": int(give)})

                            miss = need - give
                            if miss > 0:
                                result["missing_by_user"][uid].append({"item_id": item_name, "amount": int(miss)})

                    if changed:
                        await conn.execute(
                            "UPDATE users SET items = $2 WHERE user_id = $1",
                            creator_i,
                            encode_items(inventory),
                        )
                        result["updated"] = True

            result["alloc_by_user"] = {k: v for k, v in result["alloc_by_user"].items() if v}
            result["missing_by_user"] = {k: v for k, v in result["missing_by_user"].items() if v}
            return result
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "creator_id": creator_i,
                "alloc_by_user": {},
                "missing_by_user": {},
                "updated": False,
            }

    async def reset_chat_king_settings(
            self,
            chat_id: int,
            *,
            creator_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Полный сброс настроек «Царя статистики» для группы:
        - выключает систему
        - сбрасывает порог/период/срок/дату старта
        - очищает награды 1/2/3 мест
        """
        await self.ensure_chat_king_settings_row(chat_id, creator_id=creator_id)
        default_period_kind = self._default_king_period_kind()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_king_reward_settings
                SET enabled = FALSE,
                    min_messages = 0,
                    period_kind = $2,
                    active_until_ts = NULL,
                    start_at_ts = NULL,
                    reward_p1 = '{}'::jsonb,
                    reward_p2 = '{}'::jsonb,
                    reward_p3 = '{}'::jsonb,
                    creator_id = COALESCE($3, creator_id),
                    updated_at = NOW()
                WHERE chat_id = $1
                """,
                int(chat_id),
                default_period_kind,
                int(creator_id) if creator_id is not None else None,
            )
        return await self.get_chat_king_reward_settings(chat_id)

    async def set_chat_king_place_kut_reward(
            self,
            chat_id: int,
            place: int,
            kut: int,
            *,
            creator_id: int | None = None,
    ) -> dict[str, Any]:
        await self.ensure_chat_king_settings_row(chat_id, creator_id=creator_id)
        settings = await self.get_chat_king_reward_settings(chat_id)
        reward = self._normalize_king_reward_payload(settings.get(f"place_{int(place)}"))
        reward["kut"] = max(0, int(kut))
        column = self._king_place_column(place)
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE chat_king_reward_settings
                SET {column} = $2::jsonb,
                    creator_id = COALESCE($3, creator_id),
                    updated_at = NOW()
                WHERE chat_id = $1
                """,
                int(chat_id),
                json.dumps(reward, ensure_ascii=False),
                int(creator_id) if creator_id is not None else None,
            )
        return await self.get_chat_king_reward_settings(chat_id)

    async def add_chat_king_place_item_reward(
            self,
            chat_id: int,
            place: int,
            item_id: str,
            amount: int,
            *,
            creator_id: int | None = None,
    ) -> dict[str, Any]:
        item_token = str(item_id or "").strip()
        amount_i = int(amount)
        if not item_token:
            raise ValueError("item_id пустой")
        if amount_i <= 0:
            raise ValueError("Количество предмета должно быть больше 0")

        await self.ensure_chat_king_settings_row(chat_id, creator_id=creator_id)
        settings = await self.get_chat_king_reward_settings(chat_id)
        reward = self._normalize_king_reward_payload(settings.get(f"place_{int(place)}"))

        merged: dict[str, int] = {}
        for row in reward.get("items", []):
            if not isinstance(row, dict):
                continue
            key = str(row.get("item_id") or "").strip()
            value = int(row.get("amount") or 0)
            if key and value > 0:
                merged[key] = merged.get(key, 0) + value
        merged[item_token] = merged.get(item_token, 0) + amount_i
        reward["items"] = [{"item_id": key, "amount": value} for key, value in merged.items() if value > 0]

        column = self._king_place_column(place)
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE chat_king_reward_settings
                SET {column} = $2::jsonb,
                    creator_id = COALESCE($3, creator_id),
                    updated_at = NOW()
                WHERE chat_id = $1
                """,
                int(chat_id),
                json.dumps(reward, ensure_ascii=False),
                int(creator_id) if creator_id is not None else None,
            )
        return await self.get_chat_king_reward_settings(chat_id)

    async def clear_chat_king_place_reward(
            self,
            chat_id: int,
            place: int,
            *,
            creator_id: int | None = None,
    ) -> dict[str, Any]:
        await self.ensure_chat_king_settings_row(chat_id, creator_id=creator_id)
        column = self._king_place_column(place)
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE chat_king_reward_settings
                SET {column} = $2::jsonb,
                    creator_id = COALESCE($3, creator_id),
                    updated_at = NOW()
                WHERE chat_id = $1
                """,
                int(chat_id),
                json.dumps({}, ensure_ascii=False),
                int(creator_id) if creator_id is not None else None,
            )
        return await self.get_chat_king_reward_settings(chat_id)

    async def get_chat_meta_basic(self, chat_id: int) -> dict[str, Any]:
        chat_id_i = int(chat_id)
        if not await self.ensure_pool():
            return {
                "chat_id": chat_id_i,
                "namechat": None,
                "usernamechat": None,
                "chatlink": None,
                "creator_id": None,
                "chatbalance": 0,
            }

        async with self.pool.acquire() as conn:
            row = None
            try:
                row = await conn.fetchrow(
                    """
                    SELECT chat_id, namechat, usernamechat, chatlink, creator_id, COALESCE(chatbalance, 0) AS chatbalance
                    FROM chat
                    WHERE chat_id = $1
                    LIMIT 1
                    """,
                    chat_id_i,
                )
            except Exception:
                # В старых схемах поля creator_id/chatlink могут отсутствовать.
                row = await conn.fetchrow(
                    """
                    SELECT chat_id, namechat, usernamechat, COALESCE(chatbalance, 0) AS chatbalance
                    FROM chat
                    WHERE chat_id = $1
                    LIMIT 1
                    """,
                    chat_id_i,
                )

        if not row:
            return {
                "chat_id": chat_id_i,
                "namechat": None,
                "usernamechat": None,
                "chatlink": None,
                "creator_id": None,
                "chatbalance": 0,
            }

        keys = set(row.keys()) if hasattr(row, "keys") else set()
        return {
            "chat_id": int(row["chat_id"]),
            "namechat": row["namechat"] if "namechat" in keys else None,
            "usernamechat": row["usernamechat"] if "usernamechat" in keys else None,
            "chatlink": row["chatlink"] if "chatlink" in keys else None,
            "creator_id": int(row["creator_id"]) if ("creator_id" in keys and row["creator_id"] is not None) else None,
            "chatbalance": int(row["chatbalance"] or 0) if "chatbalance" in keys else 0,
        }

    async def list_creator_groups_with_positive_balance(
            self,
            creator_id: int,
            *,
            exclude_chat_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if not await self.ensure_pool():
            return []

        creator_id_i = int(creator_id)
        exclude_id = int(exclude_chat_id) if exclude_chat_id is not None else None
        async with self.pool.acquire() as conn:
            try:
                if exclude_id is None:
                    rows = await conn.fetch(
                        """
                        SELECT chat_id, namechat, usernamechat, chatlink, COALESCE(chatbalance, 0) AS chatbalance
                        FROM chat
                        WHERE creator_id = $1
                          AND COALESCE(chatbalance, 0) > 0
                        ORDER BY chatbalance DESC, chat_id ASC
                        """,
                        creator_id_i,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT chat_id, namechat, usernamechat, chatlink, COALESCE(chatbalance, 0) AS chatbalance
                        FROM chat
                        WHERE creator_id = $1
                          AND chat_id <> $2
                          AND COALESCE(chatbalance, 0) > 0
                        ORDER BY chatbalance DESC, chat_id ASC
                        """,
                        creator_id_i,
                        exclude_id,
                    )
            except Exception:
                # Если в схеме нет creator_id/chatlink/namechat, возвращаем пусто.
                return []

        result: list[dict[str, Any]] = []
        for row in rows or []:
            result.append(
                {
                    "chat_id": int(row["chat_id"]),
                    "namechat": row["namechat"],
                    "usernamechat": row["usernamechat"],
                    "chatlink": row["chatlink"] if "chatlink" in row.keys() else None,
                    "chatbalance": int(row["chatbalance"] or 0),
                }
            )
        return result

    async def deduct_chatbalance_up_to(self, chat_id: int, amount: int) -> dict[str, Any]:
        """
        Снимает ИЗ chat.chatbalance до amount (не более доступного).
        Возвращает фактически списанную сумму и новый баланс.
        """
        if not await self.ensure_pool():
            return {"ok": False, "deducted": 0, "chatbalance_after": 0}

        cid = int(chat_id)
        need = max(0, int(amount))
        if need <= 0:
            snap = await self.fetch_group_balances(cid)
            return {
                "ok": True,
                "deducted": 0,
                "chatbalance_after": int(snap.chatbalance if snap else 0),
            }

        deducted = 0
        chat_after = 0
        dex_after = 0
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT COALESCE(chatbalance, 0) AS chatbalance, COALESCE(dexbalance, 0) AS dexbalance
                    FROM chat
                    WHERE chat_id = $1
                    LIMIT 1
                    FOR UPDATE
                    """,
                    cid,
                )
                if not row:
                    return {"ok": False, "deducted": 0, "chatbalance_after": 0}

                current_chat = int(row["chatbalance"] or 0)
                current_dex = int(row["dexbalance"] or 0)
                deducted = min(current_chat, need)

                if deducted > 0:
                    row_after = await conn.fetchrow(
                        """
                        UPDATE chat
                        SET chatbalance = GREATEST(COALESCE(chatbalance, 0) - $2, 0)
                        WHERE chat_id = $1
                        RETURNING COALESCE(chatbalance, 0) AS chatbalance, COALESCE(dexbalance, 0) AS dexbalance
                        """,
                        cid,
                        deducted,
                    )
                    chat_after = int(row_after["chatbalance"] or 0) if row_after else max(0, current_chat - deducted)
                    dex_after = int(row_after["dexbalance"] or 0) if row_after else current_dex
                else:
                    chat_after = current_chat
                    dex_after = current_dex

        try:
            self.__fastlane_set__(cid, BalanceSnapshot(chatbalance=chat_after, dexbalance=dex_after))
            self.__negguard_clear__(cid)
        except Exception:
            pass

        return {
            "ok": True,
            "deducted": int(deducted),
            "chatbalance_after": int(chat_after),
        }

    async def list_chat_ids_with_king_enabled(self) -> list[int]:
        await self.ensure_king_stats_schema()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT chat_id
                FROM chat_king_reward_settings
                WHERE enabled = TRUE
                ORDER BY chat_id ASC
                """
            )
        return [int(row["chat_id"]) for row in rows]

    async def list_enabled_chat_king_profiles(self) -> list[dict[str, Any]]:
        await self.ensure_king_stats_schema()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT chat_id, period_kind, start_at_ts, active_until_ts
                FROM chat_king_reward_settings
                WHERE enabled = TRUE
                ORDER BY chat_id ASC
                """
            )
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "chat_id": int(row["chat_id"]),
                    "period_kind": self._normalize_king_period_kind(row["period_kind"]),
                    "start_at_ts": row["start_at_ts"],
                    "active_until_ts": row["active_until_ts"],
                }
            )
        return result

    async def has_chat_king_period_result(self, chat_id: int, period_type: str, period_key: str) -> bool:
        await self.ensure_king_stats_schema()
        period_type_s = str(period_type or "day").strip().lower() or "day"
        period_key_s = str(period_key or "").strip()
        if not period_key_s:
            return False

        async with self.pool.acquire() as conn:
            exists = await conn.fetchval(
                """
                SELECT 1
                FROM chat_king_daily_results
                WHERE chat_id = $1
                  AND period_type = $2
                  AND period_key = $3
                LIMIT 1
                """,
                int(chat_id),
                period_type_s,
                period_key_s,
            )
        return bool(exists)

    async def has_chat_king_day_result(self, chat_id: int, stat_date: date) -> bool:
        return await self.has_chat_king_period_result(
            chat_id=int(chat_id),
            period_type="day",
            period_key=stat_date.isoformat(),
        )

    async def create_chat_king_period_result(
            self,
            *,
            chat_id: int,
            stat_date: date,
            period_type: str,
            period_key: str,
            period_from: date | None,
            period_to: date | None,
            winner_user_id: int | None,
            top_rows: list[dict[str, Any]],
            total_messages: int,
    ) -> bool:
        await self.ensure_king_stats_schema()
        period_type_s = str(period_type or "day").strip().lower() or "day"
        period_key_s = str(period_key or "").strip()
        if not period_key_s:
            raise ValueError("period_key пустой")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO chat_king_daily_results (
                    chat_id,
                    stat_date,
                    period_type,
                    period_key,
                    period_from,
                    period_to,
                    winner_user_id,
                    top_json,
                    total_messages
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
                ON CONFLICT (chat_id, period_type, period_key) DO NOTHING
                RETURNING id
                """,
                int(chat_id),
                stat_date,
                period_type_s,
                period_key_s,
                period_from,
                period_to,
                int(winner_user_id) if winner_user_id is not None else None,
                json.dumps(top_rows, ensure_ascii=False),
                int(total_messages or 0),
            )
        return bool(row)

    async def create_chat_king_day_result(
            self,
            chat_id: int,
            stat_date: date,
            winner_user_id: int | None,
            top_rows: list[dict[str, Any]],
            total_messages: int,
    ) -> bool:
        return await self.create_chat_king_period_result(
            chat_id=int(chat_id),
            stat_date=stat_date,
            period_type="day",
            period_key=stat_date.isoformat(),
            period_from=stat_date,
            period_to=stat_date,
            winner_user_id=winner_user_id,
            top_rows=top_rows,
            total_messages=total_messages,
        )

    async def mark_chat_king_period_announced(self, chat_id: int, period_type: str, period_key: str) -> None:
        await self.ensure_king_stats_schema()
        period_type_s = str(period_type or "day").strip().lower() or "day"
        period_key_s = str(period_key or "").strip()
        if not period_key_s:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_king_daily_results
                SET announced = TRUE,
                    announced_at = NOW()
                WHERE chat_id = $1
                  AND period_type = $2
                  AND period_key = $3
                """,
                int(chat_id),
                period_type_s,
                period_key_s,
            )

    async def mark_chat_king_day_announced(self, chat_id: int, stat_date: date) -> None:
        await self.mark_chat_king_period_announced(
            chat_id=int(chat_id),
            period_type="day",
            period_key=stat_date.isoformat(),
        )

    async def get_user_king_stats(self, user_id: int) -> dict[str, Any]:
        await self.ensure_king_stats_schema()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT king_stats FROM users WHERE user_id = $1",
                int(user_id),
            )

        raw = self._parse_json_obj(row["king_stats"] if row else {})
        now_month_key = datetime.now().strftime("%Y-%m")
        month_key = str(raw.get("day_king_month_key") or "")
        month_count = int(raw.get("day_king_month_count") or 0)
        if month_key != now_month_key:
            month_count = 0

        return {
            "day_king_total_count": int(raw.get("day_king_total_count") or 0),
            "day_king_month_count": max(0, month_count),
            "day_king_month_key": now_month_key,
            "last_day_king_date": str(raw.get("last_day_king_date") or ""),
            "last_day_king_chat_id": int(raw.get("last_day_king_chat_id") or 0),
        }

    async def get_user_chat_king_summary(
            self,
            *,
            chat_id: int,
            user_id: int,
            reference_date: date | None = None,
    ) -> dict[str, Any]:
        await self.ensure_king_stats_schema()
        ref = reference_date or datetime.now().date()
        ref = ref if isinstance(ref, date) else datetime.now().date()

        month_start = ref.replace(day=1)
        if month_start.month == 12:
            month_next = date(month_start.year + 1, 1, 1)
        else:
            month_next = date(month_start.year, month_start.month + 1, 1)

        year_start = date(ref.year, 1, 1)
        year_next = date(ref.year + 1, 1, 1)

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE stat_date = $3) AS day_count,
                    COUNT(*) FILTER (WHERE stat_date >= $4 AND stat_date < $5) AS month_count,
                    COUNT(*) FILTER (WHERE stat_date >= $6 AND stat_date < $7) AS year_count,
                    COUNT(*) AS total_count,
                    COUNT(*) FILTER (WHERE period_type = 'day') AS period_day_total,
                    COUNT(*) FILTER (WHERE period_type = 'week') AS period_week_total,
                    COUNT(*) FILTER (WHERE period_type = 'month') AS period_month_total,
                    MAX(stat_date) AS last_win_date
                FROM chat_king_daily_results
                WHERE chat_id = $1
                  AND winner_user_id = $2
                """,
                int(chat_id),
                int(user_id),
                ref,
                month_start,
                month_next,
                year_start,
                year_next,
            )

        def _row_value(key: str, default: Any = None) -> Any:
            try:
                if row is None:
                    return default
                return row[key]
            except Exception:
                return default

        last_win_date = _row_value("last_win_date")
        return {
            "reference_date": ref.isoformat(),
            "day_count": int(_row_value("day_count") or 0),
            "month_count": int(_row_value("month_count") or 0),
            "year_count": int(_row_value("year_count") or 0),
            "total_count": int(_row_value("total_count") or 0),
            "period_day_total": int(_row_value("period_day_total") or 0),
            "period_week_total": int(_row_value("period_week_total") or 0),
            "period_month_total": int(_row_value("period_month_total") or 0),
            "last_win_date": last_win_date.isoformat() if last_win_date else "",
        }

    async def increment_user_day_king_win(self, user_id: int, stat_date: date, chat_id: int) -> dict[str, Any]:
        await self.ensure_king_stats_schema()
        month_key = stat_date.strftime("%Y-%m")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT king_stats FROM users WHERE user_id = $1 FOR UPDATE",
                    int(user_id),
                )
                if not row:
                    return {
                        "ok": False,
                        "reason": "user_not_found",
                    }

                stats = self._parse_json_obj(row["king_stats"])
                if str(stats.get("day_king_month_key") or "") != month_key:
                    stats["day_king_month_key"] = month_key
                    stats["day_king_month_count"] = 0

                stats["day_king_total_count"] = int(stats.get("day_king_total_count") or 0) + 1
                stats["day_king_month_count"] = int(stats.get("day_king_month_count") or 0) + 1
                stats["last_day_king_date"] = stat_date.isoformat()
                stats["last_day_king_chat_id"] = int(chat_id)

                await conn.execute(
                    "UPDATE users SET king_stats = $2::jsonb WHERE user_id = $1",
                    int(user_id),
                    json.dumps(stats, ensure_ascii=False),
                )

        return {"ok": True, "stats": stats}

    async def award_chat_king_reward(
            self,
            chat_id: int,
            stat_date: date,
            user_id: int,
            place: int,
            reward_payload: Any,
            details_extra: dict[str, Any] | None = None,
            *,
            period_type: str = "day",
            period_key: str | None = None,
    ) -> dict[str, Any]:
        await self.ensure_king_stats_schema()
        reward = self._normalize_king_reward_payload(reward_payload)
        kut = int(reward.get("kut") or 0)
        items = reward.get("items") or []
        if kut <= 0 and not items:
            return {"ok": True, "skipped": True, "reason": "empty_reward"}

        place_i = int(place)
        chat_i = int(chat_id)
        user_i = int(user_id)
        period_type_s = str(period_type or "day").strip().lower() or "day"
        period_key_s = str(period_key or stat_date.isoformat()).strip() or stat_date.isoformat()

        log_id: int | None = None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT id, delivered
                    FROM chat_king_reward_log
                    WHERE chat_id = $1
                      AND period_type = $2
                      AND period_key = $3
                      AND user_id = $4
                      AND place = $5
                    FOR UPDATE
                    """,
                    chat_i,
                    period_type_s,
                    period_key_s,
                    user_i,
                    place_i,
                )

                if row and bool(row["delivered"]):
                    return {"ok": True, "already_delivered": True, "log_id": int(row["id"])}

                if not row:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO chat_king_reward_log (
                            chat_id,
                            stat_date,
                            period_type,
                            period_key,
                            user_id,
                            place,
                            kut_awarded,
                            items_awarded_json,
                            delivered
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, FALSE)
                        ON CONFLICT (chat_id, period_type, period_key, user_id, place) DO UPDATE
                        SET kut_awarded = EXCLUDED.kut_awarded,
                            items_awarded_json = EXCLUDED.items_awarded_json
                        RETURNING id, delivered
                        """,
                        chat_i,
                        stat_date,
                        period_type_s,
                        period_key_s,
                        user_i,
                        place_i,
                        kut,
                        json.dumps(items, ensure_ascii=False),
                    )

                log_id = int(row["id"])
                if bool(row["delivered"]):
                    return {"ok": True, "already_delivered": True, "log_id": log_id}

        details: dict[str, Any] = {"kut": kut, "items": [], "balance_after": None}
        if isinstance(details_extra, dict) and details_extra:
            details["meta"] = details_extra
        try:
            if kut > 0:
                details["balance_after"] = await self.update_user_balance(user_i, f"+{kut}")

            for item in items:
                item_id = str(item.get("item_id") or "").strip()
                amount = int(item.get("amount") or 0)
                if not item_id or amount <= 0:
                    continue
                resolved_name = item_id
                try:
                    resolved_item = await self.resolve_dex_item_token(item_id)
                    if resolved_item and str(resolved_item.get("name") or "").strip():
                        resolved_name = str(resolved_item.get("name")).strip()
                except Exception:
                    pass

                await self.set_items(user_i, resolved_name, amount)
                details_item = {"item_id": resolved_name, "amount": amount}
                if resolved_name != item_id:
                    details_item["source_token"] = item_id
                details["items"].append(details_item)

            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE chat_king_reward_log
                    SET delivered = TRUE,
                        delivered_at = NOW(),
                        details_json = $2::jsonb,
                        error_text = NULL
                    WHERE id = $1
                    """,
                    int(log_id or 0),
                    json.dumps(details, ensure_ascii=False),
                )
            return {
                "ok": True,
                "delivered": True,
                "log_id": int(log_id or 0),
                "details": details,
            }
        except Exception as e:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE chat_king_reward_log
                    SET delivered = FALSE,
                        details_json = $2::jsonb,
                        error_text = $3
                    WHERE id = $1
                    """,
                    int(log_id or 0),
                    json.dumps(details, ensure_ascii=False),
                    str(e),
                )
            return {
                "ok": False,
                "delivered": False,
                "log_id": int(log_id or 0),
                "error": str(e),
                "details": details,
            }










    # -------------------------------
    # Пул как в старом db.py: if self.pool → ok, иначе connect()
    # -------------------------------
    async def ensure_pool(self) -> bool:
        if self.pool:
            return True
        try:
            await self.connect()
            return self.pool is not None
        except Exception:
            return False

    @asynccontextmanager
    async def acquire(self):
        if not self.pool:
            await self.connect()
        if not self.pool:
            raise RuntimeError("Пул соединений не инициализирован (acquire).")
        con = await self.pool.acquire()
        try:
            yield con
        finally:
            await self.pool.release(con)

    # ============================================================
    # ✅ Нормализация
    # ============================================================
    def _norm_name(self, v: Any) -> Optional[str]:
        try:
            s = str(v).strip()
            return s if s else None
        except Exception:
            return None

    def _norm_username(self, v: Any) -> Optional[str]:
        try:
            s = str(v).strip()
            if not s:
                return None
            s = s.lstrip("@").strip()
            return s if s else None
        except Exception:
            return None

    # ============================================================
    # ✅ DB: creator_id из таблицы chat
    # ============================================================

    async def set_canwithdrawal(self , user_id: int , amount: int):
        """
        Устанавливает значение canwithdrawal для пользователя по user_id.
        """
        try:
            async with self.pool.acquire() as connection:
                # Обновляем значение canwithdrawal
                await connection.execute(
                    """
                    UPDATE users
                    SET canwithdrawal = $1
                    WHERE user_id = $2
                    """ , amount , user_id)

                return True

        except Exception as e:
            print(f"Ошибка при обновлении canwithdrawal: {e}")
            return False

    async def get_canwithdrawal(self , user_id: int):
        """
        Возвращает лимит вывода (canwithdrawal) для пользователя.
        """
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT canwithdrawal FROM users WHERE user_id = $1" , user_id)

                if result and result [ "canwithdrawal" ] is not None:
                    return result [ "canwithdrawal" ]
                else:
                    # если пользователя нет или лимит не установлен
                    return 0

        except Exception as e:
            print(f"Ошибка при получении canwithdrawal: {e}")
            return 0










    async def get_creator_id(self, chat_id):
        """Получает идентификатор создателя группы по идентификатору чата."""
        try:
            async with self.acquire() as connection:
                creator_id = await connection.fetchval(
                    "SELECT creator_id FROM chat WHERE chat_id = $1", int(chat_id)
                )
            self._jc("DB:GET_CREATOR", f"chat_id={chat_id} -> creator_id(DB)={creator_id}")
            return creator_id
        except Exception as e:
            print(f"❌ Ошибка при получении идентификатора создателя: {e}")
            self._jc("DB:GET_CREATOR", f"exception {type(e).__name__}: {e}")
            return None

    # ============================================================
    # ✅ TG: Получить creator_id (истина) - УЛУЧШЕНО
    # - private chat -> None
    # - RetryAfter -> уважить, но без долгих подвисаний
    # - BadRequest/Forbidden -> None
    # ============================================================
    async def _tg_get_chat_creator_id(self , bot1 , chat_id: int) -> Optional [ int ]:
        chat_id_int = int(chat_id)

        # ✅ лички не трогаем
        if chat_id_int > 0:
            self._jc("TG:CREATOR" , f"SKIP private chat_id={chat_id_int}")
            return None

        self._jc("TG:CREATOR" , f"request get_chat_administrators chat_id={chat_id_int}")
        try:
            admins = await bot1.get_chat_administrators(chat_id_int)

            try:
                cnt = len(admins) if admins is not None else 0
            except Exception:
                cnt = -1
            self._jc("TG:CREATOR" , f"admins count={cnt} chat_id={chat_id_int}")

            for adm in (admins or [ ]):
                st = getattr(adm , "status" , None)
                user_obj = getattr(adm , "user" , None)
                uid = getattr(user_obj , "id" , None) if user_obj else None

                self._jc("TG:CREATOR:SCAN" , f"status={st} uid={uid}")

                if st == "creator" and uid:
                    self._jc("TG:CREATOR" , f"FOUND creator_id={int(uid)} chat_id={chat_id_int}")
                    return int(uid)

            self._jc("TG:CREATOR" , f"NOT FOUND creator in admins chat_id={chat_id_int}")
            return None

        except TelegramAPIError as e:
            # ✅ универсальная обработка под любые версии aiogram
            ename = type(e).__name__
            emsg = str(e)

            low = emsg.lower()

            # RetryAfter (rate-limit)
            if ("retry after" in low) or ("too many requests" in low) or ("flood" in low):
                # ⚠️ очень аккуратно: максимум 3 секунды
                sleep_s = 1.0
                # попытка вытащить retry_after если вдруг поле есть
                try:
                    ra = float(getattr(e , "retry_after" , 1.0) or 1.0)
                    sleep_s = min(3.0 , max(0.2 , ra))
                except Exception:
                    sleep_s = 1.0

                self._jc(
                    "TG:CREATOR:ERR" , f"RATE_LIMIT chat_id={chat_id_int} ename={ename} sleep={sleep_s} msg={emsg!r}")
                await asyncio.sleep(sleep_s)
                return None

            # Forbidden / no rights
            if ("forbidden" in low) or ("not enough rights" in low) or ("bot was kicked" in low) or (
                    "not a member" in low):
                self._jc("TG:CREATOR:ERR" , f"FORBIDDEN chat_id={chat_id_int} ename={ename} msg={emsg!r}")
                return None

            # chat not found / invalid
            if ("chat not found" in low) or ("bad request" in low) or ("wrong chat id" in low):
                self._jc("TG:CREATOR:ERR" , f"BAD_REQUEST chat_id={chat_id_int} ename={ename} msg={emsg!r}")
                return None

            # остальное
            self._jc("TG:CREATOR:ERR" , f"TelegramAPIError chat_id={chat_id_int} ename={ename} msg={emsg!r}")
            return None

        except Exception as e:
            self._jc("TG:CREATOR:ERR" , f"unexpected chat_id={chat_id_int} {type(e).__name__}: {e}")
            return None

    # ============================================================
    # ✅ Быстрый UPDATE только если изменилось (ключевой ускоритель)
    # ============================================================
    async def _update_chat_creator_if_changed(
        self,
        chat_id: int,
        creator_id: Optional[int],
        creator_name: Optional[str],
        creator_username: Optional[str],
    ) -> bool:
        if not await self.ensure_pool():
            self._jc("DB:UPDATE", "pool not ready -> return False")
            return False

        chat_id_int = int(chat_id)
        cid = int(creator_id) if creator_id else None
        cname = self._norm_name(creator_name)
        cuser = self._norm_username(creator_username)

        self._jc("DB:UPDATE", f"prepare chat_id={chat_id_int} cid={cid} name={cname!r} username={cuser!r}")

        try:
            async with self.acquire() as connection:
                row = await connection.fetchrow(
                    """
                    UPDATE chat
                       SET creator_id = $2,
                           creator_name = $3,
                           creator_username = $4
                     WHERE chat_id = $1
                       AND (
                            creator_id IS DISTINCT FROM $2
                         OR creator_name IS DISTINCT FROM $3
                         OR creator_username IS DISTINCT FROM $4
                       )
                    RETURNING chat_id
                    """,
                    chat_id_int, cid, cname, cuser
                )

            if row:
                print(f"✅ [CHAT][CREATOR][UPDATED] chat_id={chat_id_int} -> creator_id={cid}")
                self._jc("DB:UPDATE", "UPDATED row returned")
                return True

            self._jc("DB:UPDATE", "NOOP (already actual or no row)")
            return False

        except Exception as e:
            print(f"❌ [CHAT][CREATOR][DB] Ошибка UPDATE chat_id={chat_id_int}: {type(e).__name__}: {e}")
            self._jc("DB:UPDATE:ERR", f"{type(e).__name__}: {e}")
            return False

    # ============================================================
    # ✅ Твой метод (принцип сохранён)
    # ============================================================
    async def update_chat_creator_if_owner(self, bot1, user_id: int, chat_id: int) -> bool:
        """
        1) Узнаём владельца в TG
        2) Если user_id == creator_id -> обновляем chat.creator_*
        3) Иначе - ничего
        """
        if not await self.ensure_pool():
            self._jc("OWNER:FLOW", "pool not ready -> False")
            print("❌ [CHAT][CREATOR][DB] self.pool не инициализирован")
            return False

        try:
            chat_id_int = int(chat_id)
            user_id_int = int(user_id)
        except Exception as e:
            self._jc("OWNER:FLOW:ERR", f"bad args user_id={user_id!r} chat_id={chat_id!r} err={e}")
            print(f"❌ [CHAT][CREATOR][ARGS] Неверные аргументы: user_id={user_id!r} chat_id={chat_id!r} | {type(e).__name__}: {e}")
            return False

        # ✅ личка не интересует
        if chat_id_int > 0:
            self._jc("OWNER:FLOW", f"SKIP private chat_id={chat_id_int}")
            return False

        self._jc("OWNER:FLOW", f"START user_id={user_id_int} chat_id={chat_id_int}")
        print(f"🧾 [CHAT][CREATOR][START] user_id={user_id_int} chat_id={chat_id_int}")

        creator_id = await self._tg_get_chat_creator_id(bot1, chat_id_int)
        if not creator_id:
            self._jc("OWNER:FLOW", f"TG returned creator_id=None chat_id={chat_id_int}")
            print(f"🟨 [CHAT][CREATOR] Владелец не найден в TG или нет доступа | chat_id={chat_id_int}")
            return False

        creator_id = int(creator_id)
        self._jc("OWNER:FLOW", f"TG creator_id={creator_id} chat_id={chat_id_int}")
        print(f"👑 [CHAT][CREATOR][TG] creator_id={creator_id} chat_id={chat_id_int}")

        if user_id_int != creator_id:
            self._jc("OWNER:FLOW", f"SKIP not owner user_id={user_id_int} creator_id={creator_id}")
            print(f"⛔ [CHAT][CREATOR][SKIP] user_id != creator_id | user_id={user_id_int} creator_id={creator_id}")
            return False

        first_name = None
        username = None

        try:
            first_name = await self.get_firstname_by_user_id(creator_id)
            self._jc("OWNER:FLOW", f"get_firstname_by_user_id({creator_id}) -> {first_name!r}")
        except Exception as e:
            self._jc("OWNER:FLOW:ERR", f"get_firstname_by_user_id({creator_id}) {type(e).__name__}: {e}")
            print(f"🟨 [CHAT][CREATOR][NAME] Ошибка get_firstname_by_user_id({creator_id}): {type(e).__name__}: {e}")

        try:
            username = await self.get_username_by_user_id(creator_id)
            self._jc("OWNER:FLOW", f"get_username_by_user_id({creator_id}) -> {username!r}")
        except Exception as e:
            self._jc("OWNER:FLOW:ERR", f"get_username_by_user_id({creator_id}) {type(e).__name__}: {e}")
            print(f"🟨 [CHAT][CREATOR][USERNAME] Ошибка get_username_by_user_id({creator_id}): {type(e).__name__}: {e}")

        creator_name = self._norm_name(first_name)
        creator_username = self._norm_username(username)

        self._jc("OWNER:FLOW", f"DATA name={creator_name!r} username={creator_username!r}")
        print(f"🧾 [CHAT][CREATOR][DATA] creator_id={creator_id} name={creator_name!r} username={creator_username!r}")

        return await self._update_chat_creator_if_changed(
            chat_id=chat_id_int,
            creator_id=creator_id,
            creator_name=creator_name,
            creator_username=creator_username,
        )

    # ======================================================================
    # ✅ JACKCHAT - публичные методы (подключение в боте)
    # ======================================================================

    def _jackchat_now(self) -> float:
        # monotonic лучше для таймеров
        return time.monotonic()

    def _jackchat_get_lock(self, chat_id: int) -> asyncio.Lock:
        self._lazy_init_runtime_fields()
        cid = int(chat_id)
        lk = self._jackchat_locks.get(cid)
        if lk is None:
            lk = asyncio.Lock()
            self._jackchat_locks[cid] = lk
            self._jc("LOCK", f"create lock chat_id={cid}")
        return lk

    def _jackchat_get_or_create_state(self, chat_id: int) -> Dict[str, Any]:
        self._lazy_init_runtime_fields()
        cid = int(chat_id)

        st = self._jackchat_state.get(cid)
        if st is None:
            now = self._jackchat_now()
            st = {
                "chat_id": cid,
                "last_activity_ts": now,
                "last_seen_ts": now,
                "next_check_ts": now,       # сразу можно проверить
                "fails": 0,
                "last_ok_ts": 0.0,
                "last_creator_id": None,

                # ✅ новый ключ: чтобы не дергать TG чаще минимума
                "last_tg_ts": 0.0,
            }
            self._jackchat_state[cid] = st
            self._jc("STATE", f"create state chat_id={cid} -> {st}")
        return st

    async def jackchat_mark_activity(self, chat_id: int) -> None:
        """
        ❗ Вызывай на каждое сообщение в чате.
        JackChat НЕ трекает лички (chat_id > 0).
        """
        self._lazy_init_runtime_fields()

        chat_id_int = int(chat_id)

        if chat_id_int > 0:
            self._jc("ACTIVITY:SKIP", f"private chat detected -> skip chat_id={chat_id_int}")
            return

        st = self._jackchat_get_or_create_state(chat_id_int)
        now = self._jackchat_now()

        old_next = float(st.get("next_check_ts") or 0.0)

        st["last_activity_ts"] = now
        st["last_seen_ts"] = now

        # ✅ ускоряем проверку, но не в ноль, чтобы не дергать TG каждую букву
        soon = now + float(self.JACKCHAT_ACTIVITY_SOON_DELAY)
        if old_next <= 0.0 or soon < old_next:
            st["next_check_ts"] = soon

        self._jc(
            "ACTIVITY",
            f"chat_id={chat_id_int} last_activity_ts={now:.3f} next_check_ts: {old_next:.3f} -> {float(st.get('next_check_ts') or 0.0):.3f}"
        )

    def jackchat_start(self, bot1) -> None:
        """
        Запуск фонового цикла JackChat.
        """
        self._lazy_init_runtime_fields()

        if self._jackchat_task and not self._jackchat_task.done():
            self._jc("START", "already running -> skip")
            _vdbg("🟨 [ДЖЕКЧАТ] уже запущен")
            return

        self._jackchat_stop = False
        self._jackchat_task = asyncio.create_task(self._jackchat_loop(bot1))
        self._jc("START", "task created")
        _vdbg("✅ [ДЖЕКЧАТ][START] система запущена")

    async def jackchat_stop(self) -> None:
        """
        Остановка JackChat.
        """
        self._lazy_init_runtime_fields()
        self._jackchat_stop = True

        t = self._jackchat_task
        if t and not t.done():
            self._jc("STOP", "cancel task")
            t.cancel()
            try:
                await t
            except Exception:
                pass

        self._jackchat_task = None
        self._jc("STOP", "stopped")
        _vdbg("🛑 [ДЖЕКЧАТ][STOP] система остановлена")

    # ======================================================================
    # ✅ JACKCHAT - внутренние helpers
    # ======================================================================

    def _jackchat_pick_due(self, now: float, limit: int) -> List[int]:
        due: List[int] = []
        try:
            for chat_id, st in self._jackchat_state.items():
                n = float(st.get("next_check_ts") or 0.0)
                if n <= now:
                    due.append(int(chat_id))
            due.sort(key=lambda cid: float((self._jackchat_state.get(cid) or {}).get("next_check_ts") or 0.0))
            return due[:max(0, int(limit))]
        except Exception:
            return []

    def _jackchat_schedule_next(self, st: Dict[str, Any], now: float) -> None:
        try:
            last_act = float(st.get("last_activity_ts") or 0.0)
            active = (now - last_act) <= (float(self.JACKCHAT_ACTIVE_INTERVAL) * 2.0)
            interval = float(self.JACKCHAT_ACTIVE_INTERVAL) if active else float(self.JACKCHAT_IDLE_INTERVAL)

            old = float(st.get("next_check_ts") or 0.0)
            st["next_check_ts"] = now + interval
            self._jc("SCHEDULE", f"chat_id={st.get('chat_id')} active={active} interval={interval} next: {old:.3f}->{st['next_check_ts']:.3f}")
        except Exception as e:
            st["next_check_ts"] = now + float(self.JACKCHAT_IDLE_INTERVAL)
            self._jc("SCHEDULE:ERR", f"{type(e).__name__}: {e}")

    def _jackchat_apply_fail(self, st: Dict[str, Any], now: float, reason: str) -> None:
        fails = int(st.get("fails") or 0) + 1
        st["fails"] = fails

        backoff = float(self.JACKCHAT_FAIL_MIN) * (2 ** max(0, fails - 1))
        backoff = min(float(self.JACKCHAT_FAIL_MAX), backoff)

        old = float(st.get("next_check_ts") or 0.0)
        st["next_check_ts"] = now + backoff

        self._jc("FAIL", f"chat_id={st.get('chat_id')} fails={fails} reason={reason} backoff={backoff:.1f}s next: {old:.3f}->{st['next_check_ts']:.3f}")
        _vdbg(f"🟨 [ДЖЕКЧАТ][FAIL] chat_id={st.get('chat_id')} fails={fails} backoff={backoff:.1f}s reason={reason}")

    def _jackchat_cleanup(self, now: float) -> None:
        # 1) забываем чаты без сообщений давно
        try:
            ttl = float(self.JACKCHAT_STATE_TTL)
            drop = []
            for chat_id, st in list(self._jackchat_state.items()):
                last_seen = float(st.get("last_seen_ts") or 0.0)
                if (now - last_seen) > ttl:
                    drop.append(int(chat_id))

            for cid in drop:
                self._jc("GC", f"drop state chat_id={cid}")
                self._jackchat_state.pop(cid, None)
                self._jackchat_locks.pop(cid, None)
                _vdbg(f"🧹 [ДЖЕКЧАТ][GC] забыли чат chat_id={cid} (долго не видели)")

        except Exception as e:
            self._jc("GC:ERR", f"{type(e).__name__}: {e}")

        # 2) чистим кеш user public info
        try:
            ttl_u = float(self.JACKCHAT_USER_TTL) * 5.0
            dropu = []
            for uid, ent in list(self._jackchat_user_cache.items()):
                ts = float(ent.get("ts") or 0.0)
                if (now - ts) > ttl_u:
                    dropu.append(int(uid))
            for uid in dropu:
                self._jc("GC", f"drop user_cache uid={uid}")
                self._jackchat_user_cache.pop(uid, None)
        except Exception as e:
            self._jc("GC:USER_ERR", f"{type(e).__name__}: {e}")

    async def _jackchat_get_user_public(self, user_id: int) -> Dict[str, Any]:
        uid = int(user_id)
        now = self._jackchat_now()

        ent = self._jackchat_user_cache.get(uid)
        if ent:
            ts = float(ent.get("ts") or 0.0)
            if (now - ts) <= float(self.JACKCHAT_USER_TTL):
                self._jc("USER:CACHE", f"HIT uid={uid} name={ent.get('name')!r} username={ent.get('username')!r} age={(now - ts):.2f}s")
                return ent

        self._jc("USER:CACHE", f"MISS uid={uid} -> запрос к users методам")

        name = None
        username = None

        try:
            name = await self.get_firstname_by_user_id(uid)
            self._jc("USER:GET", f"get_firstname_by_user_id({uid}) -> {name!r}")
        except Exception as e:
            self._jc("USER:GET:ERR", f"firstname uid={uid} {type(e).__name__}: {e}")

        try:
            username = await self.get_username_by_user_id(uid)
            self._jc("USER:GET", f"get_username_by_user_id({uid}) -> {username!r}")
        except Exception as e:
            self._jc("USER:GET:ERR", f"username uid={uid} {type(e).__name__}: {e}")

        ent2 = {
            "name": self._norm_name(name),
            "username": self._norm_username(username),
            "ts": now
        }
        self._jackchat_user_cache[uid] = ent2
        self._jc("USER:CACHE", f"STORE uid={uid} -> {ent2}")
        return ent2

    async def _jackchat_check_one(self, bot1, chat_id: int) -> None:
        chat_id_int = int(chat_id)

        # ✅ защита: лички не проверяем
        if chat_id_int > 0:
            self._jc("CHECK:SKIP", f"private chat -> skip check_one chat_id={chat_id_int}")
            return

        st = self._jackchat_get_or_create_state(chat_id_int)
        lk = self._jackchat_get_lock(chat_id_int)

        self._jc("CHECK", f"ENTER chat_id={chat_id_int} state={st}")

        async with lk:
            now = self._jackchat_now()
            self._jc("CHECK", f"LOCKED chat_id={chat_id_int} now={now:.3f}")

            # ✅ анти-спам TG: если недавно уже дернули TG по этому чату - скипаем
            last_tg_ts = float(st.get("last_tg_ts") or 0.0)
            min_dt = float(self.JACKCHAT_TG_MIN_INTERVAL)
            if (now - last_tg_ts) < min_dt:
                # переносим next_check чуть вперед (чтобы не лупить)
                old = float(st.get("next_check_ts") or 0.0)
                st["next_check_ts"] = now + (min_dt - (now - last_tg_ts))
                self._jc("CHECK:TG", f"SKIP tg cooldown chat_id={chat_id_int} dt={(now-last_tg_ts):.3f}s min={min_dt} next: {old:.3f}->{st['next_check_ts']:.3f}")
                return

            # 1) Истина из TG
            creator_id = None
            try:
                st["last_tg_ts"] = now
                creator_id = await self._tg_get_chat_creator_id(bot1, chat_id_int)
                self._jc("CHECK:TG", f"tg_creator_id={creator_id} chat_id={chat_id_int}")

                if not creator_id:
                    self._jackchat_apply_fail(st, now, "no_creator_or_no_access")
                    return

                creator_id = int(creator_id)
                st["last_ok_ts"] = now
                st["fails"] = 0

            except Exception as e:
                self._jc("CHECK:TG:ERR", f"{type(e).__name__}: {e}")
                self._jackchat_apply_fail(st, now, f"tg_error:{type(e).__name__}")
                return

            # 2) следующий чек
            self._jackchat_schedule_next(st, now)

            # 3) сравнение с прошлым
            prev = st.get("last_creator_id")
            changed = (prev != creator_id)
            st["last_creator_id"] = creator_id

            self._jc("CHECK:COMPARE", f"prev_creator_id={prev} new_creator_id={creator_id} changed={changed}")

            if changed:
                _vdbg(f"👑 [ДЖЕКЧАТ][CHANGED] chat_id={chat_id_int} prev={prev} now={creator_id}")
            else:
                _vdbg(f"⚡ [ДЖЕКЧАТ][OK] chat_id={chat_id_int} creator_id={creator_id}")

            # 4) имя/юзер владельца (кеш)
            u = await self._jackchat_get_user_public(creator_id)
            self._jc("CHECK:USER", f"user_public={u}")

            # 5) обновляем БД только если изменилось
            updated = await self._update_chat_creator_if_changed(
                chat_id=chat_id_int,
                creator_id=creator_id,
                creator_name=u.get("name"),
                creator_username=u.get("username"),
            )
            self._jc("CHECK:DB", f"db_updated={updated}")

            self._jc("CHECK", f"EXIT chat_id={chat_id_int}")

    async def _jackchat_loop(self, bot1) -> None:
        self._lazy_init_runtime_fields()
        self._jc("LOOP", "START loop")

        try:
            while not self._jackchat_stop:
                now = self._jackchat_now()

                if bool(self.JACKCHAT_LOG_EVERY_TICK):
                    self._jc("TICK", f"tick now={now:.3f} state_size={len(self._jackchat_state)}")

                # самочистка
                self._jackchat_cleanup(now)

                # чаты, которые пора проверять
                due = self._jackchat_pick_due(now, limit=int(self.JACKCHAT_MAX_PER_TICK))
                self._jc("LOOP", f"due_chats={due}")

                if not due:
                    await asyncio.sleep(float(self.JACKCHAT_TICK))
                    continue

                # последовательно - не устраиваем шторм TG
                for chat_id in due:
                    try:
                        await self._jackchat_check_one(bot1, chat_id)
                    except Exception as e:
                        self._jc("LOOP:ERR", f"check_one chat_id={chat_id} {type(e).__name__}: {e}")
                        _vdbg(f"❌ [ДЖЕКЧАТ][CHECK_ONE][ERROR] chat_id={chat_id} {type(e).__name__}: {e}")

                await asyncio.sleep(float(self.JACKCHAT_TICK))

        except asyncio.CancelledError:
            self._jc("LOOP", "CANCELLED")
            return
        except Exception as e:
            self._jc("LOOP:FATAL", f"{type(e).__name__}: {e}")
            _vdbg(f"❌ [ДЖЕКЧАТ][LOOP][FATAL] {type(e).__name__}: {e}")
            return
        finally:
            self._jc("LOOP", "STOP loop")





    # -------------------------------
    # ✅ TTL cache для групп (быстро)
    # -------------------------------
    def _cache_get_group(self, chat_id: int) -> Optional[Dict[str, Any]]:
        self._lazy_init_runtime_fields()

        try:
            chat_id = int(chat_id)
        except Exception:
            return None

        ts = self._group_cache_ts.get(chat_id)
        if not ts:
            return None

        if (time.time() - float(ts)) > float(self.GROUP_CACHE_TTL):
            # протухло
            try:
                self.group_cache.pop(chat_id, None)
            except Exception:
                pass
            try:
                self._group_cache_ts.pop(chat_id, None)
            except Exception:
                pass
            self._r("CACHE", f"⚠️ Кэш группы протух chat_id={chat_id}, удалил запись.")
            return None

        data = self.group_cache.get(chat_id)
        return data if isinstance(data, dict) else None

    def _cache_set_group(self, chat_id: int, data: Dict[str, Any]) -> None:
        self._lazy_init_runtime_fields()

        try:
            chat_id = int(chat_id)
        except Exception:
            return
        if not isinstance(data, dict):
            return

        self.group_cache[chat_id] = data
        self._group_cache_ts[chat_id] = time.time()

    # -------------------------------
    # ✅ DB методы для группы
    # -------------------------------
    async def check_group_exists(self, chat_id: int) -> bool:
        try:
            chat_id = int(chat_id)
        except Exception:
            return False

        try:
            async with self.acquire() as con:
                return bool(await con.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM chat WHERE chat_id=$1)",
                    chat_id
                ))
        except Exception as e:
            self._r("DB:CHAT", f"❌ check_group_exists({chat_id}) ошибка: {e}")
            return False

    async def fetch_group_row(self, chat_id: int):
        try:
            chat_id = int(chat_id)
        except Exception:
            return None

        try:
            async with self.acquire() as con:
                return await con.fetchrow(
                    "SELECT * FROM chat WHERE chat_id=$1 LIMIT 1",
                    chat_id
                )
        except Exception as e:
            self._r("DB:CHAT", f"❌ fetch_group_row({chat_id}) ошибка: {e}")
            return None

    # -------------------------------
    # ✅ ensure_group: cache -> db -> sync -> db -> cache
    # -------------------------------
    async def ensure_group(self, *, bot1, chat_id: int, sync_func):
        """
        Самолечащая гарантия:
        1) cache-hit -> моментально
        2) лок chat_id
        3) db-hit -> cache-set
        4) db-miss -> sync_func(bot1, chat_id, db)
        5) db-hit -> cache-set
        """
        try:
            chat_id = int(chat_id)
        except Exception:
            self._r("GROUP", f"❌ ensure_group: неверный chat_id={chat_id!r}")
            return None

        cached = self._cache_get_group(chat_id)
        if cached:
            self._r("GROUP", f"✅ cache-hit chat_id={chat_id}")
            return cached

        lock = self._get_group_lock(chat_id)
        async with lock:
            cached2 = self._cache_get_group(chat_id)
            if cached2:
                self._r("GROUP", f"✅ cache-hit (после lock) chat_id={chat_id}")
                return cached2

            row = await self.fetch_group_row(chat_id)
            if row:
                data = dict(row)
                self._cache_set_group(chat_id, data)
                self._r("GROUP", f"✅ db-hit chat_id={chat_id} -> закэшировал")
                return data

            self._r("GROUP", f"⚠️ db-miss chat_id={chat_id} -> вызываю sync_func")
            try:
                await sync_func(bot1, chat_id, self)
            except Exception as e:
                self._r("GROUP", f"❌ sync_func упал chat_id={chat_id}: {e}")
                return None

            row2 = await self.fetch_group_row(chat_id)
            if row2:
                data2 = dict(row2)
                self._cache_set_group(chat_id, data2)
                self._r("GROUP", f"✅ ensured chat_id={chat_id} -> закэшировал")
                return data2

            self._r("GROUP", f"🔥 ensure_group: после sync_func строки нет в БД chat_id={chat_id}")
            return None

    async def ensure_mutechat_schema(self) -> None:
        """
        Создаёт таблицу mutechat, если её нет.
        Важно: безопасно вызывать на каждом старте.
        """
        if not self.pool:
            print("[MUTECHAT][ERROR] Пул соединений не инициализирован (ensure_mutechat_schema).")
            return

        try:
            async with self.pool.acquire() as conn:
                # таблица
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mutechat (
                        chat_id      BIGINT PRIMARY KEY,
                        name_chat    TEXT,
                        usernamechat TEXT,
                        data         TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                # индекс (ускоряет list по дате)
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mutechat_data ON mutechat (data DESC);"
                )

            print("[MUTECHAT][OK] ensure_mutechat_schema: таблица готова ✅")
        except Exception as e:
            print(f"[MUTECHAT][ERROR] ensure_mutechat_schema: {e}\n{traceback.format_exc()}")

    async def mute_chat(
        self,
        chat_id: int,
        *,
        name_chat: Optional[str] = None,
        usernamechat: Optional[str] = None
    ) -> bool:
        """
        Добавляет/обновляет чат в mutechat (UPSERT).
        Продумано:
          - нормализуем chat_id
          - чистим строки
          - username приводим к '@name'
          - обновляем data=NOW() при каждом апдейте
        """
        if not self.pool:
            print("[MUTECHAT][ERROR] Пул соединений не инициализирован (mute_chat).")
            return False

        try:
            cid = int(chat_id)
        except Exception:
            print(f"[MUTECHAT][WARN] mute_chat: bad chat_id={chat_id!r}")
            return False

        # нормализуем тексты
        name_chat = _safe_str(name_chat).strip() or None
        usernamechat = _safe_str(usernamechat).strip() or None

        # нормализуем username -> с @
        if usernamechat:
            try:
                if not usernamechat.startswith("@"):
                    usernamechat = "@" + usernamechat
            except Exception:
                usernamechat = None

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO mutechat (chat_id, name_chat, usernamechat, data)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (chat_id) DO UPDATE
                    SET name_chat = EXCLUDED.name_chat,
                        usernamechat = EXCLUDED.usernamechat,
                        data = NOW()
                    """,
                    cid, name_chat, usernamechat
                )

            print(f"[MUTECHAT][OK] mute_chat: chat_id={cid} 🔇")
            return True

        except Exception as e:
            print(f"[MUTECHAT][ERROR] mute_chat({chat_id}): {e}\n{traceback.format_exc()}")
            return False

    async def unmute_chat(self, chat_id: int) -> bool:
        """
        Удаляет чат из mutechat.
        Возвращает True если реально удалили (DELETE 1).
        """
        if not self.pool:
            print("[MUTECHAT][ERROR] Пул соединений не инициализирован (unmute_chat).")
            return False

        try:
            cid = int(chat_id)
        except Exception:
            print(f"[MUTECHAT][WARN] unmute_chat: bad chat_id={chat_id!r}")
            return False

        try:
            async with self.pool.acquire() as conn:
                res = await conn.execute("DELETE FROM mutechat WHERE chat_id = $1", cid)

            # res: "DELETE 0" / "DELETE 1"
            deleted = str(res).strip().endswith("1")
            print(f"[MUTECHAT][OK] unmute_chat: chat_id={cid} deleted={deleted} 🔊")
            return deleted

        except Exception as e:
            print(f"[MUTECHAT][ERROR] unmute_chat({chat_id}): {e}\n{traceback.format_exc()}")
            return False

    async def is_chat_muted(self, chat_id: int) -> bool:
        """
        Проверяет, находится ли чат в mutechat.
        """
        if not self.pool:
            return False

        try:
            cid = int(chat_id)
        except Exception:
            return False

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT chat_id FROM mutechat WHERE chat_id = $1 LIMIT 1",
                    cid
                )
            return bool(row)

        except Exception as e:
            print(f"[MUTECHAT][ERROR] is_chat_muted({chat_id}): {e}")
            return False

    async def list_muted_chats(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Возвращает список замученных чатов (последние сверху).
        """
        if not self.pool:
            print("[MUTECHAT][ERROR] Пул соединений не инициализирован (list_muted_chats).")
            return []

        try:
            lim = int(limit)
            if lim <= 0:
                lim = 200
            lim = min(lim, 500)
        except Exception:
            lim = 200

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT chat_id, name_chat, usernamechat, data
                    FROM mutechat
                    ORDER BY data DESC
                    LIMIT $1
                    """,
                    lim
                )

            out: List[Dict[str, Any]] = []
            for r in rows:
                out.append({
                    "chat_id": r["chat_id"],
                    "name_chat": r["name_chat"],
                    "usernamechat": r["usernamechat"],
                    "data": r["data"],
                })
            return out

        except Exception as e:
            print(f"[MUTECHAT][ERROR] list_muted_chats: {e}\n{traceback.format_exc()}")
            return []












    async def cancel_gc_assignment(self , user_id: int) -> bool:
        """
        Отмена ТЕКУЩЕГО АКТИВНОГО GC-задания пользователя:
          - находим active assignment;
          - меняем статус на 'cancelled';
          - при необходимости освобождаем слот в шаблоне.

        Возвращает True при успехе, False если активного задания нет
        или произошла ошибка.
        """
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Находим активное задание и блокируем строку
                    row = await conn.fetchrow(
                        """
                        SELECT id, template_id
                        FROM z_game_challenge_active_assignments
                        WHERE user_id = $1 AND status = 'active'
                        FOR UPDATE
                        """ , int(user_id) , )
                    if not row:
                        _log_warn(
                            f"cancel_gc_assignment: no active assignment for user {user_id}")
                        return False

                    assignment_id = row [ "id" ]
                    template_id = row [ "template_id" ]

                    # Помечаем задание отменённым
                    await conn.execute(
                        """
                        UPDATE z_game_challenge_active_assignments
                        SET status = 'finish',
                            last_updated_at = NOW()
                        WHERE id = $1
                        """ , int(assignment_id) , )

            # Вне транзакции - освобождаем слот по шаблону (если нужно)
            if template_id:
                await self.decrement_gc_template_completed(int(template_id) , step=1)

            _log_ok(
                f"cancel_gc_assignment: user_id={user_id}, assignment_id={assignment_id}, "
                f"template_id={template_id} -> finish а не '-cancelled-' + slot freed")
            return True

        except Exception as e:
            _log_err(
                f"cancel_gc_assignment({user_id}): {e}\n{traceback.format_exc()}")
            return False

    # ================== FREE-FLAG ДЛЯ GC-ШАБЛОНОВ ==================
    async def get_gc_template_free_flag(self , template_id: int) -> str:
        """
        Возвращает флаг бесплатности шаблона по его ID.

        Читает столбец free из z_game_challenge_templates и
        всегда приводит результат к одному символу:

          '+'  - бесплатное задание;
          '-'  - обычное задание (по умолчанию).

        Если:
          - шаблон не найден,
          - free = NULL,
          - free = '' или пробелы,
          - free содержит что-то отличное от '+',
        то возвращается '-'.

        Ошибки БД логируются, но наружу не выбрасываются.
        """
        try:
            tid = int(template_id)
        except Exception as e:
            _log_warn(
                f"get_gc_template_free_flag: bad template_id={template_id!r}: {e}")
            return "-"

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT free
                    FROM z_game_challenge_templates
                    WHERE id = $1
                    LIMIT 1
                    """ , tid , )

            if not row:
                _log_warn(
                    f"get_gc_template_free_flag: template id={tid} not found, default '-'")
                return "-"

            raw = row.get("free") if isinstance(row , dict) else row [ "free" ]

            if raw is None:
                # NULL трактуем как обычное задание
                return "-"

            s = str(raw).strip()
            if s == "+":
                return "+"
            # всё остальное считаем обычным
            return "-"

        except Exception as e:
            _log_err(
                f"get_gc_template_free_flag({template_id}): {e}\n"
                f"{traceback.format_exc()}")
            # в случае любой ошибки - безопасный дефолт
            return "-"

    async def get_user_donate(self , user_id: int) -> int:
        """
        Возвращает сумму доната пользователя из users.donate по users.user_id.

        Гарантии:
        - всегда возвращает int >= 0
        - если user_id не найден / donate = NULL / donate пустой / мусор -> 0
        - ошибки БД логируются и возвращается 0
        """
        try:
            uid = int(user_id)
        except Exception as e:
            _log_warn(f"get_user_donate: bad user_id={user_id!r}: {e}")
            return 0

        if not self.pool:
            _log_err("get_user_donate: pool is not initialized")
            return 0

        try:
            async with self.pool.acquire() as conn:
                raw = await conn.fetchval(
                    """
                    SELECT donate
                    FROM users
                    WHERE user_id = $1
                    LIMIT 1
                    """ , uid , )

            if raw is None:
                return 0

            # donate может быть int/float/Decimal/str - приводим максимально мягко
            try:
                s = str(raw).strip().replace(" " , "").replace("," , ".")
                if not s:
                    return 0

                # если вдруг хранят типа "100.0" - берём целую часть
                if "." in s:
                    s = s.split("." , 1) [ 0 ]

                if s.startswith("+"):
                    s = s [ 1: ]

                val = int(s) if s.isdigit() else 0
                return val if val > 0 else 0
            except Exception:
                return 0

        except Exception as e:
            _log_err(f"get_user_donate({uid}): {e}\n{traceback.format_exc()}")
            return 0
    async def is_gc_template_free(self , template_id: int) -> bool:
        """
        Удобная обёртка над get_gc_template_free_flag.

        Возвращает:
          True  - если шаблон помечен как бесплатный (free = '+'),
          False - во всех остальных случаях (включая ошибки и отсутствие записи).
        """
        flag = await self.get_gc_template_free_flag(template_id)
        return flag == "+"
    # ----------------- НИЗКОУРОВНЕВАЯ УТИЛИТА -----------------
    async def _row_to_dict(self , row):
        """
        Асинхронно конвертирует asyncpg.Record → dict.
        Если row=None → возвращает None.
        Работает рекурсивно с вложенными Records и списками.
        """
        if row is None:
            return None

        try:
            # Если это asyncpg.Record - берем mapping
            if isinstance(row , asyncpg.Record):
                d = dict(row)
            elif isinstance(row , dict):
                d = dict(row)
            else:
                # fallback: попытка приведения
                try:
                    d = dict(row)
                except Exception:
                    return None

            # рекурсивная обработка вложенных Records/списков/tuple
            for k , v in list(d.items()):
                # Record внутри
                if isinstance(v , asyncpg.Record):
                    d [ k ] = dict(v)
                # mapping-like объект (например JSONB -> dict)
                elif isinstance(v , dict):
                    # оставляем как есть
                    pass
                # список/кортеж с возможными Record'ами
                elif isinstance(v , (list , tuple)):
                    new_list = [ ]
                    for item in v:
                        if isinstance(item , asyncpg.Record):
                            new_list.append(dict(item))
                        else:
                            new_list.append(item)
                    d [ k ] = new_list
            return d
        except Exception as e:
            _log_err(f"[DB_UTIL_ERROR] _row_to_dict failed: {e}\n{traceback.format_exc()}")
            return None

    # ---------------- DB: decrement_gc_template_completed (опционально) ----------------
    async def decrement_gc_template_completed(self , template_id: int , step: int = 1 , ) -> Optional [
        Dict [ str , Any ] ]:
        """
        Уменьшает completed_users у шаблона (освобождаем слот), но не ниже 0.
        Возвращает dict с данными шаблона или None при ошибке/отсутствии шаблона.
        """
        if step <= 0:
            step = 1

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        """
                        SELECT id, completed_users, max_users, status
                        FROM z_game_challenge_templates
                        WHERE id = $1
                        FOR UPDATE
                        """ , int(template_id) , )
                    if not row:
                        _log_warn(f"decrement_gc_template_completed: template {template_id} not found")
                        return None

                    cur = row [ "completed_users" ] or 0
                    newv = max(0 , cur - step)

                    updated = await conn.fetchrow(
                        """
                        UPDATE z_game_challenge_templates
                        SET completed_users = $2
                        WHERE id = $1
                        RETURNING
                            id,
                            start_amount,
                            target_amount,
                            reward_amount,
                            betlimit,
                            max_users,
                            completed_users,
                            target_chat_id,
                            target_chat_ref,
                            free,
                            status,
                            created_at,
                            TO_CHAR(
                                created_at AT TIME ZONE 'Europe/Oslo',
                                'HH24:MI | DD.MM.YYYY'
                            ) AS created_pretty
                        """ , int(template_id) , int(newv) , )

                    _log_ok(
                        f"decrement_gc_template_completed: id={template_id}, "
                        f"{cur} -> {newv}")
                    return await self._row_to_dict(updated) if updated else None

        except Exception as e:
            _log_err(
                f"decrement_gc_template_completed({template_id}): {e}\n"
                f"{traceback.format_exc()}")
            return None

    # ---------------- DB: mark_assignment_failed ----------------
    async def mark_assignment_failed(
        self,
        user_id: int,
        reason: str = "balance_zero",
    ) -> bool:
        """
        Пометить текущее активное задание пользователя как проваленное.

        ВАЖНО:
          - статус = 'failed'
          - НИЧЕГО не удаляем и не трогаем completed_users у шаблона
          - просто фиксируем факт, что пользователь этот шаблон уже проходил
        """
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        """
                        SELECT id, template_id
                        FROM z_game_challenge_active_assignments
                        WHERE user_id = $1
                          AND status = 'active'
                        FOR UPDATE
                        """,
                        int(user_id),
                    )
                    if not row:
                        _log_warn(
                            f"mark_assignment_failed: нет active-задания для user_id={user_id}"
                        )
                        return False

                    assignment_id = int(row["id"])

                    await conn.execute(
                        """
                        UPDATE z_game_challenge_active_assignments
                        SET status = 'failed',
                            last_updated_at = NOW()
                        WHERE id = $1
                        """,
                        assignment_id,
                    )

                    _log_ok(
                        f"mark_assignment_failed: user={user_id} → status=failed (reason={reason})"
                    )
                    return True
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            _log_err(f"mark_assignment_failed({user_id}): {e}\n{tb}")
            return False

    async def has_user_gc_finished_template(self , user_id: int , template_id: int , ) -> bool:
        """
        Проверяем, проходил ли пользователь ЭТОТ шаблон раньше до финального статуса.

        Финальные статусы:
          - 'finish'  - успешно выполнено
          - 'failed'  - провалено

        Если такая запись есть - этот шаблон больше нельзя брать.
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT 1
                    FROM z_game_challenge_active_assignments
                    WHERE user_id   = $1
                      AND template_id = $2
                      AND status IN ('finish', 'failed')
                    LIMIT 1
                    """ , int(user_id) , int(template_id) , )
                return bool(row)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            _log_err(
                f"has_user_gc_finished_template({user_id}, {template_id}): {e}\n{tb}")
            return False

    async def _gc_completion_reward_already_logged(
        self ,
        conn ,
        user_id: int ,
        assignment_id: int ,
    ) -> bool:
        """Проверяет, была ли уже записана награда за конкретное завершённое задание."""
        try:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM user_balance_log AS l
                WHERE l.user_id = $1
                  AND l.note = 'gc_task_reward'
                  AND l.created_at >= COALESCE(
                        (SELECT COALESCE(a.last_updated_at, a.created_at)
                           FROM z_game_challenge_active_assignments AS a
                          WHERE a.id = $2),
                        NOW() - INTERVAL '7 days'
                  )
                LIMIT 1
                """,
                int(user_id),
                int(assignment_id),
            )
            return bool(row)
        except Exception as e:
            _log_warn(
                f"_gc_completion_reward_already_logged(user={user_id}, assign={assignment_id}): {e}"
            )
            return False

    async def _gc_credit_completion_reward_to_main(
        self ,
        user_id: int ,
        reward_amount: int ,
        *,
        assignment_id: Optional[int] = None,
        is_free: bool = False,
    ) -> bool:
        """
        Зачисляет награду за выполнение задания на ОСНОВНОЙ баланс пользователя.
        Работает одинаково для бесплатных и обычных заданий.
        """
        uid = int(user_id)
        reward_int = int(reward_amount or 0)
        if reward_int <= 0:
            return True

        try:
            new_balance = await self.update_user_balance(uid, f"+{reward_int}")
            if new_balance is None:
                _log_err(
                    f"[GC_DB] _gc_credit_completion_reward_to_main: не удалось начислить "
                    f"user={uid} reward={reward_int}"
                )
                return False

            _log_ok(
                f"[GC_DB] _gc_credit_completion_reward_to_main: user={uid} "
                f"+{reward_int} -> main balance={new_balance} "
                f"(free={is_free}, assignment_id={assignment_id})"
            )

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO user_balance_log(user_id, amount, note, created_at)
                        VALUES($1, $2, $3, NOW())
                        """,
                        uid,
                        reward_int,
                        "gc_task_reward",
                    )
            except Exception as e_log:
                _log_warn(
                    f"[GC_DB] _gc_credit_completion_reward_to_main: user_balance_log fail "
                    f"user={uid}: {e_log}"
                )

            history_note = (
                "+ награда за бесплатное задание"
                if is_free
                else "+ награда за задание"
            )
            try:
                await self.cutehistory_plus(uid, reward_int, history_note)
            except Exception as e_hist:
                _log_warn(
                    f"[GC_DB] _gc_credit_completion_reward_to_main: cutehistory fail "
                    f"user={uid}: {e_hist}"
                )

            try:
                await self.touch_balance_last_active(uid, set_active_status=True)
            except Exception:
                pass

            return True
        except Exception as e:
            _log_err(
                f"[GC_DB] _gc_credit_completion_reward_to_main({uid}, {reward_int}): "
                f"{e}\n{traceback.format_exc()}"
            )
            return False

    async def mark_assignment_completed(
        self ,
        user_id: int ,
        reward_amount: int ,
        template_id: Optional [ int ] = None ,
    ) -> bool:
        """
        Пометить активный игровой челлендж как выполненный и выдать награду.

        Награда (reward_amount) ВСЕГДА зачисляется на основной баланс пользователя -
        и для бесплатных (free='+'), и для обычных заданий.

        Логика:
          1) status active → finish (слоты шаблона не трогаем)
          2) +reward_amount на основной баланс, user_balance_log, cutehistory
          3) Идемпотентность: повторный вызов не дублирует награду
          4) Восстановление: если задание уже finish, но награда не записана - доначисляем
        """

        user_id_int = int(user_id)
        reward_int = int(reward_amount or 0)
        is_free = False

        try:
            assignment_id: Optional[int] = None
            need_finish = False

            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        """
                        SELECT a.id, a.template_id, a.status, t.free
                        FROM z_game_challenge_active_assignments AS a
                        LEFT JOIN z_game_challenge_templates AS t
                          ON t.id = a.template_id
                        WHERE a.user_id = $1
                          AND a.status = 'active'
                        FOR UPDATE OF a
                        """,
                        user_id_int,
                    )

                    if row:
                        assignment_id = int(row["id"])
                        is_free = (row.get("free") == "+")
                        need_finish = True
                    else:
                        finished = await conn.fetchrow(
                            """
                            SELECT a.id, t.free
                            FROM z_game_challenge_active_assignments AS a
                            LEFT JOIN z_game_challenge_templates AS t
                              ON t.id = a.template_id
                            WHERE a.user_id = $1
                              AND a.status = 'finish'
                            ORDER BY COALESCE(a.last_updated_at, a.created_at) DESC
                            LIMIT 1
                            """,
                            user_id_int,
                        )
                        if not finished:
                            _log_warn(
                                f"[GC_DB] mark_assignment_completed: нет active/finish "
                                f"для user_id={user_id_int}"
                            )
                            return False

                        assignment_id = int(finished["id"])
                        is_free = (finished.get("free") == "+")

                        if reward_int > 0:
                            already_paid = await self._gc_completion_reward_already_logged(
                                conn, user_id_int, assignment_id
                            )
                            if already_paid:
                                _log_ok(
                                    f"[GC_DB] mark_assignment_completed: user={user_id_int} "
                                    f"assignment={assignment_id} уже получил награду"
                                )
                                return True

                    if need_finish and assignment_id is not None:
                        tpl_id = row.get("template_id") if row else template_id
                        _log_ok(
                            f"[GC_DB] mark_assignment_completed: assignment_id={assignment_id}, "
                            f"tpl_id={tpl_id}, free={is_free}"
                        )
                        await conn.execute(
                            """
                            UPDATE z_game_challenge_active_assignments
                            SET status = 'finish',
                                last_updated_at = NOW()
                            WHERE id = $1
                            """,
                            assignment_id,
                        )
                        _log_ok(
                            f"[GC_DB] mark_assignment_completed: assignment_id={assignment_id} "
                            f"→ status='finish'"
                        )

            if reward_int <= 0:
                _log_ok(
                    f"[GC_DB] mark_assignment_completed: user_id={user_id_int}, reward=0"
                )
                return True

            return await self._gc_credit_completion_reward_to_main(
                user_id_int,
                reward_int,
                assignment_id=assignment_id,
                is_free=is_free,
            )

        except Exception as e:
            try:
                tb = traceback.format_exc()
            except Exception:
                tb = ""
            _log_err(
                f"[GC_DB] mark_assignment_completed({user_id_int}, {reward_int}): {e}\n{tb}"
            )
            return False
    # ---------------- DB: force_remove_assignment_by_user (hard delete) ----------------
    async def force_remove_assignment_by_user(self , user_id: int) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM z_game_challenge_active_assignments WHERE user_id = $1" , int(user_id))
                _log_ok(f"force_remove_assignment_by_user: user={user_id}")
                return True
        except Exception as e:
            _log_err(f"force_remove_assignment_by_user({user_id}): {e}\n{traceback.format_exc()}")
            return False

    # ---------------- DB: get_active_assignment_by_user ----------------
    async def get_active_assignment_by_user(self , user_id: int) -> Optional [ Dict [ str , Any ] ]:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM z_game_challenge_active_assignments WHERE user_id = $1 AND status = 'active' LIMIT 1" ,
                    int(user_id))
                return await self._row_to_dict(row)
        except Exception as e:
            _log_err(f"get_active_assignment_by_user({user_id}): {e}\n{traceback.format_exc()}")
            return None

    # ---------------- DB: create_active_assignment ----------------
    async def create_active_assignment(self , user_id: int , template_id: int , first_name: Optional [ str ] ,
            username: Optional [ str ] , two_balance_initial: int , betlimit: Optional [ int ] ,
            target_amount: int , reward_amount: int , ) -> Optional [ Dict [ str , Any ] ]:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO z_game_challenge_active_assignments
                        (user_id, first_name, username, template_id,
                         two_balance, two_balance_initial, status,
                         progress_json, betlimit, target_amount, reward_amount,
                         created_at, last_updated_at)
                    VALUES
                        ($1,$2,$3,$4,$5,$6,'active','{}'::jsonb,$7,$8,$9,NOW(),NOW())
                    RETURNING *
                    """ , int(user_id) , first_name , username , int(template_id) , int(two_balance_initial) ,
                    int(two_balance_initial) , None if betlimit is None else int(betlimit) ,
                    int(target_amount) , int(reward_amount))
                if row:
                    _log_ok(f"create_active_assignment: user={user_id} template={template_id}")
                return await self._row_to_dict(row)
        except asyncpg.exceptions.UniqueViolationError:
            _log_info(f"create_active_assignment: user {user_id} already has active assignment")
            return None
        except Exception as e:
            _log_err(f"create_active_assignment error: {e}\n{traceback.format_exc()}")
            return None




    async def gc_get_current_two_balance(self , user_id: int) -> Optional [ int ]:
        """
        Возвращает текущий виртуальный баланс (two_balance_initial)
        АКТИВНОГО челленджа пользователя.

        Нет активного задания → None.
        """
        try:
            uid = int(user_id)
        except Exception as e:
            _log_err(
                f"gc_get_current_two_balance(bad_user_id): user_id={user_id!r}: "
                f"{e}\n{traceback.format_exc()}")
            return None

        try:
            async with self.pool.acquire() as conn:
                value = await conn.fetchval(
                    """
                    SELECT a.two_balance_initial
                    FROM z_game_challenge_active_assignments AS a
                    WHERE a.user_id = $1
                      AND a.status  = 'active'
                    LIMIT 1
                    """ , uid , )

            if value is None:
                _log_info(f"gc_get_current_two_balance: no active assignment for user={uid}")
                return None

            current_two = int(value)
            _log_info(
                f"gc_get_current_two_balance: user={uid} -> two_balance_initial={current_two}")
            return current_two

        except Exception as e:
            _log_err(
                f"gc_get_current_two_balance({uid}): {e}\n{traceback.format_exc()}")
            return None
    async def gc_active_is_free(self , user_id: int) -> bool:
        """
        Проверяет, есть ли у пользователя АКТИВНОЕ задание и является ли оно БЕСПЛАТНЫМ.

        Логика:
          - нет активного задания → False
          - есть активное, шаблон free = '+' → True
          - free = '-' или NULL/другое → False
        """
        try:
            uid = int(user_id)
        except Exception as e:
            _log_err(
                f"gc_active_is_free(bad_user_id): user_id={user_id!r}: "
                f"{e}\n{traceback.format_exc()}")
            return False

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT t.free
                    FROM z_game_challenge_active_assignments AS a
                    JOIN z_game_challenge_templates         AS t
                      ON t.id = a.template_id
                    WHERE a.user_id = $1
                      AND a.status  = 'active'
                    LIMIT 1
                    """ , uid , )

            # нет активного задания
            if not row:
                _log_info(f"gc_active_is_free: no active assignment for user={uid}")
                return False

            free_flag = row.get("free")

            if free_flag == "+":
                _log_info(f"gc_active_is_free: user={uid} -> FREE (+)")
                return True

            # обычное задание ( '-', NULL или что-то ещё )
            _log_info(f"gc_active_is_free: user={uid} -> NOT FREE ({free_flag!r})")
            return False

        except Exception as e:
            _log_err(
                f"gc_active_is_free({uid}): {e}\n{traceback.format_exc()}")
            return False
    async def gc_apply_two_balance(self , user_id: int , sign: str , amount: int) -> bool:
        """
        Универсальный апдейтер виртуального баланса задания.

        sign:
            "+" → прибавить amount к текущему two_balance_initial
            "-" → отнять amount от текущего two_balance_initial

        amount:
            положительное число. Функция сама корректно применяет знак.

        Возвращает True/False по результату обновления.
        """

        try:
            user_id = int(user_id)
            amount = int(amount)
            if amount <= 0:
                _log_err(f"gc_apply_two_balance: amount <= 0 ({amount})")
                return False

            sign = (sign or "").strip()
            if sign not in ("+" , "-"):
                _log_err(f"gc_apply_two_balance: bad sign '{sign}'")
                return False

        except Exception as e:
            _log_err(f"gc_apply_two_balance(bad_args): {e}\n{traceback.format_exc()}")
            return False

        # --- читаем текущий виртуальный баланс ---
        try:
            row = await self.get_active_gc_assignment(user_id)
            if not row or row.get("status") != "active":
                _log_info(f"gc_apply_two_balance: no active assignment for {user_id}")
                return False

            current = int(row.get("two_balance_initial") or 0)
        except Exception as e:
            _log_err(
                f"gc_apply_two_balance(get_balance_err): {user_id}, {e}\n{traceback.format_exc()}")
            return False

        # --- считаем новый баланс ---
        if sign == "+":
            new_balance = current + amount
        else:  # "-"
            new_balance = max(0 , current - amount)

        # --- применяем ---
        ok = await self.update_active_assignment_two_balance(user_id , new_balance)
        if ok:
            _log_info(
                f"gc_apply_two_balance: user={user_id}, {current} {sign} {amount} -> {new_balance}")
        else:
            _log_err(
                f"gc_apply_two_balance: update failed user={user_id}, target={new_balance}")

        return ok


    async def update_active_assignment_two_balance(self , user_id: int , new_two_balance: int) -> bool:
        """
        Обновляет ТЕКУЩИЙ виртуальный баланс игрового задания пользователя.

        ВАЖНО:
          - two_balance остаётся стартовой суммой;
          - two_balance_initial - текущий виртуальный баланс, его и обновляем.
        """
        try:
            async with self.pool.acquire() as conn:
                res = await conn.execute(
                    """
                    UPDATE z_game_challenge_active_assignments
                    SET
                        two_balance_initial = $1,
                        last_updated_at    = NOW()
                    WHERE user_id = $2
                      AND status  = 'active'
                    """ , int(new_two_balance) , int(user_id) , )
                _log_info(
                    f"update_active_assignment_two_balance(current): "
                    f"user={user_id} -> {new_two_balance} ({res})")
                return True
        except Exception as e:
            _log_err(
                f"update_active_assignment_two_balance({user_id}, {new_two_balance}): "
                f"{e}\n{traceback.format_exc()}")
            return False

    # --- Твои новые функции ---
    async def get_group_name(self , chat_id: int) -> Optional [ str ]:
        """
        Возвращает namechat (название группы) из таблицы chat по chat_id
        или None если не найдено.
        """
        # предполагается, что у тебя есть self.init() где-то вне этого фрагмента, поэтому не создаю его
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT namechat FROM chat WHERE chat_id = $1 LIMIT 1" , chat_id)
            return row [ "namechat" ] if row and row [ "namechat" ] is not None else None

    async def get_group_username(self , chat_id: int) -> Optional [ str ]:
        """
        Возвращает usernamechat (username группы, без @) по chat_id
        или None если не найдено.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT usernamechat FROM chat WHERE chat_id = $1 LIMIT 1" , chat_id)
            if row and row [ "usernamechat" ]:
                uname = row [ "usernamechat" ]
                return uname [ 1: ] if isinstance(uname , str) and uname.startswith("@") else uname
            return None

    async def remove_assignment_by_user(
        self,
        user_id: int,
        restore_slot: bool = True,
    ) -> bool:
        """
        Снимает ТЕКУЩЕЕ АКТИВНОЕ GC-задание пользователя.

        Если restore_slot=True - освобождает слот в шаблоне
        (уменьшает completed_users у соответствующего template_id).

        Делает только одно: ставит статус задания в 'switched'.

        Возвращает True, если активное задание было и мы его сняли,
        иначе False.
        """
        try:
            template_id = None

            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Лочим текущую активную запись пользователя
                    row = await conn.fetchrow(
                        """
                        SELECT id, template_id
                        FROM z_game_challenge_active_assignments
                        WHERE user_id = $1 AND status = 'active'
                        FOR UPDATE
                        """,
                        int(user_id),
                    )

                    if not row:
                        _log_warn(
                            f"remove_assignment_by_user: no active assignment for user {user_id}"
                        )
                        return False

                    assignment_id = row["id"]
                    template_id = row["template_id"]

                    # Просто меняем статус на 'switched', без finished_at
                    await conn.execute(
                        """
                        UPDATE z_game_challenge_active_assignments
                        SET status = 'switched'
                        WHERE id = $1
                        """,
                        int(assignment_id),
                    )

            # Освобождаем слот в шаблоне, если нужно
            if restore_slot and template_id:
                await self.decrement_gc_template_completed(int(template_id), step=1)

            _log_ok(
                f"remove_assignment_by_user: user_id={user_id}, "
                f"template_id={template_id}, restore_slot={restore_slot}"
            )
            return True

        except Exception as e:
            _log_err(
                f"remove_assignment_by_user({user_id}, restore_slot={restore_slot}): "
                f"{e}\n{traceback.format_exc()}"
            )
            return False

    async def gc_get_bet_limit_for_user(self , user_id: int) -> Optional [ int ]:
        """
        Возвращает лимит ставки из активного челленджа пользователя.

        Логика:
          - если нет активного задания → None (использовать общий лимит 1000);
          - если betlimit IS NULL или <= 0 → None (общий лимит 1000);
          - если betlimit > 0 → вернуть это значение как максимальную ставку.
        """
        try:
            uid = int(user_id)
        except Exception:
            _log_err(f"[GC_DB] gc_get_bet_limit_for_user: user_id={user_id!r} не int")
            return None

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT betlimit
                    FROM z_game_challenge_active_assignments
                    WHERE user_id = $1
                      AND status  = 'active'
                    LIMIT 1
                    """ , uid , )

            if not row:
                _log_info(f"[GC_DB] gc_get_bet_limit_for_user: активное задание не найдено для user_id={uid}")
                return None

            raw_limit = row.get("betlimit")

            if raw_limit is None:
                _log_info(f"[GC_DB] gc_get_bet_limit_for_user: betlimit=NULL → используем общий лимит")
                return None

            try:
                bet_limit = int(raw_limit)
            except Exception as e:
                _log_err(
                    f"[GC_DB] gc_get_bet_limit_for_user: ошибка приведения betlimit={raw_limit!r} к int: {e}")
                return None

            if bet_limit <= 0:
                _log_info(
                    f"[GC_DB] gc_get_bet_limit_for_user: betlimit={bet_limit} <= 0 → используем общий лимит")
                return None

            _log_info(
                f"[GC_DB] gc_get_bet_limit_for_user: user_id={uid}, active betlimit={bet_limit}")
            return bet_limit

        except Exception as e:
            import traceback
            _log_err(
                f"[GC_DB] gc_get_bet_limit_for_user({user_id}): {e}\n{traceback.format_exc()}")
            return None

    # ---------------- DB: mark_gc_assignment_failed ----------------
    async def mark_gc_assignment_failed(self , user_id: int) -> bool:
        """
        Помечает текущее активное GC-задание пользователя как 'failed'
        и освобождает слот шаблона (decrement_gc_template_completed).

        Вызывай это, когда пользователь окончательно провалил челлендж
        (например, виртуальный баланс упал до нуля).
        """
        try:
            template_id = None

            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        """
                        SELECT id, template_id
                        FROM z_game_challenge_active_assignments
                        WHERE user_id = $1 AND status = 'active'
                        FOR UPDATE
                        """ , int(user_id) , )
                    if not row:
                        _log_warn(
                            f"mark_gc_assignment_failed: no active assignment for user {user_id}")
                        return False

                    assignment_id = row [ "id" ]
                    template_id = row [ "template_id" ]

                    await conn.execute(
                        """
                        UPDATE z_game_challenge_active_assignments
                        SET status = 'failed',
                            finished_at = NOW()
                        WHERE id = $1
                        """ , int(assignment_id) , )

            if template_id:
                await self.decrement_gc_template_completed(int(template_id) , step=1)

            _log_ok(
                f"mark_gc_assignment_failed: user_id={user_id}, template_id={template_id}")
            return True

        except Exception as e:
            _log_err(
                f"mark_gc_assignment_failed({user_id}): {e}\n{traceback.format_exc()}")
            return False

    # ---------------- DB: mark_gc_assignment_finished ----------------
    async def mark_gc_assignment_finished(self, user_id: int) -> bool:
        """
        Помечает активное GC-задание пользователя как 'finish' (успешно выполнено).

        ВАЖНО:
        ✔️ completed_users НЕ меняем
        ✔️ слот остаётся занятым навсегда
        ❌ никакого +1 не добавляем

        Эта функция только:
        - фиксирует статус 'finish'
        - ставит finished_at
        """
        if not user_id:
            _log_warn("mark_gc_assignment_finished: пустой user_id")
            return False

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Ищем активное задание пользователя
                    row = await conn.fetchrow(
                        """
                        SELECT id, template_id, status
                        FROM z_game_challenge_active_assignments
                        WHERE user_id = $1
                        ORDER BY id DESC
                        LIMIT 1
                        FOR UPDATE
                        """,
                        int(user_id),
                    )

                    if not row:
                        _log_warn(
                            f"mark_gc_assignment_finished: active assignment not found for user {user_id}"
                        )
                        return False

                    assign_id = row["id"]
                    tpl_id = row["template_id"]
                    status = (row.get("status") or "").strip().lower()

                    # Если задание уже не active -> ничего не делаем
                    # (особенно - не трогаем completed_users)
                    if status != "active":
                        _log_warn(
                            f"mark_gc_assignment_finished: user {user_id} assignment id={assign_id} "
                            f"status={status!r}, skip finish"
                        )
                        return False

                    # Меняем статус задания на finish
                    await conn.execute(
                        """
                        UPDATE z_game_challenge_active_assignments
                        SET status = 'finish',
                            finished_at = NOW()
                        WHERE id = $1
                        """,
                        int(assign_id),
                    )

                    _log_ok(
                        f"mark_gc_assignment_finished: assignment id={assign_id} "
                        f"for user={user_id} template_id={tpl_id}, "
                        f"status active -> finish (completed_users НЕ изменён)"
                    )

            return True

        except Exception as e:
            _log_err(
                f"mark_gc_assignment_finished({user_id}): {e}\n{traceback.format_exc()}"
            )
            return False

    async def fail_gc_assignment(self , user_id: int) -> Optional [ Dict [ str , Any ] ]:
        """
        Помечает АКТИВНОЕ задание пользователя как failed
        и одновременно освобождает один слот в шаблоне
        (completed_users -= 1, но не ниже 0).

        Если активного задания нет или оно уже не active – слоты не трогаем.
        Гарантия: completed_users в шаблоне никогда не станет меньше 0.
        """
        if not user_id:
            _log_warn("fail_gc_assignment: пустой user_id")
            return None

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # 1) Берём последнее задание пользователя (под блокировку)
                    assignment = await conn.fetchrow(
                        """
                        SELECT id, user_id, template_id, status
                        FROM z_game_challenge_active_assignments
                        WHERE user_id = $1
                        ORDER BY id DESC
                        LIMIT 1
                        FOR UPDATE
                        """ ,
                        int(user_id)
                    )

                    if not assignment:
                        _log_warn(f"fail_gc_assignment: assignment not found for user {user_id}")
                        return None

                    assign_id = assignment [ "id" ]
                    tpl_id = assignment [ "template_id" ]
                    status_raw = assignment [ "status" ] or ""
                    status = status_raw.strip().lower()

                    _log_ok(
                        f"fail_gc_assignment: found assignment id={assign_id} "
                        f"for user={user_id}, template_id={tpl_id}, status={status!r}"
                    )

                    # 2) Если задание уже не active – ничего не делаем со слотами
                    if status != "active":
                        _log_warn(
                            f"fail_gc_assignment: assignment id={assign_id} for user={user_id} "
                            f"has status={status!r}, skip slot decrement"
                        )
                        # Просто возвращаем то, что нашли (как dict)
                        return await self._row_to_dict(assignment)

                    # 3) Обновляем статус задания на failed
                    updated_assignment = await conn.fetchrow(
                        """
                        UPDATE z_game_challenge_active_assignments
                        SET status = 'failed'
                        WHERE id = $1
                        RETURNING id, user_id, template_id, status
                        """ ,
                        int(assign_id)
                    )

                    if not updated_assignment:
                        _log_err(
                            f"fail_gc_assignment: UPDATE assignment id={assign_id} "
                            f"for user={user_id} вернул пусто"
                        )
                        return None

                    # 4) Если по каким-то причинам нет template_id –
                    #    аккуратно завершаем без изменения слотов.
                    if tpl_id is None:
                        _log_warn(
                            f"fail_gc_assignment: assignment id={assign_id} for user={user_id} "
                            f"has template_id=None, slots are not changed"
                        )
                        return await self._row_to_dict(updated_assignment)

                    # 5) Берём шаблон под блокировку
                    tpl_row = await conn.fetchrow(
                        """
                        SELECT id, completed_users
                        FROM z_game_challenge_templates
                        WHERE id = $1
                        FOR UPDATE
                        """ ,
                        int(tpl_id)
                    )

                    if not tpl_row:
                        _log_warn(
                            f"fail_gc_assignment: template {tpl_id} not found for assignment {assign_id}, "
                            f"slot not decremented"
                        )
                        return await self._row_to_dict(updated_assignment)

                    cur_raw = tpl_row [ "completed_users" ]
                    try:
                        cur_int = int(cur_raw) if cur_raw is not None else 0
                    except Exception as e:
                        _log_err(
                            f"fail_gc_assignment: bad completed_users={cur_raw!r} "
                            f"for template_id={tpl_id}: {e}"
                        )
                        cur_int = 0

                    # Здесь жёстко гарантируем, что не уйдём ниже 0
                    if cur_int <= 0:
                        newv = 0
                        _log_warn(
                            f"fail_gc_assignment: template_id={tpl_id}, "
                            f"completed_users={cur_int} -> уже 0 или меньше, "
                            f"слоты не уменьшаем"
                        )
                    else:
                        newv = cur_int - 1

                    # Страховка от любых приколов: newv не меньше 0
                    if newv < 0:
                        _log_err(
                            f"fail_gc_assignment: вычислен newv={newv} < 0 "
                            f"для template_id={tpl_id}, принудительно ставим 0"
                        )
                        newv = 0

                    await conn.execute(
                        """
                        UPDATE z_game_challenge_templates
                        SET completed_users = $2
                        WHERE id = $1
                        """ ,
                        int(tpl_id) ,
                        int(newv)
                    )

                    _log_ok(
                        f"fail_gc_assignment: user={user_id}, assign_id={assign_id}, "
                        f"template_id={tpl_id}, status: active -> failed, "
                        f"slots: {cur_int} -> {newv}"
                    )

                    return await self._row_to_dict(updated_assignment)

        except Exception as e:
            _log_err(f"fail_gc_assignment({user_id}): {e}\n{traceback.format_exc()}")
            return None

    async def gc_disable_template_by_id(self , template_id: int) -> Optional [ Dict [ str , Any ] ]:
        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    """
                    UPDATE z_game_challenge_templates
                    SET status = 'disabled'
                    WHERE id = $1
                      AND status = 'active'
                    RETURNING
                        id,
                        start_amount,
                        target_amount,
                        reward_amount,
                        betlimit,
                        max_users,
                        completed_users,
                        target_chat_id,
                        target_chat_ref,
                        free,
                        status,
                        created_at,
                        TO_CHAR(
                            created_at AT TIME ZONE 'Europe/Oslo',
                            'HH24:MI | DD.MM.YYYY'
                        ) AS created_pretty
                    """ , int(template_id) , )
                if not row:
                    _log_info(f"gc_disable_template_by_id: id={template_id} not found or not active")
                    return None
                _log_ok(f"gc_disable_template_by_id: disabled id={row [ 'id' ]}")
                return await self._row_to_dict(row)
        except Exception as e:
            _log_err(f"gc_disable_template_by_id({template_id}): {e}\n{traceback.format_exc()}")
            return None

    async def gc_find_template_for_delete(self , raw_target: str) -> Optional [ Dict [ str , Any ] ]:
        if raw_target is None:
            return None
        raw = str(raw_target).strip()
        if not raw:
            return None
        try:
            async with self.pool.acquire() as connection:
                tmp = raw
                if tmp.startswith("-"):
                    tmp = tmp [ 1: ]
                if tmp.isdigit():
                    num = int(raw)
                    row = await connection.fetchrow(
                        """
                        SELECT
                            id,
                            start_amount,
                            target_amount,
                            reward_amount,
                            betlimit,
                            max_users,
                            completed_users,
                            target_chat_id,
                            target_chat_ref,
                            free,
                            status,
                            created_at,
                            TO_CHAR(
                                created_at AT TIME ZONE 'Europe/Oslo',
                                'HH24:MI | DD.MM.YYYY'
                            ) AS created_pretty
                        FROM z_game_challenge_templates
                        WHERE status = 'active'
                          AND target_chat_id = $1
                        ORDER BY id DESC
                        LIMIT 1
                        """ , num , )
                    if row:
                        _log_info(
                            f"gc_find_template_for_delete: found by chat_id={num} id={row [ 'id' ]}")
                        return await self._row_to_dict(row)
                    row = await connection.fetchrow(
                        """
                        SELECT
                            id,
                            start_amount,
                            target_amount,
                            reward_amount,
                            betlimit,
                            max_users,
                            completed_users,
                            target_chat_id,
                            target_chat_ref,
                            free,
                            status,
                            created_at,
                            TO_CHAR(
                                created_at AT TIME ZONE 'Europe/Oslo',
                                'HH24:MI | DD.MM.YYYY'
                            ) AS created_pretty
                        FROM z_game_challenge_templates
                        WHERE id = $1
                          AND status = 'active'
                        """ , num , )
                    if row:
                        _log_info(
                            f"gc_find_template_for_delete: found by template id={num}")
                        return await self._row_to_dict(row)

                # обработка username/slug
                slug = raw
                m = re.search(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)" , raw , flags=re.IGNORECASE)
                if m:
                    slug = m.group(1)
                else:
                    if slug.startswith("@"):
                        slug = slug [ 1: ]
                if not slug:
                    return None
                like = f"%{slug}%"
                row = await connection.fetchrow(
                    """
                    SELECT
                        id,
                        start_amount,
                        target_amount,
                        reward_amount,
                        betlimit,
                        max_users,
                        completed_users,
                        target_chat_id,
                        target_chat_ref,
                        free,
                        status,
                        created_at,
                        TO_CHAR(
                            created_at AT TIME ZONE 'Europe/Oslo',
                            'HH24:MI | DD.MM.YYYY'
                        ) AS created_pretty
                    FROM z_game_challenge_templates
                    WHERE status = 'active'
                      AND target_chat_ref ILIKE $1
                    ORDER BY id DESC
                    LIMIT 1
                    """ , like , )
                if row:
                    _log_info(
                        f"gc_find_template_for_delete: found by ref like {slug}, id={row [ 'id' ]}")
                    return await self._row_to_dict(row)
                _log_info(f"gc_find_template_for_delete: nothing found for {raw}")
                return None
        except Exception as e:
            _log_err(f"gc_find_template_for_delete({raw}): {e}\n{traceback.format_exc()}")
            return None

    # ================== СПИСОК ШАБЛОНОВ ЗАДАНИЙ ==================
    async def list_gc_templates(self , active_only: bool = False , limit: int = 50) -> List [ Dict [ str , Any ] ]:
        try:
            limit = max(1 , min(200 , int(limit)))
        except Exception:
            limit = 50

        try:
            async with self.pool.acquire() as conn:
                if active_only:
                    query = """
                        SELECT
                            id,
                            start_amount,
                            target_amount,
                            reward_amount,
                            betlimit,
                            max_users,
                            completed_users,
                            target_chat_id,
                            target_chat_ref,
                            free,
                            status,
                            created_at,
                            TO_CHAR(created_at AT TIME ZONE 'Europe/Oslo','HH24:MI | DD.MM.YYYY') AS created_pretty
                        FROM z_game_challenge_templates
                        WHERE status = 'active'
                          AND (max_users IS NULL OR completed_users < max_users)
                        ORDER BY id DESC
                        LIMIT $1
                    """
                else:
                    query = """
                        SELECT
                            id,
                            start_amount,
                            target_amount,
                            reward_amount,
                            betlimit,
                            max_users,
                            completed_users,
                            target_chat_id,
                            target_chat_ref,
                            free,
                            status,
                            created_at,
                            TO_CHAR(created_at AT TIME ZONE 'Europe/Oslo','HH24:MI | DD.MM.YYYY') AS created_pretty
                        FROM z_game_challenge_templates
                        ORDER BY id DESC
                        LIMIT $1
                    """
                rows = await conn.fetch(query , limit)
                _log_info(f"list_gc_templates(active_only={active_only}, limit={limit}) -> {len(rows)}")
                out = [ ]
                for r in rows:
                    out.append(await self._row_to_dict(r))
                return out
        except Exception as e:
            _log_err(f"list_gc_templates error: {e}\n{traceback.format_exc()}")
            return [ ]

    async def gc_resolve_chat_target(self , raw_ref: Optional [ str ]) -> Tuple [
        Optional [ int ] , Optional [ str ] ]:
        raw_ref = (raw_ref or "").strip()
        if not raw_ref:
            return None , None

        raw_digits = raw_ref.replace(" " , "")
        if raw_digits.replace("-" , "").isdigit():
            try:
                return int(raw_digits) , raw_ref
            except Exception as e:
                _log_warn(f"gc_resolve_chat_target: int cast failed {raw_digits}: {e}")

        def _extract_username_token(s: str) -> str:
            s = s.strip()
            m = re.search(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)" , s , flags=re.IGNORECASE)
            if m:
                return m.group(1)
            if s.startswith("@"):
                return s [ 1: ]
            return s

        username_token = _extract_username_token(raw_ref)
        username_token_l = username_token.lower()

        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    "SELECT chat_id, usernamechat, chatlink FROM chat WHERE LOWER(usernamechat) = LOWER($1) LIMIT 1" ,
                    username_token_l)
                if row:
                    cid = row [ "chat_id" ]
                    uname = row [ "usernamechat" ]
                    canonical = f"@{uname}" if uname else raw_ref
                    _log_info(f"gc_resolve_chat_target: found by usernamechat {uname} -> {cid}")
                    return cid , canonical

                row = await connection.fetchrow(
                    "SELECT chat_id, usernamechat, chatlink FROM chat WHERE LOWER(chatlink) = LOWER($1) OR LOWER(chatlink) LIKE '%' || LOWER($2) || '%' LIMIT 1" ,
                    raw_ref , username_token_l)
                if row:
                    cid = row [ "chat_id" ]
                    uname = row [ "usernamechat" ]
                    link = row [ "chatlink" ]
                    canonical = f"@{uname}" if uname else (link or raw_ref)
                    _log_info(f"gc_resolve_chat_target: found by chatlink {link} -> {cid}")
                    return cid , canonical

                _log_info(f"gc_resolve_chat_target: not found for {raw_ref}")
                return None , raw_ref
        except Exception as e:
            _log_err(f"gc_resolve_chat_target({raw_ref}): {e}\n{traceback.format_exc()}")
            return None , raw_ref

    async def gc_find_similar_template(self , chat_ref: Optional [ str ] , start_amount: int , target_amount: int ,
            free_flag: Optional [ str ] = None , ) -> Optional [ Dict [ str , Any ] ]:
        chat_ref_db = (chat_ref or "").strip() or None

        # Нормализация флага: всё, что не '+', считаем '-'
        free_raw = (free_flag or "-").strip()
        free_norm = "+" if free_raw == "+" else "-"

        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    """
                    SELECT
                        id,
                        start_amount,
                        target_amount,
                        reward_amount,
                        betlimit,
                        max_users,
                        completed_users,
                        target_chat_id,
                        target_chat_ref,
                        free,
                        status,
                        created_at,
                        TO_CHAR(
                            created_at AT TIME ZONE 'Europe/Oslo',
                            'HH24:MI | DD.MM.YYYY'
                        ) AS created_pretty
                    FROM z_game_challenge_templates
                    WHERE status = 'active'
                      AND COALESCE(target_chat_ref, '') = COALESCE($1, '')
                      AND start_amount = $2
                      AND target_amount = $3
                      AND COALESCE(free, '-') = $4
                    LIMIT 1
                    """ , chat_ref_db , int(start_amount) , int(target_amount) , free_norm , )
                return await self._row_to_dict(row)
        except Exception as e:
            _log_err(
                f"gc_find_similar_template(chat_ref={chat_ref}, start={start_amount}, "
                f"target={target_amount}, free_flag={free_flag}): {e}\n{traceback.format_exc()}")
            return None

    async def create_gc_template_record(self , start_amount: int , target_amount: int , reward_amount: int ,
            chat_ref: Optional [ str ] , max_users: Optional [ int ] , max_bet: Optional [ int ] = None ,
            free_flag: Optional [ str ] = None , ) -> Dict [ str , Any ]:
        def _safe_int(x):
            try:
                return int(x)
            except Exception:
                return 0

        start_amount = _safe_int(start_amount)
        target_amount = _safe_int(target_amount)
        reward_amount = _safe_int(reward_amount)

        betlimit = None
        if max_bet is not None:
            mb = _safe_int(max_bet)
            if mb > 0:
                betlimit = mb

        # Нормализация free_flag: всё, что не '+', считаем '-'
        free_raw = (free_flag or "-").strip()
        free_norm = "+" if free_raw == "+" else "-"

        if (start_amount <= 0 or target_amount <= 0 or reward_amount <= 0 or target_amount <= start_amount):
            _log_warn("create_gc_template_record: invalid numeric params")
            return {"status": "error" , "row": None , "existing": None}

        if max_users is not None:
            try:
                max_users = int(max_users)
                if max_users <= 0:
                    max_users = None
            except Exception:
                max_users = None

        chat_ref_raw = (chat_ref or "").strip() or None

        # ensure table exists (best-effort) + ensure column free
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS z_game_challenge_templates (
                        id BIGSERIAL PRIMARY KEY,
                        start_amount BIGINT NOT NULL,
                        target_amount BIGINT NOT NULL,
                        reward_amount BIGINT NOT NULL,
                        betlimit BIGINT,
                        max_users BIGINT,
                        completed_users BIGINT NOT NULL DEFAULT 0 CHECK (completed_users >= 0),
                        target_chat_id BIGINT,
                        target_chat_ref TEXT,
                        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """)
                await connection.execute(
                    """
                    ALTER TABLE z_game_challenge_templates
                    ADD COLUMN IF NOT EXISTS free TEXT
                    """)
        except Exception as e:
            _log_err(
                f"create_gc_template_record: ensure table/column failed: {e}\n{traceback.format_exc()}")
            return {"status": "error" , "row": None , "existing": None}

        # Пытаемся нормализовать чат
        try:
            chat_id_resolved , chat_ref_canon = await self.gc_resolve_chat_target(chat_ref_raw)
        except Exception as e:
            _log_warn(f"gc_resolve_chat_target failed: {e}")
            chat_id_resolved , chat_ref_canon = None , chat_ref_raw

        dup_ref = chat_ref_canon or chat_ref_raw

        # Проверяем дубликат с учётом free_flag
        similar = await self.gc_find_similar_template(
            chat_ref=dup_ref , start_amount=start_amount , target_amount=target_amount , free_flag=free_norm , )
        if similar:
            _log_warn(
                f"create_gc_template_record: duplicate template found id={similar.get('id')}, "
                f"free={similar.get('free')}")
            return {"status": "duplicate" , "row": None , "existing": similar}

        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    """
                    INSERT INTO z_game_challenge_templates
                        (start_amount,
                         target_amount,
                         reward_amount,
                         betlimit,
                         max_users,
                         completed_users,
                         target_chat_id,
                         target_chat_ref,
                         free,
                         status,
                         created_at)
                    VALUES
                        ($1,$2,$3,$4,$5,0,$6,$7,$8,'active', NOW())
                    RETURNING
                        id,
                        start_amount,
                        target_amount,
                        reward_amount,
                        betlimit,
                        max_users,
                        completed_users,
                        target_chat_id,
                        target_chat_ref,
                        free,
                        status,
                        created_at,
                        TO_CHAR(
                            created_at AT TIME ZONE 'Europe/Oslo',
                            'HH24:MI | DD.MM.YYYY'
                        ) AS created_pretty
                    """ , start_amount , target_amount , reward_amount , betlimit , max_users , chat_id_resolved ,
                    dup_ref , free_norm , )
                if not row:
                    _log_err("create_gc_template_record: insert returned None")
                    return {"status": "error" , "row": None , "existing": None}
                _log_ok(
                    f"create_gc_template_record: created id={row [ 'id' ]} free={free_norm!r}")
                return {"status": "ok" , "row": await self._row_to_dict(row) , "existing": None}
        except asyncpg.exceptions.UniqueViolationError:
            _log_warn("create_gc_template_record: unique violation -> searching existing")
            similar = await self.gc_find_similar_template(
                chat_ref=dup_ref , start_amount=start_amount , target_amount=target_amount , free_flag=free_norm , )
            return {"status": "duplicate" , "row": None , "existing": similar}
        except Exception as e:
            _log_err(
                f"create_gc_template_record insert failed: {e}\n{traceback.format_exc()}")
            return {"status": "error" , "row": None , "existing": None}

    async def get_gc_template_by_id(self , template_id: int) -> Optional [ Dict [ str , Any ] ]:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        id,
                        start_amount,
                        target_amount,
                        reward_amount,
                        betlimit,
                        max_users,
                        completed_users,
                        target_chat_id,
                        target_chat_ref,
                        free,
                        status,
                        created_at,
                        TO_CHAR(
                            created_at AT TIME ZONE 'Europe/Oslo',
                            'HH24:MI | DD.MM.YYYY'
                        ) AS created_pretty
                    FROM z_game_challenge_templates
                    WHERE id = $1
                    """ , int(template_id) , )
                return await self._row_to_dict(row)
        except Exception as e:
            _log_err(f"get_gc_template_by_id({template_id}): {e}\n{traceback.format_exc()}")
            return None

    async def get_active_gc_assignment(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Вернуть текущее АКТИВНОЕ игровое задание пользователя
        из z_game_challenge_active_assignments.

        Логика:
          1) Ищем активное задание по user_id и status='active'.
          2) Если нашли - берём его template_id.
          3) По template_id дополнительно читаем z_game_challenge_templates:
             - target_chat_id
             - target_chat_ref
          4) Возвращаем dict со ВСЕЙ этой информацией.

        Если активного задания нет - возвращает None.
        При любой ошибке на шаге 3 (templates) - возвращаем задание БЕЗ полей target_chat_*.
        """
        try:
            uid_int = int(user_id)
        except Exception as e:
            _log_err(
                f"get_active_gc_assignment: user_id={user_id!r} не получается привести к int: {e}"
            )
            return None

        try:
            async with self.pool.acquire() as conn:
                # ---------------- ШАГ 1: берём активное задание ----------------
                _log_ok(f"[GC/DB] get_active_gc_assignment: ищем активное задание для user_id={uid_int}")

                row = await conn.fetchrow(
                    """
                    SELECT
                        id,
                        user_id,
                        first_name,
                        username,
                        template_id,
                        assigned_at,
                        two_balance,
                        two_balance_initial AS two_balance_initial,
                        status,
                        progress_json,
                        betlimit,
                        target_amount,
                        reward_amount,
                        created_at,
                        last_updated_at,
                        TO_CHAR(
                            created_at AT TIME ZONE 'Europe/Oslo',
                            'HH24:MI | DD.MM.YYYY'
                        ) AS created_pretty
                    FROM z_game_challenge_active_assignments
                    WHERE user_id = $1
                      AND LOWER(status) = 'active'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    uid_int,
                )

                if not row:
                    _log_warn(
                        f"[GC/DB] get_active_gc_assignment: активное задание НЕ найдено для user_id={uid_int}"
                    )
                    return None

                d = await self._row_to_dict(row)
                assign_id = d.get("id")
                tpl_id = d.get("template_id")

                _log_ok(
                    f"[GC/DB] get_active_gc_assignment: найдено активное задание id={assign_id}, "
                    f"user_id={uid_int}, template_id={tpl_id}"
                )

                # ---------------- ШАГ 2: тянем шаблон из templates ----------------
                if tpl_id is None:
                    _log_warn(
                        f"[GC/DB] get_active_gc_assignment: у задания id={assign_id} нет template_id, "
                        "поэтому группу проверить нельзя"
                    )
                    return d

                try:
                    tpl_id_int = int(tpl_id)
                except Exception as e:
                    _log_warn(
                        f"[GC/DB] get_active_gc_assignment: template_id={tpl_id!r} не int, "
                        f"ошибка: {e}. Группу не подцепляем."
                    )
                    return d

                _log_ok(
                    f"[GC/DB] get_active_gc_assignment: пробуем найти шаблон в z_game_challenge_templates "
                    f"по id={tpl_id_int}"
                )

                tpl_row = await conn.fetchrow(
                    """
                    SELECT
                        id,
                        target_chat_id,
                        target_chat_ref
                    FROM z_game_challenge_templates
                    WHERE id = $1
                    LIMIT 1
                    """,
                    tpl_id_int,
                )

                if not tpl_row:
                    _log_warn(
                        f"[GC/DB] get_active_gc_assignment: в z_game_challenge_templates нет строки "
                        f"с id={tpl_id_int} (задание id={assign_id})"
                    )
                    # Возвращаем само задание, просто без инфы о группе
                    return d

                tpl_dict = dict(tpl_row)
                target_chat_id = tpl_dict.get("target_chat_id")
                target_chat_ref = tpl_dict.get("target_chat_ref")

                _log_ok(
                    "[GC/DB] get_active_gc_assignment: для template_id={tid} найден шаблон: "
                    "target_chat_id={cid}, target_chat_ref={ref}".format(
                        tid=tpl_id_int,
                        cid=target_chat_id,
                        ref=target_chat_ref,
                    )
                )

                # аккуратно дописываем в результат
                d["target_chat_id"] = target_chat_id
                d["target_chat_ref"] = target_chat_ref

                return d

        except Exception as e:
            _log_err(
                f"[GC/DB] get_active_gc_assignment({user_id}): общая ошибка: {e}\n"
                f"{traceback.format_exc()}"
            )
            return None

    async def increment_gc_template_completed(self , template_id: int , step: int = 1 , ) -> Optional [
        Dict [ str , Any ] ]:
        """
        Увеличивает completed_users у шаблона (занимаем слот).

        Возвращает dict с данными шаблона или None, если:
          - шаблон не найден;
          - статус не active;
          - слоты уже исчерпаны (max_users);
          - произошла ошибка.
        """
        if step <= 0:
            step = 1

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Блокируем строку шаблона
                    row = await conn.fetchrow(
                        """
                        SELECT id, completed_users, max_users, status
                        FROM z_game_challenge_templates
                        WHERE id = $1
                        FOR UPDATE
                        """ , int(template_id) , )
                    if not row:
                        _log_warn(f"increment_gc_template_completed: template {template_id} not found")
                        return None

                    status = str(row.get("status") or "active").strip().lower()
                    if status not in ("active" , ""):
                        _log_warn(
                            f"increment_gc_template_completed: template {template_id} not active "
                            f"(status={status!r})")
                        return None

                    cur = row [ "completed_users" ] or 0
                    max_users = row.get("max_users")

                    # Проверка капа по слоту
                    if max_users is not None:
                        try:
                            max_users_int = int(max_users)
                        except Exception:
                            max_users_int = None

                        if max_users_int is not None:
                            if max_users_int <= 0:
                                _log_warn(
                                    f"increment_gc_template_completed: template {template_id} "
                                    f"max_users={max_users_int} -> no slots")
                                return None
                            if cur >= max_users_int:
                                _log_warn(
                                    f"increment_gc_template_completed: template {template_id} "
                                    f"slots exhausted {cur}/{max_users_int}")
                                return None

                            # Не выходим за пределы
                            newv = min(max_users_int , cur + step)
                        else:
                            newv = cur + step
                    else:
                        # Нет капа - просто увеличиваем
                        newv = cur + step

                    updated = await conn.fetchrow(
                        """
                        UPDATE z_game_challenge_templates
                        SET completed_users = $2
                        WHERE id = $1
                        RETURNING
                            id,
                            start_amount,
                            target_amount,
                            reward_amount,
                            betlimit,
                            max_users,
                            completed_users,
                            target_chat_id,
                            target_chat_ref,
                            free,
                            status,
                            created_at,
                            TO_CHAR(
                                created_at AT TIME ZONE 'Europe/Oslo',
                                'HH24:MI | DD.MM.YYYY'
                            ) AS created_pretty
                        """ , int(template_id) , int(newv) , )

                    _log_ok(
                        f"increment_gc_template_completed: id={template_id}, "
                        f"{cur} -> {newv}")
                    return await self._row_to_dict(updated) if updated else None

        except Exception as e:
            _log_err(
                f"increment_gc_template_completed({template_id}): {e}\n"
                f"{traceback.format_exc()}")
            return None

    async def award_reward_to_user(self , user_id: int , amount: int) -> bool:
        """
        Раньше сама делала SELECT ... FOR UPDATE + UPDATE balance напрямую -
        в обход update_user_balance, из-за чего кэш баланса (user_cache_balance/
        Redis) не обновлялся сразу после начисления. Теперь начисление идёт
        через единую защищённую функцию (delta-режим), аудит-запись в
        user_balance_log сохранена как была.
        """
        try:
            new_balance = await self.update_user_balance(int(user_id) , f"+{int(amount)}")
            if new_balance is None:
                _log_warn(f"award_reward_to_user: update_user_balance failed for user {user_id}")
                return False

            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO user_balance_log(user_id, amount, note, created_at) VALUES($1, $2, $3, NOW())" ,
                    int(user_id) , int(amount) , "gc_reward")

            _log_ok(f"award_reward_to_user: user={user_id} +{amount} -> {new_balance}")
            return True
        except Exception as e:
            _log_err(f"award_reward_to_user({user_id}, {amount}): {e}\n{traceback.format_exc()}")
            return False





















































    async def get_user_row(self , user_id: int) -> Optional [ Dict [ str , Any ] ]:
        """
        Точечный запрос по users.user_id -> dict | None.
        Возвращаем только ключевые поля (можешь расширить SELECT).
        """
        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    """
                    SELECT user_id, balance, first_name, username, vip, active, last_active
                    FROM users
                    WHERE user_id = $1
                    """ , user_id , )
                return dict(row) if row else None
        except Exception as e:
            print(f"[ERROR] get_user_row({user_id}) : {e}")
            return None

    # ---------- Точечный запрос по пользователю ----------
    async def get_user_row(self , user_id: int) -> Optional [ Dict [ str , Any ] ]:
        """
        Точечная проверка пользователя в основной таблице users.
        Возвращает dict со столбцами или None, если записи нет.
        Расширь список столбцов под свои нужды.
        """
        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    """
                    SELECT
                        user_id,
                        balance,
                        first_name,
                        username,
                        vip,
                        active,
                        last_active
                    FROM users
                    WHERE user_id = $1
                    """ , user_id , )
                return dict(row) if row else None
        except Exception as e:
            print(f"[ERROR] get_user_row({user_id}): {e}")
            return None

    # ---------- Батч по пользователям (для фоновой синхронизации) ----------
    async def get_users_rows(self , user_ids: List [ int ]) -> List [ Dict [ str , Any ] ]:
        """
        Возвращает список словарей для существующих user_id.
        Не найденные в БД user_id просто отсутствуют в результате.
        """
        if not user_ids:
            return [ ]
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    """
                    SELECT
                        user_id,
                        balance,
                        first_name,
                        username,
                        vip,
                        active,
                        last_active
                    FROM users
                    WHERE user_id = ANY($1::bigint[])
                    """ , user_ids , )
                return [ dict(r) for r in rows ]
        except Exception as e:
            print(f"[ERROR] get_users_rows({len(user_ids)} ids): {e}")
            return [ ]
    async def get_promocode_by_code(self , promo_code: str):
        try:
            async with self.pool.acquire() as connection:
                query = """
                    SELECT promo, count, maxcount, priceonone, maxprice, data, chat_id
                    FROM promocode
                    WHERE LOWER(promo) = LOWER($1)
                """
                row = await connection.fetchrow(query , promo_code.lower())
                return row
        except Exception as e:
            print(f"[ERROR] Ошибка при получении промокода из БД: {e}")
            return None

    async def save_withdrawal_record(self , user_id: int , amount: int , withdrawal_text: str):
        """
        Сохраняет запись о выводе в savedataw:
          - user_id    → идентификатор пользователя
          - count      → сумма текущего вывода (целое количество кут)
          - allcount   → суммарный вывод по пользователю (включая текущий)
          - data       → ТЕКСТ, формат "HH:MM DD.MM.YYYY" (время/дата Европы/Осло)
          - withdrawal → текстовая метка

        Возвращает asyncpg.Record или None при ошибке.
        """

        # ---------- 1) Нормализация и валидация входных данных ----------
        def _to_int_amount(x) -> int:
            """
            Поддерживает: 1000, "1 000", "1 000", "1,000", "1000.00".
            Любые пробелы (в т.ч. неразрывные) и запятые удаляются.
            Десятичную точку/запятую отбрасываем (берём целую часть).
            """
            if x is None:
                return 0
            if isinstance(x , (int ,)):
                return int(x)
            s = str(x).strip()
            # Заменяем все варианты пробелов (обычные и неразрывные)
            s = s.replace("\u00A0" , " ").replace("\u202F" , " ")
            # Удаляем пробелы и запятые-разделители тысяч
            s = s.replace(" " , "").replace("," , "")
            # Если есть десятичная точка - берём целую часть слева
            if "." in s:
                s = s.split("." , 1) [ 0 ]
            if not s.isdigit():
                return 0
            return int(s)

        amt = _to_int_amount(amount)
        if amt <= 0:
            print(f"[WARN] Некорректная сумма вывода: user_id={user_id}, amount={amount!r} → amt={amt}")
            return None

        # Нормализуем и ограничим текст метки (напр., до 200 символов - подстрой под схему)
        wtext = (withdrawal_text or "").strip()
        if len(wtext) > 200:
            wtext = wtext [ :200 ]

        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    # ---------- 2) Пер-пользовательская блокировка ----------
                    try:
                        # Прямо по user_id (если влезает в bigint)
                        await connection.execute("SELECT pg_advisory_xact_lock($1::bigint)" , int(user_id))
                    except Exception:
                        # Универсальный вариант через md5 → 64 бита
                        await connection.execute(
                            "SELECT pg_advisory_xact_lock( ('x'||substr(md5($1),1,16))::bit(64)::bigint )" ,
                            str(user_id) , )

                    # ---------- 3) Предыдущая суммарная сумма ----------
                    # Всегда приводим count к numeric, чтобы работать и с text-столбцом, и с numeric/int.
                    # NULL/пустые/некорректные значения трактуем как 0.
                    query_sum = """
                        SELECT COALESCE(SUM(NULLIF(TRIM(count::text), '')::numeric), 0) AS prev_sum
                        FROM savedataw
                        WHERE user_id = $1
                    """
                    row_sum = await connection.fetchrow(query_sum , user_id)
                    prev_sum_dec = row_sum [ "prev_sum" ] if row_sum else 0
                    try:
                        # Превратим в int безопасно (с учётом возможного Decimal)
                        prev_sum = int(prev_sum_dec)
                    except Exception:
                        prev_sum = 0

                    total_sum = prev_sum + amt  # будущий allcount

                    # ---------- 4) Вставка новой записи ----------
                    # Дата/время строго в Европе/Осло и в формате "HH:MM DD.MM.YYYY".
                    query_insert = """
                        INSERT INTO savedataw (user_id, count, allcount, data, withdrawal)
                        VALUES (
                            $1,
                            $2,
                            $3,
                            TO_CHAR(NOW() AT TIME ZONE 'Europe/Oslo', 'HH24:MI DD.MM.YYYY'),
                            $4
                        )
                        RETURNING user_id, count, allcount, data, withdrawal
                    """
                    row_inserted = await connection.fetchrow(
                        query_insert , user_id , amt , total_sum , wtext)
                    return row_inserted

        except Exception as e:
            print(f"[ERROR] Ошибка при сохранении вывода в БД: user_id={user_id}, amount={amount!r}, err={e}")
            return None

    # --- USERS ---

    # ====================== СХЕМА ======================
    async def ensure_quest_schema(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS users (
          user_id     BIGINT PRIMARY KEY,
          balance     NUMERIC(18,2) NOT NULL DEFAULT 0,
          quebalance  TEXT          NOT NULL DEFAULT '0.00',
          updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS quest_tasks (
          id              BIGSERIAL PRIMARY KEY,
          chat_ref        TEXT NOT NULL,
          reward          NUMERIC(18,2) NOT NULL,
          active          BOOLEAN NOT NULL DEFAULT TRUE,
          total_cap       INTEGER,
          ttl_expires_at  TIMESTAMPTZ,
          created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_quest_tasks_chat_ref ON quest_tasks (chat_ref);
        CREATE INDEX  IF NOT EXISTS ix_quest_tasks_ttl_expires_at ON quest_tasks (ttl_expires_at);

        CREATE TABLE IF NOT EXISTS quest_done (
          id          BIGSERIAL PRIMARY KEY,
          user_id     BIGINT NOT NULL,
          chat_ref    TEXT   NOT NULL,
          action      TEXT   NOT NULL CHECK (action IN ('sub','skip')),
          reward      NUMERIC(18,2) NOT NULL DEFAULT 0,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_quest_done_user_chat ON quest_done (user_id, chat_ref);
        CREATE INDEX  IF NOT EXISTS ix_quest_done_chat_ref_action ON quest_done (chat_ref, action);

        CREATE TABLE IF NOT EXISTS quest_clicks (
          user_id     BIGINT NOT NULL,
          task_id     BIGINT NOT NULL REFERENCES quest_tasks(id) ON DELETE CASCADE,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, task_id)
        );
        """
        async with self.pool.acquire() as c:
            await c.execute(sql)

    async def _ensure_caps_columns(self) -> None:
        try:
            async with self.pool.acquire() as c:
                await c.execute(
                    """
                    ALTER TABLE quest_tasks
                      ADD COLUMN IF NOT EXISTS total_cap INTEGER,
                      ADD COLUMN IF NOT EXISTS ttl_expires_at TIMESTAMPTZ
                """)
                await c.execute(
                    "CREATE INDEX IF NOT EXISTS ix_quest_tasks_ttl_expires_at ON quest_tasks (ttl_expires_at)")
        except Exception as e:
            print(f"[WARN] _ensure_caps_columns: {e}")
    # ================== QUEBALANCE (TEXT) ==================
    async def get_que_balance(self , user_id: int) -> Decimal:
        """Чтение quebalance как Decimal(2). Никогда не None."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COALESCE(quebalance, '0.00') AS qb FROM users WHERE user_id=$1" , user_id)
                qb = _parse_money_text(row [ "qb" ] if row else "0.00")
                print(f"💰 [QUE] get_que_balance: user_id={user_id} -> {qb}")
                return qb
        except Exception as e:
            print(f"💰 [QUE][ERR] get_que_balance: {e}")
            return D(0)

    async def update_que_balance(self , user_id: int , new_balance) -> bool:
        """
        Жёстко поставить quebalance = new_balance (UPSERT).
        Хранится как TEXT 'NN.NN'. Не трогаем обычный balance.
        """
        nb = D(new_balance)
        txt = _format_money_text(nb)
        print(f"💰 [QUE] update_que_balance: user_id={user_id} -> {txt}")
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO users (user_id, balance, quebalance)
                    VALUES ($1, 0, $2)
                    ON CONFLICT (user_id) DO UPDATE
                      SET quebalance = EXCLUDED.quebalance
                    """ , user_id , txt)
            print(f"💰 [QUE] update_que_balance: OK (user_id={user_id}, quebalance={txt})")
            return True
        except Exception as e:
            print(f"💰 [QUE][ERR] update_que_balance: {e}")
            return False

    async def add_que_balance(self , user_id: int , delta) -> Decimal:
        """
        Атомарно увеличить quebalance на delta (>=0).
        Возвращает новое значение (Decimal).
        """
        d = D(delta)
        if d < 0:
            print(f"💰 [QUE][WARN] add_que_balance: отрицательная дельта {d} - отклонено")
            return await self.get_que_balance(user_id)

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # гарантируем строку
                    await conn.execute(
                        "INSERT INTO users (user_id, balance, quebalance) VALUES ($1, 0, '0.00') "
                        "ON CONFLICT (user_id) DO NOTHING" , user_id)
                    # блокируем и считаем
                    row = await conn.fetchrow(
                        "SELECT quebalance FROM users WHERE user_id=$1 FOR UPDATE" , user_id)
                    cur = _parse_money_text(row [ "quebalance" ] if row else "0.00")
                    new_val = D(cur + d)
                    await conn.execute(
                        "UPDATE users SET quebalance=$1 WHERE user_id=$2" , _format_money_text(new_val) , user_id)
                    print(f"💰 [QUE] add_que_balance: user_id={user_id}, {cur} + {d} = {new_val}")
                    return new_val
        except Exception as e:
            print(f"💰 [QUE][ERR] add_que_balance: {e}")
            return await self.get_que_balance(user_id)

    async def deduct_que_balance(self , user_id: int , delta) -> bool:
        """
        Атомарно списать delta (>0) только если хватает средств.
        """
        d = D(delta)
        if d <= 0:
            print(f"💰 [QUE] deduct_que_balance: delta={d} (ничего не списываем)")
            return True

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "INSERT INTO users (user_id, balance, quebalance) VALUES ($1, 0, '0.00') "
                        "ON CONFLICT (user_id) DO NOTHING" , user_id)
                    row = await conn.fetchrow(
                        "SELECT quebalance FROM users WHERE user_id=$1 FOR UPDATE" , user_id)
                    cur = _parse_money_text(row [ "quebalance" ] if row else "0.00")
                    if cur < d:
                        print(f"💰 [QUE] deduct_que_balance: недостаточно средств (есть={cur}, нужно={d})")
                        return False

                    new_val = D(cur - d)
                    await conn.execute(
                        "UPDATE users SET quebalance=$1 WHERE user_id=$2" , _format_money_text(new_val) , user_id)
                    print(f"💰 [QUE] deduct_que_balance: user_id={user_id}, {cur} - {d} = {new_val}")
                    return True
        except Exception as e:
            print(f"💰 [QUE][ERR] deduct_que_balance: {e}")
            return False

    async def transfer_que_to_main(self , user_id: int , amount_int: int) -> bool:
        """
        Перевод целого amount_int из quebalance (TEXT) в основной balance (NUMERIC)
        через пары методов:
          - get_user_balance(user_id)
          - update_user_balance(user_id, new_balance)

        Логика:
          1) В одной транзакции: гарантируем пользователя, блокируем строку, проверяем
             и СНИМАЕМ amount с quebalance (TEXT).
          2) Вне этой транзакции: читаем текущий основной баланс через get_user_balance
             и пополняем его через update_user_balance ровно на amount.
          3) Если пополнение основного баланса не удалось - делаем компенсацию:
             возвращаем сумму обратно в quebalance и возвращаем False.

        Важно: amount_int должен быть целым (>0).
        """
        # валидация и подготовка суммы
        if not isinstance(amount_int , int) or amount_int <= 0:
            print(f"💰 [QUE] transfer_que_to_main: некорректная сумма {amount_int}")
            return False
        amt = D(amount_int)

        try:
            # --- Шаг 1. Списание из quebalance под блокировкой строки ---
            cur_q = D(0)
            new_q = None
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # гарантируем наличие пользователя
                    await conn.execute(
                        "INSERT INTO users (user_id, balance, quebalance) VALUES ($1, 0, '0.00') "
                        "ON CONFLICT (user_id) DO NOTHING" , user_id)
                    # читаем и блокируем строку
                    row = await conn.fetchrow(
                        "SELECT quebalance FROM users WHERE user_id=$1 FOR UPDATE" , user_id)
                    cur_q = _parse_money_text(row [ "quebalance" ] if row else "0.00")
                    if cur_q < amt:
                        print(f"💰 [QUE] transfer_que_to_main: недостаточно средств (есть={cur_q}, нужно={amt})")
                        return False

                    new_q = D(cur_q - amt)
                    await conn.execute(
                        "UPDATE users SET quebalance=$1 WHERE user_id=$2" , _format_money_text(new_q) , user_id)
                    print(f"💰 [QUE] transfer_que_to_main: списано из que {amt} -> остаток={new_q}")

            # --- Шаг 2. Пополнение основного баланса через публичные методы ---
            cur_main = await self.get_user_balance(user_id)
            if cur_main is None:
                # Компенсация: возвращаем в quebalance
                print("💰 [QUE][ERR] transfer_que_to_main: get_user_balance вернул None - откат")
                await self.add_que_balance(user_id , amt)  # best-effort компенсация
                return False

            target_main = D(cur_main) + amt
            ok_update = await self.update_user_balance(user_id , target_main)

            # Некоторые реализации возвращают None вместо True - считаем неуспех только при явном False
            if isinstance(ok_update , bool) and not ok_update:
                print("💰 [QUE][ERR] transfer_que_to_main: update_user_balance=False - откат")
                await self.add_que_balance(user_id , amt)  # вернуть обратно
                return False

            print(f"💰 [QUE] transfer_que_to_main: OK (−{amt} из que => +{amt} в main). Новый main={target_main}")
            return True

        except Exception as e:
            print(f"💰 [QUE][ERR] transfer_que_to_main: {e}")
            # здесь неизвестно, где упали - попытаемся мягко откатить, если списание уже произошло
            try:
                # пробуем вернуть сумму (если до этого списали - add_que_balance просто прибавит)
                await self.add_que_balance(user_id , amt)
                print("💰 [QUE] transfer_que_to_main: компенсация (возврат в que) выполнена")
            except Exception as e2:
                print(f"💰 [QUE][ERR] transfer_que_to_main: компенсация не удалась: {e2}")
            return False

    # ================== TASKS ==================
    async def add_or_update_task(self , chat_ref: str , reward: Decimal) -> bool:
        chat_ref_s = norm_chat_ref(chat_ref)
        try:
            async with self.pool.acquire() as c:
                await c.execute(
                    """
                    INSERT INTO quest_tasks(chat_ref, reward, active)
                    VALUES ($1, $2, TRUE)
                    ON CONFLICT (chat_ref) DO UPDATE
                      SET reward=EXCLUDED.reward, active=TRUE, updated_at=now()
                    """ , chat_ref_s , D(reward))
            return True
        except Exception as e:
            print(f"[ERROR] add_or_update_task: {e}")
            return False

    async def delete_task(self , chat_ref: str) -> bool:
        try:
            async with self.pool.acquire() as c:
                await c.execute("DELETE FROM quest_tasks WHERE chat_ref=$1" , norm_chat_ref(chat_ref))
                return True
        except Exception as e:
            print(f"[ERROR] delete_task: {e}")
            return False

    async def get_task_by_ref(self , chat_ref: str) -> Optional [ Dict ]:
        try:
            async with self.pool.acquire() as c:
                row = await c.fetchrow(
                    """
                    SELECT id, chat_ref, reward, active, total_cap, ttl_expires_at, created_at
                      FROM quest_tasks
                     WHERE chat_ref=$1
                    """ , norm_chat_ref(chat_ref))
                return dict(row) if row else None
        except Exception as e:
            print(f"[ERROR] get_task_by_ref: {e}")
            return None

    async def list_tasks(self , active_only: bool = False) -> List [ Dict ]:
        try:
            async with self.pool.acquire() as c:
                if active_only:
                    rows = await c.fetch(
                        """
                        SELECT qt.id, qt.chat_ref, qt.reward, qt.active, qt.total_cap, qt.ttl_expires_at, qt.created_at
                          FROM quest_tasks qt
                         WHERE qt.active = TRUE
                           AND (qt.ttl_expires_at IS NULL OR qt.ttl_expires_at > now())
                           AND (
                             qt.total_cap IS NULL
                             OR (
                                  SELECT COUNT(*) FROM quest_done qd
                                   WHERE qd.chat_ref = qt.chat_ref AND qd.action='sub'
                                ) < qt.total_cap
                           )
                         ORDER BY qt.id
                        """)
                else:
                    rows = await c.fetch(
                        """
                        SELECT id, chat_ref, reward, active, total_cap, ttl_expires_at, created_at
                          FROM quest_tasks
                         ORDER BY id
                        """)
                return [ dict(r) for r in rows ]
        except Exception as e:
            print(f"[ERROR] list_tasks: {e}")
            return [ ]

    async def cleanup_tasks(self , hard_delete: bool = False) -> Dict [ str , int ]:
        out = {"deactivated": 0 , "deleted": 0}
        try:
            async with self.pool.acquire() as c:
                r1 = await c.fetchrow(
                    """
                    WITH to_close AS (
                      SELECT id
                        FROM quest_tasks qt
                       WHERE qt.active = TRUE
                         AND (
                             (qt.ttl_expires_at IS NOT NULL AND qt.ttl_expires_at <= now())
                          OR (qt.total_cap IS NOT NULL AND (
                               SELECT COUNT(*) FROM quest_done qd
                                WHERE qd.chat_ref=qt.chat_ref AND qd.action='sub'
                             ) >= qt.total_cap)
                         )
                    ),
                    upd AS (
                      UPDATE quest_tasks q
                         SET active = FALSE, updated_at = now()
                       WHERE q.id IN (SELECT id FROM to_close)
                       RETURNING 1
                    )
                    SELECT COUNT(*) AS cnt FROM upd
                    """)
                out [ "deactivated" ] = int(r1 [ "cnt" ] if r1 and r1 [ "cnt" ] is not None else 0)

                if hard_delete:
                    r2cnt = await c.fetchrow(
                        """
                        SELECT COUNT(*) AS cnt
                          FROM quest_tasks
                         WHERE active = FALSE
                           AND ttl_expires_at IS NOT NULL
                           AND ttl_expires_at <= now()
                        """)
                    del_cnt = int(r2cnt [ "cnt" ] if r2cnt and r2cnt [ "cnt" ] is not None else 0)
                    if del_cnt > 0:
                        await c.execute(
                            """
                            DELETE FROM quest_tasks
                             WHERE active = FALSE
                               AND ttl_expires_at IS NOT NULL
                               AND ttl_expires_at <= now()
                            """)
                    out [ "deleted" ] = del_cnt
            return out
        except Exception as e:
            print(f"[ERROR] cleanup_tasks: {e}")
            return out

    async def refresh_task_activity(self , chat_ref: str) -> bool:
        cref = norm_chat_ref(chat_ref)
        try:
            async with self.pool.acquire() as c:
                await c.execute(
                    """
                    UPDATE quest_tasks qt
                       SET active = (
                            (qt.ttl_expires_at IS NULL OR qt.ttl_expires_at > now())
                        AND (qt.total_cap IS NULL OR (
                              SELECT COUNT(*) FROM quest_done qd
                               WHERE qd.chat_ref = qt.chat_ref AND qd.action='sub'
                            ) < qt.total_cap)
                       ),
                           updated_at = now()
                     WHERE qt.chat_ref = $1
                    """ , cref)
            return True
        except Exception as e:
            print(f"[ERROR] refresh_task_activity: {e}")
            return False
    # ============== DONE / идемпотентность ==============
    async def get_done_refs_for_user(self , user_id: int , refs_iter: Iterable) -> Set [ str ]:
        refs = [ norm_chat_ref(r) for r in refs_iter ]
        if not refs:
            return set()
        async with self.pool.acquire() as c:
            rows = await c.fetch(
                "SELECT chat_ref FROM quest_done WHERE user_id=$1 AND chat_ref = ANY($2::text[])" , user_id , refs)
            return {r [ "chat_ref" ] for r in rows}

    async def is_task_done(self , user_id: int , chat_ref: Union [ str , int ]) -> bool:
        cref = norm_chat_ref(chat_ref)
        try:
            async with self.pool.acquire() as c:
                row = await c.fetchrow(
                    "SELECT 1 FROM quest_done WHERE user_id=$1 AND chat_ref=$2" , user_id , cref)
                return bool(row)
        except Exception as e:
            print(f"[ERROR] is_task_done: {e}")
            return False

    async def claim_task_reward_once(self , user_id: int , chat_ref: Union [ str , int ] , reward: Decimal) -> bool:
        """
        True - только если реально зачислили (вставили в quest_done и увеличили users.quebalance).
        Вся математика по quebalance - в Python.
        """
        cref = norm_chat_ref(chat_ref)
        r = D(reward)
        try:
            async with self.pool.acquire() as c:
                async with c.transaction():
                    inserted = await c.fetchval(
                        """
                        INSERT INTO quest_done (user_id, chat_ref, action, reward)
                        VALUES ($1, $2, 'sub', $3)
                        ON CONFLICT (user_id, chat_ref) DO NOTHING
                        RETURNING 1
                        """ , user_id , cref , r)
                    if not inserted:
                        return False  # уже было - ничего не делаем

                    # гарантируем пользователя
                    await c.execute(
                        "INSERT INTO users (user_id, balance, quebalance) VALUES ($1, 0, '0.00') "
                        "ON CONFLICT (user_id) DO NOTHING" , user_id)

                    # атомарно прибавляем (TEXT)
                    row = await c.fetchrow(
                        "SELECT quebalance FROM users WHERE user_id=$1 FOR UPDATE" , user_id)
                    cur = _parse_money_text(row [ "quebalance" ] if row else "0.00")
                    new_val = D(cur + r)
                    await c.execute(
                        "UPDATE users SET quebalance=$1 WHERE user_id=$2" , _format_money_text(new_val) , user_id)
                    print(f"[QUESTDBG] DB: claim_task_reward_once -> {cur} + {r} = {new_val}")
                    return True
        except Exception as e:
            print(f"[ERROR] claim_task_reward_once: {e}")
            return False

    async def skip_task_once(self , user_id: int , chat_ref: Union [ str , int ] , cost: Decimal) -> bool:
        """
        Пропуск задания - списываем стоимость из quebalance (TEXT) только один раз.
        """
        cref = norm_chat_ref(chat_ref)
        cst = D(cost)
        try:
            async with self.pool.acquire() as c:
                async with c.transaction():
                    # уже закрыто?
                    got = await c.fetchrow(
                        "SELECT 1 FROM quest_done WHERE user_id=$1 AND chat_ref=$2" , user_id , cref)
                    if got:
                        return True

                    # гарантируем пользователя
                    await c.execute(
                        "INSERT INTO users (user_id, balance, quebalance) VALUES ($1, 0, '0.00') "
                        "ON CONFLICT (user_id) DO NOTHING" , user_id)

                    # проверяем средства и списываем под блокировкой
                    row = await c.fetchrow(
                        "SELECT quebalance FROM users WHERE user_id=$1 FOR UPDATE" , user_id)
                    cur = _parse_money_text(row [ "quebalance" ] if row else "0.00")
                    if cur < cst:
                        return False
                    new_val = D(cur - cst)
                    await c.execute(
                        "UPDATE users SET quebalance=$1 WHERE user_id=$2" , _format_money_text(new_val) , user_id)

                    # фиксируем skip (идемпотентно)
                    await c.execute(
                        """
                        INSERT INTO quest_done (user_id, chat_ref, action, reward)
                        VALUES ($1, $2, 'skip', 0)
                        ON CONFLICT (user_id, chat_ref) DO NOTHING
                        """ , user_id , cref)
                    return True
        except Exception as e:
            print(f"[ERROR] skip_task_once: {e}")
            return False

    # ================== статистика ==================
    async def stats_for_task(self , chat_ref: str) -> Dict [ str , Any ]:
        cref = norm_chat_ref(chat_ref)
        try:
            async with self.pool.acquire() as c:
                row_clicks = await c.fetchrow(
                    """
                    SELECT COUNT(DISTINCT qc.user_id) AS clicks
                    FROM quest_clicks qc
                    JOIN quest_tasks qt ON qt.id = qc.task_id
                    WHERE qt.chat_ref=$1
                    """ , cref)
                row_subs = await c.fetchrow(
                    """
                    SELECT COUNT(*) AS subs, COALESCE(SUM(reward),0) AS reward_total
                    FROM quest_done
                    WHERE chat_ref=$1 AND action='sub'
                    """ , cref)
                row_skips = await c.fetchrow(
                    """
                    SELECT COUNT(*) AS skips
                    FROM quest_done
                    WHERE chat_ref=$1 AND action='skip'
                    """ , cref)
                return {"clicks": int(
                    row_clicks [ "clicks" ] if row_clicks and row_clicks [ "clicks" ] is not None else 0) ,
                    "subs": int(row_subs [ "subs" ] if row_subs and row_subs [ "subs" ] is not None else 0) ,
                    "reward_total": D(
                        row_subs [ "reward_total" ] if row_subs and row_subs [
                            "reward_total" ] is not None else 0) , "skips": int(
                        row_skips [ "skips" ] if row_skips and row_skips [ "skips" ] is not None else 0) , }
        except Exception as e:
            print(f"[ERROR] stats_for_task: {e}")
            return {"clicks": 0 , "subs": 0 , "reward_total": D(0) , "skips": 0}

    async def set_task_caps_and_expiry(self , chat_ref: str , total_cap: Optional [ int ] = None ,
            expires_at: Optional [ dt.datetime ] = None , * , exclusive: bool = False ,
            # ВАЖНО: если True - второй параметр очищается (взаимоисключающие режимы)
    ) -> bool:
        cref = norm_chat_ref(chat_ref)
        try:
            async with self.pool.acquire() as c:
                if exclusive:
                    # если задаём кап - чистим TTL; если задаём TTL - чистим кап
                    if total_cap is not None:
                        await c.execute(
                            """
                            UPDATE quest_tasks
                               SET total_cap      = $2,
                                   ttl_expires_at = NULL,
                                   updated_at     = now()
                             WHERE chat_ref = $1
                            """ , cref , int(total_cap))
                    elif expires_at is not None:
                        await c.execute(
                            """
                            UPDATE quest_tasks
                               SET ttl_expires_at = $2,
                                   total_cap      = NULL,
                                   updated_at     = now()
                             WHERE chat_ref = $1
                            """ , cref , expires_at)
                    else:
                        # exclusive=True, но ничего не задано - нет операции
                        pass
                else:
                    await c.execute(
                        """
                        UPDATE quest_tasks
                           SET total_cap      = COALESCE($2, total_cap),
                               ttl_expires_at = COALESCE($3, ttl_expires_at),
                               updated_at     = now()
                         WHERE chat_ref = $1
                        """ , cref , total_cap , expires_at)
            await self.refresh_task_activity(cref)
            return True
        except Exception as e:
            if "column" in str(e).lower() and ("ttl_expires_at" in str(e) or "total_cap" in str(e)):
                await self._ensure_caps_columns()
                return await self.set_task_caps_and_expiry(
                    chat_ref , total_cap=total_cap , expires_at=expires_at , exclusive=exclusive)
            print(f"[ERROR] set_task_caps_and_expiry: {e}")
            return False



    async def task_capacity_snapshot_total(self , chat_refs: List [ str ]) -> Dict [
        str , Dict [ str , Optional [ int ] ] ]:
        if not chat_refs:
            return {}
        refs = [ norm_chat_ref(r) for r in chat_refs ]
        try:
            async with self.pool.acquire() as c:
                rows = await c.fetch(
                    """
                    WITH total AS (
                      SELECT chat_ref, COUNT(*)::int AS used
                        FROM quest_done
                       WHERE action='sub' AND chat_ref = ANY($1::text[])
                       GROUP BY chat_ref
                    )
                    SELECT qt.chat_ref, qt.total_cap, qt.ttl_expires_at, qt.active,
                           COALESCE(t.used, 0) AS total_used
                      FROM quest_tasks qt
                      LEFT JOIN total t ON t.chat_ref = qt.chat_ref
                     WHERE qt.chat_ref = ANY($1::text[])
                    """ , refs)
            out: Dict [ str , Dict [ str , Optional [ int ] ] ] = {}
            now = dt.datetime.now(dt.timezone.utc)
            for r in rows:
                total_cap = r [ "total_cap" ]
                ttl_expires = r [ "ttl_expires_at" ]
                active = bool(r [ "active" ])
                total_used = int(r [ "total_used" ] or 0)

                rem_total = None if total_cap is None else max(total_cap - total_used , 0)
                not_expired = (ttl_expires is None) or (ttl_expires > now)
                joinable = active and not_expired and (rem_total is None or rem_total > 0)

                out [ r [ "chat_ref" ] ] = {"total_cap": total_cap , "total_used": total_used ,
                    "remaining_total": rem_total , "expires_at": ttl_expires ,  # dt|None
                    "active": active , "joinable": joinable , }
            return out
        except Exception as e:
            print(f"[ERROR] task_capacity_snapshot_total: {e}")
            return {}

    async def claim_task_reward_once_capped_expiry(self , user_id: int , chat_ref , reward: Decimal) -> Tuple [
        bool , str ]:
        """
        Возвращает (ok, code):
          ok=True  -> ('ok')
          ok=False -> 'already' | 'not_active' | 'expired' | 'cap_total' | 'error'
        """
        cref = norm_chat_ref(chat_ref)
        r = D(reward)
        try:
            async with self.pool.acquire() as c:
                async with c.transaction():
                    q = await c.fetchrow(
                        "SELECT id, active, total_cap, ttl_expires_at FROM quest_tasks WHERE chat_ref=$1 FOR UPDATE" ,
                        cref)
                    if not q or not q [ "active" ]:
                        return (False , "not_active")

                    now = dt.datetime.now(dt.timezone.utc)
                    exp = q [ "ttl_expires_at" ]
                    if exp is not None and exp <= now:
                        await c.execute(
                            "UPDATE quest_tasks SET active=FALSE, updated_at=now() WHERE id=$1" , q [ "id" ])
                        return (False , "expired")

                    existed = await c.fetchrow(
                        "SELECT 1 FROM quest_done WHERE user_id=$1 AND chat_ref=$2" , user_id , cref)
                    if existed:
                        return (False , "already")

                    total_cap = q [ "total_cap" ]
                    if total_cap is not None:
                        total_used = await c.fetchval(
                            "SELECT COUNT(*) FROM quest_done WHERE chat_ref=$1 AND action='sub'" , cref)
                        if (int(total_used or 0) + 1) > int(total_cap):
                            await c.execute(
                                "UPDATE quest_tasks SET active=FALSE, updated_at=now() WHERE id=$1" , q [ "id" ])
                            return (False , "cap_total")

                    inserted = await c.fetchval(
                        """
                        INSERT INTO quest_done (user_id, chat_ref, action, reward)
                        VALUES ($1, $2, 'sub', $3)
                        RETURNING 1
                        """ , user_id , cref , r)
                    if not inserted:
                        return (False , "error")

                    await c.execute(
                        "INSERT INTO users (user_id, balance, quebalance) VALUES ($1, 0, '0.00') "
                        "ON CONFLICT (user_id) DO NOTHING" , user_id)

                    row = await c.fetchrow("SELECT quebalance FROM users WHERE user_id=$1 FOR UPDATE" , user_id)
                    cur = _parse_money_text(row [ "quebalance" ] if row else "0.00")
                    new_val = D(cur + r)
                    await c.execute(
                        "UPDATE users SET quebalance=$1 WHERE user_id=$2" , _format_money_text(new_val) , user_id)

                    # если кап выбит после текущего зачёта - деактивируем сразу
                    if total_cap is not None:
                        total_used2 = await c.fetchval(
                            "SELECT COUNT(*) FROM quest_done WHERE chat_ref=$1 AND action='sub'" , cref)
                        if int(total_used2 or 0) >= int(total_cap):
                            await c.execute(
                                "UPDATE quest_tasks SET active=FALSE, updated_at=now() WHERE id=$1" , q [ "id" ])

                    return (True , "ok")
        except Exception as e:
            print(f"[ERROR] claim_task_reward_once_capped_expiry: {e}")
            return (False , "error")

    # ✅ 2. Проверка, использовал ли пользователь промокод
    async def has_user_used_promo(self , user_id: int , promo_code: str) -> bool:
        try:
            async with self.pool.acquire() as connection:
                query = """
                    SELECT 1 FROM promocodeusers
                    WHERE user_id = $1 AND LOWER(promo) = LOWER($2)
                """
                result = await connection.fetchval(query , user_id , promo_code.lower())
                return result is not None
        except Exception as e:
            print(f"[ERROR] Ошибка при проверке использования промокода: {e}")
            return True

    # ✅ 3. Добавить пользователя к использовавшим промокод
    async def add_user_to_promo_users(self , user_id: int , promo_code: str):
        try:
            async with self.pool.acquire() as connection:
                query = """
                    INSERT INTO promocodeusers (user_id, promo, data)
                    VALUES ($1, LOWER($2), $3)
                """
                await connection.execute(query , user_id , promo_code.lower() , datetime.now())
        except Exception as e:
            print(f"[ERROR] Ошибка при добавлении пользователя в таблицу promocodeusers: {e}")

    # ✅ 4. Уменьшить счётчик промокода или удалить его
    async def decrement_promo_count_or_delete(self , promo_code: str):
        promo_code_lower = promo_code.lower()
        try:
            async with self.pool.acquire() as connection:
                query_get = "SELECT count FROM promocode WHERE LOWER(promo) = LOWER($1)"
                promo = await connection.fetchrow(query_get , promo_code_lower)

                if promo:
                    count = promo [ "count" ]
                    if count > 1:
                        query_update = "UPDATE promocode SET count = count - 1 WHERE LOWER(promo) = LOWER($1)"
                        await connection.execute(query_update , promo_code_lower)
                    else:
                        async with connection.transaction():
                            query_delete_promo = "DELETE FROM promocode WHERE LOWER(promo) = LOWER($1)"
                            query_delete_users = "DELETE FROM promocodeusers WHERE LOWER(promo) = LOWER($1)"
                            await connection.execute(query_delete_promo , promo_code_lower)
                            await connection.execute(query_delete_users , promo_code_lower)
                            print(f"[INFO] Промокод {promo_code_lower} и связанные пользователи были удалены.")
        except Exception as e:
            print(f"[ERROR] Ошибка при обновлении/удалении промокода: {e}")

    # ✅ 5. Удалить промокод вручную
    async def delete_promocode(self , promo_code: str):
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(
                        "DELETE FROM promocode WHERE LOWER(promo) = LOWER($1)" , promo_code.lower())
                    await connection.execute(
                        "DELETE FROM promocodeusers WHERE LOWER(promo) = LOWER($1)" , promo_code.lower())
                    print(f"[INFO] Промокод {promo_code.lower()} и связанные записи пользователей успешно удалены.")
        except Exception as e:
            print(f"[ERROR] Ошибка при удалении промокода {promo_code}: {e}")

    # ✅ 6. Получить все промокоды с количеством использований
    async def get_all_promocodes_with_usage(self):
        try:
            async with self.pool.acquire() as connection:
                query = """
                    SELECT
                        p.promo,
                        p.count,
                        (SELECT COUNT(*) FROM promocodeusers pu WHERE LOWER(pu.promo) = LOWER(p.promo)) AS used_count
                    FROM promocode p
                """
                rows = await connection.fetch(query)
                return rows
        except Exception as e:
            print(f"[ERROR] Ошибка при получении списка промокодов из БД: {e}")
            return [ ]

    # ✅ 7. Добавить новый промокод
    async def add_promocode_to_db(self , promo_code: str , max_price: float , max_count: int , price_per_user: float ,
                                  chat_id: int):
        try:
            async with self.pool.acquire() as connection:
                now = datetime.now()
                query = """
                    INSERT INTO promocode (promo, count, maxcount, priceonone, maxprice, data, chat_id)
                    VALUES (LOWER($1), $2, $3, $4, $5, $6, $7)
                """
                await connection.execute(
                    query , promo_code.lower() , max_count , max_count , price_per_user , max_price , now , chat_id)
        except Exception as e:
            print(f"[ERROR] Ошибка при записи промокода в БД: {e}")











    async def get_connection_stats(self):
        """
        Возвращает статистику о текущих соединениях и нагрузке на пул.
        """
        if not self.pool:
            print("[ERROR] Пул соединений не инициализирован.")
            return None

        try:
            async with self.pool.acquire() as connection:
                stats = await connection.fetch('SELECT * FROM pg_stat_activity')
                active_connections = len([s for s in stats if s['state'] == 'active'])
                idle_connections = len([s for s in stats if s['state'] == 'idle'])

            # Примерные значения min_size и max_size для пула


            return {
                "total_connections": len(stats),
                "active_connections": active_connections,
                "idle_connections": idle_connections,
                "min_connections": min_connections,
                "max_connections": max_connections
            }
        except Exception as e:
            print(f"[ERROR] Ошибка при получении статистики соединений: {e}")
            return None

    async def print_connection_stats(self , message: types.Message):
        """
        Отправляет статистику соединений в компактной и понятной форме.
        """
        stats = await self.get_connection_stats()
        if stats:
            text = ("<b>🌐 Статистика соединений</b>\n"
                    f"🔗 Всего: <b>{stats [ 'total_connections' ]}</b>\n"
                    f"⚡ Активные: <b>{stats [ 'active_connections' ]}</b>\n"
                    f"⏸️ Неактивные: <b>{stats [ 'idle_connections' ]}</b>\n"
                    f"🔽 Мин. в пуле: <b>{stats [ 'min_connections' ]}</b>\n"
                    f"🔼 Макс. в пуле: <b>{stats [ 'max_connections' ]}</b>")
            await message.reply(text , parse_mode="HTML")




    async def check_and_update_stata(self , chat_id: int):
        """Проверка значения stata и обновление его на 0, если оно равно 1."""
        try:
            async with self.pool.acquire() as connection:
                current_stata = await connection.fetchval(
                    "SELECT stata FROM chat WHERE chat_id = $1" , chat_id)
                if current_stata == 1:
                    await connection.execute(
                        "UPDATE chat SET stata = 0 WHERE chat_id = $1" , chat_id)
                    print(f"Статус stata обновлён на 0 для chat_id {chat_id}")
                else:
                    print(f"Значение stata не требует обновления для chat_id {chat_id}")
        except Exception as e:
            print(f"Ошибка при проверке/обновлении stata: {e}")

    async def check_and_set_stata_to_one(self , chat_id: int):
        """Проверка значения stata и обновление его на 1, если оно равно 0."""
        try:
            async with self.pool.acquire() as connection:
                current_stata = await connection.fetchval(
                    "SELECT stata FROM chat WHERE chat_id = $1" , chat_id)
                if current_stata == 0:
                    await connection.execute(
                        "UPDATE chat SET stata = 1 WHERE chat_id = $1" , chat_id)
                    print(f"Статус stata обновлён на 1 для chat_id {chat_id}")
                else:
                    print(f"Значение stata уже равно 1 или не требует обновления для chat_id {chat_id}")
        except Exception as e:
            print(f"Ошибка при обновлении stata: {e}")

    async def get_current_stata(self , chat_id: int):
        """Получение текущего значения stata по chat_id."""
        try:
            async with self.pool.acquire() as connection:
                current_stata = await connection.fetchval(
                    "SELECT stata FROM chat WHERE chat_id = $1" , chat_id)
                print(f"Текущее значение stata для chat_id {chat_id}: {current_stata}")
                return current_stata
        except Exception as e:
            print(f"Ошибка при получении значения stata: {e}")
            return None

    async def get_group_creator(self , chat_id: int):
        """Получение creator_id (создателя группы) по chat_id из таблицы chat."""
        try:
            async with self.pool.acquire() as connection:
                creator_id = await connection.fetchval(
                    "SELECT creator_id FROM chat WHERE chat_id = $1" , chat_id)
                if creator_id is not None:
                    print(f"👑 Создатель группы: {creator_id}")
                else:
                    print(f"❗Создатель не найден для chat_id {chat_id}")
                return creator_id
        except Exception as e:
            print(f"Ошибка при получении creator_id: {e}")
            return None

    async def get_random_user_with_min_referrals(self , min_referrals: int = 5) -> Optional [ int ]:
        """
        Получение случайного user_id пользователя,
        у которого количество рефералов >= min_referrals.
        """
        try:
            async with self.pool.acquire() as connection:
                user_id = await connection.fetchval(
                    """
                    SELECT user_id
                      FROM users
                     WHERE refferals >= $1
                  ORDER BY RANDOM()
                     LIMIT 1
                    """ , min_referrals)

                if user_id is not None:
                    print(f"🎲 Выбран пользователь: {user_id}")
                else:
                    print(f"❗ Нет пользователей с referrals >= {min_referrals}")

                return user_id

        except Exception as e:
            print(f"Ошибка при получении случайного user_id: {e}")
            return None

    async def add_donation(self , user_id: int , amount: Union [ int , float , Decimal ] ,
            bonus_percent: Decimal = Decimal('0.03') , bonus: Optional [ Decimal ] = None) -> Tuple [
        Decimal , Decimal , Decimal ]:
        """
        Добавляет донат пользователю.
        Возвращает (new_donate, new_canwithdrawal, bonus_used).
        """
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError(f"Некорректная сумма доната: {amount}")

        # Вычисляем или используем переданный бонус
        if bonus is None:
            bonus = (amount * bonus_percent).quantize(Decimal('0.01') , rounding=ROUND_HALF_UP)
        else:
            bonus = Decimal(str(bonus)).quantize(Decimal('0.01') , rounding=ROUND_HALF_UP)
            expected_bonus = (amount * bonus_percent).quantize(Decimal('0.01') , rounding=ROUND_HALF_UP)
            if abs(bonus - expected_bonus) > Decimal('0.01'):
                print(f"⚠️ [DB] Переданный бонус {bonus} != ожидаемому {expected_bonus} – использую переданный")

        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    query_update = """
                        UPDATE users
                        SET 
                            donate = COALESCE(donate, 0) + $1::numeric,
                            canwithdrawal = COALESCE(canwithdrawal, 0) + $2::numeric
                        WHERE user_id = $3
                        RETURNING donate, canwithdrawal
                    """
                    row = await connection.fetchrow(query_update , amount , bonus , user_id)

                    if row is None:
                        raise ValueError(f"Пользователь user_id={user_id} не найден")

                    new_donate = row [ 'donate' ]
                    new_canwithdrawal = row [ 'canwithdrawal' ]

                    # Логируем донат в историю
                    current_time = datetime.now()
                    query_insert = """
                        INSERT INTO public.donate (user_id, count, data)
                        VALUES ($1, $2::numeric, $3)
                    """
                    await connection.execute(query_insert , user_id , amount , current_time)

                    print(
                        f"✅ [DB] Донат записан: user={user_id}, amount={amount}, bonus={bonus}, "
                        f"new_donate={new_donate}, new_limit={new_canwithdrawal}")

                    return new_donate , new_canwithdrawal , bonus

        except Exception as e:
            print(f"❌ [DB] Ошибка при обновлении donate для user_id={user_id}: {e}")
            raise

















    async def remove_marriage_request(self , user_id , partner_id):
        """Удаляет запрос на брак и делает его неактивным в базе данных."""
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        # Удаляем пользователя из списка запросов
        if user_id in user_request_time:
            del user_request_time [ user_id ]

        async with self.pool.acquire() as connection:
            status = await connection.fetchval(
                """
                SELECT status FROM marriages 
                WHERE (user_id1 = $1 AND user_id2 = $2) 
                   OR (user_id1 = $2 AND user_id2 = $1)
                """ , user_id , partner_id)

        if status == 0:
            async with self.pool.acquire() as connection:
                await connection.execute(
                    """
                    DELETE FROM marriages 
                    WHERE (user_id1 = $1 AND user_id2 = $2) 
                       OR (user_id1 = $2 AND user_id2 = $1)
                    """ , user_id , partner_id)
            return True
        return False

    async def is_married(self , user_id):
        """Проверяет, состоит ли пользователь в браке в базе данных PostgreSQL."""
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        # Запрос для проверки статуса брака пользователя
        query = """
        SELECT status FROM marriages WHERE user_id1 = $1 OR user_id2 = $1
        """

        async with self.pool.acquire() as connection:
            marriage_status = await connection.fetchrow(query , user_id)

        # Возвращаем True, если статус брака равен 1 (в браке), иначе False
        return marriage_status and marriage_status [ 'status' ] == 1

    async def invite_to_marriage(self , message: Message , partner_id: int , comment: str = ""):
        """Отправляет запрос на брак с проверкой времени между заявками."""
        current_datetime = datetime.now()
        user_id = message.from_user.id

        if user_id in user_request_time:
            last_request_time = user_request_time [ user_id ]
            time_diff = (current_datetime - last_request_time).total_seconds()
            if time_diff < 30:
                time_left = 30 - time_diff
                await message.reply(
                    f"⚠️ <b>Подождите {int(time_left)} секунд перед следующим запросом.</b>" ,
                    parse_mode="HTML")
                return

        async with self.pool.acquire() as connection:
            row = await connection.fetchrow("SELECT first_name, username FROM users WHERE user_id = $1" , partner_id)

        partner_first_name = row [ "first_name" ] if row else f"Пользователь с ID {partner_id}"
        partner_username = row [ "username" ] if row else ""

        async with self.pool.acquire() as connection:
            existing_request = await connection.fetchrow(
                "SELECT * FROM marriages WHERE (user_id1 = $1 AND user_id2 = $2) OR (user_id1 = $2 AND user_id2 = $1)" ,
                message.from_user.id , partner_id)

        if not existing_request:
            async with self.pool.acquire() as connection:
                await connection.execute(
                    "INSERT INTO marriages (user_id1, user_id2, status, datetime, chat_id) VALUES ($1, $2, 0, $3, $4)" ,
                    message.from_user.id , partner_id , current_datetime , message.chat.id)

            send_request_pm_button = InlineKeyboardButton(
                text='💬 Отправить запрос в лс' , callback_data=f'smarriageend_request_pm_{partner_id}')

            # Создание клавиатуры
            keyboard = InlineKeyboardMarkup(inline_keyboard=[ ])

            # Если чат не является личным, добавляем кнопки согласия и отказа
            if message.chat.type != "private":
                accept_button = InlineKeyboardButton(text='🌹 Согласиться' , callback_data='accept')
                reject_button = InlineKeyboardButton(text='🥀 Отказать' , callback_data='reject')

                # Добавляем кнопки согласия и отказа в одну строку
                keyboard.inline_keyboard.append([ reject_button , accept_button ])

            # Кнопка для отмены
            cancel_button = InlineKeyboardButton(text=f'✖️' , callback_data=f'marriageclosemessage_{partner_id}')

            # Добавляем кнопки в нужные строки
            keyboard.inline_keyboard.append([ send_request_pm_button ])  # Отдельная строка для кнопки запроса в ЛС
            keyboard.inline_keyboard.append([ cancel_button ])  # Кнопка отмены в отдельной строке

            proposal_message = None
            try:
                first_name = await self.get_firstname_by_user_id(partner_id)
                username = await self.get_username_by_id(partner_id)
                name_link111 = await create_user_link(partner_id , first_name , username)

                user_id_name_link111 = message.from_user.id
                first_name1 = await self.get_firstname_by_user_id(user_id_name_link111)
                username1 = await self.get_username_by_id(user_id_name_link111)
                name_link1111 = await create_user_link(user_id_name_link111 , first_name1 , username1)

                randommessagemarriage = random.choice(
                    [ f"💍 <b>{name_link111}, внимание!</b>\n🕊 <b>{name_link1111} предложил(-а) вам руку и сердце</b>" ,
                        f"💍 <b>{name_link111}, минуточку!</b>\n🕊 <b>{name_link1111} предлагает вам руку и сердце</b>" ,
                        f"💍 <b>{name_link111}, секунду!</b>\n🕊 <b>{name_link1111} дарит вам руку и сердце</b>" ,
                        f"💍 <b>{name_link111}, слушайте!</b>\n🕊 <b>{name_link1111} сделал(-а) вам предложение</b>" ,
                        f"💍 <b>{name_link111}, внимание!</b>\n🕊 <b>{name_link1111} зовёт вас в брак</b>" , ])
                if comment:
                    randommessagemarriage += f"\n💬 <b>{comment}</b>"


                proposal_message = await message.bot.send_message(
                    message.chat.id , randommessagemarriage , disable_web_page_preview=True ,
                    parse_mode="HTML" , reply_markup=keyboard)
            except Exception as e:
                print(f"Failed to send message: {e}")

            user_request_time [ user_id ] = current_datetime
            await asyncio.sleep(30)

            if user_id in user_request_time:
                del user_request_time [ user_id ]

            async with self.pool.acquire() as connection:
                status = await connection.fetchval(
                    "SELECT status FROM marriages WHERE (user_id1 = $1 AND user_id2 = $2) OR (user_id1 = $2 AND user_id2 = $1)" ,
                    message.from_user.id , partner_id)

            if status == 0:
                async with self.pool.acquire() as connection:
                    await connection.execute(
                        "DELETE FROM marriages WHERE (user_id1 = $1 AND user_id2 = $2) OR (user_id1 = $2 AND user_id2 = $1)" ,
                        message.from_user.id , partner_id)
                if proposal_message:
                    await message.bot.delete_message(message.chat.id , proposal_message.message_id)

    async def check_user_marriage_status34123412(self , user_id):
        """Проверяет, находится ли пользователь в браке."""
        async with self.pool.acquire() as connection:
            # Запрос для проверки статуса брака
            user_info = await connection.fetchrow(
                "SELECT status, user_id1, user_id2 FROM marriages WHERE user_id1 = $1 OR user_id2 = $1" , user_id)

        # Если информация о браке найдена
        if user_info:
            if user_info [ "status" ] == 1:
                # Брак активен
                return True
            else:
                # Брак не активен
                return False
        else:
            # Пользователь не состоит в браке
            return False

    async def delete_unfinished_marriages(self):
        try:
            async with self.pool.acquire() as connection:
                # Получаем все записи со статусом 0
                result = await connection.fetch("SELECT datetime, user_id1, user_id2 FROM marriages WHERE status = 0")

                current_time = datetime.now()  # Текущее время

                for row in result:
                    marriage_time = row [ 'datetime' ]
                    marriage_time = marriage_time.replace(tzinfo=None)

                    if current_time - marriage_time > timedelta(seconds=30):
                        # Удаляем запись с учетом возможных NULL значений
                        await connection.execute(
                            """
                            DELETE FROM marriages
                            WHERE status = 0
                            AND ((user_id1 = $1 OR (user_id1 IS NULL AND $1 IS NULL))
                            AND (user_id2 = $2 OR (user_id2 IS NULL AND $2 IS NULL)))
                            """ , row [ 'user_id1' ] , row [ 'user_id2' ])
                        print(f"Удалена заявка на брак с user_id1 {row [ 'user_id1' ]} и user_id2 {row [ 'user_id2' ]}")

                print("🧹 Все незавершённые заявки на брак удалены.")
        except Exception as e:
            print(f"Ошибка при удалении браков при завершении: {e}")
    async def divorce(self , message: Message , user_id: int):
        """Разводит пользователя."""
        async with self.pool.acquire() as connection:
            user_info = await connection.fetchrow(
                "SELECT status, user_id1, user_id2 FROM marriages WHERE user_id1 = $1 OR user_id2 = $1" , user_id)

        if user_info:
            if user_info [ "status" ] == 1:
                partner_id = user_info [ "user_id1" ] if user_info [ "user_id1" ] != user_id else user_info [
                    "user_id2" ]
                async with self.pool.acquire() as connection:
                    await connection.execute(
                        "DELETE FROM marriages WHERE (user_id1 = $1 AND user_id2 = $2) OR (user_id1 = $2 AND user_id2 = $1)" ,
                        user_id , partner_id)
                async with self.pool.acquire() as connection:
                    partner_info = await connection.fetchrow(
                        "SELECT username, first_name FROM users WHERE user_id = $1" , partner_id)

                partner_name = partner_info [ "first_name" ] if partner_info else "Unknown"
                user_id_name_link111 = message.from_user.id
                first_name1 = await self.get_firstname_by_user_id(partner_id)
                username1 = await self.get_username_by_id(partner_id)
                name_link1111 = await create_user_link(partner_id , first_name1 , username1)

                randommessagemarriage = random.choice ([
                    f"💔 <b>Вы развелись с {name_link1111}</b>",
                    f"💔 <b>Вы расстались с {name_link1111}</b>",
                    f"💔 <b>Вы разошлись с {name_link1111}</b>",
                    f"💔 <b>С {name_link1111} все завершено</b>",
                    f"💔 <b>Вы прекратили отношения с {name_link1111}</b>"

                    ])
                await message.edit_text(randommessagemarriage,disable_web_page_preview=True , parse_mode="HTML")

                user_id_name_link111 = user_id
                first_name1 = await self.get_firstname_by_user_id(user_id_name_link111)
                username1 = await self.get_username_by_id(user_id_name_link111)
                name_link1111 = await create_user_link(user_id_name_link111 , first_name1 , username1)

                randommessagemarriage3412 = random.choice ([
                    f"💔 <b>{name_link1111} завершил(-а) ваш брак</b>",
                    f"💔 <b>{name_link1111} принял(-а) решение развестись с вами</b>",
                    f"💔 <b>{name_link1111} разорвал(-а) отношения с вами</b>",
                    f"💔 <b>{name_link1111} закончил(-а) ваш брак</b>"
                ])

                await message.bot.send_message(
                    partner_id , randommessagemarriage3412 , disable_web_page_preview=True , parse_mode="HTML")
            else:
                await message.edit_text("🥀 <b>Вы не находитесь в браке</b>", disable_web_page_preview=True , parse_mode="HTML")
        else:
            await message.edit_text("🥀 <b>Вы не находитесь в браке</b>", disable_web_page_preview=True , parse_mode="HTML")

    async def get_partner_data(self, partner_id):
        async with self.pool.acquire() as connection:
            return await connection.fetchrow("SELECT username, first_name FROM users WHERE user_id = $1", partner_id)

    async def get_marriage_info(self, user_id):
        async with self.pool.acquire() as connection:
            return await connection.fetchrow("SELECT user_id1, user_id2, status, datetime FROM marriages WHERE user_id1 = $1 OR user_id2 = $1", user_id)



    async def get_partner_info_for_accept(self , user_id):
        """Получить информацию о партнере для принятия предложения брака."""
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(
                "SELECT user_id1, chat_id FROM marriages WHERE user_id2 = $1 AND status = 0" , user_id)

    async def update_marriage_status(self , user_id):
        """Обновить статус брака для принятия предложения."""
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")
        async with self.pool.acquire() as connection:
            await connection.execute(
                "UPDATE marriages SET status = 1 WHERE user_id2 = $1" , user_id)

    async def send_marriage_request(self , user_id , partner_id , chat_id):
        """Отправляет запрос на брак."""
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Проверяем, не существует ли уже запроса на брак
        existing_request = await self.pool.fetchrow(
            "SELECT * FROM marriages WHERE (user_id1 = $1 AND user_id2 = $2) OR (user_id1 = $2 AND user_id2 = $1)" ,
            user_id , partner_id)

        if not existing_request:
            query = """
                INSERT INTO marriages (user_id1, user_id2, status, datetime, chat_id)
                VALUES ($1, $2, 0, $3, $4)
            """
            async with self.pool.acquire() as connection:
                await connection.execute(query , user_id , partner_id , current_datetime , chat_id)

    async def get_marriage_request_info(self , user_id , partner_id):
        """Получает информацию о запросе на брак."""
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        query = """
            SELECT status, user_id1, user_id2 FROM marriages
            WHERE (user_id1 = $1 AND user_id2 = $2) OR (user_id1 = $2 AND user_id2 = $1)
        """
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query , user_id , partner_id)

    async def get_marriage_request_info_by_chat_id(self , chat_id):
        """Получает информацию о запросе на брак по chat_id."""
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        query = "SELECT user_id1, user_id2 FROM marriages WHERE chat_id = $1 AND status = 0"
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(query , chat_id)
        return row

    async def delete_marriage_request_by_chat_id(self , chat_id):
        """Удаляет запрос на брак по chat_id."""
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        query = "DELETE FROM marriages WHERE chat_id = $1 AND status = 0"
        async with self.pool.acquire() as connection:
            await connection.execute(query , chat_id)


    async def cancel_marriage_request(self , user_id):
        """Отменяет запрос на брак пользователя."""
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        # Получаем имя и username пользователя
        first_name = await self.get_name_by_user_id(user_id)
        username = await self.get_username_by_user_id(user_id)

        # Проверяем, есть ли активный запрос от другого пользователя
        async with self.pool.acquire() as connection:
            requesting_user_id = await connection.fetchval(
                "SELECT user_id1 FROM marriages WHERE user_id2 = $1 AND status = 0" , user_id)

            # Проверяем, есть ли запрос на пользователя от другого
            requested_user_id = await connection.fetchval(
                "SELECT user_id2 FROM marriages WHERE user_id1 = $1 AND status = 0" , user_id)

            if requesting_user_id:
                await connection.execute(
                    "DELETE FROM marriages WHERE user_id1 = $1 AND user_id2 = $2 AND status = 0" , user_id ,
                    requesting_user_id)

                # Записываем это в историю с минусом
                cause = "Отмена запроса на брак (пользователь отозвал запрос)"
                amount = -1  # Минусуем какой-то фиксированный "amount", или можно сделать динамическим
                await self.cutehistory_minus(user_id , amount , cause)

                return True

            if requested_user_id:
                await connection.execute(
                    "DELETE FROM marriages WHERE user_id1 = $1 AND user_id2 = $2 AND status = 0" , requested_user_id ,
                    user_id)

                # Записываем это в историю с минусом
                cause = "Отмена запроса на брак (пользователь отклонил запрос)"
                amount = -1  # Минусуем какой-то фиксированный "amount"
                await self.cutehistory_minus(user_id , amount , cause)

                return True

            return False  # Если нет активных запросов

    async def get_marriage_info_by_user_id(self , user_id):
        """Получение информации о запросе на брак по user_id1 или user_id2."""
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        async with self.pool.acquire() as connection:
            result = await connection.fetchrow(
                "SELECT user_id1, user_id2 FROM marriages WHERE (user_id1 = $1 OR user_id2 = $1) AND status = 0" ,
                user_id)

        return result

    async def reject_marriage_request(self , user_id):
        """Отклоняет запрос на брак по user_id1 или user_id2."""
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        # Отладочный вывод: проверяем подключение к базе данных
        print(f"Проверка подключения к базе данных: {self.pool is not None}")

        try:
            # Получаем информацию о запросе на брак для переданного user_id
            print(f"Получаем информацию о запросе на брак для user_id: {user_id}")
            marriage_info = await self.get_marriage_info_by_user_id(user_id)

            # Отладочный вывод: проверяем, что информация о запросе на брак получена
            if marriage_info:
                print(f"Информация о запросе на брак получена: {marriage_info}")
                user_id1 , user_id2 = marriage_info

                # Удаляем запрос на брак по user_id1 или user_id2
                print(f"Удаляем запрос на брак для пользователя {user_id} (user_id1: {user_id1}, user_id2: {user_id2})")
                async with self.pool.acquire() as connection:
                    result = await connection.execute(
                        "DELETE FROM marriages WHERE (user_id1 = $1 OR user_id2 = $1) AND status = 0" , user_id)

                    # Отладочный вывод: проверяем результат удаления
                    print(f"Результат удаления запроса на брак: {result}")

                # Возвращаем user_id1 и user_id2 для дальнейшего использования
                return user_id1 , user_id2
            else:
                print(f"Запрос на брак для user_id {user_id} не найден.")
                return None
        except Exception as e:
            # Отладочный вывод: выводим ошибку
            print(f"Произошла ошибка при отклонении запроса на брак для user_id {user_id}: {e}")
            return None


    async def cutehistory_plus(self , user_id , amount , cause):
        """
        Записывает данные с плюсом в таблицу cutehistory.
        :param user_id: ID пользователя.
        :param amount: Сумма.
        :param cause: Причина.
        """
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        # Получаем имя и username пользователя
        first_name = await self.get_name_by_user_id(user_id)
        username = await self.get_username_by_user_id(user_id)

        # Получаем текущий баланс пользователя
        balance = await self.get_user_balance(user_id)

        # Получаем текущую дату и время
        current_datetime = datetime.now()

        # Преобразуем datetime в строку в формате чч:мм дд.мм.гггг
        formatted_date = current_datetime.strftime("%H:%M %d.%m.%Y")

        try:
            query = """
                INSERT INTO cutehistory ("user_id", "+", cause, data, first_name, username, balance)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            async with self.pool.acquire() as connection:
                await connection.execute(query , user_id , amount , cause , formatted_date , first_name , username, balance)
        except Exception as e:
            print(f"[ERROR] Ошибка при записи данных с плюсом в таблицу cutehistory: {e}")

    async def cutehistory_minus(self , user_id , amount , cause , chat_id=None):
        """
        Записывает данные с минусом в таблицу cutehistory.
        :param user_id: ID пользователя.
        :param amount: Сумма.
        :param cause: Причина.
        :param chat_id: (необязательно) ID группы-получателя при пополнении баланса чата.
        """
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        # Получаем имя и username пользователя
        first_name = await self.get_name_by_user_id(user_id)
        username = await self.get_username_by_user_id(user_id)

        # Получаем текущий баланс пользователя
        balance = await self.get_user_balance(user_id)

        # Получаем текущую дату и время
        current_datetime = datetime.now()

        # Преобразуем datetime в строку в формате чч:мм дд.мм.гггг
        formatted_date = current_datetime.strftime("%H:%M %d.%m.%Y")

        try:
            query = """
                INSERT INTO cutehistory ("user_id", "-", cause, data, first_name, username, balance, chat_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            async with self.pool.acquire() as connection:
                await connection.execute(query , user_id , amount , cause , formatted_date , first_name , username, balance, chat_id)
        except Exception as e:
            print(f"[ERROR] Ошибка при записи данных с минусом в таблицу cutehistory: {e}")

    async def transfer_currency(
        self,
        sender_id: int,
        receiver_id: int,
        amount: int,
        cause: str = "дать",
    ) -> "TransferResult":
        """
        Атомарный перевод кут между игроками: списание, начисление и вся
        журнальная запись (cutehistory x2, moneyhistory, p2p_transfers) идут
        в ОДНОЙ DB-транзакции — либо перевод происходит целиком, либо
        не меняется ничего (в отличие от старого пути из отдельных вызовов
        update_user_balance/cutehistory_plus/cutehistory_minus/add_transaction,
        который мог списать у отправителя и не успеть начислить получателю).

        Поднимает InsufficientBalanceError, если у отправителя не хватает
        баланса на момент фиксации (финальная проверка на уровне SQL,
        защищает от гонки даже если вызывающий код уже проверил баланс заранее).
        """
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        amount = int(amount)
        sender_id = int(sender_id)
        receiver_id = int(receiver_id)

        sender_first_name = await self.get_name_by_user_id(sender_id)
        sender_username = await self.get_username_by_user_id(sender_id)
        receiver_first_name = await self.get_name_by_user_id(receiver_id)
        receiver_username = await self.get_username_by_user_id(receiver_id)

        current_datetime = datetime.now()
        formatted_date = current_datetime.strftime("%H:%M %d.%m.%Y")
        timestamp_without_microseconds = current_datetime.replace(microsecond=0)

        # Детерминированный порядок блокировки по user_id - при встречных
        # переводах A->B и B->A одновременно оба процесса лочат строки users
        # в одном и том же порядке, поэтому дедлок невозможен.
        first_id, second_id = sorted((sender_id, receiver_id))

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Лочим обе строки в детерминированном порядке (SELECT ... FOR UPDATE),
                # затем применяем изменения к нужной стороне.
                await connection.fetch(
                    "SELECT user_id FROM users WHERE user_id = ANY($1::bigint[]) ORDER BY user_id FOR UPDATE",
                    [first_id, second_id],
                )

                sender_row = await connection.fetchrow(
                    """
                    UPDATE users
                       SET balance = balance - $2
                     WHERE user_id = $1
                       AND balance >= $2
                    RETURNING balance
                    """,
                    sender_id, amount,
                )
                if sender_row is None:
                    raise InsufficientBalanceError(
                        f"user_id={sender_id} недостаточно баланса для перевода {amount}"
                    )
                sender_after = int(sender_row["balance"])
                sender_before = sender_after + amount

                receiver_row = await connection.fetchrow(
                    """
                    UPDATE users
                       SET balance = balance + $2
                     WHERE user_id = $1
                    RETURNING balance
                    """,
                    receiver_id, amount,
                )
                if receiver_row is None:
                    receiver_row = await connection.fetchrow(
                        """
                        INSERT INTO users (user_id, balance)
                        VALUES ($1, $2)
                        ON CONFLICT (user_id) DO UPDATE SET balance = users.balance + EXCLUDED.balance
                        RETURNING balance
                        """,
                        receiver_id, amount,
                    )
                receiver_after = int(receiver_row["balance"])
                receiver_before = receiver_after - amount

                transfer_row = await connection.fetchrow(
                    """
                    INSERT INTO p2p_transfers (
                        sender_id, receiver_id, amount,
                        sender_balance_before, sender_balance_after,
                        receiver_balance_before, receiver_balance_after,
                        cause
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                    """,
                    sender_id, receiver_id, amount,
                    sender_before, sender_after,
                    receiver_before, receiver_after,
                    cause,
                )
                transfer_id = int(transfer_row["id"])

                await connection.execute(
                    """
                    INSERT INTO cutehistory ("user_id", "-", cause, data, first_name, username, balance, transfer_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    sender_id, amount, cause, formatted_date,
                    sender_first_name, sender_username, sender_after, transfer_id,
                )
                await connection.execute(
                    """
                    INSERT INTO cutehistory ("user_id", "+", cause, data, first_name, username, balance, transfer_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    receiver_id, amount, cause, formatted_date,
                    receiver_first_name, receiver_username, receiver_after, transfer_id,
                )
                await connection.execute(
                    """
                    INSERT INTO moneyhistory (user_id, user_id2, money, data)
                    VALUES ($1, $2, $3, $4)
                    """,
                    sender_id, receiver_id, amount, timestamp_without_microseconds,
                )

        # Write-through кэш (тот же паттерн, что update_user_balance) - после
        # успешного коммита, best-effort, не влияет на атомарность перевода.
        for uid, new_val in ((sender_id, sender_after), (receiver_id, receiver_after)):
            await self._refresh_balance_cache(uid, new_val)

        return TransferResult(
            transfer_id=int(transfer_row["id"]),
            sender_before=sender_before,
            sender_after=sender_after,
            receiver_before=receiver_before,
            receiver_after=receiver_after,
        )

    async def _refresh_balance_cache(self, user_id: int, new_balance: int) -> None:
        """Best-effort обновление Redis/локального кэша баланса после transfer_currency.

        Тот же паттерн, что update_user_balance: если user_cache_balance ещё не
        приведён к plain dict в этом процессе - приводим (см. update_user_balance
        для истории этого защитного приведения).
        """
        g = globals()
        if "user_cache_balance" not in g or not isinstance(g.get("user_cache_balance"), dict):
            g["user_cache_balance"] = {}
        if "_balance_fresh_at" not in g or not isinstance(g.get("_balance_fresh_at"), dict):
            g["_balance_fresh_at"] = {}
        try:
            g["user_cache_balance"][user_id] = new_balance
            g["_balance_fresh_at"][user_id] = time.monotonic()
        except Exception as e:
            print(f"[WARN] transfer_currency: локальный кэш баланса не обновлён для {user_id}: {e}")

        redis = getattr(self, "redis", None)
        if not redis:
            return
        try:
            await redis.set(f"bal:val:{user_id}", str(new_balance), ex=3600)
            msg = json.dumps({"uid": user_id, "balance": new_balance, "ts": time.time()})
            await redis.publish("bal:bus", msg)
        except Exception as e:
            print(f"[WARN] transfer_currency: Redis-кэш баланса не обновлён для {user_id}: {e}")

    async def get_group_ids34123412(self):
        """
        Получить все идентификаторы групп из таблицы chat.
        """
        if not self.pool:
            raise ConnectionError("[ERROR] Пул соединений не инициализирован.")

        async with self.pool.acquire() as connection:
            try:
                rows = await connection.fetch("SELECT chat_id FROM chat")
                return [ row [ "chat_id" ] for row in rows ]
            except Exception as e:
                print(f"[ERROR] Ошибка при выполнении запроса: {e}")
                return [ ]

    async def get_user_referrals(self):
        """
        Получение данных о пользователях и их количестве приглашенных из таблицы `users`.
        """
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        try:
            query = """
                SELECT user_id, referrals 
                FROM users
                WHERE referrals IS NOT NULL
            """
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(query)
                # Преобразуем результат в список кортежей
                return [ (row [ 'user_id' ] , row [ 'referrals' ]) for row in rows ]
        except Exception as e:
            print(f"[ERROR] Ошибка при выполнении запроса get_user_referrals: {e}")
            return [ ]

    async def get_user_by_chat_id_count(self , chat_id):
        """
        Функция для получения значения из столбца member по chat_id.
        Предполагается, что значение хранится в столбце member.
        """
        try:
            # Запрос для получения значения столбца member для конкретного chat_id
            query = """
                SELECT member 
                FROM chat 
                WHERE chat_id = $1 AND member IS NOT NULL AND member <> ''
            """
            async with self.pool.acquire() as connection:
                member = await connection.fetchval(query , chat_id)

            # Если member равен None, заменяем на 0
            return member if member is not None else 0
        except Exception as e:
            print(f"[ERROR] Ошибка при получении данных: {e}")
            return 0  # Возвращаем 0 в случае ошибки

    async def update_group_member_count(self , chat_id: int , bot1) -> None:
        """
        Обновляет количество участников группы в таблице `chat`.

        :param chat_id: ID чата, для которого нужно обновить количество участников.
        :param bot1: Экземпляр бота для получения информации о чате.
        """
        try:
            # Получаем количество участников через API
            member_count = await bot1.get_chat_member_count(chat_id)
            print(f"[DEBUG] Количество участников в группе {chat_id}: {member_count}")

            # Преобразуем количество участников в строку, если база ожидает строковый тип
            member_count_str = str(member_count)

            # Обновление количества участников в базе данных
            query_update = """
            UPDATE chat
            SET member = $1
            WHERE chat_id = $2
            """

            async with self.pool.acquire() as connection:
                # Выполняем обновление количества участников
                await connection.execute(query_update , member_count_str , chat_id)

            print(f"[DEBUG] Успешно обновлено количество участников для группы {chat_id}.")

        except Exception as e:
            print(f"[ERROR] Ошибка при обновлении участников группы {chat_id}: {e}")

    async def check_user_id_in_users(self , user_id: int) -> bool:
        """
        Возвращает:
          True  - нужна регистрация (строки нет ИЛИ usersref == 0)
          False - уже зарегистрирован (usersref == 1)

        Единственный фактор - столбец usersref (0/1).
        Если строки нет - создаём заглушку (user_id, usersref=0) и возвращаем True.
        """

        # --- Константы для удобства фильтрации логов ---
        _TAG = "[usersref-check]"
        _DEBUG = True  # при желании можно выключить болтливость

        # --- Локальные импорты для самодостаточности функции (без правок модулей) ---
        import time
        from datetime import datetime
        import traceback

        def dbg(msg: str):
            if _DEBUG:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"{_TAG} {now} | {msg}")

        # 0) Проверка типа
        if not isinstance(user_id , int):
            err_text = f"user_id должен быть int, а не {type(user_id).__name__}"
            dbg(f"ОШИБКА: {err_text}")
            raise ValueError(err_text)

        dbg(f"Старт проверки. user_id={user_id}")

        try:
            t_acq = time.perf_counter()
            async with self.pool.acquire() as conn:
                t_acq_done = time.perf_counter()
                dbg(f"Подключение к БД получено за {(t_acq_done - t_acq) * 1000:.2f} мс")

                # 1) Читаем usersref
                sql = "SELECT usersref FROM users WHERE user_id = $1;"
                dbg(f"SQL: {sql} | Параметры: user_id={user_id}")

                t_q = time.perf_counter()
                val = await conn.fetchval(sql , user_id)
                t_q_done = time.perf_counter()
                dbg(f"Запрос выполнен за {(t_q_done - t_q) * 1000:.2f} мс")

                if val is None:
                    dbg("Строка с данным user_id в таблице users НЕ найдена (val is None).")
                    dbg("Делаем заглушку: INSERT (user_id, usersref=0) ...")
                    try:
                        t_ins = time.perf_counter()
                        await conn.execute(
                            """
                            INSERT INTO users (user_id, usersref)
                            VALUES ($1, 0)
                            ON CONFLICT (user_id) DO NOTHING;
                            """ , user_id , )
                        t_ins_done = time.perf_counter()
                        dbg(f"Заглушка вставлена/проверена за {(t_ins_done - t_ins) * 1000:.2f} мс")
                    except Exception as ie:
                        dbg(f"ПРЕДУПРЕЖДЕНИЕ: не удалось вставить заглушку. Причина: {ie}")
                        dbg(traceback.format_exc())
                    dbg("РЕЗУЛЬТАТ: строки не было → нужна регистрация → возврат True")
                    return True

                # 2) Нормализация только в 0/1, без «догадок»
                dbg(f"Получено значение usersref из БД: {val!r} (тип: {type(val).__name__})")

                try:
                    if isinstance(val , bool):
                        dbg("Ветка: значение типа bool.")
                        uref = 1 if val else 0
                    else:
                        # Приводим к строке, убираем пробелы, затем к int.
                        dbg("Ветка: значение НЕ bool. Пробуем привести к int(str(val).strip()).")
                        s = str(val).strip()
                        dbg(f"Строковое представление после strip: {s!r}")
                        iv = int(s)
                        dbg(f"int(...) успешен, получено: {iv}")
                        uref = 1 if iv == 1 else 0
                except Exception as ce:
                    dbg("ИСКЛЮЧЕНИЕ при приведении к 0/1. Трактуем как 0 (не зарегистрирован).")
                    dbg(f"Причина: {ce}")
                    dbg(traceback.format_exc())
                    uref = 0

                dbg(f"Нормализованное значение usersref → uref={uref} (0=не зарег., 1=зарег.)")

                needs_registration = (uref == 0)
                if needs_registration:
                    dbg("РЕЗУЛЬТАТ: usersref == 0 → нужна регистрация → возврат True")
                else:
                    dbg("РЕЗУЛЬТАТ: usersref == 1 → уже зарегистрирован → возврат False")

                return needs_registration

        except Exception as e:
            dbg(f"ОШИБКА верхнего уровня: {e}")
            dbg(traceback.format_exc())
            dbg("Безопасное поведение: считаем, что нужна регистрация → возврат True")
            return True
    async def set_usersref_1(self , user_id: int) -> bool:
        """
        Ставит usersref = 1 для указанного user_id.

        :return: True, если UPDATE что-то изменил (строка найдена и usersref был не 1),
                 False, если строки нет или уже было 1.
        """
        if not isinstance(user_id , int):
            raise ValueError(f"user_id должен быть int, а не {type(user_id).__name__}")

        query = """
            UPDATE users
            SET usersref = 1
            WHERE user_id = $1 AND COALESCE(usersref, 0) <> 1
            RETURNING 1;
        """
        try:
            async with self.pool.acquire() as conn:
                updated = await conn.fetchval(query , user_id)  # None или 1
        except Exception as e:
            print(f"[ERROR] set_usersref_1(user_id={user_id}): {e}")
            return False

        if updated:
            # при наличии кэша - синхронизируем
            if hasattr(self , "user_cache") and isinstance(getattr(self , "user_cache") , dict):
                self.user_cache [ user_id ] = True  # пользователь «зарегистрирован» (usersref == 1)
            return True

        return False

    async def get_active_users_last_10_days(self):
        """
        Возвращает список user_id пользователей, чей last_active в пределах последних 10 дней от текущего момента.
        """
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            async with self.pool.acquire() as connection:
                # Выбираем всех пользователей, у которых поле last_active >= (текущая дата - 10 дней)
                rows = await connection.fetch(
                    "SELECT user_id FROM users WHERE last_active >= NOW() - INTERVAL '10 days'")
            # Извлекаем user_id из результата и возвращаем список
            return [ row [ 'user_id' ] for row in rows ]

        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error: {e}")
            return [ ]
    async def is_group_in_cache_or_db(self , chat_id):
        """
        Проверяет, есть ли группа в group_cache, и если нет, проверяет базу данных.
        :param chat_id: ID чата для проверки.
        :return: True, если группа есть в кэше или базе данных; иначе False.
        """
        # Проверка в group_cache
        if chat_id in self.group_cache:
            print(f"Группа {chat_id} найдена в кэше.")
            return True

        print(f"Группа {chat_id} не найдена в кэше. Проверка в базе данных...")

        # Проверка в базе данных
        query = "SELECT EXISTS(SELECT 1 FROM chat WHERE chat_id = $1)"
        async with self.pool.acquire() as connection:
            result = await connection.fetchval(query , chat_id)
        # Если группа найдена, добавляем её в кэш
        if result:
            self.group_cache [ chat_id ] = True
            print(f"Группа {chat_id} добавлена в кэш.")
            return True

        print(f"Группа {chat_id} не найдена в базе данных.")
        return False
    async def get_current_emoji(self , user_id: int , column_name: str):
        """Получение текущего эмодзи пользователя по его user_id и имени столбца."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            async with self.pool.acquire() as connection:
                # Выполняем асинхронный запрос для получения текущего эмодзи
                result = await connection.fetchrow(
                    f"SELECT {column_name} FROM users WHERE user_id=$1" , user_id)

            # Если результат найден, возвращаем эмодзи, иначе None
            return result [ column_name ] if result else None
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error: {e}")
            return None

    async def update_emoji(self , user_id: int , emoji: str , column_name: str):
        """Обновление эмодзи пользователя в указанном столбце."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            async with self.pool.acquire() as connection:
                # Выполняем асинхронный запрос на обновление эмодзи в таблице
                result = await connection.execute(
                    f"UPDATE users SET {column_name}=$1 WHERE user_id=$2" , emoji , user_id)

            # Возвращаем результат успешного выполнения
            return result
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error: {e}")
            return None

    async def get_user_items_editprofile(self , user_id: int):
        """Получение инвентаря пользователя по user_id в асинхронном режиме."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            async with self.pool.acquire() as connection:
                # Выполняем асинхронный запрос
                result = await connection.fetchrow(
                    "SELECT items FROM users WHERE user_id=$1" , user_id)

            return result [ 'items' ] if result else None
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error: {e}")
            return None

    async def get_user_data_craft(self , user_id):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT user_id, balance, items FROM users WHERE user_id=$1" , user_id)
            return result
    async def fetch_with_retry(self , query , retries=3 , delay=2):
        """
        Повторные попытки выполнить запрос при ошибке.
        """
        for attempt in range(retries):
            try:
                async with self.pool.acquire() as connection:
                    return await connection.fetch(query)
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(delay)  # Ждём перед повторной попыткой
                    continue
                else:
                    raise e

    async def get_user_inventory_use(self , user_id: int):
        """
        Возвращает словарь инвентаря пользователя (users.items).

        - Читает ЛЮБОЙ формат через единый кодек decode_items (dict, чистый JSON,
          старый «обёрнутый» формат вебаппа, bytes и т.п.) и никогда не падает.
        - При необходимости мягко приводит запись в БД к каноническому JSON,
          НО НИКОГДА не затирает непустой инвентарь пустым значением
          (если данные почему-то не распарсились — оставляем их как есть).
        - Делает до 3 попыток при временных сбоях. В худшем случае - {}.
        """
        import asyncio

        for attempt in range(1 , 4):
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT items FROM users WHERE user_id = $1" , user_id)
                    if not row:
                        return {}

                    raw_val = row [ "items" ]
                    decoded = decode_items(raw_val)

                    # Каноническое представление текущего инвентаря.
                    canonical = encode_items(decoded)

                    raw_str = raw_val if isinstance(raw_val , str) else None
                    raw_nonempty = bool(raw_str and raw_str.strip() not in ("" , "{}" , '"{}"'))

                    # Обновляем БД, только если строка отличается И это безопасно:
                    # не перезаписываем непустое поле пустым (защита от потери данных
                    # при неожиданном формате).
                    if raw_str != canonical and not (raw_nonempty and not decoded):
                        await conn.execute(
                            "UPDATE users SET items = $1 WHERE user_id = $2" , canonical , user_id)

                    return decoded

            except Exception as e:
                print(f"[INV][{user_id}] попытка {attempt}/3: {e!r}")
                if attempt < 3:
                    await asyncio.sleep(0.15 * attempt)
                else:
                    print(f"[INV][{user_id}] отдаю дефолт из-за ошибки после 3 попыток")
                    return {}

    # Получаем название предмета по эмодзи (нужно использовать await)
    async def get_item_name_by_emoji_use(self , item_emoji):
        """
        Получает название предмета по его эмодзи.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT name FROM dex WHERE emoji = $1" , item_emoji)
            return row [ "name" ] if row else None

    # Получаем информацию о предмете по его названию (нужно использовать await)
    async def get_item_info_use(self , item_name):
        """
        Получает информацию о предмете по его названию.
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM dex WHERE name = $1" , item_name)
    async def get_marriage_info(self , user_id):
        """
        Получает информацию о браке пользователя по его user_id.

        Возвращает список кортежей с информацией о браке:
        - partner_id: ID партнера
        - status: статус брака (1 - в браке, 0 - нет)
        - marriage_date: дата свадьбы
        - love_coins: количество LoveCoins
        """
        try:
            async with self.pool.acquire() as connection:
                query = """
                SELECT 
                    CASE WHEN user_id1 = $1 THEN user_id2 ELSE user_id1 END AS partner_id,
                    status,
                    datetime,
                    lovecoin
                FROM marriages
                WHERE user_id1 = $1 OR user_id2 = $1
                """
                marriage_info = await connection.fetch(query , user_id)

                # Форматирование даты и формирование результирующего списка
                formatted_marriage_info = [ ]
                for info in marriage_info:
                    partner_id , status , marriage_date , love_coins = info

                    # Проверка, является ли marriage_date строкой (если да, то пропускаем форматирование)
                    if isinstance(marriage_date , str):
                        formatted_date = marriage_date
                    else:
                        # Если это объект datetime, форматируем его в строку
                        formatted_date = marriage_date.strftime("%d.%m.%Y %H:%M:%S")

                    formatted_marriage_info.append((partner_id , status , formatted_date , love_coins))

                return formatted_marriage_info

        except Exception as e:
            print(f"Ошибка при получении информации о браке: {e}")
            return None

    async def get_partner_data(self , partner_id):
        """
        Асинхронно возвращает данные о партнере из таблицы users для заданного user_id.
        """
        try:
            async with self.pool.acquire() as connection:
                query = """
                    SELECT username, first_name
                    FROM users
                    WHERE user_id = $1
                """
                partner_data = await connection.fetchrow(query , partner_id)
                return partner_data
        except Exception as e:
            print(f"Ошибка при выполнении запроса: {e}")
            return None

    # опционально - единый переключатель подробных логов


    def _balance_is_fresh(self, user_id) -> bool:
        """True, если кэш баланса недавно сверялся с БД и ему можно доверять."""
        if BALANCE_CACHE_TTL_SEC <= 0:
            return False
        try:
            ts = _balance_fresh_at.get(int(user_id))
        except Exception:
            return False
        if ts is None:
            return False
        return (time.monotonic() - ts) <= BALANCE_CACHE_TTL_SEC

    def invalidate_user_balance_cache(self, user_id) -> None:
        """Пометить кэш баланса устаревшим — следующий get_user_balance перечитает
        БД. Вызывай после правок баланса вне бота (WebApp/админка/ручной SQL)."""
        try:
            _balance_fresh_at.pop(int(user_id), None)
        except Exception:
            pass

    async def get_user_balance(self , user_id):
        """
        Возвращает int-баланс пользователя по user_id.

        Кэш + сверка с БД (cache coherence):
          1) Cache-hit отдаётся ТОЛЬКО если запись «свежая» (моложе TTL) — иначе
             считаем возможной внешнюю правку и перечитываем БД.
          2) Проверка пула.
          3) Лок на user_id + повторная проверка свежего кэша (double-check).
          4) Одиночный SELECT balance.
          5) Нормализация -> int.
          6) Запись в кэш + отметка свежести, возврат.
          7) Если не найден - None.
        """
        # 1) КЭШ (вне лока)
        try:
            cached = user_cache_balance.get(user_id)
        except Exception as e:
            _dbg(f"💰 [cache] Ошибка чтения кэша для {user_id}: {e}")
            cached = None

        if cached is not None:
            try:
                cached_int = int(cached)
            except Exception as e:
                _dbg(f"💰 [cache] Ошибка приведения к int для {user_id}: {e}")
                cached_int = None
            # Отдаём кэш только если он недавно сверялся с БД. Иначе — сверка ниже.
            if cached_int is not None and self._balance_is_fresh(user_id):
                _dbg(f"💰 [cache-hit] user_id={user_id}, balance={cached_int}")
                return cached_int

        # 2) Страховка пула
        if not getattr(self , "pool" , None):
            _dbg("💰 [error] Пул соединений не инициализирован.")
            return None

        # 3) Лок на конкретного пользователя
        lock = _user_balance_locks.setdefault(user_id , asyncio.Lock())
        async with lock:
            # Повторная попытка взять из кэша (double-check) — только если свежий
            try:
                cached = user_cache_balance.get(user_id)
                if cached is not None and self._balance_is_fresh(user_id):
                    cached_int = int(cached)
                    _dbg(f"💰 [cache-hit-2] user_id={user_id}, balance={cached_int}")
                    return cached_int
            except Exception as e:
                _dbg(f"💰 [cache] Ошибка повторного чтения/приведения к int для {user_id}: {e}")

            # 4) Читаем из БД
            query = "SELECT balance FROM users WHERE user_id = $1"
            try:
                async with self.pool.acquire() as connection:
                    value = await connection.fetchval(query , user_id)
            except Exception as e:
                _dbg(f"💰 [db] Ошибка SELECT balance для user_id={user_id}: {e}")
                return None

            if value is None:
                _dbg(f"💰 [db] Пользователь user_id={user_id} не найден.")
                return None

            # 5) НОРМАЛИЗАЦИЯ -> int
            try:
                # быстрые пути
                if isinstance(value , int):
                    balance_int = value
                elif isinstance(value , bool):
                    balance_int = int(value)
                elif isinstance(value , float):
                    # защита от NaN/Inf
                    if value != value or value in (float("inf") , float("-inf")):
                        _dbg(f"💰 [normalize] float is NaN/Inf (user_id={user_id})")
                        return None
                    balance_int = int(value)  # усечение, как у тебя
                elif isinstance(value , Decimal):
                    # Decimal → float → int по твоей логике с усечением
                    f = float(value)
                    if f != f or f in (float("inf") , float("-inf")):
                        _dbg(f"💰 [normalize] Decimal NaN/Inf (user_id={user_id})")
                        return None
                    balance_int = int(f)
                elif isinstance(value , str):
                    # чистим пробелы, \u00A0 (неразрывный), табы и т.д.
                    s = value.strip().replace("\u00A0" , "").replace(" " , "")
                    # запятая = десятичный разделитель → как в твоём коде заменим на точку
                    s = s.replace("," , ".")
                    if "." in s:
                        try:
                            f = float(s)
                        except Exception:
                            _dbg(f"💰 [normalize] bad float string '{value}' (user_id={user_id})")
                            return None
                        if f != f or f in (float("inf") , float("-inf")):
                            _dbg(f"💰 [normalize] str NaN/Inf '{value}' (user_id={user_id})")
                            return None
                        balance_int = int(f)  # усечение, как у тебя
                    else:
                        balance_int = int(s)
                else:
                    # последний шанс: сначала int(), иначе float()->int, как у тебя
                    try:
                        balance_int = int(value)
                    except Exception:
                        f = float(value)
                        if f != f or f in (float("inf") , float("-inf")):
                            _dbg(f"💰 [normalize] fallback NaN/Inf (user_id={user_id})")
                            return None
                        balance_int = int(f)
            except Exception as e:
                _dbg(f"💰 [normalize] Не удалось привести balance={value!r} к int (user_id={user_id}): {e}")
                return None

            # негативные значения не блокируем (сохраняем твою семантику),
            # но логируем - чтобы можно было отследить источник
            if balance_int < 0:
                _dbg(f"💰 [warn] отрицательный баланс user_id={user_id}: {balance_int}")

            # 6) Кладём в кэш уже int + отмечаем свежесть (значение сверено с БД)
            try:
                user_cache_balance [ user_id ] = balance_int
                _balance_touch_fresh(user_id)
                _dbg(f"💰 [cache-set] user_id={user_id}, balance={balance_int}")
            except Exception as e:
                _dbg(f"💰 [cache-set] Ошибка сохранения в кэш для {user_id}: {e}")

            return balance_int

    async def get_user_balance_and_assets(self, user_id):
        """
        Асинхронно получаем баланс, CuteCoin, cutenin, balance2 и balance3 пользователя по user_id.
        """
        query = """
        SELECT balance, "CuteCoin", cutenin, balance2, balance3
        FROM users
        WHERE user_id = $1
        """
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow(query, user_id)

        if result:
            return tuple(result.values())  # Возвращает кортеж (balance, CuteCoin, cutenin, balance2, balance3)
        else:
            return None  # Нет пользователя с таким user_id

    async def get_user_inventory(self , user_id):
        try:
            async with self.pool.acquire() as connection:
                # Получаем инвентарь пользователя из базы данных
                row = await connection.fetchrow(
                    "SELECT items FROM users WHERE user_id = $1" , user_id)

                # Если запись найдена — читаем инвентарь через единый кодек
                # (понимает dict, чистый JSON и старый «обёрнутый» формат вебаппа).
                if row:
                    return decode_items(row [ 'items' ])
                else:
                    return {}
        except Exception as e:
            print(f"[ERROR] Ошибка при получении инвентаря пользователя {user_id}: {e}")
            return {}






    async def fetch_all(self , query , params=None):
        """
        Выполняет запрос и возвращает все результаты.
        Если параметров нет, передаем пустой список или кортеж.
        """
        if params is None:
            params = [ ]
        async with self.pool.acquire() as conn:
            # Получаем все строки по запросу и возвращаем их
            return await conn.fetch(query , *params)
    async def load_users_to_dict(self):
        """
        Загружает информацию о всех пользователях в словарь.
        """
        query = "SELECT user_id, first_name, username, bio FROM users"

        async with self.pool.acquire() as connection:
            rows = await connection.fetch(query)
            for row in rows:
                user_id = row [ 'user_id' ]
                self.users_dict [ user_id ] = {'first_name': row [ 'first_name' ] , 'username': row [ 'username' ] ,
                    'bio': row [ 'bio' ]}

    async def user_update_fields(self, user_id, updates):
        """
        Обновляет указанные поля для пользователя с данным user_id.
        :param user_id: ID пользователя
        :param updates: Словарь с полями для обновления (например, {'first_name': 'John', 'bio': 'New bio'}).
        """
        # Строим динамический запрос на основе переданных обновлений
        set_clause = ", ".join([f"{field} = ${idx + 1}" for idx, field in enumerate(updates.keys())])
        values = list(updates.values())
        values.append(user_id)  # Добавляем user_id в конец списка значений

        query = f"UPDATE users SET {set_clause} WHERE user_id = ${len(values)}"

        # Выполняем запрос с обновлёнными значениями
        async with self.pool.acquire() as connection:
            await connection.execute(query, *values)

        print(f"⭐️⭐️⭐️ Обновлены следующие поля для пользователя {user_id}: {updates}")

    async def add_data(self , user_id , first_name , username , bio , start_balance):
        """
        Добавляет или обновляет данные пользователя в базе данных.
        """
        # Проверка значений
        if not user_id:
            raise ValueError("ID пользователя не может быть None или пустым.")
        if not first_name:
            first_name = "Неизвестный"  # Задаем значение по умолчанию
        if username is None:
            username = ""
        if bio is None:
            bio = ""

        # Лог для отладки
        print(
            f"Данные для добавления/обновления: user_id={user_id}, first_name={first_name}, username={username}, bio={bio}, balance={start_balance}")

        #user_cache_balance [ user_id ] = start_balance
        registration_date = datetime.now()

        query_check = "SELECT 1 FROM users WHERE user_id = $1"

        # ВАЖНО: для существующего пользователя НЕ трогаем balance и data.
        # balance = куты игрока, data = дата регистрации ("время в боте" в стате).
        # Раньше здесь стояло SET data=..., balance=start_balance, из-за чего переход
        # по чужой реф-ссылке обнулял куты и сбрасывал дату регистрации на сегодня.
        # Обновляем только профильные поля.
        query_update = """
        UPDATE users
        SET first_name = $1, username = $2, bio = $3
        WHERE user_id = $4
        """

        query_insert = """
        INSERT INTO users (user_id, data, first_name, username, bio, balance)
        VALUES ($1, $2, $3, $4, $5, $6)
        """

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            exists = await connection.fetchval(query_check , user_id)

            if exists:
                # Обновляем ТОЛЬКО профиль существующего пользователя (без balance/data)
                await connection.execute(
                    query_update , first_name , username , bio , user_id)
                print(f"⭐️ Пользователь с ID {user_id} обновлен (профиль; баланс и дата сохранены).")
            else:
                # Добавляем нового пользователя без столбца id
                await connection.execute(
                    query_insert , user_id , registration_date , first_name , username , bio , start_balance)
                print(f"⭐️ Пользователь с ID {user_id} добавлен.")
    async def user_get_user_info(self, user_id):
        """
        Получает информацию о пользователе (first_name, username, bio) по user_id.
        :param user_id: ID пользователя.
        :return: Кортеж с информацией о пользователе или None, если пользователь не найден.
        """
        query = """
        SELECT first_name, username, bio
        FROM users
        WHERE user_id = $1
        """
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow(query, user_id)

        return result if result else None  # Возвращает кортеж или None, если пользователь не найден










    async def update_user_winamount(self, user_id: int, increment: int):
        """
        Обновляет winamount пользователя по user_id, увеличив его на значение increment.
        Если пользователя нет в базе, создаёт нового с начальным winamount.
        :param user_id: ID пользователя.
        :param increment: Сколько нужно добавить к winamount.
        """
        query_check = "SELECT winamount FROM users WHERE user_id = $1"
        query_update = "UPDATE users SET winamount = $1 WHERE user_id = $2"
        query_insert = "INSERT INTO users (user_id, winamount) VALUES ($1, $2)"

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            result = await connection.fetchval(query_check, user_id)

            if result is not None:
                # Обновляем winamount для существующего пользователя
                new_wins = result + increment
                await connection.execute(query_update, new_wins, user_id)
                print(f"⭐️⭐️⭐️ winamount пользователя с ID {user_id} обновлён на {new_wins}.")
            else:
                # Создаём нового пользователя с указанным winamount
                await connection.execute(query_insert, user_id, increment)
                print(f"⭐️⭐️⭐️ Новый пользователь с ID {user_id} добавлен с winamount = {increment}.")

    async def get_user_winamount_all(self):
        query = "SELECT user_id, winamount FROM users WHERE winamount IS NOT NULL"

        async with self.pool.acquire() as connection:
            # Выполнение запроса и получение всех результатов
            referrals = await connection.fetch(query)

        return referrals  # Возвращаем список словарей с user_id и winamount

    async def get_user_loose_all(self):
        query = "SELECT user_id, loose FROM users WHERE loose IS NOT NULL"

        async with self.pool.acquire() as connection:
            # Выполнение запроса и получение всех результатов
            loose_data = await connection.fetch(query)

        return loose_data  # Возвращаем список словарей с user_id и loose

    async def get_user_wins_all(self):
        query = "SELECT user_id, wins FROM users WHERE wins IS NOT NULL"

        async with self.pool.acquire() as connection:
            # Выполнение запроса и получение всех результатов
            wins_data = await connection.fetch(query)

        return wins_data  # Возвращаем список словарей с user_id и wins


    async def get_user_winamount(self, user_id):
        """
        Получает значение из столбца winamount для указанного user_id из таблицы users.

        :param user_id: ID пользователя
        :return: Значение из столбца winamount или None, если записи не существует
        """
        query = "SELECT winamount FROM users WHERE user_id = $1"

        # Подключаемся через пул соединений
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow(query, user_id)

        return result['winamount'] if result else None

    async def get_user_wins(self , user_id):
        """
        Получает значение из столбца wins для указанного user_id из таблицы users.

        :param user_id: ID пользователя
        :return: Значение из столбца wins или None, если записи не существует
        """
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow("SELECT wins FROM users WHERE user_id = $1" , user_id)

        return result [ 'wins' ] if result else None

    async def get_user_loose(self , user_id):
        """
        Получает значение из столбца loose для указанного user_id из таблицы users.

        :param user_id: ID пользователя
        :return: Значение из столбца loose или None, если записи не существует
        """
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow("SELECT loose FROM users WHERE user_id = $1" , user_id)

        return result [ 'loose' ] if result else None

    async def delete_refout_if_exists(self , user_id):
        """
        Удаляет строку из таблицы refout для указанного user_id, если она существует.

        :param user_id: ID пользователя
        :return: True, если запись была удалена; False, если записи не было
        """
        query = "DELETE FROM refout WHERE user_id = $1 RETURNING user_id"

        # Подключаемся через пул соединений
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(query , user_id)

        return row is not None

    async def update_user_wins(self , user_id: int , increment: int , bot1 , ref_coin: int , game_id=None ,
                               participants=None):
        """
        Обновляет значение побед пользователя и обрабатывает реферальную систему,
        только если играет сам реферал (actor=user_id) и существует прямая запись в refcheck (refcheck.user_id = actor).
        Дополнительно: если известен состав игры, актёр должен быть участником, а inviter и referral не должны быть в одной игре.
        """
        print(
            f"[update_user_wins] ▶️ Старт функции | user_id={user_id} | increment={increment} | ref_coin={ref_coin} | game_id={game_id}")
        async with self.pool.acquire() as connection:
            print("[update_user_wins] 🔌 Подключение к БД получено")

            # 0) Подтянем (опционально) участников игры
            game_participants = None
            if participants is not None:
                try:
                    game_participants = {int(p) for p in participants if p is not None}
                    print(f"[update_user_wins] 🧾 participants (в арг.): {game_participants}")
                except Exception as e:
                    print(f"[update_user_wins] ⚠️ Не удалось разобрать participants из аргумента: {e}")
                    game_participants = None
            elif game_id is not None:
                # Пытаемся получить через БД/хелпер, если реализовано у тебя
                try:
                    gp = await self.get_game_participants(game_id)
                    game_participants = {int(p) for p in (gp or [ ])}
                    print(f"[update_user_wins] 🧾 participants (по game_id): {game_participants}")
                except AttributeError:
                    print(
                        "[update_user_wins] ℹ️ self.get_game_participants недоступен - пропускаю валидацию состава игры")
                except Exception as e:
                    print(f"[update_user_wins] ⚠️ Ошибка при get_game_participants: {e}")

            # 1) Обновление побед и refcheckgame
            print(f"[update_user_wins] 🔎 Читаю пользователя из users: user_id={user_id}")
            result = await connection.fetchrow("SELECT wins, refcheckgame FROM users WHERE user_id = $1" , user_id)

            if result:
                print(
                    f"[update_user_wins] ✅ Найден пользователь: wins={result [ 'wins' ]}, refcheckgame={result [ 'refcheckgame' ]}")
                new_wins = (result [ 'wins' ] or 0) + increment
                print(f"[update_user_wins] ✏️ Обновляю wins: {result [ 'wins' ]} -> {new_wins}")
                await connection.execute("UPDATE users SET wins = $1 WHERE user_id = $2" , new_wins , user_id)

                if (result [ 'refcheckgame' ] or 0) == 0:
                    print("[update_user_wins] ✏️ refcheckgame=0, устанавливаю refcheckgame=1")
                    await connection.execute("UPDATE users SET refcheckgame = 1 WHERE user_id = $1" , user_id)
            else:
                print("[update_user_wins] ⚠️ Пользователь не найден в таблице users - пропускаю обновление wins")

            # 2) Строгий поиск ролей inviter/referral - ТОЛЬКО refcheck.user_id = actor
            print(f"[update_user_wins] 🔎 Определяю роли inviter/referral (strict) для event_user_id={user_id}")

            inviter_id = None
            referral_id = None
            found_by = None
            ref_deleted = False
            will_notify = False

            # Доп.предикаты по составу игры: актёр должен быть участником (если известен состав)
            if game_participants is not None and user_id not in game_participants:
                print("[update_user_wins] 💤 Актёр не является участником этой игры - тихий выход без реф-логики")
                print(f"[update_user_wins] 🏁 Завершение функции для user_id={user_id}")
                return

            async with connection.transaction():
                print("[update_user_wins] 🔒 Транзакция начата")
                row_fwd = await connection.fetchrow(
                    "SELECT user_id, ref_user_id FROM refcheck WHERE user_id = $1 FOR UPDATE" , user_id)
                print(f"[update_user_wins] 🧾 row_fwd(strict)={row_fwd}")

                if not row_fwd or row_fwd [ "ref_user_id" ] is None:
                    print(
                        "[update_user_wins] 💤 Нет актуальной прямой записи refcheck для этого игрока - верификация не требуется")
                else:
                    inviter_id = int(row_fwd [ "ref_user_id" ])
                    referral_id = int(row_fwd [ "user_id" ])
                    found_by = "refcheck_forward_strict"
                    print(f"[update_user_wins] ✅ Прямая запись (strict): inviter={inviter_id}, referral={referral_id}")

                    if inviter_id == referral_id:
                        print(
                            "[update_user_wins] ⚠️ inviter_id == referral_id - некорректная связка, выхожу без начислений")
                        inviter_id = referral_id = None
                    else:
                        # Если известен состав - убеждаемся, что inviter и referral НЕ в одной игре
                        if game_participants is not None and inviter_id in game_participants and referral_id in game_participants:
                            print(
                                "[update_user_wins] ⛔ inviter и referral в одном матче - верификация запрещена для этой игры")
                            # НИЧЕГО НЕ УДАЛЯЕМ: пусть сыграют в другой игре, чтобы пройти верификацию
                            inviter_id = referral_id = None
                        else:
                            inv_exists = await connection.fetchval(
                                "SELECT 1 FROM users WHERE user_id = $1" , inviter_id)
                            ref_exists = await connection.fetchval(
                                "SELECT 1 FROM users WHERE user_id = $1" , referral_id)
                            print(
                                f"[update_user_wins] 🧾 exists -> inviter={bool(inv_exists)} | referral={bool(ref_exists)}")
                            if not inv_exists or not ref_exists:
                                print("[update_user_wins] ⚠️ Один из участников отсутствует в users - не начисляю")
                                inviter_id = referral_id = None
                            else:
                                true_inv = await connection.fetchval(
                                    "SELECT refferer_id FROM users WHERE user_id = $1" , referral_id)
                                print(f"[update_user_wins] 🔍 users.refferer_id(referral={referral_id}) => {true_inv}")
                                if true_inv is None or int(true_inv) != inviter_id:
                                    print("[update_user_wins] ⚠️ Несоответствие refferer_id - не начисляю")
                                    inviter_id = referral_id = None
                                else:
                                    # ── НАЧИСЛЕНИЯ (атомарно) ─────────────────────────────
                                    print("[update_user_wins] 💰 Готовлю начисления (в транзакции)")
                                    inviter_balance_old = await self.get_user_balance(inviter_id)
                                    referral_balance_old = await self.get_user_balance(referral_id)
                                    inviter_balance_new = inviter_balance_old + ref_coin
                                    referral_balance_new = referral_balance_old + ref_coin

                                    print(
                                        f"[update_user_wins] ✏️ Начисляю пригласителю: {inviter_balance_old} + {ref_coin} = {inviter_balance_new}")
                                    await self.update_user_balance(inviter_id , inviter_balance_new)

                                    print(
                                        f"[update_user_wins] ✏️ Начисляю рефералу: {referral_balance_old} + {ref_coin} = {referral_balance_new}")
                                    await self.update_user_balance(referral_id , referral_balance_new)

                                    current_refferals = await self.get_refferals_count(inviter_id)
                                    new_refferals = (current_refferals or 0) + 1
                                    print(
                                        f"[update_user_wins] ✏️ Обновляю счётчик рефералов: {current_refferals} -> {new_refferals}")
                                    await self.set_ref_user(inviter_id , new_refferals)

                                    await self.set_usersref_1(referral_id)
                                    print(f"[update_user_wins] ✅ Пометка usersref_1: referral_id={referral_id}")

                                    print(
                                        "[update_user_wins] 🧽 Очищаю просроченные refout через remove_expired_refout()")
                                    await self.remove_expired_refout()
                                    print("[update_user_wins] ✅ Очистка refout завершена")

                                    # Удаляем все записи для user_id реферала (на случай дублей)
                                    await connection.execute("DELETE FROM refcheck WHERE user_id = $1" , referral_id)
                                    ref_deleted = True
                                    print(
                                        f"[update_user_wins] 🧹 Удалены записи refcheck (strict forward): user_id={referral_id}")

                                    will_notify = True

                print("[update_user_wins] 🔓 Транзакция завершена")

            # 3) Антидубликатор уведомлений
            import time as _time
            if not hasattr(self , "_sent_msg_cache"):
                self._sent_msg_cache = {}

            def _should_send(msg_type: str , chat_id: int , inviter_id_: int , referral_id_: int , limit: int = 1 ,
                             ttl_sec: int = 120) -> bool:
                key = (msg_type , int(chat_id) , int(inviter_id_) , int(referral_id_))
                now = _time.time()
                rec = self._sent_msg_cache.get(key)
                if rec and (now - rec [ "ts" ] <= ttl_sec) and rec [ "count" ] >= limit:
                    print(f"[update_user_wins] 🔁 Skip duplicate msg: key={key} count={rec [ 'count' ]} ttl_ok")
                    return False
                if not rec or (now - rec [ "ts" ] > ttl_sec):
                    rec = {"count": 0 , "ts": now}
                rec [ "count" ] += 1
                rec [ "ts" ] = now
                self._sent_msg_cache [ key ] = rec
                print(f"[update_user_wins] ✅ Send allowed: key={key} new_count={rec [ 'count' ]}")
                return True

            # 4) Уведомления и финальная подчистка refout
            try:
                if inviter_id and referral_id and will_notify:
                    print("[update_user_wins] ✉️ Готовлю уведомления и ссылки")
                    referral_first_name = await self.get_firstname_by_user_id(referral_id)
                    referral_username = await self.get_username_by_user_id(referral_id)
                    referral_link = await create_user_link(referral_id , referral_first_name , referral_username)
                    win_amount_formatted = "{:,.0f}".format(ref_coin).replace("," , ".")
                    print(f"[update_user_wins] 🔗 Ссылка на реферала: {referral_link}")

                    if _should_send("ping_inviter" , inviter_id , inviter_id , referral_id):
                        await bot1.send_message(
                            chat_id=inviter_id , text="🍀" , parse_mode="HTML" , disable_web_page_preview=True)
                        print(f"[update_user_wins] ✅ Пинг пригласителю: chat_id={inviter_id}")

                    if _should_send("inviter_notify" , inviter_id , inviter_id , referral_id):
                        print(f"[update_user_wins] ✉️ Отправляю уведомление пригласителю: chat_id={inviter_id}")
                        await bot1.send_message(
                            chat_id=inviter_id ,
                            text=(f"<b>🌿 Реферал засчитан, вы получили {win_amount_formatted} кут!</b>\n"
                                  f"<b>🌴 {referral_link} прошёл(-ла) верификацию</b>") , parse_mode="HTML" ,
                            disable_web_page_preview=True)
                        print("[update_user_wins] ✅ Уведомление пригласителю отправлено")

                    if _should_send("referral_verified" , referral_id , inviter_id , referral_id):
                        verification_msg = (f"<b>🌿 Верификация реферальной системы пройдена!</b>\n"
                                            f"<b>🌴 Вы получили {win_amount_formatted} кут</b>")
                        print(f"[update_user_wins] ✉️ Отправляю уведомление рефералу: chat_id={referral_id}")
                        await bot1.send_message(
                            chat_id=referral_id , text=verification_msg , parse_mode="HTML" ,
                            disable_web_page_preview=True)
                        print("[update_user_wins] ✅ Уведомление рефералу отправлено")

                    # Чистим refout по рефералу
                    deleted = await self.delete_refout_if_exists(referral_id)
                    if deleted:
                        print(f"[update_user_wins] 🧹 Удалил запись refout для referral_id={referral_id}")
                    else:
                        print(
                            f"[update_user_wins] ℹ️ Записи refout для referral_id={referral_id} не было - ничего не делал")
                else:
                    print("[update_user_wins] ℹ️ Верификация не производилась - уведомления не требуются")

            except Exception as e:
                print(f"[update_user_wins] ❗ Ошибка при отправке уведомлений: {e}")

        print(f"[update_user_wins] 🏁 Завершение функции для user_id={user_id}")

    async def update_user_loose(self , user_id: int , increment: int , bot1 , ref_coin: int , game_id=None ,
                                participants=None):
        """
        Обновляет значение проигрышей пользователя и обрабатывает реферальную систему,
        только если играет сам реферал (actor=user_id) и существует прямая запись в refcheck (refcheck.user_id = actor).
        Дополнительно: если известен состав игры, актёр должен быть участником, а inviter и referral не должны быть в одной игре.
        """
        print(
            f"[update_user_loose] ▶️ Старт функции | user_id={user_id} | increment={increment} | ref_coin={ref_coin} | game_id={game_id}")
        async with self.pool.acquire() as connection:
            print("[update_user_loose] 🔌 Подключение к БД получено")

            # 0) Подтянем (опционально) участников игры
            game_participants = None
            if participants is not None:
                try:
                    game_participants = {int(p) for p in participants if p is not None}
                    print(f"[update_user_loose] 🧾 participants (в арг.): {game_participants}")
                except Exception as e:
                    print(f"[update_user_loose] ⚠️ Не удалось разобрать participants из аргумента: {e}")
                    game_participants = None
            elif game_id is not None:
                try:
                    gp = await self.get_game_participants(game_id)
                    game_participants = {int(p) for p in (gp or [ ])}
                    print(f"[update_user_loose] 🧾 participants (по game_id): {game_participants}")
                except AttributeError:
                    print(
                        "[update_user_loose] ℹ️ self.get_game_participants недоступен - пропускаю валидацию состава игры")
                except Exception as e:
                    print(f"[update_user_loose] ⚠️ Ошибка при get_game_participants: {e}")

            # 1) Обновляем проигрыши и refcheckgame
            print(f"[update_user_loose] 🔎 Читаю пользователя из users: user_id={user_id}")
            result = await connection.fetchrow("SELECT loose, refcheckgame FROM users WHERE user_id = $1" , user_id)

            if result:
                print(
                    f"[update_user_loose] ✅ Найден пользователь: loose={result [ 'loose' ]}, refcheckgame={result [ 'refcheckgame' ]}")
                new_loose = (result [ 'loose' ] or 0) + increment
                print(f"[update_user_loose] ✏️ Обновляю loose: {result [ 'loose' ]} -> {new_loose}")
                await connection.execute("UPDATE users SET loose = $1 WHERE user_id = $2" , new_loose , user_id)

                if (result [ 'refcheckgame' ] or 0) == 0:
                    print("[update_user_loose] ✏️ refcheckgame=0, устанавливаю refcheckgame=1")
                    await connection.execute("UPDATE users SET refcheckgame = 1 WHERE user_id = $1" , user_id)
            else:
                print("[update_user_loose] ⚠️ Пользователь не найден в таблице users - пропускаю обновление loose")

            # 2) Строгий поиск ролей inviter/referral - ТОЛЬКО refcheck.user_id = actor
            print(f"[update_user_loose] 🔎 Определяю роли inviter/referral (strict) для event_user_id={user_id}")

            inviter_id = None
            referral_id = None
            found_by = None
            ref_deleted = False
            will_notify = False

            # Доп.предикаты по составу игры: актёр должен быть участником (если известен состав)
            if game_participants is not None and user_id not in game_participants:
                print("[update_user_loose] 💤 Актёр не является участником этой игры - тихий выход без реф-логики")
                print(f"[update_user_loose] 🏁 Завершение функции для user_id={user_id}")
                return

            async with connection.transaction():
                print("[update_user_loose] 🔒 Транзакция начата")
                row_fwd = await connection.fetchrow(
                    "SELECT user_id, ref_user_id FROM refcheck WHERE user_id = $1 FOR UPDATE" , user_id)
                print(f"[update_user_loose] 🧾 row_fwd(strict)={row_fwd}")

                if not row_fwd or row_fwd [ "ref_user_id" ] is None:
                    print(
                        "[update_user_loose] 💤 Нет актуальной прямой записи refcheck для этого игрока - верификация не требуется")
                else:
                    inviter_id = int(row_fwd [ "ref_user_id" ])
                    referral_id = int(row_fwd [ "user_id" ])
                    found_by = "refcheck_forward_strict"
                    print(f"[update_user_loose] ✅ Прямая запись (strict): inviter={inviter_id}, referral={referral_id}")

                    if inviter_id == referral_id:
                        print(
                            "[update_user_loose] ⚠️ inviter_id == referral_id - некорректная связка, выхожу без начислений")
                        inviter_id = referral_id = None
                    else:
                        # Если известен состав - убеждаемся, что inviter и referral НЕ в одной игре
                        if game_participants is not None and inviter_id in game_participants and referral_id in game_participants:
                            print(
                                "[update_user_loose] ⛔ inviter и referral в одном матче - верификация запрещена для этой игры")
                            inviter_id = referral_id = None
                        else:
                            inv_exists = await connection.fetchval(
                                "SELECT 1 FROM users WHERE user_id = $1" , inviter_id)
                            ref_exists = await connection.fetchval(
                                "SELECT 1 FROM users WHERE user_id = $1" , referral_id)
                            print(
                                f"[update_user_loose] 🧾 exists -> inviter={bool(inv_exists)} | referral={bool(ref_exists)}")
                            if not inv_exists or not ref_exists:
                                print("[update_user_loose] ⚠️ Один из участников отсутствует в users - не начисляю")
                                inviter_id = referral_id = None
                            else:
                                true_inv = await connection.fetchval(
                                    "SELECT refferer_id FROM users WHERE user_id = $1" , referral_id)
                                print(f"[update_user_loose] 🔍 users.refferer_id(referral={referral_id}) => {true_inv}")
                                if true_inv is None or int(true_inv) != inviter_id:
                                    print("[update_user_loose] ⚠️ Несоответствие refferer_id - не начисляю")
                                    inviter_id = referral_id = None
                                else:
                                    # ── НАЧИСЛЕНИЯ (атомарно) ─────────────────────────────
                                    print("[update_user_loose] 💰 Готовлю начисления (в транзакции)")
                                    inviter_balance_old = await self.get_user_balance(inviter_id)
                                    referral_balance_old = await self.get_user_balance(referral_id)
                                    inviter_balance_new = inviter_balance_old + ref_coin
                                    referral_balance_new = referral_balance_old + ref_coin

                                    print(
                                        f"[update_user_loose] ✏️ Начисляю пригласителю: {inviter_balance_old} + {ref_coin} = {inviter_balance_new}")
                                    await self.update_user_balance(inviter_id , inviter_balance_new)

                                    print(
                                        f"[update_user_loose] ✏️ Начисляю рефералу: {referral_balance_old} + {ref_coin} = {referral_balance_new}")
                                    await self.update_user_balance(referral_id , referral_balance_new)

                                    current_refferals = await self.get_refferals_count(inviter_id)
                                    new_refferals = (current_refferals or 0) + 1
                                    print(
                                        f"[update_user_loose] ✏️ Обновляю счётчик рефералов: {current_refferals} -> {new_refferals}")
                                    await self.set_ref_user(inviter_id , new_refferals)

                                    await self.set_usersref_1(referral_id)
                                    print(f"[update_user_loose] ✅ Пометка usersref_1: referral_id={referral_id}")

                                    print(
                                        "[update_user_loose] 🧽 Очищаю просроченные refout через remove_expired_refout()")
                                    await self.remove_expired_refout()
                                    print("[update_user_loose] ✅ Очистка refout завершена")

                                    await connection.execute("DELETE FROM refcheck WHERE user_id = $1" , referral_id)
                                    ref_deleted = True
                                    print(
                                        f"[update_user_loose] 🧹 Удалены записи refcheck (strict forward): user_id={referral_id}")

                                    will_notify = True

                print("[update_user_loose] 🔓 Транзакция завершена")

            # 3) Антидубликатор
            import time as _time
            if not hasattr(self , "_sent_msg_cache"):
                self._sent_msg_cache = {}

            def _should_send(msg_type: str , chat_id: int , inviter_id_: int , referral_id_: int , limit: int = 1 ,
                             ttl_sec: int = 120) -> bool:
                key = (msg_type , int(chat_id) , int(inviter_id_) , int(referral_id_))
                now = _time.time()
                rec = self._sent_msg_cache.get(key)
                if rec and (now - rec [ "ts" ] <= ttl_sec) and rec [ "count" ] >= limit:
                    print(f"[update_user_loose] 🔁 Skip duplicate msg: key={key} count={rec [ 'count' ]} ttl_ok")
                    return False
                if not rec or (now - rec [ "ts" ] > ttl_sec):
                    rec = {"count": 0 , "ts": now}
                rec [ "count" ] += 1
                rec [ "ts" ] = now
                self._sent_msg_cache [ key ] = rec
                print(f"[update_user_loose] ✅ Send allowed: key={key} new_count={rec [ 'count' ]}")
                return True

            # 4) Уведомления + refout
            try:
                if inviter_id and referral_id and will_notify:
                    print("[update_user_loose] ✉️ Готовлю уведомления и ссылки")
                    referral_first_name = await self.get_firstname_by_user_id(referral_id)
                    referral_username = await self.get_username_by_user_id(referral_id)
                    referral_link = await create_user_link(referral_id , referral_first_name , referral_username)
                    win_amount_formatted2 = "{:,.0f}".format(ref_coin).replace("," , ".")
                    print(f"[update_user_loose] 🔗 Ссылка на реферала: {referral_link}")

                    if _should_send("ping_inviter" , inviter_id , inviter_id , referral_id):
                        await bot1.send_message(
                            chat_id=inviter_id , text="🍀" , parse_mode="HTML" , disable_web_page_preview=True)
                        print(f"[update_user_loose] ✅ Пинг пригласителю: chat_id={inviter_id}")

                    if _should_send("inviter_notify" , inviter_id , inviter_id , referral_id):
                        print(f"[update_user_loose] ✉️ Отправляю уведомление пригласителю: chat_id={inviter_id}")
                        await bot1.send_message(
                            chat_id=inviter_id ,
                            text=(f"<b>🌿 Реферал засчитан, вы получили {win_amount_formatted2} кут!</b>\n"
                                  f"<b>🌴 {referral_link} прошёл(-ла) верификацию</b>") , parse_mode="HTML" ,
                            disable_web_page_preview=True)
                        print("[update_user_loose] ✅ Уведомление пригласителю отправлено")

                    if _should_send("referral_verified" , referral_id , inviter_id , referral_id):
                        verification_msg = (f"<b>🌿 Верификация реферальной системы пройдена!</b>\n"
                                            f"<b>🌴 Вы получили {win_amount_formatted2} кут</b>")
                        print(f"[update_user_loose] ✉️ Отправляю уведомление рефералу: chat_id={referral_id}")
                        await bot1.send_message(
                            chat_id=referral_id , text=verification_msg , parse_mode="HTML" ,
                            disable_web_page_preview=True)
                        print("[update_user_loose] ✅ Уведомление рефералу отправлено")

                    # Чистим refout по рефералу
                    deleted = await self.delete_refout_if_exists(referral_id)
                    if deleted:
                        print(f"[update_user_loose] 🧹 Удалил запись refout для referral_id={referral_id}")
                    else:
                        print(
                            f"[update_user_loose] ℹ️ Записи refout для referral_id={referral_id} не было - ничего не делал")
                else:
                    print("[update_user_loose] ℹ️ Верификация не производилась - уведомления не требуются")

            except Exception as e:
                print(f"[update_user_loose] ❗ Ошибка при отправке уведомлений: {e}")

        print(f"[update_user_loose] 🏁 Завершение функции для user_id={user_id}")

    async def get_refferer_id_or_error(self , user_id: int) -> int:
        """
        Возвращает refferer_id для заданного user_id.
        Если пользователь не найден в таблице users или refferer_id не задан,
        возбуждает LookupError с понятным текстом.

        :raises ValueError: если user_id не int
        :raises LookupError: если пользователя нет в users или не задан refferer_id
        :return: int refferer_id
        """
        if not isinstance(user_id , int):
            raise ValueError(f"user_id должен быть int, а не {type(user_id).__name__}")

        query = "SELECT refferer_id FROM users WHERE user_id = $1;"
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query , user_id)
        except Exception as e:
            # Ошибка доступа к БД - пробрасываем дальше (или заверни в RuntimeError, если нужно)
            raise

        if row is None:
            raise LookupError(f"Пользователь user_id={user_id} не найден в таблице users.")

        ref_val = row["refferer_id"]
        if ref_val is None:
            raise LookupError(f"Для user_id={user_id} не указан refferer_id.")

        # Нормализуем к int на случай строк/Decimal
        try:
            return int(ref_val)
        except Exception:
            raise LookupError(f"refferer_id для user_id={user_id} имеет некорректный тип/значение: {ref_val!r}")

    async def get_invitees_in(self , inviter_id , candidates):
        """
        Возвращает список user_id из candidates, у которых refferer_id == inviter_id.
        Без аннотаций типов. Некорректные элементы в candidates игнорируются.
        """
        # Нормализуем inviter_id к int
        try:
            inviter_id = int(inviter_id)
        except Exception:
            raise ValueError("inviter_id должен приводиться к int")

        # Соберём массив ID
        ids = [ ]
        if candidates:
            for x in candidates:
                try:
                    ids.append(int(x))
                except Exception:
                    continue  # пропускаем мусор
            ids = list(set(ids))  # дедуп

        if not ids:
            return [ ]

        sql = """
            SELECT user_id
            FROM users
            WHERE refferer_id = $1
              AND user_id = ANY($2::bigint[])
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql , inviter_id , ids)

        return [ r [ "user_id" ] for r in rows ]

    async def get_refferals_count(self , user_id: int) -> int:
        """
        Возвращает текущее количество приглашённых (users.refferals) для user_id.
        Если пользователя нет в таблице или значение NULL/некорректно - возвращает 0.
        """
        if not isinstance(user_id , int):
            raise ValueError(f"user_id должен быть int, а не {type(user_id).__name__}")

        sql = "SELECT COALESCE(refferals, 0) FROM users WHERE user_id = $1;"
        try:
            async with self.pool.acquire() as conn:
                val = await conn.fetchval(sql , user_id)  # может быть None, int, str и т.п.
        except Exception as e:
            print(f"[ERROR] get_refferals_count(user_id={user_id}): {e}")
            return 0

        if val is None:
            return 0

        try:
            return int(val)
        except Exception:
            # На случай, если в БД лежит строка/Decimal и т.п., которые не привести
            return 0

    async def insert_refcheck_entry(self , user_id: int , ref_user_id: int , first_name: str , ref_first_name: str):
        """
        Создаёт/обновляет запись в refcheck для данного user_id.
        Если запись уже есть - перезаписывает поля и дату.
        Если записи нет - вставляет новую.
        Гарантия от дублей без UNIQUE: транзакция + advisory lock + финальная нормализация.
        """
        from datetime import datetime , timezone
        date = datetime.now(timezone.utc)

        print(
            f"[insert_refcheck_entry] ▶️ Старт | user_id={user_id} | ref_user_id={ref_user_id} | "
            f"first_name={first_name!r} | ref_first_name={ref_first_name!r} | date={date.isoformat()}")

        # (опционально) защита от самореферала
        if user_id == ref_user_id:
            print("[insert_refcheck_entry] ⛔ user_id == ref_user_id - самореферал, запись не создаю/не обновляю")
            return

        async with self.pool.acquire() as connection:
            print("[insert_refcheck_entry] 🔌 Подключение к БД получено")
            async with connection.transaction():
                print("[insert_refcheck_entry] 🔒 Транзакция начата")

                # Пер-пользовательская блокировка на время транзакции, чтобы параллельные клики не создавали дубли
                try:
                    await connection.execute("SELECT pg_advisory_xact_lock($1)" , int(user_id))
                    print("[insert_refcheck_entry] 🔐 Advisory lock получен (на user_id)")
                except Exception as e:
                    print(f"[insert_refcheck_entry] ⚠️ Не удалось получить advisory lock: {e}")

                # 1) Пробуем ОБНОВИТЬ существующую запись по user_id
                print("[insert_refcheck_entry] ✏️ UPDATE ... RETURNING")
                updated_row = await connection.fetchrow(
                    """
                    UPDATE refcheck
                       SET ref_user_id    = $2,
                           first_name     = $3,
                           ref_first_name = $4,
                           date           = $5
                     WHERE user_id       = $1
                 RETURNING user_id
                    """ , user_id , ref_user_id , first_name , ref_first_name , date)

                if updated_row:
                    print(f"[insert_refcheck_entry] ✅ Обновлена существующая запись для user_id={user_id}")
                else:
                    # 2) Не нашли - ВСТАВЛЯЕМ новую запись
                    print("[insert_refcheck_entry] ➕ Запись не найдена - выполняю INSERT")
                    await connection.execute(
                        """
                        INSERT INTO refcheck (user_id, ref_user_id, first_name, ref_first_name, date)
                        VALUES ($1, $2, $3, $4, $5)
                        """ , user_id , ref_user_id , first_name , ref_first_name , date)
                    print(f"[insert_refcheck_entry] ✅ Вставлена новая запись для user_id={user_id}")

                # 3) Нормализация: удалим возможные дубли по этому user_id
                # 3.1) Сначала уберём строки с другим ref_user_id (если такие были)
                print("[insert_refcheck_entry] 🧹 Удаляю строки с другим ref_user_id")
                del_status = await connection.execute(
                    "DELETE FROM refcheck WHERE user_id = $1 AND ref_user_id <> $2" , user_id , ref_user_id)
                print(f"[insert_refcheck_entry] 🧾 DELETE <> статус: {del_status}")

                # 3.2) Если вдруг остались дубликаты с тем же ref_user_id - оставим одну самую свежую
                # Используем ctid и window function, чтобы удалить все кроме одной
                print("[insert_refcheck_entry] 🧹 Удаляю возможные дубликаты, оставляя самую свежую запись")
                await connection.execute(
                    """
                    WITH ranked AS (
                        SELECT ctid,
                               row_number() OVER (PARTITION BY user_id ORDER BY date DESC, ctid DESC) AS rn
                        FROM refcheck
                        WHERE user_id = $1
                    )
                    DELETE FROM refcheck
                    WHERE ctid IN (SELECT ctid FROM ranked WHERE rn > 1)
                    """ , user_id)
                print("[insert_refcheck_entry] ✅ Нормализация завершена (по user_id остаётся ровно одна строка)")

            print("[insert_refcheck_entry] 🔓 Транзакция завершена")

        print(f"[insert_refcheck_entry] 🏁 Готово для user_id={user_id}")

    async def user_exists_in_chat1111(self , user_id , chat_id):
        """
        Проверяет, существует ли пользователь с указанным user_id и chat_id в таблице memberchat.

        :param user_id: ID пользователя
        :param chat_id: ID чата
        :return: Кортеж (True, список rowid) если дубликаты найдены, иначе (False, пустой список)
        """
        async with self.pool.acquire() as connection:
            # Запрашиваем все строки с данным user_id и chat_id
            rows = await connection.fetch(
                "SELECT rowid FROM memberchat WHERE user_id = $1 AND chat_id = $2" , user_id , chat_id)

            # Проверяем, есть ли больше одной записи
            if len(rows) > 1:
                # Возвращаем True и список rowid для всех записей-дубликатов
                return True , [ row [ 'rowid' ] for row in rows ]
            else:
                # Если запись только одна или отсутствует, возвращаем False и пустой список
                return False , [ ]

    async def delete_duplicate_users_from_chat(self , rowids):
        """
        Удаляет все строки, rowid которых находятся в списке дубликатов, кроме первой записи.

        :param rowids: Список rowid дубликатов
        """
        async with self.pool.acquire() as connection:
            # Удаляем все строки, rowid которых находятся в списке дубликатов, начиная со второго
            query = "DELETE FROM memberchat WHERE rowid = $1"
            for rowid in rowids [ 1: ]:  # Оставляем первую запись, начиная с индекса 1
                await connection.execute(query , rowid)

    async def remove_member(self , chat_id , user_id):
        """
        Удаляет пользователя из чата по chat_id и user_id.

        :param chat_id: Идентификатор чата
        :param user_id: Идентификатор пользователя
        """
        async with self.pool.acquire() as connection:
            query = "DELETE FROM memberchat WHERE chat_id = $1 AND user_id = $2"
            await connection.execute(query , chat_id , user_id)
    async def get_users_by_chat_id(self, chat_id):
        """Получаем всех пользователей для указанного chat_id."""
        async with self.pool.acquire() as connection:
            query = "SELECT user_id, name FROM memberchat WHERE chat_id = $1"
            result = await connection.fetch(query, chat_id)
            return result

    async def user_exists_in_chat_telethone(self , user_id , chat_id):
        """
        Проверяет наличие пользователя в чате по его user_id и chat_id.

        :param user_id: ID пользователя
        :param chat_id: ID чата
        :return: True, если запись существует, иначе False
        """
        async with self.pool.acquire() as connection:
            query = "SELECT COUNT(*) FROM memberchat WHERE user_id = $1 AND chat_id = $2"
            result = await connection.fetchval(query , user_id , chat_id)
            return result > 0  # Возвращаем True, если запись найдена, иначе False
    async def user_exists_in_chat(self, user_id, chat_id):
        """Проверяет, существует ли пользователь в базе данных для указанного чата."""
        try:
            async with self.pool.acquire() as connection:
                query = "SELECT 1 FROM memberchat WHERE user_id = $1 AND chat_id = $2"
                result = await connection.fetchrow(query, user_id, chat_id)
                return bool(result)  # Если результат найден, возвращаем True, иначе False
        except Exception as e:
            print(f"Ошибка при проверке существования пользователя: {e}")
            return False
    #async def user_exists_in_chat_telethone(self, user_id, chat_id):
        #"""Проверяет, существует ли пользователь с данным user_id и chat_id в базе данных."""
        #try:
            # Выполняем запрос с использованием асинхронного метода fetchval
            #query = "SELECT COUNT(*) FROM memberchat WHERE user_id = $1 AND chat_id = $2"
            #result = await self.connection.fetchval(query, user_id, chat_id)
            #return result > 0  # Возвращаем True, если запись существует, иначе False
        #except Exception as e:
            #print(f"Ошибка при проверке существования пользователя: {e}")
            #return False
    async def add_user_to_chat_telethone(self, user_id, name, username, chat_id, chat_name, data):
        """Добавление пользователя в чат"""
        if await self.user_exists_in_chat(user_id, chat_id):
            print(f"Пользователь с user_id {user_id} уже существует в чате {chat_name}.")
        else:
            try:
                # Если пользователя нет в базе, добавляем его
                async with self.pool.acquire() as connection:
                    query = """
                    INSERT INTO memberchat (user_id, name, username, chat_id, chat_name, data)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """
                    await connection.execute(query, user_id, name, username, chat_id, chat_name, data)
                    print(f"Пользователь {name} ({username}) добавлен в базу данных чата {chat_name}.")
            except Exception as e:
                print(f"Ошибка при добавлении пользователя в чат1 {chat_name}: {e}")
    async def add_user_to_chat(self, user_id, name, username, chat_id, chat_name, data):
        """Добавление пользователя в чат"""
        if self.pool is None:
            print("Ошибка: Пул соединений не инициализирован.")
            return

        if await self.user_exists_in_chat(user_id, chat_id):
            print(f"Пользователь с user_id {user_id} уже существует в чате {chat_name}.")
        else:
            try:
                # Если пользователя нет в базе, добавляем его
                async with self.pool.acquire() as connection:
                    query = """
                    INSERT INTO memberchat (user_id, name, username, chat_id, chat_name, data)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """
                    await connection.execute(query, user_id, name, username, chat_id, chat_name, data)
                    print(f"Пользователь {name} ({username}) добавлен в базу данных чата {chat_name}.")
            except Exception as e:
                print(f"Ошибка при добавлении пользователя в чат2 {chat_name}: {e}")

    async def _get_user_emoji_field(self, user_id, column: str) -> str:
        """Возвращает кастомный emoji-тег из users.<column> или дефолт (никогда False)."""
        default = _USER_EMOJI_DEFAULTS.get(column, "")
        if not await self.ensure_pool():
            return default
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    f"SELECT {column} FROM users WHERE user_id = $1",
                    user_id,
                )
                if result and result[column] is not None:
                    return result[column]
                return default
        except Exception as e:
            print(f"Ошибка при запросе {column}: {e}")
            return default

    async def check_user_id_in_idemo(self, user_id):
        return await self._get_user_emoji_field(user_id, "idemo")

    async def check_user_id_in_nameemo(self, user_id):
        return await self._get_user_emoji_field(user_id, "nameemo")

    async def check_user_id_in_usernameemo(self, user_id):
        return await self._get_user_emoji_field(user_id, "usernameemo")

    async def check_user_id_in_balanceemo(self, user_id):
        return await self._get_user_emoji_field(user_id, "balanceemo")

    async def check_user_id_in_winamountemo(self, user_id):
        return await self._get_user_emoji_field(user_id, "winamountemo")

    async def check_user_id_in_marryemo(self, user_id):
        return await self._get_user_emoji_field(user_id, "marryemo")

    async def check_user_id_in_repemo(self, user_id):
        return await self._get_user_emoji_field(user_id, "repemo")

    async def check_user_id_in_prgl(self, user_id):
        return await self._get_user_emoji_field(user_id, "prgl")

    async def check_user_id_in_limitemo(self, user_id):
        return await self._get_user_emoji_field(user_id, "limitemo")

    async def check_user_id_in_refemo(self, user_id):
        return await self._get_user_emoji_field(user_id, "refemo")

    async def check_user_id_in_dataemo(self, user_id):
        return await self._get_user_emoji_field(user_id, "dataemo")

    _PROFILE_BUNDLE_TTL_SEC = 45.0

    def invalidate_profile_bundle_cache(self, user_id: int) -> None:
        cache = getattr(self, "_profile_bundle_cache", None)
        if isinstance(cache, dict):
            cache.pop(int(user_id), None)

    async def fetch_profile_render_bundle(
        self, user_id: int, *, use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Один SQL round-trip для отрисовки профиля (вместо 25+ запросов)."""
        if not self.pool:
            return None
        uid = int(user_id)
        if use_cache:
            if not hasattr(self, "_profile_bundle_cache"):
                self._profile_bundle_cache: Dict[int, Tuple[float, Dict[str, Any]]] = {}
            cached = self._profile_bundle_cache.get(uid)
            if cached:
                ts, payload = cached
                if (time.monotonic() - ts) < self._PROFILE_BUNDLE_TTL_SEC:
                    return payload
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT u.user_id, u.first_name, u.username, u.balance, u.data,
                           u.refferals, u.xpp, u.country,
                           u.idemo, u.nameemo, u.usernameemo, u.balanceemo, u.winamountemo,
                           u.marryemo, u.repemo, u.limitemo, u.refemo, u.prgl, u.dataemo,
                           u.wins, u.loose, u.winamount, u.donate, u.canwithdrawal, u.give,
                           u.rep_plus, u.rep_minus,
                           ref.first_name AS referer_name,
                           m.kube, m.boul, m.basket, m.slots, m.trade, m.crash, m.mine,
                           m.tank, m.roul, m.kazik, m.lot, m.ball, m.knb,
                           (b.user_id IS NOT NULL) AS is_banned
                    FROM users u
                    LEFT JOIN users ref ON ref.user_id = u.refferer_id
                    LEFT JOIN moneyachiv m ON m.user_id = u.user_id
                    LEFT JOIN banusers b ON b.user_id = u.user_id
                    WHERE u.user_id = $1
                    """,
                    uid,
                )
            if not row:
                return None

            game_cols = (
                "kube", "boul", "basket", "slots", "trade", "crash", "mine",
                "tank", "roul", "kazik", "lot", "ball", "knb",
            )
            total_games = sum(
                int(row[col]) if row.get(col) is not None and str(row[col]).isdigit() else 0
                for col in game_cols
            )
            user_row = row
            banned_flag = bool(row.get("is_banned"))

            def _em(col: str, default_key: str) -> str:
                raw = user_row.get(col)
                if raw and raw is not False:
                    return str(raw)
                return _USER_EMOJI_DEFAULTS.get(default_key, "")

            bundle = {
                "user_id": uid,
                "first_name": user_row.get("first_name") or "",
                "username": user_row.get("username") or "",
                "balance": user_row.get("balance") or 0,
                "date": user_row.get("data"),
                "referrals": user_row.get("refferals") or 0,
                "xpp": user_row.get("xpp") or 0,
                "country_emoji": user_row.get("country") or "",
                "referer_name": user_row.get("referer_name"),
                "give_limite": user_row.get("give") or 0,
                "reputation_plus1": user_row.get("rep_plus") or 0,
                "reputation_minus1": user_row.get("rep_minus") or 0,
                "wins": user_row.get("wins") or 0,
                "loose": user_row.get("loose") or 0,
                "winamount": user_row.get("winamount") or 0,
                "donated": user_row.get("donate") or 0,
                "canwithdrawalunt": user_row.get("canwithdrawal") or 0,
                "is_banned": banned_flag,
                "total_games_played": total_games,
                "id_emoji": _em("idemo", "idemo"),
                "username_emoji": _em("usernameemo", "usernameemo"),
                "name_emoji": _em("nameemo", "nameemo"),
                "balance_emoji": _em("balanceemo", "balanceemo"),
                "winamount_emoji": _em("winamountemo", "winamountemo"),
                "marry_emoji": _em("marryemo", "marryemo"),
                "rep_emoji": _em("repemo", "repemo"),
                "limit_emoji": _em("limitemo", "limitemo"),
                "ref_emoji": _em("refemo", "refemo"),
                "prlg_emoji": _em("prgl", "prgl"),
                "data_emoji": _em("dataemo", "dataemo"),
            }
            if use_cache:
                if not hasattr(self, "_profile_bundle_cache"):
                    self._profile_bundle_cache = {}
                self._profile_bundle_cache[uid] = (time.monotonic(), bundle)
            return bundle
        except Exception as e:
            _safe_log(f"[DB][WARN] fetch_profile_render_bundle({uid}): {type(e).__name__}: {e}")
            return None

    async def fetch_column_value(self, user_id, column_name):
        """
        Получает значение из указанного столбца для определенного user_id.
        Возвращает:
            Значение из столбца, если оно существует, иначе None.
        """
        try:
            async with self.pool.acquire() as connection:
                # Формируем SQL запрос с параметризированным столбцом
                query = f"SELECT {column_name} FROM users WHERE user_id = $1"
                result = await connection.fetchrow(query, user_id)

                if result:
                    return result[column_name]  # Возвращаем значение столбца
                else:
                    return None  # Если нет результата, возвращаем None
        except Exception as e:
            print(f"Ошибка при запросе: {e}")
            return None

    async def reset_column_value_if_exists(self, user_id, column_name):
        """
        Проверяет наличие значения в указанном столбце для user_id и сбрасывает его, если оно установлено.
        Возвращает:
            str: Сообщение о результате операции.
        """
        # Получаем значение из указанного столбца
        value = await self.fetch_column_value(user_id, column_name)

        if value:
            try:
                async with self.pool.acquire() as connection:
                    # Сбрасываем значение столбца на NULL
                    query = f"UPDATE users SET {column_name} = NULL WHERE user_id = $1"
                    await connection.execute(query, user_id)
                    return "✅ Эмодзи строки успешно сброшено"
            except Exception as e:
                print(f"Ошибка при обновлении столбца: {e}")
                return "💭 Произошла ошибка при сбросе значения."
        else:
            return "💭 Эмодзи строки отсутствует."

    async def find_item_name_by_emoji(self, emoji):
        """
        Находит название предмета по эмодзи из таблицы dex.
        Возвращает:
            str: Название предмета или None, если предмет не найден.
        """
        try:
            async with self.pool.acquire() as connection:
                query = "SELECT name FROM dex WHERE emoji = $1"
                result = await connection.fetchrow(query, emoji)

                if result:
                    return result['name']  # Возвращаем название предмета
                return None  # Если ничего не найдено, возвращаем None
        except Exception as e:
            print(f"Ошибка при поиске предмета: {e}")
            return None

    async def get_group_balances(self):
        """Получение деталей группы, включая ID, баланс, имя и username из таблицы chat,
        с учетом только chatbalance (dexbalance заморожен).
        Код находит только группы, где usernamechat существует и не равен 'username отсутствует'.
        """
        if not self.pool:
            print("Ошибка: Пул соединений не инициализирован.")
            return None

        try:
            async with self.pool.acquire() as connection:
                query_with_creator = """
                    SELECT 
                        chat_id, 
                        chatbalance, 
                        dexbalance, 
                        chatbalance AS total_balance, 
                        creator_id,
                        namechat, 
                        usernamechat 
                    FROM chat
                    WHERE usernamechat IS NOT NULL
                    AND usernamechat != 'username отсутствует'
                """
                query_without_creator = """
                    SELECT 
                        chat_id, 
                        chatbalance, 
                        dexbalance, 
                        chatbalance AS total_balance, 
                        namechat, 
                        usernamechat 
                    FROM chat
                    WHERE usernamechat IS NOT NULL
                    AND usernamechat != 'username отсутствует'
                """
                try:
                    result = await connection.fetch(query_with_creator)
                except Exception as qerr:
                    print(f"[get_group_balances] fallback без creator_id: {qerr}")
                    result = await connection.fetch(query_without_creator)
                return result
        except Exception as e:
            print(f"Ошибка при получении данных о группах: {e}")
            return None

    async def get_group_economy_pressure_snapshot(self, per_group_threshold: int = 20000) -> Dict[str, Any]:
        """
        Сводка давления экономики по группам для Jericho:
        - groups_total: сумма chatbalance по всем группам
        - total_excess: суммарный «лишек» только по группам выше per_group_threshold
        - creator_excess_map: лишек, агрегированный по creator_id
        """
        if not self.pool:
            return {
                "groups_total": 0,
                "total_excess": 0,
                "hot_groups": 0,
                "creator_excess_map": {},
                "creator_hot_groups_map": {},
                "per_group_threshold": int(max(0, per_group_threshold)),
            }

        threshold = int(max(0, per_group_threshold))
        base_result: Dict[str, Any] = {
            "groups_total": 0,
            "total_excess": 0,
            "hot_groups": 0,
            "creator_excess_map": {},
            "creator_hot_groups_map": {},
            "per_group_threshold": threshold,
        }

        try:
            async with self.pool.acquire() as connection:
                totals_row = await connection.fetchrow(
                    """
                    SELECT
                        COALESCE(SUM(COALESCE(chatbalance, 0)), 0)::bigint AS groups_total,
                        COALESCE(
                            SUM(GREATEST(COALESCE(chatbalance, 0) - $1, 0)),
                            0
                        )::bigint AS total_excess,
                        COUNT(*) FILTER (
                            WHERE COALESCE(chatbalance, 0) > $1
                        )::int AS hot_groups
                    FROM chat
                    """,
                    threshold,
                )

                if totals_row:
                    base_result["groups_total"] = int(totals_row["groups_total"] or 0)
                    base_result["total_excess"] = int(totals_row["total_excess"] or 0)
                    base_result["hot_groups"] = int(totals_row["hot_groups"] or 0)

                # В старых схемах creator_id может отсутствовать — тогда просто вернём общую сводку.
                try:
                    creator_rows = await connection.fetch(
                        """
                        SELECT
                            creator_id,
                            SUM(
                                GREATEST(COALESCE(chatbalance, 0) - $1, 0)
                            )::bigint AS creator_excess,
                            COUNT(*) FILTER (
                                WHERE COALESCE(chatbalance, 0) > $1
                            )::int AS creator_hot_groups
                        FROM chat
                        WHERE creator_id IS NOT NULL
                        GROUP BY creator_id
                        HAVING SUM(
                            GREATEST(COALESCE(chatbalance, 0) - $1, 0)
                        ) > 0
                        ORDER BY creator_excess DESC
                        """,
                        threshold,
                    )
                except Exception as creator_err:
                    print(f"[PRESSURE] creator breakdown недоступен: {creator_err}")
                    creator_rows = []

                creator_excess_map: Dict[int, int] = {}
                creator_hot_groups_map: Dict[int, int] = {}
                for row in creator_rows:
                    try:
                        creator_id = int(row["creator_id"])
                    except Exception:
                        continue
                    creator_excess_map[creator_id] = int(row["creator_excess"] or 0)
                    creator_hot_groups_map[creator_id] = int(row["creator_hot_groups"] or 0)

                base_result["creator_excess_map"] = creator_excess_map
                base_result["creator_hot_groups_map"] = creator_hot_groups_map

            return base_result
        except Exception as e:
            print(f"[PRESSURE] Ошибка сводки по группам: {e}")
            return base_result

    async def get_jericho_mode_metrics(self, sample_size: int = 5000) -> Dict[str, Any]:
        """
        Быстрая сводка по фактическим исходам demo/0demo в истории игр.
        Берёт последние sample_size записей из cutehistory, где фигурирует demo.
        """
        sample = int(max(100, min(200000, sample_size)))
        fallback: Dict[str, Any] = {
            "sample_size": sample,
            "rows_considered": 0,
            "demo_wins": 0,
            "demo_losses": 0,
            "zero_demo_wins": 0,
            "zero_demo_losses": 0,
        }

        if not self.pool:
            return fallback

        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    """
                    SELECT
                        COUNT(*)::int AS rows_considered,
                        COUNT(*) FILTER (
                            WHERE cause LIKE '+ %'
                              AND cause ILIKE '%demo%'
                              AND cause NOT ILIKE '%0demo%'
                        )::int AS demo_wins,
                        COUNT(*) FILTER (
                            WHERE cause LIKE '- %'
                              AND cause ILIKE '%demo%'
                              AND cause NOT ILIKE '%0demo%'
                        )::int AS demo_losses,
                        COUNT(*) FILTER (
                            WHERE cause LIKE '+ %'
                              AND cause ILIKE '%0demo%'
                        )::int AS zero_demo_wins,
                        COUNT(*) FILTER (
                            WHERE cause LIKE '- %'
                              AND cause ILIKE '%0demo%'
                        )::int AS zero_demo_losses
                    FROM (
                        SELECT cause
                        FROM cutehistory
                        WHERE cause ILIKE '%demo%'
                        ORDER BY data DESC
                        LIMIT $1
                    ) s
                    """,
                    sample,
                )

            if not row:
                return fallback

            return {
                "sample_size": sample,
                "rows_considered": int(row["rows_considered"] or 0),
                "demo_wins": int(row["demo_wins"] or 0),
                "demo_losses": int(row["demo_losses"] or 0),
                "zero_demo_wins": int(row["zero_demo_wins"] or 0),
                "zero_demo_losses": int(row["zero_demo_losses"] or 0),
            }
        except Exception as e:
            print(f"[JERICHO][METRICS] Ошибка чтения метрик: {e}")
            return fallback


    async def get_user_referrals(self):
        """Запрос для получения идентификаторов пользователей и их приглашений."""
        if not self.pool:
            print("Ошибка: Пул соединений не инициализирован.")
            return None

        try:
            async with self.pool.acquire() as connection:
                query = "SELECT user_id, refferals FROM users WHERE refferals IS NOT NULL"
                referrals = await connection.fetch(query)
                return referrals  # Возвращаем список кортежей (user_id, referrals)
        except Exception as e:
            print(f"Ошибка при получении данных о пользователях и их приглашениях: {e}")
            return None

    async def get_random_chat(self):
        """Получить случайный chat_id из публичных групп (с установленным username)."""
        if not self.pool:
            print("Ошибка: Пул соединений не инициализирован.")
            return None

        try:
            async with self.pool.acquire() as connection:
                # SQL запрос для получения случайного chat_id из групп с установленным username
                query = """
                    SELECT chat_id 
                    FROM chat 
                    WHERE usernamechat != 'username отсутствует'
                    ORDER BY RANDOM() 
                    LIMIT 1
                """
                result = await connection.fetchrow(query)

                # Возвращаем chat_id, если он найден, иначе None
                return result [ 'chat_id' ] if result else None
        except Exception as e:
            print(f"Ошибка при запросе в БД: {e}")
            return None

    async def get_invitetop(self , user_id):
        """Получить текущее значение invitetop для пользователя."""
        query = "SELECT invitetop FROM users WHERE user_id = $1"
        async with self.pool.acquire() as connection:
            result = await connection.fetch(query , user_id)

        # Проверка результата
        if result and result [ 0 ] [ 'invitetop' ] is not None:
            return Decimal(result [ 0 ] [ 'invitetop' ]).quantize(Decimal('0.00') , rounding=ROUND_DOWN)
        return Decimal('0.00')

    async def update_invitetop_values(self):
        """Обновление значения invitetop для топ-3 пользователей и остальных пользователей."""

        # Получаем данные: user_id и количество приглашений
        query = "SELECT user_id, refferals FROM users"
        async with self.pool.acquire() as connection:
            data = await connection.fetch(query)

        user_referrals = {item [ 'user_id' ]: item [ 'refferals' ] for item in data if item [ 'refferals' ] is not None}
        sorted_users = sorted(user_referrals.items() , key=lambda x: x [ 1 ] , reverse=True)

        top_referrers = {}
        top_limits = {1: Decimal('0.50') , 2: Decimal('0.40') , 3: Decimal('0.35')}
        user_updates = {}  # Словарь для хранения обновлений

        # Собираем обновления для топ-3
        for rank , (user_id , referrals) in enumerate(sorted_users [ :3 ] , start=1):
            top_referrers [ rank ] = {'user_id': user_id , 'referrals': referrals ,
                                      'referrals_formatted': locale.format_string(
                                          "%d" , referrals , grouping=True).replace("," , ".")}
            current_value = await self.get_invitetop(user_id)
            limit = top_limits [ rank ]

            # Определяем новое значение
            new_value = limit if current_value >= limit else current_value + (
                limit - current_value if current_value < limit else 0)
            user_updates [ user_id ] = new_value

        # Обновление значений для топ-3 пользователей в одном запросе
        if user_updates:
            query = """
                UPDATE users
                SET invitetop = CASE user_id
                    {cases}
                END
                WHERE user_id = ANY($1)
            """
            case_statements = [ ]
            params = [ list(user_updates.keys()) ]  # Передаем список в качестве параметра для IN
            for user_id , new_value in user_updates.items():
                case_statements.append(f"WHEN {user_id} THEN {new_value}")

            # Формирование параметров для IN-выражения
            query = query.format(cases=" ".join(case_statements))

            # Выполнение запроса
            async with self.pool.acquire() as connection:
                await connection.execute(query , *params)

        # Обновляем invitetop для пользователей с 0.50, 0.40 и 0.35, которые не в топ-3
        non_top_values = [ Decimal('0.50') , Decimal('0.40') , Decimal('0.35') ]
        top_user_ids = {user_info [ 'user_id' ] for user_info in top_referrers.values()}

        # Получаем список ID пользователей с текущими значениями invitetop
        query = "SELECT user_id, invitetop FROM users WHERE invitetop = ANY($1)"
        async with self.pool.acquire() as connection:
            users_with_values = await connection.fetch(query , [ str(val) for val in non_top_values ])

        # Обновляем invitetop для пользователей, не входящих в топ-3
        if users_with_values:
            params = [ user_id for user_id , invitetop in users_with_values if user_id not in top_user_ids ]
            if params:  # Проверяем, есть ли параметры для обновления
                query = "UPDATE users SET invitetop = 0.25 WHERE user_id = ANY($1)"
                async with self.pool.acquire() as connection:
                    await connection.execute(query , params)

















#

    async def update_give(self, user_id):
        """Обновление значения give для пользователя."""
        # Получаем текущее значение столбца give
        query = "SELECT give FROM users WHERE user_id = $1"
        async with self.pool.acquire() as connection:
            result = await connection.fetch(query, user_id)

        if result:  # Проверяем, что пользователь существует
            current_value = result[0]['give'] or 0  # Если значение None, заменяем на 0
            new_value = current_value + 20

            # Обновляем значение в базе данных
            update_query = "UPDATE users SET give = $1 WHERE user_id = $2"
            async with self.pool.acquire() as connection:
                await connection.execute(update_query, new_value, user_id)

            return new_value
        else:
            print(f"Пользователь с ID {user_id} не найден.")
            return None

    async def c(self , user_id):
        """Удаление пользователя из таблицы givetime по user_id."""
        try:
            delete_query = "DELETE FROM givetime WHERE user_id = $1"
            async with self.pool.acquire() as connection:
                await connection.execute(delete_query , user_id)

            print(f"[DEBUG] Пользователь {user_id} удалён из таблицы givetime.")
        except Exception as e:
            print(f"[ERROR] Ошибка при удалении пользователя {user_id} из таблицы givetime: {str(e)}")

    async def remove_user_give_limit(self , user_id):
        """Удаление пользователя из таблицы givelimit по user_id."""
        try:
            delete_query = "DELETE FROM givelimit WHERE user_id = $1"
            async with self.pool.acquire() as connection:
                await connection.execute(delete_query , user_id)

            print(f"[DEBUG] Пользователь {user_id} удалён из таблицы givelimit.")
        except Exception as e:
            print(f"[ERROR] Ошибка при удалении пользователя {user_id} из таблицы givelimit: {str(e)}")

    async def remove_expired_give_times(self):
        """Удаление устаревших записей из таблицы givetime."""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Преобразуем datetime в строку

        try:
            delete_query = "DELETE FROM givetime WHERE data_over < $1"
            async with self.pool.acquire() as connection:
                await connection.execute(delete_query , current_time)

            print(f"[DEBUG] Устаревшие записи из таблицы givetime удалены.")
        except Exception as e:
            print(f"[ERROR] Ошибка при удалении устаревших записей из givetime: {str(e)}")

    async def remove_expired_give_limits(self):
        """Удаление устаревших записей из таблицы givelimit."""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Преобразуем datetime в строку

        try:
            delete_query = "DELETE FROM givelimit WHERE data_over1 < $1"
            async with self.pool.acquire() as connection:
                await connection.execute(delete_query , current_time)

            print(f"[DEBUG] Устаревшие записи из таблицы givelimit удалены.")
        except Exception as e:
            print(f"[ERROR] Ошибка при удалении устаревших записей из givelimit: {str(e)}")
    async def remove_user_give(self, user_id):
        """Удаление пользователя из таблицы бонусов."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для удаления бонуса пользователя
                await connection.execute(
                    "DELETE FROM givetime WHERE user_id = $1",
                    user_id
                )
                print(f"Пользователь {user_id} удалён из таблицы бонусов.")
        except Exception as e:
            print(f"Ошибка при удалении пользователя: {str(e)}")
    async def check_and_remove_expired_give_times(self):
        """Проверка текущих записей пользователей и удаление устаревших записей."""
        current_time = datetime.now()  # Получаем текущее время

        try:
            # Извлечение всех идентификаторов пользователей из таблицы givetime
            query = "SELECT user_id FROM givetime"
            async with self.pool.acquire() as connection:
                users_with_give_times = await connection.fetch(query)

            for user in users_with_give_times:
                user_id = user['user_id']  # Извлекаем user_id

                # Проверка, есть ли у пользователя устаревшая запись в givetime
                query = "SELECT data_over FROM givetime WHERE user_id = $1"
                async with self.pool.acquire() as connection:
                    give_time_record = await connection.fetchrow(query, user_id)

                if give_time_record:
                    data_over = give_time_record['data_over']
                    try:
                        # Преобразование строки в объект datetime
                        data_over_datetime = datetime.strptime(data_over, '%Y-%m-%d %H:%M:%S')

                        if data_over_datetime < current_time:
                            await self.remove_user_give(user_id)  # Удаление пользователя с устаревшей записью
                            await self.remove_user_give_limit(user_id)  # Удаление записи из givelimit
                            print(f"[DEBUG] Устаревшая запись для пользователя {user_id} удалена из обеих таблиц.")
                    except ValueError:
                        print(f"[ERROR] Неверный формат времени для пользователя {user_id}: {data_over}")

            # Удаление всех устаревших записей из таблицы givetime
            await self.remove_expired_give_times()
            # Удаление всех устаревших записей из таблицы givelimit
            await self.remove_expired_give_limits()

        except Exception as e:
            print(f"[ERROR] Ошибка при обработке и удалении устаревших записей: {str(e)}")

    async def get_give_times(self , user_id):
        """Получает время последней передачи и окончания срока."""
        try:
            query = "SELECT data, data_over FROM givetime WHERE user_id = $1 ORDER BY data DESC LIMIT 1"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , user_id)

            return result if result else (None , None)

        except Exception as e:
            print(f"[ERROR] Ошибка при получении данных времени передачи для пользователя {user_id}: {str(e)}")
            return (None , None)

    async def update_give_time(self, user_id, chat_id, chat_name, user_name, user_username, last_open, data_over):
        """Обновляет запись о передаче денег с ограничением по времени для указанного пользователя."""
        try:
            query = """
                UPDATE givetime 
                SET chat_id = $1, chat_name = $2, user_name = $3, user_username = $4, data = $5, data_over = $6
                WHERE user_id = $7
            """
            async with self.pool.acquire() as connection:
                await connection.execute(query, chat_id, chat_name, user_name, user_username, last_open, data_over, user_id)

            print(f"Запись для пользователя {user_id} обновлена до {data_over}.")
        except Exception as e:
            print(f"Ошибка при обновлении записи для пользователя {user_id}: {str(e)}")

    async def check_user_in_givetime(self, user_id):
        """Проверяет, существует ли пользователь в таблице givetime по user_id."""
        try:
            query = "SELECT * FROM givetime WHERE user_id = $1"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query, user_id)

            if result:
                print(f"[DEBUG] Пользователь {user_id} найден в таблице givetime.")
                return result  # Возвращаем всю запись о пользователе, если он найден
            else:
                print(f"[DEBUG] Пользователь {user_id} не найден в таблице givetime.")
                return None  # Если пользователя нет, возвращаем None

        except Exception as e:
            print(f"[ERROR] Ошибка при проверке пользователя {user_id} в таблице givetime: {str(e)}")
            return None  # Возвращаем None в случае ошибки

    async def add_give_time(self , chat_id , chat_name , user_id , user_name , user_username , last_open , data_over):
        """Добавляет запись о передаче денег с ограничением по времени."""
        try:
            query = """
            INSERT INTO givetime (chat_id, chat_name, user_id, user_name, user_username, data, data_over)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            async with self.pool.acquire() as connection:
                await connection.execute(
                    query , chat_id , chat_name , user_id , user_name , user_username , last_open , data_over)

            print(f"Запись для пользователя {user_id} добавлена до {data_over}.")
        except Exception as e:
            print(f"Ошибка при добавлении записи для пользователя {user_id}: {str(e)}")

    async def get_daily_give_sum(self , user_id):
        """Получает сумму значений столбца give для указанного пользователя за текущую дату."""
        # Получаем текущую дату без времени
        current_date = datetime.now().date()  # Это возвращает объект datetime.date, а не строку.

        query = """
        SELECT SUM(give) 
        FROM givelimit 
        WHERE user_id = $1 AND DATE(data) = $2
        """
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchval(query , user_id , current_date)

            return result if result else 0  # Если нет записей, вернуть 0
        except Exception as e:
            print(f"[ERROR] Ошибка при получении суммы для пользователя {user_id}: {str(e)}")
            return 0  # В случае ошибки возвращаем 0

    async def add_to_user_give(self , user_id , amount):
        """Добавляет указанную сумму к текущему значению в столбце give для пользователя."""
        query = "SELECT give FROM users WHERE user_id = $1"
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , user_id)

            if result:  # Если пользователь найден
                current_give = result [ 'give' ]  # Получаем текущее значение give
                new_give = current_give + amount  # Добавляем указанную сумму к текущему значению
                update_query = "UPDATE users SET give = $1 WHERE user_id = $2"

                async with self.pool.acquire() as connection:
                    await connection.execute(update_query , new_give , user_id)  # Обновляем запись

                print(f"Сумма для пользователя {user_id} обновлена: {new_give}")
            else:
                print(f"Пользователь с ID {user_id} не найден.")
        except Exception as e:
            print(f"[ERROR] Ошибка при добавлении суммы для пользователя {user_id}: {str(e)}")

    async def get_user_give_limit(self , user_id):
        """Возвращает лимит передачи для указанного пользователя."""
        query = "SELECT give FROM users WHERE user_id = $1"
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , user_id)

            return result [ 'give' ] if result else 0  # Если пользователь не найден, возвращаем 0
        except Exception as e:
            print(f"[ERROR] Ошибка при получении лимита для пользователя {user_id}: {str(e)}")
            return 0  # Возвращаем 0 в случае ошибки

    async def add_give_limit(self, user_id, user_name, user_username, give, chat_id, chat_name, time_to_remove_give):
        """Добавляет запись в таблицу givelimit с данными пользователя и чата, включая дату окончания."""
        current_time = datetime.now()  # Получаем текущее время
        current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')  # Форматируем текущее время

        # Рассчитываем дату окончания
        data_over1 = current_time + timedelta(seconds=time_to_remove_give)
        data_over1_str = data_over1.strftime("%Y-%m-%d %H:%M:%S")  # Форматируем дату окончания в строку

        query = """
        INSERT INTO givelimit (user_id, user_name, user_username, give, chat_id, chat_name, data, data_over1) 
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """

        try:
            async with self.pool.acquire() as connection:
                await connection.execute(
                    query,
                    user_id, user_name, user_username, give, chat_id, chat_name, current_time_str, data_over1_str
                )
            print(f"[DEBUG] Запись для пользователя {user_id} добавлена с ограничением до {data_over1_str}.")
        except Exception as e:
            print(f"[ERROR] Ошибка при добавлении записи для пользователя {user_id}: {str(e)}")















    # ============================================================
    # ✅ 4) cooldown: удалить истёкший (как у тебя)
    # ============================================================
    async def _delete_user_cooldown_if_expired(self, conn, user_id: int) -> bool:
        """
        ✅ У тебя уже было - оставил под твою схему.
        """
        _vdbg(f"[ЛИМИТЫ][DEBUG] Проверяю истёкший кулдаун пользователя {user_id}")
        try:
            res = await conn.execute(
                """
                DELETE FROM withdraw_cooldown
                WHERE user_id = $1 AND until_at <= NOW()
                """,
                int(user_id)
            )
            deleted = int(res.split()[-1])
        except Exception as e:
            _vdbg(f"[ЛИМИТЫ][ERROR] Ошибка при удалении кулдауна: {e}")
            deleted = 0

        if deleted > 0:
            _vdbg(f"[ЛИМИТЫ][DEBUG] Кулдаун истёк → удалён, окно будет сброшено")
        return deleted > 0

    # ---------------------------------------------------------------
    async def get_today_withdrawn(self , user_id: int) -> int:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval(SQL_TODAY_SUM , user_id)
            return int(val or 0)

        # ============================================================
        # ✅ 10) Диагностика: started_at окна
        # ============================================================
        async def get_quota_window_started_at(self , user_id: int):
            uid = int(user_id)
            async with self.pool.acquire() as conn:
                val = await conn.fetchval(
                    "SELECT window_started_at FROM withdraw_quota_window WHERE user_id=$1" , uid)
            _vdbg(f"[ЛИМИТЫ][DEBUG] window_started_at пользователя {uid}: {val}")
            return val

    # ---------------------------------------------------------------
    # Снять кулдаун если истёк + сбросить окно
    # ---------------------------------------------------------------
    async def clear_user_expired_withdraw_cooldown(self, user_id: int) -> int:
        _vdbg(f"[ЛИМИТЫ][DEBUG] clear_user_expired_withdraw_cooldown({user_id})")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                deleted = await self._delete_user_cooldown_if_expired(conn, user_id)
                if deleted:
                    _vdbg(f"[ЛИМИТЫ][DEBUG] Кулдаун истёк → сбрасываю окно")
                    await conn.execute(
                        """
                        INSERT INTO withdraw_quota_window(user_id, window_started_at)
                        VALUES ($1, NOW())
                        ON CONFLICT (user_id) DO UPDATE SET window_started_at = NOW()
                        """,
                        user_id
                    )
                else:
                    _vdbg(f"[ЛИМИТЫ][DEBUG] Кулдауна нет → создаю окно при необходимости")
                    await conn.execute(
                        """
                        INSERT INTO withdraw_quota_window(user_id, window_started_at)
                        VALUES ($1, NOW())
                        ON CONFLICT (user_id) DO NOTHING
                        """,
                        user_id
                    )
                return int(deleted)

    # есть ли активный кулдаун прямо сейчас
    # ---------------------------------------------------------------
    # Проверить активен ли кулдаун
    # ---------------------------------------------------------------
    async def has_active_withdraw_cooldown(self , user_id: int) -> bool:
        uid = int(user_id)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM withdraw_cooldown WHERE user_id=$1 AND until_at > NOW()" , uid)
        active = bool(row)
        _vdbg(f"[ЛИМИТЫ][DEBUG] has_active_cooldown({uid}) = {active}")
        return active

    def _safe_used_percent_int(self , used_val: int , limit_val: int) -> int:
        """
        ✅ Возвращает used_percent как INT 0..100 (под SMALLINT + CHECK).
        Никаких '0.00'. Только int.
        """
        try:
            u = int(used_val or 0)
            l = int(limit_val or 0)
            if l <= 0:
                return 0
            pct = int(round((u * 100.0) / float(l)))
            if pct < 0:
                return 0
            if pct > 100:
                return 100
            return pct
        except Exception:
            return 0

    async def _set_withdraw_cooldown_idempotent(self , conn , * , user_id: int , cooldown_seconds: int ,
            cause: str = "daily_limit" , ) -> bool:
        """
        ✅ Идемпотентно ставит кулдаун под уже открытой транзакцией.

        Логика:
        - если у пользователя уже есть активный кулдаун -> НЕ продлеваем
        - если кулдаун истёк или строки нет -> ставим новый
        - работает через ON CONFLICT (user_id)

        Возвращает:
        - True  -> строка кулдауна гарантированно есть/активна
        - False -> если cooldown_seconds <= 0
        """
        try:
            uid = int(user_id)
        except Exception:
            uid = 0

        try:
            secs = int(cooldown_seconds or 0)
        except Exception:
            secs = 0

        if uid <= 0:
            _vdbg(f"[ЛИМИТЫ][COOLDOWN][LOCKED][ABORT] bad uid={user_id!r}")
            return False

        if secs <= 0:
            try:
                secs = int(getattr(self , "WITHDRAW_DEFAULT_COOLDOWN_SEC" , 12 * 3600) or (12 * 3600))
            except Exception:
                secs = 12 * 3600

        if secs <= 0:
            _vdbg(f"[ЛИМИТЫ][COOLDOWN][LOCKED][ABORT] bad secs={cooldown_seconds!r}")
            return False

        cause = str(cause or "daily_limit").strip() or "daily_limit"

        # ВАЖНО:
        # - если кулдаун уже активен, until_at НЕ трогаем
        # - если истёк / строки нет, ставим новый
        await conn.execute(
            """
            INSERT INTO withdraw_cooldown(user_id, started_at, until_at, cause)
            VALUES ($1, NOW(), NOW() + ($2::bigint * INTERVAL '1 second'), $3)
            ON CONFLICT (user_id) DO UPDATE
            SET
                started_at = CASE
                    WHEN withdraw_cooldown.until_at > NOW()
                        THEN withdraw_cooldown.started_at
                    ELSE EXCLUDED.started_at
                END,
                until_at = CASE
                    WHEN withdraw_cooldown.until_at > NOW()
                        THEN withdraw_cooldown.until_at
                    ELSE EXCLUDED.until_at
                END,
                cause = CASE
                    WHEN withdraw_cooldown.until_at > NOW()
                        THEN withdraw_cooldown.cause
                    ELSE EXCLUDED.cause
                END
            """ , uid , secs , cause , )

        _vdbg(f"[ЛИМИТЫ][COOLDOWN][LOCKED] ✅ uid={uid} secs={secs} cause={cause!r} (NO-EXTEND)")
        return True
    async def refresh_withdraw_quota_if_needed(self , user_id: int , * , daily_limit: Optional [ int ] = None ,
            cooldown_seconds: Optional [ int ] = None , **_ignore_kwargs) -> Dict [ str , Any ]:
        """
        ✅ UI/статус квоты (железобетон):
        - гарантирует строку withdraw_quota_window
        - удаляет истёкший cooldown и сбрасывает окно
        - если cooldown активен -> allowed=False + cooldown_left
        - иначе считает used (истина) по withdraw_log от window_started_at
        - пишет used_percent как INT 0..100 (под SMALLINT + CHECK)
        - если remaining==0 -> ставит cooldown NO-EXTEND и возвращает allowed=False
        """

        t0 = time.perf_counter()

        # -------- normalize uid --------
        try:
            uid = int(user_id)
        except Exception:
            _vdbg(f"🟥[ЛИМИТЫ][REFRESH][ABORT] bad user_id={user_id!r}")
            return {"allowed": False , "remaining": 0 , "daily_limit": 0 , "used": 0 , "cooldown_left": 0 ,
                    "cooldown_seconds": int(getattr(self , "WITHDRAW_DEFAULT_COOLDOWN_SEC" , 12 * 3600) or 12 * 3600) ,
                    "reason": "bad_user_id"}

        if not getattr(self , "pool" , None):
            _vdbg("🟥[ЛИМИТЫ][REFRESH][ERROR] pool is None")
            return {"allowed": False , "remaining": 0 , "daily_limit": 0 , "used": 0 , "cooldown_left": 0 ,
                    "cooldown_seconds": int(getattr(self , "WITHDRAW_DEFAULT_COOLDOWN_SEC" , 12 * 3600) or 12 * 3600) ,
                    "reason": "no_pool"}

        # -------- limits --------
        try:
            if daily_limit is None or cooldown_seconds is None:
                dl , cd = await self.get_user_withdraw_limits(uid)
                if daily_limit is None:
                    daily_limit = dl
                if cooldown_seconds is None:
                    cooldown_seconds = cd
        except Exception as e:
            _vdbg(f"🟧[ЛИМИТЫ][REFRESH][WARN] get_user_withdraw_limits err={type(e).__name__}: {e!r}")

        dl_i = int(daily_limit or 0)
        cd_i = int(cooldown_seconds or 0)

        # 1️⃣ если лимит не задан - берём из users.canwithdrawal
        if dl_i <= 0:
            dl_i = int(await self.get_canwithdrawal(user_id) or 0)

        # 2️⃣ если и там пусто - дефолт
        if dl_i <= 0:
            dl_i = int(Default_WITHDRAW_DEFAULT_DAILY_LIMIT)

        if cd_i <= 0:
            cd_i = int(getattr(self , "WITHDRAW_DEFAULT_COOLDOWN_SEC" , 12 * 3600) or 12 * 3600)

        async with self.pool.acquire() as conn:
            async with conn.transaction():

                # 1) ensure quota row (и сразу правильные типы)
                await conn.execute(
                    """
                    INSERT INTO withdraw_quota_window(
                        user_id, window_started_at, used_in_window, daily_limit, remaining,
                        used_percent, status, cooldown_left_sec, cooldown_until, updated_at
                    )
                    VALUES ($1, NOW(), 0, $2, $2, 0, 'OK', 0, NULL, NOW())
                    ON CONFLICT (user_id) DO NOTHING
                    """ , uid , dl_i)

                # 2) удалить истёкший кулдаун (как у тебя) + сбросить окно
                deleted = False
                try:
                    deleted = await self._delete_user_cooldown_if_expired(conn , uid)
                except Exception as e:
                    _vdbg(f"🟧[ЛИМИТЫ][REFRESH][WARN] _delete_user_cooldown_if_expired err={type(e).__name__}: {e!r}")

                if deleted:
                    await conn.execute(
                        """
                        UPDATE withdraw_quota_window
                        SET window_started_at = NOW(),
                            used_in_window    = 0,
                            daily_limit       = $2,
                            remaining         = $2,
                            used_percent      = 0,
                            status            = 'OK',
                            cooldown_left_sec = 0,
                            cooldown_until    = NULL,
                            updated_at        = NOW()
                        WHERE user_id = $1
                        """ , uid , dl_i)
                    _vdbg(f"🟩[ЛИМИТЫ][AUTO-RESET] uid={uid} cooldown expired -> reset window remaining={dl_i}")

                # 3) активный кулдаун?
                cd_until = await conn.fetchval(
                    "SELECT until_at FROM withdraw_cooldown WHERE user_id=$1 AND until_at > NOW()" , uid)
                if cd_until is not None:
                    left = await conn.fetchval(
                        """
                        SELECT GREATEST(0, EXTRACT(EPOCH FROM (until_at - NOW()))::BIGINT)
                        FROM withdraw_cooldown
                        WHERE user_id=$1 AND until_at > NOW()
                        """ , uid)
                    left_i = int(left or 0)

                    await conn.execute(
                        """
                        UPDATE withdraw_quota_window
                        SET status='COOLDOWN',
                            cooldown_left_sec=$2,
                            cooldown_until=$3,
                            remaining=0,
                            used_percent=0,
                            updated_at=NOW()
                        WHERE user_id=$1
                        """ , uid , left_i , cd_until)

                    _vdbg(f"🟦[ЛИМИТЫ][STATE] uid={uid} cooldown_active left={left_i}s")
                    return {"allowed": False , "remaining": 0 , "daily_limit": int(dl_i) , "used": None ,
                            "cooldown_left": int(left_i) , "cooldown_seconds": int(cd_i) , "reason": "cooldown_active"}

                # 4) window_started_at
                ws = await conn.fetchval(
                    "SELECT window_started_at FROM withdraw_quota_window WHERE user_id=$1" , uid)
                if not ws:
                    ws = await conn.fetchval("SELECT NOW()")
                    await conn.execute(
                        "UPDATE withdraw_quota_window SET window_started_at=$2, updated_at=NOW() WHERE user_id=$1" ,
                        uid , ws)

                # 5) истина used по withdraw_log
                used_truth = int(
                    await conn.fetchval(
                        """
                        SELECT COALESCE(SUM(amount),0)::BIGINT
                        FROM withdraw_log
                        WHERE user_id=$1 AND created_at >= $2
                        """ , uid , ws) or 0)

                remaining = max(0 , int(dl_i) - int(used_truth))

                # ✅ в окно пишем безопасное used_store (не больше dl_i)
                used_store = min(int(used_truth) , int(dl_i))
                used_percent_i = self._safe_used_percent_int(used_store , dl_i)

                status = "OK" if remaining > 0 else "LIMIT_REACHED"

                await conn.execute(
                    """
                    UPDATE withdraw_quota_window
                    SET used_in_window=$2,
                        daily_limit=$3,
                        remaining=$4,
                        used_percent=$5,
                        status=$6,
                        cooldown_left_sec=0,
                        cooldown_until=NULL,
                        updated_at=NOW()
                    WHERE user_id=$1
                    """ , uid , int(used_store) , int(dl_i) , int(remaining) , int(used_percent_i) , str(status))

                print(
                    f"🟦[ЛИМИТЫ][STATE] uid={uid} ws={ws} limit={dl_i} used_truth={used_truth} used_store={used_store} remaining={remaining} used_percent={used_percent_i} status={status}")

                # 6) remaining==0 -> поставить кулдаун NO-EXTEND
                if remaining <= 0 and cd_i > 0:
                    try:
                        await self._set_withdraw_cooldown_idempotent(
                            conn , user_id=uid , cooldown_seconds=cd_i , cause="daily_limit")
                    except Exception as e:
                        _vdbg(f"🟧[ЛИМИТЫ][AUTO-CD][WARN] set cooldown err={type(e).__name__}: {e!r}")

                    left2 = await conn.fetchval(
                        """
                        SELECT GREATEST(0, EXTRACT(EPOCH FROM (until_at - NOW()))::BIGINT)
                        FROM withdraw_cooldown
                        WHERE user_id=$1 AND until_at > NOW()
                        """ , uid)
                    left2_i = int(left2 or 0)
                    cd_until2 = await conn.fetchval(
                        "SELECT until_at FROM withdraw_cooldown WHERE user_id=$1 AND until_at > NOW()" , uid)

                    await conn.execute(
                        """
                        UPDATE withdraw_quota_window
                        SET status='COOLDOWN',
                            cooldown_left_sec=$2,
                            cooldown_until=$3,
                            remaining=0,
                            used_percent=100,
                            updated_at=NOW()
                        WHERE user_id=$1
                        """ , uid , left2_i , cd_until2)

                    dt = time.perf_counter() - t0
                    _vdbg(f"🟩[ЛИМИТЫ][AUTO-CD] uid={uid} remaining=0 -> cooldown left={left2_i}s dt={dt:.4f}s")
                    return {"allowed": False , "remaining": 0 , "daily_limit": int(dl_i) , "used": int(used_truth) ,
                            "cooldown_left": int(left2_i) , "cooldown_seconds": int(cd_i) ,
                            "reason": "daily_limit_reached"}

                dt = time.perf_counter() - t0
                _vdbg(f"🟩[ЛИМИТЫ][REFRESH][OK] uid={uid} dt={dt:.4f}s")
                return {"allowed": bool(remaining > 0) , "remaining": int(remaining) , "daily_limit": int(dl_i) ,
                        "used": int(used_truth) , "cooldown_left": 0 , "cooldown_seconds": int(cd_i) ,
                        "reason": "ok" if remaining > 0 else "daily_limit_reached"}

    async def ensure_withdraw_schema(self) -> None:
        """
        Запусти 1 раз на старте (после connect).
        НИЧЕГО НЕ ДРОПАЕТ. Только CREATE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS.
        """
        if not getattr(self , "pool" , None):
            _vdbg("[ЛИМИТЫ][SCHEMA][ERROR] pool is None")
            return

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # 1) withdraw_limits
                await conn.execute(
                    """
                CREATE TABLE IF NOT EXISTS withdraw_limits (
                    user_id BIGINT PRIMARY KEY,
                    daily_amount_limit BIGINT NOT NULL DEFAULT 0,
                    cooldown_seconds BIGINT NOT NULL DEFAULT 0,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """)

                # 2) withdraw_cooldown (важно: started_at + until_at + cause)
                await conn.execute(
                    """
                CREATE TABLE IF NOT EXISTS withdraw_cooldown (
                    user_id BIGINT PRIMARY KEY,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    until_at TIMESTAMPTZ NOT NULL,
                    cause TEXT
                );
                """)

                # 3) withdraw_quota_window (твоя “UI таблица”)
                await conn.execute(
                    """
                CREATE TABLE IF NOT EXISTS withdraw_quota_window (
                    user_id BIGINT PRIMARY KEY,
                    window_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    used_in_window BIGINT NOT NULL DEFAULT 0,
                    daily_limit BIGINT NOT NULL DEFAULT 0,
                    remaining BIGINT NOT NULL DEFAULT 0,
                    used_percent DOUBLE PRECISION NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'OK',
                    cooldown_left_sec BIGINT NOT NULL DEFAULT 0,
                    cooldown_until TIMESTAMPTZ NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """)

                # 4) На всякий случай - мягкая миграция (если таблица была старой)
                #    Добавляем недостающие колонки без ошибок:
                await conn.execute(
                    "ALTER TABLE withdraw_quota_window ADD COLUMN IF NOT EXISTS window_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW();")
                await conn.execute(
                    "ALTER TABLE withdraw_quota_window ADD COLUMN IF NOT EXISTS used_in_window BIGINT NOT NULL DEFAULT 0;")
                await conn.execute(
                    "ALTER TABLE withdraw_quota_window ADD COLUMN IF NOT EXISTS daily_limit BIGINT NOT NULL DEFAULT 0;")
                await conn.execute(
                    "ALTER TABLE withdraw_quota_window ADD COLUMN IF NOT EXISTS remaining BIGINT NOT NULL DEFAULT 0;")
                await conn.execute(
                    "ALTER TABLE withdraw_quota_window ADD COLUMN IF NOT EXISTS used_percent DOUBLE PRECISION NOT NULL DEFAULT 0;")
                await conn.execute(
                    "ALTER TABLE withdraw_quota_window ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'OK';")
                await conn.execute(
                    "ALTER TABLE withdraw_quota_window ADD COLUMN IF NOT EXISTS cooldown_left_sec BIGINT NOT NULL DEFAULT 0;")
                await conn.execute(
                    "ALTER TABLE withdraw_quota_window ADD COLUMN IF NOT EXISTS cooldown_until TIMESTAMPTZ NULL;")
                await conn.execute(
                    "ALTER TABLE withdraw_quota_window ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();")

                await conn.execute(
                    "ALTER TABLE withdraw_cooldown ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ NOT NULL DEFAULT NOW();")
                await conn.execute("ALTER TABLE withdraw_cooldown ADD COLUMN IF NOT EXISTS cause TEXT;")

                # 5) Индексы (безопасно)
                # withdraw_log (если таблица есть) - ускоряет SUM по окну
                try:
                    await conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_withdraw_log_user_created ON withdraw_log(user_id, created_at);")
                except Exception as e:
                    _vdbg(f"[ЛИМИТЫ][SCHEMA][WARN] idx withdraw_log пропущен: {e!r}")

                # Защита от двойных кликов (если request_id у тебя реально пишется всегда)
                try:
                    await conn.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_withdraw_log_user_req ON withdraw_log(user_id, request_id);")
                except Exception as e:
                    _vdbg(f"[ЛИМИТЫ][SCHEMA][WARN] uq withdraw_log пропущен: {e!r}")

        _vdbg("[ЛИМИТЫ][SCHEMA] ✅ OK")
    async def add_withdraw_usage(self , user_id: int , amount: int) -> Dict [ str , Any ]:
        """
        ВАЖНО: это то, что должно вызываться при успешном выводе,
        чтобы used увеличивался и remaining уменьшался.

        Делает: used += amount (в текущем окне).
        Если used дошёл до лимита -> на следующем refresh поставится кулдаун.

        Возвращает {ok, used, daily_limit, remaining}
        """
        uid = int(user_id)
        amt = int(amount or 0)
        if amt <= 0:
            return {"ok": False , "error": "invalid_amount"}

        if not self.pool:
            return {"ok": False , "error": "no_pool"}

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT user_id, window_end, daily_limit, used
                    FROM withdraw_quota_window
                    WHERE user_id=$1
                    FOR UPDATE
                    """ , uid)
                if row is None:
                    # если внезапно окна нет - создадим через refresh и повторим
                    await self.refresh_withdraw_quota_if_needed(uid)
                    row = await conn.fetchrow(
                        """
                        SELECT user_id, window_end, daily_limit, used
                        FROM withdraw_quota_window
                        WHERE user_id=$1
                        FOR UPDATE
                        """ , uid)
                    if row is None:
                        return {"ok": False , "error": "no_window"}

                # если окно истекло - сначала обновим окно
                expired = await conn.fetchval("SELECT ($1 <= NOW())" , row [ "window_end" ]) if row [
                                                                                                    "window_end" ] is not None else True
                if expired:
                    await self.refresh_withdraw_quota_if_needed(uid)
                    row = await conn.fetchrow(
                        """
                        SELECT daily_limit, used
                        FROM withdraw_quota_window
                        WHERE user_id=$1
                        FOR UPDATE
                        """ , uid)

                daily_limit_db = int(row [ "daily_limit" ] or 0)
                used_db = int(row [ "used" ] or 0)

                new_used = used_db + amt
                if new_used < 0:
                    new_used = used_db

                await conn.execute(
                    "UPDATE withdraw_quota_window SET used=$2 WHERE user_id=$1" , uid , new_used)

                remaining = daily_limit_db - new_used
                if remaining < 0:
                    remaining = 0

                print(
                    f"[WITHDRAW][USAGE] uid={uid} +{amt} used:{used_db}->{new_used} remaining={remaining}/{daily_limit_db}")

                return {"ok": True , "used": new_used , "daily_limit": daily_limit_db , "remaining": remaining}
    # ---------------------------------------------------------------
    # Поставить кулдаун
    # ---------------------------------------------------------------
    async def start_user_withdraw_cooldown(self, user_id: int, cooldown_seconds: int, cause: str = "daily_limit") -> bool:
        """
        ✅ Идемпотентно ставит кулдаун.
        ВАЖНО: таблица withdraw_cooldown = (user_id, started_at, until_at, cause)
        """
        uid = int(user_id)
        cd = int(cooldown_seconds or 0)
        if cd <= 0:
            return False

        if not getattr(self, "pool", None):
            _vdbg("[ЛИМИТЫ][COOLDOWN][ERROR] pool is None")
            return False

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Не продлеваем активный кулдаун (NO-EXTEND)
                exists = await conn.fetchval(
                    "SELECT 1 FROM withdraw_cooldown WHERE user_id=$1 AND until_at > NOW()",
                    uid
                )
                if exists:
                    _vdbg(f"[ЛИМИТЫ][COOLDOWN] uid={uid} already active -> no-extend")
                    return False

                try:
                    await conn.execute(
                        """
                        INSERT INTO withdraw_cooldown(user_id, started_at, until_at, cause)
                        VALUES ($1, NOW(), NOW() + ($2::bigint * INTERVAL '1 second'), $3)
                        ON CONFLICT (user_id)
                        DO UPDATE SET
                            started_at = EXCLUDED.started_at,
                            until_at   = EXCLUDED.until_at,
                            cause      = EXCLUDED.cause
                        """,
                        uid, cd, str(cause or "daily_limit")
                    )
                    _vdbg(f"[ЛИМИТЫ][COOLDOWN] ✅ set uid={uid} sec={cd} cause={cause!r}")
                    return True
                except Exception as e:
                    _vdbg(f"[ЛИМИТЫ][COOLDOWN][ERROR] insert cooldown uid={uid} err={e!r}")
                    raise

    async def get_withdrawn_in_window(self , user_id: int) -> int:
        """
        Истина = withdraw_log SUM(amount) с момента window_started_at.
        """
        uid = int(user_id)
        SQL = r"""
            WITH w AS (
                SELECT COALESCE(
                    (SELECT window_started_at
                     FROM withdraw_quota_window
                     WHERE user_id=$1),
                    '1970-01-01'::timestamptz
                ) AS ws
            )
            SELECT COALESCE(SUM(amount),0)::BIGINT
            FROM withdraw_log, w
            WHERE user_id=$1 AND created_at >= w.ws
        """
        async with self.pool.acquire() as conn:
            v = await conn.fetchval(SQL , uid)
            val = int(v or 0)
            _vdbg(f"[ЛИМИТЫ][DEBUG] Сумма выводов с окна = {val}")
            return val

    # 4) «состояние квоты» в одном вызове - удобно для логов/статуса
    async def get_quota_state(self , user_id: int) -> dict:
        await self.ensure_quota_window(user_id)
        ws = await self.get_quota_window_started_at(user_id)
        used = await self.get_withdrawn_in_window(user_id)
        daily_limit , cooldown_sec = await self.get_user_withdraw_limits(user_id)
        remaining = max(0 , int(daily_limit) - int(used))
        left_cd = await self.get_user_cooldown_left(user_id)  # 0 если кулдауна нет
        return {"user_id": user_id , "window_started_at": ws.isoformat() if ws else None , "used_in_window": int(used) ,
            "daily_limit": int(daily_limit) , "remaining": int(remaining) ,
            "cooldown_seconds_left": int(left_cd or 0) , }

    async def rollback_withdraw_strict(self , user_id: int , request_id: str) -> Dict [ str , Any ]:
        """
        Откат строгого вывода (если gift не отправился).
        - возвращаем баланс
        - удаляем withdraw_log по request_id
        - пересчитываем used/remaining в withdraw_quota_window
        - удаляем cooldown, если он был поставлен именно этим rid
        Идемпотентно: если лога нет - ничего не делаем.
        """

        try:
            uid = int(user_id)
        except Exception as e:
            print(f"[ВЫВОД][ROLLBACK] 🟥 bad user_id={user_id!r} err={e!r}")
            return {"ok": False , "error": "invalid_user_id"}

        rid = str(request_id or "").strip()
        if not rid:
            return {"ok": False , "error": "no_request_id"}

        if not getattr(self , "pool" , None):
            return {"ok": False , "error": "pool_not_ready"}

        t0 = time.perf_counter()
        print(f"[ВЫВОД][{rid}][ROLLBACK] ▶️ start uid={uid}")

        payload: Optional [ Dict [ str , Any ] ] = None
        new_balance_after_commit: Optional [ int ] = None

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # ---------------------------------------------------
                # 0) анти-гонки
                # ---------------------------------------------------
                await conn.execute("SELECT pg_advisory_xact_lock($1::bigint)" , uid)

                # ---------------------------------------------------
                # 1) найти withdraw_log
                # ---------------------------------------------------
                row = await conn.fetchrow(
                    """
                    SELECT amount
                    FROM withdraw_log
                    WHERE user_id=$1 AND request_id=$2
                    """ , uid , rid , )

                if not row:
                    print(f"[ВЫВОД][{rid}][ROLLBACK] 🟨 no log -> noop")
                    return {"ok": True , "noop": True}

                amount_i = self._safe_non_negative_int(row [ "amount" ] , 0)
                if amount_i <= 0:
                    await conn.execute(
                        """
                        DELETE FROM withdraw_log
                        WHERE user_id=$1 AND request_id=$2
                        """ , uid , rid , )
                    print(f"[ВЫВОД][{rid}][ROLLBACK] 🟨 non-positive amount in log -> deleted log -> noop")
                    return {"ok": True , "noop": True}

                # ---------------------------------------------------
                # 2) вернуть баланс
                # ---------------------------------------------------
                bal_row = await conn.fetchrow(
                    """
                    UPDATE users
                       SET balance = balance + $2
                     WHERE user_id = $1
                    RETURNING balance
                    """ , uid , amount_i , )

                if not bal_row:
                    print(f"[ВЫВОД][{rid}][ROLLBACK] 🟥 user_not_found_on_refund")
                    return {"ok": False , "error": "user_not_found"}

                new_bal = self._safe_non_negative_int(bal_row [ "balance" ] , 0)

                # ---------------------------------------------------
                # 3) удалить лог
                # ---------------------------------------------------
                await conn.execute(
                    """
                    DELETE FROM withdraw_log
                    WHERE user_id=$1 AND request_id=$2
                    """ , uid , rid , )

                # ---------------------------------------------------
                # 4) удалить cooldown, если он был поставлен именно этим rid
                # ---------------------------------------------------
                try:
                    del_cd = await conn.execute(
                        """
                        DELETE FROM withdraw_cooldown
                        WHERE user_id=$1 AND cause LIKE '%' || $2
                        """ , uid , f":{rid}" , )
                    print(f"[ВЫВОД][{rid}][ROLLBACK] cooldown delete result={del_cd}")
                except Exception as e:
                    print(f"[ВЫВОД][{rid}][ROLLBACK] cooldown delete warn: {e!r}")

                # ---------------------------------------------------
                # 5) гарантировать quota row + lock
                # ---------------------------------------------------
                ws = await conn.fetchval(
                    """
                    SELECT window_started_at
                    FROM withdraw_quota_window
                    WHERE user_id=$1
                    FOR UPDATE
                    """ , uid , )

                if not ws:
                    ws = await conn.fetchval("SELECT NOW()")
                    default_dl = self._safe_non_negative_int(Default_WITHDRAW_DEFAULT_DAILY_LIMIT , 0)

                    await conn.execute(
                        """
                        INSERT INTO withdraw_quota_window(
                            user_id,
                            window_started_at,
                            used_in_window,
                            daily_limit,
                            remaining,
                            used_percent,
                            status,
                            cooldown_left_sec,
                            cooldown_until,
                            updated_at
                        )
                        VALUES ($1, $2, 0, $3, $3, 0, 'OK', 0, NULL, NOW())
                        ON CONFLICT (user_id) DO NOTHING
                        """ , uid , ws , int(default_dl) , )

                # ---------------------------------------------------
                # 6) взять daily_limit
                # ---------------------------------------------------
                daily_limit = await conn.fetchval(
                    """
                    SELECT daily_limit
                    FROM withdraw_quota_window
                    WHERE user_id=$1
                    """ , uid , )
                dl = self._safe_non_negative_int(daily_limit , 0)

                if dl <= 0:
                    dl = self._safe_non_negative_int(await self.get_canwithdrawal(uid) or 0 , 0)

                if dl <= 0:
                    dl = self._safe_non_negative_int(Default_WITHDRAW_DEFAULT_DAILY_LIMIT , 0)

                # ---------------------------------------------------
                # 7) truth used после удаления withdraw_log
                # ---------------------------------------------------
                used_truth = self._safe_non_negative_int(
                    await conn.fetchval(
                        """
                        SELECT COALESCE(SUM(amount), 0)::BIGINT
                        FROM withdraw_log
                        WHERE user_id=$1 AND created_at >= $2
                        """ , uid , ws , ) or 0 , 0 , )

                # ---------------------------------------------------
                # 8) safe-store значения для quota window
                # ---------------------------------------------------
                if int(dl) > 0:
                    used_store = min(int(used_truth) , int(dl))
                else:
                    used_store = 0

                remaining_store = max(0 , int(dl) - int(used_store))
                used_percent_store = self._safe_used_percent_int(int(used_store) , int(dl))
                status = "OK" if remaining_store > 0 else "LIMIT_REACHED"

                # ---------------------------------------------------
                # 9) обновить quota window безопасно
                # ---------------------------------------------------
                await conn.execute(
                    """
                    UPDATE withdraw_quota_window
                    SET used_in_window    = $2,
                        daily_limit       = $3,
                        remaining         = $4,
                        used_percent      = $5,
                        status            = $6,
                        cooldown_left_sec = 0,
                        cooldown_until    = NULL,
                        updated_at        = NOW()
                    WHERE user_id = $1
                    """ , uid , int(used_store) , int(dl) , int(remaining_store) , int(used_percent_store) ,
                    str(status) , )

                dt = time.perf_counter() - t0
                print(
                    f"[ВЫВОД][{rid}][ROLLBACK] ✅ done amount={amount_i} new_bal={new_bal} "
                    f"used_truth={used_truth} used_store={used_store} remaining={remaining_store} "
                    f"pct={used_percent_store} dt={dt:.4f}s")

                payload = {"ok": True , "refunded": int(amount_i) , "user_balance_after": int(new_bal) ,
                    "used": int(used_truth) ,  # truth для логики
                    "remaining": int(remaining_store) ,  # safe-store для UI
                }
                new_balance_after_commit = int(new_bal)

        # ---------------------------------------------------
        # 10) после коммита: синк кэша баланса
        # ---------------------------------------------------
        if payload and payload.get("ok") and isinstance(new_balance_after_commit , int):
            try:
                if hasattr(self , "sync_user_balance_cache"):
                    await self.sync_user_balance_cache(int(uid) , int(new_balance_after_commit))
            except Exception as e:
                print(f"[ВЫВОД][{rid}][ROLLBACK] 🟠 cache sync failed: {e!r}")

        return payload or {"ok": False , "error": "unknown"}
    # ---------------------------------------------------------------
    # Остаток кулдауна
    # ---------------------------------------------------------------
    async def get_user_cooldown_left(self, user_id: int) -> int:
        """
        Возвращает cooldown_left_sec (0 если нет активного).
        """
        uid = int(user_id)
        if not getattr(self, "pool", None):
            return 0
        async with self.pool.acquire() as conn:
            left = await conn.fetchval(
                """
                SELECT GREATEST(0, EXTRACT(EPOCH FROM (until_at - NOW()))::BIGINT)
                FROM withdraw_cooldown
                WHERE user_id=$1 AND until_at > NOW()
                """,
                uid
            )
            return int(left or 0)
    # ============================================================
    # ✅ quota window helpers
    # ============================================================
    async def ensure_quota_window(self , user_id: int) -> None:
        uid = int(user_id)
        async with self.pool.acquire() as conn:
            _vdbg(f"[ЛИМИТЫ][DEBUG] Гарантирую окно пользователя {uid}")
            await conn.execute(
                """
                INSERT INTO withdraw_quota_window(user_id, window_started_at, updated_at)
                VALUES ($1, NOW(), NOW())
                ON CONFLICT (user_id) DO NOTHING
                """ , uid)

    # 2) принудительно сбросить окно сейчас (админская/диагностическая)
    async def reset_quota_window_now(self , user_id: int) -> None:
        SQL = """
        INSERT INTO withdraw_quota_window (user_id, window_started_at)
        VALUES ($1, now())
        ON CONFLICT (user_id) DO UPDATE SET window_started_at = now()
        """
        async with self.pool.acquire() as conn:
            await conn.execute(SQL , user_id)

    # ============================================================
    # ✅ LIMITS: получить лимиты пользователя (или дефолты)
    # ============================================================
    # ============================================================
    # ✅ LIMITS: получить лимиты пользователя (или дефолты)
    # ============================================================

    async def get_user_withdraw_limits(self, user_id: int) -> Tuple[int, int]:
        """
        Источник истины по лимиту вывода: users.canwithdrawal.
        withdraw_limits используем как дополнительное хранилище cooldown
        и для обратной совместимости.
        """
        uid = int(user_id)
        if not getattr(self, "pool", None):
            _vdbg("[ЛИМИТЫ][LIMITS][ERROR] pool is None")
            return int(await self.get_canwithdrawal(user_id)), int(self.WITHDRAW_DEFAULT_COOLDOWN_SEC)

        async with self.pool.acquire() as conn:
            canwithdrawal_dl = int(
                await conn.fetchval(
                    "SELECT canwithdrawal FROM users WHERE user_id=$1",
                    uid,
                ) or 0
            )

            row = await conn.fetchrow(
                """
                SELECT daily_amount_limit, cooldown_seconds
                FROM withdraw_limits
                WHERE user_id=$1
                """,
                uid,
            )

            if not row:
                dl = int(canwithdrawal_dl or 0)
                cd = int(self.WITHDRAW_DEFAULT_COOLDOWN_SEC or 12 * 3600)
                if dl <= 0:
                    dl = int(Default_WITHDRAW_DEFAULT_DAILY_LIMIT or 100)
                return int(dl), int(cd)

            row_dl = int(row["daily_amount_limit"] or 0)
            cd = int(row["cooldown_seconds"] or 0)

            # КЛЮЧЕВОЕ ПРАВИЛО:
            # если в users.canwithdrawal есть число > 0, берём именно его.
            if canwithdrawal_dl > 0:
                dl = int(canwithdrawal_dl)
            else:
                dl = int(row_dl or 0)
                if dl <= 0:
                    dl = int(Default_WITHDRAW_DEFAULT_DAILY_LIMIT or 100)

                # Если canwithdrawal пустой, а в withdraw_limits есть лимит - синхронизируем users.
                try:
                    await conn.execute(
                        """
                        UPDATE users
                        SET canwithdrawal = $2
                        WHERE user_id = $1
                          AND COALESCE(canwithdrawal, 0) <= 0
                        """,
                        uid,
                        int(dl),
                    )
                except Exception as e:
                    _vdbg(f"[ЛИМИТЫ][LIMITS][WARN] users sync err={type(e).__name__}: {e!r}")

            # Поддерживаем withdraw_limits в синхроне с источником истины.
            try:
                if int(row_dl or 0) != int(dl):
                    await conn.execute(
                        """
                        UPDATE withdraw_limits
                        SET daily_amount_limit = $2,
                            updated_at = NOW()
                        WHERE user_id = $1
                        """,
                        uid,
                        int(dl),
                    )
            except Exception as e:
                _vdbg(f"[ЛИМИТЫ][LIMITS][WARN] withdraw_limits sync err={type(e).__name__}: {e!r}")

            if cd <= 0:
                cd = int(self.WITHDRAW_DEFAULT_COOLDOWN_SEC)

            return int(dl), int(cd)

    async def upsert_withdraw_limit(
            self,
            user_id: int,
            daily_amount_limit: Optional[int] = None,
            cooldown_seconds: Optional[int] = None,
    ) -> None:
        """
        Установить/обновить персональные лимиты. Не переданный параметр - берём текущее значение/дефолт.
        """
        current_limit, current_cooldown = await self.get_user_withdraw_limits(user_id)
        new_limit = daily_amount_limit if daily_amount_limit is not None else current_limit
        new_cd = cooldown_seconds if cooldown_seconds is not None else current_cooldown

        sql = """
        INSERT INTO withdraw_limits (user_id, daily_amount_limit, cooldown_seconds, updated_at)
        VALUES ($1, $2, $3, now())
        ON CONFLICT (user_id) DO UPDATE
          SET daily_amount_limit = EXCLUDED.daily_amount_limit,
              cooldown_seconds   = EXCLUDED.cooldown_seconds,
              updated_at         = now();
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, user_id, int(new_limit), int(new_cd))
            # users.canwithdrawal — источник истины.
            await conn.execute(
                """
                UPDATE users
                SET canwithdrawal = $2
                WHERE user_id = $1
                """,
                int(user_id),
                int(new_limit),
            )

    async def _cleanup_expired_cooldown_and_reset_quota_locked(
            self,
            conn,
            *,
            user_id: int,
            daily_limit: int,
    ) -> bool:
        """
        Если кулдаун истёк:
        - удаляем протухший withdraw_cooldown
        - сбрасываем withdraw_quota_window
        - нормализуем лимит перед reset

        ВАЖНО:
        - вызывать только под lock / внутри транзакции
        - новый cooldown НЕ создаёт
        """

        def _safe_int_local(v, default: int = 0) -> int:
            try:
                return int(v)
            except Exception:
                return int(default)

        def _safe_non_negative_local(v, default: int = 0) -> int:
            x = _safe_int_local(v, default)
            return x if x >= 0 else 0

        uid = int(user_id)
        dl = _safe_non_negative_local(daily_limit, 0)

        # 1) удаляем только ПРОТУХШИЙ cooldown
        res = await conn.execute(
            """
            DELETE FROM withdraw_cooldown
            WHERE user_id=$1 AND until_at <= NOW()
            """,
            uid,
        )

        try:
            deleted = int((res or "0").split()[-1])
        except Exception:
            deleted = 0

        if deleted <= 0:
            return False

        # 2) нормализуем daily_limit
        if dl <= 0:
            try:
                if hasattr(self, "get_canwithdrawal"):
                    dl = _safe_non_negative_local(await self.get_canwithdrawal(uid) or 0, 0)
            except Exception as e:
                _vdbg(f"[ЛИМИТЫ][AUTO-RESET][WARN] get_canwithdrawal uid={uid} err={e!r}")
                dl = 0

        if dl <= 0:
            try:
                dl = _safe_non_negative_local(Default_WITHDRAW_DEFAULT_DAILY_LIMIT, 0)
            except Exception:
                dl = 100

        if dl <= 0:
            dl = 100

        print(
            f"[ЛИМИТЫ][AUTO-RESET] ✅ uid={uid} кулдаун истёк -> удалён({deleted}) "
            f"-> сброс окна, лимит={dl}"
        )

        # 3) жёсткий reset quota window
        await conn.execute(
            """
            INSERT INTO withdraw_quota_window(
                user_id,
                window_started_at,
                used_in_window,
                daily_limit,
                remaining,
                used_percent,
                status,
                cooldown_left_sec,
                cooldown_until,
                updated_at
            )
            VALUES ($1, NOW(), 0, $2, $2, 0, 'OK', 0, NULL, NOW())
            ON CONFLICT (user_id) DO UPDATE
              SET window_started_at = NOW(),
                  used_in_window    = 0,
                  daily_limit       = EXCLUDED.daily_limit,
                  remaining         = EXCLUDED.remaining,
                  used_percent      = 0,
                  status            = 'OK',
                  cooldown_left_sec = 0,
                  cooldown_until    = NULL,
                  updated_at        = NOW()
            """,
            uid,
            int(dl),
        )

        # 4) лог текущего состояния после reset
        try:
            row = await conn.fetchrow(
                """
                SELECT
                    user_id,
                    window_started_at,
                    used_in_window,
                    daily_limit,
                    remaining,
                    used_percent,
                    status,
                    cooldown_left_sec,
                    cooldown_until
                FROM withdraw_quota_window
                WHERE user_id=$1
                """,
                uid,
            )
            _vdbg(f"[ЛИМИТЫ][AUTO-RESET][STATE] uid={uid} row={dict(row) if row else None}")
        except Exception as e:
            _vdbg(f"[ЛИМИТЫ][AUTO-RESET][WARN] state fetch uid={uid} err={e!r}")

        return True

    async def remove_expired_withdraw_cooldowns(self, user_id) -> int:
        """
        Чистим просроченные кулдауны.
        Для затронутых пользователей сбрасываем окно (used=0, remaining=daily_limit).
        """
        if not getattr(self, "pool", None):
            return 0

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch("SELECT user_id FROM withdraw_cooldown WHERE until_at <= NOW()")
                user_ids = [int(r["user_id"]) for r in rows] if rows else []

                res = await conn.execute("DELETE FROM withdraw_cooldown WHERE until_at <= NOW()")
                try:
                    deleted_count = int((res or "0").split()[-1])
                except Exception:
                    deleted_count = 0

                if user_ids:
                    default_dl = int(Default_WITHDRAW_DEFAULT_DAILY_LIMIT or 100)

                    # 1) пользователи, которые есть в users
                    await conn.execute(
                        """
                        INSERT INTO withdraw_quota_window(
                            user_id, window_started_at, used_in_window, daily_limit, remaining,
                            used_percent, status, cooldown_left_sec, cooldown_until, updated_at
                        )
                        SELECT u.user_id, NOW(), 0,
                               COALESCE(NULLIF(u.canwithdrawal,0), $2),
                               COALESCE(NULLIF(u.canwithdrawal,0), $2),
                               0, 'OK', 0, NULL, NOW()
                          FROM users u
                         WHERE u.user_id = ANY($1::BIGINT[])
                        ON CONFLICT (user_id) DO UPDATE
                          SET window_started_at = EXCLUDED.window_started_at,
                              used_in_window    = 0,
                              daily_limit       = EXCLUDED.daily_limit,
                              remaining         = EXCLUDED.remaining,
                              used_percent      = 0,
                              status            = 'OK',
                              cooldown_left_sec = 0,
                              cooldown_until    = NULL,
                              updated_at        = NOW()
                        """,
                        user_ids,
                        int(default_dl),
                    )

                    # 2) user_id есть в cooldown, но нет строки в users
                    await conn.execute(
                        """
                        INSERT INTO withdraw_quota_window(
                            user_id, window_started_at, used_in_window, daily_limit, remaining,
                            used_percent, status, cooldown_left_sec, cooldown_until, updated_at
                        )
                        SELECT u_id, NOW(), 0, $2, $2, 0, 'OK', 0, NULL, NOW()
                          FROM UNNEST($1::BIGINT[]) AS t(u_id)
                         WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.user_id = t.u_id)
                        ON CONFLICT (user_id) DO UPDATE
                          SET window_started_at = EXCLUDED.window_started_at,
                              used_in_window    = 0,
                              daily_limit       = EXCLUDED.daily_limit,
                              remaining         = EXCLUDED.remaining,
                              used_percent      = 0,
                              status            = 'OK',
                              cooldown_left_sec = 0,
                              cooldown_until    = NULL,
                              updated_at        = NOW()
                        """,
                        user_ids,
                        int(default_dl),
                    )

                _vdbg(f"[ЛИМИТЫ][CLEANUP] удалено кулдаунов: {deleted_count}. сброшено окон: {len(user_ids)}")
                return deleted_count

    async def get_staff_daily_counts(self, user_id: int) -> Dict[int, int]:
        """
        Возвращает {chat_id: сколько сообщений пользователь написал СЕГОДНЯ}
        по каждой официальной группе (MuteConfig.STAFF_CHAT_IDS).
        Группы без сообщений присутствуют со значением 0.
        При ошибке БД возвращает то, что успели собрать (по умолчанию нули).
        """
        result: Dict[int, int] = {}
        if not self.pool:
            return result

        try:
            from bot.admins.mute import MuteConfig
        except Exception as e:
            print(f"[STAFF_DAILY][CFG][WARN] {e!r}")
            return result

        staff_ids = [int(c) for c in MuteConfig.STAFF_CHAT_IDS]
        if not staff_ids:
            return result

        for cid in staff_ids:
            result[cid] = 0

        today = date.today()
        query = """
            SELECT chat_id, COALESCE(SUM(text), 0) AS total
            FROM chatchange
            WHERE user_id = $1
              AND date = $2
              AND text IS NOT NULL
              AND chat_id = ANY($3::bigint[])
            GROUP BY chat_id
        """
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(query, int(user_id), today, staff_ids)
                for row in rows:
                    result[int(row["chat_id"])] = int(row["total"] or 0)
        except Exception as e:
            print(f"[STAFF_DAILY][ERROR] uid={user_id}: {e!r}")

        # Плюсуем несброшенные в БД сообщения из in-memory буфера.
        try:
            uid = int(user_id)
            staff_set = set(staff_ids)
            pending = getattr(self, "_pending_user_counts", {}) or {}

            for (p_uid, p_cid), p_cnt in pending.items():
                try:
                    p_uid_i = int(p_uid)
                    p_cid_i = int(p_cid)
                    p_cnt_i = int(p_cnt or 0)
                except Exception:
                    continue

                if p_cnt_i <= 0:
                    continue
                if p_uid_i != uid or p_cid_i not in staff_set:
                    continue

                result[p_cid_i] = int(result.get(p_cid_i, 0)) + p_cnt_i
        except Exception as e:
            print(f"[STAFF_DAILY][PENDING][WARN] uid={user_id}: {e!r}")

        return result

    # ============================================================
    # ✅ 9) get_withdraw_state (UI-обёртка)
    # ============================================================
    async def get_withdraw_state(self , user_id: int) -> Dict [ str , Any ]:
        """
        Для UI. Не “железо”. Железо - add_withdraw/add_withdraw_strict.
        """
        st = await self.refresh_withdraw_quota_if_needed(int(user_id))
        if not st.get("allowed"):
            return {"allowed": False , "cooldown_left": int(st.get("cooldown_left") or 0) ,
                "daily_limit": int(st.get("daily_limit") or 0) , "used": st.get("used") , "remaining": 0 ,
                "cooldown_seconds": int(st.get("cooldown_seconds") or 0) , "reason": st.get("reason")}

        return {"allowed": True , "daily_limit": int(st.get("daily_limit") or 0) ,
            "used": int(st.get("used") or 0) , "remaining": int(st.get("remaining") or 0) ,
            "cooldown_seconds": int(st.get("cooldown_seconds") or 0) , "reason": "ok"}
    async def sync_user_balance_cache(self , user_id: int , new_balance: int) -> None:
        """
        ✅ Синхронизация кэшей баланса ПОСЛЕ прямого UPDATE в БД (без SQL).
        Нужна потому что add_withdraw_strict списывает balance напрямую в users,
        а твой UI/бот читает баланс из Redis/local cache (cache-hit).
        """
        import json , time

        DEBUG = True
        NS_PREFIX = "bal"
        REDIS_CACHE_TTL = 3600
        PUBLISH_UPDATES = True

        try:
            uid = int(user_id)
            val = int(new_balance)
        except Exception as e:
            if DEBUG:
                print(f"📦[CACHE][SYNC][ABORT] bad args user_id={user_id!r} new_balance={new_balance!r} err={e!r}")
            return

        use_redis = bool(getattr(self , "redis" , None))
        redis = getattr(self , "redis" , None)

        # локальный кэш как у тебя
        g = globals()
        if "user_cache_balance" not in g or not isinstance(g.get("user_cache_balance") , dict):
            g [ "user_cache_balance" ] = {}
            if DEBUG: print("📦[CACHE][LOCAL] Инициализирован словарь user_cache_balance")

        user_cache_balance = g [ "user_cache_balance" ]

        if DEBUG:
            print(f"📦[CACHE][SYNC][START] uid={uid} balance={val} use_redis={use_redis}")

        # Redis cache + pubsub
        if use_redis:
            try:
                await redis.set(f"{NS_PREFIX}:val:{uid}" , str(val) , ex=REDIS_CACHE_TTL)
                if DEBUG:
                    print(f"📦[CACHE][REDIS] {NS_PREFIX}:val:{uid} = {val} (ttl={REDIS_CACHE_TTL}s)")

                if PUBLISH_UPDATES:
                    msg = json.dumps({"uid": uid , "balance": val , "ts": time.time()})
                    await redis.publish(f"{NS_PREFIX}:bus" , msg)
                    if DEBUG:
                        print(f"📣[CACHE][PUB] {NS_PREFIX}:bus <- {msg}")

            except Exception as e:
                if DEBUG:
                    print(f"📦[CACHE][SYNC][WARN] redis set/publish failed: {e!r}")

        # Local cache
        try:
            user_cache_balance [ uid ] = val
            _balance_fresh_at [ uid ] = time.monotonic()
            if DEBUG:
                print(f"📦[CACHE][LOCAL] user_cache_balance[{uid}] = {val}")
        except Exception as e:
            if DEBUG:
                print(f"📦[CACHE][SYNC][WARN] local cache set failed: {e!r}")

        if DEBUG:
            print(f"📦[CACHE][SYNC][END] uid={uid}")

    def _safe_int(self , value , default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return int(default)

    def _safe_non_negative_int(self , value , default: int = 0) -> int:
        x = self._safe_int(value , default)
        return x if x >= 0 else 0

    def _safe_used_percent_int(self , used_value , limit_value) -> int:
        """
        Всегда возвращает INT в диапазоне 0..100.
        Никаких float, NaN, inf, отрицательных значений.
        """
        used_i = self._safe_non_negative_int(used_value , 0)
        limit_i = self._safe_non_negative_int(limit_value , 0)

        if limit_i <= 0:
            return 100 if used_i > 0 else 0

        pct = int((used_i * 100) / limit_i)

        if pct < 0:
            return 0
        if pct > 100:
            return 100
        return pct

    async def _normalize_withdraw_quota_row_locked(self , conn , * , user_id: int , daily_limit: int) -> None:
        """
        Самолечение строки withdraw_quota_window под lock.
        Ничего не пишет за пределы допустимых значений.
        """
        uid = int(user_id)
        dl = self._safe_non_negative_int(daily_limit , 0)

        row = await conn.fetchrow(
            """
            SELECT user_id, window_started_at, used_in_window, daily_limit, remaining,
                   used_percent, status, cooldown_left_sec, cooldown_until
            FROM withdraw_quota_window
            WHERE user_id = $1
            FOR UPDATE
            """ , uid , )

        if not row:
            await conn.execute(
                """
                INSERT INTO withdraw_quota_window(
                    user_id, window_started_at, used_in_window, daily_limit, remaining,
                    used_percent, status, cooldown_left_sec, cooldown_until, updated_at
                )
                VALUES ($1, NOW(), 0, $2, $2, 0, 'OK', 0, NULL, NOW())
                ON CONFLICT (user_id) DO NOTHING
                """ , uid , int(dl) , )
            return

        ws = row [ "window_started_at" ]
        if not ws:
            ws = await conn.fetchval("SELECT NOW()")

        row_dl = self._safe_non_negative_int(row [ "daily_limit" ] , dl)
        if dl > 0:
            row_dl = dl

        used_store = self._safe_non_negative_int(row [ "used_in_window" ] , 0)
        if row_dl > 0:
            used_store = min(used_store , row_dl)
        else:
            used_store = 0

        remaining_store = max(0 , row_dl - used_store)
        used_percent_store = self._safe_used_percent_int(used_store , row_dl)

        old_status = str(row [ "status" ] or "").strip().upper()
        if remaining_store <= 0:
            status = "COOLDOWN" if old_status == "COOLDOWN" else "LIMIT_REACHED"
        else:
            status = "OK"

        cooldown_left_sec = self._safe_non_negative_int(row [ "cooldown_left_sec" ] , 0)
        cooldown_until = row [ "cooldown_until" ]

        await conn.execute(
            """
            UPDATE withdraw_quota_window
            SET window_started_at = $2,
                used_in_window    = $3,
                daily_limit       = $4,
                remaining         = $5,
                used_percent      = $6,
                status            = $7,
                cooldown_left_sec = $8,
                cooldown_until    = $9,
                updated_at        = NOW()
            WHERE user_id = $1
            """ , uid , ws , int(used_store) , int(row_dl) , int(remaining_store) , int(used_percent_store) ,
            str(status) , int(cooldown_left_sec) , cooldown_until , )

    async def add_withdraw_strict(self , user_id: int , amount: int , * , request_id: Optional [ str ] = None ,
            chat_id: Optional [ int ] = None , chat_name: Optional [ str ] = None ,
            reason: Optional [ str ] = "user_payout" , ) -> Dict [ str , Any ]:
        """
        ✅ Абсолютно строгий вывод:
        - advisory lock по uid
        - идемпотентность по request_id
        - truth used считаем по withdraw_log
        - cooldown ставим NO-EXTEND
        - HARD SELF-HEAL окна: если cooldown истёк, а окно не сбросилось -> окно сбрасывается
        - committed=True только если деньги реально списаны в ЭТОЙ транзакции
        """

        def _safe_int_local(v , default: int = 0) -> int:
            try:
                return int(v)
            except Exception:
                return int(default)

        def _safe_non_negative_local(v , default: int = 0) -> int:
            x = _safe_int_local(v , default)
            return x if x >= 0 else 0

        def _safe_str_local(v , default: str = "") -> str:
            try:
                if v is None:
                    return default
                s = str(v).strip()
                return s if s else default
            except Exception:
                return default

        def _make_fail(error: str , **extra) -> Dict [ str , Any ]:
            payload_local = {"ok": False , "committed": False , "duplicate": False , "should_send_to_channel": False ,
                "error": str(error) , "status": str(error) , }
            if extra:
                payload_local.update(extra)
            return payload_local

        def _safe_used_percent_local(used_value: int , limit_value: int) -> int:
            try:
                used_i = int(used_value or 0)
            except Exception:
                used_i = 0

            try:
                limit_i = int(limit_value or 0)
            except Exception:
                limit_i = 0

            if used_i < 0:
                used_i = 0
            if limit_i < 0:
                limit_i = 0

            if limit_i <= 0:
                return 100 if used_i > 0 else 0

            pct = int((used_i * 100) / limit_i)

            if pct < 0:
                return 0
            if pct > 100:
                return 100
            return pct

        async def _cooldown_left_locked_fallback(conn_ , uid_: int) -> int:
            v = await conn_.fetchval(
                """
                SELECT GREATEST(0, EXTRACT(EPOCH FROM (until_at - NOW()))::BIGINT)
                FROM withdraw_cooldown
                WHERE user_id=$1 AND until_at > NOW()
                """ , int(uid_) , )
            return _safe_non_negative_local(v , 0)

        async def _update_quota_window_safe(conn_ , * , uid_: int , daily_limit_: int , used_value_: int ,
                status_: str , cooldown_left_sec_: int = 0 , cooldown_until_=None , ) -> None:
            dl_ = _safe_non_negative_local(daily_limit_ , 0)
            if dl_ <= 0:
                dl_ = 100

            used_raw_ = _safe_non_negative_local(used_value_ , 0)
            used_store_ = min(int(used_raw_) , int(dl_))
            remaining_ = max(0 , int(dl_) - int(used_store_))
            used_percent_ = _safe_used_percent_local(int(used_store_) , int(dl_))
            cooldown_left_sec_ = _safe_non_negative_local(cooldown_left_sec_ , 0)

            await conn_.execute(
                """
                UPDATE withdraw_quota_window
                   SET used_in_window     = $2,
                       daily_limit        = $3,
                       remaining          = $4,
                       used_percent       = $5,
                       status             = $6,
                       cooldown_left_sec  = $7,
                       cooldown_until     = $8,
                       updated_at         = NOW()
                 WHERE user_id = $1
                """ , int(uid_) , int(used_store_) , int(dl_) , int(remaining_) , int(used_percent_) , str(status_) ,
                int(cooldown_left_sec_) , cooldown_until_ , )

        async def _set_cooldown_best_effort(conn_ , uid_: int , secs_: int , cause_: str) -> bool:
            secs_ = _safe_non_negative_local(secs_ , 0)
            if secs_ <= 0:
                try:
                    secs_ = _safe_non_negative_local(
                        getattr(self , "WITHDRAW_DEFAULT_COOLDOWN_SEC" , 12 * 3600) or (12 * 3600) , 12 * 3600 , )
                except Exception:
                    secs_ = 12 * 3600

            if secs_ <= 0:
                print(f"[ВЫВОД][{rid}] 🟨 cooldown skipped: bad secs={secs_}")
                return False

            cause_ = _safe_str_local(cause_ , "daily_limit")

            helper = getattr(self , "_set_withdraw_cooldown_idempotent" , None)
            if callable(helper):
                try:
                    return bool(
                        await helper(
                            conn_ , user_id=int(uid_) , cooldown_seconds=int(secs_) , cause=str(cause_) , ))
                except Exception as e:
                    print(f"[ВЫВОД][{rid}] 🟠 helper _set_withdraw_cooldown_idempotent failed -> fallback SQL: {e!r}")

            await conn_.execute(
                """
                INSERT INTO withdraw_cooldown(user_id, started_at, until_at, cause)
                VALUES ($1, NOW(), NOW() + ($2::bigint * INTERVAL '1 second'), $3)
                ON CONFLICT (user_id) DO UPDATE
                SET
                    started_at = CASE
                        WHEN withdraw_cooldown.until_at > NOW()
                            THEN withdraw_cooldown.started_at
                        ELSE EXCLUDED.started_at
                    END,
                    until_at = CASE
                        WHEN withdraw_cooldown.until_at > NOW()
                            THEN withdraw_cooldown.until_at
                        ELSE EXCLUDED.until_at
                    END,
                    cause = CASE
                        WHEN withdraw_cooldown.until_at > NOW()
                            THEN withdraw_cooldown.cause
                        ELSE EXCLUDED.cause
                    END
                """ , int(uid_) , int(secs_) , str(cause_) , )
            print(f"[ВЫВОД][{rid}] ✅ cooldown set via SQL fallback uid={uid_} secs={secs_} cause={cause_!r}")
            return True

        rid = _safe_str_local(request_id , "")
        if not rid:
            rid = uuid.uuid4().hex [ :16 ]
        rid = rid [ :64 ].strip() or uuid.uuid4().hex [ :16 ]

        reason = _safe_str_local(reason , "user_payout")
        chat_name = _safe_str_local(chat_name , "")

        t0 = time.perf_counter()

        try:
            uid = int(user_id)
            amount_i = int(amount)
        except Exception as e:
            print(f"[ВЫВОД][{rid}] 🟥 bad args user_id={user_id!r} amount={amount!r} err={e!r}")
            return _make_fail("invalid_amount")

        if uid <= 0:
            print(f"[ВЫВОД][{rid}] 🟥 invalid_user uid={uid}")
            return _make_fail("invalid_user")

        if amount_i <= 0:
            print(f"[ВЫВОД][{rid}] 🟥 invalid_amount amount={amount_i}")
            return _make_fail("invalid_amount")

        if not getattr(self , "pool" , None):
            print(f"[ВЫВОД][{rid}] 🟥 pool_not_ready")
            return _make_fail("pool_not_ready")

        print(
            f"[ВЫВОД][{rid}] ▶️ start uid={uid} amount={amount_i} "
            f"chat_id={chat_id} chat_name={chat_name!r} reason={reason!r}")

        payload: Optional [ Dict [ str , Any ] ] = None
        new_balance_after_commit: Optional [ int ] = None

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock($1::bigint)" , int(uid))

                # ---------------------------------------------------
                # 0) идемпотентность по request_id
                # ---------------------------------------------------
                prev = await conn.fetchrow(
                    """
                    SELECT amount, created_at
                    FROM withdraw_log
                    WHERE user_id = $1 AND request_id = $2
                    """ , int(uid) , str(rid) , )
                if prev:
                    bal_now = _safe_non_negative_local(
                        await conn.fetchval(
                            "SELECT balance FROM users WHERE user_id=$1" , int(uid) , ) or 0 , 0 , )

                    cd_until = await conn.fetchval(
                        """
                        SELECT until_at
                        FROM withdraw_cooldown
                        WHERE user_id=$1 AND until_at > NOW()
                        """ , int(uid) , )

                    if cd_until is not None:
                        left = _safe_non_negative_local(
                            await conn.fetchval(
                                """
                                SELECT GREATEST(0, EXTRACT(EPOCH FROM (until_at - NOW()))::BIGINT)
                                FROM withdraw_cooldown
                                WHERE user_id=$1 AND until_at > NOW()
                                """ , int(uid) , ) or 0 , 0 , )
                        print(f"[ВЫВОД][{rid}] 🟨 DUPLICATE -> cooldown_active left={left}s bal={bal_now}")
                        return {"ok": True , "committed": False , "duplicate": True , "should_send_to_channel": False ,
                            "request_id": rid , "user_balance_after": int(bal_now) , "allowed": False ,
                            "cooldown_left": int(left) , "remaining": 0 , "reason": "duplicate_cooldown" ,
                            "status": "duplicate_cooldown" , }

                    qd = await conn.fetchrow(
                        """
                        SELECT daily_limit, used_in_window, remaining
                        FROM withdraw_quota_window
                        WHERE user_id=$1
                        """ , int(uid) , )
                    dl0 = _safe_non_negative_local(qd [ "daily_limit" ] , 0) if qd else 0
                    used0 = _safe_non_negative_local(qd [ "used_in_window" ] , 0) if qd else 0
                    rem0 = _safe_non_negative_local(qd [ "remaining" ] , 0) if qd else 0

                    print(f"[ВЫВОД][{rid}] 🟨 DUPLICATE -> ok bal={bal_now} limit={dl0} used={used0} remaining={rem0}")
                    return {"ok": True , "committed": False , "duplicate": True , "should_send_to_channel": False ,
                        "request_id": rid , "user_balance_after": int(bal_now) , "daily_limit": int(dl0) ,
                        "used": int(used0) , "remaining": int(rem0) , "cooldown_set": False , "cooldown_left": 0 ,
                        "reason": "duplicate_ok" , "status": "duplicate_ok" , }

                # ---------------------------------------------------
                # 1) лимиты
                # ---------------------------------------------------
                daily_limit = 0
                cooldown_sec = 0

                try:
                    daily_limit , cooldown_sec = await self.get_user_withdraw_limits(uid)
                except Exception as e:
                    print(f"[ВЫВОД][{rid}] 🟠 get_user_withdraw_limits failed: {e!r}")

                dl = _safe_non_negative_local(daily_limit , 0)
                cd = _safe_non_negative_local(cooldown_sec , 0)

                if dl <= 0:
                    try:
                        dl = _safe_non_negative_local(await self.get_canwithdrawal(uid) or 0 , 0)
                    except Exception as e:
                        print(f"[ВЫВОД][{rid}] 🟠 get_canwithdrawal failed: {e!r}")

                if dl <= 0:
                    dl = _safe_non_negative_local(Default_WITHDRAW_DEFAULT_DAILY_LIMIT , 0)

                if dl <= 0:
                    dl = 100

                if cd <= 0:
                    cd = _safe_non_negative_local(
                        getattr(self , "WITHDRAW_DEFAULT_COOLDOWN_SEC" , 12 * 3600) or (12 * 3600) , 12 * 3600 , )

                ensure_helper = getattr(self , "_ensure_quota_row_locked" , None)
                if callable(ensure_helper):
                    await ensure_helper(conn , user_id=uid , daily_limit=int(dl))
                else:
                    await conn.execute(
                        """
                        INSERT INTO withdraw_quota_window(
                            user_id, window_started_at, used_in_window, daily_limit, remaining,
                            used_percent, status, cooldown_left_sec, cooldown_until, updated_at
                        )
                        VALUES ($1, NOW(), 0, $2, $2, 0, 'OK', 0, NULL, NOW())
                        ON CONFLICT (user_id) DO NOTHING
                        """ , int(uid) , int(dl) , )

                normalize_helper = getattr(self , "_normalize_withdraw_quota_row_locked" , None)
                if callable(normalize_helper):
                    await normalize_helper(conn , user_id=uid , daily_limit=int(dl))

                cleanup_helper = getattr(self , "_cleanup_expired_cooldown_and_reset_quota_locked" , None)
                if callable(cleanup_helper):
                    try:
                        await cleanup_helper(conn , user_id=uid , daily_limit=int(dl))
                    except Exception as e:
                        print(f"[ВЫВОД][{rid}] 🟠 warn cleanup_expired_cooldown: {e!r}")

                if callable(normalize_helper):
                    await normalize_helper(conn , user_id=uid , daily_limit=int(dl))

                cd_active = await conn.fetchval(
                    """
                    SELECT until_at
                    FROM withdraw_cooldown
                    WHERE user_id=$1 AND until_at > NOW()
                    FOR UPDATE
                    """ , int(uid) , )
                if cd_active:
                    left_helper = getattr(self , "_get_withdraw_cooldown_left_locked" , None)
                    if callable(left_helper):
                        left = _safe_non_negative_local(await left_helper(conn , user_id=uid) or 0 , 0)
                    else:
                        left = await _cooldown_left_locked_fallback(conn , uid)

                    print(f"[ВЫВОД][{rid}] 🟥 cooldown_active left={left}s")
                    return _make_fail("cooldown_active" , cooldown_left=int(left) , remaining=0)

                bal = await conn.fetchval(
                    "SELECT balance FROM users WHERE user_id=$1 FOR UPDATE" , int(uid) , )
                if bal is None:
                    print(f"[ВЫВОД][{rid}] 🟥 user_not_found")
                    return _make_fail("user_not_found")

                bal = _safe_non_negative_local(bal , 0)

                if bal < amount_i:
                    print(f"[ВЫВОД][{rid}] 🟥 insufficient_funds bal={bal} need={amount_i}")
                    return _make_fail("insufficient_funds" , balance=int(bal))

                q = await conn.fetchrow(
                    """
                    SELECT window_started_at, daily_limit
                    FROM withdraw_quota_window
                    WHERE user_id=$1
                    FOR UPDATE
                    """ , int(uid) , )

                ws = q [ "window_started_at" ] if q else None
                dl_db = _safe_non_negative_local(q [ "daily_limit" ] , dl) if q else int(dl)
                if dl_db <= 0:
                    dl_db = int(dl)

                if not ws:
                    ws = await conn.fetchval("SELECT NOW()")
                    await conn.execute(
                        """
                        UPDATE withdraw_quota_window
                        SET window_started_at=$2, updated_at=NOW()
                        WHERE user_id=$1
                        """ , int(uid) , ws , )

                used_truth = _safe_non_negative_local(
                    await conn.fetchval(
                        """
                        SELECT COALESCE(SUM(amount),0)::BIGINT
                        FROM withdraw_log
                        WHERE user_id=$1 AND created_at >= $2
                        """ , int(uid) , ws , ) or 0 , 0 , )

                remaining_truth = max(0 , int(dl_db) - int(used_truth))

                print(
                    f"[ВЫВОД][{rid}] 🧾 SELF-HEAL(pre) ws={ws} limit={dl_db} "
                    f"used_truth={used_truth} remaining_truth={remaining_truth} "
                    f"bal={bal} amount={amount_i}")

                if int(remaining_truth) <= 0:
                    active_cd_check = await conn.fetchval(
                        """
                        SELECT 1
                        FROM withdraw_cooldown
                        WHERE user_id=$1 AND until_at > NOW()
                        LIMIT 1
                        """ , int(uid) , )

                    if not active_cd_check:
                        ws = await conn.fetchval("SELECT NOW()")

                        await conn.execute(
                            """
                            UPDATE withdraw_quota_window
                            SET
                                window_started_at   = $2,
                                used_in_window      = 0,
                                daily_limit         = $3,
                                remaining           = $3,
                                used_percent        = 0,
                                status              = 'OK',
                                cooldown_left_sec   = 0,
                                cooldown_until      = NULL,
                                updated_at          = NOW()
                            WHERE user_id = $1
                            """ , int(uid) , ws , int(dl_db) , )

                        used_truth = 0
                        remaining_truth = int(dl_db)

                        print(
                            f"[ВЫВОД][{rid}] ♻️ HARD RESET window after expired cooldown "
                            f"new_ws={ws} new_remaining={remaining_truth}")

                if amount_i > int(remaining_truth):
                    cooldown_left = 0
                    cooldown_set = False
                    cd_until2 = None
                    used_store_pre = min(
                        _safe_non_negative_local(used_truth , 0) , _safe_non_negative_local(dl_db , 0) , )

                    if int(remaining_truth) <= 0 and int(cd) > 0:
                        cooldown_set = await _set_cooldown_best_effort(
                            conn , uid_=uid , secs_=int(cd) , cause_="daily_limit" , )

                        left_helper = getattr(self , "_get_withdraw_cooldown_left_locked" , None)
                        if callable(left_helper):
                            cooldown_left = _safe_non_negative_local(await left_helper(conn , user_id=uid) or 0 , 0)
                        else:
                            cooldown_left = await _cooldown_left_locked_fallback(conn , uid)

                        cd_until2 = await conn.fetchval(
                            """
                            SELECT until_at
                            FROM withdraw_cooldown
                            WHERE user_id=$1 AND until_at > NOW()
                            """ , int(uid) , )

                        await _update_quota_window_safe(
                            conn , uid_=int(uid) , daily_limit_=int(dl_db) , used_value_=int(used_store_pre) ,
                            status_="COOLDOWN" , cooldown_left_sec_=int(cooldown_left) , cooldown_until_=cd_until2 , )
                    else:
                        await _update_quota_window_safe(
                            conn , uid_=int(uid) , daily_limit_=int(dl_db) , used_value_=int(used_store_pre) ,
                            status_="OK" if int(dl_db) - int(used_store_pre) > 0 else "LIMIT_REACHED" ,
                            cooldown_left_sec_=0 , cooldown_until_=None , )

                    print(
                        f"[ВЫВОД][{rid}] 🟥 exceeds_remaining amount={amount_i} "
                        f"remaining_truth={remaining_truth} cd_set={cooldown_set} cd_left={cooldown_left}")
                    return _make_fail(
                        "exceeds_remaining" , daily_limit=int(dl_db) , used=int(min(int(used_truth) , int(dl_db))) ,
                        remaining=int(remaining_truth) , cooldown_set=bool(cooldown_set) ,
                        cooldown_left=int(cooldown_left) , )

                print(f"[ВЫВОД][{rid}] 💳 UPDATE users.balance -{amount_i}")
                row_bal = await conn.fetchrow(
                    """
                    UPDATE users
                       SET balance = balance - $2
                     WHERE user_id = $1
                    RETURNING balance
                    """ , int(uid) , int(amount_i) , )
                if not row_bal:
                    print(f"[ВЫВОД][{rid}] 🟥 balance_update_failed")
                    return _make_fail("balance_update_failed")

                new_bal = _safe_non_negative_local(row_bal [ "balance" ] , 0)

                print(f"[ВЫВОД][{rid}] 🧾 INSERT withdraw_log amount={amount_i} request_id={rid!r}")
                await conn.execute(
                    """
                    INSERT INTO withdraw_log(user_id, amount, chat_id, chat_name, reason, created_at, request_id)
                    VALUES ($1, $2, $3, $4, $5, NOW(), $6)
                    """ , int(uid) , int(amount_i) , chat_id , (chat_name or None) , str(reason) , str(rid) , )

                used_truth_after = _safe_non_negative_local(
                    await conn.fetchval(
                        """
                        SELECT COALESCE(SUM(amount),0)::BIGINT
                        FROM withdraw_log
                        WHERE user_id=$1 AND created_at >= $2
                        """ , int(uid) , ws , ) or 0 , 0 , )

                used_store = min(
                    _safe_non_negative_local(used_truth_after , 0) , max(0 , int(dl_db)) , )
                remaining_store = max(0 , int(dl_db) - int(used_store))
                used_percent_store = _safe_used_percent_local(int(used_store) , int(dl_db))

                print(
                    f"[ВЫВОД][{rid}] 🧾 QUOTA PRE-SAFE truth_used={used_truth_after} "
                    f"store_used={used_store}/{dl_db} remaining={remaining_store} "
                    f"used_percent={used_percent_store}")

                status = "OK" if remaining_store > 0 else "LIMIT_REACHED"
                cooldown_left_after = 0
                cd_until_after = None
                cooldown_set2 = False

                if remaining_store <= 0 and int(cd) > 0:
                    cooldown_set2 = await _set_cooldown_best_effort(
                        conn , uid_=uid , secs_=int(cd) , cause_=f"daily_limit:{rid}" , )

                    left_helper = getattr(self , "_get_withdraw_cooldown_left_locked" , None)
                    if callable(left_helper):
                        cooldown_left_after = _safe_non_negative_local(await left_helper(conn , user_id=uid) or 0 , 0)
                    else:
                        cooldown_left_after = await _cooldown_left_locked_fallback(conn , uid)

                    cd_until_after = await conn.fetchval(
                        """
                        SELECT until_at
                        FROM withdraw_cooldown
                        WHERE user_id=$1 AND until_at > NOW()
                        """ , int(uid) , )
                    status = "COOLDOWN"

                print(
                    f"[ВЫВОД][{rid}] 🧾 QUOTA UPDATE truth_used={used_truth_after} "
                    f"store_used={used_store}/{dl_db} store_remaining={remaining_store} "
                    f"used_percent={used_percent_store} status={status} cd_left={cooldown_left_after}")

                await _update_quota_window_safe(
                    conn , uid_=int(uid) , daily_limit_=int(dl_db) , used_value_=int(used_truth_after) ,
                    status_=str(status) , cooldown_left_sec_=int(cooldown_left_after) ,
                    cooldown_until_=cd_until_after , )

                dt = time.perf_counter() - t0
                print(f"[ВЫВОД][{rid}] ✅ OK new_bal={new_bal} dt={dt:.4f}s")

                payload = {"ok": True , "committed": True , "duplicate": False , "should_send_to_channel": True ,
                    "request_id": rid , "user_balance_after": int(new_bal) , "daily_limit": int(dl_db) ,
                    "used": int(used_store) , "remaining": int(remaining_store) , "cooldown_set": bool(cooldown_set2) ,
                    "cooldown_left": int(cooldown_left_after) , "status": "committed" , }
                new_balance_after_commit = int(new_bal)

        if payload and payload.get("ok") and payload.get("committed") and isinstance(new_balance_after_commit , int):
            try:
                if hasattr(self , "sync_user_balance_cache"):
                    await self.sync_user_balance_cache(int(user_id) , int(new_balance_after_commit))
            except Exception as e:
                print(f"[ВЫВОД][{rid}] 🟠 cache sync failed: {e!r}")

        return payload or _make_fail("unknown")

    # ============================================================
    # ✅ САМОЛЕЧЕНИЕ: ИСТЁК КУЛДАУН -> УДАЛИТЬ -> СБРОСИТЬ ОКНО (вернуть remaining)
    # ============================================================
    async def _cleanup_expired_cooldown_and_reset_quota_locked(self , conn , * , user_id: int ,
            daily_limit: int , ) -> bool:
        """
        Если кулдаун истёк:
        - удаляем протухший withdraw_cooldown
        - сбрасываем withdraw_quota_window
        - нормализуем лимит перед reset

        ВАЖНО:
        - вызывать только под lock / внутри транзакции
        - новый cooldown НЕ создаёт
        """

        def _safe_int_local(v , default: int = 0) -> int:
            try:
                return int(v)
            except Exception:
                return int(default)

        def _safe_non_negative_local(v , default: int = 0) -> int:
            x = _safe_int_local(v , default)
            return x if x >= 0 else 0

        uid = int(user_id)
        dl = _safe_non_negative_local(daily_limit , 0)

        # ---------------------------------------------------
        # 1) удаляем только ПРОТУХШИЙ cooldown
        # ---------------------------------------------------
        res = await conn.execute(
            """
            DELETE FROM withdraw_cooldown
            WHERE user_id=$1 AND until_at <= NOW()
            """ , uid , )

        try:
            deleted = int((res or "0").split() [ -1 ])
        except Exception:
            deleted = 0

        if deleted <= 0:
            return False

        # ---------------------------------------------------
        # 2) нормализуем daily_limit
        # ---------------------------------------------------
        if dl <= 0:
            try:
                if hasattr(self , "get_canwithdrawal"):
                    dl = _safe_non_negative_local(await self.get_canwithdrawal(uid) or 0 , 0)
            except Exception as e:
                _vdbg(f"[ЛИМИТЫ][AUTO-RESET][WARN] get_canwithdrawal uid={uid} err={e!r}")
                dl = 0

        if dl <= 0:
            try:
                dl = _safe_non_negative_local(Default_WITHDRAW_DEFAULT_DAILY_LIMIT , 0)
            except Exception:
                dl = 100

        if dl <= 0:
            dl = 100

        print(
            f"[ЛИМИТЫ][AUTO-RESET] ✅ uid={uid} кулдаун истёк -> удалён({deleted}) "
            f"-> сброс окна, лимит={dl}")

        # ---------------------------------------------------
        # 3) жёсткий reset quota window
        # ---------------------------------------------------
        await conn.execute(
            """
            INSERT INTO withdraw_quota_window(
                user_id,
                window_started_at,
                used_in_window,
                daily_limit,
                remaining,
                used_percent,
                status,
                cooldown_left_sec,
                cooldown_until,
                updated_at
            )
            VALUES ($1, NOW(), 0, $2, $2, 0, 'OK', 0, NULL, NOW())
            ON CONFLICT (user_id) DO UPDATE
              SET window_started_at = NOW(),
                  used_in_window    = 0,
                  daily_limit       = EXCLUDED.daily_limit,
                  remaining         = EXCLUDED.remaining,
                  used_percent      = 0,
                  status            = 'OK',
                  cooldown_left_sec = 0,
                  cooldown_until    = NULL,
                  updated_at        = NOW()
            """ , uid , int(dl) , )

        # ---------------------------------------------------
        # 4) лог текущего состояния после reset
        # ---------------------------------------------------
        try:
            row = await conn.fetchrow(
                """
                SELECT
                    user_id,
                    window_started_at,
                    used_in_window,
                    daily_limit,
                    remaining,
                    used_percent,
                    status,
                    cooldown_left_sec,
                    cooldown_until
                FROM withdraw_quota_window
                WHERE user_id=$1
                """ , uid , )
            _vdbg(f"[ЛИМИТЫ][AUTO-RESET][STATE] uid={uid} row={dict(row) if row else None}")
        except Exception as e:
            _vdbg(f"[ЛИМИТЫ][AUTO-RESET][WARN] state fetch uid={uid} err={e!r}")

        return True

    async def _get_withdraw_cooldown_left_locked(self , conn , * , user_id: int) -> int:
        """
        Возвращает остаток активного кулдауна в секундах.
        Работает внутри уже открытой транзакции.
        """
        try:
            uid = int(user_id)
        except Exception:
            uid = 0

        if uid <= 0:
            return 0

        v = await conn.fetchval(
            """
            SELECT GREATEST(0, EXTRACT(EPOCH FROM (until_at - NOW()))::BIGINT)
            FROM withdraw_cooldown
            WHERE user_id = $1 AND until_at > NOW()
            """ , uid , )
        try:
            return int(v or 0)
        except Exception:
            return 0

    async def _ensure_quota_row_locked(self , conn , * , user_id: int , daily_limit: int) -> None:
        """
        Гарантирует строку в withdraw_quota_window.
        """
        uid = int(user_id)
        dl = self._safe_non_negative_int(daily_limit , 0)

        await conn.execute(
            """
            INSERT INTO withdraw_quota_window(
                user_id, window_started_at, used_in_window, daily_limit, remaining,
                used_percent, status, cooldown_left_sec, cooldown_until, updated_at
            )
            VALUES ($1, NOW(), 0, $2, $2, 0, 'OK', 0, NULL, NOW())
            ON CONFLICT (user_id) DO NOTHING
            """ , uid , int(dl) , )
    async def upsert_withdraw_limit(self , user_id: int , daily_amount_limit: Optional [ int ] = None ,
                                    cooldown_seconds: Optional [ int ] = None) -> None:
        """
        Установить/обновить персональные лимиты. Не переданный параметр - берём текущее значение/дефолт.
        """
        # берём текущие (или дефолты)
        current_limit , current_cooldown = await self.get_user_withdraw_limits(user_id)
        new_limit = daily_amount_limit if daily_amount_limit is not None else current_limit
        new_cd = cooldown_seconds if cooldown_seconds is not None else current_cooldown

        sql = """
        INSERT INTO withdraw_limits (user_id, daily_amount_limit, cooldown_seconds, updated_at)
        VALUES ($1, $2, $3, now())
        ON CONFLICT (user_id) DO UPDATE
          SET daily_amount_limit = EXCLUDED.daily_amount_limit,
              cooldown_seconds   = EXCLUDED.cooldown_seconds,
              updated_at         = now();
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql , user_id , int(new_limit) , int(new_cd))

    # ---------- кулдауны ----------

    async def _get_active_cooldown(self , user_id: int):
        sql = "SELECT started_at, until_at, cause FROM withdraw_cooldown WHERE user_id = $1 AND until_at > now()"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql , user_id)

    # ============================================================
    # ✅ 11) Тех-обслуживание: чистка просроченных кулдаунов пачкой
    # ============================================================
    async def remove_expired_withdraw_cooldowns(self, user_id) -> int:
        """
        Чистим просроченные кулдауны.
        Для затронутых пользователей сбрасываем окно (used=0, remaining=daily_limit).
        """
        if not getattr(self , "pool" , None):
            return 0

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch("SELECT user_id FROM withdraw_cooldown WHERE until_at <= NOW()")
                user_ids = [ int(r [ "user_id" ]) for r in rows ] if rows else [ ]

                res = await conn.execute("DELETE FROM withdraw_cooldown WHERE until_at <= NOW()")
                try:
                    deleted_count = int((res or "0").split() [ -1 ])
                except Exception:
                    deleted_count = 0

                if user_ids:
                    # сброс окна (daily_limit берём из withdraw_limits, иначе дефолт)
                    # 1) пользователи с персональным лимитом
                    await conn.execute(
                        """
                        INSERT INTO withdraw_quota_window(
                            user_id, window_started_at, used_in_window, daily_limit, remaining,
                            used_percent, status, cooldown_left_sec, cooldown_until, updated_at
                        )
                        SELECT l.user_id, NOW(), 0,
                               COALESCE(NULLIF(l.daily_amount_limit,0), $2),
                               COALESCE(NULLIF(l.daily_amount_limit,0), $2),
                               0, 'OK', 0, NULL, NOW()
                          FROM withdraw_limits l
                         WHERE l.user_id = ANY($1::BIGINT[])
                        ON CONFLICT (user_id) DO UPDATE
                          SET window_started_at = EXCLUDED.window_started_at,
                              used_in_window    = 0,
                              daily_limit       = EXCLUDED.daily_limit,
                              remaining         = EXCLUDED.remaining,
                              used_percent      = 0,
                              status            = 'OK',
                              cooldown_left_sec = 0,
                              cooldown_until    = NULL,
                              updated_at        = NOW()
                        """ , user_ids , int(await self.get_canwithdrawal(user_id)))

                    # 2) пользователи без строки в withdraw_limits
                    await conn.execute(
                        """
                        INSERT INTO withdraw_quota_window(
                            user_id, window_started_at, used_in_window, daily_limit, remaining,
                            used_percent, status, cooldown_left_sec, cooldown_until, updated_at
                        )
                        SELECT u_id, NOW(), 0, $2, $2, 0, 'OK', 0, NULL, NOW()
                          FROM UNNEST($1::BIGINT[]) AS t(u_id)
                         WHERE NOT EXISTS (SELECT 1 FROM withdraw_limits l WHERE l.user_id = t.u_id)
                        ON CONFLICT (user_id) DO UPDATE
                          SET window_started_at = EXCLUDED.window_started_at,
                              used_in_window    = 0,
                              daily_limit       = EXCLUDED.daily_limit,
                              remaining         = EXCLUDED.remaining,
                              used_percent      = 0,
                              status            = 'OK',
                              cooldown_left_sec = 0,
                              cooldown_until    = NULL,
                              updated_at        = NOW()
                        """ , user_ids , int(await self.get_canwithdrawal(user_id)))

                _vdbg(f"[ЛИМИТЫ][CLEANUP] удалено кулдаунов: {deleted_count}. сброшено окон: {len(user_ids)}")
                return deleted_count

    # ============================================================
    # ✅ 6) can_withdraw - лёгкая обёртка для UI
    # ============================================================
    async def can_withdraw(self , user_id: int) -> dict:
        uid = int(user_id)
        _vdbg(f"[ЛИМИТЫ][DEBUG] can_withdraw({uid})")
        st = await self.refresh_withdraw_quota_if_needed(uid)

        if not st.get("allowed"):
            return {"allowed": False , "reason": st.get("reason" , "blocked") , "remaining": 0 ,
                "cooldown_left": int(st.get("cooldown_left") or 0) , "daily_limit": int(st.get("daily_limit") or 0) ,
                "used": st.get("used") , }

        return {"allowed": True , "reason": "ok" , "remaining": int(st.get("remaining") or 0) ,
            "daily_limit": int(st.get("daily_limit") or 0) , "used": int(st.get("used") or 0) ,
            "cooldown_seconds": int(st.get("cooldown_seconds") or 0) , }

    # ---------------------------------------------------------------
    # Финальная операция - выполнить вывод
    # ---------------------------------------------------------------
    async def add_withdraw(self , user_id: int , amount: int , chat_id=None , chat_name=None , reason=None , * ,
            request_id: Optional [ str ] = None) -> dict:
        """
        ✅ Строго (как у тебя):
        - pg_advisory_xact_lock(user_id)
        - FOR UPDATE: balance, cooldown, quota window
        - used считается по withdraw_log внутри транзакции (истина)
        - request_id: двойной клик НЕ спишет повторно
        - ✅ кулдаун ставится ТОЛЬКО идемпотентно (НЕ перезапускает таймер)
        - ✅ если remaining == 0 -> ставим кулдаун и возвращаем cooldown_left
        """
        rid = request_id or uuid.uuid4().hex [ :16 ]
        t0 = time.perf_counter()

        print(f"[ВЫВОД][DEBUG] add_withdraw(user={user_id}, amount={amount}, rid={rid})")

        try:
            uid = int(user_id)
            amount_i = int(amount)
        except Exception:
            return {"ok": False , "error": "invalid_amount"}

        if amount_i <= 0:
            return {"ok": False , "error": "invalid_amount"}

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # 0) анти-гонки
                await conn.execute("SELECT pg_advisory_xact_lock($1::bigint)" , uid)
                now = await conn.fetchval("SELECT NOW()")

                # 1) идемпотентность по request_id
                prev = await conn.fetchrow(
                    "SELECT amount, created_at FROM withdraw_log WHERE user_id=$1 AND request_id=$2" , uid , rid)
                if prev:
                    print(f"[ВЫВОД][DEBUG] DUPLICATE rid={rid} -> ignore повтор")
                    # возвращаем текущее состояние (в транзакции - быстрее/правильнее)
                    await conn.execute("DELETE FROM withdraw_cooldown WHERE user_id=$1 AND until_at <= NOW()" , uid)

                    cd_active = await conn.fetchval(
                        "SELECT until_at FROM withdraw_cooldown WHERE user_id=$1 AND until_at > NOW()" , uid)
                    if cd_active:
                        left = int(
                            await conn.fetchval(
                                "SELECT GREATEST(EXTRACT(EPOCH FROM ($1 - NOW()))::BIGINT, 0)" , cd_active) or 0)
                        bal_now = int(await conn.fetchval("SELECT balance FROM users WHERE user_id=$1" , uid) or 0)
                        return {"ok": True , "duplicate": True , "user_balance_after": bal_now , "allowed": False ,
                                "cooldown_left": left , "remaining": 0}

                    # если кулдауна нет - посчитаем remaining
                    daily_limit , cooldown_seconds = await self.get_user_withdraw_limits(uid)
                    daily_limit = int(daily_limit or 0)
                    cooldown_seconds = int(cooldown_seconds or 0)

                    await conn.execute(
                        """
                        INSERT INTO withdraw_quota_window(user_id, window_started_at)
                        VALUES ($1, NOW())
                        ON CONFLICT (user_id) DO NOTHING
                        """ , uid)
                    ws = await conn.fetchval(
                        "SELECT window_started_at FROM withdraw_quota_window WHERE user_id=$1" , uid)
                    used = 0
                    if ws:
                        used = int(
                            await conn.fetchval(
                                """
                            SELECT COALESCE(SUM(amount),0)::BIGINT
                            FROM withdraw_log
                            WHERE user_id=$1 AND created_at >= $2
                            """ , uid , ws) or 0)

                    remaining = max(0 , int(daily_limit) - int(used))
                    bal_now = int(await conn.fetchval("SELECT balance FROM users WHERE user_id=$1" , uid) or 0)
                    return {"ok": True , "duplicate": True , "user_balance_after": bal_now ,
                            "daily_limit": daily_limit , "used": used , "remaining": remaining}

                # 2) баланс FOR UPDATE
                bal = await conn.fetchval("SELECT balance FROM users WHERE user_id=$1 FOR UPDATE" , uid)
                if bal is None:
                    return {"ok": False , "error": "user_not_found"}
                bal = int(bal or 0)

                if bal < amount_i:
                    return {"ok": False , "error": "insufficient_funds"}

                # 3) кулдаун FOR UPDATE + самолечение
                cd = await conn.fetchrow(
                    "SELECT started_at, until_at, cause FROM withdraw_cooldown WHERE user_id=$1 FOR UPDATE" , uid)
                if cd and cd [ "until_at" ] and cd [ "until_at" ] > now:
                    left = int(
                        await conn.fetchval(
                            "SELECT GREATEST(EXTRACT(EPOCH FROM ($1 - NOW()))::BIGINT, 0)" , cd [ "until_at" ]) or 0)
                    return {"ok": False , "error": "cooldown_active" , "cooldown_left": left}

                if cd and cd [ "until_at" ] and cd [ "until_at" ] <= now:
                    await conn.execute("DELETE FROM withdraw_cooldown WHERE user_id=$1" , uid)

                # 4) limits
                daily_limit , cooldown_seconds = await self.get_user_withdraw_limits(uid)
                daily_limit = int(daily_limit or 0)
                cooldown_seconds = int(cooldown_seconds or 0)

                # 5) окно квоты FOR UPDATE
                await conn.execute(
                    """
                    INSERT INTO withdraw_quota_window(user_id, window_started_at)
                    VALUES ($1, NOW())
                    ON CONFLICT (user_id) DO NOTHING
                    """ , uid)
                ws = await conn.fetchval(
                    "SELECT window_started_at FROM withdraw_quota_window WHERE user_id=$1 FOR UPDATE" , uid)
                if not ws:
                    ws = now
                    await conn.execute(
                        "UPDATE withdraw_quota_window SET window_started_at=$2 WHERE user_id=$1" , uid , ws)

                # 6) used/remaining (истина)
                used = int(
                    await conn.fetchval(
                        """
                    SELECT COALESCE(SUM(amount),0)::BIGINT
                    FROM withdraw_log
                    WHERE user_id=$1 AND created_at >= $2
                    """ , uid , ws) or 0)

                remaining = max(0 , int(daily_limit) - int(used))

                print(
                    f"[ВЫВОД][DEBUG] limit={daily_limit} used={used} remaining={remaining} bal={bal} amount={amount_i}")

                # 7) запрет превышения
                if amount_i > remaining:
                    cooldown_set = False
                    cooldown_left = 0

                    # ✅ ВАЖНО: кулдаун ставим ТОЛЬКО идемпотентно (не сбрасывает таймер)
                    if remaining <= 0 and cooldown_seconds > 0:
                        cooldown_set = await self._set_withdraw_cooldown_idempotent(
                            conn , user_id=uid , cooldown_seconds=cooldown_seconds , cause="daily_limit")
                        cooldown_left = await self._get_withdraw_cooldown_left_locked(conn , user_id=uid)

                    return {"ok": False , "error": "exceeds_remaining" , "daily_limit": int(daily_limit) ,
                        "used": int(used) , "remaining": int(remaining) , "cooldown_set": bool(cooldown_set) ,
                        "cooldown_left": int(cooldown_left) , }

                # 8) списание баланса (лучше RETURNING, чтобы не читать второй раз)
                row_bal = await conn.fetchrow(
                    """
                    UPDATE users
                       SET balance = balance - $2
                     WHERE user_id = $1
                    RETURNING balance
                    """ , uid , amount_i)
                if not row_bal:
                    return {"ok": False , "error": "balance_update_failed"}

                new_bal = int(row_bal [ "balance" ] or 0)

                # 9) лог
                await conn.execute(
                    """
                    INSERT INTO withdraw_log (user_id, amount, chat_id, chat_name, reason, created_at, request_id)
                    VALUES ($1, $2, $3, $4, $5, NOW(), $6)
                    """ , uid , amount_i , chat_id , chat_name , reason or "user_payout" , rid)

                used_after = int(used) + int(amount_i)
                remaining_after = max(0 , int(daily_limit) - int(used_after))

                cooldown_set = False
                cooldown_left = 0

                # 10) ✅ если лимит выбит - ставим кулдаун ИДЕМПОТЕНТНО (не сбрасывает)
                if remaining_after <= 0 and cooldown_seconds > 0:
                    cooldown_set = await self._set_withdraw_cooldown_idempotent(
                        conn , user_id=uid , cooldown_seconds=cooldown_seconds , cause="daily_limit")
                    cooldown_left = await self._get_withdraw_cooldown_left_locked(conn , user_id=uid)

                dt = time.perf_counter() - t0
                print(
                    f"[ВЫВОД][DEBUG] OK rid={rid} new_bal={new_bal} used={used_after} "
                    f"remaining={remaining_after} cooldown_set={cooldown_set} left={cooldown_left} dt={dt:.4f}s")

                return {"ok": True , "request_id": rid , "user_balance_after": int(new_bal) ,
                    "daily_limit": int(daily_limit) , "used": int(used_after) , "remaining": int(remaining_after) ,
                    "cooldown_set": bool(cooldown_set) , "cooldown_left": int(cooldown_left) , }















    async def get_price_by_emoji(self, emoji):
        """Получает цену предмета по его эмодзи."""
        query = "SELECT price FROM dex WHERE emoji = $1"

        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query, emoji)

            if result:
                price = result['price']
                print(f"Цена предмета: {price}")
                return price
            else:
                print("Предмет не найден.")
                return None
        except Exception as e:
            print(f"[ERROR] Ошибка при выполнении запроса: {e}")
            return None



    async def get_user_country123(self , user_id):
        """Возвращает страну пользователя по user_id."""
        try:
            query = "SELECT country FROM users WHERE user_id = $1"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , user_id)

            if result:
                return result [ 'country' ]  # Извлекаем страну из результата
            return None  # Если пользователя нет в базе, возвращаем None

        except Exception as e:
            print(f"Ошибка при получении страны для пользователя {user_id}: {e}")
            return None

    async def get_referrals(self, user_id):
        """Возвращает количество рефералов для указанного user_id."""
        try:
            query = "SELECT refferals FROM users WHERE user_id = $1"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query, user_id)

            # Если результат найден, возвращаем количество рефералов
            if result:
                return result['refferals']
            return 0  # Если пользователь не найден, возвращаем 0

        except Exception as e:
            print(f"Ошибка при получении рефералов для пользователя {user_id}: {e}")
            return 0

    async def get_all_chat_ids(self):
        """Получает все chat_id из таблицы chat."""
        try:
            query = "SELECT chat_id FROM chat"
            async with self.pool.acquire() as connection:
                result = await connection.fetch(query)

            # Возвращаем все chat_id в виде списка
            return [row['chat_id'] for row in result]

        except Exception as e:
            print(f"Ошибка при получении chat_id: {e}")
            return []

    async def get_total_balance1(self):
        """Возвращает общую сумму балансов пользователей."""
        try:
            query = "SELECT SUM(balance) FROM users"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query)

            # Получаем сумму балансов (если результат None, возвращаем 0)
            total_balance = result [ 0 ] if result [ 0 ] else 0
            return total_balance

        except Exception as e:
            print(f"Ошибка при выполнении запроса: {e}")
            return 0

    async def get_total_chat_balance(self):
        """Возвращает общую сумму балансов чатов."""
        try:
            query = "SELECT SUM(chatbalance) FROM chat"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query)

            # Получаем сумму балансов (если результат None, возвращаем 0)
            total_chat_balance = result [ 0 ] if result [ 0 ] else 0
            return total_chat_balance

        except Exception as e:
            print(f"Ошибка при выполнении запроса: {e}")
            return 0

    async def get_total_dex_balance(self):
        """Возвращает общую сумму dexbalance из таблицы chat."""
        try:
            query = "SELECT SUM(dexbalance) FROM chat"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query)

            # Получаем сумму балансов (если результат None, возвращаем 0)
            total_dex_balance = result [ 0 ] if result [ 0 ] else 0
            return total_dex_balance

        except Exception as e:
            print(f"Ошибка при выполнении запроса: {e}")
            return 0

    async def sync_balance_cache_from_db(self , user_id: int , * , debug: bool = False , ) -> Optional [
        Dict [ str , Any ] ]:
        """
        ✅ ОБЯЗАТЕЛЬНЫЙ кэш = ЛОКАЛЬНЫЙ user_cache_balance (без Redis).
        Истина = БД.

        Что делает:
          1) Читает баланс из БД: users.balance WHERE user_id=$1
          2) Берёт баланс из user_cache_balance[uid] (обязательный кэш)
          3) Если ключа в кэше нет -> записывает DB в кэш
          4) Если ключ есть:
             - совпало -> NOOP
             - не совпало -> перезаписывает кэш значением из DB

        В debug ты видишь:
          - db_balance
          - local_before (было в кэше)
          - match True/False
          - action noop / inserted / updated
          - local_after (что стало)
        """
        import asyncio
        import time

        t0 = time.perf_counter()

        # ---- окружение ----
        if not getattr(self , "pool" , None):
            if debug:
                print("🧊[SYNC][ABORT] asyncpg pool не инициализирован")
            return None

        try:
            uid = int(user_id)
        except Exception as e:
            if debug:
                print(f"🧊[SYNC][ABORT] user_id не int: {e!r}")
            return None

        # ---- ленивые сторы в процессе (как у тебя) ----
        g = globals()
        if "_user_balance_locks" not in g or not isinstance(g.get("_user_balance_locks") , dict):
            g [ "_user_balance_locks" ] = {}
            if debug:
                print("🧵[SYNC][LOCAL-LOCKS] Инициализирован _user_balance_locks")

        if "user_cache_balance" not in g or not isinstance(g.get("user_cache_balance") , dict):
            g [ "user_cache_balance" ] = {}
            if debug:
                print("📦[SYNC][CACHE][LOCAL] Инициализирован user_cache_balance")

        _user_balance_locks = g [ "_user_balance_locks" ]  # uid -> asyncio.Lock
        user_cache_balance = g [ "user_cache_balance" ]  # uid -> int

        async def _read_db_balance() -> int:
            async with self.pool.acquire() as conn:
                v = await conn.fetchval("SELECT balance FROM users WHERE user_id=$1" , uid)
            if v is None:
                return 0
            try:
                return int(v)
            except Exception:
                return int(float(v))

        def _read_local() -> Optional [ int ]:
            try:
                if uid in user_cache_balance:
                    return int(user_cache_balance.get(uid))
            except Exception:
                return None
            return None

        if debug:
            print("────────────────────────────────────────────")
            print(f"🧊[SYNC][START] uid={uid} cache=LOCAL(user_cache_balance)")

        # читаем local ДО (без await)
        local_before = _read_local()

        # читаем DB
        try:
            t_db = time.perf_counter()
            db_val = await _read_db_balance()
            dt_db = time.perf_counter() - t_db
        except Exception as e:
            if debug:
                print(f"🧊[SYNC][DB][ERR] uid={uid}: {e!r}")
            return None

        # сравнение: DB vs LOCAL
        has_local = (local_before is not None)
        match = (has_local and int(local_before) == int(db_val))

        if debug:
            print(f"🧊[SYNC][VALUES] DB(users.balance)  = {int(db_val)}")
            print(f"📦[SYNC][VALUES] LOCAL(cache)      = {local_before}")
            print(f"✅[SYNC][MATCH] local==db ? {match} (db={int(db_val)}, local={local_before})")
            print(f"⏱️[SYNC][DB-TIME] {dt_db:.4f}s")

        # NOOP - если совпало
        if match:
            if debug:
                print("✅[SYNC][NOOP] LOCAL уже равен БД -> ничего не делаем")
                print(f"🧊[SYNC][END] dt_all={(time.perf_counter() - t0):.4f}s")
                print("────────────────────────────────────────────")
            return {"ok": True , "uid": uid , "action": "noop" , "db_balance": int(db_val) ,
                "local_before": int(local_before) , "local_after": int(local_before) , "match": True ,
                "dt": round(time.perf_counter() - t0 , 6) , }

        # иначе - берём лок и записываем
        local_lock = _user_balance_locks.get(uid)
        if local_lock is None:
            local_lock = asyncio.Lock()
            _user_balance_locks [ uid ] = local_lock
            if debug:
                print(f"🧵[SYNC][LOCAL-LOCK] создан для uid={uid}")

        async with local_lock:
            if debug:
                print(f"🧵[SYNC][LOCAL-LOCK] захвачен uid={uid}")

            # перепроверка DB внутри лока (как highload-паттерн)
            db_val_locked = await _read_db_balance()

            # перепроверка local внутри лока (на всякий)
            local_before2 = _read_local()
            match2 = (local_before2 is not None and int(local_before2) == int(db_val_locked))

            if debug:
                print("🧾[SYNC][BEFORE-WRITE]")
                print(f"   DB    = {int(db_val_locked)}")
                print(f"   LOCAL = {local_before2}")
                print(f"   Match = {match2}")

            if match2:
                if debug:
                    print("✅[SYNC][NOOP-LOCKED] Пока ждали лок - LOCAL уже стал равен БД")
                    print(f"🧊[SYNC][END] dt_all={(time.perf_counter() - t0):.4f}s")
                    print("────────────────────────────────────────────")
                return {"ok": True , "uid": uid , "action": "noop_locked" , "db_balance": int(db_val_locked) ,
                    "local_before": None if local_before2 is None else int(local_before2) ,
                    "local_after": None if local_before2 is None else int(local_before2) , "match": True ,
                    "dt": round(time.perf_counter() - t0 , 6) , }

            # действие: вставка если ключа не было, иначе апдейт
            action = "inserted" if local_before2 is None else "updated"

            user_cache_balance [ uid ] = int(db_val_locked)
            _balance_fresh_at [ uid ] = time.monotonic()

            local_after = _read_local()
            match_after = (local_after is not None and int(local_after) == int(db_val_locked))

            if debug:
                print(f"📦[SYNC][WRITE] action={action} user_cache_balance[{uid}]={int(db_val_locked)}")
                print("🧾[SYNC][AFTER-WRITE]")
                print(f"   DB        = {int(db_val_locked)}")
                print(f"   LOCAL     = {local_after}")
                print(f"   MatchAfter= {match_after}")
                print(f"🧊[SYNC][END] dt_all={(time.perf_counter() - t0):.4f}s")
                print("────────────────────────────────────────────")

            return {"ok": True , "uid": uid , "action": action , "db_balance": int(db_val_locked) ,
                "local_before": None if local_before2 is None else int(local_before2) ,
                "local_after": None if local_after is None else int(local_after) , "match": False ,
                "match_after": bool(match_after) , "dt": round(time.perf_counter() - t0 , 6) , }
    async def update_user_balance(self , user_id , new_balance) -> Optional [ int ]:
        """
        ЕДИНАЯ защищённая функция обновления баланса.

        Режимы:
          • SET   : await update_user_balance(uid, 500)        -> баланс станет ровно 500 (не ниже 0)
          • DELTA : await update_user_balance(uid, "+100")      -> прибавить 100
                     await update_user_balance(uid, "-25")      -> списать 25 (без ухода в минус)

        Защиты/фичи:
          • Меж-инстанс Redis-lock (NX+PX) + безопасный Lua-unlock.
          • Пер-процессный asyncio.Lock на пользователя (узкая критическая секция).
          • Атомарные SQL (UPDATE ... RETURNING / INSERT ... ON CONFLICT ... RETURNING) в транзакции.
          • Write-through кэш: Redis ключ bal:val:{uid} (+ TTL) и локальный user_cache_balance.
          • Pub/Sub оповещение (канал bal:bus) для консистентности воркеров.
          • Безопасный мини-снапшот «только данных» (whitelist) - НИКОГДА не сериализует локи/таски.
          • Подробные русские логи + ретраи с прогрессивным бэкоффом.
        """
        # ---- локальные импорты и настройки (всё внутри одной функции) ----
        import asyncio , time , uuid , json , pickle

        DEBUG = True  # подробные принты
        ALLOW_NEGATIVE = False  # запрет отрицательного баланса
        RETRIES = 3  # число повторов при временных ошибках
        BACKOFF_BASE = 0.05  # 50/100/150 мс
        LOCK_TTL_MS = 8000  # TTL меж-инстанс Redis-лока
        TRY_LOCK_SEC = 1.5  # сколько пытаться взять Redis-лок
        VERIFY_WRITE = False  # верифицировать SELECTом после записи (включай на тесте)
        NS_PREFIX = "bal"  # префикс ключей в Redis
        REDIS_CACHE_TTL = 3600  # кэш баланса в Redis
        PUBLISH_UPDATES = True  # pub/sub уведомление о смене баланса
        SNAPSHOT_ON_WRITE = True  # сохранять безопасный снапшот «только данных»
        SNAPSHOT_KEY = "snapshot:globals"
        SNAPSHOT_INCLUDE = ("user_cache_balance" ,)  # что можно снапшотить (без локов!)

        LUA_UNLOCK = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
          return redis.call("DEL", KEYS[1])
        else
          return 0
        end
        """

        t_all = time.perf_counter()
        if DEBUG:
            print(f"💰[UPD][START] user_id={user_id!r}, new_balance={new_balance!r}")

        # ---- окружение ----
        if not getattr(self , "pool" , None):
            if DEBUG: print("💰[UPD][ABORT] asyncpg pool не инициализирован")
            return None
        use_redis = bool(getattr(self , "redis" , None))
        redis = getattr(self , "redis" , None)

        # ---- ленивые сторы в процессе (НЕ сериализуем) ----
        g = globals()
        if "_user_balance_locks" not in g or not isinstance(g.get("_user_balance_locks") , dict):
            g [ "_user_balance_locks" ] = {}
            if DEBUG: print("🧵[LOCAL-LOCKS] Инициализирован словарь _user_balance_locks")
        if "user_cache_balance" not in g or not isinstance(g.get("user_cache_balance") , dict):
            g [ "user_cache_balance" ] = {}
            if DEBUG: print("📦[CACHE][LOCAL] Инициализирован словарь user_cache_balance")

        _user_balance_locks = g [ "_user_balance_locks" ]  # uid -> asyncio.Lock()
        user_cache_balance = g [ "user_cache_balance" ]  # uid -> int

        # ---- маленькие хелперы ----
        def _is_picklable(obj) -> bool:
            try:
                pickle.dumps(obj , protocol=pickle.HIGHEST_PROTOCOL)
                return True
            except Exception:
                return False

        def _build_safe_snapshot(mapping: dict , allow_keys: tuple) -> dict:
            safe = {}
            for k in allow_keys:
                if k in mapping:
                    v = mapping [ k ]
                    try:
                        if _is_picklable(v):
                            safe [ k ] = v
                        elif isinstance(v , dict):
                            sub = {}
                            for sk , sv in v.items():
                                if _is_picklable(sv):
                                    sub [ sk ] = sv
                            safe [ k ] = sub
                    except Exception:
                        pass
            return safe

        async def _save_snapshot_safely() -> None:
            if not (SNAPSHOT_ON_WRITE and use_redis):
                return
            try:
                safe = _build_safe_snapshot(globals() , SNAPSHOT_INCLUDE)
                payload = pickle.dumps(safe , protocol=pickle.HIGHEST_PROTOCOL)
                for attempt in range(1 , 3 + 1):
                    try:
                        await redis.set(SNAPSHOT_KEY , payload)
                        if DEBUG: print(f"✅ [SNAPSHOT][SAVE] key={SNAPSHOT_KEY}, size={len(payload)}")
                        break
                    except Exception as e:
                        if attempt >= 3:
                            if DEBUG: print(f"🟠 [SNAPSHOT][SKIP] Redis SET не удался: {e!r}")
                            break
                        await asyncio.sleep(0.05 * attempt)
            except Exception as e:
                if DEBUG: print(f"🟠 [SNAPSHOT][SKIP] сбор/сериализация не удались: {e!r}")

        # ---- нормализация входа ----
        t_norm = time.perf_counter()
        try:
            uid = int(user_id)
        except Exception as e:
            if DEBUG: print(f"💰[UPD][ABORT] user_id не int: {e!r}")
            return None

        is_delta , delta , target = False , None , None
        try:
            if isinstance(new_balance , str):
                s = new_balance.strip().replace(" " , "")
                if s.startswith(("+" , "-")):
                    is_delta = True
                    delta = int(s) if s.lstrip("+-").isdigit() else int(float(s))
                else:
                    target = int(float(s))
            else:
                target = int(new_balance)
        except Exception as e:
            if DEBUG: print(f"💰[UPD][ABORT] неверный new_balance: {e!r}")
            return None

        if DEBUG:
            print(
                f"💰[UPD][PARSED] uid={uid}, mode={'DELTA' if is_delta else 'SET'}, "
                f"value={delta if is_delta else target}, dt={(time.perf_counter() - t_norm):.4f}s")

        # ---- Redis-lock (меж инстансами, best-effort) ----
        lock_token = None
        lock_key = f"{NS_PREFIX}:lock:{uid}"
        got_lock = False
        if use_redis:
            t_lock = time.perf_counter()
            lock_token = f"{uuid.uuid4()}:{time.time()}"
            deadline = time.monotonic() + TRY_LOCK_SEC
            while time.monotonic() < deadline and not got_lock:
                try:
                    got_lock = await redis.set(lock_key , lock_token , nx=True , px=LOCK_TTL_MS)
                    if got_lock:
                        if DEBUG:
                            print(
                                f"🔐[LOCK][OK] key={lock_key}, ttl={LOCK_TTL_MS}ms, "
                                f"dt={(time.perf_counter() - t_lock):.4f}s")
                        break
                except Exception as e:
                    if DEBUG: print(f"🔐[LOCK][ERR] redis.set NX PX: {e!r}")
                    break
                await asyncio.sleep(0.02)
            if not got_lock and DEBUG:
                print(f"🔐[LOCK][SKIP] не взяли redis-lock за {TRY_LOCK_SEC}s - продолжим под локальным lock")

        # ---- лок процесса (пер-пользовательский) ----
        local_lock = _user_balance_locks.get(uid)
        if local_lock is None:
            local_lock = asyncio.Lock()
            _user_balance_locks [ uid ] = local_lock
            if DEBUG: print(f"🧵[LOCAL-LOCK] создан для uid={uid}")

        # ---- журнал операции (best-effort) ----
        op_key = None
        if use_redis:
            try:
                op_id = str(uuid.uuid4())
                op_key = f"{NS_PREFIX}:op:{uid}:{op_id}"
                await redis.hset(
                    op_key , mapping={"state": "PENDING" , "mode": "DELTA" if is_delta else "SET" ,
                        "amount": str(delta if is_delta else target) ,
                        "allow_negative": "1" if ALLOW_NEGATIVE else "0" , "user_id": str(uid) ,
                        "ts": str(time.time()) , })
                await redis.expire(op_key , 86400)
                if DEBUG: print(f"📝[JOURNAL][PENDING] {op_key}")
            except Exception as e:
                if DEBUG: print(f"📝[JOURNAL][WARN] не удалось записать PENDING: {e!r}")
                op_key = None

        # ---- основная логика с ретраями ----
        try:
            async with local_lock:
                if DEBUG: print(f"🧵[LOCAL-LOCK] захвачен uid={uid}")

                for attempt in range(1 , RETRIES + 1):
                    t_try = time.perf_counter()
                    try:
                        if DEBUG: print(f"⚙️[TRY {attempt}/{RETRIES}] BEGIN транзакции")
                        async with self.pool.acquire() as conn:
                            async with conn.transaction():
                                # журнал -> COMMITTING
                                if use_redis and op_key:
                                    try:
                                        await redis.hset(op_key , "state" , "COMMITTING")
                                        if DEBUG: print(f"📝[JOURNAL][COMMITTING] {op_key}")
                                    except Exception as e:
                                        if DEBUG: print(f"📝[JOURNAL][WARN] COMMITTING не записан: {e!r}")

                                if is_delta:
                                    # Δ-режим - строго без ухода в минус (если не ALLOW_NEGATIVE)
                                    if DEBUG:
                                        print(
                                            f"🧮[SQL][DELTA] uid={uid}, delta={delta}, allow_negative={ALLOW_NEGATIVE}")
                                    row = await conn.fetchrow(
                                        """
                                        UPDATE users
                                           SET balance = balance + $2
                                         WHERE user_id = $1
                                           AND ($3::boolean OR (balance + $2) >= 0)
                                        RETURNING balance
                                        """ , uid , int(delta) , bool(ALLOW_NEGATIVE))
                                    if row is None:
                                        if int(delta) < 0 and not ALLOW_NEGATIVE:
                                            if DEBUG:
                                                print(f"⛔[SQL][DELTA] уход в минус запрещён uid={uid}, delta={delta}")
                                            return None
                                        if DEBUG:
                                            print(f"🧮[SQL][DELTA->INSERT] uid={uid}, delta={delta}")
                                        row = await conn.fetchrow(
                                            """
                                            INSERT INTO users (user_id, balance)
                                            VALUES ($1, $2)
                                            ON CONFLICT (user_id)
                                            DO UPDATE SET balance = users.balance + EXCLUDED.balance
                                            RETURNING balance
                                            """ , uid , int(delta) if ALLOW_NEGATIVE else max(0 , int(delta)))
                                    if not row:
                                        if DEBUG: print(f"❓[SQL][DELTA] RETURNING пустой uid={uid}")
                                        return None
                                    new_val = int(row [ "balance" ])
                                    if DEBUG: print(f"✅[SQL][DELTA] RETURNING balance={new_val}")

                                else:
                                    # SET-режим (жёсткая установка, не ниже нуля)
                                    tgt = int(target)
                                    if not ALLOW_NEGATIVE and tgt < 0:
                                        if DEBUG:
                                            print(f"⛔[SQL][SET] отрицательное значение запрещено uid={uid}, tgt={tgt}")
                                        return None
                                    if DEBUG:
                                        print(f"🧮[SQL][SET] uid={uid}, target={tgt}, allow_negative={ALLOW_NEGATIVE}")
                                    row = await conn.fetchrow(
                                        """
                                        UPDATE users
                                           SET balance = $2
                                         WHERE user_id = $1
                                           AND ($3::boolean OR $2 >= 0)
                                        RETURNING balance
                                        """ , uid , tgt , bool(ALLOW_NEGATIVE))
                                    if row is None:
                                        if DEBUG:
                                            print(f"🧮[SQL][SET->INSERT] uid={uid}, target={tgt}")
                                        row = await conn.fetchrow(
                                            """
                                            INSERT INTO users (user_id, balance)
                                            VALUES ($1, $2)
                                            ON CONFLICT (user_id) DO UPDATE SET balance = EXCLUDED.balance
                                            RETURNING balance
                                            """ , uid , tgt if ALLOW_NEGATIVE else max(0 , tgt))
                                    if not row:
                                        if DEBUG: print(f"❓[SQL][SET] RETURNING пустой uid={uid}")
                                        return None
                                    new_val = int(row [ "balance" ])
                                    if DEBUG: print(f"✅[SQL][SET] RETURNING balance={new_val}")

                        # ---- write-through кэш ----
                        if use_redis:
                            try:
                                await redis.set(f"{NS_PREFIX}:val:{uid}" , str(new_val) , ex=REDIS_CACHE_TTL)
                                if DEBUG:
                                    print(f"📦[CACHE][REDIS] {NS_PREFIX}:val:{uid} = {new_val} (ttl={REDIS_CACHE_TTL}s)")
                                if PUBLISH_UPDATES:
                                    msg = json.dumps({"uid": uid , "balance": new_val , "ts": time.time()})
                                    await redis.publish(f"{NS_PREFIX}:bus" , msg)
                                    if DEBUG:
                                        print(f"📣[CACHE][PUB] {NS_PREFIX}:bus <- {msg}")
                            except Exception as e:
                                if DEBUG: print(f"📦[CACHE][REDIS][WARN] set/publish: {e!r}")

                        try:
                            user_cache_balance [ uid ] = new_val
                            _balance_fresh_at [ uid ] = time.monotonic()
                            if DEBUG:
                                print(f"📦[CACHE][LOCAL] user_cache_balance[{uid}] = {new_val}")
                        except Exception as e:
                            if DEBUG: print(f"📦[CACHE][LOCAL][WARN] {e!r}")

                        if VERIFY_WRITE:
                            try:
                                async with self.pool.acquire() as conn:
                                    echoed = await conn.fetchval("SELECT balance FROM users WHERE user_id=$1" , uid)
                                if echoed is None or int(echoed) != new_val:
                                    if DEBUG: print(f"🔁[ECHO][MISMATCH] wrote={new_val}, read={echoed}")
                                    return None
                                if DEBUG: print("🔁[ECHO][OK]")
                            except Exception as e:
                                if DEBUG: print(f"🔁[ECHO][ERR] {e!r}")
                                return None

                        if use_redis and op_key:
                            try:
                                await redis.hset(op_key , "state" , "DONE")
                                await redis.expire(op_key , 86400)
                                if DEBUG: print(f"📝[JOURNAL][DONE] {op_key}")
                            except Exception as e:
                                if DEBUG: print(f"📝[JOURNAL][WARN] DONE не записан: {e!r}")

                        if DEBUG:
                            print(
                                f"🎉[UPD][OK] uid={uid}, new_balance={new_val}, "
                                f"attempt={attempt}, dt_try={(time.perf_counter() - t_try):.4f}s, "
                                f"dt_all={(time.perf_counter() - t_all):.4f}s")

                        # безопасный снапшот «только данных»
                        await _save_snapshot_safely()

                        return new_val

                    except Exception as e:
                        if DEBUG:
                            print(
                                f"⚠️[TRY {attempt}/{RETRIES}][ERR] uid={uid}, err={e!r}, "
                                f"dt_try={(time.perf_counter() - t_try):.4f}s")
                        if attempt >= RETRIES:
                            if DEBUG: print(f"💥[UPD][FAIL] uid={uid}, после {RETRIES} попыток")
                            return None
                        await asyncio.sleep(BACKOFF_BASE * attempt)

        finally:
            # безопасный unlock (если брали redis-lock)
            if use_redis and lock_token:
                try:
                    await redis.eval(LUA_UNLOCK , 1 , lock_key , lock_token)
                    if DEBUG: print(f"🔓[LOCK][UNLOCKED] key={lock_key}")
                except Exception as e:
                    if DEBUG: print(f"🔓[LOCK][WARN] unlock: {e!r}")

            if DEBUG:
                print(f"💰[UPD][END] uid={user_id}, dt_all={(time.perf_counter() - t_all):.4f}s")
















































    async def get_refferer_id(self , user_id):
        """Получает refferer_id для пользователя из таблицы users."""
        try:
            # Выполняем запрос с параметром user_id
            query = "SELECT refferer_id FROM users WHERE user_id = $1"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , user_id)

            # Если результат найден, возвращаем refferer_id, иначе None
            return result [ 'refferer_id' ] if result else None
        except Exception as e:
            print(f"Ошибка при получении refferer_id для пользователя {user_id}: {e}")
            return None

    async def get_user_by_idgive(self, user_id):
        """Получение данных о пользователе по user_id."""
        try:
            # Выполняем запрос с параметром user_id
            query = "SELECT * FROM users WHERE user_id = $1"
            async with self.pool.acquire() as connection:
                user_data = await connection.fetchrow(query, user_id)

            # Возвращаем данные о пользователе, если они найдены, иначе None
            return user_data if user_data else None
        except Exception as e:
            print(f"Ошибка при получении данных о пользователе с ID {user_id}: {e}")
            return None

    async def get_user_id_by_username(self , username):
        """Получить ID пользователя по юзернейму, игнорируя регистр."""
        try:
            # Выполняем запрос для получения user_id по username с учетом регистра
            query = "SELECT user_id FROM users WHERE LOWER(username) = LOWER($1)"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , username)

            # Проверяем, есть ли результат и возвращаем user_id
            if result:
                return result [ 'user_id' ]
            return None
        except Exception as e:
            print(f"Ошибка при получении user_id для пользователя {username}: {e}")
            return None

    async def get_user_id_by_first_name(self , first_name):
        """Получить user_id пользователей по имени из столбца first_name, без учета регистра."""
        try:
            query = "SELECT user_id, first_name FROM users WHERE first_name ILIKE $1"

            async with self.pool.acquire() as connection:
                result = await connection.fetch(query , first_name)

            if result:
                # Создаем словарь с user_id как ключами и first_name как значениями
                users_dict = {user [ 'user_id' ]: user [ 'first_name' ] for user in result}
                return users_dict
            else:
                return {}

        except Exception as e:
            print(f"Ошибка при получении user_id для пользователя {first_name}: {e}")
            return None

    async def get_all_user_ids(self):
        """Возвращает список всех user_id из таблицы users."""
        try:
            query = "SELECT user_id FROM users"
            async with self.pool.acquire() as connection:
                # Выполняем запрос и получаем все строки
                result = await connection.fetch(query)

            # Извлекаем user_id из списка строк
            return [ row [ 'user_id' ] for row in result ]
        except Exception as e:
            print(f"Ошибка при получении всех user_id: {e}")
            return [ ]

    async def get_user_country(self , user_id):
        """
        Получение страны пользователя по его ID.
        """
        query = "SELECT country FROM users WHERE user_id = $1"
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow(query , user_id)  # Выполняем запрос

            # Если результат найден, возвращаем значение из столбца "country"
            return result [ 'country' ] if result else None

    async def remove_user_country(self, user_id):
        """
        Удаление информации о стране пользователя, устанавливая значение NULL.
        """
        query = "UPDATE users SET country = NULL WHERE user_id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, user_id)
            print(f"Страна пользователя с ID {user_id} успешно удалена.")

    async def get_firstname_by_user_id(self , user_id):
        """Получение имени пользователя (first_name) по user_id."""
        if not await self.ensure_pool():
            return None

        try:
            query = "SELECT first_name FROM users WHERE user_id = $1"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , user_id)
                return result [ 'first_name' ] if result else None
        except Exception as e:
            print(f"Ошибка при получении имени пользователя: {str(e)}")
            return None

    async def get_names_bulk(self, user_ids):
        """Массово получить (first_name, username) для списка user_id ОДНИМ
        запросом вместо N×2 (get_firstname_by_user_id + get_username_by_user_id
        по одному на юзера). Используется в топ-10-рендерах ("топ", "стата" и т.п.),
        где раньше на каждую команду уходило до 20 последовательных запросов.
        Возвращает {user_id: (first_name, username)}.
        """
        ids = list({int(uid) for uid in user_ids if uid is not None})
        if not ids or not await self.ensure_pool():
            return {}
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    "SELECT user_id, first_name, username FROM users WHERE user_id = ANY($1::bigint[])",
                    ids,
                )
                return {
                    int(row["user_id"]): (row["first_name"], row["username"])
                    for row in rows
                }
        except Exception as e:
            print(f"Ошибка при массовом получении имён: {e}")
            return {}
    async def add_winnings_ruletka(self , user_id , winnings):
        """
        Добавляет выигрыш к балансу пользователя.

        Делегирует в update_user_balance (delta-режим) вместо прямого raw SQL -
        так пишущий путь остаётся ЕДИНЫМ для всех начислений/списаний баланса
        в проекте (защита от гонок, кэш user_cache_balance/Redis всегда актуален).

        :param user_id: ID пользователя.
        :param winnings: Сумма выигрыша.
        :return: True, если операция успешна, иначе False.
        """
        try:
            new_balance = await self.update_user_balance(user_id , f"+{int(winnings)}")
            if new_balance is None:
                print(f"Пользователь с ID {user_id} не найден или начисление не удалось.")
                return False
            print(f"Баланс пользователя {user_id} увеличен на {winnings}. Новый баланс: {new_balance}.")
            return True
        except Exception as e:
            print(f"Ошибка при добавлении выигрыша для пользователя {user_id}: {str(e)}")
            return False

    async def get_user_experience(self , user_id):
        """
        Получает значение опыта пользователя по его ID.

        :param user_id: ID пользователя.
        :return: Значение опыта пользователя или None, если пользователь не найден.
        """
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для получения значения опыта
                query = "SELECT xpp FROM users WHERE user_id = $1"
                result = await connection.fetchrow(query , user_id)

                # Проверяем результат
                if result:
                    return result [ 'xpp' ]  # Возвращаем значение опыта
                return None  # Если пользователь не найден
        except Exception as e:
            print(f"Ошибка при получении опыта пользователя {user_id}: {str(e)}")
            return None

    async def add_xp_to_games(self , user_id):
        """
        Добавляет случайное количество опыта (XP) пользователю, если случайное число > 70.
        :param user_id: ID пользователя.
        :return: Количество добавленного опыта или 0.
        """
        try:
            # Генерируем случайное число от 1 до 100
            random_number = random.randint(1 , 100)

            # Если случайное число меньше или равно 70, опыт не добавляется
            if random_number <= 70:
                print("У вас не повезло! Опыт не был добавлен.")
                return 0

            # Генерируем случайное количество XP за игру (от 1 до 5)
            xp = random.randint(1 , 5)

            # Обновляем XP в таблице users
            query = "UPDATE users SET xpp = xpp + $1 WHERE user_id = $2"
            async with self.pool.acquire() as connection:
                await connection.execute(query , xp , user_id)

            print(f"Вы получили {xp} XP за игру!")
            return xp

        except Exception as e:
            print(f"Ошибка при выполнении действия: {str(e)}")
            return 0

    async def get_user_games_history(self , user_id , limit=7 , offset=0):
        """
        Получает историю игр пользователя с указанными ограничениями.
        :param user_id: ID пользователя.
        :param limit: Количество записей для выборки (по умолчанию 7).
        :param offset: Смещение (по умолчанию 0).
        :return: Список записей о играх.
        """
        query = """
        SELECT 
            kube, kubelose, 
            boul, boullose, 
            basket, basketlose, 
            slots, slotslose, 
            trade, tradelose, 
            crash, crashlose, 
            mine, minelose, 
            tank, tanklose, 
            roul, roullose, 
            kazik, kaziklose, 
            lot, lotlose, 
            ball, balllose, 
            knb, knblose, 
            orel, orellose, 
            dart, dartlose, 
            foot, footlose, 
            kosti, kostilose, 
            due, duelose,
            bingo, bingolose,
            rulet, ruletlose,
            reshka, reshkalose,
            risk, risklose,
            plate, platelose,
            bombs, bombslose,
            datetime
        FROM 
            moneykommi
        WHERE 
            user_id = $1
        ORDER BY 
            datetime DESC
        LIMIT $2 OFFSET $3
        """
        async with self.pool.acquire() as connection:
            result = await connection.fetch(query , user_id , limit , offset)
        return result

    async def get_user_games_count(self , user_id):
        """
        Получает количество игр, сыгранных пользователем.
        :param user_id: ID пользователя.
        :return: Количество игр, сыгранных пользователем.
        """
        query = "SELECT COUNT(*) FROM moneykommi WHERE user_id = $1"
        async with self.pool.acquire() as connection:
            result = await connection.fetchval(query , user_id)
        return result

    async def add_transaction(self , user_id , user_id2 , money):
        """
        Добавляет запись о транзакции в таблицу moneyhistory.
        :param user_id: ID первого пользователя.
        :param user_id2: ID второго пользователя.
        :param money: Количество денег в транзакции.
        """
        # Get the current time as a datetime object
        timestamp = datetime.now()

        # Remove microseconds by replacing them with zero
        timestamp_without_microseconds = timestamp.replace(microsecond=0)

        # Print the timestamp without microseconds for debugging
        formatted_timestamp = timestamp_without_microseconds.strftime("%Y-%m-%d %H:%M:%S")
        print(f'{formatted_timestamp} : ' , timestamp_without_microseconds)  # Log for debugging

        # Now use the timestamp without microseconds for the query
        query = """
        INSERT INTO moneyhistory (user_id, user_id2, money, data)
        VALUES ($1, $2, $3, $4)
        """

        async with self.pool.acquire() as connection:
            # Pass the timestamp without microseconds to the query
            await connection.execute(query , user_id , user_id2 , money , timestamp_without_microseconds)



    async def get_transaction_history(self , user_id , limit=10 , offset=0):
        """
        Получает историю транзакций пользователя.
        :param user_id: ID пользователя, для которого нужно получить историю.
        :param limit: Количество записей для выборки.
        :param offset: Смещение для выборки.
        """
        query = """
        SELECT user_id, user_id2, money, data
        FROM moneyhistory
        WHERE user_id = $1 OR user_id2 = $1
        ORDER BY data DESC
        LIMIT $2 OFFSET $3
        """

        async with self.pool.acquire() as connection:
            rows = await connection.fetch(query , user_id , limit , offset)
            return rows  # Возвращаем список строк с транзакциями

    async def get_transaction_count(self , user_id):
        """
        Получает количество транзакций пользователя.
        :param user_id: ID пользователя, для которого нужно получить количество транзакций.
        """
        query = """
        SELECT COUNT(*)
        FROM moneyhistory
        WHERE user_id = $1 OR user_id2 = $1
        """

        async with self.pool.acquire() as connection:
            result = await connection.fetchrow(query , user_id)
            return result [ 'count' ]  # Возвращаем количество транзакций

    # ─────────────────────────────────────────────────────────────────────
    # Начиная отсюда - функции для отдельных игр (bingo/orel/knb/kosti).
    # На момент ревью 2026-07 ни одна из них не вызывается нигде в проекте
    # (проверено по всем call site'ам, включая динамический getattr(db, name)
    # диспетчинг) - оставлены как готовый API на случай, если игра снова будет
    # подключена. Все переведены на update_user_balance (delta-режим) вместо
    # прямого raw SQL, чтобы у ЛЮБОГО пишущего пути в проекте была одна и та
    # же защита от гонок/ухода в минус и одинаковое обновление кэша баланса.
    # ─────────────────────────────────────────────────────────────────────
    async def increment_user_balance_bingo(self , user_id , amount):
        """
        Увеличивает баланс пользователя на указанную сумму.
        :param user_id: ID пользователя, чей баланс нужно увеличить.
        :param amount: Сумма, на которую нужно увеличить баланс.
        :return: Новый баланс пользователя после изменения.
        """
        return await self.update_user_balance(user_id , f"+{int(amount)}")

    async def deduct_balance_bingo(self , user_id , amount):
        """
        Уменьшает баланс пользователя на указанную сумму.
        :param user_id: ID пользователя, чей баланс нужно уменьшить.
        :param amount: Сумма, на которую нужно уменьшить баланс.
        :return: Кортеж из флага успешности операции и нового баланса (или старого, если операция не удалась).
        """
        current_balance = await self.get_user_balance(user_id)
        new_balance = await self.update_user_balance(user_id , f"-{int(amount)}")
        if new_balance is None:
            return False , current_balance
        return True , new_balance

    async def deduct_balance_orel(self , user_id , amount):
        """
        Уменьшает баланс пользователя на указанную сумму.
        :param user_id: ID пользователя, чей баланс нужно уменьшить.
        :param amount: Сумма, на которую нужно уменьшить баланс.
        :return: Флаг успешности операции (True/False).
        """
        new_balance = await self.update_user_balance(user_id , f"-{int(amount)}")
        return new_balance is not None

    async def add_balance_orel(self , user_id , amount):
        """
        Увеличивает баланс пользователя на указанную сумму.
        :param user_id: ID пользователя, чей баланс нужно увеличить.
        :param amount: Сумма, на которую нужно увеличить баланс.
        :return: Флаг успешности операции (True/False).
        """
        new_balance = await self.update_user_balance(user_id , f"+{int(amount)}")
        return new_balance is not None

    async def deduct_balance_knb(self , user_id , amount):
        """
        Уменьшает баланс пользователя на указанную сумму.
        :param user_id: ID пользователя, чей баланс нужно уменьшить.
        :param amount: Сумма, на которую нужно уменьшить баланс.
        :return: Кортеж (True/False, новый баланс).
        """
        current_balance = await self.get_user_balance(user_id)
        new_balance = await self.update_user_balance(user_id , f"-{int(amount)}")
        if new_balance is None:
            return False , current_balance
        return True , new_balance

    async def add_balance_knb(self , user_id , amount):
        """
        Увеличивает баланс пользователя на указанную сумму.
        :param user_id: ID пользователя, чей баланс нужно увеличить.
        :param amount: Сумма, на которую нужно увеличить баланс.
        :return: True, если операция прошла успешно, иначе False.
        """
        new_balance = await self.update_user_balance(user_id , f"+{int(amount)}")
        return new_balance is not None

    async def deduct_balance_kosti(self , user_id , amount):
        """
        Уменьшает баланс пользователя на указанную сумму.
        :param user_id: ID пользователя, чей баланс нужно уменьшить.
        :param amount: Сумма, на которую нужно уменьшить баланс.
        :return: True, если операция прошла успешно, иначе False.
        """
        new_balance = await self.update_user_balance(user_id , f"-{int(amount)}")
        return new_balance is not None

    async def add_balance_kosti(self, user_id, amount, bet):
        """Обновляем баланс пользователя после игры с костями (net = amount - bet)."""
        net = int(amount) - int(bet)
        sign = "+" if net >= 0 else "-"
        new_balance = await self.update_user_balance(user_id, f"{sign}{abs(net)}")
        return new_balance is not None

    async def get_user_assets(self , user_id):
        try:
            # Используем пул подключений для асинхронного выполнения запроса
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT im1, house1, gelicopter FROM users WHERE user_id = $1" , user_id)

                if result:
                    print(f"Данные пользователя: {result}")  # Отладочное сообщение
                    im1 , house1 , gelicopter = result
                    assets = {'🏡 Дома': house1 , '🏎 Машины': im1 , '🚁 Вертолеты': gelicopter}
                    # Убираем пустые значения и форматируем данные
                    return {key: '\n'.join(value.split(', ')) for key , value in assets.items() if value}
                return {}
        except Exception as e:
            print(f"Ошибка при получении активов пользователя: {e}")
            return {}

    async def find_referer_name(self, user_id):
        try:
            # Получаем refferer_id пользователя по его user_id
            async with self.pool.acquire() as connection:
                referer_id_row = await connection.fetchrow("SELECT refferer_id FROM users WHERE user_id = $1", user_id)

            # Проверяем, найден ли refferer_id
            if referer_id_row is None:
                return None

            referer_id = referer_id_row['refferer_id']

            # Получаем имя пользователя, который является реферером
            async with self.pool.acquire() as connection:
                referer_name_row = await connection.fetchrow("SELECT first_name FROM users WHERE user_id = $1", referer_id)

            # Проверяем, найдено ли имя
            if referer_name_row is None:
                return None

            referer_name = referer_name_row['first_name']

            return referer_name
        except Exception as e:
            print("Ошибка при получении имени реферера:", e)
            return None

    async def find_referer(self, user_id):
        try:
            # Получаем refferer_id пользователя по его user_id
            async with self.pool.acquire() as connection:
                referer_id_row = await connection.fetchrow("SELECT refferer_id FROM users WHERE user_id = $1", user_id)

            # Проверяем, найден ли refferer_id
            if referer_id_row is None:
                return None

            referer_id = referer_id_row['refferer_id']

            return referer_id
        except Exception as e:
            print("Ошибка при получении refferer_id:", e)
            return None

    async def get_country_emoji_by_user_id(self, user_id):
        try:
            # Получаем страну (emoji) по user_id
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow("SELECT country FROM users WHERE user_id = $1", user_id)

            # Если результат найден, возвращаем страну (emoji)
            if result:
                return result['country']
            return None
        except Exception as e:
            print("Ошибка при получении country по user_id:", e)
            return None

    async def update_user_country(self, user_id, country_emoji):
        try:
            # Обновляем страну пользователя в базе данных
            async with self.pool.acquire() as connection:
                await connection.execute('''UPDATE users SET country = $1 WHERE user_id = $2''', country_emoji, user_id)
            print(f"Страна пользователя с ID {user_id} обновлена на {country_emoji}")
        except Exception as e:
            print("Ошибка при обновлении страны пользователя:", e)






    async def get_registration_date(self, user_id):
        if not await self.ensure_pool():
            return None
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT data FROM users WHERE user_id = $1", user_id
                )
            if result:
                return result["data"]
            return None
        except Exception as e:
            print("Ошибка при получении даты регистрации:", e)
            return None




    async def remove_vip_status(self, user_id):
        try:
            # Удаляем VIP статус пользователя
            async with self.pool.acquire() as connection:
                await connection.execute('UPDATE users SET vip = 0 WHERE user_id = $1', user_id)
            print(f"VIP статус пользователя с ID {user_id} удалён.")
        except Exception as e:
            print("Ошибка при удалении VIP статуса:", e)

    async def remove_user_reward_by_number(self, user_id, reward_number):
        try:
            # Получаем все награды пользователя
            async with self.pool.acquire() as connection:
                rewards = await connection.fetch('SELECT reward FROM reward WHERE user_id = $1', user_id)

            if reward_number <= len(rewards):
                reward_to_remove = rewards[reward_number - 1]['reward']

                # Удаляем указанную награду
                async with self.pool.acquire() as connection:
                    await connection.execute('DELETE FROM reward WHERE user_id = $1 AND reward = $2', user_id, reward_to_remove)

                print(f"Награда {reward_to_remove} была удалена.")
                return reward_to_remove

            return None
        except Exception as e:
            print("Ошибка при удалении награды:", e)
            return None

    async def get_user_rewards(self , user_id):
        try:
            # Получаем до 20 наград пользователя
            async with self.pool.acquire() as connection:
                rewards = await connection.fetch('SELECT reward FROM reward WHERE user_id = $1 LIMIT 20' , user_id)

            # Возвращаем список наград
            return [ reward [ 'reward' ] for reward in rewards ]
        except Exception as e:
            print(f"Ошибка при получении наград: {e}")
            return [ ]

    async def check_vip_status(self, user_id):
        # Проверяем статус VIP пользователя
        vip_status = await self.get_vip_status(user_id)
        return vip_status

    async def get_vip_status(self , user_id):
        try:
            # Получаем статус VIP для пользователя
            async with self.pool.acquire() as connection:
                result = await connection.fetchval('SELECT vip FROM users WHERE user_id = $1' , user_id)

            # Если результат найден, преобразуем в булево значение
            if result is not None:
                return bool(result)  # Преобразуем 0 в False, 1 в True
            return False  # Если пользователя нет в базе, считаем, что VIP статуса нет
        except Exception as e:
            print(f"Ошибка при получении статуса VIP: {e}")
            return False





    async def update_vip_status(self, user_id, status):
        try:
            # Обновляем статус VIP для пользователя
            async with self.pool.acquire() as connection:
                await connection.execute('UPDATE users SET vip = $1 WHERE user_id = $2', status, user_id)
            print(f"Статус VIP для пользователя {user_id} обновлен на {status}")
        except Exception as e:
            print(f"Ошибка при обновлении статуса VIP для пользователя {user_id}: {e}")


    async def get_user_info(self, user_id):
        try:
            # Получаем имя и юзернейм пользователя по user_id
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow('SELECT first_name, username FROM users WHERE user_id = $1', user_id)
                if result:
                    return result['first_name'], result['username']
                return None, None  # Возвращаем None, если пользователь не найден
        except Exception as e:
            print(f"Ошибка при получении информации о пользователе {user_id}: {e}")
            return None, None

    async def check_reward_exists(self, recipient_user_id, reward_text):
        try:
            # Проверяем, существует ли награда для указанного пользователя
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow('SELECT * FROM reward WHERE user_id = $1 AND reward = $2', recipient_user_id, reward_text)
                return result is not None  # Возвращаем True, если награда найдена, иначе False
        except Exception as e:
            print(f"Ошибка при проверке награды для пользователя {recipient_user_id}: {e}")
            return False

    async def add_reward(self, recipient_user_id, sender_user_id, reward_text):
        try:
            # Проверяем, есть ли у пользователя уже 20 наград
            async with self.pool.acquire() as connection:
                num_rewards = await connection.fetchval('SELECT COUNT(*) FROM reward WHERE user_id = $1', recipient_user_id)
                if num_rewards >= 20:
                    return False  # Если у пользователя уже 20 наград, возвращаем False

                # Добавляем награду, если у пользователя меньше 20 наград
                await connection.execute('INSERT INTO reward (user_id, user_id2, reward) VALUES ($1, $2, $3)',
                                         recipient_user_id, sender_user_id, reward_text)
                return True  # Награда успешно добавлена
        except Exception as e:
            print(f"Ошибка при добавлении награды для пользователя {recipient_user_id}: {e}")
            return False

    async def get_total_games_played(self , user_id):
        try:
            # Запрос к базе данных для получения данных об играх
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    "SELECT kube, boul, basket, slots, trade, crash, mine, tank, roul, kazik, lot, ball, knb FROM moneyachiv WHERE user_id = $1" ,
                    user_id)

                if row:
                    # Преобразуем значения в список целых чисел, если они являются числами
                    return [ int(value) if str(value).isdigit() else 0 for value in row ]
                else:
                    return [ ]
        except Exception as e:
            print(f"Ошибка при получении статистики игр для пользователя {user_id}: {e}")
            return [ ]

    async def get_user_achievements(self , user_id):
        try:
            # Асинхронный запрос для получения достижений пользователя
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    "SELECT kube, boul, basket, slots, trade, crash, mine, tank, roul, kazik, lot, ball, knb FROM moneyachiv WHERE user_id = $1" ,
                    user_id)

                if row:
                    return {"kube": row [ "kube" ] , "boul": row [ "boul" ] , "basket": row [ "basket" ] ,
                        "slots": row [ "slots" ] , "trade": row [ "trade" ] , "crash": row [ "crash" ] ,
                        "mine": row [ "mine" ] , "tank": row [ "tank" ] , "roul": row [ "roul" ] ,
                        "kazik": row [ "kazik" ] , "lot": row [ "lot" ] , "ball": row [ "ball" ] , "knb": row [ "knb" ]}
                else:
                    return {}  # Если данные не найдены, возвращаем пустой словарь

        except Exception as e:
            print(f"Ошибка при получении достижений пользователя {user_id}: {e}")
            return {}

    async def update_user_achievements(self, user_id, game_name, achiv):
        for achievement_name, required_count, column_name in achiv:
            # Асинхронно получаем количество игр для достижения
            async with self.pool.acquire() as connection:
                user_games = await connection.fetchval(
                    f"SELECT {column_name} FROM moneyachiv WHERE user_id = $1", user_id
                )

            if user_games and user_games == required_count:
                # Если достижение уже получено, пропускаем
                if await self.check_achievement_obtained(user_id, achievement_name):
                    continue

                # Асинхронно обновляем достижение пользователя
                async with self.pool.acquire() as connection:
                    await connection.execute(
                        "UPDATE moneyachiv SET achiv = $1 WHERE user_id = $2", achievement_name, user_id
                    )

                return achievement_name  # Возвращаем название достижения

        return None  # Если ни одно достижение не было обновлено

    async def check_achievement_obtained(self, user_id, achievement_name):
        """
        Проверка, было ли получено достижение для пользователя.
        :param user_id: ID пользователя
        :param achievement_name: Название достижения
        :return: True если достижение получено, False в противном случае
        """
        async with self.pool.acquire() as connection:
            # Выполняем запрос с параметрами user_id и achievement_name
            count = await connection.fetchval(
                "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1 AND achiv = $2", user_id, achievement_name
            )
            return count > 0  # Если количество больше 0, достижение получено






    async def get_user_info_by_id(self, user_id):
        """
        Получение информации о пользователе по его user_id.
        :param user_id: ID пользователя
        :return: словарь с информацией о пользователе (username и first_name) или None, если не найдено
        """
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow(
                "SELECT username, first_name FROM users WHERE user_id = $1", user_id
            )
            if result:
                return {'username': result['username'], 'first_name': result['first_name']}
            else:
                return None


    async def get_cutecoins_by_user_id(self, user_id):
        """Получение количества CuteCoin для пользователя по его user_id."""
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow(
                "SELECT CuteCoin FROM users WHERE user_id = $1", user_id
            )
            if result:
                return result['CuteCoin']
            return None

    async def get_cutenin_by_user_id(self, user_id):
        """Получение значения cutenin для пользователя по его user_id."""
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow(
                "SELECT cutenin FROM users WHERE user_id = $1", user_id
            )
            if result:
                return result['cutenin']
            return None

    async def subtract_money(self, user_id, amount):
        """
        Вычитаем деньги из баланса пользователя.

        Раньше делал это через raw SQL (UPDATE ... SET balance = balance - $1)
        напрямую, в обход update_user_balance - из-за этого не было защиты от
        ухода в минус, и локальный/Redis-кэш баланса (user_cache_balance)
        оставался устаревшим после списания. Теперь делегируем в единую
        защищённую функцию (delta-режим), которая сама блокирует запись,
        не даёт уйти в минус и обновляет кэш.
        """
        return await self.update_user_balance(user_id, f"-{int(amount)}")













    async def retrieve_user_balance(self, username):
        """
        Получает баланс пользователя по имени пользователя.

        Раньше читала balance напрямую raw SQL по username - отдельный,
        не связанный с get_user_balance путь чтения (и без кэша). Теперь
        сначала резолвит username -> user_id (get_user_id_by_username),
        а сам баланс берёт через ЕДИНУЮ get_user_balance - тот же кэш,
        то же поведение, что и везде в проекте.
        """
        print(f"Поиск баланса для пользователя: {username}")
        user_id = await self.get_user_id_by_username(username)
        if user_id is None:
            print(f"Пользователь @{username} не найден в базе данных")
            return None
        return await self.get_user_balance(user_id)

    async def modify_user_balance(self, username, new_balance):
        """
        Обновляет баланс пользователя по имени пользователя.

        Раньше писала balance напрямую raw SQL по username, в обход
        update_user_balance (без защиты от гонок/ухода в минус и без
        обновления кэша). Теперь резолвит username -> user_id и делегирует
        в update_user_balance - тот же единый путь записи, что и везде
        в проекте. new_balance можно передавать как абсолютное значение,
        так и дельтой ("+N"/"-N") - update_user_balance поддерживает оба режима.
        """
        print(f"Обновление баланса пользователя @{username} до {new_balance}")
        user_id = await self.get_user_id_by_username(username)
        if user_id is None:
            print(f"Пользователь @{username} не найден в базе данных")
            return None

        result = await self.update_user_balance(user_id, new_balance)
        if result is None:
            print(f"Ошибка при обновлении баланса пользователя {username}")
        else:
            print(f"Баланс пользователя @{username} успешно обновлен")
        return result

    async def handle_withdraw(self, message, admin_id):
        """Обрабатывает снятие средств."""
        # Убедитесь, что пользователь является администратором
        if message.from_user.id in admin_id:
            all_symb = message.text.lower().split()

            # Проверяем, что команда соответствует шаблону 'снять [username] [amount]'
            if len(all_symb) >= 3 and all_symb[0] == 'снять':
                target = all_symb[1]  # Целевой пользователь
                try:
                    amount_to_withdraw = float(all_symb[2])  # Сумма для снятия
                except ValueError:
                    await message.reply('Неверный формат суммы для снятия. Пожалуйста, введите число.')
                    return

                # Извлечение имени пользователя из URL или @username
                if target.startswith('https://t.me/'):
                    username = target.replace('https://t.me/', '')
                elif target.startswith('@'):
                    username = target[1:]  # Убираем символ '@'
                else:
                    await message.reply(
                        'Некорректный формат имени пользователя. Пожалуйста, используйте ссылку или @username.')
                    return

                # Получение текущего баланса пользователя
                current_balance = await self.retrieve_user_balance(username)

                # Проверяем, что пользователь существует и у него достаточно средств
                if current_balance is not None:
                    if current_balance >= amount_to_withdraw:
                        # Вычитаем сумму для снятия из текущего баланса и обновляем баланс пользователя
                        new_balance = current_balance - amount_to_withdraw
                        await self.modify_user_balance(username, new_balance)

                        # Отправляем сообщение об успехе операции
                        await message.reply(
                            f'Успешно снято {amount_to_withdraw} с баланса @{username}. Новый баланс: {new_balance}')
                    else:
                        await message.reply(
                            f'У пользователя @{username} недостаточно средств для снятия {amount_to_withdraw}. Баланс: {current_balance}')
                else:
                    await message.reply(f'Пользователь @{username} не найден в базе данных.')
            else:
                await message.reply('Неверный формат команды. Пожалуйста, используйте: "снять [username] [amount]"')
        else:
            await message.reply('Вы не являетесь администратором, доступ запрещен.')



    async def get_user_username(self, user_id):
        """Получает имя пользователя (username) по его идентификатору (user_id)."""
        try:
            # Получаем подключение из пула
            async with self.pool.acquire() as connection:
                # Выполняем SQL-запрос для получения имени пользователя по user_id
                result = await connection.fetchrow("SELECT username FROM users WHERE user_id = $1", user_id)

            # Если результат найден, возвращаем username
            if result:
                return result['username']
            else:
                # Если результат не найден, возвращаем None
                return None
        except Exception as e:
            # Обработка ошибок в случае проблемы с базой данных
            print(f"Ошибка при получении username для user_id1 {user_id}: {e}")
            return None



    async def get_username_by_id(self, user_id):
        """Получает имя пользователя по его идентификатору (user_id)."""
        try:
            # Получаем подключение из пула
            async with self.pool.acquire() as connection:
                # Выполняем SQL-запрос для получения имени пользователя по user_id
                result = await connection.fetchrow("SELECT username FROM users WHERE user_id = $1", user_id)

            # Если результат найден, возвращаем username
            if result:
                return result['username']
            else:
                # Если результат не найден, возвращаем None
                return None
        except Exception as e:
            # Обработка ошибок в случае проблемы с базой данных
            print(f"Ошибка при получении username для user_id2 {user_id}: {e}")
            return None

    async def user_exists(self, user_id: int):
        """Проверяет, существует ли пользователь с данным user_id в базе данных."""
        try:
            # Получаем подключение из пула
            async with self.pool.acquire() as connection:
                # Выполняем SQL-запрос для проверки существования пользователя по user_id
                result = await connection.fetchrow("SELECT 1 FROM users WHERE user_id = $1", user_id)

            # Если результат найден, то пользователь существует
            return result is not None
        except Exception as e:
            # Обработка ошибок в случае проблемы с базой данных
            print(f"Ошибка при проверке существования пользователя с user_id {user_id}: {e}")
            return False

    async def add_user_database(self, user_id, username):
        """Добавление пользователя в базу данных."""
        try:
            # Получаем подключение из пула
            async with self.pool.acquire() as connection:
                # Пытаемся вставить запись, игнорируя дублирование
                result = await connection.execute(
                    "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
                    user_id, username
                )
                if result:
                    print(f"Пользователь {username} с ID {user_id} успешно добавлен.")
                else:
                    print(f"Пользователь {username} с ID {user_id} уже существует.")
        except Exception as e:
            print(f"Ошибка при добавлении пользователя {username}: {e}")

    async def add_ref1(self , user_id: int , refferer_id: int) -> bool:
        """
        Устанавливает/заменяет пригласителя (refferer_id) для user_id.

        Поведение:
          - Если строки в users нет - создаёт и ставит refferer_id.
          - Если строка есть - ПЕРЕЗАПИСЫВАЕТ refferer_id на новый.
          - Если новое значение совпадает со старым - возвращает False (no-op).
          - Самореф (user_id == refferer_id) запрещён → False.

        Возвращает:
          True  - если была вставка или реальное изменение значения.
          False - если ничего не изменилось (уже стоял тот же refferer_id) или самореф.
        """
        if not isinstance(user_id , int) or not isinstance(refferer_id , int):
            raise ValueError("user_id и refferer_id должны быть int")

        if user_id == refferer_id:
            # Нельзя назначать себя пригласителем
            return False

        # Опционально гарантируем, что у пригласителя есть строка в users (заглушка)
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING;" , refferer_id)

                # Апсертом вставляем или обновляем, НО апдейт делаем только если значение реально меняется
                # (IS DISTINCT FROM корректно сравнивает с учётом NULL).
                changed_sql = """
                    WITH upsert AS (
                      INSERT INTO users (user_id, refferer_id)
                      VALUES ($1, $2)
                      ON CONFLICT (user_id) DO UPDATE
                        SET refferer_id = EXCLUDED.refferer_id
                        WHERE users.refferer_id IS DISTINCT FROM EXCLUDED.refferer_id
                      RETURNING 1
                    )
                    SELECT EXISTS (SELECT 1 FROM upsert);
                """
                changed = await conn.fetchval(changed_sql , user_id , refferer_id)
                return bool(changed)
        except Exception as e:
            print(f"[ERROR] add_ref1(user_id={user_id}, refferer_id={refferer_id}): {e}")
            return False

    async def set_active(self, user_id, active):
        """Обновляет статус активности пользователя."""
        try:
            # Получаем подключение из пула
            async with self.pool.acquire() as connection:
                # Выполняем запрос на обновление статуса активности пользователя
                await connection.execute(
                    "UPDATE users SET active = $1 WHERE user_id = $2",
                    active, user_id
                )
                print(f"Статус активности для пользователя {user_id} обновлен на {active}")
        except Exception as e:
            print(f"Ошибка при обновлении статуса активности для пользователя {user_id}: {e}")

    async def get_data_users(self):
        """Получаем данные пользователей из базы данных."""
        try:
            # Получаем подключение из пула
            async with self.pool.acquire() as connection:
                # Выполняем запрос и получаем все строки из запроса
                rows = await connection.fetch(
                    "SELECT user_id, balance, refferals, activated_promo, refferer_id, username, items FROM users"
                )
                return rows  # Возвращаем результат
        except Exception as e:
            print(f"Ошибка при получении данных пользователей: {e}")
            return []

    async def get_donaters(self):
        """
        Получает user_id и donate пользователей с donate > 0.
        """
        try:
            async with self.pool.acquire() as connection:
                # Получаем данные пользователей: user_id и donate
                return await connection.fetch("SELECT user_id, donate FROM users WHERE donate > 0")
        except Exception as e:
            print(f"[ERROR] Ошибка при получении данных донатеров: {e}")
            return [ ]




    async def set_ref_user(self, user_id, option):
        """Обновляет количество рефералов для пользователя."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем обновление данных пользователя
                await connection.execute(
                    "UPDATE users SET refferals = $1 WHERE user_id = $2",
                    option, user_id
                )
                print(f"Рефералы для пользователя с user_id {user_id} успешно обновлены.")
        except Exception as e:
            print(f"Ошибка при обновлении рефералов для пользователя {user_id}: {e}")

    async def get_user_data(self, user_id: int):
        """Получает данные пользователя по user_id (баланс и количество рефералов)."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос на получение баланса и рефералов
                result = await connection.fetchrow(
                    "SELECT balance, refferals FROM users WHERE user_id = $1",
                    user_id
                )

            if result:
                # Если данные получены, возвращаем их в виде словаря
                return {'balance': result['balance'], 'refferals': result['refferals']}
            else:
                # Если данных нет, возвращаем None
                return None

        except Exception as e:
            print(f"Ошибка при получении данных для пользователя с user_id {user_id}: {e}")
            return None



    async def set_prom(self, user_id, option):
        """Обновляет статус активации промо-кода для пользователя."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос на обновление статуса активации промо-кода
                await connection.execute(
                    "UPDATE users SET activated_promo = $1 WHERE user_id = $2",
                    option, user_id
                )
            print(f"Статус промо для пользователя с user_id {user_id} успешно обновлен.")
        except Exception as e:
            print(f"Ошибка при обновлении статуса промо для пользователя с user_id {user_id}: {e}")

    async def get_username_by_user_id(self , user_id):
        """Получает username по user_id (кэш на 5 минут, чтобы не бить БД на каждый вызов)."""
        if user_id is None:
            return None
        now = time.monotonic()
        cached = self._username_cache.get(user_id)
        if cached is not None and (now - cached[0]) < self._username_cache_ttl:
            return cached[1]
        try:
            async with self.pool.acquire() as connection:
                # Передаем user_id как целое число, без преобразования в строку
                row = await connection.fetchrow(
                    "SELECT username FROM users WHERE user_id = $1" , user_id)
                value = row['username'] if row else None
                self._username_cache[user_id] = (now, value)
                return value
        except Exception as e:
            print(f"Ошибка при получении username для user_id {user_id}: {e}")
        return None

    def invalidate_username_cache(self, user_id=None):
        """Сбросить кэш username (после смены ника)."""
        if user_id is None:
            self._username_cache.clear()
        else:
            self._username_cache.pop(user_id, None)



















    async def get_clan_by_user_id(self, user_id):
        """
        Находит клан, в котором состоит пользователь, по его идентификатору.
        """
        query = """
            SELECT emoji, name, owner, members, zam
            FROM clan
            WHERE owner = $1 OR members LIKE $2
        """
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(query, user_id, f"%{user_id}%")
            if row:
                return {
                    'emoji': row['emoji'],
                    'name': row['name'],
                    'owner': row['owner'],
                    'members': row['members'],  # Поле сохраняется как строка
                    'zam': row['zam']  # Поле сохраняется как строка
                }
        return None

    async def get_clan_private_status(self, emoji):
        """
        Получение статуса приватности клана по его эмодзи.
        """
        query = "SELECT private FROM clan WHERE emoji = $1"
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchval(query, emoji)
                if result is not None:
                    # Возвращаем строковый статус в зависимости от значения
                    if result == 1:
                        return "Приватный"
                    elif result == 0:
                        return "Публичный"
                return "Не определен"  # Возвращаем "Не определен", если клан не найден
        except Exception as e:
            print(f"Ошибка при получении статуса приватности: {e}")
            return "Ошибка"  # Возвращаем "Ошибка" в случае возникновения исключения





    async def update_clan_private_status(self, emoji, status):
        """
        Обновление статуса приватности клана.
        """
        # Запросы для проверки текущего статуса и обновления
        select_query = "SELECT private FROM clan WHERE emoji = $1"
        update_query = "UPDATE clan SET private = $1 WHERE emoji = $2"

        try:
            async with self.pool.acquire() as connection:
                # Получение текущего статуса приватности
                current_status = await connection.fetchval(select_query, emoji)

                if current_status is None:
                    print("Клан не найден.")
                    return

                # Определение нового статуса
                new_status = 1 if current_status == 0 else 0

                # Обновление статуса
                await connection.execute(update_query, new_status, emoji)
                print(f"Статус приватности клана обновлен: {new_status}")
        except Exception as e:
            # Логирование или обработка ошибок
            print(f"Ошибка обновления статуса приватности клана: {e}")



    async def get_clan_zam_list(self, emoji):
        """
        Получение списка идентификаторов заместителей клана по его эмодзи.
        """
        query = "SELECT zam FROM clan WHERE emoji = $1"
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос
                zam_list_str = await connection.fetchval(query, emoji)

                # Проверяем, если данных нет
                if zam_list_str is None:
                    print(f"Заместители для клана {emoji} не найдены (нет данных в базе).")
                    return []

                print(f"Полученное значение из базы данных для клана {emoji}: {zam_list_str} (тип: {type(zam_list_str)})")

                # Убедимся, что строка не пуста
                zam_list_str = zam_list_str.strip() if isinstance(zam_list_str, str) else ""
                if not zam_list_str:
                    print(f"Заместители для клана {emoji} не найдены (пустое значение).")
                    return []

                # Преобразуем строку в список
                zam_list = [zam_id.strip() for zam_id in zam_list_str.split(',') if zam_id.strip()]
                print(f"Список идентификаторов заместителей для клана {emoji}: {zam_list}")
                return zam_list
        except Exception as e:
            print(f"Ошибка при получении списка заместителей для клана {emoji}: {e}")
            return []

    async def get_zam_info(self, zam_ids):
        """
        Получение информации о заместителях по их идентификаторам.
        """
        if not zam_ids:
            print("Нет идентификаторов заместителей для получения информации.")
            return "Нет заместителей"

        # Формируем запрос с использованием $N для параметров
        placeholders = ', '.join([f"${i+1}" for i in range(len(zam_ids))])
        query = f"SELECT user_id, first_name FROM users WHERE user_id IN ({placeholders})"

        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос
                rows = await connection.fetch(query, *zam_ids)
                print(f"Полученные данные о заместителях: {rows}")

                # Проверяем, есть ли данные
                if not rows:
                    print("Информация о заместителях не найдена.")
                    return "Нет заместителей"

                # Формируем список ссылок
                zam_list_str = [
                    f"<a href='tg://user?id={row['user_id']}'>{row['first_name']}</a>"
                    for row in rows
                ]
                return ', '.join(zam_list_str) if zam_list_str else "Нет заместителей"
        except Exception as e:
            print(f"Ошибка при получении информации о заместителях: {e}")
            return "Ошибка получения данных"

    async def is_target_id_zam(self , emoji , target_id):
        """
        Проверяет, является ли указанный идентификатор заместителем в клане.
        """
        query = "SELECT zam FROM clan WHERE emoji = $1"
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос
                row = await connection.fetchrow(query , emoji)

                # Если данные не найдены или список заместителей пуст
                if not row or not row [ 'zam' ]:
                    return False

                zam_list_str = row [ 'zam' ]

                # Если значение - целое число, создаем пустой список
                if isinstance(zam_list_str , int):
                    zam_list = [ ]
                else:
                    # Преобразуем строку в список
                    zam_list = zam_list_str.split(',')

                # Проверяем, есть ли target_id в списке
                return str(target_id) in zam_list
        except Exception as e:
            print(f"Ошибка при проверке заместителя: {e}")
            return False

    async def add_zam_to_clan(self, emoji, target_id):
        """
        Добавляет нового заместителя в клан.
        """
        try:
            query_select = "SELECT zam FROM clan WHERE emoji = $1"
            query_update = "UPDATE clan SET zam = $1 WHERE emoji = $2"

            async with self.pool.acquire() as connection:
                # Получаем текущий список заместителей
                result = await connection.fetchrow(query_select, emoji)

                if result:
                    current_members = result['zam']  # Получаем список замов

                    # Добавляем нового пользователя к списку
                    if current_members:
                        updated_members = f"{current_members},{target_id}"
                    else:
                        updated_members = str(target_id)

                    # Обновляем запись в базе данных
                    await connection.execute(query_update, updated_members, emoji)
        except Exception as e:
            print(f"Ошибка при добавлении заместителя: {e}")

    async def get_clan_by_user_zam(self , user_id):
        """
        Получаем эмодзи клана для пользователя по его ID.
        """
        query = """
            SELECT emoji 
            FROM clan 
            WHERE owner = $1 OR zam LIKE $2
        """
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос
                result = await connection.fetchrow(query , user_id , f"%{user_id}%")

                # Если есть результат, возвращаем значение
                if result:
                    return result [ 'emoji' ]
        except Exception as e:
            print(f"Ошибка при получении эмодзи клана: {e}")

        # Если ничего не найдено, возвращаем None
        return None

    async def get_clan_by_emoji_zam(self , clan_emoji):
        """Получаем информацию о клане по эмодзи."""
        query = """
            SELECT * 
            FROM clan 
            WHERE emoji = $1
        """
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос
                result = await connection.fetchrow(query , clan_emoji)

                # Если есть результат, возвращаем его в виде словаря
                if result:
                    return dict(result)
        except Exception as e:
            print(f"Ошибка при получении информации о клане по эмодзи: {e}")

        # Если ничего не найдено, возвращаем None
        return None

    async def check_demotion_conditions(self, initiator_id, target_id):
        """Проверяем условия для понижения должности заместителя."""
        # Получаем эмодзи клана для инициатора
        clan_emoji = await self.get_clan_by_user_zam(initiator_id)
        if not clan_emoji:
            return "🛠 Вы не являетесь членом какого-либо клана.", None

        # Получаем информацию о клане по эмодзи
        clan_info = await self.get_clan_by_emoji_zam(clan_emoji)
        if not clan_info:
            return "🛠 Не удалось найти клан с указанным эмодзи.", None

        # Проверка, является ли пользователь лидером клана
        if clan_info['owner'] != initiator_id:
            return "🛠 Вы не являетесь лидером клана.", None

        # Проверка, является ли целевой пользователь заместителем
        zam_list = clan_info['zam']
        if not zam_list:
            return "🛠 Список заместителей пуст.", None

        # Преобразуем зам_list в строку, если это необходимо
        if isinstance(zam_list, int):
            zam_list = str(zam_list)

        # Преобразуем строку эмодзи в список для поиска целевого пользователя
        zam_list = zam_list.split(',')
        if str(target_id) not in zam_list:
            return "🛠 Этот пользователь не является заместителем вашего клана.", None

        return None, clan_info

    async def remove_zam(self, clan_emoji, target_id):
        """Удаляем идентификатор пользователя из списка заместителей клана."""
        # Получаем информацию о клане по эмодзи
        clan_info = await self.get_clan_by_emoji_zam(clan_emoji)
        if not clan_info:
            return False

        # Проверяем текущий список заместителей
        zam_list = clan_info['zam']
        if not zam_list:
            return False

        # Преобразуем зам_list в строку, если это необходимо
        if isinstance(zam_list, int):
            zam_list = str(zam_list)

        # Преобразуем строку эмодзи в список и удаляем целевого пользователя
        zam_list = zam_list.split(',')
        if str(target_id) in zam_list:
            zam_list.remove(str(target_id))
            new_zam_list = ','.join(zam_list)
        else:
            return False

        # Обновляем запись в базе данных
        query = "UPDATE clan SET zam = $1 WHERE emoji = $2"
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(query, new_zam_list, clan_emoji)
        return True

    async def get_user_first_name(self, user_id):
        query = "SELECT first_name FROM users WHERE user_id = $1"
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow(query, user_id)
        if result:
            return result['first_name']
        return None



    async def update_clan_members_and_zam(self, emoji, members, zam):
        members_string = ','.join(members)
        zam_string = ','.join(zam)

        query = """
            UPDATE clan
            SET members = $1, zam = $2
            WHERE emoji = $3
        """

        async with self.pool.acquire() as connection:
            await connection.execute(query, members_string, zam_string, emoji)

    async def get_all_clans3412(self):
        query = "SELECT emoji, name, owner, members FROM clan"

        async with self.pool.acquire() as connection:
            result = await connection.fetch(query)

        return result

    async def get_clans_data(self):
        query = "SELECT emoji, name, coins FROM clan"

        async with self.pool.acquire() as connection:
            result = await connection.fetch(query)

        return result

    async def get_clan_name(self , emoji):
        """Находит название клана по эмодзи."""
        try:
            query = "SELECT name FROM clan WHERE emoji = $1"

            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , emoji)

            if result:
                return result [ 'name' ]  # Возвращаем название клана
            return None
        except Exception as e:
            print(f"DEBUG: Ошибка при получении названия клана для эмодзи {emoji}: {e}")
            return None

    async def get_clan_emoji3(self , user_id):
        query = """
            SELECT emoji 
            FROM clan 
            WHERE $1 = ANY(members) OR owner = $1
        """

        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(query , user_id)

            return row [ 'emoji' ] if row else None
        except Exception as e:
            print(f"DEBUG: Ошибка при получении эмодзи клана для пользователя {user_id}: {e}")
            return None

    async def get_clan_attack(self , clan_emoji):
        query = "SELECT attack, clanattack FROM clan WHERE emoji = $1"

        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(query , clan_emoji)

            return row if row else None
        except Exception as e:
            print(f"DEBUG: Ошибка при получении данных о нападении клана для эмодзи {clan_emoji}: {e}")
            return None

    async def get_clan_balance(self , clan_emoji):
        """Возвращает текущий баланс клана."""
        query = "SELECT coins FROM clan WHERE emoji = $1"

        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(query , clan_emoji)

            if row:
                balance = row [ 'coins' ]
                print(f"DEBUG: Баланс клана {clan_emoji}: {balance}")
                return balance
            else:
                print(f"DEBUG: Клан с эмодзи {clan_emoji} не найден.")
                return None
        except Exception as e:
            print(f"DEBUG: Ошибка при получении баланса клана {clan_emoji}: {e}")
            return None




    async def adjust_clan_coins(self, clan_emoji, amount, operation):
        """
        Регулирует баланс клана в зависимости от типа операции.

        :param clan_emoji: Эмодзи клана.
        :param amount: Сумма для добавления или уменьшения.
        :param operation: Тип операции ('add' для увеличения, 'deduct' для уменьшения).
        """
        query = ""
        if operation == 'add':
            query = "UPDATE clan SET coins = coins + $1 WHERE emoji = $2"
            print(f"DEBUG: Баланс клана {clan_emoji} увеличен на {amount}.")
        elif operation == 'deduct':
            query = "UPDATE clan SET coins = coins - $1 WHERE emoji = $2"
            print(f"DEBUG: Баланс клана {clan_emoji} уменьшен на {amount}.")
        else:
            print(f"DEBUG: Некорректная операция: {operation}. Используйте 'add' или 'deduct'.")
            return

        try:
            # Получаем соединение из пула
            async with self.pool.acquire() as connection:
                await connection.execute(query, amount, clan_emoji)

            print(f"DEBUG: Операция {operation} для клана {clan_emoji} завершена.")
        except Exception as e:
            print(f"DEBUG: Ошибка при регулировке баланса клана {clan_emoji}: {e}")

    #12

    async def clear_clan_attack(self, clan_emoji):
        """
        Очищает данные о текущем нападении и атакующем клане.
        Сначала устанавливает 0 в столбец attack, если его значение было 1.
        """
        try:
            async with self.pool.acquire() as connection:
                # Обновляем столбец attack
                await connection.execute(
                    "UPDATE clan SET attack = 0 WHERE emoji = $1 AND attack = 1", (clan_emoji,)
                )

                # Очищаем данные о текущем нападении и атакующем клане
                await connection.execute(
                    "UPDATE clan SET clanattack = NULL, at = NULL WHERE emoji = $1", (clan_emoji,)
                )

            print(f"DEBUG: Данные о нападении для клана {clan_emoji} были очищены.")
        except Exception as e:
            print(f"DEBUG: Ошибка при очистке данных о нападении для клана {clan_emoji}: {e}")
    async def get_clan_attacker(self, defending_clan_emoji):
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос и получаем результат
                result = await connection.fetchrow(
                    "SELECT clanattack FROM clan WHERE emoji = $1", defending_clan_emoji
                )

            # Если результат есть, возвращаем значение, иначе None
            return result['clanattack'] if result else None
        except Exception as e:
            print(f"DEBUG: Ошибка при получении атакующего клана для {defending_clan_emoji}: {e}")
            return None



    async def update_clan_coins(self, clan_emoji, new_coins):
        """
        Обновить количество монет в клане по его эмодзи.
        """
        async with self.pool.acquire() as connection:
            await connection.execute(
                "UPDATE clan SET coins = $1 WHERE emoji = $2",
                new_coins, clan_emoji
            )

    async def get_clan_at(self , clan_emoji):
        """
        Проверяет, какой клан атакует данный клан.
        Если в столбце `at` есть информация, возвращает `True` (атакующий клан).
        Если в столбце `at` стоит `NULL`, возвращает `False` (не атакующий клан).
        """
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос и получаем результат
                result = await connection.fetchrow(
                    "SELECT at FROM clan WHERE emoji = $1" , clan_emoji)

            # Если результат найден, проверяем значение в столбце `at`
            if result is not None:
                at_value = result [ 'at' ]
                # Если в столбце `at` есть информация (не NULL), возвращаем True
                return bool(at_value)

            # Если данных по указанному emoji нет, возвращаем False
            return False
        except Exception as e:
            print(f"DEBUG: Ошибка при проверке атакующего клана для {clan_emoji}: {e}")
            return False

    async def is_clan_in_war(self , clan_emoji):
        """
        Проверяет, находится ли клан в состоянии войны.
        """
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для получения значения поля 'attack'
                result = await connection.fetchrow(
                    "SELECT attack FROM clan WHERE emoji = $1" , clan_emoji)

            # Проверяем результат, если найдено значение, то проверяем его
            if result:
                return result [ 'attack' ] == 1
            return False
        except Exception as e:
            print(f"DEBUG: Ошибка при проверке состояния войны для клана {clan_emoji}: {e}")
            return False

    async def is_clan_attacking(self , clan_emoji):
        """
        Проверяет, является ли клан атакующим.
        Клан считается атакующим, если его статус атаки равен 'in_war' и столбец `at` равен NULL.
        """
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для получения значений столбцов 'at' и 'attack'
                result = await connection.fetchrow(
                    "SELECT at, attack FROM clan WHERE emoji = $1" , clan_emoji)

            # Если результат запроса найден, проверяем условия
            if result:
                at_value , war_status = result [ 'at' ] , result [ 'attack' ]
                return at_value is None and war_status == 'in_war'
            return False
        except Exception as e:
            print(f"DEBUG: Ошибка при проверке состояния атаки для клана {clan_emoji}: {e}")
            return False



    async def update_clan_at(self, emoji, target_clan_emoji):
        """
        Обновляет столбец `at` клана, устанавливая его в эмодзи атакующего клана.
        """
        try:
            async with self.pool.acquire() as connection:
                # Обновляем столбец 'at' для указанного клана
                await connection.execute(
                    "UPDATE clan SET at = $1 WHERE emoji = $2", target_clan_emoji, emoji
                )
            print(f"DEBUG: Столбец 'at' клана {emoji} успешно обновлен на {target_clan_emoji}.")
        except Exception as e:
            print(f"DEBUG: Ошибка при обновлении столбца 'at' клана {emoji}: {e}")

    async def get_clan_info_by_emoji(self, clan_emoji):
        """
        Получает информацию о клане по его эмодзи.
        """
        query = """
            SELECT emoji, name, owner, attack, members, private, zam
            FROM clan
            WHERE emoji = $1
        """
        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(query, clan_emoji)
                if row:
                    return {
                        'emoji': row['emoji'],
                        'name': row['name'],
                        'owner': row['owner'],
                        'attack': row['attack'],
                        'members': row['members'],
                        'private': row['private'],
                        'zam': row['zam']
                    }
            return None
        except Exception as e:
            print(f"DEBUG: Ошибка при получении информации о клане {clan_emoji}: {e}")
            return None

    async def clear_clan_at(self , clan_emoji: str):
        """
        Очищает информацию из столбца `at` у целевого и атакующего клана.
        """
        query = """
            UPDATE clan
            SET at = NULL
            WHERE emoji = $1 OR emoji = (SELECT at FROM clan WHERE emoji = $1)
        """
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(query , clan_emoji)
                print(f"DEBUG: Информация о столбце 'at' для клана {clan_emoji} очищена.")
        except Exception as e:
            print(f"DEBUG: Ошибка при очистке столбца 'at' для клана {clan_emoji}: {e}")

    async def finish_clan_war(self , clan_emoji: str):
        """
        Завершает войну между кланами, сбрасывая статус атаки и очищая информацию о текущем атакующем клане.
        """
        query = """
            UPDATE clan
            SET attack = 0, clanattack = NULL
            WHERE emoji = $1 OR emoji = (SELECT clanattack FROM clan WHERE emoji = $1)
        """
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(query , clan_emoji)
                print(f"DEBUG: Война для клана {clan_emoji} завершена.")
        except Exception as e:
            print(f"DEBUG: Ошибка при завершении войны для клана {clan_emoji}: {e}")

    async def update_clan_attackclan(self , clan_emoji: str , enemy_clan_emoji: str):
        """
        Обновляет информацию о клане, который атакует данный клан.
        """
        query = """
            UPDATE clan
            SET clanattack = $1
            WHERE emoji = $2
        """
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(query , enemy_clan_emoji , clan_emoji)
                print(f"DEBUG: Клан {clan_emoji} теперь атакует клан {enemy_clan_emoji}.")
        except Exception as e:
            print(f"DEBUG: Ошибка при обновлении атаки клана {clan_emoji}: {e}")

    async def get_clan_war_status(self , clan_emoji: str):
        try:
            query = """
                SELECT attack, clanattack FROM clan WHERE emoji = $1
            """
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , clan_emoji)

                if result:
                    attack_status = result [ 'attack' ]  # Статус войны (0 - нет войны, 1 - война)
                    enemy_clan_emoji = result [ 'clanattack' ]  # Эмодзи клана противника

                    if attack_status == 0:
                        return "Нет битв"
                    elif attack_status == 1:
                        if enemy_clan_emoji:
                            # Находим название и эмодзи клана противника
                            enemy_query = """
                                SELECT emoji, name FROM clan WHERE emoji = $1
                            """
                            enemy_clan = await connection.fetchrow(enemy_query , enemy_clan_emoji)

                            if enemy_clan:
                                enemy_clan_emoji , enemy_clan_name = enemy_clan [ 'emoji' ] , enemy_clan [ 'name' ]
                                return f'Битва против <b>"<code>{enemy_clan_emoji}</code> {enemy_clan_name}"</b>'
                            else:
                                return "Информация о клане-противнике не найдена"
                        else:
                            return "Ошибка: Не указано, с каким кланом идет война"
                    else:
                        return "Неизвестный статус"
                else:
                    return "Клан не найден"
        except Exception as e:
            print(f"Ошибка при получении статуса войны: {e}")
            return "Ошибка запроса"

    async def get_clan_attack_status(self , clan_emoji: str):
        query = "SELECT attack FROM clan WHERE emoji = $1"
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , clan_emoji)

                if result:
                    return result [ 'attack' ]
                return None
        except Exception as e:
            print(f"Ошибка при получении статуса атаки: {e}")
            return None

    async def update_clan_attack_status(self , clan_emoji: str , status: int):
        query = "UPDATE clan SET attack = $1 WHERE emoji = $2"
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(query , status , clan_emoji)
        except Exception as e:
            print(f"Ошибка при обновлении статуса атаки: {e}")

    async def find_clan_by_member_or_owner(self , user_id: int):
        query = """
            SELECT name, emoji, owner 
            FROM clan 
            WHERE owner = $1 OR members LIKE $2
        """
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , user_id , f"%{user_id}%")
                return result
        except Exception as e:
            print(f"Ошибка при поиске клана по владельцу или участнику: {e}")
            return None

    async def find_clan_by_emoji(self , emoji: str):
        query = """
            SELECT * 
            FROM clan 
            WHERE emoji = $1
        """
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , emoji)
                return result
        except Exception as e:
            print(f"Ошибка при поиске клана по эмодзи: {e}")
            return None

    async def get_clan_members_and_owner(self , emoji: str):
        query = """
            SELECT members, owner 
            FROM clan 
            WHERE emoji = $1
        """
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , emoji)

                if result:
                    members_str , owner_id = result
                    # Проверяем, что members_str не является None перед split
                    if members_str:
                        members_list = members_str.split(',')
                    else:
                        members_list = [ ]
                    return members_list , owner_id  # Возвращаем список участников и идентификатор владельца
                return None
        except Exception as e:
            print(f"Ошибка при получении участников и владельца клана: {e}")
            return None

    async def get_clan_rating(self , emoji: str):
        query = """
            SELECT coins 
            FROM clan 
            WHERE emoji = $1
        """
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , emoji)

                if result:
                    return result [ 'coins' ]  # Возвращаем значение из поля 'coins'
                return None  # Если нет данных, возвращаем None
        except Exception as e:
            print(f"Ошибка при получении рейтинга клана: {e}")
            return None

    async def get_clan_name_by_emoji(self , emoji: str) -> str:
        # Retrieve the clan name by its emoji
        print(f"[DEBUG] Retrieving clan name for emoji: {emoji}")
        query = "SELECT name FROM clan WHERE emoji = $1"

        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , emoji)
                if result:
                    print(f"[DEBUG] Clan name found: {result [ 'name' ]}")
                    return result [ 'name' ]
                else:
                    print(f"[WARNING] Clan with emoji {emoji} not found.")
                    return None
        except Exception as e:
            print(f"[ERROR] Error retrieving clan name: {e}")
            return None

    async def update_clan_members(self , clan_emoji: str , members: list):
        try:
            # Преобразуем список членов в строку
            members_str = ','.join(map(str , members))
            print(f"members_str: {members_str}, clan_emoji: {clan_emoji}")

            # SQL-запрос для обновления
            query = "UPDATE clan SET members = $1 WHERE emoji = $2"

            # Выполнение асинхронного запроса с использованием пула соединений
            async with self.pool.acquire() as connection:
                await connection.execute(query , members_str , clan_emoji)
                print(f"Обновлены члены клана с эмодзи {clan_emoji}")
        except Exception as e:
            print(f"Произошла ошибка при обновлении членов клана: {e}")

    async def get_clan_members(self , clan_emoji: str) -> list:
        try:
            # SQL-запрос для получения членов клана
            query = "SELECT members FROM clan WHERE emoji = $1"

            # Выполнение асинхронного запроса с использованием пула соединений
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , clan_emoji)

                # Если результат найден, разбиваем строку на список
                if result and result [ 'members' ]:
                    return result [ 'members' ].split(',')
                return [ ]
        except Exception as e:
            print(f"Произошла ошибка при получении членов клана: {e}")
            return [ ]

    async def get_clan_by_owner(self , owner_id):
        try:
            # SQL-запрос для получения данных о клане, владельцем которого является заданный пользователь
            query = "SELECT name, owner, members, coins, item FROM clan WHERE owner = $1"

            # Выполнение асинхронного запроса с использованием пула соединений
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query , owner_id)

            # Если результат найден, вернуть его в виде словаря
            if result:
                return {'name': result [ 'name' ] ,  # Название клана
                    'owner': result [ 'owner' ] ,  # Идентификатор владельца
                    'members': result [ 'members' ] ,  # Список участников
                    'coins': result [ 'coins' ] ,  # Казна клана
                    'item': result [ 'item' ] ,  # Склад клана
                }
            return None
        except Exception as e:
            print(f"Произошла ошибка при получении данных о клане: {e}")
            return None

    async def update_clan(self , current_name , new_name=None , new_emoji=None , owner_id=None):
        try:
            # Формируем список обновлений и параметров
            updates = [ ]
            params = [ ]

            # Проверяем, нужно ли обновить название
            if new_name is not None:
                updates.append("name = $1")
                params.append(new_name)

            # Проверяем, нужно ли обновить эмодзи
            if new_emoji is not None:
                updates.append("emoji = $2")
                params.append(new_emoji)

            # Если есть, что обновлять, выполняем запрос
            if updates:
                # Параметры для WHERE
                params.extend([ current_name , owner_id ])

                # Формируем SQL-запрос для обновления
                query = f"UPDATE clan SET {', '.join(updates)} WHERE name = $3 AND owner = $4"

                # Выполнение асинхронного запроса с использованием пула соединений
                async with self.pool.acquire() as connection:
                    await connection.execute(query , *params)

                print(f"Клан '{current_name}' был успешно обновлён.")
            else:
                print("Нет данных для обновления.")

        except Exception as e:
            print(f"Произошла ошибка при обновлении клана: {e}")

    async def get_clans_by_emoji(self , emoji):
        if not isinstance(emoji , str):
            raise ValueError("Emoji must be a string.")

        try:
            query = "SELECT * FROM clan WHERE emoji = $1"
            # Выполнение асинхронного запроса с использованием пула соединений
            async with self.pool.acquire() as connection:
                result = await connection.fetch(query , emoji)

            return result

        except Exception as e:
            print(f"Ошибка при получении кланов по эмодзи: {e}")
            return None

    async def get_clans_by_emoji(self , emoji):
        if not isinstance(emoji , str):
            raise ValueError("Emoji must be a string.")

        try:
            query = "SELECT * FROM clan WHERE emoji = $1"
            # Выполнение асинхронного запроса с использованием пула соединений
            async with self.pool.acquire() as connection:
                result = await connection.fetch(query , emoji)

            return result

        except Exception as e:
            print(f"Ошибка при получении кланов по эмодзи: {e}")
            return None

    async def get_all_clan_emojis(self):
        try:
            query = "SELECT emoji FROM clan"
            # Асинхронное выполнение запроса с использованием пула соединений
            async with self.pool.acquire() as connection:
                result = await connection.fetch(query)

            # Возвращаем список эмодзи
            return [ row [ 'emoji' ] for row in result ]

        except Exception as e:
            print(f"Ошибка при получении эмодзи кланов: {e}")
            return [ ]

    async def get_all_clan_names(self):
        try:
            query = "SELECT name FROM clan"
            # Асинхронное выполнение запроса с использованием пула соединений
            async with self.pool.acquire() as connection:
                result = await connection.fetch(query)

            # Возвращаем список названий кланов
            return [ row [ 'name' ] for row in result ]

        except Exception as e:
            print(f"Ошибка при получении названий кланов: {e}")
            return [ ]

    async def extract_emojis(text):
        emoji_pattern = re.compile(
            "["
            u"\U0001F600-\U0001F64F"  # Emoticons
            u"\U0001F300-\U0001F5FF"  # Symbols & Pictographs
            u"\U0001F680-\U0001F6FF"  # Transport & Map Symbols
            u"\U0001F1E0-\U0001F1FF"  # Flags
            u"\U00002500-\U00002BEF"  # Chinese & Japanese Characters
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            u"\U0001F926-\U0001FA9F"  # Supplemental Symbols and Pictographs
            u"\U0001F90C-\U0001F93A"
            u"\U0001F9E0-\U0001F9FF"
            "]+" , flags=re.UNICODE)
        return emoji_pattern.findall(text)

    async def exit_user_from_clan(self, emoji, user_id):
        print("[DEBUG] Запуск функции exit_user_from_clan.")
        print(f"[DEBUG] Параметры функции: emoji='{emoji}', user_id={user_id}")

        try:
            # Получаем список участников клана по эмодзи
            query = "SELECT members FROM clan WHERE emoji = $1"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query, emoji)

            if not result:
                print(f"[ERROR] Клан с эмодзи '{emoji}' не найден.")
                return "⚠️ Произошла ошибка: клан не найден."

            members = result['members']
            print(f"[DEBUG] Текущие участники клана: {members}")

            # Преобразуем строку участников в список
            members_list = members.split(',')
            print(f"[DEBUG] Преобразованный список участников: {members_list}")

            # Проверяем наличие пользователя в списке участников и удаляем его
            if str(user_id) in members_list:
                print(f"[DEBUG] Удаление пользователя с ID {user_id} из списка участников.")
                members_list.remove(str(user_id))
            else:
                print(f"[ERROR] Пользователь с ID {user_id} не найден в списке участников.")
                return "⚠️ Произошла ошибка: вы не состоите в этом клане."

            # Обновляем строку участников и базу данных
            new_members_str = ','.join(members_list)
            print(f"[DEBUG] Обновленный список участников: {new_members_str}")

            update_query = "UPDATE clan SET members = $1 WHERE emoji = $2"
            async with self.pool.acquire() as connection:
                await connection.execute(update_query, new_members_str, emoji)

            print("[DEBUG] Изменения сохранены в базе данных.")
            return "✅ Вы успешно покинули клан."

        except Exception as e:
            print(f"[ERROR] Произошла ошибка: {e}")
            return "⚠️ Произошла ошибка при обработке запроса."

    async def rename_clan(self, current_clan_name, new_clan_name):
        try:
            # Проверяем, существует ли клан с текущим названием
            query = "SELECT * FROM clan WHERE name = $1"
            async with self.pool.acquire() as connection:
                clan = await connection.fetchrow(query, current_clan_name)

            if not clan:
                # Клан с текущим названием не найден
                return f"⚠️ Клан с названием {current_clan_name} не найден."

            # Используем capitalize для приведения названия клана к нужному регистру
            new_clan_name = new_clan_name.capitalize()

            # Обновляем название клана в базе данных
            update_query = "UPDATE clan SET name = $1 WHERE name = $2"
            async with self.pool.acquire() as connection:
                await connection.execute(update_query, new_clan_name, current_clan_name)

            # Возвращаем сообщение об успешном переименовании клана
            return f"✅ Название клана успешно изменено на {new_clan_name}."

        except Exception as e:
            # Возвращаем сообщение об ошибке при переименовании клана
            return f"⚠️ Ошибка при переименовании клана: {str(e)}"

    async def get_clan_coins_by_emoji(self, clan_emoji):
        try:
            # Запрос для получения монет клана по эмодзи
            query = "SELECT coins FROM clan WHERE emoji = $1"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query, clan_emoji)

            if result:
                return result['coins']
            return 0

        except Exception as e:
            # Возвращаем 0 в случае ошибки
            return 0
    async def get_user_id_by_clan_emoji(self, clan_emoji):
        try:
            # Запрос для получения ID владельца клана по эмодзи
            query = "SELECT owner FROM clan WHERE emoji = $1"
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query, clan_emoji)

            if result:
                return result['owner']
            return None

        except Exception as e:
            # Возвращаем None в случае ошибки
            return None

    async def distribute_clan_points(self, clan_emoji, clan_coins):
        print("Распределение очков рейтинга начато...")

        # Получаем данные о всех кланах
        clans_data = await self.get_clans_data()
        total_clans = len(clans_data)

        if total_clans <= 1:
            print("Ошибка: Нет других кланов для распределения очков.")
            return "⚠️ Нет других кланов для распределения очков.", {}

        # Распределение очков рейтинга
        amount_per_clan = clan_coins / (total_clans - 1)  # Не учитываем удаляемый клан
        win_amount_rounded = round(amount_per_clan)
        formatted_win_amount = "{:,.0f}".format(win_amount_rounded).replace(',', '.')

        creators_to_notify = {}

        # Обновление балансов всех кланов
        for clan_emoji_db, clan_name_db, clan_balance in clans_data:
            if clan_emoji_db != clan_emoji:
                updated_balance = clan_balance + win_amount_rounded
                query_update = "UPDATE clan SET coins = $1 WHERE emoji = $2"
                async with self.pool.acquire() as connection:
                    await connection.execute(query_update, updated_balance, clan_emoji_db)
                creators_to_notify[clan_emoji_db] = (clan_name_db, win_amount_rounded)
                print(f"Очки рейтинга распределены: {formatted_win_amount} добавлено к клану {clan_name_db} ({clan_emoji_db}).")

        print("Все балансы обновлены в базе данных.")

        return f"Очки рейтинга распределены между другими кланами. Каждому клану начислено {formatted_win_amount}.", creators_to_notify, win_amount_rounded
    async def sell_clan(self, clan_emoji, owner_id, current_user_id):
        print("Продажа клана начата...")

        # Проверка владельца клана
        query = "SELECT owner, coins FROM clan WHERE emoji = $1"
        async with self.pool.acquire() as connection:
            clan_data = await connection.fetchrow(query, clan_emoji)

        if not clan_data:
            print("Ошибка: Клан не найден.")
            return "⚠️ Клан не найден.", {}

        owner_id_db, clan_coins = clan_data

        if owner_id != owner_id_db:
            print("Ошибка: Вы не являетесь создателем клана.")
            return "⚠️ Вы не являетесь создателем клана.", {}

        # Распределение очков рейтинга другим кланам
        response_message, creators_to_notify = await self.distribute_clan_points(clan_emoji, clan_coins)
        if response_message.startswith("⚠️"):
            return response_message, {}

        # Удаление клана из базы данных
        query_delete = "DELETE FROM clan WHERE emoji = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query_delete, clan_emoji)
        print(f"Клан с emoji '{clan_emoji}' успешно удален из базы данных.")

        return f"✅ Клан <code>{clan_emoji}</code> успешно удален. {response_message}", creators_to_notify








    async def get_all_clans(self):
        """
        Получает список всех кланов из базы данных.

        :return: Список словарей, представляющих кланы.
        """
        query = "SELECT name, owner, members, coins, items, emoji FROM clan"
        try:
            async with self.pool.acquire() as connection:
                clans = await connection.fetch(query)

            # Преобразуем результат запроса в список словарей
            clan_list = []
            if clans:
                for clan in clans:
                    # Преобразуем каждый результат в словарь
                    clan_dict = {
                        'name': clan['name'],  # Название клана
                        'owner': clan['owner'],  # Идентификатор владельца
                        'members': clan['members'],  # Список участников
                        'coins': clan['coins'],  # Казна клана
                        'items': clan['items'],  # Склад клана
                        'emoji': clan['emoji']  # Эмодзи клана
                    }
                    clan_list.append(clan_dict)

            return clan_list

        except Exception as e:
            print(f"Ошибка при выполнении запроса к базе данных: {e}")
            return []











    async def add_user_to_clan(self, clan_emoji, user_id):
        """Добавление пользователя в клан."""
        query = "SELECT members FROM clan WHERE emoji = $1"
        try:
            # Получаем текущих участников клана по эмодзи
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query, clan_emoji)

            if result:
                current_members = result['members']  # Получаем список участников клана

                # Добавляем нового пользователя к списку участников
                if current_members:
                    updated_members = f"{current_members},{user_id}"
                else:
                    updated_members = str(user_id)

                # Обновляем список участников клана в базе данных
                update_query = "UPDATE clan SET members = $1 WHERE emoji = $2"
                async with self.pool.acquire() as connection:
                    await connection.execute(update_query, updated_members, clan_emoji)
                print(f"[DEBUG] Пользователь {user_id} успешно добавлен в клан с эмодзи {clan_emoji}.")
                return f"✅ Пользователь с ID {user_id} был добавлен в клан {clan_emoji}."
            else:
                # Если клан не найден, сообщаем об этом
                print(f"[DEBUG] Клан с эмодзи '{clan_emoji}' не найден.")
                return "⚠️ Клан с таким эмодзи не найден."
        except Exception as e:
            print(f"[ERROR] Ошибка при добавлении пользователя в клан: {e}")
            return "⚠️ Произошла ошибка при добавлении пользователя в клан."





    async def user_in_clan(self, user_id):
        """Проверяет, находится ли пользователь в каком-либо клане.

        Возвращает True, если пользователь является лидером или участником клана,
        иначе False.
        """
        try:
            # Проверяем, является ли пользователь лидером клана
            query_leader = "SELECT 1 FROM clan WHERE owner = $1"
            async with self.pool.acquire() as connection:
                result_leader = await connection.fetchrow(query_leader, user_id)
            if result_leader:
                return True

            # Проверяем, является ли пользователь участником клана
            query_member = "SELECT 1 FROM clan WHERE $1 = ANY(members::text[])"
            async with self.pool.acquire() as connection:
                result_member = await connection.fetchrow(query_member, str(user_id))
            if result_member:
                return True

            return False
        except Exception as e:
            print(f"[ERROR] Ошибка при проверке пользователя в клане: {e}")
            return False














    async def clan_exists(self, name):
        """Проверяет, существует ли клан с заданным названием в базе данных."""
        try:
            async with self.pool.acquire() as connection:
                query = "SELECT 1 FROM clan WHERE name = $1"
                result = await connection.fetchrow(query, name)
                return result is not None
        except Exception as e:
            print(f"[ERROR] Ошибка при проверке существования клана: {e}")
            return False

    async def add_clan(self, name, owner, emojis):
        """Добавление нового клана в базу данных."""
        try:
            query = """
            INSERT INTO clan (name, owner, emoji, members, coins, items)
            VALUES ($1, $2, $3, '', 0, '{}')
            """
            # Выполнение асинхронного запроса
            async with self.pool.acquire() as connection:
                await connection.execute(query, name, owner, ''.join(emojis))
            print(f"Клан '{name}' добавлен в базу данных.")
        except Exception as e:
            print(f"Ошибка добавления клана в базу данных: {e}")



    async def set_full(self, name, new_name=None, owner=None, members=None, coins=None, items=None, emoji=None):
        """Обновляет информацию о клане."""
        updates = []
        params = []

        # Обновляем имя клана, если передано новое имя
        if new_name:
            updates.append("name = $1")
            params.append(new_name)
        # Обновляем владельца клана
        if owner:
            updates.append("owner = $2")
            params.append(owner)
        # Обновляем участников клана
        if members:
            updates.append("members = $3")
            params.append(members)
        # Обновляем количество монет
        if coins:
            updates.append("coins = $4")
            params.append(coins)
        # Обновляем список предметов
        if items:
            updates.append("items = $5")
            params.append(json.dumps(items))
        # Обновляем эмодзи клана
        if emoji:
            updates.append("emoji = $6")
            params.append(emoji)

        # Если есть что обновлять, формируем запрос и выполняем его
        if updates:
            updates_query = ", ".join(updates)
            params.append(name)  # Добавляем имя клана в конец списка параметров
            query = f"UPDATE clan SET {updates_query} WHERE name = $7"

            try:
                async with self.pool.acquire() as connection:
                    await connection.execute(query, *params)  # Передаем все параметры в запрос
                print(f"Клан '{name}' успешно обновлен.")
            except Exception as e:
                print(f"Ошибка обновления клана в базе данных: {e}")

    async def delete_clan(self, owner):
        """Удаляет клан по владельцу."""
        try:
            query = "DELETE FROM clan WHERE owner = $1"
            async with self.pool.acquire() as connection:
                await connection.execute(query, owner)  # Подставляем параметр владельца
            print(f"Клан с владельцем {owner} успешно удален.")
        except Exception as e:
            print(f"Ошибка при удалении клана: {e}")





    async def add_firstname_to_user(self, user_id, first_name):
        """Добавление первого имени пользователя в базу данных с очисткой от нежелательных символов."""
        # Исключаем символы < и > из строки first_name с помощью регулярного выражения
        cleaned_first_name = re.sub(r'[<>/{}"]', '', first_name)

        # Если после очистки символов < и > получается непустая строка, выполняем запрос
        if cleaned_first_name.strip():  # Проверяем, что строка не пустая после очистки
            try:
                # Выполняем запрос на обновление first_name
                async with self.pool.acquire() as connection:
                    await connection.execute(
                        "UPDATE users SET first_name = $1 WHERE user_id = $2",
                        cleaned_first_name, user_id
                    )
                print(f"Имя для пользователя {user_id} успешно обновлено.")
            except Exception as e:
                print(f"Ошибка при обновлении имени для пользователя {user_id}: {e}")
        else:
            print("Пустая строка после удаления символов < и >, запись в базу данных не выполняется.")














    async def get_shine_item(self):
        """Получает случайный предмет с бонусом shine (значение 1)"""
        try:
            # Запрос для получения предметов с shine = 1
            async with self.pool.acquire() as connection:
                result = await connection.fetch("SELECT name FROM dex WHERE shine = 1")

            # Если найдены предметы с бонусом 1
            if result:
                # Извлекаем названия предметов
                item_names = [item['name'] for item in result]

                # Выбираем случайное название
                selected_item = random.choice(item_names)
                return selected_item
            else:
                return "Нет предметов с shine 1"
        except Exception as e:
            print(f"Ошибка при запросе к базе данных: {e}")
            return "Ошибка при получении предметов с shine 1"

    async def get_shine_times(self , user_id):
        """Получение времени последнего открытия и data_open."""
        try:
            # Запрос на получение времени последнего открытия и data_open
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT last_open, data_open FROM shine WHERE user_id = $1" , user_id)

            # Возвращаем данные, если они найдены, или None, если нет
            if result:
                return result [ 'last_open' ] , result [ 'data_open' ]
            else:
                return None , None
        except Exception as e:
            print(f"Ошибка при запросе времени последнего открытия: {e}")
            return None , None

    async def add_shine(self , chat_id , chat_name , user_id , user_name , last_open , data_open):
        """
        Добавление записи о бонусе.
        :param chat_id: ID чата
        :param chat_name: имя чата
        :param user_id: ID пользователя
        :param user_name: имя пользователя
        :param last_open: дата и время последнего открытия (datetime)
        :param data_open: дата и время следующего открытия (datetime)
        """
        try:
            # Убедимся, что параметры last_open и data_open уже в нужном формате
            if isinstance(last_open , datetime):
                last_open = last_open.strftime('%Y-%m-%d %H:%M:%S')  # Преобразуем datetime в строку
            if isinstance(data_open , datetime):
                data_open = data_open.strftime('%Y-%m-%d %H:%M:%S')  # Преобразуем datetime в строку

            print(
                f"Передаем данные: chat_id={chat_id}, chat_name={chat_name}, user_id={user_id}, user_name={user_name}, last_open={last_open}, data_open={data_open}")

            async with self.pool.acquire() as connection:
                # Передаем данные в базе данных
                await connection.execute(
                    """
                    INSERT INTO shine (chat_id, chat_name, user_id, user_name, last_open, data_open)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """ , chat_id , chat_name , user_id , user_name , last_open , data_open)
            print(f"Бонус для пользователя {user_id} добавлен до {data_open}.")
        except Exception as e:
            print(f"Ошибка при добавлении бонуса: {str(e)}")
            print(
                f"Ошибка при добавлении записи с параметрами: chat_id={chat_id}, chat_name={chat_name}, user_id={user_id}, user_name={user_name}, last_open={last_open}, data_open={data_open}")
    async def update_bonus(self, user_id, last_open, data_open):
        """Обновление записи о бонусе."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос на обновление данных
                await connection.execute(
                    """
                    UPDATE bonus
                    SET last_open = $1, data_open = $2
                    WHERE user_id = $3
                    """,
                    last_open, data_open, user_id
                )
            print(f"Бонус обновлён для пользователя {user_id}.")
        except Exception as e:
            print(f"Ошибка при обновлении бонуса: {str(e)}")





    async def remove_user_shine(self, user_id):
        """Удаление пользователя из таблицы бонусов."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос на удаление пользователя
                await connection.execute(
                    "DELETE FROM shine WHERE user_id = $1",
                    user_id
                )
            print(f"Пользователь {user_id} удалён из таблицы бонусов.")
        except Exception as e:
            print(f"Ошибка при удалении пользователя: {str(e)}")

    async def remove_expired_shine(self):
        """Удаление устаревших shine."""
        # Получаем текущее время и преобразуем его в строку в формате 'YYYY-MM-DD HH:MM:SS'
        current_time = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос на удаление устаревших записей
                await connection.execute(
                    "DELETE FROM shine WHERE data_open < $1" , current_time  # Передаем строку с датой в нужном формате
                )
            print("Устаревшие shine удалены.")
        except Exception as e:
            print(f"Ошибка при удалении устаревших shine: {str(e)}")

    async def check_and_remove_expired_shine(self):
        """Проверка текущих сообщений пользователей и удаление устаревших бонусов."""
        current_time = time.time()  # Получаем текущее время

        try:
            async with self.pool.acquire() as connection:
                # Извлечение всех идентификаторов пользователей из таблицы bonus
                users_with_bonuses = await connection.fetch("SELECT user_id, data_open FROM shine")

            for user in users_with_bonuses:
                user_id = user [ 'user_id' ]  # Извлекаем user_id
                data_open = user [ 'data_open' ]  # Извлекаем data_open

                try:
                    # Преобразование строки в объект datetime
                    data_open_datetime = datetime.strptime(data_open , '%Y-%m-%d %H:%M:%S')
                    # Получение временной метки в секундах
                    data_open_timestamp = data_open_datetime.timestamp()

                    if data_open_timestamp < current_time:
                        await self.remove_user_shine(user_id)  # Удаление пользователя с устаревшим бонусом
                        print(f"[DEBUG] Устаревший бонус для пользователя {user_id} удалён.")
                except ValueError:
                    print(f"[ERROR] Неверный формат времени для пользователя {user_id}: {data_open}")

            # После проверки всех пользователей, удаление устаревших бонусов
            await self.remove_expired_shine()

        except Exception as e:
            print(f"[ERROR] Ошибка при проверке и удалении устаревших бонусов1: {str(e)}")

    async def add_shinebet(self , user_id , name , shine_amount , chat_id , chat_name , data):
        """Добавление записи о бонусе в таблицу bonusbet."""
        try:
            # Проверка типа данных для data
            if isinstance(data , datetime):
                # Если data - это datetime, преобразуем в строку
                data = data.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(data , float):
                # Если data - это Unix-время, преобразуем в целое число и потом в строку
                data = str(int(data))  # Преобразуем float в int, а затем в строку

            async with self.pool.acquire() as connection:
                await connection.execute(
                    """
                    INSERT INTO shinebet (user_id, name, shine, chat_id, chat_name, data)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """ , user_id , name , shine_amount , chat_id , chat_name , data)
            print(f"Запись о бонусе добавлена для пользователя {user_id} в чат {chat_name}.")
        except Exception as e:
            print(f"[ERROR] Ошибка при добавлении записи о бонусе: {str(e)}")

    async def get_name_by_user_id(self, user_id):
        """Получаем имя пользователя из таблицы users по user_id."""
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT first_name FROM users WHERE user_id = $1", user_id
                )
            return result['first_name'] if result else None
        except Exception as e:
            print(f"[ERROR] Ошибка при получении имени пользователя: {e}")
            return None

    async def get_items_with_shine_value(self, shine_value):
        """Получаем предметы с заданным значением shine из таблицы 'dex'."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос с параметром shine_value
                items = await connection.fetch(
                    "SELECT * FROM dex WHERE shine = $1", shine_value
                )
            return items  # Возвращаем список предметов
        except Exception as e:
            print(f"[ERROR] Ошибка при получении предметов с shine={shine_value}: {e}")
            return []













    async def get_bonus_item(self):
        """Получаем предмет с бонусом 1 из таблицы 'dex'."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для получения предметов с бонусом 1
                items_with_bonus = await connection.fetch("SELECT name FROM dex WHERE bonus = $1", 1)

            if items_with_bonus:
                # Извлекаем названия предметов
                item_names = [item['name'] for item in items_with_bonus]

                # Выбираем случайное название
                selected_item = random.choice(item_names)
                return selected_item
            else:
                return "Нет предметов с бонусом 1"
        except Exception as e:
            print(f"[ERROR] Ошибка при получении предмета с бонусом: {e}")
            return None

    async def get_bonus_times(self , user_id):
        """Получение времени последнего открытия и data_open."""
        try:
            # Проверка типа данных user_id перед использованием в запросе
            if not isinstance(user_id , (int , str)):  # Убедитесь, что это либо строка, либо число
                raise ValueError("user_id должен быть строкой или числом.")

            # Преобразуем user_id в число, если это строка
            if isinstance(user_id , str):
                user_id = int(user_id)  # Преобразуем строку в целое число

            async with self.pool.acquire() as connection:
                # Выполняем запрос для получения времени последнего открытия и data_open
                query = "SELECT last_open, data_open FROM bonus WHERE user_id = $1"
                result = await connection.fetchrow(query , user_id)

            if result:
                # Возвращаем полученные значения или (None, None) если данных нет
                return result [ 'last_open' ] , result [ 'data_open' ]
            else:
                return None , None
        except ValueError as e:
            print(f"[ERROR] Неверный тип user_id: {e}")
            return None , None
        except Exception as e:
            print(f"[ERROR] Ошибка при получении данных бонуса: {e}")
            return None , None

    async def get_ref_times(self , user_id , ref_id=None):
        """
        Получение last_open и data_open.
        Если передан ref_id - ищем по паре (user_id, ref_id).
        Если ref_id не задан - сохраняем поведение старой версии (по user_id).
        """
        try:
            # Нормализация типов
            if not isinstance(user_id , (int , str)):
                raise ValueError("user_id должен быть строкой или числом.")
            if isinstance(user_id , str):
                user_id = int(user_id)

            if ref_id is not None:
                if not isinstance(ref_id , (int , str)):
                    raise ValueError("ref_id должен быть строкой или числом.")
                if isinstance(ref_id , str):
                    ref_id = int(ref_id)

            async with self.pool.acquire() as connection:
                if ref_id is None:
                    result = await connection.fetchrow(
                        """
                        SELECT last_open, data_open
                        FROM refout
                        WHERE user_id = $1
                        ORDER BY data_open DESC
                        LIMIT 1
                        """ , user_id)
                else:
                    result = await connection.fetchrow(
                        """
                        SELECT last_open, data_open
                        FROM refout
                        WHERE user_id = $1 AND ref_id = $2
                        ORDER BY data_open DESC
                        LIMIT 1
                        """ , user_id , ref_id)

            if result:
                return result [ "last_open" ] , result [ "data_open" ]
            return None , None

        except ValueError as e:
            print(f"[ERROR] Неверный тип user_id/ref_id: {e}")
            return None , None
        except Exception as e:
            print(f"[ERROR] Ошибка при получении данных бонуса: {e}")
            return None , None

    async def is_user_registered(self , user_id) -> bool:
        """
        Проверяет, зарегистрирован ли пользователь по флагу `users.refout`.
        - 1  => зарегистрирован (True)
        - 0  или нет записи => не зарегистрирован (False)
        """
        try:
            # Нормализация типов
            if isinstance(user_id , str):
                user_id = int(user_id)
            elif not isinstance(user_id , int):
                raise ValueError("user_id должен быть строкой или числом.")

            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT usersref
                    FROM users
                    WHERE user_id = $1
                    LIMIT 1
                    """ , user_id)

            if not row:
                return False  # нет записи - считаем незарегистрированным

            # Приводим к int/bool на случай типов BOOLEAN/TEXT/INT
            val = row [ "usersref" ]
            try:
                return int(val) == 1
            except (TypeError , ValueError):
                return bool(val)

        except Exception as e:
            print(f"[ERROR] is_user_registered(user_id={user_id}): {e}")
            return False

    async def add_refout(self , user_id: int , ref_id: int , user_name: str , last_open , data_open):
        def _ensure_dt(dt):
            if isinstance(dt , datetime): return dt
            if isinstance(dt , (int , float)): return datetime.fromtimestamp(dt)
            if isinstance(dt , str): return datetime.strptime(dt , "%Y-%m-%d %H:%M:%S")
            raise ValueError(f"Неподдерживаемый тип даты: {type(dt)}")

        last_open_dt = _ensure_dt(last_open)
        data_open_dt = _ensure_dt(data_open)

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Блокируем строку пользователя, если есть
                    row = await conn.fetchrow(
                        "SELECT ref_id FROM refout WHERE user_id=$1 FOR UPDATE" , user_id)

                    if row is None:
                        # пользователя нет -> INSERT
                        await conn.execute(
                            """
                            INSERT INTO refout (user_id, ref_id, user_name, last_open, data_open)
                            VALUES ($1, $2, $3, $4, $5)
                            """ , user_id , ref_id , user_name , last_open_dt , data_open_dt)
                        print(f"[refout] ✅ Создана запись: user_id={user_id}, ref_id={ref_id}.")
                    else:
                        # пользователь есть -> сравниваем ref_id
                        # NULL-safe сравнение в SQL, чтобы не ловить кейсы с NULL
                        updated = await conn.execute(
                            """
                            UPDATE refout
                            SET ref_id = $2,
                                data_open = $3
                            WHERE user_id = $1
                              AND (ref_id IS DISTINCT FROM $2)
                            """ , user_id , ref_id , data_open_dt)
                        if updated.startswith("UPDATE 1"):
                            print(f"[refout] ♻️ Обновлён ref_id и data_open для user_id={user_id} → ref_id={ref_id}.")
                        else:
                            print(f"[refout] ➖ Без изменений: user_id={user_id}, ref_id уже {ref_id}.")
        except Exception as e:
            print(f"❌ Ошибка при add_refout(user_id={user_id}, ref_id={ref_id}): {e}")

    async def remove_user_refout(self, user_id):
        """Удаление пользователя из таблицы бонусов."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для удаления бонуса пользователя
                await connection.execute(
                    "DELETE FROM refout WHERE user_id = $1",
                    user_id
                )
                print(f"Пользователь {user_id} удалён из таблицы refout.")
        except Exception as e:
            print(f"Ошибка при удалении пользователя: {str(e)}")


    async def remove_expired_refout(self):
        """Удаление устаревших бонусов."""
        current_time = datetime.fromtimestamp(time.time())  # Преобразуем временную метку в datetime
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для удаления устаревших бонусов
                await connection.execute(
                    "DELETE FROM refout WHERE data_open < $1" ,  # Используем параметр для предотвращения SQL инъекций
                    current_time)
                print("Устаревшие бонусы удалены.")
        except Exception as e:
            print(f"Ошибка при удалении устаревших refout1: {str(e)}")
    async def add_bonus(self , chat_id , chat_name , user_id , user_name , last_open , data_open):
        """Добавление записи о бонусе."""
        try:
            # Преобразуем строки в datetime, если они являются строками
            if isinstance(last_open , str):
                last_open = datetime.strptime(last_open , "%Y-%m-%d %H:%M:%S")
            if isinstance(data_open , str):
                data_open = datetime.strptime(data_open , "%Y-%m-%d %H:%M:%S")

            async with self.pool.acquire() as connection:
                # Выполняем запрос для добавления бонуса
                await connection.execute(
                    """
                    INSERT INTO bonus (chat_id, chat_name, user_id, user_name, last_open, data_open)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """ , chat_id , chat_name , user_id , user_name , last_open , data_open)
                print(f"Бонус для пользователя {user_id} добавлен до {data_open}.")
        except Exception as e:
            print(f"Ошибка при добавлении бонуса: {str(e)}")

    async def add_historygames(self , *args) -> bool:
        """
        UPSERT записи historygames.

        Поддержка 2 форматов:

        A) await db.add_historygames(user_id, user_name, last_open, data_open)
        B) await db.add_historygames(chat_id, chat_name, user_id, user_name, last_open, data_open)

        ✅ Работает и без chat_id/chat_name (inline/private)
        ✅ ТОЧНО сохраняет: если запись есть - обновит, если нет - вставит.
        ✅ Если chat_id/chat_name не переданы - НЕ затирает старые значения в БД.
        """
        if not self.pool:
            print("[HISTORYGAMES][ERROR] Пул соединений не инициализирован (add_historygames).")
            return False

        # ---------- парсинг аргументов (4 или 6) ----------
        chat_id: Optional [ int ] = None
        chat_name: Optional [ str ] = None

        try:
            if len(args) == 4:
                # (user_id, user_name, last_open, data_open)
                user_id , user_name , last_open , data_open = args
            elif len(args) == 6:
                # (chat_id, chat_name, user_id, user_name, last_open, data_open)
                chat_id , chat_name , user_id , user_name , last_open , data_open = args
            else:
                print(f"[HISTORYGAMES][WARN] add_historygames: bad args count={len(args)} args={args!r}")
                return False

            uid = int(user_id)
        except Exception as e:
            print(f"[HISTORYGAMES][WARN] add_historygames: parse failed: {e} args={args!r}")
            return False

        # ---------- нормализация chat_id/chat_name ----------
        cid: Optional [ int ] = None
        try:
            if chat_id is not None:
                cid = int(chat_id)
        except Exception as e:
            print(f"[HISTORYGAMES][WARN] add_historygames: bad chat_id={chat_id!r}: {e}")
            cid = None

        cname: Optional [ str ] = None
        try:
            if chat_name:
                cname = str(chat_name).strip() or None
        except Exception as e:
            print(f"[HISTORYGAMES][WARN] add_historygames: bad chat_name={chat_name!r}: {e}")
            cname = None

        uname = str(user_name).strip() if user_name else ""
        if not uname:
            uname = "Игрок"

        # ---------- last_open / data_open -> datetime ----------
        def _to_dt(v: Any , label: str) -> datetime:
            try:
                if isinstance(v , (int , float)):
                    return datetime.fromtimestamp(float(v))
                if isinstance(v , str):
                    s = v.strip()
                    # основной формат
                    try:
                        return datetime.strptime(s , "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        # iso fallback
                        return datetime.fromisoformat(s.replace("Z" , "+00:00")).replace(tzinfo=None)
                if isinstance(v , datetime):
                    return v
                if hasattr(v , "timestamp"):
                    return v
            except Exception as e:
                print(f"[HISTORYGAMES][WARN] add_historygames: {label} parse failed: {e}")
            return datetime.now()

        last_open_dt = _to_dt(last_open , "last_open")
        data_open_dt = _to_dt(data_open , "data_open")

        # ---------- UPSERT ----------
        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    """
                    INSERT INTO historygames (chat_id, chat_name, user_id, user_name, last_open, data_open)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        -- ✅ не затираем чат, если его не передали
                        chat_id   = COALESCE(EXCLUDED.chat_id, historygames.chat_id),
                        chat_name = COALESCE(EXCLUDED.chat_name, historygames.chat_name),

                        user_name = EXCLUDED.user_name,
                        last_open = EXCLUDED.last_open,
                        data_open = EXCLUDED.data_open
                    RETURNING user_id, chat_id, chat_name, last_open, data_open
                    """ , cid , cname , uid , uname , last_open_dt , data_open_dt)

            if row:
                print(
                    "[HISTORYGAMES][OK] UPSERT saved: "
                    f"user_id={row [ 'user_id' ]} chat_id={row [ 'chat_id' ]} chat_name={row [ 'chat_name' ]} "
                    f"last_open={row [ 'last_open' ]} data_open={row [ 'data_open' ]}")
                return True

            print(f"[HISTORYGAMES][WARN] UPSERT вернул пусто: user_id={uid}")
            return False

        except Exception as e:
            print(f"[HISTORYGAMES][ERROR] add_historygames: {e}")
            return False


    async def get_historygames_times(self , user_id):
        """Получение времени последнего открытия и data_open."""
        try:
            # Проверка типа данных user_id перед использованием в запросе
            if not isinstance(user_id , (int , str)):  # Убедитесь, что это либо строка, либо число
                raise ValueError("user_id должен быть строкой или числом.")

            # Преобразуем user_id в число, если это строка
            if isinstance(user_id , str):
                user_id = int(user_id)  # Преобразуем строку в целое число

            async with self.pool.acquire() as connection:
                # Выполняем запрос для получения времени последнего открытия и data_open
                query = "SELECT last_open, data_open FROM historygames WHERE user_id = $1"
                result = await connection.fetchrow(query , user_id)

            if result:
                # Возвращаем полученные значения или (None, None) если данных нет
                return result [ 'last_open' ] , result [ 'data_open' ]
            else:
                return None , None
        except ValueError as e:
            print(f"[ERROR] Неверный тип user_id: {e}")
            return None , None
        except Exception as e:
            print(f"[ERROR] Ошибка при получении данных бонуса: {e}")
            return None , None

    async def update_historygames(self , user_id , last_open , data_open):
        """Обновление записи о бонусе для пользователя."""
        try:
            # Преобразуем строки в datetime, если они являются строками
            if isinstance(last_open , str):
                last_open = datetime.strptime(last_open , "%Y-%m-%d %H:%M:%S")
            if isinstance(data_open , str):
                data_open = datetime.strptime(data_open , "%Y-%m-%d %H:%M:%S")

            async with self.pool.acquire() as connection:
                # Выполняем запрос для обновления данных бонуса
                await connection.execute(
                    """
                    UPDATE historygames
                    SET last_open = $1, data_open = $2
                    WHERE user_id = $3
                    """ , last_open , data_open , user_id)
                print(f"Бонус для пользователя {user_id} обновлен до {data_open}.")
        except Exception as e:
            print(f"Ошибка при обновлении бонуса: {str(e)}")

    async def remove_user_historygames(self, user_id):
        """Удаление пользователя из таблицы бонусов."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для удаления бонуса пользователя
                await connection.execute(
                    "DELETE FROM historygames WHERE user_id = $1",
                    user_id
                )
                print(f"Пользователь {user_id} удалён из таблицы бонусов.")
        except Exception as e:
            print(f"Ошибка при удалении пользователя: {str(e)}")
    async def remove_user_bonus(self, user_id):
        """Удаление пользователя из таблицы бонусов."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для удаления бонуса пользователя
                await connection.execute(
                    "DELETE FROM bonus WHERE user_id = $1",
                    user_id
                )
                print(f"Пользователь {user_id} удалён из таблицы бонусов.")
        except Exception as e:
            print(f"Ошибка при удалении пользователя: {str(e)}")

    async def remove_user_cache(self, user_id):
        """Удаление пользователя из таблицы cache."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для удаления записи из таблицы cache
                await connection.execute(
                    "DELETE FROM cache WHERE user_id = $1",
                    user_id
                )
                print(f"Пользователь {user_id} удалён из таблицы cache.")
        except Exception as e:
            print(f"Ошибка при удалении пользователя из cache: {str(e)}")

    async def remove_expired_bonuses(self):
        """Удаление устаревших бонусов."""
        current_time = datetime.fromtimestamp(time.time())  # Преобразуем временную метку в datetime
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для удаления устаревших бонусов
                await connection.execute(
                    "DELETE FROM bonus WHERE data_open < $1" ,  # Используем параметр для предотвращения SQL инъекций
                    current_time)
                print("Устаревшие бонусы удалены.")
        except Exception as e:
            print(f"Ошибка при удалении устаревших бонусов1: {str(e)}")

    async def remove_expired_historygames(self):
        """Удаление устаревших бонусов."""
        current_time = datetime.fromtimestamp(time.time())  # Преобразуем временную метку в datetime
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для удаления устаревших бонусов
                await connection.execute(
                    "DELETE FROM historygames WHERE data_open < $1" ,
                    # Используем параметр для предотвращения SQL инъекций
                    current_time)
                print("Устаревшие бонусы удалены.")
        except Exception as e:
            print(f"Ошибка при удалении устаревших бонусов1: {str(e)}")

        # Удаление всех устаревших бонусов из таблицы
        #await self.remove_expired_cache()

    async def check_and_remove_expired_bonuses(self):
        """Проверка текущих сообщений пользователей и удаление устаревших бонусов."""
        current_time = time.time()  # Получаем текущее время

        try:
            # Извлечение всех идентификаторов пользователей из таблицы bonus
            async with self.pool.acquire() as connection:
                result = await connection.fetch("SELECT user_id, data_open FROM bonus")
                users_with_bonuses = result

                for user in users_with_bonuses:
                    user_id = user [ 'user_id' ]  # Извлекаем user_id из результата
                    data_open = user [ 'data_open' ]  # Извлекаем data_open из результата

                    try:
                        # Если data_open уже является объектом datetime, получаем временную метку
                        if isinstance(data_open , datetime):
                            data_open_timestamp = data_open.timestamp()
                        else:
                            # Если это строка, преобразуем с использованием нужного формата
                            data_open_datetime = datetime.strptime(data_open , '%d.%m.%Y %H:%M')
                            data_open_timestamp = data_open_datetime.timestamp()

                        if data_open_timestamp < current_time:
                            await self.remove_user_bonus(user_id)  # Удаление пользователя с устаревшим бонусом
                            print(f"[DEBUG] Устаревший бонус для пользователя {user_id} удалён.")
                    except ValueError:
                        print(f"[ERROR] Неверный формат времени для пользователя {user_id}: {data_open}")

            # Удаление всех устаревших бонусов из таблицы
            await self.remove_expired_bonuses()

        except Exception as e:
            print(f"[ERROR] Ошибка при проверке и удалении устаревших бонусов2: {str(e)}")


    async def check_and_remove_expired_historygames(self):
        """Проверка текущих сообщений пользователей и удаление устаревших бонусов."""
        current_time = time.time()  # Получаем текущее время

        try:
            # Извлечение всех идентификаторов пользователей из таблицы bonus
            async with self.pool.acquire() as connection:
                result = await connection.fetch("SELECT user_id, data_open FROM historygames")
                users_with_bonuses = result

                for user in users_with_bonuses:
                    user_id = user [ 'user_id' ]  # Извлекаем user_id из результата
                    data_open = user [ 'data_open' ]  # Извлекаем data_open из результата

                    try:
                        # Если data_open уже является объектом datetime, получаем временную метку
                        if isinstance(data_open , datetime):
                            data_open_timestamp = data_open.timestamp()
                        else:
                            # Если это строка, преобразуем с использованием нужного формата
                            data_open_datetime = datetime.strptime(data_open , '%d.%m.%Y %H:%M')
                            data_open_timestamp = data_open_datetime.timestamp()

                        if data_open_timestamp < current_time:
                            await self.remove_user_historygames(user_id)  # Удаление пользователя с устаревшим бонусом
                            print(f"[DEBUG] Устаревший бонус для пользователя {user_id} удалён.")
                    except ValueError:
                        print(f"[ERROR] Неверный формат времени для пользователя {user_id}: {data_open}")

            # Удаление всех устаревших бонусов из таблицы
            await self.remove_expired_historygames()

        except Exception as e:
            print(f"[ERROR] Ошибка при проверке и удалении устаревших бонусов2: {str(e)}")

    async def add_bonusbet(self, user_id, name, bonus_amount, chat_id, chat_name, data):
        """Добавление записи о бонусе в таблицу bonusbet."""
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(
                    """
                    INSERT INTO bonusbet (user_id, name, bonus, chat_id, chat_name, data)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    user_id, name, bonus_amount, chat_id, chat_name, data
                )
                print(f"Запись о бонусе добавлена для пользователя {user_id} в чат {chat_name}.")
        except Exception as e:
            print(f"Ошибка при добавлении записи о бонусе: {str(e)}")











    async def add_user(self, user_id):
        """Добавление пользователя в таблицу бонусов."""
        current_time = int(time.time())
        try:
            async with self.pool.acquire() as connection:
                # Выполнение асинхронного запроса с параметризированными значениями
                await connection.execute(
                    "INSERT INTO bonus (user_id, last_open) VALUES ($1, $2)",
                    user_id, current_time
                )
                print(f"Пользователь {user_id} добавлен в таблицу бонусов.")
        except Exception as e:
            print(f"Ошибка при добавлении пользователя: {str(e)}")








































    async def delete_row_after_delay(self, row_data):
        """Удаление строки после задержки."""
        await asyncio.sleep(864000)  # Ждем 10 дней
        try:
            # Формируем запрос с параметризацией
            query = f"DELETE FROM moneykommi WHERE user_id=$1 AND {row_data[2]}=$2 AND datetime=$3"
            async with self.pool.acquire() as connection:
                await connection.execute(query, row_data[0], row_data[1], row_data[3])
            print("Строка удалена из таблицы:", row_data)
        except Exception as e:
            print(f"Ошибка при удалении строки: {str(e)}")

    async def create_user_in_achiv(self, user_id):
        """Добавление пользователя в таблицу 'moneyachiv'."""
        try:
            # Формируем запрос с параметризацией
            query = "INSERT INTO moneyachiv (user_id) VALUES ($1)"
            async with self.pool.acquire() as connection:
                await connection.execute(query, user_id)
            print(f"Пользователь {user_id} добавлен в таблицу 'moneyachiv'.")
        except Exception as e:
            print(f"Ошибка при добавлении пользователя: {str(e)}")

    async def add_commission(self, user_id, commission, winner):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'kube' if winner == 'user' else 'kubelose'

        async with self.pool.acquire() as connection:
            # Проверяем наличие пользователя в таблице moneyachiv
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            # Если пользователя нет в таблице moneyachiv, добавляем его
            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись о комиссии в moneykommi
            insert_commission_query = f"INSERT INTO moneykommi (user_id, {game}, datetime) VALUES ($1, $2, $3)"
            await connection.execute(insert_commission_query, user_id, commission, current_time)

            # Обновляем количество выигрышей для пользователя
            update_query = f"UPDATE moneyachiv SET {game} = {game} + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

            # Запускаем асинхронную задачу для удаления строки позже
            asyncio.create_task(self.delete_row_after_delay(connection, user_id, commission, game, current_time))

    async def add_commissionboul(self, user_id, commission, winner):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'boul' if winner == 'user' else 'boullose'

        async with self.pool.acquire() as connection:
            # Проверяем наличие пользователя в таблице moneyachiv
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            # Если пользователя нет в таблице moneyachiv, добавляем его
            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись о комиссии в moneykommi
            insert_commission_query = f"INSERT INTO moneykommi (user_id, {game}, datetime) VALUES ($1, $2, $3)"
            await connection.execute(insert_commission_query, user_id, commission, current_time)

            # Обновляем количество выигрышей для пользователя
            update_query = f"UPDATE moneyachiv SET {game} = {game} + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

            # Запускаем асинхронную задачу для удаления строки позже
            asyncio.create_task(self.delete_row_after_delay(connection, user_id, commission, game, current_time))


    async def add_commissionbasket(self, user_id, commission, winner):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'basket' if winner == 'user' else 'basketlose'

        async with self.pool.acquire() as connection:
            # Проверяем наличие пользователя в таблице moneyachiv
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            # Если пользователя нет в таблице moneyachiv, добавляем его
            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись о комиссии в moneykommi
            insert_commission_query = f"INSERT INTO moneykommi (user_id, {game}, datetime) VALUES ($1, $2, $3)"
            await connection.execute(insert_commission_query, user_id, commission, current_time)

            # Обновляем количество выигрышей для пользователя
            update_query = f"UPDATE moneyachiv SET {game} = {game} + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

            # Запускаем асинхронную задачу для удаления строки позже
            asyncio.create_task(self.delete_row_after_delay(connection, user_id, commission, game, current_time))

    async def add_commissionslots(self , user_id , commission , winner):
        """Добавляет комиссию за игру в слотах и обновляет информацию о пользователе."""

        # Проверяем, был ли инициализирован пул соединений
        if self.pool is None:
            raise Exception("Пул соединений не инициализирован. Пожалуйста, инициализируйте пул перед использованием.")

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'slots' if winner == 'user' else 'slotslose'

        try:
            # Получаем соединение из пула
            async with self.pool.acquire() as connection:
                # Проверяем наличие пользователя в таблице moneyachiv
                user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
                user_exists = await connection.fetchval(user_exists_query , user_id)

                # Если пользователя нет в таблице moneyachiv, добавляем его
                if not user_exists:
                    await self.create_user_in_achiv(user_id)

                # Вставляем запись о комиссии в moneykommi
                insert_commission_query = f"INSERT INTO moneykommi (user_id, {game}, datetime) VALUES ($1, $2, $3)"
                await connection.execute(insert_commission_query , user_id , commission , current_time)

                # Обновляем количество выигрышей для пользователя
                update_query = f"UPDATE moneyachiv SET {game} = {game} + 1 WHERE user_id = $1"
                await connection.execute(update_query , user_id)

                # Запускаем асинхронную задачу для удаления строки позже
                asyncio.create_task(
                    self.delete_row_after_delay(connection , user_id , commission , game , current_time))

        except Exception as e:
            print(f"Ошибка при работе с базой данных: {e}")
            raise


    async def add_commissiontrade(self, user_id, commission, winner):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'trade' if winner == 'user' else 'tradelose'

        async with self.pool.acquire() as connection:
            # Проверяем наличие пользователя в таблице moneyachiv
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            # Если пользователя нет в таблице moneyachiv, добавляем его
            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись о комиссии в moneykommi
            insert_commission_query = f"INSERT INTO moneykommi (user_id, {game}, datetime) VALUES ($1, $2, $3)"
            await connection.execute(insert_commission_query, user_id, commission, current_time)

            # Обновляем количество выигрышей для пользователя
            update_query = f"UPDATE moneyachiv SET {game} = {game} + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

            # Запускаем асинхронную задачу для удаления строки позже
            asyncio.create_task(self.delete_row_after_delay(connection, user_id, commission, game, current_time))


    async def add_commissioncrash(self, user_id, commission, winner):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'crash' if winner == 'user' else 'crashlose'

        async with self.pool.acquire() as connection:
            # Проверяем наличие пользователя в таблице moneyachiv
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            # Если пользователя нет в таблице moneyachiv, добавляем его
            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись о комиссии в moneykommi
            insert_commission_query = f"INSERT INTO moneykommi (user_id, {game}, datetime) VALUES ($1, $2, $3)"
            await connection.execute(insert_commission_query, user_id, commission, current_time)

            # Обновляем количество выигрышей для пользователя
            update_query = f"UPDATE moneyachiv SET crash = crash + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

            # Запускаем асинхронную задачу для удаления строки позже
            asyncio.create_task(self.delete_row_after_delay(connection, user_id, commission, game, current_time))



    async def add_commissiontank(self, user_id, commission, winner):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'tank' if winner == 'user' else 'tanklose'

        async with self.pool.acquire() as connection:
            # Проверяем наличие пользователя в таблице moneyachiv
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            # Если пользователя нет в таблице moneyachiv, добавляем его
            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись о комиссии в moneykommi
            insert_commission_query = f"INSERT INTO moneykommi (user_id, {game}, datetime) VALUES ($1, $2, $3)"
            await connection.execute(insert_commission_query, user_id, commission, current_time)

            # Обновляем количество выигрышей для пользователя
            update_query = f"UPDATE moneyachiv SET tank = tank + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

            # Запускаем асинхронную задачу для удаления строки позже
            asyncio.create_task(self.delete_row_after_delay(connection, user_id, commission, game, current_time))

    async def add_commissionbombs(self, user_id, commission, winner):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'bombs' if winner == 'user' else 'bombslose'

        async with self.pool.acquire() as connection:
            # Check if the user exists in the 'moneyachiv' table
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            # If the user does not exist, create them in 'moneyachiv'
            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Insert commission record into 'moneykommi'
            insert_commission_query = f"INSERT INTO moneykommi (user_id, {game}, datetime) VALUES ($1, $2, $3)"
            await connection.execute(insert_commission_query, user_id, commission, current_time)

            # Update the user's 'bombs' count
            update_query = f"UPDATE moneyachiv SET bombs = bombs + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

            # Create an asynchronous task to delete the record after a delay
            asyncio.create_task(self.delete_row_after_delay(connection, user_id, commission, game, current_time))

    async def add_commissionrisk(self, user_id, commission, winner):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'risk' if winner == 'user' else 'risklose'

        async with self.pool.acquire() as connection:
            # Check if the user exists in the 'moneyachiv' table
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            # If the user does not exist, create them in 'moneyachiv'
            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Insert commission record into 'moneykommi'
            insert_commission_query = f"INSERT INTO moneykommi (user_id, {game}, datetime) VALUES ($1, $2, $3)"
            await connection.execute(insert_commission_query, user_id, commission, current_time)

            # Update the user's 'risk' count
            update_query = f"UPDATE moneyachiv SET risk = risk + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

            # Create an asynchronous task to delete the record after a delay
            asyncio.create_task(self.delete_row_after_delay(connection, user_id, commission, game, current_time))


    async def add_commissionplate(self, user_id, commission, winner):
        """
        Добавление записи в таблицу `moneykommi` и обновление таблицы `moneyachiv`.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'plate' if winner == 'user' else 'platelose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Добавляем запись в таблицу `moneykommi`
            insert_query = f"""
                INSERT INTO moneykommi (user_id, {game}, datetime) 
                VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, commission, current_time)

            # Обновляем поле `plate` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET plate = plate + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, commission, game, current_time))

    async def add_commissionroul(self, user_id, commission, winner):
        """
        Добавление записи в таблицу `moneykommi` и обновление таблицы `moneyachiv` для игры roulette.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'roul' if winner == 'user' else 'roullose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Добавляем запись в таблицу `moneykommi`
            insert_query = f"""
                INSERT INTO moneykommi (user_id, {game}, datetime) 
                VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, commission, current_time)

            # Обновляем поле `roul` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET roul = roul + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, commission, game, current_time))

    async def add_commissionkazik(self, user_id, commission, winner):
        """
        Добавление записи в таблицу `moneykommi` и обновление таблицы `moneyachiv` для игры казик.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'kazik' if winner == 'user' else 'kaziklose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Добавляем запись в таблицу `moneykommi`
            insert_query = f"""
                INSERT INTO moneykommi (user_id, {game}, datetime) 
                VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, commission, current_time)

            # Обновляем поле `kazik` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET kazik = kazik + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, commission, game, current_time))

    async def add_commissionblack(self, user_id):
        """
        Увеличивает счетчик для игры `black` в таблице `moneyachiv`.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Обновляем поле `black` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET black = black + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой (в данном случае время используется для будущего функционала)
        asyncio.create_task(self.delete_row_after_delay(user_id, current_time))


    async def add_commissionlot(self, user_id, commission, winner):
        """
        Добавляет запись о комиссии и обновляет статистику для игры `lot`.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'lot' if winner == 'user' else 'lotlose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, commission, current_time)

            # Обновляем счетчик `lot` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET lot = lot + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, commission, game, current_time))

    async def add_commissionball(self , user_id , commission , winner):
        """
        Добавляет запись о комиссии и обновляет статистику для игры `ball`.
        """
        # Создаем объект времени с временной зоной UTC
        current_time = datetime.now(timezone.utc)
        game = 'ball' if winner == 'user' else 'balllose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query , user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query , user_id , commission , current_time)

            # Обновляем счетчик `ball` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET ball = ball + 1 WHERE user_id = $1"
            await connection.execute(update_query , user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id , commission , game , current_time))
    async def add_commissionknb(self , user_id , commission , winner):
        """
        Добавляет запись о комиссии и обновляет статистику для игры `knb`.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'knb' if winner == 'user' else 'knblose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query , user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query , user_id , commission , current_time)

            # Обновляем счетчик `knb` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET knb = knb + 1 WHERE user_id = $1"
            await connection.execute(update_query , user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id , commission , game , current_time))
    async def add_commissionbk(self, user_id, commission, winner):
        """
        Добавляет запись о комиссии и обновляет статистику для игры `bk`.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'bk' if winner == 'user' else 'bklose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, commission, current_time)

            # Обновляем счетчик `bk` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET bk = bk + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, commission, game, current_time))

    async def add_commissionorel(self, user_id, commission, winner):
        """
        Добавляет запись о комиссии для игры `orel` и обновляет статистику.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'orel' if winner == 'user' else 'orellose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, commission, current_time)

            # Обновляем счетчик `orel` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET orel = orel + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, commission, game, current_time))

    async def add_commissiondart(self, user_id, commission, winner):
        """
        Добавляет запись о комиссии для игры `dart` и обновляет статистику.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'dart' if winner == 'user' else 'dartlose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, commission, current_time)

            # Обновляем счетчик `dart` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET dart = dart + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, commission, game, current_time))

    async def add_commissionfoot(self, user_id, commission, winner):
        """
        Добавляет запись о комиссии для игры `foot` и обновляет статистику.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'foot' if winner == 'user' else 'footlose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, commission, current_time)

            # Обновляем счетчик `foot` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET foot = foot + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, commission, game, current_time))

    async def add_commissionbingo(self, user_id, amount, winner):
        """
        Добавляет запись о комиссии для игры `bingo` и обновляет статистику.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'bingo' if winner == 'user' else 'bingolose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, amount, current_time)

            # Обновляем счетчик `bingo` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET bingo = bingo + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, amount, game, current_time))


    async def add_commission1rulet(self, user_id, amount, winner):
        """
        Добавляет запись о комиссии для игры `rulet` и обновляет статистику.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'rulet' if winner == 'user' else 'ruletlose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, amount, current_time)

            # Обновляем счетчик `rulet` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET rulet = rulet + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, amount, game, current_time))

    async def add_commissionkosti(self, user_id, amount, winner):
        """
        Добавляет запись о комиссии для игры `kosti` и обновляет статистику.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'kosti' if winner == 'user' else 'kostilose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, amount, current_time)

            # Обновляем счетчик `kosti` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET kosti = kosti + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, amount, game, current_time))



    async def add_commissionreshka(self, user_id, amount, winner):
        """
        Добавляет запись о комиссии для игры `reshka` и обновляет статистику.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'reshka' if winner == 'user' else 'reshkalose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, amount, current_time)

            # Обновляем счетчик `reshka` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET reshka = reshka + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, amount, game, current_time))



    async def add_commissiondue(self, user_id, amount, winner):
        """
        Добавляет запись о комиссии для игры `due` и обновляет статистику.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'due' if winner == 'user' else 'duelose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, amount, current_time)

            # Обновляем счетчик `due` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET due = due + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, amount, game, current_time))


    async def add_commissionmine(self, user_id, commission, winner):
        """
        Добавляет запись о комиссии для игры `mine` и обновляет статистику.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game = 'mine' if winner == 'user' else 'minelose'

        async with self.pool.acquire() as connection:
            # Проверяем, существует ли пользователь
            user_exists_query = "SELECT COUNT(*) FROM moneyachiv WHERE user_id = $1"
            user_exists = await connection.fetchval(user_exists_query, user_id)

            if not user_exists:
                await self.create_user_in_achiv(user_id)

            # Вставляем запись в таблицу `moneykommi`
            insert_query = f"""
            INSERT INTO moneykommi (user_id, {game}, datetime)
            VALUES ($1, $2, $3)
            """
            await connection.execute(insert_query, user_id, commission, current_time)

            # Обновляем счетчик `mine` в таблице `moneyachiv`
            update_query = "UPDATE moneyachiv SET mine = mine + 1 WHERE user_id = $1"
            await connection.execute(update_query, user_id)

        # Создаем задачу для удаления строки с задержкой
        asyncio.create_task(self.delete_row_after_delay(user_id, commission, game, current_time))

    async def get_sum_by_user_id(self , column_name):
        """
        Получает сумму значений для указанного столбца в таблице `moneykommi`.
        """
        query = f"SELECT SUM({column_name}) FROM moneykommi"

        async with self.pool.acquire() as connection:
            result = await connection.fetchval(query)
            return result if result is not None else 0

    async def get_rep_plus(self , user_id):
        """
        Получаем количество плюсов репутации для указанного пользователя.
        """
        query = "SELECT rep_plus FROM users WHERE user_id = $1"

        async with self.pool.acquire() as connection:
            try:
                # Выполняем запрос и получаем результат
                rep_plus = await connection.fetchval(query , user_id)

                if rep_plus is None:
                    return 0  # Если запись отсутствует, возвращаем 0
                return rep_plus  # Возвращаем количество плюсов репутации
            except Exception as e:
                print(f"Ошибка при получении репутации (плюсы) для пользователя: {e}")
                return 0  # В случае ошибки возвращаем 0

    async def get_rep_minus(self , user_id):
        """
        Получаем количество минусов репутации для указанного пользователя.
        """
        query = "SELECT rep_minus FROM users WHERE user_id = $1"

        async with self.pool.acquire() as connection:
            try:
                # Выполняем запрос и получаем результат
                rep_minus = await connection.fetchval(query , user_id)

                if rep_minus is None:
                    return 0  # Если запись отсутствует, возвращаем 0
                return rep_minus  # Возвращаем количество минусов репутации
            except Exception as e:
                print(f"Ошибка при получении репутации (минусы) для пользователя: {e}")
                return 0  # В случае ошибки возвращаем 0

    async def get_reputation_by_user_id(self , user_id):
        """
        Получаем репутацию пользователя по его user_id.
        """
        query = "SELECT rep1 FROM rep WHERE user_id = $1"

        async with self.pool.acquire() as connection:
            try:
                # Выполняем запрос и получаем результат
                result = await connection.fetchval(query , user_id)

                # Если результат пустой, возвращаем "0", иначе возвращаем репутацию
                return result if result else "0"
            except Exception as e:
                print(f"Ошибка при получении репутации для пользователя: {e}")
                return "0"  # В случае ошибки возвращаем "0"

    async def update_rep_plus(self , user_id , amount):
        """
        Обновляем репутацию пользователя, увеличив на заданное количество.
        """
        query_select = "SELECT rep_plus FROM users WHERE user_id = $1"
        query_update = "UPDATE users SET rep_plus = $1 WHERE user_id = $2"

        async with self.pool.acquire() as connection:
            try:
                # Получаем текущую репутацию пользователя
                current_rep = await connection.fetchval(query_select , user_id)

                if current_rep is None:
                    current_rep = 0  # Если запись отсутствует, начинаем с 0

                # Рассчитываем новую репутацию
                new_rep = current_rep + amount

                # Обновляем репутацию пользователя в базе данных
                await connection.execute(query_update , new_rep , user_id)

            except Exception as e:
                print(f"Ошибка при обновлении репутации пользователя: {e}")

    async def update_rep_minus(self , user_id , amount):
        """
        Обновляем репутацию пользователя, уменьшая на заданное количество.
        """
        query_select = "SELECT rep_minus FROM users WHERE user_id = $1"
        query_update = "UPDATE users SET rep_minus = $1 WHERE user_id = $2"

        async with self.pool.acquire() as connection:
            try:
                # Получаем текущую репутацию пользователя
                current_rep = await connection.fetchval(query_select , user_id)

                if current_rep is None:
                    current_rep = 0  # Если запись отсутствует, начинаем с 0

                # Рассчитываем новую репутацию
                new_rep = current_rep - amount

                # Обновляем репутацию пользователя в базе данных
                await connection.execute(query_update , new_rep , user_id)

            except Exception as e:
                print(f"Ошибка при обновлении репутации (минусы) пользователя: {e}")

    #def get_chat_id(self , user_id):
        # Assuming you have a table named 'users' where user_id and chat_id are stored
        #self.cursor.execute('''SELECT chat_id FROM users WHERE user_id = ?''' , (user_id ,))
        #result = self.cursor.fetchone()
        #if result:
            #return result [ 0 ]
        #else:
            #return None

    async def get_rep(self , user_id):
        """
        Получаем репутацию пользователя из таблицы rep.
        """
        query = "SELECT rep1 FROM rep WHERE user_id = $1"

        async with self.pool.acquire() as connection:
            try:
                # Выполняем запрос и получаем результат
                result = await connection.fetchval(query , user_id)

                # Если результат найден, возвращаем репутацию, иначе None
                return result if result is not None else None
            except Exception as e:
                print(f"Ошибка при получении репутации: {e}")
                return None

    async def is_vip_user(self , user_id):
        """
        Проверяем, является ли пользователь VIP.
        """
        query = "SELECT vip FROM users WHERE user_id = $1"

        async with self.pool.acquire() as connection:
            try:
                # Выполняем запрос и получаем значение
                vip_status = await connection.fetchval(query , user_id)

                # Возвращаем True, если vip_status существует и равен 1, иначе False
                return bool(vip_status) if vip_status is not None else False
            except Exception as e:
                print(f"Ошибка при проверке статуса VIP пользователя: {e}")
                return False

    async def update_user_style(self , user_id , style_number):
        query = "UPDATE users SET style = $1 WHERE user_id = $2"

        async with self.pool.acquire() as connection:
            try:
                # Выполняем обновление стиля пользователя
                await connection.execute(query , style_number , user_id)
                print(f"Стиль пользователя с ID {user_id} обновлён на {style_number}.")
            except Exception as e:
                print(f"Ошибка при обновлении стиля пользователя: {e}")


    async def get_user_style(self, user_id):
        query = "SELECT style FROM users WHERE user_id = $1"

        async with self.pool.acquire() as connection:
            try:
                # Выполняем запрос и получаем результат
                result = await connection.fetchrow(query, user_id)
                return result['style'] if result else None  # Возвращаем стиль или None, если результат пустой
            except Exception as e:
                print(f"Ошибка при получении стиля пользователя: {e}")
                return None

    async def get_style_price(self , style_number):
        query = "SELECT price FROM styles WHERE style_number = $1"

        async with self.pool.acquire() as connection:
            try:
                result = await connection.fetchrow(query , style_number)
                if result:
                    return result [ 'price' ]  # Возвращаем цену, если стиль найден
                else:
                    return None  # Если стиль не найден
            except Exception as e:
                print(f"Ошибка при получении цены стиля: {e}")
                return None

    async def buy_style(self, user_id: int, style_number: int) -> str:
        """
        Покупка стиля для пользователя.
        """
        # Получаем баланс пользователя
        user_balance = await self.get_user_balance(user_id)
        if user_balance is None:
            return "Ошибка: пользователь не найден"

        # Получаем цену стиля
        style_price = await self.get_style_price(style_number)
        if style_price is None:
            return "Ошибка: стиль не найден"

        # Проверяем VIP статус пользователя
        is_vip = await self.is_vip_user(user_id)

        if is_vip:
            # Если пользователь VIP, меняем стиль бесплатно
            await self.update_user_style(user_id, style_number)
            return "Стиль успешно изменен (бесплатно)"

        # Для обычных пользователей проверяем баланс
        if user_balance < style_price:
            return "Недостаточно Ктк для покупки стиля"  # Баланс ниже цены

        # Обновляем баланс и стиль
        new_balance = user_balance - style_price
        await self.update_user_balance(user_id, new_balance)
        await self.update_user_style(user_id, style_number)
        return "Стиль успешно приобретен"

    async def buy_style_with_money(self, user_id: int, style_number: int) -> str:
        # Получаем баланс пользователя
        user_balance = await self.get_user_balance(user_id)
        if user_balance is None:
            return "Пользователь не найден"

        # Получаем цену стиля
        style_price = await self.get_style_price(style_number)
        if style_price is None:
            return "Стиль не найден"

        # Проверяем, использует ли пользователь уже этот стиль
        current_style = await self.get_user_style(user_id)
        if current_style == style_number:
            return "Этот стиль уже используется"

        # Проверяем, есть ли достаточно средств
        if user_balance < style_price:
            return "Недостаточно Ктк для покупки"

        # Обновляем стиль пользователя
        await self.update_user_style(user_id, style_number)
        return "Стиль успешно приобретен"











#shop
# shop
# shop
# shop
    async def get_user_flag(self, user_id: int) -> Optional[str]:
        """Проверяет, есть ли у пользователя флаг (страна)."""
        async with self.pool.acquire() as connection:
            result = await connection.fetchval("SELECT country FROM users WHERE user_id = $1", user_id)
            return result  # Если результат есть, возвращаем его, иначе None

    async def get_item_by_emoji34123412(self , item_emoji: str) -> Optional [ Tuple [ str , int ] ]:
        """Получить название предмета и количество по эмодзи."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        async with self.pool.acquire() as connection:
            result = await connection.fetchrow("SELECT name, remains FROM dex WHERE emoji = $1" , item_emoji)
            if result:
                return result [ 'name' ] , result [ 'remains' ]
            return None

    async def update_item_remains(self , item_emoji: str , quantity_to_add: int):
        """Обновить количество предметов в remains, добавив новое количество по эмодзи."""
        async with self.pool.acquire() as connection:
            # Получаем текущее количество
            current_remains_row = await connection.fetchrow("SELECT remains FROM dex WHERE emoji = $1" , item_emoji)

            if current_remains_row:
                current_remains = current_remains_row [ 'remains' ]
                new_remains = current_remains + quantity_to_add  # Добавляем новое количество

                # Обновляем количество в базе данных
                await connection.execute("UPDATE dex SET remains = $1 WHERE emoji = $2" , new_remains , item_emoji)
                return f"Количество предмета обновлено: {new_remains}."
            else:
                return "Ошибка: Предмет с указанным эмодзи не найден в базе данных."

    async def get_craft_chance(self , emoji1: str , emoji2: str) -> int:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT craftchance FROM craft WHERE item1 = $1 AND item2 = $2" , emoji1 , emoji2)
                if row is None:
                    print(f"[DB] Рецепт {emoji1}+{emoji2} не найден, ставлю 100")
                    return 100
                chance = row [ 'craftchance' ]
                if chance is None:
                    print(f"[DB] craftchance = NULL, ставлю 100")
                    return 100
                chance = int(chance)
                if chance < 0 or chance > 100:
                    print(f"[DB] Некорректный craftchance={chance}, заменяю на 100")
                    return 100
                print(f"[DB] craftchance для {emoji1}+{emoji2} = {chance}")
                return chance
        except Exception as e:
            print(f"[DB] Ошибка get_craft_chance: {e}, возвращаю 100")
            return 100

    async def get_user_craftprox(self , user_id: int) -> int:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT craftprox FROM users WHERE user_id = $1" , user_id)
                if row and row [ 'craftprox' ] is not None:
                    return int(row [ 'craftprox' ])
                return 0
        except Exception:
            return 0

    async def reset_craftprox(self , user_id: int) -> None:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("UPDATE users SET craftprox = 0 WHERE user_id = $1" , user_id)
        except Exception as e:
            print(f"[DB] Ошибка сброса craftprox: {e}")

    async def set_user_craftprox(self , user_id: int , value: int) -> None:
        """Установить значение craftprox (обрезает до 0..100)"""
        value = max(0 , min(100 , value))
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET craftprox = $1 WHERE user_id = $2" , value , user_id)
    async def get_crafts(self):
        """Получить все крафты из базы данных"""
        async with self.pool.acquire() as connection:
            # Запрашиваем все крафты из таблицы "craft"
            rows = await connection.fetch("SELECT item1, item2, item, remains FROM craft")

            # Формируем список крафтов
            crafts = [ {'item1': row [ 'item1' ] , 'item2': row [ 'item2' ] , 'item': row [ 'item' ] ,
                        'remains': row [ 'remains' ]} for row in rows ]
            return crafts

    async def get_random_bonus_gift_item_by_chance(self):
        """
        Возвращает имя случайного предмета из таблицы dex,
        где bonusprox > 0, с учётом процентов выпадения.
        Если есть предметы с bonusprox == 100, выдаётся один из них.
        Если нет предметов с бонусным шансом, возвращает None.
        """
        async with self.pool.acquire() as connection:
            try:
                # Получаем все предметы, у которых bonusprox > 0
                rows = await connection.fetch(
                    "SELECT name, bonusprox FROM dex WHERE bonusprox > 0")
                if not rows:
                    return None  # нет доступных предметов

                # Разделяем на гарантированные (100%) и обычные
                guaranteed = [ row for row in rows if row [ "bonusprox" ] == 100 ]
                if guaranteed:
                    # Выбираем случайный из 100%-ных предметов
                    chosen = random.choice(guaranteed)
                    return chosen [ "name" ]

                # Нет 100%-ных предметов – обычная логика
                total_weight = sum(row [ "bonusprox" ] for row in rows)
                roll = random.randint(1 , 100)

                if roll > total_weight:
                    return None  # предмет не выпал

                # Взвешенный случайный выбор
                cumulative = 0
                target = random.randint(1 , total_weight)
                for row in rows:
                    cumulative += row [ "bonusprox" ]
                    if target <= cumulative:
                        return row [ "name" ]
                # На всякий случай – вернём последний (не должно дойти сюда)
                return rows [ -1 ] [ "name" ] if rows else None

            except Exception as e:
                print(f"Ошибка в get_random_bonus_gift_item_by_chance: {e}")
                return None

    async def get_user_items(self , user_id: int) -> Dict:
        """Получаем список предметов пользователя."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        async with self.pool.acquire() as connection:
            # Получаем список предметов пользователя из базы данных
            result = await connection.fetchrow("SELECT items FROM users WHERE user_id = $1" , user_id)
            # Единый кодек: читает dict, чистый JSON и старый формат вебаппа
            return decode_items(result [ 'items' ] if result else None)

    async def find_item_by_emoji_craft(self , emoji: str) -> str:
        """Находит название предмета по эмодзи."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        async with self.pool.acquire() as connection:
            # Выполняем асинхронный запрос в базу данных для получения имени предмета по эмодзи
            result = await connection.fetchrow("SELECT name FROM dex WHERE emoji = $1" , emoji)
            print(f"find_item_by_emoji_craft: emoji={emoji}, result={result}")
            if result:
                return result [ 'name' ]
            return None

    async def find_emoji_by_item_name(self , item_name: str) -> str:
        """Находит эмодзи по названию предмета."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        async with self.pool.acquire() as connection:
            # Выполняем асинхронный запрос в базу данных для получения эмодзи по названию предмета
            result = await connection.fetchrow("SELECT emoji FROM dex WHERE name = $1" , item_name)
            print(f"find_emoji_by_item_name: item_name={item_name}, result={result}")
            if result:
                return result [ 'emoji' ]
            return None

    async def remove_items_craft(self , user_id: int , item_name: str , quantity: int):
        """Удаляет указанное количество предметов из инвентаря пользователя."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        async with self.pool.acquire() as connection:
            # Получаем инвентарь пользователя
            result = await connection.fetchrow("SELECT items FROM users WHERE user_id = $1" , user_id)
            if result and result [ 'items' ]:
                inventory_items = decode_items(result [ 'items' ])
                if item_name in inventory_items:
                    inventory_items [ item_name ] = int(inventory_items [ item_name ] or 0) - quantity
                    if inventory_items [ item_name ] <= 0:
                        del inventory_items [ item_name ]

                    # Обновляем инвентарь пользователя в базе данных
                    await connection.execute(
                        "UPDATE users SET items = $1 WHERE user_id = $2" , encode_items(inventory_items) , user_id)
                    print(f"remove_items_craft: user_id={user_id}, item_name={item_name}, quantity={quantity}")

    async def add_item_craft(self , user_id: int , item_name: str , quantity: int):
        """Добавляет предмет в инвентарь пользователя."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            async with self.pool.acquire() as connection:
                # Получаем текущий инвентарь пользователя
                result = await connection.fetchrow("SELECT items FROM users WHERE user_id = $1" , user_id)
                if result:
                    inventory_items = decode_items(result [ 'items' ])

                    # Обновляем количество предмета
                    if item_name in inventory_items:
                        inventory_items [ item_name ] = int(inventory_items [ item_name ] or 0) + quantity
                    else:
                        inventory_items [ item_name ] = quantity

                    # Обновляем инвентарь пользователя в базе данных
                    await connection.execute(
                        "UPDATE users SET items = $1 WHERE user_id = $2" , encode_items(inventory_items) , user_id)
                    print(f"add_item_craft: user_id={user_id}, item_name={item_name}, quantity={quantity}")
                else:
                    print(f"Error: User {user_id} not found.")
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error while adding item to user inventory: {e}")

    async def set_user_inventorycutecoin(self, user_id: int, inventory: Dict[str, int]):
        """Обновляет инвентарь пользователя."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            # Преобразуем инвентарь в JSON строку (единый кодек)
            inventory_json = encode_items(inventory)

            # Обновляем инвентарь пользователя
            async with self.pool.acquire() as connection:
                await connection.execute(
                    "UPDATE users SET items = $1 WHERE user_id = $2",
                    inventory_json,
                    user_id
                )
            print(f"set_user_inventorycutecoin: user_id={user_id}, inventory={inventory}")
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error while updating user inventory: {e}")

    async def find_craft_craft(self , emoji1: str , emoji2: str) -> Tuple [ str , int ]:
        """Ищет рецепт крафта по комбинации emoji1 и emoji2."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            # Выполняем запрос с асинхронным соединением
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT item, remains FROM craft WHERE (item1 = $1 AND item2 = $2) OR (item1 = $2 AND item2 = $1)" ,
                    emoji1 , emoji2)

            print(f"find_craft_craft: emoji1={emoji1}, emoji2={emoji2}, result={result}")
            # Возвращаем результат или кортеж по умолчанию
            return (result [ 'item' ] , result [ 'remains' ]) if result else (None , 0)
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error: {e}")
            return (None , 0)
















    #[
    # Внутри вашего класса, где уже есть get_items(), get_items_by_sorting() и т.д.

    async def get_all_items_full(self):
        """Получить все предметы c полями name, price, remains, sorting, emoji, упорядоченные по id."""
        if not self.pool:
            print("Пул соединений не инициализирован!")
            return [ ]
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    "SELECT name, price, remains, sorting, emoji FROM dex ORDER BY id ASC")
            return [ (r [ 'name' ] , r [ 'price' ] , r [ 'remains' ] , r [ 'sorting' ] , r [ 'emoji' ]) for r in rows ]
        except Exception as e:
            print(f"Ошибка при получении всех предметов: {e}")
            return [ ]

    async def get_items_by_sorting_full(self , symbol: str):
        """Получить предметы с фильтром по sorting (name, price, remains, emoji), упорядоченные по id."""
        if not self.pool:
            print("Пул соединений не инициализирован!")
            return [ ]
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    "SELECT name, price, remains, emoji FROM dex WHERE sorting LIKE $1 ORDER BY id ASC" , f'%{symbol}%')
            return [ (r [ 'name' ] , r [ 'price' ] , r [ 'remains' ] , r [ 'emoji' ]) for r in rows ]
        except Exception as e:
            print(f"Ошибка при получении предметов по символу {symbol}: {e}")
            return [ ]
    async def get_item_name_by_emoji(self , emoji: str) -> Optional [ str ]:
        """Получить название предмета по эмодзи из таблицы dex."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            # Выполняем запрос с асинхронным соединением
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT name FROM dex WHERE emoji = $1" , emoji)

            if result:
                return result [ 'name' ]  # Возвращаем название предмета
            else:
                return None
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error: {e}")
            return None

    async def get_emoji_for_item(self , name: str) -> str:
        """Получить эмодзи по названию предмета из таблицы dex."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            # Выполняем асинхронный запрос
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT emoji FROM dex WHERE name = $1" , name)

            # Если эмодзи найдено, возвращаем его, иначе возвращаем стандартное значение
            return result [ 'emoji' ] if result else "✖️"

        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error: {e}")
            return "✖️"

    async def get_emojis_for_items(self , names: Iterable [ str ]) -> Dict [ str , str ]:
        """Пакетно: name → emoji из dex (один запрос вместо N)."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")
        unique = list({str(n).strip() for n in names if n})
        if not unique:
            return {}
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    "SELECT name, emoji FROM dex WHERE name = ANY($1::text[])" , unique)
            return {row [ 'name' ]: row [ 'emoji' ] for row in rows if row [ 'emoji' ]}
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error while batch-fetching emojis: {e}")
            return {}

    async def get_emoji_for_item_name(self , item_name: str) -> str:
        """Получить эмодзи по названию предмета из таблицы dex."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            # Выполняем асинхронный запрос
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT emoji FROM dex WHERE name = $1" , item_name)

            # Если эмодзи найдено, возвращаем его, иначе возвращаем стандартное значение
            return result [ 'emoji' ] if result else "✖️"
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error: {e}")
            return "✖️"

    async def get_item_info_by_emoji(self , emoji: str) -> Optional [ Tuple [ str , int ] ]:
        """Получить название предмета и количество по эмодзи из таблицы dex."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            # Выполняем асинхронный запрос
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT name, remains FROM dex WHERE emoji = $1" , emoji)

            # Если предмет найден, возвращаем его название и количество
            if result:
                return result [ 'name' ] , result [ 'remains' ]
            else:
                return None  # Если предмет не найден, возвращаем None
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error: {e}")
            return None

    async def get_item_price(self , item_name: str) -> Optional [ int ]:
        """Получить цену предмета по названию из таблицы dex."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            # Выполняем асинхронный запрос
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT price FROM dex WHERE name = $1" , item_name)

            # Если цена найдена, возвращаем её
            if result:
                return result [ 'price' ]
            else:
                return None  # Если предмет не найден, возвращаем None
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error: {e}")
            return None

    async def get_items(self):
        """Получить все данные по всем столбцам из таблицы dex с правильной информацией, упорядоченные по id."""
        if self.pool is None:
            print("Пул соединений не инициализирован!")
            return [ ]

        try:
            async with self.pool.acquire() as connection:
                # Выполнение запроса для получения всех столбцов из таблицы dex, отсортированных по id
                result = await connection.fetch("SELECT * FROM dex ORDER BY id ASC")

                # Преобразуем результат в список кортежей
                items = [ (item [ 'name' ] , item [ 'price' ] , item [ 'remains' ]) for item in result ]

                # Возвращаем список данных в нужном формате
                return items
        except Exception as e:
            print(f"Ошибка при получении предметов: {e}")
            return [ ]

    async def get_items_by_sorting(self , symbol):
        """Получить все предметы из таблицы dex с сортировкой по символу и упорядочить по id."""
        async with self.pool.acquire() as connection:
            try:
                # Выполнение запроса с сортировкой по id
                result = await connection.fetch(
                    "SELECT name, price, remains FROM dex WHERE sorting LIKE $1 ORDER BY id ASC" , f'%{symbol}%')

                # Возвращаем список результатов
                return [ (item [ 'name' ] , item [ 'price' ] , item [ 'remains' ]) for item in result ]
            except Exception as e:
                print(f"Ошибка при получении предметов по символу {symbol}: {e}")
                return [ ]





    async def get_user_inventorycutecoin(self , user_id: int) -> Dict:
        """Получить инвентарь пользователя по user_id."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            # Асинхронный запрос для получения инвентаря пользователя
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow("SELECT items FROM users WHERE user_id = $1" , user_id)

            if result and result [ 'items' ]:
                return decode_items(result [ 'items' ])
            else:
                print(f"Inventory not found for user: {user_id}")
                return {}
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error while fetching user inventory: {e}")
            return {}

    async def get_last_coin_price(self):
        """Получаем последнюю цену монеты."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            # Асинхронный запрос для получения последней цены монеты
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow("SELECT dice FROM cointime ORDER BY rowid DESC LIMIT 1")

            if result:
                return result [ 'dice' ]
            else:
                return None  # Возвращаем None, если результат не найден
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error while fetching last coin price: {e}")
            return None

    async def update_item_pricecutecoin(self):
        """Обновляет цену для предмета '💠 CuteCoin' в таблице dex на последнюю цену коина."""
        last_coin_price = await self.get_last_coin_price()
        if last_coin_price is None:
            print("Ошибка: Не удалось получить последнюю цену коина.")
            return

        # Обновляем цену предмета "💠 CuteCoin" в таблице dex
        query = "UPDATE dex SET price = $1 WHERE name LIKE $2"
        new_price = last_coin_price  # Пример изменения цены (можно добавить увеличение на 50% или другое логическое изменение)
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(query, new_price, '%💠 CuteCoin%')
            print(f"Цена предмета '💠 CuteCoin' успешно изменена на {new_price}")
        except asyncpg.PostgresError as e:
            print(f"Ошибка при обновлении цены предмета '💠 CuteCoin': {e}")


    async def set_items(self , user_id , item_name , quantity):
        """Обновление инвентаря пользователя, добавление или обновление количества предметов."""
        async with self.pool.acquire() as connection:
            try:
                # Получаем текущий список предметов пользователя
                result = await connection.fetchrow("SELECT items FROM users WHERE user_id = $1" , user_id)

                # Загружаем инвентарь через единый кодек (понимает любой формат)
                current_items = decode_items(result [ 'items' ] if result else None)

                # Обновляем количество предмета или добавляем новый
                if item_name in current_items:
                    current_items [ item_name ] = int(current_items [ item_name ] or 0) + quantity
                else:
                    current_items [ item_name ] = quantity

                # Обновляем запись в базе данных
                await connection.execute(
                    "UPDATE users SET items = $1 WHERE user_id = $2" , encode_items(current_items) , user_id)
                print(f"Инвентарь пользователя {user_id} успешно обновлен.")
            except Exception as e:
                print(f"Ошибка при обновлении инвентаря пользователя {user_id}: {e}")

    async def buy_item(self , item_name , quantity):
        """Покупка предмета, обновление количества на складе."""
        async with self.pool.acquire() as connection:
            async with connection.transaction():  # Используем транзакцию
                try:
                    # Получаем текущее количество предметов из базы данных
                    result = await connection.fetchrow(
                        "SELECT remains FROM dex WHERE name = $1" , item_name)

                    if result:
                        current_remain = result [ 'remains' ]
                        print(f"Найдено количество: {current_remain} для предмета '{item_name}'.")

                        # Проверка на достаточность предметов
                        if current_remain >= quantity:
                            new_remain = current_remain - quantity

                            # Обновляем количество предметов в базе данных
                            update_result = await connection.execute(
                                "UPDATE dex SET remains = $1 WHERE name = $2" , new_remain , item_name)

                            # Проверка успешности обновления
                            if update_result:
                                print(f"Предмет '{item_name}' успешно куплен. Новое количество: {new_remain}.")
                                return item_name , quantity
                            else:
                                print(f"Не удалось обновить количество для предмета '{item_name}'.")
                                return None , None
                        else:
                            print(
                                f"Недостаточно предметов '{item_name}' для покупки. Требуемое: {quantity}, доступно: {current_remain}.")
                            return None , None
                    else:
                        print(f"Предмет '{item_name}' не найден в базе данных.")
                        return None , None

                except Exception as e:
                    print(f"Ошибка при выполнении операции покупки предмета: {e}")
                    return None , None

    async def increase_item_quantity(self , item_name , quantity):
        """Увеличивает количество предмета в магазине."""
        async with self.pool.acquire() as connection:
            try:
                # Получаем текущее количество предмета в магазине
                result = await connection.fetchrow("SELECT remains FROM dex WHERE name = $1" , item_name)
                if result:
                    current_remain = result [ 'remains' ]
                    new_remain = current_remain + quantity
                    # Обновляем количество предмета в таблице dex
                    await connection.execute(
                        "UPDATE dex SET remains = $1 WHERE name = $2" , new_remain , item_name)
                    print(f"🔄 Обновлено количество предмета в магазине: {item_name}, новое количество: {new_remain}")
                else:
                    print(f"⚠️ Предмет {item_name} не найден в таблице dex")
            except Exception as e:
                print(f"Ошибка при обновлении количества предмета: {e}")

    async def set_user_items(self , user_id , inventory):
        """Обновляет инвентарь пользователя в базе данных."""
        async with self.pool.acquire() as connection:
            try:
                # Преобразуем инвентарь в строку JSON и обновляем его в базе данных
                inventory_json = encode_items(inventory)
                await connection.execute(
                    "UPDATE users SET items = $1 WHERE user_id = $2" , inventory_json , user_id)
                print(f"Инвентарь пользователя {user_id} успешно обновлён.")
            except Exception as e:
                print(f"Ошибка при обновлении инвентаря пользователя {user_id}: {e}")

    async def send_item(self , sender_id , receiver_id , item_index):
        try:
            # Получаем инвентарь отправителя
            async with self.pool.acquire() as connection:
                sender_inventory_row = await connection.fetchrow(
                    "SELECT items FROM users WHERE user_id = $1" , sender_id)
                if sender_inventory_row:
                    sender_inventory = decode_items(sender_inventory_row [ 'items' ])
                else:
                    print("Ошибка: Инвентарь отправителя не найден.")
                    return False

                # Получаем инвентарь получателя
                receiver_inventory_row = await connection.fetchrow(
                    "SELECT items FROM users WHERE user_id = $1" , receiver_id)
                if receiver_inventory_row:
                    receiver_inventory = decode_items(receiver_inventory_row [ 'items' ])
                else:
                    receiver_inventory = {}

                # Проверяем, есть ли такой предмет в инвентаре отправителя
                if item_index <= len(sender_inventory):
                    item_to_send = list(sender_inventory.keys()) [ item_index - 1 ]

                    # Получаем количество предметов
                    quantity = sender_inventory [ item_to_send ]

                    # Если у отправителя есть этот предмет, передаем его получателю
                    if quantity > 0:
                        # Обновляем инвентарь получателя
                        receiver_inventory [ item_to_send ] = receiver_inventory.get(item_to_send , 0) + quantity

                        # Обновляем инвентарь отправителя
                        sender_inventory [ item_to_send ] = 0

                        # Проверяем, если количество предмета у отправителя стало нулевым, удаляем его из инвентаря
                        if sender_inventory [ item_to_send ] == 0:
                            del sender_inventory [ item_to_send ]

                        # Проверяем, если количество предмета у получателя стало нулевым, удаляем его из инвентаря
                        if receiver_inventory [ item_to_send ] == 0:
                            del receiver_inventory [ item_to_send ]

                        # Обновляем инвентарь в базе данных
                        await connection.execute(
                            "UPDATE users SET items = $1 WHERE user_id = $2" , encode_items(sender_inventory) , sender_id)
                        await connection.execute(
                            "UPDATE users SET items = $1 WHERE user_id = $2" , encode_items(receiver_inventory) ,
                            receiver_id)

                        # Удаляем предметы с нулевым количеством из инвентаря отправителя
                        await self.remove_zero_items(sender_id)

                        # Удаляем предметы с нулевым количеством из инвентаря получателя
                        await self.remove_zero_items(receiver_id)

                        print(f"Предмет успешно отправлен пользователю {receiver_id}")
                        return True
                    else:
                        print("Ошибка: У вас нет такого предмета для передачи.")
                        return False
                else:
                    print("Ошибка: Предмет с таким номером не найден в вашем инвентаре.")
                    return False
        except Exception as e:
            print(f"Ошибка при отправке предмета: {e}")
            return False

    async def delete_user_inventory(self , user_id):
        """Удаляет предметы с нулевым количеством из инвентаря пользователя."""
        async with self.pool.acquire() as connection:
            try:
                # Получаем текущий инвентарь пользователя
                result = await connection.fetchrow(
                    "SELECT items FROM users WHERE user_id = $1" , user_id)

                if result:
                    inventory_items = decode_items(result [ 'items' ])

                    # Удаляем предметы с нулевым количеством из инвентаря
                    inventory_items = {item: quantity for item , quantity in inventory_items.items() if quantity != 0}

                    # Обновляем запись в базе данных
                    await connection.execute(
                        "UPDATE users SET items = $1 WHERE user_id = $2" , encode_items(inventory_items) , user_id)

                    print(f"Предметы с нулевым количеством успешно удалены из инвентаря пользователя {user_id}.")
                    return True
                else:
                    print(f"Инвентарь пользователя {user_id} не найден.")
                    return False
            except Exception as e:
                print(f"Ошибка при удалении предметов с нулевым количеством из инвентаря пользователя: {e}")
                return False

    async def remove_zero_items(self , user_id):
        try:
            # Получаем текущий инвентарь пользователя
            async with self.pool.acquire() as connection:
                user_inventory_row = await connection.fetchrow(
                    "SELECT items FROM users WHERE user_id = $1" , user_id)

                if user_inventory_row:
                    inventory_items = decode_items(user_inventory_row [ 'items' ])

                    # Удаляем предметы с нулевым количеством из инвентаря
                    inventory_items = {item: quantity for item , quantity in inventory_items.items() if quantity != 0}

                    # Обновляем запись в базе данных
                    await connection.execute(
                        "UPDATE users SET items = $1 WHERE user_id = $2" , encode_items(inventory_items) , user_id)

                    print(f"Предметы с нулевым количеством успешно удалены из инвентаря пользователя {user_id}.")
                    return True
                else:
                    print(f"Инвентарь пользователя {user_id} не найден.")
                    return False
        except Exception as e:
            print(f"Ошибка при удалении предметов с нулевым количеством из инвентаря пользователя: {e}")
            return False

    async def set_user_inventory(self , user_id , inventory):
        try:
            # Используем пул соединений для получения соединения
            async with self.pool.acquire() as connection:
                # Обновляем инвентарь пользователя в базе данных
                await connection.execute(
                    "UPDATE users SET items = $1 WHERE user_id = $2" , encode_items(inventory) , user_id)
                print(f"Инвентарь пользователя {user_id} успешно обновлен.")
                return True
        except Exception as e:
            print(f"Ошибка при обновлении инвентаря пользователя {user_id}: {e}")
            return False

    async def get_catalog_items(self):
        """Получить все предметы из таблицы dex в порядке, как они указаны."""
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            async with self.pool.acquire() as connection:
                # Сортировка по порядку в базе данных (например, по id)
                rows = await connection.fetch("SELECT name, price, remains FROM dex ORDER BY id")
                return rows
        except asyncpg.PostgresError as e:
            print(f"PostgreSQL error: {e}")
            return [ ]
    async def get_discounted_price(self , item_name):
        try:
            # Получаем соединение из пула
            async with self.pool.acquire() as connection:
                # Выполняем запрос для получения скидки по имени предмета
                row = await connection.fetchrow(
                    "SELECT dis FROM dex WHERE emoji = $1" , item_name)

                # Если запись найдена, возвращаем значение скидки
                return row [ 'dis' ] if row else 0
        except Exception as e:
            print(f"Ошибка при получении скидки для предмета {item_name}: {e}")
            return 0

    async def get_discounts_bulk(self, emojis):
        """Массово получить скидки для списка эмодзи ОДНИМ запросом вместо N.
        Возвращает {emoji: dis}. Раньше магазин делал по запросу на каждый из
        ~240 эмодзи → долго и грузило пул."""
        if not emojis:
            return {}
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    "SELECT emoji, dis FROM dex WHERE emoji = ANY($1)", list(emojis))
                return {r['emoji']: r['dis'] for r in rows}
        except Exception as e:
            print(f"Ошибка при массовом получении скидок: {e}")
            return {}

    async def get_dex_balance(self , chat_id):
        """Метод для получения текущего баланса dex по chat_id."""
        try:
            # Получаем соединение из пула
            async with self.pool.acquire() as connection:
                # Выполняем запрос для получения баланса dex
                row = await connection.fetchrow(
                    "SELECT dexbalance FROM chat WHERE chat_id = $1" , chat_id)

                # Если запись найдена, возвращаем текущий баланс
                return row [ 'dexbalance' ] if row else None
        except Exception as e:
            print(f"Ошибка при получении баланса dex для chat_id {chat_id}: {e}")
            return None

    async def update_dex_balance(self ,bot1, chat_id , amount):
        """Метод для обновления баланса dex по chat_id."""
        # LEGACY: система dexbalance заморожена.
        # Намеренно не обновляем dexbalance, чтобы она нигде не работала.
        try:
            current_balance = await self.get_dex_balance(bot1 , chat_id)
            print(
                f"[DEXBALANCE][FROZEN] skip update chat_id={chat_id} "
                f"amount={amount} current={current_balance}"
            )
            return current_balance
        except Exception as e:
            print(f"[DEXBALANCE][FROZEN] read failed chat_id={chat_id}: {e}")
            return 0

    async def get_item_sticker(self , emoji=None , name=None):
        """
        Получаем стикер по эмодзи или названию предмета.
        """
        try:
            async with self.pool.acquire() as connection:
                if emoji:
                    query = "SELECT stick FROM dex WHERE emoji = $1"
                    result = await connection.fetchrow(query , emoji)
                elif name:
                    query = "SELECT stick FROM dex WHERE name = $1"
                    result = await connection.fetchrow(query , name)
                else:
                    return None  # Если ни emoji, ни name не переданы

                if result:
                    return result [ 'stick' ]  # Возвращаем идентификатор стикера
                else:
                    return None  # Если стикера нет в базе данных
        except Exception as e:
            print(f"⚠️ [DEBUG] Ошибка при получении стикера: {e}")
            return None

    async def delete_user_inventory12(self , user_id , item_name , quantity):
        try:
            # Получаем текущий инвентарь пользователя
            async with self.pool.acquire() as connection:
                # Запрашиваем инвентарь пользователя
                query = "SELECT items FROM users WHERE user_id = $1"
                user_inventory = await connection.fetchrow(query , user_id)

                if user_inventory:
                    inventory_items = decode_items(user_inventory [ 'items' ])

                    # Проверяем наличие предмета в инвентаре
                    if item_name in inventory_items:
                        # Проверяем, достаточно ли предметов для удаления
                        if inventory_items [ item_name ] >= quantity:
                            # Уменьшаем количество предметов в инвентаре
                            inventory_items [ item_name ] -= quantity

                            # Удаляем предмет из инвентаря, если его количество стало 0
                            if inventory_items [ item_name ] == 0:
                                del inventory_items [ item_name ]

                            # Обновляем запись в базе данных
                            update_query = "UPDATE users SET items = $1 WHERE user_id = $2"
                            await connection.execute(update_query , encode_items(inventory_items) , user_id)

                            print(f"Предмет {item_name} успешно удален из инвентаря пользователя {user_id}.")
                            return True
                        else:
                            print(f"Ошибка: У пользователя недостаточно предметов '{item_name}' для удаления.")
                            return False
                    else:
                        print(f"Ошибка: Предмет {item_name} не найден в инвентаре пользователя.")
                        return False
                else:
                    print(f"Инвентарь пользователя {user_id} не найден.")
                    return False
        except Exception as e:
            print(f"Ошибка при удалении предмета из инвентаря пользователя: {e}")
            return False

    async def delete_user_inventory1(self, user_id, item_name):
        try:
            async with self.pool.acquire() as connection:
                # Получаем текущий инвентарь пользователя
                user_inventory = await connection.fetchrow(
                    "SELECT items FROM users WHERE user_id = $1", user_id
                )

                if user_inventory:
                    inventory_items = decode_items(user_inventory['items'])

                    # Проверяем наличие предмета в инвентаре
                    if item_name in inventory_items:
                        # Удаляем один предмет из инвентаря пользователя, если его количество больше 1
                        if inventory_items[item_name] > 1:
                            inventory_items[item_name] -= 1
                        # Если количество предметов равно 1, удаляем весь предмет
                        else:
                            del inventory_items[item_name]

                        # Обновляем запись в базе данных
                        await connection.execute(
                            "UPDATE users SET items = $1 WHERE user_id = $2",
                            encode_items(inventory_items), user_id
                        )

                        print(f"Предмет {item_name} успешно удален из инвентаря пользователя {user_id}.")
                        return True
                    else:
                        print(f"Ошибка: Предмет {item_name} не найден в инвентаре пользователя {user_id}.")
                        return False
                else:
                    print(f"Инвентарь пользователя {user_id} не найден.")
                    return False
        except Exception as e:
            print(f"Ошибка при удалении предмета из инвентаря пользователя: {e}")
            return False









    async def get_cutenin_balance(self, user_id):
        """Асинхронно получает текущий баланс cutenin пользователя по user_id."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос для получения баланса пользователя
                result = await connection.fetchrow(
                    "SELECT cutenin FROM users WHERE user_id = $1", user_id
                )

                if result:
                    return result['cutenin']  # Возвращаем баланс пользователя
                return None  # Если пользователя нет в базе данных, возвращаем None
        except Exception as e:
            print(f"Ошибка при получении баланса cutenin: {e}")
            return None

    async def update_cutenin_balance(self, user_id, amount):
        """Метод для обновления баланса cutenin по user_id."""
        try:
            # Получаем текущий баланс
            current_balance = await self.get_cutenin_balance(user_id)
            if current_balance is not None:
                new_balance = current_balance + amount
                async with self.pool.acquire() as connection:
                    # Обновляем запись в базе данных
                    await connection.execute(
                        "UPDATE users SET cutenin = $1 WHERE user_id = $2",
                        new_balance, user_id
                    )
                print(f"Баланс cutenin пользователя {user_id} успешно обновлен на {new_balance}.")
                return new_balance
            else:
                print(f"Ошибка: Пользователь с id {user_id} не найден.")
                return None
        except Exception as e:
            print(f"Ошибка при обновлении баланса cutenin пользователя {user_id}: {e}")
            return None









    async def get_group_info(self, chat_id):
        """Получает информацию о группе по chat_id."""
        try:
            async with self.pool.acquire() as connection:
                # Выполнение асинхронного запроса к базе данных
                result = await connection.fetchrow("""
                    SELECT chat_id, namechat, usernamechat, chatlink, description, channel, 
                           supergroup, creator_id, creator_name, creator_username, text, data
                    FROM chat
                    WHERE chat_id = $1
                """, chat_id)
                if result:
                    return dict(result)  # Возвращаем результат как словарь
                return None  # Если группа не найдена
        except Exception as e:
            print(f"Ошибка при получении информации о группе с chat_id {chat_id}: {e}")
            return None

    async def check_group_exists(self, chat_id):
        """Проверяет, существует ли группа в базе данных."""
        try:
            async with self.pool.acquire() as connection:
                # Выполняем запрос и проверяем, существует ли группа
                result = await connection.fetchrow("""
                    SELECT 1 FROM chat WHERE chat_id = $1
                """, chat_id)
                return result is not None  # Возвращаем True, если группа существует, иначе False
        except Exception as e:
            print(f"Ошибка при проверке существования группы с chat_id {chat_id}: {e}")
            return False

    async def add_group(self , chat_id , namechat , usernamechat , chatlink , description , creator_id , creator_name ,
                        creator_username):
        """Добавляет новую группу в базу данных, точно заполняя соответствующие столбцы."""
        current_date = datetime.now()  # Используем datetime объект, а не строку
        print("chat_id , namechat , usernamechat , chatlink , description , creator_id , creator_name ,creator_username", chat_id , namechat , usernamechat , chatlink , description , creator_id , creator_name ,
                        creator_username)
        # Проверка на существование чата
        if not await self.check_group_exists(chat_id):  # Если группа не существует, добавляем
            try:
                async with self.pool.acquire() as connection:
                    # Явно указываем столбцы и их значения, чтобы избежать ошибок
                    sql = '''
                        INSERT INTO chat 
                        (chat_id, namechat, usernamechat, chatlink, description, 
                         creator_id, creator_name, creator_username, text, data)
                        VALUES 
                        ($1, $2, $3, $4, $5, 
                         $6, $7, $8, $9, $10)
                    '''

                    # Выполнение запроса с точной передачей значений
                    await connection.execute(
                        sql , chat_id , namechat , usernamechat , chatlink , description , creator_id , creator_name ,
                        creator_username , 0 , current_date)  # Передаем объект datetime

                print(f"Добавлена новая группа {chat_id}.")
            except Exception as e:
                print(f"Ошибка при добавлении группы {chat_id}: {e}")

    async def update_group_info(self, chat_id, namechat, usernamechat, chatlink, description,
                                supergroup, creator_id, creator_name, creator_username):
        """Обновляет информацию о существующей группе."""
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Форматируем дату в строку

        try:
            async with self.pool.acquire() as connection:
                # Обновление информации о группе
                await connection.execute('''
                    UPDATE chat 
                    SET namechat = $1, 
                        usernamechat = $2, 
                        chatlink = $3, 
                        description = $4,  
                        supergroup = $5, 
                        creator_id = $6,  
                        creator_name = $7, 
                        creator_username = $8, 
                        text = text + 1,  -- Добавление 1 к текущему значению поля text
                        data = $9
                    WHERE chat_id = $10
                ''', namechat, usernamechat, chatlink, description, supergroup, creator_id,
                    creator_name, creator_username, current_date, chat_id)

            print(f"Обновлена группа {chat_id}.")
        except Exception as e:
            print(f"Ошибка при обновлении информации о группе {chat_id}: {e}")

    async def update_chat_columns(self , chat_id , **updates):
        """Обновляет столбцы группы в базе данных безопасно."""
        try:
            # Строим SET часть запроса
            set_clause = ', '.join([ f"{key} = ${i + 1}" for i , key in enumerate(updates.keys()) ])
            values = list(updates.values()) + [ chat_id ]  # Параметры для запроса

            async with self.pool.acquire() as connection:
                # Выполняем запрос с параметризацией
                await connection.execute(f'UPDATE chat SET {set_clause} WHERE chat_id = ${len(updates) + 1}' , *values)

            print(f"Обновлены столбцы для chat_id={chat_id}.")
        except Exception as e:
            print(f"Ошибка при обновлении столбцов для chat_id={chat_id}: {e}")

    async def update_or_insert_chat_opt(self , chat_id , namechat , usernamechat , chatlink , description , channel ,
                                        supergroup , members_count , creator_id , creator_name , creator_username ,
                                        admin_id , admin_name , admin_username , current_date):
        """Проверяет наличие чата в базе данных и обновляет или добавляет его информацию."""

        try:
            async with self.pool.acquire() as connection:
                # Проверка на существование записи для данного чата
                row = await connection.fetchrow('SELECT * FROM chat WHERE chat_id = $1' , chat_id)

                if row:
                    # Обновление существующей записи
                    await connection.execute(
                        '''UPDATE chat 
                           SET namechat = $1, 
                               usernamechat = $2, 
                               chatlink = $3, 
                               description = $4, 
                               channel = $5, 
                               supergroup = $6, 
                               member = $7,  
                               creator_id = $8,  
                               creator_name = $9, 
                               creator_username = $10, 
                               admin_id = $11, 
                               admin_name = $12, 
                               admin_username = $13, 
                               text = text + 1, 
                               data = $14 
                           WHERE chat_id = $15''' , (
                            namechat , usernamechat , chatlink , description , channel , supergroup , members_count ,
                            creator_id , creator_name , creator_username , admin_id , admin_name , admin_username ,
                            current_date , chat_id))
                else:
                    # Добавление новой записи
                    await connection.execute(
                        '''INSERT INTO chat (
                               chat_id, namechat, usernamechat, chatlink, description, 
                               channel, supergroup, member, creator_id, creator_name, 
                               creator_username, admin_id, admin_name, admin_username, 
                               text, data
                           ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
                                     $11, $12, $13, $14, 1, $15)''' , (
                            chat_id , namechat , usernamechat , chatlink , description , channel , supergroup ,
                            members_count , creator_id , creator_name , creator_username , admin_id , admin_name ,
                            admin_username , current_date))

                    # Установка начального количества сообщений для новой группы
                    total_messages = await connection.fetchval(
                        'SELECT SUM(text) FROM chat WHERE chat_id = $1' , chat_id) or 0
                    await connection.execute('UPDATE chat SET text = $1 WHERE chat_id = $2' , total_messages , chat_id)

            print(f"Группа с chat_id={chat_id} обновлена или добавлена.")
        except Exception as e:
            print(f"Ошибка при обновлении или добавлении группы с chat_id={chat_id}: {e}")

























#saadsa

    async def ban_group(self, chat_id):
        """Добавление идентификатора группы в таблицу banchat для блокировки группы."""
        try:
            async with self.pool.acquire() as connection:
                # Вставка в таблицу banchat, игнорируя конфликты по chat_id
                await connection.execute(
                    """
                    INSERT INTO banchat (chat_id)
                    VALUES ($1)
                    ON CONFLICT (chat_id) DO NOTHING
                    """,
                    chat_id
                )
                self.invalidate_group_ban_cache(chat_id)
                print(f"Группа с ID {chat_id} заблокирована.")
        except Exception as e:
            print(f"Ошибка при блокировке группы с chat_id={chat_id}: {e}")

    async def is_group_banned(self, chat_id):
        """Проверяет, заблокирована ли группа по chat_id (с кэшем на 60с).

        Кэш снимает лишний round-trip по SSH-туннелю на КАЖДУЮ команду.
        Блокировка группы меняется редко; свежесть в пределах TTL достаточна.
        """
        now = time.monotonic()
        cached = self._group_ban_cache.get(chat_id)
        if cached is not None and (now - cached[0]) < self._group_ban_cache_ttl:
            return cached[1]
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT chat_id FROM banchat WHERE chat_id = $1", chat_id
                )
                banned = result is not None
                self._group_ban_cache[chat_id] = (now, banned)
                return banned
        except Exception as e:
            print(f"Ошибка при проверке блокировки группы с chat_id={chat_id}: {e}")
            return False

    def invalidate_group_ban_cache(self, chat_id=None):
        """Сбросить кэш блокировки группы (после ban/unban)."""
        if chat_id is None:
            self._group_ban_cache.clear()
        else:
            self._group_ban_cache.pop(chat_id, None)

    async def unban_group(self, chat_id):
        """Удаляет группу из таблицы banchat по chat_id."""
        try:
            async with self.pool.acquire() as connection:
                result = await connection.execute(
                    "DELETE FROM banchat WHERE chat_id = $1", chat_id
                )
                self.invalidate_group_ban_cache(chat_id)
                if result:
                    print(f"Группа с ID {chat_id} разблокирована.")
                    return True
                else:
                    print(f"Группа с ID {chat_id} не найдена в списке заблокированных.")
                    return False
        except Exception as e:
            print(f"Ошибка при разблокировке группы с chat_id={chat_id}: {e}")
            return False

    async def add_chat_message(self, user_id, user_name, user_username, chat_id, chat_name, chat_username, message34, data_out):
        """Добавление сообщения в таблицу chatmessage."""
        try:
            data_open_datetime = time.time()
            current_time_str = datetime.fromtimestamp(data_open_datetime).strftime('%Y-%m-%d %H:%M:%S')

            # Вставляем новое сообщение в таблицу
            async with self.pool.acquire() as connection:
                await connection.execute(
                    """
                    INSERT INTO chatmessage (user_id, user_name, user_username, chat_id, chat_name, chat_username, message, data_type, data_delete)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    user_id, user_name, user_username, chat_id, chat_name, chat_username, message34, current_time_str, data_out
                )

            print(f"Сообщение добавлено для пользователя {user_id} в чат {chat_id}.")
        except Exception as e:
            print(f"Ошибка при добавлении сообщения: {str(e)}")

    async def unban_user(self , user_id: int):
        """Удаляет пользователя из таблицы banusers."""
        try:
            print(f"🔓 Удаление пользователя с ID {user_id} из бана...")

            # Асинхронное удаление пользователя из таблицы banusers
            async with self.pool.acquire() as connection:
                # Убедитесь, что пользователь существует перед удалением
                result = await connection.fetchval(
                    "SELECT COUNT(*) FROM banusers WHERE user_id = $1" , user_id)

                if result == 0:
                    print(f"⚠️ Пользователь с ID {user_id} не найден в списке заблокированных.")
                    return

                # Выполнение удаления
                await connection.execute(
                    "DELETE FROM banusers WHERE user_id = $1" , user_id)

            print(f"✅ Пользователь с ID {user_id} успешно разблокирован.")
        except Exception as e:
            print(f"Ошибка при удалении пользователя из бана: {str(e)}")

    async def is_user_banned(self , user_id: int) -> bool:
        """Проверяет, заблокирован ли пользователь по user_id."""
        uid = int(user_id)
        cached = self._ban_check_cache.get(uid)
        if cached and (time.monotonic() - cached[0]) < 60.0:
            return bool(cached[1])
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT 1 FROM banusers WHERE user_id = $1" , uid)
            banned = result is not None
            self._ban_check_cache[uid] = (time.monotonic(), banned)
            return banned
        except Exception as e:
            # Раньше здесь печатался пустой str(e) (у asyncpg TimeoutError нет
            # текста) и результат НЕ кешировался → на недоступной БД проверка
            # повторялась и спамила лог на каждый апдейт.
            # Теперь: логируем тип/повтор ошибки и кешируем безопасный fail-open,
            # чтобы не долбить мёртвую базу до истечения TTL кеша.
            self._ban_check_cache[uid] = (time.monotonic(), False)
            print(f"[BAN][CHECK][ERROR] uid={uid} {type(e).__name__}: {e!r} -> fail-open")
            return False

    async def ban_user(self , user_id: int , username: Optional [ str ] , name: Optional [ str ] ,
                       reason: Optional [ str ]):
        """Добавляет пользователя в таблицу banusers с дополнительными данными."""
        print(f"🔒 Добавление пользователя с ID {user_id} в бан...")

        # Проверка, что пользователь не заблокирован
        if not await self.is_user_banned(user_id):
            current_date = datetime.now()  # Получаем объект datetime
            print(f"🕒 Текущая дата и время: {current_date}")
            print(f"📋 Данные для записи: ID={user_id}, Username={username}, Name={name}, Причина={reason}")

            try:
                async with self.pool.acquire() as connection:
                    # Вставка данных пользователя в таблицу
                    await connection.execute(
                        "INSERT INTO banusers (user_id, username, name, data, cause) VALUES ($1, $2, $3, $4, $5)" ,
                        user_id , username if username else None ,  # Если username пустой, передаем None
                        name if name else None ,  # Если name пустое, передаем None
                        current_date ,  # Передаем объект datetime
                        reason if reason else None  # Если причина пустая, передаем None
                    )

                print(f"✅ Пользователь с ID {user_id} успешно заблокирован.")
            except Exception as e:
                print(f"Ошибка при блокировке пользователя: {str(e)}")
        else:
            print(f"⚠️ Пользователь с ID {user_id} уже находится в бане.")

    async def get_group_info34(self , chat_id: int):
        """Получение информации о группе по chat_id."""
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT namechat, usernamechat FROM chat WHERE chat_id = $1" , chat_id)

            return result  # Возвращает кортеж или None, если группа не найдена.
        except Exception as e:
            print(f"Ошибка при получении информации о группе: {str(e)}")
            return None

    async def count_members_in_chat(self , chat_id: int) -> int:
        """Подсчитывает количество участников в чате по chat_id."""
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    "SELECT member FROM chat WHERE chat_id = $1" , chat_id)

            if result is not None:
                print(f"Количество участников в чате с ID {chat_id}: {result}")
                return result
            else:
                print(f"Чат с ID {chat_id} не найден или не имеет участников.")
                return 0
        except Exception as e:
            print(f"Ошибка при подсчете участников чата с ID {chat_id}: {e}")
            return 0

    async def get_top_user_in_groups(self):
        """Находит пользователей, которые написали наибольшее количество сообщений в каждом чате."""
        async with self.pool.acquire() as connection:
            # 1. Получаем все чаты
            chat_ids = await connection.fetch('SELECT chat_id FROM chat')
            chat_ids = [ chat [ 'chat_id' ] for chat in chat_ids ]

            top_users = {}

            # 2. Для каждого чата находим пользователя с наибольшим количеством сообщений
            for chat_id in chat_ids:
                # Получаем пользователя, который написал наибольшее количество сообщений в чате
                top_user = await connection.fetchrow(
                    'SELECT user_id, COUNT(*) as text '
                    'FROM chatchange '
                    'WHERE chat_id = $1 '
                    'GROUP BY user_id '
                    'ORDER BY text DESC '
                    'LIMIT 1' , chat_id)

                if top_user:
                    user_id = top_user [ 'user_id' ]
                    message_count = top_user [ 'text' ]
                    top_users [ chat_id ] = (user_id , message_count)

            return top_users
    async def get_user_top_groups(self , user_id):
        query = """
            SELECT chat_id, COUNT(*) AS text
            FROM chatchange
            WHERE user_id = ?
            GROUP BY chat_id
            ORDER BY text DESC
        """

        async with self.pool.acquire() as connection:
            rows = await connection.fetch(query , user_id)

        # Найти максимальное количество сообщений
        if not rows:
            return [ ]  # Пользователь не писал сообщений

        max_message_count = rows [ 0 ] [ 'message_count' ]

        # Вернуть идентификаторы групп с максимальным количеством сообщений
        top_groups = [ row [ 'chat_id' ] for row in rows if row [ 'message_count' ] == max_message_count ]
        return top_groups

    async def find_user_max_messages_in_chats(self , user_id: int):
        """Находит чат с максимальным количеством сообщений для пользователя с заданным user_id в каждой группе."""
        try:
            # Шаг 1: Получаем все chat_id из таблицы chat
            async with self.pool.acquire() as connection:
                chat_ids = await connection.fetch("SELECT chat_id FROM chat")

            if not chat_ids:
                print("Нет доступных групп.")
                return {}

            # Шаг 2: Создаем словарь для хранения максимальных сообщений для каждого чата
            chat_max_count = {}

            # Для каждого чата из таблицы chat ищем максимальное количество сообщений в таблице chatchange
            for chat in chat_ids:
                chat_id = chat [ 'chat_id' ]

                # Шаг 3: Для каждого chat_id открываем новое соединение и выполняем запрос
                async with self.pool.acquire() as connection:
                    results = await connection.fetch(
                        """
                        SELECT MAX(text) AS max_text
                        FROM chatchange
                        WHERE user_id = $1 AND chat_id = $2
                        GROUP BY chat_id
                        """ , user_id , chat_id)

                if results:
                    # Если для этого чата найдены результаты, сохраняем максимальное количество сообщений
                    max_message_count = results [ 0 ] [ 'max_text' ]
                    chat_max_count [ chat_id ] = max_message_count

            # Возвращаем словарь с chat_id и максимальным количеством сообщений для каждого чата
            return chat_max_count

        except Exception as e:
            print(f"Ошибка при поиске чатов для пользователя {user_id}: {e}")
            return {}

    async def get_member_count_by_chat_id(self , chat_id):
        """
        Получить количество участников в группе по chat_id.

        :param chat_id: Идентификатор чата (группы)
        :return: Количество участников (int) или None, если чат не найден
        """
        query = "SELECT member FROM chat WHERE chat_id = $1"

        async with self.pool.acquire() as connection:
            result = await connection.fetchval(query , chat_id)

        return result

    async def find_user_with_max_messages(self , chat_id: int , bot1):
        """Находит пользователя с максимальным количеством сообщений в группе с >= 100 участников."""
        try:
            async with self.pool.acquire() as connection:
                # Получаем количество участников через bot1
                member_count = await self.get_member_count_by_chat_id(chat_id)
                print('member_count : ',member_count)
                # Преобразуем member_count в целое число, чтобы избежать ошибки сравнения
                try:
                    member_count = int(member_count)
                except ValueError:
                    member_count = 0  # Если нельзя преобразовать в число, устанавливаем 0

                if member_count >= 1000:
                    # Если участников >= 100, находим пользователя с максимальным количеством сообщений
                    results = await connection.fetch(
                        "SELECT user_id, text FROM chatchange WHERE chat_id = $1" , chat_id)

                    if not results:
                        print(f"Нет сообщений для группы {chat_id}.")
                        return None  # Если данных нет, возвращаем None

                    max_count = 0
                    user_id_with_max = None

                    for record in results:
                        user_id , text = record [ 'user_id' ] , record [ 'text' ]
                        if text > max_count:
                            max_count = text
                            user_id_with_max = user_id

                    if user_id_with_max is not None:
                        print(
                            f"В группе {chat_id} пользователь с ID {user_id_with_max} написал максимальное количество сообщений: {max_count} (Количество участников: {member_count})")
                        return (user_id_with_max , max_count)  # Возвращаем кортеж с user_id и max_count
                else:
                    print(f"Группа {chat_id} не соответствует критерию (меньше 100 участников).")

            return None  # Если условие не выполнено или ошибка

        except Exception as e:
            print(f"Ошибка при выполнении поиска: {e}")
            return None  # Возвращаем None в случае ошибки
    async def get_user_subscription(self, user_id: int):
        """Возвращает значение подписки пользователя."""
        try:
            # Асинхронный запрос к базе данных
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(
                    "SELECT sub FROM users WHERE user_id = $1", user_id
                )

            if result:
                return result['sub']  # Возвращаем значение подписки из результата
            else:
                print(f"Пользователь с ID {user_id} не найден в таблице.")
                return None
        except Exception as e:
            print(f"Ошибка при получении подписки для пользователя {user_id}: {e}")
            return None

    async def update_subscription(self, user_id: int):
        """Обновляет подписку пользователя в таблице users."""
        try:
            # Асинхронный запрос для обновления подписки
            async with self.pool.acquire() as connection:
                await connection.execute(
                    "UPDATE users SET sub = 1 WHERE user_id = $1", user_id
                )
            print(f"Подписка пользователя {user_id} успешно обновлена.")
        except Exception as e:
            print(f"Ошибка при обновлении подписки для пользователя {user_id}: {e}")

    async def get_group_username(self, chat_id: int) -> Optional[str]:
        """Получение username чата по chat_id."""
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    "SELECT usernamechat FROM chat WHERE chat_id = $1", chat_id
                )
                return result  # Если результат не None, вернется значение, иначе None
        except Exception as e:
            print(f"Ошибка при получении username чата: {e}")
            return None

    async def get_user_bio(self , user_id: int):
        """Получение bio пользователя по user_id."""
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    "SELECT bio FROM users WHERE user_id = $1" , user_id)
                return result  # Вернет значение bio или None
        except Exception as e:
            print(f"Ошибка при получении bio пользователя: {e}")
            return None

    async def check_and_update_bio(self, user_id: int, bot1):
        """Проверка и обновление биографии пользователя."""
        # Проверка наличия user_id в кэше
        if user_id in self.cache_bio:
            # Если данные в кэше, используем их
            current_bio = self.cache_bio[user_id]
        else:
            # Получаем текущее описание профиля пользователя
            user = await bot1.get_chat(user_id)
            current_bio = user.bio if user.bio else None  # Устанавливаем в None, если bio отсутствует

            # Сохраняем в кэш
            self.cache_bio[user_id] = current_bio

        async with self.pool.acquire() as connection:
            result = await connection.fetchrow("SELECT bio FROM users WHERE user_id = $1", user_id)

            if not result:
                print(f"Пользователь с user_id {user_id} не найден.")
                return

            # Сравниваем текущую биографию с сохраненной и обновляем только при изменении
            stored_bio = result['bio']
            if stored_bio != current_bio:
                await connection.execute(
                    "UPDATE users SET bio = $1 WHERE user_id = $2", current_bio, user_id
                )
                print(f"Описание пользователя с user_id {user_id} было обновлено на новое: {current_bio}")
            else:
                print(f"Описание профиля пользователя с user_id {user_id} уже совпадает с текущим и не требует обновления.")

    async def delete_chat_by_id(self, chat_id: int):
        """Удаление записи о чате из таблицы chat по chat_id."""
        try:
            async with self.pool.acquire() as connection:
                await connection.execute("DELETE FROM chat WHERE chat_id = $1", chat_id)
                print(f"Чат с ID {chat_id} успешно удалён.")
        except Exception as e:
            print(f"Ошибка при удалении чата с ID {chat_id}: {e}")

    async def add_user_to_chatchange(self , user_id: int , chat_id: int):
        """
        Добавление или обновление записи пользователя в таблице chatchange.
        ВАЖНО:
        - chatchange.text  -> bigint
        - chatchange.date  -> date
        """
        try:
            now_dt = datetime.now()
            today_date = now_dt.date()

            async with self.pool.acquire() as connection:
                await connection.execute(
                    '''
                    UPDATE users
                    SET last_active = $1
                    WHERE user_id = $2
                    ''' , now_dt , user_id)

                row = await connection.fetchrow(
                    '''
                    SELECT text
                    FROM chatchange
                    WHERE user_id = $1
                      AND chat_id = $2
                      AND date = $3
                    LIMIT 1
                    ''' , user_id , chat_id , today_date)

                if row:
                    await connection.execute(
                        '''
                        UPDATE chatchange
                        SET text = COALESCE(text, 0) + 1
                        WHERE user_id = $1
                          AND chat_id = $2
                          AND date = $3
                        ''' , user_id , chat_id , today_date)
                else:
                    await connection.execute(
                        '''
                        INSERT INTO chatchange (user_id, chat_id, date, text)
                        VALUES ($1, $2, $3, $4)
                        ''' , user_id , chat_id , today_date , 1)

                print(f"Данные для user_id {user_id} в чате {chat_id} были успешно обновлены/добавлены.")

        except Exception as e:
            print(f"Ошибка при добавлении пользователя в chatchange: {e}")

    async def get_user_by_chat_id_count(self , chat_id: int) -> int:
        """
        Количество уникальных пользователей, писавших в этом чате.
        """
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    '''
                    SELECT COUNT(DISTINCT user_id)
                    FROM chatchange
                    WHERE chat_id = $1
                    ''' , chat_id)
                return int(result or 0)
        except Exception as e:
            print(f"Ошибка при получении количества пользователей чата {chat_id}: {e}")
            return 0

    # =========================================================
    # HELPERS
    # =========================================================

    def _normalize_date_value(self , value):
        """
        Приводит входное значение к типу date.
        Поддерживает:
        - datetime.date
        - datetime.datetime
        - строку 'YYYY-MM-DD'
        """
        if isinstance(value , date) and not isinstance(value , datetime):
            return value

        if isinstance(value , datetime):
            return value.date()

        if isinstance(value , str):
            return datetime.strptime(value , "%Y-%m-%d").date()

        raise ValueError(f"Неподдерживаемый формат даты: {value!r}")

    def _get_month_bounds(self , year: int , month: int):
        """
        Возвращает (start_date, end_date) для месяца.
        """
        start_date = date(int(year) , int(month) , 1)

        if int(month) == 12:
            end_date = date(int(year) + 1 , 1 , 1) - timedelta(days=1)
        else:
            end_date = date(int(year) , int(month) + 1 , 1) - timedelta(days=1)

        return start_date , end_date

    # =========================================================
    # STATS / CHATCHANGE
    # =========================================================

    async def get_available_days(self , chat_id: int , limit: int = 400):
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    '''
                    SELECT date
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date IS NOT NULL
                    GROUP BY date
                    ORDER BY date DESC
                    LIMIT $2
                    ''' , chat_id , int(limit))

                return [ row [ "date" ].strftime("%Y-%m-%d") for row in rows ] if rows else [ ]

        except Exception as e:
            print(f"Ошибка при получении доступных дней для чата {chat_id}: {e}")
            return [ ]

    async def get_available_weeks(self , chat_id: int , limit: int = 200):
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    '''
                    SELECT DATE_TRUNC('week', date)::date AS week_start
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date IS NOT NULL
                    GROUP BY week_start
                    ORDER BY week_start DESC
                    LIMIT $2
                    ''' , chat_id , int(limit))

                return [ row [ "week_start" ].strftime("%Y-%m-%d") for row in rows ] if rows else [ ]

        except Exception as e:
            print(f"Ошибка при получении доступных недель для чата {chat_id}: {e}")
            return [ ]

    async def get_available_months(self , chat_id: int , limit: int = 120):
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    '''
                    SELECT
                        EXTRACT(YEAR FROM date)::INT AS year,
                        EXTRACT(MONTH FROM date)::INT AS month
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date IS NOT NULL
                    GROUP BY year, month
                    ORDER BY year DESC, month DESC
                    LIMIT $2
                    ''' , chat_id , int(limit))

                return [ (int(row [ "year" ]) , int(row [ "month" ])) for row in rows ] if rows else [ ]

        except Exception as e:
            print(f"Ошибка при получении доступных месяцев для чата {chat_id}: {e}")
            return [ ]

    # =========================================================
    # TODAY
    # =========================================================

    async def get_total_messages_today(self , chat_id: int) -> int:
        try:
            today_date = datetime.now().date()

            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    '''
                    SELECT COALESCE(SUM(text), 0)
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date = $2
                      AND text IS NOT NULL
                    ''' , chat_id , today_date)

                return int(result or 0)

        except Exception as e:
            print(f"Ошибка при получении общего числа сообщений для чата {chat_id}: {e}")
            return 0

    async def get_user_message_count_today(self , chat_id: int , user_id: int) -> int:
        try:
            today_date = datetime.now().date()

            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    '''
                    SELECT COALESCE(SUM(text), 0)
                    FROM chatchange
                    WHERE chat_id = $1
                      AND user_id = $2
                      AND date = $3
                      AND text IS NOT NULL
                    ''' , chat_id , user_id , today_date)

                return int(result or 0)

        except Exception as e:
            print(f"Ошибка при получении числа сообщений для пользователя {user_id} в чате {chat_id}: {e}")
            return 0

    async def get_staff_daily_counts(self, user_id: int) -> Dict[int, int]:
        """
        Возвращает {chat_id: сколько сообщений пользователь написал СЕГОДНЯ}
        по каждой официальной группе (MuteConfig.STAFF_CHAT_IDS).
        Группы без сообщений присутствуют со значением 0.
        При ошибке БД возвращает то, что успели собрать (по умолчанию нули).
        """
        result: Dict[int, int] = {}
        if not self.pool:
            return result

        try:
            from bot.admins.mute import MuteConfig
        except Exception as e:
            print(f"[STAFF_DAILY][CFG][WARN] {e!r}")
            return result

        staff_ids = [int(c) for c in MuteConfig.STAFF_CHAT_IDS]
        if not staff_ids:
            return result

        for cid in staff_ids:
            result[cid] = 0

        today = date.today()
        query = """
            SELECT chat_id, COALESCE(SUM(text), 0) AS total
            FROM chatchange
            WHERE user_id = $1
              AND date = $2
              AND text IS NOT NULL
              AND chat_id = ANY($3::bigint[])
            GROUP BY chat_id
        """
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(query, int(user_id), today, staff_ids)
                for row in rows:
                    result[int(row["chat_id"])] = int(row["total"] or 0)
        except Exception as e:
            print(f"[STAFF_DAILY][ERROR] uid={user_id}: {e!r}")
        return result

    async def get_daily_messages9999(self, user_id: int) -> bool:
        """
        Проверяет, написал ли пользователь СЕГОДНЯ не менее
        MESSAGE_CHECK_WITHDRAWAL сообщений хотя бы в ОДНОЙ из официальных
        групп проекта (MuteConfig.STAFF_CHAT_IDS).

        Важно по логике порога: считается активность в пределах ОДНОЙ группы
        (не суммарно по всем). Берём максимум дневных сумм по каждой группе и
        сравниваем с порогом — так «250 в одной группе» работает корректно,
        даже если в chatchange окажется несколько строк на (user, chat, дата).

        Таблица chatchange:
            user_id  -> кто писал
            chat_id  -> где писал
            date     -> дата (DATE), формат ГГГГ-ММ-ДД
            text     -> сколько сообщений написал за эту дату в этой группе

        Возвращает:
            True  — условие выполнено (в какой-то группе >= порога),
                    либо проверка отключена/недоступна;
            False — не хватило сообщений ни в одной группе.

        При ошибке БД безопасно возвращает True (не блокирует вывод игрока).
        """
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        # Настройки берём лениво, чтобы не плодить циклические импорты на старте.
        try:
            from bot.admins.mute import MuteConfig
            from bot.config.config import MESSAGE_CHECK_WITHDRAWAL
        except Exception as e:
            print(f"[DAILY_MSG][CFG][WARN] не удалось прочитать настройки: {e!r} -> пропускаем")
            return True

        threshold = int(MESSAGE_CHECK_WITHDRAWAL or 0)
        if threshold <= 0:
            return True  # проверка отключена

        staff_ids = [int(c) for c in MuteConfig.STAFF_CHAT_IDS]
        if not staff_ids:
            return True  # нет официальных групп — проверять нечего

        today_date = date.today()

        # Максимум дневных сумм по каждой группе → «набрано в одной группе».
        query = """
            SELECT COALESCE(MAX(per_chat.total), 0) AS best
            FROM (
                SELECT chat_id, SUM(text) AS total
                FROM chatchange
                WHERE user_id = $1
                  AND date = $2
                  AND text IS NOT NULL
                  AND chat_id = ANY($3::bigint[])
                GROUP BY chat_id
            ) AS per_chat
        """

        try:
            async with self.pool.acquire() as connection:
                best = await connection.fetchval(query, user_id, today_date, staff_ids)
                best_i = int(best or 0)
                ok = best_i >= threshold
                print(
                    f"[DAILY_MSG] uid={user_id} best_in_group={best_i} "
                    f"threshold={threshold} ok={ok}"
                )
                return ok
        except asyncpg.PostgresError as e:
            print(f"[DAILY_MSG][DB_ERROR] uid={user_id}: {e!r} -> пропускаем (не блокируем)")
            return True  # при ошибке БД не блокируем вывод
        except Exception as e:
            print(f"[DAILY_MSG][ERROR] uid={user_id}: {e!r} -> пропускаем (не блокируем)")
            return True

    async def get_top_users_today(self , chat_id: int , limit: int = 30):
        try:
            today_date = datetime.now().date()

            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    '''
                    SELECT user_id, COALESCE(SUM(text), 0) AS total_messages
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date = $2
                      AND text IS NOT NULL
                    GROUP BY user_id
                    ORDER BY total_messages DESC, user_id ASC
                    LIMIT $3
                    ''' , chat_id , today_date , int(limit))

                return rows if rows else [ ]

        except Exception as e:
            print(f"Ошибка при получении топ пользователей за сегодня: {e}")
            return [ ]

    async def find_user_with_max_messages(self , chat_id: int , bot1=None):
        try:
            today_date = datetime.now().date()

            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    '''
                    SELECT user_id, COALESCE(SUM(text), 0) AS total_messages
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date = $2
                      AND text IS NOT NULL
                    GROUP BY user_id
                    ORDER BY total_messages DESC, user_id ASC
                    LIMIT 1
                    ''' , chat_id , today_date)

                if not row:
                    return None

                return int(row [ "user_id" ]) , int(row [ "total_messages" ])

        except Exception as e:
            print(f"Ошибка при поиске пользователя с максимумом сообщений за сегодня: {e}")
            return None

    # =========================================================
    # EXACT DAY
    # =========================================================

    def _normalize_stats_limit(self , limit: int , default: int = 30 , max_limit: int = 100) -> int:
        try:
            value = int(limit)
        except Exception:
            value = int(default)

        if value < 1:
            return 1

        return min(value , int(max_limit))

    def _decode_top_users_payload(self , payload) -> list[tuple[int , int]]:
        if not payload:
            return [ ]

        data = payload

        try:
            if isinstance(data , str):
                data = json.loads(data)
        except Exception:
            return [ ]

        if not isinstance(data , list):
            return [ ]

        result = [ ]
        for item in data:
            try:
                if isinstance(item , (list , tuple)) and len(item) >= 2:
                    uid = int(item [ 0 ])
                    cnt = int(item [ 1 ])
                    result.append((uid , cnt))
                    continue

                if isinstance(item , dict):
                    uid = int(item.get("user_id" , 0))
                    cnt = int(item.get("total_messages" , 0))
                    if uid != 0 or cnt != 0:
                        result.append((uid , cnt))
            except Exception:
                continue

        return result

    async def get_stats_snapshot_by_day(self , chat_id: int , user_id: int , day_str: str , limit: int = 30) -> dict:
        limit = self._normalize_stats_limit(limit)

        try:
            day_date = self._normalize_date_value(day_str)

            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    '''
                    WITH filtered AS (
                        SELECT user_id, COALESCE(SUM(text), 0)::BIGINT AS total_messages
                        FROM chatchange
                        WHERE chat_id = $1
                          AND date = $2
                          AND text IS NOT NULL
                        GROUP BY user_id
                    ),
                    top_rows AS (
                        SELECT user_id, total_messages
                        FROM filtered
                        ORDER BY total_messages DESC, user_id ASC
                        LIMIT $4
                    ),
                    agg AS (
                        SELECT COALESCE(SUM(total_messages), 0)::BIGINT AS total_messages
                        FROM filtered
                    ),
                    usr AS (
                        SELECT COALESCE((SELECT total_messages FROM filtered WHERE user_id = $3), 0)::BIGINT AS user_msg_count
                    ),
                    mx AS (
                        SELECT user_id, total_messages
                        FROM filtered
                        ORDER BY total_messages DESC, user_id ASC
                        LIMIT 1
                    )
                    SELECT
                        agg.total_messages AS total_messages,
                        usr.user_msg_count AS user_msg_count,
                        mx.user_id AS max_user_id,
                        COALESCE(mx.total_messages, 0)::BIGINT AS max_messages,
                        COALESCE(
                            json_agg(
                                json_build_array(top_rows.user_id, top_rows.total_messages)
                                ORDER BY top_rows.total_messages DESC, top_rows.user_id ASC
                            ) FILTER (WHERE top_rows.user_id IS NOT NULL),
                            '[]'::json
                        ) AS top_users
                    FROM agg
                    CROSS JOIN usr
                    LEFT JOIN mx ON TRUE
                    LEFT JOIN top_rows ON TRUE
                    GROUP BY agg.total_messages, usr.user_msg_count, mx.user_id, mx.total_messages
                    ''' , chat_id , day_date , user_id , limit)

            if not row:
                return {"top_users": [ ] , "total_messages": 0 , "user_msg_count": 0 , "max_messages_user": None}

            top_users = self._decode_top_users_payload(row [ "top_users" ])

            max_messages_user = None
            if row [ "max_user_id" ] is not None:
                max_messages_user = (int(row [ "max_user_id" ]) , int(row [ "max_messages" ] or 0))

            return {"top_users": top_users ,
                "total_messages": int(row [ "total_messages" ] or 0) ,
                "user_msg_count": int(row [ "user_msg_count" ] or 0) , "max_messages_user": max_messages_user}

        except Exception as e:
            print(
                f"Ошибка get_stats_snapshot_by_day(chat_id={chat_id}, user_id={user_id}, day={day_str}, limit={limit}): {e}")
            return {"top_users": [ ] , "total_messages": 0 , "user_msg_count": 0 , "max_messages_user": None}

    async def get_stats_snapshot_by_period(self , chat_id: int , user_id: int , start_date: str , end_date: str ,
            limit: int = 30) -> dict:
        limit = self._normalize_stats_limit(limit)

        try:
            start_date_obj = self._normalize_date_value(start_date)
            end_date_obj = self._normalize_date_value(end_date)

            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    '''
                    WITH filtered AS (
                        SELECT user_id, COALESCE(SUM(text), 0)::BIGINT AS total_messages
                        FROM chatchange
                        WHERE chat_id = $1
                          AND date IS NOT NULL
                          AND text IS NOT NULL
                          AND date BETWEEN $3 AND $4
                        GROUP BY user_id
                    ),
                    top_rows AS (
                        SELECT user_id, total_messages
                        FROM filtered
                        ORDER BY total_messages DESC, user_id ASC
                        LIMIT $5
                    ),
                    agg AS (
                        SELECT COALESCE(SUM(total_messages), 0)::BIGINT AS total_messages
                        FROM filtered
                    ),
                    usr AS (
                        SELECT COALESCE((SELECT total_messages FROM filtered WHERE user_id = $2), 0)::BIGINT AS user_msg_count
                    ),
                    mx AS (
                        SELECT user_id, total_messages
                        FROM filtered
                        ORDER BY total_messages DESC, user_id ASC
                        LIMIT 1
                    )
                    SELECT
                        agg.total_messages AS total_messages,
                        usr.user_msg_count AS user_msg_count,
                        mx.user_id AS max_user_id,
                        COALESCE(mx.total_messages, 0)::BIGINT AS max_messages,
                        COALESCE(
                            json_agg(
                                json_build_array(top_rows.user_id, top_rows.total_messages)
                                ORDER BY top_rows.total_messages DESC, top_rows.user_id ASC
                            ) FILTER (WHERE top_rows.user_id IS NOT NULL),
                            '[]'::json
                        ) AS top_users
                    FROM agg
                    CROSS JOIN usr
                    LEFT JOIN mx ON TRUE
                    LEFT JOIN top_rows ON TRUE
                    GROUP BY agg.total_messages, usr.user_msg_count, mx.user_id, mx.total_messages
                    ''' , chat_id , user_id , start_date_obj , end_date_obj , limit)

            if not row:
                return {"top_users": [ ] , "total_messages": 0 , "user_msg_count": 0 , "max_messages_user": None}

            top_users = self._decode_top_users_payload(row [ "top_users" ])

            max_messages_user = None
            if row [ "max_user_id" ] is not None:
                max_messages_user = (int(row [ "max_user_id" ]) , int(row [ "max_messages" ] or 0))

            return {"top_users": top_users ,
                "total_messages": int(row [ "total_messages" ] or 0) ,
                "user_msg_count": int(row [ "user_msg_count" ] or 0) , "max_messages_user": max_messages_user}

        except Exception as e:
            print(
                f"Ошибка get_stats_snapshot_by_period(chat_id={chat_id}, user_id={user_id}, range={start_date}-{end_date}, limit={limit}): {e}")
            return {"top_users": [ ] , "total_messages": 0 , "user_msg_count": 0 , "max_messages_user": None}

    async def get_stats_snapshot_month(self , chat_id: int , user_id: int , year: int , month: int ,
            limit: int = 30) -> dict:
        try:
            start_date , end_date = self._get_month_bounds(year , month)
            return await self.get_stats_snapshot_by_period(
                chat_id=chat_id , user_id=user_id , start_date=start_date.strftime('%Y-%m-%d') ,
                end_date=end_date.strftime('%Y-%m-%d') , limit=limit)
        except Exception as e:
            print(
                f"Ошибка get_stats_snapshot_month(chat_id={chat_id}, user_id={user_id}, year={year}, month={month}, limit={limit}): {e}")
            return {"top_users": [ ] , "total_messages": 0 , "user_msg_count": 0 , "max_messages_user": None}

    async def get_stats_snapshot_all_time(self , chat_id: int , user_id: int , limit: int = 30) -> dict:
        limit = self._normalize_stats_limit(limit)

        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    '''
                    WITH filtered AS (
                        SELECT user_id, COALESCE(SUM(CAST(text AS BIGINT)), 0)::BIGINT AS total_messages
                        FROM chatall
                        WHERE chat_id = $1
                        GROUP BY user_id
                    ),
                    top_rows AS (
                        SELECT user_id, total_messages
                        FROM filtered
                        ORDER BY total_messages DESC, user_id ASC
                        LIMIT $3
                    ),
                    agg AS (
                        SELECT COALESCE(SUM(total_messages), 0)::BIGINT AS total_messages
                        FROM filtered
                    ),
                    usr AS (
                        SELECT COALESCE((SELECT total_messages FROM filtered WHERE user_id = $2), 0)::BIGINT AS user_msg_count
                    ),
                    mx AS (
                        SELECT user_id, total_messages
                        FROM filtered
                        ORDER BY total_messages DESC, user_id ASC
                        LIMIT 1
                    )
                    SELECT
                        agg.total_messages AS total_messages,
                        usr.user_msg_count AS user_msg_count,
                        mx.user_id AS max_user_id,
                        COALESCE(mx.total_messages, 0)::BIGINT AS max_messages,
                        COALESCE(
                            json_agg(
                                json_build_array(top_rows.user_id, top_rows.total_messages)
                                ORDER BY top_rows.total_messages DESC, top_rows.user_id ASC
                            ) FILTER (WHERE top_rows.user_id IS NOT NULL),
                            '[]'::json
                        ) AS top_users
                    FROM agg
                    CROSS JOIN usr
                    LEFT JOIN mx ON TRUE
                    LEFT JOIN top_rows ON TRUE
                    GROUP BY agg.total_messages, usr.user_msg_count, mx.user_id, mx.total_messages
                    ''' , chat_id , user_id , limit)

            if not row:
                return {"top_users": [ ] , "total_messages": 0 , "user_msg_count": 0 , "max_messages_user": None}

            top_users = self._decode_top_users_payload(row [ "top_users" ])

            max_messages_user = None
            if row [ "max_user_id" ] is not None:
                max_messages_user = (int(row [ "max_user_id" ]) , int(row [ "max_messages" ] or 0))

            return {"top_users": top_users ,
                "total_messages": int(row [ "total_messages" ] or 0) ,
                "user_msg_count": int(row [ "user_msg_count" ] or 0) , "max_messages_user": max_messages_user}

        except Exception as e:
            print(f"Ошибка get_stats_snapshot_all_time(chat_id={chat_id}, user_id={user_id}, limit={limit}): {e}")
            return {"top_users": [ ] , "total_messages": 0 , "user_msg_count": 0 , "max_messages_user": None}

    async def get_total_messages_by_day(self , chat_id: int , day_str: str) -> int:
        try:
            day_date = self._normalize_date_value(day_str)

            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    '''
                    SELECT COALESCE(SUM(text), 0)
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date = $2
                      AND text IS NOT NULL
                    ''' , chat_id , day_date)

                return int(result or 0)

        except Exception as e:
            print(f"Ошибка при получении общего числа сообщений за день {day_str} для чата {chat_id}: {e}")
            return 0

    async def get_user_message_count_by_day(self , chat_id: int , user_id: int , day_str: str) -> int:
        try:
            day_date = self._normalize_date_value(day_str)

            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    '''
                    SELECT COALESCE(SUM(text), 0)
                    FROM chatchange
                    WHERE chat_id = $1
                      AND user_id = $2
                      AND date = $3
                      AND text IS NOT NULL
                    ''' , chat_id , user_id , day_date)

                return int(result or 0)

        except Exception as e:
            print(
                f"Ошибка при получении числа сообщений пользователя {user_id} за день {day_str} в чате {chat_id}: {e}")
            return 0

    async def get_top_users_by_day(self , chat_id: int , day_str: str , limit: int = 30):
        try:
            day_date = self._normalize_date_value(day_str)

            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    '''
                    SELECT user_id, COALESCE(SUM(text), 0) AS total_messages
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date = $2
                      AND text IS NOT NULL
                    GROUP BY user_id
                    ORDER BY total_messages DESC, user_id ASC
                    LIMIT $3
                    ''' , chat_id , day_date , int(limit))

                return rows if rows else [ ]

        except Exception as e:
            print(f"Ошибка при получении топ пользователей за день {day_str}: {e}")
            return [ ]

    async def find_user_with_max_messages_by_day(self , chat_id: int , day_str: str):
        try:
            day_date = self._normalize_date_value(day_str)

            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    '''
                    SELECT user_id, COALESCE(SUM(text), 0) AS total_messages
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date = $2
                      AND text IS NOT NULL
                    GROUP BY user_id
                    ORDER BY total_messages DESC, user_id ASC
                    LIMIT 1
                    ''' , chat_id , day_date)

                if not row:
                    return None

                return int(row [ "user_id" ]) , int(row [ "total_messages" ])

        except Exception as e:
            print(f"Ошибка при поиске пользователя с максимумом сообщений за день {day_str}: {e}")
            return None

    # =========================================================
    # 7 DAYS
    # =========================================================

    async def get_total_messages_7d(self , chat_id: int) -> int:
        try:
            start_date = datetime.now().date() - timedelta(days=6)
            end_date = datetime.now().date()

            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    '''
                    SELECT COALESCE(SUM(text), 0)
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date IS NOT NULL
                      AND text IS NOT NULL
                      AND date BETWEEN $2 AND $3
                    ''' , chat_id , start_date , end_date)

                return int(result or 0)

        except Exception as e:
            print(f"Ошибка при получении общего числа сообщений за 7 дней для чата {chat_id}: {e}")
            return 0

    async def get_user_message_count_7d(self , chat_id: int , user_id: int) -> int:
        try:
            start_date = datetime.now().date() - timedelta(days=6)
            end_date = datetime.now().date()

            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    '''
                    SELECT COALESCE(SUM(text), 0)
                    FROM chatchange
                    WHERE chat_id = $1
                      AND user_id = $2
                      AND date IS NOT NULL
                      AND text IS NOT NULL
                      AND date BETWEEN $3 AND $4
                    ''' , chat_id , user_id , start_date , end_date)

                return int(result or 0)

        except Exception as e:
            print(f"Ошибка при получении числа сообщений пользователя {user_id} за 7 дней в чате {chat_id}: {e}")
            return 0

    async def get_top_users_7d(self , chat_id: int , limit: int = 30):
        try:
            start_date = datetime.now().date() - timedelta(days=6)
            end_date = datetime.now().date()

            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    '''
                    SELECT user_id, COALESCE(SUM(text), 0) AS total_messages
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date IS NOT NULL
                      AND text IS NOT NULL
                      AND date BETWEEN $2 AND $3
                    GROUP BY user_id
                    ORDER BY total_messages DESC, user_id ASC
                    LIMIT $4
                    ''' , chat_id , start_date , end_date , int(limit))

                return rows if rows else [ ]

        except Exception as e:
            print(f"Ошибка при получении топ пользователей за 7 дней: {e}")
            return [ ]

    async def find_user_with_max_messages_7d(self , chat_id: int):
        try:
            start_date = datetime.now().date() - timedelta(days=6)
            end_date = datetime.now().date()

            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    '''
                    SELECT user_id, COALESCE(SUM(text), 0) AS total_messages
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date IS NOT NULL
                      AND text IS NOT NULL
                      AND date BETWEEN $2 AND $3
                    GROUP BY user_id
                    ORDER BY total_messages DESC, user_id ASC
                    LIMIT 1
                    ''' , chat_id , start_date , end_date)

                if not row:
                    return None

                return int(row [ "user_id" ]) , int(row [ "total_messages" ])

        except Exception as e:
            print(f"Ошибка при поиске пользователя с максимумом сообщений за 7 дней: {e}")
            return None

    # =========================================================
    # CUSTOM PERIOD
    # =========================================================

    async def get_total_messages_by_period(self , chat_id: int , start_date: str , end_date: str) -> int:
        try:
            start_date_obj = self._normalize_date_value(start_date)
            end_date_obj = self._normalize_date_value(end_date)

            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    '''
                    SELECT COALESCE(SUM(text), 0)
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date IS NOT NULL
                      AND text IS NOT NULL
                      AND date BETWEEN $2 AND $3
                    ''' , chat_id , start_date_obj , end_date_obj)

                return int(result or 0)

        except Exception as e:
            print(
                f"Ошибка при получении общего числа сообщений за период {start_date} - {end_date} для чата {chat_id}: {e}")
            return 0

    async def get_user_message_count_by_period(self , chat_id: int , user_id: int , start_date: str ,
                                               end_date: str) -> int:
        try:
            start_date_obj = self._normalize_date_value(start_date)
            end_date_obj = self._normalize_date_value(end_date)

            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    '''
                    SELECT COALESCE(SUM(text), 0)
                    FROM chatchange
                    WHERE chat_id = $1
                      AND user_id = $2
                      AND date IS NOT NULL
                      AND text IS NOT NULL
                      AND date BETWEEN $3 AND $4
                    ''' , chat_id , user_id , start_date_obj , end_date_obj)

                return int(result or 0)

        except Exception as e:
            print(
                f"Ошибка при получении числа сообщений пользователя {user_id} за период {start_date} - {end_date} в чате {chat_id}: {e}")
            return 0

    async def get_top_users_by_period(self , chat_id: int , start_date: str , end_date: str , limit: int = 30):
        try:
            start_date_obj = self._normalize_date_value(start_date)
            end_date_obj = self._normalize_date_value(end_date)

            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    '''
                    SELECT user_id, COALESCE(SUM(text), 0) AS total_messages
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date IS NOT NULL
                      AND text IS NOT NULL
                      AND date BETWEEN $2 AND $3
                    GROUP BY user_id
                    ORDER BY total_messages DESC, user_id ASC
                    LIMIT $4
                    ''' , chat_id , start_date_obj , end_date_obj , int(limit))

                return rows if rows else [ ]

        except Exception as e:
            print(f"Ошибка при получении топ пользователей за период {start_date} - {end_date}: {e}")
            return [ ]

    async def find_user_with_max_messages_by_period(self , chat_id: int , start_date: str , end_date: str):
        try:
            start_date_obj = self._normalize_date_value(start_date)
            end_date_obj = self._normalize_date_value(end_date)

            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    '''
                    SELECT user_id, COALESCE(SUM(text), 0) AS total_messages
                    FROM chatchange
                    WHERE chat_id = $1
                      AND date IS NOT NULL
                      AND text IS NOT NULL
                      AND date BETWEEN $2 AND $3
                    GROUP BY user_id
                    ORDER BY total_messages DESC, user_id ASC
                    LIMIT 1
                    ''' , chat_id , start_date_obj , end_date_obj)

                if not row:
                    return None

                return int(row [ "user_id" ]) , int(row [ "total_messages" ])

        except Exception as e:
            print(f"Ошибка при поиске пользователя с максимумом сообщений за период {start_date} - {end_date}: {e}")
            return None

    # =========================================================
    # MONTH
    # =========================================================

    async def get_total_messages_month(self , chat_id: int , year: int , month: int) -> int:
        try:
            start_date , end_date = self._get_month_bounds(year , month)

            return await self.get_total_messages_by_period(
                chat_id , start_date.strftime('%Y-%m-%d') , end_date.strftime('%Y-%m-%d'))

        except Exception as e:
            print(f"Ошибка при получении общего числа сообщений за месяц для чата {chat_id}: {e}")
            return 0

    async def get_user_message_count_month(self , chat_id: int , user_id: int , year: int , month: int) -> int:
        try:
            start_date , end_date = self._get_month_bounds(year , month)

            return await self.get_user_message_count_by_period(
                chat_id , user_id , start_date.strftime('%Y-%m-%d') , end_date.strftime('%Y-%m-%d'))

        except Exception as e:
            print(f"Ошибка при получении числа сообщений пользователя {user_id} за месяц в чате {chat_id}: {e}")
            return 0

    async def get_top_users_month(self , chat_id: int , year: int , month: int , limit: int = 30):
        try:
            start_date , end_date = self._get_month_bounds(year , month)

            return await self.get_top_users_by_period(
                chat_id , start_date.strftime('%Y-%m-%d') , end_date.strftime('%Y-%m-%d') , limit=limit)

        except Exception as e:
            print(f"Ошибка при получении топ пользователей за месяц: {e}")
            return [ ]

    async def find_user_with_max_messages_month(self , chat_id: int , year: int , month: int):
        try:
            start_date , end_date = self._get_month_bounds(year , month)

            return await self.find_user_with_max_messages_by_period(
                chat_id , start_date.strftime('%Y-%m-%d') , end_date.strftime('%Y-%m-%d'))

        except Exception as e:
            print(f"Ошибка при поиске пользователя с максимумом сообщений за месяц: {e}")
            return None

    # =========================================================
    # ALL TIME
    # =========================================================

    async def get_total_messages(self , chat_id: int) -> int:
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    '''
                    SELECT COALESCE(SUM(text), 0)
                    FROM chatchange
                    WHERE chat_id = $1
                      AND text IS NOT NULL
                    ''' , chat_id)

                return int(result or 0)

        except Exception as e:
            print(f"Ошибка при получении общего числа сообщений за всё время для чата {chat_id}: {e}")
            return 0

    async def get_user_message_count(self , chat_id: int , user_id: int) -> int:
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchval(
                    '''
                    SELECT COALESCE(SUM(text), 0)
                    FROM chatchange
                    WHERE chat_id = $1
                      AND user_id = $2
                      AND text IS NOT NULL
                    ''' , chat_id , user_id)

                return int(result or 0)

        except Exception as e:
            print(f"Ошибка при получении числа сообщений пользователя {user_id} за всё время в чате {chat_id}: {e}")
            return 0

    async def get_top_users1(self , chat_id: int , limit: int = 30):
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    '''
                    SELECT user_id, COALESCE(SUM(text), 0) AS total_messages
                    FROM chatchange
                    WHERE chat_id = $1
                      AND text IS NOT NULL
                    GROUP BY user_id
                    ORDER BY total_messages DESC, user_id ASC
                    LIMIT $2
                    ''' , chat_id , int(limit))

                return rows if rows else [ ]

        except Exception as e:
            print(f"Ошибка при получении топ пользователей за всё время: {e}")
            return [ ]

    async def find_user_with_max_messages_all(self , chat_id: int):
        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    '''
                    SELECT user_id, COALESCE(SUM(text), 0) AS total_messages
                    FROM chatchange
                    WHERE chat_id = $1
                      AND text IS NOT NULL
                    GROUP BY user_id
                    ORDER BY total_messages DESC, user_id ASC
                    LIMIT 1
                    ''' , chat_id)

                if not row:
                    return None

                return int(row [ "user_id" ]) , int(row [ "total_messages" ])

        except Exception as e:
            print(f"Ошибка при поиске пользователя с максимумом сообщений за всё время: {e}")
            return None

    # =========================================================
    # OTHER CHAT TABLES
    # =========================================================

    async def update_banchat_info(self , chat_id: int , namechat: str , usernamechat: str , chatlink: str):
        """Обновление информации о группе в таблице banchat."""
        try:
            async with self.pool.acquire() as connection:
                ban_row = await connection.fetchrow(
                    '''
                    SELECT 1
                    FROM banchat
                    WHERE chat_id = $1
                    LIMIT 1
                    ''' , chat_id)

                if ban_row:
                    await connection.execute(
                        '''
                        UPDATE banchat
                        SET
                            namechat = $1,
                            usernamechat = $2,
                            chatlink = $3
                        WHERE chat_id = $4
                        ''' , namechat , usernamechat , chatlink , chat_id)
                    print(f"Информация о группе с chat_id {chat_id} обновлена.")
                else:
                    print(f"Группа с chat_id {chat_id} не найдена в таблице banchat.")
        except Exception as e:
            print(f"Ошибка при обновлении информации о группе: {e}")

    async def update_or_insert_chatall(self , chat_id , user_id):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    '''
                    INSERT INTO chatall (chat_id, user_id, text)
                    VALUES ($1, $2, 1)
                    ON CONFLICT (chat_id, user_id)
                    DO UPDATE SET text = COALESCE(chatall.text, 0) + 1
                    ''' , chat_id , user_id)
        except Exception:
            try:
                async with self.pool.acquire() as conn:
                    result = await conn.fetchrow(
                        'SELECT 1 FROM chatall WHERE chat_id = $1 AND user_id = $2 LIMIT 1',
                        chat_id , user_id)
                    if result:
                        await conn.execute(
                            'UPDATE chatall SET text = COALESCE(text, 0) + 1 WHERE chat_id = $1 AND user_id = $2',
                            chat_id , user_id)
                    else:
                        await conn.execute(
                            'INSERT INTO chatall (chat_id, text, user_id) VALUES ($1, 1, $2)',
                            chat_id , user_id)
            except Exception as e:
                print(f"Ошибка chatall: {e}")

    async def increment_chat_message_count(self , chat_id):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    'UPDATE chat SET text = COALESCE(text, 0) + 1 WHERE chat_id = $1',
                    chat_id)
        except Exception as e:
            print(f"increment_chat_message_count({chat_id}): {e}")

    def record_message(self, user_id: int, chat_id: int) -> None:
        """
        Засчитывает одно сообщение пользователя в группе и СРАЗУ планирует
        запись в БД (фоновой задачей, не блокируя ответ пользователю).

        +1 кладётся в буфер (мгновенно, без await), затем на этот же тик
        событийного цикла ставится задача flush_message_counters(), которая
        пишет накопленное в chatchange/chat. Несколько сообщений подряд
        естественно коалесируются в один UPDATE (буфер снимается атомарно),
        поэтому «написал → тут же записалось», без ожидания интервала.

        Дикты меняются только в синхронных участках (между чтением и
        присваиванием нет await), поэтому блокировка не нужна — цикл событий
        однопоточный.
        """
        try:
            uid = int(user_id)
            cid = int(chat_id)
        except Exception:
            return
        if uid <= 0 or cid == 0:
            return
        self._pending_user_counts[(uid, cid)] = self._pending_user_counts.get((uid, cid), 0) + 1
        self._pending_chat_counts[cid] = self._pending_chat_counts.get(cid, 0) + 1

        # Немедленная запись: планируем flush на ближайший тик event loop.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            loop.create_task(self.flush_message_counters())
            # Периодический цикл — подстраховка: дозапишет дельты, которые
            # вернулись в буфер после сбоя БД. Стартуем лениво, один раз.
            if not self._msg_counter_worker_started:
                try:
                    self.start_message_counter_flush_loop()
                except RuntimeError:
                    pass

    async def flush_message_counters(self) -> None:
        """
        Сбрасывает накопленные счётчики сообщений в БД одной транзакцией:
            _pending_user_counts -> chatchange: +N сообщений пользователя за
                                     СЕГОДНЯ в конкретной группе
                                     (UPSERT по user_id+chat_id+date);
            _pending_chat_counts -> chat.text: +N к общему счётчику группы.

        В chatchange нет уникального ограничения на (user_id, chat_id, date),
        поэтому делаем UPDATE, и если строк не затронуто — INSERT.

        При сбое БД накопленные дельты ВОЗВРАЩАЮТСЯ в буфер (ничего не теряем).
        """
        if not self.pool:
            return
        if not self._pending_user_counts and not self._pending_chat_counts:
            return

        # Атомарный «снимок»: подменяем буферы пустыми (между строками нет await).
        user_snapshot = self._pending_user_counts
        chat_snapshot = self._pending_chat_counts
        self._pending_user_counts = {}
        self._pending_chat_counts = {}

        user_items = [(uid, cid, cnt) for (uid, cid), cnt in user_snapshot.items() if cnt > 0]
        chat_items = [(cid, cnt) for cid, cnt in chat_snapshot.items() if cnt > 0]

        today = date.today()

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for uid, cid, cnt in user_items:
                        status = await conn.execute(
                            '''
                            UPDATE chatchange
                            SET text = COALESCE(text, 0) + $4
                            WHERE user_id = $1 AND chat_id = $2 AND date = $3
                            ''',
                            int(uid), int(cid), today, int(cnt),
                        )
                        try:
                            updated = int(str(status).split()[-1])
                        except Exception:
                            updated = 0
                        if updated == 0:
                            await conn.execute(
                                '''
                                INSERT INTO chatchange (user_id, chat_id, date, text)
                                VALUES ($1, $2, $3, $4)
                                ''',
                                int(uid), int(cid), today, int(cnt),
                            )

                    for cid, cnt in chat_items:
                        await conn.execute(
                            'UPDATE chat SET text = COALESCE(text, 0) + $2 WHERE chat_id = $1',
                            int(cid), int(cnt),
                        )
            _vdbg(f"[MSG_COUNTER][FLUSH][OK] users={len(user_items)} chats={len(chat_items)}")
        except Exception as e:
            # Возвращаем дельты обратно в буфер, чтобы не потерять счётчики.
            for (uid, cid), cnt in user_snapshot.items():
                self._pending_user_counts[(uid, cid)] = self._pending_user_counts.get((uid, cid), 0) + cnt
            for cid, cnt in chat_snapshot.items():
                self._pending_chat_counts[cid] = self._pending_chat_counts.get(cid, 0) + cnt
            _vdbg(f"[MSG_COUNTER][FLUSH][WARN] {type(e).__name__}: {e} (дельты возвращены в буфер)")

    def start_message_counter_flush_loop(self, interval: Optional[float] = None) -> None:
        """
        Запускает фоновый цикл, который раз в `interval` секунд пишет накопленные
        счётчики сообщений в БД. Идемпотентно: повторные вызовы игнорируются.
        Вызывать из уже работающего event loop (например, на старте бота).
        """
        if self._msg_counter_worker_started:
            return

        period = float(interval or self.MSG_COUNTER_FLUSH_INTERVAL_SEC)

        async def _loop() -> None:
            while True:
                await asyncio.sleep(period)
                try:
                    await self.flush_message_counters()
                except Exception as e:
                    _vdbg(f"[MSG_COUNTER][LOOP][WARN] {type(e).__name__}: {e}")

        # Флаг ставим ТОЛЬКО после успешного создания задачи: если event loop
        # ещё не запущен (RuntimeError), record_message() повторит попытку позже.
        asyncio.create_task(_loop())
        self._msg_counter_worker_started = True
        _vdbg(f"[MSG_COUNTER][LOOP] started (interval={period:.0f}s)")

    async def update_chat_message_count(self , chat_id):
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval(
                    '''
                    SELECT COALESCE(SUM(text), 0)
                    FROM chatall
                    WHERE chat_id = $1
                    ''' , chat_id)
                total_messages = int(result or 0)

                await conn.execute(
                    '''
                    UPDATE chat
                    SET text = $1
                    WHERE chat_id = $2
                    ''' , total_messages , chat_id)
                print(f"Обновлён счётчик сообщений для чата {chat_id}. Общее количество сообщений: {total_messages}")
        except Exception as e:
            print(f"Ошибка при обновлении счётчика сообщений для чата {chat_id}: {e}")

    async def update_or_insert_chatusers(self , chat_id , user_id):
        try:
            async with self.pool.acquire() as conn:
                user_row = await conn.fetchrow(
                    '''
                    SELECT 1
                    FROM chatusers
                    WHERE user_id = $1
                      AND chat_id = $2
                    LIMIT 1
                    ''' , user_id , chat_id)

                if user_row:
                    await conn.execute(
                        '''
                        UPDATE chatusers
                        SET text = COALESCE(text, 0) + 1
                        WHERE user_id = $1
                          AND chat_id = $2
                        ''' , user_id , chat_id)
                else:
                    await conn.execute(
                        '''
                        INSERT INTO chatusers (user_id, chat_id, text, timestamp)
                        VALUES ($1, $2, 1, $3)
                        ''' , user_id , chat_id , datetime.now())

                print(f"Данные чата обновлены для user_id={user_id}, chat_id={chat_id}")

        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL2: {e}")
            await asyncio.sleep(1)
            await self.update_or_insert_chatusers(chat_id , user_id)

        except Exception as e:
            print(f"Произошла ошибка: {e}")

    async def update_or_insert_banchat(self , chat_id , namechat , usernamechat , chatlink):
        try:
            async with self.pool.acquire() as conn:
                # Проверяем, существует ли запись для chat_id
                ban_row = await conn.fetchrow(
                    'SELECT * FROM banchat WHERE chat_id = $1' , chat_id)

                if ban_row:
                    # Если запись существует, обновляем её
                    await conn.execute(
                        '''UPDATE banchat SET namechat = $1, usernamechat = $2, chatlink = $3 
                           WHERE chat_id = $4''' , namechat , usernamechat , chatlink , chat_id)
                    print(f"Информация о группе с chat_id {chat_id} обновлена.")
                else:
                    # Если записи нет, вставляем новую запись
                    await conn.execute(
                        '''INSERT INTO banchat (chat_id, namechat, usernamechat, chatlink) 
                           VALUES ($1, $2, $3, $4)''' , chat_id , namechat , usernamechat , chatlink)
                    print(f"Новая группа с chat_id {chat_id} добавлена.")

        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL3: {e}")
        except Exception as e:
            print(f"Произошла ошибка: {e}")

    async def get_top_users(self , chat_id , limit=50):
        try:
            async with self.pool.acquire() as conn:
                # Выполняем запрос для получения топ пользователей
                users = await conn.fetch(
                    '''
                    SELECT user_id, text FROM chatusers 
                    WHERE chat_id = $1 
                    ORDER BY text DESC 
                    LIMIT $2
                    ''' , chat_id , limit)
                if not users:
                    print("Нет пользователей для данного чата.")
                    return [ ]  # Возвращаем пустой список, если нет данных
                return users
        except asyncpg.exceptions.PostgresError as e:
            print("Ошибка PostgreSQL4:" , e)
            return [ ]  # Возвращаем пустой список в случае ошибки с БД
        except Exception as e:
            print("Произошла ошибка:" , e)
            return [ ]  # Возвращаем пустой список в случае других ошибок

    async def get_top_users1(self , chat_id , limit=30):
        try:
            async with self.pool.acquire() as conn:
                # Выполняем запрос для получения топ пользователей из chatall
                users = await conn.fetch(
                    '''
                    SELECT user_id, text FROM chatall 
                    WHERE chat_id = $1 
                    ORDER BY text DESC 
                    LIMIT $2
                    ''' , chat_id , limit)
                return users
        except asyncpg.exceptions.PostgresError as e:
            print("Ошибка PostgreSQL5:" , e)
        except Exception as e:
            print("Произошла ошибка:" , e)

    async def get_total_messages(self , chat_id):
        try:
            async with self.pool.acquire() as conn:
                # Выполняем запрос для получения общей суммы сообщений из таблицы chatall
                result = await conn.fetchrow(
                    '''
                    SELECT COALESCE(SUM(CAST(text AS BIGINT)), 0) AS total
                    FROM chatall 
                    WHERE chat_id = $1
                    ''' , chat_id)
                # Используем COALESCE, чтобы заменить NULL на 0 в случае, если сообщений нет
                return result [ 'total' ] if result else 0
        except asyncpg.exceptions.PostgresError as e:
            print("Ошибка PostgreSQL:" , e)
        except Exception as e:
            print("Произошла ошибка:" , e)

    async def get_user_message_count(self , chat_id , user_id):
        try:
            async with self.pool.acquire() as conn:
                # Выполняем запрос для получения количества сообщений пользователя из таблицы chatall
                result = await conn.fetchrow(
                    '''
                    SELECT COALESCE(SUM(CAST(text AS BIGINT)), 0) AS total
                    FROM chatall 
                    WHERE chat_id = $1 AND user_id = $2
                    ''' , chat_id , user_id)
                # Используем COALESCE, чтобы заменить NULL на 0 в случае, если сообщений нет
                return result [ 'total' ] if result else 0
        except asyncpg.exceptions.PostgresError as e:
            print("Ошибка PostgreSQL7:" , e)
            return 0
        except Exception as e:
            print("Произошла ошибка:" , e)
            return 0

    async def get_top_users_7d(self, chat_id: int, limit: int = 30):
        """
        Топ пользователей по сумме сообщений за последние 7 дней (включая сегодня),
        на базе chatchange (chat_id, user_id, date, text).
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT user_id,
                           COALESCE(SUM(CAST(text AS BIGINT)), 0)::BIGINT AS total
                    FROM chatchange
                    WHERE chat_id = $1
                      AND (date)::date BETWEEN CURRENT_DATE - INTERVAL '6 days' AND CURRENT_DATE
                    GROUP BY user_id
                    ORDER BY total DESC
                    LIMIT $2
                    """,
                    chat_id, limit
                )
                return [(r["user_id"], r["total"]) for r in rows]
        except asyncpg.exceptions.PostgresError as e:
            print("Ошибка PostgreSQL [get_top_users_7d]:", e)
            return []
        except Exception as e:
            print("Произошла ошибка [get_top_users_7d]:", e)
            return []

    async def get_total_messages_7d(self, chat_id: int) -> int:
        """
        Общая сумма сообщений (text) за последние 7 дней в чате (chatchange).
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT COALESCE(SUM(CAST(text AS BIGINT)), 0)::BIGINT AS total
                    FROM chatchange
                    WHERE chat_id = $1
                      AND (date)::date BETWEEN CURRENT_DATE - INTERVAL '6 days' AND CURRENT_DATE
                    """,
                    chat_id
                )
                return int(row["total"]) if row and row["total"] is not None else 0
        except asyncpg.exceptions.PostgresError as e:
            print("Ошибка PostgreSQL [get_total_messages_7d]:", e)
            return 0
        except Exception as e:
            print("Произошла ошибка [get_total_messages_7d]:", e)
            return 0

    async def get_user_message_count_7d(self, chat_id: int, user_id: int) -> int:
        """
        Сколько конкретный пользователь написал за последние 7 дней (chatchange).
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT COALESCE(SUM(CAST(text AS BIGINT)), 0)::BIGINT AS total
                    FROM chatchange
                    WHERE chat_id = $1
                      AND user_id = $2
                      AND (date)::date BETWEEN CURRENT_DATE - INTERVAL '6 days' AND CURRENT_DATE
                    """,
                    chat_id, user_id
                )
                return int(row["total"]) if row and row["total"] is not None else 0
        except asyncpg.exceptions.PostgresError as e:
            print("Ошибка PostgreSQL [get_user_message_count_7d]:", e)
            return 0
        except Exception as e:
            print("Произошла ошибка [get_user_message_count_7d]:", e)
            return 0

    async def find_user_with_max_messages_7d(self, chat_id: int):
        """
        Пользователь с максимальным числом сообщений за 7 дней (user_id, total) из chatchange.
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT user_id,
                           COALESCE(SUM(CAST(text AS BIGINT)), 0)::BIGINT AS total
                    FROM chatchange
                    WHERE chat_id = $1
                      AND (date)::date BETWEEN CURRENT_DATE - INTERVAL '6 days' AND CURRENT_DATE
                    GROUP BY user_id
                    ORDER BY total DESC
                    LIMIT 1
                    """,
                    chat_id
                )
                if row:
                    return (row["user_id"], int(row["total"]))
                return None
        except asyncpg.exceptions.PostgresError as e:
            print("Ошибка PostgreSQL [find_user_with_max_messages_7d]:", e)
            return None
        except Exception as e:
            print("Произошла ошибка [find_user_with_max_messages_7d]:", e)
            return None

    async def get_daily_breakdown_7d(self, chat_id: int):
        """
        Суточная разбивка за 7 дней: [(day(date), total)], на базе chatchange.
        Удобно для графиков/диагностики.
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT (date)::date AS d,
                           COALESCE(SUM(CAST(text AS BIGINT)), 0)::BIGINT AS total
                    FROM chatchange
                    WHERE chat_id = $1
                      AND (date)::date BETWEEN CURRENT_DATE - INTERVAL '6 days' AND CURRENT_DATE
                    GROUP BY d
                    ORDER BY d ASC
                    """,
                    chat_id
                )
                return [(r["d"], int(r["total"])) for r in rows]
        except asyncpg.exceptions.PostgresError as e:
            print("Ошибка PostgreSQL [get_daily_breakdown_7d]:", e)
            return []
        except Exception as e:
            print("Произошла ошибка [get_daily_breakdown_7d]:", e)
            return []



    async def get_message_count(self, user_id):
        # Запрос для получения количества сообщений пользователя в каждом чате
        query = """
        SELECT chatname, SUM(text) as total_messages
        FROM chatall
        WHERE user_id = $1
        GROUP BY chatname
        """

        try:
            async with self.pool.acquire() as conn:
                # Выполнение запроса с асинхронным подключением
                results = await conn.fetch(query, user_id)

                # Формирование словаря с результатами
                message_count_by_chat = {row['chatname']: row['total_messages'] for row in results}

            return message_count_by_chat

        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL8: {e}")
            return {}
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return {}

    async def delete_users_after_24_hours(self , chat_id):
        # Ожидание 24 часа (72000 секунд)
        await asyncio.sleep(72000)

        try:
            # Подключаемся к базе данных через пул
            async with self.pool.acquire() as conn:
                # Выполняем запрос на удаление пользователей из чата
                await conn.execute('DELETE FROM chatusers WHERE chat_id = $1' , chat_id)
                print("Пользователи удалены после 24 часов.")
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL9: {e}")
        except Exception as e:
            print(f"Произошла ошибка: {e}")









    async def get_marriages_top_10_ordered_by_lovecoin(self):
        query = """
            SELECT user_id1, user_id2, lovecoin
            FROM marriages
            WHERE lovecoin > 0
            ORDER BY lovecoin DESC
            LIMIT 10
        """
        try:
            # Подключаемся к базе данных через пул
            async with self.pool.acquire() as conn:
                # Выполняем запрос и получаем результат
                top_10 = await conn.fetch(query)
                return top_10
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL0: {e}")
        except Exception as e:
            print(f"Произошла ошибка: {e}")

    async def get_marriages_xp(self, user_id):
        query = """
            SELECT xpp
            FROM users
            WHERE user_id = $1
        """
        try:
            # Подключаемся к базе данных через пул
            async with self.pool.acquire() as conn:
                # Выполняем запрос и получаем результат
                result = await conn.fetchrow(query, user_id)
                return result['xpp'] if result else 0
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL10: {e}")
        except Exception as e:
            print(f"Произошла ошибка: {e}")

    async def add_xp_to_marriage(self, user_id):
        try:
            # Проверяем, состоит ли пользователь в браке
            marriage = await self.is_user_married(user_id)
            if not marriage:
                return 0

            # Генерируем случайное количество XP за поцелуй
            xp = random.randint(1, 2)

            # Обновляем XP в таблице users для текущего пользователя
            query = "UPDATE users SET xpp = xpp + $1 WHERE user_id = $2"
            async with self.pool.acquire() as conn:
                await conn.execute(query, xp, user_id)

            return xp

        except Exception as e:
            print(f"Произошла ошибка при обновлении XP: {e}")
            return 0

    async def is_user_married(self , user_id):
        query = """
        SELECT * FROM marriages 
        WHERE user_id1 = $1 OR user_id2 = $1
        LIMIT 1
        """
        try:
            # Подключаемся к базе данных через пул
            async with self.pool.acquire() as conn:
                # Выполняем запрос и получаем результат
                result = await conn.fetchrow(query , user_id)
                return result
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL: {e}")
        except Exception as e:
            print(f"Произошла ошибка: {e}")

    async def add_xp_to_marriage(self , user_id):
        try:
            async with self.pool.acquire() as conn:
                # Найти существующий брак по user_id
                marriage = await conn.fetchrow(
                    """
                    SELECT id, xp FROM marriages 
                    WHERE user_id1 = $1 OR user_id2 = $1
                    LIMIT 1
                """ , user_id)

                if not marriage:
                    return 0  # Пользователь не в браке

                marriage_id = marriage [ "id" ]
                current_xp = marriage [ "xp" ] or 0
                new_xp = current_xp + 1

                # Обновить XP
                await conn.execute(
                    """
                    UPDATE marriages SET xp = $1 WHERE id = $2
                """ , new_xp , marriage_id)

                return new_xp

        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL при добавлении XP: {e}")
            return 0
        except Exception as e:
            print(f"Общая ошибка при добавлении XP: {e}")
            return 0


    async def get_marriages_top_10(self):
        query = """
        SELECT user_id1, user_id2, datetime
        FROM marriages
        ORDER BY datetime DESC
        LIMIT 10
        """
        try:
            # Подключаемся к базе данных через пул
            async with self.pool.acquire() as conn:
                # Выполняем запрос и получаем результаты
                top_10 = await conn.fetch(query)
                return top_10
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL12: {e}")
        except Exception as e:
            print(f"Произошла ошибка: {e}")


    async def get_marriages_top_10_ordered_by_duration(self):
        query = """
        SELECT user_id1, user_id2, datetime
        FROM marriages
        ORDER BY 
            (EXTRACT(EPOCH FROM NOW()) - EXTRACT(EPOCH FROM datetime)) DESC,
            datetime DESC
        LIMIT 10
        """
        try:
            # Подключаемся к базе данных через пул
            async with self.pool.acquire() as conn:
                # Выполняем запрос и получаем результаты
                top_10 = await conn.fetch(query)
                return top_10
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL13: {e}")
        except Exception as e:
            print(f"Произошла ошибка: {e}")











    async def delete_inactive_marriages(self):
        query = """
        WITH to_delete AS (
            SELECT rowid
            FROM marriages
            WHERE rowid NOT IN (
                SELECT MIN(rowid)
                FROM marriages
                GROUP BY user_id1, user_id2
            )
        )
        DELETE FROM marriages
        WHERE rowid IN (SELECT rowid FROM to_delete);
        """
        try:
            async with self.pool.acquire() as conn:
                # Выполняем запрос для удаления неактивных браков
                await conn.execute(query)
                print("Неактивные браки удалены.")
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL14: {e}")
        except Exception as e:
            print(f"Произошла ошибка: {e}")






#class que:
    #def __init__(self, db_file):
        #self.connection = sqlite3.connect(db_file)
        #self.cursor = self.connection.cursor()

    #def get_tasks(self):
        ## Извлекаем все задания из таблицы que1
        #with self.connection:
            #return self.cursor.execute("SELECT name FROM que1").fetchall()

    #def add_user_task(self, user_id, task_name, current_date):
        ## Добавляем пользователя и задание в таблицу que
        #with self.connection:
            #self.cursor.execute("INSERT INTO que (user_id, task_name, data) VALUES (?, ?, ?)",
                                #(user_id, task_name, current_date))
            #self.connection.commit()










    async def get_chat_username_by_id(self, chat_id):
        query = "SELECT usernamechat FROM chat WHERE chat_id = $1"
        try:
            async with self.pool.acquire() as conn:
                # Выполняем запрос для получения названия группы по chat_id
                result = await conn.fetchrow(query, chat_id)
                return result['usernamechat'] if result else None
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL15: {e}")
            return None
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return None

    async def get_chat_name_by_id(self, chat_id):
        query = "SELECT namechat FROM chat WHERE chat_id = $1"
        try:
            async with self.pool.acquire() as conn:
                # Выполняем запрос для получения названия группы по chat_id
                result = await conn.fetchrow(query, chat_id)
                return result['namechat'] if result else None
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL15: {e}")
            return None
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return None

    async def get_chat_link_by_id(self, chat_id):
        query = "SELECT chatlink FROM chat WHERE chat_id = $1"
        try:
            async with self.pool.acquire() as conn:
                # Выполняем запрос для получения ссылки на группу по chat_id
                result = await conn.fetchrow(query, chat_id)
                return result['chatlink'] if result else None
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL16: {e}")
            return None
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return None







    async def add_game_inline(self, user_id1, name_user1, user_id2, name_user2, namegame, username1=None, username2=None):
        """Добавить информацию о новой игре в таблицу."""
        try:
            data = datetime.now().strftime("%H:%M %d.%m.%Y")
            async with self.pool.acquire() as connection:
                await connection.execute(
                    """
                    INSERT INTO inline 
                    (user_id, name_user1, data, user_id2, name_user2, namegame, username1, username2) 
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    user_id1, name_user1, data, user_id2, name_user2, namegame, username1, username2
                )
            print("✅ Игра успешно добавлена в базу.")  # Отладка
        except Exception as e:
            print(f"❌ Ошибка при добавлении игры: {e}")  # Отладка

    # ============================================================
    # ✅ DB метод: снять с общего баланса чата
    # ============================================================
    async def update_total_balance_minus_db(self , chat_id: int , amount: int) -> Optional [ BalanceSnapshot ]:
        """
        Снимает amount только с ОСНОВНОГО баланса чата (chatbalance).

        LEGACY NOTE:
        - dexbalance заморожен и в списаниях не участвует
        - средства для выплат берём только из chatbalance
        """
        chat_id = int(chat_id)
        amount = int(amount)

        if amount <= 0:
            self.anarch_print(f"DB minus skip chat_id={chat_id}: amount <= 0")
            return None

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    row_before = await asyncio.wait_for(
                        conn.fetchrow(
                            """
                            SELECT
                                COALESCE(chatbalance, 0) AS chatbalance,
                                COALESCE(dexbalance, 0) AS dexbalance
                            FROM chat
                            WHERE chat_id = $1
                            LIMIT 1
                            FOR UPDATE
                            """ , int(chat_id)) , timeout=self.BALANCE_SELECT_TIMEOUT)

                    if row_before is None:
                        self.anarch_print(f"DB minus row=None chat_id={chat_id}")
                        return None

                    chat_balance_before = int(row_before [ "chatbalance" ] or 0)
                    dex_balance_before = int(row_before [ "dexbalance" ] or 0)

                    self.anarch_print(
                        f"DB minus start chat_id={chat_id} "
                        f"amount={amount} cb_before={chat_balance_before} "
                        f"dbx_before={dex_balance_before}")

                    # Должно хватать только основного баланса группы.
                    if chat_balance_before < amount:
                        self.anarch_print(
                            f"DB minus insufficient chat_id={chat_id} "
                            f"amount={amount} cb_before={chat_balance_before}")
                        return None

                    new_chat_balance = chat_balance_before - amount
                    new_dex_balance = dex_balance_before

                    row_after = await asyncio.wait_for(
                        conn.fetchrow(
                            """
                            UPDATE chat
                            SET
                                chatbalance = $1,
                                dexbalance = $2
                            WHERE chat_id = $3
                            RETURNING
                                COALESCE(chatbalance, 0) AS chatbalance,
                                COALESCE(dexbalance, 0) AS dexbalance
                            """ , int(new_chat_balance) , int(new_dex_balance) , int(chat_id)) ,
                        timeout=self.BALANCE_UPDATE_TIMEOUT)

                    if row_after is None:
                        self.anarch_print(f"DB minus update row=None chat_id={chat_id}")
                        return None

                    snap = BalanceSnapshot(
                        chatbalance=int(row_after [ "chatbalance" ] or 0) ,
                        dexbalance=int(row_after [ "dexbalance" ] or 0) , )

                    self.anarch_print(
                        f"DB minus OK chat_id={chat_id} "
                        f"amount={amount} cb_after={snap.chatbalance} dbx_after={snap.dexbalance}")
                    return snap

        except Exception as e:
            self.anarch_print(f"DB minus error chat_id={chat_id}: {e}")
            return None

    # ============================================================
    # 🧊 Холодный путь ДЛЯ МИНУСА: если строки нет - синк и проверка
    # ============================================================
    async def __ensure_chatrow_exists_for_minus__(self , bot , chat_id: int) -> bool:
        """
        Отдельный helper для минусовых операций.
        Не конфликтует с уже существующим __ensure_chatrow_exists__.
        """
        if self.__negguard_active__(chat_id):
            self.anarch_print(f"SYNC-MINUS skipped negguard chat_id={chat_id}")
            return False

        sync_fn = getattr(self , "group_sync_fn" , None)
        if sync_fn is None:
            self.anarch_print(
                "SYNC-MINUS FN is not set. Call db.set_group_sync_fn(add_or_update_group_info) in main.py")
            return False

        lock = self.get_group_lock(chat_id)
        async with lock:
            snap = await self.fetch_group_balances(chat_id)
            if snap is not None:
                self.__fastlane_set__(chat_id , snap)
                self.__negguard_clear__(chat_id)
                return True

            self.anarch_print(f"SYNC-MINUS start chat_id={chat_id}")
            try:
                ok = await asyncio.wait_for(
                    sync_fn(bot , chat_id , self) , timeout=self.BALANCE_SYNC_TIMEOUT)
            except Exception as e:
                self.anarch_print(f"SYNC-MINUS exception chat_id={chat_id}: {e}")
                self.__negguard_set__(chat_id)
                return False

            if not ok:
                self.anarch_print(f"SYNC-MINUS returned False chat_id={chat_id}")
                self.__negguard_set__(chat_id)
                return False

            snap = await self.fetch_group_balances(chat_id)
            if snap is None:
                self.anarch_print(f"SYNC-MINUS done but row missing chat_id={chat_id}")
                self.__negguard_set__(chat_id)
                return False

            self.__fastlane_set__(chat_id , snap)
            self.__negguard_clear__(chat_id)
            self.anarch_print(f"SYNC-MINUS ok chat_id={chat_id}")
            return True

    # ============================================================
    # ✅ Публичный метод: снять с общего баланса чата
    # ============================================================
    async def update_chat_balance_minus(self , chat_id , amount , bot=None) -> Optional [ BalanceSnapshot ]:
        """
        Снимает сумму с ОБЩЕГО баланса чата:
          1) сначала из chatbalance
          2) затем из dexbalance

        Работает в стиле всей balance-системы:
        - normalize chat_id
        - lock per chat_id
        - fastlane cache
        - negative cache
        - cold sync через __ensure_chatrow_exists_for_minus__
        - возврат BalanceSnapshot
        """
        cid = self._normalize_group_chat_id(chat_id)
        if cid is None:
            self.anarch_print(f"PUBLIC minus invalid chat_id={chat_id!r}")
            return None

        try:
            amount = int(amount)
        except Exception:
            self.anarch_print(f"PUBLIC minus invalid amount chat_id={cid} amount={amount!r}")
            return None

        if amount <= 0:
            self.anarch_print(f"PUBLIC minus skip chat_id={cid}: amount <= 0")
            return None

        lock = self.get_group_lock(cid)
        async with lock:
            self.anarch_print(f"PUBLIC minus lock acquired chat_id={cid} amount={amount}")

            # 1) пробуем сразу снять
            snap = await self.update_total_balance_minus_db(cid , amount)
            if snap is not None:
                self.__fastlane_set__(cid , snap)
                self.__negguard_clear__(cid)
                self.anarch_print(
                    f"PUBLIC minus success chat_id={cid} "
                    f"cb={snap.chatbalance} dbx={snap.dexbalance}")
                return snap

            # 2) если строки нет - пробуем отдельный sync для минуса
            ok = await self.__ensure_chatrow_exists_for_minus__(bot , cid)
            if not ok:
                self.anarch_print(f"PUBLIC minus ensure failed chat_id={cid}")
                return None

            # 3) повтор после синка
            snap = await self.update_total_balance_minus_db(cid , amount)
            if snap is None:
                self.anarch_print(f"PUBLIC minus retry failed chat_id={cid}")
                return None

            self.__fastlane_set__(cid , snap)
            self.__negguard_clear__(cid)
            self.anarch_print(
                f"PUBLIC minus retry success chat_id={cid} "
                f"cb={snap.chatbalance} dbx={snap.dexbalance}")
            return snap



















































#123




    # ============================================================
    # ✅ 1) Обновить время последней эконом-активности кошелька
    # ============================================================
    async def touch_balance_last_active(self , user_id: int , set_active_status: bool = True) -> bool:
        """
        ✅ ВЫЗЫВАТЬ ПОСЛЕ КАЖДОЙ ЗАВЕРШЁННОЙ ИГРЫ (win/lose не важно)

        КЛЮЧЕВАЯ ЛОГИКА:
        - ACTIVE(1): игра -> last_active=NOW(), status=1
        - SLEEP(2): игра -> last_active НЕ трогаем (таймер до burn идёт дальше!)
                    -> bump played_games (+1)
                    -> если played>=needed -> status=1 + last_active=NOW() + cleanup recovery
                    -> если elapsed>=burn -> status=3 + cleanup recovery (не успел - сам виноват)
        - BURNED(3): игра -> оживляем (status=1) + last_active=NOW()

        set_active_status=False:
        - только touch last_active=NOW() (без прогресса/статусов) - на твой страх и риск
        """
        uid = int(user_id)

        if not getattr(self , "pool" , None):
            _bal_dbg("TOUCH" , f"❌ pool не инициализирован uid={uid}")
            return False

        # сроки (на всякий случай safe fallback)
        try:
            sec_to_sleep = int(BALANCE_STATUS_1_TO_2_SEC)
        except Exception:
            sec_to_sleep = 3 * 24 * 3600

        try:
            sec_to_burn = int(BALANCE_STATUS_MAX_TO_3_SEC)
        except Exception:
            sec_to_burn = 7 * 24 * 3600

        need_default = int(SLEEP_RECOVERY_DEFAULT_NEEDED) if int(SLEEP_RECOVERY_DEFAULT_NEEDED) > 0 else 10

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():

                    # ------------------------------------------------
                    # 0) если set_active_status=False -> просто touch
                    # (но обычно тебе это НЕ нужно, раз активность только по играм)
                    # ------------------------------------------------
                    if not set_active_status:
                        res = await conn.execute(
                            "UPDATE users SET balance_last_active = NOW() WHERE user_id=$1" , uid)
                        try:
                            updated = int((res or "0").split() [ -1 ])
                        except Exception:
                            updated = 0
                        ok = updated > 0
                        _bal_dbg("TOUCH" , f"uid={uid} set_active_status=False -> touched only ok={ok}")
                        return ok

                    # ------------------------------------------------
                    # 1) читаем статус + last_active (и блокируем строку)
                    # ------------------------------------------------
                    row = await conn.fetchrow(
                        """
                        SELECT
                            COALESCE(balance_status, 1) AS st,
                            COALESCE(balance_last_active, NOW()) AS last_active
                        FROM users
                        WHERE user_id = $1
                        FOR UPDATE
                        """ , uid)
                    if not row:
                        _bal_dbg("TOUCH" , f"⚠️ uid={uid} не найден в users")
                        return False

                    try:
                        st_before = int(row [ "st" ] or BAL_STATUS_ACTIVE)
                    except Exception:
                        st_before = BAL_STATUS_ACTIVE

                    last_active = row [ "last_active" ]

                    # elapsed считаем ДО любых UPDATE
                    try:
                        elapsed = int((datetime.now() - last_active).total_seconds())
                    except Exception:
                        elapsed = 0
                    if elapsed < 0:
                        elapsed = 0

                    _bal_dbg("STATE" , f"uid={uid} st_before={st_before} elapsed={elapsed}s last_active={last_active}")

                    # ------------------------------------------------
                    # 2) BURNED -> игра оживляет (как ты хотел ранее)
                    # ------------------------------------------------
                    if st_before == BAL_STATUS_BURNED:
                        await conn.execute(
                            "UPDATE users SET balance_status=1, balance_last_active=NOW() WHERE user_id=$1" , uid)
                        await conn.execute(
                            "DELETE FROM users_balance_sleep_recovery WHERE user_id=$1" , uid)
                        _bal_dbg("REVIVE" , f"uid={uid} was BURNED -> STATUS=1, last_active=NOW(), recovery cleaned")
                        return True

                    # ------------------------------------------------
                    # 3) SLEEP: таймер до burn НЕ сбрасываем!
                    # ------------------------------------------------
                    if st_before == BAL_STATUS_SLEEP:
                        # 3.1 если уже должен сгореть - сжигаем сразу
                        if elapsed >= sec_to_burn:
                            await conn.execute(
                                "UPDATE users SET balance_status=3 WHERE user_id=$1" , uid)
                            await conn.execute(
                                "DELETE FROM users_balance_sleep_recovery WHERE user_id=$1" , uid)
                            _bal_dbg("BURN" , f"uid={uid} SLEEP but elapsed>=burn -> STATUS=3, recovery cleaned")
                            return True

                        # 3.2 гарантируем строку recovery (НЕ сбрасываем played!)
                        await conn.execute(
                            """
                            INSERT INTO users_balance_sleep_recovery (user_id, played_games, needed_games, created_at, updated_at)
                            VALUES ($1, 0, $2, NOW(), NOW())
                            ON CONFLICT (user_id) DO UPDATE
                            SET needed_games = CASE
                                WHEN users_balance_sleep_recovery.needed_games IS NULL OR users_balance_sleep_recovery.needed_games <= 0
                                THEN EXCLUDED.needed_games
                                ELSE users_balance_sleep_recovery.needed_games
                            END,
                            updated_at = NOW()
                            """ , uid , need_default)

                        # 3.3 +1 игра (ВАЖНО: last_active НЕ трогаем)
                        rr = await conn.fetchrow(
                            """
                            UPDATE users_balance_sleep_recovery
                            SET played_games = played_games + 1,
                                updated_at = NOW()
                            WHERE user_id = $1
                            RETURNING played_games, needed_games
                            """ , uid)

                        try:
                            played = int(rr [ "played_games" ] or 0) if rr else 0
                        except Exception:
                            played = 0

                        try:
                            needed = int(rr [ "needed_games" ] or need_default) if rr else need_default
                        except Exception:
                            needed = need_default

                        if needed <= 0:
                            needed = need_default

                        left = max(0 , needed - played)
                        remaining_to_burn = max(0 , sec_to_burn - elapsed)

                        _bal_dbg(
                            "SLEEP" ,
                            f"uid={uid} played={played}/{needed} left={left} remaining_to_burn={remaining_to_burn}s")

                        # 3.4 если выполнено - восстановление (и вот тут уже last_active=NOW())
                        if played >= needed:
                            await conn.execute(
                                "UPDATE users SET balance_status=1, balance_last_active=NOW() WHERE user_id=$1" , uid)
                            await conn.execute(
                                "DELETE FROM users_balance_sleep_recovery WHERE user_id=$1" , uid)
                            _bal_dbg(
                                "RESTORE" ,
                                f"✅ uid={uid} played>=needed -> STATUS=1, last_active=NOW(), recovery deleted")
                            return True

                        # 3.5 иначе остаёмся SLEEP, last_active НЕ меняем
                        # (только на всякий убедимся, что статус=2)
                        await conn.execute(
                            "UPDATE users SET balance_status=2 WHERE user_id=$1" , uid)
                        _bal_dbg("KEEP" , f"uid={uid} stays SLEEP (last_active NOT touched)")
                        return True

                    # ------------------------------------------------
                    # 4) ACTIVE: обычная логика
                    # ------------------------------------------------
                    # если по времени уже должен быть sleep/burn - можно прямо тут перевести
                    if elapsed >= sec_to_burn:
                        await conn.execute(
                            "UPDATE users SET balance_status=3 WHERE user_id=$1" , uid)
                        await conn.execute(
                            "DELETE FROM users_balance_sleep_recovery WHERE user_id=$1" , uid)
                        _bal_dbg("BURN" , f"uid={uid} ACTIVE but elapsed>=burn -> STATUS=3")
                        return True

                    if elapsed >= sec_to_sleep:
                        # вошёл в sleep (по времени), но это уже игра: статус станет sleep,
                        # и дальше он будет восстанавливаться через played/needed
                        await conn.execute(
                            "UPDATE users SET balance_status=2 WHERE user_id=$1" , uid)
                        # НЕ трогаем last_active, иначе таймер “сгорания” сломается
                        _bal_dbg(
                            "SLEEP_ENTER" ,
                            f"uid={uid} ACTIVE but elapsed>=sleep -> STATUS=2 (last_active NOT touched)")

                        # и сразу применяем sleep-ветку логики “как будто он sleep и сыграл игру”
                        # (т.е. bump +1)
                        await conn.execute(
                            """
                            INSERT INTO users_balance_sleep_recovery (user_id, played_games, needed_games, created_at, updated_at)
                            VALUES ($1, 0, $2, NOW(), NOW())
                            ON CONFLICT (user_id) DO UPDATE
                            SET needed_games = CASE
                                WHEN users_balance_sleep_recovery.needed_games IS NULL OR users_balance_sleep_recovery.needed_games <= 0
                                THEN EXCLUDED.needed_games
                                ELSE users_balance_sleep_recovery.needed_games
                            END,
                            updated_at = NOW()
                            """ , uid , need_default)

                        rr = await conn.fetchrow(
                            """
                            UPDATE users_balance_sleep_recovery
                            SET played_games = played_games + 1,
                                updated_at = NOW()
                            WHERE user_id = $1
                            RETURNING played_games, needed_games
                            """ , uid)

                        played = int(rr [ "played_games" ] or 0) if rr else 0
                        needed = int(rr [ "needed_games" ] or need_default) if rr else need_default
                        if needed <= 0:
                            needed = need_default

                        _bal_dbg("SLEEP_ENTER" , f"uid={uid} first sleep-game played={played}/{needed}")

                        if played >= needed:
                            await conn.execute(
                                "UPDATE users SET balance_status=1, balance_last_active=NOW() WHERE user_id=$1" , uid)
                            await conn.execute(
                                "DELETE FROM users_balance_sleep_recovery WHERE user_id=$1" , uid)
                            _bal_dbg(
                                "RESTORE" , f"✅ uid={uid} restored immediately on entry (played>=needed) -> STATUS=1")
                        return True

                    # иначе всё норм: active -> touch NOW()
                    await conn.execute(
                        "UPDATE users SET balance_status=1, balance_last_active=NOW() WHERE user_id=$1" , uid)
                    await conn.execute(
                        "DELETE FROM users_balance_sleep_recovery WHERE user_id=$1" , uid)
                    _bal_dbg("ACTIVE" , f"uid={uid} ACTIVE -> last_active=NOW(), status=1")
                    return True

        except Exception as e:
            _bal_dbg("TOUCH" , f"❌ uid={uid} exception: {e!r}")
            return False

    # ------------------------------------------------------------
    # ✅ 5) Увеличить прогресс на 1 игру (ВЫЗЫВАТЬ ПОСЛЕ КАЖДОЙ ЗАВЕРШЁННОЙ ИГРЫ)
    # ------------------------------------------------------------
    async def bump_sleep_recovery_game(self , user_id: int) -> Tuple [ bool , int , int ]:
        """
        Возвращает (restored:bool, played:int, needed:int)

        Работает ТОЛЬКО если сейчас status=2.
        - +1 played_games
        - если played >= needed -> ставим status=1, удаляем строку, обновляем last_active
        """
        uid = int(user_id)

        try:
            if not getattr(self , "pool" , None):
                return False , 0 , SLEEP_RECOVERY_DEFAULT_NEEDED

            # проверяем текущий статус (быстро)
            st = await self.get_balance_status(uid)
            if int(st) != BAL_STATUS_SLEEP:
                return False , 0 , SLEEP_RECOVERY_DEFAULT_NEEDED

            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # гарантируем строку
                    await conn.execute(
                        """
                        INSERT INTO users_balance_sleep_recovery (user_id, played_games, needed_games, created_at, updated_at)
                        VALUES ($1, 0, $2, NOW(), NOW())
                        ON CONFLICT (user_id) DO NOTHING
                        """ , uid , int(SLEEP_RECOVERY_DEFAULT_NEEDED))

                    # +1 игра
                    row = await conn.fetchrow(
                        """
                        UPDATE users_balance_sleep_recovery
                        SET played_games = played_games + 1,
                            updated_at = NOW()
                        WHERE user_id = $1
                        RETURNING played_games, needed_games
                        """ , uid)

                    if not row:
                        return False , 0 , SLEEP_RECOVERY_DEFAULT_NEEDED

                    played = int(row [ "played_games" ] or 0)
                    needed = int(row [ "needed_games" ] or SLEEP_RECOVERY_DEFAULT_NEEDED)

                    # ✅ заранее возвращаем в ACTIVE, как только выполнено
                    if played >= needed:
                        await conn.execute(
                            "UPDATE users SET balance_status = 1, balance_last_active = NOW() WHERE user_id = $1" ,
                            uid)
                        await conn.execute(
                            "DELETE FROM users_balance_sleep_recovery WHERE user_id = $1" , uid)

                        print(f"✅ [SLEEP_RECOVERY][RESTORE] user_id={uid} played={played}/{needed} -> STATUS=1")
                        return True , played , needed

                    print(f"🟠 [SLEEP_RECOVERY][PROGRESS] user_id={uid} played={played}/{needed}")
                    return False , played , needed

        except Exception as e:
            print(f"❌ [SLEEP_RECOVERY][BUMP] user_id={uid} err: {e!r}")
            return False , 0 , SLEEP_RECOVERY_DEFAULT_NEEDED

    # ------------------------------------------------------------
    # ✅ 4) Получить прогресс восстановления (для показа в балансе)
    # ------------------------------------------------------------
    async def get_sleep_recovery_progress(self , user_id: int) -> Tuple [ int , int ]:
        """
        Возвращает (played_games, needed_games). Если нет строки - (0, DEFAULT).
        """
        uid = int(user_id)
        try:
            if not getattr(self , "pool" , None):
                return 0 , SLEEP_RECOVERY_DEFAULT_NEEDED

            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT played_games, needed_games
                    FROM users_balance_sleep_recovery
                    WHERE user_id = $1
                    """ , uid)

            if not row:
                return 0 , SLEEP_RECOVERY_DEFAULT_NEEDED

            try:
                played = int(row [ "played_games" ] or 0)
            except Exception:
                played = 0

            try:
                needed = int(row [ "needed_games" ] or SLEEP_RECOVERY_DEFAULT_NEEDED)
            except Exception:
                needed = SLEEP_RECOVERY_DEFAULT_NEEDED

            return played , needed

        except Exception as e:
            print(f"❌ [SLEEP_RECOVERY][GET] user_id={uid} err: {e!r}")
            return 0 , SLEEP_RECOVERY_DEFAULT_NEEDED

    # ------------------------------------------------------------
    # ✅ 3) Создать/обновить строку восстановления (если status=2)
    # ------------------------------------------------------------
    async def ensure_sleep_recovery_row(self , user_id: int ,
                                        needed_games: int = SLEEP_RECOVERY_DEFAULT_NEEDED) -> bool:
        """
        Делает запись в users_balance_sleep_recovery, если её нет.
        Нужна только для status=2.
        """
        try:
            if not getattr(self , "pool" , None):
                return False

            uid = int(user_id)
            need = int(needed_games)

            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO users_balance_sleep_recovery (user_id, played_games, needed_games, created_at, updated_at)
                    VALUES ($1, 0, $2, NOW(), NOW())
                    ON CONFLICT (user_id) DO UPDATE
                    SET needed_games = EXCLUDED.needed_games,
                        updated_at = NOW()
                    """ , uid , need)

            print(f"🟠 [SLEEP_RECOVERY][ENSURE] user_id={uid} needed={need}")
            return True

        except Exception as e:
            print(f"❌ [SLEEP_RECOVERY][ENSURE] err: {e!r}")
            return False
    # ============================================================
    # ✅ 2) Получить balance_last_active
    # ============================================================
    async def get_balance_last_active(self , user_id: int) -> Optional [ datetime ]:
        """
        Возвращает users.balance_last_active (datetime) или None.
        """
        try:
            if not getattr(self , "pool" , None):
                print("❌ [BALANCE][GET_LAST] pool не инициализирован")
                return None

            uid = int(user_id)

            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    '''
                    SELECT balance_last_active
                    FROM users
                    WHERE user_id = $1
                    ''' , uid)

            if not row:
                print(f"⚠️ [BALANCE][GET_LAST] user_id={uid} не найден")
                return None

            last_dt = row.get("balance_last_active")
            print(f"ℹ️ [BALANCE][GET_LAST] user_id={uid} balance_last_active={last_dt}")
            return last_dt

        except Exception as e:
            print(f"❌ [BALANCE][GET_LAST] user_id={user_id} err: {e!r}")
            return None

    # ============================================================
    # ✅ 3) Получить balance_status
    # ============================================================
    async def get_balance_status(self, user_id: int) -> int:
        try:
            if not getattr(self, "pool", None):
                return BAL_STATUS_ACTIVE

            uid = int(user_id)
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT balance_status FROM users WHERE user_id = $1",
                    uid
                )
            if not row:
                return BAL_STATUS_ACTIVE
            try:
                return int(row["balance_status"] or BAL_STATUS_ACTIVE)
            except Exception:
                return BAL_STATUS_ACTIVE
        except Exception as e:
            print(f"❌ [BALANCE][GET_STATUS] err: {e!r}")
            return BAL_STATUS_ACTIVE

    # ============================================================
    # ✅ 4) Установить balance_status
    # ============================================================
    async def set_balance_status(self, user_id: int, new_status: int) -> bool:
        try:
            if not getattr(self, "pool", None):
                print("❌ [BALANCE][SET_STATUS] pool не инициализирован")
                return False

            uid = int(user_id)
            st = int(new_status)

            async with self.pool.acquire() as conn:
                res = await conn.execute(
                    """
                    UPDATE users
                    SET balance_status = $1
                    WHERE user_id = $2
                    """,
                    st, uid
                )

            try:
                updated = int((res or "0").split()[-1])
            except Exception:
                updated = 0

            ok = updated > 0
            if ok:
                print(f"🧠 [BALANCE][SET_STATUS] user_id={uid} -> {st}")
            else:
                print(f"⚠️ [BALANCE][SET_STATUS] user_id={uid} not updated (res={res!r})")
            return ok

        except Exception as e:
            print(f"❌ [BALANCE][SET_STATUS] err: {e!r}")
            return False

    # ============================================================
    # ✅ 5) Главная функция: пересчитать статус по времени
    # ============================================================
    async def ensure_balance_status_by_time(self , user_id: int , sec_to_sleep: int = BALANCE_STATUS_1_TO_2_SEC ,
            sec_to_burn: int = BALANCE_STATUS_MAX_TO_3_SEC) -> Tuple [
        int , Optional [ datetime ] , int , Optional [ int ] ]:
        """
        Лениво пересчитывает статус по users.balance_last_active.

        Возвращает:
        (status:int, last_active:datetime|None, elapsed_sec:int, remaining_to_3_sec:int|None)

        Логика:
        - elapsed >= sec_to_burn -> статус 3
        - elapsed >= sec_to_sleep -> статус 2 (и считает remaining до 3)
        - иначе статус 1
        """
        uid = int(user_id)
        now_dt = datetime.now()

        last_active = await self.get_balance_last_active(uid)
        status = await self.get_balance_status(uid)

        # новичок / нет данных -> не пугаем
        if not last_active:
            last_active = now_dt
            # можно не трогать БД, но я бы один раз поставил, чтобы дальше было чисто
            try:
                await self.touch_balance_last_active(uid , set_active_status=False)
            except Exception:
                pass
            print(f"🟢 [BALANCE][STATUS] user_id={uid} last_active пустой -> фиксирую now (новичок)")

        # elapsed
        try:
            elapsed = int((now_dt - last_active).total_seconds())
        except Exception:
            elapsed = 0

        # 1) burned
        if elapsed >= int(sec_to_burn):
            if int(status) != BAL_STATUS_BURNED:
                ok = await self.set_balance_status(uid , BAL_STATUS_BURNED)
                print(f"🔥 [BALANCE][STATUS] user_id={uid} -> STATUS=3 ok={ok} elapsed={elapsed}s")
            return BAL_STATUS_BURNED , last_active , elapsed , 0

        # 2) sleep
        if elapsed >= int(sec_to_sleep):
            if int(status) != BAL_STATUS_SLEEP:
                ok = await self.set_balance_status(uid , BAL_STATUS_SLEEP)
                print(f"🟠 [BALANCE][STATUS] user_id={uid} -> STATUS=2 ok={ok} elapsed={elapsed}s")
            remaining = int(sec_to_burn) - elapsed
            return BAL_STATUS_SLEEP , last_active , elapsed , max(0 , remaining)

        # 3) active
        if int(status) != BAL_STATUS_ACTIVE:
            ok = await self.set_balance_status(uid , BAL_STATUS_ACTIVE)
            print(f"🟢 [BALANCE][STATUS] user_id={uid} -> STATUS=1 ok={ok} elapsed={elapsed}s")

        return BAL_STATUS_ACTIVE , last_active , elapsed , None

    # ============================================================
    # ✅ Главная функция, от которой всё зависит (атомарно, 1 SQL)
    # ============================================================
    async def ensure_balance_status_engine(self , user_id: int , sec_to_sleep: int = BALANCE_STATUS_1_TO_2_SEC ,
            sec_to_burn: int = BALANCE_STATUS_MAX_TO_3_SEC ,
            default_needed_games: int = SLEEP_RECOVERY_DEFAULT_NEEDED , ) -> Tuple [
        int , Optional [ datetime ] , int , int , int , int , int , bool ]:
        """
        ✅ ВАЖНО: Sleep "липкий"
        - Если status=2, то он НЕ станет 1 только потому что elapsed маленький (после touch).
        - Sleep -> Active ТОЛЬКО если played >= needed.
        - Sleep -> Burned если elapsed >= sec_to_burn.

        ✅ burned_now = True ТОЛЬКО если в этом вызове произошёл переход в статус=3.
        То есть, если статус уже был 3 - burned_now будет False.
        """

        uid = int(user_id)
        need_default = int(default_needed_games) if int(default_needed_games) > 0 else 10

        if not getattr(self , "pool" , None):
            print("❌ [BALANCE][ENGINE] pool не инициализирован")
            return BAL_STATUS_ACTIVE , None , 0 , 0 , 0 , need_default , 180 , False

        q = """
        WITH cur AS (
            SELECT
                u.user_id,
                COALESCE(u.balance_last_active, NOW()) AS last_active,
                COALESCE(u.balance_status, 1) AS status
            FROM users u
            WHERE u.user_id = $1
        ),
        rec AS (
            SELECT
                r.user_id,
                COALESCE(r.played_games, 0) AS played_games,
                COALESCE(NULLIF(r.needed_games, 0), $4) AS needed_games
            FROM users_balance_sleep_recovery r
            WHERE r.user_id = $1
        ),
        calc AS (
            SELECT
                c.user_id,
                c.last_active,
                c.status AS cur_status,
                GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - c.last_active)))::int) AS elapsed_sec,
                COALESCE(rec.played_games, 0) AS played_games,
                COALESCE(rec.needed_games, $4) AS needed_games,

                CASE
                    -- 1) burn всегда приоритетнее
                    WHEN GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - c.last_active)))::int) >= $3 THEN 3

                    -- 2) липкий sleep: если уже sleep и recovery НЕ выполнен -> остаёмся sleep
                    WHEN c.status = 2 AND (COALESCE(rec.needed_games, $4) > 0)
                         AND (COALESCE(rec.played_games, 0) < COALESCE(rec.needed_games, $4))
                         THEN 2

                    -- 3) sleep -> active только если recovery выполнен
                    WHEN c.status = 2 AND (COALESCE(rec.needed_games, $4) > 0)
                         AND (COALESCE(rec.played_games, 0) >= COALESCE(rec.needed_games, $4))
                         THEN 1

                    -- 4) обычная логика для остальных: active -> sleep по времени
                    WHEN GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - c.last_active)))::int) >= $2 THEN 2

                    ELSE 1
                END AS desired_status,

                -- ✅ КЛЮЧЕВОЕ: burned_now (переход в 3 прямо сейчас)
                CASE
                    WHEN c.status IS DISTINCT FROM 3
                         AND GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - c.last_active)))::int) >= $3
                    THEN TRUE
                    ELSE FALSE
                END AS burned_now
            FROM cur c
            LEFT JOIN rec ON rec.user_id = c.user_id
        ),

        upd_status AS (
            UPDATE users u
            SET balance_status = x.desired_status
            FROM calc x
            WHERE u.user_id = x.user_id
              AND u.balance_status IS DISTINCT FROM x.desired_status
            RETURNING u.user_id
        ),

        -- если status=2 -> гарантируем строку recovery (не сбрасываем прогресс)
        ensure_sleep AS (
            INSERT INTO users_balance_sleep_recovery (user_id, played_games, needed_games, created_at, updated_at)
            SELECT x.user_id, 0, $4, NOW(), NOW()
            FROM calc x
            WHERE x.desired_status = 2
            ON CONFLICT (user_id) DO UPDATE
            SET needed_games = CASE
                                WHEN users_balance_sleep_recovery.needed_games IS NULL
                                  OR users_balance_sleep_recovery.needed_games <= 0
                                THEN EXCLUDED.needed_games
                                ELSE users_balance_sleep_recovery.needed_games
                               END,
                updated_at = NOW()
            RETURNING user_id
        ),

        -- если статус стал не 2 -> чистим recovery
        cleanup_sleep AS (
            DELETE FROM users_balance_sleep_recovery r
            USING calc x
            WHERE r.user_id = x.user_id
              AND x.desired_status <> 2
            RETURNING r.user_id
        ),

        rec2 AS (
            SELECT
                r.user_id,
                COALESCE(r.played_games, 0) AS played_games,
                COALESCE(NULLIF(r.needed_games, 0), $4) AS needed_games
            FROM users_balance_sleep_recovery r
            WHERE r.user_id = $1
        )

        SELECT
            x.desired_status AS final_status,
            x.last_active    AS last_active,
            x.elapsed_sec    AS elapsed_sec,
            CASE
                WHEN x.desired_status = 2 THEN GREATEST(0, $3 - x.elapsed_sec)
                WHEN x.desired_status = 3 THEN 0
                ELSE 0
            END AS remaining_to_3_sec,
            COALESCE(rec2.played_games, 0) AS played_games,
            COALESCE(rec2.needed_games, $4) AS needed_games,
            EXISTS(SELECT 1 FROM upd_status) AS status_changed,
            x.burned_now AS burned_now
        FROM calc x
        LEFT JOIN rec2 ON rec2.user_id = x.user_id;
        """

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(q , uid , int(sec_to_sleep) , int(sec_to_burn) , need_default)

            if not row:
                print(f"⚠️ [BALANCE][ENGINE] user_id={uid} не найден в users")
                return BAL_STATUS_ACTIVE , None , 0 , 0 , 0 , need_default , 300 , False

            status = int(row [ "final_status" ] or BAL_STATUS_ACTIVE)
            last_active = row [ "last_active" ]
            elapsed = int(row [ "elapsed_sec" ] or 0)
            remaining_to_3 = int(row [ "remaining_to_3_sec" ] or 0)
            played = int(row [ "played_games" ] or 0)
            needed = int(row [ "needed_games" ] or need_default)
            status_changed = bool(row [ "status_changed" ])
            burned_now = bool(row [ "burned_now" ])

            if status_changed:
                print(
                    f"🔁 [BALANCE][ENGINE] user_id={uid} status -> {status} elapsed={elapsed}s played={played}/{needed}")

            MIN_CHECK = 30
            MAX_CHECK = 6 * 3600

            if status == BAL_STATUS_ACTIVE:
                to_sleep = int(sec_to_sleep) - elapsed
                next_after = max(MIN_CHECK , min(MAX_CHECK , to_sleep))
            elif status == BAL_STATUS_SLEEP:
                to_burn = int(sec_to_burn) - elapsed
                next_after = max(MIN_CHECK , min(MAX_CHECK , to_burn))
            else:
                next_after = 12 * 3600

            return status , last_active , elapsed , remaining_to_3 , played , needed , int(next_after) , burned_now

        except Exception as e:
            print(f"❌ [BALANCE][ENGINE] user_id={uid} err: {e!r}")
            return BAL_STATUS_ACTIVE , None , 0 , 0 , 0 , need_default , 180 , False

























































# ============================================================
    # 🔒 ЛОКИ ДЛЯ ГРУПП
    # ============================================================

    # -------------------------------
    # [anarch] print helper
    # -------------------------------
    def anarch_print(self, msg: str) -> None:
        if ANARCH:
            print(f"[anarch] {msg}")

    # ============================================================
    # Регистрация sync функции (без импортов main.py в db.py)
    # ============================================================

    def set_group_sync_fn(self, fn: Callable[..., Awaitable[bool]]) -> None:
        """
        Вызывается из main.py один раз:
            db.set_group_sync_fn(add_or_update_group_info)
        """
        self.group_sync_fn = fn
        self.anarch_print("sync function registered")

    # ============================================================
    # 🔒 Lock per chat_id
    # ============================================================

    def get_group_lock(self, chat_id: int) -> asyncio.Lock:
        chat_id = int(chat_id)
        lock = self.__LCK_CHATROW_SYNC__.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self.__LCK_CHATROW_SYNC__[chat_id] = lock
            self.anarch_print(f"lock created chat_id={chat_id}")
        return lock

    # ============================================================
    # ✅ DB методы (балансы)
    # ============================================================

    async def fetch_group_balances(self, chat_id: int) -> Optional[BalanceSnapshot]:
        chat_id = int(chat_id)
        query = "SELECT chatbalance, dexbalance FROM chat WHERE chat_id = $1"

        try:
            async with self.pool.acquire() as conn:
                row = await asyncio.wait_for(
                    conn.fetchrow(query, chat_id),
                    timeout=self.BALANCE_SELECT_TIMEOUT
                )
        except Exception as e:
            self.anarch_print(f"DB fetch balances error chat_id={chat_id}: {e}")
            return None

        if row is None:
            self.anarch_print(f"DB fetch balances row=None chat_id={chat_id}")
            return None

        snap = BalanceSnapshot(
            chatbalance=int(row["chatbalance"] or 0),
            dexbalance=int(row["dexbalance"] or 0),
        )
        self.anarch_print(f"DB fetch OK chat_id={chat_id} cb={snap.chatbalance} dbx={snap.dexbalance}")
        return snap

    async def update_chatbalance_db(self, chat_id: int, amount: int) -> Optional[BalanceSnapshot]:
        chat_id = int(chat_id)
        amount = int(amount)
        query = """
            UPDATE chat
            SET chatbalance = chatbalance + $1
            WHERE chat_id = $2
            RETURNING chatbalance, dexbalance
        """
        try:
            async with self.pool.acquire() as conn:
                row = await asyncio.wait_for(
                    conn.fetchrow(query, amount, chat_id),
                    timeout=self.BALANCE_UPDATE_TIMEOUT
                )
        except Exception as e:
            self.anarch_print(f"DB update cb error chat_id={chat_id}: {e}")
            return None

        if row is None:
            self.anarch_print(f"DB update cb row=None chat_id={chat_id} (missing row?)")
            return None

        snap = BalanceSnapshot(
            chatbalance=int(row["chatbalance"] or 0),
            dexbalance=int(row["dexbalance"] or 0),
        )
        self.anarch_print(f"DB update cb OK chat_id={chat_id} cb={snap.chatbalance} dbx={snap.dexbalance}")
        return snap

    async def update_dexbalance_db(self, chat_id: int, amount: int) -> Optional[BalanceSnapshot]:
        chat_id = int(chat_id)
        amount = int(amount)
        query = """
            UPDATE chat
            SET dexbalance = dexbalance + $1
            WHERE chat_id = $2
            RETURNING chatbalance, dexbalance
        """
        try:
            async with self.pool.acquire() as conn:
                row = await asyncio.wait_for(
                    conn.fetchrow(query, amount, chat_id),
                    timeout=self.BALANCE_UPDATE_TIMEOUT
                )
        except Exception as e:
            self.anarch_print(f"DB update dbx error chat_id={chat_id}: {e}")
            return None

        if row is None:
            self.anarch_print(f"DB update dbx row=None chat_id={chat_id} (missing row?)")
            return None

        snap = BalanceSnapshot(
            chatbalance=int(row["chatbalance"] or 0),
            dexbalance=int(row["dexbalance"] or 0),
        )
        self.anarch_print(f"DB update dbx OK chat_id={chat_id} cb={snap.chatbalance} dbx={snap.dexbalance}")
        return snap

    # ============================================================
    # ⚡ Кэш + negative cache
    # ============================================================

    def _now(self) -> float:
        return time.time()

    def __fastlane_get__(self, chat_id: int) -> Optional[BalanceSnapshot]:
        cell = self.__CACHE_CHATBAL_FASTLANE__.get(chat_id)
        if not cell:
            return None
        if cell.expires_at <= self._now():
            self.__CACHE_CHATBAL_FASTLANE__.pop(chat_id, None)
            self.anarch_print(f"CACHE expired chat_id={chat_id}")
            return None
        return cell.value

    def __fastlane_set__(self, chat_id: int, snap: BalanceSnapshot) -> None:
        self.__CACHE_CHATBAL_FASTLANE__[chat_id] = _BalCacheCell(
            value=snap,
            expires_at=self._now() + self.BALANCE_CACHE_TTL
        )
        self.anarch_print(f"CACHE set chat_id={chat_id} cb={snap.chatbalance} dbx={snap.dexbalance}")

        meta = self.__CACHE_CHATMETA_ATLAS__.get(chat_id)
        if isinstance(meta, dict):
            meta["chatbalance"] = snap.chatbalance
            meta["dexbalance"] = snap.dexbalance
            self.__CACHE_CHATMETA_ATLAS__[chat_id] = meta

    def __negguard_active__(self, chat_id: int) -> bool:
        exp = self.__CACHE_CHATBAL_NEGGUARD__.get(chat_id)
        if not exp:
            return False
        if exp <= self._now():
            self.__CACHE_CHATBAL_NEGGUARD__.pop(chat_id, None)
            return False
        return True

    def __negguard_set__(self, chat_id: int) -> None:
        self.__CACHE_CHATBAL_NEGGUARD__[chat_id] = self._now() + self.BALANCE_NEG_TTL
        self.anarch_print(f"NEG set chat_id={chat_id} ttl={self.BALANCE_NEG_TTL}")

    def __negguard_clear__(self, chat_id: int) -> None:
        if chat_id in self.__CACHE_CHATBAL_NEGGUARD__:
            self.__CACHE_CHATBAL_NEGGUARD__.pop(chat_id, None)
            self.anarch_print(f"NEG cleared chat_id={chat_id}")

    def _normalize_group_chat_id(self, chat_id) -> Optional[int]:
        """
        Приводит chat_id к int и отсекает ЛС.
        """
        try:
            cid = int(chat_id)
        except Exception:
            return None
        if cid > 0:
            return None
        return cid

    # ============================================================
    # 🧊 Холодный путь: если строки нет - синк и проверка
    # ============================================================

    async def __ensure_chatrow_exists__(self, bot, chat_id: int) -> bool:
        if self.__negguard_active__(chat_id):
            self.anarch_print(f"SYNC skipped negguard chat_id={chat_id}")
            return False

        if self.group_sync_fn is None:
            self.anarch_print("SYNC FN is not set. Call db.set_group_sync_fn(add_or_update_group_info) in main.py")
            return False

        lock = self.get_group_lock(chat_id)
        async with lock:
            snap = await self.fetch_group_balances(chat_id)
            if snap is not None:
                self.__fastlane_set__(chat_id, snap)
                self.__negguard_clear__(chat_id)
                return True

            self.anarch_print(f"SYNC start chat_id={chat_id}")
            try:
                ok = await asyncio.wait_for(
                    self.group_sync_fn(bot, chat_id, self),
                    timeout=self.BALANCE_SYNC_TIMEOUT
                )
            except Exception as e:
                self.anarch_print(f"SYNC exception chat_id={chat_id}: {e}")
                self.__negguard_set__(chat_id)
                return False

            if not ok:
                self.anarch_print(f"SYNC returned False chat_id={chat_id}")
                self.__negguard_set__(chat_id)
                return False

            snap = await self.fetch_group_balances(chat_id)
            if snap is None:
                self.anarch_print(f"SYNC done but row missing chat_id={chat_id}")
                self.__negguard_set__(chat_id)
                return False

            self.__fastlane_set__(chat_id, snap)
            self.__negguard_clear__(chat_id)
            self.anarch_print(f"SYNC ok chat_id={chat_id}")
            return True

    # ============================================================
    # ✅ Публичные методы баланса (как ты хочешь: bot, chat_id)
    # ============================================================

    async def get_chatbalance(self, bot, chat_id) -> int:
        cid = self._normalize_group_chat_id(chat_id)
        if cid is None:
            return 0

        cached = self.__fastlane_get__(cid)
        if cached is not None:
            self.anarch_print(f"READ cb cache hit chat_id={cid}")
            return cached.chatbalance

        snap = await self.fetch_group_balances(cid)
        if snap is not None:
            self.__fastlane_set__(cid, snap)
            return snap.chatbalance

        ok = await self.__ensure_chatrow_exists__(bot, cid)
        if not ok:
            return 0

        cached = self.__fastlane_get__(cid)
        return cached.chatbalance if cached else 0

    async def get_dex_balance(self, bot, chat_id) -> int:
        cid = self._normalize_group_chat_id(chat_id)
        if cid is None:
            return 0

        cached = self.__fastlane_get__(cid)
        if cached is not None:
            return cached.dexbalance

        snap = await self.fetch_group_balances(cid)
        if snap is not None:
            self.__fastlane_set__(cid, snap)
            return snap.dexbalance

        ok = await self.__ensure_chatrow_exists__(bot, cid)
        if not ok:
            return 0

        cached = self.__fastlane_get__(cid)
        return cached.dexbalance if cached else 0

    async def get_total_balance(self, bot, chat_id) -> int:
        cid = self._normalize_group_chat_id(chat_id)
        if cid is None:
            return 0

        # LEGACY FREEZE:
        # legacy dexbalance отключён,
        # поэтому общий баланс группы = только chatbalance.
        cached = self.__fastlane_get__(cid)
        if cached is not None:
            return cached.chatbalance

        snap = await self.fetch_group_balances(cid)
        if snap is not None:
            self.__fastlane_set__(cid, snap)
            return snap.chatbalance

        ok = await self.__ensure_chatrow_exists__(bot, cid)
        if not ok:
            return 0

        cached = self.__fastlane_get__(cid)
        return cached.chatbalance if cached else 0

    async def add_to_chatbalance(self, bot, chat_id, amount: int) -> bool:
        cid = self._normalize_group_chat_id(chat_id)
        if cid is None:
            return False
        try:
            amount = int(amount)
        except Exception:
            return False

        snap = await self.update_chatbalance_db(cid, amount)
        if snap is not None:
            self.__fastlane_set__(cid, snap)
            self.__negguard_clear__(cid)
            return True

        ok = await self.__ensure_chatrow_exists__(bot, cid)
        if not ok:
            return False

        snap = await self.update_chatbalance_db(cid, amount)
        if snap is None:
            return False

        self.__fastlane_set__(cid, snap)
        return True

    async def add_to_dexbalance(self, bot, chat_id, amount: int) -> bool:
        cid = self._normalize_group_chat_id(chat_id)
        if cid is None:
            return False
        try:
            amount = int(amount)
        except Exception:
            return False

        snap = await self.update_dexbalance_db(cid, amount)
        if snap is not None:
            self.__fastlane_set__(cid, snap)
            self.__negguard_clear__(cid)
            return True

        ok = await self.__ensure_chatrow_exists__(bot, cid)
        if not ok:
            return False

        snap = await self.update_dexbalance_db(cid, amount)
        if snap is None:
            return False

        self.__fastlane_set__(cid, snap)
        return True

    # ============================================================
    # ✅ Твои старые имена (как ты вызываешь)
    # ============================================================

    async def get_chat_balancebalance(self, bot, chat_id) -> int:
        return await self.get_chatbalance(bot, chat_id)

    async def get_chat_balance(self, bot, chat_id) -> int:
        return await self.get_total_balance(bot, chat_id)

    async def update_chat_balance(self, bot, chat_id, amount: int) -> bool:
        return await self.add_to_chatbalance(bot, chat_id, amount)

    def invalidate_balance_cache(self, chat_id: int) -> None:
        cid = int(chat_id)
        self.__CACHE_CHATBAL_FASTLANE__.pop(cid, None)
        self.__CACHE_CHATBAL_NEGGUARD__.pop(cid, None)
        self.anarch_print(f"CACHE invalidated chat_id={cid}")

















######
    async def get_usernamechat_CheckpublickGroup(self , chat_id: int) -> Optional [ str ]:
        try:
            async with self.acquire() as connection:
                usernamechat_CheckpublickGroup = await connection.fetchval(
                    "SELECT usernamechat FROM chat WHERE chat_id = $1 LIMIT 1" , int(chat_id))

                try:
                    self._jc(
                        "DB:GET_USERNAMECHAT" ,
                        f"chat_id={chat_id} -> usernamechat(DB)={usernamechat_CheckpublickGroup!r}")
                except Exception:
                    pass

                print(f"[CHECKPUBLICKGROUP][DB] usernamechat chat_id={chat_id} -> {usernamechat_CheckpublickGroup!r}")
                return usernamechat_CheckpublickGroup

        except Exception as e:
            print(f"[CHECKPUBLICKGROUP][DB][ERROR] Ошибка при получении usernamechat: {type(e).__name__}: {e}")
            try:
                self._jc("DB:GET_USERNAMECHAT" , f"exception {type(e).__name__}: {e}")
            except Exception:
                pass
            return None

    async def update_usernamechat_CheckpublickGroup(self , chat_id: int , username: Optional [ str ]) -> bool:
        try:
            async with self.acquire() as connection:
                result = await connection.execute(
                    "UPDATE chat SET usernamechat = $2 WHERE chat_id = $1" , int(chat_id) , username)

                print(
                    f"[CHECKPUBLICKGROUP][DB] UPDATE usernamechat: "
                    f"chat_id={chat_id}, username={username!r}, result={result!r}")

                updated_rows = 0
                try:
                    updated_rows = int(str(result).split() [ -1 ])
                except Exception:
                    updated_rows = 0

                if updated_rows <= 0:
                    print(f"[CHECKPUBLICKGROUP][DB][WARN] Строка не обновлена, chat_id={chat_id}")
                    return False

                return True

        except Exception as e:
            print(f"[CHECKPUBLICKGROUP][DB][ERROR] Ошибка при обновлении usernamechat: {type(e).__name__}: {e}")
            return False

    async def log_deletebalance(self , user_id: int , removed_balance: int ,
            created_at: Optional [ Union [ datetime , str ] ] = None) -> bool:
        """
        ✅ ТОЛЬКО ЛОГИРОВАНИЕ (без списания денег)

        Пишет запись в таблицу deletebalance:
          - user_id
          - first_name
          - username
          - balance
          - data

        Формат даты для отображения:
          dd.mm.yyyy HH.MM.SS
        """
        uid = int(user_id)

        # защита от мусора
        try:
            removed = int(removed_balance)
        except Exception:
            removed = 0

        if removed < 0:
            removed = 0

        if not getattr(self , "pool" , None):
            _bal_dbg("LOG" , f"❌ pool не инициализирован uid={uid}")
            return False

        first_name: Optional [ str ] = None
        username: Optional [ str ] = None

        try:
            first_name = await self.get_firstname_by_user_id(uid)
        except Exception as e:
            _bal_dbg("META" , f"⚠️ get_firstname_by_user_id err uid={uid}: {e!r}")

        try:
            username = await self.get_username_by_user_id(uid)
        except Exception as e:
            _bal_dbg("META" , f"⚠️ get_username_by_user_id err uid={uid}: {e!r}")

        # дата
        dt_to_save: datetime

        try:
            if isinstance(created_at , datetime):
                dt_to_save = created_at
            elif isinstance(created_at , str) and created_at.strip():
                # если передали строку в формате "дд.мм.гггг чч.мм.сс"
                dt_to_save = datetime.strptime(created_at.strip() , "%d.%m.%Y %H.%M.%S")
            else:
                dt_to_save = datetime.now()

            async with self.pool.acquire() as conn:
                res = await conn.execute(
                    """
                    INSERT INTO deletebalance (user_id, first_name, username, balance, data)
                    VALUES ($1, $2, $3, $4, $5)
                    """ , uid , first_name , username , removed , dt_to_save)

            try:
                inserted = int((res or "0").split() [ -1 ])
            except Exception:
                inserted = 0

            ok = inserted > 0

            _bal_dbg(
                "LOG" , f"uid={uid} removed={removed} first_name={first_name!r} username={username!r} "
                        f"dt={dt_to_save.strftime('%d.%m.%Y %H.%M.%S')} res={res!r} ok={ok}")
            return ok

        except Exception as e:
            _bal_dbg("LOG" , f"❌ uid={uid} exception: {e!r}")
            return False






###########
    # -------------------------------
    # 🟦 ЛОГ для chathi (в стиле твоих _r/_jc)
    # -------------------------------
    def _ch(self , tag: str , msg: str) -> None:
        try:
            self._lazy_init_runtime_fields()
            if bool(getattr(self , "JACKCHAT_DEBUG" , False)):
                self._jc(f"CHATHI:{tag}" , msg)
            else:
                # чтобы не шуметь, можно убрать print
                pass
        except Exception:
            pass

    # -------------------------------
    # ✅ Lock по chat_id для синхронизации chathi
    # -------------------------------
    def _get_chatrow_lock(self , chat_id: int) -> asyncio.Lock:
        cid = int(chat_id)
        lck = self.__LCK_CHATROW_SYNC__.get(cid)
        if not lck:
            lck = asyncio.Lock()
            self.__LCK_CHATROW_SYNC__ [ cid ] = lck
        return lck

    # ============================================================
    # ✅ GET chathi (ИЩЕМ В ТАБЛИЦЕ chat ПО chat_id -> chathi)
    # ============================================================
    async def get_chathi(self , chat_id: int) -> Optional [ int ]:
        """
        Возвращает chat.chathi по chat_id.

        SELECT chathi FROM chat WHERE chat_id=$1

        Возвращает:
          - int (обычно 0/1), если запись есть
          - None, если записи нет или ошибка чтения
        """
        cid = int(chat_id)

        ok = await self.ensure_pool()
        if not ok:
            self._r("CHATHI:GET" , f"❌ pool not ready chat_id={cid}")
            return None

        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT chathi FROM chat WHERE chat_id=$1" , cid)
        except Exception as e:
            self._r("CHATHI:GET" , f"❌ fetchrow exception chat_id={cid}: {e!r}")
            return None

        if not row:
            self._ch("GET" , f"🟡 no row chat_id={cid}")
            return None

        val = row.get("chathi" , None)
        if val is None:
            self._ch("GET" , f"🟠 chathi is NULL chat_id={cid}")
            return None

        try:
            return int(val)
        except Exception as e:
            self._r("CHATHI:GET" , f"❌ chathi not int chat_id={cid} val={val!r} err={e!r}")
            return None

    # ============================================================
    # ✅ SET chathi (UPDATE chat SET chathi=? WHERE chat_id=?)
    # ============================================================
    async def set_chathi(self , chat_id: int , value: int) -> bool:
        """
        Обновляет chat.chathi по chat_id.

        UPDATE chat SET chathi=$2 WHERE chat_id=$1

        Возвращает True если UPDATE затронул 1+ строк.
        Если строки нет -> UPDATE 0 -> False.
        """
        cid = int(chat_id)

        ok = await self.ensure_pool()
        if not ok:
            self._r("CHATHI:SET" , f"❌ pool not ready chat_id={cid}")
            return False

        # защита от мусора: строго 0/1
        try:
            v = int(value)
        except Exception:
            v = 0
        v = 1 if v == 1 else 0

        try:
            async with self.acquire() as conn:
                res = await conn.execute(
                    "UPDATE chat SET chathi=$2 WHERE chat_id=$1" , cid , v)
        except Exception as e:
            self._r("CHATHI:SET" , f"❌ execute exception chat_id={cid} value={v}: {e!r}")
            return False

        updated = 0
        try:
            updated = int((res or "0").split() [ -1 ])
        except Exception:
            updated = 0

        ok_upd = updated > 0
        self._ch("SET" , f"chat_id={cid} value={v} res={res!r} updated={updated} ok={ok_upd}")
        return ok_upd

    # ============================================================
    # ✅ ENSURE (лениво): не делает UPDATE если уже совпадает
    # ============================================================
    async def ensure_chathi_value(self , chat_id: int , value: int) -> Tuple [ bool , Optional [ int ] , int ]:
        """
        Лениво гарантирует, что chat.chathi == value.

        Возвращает:
          (ok:bool, current_before:int|None, target:int)

        Логика:
        - берём lock на chat_id (чтобы два апдейта не дрались)
        - читаем current
        - если нет строки -> ok=False (потому что INSERT ты не разрешил)
        - если уже совпадает -> ok=True без UPDATE
        - иначе UPDATE -> ok=результат
        """
        cid = int(chat_id)

        # нормализуем target
        try:
            target = int(value)
        except Exception:
            target = 0
        target = 1 if target == 1 else 0

        lock = self._get_chatrow_lock(cid)

        async with lock:
            current = await self.get_chathi(cid)

            if current is None:
                # ВАЖНО: без INSERT невозможно "создать" строку.
                # Поэтому тут честно возвращаем False.
                self._ch("ENSURE" , f"🟡 chat_id={cid} no row -> cannot ensure without INSERT")
                return False , None , target

            try:
                cur_int = int(current)
            except Exception:
                cur_int = None

            if cur_int == target:
                self._ch("ENSURE" , f"🟢 chat_id={cid} already ok current={cur_int} target={target}")
                return True , cur_int , target

            ok_set = await self.set_chathi(cid , target)
            self._ch("ENSURE" , f"chat_id={cid} {cur_int} -> {target} ok={ok_set}")
            return ok_set , cur_int , target

    # ============================================================
    # ✅ Удобные обёртки (включить/выключить)
    # ============================================================
    async def enable_greeting(self , chat_id: int) -> bool:
        ok , _ , _ = await self.ensure_chathi_value(chat_id , CHATHI_ON)
        return ok

    async def disable_greeting(self , chat_id: int) -> bool:
        ok , _ , _ = await self.ensure_chathi_value(chat_id , CHATHI_OFF)
        return ok

    async def _get_deletebalance_data_type(self) -> Optional[str]:
        """
        Получает тип колонки deletebalance."data" из information_schema.
        Возвращает строку типа:
          - 'time without time zone'
          - 'timestamp without time zone'
          - 'timestamp with time zone'
          - 'date'
        """
        ok = await self.ensure_pool()
        if not ok:
            self._r("DELBAL:DTYPE", "❌ pool not ready")
            return None

        sql = """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'deletebalance'
              AND column_name = 'data'
            LIMIT 1
        """
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(sql)
        except Exception as e:
            self._r("DELBAL:DTYPE", f"❌ fetchrow exception: {e!r}")
            return None

        if not row:
            self._ch("DELBAL:DTYPE", "🟡 column deletebalance.data not found")
            return None

        dt = row.get("data_type")
        if not dt:
            self._ch("DELBAL:DTYPE", "🟠 data_type is NULL")
            return None

        try:
            return str(dt).strip().lower()
        except Exception:
            return None

    async def get_deletebalance_report(self , top_limit: int = 10 , days_limit: int = 14) -> Optional [
        Dict [ str , Any ] ]:
        """
        Полный отчёт по deletebalance.

        Возвращает словарь вида:
        {
          "meta": {
              "data_type": "...",
              "series_type": "daily|hourly|none",
              "note": "..."
          },
          "totals": {...},
          "extremes": {...},
          "top_users": [...],
          "daily": [...],
          "hourly": [...]
        }
        """
        ok = await self.ensure_pool()
        if not ok:
            self._r("DELBAL:REPORT" , "❌ pool not ready")
            return None

        try:
            top_n = int(top_limit)
        except Exception:
            top_n = 10

        if top_n < 1:
            top_n = 1
        elif top_n > 50:
            top_n = 50

        try:
            days_n = int(days_limit)
        except Exception:
            days_n = 14

        if days_n < 1:
            days_n = 1
        elif days_n > 365:
            days_n = 365

        data_type = await self._get_deletebalance_data_type()
        if not data_type:
            data_type = "unknown"

        data_type_l = str(data_type).lower()

        is_date_or_ts = ("timestamp" in data_type_l) or (data_type_l == "date")
        is_time_only = ("time" in data_type_l) and (not is_date_or_ts)

        dt_expr = '"data"::timestamp' if is_date_or_ts else '"data"'
        dt_select = '"data"::timestamp AS data' if is_date_or_ts else '"data" AS data'

        sql_totals = f"""
            SELECT
                COUNT(*)::bigint                        AS ops_count,
                COUNT(DISTINCT user_id)::bigint         AS users_count,
                COALESCE(SUM(balance), 0)::numeric      AS sum_balance,
                COALESCE(AVG(balance), 0)::numeric      AS avg_balance,
                COALESCE(MIN(balance), 0)::numeric      AS min_balance,
                COALESCE(MAX(balance), 0)::numeric      AS max_balance,
                MIN({dt_expr})                          AS first_dt,
                MAX({dt_expr})                          AS last_dt
            FROM deletebalance
        """

        sql_extremes_total_users = f"""
            WITH per_user AS (
                SELECT
                    user_id,
                    COUNT(*)::bigint                    AS cnt,
                    COALESCE(SUM(balance), 0)::numeric  AS sum_balance,
                    COALESCE(MIN(balance), 0)::numeric  AS min_balance,
                    COALESCE(MAX(balance), 0)::numeric  AS max_balance,
                    MIN({dt_expr})                      AS first_dt,
                    MAX({dt_expr})                      AS last_dt
                FROM deletebalance
                GROUP BY user_id
            )
            SELECT
                (
                    SELECT row_to_json(t)
                    FROM (
                        SELECT *
                        FROM per_user
                        ORDER BY sum_balance DESC, user_id ASC
                        LIMIT 1
                    ) t
                ) AS max_total_user,
                (
                    SELECT row_to_json(t)
                    FROM (
                        SELECT *
                        FROM per_user
                        ORDER BY sum_balance ASC, user_id ASC
                        LIMIT 1
                    ) t
                ) AS min_total_user
        """

        sql_extremes_single_ops = f"""
            SELECT
                (
                    SELECT row_to_json(x)
                    FROM (
                        SELECT user_id, balance, {dt_select}
                        FROM deletebalance
                        ORDER BY balance DESC, {dt_expr} ASC
                        LIMIT 1
                    ) x
                ) AS max_single_op,
                (
                    SELECT row_to_json(x)
                    FROM (
                        SELECT user_id, balance, {dt_select}
                        FROM deletebalance
                        ORDER BY balance ASC, {dt_expr} ASC
                        LIMIT 1
                    ) x
                ) AS min_single_op
        """

        sql_top_users = f"""
            SELECT
                user_id,
                COUNT(*)::bigint                    AS cnt,
                COALESCE(SUM(balance), 0)::numeric  AS sum_balance,
                COALESCE(AVG(balance), 0)::numeric  AS avg_balance,
                COALESCE(MIN(balance), 0)::numeric  AS min_balance,
                COALESCE(MAX(balance), 0)::numeric  AS max_balance,
                MIN({dt_expr})                      AS first_dt,
                MAX({dt_expr})                      AS last_dt
            FROM deletebalance
            GROUP BY user_id
            ORDER BY sum_balance DESC, cnt DESC, user_id ASC
            LIMIT $1
        """

        sql_daily = None
        sql_hourly = None

        if is_date_or_ts:
            sql_daily = f"""
                SELECT
                    date_trunc('day', {dt_expr})::date            AS day,
                    COUNT(*)::bigint                              AS cnt,
                    COALESCE(SUM(balance), 0)::numeric            AS sum_balance,
                    COALESCE(AVG(balance), 0)::numeric            AS avg_balance,
                    COALESCE(MIN(balance), 0)::numeric            AS min_balance,
                    COALESCE(MAX(balance), 0)::numeric            AS max_balance
                FROM deletebalance
                WHERE {dt_expr} >= (NOW() - ($1::int * INTERVAL '1 day'))
                GROUP BY day
                ORDER BY day DESC
            """
        else:
            sql_hourly = """
                SELECT
                    EXTRACT(HOUR FROM "data")::int                AS hour,
                    COUNT(*)::bigint                              AS cnt,
                    COALESCE(SUM(balance), 0)::numeric            AS sum_balance,
                    COALESCE(AVG(balance), 0)::numeric            AS avg_balance,
                    COALESCE(MIN(balance), 0)::numeric            AS min_balance,
                    COALESCE(MAX(balance), 0)::numeric            AS max_balance
                FROM deletebalance
                GROUP BY hour
                ORDER BY hour ASC
            """

        try:
            async with self.acquire() as conn:
                totals_row = await conn.fetchrow(sql_totals)
                extremes_users_row = await conn.fetchrow(sql_extremes_total_users)
                extremes_ops_row = await conn.fetchrow(sql_extremes_single_ops)
                top_rows = await conn.fetch(sql_top_users , top_n)

                daily_rows = [ ]
                hourly_rows = [ ]

                if sql_daily:
                    daily_rows = await conn.fetch(sql_daily , days_n)

                if sql_hourly:
                    hourly_rows = await conn.fetch(sql_hourly)

        except Exception as e:
            self._r("DELBAL:REPORT" , f"❌ db exception: {e!r}")
            return None

        if not totals_row:
            self._ch("DELBAL:REPORT" , "🟡 no totals row (unexpected)")
            return {"meta": {"data_type": data_type , "series_type": "none" , "note": ""} , "totals": {} ,
                "extremes": {} , "top_users": [ ] , "daily": [ ] , "hourly": [ ]}

        def _num(v , default=0):
            return default if v is None else v

        def _normalize_json_obj(v):
            if v is None:
                return None

            if isinstance(v , dict):
                return v

            if isinstance(v , str):
                s = v.strip()
                if not s:
                    return None
                try:
                    parsed = json.loads(s)
                    return parsed if isinstance(parsed , dict) else None
                except Exception:
                    return None

            try:
                if hasattr(v , "items"):
                    return dict(v)
            except Exception:
                pass

            return None

        totals = {"ops_count": int(totals_row.get("ops_count") or 0) ,
            "users_count": int(totals_row.get("users_count") or 0) ,
            "sum_balance": _num(totals_row.get("sum_balance") , 0) ,
            "avg_balance": _num(totals_row.get("avg_balance") , 0) ,
            "min_balance": _num(totals_row.get("min_balance") , 0) ,
            "max_balance": _num(totals_row.get("max_balance") , 0) , "first_dt": totals_row.get("first_dt") ,
            "last_dt": totals_row.get("last_dt") , }

        extremes = {"max_total_user": _normalize_json_obj(
            extremes_users_row.get("max_total_user")) if extremes_users_row else None ,
            "min_total_user": _normalize_json_obj(
                extremes_users_row.get("min_total_user")) if extremes_users_row else None ,
            "max_single_op": _normalize_json_obj(extremes_ops_row.get("max_single_op")) if extremes_ops_row else None ,
            "min_single_op": _normalize_json_obj(
                extremes_ops_row.get("min_single_op")) if extremes_ops_row else None , }

        top_users: List [ Dict [ str , Any ] ] = [ ]
        for row in (top_rows or [ ]):
            top_users.append(
                {"user_id": int(row.get("user_id") or 0) , "cnt": int(row.get("cnt") or 0) ,
                    "sum_balance": _num(row.get("sum_balance") , 0) , "avg_balance": _num(row.get("avg_balance") , 0) ,
                    "min_balance": _num(row.get("min_balance") , 0) , "max_balance": _num(row.get("max_balance") , 0) ,
                    "first_dt": row.get("first_dt") , "last_dt": row.get("last_dt") , })

        daily: List [ Dict [ str , Any ] ] = [ ]
        for row in (daily_rows or [ ]):
            daily.append(
                {"day": row.get("day") , "cnt": int(row.get("cnt") or 0) ,
                    "sum_balance": _num(row.get("sum_balance") , 0) , "avg_balance": _num(row.get("avg_balance") , 0) ,
                    "min_balance": _num(row.get("min_balance") , 0) ,
                    "max_balance": _num(row.get("max_balance") , 0) , })

        hourly: List [ Dict [ str , Any ] ] = [ ]
        for row in (hourly_rows or [ ]):
            hourly.append(
                {"hour": int(row.get("hour") or 0) , "cnt": int(row.get("cnt") or 0) ,
                    "sum_balance": _num(row.get("sum_balance") , 0) , "avg_balance": _num(row.get("avg_balance") , 0) ,
                    "min_balance": _num(row.get("min_balance") , 0) ,
                    "max_balance": _num(row.get("max_balance") , 0) , })

        if is_date_or_ts:
            series_type = "daily"
            note = ""
        elif is_time_only:
            series_type = "hourly"
            note = 'Колонка deletebalance."data" имеет тип TIME (без даты). Поэтому статистика "по дням" невозможна - показана по часам суток.'
        else:
            if hourly:
                series_type = "hourly"
            elif daily:
                series_type = "daily"
            else:
                series_type = "none"
            note = ""

        report = {"meta": {"data_type": data_type , "series_type": series_type , "note": note} , "totals": totals ,
            "extremes": extremes , "top_users": top_users , "daily": daily , "hourly": hourly , }

        self._ch(
            "DELBAL:REPORT" ,
            f"ok ops={totals [ 'ops_count' ]} users={totals [ 'users_count' ]} series={series_type} dtype={data_type}")
        return report











































####


    async def add_mute(self , chat_id , user_id , duration , start_time , unmute_time):
        query = """
            INSERT INTO mute (chat_id, user_id, mute, date, unmute)
            VALUES ($1, $2, $3, $4, $5)
        """
        try:
            async with self.pool.acquire() as conn:
                # Выполняем вставку данных о муте в таблицу mute
                await conn.execute(query , chat_id , user_id , duration , start_time , unmute_time)
                print(f"Пользователь {user_id} замучен до {unmute_time}")
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL17: {e}")
        except Exception as e:
            print(f"Произошла ошибка: {e}")


    # Проверка, есть ли пользователь в mute
    async def is_user_muted(self , chat_id , user_id):
        query = """
            SELECT unmute FROM mute 
            WHERE chat_id = $1 AND user_id = $2 AND unmute > $3
        """
        try:
            async with self.pool.acquire() as conn:
                # Выполняем запрос на проверку статуса мута
                result = await conn.fetchrow(query , chat_id , user_id , datetime.now())
                return result [ 'unmute' ] if result else None
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL1: {e}")
            return None
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return None

    async def add_crypto_check(self , invoice_id: str , user_id: int , first_name: str | None , username: str | None ,
            currency: str , crypto_amount: Decimal , base_kuts: int , bonus_kuts: int , total_kuts: int):
        """
        Сохраняет информацию о крипто-чеке в таблицу crypto_check.
        invoice_id - идентификатор инвойса (строка).
        """
        query = """
            INSERT INTO crypto_check
                (id, user_id, first_name, username, currency, crypto_amount, base_kuts, bonus_kuts, total_kuts)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO NOTHING
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query , invoice_id , user_id , first_name , username , currency , crypto_amount , base_kuts ,
                    bonus_kuts , total_kuts)
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL при сохранении чека {invoice_id}: {e}")
        except Exception as e:
            print(f"Неизвестная ошибка сохранения чека {invoice_id}: {e}")

    async def add_demo_amount(self , user_id: int , amount: int):
        """
        Увеличивает колонку demo пользователя на указанную сумму.
        Если колонки нет или она NULL, считаем начальное значение как 0.
        """
        query = """
            UPDATE users
            SET demo = COALESCE(demo, 0) + $1
            WHERE user_id = $2
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query , amount , user_id)
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL при обновлении demo для пользователя {user_id}: {e}")
        except Exception as e:
            print(f"Неизвестная ошибка при обновлении demo для пользователя {user_id}: {e}")

    async def get_user_demo(self , user_id: int) -> int:
        """
        Возвращает сумму, накопленную пользователем в колонке demo.
        Если пользователь не найден или колонка NULL - возвращает 0.
        """
        query = """
            SELECT COALESCE(demo, 0)
            FROM users
            WHERE user_id = $1
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query , user_id)
                if row is None:
                    print(f"[get_user_demo] Пользователь {user_id} не найден, возвращаю 0")
                    return 0
                return row [ 0 ]
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL при получении demo для пользователя {user_id}: {e}")
            return 0
        except Exception as e:
            print(f"Неизвестная ошибка при получении demo для пользователя {user_id}: {e}")
            return 0

    async def deduct_demo_amount(self , user_id: int , amount: int):
        """
        Списывает указанную сумму из колонки demo пользователя.
        Сумма должна быть положительной.
        Если demo становится отрицательным – устанавливается в 0.
        """
        query = """
            UPDATE users
            SET demo = GREATEST(COALESCE(demo, 0) - $1, 0)
            WHERE user_id = $2
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query , amount , user_id)
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL при списании demo для пользователя {user_id}: {e}")
        except Exception as e:
            print(f"Неизвестная ошибка при списании demo для пользователя {user_id}: {e}")

    async def get_user_0demo(self , user_id: int) -> int:
        """
        Возвращает сумму в колонке 0demo.
        Если пользователь не найден или колонка NULL - возвращает 0.
        """
        query = """
            SELECT COALESCE("0demo", 0)
            FROM users
            WHERE user_id = $1
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query , user_id)
                if row is None:
                    print(f"[get_user_0demo] Пользователь {user_id} не найден, возвращаю 0")
                    return 0
                return row [ 0 ]
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL при получении 0demo для пользователя {user_id}: {e}")
            return 0
        except Exception as e:
            print(f"Неизвестная ошибка при получении 0demo для пользователя {user_id}: {e}")
            return 0

    async def add_0demo_amount(self , user_id: int , amount: int):
        """
        Увеличивает колонку 0demo пользователя на указанную сумму.
        Используется при переводе «дддать».
        """
        query = """
            UPDATE users
            SET "0demo" = COALESCE("0demo", 0) + $1
            WHERE user_id = $2
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query , amount , user_id)
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL при обновлении 0demo для пользователя {user_id}: {e}")
        except Exception as e:
            print(f"Неизвестная ошибка при обновлении 0demo для пользователя {user_id}: {e}")

    async def deduct_0demo_amount(self , user_id: int , amount: int):
        """
        Списывает указанную сумму из колонки 0demo пользователя.
        Сумма должна быть положительной.
        Если 0demo становится отрицательным – устанавливается в 0.
        """
        query = """
            UPDATE users
            SET "0demo" = GREATEST(COALESCE("0demo", 0) - $1, 0)
            WHERE user_id = $2
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query , amount , user_id)
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL при списании 0demo для пользователя {user_id}: {e}")
        except Exception as e:
            print(f"Неизвестная ошибка при списании 0demo для пользователя {user_id}: {e}")

    async def get_all_users_with_positive_demo(self):
        """Все пользователи, у которых demo > 0"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, demo FROM users WHERE demo > 0 ORDER BY demo DESC")
        return [ dict(row) for row in rows ]

    async def get_all_users_with_positive_0demo(self):
        """Все пользователи, у которых 0demo > 0"""
        async with self.pool.acquire() as conn:
            # Двойные кавычки вокруг имени столбца, если оно начинается с цифры
            rows = await conn.fetch(
                'SELECT user_id, "0demo" FROM users WHERE "0demo" > 0 ORDER BY "0demo" DESC')  # Возвращаем с ключом "0demo", чтобы функция могла его забрать
        return [ {"user_id": row [ "user_id" ] , "0demo": row [ "0demo" ]} for row in rows ]

    async def add_home_amount(self , user_id: int , amount: int):
        """
        Увеличивает колонку home пользователя на указанную сумму.
        Вызывается при попадании в ловушку «дом».
        """
        query = """
            UPDATE users
            SET home = COALESCE(home, 0) + $1
            WHERE user_id = $2
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query , amount , user_id)
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL при обновлении home для пользователя {user_id}: {e}")
        except Exception as e:
            print(f"Неизвестная ошибка при обновлении home для пользователя {user_id}: {e}")

    async def get_user_home(self , user_id: int) -> int:
        """
        Возвращает текущую сумму в колонке home для пользователя.
        Если записи нет - 0.
        """
        query = "SELECT COALESCE(home, 0) FROM users WHERE user_id = $1"
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query , user_id)
                return row [ 0 ] if row else 0
        except Exception as e:
            print(f"Ошибка получения home для {user_id}: {e}")
            return 0

    async def subtract_home_amount(self , user_id: int , amount: int):
        """
        Уменьшает колонку home пользователя на указанную сумму (но не ниже 0).
        Используется при успешном выкупе.
        """
        query = """
            UPDATE users
            SET home = GREATEST(COALESCE(home, 0) - $1, 0)
            WHERE user_id = $2
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query , amount , user_id)
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL при вычитании home для {user_id}: {e}")
        except Exception as e:
            print(f"Неизвестная ошибка при вычитании home для {user_id}: {e}")

    async def get_black_market_kuts(self) -> int:
        query = "SELECT COALESCE(available, 0) FROM black_market LIMIT 1"
        row = await self.pool.fetchrow(query)
        return row [ 0 ] if row else 0

    async def _ensure_black_market_shop_deposits_table(self) -> bool:
        if self._black_market_shop_deposits_table_ready:
            return True

        query = """
            CREATE TABLE IF NOT EXISTS black_market_shop_deposits (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                source_chat_id BIGINT,
                target_chat_id BIGINT NOT NULL,
                amount BIGINT NOT NULL CHECK (amount > 0),
                note TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_bm_shop_deposits_user_created
                ON black_market_shop_deposits (user_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_bm_shop_deposits_target_created
                ON black_market_shop_deposits (target_chat_id, created_at DESC);
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query)
            self._black_market_shop_deposits_table_ready = True
            return True
        except Exception as e:
            print(f"[BLACK_MARKET][ERR] ensure table failed: {e}")
            return False

    async def record_shop_purchase_black_market_deposit(
        self,
        bot,
        user_id: int,
        amount: int,
        source_chat_id: Optional[int] = None,
        note: str = "",
        target_chat_id: int = -1003855337972,
    ) -> bool:
        """
        Регистрирует взнос в чёрный рынок и пополняет баланс целевой группы.

        ВАЖНО:
        - используется вместо legacy dexbalance
        - всегда пишет, кто и сколько внёс
        """
        try:
            user_id = int(user_id)
            amount = int(round(float(amount)))
            target_chat_id = int(target_chat_id)
            source_chat_id = int(source_chat_id) if source_chat_id is not None else None
        except Exception:
            return False

        if amount <= 0:
            return False

        if not await self._ensure_black_market_shop_deposits_table():
            return False

        note_text = (str(note or "").strip())[:255]

        balance_ok = await self.update_chat_balance(bot , target_chat_id , amount)
        if not balance_ok:
            print(
                f"[BLACK_MARKET][ERR] balance top-up failed "
                f"chat_id={target_chat_id} amount={amount}"
            )
            return False

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO black_market_shop_deposits
                    (user_id, source_chat_id, target_chat_id, amount, note)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    user_id,
                    source_chat_id,
                    target_chat_id,
                    amount,
                    note_text,
                )
            return True
        except Exception as e:
            print(f"[BLACK_MARKET][ERR] log insert failed, reverting balance: {e}")
            try:
                await self.update_chat_balance(bot , target_chat_id , -amount)
            except Exception as rollback_err:
                print(f"[BLACK_MARKET][CRIT] rollback failed: {rollback_err}")
            return False









#код для автопилота
    async def update_game_last_activity(self , user_id: int):
        """
        Записывает в колонку game_last_activity текущие дату и время
        в формате 'дд.мм.гггг | чч:мм'.
        """
        # Формируем строку сейчас, чтобы не нагружать БД лишней логикой
        time_str = datetime.now().strftime("%d.%m.%Y | %H:%M")
        query = """
            UPDATE users
            SET game_last_activity = $1
            WHERE user_id = $2
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query , time_str , user_id)
        except asyncpg.exceptions.PostgresError as e:
            print(f"Ошибка PostgreSQL при обновлении game_last_activity для {user_id}: {e}")
        except Exception as e:
            print(f"Неизвестная ошибка при обновлении game_last_activity для {user_id}: {e}")

    async def get_game_last_activity(self , user_id: int) -> str | None:
        query = "SELECT game_last_activity FROM users WHERE user_id = $1"
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query , user_id)
                return row [ 0 ] if row else None
        except Exception as e:
            print(f"Ошибка получения game_last_activity для {user_id}: {e}")
            return None








    async def set_consecutive_0demo(self, user_id: int, value: int):
        """Сброс или установка счётчика подряд проигрышей по 0demo."""
        query = """
            UPDATE users
            SET consecutive_0demo_losses = $1
            WHERE user_id = $2
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query, value, user_id)
        except Exception as e:
            print(f"Ошибка установки consecutive_0demo_losses для {user_id}: {e}")

    async def update_consecutive_0demo_losses(self, user_id: int, cause: str, is_loss: bool):
        """Обновляет счётчик после каждой игры (см. начало диалога)."""
        if is_loss and "0demo" in cause:
            query = """
                UPDATE users
                SET consecutive_0demo_losses = COALESCE(consecutive_0demo_losses, 0) + 1
                WHERE user_id = $1
            """
        else:
            query = """
                UPDATE users
                SET consecutive_0demo_losses = 0
                WHERE user_id = $1
            """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query, user_id)
        except Exception as e:
            print(f"Ошибка обновления счётчика 0demo-серии для {user_id}: {e}")

    # ------ получение последних действий (и проигрышей, и выигрышей) ------
    async def _get_recent_actions(self, user_id: int, limit: int = 15) -> list:
        """Последние N игровых записей с информацией о ставке/выигрыше."""
        all_causes = list(self.LOSS_CAUSES) + list(self.WIN_CAUSES)
        query = """
            SELECT cause, "-" AS bet_amount, "+" AS win_amount, data
            FROM cutehistory
            WHERE user_id = $1 AND cause = ANY($2::text[])
            ORDER BY data DESC
            LIMIT $3
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, user_id, all_causes, limit)
                actions = []
                for row in rows:
                    actions.append({
                        "cause": row["cause"],
                        "bet_amount": row["bet_amount"],
                        "win_amount": row["win_amount"],
                        "data": row["data"],
                        "is_loss": row["cause"].startswith("-"),
                    })
                return actions
        except Exception as e:
            print(f"Ошибка получения последних действий для {user_id}: {e}")
            return []


    async def get_consecutive_0demo_losses(self, user_id: int) -> int:
        query = "SELECT COALESCE(consecutive_0demo_losses, 0) FROM users WHERE user_id = $1"
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, user_id)
                return row[0] if row else 0
        except Exception as e:
            print(f"Ошибка получения consecutive_0demo_losses для {user_id}: {e}")
            return 0


    async def get_user_reg_date(self , user_id: int) -> Optional [ str ]:
        """Возвращает строку с датой регистрации из колонки data."""
        query = "SELECT data FROM users WHERE user_id = $1"
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query , user_id)
                return row [ 0 ] if row else None
        except Exception:
            return None

    async def get_profit_last_n(self , user_id: int , n: int) -> float:
        """Чистый профиль за последние n игр."""
        # Соберём все возможные паттерны, как в _fetch_recent_actions
        from bot.config.config import LOSS_CAUSES,WIN_CAUSES
        all_patterns = [ f"- {c}" for c in LOSS_CAUSES ] + [ f"+ {c}" for c in WIN_CAUSES ]
        query = """
            SELECT COALESCE(SUM(win), 0) - COALESCE(SUM(loss), 0) AS profit
            FROM (
                SELECT
                    CASE WHEN cause LIKE '+ %' THEN "+" ELSE 0 END AS win,
                    CASE WHEN cause LIKE '- %' THEN "-" ELSE 0 END AS loss
                FROM cutehistory
                WHERE user_id = $1 AND cause = ANY($2::text[])
                ORDER BY data DESC
                LIMIT $3
            ) sub
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query , user_id , all_patterns , n)
                return float(row [ 0 ]) if row and row [ 0 ] else 0.0
        except Exception:
            return 0.0




    async def get_newbie_expires_at(self , user_id: int) -> Optional [ datetime ]:
        query = "SELECT newbie_expires_at FROM users WHERE user_id = $1"
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query , user_id)
                return row [ 0 ] if row else None
        except Exception:
            return None

    async def set_newbie_expires_at(self , user_id: int , dt: datetime) -> None:
        query = "UPDATE users SET newbie_expires_at = $1 WHERE user_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query , dt , user_id)

    async def get_newbie_demo_rescues(self , user_id: int) -> int:
        query = "SELECT COALESCE(newbie_demo_rescues, 0) FROM users WHERE user_id = $1"
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query , user_id)
                return int(row [ 0 ]) if row else 0
        except Exception:
            return 0

    async def set_newbie_demo_rescues(self , user_id: int , value: int) -> None:
        query = "UPDATE users SET newbie_demo_rescues = $1 WHERE user_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query , value , user_id)

    async def get_newbie_total_demo_given(self , user_id: int) -> int:
        query = "SELECT COALESCE(newbie_total_demo_given, 0) FROM users WHERE user_id = $1"
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query , user_id)
                return int(row [ 0 ]) if row else 0
        except Exception:
            return 0

    async def set_newbie_total_demo_given(self , user_id: int , value: int) -> None:
        query = "UPDATE users SET newbie_total_demo_given = $1 WHERE user_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query , value , user_id)




    async def get_welcome_back_count(self , user_id: int) -> int:
        query = "SELECT COALESCE(welcome_back_count, 0) FROM users WHERE user_id = $1"
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query , user_id)
                return int(row [ 0 ]) if row else 0
        except Exception:
            return 0

    async def set_welcome_back_count(self , user_id: int , value: int) -> None:
        query = "UPDATE users SET welcome_back_count = $1 WHERE user_id = $2"
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query , value , user_id)
        except Exception as e:
            print(f"Ошибка обновления welcome_back_count: {e}")








































































#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_
#Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_Garden_of_Eden_

    async def eden_add_plant(self, owner_id: int, chat_id: int, message_id: int,
                             plant_type: str, water_level: float = 100):
        """Добавляет новое растение."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO eden_plants (owner_id, chat_id, message_id, plant_type, "
                "water_level, planted_at, last_update) VALUES ($1,$2,$3,$4,$5,NOW(),NOW())",
                owner_id, chat_id, message_id, plant_type, water_level
            )

    async def eden_get_user_plants(self, owner_id: int):
        """Возвращает список всех растений пользователя."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM eden_plants WHERE owner_id = $1", owner_id
            )
            return [dict(row) for row in rows]

    async def eden_get_plant(self, plant_id: int):
        """Возвращает одно растение по id или None."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM eden_plants WHERE id = $1", plant_id
            )
            return dict(row) if row else None

    async def eden_update_plant(self, plant_id: int, **kwargs):
        """Обновляет поля растения (stage, progress, water_level, message_id, last_update)."""
        allowed = {"stage", "progress", "water_level", "message_id", "last_update"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
        values = list(updates.values())
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"UPDATE eden_plants SET {set_clause} WHERE id = $1",
                plant_id, *values
            )

    async def eden_delete_plant(self, plant_id: int):
        """Удаляет растение."""
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM eden_plants WHERE id = $1", plant_id)
    async def _get_inventory_dex_reference(self) -> Tuple [ Set [ str ] , Dict [ str , str ] , Dict [ str , str ] ]:
        """
        Быстрый справочник dex для валидации users.items.

        Возвращает:
        - valid_names: точные dex.name
        - lower_to_name: casefold(name) -> канонический dex.name
        - emoji_to_name: emoji -> канонический dex.name (первое совпадение по id)
        """
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        ttl_sec = 60.0
        now = time.monotonic()
        cache_ts = float(getattr(self , "_inventory_dex_ref_ts" , 0.0))
        cached = getattr(self , "_inventory_dex_ref" , None)
        if cached and (now - cache_ts) <= ttl_sec:
            return cached [ "valid_names" ] , cached [ "lower_to_name" ] , cached [ "emoji_to_name" ]

        lock = getattr(self , "_inventory_dex_ref_lock" , None)
        if lock is None:
            lock = asyncio.Lock()
            self._inventory_dex_ref_lock = lock

        async with lock:
            now = time.monotonic()
            cache_ts = float(getattr(self , "_inventory_dex_ref_ts" , 0.0))
            cached = getattr(self , "_inventory_dex_ref" , None)
            if cached and (now - cache_ts) <= ttl_sec:
                return cached [ "valid_names" ] , cached [ "lower_to_name" ] , cached [ "emoji_to_name" ]

            async with self.pool.acquire() as connection:
                rows = await connection.fetch("SELECT name, emoji FROM dex ORDER BY id ASC")

            valid_names: Set [ str ] = set()
            lower_to_name: Dict [ str , str ] = {}
            emoji_to_name: Dict [ str , str ] = {}

            for row in rows:
                name = str(row [ "name" ] or "").strip()
                if not name:
                    continue

                valid_names.add(name)
                lower_key = name.casefold()
                if lower_key and lower_key not in lower_to_name:
                    lower_to_name [ lower_key ] = name

                emoji = str(row [ "emoji" ] or "").strip()
                if emoji and emoji not in emoji_to_name:
                    emoji_to_name [ emoji ] = name

            payload = {
                "valid_names": valid_names ,
                "lower_to_name": lower_to_name ,
                "emoji_to_name": emoji_to_name ,
            }
            self._inventory_dex_ref = payload
            self._inventory_dex_ref_ts = time.monotonic()
            return valid_names , lower_to_name , emoji_to_name

    async def sanitize_user_inventory_against_dex(self , user_id: int) -> Dict [ str , int ]:
        """
        Санитизация users.items при открытии инвентаря:
        - принимает ключи, которые существуют в dex по name или emoji;
        - emoji/alias-ключи приводит к каноническому dex.name;
        - предметы, которых нет в dex, удаляет;
        - записывает обратно только если есть реальные изменения.
        """
        if not self.pool:
            raise ValueError("Соединение с базой данных не инициализировано.")

        try:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    "SELECT items FROM users WHERE user_id = $1" , user_id)

            if not row:
                return {}

            raw_val = row [ "items" ]
            decoded = decode_items(raw_val)
            normalized = normalize_inventory(decoded)

            raw_str = raw_val if isinstance(raw_val , str) else None
            raw_nonempty = bool(raw_str and raw_str.strip() not in ("" , "{}" , '"{}"'))

            # Защита от потери данных: если поле непустое, но не распарсилось,
            # не перезаписываем его.
            if raw_nonempty and not decoded:
                return {}

            if not normalized:
                empty_canonical = encode_items({})
                if raw_str != empty_canonical and not (raw_nonempty and not decoded):
                    async with self.pool.acquire() as connection:
                        await connection.execute(
                            "UPDATE users SET items = $1 WHERE user_id = $2" ,
                            empty_canonical ,
                            user_id)
                return {}

            valid_names , lower_to_name , emoji_to_name = await self._get_inventory_dex_reference()

            cleaned: Dict [ str , int ] = {}
            removed_count = 0
            remapped_count = 0

            for raw_key , qty in normalized.items():
                token = str(raw_key or "").strip()
                if not token:
                    removed_count += 1
                    continue

                canonical_name = None
                if token in valid_names:
                    canonical_name = token
                elif token in emoji_to_name:
                    canonical_name = emoji_to_name [ token ]
                else:
                    canonical_name = lower_to_name.get(token.casefold())

                if not canonical_name:
                    removed_count += 1
                    continue

                if canonical_name != token:
                    remapped_count += 1

                cleaned [ canonical_name ] = cleaned.get(canonical_name , 0) + int(qty)

            source_canonical = encode_items(normalized)
            cleaned_canonical = encode_items(cleaned)

            if cleaned_canonical != source_canonical:
                async with self.pool.acquire() as connection:
                    await connection.execute(
                        "UPDATE users SET items = $1 WHERE user_id = $2" ,
                        cleaned_canonical ,
                        user_id)

                if removed_count or remapped_count:
                    print(
                        f"[INV][SANITIZE] user_id={user_id} "
                        f"removed={removed_count}, remapped={remapped_count}, left={len(cleaned)}")

            return cleaned

        except Exception as e:
            print(f"[ERROR] sanitize_user_inventory_against_dex user_id={user_id}: {e}")
            return await self.get_user_inventory(user_id)
    async def get_referrals_with_details(self , referrer_id: int) -> List [ Dict [ str , Any ] ]:
        """Возвращает список пользователей, у которых refferer_id = referrer_id."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, first_name, username
                FROM users
                WHERE refferer_id = $1
                ORDER BY user_id
                """ , referrer_id)
            return [ dict(row) for row in rows ]
# Singleton used across the bot (main.py, handlers, games).
db = Database(db_settings)


