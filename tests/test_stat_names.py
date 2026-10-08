"""Статистика не упоминает людей: ни tg://user, ни @username в сводке."""
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_statistics_do_not_mention_people():
    top = (ROOT / "bot" / "funcs" / "top.py").read_text(encoding="utf-8")
    king = (ROOT / "bot" / "runtime" / "king_stats_worker.py").read_text(encoding="utf-8")
    assert "tg://user" not in top
    assert "tg://user" not in king
    assert 'return f"@{html.escape(uname)}"' not in king
    assert "def stat_person_html" in top
    assert top.count("return stat_person_html(") >= 4
