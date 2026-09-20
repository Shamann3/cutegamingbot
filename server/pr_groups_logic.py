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

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

STATUS_EMOJI_OK = "5339112148175959615"
STATUS_EMOJI_WAIT = "5339082633160703625"
STATUS_EMOJI_NO = "5337017423906226569"
GIFT_EMOJI = "5199552030615558774"
CONFIRM_EMOJI = "5424616516018537963"

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

# Один экран — один кадр. HTML уже безопасный.
PHOTO_STEPS: tuple[dict[str, str], ...] = (
    {
        "what": "Список администраторов группы.",
        "need": "На кадре должен быть <code>@CuteGamingBot</code>.",
    },
    {
        "what": "Сообщение от Кут в этой группе.",
        "need": "Нужно видеть, что бот там отвечает.",
    },
    {
        "what": "Кто создатель группы.",
        "need": "В списке админов — человек с короной.",
    },
)

HELP_WORDS = frozenset({"хелп", "help", "помощь", "?"})
LINK_MODES = frozenset({"how", "how_public", "how_admin", "wait_link"})
BOT_USERNAME = "CuteGamingBot"
STARTGROUP_RIGHTS = "delete_messages+restrict_members+pin_messages+invite_users"
LINK_HINT_HTML = "<code>@группа</code> · <code>t.me/группа</code> · <code>t.me/c/id</code> · id"

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


def status_emoji_html(kind: str) -> str:
    eid, face = {
        "ok": (STATUS_EMOJI_OK, "🟢"),
        "wait": (STATUS_EMOJI_WAIT, "🟡"),
        "no": (STATUS_EMOJI_NO, "🔴"),
    }.get(kind, (STATUS_EMOJI_WAIT, "🟡"))
    return f"<tg-emoji emoji-id='{eid}'>{face}</tg-emoji>"


_PREMIUM_ID_RE = re.compile(r"emoji-id=['\"](\d+)['\"]")


def premium_emoji_ids(html: str | None) -> list[str]:
    return _PREMIUM_ID_RE.findall(str(html or ""))


def do_next(text: str) -> str:
    return f"<blockquote><i>{text}</i></blockquote>"


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
# Экраны в личке. Один экран — одно действие. Кнопка говорит, что нажать.
# ---------------------------------------------------------------------------

def text_entry() -> str:
    return (
        f"<tg-emoji emoji-id='5452002597592382164'>📣</tg-emoji> <b>Рекомендация бота в группах</b>\n"
        "<b>Заработок - до 35% комиссии с игр новых людей.</b>\n"
        "<blockquote><i>Длительность заработка - 14 дней · с той группы, в которую вы добавите нашего бота</i></blockquote>\n"
        "<i>Нажмите, кто вы. Дальше бот покажет один шаг за раз.</i>"
    )


def text_choose_role() -> str:
    return (
        f"<tg-emoji emoji-id='5451910260090485999'>🔥</tg-emoji> <b>Кто вы?</b>\n"
        "Владелец — корона в списке админов. Если привели бота в чужой чат — вторая кнопка.\n"
        + do_next("Нажмите одну кнопку. Потом бот скажет, что прислать.")
    )


def _epsilon_watch(*, yours: bool = True) -> str:
    whose = "ваша группа" if yours else "эта группа"
    return do_next(
        f"Теперь {whose} уйдёт на проверку. Ответ придёт сюда. "
        "Нажмите «Мои группы», чтобы видеть статус, или «Назад» — в меню пиара."
    )


def _link_quote() -> str:
    return do_next(f"Пришлите сюда ссылку текстом. Подойдёт {LINK_HINT_HTML}")


