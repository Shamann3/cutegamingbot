"""Топ лучших игроков: фразы, периоды, текст и кнопка под «Богачи»."""
import pathlib

from bot.funcs.best_players import (
    BEST_PLAYERS_EMOJI_ID,
    BEST_PLAYERS_PLACE_EMOJI_ID,
    best_players_keyboard,
    format_place,
    is_best_players_command,
    parse_best_players_callback,
    period_bounds,
    render_best_players_text,
)
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_phrases():
    for text in (
        "стата игр",
        "Стата Игр",
        "лучшие игроки",
        "Лучшие игроки",
        "топ лучших игроков",
        "  Топ   лучших   игроков  ",
        "статистика игр",
        "кто больше всего играет",
        "топ игроков",
        "сыгранные игры",
    ):
        assert is_best_players_command(text), text

    for text in (
        "стата",
        "статистика",
        "топ",
        "топ богачей",
        "лучший",
        "игры",
        "игры хелп",
        "история игр",
        "стата недели",
        "привет",
    ):
        assert not is_best_players_command(text), text


def test_period_bounds():
    today = date(2026, 9, 30)  # среда
    assert period_bounds("day", today) == (today, today)
    assert period_bounds("week", today) == (date(2026, 9, 28), date(2026, 10, 4))
    assert period_bounds("month", today) == (date(2026, 9, 1), date(2026, 9, 30))
    assert period_bounds("year", today) == (date(2026, 1, 1), date(2026, 12, 31))
    assert period_bounds("all", today) is None
    assert period_bounds("month", date(2024, 2, 10)) == (date(2024, 2, 1), date(2024, 2, 29))


def test_text_matches_rich_top_shape():
    text = render_best_players_text(
        12,
        [(7, 1500), (8, 40), (9, 3), (10, 1)],
        {
            7: ("Анна", "anna"),
            8: ("Боря", None),
            9: (None, "ceo"),
            10: ("Гриша", "grisha"),
        },
    )
    assert f"emoji-id='{BEST_PLAYERS_EMOJI_ID}'" in text
    assert f"emoji-id='{BEST_PLAYERS_PLACE_EMOJI_ID}'" in text
    assert "Статистика лучших игроков проекта" in text
    assert "Ваше место в топе : <i>12</i>" in text
    compact = text.replace(".", "").replace(" ", "").replace("\xa0", "").replace("\u202f", "")
    assert "1500сыгранныхигр" in compact
    assert "кут" not in text
    assert "<b>1. " in text
    assert "<b>3. " in text
    assert "4. " in text
    assert "─" in text
    assert "https://t.me/anna" in text
    assert format_place(None) == "н/a"
    assert format_place(1234) == "1.234"


def test_empty_period_line():
    text = render_best_players_text(None, [], {}, "day")
    assert "Ваше место в топе : <i>н/a</i>" in text
    assert "За сегодня игр пока нет." in text


def test_empty_after_copy_keeps_old_games_out_of_the_line():
    text = render_best_players_text(
        None,
        [],
        {},
        "all",
        "После копии новых игр пока нет. Старые в этот топ не входят.",
    )
    assert "После копии новых игр пока нет." in text
    assert "Игр пока нет." not in text


def test_keyboard_periods_and_footer():
    menu = best_players_keyboard("all", "menu")
    labels = [[button.text for button in row] for row in menu.inline_keyboard]
    assert labels[0] == ["За сегодня"]
    assert labels[1] == ["За неделю", "За месяц", "За год"]
    assert labels[2] == ["✔️ За всё время"]
    assert labels[3] == ["Назад"]
    assert menu.inline_keyboard[2][0].callback_data == "bestplay:all:menu"
    assert menu.inline_keyboard[2][0].icon_custom_emoji_id == "5303138782004924588"
    assert menu.inline_keyboard[3][0].callback_data == "backtop"

    text_kb = best_players_keyboard("day", "text")
    assert text_kb.inline_keyboard[0][0].text == "✔️ За сегодня"
    assert text_kb.inline_keyboard[0][0].callback_data == "bestplay:day:text"
    assert text_kb.inline_keyboard[-1][0].text == "Скрыть"
    assert text_kb.inline_keyboard[-1][0].callback_data == "deletehelp0101"


def test_callback_parse():
    assert parse_best_players_callback("bestplayers") == ("all", "menu")
    assert parse_best_players_callback("bestplay:week:text") == ("week", "text")
    assert parse_best_players_callback("bestplayers:day") is None
    assert parse_best_players_callback("cutessss") is None


def test_top_button_sits_under_rich():
    buttons = (ROOT / "bot" / "design" / "buttons.py").read_text(encoding="utf-8")
    rich = buttons.find("[ btn_topcutes ]")
    players = buttons.find("[ btn_topplayers ]")
    assert rich != -1 and players != -1
    assert rich < players
    assert 'text="Лучшие игроки"' in buttons
    assert 'callback_data="bestplayers"' in buttons
    assert 'icon_custom_emoji_id="5469967260380612012"' in buttons


def test_dispatch_wires_phrases():
    main_py = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "is_best_players_command" in main_py
    assert "ensure_user_games_day_schema" in main_py
    assert "callback_best_players" in main_py
    top_py = (ROOT / "bot" / "funcs" / "top.py").read_text(encoding="utf-8")
    assert "is_best_players_command(message.text)" in top_py
    assert 'c.data == "bestplayers"' in top_py
    db_py = (ROOT / "bot" / "db_create" / "db.py").read_text(encoding="utf-8")
    assert db_py.count("_note_games_played(connection, user_id, increment)") == 4
    assert db_py.count("await game_goes_to_hold(") == 2
    assert "held_board(" in db_py
    assert "epsilon_players_hold" in (ROOT / "server" / "players_hold.py").read_text(encoding="utf-8")
    assert "from server.players_hold import" in (ROOT / "bot" / "funcs" / "players_hold.py").read_text(encoding="utf-8")
    board = (ROOT / "server" / "stat_board.py").read_text(encoding="utf-8")
    assert "from bot.funcs.players_hold import" not in board
    assert "from players_hold import" in board
    assert "CREATE TABLE IF NOT EXISTS user_games_day" in db_py
