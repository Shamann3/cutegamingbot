# -*- coding: utf-8 -*-
"""Правила брака без базы и без Telegram.

Цена, разбор фразы, срок «вместе», строка профиля. Тексты живут в marriage_design.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Any, Optional

from marriage_engine.design import (
    AFTER_PERCENT,
    CARD_WORDS,
    DOUBLE_UNTIL,
    FIRST_PAID,
    FREE_WEDDINGS,
    GIFTS,
    HELP_TAIL,
    LEVELS,
    LEAVE_WORDS,
    LIST_WORDS,
    OFF_WORDS,
    ON_WORDS,
    PROFILE_EMPTY,
    PROFILE_LINE,
    PROPOSAL_MINUTES,
    RESCUE_HOURS,
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
    care = {}
    for key, value in incoming.items():
        if key in known:
            verbs[str(key)] = _clamp_int(value, 0, 0, 100000)
    incoming_care = src.get("care") if isinstance(src.get("care"), dict) else {}
    for key, value in incoming_care.items():
        if key in known:
            care[str(key)] = _clamp_int(value, 0, 0, 100)
    enabled = src.get("enabled", True)
    tone_on = src.get("toneOn", True)
    spark_on = src.get("sparkOn", True)
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
        "rescueHours": _clamp_int(src.get("rescueHours", RESCUE_HOURS), RESCUE_HOURS, 1, 48),
        "sparkOn": bool(spark_on) if isinstance(spark_on, bool) else str(spark_on).lower() not in ("0", "false", "no", "off"),
        "levels": normalize_levels(src.get("levels")),
        "glowPrice": _clamp_int(src.get("glowPrice", _gift_default("glow", "price", 12)), 12, 0, 100000),
        "glowCare": _clamp_int(src.get("glowCare", _gift_default("glow", "care", 3)), 3, 1, 100),
        "candlePrice": _clamp_int(src.get("candlePrice", _gift_default("candle", "price", 25)), 25, 0, 100000),
        "candleCare": _clamp_int(src.get("candleCare", _gift_default("candle", "care", 8)), 8, 1, 100),
        "hearthPrice": _clamp_int(src.get("hearthPrice", _gift_default("hearth", "price", 70)), 70, 0, 100000),
        "hearthCare": _clamp_int(src.get("hearthCare", _gift_default("hearth", "care", 20)), 20, 1, 100),
        "matchPrice": _clamp_int(src.get("matchPrice", _gift_default("match", "price", 80)), 80, 0, 100000),
        "ribbonPrice": _clamp_int(src.get("ribbonPrice", _gift_default("ribbon", "price", 150)), 150, 0, 100000),
        "verbs": verbs,
        "care": care,
    }


def _gift_default(kind: str, field: str, fallback: int) -> int:
    for item in GIFTS:
        if item["id"] == kind:
            try:
                return int(item.get(field, fallback))
            except (TypeError, ValueError):
                return fallback
    return fallback


_CARE_GIFTS = ("glow", "candle", "hearth")


def gift_catalog(settings: Optional[dict] = None) -> list:
    """Предметы с ценой из панели. Блик, свеча и очаг кладут разную заботу."""
    view = settings_view(settings)
    rows = []
    for item in GIFTS:
        kind = item["id"]
        care = int(view[f"{kind}Care"]) if kind in _CARE_GIFTS else 0
        rows.append({
            "id": kind,
            "name": item["name"],
            "name1": item["name1"],
            "emoji": item["emoji"],
            "buy": item["buy"],
            "use": item["use"],
            "price": int(view[f"{kind}Price"]),
            "care": care,
        })
    return rows


def gift_plan(kind: str, fading: bool, you: int, need: int, ribbon: bool = False, care: int = 5) -> dict:
    """Можно ли потратить предмет. Забота — только доля нажавшего.

    Блик, свеча и очаг кладут своё число даже сверх нормы: лишнее остаётся.
    Спичка закрывает только свою половину вчера. Лента не трогает искру.
    """
    try:
        mine = int(you)
        whole = int(need)
        plus = int(care)
    except (TypeError, ValueError):
        mine, whole, plus = 0, 0, 0
    if kind in _CARE_GIFTS:
        return {"ok": True, "reason": "", "care": max(1, plus)}
    if kind == "match":
        if not fading:
            return {"ok": False, "reason": "calm", "care": 0}
        gap = whole - mine
        if gap <= 0:
            return {"ok": False, "reason": "full", "care": 0}
        return {"ok": True, "reason": "", "care": gap}
    if kind == "ribbon":
        if ribbon:
            return {"ok": False, "reason": "worn", "care": 0}
        return {"ok": True, "reason": "", "care": 0}
    return {"ok": False, "reason": "bad", "care": 0}


def normalize_levels(raw: Any) -> list:
    """Лестница из панели. Пустой или битый список остаётся на уровнях из файла дизайна.

    Первый уровень всегда с нуля дней. Одинаковые дни разводятся. Имена без тегов.
    """
    found = []
    if isinstance(raw, list):
        for index, item in enumerate(raw[:12]):
            if not isinstance(item, dict):
                continue
            name = " ".join(
                str(item.get("name") or "").replace("<", " ").replace(">", " ").replace("&", " ").split()
            )[:24]
            found.append({
                "order": index,
                "days": _clamp_int(item.get("days"), 0, 0, 3650),
                "goal": _clamp_int(item.get("goal"), 10, 2, 500),
                "name": name,
            })
    if not found:
        return [
            {"id": int(row["id"]), "days": int(row["days"]), "name": str(row["name"]), "goal": int(row["goal"])}
            for row in LEVELS
        ]
    found.sort(key=lambda row: (row["days"], row["order"]))
    found[0]["days"] = 0
    used = set()
    rows = []
    for item in found:
        day = item["days"]
        while day in used and day < 3650:
            day += 1
        used.add(day)
        name = item["name"] or f"Уровень {len(rows) + 1}"
        rows.append({"days": day, "goal": item["goal"], "name": name})
    for index, row in enumerate(rows, start=1):
        row["id"] = index
    return rows


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


def verb_care(item: dict, settings: Optional[dict] = None) -> int:
    if not item:
        return 0
    view = settings_view(settings) if settings else None
    if view and item.get("id") in view["care"]:
        return int(view["care"][item["id"]])
    try:
        return max(0, int(item.get("care") or 0))
    except (TypeError, ValueError):
        return 0


def each_share(goal: int) -> int:
    """Половина дневной нормы. Оба должны добрать свою, не общую кучу."""
    try:
        whole = int(goal)
    except (TypeError, ValueError):
        whole = 10
    return max(1, (max(2, whole) + 1) // 2)


def level_table(settings: Optional[dict] = None) -> list:
    if isinstance(settings, dict) and isinstance(settings.get("levels"), list) and settings["levels"]:
        return normalize_levels(settings["levels"])
    if settings:
        return settings_view(settings)["levels"]
    return normalize_levels(None)


def level_of(streak: int, settings: Optional[dict] = None) -> dict:
    try:
        days = max(0, int(streak))
    except (TypeError, ValueError):
        days = 0
    table = level_table(settings)
    current = table[0]
    for row in table:
        if days >= int(row["days"]):
            current = row
    return current


def next_level(streak: int, settings: Optional[dict] = None):
    try:
        days = max(0, int(streak))
    except (TypeError, ValueError):
        days = 0
    for row in level_table(settings):
        if int(row["days"]) > days:
            return row
    return None


def rescue_deadline(day: date, hours: int) -> datetime:
    start = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=MSK)
    return start + timedelta(hours=max(1, int(hours)))


def clock_label(moment: datetime, now: datetime) -> str:
    when = moment.astimezone(MSK)
    current = now.astimezone(MSK)
    if when.date() == current.date():
        return when.strftime("%H:%M")
    return when.strftime("%d.%m %H:%M")


def _spark_state(raw: Any) -> dict:
    src = raw if isinstance(raw, dict) else {}
    fade = src.get("fade_until")
    if isinstance(fade, datetime) and fade.tzinfo is None:
        fade = fade.replace(tzinfo=MSK)
    elif not isinstance(fade, datetime):
        fade = None
    return {
        "spark_days": max(0, int(src.get("spark_days") or 0)),
        "spark_best": max(0, int(src.get("spark_best") or 0)),
        "care_total": max(0, int(src.get("care_total") or 0)),
        "care_payer": max(0, int(src.get("care_payer") or 0)),
        "care_partner": max(0, int(src.get("care_partner") or 0)),
        "spark_day": _as_date(src.get("spark_day")),
        "fade_until": fade,
        "spark_lost": max(0, int(src.get("spark_lost") or 0)),
    }


def _spark_view(state: dict, now: datetime, hours: int, saved: bool = False, settings: Optional[dict] = None) -> dict:
    streak = int(state["spark_days"])
    level = level_of(streak, settings)
    nxt = next_level(streak, settings)
    need = each_share(int(level["goal"]))
    fading = bool(state.get("fade_until")) and state.get("spark_day") is not None and state["spark_day"] < now.astimezone(MSK).date()
    both = state["care_payer"] >= need and state["care_partner"] >= need and not fading
    if fading:
        both = False
    deadline = state.get("fade_until") if fading else None
    lost = int(state.get("spark_lost") or 0)
    return {
        "state": state,
        "level": level,
        "next": nxt,
        "days_left": max(0, int(nxt["days"]) - streak) if nxt else 0,
        "need": need,
        "goal": int(level["goal"]),
        "fading": fading,
        "saved": saved,
        "both_done": state["care_payer"] >= need and state["care_partner"] >= need and not fading,
        "lost": lost,
        "clock": clock_label(deadline, now) if isinstance(deadline, datetime) else "",
        "table": level_table(settings),
        "changed": True,
    }


def _spend_share(state: dict, need: int) -> None:
    """Закрытый день снимает только норму. Лишнее остаётся на своей стороне."""
    share = max(0, int(need))
    state["care_payer"] = max(0, int(state["care_payer"]) - share)
    state["care_partner"] = max(0, int(state["care_partner"]) - share)


def settle_spark(raw: Any, now: datetime, rescue_hours: int = RESCUE_HOURS, settings: Optional[dict] = None) -> dict:
    """Закрывает прошедшие дни. Не добавляет новую заботу."""
    moment = now if now.tzinfo is not None else now.replace(tzinfo=MSK)
    moment = moment.astimezone(MSK)
    today = moment.date()
    hours = max(1, int(rescue_hours or RESCUE_HOURS))
    state = _spark_state(raw)
    if state["spark_day"] is None:
        state["spark_day"] = today
        state["care_payer"] = 0
        state["care_partner"] = 0
        state["fade_until"] = None
        return _spark_view(state, moment, hours, settings=settings)
    for _ in range(8):
        day = state["spark_day"]
        if day is None or day >= today:
            state["fade_until"] = None
            break
        need = each_share(int(level_of(state["spark_days"], settings)["goal"]))
        deadline = rescue_deadline(day, hours)
        if state["care_payer"] >= need and state["care_partner"] >= need:
            state["spark_days"] += 1
            state["spark_best"] = max(state["spark_best"], state["spark_days"])
            state["spark_day"] = day + timedelta(days=1)
            _spend_share(state, need)
            state["fade_until"] = None
            continue
        if moment <= deadline:
            state["fade_until"] = deadline
            return _spark_view(state, moment, hours, settings=settings)
        lost = state["spark_days"]
        if lost > 0:
            state["spark_lost"] = lost
        state["spark_days"] = 0
        state["spark_day"] = today
        state["care_payer"] = 0
        state["care_partner"] = 0
        state["fade_until"] = None
        break
    return _spark_view(state, moment, hours, settings=settings)


def add_spark_care(raw: Any, side: str, amount: int, now: datetime, rescue_hours: int = RESCUE_HOURS, settings: Optional[dict] = None) -> dict:
    """Плюс забота одному из двоих. Спасение закрывает вчера, не сегодня."""
    view = settle_spark(raw, now, rescue_hours, settings)
    state = view["state"]
    moment = now if now.tzinfo is not None else now.replace(tzinfo=MSK)
    moment = moment.astimezone(MSK)
    try:
        plus = max(0, int(amount))
    except (TypeError, ValueError):
        plus = 0
    key = "care_payer" if side == "payer" else "care_partner"
    fading = bool(view.get("fading"))
    state[key] = int(state[key]) + plus
    state["care_total"] = int(state["care_total"]) + plus
    saved = False
    if fading:
        need = each_share(int(level_of(state["spark_days"], settings)["goal"]))
        if state["care_payer"] >= need and state["care_partner"] >= need:
            state["spark_days"] += 1
            state["spark_best"] = max(state["spark_best"], state["spark_days"])
            if state["spark_day"] is not None and state["spark_day"] < moment.date():
                state["spark_day"] = moment.date()
                _spend_share(state, need)
            state["fade_until"] = None
            state["spark_lost"] = 0
            saved = True
    return _spark_view(state, moment, rescue_hours, saved=saved, settings=settings)


def spark_side(user_id: int, payer_id: int) -> str:
    return "payer" if int(user_id) == int(payer_id) else "partner"


def spark_split(state: dict, user_id: int, payer_id: int):
    if spark_side(user_id, payer_id) == "payer":
        return int(state.get("care_payer") or 0), int(state.get("care_partner") or 0)
    return int(state.get("care_partner") or 0), int(state.get("care_payer") or 0)


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


def tone_brief(points: Any, day: Any, today: date, decay: int, gain: int) -> dict:
    """Число на сегодня и одна фраза, что сделает ближайший жест."""
    score = tone_score(points, day, today, decay)
    nxt, _day = tone_after(points, day, today, decay, gain)
    anchor = _as_date(day)
    if anchor is None or anchor == today:
        hint = "Сегодня уже учтён. Завтра жест снова поднимет."
        fresh = False
    else:
        hint = f"Один жест сегодня поднимет до {nxt}."
        fresh = True
    return {
        "score": score,
        "label": tone_label(score),
        "hint": hint,
        "fresh": fresh,
        "next": nxt,
    }


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


def shares_general_rp(item: dict, verb: str = "") -> bool:
    """Общее рп забирает только свои старые слова, не короткие формы брака."""
    said = str(verb or "")
    if said:
        return said in SHARED_WITH_GENERAL_RP
    return any(word in SHARED_WITH_GENERAL_RP for word in item.get("verbs") or ())


def rp_by_id(verb_id: str) -> Optional[dict]:
    key = str(verb_id or "")
    for item in RP:
        if item["id"] == key:
            return item
    return None


def match_rp(text: str) -> Optional[tuple]:
    """(жест, слово, приписка) если сообщение начинается с жеста пары."""
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
    item, verb, note = found
    return item, verb, _clip(note)


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


def _phrase(raw: str, words) -> Optional[str]:
    """Пустая строка — фраза равна команде. Иначе хвост. None — не она."""
    for word in sorted(words, key=len, reverse=True):
        if raw == word:
            return ""
        if raw.startswith(word + " "):
            return raw[len(word) + 1:].strip()
    return None


def classify(text: str) -> Optional[dict]:
    """Что это за фраза. None — бот брака её не берёт."""
    raw = " ".join(str(text or "").lower().split())
    if not raw or len(raw) > 200:
        return None
    if _phrase(raw, ON_WORDS) is not None:
        return {"kind": "on"}
    if _phrase(raw, OFF_WORDS) is not None:
        return {"kind": "off"}
    if _phrase(raw, LEAVE_WORDS) is not None:
        return {"kind": "leave"}
    if _phrase(raw, CARD_WORDS) is not None:
        return {"kind": "card"}
    if _phrase(raw, TONE_WORDS) is not None:
        return {"kind": "tone"}
    if _phrase(raw, TOP_WORDS) is not None:
        return {"kind": "top"}
    if _phrase(raw, LIST_WORDS) is not None:
        return {"kind": "list"}
    tail = _phrase(raw, WED_WORDS)
    if tail is not None:
        if tail.split(" ", 1)[0] in HELP_TAIL:
            return None
        return {"kind": "wed", "tail": tail}
    hit = match_rp(raw)
    if hit is not None:
        item, verb, note = hit
        return {"kind": "rp", "rp": item, "note": note, "verb": verb}
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
