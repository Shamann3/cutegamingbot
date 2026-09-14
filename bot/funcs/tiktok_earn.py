# -*- coding: utf-8 -*-
"""TikTok-заработок в боте: тексты, ники, набор скринов и ссылок."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
NICK_WAIT_MODES = frozenset({MODE_WAIT_NICK, MODE_WAIT_NICK_EDIT})
EXAMPLE_NICK = "@cuteplayer"
EXAMPLE_COMMENT = "Как по мне @CuteGamingBot намного лучше для заработка звезд"
EXAMPLE_VIDEO_URL = "https://www.tiktok.com/@cuteplayer/video/7123456789012345678"

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
        raise ValueError("Сначала укажите свой ник в TikTok. Без него скриншоты принять нельзя.")
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
    await set_session(user_id, "", {})


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
            [_btn("Мои ники", TT_NICKS)],
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
        if count > 0:
            rows.append([_btn("Убрать последнее", TT_UNDO_PHOTO)])
    elif waiting:
        rows.append([_btn("Не сейчас", TT_CANCEL_COLLECT, ICON_BACK)])
        if count > 0:
            rows.append([_btn("Убрать последнее", TT_UNDO_PHOTO)])
            rows.append([_btn("Готово", TT_DONE_WAIT, ICON_OK)])
    elif can_send:
        rows.append([_btn("Отправить скриншоты", TT_SEND_PHOTOS, ICON_CAM)])
        if count > 0:
            rows.append([_btn("Убрать последнее", TT_UNDO_PHOTO)])
    rows.append([_btn("Мои ники", TT_NICKS)])
    rows.append([_btn("К выбору", TT_HUB, ICON_BACK)])
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
    if waiting:
        rows.append([_btn("Не сейчас", TT_CANCEL_COLLECT, ICON_BACK)])
    elif can_send:
        rows.append([_btn("Отправить ссылку", TT_SEND_LINK, ICON_VIDEOS)])
    rows.append([_btn("Мои ники", TT_NICKS)])
    rows.append([_btn("К выбору", TT_HUB, ICON_BACK)])
    return _kb(rows)


def nicks_keyboard(nicks: list[str], *, locked: bool, origin: str = "hub") -> InlineKeyboardMarkup:
    rows = []
    if not locked:
        rows.append([_btn("Указать имя профиля", TT_NICK_ADD)])
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
    if waiting:
        return _kb(
            [
                [_btn("Не сейчас", TT_CANCEL_COLLECT, ICON_BACK)],
                [_btn("К выбору", TT_HUB, ICON_BACK)],
            ]
        )
    return _kb(
        [
            [_btn("Указать имя профиля", TT_NICK_ADD)],
            [_btn("К выбору", TT_HUB, ICON_BACK)],
        ]
    )


def text_hub(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or {}
    reward = int(cfg.get("commentReward") or COMMENT_REWARD)
    kut = int(cfg.get("kutPerUnit") or KUT_PER_UNIT)
    photos = int(cfg.get("photosRequired") or PHOTOS_REQUIRED)
    return (
        "<tg-emoji emoji-id='5456282961999570188'>🎵</tg-emoji> <b>Тик ток</b>\n\n"
        "<i>Выберите, чем хотите заняться прямо сейчас.</i>\n\n"
        f"<b>Комментарии</b>\n"
        f"<i>Напишите {photos} живых комментариев и пришлите скрины. За принятую серию -</i> "
        f"<b>{reward} кут</b><i>.</i>\n\n"
        f"<b>Видео о боте</b>\n"
        f"<i>Снимите ролик про @CuteGamingBot. За каждые 1000 просмотров -</i> "
        f"<b>{kut} кут</b><i>.</i>"
    )


def text_comments(cfg: dict[str, Any]) -> str:
    tag = cfg.get("commentTag") or "тг звезды"
    reward = int(cfg.get("commentReward") or COMMENT_REWARD)
    photos = int(cfg.get("photosRequired") or PHOTOS_REQUIRED)
    return (
        f"<tg-emoji emoji-id='{ICON_COMMENTS}'>💬</tg-emoji> <b>Комментарии в TikTok</b>\n\n"
        f"<i>Найдите ролики с тегом ниже. Напишите {photos} своих комментариев.</i>\n"
        f"<i>Поставьте лайк на каждый. Один комментарий - один скрин.</i>\n\n"
        "<b>Как это выглядит</b>\n"
        "<i>Тег ролика:</i>\n"
        f"<code>{tag}</code>\n"
        "<i>Комментарий:</i>\n"
        f"<code>{EXAMPLE_COMMENT}</code>\n"
        "<i>На скрине - Ваш комментарий и лайк на нём.</i>\n\n"
        f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> "
        f"<b>За полную принятую серию - {reward} кут.</b>\n"
        f"<i>Нажмите «Отправить скриншоты», затем пришлите кадры.</i>\n"
        f"<i>Награду начислим только за {photos} скринов.</i>"
    )


def text_videos(cfg: dict[str, Any]) -> str:
    hashtag = cfg.get("videoHashtag") or "@CuteGamingBot"
    kut = int(cfg.get("kutPerUnit") or KUT_PER_UNIT)
    per = int(cfg.get("viewsPerUnit") or 1000)
    days = int(cfg.get("recheckDays") or 7)
    return (
        f"<tg-emoji emoji-id='{ICON_VIDEOS}'>📹</tg-emoji> <b>Видео про бота</b>\n\n"
        f"<i>Снимите ролик про @CuteGamingBot.</i>\n"
        f"<i>Поставьте хештег {hashtag}.</i>\n\n"
        "<b>Как отправить ссылку</b>\n"
        "<i>Нажмите «Отправить ссылку», затем пришлите адрес.</i>\n"
        "<i>Пример:</i>\n"
        f"<code>{EXAMPLE_VIDEO_URL}</code>\n\n"
        f"<b>Каждые полные {per} просмотров - {kut} кут.</b>\n"
        f"<i>Перепроверка через {days} дней: доплата только за прирост.</i>\n"
        "<i>Нужна помощь с идеей - напишите @JerichoCute.</i>"
    )


def text_need_nick(path: str = "") -> str:
    after = (
        "Потом вернёмся к комментариям."
        if path == "comments"
        else "Потом вернёмся к видео."
        if path == "videos"
        else "Потом продолжим выбранное направление."
    )
    return (
        "<tg-emoji emoji-id='5456282961999570188'>🎵</tg-emoji> <b>Сначала укажите свой TikTok</b>\n\n"
        "<i>Без публичного ника мы не найдём Ваш аккаунт.</i>\n"
        f"<i>{after}</i>\n\n"
        "<b>Как выглядит ник</b>\n"
        f"<code>{EXAMPLE_NICK}</code>\n"
        "<i>Нажмите «Указать имя профиля», затем отправьте имя.</i>"
    )


def text_ask_nick() -> str:
    return (
        "<tg-emoji emoji-id='5456282961999570188'>🎵</tg-emoji> <b>Ждём имя профиля</b>\n\n"
        "<i>Отправьте ник одним сообщением. С @ или без.</i>\n"
        "<i>По нему найдём Ваш аккаунт.</i>\n\n"
        "<i>Пример:</i>\n"
        f"<code>{EXAMPLE_NICK}</code>"
    )


def text_nick_required_alert() -> str:
    return "Сначала укажите свой ник в TikTok. Без него скриншоты принять нельзя."


def text_nicks(nicks: list[str], *, locked: bool) -> str:
    body = "\n".join(f"<b>@{n}</b>" for n in nicks) if nicks else "<i>Пока ни одного ника.</i>"
    extra = (
        "\n\n<i>Сейчас идёт проверка. Ники можно менять после ответа.</i>"
        if locked
        else "\n\n<i>Переименовались - измените ник. Можно добавить ещё один аккаунт, до трёх.</i>"
    )
    return f"<b>Ваши TikTok-аккаунты</b>\n\n{body}{extra}"


def help_earnings_block() -> str:
    return (
        "<tg-emoji emoji-id='5456282961999570188'>🎵</tg-emoji> <b>TikTok</b>\n"
        "<i>Куты за комментарии с тегом и за видео про бота.</i>\n"
        "<i>Откройте Задания, нажмите Тик ток и выберите направление.</i>\n"
    )


def _nicks_block(nicks: list[str]) -> str:
    if not nicks:
        return ""
    lines = "\n".join(f"<code>@{n}</code>" for n in nicks)
    return f"\n\n<i>Ники, по которым проверят:</i>\n{lines}"


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
        body += (
            f"\n\n<b>Серия полная: {needed} из {needed}.</b>\n"
            "<i>Всё уже на проверке. Новую серию можно прислать после ответа.</i>"
        )
    elif count > 0:
        body += "\n\n" + collect_text(count, needed)
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
        body += "\n\n<b>Ссылка на проверке.</b>\n<i>Когда укажем просмотры - начислим куты за полные тысячи.</i>"
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
    return body


def text_wait_photos(count: int = 0, needed: int = 15) -> str:
    if count > 0:
        left = max(0, int(needed) - int(count))
        return (
            "<b>Ждём скриншоты</b>\n\n"
            f"<i>Сейчас на проверке</i> <b>{count} из {needed}</b><i>.</i>\n"
            f"<i>Осталось {left}. Альбомом или по одному, как фото.</i>"
        )
    return (
        "<b>Ждём скриншоты</b>\n\n"
        "<i>Пришлите кадры альбомом или по одному. Как фото, не как файл.</i>\n"
        "<i>Каждый скрин сразу уйдёт на проверку.</i>"
    )


def text_wait_link() -> str:
    return (
        "<b>Ждём ссылку на видео</b>\n\n"
        "<i>Отправьте адрес одним сообщением.</i>\n"
        "<i>Пример:</i>\n"
        f"<code>{EXAMPLE_VIDEO_URL}</code>"
    )


def text_press_send_photos() -> str:
    return (
        "<b>Сначала нажмите кнопку.</b>\n"
        "<i>Нажмите «Отправить скриншоты», затем пришлите фото.</i>"
    )


def text_press_send_link() -> str:
    return (
        "<b>Сначала нажмите кнопку.</b>\n"
        "<i>Нажмите «Отправить ссылку», затем пришлите адрес.</i>"
    )


def text_press_bind_nick() -> str:
    return (
        "<b>Сначала укажите имя профиля.</b>\n"
        "<i>Нажмите «Указать имя профиля», затем отправьте ник.</i>"
    )


def collect_text(count: int, needed: int, nicks: list[str] | None = None) -> str:
    bound = ""
    if nicks:
        bound = "\n<i>Проверяем:</i> " + ", ".join(f"<b>@{n}</b>" for n in nicks)
    if count >= needed:
        return (
            f"<b>{needed} из {needed}. Серия собрана и уже на проверке.</b>{bound}\n"
            "<i>Убрать последний кадр можно кнопкой ниже, пока нет решения.</i>"
        )
    left = needed - count
    return (
        f"<b>На проверке {count} из {needed}.</b> <i>Осталось {left}.</i>{bound}\n"
        "<i>Альбомом или по одному. Как фото, не как файл. Награду начислим только за полную серию.</i>"
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
        bound = "\n<i>Ники:</i> " + ", ".join(f"<b>@{n}</b>" for n in nicks)
    if added <= 0 and count >= needed:
        return (
            f"<b>Серия уже на проверке: {needed} из {needed}.</b>\n"
            "<i>Ждём решение. Новые кадры сейчас не примем.</i>"
        )
    word = ru_screenshot_word(added)
    verb = ru_gone_verb(added)
    if count >= needed:
        return (
            f"<b>{added} {word} {verb} на проверку.</b>\n"
            f"<b>Серия собрана: {needed} из {needed}.</b>\n"
            f"<i>Ждём решение. Награду начислим только за полную принятую серию.</i>{bound}"
        )
    left = needed - count
    return (
        f"<b>{added} {word} {verb} на проверку.</b>\n"
        f"<i>Сейчас на проверке</i> <b>{count} из {needed}</b><i>. Осталось {left}.</i>\n"
        f"<i>Можно прислать ещё альбомом или по одному.</i>{bound}"
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
    await set_session(user_id, next_mode, {"caseId": case_id})
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
                keep = MODE_WAIT_PHOTOS if session.get("mode") in PHOTO_WAIT_MODES else MODE_COMMENTS
                await set_session(user_id, keep, {})
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
                keep = MODE_WAIT_PHOTOS if session.get("mode") in PHOTO_WAIT_MODES else MODE_COMMENTS
                await set_session(user_id, keep, {})
                return {"count": 0, "needed": needed, "complete": False, "deleted": True}
            await conn.execute(
                "UPDATE tiktok_comment_cases SET photos = $2::jsonb WHERE id = $1 AND status = 'pending'",
                int(row["id"]),
                json.dumps(photos, ensure_ascii=False),
            )
            session = await get_session(user_id)
            keep = MODE_WAIT_PHOTOS if session.get("mode") in PHOTO_WAIT_MODES else MODE_COMMENTS
            await set_session(user_id, keep, {"caseId": int(row["id"])})
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
    if (await session_mode(user_id)) not in PHOTO_WAIT_MODES:
        return False
    case = await get_pending_comment_case(user_id)
    if case and case["complete"]:
        return False
    return True


async def is_waiting_nick(user_id: int) -> bool:
    return (await session_mode(user_id)) in NICK_WAIT_MODES


async def is_waiting_link(user_id: int) -> bool:
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
