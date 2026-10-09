# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta, timezone
from marriage_engine.m_act import act_plan, dawn_up, moon_up
MSK = timezone(timedelta(hours=3))
_AMOUNT = {"self", "other", "both", "dawn"}
_EFFECTS = (
    ("self", "Тепло себе", "Забота"),
    ("other", "Тепло партнёру", "Забота"),
    ("both", "Тепло обоим", "Забота"),
    ("norm", "Ночью добить свою норму", ""),
    ("dawn", "Утром, пока искра гаснет", "Забота"),
    ("gap", "Дожечь вчерашнюю половину", ""),
    ("vow", "Один раз дописать день после ответа", ""),
    ("mark", "Свой знак в профиле", ""),
    ("propose", "Сделать предложение", ""),
    ("ring", "Отдать кольцо после предложения", ""),
    ("seed", "Саженец на ферму", ""),
    ("pantry", "Овощ для крафта", ""),
)
_KNOWN = {row[0] for row in _EFFECTS}
def build(settings):
    return _tail(settings)
def _tail(s):
    from marriage_engine.m_ids import HEART as H, SPARK as K, FREE_WEDDINGS as A, FIRST_PAID as B, DOUBLE_UNTIL as C
    from marriage_engine.look import BTN_YES as Y, BTN_NO as N, HELP_PAY, HELP_PAGE
    from marriage_engine.m_join import LEVELS as L
    s = s if isinstance(s, dict) else {}
    r = s.get("levels") if isinstance(s.get("levels"), list) and s.get("levels") else L
    e = (int(r[0].get("goal") or 10) + 1) // 2
    n = str(int(s.get("freeWeddings", A) or 0)) + " " + str(int(s.get("firstPaid", B) or 0)) + " " + str(int(s.get("doubleUntil", C) or 0))
    return HELP_PAGE.format(heart=H, pay=HELP_PAY, ladder=n, yes=Y, no=N, spark=K, level=str(r[0].get("name")), each=e)
def each_share(goal):
    return (max(2, int(goal)) + 1) // 2
def _clamp(value, default, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(default)
    return max(int(low), min(int(high), number))
def level_of(streak, settings=None):
    from marriage_engine.m_join import LEVELS
    rows = (settings or {}).get("levels") if isinstance(settings, dict) and (settings or {}).get("levels") else LEVELS
    cur = rows[0]
    for row in rows:
        if int(row["days"]) <= int(streak or 0):
            cur = row
        else:
            break
    return cur
def normalize_levels(raw):
    from marriage_engine.m_join import LEVELS
    found = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict) or len(found) == 12:
                continue
            name = " ".join(str(item.get("name") or "").replace("<", " ").replace(">", " ").replace("&", " ").split())[:24]
            found.append({"days": _clamp(item.get("days"), 0, 0, 3650), "goal": _clamp(item.get("goal"), 10, 2, 500), "name": name})
    if not found:
        return [dict(r) for r in LEVELS]
    found.sort(key=lambda row: row["days"])
    found[0]["days"] = 0
    used = -1
    for i, row in enumerate(found):
        if row["days"] <= used:
            row["days"] = min(3650, used + 1)
        used = row["days"]
        if not row["name"]:
            row["name"] = "Уровень " + str(i + 1)
        row["id"] = i + 1
    return found
def which_wedding(done):
    return int(done) + 1
def wedding_price(done, settings=None):
    view = settings if isinstance(settings, dict) and "freeWeddings" in settings else None
    if view is None:
        from marriage_engine.m_ids import FREE_WEDDINGS, FIRST_PAID, DOUBLE_UNTIL, AFTER_PERCENT
        view = {"freeWeddings": FREE_WEDDINGS, "firstPaid": FIRST_PAID, "doubleUntil": DOUBLE_UNTIL, "afterPercent": AFTER_PERCENT}
    n = max(0, int(done))
    if n < int(view["freeWeddings"]):
        return 0
    price, cap, percent = int(view["firstPaid"]), int(view["doubleUntil"]), int(view["afterPercent"])
    for _ in range(n - int(view["freeWeddings"])):
        if price >= cap:
            price = int(round(price * (100 + percent) / 100))
        else:
            doubled = price * 2
            price = cap if doubled >= cap else doubled
    return price
def price_ladder(settings=None, count=12):
    return [wedding_price(i, settings) for i in range(count)]
def _flag(src, key, default):
    value = src.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value).lower() not in ("0", "false", "no", "off")
def _item_text(value, default, limit):
    text = " ".join(str("" if value is None else value).replace("<", " ").replace(">", " ").split())
    return (text or default)[:limit]
def _span(src, key, default, lo, hi):
    raw = src.get(key, default) if isinstance(src, dict) else default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(default)
    return max(lo, min(hi, value))
def _care_label(effect):
    for eid, _label, care in _EFFECTS:
        if eid == effect:
            return care
    return ""
