"""Имя в сообщениях: ссылка t.me, если юзернейм настоящий, иначе просто имя."""
import sys
from pathlib import Path

from bot.funcs.person_html import person_name_html

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from person_html import person_name_html as server_person_name_html


def test_username_becomes_quiet_link():
    html = person_name_html("Vasya", "vasya")
    assert html == '<a href="https://t.me/vasya">Vasya</a>'
    assert server_person_name_html("Ann", "@ann_k") == '<a href="https://t.me/ann_k">Ann</a>'


def test_missing_username_is_plain_name():
    html = person_name_html("<b>Hacker</b>", "")
    assert html == "&lt;b&gt;Hacker&lt;/b&gt;"
    assert "<a" not in html
    assert "tg://" not in html


def test_bad_username_is_not_a_link():
    html = person_name_html("Игрок", "12")
    assert html == "Игрок"
    assert "t.me" not in html
    assert person_name_html("", None, empty="Без имени") == "Без имени"


def test_empty_name_uses_handle():
    assert person_name_html("", "durov") == '<a href="https://t.me/durov">durov</a>'
