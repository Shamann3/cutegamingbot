# -*- coding: utf-8 -*-
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "py"))

from cases.design import (
    KEY_PREMIUM,
    average,
    button_owner,
    check_rules,
    find_target,
    key_text,
    match_bought,
    need_key_text,
    opened_text,
    public_case,
    roll_amount,
    stamp_callback,
)


def test_key_and_case_copy_use_the_given_premium_ids():
    key = key_text()
    need = need_key_text("small")
    assert KEY_PREMIUM in key
    assert "5379808153011502648" in need
    assert "<code>" in need
    assert "5927197049077372412" in need_key_text("large")
    assert "5375106250449100282" in need_key_text("mid")


def test_rules_keep_a_real_ceiling_and_no_fee_field():
    checked = check_rules("small", 50, [
        {"chance": 70, "amount": 10},
        {"chance": 30, "amount": 50},
    ])
    assert checked["max"] == 50
    assert "commission" not in checked
    try:
        check_rules("small", 40, [
            {"chance": 70, "amount": 10},
            {"chance": 30, "amount": 50},
        ])
    except ValueError as err:
        assert str(err) == "amount"
    else:
        raise AssertionError("amount above the ceiling was accepted")


def test_roll_reaches_the_ceiling_and_averages_below_it():
    rules = public_case(None, "large")
    rng = random.Random(3)
    draws = [roll_amount(rules["bands"], rng) for _ in range(5000)]
    assert max(draws) == rules["max"]
    assert sum(draws) / len(draws) < rules["max"] * 0.7
    assert average(rules["bands"]) < rules["max"]


def test_buttons_belong_to_the_opener():
    stamped = stamp_callback("cs:find:small", 42)
    assert button_owner(stamped) == 42
    assert find_target(stamped) == "small"
    assert button_owner("cs:find:small") is None


def test_jackpot_copy_names_the_ceiling():
    text = opened_text("mid", 70, 70)
    assert "70" in text
    quiet = opened_text("mid", 32, 70)
    assert "+32" in quiet


def test_purchase_maps_back_to_the_case():
    assert match_bought("case5000_15000", "other") == "small"
    assert match_bought("key", "Ключ") == "key"
    assert match_bought("watercraft", "Вода") == ""