def _gift_shelf(src):
    from marriage_engine.m_join import GIFTS
    src = src if isinstance(src, dict) else {}
    saved = {}
    raw = src.get("shelf")
    if isinstance(raw, list):
        for row in raw:
            if isinstance(row, dict) and row.get("id"):
                saved[str(row["id"])] = row
    out = []
    seen = set()
    for item in GIFTS:
        effect = str(item.get("effect") or "self")
        price = _clamp(src.get(item["id"] + "Price", item["price"]), item["price"], 0, 100000)
        care = _clamp(src.get(item["id"] + "Care", item.get("care") or 0), item.get("care") or 0, 0, 100)
        over = saved.get(item["id"]) if isinstance(saved.get(item["id"]), dict) else {}
        if str(over.get("effect") or "") in _KNOWN:
            effect = str(over["effect"])
        if "price" in over:
            price = _clamp(over.get("price"), price, 0, 100000)
        if "care" in over:
            care = _clamp(over.get("care"), care, 0, 100)
        if effect == "hour":
            care = max(1, care)
        elif effect not in _AMOUNT:
            care = 0
        row = {
            "id": item["id"], "name": _item_text(over.get("name"), item["name"], 40), "name1": item["name1"],
            "emoji": _item_text(over.get("emoji"), item["emoji"], 8) or item["emoji"],
            "buy": _item_text(over.get("buy"), item.get("buy") or "Купить", 24),
            "use": _item_text(over.get("use"), item.get("use") or "Использовать", 24),
            "line": _item_text(over.get("line"), item.get("line") or "", 140),
            "touch": _item_text(over.get("line"), item.get("touch") or "", 140) if "line" in over and str(over.get("line") or "").strip() else (item.get("touch") or ""), "effect": effect,
            "price": price, "care": care, "careLabel": _care_label(effect),
            "on": _flag(over, "on", item.get("on", True) is not False) if "on" in over else item.get("on", True) is not False, "custom": False,
        }
        if effect == "seed":
            row["growMin"] = _span(over or item, "growMin", item.get("growMin") or 30, 1, 1440)
            row["waters"] = _span(over or item, "waters", item.get("waters") if item.get("waters") is not None else 3, 0, 12)
        out.append(row)
        seen.add(item["id"])
    for key, over in saved.items():
        if key in seen or not isinstance(over, dict) or not over.get("custom"):
            continue
        effect = str(over.get("effect") or "")
        if effect not in _KNOWN:
            continue
        name = _item_text(over.get("name"), "", 40)
        emoji = _item_text(over.get("emoji"), "", 8) or "🫧"
        ident = "".join(ch for ch in key.lower() if ch.isalnum())[:16]
        if not name or not emoji or len(ident) < 4:
            continue
        care = _clamp(over.get("care"), 0, 0, 100)
        if effect == "hour":
            care = max(1, care)
        elif effect not in _AMOUNT:
            care = 0
        code = _item_text(over.get("name1"), "", 24).lower()
        if not code.startswith("mrg") or not code[3:].isalnum():
            code = "mrg" + ident
        custom = {
            "id": ident, "name": name, "name1": code, "emoji": emoji,
            "buy": _item_text(over.get("buy"), "Купить", 24),
            "use": _item_text(over.get("use"), "Использовать", 24),
            "line": _item_text(over.get("line"), "", 140),
            "touch": _item_text(over.get("line"), "", 140), "effect": effect,
            "price": _clamp(over.get("price"), 0, 0, 100000), "care": care, "careLabel": _care_label(effect),
            "on": _flag(over, "on", True) if "on" in over else True, "custom": True,
        }
        if effect == "seed":
            custom["growMin"] = _span(over, "growMin", 30, 1, 1440)
            custom["waters"] = _span(over, "waters", 3, 0, 12)
        out.append(custom)
    return out
def settings_view(src):
    from marriage_engine.m_ids import FREE_WEDDINGS, FIRST_PAID, DOUBLE_UNTIL, AFTER_PERCENT, PROPOSAL_MINUTES, RP_PER_VERB_A_DAY, TOP_LIMIT, RESCUE_HOURS, SHOW_EMPTY_PROFILE
    from marriage_engine.m_join import RP
    from marriage_engine.m_prize import periods_view, prizes_view, quiet_row
    src = src if isinstance(src, dict) else {}
    shelf = _gift_shelf(src)
    by = {row["id"]: row for row in shelf}
    known = {row["id"] for row in RP}
    verbs = {}
    if isinstance(src.get("verbs"), dict):
        for key, value in src["verbs"].items():
            if key in known:
                verbs[key] = _clamp(value, 0, 0, 100000)
    levels = normalize_levels(src.get("levels")) if src.get("levels") else normalize_levels(None)
    got_sparks = src.get("sparks") if isinstance(src.get("sparks"), dict) else {}
    got_waits = src.get("waits") if isinstance(src.get("waits"), dict) else {}
    return {
        "enabled": _flag(src, "enabled", True), "freeWeddings": _clamp(src.get("freeWeddings", FREE_WEDDINGS), FREE_WEDDINGS, 0, 100),
        "firstPaid": _clamp(src.get("firstPaid", FIRST_PAID), FIRST_PAID, 0, 100000), "doubleUntil": _clamp(src.get("doubleUntil", DOUBLE_UNTIL), DOUBLE_UNTIL, 0, 100000),
        "afterPercent": _clamp(src.get("afterPercent", AFTER_PERCENT), AFTER_PERCENT, 0, 100), "proposalMinutes": _clamp(src.get("proposalMinutes", PROPOSAL_MINUTES), PROPOSAL_MINUTES, 1, 1440),
        "rpPerDay": _clamp(src.get("rpPerDay", RP_PER_VERB_A_DAY), RP_PER_VERB_A_DAY, 1, 20), "topLimit": _clamp(src.get("topLimit", TOP_LIMIT), TOP_LIMIT, 1, 50),
        "showEmptyProfile": _flag(src, "showEmptyProfile", SHOW_EMPTY_PROFILE), "toneOn": _flag(src, "toneOn", True), "sparkOn": _flag(src, "sparkOn", True),
        "toneStart": _clamp(src.get("toneStart", 80), 80, 0, 100), "toneGain": _clamp(src.get("toneGain", 12), 12, 0, 100), "toneDecay": _clamp(src.get("toneDecay", 8), 8, 0, 100),
        "rescueHours": _clamp(src.get("rescueHours", RESCUE_HOURS), RESCUE_HOURS, 1, 48),
        "moonFrom": _clamp(src.get("moonFrom", 21), 21, 0, 23), "moonTo": _clamp(src.get("moonTo", 6), 6, 0, 23),
        "dawnFrom": _clamp(src.get("dawnFrom", 6), 6, 0, 23), "dawnTo": _clamp(src.get("dawnTo", 10), 10, 0, 23),
        "levels": levels, "verbs": verbs,
        "sparks": {
            row["id"]: _clamp(got_sparks.get(row["id"], row.get("care") or 0), int(row.get("care") or 0), 0, 100)
            for row in RP
        },
        "waits": {
            row["id"]: _clamp(got_waits.get(row["id"], row.get("wait") or 0), int(row.get("wait") or 0), 0, 10080)
            for row in RP
        },
        "glowPrice": by["glow"]["price"], "glowCare": by["glow"]["care"],
        "candlePrice": by["candle"]["price"], "candleCare": by["candle"]["care"],
        "hearthPrice": by["hearth"]["price"], "hearthCare": by["hearth"]["care"],
        "matchPrice": by["match"]["price"], "ribbonPrice": by["ribbon"]["price"],
        "shelf": shelf,
        "effects": [{"id": eid, "label": label, "care": care} for eid, label, care in _EFFECTS],
        "replyCare": _clamp(src.get("replyCare", 1), 1, 0, 20),
        "replyWarm": _clamp(src.get("replyWarm", 3), 3, 0, 20),
        "replyWarmWords": _clamp(src.get("replyWarmWords", 4), 4, 1, 30),
        "replyAlmost": _clamp(src.get("replyAlmost", 2), 2, 1, 20),
        "replyDone": _plain(src.get("replyDone"), ""),
        "replyAlmostText": _plain(src.get("replyAlmostText"), "Поддержал отношения с {name}"),
        "giftFundChat": _fund(src.get("giftFundChat"), -1004440027555),
        "premiumKeeper": _keeper(src.get("premiumKeeper"), "JerichoCute"),
        "fundPercent": _clamp(src.get("fundPercent", 20), 20, 0, 80),
        "projectKeepPercent": _clamp(src.get("projectKeepPercent", 10), 10, 0, 80),
        "quietOn": _flag(src, "quietOn", True),
        "quietPrice": _clamp(src.get("quietPrice", 40), 40, 0, 100000),
        "quietEmoji": quiet_row({"quietEmoji": src.get("quietEmoji"), "quietOn": True}, force=True)["emoji"],
        "envelopeKut": _clamp(src.get("envelopeKut", 15), 15, 0, 100000),
        "extraKut": _clamp(src.get("extraKut", 0), 0, 0, 100000),
        "periods": periods_view(src.get("periods")),
        "prizes": prizes_view(src.get("prizes")),
    }
