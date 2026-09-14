"""Чистая логика TikTok-заработка: ники, ссылки, просмотры, хеши, тексты."""

from __future__ import annotations

import hashlib
import io
import math
import random
import re
from html import escape
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

NICK_RE = re.compile(r"^[A-Za-z0-9._]{2,24}$")
MAX_NICKS = 3
PHOTOS_REQUIRED = 15
COMMENT_REWARD = 5
VIEWS_PER_UNIT = 1000
KUT_PER_UNIT = 30
RECHECK_DAYS = 7
# Потолок наград: опечатка в админке не должна начеканить миллионы.
COMMENT_REWARD_MIN = 1
COMMENT_REWARD_MAX = 500
VIDEO_REWARD_MIN = 1
VIDEO_REWARD_MAX = 5000
HASH_THRESHOLD = 4
# Скрины одного приложения часто похожи. Подсвечиваем только почти точный дубль,
# иначе админ тонет в ложных «похоже 90%» на одинаковом интерфейсе.
HASH_INTRA_THRESHOLD = 1
VIDEO_CANONICAL_RE = re.compile(r"/(?:video|v)/(\d+)", re.I)
SHARE_VIDEO_RE = re.compile(r"/share/video/(\d+)", re.I)
PHOTO_RE = re.compile(r"/photo/(\d+)", re.I)
SHORT_CODE_RE = re.compile(r"^[A-Za-z0-9]{5,24}$")
TIKTOK_IN_TEXT_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:(?:vt|vm|m)\.)?tiktok\.com/[^\s<>\"'\)\]]+",
    re.I,
)
SHORT_HOSTS = frozenset({"vt.tiktok.com", "vm.tiktok.com"})
LINK_HINT = "Пришлите ссылку tiktok.com, vt.tiktok.com или vm.tiktok.com."
VIDEO_TITLE_MIN = 2
VIDEO_TITLE_MAX = 48
STATUS_EMOJI_OK = "5339112148175959615"
STATUS_EMOJI_WAIT = "5339082633160703625"
STATUS_EMOJI_NO = "5337017423906226569"
STATUS_EMOJI = {
    "ok": (STATUS_EMOJI_OK, "🟢"),
    "wait": (STATUS_EMOJI_WAIT, "🟡"),
    "no": (STATUS_EMOJI_NO, "🔴"),
}

DEFAULT_COMMENT_TAG = "тг звезды"
DEFAULT_VIDEO_HASHTAG = "@CuteGamingBot"

DEFAULT_REJECT_REASONS: list[dict[str, str]] = [
    {"id": "bad_link", "label": "Некорректная ссылка"},
    {"id": "no_hashtag", "label": "Не указан хештег проекта"},
    {"id": "not_about_bot", "label": "Ролик не про бота"},
    {"id": "adult", "label": "18+ контент"},
    {"id": "insult", "label": "Оскорбление проекта"},
    {"id": "repost", "label": "Чужой ролик / репост"},
    {"id": "watermark", "label": "Водяной знак другого проекта"},
    {"id": "low_quality", "label": "Низкое качество / набор слайдов без смысла"},
]

DEFAULT_PHOTO_REJECT_REASONS: list[dict[str, str]] = [
    {"id": "adult", "label": "18+ контент"},
    {"id": "insult", "label": "Оскорбление проекта или людей"},
    {"id": "not_comment", "label": "На фото нет комментария"},
    {"id": "not_tiktok", "label": "Это не скрин из TikTok"},
    {"id": "not_yours", "label": "Комментарий не Ваш"},
    {"id": "no_like", "label": "Нет лайка на своём комментарии"},
    {"id": "no_hashtag", "label": "Нет нужного хештега"},
    {"id": "blurry", "label": "Фото размытое, текст не читается"},
    {"id": "collage", "label": "Несколько комментариев на одном кадре"},
    {"id": "stolen", "label": "Чужой скрин"},
    {"id": "spam", "label": "Бессмысленный или спам-комментарий"},
    {"id": "cropped", "label": "Кадр обрезан, не видно задание"},
]