def text_how(*, intent: str = "", no_public: list | None = None, no_admin: list | None = None) -> str:
    extra = []
    line_pub = _titles_line(list(no_public or []), "нет @адреса")
    line_adm = _titles_line(list(no_admin or []), "Кут не админ")
    if line_pub:
        extra.append(line_pub)
    if line_adm:
        extra.append(line_adm)
    seen = f"\n<tg-spoiler>{' '.join(extra)}</tg-spoiler>" if extra else ""
    if intent == ROLE_RECO:
        return (
            f"{status_emoji_html('wait')} <b>Чужой чат</b>\n"
            "Попросите создателя добавить @CuteGamingBot в админы.\n"
            f"{do_next(f'Когда Кут в админах — пришлите сюда ссылку. Подойдёт {LINK_HINT_HTML}')}"
            f"{seen}"
        )
    return (
        f"{status_emoji_html('wait')} <b>Ваша группа</b>\n"
        "Добавьте Кут в список администраторов в свою публичную группу.\n"
        f"{do_next(f'Нажмите «Добавить Кут», выберите чат. Потом пришлите сюда ссылку. Подойдёт {LINK_HINT_HTML}')}"
        f"{seen}"
    )


def text_how_public() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Нужен @адрес</b>\n"
        "Название сверху → <b>Управление</b> → <b>Тип группы</b> → <b>Публичная</b>.\n"
        + do_next("Сделайте группу публичной. Потом пришлите сюда ссылку.")
    )


def text_how_admin(*, intent: str = "") -> str:
    if intent == ROLE_RECO:
        return (
            f"{status_emoji_html('wait')} <b>Кут должен быть админом</b>\n"
            "Попросите создателя: <b>Управление</b> → <b>Администраторы</b> → @CuteGamingBot.\n"
            + do_next("Когда Кут в админах — пришлите сюда ссылку.")
        )
    return (
        f"{status_emoji_html('wait')} <b>Кут должен быть админом</b>\n"
        "<b>Управление</b> → <b>Администраторы</b> → @CuteGamingBot.\n"
        + do_next("Нажмите «Проверить» или пришлите ссылку сюда.")
    )


def text_need_public(title: str = "") -> str:
    name = escape(title or "эта группа")
    return (
        f"{status_emoji_html('no')} <b>У «{name}» нет @адреса</b>\n"
        "Название сверху → <b>Управление</b> → <b>Тип группы</b> → <b>Публичная</b>.\n"
        + do_next("Сделайте группу публичной. Потом пришлите сюда ссылку.")
    )


def text_need_admin(title: str = "", *, intent: str = "") -> str:
    name = escape(title or "эта группа")
    if intent == ROLE_RECO:
        return (
            f"{status_emoji_html('no')} <b>В «{name}» Кут не админ</b>\n"
            "Попросите создателя дать ему админку.\n"
            + do_next("Когда Кут в админах — пришлите сюда ссылку.")
        )
    return (
        f"{status_emoji_html('no')} <b>В «{name}» Кут не админ</b>\n"
        "<b>Управление</b> → <b>Администраторы</b> → @CuteGamingBot.\n"
        + do_next("Нажмите «Проверить» или пришлите ссылку сюда.")
    )


def text_bot_joined(title: str, *, has_intent: bool = False) -> str:
    name = escape(title or "группа")
    if has_intent:
        return (
            f"{status_emoji_html('ok')} <b>Кут зашёл в «{name}»</b>\n"
            + do_next("Если он админ — нажмите «Проверить» или пришлите ссылку сюда.")
        )
    return (
        f"{status_emoji_html('ok')} <b>Кут зашёл в «{name}»</b>\n"
        + do_next("Нажмите, кто вы: владелец или рекомендуете. Дальше бот скажет следующий шаг.")
    )


def text_need_link() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Нужна ссылка на группу</b>\n"
        "<i>В группе : сообщение → Копировать ссылку — вставьте сюда текстом</i>\n"
        f"{_link_quote()}"
    )


def text_forward_no_group() -> str:
    return (
        f"{status_emoji_html('no')} <b>Пересылка не подходит</b>\n"
        + do_next(f"Не пересылайте сообщение. Пришлите ссылку текстом. Подойдёт {LINK_HINT_HTML}")
    )


