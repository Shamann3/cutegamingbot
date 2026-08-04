# -*- coding: utf-8 -*-
# bot/db_create/pklcode.py
# ------------------------------------------------------------
# GameStore: pkl-подобный снапшот на Redis (без файлов).
# Принцип сохранения/загрузки СТРОГО как в исходнике:
#  - данные = pickle((dict, timestamps)), опционально zlib
#  - малые снимки → pkl:{name}:blob
#  - крупные снимки → pkl:{name}:chunk:0000.. + pkl:{name}:meta
#  - чтение учитывает decode_responses=True (но payload всегда bytes → raw-client)
#
# ✅ Фиксы + ускорение под нагрузкой:
#  1) payload I/O только raw Redis (decode_responses=False), bytes
#  2) initial_sync не выключается навсегда при временном падении Redis
#  3) Самолечение чтения НЕ на каждом GET, а только если реально надо
#  4) Удаление чанков БЕЗ SCAN: удаляем ровно 0..last_chunk_count-1
#  5) Загрузка чанков через MGET (1 roundtrip вместо N)
# ------------------------------------------------------------

from __future__ import annotations

import os
import atexit
import pickle
import socket
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Tuple, Optional, Iterable, List, Set, Callable
import zlib
import heapq
import copy
import signal
import concurrent.futures

import redis  # type: ignore

from bot.db_create import hash_backend


# ========= ОТЛАДКА =========
ENABLE_DEBUG_PRINTS = False
SHOW_KEY_OPS = bool(int(os.getenv("PKL_DEBUG_KEY_OPS", "0")))
# ===========================

# ---------- эмодзи ----------
_GREEN = ("🌿", "🍀", "🍃", "🌱", "🌲", "🌳")
_RED = ("🔥", "🔴", "🍓", "🌶️", "🍎")


def _g(i: int) -> str:
    return _GREEN[i % len(_GREEN)]


def _r(i: int) -> str:
    return _RED[i % len(_RED)]


# ---------- уровни логов ----------
LVL_DEBUG = 10
LVL_INFO = 20
LVL_WARN = 30
LVL_ERROR = 40
LVL_SILENT = 50

_env_lvl = os.getenv("PKL_LOG_LEVEL")
if ENABLE_DEBUG_PRINTS:
    LOG_LEVEL = LVL_DEBUG
else:
    try:
        LOG_LEVEL = int(_env_lvl) if _env_lvl is not None else LVL_ERROR
    except Exception:
        LOG_LEVEL = LVL_ERROR


def _safe_console(msg: str) -> None:
    """print, устойчивый к консоли cp1251 (Windows) без UnicodeEncodeError."""
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            print(msg.encode("ascii", errors="backslashreplace").decode("ascii"))
        except Exception:
            pass


def _log(level: int, msg: str) -> None:
    if level >= LOG_LEVEL:
        _safe_console(msg)


def _dbg(msg: str) -> None:
    _log(LVL_DEBUG, f"[DBG] {msg}")


def _ok(msg: str) -> None:
    _log(LVL_INFO, msg)


def _warn(msg: str) -> None:
    _log(LVL_WARN, msg)


def _err(msg: str) -> None:
    _log(LVL_ERROR, msg)


def _ev(store: Optional[str], event: str, details: str = "") -> None:
    if LOG_LEVEL > LVL_DEBUG:
        return
    prefix = "[PKL]" + (f"[{store}]" if store else "")
    _dbg(f"{prefix}[{event}] {details}".strip())


# Публичные переключатели
def set_log_level(level: int) -> None:
    global LOG_LEVEL
    LOG_LEVEL = level
    _ok(f"🔧 Уровень логов установлен: {level}")


def enable_debug() -> None:
    set_log_level(LVL_DEBUG)


def enable_info() -> None:
    set_log_level(LVL_INFO)


def disable_debug() -> None:
    set_log_level(LVL_ERROR)


def mute_logs() -> None:
    set_log_level(LVL_SILENT)
    print("🔇 Логи отключены полностью (SILENT)")


# ---------- настройки ----------
EXCLUDED_STORES = (
    "groupsrassilka",
    "broadcast_state",
    "textrassilka",
    "fotorassilka",
    "user_cache_balance",
    "group_cache",
    "user_cache",
    "u",
    "ADMIN_WITHDRAW_ACTIONS",
    # ✅ настройки меню подарков (sypheraddgift/sypherupdategift) - постоянные
    # данные, не должны протухать по TTL как временные кэши/pending-действия
    "_gift_menu_emoji_overrides",
    "_gift_menu_manual_gifts",
)
# NO_DELETE_STORES не включает меню подарков: там нужен рабочий явный del
# (кнопки "Удалить подарок" / "Вернуть базовое эмодзи"), просто без авто-TTL
NO_DELETE_STORES = set(EXCLUDED_STORES) - {"_gift_menu_emoji_overrides", "_gift_menu_manual_gifts"}

AUTO_WARMUP = bool(int(os.getenv("PKL_AUTO_WARMUP", "0")))
PRINT_SUMMARY = bool(int(os.getenv("PKL_SUMMARY", "1")))

# ВАЖНО: 0 = сохранять СИНХРОННО прямо в вызывающем потоке. Так как pklcode
# вызывается из корутин (event-loop), синхронный _save_now() блокирует весь
# цикл на время Redis-записи (socket recv) при всплеске записей (warmup,
# массовые апдейты) loop замирает на секунды/минуты, и бот перестаёт отвечать.
# Положительное значение уводит сохранение в фоновый threading.Timer и
# коалесцирует всплеск записей в одно сохранение. НЕ ставить 0 на проде.
WRITE_DEBOUNCE_MS = int(os.getenv("PKL_WRITE_DEBOUNCE_MS", "1000"))
FORCE_SAVE_MS = int(os.getenv("PKL_FORCE_SAVE_MS", "15000"))
SAVE_OPS_THRESHOLD = int(os.getenv("PKL_SAVE_OPS_THRESHOLD", "5000"))

DEFAULT_EXPIRY_SECONDS = int(os.getenv("PKL_DEFAULT_EXPIRY_SECONDS", "7200"))
CLEANUP_INTERVAL_SEC = int(os.getenv("PKL_CLEANUP_INTERVAL_SEC", "5"))

# expiry_seconds >= этого значения означает "никогда не истекает"
NEVER_EXPIRE_SEC = 10 ** 9

# ============================================================
# Сроки жизни, отличные от DEFAULT_EXPIRY_SECONDS.
# ------------------------------------------------------------
# ВАЖНО: политика TTL должна быть известна В МОМЕНТ создания стора.
# Раньше её выставляли постфактум (`store.expiry_seconds = ...` в
# bot/admins/punish_timers.py и bot/funcs/king_stats.py), и между созданием
# стора и этой строкой существовало окно, в котором уборщик видел дефолтные
# 2 часа. С прогревом на старте окно растягивается на всё время до импорта
# соответствующего модуля - и наказания/привязки меню сносились при каждом
# перезапуске. Поэтому политика живёт здесь, рядом с EXCLUDED_STORES.
STORE_EXPIRY_OVERRIDES: Dict[str, float] = {
    # Наказания действуют до своей даты снятия, уборщик их трогать не должен.
    # (в EXCLUDED_STORES не добавляем: там нужен рабочий явный del)
    "mod_punish_timers": float(NEVER_EXPIRE_SEC),
    # Сообщение меню висит в чате неделями - привязки держим 30 дней.
    "_KING_MENU_OWNERS": 30 * 24 * 3600.0,
    "_KING_MENU_TARGET": 30 * 24 * 3600.0,
    "_KING_MENU_RENDER_STATE": 30 * 24 * 3600.0,
    "_KING_DM_LAST_MENU": 30 * 24 * 3600.0,
    # Inline-кнопки вывода (prep:/greq:/srq:/skipcb:) живут в чате часами.
    # Дефолтный TTL GameStore = 2ч убивал токены раньше app-cleanup → «Ошибка данных».
    "PREP_CALLBACK_ACTIONS": 7 * 24 * 3600.0,
    "GIFT_CALLBACK_ACTIONS": 7 * 24 * 3600.0,
    "SKIP_CALLBACK_ACTIONS": 7 * 24 * 3600.0,
    "SPEEDCONC_CALLBACK_ACTIONS": 7 * 24 * 3600.0,
    "SEND_REQUEST_ACTIONS": 7 * 24 * 3600.0,
}


def register_store_expiry(name: str, seconds: float) -> None:
    """
    Объявить срок жизни стора. Работает и до его создания, и после.

    Вызывай это вместо `store.expiry_seconds = ...`: присваивание атрибута
    действует только с момента вызова, а реестр - с момента создания стора.
    """
    STORE_EXPIRY_OVERRIDES[name] = float(seconds)
    inst = GameStore._instances.get(name)
    if inst is not None:
        inst.expiry_seconds = float(seconds)


def _expiry_for(name: str) -> float:
    return float(STORE_EXPIRY_OVERRIDES.get(name, DEFAULT_EXPIRY_SECONDS))
# ============================================================

COMPRESS_ZLIB = bool(int(os.getenv("PKL_COMPRESS", "1")))
ZLIB_LEVEL = int(os.getenv("PKL_ZLIB_LEVEL", "3"))

CHUNK_THRESHOLD_BYTES = int(os.getenv("PKL_CHUNK_THRESHOLD_BYTES", str(64 * 1024 * 1024)))
CHUNK_SIZE_BYTES = int(os.getenv("PKL_CHUNK_SIZE_BYTES", str(16 * 1024 * 1024)))

PKL_PURGE_ON_BOOT = bool(int(os.getenv("PKL_PURGE_ON_BOOT", "0")))
PKL_BOOT_RESET_STORES = os.getenv("PKL_BOOT_RESET_STORES", "").strip()
PKL_BOOT_RESET_RAM = bool(int(os.getenv("PKL_BOOT_RESET_RAM", "0")))

PKL_HEALTH_WATCHER = bool(int(os.getenv("PKL_HEALTH_WATCHER", "1")))
PKL_HEALTHCHECK_INTERVAL_SEC = int(os.getenv("PKL_HEALTHCHECK_INTERVAL_SEC", "3"))
PKL_ASYNC_WARMUP = bool(int(os.getenv("PKL_ASYNC_WARMUP", "1")))