BARNUM_REJECTS: tuple[str, ...] = (
    "<b>Эту серию комментариев не приняли.</b>\n<i>По кадрам не складывается цельная картина выполнения. Соберите новую серию комментариев : 15 разных комментариев под роликами с нужным хештегом, а также лайк на своём комментарии и свежие скрины.</i>",
    "<b>Серия комментариев не прошла проверку.</b>\n<i>Смотрим не только на число кадров, а на то, как собрано всё вместе. Сейчас картина выглядит незавершённой. Пришлите новую серию комментариев с нуля.</i>",
    "<b>Пока не можем принять.</b>\n<i>По этой сдаче не видно, что задание выполнено целиком. 15 свежих скринов, один комментарий - один кадр, и можно снова.</i>",
    "<b>Эту сдачу закрыли.</b>\n<i>Так бывает, если кадры слишком похожи или не показывают выполненное задание целиком. Соберите новую серию комментариев и пришлите снова.</i>",
)

TAB_TEASERS: dict[str, str] = {
    "comments": "Эту очередь разбирают те, кому доверили живые скрины. Когда откроют — окажитесь здесь.",
    "videos": "Ссылку и просмотры видят только те, кого пустили к роликам. Должность выше — дверь ближе.",
    "live": "Живые ролики и доплаты за тысячи просмотров. Сюда пускают после доверия к обычной очереди.",
    "archive": "Архив — память раздела. Его открывают тем, кто уже умеет закрывать дела, а не только смотреть.",
    "settings": "Награды, хештеги и причины отказа. Эту комнату оставляют тем, кто отвечает за правила, не только за проверку.",
}


def normalize_nick(raw: str) -> str:
    nick = (raw or "").strip()
    if "tiktok.com" in nick.lower() and "/@" in nick:
        nick = nick.split("/@", 1)[1]
    nick = nick.split("/")[0].strip()
    nick = nick.split("?")[0].strip()
    nick = nick.lstrip("@").strip()
    return nick.lower()


def validate_nick(raw: str) -> str:
    nick = normalize_nick(raw)
    if not NICK_RE.match(nick):
        raise ValueError("Ник: латиница, цифры, точка или _, от 2 до 24 символов")
    return nick


def _tiktok_host(netloc: str) -> str:
    host = (netloc or "").split("@")[-1].lower()
    if ":" in host:
        host = host.split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def _is_tiktok_host(host: str) -> bool:
    return host == "tiktok.com" or host.endswith(".tiktok.com")


