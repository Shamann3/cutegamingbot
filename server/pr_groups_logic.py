# -*- coding: utf-8 -*-
"""Пиар в группах — чистая логика: статусы, раскол посева, кто новый, тексты.

Без БД и без Telegram. Бот и админка импортируют отсюда одно и то же,
чтобы очередь, кнопки и выплаты не разъехались.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Iterable, Optional

from pr_groups_design import (
    CONFIRM_EMOJI,
    EMOJI_ADMIN,
    EMOJI_EARN,
    EMOJI_GROUPS,
    EMOJI_HUB,
    EMOJI_OWNER,
    EMOJI_PHOTO,
    EMOJI_PUBLIC,
    EMOJI_RECO,
    GIFT_EMOJI,
    LINK_HINT as LINK_HINT_HTML,
    NEED_PHOTO,
    PALETTE,
    PHOTO_STEPS,
    SCREENS,
    STATUS_EMOJI_NO,
    STATUS_EMOJI_OK,
    STATUS_EMOJI_WAIT,
    emoji_html as design_emoji_html,
)

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

SHARE_PCT = 0.35
WEEKLY_SEED_PCT = 0.15
MAX_LIVE_SEEDS = 2
MAX_PENDING = 2
DEFAULT_TERM_DAYS = 14
PHOTOS_REQUIRED = 3
PHOTO_HOURS = 24
CONFIRM_HOURS = 24
FIRST_NO_HOLD_HOURS = 24
REJECT_HOLD_HOURS = 48
BAN_DAYS = 31
NEW_IDLE_DAYS = 7
BROKE_BELOW = 5
GIFT_MIN = 5
GIFT_MAX = 12
GIFT_IDEAL = 8
NIKA_THRESHOLD = 3
NIKA_STEP = 20
NIKA_INTERVAL_HOURS = 12
NIKA_CAP_PCT = 0.50

ROLE_OWNER = "owner"
ROLE_RECO = "reco"

ST_PHOTOS = "photos"
ST_WAIT_CONFIRM = "wait_confirm"
ST_CONFIRM_RETRY = "confirm_retry"
ST_PENDING = "pending"
ST_LIVE = "live"
ST_REJECTED = "rejected"
ST_CANCELLED = "cancelled"
ST_EXPIRED = "expired"
ST_BURNED = "burned"
ST_ENDED = "ended"
ST_ACCEPTING = "accepting"
ST_FULFILLING = "fulfilling"

OPEN_STATUSES = frozenset({
    ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY, ST_PENDING, ST_ACCEPTING, ST_FULFILLING, ST_LIVE,
})
QUEUE_STATUSES = frozenset({ST_PENDING})
LIVE_STATUSES = frozenset({ST_LIVE, ST_ACCEPTING, ST_FULFILLING})
IN_PROGRESS_STATUSES = frozenset({
    ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY, ST_PENDING, ST_ACCEPTING, ST_FULFILLING, ST_LIVE,
})
MINE_STATUSES = frozenset(
    IN_PROGRESS_STATUSES | {ST_ENDED, ST_BURNED, ST_REJECTED, ST_EXPIRED}
)
HOLD_GROUP_STATUSES = frozenset({
    ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY, ST_PENDING, ST_ACCEPTING, ST_FULFILLING, ST_LIVE, ST_REJECTED,
})
WEEK_SEED_STATUSES = frozenset({ST_ACCEPTING, ST_FULFILLING, ST_LIVE, ST_ENDED, ST_BURNED})

# Общие ALTER-колонки: бот и админка поднимают одну и ту же схему.
CLAIM_COLUMNS: tuple[tuple[str, str], ...] = (
    ("photos_started_at", "TIMESTAMPTZ"),
    ("photos_done_at", "TIMESTAMPTZ"),
    ("confirm_attempt", "INTEGER NOT NULL DEFAULT 0"),
    ("confirm_message_id", "BIGINT"),
    ("confirm_expires_at", "TIMESTAMPTZ"),
    ("confirm_token", "INTEGER NOT NULL DEFAULT 0"),
    ("confirmed_at", "TIMESTAMPTZ"),
    ("reject_hold_until", "TIMESTAMPTZ"),
    ("slot_hold_until", "TIMESTAMPTZ"),
    ("banned_until", "TIMESTAMPTZ"),
    ("reject_text", "TEXT"),
    ("term_days", "INTEGER"),
    ("seed_total", "INTEGER NOT NULL DEFAULT 0"),
    ("table_amount", "INTEGER NOT NULL DEFAULT 0"),
    ("pool_amount", "INTEGER NOT NULL DEFAULT 0"),
    ("pool_left", "INTEGER NOT NULL DEFAULT 0"),
    ("gift_size", "INTEGER NOT NULL DEFAULT 0"),
    ("seed_lock", "INTEGER NOT NULL DEFAULT 0"),
    ("seed_applied", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("nika_on", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("nika_topped", "INTEGER NOT NULL DEFAULT 0"),
    ("nika_last_at", "TIMESTAMPTZ"),
    ("live_until", "TIMESTAMPTZ"),
    ("accepted_at", "TIMESTAMPTZ"),
    ("ended_at", "TIMESTAMPTZ"),
    ("paid_kut", "INTEGER NOT NULL DEFAULT 0"),
    ("commission_seen", "INTEGER NOT NULL DEFAULT 0"),
    ("pending_pay", "INTEGER NOT NULL DEFAULT 0"),
    ("last_digest_at", "TIMESTAMPTZ"),
    ("freeze", "TEXT"),
    ("chat_title", "TEXT"),
    ("chat_username", "TEXT"),
    ("member_count", "INTEGER"),
    ("added_by", "BIGINT"),
    ("creator_id", "BIGINT"),
    ("joined_at", "TIMESTAMPTZ"),
)

CONFIRM_WORDS = frozenset({
    "подтверждение", "подтвердить", "подтверди", "confirm", "confirmation",
})

PHOTO_HINTS = (
    "список админов",
    "сообщение от Кут",
    "создатель группы",
)

# Кадры доказательств: тексты в pr_groups_design.PHOTO_STEPS.
HELP_WORDS = frozenset({"хелп", "help", "помощь", "?"})
LINK_MODES = frozenset({"how", "how_public", "how_admin", "wait_link"})
BOT_USERNAME = "CuteGamingBot"
STARTGROUP_RIGHTS = "delete_messages+restrict_members+pin_messages+invite_users"

_USER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
_AT_RE = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z][A-Za-z0-9_]{4,31})\b")
_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.me|telegram\.dog)/[^\s<>\"')\]]+|tg://[^\s<>\"')\]]+",
    re.I,
)
_SKIP_TME = frozenset({
    "share", "addstickers", "socks", "proxy", "iv", "boost", "login",
    "confirmphone", "setlanguage", "premium", "nft", "giftcode", "invoice",
    "addlist", "addtheme", "addemoji", "bg", "stars",
})


def startgroup_url(username: str | None = None) -> str:
    uname = str(username or BOT_USERNAME).strip().lstrip("@") or BOT_USERNAME
    return f"https://t.me/{uname}?startgroup=pr&admin={STARTGROUP_RIGHTS}"


def _trim_url(url: str) -> str:
    return str(url or "").strip().rstrip(".,;:!?)]}'\"")


def _normalize_chat_id(raw: str) -> int | None:
    compact = str(raw or "").replace(" ", "").replace("\u00a0", "")
    if not compact or not compact.lstrip("-").isdigit():
        return None
    digits = compact.lstrip("-")
    if len(digits) < 6 or len(digits) > 20:
        return None
    n = int(compact)
    if compact.startswith("-"):
        return n
    if compact.startswith("100") and len(compact) >= 13:
        return -n
    return int(f"-100{compact}")


def _username_ref(name: str | None) -> dict[str, str] | None:
    value = str(name or "").strip().lstrip("@")
    if not _USER_RE.fullmatch(value):
        return None
    return {"kind": "username", "value": value}


def _id_ref(raw: str | int) -> dict[str, Any] | None:
    chat_id = _normalize_chat_id(str(raw))
    if chat_id is None:
        return None
    return {"kind": "id", "value": str(chat_id), "chat_id": chat_id}


def _invite_ref(value: str) -> dict[str, str]:
    return {"kind": "invite", "value": str(value)}


def _parse_tme_path(path: str) -> dict[str, Any] | None:
    from urllib.parse import unquote

    raw = _trim_url(unquote(str(path or "")))
    if "?" in raw:
        raw = raw.split("?", 1)[0]
    if "#" in raw:
        raw = raw.split("#", 1)[0]
    parts = [p for p in raw.strip("/").split("/") if p]
    if not parts:
        return None
    first = parts[0]
    low = first.lower()
    if first.startswith("+"):
        return _invite_ref(first)
    if low == "joinchat":
        token = parts[1] if len(parts) > 1 else first
        return _invite_ref(token)
    if low == "c":
        if len(parts) >= 2:
            return _id_ref(parts[1])
        return None
    if low == "s" and len(parts) >= 2:
        first = parts[1]
        low = first.lower()
    if low in _SKIP_TME:
        return None
    return _username_ref(first)


def _parse_tg_scheme(url: str) -> dict[str, Any] | None:
    from urllib.parse import parse_qs, unquote, urlparse

    parsed = urlparse(_trim_url(url))
    query = parse_qs(parsed.query)
    host = (parsed.netloc or parsed.path.lstrip("/").split("/", 1)[0]).lower()
    if host in {"resolve", "privatepost"}:
        domain = (query.get("domain") or [None])[0]
        ref = _username_ref(domain)
        if ref:
            return ref
    chat_raw = (query.get("chat_id") or query.get("channel") or [None])[0]
    if chat_raw:
        ref = _id_ref(unquote(str(chat_raw)))
        if ref:
            return ref
    invite = (query.get("invite") or [None])[0]
    if invite or host == "join":
        return _invite_ref(unquote(str(invite or "")))
    return None


def _parse_http_tme(url: str) -> dict[str, Any] | None:
    from urllib.parse import unquote

    raw = _trim_url(unquote(url))
    match = re.search(
        r"(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.me|telegram\.dog)/(.+)$",
        raw,
        re.I,
    )
    if not match:
        return None
    return _parse_tme_path(match.group(1))


def parse_group_ref(text: str | None) -> dict[str, Any] | None:
    """Любая ссылка: @username, t.me, t.me/c/id, tg://, голый id. Не имя и не пересылка."""
    raw = str(text or "").strip()
    if not raw:
        return None
    for match in _URL_RE.finditer(raw):
        url = _trim_url(match.group(0))
        parsed = _parse_tg_scheme(url) if url.lower().startswith("tg:") else _parse_http_tme(url)
        if parsed:
            return parsed
    found_at = _AT_RE.search(raw)
    if found_at:
        return _username_ref(found_at.group(1))
    compact = raw.replace(" ", "").replace("\u00a0", "")
    if compact.lstrip("-").isdigit():
        return _id_ref(compact)
    return None


