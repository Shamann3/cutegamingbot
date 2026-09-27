from datetime import date

from group_guard_rules import (
    effective_flags,
    flood_stamps,
    flood_tripped,
    morning_due,
    morning_text,
    punish_receipt,
    text_has_link,
)


def test_link_detects_telegram_and_http():
    assert text_has_link("смотри https://example.com")
    assert text_has_link("t.me/CuteRules")
    assert not text_has_link("просто слова в чате")


def test_flood_needs_six_messages_in_the_window():
    stamps = []
    now = 1000.0
    for step in range(5):
        stamps = flood_stamps(stamps, now + step)
        assert not flood_tripped(stamps)
    stamps = flood_stamps(stamps, now + 5)
    assert flood_tripped(stamps)
    later = flood_stamps(stamps, now + 30)
    assert not flood_tripped(later)


def test_receipt_names_the_official_archive_and_warn_step():
    text = punish_receipt("Модератор", "warn", 2)
    assert "официальной группы" in text
    assert "Модератор" in text
    assert "2 из 3" in text
    assert "Ещё одно предупреждение" in text
    plain = punish_receipt("Модератор", "mute", None)
    assert "из 3" not in plain


def test_shared_rule_yields_to_a_group_exception():
    shared = {"captcha": True, "links": True, "flood": False}
    assert effective_flags(custom=False, links=False, flood=True, captcha=False, policy=shared) == {
        "captcha": True,
        "links": True,
        "flood": False,
    }
    assert effective_flags(custom=True, links=False, flood=True, captcha=False, policy=shared)["links"] is False


def test_morning_follows_the_chosen_hour():
    assert morning_due(9, enabled=True, morning_hour=9)
    assert not morning_due(10, enabled=True, morning_hour=9)
    assert not morning_due(9, enabled=False, morning_hour=9)
    text = morning_text([
        {"title": "Кьют", "today": None, "yesterday": 4, "close": 1},
    ])
    assert "сегодня —" in text
    assert "вчера 4" in text
    assert "На 2 из 3: 1" in text
    assert date.today()