def _day(value):
    if isinstance(value, datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return moment.astimezone(MSK).date()
    if isinstance(value, date):
        return value
    return None
def tone_score(points, tone_day, today, decay, since=None):
    try:
        score = int(80 if points is None else points)
    except (TypeError, ValueError):
        score = 80
    score = max(0, min(100, score))
    today_d, anchor = _day(today) or today, _day(tone_day) or _day(since)
    if anchor is None or not isinstance(today_d, date):
        return score
    late = (today_d - anchor).days
    return score if late <= 0 else max(0, score - int(decay or 0) * late)
def tone_after(points, tone_day, today, decay, gain, since=None):
    today_d = _day(today) or today
    score = tone_score(points, tone_day, today, decay, since)
    if _day(tone_day) == today_d:
        return score, today_d
    return min(100, score + int(gain or 0)), today_d
def tone_label(score):
    score = int(score)
    if score >= 80:
        return "в тонусе"
    if score >= 60:
        return "спокойно"
    if score >= 20:
        return "тихо"
    return "остывает"
def tone_brief(points, tone_day, today, decay, gain):
    score = tone_score(points, tone_day, today, decay)
    fresh = _day(tone_day) != (_day(today) or today)
    nxt = min(100, score + int(gain or 0)) if fresh else score
    hint = ("Жест сегодня поднимет тонус до " + str(nxt) + ".") if fresh else ("Сегодня тонус уже " + str(score) + ".")
    return {"score": score, "next": nxt, "fresh": fresh, "hint": hint}
def _catalog_row(item):
    return {"id": item["id"], "name": item.get("name") or "", "name1": item.get("name1") or "", "emoji": item.get("emoji") or "", "buy": item.get("buy") or "", "use": item.get("use") or "", "line": item.get("line") or "", "touch": item.get("touch") or "", "effect": item.get("effect") or "self", "price": int(item.get("price") or 0), "care": int(item.get("care") or 0), "on": item.get("on") is not False}
def gift_catalog(settings=None):
    from marriage_engine.m_join import GIFTS
    if isinstance(settings, dict) and isinstance(settings.get("shelf"), list) and settings["shelf"]:
        rows = [_catalog_row(item) for item in settings["shelf"] if isinstance(item, dict) and item.get("id")]
        if rows:
            return rows
    view = settings if isinstance(settings, dict) and "candlePrice" in settings else settings_view(settings)
    if isinstance(view, dict) and isinstance(view.get("shelf"), list) and view.get("shelf"):
        return gift_catalog(view)
    rows = []
    for item in GIFTS:
        effect = str(item.get("effect") or "self")
        price = int(view.get(item["id"] + "Price", item["price"]))
        care = int(view.get(item["id"] + "Care", item.get("care") or 0)) if effect in _AMOUNT else 0
        rows.append(_catalog_row({**item, "effect": effect, "price": price, "care": care}))
    return rows
def gift_plan(kind, fading, you, need, ribbon=False, care=0):
    try:
        plus = int(care)
    except (TypeError, ValueError):
        plus = 0
    if kind in ("glow", "candle", "hearth"):
        return {"ok": True, "reason": "", "care": plus}
    if kind == "match":
        if not fading:
            return {"ok": False, "reason": "calm", "care": 0}
        gap = int(need) - int(you)
        if gap <= 0:
            return {"ok": False, "reason": "full", "care": 0}
        return {"ok": True, "reason": "", "care": gap}
    if kind == "ribbon":
        if ribbon:
            return {"ok": False, "reason": "worn", "care": 0}
        return {"ok": True, "reason": "", "care": 0}
    return {"ok": False, "reason": "bad", "care": 0}
def blocks_new_person(state):
    return str(state) in {"ask", "billing", "live"}
def _norm(text):
    raw = str(text or "").lower().replace("ё", "е")
    return " ".join("".join(ch if (ch.isalpha() or ch.isspace() or ch in "+-") else " " for ch in raw).split())
def _ribbon_off(norm):
    from marriage_engine.m_w1 import RIBBON_OFF
    if norm in RIBBON_OFF:
        return True
    polite = {"пожалуйста", "пж", "плиз"}
    for phrase in sorted(RIBBON_OFF, key=len, reverse=True):
        if norm.startswith(phrase + " "):
            rest = norm[len(phrase) + 1:]
            if rest in polite:
                return True
    return False
def classify(text):
    from marriage_engine.m_join import WED_WORDS, CARD_WORDS, LEAVE_WORDS, TOP_WORDS, ON_WORDS, OFF_WORDS, LIST_WORDS, TONE_WORDS, RP
    norm = _norm(text)
    pairs = (("on", ON_WORDS), ("off", OFF_WORDS), ("top", TOP_WORDS), ("leave", LEAVE_WORDS), ("card", CARD_WORDS), ("tone", TONE_WORDS), ("list", LIST_WORDS), ("wed", WED_WORDS))
    for kind, words in pairs:
        if norm in words:
            return {"kind": kind, "tail": ""}
    if _ribbon_off(norm):
        return {"kind": "ribbon_off", "tail": ""}
    found = []
    for item in RP:
        for verb in item["verbs"]:
            found.append((len(_norm(verb)), verb, item))
    found.sort(reverse=True)
    for _n, verb, item in found:
        v = _norm(verb)
        if norm == v:
            return {"kind": "rp", "rp": item, "verb": verb, "note": ""}
        if norm.startswith(v + " "):
            return {"kind": "rp", "rp": item, "verb": verb, "note": norm[len(v) + 1:].strip()}
    return None
def shares_general_rp(item, verb):
    from marriage_engine.m_join import SHARED_WITH_GENERAL_RP
    return _norm(verb) in {_norm(word) for word in SHARED_WITH_GENERAL_RP}
def quiet_wish(verb):
    from marriage_engine.m_join import QUIET_UNLESS_PAIR
    return _norm(verb) in QUIET_UNLESS_PAIR
def _ru(n, one, few, many):
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= (n % 10) <= 4 and not (12 <= (n % 100) <= 14):
        return few
    return many
def together_label(since, now):
    if not isinstance(since, datetime) or not isinstance(now, datetime):
        return "сегодня"
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    seconds = int((now - since).total_seconds())
    if seconds < 1:
        return "сегодня"
    if seconds < 60:
        return str(seconds) + " " + _ru(seconds, "секунду", "секунды", "секунд")
    if seconds < 3600:
        minutes = seconds // 60
        return str(minutes) + " " + _ru(minutes, "минуту", "минуты", "минут")
    if seconds < 86400:
        hours = seconds // 3600
        return str(hours) + " " + _ru(hours, "час", "часа", "часов")
    days = seconds // 86400
    if days < 7:
        return str(days) + " " + _ru(days, "день", "дня", "дней")
    if 170 <= days <= 200:
        return "полгода"
    if 330 <= days <= 400:
        return "год"
    if 500 <= days <= 600:
        return "полтора года"
    if days < 30:
        weeks = days // 7
        return str(weeks) + " " + _ru(weeks, "неделю", "недели", "недель")
    months = days // 30
    if months == 6:
        return "полгода"
    if months == 12:
        return "год"
    if months == 18:
        return "полтора года"
    if months >= 24:
        years = months // 12
        return str(years) + " " + _ru(years, "год", "года", "лет")
    return str(months) + " " + _ru(months, "месяц", "месяца", "месяцев")
def _talks_ok(state, day, today):
    if "talk_payer" not in state and "talk_partner" not in state:
        return True
    payer, partner = _day(state.get("talk_payer")), _day(state.get("talk_partner"))
    if payer is None or partner is None:
        return False
    return (payer == day and partner == day) or (payer == today and partner == today)
def _spark_copy(raw):
    src = raw or {}
    state = {"spark_days": int(src.get("spark_days") or 0), "spark_best": int(src.get("spark_best") or 0), "care_total": int(src.get("care_total") or 0), "care_payer": int(src.get("care_payer") or 0), "care_partner": int(src.get("care_partner") or 0), "spark_day": _day(src.get("spark_day")), "fade_until": src.get("fade_until"), "spark_lost": int(src.get("spark_lost") or 0), "shield": int(src.get("shield") or 0), "fade_extra": int(src.get("fade_extra") or 0)}
    if "talk_payer" in src or "talk_partner" in src:
        state["talk_payer"], state["talk_partner"] = src.get("talk_payer"), src.get("talk_partner")
    return state
def _spark_pack(state, settings, fading, lost, clock, saved):
    level = level_of(state["spark_days"], settings)
    need = each_share(level["goal"])
    rows = (settings or {}).get("levels") if isinstance(settings, dict) and (settings or {}).get("levels") else None
    if not rows:
        from marriage_engine.m_join import LEVELS
        rows = list(LEVELS)
    nxt = None
    for row in rows:
        if int(row["days"]) > int(state["spark_days"]):
            nxt = row
            break
    holidays = (settings or {}).get("periods") if isinstance(settings, dict) else None
    if not holidays:
        from marriage_engine.marriage_design import PERIODS
        holidays = list(PERIODS)
    return {"state": state, "level": level, "need": need, "goal": int(level["goal"]), "fading": fading, "saved": saved, "both_done": state["care_payer"] >= need and state["care_partner"] >= need and not fading, "lost": lost, "clock": clock, "table": rows, "next": nxt, "days_left": max(0, int(nxt["days"]) - int(state["spark_days"])) if nxt else 0, "holidays": list(holidays)}
def _spend(state, need):
    state["care_payer"] = max(0, state["care_payer"] - need)
    state["care_partner"] = max(0, state["care_partner"] - need)
def _deadline(day, rescue_hours, extra):
    hours = max(1, int(rescue_hours or 12)) + max(0, int(extra or 0))
    return datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=MSK) + timedelta(hours=hours)
