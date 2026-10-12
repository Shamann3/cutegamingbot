# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "py"))

from datetime import datetime, timedelta, timezone

from water_games.design import (
    BTN_EXTEND,
    EXTEND_FEE,
    button_owner,
    button_rows,
    stamp_callback,
    strip_callback_owner,
    emoji_id,
    ITEMS,
    POOR_BALANCE,
    PRICES,
    SHOT_CAP,
    btn_join,
    can_shoot,
    kept_kind,
    guide_status,
    after_buy_text,
    hours_phrase,
    is_shield_off,
    is_water_ask,
    joined_until,
    left_phrase,
    public_group_name,
    screen_text,
    shield_mark,
    shield_profile_line,
    water_buy_kind,
    shields_in_bag,
    shop_can_take,
    stock_is_open,
    fee_group_name,
    normalize_fee_chat,
    pistol_is_blocked,
    pour_bounds,
    split_take,
    take_amount,
    take_one_item,
    towel_amount,
    wearing_text,
)


def test_pour_button_carries_premium_emoji():
    home = button_rows("home")[0][0]
    rules = button_rows("rules")[0][0]
    shoot = button_rows("splash_ready")[0][0]
    assert home["text"] == "Выстрелить"
    assert home["data"] == "wg:aim"
    assert home["emoji"] == shoot["emoji"] == "5317000922096769303"
    assert home["style"] == shoot["style"] == rules["style"] == "success"
    assert rules["text"] == "Выстрелить"
    assert rules["emoji"] == "5317000922096769303"
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
    assert not is_water_ask("снять защиту")
    assert is_shield_off("снять защиту")
    assert is_shield_off("Сними защиту пожалуйста")
    assert not is_shield_off("водные игры")
    stamped = stamp_callback("wg:off", 5)
    assert button_owner(stamped) == 5
    assert strip_callback_owner(stamped) == "wg:off"
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
    assert not stock_is_open(name1="pistoletik")
    assert not stock_is_open(name="Пистолетик")
    assert not stock_is_open(name1="watercraft")
    assert not stock_is_open(name="Вода")
    assert not stock_is_open(name1="dryumbrella")
    assert not stock_is_open(name="Зонтик")
    assert not stock_is_open(name1="drycoat")
    assert not stock_is_open(name1="drysafe")
    assert can_shoot("dryumbrella")
    assert not can_shoot("drycoat")
    assert not can_shoot("dryawning")
    assert not can_shoot("drysafe")
    assert kept_kind("drycoat", "dryumbrella") == "drycoat"
    assert kept_kind("dryumbrella", "dryumbrella") == "dryumbrella"
    assert kept_kind("dryumbrella", "drysafe") == "drysafe"
    assert shop_can_take(1, 5, name="Зонтик") == 1
    assert shop_can_take(1, 5, name="Пистолетик") == 1
    assert shop_can_take(3, 5, name="Вода") == 3
    assert shop_can_take(3, 5, name="Камень") == 3
    assert shop_can_take(0, 5, name="Зонтик") == 0
    text = screen_text("shield")
    assert "Дождевик" in text
    assert "Навес" in text
    assert "Сухой сейф" in text
    assert "Под ним можно стрелять" in text
    assert "5224681716760715555" in text
    assert "5388820858414313315" in text
    assert "5471952986970267163" in text
    assert "tg-emoji" not in shield_mark("dryawning")
    assert shield_mark("dryawning") == "🛖"
    shields = [row[0] for row in button_rows("shield")[:4]]
    assert [button["style"] for button in shields] == ["primary", "primary", "primary", "primary"]
    assert shields[0]["emoji"] == "5224681716760715555"
    assert shields[1]["emoji"] == "5388820858414313315"
    assert shields[2]["emoji"] == ""
    assert shields[3]["emoji"] == "5471952986970267163"
    note = wearing_text(emoji="☂️", name="Зонтик", left="2 часа", fee=100)
    assert "Зонтик" in note
    assert "Увеличить" in note
    assert "100" in note
    from water_games.design import choice_label, word
    assert choice_label(emoji="☂️", name="Зонтик", count=2, plus="+3 часа") == "☂️ Зонтик: 2 шт, +3 часа"
    assert "Ответьте" in screen_text("shot_reply")
    assert word("towel") == "Полотенце"
    assert word("towel_btn", amount="120") == "Полотенце +120"
    hit = screen_text("shot_hit", amount="600", towel="120", hours="3 часа")
    assert "600" in hit and "120" in hit and "3 часа" in hit
    assert "уже на балансе" in screen_text("towel_taken", amount="120")
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
    aim = screen_text("aim")
    assert "Дальше только Пистолетик" in aim
    assert "Использовать 🔫" in aim
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
    assert "Обливайте того, у кого кут больше" in broke
    assert "<code>топ</code>" in broke
    assert "Вода потрачена" in broke
    ask = screen_text("shot_ask", amount="120")
    assert "120" in ask
    assert "заберете" in ask
    guard = screen_text("shot_guard", mark="☂️", name="Зонтик", span="ещё 2 часа")
    assert "Под защитой ещё 2 часа" in guard
    assert "куты не будут заработаны" in guard
    assert "Вода при вас" in screen_text("shot_cancel")