def extract_group_ref(*, text: str = "", urls: list[str] | None = None) -> dict[str, Any] | None:
    for blob in [*(urls or []), text]:
        ref = parse_group_ref(blob)
        if ref:
            return ref
    return None


def chat_id_from_ref(ref: dict[str, Any] | None) -> int | None:
    if not ref:
        return None
    kind = str(ref.get("kind") or "")
    if kind in {"id", "internal"}:
        if ref.get("chat_id") is not None:
            try:
                return int(ref["chat_id"])
            except (TypeError, ValueError):
                return None
        return _normalize_chat_id(str(ref.get("value") or ""))
    return None


def looks_like_group_ref(text: str | None) -> bool:
    return parse_group_ref(text) is not None

DEFAULT_REJECT_REASONS: list[dict[str, str]] = [
    {"id": "already_was", "label": "Уже был Кут"},
    {"id": "not_admin", "label": "Бот не администратор"},
    {"id": "not_public", "label": "Нет открытого @username"},
    {"id": "too_small", "label": "Мало людей"},
    {"id": "farm", "label": "Пустышка / накрутка"},
    {"id": "dead", "label": "Мёртвая группа"},
    {"id": "bad_link", "label": "Неверная ссылка"},
    {"id": "adult", "label": "18+"},
    {"id": "insult", "label": "Оскорбление"},
]


