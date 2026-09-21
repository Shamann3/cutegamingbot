# -*- coding: utf-8 -*-
"""Пиар в группах — чистая логика: статусы, раскол посева, кто новый, тексты.

Без БД и без Telegram. Бот и админка импортируют отсюда одно и то же,
чтобы очередь, кнопки и выплаты не разъехались.
"""

from __future__ import annotations

import json
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
    HELP_TASKS,
    HELP_WORDS,
    IDLE_HINT,
    IDLE_LABEL,
    LINK_HINT as LINK_HINT_HTML,
    NEED_PHOTO,
    PALETTE,
    PAUSE,
    PAUSE_HINT,
    PAUSE_SHORT,
    PHOTO_HINTS,
    PHOTO_STEPS,
    REJECT_REASONS,
    SCREENS,
    STATUS,
    STATUS_EMOJI_NO,
    STATUS_EMOJI_OK,
    STATUS_EMOJI_WAIT,
    STATUS_SHORT,
    TASKS_MENU,
    WORDS,
    CONFIRM_WORDS,
    emoji_html as design_emoji_html,
    name_or,
    progress,
    say,
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
ST_ENDING = "ending"

OPEN_STATUSES = frozenset({
    ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY, ST_PENDING, ST_ACCEPTING, ST_FULFILLING, ST_LIVE, ST_ENDING,
})
QUEUE_STATUSES = frozenset({ST_PENDING})
LIVE_STATUSES = frozenset({ST_LIVE, ST_ACCEPTING, ST_FULFILLING})
IN_PROGRESS_STATUSES = frozenset({
    ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY, ST_PENDING, ST_ACCEPTING, ST_FULFILLING, ST_LIVE, ST_ENDING,
})
MINE_STATUSES = frozenset(
    IN_PROGRESS_STATUSES | {ST_ENDED, ST_BURNED, ST_REJECTED, ST_EXPIRED, ST_CANCELLED}
)
HOLD_GROUP_STATUSES = frozenset({
    ST_PHOTOS, ST_WAIT_CONFIRM, ST_CONFIRM_RETRY, ST_PENDING, ST_ACCEPTING, ST_FULFILLING, ST_LIVE, ST_ENDING, ST_REJECTED,
})
MONEY_UNWIND_STATUSES = frozenset({ST_LIVE, ST_ACCEPTING, ST_FULFILLING, ST_ENDING})
CONFIRM_WAIT_STATUSES = frozenset({ST_WAIT_CONFIRM, ST_CONFIRM_RETRY})
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

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
_TG_EMOJI = re.compile(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", re.I | re.S)


def html_without_custom_emoji(html: str) -> str:
    return _TG_EMOJI.sub(r"\1", str(html or ""))


def sql_ident(name: str) -> str:
    """Имя колонки в кавычках: freeze в Postgres — ключевое слово."""
    key = str(name or "")
    if not _IDENT.fullmatch(key):
        raise ValueError(f"bad column {name!r}")
    return f'"{key}"'


def alter_claim_column_sql(name: str, spec: str) -> str:
    return f"ALTER TABLE pr_claims ADD COLUMN IF NOT EXISTS {sql_ident(name)} {spec}"


def claim_set_sql(fields: dict[str, Any], *, claim_id: int) -> tuple[str, list[Any]]:
    sets: list[str] = []
    args: list[Any] = []
    i = 1
    for key, value in fields.items():
        ident = sql_ident(key)
        if key == "photos" and not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
            sets.append(f"{ident} = ${i}::jsonb")
        else:
            sets.append(f"{ident} = ${i}")
        args.append(value)
        i += 1
    args.append(int(claim_id))
    sql = f"UPDATE pr_claims SET {', '.join(sets)}, updated_at = NOW() WHERE id = ${i} RETURNING *"
    return sql, args


# Кадры доказательств: тексты в pr_groups_design.PHOTO_STEPS.
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

DEFAULT_REJECT_REASONS: list[dict[str, str]] = list(REJECT_REASONS)


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
    if t.startswith("<blockquote"):
        return t
    return f"<blockquote><b><i>{t}</i></b></blockquote>"


def do_next(text: str) -> str:
    """Главное действие на экране — жирный текст, не цитата."""
    t = str(text or "").strip()
    if not t:
        return ""
    return f"<b>{t}</b>"


_HTML_PAIR = frozenset({
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "code", "pre", "blockquote", "a", "tg-emoji", "tg-spoiler", "span",
})
_HTML_TAG = re.compile(r"</?([a-zA-Z0-9-]+)(?:\s[^>]*)?>")


def html_errors(html: str) -> list[str]:
    """Telegram HTML: незакрытый тег ломает SendMessage."""
    stack: list[str] = []
    for match in _HTML_TAG.finditer(str(html or "")):
        name = match.group(1).lower()
        if name not in _HTML_PAIR:
            continue
        if match.group(0).startswith("</"):
            if not stack or stack[-1] != name:
                want = stack[-1] if stack else "?"
                return [f"ожидали </{want}>, нашли </{name}>"]
            stack.pop()
        else:
            stack.append(name)
    if stack:
        return [f"не закрыт <{stack[-1]}>"]
    return []


def tg_safe_html(html: str) -> str:
    raw = str(html or "")
    if not html_errors(raw):
        return raw
    kept: list[str] = []
    pos = 0
    for match in re.finditer(r"<tg-emoji\b[^>]*>.*?</tg-emoji>", raw, re.I | re.S):
        kept.append(re.sub(r"<[^>]+>", "", raw[pos:match.start()]))
        kept.append(match.group(0))
        pos = match.end()
    kept.append(re.sub(r"<[^>]+>", "", raw[pos:]))
    return "".join(kept)


def _bold_line(text: str) -> str:
    t = str(text or "").strip()
    if not t:
        return ""
    if t.startswith("<blockquote") or t.startswith("<pre"):
        return t
    if "<" in t:
        return t
    return f"<b>{t}</b>"


def _content_line(chunk: str) -> str:
    raw = str(chunk or "").strip()
    if not raw:
        return ""
    if raw.startswith("<blockquote"):
        inner = re.sub(r"<[^>]+>", "", raw).strip()
        return raw if inner else ""
    if raw.startswith("<pre"):
        inner = re.sub(r"<[^>]+>", "", raw).strip()
        return raw if inner else ""
    return _bold_line(raw)


def _render_message_lines(blob: str) -> list[str]:
    """Собирает строки экрана: пустые строки остаются, цитата не жирнеет построчно."""
    out: list[str] = []
    in_block = 0
    for chunk in str(blob).split("\n"):
        low = chunk.lower()
        opens = len(re.findall(r"<(?:pre|blockquote)\b", low))
        closes = low.count("</pre>") + low.count("</blockquote>")
        if in_block or opens:
            next_in = in_block + opens - closes
            if not in_block and opens and next_in <= 0:
                line = _content_line(chunk)
                if line:
                    out.append(line)
                in_block = 0
                continue
            piece = chunk.rstrip() if in_block else chunk.strip()
            out.append(piece)
            in_block = max(0, next_in)
            continue
        raw = chunk.strip()
        if not raw:
            if out and out[-1] != "":
                out.append("")
            continue
        line = _content_line(chunk)
        if line:
            out.append(line)
    while out and out[-1] == "":
        out.pop()
    return out


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
    text: str = "",
    title: str = "",
    body: str = "",
    extra_text: str = "",
    next_text: str = "",
) -> str:
    """Эмодзи + целый текст сообщения. Обычные строки жирные, цитата как написана."""
    blob = text
    if not blob:
        parts = [title]
        if body:
            parts.extend(str(body).split("\n"))
        if extra_text:
            parts.append(extra(extra_text))
        if next_text:
            parts.append(next_text)
        blob = "\n".join(str(p) for p in parts if str(p).strip())
    mark = theme_emoji_html(emoji) if emoji in PALETTE else design_emoji_html(emoji)
    out = _render_message_lines(blob)
    if mark:
        for i, line in enumerate(out):
            if line.strip():
                out[i] = f"{mark} {line}".strip()
                break
        else:
            out = [mark]
    return tg_safe_html("\n".join(out))