def text_link_invite() -> str:
    return (
        f"{status_emoji_html('no')} <b>Это закрытая ссылка</b>\n"
        + do_next("Нужна публичная группа. Сделайте @адрес и пришлите обычную ссылку.")
    )


def text_group_not_found() -> str:
    return (
        f"{status_emoji_html('no')} <b>Такую группу не вижу</b>\n"
        + do_next("Проверьте ссылку. Кут должен быть в чате. Потом пришлите ссылку снова.")
    )


def text_bot_not_there(title: str = "", *, intent: str = "") -> str:
    name = escape(title or "эта группа")
    if intent == ROLE_RECO:
        return (
            f"{status_emoji_html('no')} <b>Кут не в «{name}»</b>\n"
            "Попросите создателя добавить @CuteGamingBot в админы.\n"
            + do_next("Когда Кут будет в чате — пришлите сюда ссылку снова.")
        )
    return (
        f"{status_emoji_html('no')} <b>Кут не в «{name}»</b>\n"
        + do_next("Нажмите «Добавить Кут», выберите этот чат. Потом пришлите ссылку снова.")
    )


def text_cant_add() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Чужая группа</b>\n"
        "Напишите создателю: добавь @CuteGamingBot в админы.\n"
        + do_next(f"Когда Кут будет в чате — пришлите сюда ссылку. Подойдёт {LINK_HINT_HTML}")
    )


def text_not_in_group(title: str = "") -> str:
    name = escape(title or "эта группа")
    return (
        f"{status_emoji_html('no')} <b>Вас нет в «{name}»</b>\n"
        + do_next("Сначала вступите в группу. Потом вернитесь сюда и пришлите ссылку.")
    )


def text_not_a_group() -> str:
    return (
        f"{status_emoji_html('no')} <b>Это не группа</b>\n"
        + do_next("Нужен чат, не канал и не человек. Пришлите ссылку на группу.")
    )


def text_pick_group() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Какую группу сдаём?</b>\n"
        + do_next("Нажмите на нужную группу. Если список не тот — «Назад», в главное меню.")
    )


def text_pick_role(title: str) -> str:
    name = escape(title or "группа")
    return (
        f"{status_emoji_html('ok')} <b>«{name}»</b>\n"
        "Кто сдаёт эту группу?\n"
        + do_next("Своя — первая кнопка. Привели Кут — вторая. Создатель потом нажмёт Да.")
    )


def text_owner_bridge(title: str) -> str:
    name = escape(title or "группа")
    return (
        f"{status_emoji_html('ok')} <b>«{name}»</b>\n"
        "Вы создатель. Дальше 3 фото — и заявка на проверку.\n"
        + do_next("Пришлите первое фото сюда. Если друг просил добавить Кут — не забирайте заявку: пусть он пришлёт ссылку в бота.")
    )


def text_reco_bridge(title: str) -> str:
    name = escape(title or "группа")
    return (
        f"{status_emoji_html('ok')} <b>«{name}»</b>\n"
        "Вы не создатель. Чтобы доля шла вам, создатель нажмёт Да в группе.\n"
        + do_next("Пришлите первое фото сюда. Да нажимает только человек с короной в админах.")
    )


def text_not_owner_switch(title: str = "") -> str:
    name = escape(title or "эта группа")
    return (
        f"{status_emoji_html('no')} <b>Вы не владелец «{name}»</b>\n"
        + do_next("Нажмите «Я рекомендую бот в группах». Чужой чат сдаётся так.")
    )


def text_are_owner_switch(title: str = "") -> str:
    name = escape(title or "эта группа")
    return (
        f"{status_emoji_html('wait')} <b>«{name}» — ваша группа</b>\n"
        + do_next("Нажмите «Я владелец группы». Сдавайте как владелец.")
    )


def text_wrong_owner() -> str:
    return text_not_owner_switch()


