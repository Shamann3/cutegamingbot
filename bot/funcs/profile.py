import asyncio
import copy
import html
import random
import re
import time
import traceback

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, List

from aiogram import types
from aiogram.enums import ChatType
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from main import *
from bot.handlers.handlers_btns import *

# =========================================================
# GLOBAL STATE
# =========================================================
user_message_mappingprofile: Dict[int, int] = LazyGameStore("user_message_mappingprofile")
stop_who_are_you_flags: Dict[int, bool] = LazyGameStore("stop_who_are_you_flags")

# message_id -> meta профиля
PROFILE_MESSAGE_META: Dict[int, Dict[str, Any]] = LazyGameStore("PROFILE_MESSAGE_META")

# cooldown / inflight / locks
PROFILE_REFRESH_COOLDOWN_SECONDS = 60
PROFILE_REFRESH_LAST_TS: Dict[Tuple[int, int], float] = LazyGameStore("PROFILE_REFRESH_LAST_TS")
PROFILE_INFLIGHT_REFRESH: Dict[Tuple[int, int], bool] = LazyGameStore("PROFILE_INFLIGHT_REFRESH")
PROFILE_USER_LOCKS: Dict[int, asyncio.Lock] = LazyGameStore("PROFILE_USER_LOCKS")

# TG profile cache
user_tg_profile_cache: Dict[int, Dict[str, Any]] = LazyGameStore("user_tg_profile_cache")

# pending db updates
PROFILE_PENDING_DB_UPDATES: Dict[int, Dict[str, Any]] = LazyGameStore("PROFILE_PENDING_DB_UPDATES")
PROFILE_PENDING_DB_LOCK = asyncio.Lock()

PROFILE_TG_TIMEOUT = 3.0
PROFILE_DB_TIMEOUT = 3.0
PROFILE_EDIT_TIMEOUT = 4.0
PROFILE_RETRIES = 2
PROFILE_RETRY_BASE_DELAY = 0.20

PROFILE_DEBUG = False
PROFILE_DEBUG_LEVEL = 1

PROFILE_REFRESH_BUTTON_TEXT = "Обновить данные"
PROFILE_REFRESH_BUTTON_EMOJI_ID = "5318781800221273738"
PROFILE_REFRESH_BUTTON_STYLE = "default"

PROFILE_WARNS_BUTTON_TEXT = "Варны"
PROFILE_BACK_TO_PROFILE_TEXT = "Назад к профилю"


# =========================================================
# LOG HELPERS
# =========================================================
def _who_dbg(text: str):
    print(f"[WHO] {text}")


def _who_info_dbg(text: str):
    print(f"[WHO_INFO] {text}")


def _p_ts() -> str:
    try:
        return datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        return "??.??.???? ??:??:??"


def _p_dbg(tag: str, msg: str, level: int = 1, uid: Optional[int] = None):
    try:
        if not PROFILE_DEBUG:
            return
        if int(PROFILE_DEBUG_LEVEL) < int(level):
            return
        prefix = f"[{_p_ts()}][PROFILE][{tag}]"
        if uid is not None:
            prefix += f"[uid={uid}]"
        print(f"{prefix} {msg}")
    except Exception:
        pass


def _p_err(tag: str, msg: str, e: Exception, uid: Optional[int] = None, level: int = 1):
    try:
        _p_dbg(tag, f"❌ {msg} | {type(e).__name__}: {e}", level=level, uid=uid)
        if PROFILE_DEBUG and PROFILE_DEBUG_LEVEL >= 3:
            _p_dbg(tag, f"TRACEBACK:\n{traceback.format_exc()}", level=3, uid=uid)
    except Exception:
        pass


# =========================================================
# BASIC HELPERS
# =========================================================
def _normalize_spaces(text: str) -> str:
    return " ".join((text or "").strip().split())


def _profile_safe_str(value: Any, default: str = "") -> str:
    try:
        if value is None:
            return default
        return str(value)
    except Exception:
        return default


def _profile_safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _profile_name_link(user_id: int, first_name: str, username: Optional[str] = None) -> str:
    if username:
        return (
            f"<a href='https://t.me/{html.escape(username)}'>"
            f"{html.escape(first_name or '')}</a>"
        )
    if first_name:
        return html.escape(first_name)
    return f"<a href='tg://user?id={user_id}'>Неизвестный</a>"


def _profile_fmt_int(value: Any) -> str:
    try:
        return "{:,.0f}".format(int(value or 0)).replace(",", ".")
    except Exception:
        return "0"


def _profile_escape(value: Any) -> str:
    return html.escape(_profile_safe_str(value))


