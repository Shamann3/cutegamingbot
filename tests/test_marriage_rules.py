from datetime import date, datetime, timedelta, timezone

from bot.funcs.marriage_design import (
    ALERT_BUSY,
    ALERT_CLOSED,
    ALERT_EXPIRED,
    ALERT_NOT_INVITED,
    ALERT_NOT_PAYER,
    ALERT_TILL,
    BTN_CARD_LEAVE,
    BTN_LEAVE,
    BTN_NO,
    BTN_STAY,
    BTN_STOP,
    BTN_GEST,
    BTN_TONE,
    BTN_WHAT,
    BTN_YES,
    LEAVE_ASK,
    PROPOSE_FREE,
    PROPOSE_PAID,
    RED_ID,
    card_text,
    help_page,
    pay_label,
    spark_level,
)
from bot.funcs.marriage_live import _kb_ask, _kb_card, _kb_leave
from bot.funcs.marriage_rules import (
    blocks_new_person,
    classify,
    face_from_dex,
    is_marriage_code,
    own_ribbon,
    person_html,
    profile_line,
    ribbon_ask,
    settings_view,
    shares_general_rp,
    together_label,
    tone_after,
    add_spark_care,
    each_share,
    level_of,
    settle_spark,
    tone_brief,
    tone_label,
    tone_score,
    wedding_price,
    which_wedding,
)


def test_three_free_then_double_until_300_then_fifteen_percent():
    assert [wedding_price(n) for n in range(3)] == [0, 0, 0]
    assert wedding_price(3) == 15
    assert wedding_price(4) == 30
    assert wedding_price(5) == 60
    assert wedding_price(6) == 120
    assert wedding_price(7) == 240
    assert wedding_price(8) == 300
    assert wedding_price(9) == 345
    assert wedding_price(10) == 397
    assert which_wedding(0) == 1
    assert which_wedding(3) == 4


def test_phrases_a_newcomer_can_type_and_help_stays_help():
    assert classify("Брак")["kind"] == "wed"
    assert classify("мой брак")["kind"] == "card"
    assert classify("развод")["kind"] == "leave"
    assert classify("развестись")["kind"] == "leave"
    assert classify("разведёмся")["kind"] == "leave"
    assert classify("топ браков")["kind"] == "top"
    assert classify("+браки")["kind"] == "on"
    assert classify("+ браки")["kind"] == "on"
    assert classify("-браки")["kind"] == "off"
    assert classify("выключить браки")["kind"] == "off"
    assert classify("брак хелп") is None
    assert classify("браки")["kind"] == "list"
    assert classify("список браков")["kind"] == "list"
    assert classify("выйти замуж")["kind"] == "wed"
    assert classify("жениться")["kind"] == "wed"
    hug = classify("обнять крепко")
    assert hug["kind"] == "rp"
    assert hug["rp"]["id"] == "hug"
    assert hug["verb"] == "обнять"
    assert hug["note"] == "крепко"
    assert shares_general_rp(hug["rp"], hug["verb"])
    kiss = classify("поцелуй")
    assert kiss["rp"]["id"] == "kiss"
    assert kiss["verb"] == "поцелуй"
    assert not shares_general_rp(kiss["rp"], kiss["verb"])
    assert classify("обнятья") is None
    air = classify("воздушный поцелуй тебе")
    assert air["rp"]["id"] == "air"
    assert classify("привет") is None
    assert classify("тонус")["kind"] == "tone"
    assert classify("мой тонус")["kind"] == "tone"
    assert classify("наш брак")["kind"] == "card"