def _day_paid(state, need, day, today, moment, deadline):
    you, other = int(state.get("care_payer") or 0), int(state.get("care_partner") or 0)
    if you < need or other < need:
        return False
    if _talks_ok(state, day, today):
        return True
    if you > need and other > need:
        return True
    return moment > deadline
def _walk(state, moment, rescue_hours, settings):
    moment = moment if getattr(moment, "tzinfo", None) else moment.replace(tzinfo=MSK)
    moment = moment.astimezone(MSK)
    today = moment.date()
    lost, fading, clock, saved = 0, False, "", False
    for _ in range(500):
        day = state.get("spark_day")
        if day is None or day >= today:
            state["fade_until"] = None
            break
        need = each_share(level_of(state.get("spark_days"), settings)["goal"])
        deadline = _deadline(day, rescue_hours, state.get("fade_extra"))
        if _day_paid(state, need, day, today, moment, deadline):
            _spend(state, need)
            state["spark_days"] = int(state.get("spark_days") or 0) + 1
            state["spark_best"] = max(int(state.get("spark_best") or 0), state["spark_days"])
            state["spark_day"] = day + timedelta(days=1)
            state["fade_until"] = None
            state["fade_extra"] = 0
            saved = True
            continue
        if moment <= deadline:
            fading, clock, state["fade_until"] = True, deadline.strftime("%H:%M"), deadline
            return fading, lost, clock, saved
        if int(state.get("shield") or 0) > 0:
            state["shield"] = int(state["shield"]) - 1
            state["spark_day"] = day + timedelta(days=1)
            state["fade_until"], state["fade_extra"] = None, 0
            continue
        lost = int(state.get("spark_days") or 0)
        state["spark_lost"] = lost if lost > 0 else int(state.get("spark_lost") or 0)
        state["spark_days"], state["spark_day"] = 0, today
        state["care_payer"], state["care_partner"], state["fade_until"] = 0, 0, None
        state["fade_extra"] = 0
        break
    return fading, lost, clock, saved
def settle_spark(raw, now, rescue_hours=12, settings=None):
    moment = now if getattr(now, "tzinfo", None) else now.replace(tzinfo=MSK)
    moment = moment.astimezone(MSK)
    today, state = moment.date(), _spark_copy(raw)
    if isinstance(settings, dict) and "levels" not in settings and "freeWeddings" not in settings:
        settings = settings_view(settings)
    if state["spark_day"] is None:
        state["spark_day"], state["care_payer"], state["care_partner"], state["fade_until"] = today, 0, 0, None
        return _spark_pack(state, settings, False, 0, "", False)
    fading, lost, clock, _saved = _walk(state, moment, rescue_hours, settings)
    return _spark_pack(state, settings, fading, lost, clock, False)