def render_design(name: str, values: dict[str, Any] | None = None, **overrides: Any) -> str:
    spec = SCREENS[name]
    vals = {"link_hint": LINK_HINT_HTML}
    vals.update(values or {})
    emoji = overrides.get("emoji") or spec.get("emoji") or ""
    emoji_by = spec.get("emoji_by") or {}
    if emoji_by and vals.get("emoji_key"):
        emoji = emoji_by.get(vals["emoji_key"], emoji)
    blob = overrides["text"] if "text" in overrides else spec.get("text") or ""
    extra_by = spec.get("extra_by") or {}
    extra_text = overrides["extra"] if "extra" in overrides else spec.get("extra") or ""
    if "extra" not in overrides and extra_by and vals.get("extra_key"):
        extra_text = extra_by.get(vals["extra_key"], extra_text)
    extra_filled = fill_design(extra_text, vals)
    if extra_filled:
        vals.setdefault("extra", extra_filled)
        for token in ("note", "barnum"):
            if "{%s}" % token in blob:
                vals.setdefault(token, extra_filled)
    next_text = overrides["next"] if "next" in overrides else spec.get("next") or ""
    next_by = spec.get("next_by") or {}
    if "next" not in overrides and next_by and vals.get("next_key") is not None:
        next_text = next_by.get(str(vals["next_key"]), next_by.get("default", next_text))
    if "next" not in overrides and vals.get("has_items") is False and spec.get("next_empty"):
        next_text = spec["next_empty"]
    if next_text:
        vals.setdefault("next", fill_design(next_text, vals))
    if not blob:
        blob = "\n".join(
            part for part in (
                spec.get("title") or "",
                spec.get("body") or "",
                extra(extra_filled) if extra_filled else "",
                next_text,
            ) if str(part).strip()
        )
    return pr_screen(emoji, fill_design(blob, vals))


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
    label = escape(name_or(name, "player"))
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
        tone = "hot"
    elif n <= 30:
        tone = "warn"
    else:
        tone = "ok"
    hint = IDLE_HINT[tone]
    return {"days": n, "tone": tone, "hint": hint, "label": IDLE_LABEL.format(n=n, hint=hint)}


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
    raw = " ".join(str(text or "").lower().replace("ё", "е").split())
    raw = raw.strip(" .!?,…:;\"'«»")
    return raw in CONFIRM_WORDS


