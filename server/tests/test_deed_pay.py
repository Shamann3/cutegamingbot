"""Нормы оплаты за наказания: сколько кут и откуда списывать."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from deed_pay import milestones_for, plan_take, progress_line


def test_hundred_confirmed_bans_are_one_payout():
    assert milestones_for(99, 100) == 0
    assert milestones_for(100, 100) == 1
    assert milestones_for(250, 100) == 2
    assert milestones_for(10, 0) == 0
    line = progress_line(37, 100, 200)
    assert line == {"confirmed": 37, "into": 37, "left": 63, "nextReward": 200}


def test_kut_comes_from_the_richest_technical_groups_first():
    assert plan_take([(11, 150), (22, 80)], 200) == [(11, 150), (22, 50)]
    assert plan_take([(11, 500)], 200) == [(11, 200)]
    try:
        plan_take([(11, 40)], 200)
    except ValueError as exc:
        assert "не хватает" in str(exc)
    else:
        raise AssertionError("short purse must fail")
