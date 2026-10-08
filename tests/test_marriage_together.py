from datetime import date, datetime, timedelta, timezone
from bot.funcs.marriage_design import quiet_wish
from bot.funcs.marriage_rules import (
    award_plan, care_code, classify, due_period, fund_split, quiet_effect,
    quiet_pay, remember_wish, reply_care_amount, reply_spark_line, settings_view,
    settle_spark, together_label,
)

def test_goodnight_is_quiet_and_a_longer_line_is_not_a_gesture():
    assert quiet_wish("доброй ночи")
    assert quiet_wish("  Спокойной   ночи ")
    assert not quiet_wish("ладно спокойной ночи")
    night = classify("доброй ночи")
    assert night["kind"] == "rp" and night["rp"]["id"] == "night"
    assert classify("Ладно спокойной ночи") is None

def test_together_label_uses_fine_units():
    msk = timezone(timedelta(hours=3))
    now = datetime(2026, 10, 7, 12, 0, tzinfo=msk)
    assert together_label(now, now) == "сегодня"
    assert "секунд" in together_label(now - timedelta(seconds=5), now)
    assert "час" in together_label(now - timedelta(hours=3), now)
    assert "недел" in together_label(now - timedelta(days=14), now)
    assert together_label(now - timedelta(days=183), now) == "полгода"
    assert together_label(now - timedelta(days=365), now) == "год"
    assert together_label(now - timedelta(days=548), now) == "полтора года"

def test_spark_day_needs_both_replies_only_when_talks_are_tracked():
    msk = timezone(timedelta(hours=3))
    morning = datetime(2026, 10, 7, 10, 0, tzinfo=msk)
    base = {"spark_days": 2, "spark_day": date(2026, 10, 6), "care_payer": 5, "care_partner": 5, "talk_payer": date(2026, 10, 6), "talk_partner": date(2026, 10, 6)}
    assert settle_spark(base, morning, 12)["state"]["spark_days"] == 3
    missed = dict(base)
    missed["talk_partner"] = None
    fading = settle_spark(missed, morning, 12)
    assert fading["fading"] and fading["state"]["spark_days"] == 2
    bare = {"spark_days": 2, "spark_day": date(2026, 10, 6), "care_payer": 5, "care_partner": 5}
    assert settle_spark(bare, morning, 12)["state"]["spark_days"] == 3

def test_spare_pays_the_next_days_until_the_share_runs_out():
    msk = timezone(timedelta(hours=3))
    morning = datetime(2026, 10, 8, 10, 0, tzinfo=msk)
    farmed = settle_spark({
        "spark_days": 0,
        "spark_day": date(2026, 10, 1),
        "care_payer": 100,
        "care_partner": 100,
        "talk_payer": date(2026, 10, 1),
        "talk_partner": None,
    }, morning, 12)
    assert farmed["state"]["spark_days"] == 7
    assert farmed["state"]["spark_day"] == date(2026, 10, 8)
    assert farmed["state"]["care_payer"] == 53
    assert farmed["state"]["care_partner"] == 53
    assert farmed["level"]["name"] == "Близость"
    assert not farmed["fading"]
    exact = {
        "spark_days": 2,
        "spark_day": date(2026, 10, 6),
        "care_payer": 5,
        "care_partner": 5,
        "talk_payer": date(2026, 10, 6),
        "talk_partner": None,
    }
    assert settle_spark(exact, morning.replace(day=7), 12)["fading"]
    paid = settle_spark(exact, datetime(2026, 10, 7, 13, 0, tzinfo=msk), 12)
    assert paid["state"]["spark_days"] == 3
    assert paid["state"]["care_payer"] == 0
    assert paid["state"]["spark_day"] == date(2026, 10, 7)
    ahead = settle_spark({
        "spark_days": 2,
        "spark_day": date(2026, 10, 6),
        "care_payer": 6,
        "care_partner": 6,
        "talk_payer": None,
        "talk_partner": None,
    }, morning.replace(day=7), 12)
    assert ahead["state"]["spark_days"] == 3
    assert ahead["state"]["care_payer"] == 1
    coat = settle_spark({
        "spark_days": 3,
        "spark_day": date(2026, 10, 6),
        "care_payer": 8,
        "care_partner": 1,
        "shield": 1,
    }, datetime(2026, 10, 7, 13, 0, tzinfo=msk), 12)
    assert coat["state"]["spark_days"] == 3 and coat["state"]["shield"] == 0
    assert coat["state"]["care_payer"] == 8 and coat["state"]["care_partner"] == 1

