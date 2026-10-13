# -*- coding: utf-8 -*-
from datetime import timedelta

from bot.funcs.group_door import (
    DAY,
    GRACE,
    action_blocked,
    banner_html,
    block_text,
    classify_door,
    day1_text,
    day2_text,
    deposit_note,
    human_left,
    may_seize,
    next_step,
    public_username,
    recovered_text,
    seize_text,
    split_pots,
    start_text,
    sweep_batch,
)


def test_open_door_needs_username_and_no_requests():
    assert classify_door("CuteGamingChat", False)["open"] is True
    closed = classify_door("CuteGamingChat", True)
    assert closed["open"] is False
    assert closed["reasons"] == ["requests"]
    private = classify_door("username отсутствует", False)
    assert private["open"] is False
    assert private["reasons"] == ["private"]
    both = classify_door("", True)
    assert both["reasons"] == ["private", "requests"]
    assert public_username("ab") is None
    assert public_username("@CuteGamingChat") == "CuteGamingChat"


def test_clock_warns_before_it_takes():
    assert next_step(timedelta(0), 0, False) == "start"
    assert next_step(DAY, 1, True) == "day1"
    assert next_step(DAY * 2, 2, True) == "day2"
    assert next_step(GRACE, 3, True) == "seize"
    assert may_seize(False, GRACE) is False
    assert may_seize(True, GRACE - timedelta(minutes=1)) is False
    assert may_seize(True, GRACE) is True


def test_sweep_keeps_running_clocks_and_walks_past_one_page():
    ids, wrapped = sweep_batch([-100, -50], [-100, -40, -30], 3)
    assert ids == [-100, -50, -40, -30]
    assert wrapped is False
    small, done = sweep_batch([], [-9], 3)
    assert small == [-9]
    assert done is True


def test_pots_cover_the_whole_sum():
    parts = split_pots(10, [1, 2, 3, 4])
    assert sum(part for _, part in parts) == 10
    assert [part for _, part in parts] == [3, 3, 2, 2]
    assert split_pots(0, [1]) == []


def test_texts_name_the_rule_and_stay_distinct():
    reasons = ["requests", "private"]
    start = start_text(reasons, 1500)
    later = day1_text(reasons, 1500)
    last = day2_text(reasons, 1500)
    gone = seize_text(reasons, 1500, None, warned=3)
    play = block_text("play", reasons, 1500, "3 дня")
    withdraw = block_text("withdraw", reasons, 1500, "2 дня")
    note = deposit_note(reasons, 1500, "2 дня")
    board = banner_html(reasons, 1500, human_left(GRACE))
    opened = recovered_text("CuteGamingChat")
    blob = "\n".join([start, later, last, gone, play, withdraw, note, board, opened])
    assert "tg-emoji" in blob
    assert "5355076502960520182" in start
    assert "5355148005576058505" in start
    assert "5357287178462346359" in start
    assert "5357421327470866510" in start
    assert "<blockquote>" in start
    assert "5357319626940261522" in later
    assert "5357162761849717032" in play
    assert "5357287178462346359" in withdraw
    assert action_blocked("deposit") is False
    assert action_blocked("play") is True
    assert action_blocked("withdraw") is True
    assert len({start, later, last, gone, play, withdraw, note, board, opened}) == 9
    assert "3" in start
    assert "1.500" in start
    assert human_left(GRACE).startswith("3")