def _profile_clean_name(value: Optional[str]) -> str:
    s = _profile_safe_str(value, "").strip()
    s = re.sub(r'[<>/{}"]', "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _profile_build_full_name(first_name: Optional[str], last_name: Optional[str]) -> str:
    fn = _profile_clean_name(first_name)
    ln = _profile_clean_name(last_name)
    full = f"{fn} {ln}".strip()
    return full or "Неизвестный"


def _profile_now_ts() -> float:
    return time.monotonic()


def _profile_refresh_cb(viewer_id: int, target_user_id: int) -> str:
    return f"whoref:{int(viewer_id)}:{int(target_user_id)}"


def _profile_is_transient_error(e: Exception) -> bool:
    t = (str(e) or "").lower()
    return any(
        x in t for x in [
            "timeout", "timed out", "try again", "temporar", "connection",
            "reset", "server closed", "pool", "network", "retry", "429",
            "flood", "too many requests"
        ]
    )


async def _profile_call(coro_factory, *, timeout: float, tries: int = PROFILE_RETRIES, uid: Optional[int] = None):
    last = None
    for attempt in range(1, tries + 1):
        try:
            return await asyncio.wait_for(coro_factory(), timeout=timeout)
        except Exception as e:
            last = e
            if attempt >= tries or not _profile_is_transient_error(e):
                raise
            delay = PROFILE_RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.random() * 0.07
            _p_dbg("RETRY", f"attempt={attempt}/{tries} sleep={delay:.2f}s", level=2, uid=uid)
            await asyncio.sleep(delay)
    raise last


async def _profile_get_user_lock(user_id: int) -> asyncio.Lock:
    lock = PROFILE_USER_LOCKS.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        PROFILE_USER_LOCKS[user_id] = lock
    return lock

# =========================================================
# EXTRA BUTTON HELPERS FOR PROFILE REFRESH
# =========================================================

PROFILE_REFRESH_EXTRA_NONE = "-"
PROFILE_REFRESH_EXTRA_CLOSE_BONUS = "9close_bonus"


def _profile_make_refresh_cb(viewer_id: int, target_user_id: int, extra_button_cb: Optional[str] = None) -> str:
    """
    Формат:
      whoref:<viewer_id>:<target_user_id>:<extra_button_cb_or_->

    Примеры:
      whoref:123:123:-
      whoref:123:123:9close_bonus
    """
    extra = str(extra_button_cb or PROFILE_REFRESH_EXTRA_NONE).strip()
    return f"whoref:{int(viewer_id)}:{int(target_user_id)}:{extra}"


def _profile_parse_refresh_cb(data: str) -> Tuple[Optional[int], Optional[int], str]:
    """
    Возвращает:
      viewer_id, target_user_id, extra_button_cb

    Если extra не передан, вернёт PROFILE_REFRESH_EXTRA_NONE.
    """
    try:
        raw = str(data or "")
        parts = raw.split(":")

        # старый формат: whoref:viewer:target
        if len(parts) == 3 and parts[0] == "whoref":
            return int(parts[1]), int(parts[2]), PROFILE_REFRESH_EXTRA_NONE

        # новый формат: whoref:viewer:target:extra
        if len(parts) >= 4 and parts[0] == "whoref":
            viewer_id = int(parts[1])
            target_user_id = int(parts[2])
            extra_button_cb = ":".join(parts[3:]).strip() or PROFILE_REFRESH_EXTRA_NONE
            return viewer_id, target_user_id, extra_button_cb

    except Exception:
        pass

    return None, None, PROFILE_REFRESH_EXTRA_NONE


def _profile_make_warns_cb(viewer_id: int, target_user_id: int) -> str:
    return f"profwarn:{int(viewer_id)}:{int(target_user_id)}"


def _profile_make_back_cb(viewer_id: int, target_user_id: int) -> str:
    return f"profback:{int(viewer_id)}:{int(target_user_id)}"


def _profile_parse_viewer_target_cb(data: str, prefix: str) -> Tuple[Optional[int], Optional[int]]:
    try:
        parts = str(data or "").split(":")
        if len(parts) == 3 and parts[0] == prefix:
            return int(parts[1]), int(parts[2])
    except Exception:
        pass
    return None, None


def _profile_can_access_warns(
    clicker_id: int,
    viewer_id: int,
    target_user_id: int,
    profile_mode: str,
) -> bool:
    clicker_id = int(clicker_id)
    viewer_id = int(viewer_id)
    target_user_id = int(target_user_id)

    if clicker_id == viewer_id:
        return True
    if profile_mode != "own_profile" and clicker_id == target_user_id:
        return True
    return False


async def _profile_target_has_warns(user_id: int) -> bool:
    try:
        from bot.admins.warn import count_active_warns_for_user
        return await count_active_warns_for_user(int(user_id)) > 0
    except Exception as e:
        _p_err("WARNS", "count_active_warns_for_user failed", e, uid=int(user_id), level=2)
        return False


async def _profile_build_warns_text(
    *,
    chat_id: int,
    chat_type: str,
    target_user_id: int,
    viewer_id: int,
) -> str:
    from bot.admins.warn import _warn_overview_text, _resolve_user_display

    self_view = int(viewer_id) == int(target_user_id)
    target_name, target_username = await _resolve_user_display(int(target_user_id))

    return await _warn_overview_text(
        chat_id=int(chat_id),
        chat_type=str(chat_type or "supergroup"),
        target_id=int(target_user_id),
        self_view=self_view,
        target_name=target_name,
        target_username=target_username,
    )


def _profile_store_message_meta(
    message_id: int,
    *,
    viewer_id: int,
    target_user_id: int,
    mode: str,
    chat_id: int,
    has_warns: bool = False,
) -> None:
    try:
        PROFILE_MESSAGE_META[int(message_id)] = {
            "viewer_id": int(viewer_id),
            "target_user_id": int(target_user_id),
            "mode": str(mode),
            "chat_id": int(chat_id),
            "has_warns": bool(has_warns),
        }
    except Exception:
        pass


def _profile_get_message_meta(message_id: int) -> Dict[str, Any]:
    try:
        meta = PROFILE_MESSAGE_META.get(int(message_id))
        if isinstance(meta, dict):
            return meta
    except Exception:
        pass
    return {}


def _profile_validate_callback_meta(
    callback_query: types.CallbackQuery,
    viewer_id: int,
    target_user_id: int,
) -> Tuple[bool, Dict[str, Any]]:
    msg_meta = _profile_get_message_meta(callback_query.message.message_id)
    if not msg_meta:
        return True, msg_meta

    try:
        meta_viewer_id = int(msg_meta.get("viewer_id", 0))
        meta_target_id = int(msg_meta.get("target_user_id", 0))
    except Exception:
        return False, msg_meta

    if meta_viewer_id != int(viewer_id) or meta_target_id != int(target_user_id):
        return False, msg_meta

    return True, msg_meta


def _profile_build_extra_button(extra_button_cb: Optional[str]) -> Optional[InlineKeyboardButton]:
    extra_button_cb = str(extra_button_cb or PROFILE_REFRESH_EXTRA_NONE).strip()

    if extra_button_cb in ("", PROFILE_REFRESH_EXTRA_NONE):
        return None

    # здесь можно добавлять разные варианты доп-кнопок
    if extra_button_cb == "9close_bonus":
        return InlineKeyboardButton(
            text=" ",
            callback_data="9close_bonus",
            style="default",
            icon_custom_emoji_id="5226660202035554522"
        )

    # универсальный fallback: если передали неизвестный callback,
    # всё равно вернём кнопку-заглушку с этим callback
    return InlineKeyboardButton(
        text=" ",
        callback_data=extra_button_cb,
        style="default",
        icon_custom_emoji_id="5226660202035554522"
    )
def _profile_check_cooldown(viewer_id: int, target_user_id: int) -> Tuple[bool, int]:
    key = (int(viewer_id), int(target_user_id))
    now_ts = _profile_now_ts()
    last_ts = PROFILE_REFRESH_LAST_TS.get(key, 0.0)
    remain = PROFILE_REFRESH_COOLDOWN_SECONDS - (now_ts - last_ts)
    if remain > 0:
        return False, max(1, int(remain))
    return True, 0


def _profile_touch_cooldown(viewer_id: int, target_user_id: int) -> None:
    PROFILE_REFRESH_LAST_TS[(int(viewer_id), int(target_user_id))] = _profile_now_ts()


def format_timedelta(delta: timedelta) -> str:
    years = delta.days // 365
    months = (delta.days % 365) // 30
    days = delta.days % 30
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []

    if years > 0:
        parts.append(f"{years} {'год' if years == 1 else 'года' if 2 <= years <= 4 else 'лет'}")
    if months > 0:
        parts.append(f"{months} {'месяц' if months == 1 else 'месяца' if 2 <= months <= 4 else 'месяцев'}")
    if days > 0:
        parts.append(f"{days} {'день' if days == 1 else 'дня' if 2 <= days <= 4 else 'дней'}")
    if hours > 0 and years == 0:
        parts.append(f"{hours} {'час' if hours == 1 else 'часа' if 2 <= hours <= 4 else 'часов'}")
    if minutes > 0 and years == 0 and months == 0:
        parts.append(f"{minutes} {'минута' if minutes == 1 else 'минуты' if 2 <= minutes <= 4 else 'минут'}")
    if seconds > 0 and delta.total_seconds() < 60:
        parts.append(f"{seconds} {'секунда' if seconds == 1 else 'секунды' if 2 <= seconds <= 4 else 'секунд'}")

    if not parts:
        return "меньше секунды"

    return ", ".join(parts)


def _profile_parse_registration_date(date_value: Any) -> Tuple[Optional[datetime], str]:
    if isinstance(date_value, datetime):
        dt = date_value
        return dt, dt.strftime("%d.%m.%Y в %H:%M")

    if isinstance(date_value, str):
        for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(date_value, fmt)
                return dt, dt.strftime("%d.%м.%Y в %H:%M")
            except Exception:
                pass
        try:
            dt = datetime.fromisoformat(date_value)
            return dt, dt.strftime("%d.%m.%Y в %H:%M")
        except Exception:
            pass

    return None, "Невозможно распознать дату"


def _profile_elapsed_text(registration_date: Optional[datetime]) -> str:
    if not registration_date:
        return "время не определено"
    return format_timedelta(datetime.now() - registration_date)


# =========================================================
# TEXT PARSE HELPERS
# =========================================================
def _extract_trigger_and_arg(text: str):
    text = _normalize_spaces(text)
    lower_text = text.lower()

    triggers = ("кто ты", "ктоты")

    for tr in triggers:
        if lower_text == tr:
            return tr, ""

        if lower_text.startswith(tr + " "):
            return tr, text[len(tr):].strip()

    return None, ""


def _extract_username_from_link(text: str) -> Optional[str]:
    if not text:
        return None

    raw = text.strip()

    patterns = [
        r"^(?:https?://)?t\.me/([A-Za-z0-9_]{1,64})(?:\?.*)?$",
        r"^(?:https?://)?telegram\.me/([A-Za-z0-9_]{1,64})(?:\?.*)?$",
    ]

    for pattern in patterns:
        m = re.match(pattern, raw, flags=re.IGNORECASE)
        if m:
            return m.group(1)

    return None


def _clean_username_candidate(text: str) -> str:
    if not text:
        return ""

    s = text.strip()
    if s.startswith("@"):
        s = s[1:]

    s = s.strip()
    s = s.split("/")[0]
    s = s.split("?")[0]
    s = s.split("#")[0]
    s = s.strip(" ,.;:!\"'`()[]{}<>")

    return s


def _looks_like_username(text: str) -> bool:
    if not text or len(text) < 3:
        return False
    return re.fullmatch(r"[A-Za-z0-9_]{3,64}", text) is not None


# =========================================================
# CACHE INVALIDATION / FORCE REFRESH
# =========================================================
def _profile_invalidate_runtime_caches_for_user(user_id: int) -> None:
    uid = int(user_id)

    # известные кэши проекта
    cache_names = [
        "user_cache",
        "user_cache_balance",
        "user_tg_profile_cache",
        "user_cache_profile",
        "profile_cache",
    ]

    for cache_name in cache_names:
        try:
            obj = globals().get(cache_name)
            if isinstance(obj, dict):
                obj.pop(uid, None)
        except Exception as e:
            _p_err("CACHE", f"invalidate {cache_name} failed", e, uid=uid, level=2)


def _profile_collect_render_runtime_snapshot(message_obj) -> Tuple[str, str]:
    current_text = _profile_safe_str(getattr(message_obj, "text", None), "")
    current_caption = _profile_safe_str(getattr(message_obj, "caption", None), "")
    current_visible_text = current_text or current_caption
    current_markup_repr = repr(getattr(message_obj, "reply_markup", None))
    return current_visible_text, current_markup_repr


# =========================================================
# TG SNAPSHOT FOR TARGET USER
# =========================================================
async def _profile_get_live_tg_snapshot_for_target(bot1, target_user_id: int) -> Dict[str, Any]:
    user_id = int(target_user_id)

    bio = None
    bio_loaded = False
    first_name_tg = ""
    last_name_tg = ""
    username = ""
    language_code = ""
    is_premium = False
    is_bot = False
    chat_title = ""
    chat_type = ""

    try:
        chat_data = await _profile_call(lambda: bot1.get_chat(user_id), timeout=PROFILE_TG_TIMEOUT, uid=user_id)

        first_name_tg = _profile_safe_str(getattr(chat_data, "first_name", None), "").strip()
        last_name_tg = _profile_safe_str(getattr(chat_data, "last_name", None), "").strip()
        username = _profile_safe_str(getattr(chat_data, "username", None), "").strip()
        language_code = _profile_safe_str(getattr(chat_data, "language_code", None), "").strip()
        is_premium = bool(getattr(chat_data, "is_premium", False))
        is_bot = bool(getattr(chat_data, "is_bot", False))
        chat_title = _profile_safe_str(getattr(chat_data, "title", None), "")
        chat_type = _profile_safe_str(getattr(chat_data, "type", None), "")
        bio = _profile_safe_str(getattr(chat_data, "bio", None), "").strip()
        bio_loaded = True
    except Exception as e:
        _p_err("TG", "get_chat(target) failed", e, uid=user_id, level=2)

    full_name = _profile_build_full_name(first_name_tg, last_name_tg)

    snapshot = {
        "user_id": user_id,
        "first_name_tg": first_name_tg,
        "last_name_tg": last_name_tg,
        "full_name_for_db": full_name,
        "username": username,
        "bio": bio if bio_loaded else None,
        "bio_loaded": bio_loaded,
        "language_code": language_code,
        "is_premium": is_premium,
        "is_bot": is_bot,
        "chat_title": chat_title,
        "chat_type": chat_type,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    return snapshot


# =========================================================
# DB / CACHE SYNC CORE
# =========================================================
async def _profile_db_get_core_row(db, user_id: int) -> Dict[str, Any]:
    try:
        rows = await _profile_call(
            lambda: db.fetch_all(
                "SELECT user_id, first_name, username, bio, data FROM users WHERE user_id = $1",
                params=[user_id]
            ),
            timeout=PROFILE_DB_TIMEOUT,
            uid=user_id
        )
        row = rows[0] if rows else None
        if not row:
            return {}

        if hasattr(row, "get"):
            return {
                "user_id": row.get("user_id"),
                "first_name": row.get("first_name") or "",
                "username": row.get("username") or "",
                "bio": row.get("bio") or "",
                "data": row.get("data"),
            }

        return {
            "user_id": row["user_id"],
            "first_name": row["first_name"] or "",
            "username": row["username"] or "",
            "bio": row["bio"] or "",
            "data": row["data"],
        }
    except Exception as e:
        _p_err("DB", "_profile_db_get_core_row failed", e, uid=user_id, level=2)
        return {}


def _profile_compare_and_collect_updates(
    tg_snapshot: Dict[str, Any],
    db_row: Dict[str, Any],
    cache_row: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str], bool]:
    db_updates: Dict[str, Any] = {}
    cache_updates: Dict[str, Any] = {}
    changed_keys: List[str] = []

    tg_full_name = _profile_safe_str(tg_snapshot.get("full_name_for_db"), "").strip()
    tg_username = _profile_safe_str(tg_snapshot.get("username"), "").strip()

    db_first_name = _profile_safe_str(db_row.get("first_name"), "").strip()
    db_username = _profile_safe_str(db_row.get("username"), "").strip()
    db_bio = _profile_safe_str(db_row.get("bio"), "").strip()

    cache_first_name = _profile_safe_str(cache_row.get("first_name"), "").strip()
    cache_username = _profile_safe_str(cache_row.get("username"), "").strip()
    cache_bio = _profile_safe_str(cache_row.get("bio"), "").strip()

    if tg_full_name and tg_full_name != db_first_name:
        db_updates["first_name"] = tg_full_name
        if "Имя" not in changed_keys:
            changed_keys.append("Имя")

    if tg_full_name and tg_full_name != cache_first_name:
        cache_updates["first_name"] = tg_full_name
        if "Имя" not in changed_keys:
            changed_keys.append("Имя")

    if tg_username != db_username:
        db_updates["username"] = tg_username
        if "Username" not in changed_keys:
            changed_keys.append("Username")

    if tg_username != cache_username:
        cache_updates["username"] = tg_username
        if "Username" not in changed_keys:
            changed_keys.append("Username")

    if tg_snapshot.get("bio_loaded"):
        tg_bio = _profile_safe_str(tg_snapshot.get("bio"), "").strip()

        if tg_bio != db_bio:
            db_updates["bio"] = tg_bio
            if "Bio" not in changed_keys:
                changed_keys.append("Bio")

        if tg_bio != cache_bio:
            cache_updates["bio"] = tg_bio
            if "Bio" not in changed_keys:
                changed_keys.append("Bio")

    equal_everywhere = not db_updates and not cache_updates
    return db_updates, cache_updates, changed_keys, equal_everywhere


async def _profile_enqueue_pending_db_update(user_id: int, fields: Dict[str, Any]):
    try:
        async with PROFILE_PENDING_DB_LOCK:
            cur = PROFILE_PENDING_DB_UPDATES.get(user_id) or {}
            cur.update(fields)
            PROFILE_PENDING_DB_UPDATES[user_id] = cur
            _p_dbg("PENDING", f"enqueue fields={list(fields.keys())}", level=2, uid=user_id)
    except Exception as e:
        _p_err("PENDING", "enqueue failed", e, uid=user_id, level=2)


async def profile_pending_db_flusher(db, interval: float = 2.5):
    while True:
        await asyncio.sleep(interval)

        try:
            async with PROFILE_PENDING_DB_LOCK:
                items = list(PROFILE_PENDING_DB_UPDATES.items())
        except Exception:
            continue

        if not items:
            continue

        for uid, fields in items:
            try:
                await _profile_call(lambda: db.user_update_fields(int(uid), dict(fields)), timeout=PROFILE_DB_TIMEOUT, uid=int(uid))
                async with PROFILE_PENDING_DB_LOCK:
                    PROFILE_PENDING_DB_UPDATES.pop(uid, None)
                _p_dbg("PENDING", f"flush OK fields={list(fields.keys())}", level=1, uid=int(uid))
            except Exception as e:
                _p_err("PENDING", "flush failed", e, uid=int(uid), level=2)


async def _profile_sync_target_user_live_tg_to_db_and_cache(
    bot1,
    target_user_id: int,
    db,
    *,
    user_cache: Dict[int, Dict[str, Any]]
) -> Dict[str, Any]:
    user_id = int(target_user_id)
    lock = await _profile_get_user_lock(user_id)

    async with lock:
        _p_dbg("SYNC", "▶ target sync start", level=1, uid=user_id)

        tg_snapshot = await _profile_get_live_tg_snapshot_for_target(bot1, user_id)
        db_row = await _profile_db_get_core_row(db, user_id)

        cache_row = user_cache.get(user_id, {})
        if not isinstance(cache_row, dict):
            cache_row = {}

        db_updates, cache_updates, changed_keys, equal_everywhere = _profile_compare_and_collect_updates(
            tg_snapshot=tg_snapshot,
            db_row=db_row,
            cache_row=cache_row
        )

        db_updated = False
        cache_updated = False
        db_deferred = False

        if db_updates:
            try:
                await _profile_call(lambda: db.user_update_fields(user_id, dict(db_updates)), timeout=PROFILE_DB_TIMEOUT, uid=user_id)
                db_updated = True
                _p_dbg("SYNC-DB", f"updated={db_updates}", level=1, uid=user_id)
            except Exception as e:
                _p_err("SYNC-DB", "db update failed -> pending", e, uid=user_id, level=1)
                db_deferred = True
                await _profile_enqueue_pending_db_update(user_id, dict(db_updates))

        try:
            if user_id not in user_cache or not isinstance(user_cache.get(user_id), dict):
                user_cache[user_id] = {}

            if cache_updates:
                current_reg_date = user_cache[user_id].get("reg_date")
                user_cache[user_id].update(cache_updates)

                if current_reg_date is not None and "reg_date" not in user_cache[user_id]:
                    user_cache[user_id]["reg_date"] = current_reg_date

                cache_updated = True
                _p_dbg("SYNC-CACHE", f"updated={cache_updates}", level=1, uid=user_id)
        except Exception as e:
            _p_err("SYNC-CACHE", "cache update failed", e, uid=user_id, level=1)

        try:
            prev = user_tg_profile_cache.get(user_id, {})
            user_tg_profile_cache[user_id] = {
                **prev,
                "user_id": user_id,
                "first_name_tg": tg_snapshot.get("first_name_tg", ""),
                "last_name_tg": tg_snapshot.get("last_name_tg", ""),
                "full_name_for_db": tg_snapshot.get("full_name_for_db", ""),
                "username": tg_snapshot.get("username", ""),
                "bio": tg_snapshot.get("bio") if tg_snapshot.get("bio_loaded") else prev.get("bio", ""),
                "bio_loaded": bool(tg_snapshot.get("bio_loaded")),
                "language_code": tg_snapshot.get("language_code", ""),
                "is_premium": bool(tg_snapshot.get("is_premium", False)),
                "is_bot": bool(tg_snapshot.get("is_bot", False)),
                "chat_title": tg_snapshot.get("chat_title", ""),
                "chat_type": tg_snapshot.get("chat_type", ""),
                "updated_at": tg_snapshot.get("updated_at"),
                "last_refresh_unix": int(time.time()),
            }
        except Exception as e:
            _p_err("SYNC-TG-CACHE", "extended tg cache update failed", e, uid=user_id, level=2)

        result = {
            "ok": True,
            "user_id": user_id,
            "equal_everywhere": equal_everywhere,
            "db_updated": db_updated,
            "cache_updated": cache_updated,
            "db_deferred": db_deferred,
            "db_updates": db_updates,
            "cache_updates": cache_updates,
            "changed_keys": changed_keys,
            "tg_snapshot": tg_snapshot,
        }

        _p_dbg("SYNC", f"finish result={result}", level=2, uid=user_id)
        return result

# =========================================================
# SEARCH HELPERS
# =========================================================
async def _try_find_user_id_by_username(db, username_candidate: str):
    username_candidate = _clean_username_candidate(username_candidate)

    if not username_candidate:
        _who_dbg("Пустой username_candidate после очистки")
        return None

    try:
        _who_dbg(f"Пробуем искать по username: {username_candidate!r}")
        found_id = await db.get_user_id_by_username(username_candidate)

        if found_id:
            _who_dbg(f"По username найден user_id: {found_id}")
            return found_id

        _who_dbg(f"По username ничего не найдено: {username_candidate!r}")
        return None

    except Exception as e:
        _who_dbg(f"Ошибка поиска по username {username_candidate!r}: {e}")
        return None


async def _try_find_users_by_first_name(db, first_name_text: str):
    first_name_text = (first_name_text or "").strip()

    if not first_name_text:
        return {}

    try:
        _who_dbg(f"Пробуем искать по имени: {first_name_text!r}")
        users_dict = await db.get_user_id_by_first_name(first_name_text)

        if users_dict is None:
            _who_dbg("db.get_user_id_by_first_name вернул None")
            return {}

        if not isinstance(users_dict, dict):
            _who_dbg(f"Ожидался dict, получено: {type(users_dict).__name__}")
            return {}

        _who_dbg(f"По имени найдено пользователей: {len(users_dict)}")
        return users_dict

    except Exception as e:
        _who_dbg(f"Ошибка поиска по имени {first_name_text!r}: {e}")
        return {}


async def _send_multiple_found_users(message: Message, db, users_dict: dict):
    if not users_dict:
        await message.reply("<b>😔 Не удалось найти пользователя</b>", parse_mode="HTML")
        return

    if len(users_dict) == 1:
        target_group_id = list(users_dict.keys())[0]
        _who_dbg(f"Найден ровно один пользователь: {target_group_id}")
        await get_user_information_in_who_are_you(message, db, target_group_id)
        return

    if message.chat.type == "private":
        MAX_MESSAGES = 2
        caller_id = message.from_user.id
        stop_who_are_you_flags[caller_id] = False

        await message.answer(
            "🌸 <b>Нашёл несколько пользователей с таким именем.\n"
            "Начинаю отправку информации... Напишите <code>стоп кто ты</code>, чтобы остановить.</b>",
            parse_mode="HTML"
        )

        count = 0
        for uid in users_dict.keys():
            if stop_who_are_you_flags.get(caller_id):
                await message.answer(
                    "🛑 <b>Выдача информации остановлена по вашему запросу!</b>",
                    parse_mode="HTML"
                )
                break

            if caller_id != 6801702632 and count >= MAX_MESSAGES:
                break

            await get_user_information_in_who_are_you(message, db, uid)
            count += 1
            await asyncio.sleep(1)

        await message.answer("🌿 <b>Это всё</b>", parse_mode="HTML")
        return

    inline_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="☁️ Перейти в личные сообщения ☁️",
                    url="https://t.me/CuteGamingBot"
                )
            ]
        ]
    )
    await message.reply(
        f'<b>💛 Найдено несколько пользователей. Напишите сообщение "<code>{message.text}</code>" в ЛС боту.</b>',
        reply_markup=inline_keyboard,
        parse_mode="HTML"
    )