def test_reply_writes_once_when_two_sparks_remain_and_stays_quiet_after():
    assert reply_care_amount("ок", 1, 3, 4) == 1
    assert reply_care_amount("я рядом с тобой сегодня", 1, 3, 4) == 3
    line = "Поддержал отношения с Анна"
    assert reply_spark_line(2, 3, 5, 2, "Анна", "", line) == line
    assert reply_spark_line(0, 3, 5, 2, "Анна", "", line) == line
    assert reply_spark_line(1, 4, 5, 2, "Анна", "", line) == line
    assert reply_spark_line(3, 4, 5, 2, "Анна", "", line) == ""
    assert reply_spark_line(4, 5, 5, 2, "Анна", "", line) == ""
    assert reply_spark_line(5, 6, 5, 2, "Анна", "", line) == ""
    assert reply_spark_line(4, 5, 5, 2, "Анна", "Закрыл день с {name}", line) == "Закрыл день с Анна"
    view = settings_view({})
    assert view["replyCare"] == 1 and view["replyWarm"] == 3 and view["replyAlmost"] == 2
    assert view["replyDone"] == "" and "{name}" in view["replyAlmostText"]
    assert view["giftFundChat"] == -1004440027555
    assert view["premiumKeeper"] == "JerichoCute"
    assert settings_view({"giftFundChat": "нет", "premiumKeeper": "@JerichoCute"})["premiumKeeper"] == "JerichoCute"
    assert settings_view({"giftFundChat": 5})["giftFundChat"] == -1004440027555

def test_quiet_day_funds_the_gift_pool_and_a_holiday_waits_for_both():
    split = fund_split(40, 20, 10)
    assert split["fund"] == 7 and split["keep"] == 1 and split["project"] == 33
    pay = quiet_pay("Тихий день", 40, {})
    assert pay["chat"] == -1004440027555 and pay["fund"] == 7
    assert quiet_pay("Блик брака", 12, {}) is None
    today = date(2026, 10, 8)
    assert quiet_effect(2, 5, None, today)["care"] == 3
    assert quiet_effect(2, 5, date(2026, 10, 6), today)["reason"] == "week"
    assert quiet_effect(5, 5, None, today)["reason"] == "full"
    assert due_period(30, "7,14")["day"] == 30
    assert due_period(6, "") is None
    same = remember_wish("envelope", "", "partner", "envelope")
    assert same["locked"] == "envelope"
    assert remember_wish("envelope", "", "partner", "care")["locked"] == ""
    assert care_code(7) == "mrgglow" and care_code(100) == "mrghearth"
    assert award_plan("envelope", 20, 0, 0, 15, 0)["do"] == "kut"
    assert award_plan("care", 100, 12, 3, 15, 0)["do"] == "shop"
    assert award_plan("care", 9, 12, 0, 15, 0)["do"] == "sorry"
    assert award_plan("premium3", 100, 50, 2, 15, 0)["do"] == "keeper"
    assert award_plan("premium3", 10, 50, 2, 15, 0)["do"] == "keeper_empty"
    view = settings_view({})
    assert view["quietPrice"] == 40 and len(view["prizes"]) == 5 and view["periods"][0]["name"] == "Первая неделя"