def own_kut_amount(balance: int, gift_amount: int) -> int:
    """Куты, которые не подарок: их можно снять, перевести и играть где угодно."""
    return max(0, int(balance or 0) - max(0, int(gift_amount or 0)))


def gift_covers_this_play(
    *,
    gift_chat_id: Any,
    play_chat_id: Any,
    solo: bool = True,
    private: bool = False,
) -> bool:
    """Подарок можно тратить только в одиночной игре той группы, где его выдали."""
    if private or not solo:
        return False
    try:
        gift_chat = int(gift_chat_id or 0)
        play_chat = int(play_chat_id or 0)
    except (TypeError, ValueError):
        return False
    return gift_chat != 0 and gift_chat == play_chat


def bet_fits_gift_lock(
    *,
    balance: int,
    bet: int,
    gift_amount: int,
    gift_chat_id: Any,
    play_chat_id: Any,
    solo: bool = True,
    private: bool = False,
) -> bool:
    """False — ставка задела бы подарок не там, где можно."""
    need = max(0, int(bet or 0))
    if need <= 0:
        return True
    gift = max(0, int(gift_amount or 0))
    own = own_kut_amount(balance, gift)
    if gift_covers_this_play(
        gift_chat_id=gift_chat_id,
        play_chat_id=play_chat_id,
        solo=solo,
        private=private,
    ):
        return own + gift >= need
    return own >= need


def photo_hint(index: int) -> str:
    if 0 <= index < len(PHOTO_HINTS):
        return PHOTO_HINTS[index]
    return say("photo_hint_n", n=index + 1) if index >= 0 else say("photo")


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
        return say("ellipsis")
    return raw[: limit - 1] + say("ellipsis")


def kut_amount(n: int) -> str:
    return say("kut", n=max(0, int(n or 0)))


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
    return PAUSE.get(str(freeze or "").strip().lower(), "")


def pause_hint(freeze: str | None) -> str:
    return PAUSE_HINT.get(str(freeze or "").strip().lower(), "")


def claim_status_label(status: str, freeze: str | None = None) -> str:
    paused = pause_label(freeze)
    if paused:
        return paused
    return STATUS.get(str(status or ""), str(status or ""))


def claim_status_short(status: str, freeze: str | None = None) -> str:
    kind = str(freeze or "").strip().lower()
    short_pause = PAUSE_SHORT.get(kind)
    if short_pause:
        return short_pause
    return STATUS_SHORT.get(str(status or ""), say("group"))


def list_row_money(row: dict[str, Any] | None) -> str:
    data = row or {}
    if is_owner_claim(data):
        gifts = int(data.get("gifts") or 0)
        if gifts or str(data.get("status") or "") in LIVE_STATUSES:
            return say("gifts_row", n=gifts)
        return ""
    paid = int(data.get("paid_kut") or 0)
    if paid:
        return kut_amount(paid)
    return ""


def claim_button_label(row: dict[str, Any] | None) -> str:
    data = row or {}
    title = name_or(data.get("chat_title") or data.get("title"), "group")
    short = claim_status_short(str(data.get("status") or ""), data.get("freeze"))
    money = list_row_money(data)
    raw = say("claim_btn_money", title=title, short=short, money=money) if money else say("claim_btn", title=title, short=short)
    return clip_btn(raw)