TOUCH_ON_GET = bool(int(os.getenv("PKL_TOUCH_ON_GET", "1")))
TOUCH_SAVE_MS = int(os.getenv("PKL_TOUCH_SAVE_MS", "5000"))
TOUCH_BATCH_MAX = int(os.getenv("PKL_TOUCH_BATCH_MAX", "500"))

# ✅ самолечение чтения: включено, но "ленивое"
PKL_HEAL_READ_TIMEOUT_SEC = float(os.getenv("PKL_HEAL_READ_TIMEOUT_SEC", "1.20"))
PKL_HEAL_RETRY_DELAY_SEC = float(os.getenv("PKL_HEAL_RETRY_DELAY_SEC", "0.06"))
PKL_HEAL_FORCE_RELOAD_ON_MISS = bool(int(os.getenv("PKL_HEAL_FORCE_RELOAD_ON_MISS", "1")))
PKL_HEAL_RELOAD_COOLDOWN_SEC = float(os.getenv("PKL_HEAL_RELOAD_COOLDOWN_SEC", "0.35"))

# ✅ быстрый путь (по умолчанию включен): не трогаем самолечение если sync уже готов
PKL_FASTPATH_READS = bool(int(os.getenv("PKL_FASTPATH_READS", "1")))
# Пинговать Redis на КАЖДОМ чтении словаря дорого (синхронный раунд-трип в
# event-loop на каждый доступ). Данные и так лежат в памяти процесса, а фоновый
# health-watcher (PKL_HEALTH_WATCHER, каждые 3с) следит за Redis. Поэтому пинг на
# чтении по умолчанию ВЫКЛЮЧЕН чтения становятся чисто in-memory (быстро).
PKL_FASTPATH_PING = bool(int(os.getenv("PKL_FASTPATH_PING", "0")))

# hash = per-key Redis Hash (быстро, не деградирует со временем)
# blob = legacy full-dict pickle snapshot
PKL_STORAGE_MODE = os.getenv("PKL_STORAGE_MODE", "hash").strip().lower()
PKL_IO_THREADS = int(os.getenv("PKL_IO_THREADS", "2"))

# ============================================================
# ✅ v2: ноль Redis-I/O в горячем пути (event-loop)
# ------------------------------------------------------------
# Чтение обслуживается ТОЛЬКО из памяти процесса, запись помечает ключ грязным
# и уходит в единый фоновый писатель. Ставь 0, чтобы вернуть прежнее поведение.
PKL_HOT_PATH_V2 = bool(int(os.getenv("PKL_HOT_PATH_V2", "1")))

# Данными владеет один процесс: память авторитетна, промах чтения - это промах,
# а не повод перезаливать весь стор из Redis. Если запустишь несколько процессов
# на одну БД Redis - поставь 0 (вернётся reload-on-miss).
PKL_SINGLE_PROCESS = bool(int(os.getenv("PKL_SINGLE_PROCESS", "1")))

# Сколько ключей просматривать за один шаг подметания TTL (чтобы не держать
# _lock надолго на сторах с сотнями тысяч ключей).
PKL_SWEEP_BUDGET = int(os.getenv("PKL_SWEEP_BUDGET", "20000"))

# Страховка для сторов, чей TTL не объявлен в STORE_EXPIRY_OVERRIDES: столько
# секунд после загрузки стор не подметается. Даёт модулям время выставить свой
# срок жизни до того, как уборщик что-то удалит.
PKL_SWEEP_GRACE_SEC = float(os.getenv("PKL_SWEEP_GRACE_SEC", "120"))

# Пауза перед повторной попыткой первичной загрузки, если Redis недоступен.
PKL_SYNC_RETRY_SEC = float(os.getenv("PKL_SYNC_RETRY_SEC", "2"))
# ============================================================


# ---------- единый фоновый писатель (вместо threading.Timer на каждую запись) ----------
# Прежняя схема создавала новый поток ОС на КАЖДУЮ запись в любой стор и
# отменяла предыдущий. При 200+ сторах это давало постоянную churn потоков и
# конкуренцию за GIL с event-loop. Теперь один поток обслуживает все сторы,
# коалесцируя всплеск записей в одно сохранение на стор.
_writer_cv = threading.Condition()
# name -> store. Держим сам объект, а не только имя: если GameStore._instances
# подменится (тесты, boot-reset), сохранение по имени ушло бы в ДРУГОЙ объект, а
# hash_save_keys трактует отсутствие ключа как удаление - то есть стёрло бы
# данные в Redis.
_writer_pending: Dict[str, "GameStore"] = {}
_writer_started = False


def _notify_writer(store: "GameStore") -> None:
    with _writer_cv:
        _writer_pending[store.name] = store
        _writer_cv.notify()


def _writer_loop() -> None:
    debounce = max(0.0, WRITE_DEBOUNCE_MS / 1000.0)
    while True:
        try:
            with _writer_cv:
                while not _writer_pending:
                    _writer_cv.wait(timeout=1.0)

            # Окно коалесцирования: собрать всплеск записей в одно сохранение.
            if debounce > 0:
                time.sleep(debounce)

            with _writer_cv:
                stores = list(_writer_pending.values())
                _writer_pending.clear()

            for store in stores:
                # Внутри bulk() сохранять нельзя: контекст сам сохранит один раз
                # на выходе. Возвращаем стор в очередь.
                if store._in_bulk > 0:
                    _notify_writer(store)
                    continue
                try:
                    with store._sync_lock:
                        store._save_now()
                except Exception:
                    pass
        except Exception:
            time.sleep(0.2)


def _start_writer() -> None:
    global _writer_started
    if _writer_started:
        return
    _writer_started = True
    threading.Thread(target=_writer_loop, name="pkl-writer", daemon=True).start()


# ---------- единый сборщик TTL (вместо потока _service_loop на каждый стор) ----------
_sweeper_started = False


def _sweeper_loop() -> None:
    interval = max(1, CLEANUP_INTERVAL_SEC)
    while True:
        try:
            for store in list(getattr(GameStore, "_instances", {}).values()):
                try:
                    store._sweep_expired_step()
                except Exception:
                    pass
                try:
                    store._maybe_flush_touch_ts()
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(interval)


def _start_sweeper() -> None:
    global _sweeper_started
    if _sweeper_started:
        return
    _sweeper_started = True
    threading.Thread(target=_sweeper_loop, name="pkl-sweeper", daemon=True).start()


# ---------- фоновый IO-пул (Redis не блокирует event-loop) ----------
_io_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
_io_executor_lock = threading.Lock()
_store_io_futures: Dict[str, List[concurrent.futures.Future]] = {}
_store_io_futures_lock = threading.Lock()


def _get_io_executor() -> concurrent.futures.ThreadPoolExecutor:
    global _io_executor
    with _io_executor_lock:
        if _io_executor is None:
            _io_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, PKL_IO_THREADS),
                thread_name_prefix="pkl-io",
            )
        return _io_executor


def _io_submit(store_name: str, fn: Callable, *args, wait: bool = False, timeout: float = 5.0):
    """Запуск Redis-операции в фоновом потоке. wait=True только для flush/load."""
    try:
        fut = _get_io_executor().submit(fn, *args)
    except RuntimeError:
        # На выходе из процесса пул уже закрыт ("cannot schedule new futures
        # after shutdown"). Раньше это роняло первичную загрузку стора; лучше
        # выполнить операцию прямо здесь - мы и так в потоке завершения.
        return fn(*args)
    with _store_io_futures_lock:
        _store_io_futures.setdefault(store_name, []).append(fut)
    if wait:
        try:
            return fut.result(timeout=max(0.05, float(timeout)))
        finally:
            with _store_io_futures_lock:
                lst = _store_io_futures.get(store_name, [])
                if fut in lst:
                    lst.remove(fut)
    return fut


def _io_wait_store(store_name: str, timeout: float = 10.0) -> None:
    """Дождаться всех pending IO-операций стора (для flush/shutdown)."""
    with _store_io_futures_lock:
        futs = list(_store_io_futures.get(store_name, []))
    for fut in futs:
        try:
            fut.result(timeout=max(0.05, float(timeout)))
        except Exception:
            pass
    with _store_io_futures_lock:
        _store_io_futures.pop(store_name, None)


# ---------- глобальные клиенты ----------
_rds = None
_rds_raw = None
_purged_once = False
_raw_lock = threading.Lock()


def _client():
    return _rds


def _raw_client():
    return _rds_raw


def _mask_conn_kwargs(kw: Dict[str, Any]) -> Dict[str, Any]:
    safe = dict(kw or {})
    if safe.get("password"):
        safe["password"] = "***"
    return safe


def _raw_client_from(rds_any) -> Optional["redis.Redis"]:
    if redis is None or rds_any is None:  # type: ignore
        return None
    try:
        kw = getattr(rds_any, "connection_pool").connection_kwargs.copy()
    except Exception:
        return None

    host = kw.get("host", "127.0.0.1")
    port = int(kw.get("port", 6379))
    db = int(kw.get("db", 0))
    password = kw.get("password")
    username = kw.get("username")
    ssl = kw.get("ssl", False)

    try:
        raw = redis.Redis(  # type: ignore
            host=host,
            port=port,
            db=db,
            password=password,
            username=username,
            ssl=ssl,
            decode_responses=False,
            socket_timeout=3,
            socket_connect_timeout=3,
            health_check_interval=15,
        )
        raw.ping()
        return raw
    except Exception:
        return None


def _raw_ping_ok() -> bool:
    rc = _raw_client()
    if rc is None:
        return False
    try:
        rc.ping()
        return True
    except Exception:
        return False


def _wait_redis_ready(timeout: float = 2.0) -> bool:
    start = time.time()
    while (time.time() - start) < max(0.05, float(timeout)):
        if _raw_ping_ok():
            return True
        time.sleep(0.05)
    return _raw_ping_ok()


def _scan_delete_pattern_raw(rc, pattern: str, batch_del: int = 2000, scan_count: int = 1000) -> int:
    removed = 0
    try:
        cursor = 0
        pipe = rc.pipeline()
        batched = 0
        pat = pattern.encode("utf-8")
        while True:
            cursor, keys = rc.scan(cursor=cursor, match=pat, count=scan_count)
            if keys:
                for k in keys:
                    pipe.delete(k)
                    batched += 1
                if batched >= batch_del:
                    res = pipe.execute()
                    removed += sum(int(bool(x)) for x in res)
                    batched = 0
            if cursor == 0:
                break
        if batched:
            res = pipe.execute()
            removed += sum(int(bool(x)) for x in res)
    except Exception as e:
        _err(f"{_r(0)} [pklcode] scan_delete '{pattern}' error: {type(e).__name__}: {e}")
    return removed