def text_wait_photo(index: int, have: int) -> str:
    nxt = have if 0 <= have < PHOTOS_REQUIRED else min(int(index), PHOTOS_REQUIRED - 1)
    if 0 <= nxt < len(PHOTO_STEPS):
        step = PHOTO_STEPS[nxt]
        body = f"{step['what']}\n{step['need']}"
    else:
        body = escape(photo_hint(nxt))
    have_line = f"Есть {have} из {PHOTOS_REQUIRED}.\n" if have > 0 else ""
    tail = "Пришлите фото сюда"
    if have == 1:
        tail = "Пришлите следующее фото сюда, одним кадром."
    elif have == 2:
        tail = "Пришлите последнее фото сюда — и заявка уйдёт дальше."
    return (
        f"{status_emoji_html('wait')} <b>{have + 1} из {PHOTOS_REQUIRED}</b>\n"
        f"{have_line}{body}\n"
        f"{do_next(tail)}"
    )


def text_photo_progress(have: int) -> str:
    return text_wait_photo(have, have)


def text_need_photo(kind: str = "") -> str:
    titles = {
        "video": "Нужно фото, не видео.",
        "file": "Нужно фото, не файл.",
        "sticker": "Нужно фото из группы.",
        "text": "Нужно фото, не текст.",
        "album": "По одному фото.",
        "dup": "Это фото уже есть.",
    }
    tails = {
        "album": "Следующий кадр — отдельным сообщением.",
        "dup": "Пришлите другой кадр.",
        "sticker": "Картинка из группы — сюда.",
    }
    title = titles.get(kind or "", "Нужно именно фото.")
    tail = tails.get(kind or "", "Картинка из галереи — сюда.")
    return (
        f"{status_emoji_html('no')} <b>{escape(title)}</b>\n"
        f"<blockquote><i>{escape(tail)}</i></blockquote>"
    )


def text_photos_expired() -> str:
    return (
        f"{status_emoji_html('no')} <b>24 часа вышли</b>\n"
        + do_next("Нажмите «Сдать ещё группу» или «Назад» — и сдайте три фото заново.")
    )


def text_after_photos_owner() -> str:
    return text_after_proofs_owner()


def text_after_proofs_owner() -> str:
    return (
        f"{status_emoji_html('ok')} <b>Доказательства приняты</b>\n"
        "Новым людям проект даст куты — играть ими можно только у вас, в этой группе.\n"
        "Группа уходит на проверку. Ответ придёт сюда.\n"
        + do_next("Нажмите «Мои группы», чтобы видеть статус. «Назад» — в меню пиара.")
    )


def text_after_proofs_reco() -> str:
    return (
        f"{status_emoji_html('ok')} <b>Доказательства приняты</b>\n"
        "14 дней вам будет капать доля с игр новых людей в этой группе.\n"
        "Группа уходит на проверку. Ответ придёт сюда.\n"
        + do_next("Нажмите «Мои группы», чтобы видеть статус. «Назад» — в меню пиара.")
    )


def text_after_photos_reco(title: str = "") -> str:
    name = escape(title or "группу")
    return (
        f"{status_emoji_html('wait')} <b>Напишите в группе</b>\n"
        f"Откройте «{name}» и отправьте слово <code>подтверждение</code>.\n"
        "<i>Да нажимает только создатель (корона). 24 часа.</i>\n"
        + do_next("Нажмите «Открыть группу», напишите слово, дождитесь Да. Потом можно нажать «Я написал».")
    )


def text_wrote_confirm() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Ждём создателя</b>\n"
        "Под сообщением в группе он должен нажать Да.\n"
        + do_next("Если не нажал — откройте группу и напишите «подтверждение» ещё раз.")
    )