def extract_tiktok_url(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ValueError(f"Это не похоже на ссылку TikTok. {LINK_HINT}")
    text = text.replace("\\", "").strip("<>«»\"'`“”")
    found = TIKTOK_IN_TEXT_RE.search(text)
    if found:
        return found.group(0).rstrip(".,;!?")
    cleaned = text.split()[0].rstrip(".,;!?")
    if "tiktok.com" in cleaned.lower():
        return cleaned
    raise ValueError(f"Это не похоже на ссылку TikTok. {LINK_HINT}")


def format_int_dot(value: int) -> str:
    number = int(value)
    sign = "-" if number < 0 else ""
    digits = str(abs(number))
    parts: list[str] = []
    while digits:
        parts.append(digits[-3:])
        digits = digits[:-3]
    return sign + ".".join(reversed(parts))


def format_views_compact(value: int) -> str:
    number = max(0, int(value))
    if number >= 1_000_000:
        text = f"{number / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{text}m"
    if number >= 1000:
        text = f"{number / 1000:.1f}".rstrip("0").rstrip(".")
        return f"{text}k"
    return format_int_dot(number)


def parse_views_input(raw: Any) -> int:
    text = str(raw or "").strip().lower().replace(" ", "").replace("\u00a0", "")
    if not text:
        raise ValueError("Впишите просмотры")
    text = text.replace(",", ".")
    mult = 1
    if text.endswith(("k", "к")):
        mult = 1000
        text = text[:-1]
    elif text.endswith(("m", "м")):
        mult = 1_000_000
        text = text[:-1]
    if not re.fullmatch(r"\d+(?:\.\d+)*", text):
        raise ValueError("Просмотры: 64.6k или 1.000")
    parts = text.split(".")
    if mult > 1:
        return int(round(float(text) * mult))
    if len(parts) == 1:
        return int(parts[0])
    if all(len(chunk) == 3 for chunk in parts[1:]):
        return int("".join(parts))
    if len(parts) == 2 and 1 <= len(parts[1]) <= 2 and int(parts[0]) < 1000:
        return int(round(float(text) * 1000))
    raise ValueError("Просмотры: 64.6k или 1.000")


def reviewer_mention_html(user_id: int, name: str = "", username: str = "") -> str:
    label = escape(str(name or username or user_id).strip() or str(user_id))
    return f'<a href="tg://user?id={int(user_id)}">{label}</a>'


def reviewer_line_html(kind: str, mention: str) -> str:
    if kind == "comments":
        return f"<b><i>Выполнение Вашего задания на комментарии проверял сотрудник Эпсилона</i> {mention}.</b>"
    return f"<b><i>Ваше видео проверял сотрудник Эпсилона</i> {mention}.</b>"


def display_tiktok_url(parsed: dict[str, str] | None, raw: str = "") -> str:
    data = parsed or {}
    for key in ("sourceUrl", "url"):
        value = str(data.get(key) or "").strip()
        if value:
            if "://" not in value:
                value = "https://" + value.lstrip("/")
            return value.split("#", 1)[0]
    text = str(raw or "").strip()
    return text


def _video_payload(video_id: str, url: str) -> dict[str, str]:
    vid = str(video_id or "").strip()
    if not vid.isdigit():
        raise ValueError(f"Это не похоже на ссылку TikTok. {LINK_HINT}")
    display = str(url or "").strip()
    if display and "://" not in display:
        display = "https://" + display.lstrip("/")
    if not display:
        display = f"https://www.tiktok.com/video/{vid}"
    return {
        "url": display,
        "canonical": f"video:{vid}",
        "videoId": vid,
        "kind": "video",
        "sourceUrl": display,
    }


def _short_payload(code: str, url: str) -> dict[str, str]:
    token = re.sub(r"[^A-Za-z0-9]", "", code or "")
    if not SHORT_CODE_RE.match(token):
        raise ValueError(f"Это не похоже на ссылку TikTok. {LINK_HINT}")
    return {
        "url": url,
        "canonical": f"short:{token.lower()}",
        "videoId": "",
        "kind": "short",
        "sourceUrl": url,
    }


def parse_tiktok_url(raw: str) -> dict[str, str]:
    text = extract_tiktok_url(raw)
    if "://" not in text:
        text = "https://" + text.lstrip("/")
    parsed = urlparse(text)
    host = _tiktok_host(parsed.netloc)
    if not _is_tiktok_host(host):
        raise ValueError(f"Это не похоже на ссылку TikTok. {LINK_HINT}")
    path = parsed.path or ""
    if PHOTO_RE.search(path):
        raise ValueError("Нужна ссылка на видео, не на фото.")
    share = SHARE_VIDEO_RE.search(path)
    if share:
        return _video_payload(share.group(1), text)
    video = VIDEO_CANONICAL_RE.search(path)
    if video:
        return _video_payload(video.group(1), text)
    qs = parse_qs(parsed.query)
    for key in ("share_item_id", "item_id", "aweme_id"):
        if qs.get(key) and str(qs[key][0]).isdigit():
            return _video_payload(str(qs[key][0]), text)
    parts = [p for p in path.split("/") if p]
    code = ""
    if parts and parts[0].lower() == "t" and len(parts) > 1:
        code = parts[1]
    elif host in SHORT_HOSTS and parts:
        code = parts[0]
    elif len(parts) == 1 and SHORT_CODE_RE.match(parts[0]):
        code = parts[0]
    if code:
        display = text.split("?", 1)[0].split("#", 1)[0]
        if not display.endswith("/"):
            display += "/"
        return _short_payload(code, display)
    raise ValueError(f"Это не похоже на ссылку TikTok. {LINK_HINT}")


def resolve_tiktok_redirects(url: str, *, timeout: float = 6.0) -> str:
    """Разворачивает vt/vm короткие ссылки. Никуда кроме TikTok не ходим."""
    import urllib.request

    class _OnlyTikTok(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            host = _tiktok_host(urlparse(newurl).netloc)
            if not _is_tiktok_host(host):
                return None
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(_OnlyTikTok)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    last = url
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers=headers)
            with opener.open(req, timeout=timeout) as resp:
                final = resp.geturl() or url
                if final:
                    last = final
                    break
        except Exception:
            continue
    return last


def status_emoji_html(kind: str) -> str:
    eid, fallback = STATUS_EMOJI.get(kind) or STATUS_EMOJI["wait"]
    return f"<tg-emoji emoji-id='{eid}'>{fallback}</tg-emoji>"


def status_kind_for_task(status: str, *, recheck: bool = False) -> str:
    value = str(status or "").strip().lower()
    if value in {"rejected", "rejected_comments"}:
        return "no"
    if value in {"approved", "live"}:
        return "ok"
    if recheck or value in {"pending", "withdrawn", ""}:
        return "wait"
    return "wait"


def looks_like_tiktok_url_text(raw: str) -> bool:
    text = str(raw or "").strip()
    if not text:
        return False
    try:
        parse_tiktok_url(text)
        return True
    except ValueError:
        return bool(TIKTOK_IN_TEXT_RE.search(text))


def validate_video_title(raw: str) -> str:
    text = " ".join(str(raw or "").split())
    if not text:
        raise ValueError("Напишите, как назвать ролик.")
    if looks_like_tiktok_url_text(text):
        raise ValueError("Это ссылка. Сначала напишите название, ссылку пришлёте следующим шагом.")
    if len(text) < VIDEO_TITLE_MIN:
        raise ValueError("Название слишком короткое. Хотя бы два символа.")
    if len(text) > VIDEO_TITLE_MAX:
        raise ValueError(f"Название длиннее {VIDEO_TITLE_MAX} символов. Сократите.")
    return text


def clip_button_text(text: str, limit: int = 64) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: max(1, limit - 3)].rstrip() + "..."


