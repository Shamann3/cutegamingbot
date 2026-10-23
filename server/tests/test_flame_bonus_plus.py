# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flame_bonus_plus import board_range, gift_plus_defaults, roll_extra_bundle
from flame_bonus_plus_copy import screen_intro, screen_result


def test_defaults_and_board_range():
    conf = gift_plus_defaults({
        "gift_enabled": True,
        "gift_mult": 2,
        "gift_kuty_min": 10,
        "gift_kuty_max": 20,
        "gift_item_count": 3,
    })
    assert conf["mult"] == 2
    assert conf["item_count"] == 3
    assert board_range(conf) == (20, 40)


def test_extra_can_request_item_and_kuty_independently():
    conf = gift_plus_defaults({
        "gift_extra_kuty_on": True,
        "gift_extra_kuty_chance": 100,
        "gift_extra_kuty_min": 7,
        "gift_extra_kuty_max": 7,
        "gift_item_on": True,
        "gift_item_chance": 100,
        "drops": [
            {"kind": "item", "item_name": "Купон", "weight": 1},
            {"kind": "item", "item_name": "Вода", "weight": 1},
        ],
    })
    hit = False
    for _ in range(40):
        bundle = roll_extra_bundle(conf)
        if bundle["extra_kuty"] == 7 and bundle["want_item"] and "Купон" in bundle["item_names"]:
            hit = True
            break
    assert hit


def test_multi_item_slots_without_duplicate_preferred():
    conf = gift_plus_defaults({
        "gift_item_on": True,
        "gift_item_chance": 100,
        "gift_item_count": 2,
        "gift_extra_kuty_on": False,
        "drops": [
            {"kind": "item", "item_name": "Купон", "weight": 100},
            {"kind": "item", "item_name": "Вода", "weight": 100},
        ],
    })
    bundle = roll_extra_bundle(conf)
    assert bundle["want_item"] is True
    assert len(bundle["item_picks"]) == 2
    preferred = [picks[0] for picks in bundle["item_picks"]]
    assert len(set(preferred)) == 2


def test_copy_mentions_bigger_bonus_and_project_kuty():
    text = screen_intro(mult=2, kuty_lo=10, kuty_hi=30, items_on=True, item_count=2)
    assert "Бонус +" in text
    assert "10" in text and "30" in text
    assert "2" in text
    result = screen_result(
        board_kuty=12,
        extra_kuty=5,
        project_kuty=9,
        item_lines=["Вам: <code>🎁</code> <b>Купон</b>", "Вам: <code>💧</code> <b>Вода</b>"],
    )
    assert "дополнительные куты от проекта" in result.lower() or "Дополнительные куты от проекта" in result
    assert "30%" not in result
    assert "+12" in result or "12" in result
    assert "Купон" in result and "Вода" in result


def test_empty_result_is_honest():
    text = screen_result(board_kuty=0, extra_kuty=0, project_kuty=0, item_lines=[])
    assert "наградить нечем" in text.lower() or "нечем" in text.lower()