def _earnings_barnum(*, total: int, today: int, count: int, live: bool) -> str:
    if count <= 0:
        return "Пока тихо. Сдайте группу — и здесь появятся цифры, которые захочется открывать."
    if live and total > 0:
        return "Это уже ваши цифры. Откройте группу — будет видно, откуда капает."
    if live:
        return "Группа уже в работе. Первые куты приходят, когда новые люди начинают играть."
    if today > 0:
        return "Сегодня уже есть движение. Откройте группу — там подробнее."
    return "Вы уже сделали свою часть. Пока смотрим заявку — можно подождать здесь."


def text_earnings(
    rows: list[dict[str, Any]] | None = None,
    *,
    total: int = 0,
    today: int = 0,
    live: bool = False,
) -> str:
    items = list(rows or [])
    title = "Заработки" if live else "Мои группы"
    kind = "ok" if live or int(total) > 0 else "wait"
    barnum = _earnings_barnum(total=int(total), today=int(today), count=len(items), live=live)
    lines = [
        f"{status_emoji_html(kind)} <b>{title}</b>",
        f"<b>Всего вам пришло: {kut_amount(total)}</b>",
        f"<b>Сегодня: {kut_amount(today)}</b>",
        f"<i>{barnum}</i>",
    ]
    if items:
        lines.append(do_next("Нажмите группу — откроется карточка. «Сдать ещё группу» — новое меню."))
    else:
        lines.append(do_next("Нажмите «Сдать ещё группу» и выберите, кто вы."))
    return "\n".join(lines)


def text_mine(
    rows: list[dict[str, Any]] | None = None,
    *,
    total: int = 0,
    today: int = 0,
    live: bool = False,
) -> str:
    return text_earnings(rows, total=total, today=today, live=live)


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
    label = claim_status_label(status, freeze)
    kind = "ok" if status == ST_LIVE and not freeze else ("no" if status in {ST_REJECTED, ST_BURNED} else "wait")
    lines = [
        f"{status_emoji_html(kind)} <b>«{name}»</b>",
        f"<b>{escape(label)}</b>",
    ]
    owner = is_owner_claim(data)
    if owner:
        if chat_balance is not None:
            lines.append(f"Баланс группы: <b>{kut_amount(chat_balance)}</b>")
        lines.append(f"Подарков новым: <b>{int(gifts or 0)}</b>")
    else:
        lines.append(f"Вам уже пришло: <b>{kut_amount(data.get('paid_kut'))}</b>")
        lines.append(f"Сегодня: <b>{kut_amount(today)}</b>")
    days = claim_days_left(data)
    if days is not None and status in LIVE_STATUSES:
        lines.append(f"Осталось дней: <b>{days}</b>")
    lines.append(f"Новых людей: <b>{int(newcomers or 0)}</b>")
    hint = pause_hint(freeze)
    if hint:
        action = f"{hint} «Назад» — к списку групп."
    elif status == ST_PHOTOS:
        action = "Нажмите «Продолжить фото» и пришлите следующий кадр сюда."
    elif status in {ST_WAIT_CONFIRM, ST_CONFIRM_RETRY}:
        action = "Нажмите «Открыть группу», напишите «подтверждение», дождитесь Да."
    elif status in {ST_PENDING, ST_ACCEPTING, ST_FULFILLING}:
        action = "Ждите. Решение придёт в этот чат. «Назад» — к списку."
    elif status == ST_LIVE:
        action = "Ничего нажимать не нужно. «Назад» — к списку групп."
    elif status == ST_ENDED:
        action = "Срок вышел. «Назад» — к списку. Новую группу сдайте с главного меню."
    elif status == ST_REJECTED:
        reason = str(data.get("reject_text") or "").strip()
        action = (reason + " «Назад» — к списку.") if reason else "Не приняли. «Назад» — к списку."
    elif status == ST_BURNED:
        action = "Кут убрали из группы. «Назад» — к списку."
    else:
        action = "«Назад» — к списку групп."
    lines.append(do_next(escape(action) if status == ST_REJECTED else action))
    return "\n".join(lines)


