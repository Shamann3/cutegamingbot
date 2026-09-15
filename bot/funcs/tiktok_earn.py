# -*- coding: utf-8 -*-
"""TikTok-заработок в боте: тексты, ники, набор скринов и ссылок."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

_SERVER = Path(__file__).resolve().parents[2] / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

from tiktok_earn_logic import (  # noqa: E402
    COMMENT_REWARD,
    KUT_PER_UNIT,
    MAX_NICKS,
    PHOTOS_REQUIRED,
    STATUS_EMOJI_NO,
    STATUS_EMOJI_OK,
    STATUS_EMOJI_WAIT,
    VIEWS_PER_UNIT,
    append_case_photos,
    canonicalize_tiktok_url,
    clip_button_text,
    comment_progress,
    display_tiktok_url,
    format_int_dot,
    hashes_from_image_bytes,
    kut_for_views,
    looks_like_tiktok_url_text,
    normalize_nick,
    recheck_wait_text,
    ru_gone_verb,
    ru_screenshot_word,
    status_emoji_html,
    status_kind_for_task,
    validate_nick,
    validate_video_title,
)

log = logging.getLogger("tiktok_earn")

looks_like_tiktok_url = looks_like_tiktok_url_text

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
TT_RETRY_VIDEO = "tt:vretry:"
TT_BACK_TASKS = "questions_stars"

ICON_TT = "5456282961999570188"
ICON_BACK = "5226660202035554522"
ICON_OK = "5224257782013769471"
ICON_CAM = "5373098002641805602"
ICON_COMMENTS = "5350367217349311525"
ICON_VIDEOS = "5229011542011299168"
ICON_NICKS = "5229011542011299168"
ICON_MY_VIDEOS = "5226928895189598791"
ICON_ADD = "5339564150534200424"
ICON_EDIT = "5472410705929971383"
ICON_UNDO = "5373098002641805602"
ICON_WITHDRAW = "5213205860498549992"
ICON_PREV = "5255703720078879038"
ICON_NEXT = "5253767677670862169"
ICON_STATUS_OK = STATUS_EMOJI_OK
ICON_STATUS_WAIT = STATUS_EMOJI_WAIT
ICON_STATUS_NO = STATUS_EMOJI_NO
VIDEOS_PAGE_SIZE = 10

MODE_COMMENTS = "comments"
MODE_VIDEOS = "videos"
MODE_NEED_NICK = "need_nick"
MODE_WAIT_PHOTOS = "wait_photos"
MODE_WAIT_LINK = "await_video_link"
MODE_WAIT_TITLE = "await_video_title"
MODE_WAIT_NICK = "await_nick"
MODE_WAIT_NICK_EDIT = "await_nick_edit"
MODE_COMMENT_DONE = "comment_wait"
PHOTO_WAIT_MODES = frozenset({MODE_WAIT_PHOTOS, "collect_photos"})
NICK_WAIT_MODES = frozenset({MODE_WAIT_NICK, MODE_WAIT_NICK_EDIT, MODE_NEED_NICK})
EXAMPLE_NICK = "@cuteplayer"
EXAMPLE_COMMENT = "Как по мне @CuteGamingBot намного лучше для заработка звезд в тг"
EXAMPLE_VIDEO_URL = "https://www.tiktok.com/@cuteplayer/video/7123456789012345678"
EXAMPLE_VIDEO_SHORT = "https://vt.tiktok.com/ZSqqKaCbB/"
EXAMPLE_VIDEO_TITLE = "Обзор CuteGamingBot"

WAIT_NICK = "nick"
WAIT_NICK_EDIT = "nick_edit"
WAIT_LINK = "link"
WAIT_TITLE = "title"
WAIT_PHOTOS = "photos"
TEXT_WAIT_KINDS = frozenset({WAIT_NICK, WAIT_NICK_EDIT, WAIT_LINK, WAIT_TITLE})
CANCEL_WORDS = frozenset({"назад", "завершить"})
WAIT_TTL_SECONDS = 300
PHOTO_WAIT_TTL_SECONDS = 1200
CANCEL_HINT = "<blockquote><i>Выйти :</i> <code>Назад</code> <i>или</i> <code>Завершить</code></blockquote>"
REPLY_HINT = "<blockquote><i>Отправьте следующим сообщением.</i></blockquote>"
PHOTO_HINT = "<blockquote><i>Отправьте фото в этот чат. Альбомом или по одному.</i></blockquote>"
INPUT_FOOTER = f"{REPLY_HINT}\n{CANCEL_HINT}"
PHOTO_FOOTER = f"{PHOTO_HINT}\n{CANCEL_HINT}"

_tt_wait: dict[int, dict[str, Any]] = {}
_timeout_tasks: dict[int, asyncio.Task] = {}
_album_groups: dict[int, str] = {}
_SCHEMA_READY = False


def format_hashtag(raw: str, *, fallback: str = "тгзвезды") -> str:
    s = (raw or "").strip() or fallback
    if s.startswith("@"):
        s = s[1:]
    if s.startswith("#"):
        s = s[1:]
    s = "".join(s.split()) or fallback
    return f"#{s}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _ttl_for(kind: str) -> int:
    return PHOTO_WAIT_TTL_SECONDS if kind == WAIT_PHOTOS else WAIT_TTL_SECONDS


def _private_type(chat_type: str | None) -> bool:
    return str(chat_type or "").lower() == "private"


def is_private_chat_type(chat_type: str | None) -> bool:
    return _private_type(chat_type)


def message_is_private_chat(message: Any) -> bool:
    chat = getattr(message, "chat", None)
    return _private_type(getattr(chat, "type", None))


def is_cancel_input(raw: str | None) -> bool:
    text = str(raw or "").strip().strip("«»\"'`“”").lower()
    return text in CANCEL_WORDS


def message_link_text(message: Any) -> str:
    return str(getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()


def pick_thumb_file_id(sizes: list[Any] | None) -> str:
    if not sizes:
        return ""
    best = min(sizes, key=lambda item: abs(int(getattr(item, "width", 0) or 0) - 320))
    return str(getattr(best, "file_id", "") or "")


def _uid_of(message: Any) -> int | None:
    user = getattr(message, "from_user", None)
    uid = getattr(user, "id", None)
    return int(uid) if uid else None


def get_wait(user_id: int) -> dict[str, Any] | None:
    rec = _tt_wait.get(int(user_id))
    return dict(rec) if rec else None


def clear_wait(user_id: int) -> None:
    uid = int(user_id)
    _tt_wait.pop(uid, None)
    _album_groups.pop(uid, None)
    task = _timeout_tasks.pop(uid, None)
    if task and not task.done():
        task.cancel()


def begin_wait(
    user_id: int,
    kind: str,
    after: str = "",
    extra: dict[str, Any] | None = None,
    prompt_message_id: int | None = None,
    prompt_chat_id: int | None = None,
) -> dict[str, Any]:
    payload = dict(extra or {})
    started = _now()
    ttl = _ttl_for(kind)
    expires = payload.get("expires_at") or _iso(started + timedelta(seconds=ttl))
    rec = {
        **payload,
        "kind": kind,
        "after": after or payload.get("after") or "",
        "awaiting": True,
        "started_at": payload.get("started_at") or _iso(started),
        "expires_at": expires,
        "prompt_message_id": prompt_message_id or payload.get("prompt_message_id"),
        "prompt_chat_id": prompt_chat_id or payload.get("prompt_chat_id"),
    }
    _tt_wait[int(user_id)] = rec
    return dict(rec)


def is_wait_expired(user_id: int) -> bool:
    rec = get_wait(user_id)
    if not rec:
        return False
    expires = _parse_iso(rec.get("expires_at"))
    if not expires:
        return False
    return _now() >= expires


def is_awaiting_text(user_id: int) -> bool:
    rec = get_wait(user_id)
    return bool(rec and rec.get("awaiting") and rec.get("kind") in TEXT_WAIT_KINDS and not is_wait_expired(user_id))


def is_awaiting_photos(user_id: int) -> bool:
    rec = get_wait(user_id)
    return bool(rec and rec.get("awaiting") and rec.get("kind") == WAIT_PHOTOS and not is_wait_expired(user_id))


def handler_would_accept_text(user_id: int, text: str, chat_type: str = "private") -> bool:
    if not _private_type(chat_type) or is_wait_expired(user_id) or not is_awaiting_text(user_id):
        return False
    raw = str(text or "").strip()
    if not raw or raw.startswith("/"):
        return False
    return True


def should_skip_main_text_handler(user_id: int, chat_type: str = "private") -> bool:
    if not _private_type(chat_type) or is_wait_expired(user_id):
        return False
    rec = get_wait(user_id)
    return bool(rec and rec.get("awaiting"))


def should_skip_photo_handler(user_id: int, chat_type: str = "private") -> bool:
    if not _private_type(chat_type) or is_wait_expired(user_id):
        return False
    return is_awaiting_photos(user_id)


def message_matches_wait_text(message: Any) -> bool:
    if not message_is_private_chat(message):
        return False
    uid = _uid_of(message)
    if not uid:
        return False
    return handler_would_accept_text(uid, message_link_text(message), "private")


def message_matches_wait_photo(message: Any) -> bool:
    if not message_is_private_chat(message):
        return False
    uid = _uid_of(message)
    if not uid or not is_awaiting_photos(uid):
        return False
    return bool(getattr(message, "photo", None))


def message_matches_wait_noise(message: Any) -> bool:
    if not message_is_private_chat(message):
        return False
    uid = _uid_of(message)
    if not uid:
        return False
    rec = get_wait(uid)
    if not rec or not rec.get("awaiting") or is_wait_expired(uid):
        return False
    if message_matches_wait_text(message) or message_matches_wait_photo(message):
        return False
    return True


def remember_album_group(user_id: int, group_id: str | None) -> None:
    if group_id:
        _album_groups[int(user_id)] = str(group_id)


def touch_wait(user_id: int) -> None:
    rec = _tt_wait.get(int(user_id))
    if not rec:
        return
    rec["expires_at"] = _iso(_now() + timedelta(seconds=_ttl_for(str(rec.get("kind") or ""))))


def _status_icon(kind: str) -> str:
    return {"ok": ICON_STATUS_OK, "no": ICON_STATUS_NO}.get(kind, ICON_STATUS_WAIT)


def _btn(text: str, data: str, icon: str | None = None, style: str | None = None) -> InlineKeyboardButton:
    kwargs: dict[str, Any] = {"text": text, "callback_data": data}
    if style:
        kwargs["style"] = style
    if icon:
        kwargs["icon_custom_emoji_id"] = icon
    return InlineKeyboardButton(**kwargs)


def _link_html(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    return f'<a href="{escape(raw, quote=True)}">{escape(raw)}</a>'


def _cfg(cfg: dict[str, Any] | None) -> dict[str, Any]:
    base = {
        "commentTag": "тг звезды",
        "videoHashtag": "@CuteGamingBot",
        "commentReward": COMMENT_REWARD,
        "viewsPerUnit": VIEWS_PER_UNIT,
        "kutPerUnit": KUT_PER_UNIT,
        "recheckDays": 7,
        "maxNicks": MAX_NICKS,
        "photosRequired": PHOTOS_REQUIRED,
    }
    if cfg:
        base.update({k: v for k, v in cfg.items() if v is not None})
    return base


def _nicks_line(nicks: list[str] | None) -> str:
    items = [f"@{escape(n)}" for n in (nicks or []) if n]
    return ", ".join(items) if items else EXAMPLE_NICK


def _notice_block(notice: str) -> str:
    text = str(notice or "").strip()
    return f"{text}\n\n" if text else ""


def help_earnings_block() -> str:
    return (
        f"<tg-emoji emoji-id='{ICON_TT}'>🎵</tg-emoji> <b>Тик ток</b>\n"
        "<b><i>Откройте Задания и нажмите Тик ток.</i></b>\n"
        "<blockquote><code>Задания</code></blockquote>"
    )


def text_hub(cfg: dict[str, Any] | None = None, *, has_nicks: bool = False) -> str:
    s = _cfg(cfg)
    reward = int(s["commentReward"])
    kut = int(s["kutPerUnit"])
    needed = int(s["photosRequired"])
    unit = format_int_dot(int(s["viewsPerUnit"]))
    extra = (
        "<blockquote><b>Имя вашего TikTok аккаунта уже сохранено</b></blockquote>"
        if has_nicks
        else "<blockquote><b>Для начала работы, напишите имя своего TikTok</b></blockquote>"
    )
    return (
        f"<tg-emoji emoji-id='{ICON_TT}'>🎵</tg-emoji> <b>Тик ток задания</b>\n"
        "<blockquote>"
        f"<b>Создание комментариев : {needed} скринов · {reward} кут</b>\n"
        f"<b>Съемка видео : {kut} кут за {unit} просмотров</b>"
        "</blockquote>"
    )


def text_need_nick(after: str = "", error: str = "") -> str:
    head = f"<b>{escape(error)}</b>\n" if error else ""
    why = {
        "comments": "Чтобы было видно, что комментарии Ваши",
        "videos": "Чтобы принять ролик на проверку",
        "mine": "Чтобы открыть Ваши ролики",
    }.get(after, "чтобы принять работу")
    return (
        f"{head}<b>Напишите имя своего TikTok</b>\n"
        f"<blockquote><b>{why}</b></blockquote>"
    )


def text_ask_nick() -> str:
    return text_need_nick()


def text_nick_required_alert() -> str:
    return "Сначала напишите имя своего TikTok"


def text_comments(cfg: dict[str, Any] | None = None) -> str:
    s = _cfg(cfg)
    tag = format_hashtag(s.get("commentTag") or "тг звезды")
    reward = int(s["commentReward"])
    needed = int(s["photosRequired"])
    return (
        f"<tg-emoji emoji-id='{ICON_COMMENTS}'>💬</tg-emoji> <b>Комментарии</b>\n"
        "<i>Делайте по порядку.</i>\n"
        "<blockquote>"
        f"<b>1. Найдите в поиске ролики с хештегом <code>{escape(tag)}</code></b>\n"
        "<b>2. Напишите комментарий с упоминанием @CuteGamingBot и поставьте лайк на свой комментарий</b>\n"
        f"<b>3. {needed} скринов · {reward} кут</b>"
        "</blockquote>\n"
        f"<blockquote><b>Например <code>{escape(EXAMPLE_COMMENT)}</code></b></blockquote>\n"
    )


def text_videos(cfg: dict[str, Any] | None = None) -> str:
    s = _cfg(cfg)
    tag = escape(str(s.get("videoHashtag") or "@CuteGamingBot"))
    kut = int(s["kutPerUnit"])
    unit = format_int_dot(int(s["viewsPerUnit"]))
    return (
        f"<tg-emoji emoji-id='{ICON_VIDEOS}'>🎬</tg-emoji> <b>Видео о боте</b>\n"
        "<b><i>Делайте по порядку.</i></b>\n"
        "<blockquote>"
        f"<b>1. Назовите своё видео</b>\n"
        f"<b>2. Отправьте ссылку на видео</b>"
        "</blockquote>\n"
        "<blockquote>"
        f"<b>Хештег под видео должен быть : {tag}</b>\n"
        f"<b>Награда : {kut} кут за {unit} просмотров</b>"
        "</blockquote>"
    )


def collect_text(count: int, needed: int, nicks: list[str] | None = None, cfg: dict[str, Any] | None = None) -> str:
    s = _cfg(cfg)
    reward = int(s["commentReward"])
    left = max(0, int(needed) - int(count))
    names = _nicks_line(nicks)
    if count >= needed:
        body = (
            f"<b>{count} из {needed}</b>\n"
            f"<blockquote><b>Готово {reward} кут после проверки</b></blockquote>"
        )
    elif count > 0:
        body = (
            f"<b>{count} из {needed}</b>\n"
            f"<blockquote><b>Ещё {left} · {names}</b></blockquote>"
        )
    else:
        body = (
            f"<b>0 из {needed}</b>\n"
            f"<blockquote><b>Аккаунт : {names}</b></blockquote>"
        )
    return (
        f"{status_emoji_html('wait')} {body}\n"
    )


def comments_screen_text(
    cfg: dict[str, Any] | None,
    nicks: list[str],
    *,
    pending: bool = False,
    count: int = 0,
    notice: str = "",
    latest: dict[str, Any] | None = None,
) -> str:
    s = _cfg(cfg)
    needed = int(s["photosRequired"])
    head = _notice_block(notice)
    if pending:
        return (
            f"{head}{status_emoji_html('wait')} <b>Серия скриншотов на проверке.</b>\n"
            f"<blockquote><b>{count} из {needed}</b></blockquote>\n"
        )
    if count > 0:
        return head + collect_text(count, needed, nicks, s)
    if latest and latest.get("status") == "rejected":
        reason = escape(str(latest.get("rejectText") or "Серию не приняли."))
        return (
            f"{head}{status_emoji_html('no')} <b>Прошлая серия сриншотов не прошла проверку</b>\n"
            f"<blockquote>{reason}</blockquote>\n"
            f"{text_comments(s)}"
        )
    if latest and latest.get("status") == "approved":
        return (
            f"{head}{status_emoji_html('ok')} <b>Прошлая серия скриншотов принята.</b>\n"
            f"{text_comments(s)}"
        )
    return head + text_comments(s)


def videos_screen_text(
    cfg: dict[str, Any] | None,
    nicks: list[str],
    videos: list[dict[str, Any]] | None = None,
    notice: str = "",
) -> str:
    s = _cfg(cfg)
    head = _notice_block(notice)
    pending = next((v for v in (videos or []) if v.get("status") == "pending"), None)
    if pending:
        title = escape(str(pending.get("title") or f"Ролик #{pending.get('id')}"))
        return (
            f"{head}{status_emoji_html('wait')} <b>Видео {title}</b>\n"
            "<blockquote><b>На проверке</b></blockquote>\n"
        )
    return head + text_videos(s)


def text_wait_photos(count: int = 0, needed: int = 15, nicks: list[str] | None = None) -> str:
    return collect_text(count, needed, nicks)


def text_wait_title(error: str = "", *, replace: bool = False) -> str:
    head = f"<b>{escape(error)}</b>\n" if error else ""
    action = "Новое название" if replace else "Название"
    return (
        f"{head}{status_emoji_html('wait')} <b>{action}.</b>\n"
        "<blockquote><b><i>Затем ссылку.</i></b></blockquote>\n"
    )


def text_wait_link(title: str = "", error: str = "") -> str:
    head = f"<b>{escape(error)}</b>\n" if error else ""
    named = f"<b>{escape(title)}</b>\n" if title else ""
    return (
        f"{head}{named}{status_emoji_html('wait')} <b>Теперь ссылка.</b>\n"
    )


def text_link_screen(error: str = "", title: str = "") -> str:
    return text_wait_link(title=title, error=error)


def text_wait_expired() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Срок ввода истёк</b>\n"
        "<blockquote><b><i>Попробуйте повторно загрузить доказательства.</i></b></blockquote>\n"

    )


def text_photos_on_review(added: int, count: int, needed: int, nicks: list[str] | None = None) -> str:
    word = ru_screenshot_word(added)
    verb = ru_gone_verb(added)
    names = _nicks_line(nicks)
    wait = "Ждём решение" if count >= needed else f"ещё {max(0, needed - count)}"
    return (
        f"{status_emoji_html('wait')} <b>{added} {word} {verb} на проверку.</b>\n"
        f"<blockquote><b>{count} из {needed} · {wait} · {names}</b></blockquote>\n"
    )


def text_press_send_photos() -> str:
    return "<b>Сначала нажмите кнопку.</b>\n<blockquote><b>Затем пришлите фото.</b></blockquote>"


def text_press_send_link() -> str:
    return "<b>Сначала нажмите кнопку.</b>\n<blockquote><b>Затем название и ссылку.</b></blockquote>"


def text_photo_wait_error(hint: str, count: int, needed: int) -> str:
    return (
        f"<b>{escape(hint)}</b>\n"
        f"<blockquote><b>Сейчас : {count} из {needed}</b></blockquote>\n"
    )


def text_nicks(nicks: list[str], *, locked: bool = False) -> str:
    if not nicks:
        return text_need_nick()
    listed = "\n".join(f"<code>@{escape(n)}</code>" for n in nicks)
    lock = (
        "<blockquote><b>Идёт проверка</b></blockquote>"
        if locked
        else "<blockquote><b><i>Добавить или сменить имя.</i></b></blockquote>"
    )
    return f"<b><tg-emoji emoji-id='5463071033256848094'>🔝</tg-emoji> Ваши аккаунты в TikTok\n{listed}\n{lock}</b>"


def text_my_videos(videos: list[dict[str, Any]] | None = None, page: int = 0) -> str:
    items = videos or []
    if not items:
        return (
            f"{status_emoji_html('wait')} <b>Ваши ролики</b>\n"
            "<blockquote><b><i>Пока пусто.</i></b></blockquote>"
        )
    _, pages = _video_pages(len(items), page)
    extra = f" · стр. {page + 1} из {pages}" if pages > 1 else ""
    return (
        f"<tg-emoji emoji-id='5226928895189598791'>⭐️</tg-emoji> <b>Ваши ролики{escape(extra)}</b>\n"
        "<blockquote><b>Зелёный <i>принят</i> · жёлтый <i>ждём</i> · красный <i>снова</i></b></blockquote>"
    )


def text_video_card(item: dict[str, Any] | None, notice: str = "") -> str:
    if not item:
        return "<b>Ролик не найден.</b>"
    status = str(item.get("status") or "pending")
    recheck = bool(item.get("recheckPending"))
    kind = status_kind_for_task(status, recheck=recheck)
    title = escape(str(item.get("title") or f"Ролик #{item.get('id')}"))
    views = int(item.get("lastViews") or 0)
    paid = int(item.get("paidKut") or 0)
    head = _notice_block(notice)
    if status == "rejected":
        state = "<blockquote><b>Не приняли. Нажмите «Отправить снова».</b></blockquote>"
    elif status == "pending" or recheck:
        state = "<blockquote><b>На проверке.</b></blockquote>"
    else:
        state = (
            f"<blockquote><b>Принят : {format_int_dot(views)} просм. · {format_int_dot(paid)} кут</b></blockquote>"
        )
    return (
        f"{head}{status_emoji_html(kind)} <b>{title}</b>\n"
        f"{state}\n"
        f"{_link_html(str(item.get('url') or ''))}"
    )


def text_done_nick_added(nick: str, have: list[str] | None = None) -> str:
    extra = f"\n<blockquote><b>Сейчас :</b> {_nicks_line(have)}</blockquote>" if have else ""
    return (
        f"{status_emoji_html('ok')} <b>Имя @{escape(nick)} сохранено.</b>"
        f"{extra}"
    )


def text_done_nick_changed(old: str, new: str) -> str:
    return (
        f"{status_emoji_html('ok')} <b>Имя аккаунте сменено</b>\n"
        f"<blockquote><b>@{escape(old)} - теперь @{escape(new)}</b></blockquote>"
    )


def text_done_video_sent(url: str, title: str = "") -> str:
    named = f"<b>{escape(title)}</b>\n" if title else ""
    return (
        f"{status_emoji_html('wait')} {named}<b>На проверке.</b>\n"
        f"<blockquote><b>{_link_html(url)}</b></blockquote>"
    )


def text_done_undo(count: int, needed: int) -> str:
    return (
        f"{status_emoji_html('wait')} <b>Последний кадр убрали.</b>\n"
        f"<blockquote><b>Сейчас : {count} из {needed}</b></blockquote>"
    )


def text_done_recheck(item: dict[str, Any] | None = None) -> str:
    title = escape(str((item or {}).get("title") or "ролик"))
    return (
        f"{status_emoji_html('wait')} <b>Пересчёт просмотров запрошен</b>\n"
        f"<blockquote><b>{title} · только новые тысячи</b></blockquote>"
    )


def text_case_withdrawn() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Серию сняли с проверки.</b>\n"
        "<blockquote><b><i>Можно собирать новую пачку серий комментариев</i></b></blockquote>"
    )


def _video_pages(total: int, page: int = 0) -> tuple[int, int]:
    pages = max(1, (max(0, int(total)) + VIDEOS_PAGE_SIZE - 1) // VIDEOS_PAGE_SIZE)
    return max(0, min(int(page), pages - 1)), pages


def video_recheck_state(last_checked: datetime | None, days: int = 7) -> dict[str, Any]:
    if not last_checked:
        return {"ready": True, "waitText": ""}
    last = last_checked if last_checked.tzinfo else last_checked.replace(tzinfo=timezone.utc)
    ready_at = last + timedelta(days=int(days or 7))
    now = _now()
    if now >= ready_at:
        return {"ready": True, "waitText": ""}
    return {"ready": False, "waitText": recheck_wait_text((ready_at - now).total_seconds())}


def hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Комментарии", TT_COMMENTS, ICON_COMMENTS, style="primary")],
        [_btn("Видео о боте", TT_VIDEOS, "5375309569905938163", style="primary")],
        [_btn("Аккаунты TikTok", TT_NICKS, ICON_NICKS)],
        [_btn("Ваши ролики", TT_MY_VIDEOS, ICON_MY_VIDEOS)],
        [_btn("Назад", TT_BACK_TASKS, ICON_BACK)],
    ])


def bind_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("Назад", TT_HUB, ICON_BACK)]])


def nick_wait_keyboard(*, back: str = "hub") -> InlineKeyboardMarkup:
    data = TT_NICKS if back == "nicks" else TT_HUB
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("Назад", data, ICON_BACK)]])


def done_keyboard(*, after: str = "hub") -> InlineKeyboardMarkup:
    dest = {
        "comments": (TT_COMMENTS, "К комментариям", ICON_COMMENTS),
        "videos": (TT_VIDEOS, "К видео", ICON_VIDEOS),
        "mine": (TT_MY_VIDEOS, "К роликам", ICON_MY_VIDEOS),
        "nicks": (TT_NICKS, "К никам", ICON_NICKS),
    }.get(after, (TT_HUB, "Продолжить", ICON_OK))
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(dest[1], dest[0], dest[2])],
        [_btn("В главное меню", TT_HUB, ICON_BACK)],
    ])


def comments_keyboard(
    *,
    can_send: bool = True,
    count: int = 0,
    needed: int = 15,
    waiting: bool = False,
    complete: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if complete:
        rows.append([_btn("Забрать серию", TT_WITHDRAW, ICON_WITHDRAW)])
    elif can_send and 0 < count < needed:
        rows.append([_btn("Убрать последнее фото", TT_UNDO_PHOTO, ICON_UNDO)])
    rows.append([_btn("Аккаунты TikTok", TT_NICKS, ICON_NICKS)])
    rows.append([_btn("Назад", TT_HUB, ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def collect_keyboard(count: int, needed: int) -> InlineKeyboardMarkup:
    return comments_keyboard(
        can_send=True,
        count=count,
        needed=needed,
        waiting=count < needed,
        complete=count >= needed,
    )


def videos_keyboard(
    videos: list[dict[str, Any]] | None = None,
    *,
    waiting: bool = False,
    can_send: bool = True,
) -> InlineKeyboardMarkup:
    rows = [
        [_btn("Аккаунты TikTok", TT_NICKS, ICON_NICKS)],
        [_btn("Ваши ролики", TT_MY_VIDEOS, ICON_MY_VIDEOS)],
        [_btn("Назад", TT_HUB, ICON_BACK)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def nicks_keyboard(nicks: list[str], *, locked: bool = False, origin: str = "hub") -> InlineKeyboardMarkup:
    back = {
        "comments": (TT_COMMENTS, ICON_COMMENTS),
        "videos": (TT_VIDEOS, ICON_VIDEOS),
        "mine": (TT_MY_VIDEOS, ICON_MY_VIDEOS),
    }.get(origin, (TT_HUB, ICON_BACK))
    rows: list[list[InlineKeyboardButton]] = []
    if not locked:
        rows.append([_btn("Добавить имя", TT_NICK_ADD, ICON_ADD)])
        if nicks:
            rows.append([_btn("Сменить имя", TT_NICK_EDIT, ICON_EDIT)])
    rows.append([_btn("Назад", back[0], back[1])])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def nick_pick_keyboard(nicks: list[str]) -> InlineKeyboardMarkup:
    rows = [[_btn(f"@{n}", f"{TT_NICK_PICK}{n}", ICON_NICKS)] for n in nicks]
    rows.append([_btn("Назад", TT_NICKS, ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_videos_keyboard(items: list[dict[str, Any]], page: int = 0) -> InlineKeyboardMarkup:
    page, pages = _video_pages(len(items), page)
    start = page * VIDEOS_PAGE_SIZE
    chunk = items[start:start + VIDEOS_PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []
    for item in chunk:
        status = str(item.get("status") or "pending")
        kind = status_kind_for_task(status, recheck=bool(item.get("recheckPending")))
        title = clip_button_text(str(item.get("title") or f"Ролик #{item.get('id')}"))
        rows.append([_btn(title, f"{TT_VIDEO_OPEN}{item.get('id')}", _status_icon(kind))])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn("Раньше", f"{TT_VIDEO_PAGE}{page - 1}", ICON_PREV))
    if page + 1 < pages:
        nav.append(_btn("Дальше", f"{TT_VIDEO_PAGE}{page + 1}", ICON_NEXT))
    if nav:
        rows.append(nav)
    rows.append([_btn("Новый ролик", TT_VIDEOS, ICON_ADD)])
    rows.append([_btn("Назад", TT_VIDEOS, ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def video_card_keyboard(item: dict[str, Any], page: int = 0) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    vid = int(item.get("id") or 0)
    status = str(item.get("status") or "")
    if status == "live" and item.get("recheckReady") and not item.get("recheckPending"):
        rows.append([_btn("Пересчитать просмотры", f"{TT_RECHECK}{vid}", ICON_OK)])
    if status == "rejected":
        rows.append([_btn("Отправить снова", f"{TT_RETRY_VIDEO}{vid}", ICON_ADD)])
    rows.append([_btn("Назад", f"{TT_VIDEO_PAGE}{page}", ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
            title TEXT NOT NULL DEFAULT '',
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
        ALTER TABLE tiktok_videos
            ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT '';
        INSERT INTO tiktok_settings (id) VALUES (1)
        ON CONFLICT (id) DO NOTHING;
        """
    )
    _SCHEMA_READY = True