def test_twenty_items_each_do_something_different():
    from bot.funcs.marriage_rules import act_plan, dawn_up, gift_catalog, moon_up, quiet_row
    view = settings_view({})
    catalog = gift_catalog(view)
    quiet = quiet_row(view)
    assert len(catalog) == 21
    assert len({row["emoji"] for row in catalog}) == 21
    assert quiet["emoji"] not in {row["emoji"] for row in catalog}
    effects = {row["id"]: row["effect"] for row in catalog}
    assert effects["glow"] == "self" and effects["tulip"] == "other" and effects["honey"] == "both"
    assert effects["moon"] == "norm" and effects["dawn"] == "dawn" and effects["match"] == "gap"
    assert effects["vow"] == "vow" and effects["ribbon"] == "mark"
    assert effects["propose"] == "propose" and effects["band"] == "ring"
    assert effects["seedcuke"] == "seed" and effects["cuke"] == "pantry" and effects["salad"] == "both"
    by = {row["id"]: row for row in catalog}
    seed_row = next(row for row in view["shelf"] if row["id"] == "seedcuke")
    assert by["seedcuke"]["price"] == 15 and by["seedcuke"]["on"] is True and seed_row["growMin"] == 30
    assert seed_row["waters"] == 3 and by["cuke"]["on"] is False and by["salad"]["on"] is False
    assert by["juice"]["care"] == 8 and by["soup"]["care"] == 12 and by["salad"]["care"] == 15
    from bot.funcs.marriage_rules import place_hint
    farm = place_hint("mrgseedtom")
    assert farm["where"] == "farm" and "ферме" in farm["text"]
    assert place_hint("mrgcab")["where"] == "craft"
    assert place_hint("mrgglow") is None
    seed = act_plan("seed")
    assert seed["ok"] is False and seed["reason"] == "field"
    veg = act_plan("pantry")
    assert veg["ok"] is False and veg["reason"] == "cook"
    meal = act_plan("both", amount=15)
    assert meal["ok"] and meal["add_you"] == 15 and meal["add_other"] == 15
    asked = act_plan("propose")
    assert asked["ok"] and asked["bond"] == "propose" and asked["set_proposer"]
    assert act_plan("propose", bond="propose")["reason"] == "said"
    assert act_plan("ring")["reason"] == "wait"
    assert act_plan("ring", bond="propose")["reason"] == "giver"
    given = act_plan("ring", bond="propose", is_proposer=True)
    assert given["ok"] and given["bond"] == "family" and given["transfer"]
    assert act_plan("ring", bond="family")["reason"] == "kept"
    assert act_plan("ring", bond="family", is_proposer=True)["reason"] == "home"
    custom = settings_view({"shelf": [{
        "id": "ownlamp01", "custom": True, "name": "Лампа", "emoji": "💡",
        "effect": "self", "price": 9, "care": 2, "line": "Свет на столе.",
    }]})
    lamp = next(row for row in custom["shelf"] if row["id"] == "ownlamp01")
    assert lamp["name1"] == "mrgownlamp01" and lamp["care"] == 2 and lamp["line"] == "Свет на столе."
    renamed = settings_view({"shelf": [{"id": "glow", "name": "Искорка", "emoji": "✨"}]})
    glow = next(row for row in renamed["shelf"] if row["id"] == "glow")
    assert glow["name"] == "Искорка" and glow["emoji"] == "✨" and glow["effect"] == "self"
    tuned = settings_view({"shelf": [{"id": "tulip", "price": 7, "care": 2}], "candlePrice": 40})
    tulip = next(row for row in tuned["shelf"] if row["id"] == "tulip")
    assert tulip["price"] == 7 and tulip["care"] == 2 and tuned["candlePrice"] == 40
    assert act_plan("other", amount=5)["add_other"] == 5
    both = act_plan("both", amount=4)
    assert both["add_you"] == 4 and both["add_other"] == 4
    assert act_plan("norm", need=11, night=True)["add_you"] == 11
    assert act_plan("norm", you=4, need=11, night=True)["add_you"] == 7
    assert act_plan("norm", you=11, need=11, night=True)["reason"] == "done"
    assert act_plan("norm", need=11)["reason"] == "night"
    msk = timezone(timedelta(hours=3))
    assert moon_up(datetime(2026, 10, 8, 21, 0, tzinfo=msk))
    assert moon_up(datetime(2026, 10, 8, 2, 0, tzinfo=msk))
    assert moon_up(datetime(2026, 10, 8, 5, 59, tzinfo=msk))
    assert not moon_up(datetime(2026, 10, 8, 6, 0, tzinfo=msk))
    assert not moon_up(datetime(2026, 10, 8, 20, 59, tzinfo=msk))
    assert act_plan("dawn", fading=False, amount=6, morning=True)["reason"] == "late"
    assert act_plan("dawn", fading=True, amount=6, morning=True)["add_you"] == 6
    assert act_plan("dawn", fading=True, amount=6)["reason"] == "sun"
    assert dawn_up(datetime(2026, 10, 8, 6, 0, tzinfo=msk))
    assert dawn_up(datetime(2026, 10, 8, 9, 59, tzinfo=msk))
    assert not dawn_up(datetime(2026, 10, 8, 5, 59, tzinfo=msk))
    assert not dawn_up(datetime(2026, 10, 8, 10, 0, tzinfo=msk))
    assert act_plan("vow", you=2, need=5, you_spoke=False)["reason"] == "silent"
    spoken = act_plan("vow", you=2, need=5, you_spoke=True)
    assert spoken["add_you"] == 3 and spoken["vow"]
    assert act_plan("vow", you=5, need=5, you_spoke=True)["vow"]
    assert act_plan("vow", you=5, need=5, you_spoke=True)["add_you"] == 0
    assert act_plan("vow", you=2, need=5, you_spoke=True, vow_used=True)["reason"] == "sworn"
    assert act_plan("mark", ribbon=True)["reason"] == "worn"
    msk = timezone(timedelta(hours=3))
    held = settle_spark({
        "spark_days": 3, "spark_day": date(2026, 10, 6),
        "care_payer": 8, "care_partner": 1, "shield": 1,
    }, datetime(2026, 10, 7, 13, 0, tzinfo=msk), 12)
    assert held["state"]["spark_days"] == 3 and held["state"]["shield"] == 0
    assert held["state"]["spark_day"] == date(2026, 10, 7) and held["lost"] == 0
    clock = settle_spark({
        "spark_days": 3, "spark_day": date(2026, 10, 6),
        "care_payer": 8, "care_partner": 1, "fade_extra": 6,
    }, datetime(2026, 10, 7, 13, 0, tzinfo=msk), 12)
    assert clock["fading"] and clock["clock"] == "18:00" and clock["state"]["spark_days"] == 3

def test_each_level_feels_further_along_and_items_are_things():
    from bot.funcs.marriage_rules import gift_catalog, level_of, spark_home
    early, late = level_of(0)["life"], level_of(365)["life"]
    assert "узнаёте" in early and "спокойно" in late and early != late
    assert "привычкой" in level_of(3)["life"]
    assert "свой тон" in level_of(14)["life"]
    assert "без объяснений" in level_of(60)["life"]
    home = spark_home("А", "Б", "две недели", "", {
        "level": level_of(14), "need": 15, "lost": 0,
        "state": {"spark_days": 14}, "both_done": False,
    }, 1, 1, "Б")
    assert "свой тон" in home
    dead = spark_home("А", "Б", "день", "", {
        "level": level_of(0), "need": 5, "lost": 12, "state": {"spark_days": 0},
    }, 0, 0, "Б")
    assert "не чужие" in dead and "12 дней" in dead
    catalog = gift_catalog(settings_view({}))
    assert all(row.get("touch") and " " in row.get("line", "") for row in catalog)
    assert "в руке" in next(row["line"] for row in catalog if row["id"] == "glow")
    assert "в руках партнёра" in next(row["touch"] for row in catalog if row["id"] == "tulip")