def test_ribbon_comes_off_only_by_a_real_command():
    assert classify("снять ленту")["kind"] == "ribbon_off"
    assert classify("Снять ленту брака!")["kind"] == "ribbon_off"
    assert classify("сними ленту пожалуйста")["kind"] == "ribbon_off"
    assert classify("убрать ленту с профиля")["kind"] == "ribbon_off"
    assert classify("хочу снять ленту") is None
    assert classify("снять ленту брака завтра") is None
    assert classify("лента красивая") is None
    assert classify("снять варн") is None
    assert classify("я снял ленту вчера") is None
    book = {"payer_id": 1, "partner_id": 2, "ribbon": True, "ribbon_payer": True, "ribbon_partner": False}
    assert own_ribbon(book, 1) is True
    assert own_ribbon(book, 2) is False
    now = datetime(2026, 10, 7, 12, tzinfo=timezone(timedelta(hours=3)))
    worn = profile_line({"name_html": "Анна", "since": now, "ribbon": True}, now)
    assert worn.startswith("🎀")
    assert "В браке с" in worn
    assert "\n" not in worn
    ask = ribbon_ask()
    assert "Снять ленту?" in ask
    assert "Брак останется" in ask
    labels = [row[0].text for row in _kb_card("7", True).inline_keyboard]
    assert "Лента в профиле" in labels
    assert labels[-1] == BTN_CARD_LEAVE


def test_dex_row_is_the_face_of_an_item():
    gift = {"id": "glow", "name": "Блик брака", "emoji": "🎇", "price": 12, "line": "старое", "on": True}
    faced = face_from_dex(gift, {"name": "Искорка", "emoji": "✨", "price": 9, "bio": "Свет.", "remains": 4})
    assert faced["name"] == "Искорка"
    assert faced["emoji"] == "✨"
    assert faced["price"] == 9
    assert faced["line"] == "Свет."
    assert faced["on"] is True
    hidden = face_from_dex(gift, {"remains": 0})
    assert hidden["on"] is False
    assert is_marriage_code("mrgglow") and is_marriage_code("mrribbon")
    assert not is_marriage_code("mrgquiet")
    assert not is_marriage_code("seed")


def test_profile_line_sits_as_one_short_sentence():
    now = datetime(2026, 10, 7, 12, tzinfo=timezone(timedelta(hours=3)))
    since = now - timedelta(days=2)
    line = profile_line({"name_html": "<a href='tg://user?id=1'>Анна</a>", "since": since}, now)
    assert "В браке с" in line
    assert "Анна" in line
    assert "tg://user?id=1" in line
    shown = person_html(5, "@Лана", "lana")
    assert "Лана" in shown
    assert "https://t.me/lana" in shown
    assert "tg://user" not in shown
    assert "@" not in shown
    handle = person_html(5, "", "lana")
    assert "https://t.me/lana" in handle
    assert "@" not in handle
    bare = person_html(5, "Анна", "")
    assert "tg://user?id=5" in bare
    assert "Анна" in bare
    assert "2 дня" in line
    assert "\n" not in line.strip()
    empty = profile_line({"name_html": "", "since": None}, now)
    assert "Брака нет" in empty
    assert "«брак»" in empty
    assert "\n" not in empty.strip()
    assert together_label(now, now) == "сегодня"


