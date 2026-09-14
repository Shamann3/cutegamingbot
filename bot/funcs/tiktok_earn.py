# -*- coding: utf-8 -*-
"""TikTok-заработок в боте: тексты, ники, набор скринов и ссылок."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import sys
from html import escape
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from aiogram.types import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup

_SERVER = Path(__file__).resolve().parents[2] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

from tiktok_earn_logic import (  # noqa: E402
    COMMENT_REWARD,
    KUT_PER_UNIT,
    MAX_NICKS,
    PHOTOS_REQUIRED,
    append_case_photos,
    comment_progress,
    hashes_from_image_bytes,
    normalize_nick,
    parse_tiktok_url,
    recheck_wait_text,
    ru_gone_verb,
    ru_screenshot_word,
    validate_nick,
    canonicalize_tiktok_url,
)

log = logging.getLogger("tiktok_earn")

TT_HUB = "tt:hub"
TT_COMMENTS = "tt:comments"
TT_VIDEOS = "tt:videos"
TT_NICKS = "tt:nicks"
TT_NICK_ADD = "tt:nick_add"
TT_NICK_EDIT = "tt:nick_edit"
TT_NICK_PICK = "tt:nick_pick:"
TT_MY_VIDEOS = "tt:my_videos"
TT_VIDEO_PAGE = "tt:vpage:"
TT_VIDEO_OPEN = "tt:vid:"
TT_NOOP = "tt:noop"
TT_SEND_PHOTOS = "tt:send_photos"
TT_SEND_LINK = "tt:send_link"
TT_CANCEL_COLLECT = "tt:cancel_collect"
TT_DONE_WAIT = "tt:done_wait"
TT_SUBMIT_PHOTOS = "tt:submit_photos"
TT_UNDO_PHOTO = "tt:undo_photo"
TT_WITHDRAW = "tt:withdraw"
TT_RECHECK = "tt:recheck:"
TT_BACK_TASKS = "questions_stars"

ICON_TT = "5456282961999570188"
ICON_BACK = "5226660202035554522"
ICON_OK = "5224257782013769471"
ICON_CAM = "5373098002641805602"
ICON_COMMENTS = "5350367217349311525"
ICON_VIDEOS = "5375309569905938163"
ICON_NICKS = "5456282961999570188"
ICON_MY_VIDEOS = "5326018884539553727"
ICON_ADD = "5339564150534200424"
ICON_EDIT = "5472410705929971383"
ICON_UNDO = "5373098002641805602"
ICON_WITHDRAW = "5213205860498549992"
ICON_PREV = "5255703720078879038"
ICON_NEXT = "5253767677670862169"
VIDEOS_PAGE_SIZE = 10

MODE_COMMENTS = "comments"
MODE_VIDEOS = "videos"
MODE_NEED_NICK = "need_nick"
MODE_WAIT_PHOTOS = "wait_photos"
MODE_WAIT_LINK = "await_video_link"
MODE_WAIT_NICK = "await_nick"
MODE_WAIT_NICK_EDIT = "await_nick_edit"
MODE_COMMENT_DONE = "comment_wait"
PHOTO_WAIT_MODES = frozenset({MODE_WAIT_PHOTOS, "collect_photos"})
NICK_WAIT_MODES = frozenset({MODE_WAIT_NICK, MODE_WAIT_NICK_EDIT, MODE_NEED_NICK})
EXAMPLE_NICK = "@cuteplayer"
EXAMPLE_COMMENT = "Как по мне @CuteGamingBot намного лучше для заработка звезд в тг"
EXAMPLE_VIDEO_URL = "https://www.tiktok.com/@cuteplayer/video/7123456789012345678"
EXAMPLE_VIDEO_SHORT = "https://vt.tiktok.com/ZSqxKyCTB/"

# Как user_gift["awaiting_recipient"] у подарка другу: флаг в памяти,
# чтобы @dp.message(lambda ...) поймал следующее сообщение до общего F.text.
WAIT_NICK = "nick"
WAIT_NICK_EDIT = "nick_edit"
WAIT_LINK = "link"
WAIT_PHOTOS = "photos"
TEXT_WAIT_KINDS = frozenset({WAIT_NICK, WAIT_NICK_EDIT, WAIT_LINK})
CANCEL_WORDS = frozenset({"назад", "завершить"})
WAIT_TTL_SECONDS = 300
PHOTO_WAIT_TTL_SECONDS = 1200
CANCEL_HINT = "<blockquote><i>Чтобы выйти - напишите</i> <code>Назад</code> <i>или</i> <code>Завершить</code></blockquote>"
REPLY_HINT = "<blockquote><i>Отправьте следующим сообщением в этот чат.</i></blockquote>"
PHOTO_HINT = "<blockquote><i>Можно альбомом или по одному. Telegram берёт до 10 фото за раз - пришлите ещё, пока не будет 15.</i></blockquote>"
INPUT_FOOTER = f"{REPLY_HINT}\n{CANCEL_HINT}"
PHOTO_FOOTER = f"{PHOTO_HINT}\n{CANCEL_HINT}"


def format_hashtag(raw: str, *, fallback: str = "тгзвезды") -> str:
    s = (raw or "").strip() or fallback
    if s.startswith("@"):
        s = s[1:]
    if s.startswith("#"):
        s = s[1:]
    s = "".join(s.split()) or fallback
    return f"#{s}"
_tt_wait: dict[int, dict[str, Any]] = {}
_timeout_tasks: dict[int, asyncio.Task] = {}

_SCHEMA_READY = False


def _pool():
    from bot.db_create.db import db
    return getattr(db, "pool", None)


def _json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


async def ensure_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    pool = _pool()
    if not pool:
        return
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS tiktok_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            comment_tag TEXT NOT NULL DEFAULT 'тг звезды',
            video_hashtag TEXT NOT NULL DEFAULT '@CuteGamingBot',
            comment_reward INTEGER NOT NULL DEFAULT 5,
            views_per_unit INTEGER NOT NULL DEFAULT 1000,
            kut_per_unit INTEGER NOT NULL DEFAULT 30,
            recheck_days INTEGER NOT NULL DEFAULT 7,
            max_nicks INTEGER NOT NULL DEFAULT 3,
            photos_required INTEGER NOT NULL DEFAULT 15,
            reject_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tiktok_nicks (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            nick TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (nick)
        );
        CREATE INDEX IF NOT EXISTS tiktok_nicks_user_idx ON tiktok_nicks (user_id);
        CREATE TABLE IF NOT EXISTS tiktok_sessions (
            user_id BIGINT PRIMARY KEY,
            mode TEXT NOT NULL DEFAULT '',
            extra JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tiktok_comment_cases (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            photos JSONB NOT NULL DEFAULT '[]'::jsonb,
            nick_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
            reviewed_by BIGINT,
            reviewed_at TIMESTAMPTZ,
            reject_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tiktok_videos (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            url TEXT NOT NULL,
            canonical_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            last_views INTEGER NOT NULL DEFAULT 0,
            last_paid_thousands INTEGER NOT NULL DEFAULT 0,
            last_checked_at TIMESTAMPTZ,
            recheck_requested_at TIMESTAMPTZ,
            reject_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
            reviewed_by BIGINT,
            reviewed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS tiktok_comment_one_pending
            ON tiktok_comment_cases (user_id) WHERE status = 'pending';
        CREATE UNIQUE INDEX IF NOT EXISTS tiktok_video_one_pending
            ON tiktok_videos (user_id) WHERE status = 'pending';
        CREATE UNIQUE INDEX IF NOT EXISTS tiktok_video_canonical_active
            ON tiktok_videos (canonical_key) WHERE status IN ('pending', 'live');
        CREATE INDEX IF NOT EXISTS tiktok_comment_status_idx
            ON tiktok_comment_cases (status, created_at);
        CREATE INDEX IF NOT EXISTS tiktok_videos_status_idx
            ON tiktok_videos (status, created_at);
        """
    )
    await pool.execute(
        """
        INSERT INTO tiktok_settings (id) VALUES (1)
        ON CONFLICT (id) DO NOTHING
        """
    )
    _SCHEMA_READY = True


