"""Розыгрыши: чистые функции bucket/отображаемого имени, без БД."""
from datetime import datetime, timedelta, timezone

from giveaway_display import giveaway_bucket, display_name

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def test_completed_is_past_regardless_of_starts_at():
    assert giveaway_bucket("completed", None, NOW) == "past"
    assert giveaway_bucket("completed", NOW + timedelta(days=1), NOW) == "past"


def test_active_with_no_starts_at_is_active():
    assert giveaway_bucket("active", None, NOW) == "active"


def test_active_with_past_starts_at_is_active():
    assert giveaway_bucket("active", NOW - timedelta(hours=1), NOW) == "active"


def test_active_with_future_starts_at_is_upcoming():
    assert giveaway_bucket("active", NOW + timedelta(hours=1), NOW) == "upcoming"


def test_active_with_starts_at_exactly_now_is_active():
    assert giveaway_bucket("active", NOW, NOW) == "active"


def test_display_name_prefers_username():
    assert display_name("alex_trade", "Alex") == "@alex_trade"


def test_display_name_falls_back_to_first_name():
    assert display_name(None, "Alex") == "Alex"
    assert display_name("", "Alex") == "Alex"


def test_display_name_falls_back_to_generic_label():
    assert display_name(None, None) == "Игрок"
    assert display_name("", "") == "Игрок"
