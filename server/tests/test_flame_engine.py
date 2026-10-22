# -*- coding: utf-8 -*-
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flame_engine import gift_preview, help_html, need_for, profile_line, span_label, title_for


def test_span_label_days_months_years():
    assert span_label(1) == "1 день"
    assert span_label(2) == "2 дня"
    assert span_label(5) == "5 дней"
    assert span_label(21) == "21 день"
    assert span_label(90) == "3 месяца"
    assert span_label(365) == "1 год"
    assert span_label(400) == "1 год 1 месяц 5 дней"


def test_need_grows_from_the_chosen_day():
    steps = [{"from_day": 7, "messages": 250}, {"from_day": 30, "messages": 400}]
    assert need_for(1, 200, steps) == 200
    assert need_for(6, 200, steps) == 200
    assert need_for(7, 200, steps) == 250
    assert need_for(29, 200, steps) == 250
    assert need_for(30, 200, steps) == 400


def test_profile_line_with_status_title():
    assert profile_line(0) == ""
    text = profile_line(2)
    assert "Огонёк уже 2 дня" in text
    titled = profile_line(10, [{"from_day": 7, "title": "Живой огонь", "emoji_id": "1"}])
    assert "Живой огонь" in titled
    assert "10 дней" in titled


def test_title_picks_highest_unlocked():
    titles = [
        {"from_day": 3, "title": "Искра"},
        {"from_day": 14, "title": "Негасимый"},
    ]
    assert title_for(2, titles) is None
    assert title_for(3, titles)["title"] == "Искра"
    assert title_for(20, titles)["title"] == "Негасимый"


def test_help_lists_rewards_and_warm_hour():
    html = help_html({
        "settings": {"enabled": True, "base_messages": 200, "min_words": 2},
        "steps": [{"from_day": 7, "messages": 250}],
        "rewards": [
            {"day": 3, "kind": "bonus", "amount": 1, "item_name": ""},
            {"day": 7, "kind": "kuty", "amount": 50, "item_name": ""},
        ],
        "titles": [{"from_day": 7, "title": "Живой огонь"}],
        "warm": {"enabled": True, "min_day": 3, "every": 40, "cap": 3, "hour": 18},
        "gift": {"enabled": True, "mult": 2},
    })
    assert "200" in html
    assert "с 7-го — <b>250</b>" in html
    assert "3 дня" in html
    assert "50 кут" in html
    assert "Тёплый час" in html
    assert "18:00" in html
    assert "🎁" in html
    assert "Как работает" in html
    assert "официальных группах" in html


def test_gift_preview_shows_average():
    preview = gift_preview(
        [
            {"kind": "item", "item_name": "Купон", "weight": 1},
            {"kind": "kuty", "amount_min": 10, "amount_max": 10, "weight": 1},
        ],
        mult=2,
        kuty_min=1,
        kuty_max=3,
    )
    assert preview["mult"] == 2
    assert preview["kutyMin"] == 2
    assert preview["kutyMax"] == 6
    assert preview["itemChancePct"] == 50.0
    assert preview["avgPerOpen"] > 0


def test_missed_day_is_before_yesterday():
    today = date(2026, 10, 22)
    yesterday = today - timedelta(days=1)
    assert yesterday == date(2026, 10, 21)
    assert date(2026, 10, 20) < yesterday
