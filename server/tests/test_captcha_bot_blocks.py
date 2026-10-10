"""Блокировки, которые бот ставит сам за непройденную капчу."""
import inspect
import pathlib
import sys
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from admin_captcha import (
    BOT_BLOCK_ACTIONS,
    CAPTCHA_REMOVE_ACTIONS,
    bot_blocks,
    captcha_removed_stat,
    day_strip,
    hold_label,
    penalty_face,
)


def test_only_bans_count_as_a_bot_block():
    assert BOT_BLOCK_ACTIONS == ("ban", "banall", "banfull")
    assert penalty_face("banfull")["block"] is True
    assert penalty_face("banfull")["label"] == "Банфулл"
    assert penalty_face("mute")["block"] is False
    assert penalty_face("kick")["block"] is False


def test_a_ban_without_a_term_says_so_and_a_kick_does_not():
    assert hold_label("ban", None) == "без срока"
    assert "час" in hold_label("ban", 60)
    assert hold_label("kick", None) == ""


def test_the_strip_keeps_empty_days():
    today = date(2026, 10, 10)
    days = day_strip({date(2026, 10, 9): 3}, today)
    assert len(days) == 14
    assert days[0]["day"] == "2026-09-27"
    assert days[-2] == {"day": "2026-10-09", "n": 3}
    assert days[-1] == {"day": "2026-10-10", "n": 0}


def test_archive_counts_people_captcha_removed():
    assert "kick" in CAPTCHA_REMOVE_ACTIONS
    assert "ban" in CAPTCHA_REMOVE_ACTIONS
    assert "mute" not in CAPTCHA_REMOVE_ACTIONS
    source = inspect.getsource(captcha_removed_stat)
    assert "admin_name = 'Капча'" in source
    assert "count(DISTINCT target_player_id)" in source
    assert "INTERVAL '30 days'" in source
    assert "event = 'blocked'" not in source


def test_deleted_messages_are_not_counted_as_blocks():
    source = inspect.getsource(bot_blocks)
    assert "admin_name = 'Капча'" in source
    assert "date_trunc('minute', created_at)" in source
    assert "event = 'blocked'" not in source
    assert "active_bans" in source