async def get_settings() -> dict[str, Any]:
    await ensure_schema()
    pool = _pool()
    if not pool:
        return _cfg(None)
    row = await pool.fetchrow("SELECT * FROM tiktok_settings WHERE id = 1")
    if not row:
        return _cfg(None)
    return _cfg({
        "commentTag": row["comment_tag"],
        "videoHashtag": row["video_hashtag"],
        "commentReward": int(row["comment_reward"]),
        "viewsPerUnit": int(row["views_per_unit"]),
        "kutPerUnit": int(row["kut_per_unit"]),
        "recheckDays": int(row["recheck_days"]),
        "maxNicks": int(row["max_nicks"]),
        "photosRequired": int(row["photos_required"]),
    })


async def get_session(user_id: int) -> dict[str, Any]:
    await ensure_schema()
    pool = _pool()
    if not pool:
        return {"mode": "", "extra": {}}
    row = await pool.fetchrow(
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
    pool = _pool()
    if not pool:
        return
    await pool.execute(
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


async def persist_prompt(user_id: int, extra: dict[str, Any], mode: str | None = None) -> None:
    session = await get_session(user_id)
    payload = dict(session.get("extra") or {})
    payload.update(extra or {})
    await set_session(user_id, mode if mode is not None else session.get("mode") or "", payload)


async def clear_session(user_id: int) -> None:
    clear_wait(user_id)
    await set_session(user_id, "", {})


async def arm_wait(
    user_id: int,
    kind: str,
    mode: str,
    extra: dict[str, Any] | None = None,
    *,
    prompt_chat_id: int | None = None,
    prompt_message_id: int | None = None,
) -> dict[str, Any]:
    payload = dict(extra or {})
    rec = begin_wait(
        user_id,
        kind,
        after=str(payload.get("after") or ""),
        extra=payload,
        prompt_chat_id=prompt_chat_id,
        prompt_message_id=prompt_message_id,
    )
    rec["kind"] = kind
    await persist_prompt(
        user_id,
        {
            **payload,
            "kind": kind,
            "expires_at": rec.get("expires_at"),
            "prompt_chat_id": rec.get("prompt_chat_id"),
            "prompt_message_id": rec.get("prompt_message_id"),
        },
        mode=mode,
    )
    return rec


async def restore_wait_from_session(user_id: int) -> dict[str, Any] | None:
    if get_wait(user_id):
        return get_wait(user_id)
    session = await get_session(user_id)
    extra = dict(session.get("extra") or {})
    kind = extra.get("kind") or ""
    if not kind:
        mode = session.get("mode") or ""
        kind = {
            MODE_WAIT_PHOTOS: WAIT_PHOTOS,
            MODE_WAIT_LINK: WAIT_LINK,
            MODE_WAIT_TITLE: WAIT_TITLE,
            MODE_WAIT_NICK: WAIT_NICK,
            MODE_WAIT_NICK_EDIT: WAIT_NICK_EDIT,
        }.get(mode, "")
    if not kind:
        return None
    return begin_wait(user_id, kind, after=str(extra.get("after") or ""), extra=extra)


async def expire_wait_if_needed(user_id: int) -> bool:
    rec = get_wait(user_id) or await restore_wait_from_session(user_id)
    if not rec or not is_wait_expired(user_id):
        return False
    chat_id = rec.get("prompt_chat_id")
    mid = rec.get("prompt_message_id")
    clear_wait(user_id)
    await set_session(user_id, "", {})
    if chat_id and mid:
        try:
            from main import bot1
            await bot1.edit_message_text(
                text_wait_expired(),
                chat_id=int(chat_id),
                message_id=int(mid),
                reply_markup=hub_keyboard(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception:
            try:
                from main import bot1
                await bot1.send_message(
                    int(chat_id),
                    text_wait_expired(),
                    reply_markup=hub_keyboard(),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception:
                log.debug("tiktok expire notify failed", exc_info=True)
    return True


async def list_nicks(user_id: int) -> list[str]:
    await ensure_schema()
    pool = _pool()
    if not pool:
        return []
    rows = await pool.fetch(
        "SELECT nick FROM tiktok_nicks WHERE user_id = $1 ORDER BY id",
        int(user_id),
    )
    return [r["nick"] for r in rows]


async def has_pending(user_id: int) -> bool:
    await ensure_schema()
    pool = _pool()
    if not pool:
        return False
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


async def require_nicks(user_id: int) -> list[str]:
    nicks = await list_nicks(user_id)
    if not nicks:
        raise ValueError("Сначала напишите имя своего TikTok.")
    return nicks


async def add_nick(user_id: int, raw: str) -> str:
    settings = await get_settings()
    nick = validate_nick(raw)
    nicks = await list_nicks(user_id)
    if nick in nicks:
        raise ValueError("Такой ник уже есть в Вашем списке")
    if len(nicks) >= int(settings["maxNicks"]):
        raise ValueError(f"Можно не больше {settings['maxNicks']} имён TikTok")
    if await has_pending(user_id):
        raise ValueError("Сейчас идёт проверка. Имена можно менять после ответа.")
    pool = _pool()
    if not pool:
        raise ValueError("Сейчас нельзя сохранить имя. Попробуйте позже.")
    owner = await pool.fetchval("SELECT user_id FROM tiktok_nicks WHERE nick = $1", nick)
    if owner and int(owner) != int(user_id):
        raise ValueError("Этот ник уже занят другим игроком")
    try:
        await pool.execute(
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
    if await has_pending(user_id):
        raise ValueError("Сейчас идёт проверка. Имена можно менять после ответа.")
    new_nick = validate_nick(raw)
    old = normalize_nick(old_nick)
    current = await list_nicks(user_id)
    if old not in current:
        raise ValueError("Такого имени нет в Вашем списке")
    if new_nick in current and new_nick != old:
        raise ValueError("Такой ник уже есть в Вашем списке")
    pool = _pool()
    if not pool:
        raise ValueError("Сейчас нельзя сменить имя. Попробуйте позже.")
    owner = await pool.fetchval("SELECT user_id FROM tiktok_nicks WHERE nick = $1", new_nick)
    if owner and int(owner) != int(user_id):
        raise ValueError("Этот ник уже занят другим игроком")
    await pool.execute(
        "UPDATE tiktok_nicks SET nick = $3 WHERE user_id = $1 AND nick = $2",
        int(user_id),
        old,
        new_nick,
    )
    return new_nick


def _case_from_row(row, needed: int) -> dict[str, Any]:
    photos = _json(row["photos"]) or []
    progress = comment_progress(photos, needed)
    return {
        "id": int(row["id"]),
        "status": row["status"],
        "photos": photos,
        "received": int(progress["received"]),
        "needed": needed,
        "complete": bool(progress["complete"]),
        "rejectText": row["reject_text"] if "reject_text" in row.keys() else "",
        "createdAt": row["created_at"].isoformat() if getattr(row["created_at"], "isoformat", None) else row["created_at"],
    }


async def get_pending_comment_case(user_id: int) -> dict[str, Any] | None:
    await ensure_schema()
    pool = _pool()
    if not pool:
        return None
    settings = await get_settings()
    row = await pool.fetchrow(
        """
        SELECT * FROM tiktok_comment_cases
        WHERE user_id = $1 AND status = 'pending'
        ORDER BY id DESC LIMIT 1
        """,
        int(user_id),
    )
    return _case_from_row(row, int(settings["photosRequired"])) if row else None


async def get_latest_comment_case(user_id: int) -> dict[str, Any] | None:
    await ensure_schema()
    pool = _pool()
    if not pool:
        return None
    settings = await get_settings()
    row = await pool.fetchrow(
        """
        SELECT * FROM tiktok_comment_cases
        WHERE user_id = $1
        ORDER BY id DESC LIMIT 1
        """,
        int(user_id),
    )
    return _case_from_row(row, int(settings["photosRequired"])) if row else None


async def _ensure_pending_case(user_id: int) -> dict[str, Any]:
    existing = await get_pending_comment_case(user_id)
    if existing:
        return existing
    nicks = await require_nicks(user_id)
    pool = _pool()
    settings = await get_settings()
    row = await pool.fetchrow(
        """
        INSERT INTO tiktok_comment_cases (user_id, status, photos, nick_snapshot)
        VALUES ($1, 'pending', '[]'::jsonb, $2::jsonb)
        RETURNING *
        """,
        int(user_id),
        json.dumps(nicks, ensure_ascii=False),
    )
    return _case_from_row(row, int(settings["photosRequired"]))


async def add_photo(user_id: int, file_id: str, hashes: dict[str, Any] | None, thumb_id: str = "") -> dict[str, Any]:
    await require_nicks(user_id)
    settings = await get_settings()
    needed = int(settings["photosRequired"])
    case = await _ensure_pending_case(user_id)
    photo = {
        "fileId": file_id,
        "thumbFileId": thumb_id or "",
        "ahash": (hashes or {}).get("ahash") or "",
        "dhash": (hashes or {}).get("dhash") or "",
        "phash": (hashes or {}).get("phash") or "",
        "md5": (hashes or {}).get("md5") or "",
    }
    result = append_case_photos(case["photos"], [photo], needed)
    pool = _pool()
    await pool.execute(
        "UPDATE tiktok_comment_cases SET photos = $2::jsonb WHERE id = $1",
        case["id"],
        json.dumps(result["photos"], ensure_ascii=False),
    )
    return {
        "added": int(result["added"]),
        "count": int(result["received"]),
        "needed": needed,
        "complete": bool(result["complete"]),
        "caseId": case["id"],
    }


async def undo_photo(user_id: int) -> dict[str, Any]:
    case = await get_pending_comment_case(user_id)
    if not case:
        raise ValueError("Нет серии, из которой можно убрать кадр.")
    if case["complete"]:
        raise ValueError("Серия уже на проверке. Её можно только забрать целиком.")
    photos = list(case["photos"] or [])
    if not photos:
        raise ValueError("Пока нечего убирать.")
    photos.pop()
    settings = await get_settings()
    needed = int(settings["photosRequired"])
    pool = _pool()
    await pool.execute(
        "UPDATE tiktok_comment_cases SET photos = $2::jsonb WHERE id = $1",
        case["id"],
        json.dumps(photos, ensure_ascii=False),
    )
    progress = comment_progress(photos, needed)
    return {"count": int(progress["received"]), "needed": needed, "complete": False, "caseId": case["id"]}


async def withdraw_comment_case(user_id: int) -> None:
    case = await get_pending_comment_case(user_id)
    if not case:
        raise ValueError("Нет серии на проверке.")
    pool = _pool()
    await pool.execute(
        "UPDATE tiktok_comment_cases SET status = 'withdrawn' WHERE id = $1 AND user_id = $2",
        case["id"],
        int(user_id),
    )


async def submit_comment_case(user_id: int) -> dict[str, Any]:
    case = await get_pending_comment_case(user_id)
    if not case:
        raise ValueError("Сначала пришлите скрины.")
    return case


def _video_item(row, settings: dict[str, Any]) -> dict[str, Any]:
    last_checked = row["last_checked_at"]
    days = int(settings.get("recheckDays") or 7)
    unit = int(settings.get("kutPerUnit") or KUT_PER_UNIT)
    state = video_recheck_state(last_checked, days) if row["status"] == "live" else {"ready": False, "waitText": ""}
    paid_thousands = int(row["last_paid_thousands"] or 0)
    return {
        "id": int(row["id"]),
        "url": row["url"],
        "title": (row["title"] if "title" in row.keys() else "") or "",
        "status": row["status"],
        "lastViews": int(row["last_views"] or 0),
        "lastPaidThousands": paid_thousands,
        "paidKut": paid_thousands * unit,
        "kutPerUnit": unit,
        "lastCheckedAt": last_checked.isoformat() if last_checked else None,
        "recheckPending": bool(row["recheck_requested_at"]),
        "recheckReady": bool(state["ready"] and not row["recheck_requested_at"]),
        "recheckWaitText": state.get("waitText") or "",
        "rejectReasons": _json(row["reject_reasons"]) or [],
    }


async def list_user_videos(user_id: int) -> list[dict[str, Any]]:
    await ensure_schema()
    pool = _pool()
    if not pool:
        return []
    settings = await get_settings()
    rows = await pool.fetch(
        "SELECT * FROM tiktok_videos WHERE user_id = $1 ORDER BY created_at DESC",
        int(user_id),
    )
    return [_video_item(r, settings) for r in rows]


async def get_user_video(user_id: int, video_id: int) -> dict[str, Any] | None:
    await ensure_schema()
    pool = _pool()
    if not pool:
        return None
    settings = await get_settings()
    row = await pool.fetchrow(
        "SELECT * FROM tiktok_videos WHERE id = $1 AND user_id = $2",
        int(video_id),
        int(user_id),
    )
    return _video_item(row, settings) if row else None


async def submit_video(
    user_id: int,
    raw_url: str,
    title: str = "",
    replace_id: int | None = None,
) -> dict[str, Any]:
    await require_nicks(user_id)
    name = validate_video_title(title) if title else ""
    parsed = await asyncio.to_thread(canonicalize_tiktok_url, raw_url)
    display = display_tiktok_url(parsed, raw_url)
    pool = _pool()
    if not pool:
        raise ValueError("Сейчас нельзя принять ссылку. Попробуйте позже.")
    pending = await pool.fetchval(
        "SELECT id FROM tiktok_videos WHERE user_id = $1 AND status = 'pending'",
        int(user_id),
    )
    if pending and int(pending) != int(replace_id or 0):
        raise ValueError("Это видео уже на проверке. Как ответим - можно прислать новую ссылку.")
    taken = await pool.fetchrow(
        """
        SELECT id, user_id FROM tiktok_videos
        WHERE canonical_key = $1 AND status IN ('pending', 'live')
        """,
        parsed["canonical"],
    )
    if taken and int(taken["id"]) != int(replace_id or 0):
        raise ValueError("Этот ролик уже в системе.")
    if replace_id:
        row = await pool.fetchrow(
            "SELECT * FROM tiktok_videos WHERE id = $1 AND user_id = $2",
            int(replace_id),
            int(user_id),
        )
        if not row:
            raise ValueError("Ролик не найден")
        if row["status"] not in {"rejected"}:
            raise ValueError("Снова отправить можно только отклонённый ролик.")
        await pool.execute(
            """
            UPDATE tiktok_videos
            SET url = $2,
                canonical_key = $3,
                title = $4,
                status = 'pending',
                last_views = 0,
                last_paid_thousands = 0,
                last_checked_at = NULL,
                recheck_requested_at = NULL,
                reject_reasons = '[]'::jsonb,
                reviewed_by = NULL,
                reviewed_at = NULL
            WHERE id = $1
            """,
            int(replace_id),
            display,
            parsed["canonical"],
            name,
        )
        return {"id": int(replace_id), "url": display, "title": name, "canonical": parsed["canonical"]}
    row = await pool.fetchrow(
        """
        INSERT INTO tiktok_videos (user_id, url, canonical_key, title, status)
        VALUES ($1, $2, $3, $4, 'pending')
        RETURNING id
        """,
        int(user_id),
        display,
        parsed["canonical"],
        name,
    )
    return {"id": int(row["id"]), "url": display, "title": name, "canonical": parsed["canonical"]}


async def request_recheck(user_id: int, video_id: int) -> dict[str, Any]:
    item = await get_user_video(user_id, video_id)
    if not item:
        raise ValueError("Видео не найдено")
    if item["status"] != "live":
        raise ValueError("Перепроверка доступна только для принятого видео")
    if item["recheckPending"]:
        raise ValueError("Запрос уже на проверке")
    if not item["recheckReady"]:
        raise ValueError(item.get("recheckWaitText") or "Ещё рано. Подождите 7 дней.")
    pool = _pool()
    await pool.execute(
        "UPDATE tiktok_videos SET recheck_requested_at = NOW() WHERE id = $1",
        int(video_id),
    )
    return {"ok": True}


async def download_and_hash(bot: Any, file_id: str) -> dict[str, str]:
    try:
        file = await bot.get_file(file_id)
        buf = await bot.download_file(file.file_path)
        data = buf.getvalue() if hasattr(buf, "getvalue") else bytes(buf)
        return hashes_from_image_bytes(data)
    except Exception:
        log.debug("tiktok hash failed", exc_info=True)
        return {}


async def is_waiting_nick(user_id: int) -> bool:
    rec = get_wait(user_id) or {}
    return rec.get("kind") in {WAIT_NICK, WAIT_NICK_EDIT}


async def is_waiting_link(user_id: int) -> bool:
    rec = get_wait(user_id) or {}
    return rec.get("kind") == WAIT_LINK


async def is_waiting_title(user_id: int) -> bool:
    rec = get_wait(user_id) or {}
    return rec.get("kind") == WAIT_TITLE