def theme_emoji_html(kind: str) -> str:
    tag = PALETTE.get(str(kind or "")) or PALETTE["wait"]
    return design_emoji_html(tag)


def status_emoji_html(kind: str) -> str:
    return theme_emoji_html(kind)


def extra(text: str) -> str:
    """Только дополнительная информация: цитата, жирная и курсив."""
    t = str(text or "").strip()
    if not t:
        return ""
    return f"<blockquote><b><i>{t}</i></b></blockquote>"


def do_next(text: str) -> str:
    """Главное действие на экране — жирный текст, не цитата."""
    t = str(text or "").strip()
    if not t:
        return ""
    return f"<b>{t}</b>"


def _bold_line(text: str) -> str:
    t = str(text or "").strip()
    if not t:
        return ""
    if t.startswith("<blockquote"):
        return t
    if t.startswith("<b>") and t.endswith("</b>"):
        return t
    return f"<b>{t}</b>"


class _SafeFmt(dict):
    def __missing__(self, key: str) -> str:
        return ""


def fill_design(text: Any, values: dict[str, Any] | None = None) -> str:
    if text is None:
        return ""
    if isinstance(text, (list, tuple)):
        lines = [fill_design(item, values) for item in text]
        return "\n".join(line for line in lines if line)
    return str(text).format_map(_SafeFmt(values or {}))


def pr_screen(
    emoji: str,
    title: str,
    body: str = "",
    extra_text: str = "",
    next_text: str = "",
) -> str:
    """Заголовок с премиум-эмодзи, факты жирным, цитата только для доп. сведений."""
    mark = theme_emoji_html(emoji) if emoji in PALETTE else design_emoji_html(emoji)
    head = f"{mark} {_bold_line(title)}".strip() if mark else _bold_line(title)
    parts = [head] if head else []
    if body:
        for chunk in str(body).split("\n"):
            line = _bold_line(chunk)
            if line:
                parts.append(line)
    if extra_text:
        quoted = extra(extra_text)
        if quoted:
            parts.append(quoted)
    if next_text:
        action = do_next(next_text)
        if action:
            parts.append(action)
    return "\n".join(parts)