def add_spark_care(raw, side, amount, now, rescue_hours=12, settings=None):
    view = settle_spark(raw, now, rescue_hours, settings)
    state, moment = view["state"], now if getattr(now, "tzinfo", None) else now.replace(tzinfo=MSK)
    moment = moment.astimezone(MSK)
    key = "care_payer" if side == "payer" else "care_partner"
    state[key] = int(state[key]) + max(0, int(amount or 0))
    state["care_total"] = int(state.get("care_total") or 0) + max(0, int(amount or 0))
    fading, lost, clock, saved = _walk(state, moment, rescue_hours, settings)
    packed = _spark_pack(state, settings, fading, lost or view["lost"], clock or ("" if saved else view["clock"]), saved)
    return packed
def nudge_spark(state, now, rescue_hours=12, settings=None):
    moment = now if getattr(now, "tzinfo", None) else now.replace(tzinfo=MSK)
    fading, _lost, clock, saved = _walk(state, moment, rescue_hours, settings)
    return _spark_pack(state, settings, fading, 0, clock, saved)
def seal_today(state, today, need):
    need = int(need or 0)
    state["care_payer"] = max(0, int(state.get("care_payer") or 0) - need)
    state["care_partner"] = max(0, int(state.get("care_partner") or 0) - need)
    state["spark_days"] = int(state.get("spark_days") or 0) + 1
    state["spark_best"] = max(int(state.get("spark_best") or 0), state["spark_days"])
    state["spark_day"] = today + timedelta(days=1)
    state["fade_until"] = None
    state["fade_extra"] = 0
    return state
def profile_line(view, now=None):
    from marriage_engine.look import HEART, PROFILE_EMPTY, PROFILE_WITH, PROFILE_TONE
    now = now or datetime.now(MSK)
    name = (view or {}).get("name_html") or ""
    if not name:
        return PROFILE_EMPTY.format(heart=HEART)
    mark = "🎀" if (view or {}).get("ribbon") else HEART
    line = PROFILE_WITH.format(mark=mark, name=name, span=together_label((view or {}).get("since"), now))
    tone = (view or {}).get("tone_label") or ""
    return line + (PROFILE_TONE.format(tone=tone) if tone else "")
def tone_text(score, label, hint=""):
    from marriage_engine.look import SPARK, TONE_LINE
    tail = (" " + hint) if hint else ""
    return TONE_LINE.format(spark=SPARK, score=int(score), label=label, tail=tail)
def pay_label(amount):
    from marriage_engine.look import PAY
    return PAY["text"].format(amount=amount)
def verb_button(verb_id, price=0, care=0):
    from marriage_engine.m_join import VERB_LABEL
    from marriage_engine.look import VERB_PRICE
    found = rp_by_id(verb_id) or {}
    label = VERB_LABEL.get(str(verb_id)) or found.get("title") or str(verb_id)
    return VERB_PRICE.format(label=label, price=int(price)) if int(price or 0) > 0 else label
def _pair(you, need, partner, other):
    from marriage_engine.look import PAIR_LINE
    return PAIR_LINE.format(you=int(you), need=int(need), partner=partner, other=int(other))
def _spare(you, other, need, partner):
    yours, theirs = max(0, int(you) - int(need)), max(0, int(other) - int(need))
    if yours <= 0 and theirs <= 0:
        return ""
    from marriage_engine.look import SPARE_LINE, SPARE_DAYS
    if yours > 0 and theirs > 0:
        line = SPARE_LINE.format(yours=yours, partner=partner, theirs=theirs)
    elif yours > 0:
        line = "Запас: ты " + str(yours)
    else:
        line = "Запас: " + str(partner) + " " + str(theirs)
    share = int(need or 0)
    if share > 0 and yours > 0 and theirs > 0:
        ahead = min(yours, theirs) // share
        if ahead > 0:
            line += SPARE_DAYS.format(ahead=ahead)
    return line
def _feel(level):
    text = str((level or {}).get("life") or "")
    if not text:
        from marriage_engine.m_join import LEVELS
        try:
            number = int((level or {}).get("id") or 0)
        except (TypeError, ValueError):
            number = 0
        for row in LEVELS:
            if int(row.get("id") or 0) == number:
                text = str(row.get("life") or "")
                break
    text = " ".join(text.replace("<", " ").replace(">", " ").split())
    return "<i>" + text + "</i>" if text else ""
def _was(lost):
    from marriage_engine.look import WAS_LINE, SPAN_DAY
    n = int(lost or 0)
    return WAS_LINE.format(n=n, word=_ru(n, *SPAN_DAY))
def card_text(a, b, span, date="", tone=""):
    from marriage_engine.look import HEART, CARD_HEAD, CARD_TOGETHER, CARD_DATE, CARD_TONE
    lines = [CARD_HEAD.format(heart=HEART, a=a, b=b), CARD_TOGETHER.format(span=span)]
    if date:
        lines.append(CARD_DATE.format(date=date))
    if tone:
        lines.append(CARD_TONE.format(tone=tone))
    return "\n".join(lines)
def flame_strip(state, today=None, both_done=False, fading=False, clock=""):
    """Семь дней, как огонёк: 🔥 — день закрыт, ◌ — сегодня ещё можно, · — пусто."""
    from marriage_engine.look import (
        CLOCK_WORD, FLAME_COUNT, FLAME_FIRST, FLAME_LIT, FLAME_MARK, FLAME_NAMES, FLAME_OFF,
        FLAME_OPEN, FLAME_RISK, FLAME_TODAY, FLAME_ZERO,
    )
    today = _day(today) or datetime.now(MSK).date()
    state = state or {}
    closed = max(0, int(state.get("spark_days") or 0))
    anchor = _day(state.get("spark_day"))
    lit = set()
    if closed > 0 and anchor is not None:
        for shift in range(closed):
            lit.add(anchor - timedelta(days=shift))
    if both_done:
        lit.add(today)
    names, marks = [], []
    for shift in range(6, -1, -1):
        day = today - timedelta(days=shift)
        names.append(FLAME_NAMES[day.weekday()])
        if day in lit:
            marks.append(FLAME_MARK)
        elif day == today:
            marks.append(FLAME_TODAY)
        else:
            marks.append(FLAME_OFF)
    if fading and not both_done:
        note = (FLAME_FIRST if closed <= 0 else FLAME_RISK).format(clock=clock or CLOCK_WORD)
    elif closed <= 0 and not both_done:
        note = FLAME_ZERO
    elif today in lit:
        note = FLAME_LIT
    else:
        note = FLAME_OPEN
    return FLAME_COUNT.format(days=closed) + "\n" + " ".join(names) + "\n" + " ".join(marks) + "\n" + note