def test_help_page_uses_the_same_numbers_as_the_ladder():
    page = help_page()
    assert "3" in page
    assert "15" in page
    assert "300" in page
    assert "tg-emoji" in page
    assert RED_ID in page
    assert "Мой брак" in page
    assert "кто написал «брак»" in page
    free = PROPOSE_FREE.format(heart="r", a="А", b="Б", which=1, free=3, minutes=10)
    paid = PROPOSE_PAID.format(heart="r", a="А", b="Б", which=4, price="15", minutes=10)
    assert "Бесплатно" in free
    assert "15 кут" in paid
    assert "\n\n" not in free.strip()
    for screen in (free, paid, page):
        assert BTN_YES in screen
        assert BTN_NO in screen
    assert BTN_STOP in free
    card = card_text("А", "Б", "2 дня", "01.01.2026 12:00", "Тонус 80 · в тонусе")
    assert "Тонус 80" in card
    assert BTN_CARD_LEAVE not in card
    assert BTN_LEAVE not in card
    assert card.count("\n") <= 3
    ask = LEAVE_ASK.format(heart="x", b="Б")
    assert "Расторгнуть" in ask
    assert "не вернутся" in ask
    assert BTN_STAY not in ask
    row = _kb_ask(7).inline_keyboard
    assert row[0][0].text == BTN_NO
    assert row[0][0].style == "danger"
    assert row[0][1].text == BTN_YES
    assert row[0][1].style == "success"
    assert row[1][0].text == BTN_STOP
    assert row[1][0].style == "primary"
    leave = _kb_leave("7").inline_keyboard[0]
    assert leave[0].text == BTN_STAY and leave[0].style == "success"
    assert leave[1].text == BTN_LEAVE and leave[1].style == "danger"
    card_kb = _kb_card("7", True).inline_keyboard
    assert card_kb[0][0].text == BTN_GEST and card_kb[0][0].style == "primary"
    assert card_kb[1][0].text == BTN_TONE and card_kb[1][0].style == "default"
    assert card_kb[2][0].text == BTN_WHAT and card_kb[2][0].style == "default"
    assert card_kb[-1][0].text == BTN_CARD_LEAVE and card_kb[-1][0].style == "danger"
    assert pay_label("15") == "Списать 15 кут"
    for popup in (ALERT_BUSY, ALERT_CLOSED, ALERT_EXPIRED, ALERT_NOT_INVITED, ALERT_NOT_PAYER, ALERT_TILL):
        assert len(popup) <= 200
        assert "<" not in popup


def test_settings_change_the_price_and_tone_stays_one_day():
    custom = settings_view({"freeWeddings": 0, "firstPaid": 10, "doubleUntil": 20, "afterPercent": 0})
    assert wedding_price(0, custom) == 10
    assert wedding_price(1, custom) == 20
    assert wedding_price(2, custom) == 20
    today = date(2026, 10, 7)
    assert tone_score(80, today, today, 8) == 80
    assert tone_score(80, date(2026, 10, 6), today, 8) == 72
    raised, day = tone_after(80, date(2026, 10, 6), today, 8, 12)
    assert (raised, day) == (84, today)
    again, _day = tone_after(84, today, today, 8, 12)
    assert again == 84
    brief = tone_brief(80, date(2026, 10, 6), today, 8, 12)
    assert brief["score"] == 72
    assert brief["next"] == 84
    assert brief["fresh"]
    assert "84" in brief["hint"]
    held = tone_brief(84, today, today, 8, 12)
    assert not held["fresh"]
    assert tone_label(84) == "в тонусе"
    assert tone_label(72) == "спокойно"
    assert tone_label(20) == "тихо"
    assert tone_label(4) == "остывает"
    assert blocks_new_person("ask")
    assert blocks_new_person("billing")
    assert blocks_new_person("live")
    assert not blocks_new_person("left")
    broken = settings_view({"freeWeddings": -4, "proposalMinutes": 99999, "verbs": {"hug": 40, "nope": 9}})
    assert broken["freeWeddings"] == 0
    assert broken["proposalMinutes"] == 1440
    assert broken["verbs"] == {"hug": 40}
    assert "тонус" in help_page(custom).lower()
    assert "искра" in help_page(custom).lower()