def render_design(name: str, values: dict[str, Any] | None = None, **overrides: Any) -> str:
    spec = SCREENS[name]
    vals = {"link_hint": LINK_HINT_HTML}
    vals.update(values or {})
    emoji = overrides.get("emoji") or spec.get("emoji") or ""
    emoji_by = spec.get("emoji_by") or {}
    if emoji_by and vals.get("emoji_key"):
        emoji = emoji_by.get(vals["emoji_key"], emoji)
    extra_text = overrides["extra"] if "extra" in overrides else spec.get("extra") or ""
    extra_by = spec.get("extra_by") or {}
    if "extra" not in overrides and isinstance(extra_by, dict) and vals.get("extra_key"):
        extra_text = extra_by.get(vals["extra_key"], extra_text)
    next_text = overrides["next"] if "next" in overrides else spec.get("next") or ""
    next_by = spec.get("next_by") or {}
    if "next" not in overrides and isinstance(next_by, dict) and vals.get("next_key") is not None:
        next_text = next_by.get(str(vals["next_key"]), next_by.get("default", next_text))
    if "next" not in overrides and vals.get("has_items") is False and spec.get("next_empty"):
        next_text = spec["next_empty"]
    body = overrides["body"] if "body" in overrides else spec.get("body") or ""
    return pr_screen(
        emoji,
        fill_design(spec.get("title") or "", vals),
        fill_design(body, vals),
        fill_design(extra_text, vals),
        fill_design(next_text, vals),
    )


def card_emoji_kind(status: str, freeze: str | None = None, *, owner: bool = False) -> str:
    if pause_label(freeze):
        return "wait"
    st = str(status or "")
    if st == ST_PHOTOS:
        return "photos"
    if st in {ST_REJECTED, ST_BURNED}:
        return "error"
    if st == ST_LIVE:
        return "live_owner" if owner else "live_reco"
    return "wait"


_PREMIUM_ID_RE = re.compile(r"emoji-id=['\"](\d+)['\"]")


def premium_emoji_ids(html: str | None) -> list[str]:
    return _PREMIUM_ID_RE.findall(str(html or ""))


def mention_html(user_id: int, name: str) -> str:
    label = escape((name or "игрок").strip() or "игрок")
    return f'<a href="tg://user?id={int(user_id)}">{label}</a>'


def group_link(username: str | None, chat_id: int | None = None) -> str:
    uname = str(username or "").strip().lstrip("@")
    if uname:
        return f"https://t.me/{uname}"
    if chat_id:
        return f"https://t.me/c/{str(abs(int(chat_id)))[3:]}" if str(chat_id).startswith("-100") else ""
    return ""


