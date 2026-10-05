from pathlib import Path

from meme_mode import clamp_chance, creator_only, dump_excluded, parse_excluded


def test_chance_stays_between_zero_and_hundred():
    assert clamp_chance(None) == 10
    assert clamp_chance("нет") == 10
    assert clamp_chance(-4) == 0
    assert clamp_chance(140) == 100
    assert clamp_chance("55") == 55


def test_excluded_ids_are_unique_positive_numbers():
    assert parse_excluded("6801702632, 12\n12 abc 0 -3") == [6801702632, 12]
    assert dump_excluded([4, 4, "8"]) == "4 8"


def test_only_the_project_creator_may_change_the_chance():
    root = Path(__file__).resolve().parents[1]
    source = (root / "admin_routes.py").read_text(encoding="utf-8")
    meme = (root / "meme_mode.py").read_text(encoding="utf-8")
    lines = [line.strip() for line in meme.splitlines()]
    assert "meme_mode_save" in source
    assert "Это может менять только создатель проекта" in source
    assert "from db import db" in lines
    assert "import db" not in lines
    assert creator_only(0) is False