def _purge_all_pkl_keys() -> int:
    rc = _raw_client()
    if rc is None:
        return 0
    return _scan_delete_pattern_raw(rc, "pkl:*")


def _purge_all_ram() -> int:
    stores = getattr(GameStore, "_instances", {}) or {}
    cnt = 0
    for s in list(stores.values()):
        try:
            with s._lock:
                dict.clear(s)
                s.timestamps.clear()
                s._expire_heap.clear()
                s._ops_total = s._ops_created = s._ops_updated = s._ops_skipped = 0
                s._ops_deleted = 0
                s._snapshots = 0
                s._ops_since_save = 0
                s._pending_dirty = False
                s._last_save_ts = 0.0
                s._need_initial_sync = True
                s._dirty_since_boot = False
                s._touch_dirty = False
                s._touch_count = 0
                s._last_touch_save_ts = 0.0
                s._hash_dirty_keys.clear()
                s._touch_keys.clear()
                s._sweep_keys = []
                s._sweep_pos = 0
                s._sync_retry_after = 0.0
        except Exception as e:
            _err(f"{_r(0)} [pklcode] purge RAM '{s.name}': {type(e).__name__}: {e}")
        else:
            cnt += 1
    return cnt


def purge_all_pkl_everywhere() -> None:
    global _purged_once
    removed = _purge_all_pkl_keys()
    cnt = _purge_all_ram()
    _ok(f"{_g(0)} [pklcode] PURGE: redis_keys_removed={removed}, ram_stores_cleared={cnt}")
    _purged_once = True


def _parse_patterns(csv: str) -> Tuple[Set[str], Set[str], bool]:
    inc: Set[str] = set()
    exc: Set[str] = set()
    has_wc = False
    for raw in (csv or "").split(","):
        name = raw.strip()
        if not name:
            continue
        if name == "*":
            has_wc = True
            continue
        if name.startswith("!"):
            n = name[1:].strip()
            if n:
                exc.add(n)
            continue
        inc.add(name)
    return inc, exc, has_wc


def _list_all_store_names() -> Set[str]:
    rc = _raw_client()
    names: Set[str] = set()
    try:
        names |= set(getattr(GameStore, "_instances", {}).keys())
    except Exception:
        pass
    if rc is None:
        return names

    for pattern in (b"pkl:*:blob", b"pkl:*:meta", b"pkl:*:data"):
        cursor = 0
        while True:
            cursor, keys = rc.scan(cursor=cursor, match=pattern, count=1000)
            for k in keys:
                s = k.decode("utf-8", "ignore")
                if s.startswith("pkl:"):
                    if s.endswith(":blob") or s.endswith(":meta"):
                        n = s[4:-5]
                    elif s.endswith(":data"):
                        n = s[4:-5]
                    else:
                        continue
                    if n:
                        names.add(n)
            if cursor == 0:
                break
    return names


def _delete_store_redis(store: str) -> int:
    rc = _raw_client()
    if rc is None:
        return 0
    removed = 0
    removed += hash_backend.hash_delete_store(rc, store)
    removed += _scan_delete_pattern_raw(rc, f"pkl:{store}:blob", scan_count=1000)
    removed += _scan_delete_pattern_raw(rc, f"pkl:{store}:meta", scan_count=1000)
    removed += _scan_delete_pattern_raw(rc, f"pkl:{store}:chunk:*", scan_count=1000)
    return removed


def _delete_store_ram(store: str) -> bool:
    gs = getattr(GameStore, "_instances", {}).get(store)
    if not gs:
        return False
    try:
        with gs._lock:
            dict.clear(gs)
            gs.timestamps.clear()
            gs._expire_heap.clear()
            gs._ops_total = gs._ops_created = gs._ops_updated = 0
            gs._ops_skipped = 0
            gs._ops_deleted = 0
            gs._snapshots = 0
            gs._ops_since_save = 0
            gs._pending_dirty = False
            gs._last_save_ts = 0.0
            gs._need_initial_sync = True
            gs._dirty_since_boot = False
            gs._touch_dirty = False
            gs._touch_count = 0
            gs._last_touch_save_ts = 0.0
            gs._hash_dirty_keys.clear()
            gs._touch_keys.clear()
            gs._sweep_keys = []
            gs._sweep_pos = 0
            gs._sync_retry_after = 0.0
        return True
    except Exception:
        return False


def selective_boot_reset() -> None:
    csv = PKL_BOOT_RESET_STORES
    if not csv:
        return

    rc = _raw_client()
    if rc is None:
        _warn("[pklcode] BOOT_RESET requested, but raw Redis client is None - skip")
        return

    inc, exc, has_wc = _parse_patterns(csv)
    if has_wc:
        all_names = _list_all_store_names()
        targets: Set[str] = (all_names - exc) | (inc - exc)
    else:
        targets = inc - exc

    if not targets:
        _ok("[pklcode] BOOT_RESET: no targets")
        return

    _ok(f"[pklcode] BOOT_RESET targets: {sorted(targets)}")
    total = 0
    for name in sorted(targets):
        try:
            rm = _delete_store_redis(name)
            total += rm
            ram_done = False
            if PKL_BOOT_RESET_RAM:
                ram_done = _delete_store_ram(name)
            _ok(f"[pklcode] BOOT_RESET '{name}': redis_removed={rm}, ram_cleared={int(ram_done)}")
        except Exception as e:
            _err(f"[pklcode] BOOT_RESET '{name}' error: {type(e).__name__}: {e}")
    _ok(f"[pklcode] BOOT_RESET done. total_redis_keys_removed={total}")


def _build_clients_from_env() -> Tuple[Optional["redis.Redis"], Optional["redis.Redis"]]:
    if redis is None:
        return None, None

    url = os.getenv("REDIS_URL", "").strip()
    if url:
        try:
            cli = redis.from_url(  # type: ignore
                url,
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
                health_check_interval=15,
            )
        except Exception:
            cli = None
    else:
        host = os.getenv("REDIS_HOST", "127.0.0.1")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))
        password = os.getenv("REDIS_PASSWORD") or None
        username = os.getenv("REDIS_USERNAME") or None
        use_ssl = bool(int(os.getenv("REDIS_SSL", "0")))
        try:
            cli = redis.Redis(  # type: ignore
                host=host,
                port=port,
                db=db,
                username=username,
                password=password,
                ssl=use_ssl,
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
                health_check_interval=15,
            )
        except Exception:
            cli = None

    rc = _raw_client_from(cli) if cli is not None else None
    return cli, rc


# Быстрый TCP-предчек: не блокировать импорт/health-watcher на таймаутах,
# если Redis не поднят. По умолчанию 0.35s connect refused на localhost мгновенный,
# а зависший/недоступный хост не держит старт всей системы на 12+ секунд.
PKL_REDIS_PRECHECK_TIMEOUT_SEC = float(os.getenv("PKL_REDIS_PRECHECK_TIMEOUT_SEC", "0.35"))


def _resolve_redis_endpoint() -> Tuple[str, int]:
    """Хост/порт Redis из env (тем же способом, что и _build_clients_from_env)."""
    url = os.getenv("REDIS_URL", "").strip()
    if url:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            host = parsed.hostname or "127.0.0.1"
            port = int(parsed.port or 6379)
            return host, port
        except Exception:
            return "127.0.0.1", 6379
    host = os.getenv("REDIS_HOST", "127.0.0.1")
    port = int(os.getenv("REDIS_PORT", "6379") or "6379")
    return host, port


def _redis_endpoint_reachable(timeout: float = PKL_REDIS_PRECHECK_TIMEOUT_SEC) -> bool:
    host, port = _resolve_redis_endpoint()
    try:
        with socket.create_connection((host, port), timeout=max(0.05, float(timeout))):
            return True
    except Exception:
        return False


def _try_bind_redis_from_env() -> bool:
    global _rds, _rds_raw
    if redis is None:
        return False

    # Не тратить секунды на socket_connect_timeout, если порт заведомо закрыт.
    if not _redis_endpoint_reachable():
        return False

    try:
        cli, rc = _build_clients_from_env()
        if cli is None or rc is None:
            return False
        cli.ping()
        rc.ping()
        set_redis_client(cli)
        return True
    except Exception as e:
        _warn(f"[pklcode] AUTOBIND fail: {type(e).__name__}: {e}")
        return False


def set_redis_client(client) -> None:
    global _rds, _rds_raw, _purged_once
    _rds = client

    with _raw_lock:
        _rds_raw = _raw_client_from(_rds)

    try:
        if _rds is not None:
            _rds.ping()
            kw = getattr(_rds, "connection_pool").connection_kwargs
            _ok(f"{_g(0)} [pklcode] Redis клиент установлен (PING=True) {_mask_conn_kwargs(kw)}")
    except Exception as e:
        _err(f"{_r(0)} [pklcode] Redis ping FAIL: {type(e).__name__}: {e}")

    if _rds_raw is None:
        _warn("[pklcode] raw Redis client None - payload не сможет сохраняться")

    if PKL_BOOT_RESET_STORES:
        selective_boot_reset()

    if PKL_PURGE_ON_BOOT and not _purged_once:
        purge_all_pkl_everywhere()

    for inst in list(GameStore._instances.values()):
        try:
            inst._initial_sync_if_needed()
        except Exception as e:
            _err(f"{_r(1)} [pklcode] initial_sync('{inst.name}'): {e}")

    # ✅ Флаги читаем здесь, а не при импорте: main.py импортирует pklcode на
    # строке 135, а os.environ.setdefault("PKL_...") делает на 3724 - к тому
    # моменту константы модуля уже заморожены.
    global _boot_warmup_done
    if (
        PKL_HOT_PATH_V2
        and not _boot_warmup_done
        and bool(int(os.getenv("PKL_BOOT_WARMUP", "1") or "1"))
    ):
        _boot_warmup_done = True
        try:
            budget = float(os.getenv("PKL_BOOT_WARMUP_BUDGET_SEC", "8"))
            t0 = time.monotonic()
            warmed, truncated = _boot_warmup_blocking(budget)
            _ok(
                f"{_g(3)} [pklcode] BOOT WARMUP: стораджей={warmed} "
                f"за {time.monotonic() - t0:.2f}с"
            )
            # Полный прогрев может занять десятки секунд, а держать старт бота
            # столько нельзя. Что не влезло в бюджет - догружаем фоном; до
            # первого обращения такой стор успевает прогреться.
            if truncated:
                _start_async_warmup()
        except Exception as e:
            _warn(f"[pklcode] BOOT WARMUP error: {type(e).__name__}: {e}")

    if AUTO_WARMUP and PKL_ASYNC_WARMUP:
        _start_async_warmup()
    elif AUTO_WARMUP:
        try:
            cnt = warmup_from_redis()
            _ok(f"{_g(2)} [pklcode] Warmup завершён. стораджей={cnt}")
        except Exception as e:
            _err(f"{_r(2)} [pklcode] Warmup упал: {type(e).__name__}: {e}")

    if PKL_HEALTH_WATCHER:
        _start_health_watcher()


