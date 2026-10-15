# -*- coding: utf-8 -*-
"""Морской бой: поле, касание, обводка, кнопки и команда."""
import re

import bot.games.sea as sea
from bot.games.sea import (
    aim_markup,
    apply_shot,
    button_char,
    chart,
    chart_html,
    fight_text,
    fleet_ready,
    halo_cells,
    own_marks,
    parse_sea,
    place_markup,
    place_ship,
    place_text,
    public_marks,
    sea_command,
    shape,
)


def test_command_accepts_the_game_and_refuses_a_bare_mb():
    assert parse_sea("морской бой") == ("play", 0)
    assert parse_sea("Морской бой 10") == ("play", 10)
    assert parse_sea("морская битва 1.000") == ("play", 1000)
    assert parse_sea("battleship") == ("play", 0)
    assert parse_sea("морскойбой25") == ("play", 25)
    assert parse_sea("мб")[0] == "ignore"
    assert parse_sea("морской")[0] == "ignore"
    assert parse_sea("морской бой хелп")[0] == "help"
    assert parse_sea("морской бой привет")[0] == "bad"
    assert sea_command("морской бой") is True
    assert sea_command("мб 10") is False
    assert sea_command("морской бой хелп") is False


def test_chart_puts_letters_on_top_and_numbers_down_the_side():
    text = chart({})
    lines = text.splitlines()
    assert lines[0].split() == list("ABCDEFGHIJ")
    assert [line.split()[0] for line in lines[1:]] == [str(i) for i in range(1, 11)]
    assert lines[0].index("A") == lines[1].index(".")
    assert lines[-1].index(".") == lines[0].index("A")


def test_chart_escapes_ship_bows_inside_pre():
    page = chart_html({(0, 0): "<"})
    assert page.startswith("<pre>")
    assert "&lt;" in page


def test_ships_stay_straight_and_do_not_touch_even_by_a_corner():
    ok, ships, code = place_ship([], 4, 0, 0, True)
    assert ok and code == ""
    assert ships[0] == ((0, 0), (0, 1), (0, 2), (0, 3))
    ok, _, code = place_ship(ships, 1, 1, 4, True)
    assert not ok and code == "touch"
    ok, _, code = place_ship(ships, 4, 0, 7, True)
    assert not ok and code == "edge"
    ok, _, code = place_ship(ships, 4, 2, 0, True)
    assert not ok and code == "count"
    ok, down, code = place_ship([], 3, 0, 0, False)
    assert ok and code == ""
    assert down[0] == ((0, 0), (1, 0), (2, 0))


def test_a_full_fleet_can_stand_without_touching():
    ships = []
    plan = [
        (4, 0, 0, True),
        (3, 2, 0, True),
        (3, 2, 4, True),
        (2, 4, 0, True),
        (2, 4, 3, True),
        (2, 4, 6, True),
        (1, 6, 0, True),
        (1, 6, 2, True),
        (1, 6, 4, True),
        (1, 6, 6, True),
    ]
    for length, r, c, across in plan:
        ok, ships, code = place_ship(ships, length, r, c, across)
        assert ok and code == "", code
    assert fleet_ready(ships)


def test_live_ship_is_hidden_and_a_sunk_one_keeps_its_shape_inside_a_ring():
    ships = [((0, 0), (0, 1), (0, 2))]
    hidden = public_marks(ships, set(), set())
    assert (0, 0) not in hidden
    wounded = public_marks(ships, {(0, 1)}, set())
    assert wounded[(0, 1)] == "x"
    assert (0, 0) not in wounded
    sunk = public_marks(ships, {(0, 0), (0, 1), (0, 2)}, set())
    assert sunk[(0, 0)] == "<"
    assert sunk[(0, 1)] == "="
    assert sunk[(0, 2)] == ">"
    assert sunk[(1, 1)] == "+"
    assert sunk[(0, 3)] == "+"
    assert (0, 1) not in halo_cells(ships, {(0, 0), (0, 1), (0, 2)})
    own = own_marks(ships, set(), set())
    assert own[(0, 0)] == "<" and own[(0, 2)] == ">"
    assert shape(((5, 5),), 5, 5) == "#"
    assert button_char("<") == "◀"
    assert button_char("+") == "▫"
    assert button_char("#") == "●"


def test_shot_repeats_misses_and_only_wins_when_every_ship_is_down():
    ships = [((0, 0), (0, 1)), ((3, 3),)]
    kind, hits, misses = apply_shot(ships, set(), set(), 5, 5)
    assert kind == "miss" and (5, 5) in misses
    kind, hits, misses = apply_shot(ships, hits, misses, 0, 0)
    assert kind == "hit"
    kind, hits, misses = apply_shot(ships, hits, misses, 0, 0)
    assert kind == "repeat"
    kind, hits, misses = apply_shot(ships, hits, misses, 0, 1)
    assert kind == "sunk"
    kind, hits, misses = apply_shot(ships, hits, misses, 3, 3)
    assert kind == "win"
    kind, hits, misses = apply_shot([((0, 0),)], set(), set(), 0, 0)
    assert kind == "win"
    kind, _, _ = apply_shot([((0, 0),)], hits, misses, 0, 1)
    assert kind == "halo"


