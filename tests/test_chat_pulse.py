from datetime import date, datetime, timezone

from bot.funcs.chat_pulse import (
    compact_count,
    last_seen_label,
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


def test_last_seen_prefers_the_live_clock_then_the_stored_day():
    today = date(2026, 10, 6)
    now = datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc).timestamp()
    assert last_seen_label(seen_unix=now - 10, last_day=today, now_unix=now, today=today) == "только что"
    assert last_seen_label(seen_unix=now - 180, last_day=today, now_unix=now, today=today) == "3 мин назад"
    assert last_seen_label(seen_unix=None, last_day=today, now_unix=now, today=today) == "сегодня"
    assert last_seen_label(seen_unix=None, last_day=date(2026, 10, 5), now_unix=now, today=today) == "вчера"
    assert last_seen_label(seen_unix=None, last_day=None, now_unix=now, today=today) == "ещё не было"
    stored = datetime(2026, 10, 5, 12, 0)
    assert last_seen_label(seen_unix=None, last_day=stored, now_unix=now, today=today) == "вчера"


def test_old_activity_shows_a_real_date_instead_of_a_vague_word():
    today = date(2026, 10, 6)
    now = datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc).timestamp()
    assert last_seen_label(seen_unix=None, last_day=date(2026, 10, 3), now_unix=now, today=today) == "3 дн. назад"
    assert last_seen_label(seen_unix=None, last_day=date(2026, 9, 12), now_unix=now, today=today) == "12 сентября"
    assert last_seen_label(seen_unix=None, last_day=date(2025, 12, 31), now_unix=now, today=today) == "31.12.2025"
    two_days = now - 2 * 86400 - 60
    assert last_seen_label(seen_unix=two_days, last_day=None, now_unix=now, today=today) == "2 дн. назад"
    assert last_seen_label(seen_unix=now - 7200, last_day=date(2026, 9, 1), now_unix=now, today=today) == "2 ч назад"


def test_pulse_block_is_two_lines_with_the_given_premium_emoji():
    text = pulse_block("только что", 242, 2300, 10900, 61000)
    assert text.startswith("<tg-emoji emoji-id='5174659134607328175'>🕊</tg-emoji>")
    assert "<tg-emoji emoji-id='5472410705929971383'>📖</tg-emoji>" in text
    assert "Последний актив" not in text
    assert "Актив (" not in text
    # Новичку сразу видно, где считали и что считали.
    assert "Последнее сообщение в этой группе : только что" in text
    assert "Сообщений : сегодня 242 · неделя 2,3k · месяц 10,9k · всего 61k" in text
    assert text.count("\n") == 1


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
