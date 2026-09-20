# -*- coding: utf-8 -*-
"""Пиар в группах — чистая логика: статусы, раскол посева, кто новый, тексты.

Без БД и без Telegram. Бот и админка импортируют отсюда одно и то же,
чтобы очередь, кнопки и выплаты не разъехались.
"""

from __future__ import annotations

import re
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
    "список админов",
    "сообщение Кута",
    "создатель группы",
)

# Один экран — один кадр. HTML уже безопасный.
PHOTO_STEPS: tuple[dict[str, str], ...] = (
    {
        "what": "Список администраторов группы.",
        "need": "На кадре должен быть <code>@CuteGamingBot</code>.",
    },
    {
        "what": "Сообщение Кута в этой группе.",
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

_TME_RE = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z0-9_+]+)", re.I)
_USER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
_SKIP_TME = frozenset({"share", "addstickers", "socks", "proxy", "iv", "boost"})


def startgroup_url(username: str | None = None) -> str:
    uname = str(username or BOT_USERNAME).strip().lstrip("@") or BOT_USERNAME
    return f"https://t.me/{uname}?startgroup=pr&admin={STARTGROUP_RIGHTS}"


def parse_group_ref(text: str | None) -> dict[str, str] | None:
    """@имя / t.me/имя / закрытая ссылка / t.me/c/id. Без голых слов — меньше ложных срабатываний."""
    raw = str(text or "").strip()
    if not raw:
        return None
    found = _TME_RE.search(raw)
    if found:
        part = found.group(1)
        low = part.lower()
        if part.startswith("+") or low == "joinchat":
            return {"kind": "invite", "value": part}
        if low == "c":
            rest = raw[found.end():]
            nums = re.match(r"/?(\d{6,})", rest)
            if nums:
                return {"kind": "internal", "value": nums.group(1)}
            return None
        if low in _SKIP_TME:
            return None
        if _USER_RE.fullmatch(part):
            return {"kind": "username", "value": part}
        return None
    token = raw.split()[0]
    if token.startswith("@"):
        name = token[1:].split("/")[0]
        if _USER_RE.fullmatch(name):
            return {"kind": "username", "value": name}
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


def claim_status_label(status: str) -> str:
    return {
        ST_PHOTOS: "ждите 3 фото",
        ST_WAIT_CONFIRM: "напишите «подтверждение» в группе",
        ST_CONFIRM_RETRY: "ещё один шанс · напишите «подтверждение»",
        ST_PENDING: "на проверке",
        ST_ACCEPTING: "на проверке",
        ST_FULFILLING: "на проверке",
        ST_LIVE: "капает",
    }.get(str(status or ""), str(status or ""))


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
        "<b><tg-emoji emoji-id='5391270106464539040'>😐</tg-emoji> Заработок - до 35% комиссии с игр новых людей.</b>\n"
        "<blockquote><i>Длительность заработка - 14 дней · с той группы, в которую вы добавите нашего бота</i></blockquote>"
    )


def text_choose_role() -> str:
    return (
        f"<tg-emoji emoji-id='5388583647370565067'>🌂</tg-emoji> <b>Кто вы?</b>\n"
        "<blockquote><i>Нажмите кнопку. Дальше бот будет ждать доказательства под ваш путь</i></blockquote>"
    )


def _epsilon_watch(*, yours: bool = True) -> str:
    whose = "ваша группа" if yours else "новая группа"
    return (
        f"<blockquote><i>Теперь {whose} уйдёт на проверку в защитную систему проекта Эпсилон.\n"
        "После этого вам придёт сообщение — прямо в этот чат. Следите за этим.</i></blockquote>"
    )


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
            "Потом пришлите сюда ссылку:\n"
            "<blockquote><code>@группа</code></blockquote>"
            "<i>Можно переслать сообщение из той группы.</i>"
            f"{seen}"
        )
    return (
        f"{status_emoji_html('wait')} <b>Ваша группа</b>\n"
        "Добавьте Кута админом в публичную группу.\n"
        "Потом пришлите сюда ссылку:\n"
        "<blockquote><code>@группа</code></blockquote>"
        "<i>Можно переслать сообщение из той группы.</i>"
        f"{seen}"
    )


def text_how_public() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Нужен @адрес</b>\n"
        "Название сверху → <b>Управление</b> → <b>Тип группы</b> → <b>Публичная</b>.\n"
        "<blockquote><i>Потом пришлите сюда <code>@адрес</code></i></blockquote>"
    )


