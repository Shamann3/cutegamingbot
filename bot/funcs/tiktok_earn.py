# -*- coding: utf-8 -*-
"""TikTok-заработок в боте: тексты, ники, набор скринов и ссылок."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
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
)

log = logging.getLogger("tiktok_earn")

TT_HUB = "tt:hub"
TT_COMMENTS = "tt:comments"
TT_VIDEOS = "tt:videos"
TT_NICKS = "tt:nicks"
TT_NICK_ADD = "tt:nick_add"
TT_NICK_EDIT = "tt:nick_edit"
TT_NICK_PICK = "tt:nick_pick:"
TT_SEND_PHOTOS = "tt:send_photos"
TT_SEND_LINK = "tt:send_link"
TT_CANCEL_COLLECT = "tt:cancel_collect"
TT_DONE_WAIT = "tt:done_wait"
TT_SUBMIT_PHOTOS = "tt:submit_photos"
TT_UNDO_PHOTO = "tt:undo_photo"
TT_RECHECK = "tt:recheck:"
TT_BACK_TASKS = "questions_stars"

ICON_TT = "5456282961999570188"
ICON_BACK = "5226660202035554522"
ICON_OK = "5224257782013769471"
ICON_CAM = "5373098002641805602"
ICON_COMMENTS = "5350367217349311525"
ICON_VIDEOS = "5375309569905938163"

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
EXAMPLE_COMMENT = "Как по мне @CuteGamingBot намного лучше для заработка звезд"
EXAMPLE_VIDEO_URL = "https://www.tiktok.com/@cuteplayer/video/7123456789012345678"

# Как user_gift["awaiting_recipient"] у подарка другу: флаг в памяти,
# чтобы @dp.message(lambda ...) поймал следующее сообщение до общего F.text.
WAIT_NICK = "nick"
WAIT_NICK_EDIT = "nick_edit"
WAIT_LINK = "link"
WAIT_PHOTOS = "photos"
TEXT_WAIT_KINDS = frozenset({WAIT_NICK, WAIT_NICK_EDIT, WAIT_LINK})
CANCEL_WORDS = frozenset({"назад", "завершить"})
WAIT_TTL_SECONDS = 300
CANCEL_HINT = "<i>Напишите «Назад» или «Завершить», чтобы выйти.</i>"
REPLY_HINT = "<i>Ответьте на это сообщение. На ответ есть 5 минут.</i>"
INPUT_FOOTER = f"{REPLY_HINT}\n{CANCEL_HINT}"
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


def _fresh_expires_iso() -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=WAIT_TTL_SECONDS)).isoformat()


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
        rec["expires_at"] = parsed.isoformat() if parsed else _fresh_expires_iso()
    else:
        rec["expires_at"] = _fresh_expires_iso()
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
    raw = (getattr(message, "text", None) or "").strip()
    if rec and rec.get("kind") == WAIT_PHOTOS and is_cancel_input(raw):
        return _gift_style_or_fallback(message, rec)
    if not handler_would_accept_text(message.from_user.id, raw):
        return False
    if not rec:
        return False
    return _gift_style_or_fallback(message, rec)


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
    return _gift_style_or_fallback(message, rec)


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


async def submit_video(user_id: int, raw_url: str) -> None:
    await ensure_schema()
    await require_nicks(user_id)
    parsed = parse_tiktok_url(raw_url)
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
        SELECT id, url, status, last_views, last_checked_at, recheck_requested_at, created_at
        FROM tiktok_videos WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        int(user_id),
    )
    out = []
    for r in rows:
        state = video_recheck_state(r["last_checked_at"], days)
        out.append(
            {
                "id": int(r["id"]),
                "url": r["url"],
                "status": r["status"],
                "lastViews": int(r["last_views"] or 0),
                "recheckPending": bool(r["recheck_requested_at"]),
                "lastCheckedAt": r["last_checked_at"],
                "recheckReady": state["ready"],
                "recheckWaitText": state["waitText"],
            }
        )
    return out


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


def hub_keyboard() -> InlineKeyboardMarkup:
    return _kb(
        [
            [_btn("Комментарии", TT_COMMENTS, ICON_COMMENTS)],
            [_btn("Видео о боте", TT_VIDEOS, ICON_VIDEOS)],
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
    rows = []
    if complete or count >= needed:
        rows.append([_btn("Уже на проверке", TT_SUBMIT_PHOTOS, ICON_OK)])
    if count > 0 and not (complete or count >= needed):
        rows.append([_btn("Убрать последнее", TT_UNDO_PHOTO)])
    elif count > 0 and (complete or count >= needed):
        rows.append([_btn("Убрать последнее", TT_UNDO_PHOTO)])
    rows.append([_btn("Мои ники", TT_NICKS)])
    rows.append([_btn("Назад", TT_HUB, ICON_BACK)])
    return _kb(rows)


def videos_keyboard(
    videos: list[dict] | None = None,
    *,
    waiting: bool = False,
    can_send: bool = True,
) -> InlineKeyboardMarkup:
    rows = []
    for item in videos or []:
        if item.get("status") != "live" or item.get("recheckPending"):
            continue
        if item.get("recheckReady") is False:
            continue
        rows.append([_btn(f"Проверить просмотры · #{item['id']}", f"{TT_RECHECK}{item['id']}")])
    rows.append([_btn("Мои ники", TT_NICKS)])
    rows.append([_btn("Назад", TT_HUB, ICON_BACK)])
    return _kb(rows)


def nicks_keyboard(nicks: list[str], *, locked: bool, origin: str = "hub") -> InlineKeyboardMarkup:
    rows = []
    if not locked:
        rows.append([_btn("Написать имя TikTok", TT_NICK_ADD)])
        if nicks:
            rows.append([_btn("Изменить", TT_NICK_EDIT)])
    back = TT_COMMENTS if origin == "comments" else TT_VIDEOS if origin == "videos" else TT_HUB
    rows.append([_btn("Назад", back, ICON_BACK)])
    return _kb(rows)


def nick_pick_keyboard(nicks: list[str]) -> InlineKeyboardMarkup:
    rows = [[_btn(f"@{n}", f"{TT_NICK_PICK}{n}")] for n in nicks]
    rows.append([_btn("Назад", TT_NICKS, ICON_BACK)])
    return _kb(rows)


def collect_keyboard(count: int, needed: int) -> InlineKeyboardMarkup:
    return comments_keyboard(can_send=True, count=count, needed=needed, waiting=True)


def bind_keyboard(*, waiting: bool = False) -> InlineKeyboardMarkup:
    return _kb([[_btn("Назад", TT_HUB, ICON_BACK)]])


def text_hub(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or {}
    reward = int(cfg.get("commentReward") or COMMENT_REWARD)
    kut = int(cfg.get("kutPerUnit") or KUT_PER_UNIT)
    photos = int(cfg.get("photosRequired") or PHOTOS_REQUIRED)
    return (
        "<tg-emoji emoji-id='5456282961999570188'>🎵</tg-emoji> <b>Тик ток</b>\n\n"
        "<i>Выберите одно.</i>\n"
        f"<i>Комментарии: {photos} фото -</i> <b>{reward} кут</b><i>.</i>\n"
        f"<i>Видео: 1000 просмотров -</i> <b>{kut} кут</b><i>.</i>"
    )


def text_comments(cfg: dict[str, Any]) -> str:
    tag = cfg.get("commentTag") or "тг звезды"
    reward = int(cfg.get("commentReward") or COMMENT_REWARD)
    photos = int(cfg.get("photosRequired") or PHOTOS_REQUIRED)
    return (
        f"<tg-emoji emoji-id='{ICON_COMMENTS}'>💬</tg-emoji> <b>Комментарии</b>\n\n"
        f"<i>Напишите {photos} комментариев с @CuteGamingBot. Один скрин - один комментарий.</i>\n"
        f"<i>Тег ролика:</i> <code>{tag}</code>\n\n"
        "<i>Пример:</i>\n"
        f"<code>{EXAMPLE_COMMENT}</code>\n\n"
        f"<b>{photos} фото = {reward} кут</b>"
    )


def text_videos(cfg: dict[str, Any]) -> str:
    hashtag = cfg.get("videoHashtag") or "@CuteGamingBot"
    kut = int(cfg.get("kutPerUnit") or KUT_PER_UNIT)
    per = int(cfg.get("viewsPerUnit") or 1000)
    return (
        f"<tg-emoji emoji-id='{ICON_VIDEOS}'>📹</tg-emoji> <b>Видео</b>\n\n"
        f"<i>Снимите ролик про бота. Поставьте {hashtag}.</i>\n\n"
        "<i>Пример ссылки:</i>\n"
        f"<code>{EXAMPLE_VIDEO_URL}</code>\n\n"
        f"<b>{per} просмотров = {kut} кут</b>"
    )


def text_need_nick(path: str = "", error: str = "") -> str:
    body = (
        "<tg-emoji emoji-id='5456282961999570188'>🎵</tg-emoji> <b>Напишите имя своего TikTok</b>\n\n"
        "<i>Как в приложении. С @ или без.</i>\n\n"
        "<i>Пример:</i>\n"
        f"<code>{EXAMPLE_NICK}</code>\n\n"
        f"{INPUT_FOOTER}"
    )
    if error:
        return f"<b>{error}</b>\n\n{body}"
    return body


def text_ask_nick(error: str = "") -> str:
    return text_need_nick(error=error)


def text_link_screen(error: str = "") -> str:
    body = (
        f"<tg-emoji emoji-id='{ICON_VIDEOS}'>📹</tg-emoji> <b>Видео</b>\n\n"
        "<i>Отправьте ссылку на ролик.</i>\n\n"
        "<i>Пример:</i>\n"
        f"<code>{EXAMPLE_VIDEO_URL}</code>\n\n"
        f"{INPUT_FOOTER}"
    )
    if error:
        return f"<b>{error}</b>\n\n{body}"
    return body


def text_photo_wait_error(error: str, count: int = 0, needed: int = 15) -> str:
    return f"<b>{error}</b>\n\n{text_wait_photos(count, needed)}"


def text_nick_required_alert() -> str:
    return "Сначала напишите имя своего TikTok."


def text_nicks(nicks: list[str], *, locked: bool) -> str:
    body = "\n".join(f"<code>@{n}</code>" for n in nicks) if nicks else "<i>Пока пусто.</i>"
    extra = (
        "\n\n<i>Сейчас проверка. Имя можно сменить после ответа.</i>"
        if locked
        else "\n\n<i>До трёх имён.</i>"
    )
    return f"<b>Ваши имена TikTok</b>\n\n{body}{extra}"


def help_earnings_block() -> str:
    return (
        "<tg-emoji emoji-id='5456282961999570188'>🎵</tg-emoji> <b>TikTok</b>\n"
        "<i>Задания → Тик ток → комментарии или видео.</i>\n"
    )


def _nicks_block(nicks: list[str]) -> str:
    if not nicks:
        return ""
    lines = "\n".join(f"<code>@{n}</code>" for n in nicks)
    return f"\n\n<i>Имена:</i>\n{lines}"


def comments_screen_text(
    cfg: dict[str, Any],
    nicks: list[str],
    *,
    pending: bool,
    count: int,
) -> str:
    needed = int(cfg.get("photosRequired") or PHOTOS_REQUIRED)
    body = text_comments(cfg)
    body += _nicks_block(nicks)
    if pending:
        body += f"\n\n<b>{needed} из {needed}. Ждём решение.</b>"
        return body
    if count > 0:
        body += "\n\n" + collect_text(count, needed)
    body += f"\n\n<i>Отправьте фото ответом на это сообщение. Альбомом или по одному.</i>\n{INPUT_FOOTER}"
    return body


def videos_screen_text(
    cfg: dict[str, Any],
    nicks: list[str],
    videos: list[dict[str, Any]],
) -> str:
    body = text_videos(cfg)
    body += _nicks_block(nicks)
    pending = [v for v in videos if v.get("status") == "pending"]
    live = [v for v in videos if v.get("status") == "live"]
    if pending:
        body += "\n\n<b>Ссылка на проверке.</b>"
    if live:
        body += "\n\n<b>Ваши ролики</b>"
        for item in live[:5]:
            if item.get("recheckPending"):
                mark = " · ждём перепроверку"
            elif item.get("recheckReady") is False:
                mark = f" · учтено {item['lastViews']} · {item.get('recheckWaitText') or 'ещё рано'}"
            else:
                mark = f" · учтено {item['lastViews']} · можно проверить"
            body += f"\n<code>{item['url']}</code>\n<i>{mark}</i>"
    if pending:
        return body
    body += f"\n\n<i>Отправьте ссылку на ролик ответом на это сообщение.</i>\n{INPUT_FOOTER}"
    return body


def text_wait_photos(count: int = 0, needed: int = 15) -> str:
    if count > 0:
        left = max(0, int(needed) - int(count))
        return (
            "<b>Сейчас отправьте фото</b>\n"
            f"<i>На проверке {count} из {needed}. Ещё {left}.</i>\n"
            f"{INPUT_FOOTER}"
        )
    return (
        "<b>Сейчас отправьте фото</b>\n"
        "<i>Альбомом или по одному. Ответьте на это сообщение.</i>\n"
        f"{INPUT_FOOTER}"
    )


def text_wait_expired() -> str:
    return (
        "<b>Срок ввода истёк.</b>\n"
        "<i>Попробуйте повторно загрузить доказательства.</i>\n"
        "<i>Откройте комментарии или видео и начните снова.</i>\n"
        "<i>Уже отправленные фото остаются на проверке.</i>"
    )


def text_wait_link() -> str:
    return (
        "<b>Сейчас отправьте ссылку</b>\n\n"
        "<i>Пример:</i>\n"
        f"<code>{EXAMPLE_VIDEO_URL}</code>\n\n"
        f"{INPUT_FOOTER}"
    )


def text_press_send_photos() -> str:
    return (
        "<b>Сначала нажмите кнопку.</b>\n"
        "<i>Потом отправьте фото ответом на сообщение.</i>\n"
        f"{CANCEL_HINT}"
    )


def text_press_send_link() -> str:
    return (
        "<b>Сначала нажмите кнопку.</b>\n"
        "<i>Потом отправьте ссылку ответом на сообщение.</i>\n"
        f"{CANCEL_HINT}"
    )


def text_press_bind_nick() -> str:
    return (
        "<b>Сначала нажмите кнопку.</b>\n"
        "<i>Потом напишите имя своего TikTok.</i>\n"
        f"{CANCEL_HINT}"
    )


def collect_text(count: int, needed: int, nicks: list[str] | None = None) -> str:
    bound = ""
    if nicks:
        bound = "\n<i>Проверяем:</i> " + ", ".join(f"<b>@{n}</b>" for n in nicks)
    if count >= needed:
        return f"<b>{needed} из {needed}. Ждём решение.</b>{bound}"
    left = needed - count
    return f"<b>На проверке {count} из {needed}.</b> <i>Ещё {left}.</i>{bound}"


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
        bound = "\n<i>Ники:</i> " + ", ".join(f"<b>@{n}</b>" for n in nicks)
    if added <= 0 and count >= needed:
        return f"<b>{needed} из {needed}. Ждём решение.</b>"
    word = ru_screenshot_word(added)
    verb = ru_gone_verb(added)
    if count >= needed:
        return (
            f"<b>{added} {word} {verb} на проверку.</b>\n"
            f"<b>{needed} из {needed}. Ждём решение.</b>{bound}"
        )
    left = needed - count
    return with_input_footer(
        f"<b>{added} {word} {verb} на проверку.</b>\n"
        f"<i>Сейчас {count} из {needed}. Ещё {left}. Отправьте следующее фото ответом.</i>{bound}"
    )


async def download_and_hash(bot, file_id: str) -> dict[str, str]:
    try:
        buf = BytesIO()
        await bot.download(file_id, destination=buf)
        return hashes_from_image_bytes(buf.getvalue())
    except Exception:
        log.exception("tiktok photo hash failed")
        return {"ahash": "", "dhash": "", "phash": "", "md5": ""}


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