def test_spark_needs_both_people_and_can_be_saved():
    msk = timezone(timedelta(hours=3))
    assert each_share(10) == 5
    assert level_of(0)["name"] == "Знакомство"
    assert level_of(3)["name"] == "Тепло"
    assert level_of(3)["goal"] == 16
    morning = datetime(2026, 10, 7, 10, 0, tzinfo=msk)
    afternoon = datetime(2026, 10, 7, 13, 0, tzinfo=msk)
    closed = {
        "spark_days": 2,
        "spark_day": date(2026, 10, 6),
        "care_payer": 5,
        "care_partner": 5,
    }
    rolled = settle_spark(closed, morning, 12)
    assert rolled["state"]["spark_days"] == 3
    assert rolled["state"]["spark_day"] == date(2026, 10, 7)
    assert rolled["state"]["care_payer"] == 0
    assert rolled["state"]["care_partner"] == 0
    assert rolled["level"]["name"] == "Тепло"
    assert rolled["need"] == 8
    short = {
        "spark_days": 3,
        "spark_day": date(2026, 10, 6),
        "care_payer": 8,
        "care_partner": 1,
    }
    fading = settle_spark(short, morning, 12)
    assert fading["fading"]
    assert fading["state"]["spark_days"] == 3
    assert fading["clock"] == "12:00"
    one = add_spark_care(short, "payer", 10, morning, 12)
    assert not one["saved"]
    assert one["state"]["care_partner"] == 1
    both = add_spark_care(one["state"], "partner", 7, morning, 12)
    assert both["saved"]
    assert both["state"]["spark_days"] == 4
    assert both["state"]["care_payer"] == 10
    assert both["state"]["care_partner"] == 0
    assert both["state"]["spark_day"] == date(2026, 10, 7)
    dead = settle_spark(short, afternoon, 12)
    assert dead["state"]["spark_days"] == 0
    assert dead["state"]["care_payer"] == 0
    assert dead["lost"] == 3
    assert dead["level"]["name"] == "Знакомство"
    assert classify("искра")["kind"] == "tone"


def test_spare_stays_and_burns_one_share_each_day():
    from bot.funcs.marriage_design import spark_home

    msk = timezone(timedelta(hours=3))
    morning = datetime(2026, 10, 7, 10, 0, tzinfo=msk)
    bank = settle_spark({
        "spark_days": 0,
        "spark_day": date(2026, 10, 5),
        "care_payer": 20,
        "care_partner": 20,
    }, morning, 12)
    assert bank["state"]["spark_days"] == 2
    assert bank["state"]["spark_day"] == date(2026, 10, 7)
    assert bank["state"]["care_payer"] == 10
    assert bank["state"]["care_partner"] == 10
    later = datetime(2026, 10, 8, 10, 0, tzinfo=msk)
    burned = settle_spark(bank["state"], later, 12)
    assert burned["state"]["spark_days"] == 3
    assert burned["state"]["care_payer"] == 5
    assert burned["need"] == 8
    assert burned["level"]["name"] == "Тепло"
    grown = settle_spark({
        "spark_days": 6,
        "spark_day": date(2026, 10, 5),
        "care_payer": 30,
        "care_partner": 30,
    }, datetime(2026, 10, 8, 10, 0, tzinfo=msk), 12)
    assert grown["state"]["spark_days"] == 9
    assert grown["state"]["care_payer"] == 0
    assert grown["level"]["name"] == "Близость"
    uneven = settle_spark({
        "spark_days": 0,
        "spark_day": date(2026, 10, 6),
        "care_payer": 20,
        "care_partner": 5,
    }, morning, 12)
    assert uneven["state"]["spark_days"] == 1
    assert uneven["state"]["care_payer"] == 15
    assert uneven["state"]["care_partner"] == 0
    fade = settle_spark(uneven["state"], later, 12)
    assert fade["fading"]
    assert fade["state"]["spark_days"] == 1
    assert fade["state"]["care_payer"] == 15
    dead = settle_spark(uneven["state"], datetime(2026, 10, 8, 13, 0, tzinfo=msk), 12)
    assert dead["state"]["spark_days"] == 0
    assert dead["state"]["care_payer"] == 0
    page = spark_home("А", "Б", "1 день", "", bank, 10, 10, "Б")
    assert "Запас: ты 5" in page