def _iter_store_names_from_redis() -> Iterable[str]:
    rc = _raw_client()
    if rc is None:
        return []
    cursor = 0
    seen = set()

    def _yield_from(match: bytes):
        nonlocal cursor, rc, seen
        try:
            cursor = 0
            while True:
                cursor, keys = rc.scan(cursor=cursor, match=match, count=500)
                for k in keys:
                    s = k.decode("utf-8", "ignore")
                    if s.startswith("pkl:") and (
                        s.endswith(":blob") or s.endswith(":meta") or s.endswith(":data")
                    ):
                        name = s[4:-5]
                        if name and name not in seen:
                            seen.add(name)
                            yield name
                if cursor == 0:
                    break
        except Exception:
            return

    yield from _yield_from(b"pkl:*:blob")
    yield from _yield_from(b"pkl:*:meta")
    yield from _yield_from(b"pkl:*:data")


def warmup_from_redis() -> int:
    cnt = 0
    for name in _iter_store_names_from_redis():
        inst = GameStore._instances.get(name) or GameStore(name)
        try:
            inst._initial_sync_if_needed()
            cnt += 1
        except Exception:
            pass
    return cnt


_boot_warmup_done = False


def _boot_warmup_blocking(budget_sec: float) -> Tuple[int, bool]:
    """
    Прогрев всех сторов из Redis ДО начала обслуживания апдейтов.

    Без него первое обращение к стору происходит уже внутри хендлера и тянет
    полный HGETALL в event-loop (на 20k ключей это ~0.5с залипания на каждый
    стор). set_redis_client() вызывается на старте, до поллинга, поэтому здесь
    блокироваться безопасно - бот ещё никого не обслуживает.
    """
    deadline = time.monotonic() + max(0.0, float(budget_sec))
    warmed = 0
    truncated = False
    for name in _iter_store_names_from_redis():
        if time.monotonic() >= deadline:
            truncated = True
            break
        inst = GameStore._instances.get(name) or GameStore(name)
        try:
            inst._initial_sync_if_needed()
            warmed += 1
        except Exception:
            pass
    return warmed, truncated


def _async_warmup_loop():
    try:
        warmup_from_redis()
    except Exception as e:
        _err(f"[pklcode] async warmup error: {type(e).__name__}: {e}")


def _start_async_warmup():
    t = threading.Thread(target=_async_warmup_loop, name="pkl-async-warmup", daemon=True)
    t.start()


_health_thread_started = False


def _health_watcher_loop():
    while True:
        try:
            ok = _raw_ping_ok()
            if not ok:
                _try_bind_redis_from_env()

            if _raw_ping_ok():
                for s in list(getattr(GameStore, "_instances", {}).values()):
                    try:
                        if s._need_initial_sync:
                            s._initial_sync_if_needed()
                        if s._pending_retry_payload is not None or s._dirty_since_boot or s._pending_dirty or s._touch_dirty:
                            s.flush()
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(PKL_HEALTHCHECK_INTERVAL_SEC)


def _start_health_watcher():
    global _health_thread_started
    if _health_thread_started:
        return
    _health_thread_started = True
    t = threading.Thread(target=_health_watcher_loop, name="pkl-health", daemon=True)
    t.start()