def text_cancelled() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Заявку сняли</b>\n"
        + do_next("Нажмите «Сдать ещё группу» — и выберите путь заново.")
    )


def text_confirm_prompt(user_id: int, name: str) -> str:
    who = mention_html(user_id, name)
    return (
        f"<tg-emoji emoji-id='{CONFIRM_EMOJI}'>🎁</tg-emoji> "
        f"<b>{who} добавил Кут сюда. Если это так — нажмите Да. Тогда заработок пойдёт ему.</b>"
    )


def text_confirm_yes() -> str:
    return (
        f"{status_emoji_html('ok')} <b>Подтверждено. Заявка на проверке.</b>\n"
        + do_next("Ничего больше нажимать не нужно. Решение придёт пригласившему в личку.")
    )


def text_confirm_no_first() -> str:
    return (
        f"{status_emoji_html('no')} <b>Создатель не подтвердил</b>\n"
        + do_next("Остался один шанс. Откройте группу и напишите <code>подтверждение</code> ещё раз.")
    )


def text_confirm_no_second() -> str:
    return (
        f"{status_emoji_html('no')} <b>Снова нет</b>\n"
        + do_next("Эту группу нельзя 31 день. Нажмите «Назад» и возьмите другую.")
    )


def text_not_your_claim() -> str:
    return (
        f"{status_emoji_html('no')} <b>Это не ваша заявка.</b>\n"
        + do_next("Нажмите «Назад» — откроется меню пиара.")
    )


def text_not_creator() -> str:
    return (
        f"{status_emoji_html('no')} <b>Подтверждает только создатель</b>\n"
        + do_next("Да должен нажать человек с короной в списке админов.")
    )


def text_confirm_expired() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Это подтверждение уже не действует.</b>\n"
        + do_next("Напишите в группе «подтверждение» снова.")
    )


def text_wrong_group() -> str:
    return (
        f"{status_emoji_html('no')} <b>Не та группа.</b>\n"
        + do_next("Откройте ту группу, куда вы добавляли Кут, и напишите «подтверждение» там.")
    )


def text_need_photos_first() -> str:
    return (
        f"{status_emoji_html('no')} <b>Сначала 3 фото в боте</b>\n"
        + do_next("Пришлите их сюда, в этот чат, по одному кадру.")
    )


def text_accepted(term_days: int, *, role: str = "") -> str:
    days = int(term_days or DEFAULT_TERM_DAYS)
    if str(role or "") == ROLE_OWNER:
        return (
            f"{status_emoji_html('ok')} <b>Группу приняли.</b>\n"
            f"<b>{days} дней · новые смогут играть у вас на подарочные куты.</b>\n"
            + do_next("Нажмите «Мои группы», когда захотите цифры.")
        )
    return (
        f"{status_emoji_html('ok')} <b>Группу приняли.</b>\n"
        f"<b>{days} дней вам капает доля с игр новых.</b>\n"
        + do_next("Нажмите «Заработки» или «Мои группы», когда захотите цифры.")
    )


def text_digest(
    *,
    newcomers: int,
    commission: int = 0,
    paid: int,
    days_left: int,
    title: str = "",
) -> str:
    name = escape(title or "группы")
    extra = "Это уже на вашем балансе." if int(paid or 0) > 0 else "Как появятся игры новых — цифра вырастет."
    return (
        f"{status_emoji_html('ok')} <b>Сегодня с «{name}»: {int(newcomers or 0)} новых людей · вам {kut_amount(paid)}.</b>\n"
        f"<b>Осталось {int(days_left or 0)} дн.</b>\n"
        f"<i>{extra}</i>\n"
        + do_next("Откройте «Заработки», чтобы видеть цифры по группам.")
    )