def _titles_line(rows: list[dict[str, Any]], reason: str) -> str:
    names = []
    for row in rows[:3]:
        names.append(escape(name_or(row.get("title"), "group")))
    if not names:
        return ""
    return say("seen_line", names=say("seen_join").join(names), reason=reason)


def looks_like_help(text: str | None) -> bool:
    return str(text or "").strip().lower() in HELP_WORDS


# ---------------------------------------------------------------------------
# Экраны читают pr_groups_design.SCREENS. Здесь только данные и выбор варианта.
# ---------------------------------------------------------------------------

def _seen_groups_extra(no_public: list | None, no_admin: list | None) -> str:
    bits = []
    line_pub = _titles_line(list(no_public or []), say("seen_no_public"))
    line_adm = _titles_line(list(no_admin or []), say("seen_no_admin"))
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
    return render_design(name, {
        "seen": _seen_value(no_public, no_admin),
        "progress": progress(intent=intent, n=1),
    })


def text_how_public(*, intent: str = "") -> str:
    return render_design("how_public", {"progress": progress(intent=intent, n=1)})


def text_how_admin(*, intent: str = "") -> str:
    return render_design(
        "how_admin_reco" if intent == ROLE_RECO else "how_admin",
        {"progress": progress(intent=intent, n=1)},
    )


def text_need_public(title: str = "", *, intent: str = "") -> str:
    return render_design("need_public", {
        "name": escape(name_or(title, "this_group")),
        "progress": progress(intent=intent, n=1),
    })


def text_need_admin(title: str = "", *, intent: str = "") -> str:
    name = "need_admin_reco" if intent == ROLE_RECO else "need_admin"
    return render_design(name, {
        "name": escape(name_or(title, "this_group")),
        "progress": progress(intent=intent, n=1),
    })


def text_bot_joined(title: str, *, has_intent: bool = False, intent: str = "") -> str:
    key = "bot_joined_intent" if has_intent else "bot_joined"
    vals = {"name": escape(name_or(title, "group"))}
    if has_intent:
        vals["progress"] = progress(intent=intent, n=1)
    return render_design(key, vals)


def text_need_link(*, intent: str = "") -> str:
    return render_design("need_link", {"progress": progress(intent=intent, n=2)})


def text_forward_no_group(*, intent: str = "") -> str:
    return render_design("forward_no_group", {"progress": progress(intent=intent, n=2)})


def text_link_invite(*, intent: str = "") -> str:
    return render_design("link_invite", {"progress": progress(intent=intent, n=2)})


def text_group_not_found(*, intent: str = "") -> str:
    return render_design("group_not_found", {"progress": progress(intent=intent, n=2)})


def text_bot_not_there(title: str = "", *, intent: str = "") -> str:
    name = "bot_not_there_reco" if intent == ROLE_RECO else "bot_not_there"
    return render_design(name, {
        "name": escape(name_or(title, "this_group")),
        "progress": progress(intent=intent, n=1),
    })


def text_cant_add() -> str:
    return render_design("cant_add", {"progress": progress(intent=ROLE_RECO, n=1)})


def text_not_in_group(title: str = "", *, intent: str = "") -> str:
    return render_design("not_in_group", {
        "name": escape(name_or(title, "this_group")),
        "progress": progress(intent=intent, n=2),
    })


def text_not_a_group(*, intent: str = "") -> str:
    return render_design("not_a_group", {"progress": progress(intent=intent, n=2)})


def text_pick_group() -> str:
    return render_design("pick_group")


def text_pick_role(title: str) -> str:
    return render_design("pick_role", {"name": escape(name_or(title, "group"))})


def text_owner_bridge(title: str) -> str:
    return render_design("owner_bridge", {
        "name": escape(name_or(title, "group")),
        "progress": progress(intent=ROLE_OWNER, n=3),
    })


def text_reco_bridge(title: str) -> str:
    return render_design("reco_bridge", {
        "name": escape(name_or(title, "group")),
        "progress": progress(intent=ROLE_RECO, n=3),
    })


def text_not_owner_switch(title: str = "") -> str:
    return render_design("not_owner_switch", {"name": escape(name_or(title, "this_group"))})


def text_are_owner_switch(title: str = "") -> str:
    return render_design("are_owner_switch", {"name": escape(name_or(title, "this_group"))})


def text_wrong_owner() -> str:
    return text_not_owner_switch()