async def get_settings() -> dict[str, Any]:
    await ensure_schema()
    pool = _pool()
    row = await pool.fetchrow("SELECT * FROM tiktok_settings WHERE id = 1")
    if not row:
        return {
            "commentTag": "тг звезды",
            "videoHashtag": "@CuteGamingBot",
            "commentReward": COMMENT_REWARD,
            "viewsPerUnit": 1000,
            "kutPerUnit": KUT_PER_UNIT,
            "recheckDays": 7,
            "maxNicks": 3,
            "photosRequired": PHOTOS_REQUIRED,
        }
    return {
        "commentTag": row["comment_tag"],
        "videoHashtag": row["video_hashtag"],
        "commentReward": int(row["comment_reward"]),
        "viewsPerUnit": int(row["views_per_unit"]),
        "kutPerUnit": int(row["kut_per_unit"]),
        "recheckDays": int(row["recheck_days"]),
        "maxNicks": int(row["max_nicks"]),
        "photosRequired": int(row["photos_required"]),
    }


async def list_nicks(user_id: int) -> list[str]:
    await ensure_schema()
    rows = await _pool().fetch(
        "SELECT nick FROM tiktok_nicks WHERE user_id = $1 ORDER BY id",
        int(user_id),
    )
    return [r["nick"] for r in rows]


async def require_nicks(user_id: int) -> list[str]:
    nicks = await list_nicks(user_id)
    if not nicks:
        raise ValueError("Сначала напишите имя своего TikTok.")
    return nicks


async def has_pending(user_id: int) -> bool:
    await ensure_schema()
    pool = _pool()
    comment = await pool.fetchval(
        "SELECT 1 FROM tiktok_comment_cases WHERE user_id = $1 AND status = 'pending'",
        int(user_id),
    )
    video = await pool.fetchval(
        """
        SELECT 1 FROM tiktok_videos
        WHERE user_id = $1 AND (status = 'pending' OR recheck_requested_at IS NOT NULL)
        """,
        int(user_id),
    )
    return bool(comment or video)