# =========================================================
# PROFILE STATE / RENDER HELPERS
# =========================================================
async def _profile_collect_state_for_render(
    *,
    user_id: int,
    viewer_id: int,
    db,
    chat_id: int
) -> Dict[str, Any]:
    bundle = await db.fetch_profile_render_bundle(user_id)
    if bundle:
        country_text = country_dict.get(bundle.get("country_emoji", ""), "Неизвестная страна")
        return {
            **bundle,
            "viewer_id": int(viewer_id),
            "chat_id": int(chat_id),
            "country_text": country_text,
        }

    async def _safe_db_call(fn, default=None, tag: str = "PROFILE-STATE"):
        try:
            return await fn()
        except Exception as e:
            _p_err(tag, "safe db call failed", e, uid=user_id, level=2)
            return default

    first_name = await _safe_db_call(lambda: db.get_firstname_by_user_id(user_id), "", "PROFILE-STATE")
    username = await _safe_db_call(lambda: db.get_username_by_id(user_id), "", "PROFILE-STATE")

    id_emoji = await _safe_db_call(lambda: db.check_user_id_in_idemo(user_id), "🆔", "EMOJI")
    username_emoji = await _safe_db_call(lambda: db.check_user_id_in_usernameemo(user_id), "👤", "EMOJI")
    name_emoji = await _safe_db_call(lambda: db.check_user_id_in_nameemo(user_id), "🎩", "EMOJI")
    balance_emoji = await _safe_db_call(lambda: db.check_user_id_in_balanceemo(user_id), "💰", "EMOJI")
    winamount_emoji = await _safe_db_call(lambda: db.check_user_id_in_winamountemo(user_id), "🏆", "EMOJI")
    marry_emoji = await _safe_db_call(lambda: db.check_user_id_in_marryemo(user_id), "💍", "EMOJI")
    rep_emoji = await _safe_db_call(lambda: db.check_user_id_in_repemo(user_id), "⭐️", "EMOJI")
    limit_emoji = await _safe_db_call(lambda: db.check_user_id_in_limitemo(user_id), "📦", "EMOJI")
    ref_emoji = await _safe_db_call(lambda: db.check_user_id_in_refemo(user_id), "🎁", "EMOJI")
    prlg_emoji = await _safe_db_call(lambda: db.check_user_id_in_prgl(user_id), "🔗", "EMOJI")
    data_emoji = await _safe_db_call(lambda: db.check_user_id_in_dataemo(user_id), "📅", "EMOJI")

    balance = await _safe_db_call(lambda: db.get_user_balance(user_id), 0, "PROFILE-STATE")
    total_games_played = await _safe_db_call(lambda: db.get_total_games_played(user_id), [], "PROFILE-STATE")
    try:
        total_games_played = sum(total_games_played) if total_games_played else 0
    except Exception:
        total_games_played = 0

    date = await _safe_db_call(lambda: db.get_registration_date(user_id), None, "PROFILE-STATE")
    referrals = await _safe_db_call(lambda: db.get_referrals(user_id), 0, "PROFILE-STATE") or 0
    xpp = await _safe_db_call(lambda: db.get_user_experience(user_id), 0, "PROFILE-STATE") or 0

    country_emoji = await _safe_db_call(lambda: db.get_country_emoji_by_user_id(user_id), "", "PROFILE-STATE")
    country_text = country_dict.get(country_emoji, "Неизвестная страна")

    first_name_ref = await _safe_db_call(lambda: db.find_referer_name(user_id), None, "PROFILE-STATE")
    give_limite = await _safe_db_call(lambda: db.get_user_give_limit(user_id), 0, "PROFILE-STATE")
    reputation_plus1 = await _safe_db_call(lambda: db.get_rep_plus(user_id), 0, "PROFILE-STATE")
    reputation_minus1 = await _safe_db_call(lambda: db.get_rep_minus(user_id), 0, "PROFILE-STATE")
    wins = await _safe_db_call(lambda: db.get_user_wins(user_id), 0, "PROFILE-STATE")
    loose = await _safe_db_call(lambda: db.get_user_loose(user_id), 0, "PROFILE-STATE")
    winamount = await _safe_db_call(lambda: db.get_user_winamount(user_id), 0, "PROFILE-STATE")
    donated = await _safe_db_call(lambda: db.get_user_donate(user_id), 0, "PROFILE-STATE")
    canwithdrawalunt = await _safe_db_call(lambda: db.get_canwithdrawal(user_id), 0, "PROFILE-STATE")
    is_banned = await _safe_db_call(lambda: db.is_user_banned(user_id), False, "PROFILE-STATE")

    return {
        "user_id": int(user_id),
        "viewer_id": int(viewer_id),
        "chat_id": int(chat_id),
        "first_name": _profile_safe_str(first_name, ""),
        "username": _profile_safe_str(username, ""),
        "id_emoji": _profile_safe_str(id_emoji, "🆔"),
        "username_emoji": _profile_safe_str(username_emoji, "👤"),
        "name_emoji": _profile_safe_str(name_emoji, "🎩"),
        "balance_emoji": _profile_safe_str(balance_emoji, "💰"),
        "winamount_emoji": _profile_safe_str(winamount_emoji, "🏆"),
        "marry_emoji": _profile_safe_str(marry_emoji, "💍"),
        "rep_emoji": _profile_safe_str(rep_emoji, "⭐️"),
        "limit_emoji": _profile_safe_str(limit_emoji, "📦"),
        "ref_emoji": _profile_safe_str(ref_emoji, "🎁"),
        "prlg_emoji": _profile_safe_str(prlg_emoji, "🔗"),
        "data_emoji": _profile_safe_str(data_emoji, "📅"),
        "balance": _profile_safe_int(balance, 0),
        "total_games_played": _profile_safe_int(total_games_played, 0),
        "date": date,
        "referrals": _profile_safe_int(referrals, 0),
        "xpp": _profile_safe_int(xpp, 0),
        "country_emoji": _profile_safe_str(country_emoji, ""),
        "country_text": _profile_safe_str(country_text, "Неизвестная страна"),
        "referer_name": first_name_ref,
        "give_limite": _profile_safe_int(give_limite, 0),
        "reputation_plus1": _profile_safe_int(reputation_plus1, 0),
        "reputation_minus1": _profile_safe_int(reputation_minus1, 0),
        "wins": _profile_safe_int(wins, 0),
        "loose": _profile_safe_int(loose, 0),
        "winamount": _profile_safe_int(winamount, 0),
        "donated": _profile_safe_int(donated, 0),
        "canwithdrawalunt": _profile_safe_int(canwithdrawalunt, 0),
        "is_banned": bool(is_banned),
    }