def canonicalize_tiktok_url(raw: str, *, resolve: bool = True) -> dict[str, str]:
    parsed = parse_tiktok_url(raw)
    if not resolve or parsed.get("videoId"):
        return parsed
    try:
        final = resolve_tiktok_redirects(parsed["url"])
    except Exception:
        return parsed
    if not final or final == parsed["url"]:
        return parsed
    try:
        again = parse_tiktok_url(final)
    except ValueError:
        return parsed
    if again.get("videoId"):
        original = parsed.get("sourceUrl") or parsed.get("url") or raw
        again["sourceUrl"] = original
        again["url"] = original
        return again
    return parsed


def thousands_from_views(views: int) -> int:
    views = int(views or 0)
    if views < 0:
        raise ValueError("Просмотры не могут быть меньше 0")
    return views // VIEWS_PER_UNIT


def validate_comment_reward(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Награда за пачку должна быть целым числом") from exc
    if value < COMMENT_REWARD_MIN or value > COMMENT_REWARD_MAX:
        raise ValueError(
            f"Награда за пачку: от {COMMENT_REWARD_MIN} до {COMMENT_REWARD_MAX} кут"
        )
    return value


def validate_video_reward(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Награда за 1.000 просмотров должна быть целым числом") from exc
    if value < VIDEO_REWARD_MIN or value > VIDEO_REWARD_MAX:
        raise ValueError(
            f"Награда за 1.000 просмотров : от {VIDEO_REWARD_MIN} до {VIDEO_REWARD_MAX} кут"
        )
    return value


def comment_progress(photos: Any, needed: int = PHOTOS_REQUIRED) -> dict[str, Any]:
    received = len(list(photos or []))
    need = max(1, int(needed or PHOTOS_REQUIRED))
    return {
        "received": received,
        "needed": need,
        "left": max(0, need - received),
        "complete": received >= need,
        "incomplete": received < need,
    }


def append_case_photos(
    existing: Iterable[Any] | None,
    incoming: Iterable[Any] | None,
    needed: int = PHOTOS_REQUIRED,
) -> dict[str, Any]:
    photos = list(existing or [])
    added = 0
    for item in incoming or []:
        if len(photos) >= int(needed or PHOTOS_REQUIRED):
            break
        photos.append(item)
        added += 1
    progress = comment_progress(photos, needed)
    return {**progress, "photos": photos, "added": added}


def assert_can_approve_comments(photos: Any, needed: int = PHOTOS_REQUIRED) -> dict[str, Any]:
    progress = comment_progress(photos, needed)
    if progress["incomplete"]:
        raise ValueError(
            f"Серия неполная : {progress['received']} из {progress['needed']}. "
            "Награду можно начислить только за полную пачку."
        )
    return progress


def ru_screenshot_word(n: int) -> str:
    value = abs(int(n))
    mod10 = value % 10
    mod100 = value % 100
    if mod10 == 1 and mod100 != 11:
        return "скриншот"
    if mod10 in {2, 3, 4} and mod100 not in {12, 13, 14}:
        return "скриншота"
    return "скриншотов"


def ru_gone_verb(n: int) -> str:
    value = abs(int(n))
    mod10 = value % 10
    mod100 = value % 100
    if mod10 == 1 and mod100 != 11:
        return "ушёл"
    return "ушли"


def wrap_barnum_html(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        raw = BARNUM_REJECTS[0]
    if "<b>" in raw or "<i>" in raw:
        return raw
    return f"<b>Серия комментариев не принята.\n<i>{raw}</i></b>"


CUSTOM_REASON_MAX = 280


def clean_custom_reason(raw: Any) -> str:
    text = " ".join(str(raw or "").split())
    if len(text) > CUSTOM_REASON_MAX:
        raise ValueError(f"Своя причина длиннее {CUSTOM_REASON_MAX} символов")
    return text


def reject_labels(*parts: Any) -> list[str]:
    clean: list[str] = []
    for part in parts:
        if isinstance(part, (list, tuple)):
            items = part
        else:
            items = [part]
        for item in items:
            label = str(item or "").strip()
            if label and label not in clean:
                clean.append(label)
    if not clean:
        raise ValueError("Отметьте хотя бы одну причину отказа")
    return clean


def _who_checked(kind: str, reviewer_html: str = "") -> str:
    mention = str(reviewer_html or "").strip()
    if not mention:
        return ""
    return f"\n{reviewer_line_html(kind, mention)}"


def format_photo_reject_html(labels: list[str], *, reviewer_html: str = "") -> str:
    clean = reject_labels(labels)
    lines = "\n".join(f"<b>{i}.</b> {escape(label)}" for i, label in enumerate(clean, 1))
    return (
        f"{status_emoji_html('no')} <b>Комментарии не приняли.</b>\n"
        "<blockquote>"
        f"<b>{lines}</b>"
        "</blockquote>"
        f"{_who_checked('comments', reviewer_html)}"
    )


def format_comment_payout_html(
    amount: int,
    photos: int = PHOTOS_REQUIRED,
    *,
    reviewer_html: str = "",
) -> str:
    pay = max(0, int(amount))
    pack = max(1, int(photos or PHOTOS_REQUIRED))
    return (
        f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>+{format_int_dot(pay)} кут</b>\n"
        f"<blockquote><b>{pack} скринов за комментарии</b></blockquote>"
        f"{_who_checked('comments', reviewer_html)}"
    )


def format_video_payout_html(
    *,
    kut: int,
    views: int,
    kut_per_unit: int = KUT_PER_UNIT,
    is_recheck: bool = False,
    old_views: int = 0,
    days: int = RECHECK_DAYS,
    title: str = "",
    reviewer_html: str = "",
) -> str:
    pay = max(0, int(kut))
    now = max(0, int(views))
    unit = max(1, int(kut_per_unit or KUT_PER_UNIT))
    thousands = thousands_from_views(now)
    wait_days = max(1, int(days or RECHECK_DAYS))
    named = f"<b>{escape(title)}</b>\n" if str(title or "").strip() else ""
    who = _who_checked("video", reviewer_html)
    if is_recheck:
        if pay > 0:
            return (
                f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>+{format_int_dot(pay)} кут</b>\n"
                f"{named}"
                "<blockquote>"
                "<b>За обновление новых просмотров на TikTok видео</b>\n"
                f"<b>Было {format_int_dot(int(old_views))}</b>\n"
                f"<b>Сейчас {format_int_dot(now)}</b>\n"
                f"<b>Доплата {format_int_dot(pay)} кут</b>"
                "</blockquote>"
                f"{who}"
            )
        return (
            f"<b>Просмотры обновили.</b>\n"
            f"{named}"
            "<blockquote>"
            "<b>За перепроверку TikTok видео</b>\n"
            f"<b>Сейчас {format_int_dot(now)}</b>\n"
            "<b>Доплаты нет, новых полных тысяч не набралось</b>"
            "</blockquote>\n"
            f"<b><i>Следующая проверка через {wait_days} дн.</i></b>"
            f"{who}"
        )
    if pay > 0:
        return (
            f"<tg-emoji emoji-id='5224257782013769471'>💰</tg-emoji> <b>+{format_int_dot(pay)} кут</b>\n"
            f"{named}"
            "<blockquote>"
            "<b>За TikTok видео о проекте</b>\n"
            f"<b>Просмотры {format_int_dot(now)}</b>\n"
            f"<b>Счёт {format_int_dot(thousands)} × {unit} кут</b>"
            "</blockquote>"
            f"{who}"
        )
    return (
        f"{status_emoji_html('ok')} <b>Видео принято.</b>\n"
        f"{named}"
        "<blockquote>"
        "<b>За TikTok ролик о проекте</b>\n"
        f"<b>Просмотры {format_int_dot(now)}</b>\n"
        f"<b>Куты появятся после {format_int_dot(VIEWS_PER_UNIT)} просмотров</b>"
        "</blockquote>"
        f"{who}"
    )


def format_video_reject_html(labels: list[str], *, title: str = "", reviewer_html: str = "") -> str:
    clean = reject_labels(labels)
    lines = "\n".join(f"<b>{i}. {escape(label)}</b>" for i, label in enumerate(clean, 1))
    named = f"<b>{escape(title)}</b>\n" if str(title or "").strip() else ""
    return (
        f"{status_emoji_html('no')} <b>Ролик не приняли.</b>\n"
        f"{named}"
        "<blockquote>"
        f"<b>{lines}</b>"
        "</blockquote>\n"
        "<blockquote><b><i>Ваши ролики → «Отправить снова».</i></b></blockquote>"
        f"{_who_checked('video', reviewer_html)}"
    )


def kut_for_thousands(thousands: int, kut_per_unit: int = KUT_PER_UNIT) -> int:
    return max(0, int(thousands)) * int(kut_per_unit)


def kut_for_views(views: int, kut_per_unit: int = KUT_PER_UNIT) -> int:
    return kut_for_thousands(thousands_from_views(views), kut_per_unit)


def payout_delta(old_views: int, new_views: int, kut_per_unit: int = KUT_PER_UNIT) -> dict[str, int]:
    if int(new_views) < int(old_views):
        raise ValueError("Новые просмотры меньше уже учтённых")
    old_t = thousands_from_views(old_views)
    new_t = thousands_from_views(new_views)
    delta_t = new_t - old_t
    return {
        "oldViews": int(old_views),
        "newViews": int(new_views),
        "oldThousands": old_t,
        "newThousands": new_t,
        "deltaThousands": delta_t,
        "kut": kut_for_thousands(delta_t, kut_per_unit),
    }


def pick_barnum(
    rng: random.Random | None = None,
    texts: Iterable[str] | None = None,
) -> str:
    pool = [t.strip() for t in (texts or BARNUM_REJECTS) if str(t).strip()]
    if not pool:
        pool = list(BARNUM_REJECTS)
    src = rng or random
    return src.choice(pool)


def next_queue_item(items: list[dict[str, Any]], current_id: int | None) -> dict[str, Any] | None:
    if not items:
        return None
    if current_id is None:
        return items[0]
    for index, item in enumerate(items):
        try:
            if int(item.get("id")) == int(current_id):
                return items[index + 1] if index + 1 < len(items) else None
        except (TypeError, ValueError):
            continue
    return items[0]


def hamming_hex(a: str, b: str) -> int:
    if not a or not b or len(a) != len(b):
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def hash_distance(left: dict[str, str], right: dict[str, str]) -> int:
    left_md5 = str(left.get("md5") or "")
    right_md5 = str(right.get("md5") or "")
    if left_md5 and right_md5 and left_md5 == right_md5:
        return 0
    scores = []
    for key in ("ahash", "dhash", "phash"):
        a, b = left.get(key) or "", right.get(key) or ""
        if a and b:
            scores.append(hamming_hex(a, b))
    if not scores:
        return 64
    return min(scores)


def similarity_percent(distance: int) -> int:
    dist = max(0, min(64, int(distance)))
    return int(round(100 * (1 - dist / 64)))


def hashes_similar(left: dict[str, str], right: dict[str, str], threshold: int = HASH_THRESHOLD) -> bool:
    return hash_distance(left, right) <= int(threshold)


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def find_matches(
    photos: list[dict[str, Any]],
    library: list[dict[str, Any]],
    *,
    verdicts: dict[tuple[str, str], str] | None = None,
    threshold: int = HASH_THRESHOLD,
    intra_threshold: int = HASH_INTRA_THRESHOLD,
) -> list[dict[str, Any]]:
    """Похожие пары: другие заявки по threshold, внутри серии только почти точные дубли."""
    verdicts = verdicts or {}
    found: list[dict[str, Any]] = []
    seen_pairs: set[tuple[Any, Any, Any, Any]] = set()
    for src in photos:
        for other in library:
            if src is other:
                continue
            if src.get("id") and other.get("id") and src["id"] == other["id"]:
                continue
            same_case = bool(
                src.get("caseId") is not None
                and other.get("caseId") is not None
                and src.get("caseId") == other.get("caseId")
            )
            if same_case and src.get("index") == other.get("index"):
                continue
            distance = hash_distance(src, other)
            limit = int(intra_threshold if same_case else threshold)
            if distance > limit:
                continue
            key = pair_key(src.get("phash") or src.get("ahash") or "", other.get("phash") or other.get("ahash") or "")
            if verdicts.get(key) == "unique":
                continue
            pair_id = (
                src.get("caseId"),
                src.get("index"),
                other.get("caseId"),
                other.get("index"),
            )
            rev = (pair_id[2], pair_id[3], pair_id[0], pair_id[1])
            if pair_id in seen_pairs or rev in seen_pairs:
                continue
            seen_pairs.add(pair_id)
            found.append(
                {
                    "source": src,
                    "match": other,
                    "distance": distance,
                    "similarity": similarity_percent(distance),
                    "sameCase": same_case,
                    "scope": "same_series" if same_case else "other",
                    "verdict": verdicts.get(key),
                }
            )
    found.sort(key=lambda x: (x["sameCase"], x["distance"]))
    return found[:48]


def _avg_hash(pixels: list[int], width: int, height: int) -> str:
    mean = sum(pixels) / max(1, len(pixels))
    bits = 0
    for i, p in enumerate(pixels):
        if p >= mean:
            bits |= 1 << i
    return f"{bits:016x}"


def _dhash(pixels: list[int], width: int, height: int) -> str:
    bits = 0
    bit = 0
    for y in range(height):
        row = y * width
        for x in range(width - 1):
            if pixels[row + x] < pixels[row + x + 1]:
                bits |= 1 << bit
            bit += 1
    return f"{bits:016x}"


def _phash(pixels: list[int], size: int = 32) -> str:
    """Упрощённый pHash: DCT по 32×32, берём 8×8 низких частот."""
    vals = [float(p) for p in pixels]
    n = size
    dct = [[0.0] * n for _ in range(n)]
    for u in range(8):
        cu = math.sqrt(1 / n) if u == 0 else math.sqrt(2 / n)
        for v in range(8):
            cv = math.sqrt(1 / n) if v == 0 else math.sqrt(2 / n)
            acc = 0.0
            for y in range(n):
                for x in range(n):
                    acc += vals[y * n + x] * math.cos((2 * x + 1) * u * math.pi / (2 * n)) * math.cos(
                        (2 * y + 1) * v * math.pi / (2 * n)
                    )
            dct[u][v] = cu * cv * acc
    flat = [dct[u][v] for u in range(8) for v in range(8)]
    flat[0] = 0.0
    median = sorted(flat)[len(flat) // 2]
    bits = 0
    for i, val in enumerate(flat):
        if val > median:
            bits |= 1 << i
    return f"{bits:016x}"


def hashes_from_image_bytes(data: bytes) -> dict[str, str]:
    from PIL import Image

    image = Image.open(io.BytesIO(data)).convert("L")
    small = image.resize((8, 8), Image.Resampling.BILINEAR)
    dsmall = image.resize((9, 8), Image.Resampling.BILINEAR)
    psmall = image.resize((32, 32), Image.Resampling.BILINEAR)
    ahash = _avg_hash(list(small.getdata()), 8, 8)
    dhash = _dhash(list(dsmall.getdata()), 9, 8)
    phash = _phash(list(psmall.getdata()), 32)
    md5 = hashlib.md5(data).hexdigest()
    return {"ahash": ahash, "dhash": dhash, "phash": phash, "md5": md5}


def format_nicks(nicks: Iterable[str]) -> str:
    items = [f"@{normalize_nick(n)}" for n in nicks if n]
    return "\n".join(items)


def days_left(seconds: float) -> int:
    if seconds <= 0:
        return 0
    return max(1, math.ceil(seconds / 86400))


def recheck_wait_text(seconds: float) -> str:
    days = days_left(seconds)
    word = "день" if days == 1 else ("дня" if days < 5 else "дней")
    return f"Следующая проверка через {days} {word}."
