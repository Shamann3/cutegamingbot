# -*- coding: utf-8 -*-
"""Ника: формула долива/сбора и лестница источников — без живой базы."""

from bot.config.config import (
    BACKGROUND_EARNINGS_CHAT_ID,
    GAME_COMMISSION_CHAT_ID,
    PROFIT_JAR_CHAT_ID,
    TECH_CHAT_ID,
)
from bot.runtime.nika.policy import (
    SOURCE_LADDER,
    SWEEP_DEST_CHAT_ID,
    SWEEP_DEST_LADDER,
    GroupPolicy,
    allocate_from_ladder,
    apply_sweep_speed,
    dead_zone,
    pick_sweep_dest,
    plan_drain_sweep,
    plan_sweep,
    plan_topup,
    suggest_caps,
    sweep_keep,
)
from bot.runtime.nika.schema import FIRST_MANAGED_CHAT_ID, FIRST_MANAGED_TARGET
from bot.runtime.nika.store import forbidden_managed_ids


OFFICIAL = GroupPolicy(
    chat_id=FIRST_MANAGED_CHAT_ID,
    target_balance=FIRST_MANAGED_TARGET,
    speed_mode="auto",
    max_transfer=1000,
    max_daily_topup=10000,
    max_daily_sweep=10000,
)


def test_admin_nika_ids_match_bot_config():
    import sys

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "server"))
    from nika.ids import (
        BACKGROUND_EARNINGS_CHAT_ID as ADMIN_BG,
        GAME_COMMISSION_CHAT_ID as ADMIN_COMM,
        GROWTH_FUND_OWNER_NOTIFY_USER_ID as ADMIN_OWNER,
        PROFIT_JAR_CHAT_ID as ADMIN_JAR,
        TECH_CHAT_ID as ADMIN_TECH,
    )
    from nika.policy import (
        SOURCE_LADDER as ADMIN_LADDER,
        SWEEP_DEST_LADDER as ADMIN_DEST,
        apply_sweep_speed as admin_apply,
        pick_sweep_dest as admin_pick,
        plan_sweep as admin_sweep,
        plan_topup as admin_topup,
        GroupPolicy as AdminPolicy,
    )

    from bot.config.config import (
        BACKGROUND_EARNINGS_CHAT_ID,
        GAME_COMMISSION_CHAT_ID,
        GROWTH_FUND_OWNER_NOTIFY_USER_ID,
        PROFIT_JAR_CHAT_ID,
        TECH_CHAT_ID,
    )

    assert ADMIN_JAR == PROFIT_JAR_CHAT_ID
    assert ADMIN_COMM == GAME_COMMISSION_CHAT_ID
    assert ADMIN_BG == BACKGROUND_EARNINGS_CHAT_ID
    assert ADMIN_TECH == TECH_CHAT_ID
    assert ADMIN_OWNER == GROWTH_FUND_OWNER_NOTIFY_USER_ID
    assert [cid for cid, _ in ADMIN_LADDER] == [cid for cid, _ in SOURCE_LADDER]
    assert [cid for cid, _ in ADMIN_DEST] == [cid for cid, _ in SWEEP_DEST_LADDER]
    bot_plan = plan_topup(OFFICIAL, balance=0)
    admin_plan = admin_topup(AdminPolicy(chat_id=OFFICIAL.chat_id, target_balance=OFFICIAL.target_balance, speed_mode="auto", max_transfer=1000, max_daily_topup=10000, max_daily_sweep=10000), balance=0)
    assert admin_plan.action == bot_plan.action
    assert admin_plan.amount == bot_plan.amount
    hot = GroupPolicy(chat_id=1, target_balance=3000, max_transfer=600, max_daily_topup=6000, max_daily_sweep=6000)
    bot_s = plan_sweep(apply_sweep_speed(hot, "fast"), balance=3152, stable_balance=3152, history_covers_delay=True)
    admin_s = admin_sweep(admin_apply(AdminPolicy(chat_id=1, target_balance=3000, max_transfer=600, max_daily_topup=6000, max_daily_sweep=6000), "fast"), balance=3152, stable_balance=3152, history_covers_delay=True)
    assert bot_s.action == admin_s.action == "sweep"
    assert bot_s.amount == admin_s.amount
    assert admin_pick(hot.chat_id) == pick_sweep_dest(hot.chat_id) == TECH_CHAT_ID


def test_ladder_order_is_owner_decision():
    ids = [cid for cid, _ in SOURCE_LADDER]
    assert ids == [
        GAME_COMMISSION_CHAT_ID,
        BACKGROUND_EARNINGS_CHAT_ID,
        TECH_CHAT_ID,
        PROFIT_JAR_CHAT_ID,
    ]
    assert SWEEP_DEST_CHAT_ID == PROFIT_JAR_CHAT_ID
    assert SOURCE_LADDER[-1][0] == PROFIT_JAR_CHAT_ID
    assert [cid for cid, _ in SWEEP_DEST_LADDER] == [
        TECH_CHAT_ID,
        GAME_COMMISSION_CHAT_ID,
        BACKGROUND_EARNINGS_CHAT_ID,
        PROFIT_JAR_CHAT_ID,
    ]
    assert pick_sweep_dest(FIRST_MANAGED_CHAT_ID) == TECH_CHAT_ID
    assert pick_sweep_dest(TECH_CHAT_ID) == GAME_COMMISSION_CHAT_ID