def text_how_admin(*, intent: str = "") -> str:
    if intent == ROLE_RECO:
        return (
            f"{status_emoji_html('wait')} <b>Кут должен быть админом</b>\n"
            "Попросите создателя: <b>Управление</b> → <b>Администраторы</b> → @CuteGamingBot.\n"
            "<blockquote><i>Потом пришлите сюда <code>@ссылку</code></i></blockquote>"
        )
    return (
        f"{status_emoji_html('wait')} <b>Кут должен быть админом</b>\n"
        "<b>Управление</b> → <b>Администраторы</b> → @CuteGamingBot.\n"
        "<blockquote><i>Потом «Проверить» или пришлите <code>@ссылку</code></i></blockquote>"
    )


def text_need_public(title: str = "") -> str:
    name = escape(title or "эта группа")
    return (
        f"{status_emoji_html('no')} <b>У «{name}» нет @адреса</b>\n"
        "Название сверху → <b>Управление</b> → <b>Тип группы</b> → <b>Публичная</b>.\n"
        "<blockquote><i>Потом пришлите сюда <code>@адрес</code></i></blockquote>"
    )


def text_need_admin(title: str = "", *, intent: str = "") -> str:
    name = escape(title or "эта группа")
    if intent == ROLE_RECO:
        return (
            f"{status_emoji_html('no')} <b>В «{name}» Кут не админ</b>\n"
            "Попросите создателя дать ему админку.\n"
            "<blockquote><i>Потом пришлите сюда <code>@ссылку</code></i></blockquote>"
        )
    return (
        f"{status_emoji_html('no')} <b>В «{name}» Кут не админ</b>\n"
        "<b>Управление</b> → <b>Администраторы</b> → @CuteGamingBot.\n"
        "<blockquote><i>Потом «Проверить» или пришлите <code>@ссылку</code></i></blockquote>"
    )


def text_bot_joined(title: str, *, has_intent: bool = False) -> str:
    name = escape(title or "группа")
    if has_intent:
        return (
            f"{status_emoji_html('ok')} <b>Кут зашёл в «{name}»</b>\n"
            "<blockquote><i>Если он админ — нажмите «Проверить» или пришлите <code>@ссылку</code></i></blockquote>"
        )
    return (
        f"{status_emoji_html('ok')} <b>Кут зашёл в «{name}»</b>\n"
        "<blockquote><i>Нажмите «Начать» и выберите, кто вы</i></blockquote>"
    )


def text_need_link() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Нужна ссылка на группу</b>\n"
        "Пришлите <code>@имя</code> или <code>t.me/имя</code>\n"
        "<blockquote><i>Или перешлите сообщение из той группы</i></blockquote>"
    )


def text_link_invite() -> str:
    return (
        f"{status_emoji_html('no')} <b>Это закрытая ссылка</b>\n"
        "<blockquote><i>Группа должна быть публичной — с @адресом</i></blockquote>"
    )


def text_group_not_found() -> str:
    return (
        f"{status_emoji_html('no')} <b>Такую группу не вижу</b>\n"
        "<blockquote><i>Проверьте @адрес. Кут должен быть в чате</i></blockquote>"
    )


def text_bot_not_there(title: str = "", *, intent: str = "") -> str:
    name = escape(title or "эта группа")
    if intent == ROLE_RECO:
        return (
            f"{status_emoji_html('no')} <b>Кута нет в «{name}»</b>\n"
            "Попросите создателя добавить @CuteGamingBot в админы.\n"
            "<blockquote><i>Потом снова пришлите <code>@ссылку</code></i></blockquote>"
        )
    return (
        f"{status_emoji_html('no')} <b>Кута нет в «{name}»</b>\n"
        "Нажмите «Добавить Кута» и выберите этот чат.\n"
        "<blockquote><i>Потом снова пришлите <code>@ссылку</code></i></blockquote>"
    )


def text_cant_add() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Чужая группа</b>\n"
        "Напишите создателю: добавь @CuteGamingBot в админы.\n"
        "Когда Кут будет в чате — пришлите сюда ссылку:\n"
        "<blockquote><code>@группа</code></blockquote>"
    )


def text_not_in_group(title: str = "") -> str:
    name = escape(title or "эта группа")
    return (
        f"{status_emoji_html('no')} <b>Вас нет в «{name}»</b>\n"
        "<blockquote><i>Сначала вступите в группу</i></blockquote>"
    )


