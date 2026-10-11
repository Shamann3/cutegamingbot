# -*- coding: utf-8 -*-
"""Выдача из вкладки «Игроки» должна находиться командой «использовать»."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "bot" / "funcs"))

from item_use_match import pick_held_row
from user_items import fold_item_onto_name


SAFE = {"id": "339", "name": "Сухой сейф", "name1": "drysafe", "emoji": "💎"}
RING = {"id": "12", "name": "Обручальное", "name1": "mrgring", "emoji": "💎"}


def test_grant_lands_under_the_name_the_bot_uses():
    stored = fold_item_onto_name({"339": 1, "старое": 2}, name="Сухой сейф", item_id="339", name1="drysafe")
    assert stored["Сухой сейф"] == 1
    assert "339" not in stored
    assert stored["старое"] == 2


def test_use_picks_the_safe_even_when_another_item_shares_the_emoji():
    row, key = pick_held_row([RING, SAFE], {"339": 1})
    assert row["name1"] == "drysafe"
    assert key == "339"


def test_use_picks_the_named_copy_after_a_grant_was_folded():
    row, key = pick_held_row([RING, SAFE], {"Сухой сейф": 1})
    assert row["name"] == "Сухой сейф"
    assert key == "Сухой сейф"


def test_use_ignores_a_diamond_the_player_does_not_hold():
    row, key = pick_held_row([RING, SAFE], {"Вода": 3})
    assert row is None
    assert key is None
