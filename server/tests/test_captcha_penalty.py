from captcha_penalty import clean_penalty, penalty_fires, penalty_sentence
from official_ids import chat_is_official, merged_official_ids


def test_panel_official_group_counts_even_if_it_is_not_in_the_old_list():
    old = (-1001612636292, -1001921925861)
    live = (-100555, -1001612636292, 42)
    assert chat_is_official(-100555, hardcoded=old, live=live)
    assert chat_is_official(-1001612636292, hardcoded=old, live=())
    assert not chat_is_official(42, hardcoded=old, live=live)
    assert not chat_is_official(-100555, hardcoded=old, live=live, excluded=(-100555,))
    assert merged_official_ids(old, live)[:2] == [-1001612636292, -1001921925861]
    assert -100555 in merged_official_ids(old, live)


def test_captcha_penalty_fires_once_the_streak_is_reached():
    rule = {"enabled": True, "strikes": 5, "action": "banfull", "seconds": 3600}
    assert penalty_fires(4, rule) is False
    assert penalty_fires(5, rule) is True
    assert penalty_fires(6, rule) is True
    assert penalty_fires(6, rule, already=True) is False
    assert penalty_fires(9, {"enabled": False, "strikes": 5, "action": "mute"}) is False
    assert penalty_fires(9, {"enabled": True, "strikes": 5, "action": "nope"}) is False


def test_captcha_penalty_keeps_a_short_span_and_describes_banfull():
    saved = clean_penalty({"enabled": True, "strikes": 5, "action": "banfull", "seconds": 10})
    assert saved["seconds"] == 35
    assert saved["enabled"] is True
    text = penalty_sentence({"enabled": True, "strikes": 5, "action": "mute", "seconds": 3600})
    assert "5" in text
    assert "мут" in text
    assert "1 час" in text
    kick = clean_penalty({"enabled": True, "strikes": 3, "action": "kick", "seconds": 3600})
    assert kick["seconds"] == 0
    assert "выключено" in penalty_sentence({"enabled": False, "strikes": 5, "action": "mute"})