def test_custom_levels_drive_the_spark_and_drop_bad_rows():
    custom = settings_view({
        "levels": [
            {"name": "Искра", "days": 5, "goal": 4},
            {"name": "<Пламя>", "days": 5, "goal": -3},
            {"name": "", "days": 0, "goal": 8},
        ]
    })
    rows = custom["levels"]
    assert [row["days"] for row in rows] == [0, 5, 6]
    assert rows[0]["name"] == "Уровень 1"
    assert rows[0]["goal"] == 8
    assert rows[1]["name"] == "Искра"
    assert rows[1]["goal"] == 4
    assert rows[2]["name"] == "Пламя"
    assert rows[2]["goal"] == 2
    assert "<" not in rows[2]["name"]
    assert level_of(0, custom)["name"] == "Уровень 1"
    assert level_of(5, custom)["name"] == "Искра"
    assert level_of(6, custom)["goal"] == 2
    fresh = settings_view({"levels": []})
    assert fresh["levels"][0]["name"] == "Знакомство"
    assert fresh["levels"][0]["goal"] == 10
    junk = settings_view({"levels": [{"name": "x" * 40, "days": -9, "goal": 9999}, "nope", {"days": "a"}]})
    assert junk["levels"][0]["days"] == 0
    assert len(junk["levels"][0]["name"]) == 24
    assert junk["levels"][0]["goal"] == 9999
    assert len(junk["levels"]) == 2
    assert junk["levels"][1]["days"] == 1
    wide = settings_view({"levels": [{"name": str(i), "days": i, "goal": 4} for i in range(15)]})
    assert len(wide["levels"]) == 12
    msk = timezone(timedelta(hours=3))
    morning = datetime(2026, 10, 7, 10, 0, tzinfo=msk)
    cfg = settings_view({"levels": [
        {"name": "Тихо", "days": 0, "goal": 4},
        {"name": "Громко", "days": 2, "goal": 20},
    ]})
    rolled = settle_spark({
        "spark_days": 1,
        "spark_day": date(2026, 10, 6),
        "care_payer": 2,
        "care_partner": 2,
    }, morning, 12, cfg)
    assert rolled["state"]["spark_days"] == 2
    assert rolled["level"]["name"] == "Громко"
    assert rolled["need"] == 10
    assert rolled["table"][0]["name"] == "Тихо"
    page = help_page(cfg)
    assert "Тихо" in page
    assert "по 2" in page
    screen = spark_level(rolled)
    assert "Громко" in screen
    assert "Знакомство" not in screen


def test_gifts_help_only_your_half_and_stack_in_the_bag():
    from bot.funcs.marriage_design import GIFT_ALERT
    from bot.funcs.marriage_rules import gift_catalog, gift_plan
    from bot.funcs.marriage_store import _count_items, _take_one

    view = settings_view({
        "candlePrice": 40,
        "candleCare": 7,
        "matchPrice": 90,
        "ribbonPrice": 10,
        "glowCare": 4,
        "hearthPrice": 55,
    })
    assert view["candlePrice"] == 40
    assert view["candleCare"] == 7
    assert view["glowCare"] == 4
    assert view["hearthCare"] == 20
    catalog = gift_catalog(view)
    ids = [row["id"] for row in catalog]
    assert ids[:5] == ["glow", "candle", "hearth", "match", "ribbon"]
    assert len(ids) == 21 and len(set(ids)) == 21
    assert catalog[0]["care"] == 4
    assert catalog[1]["care"] == 7
    assert catalog[1]["price"] == 40
    assert catalog[2]["price"] == 55
    assert catalog[2]["care"] == 20
    assert catalog[3]["price"] == 90
    assert gift_plan("candle", True, 0, 5, care=7) == {"ok": True, "reason": "", "care": 7}
    assert gift_plan("candle", False, 9, 5, care=7)["care"] == 7
    assert gift_plan("glow", False, 0, 5, care=3)["care"] == 3
    assert gift_plan("hearth", True, 20, 5, care=20)["care"] == 20
    assert gift_plan("match", False, 0, 5)["reason"] == "calm"
    assert gift_plan("match", True, 1, 5)["care"] == 4
    assert gift_plan("match", True, 5, 5)["reason"] == "full"
    assert gift_plan("ribbon", False, 0, 5, ribbon=True)["reason"] == "worn"
    assert gift_plan("ribbon", False, 0, 5)["ok"]
    gift = {"name": "Свеча брака", "name1": "mrgcandle"}
    items = {"Свеча брака": 1, "15": 2}
    assert _count_items(items, gift, 15) == 3
    left = _take_one(items, gift, 15)
    assert _count_items(left, gift, 15) == 2
    for text in GIFT_ALERT.values():
        assert len(text) <= 200
        assert "<" not in text