async def _build_profile_caption_for_target(
    *,
    viewer_id: int,
    target_user_id: int,
    db,
    chat_id: int
) -> str:
    state = await _profile_collect_state_for_render(
        user_id=int(target_user_id),
        viewer_id=int(viewer_id),
        db=db,
        chat_id=int(chat_id)
    )

    user_id = state["user_id"]
    first_name = state["first_name"]
    username = state["username"]

    try:
        button_creators[f"promo{viewer_id}"] = user_id
        button_creators[f"ref{viewer_id}"] = user_id
    except Exception:
        pass

    formatted_balance = _profile_fmt_int(state["balance"])
    username1 = username or "..."

    registration_date, formatted_registration_date = _profile_parse_registration_date(state["date"])
    elapsed_time = _profile_elapsed_text(registration_date)

    referrals_text = "Рефералов"
    referrals_line = (
        f"{state['ref_emoji']} <b>{referrals_text} : {_profile_fmt_int(state['referrals'])}</b>"
        if state["referrals"] > 0 else ""
    )

    username_line = (
        f"{state['username_emoji']} <code>@{_profile_escape(username1)}</code>"
        if username1 and str(username1).strip() != "..." else ""
    )

    nationality_line = (
        f"<code>{_profile_escape(state['country_emoji'])}</code> "
        f"<b>Повешан {_profile_escape(state['country_text'])}</b> "
        f"<code>{_profile_escape(state['country_emoji'])}</code>\n"
        if state["country_emoji"] else ""
    )

    try:
        name_link = _profile_name_link(user_id, first_name, username)
    except Exception as e:
        _p_err("PROFILE", "create_user_link failed", e, uid=user_id, level=2)
        name_link = f"<a href='tg://user?id={user_id}'>{_profile_escape(first_name or 'Неизвестный')}</a>"

    invite_message = (
        f"{state['prlg_emoji']} <b>Приглашен(-а) : {_profile_escape(state['referer_name'])}</b>"
        if state["referer_name"] is not None else ""
    )

    rep_line = ""
    if state["reputation_plus1"] > 0 or state["reputation_minus1"] > 0:
        rep_line = (
            f"<b><tg-emoji emoji-id='5422604985265303975'>➕</tg-emoji> {_profile_fmt_int(state['reputation_plus1'])} | "
            f"<tg-emoji emoji-id='5303369181230542608'>➖</tg-emoji> {_profile_fmt_int(state['reputation_minus1'])}</b>"
        )

    wins_line = ""
    if state["wins"] > 0 or state["loose"] > 0:
        wins_line = (
            f"<b><tg-emoji emoji-id='5318892863780579996'>🏆</tg-emoji> Wins : {_profile_fmt_int(state['wins'])} | "
            f"<tg-emoji emoji-id='5253883839356365934'>🔥</tg-emoji> losses : {_profile_fmt_int(state['loose'])}</b>"
        )

    winamount_line = ""
    if state["winamount"] > 0:
        winamount_line = f"<b>{state['winamount_emoji']} Выиграно : {_profile_fmt_int(state['winamount'])} кут</b>"

    donated_line = ""
    if state["donated"] > 0:
        donated_line = (
            f"<b><tg-emoji emoji-id='5192944906330481531'>🏄</tg-emoji> "
            f"Задоначено : {_profile_fmt_int(state['donated'])} кут</b>"
        )

    canwithdrawal_line = ""
    if state["canwithdrawalunt"] > 0:
        canwithdrawal_line = (
            f"<b><tg-emoji emoji-id='5256145216947118159'>⌚️</tg-emoji> "
            f"Лимит выводов : {_profile_fmt_int(state['canwithdrawalunt'])} кут</b>"
        )

    banned_line = ""
    if state["is_banned"]:
        banned_line = (
            "<b><tg-emoji emoji-id='5249268768147792417'>🚫</tg-emoji> "
            "ПОЛЬЗОВАТЕЛЬ ЗАБЛОКИРОВАН "
            "<tg-emoji emoji-id='5249268768147792417'>🚫</tg-emoji>\n</b>"
        )

    statistic_lines = {"title": ""}

    caption_parts = [
        banned_line,
        nationality_line,
        f"{state['name_emoji']} <b>{name_link}</b>",
        username_line,
        f"{state['id_emoji']} <code>{user_id}</code>\n",
        f"{state['balance_emoji']} <b>{formatted_balance} кут</b>\n",
        donated_line,
        winamount_line,
        wins_line,
        f"{state['limit_emoji']} <b>Переводы до ~ {_profile_fmt_int(state['give_limite'])} кут</b>",
        canwithdrawal_line,
        referrals_line,
        rep_line,
        invite_message,
        *statistic_lines.values(),
        (
            f"<blockquote><tg-emoji emoji-id='5255937074242020424'>⛵️</tg-emoji> "
            f"{formatted_registration_date}\n"
            f"<tg-emoji emoji-id='5249056721317420453'>🔥</tg-emoji> "
            f"{elapsed_time}</blockquote>"
        ),
    ]

    return "\n".join(filter(None, caption_parts))
