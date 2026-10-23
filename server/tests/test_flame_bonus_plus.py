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
    })
    assert conf["mult"] == 2
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


def test_copy_mentions_bigger_bonus_and_project_kuty():
    text = screen_intro(mult=2, kuty_lo=10, kuty_hi=30, items_on=True)
    assert "увеличенный бонус" in text.lower() or "Увеличенный" in text
    assert "10" in text and "30" in text
    assert "предмет" in text.lower()
    result = screen_result(board_kuty=12, extra_kuty=5, project_kuty=9, item_line="")
    assert "дополнительные куты от самого проекта" in result
    assert "30%" not in result
    assert "+12" in result or "12" in result