def text_wait_photo(index: int, have: int, *, intent: str = "") -> str:
    nxt = have if 0 <= have < PHOTOS_REQUIRED else min(int(index), PHOTOS_REQUIRED - 1)
    if 0 <= nxt < len(PHOTO_STEPS):
        step = PHOTO_STEPS[nxt]
        what = step["what"]
        need = step["need"]
    else:
        what = escape(photo_hint(nxt))
        need = ""
    body = say("photo_have", have=have, total=PHOTOS_REQUIRED, what=what) if have > 0 else what
    return render_design("wait_photo", {
        "step": have + 1,
        "total": PHOTOS_REQUIRED,
        "body": body,
        "need": need,
        "tail": "",
        "next_key": str(min(max(int(have), 0), 2)),
        "progress": progress(intent=intent, n=3),
    })


def text_photo_progress(have: int, *, intent: str = "") -> str:
    return text_wait_photo(have, have, intent=intent)


def text_need_photo(kind: str = "", *, intent: str = "") -> str:
    spec = NEED_PHOTO.get(kind or "") or NEED_PHOTO[""]
    return render_design("need_photo", {
        "title": spec["title"],
        "extra": spec["extra"],
        "tail": spec["next"],
        "progress": progress(intent=intent, n=3),
    })


def text_photos_expired() -> str:
    return render_design("photos_expired")


def text_after_photos_owner() -> str:
    return text_after_proofs_owner()


def text_after_proofs_owner() -> str:
    return render_design("after_proofs_owner", {"progress": progress(intent=ROLE_OWNER, n=4)})


def text_after_proofs_reco() -> str:
    return render_design("after_proofs_reco", {"progress": progress(intent=ROLE_RECO, n=5)})


def text_after_photos_reco(title: str = "") -> str:
    return render_design("after_photos_reco", {
        "name": escape(name_or(title, "group_acc")),
        "progress": progress(intent=ROLE_RECO, n=4),
    })


def text_wrote_confirm() -> str:
    return render_design("wrote_confirm", {"progress": progress(intent=ROLE_RECO, n=4)})


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
    name = escape(name_or(data.get("chat_title") or data.get("title"), "group"))
    status = str(data.get("status") or "")
    freeze = data.get("freeze")
    owner = is_owner_claim(data)
    spec = SCREENS["card"]
    key = _card_status_key(status, freeze)
    values: dict[str, Any] = {
        "name": name,
        "status": claim_status_label(status, freeze),
        "gifts": int(gifts or 0),
        "paid": kut_amount(data.get("paid_kut")),
        "today": kut_amount(today),
        "newcomers": int(newcomers or 0),
        "hint": pause_hint(freeze),
        "reason": escape(str(data.get("reject_text") or "").strip()) or say("reject_fallback"),
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
    if isinstance(templates, str):
        lines_src = [line for line in templates.split("\n") if line.strip()]
    else:
        lines_src = list(templates or [])
    facts: list[str] = []
    for tmpl in lines_src:
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
    values["extra"] = fill_design(extra_tmpl, values)
    values["next"] = fill_design(next_tmpl, values)
    return render_design("card", values)


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


def text_confirm_not_needed() -> str:
    return render_design("confirm_not_needed")


def text_creator_typed_confirm() -> str:
    return render_design("creator_typed_confirm")


def text_drop_confirm(title: str) -> str:
    return render_design("drop_confirm", {"name": escape(title or say("group"))})


def text_dropped() -> str:
    return render_design("dropped")


def text_admin_ended(title: str, reason: str = "") -> str:
    why = escape(str(reason or "").strip()) or "Проект снял эту группу."
    return render_design("admin_ended", {"name": escape(title or say("group")), "reason": why})


def text_group_blocked() -> str:
    return render_design("group_blocked")


def text_need_photos_first(*, intent: str = "") -> str:
    return render_design("need_photos_first", {"progress": progress(intent=intent or ROLE_RECO, n=3)})


def text_accepted(term_days: int, *, role: str = "") -> str:
    name = "accepted_owner" if str(role or "") == ROLE_OWNER else "accepted"
    return render_design(name, {"days": int(term_days or DEFAULT_TERM_DAYS)})


def text_accepting() -> str:
    return render_design("accepting")


def text_digest(
    *,
    newcomers: int,
    commission: int = 0,
    paid: int,
    days_left: int,
    title: str = "",
) -> str:
    return render_design("digest", {
        "name": escape(name_or(title, "of_group")),
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
    body = escape(name_or(reason, "rejected"))
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
        "name": escape(name_or(title, "group")),
        "status": claim_status_label(status, freeze),
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
    return say("reject_join").join(labels) or say("rejected")