# =========================================================
# FULL PROFILE REFRESH
# =========================================================
async def _profile_full_refresh_and_render(
    *,
    viewer_id: int,
    target_user_id: int,
    db,
    bot1,
    chat_id: int,
    message_obj,
    extra_button_cb: Optional[str] = None,
    mode: str = "who_are_you",
) -> Dict[str, Any]:
    user_id = int(target_user_id)

    # Снимок того, что реально показано сейчас
    before_visible_text, before_markup_repr = _profile_collect_render_runtime_snapshot(message_obj)

    # Сбрасываем runtime-кэши пользователя, чтобы получить свежие значения
    _profile_invalidate_runtime_caches_for_user(user_id)
    try:
        db.invalidate_profile_bundle_cache(user_id)
    except Exception:
        pass

    # TG sync
    tg_sync_result = await _profile_sync_target_user_live_tg_to_db_and_cache(
        bot1=bot1,
        target_user_id=user_id,
        db=db,
        user_cache=user_cache
    )

    # Ещё раз сбрасываем кэши после sync, чтобы рендер точно собрал свежие данные
    _profile_invalidate_runtime_caches_for_user(user_id)

    # Строим новый профиль полностью заново
    new_caption = await _build_profile_caption_for_target(
        viewer_id=viewer_id,
        target_user_id=user_id,
        db=db,
        chat_id=chat_id
    )
    has_warns = await _profile_target_has_warns(user_id)
    new_markup = _profile_build_who_markup(
        viewer_id=viewer_id,
        target_user_id=user_id,
        extra_button_cb=extra_button_cb,
        has_warns=has_warns,
    )

    after_visible_text = new_caption
    after_markup_repr = repr(new_markup)

    text_changed = before_visible_text != after_visible_text
    markup_changed = before_markup_repr != after_markup_repr

    changed_keys = list(tg_sync_result.get("changed_keys") or [])

    # если текст профиля реально изменился, но tg_changed_keys пустой,
    # это значит, что изменились именно профильные данные из БД
    if text_changed and not changed_keys:
        changed_keys.append("Данные профиля")

    # Обновляем мету сообщения
    _profile_store_message_meta(
        message_obj.message_id,
        viewer_id=viewer_id,
        target_user_id=user_id,
        mode=mode,
        chat_id=chat_id,
        has_warns=has_warns,
    )

    return {
        "ok": True,
        "user_id": user_id,
        "new_caption": new_caption,
        "new_markup": new_markup,
        "text_changed": text_changed,
        "markup_changed": markup_changed,
        "equal_everywhere": not text_changed and not markup_changed,
        "db_deferred": bool(tg_sync_result.get("db_deferred")),
        "changed_keys": changed_keys,
        "tg_sync_result": tg_sync_result,
    }


# =========================================================
# MARKUP HELPERS
# =========================================================
def _make_refresh_button(callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=PROFILE_REFRESH_BUTTON_TEXT,
        callback_data=callback_data,
        style=PROFILE_REFRESH_BUTTON_STYLE,
        icon_custom_emoji_id=PROFILE_REFRESH_BUTTON_EMOJI_ID
    )


def _profile_clone_markup(markup: Optional[InlineKeyboardMarkup]) -> InlineKeyboardMarkup:
    try:
        if markup is None:
            return InlineKeyboardMarkup(inline_keyboard=[])
        return copy.deepcopy(markup)
    except Exception:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[])
            if getattr(markup, "inline_keyboard", None):
                for row in markup.inline_keyboard:
                    kb.inline_keyboard.append(list(row))
            return kb
        except Exception:
            return InlineKeyboardMarkup(inline_keyboard=[])


def _profile_build_who_markup(
    viewer_id: int,
    target_user_id: int,
    extra_button_cb: Optional[str] = None,
    has_warns: bool = False,
) -> InlineKeyboardMarkup:
    refresh_cb = _profile_make_refresh_cb(
        viewer_id=viewer_id,
        target_user_id=target_user_id,
        extra_button_cb=extra_button_cb
    )

    refresh_button = InlineKeyboardButton(
        text="Обновить данные",
        callback_data=refresh_cb,
        style="default",
        icon_custom_emoji_id="5318781800221273738"
    )

    inline_keyboard: List[List[InlineKeyboardButton]] = []

    if has_warns:
        inline_keyboard.append([
            InlineKeyboardButton(
                text=PROFILE_WARNS_BUTTON_TEXT,
                callback_data=_profile_make_warns_cb(viewer_id, target_user_id),
                style="danger", icon_custom_emoji_id="5389099803655305880",
            )
        ])

    inline_keyboard.append([refresh_button])

    extra_button = _profile_build_extra_button(extra_button_cb)
    if extra_button is not None:
        inline_keyboard.append([extra_button])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def _profile_build_warns_view_markup(viewer_id: int, target_user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=PROFILE_BACK_TO_PROFILE_TEXT,
            callback_data=_profile_make_back_cb(viewer_id, target_user_id),
            style="default",
        )
    ]])


def _profile_build_own_profile_markup(
    base_markup: Optional[InlineKeyboardMarkup],
    viewer_id: int,
    extra_button_cb: Optional[str] = None,
    has_warns: bool = False,
) -> InlineKeyboardMarkup:
    kb = _profile_clone_markup(base_markup)

    if not getattr(kb, "inline_keyboard", None):
        kb.inline_keyboard = []

    refresh_cb = _profile_make_refresh_cb(
        viewer_id=viewer_id,
        target_user_id=viewer_id,
        extra_button_cb=extra_button_cb
    )

    already_has_refresh = False
    for row in kb.inline_keyboard:
        for btn in row:
            if getattr(btn, "callback_data", None) == refresh_cb:
                already_has_refresh = True
                break
        if already_has_refresh:
            break

    if not already_has_refresh:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="Обновить данные",
                callback_data=refresh_cb,
                style="default",
                icon_custom_emoji_id="5318781800221273738"
            )
        ])

    if has_warns:
        warns_cb = _profile_make_warns_cb(viewer_id, viewer_id)
        already_has_warns = False
        for row in kb.inline_keyboard:
            for btn in row:
                if getattr(btn, "callback_data", None) == warns_cb:
                    already_has_warns = True
                    break
            if already_has_warns:
                break

        if not already_has_warns:
            kb.inline_keyboard.insert(-1 if kb.inline_keyboard else 0, [
                InlineKeyboardButton(
                    text=PROFILE_WARNS_BUTTON_TEXT,
                    callback_data=warns_cb,
                    style="danger", icon_custom_emoji_id="5389099803655305880",
                )
            ])

    extra_button = _profile_build_extra_button(extra_button_cb)
    if extra_button is not None:
        exists_extra = False
        for row in kb.inline_keyboard:
            for btn in row:
                if getattr(btn, "callback_data", None) == getattr(extra_button, "callback_data", None):
                    exists_extra = True
                    break
            if exists_extra:
                break

        if not exists_extra:
            kb.inline_keyboard.append([extra_button])

    return kb


# =========================================================
# SAFE EDIT
# =========================================================
def _profile_is_not_modified_error(e: Exception) -> bool:
    try:
        return "message is not modified" in str(e).lower()
    except Exception:
        return False


def _profile_is_no_caption_error(e: Exception) -> bool:
    try:
        return "there is no caption in the message to edit" in str(e).lower()
    except Exception:
        return False


async def _profile_safe_edit_message(
    message_obj,
    *,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup],
    parse_mode: str = "HTML"
) -> str:
    try:
        await _profile_call(
            lambda: message_obj.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            ),
            timeout=PROFILE_EDIT_TIMEOUT
        )
        return "edit_text"

    except Exception as e:
        if _profile_is_not_modified_error(e):
            _p_dbg("EDIT", "edit_text -> not_modified", level=2)
            return "not_modified"
        _p_err("EDIT", "edit_text failed", e, level=2)

    try:
        await _profile_call(
            lambda: message_obj.edit_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            ),
            timeout=PROFILE_EDIT_TIMEOUT
        )
        return "edit_caption"

    except Exception as e:
        if _profile_is_not_modified_error(e):
            _p_dbg("EDIT", "edit_caption -> not_modified", level=2)
            return "not_modified"
        if _profile_is_no_caption_error(e):
            _p_dbg("EDIT", "edit_caption skipped: there is no caption in the message", level=2)
        else:
            _p_err("EDIT", "edit_caption failed", e, level=2)

    try:
        await _profile_call(
            lambda: message_obj.edit_reply_markup(reply_markup=reply_markup),
            timeout=PROFILE_EDIT_TIMEOUT
        )
        return "edit_reply_markup"

    except Exception as e:
        if _profile_is_not_modified_error(e):
            _p_dbg("EDIT", "edit_reply_markup -> not_modified", level=2)
            return "not_modified"
        _p_err("EDIT", "edit_reply_markup failed", e, level=2)

    return "failed"


# =========================================================
# UNIVERSAL PROFILE UPDATE (NEW)
# =========================================================