# ============================ GameStore ============================
class GameStore(dict):
    _instances: Dict[str, "GameStore"] = {}

    def __new__(cls, name: str):
        if name in cls._instances:
            _ok(f"[i] GameStore '{name}' уже существует - использую существующий экземпляр")
            return cls._instances[name]
        _ok(f"[i] Создаётся новый GameStore: '{name}'")
        inst = super().__new__(cls)
        cls._instances[name] = inst
        return inst

    def __init__(self, name: str):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.name = name
        self.redis_blob_key = f"pkl:{name}:blob"
        self.redis_meta_key = f"pkl:{name}:meta"
        self.redis_chunk_key = f"pkl:{name}:chunk:"

        self.timestamps: Dict[str, float] = {}
        # Срок жизни известен сразу, до первого тика уборщика.
        self.expiry_seconds = _expiry_for(name)
        self.cleanup_interval = CLEANUP_INTERVAL_SEC
        self._expire_heap: List[Tuple[float, str]] = []

        self._need_initial_sync = True
        self._dirty_since_boot = False
        # Момент, раньше которого не повторяем первичную загрузку (Redis лежит).
        self._sync_retry_after = 0.0

        self._sync_lock = threading.RLock()
        self._lock = threading.RLock()

        self._log_i = 0
        self._ops_total = self._ops_created = self._ops_updated = self._ops_skipped = 0
        self._ops_deleted = 0
        self._snapshots = 0
        self._ops_since_save = 0
        self._pending_dirty = False
        self._last_save_ts = 0.0
        self._debounce_timer: Optional[threading.Timer] = None
        self._in_bulk = 0
        self._bulk_dirty = False

        self._pending_retry_payload: Optional[bytes] = None
        self._retry_backoff = 1.0
        self._next_retry_ts = 0.0

        self._touch_dirty = False
        self._touch_count = 0
        self._last_touch_save_ts = 0.0

        # ✅ вместо SCAN-чистки чанков: знаем сколько было чанков в прошлом снапшоте
        self._last_chunk_count = 0

        # ✅ самолечение чтения: анти-спам reload
        self._heal_reload_inflight = False
        self._heal_last_reload_ts = 0.0

        # ✅ hash-backend: точечное сохранение ключей (без полного blob)
        self._hash_dirty_keys: Set[str] = set()
        self._storage_mode = PKL_STORAGE_MODE

        # ✅ v2: touch-метки TTL пишутся батчем, а не через полное сохранение.
        # Раньше в hash-режиме touch вообще не доезжал до Redis: ключ не попадал
        # в _hash_dirty_keys, _save_now() видел пустой набор и выходил. В итоге
        # score в zset не обновлялся, и активно читаемый ключ удалялся из Redis
        # по TTL, хотя в памяти жил.
        self._touch_keys: Set[str] = set()

        # ✅ v2: пошаговое подметание TTL по timestamps вместо вечно растущей
        # _expire_heap (в hash-режиме куча вообще никогда не сливалась - ветка
        # hash в _cleanup_expired_now выходила до цикла слива).
        self._sweep_keys: List[str] = []
        self._sweep_pos = 0
        # Страховка: не подметаем стор сразу после создания, если его TTL не
        # объявлен в реестре - модуль мог ещё не выставить свой expiry_seconds.
        self._sweep_not_before = (
            0.0 if name in STORE_EXPIRY_OVERRIDES
            else time.time() + max(0.0, PKL_SWEEP_GRACE_SEC)
        )

        if PKL_HOT_PATH_V2:
            _start_writer()
            _start_sweeper()
            self._svc_thread = None
        else:
            self._svc_thread = threading.Thread(target=self._service_loop, daemon=True)
            self._svc_thread.start()

    def _is_hash_mode(self) -> bool:
        return self._storage_mode == "hash"

    def _never_expires(self) -> bool:
        """True, если стор не должен чистить ключи по TTL."""
        if self.name in EXCLUDED_STORES:
            return True
        try:
            exp = float(self.expiry_seconds)
        except Exception:
            return True
        return exp <= 0 or exp >= NEVER_EXPIRE_SEC

    def _maintain_exp_zset(self) -> bool:
        """
        Нужен ли Redis-zset со сроками жизни.

        В одно-процессном режиме локальные timestamps авторитетны, TTL считается
        в памяти, и zset - это лишний ZADD на каждую запись. Он нужен только
        когда несколько процессов делят одну БД Redis.
        """
        if self._never_expires():
            return False
        if PKL_HOT_PATH_V2 and PKL_SINGLE_PROCESS:
            return False
        return True

    @staticmethod
    def _excluded_stores() -> Set[str]:
        return set(EXCLUDED_STORES)

    def _hash_mark_dirty(self, sk: str) -> None:
        # _lock реентрантный: часть вызывающих уже держит его (bulk_load).
        # Снимок набора в писателе тоже делается под ним, иначе итерация по
        # изменяемому set падает с RuntimeError.
        with self._lock:
            self._hash_dirty_keys.add(sk)
        self._pending_dirty = True
        self._dirty_since_boot = True

    def _delete_blob_keys(self, rc) -> None:
        try:
            rc.delete(self.redis_blob_key.encode("utf-8"))
            rc.delete(self.redis_meta_key.encode("utf-8"))
            self._delete_old_chunks_fast(rc)
        except Exception:
            pass

    @staticmethod
    def _canon_key(key: Any) -> str:
        if isinstance(key, (bytes, bytearray)):
            try:
                return key.decode("utf-8")
            except Exception:
                return key.decode("latin-1", "ignore")
        return str(key)

    def _migrate_keys_to_str(self) -> None:
        moved = 0
        for k in list(super().keys()):
            if not isinstance(k, str):
                v = super().pop(k)
                sk = self._canon_key(k)
                if sk not in self:
                    super().__setitem__(sk, v)
                moved += 1
        if moved:
            _ok(f"{_g(10)} [{self.name}] Мигрировано ключей в str: {moved}")

        if self.timestamps:
            new_ts: Dict[str, float] = {}
            for k, ts in list(self.timestamps.items()):
                new_ts[self._canon_key(k)] = float(ts)
            self.timestamps = new_ts

    def _pack_tuple(self) -> Tuple[Dict[str, Any], Dict[str, float]]:
        return dict(self), self.timestamps

    def _pack_bytes(self) -> bytes:
        raw = pickle.dumps(self._pack_tuple(), protocol=pickle.HIGHEST_PROTOCOL)
        if COMPRESS_ZLIB:
            try:
                raw = zlib.compress(raw, level=max(1, min(ZLIB_LEVEL, 9)))
            except Exception:
                pass
        return raw

    def _unpack_bytes(self, data: bytes) -> Tuple[Dict[str, Any], Dict[str, float]]:
        blob = data
        if COMPRESS_ZLIB:
            try:
                blob = zlib.decompress(data)
            except Exception:
                pass
        obj = pickle.loads(blob)
        raw_data, raw_ts = obj
        return raw_data, raw_ts

    def _log_ok(self, msg: str) -> None:
        self._log_i += 1
        _ok(f"{_g(self._log_i)} [{self.name}] {msg}")

    def _log_err(self, msg: str, e: Optional[Exception] = None) -> None:
        self._log_i += 1
        _err(f"{_r(self._log_i)} [{self.name}] {msg}" + (f": {type(e).__name__}: {e}" if e else ""))

    # ✅ быстрый delete чанков без SCAN
    def _delete_old_chunks_fast(self, rc) -> None:
        if self._last_chunk_count <= 0:
            return
        try:
            pipe = rc.pipeline()
            for idx in range(self._last_chunk_count):
                pipe.delete(f"{self.redis_chunk_key}{idx:04d}".encode("utf-8"))
            pipe.delete(self.redis_meta_key.encode("utf-8"))
            pipe.execute()
        except Exception:
            pass
        finally:
            self._last_chunk_count = 0

    def _save_payload(self, payload: bytes) -> bool:
        rc = _raw_client()
        if rc is None:
            self._dirty_since_boot = True
            return False

        try:
            if len(payload) <= CHUNK_THRESHOLD_BYTES:
                pipe = rc.pipeline()
                pipe.set(self.redis_blob_key.encode("utf-8"), payload)
                pipe.delete(self.redis_meta_key.encode("utf-8"))
                pipe.execute()

                # ✅ вместо scan - удаляем известные старые чанки
                self._delete_old_chunks_fast(rc)

                self._snapshots += 1
                self._last_save_ts = time.time()
                self._last_chunk_count = 0
            else:
                # ✅ сначала удаляем старый blob + старые чанки (быстро)
                try:
                    rc.delete(self.redis_blob_key.encode("utf-8"))
                except Exception:
                    pass
                self._delete_old_chunks_fast(rc)

                chunks = [payload[i:i + CHUNK_SIZE_BYTES] for i in range(0, len(payload), CHUNK_SIZE_BYTES)]
                pipe = rc.pipeline()
                for idx, chunk in enumerate(chunks):
                    pipe.set(f"{self.redis_chunk_key}{idx:04d}".encode("utf-8"), chunk)

                meta = pickle.dumps(
                    {
                        "version": 1,
                        "chunks": len(chunks),
                        "total_bytes": len(payload),
                        "ts": time.time(),
                        "compress": int(COMPRESS_ZLIB),
                        "chunk_size": CHUNK_SIZE_BYTES,
                    },
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
                pipe.set(self.redis_meta_key.encode("utf-8"), meta)
                pipe.execute()

                self._snapshots += 1
                self._last_save_ts = time.time()
                self._last_chunk_count = len(chunks)
            return True
        except Exception as e:
            self._log_err("Ошибка при сохранении снапшота в Redis", e)
            return False

    def _load_payload(self) -> Optional[bytes]:
        rc = _raw_client()
        if rc is None:
            return None

        # meta/chunks
        try:
            meta_raw = rc.get(self.redis_meta_key.encode("utf-8"))
            if meta_raw:
                try:
                    meta = pickle.loads(meta_raw)
                    chunks = int(meta.get("chunks", 0))
                except Exception:
                    chunks = 0

                if chunks > 0:
                    keys = [f"{self.redis_chunk_key}{idx:04d}".encode("utf-8") for idx in range(chunks)]
                    parts = rc.mget(keys)  # ✅ one roundtrip
                    if not parts or any(p is None for p in parts):
                        return None
                    out = b"".join(bytes(p) for p in parts if p is not None)
                    self._last_chunk_count = chunks
                    return out
        except Exception:
            pass

        # blob
        try:
            raw_bytes = rc.get(self.redis_blob_key.encode("utf-8"))
            if raw_bytes is None:
                return None
            self._last_chunk_count = 0
            return bytes(raw_bytes)
        except Exception:
            return None

    def _initial_sync_if_needed(self) -> None:
        if not self._need_initial_sync:
            return

        # Пауза перед повторной попыткой проверяется ДО взятия _sync_lock, иначе
        # каждое чтение при лежащем Redis платило бы _wait_redis_ready (150мс).
        if self._sync_retry_after and time.time() < self._sync_retry_after:
            return

        with self._sync_lock:
            if not self._need_initial_sync:
                return
            if self._sync_retry_after and time.time() < self._sync_retry_after:
                return

            if _raw_client() is None or not _wait_redis_ready(timeout=0.15):
                # НЕ сдаёмся навсегда. Раньше здесь выставлялось
                # _need_initial_sync = False, и стор до самого перезапуска
                # отдавал пустоту, хотя данные в Redis были целы: health-watcher
                # переспрашивал только сторы с _need_initial_sync = True.
                self._dirty_since_boot = True
                self._sync_retry_after = time.time() + PKL_SYNC_RETRY_SEC
                return

            self._sync_retry_after = 0.0

            # ---------- hash mode: HGETALL вместо огромного pickle blob ----------
            if self._is_hash_mode():
                rc = _raw_client()
                if rc is None:
                    # Клиент мог отвалиться между проверкой выше и этой строкой:
                    # повторим позже, а не сдаёмся до перезапуска.
                    self._dirty_since_boot = True
                    self._sync_retry_after = time.time() + PKL_SYNC_RETRY_SEC
                    return

                def _hash_boot_load() -> bool:
                    # Записи, сделанные ДО первой удачной загрузки (например,
                    # пока Redis лежал), нельзя терять: hash_load_all делает
                    # clear() + update(), а прежний код вдобавок очищал
                    # _hash_dirty_keys - такие записи исчезали и из памяти, и из
                    # очереди на сохранение.
                    with self._lock:
                        pending = {
                            sk: dict.__getitem__(self, sk)
                            for sk in self._hash_dirty_keys
                            if dict.__contains__(self, sk)
                        }
                        pending_ts = {sk: self.timestamps.get(sk) for sk in pending}
                        pending_del = {
                            sk for sk in self._hash_dirty_keys if sk not in pending
                        }

                    if hash_backend.hash_has_data(rc, self.name):
                        ok = hash_backend.hash_load_all(self, rc)
                    elif self._dirty_since_boot and (self or self.timestamps):
                        with self._lock:
                            keys = set(self.keys())
                        return hash_backend.hash_save_keys(self, rc, keys)
                    else:
                        ok = hash_backend.hash_migrate_from_blob(
                            self,
                            rc,
                            load_blob_fn=self._load_payload,
                            unpack_blob_fn=self._unpack_bytes,
                            delete_blob_fn=self._delete_blob_keys,
                        )

                    if pending or pending_del:
                        with self._lock:
                            for sk, value in pending.items():
                                dict.__setitem__(self, sk, value)
                                ts = pending_ts.get(sk)
                                if ts is not None:
                                    self.timestamps[sk] = ts
                            for sk in pending_del:
                                if dict.__contains__(self, sk):
                                    dict.__delitem__(self, sk)
                                self.timestamps.pop(sk, None)
                            self._hash_dirty_keys |= set(pending) | pending_del
                        self._pending_dirty = True
                    return ok

                try:
                    _io_submit(self.name, _hash_boot_load, wait=True, timeout=3.0)
                except Exception as e:
                    self._log_err("hash initial_sync failed", e)

                self._need_initial_sync = False
                self._touch_dirty = False
                self._touch_count = 0
                self._last_touch_save_ts = time.time()
                if self._hash_dirty_keys:
                    self._schedule_save()
                return

            # ---------- legacy blob mode ----------
            if self._dirty_since_boot and (self or self.timestamps):
                try:
                    payload = self._pack_bytes()
                    ok = self._save_payload(payload)
                    if ok:
                        self._need_initial_sync = False
                        self._touch_dirty = False
                        self._touch_count = 0
                        self._last_touch_save_ts = time.time()
                        self._pending_retry_payload = None
                        self._retry_backoff = 1.0
                        self._dirty_since_boot = False
                        return
                    self._pending_retry_payload = payload
                    self._next_retry_ts = time.time() + self._retry_backoff
                    return
                except Exception:
                    pass

            raw_bytes = self._load_payload()
            if raw_bytes is None:
                try:
                    payload = self._pack_bytes()
                    if self._save_payload(payload):
                        self._need_initial_sync = False
                        self._touch_dirty = False
                        self._touch_count = 0
                        self._last_touch_save_ts = time.time()
                    else:
                        self._pending_retry_payload = payload
                        self._next_retry_ts = time.time() + self._retry_backoff
                except Exception:
                    pass
                return

            try:
                data_dict, ts_dict = self._unpack_bytes(raw_bytes)
                with self._lock:
                    self.clear()
                    super().update(data_dict)
                    self.timestamps = ts_dict
                    self._rebuild_expire_heap()
                    self._migrate_keys_to_str()

                self._need_initial_sync = False
                self._touch_dirty = False
                self._touch_count = 0
                self._last_touch_save_ts = time.time()
            except Exception:
                with self._lock:
                    self.clear()
                    self.timestamps = {}
                    self._expire_heap.clear()
                try:
                    payload = self._pack_bytes()
                    self._save_payload(payload)
                except Exception:
                    pass
                self._need_initial_sync = False
                self._touch_dirty = False
                self._touch_count = 0
                self._last_touch_save_ts = time.time()

    # ✅ ЛЕНИВОЕ самолечение: только если реально надо
    def _maybe_heal_read(self) -> None:
        # ✅ v2: в вызывающем потоке (это event-loop) НИКОГДА не спим и не ждём
        # Redis. Единственный допустимый Redis-I/O здесь - однократная загрузка
        # стора при первом обращении; всё остальное делают фоновые потоки.
        if PKL_HOT_PATH_V2:
            if self._need_initial_sync:
                self._initial_sync_if_needed()
            return

        # Быстрый путь: данные уже в памяти и initial_sync выполнен → отдаём без
        # обращения к Redis. Пинг делаем только если явно включён PKL_FASTPATH_PING.
        if PKL_FASTPATH_READS and (not self._need_initial_sync):
            if (not PKL_FASTPATH_PING) or _raw_ping_ok():
                return

        deadline = time.time() + PKL_HEAL_READ_TIMEOUT_SEC
        while time.time() < deadline:
            if not self._need_initial_sync and _raw_ping_ok():
                return
            if _raw_client() is None:
                _try_bind_redis_from_env()
            if _wait_redis_ready(timeout=0.12):
                self._initial_sync_if_needed()
                if not self._need_initial_sync:
                    return
            time.sleep(PKL_HEAL_RETRY_DELAY_SEC)

    def _force_reload_from_redis_once(self) -> None:
        # ✅ v2 + один процесс: память авторитетна, поэтому промах - это просто
        # промах. Прежнее поведение тянуло в event-loop полный HGETALL стора со
        # снятием pickle с каждого значения (плюс ZADD на каждую метку времени)
        # на КАЖДЫЙ промах чтения, с кулдауном всего 0.35с. Стоимость росла
        # вместе с размером стора - отсюда и "через несколько часов всё встаёт".
        if PKL_HOT_PATH_V2 and PKL_SINGLE_PROCESS:
            return
        if not PKL_HEAL_FORCE_RELOAD_ON_MISS:
            return
        if self._heal_reload_inflight:
            return
        if (time.time() - self._heal_last_reload_ts) < max(0.05, PKL_HEAL_RELOAD_COOLDOWN_SEC):
            return

        self._heal_reload_inflight = True
        try:
            self._maybe_heal_read()

            # hash mode: перезагрузка по ключам, не огромный blob
            if self._is_hash_mode():
                rc = _raw_client()
                if rc is None:
                    return

                has_unsaved_local = bool(
                    self._pending_dirty or self._dirty_since_boot or self._hash_dirty_keys
                )

                if not has_unsaved_local:
                    hash_backend.hash_load_all(self, rc)
                    self._heal_last_reload_ts = time.time()
                    return

                # Мердж: сохраняем локальные несохранённые записи
                local_data = dict(self)
                local_ts = dict(self.timestamps)
                hash_backend.hash_load_all(self, rc)

                with self._lock:
                    for k, v in local_data.items():
                        remote_k_ts = self.timestamps.get(k)
                        local_k_ts = local_ts.get(k)
                        is_new_locally = k not in self
                        is_fresher_locally = (
                            local_k_ts is not None
                            and (remote_k_ts is None or local_k_ts > remote_k_ts)
                        )
                        if is_new_locally or is_fresher_locally:
                            super().__setitem__(k, v)
                            if local_k_ts is not None:
                                self.timestamps[k] = local_k_ts

                self._heal_last_reload_ts = time.time()
                return

            raw_bytes = self._load_payload()
            if raw_bytes is None:
                return

            try:
                data_dict, ts_dict = self._unpack_bytes(raw_bytes)
            except Exception:
                return

            with self._lock:
                # Запись в Redis дебаунсится (WRITE_DEBOUNCE_MS), поэтому снапшот
                # может быть старее памяти. Раньше здесь был clear()+update(), и
                # reload по промаху затирал только что сделанные записи, которые
                # ещё не успели сохраниться.
                #
                # Мердж нужен ТОЛЬКО когда есть что защищать: несохранённые
                # записи (_pending_dirty) или данные, ни разу не доехавшие до
                # Redis (_dirty_since_boot). В остальных случаях снапшот и так
                # авторитетен, а мердж - лишние копии словарей на каждом
                # промахе, то есть тормоза на ровном месте по всем сторам.
                has_unsaved_local = bool(self._pending_dirty or self._dirty_since_boot)

                if not has_unsaved_local:
                    self.clear()
                    super().update(data_dict)
                    self.timestamps = dict(ts_dict)
                else:
                    local_data = dict(self)
                    local_ts = dict(self.timestamps)

                    self.clear()
                    super().update(data_dict)
                    self.timestamps = dict(ts_dict)

                    for k, v in local_data.items():
                        remote_k_ts = ts_dict.get(k)
                        local_k_ts = local_ts.get(k)
                        is_new_locally = k not in data_dict
                        is_fresher_locally = (
                            local_k_ts is not None
                            and (remote_k_ts is None or local_k_ts > remote_k_ts)
                        )
                        if is_new_locally or is_fresher_locally:
                            super().__setitem__(k, v)
                            if local_k_ts is not None:
                                self.timestamps[k] = local_k_ts

                self._rebuild_expire_heap()
                self._migrate_keys_to_str()

            self._heal_last_reload_ts = time.time()
        finally:
            self._heal_reload_inflight = False

    def _mark_touch_dirty(self, sk: Optional[str] = None) -> None:
        if self.name in EXCLUDED_STORES:
            return
        if TOUCH_SAVE_MS <= 0:
            return

        # ✅ v2: копим сами ключи, чтобы фоновый писатель обновил только метки
        # времени (HSET ts) одним пайплайном - без полного сохранения значений.
        if PKL_HOT_PATH_V2:
            if sk is not None and not self._never_expires():
                self._touch_keys.add(sk)
            return

        self._touch_dirty = True
        self._touch_count += 1
        if self._touch_count >= max(1, TOUCH_BATCH_MAX):
            self._touch_count = 0
            self._pending_dirty = True
            self._schedule_save()

    def _maybe_flush_touch_ts(self) -> None:
        """Батч-сохранение TTL-меток. Вызывается только из фонового сборщика."""
        if not (PKL_HOT_PATH_V2 and self._is_hash_mode()):
            return
        if TOUCH_SAVE_MS <= 0 or not self._touch_keys:
            return
        if (time.time() - self._last_touch_save_ts) * 1000.0 < TOUCH_SAVE_MS:
            return

        # Снимок под _lock: горячий путь чтения пополняет _touch_keys из
        # event-loop, а итерация по изменяемому set бросает RuntimeError.
        with self._lock:
            keys = set(self._touch_keys)
            self._touch_keys.clear()
        self._last_touch_save_ts = time.time()

        rc = _raw_client()
        if rc is None:
            with self._lock:
                self._touch_keys |= keys
            return
        try:
            hash_backend.hash_save_timestamps(self, rc, keys)
        except Exception:
            with self._lock:
                self._touch_keys |= keys

    def _schedule_save(self) -> None:
        self._pending_dirty = True

        # ✅ v2: только помечаем стор грязным и будим единый писатель. Никаких
        # threading.Timer на каждую запись и никакого Redis-I/O в этом потоке.
        if PKL_HOT_PATH_V2:
            _notify_writer(self)
            return

        if WRITE_DEBOUNCE_MS <= 0:
            self._save_now()
            return

        def _do():
            with self._sync_lock:
                if self._in_bulk > 0:
                    return
                self._save_now()

        if self._debounce_timer and self._debounce_timer.is_alive():
            self._debounce_timer.cancel()
        self._debounce_timer = threading.Timer(WRITE_DEBOUNCE_MS / 1000.0, _do)
        self._debounce_timer.daemon = True
        self._debounce_timer.start()

    def _requeue_dirty(self, keys: Set[str]) -> None:
        """Вернуть незаписанные ключи в очередь (Redis недоступен/ошибка)."""
        with self._lock:
            self._hash_dirty_keys |= keys
        self._pending_dirty = True
        self._dirty_since_boot = True

    def _save_now(self) -> None:
        if _raw_client() is None or not _wait_redis_ready(timeout=0.1):
            self._dirty_since_boot = True
            return

        # ---------- hash mode: сохраняем только изменённые ключи ----------
        if self._is_hash_mode():
            with self._lock:
                keys = set(self._hash_dirty_keys)
                self._hash_dirty_keys.clear()
            if not keys:
                self._pending_dirty = False
                return

            rc = _raw_client()
            if rc is None:
                self._requeue_dirty(keys)
                return

            def _do_save() -> bool:
                return hash_backend.hash_save_keys(self, rc, keys)

            try:
                if PKL_HOT_PATH_V2:
                    # Мы уже в фоновом потоке (pkl-writer / health / atexit),
                    # поэтому сохраняем прямо здесь: общий пул на 2 воркера был
                    # узким местом - один тяжёлый стор затыкал записи всем.
                    if not _do_save():
                        self._requeue_dirty(keys)
                        return
                else:
                    _io_submit(self.name, _do_save, wait=False)
                # fire-and-forget; flush() дождётся через _io_wait_store
                self._pending_dirty = bool(self._hash_dirty_keys)
                self._ops_since_save = 0
                self._last_save_ts = time.time()
                if not self._hash_dirty_keys:
                    self._dirty_since_boot = False
                    if not PKL_HOT_PATH_V2:
                        # В v2 TTL-метки сливаются своим таймером
                        # (_maybe_flush_touch_ts). Если сбрасывать его здесь, то
                        # при частых записях он не наступит никогда, _touch_keys
                        # будет расти, а TTL живых ключей не доедет до Redis.
                        self._touch_dirty = False
                        self._touch_count = 0
                        self._last_touch_save_ts = time.time()
            except Exception:
                self._requeue_dirty(keys)
            return

        try:
            with self._lock:
                payload = self._pack_bytes()

            ok = self._save_payload(payload)
            if ok:
                self._pending_dirty = False
                self._ops_since_save = 0
                self._pending_retry_payload = None
                self._retry_backoff = 1.0
                self._touch_dirty = False
                self._touch_count = 0
                self._last_touch_save_ts = time.time()
                self._dirty_since_boot = False
            else:
                self._pending_retry_payload = payload
                self._retry_backoff = min(self._retry_backoff * 2.0, 60.0)
                self._next_retry_ts = time.time() + self._retry_backoff
                self._dirty_since_boot = True
        except Exception:
            try:
                self._pending_retry_payload = payload  # type: ignore[name-defined]
            except Exception:
                pass
            self._retry_backoff = min(self._retry_backoff * 2.0, 60.0)
            self._next_retry_ts = time.time() + self._retry_backoff
            self._dirty_since_boot = True

    def save(self) -> None:
        self._initial_sync_if_needed()
        self._schedule_save()

    def flush(self) -> None:
        self._initial_sync_if_needed()
        with self._sync_lock:
            if self._is_hash_mode():
                _io_wait_store(self.name, timeout=10.0)
                with self._lock:
                    keys = set(self._hash_dirty_keys)
                    self._hash_dirty_keys.clear()
                rc = _raw_client()
                if rc and keys:
                    if not hash_backend.hash_save_keys(self, rc, keys):
                        self._requeue_dirty(keys)
                        return

                # ✅ TTL-метки прочитанных ключей: без этого после перезапуска
                # активно используемые ключи выглядят "старыми" и истекают.
                if rc and PKL_HOT_PATH_V2 and self._touch_keys:
                    with self._lock:
                        touched = set(self._touch_keys)
                        self._touch_keys.clear()
                    try:
                        hash_backend.hash_save_timestamps(self, rc, touched)
                    except Exception:
                        with self._lock:
                            self._touch_keys |= touched
                    self._last_touch_save_ts = time.time()
                self._pending_dirty = False
                self._ops_since_save = 0
                self._last_save_ts = time.time()
                self._dirty_since_boot = False
                return
            self._save_now()

    @contextmanager
    def bulk(self):
        self._in_bulk += 1
        try:
            yield
        finally:
            self._in_bulk -= 1
            if self._in_bulk == 0 and (self._bulk_dirty or self._pending_dirty):
                self._bulk_dirty = False
                self._schedule_save()

    def bulk_load(self, mapping: Dict[Any, Any]) -> None:
        """Быстрая пакетная загрузка: один initial_sync + один save вместо N×__setitem__."""
        if not mapping:
            return
        self._initial_sync_if_needed()
        now = time.time()
        dirty_keys: Set[str] = set()
        with self.bulk():
            with self._lock:
                for key, value in mapping.items():
                    sk = self._canon_key(key)
                    existed = dict.__contains__(self, sk)
                    dict.__setitem__(self, sk, value)
                    self.timestamps[sk] = now
                    if self._is_hash_mode():
                        dirty_keys.add(sk)
                    self._ops_total += 1
                    if existed:
                        self._ops_updated += 1
                    else:
                        self._ops_created += 1
                self._ops_since_save += len(mapping)
                self._bulk_dirty = True
                self._dirty_since_boot = True
                if self._is_hash_mode():
                    self._hash_dirty_keys |= dirty_keys
                    self._pending_dirty = True

    @contextmanager
    def edit(self, key: Any, default: Any = None):
        self._initial_sync_if_needed()
        sk = self._canon_key(key)

        with self._lock:
            base = dict.__getitem__(self, sk) if dict.__contains__(self, sk) else default
            try:
                obj = copy.deepcopy(base)
            except Exception:
                obj = base

        try:
            yield obj
        finally:
            self[sk] = obj

    def set_mut(self, key: Any, fn: Callable[[Any], Any], default: Any = None) -> Any:
        self._initial_sync_if_needed()
        sk = self._canon_key(key)
        cur = self.get(sk, default)
        try:
            out = fn(cur)
        except Exception as e:
            self._log_err("set_mut(): ошибка в fn()", e)
            return cur
        self[sk] = out
        return out

    def _check_nested_changes(self, old_dict, new_dict) -> bool:
        for k, v in new_dict.items():
            if k not in old_dict or old_dict[k] != v:
                return True
            if isinstance(v, dict) and isinstance(old_dict[k], dict):
                if self._check_nested_changes(old_dict[k], v):
                    return True
        return False

    def _check_list_changes(self, old_list, new_list) -> bool:
        if len(old_list) != len(new_list):
            return True
        for i, item in enumerate(new_list):
            if item != old_list[i]:
                return True
        return False

    def save_if_changed(self, key, value) -> bool:
        sk = self._canon_key(key)
        if not dict.__contains__(self, sk):
            return True
        old = dict.__getitem__(self, sk)

        # ✅ v2: рекурсивный обход вложенных словарей/списков на КАЖДОЙ записи -
        # это O(размера значения) CPU прямо в event-loop. Сравниваем дёшево:
        # скаляры по значению, остальное считаем изменившимся. Лишняя запись
        # ничего не стоит - ключ всё равно коалесцируется до одного HSET.
        if PKL_HOT_PATH_V2:
            if old is value:
                # Тот же объект: скорее всего его мутировали на месте (частый
                # паттерн store[k]["field"] = ... ; store[k] = store[k]).
                return True
            if type(old) is type(value) and isinstance(
                value, (int, float, bool, str, bytes, type(None))
            ):
                return old != value
            return True

        if isinstance(old, dict) and isinstance(value, dict):
            return self._check_nested_changes(old, value)
        if isinstance(old, list) and isinstance(value, list):
            return self._check_list_changes(old, value)
        return old != value

    def _deletes_forbidden(self) -> bool:
        return self.name in NO_DELETE_STORES

    def _push_expiry(self, sk: str, ts: float) -> None:
        # ✅ v2: куча больше не используется. Раньше сюда попадал КАЖДЫЙ touch на
        # чтении, а сливалась куча только в blob-ветке _cleanup_expired_now - то
        # есть в hash-режиме она росла на один элемент с каждого чтения и никогда
        # не уменьшалась. TTL теперь считается напрямую по timestamps.
        if PKL_HOT_PATH_V2:
            return
        if self.name in EXCLUDED_STORES:
            return
        heapq.heappush(self._expire_heap, (ts + self.expiry_seconds, sk))

    def _rebuild_expire_heap(self) -> None:
        self._expire_heap.clear()
        if PKL_HOT_PATH_V2:
            return
        if self.name in EXCLUDED_STORES:
            return
        for sk, ts in self.timestamps.items():
            heapq.heappush(self._expire_heap, (ts + self.expiry_seconds, sk))

    def _sweep_expired_step(self, budget: Optional[int] = None) -> int:
        """
        Пошаговое истечение по локальным timestamps.

        Просматриваем ключи порциями, чтобы не держать _lock на сторах с сотнями
        тысяч ключей. Удалённые ключи помечаются грязными - фоновый писатель
        сделает HDEL. Локальная память здесь авторитетна, поэтому активно
        читаемый ключ не может быть удалён (в отличие от старой чистки по
        Redis-zset, которая сносила живые данные, т.к. touch туда не доезжал).
        """
        if not PKL_HOT_PATH_V2:
            return 0
        if self._never_expires() or self._deletes_forbidden():
            return 0
        if self._need_initial_sync:
            return 0
        if self._sweep_not_before and time.time() < self._sweep_not_before:
            return 0

        limit = max(1, int(budget if budget is not None else PKL_SWEEP_BUDGET))
        exp = float(self.expiry_seconds)
        now = time.time()
        doomed: List[str] = []

        with self._lock:
            if self._sweep_pos >= len(self._sweep_keys):
                self._sweep_keys = list(self.timestamps.keys())
                self._sweep_pos = 0
            chunk = self._sweep_keys[self._sweep_pos:self._sweep_pos + limit]
            self._sweep_pos += limit

            for sk in chunk:
                ts = self.timestamps.get(sk)
                if ts is None:
                    continue
                if (now - ts) <= exp:
                    continue
                if dict.__contains__(self, sk):
                    dict.__delitem__(self, sk)
                self.timestamps.pop(sk, None)
                doomed.append(sk)

        if not doomed:
            return 0

        self._ops_deleted += len(doomed)
        self._dirty_since_boot = True
        for sk in doomed:
            self._touch_keys.discard(sk)
            if self._is_hash_mode():
                self._hash_mark_dirty(sk)
        if not self._is_hash_mode():
            self._pending_dirty = True
        self._schedule_save()
        return len(doomed)

    def _cleanup_expired_now(self) -> int:
        if self.name in EXCLUDED_STORES or self._deletes_forbidden():
            return 0

        # ✅ v2: истечение считается по локальным timestamps, а не по Redis-zset.
        if PKL_HOT_PATH_V2:
            return self._sweep_expired_step()

        if self._is_hash_mode():
            rc = _raw_client()
            if rc is None:
                return 0

            def _do_cleanup() -> int:
                return hash_backend.hash_cleanup_expired(self, rc)

            try:
                removed = _io_submit(self.name, _do_cleanup, wait=True, timeout=2.0)
            except Exception:
                removed = 0
            if removed:
                self._ops_deleted += removed
                self.save()
            return int(removed or 0)

        now = time.time()
        removed = 0
        with self._lock:
            while self._expire_heap and self._expire_heap[0][0] <= now:
                _, sk = heapq.heappop(self._expire_heap)
                ts = self.timestamps.get(sk)
                if ts is None:
                    continue
                if now - ts > self.expiry_seconds:
                    if dict.__contains__(self, sk):
                        dict.__delitem__(self, sk)
                        removed += 1
                    self.timestamps.pop(sk, None)
        if removed:
            self._ops_deleted += removed
            self.save()
        return removed

    def _service_loop(self):
        while True:
            try:
                if self._need_initial_sync and _raw_ping_ok():
                    self._initial_sync_if_needed()

                self._cleanup_expired_now()

                if (
                    self._pending_retry_payload is not None
                    and time.time() >= self._next_retry_ts
                    and self._in_bulk == 0
                    and _raw_ping_ok()
                ):
                    if self._save_payload(self._pending_retry_payload):
                        self._pending_retry_payload = None
                        self._retry_backoff = 1.0
                        self._pending_dirty = False
                        self._ops_since_save = 0
                        self._touch_dirty = False
                        self._touch_count = 0
                        self._last_touch_save_ts = time.time()
                        self._dirty_since_boot = False
                    else:
                        self._retry_backoff = min(self._retry_backoff * 2.0, 60.0)
                        self._next_retry_ts = time.time() + self._retry_backoff

                if (
                    self._touch_dirty
                    and TOUCH_SAVE_MS > 0
                    and self._in_bulk == 0
                    and self._pending_retry_payload is None
                ):
                    if (time.time() - self._last_touch_save_ts) * 1000.0 >= TOUCH_SAVE_MS:
                        self._schedule_save()

                need_force = False
                if FORCE_SAVE_MS > 0 and (time.time() - self._last_save_ts) * 1000.0 >= FORCE_SAVE_MS:
                    if self._pending_dirty:
                        need_force = True
                if SAVE_OPS_THRESHOLD > 0 and self._ops_since_save >= SAVE_OPS_THRESHOLD:
                    need_force = True

                if need_force and self._in_bulk == 0 and self._pending_retry_payload is None:
                    with self._sync_lock:
                        self._save_now()
            except Exception:
                pass
            time.sleep(self.cleanup_interval)

    # ---------- dict API ----------
    def __contains__(self, key: Any) -> bool:
        self._maybe_heal_read()

        sk = self._canon_key(key)
        with self._lock:
            if dict.__contains__(self, sk):
                return True

        # miss -> один быстрый reload и повтор
        self._force_reload_from_redis_once()
        with self._lock:
            if dict.__contains__(self, sk):
                return True

        try:
            if isinstance(key, str) and key.isdigit():
                k2 = str(int(key))
                with self._lock:
                    return dict.__contains__(self, k2)
            if isinstance(key, int):
                k2 = str(key)
                with self._lock:
                    return dict.__contains__(self, k2)
        except Exception:
            pass
        return False

    def __getitem__(self, key: Any) -> Any:
        self._maybe_heal_read()
        sk = self._canon_key(key)

        def _touch(k: str) -> None:
            if TOUCH_ON_GET and self.name not in EXCLUDED_STORES:
                now = time.time()
                self.timestamps[k] = now
                self._push_expiry(k, now)
                self._mark_touch_dirty(k)

        with self._lock:
            if dict.__contains__(self, sk):
                _touch(sk)
                return dict.__getitem__(self, sk)

            if isinstance(key, str) and key.isdigit():
                sk2 = str(int(key))
                if dict.__contains__(self, sk2):
                    _touch(sk2)
                    return dict.__getitem__(self, sk2)

            if isinstance(key, int):
                sk2 = str(key)
                if dict.__contains__(self, sk2):
                    _touch(sk2)
                    return dict.__getitem__(self, sk2)

        self._force_reload_from_redis_once()

        with self._lock:
            if dict.__contains__(self, sk):
                _touch(sk)
                return dict.__getitem__(self, sk)
            try:
                if isinstance(key, str) and key.isdigit():
                    sk2 = str(int(key))
                    if dict.__contains__(self, sk2):
                        _touch(sk2)
                        return dict.__getitem__(self, sk2)
                if isinstance(key, int):
                    sk2 = str(key)
                    if dict.__contains__(self, sk2):
                        _touch(sk2)
                        return dict.__getitem__(self, sk2)
            except Exception:
                pass

        raise KeyError(key)

    def get(self, key: Any, default=None) -> Any:
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def __setitem__(self, key: Any, value: Any) -> None:
        self._initial_sync_if_needed()
        sk = self._canon_key(key)
        changed = False
        with self._lock:
            existed = dict.__contains__(self, sk)
            if self.save_if_changed(sk, value):
                dict.__setitem__(self, sk, value)
                now = time.time()
                self.timestamps[sk] = now
                self._push_expiry(sk, now)
                self._ops_total += 1
                self._ops_since_save += 1
                if existed:
                    self._ops_updated += 1
                else:
                    self._ops_created += 1
                changed = True
            else:
                self._ops_total += 1
                self._ops_since_save += 1
                self._ops_skipped += 1
        if changed:
            self._dirty_since_boot = True
            if self._is_hash_mode():
                self._hash_mark_dirty(sk)
            if self._in_bulk > 0:
                self._bulk_dirty = True
            else:
                self.save()

    def __delitem__(self, key: Any) -> None:
        self._initial_sync_if_needed()
        if self._deletes_forbidden():
            return
        sk = self._canon_key(key)
        # Удалить могли по нормализованному ключу (sk2). Раньше и метка времени,
        # и пометка "грязного" ключа брались всё равно от sk: метка оставалась
        # висеть навсегда, а в Redis уходил HDEL не того поля - данные удалённого
        # ключа оставались в хранилище.
        deleted_key: Optional[str] = None
        with self._lock:
            if dict.__contains__(self, sk):
                dict.__delitem__(self, sk)
                deleted_key = sk
            else:
                try:
                    sk2 = None
                    if isinstance(key, str) and key.isdigit():
                        sk2 = str(int(key))
                    elif isinstance(key, int):
                        sk2 = str(key)
                    if sk2 is not None and dict.__contains__(self, sk2):
                        dict.__delitem__(self, sk2)
                        deleted_key = sk2
                except Exception:
                    pass

            if deleted_key is not None:
                self.timestamps.pop(deleted_key, None)
                self._touch_keys.discard(deleted_key)
                self._ops_deleted += 1
                self._ops_total += 1
                self._ops_since_save += 1
        deleted = deleted_key is not None
        if deleted:
            self._dirty_since_boot = True
            if self._is_hash_mode():
                self._hash_mark_dirty(deleted_key)
            if self._in_bulk > 0:
                self._bulk_dirty = True
            else:
                self.save()


# ========================== LazyGameStore ==========================
class LazyGameStore:
    _loaded_instances: Dict[str, GameStore] = {}

    def __init__(self, name: str):
        self.name = name
        self._store: Optional[GameStore] = None

    def _load(self) -> GameStore:
        if self._store is None:
            if self.name in LazyGameStore._loaded_instances:
                self._store = LazyGameStore._loaded_instances[self.name]
            else:
                self._store = GameStore(self.name)
                LazyGameStore._loaded_instances[self.name] = self._store
        return self._store

    def __getattr__(self, attr):
        return getattr(self._load(), attr)

    def __getitem__(self, key):
        return self._load()[key]

    def __setitem__(self, k, v):
        self._load()[k] = v

    def __delitem__(self, k):
        del self._load()[k]

    def __contains__(self, k):
        return k in self._load()

    def __len__(self):
        return len(self._load())

    def __iter__(self):
        return iter(self._load())


# ========================== Self-test ==========================
def redis_roundtrip_selftest() -> bool:
    rc = _raw_client()
    if rc is None:
        _err("🔥 [pklcode] SELFTEST: raw redis client is None")
        return False

    key = f"pkl:selftest:{int(time.time())}".encode("utf-8")
    payload = b"\x00PKLTEST\xff" + os.urandom(16)

    try:
        rc.set(key, payload, ex=30)
        got = rc.get(key)
        rc.delete(key)
        return got == payload
    except Exception as e:
        _err(f"🔥 [pklcode] SELFTEST EXC: {type(e).__name__}: {e}")
        return False


def verify_store_persisted(
    name: str,
    *,
    scan_count: int = 500,
    max_scan_steps: int = 24,
    max_scan_seconds: float = 1.5,
) -> Dict[str, Any]:
    rc = _raw_client()
    if rc is None:
        return {"store": name, "ok": False, "error": "raw redis client is None"}

    if PKL_STORAGE_MODE == "hash":
        return hash_backend.hash_verify_persisted(rc, name)

    out: Dict[str, Any] = {
        "store": name,
        "ok": False,
        "blob": 0,
        "meta": 0,
        "chunks": 0,
        "scan_steps": 0,
        "scan_truncated": False,
    }
    if rc is None:
        out["error"] = "raw redis client is None"
        return out

    try:
        blob = rc.get(f"pkl:{name}:blob".encode("utf-8"))
        meta = rc.get(f"pkl:{name}:meta".encode("utf-8"))
        out["blob"] = 0 if blob is None else len(blob)
        out["meta"] = 0 if meta is None else len(meta)

        cursor = 0
        chunks = 0
        steps = 0
        truncated = False
        pattern = f"pkl:{name}:chunk:*".encode("utf-8")
        deadline = time.monotonic() + max(0.05, float(max_scan_seconds))

        while True:
            cursor, keys = rc.scan(cursor=cursor, match=pattern, count=max(1, int(scan_count)))
            chunks += len(keys)
            steps += 1
            if cursor == 0:
                break
            if steps >= max(1, int(max_scan_steps)):
                truncated = True
                break
            if time.monotonic() >= deadline:
                truncated = True
                break

        out["scan_steps"] = steps
        out["scan_truncated"] = truncated
        out["chunks"] = chunks
        out["ok"] = (out["blob"] > 0) or (out["meta"] > 0 and (out["chunks"] > 0 or truncated))
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out


# ========================== Завершение/сигналы ==========================
def _flush_all_stores_on_exit():
    try:
        for s in list(getattr(GameStore, "_instances", {}).values()):
            try:
                s.flush()
            except Exception:
                pass
    except Exception:
        pass


def _print_summary():
    if not PRINT_SUMMARY:
        return
    stores = getattr(GameStore, "_instances", {}) or {}
    total = len(stores)
    snapshots = sum(s._snapshots for s in stores.values())
    created = sum(s._ops_created for s in stores.values())
    updated = sum(s._ops_updated for s in stores.values())
    skipped = sum(s._ops_skipped for s in stores.values())
    deleted = sum(s._ops_deleted for s in stores.values())

    line = "-" * 56
    _safe_console(f"\n{line}\n[pklcode] session summary")
    _safe_console(
        f"stores: {total} | snapshots: {snapshots} | "
        f"created: {created} | updated: {updated} | skipped: {skipped} | deleted: {deleted}"
    )
    _safe_console(f"{line}\n")


def _on_terminate(*_):
    try:
        _flush_all_stores_on_exit()
    finally:
        os._exit(0)


def _setup_signal_handlers_once() -> None:
    try:
        if threading.current_thread() is not threading.main_thread():
            return
        signal.signal(signal.SIGTERM, _on_terminate)
        signal.signal(signal.SIGINT, _on_terminate)
    except Exception:
        pass


atexit.register(_flush_all_stores_on_exit)
atexit.register(_print_summary)


try:
    _setup_signal_handlers_once()

    if _client() is None or _raw_client() is None:
        _try_bind_redis_from_env()

    if PKL_HEALTH_WATCHER:
        _start_health_watcher()

    if AUTO_WARMUP and PKL_ASYNC_WARMUP:
        _start_async_warmup()

except Exception as _e:
    _warn(f"[pklcode] bootstrap error: {type(_e).__name__}: {_e}")