def test_public_place_has_no_map_and_the_fight_hides_a_live_fleet():
    game = {
        "players": [1, 2],
        "boards": {1: {"ready": False}, 2: {"ready": True}},
        "links": {1: "A", 2: "B"},
    }
    text = place_text(game)
    assert "<pre>" not in text
    assert "расставляет" in text and "готов" in text
    fight = {
        "players": [1, 2],
        "turn": 1,
        "first": 2,
        "skips": {1: 0, 2: 0},
        "note": "",
        "boards": {
            1: {"ships": [((0, 0), (0, 1), (0, 2))]},
            2: {"ships": [((4, 4),)]},
        },
        "shots": {
            1: {"hit": set(), "miss": set()},
            2: {"hit": set(), "miss": set()},
        },
        "links": {1: "A", 2: "B"},
    }
    page = fight_text(fight)
    bodies = re.findall(r"<pre>(.*?)</pre>", page, flags=re.S)
    assert bodies
    assert all("&lt;" not in body and "<" not in body for body in bodies)


def test_button_rows_stay_within_eight_and_keep_coordinates():
    kb = aim_markup("sea:", 7, 0, {})
    assert [button.text for button in kb.inline_keyboard[0]] == ["◎", *"ABCDE"]
    assert [row[0].text for row in kb.inline_keyboard[1:11]] == [str(i) for i in range(1, 11)]
    assert kb.inline_keyboard[1][1].callback_data == "sea:c:7:0"
    for row in kb.inline_keyboard:
        assert len(row) <= 8
    other = aim_markup("sea:", 7, 1, {})
    assert other.inline_keyboard[0][1].text == "F"
    assert other.inline_keyboard[1][1].callback_data == "sea:c:7:5"
    place = place_markup("sea:", 1, [], 0, True, 3)
    assert any(button.text == "Готово" for row in place.inline_keyboard for button in row)
    assert any(button.text == "A" for row in place.inline_keyboard for button in row)
    assert any(button.text == "1" for row in place.inline_keyboard for button in row)
    for row in place.inline_keyboard:
        assert len(row) <= 8


def test_a_wide_page_setting_still_fits_the_row(monkeypatch):
    monkeypatch.setattr(sea, "PAGE", 10)
    kb = sea.aim_markup("sea:", 1, 0, {})
    for row in kb.inline_keyboard:
        assert len(row) <= 8
    assert len(kb.inline_keyboard[0]) == 8


def test_the_table_shows_the_next_step():
    from bot.games.sea import guide_text, label_hint, lobby_text, next_length, ship_face

    for phase in ("lobby", "place", "fight"):
        text = guide_text(phase)
        assert 0 < len(text) <= 200
    assert "Присоединиться" in guide_text("lobby")
    assert "Готово" in guide_text("place")
    assert "Мои корабли" in guide_text("fight")
    assert "столбца" in label_hint("a")
    assert "ряда" in label_hint("n")
    assert next_length([]) == 4
    four = [((0, 0), (0, 1), (0, 2), (0, 3))]
    assert next_length(four) == 3
    assert next_length(four, 4) == 3
    assert ship_face(4, 1, True).startswith("✓")
    assert "▬" in ship_face(3, 2, False)
    lobby = lobby_text({"bet": 0, "creator": 1, "participants": [1], "links": {1: "A"}})
    assert "Присоединиться" in lobby and "Начать игру" in lobby
    board = aim_markup("sea:", 3, 0, {})
    names = [button.text for row in board.inline_keyboard for button in row]
    assert "Как играть" in names and "Мои корабли" in names and "Сдаться" in names
    sea_board = place_markup("sea:", 3, [], 0, True, 4)
    sea_names = [button.text for row in sea_board.inline_keyboard for button in row]
    assert "Как играть" in sea_names and "Готово" in sea_names
    assert any("Вправо" in name for name in sea_names)
    assert any(button.callback_data.startswith("sea:h:") for row in sea_board.inline_keyboard for button in row)


def test_help_knows_the_game():
    from bot.games.howto import read_howto
    from bot.games.rules import rules_html

    ask = read_howto("как играть в морской бой")
    assert ask is not None and ask.key == "sea"
    text = rules_html("sea")
    assert text is not None
    assert "Морской бой" in text
    assert "10" in text
    assert "не касаются" in text
