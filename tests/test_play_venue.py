# -*- coding: utf-8 -*-
"""Выбор официальной площадки для игр."""
from bot.funcs.play_venue import PlayVenue, _pick_best, _rank_key


def test_pick_best_by_balance():
    a = PlayVenue(-1, "a", "A", balance=10, activity=100)
    b = PlayVenue(-2, "b", "B", balance=50, activity=1)
    assert _pick_best([a, b]) is b


def test_pick_best_tie_by_activity():
    a = PlayVenue(-1, "a", "A", balance=40, activity=10)
    b = PlayVenue(-2, "b", "B", balance=40, activity=99)
    assert _pick_best([a, b]) is b


def test_rank_stable_on_full_tie():
    a = PlayVenue(-100, "a", "A", balance=5, activity=5)
    b = PlayVenue(-200, "b", "B", balance=5, activity=5)
    # При полном равенстве — более отрицательный chat_id (через -chat_id).
    assert _rank_key(b) > _rank_key(a)
    assert _pick_best([a, b]) is b


def test_venue_ref_and_url():
    v = PlayVenue(-1001612636292, "CuteGamingChat", "Cute", balance=14, activity=1)
    assert v.ref == "@CuteGamingChat"
    assert v.open_url == "https://t.me/CuteGamingChat"
