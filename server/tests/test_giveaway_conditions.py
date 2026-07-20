"""Розыгрыши: чистые функции проверки условий участия, без БД."""
from giveaway_conditions import all_conditions_met, condition_satisfied


def test_balance_condition():
    cond = {"kind": "balance", "target_value": 500}
    ctx_ok = {"balance": 500, "harvest_count": 0, "items": {}}
    ctx_low = {"balance": 499, "harvest_count": 0, "items": {}}
    assert condition_satisfied(ctx_ok, cond) is True
    assert condition_satisfied(ctx_low, cond) is False


def test_harvest_count_condition():
    cond = {"kind": "harvest_count", "target_value": 10}
    assert condition_satisfied({"balance": 0, "harvest_count": 10, "items": {}}, cond) is True
    assert condition_satisfied({"balance": 0, "harvest_count": 9, "items": {}}, cond) is False


def test_item_count_condition():
    cond = {"kind": "item_count", "target_value": 3, "item_id": "Ключ"}
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {"Ключ": 3}}, cond) is True
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {"Ключ": 2}}, cond) is False
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {}}, cond) is False


def test_referral_count_condition():
    cond = {"kind": "referral_count", "target_value": 3}
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {}, "referral_count": 3}, cond) is True
    assert condition_satisfied({"balance": 0, "harvest_count": 0, "items": {}, "referral_count": 2}, cond) is False


def test_channel_sub_condition():
    cond = {"kind": "channel_sub", "target_value": 1, "item_id": "cute_channel"}
    ctx_subscribed = {"balance": 0, "harvest_count": 0, "items": {}, "channel_sub": {"cute_channel": True}}
    ctx_not_subscribed = {"balance": 0, "harvest_count": 0, "items": {}, "channel_sub": {"cute_channel": False}}
    ctx_missing = {"balance": 0, "harvest_count": 0, "items": {}, "channel_sub": {}}
    assert condition_satisfied(ctx_subscribed, cond) is True
    assert condition_satisfied(ctx_not_subscribed, cond) is False
    assert condition_satisfied(ctx_missing, cond) is False


def test_unknown_kind_is_not_satisfied():
    # Условия из будущих фаз (quest_count и т.п.) не должны падать с
    # исключением — просто "не выполнено" до того, как появится чекер.
    cond = {"kind": "quest_count", "target_value": 1}
    ctx = {"balance": 999999, "harvest_count": 999999, "items": {}}
    assert condition_satisfied(ctx, cond) is False


def test_all_conditions_met_is_and_logic():
    ctx = {"balance": 500, "harvest_count": 10, "items": {"Ключ": 3}}
    conditions = [
        {"kind": "balance", "target_value": 500},
        {"kind": "harvest_count", "target_value": 10},
        {"kind": "item_count", "target_value": 3, "item_id": "Ключ"},
    ]
    assert all_conditions_met(ctx, conditions) is True

    conditions_with_one_unmet = conditions + [{"kind": "balance", "target_value": 501}]
    assert all_conditions_met(ctx, conditions_with_one_unmet) is False


def test_no_conditions_means_available_to_everyone():
    ctx = {"balance": 0, "harvest_count": 0, "items": {}}
    assert all_conditions_met(ctx, []) is True
