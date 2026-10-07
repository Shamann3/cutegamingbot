# -*- coding: utf-8 -*-
"""Правила брака без базы и без Telegram.

Цена, разбор фразы, срок «вместе», строка профиля. Тексты живут в marriage_design.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Any, Optional

from bot.funcs.marriage_design import (
    AFTER_PERCENT,
    CARD_WORDS,
    DOUBLE_UNTIL,
    FIRST_PAID,
    FREE_WEDDINGS,
    HELP_TAIL,
    LEAVE_WORDS,
    OFF_WORDS,
    ON_WORDS,
    PROFILE_EMPTY,
    PROFILE_LINE,
    PROPOSAL_MINUTES,
    RP,
    RP_PER_VERB_A_DAY,
    RP_LINE,
    RP_NOTE,
    SHOW_EMPTY_PROFILE,
    TONE_WORDS,
    TOP_LIMIT,
    TOP_WORDS,
    WED_WORDS,
    RING,
    SHARED_WITH_GENERAL_RP,
)

MSK = timezone(timedelta(hours=3))
_NOTE_MAX = 80


def _clamp_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(default)
    return max(lo, min(hi, number))


def settings_view(raw: Any = None) -> dict:
    """Настройки панели. Пустое или битое поле остаётся на числе из файла дизайна."""
    src = raw if isinstance(raw, dict) else {}
    known = {item["id"] for item in RP}
    incoming = src.get("verbs") if isinstance(src.get("verbs"), dict) else {}
    verbs = {}
    for key, value in incoming.items():
        if key in known:
            verbs[str(key)] = _clamp_int(value, 0, 0, 100000)
    enabled = src.get("enabled", True)
    tone_on = src.get("toneOn", True)
    return {
        "enabled": bool(enabled) if isinstance(enabled, bool) else str(enabled).lower() not in ("0", "false", "no", "off"),
        "freeWeddings": _clamp_int(src.get("freeWeddings", FREE_WEDDINGS), FREE_WEDDINGS, 0, 30),
        "firstPaid": _clamp_int(src.get("firstPaid", FIRST_PAID), FIRST_PAID, 0, 100000),
        "doubleUntil": _clamp_int(src.get("doubleUntil", DOUBLE_UNTIL), DOUBLE_UNTIL, 1, 1000000),
        "afterPercent": _clamp_int(src.get("afterPercent", AFTER_PERCENT), AFTER_PERCENT, 0, 100),
        "proposalMinutes": _clamp_int(src.get("proposalMinutes", PROPOSAL_MINUTES), PROPOSAL_MINUTES, 1, 1440),
        "rpPerDay": _clamp_int(src.get("rpPerDay", RP_PER_VERB_A_DAY), RP_PER_VERB_A_DAY, 1, 20),
        "topLimit": _clamp_int(src.get("topLimit", TOP_LIMIT), TOP_LIMIT, 3, 30),
        "showEmptyProfile": bool(src.get("showEmptyProfile", SHOW_EMPTY_PROFILE)),
        "toneOn": bool(tone_on) if isinstance(tone_on, bool) else str(tone_on).lower() not in ("0", "false", "no", "off"),
        "toneStart": _clamp_int(src.get("toneStart", 80), 80, 0, 100),
        "toneGain": _clamp_int(src.get("toneGain", 12), 12, 0, 100),
        "toneDecay": _clamp_int(src.get("toneDecay", 8), 8, 0, 100),
        "verbs": verbs,
    }


def wedding_price(done: int, settings: Optional[dict] = None) -> int:
    """Сколько кут стоит следующая свадьба.

    done — сколько свадеб этот человек уже довёл до согласия, включая
    те, что потом развелись. Первые бесплатные свадьбы берутся из настроек.
    """
    knobs = settings_view(settings) if settings else None
    free = knobs["freeWeddings"] if knobs else FREE_WEDDINGS
    first = knobs["firstPaid"] if knobs else FIRST_PAID
    cap = knobs["doubleUntil"] if knobs else DOUBLE_UNTIL
    percent = knobs["afterPercent"] if knobs else AFTER_PERCENT
    try:
        n = max(0, int(done))
    except (TypeError, ValueError):
        n = 0
    if n < free:
        return 0
    price = int(first)
    for _ in range(n - free):
        price = _next_price(price, cap, percent)
    return price


def _next_price(price: int, cap: int = DOUBLE_UNTIL, percent: int = AFTER_PERCENT) -> int:
    if price < cap:
        doubled = price * 2
        if doubled <= cap:
            return doubled
        return cap
    return (price * (100 + percent) + 50) // 100


def price_ladder(settings: Optional[dict] = None, count: int = 12) -> list:
    view = settings_view(settings)
    total = max(1, min(24, int(count)))
    return [{"wedding": index + 1, "price": wedding_price(index, view)} for index in range(total)]


def verb_catalog(settings: Optional[dict] = None) -> list:
    view = settings_view(settings)
    chosen = view["verbs"]
    rows = []
    for item in RP:
        price = chosen[item["id"]] if item["id"] in chosen else int(item.get("price") or 0)
        rows.append({"id": item["id"], "title": item["verbs"][0], "price": price})
    return rows


def verb_price(item: dict, settings: Optional[dict] = None) -> int:
    if not item:
        return 0
    view = settings_view(settings) if settings else None
    if view and item.get("id") in view["verbs"]:
        return int(view["verbs"][item["id"]])
    try:
        return max(0, int(item.get("price") or 0))
    except (TypeError, ValueError):
        return 0


def blocks_new_person(state: str) -> bool:
    """Эти состояния не дают человеку открыть вторую заявку или второй брак."""
    return str(state or "") in ("ask", "billing", "live")


def _as_date(value: Any):
    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=MSK)
        return moment.astimezone(MSK).date()
    if isinstance(value, date):
        return value
    return None


def tone_score(points: Any, day: Any, today: date, decay: int, since: Any = None) -> int:
    """Тонус на сегодня. Пустой день учёта значит, что часы ещё не запущены."""
    try:
        base = int(points)
    except (TypeError, ValueError):
        base = 80
    base = max(0, min(100, base))
    anchor = _as_date(day)
    if anchor is None:
        return base
    late = (today - anchor).days
    if late <= 0:
        return base
    return max(0, base - max(0, int(decay)) * late)


def tone_after(points: Any, day: Any, today: date, decay: int, gain: int, since: Any = None):
    """Первый жест новых суток поднимает тонус. Повтор в тот же день не крутит его снова."""
    anchor = _as_date(day)
    current = tone_score(points, day, today, decay, since)
    if anchor is None or anchor == today:
        return current, today
    return min(100, current + max(0, int(gain))), today


def tone_label(score: int) -> str:
    value = max(0, min(100, int(score)))
    if value >= 80:
        return "в тонусе"
    if value >= 45:
        return "спокойно"
    if value >= 15:
        return "тихо"
    return "остывает"


def which_wedding(done: int) -> int:
    try:
        return max(0, int(done)) + 1
    except (TypeError, ValueError):
        return 1


def free_left(done: int) -> int:
    try:
        n = max(0, int(done))
    except (TypeError, ValueError):
        n = 0
    return max(0, FREE_WEDDINGS - n)


def person_html(user_id: int, first_name: str, username: str = "") -> str:
    name = escape((first_name or "").strip() or "игрок")
    user = str(username or "").strip().lstrip("@")
    if user:
        return f"<a href='https://t.me/{escape(user)}'>{name}</a>"
    return f"<a href='tg://user?id={int(user_id)}'>{name}</a>"


def as_aware(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=MSK)
    if isinstance(value, str):
        raw = value.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=MSK)
            except ValueError:
                continue
    return None


def together_label(since: Any, now: datetime) -> str:
    start = as_aware(since)
    if start is None:
        return "вместе"
    moment = now if now.tzinfo is not None else now.replace(tzinfo=MSK)
    days = (moment.astimezone(MSK).date() - start.astimezone(MSK).date()).days
    if days <= 0:
        return "сегодня"
    if days == 1:
        return "1 день"
    if 2 <= days <= 4:
        return f"{days} дня"
    if days < 30:
        return f"{days} дн."
    months = days // 30
    if months < 12:
        return "1 мес." if months == 1 else f"{months} мес."
    years = days // 365
    if years == 1:
        return "1 год"
    if 2 <= years % 10 <= 4 and years % 100 not in (12, 13, 14):
        return f"{years} года"
    return f"{years} лет"


def wedding_date(since: Any) -> str:
    start = as_aware(since)
    if start is None:
        return ""
    return start.astimezone(MSK).strftime("%d.%m.%Y %H:%M")


def profile_line(view: Optional[dict], now: Optional[datetime] = None) -> str:
    """Маленькая строка под активностью. Пустая строка — строку не показывать."""
    moment = now or datetime.now(MSK)
    name = ""
    since = None
    if view:
        name = str(view.get("name_html") or "").strip()
        since = view.get("since")
    if not name:
        if view and view.get("hide_empty"):
            return ""
        if not SHOW_EMPTY_PROFILE:
            return ""
        return PROFILE_EMPTY.format(ring=RING)
    line = PROFILE_LINE.format(
        ring=RING,
        name=name,
        span=together_label(since, moment),
    )
    tone = str((view or {}).get("tone_label") or "").strip()
    if tone:
        line = line.replace("</b>", f" · {escape(tone)}</b>", 1)
    return line


def verb_list() -> str:
    return " · ".join(item["verbs"][0] for item in RP)


def shares_general_rp(item: dict) -> bool:
    return any(verb in SHARED_WITH_GENERAL_RP for verb in item.get("verbs") or ())


def rp_by_id(verb_id: str) -> Optional[dict]:
    key = str(verb_id or "")
    for item in RP:
        if item["id"] == key:
            return item
    return None


def match_rp(text: str) -> Optional[tuple]:
    """(жест, приписка) если сообщение начинается с жеста пары."""
    raw = " ".join(str(text or "").lower().split())
    if not raw or len(raw) > 200:
        return None
    found = None
    for item in RP:
        for verb in item["verbs"]:
            note = _tail(raw, verb)
            if note is None:
                continue
            if found is None or len(verb) > len(found[1]):
                found = (item, verb, note)
    if found is None:
        return None
    item, _verb, note = found
    return item, _clip(note)


def _tail(text: str, verb: str) -> Optional[str]:
    if text == verb:
        return ""
    prefix = verb + " "
    if text.startswith(prefix):
        return text[len(prefix):].strip()
    return None


def _clip(note: str) -> str:
    clean = " ".join(str(note or "").split())
    if len(clean) > _NOTE_MAX:
        clean = clean[:_NOTE_MAX].rstrip()
    return clean


def rp_html(item: dict, a_html: str, b_html: str, note: str = "") -> str:
    body = RP_LINE.format(
        emoji=item["emoji"],
        a=a_html,
        does=escape(str(item["does"])),
        b=b_html,
    )
    extra = _clip(note)
    if extra:
        body = body + "\n" + RP_NOTE.format(note=escape(extra))
    return body


def classify(text: str) -> Optional[dict]:
    """Что это за фраза. None — бот брака её не берёт."""
    raw = " ".join(str(text or "").lower().split())
    if not raw or len(raw) > 200:
        return None
    if raw in ON_WORDS:
        return {"kind": "on"}
    if raw in OFF_WORDS:
        return {"kind": "off"}
    if raw in CARD_WORDS or raw in TONE_WORDS:
        return {"kind": "card"}
    if raw in LEAVE_WORDS:
        return {"kind": "leave"}
    if raw in TOP_WORDS:
        return {"kind": "top"}
    parts = raw.split(" ", 1)
    head, tail = parts[0], (parts[1] if len(parts) > 1 else "")
    if head in WED_WORDS:
        if tail.split(" ", 1)[0] in HELP_TAIL:
            return None
        return {"kind": "wed", "tail": tail}
    hit = match_rp(raw)
    if hit is not None:
        item, note = hit
        return {"kind": "rp", "rp": item, "note": note}
    return None


def mention_in(tail: str) -> str:
    """@имя, t.me/имя или число из хвоста команды. Пусто — не было."""
    for part in str(tail or "").split():
        if part.startswith("@"):
            return part[1:]
        if "t.me/" in part:
            return part.rstrip("/").split("/")[-1].split("?")[0]
        if part.isdigit():
            return part
    return ""