def test_allocate_skips_empty_and_never_overdraws():
    takes, leftover = allocate_from_ladder(
        800,
        (
            (GAME_COMMISSION_CHAT_ID, 0),
            (BACKGROUND_EARNINGS_CHAT_ID, 300),
            (TECH_CHAT_ID, 200),
            (PROFIT_JAR_CHAT_ID, 5000),
        ),
    )
    assert takes == (
        (BACKGROUND_EARNINGS_CHAT_ID, 300),
        (TECH_CHAT_ID, 200),
        (PROFIT_JAR_CHAT_ID, 300),
    )
    assert leftover == 0


def test_allocate_reports_shortfall_when_all_empty():
    takes, leftover = allocate_from_ladder(
        500,
        (
            (GAME_COMMISSION_CHAT_ID, 0),
            (BACKGROUND_EARNINGS_CHAT_ID, 0),
            (TECH_CHAT_ID, 0),
            (PROFIT_JAR_CHAT_ID, 0),
        ),
    )
    assert takes == ()
    assert leftover == 500


def test_dead_zone_for_official_group_is_250():
    assert dead_zone(OFFICIAL) == 250


def test_topup_does_not_close_gap_in_one_shot():
    plan = plan_topup(OFFICIAL, balance=3000, events_24h=200, drain_per_hour=0)
    assert plan.action == "topup"
    assert plan.amount > 0
    assert plan.amount < (5000 - 3000)
    assert plan.amount <= OFFICIAL.max_transfer


def test_topup_inside_dead_zone_does_nothing():
    plan = plan_topup(OFFICIAL, balance=4800, events_24h=200)
    assert plan.action == "none"
    assert plan.amount == 0
    assert plan.skip == "dead_zone"


def test_slow_mode_is_smaller_than_aggressive():
    slow = GroupPolicy(**{**OFFICIAL.__dict__, "speed_mode": "slow"})
    agr = GroupPolicy(**{**OFFICIAL.__dict__, "speed_mode": "aggressive"})
    a = plan_topup(slow, balance=3000)
    b = plan_topup(agr, balance=3000)
    assert a.amount == 100
    assert b.amount == 500
    assert a.cooldown_sec > b.cooldown_sec


def test_daily_cap_blocks_topup():
    plan = plan_topup(OFFICIAL, balance=3000, events_24h=200, daily_topup_used=10000)
    assert plan.amount == 0
    assert plan.skip == "daily_cap"


def test_sweep_waits_for_stable_excess():
    delayed = plan_sweep(
        OFFICIAL,
        balance=6000,
        stable_balance=None,
        history_covers_delay=False,
    )
    assert delayed.skip == "sweep_delay"
    ready = plan_sweep(
        OFFICIAL,
        balance=6000,
        stable_balance=5800,
        history_covers_delay=True,
    )
    assert ready.action == "sweep"
    assert ready.amount > 0
    assert ready.amount <= (5800 - 5000)
    assert 5000 + ready.amount <= 5800


def test_sweep_inside_keep_does_nothing():
    plan = plan_sweep(
        OFFICIAL,
        balance=5040,
        stable_balance=5040,
        history_covers_delay=True,
    )
    assert plan.skip == "keep"
    assert plan.amount == 0


def test_fast_sweep_takes_user_case_152_above_3000():
    policy = apply_sweep_speed(
        GroupPolicy(
            chat_id=1,
            target_balance=3000,
            max_transfer=600,
            max_daily_topup=6000,
            max_daily_sweep=6000,
        ),
        "fast",
    )
    keep = sweep_keep(policy)
    assert keep < 152
    delayed = plan_sweep(policy, balance=3152, stable_balance=None, history_covers_delay=False)
    assert delayed.skip == "sweep_delay"
    assert delayed.cooldown_sec <= 45
    ready = plan_sweep(policy, balance=3152, stable_balance=3152, history_covers_delay=True)
    assert ready.action == "sweep"
    assert ready.amount >= 100
    assert ready.amount <= 152 - keep
    assert 3000 + keep + ready.amount <= 3152
    assert ready.cooldown_sec <= 45
    instant = plan_sweep(
        apply_sweep_speed(policy, "instant"),
        balance=3152,
        stable_balance=3152,
        history_covers_delay=True,
    )
    assert instant.action == "sweep"
    assert instant.amount >= ready.amount
    assert instant.cooldown_sec <= 15


def test_drain_sweep_takes_everything_above_target():
    policy = GroupPolicy(
        chat_id=1,
        target_balance=3000,
        max_transfer=600,
        max_daily_topup=6000,
        max_daily_sweep=10,
        sweep_keep_min=150,
        sweep_keep_pct=0.05,
        sweep_share=0.25,
    )
    plan = plan_drain_sweep(policy, balance=3600)
    assert plan.action == "sweep"
    assert plan.amount == 600
    assert plan.tier == "drain"
    assert plan_drain_sweep(policy, balance=3000).amount == 0
    assert plan_drain_sweep(policy, balance=2999).skip == "on_target"
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "server"))
    from nika.policy import GroupPolicy as AdminPolicy
    from nika.policy import plan_drain_sweep as admin_drain
    admin = admin_drain(AdminPolicy(chat_id=1, target_balance=3000), balance=3600)
    assert admin.amount == 600


def test_suggest_caps_scale_with_target():
    caps = suggest_caps(5000)
    assert caps["max_transfer"] == 1000
    assert caps["max_daily_topup"] == 10000
    assert caps["dead_zone_min"] == 100


def test_tech_wallets_cannot_be_managed():
    forbidden = set(forbidden_managed_ids())
    assert GAME_COMMISSION_CHAT_ID in forbidden
    assert PROFIT_JAR_CHAT_ID in forbidden
    assert FIRST_MANAGED_CHAT_ID not in forbidden