def text_not_a_group() -> str:
    return (
        f"{status_emoji_html('no')} <b>Это не группа</b>\n"
        "<blockquote><i>Нужен чат, не канал и не человек</i></blockquote>"
    )


def text_pick_group() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Какую группу сдаём?</b>\n"
        "<blockquote><i>Нажмите на нужную</i></blockquote>"
    )


def text_pick_role(title: str) -> str:
    name = escape(title or "группа")
    return (
        f"{status_emoji_html('ok')} <b>«{name}»</b>\n"
        "Кто сдаёт эту группу?\n"
        "<blockquote><i>Своя — первая кнопка. Привели Кут — вторая, создатель потом нажмёт Да</i></blockquote>"
    )


def text_owner_bridge(title: str) -> str:
    name = escape(title or "группа")
    return (
        f"{status_emoji_html('ok')} <b>«{name}»</b>\n"
        "Вы создатель. Дальше 3 фото — и заявка на проверку.\n"
        "<blockquote><i>Друг попросил добавить Кута? Не забирайте заявку — пусть он пришлёт @ссылку в бота</i></blockquote>"
    )


def text_reco_bridge(title: str) -> str:
    name = escape(title or "группа")
    return (
        f"{status_emoji_html('ok')} <b>«{name}»</b>\n"
        "Вы не создатель. Чтобы % шёл вам, создатель нажмёт Да в группе.\n"
        "<blockquote><i>Дальше 3 фото сюда. Да нажимает только создатель — корона в админах</i></blockquote>"
    )


def text_not_owner_switch(title: str = "") -> str:
    name = escape(title or "эта группа")
    return (
        f"{status_emoji_html('no')} <b>Вы не владелец «{name}»</b>\n"
        "<blockquote><i>Чужой чат сдаётся через «Рекомендую бот в группах»</i></blockquote>"
    )


def text_are_owner_switch(title: str = "") -> str:
    name = escape(title or "эта группа")
    return (
        f"{status_emoji_html('wait')} <b>«{name}» — ваша группа</b>\n"
        "<blockquote><i>Сдавайте как владелец</i></blockquote>"
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
    head = ""
    if have > 0:
        head = f"{status_emoji_html('ok')} <b>Есть {have} из {PHOTOS_REQUIRED}</b>\n\n"
    return (
        f"{head}"
        f"{status_emoji_html('wait')} <b>{have + 1} из {PHOTOS_REQUIRED}</b>\n"
        f"{body}\n"
        "<blockquote><i>Пришлите фото сюда</i></blockquote>"
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
        "<blockquote><i>Нажмите «Начать» — три фото заново</i></blockquote>"
    )


def text_after_photos_owner() -> str:
    return text_after_proofs_owner()


def text_after_proofs_owner() -> str:
    return (
        f"{status_emoji_html('ok')} <b>Доказательства приняты</b>\n"
        "<b>Как это работает в вашей группе.</b>\n"
        "Проект положит куты на баланс группы — с него идут выплаты в играх. "
        "Новому человеку проект даст подарочные куты: ими можно сыграть соло здесь, в этой группе. "
        "Снять и перевести подарочные куты нельзя: только научиться играть у вас.\n"
        f"{_epsilon_watch(yours=True)}"
    )


def text_after_proofs_reco() -> str:
    return (
        f"{status_emoji_html('ok')} <b>Доказательства приняты</b>\n"
        "<b>Как вы зарабатываете.</b>\n"
        "14 дней вам капает до 35% комиссии с игр новых людей в этой группе. "
        "Новым считается тот, кто раньше не крутил живые ставки. "
        "Куты приходят вам в этого бота, пока Кут — админ в публичном чате.\n"
        f"{_epsilon_watch(yours=False)}"
    )


def text_after_photos_reco(title: str = "") -> str:
    name = escape(title or "группу")
    return (
        f"{status_emoji_html('wait')} <b>Напишите в группе</b>\n"
        f"Откройте «{name}» и отправьте слово:\n"
        "<blockquote><code>подтверждение</code></blockquote>"
        "<i>Да нажимает только создатель (корона). 24 часа.</i>"
    )


def text_wrote_confirm() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Ждём создателя</b>\n"
        "Под сообщением в группе он должен нажать Да.\n"
        "<blockquote><i>Не нажал — напишите слово ещё раз</i></blockquote>"
    )


