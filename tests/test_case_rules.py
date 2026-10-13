# -*- coding: utf-8 -*-
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "py"))

from cases.design import (
    average,
    button_owner,
    check_rules,
    find_target,
    guide_home,
    guide_how,
    is_case_ask,
    HOW_ICON,
    KEY_PREMIUM,
    NEED_KEY_PREMIUM,
    buy_label,
    key_text,
    match_bought,
    open_label,
    need_key_text,
    owns,
    ready_open_text,
    opened_text,
    public_case,
    roll_amount,
    stamp_callback,
    closed_text,
    take_plan,
)


def test_key_and_case_copy_use_the_given_premium_ids():
    key = key_text()
    need = need_key_text("small")
    assert KEY_PREMIUM == "5330115548900501467"
    assert KEY_PREMIUM in key
    assert KEY_PREMIUM in need
    assert "5379808153011502648" in need
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


def test_case_words_open_the_guide():
    opened = (
        "кейсы",
        "кейс",
        "кейсик",
        "кейсики",
        "открыть кейс",
        "открыть кейсы",
        "Открой кейс",
        "откройте, пожалуйста, кейс",
        "открывай кейсы",
        "как открыть кейс?",
        "как мне открыть кейс",
        "кейс как открыть",
        "  открытие кейсов ",
        "хочу открыть кейс",
        "где кейсы",
        "как работают кейсы",
        "что такое кейс",
        "хелп кейсы",
        "help cases",
        "как пользоваться кейсом",
        "использовать кейс",
        "инструкция по кейсам",
        "как купить кейс",
        "подскажи как открыть кейсик",
    )
    for phrase in opened:
        assert is_case_ask(phrase), phrase
    closed = (
        "привет",
        "использовать 📦",
        "использовать 🔑",
        "использовать маленький кейс",
        "использовать ключ",
        "баланс",
        "водные игры",
        "как открыть магазин",
        "у меня сегодня был странный день и я видел чемодан далеко от дома вечером",
    )
    for phrase in closed:
        assert not is_case_ask(phrase), phrase
    home = guide_home(has_key=True, held=[])
    assert "Нужен кейс" in home
    how = guide_how([50, 70, 170])
    assert "<code>использовать 📦</code>" in how
    assert "до <b>170</b>" in how
    waiting = guide_home(has_key=False, held=[{"emoji": "📦"}])
    assert NEED_KEY_PREMIUM in waiting
    assert "Нужен ключ" in waiting
    assert buy_label("Маленький кейс") == "Купить маленький кейс"
    assert buy_label("Ключ") == "Купить ключ"
    assert open_label("Большой кейс") == "Открыть большой кейс"
    assert HOW_ICON == "5357371226677359435"
    assert button_owner(stamp_callback("cs:go:shop-4", 9)) == 9
    assert button_owner("cs:go:shop-4") is None
    desk = (Path(__file__).resolve().parents[1] / "bot" / "funcs" / "case_desk.py").read_text(encoding="utf-8")
    assert "_guide_button(\"Назад\", where, user_id, \"\")" in desk
    assert "Открыть покупку" not in desk
    assert "личные сообщения" not in desk
    assert "Эта кнопка не ваша" in desk
    stamped = stamp_callback("cs:guide:how", 7)
    assert button_owner(stamped) == 7


def test_ready_case_is_one_command_and_no_button_copy():
    from cases.design import case_by_id
    small = case_by_id("small")
    text = ready_open_text([small])
    assert "<code>использовать 📦</code>" in text
    assert "Можно открыть" in text
    assert owns({"Маленький кейс": 1}, small)
    assert owns({"4": 1}, small, 4)
    assert not owns({"Ключ": 1}, small)


def test_shop_lists_the_key_before_the_cases():
    from cases.design import shop_items
    names = [item["name1"] for item in shop_items()]
    assert names == ["key", "case5000_15000", "case20000_40000", "case50000_100000"]
    text = (Path(__file__).resolve().parents[1] / "server" / "panel_access.py").read_text(encoding="utf-8")
    assert '"id": "cases"' in text


def test_prize_is_taken_from_technical_groups():
    groups = [
        {"id": 1, "balance": 10},
        {"id": 2, "balance": 40},
        {"id": 3, "balance": 0},
    ]
    assert take_plan(groups, 45) == [{"id": 2, "take": 40}, {"id": 1, "take": 5}]
    assert take_plan(groups, 100) is None
    assert take_plan(groups, 0) == []
    paused = closed_text()
    assert "подождать" in paused
    assert button_owner(stamp_callback("cs:open:small", 7)) == 7
    home = guide_home(has_key=True, held=[{"emoji": "x"}], open_now=False)
    assert "подождать" in home
    back = stamp_callback("cs:find:small:how", 7)
    assert find_target(back) == "small"
    assert button_owner(back) == 7


def test_purchase_maps_back_to_the_case():
    assert match_bought("case5000_15000", "other") == "small"
    assert match_bought("key", "Ключ") == "key"
    assert match_bought("watercraft", "Вода") == ""
