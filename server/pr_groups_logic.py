# -*- coding: utf-8 -*-
"""Пиар в группах — чистая логика: статусы, раскол посева, кто новый, тексты.

Без БД и без Telegram. Бот и админка импортируют отсюда одно и то же,
чтобы очередь, кнопки и выплаты не разъехались.
"""

from __future__ import annotations

from html import escape
from typing import Any, Iterable, Optional

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
    "Кут в списке админов",
    "Сообщение Кута в этой группе",
    "Профиль создателя в списке админов",
)

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
    """Умный раскол: сначала стол на несколько выигрышей, остаток — фонд."""
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
    """До 20 кут или дыра до исходного стола. Потолок срока — половина стола."""
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


# ---------------------------------------------------------------------------
# Тексты. Зафиксированы с владельцем. Не раздувать.
# ---------------------------------------------------------------------------

def text_entry() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Пиар в группах</b>\n"
        "<blockquote><b>До 35% комиссии с игр новых людей · 14 дней</b></blockquote>"
    )


def text_need_public() -> str:
    return f"{status_emoji_html('no')} <b>Нужна публичная группа с @username.</b>"


def text_need_admin() -> str:
    return f"{status_emoji_html('no')} <b>Сделайте Кута админом.</b>"


def text_pick_group() -> str:
    return f"{status_emoji_html('wait')} <b>В какую группу сдаём?</b>"


def text_pick_role(title: str) -> str:
    name = escape(title or "группа")
    return (
        f"{status_emoji_html('wait')} <b>{name}</b>\n"
        "<blockquote><b>Это моя группа · или вы привели Кут</b></blockquote>"
    )


def text_wrong_owner() -> str:
    return (
        f"{status_emoji_html('no')} <b>Вы не создатель этой группы.</b>\n"
        "<blockquote><b>Нажмите «Я привёл Кут» — подтвердит создатель.</b></blockquote>"
    )


def text_wait_photo(index: int, have: int) -> str:
    hint = photo_hint(index)
    return (
        f"{status_emoji_html('wait')} <b>{escape(hint)}</b>\n"
        f"<blockquote><b>Сейчас : {have} из {PHOTOS_REQUIRED}</b></blockquote>"
    )


def text_photo_progress(have: int) -> str:
    nxt = photo_hint(have) if have < PHOTOS_REQUIRED else "готово"
    extra = f" · дальше {nxt}" if have < PHOTOS_REQUIRED else ""
    return (
        f"{status_emoji_html('ok')} <b>{have} из {PHOTOS_REQUIRED}</b>\n"
        f"<blockquote><b>{escape(extra.lstrip(' · ') or 'три кадра на месте')}</b></blockquote>"
    )


def text_need_photo() -> str:
    return f"{status_emoji_html('no')} <b>Нужно фото.</b>"


def text_photos_expired() -> str:
    return (
        f"{status_emoji_html('no')} <b>24 часа вышли — фото не собраны.</b>\n"
        "<blockquote><b>Можно начать снова.</b></blockquote>"
    )


def text_after_photos_owner() -> str:
    return f"{status_emoji_html('wait')} <b>На проверке.</b>"


def text_after_photos_reco() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Напишите в группе, в которую вы привели Кут, «подтверждение»</b>"
    )


def text_cancelled() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Заявку сняли.</b>\n"
        "<blockquote><b>Можно начать снова.</b></blockquote>"
    )


def text_confirm_prompt(user_id: int, name: str) -> str:
    who = mention_html(user_id, name)
    return (
        f"<tg-emoji emoji-id='{CONFIRM_EMOJI}'>🎁</tg-emoji> "
        f"<b>Создатель, подтвердите: {who} привёл @CuteGamingBot в эту группу?</b>"
    )


def text_confirm_yes() -> str:
    return f"{status_emoji_html('ok')} <b>Подтверждено. Заявка на проверке.</b>"


def text_confirm_no_first() -> str:
    return f"{status_emoji_html('no')} <b>Создатель не подтвердил. Остался один шанс.</b>"


def text_confirm_no_second() -> str:
    return f"{status_emoji_html('no')} <b>Снова нет. Эту группу нельзя сдать 31 день.</b>"


def text_not_your_claim() -> str:
    return f"{status_emoji_html('no')} <b>Это не ваша заявка.</b>"


def text_not_creator() -> str:
    return f"{status_emoji_html('no')} <b>Подтверждает только создатель группы.</b>"


def text_confirm_expired() -> str:
    return f"{status_emoji_html('wait')} <b>Это подтверждение уже не действует. Напишите «подтверждение» снова.</b>"


def text_wrong_group() -> str:
    return f"{status_emoji_html('no')} <b>Не та группа.</b>"


def text_need_photos_first() -> str:
    return f"{status_emoji_html('no')} <b>Сначала 3 фото в боте.</b>"


def text_accepted(term_days: int) -> str:
    days = int(term_days or DEFAULT_TERM_DAYS)
    return (
        f"{status_emoji_html('ok')} <b>Группу приняли.</b>\n"
        f"<blockquote><b>{days} дней · до 35% комиссии с игр новых.</b></blockquote>"
    )


def text_digest(*, newcomers: int, commission: int, paid: int, days_left: int) -> str:
    return (
        f"{status_emoji_html('ok')} <b>За сутки: {newcomers} новых · комиссия {commission} · вам {paid} кут.</b>\n"
        f"<blockquote><b>Осталось {days_left} дн.</b></blockquote>"
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
    return f"{status_emoji_html('no')} <b>Подарочные куты — только соло-игры в этой группе.</b>"


def text_term_end() -> str:
    return f"{status_emoji_html('wait')} <b>Срок по этой группе закончился. Новые куты с неё больше не капают.</b>"


def text_kicked() -> str:
    return f"{status_emoji_html('no')} <b>Кут убрали из группы. Начисления стоп.</b>"


def text_rejected(reason: str, *, can_fix: bool) -> str:
    body = escape((reason or "Не приняли.").strip() or "Не приняли.")
    extra = "Есть 48 часов." if can_fix else ""
    tail = f"\n<blockquote><b>{extra}</b></blockquote>" if extra else ""
    return f"{status_emoji_html('no')} <b>Не приняли.</b>\n<blockquote><b>{body}</b></blockquote>{tail}"


def text_two_pending() -> str:
    return f"{status_emoji_html('no')} <b>Уже 2 заявки на проверке.</b>"


def text_two_live() -> str:
    return f"{status_emoji_html('no')} <b>Уже 2 живые группы.</b>"


def text_banned_31() -> str:
    return f"{status_emoji_html('no')} <b>Эту группу нельзя 31 день.</b>"


def text_freeze_admin() -> str:
    return f"{status_emoji_html('wait')} <b>У бота нет прав администратора.</b>"


def text_freeze_public() -> str:
    return f"{status_emoji_html('wait')} <b>Группа больше не публичная.</b>"


def text_group_busy() -> str:
    return f"{status_emoji_html('no')} <b>Эту группу уже сдают.</b>"


def text_no_groups() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Добавьте @CuteGamingBot админом в публичную группу.</b>"
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
