# -*- coding: utf-8 -*-
"""Праздники пары и тихий день. В магазин попадает только то, что создатель оставил включённым."""
import math

PERIODS = (
    {"day": 7, "name": "Первая неделя"},
    {"day": 14, "name": "Две недели"},
    {"day": 30, "name": "Месяц"},
    {"day": 100, "name": "Сто дней"},
)
PRIZES = (
    {"id": "envelope", "name": "Конверт", "emoji": "✉️", "on": True, "blurb": "Куты, если предмет не успели купить."},
    {"id": "care", "name": "Забота", "emoji": "🕯", "on": True, "blurb": "Блик, свеча или очаг. Забота только получившему."},
    {"id": "ribbon", "name": "Лента", "emoji": "🎀", "on": True, "blurb": "Свой знак брака в профиле. Снимается фразой."},
    {"id": "premium3", "name": "Премиум 3 мес.", "emoji": "⭐", "on": True, "blurb": "Предмет проекта. Его передаёт создатель, не бот Telegram."},
    {"id": "premium6", "name": "Премиум 6 мес.", "emoji": "🌟", "on": True, "blurb": "Длинный праздник. Предмет тоже передаёт создатель."},
)
QUIET_NAME = "Тихий день"
QUIET_CODE = "mrgquiet"
QUIET_EMOJI = "🤫"


def _clip(value, default, limit=80):
    text = " ".join(str(value or "").replace("<", " ").replace(">", " ").split())
    return (text or default)[:limit]


def periods_view(src):
    raw = src if isinstance(src, list) else []
    saved = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            saved[int(row.get("day"))] = row
        except (TypeError, ValueError):
            continue
    out = []
    for base in PERIODS:
        got = saved.get(base["day"]) or {}
        out.append({"day": base["day"], "name": _clip(got.get("name"), base["name"], 24)})
    return out


def prizes_view(src):
    raw = src if isinstance(src, list) else []
    saved = {}
    for row in raw:
        if isinstance(row, dict) and row.get("id"):
            saved[str(row["id"])] = row
    out = []
    for base in PRIZES:
        got = saved.get(base["id"]) or {}
        flag = got.get("on", base["on"])
        out.append({
            "id": base["id"],
            "name": base["name"],
            "emoji": base["emoji"],
            "on": bool(flag),
            "blurb": _clip(got.get("blurb"), base["blurb"]),
        })
    return out


def quiet_row(cfg, force=False):
    cfg = cfg if isinstance(cfg, dict) else {}
    if not force and cfg.get("quietOn") is False:
        return None
    emoji = _clip(cfg.get("quietEmoji"), QUIET_EMOJI, 4) or QUIET_EMOJI
    try:
        price = int(cfg.get("quietPrice", 40))
    except (TypeError, ValueError):
        price = 40
    return {
        "id": "quiet",
        "name": QUIET_NAME,
        "name1": QUIET_CODE,
        "emoji": emoji,
        "price": max(0, min(100000, price)),
        "care": 0,
        "buy": "Купить тихий день",
        "use": "Затихнуть",
        "blurb": "Раз в 7 дней закрывает вашу половину, если не успели.",
    }


def fund_split(price, fund_percent=20, keep_percent=10):
    price = max(0, int(price or 0))
    fund_percent = max(0, min(80, int(fund_percent or 0)))
    keep_percent = max(0, min(80, int(keep_percent or 0)))
    commission = price * fund_percent // 100
    keep = math.ceil(commission * keep_percent / 100) if commission else 0
    keep = min(keep, commission)
    fund = commission - keep
    return {"price": price, "fund": fund, "keep": keep, "project": price - fund}


def quiet_pay(item_name, price, cfg=None):
    cfg = cfg if isinstance(cfg, dict) else {}
    token = str(item_name or "")
    row = quiet_row(cfg, force=True)
    if token not in (row["name"], row["name1"]):
        return None
    if cfg.get("quietOn") is False:
        return None
    split = fund_split(price, cfg.get("fundPercent", 20), cfg.get("projectKeepPercent", 10))
    try:
        chat = int(cfg.get("giftFundChat") or -1004440027555)
    except (TypeError, ValueError):
        chat = -1004440027555
    split["chat"] = chat
    return split


def done_days(text):
    out = set()
    for part in str(text or "").split(","):
        if part.strip().isdigit():
            out.add(int(part.strip()))
    return out


def with_day(text, day):
    got = done_days(text)
    got.add(int(day))
    return ",".join(str(n) for n in sorted(got))


def due_period(streak, done, periods=None):
    rows = periods if periods else periods_view(None)
    closed = done_days(done)
    try:
        days = int(streak or 0)
    except (TypeError, ValueError):
        days = 0
    for row in rows:
        if days >= int(row["day"]) and int(row["day"]) not in closed:
            return row
    return None


def remember_wish(payer, partner, side, prize_id):
    prize_id = str(prize_id or "")
    if side == "payer":
        payer = prize_id
    else:
        partner = prize_id
    locked = payer if payer and partner and payer == partner else ""
    return {"payer": payer, "partner": partner, "locked": locked}


def care_code(day):
    if int(day) <= 7:
        return "mrgglow"
    if int(day) <= 14:
        return "mrgcandle"
    return "mrghearth"


def quiet_effect(you, need, last, today):
    if last is not None and (today - last).days < 7:
        return {"ok": False, "reason": "week", "care": 0}
    gap = max(0, int(need) - int(you))
    if gap <= 0:
        return {"ok": False, "reason": "full", "care": 0}
    return {"ok": True, "reason": "", "care": gap}


def award_plan(prize_id, fund, shop_price, shop_remains, envelope, extra):
    fund = max(0, int(fund or 0))
    extra = max(0, int(extra or 0))
    shop_price = max(0, int(shop_price or 0))
    remains = max(0, int(shop_remains or 0))
    if prize_id == "envelope":
        pay = max(0, int(envelope or 0)) + extra
        if pay > 0 and fund >= pay:
            return {"do": "kut", "amount": pay}
        return {"do": "short", "amount": pay}
    if prize_id in ("premium3", "premium6"):
        if remains > 0 and shop_price > 0 and fund >= shop_price:
            return {"do": "keeper", "amount": shop_price, "qty": 1}
        return {"do": "keeper_empty", "amount": shop_price}
    if remains > 0 and shop_price > 0 and fund >= shop_price:
        return {"do": "shop", "amount": shop_price, "qty": 1}
    fallback = shop_price * 80 // 100 + extra
    if fallback > 0 and fund >= fallback:
        return {"do": "sorry", "amount": fallback}
    return {"do": "short", "amount": fallback}