def test_kind_words_feed_the_flame_and_the_week_is_visible():
    from datetime import date

    from bot.funcs.marriage_design import classify, flame_strip, settings_view, verb_care, verb_catalog

    pity = classify("пожалеть")
    assert pity["kind"] == "rp"
    assert pity["verb"] == "пожалеть"
    tea = classify("принести чай ей")
    assert tea["rp"]["id"] == "tea"
    assert tea["note"] == "ей"
    view = settings_view({"sparks": {"hug": 9}, "waits": {"hug": 15}})
    assert view["sparks"]["hug"] == 9
    assert view["waits"]["hug"] == 15
    assert view["sparks"]["pity"] == 3
    assert verb_care({"id": "hug", "care": 4}, view) == 9
    row = next(item for item in verb_catalog(view) if item["id"] == "pity")
    assert row["word"] == "пожалеть"
    assert row["care"] == 3
    assert row["wait"] == 30
    strip = flame_strip(
        {"spark_days": 3, "spark_day": date(2026, 10, 8)},
        today=date(2026, 10, 9),
        both_done=False,
    )
    assert "🔥" in strip
    assert "сегодня" in strip
    assert "пн" not in strip
    assert "◌" in strip
    assert "ещё можно" in strip
    from bot.funcs.marriage_design import HOW_TEXT, WHAT_TEXT, spark_fire
    assert "лимит" in WHAT_TEXT.lower()
    assert "доброе слово" in WHAT_TEXT.lower()
    assert "оба" in HOW_TEXT.lower()
    fire = spark_fire(
        {"need": 5, "goal": 10, "both_done": False, "fading": False, "level": {"name": "Знакомство"}, "state": {"spark_days": 0}},
        2, 0, "Б", 12,
    )
    assert "Лимит 10" in fire
    assert "ещё 3" in fire
    from bot.funcs.marriage_design import spark_home
    home = spark_home("А", "Б", "1 день", "", {
        "need": 5, "goal": 10, "both_done": False, "fading": True, "clock": "12:00",
        "level": {"name": "Знакомство"},
        "state": {"spark_days": 0},
        "holidays": [{"day": 7, "name": "Первая неделя"}],
    }, 7, 2, "Б")
    assert "Лимит 10" in home
    assert "ещё 3" in home
    assert "первый огонёк" in home
    assert "сегодня до 12:00" in home
    assert "сб" not in home
    assert "Огонька нет" not in home
    assert "Гаснет" not in home
    assert "●" in home
    from bot.funcs.marriage_design import care_meter
    wide = care_meter(120, 500)
    assert wide.count("●") + wide.count("○") == 8
    assert "120/500" in wide
    assert "ещё 380" in wide
    full = care_meter(1200, 500)
    assert "1 200/500" in full
    assert "+700" in full


def test_every_button_is_written_under_its_message():
    from bot.funcs.marriage_design import button_rows, screen_of_item
    from bot.funcs.marriage_live import _kb_gifts

    assert screen_of_item("glow") == "item_glow"
    shop = _kb_gifts([{"id": "glow", "price": 15, "have": 2, "buy": True}])
    words = [btn.text for row in shop.inline_keyboard for btn in row]
    assert words[0].startswith("Купить блик")
    assert "15" in words[0]
    assert words[1].startswith("Зажечь")
    assert words[1].endswith("2")
    early = [btn["data"] for row in button_rows("feast") for btn in row]
    assert "mrg:wish:premium6" not in early
    late = [btn["data"] for row in button_rows("feast", ("late",)) for btn in row]
    assert "mrg:wish:premium6" in late
    assert "mrg:mine:0" in late
