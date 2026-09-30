from datetime import date

from stat_lens import (
    anchor_day,
    gained,
    games_people_see,
    period_bounds,
    phase,
    plan_period_total,
    seen_number,
)


def test_period_bounds_follow_moscow_calendar():
    today = date(2026, 9, 30)
    assert period_bounds("day", today) == (today, today)
    assert period_bounds("week", today) == (date(2026, 9, 28), date(2026, 10, 4))
    assert period_bounds("month", today) == (date(2026, 9, 1), date(2026, 9, 30))
    assert period_bounds("year", today) == (date(2026, 1, 1), date(2026, 12, 31))
    assert period_bounds("all", today) is None
    assert anchor_day("week", today) == today
    assert anchor_day("all", today) == today


def test_people_see_zero_inside_the_window_and_the_sum_after():
    start, end = date(2026, 10, 1), date(2026, 10, 7)
    assert phase(date(2026, 9, 30), start, end) == "before"
    assert phase(date(2026, 10, 3), start, end) == "zero"
    assert phase(date(2026, 10, 8), start, end) == "after"
    assert seen_number(1040, 1000, "before") == 1040
    assert seen_number(1040, 1000, "zero") == 0
    assert seen_number(1040, 1000, "after") == 1040
    assert gained(1040, 1000) == 40
    assert seen_number(5, None, "after") == 5


def test_game_copy_keeps_only_games_after_the_snapshot():
    assert games_people_see(1040, None) == 1040
    assert games_people_see(1040, 1000) == 40
    assert games_people_see(1000, 1000) == 0
    assert games_people_see(10, 40) == 0


def test_period_total_lands_on_the_anchor_without_going_negative():
    days = [(date(2026, 9, 28), 400), (date(2026, 9, 30), 100)]
    assert plan_period_total(days, date(2026, 9, 30), 1000) == [(date(2026, 9, 30), 600)]
    assert plan_period_total(days, date(2026, 9, 30), 200) == [
        (date(2026, 9, 30), 0),
        (date(2026, 9, 28), 200),
    ]
    assert plan_period_total(days, date(2026, 9, 30), 500) == []
