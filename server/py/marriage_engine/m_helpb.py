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
    from marriage_engine.look import BTN_YES as Y, BTN_NO as N, HELP_PAY
    from marriage_engine.m_join import LEVELS as L
    s = s if isinstance(s, dict) else {}
    r = s.get("levels") if isinstance(s.get("levels"), list) and s.get("levels") else L
    e = (int(r[0].get("goal") or 10) + 1) // 2
    n = str(int(s.get("freeWeddings", A) or 0)) + " " + str(int(s.get("firstPaid", B) or 0)) + " " + str(int(s.get("doubleUntil", C) or 0))
    return H + "\n<code>Мой брак</code>\n<i>" + HELP_PAY + " " + n + " «" + Y + "» «" + N + "»</i>\n" + K + " искра тонус «" + str(r[0].get("name")) + "» — по " + str(e)
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
    return {
        "enabled": _flag(src, "enabled", True), "freeWeddings": _clamp(src.get("freeWeddings", FREE_WEDDINGS), FREE_WEDDINGS, 0, 100),
        "firstPaid": _clamp(src.get("firstPaid", FIRST_PAID), FIRST_PAID, 0, 100000), "doubleUntil": _clamp(src.get("doubleUntil", DOUBLE_UNTIL), DOUBLE_UNTIL, 0, 100000),
        "afterPercent": _clamp(src.get("afterPercent", AFTER_PERCENT), AFTER_PERCENT, 0, 100), "proposalMinutes": _clamp(src.get("proposalMinutes", PROPOSAL_MINUTES), PROPOSAL_MINUTES, 1, 1440),
        "rpPerDay": _clamp(src.get("rpPerDay", RP_PER_VERB_A_DAY), RP_PER_VERB_A_DAY, 1, 20), "topLimit": _clamp(src.get("topLimit", TOP_LIMIT), TOP_LIMIT, 1, 50),
        "showEmptyProfile": _flag(src, "showEmptyProfile", SHOW_EMPTY_PROFILE), "toneOn": _flag(src, "toneOn", True), "sparkOn": _flag(src, "sparkOn", True),
        "toneStart": _clamp(src.get("toneStart", 80), 80, 0, 100), "toneGain": _clamp(src.get("toneGain", 12), 12, 0, 100), "toneDecay": _clamp(src.get("toneDecay", 8), 8, 0, 100),
        "rescueHours": _clamp(src.get("rescueHours", RESCUE_HOURS), RESCUE_HOURS, 1, 48), "levels": levels, "verbs": verbs,
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
    return {"state": state, "level": level, "need": need, "goal": int(level["goal"]), "fading": fading, "saved": saved, "both_done": state["care_payer"] >= need and state["care_partner"] >= need and not fading, "lost": lost, "clock": clock, "table": rows, "next": nxt, "days_left": max(0, int(nxt["days"]) - int(state["spark_days"])) if nxt else 0}
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
    from marriage_engine.m_ids import HEART
    now = now or datetime.now(MSK)
    name = (view or {}).get("name_html") or ""
    if not name:
        return HEART + " Брака нет. Ответьте «брак» на сообщение человека."
    mark = "🎀" if (view or {}).get("ribbon") else HEART
    line = mark + " В браке с " + name + " · " + together_label((view or {}).get("since"), now)
    tone = (view or {}).get("tone_label") or ""
    return line + (" · " + tone if tone else "")
def tone_text(score, label, hint=""):
    from marriage_engine.m_ids import SPARK
    tail = (" " + hint) if hint else ""
    return SPARK + " <b>Тонус " + str(int(score)) + " · " + str(label) + "</b>" + tail
def pay_label(amount):
    return "Списать " + str(amount) + " кут"
def verb_button(verb_id, price=0, care=0):
    from marriage_engine.m_join import VERB_LABEL
    label = VERB_LABEL.get(str(verb_id), str(verb_id))
    return label + " · " + str(int(price)) if int(price or 0) > 0 else label
def _pair(you, need, partner, other):
    return "Ты " + str(int(you)) + "/" + str(int(need)) + " · " + str(partner) + " " + str(int(other)) + "/" + str(int(need))
def _spare(you, other, need, partner):
    yours, theirs = max(0, int(you) - int(need)), max(0, int(other) - int(need))
    if yours <= 0 and theirs <= 0:
        return ""
    line = "Запас: ты " + str(yours) + " · " + str(partner) + " " + str(theirs)
    share = int(need or 0)
    if share > 0 and yours > 0 and theirs > 0:
        ahead = min(yours, theirs) // share
        if ahead > 0:
            line += " · ещё " + str(ahead) + " дн."
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
    n = int(lost or 0)
    return "<i>Серия была " + str(n) + " " + _ru(n, "день", "дня", "дней") + ". Вы уже не чужие.</i>"
def card_text(a, b, span, date="", tone=""):
    from marriage_engine.m_ids import HEART
    lines = [HEART + " <b>" + a + " и " + b + "</b>", "<b>Вместе " + span + "</b>"]
    if date:
        lines.append("<i>" + date + "</i>")
    if tone:
        lines.append("<i>" + tone + "</i>")
    return "\n".join(lines)
def spark_home(a, b, span, date, view, you, partner_care, partner_name):
    from marriage_engine.m_ids import HEART, SPARK
    level = str((view.get("level") or {}).get("name") or "Знакомство")
    days, need = int((view.get("state") or {}).get("spark_days") or 0), int(view.get("need") or 0)
    lines = [HEART + " <b>" + a + " и " + b + "</b>", "<b>" + span + "</b>"]
    lost = int(view.get("lost") or 0)
    if lost > 0:
        lines += [
            SPARK + " <b>С нуля · " + level + "</b>",
            "<b>" + _pair(you, need, partner_name, partner_care) + "</b>",
            "<i>Было " + str(lost) + " " + _ru(lost, "день", "дня", "дней") + ". Вы уже не чужие.</i>",
        ]
    elif view.get("fading"):
        lines += [
            SPARK + " <b>Гаснет · " + str(days) + "</b>",
            "<i>До " + str(view.get("clock") or "полудня") + " закройте вчера.</i>",
            "<b>" + _pair(you, need, partner_name, partner_care) + "</b>",
        ]
    else:
        lines += [SPARK + " <b>" + str(days) + " · " + level + "</b>", "<b>" + _pair(you, need, partner_name, partner_care) + "</b>"]
        spare = _spare(you, partner_care, need, partner_name)
        if spare:
            lines.append("<i>" + spare + "</i>")
        elif view.get("both_done"):
            lines.append("<i>День закроется в полночь.</i>")
    if int((view.get("state") or {}).get("shield") or 0) > 0:
        lines.append("<i>Пальто: один пропуск.</i>")
    return "\n".join(line for line in lines if line)
def spark_level(view):
    from marriage_engine.m_ids import SPARK
    from marriage_engine.m_join import LEVELS
    rows = view.get("table") if isinstance(view.get("table"), list) and view.get("table") else LEVELS
    current = int((view.get("level") or {}).get("id") or 1)
    lines = [SPARK + " <b>Уровни</b>"]
    for row in rows:
        mark = " · сейчас" if int(row["id"]) == current else ""
        lines.append("<b>" + row["name"] + "</b> <i>" + str(row["days"]) + " дн. · по " + str((int(row["goal"]) + 1) // 2) + mark + "</i>")
    return "\n".join(lines)
def spark_fire(view, you, partner_care, partner_name, hours):
    from marriage_engine.m_ids import SPARK
    need, goal = int(view.get("need") or 0), int(view.get("goal") or 0)
    name = str((view.get("level") or {}).get("name") or "Знакомство")
    days = int((view.get("state") or {}).get("spark_days") or 0)
    if view.get("fading"):
        head = SPARK + " <b>Гаснет · " + str(days) + "</b>"
        sub = "До " + str(view.get("clock") or "полудня") + " по " + str(need) + "."
    else:
        head = SPARK + " <b>" + str(days) + " · " + name + "</b>"
        sub = "По " + str(need) + " с каждого."
    lines = [head, "<b>" + _pair(you, need, partner_name, partner_care) + "</b>", "<i>" + sub + "</i>"]
    spare = _spare(you, partner_care, need, partner_name)
    if spare:
        lines.append("<i>" + spare + "</i>")
    return "\n".join(lines)
def care_line(amount, you, need, partner_care, saved, both, fading):
    if saved:
        return "<i>+" + str(int(amount)) + ". Вчера закрыто.</i>"
    if fading:
        return "<i>+" + str(int(amount)) + ". Искра ещё гаснет.</i>"
    return "<i>+" + str(int(amount)) + ".</i>"
def bond_line(bond, proposer_id, you_id, partner):
    from marriage_engine.m_ids import HEART
    if str(bond or "") == "family":
        return HEART + " <b>Семья</b>"
    try:
        giver = int(proposer_id or 0)
    except (TypeError, ValueError):
        giver = 0
    if str(bond or "") == "propose" and giver == int(you_id):
        return HEART + " <b>Вы сделали предложение</b>"
    if str(bond or "") == "propose" and giver:
        return HEART + " <b>Вам сделали предложение</b>"
    if str(bond or "") == "bouquet":
        return HEART + " <b>Букет</b>"
    return ""
def talk_line(you_spoke, partner_spoke):
    from marriage_engine.m_ids import SPARK
    if you_spoke and partner_spoke:
        return SPARK + " <i>Оба ответили.</i>"
    if you_spoke:
        return SPARK + " <i>Вы ответили. Ждём пару.</i>"
    if partner_spoke:
        return SPARK + " <i>Пара ответила. Ответьте.</i>"
    return SPARK + " <i>Ответьте друг другу.</i>"
def spark_stats(view, you, partner_care, partner_name):
    from marriage_engine.m_ids import HEART
    state, level = view.get("state") or {}, view.get("level") or {}
    return HEART + " <b>" + str(level.get("name") or "Знакомство") + "</b>\n<i>" + _pair(you, int(view.get("need") or 0), partner_name, partner_care) + "</i>\n<i>Всего " + str(int(state.get("care_total") or 0)) + "</i>"
def gift_text(rows, ribbon=False):
    from marriage_engine.m_ids import HEART
    held = []
    for row in rows or []:
        count = int(row.get("have") or 0)
        if count <= 0:
            continue
        held.append(str(row.get("emoji") or "") + str(count))
    bag = " ".join(held) if held else "пусто"
    line = HEART + " <b>Предметы · " + bag + "</b>"
    if ribbon:
        line += "\n<i>Лента на вас.</i>"
    return line
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
    if worn:
        return "🎀 <b>Лента на вас</b>"
    return "🎀 <b>Ленты нет</b>\n<i>Своя, в предметах.</i>"
def ribbon_ask():
    return "🎀 <b>Снять ленту?</b>\n<i>Брак останется.</i>"
def ribbon_gone():
    return "🎀 <b>Лента снята</b>"
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
    return int((item or {}).get("care") or 0)
def verb_catalog(settings=None):
    from marriage_engine.m_join import RP
    view = settings if isinstance(settings, dict) and "verbs" in settings else settings_view(settings)
    rows = []
    for item in RP:
        row = dict(item)
        if item["id"] in (view.get("verbs") or {}):
            row["price"] = int(view["verbs"][item["id"]])
        rows.append(row)
    return rows
def rp_html(item, a, b, note=""):
    extra = " <i>" + note + "</i>" if note else ""
    return str((item or {}).get("emoji") or "") + " <b>" + a + "</b> " + str((item or {}).get("does") or "") + " <b>" + b + "</b>" + extra
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