def care_meter(have, need):
    from marriage_engine.look import BAR_OFF, BAR_ON, METER_EXTRA, METER_LEFT, METER_READY
    have, need = max(0, int(have or 0)), max(1, int(need or 1))
    cells = min(need, 8)
    filled = cells if have >= need else min(cells, int(round(have * cells / need)))
    bar = (BAR_ON * filled) + (BAR_OFF * (cells - filled))
    extra = have - need
    if extra > 0:
        tail = METER_EXTRA.format(extra=extra)
    elif have >= need:
        tail = METER_READY
    else:
        tail = METER_LEFT.format(left=need - have)
    return bar + " " + tail
def _meters(you, need, partner, other):
    from marriage_engine.look import METER_LINE
    return [
        METER_LINE.format(who="Вы", bar=care_meter(you, need)),
        METER_LINE.format(who=partner, bar=care_meter(other, need)),
    ]
def _step(view, you, other, need):
    from marriage_engine.look import (
        CLOCK_WORD, STEP_FIRST_BOTH, STEP_FIRST_THEM, STEP_FIRST_WAIT, STEP_FIRST_YOU,
        STEP_OPEN_BOTH, STEP_OPEN_THEM, STEP_OPEN_WAIT, STEP_OPEN_YOU, STEP_THEM, STEP_YOU,
    )
    you_left, them_left = max(0, int(need) - int(you or 0)), max(0, int(need) - int(other or 0))
    clock = view.get("clock") or CLOCK_WORD
    days = int((view.get("state") or {}).get("spark_days") or 0)
    if view.get("both_done"):
        return ""
    if view.get("fading") and days <= 0:
        if you_left and them_left:
            return STEP_FIRST_BOTH.format(clock=clock, you=you_left, them=them_left)
        if you_left:
            return STEP_FIRST_YOU.format(clock=clock, left=you_left)
        if them_left:
            return STEP_FIRST_THEM.format(clock=clock, left=them_left)
        return STEP_FIRST_WAIT.format(clock=clock)
    if view.get("fading"):
        if you_left and them_left:
            return STEP_OPEN_BOTH.format(clock=clock, you=you_left, them=them_left)
        if you_left:
            return STEP_OPEN_YOU.format(clock=clock, left=you_left)
        if them_left:
            return STEP_OPEN_THEM.format(clock=clock, left=them_left)
        return STEP_OPEN_WAIT.format(clock=clock)
    if you_left:
        return STEP_YOU.format(left=you_left)
    if them_left:
        return STEP_THEM.format(left=them_left)
    return ""
def _next_gift(view):
    from marriage_engine.look import HOLIDAY_GIFT, NEXT_GIFT
    days = int((view.get("state") or {}).get("spark_days") or 0)
    for row in view.get("holidays") or []:
        try:
            day = int(row.get("day") or 0)
        except (TypeError, ValueError):
            continue
        if day > days:
            return NEXT_GIFT.format(
                day=day,
                name=str(row.get("name") or ""),
                gift=HOLIDAY_GIFT.get(day, "Один дар на выбор."),
            )
    return ""
def spark_home(a, b, span, date, view, you, partner_care, partner_name):
    from marriage_engine.look import (
        HEART, LEVEL_EMPTY, SPARK_COAT, WAS_SHORT, SPAN_DAY, CARD_HEAD, CARD_TOGETHER, LIMIT_HEAD,
    )
    view = view or {}
    need = int(view.get("need") or 0)
    goal = int(view.get("goal") or 0)
    lines = [
        CARD_HEAD.format(heart=HEART, a=a, b=b),
        CARD_TOGETHER.format(span=span),
        "<b>" + str((view.get("level") or {}).get("name") or LEVEL_EMPTY) + "</b>",
        flame_strip(
            view.get("state"),
            both_done=bool(view.get("both_done")),
            fading=bool(view.get("fading")),
            clock=view.get("clock") or "",
        ),
        LIMIT_HEAD.format(goal=goal, need=need),
    ]
    lines.extend(_meters(you, need, partner_name, partner_care))
    step = _step(view, you, partner_care, need)
    if step:
        lines.append(step)
    spare = _spare(you, partner_care, need, partner_name)
    if spare:
        lines.append("<i>" + spare + "</i>")
    gift = _next_gift(view)
    if gift:
        lines.append(gift)
    lost = int(view.get("lost") or 0)
    if lost > 0:
        lines.append(WAS_SHORT.format(n=lost, word=_ru(lost, *SPAN_DAY)))
    if int((view.get("state") or {}).get("shield") or 0) > 0:
        lines.append(SPARK_COAT)
    return "\n".join(line for line in lines if line)
def spark_level(view):
    from marriage_engine.look import LEVEL_LEAD, LEVEL_NEXT, LEVEL_NOW, LEVEL_ROW, LEVELS_TITLE, SPARK
    from marriage_engine.m_join import LEVELS
    rows = view.get("table") if isinstance(view.get("table"), list) and view.get("table") else LEVELS
    current = int((view.get("level") or {}).get("id") or 1)
    lines = [LEVELS_TITLE.format(spark=SPARK), LEVEL_LEAD]
    for row in rows:
        mark = LEVEL_NOW if int(row["id"]) == current else ""
        goal = int(row["goal"])
        lines.append(LEVEL_ROW.format(
            name=row["name"],
            days=row["days"],
            goal=goal,
            share=each_share(goal),
            mark=mark,
        ))
    nxt = view.get("next")
    if isinstance(nxt, dict) and nxt.get("name"):
        goal = int(nxt.get("goal") or 0)
        lines.append(LEVEL_NEXT.format(
            name=nxt["name"],
            days=int(view.get("days_left") or 0),
            goal=goal,
            share=each_share(goal),
        ))
    from marriage_engine.look import HOLIDAY_GIFT, HOLIDAY_HEAD, HOLIDAY_LINE, HOLIDAY_NOTE, HOLIDAY_SOON
    days = int((view.get("state") or {}).get("spark_days") or 0)
    soon = None
    for row in view.get("holidays") or []:
        try:
            day = int(row.get("day") or 0)
        except (TypeError, ValueError):
            continue
        if day > days and soon is None:
            soon = day
    if view.get("holidays"):
        lines.append(HOLIDAY_HEAD)
        lines.append(HOLIDAY_NOTE)
        for row in view.get("holidays"):
            try:
                day = int(row.get("day") or 0)
            except (TypeError, ValueError):
                continue
            lines.append(HOLIDAY_LINE.format(
                day=day,
                name=str(row.get("name") or ""),
                gift=HOLIDAY_GIFT.get(day, "Один дар на выбор."),
                mark=HOLIDAY_SOON if day == soon else "",
            ))
    return "\n".join(lines)
