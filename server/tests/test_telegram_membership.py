"""telegram_membership: чистые функции статус-маппинга и TTL, без сети/БД."""
from datetime import datetime, timedelta, timezone

from telegram_membership import (
    _is_cache_fresh,
    _is_member_status,
    normalize_channel,
    TTL_MINUTES,
)

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def test_is_member_status_true_for_member_administrator_creator():
    assert _is_member_status("member") is True
    assert _is_member_status("administrator") is True
    assert _is_member_status("creator") is True


def test_is_member_status_false_for_other_statuses():
    assert _is_member_status("left") is False
    assert _is_member_status("kicked") is False
    assert _is_member_status("restricted") is False
    assert _is_member_status(None) is False
    assert _is_member_status("") is False


def test_is_member_status_case_insensitive():
    assert _is_member_status("Member") is True
    assert _is_member_status("CREATOR") is True


def test_is_cache_fresh_within_ttl():
    checked_at = NOW - timedelta(minutes=5)
    assert _is_cache_fresh(checked_at, NOW, ttl_minutes=TTL_MINUTES) is True


def test_is_cache_fresh_stale_after_ttl():
    checked_at = NOW - timedelta(minutes=11)
    assert _is_cache_fresh(checked_at, NOW, ttl_minutes=TTL_MINUTES) is False


def test_is_cache_fresh_exactly_at_ttl_boundary_is_stale():
    checked_at = NOW - timedelta(minutes=TTL_MINUTES)
    assert _is_cache_fresh(checked_at, NOW, ttl_minutes=TTL_MINUTES) is False


def test_normalize_channel_plain_username():
    assert normalize_channel("mychannel") == "mychannel"
    assert normalize_channel("@mychannel") == "mychannel"
    assert normalize_channel("  @mychannel  ") == "mychannel"


def test_normalize_channel_from_link():
    assert normalize_channel("https://t.me/mychannel") == "mychannel"
    assert normalize_channel("http://t.me/mychannel") == "mychannel"
    assert normalize_channel("t.me/mychannel") == "mychannel"
    assert normalize_channel("https://t.me/mychannel/") == "mychannel"
    assert normalize_channel("https://telegram.me/mychannel") == "mychannel"


def test_normalize_channel_preserves_case_and_underscores():
    assert normalize_channel("https://t.me/Cute_Gaming") == "Cute_Gaming"


def test_normalize_channel_empty():
    assert normalize_channel("") == ""
    assert normalize_channel(None) == ""
