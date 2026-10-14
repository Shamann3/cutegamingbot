# -*- coding: utf-8 -*-
from group_money import page_bounds, shape_group, shape_totals


def test_page_stays_inside_a_readable_size():
    assert page_bounds(-5, 0) == (0, 1)
    assert page_bounds(40, 500) == (40, 80)


def test_totals_keep_every_pocket_separate():
    totals = shape_totals({
        "all_chat": 10000,
        "living_chat": 7000,
        "technical_chat": 3000,
        "all_dex": 50,
        "groups_with_cute": 12,
    }, 4)
    assert totals["allChat"] == 10000
    assert totals["livingChat"] == 7000
    assert totals["technicalChat"] == 3000
    assert totals["allDex"] == 50
    assert totals["groupsWithCute"] == 12
    assert totals["peopleWithCute"] == 4


def test_missing_people_count_stays_unknown():
    assert shape_totals({}, None)["peopleWithCute"] is None


def test_rank_follows_the_rich_to_poor_order():
    row = shape_group({
        "chat_id": -100, "name": "Клуб", "username": "club",
        "chat": 1, "dex": 0, "technical": False, "level": 2,
    }, 9)
    assert row["rank"] == 9
    assert row["chat"] == 1
    assert row["name"] == "Клуб"