def spark_fire(view, you, partner_care, partner_name, hours):
    from marriage_engine.look import (
        CLOCK_WORD, FIRE_DONE, FIRE_DO, FIRE_FADE, FIRE_HEAD, FIRE_SPLIT, FIRE_WAIT,
        FIRE_YESTERDAY, LEVEL_EMPTY, SPARK,
    )
    need = int(view.get("need") or 0)
    goal = int(view.get("goal") or 0)
    name = str((view.get("level") or {}).get("name") or LEVEL_EMPTY)
    days = int((view.get("state") or {}).get("spark_days") or 0)
    left = max(0, need - int(you or 0))
    if view.get("fading"):
        head = FIRE_FADE.format(spark=SPARK, days=days)
        sub = FIRE_YESTERDAY.format(clock=view.get("clock") or CLOCK_WORD, need=need)
    else:
        head = FIRE_HEAD.format(spark=SPARK, name=name, days=days)
        if view.get("both_done"):
            sub = FIRE_DONE
        elif left <= 0:
            sub = FIRE_WAIT
        else:
            sub = FIRE_DO.format(left=left)
    lines = [
        head,
        FIRE_SPLIT.format(goal=goal, need=need),
    ]
    lines.extend(_meters(you, need, partner_name, partner_care))
    lines.append(sub)
    spare = _spare(you, partner_care, need, partner_name)
    if spare:
        lines.append("<i>" + spare + "</i>")
    return "\n".join(lines)
def care_line(amount, you, need, partner_care, saved, both, fading):
    from marriage_engine.look import CARE_SAVED, CARE_FADING, CARE_PLUS
    number = int(amount)
    if saved:
        return CARE_SAVED.format(n=number)
    if fading:
        return CARE_FADING.format(n=number)
    return CARE_PLUS.format(n=number)
def bond_line(bond, proposer_id, you_id, partner):
    from marriage_engine.look import HEART, BOND_FAMILY, BOND_YOU, BOND_THEM, BOND_BOUQUET
    if str(bond or "") == "family":
        return BOND_FAMILY.format(heart=HEART)
    try:
        giver = int(proposer_id or 0)
    except (TypeError, ValueError):
        giver = 0
    if str(bond or "") == "propose" and giver == int(you_id):
        return BOND_YOU.format(heart=HEART)
    if str(bond or "") == "propose" and giver:
        return BOND_THEM.format(heart=HEART)
    if str(bond or "") == "bouquet":
        return BOND_BOUQUET.format(heart=HEART)
    return ""
def talk_line(you_spoke, partner_spoke):
    from marriage_engine.look import SPARK, TALK_BOTH, TALK_YOU, TALK_THEM, TALK_NONE
    if you_spoke and partner_spoke:
        return TALK_BOTH.format(spark=SPARK)
    if you_spoke:
        return TALK_YOU.format(spark=SPARK)
    if partner_spoke:
        return TALK_THEM.format(spark=SPARK)
    return TALK_NONE.format(spark=SPARK)
def spark_stats(view, you, partner_care, partner_name):
    from marriage_engine.look import HEART, LEVEL_EMPTY, STATS_LINE
    state, level = view.get("state") or {}, view.get("level") or {}
    return STATS_LINE.format(
        heart=HEART,
        name=str(level.get("name") or LEVEL_EMPTY),
        pair=_pair(you, int(view.get("need") or 0), partner_name, partner_care),
        total=int(state.get("care_total") or 0),
    )
def shop_group(row):
    effect = str((row or {}).get("effect") or "")
    ident = str((row or {}).get("id") or "")
    if ident == "quiet" or effect == "quiet":
        return "quiet"
    if effect in ("seed", "pantry") or ident in ("juice", "soup", "salad"):
        return "meal"
    if effect in ("mark", "propose", "ring") or (row or {}).get("rite"):
        return "mark"
    return "fire"
def gift_text(rows, ribbon=False, cfg=None, shelf=""):
    from marriage_engine.look import (
        DINNER_LINE, GIFT_EMPTY, GIFT_FREE, GIFT_RIBBON, GIFT_ROW, GIFT_STOCK, GIFT_TITLE, HEART,
        SHOP_FIRE, SHOP_MARK, SHOP_MEAL, SHOP_QUIET, item_about, item_name,
    )
    titles = {"fire": SHOP_FIRE, "mark": SHOP_MARK, "meal": SHOP_MEAL, "quiet": SHOP_QUIET}
    lines = [titles.get(shelf, GIFT_TITLE).format(heart=HEART)]
    shown = 0
    seeds = False
    for row in rows or []:
        have = int(row.get("have") or 0)
        if row.get("on") is False and have <= 0:
            continue
        shown += 1
        if str(row.get("effect") or "") == "seed":
            seeds = True
        stock = GIFT_STOCK.format(have=have) if have else ""
        about = item_about(row, rows, cfg)
        if len(about) > 90:
            about = about[:87].rstrip() + "…"
        price = int(row.get("price") or 0)
        piece = GIFT_ROW if price else GIFT_FREE
        lines.append(piece.format(
            emoji=str(row.get("emoji") or ""),
            name=item_name(row),
            about=about,
            stock=stock,
            price=price,
        ))
    if seeds:
        lines.append("<i>" + DINNER_LINE + "</i>")
    if ribbon:
        lines.append(GIFT_RIBBON)
    if shown == 0:
        lines.append(GIFT_EMPTY)
    return "\n".join(lines)
def own_ribbon(live, user_id):
    if not isinstance(live, dict):
        return False
    try:
        uid = int(user_id)
        payer = int(live.get("payer_id") or 0)
    except (TypeError, ValueError):
        return False
    key = "ribbon_payer" if uid == payer else "ribbon_partner"
    return bool(live.get(key))
def ribbon_home(worn):
    from marriage_engine.look import RIBBON_ON, RIBBON_OFF_HOME
    return RIBBON_ON if worn else RIBBON_OFF_HOME
def ribbon_ask():
    from marriage_engine.look import RIBBON_ASK
    return RIBBON_ASK
def ribbon_gone():
    from marriage_engine.look import RIBBON_GONE
    return RIBBON_GONE
def person_html(user_id, first="", username=""):
    label = str(first or (("@" + username) if username else "") or "игрок").replace("<", "").replace(">", "")
    return "<a href='tg://user?id=" + str(int(user_id)) + "'>" + label + "</a>"