def text_gift(user_id: int, name: str, amount: int) -> str:
    who = mention_html(user_id, name)
    n = int(amount)
    return (
        f"<tg-emoji emoji-id='{GIFT_EMOJI}'>🪙</tg-emoji> "
        f"<b>{who}, На ваш баланс было выдано {n} кут в подарок, для того чтобы научится играть в @CuteGamingBot</b>\n"
        "<blockquote><b>В случае каких либо непоняток, напишите \"хелп\"</b></blockquote>"
    )


def text_gift_locked() -> str:
    return (
        f"{status_emoji_html('no')} <b>Подарочные куты можно поставить только в играх этой группы, одному.</b>\n"
        "<blockquote><i>Снять или перевести нельзя — ими учатся играть у вас.</i></blockquote>"
    )


def text_term_end() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Срок по этой группе закончился. Новые куты с неё больше не капают.</b>\n"
        + do_next("Откройте «Мои группы», чтобы увидеть статус. Новую можно сдать с главного меню.")
    )


def text_kicked() -> str:
    return (
        f"{status_emoji_html('no')} <b>Кут убрали из группы. Начисления стоп.</b>\n"
        + do_next("Верните Кут в админы, если хотите продолжить. Статус — в «Мои группы».")
    )


def text_rejected(reason: str, *, can_fix: bool) -> str:
    body = escape((reason or "Не приняли.").strip() or "Не приняли.")
    if can_fix:
        action = f"{body} Есть 48 часов. Исправьте и сдайте снова через «Сдать ещё группу»."
    else:
        action = f"{body} Нажмите «Назад» — в меню пиара."
    return (
        f"{status_emoji_html('no')} <b>Не приняли.</b>\n"
        + do_next(action)
    )


def text_two_pending() -> str:
    return (
        f"{status_emoji_html('no')} <b>Уже 2 заявки</b>\n"
        + do_next("Нажмите «Мои группы»: дождитесь проверки или снимите одну.")
    )


def text_two_live() -> str:
    return (
        f"{status_emoji_html('no')} <b>Уже 2 живые группы</b>\n"
        + do_next("Нажмите «Заработки». Новую можно сдать, когда освободится слот.")
    )


def text_banned_31() -> str:
    return (
        f"{status_emoji_html('no')} <b>Эту группу нельзя 31 день</b>\n"
        + do_next("Нажмите «Назад» и возьмите другую — или подождите.")
    )


def text_freeze_admin() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Пауза: Кут нужна админка</b>\n"
        + do_next("Верните Кут в администраторы группы. Потом снова начнёт капать.")
    )


def text_freeze_public() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Пауза: группа стала закрытой</b>\n"
        + do_next("Сделайте группу открытой с @адресом. Потом снова начнёт капать.")
    )


def text_group_busy(*, owner: bool = False) -> str:
    if owner:
        return (
            f"{status_emoji_html('no')} <b>Эту группу уже сдаёт создатель</b>\n"
            + do_next("Одна группа — один человек. Нажмите «Назад» и возьмите другую.")
        )
    return (
        f"{status_emoji_html('no')} <b>Эту группу уже сдают</b>\n"
        + do_next("Одна группа — один человек. Нажмите «Назад» и возьмите другую.")
    )


def text_confirm_timeout() -> str:
    return (
        f"{status_emoji_html('no')} <b>Создатель не нажал Да за 24 часа</b>\n"
        + do_next("Нажмите «Сдать ещё группу» — можно начать снова.")
    )


def text_owner_no_confirm() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Вам подтверждение не нужно</b>\n"
        + do_next("Заявка создателя идёт на проверку без Да. Смотрите «Мои группы».")
    )


def text_no_groups() -> str:
    return text_how()


def text_resume_claim(title: str, status: str, freeze: str | None = None) -> str:
    name = escape(title or "группа")
    label = claim_status_label(status, freeze)
    return (
        f"{status_emoji_html('wait')} <b>«{name}»</b>\n"
        f"<b>{escape(label)}</b>\n"
        + do_next("Нажмите кнопку ниже — бот продолжит с этого шага.")
    )


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
