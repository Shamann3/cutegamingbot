# -*- coding: utf-8 -*-
from bot.funcs.tg_dice import (
    is_basket_hit,
    is_bowling_strike,
    is_darts_bullseye,
    is_soccer_goal,
    read_dice_value,
)
# Fortuna тянет main.py — проверяем константу без полного импорта игры.
import ast
from pathlib import Path


class _Dice:
    def __init__(self, value):
        self.value = value


class _Msg:
    def __init__(self, value):
        self.dice = _Dice(value) if value is not None else None


def test_soccer_only_real_goals():
    assert is_soccer_goal(4) and is_soccer_goal(5)
    assert not is_soccer_goal(3)
    assert not is_soccer_goal(1)
    assert not is_soccer_goal(None)


def test_other_official_wins():
    assert is_basket_hit(4) and is_basket_hit(5) and not is_basket_hit(3)
    assert is_darts_bullseye(6) and not is_darts_bullseye(5)
    assert is_bowling_strike(6) and not is_bowling_strike(5)


def test_read_dice_value():
    assert read_dice_value(_Msg(5)) == 5
    assert read_dice_value(_Msg(None)) is None
    assert read_dice_value(_Msg(0)) is None


def test_single_number_is_rare():
    src = Path("bot/games/Fortuna.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    chance = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "FORTUNA_SINGLE_NUMBER_WIN_CHANCE":
                    chance = ast.literal_eval(node.value)
    assert chance is not None
    assert 0.02 <= float(chance) <= 0.04