async def add_nick(user_id: int, raw: str) -> str:
    await ensure_schema()
    cfg = await get_settings()
    nick = validate_nick(raw)
    nicks = await list_nicks(user_id)
    if nick in nicks:
        raise ValueError("Такой ник уже есть в Вашем списке")
    if len(nicks) >= int(cfg["maxNicks"]):
        raise ValueError(f"Можно не больше {cfg['maxNicks']} ников")
    if await has_pending(user_id):
        raise ValueError("Сейчас идёт проверка. Ники можно менять после ответа.")
    owner = await _pool().fetchval("SELECT user_id FROM tiktok_nicks WHERE nick = $1", nick)
    if owner and int(owner) != int(user_id):
        raise ValueError("Этот ник уже занят другим игроком")
    try:
        await _pool().execute(
            "INSERT INTO tiktok_nicks (user_id, nick) VALUES ($1, $2)",
            int(user_id),
            nick,
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise ValueError("Этот ник уже занят другим игроком") from exc
        raise
    return nick


async def replace_nick(user_id: int, old_nick: str, raw: str) -> str:
    await ensure_schema()
    if await has_pending(user_id):
        raise ValueError("Сейчас идёт проверка. Ники можно менять после ответа.")
    new_nick = validate_nick(raw)
    old = normalize_nick(old_nick)
    current = await list_nicks(user_id)
    if old not in current:
        raise ValueError("Такого ника нет в Вашем списке")
    if new_nick in current and new_nick != old:
        raise ValueError("Такой ник уже есть в Вашем списке")
    owner = await _pool().fetchval("SELECT user_id FROM tiktok_nicks WHERE nick = $1", new_nick)
    if owner and int(owner) != int(user_id):
        raise ValueError("Этот ник уже занят другим игроком")
    await _pool().execute(
        "UPDATE tiktok_nicks SET nick = $3 WHERE user_id = $1 AND nick = $2",
        int(user_id),
        old,
        new_nick,
    )
    return new_nick


async def get_session(user_id: int) -> dict[str, Any]:
    await ensure_schema()
    row = await _pool().fetchrow(
        "SELECT mode, extra FROM tiktok_sessions WHERE user_id = $1",
        int(user_id),
    )
    if not row:
        return {"mode": "", "extra": {}}
    extra = _json(row["extra"]) or {}
    if not isinstance(extra, dict):
        extra = {}
    return {"mode": row["mode"] or "", "extra": extra}


async def set_session(user_id: int, mode: str, extra: dict[str, Any] | None = None) -> None:
    await ensure_schema()
    await _pool().execute(
        """
        INSERT INTO tiktok_sessions (user_id, mode, extra, updated_at)
        VALUES ($1, $2, $3::jsonb, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET mode = EXCLUDED.mode, extra = EXCLUDED.extra, updated_at = NOW()
        """,
        int(user_id),
        mode or "",
        json.dumps(extra or {}, ensure_ascii=False),
    )


async def clear_session(user_id: int) -> None:
    clear_wait(user_id)
    await set_session(user_id, "", {})


def _parse_expires(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _expires_is_past(value: Any, *, now: datetime | None = None) -> bool:
    exp = _parse_expires(value)
    if exp is None:
        return False
    stamp = now or datetime.now(timezone.utc)
    return stamp >= exp


def _rec_is_expired(rec: dict[str, Any] | None, *, now: datetime | None = None) -> bool:
    if not rec:
        return False
    return _expires_is_past(rec.get("expires_at"), now=now)


def _fresh_expires_iso(kind: str = "") -> str:
    ttl = PHOTO_WAIT_TTL_SECONDS if kind == WAIT_PHOTOS else WAIT_TTL_SECONDS
    return (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat()


def peek_wait(user_id: int) -> dict[str, Any] | None:
    return _tt_wait.get(int(user_id))


def get_wait(user_id: int) -> dict[str, Any] | None:
    rec = peek_wait(user_id)
    if rec and rec.get("awaiting") and not _rec_is_expired(rec):
        return rec
    return None


def is_wait_expired(user_id: int) -> bool:
    return _rec_is_expired(peek_wait(user_id))


def begin_wait(
    user_id: int,
    kind: str,
    *,
    after: str = "",
    prompt_chat_id: int | None = None,
    prompt_message_id: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "kind": kind,
        "after": after,
        "awaiting": True,
        "prompt_chat_id": int(prompt_chat_id) if prompt_chat_id else None,
        "prompt_message_id": int(prompt_message_id) if prompt_message_id else None,
    }
    if extra:
        rec.update(extra)
        rec["kind"] = kind
        rec["awaiting"] = True
        if after:
            rec["after"] = after
    if extra is not None and extra.get("expires_at") is not None:
        parsed = _parse_expires(extra.get("expires_at"))
        rec["expires_at"] = parsed.isoformat() if parsed else _fresh_expires_iso(kind)
    else:
        rec["expires_at"] = _fresh_expires_iso(kind)
    _tt_wait[int(user_id)] = rec
    return rec


def remember_prompt(user_id: int, chat_id: int | None, message_id: int | None) -> None:
    rec = _tt_wait.get(int(user_id))
    if not rec:
        return
    if chat_id:
        rec["prompt_chat_id"] = int(chat_id)
    if message_id:
        rec["prompt_message_id"] = int(message_id)


def remember_album_group(user_id: int, media_group_id: Any) -> None:
    rec = _tt_wait.get(int(user_id))
    if rec and media_group_id:
        rec["album_group"] = str(media_group_id)


async def touch_wait(user_id: int) -> None:
    rec = peek_wait(user_id)
    if not rec:
        return
    rec["awaiting"] = True
    rec["expires_at"] = _fresh_expires_iso(str(rec.get("kind") or ""))
    schedule_wait_timeout(user_id)
    try:
        session = await get_session(user_id)
        extra = dict(session.get("extra") or {})
        extra["expires_at"] = rec["expires_at"]
        extra["awaiting"] = True
        extra["kind"] = rec.get("kind")
        await set_session(user_id, session.get("mode") or MODE_WAIT_PHOTOS, extra)
    except Exception:
        log.exception("tiktok touch wait persist failed uid=%s", user_id)


def is_cancel_input(text: str) -> bool:
    raw = (text or "").strip().lower().replace("«", "").replace("»", "").replace('"', "")
    return raw in CANCEL_WORDS


def force_reply_markup() -> ForceReply:
    return ForceReply(selective=True)


def with_input_footer(body: str) -> str:
    text = (body or "").rstrip()
    if CANCEL_HINT not in text:
        return f"{text}\n\n{INPUT_FOOTER}"
    if REPLY_HINT not in text:
        return f"{text}\n{REPLY_HINT}"
    return text


def cancel_wait_timeout(user_id: int) -> None:
    task = _timeout_tasks.pop(int(user_id), None)
    if task is not None and not task.done():
        task.cancel()


def schedule_wait_timeout(user_id: int) -> None:
    cancel_wait_timeout(user_id)
    rec = peek_wait(user_id)
    delay = float(WAIT_TTL_SECONDS)
    exp = _parse_expires((rec or {}).get("expires_at"))
    if exp is not None:
        delay = max(0.0, (exp - datetime.now(timezone.utc)).total_seconds())

    async def _job() -> None:
        try:
            await asyncio.sleep(delay)
            if _rec_is_expired(peek_wait(user_id)):
                await expire_wait(user_id, notify=True)
        except asyncio.CancelledError:
            return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _timeout_tasks[int(user_id)] = loop.create_task(_job())


def clear_wait(user_id: int) -> None:
    cancel_wait_timeout(user_id)
    _tt_wait.pop(int(user_id), None)


def is_awaiting_text(user_id: int) -> bool:
    rec = get_wait(user_id)
    return bool(rec and rec.get("kind") in TEXT_WAIT_KINDS)


def is_awaiting_photos(user_id: int) -> bool:
    rec = get_wait(user_id)
    return bool(rec and rec.get("kind") == WAIT_PHOTOS)


def chat_type_name(chat_or_message: Any = None, chat_type: Any = None) -> str:
    raw = chat_type
    if raw is None:
        if chat_or_message is None:
            return ""
        chat = getattr(chat_or_message, "chat", chat_or_message)
        raw = getattr(chat, "type", chat)
    value = getattr(raw, "value", raw)
    return str(value or "").strip().lower()


def is_private_chat_type(chat_type: Any = None, *, message: Any = None) -> bool:
    return chat_type_name(message, chat_type=chat_type) == "private"


def message_is_private_chat(message: Any) -> bool:
    return is_private_chat_type(message=message)


def should_skip_main_text_handler(user_id: int, chat_type: Any = "private") -> bool:
    """Общий F.text пропускаем только в личке, пока ждём ник / ссылку / фото."""
    if not is_private_chat_type(chat_type):
        return False
    rec = get_wait(int(user_id))
    return bool(rec and rec.get("awaiting"))


def should_skip_photo_handler(user_id: int, chat_type: Any = "private") -> bool:
    """Чужой F.photo не должен забирать скрины. В группе никогда не скипать."""
    if not is_private_chat_type(chat_type):
        return False
    return is_awaiting_photos(user_id)


def _prompt_ids_from(extra: dict[str, Any]) -> tuple[int | None, int | None]:
    chat_id = extra.get("prompt_chat_id")
    message_id = extra.get("prompt_message_id")
    try:
        chat_id = int(chat_id) if chat_id else None
    except (TypeError, ValueError):
        chat_id = None
    try:
        message_id = int(message_id) if message_id else None
    except (TypeError, ValueError):
        message_id = None
    return chat_id, message_id


async def persist_prompt(user_id: int, chat_id: int | None, message_id: int | None) -> None:
    remember_prompt(user_id, chat_id, message_id)
    session = await get_session(user_id)
    extra = dict(session.get("extra") or {})
    rec = _tt_wait.get(int(user_id)) or {}
    if chat_id:
        extra["prompt_chat_id"] = int(chat_id)
    if message_id:
        extra["prompt_message_id"] = int(message_id)
    extra["awaiting"] = True
    if rec.get("kind"):
        extra["kind"] = rec["kind"]
    if rec.get("after"):
        extra["after"] = rec["after"]
    if rec.get("oldNick"):
        extra["oldNick"] = rec["oldNick"]
    if rec.get("expires_at"):
        extra["expires_at"] = rec["expires_at"]
    await set_session(user_id, session.get("mode") or "", extra)


def _session_is_wait(mode: str, extra: dict[str, Any]) -> bool:
    return bool(
        extra.get("awaiting")
        or extra.get("prompt_message_id")
        or mode in NICK_WAIT_MODES
        or mode == MODE_WAIT_LINK
        or mode in PHOTO_WAIT_MODES
    )


async def expire_wait(user_id: int, *, notify: bool = True) -> bool:
    """Снять waiter. Дело и уже сданные фото не трогаем."""
    rec = peek_wait(user_id) or {}
    chat_id = rec.get("prompt_chat_id")
    mid = rec.get("prompt_message_id")
    extra: dict[str, Any] = {}
    mode = ""
    try:
        session = await get_session(user_id)
        extra = dict(session.get("extra") or {})
        mode = str(session.get("mode") or "")
        chat_id = chat_id or extra.get("prompt_chat_id")
        mid = mid or extra.get("prompt_message_id")
    except Exception:
        pass
    cancel_wait_timeout(user_id)
    _tt_wait.pop(int(user_id), None)
    extra.pop("awaiting", None)
    extra.pop("prompt_message_id", None)
    extra.pop("prompt_chat_id", None)
    extra.pop("expires_at", None)
    extra.pop("kind", None)
    extra.pop("album_group", None)
    if mode in NICK_WAIT_MODES:
        mode = ""
    elif mode == MODE_WAIT_LINK:
        mode = MODE_VIDEOS
    elif mode in PHOTO_WAIT_MODES:
        mode = MODE_COMMENTS
    try:
        await set_session(user_id, mode, extra)
    except Exception:
        pass
    if notify:
        try:
            from main import bot1
            if chat_id and mid:
                try:
                    await bot1.delete_message(int(chat_id), int(mid))
                except Exception:
                    pass
            await bot1.send_message(
                int(chat_id or user_id),
                text_wait_expired(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception:
            log.exception("tiktok expire notify failed uid=%s", user_id)
    return True


async def expire_wait_if_needed(user_id: int) -> bool:
    rec = peek_wait(user_id)
    if rec and _rec_is_expired(rec):
        await expire_wait(user_id, notify=True)
        return True
    try:
        session = await get_session(user_id)
    except Exception:
        return False
    extra = dict(session.get("extra") or {})
    mode = str(session.get("mode") or "")
    if _session_is_wait(mode, extra) and _expires_is_past(extra.get("expires_at")):
        await expire_wait(user_id, notify=True)
        return True
    return False


async def restore_wait_from_session(user_id: int) -> bool:
    """Если в БД wait, а в памяти пусто (рестарт) - поднять флаг и prompt id как у user_gift."""
    if get_wait(user_id):
        return True
    if peek_wait(user_id) and _rec_is_expired(peek_wait(user_id)):
        await expire_wait(user_id, notify=True)
        return False
    session = await get_session(user_id)
    mode = session.get("mode") or ""
    extra = dict(session.get("extra") or {})
    if _session_is_wait(mode, extra) and _expires_is_past(extra.get("expires_at")):
        await expire_wait(user_id, notify=True)
        return False
    after = str(extra.get("after") or extra.get("origin") or "")
    prompt_chat_id, prompt_message_id = _prompt_ids_from(extra)
    restored = False
    if mode in NICK_WAIT_MODES:
        kind = WAIT_NICK_EDIT if mode == MODE_WAIT_NICK_EDIT else WAIT_NICK
        begin_wait(
            user_id,
            kind,
            after=after,
            extra=extra,
            prompt_chat_id=prompt_chat_id,
            prompt_message_id=prompt_message_id,
        )
        restored = True
    elif mode == MODE_WAIT_LINK:
        begin_wait(
            user_id,
            WAIT_LINK,
            after=after or "videos",
            extra=extra,
            prompt_chat_id=prompt_chat_id,
            prompt_message_id=prompt_message_id,
        )
        restored = True
    elif mode in PHOTO_WAIT_MODES:
        begin_wait(
            user_id,
            WAIT_PHOTOS,
            after=after or "comments",
            extra=extra,
            prompt_chat_id=prompt_chat_id,
            prompt_message_id=prompt_message_id,
        )
        restored = True
    if restored:
        schedule_wait_timeout(user_id)
    return restored


def _message_is_private(message: Any) -> bool:
    return message_is_private_chat(message)


def handler_would_accept_text(user_id: int, text: str, *, chat_type: str = "private") -> bool:
    if str(chat_type) != "private":
        return False
    rec = get_wait(user_id)
    if not rec or rec.get("kind") not in TEXT_WAIT_KINDS:
        return False
    raw = (text or "").strip()
    return bool(raw) and not raw.startswith("/")


def _gift_style_reply_ok(message: Any, rec: dict[str, Any]) -> bool:
    prompt_id = rec.get("prompt_message_id")
    reply = getattr(message, "reply_to_message", None)
    reply_id = getattr(reply, "message_id", None) if reply else None
    if prompt_id and reply_id and int(reply_id) == int(prompt_id):
        return True
    group = getattr(message, "media_group_id", None)
    if group and rec.get("kind") == WAIT_PHOTOS and str(rec.get("album_group") or "") == str(group):
        return True
    return False


def _gift_style_or_fallback(message: Any, rec: dict[str, Any]) -> bool:
    """Как у подарка: ответ на prompt_message_id. Если ForceReply смахнули - всё равно принять."""
    if _gift_style_reply_ok(message, rec):
        return True
    if rec.get("prompt_message_id") and getattr(message, "reply_to_message", None):
        return False
    return True


def message_matches_wait_text(message: Any) -> bool:
    if not message or not getattr(message, "from_user", None):
        return False
    if not _message_is_private(message):
        return False
    rec = get_wait(message.from_user.id)
    raw = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
    if rec and rec.get("kind") == WAIT_PHOTOS and is_cancel_input(raw):
        return True
    if rec and rec.get("kind") in TEXT_WAIT_KINDS:
        if is_cancel_input(raw):
            return True
        return handler_would_accept_text(message.from_user.id, raw)
    return False


def message_matches_wait_photo(message: Any) -> bool:
    if not message or not getattr(message, "from_user", None):
        return False
    if not _message_is_private(message):
        return False
    if not getattr(message, "photo", None):
        return False
    rec = get_wait(message.from_user.id)
    if not rec or rec.get("kind") != WAIT_PHOTOS:
        return False
    group = getattr(message, "media_group_id", None)
    if group:
        remember_album_group(message.from_user.id, group)
    # Альбом в Telegram: первое фото отвечает на ForceReply, остальные -
    # на первое фото альбома. Пока ждём скрины, принимаем все фото в личке.
    return True


def message_matches_wait_noise(message: Any) -> bool:
    if not message or not getattr(message, "from_user", None):
        return False
    if not _message_is_private(message):
        return False
    if getattr(message, "photo", None):
        return False
    text = (getattr(message, "text", None) or "").strip()
    if text.startswith("/"):
        return False
    if is_cancel_input(text):
        return False
    if not (text or getattr(message, "document", None)):
        return False
    rec = get_wait(message.from_user.id)
    if not rec:
        return False
    if rec.get("kind") == WAIT_PHOTOS:
        return _gift_style_or_fallback(message, rec)
    if rec.get("kind") in {WAIT_NICK, WAIT_NICK_EDIT} and getattr(message, "document", None):
        return _gift_style_or_fallback(message, rec)
    return False


async def arm_wait(
    user_id: int,
    kind: str,
    mode: str,
    extra: dict[str, Any] | None = None,
    *,
    prompt_chat_id: int | None = None,
    prompt_message_id: int | None = None,
) -> dict[str, Any]:
    extra = dict(extra or {})
    after = str(extra.get("after") or extra.get("origin") or "")
    extra.pop("expires_at", None)
    if prompt_chat_id:
        extra["prompt_chat_id"] = int(prompt_chat_id)
    if prompt_message_id:
        extra["prompt_message_id"] = int(prompt_message_id)
    extra["awaiting"] = True
    extra["kind"] = kind
    rec = begin_wait(
        user_id,
        kind,
        after=after,
        prompt_chat_id=prompt_chat_id,
        prompt_message_id=prompt_message_id,
        extra=extra,
    )
    extra["expires_at"] = rec["expires_at"]
    await set_session(user_id, mode, extra)
    schedule_wait_timeout(user_id)
    return rec


async def get_pending_comment_case(user_id: int) -> dict[str, Any] | None:
    await ensure_schema()
    cfg = await get_settings()
    row = await _pool().fetchrow(
        "SELECT id, photos, status FROM tiktok_comment_cases WHERE user_id = $1 AND status = 'pending'",
        int(user_id),
    )
    if not row:
        return None
    photos = _json(row["photos"]) or []
    if not isinstance(photos, list):
        photos = []
    progress = comment_progress(photos, cfg["photosRequired"])
    return {"id": int(row["id"]), "photos": photos, "status": row["status"], **progress}


async def submit_comment_case(user_id: int, photos: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Старый колбэк «Отправить»: кадры уже на проверке с первого фото."""
    await require_nicks(user_id)
    case = await get_pending_comment_case(user_id)
    if not case:
        raise ValueError("Сначала пришлите хотя бы один скриншот. Он сразу уйдёт на проверку.")
    return case


async def submit_video(user_id: int, raw_url: str) -> dict[str, Any]:
    await ensure_schema()
    await require_nicks(user_id)
    parsed = await asyncio.to_thread(canonicalize_tiktok_url, raw_url)
    pending = await _pool().fetchval(
        "SELECT id FROM tiktok_videos WHERE user_id = $1 AND status = 'pending'",
        int(user_id),
    )
    if pending:
        raise ValueError("Это видео ещё на проверке. Новую ссылку можно прислать после ответа.")
    taken = await _pool().fetchval(
        """
        SELECT id FROM tiktok_videos
        WHERE canonical_key = $1 AND status IN ('pending', 'live')
        """,
        parsed["canonical"],
    )
    if taken:
        raise ValueError("Этот ролик уже в системе.")
    await _pool().execute(
        """
        INSERT INTO tiktok_videos (user_id, url, canonical_key, status)
        VALUES ($1, $2, $3, 'pending')
        """,
        int(user_id),
        parsed["url"],
        parsed["canonical"],
    )
    await clear_session(user_id)
    return parsed


def video_recheck_state(last_checked, days: int) -> dict[str, Any]:
    if not last_checked:
        return {"ready": True, "waitText": ""}
    ready = last_checked if last_checked.tzinfo else last_checked.replace(tzinfo=timezone.utc)
    ready_at = ready + timedelta(days=int(days))
    now = datetime.now(timezone.utc)
    if ready_at > now:
        return {"ready": False, "waitText": recheck_wait_text((ready_at - now).total_seconds())}
    return {"ready": True, "waitText": ""}


async def list_user_videos(user_id: int) -> list[dict[str, Any]]:
    await ensure_schema()
    cfg = await get_settings()
    days = int(cfg["recheckDays"])
    rows = await _pool().fetch(
        """
        SELECT id, url, status, last_views, last_paid_thousands,
               last_checked_at, recheck_requested_at, reject_reasons, created_at
        FROM tiktok_videos WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        int(user_id),
    )
    unit = int(cfg["kutPerUnit"])
    out = []
    for r in rows:
        state = video_recheck_state(r["last_checked_at"], days)
        paid_thousands = int(r["last_paid_thousands"] or 0)
        out.append(
            {
                "id": int(r["id"]),
                "url": r["url"],
                "status": r["status"],
                "lastViews": int(r["last_views"] or 0),
                "lastPaidThousands": paid_thousands,
                "paidKut": paid_thousands * unit,
                "kutPerUnit": unit,
                "recheckPending": bool(r["recheck_requested_at"]),
                "lastCheckedAt": r["last_checked_at"],
                "recheckReady": state["ready"],
                "recheckWaitText": state["waitText"],
                "rejectReasons": _json(r["reject_reasons"]) or [],
            }
        )
    return out


async def get_user_video(user_id: int, video_id: int) -> dict[str, Any] | None:
    videos = await list_user_videos(user_id)
    for item in videos:
        if int(item["id"]) == int(video_id):
            return item
    return None


async def request_recheck(user_id: int, video_id: int) -> None:
    await ensure_schema()
    cfg = await get_settings()
    row = await _pool().fetchrow(
        "SELECT * FROM tiktok_videos WHERE id = $1 AND user_id = $2",
        int(video_id),
        int(user_id),
    )
    if not row:
        raise ValueError("Видео не найдено")
    if row["status"] != "live":
        raise ValueError("Перепроверка доступна только для принятого видео")
    if row["recheck_requested_at"]:
        raise ValueError("Запрос уже на проверке")
    last = row["last_checked_at"]
    days = int(cfg["recheckDays"])
    if last:
        ready = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
        ready_at = ready + timedelta(days=days)
        now = datetime.now(timezone.utc)
        if ready_at > now:
            raise ValueError(recheck_wait_text((ready_at - now).total_seconds()))
    await _pool().execute(
        "UPDATE tiktok_videos SET recheck_requested_at = NOW() WHERE id = $1",
        int(video_id),
    )


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _btn(text: str, data: str, icon: str | None = None) -> InlineKeyboardButton:
    kwargs = {"text": text, "callback_data": data, "style": "default"}
    if icon:
        kwargs["icon_custom_emoji_id"] = icon
    return InlineKeyboardButton(**kwargs)


def _chain_rows(*exclude: str) -> list[list[InlineKeyboardButton]]:
    items = (
        ("comments", "Комментарии", TT_COMMENTS, ICON_COMMENTS),
        ("videos", "Видео о боте", TT_VIDEOS, ICON_VIDEOS),
        ("nicks", "Имена аккаунтов", TT_NICKS, ICON_NICKS),
        ("mine", "Ваши ролики", TT_MY_VIDEOS, ICON_MY_VIDEOS),
    )
    return [[_btn(label, data, icon)] for key, label, data, icon in items if key not in exclude]


def hub_keyboard() -> InlineKeyboardMarkup:
    return _kb(
        [
            *_chain_rows(),
            [_btn("Назад", TT_BACK_TASKS, ICON_BACK)],
        ]
    )


def comments_keyboard(
    *,
    can_send: bool = True,
    count: int = 0,
    needed: int = 15,
    waiting: bool = False,
    complete: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if complete or count >= needed:
        rows.append([_btn("Отклонить заявку", TT_WITHDRAW, ICON_WITHDRAW)])
    elif count > 0:
        rows.append([_btn("Убрать последнее", TT_UNDO_PHOTO, ICON_UNDO)])
    else:
        rows.append([_btn("Имена аккаунтов", TT_NICKS, ICON_NICKS)])
    rows.append([_btn("Назад", TT_HUB, ICON_BACK)])
    return _kb(rows)


def videos_keyboard(
    videos: list[dict] | None = None,
    *,
    waiting: bool = False,
    can_send: bool = True,
) -> InlineKeyboardMarkup:
    return _kb(
        [
            [_btn("Ваши ролики", TT_MY_VIDEOS, ICON_MY_VIDEOS)],
            [_btn("Имена аккаунтов", TT_NICKS, ICON_NICKS)],
            [_btn("Назад", TT_HUB, ICON_BACK)],
        ]
    )


def nicks_keyboard(nicks: list[str], *, locked: bool, origin: str = "hub") -> InlineKeyboardMarkup:
    rows = []
    if not locked:
        rows.append([_btn("Написать имя TikTok", TT_NICK_ADD, ICON_ADD)])
        if nicks:
            rows.append([_btn("Изменить", TT_NICK_EDIT, ICON_EDIT)])
    back = {
        "comments": TT_COMMENTS,
        "videos": TT_VIDEOS,
        "mine": TT_MY_VIDEOS,
    }.get(origin, TT_HUB)
    rows.append([_btn("Назад", back, ICON_BACK)])
    return _kb(rows)


def nick_pick_keyboard(nicks: list[str]) -> InlineKeyboardMarkup:
    rows = [[_btn(f"@{n}", f"{TT_NICK_PICK}{n}", ICON_NICKS)] for n in nicks]
    rows.append([_btn("Назад", TT_NICKS, ICON_BACK)])
    return _kb(rows)


def nick_wait_keyboard(*, back: str = "hub") -> InlineKeyboardMarkup:
    data = TT_HUB
    if back == "nicks":
        data = TT_NICKS
    elif back == "comments":
        data = TT_COMMENTS
    elif back == "videos":
        data = TT_VIDEOS
    elif back == "mine":
        data = TT_MY_VIDEOS
    return _kb([[_btn("Назад", data, ICON_BACK)]])


def collect_keyboard(count: int, needed: int) -> InlineKeyboardMarkup:
    return comments_keyboard(can_send=True, count=count, needed=needed, waiting=True)


def bind_keyboard(*, waiting: bool = False) -> InlineKeyboardMarkup:
    return _kb([[_btn("Назад", TT_HUB, ICON_BACK)]])


def done_keyboard(*, after: str = "hub") -> InlineKeyboardMarkup:
    rows = []
    if after == "comments":
        rows.append([_btn("Продолжить", TT_COMMENTS, ICON_COMMENTS)])
    elif after == "videos":
        rows.append([_btn("Продолжить", TT_VIDEOS, ICON_VIDEOS)])
    elif after == "mine":
        rows.append([_btn("К роликам", TT_MY_VIDEOS, ICON_MY_VIDEOS)])
    rows.append([_btn("Тик ток", TT_HUB, ICON_TT)])
    return _kb(rows)


def _video_pages(total: int, page: int) -> tuple[int, int]:
    pages = max(1, math.ceil(total / VIDEOS_PAGE_SIZE) if total else 1)
    page = max(0, min(int(page or 0), pages - 1))
    return page, pages


def video_button_label(item: dict[str, Any]) -> str:
    vid = int(item.get("id") or 0)
    status = item.get("status")
    paid = int(item.get("paidKut") or 0)
    if status == "pending":
        return f"На проверке · #{vid}"
    if status == "rejected":
        return f"Отклонено · #{vid}"
    if item.get("recheckPending"):
        return f"Перепроверка · #{vid}"
    if paid:
        return f"Принято · +{paid} кут"
    return f"Принято · #{vid}"


def my_videos_keyboard(
    videos: list[dict[str, Any]],
    *,
    page: int = 0,
) -> InlineKeyboardMarkup:
    page, pages = _video_pages(len(videos), page)
    start = page * VIDEOS_PAGE_SIZE
    chunk = videos[start:start + VIDEOS_PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []
    for item in chunk:
        rows.append([_btn(video_button_label(item), f"{TT_VIDEO_OPEN}{item['id']}", ICON_MY_VIDEOS)])
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(_btn("Раньше", f"{TT_VIDEO_PAGE}{page - 1}", ICON_PREV))
        if page + 1 < pages:
            nav.append(_btn("Дальше", f"{TT_VIDEO_PAGE}{page + 1}", ICON_NEXT))
        if nav:
            rows.append(nav)
    rows.append([_btn("Новая ссылка", TT_VIDEOS, ICON_VIDEOS)])
    rows.append([_btn("Назад", TT_HUB, ICON_BACK)])
    return _kb(rows)


def video_card_keyboard(item: dict[str, Any], *, page: int = 0) -> InlineKeyboardMarkup:
    rows = []
    if (
        item.get("status") == "live"
        and not item.get("recheckPending")
        and item.get("recheckReady") is not False
    ):
        rows.append([_btn("Проверить просмотры", f"{TT_RECHECK}{item['id']}", ICON_OK)])
    rows.append([_btn("Назад", f"{TT_VIDEO_PAGE}{page}", ICON_BACK)])
    return _kb(rows)


def text_hub(cfg: dict[str, Any] | None = None, *, has_nicks: bool = True) -> str:
    cfg = cfg or {}
    reward = int(cfg.get("commentReward") or COMMENT_REWARD)
    kut = int(cfg.get("kutPerUnit") or KUT_PER_UNIT)
    photos = int(cfg.get("photosRequired") or PHOTOS_REQUIRED)
    lead = (
        "Выберите задание. Куты приходят после проверки."
        if has_nicks
        else "Выберите задание. Сначала один раз напишем имя TikTok - это полминуты."
    )
    return (
        "<tg-emoji emoji-id='5456282961999570188'>🎵</tg-emoji> <b>Тик ток</b>\n\n"
        f"<tg-emoji emoji-id='5472083261918291121'>😎</tg-emoji> <b><i>{lead}</i></b>\n"
        f"<blockquote><b>1. Комментарии\n"
        f"{photos} фото = {reward} кут. Можно закрыть сегодня.</b></blockquote>\n"
        f"<blockquote><b>2. Видео про бота\n"
        f"Каждые 1.000 просмотров = {kut} кут. Чем больше просмотров - тем больше кут.</b></blockquote>"
    )


def text_comments(cfg: dict[str, Any]) -> str:
    hashtag = format_hashtag(cfg.get("commentTag") or "тг звезды")
    reward = int(cfg.get("commentReward") or COMMENT_REWARD)
    photos = int(cfg.get("photosRequired") or PHOTOS_REQUIRED)
    return (
        f"<tg-emoji emoji-id='5350367217349311525'>💬</tg-emoji> <b>Комментарии</b>\n\n"
        "<tg-emoji emoji-id='5471937988944470973'>😊</tg-emoji> <b>Делайте по порядку:</b>\n"
        "<blockquote><b>1. Откройте TikTok\n"
        f'2. Найдите ролики с хештегом "<code>{hashtag}</code>"\n'
        "3. Напишите комментарий и поставьте лайк своему комментарию\n"
        "4. Сделайте скриншот своего комментария\n"
        f"5. Пришлите сюда {photos} таких фото. Одно фото - один комментарий. Каждое сразу уходит на проверку</b></blockquote>\n\n"
        "<tg-emoji emoji-id='5472410705929971383'>📖</tg-emoji> <b><i>Пример комментария:</i></b>\n"
        f"<blockquote><code>{EXAMPLE_COMMENT}</code></blockquote>\n\n"
        f"<tg-emoji emoji-id='{ICON_OK}'>✅</tg-emoji> <b>Награда: {photos} фото = {reward} кут. После проверки придут сюда.</b>"
    )


def text_videos(cfg: dict[str, Any]) -> str:
    hashtag = format_hashtag(cfg.get("videoHashtag") or "@CuteGamingBot", fallback="CuteGamingBot")
    kut = int(cfg.get("kutPerUnit") or KUT_PER_UNIT)
    per = int(cfg.get("viewsPerUnit") or 1000)
    return (
        f"<tg-emoji emoji-id='5375309569905938163'>📹</tg-emoji> <b>Видео про бота</b>\n\n"
        "<tg-emoji emoji-id='5391143319029968523'>🤙</tg-emoji> <b>Делайте по порядку:</b>\n"
        "<blockquote><b>1. Снимите ролик про бота <code>@CuteGamingBot</code>\n"
        f"2. В описании поставьте хештег <code>{hashtag}</code>\n"
        "3. Опубликуйте ролик\n"
        "4. Скопируйте ссылку и отправьте её сюда</b></blockquote>\n\n"
        "<tg-emoji emoji-id='5388591472800986666'>✌</tg-emoji> <b><i>Пример ссылки:</i></b>\n"
        "<b>1.</b> <code>" + EXAMPLE_VIDEO_SHORT + "</code>\n"
        "<b>2.</b> <code>" + EXAMPLE_VIDEO_URL + "</code>\n\n"
        f"<tg-emoji emoji-id='5326018884539553727'>🖤</tg-emoji> <b>Награда: каждые {per} просмотров = {kut} кут. Просмотры копятся сами.</b>"
    )


def text_need_nick(path: str = "", error: str = "") -> str:
    body = (
        "<tg-emoji emoji-id='5456282961999570188'>🎵</tg-emoji> <b>Напишите имя своего TikTok</b>\n\n"
        "<tg-emoji emoji-id='5339564150534200424'>🎁</tg-emoji> <b>Что сделать:</b>\n"
        "<blockquote><b>1. Откройте TikTok\n"
        "2. Скопируйте своё имя профиля\n"
        "3. Отправьте его сюда. Можно с @ или без</b></blockquote>\n\n"
        "<tg-emoji emoji-id='5255850874248399164'>🎁</tg-emoji> <b><i>Пример написания ника:</i></b>\n"
        f"<blockquote><code>{EXAMPLE_NICK}</code></blockquote>\n\n"
        f"<b>{INPUT_FOOTER}</b>"
    )
    if error:
        return f"<b>{error}</b>\n\n{body}"
    return body


def text_ask_nick(error: str = "") -> str:
    return text_need_nick(error=error)


def text_link_screen(error: str = "") -> str:
    body = (
        f"<tg-emoji emoji-id='{ICON_VIDEOS}'>📹</tg-emoji> <b>Отправьте ссылку на ролик</b>\n\n"
        "<tg-emoji emoji-id='5391143319029968523'>🤙</tg-emoji> <b>Что сделать:</b>\n"
        "<blockquote>"
        "<b>1. Откройте свой ролик в TikTok\n"
        "2. Нажмите «Поделиться» и скопируйте ссылку\n"
        "3. Отправьте ссылку сюда. Подойдёт короткая vt.tiktok.com</b>"
        "</blockquote>\n\n"
        "<tg-emoji emoji-id='5388591472800986666'>✌</tg-emoji> <b><i>Пример ссылки:</i></b>\n"
        "<b>1.</b> <code>" + EXAMPLE_VIDEO_SHORT + "</code>\n"
        "<b>2.</b> <code>" + EXAMPLE_VIDEO_URL + "</code>\n\n"
        f"<b>{INPUT_FOOTER}</b>"
    )
    if error:
        return f"<b>{error}</b>\n\n{body}"
    return body


def text_photo_wait_error(error: str, count: int = 0, needed: int = 15) -> str:
    return f"<b>{error}</b>\n\n{text_wait_photos(count, needed)}"


def text_nick_required_alert() -> str:
    return "Сначала напишите имя своего TikTok."


def text_nicks(nicks: list[str], *, locked: bool) -> str:
    if nicks:
        body = "\n".join(f"<b>{i}. <code>@{n}</code></b>" for i, n in enumerate(nicks, 1))
    else:
        body = "<i>Пока нет ни одного имени.</i>"
    extra = (
        "\n\n<i>Сейчас идёт проверка. Имя можно сменить после ответа.</i>"
        if locked
        else "\n\n<i>Можно указать до трёх имён.</i>"
    )
    return (
        f"<tg-emoji emoji-id='{ICON_NICKS}'>🎵</tg-emoji> <b>Имена аккаунтов TikTok</b>\n\n"
        f"{body}{extra}"
    )


def help_earnings_block() -> str:
    return (
        "<tg-emoji emoji-id='5456282961999570188'>🎵</tg-emoji> <b>TikTok</b>\n"
        "<blockquote><b><i>Откройте Задания, нажмите Тик ток и выберите комментарии или видео. Дальше бот покажет шаги.</i></b></blockquote>\n"
    )


def _nicks_block(nicks: list[str]) -> str:
    if not nicks:
        return ""
    lines = "\n".join(f"<code>@{n}</code>" for n in nicks)
    return f"\n\n<b><i>Имена аккаунтов:</i></b>\n{lines}"


def comments_screen_text(
    cfg: dict[str, Any],
    nicks: list[str],
    *,
    pending: bool,
    count: int,
    notice: str = "",
) -> str:
    needed = int(cfg.get("photosRequired") or PHOTOS_REQUIRED)
    if pending:
        text = (
            f"<tg-emoji emoji-id='5350367217349311525'>💬</tg-emoji> <b>Комментарии</b>\n\n"
            f"<blockquote><b>{needed} из {needed} сдано. Ждём проверку.</b>\n"
            "<i>Как ответят - куты придут сюда. Если передумали, заявку можно отозвать.</i></blockquote>"
        )
    elif count > 0:
        left = max(0, needed - int(count))
        reward = int(cfg.get("commentReward") or COMMENT_REWARD)
        text = (
            f"<tg-emoji emoji-id='5350367217349311525'>💬</tg-emoji> <b>Комментарии</b>\n\n"
            f"<blockquote><b>{count} из {needed}. Ещё {left} фото - и {reward} кут Ваши.</b>\n"
            "<i>Альбом до 10 фото. Одно фото - один комментарий.</i></blockquote>\n"
            f"{PHOTO_FOOTER}"
        )
    else:
        text = text_comments(cfg)
        text += f"\n\n{PHOTO_FOOTER}"
    if notice:
        return f"{notice}\n\n{text}"
    return text


def videos_screen_text(
    cfg: dict[str, Any],
    nicks: list[str],
    videos: list[dict[str, Any]],
    notice: str = "",
) -> str:
    body = text_videos(cfg)
    pending = [v for v in videos if v.get("status") == "pending"]
    if pending:
        body += (
            "\n\n<b>Ссылка уже на проверке</b>\n"
            "<blockquote><i>Ждём решение. Как примем - куты придут сюда. Новую ссылку можно прислать после ответа.</i></blockquote>"
        )
    else:
        body += f"\n\n<blockquote><i>Теперь отправьте ссылку на ролик следующим сообщением.</i></blockquote>\n{INPUT_FOOTER}"
    if notice:
        return f"{notice}\n\n{body}"
    return body


def text_wait_photos(count: int = 0, needed: int = 15) -> str:
    if count > 0:
        left = max(0, int(needed) - int(count))
        return (
            "<b>Отправьте следующее фото</b>\n"
            f"<blockquote><b>Уже на проверке {count} из {needed}. Осталось {left}.</b>\n"
            "<i>Альбом до 10 фото. Если не хватает - пришлите ещё одним альбомом.</i></blockquote>\n"
            f"{PHOTO_FOOTER}"
        )
    return (
        "<b>Отправьте скриншоты комментариев</b>\n"
        "<blockquote>"
        "<b>1. Сделайте скриншот комментария\n"
        "2. Отправьте фото сюда\n"
        "3. Можно альбомом. Telegram берёт до 10 фото за раз</b>"
        "</blockquote>\n"
        f"{PHOTO_FOOTER}"
    )


def text_wait_expired() -> str:
    return (
        "<b>Срок ввода истёк.</b>\n"
        "<blockquote><b><i>Попробуйте повторно загрузить доказательства.</i></b></blockquote>\n"
        "<blockquote>"
        "<b>1. Откройте Задания → Тик ток\n"
        "2. Выберите комментарии или видео\n"
        "3. Загрузите доказательства ещё раз</b>"
        "</blockquote>\n\n"
        "<b><i>Уже отправленные фото остаются на проверке.</i></b>"
    )


def text_wait_link() -> str:
    return (
        "<b>Отправьте ссылку на ролик</b>\n"
        "<blockquote>"
        "<b>1. Откройте ролик в TikTok\n"
        "2. Нажмите «Поделиться» и скопируйте ссылку\n"
        "3. Отправьте ссылку сюда. Можно vt.tiktok.com</b>"
        "</blockquote>\n"
        "<b><i>Пример:</i></b>\n"
        "<b>1.</b> <code>" + EXAMPLE_VIDEO_SHORT + "</code>\n"
        "<b>2.</b> <code>" + EXAMPLE_VIDEO_URL + "</code>\n"
        f"{INPUT_FOOTER}"
    )


def text_press_send_photos() -> str:
    return (
        "<b>Сначала нажмите кнопку.</b>\n"
        "<blockquote>"
        "<b>1. Нажмите кнопку под сообщением\n"
        "2. Потом отправьте фото ответом</b>"
        "</blockquote>\n"
        f"{CANCEL_HINT}"
    )


def text_press_send_link() -> str:
    return (
        "<b>Сначала нажмите кнопку.</b>\n"
        "<blockquote>"
        "<b>1. Нажмите кнопку под сообщением\n"
        "2. Потом отправьте ссылку ответом</b>"
        "</blockquote>\n"
        f"{CANCEL_HINT}"
    )


def text_press_bind_nick() -> str:
    return (
        "<b>Сначала нажмите кнопку.</b>\n"
        "<blockquote>"
        "<b>1. Нажмите кнопку под сообщением\n"
        "2. Потом напишите имя своего TikTok</b>"
        "</blockquote>\n"
        f"{CANCEL_HINT}"
    )


def collect_text(count: int, needed: int, nicks: list[str] | None = None) -> str:
    bound = ""
    if nicks:
        bound = "\n<i>Проверяем:</i> " + ", ".join(f"<b>@{n}</b>" for n in nicks)
    if count >= needed:
        return f"<b>{needed} из {needed}. Ждём решение.</b>{bound}"
    left = needed - count
    return (
        f"<b>На проверке {count} из {needed}. <i>Ещё {left}.</i></b>{bound}"
    )


def text_photos_on_review(
    added: int,
    count: int,
    needed: int,
    nicks: list[str] | None = None,
) -> str:
    added = max(0, int(added))
    count = int(count)
    needed = int(needed)
    bound = ""
    if nicks:
        bound = "\n<i>Ники аккаунтов:</i> " + ", ".join(f"<b>@{n}</b>" for n in nicks)
    if added <= 0 and count >= needed:
        return f"<b>{needed} из {needed}. Ждём решение.</b>"
    word = ru_screenshot_word(added)
    verb = ru_gone_verb(added)
    if count >= needed:
        return (
            f"<b>{added} {word} {verb} на проверку.</b>\n"
            f"<blockquote><b>{needed} из {needed}. Ждём решение.</b>{bound}</blockquote>"
        )
    left = needed - count
    return with_input_footer(
        f"<b>{added} {word} {verb} на проверку.</b>\n"
        f"<blockquote><b>Сейчас {count} из {needed}. Осталось {left}.</b>\n"
        "<i>Отправьте следующее фото. Можно альбомом.</i>"
        f"{bound}</blockquote>"
    )


def text_case_withdrawn() -> str:
    return (
        f"<tg-emoji emoji-id='{ICON_OK}'>✅</tg-emoji> <b>Заявку отозвали</b>\n"
        "<blockquote><i>Серия сброшена. Можно собрать новую.</i></blockquote>"
    )


def text_done_nick_added(nick: str, nicks: list[str]) -> str:
    left = max(0, MAX_NICKS - len(nicks))
    extra = f"Можно добавить ещё {left}." if left else "Лимит имён заполнен."
    return (
        f"<tg-emoji emoji-id='{ICON_OK}'>✅</tg-emoji> <b>Имя аккаунта записано</b>\n\n"
        f"<blockquote><b><code>@{escape(nick)}</code></b>\n"
        f"<i>{extra} Теперь можно сдавать комментарии и видео.</i></blockquote>"
    )


def text_done_nick_changed(old: str, new: str) -> str:
    return (
        f"<tg-emoji emoji-id='{ICON_OK}'>✅</tg-emoji> <b>Имя аккаунта изменено</b>\n\n"
        f"<blockquote><b>Было: <code>@{escape(old)}</code>\n"
        f"Стало: <code>@{escape(new)}</code></b></blockquote>"
    )


def text_done_video_sent(url: str) -> str:
    return (
        f"<tg-emoji emoji-id='{ICON_VIDEOS}'>📹</tg-emoji> <b>Ссылка принята</b>\n\n"
        f"<blockquote><b><code>{escape(url)}</code></b>\n"
        "<i>Ролик на проверке. Как примем - куты за просмотры придут сюда.</i></blockquote>"
    )


def text_done_recheck(item: dict[str, Any]) -> str:
    return (
        f"<tg-emoji emoji-id='{ICON_OK}'>✅</tg-emoji> <b>Перепроверку запросили</b>\n\n"
        f"<blockquote><b><code>{escape(str(item.get('url') or ''))}</code></b>\n"
        "<i>Ролик снова в очереди. Напишем, когда посчитаем новые просмотры.</i></blockquote>"
    )


def text_done_undo(count: int, needed: int) -> str:
    return (
        f"<tg-emoji emoji-id='{ICON_CAM}'>📸</tg-emoji> <b>Последний скрин убрали</b>\n"
        f"<blockquote><b>Сейчас {count} из {needed}.</b></blockquote>"
    )


def _fmt_num(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


def video_status_phrase(item: dict[str, Any]) -> str:
    status = item.get("status")
    if status == "pending":
        return "на проверке"
    if status == "rejected":
        return "отклонено"
    if item.get("recheckPending"):
        return "перепроверка"
    return "принято"


def text_my_videos(videos: list[dict[str, Any]], page: int = 0) -> str:
    total = len(videos)
    if not total:
        return (
            f"<tg-emoji emoji-id='{ICON_MY_VIDEOS}'>🖤</tg-emoji> <b>Ваши ролики</b>\n\n"
            "<i>Пока нет ни одного ролика.</i>\n"
            "<blockquote><i>Нажмите «Новая ссылка» и отправьте ролик. Каждые 1.000 просмотров приносят куты.</i></blockquote>"
        )
    page, pages = _video_pages(total, page)
    pending = sum(1 for v in videos if v.get("status") == "pending")
    live = sum(1 for v in videos if v.get("status") == "live")
    paid = sum(int(v.get("paidKut") or 0) for v in videos)
    return (
        f"<tg-emoji emoji-id='{ICON_MY_VIDEOS}'>🖤</tg-emoji> <b>Ваши ролики</b>\n\n"
        f"<blockquote><b>Всего: {total} · принято: {live} · на проверке: {pending}\n"
        f"Выплачено: {_fmt_num(paid)} кут</b>\n"
        f"<i>Страница {page + 1} из {pages}. Нажмите ролик - там статус и выплата.</i></blockquote>"
    )


def text_video_card(item: dict[str, Any]) -> str:
    status = video_status_phrase(item)
    url = escape(str(item.get("url") or ""))
    views = int(item.get("lastViews") or 0)
    paid = int(item.get("paidKut") or 0)
    unit = int(item.get("kutPerUnit") or KUT_PER_UNIT)
    thousands = int(item.get("lastPaidThousands") or 0)
    lines = [
        f"<tg-emoji emoji-id='{ICON_VIDEOS}'>📹</tg-emoji> <b>Ролик #{item.get('id')}</b>",
        "",
        f"<b>Статус:</b> {status}",
        f"<blockquote><code>{url}</code></blockquote>",
    ]
    if item.get("status") == "live" or paid or views:
        pay_line = f"<b>Выплата:</b> +{_fmt_num(paid)} кут"
        if thousands:
            pay_line += f"\n<i>{_fmt_num(thousands)} тыс. × {unit} кут</i>"
        elif item.get("status") == "live":
            pay_line += "\n<i>Пока меньше 1.000. Куты появятся, когда наберётся тысяча.</i>"
        lines.append(
            "<blockquote>"
            f"<b>Просмотры:</b> {_fmt_num(views)}\n"
            f"{pay_line}"
            "</blockquote>"
        )
    reasons = [str(r).strip() for r in (item.get("rejectReasons") or []) if str(r).strip()]
    if item.get("status") == "rejected":
        reason_text = "\n".join(f"· {escape(r)}" for r in reasons) or "· Ролик не приняли"
        lines.append(f"<blockquote><b>Почему отклонили</b>\n{reason_text}</blockquote>")
    if item.get("status") == "pending":
        lines.append("<blockquote><i>Ждём решение. Напишем сюда.</i></blockquote>")
    elif item.get("recheckPending"):
        lines.append("<blockquote><i>Перепроверка уже в очереди.</i></blockquote>")
    elif item.get("status") == "live" and item.get("recheckReady") is False:
        wait = item.get("recheckWaitText") or "ещё рано"
        lines.append(f"<blockquote><i>Следующая проверка {wait}.</i></blockquote>")
    elif item.get("status") == "live":
        lines.append("<blockquote><i>Можно запросить перепроверку просмотров.</i></blockquote>")
    return "\n".join(lines)


async def download_and_hash(bot, file_id: str) -> dict[str, str]:
    empty = {"ahash": "", "dhash": "", "phash": "", "md5": ""}
    for attempt in range(2):
        try:
            buf = BytesIO()
            await bot.download(file_id, destination=buf)
            hashes = hashes_from_image_bytes(buf.getvalue())
            if hashes.get("phash") or hashes.get("ahash"):
                return hashes
        except Exception:
            log.exception("tiktok photo hash failed attempt=%s", attempt + 1)
    return empty


def pick_thumb_file_id(sizes) -> str:
    if not sizes:
        return ""
    return min(sizes, key=lambda s: abs((getattr(s, "width", 0) or 0) - 320)).file_id


async def add_photo(
    user_id: int,
    file_id: str,
    hashes: dict[str, str],
    thumb_file_id: str = "",
) -> dict[str, Any]:
    nicks = await require_nicks(user_id)
    cfg = await get_settings()
    needed = int(cfg["photosRequired"])
    photo = {"fileId": file_id, "thumbFileId": thumb_file_id or "", **hashes}
    pool = _pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, photos FROM tiktok_comment_cases
                WHERE user_id = $1 AND status = 'pending'
                FOR UPDATE
                """,
                int(user_id),
            )
            if row:
                existing = _json(row["photos"]) or []
                if not isinstance(existing, list):
                    existing = []
                result = append_case_photos(existing, [photo], needed)
                if result["added"]:
                    await conn.execute(
                        "UPDATE tiktok_comment_cases SET photos = $2::jsonb WHERE id = $1 AND status = 'pending'",
                        int(row["id"]),
                        json.dumps(result["photos"], ensure_ascii=False),
                    )
                case_id = int(row["id"])
            else:
                result = append_case_photos([], [photo], needed)
                case_id = int(
                    await conn.fetchval(
                        """
                        INSERT INTO tiktok_comment_cases (user_id, status, photos, nick_snapshot)
                        VALUES ($1, 'pending', $2::jsonb, $3::jsonb)
                        RETURNING id
                        """,
                        int(user_id),
                        json.dumps(result["photos"], ensure_ascii=False),
                        json.dumps(nicks, ensure_ascii=False),
                    )
                )
    next_mode = MODE_COMMENT_DONE if result["complete"] else MODE_WAIT_PHOTOS
    session = await get_session(user_id)
    extra = dict(session.get("extra") or {})
    extra["caseId"] = case_id
    extra["after"] = extra.get("after") or "comments"
    await set_session(user_id, next_mode, extra)
    return {
        "count": result["received"],
        "needed": result["needed"],
        "added": result["added"],
        "full": result["complete"],
        "complete": result["complete"],
        "caseId": case_id,
    }


async def undo_photo(user_id: int) -> dict[str, Any]:
    cfg = await get_settings()
    needed = int(cfg["photosRequired"])
    pool = _pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, photos, reviewed_at FROM tiktok_comment_cases
                WHERE user_id = $1 AND status = 'pending'
                FOR UPDATE
                """,
                int(user_id),
            )
            if not row:
                session = await get_session(user_id)
                extra = dict(session.get("extra") or {})
                extra.pop("caseId", None)
                keep = MODE_WAIT_PHOTOS if session.get("mode") in PHOTO_WAIT_MODES else MODE_COMMENTS
                await set_session(user_id, keep, extra)
                return {"count": 0, "needed": needed, "complete": False, "deleted": False}
            if row["reviewed_at"]:
                raise ValueError("По этой серии уже есть решение.")
            photos = _json(row["photos"]) or []
            if not isinstance(photos, list):
                photos = []
            if photos:
                photos.pop()
            if not photos:
                await conn.execute(
                    "DELETE FROM tiktok_comment_cases WHERE id = $1 AND status = 'pending'",
                    int(row["id"]),
                )
                session = await get_session(user_id)
                extra = dict(session.get("extra") or {})
                extra.pop("caseId", None)
                keep = MODE_WAIT_PHOTOS if session.get("mode") in PHOTO_WAIT_MODES else MODE_COMMENTS
                await set_session(user_id, keep, extra)
                return {"count": 0, "needed": needed, "complete": False, "deleted": True}
            await conn.execute(
                "UPDATE tiktok_comment_cases SET photos = $2::jsonb WHERE id = $1 AND status = 'pending'",
                int(row["id"]),
                json.dumps(photos, ensure_ascii=False),
            )
            session = await get_session(user_id)
            extra = dict(session.get("extra") or {})
            extra["caseId"] = int(row["id"])
            keep = MODE_WAIT_PHOTOS if session.get("mode") in PHOTO_WAIT_MODES else MODE_COMMENTS
            await set_session(user_id, keep, extra)
            progress = comment_progress(photos, needed)
            return {
                "count": progress["received"],
                "needed": progress["needed"],
                "complete": progress["complete"],
                "deleted": False,
            }


async def withdraw_comment_case(user_id: int) -> dict[str, Any]:
    await ensure_schema()
    pool = _pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, photos, reviewed_at FROM tiktok_comment_cases
                WHERE user_id = $1 AND status = 'pending'
                FOR UPDATE
                """,
                int(user_id),
            )
            if not row:
                raise ValueError("Открытой заявки нет.")
            if row["reviewed_at"]:
                raise ValueError("По этой серии уже есть решение.")
            await conn.execute(
                """
                UPDATE tiktok_comment_cases
                SET status = 'withdrawn', reviewed_at = NOW(), reject_text = $2
                WHERE id = $1 AND status = 'pending'
                """,
                int(row["id"]),
                "Игрок отозвал заявку",
            )
    clear_wait(user_id)
    await set_session(user_id, MODE_WAIT_PHOTOS, {"after": "comments"})
    return {"ok": True, "id": int(row["id"])}


async def session_mode(user_id: int) -> str:
    return str((await get_session(user_id)).get("mode") or "")


async def is_collecting(user_id: int) -> bool:
    if not await list_nicks(user_id):
        return False
    if is_awaiting_photos(user_id):
        case = await get_pending_comment_case(user_id)
        return not (case and case["complete"])
    if (await session_mode(user_id)) not in PHOTO_WAIT_MODES:
        return False
    case = await get_pending_comment_case(user_id)
    if case and case["complete"]:
        return False
    return True


async def is_waiting_nick(user_id: int) -> bool:
    rec = get_wait(user_id)
    if rec and rec.get("kind") in {WAIT_NICK, WAIT_NICK_EDIT}:
        return True
    return (await session_mode(user_id)) in NICK_WAIT_MODES


async def is_waiting_link(user_id: int) -> bool:
    rec = get_wait(user_id)
    if rec and rec.get("kind") == WAIT_LINK:
        return True
    return (await session_mode(user_id)) == MODE_WAIT_LINK


async def is_comments_idle(user_id: int) -> bool:
    return (await session_mode(user_id)) in {MODE_COMMENTS, MODE_NEED_NICK, MODE_COMMENT_DONE}


async def is_videos_idle(user_id: int) -> bool:
    return (await session_mode(user_id)) == MODE_VIDEOS


def looks_like_tiktok_url(raw: str) -> bool:
    try:
        parse_tiktok_url(raw)
        return True
    except ValueError:
        return False


def message_link_text(message: Any) -> str:
    text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
    for bucket in (getattr(message, "entities", None), getattr(message, "caption_entities", None)):
        for ent in bucket or []:
            url = getattr(ent, "url", None)
            if url:
                return str(url).strip()
    return text
