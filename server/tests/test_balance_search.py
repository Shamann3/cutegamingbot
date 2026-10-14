# -*- coding: utf-8 -*-
from balance_search import (
    contains_pattern,
    money_card,
    plain_query,
    prefix_pattern,
    query_user_id,
)


def test_query_keeps_the_name_and_drops_the_at_sign():
    assert plain_query("  @Cute_Name  ") == "Cute_Name"
    assert query_user_id("8103474410") == 8103474410
    assert query_user_id("cute") is None


def test_like_patterns_do_not_treat_signs_as_wildcards():
    assert contains_pattern("100%") == "%100\\%%"
    assert prefix_pattern("a_b") == "a\\_b%"


def test_personal_and_group_cute_stay_apart():
    card = money_card(1500, [
        {"chatId": 2, "name": "Малая", "chat": 1, "dex": 0},
        {"chatId": 1, "name": "Большая", "username": "big", "chat": 8000, "dex": 40, "creator": True},
        {"chatId": 3, "name": "Пустая", "chat": 0, "dex": 0},
        {"chatId": 1, "name": "Большая ещё раз", "chat": 8000, "dex": 40},
    ])
    assert card["personal"] == 1500
    assert card["groupsChat"] == 8001
    assert card["groupsDex"] == 40
    assert [row["chatId"] for row in card["groups"]] == [1, 2]
    assert card["groups"][0]["creator"] is True
    assert card["personal"] != card["groupsChat"]