def text_mine(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return (
            f"{status_emoji_html('wait')} <b>Пока пусто</b>\n"
            "<blockquote><i>Нажмите «Начать» — сначала группа</i></blockquote>"
        )
    lines = [f"{status_emoji_html('wait')} <b>Мои заявки</b>"]
    for row in rows[:8]:
        title = escape(str(row.get("chat_title") or row.get("title") or "группа"))
        label = claim_status_label(str(row.get("status") or ""))
        lines.append(f"• <b>{title}</b> — <i>{escape(label)}</i>")
    return "\n".join(lines)


def text_cancelled() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Заявку сняли</b>\n"
        "<blockquote><i>Можно начать снова — с группы</i></blockquote>"
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
    return (
        f"{status_emoji_html('no')} <b>Создатель не подтвердил</b>\n"
        "<blockquote><i>Остался один шанс. Напишите <code>подтверждение</code> ещё раз</i></blockquote>"
    )


def text_confirm_no_second() -> str:
    return (
        f"{status_emoji_html('no')} <b>Снова нет</b>\n"
        "<blockquote><i>Эту группу нельзя 31 день. Возьмите другую</i></blockquote>"
    )


def text_not_your_claim() -> str:
    return f"{status_emoji_html('no')} <b>Это не ваша заявка.</b>"


def text_not_creator() -> str:
    return (
        f"{status_emoji_html('no')} <b>Подтверждает только создатель</b>\n"
        "<blockquote><i>Человек с короной в списке админов</i></blockquote>"
    )


def text_confirm_expired() -> str:
    return f"{status_emoji_html('wait')} <b>Это подтверждение уже не действует. Напишите «подтверждение» снова.</b>"


def text_wrong_group() -> str:
    return f"{status_emoji_html('no')} <b>Не та группа.</b>"


def text_need_photos_first() -> str:
    return (
        f"{status_emoji_html('no')} <b>Сначала 3 фото в боте</b>\n"
        "<blockquote><i>Пришлите их Куту в личку</i></blockquote>"
    )


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
    return (
        f"{status_emoji_html('no')} <b>Уже 2 заявки</b>\n"
        "<blockquote><i>Дождитесь проверки или снимите одну в «Мои заявки»</i></blockquote>"
    )


def text_two_live() -> str:
    return (
        f"{status_emoji_html('no')} <b>Уже 2 живые группы</b>\n"
        "<blockquote><i>Новую можно сдать, когда освободится слот</i></blockquote>"
    )


def text_banned_31() -> str:
    return (
        f"{status_emoji_html('no')} <b>Эту группу нельзя 31 день</b>\n"
        "<blockquote><i>Возьмите другую — или подождите</i></blockquote>"
    )


def text_freeze_admin() -> str:
    return (
        f"{status_emoji_html('wait')} <b>У бота нет прав администратора.</b>\n"
        "<blockquote><b>Верните админку — подарки снова включатся</b></blockquote>"
    )


def text_freeze_public() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Группа больше не публичная.</b>\n"
        "<blockquote><b>Верните @адрес — подарки снова включатся</b></blockquote>"
    )


def text_group_busy(*, owner: bool = False) -> str:
    if owner:
        return (
            f"{status_emoji_html('no')} <b>Эту группу уже сдаёт создатель</b>\n"
            "<blockquote><i>Одна группа — один человек. Возьмите другую</i></blockquote>"
        )
    return (
        f"{status_emoji_html('no')} <b>Эту группу уже сдают</b>\n"
        "<blockquote><i>Одна группа — один человек. Возьмите другую</i></blockquote>"
    )


def text_confirm_timeout() -> str:
    return (
        f"{status_emoji_html('no')} <b>Создатель не нажал Да за 24 часа</b>\n"
        "<blockquote><i>Можно начать снова — с группы</i></blockquote>"
    )


def text_owner_no_confirm() -> str:
    return (
        f"{status_emoji_html('wait')} <b>Вам подтверждение не нужно</b>\n"
        "<blockquote><i>Заявка создателя идёт на проверку без Да</i></blockquote>"
    )


def text_no_groups() -> str:
    return text_how()


def text_resume_claim(title: str, status: str) -> str:
    name = escape(title or "группа")
    label = claim_status_label(status)
    return (
        f"{status_emoji_html('wait')} <b>«{name}»</b>\n"
        f"<blockquote><b>{escape(label)}</b></blockquote>"
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
