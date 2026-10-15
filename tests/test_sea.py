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
    assert lines[0].split() == list("ABCDEFGH")
    assert [line.split()[0] for line in lines[1:]] == [str(i) for i in range(1, 9)]
    assert lines[0].index("A") == lines[1].index(".")
    assert lines[-1].index(".") == lines[0].index("A")


def test_chart_escapes_ship_bows_inside_pre():
    page = chart_html({(0, 0): "<"})
    assert page.startswith("<pre>")
    assert "&lt;" in page


def test_ships_stay_straight_and_do_not_touch_even_by_a_corner():
    ok, ships, code = place_ship([], 3, 0, 0, True)
    assert ok and code == ""
    assert ships[0] == ((0, 0), (0, 1), (0, 2))
    ok, _, code = place_ship(ships, 1, 1, 3, True)
    assert not ok and code == "touch"
    ok, _, code = place_ship(ships, 3, 0, 6, True)
    assert not ok and code == "edge"
    ok, _, code = place_ship(ships, 3, 2, 0, True)
    assert not ok and code == "count"
    ok, down, code = place_ship([], 3, 0, 0, False)
    assert ok and code == ""
    assert down[0] == ((0, 0), (1, 0), (2, 0))


def test_a_full_fleet_can_stand_without_touching():
    ships = []
    plan = [
        (3, 0, 0, True),
        (2, 2, 0, True),
        (2, 2, 3, True),
        (1, 4, 0, True),
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
    assert "<pre>" not in page
    assert "Ход" in page


def test_button_rows_stay_within_eight_and_keep_coordinates():
    kb = aim_markup("sea:", 7, 0, {})
    assert len(kb.inline_keyboard[0]) == 8
    assert kb.inline_keyboard[0][0].callback_data == "sea:c:7:0"
    assert kb.inline_keyboard[0][5].callback_data == "sea:c:7:5"
    for row in kb.inline_keyboard:
        assert len(row) <= 8
    place = place_markup("sea:", 1, [], 0)
    assert any(button.text == "Готово" for row in place.inline_keyboard for button in row)
    assert any(button.text == "Авто" for row in place.inline_keyboard for button in row)
    assert any(button.text == "Выставить вручную" for row in place.inline_keyboard for button in row)
    assert any(
        getattr(button, "icon_custom_emoji_id", None) == "5805509901048356965"
        for row in place.inline_keyboard for button in row
    )
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
    assert next_length([]) == 3
    three = [((0, 0), (0, 1), (0, 2))]
    assert next_length(three) == 2
    assert next_length(three, 3) == 2
    assert ship_face(4, 1, True).startswith("✓")
    assert "▬" in ship_face(3, 2, False)
    lobby = lobby_text({"bet": 0, "creator": 1, "participants": [1], "links": {1: "A"}})
    assert "Ставка" not in lobby
    assert "• <b>A</b>" in lobby
    paid = lobby_text({"bet": 10, "creator": 1, "participants": [1, 2], "links": {1: "A", 2: "B"}})
    assert "5381975814415866082" in paid
    assert "Ставка - 10 кут" in paid
    board = aim_markup("sea:", 3, 0, {})
    names = [button.text for row in board.inline_keyboard for button in row]
    assert "Мои корабли" in names and "Сдаться" in names
    sea_board = place_markup("sea:", 3, [((0, 0), (0, 1), (0, 2))], 0, 0)
    sea_names = [button.text for row in sea_board.inline_keyboard for button in row]
    assert "Готово" in sea_names and "Авто" in sea_names and "Выставить вручную" in sea_names
    icons = [getattr(button, "icon_custom_emoji_id", None) for row in sea_board.inline_keyboard for button in row]
    assert "5807601906603792598" in icons and "5805509901048356965" in icons
    assert "5807492110059838726" in icons
    assert any(button.callback_data.startswith("sea:m:") for row in sea_board.inline_keyboard for button in row)


def test_plain_command_is_a_game_command():
    from pathlib import Path

    from bot.games.invoke import looks_like_game_command

    assert looks_like_game_command("морской бой")
    assert looks_like_game_command("морской бой 10")
    assert looks_like_game_command("морскойбой")
    assert looks_like_game_command("battleship")
    assert looks_like_game_command("морская битва")
    assert not looks_like_game_command("морской")
    source = Path(__file__).resolve().parents[1].joinpath("main.py").read_text(encoding="utf-8")
    start = source.find("custom_commands = {")
    end = source.find("_custom_cmds_by_first_char", start)
    body = source[start:end]
    for phrase in ("морской бой", "морская битва", "морскойбой", "battleship"):
        assert phrase in body


def test_inline_card_is_the_shared_table():
    from bot.design.sea_inline import catalog_article
    from bot.games.sea import LOBBY_SECONDS, _surface, lobby_markup, place_public_markup, public_channel

    game = {"inline_id": "abc", "chat_id": 0, "message_id": 0}
    assert public_channel(game) == "inline"
    assert public_channel({"inline_id": "", "chat_id": 5, "message_id": 9}) == "chat"

    class InlineClick:
        inline_message_id = "abc"
        message = None

    class PrivateClick:
        inline_message_id = ""
        message = None

    assert _surface(InlineClick(), game) == "public"
    assert _surface(PrivateClick(), game) == "none"
    assert catalog_article(7) is None
    assert LOBBY_SECONDS == 7200
    full = {
        "prefix": "sea:",
        "id": 4,
        "participants": [1, 2],
        "creator": 1,
        "level": "easy",
    }
    names = [button.text for row in lobby_markup(full).inline_keyboard for button in row]
    assert "Присоединиться" not in names
    assert "Начать" in names
    public = place_public_markup(full)
    assert [button.text for row in public.inline_keyboard for button in row] == ["Моё море"]
    assert "Выйти" not in [button.text for row in public.inline_keyboard for button in row]


def test_auto_place_is_random_and_a_ship_can_move():
    from bot.games.sea import _jsonify, _revive, scatter, shift_ship, turn_ship

    layouts = {tuple(tuple(ship) for ship in scatter()) for _ in range(12)}
    assert len(layouts) > 1
    for ships in layouts:
        assert fleet_ready(ships)
    base = [((0, 0), (0, 1))]
    ok, moved = shift_ship(base, 0, 1, 0)
    assert ok and moved[0] == ((1, 0), (1, 1))
    ok, spun = turn_ship(base, 0)
    assert ok and spun[0][0][1] == spun[0][1][1]
    packed = _revive(_jsonify({"ships": base, "hits": {(0, 0)}}))
    assert packed["ships"][0] == ((0, 0), (0, 1))
    assert (0, 0) in packed["hits"]


def test_premium_slot_sits_on_the_button(monkeypatch):
    monkeypatch.setitem(sea.FACE, "again", "100")
    board = sea.place_markup("sea:", 1, [], 0)
    again = board.inline_keyboard[0][0]
    assert again.text == "Авто"
    assert again.icon_custom_emoji_id == "100"
    monkeypatch.setitem(sea.FACE, "ship_one", "200")
    monkeypatch.setitem(sea.FACE, "ship_left", "201")
    monkeypatch.setitem(sea.FACE, "ship_mid_h", "202")
    monkeypatch.setitem(sea.FACE, "ship_right", "203")
    cells = sea.place_markup("sea:", 1, [((0, 0),), ((1, 0), (1, 1), (1, 2))], 0)
    assert cells.inline_keyboard[2][0].icon_custom_emoji_id == "200"
    assert cells.inline_keyboard[2][0].text == " "
    row = cells.inline_keyboard[3]
    assert [button.icon_custom_emoji_id for button in row[:3]] == ["201", "202", "203"]
    hidden = sea.aim_markup("sea:", 1, 0, [((0, 0), (0, 1), (0, 2))], {(0, 0)}, set())
    assert hidden.inline_keyboard[0][0].icon_custom_emoji_id == "5469785308386041323"
    assert hidden.inline_keyboard[0][1].text == "\u3164"
    sunk = sea.aim_markup("sea:", 1, 0, [((0, 0), (0, 1))], {(0, 0), (0, 1)}, set())
    assert sunk.inline_keyboard[0][0].icon_custom_emoji_id == "5276032951342088188"
    assert sunk.inline_keyboard[0][1].icon_custom_emoji_id == "5276032951342088188"
    hand = sea.place_markup("sea:", 1, [((3, 3),)], 0, hand=True, tool=2)
    blocked = next(button for row in hand.inline_keyboard for button in row if button.callback_data == "sea:c:1:28")
    assert blocked.icon_custom_emoji_id == "5350475991691052862"
    assert "Выставить вручную" not in [button.text for row in hand.inline_keyboard for button in row]


def test_levels_squares_and_the_coin_ring():
    from bot.games.sea import LEVELS, lobby_markup, stake_line

    assert stake_line(0) == ""
    easy, mid, hard = (item[2] for item in LEVELS)
    assert sum(easy) == 8 and sum(mid) == 10 and sum(hard) == 12
    for fleet in (easy, mid, hard):
        ships = sea._fallback_fleet(fleet)
        assert sea.fleet_ready(ships, fleet)
        assert sea.fleet_ready(sea.scatter(fleet=fleet), fleet)
    game = {
        "prefix": "sea:",
        "id": 4,
        "participants": [1],
        "creator": 1,
        "level": "easy",
        "bet": 0,
    }
    names = [button.text for row in lobby_markup(game).inline_keyboard for button in row]
    assert names[:3] == ["Лёгкий 8", "Средний 10", "Сложный 12"]
    assert "Отмена" not in names
    assert "Присоединиться" in names
    note = sea.secret_place_text({"hand": True, "ships": [((0, 0),)]}, 8)
    assert "Клеток ещё можно занять" in note and "<b>7</b>" in note
    ok, grown, code = sea.hand_put([], 0, 0, 8)
    assert ok and code == "new" and grown == [((0, 0),)]
    ok, grown, code = sea.hand_put(grown, 0, 1, 8)
    assert ok and code == "grow" and len(grown[0]) == 2
    ok, _, code = sea.hand_put(grown, 1, 1, 8)
    assert not ok and code == "diag"
    ok, grown, code = sea.hand_put(grown, 0, 2, 8)
    assert ok and len(grown[0]) == 3
    ok, _, code = sea.hand_put(grown, 0, 3, 8)
    assert not ok and code == "long"
    board = place_markup("sea:", 1, [((0, 0), (0, 1))], 0)
    square = sea._PART_TEXT["one"]
    assert board.inline_keyboard[2][0].text == square
    assert board.inline_keyboard[2][1].text == square
    assert square == "◻️"
    held = place_markup("sea:", 1, [((0, 0),)], 0, hold=0)
    ring = next(button for row in held.inline_keyboard for button in row if button.callback_data == "sea:c:1:1")
    assert ring.icon_custom_emoji_id == "5350475991691052862"
    page = sea.end_text(
        {"bet": 10, "links": {1: "A"}},
        1,
        "Все корабли соперника потоплены.",
        9,
    )
    assert "5469967260380612012" in page
    assert "<b>A - победитель!</b>" in page
    assert "<b>Выигрыш - 9 кут</b>" in page
    assert "<i>Все корабли соперника потоплены.</i>" in page
    assert len(sea.end_markup({"boards": {}}, 1, None).inline_keyboard) == 0


def test_hidden_sea_links_are_cleared_after_leave():
    board = {
        "mode": "ephemeral",
        "ephemeral_id": 17,
        "message_id": 9,
        "chat_id": -100,
    }
    sea._clear_board_link(board)
    assert board["mode"] == "none"
    assert board["ephemeral_id"] == 0
    assert board["message_id"] == 0


def test_a_fast_repeat_asks_once_to_wait():
    sea._PACE_AT.clear()
    sea._WARN_AT.clear()
    assert sea._pace(9, 3, stamp=True) == ""
    assert sea._pace(9, 3, stamp=False) == "alert"
    assert sea._pace(9, 3, stamp=False) == "quiet"
    sea._PACE_AT[(9, 3)] = 0.0
    assert sea._pace(9, 3, stamp=True) == ""
    sea._drop_pace(9)
    assert (9, 3) not in sea._PACE_AT


def test_help_knows_the_game():
    from bot.games.howto import read_howto
    from bot.games.rules import rules_html

    ask = read_howto("как играть в морской бой")
    assert ask is not None and ask.key == "sea"
    text = rules_html("sea")
    assert text is not None
    assert "Морской бой" in text
    assert "8" in text
    assert "не касаются" in text