async def _profile_safe_edit_message_by_ids(
    bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup],
    parse_mode: str = "HTML"
) -> str:
    """
    Безопасно редактирует сообщение по chat_id и message_id.
    Возвращает 'edit_text', 'edit_caption', 'edit_reply_markup' или 'failed'.
    """
    try:
        await _profile_call(
            lambda: bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            ),
            timeout=PROFILE_EDIT_TIMEOUT
        )
        return "edit_text"
    except Exception as e:
        if _profile_is_not_modified_error(e):
            _p_dbg("EDIT_IDS", "edit_text -> not_modified", level=2)
            return "not_modified"
        _p_dbg("EDIT_IDS", f"edit_text failed: {e}", level=2)

    try:
        await _profile_call(
            lambda: bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            ),
            timeout=PROFILE_EDIT_TIMEOUT
        )
        return "edit_caption"
    except Exception as e:
        if _profile_is_not_modified_error(e):
            _p_dbg("EDIT_IDS", "edit_caption -> not_modified", level=2)
            return "not_modified"
        if _profile_is_no_caption_error(e):
            _p_dbg("EDIT_IDS", "edit_caption skipped: no caption", level=2)
        else:
            _p_dbg("EDIT_IDS", f"edit_caption failed: {e}", level=2)

    try:
        await _profile_call(
            lambda: bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup
            ),
            timeout=PROFILE_EDIT_TIMEOUT
        )
        return "edit_reply_markup"
    except Exception as e:
        if _profile_is_not_modified_error(e):
            _p_dbg("EDIT_IDS", "edit_reply_markup -> not_modified", level=2)
            return "not_modified"
        _p_dbg("EDIT_IDS", f"edit_reply_markup failed: {e}", level=2)

    return "failed"


