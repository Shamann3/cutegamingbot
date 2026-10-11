# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "py"))

from datetime import datetime, timedelta, timezone

from water_games.design import (
    BTN_EXTEND,
    EXTEND_FEE,
    button_rows,
    emoji_id,
    ITEMS,
    POOR_BALANCE,
    PRICES,
    SHOT_CAP,
    btn_join,
    can_shoot,
    kept_kind,
    guide_status,
    hours_phrase,
    is_water_ask,
    joined_until,
    left_phrase,
    screen_text,
    shield_profile_line,
    shields_in_bag,
    shop_can_take,
    stock_is_open,
    take_amount,
    take_one_item,
    towel_amount,
    wearing_text,
)


def test_pour_button_carries_premium_emoji():
    home = button_rows("home")[0][0]
    rules = button_rows("rules")[0][0]
    assert home["text"] == "Облить"
    assert rules["text"] == "Облить"
    assert home["emoji"] == rules["emoji"] == "5354820836442287981"
    assert emoji_id("5354820836442287981") == "5354820836442287981"
    assert emoji_id("gun") == ""
    assert button_rows("home")[1][0]["emoji"] == "5895483165182529286"
    assert button_rows("home")[2][0]["emoji"] == ""


def test_any_short_question_opens_water_games():
    assert is_water_ask("Водные игры")
    assert is_water_ask("что такое водные игры?")
    assert is_water_ask("как облить человека")
    assert is_water_ask("водный пистолет")
    assert not is_water_ask("облить водой")
    assert not is_water_ask("привет как дела на ферме сегодня вечером и завтра тоже")


def test_water_items_have_their_own_shop_shelf():
    server = Path(__file__).resolve().parents[1] / "server"
    sys.path.insert(0, str(server))
    from shop_catalog import WATER_SHELF, sorting_for_category_id
    assert sorting_for_category_id("sort_water") == WATER_SHELF == "🔫"


def test_umbrella_costs_sixty_and_is_not_a_limited_shelf():
    assert PRICES["dryumbrella"] == 60
    assert PRICES["drycoat"] == 180
    assert PRICES["dryawning"] == 300
    assert PRICES["drysafe"] == 10000
    assert EXTEND_FEE == 100
    assert btn_join() == "Улучшить за 100 кут"
    assert BTN_EXTEND == "Увеличить"
    assert PRICES["pistoletik"] == 100
    water = next(item for item in ITEMS if item["name1"] == "watercraft")
    assert water["name"] == "Вода"
    assert "price" not in water
    seeded = [item["name1"] for item in ITEMS if "price" in item]
    assert seeded == [
        "pistoletik",
        "dryumbrella",
        "drycoat",
        "dryawning",
        "drysafe",
    ]
    assert stock_is_open(name1="pistoletik")
    assert stock_is_open(name="Пистолетик")
    assert not stock_is_open(name1="watercraft")
    assert not stock_is_open(name="Вода")
    assert stock_is_open(name1="dryumbrella")
    assert stock_is_open(name="Зонтик")
    assert stock_is_open(name1="drycoat")
    assert stock_is_open(name="Дождевик")
    assert stock_is_open(name1="dryawning")
    assert stock_is_open(name="Навес")
    assert stock_is_open(name1="drysafe")
    assert stock_is_open(name="Сухой сейф")
    assert can_shoot("dryumbrella")
    assert not can_shoot("drycoat")
    assert not can_shoot("dryawning")
    assert not can_shoot("drysafe")
    assert kept_kind("drycoat", "dryumbrella") == "drycoat"
    assert kept_kind("dryumbrella", "dryumbrella") == "dryumbrella"
    assert kept_kind("dryumbrella", "drysafe") == "drysafe"
    assert shop_can_take(1, 5, name="Зонтик") == 5
    assert shop_can_take(1, 5, name="Пистолетик") == 5
    assert shop_can_take(3, 5, name="Вода") == 3
    assert shop_can_take(3, 5, name="Камень") == 3
    assert shop_can_take(0, 5, name="Зонтик") == 0
    text = screen_text("shield", fee=EXTEND_FEE)
    assert "100" in text
    assert "Дождевик" in text
    assert "Навес" in text
    assert "Сухой сейф" in text
    assert "только под зонтиком" in text or "Под ним можно стрелять" in text
    assert "половину" in text
    note = wearing_text(emoji="☂️", name="Зонтик", left="2 часа", fee=100)
    assert "Зонтик" in note
    assert "Увеличить" in note
    assert "100" in note
    from water_games.design import choice_label, word
    assert choice_label(emoji="☂️", name="Зонтик", count=2, plus="+3 часа") == "☂️ Зонтик: 2 шт, +3 часа"
    assert "Ответьте" in screen_text("shot_reply")
    assert word("towel") == "Полотенце"
    assert "Вода при вас" in screen_text("shot_day")


def test_a_second_umbrella_adds_its_hours_to_the_time_left():
    now = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    current = now + timedelta(hours=2, minutes=14)
    nxt = joined_until(current, 3, now)
    assert nxt == now + timedelta(hours=5, minutes=14)
    assert joined_until(current, None, now) is None
    assert hours_phrase(3) == "3 часа"
    assert hours_phrase(72) == "3 дня"
    assert left_phrase(2 * 3600 + 14 * 60) == "2 часа 14 минут"
    bag = shields_in_bag({"Зонтик": 2, "Вода": 4})
    assert [row["name1"] for row in bag] == ["dryumbrella"]
    assert bag[0]["count"] == 2
    left, ok = take_one_item({"Зонтик": 1}, "Зонтик")
    assert ok and "Зонтик" not in left


def test_guide_names_what_is_missing_and_profile_keeps_the_time_left():
    empty = guide_status(pistol=0, water=0, shield_line="Защиты нет. Вас можно облить.")
    assert "нет. Кнопка ниже откроет покупку" in empty
    assert "Можно нажимать" not in empty
    ready = guide_status(pistol=1, water=2, shield_line="Защиты нет. Вас можно облить.")
    assert "есть, 1 шт." in ready
    assert "есть, 2 шт." in ready
    assert "Можно нажимать" in ready
    timed = shield_profile_line(emoji="☂️", name="Зонтик", forever=False, left="2 часа", shoot=True)
    assert "Под защитой от ограблений" in timed
    assert "ещё 2 часа" in timed
    assert "Стрелять можно." in timed
    forever = shield_profile_line(emoji="💎", name="Сухой сейф", forever=True, left="", shoot=False)
    assert "навсегда" in forever
    assert "ещё" not in forever
    assert "Стрелять нельзя." in forever
    private = screen_text("shot_private")
    assert "Пистолетик и вода уже есть" in private
    assert "по кнопке" in private
    broke = screen_text("shot_broke", poor=POOR_BALANCE)
    assert "Обливайте того, у кого кут больше." in broke
    assert "<code>топ</code>" in broke
    assert "Вода потрачена" in broke


def test_poor_balance_is_not_taken_and_a_shot_has_a_ceiling():
    assert take_amount(POOR_BALANCE - 1, 8, cap=SHOT_CAP, day_left=SHOT_CAP) == 0
    assert take_amount(10_000, 8, cap=SHOT_CAP, day_left=SHOT_CAP) == 800
    assert take_amount(1_000_000, 8, cap=SHOT_CAP, day_left=SHOT_CAP) == SHOT_CAP
    assert take_amount(10_000, 8, cap=SHOT_CAP, day_left=100) == 100
    assert towel_amount(1000) == 200
