# -*- coding: utf-8 -*-
from balance_ledger import split_pots


def test_pots_keep_players_apart_from_the_project():
    pots = split_pots(1000, 400, 50, 200, 25)
    assert pots["users"] == 1000
    assert pots["groups"] == 450
    assert pots["project"] == 225
    assert pots["system"] == 1675
    assert pots["allBalances"] == 1600


def test_pots_drop_negative_pockets():
    pots = split_pots(-5, None, "no", 10, 0)
    assert pots["users"] == 0
    assert pots["groups"] == 0
    assert pots["project"] == 10
    assert pots["system"] == 10
