from datetime import date, datetime, timedelta, timezone

from bot.funcs.chat_pulse import (
    as_seen_unix,
    compact_count,
    last_seen_label,
    msk_stamp,
    pending_today,
    pulse_block,
    windows,
)


def test_compact_count_matches_the_short_profile_scale():
    assert compact_count(0) == "0"
    assert compact_count(242) == "242"
    assert compact_count(2300) == "2,3k"
    assert compact_count(10900) == "10,9k"
    assert compact_count(61000) == "61k"
    assert compact_count(1_000_000) == "1 млн"


def test_last_seen_shows_moscow_clock_today_and_yesterday_as_a_word():
    today = date(2026, 10, 6)
    # 18:00 UTC — это 21:00 по Москве.
    now = datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc).timestamp()
    assert last_seen_label(seen_unix=now, last_day=today, now_unix=now, today=today) == "21:00"
    assert last_seen_label(seen_unix=now - 10, last_day=today, now_unix=now, today=today) == "20:59"
    assert last_seen_label(seen_unix=now - 180, last_day=today, now_unix=now, today=today) == "20:57"
    assert last_seen_label(seen_unix=None, last_day=today, now_unix=now, today=today) == "сегодня"
    assert last_seen_label(seen_unix=None, last_day=date(2026, 10, 5), now_unix=now, today=today) == "вчера"
    assert last_seen_label(seen_unix=None, last_day=None, now_unix=now, today=today) == "ещё не было"
    stored = datetime(2026, 10, 5, 12, 0)
    assert last_seen_label(seen_unix=None, last_day=stored, now_unix=now, today=today) == "вчера"
    # Полночь уже сегодня, а сообщение было в 23:50 — это всё ещё вчера.
    now_night = datetime(2026, 10, 5, 21, 20, tzinfo=timezone.utc).timestamp()
    late = datetime(2026, 10, 5, 20, 50, tzinfo=timezone.utc).timestamp()
    morning = datetime(2026, 10, 5, 21, 4, tzinfo=timezone.utc).timestamp()
    assert last_seen_label(
        seen_unix=late, last_day=date(2026, 10, 5), now_unix=now_night, today=today,
    ) == "вчера"
    assert last_seen_label(
        seen_unix=morning, last_day=None, now_unix=now_night, today=today,
    ) == "00:04"
    # Вчерашние часы не подменяют сегодняшний день, если минут уже нет.
    yesterday_clock = datetime(2026, 10, 5, 23, 40, tzinfo=timezone(timedelta(hours=3))).timestamp()
    assert last_seen_label(
        seen_unix=yesterday_clock, last_day=today, now_unix=now, today=today,
    ) == "сегодня"


def test_old_activity_shows_a_real_date_instead_of_a_vague_word():
    today = date(2026, 10, 6)
    now = datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc).timestamp()
    assert last_seen_label(seen_unix=None, last_day=date(2026, 10, 3), now_unix=now, today=today) == "3 дн. назад"
    assert last_seen_label(seen_unix=None, last_day=date(2026, 9, 12), now_unix=now, today=today) == "12 сентября"
    assert last_seen_label(seen_unix=None, last_day=date(2025, 12, 31), now_unix=now, today=today) == "31.12.2025"
    two_days = now - 2 * 86400 - 60
    assert last_seen_label(seen_unix=two_days, last_day=None, now_unix=now, today=today) == "2 дн. назад"
    assert last_seen_label(seen_unix=now - 7200, last_day=date(2026, 9, 1), now_unix=now, today=today) == "19:00"
    stamp = msk_stamp(now, today)
    assert stamp == datetime(2026, 10, 6, 21, 0)
    assert stamp.tzinfo is None
    assert msk_stamp(now, date(2026, 10, 5)) is None
    naive = datetime(2026, 10, 6, 9, 5)
    assert last_seen_label(
        seen_unix=as_seen_unix(naive), last_day=today, now_unix=now, today=today,
    ) == "09:05"


def test_pulse_block_is_two_lines_with_the_given_premium_emoji():
    text = pulse_block("только что", 242, 2300, 10900, 61000)
    assert text.startswith("<tg-emoji emoji-id='5174659134607328175'>🕊</tg-emoji>")
    assert "<tg-emoji emoji-id='5472410705929971383'>📖</tg-emoji>" in text
    assert "Последний актив" not in text
    assert "Актив (" not in text
    assert "Последняя активность : только что" in text
    assert "Д 242 | Н 2,3k | М 10,9k | Все 61k соо" in text
    assert text.count("\n") == 1
    clock = pulse_block("21:00", 4, 4, 4, 4)
    assert "Последняя активность : 21:00" in clock
    yesterday = pulse_block("вчера", 0, 1, 1, 1)
    assert "Последняя активность : вчера" in yesterday


def test_pulse_sits_in_a_blank_gap_after_the_fund():
    pulse = pulse_block("только что", 242, 2300, 10900, 61000)
    block = "фонд\n\n" + pulse + "\n"
    assert block.startswith("фонд\n\n")
    assert block.endswith("\n")
    assert block.count("\n\n") == 1


def test_pending_today_adds_only_this_chat_and_this_day():
    today = date(2026, 10, 6)
    buffer = {
        (7, -100, today): 4,
        (7, -100, date(2026, 10, 5)): 9,
        (7, -200, today): 3,
        (8, -100, today): 11,
    }
    assert pending_today(buffer, 7, -100, today) == 4
    week_start, month_start = windows(today)[1], windows(today)[2]
    assert week_start == date(2026, 9, 30)
    assert month_start == date(2026, 10, 1)
