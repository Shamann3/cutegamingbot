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
    BTN_YES,
    CARD,
    LEAVE_ASK,
    PROPOSE_FREE,
    PROPOSE_PAID,
    help_page,
    pay_label,
)
from bot.funcs.marriage_rules import (
    blocks_new_person,
    classify,
    profile_line,
    settings_view,
    together_label,
    tone_after,
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
    assert classify("топ браков")["kind"] == "top"
    assert classify("+браки")["kind"] == "on"
    assert classify("-браки")["kind"] == "off"
    assert classify("брак хелп") is None
    assert classify("браки") is None
    hug = classify("обнять крепко")
    assert hug["kind"] == "rp"
    assert hug["rp"]["id"] == "hug"
    assert hug["note"] == "крепко"
    assert classify("обнятья") is None
    air = classify("воздушный поцелуй тебе")
    assert air["rp"]["id"] == "air"
    assert classify("привет") is None
    assert classify("тонус")["kind"] == "card"


def test_profile_line_sits_as_one_short_sentence():
    now = datetime(2026, 10, 7, 12, tzinfo=timezone(timedelta(hours=3)))
    since = now - timedelta(days=2)
    line = profile_line({"name_html": "<a href='tg://user?id=1'>Анна</a>", "since": since}, now)
    assert "В браке с" in line
    assert "Анна" in line
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
    assert "Мой брак" in page
    free = PROPOSE_FREE.format(ring="r", dove="d", a="А", b="Б", which=1, left=3, minutes=10)
    paid = PROPOSE_PAID.format(ring="r", dove="d", a="А", b="Б", which=4, price="15", minutes=10)
    assert "бесплатная" in free
    assert "15 кут" in paid
    for screen in (free, paid, help_page()):
        assert BTN_YES in screen
        assert "кто написал «брак»" in screen.lower() or "кто написал «брак»" in screen
    assert BTN_NO in free
    assert BTN_STOP in free
    assert "Кнопки под этим сообщением" in free
    card = CARD.format(
        ring="r", heart="h", dove="d", a="А", b="Б",
        span="2 дня", date="01.01.2026 12:00", verbs="обнять",
        tone="Тонус: в тонусе.",
    )
    assert BTN_CARD_LEAVE in card
    assert BTN_LEAVE not in card
    ask = LEAVE_ASK.format(no="x", b="Б")
    assert BTN_STAY in ask
    assert BTN_LEAVE in ask
    assert pay_label("15") == "Списать 15 кут и сделать"
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