async def refresh_all_profile_messages_for_user(
    user_id: int,
    bot,
    db,
    *,
    extra_button_cb: Optional[str] = None,
) -> None:
    """
    Инвалидирует кэши пользователя и обновляет ВСЕ сообщения,
    в которых отображается профиль этого пользователя.
    Полезно вызывать после изменения данных профиля (флаг, имя, баланс и т.п.).
    """
    uid = int(user_id)

    # 1. Инвалидируем все кэши
    _profile_invalidate_runtime_caches_for_user(uid)
    try:
        db.invalidate_profile_bundle_cache(uid)
    except Exception:
        pass

    # 2. Собираем все сообщения, где target_user_id == uid
    to_update = []
    for msg_id, meta in list(PROFILE_MESSAGE_META.items()):
        if meta.get("target_user_id") == uid:
            to_update.append((msg_id, meta))

    if not to_update:
        _p_dbg("REFRESH_ALL", f"no messages found for user {uid}", level=2, uid=uid)
        return

    _p_dbg("REFRESH_ALL", f"found {len(to_update)} messages for user {uid}", level=1, uid=uid)

    # 3. Для каждого сообщения перестраиваем профиль и обновляем
    for msg_id, meta in to_update:
        try:
            chat_id = meta.get("chat_id")
            viewer_id = meta.get("viewer_id", uid)
            mode = meta.get("mode", "who_are_you")

            if not chat_id:
                continue

            caption = await _build_profile_caption_for_target(
                viewer_id=viewer_id,
                target_user_id=uid,
                db=db,
                chat_id=chat_id
            )

            has_warns = await _profile_target_has_warns(uid)

            if mode == "own_profile":
                reply_markup = _profile_build_own_profile_markup(
                    privates,
                    viewer_id=viewer_id,
                    extra_button_cb=extra_button_cb,
                    has_warns=has_warns,
                )
            else:
                reply_markup = _profile_build_who_markup(
                    viewer_id=viewer_id,
                    target_user_id=uid,
                    extra_button_cb=extra_button_cb,
                    has_warns=has_warns,
                )

            result = await _profile_safe_edit_message_by_ids(
                bot=bot,
                chat_id=chat_id,
                message_id=msg_id,
                text=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

            if result != "failed":
                # Обновляем мету (сохраняем актуальный статус варнов)
                _profile_store_message_meta(
                    msg_id,
                    viewer_id=viewer_id,
                    target_user_id=uid,
                    mode=mode,
                    chat_id=chat_id,
                    has_warns=has_warns,
                )
                _p_dbg("REFRESH_ALL", f"updated message {msg_id} (result={result})", level=2, uid=uid)
            else:
                _p_dbg("REFRESH_ALL", f"failed to update message {msg_id}", level=2, uid=uid)

        except Exception as e:
            _p_err("REFRESH_ALL", f"error updating message {msg_id}", e, uid=uid, level=2)


async def update_profile_after_data_change(
    user_id: int,
    bot,
    db,
    *,
    extra_button_cb: Optional[str] = None,
) -> None:
    """
    Публичная функция для вызова после любого изменения данных профиля.
    Например, после установки флага, смены имени, баланса и т.д.
    """
    await refresh_all_profile_messages_for_user(user_id, bot, db, extra_button_cb=extra_button_cb)


# =========================================================
# MAIN SEARCH LOGIC
# =========================================================
def _resolve_reply_target_user_id(message: Message) -> Optional[int]:
    """Определяет user_id из сообщения, на которое ответили."""
    reply = message.reply_to_message
    if reply is None:
        return None

    reply_user = reply.from_user
    if reply_user is not None and not bool(getattr(reply_user, "is_bot", False)):
        return int(reply_user.id)

    meta = _profile_get_message_meta(reply.message_id)
    target_user_id = meta.get("target_user_id")
    if target_user_id:
        try:
            return int(target_user_id)
        except Exception:
            pass

    if reply_user is not None and bool(getattr(reply_user, "is_bot", False)):
        caption = _profile_safe_str(getattr(reply, "text", None) or getattr(reply, "caption", None), "")
        id_match = re.search(r"<code>(\d{5,})</code>", caption)
        if id_match:
            try:
                return int(id_match.group(1))
            except Exception:
                pass

    return None


async def get_user_who_are_you(message: Message, db):
    text = _normalize_spaces(message.text or "")
    lower_text = text.lower().strip()

    # Остановка цепочки выдачи "стоп кто ты"
    if lower_text == "стоп кто ты":
        stop_who_are_you_flags[message.from_user.id] = True
        await message.reply("🛑 <b>Остановка выдачи информации!</b>", parse_mode="HTML")
        return

    trigger_used, arg_text = _extract_trigger_and_arg(text)
    if not trigger_used:
        return

    _who_dbg(f"Триггер: {trigger_used!r}")
    _who_dbg(f"Аргумент: {arg_text!r}")

    # Ответ на сообщение без аргумента → профиль автора того сообщения
    if not arg_text:
        reply_target_id = _resolve_reply_target_user_id(message)
        if reply_target_id is not None:
            _who_dbg(f"Ответ на сообщение: ID пользователя - {reply_target_id}")
            await get_user_information_in_who_are_you(message, db, reply_target_id)
            return

        target_group_id = message.from_user.id
        _who_dbg(f"Аргумент пустой, показываем автора: {target_group_id}")
        await get_user_information_in_who_are_you(message, db, target_group_id)
        return

    # Числовой ID
    if arg_text.isdigit():
        try:
            target_group_id = int(arg_text)
            _who_dbg(f"Извлечён числовой ID: {target_group_id}")
            await get_user_information_in_who_are_you(message, db, target_group_id)
            return
        except Exception as e:
            _who_dbg(f"Ошибка приведения ID к int: {e}")

    # Поиск по @username
    if arg_text.startswith("@"):
        username_candidate = _clean_username_candidate(arg_text)
        found_id = await _try_find_user_id_by_username(db, username_candidate)
        if found_id:
            await get_user_information_in_who_are_you(message, db, found_id)
            return
        await message.reply("<b>😔 Не удалось найти пользователя по этому @username</b>", parse_mode="HTML")
        return

    # Ссылка t.me
    username_from_link = _extract_username_from_link(arg_text)
    if username_from_link:
        _who_dbg(f"Извлечён username из ссылки: {username_from_link!r}")
        found_id = await _try_find_user_id_by_username(db, username_from_link)
        if found_id:
            await get_user_information_in_who_are_you(message, db, found_id)
            return
        await message.reply("<b>😔 Не удалось найти пользователя по этой ссылке</b>", parse_mode="HTML")
        return

    # Поиск по имени / username-like
    plain_text = arg_text.strip()
    username_candidate = _clean_username_candidate(plain_text)
    should_try_username_first = _looks_like_username(username_candidate)

    if should_try_username_first:
        _who_dbg(f"Plain-text похож на username, сначала ищем как username: {username_candidate!r}")
        found_id = await _try_find_user_id_by_username(db, username_candidate)
        if found_id:
            await get_user_information_in_who_are_you(message, db, found_id)
            return
    else:
        _who_dbg(f"Plain-text не очень похож на username, но всё равно попробуем fallback-поиск позже: {username_candidate!r}")

    users_dict = await _try_find_users_by_first_name(db, plain_text)
    if users_dict:
        await _send_multiple_found_users(message, db, users_dict)
        return

    if not should_try_username_first and username_candidate:
        _who_dbg(f"Имя не найдено, запускаем финальный план Б: повторная попытка как username -> {username_candidate!r}")
        found_id = await _try_find_user_id_by_username(db, username_candidate)
        if found_id:
            await get_user_information_in_who_are_you(message, db, found_id)
            return

    await message.reply("<b>😔 Не удалось найти пользователя</b>", parse_mode="HTML")


# =========================================================
# USER INFO ("кто ты")
# =========================================================
async def get_user_information_in_who_are_you(message: Message, db, target_group_id: int):
    user_id = int(target_group_id)
    viewer_id = int(message.from_user.id)

    try:
        caption = await _build_profile_caption_for_target(
            viewer_id=viewer_id,
            target_user_id=user_id,
            db=db,
            chat_id=message.chat.id
        )
    except Exception as e:
        _who_info_dbg(f"Ошибка при сборке профиля пользователя {user_id}: {e}")
        await message.reply("<b>😔 Не удалось получить информацию о пользователе</b>", parse_mode="HTML")
        return

    has_warns = await _profile_target_has_warns(user_id)
    markup = _profile_build_who_markup(
        viewer_id=viewer_id,
        target_user_id=user_id,
        has_warns=has_warns,
    )

    sent = await message.reply(
        caption,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=markup
    )

    _profile_store_message_meta(
        sent.message_id,
        viewer_id=viewer_id,
        target_user_id=user_id,
        mode="who_are_you",
        chat_id=message.chat.id,
        has_warns=has_warns,
    )


# =========================================================
# OWN PROFILE COMMAND
# =========================================================
async def add_or_update_user_info_with_tg_cache(message, db, start_balance, *, bot=None):
    _bot = bot if bot is not None else bot1

    try:
        await add_or_update_user_info(message, db, start_balance, bot=_bot)
    except TypeError:
        await add_or_update_user_info(message, db, start_balance)
    except Exception as e:
        _p_err("INIT", "add_or_update_user_info failed", e, uid=int(message.from_user.id), level=1)

    try:
        user_id = int(message.from_user.id)
        tg_snapshot = await _profile_get_live_tg_snapshot_for_target(_bot, user_id)

        prev = user_tg_profile_cache.get(user_id, {})
        user_tg_profile_cache[user_id] = {
            **prev,
            "user_id": user_id,
            "first_name_tg": tg_snapshot.get("first_name_tg", ""),
            "last_name_tg": tg_snapshot.get("last_name_tg", ""),
            "full_name_for_db": tg_snapshot.get("full_name_for_db", ""),
            "username": tg_snapshot.get("username", ""),
            "bio": tg_snapshot.get("bio") if tg_snapshot.get("bio_loaded") else prev.get("bio", ""),
            "bio_loaded": bool(tg_snapshot.get("bio_loaded")),
            "language_code": tg_snapshot.get("language_code", ""),
            "is_premium": bool(tg_snapshot.get("is_premium", False)),
            "is_bot": bool(tg_snapshot.get("is_bot", False)),
            "chat_title": tg_snapshot.get("chat_title", ""),
            "chat_type": tg_snapshot.get("chat_type", ""),
            "updated_at": tg_snapshot.get("updated_at"),
            "last_refresh_unix": int(time.time()),
        }
    except Exception as e:
        _p_err("INIT-TG-CACHE", "tg cache init failed", e, uid=int(message.from_user.id), level=2)


async def _profile_background_sync(message: types.Message, db, bot1, viewer_id: int) -> None:
    try:
        await add_or_update_user_info_with_tg_cache(
            message=message,
            db=db,
            start_balance=0,
            bot=bot1,
        )
    except Exception as e:
        _p_err("PROFILE", "background sync failed", e, uid=viewer_id, level=2)


async def handle_profile_command(
    message: types.Message,
    *,
    db,
    bot1,
    privates: Optional[InlineKeyboardMarkup],
    country_dict: Dict[str, str],
):
    viewer_id = int(message.from_user.id)
    has_warns = await _profile_target_has_warns(viewer_id)

    try:
        caption = await _build_profile_caption_for_target(
            viewer_id=viewer_id,
            target_user_id=viewer_id,
            db=db,
            chat_id=message.chat.id
        )
        profile_markup = _profile_build_own_profile_markup(
            privates,
            viewer_id=viewer_id,
            has_warns=has_warns,
        )
    except Exception as e:
        _p_err("PROFILE", "build own profile failed", e, uid=viewer_id, level=1)
        safe_name = _profile_escape(_profile_build_full_name(message.from_user.first_name, message.from_user.last_name))
        safe_username = f"@{_profile_escape(message.from_user.username)}" if message.from_user.username else "Без username"
        caption = (
            f"🎩 <b><a href='tg://user?id={viewer_id}'>{safe_name}</a></b>\n"
            f"👤 <code>{safe_username}</code>\n"
            f"🆔 <code>{viewer_id}</code>\n"
            f"<blockquote>Профиль показан в упрощённом режиме.</blockquote>"
        )
        profile_markup = _profile_build_own_profile_markup(
            privates,
            viewer_id=viewer_id,
            has_warns=has_warns,
        )

    try:
        sent_messageprofile = await message.reply(
            text=caption,
            reply_markup=profile_markup,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        _p_err("PROFILE", "message.reply failed; trying answer", e, uid=viewer_id, level=1)
        try:
            sent_messageprofile = await message.answer(
                text=caption,
                reply_markup=profile_markup,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception as e2:
            _p_err("PROFILE", "message.answer failed", e2, uid=viewer_id, level=1)
            return

    asyncio.create_task(_profile_background_sync(message, db, bot1, viewer_id))

    try:
        user_message_mappingprofile[viewer_id] = sent_messageprofile.message_id
    except Exception:
        pass

    try:
        _profile_store_message_meta(
            sent_messageprofile.message_id,
            viewer_id=viewer_id,
            target_user_id=viewer_id,
            mode="own_profile",
            chat_id=message.chat.id,
            has_warns=has_warns,
        )
    except Exception:
        pass

    _p_dbg("PROFILE", f"profile sent message_id={sent_messageprofile.message_id}", level=1, uid=viewer_id)


# =========================================================
# REFRESH CALLBACK FOR BOTH OWN PROFILE AND "КТО ТЫ"
# =========================================================
@dp.callback_query(lambda c: c.data and c.data.startswith("whoref:"))
async def profile_refresh_callback(callback_query: types.CallbackQuery):
    clicker_id = int(callback_query.from_user.id)

    try:
        await db.ensure_pool()
    except Exception as e:
        _p_err("CALLBACK", "ensure_pool failed", e, uid=clicker_id, level=2)

    viewer_id, target_user_id, extra_button_cb = _profile_parse_refresh_cb(callback_query.data or "")

    if viewer_id is None or target_user_id is None:
        try:
            await callback_query.answer("Ошибка кнопки.", show_alert=True)
        except Exception:
            pass
        return

    if clicker_id != viewer_id:
        try:
            await callback_query.answer("Эта кнопка не для вас.", show_alert=True)
        except Exception:
            pass
        return

    msg_meta = PROFILE_MESSAGE_META.get(callback_query.message.message_id)
    if msg_meta:
        try:
            meta_viewer_id = int(msg_meta.get("viewer_id", 0))
            meta_target_id = int(msg_meta.get("target_user_id", 0))
            mode = msg_meta.get("mode", "who_are_you")
        except Exception:
            meta_viewer_id = 0
            meta_target_id = 0
            mode = "who_are_you"

        if meta_viewer_id != viewer_id or meta_target_id != target_user_id:
            try:
                await callback_query.answer("Сообщение профиля уже неактуально.", show_alert=True)
            except Exception:
                pass
            return
    else:
        mode = "who_are_you"

    inflight_key = (viewer_id, target_user_id)

    allowed, remain = _profile_check_cooldown(viewer_id, target_user_id)
    if not allowed:
        try:
            await callback_query.answer(f"Обновление доступно через {remain} сек.", show_alert=True)
        except Exception:
            pass
        return

    PROFILE_INFLIGHT_REFRESH[inflight_key] = True

    try:
        _profile_touch_cooldown(viewer_id, target_user_id)

        try:
            await callback_query.answer("Полностью обновляю профиль...", show_alert=False)
        except Exception:
            pass

        refresh_result = await _profile_full_refresh_and_render(
            viewer_id=viewer_id,
            target_user_id=target_user_id,
            db=db,
            bot1=bot1,
            chat_id=callback_query.message.chat.id,
            message_obj=callback_query.message,
            extra_button_cb=extra_button_cb,
            mode=mode,
        )

        changed_keys = refresh_result.get("changed_keys") or []
        equal_everywhere = bool(refresh_result.get("equal_everywhere"))
        db_deferred = bool(refresh_result.get("db_deferred"))
        new_caption = refresh_result.get("new_caption") or ""

        new_markup = refresh_result.get("new_markup")

        if equal_everywhere:
            try:
                await callback_query.answer(
                    "Обновлять нечего, информация уже и так правильная.",
                    show_alert=True
                )
            except Exception:
                pass
            return

        edit_mode = await _profile_safe_edit_message(
            callback_query.message,
            text=new_caption,
            reply_markup=new_markup,
            parse_mode="HTML"
        )

        if edit_mode == "not_modified":
            try:
                await callback_query.answer(
                    "Обновлять нечего, информация уже и так правильная.",
                    show_alert=True
                )
            except Exception:
                pass
            return

        if edit_mode == "failed":
            try:
                new_msg = await callback_query.message.answer(
                    text=new_caption,
                    reply_markup=new_markup,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )

                try:
                    _profile_store_message_meta(
                        new_msg.message_id,
                        viewer_id=viewer_id,
                        target_user_id=target_user_id,
                        mode="who_are_you_refresh_fallback",
                        chat_id=callback_query.message.chat.id,
                        has_warns=await _profile_target_has_warns(target_user_id),
                    )
                except Exception:
                    pass

            except Exception as e:
                _p_err("CALLBACK", "fallback send new message failed", e, uid=target_user_id, level=1)
                try:
                    await callback_query.answer(
                        "Данные обновились, но сообщение изменить не удалось.",
                        show_alert=True
                    )
                except Exception:
                    pass
                return

        changed_text = ", ".join(changed_keys) if changed_keys else "данные профиля"

        if db_deferred:
            try:
                await callback_query.answer(
                    f"Профиль обновлён: {changed_text}. База дозапишется автоматически.",
                    show_alert=True
                )
            except Exception:
                pass
            return

        try:
            await callback_query.answer(
                f"Профиль обновлён: {changed_text}.",
                show_alert=True
            )
        except Exception:
            pass

    except Exception as e:
        _p_err("CALLBACK", "profile_refresh_callback crashed", e, uid=target_user_id, level=1)
        try:
            await callback_query.answer("Ошибка обновления профиля.", show_alert=True)
        except Exception:
            pass
    finally:
        PROFILE_INFLIGHT_REFRESH.pop(inflight_key, None)


@dp.callback_query(lambda c: c.data and c.data.startswith("profwarn:"))
async def profile_warns_callback(callback_query: types.CallbackQuery):
    clicker_id = int(callback_query.from_user.id)
    viewer_id, target_user_id = _profile_parse_viewer_target_cb(callback_query.data or "", "profwarn")

    if viewer_id is None or target_user_id is None:
        try:
            await callback_query.answer("Ошибка кнопки.", show_alert=True)
        except Exception:
            pass
        return

    meta_ok, msg_meta = _profile_validate_callback_meta(callback_query, viewer_id, target_user_id)
    if not meta_ok:
        try:
            await callback_query.answer("Сообщение профиля уже неактуально.", show_alert=True)
        except Exception:
            pass
        return

    profile_mode = str(msg_meta.get("mode") or "who_are_you")
    if not _profile_can_access_warns(clicker_id, viewer_id, target_user_id, profile_mode):
        try:
            await callback_query.answer("Эта кнопка не для вас.", show_alert=True)
        except Exception:
            pass
        return

    if not await _profile_target_has_warns(target_user_id):
        try:
            await callback_query.answer("У пользователя нет активных варнов.", show_alert=True)
        except Exception:
            pass
        return

    try:
        await callback_query.answer("Загружаю варны...", show_alert=False)
    except Exception:
        pass

    try:
        warns_text = await _profile_build_warns_text(
            chat_id=callback_query.message.chat.id,
            chat_type=str(callback_query.message.chat.type),
            target_user_id=target_user_id,
            viewer_id=viewer_id,
        )
        warns_markup = _profile_build_warns_view_markup(viewer_id, target_user_id)

        edit_mode = await _profile_safe_edit_message(
            callback_query.message,
            text=warns_text,
            reply_markup=warns_markup,
            parse_mode="HTML",
        )

        if edit_mode == "failed":
            await callback_query.answer("Не удалось показать варны.", show_alert=True)
            return

        _profile_store_message_meta(
            callback_query.message.message_id,
            viewer_id=viewer_id,
            target_user_id=target_user_id,
            mode=profile_mode,
            chat_id=callback_query.message.chat.id,
            has_warns=True,
        )
    except Exception as e:
        _p_err("CALLBACK", "profile_warns_callback crashed", e, uid=target_user_id, level=1)
        try:
            await callback_query.answer("Ошибка загрузки варнов.", show_alert=True)
        except Exception:
            pass


@dp.callback_query(lambda c: c.data and c.data.startswith("profback:"))
async def profile_back_callback(callback_query: types.CallbackQuery):
    clicker_id = int(callback_query.from_user.id)
    viewer_id, target_user_id = _profile_parse_viewer_target_cb(callback_query.data or "", "profback")

    if viewer_id is None or target_user_id is None:
        try:
            await callback_query.answer("Ошибка кнопки.", show_alert=True)
        except Exception:
            pass
        return

    meta_ok, msg_meta = _profile_validate_callback_meta(callback_query, viewer_id, target_user_id)
    if not meta_ok:
        try:
            await callback_query.answer("Сообщение профиля уже неактуально.", show_alert=True)
        except Exception:
            pass
        return

    profile_mode = str(msg_meta.get("mode") or "who_are_you")
    if not _profile_can_access_warns(clicker_id, viewer_id, target_user_id, profile_mode):
        try:
            await callback_query.answer("Эта кнопка не для вас.", show_alert=True)
        except Exception:
            pass
        return

    try:
        await callback_query.answer("Возвращаю профиль...", show_alert=False)
    except Exception:
        pass

    try:
        caption = await _build_profile_caption_for_target(
            viewer_id=viewer_id,
            target_user_id=target_user_id,
            db=db,
            chat_id=callback_query.message.chat.id,
        )
        has_warns = await _profile_target_has_warns(target_user_id)

        if profile_mode == "own_profile":
            reply_markup = _profile_build_own_profile_markup(
                privates,
                viewer_id=viewer_id,
                has_warns=has_warns,
            )
        else:
            reply_markup = _profile_build_who_markup(
                viewer_id=viewer_id,
                target_user_id=target_user_id,
                has_warns=has_warns,
            )

        edit_mode = await _profile_safe_edit_message(
            callback_query.message,
            text=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )

        if edit_mode == "failed":
            await callback_query.answer("Не удалось вернуть профиль.", show_alert=True)
            return

        _profile_store_message_meta(
            callback_query.message.message_id,
            viewer_id=viewer_id,
            target_user_id=target_user_id,
            mode=profile_mode,
            chat_id=callback_query.message.chat.id,
            has_warns=has_warns,
        )
    except Exception as e:
        _p_err("CALLBACK", "profile_back_callback crashed", e, uid=target_user_id, level=1)
        try:
            await callback_query.answer("Ошибка возврата к профилю.", show_alert=True)
        except Exception:
            pass


# =========================================================
# OLD CALLBACKS - оставлены совместимыми
# =========================================================
@dp.callback_query(lambda c: c.data.startswith('vip1'))
async def callback_main(call: types.CallbackQuery):
    user_rewards = await db.get_user_rewards(call.from_user.id)

    user_id = call.from_user.id
    message_id = call.message.message_id

    randommessageprofile = [
        'Это не ваша кнопка',
        'Кнопка принадлежит другому пользователю',
        'Подожди, барашка домой зашла',
        'Не стоит этого делать',
        'Она тебя сожрёт, БЛ!@*ТЬ. ты б?..АААА!Бллядьс!ЁЁЁЁ!'
    ]

    randommessageprofile1 = random.choice(randommessageprofile)

    if user_id not in user_message_mappingprofile or user_message_mappingprofile[user_id] != message_id:
        await call.answer(randommessageprofile1)
        return

    await call.answer()

    if user_rewards:
        rewards_text = "\n\n".join([f"{i + 1}. {reward[0]}" for i, reward in enumerate(user_rewards)])
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton(text="Назад", callback_data="back_to_menu1"))
        await call.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🏅 Список ваших наград 🏅\n\n{rewards_text}",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    else:
        await call.message.reply("🕊 У вас пока нет наград.")


@dp.callback_query(lambda c: c.data.startswith('back_to_menu1'))
async def handle_back_to_menu(call: types.CallbackQuery):
    user_id = call.from_user.id
    message_id = call.message.message_id

    randommessageprofile1 = random.choice(randommessagehelp)

    if user_id not in user_message_mappingprofile or user_message_mappingprofile[user_id] != message_id:
        await call.answer(randommessageprofile1)
        return

    await call.answer()

    try:
        has_warns = await _profile_target_has_warns(user_id)
        caption = await _build_profile_caption_for_target(
            viewer_id=user_id,
            target_user_id=user_id,
            db=db,
            chat_id=call.message.chat.id
        )
        reply_markup = _profile_build_own_profile_markup(
            privates,
            viewer_id=user_id,
            has_warns=has_warns,
        )
    except Exception as e:
        _p_err("BACK", "rebuild own profile failed", e, uid=user_id, level=1)
        await call.answer("Не удалось вернуть профиль.", show_alert=True)
        return

    await call.message.edit_text(
        caption,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
        parse_mode="HTML"
    )

    _profile_store_message_meta(
        call.message.message_id,
        viewer_id=user_id,
        target_user_id=user_id,
        mode="own_profile",
        chat_id=call.message.chat.id,
        has_warns=has_warns,
    )


@dp.callback_query(lambda c: c.data.startswith('im3412'))
async def send_im(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    assets = await db.get_user_assets(user_id)
    keyboard = InlineKeyboardMarkup(row_width=1)

    message_id = callback_query.message.message_id
    randommessageprofile1 = random.choice(randommessagehelp)

    if user_id not in user_message_mappingprofile or user_message_mappingprofile[user_id] != message_id:
        await callback_query.answer(randommessageprofile1)
        return

    await callback_query.answer()

    if assets:
        assets_message = "📦 Имущество:\n\n" + "\n\n".join([f"{key}:\n{value}" for key, value in assets.items()])
    else:
        assets_message = "🎩 У вас нет имущества."

    keyboard.add(InlineKeyboardButton(text="Назад", callback_data="back_to_menu1"))

    await bot1.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=assets_message,
        reply_markup=keyboard
    )


@dp.callback_query(lambda c: c.data.startswith('refprofile1'))
async def process_callback_kb1btn1(call: types.CallbackQuery):
    link = await get_start_link(call.from_user.id)

    user_id = call.from_user.id
    message_id = call.message.message_id

    randommessageprofile1 = random.choice(randommessagehelp)

    if user_id not in user_message_mappingprofile or user_message_mappingprofile[user_id] != message_id:
        await call.answer(randommessageprofile1)
        return

    await call.answer()

    button = InlineKeyboardButton(text="Назад", callback_data="back_to_menu1")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    try:
        await bot1.edit_message_text(
            message_id=call.message.message_id,
            chat_id=call.message.chat.id,
            text=f'''
<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b>Ваша реферальная ссылка :</b> 

<code>{link}</code>

<tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> <b>1 друг = 1 кут </b>

<tg-emoji emoji-id='5278428495121248059'>🪴</tg-emoji> <b>+ 25% с каждой покупки, которую совершит ваш реферал в магазине!</b>

<tg-emoji emoji-id='5449885771420934013'>🌱</tg-emoji> <b>+ Каждый приглашённый - рост вашей реферальной статистики!</b>''',
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise


@dp.callback_query(lambda c: c.data.startswith('style3412_'))
async def send_styles(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessageprofile = [
        'Это не ваша кнопка',
        'Кнопка принадлежит другому пользователю',
        'Подожди, барашка домой зашла',
        'Не стоит этого делать',
        'Она тебя сожрёт, БЛ!@*ТЬ. ты б?..АААА!Бллядьс!ЁЁЁЁ!'
    ]
    randommessageprofile1 = random.choice(randommessageprofile)

    if user_id not in user_message_mappingprofile or user_message_mappingprofile[user_id] != message_id:
        await callback_query.answer(randommessageprofile1)
        return

    await callback_query.answer()

    inline_keyboard = []

    for style_tuple in style3412:
        emoji_text = ''.join(map(str, style_tuple[1:-1]))
        win_amount_formatted = "{:,.0f}".format(style_tuple[-1]).replace(",", ".")
        button_text = f"{style_tuple[0]}. {emoji_text} - {win_amount_formatted}"
        button_callback = f"style34123412_{style_tuple[0]}"
        inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=button_callback)])

    inline_keyboard.append([InlineKeyboardButton(text="Установить по умолчанию", callback_data="style1_default")])
    inline_keyboard.append([InlineKeyboardButton(text="Назад", callback_data="back_to_menu1")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    global user_id_with_buttons3412
    user_id_with_buttons3412 = callback_query.from_user.id

    await bot1.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="Выберите стиль:",
        reply_markup=keyboard
    )