def as_aware(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
def wedding_date(value):
    moment = as_aware(value)
    if not isinstance(moment, datetime):
        return ""
    return moment.astimezone(MSK).strftime("%d.%m.%Y %H:%M")
def spark_side(user_id, payer_id):
    return "payer" if int(user_id) == int(payer_id) else "partner"
def spark_split(state, user_id, payer_id):
    if spark_side(user_id, payer_id) == "payer":
        return int(state.get("care_payer") or 0), int(state.get("care_partner") or 0)
    return int(state.get("care_partner") or 0), int(state.get("care_payer") or 0)
def rp_by_id(verb_id):
    from marriage_engine.m_join import RP
    for item in RP:
        if item["id"] == verb_id:
            return item
    return None
def verb_price(item, cfg):
    verbs = (cfg or {}).get("verbs") or {}
    if item and item.get("id") in verbs:
        return int(verbs[item["id"]])
    return int((item or {}).get("price") or 0)
def verb_care(item, cfg=None):
    sparks = (cfg or {}).get("sparks") or {}
    ident = (item or {}).get("id")
    if ident in sparks:
        return int(sparks[ident])
    return int((item or {}).get("care") or 0)
def verb_wait(item, cfg=None):
    """Минуты паузы перед тем же словом. 0 — можно сразу."""
    waits = (cfg or {}).get("waits") or {}
    ident = (item or {}).get("id")
    if ident in waits:
        return int(waits[ident])
    return int((item or {}).get("wait") or 0)
def wait_left_text(seconds):
    left = max(0, int(seconds or 0))
    if left < 60:
        return str(max(1, left)) + " сек"
    minutes = (left + 59) // 60
    if minutes < 60:
        return str(minutes) + " мин"
    hours, mins = divmod(minutes, 60)
    if mins == 0:
        return str(hours) + " ч"
    return str(hours) + " ч " + str(mins) + " мин"
def verb_catalog(settings=None):
    from marriage_engine.m_join import RP, VERB_LABEL
    view = settings if isinstance(settings, dict) and "verbs" in settings else settings_view(settings)
    rows = []
    sparks = view.get("sparks") or {}
    waits = view.get("waits") or {}
    for item in RP:
        row = dict(item)
        if item["id"] in (view.get("verbs") or {}):
            row["price"] = int(view["verbs"][item["id"]])
        row["care"] = int(sparks.get(item["id"], item.get("care") or 0))
        row["wait"] = int(waits.get(item["id"], item.get("wait") or 0))
        row["title"] = VERB_LABEL.get(item["id"]) or item.get("title") or item["verbs"][0]
        row["word"] = item["verbs"][0]
        rows.append(row)
    return rows
def rp_html(item, a, b, note=""):
    from marriage_engine.look import RP_LINE
    extra = " <i>" + note + "</i>" if note else ""
    return RP_LINE.format(emoji=str((item or {}).get("emoji") or ""), a=a, does=str((item or {}).get("does") or ""), b=b, note=extra)
def mention_in(tail):
    text = str(tail or "").strip()
    if not text:
        return ""
    token = text[1:].split()[0] if text.startswith("@") else text.split()[0]
    return token if token.startswith("@") is False else token
def place_hint(name1):
    """Куда вести, если предмет нельзя «использовать» в чате."""
    code = str(name1 or "")
    seeds = {
        "mrgseedcuke": "Саженец огурца",
        "mrgseedtom": "Саженец помидора",
        "mrgseedcab": "Саженец капусты",
    }
    pantry = {
        "mrgcuke": ("🥒", "Огурец"),
        "mrgtom": ("🍅", "Помидор"),
        "mrgcab": ("🥬", "Капуста"),
    }
    from marriage_engine.look import PANTRY_LINE, SEED_LINE, use_card
    if code in seeds:
        return {"where": "farm", "title": seeds[code], "text": use_card("🌱", seeds[code], SEED_LINE)}
    if code in pantry:
        mark, title = pantry[code]
        return {"where": "craft", "title": title, "text": use_card(mark, title, PANTRY_LINE)}
    return None
def is_marriage_code(name1):
    code = str(name1 or "").strip()
    return code == "mrribbon" or (code.startswith("mrg") and code != "mrgquiet")
def face_from_dex(gift, row):
    """Имя, знак, цена и фраза предмета берутся из dex, если строка уже есть."""
    out = dict(gift or {})
    if not isinstance(row, dict):
        return out
    name = " ".join(str(row.get("name") or "").split())
    emoji = " ".join(str(row.get("emoji") or "").split())
    bio = " ".join(str(row.get("bio") or "").replace("<", " ").replace(">", " ").split())
    if name:
        out["name"] = name[:40]
    if emoji:
        out["emoji"] = emoji[:8]
    if bio:
        out["line"] = bio[:140]
        out["from_dex"] = True
    if row.get("price") is not None:
        try:
            out["price"] = max(0, min(100000, int(row["price"])))
        except (TypeError, ValueError):
            pass
    if row.get("remains") is not None:
        try:
            left = int(row["remains"])
        except (TypeError, ValueError):
            left = 0
        out["remains"] = left
        if left <= 0:
            out["on"] = False
    return out
def gift_names():
    from marriage_engine.m_join import GIFTS, RITES
    names = set()
    for item in list(GIFTS) + list(RITES):
        names.add(item["name"])
        names.add(item["name1"])
    return names
def free_left(done, settings=None):
    view = settings if isinstance(settings, dict) and "freeWeddings" in settings else settings_view(settings)
    return max(0, int(view["freeWeddings"]) - int(done or 0))
def _fund(value, default):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if number >= 0 or number < -10**15:
        return default
    return number
def _keeper(value, default):
    raw = str(value or "").strip().lstrip("@")
    text = "".join(ch for ch in raw if ch.isalnum() or ch == "_")
    return (text or default)[:32]
def _plain(value, default):
    text = " ".join(str(value or "").replace("<", " ").replace(">", " ").split())
    return (text or default)[:80]
def reply_care_amount(text, care=1, warm=3, warm_words=4):
    words = len(str(text or "").split())
    if words >= int(warm_words or 4):
        return max(0, int(warm or 0))
    return max(0, int(care or 0))
def reply_spark_line(before, after, need, almost, name, done_text, almost_text):
    if int(before) >= int(need):
        return ""
    left = max(0, int(need) - int(after))
    before_left = max(0, int(need) - int(before))
    hit = left == int(almost) or (before_left > int(almost) and left < int(almost))
    if int(after) >= int(need) and str(done_text or "").strip():
        pattern = done_text
    elif hit:
        pattern = almost_text or "Поддержал отношения с {name}"
    else:
        return ""
    if not str(pattern or "").strip():
        return ""
    return pattern.replace("{name}", str(name or "партнёром")).replace("{left}", str(left))