def clamp_int(value: Any, low: int, high: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = low
    if n < low:
        return low
    if n > high:
        return high
    return n


def expected_newcomers(member_count: int) -> int:
    members = max(0, int(member_count or 0))
    raw = round(members * 0.06)
    return clamp_int(raw, 3, 40)


def recommend_split(total: int, member_count: int) -> dict[str, int]:
    """Умный раскол: сначала баланс чата на выплаты, остаток — подарки новичкам."""
    total = max(0, int(total or 0))
    expected = expected_newcomers(member_count)
    if total <= 0:
        return {
            "total": 0, "table": 0, "pool": 0, "gift": GIFT_IDEAL,
            "slots": 0, "expected": expected,
        }
    table_need = max(6 * GIFT_IDEAL, 30)
    if int(member_count or 0) < 15:
        table_need = max(table_need, 40)
    table_need = min(table_need, max(total // 2, 0))
    min_pool = GIFT_MIN
    table = table_need
    if total - table < min_pool and total > min_pool:
        table = total - min_pool
    if table < 0:
        table = 0
    if table > total:
        table = total
    pool = total - table
    if expected > 0 and pool // expected >= GIFT_IDEAL:
        gift = min(GIFT_MAX, pool // expected)
    else:
        gift = GIFT_MIN if pool >= GIFT_MIN else max(1, pool)
    if gift < 1:
        gift = 1
    slots = pool // gift if gift else 0
    return {
        "total": total,
        "table": table,
        "pool": pool,
        "gift": gift,
        "slots": slots,
        "expected": expected,
    }


def recommend_seed(member_count: int, spendable: int) -> int:
    expected = expected_newcomers(member_count)
    raw = expected * GIFT_IDEAL * 2
    raw = clamp_int(raw, 40, 400)
    return min(raw, max(0, int(spendable or 0)))


def spendable_amount(ladder_free: int, nika_need: int) -> int:
    return max(0, int(ladder_free or 0) - int(nika_need or 0))


def weekly_seed_budget(spendable: int) -> int:
    return max(0, int(round(int(spendable or 0) * WEEKLY_SEED_PCT)))


def nika_step_amount(*, table_origin: int, chat_balance: int, already_topped: int) -> int:
    """До 20 кут или дыра до исходного баланса группы. Потолок срока — половина баланса группы."""
    origin = max(0, int(table_origin or 0))
    bal = max(0, int(chat_balance or 0))
    topped = max(0, int(already_topped or 0))
    gap = max(0, origin - bal)
    cap_left = max(0, int(origin * NIKA_CAP_PCT) - topped)
    return max(0, min(NIKA_STEP, gap, cap_left))


def left_days_hint(days: Optional[int]) -> Optional[dict[str, Any]]:
    if days is None:
        return None
    n = int(days)
    if n < 7:
        tone, hint = "hot", "скорее нет"
    elif n <= 30:
        tone, hint = "warn", "осторожно"
    else:
        tone, hint = "ok", "можно смотреть"
    return {"days": n, "tone": tone, "hint": hint, "label": f"Уходил {n} дн. назад · {hint}"}


def classify_player(
    *,
    last_real_ts: Optional[float],
    first_seen_ts: Optional[float],
    joined_ts: float,
) -> str:
    """Кто новый — только жизнь ДО входа Кута.

    Игра после T0 не делает человека «своим»: иначе первая ставка
    обнуляет выплату пригласившему. last_real/first_seen после T0
    игнорируются.
    """
    week = NEW_IDLE_DAYS * 86400
    t0 = float(joined_ts)
    last = float(last_real_ts) if last_real_ts else None
    seen = float(first_seen_ts) if first_seen_ts else None
    last_before = last if last is not None and last < t0 else None
    seen_before = seen if seen is not None and seen < t0 else None
    if last_before is not None and last_before >= t0 - week:
        return "active"
    if last_before is not None:
        return "dormant"
    if seen_before is not None and seen_before < t0 - week:
        return "ghost"
    if seen_before is not None:
        return "warming"
    return "brand"


def is_new_class(kind: str) -> bool:
    return kind in {"dormant", "ghost", "brand"}


def is_broke(balance: int, gift_locked: int = 0) -> bool:
    free = int(balance or 0) - int(gift_locked or 0)
    return free < BROKE_BELOW


def free_balance(balance: int, gift_locked: int) -> int:
    return max(0, int(balance or 0) - int(gift_locked or 0))


def withdrawable_chat(balance: int, seed_lock: int) -> int:
    return max(0, int(balance or 0) - int(seed_lock or 0))


def promoter_cut(commission: int, already_paid: int, commission_seen: int) -> int:
    """35% этой комиссии, но всего не больше 35% накопленной и не больше самой комиссии."""
    piece = int(round(int(commission or 0) * SHARE_PCT))
    cap = int(round(int(commission_seen or 0) * SHARE_PCT))
    left = max(0, cap - int(already_paid or 0))
    return max(0, min(piece, left, int(commission or 0)))


def looks_like_confirm(text: str) -> bool:
    raw = " ".join(str(text or "").lower().split())
    return raw in CONFIRM_WORDS


def photo_hint(index: int) -> str:
    if 0 <= index < len(PHOTO_HINTS):
        return PHOTO_HINTS[index]
    return "фото"


def moscow_day_start(now: datetime | None = None) -> datetime:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    try:
        zone = ZoneInfo("Europe/Moscow") if ZoneInfo else timezone(timedelta(hours=3))
    except Exception:
        zone = timezone(timedelta(hours=3))
    local = moment.astimezone(zone)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


def clip_btn(text: str, limit: int = 64) -> str:
    raw = " ".join(str(text or "").split())
    if len(raw) <= limit:
        return raw
    if limit <= 1:
        return "…"
    return raw[: limit - 1] + "…"


def kut_amount(n: int) -> str:
    return f"{max(0, int(n or 0))} кут"


def is_owner_claim(row: dict[str, Any] | None) -> bool:
    return str((row or {}).get("role") or "") == ROLE_OWNER


def claim_days_left(row: dict[str, Any] | None, now: datetime | None = None) -> Optional[int]:
    until = (row or {}).get("live_until")
    if until is None:
        return None
    if getattr(until, "tzinfo", None) is None:
        until = until.replace(tzinfo=timezone.utc)
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max(0, int((until - moment).total_seconds() // 86400))


def pause_label(freeze: str | None) -> str:
    kind = str(freeze or "").strip().lower()
    if kind == "admin":
        return "пауза: Кут нужна админка"
    if kind == "public":
        return "пауза: группа стала закрытой"
    return ""


def pause_hint(freeze: str | None) -> str:
    kind = str(freeze or "").strip().lower()
    if kind == "admin":
        return "Верните Кут в администраторы — снова начнёт капать."
    if kind == "public":
        return "Сделайте группу открытой с @адресом — снова начнёт капать."
    return ""


def claim_status_label(status: str, freeze: str | None = None) -> str:
    paused = pause_label(freeze)
    if paused:
        return paused
    return {
        ST_PHOTOS: "нужны 3 фото",
        ST_WAIT_CONFIRM: "ждём Да от создателя",
        ST_CONFIRM_RETRY: "ещё один шанс у создателя",
        ST_PENDING: "заявку смотрят",
        ST_ACCEPTING: "заявку смотрят",
        ST_FULFILLING: "заявку смотрят",
        ST_LIVE: "идёт заработок",
        ST_ENDED: "срок вышел",
        ST_REJECTED: "не приняли",
        ST_BURNED: "Кут убрали из группы",
        ST_EXPIRED: "время вышло",
        ST_CANCELLED: "заявку сняли",
    }.get(str(status or ""), str(status or ""))


def claim_status_short(status: str, freeze: str | None = None) -> str:
    kind = str(freeze or "").strip().lower()
    if kind == "admin":
        return "пауза"
    if kind == "public":
        return "закрыта"
    return {
        ST_PHOTOS: "фото",
        ST_WAIT_CONFIRM: "ждём Да",
        ST_CONFIRM_RETRY: "ещё шанс",
        ST_PENDING: "смотрят",
        ST_ACCEPTING: "смотрят",
        ST_FULFILLING: "смотрят",
        ST_LIVE: "идёт",
        ST_ENDED: "срок",
        ST_REJECTED: "не приняли",
        ST_BURNED: "убрали",
        ST_EXPIRED: "время",
        ST_CANCELLED: "сняли",
    }.get(str(status or ""), "группа")


def list_row_money(row: dict[str, Any] | None) -> str:
    data = row or {}
    if is_owner_claim(data):
        gifts = int(data.get("gifts") or 0)
        if gifts or str(data.get("status") or "") in LIVE_STATUSES:
            return f"подарков: {gifts}"
        return ""
    paid = int(data.get("paid_kut") or 0)
    if paid:
        return kut_amount(paid)
    return ""


def claim_button_label(row: dict[str, Any] | None) -> str:
    data = row or {}
    title = str(data.get("chat_title") or data.get("title") or "группа").strip() or "группа"
    short = claim_status_short(str(data.get("status") or ""), data.get("freeze"))
    money = list_row_money(data)
    raw = f"{title} · {short} · {money}" if money else f"{title} · {short}"
    return clip_btn(raw)


def _titles_line(rows: list[dict[str, Any]], reason: str) -> str:
    names = []
    for row in rows[:3]:
        names.append(escape(str(row.get("title") or "группа")))
    if not names:
        return ""
    return f"«{'», «'.join(names)}» — {reason}."


def looks_like_help(text: str | None) -> bool:
    return str(text or "").strip().lower() in HELP_WORDS


# ---------------------------------------------------------------------------
# Экраны читают pr_groups_design.SCREENS. Здесь только данные и выбор варианта.
# ---------------------------------------------------------------------------

def _seen_groups_extra(no_public: list | None, no_admin: list | None) -> str:
    bits = []
    line_pub = _titles_line(list(no_public or []), "нет @адреса")
    line_adm = _titles_line(list(no_admin or []), "Кут не админ")
    if line_pub:
        bits.append(line_pub)
    if line_adm:
        bits.append(line_adm)
    return " ".join(bits)


def _seen_value(no_public: list | None = None, no_admin: list | None = None) -> str:
    seen = _seen_groups_extra(no_public, no_admin)
    return f" {seen}" if seen else ""


def text_entry() -> str:
    return render_design("hub")


def text_choose_role() -> str:
    return render_design("choose")


def text_how(*, intent: str = "", no_public: list | None = None, no_admin: list | None = None) -> str:
    name = "how_reco" if intent == ROLE_RECO else "how_owner"
    return render_design(name, {"seen": _seen_value(no_public, no_admin)})


def text_how_public() -> str:
    return render_design("how_public")


def text_how_admin(*, intent: str = "") -> str:
    return render_design("how_admin_reco" if intent == ROLE_RECO else "how_admin")


def text_need_public(title: str = "") -> str:
    return render_design("need_public", {"name": escape(title or "эта группа")})


def text_need_admin(title: str = "", *, intent: str = "") -> str:
    name = "need_admin_reco" if intent == ROLE_RECO else "need_admin"
    return render_design(name, {"name": escape(title or "эта группа")})


def text_bot_joined(title: str, *, has_intent: bool = False) -> str:
    key = "bot_joined_intent" if has_intent else "bot_joined"
    return render_design(key, {"name": escape(title or "группа")})


def text_need_link() -> str:
    return render_design("need_link")


def text_forward_no_group() -> str:
    return render_design("forward_no_group")


def text_link_invite() -> str:
    return render_design("link_invite")


def text_group_not_found() -> str:
    return render_design("group_not_found")


def text_bot_not_there(title: str = "", *, intent: str = "") -> str:
    name = "bot_not_there_reco" if intent == ROLE_RECO else "bot_not_there"
    return render_design(name, {"name": escape(title or "эта группа")})


def text_cant_add() -> str:
    return render_design("cant_add")


def text_not_in_group(title: str = "") -> str:
    return render_design("not_in_group", {"name": escape(title or "эта группа")})


def text_not_a_group() -> str:
    return render_design("not_a_group")


def text_pick_group() -> str:
    return render_design("pick_group")


def text_pick_role(title: str) -> str:
    return render_design("pick_role", {"name": escape(title or "группа")})


def text_owner_bridge(title: str) -> str:
    return render_design("owner_bridge", {"name": escape(title or "группа")})


def text_reco_bridge(title: str) -> str:
    return render_design("reco_bridge", {"name": escape(title or "группа")})


def text_not_owner_switch(title: str = "") -> str:
    return render_design("not_owner_switch", {"name": escape(title or "эта группа")})


def text_are_owner_switch(title: str = "") -> str:
    return render_design("are_owner_switch", {"name": escape(title or "эта группа")})


def text_wrong_owner() -> str:
    return text_not_owner_switch()


def text_wait_photo(index: int, have: int) -> str:
    nxt = have if 0 <= have < PHOTOS_REQUIRED else min(int(index), PHOTOS_REQUIRED - 1)
    if 0 <= nxt < len(PHOTO_STEPS):
        step = PHOTO_STEPS[nxt]
        what = step["what"]
        need = step["need"]
    else:
        what = escape(photo_hint(nxt))
        need = ""
    body = f"Есть {have} из {PHOTOS_REQUIRED}.\n{what}" if have > 0 else what
    return render_design("wait_photo", {
        "step": have + 1,
        "total": PHOTOS_REQUIRED,
        "body": body,
        "need": need,
        "tail": "",
        "next_key": str(min(max(int(have), 0), 2)),
    })


def text_photo_progress(have: int) -> str:
    return text_wait_photo(have, have)


def text_need_photo(kind: str = "") -> str:
    spec = NEED_PHOTO.get(kind or "") or NEED_PHOTO[""]
    return render_design("need_photo", {
        "title": spec["title"],
        "extra": spec["extra"],
        "tail": spec["next"],
    })


def text_photos_expired() -> str:
    return render_design("photos_expired")


def text_after_photos_owner() -> str:
    return text_after_proofs_owner()


def text_after_proofs_owner() -> str:
    return render_design("after_proofs_owner")


def text_after_proofs_reco() -> str:
    return render_design("after_proofs_reco")


def text_after_photos_reco(title: str = "") -> str:
    return render_design("after_photos_reco", {"name": escape(title or "группу")})


def text_wrote_confirm() -> str:
    return render_design("wrote_confirm")


def _earnings_key(*, total: int, today: int, count: int, live: bool) -> str:
    if count <= 0:
        return "empty"
    if live and total > 0:
        return "live_paid"
    if live:
        return "live"
    if today > 0:
        return "today"
    return "pending"


def text_earnings(
    rows: list[dict[str, Any]] | None = None,
    *,
    total: int = 0,
    today: int = 0,
    live: bool = False,
) -> str:
    items = list(rows or [])
    name = "earnings" if live or int(total) > 0 else "mine"
    key = _earnings_key(total=int(total), today=int(today), count=len(items), live=live)
    spec = SCREENS[name]
    barnum = (spec.get("extra_by") or {}).get(key) or ""
    return render_design(name, {
        "total": kut_amount(total),
        "today": kut_amount(today),
        "barnum": barnum,
        "has_items": bool(items),
    })


def text_mine(
    rows: list[dict[str, Any]] | None = None,
    *,
    total: int = 0,
    today: int = 0,
    live: bool = False,
) -> str:
    return text_earnings(rows, total=total, today=today, live=live)


def _card_status_key(status: str, freeze: str | None) -> str:
    if pause_hint(freeze):
        return "pause"
    st = str(status or "")
    if st == ST_PHOTOS:
        return "photos"
    if st in {ST_WAIT_CONFIRM, ST_CONFIRM_RETRY}:
        return "wait_confirm"
    if st in {ST_PENDING, ST_ACCEPTING, ST_FULFILLING}:
        return "pending"
    if st == ST_LIVE:
        return "live"
    if st == ST_ENDED:
        return "ended"
    if st == ST_REJECTED:
        return "rejected"
    if st == ST_BURNED:
        return "burned"
    return "default"


def text_group_card(
    claim: dict[str, Any] | None,
    *,
    today: int = 0,
    newcomers: int = 0,
    gifts: int = 0,
    chat_balance: int | None = None,
) -> str:
    data = claim or {}
    name = escape(str(data.get("chat_title") or data.get("title") or "группа"))
    status = str(data.get("status") or "")
    freeze = data.get("freeze")
    owner = is_owner_claim(data)
    spec = SCREENS["card"]
    key = _card_status_key(status, freeze)
    values: dict[str, Any] = {
        "name": name,
        "status": escape(claim_status_label(status, freeze)),
        "gifts": int(gifts or 0),
        "paid": kut_amount(data.get("paid_kut")),
        "today": kut_amount(today),
        "newcomers": int(newcomers or 0),
        "hint": pause_hint(freeze),
        "reason": escape(str(data.get("reject_text") or "").strip()) or "Заявку не приняли.",
        "emoji_key": card_emoji_kind(status, freeze, owner=owner),
        "extra_key": key,
        "next_key": key,
        "balance": kut_amount(chat_balance) if chat_balance is not None else "",
        "days": "",
    }
    days = claim_days_left(data)
    if days is not None and status in LIVE_STATUSES:
        values["days"] = days
    templates = spec.get("facts_owner") if owner else spec.get("facts_reco")
    facts: list[str] = []
    for tmpl in list(templates or []):
        if "{balance}" in tmpl and chat_balance is None:
            continue
        if "{days}" in tmpl and values["days"] == "":
            continue
        line = fill_design(tmpl, values)
        if line:
            facts.append(line)
    values["facts"] = "\n".join(facts)
    extra_tmpl = (spec.get("extra_by") or {}).get(key) or spec.get("extra") or ""
    next_tmpl = (spec.get("next_by") or {}).get(key) or (spec.get("next_by") or {}).get("default") or spec.get("next") or ""
    return render_design("card", values, extra=fill_design(extra_tmpl, values), next=fill_design(next_tmpl, values))


def text_cancelled() -> str:
    return render_design("cancelled")


def text_confirm_prompt(user_id: int, name: str) -> str:
    return render_design("confirm", {"who": mention_html(user_id, name)})


def text_confirm_yes() -> str:
    return render_design("confirm_yes")


def text_confirm_no_first() -> str:
    return render_design("confirm_no_first")


def text_confirm_no_second() -> str:
    return render_design("confirm_no_second")


def text_not_your_claim() -> str:
    return render_design("not_your_claim")


def text_not_creator() -> str:
    return render_design("not_creator")


def text_confirm_expired() -> str:
    return render_design("confirm_expired")


def text_wrong_group() -> str:
    return render_design("wrong_group")


def text_need_photos_first() -> str:
    return render_design("need_photos_first")


def text_accepted(term_days: int, *, role: str = "") -> str:
    name = "accepted_owner" if str(role or "") == ROLE_OWNER else "accepted"
    return render_design(name, {"days": int(term_days or DEFAULT_TERM_DAYS)})


def text_digest(
    *,
    newcomers: int,
    commission: int = 0,
    paid: int,
    days_left: int,
    title: str = "",
) -> str:
    return render_design("digest", {
        "name": escape(title or "группы"),
        "newcomers": int(newcomers or 0),
        "paid": kut_amount(paid),
        "days": int(days_left or 0),
        "note": "",
        "extra_key": "paid" if int(paid or 0) > 0 else "empty",
    })


def text_gift(user_id: int, name: str, amount: int) -> str:
    return render_design("gift", {
        "who": mention_html(user_id, name),
        "amount": int(amount),
    })


def text_gift_locked() -> str:
    return render_design("gift_locked")


def text_term_end() -> str:
    return render_design("term_end")


def text_kicked() -> str:
    return render_design("kicked")


def text_rejected(reason: str, *, can_fix: bool) -> str:
    name = "rejected_fix" if can_fix else "rejected"
    body = escape((reason or "Не приняли.").strip() or "Не приняли.")
    return render_design(name, {"reason": body})


def text_two_pending() -> str:
    return render_design("two_pending")


def text_two_live() -> str:
    return render_design("two_live")


def text_banned_31() -> str:
    return render_design("banned_31")


def text_freeze_admin() -> str:
    return render_design("freeze_admin")


def text_freeze_public() -> str:
    return render_design("freeze_public")


def text_group_busy(*, owner: bool = False) -> str:
    return render_design("group_busy_owner" if owner else "group_busy")


def text_confirm_timeout() -> str:
    return render_design("confirm_timeout")


def text_owner_no_confirm() -> str:
    return render_design("owner_no_confirm")


def text_no_groups() -> str:
    return text_how()


def text_resume_claim(title: str, status: str, freeze: str | None = None) -> str:
    return render_design("resume", {
        "name": escape(title or "группа"),
        "status": escape(claim_status_label(status, freeze)),
        "emoji_key": card_emoji_kind(status, freeze),
    })

def reject_text_from(reasons: Iterable[dict[str, str]] | None, custom: str, catalog: list[dict[str, str]]) -> str:
    labels = []
    ids = {str(r.get("id")) for r in (reasons or []) if r}
    for item in catalog:
        if item.get("id") in ids and item.get("label"):
            labels.append(str(item["label"]))
    own = " ".join(str(custom or "").split())
    if own:
        labels.append(own)
    return " · ".join(labels) or "Не приняли."