def test_a_water_purchase_advances_only_its_own_message():
    text, step = after_buy_text(kind="pistoletik", emoji="🔫", name="Пистолетик", pistol=True, water=False)
    assert step == "water"
    assert "Отлично" in text
    assert "Осталась Вода" in text
    text, step = after_buy_text(kind="watercraft", emoji="💧", name="Вода", pistol=False, water=True)
    assert step == "pistol"
    assert "Остался Пистолетик" in text
    text, step = after_buy_text(kind="watercraft", emoji="💧", name="Вода", pistol=True, water=True)
    assert step == "shoot"
    assert "Использовать 🔫" in text
    text, step = after_buy_text(kind="dryumbrella", emoji="☂️", name="Зонтик", pistol=False, water=False)
    assert step == "wear"
    assert "инвентаре" in text
    assert water_buy_kind(name1="watercraft") == "watercraft"
    assert water_buy_kind(name="Вода") == "watercraft"
    assert water_buy_kind(name1="stone", name="Камень") == ""
    assert public_group_name("https://t.me/CuteChat") == "CuteChat"
    assert public_group_name("не адрес") == ""
    pistol_buy = button_rows("splash_need")[0][0]
    water_buy = button_rows("splash_need")[1][0]
    assert pistol_buy["text"] == "🔫 Найти пистолетик"
    assert pistol_buy["style"] == water_buy["style"] == "success"
    assert "Снимите лот" in screen_text("own_lot", emoji="🔫", name="Пистолетик")
    home = stamp_callback("wg:home", 42)
    assert home == "wg:home:42"
    assert button_owner(home) == 42
    assert strip_callback_owner(home) == "wg:home"
    assert button_owner("wg:pour:9:42") == 42
    assert strip_callback_owner("wg:pour:9:42") == "wg:pour:9"
    assert button_owner("wg:more:42") == 42
    assert strip_callback_owner("wg:more:42") == "wg:more:42"
    assert stamp_callback("wg:more:42", 99) == "wg:more:42"
    assert button_owner("wg:find:watercraft") is None
    assert button_owner(stamp_callback("wg:towel:3", 9)) == 9


def test_project_keeps_a_slice_of_the_take():
    assert split_take(80, 10) == (72, 8)
    assert split_take(40, 10) == (36, 4)
    assert split_take(1500, 10) == (1350, 150)
    assert split_take(80, 0) == (80, 0)
    assert split_take(80, 100) == (0, 80)
    note = screen_text("shot_fee", payout="72", fee="8", group="Игры")
    assert "Группе" in note and "Игры" in note
    assert pistol_is_blocked(10, on=False, limit=2) is False
    assert pistol_is_blocked(2, on=True, limit=2) is True
    assert pistol_is_blocked(1, on=True, limit=2) is False
    assert fee_group_name("-1004324787050") == "Игры"
    assert normalize_fee_chat("нет такой") == "-1004324787050"


def test_pour_bounds_follow_the_percent_and_the_ceiling():
    assert pour_bounds(1000, 4, 8, cap=1500, day_left=4000, poor=50) == (40, 80)
    assert pour_bounds(100_000, 4, 8, cap=1500, day_left=4000, poor=50) == (1500, 1500)
    assert pour_bounds(40, 4, 8, cap=1500, day_left=4000, poor=50) == (0, 0)
    assert pour_bounds(1000, 4, 8, cap=1500, day_left=30, poor=50) == (30, 30)


def test_poor_balance_is_not_taken_and_a_shot_has_a_ceiling():
    assert take_amount(POOR_BALANCE - 1, 8, cap=SHOT_CAP, day_left=SHOT_CAP) == 0
    assert take_amount(10_000, 8, cap=SHOT_CAP, day_left=SHOT_CAP) == 800
    assert take_amount(1_000_000, 8, cap=SHOT_CAP, day_left=SHOT_CAP) == SHOT_CAP
    assert take_amount(10_000, 8, cap=SHOT_CAP, day_left=100) == 100
    assert towel_amount(1000) == 200
